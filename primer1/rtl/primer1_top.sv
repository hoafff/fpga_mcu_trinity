module primer1_top (
    input  logic sys_clk_i,
    input  logic rst_ni,
    input  logic spi_sck_i,
    input  logic spi_mosi_i,
    output wire  spi_miso_o,
    input  logic spi_cs_ni,
    output logic irq_no,
    output logic uart_tx_o,
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
      secure_meta <= 1'b0; secure_sync <= 1'b0;
      zeroize_meta <= 1'b0; zeroize_sync <= 1'b0;
      fatal_meta <= 1'b0; fatal_sync <= 1'b0;
    end else begin
      secure_meta <= secure_enable_i; secure_sync <= secure_meta;
      zeroize_meta <= zeroize_ni; zeroize_sync <= zeroize_meta;
      fatal_meta <= fatal_latched_i; fatal_sync <= fatal_meta;
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
  logic retained_pending, event_pending;
  logic [3:0] session_state;
  logic [2:0] operation_state;

  // MISO is electrically disconnected from the shared bus whenever CS_N is high.
  assign spi_miso_o = spi_cs_ni ? 1'bz : spi_miso_bit;
  always_comb irq_no = ~(mailbox_pending | retained_pending | event_pending);

  spi_packet_endpoint u_spi (
    .clk_i(sys_clk_i), .rst_ni(rst_ni),
    .spi_sck_i(spi_sck_i), .spi_mosi_i(spi_mosi_i), .spi_cs_ni(spi_cs_ni),
    .spi_miso_bit_o(spi_miso_bit),
    .request_valid_o(request_valid), .request_command_o(request_command),
    .request_flags_o(request_flags), .request_txid_o(request_txid),
    .request_payload_length_o(request_payload_length), .request_payload_o(request_payload),
    .request_fingerprint_o(request_fingerprint),
    .transport_error_valid_o(transport_error_valid),
    .transport_error_command_o(transport_error_command),
    .transport_error_txid_o(transport_error_txid),
    .transport_error_code_o(transport_error_code),
    .response_commit_i(response_commit), .response_command_i(response_command),
    .response_flags_i(response_flags), .response_txid_i(response_txid),
    .response_payload_length_i(response_payload_length), .response_payload_i(response_payload),
    .response_ready_o(response_ready), .mailbox_pending_o(mailbox_pending)
  );

  primer1_command_core u_core (
    .clk_i(sys_clk_i), .rst_ni(rst_ni),
    .secure_enable_i(secure_sync), .zeroize_ni(zeroize_sync),
    .fatal_latched_i(fatal_sync),
    .request_valid_i(request_valid), .request_command_i(request_command),
    .request_flags_i(request_flags), .request_txid_i(request_txid),
    .request_payload_length_i(request_payload_length), .request_payload_i(request_payload),
    .request_fingerprint_i(request_fingerprint),
    .transport_error_valid_i(transport_error_valid),
    .transport_error_command_i(transport_error_command),
    .transport_error_txid_i(transport_error_txid),
    .transport_error_code_i(transport_error_code),
    .response_commit_o(response_commit), .response_command_o(response_command),
    .response_flags_o(response_flags), .response_txid_o(response_txid),
    .response_payload_length_o(response_payload_length), .response_payload_o(response_payload),
    .response_ready_i(response_ready), .mailbox_pending_i(mailbox_pending),
    .retained_result_pending_o(retained_pending), .irq_event_pending_o(event_pending),
    .uart_tx_o(uart_tx_o), .heartbeat_o(heartbeat_o), .fault_o(fault_o),
    .session_state_o(session_state), .operation_state_o(operation_state)
  );
endmodule
