#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
PART00 = ROOT / "sn32/src/app/trinity_deploy_main_part_00.inc"
PART05 = ROOT / "sn32/src/app/trinity_deploy_main_part_05.inc"
CLIENT = ROOT / "pc_host/src/trinity_host/serial_client.py"
CLI = ROOT / "pc_host/src/trinity_host/cli.py"
TEST = ROOT / "pc_host/tests/test_dual_spi_bringup.py"
GATE_DOC = ROOT / "sn32/docs/SN32_DUAL_SPI_HARDWARE_QUALIFICATION_NEXT_GATE.md"
UART_DOC = ROOT / "sn32/docs/PC_TO_SN32_UART_PING_HARDWARE_QUALIFICATION_2026-08-03.md"
UART_EVIDENCE = ROOT / "sn32/hardware/pc_uart_ping/evidence/pc_uart_ping_2026-08-03.txt"
EVIDENCE_TEMPLATE = (
    ROOT
    / "sn32/hardware/dual_spi_control_plane/evidence/run_manifest_TEMPLATE.txt"
)


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
    client = read(CLIENT)
    cli = read(CLI)
    test = read(TEST)
    gate_doc = read(GATE_DOC)
    uart_doc = read(UART_DOC)
    uart_evidence = read(UART_EVIDENCE)
    evidence_template = read(EVIDENCE_TEMPLATE)

    if (
        macro(config, "TRINITY_DEPLOY_VERSION_MAJOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_MINOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_PATCH"),
    ) != (0, 7, 1):
        fail("dual-SPI qualification image must be version 0.7.1")
    if macro(config, "TRINITY_DEPLOY_SPI_HZ") != 100_000:
        fail("first dual-SPI qualification must remain at 100 kHz")
    if macro(config, "TRINITY_DEPLOY_SPI_CLKDIV") != 59:
        fail("12 MHz / 2 / (CLKDIV+1) must use CLKDIV 59")

    require(part00, "#define DEPLOY_BUILD_ID UINT32_C(0x00070001)", "deploy part 00")
    require(part00, "SPI qualification clock and CLKDIV disagree", "deploy part 00")
    require(part05, "SN_SPI0->CLKDIV_b.DIV = TRINITY_DEPLOY_SPI_CLKDIV;", "deploy part 05")
    if "SN_SPI0->CLKDIV_b.DIV = 5u" in part05:
        fail("old 1 MHz literal divider returned")

    for token in (
        "architecture_patch: int",
        "P1_KAT_TEST_MASK = 0x013E",
        "P2_KAT_TEST_MASK = 0x03E3",
        "def run_dual_spi_bringup(",
        "EXPECTED_P1_BUILD_ID = 0x50310001",
        "EXPECTED_P2_BUILD_ID = 0x50320001",
    ):
        require(client, token, "PC serial client")
    for token in (
        '"dual-spi-bringup"',
        '"SN32_DUAL_SPI_CONTROL_PLANE"',
        '"architecture_version"',
    ):
        require(cli, token, "PC CLI")
    for token in (
        "test_probe_and_separate_p1_p2_retained_self_tests",
        "P1_KAT_TEST_MASK",
        "P2_KAT_TEST_MASK",
        "architecture_patch, 1",
    ):
        require(test, token, "dual-SPI regression")

    require(uart_doc, "PC <-> SN32 UART PING HARDWARE: PASS", "UART qualification")
    require(uart_evidence, "PC <-> SN32 UART PING HARDWARE: PASS", "UART evidence")
    for token in (
        "SN32 -> P1/P2 DUAL-SPI CONTROL PLANE HARDWARE: PASS",
        "secure_enable_i  -> GND",
        "SPI0 CLKDIV = 59",
        "P2 R13 uart_rx_i -> 3.3 V through 10 kΩ",
    ):
        require(gate_doc, token, "dual-SPI gate")
    for token in (
        "repository_commit:",
        "sn32_build_id: 0x00070001",
        "spi_frequency_hz: 100000",
        "p2_uart_rx_r13_pulled_up_to_3v3_through_10k:",
        "p1_retained_kat_0x013e:",
        "p2_retained_kat_0x03e3:",
        "full_system_hardware_qualified: false",
    ):
        require(evidence_template, token, "dual-SPI evidence template")

    print("PASS: scoped PC-to-SN32 UART evidence is locked without broader claims")
    print("PASS: v0.7.1 dual-SPI gate is fixed at 100 kHz mode 0 with build ID 0x00070001")
    print("PASS: PC host probes P1/P2 and runs separate retained KAT self-tests")
    print("PASS: P2 UART RX is held idle high while the direct payload wire is isolated")
    print("PASS: dual-SPI evidence manifest records identities, wiring and non-claims")
    print("NOTE: static PASS does not claim a current exact Keil rebuild or dual-SPI hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
