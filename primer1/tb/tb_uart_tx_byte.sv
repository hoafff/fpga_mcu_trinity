`timescale 1ns/1ps

module tb_uart_tx_byte;
  logic clk = 0;
  logic rst_n = 0;
  logic start = 0;
  logic abort = 0;
  logic [7:0] data = 0;
  logic tx, busy, done;
  integer bit_index;
  integer timeout;

  always #5 clk = ~clk;

  uart_tx_byte #(.CLOCK_HZ(16), .BAUD(4)) dut (
      .clk_i(clk), .rst_ni(rst_n), .start_i(start), .abort_i(abort),
      .data_i(data), .tx_o(tx), .busy_o(busy), .done_o(done)
  );

  task automatic wait_cycles(input integer count);
    integer loop_index;
    begin
      for (loop_index = 0; loop_index < count; loop_index = loop_index + 1)
        @(posedge clk);
    end
  endtask

  initial begin
    repeat (4) @(posedge clk);
    rst_n = 1;
    repeat (2) @(posedge clk);
    @(negedge clk);
    data = 8'hA6;
    start = 1;
    @(negedge clk);
    start = 0;
    if (tx !== 0 || !busy) $fatal(1, "UART start bit not launched");
    wait_cycles(2);
    if (tx !== 0) $fatal(1, "UART start bit center mismatch");
    wait_cycles(2);
    for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1) begin
      wait_cycles(2);
      if (tx !== data[bit_index])
        $fatal(1, "UART data bit %0d mismatch", bit_index);
      wait_cycles(2);
    end
    wait_cycles(2);
    if (tx !== 1) $fatal(1, "UART stop bit mismatch");
    timeout = 0;
    while (!done && timeout < 20) begin
      @(posedge clk);
      timeout = timeout + 1;
    end
    if (!done || busy || tx !== 1) $fatal(1, "UART byte completion mismatch");
    $display("PASS uart_byte_8n1_lsb_first");

    @(negedge clk);
    data = 8'h3C;
    start = 1;
    @(negedge clk);
    start = 0;
    wait_cycles(5);
    @(negedge clk);
    abort = 1;
    @(negedge clk);
    abort = 0;
    @(posedge clk);
    if (tx !== 1 || busy || done) $fatal(1, "UART abort did not return idle");
    $display("PASS uart_byte_abort_idle");
    $finish;
  end
endmodule
