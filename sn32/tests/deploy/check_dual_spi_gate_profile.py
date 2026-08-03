#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
PART00 = ROOT / "sn32/src/app/trinity_deploy_main_part_00.inc"
PART05 = ROOT / "sn32/src/app/trinity_deploy_main_part_05.inc"
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
    part05 = read(PART05)
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
    if version != (0, 7, 2):
        fail(f"single-CS diagnostic image must be version 0.7.2, got {version}")
    if macro(config, "TRINITY_DEPLOY_SPI_HZ") != 100_000:
        fail("dual-SPI qualification must remain at 100 kHz")
    if macro(config, "TRINITY_DEPLOY_SPI_CLKDIV") != 59:
        fail("12 MHz / 2 / (CLKDIV+1) must use CLKDIV 59")

    require(part00, "#define DEPLOY_BUILD_ID UINT32_C(0x00070002)", "deploy part 00")
    require(part00, "SPI qualification clock and CLKDIV disagree", "deploy part 00")
    require(part05, "SN_SPI0->CLKDIV_b.DIV = TRINITY_DEPLOY_SPI_CLKDIV;", "deploy part 05")
    if "SN_SPI0->CLKDIV_b.DIV = 5u" in part05:
        fail("old 1 MHz literal divider returned")

    for token in (
        "spi_trace_begin",
        "spi_drain_startup_mailbox",
        "spi_bytes(NULL, g_spi_buf, TRINITY_SPI_MAX_PACKET)",
        "The Primer mailbox restarts at byte zero",
        "if (issued_txid != NULL) *issued_txid = txid;",
    ):
        require(part07, token, "single-CS transport")
    if "spi_bytes(NULL, g_spi_buf, TRINITY_SPI_HEADER_SIZE)" in part07:
        fail("split response header read returned")
    for token in (
        "response_crc_received",
        "response_crc_calculated",
        "g_spi_rsp.transaction_id != txid",
    ):
        require(part08, token, "response trace validation")
    for token in (
        "handle_spi_diagnostic",
        "TRINITY_SPI_GET_INFO",
        "TRINITY_SPI_GET_STATUS",
        "request_fingerprint",
        "response_capture_length",
    ):
        require(part14, token, "diagnostic handler")
    require(part15, "case TRINITY_PC_SPI_DIAGNOSTIC:", "PC dispatch")
    require(part17, "spi_drain_startup_mailbox(&g_p1)", "startup drain")
    require(part17, "spi_drain_startup_mailbox(&g_p2)", "startup drain")
    for token in (
        "uint16_t issued_txid = 0u;",
        "((uint32_t)TRINITY_SPI_GET_INFO << 16)",
        "((uint32_t)TRINITY_SPI_GET_STATUS << 16)",
    ):
        require(controller, token, "controller target-txid telemetry")

    require(constants, "SPI_DIAGNOSTIC = 0x7", "PC constants")
    for token in (
        "class SpiDiagnosticTrace",
        "def spi_diagnostic(",
        "SPI_DIAGNOSTIC_HEADER_SIZE = 24",
        "request_bytes=payload[request_start:response_start]",
    ):
        require(client, token, "PC diagnostic decoder")
    for token in (
        '"spi-diag"',
        'dest="spi_command"',
        '"request_fingerprint"',
        '"response_crc_match"',
        '"irq_before_request"',
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

    if registry["pc"]["commands"].get("SPI_DIAGNOSTIC") != 7:
        fail("protocol registry does not assign SPI_DIAGNOSTIC=7")

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
        "SPI0 CLKDIV = 59",
        "P2 R13 uart_rx_i -> 3.3 V through 10 kΩ",
        "architecture_version = 0.7.2",
        "spi-diag --target p2 --command get-info",
    ):
        require(gate_doc, token, "dual-SPI gate")
    for token in (
        "repository_commit:",
        "sn32_build_id: 0x00070002",
        "spi_frequency_hz: 100000",
        "p2_uart_rx_r13_pulled_up_to_3v3_through_10k:",
        "p1_retained_kat_0x013e:",
        "p2_retained_kat_0x03e3:",
        "full_system_hardware_qualified: false",
    ):
        require(evidence_template, token, "dual-SPI evidence template")

    print("PASS: v0.7.1 clean-boot failure is recorded without claiming P2 failed first")
    print("PASS: v0.7.2 reads each Primer response under one CS assertion")
    print("PASS: startup mailbox drain and target command/txid telemetry are present")
    print("PASS: side-effect-free raw SPI diagnostic records bytes, CRC and IRQ state")
    print("PASS: dual-SPI qualification remains 100 kHz mode 0 with no broader claims")
    print("NOTE: static PASS does not claim exact Keil rebuild, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
