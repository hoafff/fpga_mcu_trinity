#include "trinity_full_controller.h"

#include <string.h>

enum {
    CONTROLLER_STATUS_TIMEOUT_MS = 100u,
    CONTROLLER_POLL_INTERVAL_MS = 1u,
    CONTROLLER_SESSION_COMMIT_LOW_MS = 2u,
    CONTROLLER_SESSION_STAGE_TIMEOUT_MS = 500u,
    CONTROLLER_SESSION_ACTIVE_TIMEOUT_MS = 2000u
};

static void controller_latch_error(trinity_controller_t *controller,
                                   trinity_error_code_t code,
                                   trinity_source_t source,
                                   uint32_t detail) {
    if (controller == NULL || code == TRINITY_OK) return;
    controller->last_error = code;
    controller->last_error_source = source;
    controller->last_error_detail = detail;
    if (code == TRINITY_FAULT_LOCKED || code == TRINITY_AUTH_THRESHOLD ||
        code == TRINITY_HEARTBEAT_TIMEOUT || code == TRINITY_COMMIT_REJECTED ||
        code == TRINITY_SESSION_COMMIT_FAILED) {
        controller->state = TRINITY_SYSTEM_FAULT_LOCKED;
    } else if (controller->state != TRINITY_SYSTEM_FAULT_LOCKED) {
        controller->state = TRINITY_SYSTEM_ERROR;
    }
}

static bool controller_error_is_transport(trinity_error_code_t code) {
    return code == TRINITY_BAD_MAGIC || code == TRINITY_BAD_VERSION ||
           code == TRINITY_BAD_LENGTH || code == TRINITY_BAD_CRC ||
           code == TRINITY_BAD_FLAGS || code == TRINITY_MALFORMED_FRAME ||
           code == TRINITY_FRAME_TIMEOUT ||
           code == TRINITY_TRANSACTION_CONFLICT;
}

static void controller_clear_recovered_transport_error(
    trinity_controller_t *controller) {
    if (controller == NULL ||
        controller->state == TRINITY_SYSTEM_FAULT_LOCKED ||
        !controller_error_is_transport(controller->last_error))
        return;
    controller->last_error = TRINITY_OK;
    controller->last_error_source = TRINITY_SOURCE_SN32;
    controller->last_error_detail = 0u;
}

void trinity_controller_secure_clear(void *buffer, size_t length) {
    volatile uint8_t *cursor = (volatile uint8_t *)buffer;
    if (cursor == NULL) return;
    while (length != 0u) {
        *cursor++ = 0u;
        --length;
    }
}

static uint32_t controller_now(const trinity_controller_t *controller) {
    return controller->ops.now_ms(controller->ops.context);
}

static void controller_progress(const trinity_controller_t *controller) {
    if (controller->ops.progress != NULL)
        controller->ops.progress(controller->ops.context);
}

static bool controller_expired(const trinity_controller_t *controller,
                               uint32_t started,
                               uint32_t timeout_ms) {
    return (uint32_t)(controller_now(controller) - started) >= timeout_ms;
}

static void controller_wait_ms(const trinity_controller_t *controller,
                               uint32_t delay_ms) {
    const uint32_t started = controller_now(controller);
    while (!controller_expired(controller, started, delay_ms))
        controller_progress(controller);
}

static bool controller_tiny_fault(const trinity_controller_t *controller) {
    return controller->ops.tiny_fault_active != NULL &&
           controller->ops.tiny_fault_active(controller->ops.context);
}

static trinity_source_t controller_source(uint8_t target_id) {
    return target_id == TRINITY_TARGET_PRIMER1
               ? TRINITY_SOURCE_PRIMER1
               : TRINITY_SOURCE_PRIMER2;
}

static bool controller_error_is_polling_state(trinity_error_code_t code) {
    return code == TRINITY_RESULT_NOT_READY || code == TRINITY_BUSY ||
           code == TRINITY_RESULT_PENDING;
}

static trinity_error_code_t controller_exchange(
    trinity_controller_t *controller,
    uint8_t target_id,
    uint8_t command,
    const uint8_t *payload,
    uint16_t payload_length,
    uint8_t *response,
    uint16_t response_capacity,
    uint16_t *response_length,
    uint16_t *issued_txid) {
    trinity_error_code_t rc;
    if (controller == NULL || controller->ops.exchange == NULL ||
        controller->ops.now_ms == NULL)
        return TRINITY_INTERNAL_FAULT;
    if (controller_tiny_fault(controller)) {
        controller_latch_error(controller, TRINITY_FAULT_LOCKED,
                               TRINITY_SOURCE_TINY1P5, command);
        return TRINITY_FAULT_LOCKED;
    }
    rc = controller->ops.exchange(controller->ops.context, target_id, command,
                                  payload, payload_length, response,
                                  response_capacity, response_length,
                                  issued_txid);
    if (rc != TRINITY_OK && !controller_error_is_polling_state(rc)) {
        controller_latch_error(controller, rc, controller_source(target_id),
                               ((uint32_t)command << 16) |
                               (issued_txid != NULL ? *issued_txid : 0u));
    }
    controller_progress(controller);
    return rc;
}

static trinity_error_code_t controller_get_info(
    trinity_controller_t *controller,
    trinity_controller_endpoint_t *endpoint) {
    uint8_t response[12];
    uint16_t response_length = 0u;
    uint16_t issued_txid = 0u;
    trinity_error_code_t rc = controller_exchange(
        controller, endpoint->target_id, TRINITY_SPI_GET_INFO,
        NULL, 0u, response, sizeof(response), &response_length, &issued_txid);
    if (rc != TRINITY_OK) return rc;
    if (response_length != sizeof(response) ||
        response[0] != endpoint->target_id ||
        response[1] != TRINITY_PROTOCOL_VERSION ||
        response[10] != 0u || response[11] != 0u) {
        controller_latch_error(controller, TRINITY_BAD_STATE,
                               controller_source(endpoint->target_id),
                               ((uint32_t)TRINITY_SPI_GET_INFO << 16) |
                               issued_txid);
        return TRINITY_BAD_STATE;
    }
    endpoint->capabilities = trinity_read_be32(&response[2]);
    endpoint->build_id = trinity_read_be32(&response[6]);
