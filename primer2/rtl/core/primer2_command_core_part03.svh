        heartbeat_o <= ~heartbeat_o;
      end else begin
        heartbeat_counter <= heartbeat_counter + 1'b1;
      end

      if (session_state == SESSION_COMMITTED_BLOCKED && secure_enable_i &&
          !fatal_latched_i && !fault_latched) begin
        session_state <= SESSION_ACTIVE;
      end

      if ((fatal_latched_i || !zeroize_ni ||
           (session_state == SESSION_ACTIVE && !secure_enable_i)) &&
          core_state != CORE_ZEROIZE && session_state != SESSION_FAULT_LOCKED) begin
        if (fatal_latched_i) begin
          fault_latched <= 1'b1;
          diag_fault_count <= diag_fault_count + 1'b1;
          diagnostic_summary <= diagnostic_summary | DIAG_HEARTBEAT_OR_FAULT;
          last_error <= ERR_FAULT_LOCKED;
        end
        retained_valid <= 1'b0;
        start_zeroize(1'b0, fatal_latched_i | fault_latched,
                      !zeroize_ni | (session_state == SESSION_ACTIVE && !secure_enable_i));
      end else if (core_state == CORE_ZEROIZE) begin
        if (zeroize_counter != 6'd24) begin
          zeroize_counter <= zeroize_counter + 1'b1;
        end else if (zeroize_ni) begin
          zeroize_counter <= 6'd0;
          if (zeroize_from_command) begin
            complete_retained(TXN_ZEROIZED, ERR_ZEROIZED, 16'd0, '0);
            session_state <= self_test_pass ? SESSION_READY_NO_SESSION : SESSION_SELF_TEST_REQUIRED;
          end else if (zeroize_due_to_fault || fault_latched || fatal_latched_i) begin
            session_state <= SESSION_FAULT_LOCKED;
          end else begin
            if (zeroize_requires_selftest)
              self_test_pass <= 1'b0;
            session_state <= zeroize_requires_selftest ?
                             SESSION_SELF_TEST_REQUIRED : SESSION_READY_NO_SESSION;
          end
          zeroize_from_command <= 1'b0;
          zeroize_due_to_fault <= 1'b0;
          zeroize_requires_selftest <= 1'b0;
          core_state <= CORE_IDLE;
        end
      end else begin
        if (frame_timeout_i) begin
          diag_frame_error_count <= diag_frame_error_count + 1'b1;
          diagnostic_summary <= diagnostic_summary | DIAG_FRAME_ERROR;
          last_error <= ERR_FRAME_TIMEOUT;
        end
        if (frame_framing_error_i) begin
          diag_frame_error_count <= diag_frame_error_count + 1'b1;
          diagnostic_summary <= diagnostic_summary | DIAG_FRAME_ERROR;
          last_error <= ERR_MALFORMED_FRAME;
        end
        if (frame_pending_drop_i) begin
          diag_result_pending_drop_count <= diag_result_pending_drop_count + 1'b1;
          diagnostic_summary <= diagnostic_summary | DIAG_RESULT_PENDING_DROP;
          last_error <= ERR_RESULT_PENDING_DROP;
        end
        if (frame_blocked_i) begin
          diag_frame_error_count <= diag_frame_error_count + 1'b1;
          diagnostic_summary <= diagnostic_summary | DIAG_FRAME_ERROR;
          last_error <= ERR_BAD_STATE;
        end

        if (core_state == CORE_VALIDATE) begin
          if (fbyte(candidate_frame,0) != PROTOCOL_VERSION ||
              fbyte(candidate_frame,1) != 8'h02 ||
              fbyte(candidate_frame,16) != 8'h00 ||
              fbyte(candidate_frame,17) != 8'h18 ||
              fbyte(candidate_frame,20) != 8'h00 ||
              fbyte(candidate_frame,21) != 8'h00 ||
              fbyte(candidate_frame,22) != 8'h00 ||
              fbyte(candidate_frame,23) != 8'h00) begin
            diag_frame_error_count <= diag_frame_error_count + 1'b1;
            diagnostic_summary <= diagnostic_summary | DIAG_FRAME_ERROR;
            last_error <= ERR_MALFORMED_FRAME;
            operation_state <= OP_IDLE;
            core_state <= CORE_IDLE;
          end else if (!active_valid || candidate_session_id != active_session_id) begin
            diagnostic_summary <= diagnostic_summary | DIAG_REPLAY_OR_STALE;
            diag_replay_stale_count <= diag_replay_stale_count + 1'b1;
            last_error <= ERR_BAD_SESSION;
            operation_state <= OP_IDLE;
            core_state <= CORE_IDLE;
          end else if (candidate_sequence == 64'd0) begin
            diagnostic_summary <= diagnostic_summary | DIAG_REPLAY_OR_STALE;
            diag_replay_stale_count <= diag_replay_stale_count + 1'b1;
            last_error <= ERR_STALE_SEQUENCE;
            operation_state <= OP_IDLE;
            core_state <= CORE_IDLE;
          end else if (candidate_sequence == last_accepted_sequence &&
                       last_accepted_sequence != 64'd0) begin
            diagnostic_summary <= diagnostic_summary | DIAG_REPLAY_OR_STALE;
            diag_replay_stale_count <= diag_replay_stale_count + 1'b1;
            last_error <= ERR_REPLAY;
            operation_state <= OP_IDLE;
            core_state <= CORE_IDLE;
          end else if (candidate_sequence < last_accepted_sequence) begin
            diagnostic_summary <= diagnostic_summary | DIAG_REPLAY_OR_STALE;
            diag_replay_stale_count <= diag_replay_stale_count + 1'b1;
            last_error <= ERR_STALE_SEQUENCE;
            operation_state <= OP_IDLE;
            core_state <= CORE_IDLE;
          end else if ((last_accepted_sequence == 64'd0 &&
                        candidate_sequence != 64'd1) ||
                       (last_accepted_sequence != 64'd0 &&
                        candidate_sequence != last_accepted_sequence + 1'b1)) begin
            // The locked receive contract is contiguous: the first accepted
            // sequence is one and every later frame advances exactly once.
            // A forward gap is fail-closed because the missing frame outcome
            // cannot be reconstructed by Primer #2.
            diagnostic_summary <= diagnostic_summary | DIAG_REPLAY_OR_STALE;
            diag_replay_stale_count <= diag_replay_stale_count + 1'b1;
            last_error <= ERR_STALE_SEQUENCE;
            operation_state <= OP_IDLE;
            core_state <= CORE_IDLE;
          end else begin
            decrypt_key <= active_key;
            decrypt_nonce[63:0] <= active_nonce_prefix;
            decrypt_nonce[127:64] <= candidate_frame[8*8 +: 64];
            decrypt_ad <= candidate_frame[0 +: 192];
            decrypt_ciphertext <= candidate_frame[8*24 +: 192];
            decrypt_tag <= candidate_frame[8*48 +: 128];
            decrypt_start <= 1'b1;
            operation_state <= OP_EXECUTING;
            core_state <= CORE_DECRYPT;
          end
        end else if (core_state == CORE_DECRYPT && decrypt_done) begin
          // Copy the authenticated result first, then scrub the complete decrypt
          // datapath on the following cycle.  abort_i has priority inside the
          // Ascon core and clears key, nonce-derived state, AD, ciphertext,
          // received tag, permutation state and quarantine plaintext.
          decrypt_abort <= 1'b1;
          operation_state <= OP_IDLE;
          core_state <= CORE_IDLE;
          candidate_frame <= '0;
          candidate_session_id <= 32'd0;
          candidate_sequence <= 64'd0;
          decrypt_key <= '0;
          decrypt_nonce <= '0;
          decrypt_ad <= '0;
          decrypt_ciphertext <= '0;
          decrypt_tag <= '0;
          if (decrypt_tag_valid) begin
            auth_result_valid <= 1'b1;
            auth_result_session_id <= candidate_session_id;
            auth_result_sequence <= candidate_sequence;
            auth_result_plaintext <= decrypt_plaintext;
            auth_result_status <= ERR_OK;
            last_accepted_sequence <= candidate_sequence;
            consecutive_bad_tags <= 8'd0;
            last_error <= ERR_OK;
          end else begin
            diag_bad_tag_count <= diag_bad_tag_count + 1'b1;
            diagnostic_summary <= diagnostic_summary | DIAG_BAD_TAG;
            last_error <= ERR_BAD_TAG;
            if (consecutive_bad_tags + 1 >= BAD_TAG_THRESHOLD) begin
              consecutive_bad_tags <= BAD_TAG_THRESHOLD;
              fault_latched <= 1'b1;
              diag_fault_count <= diag_fault_count + 1'b1;
              diagnostic_summary <= diagnostic_summary |
                                    DIAG_BAD_TAG | DIAG_HEARTBEAT_OR_FAULT;
              last_error <= ERR_AUTH_THRESHOLD;
              retained_valid <= 1'b0;
              start_zeroize(1'b0, 1'b1, 1'b0);
            end else begin
              consecutive_bad_tags <= consecutive_bad_tags + 1'b1;
            end
          end
