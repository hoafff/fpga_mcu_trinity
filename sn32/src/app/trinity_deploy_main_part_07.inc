    return id;
}

static trinity_source_t endpoint_source(const endpoint_t *ep) {
    return ep->id == TRINITY_TARGET_PRIMER1
               ? TRINITY_SOURCE_PRIMER1 : TRINITY_SOURCE_PRIMER2;
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

    rc = spi_select(ep);
    if (rc == TRINITY_OK) rc = spi_bytes(g_spi_buf, NULL, request_len);
    spi_end();
    if (rc != TRINITY_OK) goto failed;

    /*
     * A retained result keeps IRQ low after its mailbox has been read. Waiting
     * for a new IRQ edge would therefore be incorrect for GET_TXN_RESULT.
     * Give the 27 MHz endpoint one millisecond to build the new mailbox, then
     * validate the response header. A premature all-zero read is retried until
     * the bounded SPI timeout expires.
     */
    wait_ms(SPI_RESPONSE_SETTLE_MS);
    while (!expired(wait_start, TRINITY_DEPLOY_SPI_TIMEOUT_MS)) {
        if (!irq_active(ep)) {
            progress();
            continue;
        }

        rc = spi_select(ep);
        if (rc == TRINITY_OK)
            rc = spi_bytes(NULL, g_spi_buf, TRINITY_SPI_HEADER_SIZE);
        if (rc != TRINITY_OK) {
            spi_end();
            goto failed;
        }
