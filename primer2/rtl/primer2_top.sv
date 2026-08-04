module primer2_top #(
    parameter integer CLOCK_HZ = 27000000,
    parameter integer UART_BAUD = 115200,
    parameter logic [31:0] BUILD_ID = 32'h5032_0001
) (
    input  logic sys_clk_i,
    input  logic rst_ni,
    input  logic spi_sck_i,
    input  logic spi_mosi_i,
    output wire  spi_miso_o,
    input  logic spi_cs_ni,
    output logic irq_no,
    input  logic uart_rx_i,
    output logic fault_o,
    input  logic fatal_latched_i,
    input  logic secure_enable_i,
    input  logic zeroize_ni,
    output logic heartbeat_o
);
  logic secure_meta, secure_sync;
  logic zeroize_meta, zeroize_sync;
  logic fatal_meta, fatal_sync;

  always_ff @(posedge sys_clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      secure_meta <= 1'b0;
      secure_sync <= 1'b0;
      zeroize_meta <= 1'b0;
      zeroize_sync <= 1'b0;
      fatal_meta <= 1'b0;
      fatal_sync <= 1'b0;
    end else begin
      secure_meta <= secure_enable_i;
      secure_sync <= secure_meta;
      zeroize_meta <= zeroize_ni;
      zeroize_sync <= zeroize_meta;
      fatal_meta <= fatal_latched_i;
      fatal_sync <= fatal_meta;
    end
  end

  logic spi_miso_bit;
  logic request_valid;
  logic [7:0] request_command, request_flags;
  logic [15:0] request_txid, request_payload_length;
  logic [527:0] request_payload;
  logic [31:0] request_fingerprint;
  logic transport_error_valid;
  logic [7:0] transport_error_command;
  logic [15:0] transport_error_txid, transport_error_code;
  logic response_commit, response_ready, mailbox_pending;
  logic [7:0] response_command, response_flags;
  logic [15:0] response_txid, response_payload_length;
  logic [527:0] response_payload;

  logic uart_byte_valid, uart_framing_error, uart_byte_busy;
  logic [7:0] uart_byte;
  logic frame_valid, frame_timeout, frame_framing_error;
  logic frame_pending_drop, frame_blocked;
  logic [511:0] frame_body;
  logic [2:0] frame_rx_state;
  logic rx_accept_enable, result_pending;
  logic receiver_abort;

  logic retained_pending, authenticated_pending, event_pending;
  logic [3:0] session_state;
  logic [2:0] operation_state, rx_state;

  assign spi_miso_o = spi_cs_ni ? 1'bz : spi_miso_bit;

  /*
   * IRQ_N is asserted only while a complete SPI response mailbox can be read.
   * Retained side-effect and authenticated payload buffers are persistent state,
   * exposed through GET_STATUS and explicit query/read commands; they must not
   * hold IRQ_N low after the response mailbox is consumed because the master
   * must remain able to issue GET_TXN_RESULT, RETIRE_TXN_RESULT,
   * READ_AUTH_RESULT and ACK_AUTH_RESULT.
   */
  always_comb irq_no = ~mailbox_pending;

  assign receiver_abort = !zeroize_sync | fatal_sync |
                          (session_state == 4'd7) | (session_state == 4'd8);

  spi_packet_endpoint u_spi (
      .clk_i(sys_clk_i),
      .rst_ni(rst_ni),
      .spi_sck_i(spi_sck_i),
      .spi_mosi_i(spi_mosi_i),
      .spi_cs_ni(spi_cs_ni),
      .spi_miso_bit_o(spi_miso_bit),
      .request_valid_o(request_valid),
      .request_command_o(request_command),
      .request_flags_o(request_flags),
      .request_txid_o(request_txid),
      .request_payload_length_o(request_payload_length),
      .request_payload_o(request_payload),
      .request_fingerprint_o(request_fingerprint),
      .transport_error_valid_o(transport_error_valid),
      .transport_error_command_o(transport_error_command),
      .transport_error_txid_o(transport_error_txid),
      .transport_error_code_o(transport_error_code),
      .response_commit_i(response_commit),
      .response_command_i(response_command),
      .response_flags_i(response_flags),
      .response_txid_i(response_txid),
      .response_payload_length_i(response_payload_length),
      .response_payload_i(response_payload),
      .response_ready_o(response_ready),
      .mailbox_pending_o(mailbox_pending)
  );

  uart_rx_byte #(.CLOCK_HZ(CLOCK_HZ), .BAUD(UART_BAUD)) u_uart_byte (
      .clk_i(sys_clk_i),
      .rst_ni(rst_ni),
      .abort_i(receiver_abort),
      .rx_i(uart_rx_i),
      .byte_valid_o(uart_byte_valid),
      .byte_o(uart_byte),
      .framing_error_o(uart_framing_error),
      .busy_o(uart_byte_busy)
  );

  uart_frame_receiver #(.CLOCK_HZ(CLOCK_HZ)) u_uart_frame (
      .clk_i(sys_clk_i),
      .rst_ni(rst_ni),
      .abort_i(receiver_abort),
      .accept_enable_i(rx_accept_enable),
      .result_pending_i(result_pending),
      .byte_valid_i(uart_byte_valid),
      .byte_i(uart_byte),
      .framing_error_i(uart_framing_error),
      .frame_valid_o(frame_valid),
      .frame_body_o(frame_body),
      .frame_timeout_o(frame_timeout),
      .framing_error_o(frame_framing_error),
      .pending_drop_o(frame_pending_drop),
      .blocked_frame_o(frame_blocked),
      .rx_state_o(frame_rx_state)
  );

  primer2_command_core #(.CLOCK_HZ(CLOCK_HZ), .BUILD_ID(BUILD_ID)) u_core (
      .clk_i(sys_clk_i),
      .rst_ni(rst_ni),
      .secure_enable_i(secure_sync),
      .zeroize_ni(zeroize_sync),
      .fatal_latched_i(fatal_sync),
      .request_valid_i(request_valid),
      .request_command_i(request_command),
      .request_flags_i(request_flags),
      .request_txid_i(request_txid),
      .request_payload_length_i(request_payload_length),
      .request_payload_i(request_payload),
      .request_fingerprint_i(request_fingerprint),
      .transport_error_valid_i(transport_error_valid),
      .transport_error_command_i(transport_error_command),
      .transport_error_txid_i(transport_error_txid),
      .transport_error_code_i(transport_error_code),
      .response_commit_o(response_commit),
      .response_command_o(response_command),
      .response_flags_o(response_flags),
      .response_txid_o(response_txid),
      .response_payload_length_o(response_payload_length),
      .response_payload_o(response_payload),
      .response_ready_i(response_ready),
      .mailbox_pending_i(mailbox_pending),
      .frame_valid_i(frame_valid),
      .frame_body_i(frame_body),
      .frame_timeout_i(frame_timeout),
      .frame_framing_error_i(frame_framing_error),
      .frame_pending_drop_i(frame_pending_drop),
      .frame_blocked_i(frame_blocked),
      .frame_rx_state_i(frame_rx_state),
      .rx_accept_enable_o(rx_accept_enable),
      .result_pending_o(result_pending),
      .retained_result_pending_o(retained_pending),
      .authenticated_result_pending_o(authenticated_pending),
      .irq_event_pending_o(event_pending),
      .heartbeat_o(heartbeat_o),
      .fault_o(fault_o),
      .session_state_o(session_state),
      .operation_state_o(operation_state),
      .rx_state_o(rx_state)
  );
endmodule
