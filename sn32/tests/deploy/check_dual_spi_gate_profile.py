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
    gate_doc = read(GATE_DOC)
    evidence = read(EVIDENCE)
    registry = json.loads(read(REGISTRY))

    version = (
        macro(config, "TRINITY_DEPLOY_VERSION_MAJOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_MINOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_PATCH"),
    )
    if version != (0, 7, 10):
        fail(f"byte-FIFO image must be v0.7.10, got {version}")
    if macro(config, "TRINITY_DEPLOY_SPI_HZ") != 100_000:
        fail("qualification SPI clock must remain 100 kHz")
    if macro(config, "TRINITY_DEPLOY_SPI_CLKDIV") != 59:
        fail("12 MHz qualification clock must use CLKDIV=59")

    require(p00, "#define DEPLOY_BUILD_ID UINT32_C(0x0007000A)", "identity")
    require(p00, "SPI qualification clock and CLKDIV disagree", "clock lock")

    for token in (
        "SPI_RESPONSE_SETTLE_MS = 15u",
        "SPI_STARTUP_WARMUP_MS = 2000u",
        "g_spi_first_failure",
        "g_spi_startup_residue",
    ):
        require(p01, token, "timing/telemetry")

    for token in (
        "SN_SPI0->CTRL0_b.DL = 7u;",
        "SN_SPI0->FIFO_TH = (1u << 31);",
        "16 x 8-bit FIFO organization",
        "SN_SPI0->CLKDIV_b.DIV = TRINITY_DEPLOY_SPI_CLKDIV;",
        "SN_SPI0->CTRL1 = 0u;",
        "SN_SPI0->CTRL0_b.SPIEN = 1u;",
    ):
        require(p05, token, "SPI init")
    forbid(p05, "SN_SPI0->FIFO_TH = 0u;", "SPI init")
    forbid(p05, "Keep the optional threshold extension disabled", "SPI init")

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
        transfer.find("SN_SPI0->DATA & UINT32_C(0xFF)"),
    ]
    if min(order) < 0 or order != sorted(order):
        fail("SPI byte order must be TX -> BUSY clear -> RX ready -> DATA[7:0]")

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
    require(capture, "g_spi_trace.response_capture_length", "response telemetry")

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
    forbid(p07, "trinity_spi_encode", "response-only recovery")

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
        "serialize_spi_trace",
        "trace->spi_status",
    ):
        require(p14, token, "diagnostic handlers")
    require(p15, "case TRINITY_PC_SPI_DIAGNOSTIC:", "PC dispatch")
    require(p15, "case TRINITY_PC_GET_FIRST_SPI_FAILURE:", "PC dispatch")

    require(constants, "SPI_DIAGNOSTIC = 0x7", "PC constants")
    require(constants, "GET_FIRST_SPI_FAILURE = 0x8", "PC constants")
    require(client, "class SpiDiagnosticTrace", "PC decoder")
    require(client, "def spi_diagnostic(", "PC decoder")
    require(cli, '"spi-first-failure"', "PC CLI")

    if registry["pc"]["commands"].get("SPI_DIAGNOSTIC") != 7:
        fail("registry SPI_DIAGNOSTIC must remain 7")
    if registry["pc"]["commands"].get("GET_FIRST_SPI_FAILURE") != 8:
        fail("registry GET_FIRST_SPI_FAILURE must remain 8")

    for token in (
        "architecture_version = 0.7.10",
        "sn32_build_id         = 0x0007000A",
        "FIFO_TH.NEW_TH_EN = 1",
        "16 x 8-bit",
        "remove disproven startup mailbox prime",
        "system-info remains local and side-effect free",
        "full_system_hardware_qualified:            false",
    ):
        require(gate_doc, token, "dual-SPI gate")

    for token in (
        'implementation_status = "V0_7_10_16X8_SPI_FIFO_SOURCE_READY"',
        'qualification_build_id = "0x0007000A"',
        'qualification_architecture_version = "0.7.10"',
        'qualification_fifo_organization = "NEW_TH_EN_1_16X8_BYTE_FIFO"',
        'qualification_startup_prime = "REMOVED_DISPROVEN_BY_V0_7_9_HARDWARE"',
        'deploy_translation_unit_compile = "PENDING_CI_FOR_V0_7_10"',
    ):
        require(target, token, "target metadata")

    for token in (
        "sn32_architecture_version: 0.7.10",
        "sn32_build_id: 0x0007000A",
        "spi_fifo_organization: 16_X_8_BIT",
        "new_th_en_16x8_fifo_enabled:",
        "startup_mailbox_prime_removed:",
        "v0_7_10_exact_keil_rebuild:",
        "full_system_hardware_qualified: false",
    ):
        require(evidence, token, "evidence template")

    print("PASS: v0.7.10 identity and 100 kHz profile are locked")
    print("PASS: NEW_TH_EN selects the 16 x 8-bit FIFO for byte traffic")
    print("PASS: disproven startup mailbox priming is absent")
    print("PASS: reset, exact-frame capture, retry and diagnostics remain locked")
    print("NOTE: static PASS does not claim Keil build, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
