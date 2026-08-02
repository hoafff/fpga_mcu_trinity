                  if (request_mask & DIAG_SELF_TEST) begin
                    diag_selftest_count <= 16'd0;
                  end
                  diagnostic_summary <= diagnostic_summary & ~request_mask;
                  if (request_mask == DIAG_ALL)
                    last_error <= ERR_OK;
                  emit_empty_success(request_command_i, request_txid_i);
                end
              end
              default: begin
                diag_bad_command_count <= diag_bad_command_count + 1'b1;
                diagnostic_summary <= diagnostic_summary | DIAG_BAD_COMMAND;
                emit_error(request_command_i, request_txid_i, ERR_BAD_COMMAND, 16'd0);
              end
            endcase
          end
        end
      end
    end
  end
endmodule
