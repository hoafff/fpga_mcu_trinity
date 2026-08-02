`timescale 1ns/1ps

module tb_primer1_top;
  logic clk = 0;
  logic rst_n = 0;
  logic spi_sck = 0;
  logic spi_mosi = 0;
  wire spi_miso;
  logic spi_cs_n = 1;
  logic irq_n;
  logic uart_tx;
  logic fault;
  logic fatal_latched = 0;
  logic secure_enable = 0;
  logic zeroize_n = 1;
  logic heartbeat;
  logic previous_heartbeat;

  always #5 clk = ~clk;

  primer1_top dut (
      .sys_clk_i(clk), .rst_ni(rst_n), .spi_sck_i(spi_sck),
      .spi_mosi_i(spi_mosi), .spi_miso_o(spi_miso), .spi_cs_ni(spi_cs_n),
      .irq_no(irq_n), .uart_tx_o(uart_tx), .fault_o(fault),
      .fatal_latched_i(fatal_latched), .secure_enable_i(secure_enable),
      .zeroize_ni(zeroize_n), .heartbeat_o(heartbeat)
  );

  initial begin
    repeat (5) @(posedge clk);
    rst_n = 1;
    repeat (6) @(posedge clk);
    if (spi_miso !== 1'bz) $fatal(1, "top MISO is not high-Z while CS_N high");
    if (irq_n !== 1 || uart_tx !== 1 || fault !== 0)
      $fatal(1, "top idle outputs mismatch irq=%b uart=%b fault=%b", irq_n, uart_tx, fault);
    $display("PASS primer1_top_idle_and_miso_high_z");

    previous_heartbeat = heartbeat;
    @(negedge clk);
    dut.u_core.heartbeat_counter = 22'd2699999;
    @(posedge clk);
    #1;
    if (heartbeat === previous_heartbeat) $fatal(1, "top heartbeat path did not toggle");
    $display("PASS primer1_top_heartbeat_integration");

    fatal_latched = 1;
    repeat (4) @(posedge clk);
    if (dut.fatal_sync !== 1 || fault !== 1)
      $fatal(1, "top fatal synchronizer/fail-closed path mismatch");
    $display("PASS primer1_top_safety_synchronizer_and_fault");
    $finish;
  end
endmodule
