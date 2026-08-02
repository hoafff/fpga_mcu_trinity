module primer2_command_core #(
    parameter integer CLOCK_HZ = 27000000,
    parameter logic [31:0] BUILD_ID = 32'h5032_0001,
    parameter integer BAD_TAG_THRESHOLD = 3
) (
    input  logic         clk_i,
    input  logic         rst_ni,
    input  logic         secure_enable_i,
    input  logic         zeroize_ni,
    input  logic         fatal_latched_i,

    input  logic         request_valid_i,
    input  logic [7:0]   request_command_i,
    input  logic [7:0]   request_flags_i,
    input  logic [15:0]  request_txid_i,
    input  logic [15:0]  request_payload_length_i,
    input  logic [527:0] request_payload_i,
    input  logic [31:0]  request_fingerprint_i,

    input  logic         transport_error_valid_i,
    input  logic [7:0]   transport_error_command_i,
    input  logic [15:0]  transport_error_txid_i,
    input  logic [15:0]  transport_error_code_i,

    output logic         response_commit_o,
    output logic [7:0]   response_command_o,
    output logic [7:0]   response_flags_o,
    output logic [15:0]  response_txid_o,
    output logic [15:0]  response_payload_length_o,
    output logic [527:0] response_payload_o,
    input  logic         response_ready_i,
    input  logic         mailbox_pending_i,

    input  logic         frame_valid_i,
    input  logic [511:0] frame_body_i,
    input  logic         frame_timeout_i,
    input  logic         frame_framing_error_i,
    input  logic         frame_pending_drop_i,
    input  logic         frame_blocked_i,
    input  logic [2:0]   frame_rx_state_i,
    output logic         rx_accept_enable_o,
    output logic         result_pending_o,

    output logic         retained_result_pending_o,
    output logic         authenticated_result_pending_o,
    output logic         irq_event_pending_o,
    output logic         heartbeat_o,
    output logic         fault_o,
    output logic [3:0]   session_state_o,
    output logic [2:0]   operation_state_o,
    output logic [2:0]   rx_state_o
);
  import trinity_spi_pkg::*;

  localparam logic [31:0] CAPABILITIES =
      CAP_SELF_TEST | CAP_ZEROIZE | CAP_TRANSACTION_RECONCILIATION |
      CAP_SESSION_STAGE_COMMIT | CAP_ASCON_DECRYPT | CAP_REPLAY_FILTER |
      CAP_AUTH_RESULT_BUFFER | CAP_DIAGNOSTICS;
  localparam integer HEARTBEAT_CYCLES = CLOCK_HZ / 10;
  localparam logic [15:0] SELFTEST_SUPPORTED_MASK =
      TEST_PROTOCOL | TEST_MEMORY | TEST_ASCON | TEST_UART |
      TEST_SESSION | TEST_ZEROIZE | TEST_HEARTBEAT;
  localparam logic [191:0] ASCON_KAT_CT =
      192'h64AE2CC0931A7A9101C4872B0A040525B17FC6E9FD6D89E6;
  localparam logic [127:0] ASCON_KAT_TAG =
      128'h4B9E81835266C56C0884E76F29D95FE8;

  typedef enum logic [2:0] {
    CORE_IDLE,
    CORE_VALIDATE,
    CORE_DECRYPT,
    CORE_SELFTEST_DECRYPT,
    CORE_ZEROIZE
  } core_state_e;

  core_state_e core_state;
  session_state_e session_state;
  operation_state_e operation_state;

  logic self_test_pass;
  logic fault_latched;
  logic [15:0] last_error;
  logic [31:0] diagnostic_summary;
  logic [15:0] active_transaction_id;

  logic [31:0] staged_session_id, active_session_id;
  logic [127:0] staged_key, active_key;
  logic [63:0] staged_nonce_prefix, active_nonce_prefix;
  logic staged_valid, active_valid;
  logic [63:0] last_accepted_sequence;

  logic retained_valid;
  logic [15:0] retained_txid;
  logic [7:0] retained_command;
  logic [31:0] retained_fingerprint;
  transaction_state_e retained_state;
  logic [15:0] retained_code;
  logic [15:0] retained_data_length;
  logic [127:0] retained_data;

  logic auth_result_valid;
  logic [31:0] auth_result_session_id;
  logic [63:0] auth_result_sequence;
  logic [191:0] auth_result_plaintext;
  logic [15:0] auth_result_status;
  logic last_ack_valid;
  logic [31:0] last_ack_session_id;
  logic [63:0] last_ack_sequence;

  logic [7:0] consecutive_bad_tags;
  logic [15:0] diag_transport_count;
  logic [15:0] diag_crc_count;
  logic [15:0] diag_bad_command_count;
  logic [15:0] diag_transaction_conflict_count;
  logic [15:0] diag_bad_tag_count;
  logic [15:0] diag_replay_stale_count;
  logic [15:0] diag_frame_error_count;
  logic [15:0] diag_result_pending_drop_count;
  logic [15:0] diag_fault_count;
  logic [15:0] diag_selftest_count;

  logic [21:0] heartbeat_counter;
  logic [5:0] zeroize_counter;
  logic zeroize_from_command;
  logic zeroize_due_to_fault;
  logic zeroize_requires_selftest;

  logic [511:0] candidate_frame;
  logic [31:0] candidate_session_id;
  logic [63:0] candidate_sequence;

  logic decrypt_start, decrypt_abort, decrypt_busy, decrypt_done, decrypt_tag_valid;
  logic [127:0] decrypt_key, decrypt_nonce;
  logic [191:0] decrypt_ad, decrypt_ciphertext, decrypt_plaintext;
  logic [127:0] decrypt_tag;

  logic [15:0] selftest_requested_mask;

  logic [527:0] rsp;
  logic [527:0] error_rsp;
  logic [527:0] result_rsp;
  logic [31:0] request_mask;
  logic [31:0] request_session_id;
  logic [63:0] request_sequence;
  logic [31:0] frame_session_id;
  logic [63:0] frame_sequence;
  integer ri;

  function automatic logic [7:0] pbyte(input logic [527:0] p, input integer idx);
    pbyte = p[8*idx +: 8];
  endfunction

  function automatic logic [7:0] fbyte(input logic [511:0] p, input integer idx);
    fbyte = p[8*idx +: 8];
  endfunction

  function automatic logic is_retained_side_effect(input logic [7:0] command);
    begin
      case (command)
        CMD_RUN_SELF_TEST, CMD_ZEROIZE, CMD_COMMIT_SESSION:
          is_retained_side_effect = 1'b1;
        default:
          is_retained_side_effect = 1'b0;
      endcase
    end
  endfunction

  task automatic emit_response(
      input logic [7:0] command,
      input logic [15:0] txid,
