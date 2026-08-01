`timescale 1ns/1ps
module tb_poly_accel;
  logic clk=0,rst_n=0,we,slot,start,zeroize;
  logic [7:0] waddr,raddr;logic [15:0] wdata,rdata;logic [1:0] op;
  logic busy,done,error,zb,zd;integer i,chunk,offset;
  always #5 clk=~clk;
  mlkem_poly_accel dut(.clk_i(clk),.rst_ni(rst_n),.load_we_i(we),.load_slot_i(slot),
    .load_addr_i(waddr),.load_data_i(wdata),.read_slot_i(slot),.read_addr_i(raddr),.read_data_o(rdata),
    .start_i(start),.operation_i(op),.busy_o(busy),.done_o(done),.error_o(error),
    .zeroize_i(zeroize),.zeroize_busy_o(zb),.zeroize_done_o(zd));

  task automatic write_coeff(input bit target_slot,input integer index,input [15:0] value);
    begin @(posedge clk);slot<=target_slot;waddr<=index;wdata<=value;we<=1;
      @(posedge clk);we<=0;end
  endtask

  task automatic pulse_start(input [1:0] value);
    begin @(posedge clk);op<=value;start<=1;@(posedge clk);start<=0;wait(done);end
  endtask

  task automatic check_chunk(input bit target_slot,input integer base,input integer pattern);
    integer k;reg [15:0] expected;
    begin
      slot=target_slot;raddr=base[7:0];@(posedge clk);#1;
      for(k=0;k<32;k=k+1)begin
        case(pattern)
          0:expected=(base+k==0)?16'd1:16'd0;
          1:expected=((base+k)&1)?16'd0:16'd1;
          default:expected=16'd0;
        endcase
        if(rdata!==expected)$fatal(1,"slot=%0d index=%0d got=%0d expected=%0d",target_slot,base+k,rdata,expected);
        if(k!=31)begin @(posedge clk);#1;raddr=(base+k+1);end
      end
    end
  endtask

  task automatic check_all_chunks(input bit target_slot,input integer pattern);
    integer c;begin for(c=0;c<8;c=c+1)check_chunk(target_slot,32*c,pattern);end
  endtask

  initial begin
    we=0;slot=0;start=0;zeroize=0;waddr=0;wdata=0;raddr=0;op=0;
    repeat(3)@(posedge clk);rst_n=1;

    // Directed NTT KAT: delta polynomial maps to [1,0,1,0,...].
    for(i=0;i<256;i=i+1)write_coeff(0,i,(i==0)?16'd1:16'd0);
    pulse_start(2'd1);check_all_chunks(0,1);

    // INTT returns the original standard-domain delta polynomial.
    pulse_start(2'd2);check_all_chunks(0,0);

    // BaseMul KAT in NTT order: delta-transform squared is unchanged.
    for(i=0;i<256;i=i+1)begin
      write_coeff(0,i,(i[0])?16'd0:16'd1);
      write_coeff(1,i,(i[0])?16'd0:16'd1);
    end
    pulse_start(2'd3);check_all_chunks(0,1);

    // Sequential zeroization overwrites both polynomial memories.
    @(posedge clk);zeroize<=1;@(posedge clk);zeroize<=0;wait(zd);
    check_all_chunks(0,2);check_all_chunks(1,2);
    $display("PASS tb_poly_accel");$finish;
  end
endmodule
