    (void)response_send();
}

static void full_handle_read_last_result(const trinity_pc_frame_t *req) {
    const trinity_controller_auth_result_t *result = &g_controller.last_result;
    if (!request_length_is(req, 0u)) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    if (!result->valid) {
        response_error(req, TRINITY_RESULT_NOT_READY,
                       TRINITY_SOURCE_PRIMER2, 0u);
        return;
    }
    g_pc_rsp.payload_length = 38u;
    trinity_write_be32(&g_pc_rsp.payload[0], result->session_id);
    trinity_write_be64(&g_pc_rsp.payload[4], result->sequence);
    memcpy(&g_pc_rsp.payload[12], result->plaintext,
           sizeof(result->plaintext));
    trinity_write_be16(&g_pc_rsp.payload[36], (uint16_t)result->status);
    (void)response_send();
}

static void full_handle_transport_stress(const trinity_pc_frame_t *req) {
    trinity_error_code_t rc;
    uint32_t count;
    if (!request_length_is(req, 8u) || req->payload[1] != 0u ||
        req->payload[2] != 0u || req->payload[3] != 0u) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    count = trinity_read_be32(&req->payload[4]);
    if (!managed_transaction_begin(req)) return;
    rc = trinity_controller_transport_stress(&g_controller,
                                              req->payload[0], count);
    managed_transaction_finish(rc, NULL, 0u);
    (void)response_send();
}
