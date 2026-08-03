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
PART14 = ROOT / "sn32/src/app/trinity_deploy_main_part_14.inc"
PART15 = ROOT / "sn32/src/app/trinity_deploy_main_part_15.inc"
PART17 = ROOT / "sn32/src/app/trinity_deploy_main_part_17.inc"
CONTROLLER00 = ROOT / "sn32/src/app/trinity_full_controller_part_00.inc"
CONTROLLER01 = ROOT / "sn32/src/app/trinity_full_controller_part_01.inc"
PC_CONSTANTS = ROOT / "pc_host/src/trinity_host/protocol/constants.py"
CLIENT = ROOT / "pc_host/src/trinity_host/serial_client.py"
CLI = ROOT / "pc_host/src/trinity_host/cli.py"
DUAL_TEST = ROOT / "pc_host/tests/test_dual_spi_bringup.py"
DIAG_TEST = ROOT / "pc_host/tests/test_spi_diagnostic.py"
FIRST_FAILURE_TEST = ROOT / "pc_host/tests/test_spi_first_failure.py"
REGISTRY = ROOT / "ai_context/interfaces/PROTOCOL_REGISTRY_v0.1.json"
GATE_DOC = ROOT / "sn32/docs/SN32_DUAL_SPI_HARDWARE_QUALIFICATION_NEXT_GATE.md"
FAILURE_DOC = ROOT / "sn32/docs/SN32_DUAL_SPI_CLEAN_BOOT_FAILURE_2026-08-03.md"
FAILURE_EVIDENCE = ROOT / "sn32/hardware/dual_spi_control_plane/evidence/clean_boot_failure_2026-08-03.txt"
UART_DOC = ROOT / "sn32/docs/PC_TO_SN32_UART_PING_HARDWARE_QUALIFICATION_2026-08-03.md"
UART_EVIDENCE = ROOT / "sn32/hardware/pc_uart_ping/evidence/pc_uart_ping_2026-08-03.txt"
EVIDENCE_TEMPLATE = ROOT / "sn32/hardware/dual_spi_control_plane/evidence/run_manifest_TEMPLATE.txt"


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
        fail(f"{label} still contains forbidden token {token}")


def macro(text: str, name: str) -> int:
    match = re.search(
        rf"^#define\s+{re.escape(name)}\s+(0x[0-9A-Fa-f]+|\d+)u?\s*$",
        text,
        re.M,
    )
    if match is None:
        fail(f"missing numeric macro {name}")
    return int(match.group(1), 0)


def function_slice(text: str, start: str, end: str, label: str) -> str:
    start_index = text.find(start)
    end_index = text.find(end, start_index + len(start))
    if start_index < 0 or end_index < 0:
        fail(f"cannot isolate {label}")
    return text[start_index:end_index]


