static void handle_retire_txn_result(const trinity_pc_frame_t *req) {
    trinity_error_code_t rc = TRINITY_OK;
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
    if (g_host_txn.target_txid != 0u) {
        trinity_write_be16(payload, g_host_txn.target_txid);
        rc = endpoint_exchange(&g_p1, TRINITY_SPI_RETIRE_TXN_RESULT,
                               payload, sizeof(payload), NULL);
    }
    if (rc != TRINITY_OK) {
        response_error(req, rc, TRINITY_SOURCE_SN32,
                       g_host_txn.target_txid);
        return;
    }
    memset(&g_host_txn, 0, sizeof(g_host_txn));
    g_active_host_txid = 0u;
    (void)full_refresh_all();
    (void)response_send();
}
