#ifndef TRINITY_SPI_PROTOCOL_H
#define TRINITY_SPI_PROTOCOL_H

#include "trinity_protocol_common.h"

#ifdef __cplusplus
extern "C" {
#endif

#define TRINITY_SPI_MAGIC 0xA5u
#define TRINITY_SPI_HEADER_SIZE 8u
#define TRINITY_SPI_CRC_SIZE 2u
#define TRINITY_SPI_MAX_POLYNOMIAL_DATA 64u
#define TRINITY_SPI_MAX_PAYLOAD 66u
#define TRINITY_SPI_MAX_PACKET 76u

typedef enum {
    TRINITY_SPI_GET_INFO = 0x01,
    TRINITY_SPI_GET_STATUS = 0x02,
    TRINITY_SPI_RUN_SELF_TEST = 0x03,
    TRINITY_SPI_GET_TXN_RESULT = 0x04,
    TRINITY_SPI_RETIRE_TXN_RESULT = 0x05,
    TRINITY_SPI_ZEROIZE = 0x06,
    TRINITY_SPI_STAGE_SESSION = 0x07,
    TRINITY_SPI_COMMIT_SESSION = 0x08,
    TRINITY_SPI_ABORT_SESSION = 0x09,
    TRINITY_SPI_POLY_BEGIN = 0x20,
    TRINITY_SPI_POLY_WRITE_CHUNK = 0x21,
    TRINITY_SPI_POLY_EXECUTE = 0x22,
    TRINITY_SPI_POLY_READ_CHUNK = 0x23,
    TRINITY_SPI_POLY_RETIRE = 0x24,
    TRINITY_SPI_LOAD_TELEMETRY = 0x30,
    TRINITY_SPI_ENCRYPT_AND_SEND = 0x31,
    TRINITY_SPI_GET_RX_STATUS = 0x40,
    TRINITY_SPI_READ_AUTH_RESULT = 0x41,
    TRINITY_SPI_ACK_AUTH_RESULT = 0x42,
    TRINITY_SPI_CLEAR_DIAGNOSTIC_COUNTERS = 0x43
} trinity_spi_command_t;

typedef enum { TRINITY_TARGET_PRIMER1 = 1, TRINITY_TARGET_PRIMER2 = 2 } trinity_target_id_t;
typedef enum {
    TRINITY_SESSION_BOOT = 0, TRINITY_SESSION_SELF_TEST_REQUIRED = 1,
    TRINITY_SESSION_SELF_TEST_RUNNING = 2, TRINITY_SESSION_READY_NO_SESSION = 3,
    TRINITY_SESSION_STAGED = 4, TRINITY_SESSION_COMMITTED_BLOCKED = 5,
    TRINITY_SESSION_ACTIVE = 6, TRINITY_SESSION_ZEROIZE_BUSY = 7,
    TRINITY_SESSION_FAULT_LOCKED = 8
} trinity_session_state_t;
typedef enum {
    TRINITY_OPERATION_IDLE = 0, TRINITY_OPERATION_LOAD_INPUT = 1,
    TRINITY_OPERATION_READY_TO_EXECUTE = 2, TRINITY_OPERATION_EXECUTING = 3,
    TRINITY_OPERATION_RESULT_READY = 4
} trinity_operation_state_t;
typedef enum {
    TRINITY_RX_HUNT_SYNC = 0, TRINITY_RX_RECEIVE_BODY = 1,
    TRINITY_RX_VALIDATE = 2, TRINITY_RX_VERIFY_TAG = 3,
    TRINITY_RX_RESULT_PENDING = 4
} trinity_rx_state_t;

#define TRINITY_PENDING_RESPONSE_MAILBOX 0x01u
#define TRINITY_PENDING_SIDE_EFFECT_RESULT 0x02u
#define TRINITY_PENDING_AUTHENTICATED_RESULT 0x04u
#define TRINITY_SECURE_SELF_TEST_PASS 0x01u
#define TRINITY_SECURE_SESSION_STAGED 0x02u
#define TRINITY_SECURE_ENABLE 0x04u
#define TRINITY_SECURE_ZEROIZE_BUSY 0x08u
#define TRINITY_SECURE_FAULT_LOCKED 0x10u

#define TRINITY_SPI_CAP_SELF_TEST (1u << 0)
#define TRINITY_SPI_CAP_ZEROIZE (1u << 1)
#define TRINITY_SPI_CAP_TRANSACTION_RECONCILIATION (1u << 2)
#define TRINITY_SPI_CAP_SESSION_STAGE_COMMIT (1u << 3)
#define TRINITY_SPI_CAP_NTT (1u << 4)
#define TRINITY_SPI_CAP_INTT (1u << 5)
#define TRINITY_SPI_CAP_BASEMUL (1u << 6)
#define TRINITY_SPI_CAP_ASCON_ENCRYPT (1u << 7)
#define TRINITY_SPI_CAP_UART_TX (1u << 8)
#define TRINITY_SPI_CAP_ASCON_DECRYPT (1u << 9)
#define TRINITY_SPI_CAP_REPLAY_FILTER (1u << 10)
#define TRINITY_SPI_CAP_AUTH_RESULT_BUFFER (1u << 11)
#define TRINITY_SPI_CAP_DIAGNOSTICS (1u << 12)

typedef enum {
    TRINITY_TEST_PROFILE_QUICK = 0,
    TRINITY_TEST_PROFILE_FULL = 1,
    TRINITY_TEST_PROFILE_KAT = 2,
    TRINITY_TEST_PROFILE_DIAGNOSTIC = 3
} trinity_test_profile_t;

#define TRINITY_TEST_PROTOCOL (1u << 0)
#define TRINITY_TEST_MEMORY (1u << 1)
#define TRINITY_TEST_NTT (1u << 2)
#define TRINITY_TEST_INTT (1u << 3)
#define TRINITY_TEST_BASEMUL (1u << 4)
#define TRINITY_TEST_ASCON (1u << 5)
#define TRINITY_TEST_UART (1u << 6)
#define TRINITY_TEST_SESSION (1u << 7)
#define TRINITY_TEST_ZEROIZE (1u << 8)
#define TRINITY_TEST_HEARTBEAT (1u << 9)
#define TRINITY_ZEROIZE_ACTIVE_SESSION (1u << 0)
#define TRINITY_ZEROIZE_STAGED_SESSION (1u << 1)
#define TRINITY_ZEROIZE_POLYNOMIAL_BUFFERS (1u << 2)
#define TRINITY_ZEROIZE_TELEMETRY_OR_AUTH_RESULT (1u << 3)
#define TRINITY_ZEROIZE_TRANSACTION_STATE (1u << 4)
#define TRINITY_ZEROIZE_DIAGNOSTIC_TRANSIENT (1u << 5)
#define TRINITY_ZEROIZE_ALL 0xFFu
#define TRINITY_DIAG_TRANSPORT (1u << 0)
#define TRINITY_DIAG_CRC (1u << 1)
#define TRINITY_DIAG_BAD_COMMAND (1u << 2)
#define TRINITY_DIAG_TRANSACTION_CONFLICT (1u << 3)
#define TRINITY_DIAG_BAD_TAG (1u << 4)
#define TRINITY_DIAG_REPLAY_OR_STALE (1u << 5)
#define TRINITY_DIAG_FRAME_ERROR (1u << 6)
#define TRINITY_DIAG_RESULT_PENDING_DROP (1u << 7)
#define TRINITY_DIAG_HEARTBEAT_OR_FAULT (1u << 8)
#define TRINITY_DIAG_SELF_TEST (1u << 9)
#define TRINITY_DIAG_ALL 0xFFFFFFFFu

typedef struct {
    uint8_t version;
    uint8_t command;
    uint8_t flags;
    uint16_t transaction_id;
    uint16_t payload_length;
    uint8_t payload[TRINITY_SPI_MAX_PAYLOAD];
} trinity_spi_packet_t;

trinity_error_code_t trinity_spi_encode(const trinity_spi_packet_t *packet,
                                         uint8_t *output, size_t output_capacity,
                                         size_t *output_length);
trinity_error_code_t trinity_spi_decode(const uint8_t *input, size_t input_length,
                                         trinity_spi_packet_t *packet);
int trinity_spi_bad_length_detail_is_short_cs(uint16_t detail);
int trinity_spi_bad_length_detail_proves_truncation(
    uint16_t detail, size_t expected_wire_length);
uint32_t trinity_spi_request_fingerprint(uint8_t command, uint8_t flags,
                                         const uint8_t *payload, uint16_t payload_length);
trinity_error_code_t trinity_spi_build_poly_chunk(uint8_t slot_id, uint8_t chunk_index,
                                                   const uint8_t data[64],
                                                   uint8_t output[66]);

#ifdef __cplusplus
}
#endif
#endif
