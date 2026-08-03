    trinity_error_code_t rc2;
    uint32_t session_id;
    if (controller == NULL) return TRINITY_INTERNAL_FAULT;
    if (controller->ops.session_commit_low != NULL)
        controller->ops.session_commit_low(controller->ops.context);
    session_id = controller->session_material_valid
                     ? controller->session.session_id : 0u;
    rc1 = controller_abort_one(controller, TRINITY_TARGET_PRIMER1, session_id);
    rc2 = controller_abort_one(controller, TRINITY_TARGET_PRIMER2, session_id);
    trinity_controller_secure_clear(&controller->session,
                                    sizeof(controller->session));
    controller->session_material_valid = false;
    controller->commit_issued = false;
    controller->current_sequence = 0u;
    trinity_controller_forget_last_result(controller);
    controller->state = TRINITY_SYSTEM_READY_NO_SESSION;
    (void)timeout_ms;
    if (rc1 != TRINITY_OK && rc1 != TRINITY_BAD_SESSION &&
        rc1 != TRINITY_FAULT_LOCKED) return rc1;
    if (rc2 != TRINITY_OK && rc2 != TRINITY_BAD_SESSION &&
        rc2 != TRINITY_FAULT_LOCKED) return rc2;
    return controller_tiny_fault(controller) ? TRINITY_FAULT_LOCKED : TRINITY_OK;
}

trinity_error_code_t trinity_controller_zeroize(
    trinity_controller_t *controller,
    uint8_t scope,
    uint32_t timeout_ms) {
    trinity_error_code_t rc1;
    trinity_error_code_t rc2;
    if (controller == NULL) return TRINITY_INTERNAL_FAULT;
    if (controller->ops.session_commit_low != NULL)
        controller->ops.session_commit_low(controller->ops.context);
    controller->state = TRINITY_SYSTEM_ZEROIZE_BUSY;
    rc1 = controller_zeroize_one(controller, TRINITY_TARGET_PRIMER1,
                                 scope, timeout_ms);
    rc2 = controller_zeroize_one(controller, TRINITY_TARGET_PRIMER2,
                                 scope, timeout_ms);
    trinity_controller_secure_clear(&controller->session,
                                    sizeof(controller->session));
    controller->session_material_valid = false;
    controller->commit_issued = false;
    controller->current_sequence = 0u;
    trinity_controller_forget_last_result(controller);
    controller->state = controller_tiny_fault(controller)
                            ? TRINITY_SYSTEM_FAULT_LOCKED
                            : TRINITY_SYSTEM_READY_NO_SESSION;
    if (rc1 != TRINITY_OK && rc1 != TRINITY_ZEROIZED &&
        rc1 != TRINITY_FAULT_LOCKED) return rc1;
    if (rc2 != TRINITY_OK && rc2 != TRINITY_ZEROIZED &&
        rc2 != TRINITY_FAULT_LOCKED) return rc2;
    return controller_tiny_fault(controller) ? TRINITY_FAULT_LOCKED : TRINITY_OK;
}

static trinity_error_code_t controller_get_rx_status(
    trinity_controller_t *controller,
    uint8_t *rx_state,
    bool *result_valid,
    bool *rx_ready,
    uint8_t *bad_tags,
    uint32_t *session_id,
    uint64_t *sequence) {
    uint8_t response[16];
    uint16_t response_length = 0u;
    trinity_error_code_t rc = controller_exchange(
        controller, TRINITY_TARGET_PRIMER2, TRINITY_SPI_GET_RX_STATUS,
        NULL, 0u, response, sizeof(response), &response_length, NULL);
    if (rc != TRINITY_OK) return rc;
    if (response_length != sizeof(response)) return TRINITY_BAD_LENGTH;
    if (rx_state != NULL) *rx_state = response[0];
    if (result_valid != NULL) *result_valid = response[1] != 0u;
    if (rx_ready != NULL) *rx_ready = response[2] != 0u;
    if (bad_tags != NULL) *bad_tags = response[3];
    if (session_id != NULL) *session_id = trinity_read_be32(&response[4]);
    if (sequence != NULL) *sequence = trinity_read_be64(&response[8]);
    return TRINITY_OK;
}

static trinity_error_code_t controller_read_auth_result(
    trinity_controller_t *controller,
    trinity_controller_auth_result_t *result) {
    uint8_t response[38];
    uint16_t response_length = 0u;
    trinity_error_code_t rc = controller_exchange(
        controller, TRINITY_TARGET_PRIMER2, TRINITY_SPI_READ_AUTH_RESULT,
        NULL, 0u, response, sizeof(response), &response_length, NULL);
    if (rc != TRINITY_OK) return rc;
    if (response_length != sizeof(response)) return TRINITY_BAD_LENGTH;
    memset(result, 0, sizeof(*result));
    result->valid = true;
    result->session_id = trinity_read_be32(&response[0]);
    result->sequence = trinity_read_be64(&response[4]);
    memcpy(result->plaintext, &response[12], sizeof(result->plaintext));
    result->status = (trinity_error_code_t)trinity_read_be16(&response[36]);
    return TRINITY_OK;
}

static trinity_error_code_t controller_ack_auth_result(
    trinity_controller_t *controller,
    uint32_t session_id,
    uint64_t sequence) {
    uint8_t payload[12];
    uint16_t response_length = 0u;
    trinity_write_be32(&payload[0], session_id);
    trinity_write_be64(&payload[4], sequence);
    return controller_exchange(controller, TRINITY_TARGET_PRIMER2,
                               TRINITY_SPI_ACK_AUTH_RESULT,
                               payload, sizeof(payload), NULL, 0u,
                               &response_length, NULL);
}

trinity_error_code_t trinity_controller_send_telemetry(
    trinity_controller_t *controller,
    const uint8_t telemetry_payload[32],
    uint32_t timeout_ms,
    trinity_controller_auth_result_t *result) {
    trinity_controller_transaction_result_t tx_result;
    trinity_controller_auth_result_t authenticated;
