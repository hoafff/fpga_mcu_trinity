    *out = (uint8_t)SN_UART0->RB;
    return true;
}

static void spi_guard_delay(void) {
    volatile uint32_t cycles =
        (FPST_SN32F407_HCLK_HZ / UINT32_C(1000000)) *
        TRINITY_DEPLOY_SPI_CS_GUARD_US;
    while (cycles != 0u) {
        __NOP();
        --cycles;
    }
}

static trinity_error_code_t spi_transfer_timeout(uint8_t stage,
                                                  size_t byte_index,
                                                  size_t transfer_length) {
    if (g_spi_trace.valid) {
        g_spi_trace.transfer_stage = stage;
        g_spi_trace.transfer_byte_index = (uint16_t)byte_index;
        g_spi_trace.transfer_length = (uint16_t)transfer_length;
        g_spi_trace.spi_status = SN_SPI0->STAT;
    }
    return TRINITY_FRAME_TIMEOUT;
}

static trinity_error_code_t spi_reset_idle(void) {
    uint32_t start;
    unsigned drained = 0u;

    if (!g_spi_ready || g_spi_selected) return TRINITY_BAD_STATE;

    start = g_ms;
    while ((SN_SPI0->STAT & SPI_BUSY) != 0u) {
        progress();
        if (expired(start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
            return spi_transfer_timeout(SPI_TRANSFER_STAGE_BUSY, 0u, 0u);
    }

    SN_SPI0->CTRL0_b.FRESET = 3u;
    start = g_ms;
    while (SN_SPI0->CTRL0_b.FRESET != 0u) {
        progress();
        if (expired(start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
            return spi_transfer_timeout(SPI_TRANSFER_STAGE_BUSY, 0u, 0u);
    }

    while ((SN_SPI0->STAT & SPI_RX_EMPTY) == 0u && drained < 8u) {
        (void)(SN_SPI0->DATA & UINT32_C(0xFFFF));
        ++drained;
    }
    return ((SN_SPI0->STAT & (SPI_BUSY | SPI_RX_EMPTY)) == SPI_RX_EMPTY)
               ? TRINITY_OK : TRINITY_BAD_STATE;
}

/*
 * Request TX has a dedicated implementation. It never aliases the response
 * destination and it drains one RX word for every transmitted frame.
 */
static trinity_error_code_t spi_write_request_bytes(const uint8_t *tx,
                                                      size_t len) {
    size_t i;
    if (!g_spi_ready || !g_spi_selected || tx == NULL)
        return TRINITY_BAD_STATE;

    if (g_spi_trace.valid) {
        g_spi_trace.transfer_stage = SPI_TRANSFER_STAGE_NONE;
        g_spi_trace.transfer_direction = SPI_TRANSFER_DIRECTION_REQUEST;
        g_spi_trace.transfer_byte_index = 0u;
        g_spi_trace.transfer_length = (uint16_t)len;
        g_spi_trace.transfer_completed = 0u;
        g_spi_trace.spi_status = SN_SPI0->STAT;
    }

    for (i = 0u; i < len; ++i) {
        uint32_t stage_start = g_ms;
        while ((SN_SPI0->STAT & SPI_TX_FULL) != 0u) {
            progress();
            if (expired(stage_start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return spi_transfer_timeout(SPI_TRANSFER_STAGE_TX_FULL,
                                            i, len);
        }

        SN_SPI0->DATA = tx[i];

        stage_start = g_ms;
        while ((SN_SPI0->STAT & SPI_BUSY) != 0u) {
            progress();
            if (expired(stage_start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return spi_transfer_timeout(SPI_TRANSFER_STAGE_BUSY, i, len);
        }

        stage_start = g_ms;
        while ((SN_SPI0->STAT & SPI_RX_EMPTY) != 0u) {
            progress();
            if (expired(stage_start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return spi_transfer_timeout(SPI_TRANSFER_STAGE_RX_EMPTY,
                                            i, len);
        }

        (void)SN_SPI0->DATA;
        if (g_spi_trace.valid) {
            g_spi_trace.transfer_completed = (uint16_t)(i + 1u);
            g_spi_trace.spi_status = SN_SPI0->STAT;
        }
    }
    return TRINITY_OK;
}

/*
 * Response RX also has a dedicated implementation. DATA[7:0] is written first
 * to a standalone canonical wire buffer; the trace copy is diagnostic only.
 */
static trinity_error_code_t spi_read_response_segment(
    size_t len,
    size_t byte_offset,
    size_t transfer_length,
    bool begin_trace) {
    size_t i;
    if (!g_spi_ready || !g_spi_selected)
        return TRINITY_BAD_STATE;
    if (byte_offset > transfer_length || len > transfer_length - byte_offset ||
        transfer_length > TRINITY_SPI_MAX_PACKET)
        return TRINITY_BAD_LENGTH;

    if (g_spi_trace.valid) {
        if (begin_trace) {
            g_spi_trace.transfer_stage = SPI_TRANSFER_STAGE_NONE;
            g_spi_trace.transfer_direction = SPI_TRANSFER_DIRECTION_RESPONSE;
            g_spi_trace.transfer_byte_index = 0u;
            g_spi_trace.transfer_completed = 0u;
            g_spi_trace.spi_ctrl0 = SN_SPI0->CTRL0;
            g_spi_trace.spi_ctrl1 = SN_SPI0->CTRL1;
            g_spi_trace.spi_clkdiv = SN_SPI0->CLKDIV;
            g_spi_trace.spi_fifo_th = SN_SPI0->FIFO_TH;
            g_spi_trace.response_sample_count = 0u;
        } else if (g_spi_trace.transfer_direction !=
                   SPI_TRANSFER_DIRECTION_RESPONSE) {
            return TRINITY_BAD_STATE;
        }
        g_spi_trace.transfer_length = (uint16_t)transfer_length;
        g_spi_trace.spi_status = SN_SPI0->STAT;
    }

    for (i = 0u; i < len; ++i) {
        const size_t trace_index = byte_offset + i;
        uint32_t stage_start = g_ms;
        uint32_t status_before_read;
        uint32_t data_word;
        uint32_t status_after_read;
        uint8_t value;

        while ((SN_SPI0->STAT & SPI_TX_FULL) != 0u) {
            progress();
            if (expired(stage_start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return spi_transfer_timeout(SPI_TRANSFER_STAGE_TX_FULL,
                                            trace_index, transfer_length);
        }

        SN_SPI0->DATA = 0u;

        stage_start = g_ms;
        while ((SN_SPI0->STAT & SPI_BUSY) != 0u) {
            progress();
            if (expired(stage_start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return spi_transfer_timeout(SPI_TRANSFER_STAGE_BUSY,
                                            trace_index, transfer_length);
        }

        stage_start = g_ms;
        while ((SN_SPI0->STAT & SPI_RX_EMPTY) != 0u) {
            progress();
            if (expired(stage_start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return spi_transfer_timeout(SPI_TRANSFER_STAGE_RX_EMPTY,
                                            trace_index, transfer_length);
        }

        status_before_read = SN_SPI0->STAT;
        data_word = SN_SPI0->DATA;
        status_after_read = SN_SPI0->STAT;
        value = (uint8_t)(data_word & UINT32_C(0xFF));
        g_spi_response_wire[trace_index] = value;

        if (g_spi_trace.valid) {
            g_spi_trace.response_bytes[trace_index] = value;
            if (trace_index < SPI_RESPONSE_SAMPLE_MAX) {
                g_spi_trace.response_status_before_read[trace_index] =
                    status_before_read;
                g_spi_trace.response_data_words[trace_index] = data_word;
                g_spi_trace.response_status_after_read[trace_index] =
                    status_after_read;
                g_spi_trace.response_sample_count =
                    (uint8_t)(trace_index + 1u);
            }
            g_spi_trace.transfer_completed = (uint16_t)(trace_index + 1u);
            g_spi_trace.spi_status = status_after_read;
        }
    }
    return TRINITY_OK;
}

static trinity_error_code_t spi_select(const endpoint_t *ep) {
    trinity_error_code_t rc;
    if (ep == NULL || !g_spi_ready || g_spi_selected || g_fault)
        return TRINITY_BAD_STATE;
    cs_all_high();
    spi_guard_delay();
    rc = spi_reset_idle();
    if (rc != TRINITY_OK) return rc;
    spi_guard_delay();
    gpio_write(ep->cs_port, ep->cs_pin, false);
    spi_guard_delay();
    g_spi_selected = true;
    return TRINITY_OK;
}

static void spi_end(void) {
    const uint32_t start = g_ms;
    while (g_spi_selected && (SN_SPI0->STAT & SPI_BUSY) != 0u &&
           !expired(start, TRINITY_DEPLOY_SPI_TIMEOUT_MS)) {
        progress();
    }
    if (g_spi_selected) spi_guard_delay();
    cs_all_high();
    spi_guard_delay();
}

static bool irq_active(const endpoint_t *ep) {
    const bool level = gpio_read(ep->irq_port, ep->irq_pin);
    return FPST_SN32F407_IRQ_ACTIVE_LOW ? !level : level;
}

static uint16_t next_spi_txid(void) {
    const uint16_t id = g_spi_txid;
    if (++g_spi_txid == 0u) g_spi_txid = 1u;