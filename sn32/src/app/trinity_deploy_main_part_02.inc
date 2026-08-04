    TRINITY_TARGET_PRIMER1,
    FPST_SN32F407_P1_CS_N_PORT, FPST_SN32F407_P1_CS_N_PIN,
    FPST_SN32F407_P1_IRQ_N_PORT, FPST_SN32F407_P1_IRQ_N_PIN,
    false, 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u
};
#if TRINITY_DEPLOY_P1_BRINGUP_ONLY == 0
static endpoint_t g_p2 = {
    TRINITY_TARGET_PRIMER2,
    FPST_SN32F407_P2_CS_N_PORT, FPST_SN32F407_P2_CS_N_PIN,
    FPST_SN32F407_P2_IRQ_N_PORT, FPST_SN32F407_P2_IRQ_N_PIN,
    false, 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u
};
#endif

/*
 * Keep PC framing, SPI request bytes and SPI response bytes in disjoint RAM.
 * Hardware v0.7.11/v0.7.12 proved the peripheral DATA words were correct while
 * a shared/aliased software destination was corrupted. These buffers therefore
 * have one owner each and are never overlaid through a union.
 */
static uint8_t g_pc_wire[TRINITY_PC_MAX_WIRE_FRAME];
static uint8_t g_pc_raw[TRINITY_PC_MAX_RAW_FRAME];
static uint8_t g_spi_request_wire[TRINITY_SPI_MAX_PACKET];
static uint8_t g_spi_response_wire[TRINITY_SPI_MAX_PACKET];

static size_t g_pc_wire_len;
static uint32_t g_pc_frame_start;
static trinity_pc_frame_t g_pc_req;
static trinity_pc_frame_t g_pc_rsp;

/* Request construction and response decode must not alias each other. */
static trinity_spi_packet_t g_spi_req;
static trinity_spi_packet_t g_spi_rsp;

extern void SystemInit(void);
extern void SystemCoreClockUpdate(void);
extern uint32_t SystemCoreClock;

static volatile uint32_t *gpio_mode(unsigned port) {
    switch (port) {
        case 0u: return &SN_GPIO0->MODE;
        case 1u: return &SN_GPIO1->MODE;
        case 2u: return &SN_GPIO2->MODE;
        case 3u: return &SN_GPIO3->MODE;
        default: return NULL;
    }
}

static volatile uint32_t *gpio_cfg(unsigned port) {
    switch (port) {
        case 0u: return &SN_GPIO0->CFG;
        case 1u: return &SN_GPIO1->CFG;
        case 2u: return &SN_GPIO2->CFG;
        case 3u: return &SN_GPIO3->CFG;
        default: return NULL;
    }
}

static void gpio_set_mode(unsigned port, unsigned pin, bool output) {
    volatile uint32_t *reg = gpio_mode(port);
    if (reg == NULL || pin >= 16u) return;
    if (output) *reg |= UINT32_C(1) << pin;
    else *reg &= ~(UINT32_C(1) << pin);
}

static void gpio_set_cfg(unsigned port, unsigned pin, unsigned cfg) {
    volatile uint32_t *reg = gpio_cfg(port);
    const unsigned shift = pin * 2u;