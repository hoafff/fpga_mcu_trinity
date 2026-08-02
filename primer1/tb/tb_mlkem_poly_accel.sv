`timescale 1ns/1ps

module tb_mlkem_poly_accel;
  localparam integer Q = 3329;
  logic clk = 0;
  logic rst_n = 0;
  logic load_we = 0;
  logic load_slot = 0;
  logic [7:0] load_addr = 0;
  logic [15:0] load_data = 0;
  logic read_slot = 0;
  logic [7:0] read_addr = 0;
  logic [15:0] read_data;
  logic start = 0;
  logic [1:0] operation = 0;
  logic busy, done, error;
  logic zeroize = 0;
  logic zeroize_busy, zeroize_done;

  logic [15:0] vector_a [0:255];
  logic [15:0] vector_b [0:255];
  logic [15:0] expected [0:255];
  integer index;
  integer got_i;
  integer expected_i;

  always #5 clk = ~clk;

  mlkem_poly_accel dut (
      .clk_i(clk), .rst_ni(rst_n),
      .load_we_i(load_we), .load_slot_i(load_slot),
      .load_addr_i(load_addr), .load_data_i(load_data),
      .read_slot_i(read_slot), .read_addr_i(read_addr), .read_data_o(read_data),
      .start_i(start), .operation_i(operation), .busy_o(busy),
      .done_o(done), .error_o(error),
      .zeroize_i(zeroize), .zeroize_busy_o(zeroize_busy),
      .zeroize_done_o(zeroize_done)
  );

  function automatic integer canonical(input integer value);
    integer reduced;
    begin
      reduced = value % Q;
      if (reduced < 0) reduced = reduced + Q;
      canonical = reduced;
    end
  endfunction

  task automatic reset_dut;
    begin
      rst_n = 0;
      load_we = 0;
      start = 0;
      zeroize = 0;
      repeat (4) @(posedge clk);
      rst_n = 1;
      repeat (2) @(posedge clk);
    end
  endtask

  task automatic load_a;
    begin
      load_slot = 0;
      for (index = 0; index < 256; index = index + 1) begin
        @(negedge clk);
        load_we = 1;
        load_addr = index[7:0];
        load_data = vector_a[index];
      end
      @(negedge clk);
      load_we = 0;
    end
  endtask

  task automatic load_b;
    begin
      load_slot = 1;
      for (index = 0; index < 256; index = index + 1) begin
        @(negedge clk);
        load_we = 1;
        load_addr = index[7:0];
        load_data = vector_b[index];
      end
      @(negedge clk);
      load_we = 0;
    end
  endtask

  task automatic execute(input logic [1:0] op);
    integer timeout;
    begin
      @(negedge clk);
      operation = op;
      start = 1;
      @(negedge clk);
      start = 0;
      timeout = 0;
      while (!done && timeout < 20000) begin
        @(posedge clk);
        timeout = timeout + 1;
      end
      if (!done) $fatal(1, "mlkem operation %0d timeout", op);
      if (error) $fatal(1, "mlkem operation %0d asserted error", op);
      @(posedge clk);
    end
  endtask

  task automatic compare_a(input string name);
    begin
      for (index = 0; index < 256; index = index + 1) begin
        got_i = canonical($signed(dut.poly_a[index]));
        expected_i = canonical($signed(expected[index]));
        if (got_i != expected_i)
          $fatal(1, "%s mismatch at %0d: got=%0d expected=%0d raw=%h/%h",
                 name, index, got_i, expected_i, dut.poly_a[index], expected[index]);
      end
      $display("PASS %s_nonzero_vector", name);
    end
  endtask

  initial begin
    reset_dut();
    $readmemh("primer1/tb/generated/ntt_input.hex", vector_a);
    $readmemh("primer1/tb/generated/ntt_expected.hex", expected);
    load_a();
    execute(2'd1);
    compare_a("ntt");

    reset_dut();
    $readmemh("primer1/tb/generated/intt_input.hex", vector_a);
    $readmemh("primer1/tb/generated/intt_expected.hex", expected);
    load_a();
    execute(2'd2);
    compare_a("intt");

    reset_dut();
    $readmemh("primer1/tb/generated/basemul_a.hex", vector_a);
    $readmemh("primer1/tb/generated/basemul_b.hex", vector_b);
    $readmemh("primer1/tb/generated/basemul_expected.hex", expected);
    load_a();
    load_b();
    execute(2'd3);
    compare_a("basemul");

    @(negedge clk);
    zeroize = 1;
    @(negedge clk);
    zeroize = 0;
    index = 0;
    while (!zeroize_done && index < 1000) begin
      @(posedge clk);
      index = index + 1;
    end
    if (!zeroize_done) $fatal(1, "poly zeroize timeout");
    for (index = 0; index < 256; index = index + 1) begin
      if (dut.poly_a[index] !== 16'd0 || dut.poly_b[index] !== 16'd0)
        $fatal(1, "poly zeroize mismatch at %0d", index);
    end
    $display("PASS mlkem_zeroize_both_dpb");
    $finish;
  end
endmodule
