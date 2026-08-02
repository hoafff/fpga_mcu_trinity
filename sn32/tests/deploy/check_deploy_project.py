#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "sn32/keil/trinity_sn32f407_deploy.uvprojx"
S0_PROJECT = ROOT / "sn32/keil/trinity_sn32f407.uvprojx"
SOURCE = ROOT / "sn32/src/app/trinity_deploy_main.c"
SOURCE_PARTS = [ROOT / f"sn32/src/app/trinity_deploy_main_part_{index:02d}.inc" for index in range(18)]
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
BOARD = ROOT / "sn32/firmware/platform/sn32f407/board_profile.h"
HOST = ROOT / "pc_host/src/trinity_host/serial_client.py"
CLI = ROOT / "pc_host/src/trinity_host/cli.py"
PYPROJECT = ROOT / "pc_host/pyproject.toml"
HOST_TEST = ROOT / "pc_host/tests/test_p1_bringup.py"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def read(path: Path) -> str:
    require(path.is_file(), f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require_source_and_host() -> None:
    wrapper = read(SOURCE)
    for index, part in enumerate(SOURCE_PARTS):
        require(f'`include "trinity_deploy_main_part_{index:02d}.inc"' not in wrapper, "SystemVerilog include syntax used in C wrapper")
        require(f'#include "trinity_deploy_main_part_{index:02d}.inc"' in wrapper, f"missing deploy source part {index}")
    source = "".join(read(part) for part in SOURCE_PARTS)
    config = read(CONFIG)
    host = read(HOST)
    cli = read(CLI)
    pyproject = read(PYPROJECT)
    host_test = read(HOST_TEST)

    flags = {
        "TRINITY_DEPLOY_ENABLE_PC_UART": "1",
        "TRINITY_DEPLOY_ENABLE_SPI": "1",
        "TRINITY_DEPLOY_ENABLE_PRIMER1": "1",
        "TRINITY_DEPLOY_ENABLE_MLKEM": "0",
        "TRINITY_DEPLOY_ENABLE_PAYLOAD_RELAY": "0",
        "TRINITY_DEPLOY_ENABLE_TINY_SESSION_COMMIT": "0",
        "TRINITY_DEPLOY_ENABLE_DEMO_SECURE": "0",
        "TRINITY_DEPLOY_P1_BRINGUP_ONLY": "1",
    }
    for macro, value in flags.items():
        require(
            re.search(rf"^#define\s+{macro}\s+{value}\s*$", config, re.M)
            is not None,
            f"wrong deploy guard {macro}",
        )

    for token in (
        "SN_SPI0->CTRL1 = 0u",
        "SN_SPI0->CLKDIV_b.DIV = 5u",
        "endpoint_exchange(",
        "TRINITY_SPI_GET_INFO",
        "TRINITY_SPI_GET_STATUS",
        "TRINITY_SPI_RUN_SELF_TEST",
        "TRINITY_SPI_GET_TXN_RESULT",
        "TRINITY_SPI_RETIRE_TXN_RESULT",
        "request_fingerprint",
        "host_txid",
        "target_txid",
        "P1_SELF_TEST_RESULT_MAX",
        "g_spi_rsp.payload[8] != 0u",
        "g_spi_rsp.payload[9] != 0u",
    ):
        require(token in source, f"deploy source missing {token}")

    require(
        "target_payload[0] = req->payload[2];" in source
        and "target_payload[1] = req->payload[3];" in source
        and "target_payload[2] = 0u;" in source
        and "target_payload[3] = 0u;" in source,
        "PC RUN_SELF_TEST is not mapped to P1 mask||reserved payload",
    )
    require(
        "g_pc_rsp.payload_length = (uint16_t)(8u + g_host_txn.result_length);"
        in source,
        "P1 retained result is not translated to PC transaction result",
    )
    require(
        "if (!g_host_txn.valid" in source
        and "TRINITY_RESULT_NOT_READY" in source,
        "unknown host transaction result is not rejected",
    )
    require(
        "if (!g_host_txn.valid || query_txid != g_host_txn.host_txid) {\n"
        "        (void)response_send();"
        in source,
        "RETIRE_TXN_RESULT is not idempotent for unknown/already-retired IDs",
    )
    require(
        "if (!g_host_txn.valid &&" in source,
        "periodic probe can interfere with an outstanding retained transaction",
    )

    forbidden_source = (
        "TRINITY_SPI_ENCRYPT_AND_SEND",
        "TRINITY_SPI_STAGE_SESSION",
        "TRINITY_SPI_COMMIT_SESSION",
        "TRINITY_PC_SEND_ONE_TELEMETRY",
    )
    for token in forbidden_source:
        require(token not in source, f"out-of-scope command leaked into P1 bring-up firmware: {token}")

    for token in (
        "class TrinitySerialClient",
        "def ping(",
        "def get_system_info(",
        "def get_system_status(",
        "def start_p1_self_test(",
        "def get_transaction_result(",
        "def retire_transaction_result(",
        "def run_p1_bringup(",
    ):
        require(token in host, f"host client missing {token}")
    for token in (
        'sub.add_parser("ping"',
        'sub.add_parser("p1-info"',
        'sub.add_parser("p1-status"',
        'sub.add_parser("p1-self-test-start"',
        'sub.add_parser("txn-result"',
        'sub.add_parser("txn-retire"',
        'sub.add_parser("p1-bringup"',
        '"step": "P1_CONTROL_PLANE_SELF_TEST"',
    ):
        require(token in cli, f"host CLI missing {token}")
    require(
        'trinity-host = "trinity_host.cli:main"' in pyproject,
        "console entrypoint is not installed",
    )
    require(
        "PING" in host_test
        and "GET_SYSTEM_INFO" in host_test
        and "GET_SYSTEM_STATUS" in host_test
        and "RUN_SELF_TEST" in host_test
        and "GET_TXN_RESULT" in host_test
        and "RETIRE_TXN_RESULT" in host_test,
        "fake-serial test does not cover the required command sequence",
    )
    require(
        'b"\\x02\\x02\\x00\\x3E"' in host_test,
        "self-test target/profile/mask wire payload is not locked by test",
    )

    for text, label in ((wrapper + source, "SN32 source"), (host, "host client"), (cli, "host CLI")):
        require(
            not re.search(r"[A-Za-z]:[\\/]", text),
            f"absolute Windows path in {label}",
        )

    print("PASS: P1-only SN32 control-plane source implements GET_INFO/GET_STATUS and retained self-test lifecycle")
    print("PASS: host and target transaction IDs are explicitly mapped and retirement is idempotent")
    print("PASS: PC CLI locks PING -> INFO -> STATUS -> RUN -> GET -> RETIRE without session/encryption/P2")
    print("PASS: source/config/host files contain no machine-specific absolute path")


def require_project_and_pins() -> None:
    project_text = read(PROJECT)
    board = read(BOARD)
    require(S0_PROJECT.is_file(), "canonical S0 project was removed")
    try:
        root = ET.fromstring(project_text)
    except ET.ParseError as exc:
        fail(f"invalid deploy project XML: {exc}")

    def one(xpath: str) -> str:
        node = root.find(xpath)
        require(node is not None and node.text is not None, f"missing XML field {xpath}")
        return node.text.strip()

    require(one("./Targets/Target/TargetName") == "trinity_sn32f407_deploy", "wrong deploy target name")
    require(one("./Targets/Target/pCCUsed") == "6240000::V6.24::ARMCLANG", "ArmClang 6.24 lock changed")
    require(one("./Targets/Target/TargetOption/TargetCommonOption/Device") == "SN32F407F", "device lock changed")
    require(one("./Targets/Target/TargetOption/TargetCommonOption/PackID") == "SONiX.SN32F4_DFP.1.0.1", "DFP lock changed")
    define = one("./Targets/Target/TargetOption/TargetArmAds/Cads/VariousControls/Define")
    require(define == "TRINITY_DEPLOY_TARGET=1", "deploy define drifted")

    paths = [(node.text or "").replace("\\", "/").lower() for node in root.findall(".//FilePath")]
    expected_c = {
        "../src/app/trinity_deploy_main.c",
        "../firmware/platform/sn32f407/fpst_sn32f407_p010_guard.c",
        "../src/trinity_protocol_common.c",
        "../src/trinity_pc_protocol.c",
        "../src/trinity_spi_protocol.c",
    }
    require({path for path in paths if path.endswith(".c")} == expected_c, "unexpected deploy C source set")
    require(not re.search(r"(?:^|[>\s])(?:[A-Za-z]:\\|[A-Za-z]:/)", project_text), "absolute path in Keil project")

    for token in (
        "FPST_SN32F407_SPI_SCK_PIN             0u",
        "FPST_SN32F407_SPI_MISO_PIN             1u",
        "FPST_SN32F407_SPI_MOSI_PIN             2u",
        "FPST_SN32F407_P1_CS_N_PIN              1u",
        "FPST_SN32F407_P1_IRQ_N_PIN              3u",
        "FPST_SN32F407_UART_TX_PIN               1u",
        "FPST_SN32F407_UART_RX_PIN               2u",
    ):
        require(token in board, f"board profile pin drift: {token}")

    print("PASS: Keil deploy project remains SN32F407F / ArmClang 6.24 / DFP 1.0.1 with the exact source set")
    print("PASS: board profile retains P1 SPI and PC UART pin mappings")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="check modified source/host files when a full repository checkout is unavailable",
    )
    args = parser.parse_args()
    require_source_and_host()
    if not args.source_only:
        require_project_and_pins()
    else:
        print("NOTE: project XML and board-profile checks skipped by explicit --source-only")
    print("NOTE: static checks do not replace the exact ArmClang build and SN32 flash log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
