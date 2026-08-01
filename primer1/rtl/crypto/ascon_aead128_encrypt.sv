module ascon_aead128_encrypt (
    input  logic         clk_i,
    input  logic         rst_ni,
    input  logic         start_i,
    input  logic         abort_i,
    input  logic [127:0] key_i,
    input  logic [127:0] nonce_i,
    input  logic [191:0] ad_i,
    input  logic [191:0] plaintext_i,
    output logic         busy_o,
    output logic         done_o,
    output logic [191:0] ciphertext_o,
    output logic [127:0] tag_o
);
  // NIST SP 800-232 Ascon-AEAD128. Byte 0 occupies bits [7:0].
  localparam logic [63:0] ASCON_IV = 64'h00001000808C0001;

  typedef enum logic [3:0] {
    S_IDLE, S_INIT_P12, S_INIT_KEY, S_AD0_P8, S_AD1_P8,
    S_DOMAIN_SEP, S_MSG0_P8, S_MSG1, S_FINAL_P12, S_TAG, S_DONE
  } state_e;

  state_e state;
  logic [63:0] x0, x1, x2, x3, x4;
  logic [63:0] k0, k1, n0, n1;
  logic [191:0] ad_reg, pt_reg;
  logic [3:0] round_index;

  function automatic logic [63:0] ror64(input logic [63:0] x, input integer n);
    ror64 = (x >> n) | (x << (64-n));
  endfunction

  function automatic logic [7:0] round_constant(input logic [3:0] r);
    case (r)
      4'd0: round_constant = 8'hF0;
      4'd1: round_constant = 8'hE1;
      4'd2: round_constant = 8'hD2;
      4'd3: round_constant = 8'hC3;
      4'd4: round_constant = 8'hB4;
      4'd5: round_constant = 8'hA5;
      4'd6: round_constant = 8'h96;
      4'd7: round_constant = 8'h87;
      4'd8: round_constant = 8'h78;
      4'd9: round_constant = 8'h69;
      4'd10: round_constant = 8'h5A;
      default: round_constant = 8'h4B;
    endcase
  endfunction

  task automatic ascon_round(
      input logic [63:0] i0, i1, i2, i3, i4,
      input logic [7:0] rc,
      output logic [63:0] o0, o1, o2, o3, o4
  );
    logic [63:0] a0, a1, a2, a3, a4;
    logic [63:0] t0, t1, t2, t3, t4;
    begin
      a0 = i0;
      a1 = i1;
      a2 = i2 ^ {56'h0, rc};
      a3 = i3;
      a4 = i4;

      a0 = a0 ^ a4;
      a4 = a4 ^ a3;
      a2 = a2 ^ a1;
      t0 = a0 ^ ((~a1) & a2);
      t1 = a1 ^ ((~a2) & a3);
      t2 = a2 ^ ((~a3) & a4);
      t3 = a3 ^ ((~a4) & a0);
      t4 = a4 ^ ((~a0) & a1);
      t1 = t1 ^ t0;
      t0 = t0 ^ t4;
      t3 = t3 ^ t2;
      t2 = ~t2;

      o0 = t0 ^ ror64(t0, 19) ^ ror64(t0, 28);
      o1 = t1 ^ ror64(t1, 61) ^ ror64(t1, 39);
      o2 = t2 ^ ror64(t2, 1)  ^ ror64(t2, 6);
      o3 = t3 ^ ror64(t3, 10) ^ ror64(t3, 17);
      o4 = t4 ^ ror64(t4, 7)  ^ ror64(t4, 41);
    end
  endtask

  logic [63:0] r0, r1, r2, r3, r4;
  always_comb begin
    ascon_round(x0, x1, x2, x3, x4, round_constant(round_index),
                r0, r1, r2, r3, r4);
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state        <= S_IDLE;
      busy_o       <= 1'b0;
      done_o       <= 1'b0;
      ciphertext_o <= '0;
      tag_o        <= '0;
      x0 <= '0; x1 <= '0; x2 <= '0; x3 <= '0; x4 <= '0;
      k0 <= '0; k1 <= '0; n0 <= '0; n1 <= '0;
      ad_reg <= '0; pt_reg <= '0;
      round_index <= '0;
    end else if (abort_i) begin
      state <= S_IDLE;
      busy_o <= 1'b0;
      done_o <= 1'b0;
      ciphertext_o <= '0;
      tag_o <= '0;
      x0 <= '0; x1 <= '0; x2 <= '0; x3 <= '0; x4 <= '0;
      k0 <= '0; k1 <= '0; n0 <= '0; n1 <= '0;
      ad_reg <= '0; pt_reg <= '0;
      round_index <= '0;
    end else begin
      done_o <= 1'b0;
      case (state)
        S_IDLE: begin
          busy_o <= 1'b0;
          if (start_i) begin
            k0 <= key_i[63:0];
            k1 <= key_i[127:64];
            n0 <= nonce_i[63:0];
            n1 <= nonce_i[127:64];
            ad_reg <= ad_i;
            pt_reg <= plaintext_i;
            ciphertext_o <= '0;
            tag_o <= '0;
            x0 <= ASCON_IV;
            x1 <= key_i[63:0];
            x2 <= key_i[127:64];
            x3 <= nonce_i[63:0];
            x4 <= nonce_i[127:64];
            round_index <= 4'd0;
            busy_o <= 1'b1;
            state <= S_INIT_P12;
          end
        end

        S_INIT_P12: begin
          x0 <= r0; x1 <= r1; x2 <= r2; x3 <= r3; x4 <= r4;
          if (round_index == 4'd11) begin
            round_index <= 4'd4;
            state <= S_INIT_KEY;
          end else begin
            round_index <= round_index + 1'b1;
          end
        end

        S_INIT_KEY: begin
          x0 <= x0 ^ ad_reg[63:0];
          x1 <= x1 ^ ad_reg[127:64];
          x3 <= x3 ^ k0;
          x4 <= x4 ^ k1;
          round_index <= 4'd4;
          state <= S_AD0_P8;
        end

        S_AD0_P8: begin
          x0 <= r0; x1 <= r1; x2 <= r2; x3 <= r3; x4 <= r4;
          if (round_index == 4'd11) begin
            x0 <= r0 ^ ad_reg[191:128];
            x1 <= r1 ^ 64'h0000000000000001;
            round_index <= 4'd4;
            state <= S_AD1_P8;
          end else begin
            round_index <= round_index + 1'b1;
          end
        end

        S_AD1_P8: begin
          x0 <= r0; x1 <= r1; x2 <= r2; x3 <= r3; x4 <= r4;
          if (round_index == 4'd11) begin
            round_index <= 4'd4;
            state <= S_DOMAIN_SEP;
          end else begin
            round_index <= round_index + 1'b1;
          end
        end

        S_DOMAIN_SEP: begin
          x4 <= x4 ^ 64'h8000000000000000;
          x0 <= x0 ^ pt_reg[63:0];
          x1 <= x1 ^ pt_reg[127:64];
          ciphertext_o[63:0] <= x0 ^ pt_reg[63:0];
          ciphertext_o[127:64] <= x1 ^ pt_reg[127:64];
          round_index <= 4'd4;
          state <= S_MSG0_P8;
        end

        S_MSG0_P8: begin
          x0 <= r0; x1 <= r1; x2 <= r2; x3 <= r3; x4 <= r4;
          if (round_index == 4'd11) begin
            round_index <= 4'd0;
            state <= S_MSG1;
          end else begin
            round_index <= round_index + 1'b1;
          end
        end

        S_MSG1: begin
          ciphertext_o[191:128] <= x0 ^ pt_reg[191:128];
          x0 <= x0 ^ pt_reg[191:128];
          x1 <= x1 ^ 64'h0000000000000001;
          x2 <= x2 ^ k0;
          x3 <= x3 ^ k1;
          round_index <= 4'd0;
          state <= S_FINAL_P12;
        end

        S_FINAL_P12: begin
          x0 <= r0; x1 <= r1; x2 <= r2; x3 <= r3; x4 <= r4;
          if (round_index == 4'd11) begin
            state <= S_TAG;
          end else begin
            round_index <= round_index + 1'b1;
          end
        end

        S_TAG: begin
          tag_o[63:0] <= x3 ^ k0;
          tag_o[127:64] <= x4 ^ k1;
          state <= S_DONE;
        end

        S_DONE: begin
          busy_o <= 1'b0;
          done_o <= 1'b1;
          state <= S_IDLE;
        end

        default: state <= S_IDLE;
      endcase
    end
  end
endmodule
