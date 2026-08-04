#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "trinity_pc_protocol.h"
#include "trinity_spi_protocol.h"

static void test_crc(void) {
    static const uint8_t s[] = "123456789";
    assert(trinity_crc16_ccitt_false(s, 9u) == 0x29B1u);
    assert(trinity_crc32c(s, 9u) == 0xE3069283u);
}

static void test_pc_roundtrip(void) {
    trinity_pc_frame_t in = {0}, out = {0};
    uint8_t wire[TRINITY_PC_MAX_WIRE_FRAME];
    size_t wire_length = 0u;
    in.version = TRINITY_PROTOCOL_VERSION;
    in.command = TRINITY_PC_PING;
    in.transaction_id = 0x1234u;
    in.payload_length = 5u;
    in.payload[0] = 0u; in.payload[1] = 'a'; in.payload[2] = 'b'; in.payload[3] = 0u; in.payload[4] = 'c';
    assert(trinity_pc_encode_wire(&in, wire, sizeof(wire), &wire_length) == TRINITY_OK);
    assert(wire[wire_length - 1u] == 0u);
    assert(trinity_pc_decode_wire(wire, wire_length, &out) == TRINITY_OK);
    assert(out.transaction_id == in.transaction_id);
    assert(out.payload_length == in.payload_length);
    assert(memcmp(out.payload, in.payload, in.payload_length) == 0);
}

static void test_spi_roundtrip(void) {
    trinity_spi_packet_t in = {0}, out = {0};
    uint8_t encoded[TRINITY_SPI_MAX_PACKET];
    size_t length = 0u, i;
    in.version = TRINITY_PROTOCOL_VERSION;
    in.command = TRINITY_SPI_POLY_WRITE_CHUNK;
    in.transaction_id = 0xBEEFu;
    in.payload_length = 66u;
    for (i = 0u; i < 66u; ++i) in.payload[i] = (uint8_t)i;
    assert(trinity_spi_encode(&in, encoded, sizeof(encoded), &length) == TRINITY_OK);
    assert(length == 76u);
    assert(trinity_spi_decode(encoded, length, &out) == TRINITY_OK);
    assert(out.transaction_id == in.transaction_id);
    assert(memcmp(out.payload, in.payload, 66u) == 0);
}

static void test_short_cs_startup_residue(void) {
    static const uint8_t frame[] = {
        0xA5u, 0x01u, 0x00u, 0x03u, 0x00u, 0x00u, 0x00u, 0x06u,
        0x01u, 0x03u, 0x01u, 0x00u, 0x00u, 0xFFu, 0xBAu, 0x95u,
    };
    trinity_spi_packet_t packet = {0};

    assert(sizeof(frame) == 16u);
    assert(trinity_crc16_ccitt_false(frame, sizeof(frame) - 2u) == 0xBA95u);
    assert(trinity_spi_decode(frame, sizeof(frame), &packet) == TRINITY_OK);
    assert(packet.command == 0u);
    assert(packet.transaction_id == 0u);
    assert(packet.flags == (TRINITY_FLAG_RESPONSE | TRINITY_FLAG_ERROR));
    assert(packet.payload_length == 6u);
    assert(trinity_read_be16(packet.payload) == TRINITY_BAD_LENGTH);
    assert(trinity_spi_bad_length_detail_is_short_cs(
        trinity_read_be16(&packet.payload[4])));

    assert(trinity_spi_bad_length_detail_is_short_cs(0x0000u));
    assert(trinity_spi_bad_length_detail_is_short_cs(0x0EFFu));
    assert(!trinity_spi_bad_length_detail_is_short_cs(0x0100u));
    assert(!trinity_spi_bad_length_detail_is_short_cs(0x10FFu));
}

static void test_bad_length_truncation_proof(void) {
    static const uint8_t hardware_frames[][16] = {
        {0xA5u, 0x01u, 0x35u, 0x03u, 0x00u, 0x00u, 0x00u, 0x06u,
         0x01u, 0x03u, 0x01u, 0x00u, 0x08u, 0xFFu, 0x64u, 0x6Du},
        {0xA5u, 0x01u, 0x40u, 0x03u, 0x02u, 0x40u, 0x00u, 0x06u,
         0x01u, 0x03u, 0x01u, 0x00u, 0x12u, 0x27u, 0xC9u, 0xE2u},
        {0xA5u, 0x01u, 0x80u, 0x03u, 0x00u, 0xC0u, 0x00u, 0x06u,
         0x01u, 0x03u, 0x01u, 0x00u, 0x12u, 0x25u, 0xFFu, 0x79u},
    };
    trinity_spi_packet_t packet = {0};
    size_t i;

    for (i = 0u; i < sizeof(hardware_frames) / sizeof(hardware_frames[0]);
         ++i) {
        assert(trinity_spi_decode(hardware_frames[i],
                                  sizeof(hardware_frames[i]),
                                  &packet) == TRINITY_OK);
        assert(packet.flags ==
               (TRINITY_FLAG_RESPONSE | TRINITY_FLAG_ERROR));
        assert(packet.payload_length == 6u);
        assert(trinity_read_be16(packet.payload) == TRINITY_BAD_LENGTH);
        assert(trinity_spi_bad_length_detail_proves_truncation(
            trinity_read_be16(&packet.payload[4]), 10u));
    }

    /* Hardware captures: four bytes, then nine bytes of a ten-byte request. */
    assert(trinity_spi_bad_length_detail_proves_truncation(0x08FFu, 10u));
    assert(trinity_spi_bad_length_detail_proves_truncation(0x1225u, 10u));
    assert(trinity_spi_bad_length_detail_proves_truncation(0x1227u, 10u));

    /* An encoded eight-byte header is still short of the ten-byte wire frame. */
    assert(trinity_spi_bad_length_detail_proves_truncation(0x10FFu, 10u));

    /* Legacy zero detail and inconsistent pre-header encodings prove nothing. */
    assert(!trinity_spi_bad_length_detail_proves_truncation(0x0000u, 10u));
    assert(!trinity_spi_bad_length_detail_proves_truncation(0x0100u, 10u));

    /* A complete or over-complete capture is not a truncation proof. */
    assert(!trinity_spi_bad_length_detail_proves_truncation(0x1400u, 10u));
    assert(!trinity_spi_bad_length_detail_proves_truncation(0x1600u, 10u));
    assert(!trinity_spi_bad_length_detail_proves_truncation(0x08FFu, 9u));
    assert(!trinity_spi_bad_length_detail_proves_truncation(0x08FFu,
                                                             77u));
}

static void test_poly_chunk_and_fingerprint(void) {
    uint8_t data[64] = {0}, payload[66];
    uint32_t a, b, c;
    assert(trinity_spi_build_poly_chunk(0u, 7u, data, payload) == TRINITY_OK);
    assert(payload[0] == 0u && payload[1] == 7u);
    a = trinity_spi_request_fingerprint(TRINITY_SPI_STAGE_SESSION, 0u, payload, 66u);
    b = trinity_spi_request_fingerprint(TRINITY_SPI_STAGE_SESSION, 0u, payload, 66u);
    payload[65] ^= 1u;
    c = trinity_spi_request_fingerprint(TRINITY_SPI_STAGE_SESSION, 0u, payload, 66u);
    assert(a == b);
    assert(a != c);
}

int main(void) {
    test_crc();
    test_pc_roundtrip();
    test_spi_roundtrip();
    test_short_cs_startup_residue();
    test_bad_length_truncation_proof();
    test_poly_chunk_and_fingerprint();
    puts("PASS: Trinity portable protocol tests");
    return 0;
}
