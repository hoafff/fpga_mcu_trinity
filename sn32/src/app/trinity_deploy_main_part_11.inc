    if (rc == TRINITY_OK)
        rc = trinity_cobs_encode(g_pc_raw, raw_len, g_pc_tx,
                                 sizeof(g_pc_tx) - 1u, &wire_len);
    if (rc == TRINITY_OK) {
        g_pc_tx[wire_len] = 0u;
        rc = uart_write(g_pc_tx, wire_len + 1u);
    }
    if (rc != TRINITY_OK) set_error(rc, TRINITY_SOURCE_SN32, 0u);
    return rc;
}

static void response_error(const trinity_pc_frame_t *req,
                           trinity_error_code_t code,
                           trinity_source_t source,
                           uint16_t related_target_txid) {
    response_begin(req);
    g_pc_rsp.flags |= TRINITY_FLAG_ERROR;
    g_pc_rsp.payload_length = 6u;
    trinity_write_be16(&g_pc_rsp.payload[0], (uint16_t)code);
    g_pc_rsp.payload[2] = system_state();
    g_pc_rsp.payload[3] = (uint8_t)source;
    trinity_write_be16(&g_pc_rsp.payload[4], related_target_txid);
    set_error(code, source, related_target_txid);
    (void)response_send();
}

static bool request_length_is(const trinity_pc_frame_t *req, uint16_t length) {
    return req != NULL && req->payload_length == length;
}

static void refresh_p1_status_best_effort(void) {
    const trinity_error_code_t rc = endpoint_get_status(&g_p1);
    if (rc != TRINITY_OK) {
        g_p1.ready = false;
        g_p1.last_error = (uint16_t)rc;
    }
}

static void handle_ping(const trinity_pc_frame_t *req) {
    if (!request_length_is(req, 0u)) {
        response_error(req, TRINITY_BAD_LENGTH, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    g_pc_rsp.payload_length = 4u;
    trinity_write_be32(g_pc_rsp.payload, g_ms);
    (void)response_send();
}

static void handle_get_system_info(const trinity_pc_frame_t *req) {
    trinity_error_code_t rc;
    if (!request_length_is(req, 0u)) {
        response_error(req, TRINITY_BAD_LENGTH, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    rc = endpoint_get_info(&g_p1);
    if (rc != TRINITY_OK) {
        g_p1.ready = false;
        response_error(req, rc, TRINITY_SOURCE_PRIMER1, 0u);
        return;
    }
