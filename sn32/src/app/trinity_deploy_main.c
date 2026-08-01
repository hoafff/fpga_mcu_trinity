#include <SN32F400.h>

#include "board_profile.h"
#include "fpst_sn32f407_p010_guard.h"
#include "trinity_deploy_config.h"
#include "trinity_pc_protocol.h"
#include "trinity_spi_protocol.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#if !defined(TRINITY_DEPLOY_TARGET) || TRINITY_DEPLOY_TARGET != 1
#error "Deploy source requires TRINITY_DEPLOY_TARGET=1"
#endif
#if TRINITY_DEPLOY_ENABLE_PC_UART != 1 || TRINITY_DEPLOY_ENABLE_SPI != 1
#error "Minimum deploy requires PC UART and Primer SPI"
#endif
#if TRINITY_DEPLOY_ENABLE_PRIMER1 != 1 || TRINITY_DEPLOY_ENABLE_PRIMER2 != 1
#error "Minimum deploy requires both Primer control endpoints"
#endif
#if TRINITY_DEPLOY_ENABLE_MLKEM != 0 || TRINITY_DEPLOY_ENABLE_PAYLOAD_RELAY != 0
#error "ML-KEM and MCU payload relay must remain disabled"
#endif
#if TRINITY_DEPLOY_ENABLE_TINY_SESSION_COMMIT != 0 || \
    TRINITY_DEPLOY_ENABLE_DEMO_SECURE != 0
#error "Tiny session commit and DEMO_SECURE must remain disabled"
#endif

#define DEPLOY_BUILD_ID UINT32_C(0x00050000)
#define DEPLOY_MARKER_BOOT UINT32_C(0x44504254) /* DPBT */
#define DEPLOY_MARKER_OK UINT32_C(0x44504F4B)   /* DPOK */
#define DEPLOY_MARKER_ERR UINT32_C(0x44504552)  /* DPER */

enum {
    UART0_CLK_EN = 1u << 16,
    UART_LCR_DLAB_8N1 = 0x83u,
    UART_LCR_8N1 = 0x03u,
    UART_FD_115200_12M = (7u << 4) | 5u,
    UART_FIFO_RESET = 0x07u,
    UART_CTRL_RX_TX = 0xC1u,
    UART_LS_RDR = 0x01u,
    UART_LS_THRE = 0x20u,
    UART_LS_TEMT = 0x40u,
    SPI_TX_FULL = 1u << 1,
    SPI_RX_EMPTY = 1u << 2,
    SPI_BUSY = 1u << 4,
    GPIO_PULL_UP = 0u,
    GPIO_NO_PULL_SCHMITT = 2u,
    HEARTBEAT_MS = 100u,
    PROGRESS_LEASE_MS = 250u,
    GUARD_MS = 10u,
    UART_TIMEOUT_MS = 100u,
    PC_FRAME_TIMEOUT_MS = 250u
};

typedef struct {
    uint8_t id;
    unsigned cs_port;
    unsigned cs_pin;
    unsigned irq_port;
    unsigned irq_pin;
    bool ready;
    uint32_t capabilities;
    uint32_t build_id;
    uint16_t last_error;
} endpoint_t;

typedef struct {
    trinity_error_code_t code;
    trinity_source_t source;
    uint32_t detail;
} error_record_t;

volatile uint32_t g_trinity_deploy_marker;
volatile uint32_t g_trinity_deploy_last_error;

static volatile uint32_t g_ms;
static volatile uint32_t g_progress_ms;
static volatile uint32_t g_heartbeat_ms;
static volatile uint32_t g_guard_faults;
static volatile bool g_fault;
static volatile bool g_spi_selected;
static bool g_uart_ready;
static bool g_spi_ready;
static bool g_heartbeat_level;
static uint16_t g_spi_txid = 1u;
static uint16_t g_active_host_txid;
static error_record_t g_error;

