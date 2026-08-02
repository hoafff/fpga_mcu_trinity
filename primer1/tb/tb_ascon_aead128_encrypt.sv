`timescale 1ns/1ps

module tb_ascon_aead128_encrypt;
  logic clk = 0;
  logic rst_n = 0;
  logic start = 0;
  logic abort = 0;
  logic [127:0] key = 0;
  logic [127:0] nonce = 0;
  logic [191:0] ad = 0;
  logic [191:0] plaintext = 0;
  logic busy, done;
  logic [191:0] ciphertext;
  logic [127:0] tag;
  integer timeout;

  always #5 clk = ~clk;

  ascon_aead128_encrypt dut (
      .clk_i(clk), .rst_ni(rst_n), .start_i(start), .abort_i(abort),
      .key_i(key), .nonce_i(nonce), .ad_i(ad), .plaintext_i(plaintext),
      .busy_o(busy), .done_o(done), .ciphertext_o(ciphertext), .tag_o(tag)
  );

  task automatic reset_dut;
    begin
      rst_n = 0;
      start = 0;
      abort = 0;
      repeat (4) @(posedge clk);
      rst_n = 1;
      repeat (2) @(posedge clk);
    end
  endtask

  task automatic run_vector(
      input logic [127:0] key_value,
      input logic [127:0] nonce_value,
      input logic [191:0] ad_value,
      input logic [191:0] pt_value,
      input logic [191:0] expected_ct,
      input logic [127:0] expected_tag,
      input string name
  );
    begin
      @(negedge clk);
      key = key_value;
      nonce = nonce_value;
      ad = ad_value;
      plaintext = pt_value;
      start = 1;
      @(negedge clk);
      start = 0;
      timeout = 0;
      while (!done && timeout < 300) begin
        @(posedge clk);
        timeout = timeout + 1;
      end
      if (!done) $fatal(1, "%s timeout", name);
      if (ciphertext !== expected_ct)
        $fatal(1, "%s ciphertext mismatch: got=%h expected=%h", name, ciphertext, expected_ct);
      if (tag !== expected_tag)
        $fatal(1, "%s tag mismatch: got=%h expected=%h", name, tag, expected_tag);
      $display("PASS %s", name);
      @(posedge clk);
    end
  endtask

  initial begin
    reset_dut();
    run_vector(
      128'h0f0e0d0c0b0a09080706050403020100,
      128'h1f1e1d1c1b1a19181716151413121110,
      192'h47464544434241403f3e3d3c3b3a39383736353433323130,
      192'h37363534333231302f2e2d2c2b2a29282726252423222120,
      192'h9298467629b3b1fcc71a48a4e0bc4caf7094df2ad5f9299d,
      128'h59ae42702c029d019bec055244afebdf,
      "ascon_official_count817_kat"
    );

    run_vector(
      128'haaaba8a9aeafacada2a3a0a1a6a7a4a5,
      128'h5e5b5855524f4c494643403d3a373431,
      192'hf3eee9e4dfdad5d0cbc6c1bcb7b2ada8a39e99948f8a8580,
      192'hf6efe8e1dad3ccc5beb7b0a9a29b948d867f78716a635c55,
      192'ha4fabf6334c32912619cc03725faeb6c1b341c8da4f97245,
      128'h5dcecf0032a1c1de4a21ede1c5786ef7,
      "ascon_nonzero_differential_vector"
    );

    @(negedge clk);
    key = '1;
    nonce = '1;
    ad = '1;
    plaintext = '1;
    start = 1;
    @(negedge clk);
    start = 0;
    repeat (7) @(posedge clk);
    @(negedge clk);
    abort = 1;
    @(negedge clk);
    abort = 0;
    @(posedge clk);
    if (busy !== 1'b0 || done !== 1'b0 || ciphertext !== '0 || tag !== '0)
      $fatal(1, "ascon abort did not clear transient/output state");
    $display("PASS ascon_abort_zeroizes_state");
    $finish;
  end
endmodule
