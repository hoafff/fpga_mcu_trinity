    SystemCoreClockUpdate();
    if (SystemCoreClock != FPST_SN32F407_HCLK_HZ ||
        SysTick_Config(SystemCoreClock / 1000u) != 0u) {
        set_error(TRINITY_INTERNAL_FAULT, TRINITY_SOURCE_SN32, SystemCoreClock);
        g_fault = true;
        g_trinity_deploy_marker = DEPLOY_MARKER_ERR;
        return TRINITY_INTERNAL_FAULT;
    }
    gpio_init();
    rc = uart_init();
    if (rc != TRINITY_OK) {
        set_error(rc, TRINITY_SOURCE_SN32, UINT32_C(0x55415254));
        g_fault = true;
        g_trinity_deploy_marker = DEPLOY_MARKER_ERR;
        return rc;
    }

    /* PC ingress begins immediately after UART init, before any SPI wait. */
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
    uint32_t startup_wait_start;
    trinity_error_code_t startup_rc;
    trinity_source_t startup_source = TRINITY_SOURCE_PRIMER1;
    SystemInit();
    SystemCoreClockUpdate();
    if (hardware_init() != TRINITY_OK) {
        for (;;) __NOP();
    }

    /*
     * Keep PING/SYSTEM_INFO live during the two-second warm-up without allowing
     * progress() to execute commands from inside a nested SPI/crypto stack.
     * All command execution in this loop occurs directly under main().
     */
    startup_wait_start = g_ms;
    while (!expired(startup_wait_start, SPI_STARTUP_WARMUP_MS)) {
        progress();
        full_contain_tiny_fault();
        pc_poll();
    }
    startup_wait_start = g_ms;
    while (!expired(startup_wait_start,
                    TRINITY_DEPLOY_SPI_STARTUP_SETTLE_MS)) {
        progress();
        full_contain_tiny_fault();
        pc_poll();
    }

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
    pc_poll();
    last_probe = g_ms;

    for (;;) {
        progress();
        full_contain_tiny_fault();
        pc_poll();
        /*
         * Preserve the first active SPI failure as immutable evidence. Once a
         * failure is retained, background traffic must stop; only explicit
         * host diagnostics may touch the bus.
         */
        if (!g_fault && !g_spi_retained_failure && !g_host_txn.valid &&
            pc_quiet_for_automatic_probe() &&
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
            pc_poll();
            last_probe = g_ms;
        }
    }
}
