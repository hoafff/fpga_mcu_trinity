    g_trinity_deploy_last_error = (uint32_t)code;
}

static bool expired(uint32_t start, uint32_t timeout) {
    return (uint32_t)(g_ms - start) >= timeout;
}

static void progress(void) { g_progress_ms = g_ms; }

static void wait_ms(uint32_t duration) {
    const uint32_t start = g_ms;
    while (!expired(start, duration)) progress();
}

void SysTick_Handler(void) {
    const uint32_t now = ++g_ms;
    if ((uint32_t)(now - g_heartbeat_ms) >= HEARTBEAT_MS) {
        g_heartbeat_ms = now;
        g_heartbeat_level = !g_fault &&
                            (uint32_t)(now - g_progress_ms) <= PROGRESS_LEASE_MS
                                ? !g_heartbeat_level : false;
        gpio_write(FPST_SN32F407_MCU_HEARTBEAT_PORT,
                   FPST_SN32F407_MCU_HEARTBEAT_PIN,
                   g_heartbeat_level);
    }
    if ((now % GUARD_MS) == 0u) {
        const uint32_t faults = guard_check();
        if (faults != FPST_P010_VIOLATION_NONE) {
            g_guard_faults |= faults;
            g_fault = true;
            g_trinity_deploy_marker = DEPLOY_MARKER_ERR;
            set_error(TRINITY_FAULT_LOCKED, TRINITY_SOURCE_SN32, faults);
            cs_all_high();
            guard_apply();
        }
    }
}

static void gpio_init(void) {
    cs_all_high();
    gpio_set_mode(FPST_SN32F407_FLASH_CS_N_PORT, FPST_SN32F407_FLASH_CS_N_PIN, true);
    gpio_set_cfg(FPST_SN32F407_FLASH_CS_N_PORT, FPST_SN32F407_FLASH_CS_N_PIN,
                 GPIO_NO_PULL_SCHMITT);
    gpio_set_mode(FPST_SN32F407_P1_CS_N_PORT, FPST_SN32F407_P1_CS_N_PIN, true);
    gpio_set_cfg(FPST_SN32F407_P1_CS_N_PORT, FPST_SN32F407_P1_CS_N_PIN,
                 GPIO_NO_PULL_SCHMITT);
    gpio_set_mode(FPST_SN32F407_P2_CS_N_PORT, FPST_SN32F407_P2_CS_N_PIN, true);
    gpio_set_cfg(FPST_SN32F407_P2_CS_N_PORT, FPST_SN32F407_P2_CS_N_PIN,
                 GPIO_NO_PULL_SCHMITT);
    gpio_set_mode(FPST_SN32F407_P1_IRQ_N_PORT, FPST_SN32F407_P1_IRQ_N_PIN, false);
    gpio_set_cfg(FPST_SN32F407_P1_IRQ_N_PORT, FPST_SN32F407_P1_IRQ_N_PIN,
                 GPIO_PULL_UP);
    gpio_set_mode(FPST_SN32F407_P2_IRQ_N_PORT, FPST_SN32F407_P2_IRQ_N_PIN, false);
    gpio_set_cfg(FPST_SN32F407_P2_IRQ_N_PORT, FPST_SN32F407_P2_IRQ_N_PIN,
                 GPIO_PULL_UP);
    gpio_write(FPST_SN32F407_MCU_HEARTBEAT_PORT,
               FPST_SN32F407_MCU_HEARTBEAT_PIN, false);
    gpio_set_mode(FPST_SN32F407_MCU_HEARTBEAT_PORT,
                  FPST_SN32F407_MCU_HEARTBEAT_PIN, true);
    gpio_set_cfg(FPST_SN32F407_MCU_HEARTBEAT_PORT,
