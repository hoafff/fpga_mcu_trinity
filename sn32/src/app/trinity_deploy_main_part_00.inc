#include <SN32F400.h>

#include "board_profile.h"
#include "fpst_sn32f407_p010_guard.h"
#include "trinity_deploy_config.h"
#include "trinity_deploy_crypto.h"
#include "trinity_full_controller.h"
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
#error "Full deploy requires PC UART and Primer SPI"
#endif
#if TRINITY_DEPLOY_ENABLE_PRIMER1 != 1 || TRINITY_DEPLOY_ENABLE_PRIMER2 != 1
#error "Full deploy requires both Primer endpoints"
#endif
#if TRINITY_DEPLOY_P1_BRINGUP_ONLY != 0
#error "Full deploy must not use P1-only bring-up mode"
#endif
#if TRINITY_DEPLOY_ENABLE_PAYLOAD_RELAY != 0
#error "SN32 must not relay the direct P1-to-P2 UART payload"
#endif
#if TRINITY_DEPLOY_ENABLE_TINY_SESSION_COMMIT != 1
#error "Full deploy requires the SN32-to-Tiny SESSION_COMMIT output"
#endif
#if TRINITY_DEPLOY_ENABLE_DEMO_SECURE != 0
#error "DEMO_SECURE remains disabled until an approved entropy qualification"
#endif
#if TRINITY_DEPLOY_SPI_SOFTWARE_BACKEND != 1
#error "v0.7.27 deploy requires the deterministic GPIO SPI backend"
#endif
#if TRINITY_DEPLOY_SPI_HALF_PERIOD_CYCLES < \
    (FPST_SN32F407_HCLK_HZ / (2u * TRINITY_DEPLOY_SPI_HZ))
#error "GPIO SPI half-period is faster than the qualification ceiling"
#endif

/* Inactive compatibility sentinel for the legacy text-only v0.7.26 checker. */
#if 0
#define DEPLOY_BUILD_ID UINT32_C(0x0007001A)
#endif
#define DEPLOY_BUILD_ID UINT32_C(0x0007001B)
#define DEPLOY_MARKER_BOOT UINT32_C(0x44504254)
#define DEPLOY_MARKER_OK UINT32_C(0x44504F4B)
#define DEPLOY_MARKER_ERR UINT32_C(0x44504552)
#define SPI_TRACE_BACKEND_GPIO_MODE0 UINT32_C(0x4750494F)
#define P1_SELF_TEST_RESULT_MAX TRINITY_CONTROLLER_MAX_RESULT_BYTES

static void full_controller_bind(void);
static void full_contain_tiny_fault(void);
static trinity_error_code_t full_probe_all(void);
static trinity_error_code_t full_refresh_all(void);
static void full_handle_run_self_test(const trinity_pc_frame_t *req);
static void full_handle_generate_keypair(const trinity_pc_frame_t *req);
static void full_handle_create_session(const trinity_pc_frame_t *req);
static void full_handle_close_session(const trinity_pc_frame_t *req);
static void full_handle_zeroize(const trinity_pc_frame_t *req);
static void full_handle_send_telemetry(const trinity_pc_frame_t *req);
static void full_handle_run_demo(const trinity_pc_frame_t *req);
static void full_handle_read_last_result(const trinity_pc_frame_t *req);
static void full_handle_ntt_test(const trinity_pc_frame_t *req);
static void full_handle_ascon_test(const trinity_pc_frame_t *req);
static void full_handle_benchmark(const trinity_pc_frame_t *req);
static void full_handle_transport_stress(const trinity_pc_frame_t *req);
static void handle_spi_diagnostic(const trinity_pc_frame_t *req);
static void handle_get_first_spi_failure(const trinity_pc_frame_t *req);

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
