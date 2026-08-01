#include "trinity_protocol_common.h"

uint16_t trinity_crc16_ccitt_false(const uint8_t *data, size_t length) {
    uint16_t crc = 0xFFFFu;
    size_t i;
    unsigned bit;
    if (data == NULL && length != 0u) return 0u;
    for (i = 0u; i < length; ++i) {
        crc ^= (uint16_t)data[i] << 8;
        for (bit = 0u; bit < 8u; ++bit) {
            crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u) : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

uint32_t trinity_crc32c(const uint8_t *data, size_t length) {
    uint32_t crc = 0xFFFFFFFFu;
    size_t i;
    unsigned bit;
    if (data == NULL && length != 0u) return 0u;
    for (i = 0u; i < length; ++i) {
        crc ^= data[i];
        for (bit = 0u; bit < 8u; ++bit) crc = (crc & 1u) ? (crc >> 1) ^ 0x82F63B78u : crc >> 1;
    }
    return crc ^ 0xFFFFFFFFu;
}

uint16_t trinity_read_be16(const uint8_t *p) { return (uint16_t)(((uint16_t)p[0] << 8) | p[1]); }
uint32_t trinity_read_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}
uint64_t trinity_read_be64(const uint8_t *p) { return ((uint64_t)trinity_read_be32(p) << 32) | trinity_read_be32(p + 4); }
void trinity_write_be16(uint8_t *p, uint16_t value) { p[0] = (uint8_t)(value >> 8); p[1] = (uint8_t)value; }
void trinity_write_be32(uint8_t *p, uint32_t value) {
    p[0] = (uint8_t)(value >> 24); p[1] = (uint8_t)(value >> 16); p[2] = (uint8_t)(value >> 8); p[3] = (uint8_t)value;
}
void trinity_write_be64(uint8_t *p, uint64_t value) { trinity_write_be32(p, (uint32_t)(value >> 32)); trinity_write_be32(p + 4, (uint32_t)value); }
int trinity_flags_valid(uint8_t flags) { return (flags & (uint8_t)~TRINITY_FLAG_ALLOWED_MASK) == 0u; }
