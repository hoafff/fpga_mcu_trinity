    if (endpoint->target_id == TRINITY_TARGET_PRIMER1) {
        if ((endpoint->capabilities & TRINITY_CONTROLLER_P1_CAPABILITIES) !=
            TRINITY_CONTROLLER_P1_CAPABILITIES)
            return TRINITY_NOT_SUPPORTED;
    } else if ((endpoint->capabilities & TRINITY_CONTROLLER_P2_CAPABILITIES) !=
               TRINITY_CONTROLLER_P2_CAPABILITIES) {
        return TRINITY_NOT_SUPPORTED;
    }
    return TRINITY_OK;
}

static trinity_error_code_t controller_get_status(
    trinity_controller_t *controller,
    trinity_controller_endpoint_t *endpoint) {
    uint8_t response[16];
    uint16_t response_length = 0u;
    trinity_error_code_t rc = controller_exchange(
        controller, endpoint->target_id, TRINITY_SPI_GET_STATUS,
        NULL, 0u, response, sizeof(response), &response_length, NULL);
    if (rc != TRINITY_OK) {
        endpoint->ready = false;
        return rc;
    }
    if (response_length != sizeof(response)) return TRINITY_BAD_LENGTH;
    endpoint->session_state = response[0];
    endpoint->operation_state = response[1];
    endpoint->pending_flags = response[2];
    endpoint->secure_flags = response[3];
    endpoint->session_id = trinity_read_be32(&response[4]);
    endpoint->last_error = trinity_read_be16(&response[8]);
    endpoint->active_transaction_id = trinity_read_be16(&response[10]);
    endpoint->diagnostic_summary = trinity_read_be32(&response[12]);
    endpoint->ready = true;
    if (endpoint->session_state == TRINITY_SESSION_FAULT_LOCKED ||
        (endpoint->secure_flags & TRINITY_SECURE_FAULT_LOCKED) != 0u) {
        controller_latch_error(controller, TRINITY_FAULT_LOCKED,
                               controller_source(endpoint->target_id),
                               endpoint->diagnostic_summary);
        return TRINITY_FAULT_LOCKED;
    }
    return TRINITY_OK;
}

static trinity_error_code_t controller_probe_endpoint(
    trinity_controller_t *controller,
    trinity_controller_endpoint_t *endpoint) {
    trinity_error_code_t rc;
    endpoint->ready = false;
    rc = controller_get_info(controller, endpoint);
    if (rc == TRINITY_OK) rc = controller_get_status(controller, endpoint);
    if (rc != TRINITY_OK) {
        endpoint->last_error = (uint16_t)rc;
        controller_latch_error(controller, rc,
                               controller_source(endpoint->target_id),
                               endpoint->target_id);
    }
    return rc;
}

static trinity_error_code_t controller_parse_transaction_result(
    const uint8_t *response,
    uint16_t response_length,
    uint16_t expected_txid,
    uint8_t expected_command,
    trinity_controller_transaction_result_t *result) {
    uint16_t result_length;
    if (response == NULL || result == NULL || response_length < 10u)
        return TRINITY_BAD_LENGTH;
    if (trinity_read_be16(&response[0]) != expected_txid ||
        response[3] != expected_command || response[8] != 0u ||
        response[9] != 0u)
        return TRINITY_TRANSACTION_CONFLICT;
    if (response[2] > (uint8_t)TRINITY_TXN_OUTCOME_UNKNOWN)
        return TRINITY_BAD_STATE;
    result_length = trinity_read_be16(&response[6]);
    if (result_length > sizeof(result->result_data) ||
        response_length != (uint16_t)(10u + result_length))
        return TRINITY_BAD_LENGTH;
    memset(result, 0, sizeof(*result));
    result->original_txid = expected_txid;
    result->state = (trinity_transaction_state_t)response[2];
    result->original_command = response[3];
    result->result_code =
        (trinity_error_code_t)trinity_read_be16(&response[4]);
    result->result_length = result_length;
    if (result_length != 0u)
        memcpy(result->result_data, &response[10], result_length);
    return TRINITY_OK;
}

static bool controller_transaction_terminal(
    trinity_transaction_state_t state) {
    return state != TRINITY_TXN_ACCEPTED && state != TRINITY_TXN_RUNNING;
}

static trinity_error_code_t controller_get_transaction_result(
    trinity_controller_t *controller,
    uint8_t target_id,
    uint16_t original_txid,
    uint8_t original_command,
    trinity_controller_transaction_result_t *result) {
    uint8_t request[2];
    uint8_t response[10u + TRINITY_CONTROLLER_MAX_RESULT_BYTES];
    uint16_t response_length = 0u;
    trinity_error_code_t rc;
    trinity_write_be16(request, original_txid);
    rc = controller_exchange(controller, target_id,
                             TRINITY_SPI_GET_TXN_RESULT,
                             request, sizeof(request), response,
                             sizeof(response), &response_length, NULL);
