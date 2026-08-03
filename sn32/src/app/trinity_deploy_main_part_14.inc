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

static void handle_spi_diagnostic(const trinity_pc_frame_t *req) {
    endpoint_t *ep;
    trinity_error_code_t rc;
    uint8_t irq_flags = 0u;
    uint16_t offset = 24u;
    const uint8_t target_id = req->payload[0];
    const uint8_t command = req->payload[1];

    if (!request_length_is(req, 2u)) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    if ((target_id != TRINITY_TARGET_PRIMER1 &&
         target_id != TRINITY_TARGET_PRIMER2) ||
        (command != TRINITY_SPI_GET_INFO &&
         command != TRINITY_SPI_GET_STATUS)) {
        response_error(req, TRINITY_NOT_SUPPORTED,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }

    ep = target_id == TRINITY_TARGET_PRIMER1 ? &g_p1 : &g_p2;
    rc = endpoint_exchange(ep, command, NULL, 0u, NULL);
    if (!g_spi_trace.valid || g_spi_trace.target_id != target_id ||
        g_spi_trace.command != command) {
        response_error(req, TRINITY_INTERNAL_FAULT,
                       TRINITY_SOURCE_SN32, 0u);
        return;
    }

    if (g_spi_trace.irq_before_request) irq_flags |= 0x01u;
    if (g_spi_trace.irq_after_request) irq_flags |= 0x02u;
    if (g_spi_trace.irq_before_response) irq_flags |= 0x04u;
    if (g_spi_trace.irq_after_response) irq_flags |= 0x08u;

    g_pc_rsp.payload[0] = target_id;
    g_pc_rsp.payload[1] = command;
    g_pc_rsp.payload[2] = (uint8_t)g_spi_trace.source;
    g_pc_rsp.payload[3] = irq_flags;
    trinity_write_be16(&g_pc_rsp.payload[4], (uint16_t)rc);
    trinity_write_be16(&g_pc_rsp.payload[6], g_spi_trace.target_txid);
    trinity_write_be32(&g_pc_rsp.payload[8], g_spi_trace.request_fingerprint);
    trinity_write_be16(&g_pc_rsp.payload[12], g_spi_trace.request_length);
    trinity_write_be16(&g_pc_rsp.payload[14],
                       g_spi_trace.response_capture_length);
    trinity_write_be16(&g_pc_rsp.payload[16],
                       g_spi_trace.response_frame_length);
    trinity_write_be16(&g_pc_rsp.payload[18], g_spi_trace.request_crc);
    trinity_write_be16(&g_pc_rsp.payload[20],
                       g_spi_trace.response_crc_received);
    trinity_write_be16(&g_pc_rsp.payload[22],
                       g_spi_trace.response_crc_calculated);

    if ((uint32_t)offset + g_spi_trace.request_length +
            g_spi_trace.response_capture_length > TRINITY_PC_MAX_PAYLOAD) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_SN32, g_spi_trace.target_txid);
        return;
    }
    memcpy(&g_pc_rsp.payload[offset], g_spi_trace.request_bytes,
           g_spi_trace.request_length);
    offset = (uint16_t)(offset + g_spi_trace.request_length);
    memcpy(&g_pc_rsp.payload[offset], g_spi_trace.response_bytes,
           g_spi_trace.response_capture_length);
    offset = (uint16_t)(offset + g_spi_trace.response_capture_length);
    g_pc_rsp.payload_length = offset;
    (void)response_send();
}
