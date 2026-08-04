#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
PART00 = ROOT / "sn32/src/app/trinity_deploy_main_part_00.inc"
PART02 = ROOT / "sn32/src/app/trinity_deploy_main_part_02.inc"
PART05 = ROOT / "sn32/src/app/trinity_deploy_main_part_05.inc"
PART06 = ROOT / "sn32/src/app/trinity_deploy_main_part_06.inc"
PART07 = ROOT / "sn32/src/app/trinity_deploy_main_part_07.inc"
PART08 = ROOT / "sn32/src/app/trinity_deploy_main_part_08.inc"
PART12 = ROOT / "sn32/src/app/trinity_deploy_main_part_12.inc"


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
    p02 = read(PART02)
    p05 = read(PART05)
    p06 = read(PART06)
    p07 = read(PART07)
    p08 = read(PART08)
    p12 = read(PART12)

    version = (
        macro(config, "TRINITY_DEPLOY_VERSION_MAJOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_MINOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_PATCH"),
    )
    if version != (0, 7, 13):
        fail(f"split transport image must be v0.7.13, got {version}")
    if macro(config, "TRINITY_DEPLOY_SPI_HZ") != 100_000:
        fail("qualification SPI clock must remain 100 kHz")
    if macro(config, "TRINITY_DEPLOY_SPI_CLKDIV") != 59:
        fail("qualification SPI clock divider must remain 59")
    require(p00, "#define DEPLOY_BUILD_ID UINT32_C(0x0007000D)", "identity")

    for token in (
        "static uint8_t g_pc_raw[TRINITY_PC_MAX_RAW_FRAME];",
        "static uint8_t g_spi_request_wire[TRINITY_SPI_MAX_PACKET];",
        "static uint8_t g_spi_response_wire[TRINITY_SPI_MAX_PACKET];",
        "static trinity_spi_packet_t g_spi_req;",
        "static trinity_spi_packet_t g_spi_rsp;",
    ):
        require(p02, token, "disjoint transport storage")
    forbid(p02, "g_transport_scratch", "disjoint transport storage")
    forbid(p02, "union {\n    trinity_spi_packet_t req", "packet storage")

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
    forbid(request_tx, "g_spi_response_wire", "request TX")

    response_rx = section(
        p06,
        "static trinity_error_code_t spi_read_response_segment(",
        "static trinity_error_code_t spi_select(",
        "response RX",
    )
    for token in (
        "SN_SPI0->DATA = 0u;",
        "data_word = SN_SPI0->DATA;",
        "value = (uint8_t)(data_word & UINT32_C(0xFF));",
        "g_spi_response_wire[trace_index] = value;",
        "g_spi_trace.response_bytes[trace_index] = value;",
    ):
        require(response_rx, token, "response RX")
    forbid(p06, "spi_bytes_segment", "split transport")
    forbid(p06, "static trinity_error_code_t spi_bytes(", "split transport")

    capture = section(
        p07,
        "static trinity_error_code_t spi_capture_response_once(",
        "static bool spi_response_read_retryable(",
        "response capture",
    )
    for token in (
        "g_spi_response_wire[0] != TRINITY_SPI_MAGIC",
        "trinity_read_be16(&g_spi_response_wire[6])",
        "spi_read_response_segment(TRINITY_SPI_HEADER_SIZE",
    ):
        require(capture, token, "response capture")
    forbid(capture, "uint8_t *response", "response capture")
    forbid(capture, "g_spi_trace.response_bytes[0]", "response validation source")

    for token in (
        "static trinity_error_code_t spi_prepare_request_window(",
        "TRINITY_DEPLOY_SPI_STARTUP_SETTLE_MS",
        "spi_drain_startup_mailbox(ep)",
        "rc = spi_prepare_request_window(ep);",
        "spi_write_request_bytes(g_spi_request_wire, request_len)",
        "trinity_spi_encode(&g_spi_req, g_spi_request_wire",
    ):
        require(p07, token, "request window")
    forbid(p07, "g_spi_buf", "request wire")

    for token in (
        "g_spi_response_wire[0] != TRINITY_SPI_MAGIC",
        "trinity_crc16_ccitt_false(g_spi_response_wire",
        "trinity_spi_decode(g_spi_response_wire",
    ):
        require(p08, token, "response validation")
    forbid(p08, "g_spi_trace.response_bytes", "response validation")

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

    print("PASS: v0.7.13 identity and 100 kHz profile are locked")
    print("PASS: PC, request and response storage are disjoint")
    print("PASS: request TX and response RX use separate implementations")
    print("PASS: response validation consumes only the canonical wire buffer")
    print("PASS: IRQ must remain inactive for a full quiet window before request")
    print("NOTE: source PASS does not claim Keil build, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
