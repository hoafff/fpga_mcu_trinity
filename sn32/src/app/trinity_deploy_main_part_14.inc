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

static bool serialize_spi_trace(const spi_exchange_trace_t *trace,
                                uint16_t base, uint16_t *payload_length) {
    uint8_t irq_flags = 0u;
    uint16_t offset = (uint16_t)(base + 24u);
    if (trace == NULL || payload_length == NULL || !trace->valid)
        return false;
    if ((uint32_t)offset + trace->request_length +
            trace->response_capture_length > TRINITY_PC_MAX_PAYLOAD)
        return false;

    if (trace->irq_before_request) irq_flags |= 0x01u;
    if (trace->irq_after_request) irq_flags |= 0x02u;
    if (trace->irq_before_response) irq_flags |= 0x04u;
    if (trace->irq_after_response) irq_flags |= 0x08u;

    g_pc_rsp.payload[base + 0u] = trace->target_id;
    g_pc_rsp.payload[base + 1u] = trace->command;
    g_pc_rsp.payload[base + 2u] = (uint8_t)trace->source;
    g_pc_rsp.payload[base + 3u] = irq_flags;
    trinity_write_be16(&g_pc_rsp.payload[base + 4u],
                       (uint16_t)trace->result_code);
    trinity_write_be16(&g_pc_rsp.payload[base + 6u], trace->target_txid);
    trinity_write_be32(&g_pc_rsp.payload[base + 8u],
                       trace->request_fingerprint);
    trinity_write_be16(&g_pc_rsp.payload[base + 12u], trace->request_length);
    trinity_write_be16(&g_pc_rsp.payload[base + 14u],
                       trace->response_capture_length);
    trinity_write_be16(&g_pc_rsp.payload[base + 16u],
                       trace->response_frame_length);
    trinity_write_be16(&g_pc_rsp.payload[base + 18u], trace->request_crc);
    trinity_write_be16(&g_pc_rsp.payload[base + 20u],
                       trace->response_crc_received);
    trinity_write_be16(&g_pc_rsp.payload[base + 22u],
                       trace->response_crc_calculated);

    memcpy(&g_pc_rsp.payload[offset], trace->request_bytes,
           trace->request_length);
    offset = (uint16_t)(offset + trace->request_length);
    memcpy(&g_pc_rsp.payload[offset], trace->response_bytes,
           trace->response_capture_length);
    *payload_length = (uint16_t)(offset + trace->response_capture_length);
    return true;
}

static void handle_spi_diagnostic(const trinity_pc_frame_t *req) {
    endpoint_t *ep;
    trinity_error_code_t rc;
    uint8_t target_id;
    uint8_t command;
    uint16_t payload_length;

    if (!request_length_is(req, 2u)) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    target_id = req->payload[0];
    command = req->payload[1];
    if ((target_id != TRINITY_TARGET_PRIMER1 &&
         target_id != TRINITY_TARGET_PRIMER2) ||
        (command != TRINITY_SPI_GET_INFO &&
         command != TRINITY_SPI_GET_STATUS)) {
        response_error(req, TRINITY_NOT_SUPPORTED,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }

    ep = target_id == TRINITY_TARGET_PRIMER1 ? &g_p1 : &g_p2;
    g_spi_trace_context = SPI_TRACE_CONTEXT_HOST_DIAGNOSTIC;
    rc = endpoint_exchange(ep, command, NULL, 0u, NULL);
    g_spi_trace_context = SPI_TRACE_CONTEXT_NONE;
    if (!g_spi_trace.valid || g_spi_trace.target_id != target_id ||
        g_spi_trace.command != command) {
        response_error(req, TRINITY_INTERNAL_FAULT,
                       TRINITY_SOURCE_SN32, 0u);
        return;
    }

    if (!serialize_spi_trace(&g_spi_trace, 0u, &payload_length)) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_SN32, g_spi_trace.target_txid);
        return;
    }
    g_pc_rsp.payload_length = payload_length;
    (void)rc;
    (void)response_send();
}

static void handle_get_first_spi_failure(const trinity_pc_frame_t *req) {
    const spi_exchange_trace_t *trace = NULL;
    uint16_t payload_length;
    if (!request_length_is(req, 0u)) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }

    if (g_spi_first_failure.valid) {
        g_pc_rsp.payload[0] = 1u;
        trace = &g_spi_first_failure;
    } else if (g_spi_startup_residue.valid) {
        g_pc_rsp.payload[0] = 0u;
        trace = &g_spi_startup_residue;
    } else {
        g_pc_rsp.payload[0] = 0u;
    }
    g_pc_rsp.payload[1] = trace != NULL ? trace->context
                                        : SPI_TRACE_CONTEXT_NONE;
    if (trace == NULL) {
        g_pc_rsp.payload_length = 2u;
        (void)response_send();
        return;
    }
    if (!serialize_spi_trace(trace, 2u, &payload_length)) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_SN32, trace->target_txid);
        return;
    }
    g_pc_rsp.payload_length = payload_length;
    (void)response_send();
}
