      input logic [7:0] flags,
      input logic [15:0] length,
      input logic [527:0] data
  );
    begin
      response_command_o <= command;
      response_txid_o <= txid;
      response_flags_o <= flags;
      response_payload_length_o <= length;
      response_payload_o <= data;
      response_commit_o <= 1'b1;
    end
  endtask

  task automatic emit_empty_success(input logic [7:0] command, input logic [15:0] txid);
    begin
      emit_response(command, txid, FLAG_RESPONSE, 16'd0, '0);
    end
  endtask

  task automatic emit_error(
      input logic [7:0] command,
      input logic [15:0] txid,
      input logic [15:0] code,
      input logic [15:0] detail
  );
    begin
      error_rsp = '0;
      error_rsp[7:0] = code[15:8];
      error_rsp[15:8] = code[7:0];
      error_rsp[23:16] = {4'h0, session_state};
      error_rsp[31:24] = {5'h0, operation_state};
      error_rsp[39:32] = detail[15:8];
      error_rsp[47:40] = detail[7:0];
      emit_response(command, txid, FLAG_RESPONSE | FLAG_ERROR, 16'd6, error_rsp);
      last_error <= code;
    end
  endtask

  task automatic begin_retained(
      input logic [15:0] txid,
      input logic [7:0] command,
      input logic [31:0] fingerprint
  );
    begin
      retained_valid <= 1'b1;
      retained_txid <= txid;
      retained_command <= command;
      retained_fingerprint <= fingerprint;
      retained_state <= TXN_RUNNING;
      retained_code <= ERR_OK;
      retained_data_length <= 16'd0;
      retained_data <= '0;
      active_transaction_id <= txid;
    end
  endtask

  task automatic complete_retained(
      input transaction_state_e final_state,
      input logic [15:0] code,
      input logic [15:0] length,
      input logic [127:0] data
  );
    begin
      retained_state <= final_state;
      retained_code <= code;
      retained_data_length <= length;
      retained_data <= data;
      active_transaction_id <= 16'd0;
      if (code != ERR_OK)
        last_error <= code;
    end
  endtask

  task automatic clear_session_and_result;
    begin
      staged_session_id <= 32'd0;
      active_session_id <= 32'd0;
      staged_key <= '0;
      active_key <= '0;
      staged_nonce_prefix <= '0;
      active_nonce_prefix <= '0;
      staged_valid <= 1'b0;
      active_valid <= 1'b0;
      last_accepted_sequence <= 64'd0;
      candidate_frame <= '0;
      candidate_session_id <= 32'd0;
      candidate_sequence <= 64'd0;
      auth_result_valid <= 1'b0;
      auth_result_session_id <= 32'd0;
      auth_result_sequence <= 64'd0;
      auth_result_plaintext <= '0;
      auth_result_status <= 16'd0;
      consecutive_bad_tags <= 8'd0;
      last_ack_valid <= 1'b0;
      last_ack_session_id <= 32'd0;
      last_ack_sequence <= 64'd0;
    end
  endtask

  task automatic start_zeroize(
      input logic from_command,
      input logic due_to_fault,
      input logic requires_selftest
  );
    begin
      decrypt_abort <= 1'b1;
      decrypt_key <= '0;
      decrypt_nonce <= '0;
      decrypt_ad <= '0;
      decrypt_ciphertext <= '0;
      decrypt_tag <= '0;
      clear_session_and_result();
      zeroize_counter <= 6'd0;
      zeroize_from_command <= from_command;
      zeroize_due_to_fault <= due_to_fault;
      zeroize_requires_selftest <= requires_selftest;
      session_state <= SESSION_ZEROIZE_BUSY;
      operation_state <= OP_IDLE;
      core_state <= CORE_ZEROIZE;
    end
  endtask

  task automatic emit_status(input logic [7:0] command, input logic [15:0] txid);
    begin
      rsp = '0;
      rsp[7:0] = {4'h0, session_state};
      rsp[15:8] = {5'h0, operation_state};
      rsp[23:16] = (mailbox_pending_i ? PENDING_RESPONSE_MAILBOX : 8'd0) |
                       (retained_valid ? PENDING_SIDE_EFFECT_RESULT : 8'd0) |
                       (auth_result_valid ? PENDING_AUTHENTICATED_RESULT : 8'd0);
      rsp[31:24] = (self_test_pass ? SECURE_SELF_TEST_PASS : 8'd0) |
                       (staged_valid ? SECURE_SESSION_STAGED : 8'd0) |
                       (secure_enable_i ? SECURE_ENABLE : 8'd0) |
                       ((session_state == SESSION_ZEROIZE_BUSY) ? SECURE_ZEROIZE_BUSY : 8'd0) |
                       (fault_o ? SECURE_FAULT_LOCKED : 8'd0);
      if (active_valid) begin
        rsp[39:32] = active_session_id[31:24];
        rsp[47:40] = active_session_id[23:16];
        rsp[55:48] = active_session_id[15:8];
        rsp[63:56] = active_session_id[7:0];
      end else if (staged_valid) begin
        rsp[39:32] = staged_session_id[31:24];
        rsp[47:40] = staged_session_id[23:16];
        rsp[55:48] = staged_session_id[15:8];
        rsp[63:56] = staged_session_id[7:0];
      end
      rsp[71:64] = last_error[15:8];
      rsp[79:72] = last_error[7:0];
      rsp[87:80] = active_transaction_id[15:8];
      rsp[95:88] = active_transaction_id[7:0];
      rsp[103:96] = diagnostic_summary[31:24];
      rsp[111:104] = diagnostic_summary[23:16];
      rsp[119:112] = diagnostic_summary[15:8];
      rsp[127:120] = diagnostic_summary[7:0];
      emit_response(command, txid, FLAG_RESPONSE, 16'd16, rsp);
    end
  endtask

  task automatic emit_txn_result(
      input logic [7:0] command,
      input logic [15:0] response_txid,
      input logic [15:0] queried_txid
  );
    begin
      if (!retained_valid || queried_txid != retained_txid) begin
        emit_error(command, response_txid, ERR_RESULT_NOT_READY, 16'd0);
      end else begin
        result_rsp = '0;
        result_rsp[7:0] = retained_txid[15:8];
