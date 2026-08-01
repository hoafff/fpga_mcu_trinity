`timescale 1ns/1ps
module tb_primer1_top_spi;
  logic clk=0,rst_n=0,sck=0,mosi=0,cs_n=1;
  wire miso; logic irq_n,uart_tx,fault,hb;
  logic fatal=0,secure=0,zeroize_n=1;
  byte unsigned req[0:9]; byte unsigned rsp[0:21]; integer i;
  always #18.518 clk=~clk;
  primer1_top dut(.sys_clk_i(clk),.rst_ni(rst_n),.spi_sck_i(sck),.spi_mosi_i(mosi),
    .spi_miso_o(miso),.spi_cs_ni(cs_n),.irq_no(irq_n),.uart_tx_o(uart_tx),.fault_o(fault),
    .fatal_latched_i(fatal),.secure_enable_i(secure),.zeroize_ni(zeroize_n),.heartbeat_o(hb));

  function automatic [15:0] crc_update(input [15:0] cin,input [7:0] d);
    reg [15:0] c;integer b;begin c=cin^{d,8'h00};for(b=0;b<8;b=b+1)c=c[15]?((c<<1)^16'h1021):(c<<1);crc_update=c;end
  endfunction
  task automatic xfer(input [7:0] tx,output [7:0] rx);
    integer b;begin rx=0;for(b=7;b>=0;b=b-1)begin mosi=tx[b];#400;sck=1;#400;rx[b]=miso;sck=0;end end
  endtask
  reg [7:0] discard;reg [15:0] crc;
  initial begin
    #100; if(miso!==1'bz)$fatal(1,"MISO not high-Z while deselected");
    repeat(4)@(posedge clk);rst_n=1;#12000;
    req[0]=8'hA5;req[1]=1;req[2]=1;req[3]=0;req[4]=8'h12;req[5]=8'h34;req[6]=0;req[7]=0;
    crc=16'hFFFF;for(i=0;i<8;i=i+1)crc=crc_update(crc,req[i]);req[8]=crc[15:8];req[9]=crc[7:0];
    cs_n=0;#500;for(i=0;i<10;i=i+1)xfer(req[i],discard);#500;cs_n=1;
    wait(irq_n==0);#1000;cs_n=0;#500;for(i=0;i<22;i=i+1)xfer(8'hFF,rsp[i]);#500;cs_n=1;#200;
    if(miso!==1'bz)$fatal(1,"MISO not high-Z after response");
    if(rsp[0]!=8'hA5||rsp[1]!=1||rsp[2]!=1||rsp[3]!=1||rsp[4]!=8'h12||rsp[5]!=8'h34)$fatal(1,"GET_INFO header");
    if({rsp[6],rsp[7]}!=12)$fatal(1,"GET_INFO length");
    crc=16'hFFFF;for(i=0;i<20;i=i+1)crc=crc_update(crc,rsp[i]);if({rsp[20],rsp[21]}!=crc)$fatal(1,"response CRC");
    $display("PASS tb_primer1_top_spi");$finish;
  end
endmodule
