#ifndef TRINITY_PC_PROTOCOL_H
#define TRINITY_PC_PROTOCOL_H

#include "trinity_protocol_common.h"

#ifdef __cplusplus
extern "C" {
#endif

#define TRINITY_PC_HEADER_SIZE 8u
#define TRINITY_PC_CRC_SIZE 2u
#define TRINITY_PC_MAX_PAYLOAD 256u
#define TRINITY_PC_MAX_RAW_FRAME (TRINITY_PC_HEADER_SIZE + TRINITY_PC_MAX_PAYLOAD + TRINITY_PC_CRC_SIZE)
#define TRINITY_PC_MAX_COBS_FRAME (TRINITY_PC_MAX_RAW_FRAME + (TRINITY_PC_MAX_RAW_FRAME / 254u) + 1u)
#define TRINITY_PC_MAX_WIRE_FRAME (TRINITY_PC_MAX_COBS_FRAME + 1u)

typedef enum {
    TRINITY_PC_PING = 0x01,
    TRINITY_PC_GET_SYSTEM_INFO = 0x02,
    TRINITY_PC_GET_SYSTEM_STATUS = 0x03,
    TRINITY_PC_GET_LAST_ERROR = 0x04,
    TRINITY_PC_GET_TXN_RESULT = 0x05,
    TRINITY_PC_RETIRE_TXN_RESULT = 0x06,
    TRINITY_PC_RUN_SELF_TEST = 0x10,
    TRINITY_PC_GENERATE_KEYPAIR = 0x11,
    TRINITY_PC_CREATE_SESSION = 0x12,
    TRINITY_PC_CLOSE_SESSION = 0x13,
    TRINITY_PC_ZEROIZE_SYSTEM = 0x14,
    TRINITY_PC_SEND_ONE_TELEMETRY = 0x20,
    TRINITY_PC_RUN_DEMO = 0x21,
    TRINITY_PC_READ_LAST_RESULT = 0x22,
    TRINITY_PC_RUN_NTT_TEST = 0x30,
    TRINITY_PC_RUN_ASCON_TEST = 0x31,
    TRINITY_PC_RUN_BENCHMARK = 0x32,
    TRINITY_PC_RUN_TRANSPORT_STRESS = 0x33,
    TRINITY_PC_INJECT_TEST_FAULT = 0x40,
    TRINITY_PC_REQUEST_FAULT_CLEAR = 0x41,
    TRINITY_PC_EVENT = 0xE0
} trinity_pc_command_t;

typedef enum {
    TRINITY_MODE_KAT = 0,
    TRINITY_MODE_DEMO_DETERMINISTIC = 1,
    TRINITY_MODE_DEMO_SECURE = 2
} trinity_mode_t;

typedef enum {
    TRINITY_SYSTEM_BOOT = 0,
    TRINITY_SYSTEM_SELF_TEST_REQUIRED = 1,
    TRINITY_SYSTEM_SELF_TEST_RUNNING = 2,
    TRINITY_SYSTEM_READY_NO_KEYPAIR = 3,
    TRINITY_SYSTEM_READY_NO_SESSION = 4,
    TRINITY_SYSTEM_SESSION_ESTABLISHING = 5,
    TRINITY_SYSTEM_ACTIVE = 6,
    TRINITY_SYSTEM_ZEROIZE_BUSY = 7,
    TRINITY_SYSTEM_FAULT_LOCKED = 8,
    TRINITY_SYSTEM_ERROR = 9
} trinity_system_state_t;

#define TRINITY_READY_SN32 0x01u
#define TRINITY_READY_PRIMER1 0x02u
#define TRINITY_READY_PRIMER2 0x04u
#define TRINITY_READY_TINY1P5 0x08u
#define TRINITY_FAULT_SN32 0x01u
#define TRINITY_FAULT_PRIMER1 0x02u
#define TRINITY_FAULT_PRIMER2 0x04u
#define TRINITY_FAULT_TINY1P5 0x08u
#define TRINITY_FAULT_COMMIT_REJECTED 0x10u
#define TRINITY_FAULT_HEARTBEAT_TIMEOUT 0x20u
#define TRINITY_FAULT_AUTH_THRESHOLD 0x40u
#define TRINITY_FAULT_TRANSPORT 0x80u

typedef enum {
    TRINITY_SOURCE_SN32 = 0,
    TRINITY_SOURCE_PRIMER1 = 1,
    TRINITY_SOURCE_PRIMER2 = 2,
    TRINITY_SOURCE_TINY1P5 = 3,
    TRINITY_SOURCE_HOST_PROTOCOL = 4
} trinity_source_t;

typedef enum {
    TRINITY_EVENT_PROGRESS = 0x0001,
    TRINITY_EVENT_STATUS_CHANGED = 0x0002,
    TRINITY_EVENT_RESULT_READY = 0x0003,
    TRINITY_EVENT_FAULT = 0x0004,
    TRINITY_EVENT_RECOVERY_REQUIRED = 0x0005,
    TRINITY_EVENT_LOG = 0x0006,
    TRINITY_EVENT_TRANSACTION_COMPLETED = 0x0007
} trinity_event_type_t;

#define TRINITY_SYSTEM_CAP_KAT (1u << 0)
#define TRINITY_SYSTEM_CAP_DEMO_DETERMINISTIC (1u << 1)
#define TRINITY_SYSTEM_CAP_DEMO_SECURE (1u << 2)
#define TRINITY_SYSTEM_CAP_MLKEM512 (1u << 3)
#define TRINITY_SYSTEM_CAP_PRIMER1_ACCELERATOR (1u << 4)
#define TRINITY_SYSTEM_CAP_ASCON_AEAD128 (1u << 5)
#define TRINITY_SYSTEM_CAP_PAYLOAD_UART (1u << 6)
#define TRINITY_SYSTEM_CAP_TINY_SUPERVISOR (1u << 7)
#define TRINITY_SYSTEM_CAP_FAULT_INJECTION (1u << 8)
#define TRINITY_SYSTEM_CAP_BENCHMARK (1u << 9)
#define TRINITY_SYSTEM_CAP_TRANSPORT_STRESS (1u << 10)
#define TRINITY_SYSTEM_CAP_TRANSACTION_RECONCILIATION (1u << 11)

typedef enum {
    TRINITY_FAULT_INJECT_DROP_SN32_HEARTBEAT = 0x0001,
    TRINITY_FAULT_INJECT_DROP_P1_HEARTBEAT = 0x0002,
    TRINITY_FAULT_INJECT_DROP_P2_HEARTBEAT = 0x0003,
    TRINITY_FAULT_INJECT_FORCE_BAD_TAG = 0x0004,
    TRINITY_FAULT_INJECT_FORCE_REPLAY = 0x0005,
    TRINITY_FAULT_INJECT_FORCE_FRAME_TIMEOUT = 0x0006,
    TRINITY_FAULT_INJECT_FORCE_SPI_CRC_ERROR = 0x0007,
    TRINITY_FAULT_INJECT_FORCE_TARGET_RESET = 0x0008,
    TRINITY_FAULT_INJECT_FORCE_COMMIT_REJECTED = 0x0009,
    TRINITY_FAULT_INJECT_FORCE_ZEROIZE = 0x000A
} trinity_fault_injection_id_t;

#define TRINITY_BENCH_NTT (1u << 0)
#define TRINITY_BENCH_INTT (1u << 1)
#define TRINITY_BENCH_BASEMUL (1u << 2)
#define TRINITY_BENCH_MLKEM_KEYGEN (1u << 3)
#define TRINITY_BENCH_MLKEM_ENCAPS (1u << 4)
#define TRINITY_BENCH_MLKEM_DECAPS (1u << 5)
#define TRINITY_BENCH_ASCON_ENCRYPT (1u << 6)
#define TRINITY_BENCH_ASCON_DECRYPT (1u << 7)
#define TRINITY_BENCH_SPI (1u << 8)
#define TRINITY_BENCH_PAYLOAD_UART (1u << 9)
#define TRINITY_BENCH_END_TO_END (1u << 10)

typedef struct {
    uint8_t version;
    uint8_t command;
    uint8_t flags;
    uint16_t transaction_id;
    uint16_t payload_length;
    uint8_t payload[TRINITY_PC_MAX_PAYLOAD];
} trinity_pc_frame_t;

trinity_error_code_t trinity_cobs_encode(const uint8_t *input, size_t input_length,
                                          uint8_t *output, size_t output_capacity,
                                          size_t *output_length);
trinity_error_code_t trinity_cobs_decode(const uint8_t *input, size_t input_length,
                                          uint8_t *output, size_t output_capacity,
                                          size_t *output_length);
trinity_error_code_t trinity_pc_encode_raw(const trinity_pc_frame_t *frame,
                                            uint8_t *output, size_t output_capacity,
                                            size_t *output_length);
trinity_error_code_t trinity_pc_decode_raw(const uint8_t *input, size_t input_length,
                                            trinity_pc_frame_t *frame);
trinity_error_code_t trinity_pc_encode_wire(const trinity_pc_frame_t *frame,
                                             uint8_t *output, size_t output_capacity,
                                             size_t *output_length);
trinity_error_code_t trinity_pc_decode_wire(const uint8_t *input, size_t input_length,
                                             trinity_pc_frame_t *frame);

#ifdef __cplusplus
}
#endif
#endif
