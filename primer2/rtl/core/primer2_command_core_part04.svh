        end else if (core_state == CORE_SELFTEST_DECRYPT && decrypt_done) begin
          decrypt_abort <= 1'b1;
          decrypt_key <= '0;
          decrypt_nonce <= '0;
          decrypt_ad <= '0;
          decrypt_ciphertext <= '0;
          decrypt_tag <= '0;
          if (decrypt_tag_valid && decrypt_plaintext == 192'd0) begin
            finish_selftest_success();
          end else begin
            diag_selftest_count <= diag_selftest_count + 1'b1;
            diagnostic_summary <= diagnostic_summary | DIAG_SELF_TEST;
            fault_latched <= 1'b1;
            session_state <= SESSION_FAULT_LOCKED;
            operation_state <= OP_IDLE;
            complete_retained(TXN_FAILED, ERR_SELF_TEST_FAILED, 16'd0, '0);
            core_state <= CORE_IDLE;
          end
        end else if (frame_valid_i && core_state == CORE_IDLE) begin
          if (!rx_accept_enable_o) begin
            diag_frame_error_count <= diag_frame_error_count + 1'b1;
            diagnostic_summary <= diagnostic_summary | DIAG_FRAME_ERROR;
            last_error <= auth_result_valid ? ERR_RESULT_PENDING_DROP : ERR_BAD_STATE;
          end else begin
            candidate_frame <= frame_body_i;
            candidate_session_id <= frame_session_id;
            candidate_sequence <= frame_sequence;
            operation_state <= OP_LOAD_INPUT;
            core_state <= CORE_VALIDATE;
          end
        end

        if (transport_error_valid_i && response_ready_i) begin
          if (transport_error_code_i == ERR_BAD_CRC) begin
            diag_crc_count <= diag_crc_count + 1'b1;
            diagnostic_summary <= diagnostic_summary | DIAG_CRC;
          end else begin
            diag_transport_count <= diag_transport_count + 1'b1;
            diagnostic_summary <= diagnostic_summary | DIAG_TRANSPORT;
          end
          emit_error(transport_error_command_i, transport_error_txid_i,
                     transport_error_code_i, 16'd0);
        end else if (request_valid_i && response_ready_i) begin
          if (is_retained_side_effect(request_command_i) && retained_valid) begin
            if (request_txid_i == retained_txid &&
                request_command_i == retained_command &&
                request_fingerprint_i == retained_fingerprint) begin
              emit_empty_success(request_command_i, request_txid_i);
            end else if (request_txid_i == retained_txid) begin
              diag_transaction_conflict_count <= diag_transaction_conflict_count + 1'b1;
              diagnostic_summary <= diagnostic_summary | DIAG_TRANSACTION_CONFLICT;
              emit_error(request_command_i, request_txid_i,
                         ERR_TRANSACTION_CONFLICT, 16'd0);
            end else if (request_command_i != CMD_ZEROIZE) begin
              emit_error(request_command_i, request_txid_i,
                         ERR_RESULT_PENDING, retained_txid);
            end else begin
              begin_retained(request_txid_i, request_command_i, request_fingerprint_i);
              emit_empty_success(request_command_i, request_txid_i);
              start_zeroize(1'b1, 1'b0, 1'b0);
            end
          end else if ((core_state != CORE_IDLE || frame_valid_i) &&
                       request_command_i != CMD_GET_STATUS &&
                       request_command_i != CMD_GET_TXN_RESULT &&
                       request_command_i != CMD_ABORT_SESSION &&
                       request_command_i != CMD_ZEROIZE) begin
            emit_error(request_command_i, request_txid_i, ERR_BUSY, active_transaction_id);
          end else begin
            case (request_command_i)
              CMD_GET_INFO: begin
                if (request_payload_length_i != 0) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_LENGTH, 16'd0);
                end else begin
                  rsp = '0;
                  rsp[7:0] = TARGET_PRIMER2;
                  rsp[15:8] = PROTOCOL_VERSION;
                  rsp[23:16] = CAPABILITIES[31:24];
                  rsp[31:24] = CAPABILITIES[23:16];
                  rsp[39:32] = CAPABILITIES[15:8];
                  rsp[47:40] = CAPABILITIES[7:0];
                  rsp[55:48] = BUILD_ID[31:24];
                  rsp[63:56] = BUILD_ID[23:16];
                  rsp[71:64] = BUILD_ID[15:8];
                  rsp[79:72] = BUILD_ID[7:0];
                  emit_response(request_command_i, request_txid_i,
                                FLAG_RESPONSE, 16'd12, rsp);
                end
              end

              CMD_GET_STATUS: begin
                if (request_payload_length_i != 0)
                  emit_error(request_command_i, request_txid_i, ERR_BAD_LENGTH, 16'd0);
                else
                  emit_status(request_command_i, request_txid_i);
              end

              CMD_RUN_SELF_TEST: begin
                if (request_payload_length_i != 4 ||
                    pbyte(request_payload_i,2) != 0 || pbyte(request_payload_i,3) != 0) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_LENGTH, 16'd0);
                end else if ({pbyte(request_payload_i,0), pbyte(request_payload_i,1)} == 0 ||
                             (({pbyte(request_payload_i,0), pbyte(request_payload_i,1)} &
                               ~SELFTEST_SUPPORTED_MASK) != 0)) begin
                  emit_error(request_command_i, request_txid_i, ERR_NOT_SUPPORTED,
                             {pbyte(request_payload_i,0), pbyte(request_payload_i,1)});
                end else if (session_state != SESSION_SELF_TEST_REQUIRED &&
                             session_state != SESSION_READY_NO_SESSION) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_STATE, 16'd0);
                end else begin
                  selftest_requested_mask <= {pbyte(request_payload_i,0), pbyte(request_payload_i,1)};
                  begin_retained(request_txid_i, request_command_i, request_fingerprint_i);
                  session_state <= SESSION_SELF_TEST_RUNNING;
                  operation_state <= OP_EXECUTING;
                  emit_empty_success(request_command_i, request_txid_i);
                  // Every accepted self-test mask executes the byte-exact Ascon
                  // decrypt KAT. This keeps the boot gate cryptographically meaningful
                  // even when the caller selected only protocol/UART/session checks.
                  decrypt_key <= '0;
                  decrypt_nonce <= '0;
                  decrypt_ad <= '0;
                  decrypt_ciphertext <= ASCON_KAT_CT;
                  decrypt_tag <= ASCON_KAT_TAG;
                  decrypt_start <= 1'b1;
                  core_state <= CORE_SELFTEST_DECRYPT;
                end
              end

              CMD_GET_TXN_RESULT: begin
                if (request_payload_length_i != 2)
                  emit_error(request_command_i, request_txid_i, ERR_BAD_LENGTH, 16'd0);
                else
                  emit_txn_result(request_command_i, request_txid_i,
                                  {pbyte(request_payload_i,0), pbyte(request_payload_i,1)});
              end

              CMD_RETIRE_TXN_RESULT: begin
                if (request_payload_length_i != 2) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_LENGTH, 16'd0);
                end else begin
                  if (retained_valid &&
                      {pbyte(request_payload_i,0), pbyte(request_payload_i,1)} == retained_txid) begin
                    retained_valid <= 1'b0;
                    retained_state <= TXN_NONE;
                  end
                  emit_empty_success(request_command_i, request_txid_i);
                end
              end

              CMD_ZEROIZE: begin
                if (request_payload_length_i != 4 ||
                    pbyte(request_payload_i,1) != 0 ||
                    pbyte(request_payload_i,2) != 0 ||
                    pbyte(request_payload_i,3) != 0) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_LENGTH, 16'd0);
                end else if (pbyte(request_payload_i,0) != ZEROIZE_ALL) begin
                  emit_error(request_command_i, request_txid_i, ERR_NOT_SUPPORTED,
                             {8'd0, pbyte(request_payload_i,0)});
                end else begin
                  begin_retained(request_txid_i, request_command_i, request_fingerprint_i);
                  emit_empty_success(request_command_i, request_txid_i);
                  start_zeroize(1'b1, 1'b0, 1'b0);
                end
              end

              CMD_STAGE_SESSION: begin
                if (request_payload_length_i != 28) begin
                  emit_error(request_command_i, request_txid_i, ERR_BAD_LENGTH, 16'd0);
                end else if (!self_test_pass ||
                             (session_state != SESSION_READY_NO_SESSION &&
                              session_state != SESSION_STAGED)) begin
