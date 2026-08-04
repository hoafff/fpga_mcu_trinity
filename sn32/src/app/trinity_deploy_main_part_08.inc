        /*
         * P1 diagnostic images encode the number of request bytes actually
         * captured in BAD_LENGTH detail. This covers both the legacy empty-CS
         * response and the hardware-proven four/nine-byte truncated requests,
         * whose echoed command and txid cannot be correlated. Reissue only
         * within the same bounded policy and only for idempotent, zero-payload
         * discovery/status reads.
         */
        if (spi_decoded_proves_truncated_request(request_len)) {
            g_spi_trace.result_code = TRINITY_BAD_LENGTH;
            if (spi_trace_is_startup_reset_residue(&g_spi_trace))
                spi_record_startup_residue();
            rc = TRINITY_BAD_LENGTH;
            goto retry_read_request;
        }

        if (g_spi_rsp.command != command ||
            g_spi_rsp.transaction_id != txid ||
            (g_spi_rsp.flags & TRINITY_FLAG_RESPONSE) == 0u ||
            (g_spi_rsp.flags & (TRINITY_FLAG_MORE | TRINITY_FLAG_EVENT)) != 0u) {
            rc = TRINITY_TRANSACTION_CONFLICT;
            goto retry_read_request;
        }
        if ((g_spi_rsp.flags & TRINITY_FLAG_ERROR) != 0u) {
            rc = g_spi_rsp.payload_length >= 2u
                     ? (trinity_error_code_t)trinity_read_be16(g_spi_rsp.payload)
                     : TRINITY_BAD_LENGTH;
            goto retry_read_request;
        }
        g_spi_trace.result_code = TRINITY_OK;
        wait_ms(TRINITY_DEPLOY_SPI_INTER_EXCHANGE_MS);
        return TRINITY_OK;
    }
    rc = TRINITY_FRAME_TIMEOUT;

retry_read_request:
    g_spi_trace.result_code = rc;
    /* Side-effect operations bypass this branch and fall through to failure. */
    if (spi_command_allows_read_retry(command, payload_length) &&
        spi_error_allows_read_retry(rc) &&
        read_reissues < TRINITY_DEPLOY_SPI_READ_REISSUE_MAX) {
        ++read_reissues;
        wait_ms(TRINITY_DEPLOY_SPI_READ_RETRY_BACKOFF_MS);
        goto retry_request;
    }

failed:
    g_spi_trace.result_code = rc;
    spi_latch_first_failure();
    set_error(rc, endpoint_source(ep), ((uint32_t)command << 16) | txid);
    return rc;
}
