    g_pc_rsp.payload_length = 20u;
    g_pc_rsp.payload[0] = TRINITY_PROTOCOL_VERSION;
    g_pc_rsp.payload[1] = TRINITY_DEPLOY_VERSION_MAJOR;
    g_pc_rsp.payload[2] = TRINITY_DEPLOY_VERSION_MINOR;
    g_pc_rsp.payload[3] = 0u;
    trinity_write_be32(&g_pc_rsp.payload[4],
        TRINITY_SYSTEM_CAP_KAT |
        TRINITY_SYSTEM_CAP_PRIMER1_ACCELERATOR |
        TRINITY_SYSTEM_CAP_ASCON_AEAD128 |
        TRINITY_SYSTEM_CAP_PAYLOAD_UART |
        TRINITY_SYSTEM_CAP_TRANSACTION_RECONCILIATION);
    trinity_write_be32(&g_pc_rsp.payload[8], DEPLOY_BUILD_ID);
    trinity_write_be32(&g_pc_rsp.payload[12], g_p1.build_id);
#if TRINITY_DEPLOY_P1_BRINGUP_ONLY == 0
    trinity_write_be32(&g_pc_rsp.payload[16], g_p2.ready ? g_p2.build_id : 0u);
#else
    trinity_write_be32(&g_pc_rsp.payload[16], 0u);
#endif
    (void)response_send();
}

static void handle_get_system_status(const trinity_pc_frame_t *req) {
    trinity_error_code_t rc;
    if (!request_length_is(req, 0u)) {
        response_error(req, TRINITY_BAD_LENGTH, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    rc = endpoint_get_status(&g_p1);
    if (rc != TRINITY_OK) {
        g_p1.ready = false;
        response_error(req, rc, TRINITY_SOURCE_PRIMER1, 0u);
        return;
    }
    g_pc_rsp.payload_length = 20u;
    g_pc_rsp.payload[0] = system_state();
    g_pc_rsp.payload[1] = (uint8_t)TRINITY_MODE_KAT;
    g_pc_rsp.payload[2] = ready_mask();
    g_pc_rsp.payload[3] = fault_mask();
    trinity_write_be32(&g_pc_rsp.payload[4], g_p1.session_id);
    trinity_write_be64(&g_pc_rsp.payload[8], 0u);
    trinity_write_be16(&g_pc_rsp.payload[16], g_p1.last_error);
    trinity_write_be16(&g_pc_rsp.payload[18], g_active_host_txid);
    (void)response_send();
}

static void handle_get_last_error(const trinity_pc_frame_t *req) {
    if (!request_length_is(req, 0u)) {
        response_error(req, TRINITY_BAD_LENGTH, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    g_pc_rsp.payload_length = 8u;
    trinity_write_be16(&g_pc_rsp.payload[0], (uint16_t)g_error.code);
    g_pc_rsp.payload[2] = (uint8_t)g_error.source;
    g_pc_rsp.payload[3] = 0u;
    trinity_write_be32(&g_pc_rsp.payload[4], g_error.detail);
    (void)response_send();
}

static void handle_run_self_test(const trinity_pc_frame_t *req) {
    trinity_error_code_t rc;
