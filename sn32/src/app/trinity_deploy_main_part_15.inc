    trinity_error_code_t rc;
    uint8_t payload[2];
    uint16_t query_txid;
    if (!request_length_is(req, 2u)) {
        response_error(req, TRINITY_BAD_LENGTH, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    query_txid = trinity_read_be16(req->payload);
    if (!g_host_txn.valid || query_txid != g_host_txn.host_txid) {
        (void)response_send();
        return;
    }
    trinity_write_be16(payload, g_host_txn.target_txid);
    rc = endpoint_exchange(&g_p1, TRINITY_SPI_RETIRE_TXN_RESULT,
                           payload, sizeof(payload), NULL);
    if (rc != TRINITY_OK) {
        response_error(req, rc, TRINITY_SOURCE_PRIMER1,
                       g_host_txn.target_txid);
        return;
    }
    memset(&g_host_txn, 0, sizeof(g_host_txn));
    g_active_host_txid = 0u;
    refresh_p1_status_best_effort();
    (void)response_send();
}

static void handle_request(const trinity_pc_frame_t *req) {
    response_begin(req);
    if (req->flags != 0u) {
        response_error(req, TRINITY_BAD_FLAGS, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }

    switch (req->command) {
        case TRINITY_PC_PING:
            handle_ping(req);
            break;
        case TRINITY_PC_GET_SYSTEM_INFO:
            handle_get_system_info(req);
            break;
        case TRINITY_PC_GET_SYSTEM_STATUS:
            handle_get_system_status(req);
            break;
        case TRINITY_PC_GET_LAST_ERROR:
            handle_get_last_error(req);
            break;
        case TRINITY_PC_RUN_SELF_TEST:
            handle_run_self_test(req);
            break;
        case TRINITY_PC_GET_TXN_RESULT:
            handle_get_txn_result(req);
            break;
        case TRINITY_PC_RETIRE_TXN_RESULT:
            handle_retire_txn_result(req);
            break;
        default:
            response_error(req, TRINITY_NOT_SUPPORTED, TRINITY_SOURCE_SN32, 0u);
            break;
    }
    g_active_host_txid = g_host_txn.valid ? g_host_txn.host_txid : 0u;
