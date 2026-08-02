`timescale 1ns/1ps
module tb_uart_rx_byte;
  localparam integer CLOCK_HZ=1000000;
  localparam integer BAUD=100000;
  localparam integer BIT_CYCLES=CLOCK_HZ/BAUD;
  logic clk=0,rst_n=0,abort=0,rx=1;
  logic valid,err,busy; logic [7:0] data;
  integer i;
  always #5 clk=~clk;
  uart_rx_byte #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) dut(
    .clk_i(clk),.rst_ni(rst_n),.abort_i(abort),.rx_i(rx),
    .byte_valid_o(valid),.byte_o(data),.framing_error_o(err),.busy_o(busy));
  task automatic bit_hold(input bit v); begin rx=v; repeat(BIT_CYCLES) @(posedge clk); end endtask
  task automatic send_byte(input [7:0] v,input bit good_stop);
    begin bit_hold(0); for(i=0;i<8;i=i+1) bit_hold(v[i]); bit_hold(good_stop); bit_hold(1); end
  endtask
  initial begin
    repeat(4) @(posedge clk);rst_n=1;repeat(3) @(posedge clk);
    fork send_byte(8'hA5,1); begin wait(valid); if(data!=8'hA5)$fatal(1,"byte mismatch"); end join
    $display("PASS uart_rx_8n1_byte");
    fork send_byte(8'h5A,0); begin wait(err); end join
    $display("PASS uart_rx_framing_error");
    fork send_byte(8'h33,1); begin repeat(20)@(posedge clk);abort=1;@(posedge clk);abort=0; end join
    repeat(5)@(posedge clk); if(busy)$fatal(1,"abort left UART busy");
    $display("PASS uart_rx_abort");
    $finish;
  end
endmodule
