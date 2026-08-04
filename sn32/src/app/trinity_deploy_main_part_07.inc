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
    g_spi_trace.context = g_spi_trace_context;
    g_spi_trace.target_id = ep->id;
    g_spi_trace.command = command;
    g_spi_trace.source = endpoint_source(ep);
    g_spi_trace.result_code = TRINITY_OK;
    g_spi_trace.target_txid = txid;
    g_spi_trace.request_fingerprint = fingerprint;
}

static void spi_latch_first_failure(void) {
    if (!g_spi_first_failure.valid && g_spi_trace.valid &&
        g_spi_trace.result_code != TRINITY_OK) {
        g_spi_first_failure = g_spi_trace;
    }
}

static bool spi_trace_is_startup_reset_residue(
    const spi_exchange_trace_t *trace) {
    const uint8_t *rsp;
    if (trace == NULL || !trace->valid) return false;
    if (trace->context != SPI_TRACE_CONTEXT_STARTUP_DRAIN_P1 &&
        trace->context != SPI_TRACE_CONTEXT_STARTUP_DRAIN_P2)
        return false;
    if (trace->result_code != TRINITY_BAD_LENGTH ||
        trace->command != 0u || trace->target_txid != 0u ||
        trace->request_length != 0u ||
        trace->response_capture_length != 16u ||
        trace->response_frame_length != 16u ||
        trace->response_crc_received != trace->response_crc_calculated)
        return false;

    rsp = trace->response_bytes;
    return rsp[0] == TRINITY_SPI_MAGIC &&
           rsp[1] == TRINITY_PROTOCOL_VERSION &&
           rsp[2] == 0u &&
           rsp[3] == (TRINITY_FLAG_RESPONSE | TRINITY_FLAG_ERROR) &&
           rsp[4] == 0u && rsp[5] == 0u &&
           rsp[6] == 0u && rsp[7] == 6u &&
           rsp[8] == (uint8_t)(TRINITY_BAD_LENGTH >> 8) &&
           rsp[9] == (uint8_t)TRINITY_BAD_LENGTH &&
           rsp[10] == 1u && rsp[11] == 0u &&
           rsp[12] == 0u && rsp[13] == 0u;
}

static void spi_record_startup_residue(void) {
    if (!g_spi_startup_residue.valid &&
        spi_trace_is_startup_reset_residue(&g_spi_trace)) {
        g_spi_startup_residue = g_spi_trace;
    }
}

/*
 * Read the eight-byte header and its declared payload/CRC without releasing CS.
 * The canonical response is written directly into g_spi_trace.response_bytes;
 * the shared transport scratch buffer is no longer used for response decode.
 */
static trinity_error_code_t spi_capture_response_once(endpoint_t *ep,
                                                       size_t *response_len) {
    trinity_error_code_t rc;
    uint16_t payload_length;
    size_t frame_len = 0u;
    size_t captured = 0u;
    uint8_t *response;

    if (ep == NULL || response_len == NULL || !g_spi_trace.valid)
        return TRINITY_BAD_STATE;
    *response_len = 0u;
    response = g_spi_trace.response_bytes;
    memset(response, 0, sizeof(g_spi_trace.response_bytes));

    g_spi_trace.irq_before_response = irq_active(ep);
    rc = spi_select(ep);
    if (rc == TRINITY_OK) {
        rc = spi_bytes_segment(NULL, NULL,
                               TRINITY_SPI_HEADER_SIZE,
                               0u, TRINITY_SPI_HEADER_SIZE, true);
    }

    if (rc == TRINITY_OK) {
        /* Startup drain has no request metadata, so recover it from the frame. */
        if (g_spi_trace.request_length == 0u) {
            g_spi_trace.command = response[2];
            g_spi_trace.target_txid = trinity_read_be16(&response[4]);
        }
        if (response[0] != TRINITY_SPI_MAGIC) {
            rc = TRINITY_BAD_MAGIC;
        } else if (response[1] != TRINITY_PROTOCOL_VERSION) {
            rc = TRINITY_BAD_VERSION;
        } else {
            payload_length = trinity_read_be16(&response[6]);
            if (payload_length > TRINITY_SPI_MAX_PAYLOAD) {
                rc = TRINITY_BAD_LENGTH;
            } else {
                frame_len = TRINITY_SPI_HEADER_SIZE + payload_length +
                            TRINITY_SPI_CRC_SIZE;
                g_spi_trace.response_frame_length = (uint16_t)frame_len;
                rc = spi_bytes_segment(
                    NULL, NULL,
                    frame_len - TRINITY_SPI_HEADER_SIZE,
                    TRINITY_SPI_HEADER_SIZE, frame_len, false);
                if (rc == TRINITY_OK) *response_len = frame_len;
            }
        }
    }

    spi_end();
    wait_ms(SPI_RESPONSE_SETTLE_MS);
    g_spi_trace.irq_after_response = irq_active(ep);

    captured = g_spi_trace.transfer_completed;
    if (captured > TRINITY_SPI_MAX_PACKET)
        captured = TRINITY_SPI_MAX_PACKET;
    g_spi_trace.response_capture_length = (uint16_t)captured;
    return rc;
}

