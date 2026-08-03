        controller_tiny_fault(controller))
        return TRINITY_FAULT_LOCKED;
    controller->state = TRINITY_SYSTEM_SELF_TEST_RUNNING;
    trinity_write_be16(&payload[0], test_mask);
    payload[2] = 0u;
    payload[3] = 0u;
    if ((target_mask & TRINITY_READY_PRIMER1) != 0u) {
        rc = controller_execute_retained(controller, TRINITY_TARGET_PRIMER1,
                                         TRINITY_SPI_RUN_SELF_TEST,
                                         payload, sizeof(payload), timeout_ms,
                                         &result);
        if (rc != TRINITY_OK) return rc;
        if (result.result_length != 2u ||
            trinity_read_be16(result.result_data) != test_mask)
            return TRINITY_SELF_TEST_FAILED;
    }
    if ((target_mask & TRINITY_READY_PRIMER2) != 0u) {
        rc = controller_execute_retained(controller, TRINITY_TARGET_PRIMER2,
                                         TRINITY_SPI_RUN_SELF_TEST,
                                         payload, sizeof(payload), timeout_ms,
                                         &result);
        if (rc != TRINITY_OK) return rc;
        if (result.result_length != 2u ||
            trinity_read_be16(result.result_data) != test_mask)
            return TRINITY_SELF_TEST_FAILED;
    }
    rc = trinity_controller_refresh_status(controller);
    if (rc == TRINITY_OK) controller->state = TRINITY_SYSTEM_READY_NO_SESSION;
    return rc;
}

trinity_error_code_t trinity_controller_activate_session(
    trinity_controller_t *controller,
    const trinity_controller_session_material_t *material,
    trinity_mode_t mode,
    uint32_t timeout_ms) {
    trinity_error_code_t rc;
    if (controller == NULL || material == NULL || material->session_id == 0u)
        return TRINITY_BAD_SESSION;
    if (!controller->p1.ready || !controller->p2.ready)
        return TRINITY_BAD_STATE;
    controller->state = TRINITY_SYSTEM_SESSION_ESTABLISHING;
    controller->commit_issued = false;

    rc = controller_stage_one(controller, TRINITY_TARGET_PRIMER1, material);
    if (rc == TRINITY_OK)
        rc = controller_stage_one(controller, TRINITY_TARGET_PRIMER2, material);
    if (rc != TRINITY_OK) goto fail_abort;

    rc = controller_wait_session_state(controller, TRINITY_SESSION_STAGED,
                                       material->session_id,
                                       CONTROLLER_SESSION_STAGE_TIMEOUT_MS);
    if (rc != TRINITY_OK) goto fail_abort;

    rc = controller_commit_one(controller, TRINITY_TARGET_PRIMER1,
                               material->session_id, timeout_ms);
    if (rc == TRINITY_OK)
        rc = controller_commit_one(controller, TRINITY_TARGET_PRIMER2,
                                   material->session_id, timeout_ms);
    if (rc != TRINITY_OK) goto fail_abort;

    rc = controller_wait_session_state(controller,
                                       TRINITY_SESSION_COMMITTED_BLOCKED,
                                       material->session_id,
                                       CONTROLLER_SESSION_STAGE_TIMEOUT_MS);
    if (rc != TRINITY_OK) goto fail_abort;

    if (controller->ops.session_commit_toggle == NULL) {
        rc = TRINITY_SESSION_COMMIT_FAILED;
        goto fail_abort;
    }
    controller->ops.session_commit_toggle(controller->ops.context);
    controller->commit_issued = true;
    controller_progress(controller);

    rc = controller_wait_session_state(controller, TRINITY_SESSION_ACTIVE,
                                       material->session_id,
                                       CONTROLLER_SESSION_ACTIVE_TIMEOUT_MS);
    if (rc != TRINITY_OK) goto fail_zeroize;
    if ((controller->p1.secure_flags & TRINITY_SECURE_ENABLE) == 0u ||
        (controller->p2.secure_flags & TRINITY_SECURE_ENABLE) == 0u) {
        rc = TRINITY_SESSION_COMMIT_FAILED;
        goto fail_zeroize;
    }

    controller->session = *material;
    controller->session_material_valid = true;
    controller->current_sequence = 0u;
    controller->mode = mode;
    controller->state = TRINITY_SYSTEM_ACTIVE;
    controller->last_error = TRINITY_OK;
    return TRINITY_OK;

fail_abort:
    (void)controller_abort_one(controller, TRINITY_TARGET_PRIMER1,
                               material->session_id);
    (void)controller_abort_one(controller, TRINITY_TARGET_PRIMER2,
                               material->session_id);
fail_zeroize:
    (void)trinity_controller_zeroize(controller, TRINITY_ZEROIZE_ALL,
                                     timeout_ms);
    controller_latch_error(controller, rc, TRINITY_SOURCE_SN32,
                           material->session_id);
    return rc;
}

trinity_error_code_t trinity_controller_close_session(
    trinity_controller_t *controller,
    uint32_t timeout_ms) {
    trinity_error_code_t rc1;
