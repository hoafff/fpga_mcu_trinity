    if (reg == NULL || pin >= 16u) return;
    *reg = (*reg & ~(UINT32_C(3) << shift)) |
           (((uint32_t)cfg & UINT32_C(3)) << shift);
}

static void gpio_write(unsigned port, unsigned pin, bool high) {
    const uint32_t mask = UINT32_C(1) << pin;
    switch (port) {
        case 0u: if (high) SN_GPIO0->BSET = mask; else SN_GPIO0->BCLR = mask; break;
        case 1u: if (high) SN_GPIO1->BSET = mask; else SN_GPIO1->BCLR = mask; break;
        case 2u: if (high) SN_GPIO2->BSET = mask; else SN_GPIO2->BCLR = mask; break;
        case 3u: if (high) SN_GPIO3->BSET = mask; else SN_GPIO3->BCLR = mask; break;
        default: break;
    }
}

static bool gpio_read(unsigned port, unsigned pin) {
    uint32_t data;
    switch (port) {
        case 0u: data = SN_GPIO0->DATA; break;
        case 1u: data = SN_GPIO1->DATA; break;
        case 2u: data = SN_GPIO2->DATA; break;
        case 3u: data = SN_GPIO3->DATA; break;
        default: return false;
    }
    return ((data >> pin) & 1u) != 0u;
}

static fpst_sn32f407_p010_regs_t guard_regs(void) {
    const fpst_sn32f407_p010_regs_t regs = {
        &SN_GPIO0->MODE, &SN_GPIO0->CFG, &SN_PFPA->UART0,
        &SN_PFPA->I2C0, &SN_PFPA->CT16B1,
        &SN_SYS1->AHBCLKEN, &SN_SYS1->PRST
    };
    return regs;
}

static uint32_t guard_check(void) {
    const fpst_sn32f407_p010_regs_t regs = guard_regs();
    fpst_sn32f407_p010_readback_t snapshot;
    return fpst_sn32f407_p010_guard_readback(&regs, &snapshot);
}

static void guard_apply(void) {
    const fpst_sn32f407_p010_regs_t regs = guard_regs();
    fpst_sn32f407_p010_guard_apply(&regs);
}

static void cs_all_high(void) {
    gpio_write(FPST_SN32F407_FLASH_CS_N_PORT, FPST_SN32F407_FLASH_CS_N_PIN, true);
    gpio_write(FPST_SN32F407_P1_CS_N_PORT, FPST_SN32F407_P1_CS_N_PIN, true);
    gpio_write(FPST_SN32F407_P2_CS_N_PORT, FPST_SN32F407_P2_CS_N_PIN, true);
    g_spi_selected = false;
}

static bool safety_error_latched(trinity_error_code_t code) {
    return code == TRINITY_AUTH_THRESHOLD ||
           code == TRINITY_COMMIT_REJECTED ||
           code == TRINITY_SESSION_COMMIT_FAILED ||
           code == TRINITY_HEARTBEAT_TIMEOUT ||
           code == TRINITY_FAULT_LOCKED ||
           code == TRINITY_INTERNAL_FAULT;
}

static void set_error(trinity_error_code_t code, trinity_source_t source,
                      uint32_t detail) {
    if (safety_error_latched(g_error.code) && !safety_error_latched(code))
        return;
    g_error.code = code;
    g_error.source = source;
    g_error.detail = detail;
