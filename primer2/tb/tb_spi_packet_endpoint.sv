`timescale 1ns/1ps
module tb_spi_packet_endpoint;
  import trinity_spi_pkg::*;
  logic clk=0,rst_n=0,sck=0,mosi=0,cs_n=1,miso;
  logic request_valid;logic[7:0]request_command,request_flags;logic[15:0]request_txid,request_payload_length;
  logic[527:0]request_payload;logic[31:0]request_fingerprint;logic transport_error_valid;
  logic[7:0]transport_error_command;logic[15:0]transport_error_txid,transport_error_code;
  logic response_commit=0;logic[7:0]response_command=0,response_flags=0;logic[15:0]response_txid=0,response_payload_length=0;
  logic[527:0]response_payload=0;logic response_ready,mailbox_pending;logic[7:0]packet[0:75];integer packet_length,index,bad_crc_seen;
  always #5 clk=~clk;
  spi_packet_endpoint dut(.clk_i(clk),.rst_ni(rst_n),.spi_sck_i(sck),.spi_mosi_i(mosi),.spi_cs_ni(cs_n),.spi_miso_bit_o(miso),
    .request_valid_o(request_valid),.request_command_o(request_command),.request_flags_o(request_flags),.request_txid_o(request_txid),
    .request_payload_length_o(request_payload_length),.request_payload_o(request_payload),.request_fingerprint_o(request_fingerprint),
    .transport_error_valid_o(transport_error_valid),.transport_error_command_o(transport_error_command),.transport_error_txid_o(transport_error_txid),
    .transport_error_code_o(transport_error_code),.response_commit_i(response_commit),.response_command_i(response_command),
    .response_flags_i(response_flags),.response_txid_i(response_txid),.response_payload_length_i(response_payload_length),
    .response_payload_i(response_payload),.response_ready_o(response_ready),.mailbox_pending_o(mailbox_pending));
  function automatic[15:0]crc_update(input[15:0]ci,input[7:0]d);reg[15:0]c;integer b;begin c=ci^{d,8'h00};for(b=0;b<8;b=b+1)c=c[15]?((c<<1)^16'h1021):(c<<1);crc_update=c;end endfunction
  task automatic build(input[7:0]cmd,input[15:0]tx,input integer n);reg[15:0]c;begin
    packet[0]=SPI_MAGIC;packet[1]=PROTOCOL_VERSION;packet[2]=cmd;packet[3]=0;packet[4]=tx[15:8];packet[5]=tx[7:0];packet[6]=n[15:8];packet[7]=n[7:0];
    for(index=0;index<n;index=index+1)packet[8+index]=index[7:0]^8'h5A;c=16'hFFFF;for(index=0;index<8+n;index=index+1)c=crc_update(c,packet[index]);
    packet[8+n]=c[15:8];packet[9+n]=c[7:0];packet_length=10+n;end endtask
  task automatic shift_byte(input[7:0]v);integer b;begin for(b=7;b>=0;b=b-1)begin mosi=v[b];repeat(4)@(posedge clk);sck=1;repeat(4)@(posedge clk);sck=0;end end endtask
  task automatic send;begin cs_n=0;repeat(5)@(posedge clk);for(index=0;index<packet_length;index=index+1)shift_byte(packet[index]);repeat(4)@(posedge clk);cs_n=1;repeat(5)@(posedge clk);end endtask
  always@(posedge clk)if(transport_error_valid&&transport_error_code==ERR_BAD_CRC)bad_crc_seen<=1;
  initial begin bad_crc_seen=0;repeat(4)@(posedge clk);rst_n=1;repeat(4)@(posedge clk);
    build(CMD_READ_AUTH_RESULT,16'h1234,0);send();index=0;while(!request_valid&&index<300)begin @(posedge clk);index=index+1;end
    if(!request_valid||request_command!=CMD_READ_AUTH_RESULT||request_txid!=16'h1234)$fatal(1,"SPI request mismatch");$display("PASS spi_mode0_request");
    build(CMD_GET_INFO,16'h0102,0);packet[9]^=1;send();repeat(100)@(posedge clk);if(!bad_crc_seen)$fatal(1,"bad CRC accepted");$display("PASS spi_bad_crc_rejected");
    @(negedge clk);response_command=CMD_GET_INFO;response_flags=FLAG_RESPONSE;response_txid=16'h0102;response_payload_length=2;response_payload[7:0]=8'hAA;response_payload[15:8]=8'h55;response_commit=1;
    @(negedge clk);response_commit=0;index=0;while(!mailbox_pending&&index<100)begin @(posedge clk);index=index+1;end
    if(!mailbox_pending||dut.tx_mem[8]!=8'hAA||dut.tx_mem[9]!=8'h55)$fatal(1,"mailbox build");$display("PASS spi_response_mailbox_build");$finish;end
endmodule
