    g_trinity_deploy_last_error = (uint32_t)code;
}

static bool expired(uint32_t start, uint32_t timeout) {
    return (uint32_t)(g_ms - start) >= timeout;
}

static void pc_receive(void);
static void pc_poll(void);

/*
 * progress() is called from deep SPI and ML-KEM call chains. It may service
 * heartbeat state and drain UART bytes into the one-frame receive queue, but it
 * must never decode or execute a PC command. Command execution is restricted to
 * pc_poll() calls made directly by main(), eliminating progress <-> pc_poll
 * recursion and keeping the stack depth statically bounded.
 */
static void progress(void) {
    g_progress_ms = g_ms;
    if (g_pc_service_enabled && !g_pc_poll_active)
        pc_receive();
}

static void crypto_progress_lease_begin(void) {
    g_crypto_lease_deadline_ms =
        g_ms + TRINITY_DEPLOY_CRYPTO_PROGRESS_LEASE_MS;
    g_crypto_lease_active = true;
    progress();
}

static trinity_error_code_t crypto_progress_lease_end(
    trinity_error_code_t operation_result) {
    const bool lease_failed =
        g_fault && g_error.code == TRINITY_HEARTBEAT_TIMEOUT;
    g_crypto_lease_active = false;
    if (lease_failed) {
        trinity_deploy_crypto_zeroize(&g_crypto);
        trinity_controller_secure_clear(&g_controller.session,
                                        sizeof(g_controller.session));
        trinity_controller_forget_last_result(&g_controller);
        g_controller.session_material_valid = false;
        g_controller.commit_issued = false;
        g_controller.current_sequence = 0u;
        g_controller.state = TRINITY_SYSTEM_FAULT_LOCKED;
        g_controller.last_error = TRINITY_HEARTBEAT_TIMEOUT;
        g_controller.last_error_source = TRINITY_SOURCE_SN32;
        g_controller.last_error_detail =
            TRINITY_DEPLOY_CRYPTO_PROGRESS_LEASE_MS;
    }
    progress();
    return lease_failed ? TRINITY_HEARTBEAT_TIMEOUT : operation_result;
}

static void wait_ms(uint32_t duration) {
    const uint32_t start = g_ms;
    while (!expired(start, duration)) progress();
}

void SysTick_Handler(void) {
    const uint32_t now = ++g_ms;
    bool lease_alive = false;
    bool foreground_alive;

    if (g_crypto_lease_active) {
        lease_alive = (int32_t)(g_crypto_lease_deadline_ms - now) > 0;
        if (!lease_alive) {
            g_crypto_lease_active = false;
            g_fault = true;
            g_trinity_deploy_marker = DEPLOY_MARKER_ERR;
            set_error(TRINITY_HEARTBEAT_TIMEOUT, TRINITY_SOURCE_SN32,
                      TRINITY_DEPLOY_CRYPTO_PROGRESS_LEASE_MS);
            cs_all_high();
        }
    }

    if ((uint32_t)(now - g_heartbeat_ms) >= HEARTBEAT_MS) {
        g_heartbeat_ms = now;
        foreground_alive =
            (uint32_t)(now - g_progress_ms) <= PROGRESS_LEASE_MS ||
            lease_alive;
        g_heartbeat_level = !g_fault && foreground_alive
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
            g_crypto_lease_active = false;
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
