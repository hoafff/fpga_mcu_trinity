module primer1_command_core #(
parameter integer CLOCK_HZ = 27000000,
parameter integer UART_BAUD = 115200,
parameter logic [31:0] BUILD_ID = 32'h5031_0001
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
output logic         retained_result_pending_o,
output logic         irq_event_pending_o,
output logic         uart_tx_o,
output logic         heartbeat_o,
output logic         fault_o,
output logic [3:0]   session_state_o,
output logic [2:0]   operation_state_o
);
import trinity_spi_pkg::*;
localparam logic [31:0] CAPABILITIES =
CAP_SELF_TEST | CAP_ZEROIZE | CAP_TRANSACTION_RECONCILIATION |
CAP_SESSION_STAGE_COMMIT | CAP_NTT | CAP_INTT | CAP_BASEMUL |
CAP_ASCON_ENCRYPT | CAP_UART_TX | CAP_DIAGNOSTICS;
localparam integer HEARTBEAT_CYCLES = CLOCK_HZ / 10;
localparam logic [191:0] ASCON_KAT_CT =
192'h64AE2CC0931A7A9101C4872B0A040525B17FC6E9FD6D89E6;
localparam logic [127:0] ASCON_KAT_TAG =
128'h4B9E81835266C56C0884E76F29D95FE8;
typedef enum logic [4:0] {
C_IDLE,
C_WRITE_CHUNK,
C_READ_PRIME,
C_READ_CHUNK,
C_READ_RESP,
C_WAIT_POLY,
C_WAIT_ASCON,
C_WAIT_UART,
C_ZEROIZE_WAIT,
C_ST_ASCON_WAIT,
C_ST_ZERO_WAIT,
C_ST_NTT_WAIT,
C_ST_NTT_SCAN,
C_ST_INTT_WAIT,
C_ST_INTT_SCAN,
C_ST_BM_WAIT,
C_ST_BM_SCAN
} core_state_e;
core_state_e core_state;
session_state_e session_state;
operation_state_e operation_state;
logic self_test_pass;
logic fault_latched;
logic [31:0] diagnostic_summary;
logic [15:0] last_error;
logic [15:0] active_transaction_id;
logic [31:0] staged_session_id, active_session_id;
logic [127:0] staged_key, active_key;
logic [63:0] staged_nonce_prefix, active_nonce_prefix;
logic staged_valid, active_valid;
logic [63:0] sequence_number;
logic telemetry_loaded;
logic [7:0] telemetry_message_type;
logic [15:0] telemetry_flags, telemetry_source_id;
logic [191:0] telemetry_plaintext;
logic [255:0] telemetry_request_image;
logic retained_valid;
logic [15:0] retained_txid;
logic [7:0] retained_command;
logic [31:0] retained_fingerprint;
transaction_state_e retained_state;
logic [15:0] retained_code;
logic [15:0] retained_data_length;
logic [127:0] retained_data;
logic [7:0] poly_operation;
logic [7:0] poly_mask_a, poly_mask_b;
logic [31:0] chunk_fingerprint_a [0:7];
logic [31:0] chunk_fingerprint_b [0:7];
logic [7:0] chunk_valid_a, chunk_valid_b;
logic poly_load_we, poly_load_slot;
logic [7:0] poly_load_addr;
logic [15:0] poly_load_data;
logic poly_read_slot;
logic [7:0] poly_read_addr;
logic [15:0] poly_read_data;
logic poly_start;
logic [1:0] poly_start_operation;
logic poly_busy, poly_done, poly_error;
logic poly_zeroize, poly_zeroize_busy, poly_zeroize_done;
mlkem_poly_accel u_poly (
.clk_i(clk_i), .rst_ni(rst_ni),
.load_we_i(poly_load_we), .load_slot_i(poly_load_slot),
.load_addr_i(poly_load_addr), .load_data_i(poly_load_data),
.read_slot_i(poly_read_slot), .read_addr_i(poly_read_addr),
.read_data_o(poly_read_data), .start_i(poly_start),
.operation_i(poly_start_operation), .busy_o(poly_busy),
.done_o(poly_done), .error_o(poly_error),
.zeroize_i(poly_zeroize), .zeroize_busy_o(poly_zeroize_busy),
.zeroize_done_o(poly_zeroize_done)
);
logic ascon_start, ascon_busy, ascon_done;
logic crypto_abort;
logic [127:0] ascon_key_input, ascon_nonce_input;
logic [191:0] ascon_ad_input, ascon_pt_input;
logic [191:0] ascon_ciphertext;
logic [127:0] ascon_tag;
ascon_aead128_encrypt u_ascon (
.clk_i(clk_i), .rst_ni(rst_ni), .start_i(ascon_start), .abort_i(crypto_abort),
.key_i(ascon_key_input), .nonce_i(ascon_nonce_input),
.ad_i(ascon_ad_input), .plaintext_i(ascon_pt_input),
.busy_o(ascon_busy), .done_o(ascon_done),
.ciphertext_o(ascon_ciphertext), .tag_o(ascon_tag)
);
logic uart_start, uart_busy, uart_done;
logic uart_abort;
