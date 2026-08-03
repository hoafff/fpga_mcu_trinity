#ifndef TRINITY_FULL_CONTROLLER_H
#define TRINITY_FULL_CONTROLLER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "trinity_protocol_common.h"
#include "trinity_pc_protocol.h"
#include "trinity_spi_protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

#define TRINITY_CONTROLLER_PLAINTEXT_BYTES 24u
#define TRINITY_CONTROLLER_SESSION_KEY_BYTES 16u
#define TRINITY_CONTROLLER_NONCE_PREFIX_BYTES 8u
#define TRINITY_CONTROLLER_MAX_RESULT_BYTES 66u
#define TRINITY_CONTROLLER_UART_FRAME_BYTES 66u

#define TRINITY_CONTROLLER_P1_CAPABILITIES \
    (TRINITY_SPI_CAP_SELF_TEST | TRINITY_SPI_CAP_ZEROIZE | \
     TRINITY_SPI_CAP_TRANSACTION_RECONCILIATION | \
     TRINITY_SPI_CAP_SESSION_STAGE_COMMIT | TRINITY_SPI_CAP_NTT | \
     TRINITY_SPI_CAP_INTT | TRINITY_SPI_CAP_BASEMUL | \
     TRINITY_SPI_CAP_ASCON_ENCRYPT | TRINITY_SPI_CAP_UART_TX)

#define TRINITY_CONTROLLER_P2_CAPABILITIES \
    (TRINITY_SPI_CAP_SELF_TEST | TRINITY_SPI_CAP_ZEROIZE | \
     TRINITY_SPI_CAP_TRANSACTION_RECONCILIATION | \
     TRINITY_SPI_CAP_SESSION_STAGE_COMMIT | \
     TRINITY_SPI_CAP_ASCON_DECRYPT | TRINITY_SPI_CAP_REPLAY_FILTER | \
     TRINITY_SPI_CAP_AUTH_RESULT_BUFFER | TRINITY_SPI_CAP_DIAGNOSTICS)

typedef struct {
    uint8_t target_id;
    bool ready;
    uint32_t capabilities;
    uint32_t build_id;
    uint8_t session_state;
    uint8_t operation_state;
    uint8_t pending_flags;
    uint8_t secure_flags;
    uint32_t session_id;
    uint16_t last_error;
    uint16_t active_transaction_id;
    uint32_t diagnostic_summary;
} trinity_controller_endpoint_t;

typedef struct {
    uint16_t original_txid;
    trinity_transaction_state_t state;
    uint8_t original_command;
    trinity_error_code_t result_code;
    uint16_t result_length;
    uint8_t result_data[TRINITY_CONTROLLER_MAX_RESULT_BYTES];
} trinity_controller_transaction_result_t;

typedef struct {
    bool valid;
    uint32_t session_id;
    uint64_t sequence;
    uint8_t plaintext[TRINITY_CONTROLLER_PLAINTEXT_BYTES];
    trinity_error_code_t status;
} trinity_controller_auth_result_t;

typedef struct {
    uint32_t session_id;
    uint8_t key[TRINITY_CONTROLLER_SESSION_KEY_BYTES];
    uint8_t nonce_prefix[TRINITY_CONTROLLER_NONCE_PREFIX_BYTES];
} trinity_controller_session_material_t;

typedef struct {
    void *context;
    trinity_error_code_t (*exchange)(
        void *context,
        uint8_t target_id,
        uint8_t command,
        const uint8_t *payload,
        uint16_t payload_length,
        uint8_t *response_payload,
        uint16_t response_capacity,
        uint16_t *response_length,
        uint16_t *issued_txid);
    uint32_t (*now_ms)(void *context);
    void (*progress)(void *context);
    void (*session_commit_low)(void *context);
    void (*session_commit_high)(void *context);
    bool (*tiny_fault_active)(void *context);
} trinity_controller_ops_t;

typedef struct {
    trinity_controller_ops_t ops;
    trinity_controller_endpoint_t p1;
    trinity_controller_endpoint_t p2;
    trinity_controller_session_material_t session;
    trinity_controller_auth_result_t last_result;
    uint64_t current_sequence;
    trinity_mode_t mode;
    trinity_system_state_t state;
    trinity_error_code_t last_error;
    trinity_source_t last_error_source;
    uint32_t last_error_detail;
    bool session_material_valid;
    bool commit_issued;
} trinity_controller_t;

void trinity_controller_init(trinity_controller_t *controller,
                             const trinity_controller_ops_t *ops);

trinity_error_code_t trinity_controller_probe_all(
    trinity_controller_t *controller);
trinity_error_code_t trinity_controller_refresh_status(
    trinity_controller_t *controller);
trinity_error_code_t trinity_controller_run_self_test(
    trinity_controller_t *controller,
    uint8_t target_mask,
    uint16_t test_mask,
    uint32_t timeout_ms);
trinity_error_code_t trinity_controller_activate_session(
    trinity_controller_t *controller,
    const trinity_controller_session_material_t *material,
    trinity_mode_t mode,
    uint32_t timeout_ms);
trinity_error_code_t trinity_controller_close_session(
    trinity_controller_t *controller,
    uint32_t timeout_ms);
trinity_error_code_t trinity_controller_zeroize(
    trinity_controller_t *controller,
    uint8_t scope,
    uint32_t timeout_ms);
trinity_error_code_t trinity_controller_send_telemetry(
    trinity_controller_t *controller,
    const uint8_t telemetry_payload[32],
    uint32_t timeout_ms,
    trinity_controller_auth_result_t *result);
trinity_error_code_t trinity_controller_clear_p2_diagnostics(
    trinity_controller_t *controller,
    uint32_t mask);
trinity_error_code_t trinity_controller_transport_stress(
    trinity_controller_t *controller,
    uint8_t link_id,
    uint32_t transaction_count);

uint8_t trinity_controller_ready_mask(const trinity_controller_t *controller);
uint8_t trinity_controller_fault_mask(const trinity_controller_t *controller);
void trinity_controller_forget_last_result(trinity_controller_t *controller);
void trinity_controller_secure_clear(void *buffer, size_t length);

#ifdef __cplusplus
}
#endif

#endif
