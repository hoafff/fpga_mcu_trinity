}

static void pc_reset(void) {
    g_pc_wire_len = 0u;
    g_pc_frame_start = 0u;
}

static void pc_process(void) {
    size_t raw_len = 0u;
    trinity_error_code_t rc = trinity_cobs_decode(
        g_pc_wire, g_pc_wire_len, g_pc_raw, sizeof(g_pc_raw), &raw_len);
    if (rc == TRINITY_OK)
        rc = trinity_pc_decode_raw(g_pc_raw, raw_len, &g_pc_req);
    pc_reset();
    if (rc == TRINITY_OK) handle_request(&g_pc_req);
    else set_error(rc, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
}

static void pc_poll(void) {
    uint8_t byte;
    if (!g_pc_service_enabled || g_pc_poll_active) return;
    g_pc_poll_active = true;

    if (g_pc_wire_len != 0u && expired(g_pc_frame_start, PC_FRAME_TIMEOUT_MS)) {
        pc_reset();
        set_error(TRINITY_FRAME_TIMEOUT, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
    }
    while (uart_read(&byte)) {
        progress();
        if (byte == 0u) {
            if (g_pc_wire_len != 0u) pc_process();
        } else if (g_pc_wire_len < sizeof(g_pc_wire)) {
            if (g_pc_wire_len == 0u) g_pc_frame_start = g_ms;
            g_pc_wire[g_pc_wire_len++] = byte;
        } else {
            pc_reset();
            set_error(TRINITY_BAD_LENGTH, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        }
    }

    g_pc_poll_active = false;
}

static trinity_error_code_t hardware_init(void) {
    trinity_error_code_t rc;
    uint32_t faults;
    g_trinity_deploy_marker = DEPLOY_MARKER_BOOT;
    g_trinity_deploy_last_error = 0u;
    g_ms = g_progress_ms = g_heartbeat_ms = g_guard_faults = 0u;
    g_crypto_lease_deadline_ms = 0u;
    g_crypto_lease_active = false;
    g_fault = g_spi_selected = false;
    g_uart_ready = g_spi_ready = g_heartbeat_level = false;
    g_pc_service_enabled = false;
    g_pc_poll_active = false;
    g_automatic_probe_active = true;
    g_spi_txid = 1u;
    g_active_host_txid = 0u;
    g_spi_trace_work = &g_spi_trace_slots[0];
    g_spi_retained_trace = NULL;
    g_spi_retained_failure = false;
    g_spi_retained_startup_residue = false;
    memset(g_spi_trace_slots, 0, sizeof(g_spi_trace_slots));
    memset(&g_error, 0, sizeof(g_error));
    memset(&g_host_txn, 0, sizeof(g_host_txn));
    pc_reset();

    guard_apply();
    faults = guard_check();
    if (faults != FPST_P010_VIOLATION_NONE) {
        set_error(TRINITY_FAULT_LOCKED, TRINITY_SOURCE_SN32, faults);
        g_fault = true;
        g_trinity_deploy_marker = DEPLOY_MARKER_ERR;
        return TRINITY_FAULT_LOCKED;
    }