static endpoint_t g_p1 = {
    TRINITY_TARGET_PRIMER1,
    FPST_SN32F407_P1_CS_N_PORT, FPST_SN32F407_P1_CS_N_PIN,
    FPST_SN32F407_P1_IRQ_N_PORT, FPST_SN32F407_P1_IRQ_N_PIN,
    false, 0u, 0u, 0u
};
static endpoint_t g_p2 = {
    TRINITY_TARGET_PRIMER2,
    FPST_SN32F407_P2_CS_N_PORT, FPST_SN32F407_P2_CS_N_PIN,
    FPST_SN32F407_P2_IRQ_N_PORT, FPST_SN32F407_P2_IRQ_N_PIN,
    false, 0u, 0u, 0u
};

static uint8_t g_pc_wire[TRINITY_PC_MAX_WIRE_FRAME];
static uint8_t g_pc_raw[TRINITY_PC_MAX_RAW_FRAME];
static uint8_t g_pc_tx[TRINITY_PC_MAX_WIRE_FRAME];
static size_t g_pc_wire_len;
static uint32_t g_pc_frame_start;
static trinity_pc_frame_t g_pc_req;
static trinity_pc_frame_t g_pc_rsp;

static uint8_t g_spi_buf[TRINITY_SPI_MAX_PACKET];
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

static void set_error(trinity_error_code_t code, trinity_source_t source,
                      uint32_t detail) {
    g_error.code = code;
    g_error.source = source;
    g_error.detail = detail;
    g_trinity_deploy_last_error = (uint32_t)code;
}

static bool expired(uint32_t start, uint32_t timeout) {
    return (uint32_t)(g_ms - start) >= timeout;
}

static void progress(void) { g_progress_ms = g_ms; }

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
                 FPST_SN32F407_MCU_HEARTBEAT_PIN, GPIO_NO_PULL_SCHMITT);
}

static trinity_error_code_t uart_init(void) {
    if (guard_check() != FPST_P010_VIOLATION_NONE) return TRINITY_FAULT_LOCKED;
    SN_SYS1->AHBCLKEN |= UART0_CLK_EN;
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
    SN_SYS1->AHBCLKEN_b.SPI0CLKEN = 1u;
    SN_SPI0->CTRL0_b.SPIEN = 0u;
    SN_SPI0->CTRL0_b.DL = 7u;
    SN_SPI0->CTRL0_b.MS = 0u;
    SN_SPI0->CTRL0_b.LOOPBACK = 0u;
    SN_SPI0->CTRL0_b.SDODIS = 0u;
    SN_SPI0->FIFO_TH = 0u;
    SN_SPI0->CLKDIV_b.DIV = 5u; /* 12 MHz / 12 = 1 MHz. */
    SN_SPI0->CTRL1 = 0u;        /* Mode 0, MSB first. */
    SN_SPI0->CTRL0_b.SELDIS = 1u;
    SN_SPI0->CTRL0_b.FRESET = 3u;
    SN_SPI0->IE = 0u;
    NVIC_DisableIRQ(SPI0_IRQn);
    SN_SPI0->CTRL0_b.SPIEN = 1u;
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
    *out = (uint8_t)SN_UART0->RB;
    return true;
}

