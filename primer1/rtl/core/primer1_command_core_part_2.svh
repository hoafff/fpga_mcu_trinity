assign fault_o = fault_latched || (session_state == SESSION_FAULT_LOCKED);
integer ci;
logic [31:0] incoming_fingerprint;
logic [527:0] rsp;
logic [127:0] txn_data;
logic [7:0] new_mask;
always_ff @(posedge clk_i or negedge rst_ni) begin
if (!rst_ni) begin
core_state <= C_IDLE;
session_state <= SESSION_SELF_TEST_REQUIRED;
operation_state <= OP_IDLE;
self_test_pass <= 1'b0;
fault_latched <= 1'b0;
diagnostic_summary <= 0;
last_error <= 0;
active_transaction_id <= 0;
staged_session_id <= 0; active_session_id <= 0;
staged_key <= 0; active_key <= 0;
staged_nonce_prefix <= 0; active_nonce_prefix <= 0;
staged_valid <= 1'b0; active_valid <= 1'b0;
sequence_number <= 64'd1;
telemetry_loaded <= 1'b0;
telemetry_message_type <= 0; telemetry_flags <= 0; telemetry_source_id <= 0;
telemetry_plaintext <= 0; telemetry_request_image <= 0;
retained_valid <= 1'b0; retained_txid <= 0; retained_command <= 0;
retained_fingerprint <= 0; retained_state <= TXN_NONE; retained_code <= 0;
retained_data_length <= 0; retained_data <= 0;
retained_commit_pending <= 1'b0;
retained_completion_kind <= RETAIN_COMMIT_SUCCESS_EMPTY;
retained_completion_data <= 0;
poly_operation <= 0; poly_mask_a <= 0; poly_mask_b <= 0;
chunk_valid_a <= 0; chunk_valid_b <= 0;
for (ci=0; ci<8; ci=ci+1) begin
chunk_fingerprint_a[ci] <= 0;
chunk_fingerprint_b[ci] <= 0;
end
response_commit_o <= 1'b0; response_command_o <= 0; response_flags_o <= 0;
response_txid_o <= 0; response_payload_length_o <= 0; response_payload_o <= 0;
poly_load_we <= 1'b0; poly_load_slot <= 0; poly_load_addr <= 0; poly_load_data <= 0;
poly_read_slot <= 0; poly_read_addr <= 0; poly_start <= 1'b0;
poly_start_operation <= 0; poly_zeroize <= 1'b0;
ascon_start <= 1'b0; ascon_key_input <= 0; ascon_nonce_input <= 0;
ascon_ad_input <= 0; ascon_pt_input <= 0;
uart_start <= 1'b0; uart_frame <= 0;
heartbeat_counter <= 0; heartbeat_o <= 1'b0;
chunk_word_index <= 0; saved_chunk_slot <= 0; saved_chunk_index <= 0;
saved_chunk_fingerprint <= 0; saved_chunk_data <= 0; saved_chunk_invalid <= 1'b0;
read_word_index <= 0; saved_read_slot <= 0; saved_read_chunk <= 0;
read_response_data <= 0; read_response_emit_pending <= 1'b0;
selftest_index <= 0; selftest_scan_phase <= 0; selftest_requested_mask <= 0;
poly_read_sample <= 0;
zeroize_from_command <= 1'b0; zeroize_due_to_fault <= 1'b0;
zeroize_memory_done <= 1'b0;
crypto_ad_snapshot <= 0;
end else begin
response_commit_o <= 1'b0;
poly_load_we <= 1'b0;
poly_start <= 1'b0;
poly_zeroize <= 1'b0;
ascon_start <= 1'b0;
uart_start <= 1'b0;
// Commit the wide retained bank from a registered one-bit pulse. This runs in
// parallel with request dispatch, so a one-cycle SPI request_valid pulse is
// never dropped merely because a completion became visible in this cycle.
if (retained_commit_pending) begin
retained_commit_pending <= 1'b0;
active_transaction_id <= 0;
retained_state <= TXN_SUCCEEDED;
retained_code <= ERR_OK;
retained_data_length <= 0;
retained_data <= '0;
case (retained_completion_kind)
RETAIN_COMMIT_INTERNAL_FAULT: begin
retained_state <= TXN_FAILED;
retained_code <= ERR_INTERNAL_FAULT;
last_error <= ERR_INTERNAL_FAULT;
end
RETAIN_COMMIT_ZEROIZED: begin
retained_state <= TXN_ZEROIZED;
retained_code <= ERR_ZEROIZED;
last_error <= ERR_ZEROIZED;
end
RETAIN_COMMIT_SELFTEST_FAILED: begin
retained_state <= TXN_FAILED;
retained_code <= ERR_SELF_TEST_FAILED;
last_error <= ERR_SELF_TEST_FAILED;
end
RETAIN_COMMIT_SELFTEST_SUCCESS: begin
retained_data_length <= 16'd2;
retained_data <= retained_completion_data;
end
RETAIN_COMMIT_UART_SUCCESS: begin
retained_data_length <= 16'd14;
retained_data <= retained_completion_data;
end
default: begin end
endcase
end
if (heartbeat_counter == HEARTBEAT_CYCLES-1) begin
heartbeat_counter <= 0;
heartbeat_o <= ~heartbeat_o;
end else heartbeat_counter <= heartbeat_counter + 1'b1;
if (session_state == SESSION_COMMITTED_BLOCKED && secure_enable_i && !fatal_latched_i) begin
session_state <= SESSION_ACTIVE;
end
if ((fatal_latched_i || !zeroize_ni ||
(session_state == SESSION_ACTIVE && !secure_enable_i)) &&
core_state != C_ZEROIZE_WAIT && session_state != SESSION_ZEROIZE_BUSY &&
session_state != SESSION_FAULT_LOCKED) begin
fault_latched <= fault_latched | fatal_latched_i;
zeroize_due_to_fault <= fatal_latched_i;
zeroize_from_command <= 1'b0;
zeroize_memory_done <= 1'b0;
session_state <= SESSION_ZEROIZE_BUSY;
operation_state <= OP_IDLE;
staged_key <= 0; active_key <= 0;
staged_nonce_prefix <= 0; active_nonce_prefix <= 0;
staged_session_id <= 0; active_session_id <= 0;
staged_valid <= 1'b0; active_valid <= 1'b0;
telemetry_loaded <= 1'b0; telemetry_plaintext <= 0;
sequence_number <= 64'd1;
retained_valid <= 1'b0;
retained_commit_pending <= 1'b0;
read_response_emit_pending <= 1'b0;
poly_zeroize <= 1'b1;
core_state <= C_ZEROIZE_WAIT;
end else begin
// Long-running retained operations continue their FSM in this cycle, while
// read-only reconciliation requests are answered independently. This avoids
// losing the one-cycle request_valid pulse without pausing poly/Ascon/UART work.
if ((core_state==C_WAIT_POLY || core_state==C_WAIT_ASCON ||
core_state==C_WAIT_UART || core_state==C_ZEROIZE_WAIT ||
core_state==C_ST_ASCON_WAIT || core_state==C_ST_ZERO_WAIT ||
core_state==C_ST_NTT_WAIT || core_state==C_ST_NTT_SCAN ||
core_state==C_ST_INTT_WAIT || core_state==C_ST_INTT_SCAN ||
core_state==C_ST_BM_WAIT || core_state==C_ST_BM_SCAN) &&
request_valid_i && response_ready_i) begin
if (request_command_i==CMD_GET_STATUS) begin
if (request_payload_length_i!=0)
emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else
emit_status_response(request_command_i,request_txid_i);
end else if (request_command_i==CMD_GET_TXN_RESULT) begin
if (request_payload_length_i!=2)
emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else
emit_txn_result_response(request_command_i,request_txid_i,
{pbyte(request_payload_i,0),pbyte(request_payload_i,1)});
end else begin
emit_error(request_command_i,request_txid_i,ERR_BUSY,active_transaction_id);
end
end
case (core_state)
C_IDLE: begin
if (transport_error_valid_i && response_ready_i) begin
if (transport_error_code_i == ERR_BAD_CRC)
diagnostic_summary <= diagnostic_summary | DIAG_CRC;
else
diagnostic_summary <= diagnostic_summary | DIAG_TRANSPORT;
emit_error(transport_error_command_i,transport_error_txid_i,
transport_error_code_i,
(transport_error_code_i == ERR_BAD_LENGTH) ? request_payload_length_i : 16'd0);
end else if (request_valid_i && response_ready_i) begin
incoming_fingerprint = request_fingerprint_i;
if (is_retained_side_effect(request_command_i) && retained_valid && request_command_i != CMD_ZEROIZE) begin
if (request_txid_i == retained_txid &&
request_command_i == retained_command &&
incoming_fingerprint == retained_fingerprint) begin
emit_empty_success(request_command_i,request_txid_i);
end else if (request_txid_i == retained_txid) begin
diagnostic_summary <= diagnostic_summary | DIAG_TRANSACTION_CONFLICT;
emit_error(request_command_i,request_txid_i,ERR_TRANSACTION_CONFLICT,0);
end else begin
emit_error(request_command_i,request_txid_i,ERR_RESULT_PENDING,retained_txid);
end
end else begin
case (request_command_i)
CMD_GET_INFO: begin
if (request_payload_length_i != 0) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else begin
rsp = '0;
rsp[7:0] = TARGET_PRIMER1;
rsp[15:8] = PROTOCOL_VERSION;
rsp[23:16] = CAPABILITIES[31:24]; rsp[31:24] = CAPABILITIES[23:16];
rsp[39:32] = CAPABILITIES[15:8]; rsp[47:40] = CAPABILITIES[7:0];
rsp[55:48] = BUILD_ID[31:24]; rsp[63:56] = BUILD_ID[23:16];
rsp[71:64] = BUILD_ID[15:8]; rsp[79:72] = BUILD_ID[7:0];
emit_response(request_command_i,request_txid_i,FLAG_RESPONSE,16'd12,rsp);
end
end
CMD_GET_STATUS: begin
if (request_payload_length_i != 0)
emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,request_payload_length_i);
else
emit_status_response(request_command_i,request_txid_i);
end
