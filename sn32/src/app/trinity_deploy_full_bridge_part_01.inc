static void full_sync_legacy_status(void) {
    full_sync_endpoint(&g_p1, &g_controller.p1);
    full_sync_endpoint(&g_p2, &g_controller.p2);
    if (g_controller.state == TRINITY_SYSTEM_READY_NO_SESSION &&
        !g_crypto.keypair_valid)
        g_controller.state = TRINITY_SYSTEM_READY_NO_KEYPAIR;
    if (g_controller.last_error != TRINITY_OK)
        set_error(g_controller.last_error, g_controller.last_error_source,
                  g_controller.last_error_detail);
}

static void full_controller_bind(void) {
    const trinity_controller_ops_t ops = {
        NULL,
        full_exchange,
        full_now_ms,
        full_progress,
        full_session_commit_low,
        full_session_commit_high,
        full_tiny_fault_active
    };
    g_session_commit_level = false;
    g_tiny_fault_contained = false;
    gpio_write(FPST_SN32F407_SESSION_COMMIT_PORT,
               FPST_SN32F407_SESSION_COMMIT_PIN, false);
    gpio_set_mode(FPST_SN32F407_SESSION_COMMIT_PORT,
                  FPST_SN32F407_SESSION_COMMIT_PIN, true);
    gpio_set_cfg(FPST_SN32F407_SESSION_COMMIT_PORT,
                 FPST_SN32F407_SESSION_COMMIT_PIN,
                 GPIO_NO_PULL_SCHMITT);
    trinity_controller_init(&g_controller, &ops);
}

static trinity_error_code_t full_probe_all(void) {
    trinity_error_code_t rc = trinity_controller_probe_all(&g_controller);
    full_sync_legacy_status();
    return rc;
}

static trinity_error_code_t full_refresh_all(void) {
    trinity_error_code_t rc = trinity_controller_refresh_status(&g_controller);
    full_sync_legacy_status();
    return rc;
}

static bool managed_transaction_begin(const trinity_pc_frame_t *req) {
    const uint32_t fingerprint = pc_request_fingerprint(req);
    if (g_host_txn.valid) {
        if (g_host_txn.host_txid == req->transaction_id &&
            g_host_txn.original_host_command == req->command &&
            g_host_txn.request_fingerprint == fingerprint) {
            (void)response_send();
        } else if (g_host_txn.host_txid == req->transaction_id) {
            response_error(req, TRINITY_TRANSACTION_CONFLICT,
                           TRINITY_SOURCE_HOST_PROTOCOL,
                           g_host_txn.target_txid);
        } else {
            response_error(req, TRINITY_RESULT_PENDING,
                           TRINITY_SOURCE_SN32,
                           g_host_txn.target_txid);
        }
        return false;
    }
    memset(&g_host_txn, 0, sizeof(g_host_txn));
    g_host_txn.valid = true;
    g_host_txn.host_txid = req->transaction_id;
    g_host_txn.target_txid = 0u;
    g_host_txn.original_host_command = req->command;
    g_host_txn.request_fingerprint = fingerprint;
    g_host_txn.state = TRINITY_TXN_RUNNING;
    g_host_txn.result_code = TRINITY_OK;
    g_active_host_txid = req->transaction_id;
    return true;
}

static void managed_transaction_finish(trinity_error_code_t rc,
                                       const uint8_t *result,
                                       uint16_t result_length) {
    if (result_length > sizeof(g_host_txn.result_data)) {
        rc = TRINITY_BAD_LENGTH;
        result_length = 0u;
    }
    g_host_txn.state = rc == TRINITY_OK ? TRINITY_TXN_SUCCEEDED
                                       : TRINITY_TXN_FAILED;
    g_host_txn.result_code = rc;
