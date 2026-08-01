#ifndef TRINITY_PROTOCOL_COMMON_H
#define TRINITY_PROTOCOL_COMMON_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRINITY_PROTOCOL_VERSION 0x01u
#define TRINITY_FLAG_RESPONSE 0x01u
#define TRINITY_FLAG_ERROR 0x02u
#define TRINITY_FLAG_MORE 0x04u
#define TRINITY_FLAG_EVENT 0x08u
#define TRINITY_FLAG_ALLOWED_MASK 0x0Fu

typedef enum {
    TRINITY_OK = 0x0000,
    TRINITY_BAD_MAGIC = 0x0101,
    TRINITY_BAD_VERSION = 0x0102,
    TRINITY_BAD_LENGTH = 0x0103,
    TRINITY_BAD_CRC = 0x0104,
    TRINITY_BAD_FLAGS = 0x0105,
    TRINITY_BAD_COMMAND = 0x0201,
    TRINITY_BAD_STATE = 0x0202,
    TRINITY_BUSY = 0x0203,
    TRINITY_RESULT_PENDING = 0x0204,
    TRINITY_TRANSACTION_CONFLICT = 0x0205,
    TRINITY_OUTCOME_UNKNOWN_TARGET_RESET = 0x0206,
    TRINITY_BAD_CHUNK_INDEX = 0x0301,
    TRINITY_CHUNK_CONFLICT = 0x0302,
    TRINITY_INCOMPLETE_INPUT = 0x0303,
    TRINITY_RESULT_NOT_READY = 0x0304,
    TRINITY_SELF_TEST_FAILED = 0x0305,
    TRINITY_MLKEM_SHARED_SECRET_MISMATCH = 0x0306,
    TRINITY_SESSION_ID_COLLISION = 0x0401,
    TRINITY_BAD_SESSION = 0x0402,
    TRINITY_ZEROIZED = 0x0403,
    TRINITY_REPLAY = 0x0501,
    TRINITY_STALE_SEQUENCE = 0x0502,
    TRINITY_BAD_TAG = 0x0503,
    TRINITY_MALFORMED_FRAME = 0x0504,
    TRINITY_FRAME_TIMEOUT = 0x0505,
    TRINITY_RESULT_PENDING_DROP = 0x0506,
    TRINITY_AUTH_THRESHOLD = 0x0601,
    TRINITY_COMMIT_REJECTED = 0x0602,
    TRINITY_SESSION_COMMIT_FAILED = 0x0603,
    TRINITY_HEARTBEAT_TIMEOUT = 0x0604,
    TRINITY_FAULT_LOCKED = 0x0605,
    TRINITY_INTERNAL_FAULT = 0x0701,
    TRINITY_NOT_SUPPORTED = 0x0702
} trinity_error_code_t;

typedef enum {
    TRINITY_TXN_NONE = 0,
    TRINITY_TXN_ACCEPTED = 1,
    TRINITY_TXN_RUNNING = 2,
    TRINITY_TXN_SUCCEEDED = 3,
    TRINITY_TXN_FAILED = 4,
    TRINITY_TXN_ZEROIZED = 5,
    TRINITY_TXN_OUTCOME_UNKNOWN = 6
} trinity_transaction_state_t;

uint16_t trinity_crc16_ccitt_false(const uint8_t *data, size_t length);
uint32_t trinity_crc32c(const uint8_t *data, size_t length);
uint16_t trinity_read_be16(const uint8_t *p);
uint32_t trinity_read_be32(const uint8_t *p);
uint64_t trinity_read_be64(const uint8_t *p);
void trinity_write_be16(uint8_t *p, uint16_t value);
void trinity_write_be32(uint8_t *p, uint32_t value);
void trinity_write_be64(uint8_t *p, uint64_t value);
int trinity_flags_valid(uint8_t flags);

#ifdef __cplusplus
}
#endif
#endif
