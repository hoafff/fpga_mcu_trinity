module uart_frame_receiver #(
    parameter integer CLOCK_HZ = 27000000,
    parameter integer INTERBYTE_TIMEOUT_MS = 20,
    parameter integer INTERFRAME_IDLE_US = 1000
) (
    input  logic         clk_i,
    input  logic         rst_ni,
    input  logic         abort_i,
    input  logic         accept_enable_i,
    input  logic         result_pending_i,
    input  logic         byte_valid_i,
    input  logic [7:0]   byte_i,
    input  logic         framing_error_i,
    output logic         frame_valid_o,
    output logic [511:0] frame_body_o,
    output logic         frame_timeout_o,
    output logic         framing_error_o,
    output logic         pending_drop_o,
    output logic         blocked_frame_o,
    output logic [2:0]   rx_state_o
);
  localparam integer BYTE_TIMEOUT_CYCLES = (CLOCK_HZ / 1000) * INTERBYTE_TIMEOUT_MS;
  localparam integer INTERFRAME_CYCLES = (CLOCK_HZ / 1000000) * INTERFRAME_IDLE_US;
  localparam integer TIMEOUT_W = $clog2(BYTE_TIMEOUT_CYCLES + 1);
  localparam integer IDLE_W = $clog2(INTERFRAME_CYCLES + 1);

  localparam logic [2:0] RX_HUNT_SYNC = 3'd0;
  localparam logic [2:0] RX_RECEIVE_BODY = 3'd1;

  logic sync_first;
  logic blocked_sync_first;
  logic blocked_reported;
  logic interframe_ready;
  logic [5:0] body_index;
  logic [511:0] body_reg;
  logic [511:0] body_with_byte;
  logic [TIMEOUT_W-1:0] timeout_counter;
  logic [IDLE_W-1:0] idle_counter;

  always_comb begin
    body_with_byte = body_reg;
    body_with_byte[8*body_index +: 8] = byte_i;
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      frame_valid_o <= 1'b0;
      frame_body_o <= '0;
      frame_timeout_o <= 1'b0;
      framing_error_o <= 1'b0;
      pending_drop_o <= 1'b0;
      blocked_frame_o <= 1'b0;
      rx_state_o <= RX_HUNT_SYNC;
      sync_first <= 1'b0;
      blocked_sync_first <= 1'b0;
      blocked_reported <= 1'b0;
      interframe_ready <= 1'b1;
      body_index <= '0;
      body_reg <= '0;
      timeout_counter <= '0;
      idle_counter <= INTERFRAME_CYCLES;
    end else begin
      frame_valid_o <= 1'b0;
      frame_timeout_o <= 1'b0;
      framing_error_o <= 1'b0;
      pending_drop_o <= 1'b0;
      blocked_frame_o <= 1'b0;

      if (abort_i) begin
        rx_state_o <= RX_HUNT_SYNC;
        sync_first <= 1'b0;
        blocked_sync_first <= 1'b0;
        blocked_reported <= 1'b0;
        interframe_ready <= 1'b0;
        body_index <= '0;
        body_reg <= '0;
        timeout_counter <= '0;
        idle_counter <= '0;
      end else begin
        if (byte_valid_i || framing_error_i) begin
          idle_counter <= '0;
        end else if (idle_counter < INTERFRAME_CYCLES) begin
          idle_counter <= idle_counter + 1'b1;
          if (idle_counter == INTERFRAME_CYCLES-1) begin
            interframe_ready <= 1'b1;
            blocked_reported <= 1'b0;
            blocked_sync_first <= 1'b0;
          end
        end

        case (rx_state_o)
          RX_HUNT_SYNC: begin
            timeout_counter <= '0;
            if (framing_error_i) begin
              sync_first <= 1'b0;
              framing_error_o <= 1'b1;
              interframe_ready <= 1'b0;
            end else if (byte_valid_i) begin
              if (!accept_enable_i) begin
                sync_first <= 1'b0;
                if (!blocked_reported) begin
                  if (!blocked_sync_first) begin
                    blocked_sync_first <= (byte_i == 8'hA5);
                  end else if (byte_i == 8'h5A) begin
                    blocked_reported <= 1'b1;
                    blocked_sync_first <= 1'b0;
                    if (result_pending_i)
                      pending_drop_o <= 1'b1;
                    else
                      blocked_frame_o <= 1'b1;
                  end else begin
                    blocked_sync_first <= (byte_i == 8'hA5);
                  end
                end
              end else if (interframe_ready) begin
                if (!sync_first) begin
                  sync_first <= (byte_i == 8'hA5);
                end else if (byte_i == 8'h5A) begin
                  sync_first <= 1'b0;
                  body_index <= 6'd0;
                  body_reg <= '0;
                  timeout_counter <= '0;
                  interframe_ready <= 1'b0;
                  rx_state_o <= RX_RECEIVE_BODY;
                end else begin
                  sync_first <= (byte_i == 8'hA5);
                end
              end
            end
          end

          RX_RECEIVE_BODY: begin
            if (framing_error_i) begin
              body_index <= '0;
              body_reg <= '0;
              timeout_counter <= '0;
              framing_error_o <= 1'b1;
              rx_state_o <= RX_HUNT_SYNC;
            end else if (byte_valid_i) begin
              body_reg <= body_with_byte;
              timeout_counter <= '0;
              if (body_index == 6'd63) begin
                frame_body_o <= body_with_byte;
                frame_valid_o <= 1'b1;
                body_index <= '0;
                rx_state_o <= RX_HUNT_SYNC;
              end else begin
                body_index <= body_index + 1'b1;
              end
            end else if (timeout_counter == BYTE_TIMEOUT_CYCLES-1) begin
              body_index <= '0;
              body_reg <= '0;
              timeout_counter <= '0;
              frame_timeout_o <= 1'b1;
              rx_state_o <= RX_HUNT_SYNC;
            end else begin
              timeout_counter <= timeout_counter + 1'b1;
            end
          end

          default: rx_state_o <= RX_HUNT_SYNC;
        endcase
      end
    end
  end
endmodule
