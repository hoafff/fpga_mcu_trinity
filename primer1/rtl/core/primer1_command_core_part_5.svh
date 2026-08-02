end
end
C_READ_PRIME: begin
core_state<=C_READ_CHUNK;
end
C_READ_CHUNK: begin
// Register the canonical DPB output before the variable-index response write.
poly_read_sample<=poly_read_data;
core_state<=C_READ_RESP;
end
C_READ_RESP: begin
if (read_response_emit_pending) begin
emit_response(response_command_o,response_txid_o,FLAG_RESPONSE,16'd66,read_response_data);
read_response_emit_pending<=1'b0;
core_state<=C_IDLE;
end else begin
read_response_data[8*(2+2*read_word_index)+:8]<=poly_read_sample[7:0];
read_response_data[8*(3+2*read_word_index)+:8]<=poly_read_sample[15:8];
if (read_word_index==6'd31) begin
read_response_emit_pending<=1'b1;
core_state<=C_READ_RESP;
end else begin
read_word_index<=read_word_index+1'b1;
poly_read_addr<={saved_read_chunk,5'b00000}+read_word_index+1'b1;
core_state<=C_READ_PRIME;
end
end
end
C_WAIT_POLY: begin
if (poly_done) begin
if (poly_error) begin
operation_state<=OP_IDLE;
complete_retained(TXN_FAILED,ERR_INTERNAL_FAULT,0,'0);
end else begin
operation_state<=OP_RESULT_READY;
complete_retained(TXN_SUCCEEDED,ERR_OK,0,'0);
end
core_state<=C_IDLE;
end
end
C_WAIT_ASCON: begin
if (ascon_done) begin
uart_frame<='0;
uart_frame[7:0]<=8'hA5; uart_frame[15:8]<=8'h5A;
uart_frame[8*2+:192]<=crypto_ad_snapshot;
uart_frame[8*26+:192]<=ascon_ciphertext;
uart_frame[8*50+:128]<=ascon_tag;
uart_start<=1'b1;
core_state<=C_WAIT_UART;
end
end
C_WAIT_UART: begin
if (uart_done) begin
txn_data='0;
txn_data[7:0]=active_session_id[31:24];txn_data[15:8]=active_session_id[23:16];
txn_data[23:16]=active_session_id[15:8];txn_data[31:24]=active_session_id[7:0];
for (ci=0;ci<8;ci=ci+1) txn_data[8*(4+ci)+:8]=sequence_number[63-8*ci-:8];
txn_data[103:96]=8'h00;txn_data[111:104]=8'h42;
complete_retained(TXN_SUCCEEDED,ERR_OK,16'd14,txn_data);
sequence_number<=sequence_number+1'b1;
telemetry_loaded<=1'b0;telemetry_plaintext<=0;
operation_state<=OP_IDLE;
core_state<=C_IDLE;
end
end
C_ZEROIZE_WAIT: begin
if (poly_zeroize_done) zeroize_memory_done <= 1'b1;
if ((poly_zeroize_done || zeroize_memory_done) && zeroize_ni) begin
if (zeroize_from_command) begin
complete_retained(TXN_ZEROIZED,ERR_ZEROIZED,0,'0);
session_state<=self_test_pass?SESSION_READY_NO_SESSION:SESSION_SELF_TEST_REQUIRED;
end else if (zeroize_due_to_fault || fatal_latched_i || fault_latched) begin
session_state<=SESSION_FAULT_LOCKED;
diagnostic_summary<=diagnostic_summary|DIAG_HEARTBEAT_OR_FAULT;
end else begin
self_test_pass<=1'b0;
session_state<=SESSION_SELF_TEST_REQUIRED;
end
zeroize_memory_done <= 1'b0;
core_state<=C_IDLE;
end
end
C_ST_ASCON_WAIT: begin
if (ascon_done) begin
if (ascon_ciphertext!=ASCON_KAT_CT || ascon_tag!=ASCON_KAT_TAG) begin
diagnostic_summary<=diagnostic_summary|DIAG_SELF_TEST;
fault_latched<=1'b1;session_state<=SESSION_FAULT_LOCKED;
operation_state<=OP_IDLE;
complete_retained(TXN_FAILED,ERR_SELF_TEST_FAILED,0,'0);
core_state<=C_IDLE;
end else begin
poly_zeroize<=1'b1;
core_state<=C_ST_ZERO_WAIT;
end
end
end
C_ST_ZERO_WAIT: begin
if (poly_zeroize_done) begin
poly_start_operation<=2'd1;poly_start<=1'b1;
core_state<=C_ST_NTT_WAIT;
end
end
C_ST_NTT_WAIT: begin
if (poly_done) begin
selftest_index<=0;
selftest_scan_phase<=2'd0;
poly_read_slot<=0;
poly_read_addr<=0;
core_state<=C_ST_NTT_SCAN;
end
end

// The three legacy *_SCAN states form a common three-cycle read pipeline for
// every self-test phase: PRIME -> CAPTURE -> EVALUATE. The DPB/canonical output
// is captured in poly_read_sample before it can affect transaction-control
// or retained-result logic.
C_ST_NTT_SCAN: begin
core_state<=C_ST_INTT_SCAN;
end
C_ST_INTT_SCAN: begin
poly_read_sample<=poly_read_data;
core_state<=C_ST_BM_SCAN;
end
C_ST_BM_SCAN: begin
if (poly_read_sample!=16'd0) begin
fault_latched<=1'b1;
session_state<=SESSION_FAULT_LOCKED;
operation_state<=OP_IDLE;
complete_retained(TXN_FAILED,ERR_SELF_TEST_FAILED,0,'0);
core_state<=C_IDLE;
end else if (selftest_index==8'd255) begin
case (selftest_scan_phase)
2'd0: begin
poly_start_operation<=2'd2;
poly_start<=1'b1;
core_state<=C_ST_INTT_WAIT;
end
2'd1: begin
poly_start_operation<=2'd3;
poly_start<=1'b1;
core_state<=C_ST_BM_WAIT;
end
default: begin
self_test_pass<=1'b1;
session_state<=SESSION_READY_NO_SESSION;
operation_state<=OP_IDLE;
txn_data='0;
txn_data[7:0]=8'h01;
txn_data[15:8]=8'h3E;
complete_retained(TXN_SUCCEEDED,ERR_OK,16'd2,txn_data);
core_state<=C_IDLE;
end
endcase
end else begin
selftest_index<=selftest_index+1'b1;
poly_read_addr<=selftest_index+1'b1;
core_state<=C_ST_NTT_SCAN;
end
end
C_ST_INTT_WAIT: begin
if (poly_done) begin
selftest_index<=0;
selftest_scan_phase<=2'd1;
poly_read_slot<=0;
poly_read_addr<=0;
core_state<=C_ST_NTT_SCAN;
end
end
C_ST_BM_WAIT: begin
if (poly_done) begin
selftest_index<=0;
selftest_scan_phase<=2'd2;
poly_read_slot<=0;
poly_read_addr<=0;
core_state<=C_ST_NTT_SCAN;
end
end
default: core_state<=C_IDLE;
endcase
end
end
end
endmodule
