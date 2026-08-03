    return id;
}

static trinity_source_t endpoint_source(const endpoint_t *ep) {
    return ep->id == TRINITY_TARGET_PRIMER1
               ? TRINITY_SOURCE_PRIMER1 : TRINITY_SOURCE_PRIMER2;
}

static void spi_trace_begin(endpoint_t *ep, uint8_t command,
                            uint16_t txid, uint32_t fingerprint) {
    memset(&g_spi_trace, 0, sizeof(g_spi_trace));
    g_spi_trace.valid = true;
    g_spi_trace.target_id = ep->id;
    g_spi_trace.command = command;
    g_spi_trace.source = endpoint_source(ep);
    g_spi_trace.result_code = TRINITY_OK;
    g_spi_trace.target_txid = txid;
    g_spi_trace.request_fingerprint = fingerprint;
}

static trinity_error_code_t spi_drain_startup_mailbox(endpoint_t *ep) {
    trinity_error_code_t rc;
    unsigned attempt;
    if (ep == NULL) return TRINITY_BAD_STATE;
    if (!irq_active(ep)) return TRINITY_OK;

    for (attempt = 0u; attempt < 3u; ++attempt) {
        rc = spi_select(ep);
        if (rc == TRINITY_OK)
            rc = spi_bytes(NULL, g_spi_buf, TRINITY_SPI_MAX_PACKET);
        spi_end();
        if (rc != TRINITY_OK) return rc;
        wait_ms(SPI_RESPONSE_SETTLE_MS);
        if (!irq_active(ep)) return TRINITY_OK;
    }
    return TRINITY_RESULT_PENDING;
}

static trinity_error_code_t endpoint_exchange(
    endpoint_t *ep,
    uint8_t command,
    const uint8_t *payload,
    uint16_t payload_length,
    uint16_t *issued_txid) {
    trinity_error_code_t rc;
    size_t request_len = 0u;
    size_t response_len;
    uint16_t response_payload_length;
    const uint16_t txid = next_spi_txid();
    const uint32_t wait_start = g_ms;

    if (issued_txid != NULL) *issued_txid = txid;
    if (payload_length > TRINITY_SPI_MAX_PAYLOAD ||
        (payload == NULL && payload_length != 0u))
        return TRINITY_BAD_LENGTH;

    memset(&g_spi_req, 0, sizeof(g_spi_req));
    g_spi_req.version = TRINITY_PROTOCOL_VERSION;
    g_spi_req.command = command;
    g_spi_req.transaction_id = txid;
    g_spi_req.payload_length = payload_length;
    if (payload_length != 0u) memcpy(g_spi_req.payload, payload, payload_length);
    rc = trinity_spi_encode(&g_spi_req, g_spi_buf, sizeof(g_spi_buf), &request_len);
    if (rc != TRINITY_OK) return rc;

    spi_trace_begin(ep, command, txid,
                    trinity_spi_request_fingerprint(command, 0u,
                                                    payload, payload_length));
    g_spi_trace.request_length = (uint16_t)request_len;
    memcpy(g_spi_trace.request_bytes, g_spi_buf, request_len);
    g_spi_trace.request_crc = trinity_read_be16(&g_spi_buf[request_len - 2u]);
    g_spi_trace.irq_before_request = irq_active(ep);

    rc = spi_select(ep);
    if (rc == TRINITY_OK) rc = spi_bytes(g_spi_buf, NULL, request_len);
    spi_end();
    g_spi_trace.irq_after_request = irq_active(ep);
    if (rc != TRINITY_OK) goto failed;

    /*
     * The Primer mailbox restarts at byte zero on every CS falling edge. Read
     * the complete maximum packet under one CS assertion, then decode only the
     * frame length declared by its header. Splitting header and payload across
     * two CS assertions corrupts every response longer than eight bytes.
     */
    wait_ms(SPI_RESPONSE_SETTLE_MS);
    while (!expired(wait_start, TRINITY_DEPLOY_SPI_TIMEOUT_MS)) {
        if (!irq_active(ep)) {
            progress();
            continue;
        }

        g_spi_trace.irq_before_response = irq_active(ep);
        rc = spi_select(ep);
        if (rc == TRINITY_OK)
            rc = spi_bytes(NULL, g_spi_buf, TRINITY_SPI_MAX_PACKET);
        spi_end();
        wait_ms(SPI_RESPONSE_SETTLE_MS);
        g_spi_trace.irq_after_response = irq_active(ep);
        if (rc != TRINITY_OK) goto failed;

        g_spi_trace.response_capture_length = TRINITY_SPI_MAX_PACKET;
        memcpy(g_spi_trace.response_bytes, g_spi_buf,
               TRINITY_SPI_MAX_PACKET);
