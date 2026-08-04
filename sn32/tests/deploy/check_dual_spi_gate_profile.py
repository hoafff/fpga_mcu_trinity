#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
PART00 = ROOT / "sn32/src/app/trinity_deploy_main_part_00.inc"
PART01 = ROOT / "sn32/src/app/trinity_deploy_main_part_01.inc"
PART02 = ROOT / "sn32/src/app/trinity_deploy_main_part_02.inc"
PART04 = ROOT / "sn32/src/app/trinity_deploy_main_part_04.inc"
PART05 = ROOT / "sn32/src/app/trinity_deploy_main_part_05.inc"
PART06 = ROOT / "sn32/src/app/trinity_deploy_main_part_06.inc"
PART07 = ROOT / "sn32/src/app/trinity_deploy_main_part_07.inc"
PART08 = ROOT / "sn32/src/app/trinity_deploy_main_part_08.inc"
PART12 = ROOT / "sn32/src/app/trinity_deploy_main_part_12.inc"
PART15 = ROOT / "sn32/src/app/trinity_deploy_main_part_15.inc"
PART16 = ROOT / "sn32/src/app/trinity_deploy_main_part_16.inc"
PART17 = ROOT / "sn32/src/app/trinity_deploy_main_part_17.inc"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(text: str, token: str, label: str) -> None:
    if token not in text:
        fail(f"{label} missing {token}")


def forbid(text: str, token: str, label: str) -> None:
    if token in text:
        fail(f"{label} contains forbidden token {token}")


def macro(text: str, name: str) -> int:
    match = re.search(
        rf"^#define\s+{re.escape(name)}\s+(0x[0-9A-Fa-f]+|\d+)u?\s*$",
        text,
        re.M,
    )
    if match is None:
        fail(f"missing numeric macro {name}")
    return int(match.group(1), 0)


def section(text: str, start: str, end: str, label: str) -> str:
    first = text.find(start)
    last = text.find(end, first + len(start))
    if first < 0 or last < 0:
        fail(f"cannot isolate {label}")
    return text[first:last]


def main() -> int:
    config = read(CONFIG)
    p00 = read(PART00)
    p01 = read(PART01)
    p02 = read(PART02)
    p04 = read(PART04)
    p05 = read(PART05)
    p06 = read(PART06)
    p07 = read(PART07)
    p08 = read(PART08)
    p12 = read(PART12)
    p15 = read(PART15)
    p16 = read(PART16)
    p17 = read(PART17)

    version = (
        macro(config, "TRINITY_DEPLOY_VERSION_MAJOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_MINOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_PATCH"),
    )
    if version != (0, 7, 14):
        fail(f"live-PC transport image must be v0.7.14, got {version}")
    if macro(config, "TRINITY_DEPLOY_SPI_HZ") != 100_000:
        fail("qualification SPI clock must remain 100 kHz")
    if macro(config, "TRINITY_DEPLOY_SPI_CLKDIV") != 59:
        fail("qualification SPI clock divider must remain 59")
    require(p00, "#define DEPLOY_BUILD_ID UINT32_C(0x0007000E)", "identity")

    for token in (
        "static bool g_pc_service_enabled;",
        "static bool g_pc_poll_active;",
        "static bool g_automatic_probe_active;",
    ):
        require(p01, token, "PC service state")

    for token in (
        "static uint8_t g_pc_raw[TRINITY_PC_MAX_RAW_FRAME];",
        "static uint8_t g_spi_request_wire[TRINITY_SPI_MAX_PACKET];",
        "static uint8_t g_spi_response_wire[TRINITY_SPI_MAX_PACKET];",
        "static trinity_spi_packet_t g_spi_req;",
        "static trinity_spi_packet_t g_spi_rsp;",
    ):
        require(p02, token, "disjoint transport storage")
    forbid(p02, "g_transport_scratch", "disjoint transport storage")

    for token in (
        "static void pc_poll(void);",
        "if (g_pc_service_enabled && !g_pc_poll_active)",
        "pc_poll();",
    ):
        require(p04, token, "progress PC service")

    for token in (
        "SN_SPI0->CTRL0_b.DL = 7u;",
        "SN_SPI0->FIFO_TH = (1u << 31);",
        "SN_SPI0->CLKDIV_b.DIV = TRINITY_DEPLOY_SPI_CLKDIV;",
        "SN_SPI0->CTRL1 = 0u;",
    ):
        require(p05, token, "SPI init")

    request_tx = section(
        p06,
        "static trinity_error_code_t spi_write_request_bytes(",
        "static trinity_error_code_t spi_read_response_segment(",
        "request TX",
    )
    for token in (
        "SN_SPI0->DATA = tx[i];",
        "while ((SN_SPI0->STAT & SPI_BUSY) != 0u)",
        "while ((SN_SPI0->STAT & SPI_RX_EMPTY) != 0u)",
        "(void)SN_SPI0->DATA;",
    ):
        require(request_tx, token, "request TX")

    response_rx = section(
        p06,
        "static trinity_error_code_t spi_read_response_segment(",
        "static trinity_error_code_t spi_select(",
        "response RX",
    )
    for token in (
        "SN_SPI0->DATA = 0u;",
        "data_word = SN_SPI0->DATA;",
        "g_spi_response_wire[trace_index] = value;",
        "g_spi_trace.response_bytes[trace_index] = value;",
    ):
        require(response_rx, token, "response RX")
    forbid(p06, "spi_bytes_segment", "split transport")

    for token in (
        "static trinity_error_code_t spi_prepare_request_window(",
        "spi_drain_startup_mailbox(ep)",
        "spi_write_request_bytes(g_spi_request_wire, request_len)",
        "trinity_spi_encode(&g_spi_req, g_spi_request_wire",
    ):
        require(p07, token, "request window")

    for token in (
        "g_spi_response_wire[0] != TRINITY_SPI_MAGIC",
        "trinity_crc16_ccitt_false(g_spi_response_wire",
        "trinity_spi_decode(g_spi_response_wire",
    ):
        require(p08, token, "response validation")

    system_info = section(
        p12,
        "static void handle_get_system_info(",
        "static void handle_get_system_status(",
        "system info",
    )
    for token in (
        "TRINITY_DEPLOY_VERSION_PATCH",
        "DEPLOY_BUILD_ID",
        "g_controller.p1.build_id",
        "g_controller.p2.build_id",
    ):
        require(system_info, token, "system info")

    for token in (
        "if (g_automatic_probe_active &&",
        "req->command != TRINITY_PC_PING",
        "req->command != TRINITY_PC_GET_SYSTEM_INFO",
        "response_error(req, TRINITY_BUSY, TRINITY_SOURCE_SN32, 0u);",
    ):
        require(p15, token, "automatic probe command guard")

    for token in (
        "if (!g_pc_service_enabled || g_pc_poll_active) return;",
        "g_pc_poll_active = true;",
        "g_pc_poll_active = false;",
        "g_automatic_probe_active = true;",
    ):
        require(p16, token, "reentrant PC poll")

    for token in (
        "g_pc_service_enabled = true;",
        "progress();",
        "g_automatic_probe_active = false;",
        "g_automatic_probe_active = true;",
    ):
        require(p17, token, "live PC startup/periodic probe")

    print("PASS: v0.7.14 identity and 100 kHz profile are locked")
    print("PASS: PC UART is serviced from progress during warm-up and probes")
    print("PASS: PC polling is guarded against recursive re-entry")
    print("PASS: automatic probes allow local telemetry but reject nested control work")
    print("PASS: split SPI request/response transport remains locked")
    print("NOTE: source PASS does not claim Keil build, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
