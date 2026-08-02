module uart_rx_byte #(
    parameter integer CLOCK_HZ = 27000000,
    parameter integer BAUD = 115200
) (
    input  logic       clk_i,
    input  logic       rst_ni,
    input  logic       abort_i,
    input  logic       rx_i,
    output logic       byte_valid_o,
    output logic [7:0] byte_o,
    output logic       framing_error_o,
    output logic       busy_o
);
  localparam integer CLKS_PER_BIT = CLOCK_HZ / BAUD;
  localparam integer HALF_BIT_CLKS = CLKS_PER_BIT / 2;
  localparam integer COUNTER_WIDTH = $clog2(CLKS_PER_BIT + 1);

  typedef enum logic [1:0] {RX_IDLE, RX_START, RX_DATA, RX_STOP} rx_state_e;
  rx_state_e state;

  logic rx_meta, rx_sync, rx_prev;
  logic [COUNTER_WIDTH-1:0] counter;
  logic [2:0] bit_index;
  logic [7:0] data_reg;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      rx_meta <= 1'b1;
      rx_sync <= 1'b1;
      rx_prev <= 1'b1;
      state <= RX_IDLE;
      counter <= '0;
      bit_index <= '0;
      data_reg <= '0;
      byte_valid_o <= 1'b0;
      byte_o <= '0;
      framing_error_o <= 1'b0;
      busy_o <= 1'b0;
    end else begin
      rx_meta <= rx_i;
      rx_sync <= rx_meta;
      rx_prev <= rx_sync;
      byte_valid_o <= 1'b0;
      framing_error_o <= 1'b0;

      if (abort_i) begin
        state <= RX_IDLE;
        counter <= '0;
        bit_index <= '0;
        data_reg <= '0;
        busy_o <= 1'b0;
      end else begin
        case (state)
          RX_IDLE: begin
            busy_o <= 1'b0;
            if (rx_prev && !rx_sync) begin
              counter <= HALF_BIT_CLKS;
              busy_o <= 1'b1;
              state <= RX_START;
            end
          end

          RX_START: begin
            if (counter != 0) begin
              counter <= counter - 1'b1;
            end else if (!rx_sync) begin
              counter <= CLKS_PER_BIT-1;
              bit_index <= 3'd0;
              state <= RX_DATA;
            end else begin
              state <= RX_IDLE;
              busy_o <= 1'b0;
            end
          end

          RX_DATA: begin
            if (counter != 0) begin
              counter <= counter - 1'b1;
            end else begin
              data_reg[bit_index] <= rx_sync;
              counter <= CLKS_PER_BIT-1;
              if (bit_index == 3'd7)
                state <= RX_STOP;
              else
                bit_index <= bit_index + 1'b1;
            end
          end

          RX_STOP: begin
            if (counter != 0) begin
              counter <= counter - 1'b1;
            end else begin
              busy_o <= 1'b0;
              state <= RX_IDLE;
              if (rx_sync) begin
                byte_o <= data_reg;
                byte_valid_o <= 1'b1;
              end else begin
                framing_error_o <= 1'b1;
              end
            end
          end

          default: state <= RX_IDLE;
        endcase
      end
    end
  end
endmodule
