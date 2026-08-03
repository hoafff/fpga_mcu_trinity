    uint32_t transaction_count) {
    uint32_t index;
    trinity_error_code_t rc = TRINITY_OK;
    if (controller == NULL || transaction_count == 0u)
        return TRINITY_BAD_LENGTH;
    if (link_id != 2u && link_id != 3u) return TRINITY_NOT_SUPPORTED;
    for (index = 0u; index < transaction_count; ++index) {
        rc = controller_get_status(controller,
            link_id == 2u ? &controller->p1 : &controller->p2);
        if (rc != TRINITY_OK) break;
        controller_progress(controller);
    }
    return rc;
}

uint8_t trinity_controller_ready_mask(const trinity_controller_t *controller) {
    uint8_t mask = TRINITY_READY_SN32;
    if (controller == NULL) return 0u;
    if (controller->p1.ready) mask |= TRINITY_READY_PRIMER1;
    if (controller->p2.ready) mask |= TRINITY_READY_PRIMER2;
    if (!controller_tiny_fault(controller)) mask |= TRINITY_READY_TINY1P5;
    return mask;
}

uint8_t trinity_controller_fault_mask(const trinity_controller_t *controller) {
    uint8_t mask = 0u;
    if (controller == NULL) return TRINITY_FAULT_SN32;
    if (controller->state == TRINITY_SYSTEM_ERROR ||
        controller->state == TRINITY_SYSTEM_FAULT_LOCKED)
        mask |= TRINITY_FAULT_SN32;
    if (!controller->p1.ready ||
        controller->p1.session_state == TRINITY_SESSION_FAULT_LOCKED)
        mask |= TRINITY_FAULT_PRIMER1;
    if (!controller->p2.ready ||
        controller->p2.session_state == TRINITY_SESSION_FAULT_LOCKED)
        mask |= TRINITY_FAULT_PRIMER2;
    if (controller_tiny_fault(controller)) mask |= TRINITY_FAULT_TINY1P5;
    if (controller->last_error == TRINITY_COMMIT_REJECTED ||
        controller->last_error == TRINITY_SESSION_COMMIT_FAILED)
        mask |= TRINITY_FAULT_COMMIT_REJECTED;
    if (controller->last_error == TRINITY_HEARTBEAT_TIMEOUT)
        mask |= TRINITY_FAULT_HEARTBEAT_TIMEOUT;
    if (controller->last_error == TRINITY_AUTH_THRESHOLD)
        mask |= TRINITY_FAULT_AUTH_THRESHOLD;
    if (controller->last_error == TRINITY_FRAME_TIMEOUT ||
        controller->last_error == TRINITY_BAD_CRC ||
        controller->last_error == TRINITY_TRANSACTION_CONFLICT)
        mask |= TRINITY_FAULT_TRANSPORT;
    return mask;
}

void trinity_controller_forget_last_result(trinity_controller_t *controller) {
    if (controller == NULL) return;
    trinity_controller_secure_clear(&controller->last_result,
                                    sizeof(controller->last_result));
}
