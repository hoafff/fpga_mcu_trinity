                 FPST_SN32F407_MCU_HEARTBEAT_PIN, GPIO_NO_PULL_SCHMITT);
}

static trinity_error_code_t uart_init(void) {
    if (guard_check() != FPST_P010_VIOLATION_NONE) return TRINITY_FAULT_LOCKED;
    SN_SYS1->AHBCLKEN |= UART0_CLK_EN;
    SN_PFPA->UART0 = FPST_SN32F407_PFPA_UART0_VALUE;
    SN_UART0->LC = UART_LCR_DLAB_8N1;
    SN_UART0->FD = UART_FD_115200_12M;
    SN_UART0->DLM = 0u;
    SN_UART0->DLL = 4u;
    SN_UART0->LC = UART_LCR_8N1;
    SN_UART0->FIFOCTRL = UART_FIFO_RESET;
    SN_UART0->IE = 0u;
    NVIC_DisableIRQ(UART0_IRQn);
    SN_UART0->CTRL = UART_CTRL_RX_TX;
    if (guard_check() != FPST_P010_VIOLATION_NONE) return TRINITY_FAULT_LOCKED;
    g_uart_ready = true;
    return TRINITY_OK;
}

static void spi_init(void) {
    /* Release P1.0/P1.1/P1.2 from SPI0 before assigning them as GPIO. */
    SN_SYS1->AHBCLKEN_b.SPI0CLKEN = 1u;
    SN_SPI0->CTRL0_b.SPIEN = 0u;
    SN_SPI0->IE = 0u;
    NVIC_DisableIRQ(SPI0_IRQn);
    SN_PFPA->SPI0 = 0u;

    gpio_write(FPST_SN32F407_SPI_SCK_PORT,
               FPST_SN32F407_SPI_SCK_PIN, false);
    gpio_write(FPST_SN32F407_SPI_MOSI_PORT,
               FPST_SN32F407_SPI_MOSI_PIN, false);
    gpio_set_mode(FPST_SN32F407_SPI_SCK_PORT,
                  FPST_SN32F407_SPI_SCK_PIN, true);
    gpio_set_mode(FPST_SN32F407_SPI_MOSI_PORT,
                  FPST_SN32F407_SPI_MOSI_PIN, true);
    gpio_set_mode(FPST_SN32F407_SPI_MISO_PORT,
                  FPST_SN32F407_SPI_MISO_PIN, false);
    gpio_set_cfg(FPST_SN32F407_SPI_SCK_PORT,
                 FPST_SN32F407_SPI_SCK_PIN, GPIO_NO_PULL_SCHMITT);
    gpio_set_cfg(FPST_SN32F407_SPI_MOSI_PORT,
                 FPST_SN32F407_SPI_MOSI_PIN, GPIO_NO_PULL_SCHMITT);
    gpio_set_cfg(FPST_SN32F407_SPI_MISO_PORT,
                 FPST_SN32F407_SPI_MISO_PIN, GPIO_NO_PULL_SCHMITT);
    g_spi_ready = true;
}

static trinity_error_code_t uart_write(const uint8_t *data, size_t len) {
    const uint32_t start = g_ms;
    size_t i;
    if (!g_uart_ready || (data == NULL && len != 0u)) return TRINITY_BAD_STATE;
    for (i = 0u; i < len; ++i) {
        while ((SN_UART0->LS & UART_LS_THRE) == 0u) {
            progress();
            if (expired(start, UART_TIMEOUT_MS)) return TRINITY_FRAME_TIMEOUT;
        }
        SN_UART0->TH = data[i];
    }
    while ((SN_UART0->LS & UART_LS_TEMT) == 0u) {
        progress();
        if (expired(start, UART_TIMEOUT_MS)) return TRINITY_FRAME_TIMEOUT;
    }
    return TRINITY_OK;
}

static bool uart_read(uint8_t *out) {
    if (!g_uart_ready || out == NULL || (SN_UART0->LS & UART_LS_RDR) == 0u)
        return false;
