`timescale 1ns/1ps
module tb_ascon_aead128;
  logic clk=0,rst_n=0,start;
  logic busy,done;
  logic [191:0] ct;
  logic [127:0] tag;
  always #5 clk=~clk;
  ascon_aead128_encrypt dut(.clk_i(clk),.rst_ni(rst_n),.start_i(start),
    .abort_i(1'b0),
    .key_i(128'h0F0E0D0C0B0A09080706050403020100),
    .nonce_i(128'h1F1E1D1C1B1A19181716151413121110),
    .ad_i(192'h47464544434241403F3E3D3C3B3A39383736353433323130),
    .plaintext_i(192'h37363534333231302F2E2D2C2B2A29282726252423222120),
    .busy_o(busy),.done_o(done),.ciphertext_o(ct),.tag_o(tag));
  initial begin
    start=0; repeat(3) @(posedge clk); rst_n=1; @(posedge clk); start=1;
    @(posedge clk);start=0;wait(done);
    if(ct!==192'h9298467629B3B1FCC71A48A4E0BC4CAF7094DF2AD5F9299D) $fatal(1,"Ascon official Count 817 ciphertext");
    if(tag!==128'h59AE42702C029D019BEC055244AFEBDF) $fatal(1,"Ascon official Count 817 tag");
    $display("PASS tb_ascon_aead128 official Count 817");$finish;
  end
endmodule
