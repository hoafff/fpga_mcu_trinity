else if (pbyte(request_payload_i,0)>1 || pbyte(request_payload_i,1)>7)
emit_error(request_command_i,request_txid_i,ERR_BAD_CHUNK_INDEX,0);
else if ((pbyte(request_payload_i,0)==0 && chunk_valid_a[pbyte(request_payload_i,1)]) ||
(pbyte(request_payload_i,0)==1 && chunk_valid_b[pbyte(request_payload_i,1)])) begin
if ((pbyte(request_payload_i,0)==0 && chunk_fingerprint_a[pbyte(request_payload_i,1)]==incoming_fingerprint) ||
(pbyte(request_payload_i,0)==1 && chunk_fingerprint_b[pbyte(request_payload_i,1)]==incoming_fingerprint))
emit_empty_success(request_command_i,request_txid_i);
else emit_error(request_command_i,request_txid_i,ERR_CHUNK_CONFLICT,0);
end else begin
saved_chunk_slot<=request_payload_i[0];
saved_chunk_index<=request_payload_i[10:8];
saved_chunk_fingerprint<=incoming_fingerprint;
saved_chunk_data<=request_payload_i[8*2+:512];
saved_chunk_invalid<=1'b0;
chunk_word_index<=0;
response_command_o<=request_command_i; response_txid_o<=request_txid_i;
core_state<=C_WRITE_CHUNK;
end
end
CMD_POLY_EXECUTE: begin
if (request_payload_length_i!=2 || pbyte(request_payload_i,1)!=0 || pbyte(request_payload_i,0)!=poly_operation)
emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else if (operation_state!=OP_READY_TO_EXECUTE)
emit_error(request_command_i,request_txid_i,ERR_INCOMPLETE_INPUT,0);
else begin
begin_retained(request_txid_i,request_command_i,incoming_fingerprint);
poly_start_operation<=poly_operation[1:0]; poly_start<=1'b1;
operation_state<=OP_EXECUTING;
emit_empty_success(request_command_i,request_txid_i);
core_state<=C_WAIT_POLY;
end
end
CMD_POLY_READ_CHUNK: begin
if (request_payload_length_i!=2 || pbyte(request_payload_i,0)>1 || pbyte(request_payload_i,1)>7)
emit_error(request_command_i,request_txid_i,ERR_BAD_CHUNK_INDEX,0);
else if (operation_state!=OP_RESULT_READY)
emit_error(request_command_i,request_txid_i,ERR_RESULT_NOT_READY,0);
else begin
saved_read_slot<=request_payload_i[0];
saved_read_chunk<=request_payload_i[10:8];
read_word_index<=0;
poly_read_slot<=request_payload_i[0];
poly_read_addr<={request_payload_i[10:8],5'b00000};
read_response_data<='0;
read_response_data[7:0]<=pbyte(request_payload_i,0);
read_response_data[15:8]<=pbyte(request_payload_i,1);
response_command_o<=request_command_i;response_txid_o<=request_txid_i;
core_state<=C_READ_PRIME;
end
end
CMD_POLY_RETIRE: begin
if (request_payload_length_i!=2 || pbyte(request_payload_i,1)!=0)
emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else begin
if ((pbyte(request_payload_i,0) & 8'h01) != 0) begin poly_mask_a<=0;chunk_valid_a<=0; end
if ((pbyte(request_payload_i,0) & 8'h02) != 0) begin poly_mask_b<=0;chunk_valid_b<=0; end
operation_state<=OP_IDLE;
emit_empty_success(request_command_i,request_txid_i);
end
end
CMD_LOAD_TELEMETRY: begin
if (request_payload_length_i!=32 || pbyte(request_payload_i,1)!=0 ||
pbyte(request_payload_i,6)!=0 || pbyte(request_payload_i,7)!=0)
emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else if (session_state!=SESSION_ACTIVE || !secure_enable_i || fault_o)
emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
else if (telemetry_loaded && telemetry_request_image!=request_payload_i[255:0])
emit_error(request_command_i,request_txid_i,ERR_TRANSACTION_CONFLICT,0);
else begin
telemetry_message_type<=pbyte(request_payload_i,0);
telemetry_flags<={pbyte(request_payload_i,2),pbyte(request_payload_i,3)};
telemetry_source_id<={pbyte(request_payload_i,4),pbyte(request_payload_i,5)};
telemetry_plaintext<=request_payload_i[8*8+:192];
telemetry_request_image<=request_payload_i[255:0];
telemetry_loaded<=1'b1;
emit_empty_success(request_command_i,request_txid_i);
end
end
CMD_ENCRYPT_AND_SEND: begin
if (request_payload_length_i!=0) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
else if (session_state!=SESSION_ACTIVE || !active_valid || !secure_enable_i || fault_o || !telemetry_loaded)
emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
else begin
begin_retained(request_txid_i,request_command_i,incoming_fingerprint);
ascon_key_input<=active_key;ascon_nonce_input<=constructed_nonce;
ascon_ad_input<=constructed_ad;ascon_pt_input<=telemetry_plaintext;
crypto_ad_snapshot<=constructed_ad;
ascon_start<=1'b1;
operation_state<=OP_EXECUTING;
emit_empty_success(request_command_i,request_txid_i);
core_state<=C_WAIT_ASCON;
end
end
default: begin
diagnostic_summary<=diagnostic_summary|DIAG_BAD_COMMAND;
emit_error(request_command_i,request_txid_i,ERR_BAD_COMMAND,0);
end
endcase
end
end
end
C_WRITE_CHUNK: begin
poly_load_we<=1'b1;
poly_load_slot<=saved_chunk_slot;
poly_load_addr<={saved_chunk_index,5'b00000}+chunk_word_index;
poly_load_data<=saved_chunk_data[15:0];
if (saved_chunk_data[15:0] > 16'd3328)
saved_chunk_invalid<=1'b1;
if (chunk_word_index==6'd31) begin
if (saved_chunk_invalid || (saved_chunk_data[15:0] > 16'd3328)) begin
emit_error(response_command_o,response_txid_o,ERR_BAD_LENGTH,16'h0D01);
end else if (saved_chunk_slot) begin
poly_mask_b<=poly_mask_b|(8'b1<<saved_chunk_index);
chunk_valid_b<=chunk_valid_b|(8'b1<<saved_chunk_index);
chunk_fingerprint_b[saved_chunk_index]<=saved_chunk_fingerprint;
new_mask=poly_mask_b|(8'b1<<saved_chunk_index);
if ((poly_operation==3 && poly_mask_a==8'hFF && new_mask==8'hFF))
operation_state<=OP_READY_TO_EXECUTE;
emit_empty_success(response_command_o,response_txid_o);
end else begin
poly_mask_a<=poly_mask_a|(8'b1<<saved_chunk_index);
chunk_valid_a<=chunk_valid_a|(8'b1<<saved_chunk_index);
chunk_fingerprint_a[saved_chunk_index]<=saved_chunk_fingerprint;
new_mask=poly_mask_a|(8'b1<<saved_chunk_index);
if ((poly_operation!=3 && new_mask==8'hFF) ||
(poly_operation==3 && new_mask==8'hFF && poly_mask_b==8'hFF))
operation_state<=OP_READY_TO_EXECUTE;
emit_empty_success(response_command_o,response_txid_o);
end
core_state<=C_IDLE;
end else begin
saved_chunk_data<={16'd0,saved_chunk_data[511:16]};
chunk_word_index<=chunk_word_index+6'd1;
