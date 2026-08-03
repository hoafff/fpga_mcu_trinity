    (void)rc;
    full_handle_run_self_test(req);
}

static trinity_error_code_t refresh_host_transaction(void) {
    trinity_error_code_t rc;
    uint8_t payload[2];
    uint16_t target_length;

    if (!g_host_txn.valid) return TRINITY_RESULT_NOT_READY;
    if (g_host_txn.target_txid == 0u) return TRINITY_OK;

    trinity_write_be16(payload, g_host_txn.target_txid);
    rc = endpoint_exchange(&g_p1, TRINITY_SPI_GET_TXN_RESULT,
                           payload, sizeof(payload), NULL);
    if (rc != TRINITY_OK) return rc;
    if (g_spi_rsp.payload_length < 10u ||
        g_spi_rsp.payload[8] != 0u || g_spi_rsp.payload[9] != 0u ||
        trinity_read_be16(&g_spi_rsp.payload[0]) != g_host_txn.target_txid ||
        g_spi_rsp.payload[3] != TRINITY_SPI_RUN_SELF_TEST)
        return TRINITY_TRANSACTION_CONFLICT;

    target_length = trinity_read_be16(&g_spi_rsp.payload[6]);
    if (target_length > sizeof(g_host_txn.result_data) ||
        g_spi_rsp.payload_length != (uint16_t)(10u + target_length))
        return TRINITY_BAD_LENGTH;

    if (g_spi_rsp.payload[2] > (uint8_t)TRINITY_TXN_OUTCOME_UNKNOWN)
        return TRINITY_BAD_STATE;
    g_host_txn.state = (trinity_transaction_state_t)g_spi_rsp.payload[2];
    g_host_txn.result_code =
        (trinity_error_code_t)trinity_read_be16(&g_spi_rsp.payload[4]);
    g_host_txn.result_length = target_length;
    memset(g_host_txn.result_data, 0, sizeof(g_host_txn.result_data));
    if (target_length != 0u)
        memcpy(g_host_txn.result_data, &g_spi_rsp.payload[10], target_length);
    return TRINITY_OK;
}

static void handle_get_txn_result(const trinity_pc_frame_t *req) {
    trinity_error_code_t rc;
    uint16_t query_txid;
    if (!request_length_is(req, 2u)) {
        response_error(req, TRINITY_BAD_LENGTH, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    query_txid = trinity_read_be16(req->payload);
    if (!g_host_txn.valid || query_txid != g_host_txn.host_txid) {
        response_error(req, TRINITY_RESULT_NOT_READY,
                       TRINITY_SOURCE_SN32, 0u);
        return;
    }
    rc = refresh_host_transaction();
    if (rc != TRINITY_OK) {
        response_error(req, rc, TRINITY_SOURCE_SN32,
                       g_host_txn.target_txid);
        return;
    }

    g_pc_rsp.payload_length = (uint16_t)(8u + g_host_txn.result_length);
    trinity_write_be16(&g_pc_rsp.payload[0], g_host_txn.host_txid);
    g_pc_rsp.payload[2] = (uint8_t)g_host_txn.state;
    g_pc_rsp.payload[3] = g_host_txn.original_host_command;
    trinity_write_be16(&g_pc_rsp.payload[4], (uint16_t)g_host_txn.result_code);
    trinity_write_be16(&g_pc_rsp.payload[6], g_host_txn.result_length);
    if (g_host_txn.result_length != 0u)
        memcpy(&g_pc_rsp.payload[8], g_host_txn.result_data,
               g_host_txn.result_length);
    (void)response_send();
}
