    rc = full_probe_all();
    if (rc != TRINITY_OK) {
        response_error(req, rc, g_controller.last_error_source, 0u);
        return;
    }
    g_pc_rsp.payload_length = 20u;
    g_pc_rsp.payload[0] = TRINITY_PROTOCOL_VERSION;
    g_pc_rsp.payload[1] = TRINITY_DEPLOY_VERSION_MAJOR;
    g_pc_rsp.payload[2] = TRINITY_DEPLOY_VERSION_MINOR;
    g_pc_rsp.payload[3] = TRINITY_DEPLOY_VERSION_PATCH;
    trinity_write_be32(&g_pc_rsp.payload[4],
        TRINITY_SYSTEM_CAP_KAT |
        TRINITY_SYSTEM_CAP_DEMO_DETERMINISTIC |
#if TRINITY_DEPLOY_ENABLE_MLKEM
        TRINITY_SYSTEM_CAP_MLKEM512 |
#endif
        TRINITY_SYSTEM_CAP_PRIMER1_ACCELERATOR |
        TRINITY_SYSTEM_CAP_ASCON_AEAD128 |
        TRINITY_SYSTEM_CAP_PAYLOAD_UART |
        TRINITY_SYSTEM_CAP_TINY_SUPERVISOR |
        TRINITY_SYSTEM_CAP_BENCHMARK |
        TRINITY_SYSTEM_CAP_TRANSPORT_STRESS |
        TRINITY_SYSTEM_CAP_TRANSACTION_RECONCILIATION);
    trinity_write_be32(&g_pc_rsp.payload[8], DEPLOY_BUILD_ID);
    trinity_write_be32(&g_pc_rsp.payload[12], g_controller.p1.build_id);
    trinity_write_be32(&g_pc_rsp.payload[16], g_controller.p2.build_id);
    (void)response_send();
}

static void handle_get_system_status(const trinity_pc_frame_t *req) {
    trinity_error_code_t rc = TRINITY_OK;
    uint8_t ready_mask;
    uint8_t fault_mask;
    if (!request_length_is(req, 0u)) {
        response_error(req, TRINITY_BAD_LENGTH, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    if (!g_fault) rc = full_refresh_all();
    if (rc != TRINITY_OK) {
        response_error(req, rc, g_controller.last_error_source, 0u);
        return;
    }

    ready_mask = trinity_controller_ready_mask(&g_controller);
#if !FPST_SN32F407_HARNESS_VERIFIED
    ready_mask &= (uint8_t)~TRINITY_READY_TINY1P5;
#endif
    fault_mask = trinity_controller_fault_mask(&g_controller);
    if (g_fault) fault_mask |= TRINITY_FAULT_SN32;

    g_pc_rsp.payload_length = 20u;
    g_pc_rsp.payload[0] = system_state();
    g_pc_rsp.payload[1] = (uint8_t)g_controller.mode;
    g_pc_rsp.payload[2] = ready_mask;
    g_pc_rsp.payload[3] = fault_mask;
    trinity_write_be32(&g_pc_rsp.payload[4],
                       g_controller.session_material_valid
                           ? g_controller.session.session_id : 0u);
    trinity_write_be64(&g_pc_rsp.payload[8], g_controller.current_sequence);
    trinity_write_be16(&g_pc_rsp.payload[16],
                       (uint16_t)(g_error.code != TRINITY_OK
                                      ? g_error.code
                                      : g_controller.last_error));
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
