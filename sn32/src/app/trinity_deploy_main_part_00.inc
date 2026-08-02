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
#if TRINITY_DEPLOY_ENABLE_PRIMER1 != 1
#error "Primer #1 control endpoint is mandatory"
#endif
#if TRINITY_DEPLOY_P1_BRINGUP_ONLY != 0 && TRINITY_DEPLOY_P1_BRINGUP_ONLY != 1
#error "TRINITY_DEPLOY_P1_BRINGUP_ONLY must be 0 or 1"
#endif
#if TRINITY_DEPLOY_P1_BRINGUP_ONLY == 0 && TRINITY_DEPLOY_ENABLE_PRIMER2 != 1
#error "Full deploy requires Primer #2"
#endif
#if TRINITY_DEPLOY_ENABLE_MLKEM != 0 || TRINITY_DEPLOY_ENABLE_PAYLOAD_RELAY != 0
#error "ML-KEM and MCU payload relay must remain disabled"
#endif
#if TRINITY_DEPLOY_ENABLE_TINY_SESSION_COMMIT != 0 || \
    TRINITY_DEPLOY_ENABLE_DEMO_SECURE != 0
#error "Tiny session commit and DEMO_SECURE must remain disabled"
#endif

#define DEPLOY_BUILD_ID UINT32_C(0x00050100)
#define DEPLOY_MARKER_BOOT UINT32_C(0x44504254) /* DPBT */
#define DEPLOY_MARKER_OK UINT32_C(0x44504F4B)   /* DPOK */
#define DEPLOY_MARKER_ERR UINT32_C(0x44504552)  /* DPER */
#define P1_SELF_TEST_RESULT_MAX 16u

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
