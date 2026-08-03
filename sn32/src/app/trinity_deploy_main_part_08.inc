        if (g_spi_buf[0] != TRINITY_SPI_MAGIC ||
            g_spi_buf[1] != TRINITY_PROTOCOL_VERSION) {
            spi_end();
            wait_ms(SPI_RESPONSE_SETTLE_MS);
            continue;
        }
        response_payload_length = trinity_read_be16(&g_spi_buf[6]);
        if (response_payload_length > TRINITY_SPI_MAX_PAYLOAD) {
            rc = TRINITY_BAD_LENGTH;
            spi_end();
            goto failed;
        }
        response_len = TRINITY_SPI_HEADER_SIZE + response_payload_length +
                       TRINITY_SPI_CRC_SIZE;
        rc = spi_bytes(NULL, &g_spi_buf[TRINITY_SPI_HEADER_SIZE],
                       response_len - TRINITY_SPI_HEADER_SIZE);
        spi_end();
        if (rc == TRINITY_OK)
            rc = trinity_spi_decode(g_spi_buf, response_len, &g_spi_rsp);
        if (rc != TRINITY_OK) goto failed;
        if (g_spi_rsp.command != command ||
            g_spi_rsp.transaction_id != txid ||
            (g_spi_rsp.flags & TRINITY_FLAG_RESPONSE) == 0u ||
            (g_spi_rsp.flags & (TRINITY_FLAG_MORE | TRINITY_FLAG_EVENT)) != 0u) {
            rc = TRINITY_TRANSACTION_CONFLICT;
            goto failed;
        }
        if (issued_txid != NULL) *issued_txid = txid;
        if ((g_spi_rsp.flags & TRINITY_FLAG_ERROR) != 0u) {
            rc = g_spi_rsp.payload_length >= 2u
                     ? (trinity_error_code_t)trinity_read_be16(g_spi_rsp.payload)
                     : TRINITY_BAD_LENGTH;
            goto failed;
        }
        return TRINITY_OK;
    }
    rc = TRINITY_FRAME_TIMEOUT;

failed:
    set_error(rc, endpoint_source(ep), ((uint32_t)command << 16) | txid);
    return rc;
}
