module spi_packet_endpoint (
    input  logic         clk_i,
    input  logic         rst_ni,
    input  logic         spi_sck_i,
    input  logic         spi_mosi_i,
    input  logic         spi_cs_ni,
    output logic         spi_miso_bit_o,

    output logic         request_valid_o,
    output logic [7:0]   request_command_o,
    output logic [7:0]   request_flags_o,
    output logic [15:0]  request_txid_o,
    output logic [15:0]  request_payload_length_o,
    output logic [527:0] request_payload_o,
    output logic [31:0]  request_fingerprint_o,

    output logic         transport_error_valid_o,
    output logic [7:0]   transport_error_command_o,
    output logic [15:0]  transport_error_txid_o,
    output logic [15:0]  transport_error_code_o,

    input  logic         response_commit_i,
    input  logic [7:0]   response_command_i,
    input  logic [7:0]   response_flags_i,
    input  logic [15:0]  response_txid_i,
    input  logic [15:0]  response_payload_length_i,
    input  logic [527:0] response_payload_i,
    output logic         response_ready_o,
    output logic         mailbox_pending_o
);
  import trinity_spi_pkg::*;

  logic sck_meta, sck_sync, sck_prev;
  logic mosi_meta, mosi_sync;
  logic cs_meta, cs_sync, cs_prev;
  wire sck_rise = sck_sync & ~sck_prev;
  wire sck_fall = ~sck_sync & sck_prev;
  wire cs_fall = cs_prev & ~cs_sync;
  wire cs_rise = ~cs_prev & cs_sync;

  logic [7:0] rx_mem [0:SPI_MAX_PACKET-1];
  logic [7:0] tx_mem [0:SPI_MAX_PACKET-1];
  logic [7:0] rx_shift, tx_shift;
  logic [2:0] rx_bit_count, tx_bit_count;
  logic [6:0] rx_byte_count, tx_byte_index;
  logic [15:0] tx_bits_sent;
  logic rx_mode, tx_mode;
  logic [6:0] transaction_byte_count;

  typedef enum logic [1:0] {PARSE_IDLE, PARSE_HEADER, PARSE_CRC} parse_state_e;
  parse_state_e parse_state;
  logic [15:0] parse_payload_length;
  logic [6:0] parse_index;
  logic [15:0] parse_crc;
  logic [31:0] parse_fingerprint;

  typedef enum logic [2:0] {BUILD_IDLE, BUILD_DATA, BUILD_CRC_HI, BUILD_CRC_LO} build_state_e;
  build_state_e build_state;
  logic [7:0] build_command, build_flags;
  logic [15:0] build_txid, build_payload_length;
  logic [527:0] build_payload_shift;
  logic [6:0] build_index;
  logic [15:0] build_crc;
  logic [15:0] mailbox_length;

  function automatic logic [31:0] crc32c_update_byte(
      input logic [31:0] crc_in,
      input logic [7:0] data
  );
    logic [31:0] c;
    integer bit_index;
    begin
      c = crc_in ^ {24'd0, data};
      for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1)
        c = c[0] ? ((c >> 1) ^ 32'h82F63B78) : (c >> 1);
      crc32c_update_byte = c;
    end
  endfunction

  function automatic logic fingerprint_byte_selected(input logic [6:0] index);
    begin
      fingerprint_byte_selected = (index == 7'd2) || (index == 7'd3) ||
                                  (index == 7'd6) || (index == 7'd7) ||
                                  (index >= 7'd8);
    end
  endfunction

  function automatic logic [7:0] response_data_byte(input logic [6:0] index);
    begin
      case (index)
        7'd0: response_data_byte = SPI_MAGIC;
        7'd1: response_data_byte = PROTOCOL_VERSION;
        7'd2: response_data_byte = build_command;
        7'd3: response_data_byte = build_flags;
        7'd4: response_data_byte = build_txid[15:8];
        7'd5: response_data_byte = build_txid[7:0];
        7'd6: response_data_byte = build_payload_length[15:8];
        7'd7: response_data_byte = build_payload_length[7:0];
        default: response_data_byte = build_payload_shift[7:0];
      endcase
    end
  endfunction

  function automatic logic [15:0] bad_length_detail(
      input logic [6:0] byte_count
  );
    logic length_high_nonzero;
    logic [7:0] length_low_or_unknown;
    begin
      length_high_nonzero = (byte_count > 7'd7) && (rx_mem[6] != 8'h00);
      length_low_or_unknown = (byte_count > 7'd7) ? rx_mem[7] : 8'hFF;
      bad_length_detail = {byte_count, length_high_nonzero,
                           length_low_or_unknown};
    end
  endfunction

  wire [15:0] parse_crc_next = crc16_update_byte(parse_crc, rx_mem[parse_index]);
  wire [31:0] parse_fingerprint_next = fingerprint_byte_selected(parse_index) ?
      crc32c_update_byte(parse_fingerprint, rx_mem[parse_index]) : parse_fingerprint;
  wire [15:0] build_crc_next = crc16_update_byte(build_crc, response_data_byte(build_index));

  assign response_ready_o = (build_state == BUILD_IDLE) && !mailbox_pending_o;
  assign spi_miso_bit_o = tx_mode ? tx_shift[7] : 1'b0;

  integer pi;
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      sck_meta <= 1'b0; sck_sync <= 1'b0; sck_prev <= 1'b0;
      mosi_meta <= 1'b0; mosi_sync <= 1'b0;
      cs_meta <= 1'b1; cs_sync <= 1'b1; cs_prev <= 1'b1;
      rx_shift <= 0; tx_shift <= 0;
      rx_bit_count <= 0; tx_bit_count <= 0;
      rx_byte_count <= 0; tx_byte_index <= 0; tx_bits_sent <= 0;
      rx_mode <= 1'b0; tx_mode <= 1'b0;
      transaction_byte_count <= 0;
      parse_state <= PARSE_IDLE; parse_payload_length <= 0;
      parse_index <= 0; parse_crc <= 16'hFFFF; parse_fingerprint <= 32'hFFFFFFFF;
      request_valid_o <= 1'b0; request_command_o <= 0; request_flags_o <= 0;
      request_txid_o <= 0; request_payload_length_o <= 0; request_payload_o <= 0;
      request_fingerprint_o <= 32'd0;
      transport_error_valid_o <= 1'b0; transport_error_command_o <= 0;
      transport_error_txid_o <= 0; transport_error_code_o <= 0;
      build_state <= BUILD_IDLE; build_command <= 0; build_flags <= 0;
      build_txid <= 0; build_payload_length <= 0; build_payload_shift <= 0;
      build_index <= 0; build_crc <= 16'hFFFF;
      mailbox_pending_o <= 1'b0; mailbox_length <= 0;
    end else begin
      sck_meta <= spi_sck_i;
      sck_sync <= sck_meta;
      sck_prev <= sck_sync;
      mosi_meta <= spi_mosi_i;
      mosi_sync <= mosi_meta;
      cs_meta <= spi_cs_ni;
      cs_sync <= cs_meta;
      cs_prev <= cs_sync;

      request_valid_o <= 1'b0;
      transport_error_valid_o <= 1'b0;

      if (cs_fall) begin
        rx_bit_count <= 0;
        tx_bit_count <= 0;
        rx_byte_count <= 0;
        tx_byte_index <= 0;
        tx_bits_sent <= 0;
        rx_shift <= 0;
        if (mailbox_pending_o) begin
          tx_mode <= 1'b1;
          rx_mode <= 1'b0;
          tx_shift <= tx_mem[0];
        end else begin
          tx_mode <= 1'b0;
          rx_mode <= 1'b1;
        end
      end

      if (!cs_sync && rx_mode && sck_rise) begin
        rx_shift <= {rx_shift[6:0], mosi_sync};
        if (rx_bit_count == 3'd7) begin
          if (rx_byte_count < SPI_MAX_PACKET)
            rx_mem[rx_byte_count] <= {rx_shift[6:0], mosi_sync};
          rx_byte_count <= rx_byte_count + 1'b1;
          rx_bit_count <= 0;
        end else begin
          rx_bit_count <= rx_bit_count + 1'b1;
        end
      end

      if (!cs_sync && tx_mode && sck_rise)
        tx_bits_sent <= tx_bits_sent + 1'b1;

      if (!cs_sync && tx_mode && sck_fall) begin
        if (tx_bit_count == 3'd7) begin
          tx_bit_count <= 0;
          if (tx_byte_index + 1'b1 < mailbox_length) begin
            tx_byte_index <= tx_byte_index + 1'b1;
            tx_shift <= tx_mem[tx_byte_index + 1'b1];
          end else begin
            tx_shift <= 8'h00;
          end
        end else begin
          tx_shift <= {tx_shift[6:0],1'b0};
          tx_bit_count <= tx_bit_count + 1'b1;
        end
      end

      if (cs_rise) begin
        if (rx_mode) begin
          transaction_byte_count <= rx_byte_count;
          if (parse_state == PARSE_IDLE)
            parse_state <= PARSE_HEADER;
        end
        if (tx_mode && (tx_bits_sent >= (mailbox_length << 3)))
          mailbox_pending_o <= 1'b0;
        rx_mode <= 1'b0;
        tx_mode <= 1'b0;
      end

      case (parse_state)
        PARSE_IDLE: begin end
        PARSE_HEADER: begin
          transport_error_command_o <= (transaction_byte_count > 2) ? rx_mem[2] : 8'h00;
          transport_error_txid_o <= (transaction_byte_count > 5) ? {rx_mem[4],rx_mem[5]} : 16'h0000;
          if (transaction_byte_count < 10) begin
            request_payload_length_o <= bad_length_detail(transaction_byte_count);
            transport_error_code_o <= ERR_BAD_LENGTH;
            transport_error_valid_o <= 1'b1;
            parse_state <= PARSE_IDLE;
          end else if (rx_mem[0] != SPI_MAGIC) begin
            transport_error_code_o <= ERR_BAD_MAGIC;
            transport_error_valid_o <= 1'b1;
            parse_state <= PARSE_IDLE;
          end else if (rx_mem[1] != PROTOCOL_VERSION) begin
            transport_error_code_o <= ERR_BAD_VERSION;
            transport_error_valid_o <= 1'b1;
            parse_state <= PARSE_IDLE;
          end else if (!flags_valid(rx_mem[3]) || (rx_mem[3] != 8'h00)) begin
            transport_error_code_o <= ERR_BAD_FLAGS;
            transport_error_valid_o <= 1'b1;
            parse_state <= PARSE_IDLE;
          end else if ({rx_mem[6],rx_mem[7]} > SPI_MAX_PAYLOAD ||
                       transaction_byte_count != (10 + {rx_mem[6],rx_mem[7]})) begin
            request_payload_length_o <= bad_length_detail(transaction_byte_count);
            transport_error_code_o <= ERR_BAD_LENGTH;
            transport_error_valid_o <= 1'b1;
            parse_state <= PARSE_IDLE;
          end else begin
            parse_payload_length <= {rx_mem[6],rx_mem[7]};
            parse_index <= 0;
            parse_crc <= 16'hFFFF;
            parse_fingerprint <= 32'hFFFFFFFF;
            parse_state <= PARSE_CRC;
          end
        end
        PARSE_CRC: begin
          if (parse_index == (7 + parse_payload_length)) begin
            if (parse_crc_next == {rx_mem[8+parse_payload_length],rx_mem[9+parse_payload_length]}) begin
              request_command_o <= rx_mem[2];
              request_flags_o <= rx_mem[3];
              request_txid_o <= {rx_mem[4],rx_mem[5]};
              request_payload_length_o <= parse_payload_length;
              request_fingerprint_o <= ~parse_fingerprint_next;
              request_payload_o <= '0;
              for (pi = 0; pi < SPI_MAX_PAYLOAD; pi = pi + 1)
                if (pi < parse_payload_length)
                  request_payload_o[8*pi +: 8] <= rx_mem[8+pi];
              request_valid_o <= 1'b1;
            end else begin
              transport_error_command_o <= rx_mem[2];
              transport_error_txid_o <= {rx_mem[4],rx_mem[5]};
              transport_error_code_o <= ERR_BAD_CRC;
              transport_error_valid_o <= 1'b1;
            end
            parse_state <= PARSE_IDLE;
          end else begin
            parse_crc <= parse_crc_next;
            parse_fingerprint <= parse_fingerprint_next;
            parse_index <= parse_index + 1'b1;
          end
        end
        default: parse_state <= PARSE_IDLE;
      endcase

      case (build_state)
        BUILD_IDLE: begin
          if (response_commit_i && !mailbox_pending_o) begin
            build_command <= response_command_i;
            build_flags <= response_flags_i;
            build_txid <= response_txid_i;
            build_payload_length <= response_payload_length_i;
            build_payload_shift <= response_payload_i;
            build_index <= 0;
            build_crc <= 16'hFFFF;
            build_state <= BUILD_DATA;
          end
        end
        BUILD_DATA: begin
          tx_mem[build_index] <= response_data_byte(build_index);
          build_crc <= build_crc_next;
          if (build_index >= 7'd8)
            build_payload_shift <= {8'd0, build_payload_shift[527:8]};
          if (build_index == (7 + build_payload_length)) begin
            build_state <= BUILD_CRC_HI;
          end else begin
            build_index <= build_index + 1'b1;
          end
        end
        BUILD_CRC_HI: begin
          tx_mem[8+build_payload_length] <= build_crc[15:8];
          build_state <= BUILD_CRC_LO;
        end
        BUILD_CRC_LO: begin
          tx_mem[9+build_payload_length] <= build_crc[7:0];
          mailbox_length <= build_payload_length + 16'd10;
          mailbox_pending_o <= 1'b1;
          build_state <= BUILD_IDLE;
        end
        default: build_state <= BUILD_IDLE;
      endcase
    end
  end
endmodule
