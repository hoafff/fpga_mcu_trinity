`timescale 1ns/1ps
module tb_bad_tag_threshold;
  import trinity_spi_pkg::*;

  logic clk = 1'b0;
  logic rst_n = 1'b0;
  logic secure = 1'b0;
  logic zeroize_n = 1'b1;
  logic fatal = 1'b0;

  logic request_valid = 1'b0;
  logic [7:0] request_command = 8'd0;
  logic [7:0] request_flags = 8'd0;
  logic [15:0] request_txid = 16'd0;
  logic [15:0] request_length = 16'd0;
  logic [527:0] request_payload = '0;
  logic [31:0] request_fingerprint = 32'd0;

  logic transport_error = 1'b0;
  logic [7:0] transport_command = 8'd0;
  logic [15:0] transport_txid = 16'd0;
  logic [15:0] transport_code = 16'd0;

  logic response_commit;
  logic [7:0] response_command;
  logic [7:0] response_flags;
  logic [15:0] response_txid;
  logic [15:0] response_length;
  logic [527:0] response_payload;
  logic response_ready = 1'b1;
  logic mailbox_pending = 1'b0;

  logic frame_valid = 1'b0;
  logic [511:0] frame_body = '0;
  logic frame_timeout = 1'b0;
  logic frame_error = 1'b0;
  logic frame_drop = 1'b0;
  logic frame_blocked = 1'b0;
  logic [2:0] frame_rx_state = RX_HUNT_SYNC;

  logic rx_enable;
  logic result_pending;
  logic retained_pending;
  logic auth_pending;
  logic event_pending;
  logic heartbeat;
  logic fault;
  logic [3:0] session_state;
  logic [2:0] operation_state;
  logic [2:0] rx_state;

  logic [527:0] payload;
  logic [511:0] bad_body2;
  integer i;
  integer cycles;

  localparam logic [511:0] BODY1 =
      512'h1A9061D8C0929EA8374B85ED37AF716530CCB278A33B70139B376D8290C255B8D1357E03280E320C000000004433180001000000000000004433221134120201;
  localparam logic [511:0] BODY2 =
      512'h173FAEC87E4F794FB7D585F0C18AFF7257539185E37CA985AB55C616547EE8C5EAF9A65B11B158C7000000004433180002000000000000004433221134120201;

  always #5 clk = ~clk;

  primer2_command_core #(
      .CLOCK_HZ(1000),
      .BAD_TAG_THRESHOLD(3)
  ) dut (
      .clk_i(clk),
      .rst_ni(rst_n),
      .secure_enable_i(secure),
      .zeroize_ni(zeroize_n),
      .fatal_latched_i(fatal),
      .request_valid_i(request_valid),
      .request_command_i(request_command),
      .request_flags_i(request_flags),
      .request_txid_i(request_txid),
      .request_payload_length_i(request_length),
      .request_payload_i(request_payload),
      .request_fingerprint_i(request_fingerprint),
      .transport_error_valid_i(transport_error),
      .transport_error_command_i(transport_command),
      .transport_error_txid_i(transport_txid),
      .transport_error_code_i(transport_code),
      .response_commit_o(response_commit),
      .response_command_o(response_command),
      .response_flags_o(response_flags),
      .response_txid_o(response_txid),
      .response_payload_length_o(response_length),
      .response_payload_o(response_payload),
      .response_ready_i(response_ready),
      .mailbox_pending_i(mailbox_pending),
      .frame_valid_i(frame_valid),
      .frame_body_i(frame_body),
      .frame_timeout_i(frame_timeout),
      .frame_framing_error_i(frame_error),
      .frame_pending_drop_i(frame_drop),
      .frame_blocked_i(frame_blocked),
      .frame_rx_state_i(frame_rx_state),
      .rx_accept_enable_o(rx_enable),
      .result_pending_o(result_pending),
      .retained_result_pending_o(retained_pending),
      .authenticated_result_pending_o(auth_pending),
      .irq_event_pending_o(event_pending),
      .heartbeat_o(heartbeat),
      .fault_o(fault),
      .session_state_o(session_state),
      .operation_state_o(operation_state),
      .rx_state_o(rx_state)
  );

  task automatic issue(
      input logic [7:0] command,
      input logic [15:0] txid,
      input logic [15:0] length,
      input logic [527:0] data,
      input logic [31:0] fingerprint
  );
    begin
      @(negedge clk);
      request_command = command;
      request_txid = txid;
      request_length = length;
      request_payload = data;
      request_fingerprint = fingerprint;
      request_valid = 1'b1;
      @(negedge clk);
      request_valid = 1'b0;
      cycles = 0;
      while (!response_commit && cycles < 30) begin
        @(negedge clk);
        cycles = cycles + 1;
      end
      if (!response_commit)
        $fatal(1, "no response for command %02x", command);
      if (response_command != command || response_txid != txid)
        $fatal(1, "response identity mismatch");
      if (response_flags != FLAG_RESPONSE)
        $fatal(1, "command %02x returned error flags %02x", command, response_flags);
      @(negedge clk);
    end
  endtask

  task automatic retire(input logic [15:0] original_txid,
                        input logic [15:0] txid);
    begin
      payload = '0;
      payload[7:0] = original_txid[15:8];
      payload[15:8] = original_txid[7:0];
      issue(CMD_RETIRE_TXN_RESULT, txid, 16'd2, payload,
            32'h9000_0000 | txid);
    end
  endtask

  task automatic stage_session(input logic [15:0] txid);
    begin
      payload = '0;
      payload[7:0] = 8'h11;
      payload[15:8] = 8'h22;
      payload[23:16] = 8'h33;
      payload[31:24] = 8'h44;
      for (i = 0; i < 16; i = i + 1)
        payload[8*(4+i) +: 8] = i[7:0] * 8'h11;
      payload[8*20 +: 8] = 8'h10;
      payload[8*21 +: 8] = 8'h21;
      payload[8*22 +: 8] = 8'h32;
      payload[8*23 +: 8] = 8'h43;
      payload[8*24 +: 8] = 8'h54;
      payload[8*25 +: 8] = 8'h65;
      payload[8*26 +: 8] = 8'h76;
      payload[8*27 +: 8] = 8'h87;
      issue(CMD_STAGE_SESSION, txid, 16'd28, payload,
            32'h7100_0000 | txid);
    end
  endtask

  task automatic commit_session(input logic [15:0] txid);
    begin
      payload = '0;
      payload[7:0] = 8'h11;
      payload[15:8] = 8'h22;
      payload[23:16] = 8'h33;
      payload[31:24] = 8'h44;
      issue(CMD_COMMIT_SESSION, txid, 16'd4, payload,
            32'h7200_0000 | txid);
    end
  endtask

  task automatic inject(input logic [511:0] body);
    begin
      @(negedge clk);
      frame_body = body;
      frame_valid = 1'b1;
      @(negedge clk);
      frame_valid = 1'b0;
    end
  endtask

  task automatic wait_auth;
    begin
      cycles = 0;
      while (!auth_pending && cycles < 250) begin
        @(posedge clk);
        cycles = cycles + 1;
      end
      if (!auth_pending)
        $fatal(1, "authenticated result timeout");
    end
  endtask

  task automatic ack_sequence(input logic [63:0] sequence_value,
                              input logic [15:0] txid);
    begin
      payload = '0;
      payload[7:0] = 8'h11;
      payload[15:8] = 8'h22;
      payload[23:16] = 8'h33;
      payload[31:24] = 8'h44;
      for (i = 0; i < 8; i = i + 1)
        payload[8*(4+i) +: 8] = sequence_value[63-8*i -: 8];
      issue(CMD_ACK_AUTH_RESULT, txid, 16'd12, payload,
            32'h7300_0000 | txid);
    end
  endtask

  task automatic inject_bad_tag_and_wait(input integer expected_count);
    begin
      inject(bad_body2);
      cycles = 0;
      while (dut.core_state != 3'd0 && cycles < 300) begin
        @(posedge clk);
        cycles = cycles + 1;
      end
      repeat (3) @(posedge clk);
      if (auth_pending)
        $fatal(1, "bad-tag frame exposed authenticated plaintext");
      if (expected_count < 3 && dut.consecutive_bad_tags != expected_count)
        $fatal(1, "bad-tag count mismatch: got %0d expected %0d",
               dut.consecutive_bad_tags, expected_count);
    end
  endtask

  initial begin
    repeat (4) @(posedge clk);
    rst_n = 1'b1;
    repeat (3) @(posedge clk);

    payload = '0;
    payload[7:0] = 8'h03;
    payload[15:8] = 8'hE3;
    issue(CMD_RUN_SELF_TEST, 16'h1000, 16'd4, payload, 32'h1000_1000);
    cycles = 0;
    while (dut.retained_state != TXN_SUCCEEDED && cycles < 250) begin
      @(posedge clk);
      cycles = cycles + 1;
    end
    if (dut.retained_state != TXN_SUCCEEDED ||
        session_state != SESSION_READY_NO_SESSION)
      $fatal(1, "self-test did not unlock session staging");
    retire(16'h1000, 16'h1001);

    stage_session(16'h1100);
    commit_session(16'h1101);
    retire(16'h1101, 16'h1102);
    if (session_state != SESSION_COMMITTED_BLOCKED || rx_enable)
      $fatal(1, "session did not enter committed-blocked state");

    secure = 1'b1;
    repeat (3) @(posedge clk);
    if (session_state != SESSION_ACTIVE || !rx_enable)
      $fatal(1, "session did not activate");

    inject(BODY1);
    wait_auth();
    ack_sequence(64'd1, 16'h1200);
    if (auth_pending || dut.last_accepted_sequence != 64'd1)
      $fatal(1, "valid baseline frame was not committed and acknowledged");

    bad_body2 = BODY2;
    bad_body2[384] = ~bad_body2[384];

    inject_bad_tag_and_wait(1);
    if (fault || session_state != SESSION_ACTIVE)
      $fatal(1, "fault asserted before threshold");

    inject_bad_tag_and_wait(2);
    if (fault || session_state != SESSION_ACTIVE)
      $fatal(1, "fault asserted before third bad tag");

    inject(bad_body2);
    cycles = 0;
    while (session_state != SESSION_FAULT_LOCKED && cycles < 400) begin
      @(posedge clk);
      cycles = cycles + 1;
    end

    if (!fault || session_state != SESSION_FAULT_LOCKED)
      $fatal(1, "three consecutive bad tags did not latch fault");
    if (auth_pending || dut.active_key != 128'd0 ||
        dut.active_nonce_prefix != 64'd0 || dut.active_valid)
      $fatal(1, "bad-tag threshold did not zeroize session/result state");
    if (dut.diag_bad_tag_count != 16'd3 || dut.diag_fault_count == 16'd0)
      $fatal(1, "bad-tag/fault diagnostics were not retained");

    $display("PASS three_consecutive_bad_tags_fault_and_zeroize");
    $finish;
  end
endmodule
