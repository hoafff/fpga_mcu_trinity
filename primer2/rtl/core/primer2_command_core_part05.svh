                  emit_error(request_command_i, request_txid_i, ERR_BAD_STATE, 16'd0);
                end else if (staged_valid && staged_session_id == request_session_id) begin
                  if (staged_key == request_payload_i[8*4 +: 128] &&
                      staged_nonce_prefix == request_payload_i[8*20 +: 64])
                    emit_empty_success(request_command_i, request_txid_i);
                  else
                    emit_error(request_command_i, request_txid_i,
                               ERR_SESSION_ID_COLLISION, 16'd0);
                end else if (active_valid && active_session_id == request_session_id) begin
                  emit_error(request_command_i, request_txid_i,
                             ERR_SESSION_ID_COLLISION, 16'd0);
                end else begin
                  staged_session_id <= request_session_id;
                  staged_key <= request_payload_i[8*4 +: 128];
                  staged_nonce_prefix <= request_payload_i[8*20 +: 64];
                  staged_valid <= 1'b1;
                  session_state <= SESSION_STAGED;
                  emit_empty_success(request_command_i, request_txid_i);
                end
              end

              CMD_COMMIT_SESSION: begin
                if (request_payload_length_i != 4) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_LENGTH, 16'd0);
                end else if (secure_enable_i) begin
                  emit_error(request_command_i, request_txid_i, ERR_COMMIT_REJECTED, 16'd0);
                end else if (!staged_valid || session_state != SESSION_STAGED ||
                             request_session_id != staged_session_id) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_SESSION, 16'd0);
                end else begin
                  begin_retained(request_txid_i, request_command_i, request_fingerprint_i);
                  active_session_id <= staged_session_id;
                  active_key <= staged_key;
                  active_nonce_prefix <= staged_nonce_prefix;
                  active_valid <= 1'b1;
                  staged_session_id <= 32'd0;
                  staged_key <= '0;
                  staged_nonce_prefix <= '0;
                  staged_valid <= 1'b0;
                  last_accepted_sequence <= 64'd0;
                  auth_result_valid <= 1'b0;
                  session_state <= SESSION_COMMITTED_BLOCKED;
                  complete_retained(TXN_SUCCEEDED, ERR_OK, 16'd0, '0);
                  emit_empty_success(request_command_i, request_txid_i);
                end
              end

              CMD_ABORT_SESSION: begin
                if (request_payload_length_i != 4) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_LENGTH, 16'd0);
                end else if (request_session_id != 32'd0 &&
                             !(staged_valid && request_session_id == staged_session_id) &&
                             !(active_valid && request_session_id == active_session_id)) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_SESSION, 16'd0);
                end else begin
                  decrypt_abort <= 1'b1;
                  decrypt_key <= '0;
                  decrypt_nonce <= '0;
                  decrypt_ad <= '0;
                  decrypt_ciphertext <= '0;
                  decrypt_tag <= '0;
                  clear_session_and_result();
                  operation_state <= OP_IDLE;
                  session_state <= self_test_pass ?
                                   SESSION_READY_NO_SESSION : SESSION_SELF_TEST_REQUIRED;
                  core_state <= CORE_IDLE;
                  emit_empty_success(request_command_i, request_txid_i);
                end
              end

              CMD_GET_RX_STATUS: begin
                if (request_payload_length_i != 0) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_LENGTH, 16'd0);
                end else begin
                  rsp = '0;
                  rsp[7:0] = rx_state_o;
                  rsp[15:8] = auth_result_valid ? 8'd1 : 8'd0;
                  rsp[23:16] = rx_accept_enable_o ? 8'd1 : 8'd0;
                  rsp[31:24] = consecutive_bad_tags;
                  rsp[39:32] = active_session_id[31:24];
                  rsp[47:40] = active_session_id[23:16];
                  rsp[55:48] = active_session_id[15:8];
                  rsp[63:56] = active_session_id[7:0];
                  for (ri = 0; ri < 8; ri = ri + 1)
                    rsp[8*(8+ri) +: 8] = last_accepted_sequence[63-8*ri -: 8];
                  emit_response(request_command_i, request_txid_i,
                                FLAG_RESPONSE, 16'd16, rsp);
                end
              end

              CMD_READ_AUTH_RESULT: begin
                if (request_payload_length_i != 0) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_LENGTH, 16'd0);
                end else if (!auth_result_valid) begin
                  emit_error(request_command_i, request_txid_i, ERR_RESULT_NOT_READY, 16'd0);
                end else begin
                  rsp = '0;
                  rsp[7:0] = auth_result_session_id[31:24];
                  rsp[15:8] = auth_result_session_id[23:16];
                  rsp[23:16] = auth_result_session_id[15:8];
                  rsp[31:24] = auth_result_session_id[7:0];
                  for (ri = 0; ri < 8; ri = ri + 1)
                    rsp[8*(4+ri) +: 8] = auth_result_sequence[63-8*ri -: 8];
                  rsp[8*12 +: 192] = auth_result_plaintext;
                  rsp[8*36 +: 8] = auth_result_status[15:8];
                  rsp[8*37 +: 8] = auth_result_status[7:0];
                  emit_response(request_command_i, request_txid_i,
                                FLAG_RESPONSE, 16'd38, rsp);
                end
              end

              CMD_ACK_AUTH_RESULT: begin
                if (request_payload_length_i != 12) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_LENGTH, 16'd0);
                end else if (auth_result_valid) begin
                  if (request_session_id != auth_result_session_id ||
                      request_sequence != auth_result_sequence) begin
                    emit_error(request_command_i, request_txid_i, ERR_BAD_SESSION, 16'd0);
                  end else begin
                    last_ack_valid <= 1'b1;
                    last_ack_session_id <= auth_result_session_id;
                    last_ack_sequence <= auth_result_sequence;
                    auth_result_valid <= 1'b0;
                    auth_result_session_id <= 32'd0;
                    auth_result_sequence <= 64'd0;
                    auth_result_plaintext <= '0;
                    auth_result_status <= ERR_OK;
                    emit_empty_success(request_command_i, request_txid_i);
                  end
                end else if (last_ack_valid &&
                             request_session_id == last_ack_session_id &&
                             request_sequence == last_ack_sequence) begin
                  emit_empty_success(request_command_i, request_txid_i);
                end else begin
                  emit_error(request_command_i, request_txid_i,
                             ERR_RESULT_NOT_READY, 16'd0);
                end
              end

              CMD_CLEAR_DIAGNOSTIC_COUNTERS: begin
                if (request_payload_length_i != 4) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_LENGTH, 16'd0);
                end else begin
                  if (request_mask & DIAG_TRANSPORT) begin
                    diag_transport_count <= 16'd0;
                  end
                  if (request_mask & DIAG_CRC) begin
                    diag_crc_count <= 16'd0;
                  end
                  if (request_mask & DIAG_BAD_COMMAND) begin
                    diag_bad_command_count <= 16'd0;
                  end
                  if (request_mask & DIAG_TRANSACTION_CONFLICT) begin
                    diag_transaction_conflict_count <= 16'd0;
                  end
                  if (request_mask & DIAG_BAD_TAG) begin
                    diag_bad_tag_count <= 16'd0;
                  end
                  if (request_mask & DIAG_REPLAY_OR_STALE) begin
                    diag_replay_stale_count <= 16'd0;
                  end
                  if (request_mask & DIAG_FRAME_ERROR) begin
                    diag_frame_error_count <= 16'd0;
                  end
                  if (request_mask & DIAG_RESULT_PENDING_DROP) begin
                    diag_result_pending_drop_count <= 16'd0;
                  end
                  if (request_mask & DIAG_HEARTBEAT_OR_FAULT) begin
                    diag_fault_count <= 16'd0;
                  end
