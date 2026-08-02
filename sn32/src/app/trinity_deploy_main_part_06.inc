    *out = (uint8_t)SN_UART0->RB;
    return true;
}

static trinity_error_code_t spi_bytes(const uint8_t *tx, uint8_t *rx,
                                      size_t len) {
    const uint32_t start = g_ms;
    size_t i;
    if (!g_spi_ready || !g_spi_selected) return TRINITY_BAD_STATE;
    for (i = 0u; i < len; ++i) {
        while ((SN_SPI0->STAT & SPI_TX_FULL) != 0u) {
            progress();
            if (expired(start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return TRINITY_FRAME_TIMEOUT;
        }
        SN_SPI0->DATA = tx != NULL ? tx[i] : 0u;
        while ((SN_SPI0->STAT & SPI_BUSY) != 0u) {
            progress();
            if (expired(start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return TRINITY_FRAME_TIMEOUT;
        }
        while ((SN_SPI0->STAT & SPI_RX_EMPTY) != 0u) {
            progress();
            if (expired(start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return TRINITY_FRAME_TIMEOUT;
        }
        if (rx != NULL) rx[i] = (uint8_t)SN_SPI0->DATA;
        else (void)SN_SPI0->DATA;
    }
    return TRINITY_OK;
}

static trinity_error_code_t spi_select(const endpoint_t *ep) {
    if (ep == NULL || !g_spi_ready || g_spi_selected || g_fault)
        return TRINITY_BAD_STATE;
    cs_all_high();
    SN_SPI0->CTRL0_b.FRESET = 3u;
    gpio_write(ep->cs_port, ep->cs_pin, false);
    g_spi_selected = true;
    return TRINITY_OK;
}

static void spi_end(void) {
    const uint32_t start = g_ms;
    while (g_spi_selected && (SN_SPI0->STAT & SPI_BUSY) != 0u &&
           !expired(start, TRINITY_DEPLOY_SPI_TIMEOUT_MS)) {
        progress();
    }
    cs_all_high();
    SN_SPI0->CTRL0_b.FRESET = 3u;
}

static bool irq_active(const endpoint_t *ep) {
    const bool level = gpio_read(ep->irq_port, ep->irq_pin);
    return FPST_SN32F407_IRQ_ACTIVE_LOW ? !level : level;
}

static uint16_t next_spi_txid(void) {
    const uint16_t id = g_spi_txid;
    if (++g_spi_txid == 0u) g_spi_txid = 1u;
