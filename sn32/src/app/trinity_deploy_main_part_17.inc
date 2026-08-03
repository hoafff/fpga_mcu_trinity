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
    spi_init();
    trinity_deploy_crypto_init(&g_crypto);
    full_controller_bind();
    progress();
    g_trinity_deploy_marker = DEPLOY_MARKER_OK;
    return TRINITY_OK;
}

int main(void) {
    uint32_t last_probe;
    SystemInit();
    SystemCoreClockUpdate();
    if (hardware_init() != TRINITY_OK) {
        for (;;) __NOP();
    }

    (void)full_probe_all();
    progress();
    last_probe = g_ms;

    for (;;) {
        progress();
        pc_poll();
        if (!g_host_txn.valid &&
            (uint32_t)(g_ms - last_probe) >= TRINITY_DEPLOY_ENDPOINT_PROBE_MS) {
            if (g_controller.p1.ready && g_controller.p2.ready)
                (void)full_refresh_all();
            else
                (void)full_probe_all();
            progress();
            last_probe = g_ms;
        }
    }
}
