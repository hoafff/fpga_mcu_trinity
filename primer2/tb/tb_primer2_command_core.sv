`timescale 1ns/1ps
module tb_primer2_command_core;
  import trinity_spi_pkg::*;
  logic clk=0,rst_n=0,secure=0,zeroize_n=1,fatal=0;
  logic request_valid=0; logic [7:0] request_command=0,request_flags=0;
  logic [15:0] request_txid=0,request_length=0; logic [527:0] request_payload=0;
  logic [31:0] request_fingerprint=0;
  logic transport_error=0; logic [7:0] transport_command=0; logic [15:0] transport_txid=0,transport_code=0;
  logic response_commit; logic [7:0] response_command,response_flags; logic [15:0] response_txid,response_length;
  logic [527:0] response_payload; logic response_ready=1,mailbox_pending=0;
  logic frame_valid=0,frame_timeout=0,frame_error=0,frame_drop=0,frame_blocked=0;
  logic [511:0] frame_body=0; logic [2:0] frame_rx_state=RX_HUNT_SYNC;
  logic rx_enable,result_pending,retained_pending,auth_pending,event_pending,heartbeat,fault;
  logic [3:0] session_state; logic [2:0] operation_state,rx_state;
  logic [527:0] p; integer i,cycles;
  localparam logic [511:0] BODY1=512'h1A9061D8C0929EA8374B85ED37AF716530CCB278A33B70139B376D8290C255B8D1357E03280E320C000000004433180001000000000000004433221134120201;
  localparam logic [511:0] BODY2=512'h173FAEC87E4F794FB7D585F0C18AFF7257539185E37CA985AB55C616547EE8C5EAF9A65B11B158C7000000004433180002000000000000004433221134120201;
  localparam logic [511:0] BODY3=512'hD915ED143029649F2F53A03B430EBC6574B4F56EA6B09A389877ACB7B4D24B427E4E7C03A2DA0E48000000004433180003000000000000004433221134120201;
  localparam logic [511:0] BODY4=512'h2C5D5D1349278890CC3286CBD733B4320524228B9E589922B287618812B84CBC7F2E270DF3896F33000000004433180004000000000000004433221134120201;
  localparam logic [191:0] EXPECTED_PT=192'h0017161514131211100F0E0D0C0B0A090807060504030201;
  always #5 clk=~clk;

  primer2_command_core #(.CLOCK_HZ(1000)) dut(
    .clk_i(clk),.rst_ni(rst_n),.secure_enable_i(secure),.zeroize_ni(zeroize_n),.fatal_latched_i(fatal),
    .request_valid_i(request_valid),.request_command_i(request_command),.request_flags_i(request_flags),
    .request_txid_i(request_txid),.request_payload_length_i(request_length),.request_payload_i(request_payload),
    .request_fingerprint_i(request_fingerprint),.transport_error_valid_i(transport_error),
    .transport_error_command_i(transport_command),.transport_error_txid_i(transport_txid),.transport_error_code_i(transport_code),
    .response_commit_o(response_commit),.response_command_o(response_command),.response_flags_o(response_flags),
    .response_txid_o(response_txid),.response_payload_length_o(response_length),.response_payload_o(response_payload),
    .response_ready_i(response_ready),.mailbox_pending_i(mailbox_pending),.frame_valid_i(frame_valid),.frame_body_i(frame_body),
    .frame_timeout_i(frame_timeout),.frame_framing_error_i(frame_error),.frame_pending_drop_i(frame_drop),
    .frame_blocked_i(frame_blocked),.frame_rx_state_i(frame_rx_state),.rx_accept_enable_o(rx_enable),
    .result_pending_o(result_pending),.retained_result_pending_o(retained_pending),
    .authenticated_result_pending_o(auth_pending),.irq_event_pending_o(event_pending),.heartbeat_o(heartbeat),
    .fault_o(fault),.session_state_o(session_state),.operation_state_o(operation_state),.rx_state_o(rx_state));

  always @(posedge clk)
    if (rst_n && dut.core_state==3'd2 && auth_pending)
      $fatal(1,"plaintext/result became visible before tag completion");

  task automatic issue(input [7:0] cmd,input [15:0] txid,input [15:0] len,input [527:0] payload,input [31:0] fp);
    begin
      @(negedge clk); request_command=cmd;request_txid=txid;request_length=len;request_payload=payload;request_fingerprint=fp;request_valid=1;
      @(negedge clk); request_valid=0;
      cycles=0; while(!response_commit && cycles<20)begin @(negedge clk);cycles=cycles+1;end
      if(!response_commit)$fatal(1,"no response cmd %02x",cmd);
      if(response_command!=cmd || response_txid!=txid)$fatal(1,"response identity mismatch");
      @(negedge clk);
    end
  endtask
  task automatic expect_ok; begin if(response_flags!=(FLAG_RESPONSE))$fatal(1,"expected success flags=%02x",response_flags);end endtask
  task automatic expect_error(input [15:0] code); begin
    if((response_flags&(FLAG_RESPONSE|FLAG_ERROR))!=(FLAG_RESPONSE|FLAG_ERROR))$fatal(1,"expected error");
    if({response_payload[7:0],response_payload[15:8]}!=code)$fatal(1,"error code mismatch got %04x",{response_payload[7:0],response_payload[15:8]});
  end endtask
  task automatic retire(input [15:0] original,input [15:0] txid); begin p='0;p[7:0]=original[15:8];p[15:8]=original[7:0];issue(CMD_RETIRE_TXN_RESULT,txid,2,p,32'h90000000|txid);expect_ok();end endtask
  task automatic stage(input [15:0] txid); begin
    p='0;p[7:0]=8'h11;p[15:8]=8'h22;p[23:16]=8'h33;p[31:24]=8'h44;
    for(i=0;i<16;i=i+1)p[8*(4+i)+:8]=i[7:0]*8'h11;
    p[8*20+:8]=8'h10;p[8*21+:8]=8'h21;p[8*22+:8]=8'h32;p[8*23+:8]=8'h43;
    p[8*24+:8]=8'h54;p[8*25+:8]=8'h65;p[8*26+:8]=8'h76;p[8*27+:8]=8'h87;
    issue(CMD_STAGE_SESSION,txid,28,p,32'h71000000|txid);expect_ok();
  end endtask
  task automatic commit(input [15:0] txid);begin p='0;p[7:0]=8'h11;p[15:8]=8'h22;p[23:16]=8'h33;p[31:24]=8'h44;issue(CMD_COMMIT_SESSION,txid,4,p,32'h72000000|txid);expect_ok();end endtask
  task automatic inject(input [511:0] body);begin @(negedge clk);frame_body=body;frame_valid=1;@(negedge clk);frame_valid=0;end endtask
  task automatic wait_auth;begin cycles=0;while(!auth_pending&&cycles<200)begin @(posedge clk);cycles=cycles+1;end if(!auth_pending)$fatal(1,"authentication timeout");end endtask
  task automatic ack_current(input [63:0] seq,input [15:0] txid);begin p='0;p[7:0]=8'h11;p[15:8]=8'h22;p[23:16]=8'h33;p[31:24]=8'h44;for(i=0;i<8;i=i+1)p[8*(4+i)+:8]=seq[63-8*i-:8];issue(CMD_ACK_AUTH_RESULT,txid,12,p,32'h73000000|txid);expect_ok();end endtask

  initial begin
    repeat(4)@(posedge clk);rst_n=1;repeat(3)@(posedge clk);
    if(session_state!=SESSION_SELF_TEST_REQUIRED || auth_pending || fault)$fatal(1,"reset state invalid");
    $display("PASS reset_idle_fail_closed");
    p='0;issue(CMD_GET_INFO,16'h0101,0,p,32'h1);expect_ok();if(response_payload[7:0]!=TARGET_PRIMER2)$fatal(1,"target id");
    $display("PASS get_info");
    issue(CMD_GET_STATUS,16'h0102,0,p,32'h2);expect_ok();
    issue(CMD_READ_AUTH_RESULT,16'h0103,0,p,32'h3);expect_error(ERR_RESULT_NOT_READY);
    $display("PASS no_plaintext_before_authentication");

    p='0;p[7:0]=8'h03;p[15:8]=8'hE3;issue(CMD_RUN_SELF_TEST,16'h0200,4,p,32'h200);expect_ok();
    issue(CMD_RUN_SELF_TEST,16'h0200,4,p,32'h200);expect_ok();
    issue(CMD_RUN_SELF_TEST,16'h0200,4,p,32'h201);expect_error(ERR_TRANSACTION_CONFLICT);
    $display("PASS retained_duplicate_retry_and_conflict");
    cycles=0;while(dut.retained_state!=TXN_SUCCEEDED&&cycles<200)begin @(posedge clk);cycles=cycles+1;end
    if(dut.retained_state!=TXN_SUCCEEDED || session_state!=SESSION_READY_NO_SESSION)$fatal(1,"selftest failed");
    p='0;p[7:0]=8'h02;p[15:8]=8'h00;issue(CMD_GET_TXN_RESULT,16'h0201,2,p,32'h201);expect_ok();
    retire(16'h0200,16'h0202); $display("PASS self_test_retained_result");

    stage(16'h0300);commit(16'h0301);retire(16'h0301,16'h0302);
    if(session_state!=SESSION_COMMITTED_BLOCKED || rx_enable)$fatal(1,"commit-blocked state");
    secure=1;repeat(3)@(posedge clk);if(session_state!=SESSION_ACTIVE||!rx_enable)$fatal(1,"activate failed");
    $display("PASS stage_commit_activate");

    frame_body=BODY1; frame_body[8*4]=~frame_body[8*4]; inject(frame_body); repeat(12)@(posedge clk);
    if(auth_pending || dut.last_error!=ERR_BAD_SESSION || dut.last_accepted_sequence!=0)
      $fatal(1,"wrong-session frame was accepted");
    $display("PASS wrong_session_frame_rejected");

    inject(BODY1);wait_auth();if(dut.auth_result_plaintext!==EXPECTED_PT)$fatal(1,"auth plaintext");
    repeat(2) @(posedge clk);
    if (dut.u_decrypt.k0 != 0 || dut.u_decrypt.k1 != 0 ||
        dut.u_decrypt.ad_reg != 0 || dut.u_decrypt.ct_reg != 0 ||
        dut.u_decrypt.tag_reg != 0 || dut.u_decrypt.x0 != 0 ||
        dut.u_decrypt.x1 != 0 || dut.u_decrypt.x2 != 0 ||
        dut.u_decrypt.x3 != 0 || dut.u_decrypt.x4 != 0 ||
        dut.u_decrypt.plaintext_o != 0)
      $fatal(1,"decrypt datapath retained secret state after authentication");
    if (!auth_pending || dut.auth_result_plaintext !== EXPECTED_PT)
      $fatal(1,"authenticated result was lost while decrypt datapath was scrubbed");
    $display("PASS decrypt_datapath_scrubbed_after_result_retention");
    issue(CMD_READ_AUTH_RESULT,16'h0400,0,'0,32'h400);expect_ok();
    if(response_length!=38 || response_payload[8*12+:192]!==EXPECTED_PT)$fatal(1,"read result payload");
    p='0;p[7:0]=8'h11;p[15:8]=8'h22;p[23:16]=8'h33;p[31:24]=8'h45;issue(CMD_ACK_AUTH_RESULT,16'h0401,12,p,32'h401);expect_error(ERR_BAD_SESSION);
    ack_current(64'd1,16'h0402);if(auth_pending)$fatal(1,"ACK did not clear result");
    ack_current(64'd1,16'h0403);$display("PASS authenticated_result_read_ack_idempotent");

    inject(BODY1);repeat(100)@(posedge clk);if(auth_pending||dut.last_error!=ERR_REPLAY)$fatal(1,"replay accepted");
    $display("PASS replay_rejected_without_sequence_commit");
    frame_body=BODY2;frame_body[384]=~frame_body[384];inject(frame_body);repeat(100)@(posedge clk);
    if(auth_pending||dut.consecutive_bad_tags!=1||dut.last_accepted_sequence!=1)$fatal(1,"bad tag handling");
    $display("PASS tag_flip_no_result_no_sequence_advance");
    frame_body=BODY1;frame_body[8*8+:64]=64'd0;inject(frame_body);repeat(10)@(posedge clk);
    if(auth_pending||dut.last_error!=ERR_STALE_SEQUENCE)$fatal(1,"zero sequence accepted");
    $display("PASS zero_sequence_rejected");
    frame_body=BODY2;frame_body[8+:8]=8'h03;inject(frame_body);repeat(10)@(posedge clk);
    if(auth_pending||dut.last_error!=ERR_MALFORMED_FRAME)$fatal(1,"wrong AD message type accepted");
    $display("PASS wrong_ad_message_type_rejected");
    inject(BODY4);repeat(10)@(posedge clk);
    if(auth_pending||dut.last_error!=ERR_STALE_SEQUENCE)$fatal(1,"forward sequence gap accepted");
    $display("PASS forward_sequence_gap_rejected");

    inject(BODY2);wait_auth();
    frame_body=BODY3; @(negedge clk);frame_valid=1;@(negedge clk);frame_valid=0;repeat(8)@(posedge clk);
    if(!auth_pending || dut.auth_result_sequence!=2 || dut.auth_result_plaintext!==EXPECTED_PT)
      $fatal(1,"pending authenticated result was overwritten");
    @(negedge clk);frame_drop=1;@(negedge clk);frame_drop=0;
    if(dut.diag_result_pending_drop_count==0)$fatal(1,"pending drop not counted");
    $display("PASS pending_result_not_overwritten");
    ack_current(64'd2,16'h0500);$display("PASS next_frame_and_pending_protection");
    inject(BODY1);repeat(12)@(posedge clk);
    if(auth_pending||dut.last_error!=ERR_STALE_SEQUENCE||dut.last_accepted_sequence!=2)
      $fatal(1,"stale lower sequence accepted");
    $display("PASS stale_sequence_rejected");

    inject(BODY3);repeat(5)@(posedge clk);p='0;p[7:0]=8'h11;p[15:8]=8'h22;p[23:16]=8'h33;p[31:24]=8'h44;
    issue(CMD_ABORT_SESSION,16'h0600,4,p,32'h600);expect_ok();repeat(100)@(posedge clk);
    if(auth_pending||session_state!=SESSION_READY_NO_SESSION||dut.active_key!=0)$fatal(1,"abort during decrypt failed");
    $display("PASS abort_during_decrypt_zeroizes_candidate");

    secure=0;stage(16'h0610);commit(16'h0611);retire(16'h0611,16'h0612);secure=1;repeat(3)@(posedge clk);inject(BODY1);repeat(5)@(posedge clk);
    p='0;p[7:0]=ZEROIZE_ALL;issue(CMD_ZEROIZE,16'h0620,4,p,32'h620);expect_ok();
    cycles=0;while(session_state==SESSION_ZEROIZE_BUSY&&cycles<100)begin @(posedge clk);cycles=cycles+1;end
    if(session_state!=SESSION_READY_NO_SESSION||auth_pending||dut.active_key!=0||dut.decrypt_ciphertext!=0)$fatal(1,"zeroize failed");
    if(dut.retained_state!=TXN_ZEROIZED)$fatal(1,"zeroize retained state missing");
    $display("PASS zeroize_all_during_decrypt");

    retire(16'h0620,16'h0621);secure=0;stage(16'h0630);commit(16'h0631);retire(16'h0631,16'h0632);secure=1;repeat(3)@(posedge clk);secure=0;
    cycles=0;while(session_state!=SESSION_SELF_TEST_REQUIRED&&cycles<100)begin @(posedge clk);cycles=cycles+1;end
    if(session_state!=SESSION_SELF_TEST_REQUIRED||dut.active_key!=0||auth_pending)$fatal(1,"secure drop not fail closed");
    $display("PASS secure_enable_drop_requires_new_selftest_session");

    rst_n=0;repeat(2)@(posedge clk);rst_n=1;repeat(2)@(posedge clk);fatal=1;repeat(2)@(posedge clk);fatal=0;
    cycles=0;while(session_state!=SESSION_FAULT_LOCKED&&cycles<100)begin @(posedge clk);cycles=cycles+1;end
    if(!fault||session_state!=SESSION_FAULT_LOCKED||dut.active_key!=0)$fatal(1,"fatal latch fail closed");
    $display("PASS fatal_latch_fault_locked");
    $finish;
  end
endmodule
