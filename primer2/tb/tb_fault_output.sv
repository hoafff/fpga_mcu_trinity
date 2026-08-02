`timescale 1ns/1ps
module tb_fault_output;
  import trinity_spi_pkg::*;

  logic clk_i = 1'b0;
  logic rst_ni = 1'b0;
  logic secure_enable_i = 1'b0;
  logic zeroize_ni = 1'b1;
  logic fatal_latched_i = 1'b0;
  logic request_valid_i = 1'b0;
  logic [7:0] request_command_i = '0;
  logic [7:0] request_flags_i = '0;
  logic [15:0] request_txid_i = '0;
  logic [15:0] request_payload_length_i = '0;
  logic [527:0] request_payload_i = '0;
  logic [31:0] request_fingerprint_i = '0;
  logic transport_error_valid_i = 1'b0;
  logic [7:0] transport_error_command_i = '0;
  logic [15:0] transport_error_txid_i = '0;
  logic [15:0] transport_error_code_i = '0;
  logic response_ready_i = 1'b1;
  logic mailbox_pending_i = 1'b0;
  logic frame_valid_i = 1'b0;
  logic [511:0] frame_body_i = '0;
  logic frame_timeout_i = 1'b0;
  logic frame_framing_error_i = 1'b0;
  logic frame_pending_drop_i = 1'b0;
  logic frame_blocked_i = 1'b0;
  logic [2:0] frame_rx_state_i = RX_HUNT_SYNC;

  logic response_commit_o;
  logic [7:0] response_command_o;
  logic [7:0] response_flags_o;
  logic [15:0] response_txid_o;
  logic [15:0] response_payload_length_o;
  logic [527:0] response_payload_o;
  logic rx_accept_enable_o;
  logic result_pending_o;
  logic retained_result_pending_o;
  logic authenticated_result_pending_o;
  logic irq_event_pending_o;
  logic heartbeat_o;
  logic fault_o;
  logic [3:0] session_state_o;
  logic [2:0] operation_state_o;
  logic [2:0] rx_state_o;

  integer cycles;

  always #5 clk_i = ~clk_i;

  primer2_command_core #(.CLOCK_HZ(1000)) dut (.*);

  task automatic expect_known_fault(input logic expected,
                                    input string context);
    begin
      #1;
      if ($isunknown(fault_o))
        $fatal(1, "fault_o unknown during %s", context);
      if (fault_o !== expected)
        $fatal(1, "fault_o=%b expected=%b during %s",
               fault_o, expected, context);
    end
  endtask

  initial begin
    repeat (3) @(posedge clk_i);
    expect_known_fault(1'b0, "reset asserted");
    if (rx_accept_enable_o !== 1'b0)
      $fatal(1, "receiver enabled during reset");
    $display("PASS reset_fault_output_deterministic");

    rst_ni = 1'b1;
    repeat (3) @(posedge clk_i);
    expect_known_fault(1'b0, "normal fail-closed idle");
    if (session_state_o != SESSION_SELF_TEST_REQUIRED ||
        rx_accept_enable_o !== 1'b0)
      $fatal(1, "normal reset-idle state mismatch");
    $display("PASS normal_idle_fault_output_clear");

    @(negedge clk_i);
    fatal_latched_i = 1'b1;
    @(posedge clk_i);
    expect_known_fault(1'b1, "external fatal assertion");
    if (!dut.fault_latched || dut.core_state != 3'd4)
      $fatal(1, "external fatal did not latch fault and start zeroize");
    $display("PASS external_fatal_asserts_fault_and_zeroize");

    @(negedge clk_i);
    fatal_latched_i = 1'b0;
    cycles = 0;
    while (session_state_o != SESSION_FAULT_LOCKED && cycles < 100) begin
      @(posedge clk_i);
      cycles = cycles + 1;
    end
    if (session_state_o != SESSION_FAULT_LOCKED)
      $fatal(1, "fault zeroize did not finish in FAULT_LOCKED");
    expect_known_fault(1'b1, "fatal input removed after fault latch");
    if (dut.active_key != 0 || dut.staged_key != 0 || dut.active_valid ||
        dut.staged_valid || result_pending_o || rx_accept_enable_o)
      $fatal(1, "fault lifecycle did not remain zeroized and fail-closed");
    $display("PASS fault_persists_after_external_fatal_removed");

    zeroize_ni = 1'b0;
    repeat (4) @(posedge clk_i);
    expect_known_fault(1'b1, "zeroize input while fault locked");
    if (session_state_o != SESSION_FAULT_LOCKED)
      $fatal(1, "zeroize input illegally cleared FAULT_LOCKED");
    zeroize_ni = 1'b1;
    repeat (4) @(posedge clk_i);
    expect_known_fault(1'b1, "zeroize released while fault locked");
    $display("PASS zeroize_does_not_clear_latched_fault");

    rst_ni = 1'b0;
    #1;
    expect_known_fault(1'b0, "trusted reset clears fault lifecycle");
    if (session_state_o != SESSION_SELF_TEST_REQUIRED || dut.fault_latched)
      $fatal(1, "reset did not restore SELF_TEST_REQUIRED and clear fault latch");
    $display("PASS reset_clears_fault_and_requires_selftest");

    $finish;
  end
endmodule
