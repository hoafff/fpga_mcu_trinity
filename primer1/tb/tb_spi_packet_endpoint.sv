`timescale 1ns/1ps

module tb_spi_packet_endpoint;
  import trinity_spi_pkg::*;
  logic clk = 0;
  logic rst_n = 0;
  logic sck = 0;
  logic mosi = 0;
  logic cs_n = 1;
  logic miso;
  logic request_valid;
  logic [7:0] request_command, request_flags;
  logic [15:0] request_txid, request_payload_length;
  logic [527:0] request_payload;
  logic [31:0] request_fingerprint;
  logic transport_error_valid;
  logic [7:0] transport_error_command;
  logic [15:0] transport_error_txid, transport_error_code;
  logic response_commit = 0;
  logic [7:0] response_command = 0, response_flags = 0;
  logic [15:0] response_txid = 0, response_payload_length = 0;
  logic [527:0] response_payload = 0;
  logic response_ready, mailbox_pending;
  logic [7:0] packet [0:75];
  integer packet_length;
  integer index;
  integer bad_crc_seen;
  integer bad_length_seen;
  logic [15:0] bad_length_detail_seen;
  logic [7:0] bad_length_command_seen;
  logic [15:0] bad_length_txid_seen;

  always #5 clk = ~clk;

  spi_packet_endpoint dut (
      .clk_i(clk), .rst_ni(rst_n), .spi_sck_i(sck), .spi_mosi_i(mosi),
      .spi_cs_ni(cs_n), .spi_miso_bit_o(miso),
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

  function automatic [15:0] crc_update(input [15:0] crc_in, input [7:0] data);
    reg [15:0] crc;
    integer bit_index;
    begin
      crc = crc_in ^ {data, 8'h00};
      for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1)
        crc = crc[15] ? ((crc << 1) ^ 16'h1021) : (crc << 1);
      crc_update = crc;
    end
  endfunction

  task automatic build_packet(input [7:0] command, input [15:0] txid, input integer payload_len);
    reg [15:0] crc;
    begin
      packet[0] = SPI_MAGIC;
      packet[1] = PROTOCOL_VERSION;
      packet[2] = command;
      packet[3] = 0;
      packet[4] = txid[15:8];
      packet[5] = txid[7:0];
      packet[6] = payload_len[15:8];
      packet[7] = payload_len[7:0];
      for (index = 0; index < payload_len; index = index + 1)
        packet[8 + index] = index[7:0] ^ 8'h5A;
      crc = 16'hFFFF;
      for (index = 0; index < 8 + payload_len; index = index + 1)
        crc = crc_update(crc, packet[index]);
      packet[8 + payload_len] = crc[15:8];
      packet[9 + payload_len] = crc[7:0];
      packet_length = 10 + payload_len;
    end
  endtask

  task automatic shift_byte(input [7:0] value);
    integer bit_index;
    begin
      for (bit_index = 7; bit_index >= 0; bit_index = bit_index - 1) begin
        mosi = value[bit_index];
        repeat (4) @(posedge clk);
        sck = 1;
        repeat (4) @(posedge clk);
        sck = 0;
      end
    end
  endtask

  task automatic send_packet;
    begin
      cs_n = 0;
      repeat (5) @(posedge clk);
      for (index = 0; index < packet_length; index = index + 1)
        shift_byte(packet[index]);
      repeat (4) @(posedge clk);
      cs_n = 1;
      repeat (5) @(posedge clk);
    end
  endtask

  task automatic send_packet_tight_final_edge;
    integer bit_index;
    begin
      cs_n = 0;
      repeat (5) @(posedge clk);
      for (index = 0; index < packet_length - 1; index = index + 1)
        shift_byte(packet[index]);
      for (bit_index = 7; bit_index > 0; bit_index = bit_index - 1) begin
        mosi = packet[packet_length - 1][bit_index];
        repeat (4) @(posedge clk);
        sck = 1;
        repeat (4) @(posedge clk);
        sck = 0;
      end
      mosi = packet[packet_length - 1][0];
      repeat (4) @(posedge clk);
      sck = 1;
      cs_n = 1;
      repeat (8) @(posedge clk);
      sck = 0;
      repeat (5) @(posedge clk);
    end
  endtask

  always @(posedge clk) begin
    if (transport_error_valid && transport_error_code == ERR_BAD_CRC)
      bad_crc_seen <= 1;
    if (transport_error_valid && transport_error_code == ERR_BAD_LENGTH) begin
      bad_length_seen <= 1;
      bad_length_detail_seen <= request_payload_length;
      bad_length_command_seen <= transport_error_command;
      bad_length_txid_seen <= transport_error_txid;
    end
  end

  initial begin
    bad_crc_seen = 0;
    bad_length_seen = 0;
    bad_length_detail_seen = 0;
    bad_length_command_seen = 0;
    bad_length_txid_seen = 0;
    repeat (4) @(posedge clk);
    rst_n = 1;
    repeat (4) @(posedge clk);

    build_packet(CMD_POLY_WRITE_CHUNK, 16'h1234, 66);
    send_packet();
    index = 0;
    while (!request_valid && index < 300) begin
      @(posedge clk);
      index = index + 1;
    end
    if (!request_valid) $fatal(1, "valid SPI packet did not produce request_valid");
    if (request_command != CMD_POLY_WRITE_CHUNK || request_txid != 16'h1234 ||
        request_payload_length != 66 || request_payload[7:0] != 8'h5A ||
        request_payload[8*65 +: 8] != (8'd65 ^ 8'h5A))
      $fatal(1, "valid SPI packet fields mismatch");
    $display("PASS spi_mode0_max_payload_request");

    build_packet(CMD_GET_STATUS, 16'h0E0F, 0);
    bad_length_seen = 0;
    send_packet_tight_final_edge();
    index = 0;
    while (!request_valid && index < 300) begin
      @(posedge clk);
      index = index + 1;
    end
    if (!request_valid)
      $fatal(1, "tight final SCK/CS request did not produce request_valid");
    if (request_command != CMD_GET_STATUS || request_txid != 16'h0E0F ||
        request_payload_length != 0 || bad_length_seen)
      $fatal(1, "tight final SCK/CS request was not retained as 10 bytes");
    $display("PASS spi_final_sck_cs_race_settled");

    build_packet(CMD_GET_INFO, 16'h0102, 0);
    packet[9] = packet[9] ^ 8'h01;
    send_packet();
    repeat (100) @(posedge clk);
    if (!bad_crc_seen) $fatal(1, "bad SPI CRC was not reported");
    $display("PASS spi_bad_crc_rejected");

    build_packet(CMD_GET_STATUS, 16'h0203, 0);
    packet_length = 9;
    bad_length_seen = 0;
    send_packet();
    repeat (100) @(posedge clk);
    if (!bad_length_seen) $fatal(1, "short SPI packet was not reported");
    if (bad_length_command_seen != CMD_GET_STATUS ||
        bad_length_txid_seen != 16'h0203 ||
        bad_length_detail_seen != 16'h1200)
      $fatal(1, "BAD_LENGTH detail mismatch: cmd=%02x txid=%04x detail=%04x",
             bad_length_command_seen, bad_length_txid_seen,
             bad_length_detail_seen);
    $display("PASS spi_bad_length_detail_count9_length0");

    if (!response_ready) $fatal(1, "response builder not ready");
    @(negedge clk);
    response_command = CMD_GET_INFO;
    response_flags = FLAG_RESPONSE;
    response_txid = 16'h0102;
    response_payload_length = 2;
    response_payload[7:0] = 8'hAA;
    response_payload[15:8] = 8'h55;
    response_commit = 1;
    @(negedge clk);
    response_commit = 0;
    index = 0;
    while (!mailbox_pending && index < 100) begin
      @(posedge clk);
      index = index + 1;
    end
    if (!mailbox_pending) $fatal(1, "response mailbox did not become pending");
    if (dut.tx_mem[0] != SPI_MAGIC || dut.tx_mem[2] != CMD_GET_INFO ||
        dut.tx_mem[8] != 8'hAA || dut.tx_mem[9] != 8'h55)
      $fatal(1, "SPI response packet build mismatch");
    $display("PASS spi_response_mailbox_build");
    $finish;
  end
endmodule
