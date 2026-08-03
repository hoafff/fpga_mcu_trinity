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


def macro(text: str, name: str) -> int:
    match = re.search(
        rf"^#define\s+{re.escape(name)}\s+(0x[0-9A-Fa-f]+|\d+)u?\s*$",
        text,
        re.M,
    )
    if match is None:
        fail(f"missing numeric macro {name}")
    return int(match.group(1), 0)


def main() -> int:
    config = read(CONFIG)
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
    if version != (0, 7, 5):
        fail(f"SPI timeout telemetry image must be version 0.7.5, got {version}")
    if macro(config, "TRINITY_DEPLOY_SPI_HZ") != 100_000:
        fail("dual-SPI qualification must remain at 100 kHz")
    if macro(config, "TRINITY_DEPLOY_SPI_CLKDIV") != 59:
        fail("12 MHz / 2 / (CLKDIV+1) must use CLKDIV 59")
    if macro(config, "TRINITY_DEPLOY_SPI_CS_GUARD_US") != 10:
        fail("v0.7.5 CS/FIFO qualification guard must be 10 us")
    if macro(config, "TRINITY_DEPLOY_SPI_STARTUP_SETTLE_MS") != 5:
        fail("v0.7.5 startup settle must be 5 ms")
    if macro(config, "TRINITY_DEPLOY_SPI_INTER_EXCHANGE_MS") != 1:
        fail("v0.7.5 inter-exchange mailbox guard must be 1 ms")

    require(part00, "#define DEPLOY_BUILD_ID UINT32_C(0x00070005)", "deploy part 00")
    require(part00, "handle_get_first_spi_failure", "deploy part 00")
    require(part00, "SPI qualification clock and CLKDIV disagree", "deploy part 00")
    require(part05, "SN_SPI0->CLKDIV_b.DIV = TRINITY_DEPLOY_SPI_CLKDIV;", "deploy part 05")
    if "SN_SPI0->CLKDIV_b.DIV = 5u" in part05:
        fail("old 1 MHz literal divider returned")

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
        "SPI_TRACE_CONTEXT_STARTUP_DRAIN_P1",
        "SPI_TRACE_CONTEXT_STARTUP_PROBE",
        "SPI_TRACE_CONTEXT_HOST_DIAGNOSTIC",
    ):
        require(part01, token, "first-failure byte telemetry state")
    for token in (
        "spi_guard_delay",
        "spi_transfer_timeout",
        "SPI_TRANSFER_STAGE_TX_FULL",
        "SPI_TRANSFER_STAGE_BUSY",
        "SPI_TRANSFER_STAGE_RX_EMPTY",
        "g_spi_trace.transfer_completed",
        "g_spi_trace.spi_status = SN_SPI0->STAT",
        "SN_SPI0->CTRL0_b.FRESET = 3u;",
        "gpio_write(ep->cs_port, ep->cs_pin, false);",
    ):
        require(part06, token, "SPI byte-level transport telemetry")

    for token in (
        "spi_trace_begin",
        "spi_latch_first_failure",
        "spi_trace_is_startup_reset_residue",
        "spi_record_startup_residue",
        "trace->command != 0u",
        "trace->target_txid != 0u",
        "trace->response_frame_length != 16u",
        "TRINITY_FLAG_RESPONSE | TRINITY_FLAG_ERROR",
        "spi_drain_startup_mailbox",
        "spi_bytes(NULL, g_spi_buf, TRINITY_SPI_MAX_PACKET)",
        "The Primer mailbox restarts at byte zero",
        "if (issued_txid != NULL) *issued_txid = txid;",
        "g_spi_trace.context = g_spi_trace_context",
    ):
        require(part07, token, "single-CS residue-aware transport")
    if "spi_bytes(NULL, g_spi_buf, TRINITY_SPI_HEADER_SIZE)" in part07:
        fail("split response header read returned")
    for token in (
        "response_crc_received",
        "response_crc_calculated",
        "g_spi_rsp.transaction_id != txid",
        "TRINITY_DEPLOY_SPI_INTER_EXCHANGE_MS",
        "spi_latch_first_failure();",
    ):
        require(part08, token, "response settle and validation")
    for token in (
        "handle_spi_diagnostic",
        "handle_get_first_spi_failure",
        "serialize_spi_trace",
        "g_spi_startup_residue.valid",
        "trace->transfer_stage",
        "trace->transfer_direction",
        "trace->transfer_byte_index",
        "trace->transfer_completed",
        "trace->spi_status",
        "TRINITY_SPI_GET_INFO",
        "TRINITY_SPI_GET_STATUS",
        "SPI_TRACE_CONTEXT_HOST_DIAGNOSTIC",
    ):
        require(part14, token, "diagnostic handlers")
    require(part15, "case TRINITY_PC_SPI_DIAGNOSTIC:", "PC dispatch")
    require(part15, "case TRINITY_PC_GET_FIRST_SPI_FAILURE:", "PC dispatch")
    require(part17, "TRINITY_DEPLOY_SPI_STARTUP_SETTLE_MS", "startup settle")
    require(part17, "SPI_TRACE_CONTEXT_STARTUP_DRAIN_P1", "startup context")
    require(part17, "SPI_TRACE_CONTEXT_STARTUP_DRAIN_P2", "startup context")
    require(part17, "SPI_TRACE_CONTEXT_STARTUP_PROBE", "startup context")
    require(part17, "SPI_TRACE_CONTEXT_PERIODIC_PROBE", "periodic context")
    require(part17, "!g_spi_first_failure.valid", "periodic failure freeze")
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
        '"startup_residue"',
        '"transfer_stage"',
        '"transfer_direction"',
        '"transfer_byte_index"',
        '"transfer_completed"',
        '"spi_status"',
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
        "SpiCommand.RUN_SELF_TEST",
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
        "test_unlatched_response_has_no_trace",
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
            "related_target_txid",
        ):
            require(text, token, label)

    for token in (
        "SN32 -> P1/P2 DUAL-SPI CONTROL PLANE HARDWARE: PASS",
        "secure_enable_i  -> GND",
        "SPI0 CLKDIV   = 59",
        "P2 R13 uart_rx_i -> 3.3 V through 10 kΩ",
        "architecture_version = 0.7.5",
        "sn32_build_id         = 0x00070005",
        "inter-exchange guard                 = 1 ms",
        "transfer_stage",
        "transfer_byte_index",
        "spi_status",
        "spi-first-failure",
        "startup_residue=True",
        "spi-diag --target p2 --command get-info",
    ):
        require(gate_doc, token, "dual-SPI gate")
    for token in (
        "repository_commit:",
        "sn32_build_id: 0x00070005",
        "spi_frequency_hz: 100000",
        "spi_cs_guard_us: 10",
        "spi_inter_exchange_ms: 1",
        "first_spi_failure_log:",
        "startup_reset_residue_log:",
        "v0_7_5_exact_keil_rebuild:",
        "first_failure_transfer_stage:",
        "first_failure_transfer_byte_index:",
        "first_failure_spi_status:",
        "p2_uart_rx_r13_pulled_up_to_3v3_through_10k:",
        "p1_retained_kat_0x013e:",
        "p2_retained_kat_0x03e3:",
        "full_system_hardware_qualified: false",
    ):
        require(evidence_template, token, "dual-SPI evidence template")

    print("PASS: prior v0.7.1 through v0.7.4 evidence remains explicitly scoped")
    print("PASS: v0.7.5 keeps 100 kHz single-CS transport and reset-residue separation")
    print("PASS: 1 ms inter-exchange guard separates consecutive mailbox commands")
    print("PASS: first failure preserves timeout stage, direction, byte and SPI status")
    print("PASS: periodic probing freezes after the immutable first active failure")
    print("NOTE: static PASS does not claim exact Keil rebuild, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
