        result_rsp[15:8] = retained_txid[7:0];
        result_rsp[23:16] = {5'h0, retained_state};
        result_rsp[31:24] = retained_command;
        result_rsp[39:32] = retained_code[15:8];
        result_rsp[47:40] = retained_code[7:0];
        result_rsp[55:48] = retained_data_length[15:8];
        result_rsp[63:56] = retained_data_length[7:0];
        for (ri = 0; ri < 16; ri = ri + 1)
          if (ri < retained_data_length)
            result_rsp[8*(10+ri) +: 8] = retained_data[8*ri +: 8];
        emit_response(command, response_txid, FLAG_RESPONSE,
                      16'd10 + retained_data_length, result_rsp);
      end
    end
  endtask

  task automatic finish_selftest_success;
    begin
      self_test_pass <= 1'b1;
      session_state <= SESSION_READY_NO_SESSION;
      operation_state <= OP_IDLE;
      retained_data <= '0;
      retained_data[7:0] <= selftest_requested_mask[15:8];
      retained_data[15:8] <= selftest_requested_mask[7:0];
      retained_data_length <= 16'd2;
      retained_state <= TXN_SUCCEEDED;
      retained_code <= ERR_OK;
      active_transaction_id <= 16'd0;
      core_state <= CORE_IDLE;
    end
  endtask

  ascon_aead128_decrypt u_decrypt (
      .clk_i(clk_i),
      .rst_ni(rst_ni),
      .start_i(decrypt_start),
      .abort_i(decrypt_abort),
      .key_i(decrypt_key),
      .nonce_i(decrypt_nonce),
      .ad_i(decrypt_ad),
      .ciphertext_i(decrypt_ciphertext),
      .tag_i(decrypt_tag),
      .busy_o(decrypt_busy),
      .done_o(decrypt_done),
      .tag_valid_o(decrypt_tag_valid),
      .plaintext_o(decrypt_plaintext)
  );

  always_comb begin
    frame_session_id = {fbyte(frame_body_i,4), fbyte(frame_body_i,5),
                        fbyte(frame_body_i,6), fbyte(frame_body_i,7)};
    frame_sequence = {fbyte(frame_body_i,8), fbyte(frame_body_i,9),
                      fbyte(frame_body_i,10), fbyte(frame_body_i,11),
                      fbyte(frame_body_i,12), fbyte(frame_body_i,13),
                      fbyte(frame_body_i,14), fbyte(frame_body_i,15)};

    request_session_id = {pbyte(request_payload_i,0), pbyte(request_payload_i,1),
                          pbyte(request_payload_i,2), pbyte(request_payload_i,3)};
    request_sequence = {pbyte(request_payload_i,4), pbyte(request_payload_i,5),
                        pbyte(request_payload_i,6), pbyte(request_payload_i,7),
                        pbyte(request_payload_i,8), pbyte(request_payload_i,9),
                        pbyte(request_payload_i,10), pbyte(request_payload_i,11)};
    request_mask = {pbyte(request_payload_i,0), pbyte(request_payload_i,1),
                    pbyte(request_payload_i,2), pbyte(request_payload_i,3)};

    rx_accept_enable_o = (session_state == SESSION_ACTIVE) && active_valid &&
                         secure_enable_i && !fault_o && !auth_result_valid &&
                         (core_state != CORE_ZEROIZE);
    result_pending_o = auth_result_valid;
    retained_result_pending_o = retained_valid;
    authenticated_result_pending_o = auth_result_valid;
    irq_event_pending_o = retained_valid | auth_result_valid;
    fault_o = fault_latched | (session_state == SESSION_FAULT_LOCKED);
    session_state_o = session_state;
    operation_state_o = operation_state;

    if (auth_result_valid)
      rx_state_o = RX_RESULT_PENDING;
    else if (core_state == CORE_DECRYPT || core_state == CORE_SELFTEST_DECRYPT)
      rx_state_o = RX_VERIFY_TAG;
    else if (core_state == CORE_VALIDATE)
      rx_state_o = RX_VALIDATE;
    else
      rx_state_o = frame_rx_state_i;
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      core_state <= CORE_IDLE;
      session_state <= SESSION_SELF_TEST_REQUIRED;
      operation_state <= OP_IDLE;
      self_test_pass <= 1'b0;
      fault_latched <= 1'b0;
      last_error <= ERR_OK;
      diagnostic_summary <= 32'd0;
      active_transaction_id <= 16'd0;

      staged_session_id <= 32'd0;
      active_session_id <= 32'd0;
      staged_key <= '0;
      active_key <= '0;
      staged_nonce_prefix <= '0;
      active_nonce_prefix <= '0;
      staged_valid <= 1'b0;
      active_valid <= 1'b0;
      last_accepted_sequence <= 64'd0;

      retained_valid <= 1'b0;
      retained_txid <= 16'd0;
      retained_command <= 8'd0;
      retained_fingerprint <= 32'd0;
      retained_state <= TXN_NONE;
      retained_code <= ERR_OK;
      retained_data_length <= 16'd0;
      retained_data <= '0;

      auth_result_valid <= 1'b0;
      auth_result_session_id <= 32'd0;
      auth_result_sequence <= 64'd0;
      auth_result_plaintext <= '0;
      auth_result_status <= ERR_OK;
      last_ack_valid <= 1'b0;
      last_ack_session_id <= 32'd0;
      last_ack_sequence <= 64'd0;

      consecutive_bad_tags <= 8'd0;
      diag_transport_count <= 16'd0;
      diag_crc_count <= 16'd0;
      diag_bad_command_count <= 16'd0;
      diag_transaction_conflict_count <= 16'd0;
      diag_bad_tag_count <= 16'd0;
      diag_replay_stale_count <= 16'd0;
      diag_frame_error_count <= 16'd0;
      diag_result_pending_drop_count <= 16'd0;
      diag_fault_count <= 16'd0;
      diag_selftest_count <= 16'd0;

      heartbeat_counter <= '0;
      heartbeat_o <= 1'b0;
      zeroize_counter <= 6'd0;
      zeroize_from_command <= 1'b0;
      zeroize_due_to_fault <= 1'b0;
      zeroize_requires_selftest <= 1'b0;

      candidate_frame <= '0;
      candidate_session_id <= 32'd0;
      candidate_sequence <= 64'd0;

      decrypt_start <= 1'b0;
      decrypt_abort <= 1'b0;
      decrypt_key <= '0;
      decrypt_nonce <= '0;
      decrypt_ad <= '0;
      decrypt_ciphertext <= '0;
      decrypt_tag <= '0;
      selftest_requested_mask <= 16'd0;

      response_commit_o <= 1'b0;
      response_command_o <= 8'd0;
      response_flags_o <= 8'd0;
      response_txid_o <= 16'd0;
      response_payload_length_o <= 16'd0;
      response_payload_o <= '0;
    end else begin
      response_commit_o <= 1'b0;
      decrypt_start <= 1'b0;
      decrypt_abort <= 1'b0;

      if (heartbeat_counter == HEARTBEAT_CYCLES-1) begin
        heartbeat_counter <= '0;
