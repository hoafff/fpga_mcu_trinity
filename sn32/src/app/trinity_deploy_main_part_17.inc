    SystemCoreClockUpdate();
    if (SystemCoreClock != FPST_SN32F407_HCLK_HZ ||
        SysTick_Config(SystemCoreClock / 1000u) != 0u) {
        set_error(TRINITY_INTERNAL_FAULT, TRINITY_SOURCE_SN32, SystemCoreClock);
        g_fault = true;
        g_trinity_deploy_marker = DEPLOY_MARKER_ERR;
        return TRINITY_INTERNAL_FAULT;
    }
    gpio_init();
    SN_PFPA->SPI0 = FPST_SN32F407_PFPA_SPI0_VALUE;
    rc = uart_init();
    if (rc != TRINITY_OK) {
        set_error(rc, TRINITY_SOURCE_SN32, UINT32_C(0x55415254));
        g_fault = true;
        g_trinity_deploy_marker = DEPLOY_MARKER_ERR;
        return rc;
    }

    /* PC liveness begins immediately after UART init, before any SPI wait. */
    g_pc_service_enabled = true;
    progress();

    spi_init();
    trinity_deploy_crypto_init(&g_crypto);
    full_controller_bind();
    progress();
    g_trinity_deploy_marker = DEPLOY_MARKER_OK;
    return TRINITY_OK;
}

int main(void) {
    uint32_t last_probe;
    trinity_error_code_t startup_rc;
    trinity_source_t startup_source = TRINITY_SOURCE_PRIMER1;
    SystemInit();
    SystemCoreClockUpdate();
    if (hardware_init() != TRINITY_OK) {
        for (;;) __NOP();
    }

    /*
     * Endpoint warm-up and discovery may take several seconds when a stale
     * mailbox or transport timeout is present. progress() services PC UART
     * throughout this phase, so PING/SYSTEM_INFO never depend on SPI success.
     */
    wait_ms(SPI_STARTUP_WARMUP_MS);
    wait_ms(TRINITY_DEPLOY_SPI_STARTUP_SETTLE_MS);
    g_spi_trace_context = SPI_TRACE_CONTEXT_STARTUP_DRAIN_P1;
    startup_rc = spi_drain_startup_mailbox(&g_p1);
    if (startup_rc == TRINITY_OK) {
        startup_source = TRINITY_SOURCE_PRIMER2;
        g_spi_trace_context = SPI_TRACE_CONTEXT_STARTUP_DRAIN_P2;
        startup_rc = spi_drain_startup_mailbox(&g_p2);
    }
    if (startup_rc == TRINITY_OK) {
        g_spi_trace_context = SPI_TRACE_CONTEXT_STARTUP_PROBE;
        (void)full_probe_all();
    } else {
        set_error(startup_rc, startup_source, 0u);
    }
    g_spi_trace_context = SPI_TRACE_CONTEXT_NONE;
    g_automatic_probe_active = false;
    progress();
    last_probe = g_ms;

    for (;;) {
        progress();
        full_contain_tiny_fault();
        pc_poll();
        if (!g_fault && !g_spi_first_failure.valid && !g_host_txn.valid &&
            (uint32_t)(g_ms - last_probe) >= TRINITY_DEPLOY_ENDPOINT_PROBE_MS) {
            g_automatic_probe_active = true;
            g_spi_trace_context = SPI_TRACE_CONTEXT_PERIODIC_PROBE;
            if (g_controller.p1.ready && g_controller.p2.ready)
                (void)full_refresh_all();
            else
                (void)full_probe_all();
            g_spi_trace_context = SPI_TRACE_CONTEXT_NONE;
            g_automatic_probe_active = false;
            progress();
            last_probe = g_ms;
        }
    }
}
