        if (g_spi_buf[0] != TRINITY_SPI_MAGIC) {
            rc = TRINITY_BAD_MAGIC;
            goto failed;
        }
        if (g_spi_buf[1] != TRINITY_PROTOCOL_VERSION) {
            rc = TRINITY_BAD_VERSION;
            goto failed;
        }
        response_payload_length = trinity_read_be16(&g_spi_buf[6]);
        if (response_payload_length > TRINITY_SPI_MAX_PAYLOAD) {
            rc = TRINITY_BAD_LENGTH;
            goto failed;
        }
        response_len = TRINITY_SPI_HEADER_SIZE + response_payload_length +
                       TRINITY_SPI_CRC_SIZE;
        g_spi_trace.response_frame_length = (uint16_t)response_len;
        g_spi_trace.response_crc_received =
            trinity_read_be16(&g_spi_buf[response_len - 2u]);
        g_spi_trace.response_crc_calculated =
            trinity_crc16_ccitt_false(g_spi_buf, response_len - 2u);

        rc = trinity_spi_decode(g_spi_buf, response_len, &g_spi_rsp);
        if (rc != TRINITY_OK) goto failed;
        if (g_spi_rsp.command != command ||
            g_spi_rsp.transaction_id != txid ||
            (g_spi_rsp.flags & TRINITY_FLAG_RESPONSE) == 0u ||
            (g_spi_rsp.flags & (TRINITY_FLAG_MORE | TRINITY_FLAG_EVENT)) != 0u) {
            rc = TRINITY_TRANSACTION_CONFLICT;
            goto failed;
        }
        if ((g_spi_rsp.flags & TRINITY_FLAG_ERROR) != 0u) {
            rc = g_spi_rsp.payload_length >= 2u
                     ? (trinity_error_code_t)trinity_read_be16(g_spi_rsp.payload)
                     : TRINITY_BAD_LENGTH;
            goto failed;
        }
        g_spi_trace.result_code = TRINITY_OK;
        wait_ms(TRINITY_DEPLOY_SPI_INTER_EXCHANGE_MS);
        return TRINITY_OK;
    }
    rc = TRINITY_FRAME_TIMEOUT;

failed:
    g_spi_trace.result_code = rc;
    spi_latch_first_failure();
    set_error(rc, endpoint_source(ep), ((uint32_t)command << 16) | txid);
    return rc;
}
