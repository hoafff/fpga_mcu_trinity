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
    part12 = read(PART12)
    part14 = read(PART14)
    part15 = read(PART15)
    part17 = read(PART17)
    controller03 = read(CONTROLLER03)
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
    if version != (0, 7, 8):
        fail(f"SPI reset-completion image must be version 0.7.8, got {version}")
    if macro(config, "TRINITY_DEPLOY_SPI_HZ") != 100_000:
        fail("dual-SPI qualification must remain at 100 kHz")
    if macro(config, "TRINITY_DEPLOY_SPI_CLKDIV") != 59:
        fail("12 MHz / 2 / (CLKDIV+1) must use CLKDIV 59")
    if macro(config, "TRINITY_DEPLOY_SPI_CS_GUARD_US") != 10:
        fail("CS guard must remain 10 us")

    require(part00, "#define DEPLOY_BUILD_ID UINT32_C(0x00070008)", "deploy identity")
    require(part00, "SPI qualification clock and CLKDIV disagree", "deploy clock lock")

    for token in (
        "SPI_RESPONSE_SETTLE_MS = 15u",
        "SPI_STARTUP_WARMUP_MS = 2000u",
        "g_spi_first_failure",
        "g_spi_startup_residue",
        "SPI_TRANSFER_STAGE_TX_FULL",
        "SPI_TRANSFER_STAGE_BUSY",
        "SPI_TRANSFER_STAGE_RX_EMPTY",
    ):
        require(part01, token, "v0.7.8 timing and trace state")

    for token in (
        "SN_SPI0->FIFO_TH = 0u;",
        "SN_SPI0->CTRL0_b.SPIEN = 1u;",
        "SN_SPI0->CLKDIV_b.DIV = TRINITY_DEPLOY_SPI_CLKDIV;",
        "SN_SPI0->CTRL1 = 0u;",
    ):
        require(part05, token, "SPI init")
    forbid(part05, "SN_SPI0->FIFO_TH = (1u << 31);", "SPI init")
    forbid(part05, "SN_SPI0->CLKDIV_b.DIV = 5u", "SPI init")

    reset_idle = function_slice(
        part06,
        "static trinity_error_code_t spi_reset_idle(",
        "static trinity_error_code_t spi_bytes_segment(",
        "spi_reset_idle",
    )
    for token in (
        "while ((SN_SPI0->STAT & SPI_BUSY) != 0u)",
        "SN_SPI0->CTRL0_b.FRESET = 3u;",
        "while (SN_SPI0->CTRL0_b.FRESET != 0u)",
        "while ((SN_SPI0->STAT & SPI_RX_EMPTY) == 0u && drained < 8u)",
    ):
        require(reset_idle, token, "SPI reset completion")
    forbid(reset_idle, "SN_SPI0->CTRL0_b.SPIEN = 0u;", "SPI reset completion")
    forbid(reset_idle, "SN_SPI0->CTRL0_b.SPIEN = 1u;", "SPI reset completion")
    busy_before_reset = reset_idle.find("while ((SN_SPI0->STAT & SPI_BUSY) != 0u)")
    write_reset = reset_idle.find("SN_SPI0->CTRL0_b.FRESET = 3u;")
    wait_reset = reset_idle.find("while (SN_SPI0->CTRL0_b.FRESET != 0u)")
    if min(busy_before_reset, write_reset, wait_reset) < 0 or not (
        busy_before_reset < write_reset < wait_reset
    ):
        fail("SPI reset order must be BUSY idle -> FRESET write -> self-clear wait")

    transfer = function_slice(
        part06,
        "static trinity_error_code_t spi_bytes_segment(",
        "static trinity_error_code_t spi_bytes(",
        "spi_bytes_segment",
    )
    tx_write = transfer.find("SN_SPI0->DATA =")
    busy_wait = transfer.find("while ((SN_SPI0->STAT & SPI_BUSY)")
    rx_wait = transfer.find("while ((SN_SPI0->STAT & SPI_RX_EMPTY)")
    rx_read = transfer.find(
        "value = (uint8_t)(SN_SPI0->DATA & UINT32_C(0xFF));"
    )
    if min(tx_write, busy_wait, rx_wait, rx_read) < 0 or not (
        tx_write < busy_wait < rx_wait < rx_read
    ):
        fail("SPI byte order must be TX -> BUSY clear -> RX ready -> DATA[7:0]")
    if transfer.count("stage_start = g_ms") < 3:
        fail("TX_FULL, BUSY and RX_EMPTY waits need independent deadlines")

    spi_end = function_slice(
        part06,
        "static void spi_end(void)",
        "static bool irq_active(",
        "spi_end",
    )
    require(spi_end, "cs_all_high();", "SPI end")
    forbid(spi_end, "spi_reset_idle", "SPI end")
    forbid(spi_end, "FRESET", "SPI end")

    for token in (
        "spi_capture_response_once",
        "spi_response_read_retryable",
        "spi_capture_response",
        "retry the same pending response under a fresh CS",
        "attempt < 2u",
        "irq_active(ep)",
        "frame_len - TRINITY_SPI_HEADER_SIZE",
        "g_spi_trace.response_capture_length = (uint16_t)captured",
    ):
        require(part07, token, "single-request mailbox recovery")
    forbid(part07, "spi_bytes(NULL, g_spi_buf, TRINITY_SPI_MAX_PACKET)", "response capture")

    capture = function_slice(
        part07,
        "static trinity_error_code_t spi_capture_response_once(",
        "static bool spi_response_read_retryable(",
        "spi_capture_response_once",
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
        "spi_latch_first_failure();",
    ):
        require(part08, token, "response validation")

    system_info = function_slice(
        part12,
        "static void handle_get_system_info(",
        "static void handle_get_system_status(",
        "side-effect-free system info",
    )
    for token in (
        "GET_SYSTEM_INFO is local identity telemetry",
        "TRINITY_DEPLOY_VERSION_PATCH",
        "DEPLOY_BUILD_ID",
        "g_controller.p1.build_id",
        "g_controller.p2.build_id",
    ):
        require(system_info, token, "side-effect-free system info")
    forbid(system_info, "full_probe_all", "side-effect-free system info")
    forbid(system_info, "full_refresh_all", "side-effect-free system info")
    forbid(system_info, "endpoint_exchange", "side-effect-free system info")

    for token in (
        "SPI_STARTUP_WARMUP_MS",
        "TRINITY_DEPLOY_SPI_STARTUP_SETTLE_MS",
        "SPI_TRACE_CONTEXT_STARTUP_PROBE",
        "!g_spi_first_failure.valid",
    ):
        require(part17, token, "startup and periodic probe policy")

    for token in (
        "Probe fail-fast",
        "controller_probe_endpoint(controller, &controller->p1)",
        "controller->p2.ready = false",
        "controller_probe_endpoint(controller, &controller->p2)",
    ):
        require(controller03, token, "fail-fast endpoint discovery")
    p1_probe = controller03.find("controller_probe_endpoint(controller, &controller->p1)")
    p1_return = controller03.find("return rc;", p1_probe)
    p2_probe = controller03.find("controller_probe_endpoint(controller, &controller->p2)")
    if min(p1_probe, p1_return, p2_probe) < 0 or not (p1_probe < p1_return < p2_probe):
        fail("P2 probe can still execute before a P1 failure returns")

    for token in (
        "handle_spi_diagnostic",
        "handle_get_first_spi_failure",
        "serialize_spi_trace",
        "trace->transfer_stage",
        "trace->spi_status",
    ):
        require(part14, token, "diagnostic handlers")
    require(part15, "case TRINITY_PC_SPI_DIAGNOSTIC:", "PC dispatch")
    require(part15, "case TRINITY_PC_GET_FIRST_SPI_FAILURE:", "PC dispatch")

    require(constants, "SPI_DIAGNOSTIC = 0x7", "PC constants")
    require(constants, "GET_FIRST_SPI_FAILURE = 0x8", "PC constants")
    for token in (
        "class SpiDiagnosticTrace",
        "def spi_diagnostic(",
        "SPI_DIAGNOSTIC_HEADER_SIZE = 24",
    ):
        require(client, token, "PC diagnostic decoder")
    for token in (
        '"spi-diag"',
        '"spi-first-failure"',
        "HostCommand.GET_FIRST_SPI_FAILURE",
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
        "response_capture_length, 22",
    ):
        require(diag_test, token, "raw diagnostic regression")
    for token in (
        "test_startup_probe_failure_is_decoded_byte_exact",
        "test_startup_drain_reset_residue_is_not_latched_failure",
        "STARTUP_DRAIN_P1",
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
        require(text, "DUAL-SPI clean-boot qualification: FAIL", label)
        require(text, "NOT PROVEN", label)

    for token in (
        "architecture_version = 0.7.8",
        "sn32_build_id         = 0x00070008",
        "keep SPIEN enabled during FRESET",
        "wait for FRESET self-clear before CS",
        "system-info is local and side-effect free",
        "v0.7.8 exact Keil rebuild",
        "full_system_hardware_qualified:            false",
    ):
        require(gate_doc, token, "dual-SPI gate")

    for token in (
        'implementation_status = "V0_7_8_SPIEN_ON_FRESET_SELF_CLEAR_SOURCE_READY"',
        'qualification_build_id = "0x00070008"',
        'qualification_architecture_version = "0.7.8"',
        'qualification_spi_reset = "SPIEN_REMAINS_ON_FRESET_3_WAIT_SELF_CLEAR_ONCE_BEFORE_CS"',
        'qualification_system_info = "LOCAL_SIDE_EFFECT_FREE_IDENTITY_WITH_CACHED_ENDPOINT_BUILD_IDS"',
        'deploy_translation_unit_compile = "PENDING_CI_FOR_V0_7_8"',
    ):
        require(target, token, "SN32 target metadata")

    for token in (
        "sn32_architecture_version: 0.7.8",
        "sn32_build_id: 0x00070008",
        "spi_enabled_during_freset:",
        "freset_self_clear_wait_confirmed:",
        "no_freset_in_spi_end:",
        "system_info_side_effect_free:",
        "v0_7_8_exact_keil_rebuild:",
        "full_system_hardware_qualified: false",
    ):
        require(evidence_template, token, "dual-SPI evidence template")

    print("PASS: v0.7.8 identity and 100 kHz qualification profile are locked")
    print("PASS: FRESET executes with SPIEN on and is awaited before CS")
    print("PASS: one reset occurs before each CS and none occurs in spi_end")
    print("PASS: DATA[7:0] read order matches the SN32F407 register contract")
    print("PASS: system-info is local, side-effect free and usable for image proof")
    print("PASS: mailbox retry, fail-fast discovery and diagnostics remain present")
    print("NOTE: static PASS does not claim exact Keil rebuild, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
