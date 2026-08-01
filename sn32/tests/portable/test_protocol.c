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
    test_poly_chunk_and_fingerprint();
    puts("PASS: Trinity portable protocol tests");
    return 0;
}
