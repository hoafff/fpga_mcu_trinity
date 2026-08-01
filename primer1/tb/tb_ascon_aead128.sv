`timescale 1ns/1ps
module tb_ascon_aead128;
  logic clk=0,rst_n=0,start;
  logic busy,done;
  logic [191:0] ct;
  logic [127:0] tag;
  always #5 clk=~clk;
  ascon_aead128_encrypt dut(.clk_i(clk),.rst_ni(rst_n),.start_i(start),
    .abort_i(1'b0),.key_i('0),.nonce_i('0),.ad_i('0),.plaintext_i('0),
    .busy_o(busy),.done_o(done),.ciphertext_o(ct),.tag_o(tag));
  initial begin
    start=0; repeat(3) @(posedge clk); rst_n=1; @(posedge clk); start=1;
    @(posedge clk);start=0;wait(done);
    if(ct!==192'h64AE2CC0931A7A9101C4872B0A040525B17FC6E9FD6D89E6) $fatal(1,"Ascon ciphertext KAT");
    if(tag!==128'h4B9E81835266C56C0884E76F29D95FE8) $fatal(1,"Ascon tag KAT");
    $display("PASS tb_ascon_aead128");$finish;
  end
endmodule