def main() -> int:
    config = read(CONFIG)
    target = read(TARGET)
    part00 = read(PART00)
    part01 = read(PART01)
    part05 = read(PART05)
    part06 = read(PART06)
    part07 = read(PART07)
    part08 = read(PART08)
    part14 = read(PART14)
    part15 = read(PART15)
    part17 = read(PART17)
    controller = read(CONTROLLER00) + read(CONTROLLER01)
    constants = read(PC_CONSTANTS)
    client = read(CLIENT)
    cli = read(CLI)
    dual_test = read(DUAL_TEST)
    diag_test = read(DIAG_TEST)
    first_failure_test = read(FIRST_FAILURE_TEST)
    gate_doc = read(GATE_DOC)
    failure_doc = read(FAILURE_DOC)
    failure_evidence = read(FAILURE_EVIDENCE)
    uart_doc = read(UART_DOC)
    uart_evidence = read(UART_EVIDENCE)
    evidence_template = read(EVIDENCE_TEMPLATE)
    registry = json.loads(read(REGISTRY))

    version = (
        macro(config, "TRINITY_DEPLOY_VERSION_MAJOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_MINOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_PATCH"),
    )
    if version != (0, 7, 6):
        fail(f"exact-frame transport image must be version 0.7.6, got {version}")
    if macro(config, "TRINITY_DEPLOY_SPI_HZ") != 100_000:
        fail("dual-SPI qualification must remain at 100 kHz")
    if macro(config, "TRINITY_DEPLOY_SPI_CLKDIV") != 59:
        fail("12 MHz / 2 / (CLKDIV+1) must use CLKDIV 59")
    if macro(config, "TRINITY_DEPLOY_SPI_CS_GUARD_US") != 10:
        fail("CS/FIFO qualification guard must remain 10 us")
    if macro(config, "TRINITY_DEPLOY_SPI_STARTUP_SETTLE_MS") != 5:
        fail("startup settle must remain 5 ms")
    if macro(config, "TRINITY_DEPLOY_SPI_INTER_EXCHANGE_MS") != 1:
        fail("inter-exchange mailbox guard must remain 1 ms")

    require(part00, "#define DEPLOY_BUILD_ID UINT32_C(0x00070006)", "deploy identity")
    require(part00, "SPI qualification clock and CLKDIV disagree", "deploy clock lock")
    require(part05, "SN_SPI0->CLKDIV_b.DIV = TRINITY_DEPLOY_SPI_CLKDIV;", "SPI init")
    forbid(part05, "SN_SPI0->CLKDIV_b.DIV = 5u", "SPI init")

    for token in (
        "g_spi_first_failure",
        "g_spi_startup_residue",
        "g_spi_trace_context",
        "SPI_TRANSFER_STAGE_TX_FULL",
        "SPI_TRANSFER_STAGE_BUSY",
        "SPI_TRANSFER_STAGE_RX_EMPTY",
        "transfer_byte_index",
        "transfer_completed",
        "spi_status",
    ):
        require(part01, token, "first-failure state")

    for token in (
        "spi_bytes_segment",
        "spi_transfer_timeout",
        "byte_offset",
        "transfer_length",
        "Drain the received byte as soon as RX_EMPTY clears",
        "g_spi_trace.transfer_completed",
        "SN_SPI0->CTRL0_b.FRESET = 3u;",
    ):
        require(part06, token, "segmented SPI transport")

    transfer = function_slice(
        part06,
        "static trinity_error_code_t spi_bytes_segment(",
        "static trinity_error_code_t spi_bytes(",
        "spi_bytes_segment",
    )
    tx_write = transfer.find("SN_SPI0->DATA =")
    rx_wait = transfer.find("while ((SN_SPI0->STAT & SPI_RX_EMPTY)")
    rx_read = transfer.find("value = (uint8_t)SN_SPI0->DATA;")
    busy_wait = transfer.find("while ((SN_SPI0->STAT & SPI_BUSY)")
    if min(tx_write, rx_wait, rx_read, busy_wait) < 0 or not (
        tx_write < rx_wait < rx_read < busy_wait
    ):
        fail("SPI byte order must be TX write -> RX wait/read -> BUSY wait")
    if transfer.count("const uint32_t start = g_ms") != 0:
        fail("whole-packet timeout returned; each wait stage needs a fresh deadline")
    if transfer.count("stage_start = g_ms") < 3:
        fail("TX_FULL, RX_EMPTY and BUSY waits do not have independent deadlines")

    for token in (
        "spi_capture_response",
        "Read the eight-byte header and its declared payload/CRC",
        "spi_bytes_segment(NULL, g_spi_buf",
        "frame_len - TRINITY_SPI_HEADER_SIZE",
        "Clocking only the declared frame",
        "trace->response_capture_length != 16u",
        "g_spi_trace.response_capture_length = (uint16_t)captured",
        "if (issued_txid != NULL) *issued_txid = txid;",
        "g_spi_trace.context = g_spi_trace_context",
    ):
        require(part07, token, "exact-frame single-CS transport")
    forbid(part07, "spi_bytes(NULL, g_spi_buf, TRINITY_SPI_MAX_PACKET)", "response capture")

    capture = function_slice(
        part07,
        "static trinity_error_code_t spi_capture_response(",
        "static trinity_error_code_t spi_drain_startup_mailbox(",
        "spi_capture_response",
    )
    if capture.count("spi_select(ep)") != 1 or capture.count("spi_end();") != 1:
        fail("response header and remainder must share exactly one CS assertion")
    if capture.count("spi_bytes_segment(") != 2:
        fail("response capture must contain exactly header and remainder segments")
    if capture.find("spi_end();") < capture.rfind("spi_bytes_segment("):
        fail("CS is released before the declared response remainder is captured")

    for token in (
        "response_crc_received",
        "response_crc_calculated",
        "g_spi_rsp.transaction_id != txid",
        "TRINITY_DEPLOY_SPI_INTER_EXCHANGE_MS",
        "spi_latch_first_failure();",
    ):
        require(part08, token, "response validation")

    for token in (
        "handle_spi_diagnostic",
        "handle_get_first_spi_failure",
        "serialize_spi_trace",
        "trace->transfer_stage",
        "trace->transfer_direction",
        "trace->transfer_byte_index",
        "trace->transfer_completed",
        "trace->spi_status",
    ):
        require(part14, token, "diagnostic handlers")
    require(part15, "case TRINITY_PC_SPI_DIAGNOSTIC:", "PC dispatch")
    require(part15, "case TRINITY_PC_GET_FIRST_SPI_FAILURE:", "PC dispatch")
    for token in (
        "SPI_TRACE_CONTEXT_STARTUP_DRAIN_P1",
        "SPI_TRACE_CONTEXT_STARTUP_DRAIN_P2",
        "SPI_TRACE_CONTEXT_STARTUP_PROBE",
        "SPI_TRACE_CONTEXT_PERIODIC_PROBE",
        "!g_spi_first_failure.valid",
    ):
        require(part17, token, "startup and periodic probe policy")

    for token in (
        "uint16_t issued_txid = 0u;",
        "((uint32_t)TRINITY_SPI_GET_INFO << 16)",
        "((uint32_t)TRINITY_SPI_GET_STATUS << 16)",
    ):
        require(controller, token, "controller target-txid telemetry")

    require(constants, "SPI_DIAGNOSTIC = 0x7", "PC constants")
    require(constants, "GET_FIRST_SPI_FAILURE = 0x8", "PC constants")
    for token in (
        "class SpiDiagnosticTrace",
        "def spi_diagnostic(",
        "SPI_DIAGNOSTIC_HEADER_SIZE = 24",
        "request_bytes=payload[request_start:response_start]",
    ):
        require(client, token, "PC diagnostic decoder")
    for token in (
        '"spi-diag"',
        '"spi-first-failure"',
        "_first_spi_failure_dict",
        "HostCommand.GET_FIRST_SPI_FAILURE",
        '"transfer_stage"',
        '"transfer_byte_index"',
        '"response_crc_match"',
    ):
        require(cli, token, "PC diagnostic CLI")
    for token in (
        "test_probe_and_separate_p1_p2_retained_self_tests",
        "P1_KAT_TEST_MASK",
        "P2_KAT_TEST_MASK",
    ):
        require(dual_test, token, "dual-SPI regression")
    for token in (
        "test_p2_get_info_trace_is_byte_exact",
        "HostCommand.SPI_DIAGNOSTIC",
        "not side-effect-free",
    ):
        require(diag_test, token, "raw diagnostic regression")
    for token in (
        "test_startup_probe_failure_is_decoded_byte_exact",
        "test_startup_drain_reset_residue_is_not_latched_failure",
        "transfer_extension",
        "RX_EMPTY",
        "STARTUP_DRAIN_P1",
        "BAD_LENGTH(0x0103)",
    ):
        require(first_failure_test, token, "first-failure regression")

    if registry["pc"]["commands"].get("SPI_DIAGNOSTIC") != 7:
        fail("protocol registry does not assign SPI_DIAGNOSTIC=7")
    if registry["pc"]["commands"].get("GET_FIRST_SPI_FAILURE") != 8:
        fail("protocol registry does not assign GET_FIRST_SPI_FAILURE=8")

    require(uart_doc, "PC <-> SN32 UART PING HARDWARE: PASS", "UART qualification")
    require(uart_evidence, "PC <-> SN32 UART PING HARDWARE: PASS", "UART evidence")
    for text, label in (
        (failure_doc, "failure audit"),
        (failure_evidence, "failure evidence"),
    ):
        for token in (
            "DUAL-SPI clean-boot qualification: FAIL",
            "First failing endpoint:",
            "NOT PROVEN",
            "TRANSACTION_CONFLICT 0x0205",
        ):
            require(text, token, label)

    for token in (
        "architecture_version = 0.7.6",
        "sn32_build_id         = 0x00070006",
        "header + declared remainder",
        "RX FIFO drain",
        "response_capture_length=22",
        "response_capture_length=26",
        "v0.7.6 exact Keil rebuild",
        "full_system_hardware_qualified:            false",
    ):
        require(gate_doc, token, "dual-SPI gate")
    for token in (
        'implementation_status = "V0_7_6_EXACT_FRAME_SINGLE_CS_RX_DRAIN_SOURCE_READY"',
        'qualification_build_id = "0x00070006"',
        'qualification_architecture_version = "0.7.6"',
        'qualification_response_capture = "HEADER_THEN_DECLARED_REMAINDER_UNDER_ONE_CS_EXACT_FRAME_LENGTH"',
        'deploy_translation_unit_compile = "PENDING_CI_FOR_V0_7_6"',
    ):
        require(target, token, "SN32 target metadata")
    for token in (
        "sn32_architecture_version: 0.7.6",
        "sn32_build_id: 0x00070006",
        "trace_response_capture_length:",
        "p1_get_info_response_capture_length_22:",
        "p1_get_status_response_capture_length_26:",
        "single_cs_header_and_remainder_confirmed:",
        "rx_fifo_drained_before_busy_wait_confirmed:",
        "v0_7_6_exact_keil_rebuild:",
        "full_system_hardware_qualified: false",
    ):
        require(evidence_template, token, "dual-SPI evidence template")

    print("PASS: v0.7.6 identity and 100 kHz qualification profile are locked")
    print("PASS: response header and declared remainder use one continuous CS")
    print("PASS: response capture length equals the declared frame length")
    print("PASS: RX FIFO is drained before the BUSY completion wait")
    print("PASS: timeout telemetry and immutable first-failure latch remain enabled")
    print("NOTE: static PASS does not claim exact Keil rebuild, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
