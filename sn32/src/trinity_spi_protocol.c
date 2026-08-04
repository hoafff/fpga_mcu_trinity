#include "trinity_spi_protocol.h"

#include <string.h>

trinity_error_code_t trinity_spi_encode(const trinity_spi_packet_t *packet,
                                         uint8_t *output, size_t output_capacity,
                                         size_t *output_length) {
    size_t total;
    uint16_t crc;
    if (packet == NULL || output == NULL || output_length == NULL) return TRINITY_INTERNAL_FAULT;
    if (packet->version != TRINITY_PROTOCOL_VERSION) return TRINITY_BAD_VERSION;
    if (!trinity_flags_valid(packet->flags)) return TRINITY_BAD_FLAGS;
    if (packet->payload_length > TRINITY_SPI_MAX_PAYLOAD) return TRINITY_BAD_LENGTH;
    total = TRINITY_SPI_HEADER_SIZE + packet->payload_length + TRINITY_SPI_CRC_SIZE;
    if (output_capacity < total) return TRINITY_BAD_LENGTH;
    output[0] = TRINITY_SPI_MAGIC;
    output[1] = packet->version;
    output[2] = packet->command;
    output[3] = packet->flags;
    trinity_write_be16(output + 4, packet->transaction_id);
    trinity_write_be16(output + 6, packet->payload_length);
    memcpy(output + 8, packet->payload, packet->payload_length);
    crc = trinity_crc16_ccitt_false(output, total - 2u);
    trinity_write_be16(output + total - 2u, crc);
    *output_length = total;
    return TRINITY_OK;
}

trinity_error_code_t trinity_spi_decode(const uint8_t *input, size_t input_length,
                                         trinity_spi_packet_t *packet) {
    uint16_t payload_length, expected_crc;
    size_t expected_length;
    if (input == NULL || packet == NULL) return TRINITY_INTERNAL_FAULT;
    if (input_length < TRINITY_SPI_HEADER_SIZE + TRINITY_SPI_CRC_SIZE) return TRINITY_BAD_LENGTH;
    if (input[0] != TRINITY_SPI_MAGIC) return TRINITY_BAD_MAGIC;
    if (input[1] != TRINITY_PROTOCOL_VERSION) return TRINITY_BAD_VERSION;
    if (!trinity_flags_valid(input[3])) return TRINITY_BAD_FLAGS;
    payload_length = trinity_read_be16(input + 6);
    if (payload_length > TRINITY_SPI_MAX_PAYLOAD) return TRINITY_BAD_LENGTH;
    expected_length = TRINITY_SPI_HEADER_SIZE + payload_length + TRINITY_SPI_CRC_SIZE;
    if (input_length != expected_length) return TRINITY_BAD_LENGTH;
    expected_crc = trinity_read_be16(input + input_length - 2u);
    if (expected_crc != trinity_crc16_ccitt_false(input, input_length - 2u)) return TRINITY_BAD_CRC;
    packet->version = input[1];
    packet->command = input[2];
    packet->flags = input[3];
    packet->transaction_id = trinity_read_be16(input + 4);
    packet->payload_length = payload_length;
    memcpy(packet->payload, input + 8, payload_length);
    return TRINITY_OK;
}

int trinity_spi_bad_length_detail_is_short_cs(uint16_t detail) {
    uint8_t byte_count_and_length_high;

    /* Older Primer images reported no detail for the same startup residue. */
    if (detail == 0u) return 1;

    /*
     * Diagnostic P1 encodes BAD_LENGTH detail as:
     *   {transaction_byte_count[6:0], length_high_nonzero,
     *    length_low_or_0xff}
     * A transaction shorter than the eight-byte header has no complete length
     * field, so its low byte is 0xff and length_high_nonzero must be clear.
     */
    if ((detail & UINT16_C(0x00FF)) != UINT16_C(0x00FF)) return 0;
    byte_count_and_length_high = (uint8_t)(detail >> 8);
    return (byte_count_and_length_high & 1u) == 0u &&
           (byte_count_and_length_high >> 1) < TRINITY_SPI_HEADER_SIZE;
}

int trinity_spi_bad_length_detail_proves_truncation(
    uint16_t detail, size_t expected_wire_length) {
    uint8_t byte_count_and_length_high;
    size_t byte_count;

    /* A legacy zero detail carries no byte-count proof by itself. */
    if (detail == 0u ||
        expected_wire_length < TRINITY_SPI_HEADER_SIZE + TRINITY_SPI_CRC_SIZE ||
        expected_wire_length > TRINITY_SPI_MAX_PACKET)
        return 0;

    byte_count_and_length_high = (uint8_t)(detail >> 8);
    byte_count = (size_t)(byte_count_and_length_high >> 1);
    if (byte_count >= expected_wire_length) return 0;

    /* Before byte 8, the diagnostic encoding must mark length as unknown. */
    if (byte_count < TRINITY_SPI_HEADER_SIZE) {
        return (byte_count_and_length_high & 1u) == 0u &&
               (detail & UINT16_C(0x00FF)) == UINT16_C(0x00FF);
    }

    /* At byte 8 or later the captured length field may contain any value. */
    return 1;
}

uint32_t trinity_spi_request_fingerprint(uint8_t command, uint8_t flags,
                                         const uint8_t *payload, uint16_t payload_length) {
    uint32_t crc = 0xFFFFFFFFu;
    uint8_t header[4];
    size_t i;
    unsigned bit;
    header[0] = command;
    header[1] = flags;
    trinity_write_be16(header + 2, payload_length);
    for (i = 0u; i < 4u + payload_length; ++i) {
        uint8_t value = (i < 4u) ? header[i] : payload[i - 4u];
        crc ^= value;
        for (bit = 0u; bit < 8u; ++bit) crc = (crc & 1u) ? (crc >> 1) ^ 0x82F63B78u : crc >> 1;
    }
    return crc ^ 0xFFFFFFFFu;
}

trinity_error_code_t trinity_spi_build_poly_chunk(uint8_t slot_id, uint8_t chunk_index,
                                                   const uint8_t data[64],
                                                   uint8_t output[66]) {
    if (data == NULL || output == NULL) return TRINITY_INTERNAL_FAULT;
    if (slot_id > 1u) return TRINITY_BAD_STATE;
    if (chunk_index > 7u) return TRINITY_BAD_CHUNK_INDEX;
    output[0] = slot_id;
    output[1] = chunk_index;
    memcpy(output + 2, data, 64u);
    return TRINITY_OK;
}
