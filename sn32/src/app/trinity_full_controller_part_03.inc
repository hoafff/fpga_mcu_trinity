    return controller_exchange(controller, target_id,
                               TRINITY_SPI_ABORT_SESSION,
                               payload, sizeof(payload), NULL, 0u,
                               &response_length, NULL);
}

static trinity_error_code_t controller_commit_one(
    trinity_controller_t *controller,
    uint8_t target_id,
    uint32_t session_id,
    uint32_t timeout_ms) {
    uint8_t payload[4];
    trinity_controller_transaction_result_t result;
    trinity_write_be32(payload, session_id);
    return controller_execute_retained(controller, target_id,
                                       TRINITY_SPI_COMMIT_SESSION,
                                       payload, sizeof(payload), timeout_ms,
                                       &result);
}

static trinity_error_code_t controller_zeroize_one(
    trinity_controller_t *controller,
    uint8_t target_id,
    uint8_t scope,
    uint32_t timeout_ms) {
    uint8_t payload[4] = {scope, 0u, 0u, 0u};
    trinity_controller_transaction_result_t result;
    return controller_execute_retained(controller, target_id,
                                       TRINITY_SPI_ZEROIZE,
                                       payload, sizeof(payload), timeout_ms,
                                       &result);
}

void trinity_controller_init(trinity_controller_t *controller,
                             const trinity_controller_ops_t *ops) {
    if (controller == NULL) return;
    memset(controller, 0, sizeof(*controller));
    if (ops != NULL) controller->ops = *ops;
    controller->p1.target_id = TRINITY_TARGET_PRIMER1;
    controller->p2.target_id = TRINITY_TARGET_PRIMER2;
    controller->mode = TRINITY_MODE_KAT;
    controller->state = TRINITY_SYSTEM_BOOT;
    controller->last_error = TRINITY_OK;
}

trinity_error_code_t trinity_controller_probe_all(
    trinity_controller_t *controller) {
    trinity_error_code_t rc;
    if (controller == NULL) return TRINITY_INTERNAL_FAULT;

    /*
     * Probe fail-fast. Issuing P2 traffic after a P1 transport failure can leave
     * a second stale mailbox and obscures the first failing endpoint.
     */
    rc = controller_probe_endpoint(controller, &controller->p1);
    if (rc != TRINITY_OK) {
        controller->p2.ready = false;
        return rc;
    }

    rc = controller_probe_endpoint(controller, &controller->p2);
    if (rc != TRINITY_OK) return rc;

    controller_clear_recovered_transport_error(controller);
    controller->state =
        (controller->p1.session_state == TRINITY_SESSION_SELF_TEST_REQUIRED ||
         controller->p2.session_state == TRINITY_SESSION_SELF_TEST_REQUIRED)
            ? TRINITY_SYSTEM_SELF_TEST_REQUIRED
            : TRINITY_SYSTEM_READY_NO_SESSION;
    return TRINITY_OK;
}

trinity_error_code_t trinity_controller_refresh_status(
    trinity_controller_t *controller) {
    trinity_error_code_t rc;
    if (controller == NULL) return TRINITY_INTERNAL_FAULT;
    rc = controller_get_status(controller, &controller->p1);
    if (rc != TRINITY_OK) return rc;
    rc = controller_get_status(controller, &controller->p2);
    if (rc != TRINITY_OK) return rc;

    /*
     * A complete two-endpoint refresh clears only the active transport error
     * used by fault_flags. Safety errors remain latched. The deploy layer keeps
     * g_error as diagnostic history, so user-facing last_error is preserved.
     */
    controller_clear_recovered_transport_error(controller);

    if (controller->p1.session_state == TRINITY_SESSION_ACTIVE &&
        controller->p2.session_state == TRINITY_SESSION_ACTIVE &&
        controller->p1.session_id == controller->p2.session_id &&
        controller->p1.session_id != 0u) {
        controller->state = TRINITY_SYSTEM_ACTIVE;
    } else if (controller->p1.session_state == TRINITY_SESSION_ZEROIZE_BUSY ||
               controller->p2.session_state == TRINITY_SESSION_ZEROIZE_BUSY) {
        controller->state = TRINITY_SYSTEM_ZEROIZE_BUSY;
    } else if (controller->p1.session_state == TRINITY_SESSION_SELF_TEST_REQUIRED ||
               controller->p2.session_state == TRINITY_SESSION_SELF_TEST_REQUIRED) {
        controller->state = TRINITY_SYSTEM_SELF_TEST_REQUIRED;
    } else if (controller->p1.session_state == TRINITY_SESSION_SELF_TEST_RUNNING ||
               controller->p2.session_state == TRINITY_SESSION_SELF_TEST_RUNNING) {
        controller->state = TRINITY_SYSTEM_SELF_TEST_RUNNING;
    } else if (controller->p1.session_state == TRINITY_SESSION_STAGED ||
               controller->p2.session_state == TRINITY_SESSION_STAGED ||
               controller->p1.session_state == TRINITY_SESSION_COMMITTED_BLOCKED ||
               controller->p2.session_state == TRINITY_SESSION_COMMITTED_BLOCKED) {
        controller->state = TRINITY_SYSTEM_SESSION_ESTABLISHING;
    } else {
        controller->state = TRINITY_SYSTEM_READY_NO_SESSION;
    }
    return TRINITY_OK;
}

trinity_error_code_t trinity_controller_run_self_test(
    trinity_controller_t *controller,
    uint8_t target_mask,
    uint16_t test_mask,
    uint32_t timeout_ms) {
    uint8_t payload[4];
    trinity_controller_transaction_result_t result;
    trinity_error_code_t rc;
    if (controller == NULL || (target_mask &
        ~(TRINITY_READY_SN32 | TRINITY_READY_PRIMER1 |
          TRINITY_READY_PRIMER2 | TRINITY_READY_TINY1P5)) != 0u)
        return TRINITY_BAD_LENGTH;
    if ((target_mask & TRINITY_READY_TINY1P5) != 0u &&
