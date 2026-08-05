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
                                const uint8_t *request_bytes,
                                const uint8_t *response_bytes,
                                uint16_t base, uint16_t *payload_length) {
    uint8_t irq_flags = 0u;
    uint16_t offset = (uint16_t)(base + 24u);
    if (trace == NULL || request_bytes == NULL || response_bytes == NULL ||
        payload_length == NULL || !trace->valid)
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

    memcpy(&g_pc_rsp.payload[offset], request_bytes,
           trace->request_length);
    offset = (uint16_t)(offset + trace->request_length);
    memcpy(&g_pc_rsp.payload[offset], response_bytes,
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

    /*
     * endpoint_exchange() accepts a response only after decoding the canonical
     * wire buffers.  Serialize those same accepted bytes for a live diagnostic
     * instead of the redundant per-byte trace mirror.  Hardware v0.7.23 proved
     * that the mirror could disagree with an exchange whose canonical request,
     * response and CRC had already passed locally.
     */
    if (!serialize_spi_trace(&g_spi_trace,
                             g_spi_request_wire,
                             g_spi_response_wire,
                             0u, &payload_length)) {
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
    const uint8_t *request_bytes = NULL;
    const uint8_t *response_bytes = NULL;
    uint16_t payload_length;
    uint16_t sample_offset;
    uint16_t max_samples;
    uint8_t sample_count;
    unsigned i;
    if (!request_length_is(req, 0u)) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }

    if (g_spi_retained_failure) {
        g_pc_rsp.payload[0] = 1u;
        trace = &g_spi_retained_trace.metadata;
        request_bytes = g_spi_retained_trace.request_bytes;
        response_bytes = g_spi_retained_trace.response_bytes;
    } else if (g_spi_retained_startup_residue) {
        g_pc_rsp.payload[0] = 0u;
        trace = &g_spi_retained_trace.metadata;
        request_bytes = g_spi_retained_trace.request_bytes;
        response_bytes = g_spi_retained_trace.response_bytes;
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
    if (!serialize_spi_trace(trace,
                             request_bytes,
                             response_bytes,
                             2u, &payload_length) ||
        (uint32_t)payload_length + 12u > TRINITY_PC_MAX_PAYLOAD) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_SN32, trace->target_txid);
        return;
    }

    /*
     * The 12-byte transfer extension is the mandatory compact form understood
     * by the PC host.  Register snapshots and FIFO samples are optional.  A
     * large retained request/response trace must therefore degrade to this
     * compact extension instead of turning the diagnostic query itself into
     * BAD_LENGTH.
     */
    g_pc_rsp.payload[payload_length + 0u] = trace->transfer_stage;
    g_pc_rsp.payload[payload_length + 1u] = trace->transfer_direction;
    trinity_write_be16(&g_pc_rsp.payload[payload_length + 2u],
                       trace->transfer_byte_index);
    trinity_write_be16(&g_pc_rsp.payload[payload_length + 4u],
                       trace->transfer_length);
    trinity_write_be16(&g_pc_rsp.payload[payload_length + 6u],
                       trace->transfer_completed);
    trinity_write_be32(&g_pc_rsp.payload[payload_length + 8u],
                       trace->spi_status);

    if ((uint32_t)payload_length + 32u > TRINITY_PC_MAX_PAYLOAD) {
        g_pc_rsp.payload_length = (uint16_t)(payload_length + 12u);
        (void)response_send();
        return;
    }

    trinity_write_be32(&g_pc_rsp.payload[payload_length + 12u],
                       trace->spi_ctrl0);
    trinity_write_be32(&g_pc_rsp.payload[payload_length + 16u],
                       trace->spi_ctrl1);
    trinity_write_be32(&g_pc_rsp.payload[payload_length + 20u],
                       trace->spi_clkdiv);
    trinity_write_be32(&g_pc_rsp.payload[payload_length + 24u],
                       trace->spi_fifo_th);

    max_samples = (uint16_t)((TRINITY_PC_MAX_PAYLOAD -
                              (payload_length + 32u)) / 12u);
    sample_count = trace->response_sample_count;
    if (sample_count > SPI_RESPONSE_SAMPLE_MAX)
        sample_count = SPI_RESPONSE_SAMPLE_MAX;
    if (sample_count > max_samples)
        sample_count = (uint8_t)max_samples;
    g_pc_rsp.payload[payload_length + 28u] = sample_count;
    g_pc_rsp.payload[payload_length + 29u] = 0u;
    g_pc_rsp.payload[payload_length + 30u] = 0u;
    g_pc_rsp.payload[payload_length + 31u] = 0u;

    sample_offset = (uint16_t)(payload_length + 32u);
    for (i = 0u; i < sample_count; ++i) {
        trinity_write_be32(&g_pc_rsp.payload[sample_offset + 0u],
                           trace->response_status_before_read[i]);
        trinity_write_be32(&g_pc_rsp.payload[sample_offset + 4u],
                           trace->response_data_words[i]);
        trinity_write_be32(&g_pc_rsp.payload[sample_offset + 8u],
                           trace->response_status_after_read[i]);
        sample_offset = (uint16_t)(sample_offset + 12u);
    }
    g_pc_rsp.payload_length = sample_offset;
    (void)response_send();
}
