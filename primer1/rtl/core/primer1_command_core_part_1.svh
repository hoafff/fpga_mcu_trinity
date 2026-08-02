logic [527:0] uart_frame;
uart_frame_tx #(.CLOCK_HZ(CLOCK_HZ), .BAUD(UART_BAUD)) u_uart (
.clk_i(clk_i), .rst_ni(rst_ni), .start_i(uart_start), .abort_i(uart_abort),
.frame_i(uart_frame), .tx_o(uart_tx_o), .busy_o(uart_busy), .done_o(uart_done)
);
logic [21:0] heartbeat_counter;
logic [5:0] chunk_word_index;
logic saved_chunk_slot;
logic [2:0] saved_chunk_index;
logic [31:0] saved_chunk_fingerprint;
logic [511:0] saved_chunk_data;
logic saved_chunk_invalid;
logic [5:0] read_word_index;
logic saved_read_slot;
logic [2:0] saved_read_chunk;
logic [527:0] read_response_data;
logic [7:0] selftest_index;
logic [1:0] selftest_scan_phase;
logic [15:0] selftest_requested_mask;
logic [15:0] poly_read_sample;
logic read_response_emit_pending;
logic zeroize_from_command;
logic zeroize_due_to_fault;
logic zeroize_memory_done;
logic [191:0] crypto_ad_snapshot;

localparam logic [15:0] SELFTEST_SUPPORTED_MASK =
TEST_MEMORY | TEST_NTT | TEST_INTT | TEST_BASEMUL |
TEST_ASCON | TEST_ZEROIZE;

typedef enum logic [2:0] {
RETAIN_COMMIT_SUCCESS_EMPTY,
RETAIN_COMMIT_INTERNAL_FAULT,
RETAIN_COMMIT_ZEROIZED,
RETAIN_COMMIT_SELFTEST_FAILED,
RETAIN_COMMIT_SELFTEST_SUCCESS,
RETAIN_COMMIT_UART_SUCCESS
} retained_completion_e;
retained_completion_e retained_completion_kind;
logic retained_commit_pending;
logic [127:0] retained_completion_data;

