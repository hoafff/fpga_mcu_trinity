    uint16_t response_length = 0u;
    uint32_t result_session_id;
    uint64_t result_sequence;
    uint16_t bytes_sent;
    uint32_t started;
    bool result_valid = false;
    bool rx_ready = false;
    uint32_t rx_session_id = 0u;
    uint64_t rx_sequence = 0u;
    uint8_t bad_tags = 0u;
    trinity_error_code_t rc;

    if (controller == NULL || telemetry_payload == NULL || result == NULL)
        return TRINITY_INTERNAL_FAULT;
    if (controller->state != TRINITY_SYSTEM_ACTIVE ||
        !controller->session_material_valid)
        return TRINITY_BAD_STATE;
    rc = controller_get_rx_status(controller, NULL, &result_valid,
                                  &rx_ready, &bad_tags,
                                  &rx_session_id, &rx_sequence);
    if (rc != TRINITY_OK) return rc;
    if (result_valid) return TRINITY_RESULT_PENDING;
    if (telemetry_payload[1] != 0u || telemetry_payload[6] != 0u ||
        telemetry_payload[7] != 0u)
        return TRINITY_BAD_LENGTH;

    rc = controller_exchange(controller, TRINITY_TARGET_PRIMER1,
                             TRINITY_SPI_LOAD_TELEMETRY,
                             telemetry_payload, 32u, NULL, 0u,
                             &response_length, NULL);
    if (rc != TRINITY_OK) return rc;
    if (response_length != 0u) return TRINITY_BAD_LENGTH;

    rc = controller_execute_retained(controller, TRINITY_TARGET_PRIMER1,
                                     TRINITY_SPI_ENCRYPT_AND_SEND,
                                     NULL, 0u, timeout_ms, &tx_result);
    if (rc != TRINITY_OK) return rc;
    if (tx_result.result_length != 14u) return TRINITY_BAD_LENGTH;
    result_session_id = trinity_read_be32(&tx_result.result_data[0]);
    result_sequence = trinity_read_be64(&tx_result.result_data[4]);
    bytes_sent = trinity_read_be16(&tx_result.result_data[12]);
    if (result_session_id != controller->session.session_id ||
        result_sequence != controller->current_sequence + 1u ||
        bytes_sent != TRINITY_CONTROLLER_UART_FRAME_BYTES)
        return TRINITY_TRANSACTION_CONFLICT;

    started = controller_now(controller);
    do {
        rc = controller_get_rx_status(controller, NULL, &result_valid,
                                      &rx_ready, &bad_tags,
                                      &rx_session_id, &rx_sequence);
        if (rc != TRINITY_OK) return rc;
        if (bad_tags >= 3u) {
            controller_latch_error(controller, TRINITY_AUTH_THRESHOLD,
                                   TRINITY_SOURCE_PRIMER2, bad_tags);
            (void)trinity_controller_zeroize(controller,
                                             TRINITY_ZEROIZE_ALL,
                                             timeout_ms);
            return TRINITY_AUTH_THRESHOLD;
        }
        if (result_valid && rx_ready &&
            rx_session_id == result_session_id &&
            rx_sequence == result_sequence)
            break;
        controller_progress(controller);
    } while (!controller_expired(controller, started, timeout_ms));
    if (!result_valid || rx_session_id != result_session_id ||
        rx_sequence != result_sequence)
        return TRINITY_FRAME_TIMEOUT;

    rc = controller_read_auth_result(controller, &authenticated);
    if (rc != TRINITY_OK) return rc;
    if (authenticated.session_id != result_session_id ||
        authenticated.sequence != result_sequence ||
        authenticated.status != TRINITY_OK ||
        memcmp(authenticated.plaintext, &telemetry_payload[8],
               TRINITY_CONTROLLER_PLAINTEXT_BYTES) != 0) {
        controller_latch_error(controller,
                               authenticated.status != TRINITY_OK
                                   ? authenticated.status : TRINITY_BAD_TAG,
                               TRINITY_SOURCE_PRIMER2,
                               (uint32_t)result_sequence);
        return authenticated.status != TRINITY_OK
                   ? authenticated.status : TRINITY_BAD_TAG;
    }

    rc = controller_ack_auth_result(controller, authenticated.session_id,
                                    authenticated.sequence);
    if (rc != TRINITY_OK) return rc;
    controller->last_result = authenticated;
    controller->current_sequence = authenticated.sequence;
    *result = authenticated;
    return TRINITY_OK;
}

trinity_error_code_t trinity_controller_clear_p2_diagnostics(
    trinity_controller_t *controller,
    uint32_t mask) {
    uint8_t payload[4];
    uint16_t response_length = 0u;
    trinity_write_be32(payload, mask);
    return controller_exchange(controller, TRINITY_TARGET_PRIMER2,
                               TRINITY_SPI_CLEAR_DIAGNOSTIC_COUNTERS,
                               payload, sizeof(payload), NULL, 0u,
                               &response_length, NULL);
}

trinity_error_code_t trinity_controller_transport_stress(
    trinity_controller_t *controller,
    uint8_t link_id,
