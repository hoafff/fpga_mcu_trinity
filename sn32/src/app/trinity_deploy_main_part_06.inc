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

static void soft_spi_half_delay(void) {
    volatile uint32_t cycles = TRINITY_DEPLOY_SPI_HALF_PERIOD_CYCLES;
    while (cycles != 0u) {
        __NOP();
        --cycles;
    }
}

static trinity_error_code_t spi_reset_idle(void) {
    if (!g_spi_ready || g_spi_selected) return TRINITY_BAD_STATE;
    gpio_write(FPST_SN32F407_SPI_SCK_PORT,
               FPST_SN32F407_SPI_SCK_PIN, false);
    gpio_write(FPST_SN32F407_SPI_MOSI_PORT,
               FPST_SN32F407_SPI_MOSI_PIN, false);
    return TRINITY_OK;
}

/* Explicit mode-0, MSB-first transfer on the existing DB_SPI GPIO pins. */
static trinity_error_code_t soft_spi_transfer_byte(uint8_t tx, uint8_t *rx) {
    uint8_t value = 0u;
    unsigned bit;

    if (!g_spi_ready || !g_spi_selected || rx == NULL)
        return TRINITY_BAD_STATE;

    for (bit = 0u; bit < 8u; ++bit) {
        if (g_fault || !g_spi_selected) {
            gpio_write(FPST_SN32F407_SPI_SCK_PORT,
                       FPST_SN32F407_SPI_SCK_PIN, false);
            return g_fault ? TRINITY_FAULT_LOCKED : TRINITY_BAD_STATE;
        }

        gpio_write(FPST_SN32F407_SPI_MOSI_PORT,
                   FPST_SN32F407_SPI_MOSI_PIN,
                   (tx & (uint8_t)(0x80u >> bit)) != 0u);
        soft_spi_half_delay();

        gpio_write(FPST_SN32F407_SPI_SCK_PORT,
                   FPST_SN32F407_SPI_SCK_PIN, true);
        soft_spi_half_delay();
        value = (uint8_t)((value << 1) |
                (gpio_read(FPST_SN32F407_SPI_MISO_PORT,
                           FPST_SN32F407_SPI_MISO_PIN) ? 1u : 0u));

        gpio_write(FPST_SN32F407_SPI_SCK_PORT,
                   FPST_SN32F407_SPI_SCK_PIN, false);
        soft_spi_half_delay();
    }

    *rx = value;
    return TRINITY_OK;
}

/* Request TX never aliases the response destination. */
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
        g_spi_trace.spi_status = 0u;
    }

    for (i = 0u; i < len; ++i) {
        uint8_t ignored;
        trinity_error_code_t rc = soft_spi_transfer_byte(tx[i], &ignored);
        if (rc != TRINITY_OK) {
            if (g_spi_trace.valid) {
                g_spi_trace.transfer_byte_index = (uint16_t)i;
                g_spi_trace.transfer_length = (uint16_t)len;
            }
            return rc;
        }
        if (g_spi_trace.valid) {
            g_spi_trace.transfer_completed = (uint16_t)(i + 1u);
            g_spi_trace.spi_status = 0u;
        }
    }
    return TRINITY_OK;
}

/* Response bytes go first to the canonical wire buffer; trace is diagnostic. */
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
            g_spi_trace.spi_ctrl0 = SPI_TRACE_BACKEND_GPIO_MODE0;
            g_spi_trace.spi_ctrl1 = TRINITY_DEPLOY_SPI_HZ;
            g_spi_trace.spi_clkdiv =
                TRINITY_DEPLOY_SPI_HALF_PERIOD_CYCLES;
            g_spi_trace.spi_fifo_th = 0u;
            g_spi_trace.response_sample_count = 0u;
        } else if (g_spi_trace.transfer_direction !=
                   SPI_TRANSFER_DIRECTION_RESPONSE) {
            return TRINITY_BAD_STATE;
        }
        g_spi_trace.transfer_length = (uint16_t)transfer_length;
        g_spi_trace.spi_status = 0u;
    }

    for (i = 0u; i < len; ++i) {
        const size_t trace_index = byte_offset + i;
        const uint32_t status_before_read = 0u;
        uint32_t data_word;
        const uint32_t status_after_read = 0u;
        uint8_t value;
        trinity_error_code_t rc;

        rc = soft_spi_transfer_byte(0u, &value);
        if (rc != TRINITY_OK) {
            if (g_spi_trace.valid) {
                g_spi_trace.transfer_byte_index = (uint16_t)trace_index;
                g_spi_trace.transfer_length = (uint16_t)transfer_length;
            }
            return rc;
        }
        data_word = value;
        g_spi_response_wire[trace_index] = value;

        if (g_spi_trace.valid) {
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
    g_spi_selected = true;
    spi_guard_delay();
    if (g_fault || !g_spi_selected) {
        cs_all_high();
        return g_fault ? TRINITY_FAULT_LOCKED : TRINITY_BAD_STATE;
    }
    return TRINITY_OK;
}

static void spi_end(void) {
    gpio_write(FPST_SN32F407_SPI_SCK_PORT,
               FPST_SN32F407_SPI_SCK_PIN, false);
    gpio_write(FPST_SN32F407_SPI_MOSI_PORT,
               FPST_SN32F407_SPI_MOSI_PIN, false);
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
