#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
PART00 = ROOT / "sn32/src/app/trinity_deploy_main_part_00.inc"
PART01 = ROOT / "sn32/src/app/trinity_deploy_main_part_01.inc"
PART05 = ROOT / "sn32/src/app/trinity_deploy_main_part_05.inc"
PART06 = ROOT / "sn32/src/app/trinity_deploy_main_part_06.inc"
PART07 = ROOT / "sn32/src/app/trinity_deploy_main_part_07.inc"
PART08 = ROOT / "sn32/src/app/trinity_deploy_main_part_08.inc"
PART12 = ROOT / "sn32/src/app/trinity_deploy_main_part_12.inc"
PART14 = ROOT / "sn32/src/app/trinity_deploy_main_part_14.inc"
PART15 = ROOT / "sn32/src/app/trinity_deploy_main_part_15.inc"
PART17 = ROOT / "sn32/src/app/trinity_deploy_main_part_17.inc"
CONTROLLER03 = ROOT / "sn32/src/app/trinity_full_controller_part_03.inc"
PC_CONSTANTS = ROOT / "pc_host/src/trinity_host/protocol/constants.py"
CLIENT = ROOT / "pc_host/src/trinity_host/serial_client.py"
CLI = ROOT / "pc_host/src/trinity_host/cli.py"
REGISTRY = ROOT / "ai_context/interfaces/PROTOCOL_REGISTRY_v0.1.json"


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
    p05 = read(PART05)
    p06 = read(PART06)
    p07 = read(PART07)
    p08 = read(PART08)
    p12 = read(PART12)
    p14 = read(PART14)
    p15 = read(PART15)
    p17 = read(PART17)
    controller03 = read(CONTROLLER03)
    constants = read(PC_CONSTANTS)
    client = read(CLIENT)
    cli = read(CLI)
    registry = json.loads(read(REGISTRY))

    version = (
        macro(config, "TRINITY_DEPLOY_VERSION_MAJOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_MINOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_PATCH"),
    )
    if version != (0, 7, 12):
        fail(f"canonical-response image must be v0.7.12, got {version}")
    if macro(config, "TRINITY_DEPLOY_SPI_HZ") != 100_000:
        fail("qualification SPI clock must remain 100 kHz")
    if macro(config, "TRINITY_DEPLOY_SPI_CLKDIV") != 59:
        fail("12 MHz qualification clock must use CLKDIV=59")
    require(p00, "#define DEPLOY_BUILD_ID UINT32_C(0x0007000C)", "identity")

    for token in (
        "SPI_RESPONSE_SETTLE_MS = 15u",
        "SPI_STARTUP_WARMUP_MS = 2000u",
        "SPI_RESPONSE_SAMPLE_MAX = 8u",
        "response_data_words[SPI_RESPONSE_SAMPLE_MAX]",
        "response_bytes[TRINITY_SPI_MAX_PACKET]",
    ):
        require(p01, token, "trace storage")

    for token in (
        "SN_SPI0->CTRL0_b.DL = 7u;",
        "SN_SPI0->FIFO_TH = (1u << 31);",
        "SN_SPI0->CLKDIV_b.DIV = TRINITY_DEPLOY_SPI_CLKDIV;",
        "SN_SPI0->CTRL1 = 0u;",
        "SN_SPI0->CTRL0_b.SPIEN = 1u;",
    ):
        require(p05, token, "SPI init")

    reset_idle = section(
        p06,
        "static trinity_error_code_t spi_reset_idle(",
        "static trinity_error_code_t spi_bytes_segment(",
        "SPI reset",
    )
    for token in (
        "SN_SPI0->CTRL0_b.FRESET = 3u;",
        "while (SN_SPI0->CTRL0_b.FRESET != 0u)",
        "while ((SN_SPI0->STAT & SPI_RX_EMPTY) == 0u",
    ):
        require(reset_idle, token, "SPI reset")

    transfer = section(
        p06,
        "static trinity_error_code_t spi_bytes_segment(",
        "static trinity_error_code_t spi_bytes(",
        "SPI transfer",
    )
    ordered = [
        transfer.find("SN_SPI0->DATA ="),
        transfer.find("while ((SN_SPI0->STAT & SPI_BUSY)"),
        transfer.find("while ((SN_SPI0->STAT & SPI_RX_EMPTY)"),
        transfer.find("data_word = SN_SPI0->DATA;"),
        transfer.find("value = (uint8_t)(data_word & UINT32_C(0xFF));"),
        transfer.find("g_spi_trace.response_bytes[trace_index] = value;"),
    ]
    if min(ordered) < 0 or ordered != sorted(ordered):
        fail("response byte path must be TX -> complete -> RX ready -> DATA -> canonical trace")
    for token in (
        "direction == SPI_TRANSFER_DIRECTION_RESPONSE",
        "trace_index >= TRINITY_SPI_MAX_PACKET",
        "response_status_before_read[trace_index]",
        "response_data_words[trace_index]",
        "response_status_after_read[trace_index]",
    ):
        require(transfer, token, "canonical response capture")

    capture = section(
        p07,
        "static trinity_error_code_t spi_capture_response_once(",
        "static bool spi_response_read_retryable(",
        "response capture",
    )
    for token in (
        "response = g_spi_trace.response_bytes;",
        "memset(response, 0, sizeof(g_spi_trace.response_bytes));",
        "spi_bytes_segment(NULL, NULL,",
        "payload_length = trinity_read_be16(&response[6]);",
    ):
        require(capture, token, "response capture")
    forbid(capture, "memcpy(g_spi_trace.response_bytes, g_spi_buf", "response capture")
    forbid(capture, "g_spi_buf[0]", "response capture")

    retry = section(
        p07,
        "static trinity_error_code_t spi_capture_response(",
        "static trinity_error_code_t spi_drain_startup_mailbox(",
        "mailbox retry",
    )
    require(retry, "attempt < 2u", "mailbox retry")
    require(retry, "spi_capture_response_once(ep, response_len)", "mailbox retry")
    forbid(retry, "endpoint_exchange", "mailbox retry")
    forbid(retry, "trinity_spi_encode", "mailbox retry")

    for token in (
        "response = g_spi_trace.response_bytes;",
        "trinity_crc16_ccitt_false(response, response_len - 2u)",
        "trinity_spi_decode(response, response_len, &g_spi_rsp)",
    ):
        require(p07, token, "startup-drain decode")

    for token in (
        "const uint8_t *response = g_spi_trace.response_bytes;",
        "response[0] != TRINITY_SPI_MAGIC",
        "trinity_read_be16(&response[6])",
        "trinity_crc16_ccitt_false(response, response_len - 2u)",
        "trinity_spi_decode(response, response_len, &g_spi_rsp)",
    ):
        require(p08, token, "endpoint response validation")
    forbid(p08, "g_spi_buf", "endpoint response validation")

    system_info = section(
        p12,
        "static void handle_get_system_info(",
        "static void handle_get_system_status(",
        "system info",
    )
    for token in (
        "GET_SYSTEM_INFO is local identity telemetry",
        "TRINITY_DEPLOY_VERSION_PATCH",
        "DEPLOY_BUILD_ID",
        "g_controller.p1.build_id",
        "g_controller.p2.build_id",
    ):
        require(system_info, token, "system info")
    for token in ("full_probe_all", "full_refresh_all", "endpoint_exchange"):
        forbid(system_info, token, "side-effect-free system info")

    for token in (
        "SPI_STARTUP_WARMUP_MS",
        "SPI_TRACE_CONTEXT_STARTUP_PROBE",
        "!g_spi_first_failure.valid",
    ):
        require(p17, token, "startup policy")
    for token in (
        "Probe fail-fast",
        "controller_probe_endpoint(controller, &controller->p1)",
        "controller->p2.ready = false",
        "controller_probe_endpoint(controller, &controller->p2)",
    ):
        require(controller03, token, "fail-fast discovery")

    for token in (
        "handle_spi_diagnostic",
        "handle_get_first_spi_failure",
        "trace->response_data_words[i]",
        "trace->spi_fifo_th",
    ):
        require(p14, token, "diagnostics")
    require(p15, "case TRINITY_PC_SPI_DIAGNOSTIC:", "PC dispatch")
    require(p15, "case TRINITY_PC_GET_FIRST_SPI_FAILURE:", "PC dispatch")
    require(constants, "SPI_DIAGNOSTIC = 0x7", "PC constants")
    require(constants, "GET_FIRST_SPI_FAILURE = 0x8", "PC constants")
    require(client, "class SpiDiagnosticTrace", "PC decoder")
    require(cli, '"spi-first-failure"', "PC CLI")

    if registry["pc"]["commands"].get("SPI_DIAGNOSTIC") != 7:
        fail("registry SPI_DIAGNOSTIC must remain 7")
    if registry["pc"]["commands"].get("GET_FIRST_SPI_FAILURE") != 8:
        fail("registry GET_FIRST_SPI_FAILURE must remain 8")

    print("PASS: v0.7.12 identity and 100 kHz profile are locked")
    print("PASS: hardware DATA[7:0] is stored directly in the canonical trace buffer")
    print("PASS: header, length, CRC and decoder all consume canonical response bytes")
    print("PASS: raw register telemetry remains available for hardware confirmation")
    print("NOTE: static PASS does not claim Keil build, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
