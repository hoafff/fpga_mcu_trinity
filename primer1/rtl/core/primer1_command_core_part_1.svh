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
logic zeroize_from_command;
logic zeroize_due_to_fault;
logic zeroize_memory_done;
logic [191:0] crypto_ad_snapshot;
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
active_transaction_id <= 0;
if (code != ERR_OK) last_error <= code;
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
