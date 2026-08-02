`timescale 1ns/1ps

module tb_uart_frame_tx;
  localparam integer CLOCK_HZ = 16;
  localparam integer BAUD = 4;
  localparam integer BIT_CYCLES = CLOCK_HZ / BAUD;
  logic clk = 0;
  logic rst_n = 0;
  logic start = 0;
  logic abort = 0;
  logic [23:0] frame = 0;
  logic tx, busy, done;
  reg [7:0] decoded [0:2];
  integer byte_index;
  integer bit_index;
  integer timeout;

  always #5 clk = ~clk;

  uart_frame_tx #(
      .CLOCK_HZ(CLOCK_HZ), .BAUD(BAUD), .FRAME_BYTES(3), .IDLE_CYCLES(4)
  ) dut (
      .clk_i(clk), .rst_ni(rst_n), .start_i(start), .abort_i(abort),
      .frame_i(frame), .tx_o(tx), .busy_o(busy), .done_o(done)
  );

  task automatic wait_cycles(input integer count);
    integer loop_index;
    begin
      for (loop_index = 0; loop_index < count; loop_index = loop_index + 1)
        @(posedge clk);
    end
  endtask

  task automatic decode_one(output reg [7:0] value);
    begin
      timeout = 0;
      while (tx !== 0 && timeout < 100) begin
        @(posedge clk);
        timeout = timeout + 1;
      end
      if (tx !== 0) $fatal(1, "UART frame start-bit timeout");
      wait_cycles(BIT_CYCLES + BIT_CYCLES/2);
      for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1) begin
        value[bit_index] = tx;
        wait_cycles(BIT_CYCLES);
      end
      if (tx !== 1) $fatal(1, "UART frame stop-bit mismatch");
      wait_cycles(BIT_CYCLES/2);
    end
  endtask

  initial begin
    repeat (4) @(posedge clk);
    rst_n = 1;
    repeat (2) @(posedge clk);
    @(negedge clk);
    frame = 24'hC35AA5;
    start = 1;
    @(negedge clk);
    start = 0;
    for (byte_index = 0; byte_index < 3; byte_index = byte_index + 1)
      decode_one(decoded[byte_index]);
    if (decoded[0] != 8'hA5 || decoded[1] != 8'h5A || decoded[2] != 8'hC3)
      $fatal(1, "UART frame byte order mismatch: %h %h %h", decoded[0], decoded[1], decoded[2]);
    timeout = 0;
    while (!done && timeout < 100) begin
      @(posedge clk);
      timeout = timeout + 1;
    end
    if (!done || busy) $fatal(1, "UART frame completion mismatch");
    $display("PASS uart_frame_serializer_order_and_gap");
    $finish;
  end
endmodule
