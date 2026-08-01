`timescale 1ns/1ps
module tb_poly_accel;
  logic clk=0,rst_n=0,we,slot,start,zeroize;
  logic [7:0] waddr,raddr;logic [15:0] wdata,rdata;logic [1:0] op;
  logic busy,done,error,zb,zd;integer i;
  always #5 clk=~clk;
  mlkem_poly_accel dut(.clk_i(clk),.rst_ni(rst_n),.load_we_i(we),.load_slot_i(slot),
    .load_addr_i(waddr),.load_data_i(wdata),.read_slot_i(1'b0),.read_addr_i(raddr),.read_data_o(rdata),
    .start_i(start),.operation_i(op),.busy_o(busy),.done_o(done),.error_o(error),
    .zeroize_i(zeroize),.zeroize_busy_o(zb),.zeroize_done_o(zd));
  task pulse_start(input [1:0] value);begin @(posedge clk);op<=value;start<=1;@(posedge clk);start<=0;wait(done);end endtask
  initial begin
    we=0;slot=0;start=0;zeroize=0;waddr=0;wdata=0;raddr=0;op=0;
    repeat(3)@(posedge clk);rst_n=1;
    for(i=0;i<256;i=i+1)begin @(posedge clk);we<=1;waddr<=i;wdata<=i;end
    @(posedge clk);we<=0;pulse_start(1);pulse_start(2);
    for(i=0;i<256;i=i+1)begin raddr<=i;@(posedge clk);@(posedge clk);if(rdata!==i[15:0])$fatal(1,"roundtrip %0d",i);end
    $display("PASS tb_poly_accel");$finish;
  end
endmodule
