    if (rc != TRINITY_OK) return rc;
    return controller_parse_transaction_result(response, response_length,
                                               original_txid,
                                               original_command, result);
}

static trinity_error_code_t controller_retire_transaction(
    trinity_controller_t *controller,
    uint8_t target_id,
    uint16_t original_txid) {
    uint8_t request[2];
    uint16_t response_length = 0u;
    trinity_write_be16(request, original_txid);
    return controller_exchange(controller, target_id,
                               TRINITY_SPI_RETIRE_TXN_RESULT,
                               request, sizeof(request), NULL, 0u,
                               &response_length, NULL);
}

static trinity_error_code_t controller_execute_retained(
    trinity_controller_t *controller,
    uint8_t target_id,
    uint8_t command,
    const uint8_t *payload,
    uint16_t payload_length,
    uint32_t timeout_ms,
    trinity_controller_transaction_result_t *result) {
    uint16_t original_txid = 0u;
    uint16_t response_length = 0u;
    uint32_t started;
    trinity_error_code_t rc;

    if (result == NULL) return TRINITY_INTERNAL_FAULT;
    memset(result, 0, sizeof(*result));
    result->state = TRINITY_TXN_ACCEPTED;
    result->original_command = command;

    rc = controller_exchange(controller, target_id, command, payload,
                             payload_length, NULL, 0u, &response_length,
                             &original_txid);
    if (rc != TRINITY_OK) return rc;
    if (response_length != 0u) return TRINITY_BAD_LENGTH;
    result->original_txid = original_txid;

    started = controller_now(controller);
    do {
        rc = controller_get_transaction_result(controller, target_id,
                                               original_txid, command, result);
        if (rc == TRINITY_OK && controller_transaction_terminal(result->state))
            break;
        if (rc != TRINITY_OK && rc != TRINITY_RESULT_NOT_READY &&
            rc != TRINITY_BUSY)
            return rc;
        controller_progress(controller);
    } while (!controller_expired(controller, started, timeout_ms));

    if (!controller_transaction_terminal(result->state)) {
        /* One final reconciliation read before declaring the outcome unknown. */
        rc = controller_get_transaction_result(controller, target_id,
                                               original_txid, command, result);
        if (rc != TRINITY_OK || !controller_transaction_terminal(result->state))
            return TRINITY_OUTCOME_UNKNOWN_TARGET_RESET;
    }

    rc = controller_retire_transaction(controller, target_id, original_txid);
    if (rc != TRINITY_OK) return rc;
    if (result->state == TRINITY_TXN_SUCCEEDED ||
        result->state == TRINITY_TXN_ZEROIZED)
        return result->result_code;
    return result->result_code != TRINITY_OK
               ? result->result_code : TRINITY_INTERNAL_FAULT;
}

static bool controller_session_state_matches(
    const trinity_controller_endpoint_t *endpoint,
    uint8_t expected_state,
    uint32_t expected_session_id) {
    if (endpoint == NULL || endpoint->session_state != expected_state)
        return false;

    /*
     * Primer GET_STATUS exposes active_session_id in bytes 4..7. During
     * SESSION_STAGED the active bank is intentionally still empty, so that
     * field is zero even though the staged bank contains the new session ID.
     * Validate STAGED using the state plus SECURE_SESSION_STAGED. The exact
     * session ID is then enforced independently by each Primer when it accepts
     * COMMIT_SESSION. COMMITTED_BLOCKED and ACTIVE report active_session_id and
     * therefore retain the strict ID comparison here.
     */
    if (expected_state == TRINITY_SESSION_STAGED)
        return (endpoint->secure_flags & TRINITY_SECURE_SESSION_STAGED) != 0u;

    return endpoint->session_id == expected_session_id;
}

static trinity_error_code_t controller_wait_session_state(
    trinity_controller_t *controller,
    uint8_t expected_state,
    uint32_t expected_session_id,
    uint32_t timeout_ms) {
    uint32_t started = controller_now(controller);
    trinity_error_code_t rc;
    do {
        rc = trinity_controller_refresh_status(controller);
        if (rc != TRINITY_OK) return rc;
        if (controller_session_state_matches(&controller->p1, expected_state,
                                             expected_session_id) &&
            controller_session_state_matches(&controller->p2, expected_state,
                                             expected_session_id))
            return TRINITY_OK;
        controller_progress(controller);
    } while (!controller_expired(controller, started, timeout_ms));
    return TRINITY_SESSION_COMMIT_FAILED;
}

static trinity_error_code_t controller_stage_one(
    trinity_controller_t *controller,
    uint8_t target_id,
    const trinity_controller_session_material_t *material) {
    uint8_t payload[28];
    uint16_t response_length = 0u;
    trinity_write_be32(&payload[0], material->session_id);
    memcpy(&payload[4], material->key, sizeof(material->key));
    memcpy(&payload[20], material->nonce_prefix,
           sizeof(material->nonce_prefix));
    return controller_exchange(controller, target_id,
                               TRINITY_SPI_STAGE_SESSION,
                               payload, sizeof(payload), NULL, 0u,
                               &response_length, NULL);
}

static trinity_error_code_t controller_abort_one(
    trinity_controller_t *controller,
    uint8_t target_id,
    uint32_t session_id) {
    uint8_t payload[4];
    uint16_t response_length = 0u;
    trinity_write_be32(payload, session_id);
