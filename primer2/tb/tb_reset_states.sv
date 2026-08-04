`timescale 1ns/1ps
module tb_reset_states;
  import trinity_spi_pkg::*;

  logic clk_i = 1'b0;
  logic rst_ni = 1'b0;
  logic secure_enable_i = 1'b0;
  logic zeroize_ni = 1'b1;
  logic fatal_latched_i = 1'b0;
  logic request_valid_i = 1'b0;
  logic [7:0] request_command_i = '0;
  logic [7:0] request_flags_i = '0;
  logic [15:0] request_txid_i = '0;
  logic [15:0] request_payload_length_i = '0;
  logic [527:0] request_payload_i = '0;
  logic [31:0] request_fingerprint_i = '0;
  logic transport_error_valid_i = 1'b0;
  logic [7:0] transport_error_command_i = '0;
  logic [15:0] transport_error_txid_i = '0;
  logic [15:0] transport_error_code_i = '0;
  logic response_ready_i = 1'b1;
  logic mailbox_pending_i = 1'b0;
  logic frame_valid_i = 1'b0;
  logic [511:0] frame_body_i = '0;
  logic frame_timeout_i = 1'b0;
  logic frame_framing_error_i = 1'b0;
  logic frame_pending_drop_i = 1'b0;
  logic frame_blocked_i = 1'b0;
  logic [2:0] frame_rx_state_i = RX_HUNT_SYNC;

  logic response_commit_o;
  logic [7:0] response_command_o;
  logic [7:0] response_flags_o;
  logic [15:0] response_txid_o;
  logic [15:0] response_payload_length_o;
  logic [527:0] response_payload_o;
  logic rx_accept_enable_o;
  logic result_pending_o;
  logic retained_result_pending_o;
  logic authenticated_result_pending_o;
  logic irq_event_pending_o;
  logic heartbeat_o;
  logic fault_o;
  logic [3:0] session_state_o;
  logic [2:0] operation_state_o;
  logic [2:0] rx_state_o;

  always #5 clk_i = ~clk_i;

  primer2_command_core #(.CLOCK_HZ(1000)) dut (.*);

  task poison_and_reset(input integer case_id);
    begin
      @(negedge clk_i);
      case (case_id)
        1: force dut.session_state = 4'd4; // STAGED
        2: force dut.session_state = 4'd5; // COMMITTED_BLOCKED
        3: force dut.session_state = 4'd6; // ACTIVE idle
        4: force dut.session_state = 4'd6; // ACTIVE decrypt
        5: force dut.session_state = 4'd6; // ACTIVE result pending
        6: force dut.session_state = 4'd7; // ZEROIZE_BUSY
        7: force dut.session_state = 4'd8; // FAULT_LOCKED
        default: force dut.session_state = 4'd2; // SELF_TEST_RUNNING
      endcase
      force dut.core_state = (case_id == 4) ? 3'd2 :
                             (case_id == 6) ? 3'd4 :
                             (case_id == 8) ? 3'd3 : 3'd0;
      force dut.operation_state = 3'd3;
      force dut.self_test_pass = 1'b1;
      force dut.fault_latched = (case_id == 7);
      force dut.staged_session_id = 32'h1122_3344;
      force dut.active_session_id = 32'h5566_7788;
      force dut.staged_key = 128'h00112233445566778899AABBCCDDEEFF;
      force dut.active_key = 128'hFFEEDDCCBBAA99887766554433221100;
      force dut.staged_nonce_prefix = 64'h0123_4567_89AB_CDEF;
      force dut.active_nonce_prefix = 64'hFEDC_BA98_7654_3210;
      force dut.staged_valid = 1'b1;
      force dut.active_valid = 1'b1;
      force dut.last_accepted_sequence = 64'h0102_0304_0506_0708;
      force dut.retained_valid = 1'b1;
      force dut.retained_data = 128'hDEAD_BEEF_0011_2233_4455_6677_8899_AABB;
      force dut.auth_result_valid = 1'b1;
      force dut.auth_result_session_id = 32'h5566_7788;
      force dut.auth_result_sequence = 64'h0102_0304_0506_0708;
      force dut.auth_result_plaintext = 192'h00112233445566778899AABBCCDDEEFF0011223344556677;
      force dut.last_ack_valid = 1'b1;
      force dut.candidate_frame = {512{1'b1}};
      force dut.candidate_session_id = 32'h1122_3344;
      force dut.candidate_sequence = 64'h0102_0304_0506_0708;
      force dut.decrypt_key = {128{1'b1}};
      force dut.decrypt_nonce = {128{1'b1}};
      force dut.decrypt_ad = {192{1'b1}};
      force dut.decrypt_ciphertext = {192{1'b1}};
      force dut.decrypt_tag = {128{1'b1}};
      force dut.diagnostic_summary = 32'hFFFF_FFFF;
      force dut.diag_bad_tag_count = 16'hFFFF;
      force dut.diag_frame_error_count = 16'hFFFF;
      force dut.diag_fault_count = 16'hFFFF;
      force dut.u_decrypt.plaintext_o = {192{1'b1}};
      force dut.u_decrypt.x0 = {64{1'b1}};
      force dut.u_decrypt.x1 = {64{1'b1}};
      force dut.u_decrypt.x2 = {64{1'b1}};
      force dut.u_decrypt.x3 = {64{1'b1}};
      force dut.u_decrypt.x4 = {64{1'b1}};
      force dut.u_decrypt.k0 = {64{1'b1}};
      force dut.u_decrypt.k1 = {64{1'b1}};
      force dut.u_decrypt.ad_reg = {192{1'b1}};
      force dut.u_decrypt.ct_reg = {192{1'b1}};
      force dut.u_decrypt.tag_reg = {128{1'b1}};

      #1;
      release dut.session_state;
      release dut.core_state;
      release dut.operation_state;
      release dut.self_test_pass;
      release dut.fault_latched;
      release dut.staged_session_id;
      release dut.active_session_id;
      release dut.staged_key;
      release dut.active_key;
      release dut.staged_nonce_prefix;
      release dut.active_nonce_prefix;
      release dut.staged_valid;
      release dut.active_valid;
      release dut.last_accepted_sequence;
      release dut.retained_valid;
      release dut.retained_data;
      release dut.auth_result_valid;
      release dut.auth_result_session_id;
      release dut.auth_result_sequence;
      release dut.auth_result_plaintext;
      release dut.last_ack_valid;
      release dut.candidate_frame;
      release dut.candidate_session_id;
      release dut.candidate_sequence;
      release dut.decrypt_key;
      release dut.decrypt_nonce;
      release dut.decrypt_ad;
      release dut.decrypt_ciphertext;
      release dut.decrypt_tag;
      release dut.diagnostic_summary;
      release dut.diag_bad_tag_count;
      release dut.diag_frame_error_count;
      release dut.diag_fault_count;
      release dut.u_decrypt.plaintext_o;
      release dut.u_decrypt.x0;
      release dut.u_decrypt.x1;
      release dut.u_decrypt.x2;
      release dut.u_decrypt.x3;
      release dut.u_decrypt.x4;
      release dut.u_decrypt.k0;
      release dut.u_decrypt.k1;
      release dut.u_decrypt.ad_reg;
      release dut.u_decrypt.ct_reg;
      release dut.u_decrypt.tag_reg;

      #1 rst_ni = 1'b0;
      #1;
      if (session_state_o !== SESSION_SELF_TEST_REQUIRED ||
          operation_state_o !== OP_IDLE || dut.core_state !== 3'd0 ||
          dut.self_test_pass !== 1'b0 || fault_o !== 1'b0 ||
          rx_accept_enable_o !== 1'b0 || result_pending_o !== 1'b0 ||
          retained_result_pending_o !== 1'b0 ||
          authenticated_result_pending_o !== 1'b0)
        $fatal(1, "reset control state mismatch case %0d", case_id);
      if (dut.staged_session_id !== 0 || dut.active_session_id !== 0 ||
          dut.staged_key !== 0 || dut.active_key !== 0 ||
          dut.staged_nonce_prefix !== 0 || dut.active_nonce_prefix !== 0 ||
          dut.staged_valid !== 0 || dut.active_valid !== 0 ||
          dut.last_accepted_sequence !== 0 || dut.candidate_frame !== 0 ||
          dut.auth_result_valid !== 0 || dut.auth_result_plaintext !== 0 ||
          dut.retained_valid !== 0 || dut.retained_data !== 0)
        $fatal(1, "reset did not clear session/quarantine case %0d", case_id);
      if (dut.decrypt_key !== 0 || dut.decrypt_nonce !== 0 ||
          dut.decrypt_ad !== 0 || dut.decrypt_ciphertext !== 0 ||
          dut.decrypt_tag !== 0 || dut.u_decrypt.plaintext_o !== 0 ||
          dut.u_decrypt.x0 !== 0 || dut.u_decrypt.x1 !== 0 ||
          dut.u_decrypt.x2 !== 0 || dut.u_decrypt.x3 !== 0 ||
          dut.u_decrypt.x4 !== 0 || dut.u_decrypt.k0 !== 0 ||
          dut.u_decrypt.k1 !== 0 || dut.u_decrypt.ad_reg !== 0 ||
          dut.u_decrypt.ct_reg !== 0 || dut.u_decrypt.tag_reg !== 0)
        $fatal(1, "reset did not clear Ascon state case %0d", case_id);
      if (dut.diagnostic_summary !== 0 || dut.diag_bad_tag_count !== 0 ||
          dut.diag_frame_error_count !== 0 || dut.diag_fault_count !== 0)
        $fatal(1, "reset did not clear diagnostics case %0d", case_id);

      rst_ni = 1'b1;
      repeat (2) @(posedge clk_i);
      $display("PASS reset_from_critical_state_%0d", case_id);
    end
  endtask

  initial begin
    repeat (2) @(posedge clk_i);
    rst_ni = 1'b1;
    repeat (2) @(posedge clk_i);
    poison_and_reset(1);
    poison_and_reset(2);
    poison_and_reset(3);
    poison_and_reset(4);
    poison_and_reset(5);
    poison_and_reset(6);
    poison_and_reset(7);
    poison_and_reset(8);
    $display("PASS reset_all_critical_states_zeroize_secrets");
    $finish;
  end
endmodule