static bool spi_response_read_retryable(const endpoint_t *ep,
                                        trinity_error_code_t rc) {
    if (ep == NULL || !irq_active(ep)) return false;
    return rc == TRINITY_BAD_MAGIC ||
           rc == TRINITY_BAD_VERSION ||
           rc == TRINITY_BAD_LENGTH ||
           rc == TRINITY_FRAME_TIMEOUT;
}

/*
 * A short or corrupted first read does not consume the Primer mailbox. Retry
 * the same pending response under a fresh CS instead of issuing another request
 * because CS rising resets the FPGA transmit index while IRQ remains active.
 */
static trinity_error_code_t spi_capture_response(endpoint_t *ep,
                                                  size_t *response_len) {
    trinity_error_code_t rc = TRINITY_INTERNAL_FAULT;
    unsigned attempt;
    for (attempt = 0u; attempt < 2u; ++attempt) {
        rc = spi_capture_response_once(ep, response_len);
        if (rc == TRINITY_OK) return TRINITY_OK;
        if (!spi_response_read_retryable(ep, rc)) return rc;
        wait_ms(TRINITY_DEPLOY_SPI_INTER_EXCHANGE_MS);
    }
    return rc;
}

static trinity_error_code_t spi_drain_startup_mailbox(endpoint_t *ep) {
    trinity_error_code_t rc;
    trinity_error_code_t decode_rc;
    size_t response_len;
    unsigned attempt;
    const uint8_t *response;
    if (ep == NULL) return TRINITY_BAD_STATE;
    if (!irq_active(ep)) return TRINITY_OK;

    for (attempt = 0u; attempt < 3u; ++attempt) {
        spi_trace_begin(ep, 0u, 0u, 0u);
        rc = spi_capture_response(ep, &response_len);
        if (rc != TRINITY_OK) {
            g_spi_trace.result_code = rc;
            spi_latch_first_failure();
            return rc;
        }

        response = g_spi_trace.response_bytes;
        g_spi_trace.response_crc_received =
            trinity_read_be16(&response[response_len - 2u]);
        g_spi_trace.response_crc_calculated =
            trinity_crc16_ccitt_false(response, response_len - 2u);
        decode_rc = trinity_spi_decode(response, response_len, &g_spi_rsp);
        if (decode_rc != TRINITY_OK) {
            g_spi_trace.result_code = decode_rc;
            spi_latch_first_failure();
        } else if ((g_spi_rsp.flags & TRINITY_FLAG_ERROR) != 0u) {
            g_spi_trace.result_code =
                g_spi_rsp.payload_length >= 2u
                    ? (trinity_error_code_t)trinity_read_be16(
                          g_spi_rsp.payload)
                    : TRINITY_BAD_LENGTH;
            if (spi_trace_is_startup_reset_residue(&g_spi_trace))
                spi_record_startup_residue();
            else
                spi_latch_first_failure();
        }

        if (!irq_active(ep)) return TRINITY_OK;
    }
    g_spi_trace.result_code = TRINITY_RESULT_PENDING;
    spi_latch_first_failure();
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

    wait_ms(SPI_RESPONSE_SETTLE_MS);
    while (!expired(wait_start, TRINITY_DEPLOY_SPI_TIMEOUT_MS)) {
        if (!irq_active(ep)) {
            progress();
            continue;
        }

        rc = spi_capture_response(ep, &response_len);
        if (rc != TRINITY_OK) goto failed;
