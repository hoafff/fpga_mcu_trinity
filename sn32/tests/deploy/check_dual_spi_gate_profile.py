#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
TARGET = ROOT / "sn32/target.toml"
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
FIRST_FAILURE_TEST = ROOT / "pc_host/tests/test_spi_first_failure.py"
REGISTRY = ROOT / "ai_context/interfaces/PROTOCOL_REGISTRY_v0.1.json"
GATE_DOC = ROOT / "sn32/docs/SN32_DUAL_SPI_HARDWARE_QUALIFICATION_NEXT_GATE.md"
EVIDENCE = ROOT / "sn32/hardware/dual_spi_control_plane/evidence/run_manifest_TEMPLATE.txt"


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
    a = text.find(start)
    b = text.find(end, a + len(start))
    if a < 0 or b < 0:
        fail(f"cannot isolate {label}")
    return text[a:b]


def main() -> int:
    config = read(CONFIG)
    target = read(TARGET)
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
    first_failure_test = read(FIRST_FAILURE_TEST)
    gate_doc = read(GATE_DOC)
    evidence = read(EVIDENCE)
    registry = json.loads(read(REGISTRY))

    version = (
        macro(config, "TRINITY_DEPLOY_VERSION_MAJOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_MINOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_PATCH"),
    )
    if version != (0, 7, 11):
        fail(f"raw-telemetry image must be v0.7.11, got {version}")
    if macro(config, "TRINITY_DEPLOY_SPI_HZ") != 100_000:
        fail("qualification SPI clock must remain 100 kHz")
    if macro(config, "TRINITY_DEPLOY_SPI_CLKDIV") != 59:
        fail("12 MHz qualification clock must use CLKDIV=59")

    require(p00, "#define DEPLOY_BUILD_ID UINT32_C(0x0007000B)", "identity")
    require(p00, "SPI qualification clock and CLKDIV disagree", "clock lock")

    for token in (
        "SPI_RESPONSE_SETTLE_MS = 15u",
        "SPI_STARTUP_WARMUP_MS = 2000u",
        "SPI_RESPONSE_SAMPLE_MAX = 8u",
        "uint32_t spi_ctrl0;",
        "uint32_t spi_ctrl1;",
        "uint32_t spi_clkdiv;",
        "uint32_t spi_fifo_th;",
        "response_status_before_read[SPI_RESPONSE_SAMPLE_MAX]",
        "response_data_words[SPI_RESPONSE_SAMPLE_MAX]",
        "response_status_after_read[SPI_RESPONSE_SAMPLE_MAX]",
        "g_spi_first_failure",
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
        "spi_reset_idle",
    )
    for token in (
        "while ((SN_SPI0->STAT & SPI_BUSY) != 0u)",
        "SN_SPI0->CTRL0_b.FRESET = 3u;",
        "while (SN_SPI0->CTRL0_b.FRESET != 0u)",
    ):
        require(reset_idle, token, "SPI reset completion")
    forbid(reset_idle, "SN_SPI0->CTRL0_b.SPIEN = 0u;", "SPI reset completion")

    transfer = section(
        p06,
        "static trinity_error_code_t spi_bytes_segment(",
        "static trinity_error_code_t spi_bytes(",
        "spi byte transfer",
    )
    order = [
        transfer.find("SN_SPI0->DATA ="),
        transfer.find("while ((SN_SPI0->STAT & SPI_BUSY)"),
        transfer.find("while ((SN_SPI0->STAT & SPI_RX_EMPTY)"),
        transfer.find("status_before_read = SN_SPI0->STAT;"),
        transfer.find("data_word = SN_SPI0->DATA;"),
        transfer.find("status_after_read = SN_SPI0->STAT;"),
        transfer.find("value = (uint8_t)(data_word & UINT32_C(0xFF));"),
    ]
    if min(order) < 0 or order != sorted(order):
        fail("SPI telemetry order must be TX -> complete -> RX ready -> STAT/DATA/STAT")
    for token in (
        "g_spi_trace.spi_ctrl0 = SN_SPI0->CTRL0;",
        "g_spi_trace.spi_ctrl1 = SN_SPI0->CTRL1;",
        "g_spi_trace.spi_clkdiv = SN_SPI0->CLKDIV;",
        "g_spi_trace.spi_fifo_th = SN_SPI0->FIFO_TH;",
        "trace_index < SPI_RESPONSE_SAMPLE_MAX",
        "response_status_before_read[trace_index]",
        "response_data_words[trace_index]",
        "response_status_after_read[trace_index]",
    ):
        require(transfer, token, "raw response telemetry")

    capture = section(
        p07,
        "static trinity_error_code_t spi_capture_response_once(",
        "static bool spi_response_read_retryable(",
        "response capture",
    )
    if capture.count("spi_select(ep)") != 1 or capture.count("spi_end();") != 1:
        fail("response header and remainder must use one CS window")
    if capture.count("spi_bytes_segment(") != 2:
        fail("response capture must contain header and declared remainder")
    require(capture, "frame_len - TRINITY_SPI_HEADER_SIZE", "response capture")

    retry = section(
        p07,
        "static trinity_error_code_t spi_capture_response(",
        "static trinity_error_code_t spi_drain_startup_mailbox(",
        "mailbox retry",
    )
    require(retry, "attempt < 2u", "mailbox retry")
    require(retry, "spi_capture_response_once(ep, response_len)", "mailbox retry")
    forbid(retry, "spi_prime_pending_startup_get_info", "mailbox retry")
    forbid(p07, "spi_bytes(NULL, NULL, 10u)", "disproven startup prime")

    for token in (
        "response_crc_received",
        "response_crc_calculated",
        "g_spi_rsp.transaction_id != txid",
        "spi_latch_first_failure();",
    ):
        require(p08, token, "response validation")

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
        "trace->spi_ctrl0",
        "trace->spi_ctrl1",
        "trace->spi_clkdiv",
        "trace->spi_fifo_th",
        "trace->response_sample_count",
        "trace->response_status_before_read[i]",
        "trace->response_data_words[i]",
        "trace->response_status_after_read[i]",
        "max_samples",
    ):
        require(p14, token, "first-failure serializer")
    require(p15, "case TRINITY_PC_SPI_DIAGNOSTIC:", "PC dispatch")
    require(p15, "case TRINITY_PC_GET_FIRST_SPI_FAILURE:", "PC dispatch")

    for token in (
        '"spi_ctrl0"',
        '"spi_ctrl1"',
        '"spi_clkdiv"',
        '"spi_fifo_th"',
        '"response_sample_count"',
        '"response_status_before_read"',
        '"response_data_words"',
        '"response_status_after_read"',
        "if len(extension) == 12:",
    ):
        require(cli, token, "PC telemetry decoder")
    require(first_failure_test, "test_extended_register_telemetry_is_decoded", "PC regression")

    require(constants, "SPI_DIAGNOSTIC = 0x7", "PC constants")
    require(constants, "GET_FIRST_SPI_FAILURE = 0x8", "PC constants")
    require(client, "class SpiDiagnosticTrace", "PC decoder")
    if registry["pc"]["commands"].get("SPI_DIAGNOSTIC") != 7:
        fail("registry SPI_DIAGNOSTIC must remain 7")
    if registry["pc"]["commands"].get("GET_FIRST_SPI_FAILURE") != 8:
        fail("registry GET_FIRST_SPI_FAILURE must remain 8")

    for token in (
        "architecture_version = 0.7.11",
        "sn32_build_id         = 0x0007000B",
        "full 32-bit DATA register value",
        "No further transport behavior may be changed",
        "Do not run `spi-diag`",
        "full_system_hardware_qualified:            false",
    ):
        require(gate_doc, token, "dual-SPI gate")

    for token in (
        'implementation_status = "V0_7_11_RAW_SPI_DATA_WORD_TELEMETRY_SOURCE_READY"',
        'qualification_build_id = "0x0007000B"',
        'qualification_architecture_version = "0.7.11"',
        'qualification_first_failure_telemetry = "TRANSFER_METADATA_PLUS_CTRL0_CTRL1_CLKDIV_FIFO_TH_AND_FIRST_8_RESPONSE_DATA_WORDS_WITH_STATUS_BEFORE_AFTER_READ"',
        'deploy_translation_unit_compile = "PENDING_CI_FOR_V0_7_11"',
    ):
        require(target, token, "target metadata")

    for token in (
        "sn32_architecture_version: 0.7.11",
        "sn32_build_id: 0x0007000B",
        "full_32bit_data_register_captured:",
        "response_status_before_read:",
        "response_data_words:",
        "response_status_after_read:",
        "full_system_hardware_qualified: false",
    ):
        require(evidence, token, "evidence template")

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

    print("PASS: v0.7.11 identity and 100 kHz measurement profile are locked")
    print("PASS: full DATA words and STAT-before/after samples are retained")
    print("PASS: runtime CTRL0/CTRL1/CLKDIV/FIFO_TH readback is serialized")
    print("PASS: transport behavior remains unchanged while root cause is measured")
    print("NOTE: static PASS does not claim Keil build, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
