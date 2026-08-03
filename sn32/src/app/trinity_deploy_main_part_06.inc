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

static trinity_error_code_t spi_bytes_segment(
    const uint8_t *tx,
    uint8_t *rx,
    size_t len,
    size_t byte_offset,
    size_t transfer_length,
    bool begin_trace) {
    size_t i;
    const uint8_t direction =
        tx != NULL ? SPI_TRANSFER_DIRECTION_REQUEST
                   : SPI_TRANSFER_DIRECTION_RESPONSE;

    if (!g_spi_ready || !g_spi_selected) return TRINITY_BAD_STATE;
    if (byte_offset > transfer_length || len > transfer_length - byte_offset)
        return TRINITY_BAD_LENGTH;

    if (g_spi_trace.valid) {
        if (begin_trace) {
            g_spi_trace.transfer_stage = SPI_TRANSFER_STAGE_NONE;
            g_spi_trace.transfer_direction = direction;
            g_spi_trace.transfer_byte_index = 0u;
            g_spi_trace.transfer_completed = 0u;
        } else if (g_spi_trace.transfer_direction != direction) {
            return TRINITY_BAD_STATE;
        }
        g_spi_trace.transfer_length = (uint16_t)transfer_length;
        g_spi_trace.spi_status = SN_SPI0->STAT;
    }

    for (i = 0u; i < len; ++i) {
        const size_t trace_index = byte_offset + i;
        uint32_t stage_start = g_ms;
        uint8_t value;

        while ((SN_SPI0->STAT & SPI_TX_FULL) != 0u) {
            progress();
            if (expired(stage_start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return spi_transfer_timeout(SPI_TRANSFER_STAGE_TX_FULL,
                                            trace_index, transfer_length);
        }

        SN_SPI0->DATA = tx != NULL ? tx[i] : 0u;

        /*
         * Drain the received byte as soon as RX_EMPTY clears. Waiting for BUSY
         * first can deadlock controllers whose receive FIFO back-pressures the
         * transfer-complete state. RX availability already proves that this
         * byte was clocked; BUSY is checked afterwards before the next byte.
         */
        stage_start = g_ms;
        while ((SN_SPI0->STAT & SPI_RX_EMPTY) != 0u) {
            progress();
            if (expired(stage_start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return spi_transfer_timeout(SPI_TRANSFER_STAGE_RX_EMPTY,
                                            trace_index, transfer_length);
        }

        value = (uint8_t)SN_SPI0->DATA;
        if (rx != NULL) rx[i] = value;
        if (g_spi_trace.valid) {
            g_spi_trace.transfer_completed = (uint16_t)(trace_index + 1u);
            g_spi_trace.spi_status = SN_SPI0->STAT;
        }

        stage_start = g_ms;
        while ((SN_SPI0->STAT & SPI_BUSY) != 0u) {
            progress();
            if (expired(stage_start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return spi_transfer_timeout(SPI_TRANSFER_STAGE_BUSY,
                                            trace_index, transfer_length);
        }
    }
    return TRINITY_OK;
}

static trinity_error_code_t spi_bytes(const uint8_t *tx, uint8_t *rx,
                                      size_t len) {
    return spi_bytes_segment(tx, rx, len, 0u, len, true);
}

static trinity_error_code_t spi_select(const endpoint_t *ep) {
    if (ep == NULL || !g_spi_ready || g_spi_selected || g_fault)
        return TRINITY_BAD_STATE;
    cs_all_high();
    spi_guard_delay();
    SN_SPI0->CTRL0_b.FRESET = 3u;
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
    SN_SPI0->CTRL0_b.FRESET = 3u;
    spi_guard_delay();
}

static bool irq_active(const endpoint_t *ep) {
    const bool level = gpio_read(ep->irq_port, ep->irq_pin);
    return FPST_SN32F407_IRQ_ACTIVE_LOW ? !level : level;
}

static uint16_t next_spi_txid(void) {
    const uint16_t id = g_spi_txid;
    if (++g_spi_txid == 0u) g_spi_txid = 1u;
