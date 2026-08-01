module uart_frame_tx #(
    parameter integer CLOCK_HZ = 27000000,
    parameter integer BAUD = 115200,
    parameter integer FRAME_BYTES = 66,
    parameter integer IDLE_CYCLES = 27000
) (
    input  logic                         clk_i,
    input  logic                         rst_ni,
    input  logic                         start_i,
    input  logic                         abort_i,
    input  logic [FRAME_BYTES*8-1:0]     frame_i,
    output logic                         tx_o,
    output logic                         busy_o,
    output logic                         done_o
);
  typedef enum logic [1:0] {F_IDLE, F_LAUNCH, F_WAIT, F_GAP} fstate_e;
  fstate_e state;
  logic [FRAME_BYTES*8-1:0] frame_reg;
  logic [6:0] byte_index;
  logic [15:0] gap_counter;
  logic byte_start, byte_busy, byte_done;
  logic [7:0] byte_data;

  uart_tx_byte #(.CLOCK_HZ(CLOCK_HZ), .BAUD(BAUD)) u_byte (
    .clk_i(clk_i), .rst_ni(rst_ni), .start_i(byte_start), .abort_i(abort_i), .data_i(byte_data),
    .tx_o(tx_o), .busy_o(byte_busy), .done_o(byte_done)
  );

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state <= F_IDLE;
      frame_reg <= '0;
      byte_index <= 0;
      gap_counter <= 0;
      byte_start <= 1'b0;
      byte_data <= 0;
      busy_o <= 1'b0;
      done_o <= 1'b0;
    end else if (abort_i) begin
      state <= F_IDLE;
      byte_index <= 0;
      gap_counter <= 0;
      byte_start <= 1'b0;
      busy_o <= 1'b0;
      done_o <= 1'b0;
    end else begin
      byte_start <= 1'b0;
      done_o <= 1'b0;
      case (state)
        F_IDLE: begin
          busy_o <= 1'b0;
          if (start_i) begin
            frame_reg <= frame_i;
            byte_index <= 0;
            busy_o <= 1'b1;
            state <= F_LAUNCH;
          end
        end
        F_LAUNCH: begin
          if (!byte_busy) begin
            byte_data <= frame_reg[8*byte_index +: 8];
            byte_start <= 1'b1;
            state <= F_WAIT;
          end
        end
        F_WAIT: begin
          if (byte_done) begin
            if (byte_index == FRAME_BYTES-1) begin
              gap_counter <= 0;
              state <= F_GAP;
            end else begin
              byte_index <= byte_index + 1'b1;
              state <= F_LAUNCH;
            end
          end
        end
        F_GAP: begin
          if (gap_counter == IDLE_CYCLES-1) begin
            busy_o <= 1'b0;
            done_o <= 1'b1;
            state <= F_IDLE;
          end else gap_counter <= gap_counter + 1'b1;
        end
        default: state <= F_IDLE;
      endcase
    end
  end
endmodule