static trinity_error_code_t spi_bytes(const uint8_t *tx, uint8_t *rx,
                                      size_t len) {
    const uint32_t start = g_ms;
    size_t i;
    if (!g_spi_ready || !g_spi_selected) return TRINITY_BAD_STATE;
    for (i = 0u; i < len; ++i) {
        while ((SN_SPI0->STAT & SPI_TX_FULL) != 0u) {
            progress();
            if (expired(start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return TRINITY_FRAME_TIMEOUT;
        }
        SN_SPI0->DATA = tx != NULL ? tx[i] : 0u;
        while ((SN_SPI0->STAT & SPI_BUSY) != 0u) {
            progress();
            if (expired(start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return TRINITY_FRAME_TIMEOUT;
        }
        while ((SN_SPI0->STAT & SPI_RX_EMPTY) != 0u) {
            progress();
            if (expired(start, TRINITY_DEPLOY_SPI_TIMEOUT_MS))
                return TRINITY_FRAME_TIMEOUT;
        }
        if (rx != NULL) rx[i] = (uint8_t)SN_SPI0->DATA;
        else (void)SN_SPI0->DATA;
    }
    return TRINITY_OK;
}

static trinity_error_code_t spi_select(const endpoint_t *ep) {
    if (ep == NULL || !g_spi_ready || g_spi_selected || g_fault)
        return TRINITY_BAD_STATE;
    cs_all_high();
    SN_SPI0->CTRL0_b.FRESET = 3u;
    gpio_write(ep->cs_port, ep->cs_pin, false);
    g_spi_selected = true;
    return TRINITY_OK;
}

static void spi_end(void) {
    const uint32_t start = g_ms;
    while (g_spi_selected && (SN_SPI0->STAT & SPI_BUSY) != 0u &&
           !expired(start, TRINITY_DEPLOY_SPI_TIMEOUT_MS)) {
        progress();
    }
    cs_all_high();
    SN_SPI0->CTRL0_b.FRESET = 3u;
}

static bool irq_active(const endpoint_t *ep) {
    const bool level = gpio_read(ep->irq_port, ep->irq_pin);
    return FPST_SN32F407_IRQ_ACTIVE_LOW ? !level : level;
}

static uint16_t next_spi_txid(void) {
    const uint16_t id = g_spi_txid;
    if (++g_spi_txid == 0u) g_spi_txid = 1u;
    return id;
}

static trinity_source_t endpoint_source(const endpoint_t *ep) {
    return ep->id == TRINITY_TARGET_PRIMER1
               ? TRINITY_SOURCE_PRIMER1 : TRINITY_SOURCE_PRIMER2;
}

static trinity_error_code_t endpoint_query(endpoint_t *ep, uint8_t command) {
    trinity_error_code_t rc;
    size_t request_len = 0u;
    size_t response_len;
    uint16_t payload_len;
    const uint16_t txid = next_spi_txid();
    const uint32_t wait_start = g_ms;

    memset(&g_spi_req, 0, sizeof(g_spi_req));
    g_spi_req.version = TRINITY_PROTOCOL_VERSION;
    g_spi_req.command = command;
    g_spi_req.transaction_id = txid;
    rc = trinity_spi_encode(&g_spi_req, g_spi_buf, sizeof(g_spi_buf), &request_len);
    if (rc != TRINITY_OK) return rc;

    rc = spi_select(ep);
    if (rc == TRINITY_OK) rc = spi_bytes(g_spi_buf, NULL, request_len);
    spi_end();
    if (rc != TRINITY_OK) goto failed;

    while (!irq_active(ep)) {
        progress();
        if (expired(wait_start, TRINITY_DEPLOY_SPI_TIMEOUT_MS)) {
            rc = TRINITY_FRAME_TIMEOUT;
            goto failed;
        }
    }

    rc = spi_select(ep);
    if (rc == TRINITY_OK)
        rc = spi_bytes(NULL, g_spi_buf, TRINITY_SPI_HEADER_SIZE);
    if (rc != TRINITY_OK) {
        spi_end();
        goto failed;
    }
    if (g_spi_buf[0] != TRINITY_SPI_MAGIC ||
        g_spi_buf[1] != TRINITY_PROTOCOL_VERSION) {
        rc = g_spi_buf[0] != TRINITY_SPI_MAGIC
                 ? TRINITY_BAD_MAGIC : TRINITY_BAD_VERSION;
        spi_end();
        goto failed;
    }
    payload_len = trinity_read_be16(&g_spi_buf[6]);
    if (payload_len > TRINITY_SPI_MAX_PAYLOAD) {
        rc = TRINITY_BAD_LENGTH;
        spi_end();
        goto failed;
    }
    response_len = TRINITY_SPI_HEADER_SIZE + payload_len + TRINITY_SPI_CRC_SIZE;
    rc = spi_bytes(NULL, &g_spi_buf[TRINITY_SPI_HEADER_SIZE],
                   response_len - TRINITY_SPI_HEADER_SIZE);
    spi_end();
    if (rc == TRINITY_OK)
        rc = trinity_spi_decode(g_spi_buf, response_len, &g_spi_rsp);
    if (rc != TRINITY_OK) goto failed;
    if (g_spi_rsp.command != command || g_spi_rsp.transaction_id != txid ||
        (g_spi_rsp.flags & TRINITY_FLAG_RESPONSE) == 0u ||
        (g_spi_rsp.flags & (TRINITY_FLAG_MORE | TRINITY_FLAG_EVENT)) != 0u) {
        rc = TRINITY_TRANSACTION_CONFLICT;
        goto failed;
    }
    if ((g_spi_rsp.flags & TRINITY_FLAG_ERROR) != 0u) {
        rc = g_spi_rsp.payload_length >= 2u
                 ? (trinity_error_code_t)trinity_read_be16(g_spi_rsp.payload)
                 : TRINITY_BAD_LENGTH;
        goto failed;
    }
    return TRINITY_OK;

failed:
    set_error(rc, endpoint_source(ep), ((uint32_t)command << 16) | txid);
    return rc;
}

static void probe(endpoint_t *ep) {
    trinity_error_code_t rc;
    ep->ready = false;
    ep->capabilities = 0u;
    ep->build_id = 0u;
    ep->last_error = 0u;

    rc = endpoint_query(ep, TRINITY_SPI_GET_INFO);
    if (rc != TRINITY_OK) { ep->last_error = (uint16_t)rc; return; }
    if (g_spi_rsp.payload_length != 12u || g_spi_rsp.payload[0] != ep->id ||
        g_spi_rsp.payload[1] != TRINITY_PROTOCOL_VERSION ||
        g_spi_rsp.payload[10] != 0u || g_spi_rsp.payload[11] != 0u) {
        ep->last_error = (uint16_t)TRINITY_BAD_STATE;
        set_error(TRINITY_BAD_STATE, endpoint_source(ep), g_spi_rsp.payload_length);
        return;
    }
    ep->capabilities = trinity_read_be32(&g_spi_rsp.payload[2]);
    ep->build_id = trinity_read_be32(&g_spi_rsp.payload[6]);

    rc = endpoint_query(ep, TRINITY_SPI_GET_STATUS);
    if (rc != TRINITY_OK) { ep->last_error = (uint16_t)rc; return; }
    if (g_spi_rsp.payload_length != 16u) {
        ep->last_error = (uint16_t)TRINITY_BAD_LENGTH;
        set_error(TRINITY_BAD_LENGTH, endpoint_source(ep), g_spi_rsp.payload_length);
        return;
    }
    ep->last_error = trinity_read_be16(&g_spi_rsp.payload[8]);
    ep->ready = true;
}

static uint8_t ready_mask(void) {
    uint8_t mask = TRINITY_READY_SN32;
    if (g_p1.ready) mask |= TRINITY_READY_PRIMER1;
    if (g_p2.ready) mask |= TRINITY_READY_PRIMER2;
    return mask;
}

static uint8_t fault_mask(void) {
    uint8_t mask = g_fault ? TRINITY_FAULT_SN32 : 0u;
    if (!g_p1.ready) mask |= TRINITY_FAULT_PRIMER1;
    if (!g_p2.ready) mask |= TRINITY_FAULT_PRIMER2;
    if (g_error.code == TRINITY_FRAME_TIMEOUT ||
        g_error.code == TRINITY_BAD_MAGIC || g_error.code == TRINITY_BAD_CRC ||
        g_error.code == TRINITY_TRANSACTION_CONFLICT)
        mask |= TRINITY_FAULT_TRANSPORT;
    return mask;
}

static uint8_t system_state(void) {
    if (g_fault) return (uint8_t)TRINITY_SYSTEM_ERROR;
    if (!g_p1.ready || !g_p2.ready)
        return (uint8_t)TRINITY_SYSTEM_SELF_TEST_REQUIRED;
    return (uint8_t)TRINITY_SYSTEM_READY_NO_KEYPAIR;
}

static void response_begin(const trinity_pc_frame_t *req) {
    memset(&g_pc_rsp, 0, sizeof(g_pc_rsp));
    g_pc_rsp.version = TRINITY_PROTOCOL_VERSION;
    g_pc_rsp.command = req->command;
    g_pc_rsp.flags = TRINITY_FLAG_RESPONSE;
    g_pc_rsp.transaction_id = req->transaction_id;
}

static trinity_error_code_t response_send(void) {
    size_t raw_len = 0u;
    size_t wire_len = 0u;
    trinity_error_code_t rc = trinity_pc_encode_raw(
        &g_pc_rsp, g_pc_raw, sizeof(g_pc_raw), &raw_len);
    if (rc == TRINITY_OK)
        rc = trinity_cobs_encode(g_pc_raw, raw_len, g_pc_tx,
                                 sizeof(g_pc_tx) - 1u, &wire_len);
    if (rc == TRINITY_OK) {
        g_pc_tx[wire_len] = 0u;
        rc = uart_write(g_pc_tx, wire_len + 1u);
    }
    if (rc != TRINITY_OK) set_error(rc, TRINITY_SOURCE_SN32, 0u);
    return rc;
}

static void response_error(const trinity_pc_frame_t *req,
                           trinity_error_code_t code,
                           trinity_source_t source) {
    response_begin(req);
    g_pc_rsp.flags |= TRINITY_FLAG_ERROR;
    g_pc_rsp.payload_length = 6u;
    trinity_write_be16(&g_pc_rsp.payload[0], (uint16_t)code);
    g_pc_rsp.payload[2] = system_state();
    g_pc_rsp.payload[3] = (uint8_t)source;
    trinity_write_be16(&g_pc_rsp.payload[4], 0u);
    set_error(code, source, 0u);
    (void)response_send();
}

static void handle_request(const trinity_pc_frame_t *req) {
    response_begin(req);
    g_active_host_txid = req->transaction_id;
    if (req->flags != 0u) {
        response_error(req, TRINITY_BAD_FLAGS, TRINITY_SOURCE_HOST_PROTOCOL);
        g_active_host_txid = 0u;
        return;
    }
    if (req->payload_length != 0u) {
        response_error(req, TRINITY_BAD_LENGTH, TRINITY_SOURCE_HOST_PROTOCOL);
        g_active_host_txid = 0u;
        return;
    }

    switch (req->command) {
        case TRINITY_PC_PING:
            g_pc_rsp.payload_length = 4u;
            trinity_write_be32(g_pc_rsp.payload, g_ms);
            (void)response_send();
            break;
        case TRINITY_PC_GET_SYSTEM_INFO:
            g_pc_rsp.payload_length = 20u;
            g_pc_rsp.payload[0] = TRINITY_PROTOCOL_VERSION;
            g_pc_rsp.payload[1] = 0u;
            g_pc_rsp.payload[2] = 5u;
            trinity_write_be32(&g_pc_rsp.payload[4], 0u);
            trinity_write_be32(&g_pc_rsp.payload[8], DEPLOY_BUILD_ID);
            trinity_write_be32(&g_pc_rsp.payload[12], g_p1.ready ? g_p1.build_id : 0u);
            trinity_write_be32(&g_pc_rsp.payload[16], g_p2.ready ? g_p2.build_id : 0u);
            (void)response_send();
            break;
        case TRINITY_PC_GET_SYSTEM_STATUS:
            g_pc_rsp.payload_length = 20u;
            g_pc_rsp.payload[0] = system_state();
            g_pc_rsp.payload[1] = (uint8_t)TRINITY_MODE_KAT;
            g_pc_rsp.payload[2] = ready_mask();
            g_pc_rsp.payload[3] = fault_mask();
            trinity_write_be32(&g_pc_rsp.payload[4], 0u);
            trinity_write_be64(&g_pc_rsp.payload[8], 0u);
            trinity_write_be16(&g_pc_rsp.payload[16], (uint16_t)g_error.code);
            trinity_write_be16(&g_pc_rsp.payload[18], g_active_host_txid);
            (void)response_send();
            break;
        case TRINITY_PC_GET_LAST_ERROR:
            g_pc_rsp.payload_length = 8u;
            trinity_write_be16(&g_pc_rsp.payload[0], (uint16_t)g_error.code);
            g_pc_rsp.payload[2] = (uint8_t)g_error.source;
            trinity_write_be32(&g_pc_rsp.payload[4], g_error.detail);
            (void)response_send();
            break;
        default:
            response_error(req, TRINITY_NOT_SUPPORTED, TRINITY_SOURCE_SN32);
            break;
    }
    g_active_host_txid = 0u;
}

static void pc_reset(void) { g_pc_wire_len = 0u; g_pc_frame_start = 0u; }

static void pc_process(void) {
    size_t raw_len = 0u;
    trinity_error_code_t rc = trinity_cobs_decode(
        g_pc_wire, g_pc_wire_len, g_pc_raw, sizeof(g_pc_raw), &raw_len);
    if (rc == TRINITY_OK)
        rc = trinity_pc_decode_raw(g_pc_raw, raw_len, &g_pc_req);
    pc_reset();
    if (rc == TRINITY_OK) handle_request(&g_pc_req);
    else set_error(rc, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
}

static void pc_poll(void) {
    uint8_t byte;
    if (g_pc_wire_len != 0u && expired(g_pc_frame_start, PC_FRAME_TIMEOUT_MS)) {
        pc_reset();
        set_error(TRINITY_FRAME_TIMEOUT, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
    }
    while (uart_read(&byte)) {
        progress();
        if (byte == 0u) {
            if (g_pc_wire_len != 0u) pc_process();
        } else if (g_pc_wire_len < sizeof(g_pc_wire)) {
            if (g_pc_wire_len == 0u) g_pc_frame_start = g_ms;
            g_pc_wire[g_pc_wire_len++] = byte;
        } else {
            pc_reset();
            set_error(TRINITY_BAD_LENGTH, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        }
    }
}

static trinity_error_code_t hardware_init(void) {
    trinity_error_code_t rc;
    uint32_t faults;
    g_trinity_deploy_marker = DEPLOY_MARKER_BOOT;
    g_trinity_deploy_last_error = 0u;
    g_ms = g_progress_ms = g_heartbeat_ms = g_guard_faults = 0u;
    g_fault = g_spi_selected = false;
    g_uart_ready = g_spi_ready = g_heartbeat_level = false;
    memset(&g_error, 0, sizeof(g_error));
    pc_reset();

    guard_apply();
    faults = guard_check();
    if (faults != FPST_P010_VIOLATION_NONE) {
        set_error(TRINITY_FAULT_LOCKED, TRINITY_SOURCE_SN32, faults);
        g_fault = true;
        g_trinity_deploy_marker = DEPLOY_MARKER_ERR;
        return TRINITY_FAULT_LOCKED;
    }
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

    probe(&g_p1);
    progress();
    probe(&g_p2);
    last_probe = g_ms;

    for (;;) {
        progress();
        pc_poll();
        if ((uint32_t)(g_ms - last_probe) >= TRINITY_DEPLOY_ENDPOINT_PROBE_MS) {
            probe(&g_p1);
            progress();
            probe(&g_p2);
            last_probe = g_ms;
        }
    }
}
