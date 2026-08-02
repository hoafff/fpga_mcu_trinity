    uint8_t target_payload[4];
    uint16_t target_txid = 0u;
    const uint32_t fingerprint = pc_request_fingerprint(req);

    if (!request_length_is(req, 4u) ||
        req->payload[0] != TRINITY_READY_PRIMER1 ||
        req->payload[1] > (uint8_t)TRINITY_TEST_PROFILE_DIAGNOSTIC) {
        response_error(req, TRINITY_BAD_LENGTH, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    if (!g_p1.ready) {
        response_error(req, TRINITY_BAD_STATE, TRINITY_SOURCE_PRIMER1, 0u);
        return;
    }
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
                           TRINITY_SOURCE_PRIMER1,
                           g_host_txn.target_txid);
        }
        return;
    }

    target_payload[0] = req->payload[2];
    target_payload[1] = req->payload[3];
    target_payload[2] = 0u;
    target_payload[3] = 0u;
    rc = endpoint_exchange(&g_p1, TRINITY_SPI_RUN_SELF_TEST,
                           target_payload, sizeof(target_payload), &target_txid);
    if (rc != TRINITY_OK) {
        response_error(req, rc, TRINITY_SOURCE_PRIMER1, target_txid);
        return;
    }

    memset(&g_host_txn, 0, sizeof(g_host_txn));
    g_host_txn.valid = true;
    g_host_txn.host_txid = req->transaction_id;
    g_host_txn.target_txid = target_txid;
    g_host_txn.original_host_command = req->command;
    g_host_txn.request_fingerprint = fingerprint;
    g_host_txn.state = TRINITY_TXN_RUNNING;
    g_host_txn.result_code = TRINITY_OK;
    g_active_host_txid = req->transaction_id;
    (void)response_send();
}

static trinity_error_code_t refresh_host_transaction(void) {
    trinity_error_code_t rc;
    uint8_t payload[2];
    uint16_t target_length;

    if (!g_host_txn.valid) return TRINITY_RESULT_NOT_READY;
