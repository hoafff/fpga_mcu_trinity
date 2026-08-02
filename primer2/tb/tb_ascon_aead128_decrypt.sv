`timescale 1ns/1ps
module tb_ascon_aead128_decrypt;
  logic clk = 0, rst_n = 0, start = 0, abort = 0;
  logic [127:0] key, nonce, tag;
  logic [191:0] ad, ciphertext;
  logic busy, done, tag_valid;
  logic [191:0] plaintext;
  integer cycles;
  always #5 clk = ~clk;

  ascon_aead128_decrypt dut(
    .clk_i(clk), .rst_ni(rst_n), .start_i(start), .abort_i(abort),
    .key_i(key), .nonce_i(nonce), .ad_i(ad), .ciphertext_i(ciphertext),
    .tag_i(tag), .busy_o(busy), .done_o(done), .tag_valid_o(tag_valid),
    .plaintext_o(plaintext));

  task automatic run_case(input [127:0] k, input [127:0] n,
      input [191:0] a, input [191:0] c, input [127:0] t,
      input [191:0] expected, input bit expect_valid);
    begin
      @(negedge clk); key=k; nonce=n; ad=a; ciphertext=c; tag=t; start=1;
      @(negedge clk); start=0;
      cycles=0;
      while (!done && cycles < 200) begin @(posedge clk); cycles=cycles+1; end
      if (!done) $fatal(1,"decrypt timeout");
      if (tag_valid !== expect_valid) $fatal(1,"tag result mismatch");
      if (expect_valid && plaintext !== expected) $fatal(1,"plaintext mismatch");
      @(posedge clk);
    end
  endtask

  initial begin
    key='0; nonce='0; ad='0; ciphertext='0; tag='0;
    repeat(4) @(posedge clk); rst_n=1; repeat(2) @(posedge clk);
    run_case(128'd0,128'd0,192'd0,
      192'h64AE2CC0931A7A9101C4872B0A040525B17FC6E9FD6D89E6,
      128'h4B9E81835266C56C0884E76F29D95FE8,192'd0,1'b1);
    $display("PASS ascon_zero_kat_decrypt");
    run_case(128'hFFEEDDCCBBAA99887766554433221100,
      128'h01000000000000008776655443322110,
      192'h000000004433180001000000000000004433221134120201,
      192'h30CCB278A33B70139B376D8290C255B8D1357E03280E320C,
      128'h1A9061D8C0929EA8374B85ED37AF7165,
      192'h0017161514131211100F0E0D0C0B0A090807060504030201,1'b1);
    $display("PASS ascon_nonzero_p1_compatible_vector");
    run_case(128'hFFEEDDCCBBAA99887766554433221100,
      128'h01000000000000008776655443322110,
      192'h000000004433180001000000000000004433221134120201,
      192'h30CCB278A33B70139B376D8290C255B8D1357E03280E320C,
      128'h1A9061D8C0929EA8374B85ED37AF7164,
      192'd0,1'b0);
    $display("PASS ascon_tag_flip_rejected");
    run_case(128'hFFEEDDCCBBAA99887766554433221100,
      128'h01000000000000008776655443322110,
      192'h000000004433180001000000000000004433221134120200,
      192'h30CCB278A33B70139B376D8290C255B8D1357E03280E320C,
      128'h1A9061D8C0929EA8374B85ED37AF7165,
      192'd0,1'b0);
    $display("PASS ascon_ad_flip_rejected");
    run_case(128'hFFEEDDCCBBAA99887766554433221100,
      128'h01000000000000008776655443322110,
      192'h000000004433180001000000000000004433221134120201,
      192'h30CCB278A33B70139B376D8290C255B8D1357E03280E320D,
      128'h1A9061D8C0929EA8374B85ED37AF7165,
      192'd0,1'b0);
    $display("PASS ascon_ciphertext_flip_rejected");
    run_case(128'hFFEEDDCCBBAA99887766554433221101,
      128'h01000000000000008776655443322110,
      192'h000000004433180001000000000000004433221134120201,
      192'h30CCB278A33B70139B376D8290C255B8D1357E03280E320C,
      128'h1A9061D8C0929EA8374B85ED37AF7165,
      192'd0,1'b0);
    $display("PASS ascon_wrong_key_rejected");
    run_case(128'hFFEEDDCCBBAA99887766554433221100,
      128'h01000000000000008776655443322111,
      192'h000000004433180001000000000000004433221134120201,
      192'h30CCB278A33B70139B376D8290C255B8D1357E03280E320C,
      128'h1A9061D8C0929EA8374B85ED37AF7165,
      192'd0,1'b0);
    $display("PASS ascon_wrong_nonce_rejected");
    @(negedge clk); key='0; nonce='0; ad='0; ciphertext='0; tag='0; start=1;
    @(negedge clk); start=0; repeat(5) @(posedge clk); abort=1;
    @(posedge clk); abort=0; @(posedge clk);
    if (busy || done || tag_valid || plaintext != 0) $fatal(1,"abort did not clear decrypt state");
    $display("PASS ascon_abort_zeroizes_candidate");
    $finish;
  end
endmodule
