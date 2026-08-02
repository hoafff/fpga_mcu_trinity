rsp[39:32]=active_session_id[31:24]; rsp[47:40]=active_session_id[23:16];
rsp[55:48]=active_session_id[15:8]; rsp[63:56]=active_session_id[7:0];
rsp[71:64]=last_error[15:8]; rsp[79:72]=last_error[7:0];
rsp[87:80]=active_transaction_id[15:8]; rsp[95:88]=active_transaction_id[7:0];
rsp[103:96]=diagnostic_summary[31:24]; rsp[111:104]=diagnostic_summary[23:16];
rsp[119:112]=diagnostic_summary[15:8]; rsp[127:120]=diagnostic_summary[7:0];
emit_response(request_command_i,request_txid_i,FLAG_RESPONSE,16'd16,rsp);
end
end
CMD_RUN_SELF_TEST: begin
if (request_payload_length_i != 4 || pbyte(request_payload_i,2)!=0 || pbyte(request_payload_i,3)!=0)
emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else if (session_state != SESSION_SELF_TEST_REQUIRED && session_state != SESSION_READY_NO_SESSION)
emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
else begin
begin_retained(request_txid_i,request_command_i,incoming_fingerprint);
session_state <= SESSION_SELF_TEST_RUNNING;
operation_state <= OP_EXECUTING;
ascon_key_input <= 0; ascon_nonce_input <= 0;
ascon_ad_input <= 0; ascon_pt_input <= 0;
ascon_start <= 1'b1;
emit_empty_success(request_command_i,request_txid_i);
core_state <= C_ST_ASCON_WAIT;
end
end
CMD_GET_TXN_RESULT: begin
if (request_payload_length_i != 2) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else if (!retained_valid || {pbyte(request_payload_i,0),pbyte(request_payload_i,1)} != retained_txid)
emit_error(request_command_i,request_txid_i,ERR_RESULT_NOT_READY,0);
else begin
rsp='0;
rsp[7:0]=retained_txid[15:8]; rsp[15:8]=retained_txid[7:0];
rsp[23:16]={5'h0,retained_state}; rsp[31:24]=retained_command;
rsp[39:32]=retained_code[15:8]; rsp[47:40]=retained_code[7:0];
rsp[55:48]=retained_data_length[15:8]; rsp[63:56]=retained_data_length[7:0];
for (ci=0;ci<16;ci=ci+1)
if (ci<retained_data_length) rsp[8*(10+ci)+:8]=retained_data[8*ci+:8];
emit_response(request_command_i,request_txid_i,FLAG_RESPONSE,
16'd10+retained_data_length,rsp);
end
end
CMD_RETIRE_TXN_RESULT: begin
if (request_payload_length_i != 2) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else if (retained_valid && {pbyte(request_payload_i,0),pbyte(request_payload_i,1)}==retained_txid) begin
retained_valid<=1'b0; retained_state<=TXN_NONE; emit_empty_success(request_command_i,request_txid_i);
end else emit_empty_success(request_command_i,request_txid_i);
end
CMD_ZEROIZE: begin
if (request_payload_length_i != 4 || pbyte(request_payload_i,1)!=0 ||
pbyte(request_payload_i,2)!=0 || pbyte(request_payload_i,3)!=0)
emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else begin
begin_retained(request_txid_i,request_command_i,incoming_fingerprint);
zeroize_from_command <= 1'b1; zeroize_due_to_fault <= 1'b0;
zeroize_memory_done <= 1'b0;
session_state <= SESSION_ZEROIZE_BUSY; operation_state <= OP_IDLE;
staged_key<=0;active_key<=0;staged_nonce_prefix<=0;active_nonce_prefix<=0;
staged_session_id<=0;active_session_id<=0;staged_valid<=0;active_valid<=0;
telemetry_loaded<=0;telemetry_plaintext<=0;sequence_number<=64'd1;
poly_zeroize<=1'b1;
emit_empty_success(request_command_i,request_txid_i);
core_state<=C_ZEROIZE_WAIT;
end
end
CMD_STAGE_SESSION: begin
if (request_payload_length_i != 28) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else if (!self_test_pass || (session_state!=SESSION_READY_NO_SESSION && session_state!=SESSION_STAGED))
emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
else begin
if (staged_valid && staged_session_id=={pbyte(request_payload_i,0),pbyte(request_payload_i,1),pbyte(request_payload_i,2),pbyte(request_payload_i,3)}) begin
if (staged_key==request_payload_i[8*4+:128] && staged_nonce_prefix==request_payload_i[8*20+:64])
emit_empty_success(request_command_i,request_txid_i);
else emit_error(request_command_i,request_txid_i,ERR_SESSION_ID_COLLISION,0);
end else if ((active_valid && active_session_id=={pbyte(request_payload_i,0),pbyte(request_payload_i,1),pbyte(request_payload_i,2),pbyte(request_payload_i,3)})) begin
emit_error(request_command_i,request_txid_i,ERR_SESSION_ID_COLLISION,0);
end else begin
staged_session_id<={pbyte(request_payload_i,0),pbyte(request_payload_i,1),pbyte(request_payload_i,2),pbyte(request_payload_i,3)};
staged_key<=request_payload_i[8*4+:128];
staged_nonce_prefix<=request_payload_i[8*20+:64];
staged_valid<=1'b1; session_state<=SESSION_STAGED;
emit_empty_success(request_command_i,request_txid_i);
end
end
end
CMD_COMMIT_SESSION: begin
if (request_payload_length_i != 4) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else if (secure_enable_i)
emit_error(request_command_i,request_txid_i,ERR_COMMIT_REJECTED,0);
else if (!staged_valid || session_state!=SESSION_STAGED ||
{pbyte(request_payload_i,0),pbyte(request_payload_i,1),pbyte(request_payload_i,2),pbyte(request_payload_i,3)}!=staged_session_id)
emit_error(request_command_i,request_txid_i,ERR_BAD_SESSION,0);
else begin
begin_retained(request_txid_i,request_command_i,incoming_fingerprint);
active_session_id<=staged_session_id; active_key<=staged_key;
active_nonce_prefix<=staged_nonce_prefix; active_valid<=1'b1;
staged_key<=0; staged_nonce_prefix<=0; staged_valid<=1'b0;
sequence_number<=64'd1; session_state<=SESSION_COMMITTED_BLOCKED;
complete_retained(TXN_SUCCEEDED,ERR_OK,0,'0);
emit_empty_success(request_command_i,request_txid_i);
end
end
CMD_ABORT_SESSION: begin
if (request_payload_length_i != 4) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else begin
staged_key<=0;active_key<=0;staged_nonce_prefix<=0;active_nonce_prefix<=0;
staged_session_id<=0;active_session_id<=0;staged_valid<=0;active_valid<=0;
telemetry_loaded<=0;telemetry_plaintext<=0;sequence_number<=64'd1;
session_state<=self_test_pass?SESSION_READY_NO_SESSION:SESSION_SELF_TEST_REQUIRED;
emit_empty_success(request_command_i,request_txid_i);
end
end
CMD_POLY_BEGIN: begin
if (request_payload_length_i!=4 || pbyte(request_payload_i,2)!=8 || pbyte(request_payload_i,3)!=0)
emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else if (operation_state==OP_EXECUTING)
emit_error(request_command_i,request_txid_i,ERR_BUSY,0);
else if ((pbyte(request_payload_i,0)==1 || pbyte(request_payload_i,0)==2) && pbyte(request_payload_i,1)!=1)
emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
else if (pbyte(request_payload_i,0)==3 && pbyte(request_payload_i,1)!=3)
emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
else if (pbyte(request_payload_i,0)<1 || pbyte(request_payload_i,0)>3)
emit_error(request_command_i,request_txid_i,ERR_BAD_COMMAND,0);
else begin
poly_operation<=pbyte(request_payload_i,0);
poly_mask_a<=0;poly_mask_b<=0;chunk_valid_a<=0;chunk_valid_b<=0;
operation_state<=OP_LOAD_INPUT;
emit_empty_success(request_command_i,request_txid_i);
end
end
CMD_POLY_WRITE_CHUNK: begin
if (request_payload_length_i!=66) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else if (operation_state!=OP_LOAD_INPUT && operation_state!=OP_READY_TO_EXECUTE)
emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