function automatic logic [7:0] pbyte(input logic [527:0] p, input integer idx);
pbyte = p[8*idx +: 8];
endfunction
function automatic logic is_retained_side_effect(input logic [7:0] command);
begin
case (command)
CMD_RUN_SELF_TEST, CMD_ZEROIZE, CMD_COMMIT_SESSION,
CMD_POLY_EXECUTE, CMD_ENCRYPT_AND_SEND: is_retained_side_effect = 1'b1;
default: is_retained_side_effect = 1'b0;
endcase
end
endfunction
task automatic emit_response(
input logic [7:0] command,
input logic [15:0] txid,
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
emit_response(command,txid,FLAG_RESPONSE,16'd0,'0);
end
endtask
task automatic emit_error(
input logic [7:0] command,
input logic [15:0] txid,
input logic [15:0] code,
input logic [15:0] detail
);
logic [527:0] ep;
begin
ep = '0;
ep[7:0] = code[15:8]; ep[15:8] = code[7:0];
ep[23:16] = {4'h0,session_state};
ep[31:24] = {5'h0,operation_state};
ep[39:32] = detail[15:8]; ep[47:40] = detail[7:0];
emit_response(command,txid,FLAG_RESPONSE|FLAG_ERROR,16'd6,ep);
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
retained_data_length <= 0;
retained_data <= '0;
active_transaction_id <= txid;
end
endtask

// Completion is deliberately split into two cycles. The event-detection cycle
// records only a compact completion kind; C_IDLE commits the wide retained
// payload on the following cycle from retained_commit_pending. This prevents
// RAM/read-result logic from becoming the clock-enable cone of retained_data.
task automatic complete_retained(
input transaction_state_e final_state,
input logic [15:0] code,
input logic [15:0] length,
input logic [127:0] data
);
begin
if (final_state == TXN_ZEROIZED && code == ERR_ZEROIZED)
retained_completion_kind <= RETAIN_COMMIT_ZEROIZED;
else if (final_state == TXN_FAILED && code == ERR_SELF_TEST_FAILED)
retained_completion_kind <= RETAIN_COMMIT_SELFTEST_FAILED;
else if (final_state == TXN_FAILED)
retained_completion_kind <= RETAIN_COMMIT_INTERNAL_FAULT;
else if (length == 16'd14) begin
retained_completion_kind <= RETAIN_COMMIT_UART_SUCCESS;
retained_completion_data <= data;
end else if (length == 16'd2) begin
retained_completion_kind <= RETAIN_COMMIT_SELFTEST_SUCCESS;
retained_completion_data <= data;
end else
retained_completion_kind <= RETAIN_COMMIT_SUCCESS_EMPTY;
retained_commit_pending <= 1'b1;
end
endtask

task automatic emit_status_response(
input logic [7:0] command,
input logic [15:0] txid
);
logic [527:0] status_data;
begin
status_data = '0;
status_data[7:0] = {4'h0,session_state};
status_data[15:8] = {5'h0,operation_state};
status_data[23:16] = (mailbox_pending_i ? PENDING_RESPONSE_MAILBOX : 0) |
(retained_valid ? PENDING_SIDE_EFFECT_RESULT : 0);
status_data[31:24] = (self_test_pass ? SECURE_SELF_TEST_PASS : 0) |
(staged_valid ? SECURE_SESSION_STAGED : 0) |
(secure_enable_i ? SECURE_ENABLE : 0) |
((session_state==SESSION_ZEROIZE_BUSY) ? SECURE_ZEROIZE_BUSY : 0) |
(fault_o ? SECURE_FAULT_LOCKED : 0);
status_data[39:32]=active_session_id[31:24];
status_data[47:40]=active_session_id[23:16];
status_data[55:48]=active_session_id[15:8];
status_data[63:56]=active_session_id[7:0];
status_data[71:64]=last_error[15:8];
status_data[79:72]=last_error[7:0];
status_data[87:80]=active_transaction_id[15:8];
status_data[95:88]=active_transaction_id[7:0];
status_data[103:96]=diagnostic_summary[31:24];
status_data[111:104]=diagnostic_summary[23:16];
status_data[119:112]=diagnostic_summary[15:8];
status_data[127:120]=diagnostic_summary[7:0];
emit_response(command,txid,FLAG_RESPONSE,16'd16,status_data);
end
endtask

task automatic emit_txn_result_response(
input logic [7:0] command,
input logic [15:0] response_txid,
input logic [15:0] queried_txid
);
logic [527:0] result_data;
integer result_index;
begin
if (!retained_valid || queried_txid != retained_txid)
emit_error(command,response_txid,ERR_RESULT_NOT_READY,0);
else begin
result_data='0;
result_data[7:0]=retained_txid[15:8];
result_data[15:8]=retained_txid[7:0];
result_data[23:16]={5'h0,retained_state};
result_data[31:24]=retained_command;
result_data[39:32]=retained_code[15:8];
result_data[47:40]=retained_code[7:0];
result_data[55:48]=retained_data_length[15:8];
result_data[63:56]=retained_data_length[7:0];
for (result_index=0;result_index<16;result_index=result_index+1)
if (result_index<retained_data_length)
result_data[8*(10+result_index)+:8]=retained_data[8*result_index+:8];
emit_response(command,response_txid,FLAG_RESPONSE,
16'd10+retained_data_length,result_data);
end
end
endtask

task automatic finish_selftest_success;
logic [127:0] selftest_data;
begin
selftest_data='0;
selftest_data[7:0]=selftest_requested_mask[15:8];
selftest_data[15:8]=selftest_requested_mask[7:0];
self_test_pass<=1'b1;
session_state<=SESSION_READY_NO_SESSION;
operation_state<=OP_IDLE;
complete_retained(TXN_SUCCEEDED,ERR_OK,16'd2,selftest_data);
core_state<=C_IDLE;
end
endtask

logic [191:0] constructed_ad;
logic [127:0] constructed_nonce;
integer ai;
always_comb begin
constructed_ad = '0;
constructed_ad[7:0] = PROTOCOL_VERSION;
constructed_ad[15:8] = telemetry_message_type;
constructed_ad[23:16] = telemetry_flags[15:8];
constructed_ad[31:24] = telemetry_flags[7:0];
constructed_ad[39:32] = active_session_id[31:24];
constructed_ad[47:40] = active_session_id[23:16];
constructed_ad[55:48] = active_session_id[15:8];
constructed_ad[63:56] = active_session_id[7:0];
for (ai=0; ai<8; ai=ai+1)
constructed_ad[8*(8+ai) +: 8] = sequence_number[63-8*ai -: 8];
constructed_ad[135:128] = 8'h00;
constructed_ad[143:136] = 8'h18;
constructed_ad[151:144] = telemetry_source_id[15:8];
constructed_ad[159:152] = telemetry_source_id[7:0];
constructed_nonce = '0;
constructed_nonce[63:0] = active_nonce_prefix;
for (ai=0; ai<8; ai=ai+1)
constructed_nonce[8*(8+ai) +: 8] = sequence_number[63-8*ai -: 8];
end
assign crypto_abort = (session_state == SESSION_ZEROIZE_BUSY) || !zeroize_ni || fatal_latched_i;
assign uart_abort = crypto_abort || !secure_enable_i;
assign retained_result_pending_o = retained_valid;
assign irq_event_pending_o = retained_valid;
assign session_state_o = session_state;
assign operation_state_o = operation_state;
