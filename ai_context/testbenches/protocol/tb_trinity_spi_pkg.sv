`timescale 1ns/1ps
module tb_trinity_spi_pkg;
  import trinity_spi_pkg::*;
  logic [15:0] crc;
  initial begin
    if (SPI_MAX_PACKET != 76) $fatal(1, "bad SPI_MAX_PACKET");
    if (CMD_POLY_WRITE_CHUNK != 8'h21) $fatal(1, "bad command");
    if (ERR_BAD_FLAGS != 16'h0105) $fatal(1, "bad error code");
    if (!flags_valid(8'h0F)) $fatal(1, "valid flags rejected");
    if (flags_valid(8'h80)) $fatal(1, "reserved flags accepted");
    crc = 16'hFFFF;
    crc = crc16_update_byte(crc, "1");
    crc = crc16_update_byte(crc, "2");
    crc = crc16_update_byte(crc, "3");
    crc = crc16_update_byte(crc, "4");
    crc = crc16_update_byte(crc, "5");
    crc = crc16_update_byte(crc, "6");
    crc = crc16_update_byte(crc, "7");
    crc = crc16_update_byte(crc, "8");
    crc = crc16_update_byte(crc, "9");
    if (crc != 16'h29B1) $fatal(1, "CRC mismatch");
    $display("PASS: trinity_spi_pkg");
    $finish;
  end
endmodule
