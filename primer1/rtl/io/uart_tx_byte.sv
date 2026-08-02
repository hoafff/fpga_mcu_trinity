module uart_tx_byte #(
    parameter integer CLOCK_HZ = 27000000,
    parameter integer BAUD = 115200
) (
    input  logic       clk_i,
    input  logic       rst_ni,
    input  logic       start_i,
    input  logic       abort_i,
    input  logic [7:0] data_i,
    output logic       tx_o,
    output logic       busy_o,
    output logic       done_o
);
  // A 32-bit unsigned phase accumulator is intentionally wider than required
  // for 27 MHz. Keeping parameter constants at the same width removes implicit
  // signed extension/truncation and preserves the fractional baud generator.
  localparam logic [31:0] CLOCK_HZ_U = CLOCK_HZ;
  localparam logic [31:0] BAUD_U = BAUD;

  logic [31:0] baud_acc;
  logic [3:0] bit_index;
  logic [9:0] shift_reg;
  logic baud_tick;

  always_comb begin
    baud_tick = (baud_acc >= (CLOCK_HZ_U - BAUD_U));
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      baud_acc <= 32'd0;
      bit_index <= 4'd0;
      shift_reg <= 10'h3FF;
      tx_o <= 1'b1;
      busy_o <= 1'b0;
      done_o <= 1'b0;
    end else if (abort_i) begin
      baud_acc <= 32'd0;
      bit_index <= 4'd0;
      shift_reg <= 10'h3FF;
      tx_o <= 1'b1;
      busy_o <= 1'b0;
      done_o <= 1'b0;
    end else begin
      done_o <= 1'b0;
      if (!busy_o) begin
        tx_o <= 1'b1;
        baud_acc <= 32'd0;
        if (start_i) begin
          shift_reg <= {1'b1, data_i, 1'b0};
          tx_o <= 1'b0;
          bit_index <= 4'd0;
          busy_o <= 1'b1;
        end
      end else if (baud_tick) begin
        baud_acc <= baud_acc + BAUD_U - CLOCK_HZ_U;
        if (bit_index == 4'd9) begin
          tx_o <= 1'b1;
          busy_o <= 1'b0;
          done_o <= 1'b1;
        end else begin
          bit_index <= bit_index + 4'd1;
          shift_reg <= {1'b1, shift_reg[9:1]};
          tx_o <= shift_reg[1];
        end
      end else begin
        baud_acc <= baud_acc + BAUD_U;
      end
    end
  end
endmodule
