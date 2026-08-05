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

static bool startup_probe_error_is_retryable(trinity_error_code_t rc) {
    return spi_error_allows_read_retry(rc) ||
           rc == TRINITY_RESULT_PENDING ||
           rc == TRINITY_BUSY ||
           rc == TRINITY_RESULT_NOT_READY;
}

static void startup_recovery_wait(void) {
    const uint32_t started = g_ms;
    while (!expired(started,
                    TRINITY_DEPLOY_SPI_STARTUP_RECOVERY_BACKOFF_MS)) {
        progress();
        full_contain_tiny_fault();
        pc_poll();
        if (g_fault) return;
    }
}

static void startup_clear_recovered_transport_evidence(void) {
    if (!g_spi_retained_failure) return;

    /*
     * A transport error inside the bounded startup recovery window is not an
     * active first failure after a complete P1+P2 probe succeeds. Clear only
     * that recovered startup snapshot. A persistent/non-transport failure exits
     * without calling this function and therefore remains immutable evidence.
     */
    memset(&g_spi_retained_trace, 0, sizeof(g_spi_retained_trace));
    g_spi_retained_failure = false;
    g_spi_retained_startup_residue = false;
    set_error(TRINITY_OK, TRINITY_SOURCE_SN32, 0u);
}

static trinity_error_code_t startup_drain_and_probe_with_recovery(void) {
    const uint32_t recovery_started = g_ms;
    trinity_error_code_t rc = TRINITY_INTERNAL_FAULT;
    trinity_source_t source = TRINITY_SOURCE_PRIMER1;
    bool saw_retryable_failure = false;

    for (;;) {
        source = TRINITY_SOURCE_PRIMER1;
        g_spi_trace_context = SPI_TRACE_CONTEXT_STARTUP_DRAIN_P1;
        rc = spi_drain_startup_mailbox(&g_p1);
        if (rc == TRINITY_OK) {
            source = TRINITY_SOURCE_PRIMER2;
            g_spi_trace_context = SPI_TRACE_CONTEXT_STARTUP_DRAIN_P2;
            rc = spi_drain_startup_mailbox(&g_p2);
        }
        if (rc == TRINITY_OK) {
            g_spi_trace_context = SPI_TRACE_CONTEXT_STARTUP_PROBE;
            rc = full_probe_all();
        } else {
            set_error(rc, source, 0u);
        }

        if (rc == TRINITY_OK) {
            if (saw_retryable_failure)
                startup_clear_recovered_transport_evidence();
            return TRINITY_OK;
        }

        if (!startup_probe_error_is_retryable(rc) || g_fault ||
            expired(recovery_started,
                    TRINITY_DEPLOY_SPI_STARTUP_RECOVERY_MS))
            return rc;

        saw_retryable_failure = true;
        startup_recovery_wait();
        if (g_fault)
            return g_error.code != TRINITY_OK
                       ? g_error.code : TRINITY_FAULT_LOCKED;
    }
}

int main(void) {
    uint32_t last_probe;
    uint32_t startup_wait_start;
    trinity_error_code_t startup_rc;
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

    startup_rc = startup_drain_and_probe_with_recovery();
    if (startup_rc != TRINITY_OK && g_error.code == TRINITY_OK)
        set_error(startup_rc, TRINITY_SOURCE_SN32, 0u);

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
