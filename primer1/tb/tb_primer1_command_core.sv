`timescale 1ns/1ps

module tb_primer1_command_core;
  import trinity_spi_pkg::*;

  logic clk = 0;
  logic rst_n = 0;
  logic secure_enable = 0;
  logic zeroize_n = 1;
  logic fatal_latched = 0;
  logic request_valid = 0;
  logic [7:0] request_command = 0;
  logic [7:0] request_flags = 0;
  logic [15:0] request_txid = 0;
  logic [15:0] request_payload_length = 0;
  logic [527:0] request_payload = 0;
  logic [31:0] request_fingerprint = 32'h12345678;
  logic transport_error_valid = 0;
  logic [7:0] transport_error_command = 0;
  logic [15:0] transport_error_txid = 0;
  logic [15:0] transport_error_code = 0;
  logic response_commit;
  logic [7:0] response_command;
  logic [7:0] response_flags;
  logic [15:0] response_txid;
  logic [15:0] response_payload_length;
  logic [527:0] response_payload;
  logic response_ready = 1;
  logic mailbox_pending = 0;
  logic retained_pending;
  logic event_pending;
  logic uart_tx;
  logic heartbeat;
  logic fault;
  logic [3:0] session_state;
  logic [2:0] operation_state;

  integer failures = 0;
  integer timeout;

  always #5 clk = ~clk;

  primer1_command_core #(.CLOCK_HZ(100), .UART_BAUD(10)) dut (
      .clk_i(clk), .rst_ni(rst_n),
      .secure_enable_i(secure_enable), .zeroize_ni(zeroize_n),
      .fatal_latched_i(fatal_latched),
      .request_valid_i(request_valid), .request_command_i(request_command),
      .request_flags_i(request_flags), .request_txid_i(request_txid),
      .request_payload_length_i(request_payload_length),
      .request_payload_i(request_payload),
      .request_fingerprint_i(request_fingerprint),
      .transport_error_valid_i(transport_error_valid),
      .transport_error_command_i(transport_error_command),
      .transport_error_txid_i(transport_error_txid),
      .transport_error_code_i(transport_error_code),
      .response_commit_o(response_commit),
      .response_command_o(response_command),
      .response_flags_o(response_flags),
      .response_txid_o(response_txid),
      .response_payload_length_o(response_payload_length),
      .response_payload_o(response_payload),
      .response_ready_i(response_ready),
      .mailbox_pending_i(mailbox_pending),
      .retained_result_pending_o(retained_pending),
      .irq_event_pending_o(event_pending),
      .uart_tx_o(uart_tx), .heartbeat_o(heartbeat), .fault_o(fault),
      .session_state_o(session_state), .operation_state_o(operation_state)
  );

  task automatic reset_dut;
    begin
      rst_n = 0;
      secure_enable = 0;
      zeroize_n = 1;
      fatal_latched = 0;
      request_valid = 0;
      request_command = 0;
      request_txid = 0;
      request_payload_length = 0;
      request_payload = 0;
      request_fingerprint = 32'h12345678;
      repeat (4) @(posedge clk);
      rst_n = 1;
      repeat (3) @(posedge clk);
    end
  endtask

  task automatic issue_request(
      input logic [7:0] command,
      input logic [15:0] txid,
      input logic [15:0] length,
      input logic [527:0] payload
  );
    begin
      @(negedge clk);
      request_command = command;
      request_txid = txid;
      request_payload_length = length;
      request_payload = payload;
      request_fingerprint = request_fingerprint + 32'h01010101;
      request_valid = 1;
      @(negedge clk);
      request_valid = 0;
    end
  endtask

  task automatic wait_response(input integer cycles, output integer seen);
    begin
      seen = 0;
      timeout = 0;
      while (!response_commit && timeout < cycles) begin
        @(posedge clk);
        #1;
        timeout = timeout + 1;
      end
      if (response_commit) seen = 1;
    end
  endtask

  task automatic expect_error(input logic [15:0] code, input string name);
    integer seen;
    logic [15:0] observed;
    begin
      wait_response(60, seen);
      if (!seen) begin
        $display("FAIL %s: no response", name);
        failures = failures + 1;
      end else begin
        observed = {response_payload[7:0], response_payload[15:8]};
        if ((response_flags & FLAG_ERROR) == 0 || observed != code) begin
          $display("FAIL %s: flags=%h code=%h expected=%h",
                   name, response_flags, observed, code);
          failures = failures + 1;
        end else begin
          $display("PASS %s", name);
        end
      end
      @(posedge clk);
      #1;
    end
  endtask

  task automatic start_ascon_selftest(input logic [15:0] txid);
    logic [527:0] payload;
    integer seen;
    begin
      payload = '0;
      payload[7:0] = TEST_ASCON[15:8];
      payload[15:8] = TEST_ASCON[7:0];
      issue_request(CMD_RUN_SELF_TEST, txid, 16'd4, payload);
      wait_response(60, seen);
      if (!seen || (response_flags & FLAG_ERROR)) begin
        $display("FAIL selftest_start_for_busy_query");
        failures = failures + 1;
      end
      @(posedge clk);
      #1;
    end
  endtask

  task automatic test_busy_get_status;
    integer seen;
    begin
      reset_dut();
      start_ascon_selftest(16'h3344);
      issue_request(CMD_GET_STATUS, 16'h0101, 0, '0);
      wait_response(60, seen);
      if (!seen || response_command != CMD_GET_STATUS ||
          response_payload[15:8] != OP_EXECUTING) begin
        $display("FAIL busy_get_status_not_lost");
        failures = failures + 1;
      end else begin
        $display("PASS busy_get_status_not_lost");
      end
    end
  endtask

  task automatic test_busy_get_txn_result;
    integer seen;
    logic [527:0] payload;
    begin
      reset_dut();
      start_ascon_selftest(16'h3344);
      payload = '0;
      payload[7:0] = 8'h33;
      payload[15:8] = 8'h44;
      issue_request(CMD_GET_TXN_RESULT, 16'h0102, 16'd2, payload);
      wait_response(60, seen);
      if (!seen || response_command != CMD_GET_TXN_RESULT ||
          response_payload[23:16] != TXN_RUNNING) begin
        $display("FAIL busy_get_txn_result_not_lost");
        failures = failures + 1;
      end else begin
        $display("PASS busy_get_txn_result_not_lost");
      end
    end
  endtask

  task automatic test_selftest_mask;
    integer seen;
    logic [527:0] payload;
    begin
      reset_dut();
      payload = '0;
      payload[7:0] = TEST_ASCON[15:8];
      payload[15:8] = TEST_ASCON[7:0];
      issue_request(CMD_RUN_SELF_TEST, 16'h0201, 16'd4, payload);
      wait_response(60, seen);
      if (!seen || (response_flags & FLAG_ERROR)) begin
        $display("FAIL selftest_mask_accept_supported_subset");
        failures = failures + 1;
      end
      timeout = 0;
      while (dut.retained_state == TXN_RUNNING && timeout < 30000) begin
        @(posedge clk);
        #1;
        timeout = timeout + 1;
      end
      repeat (3) begin @(posedge clk); #1; end
      if (dut.retained_state != TXN_SUCCEEDED ||
          dut.retained_data_length != 16'd2 ||
          dut.retained_data[7:0] != TEST_ASCON[15:8] ||
          dut.retained_data[15:8] != TEST_ASCON[7:0]) begin
        $display("FAIL run_self_test_honors_test_mask: state=%0d len=%0d data=%h",
                 dut.retained_state, dut.retained_data_length,
                 dut.retained_data[15:0]);
        failures = failures + 1;
      end else begin
        $display("PASS run_self_test_honors_test_mask");
      end
    end
  endtask

  task automatic test_zeroize_scope;
    integer seen;
    logic [527:0] payload;
    begin
      reset_dut();
      payload = '0;
      payload[7:0] = ZEROIZE_ACTIVE_SESSION;
      issue_request(CMD_ZEROIZE, 16'h0301, 16'd4, payload);
      expect_error(ERR_NOT_SUPPORTED, "zeroize_partial_scope_rejected");

      reset_dut();
      payload = '0;
      payload[7:0] = ZEROIZE_ALL;
      issue_request(CMD_ZEROIZE, 16'h0302, 16'd4, payload);
      wait_response(60, seen);
      if (!seen || (response_flags & FLAG_ERROR)) begin
        $display("FAIL zeroize_all_accepted");
        failures = failures + 1;
      end else begin
        $display("PASS zeroize_all_accepted");
      end
    end
  endtask

  task automatic initialize_staged_session;
    begin
      dut.self_test_pass = 1'b1;
      dut.session_state = SESSION_STAGED;
      dut.staged_valid = 1'b1;
      dut.staged_session_id = 32'h11223344;
      dut.staged_key = 128'h0123456789abcdef0123456789abcdef;
      dut.staged_nonce_prefix = 64'h1020304050607080;
    end
  endtask

  task automatic test_abort_session_id;
    integer seen;
    logic [527:0] payload;
    begin
      reset_dut();
      initialize_staged_session();
      payload = '0;
      payload[7:0] = 8'h55;
      payload[15:8] = 8'h66;
      payload[23:16] = 8'h77;
      payload[31:24] = 8'h88;
      issue_request(CMD_ABORT_SESSION, 16'h0401, 16'd4, payload);
      expect_error(ERR_BAD_SESSION, "abort_session_wrong_id_rejected");
      if (!dut.staged_valid || dut.staged_session_id != 32'h11223344) begin
        $display("FAIL abort_session_wrong_id_preserves_context");
        failures = failures + 1;
      end else begin
        $display("PASS abort_session_wrong_id_preserves_context");
      end

      reset_dut();
      initialize_staged_session();
      payload = '0;
      payload[7:0] = 8'h11;
      payload[15:8] = 8'h22;
      payload[23:16] = 8'h33;
      payload[31:24] = 8'h44;
      issue_request(CMD_ABORT_SESSION, 16'h0402, 16'd4, payload);
      wait_response(60, seen);
      if (!seen || (response_flags & FLAG_ERROR) || dut.staged_valid) begin
        $display("FAIL abort_session_matching_id_succeeds");
        failures = failures + 1;
      end else begin
        $display("PASS abort_session_matching_id_succeeds");
      end
    end
  endtask

  task automatic test_poly_result_guard;
    logic [527:0] payload;
    begin
      reset_dut();
      dut.operation_state = OP_RESULT_READY;
      payload = '0;
      payload[7:0] = 8'd1;
      payload[15:8] = 8'd1;
      payload[23:16] = 8'd8;
      payload[31:24] = 8'd0;
      issue_request(CMD_POLY_BEGIN, 16'h0501, 16'd4, payload);
      expect_error(ERR_RESULT_PENDING, "poly_begin_rejects_unretired_result");
      if (dut.operation_state != OP_RESULT_READY) begin
        $display("FAIL poly_begin_preserves_result_ready");
        failures = failures + 1;
      end else begin
        $display("PASS poly_begin_preserves_result_ready");
      end
    end
  endtask

  initial begin
    test_busy_get_status();
    test_busy_get_txn_result();
    test_selftest_mask();
    test_zeroize_scope();
    test_abort_session_id();
    test_poly_result_guard();

    if (failures != 0)
      $fatal(1, "primer1_command_core findings failures=%0d", failures);
    $display("PASS primer1_command_core_all_five_findings");
    $finish;
  end
endmodule
