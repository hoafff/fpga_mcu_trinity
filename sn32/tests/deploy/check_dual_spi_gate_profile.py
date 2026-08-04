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
    if version != (0, 7, 9):
        fail(f"startup mailbox recovery image must be version 0.7.9, got {version}")
    if macro(config, "TRINITY_DEPLOY_SPI_HZ") != 100_000:
        fail("dual-SPI qualification must remain at 100 kHz")
    if macro(config, "TRINITY_DEPLOY_SPI_CLKDIV") != 59:
        fail("12 MHz / 2 / (CLKDIV+1) must use CLKDIV 59")
    if macro(config, "TRINITY_DEPLOY_SPI_CS_GUARD_US") != 10:
        fail("CS guard must remain 10 us")

    require(part00, "#define DEPLOY_BUILD_ID UINT32_C(0x00070009)", "deploy identity")
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
        require(part01, token, "v0.7.9 timing and trace state")

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

    transfer = function_slice(
        part06,
        "static trinity_error_code_t spi_bytes_segment(",
        "static trinity_error_code_t spi_bytes(",
        "spi_bytes_segment",
    )
    tx_write = transfer.find("SN_SPI0->DATA =")
    busy_wait = transfer.find("while ((SN_SPI0->STAT & SPI_BUSY)")
    rx_wait = transfer.find("while ((SN_SPI0->STAT & SPI_RX_EMPTY)")
    rx_read = transfer.find("value = (uint8_t)(SN_SPI0->DATA & UINT32_C(0xFF));")
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
        "spi_response_read_retryable",
        "attempt < 2u",
        "irq_active(ep)",
        "frame_len - TRINITY_SPI_HEADER_SIZE",
        "g_spi_trace.response_capture_length = (uint16_t)captured",
        "spi_prime_pending_startup_get_info",
        "spi_bytes(NULL, NULL, 10u)",
        "g_spi_trace.context == SPI_TRACE_CONTEXT_STARTUP_PROBE",
        "g_spi_trace.command == TRINITY_SPI_GET_INFO",
        "rc = spi_prime_pending_startup_get_info(ep);",
        "rc = spi_capture_response_once(ep, response_len);",
    ):
        require(part07, token, "v0.7.9 mailbox recovery")
    forbid(part07, "spi_bytes(NULL, g_spi_buf, TRINITY_SPI_MAX_PACKET)", "response capture")

    prime = function_slice(
        part07,
        "static trinity_error_code_t spi_prime_pending_startup_get_info(",
        "static trinity_error_code_t spi_capture_response(",
        "startup GET_INFO mailbox prime",
    )
    if prime.count("spi_select(ep)") != 1 or prime.count("spi_end();") != 1:
        fail("startup prime must use exactly one selected-CS window")
    if prime.count("spi_bytes(NULL, NULL, 10u)") != 1:
        fail("startup prime must clock exactly ten discarded bytes")
    if "next_spi_txid" in prime or "trinity_spi_encode" in prime:
        fail("startup prime must not allocate a txid or encode a request")
    require(prime, "!irq_active(ep)", "startup prime IRQ guard")

    retry = function_slice(
        part07,
        "static trinity_error_code_t spi_capture_response(",
        "static trinity_error_code_t spi_drain_startup_mailbox(",
        "response recovery wrapper",
    )
    first_prime = retry.find("spi_prime_pending_startup_get_info(ep)")
    final_capture = retry.find("spi_capture_response_once(ep, response_len);", first_prime)
    if first_prime < 0 or final_capture < 0 or first_prime >= final_capture:
        fail("fresh-CS final capture must follow the ten-byte startup prime")
    if "endpoint_exchange" in retry or "next_spi_txid" in retry:
        fail("mailbox recovery must not issue another request")

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
    for token in ("full_probe_all", "full_refresh_all", "endpoint_exchange"):
        forbid(system_info, token, "side-effect-free system info")

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
    for token in ("class SpiDiagnosticTrace", "def spi_diagnostic(", "SPI_DIAGNOSTIC_HEADER_SIZE = 24"):
        require(client, token, "PC diagnostic decoder")
    for token in ('"spi-diag"', '"spi-first-failure"', "HostCommand.GET_FIRST_SPI_FAILURE", '"response_crc_match"'):
        require(cli, token, "PC diagnostic CLI")

    for token in ("test_probe_and_separate_p1_p2_retained_self_tests", "P1_KAT_TEST_MASK", "P2_KAT_TEST_MASK"):
        require(dual_test, token, "dual-SPI regression")
    for token in ("test_p2_get_info_trace_is_byte_exact", "response_capture_length, 22"):
        require(diag_test, token, "raw diagnostic regression")
    for token in ("test_startup_probe_failure_is_decoded_byte_exact", "test_startup_drain_reset_residue_is_not_latched_failure", "STARTUP_DRAIN_P1"):
        require(first_failure_test, token, "first-failure regression")

    if registry["pc"]["commands"].get("SPI_DIAGNOSTIC") != 7:
        fail("protocol registry does not assign SPI_DIAGNOSTIC=7")
    if registry["pc"]["commands"].get("GET_FIRST_SPI_FAILURE") != 8:
        fail("protocol registry does not assign GET_FIRST_SPI_FAILURE=8")

    require(uart_doc, "PC <-> SN32 UART PING HARDWARE: PASS", "UART qualification")
    require(uart_evidence, "PC <-> SN32 UART PING HARDWARE: PASS", "UART evidence")
    for text, label in ((failure_doc, "failure audit"), (failure_evidence, "failure evidence")):
        require(text, "DUAL-SPI clean-boot qualification: FAIL", label)
        require(text, "NOT PROVEN", label)

    for token in (
        "architecture_version = 0.7.9",
        "sn32_build_id         = 0x00070009",
        "selected-CS mailbox prime = 10 bytes discarded",
        "no new SPI request",
        "only context STARTUP_PROBE",
        "only command GET_INFO",
        "system-info remains local and side-effect free",
        "v0.7.9 exact Keil rebuild",
        "full_system_hardware_qualified:            false",
    ):
        require(gate_doc, token, "dual-SPI gate")

    for token in (
        'implementation_status = "V0_7_9_EVIDENCE_BACKED_STARTUP_MAILBOX_PRIME_SOURCE_READY"',
        'qualification_build_id = "0x00070009"',
        'qualification_architecture_version = "0.7.9"',
        'qualification_mailbox_prime_safety = "NO_NEW_REQUEST_NO_NEW_TXID_ONLY_WHILE_IRQ_ACTIVE_AND_KNOWN_GET_INFO_FRAME_LENGTH_22"',
        'qualification_system_info = "LOCAL_SIDE_EFFECT_FREE_IDENTITY_WITH_CACHED_ENDPOINT_BUILD_IDS"',
        'deploy_translation_unit_compile = "PENDING_CI_FOR_V0_7_9"',
    ):
        require(target, token, "SN32 target metadata")

    for token in (
        "sn32_architecture_version: 0.7.9",
        "sn32_build_id: 0x00070009",
        "startup_get_info_prime_length_10:",
        "startup_get_info_prime_no_new_request:",
        "startup_get_info_prime_no_new_txid:",
        "final_fresh_cs_capture_after_prime:",
        "system_info_side_effect_free:",
        "v0_7_9_exact_keil_rebuild:",
        "full_system_hardware_qualified: false",
    ):
        require(evidence_template, token, "dual-SPI evidence template")

    print("PASS: v0.7.9 identity and 100 kHz qualification profile are locked")
    print("PASS: normal exact-frame response capture and two-attempt retry remain locked")
    print("PASS: startup GET_INFO recovery primes exactly ten bytes without a new request or txid")
    print("PASS: final mailbox capture occurs under a fresh CS after the bounded prime")
    print("PASS: system-info remains local and side-effect free")
    print("NOTE: static PASS does not claim exact Keil rebuild, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
