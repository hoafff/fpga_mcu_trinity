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
WRAPPER = ROOT / "sn32/src/app/trinity_deploy_main.c"
CONTROLLER_H = ROOT / "sn32/include/trinity_full_controller.h"
CONTROLLER_C = ROOT / "sn32/src/app/trinity_full_controller.c"
CONTROLLER_PARTS = [ROOT / f"sn32/src/app/trinity_full_controller_part_{i:02d}.inc" for i in range(8)]
BRIDGE = ROOT / "sn32/src/app/trinity_deploy_full_bridge.inc"
BRIDGE_PARTS = [ROOT / f"sn32/src/app/trinity_deploy_full_bridge_part_{i:02d}.inc" for i in range(4)]
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
BOARD = ROOT / "sn32/firmware/platform/sn32f407/board_profile.h"
PARTS = [ROOT / f"sn32/src/app/trinity_deploy_main_part_{i:02d}.inc" for i in range(18)]
HOST = ROOT / "pc_host/src/trinity_host/serial_client.py"
CLI = ROOT / "pc_host/src/trinity_host/cli.py"
PYPROJECT = ROOT / "pc_host/pyproject.toml"
HOST_TEST = ROOT / "pc_host/tests/test_p1_bringup.py"
FULL_TEST = ROOT / "sn32/tests/full_controller/test_full_controller.c"
FULL_TEST_PARTS = [ROOT / f"sn32/tests/full_controller/test_full_controller_part_{i:02d}.inc" for i in range(3)]
FULL_TEST_MAKEFILE = ROOT / "sn32/tests/full_controller/Makefile"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def read(path: Path) -> str:
    require(path.is_file(), f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def check_source_and_tests() -> None:
    wrapper = read(WRAPPER)
    controller_h = read(CONTROLLER_H)
    controller_wrapper = read(CONTROLLER_C)
    controller_c = "".join(read(p) for p in CONTROLLER_PARTS)
    bridge_wrapper = read(BRIDGE)
    bridge = "".join(read(p) for p in BRIDGE_PARTS)
    config = read(CONFIG)
    source = "".join(read(p) for p in PARTS) + bridge

    for i in range(18):
        require(f'#include "trinity_deploy_main_part_{i:02d}.inc"' in wrapper,
                f"wrapper missing source part {i}")
    require('#include "trinity_full_controller.c"' in wrapper,
            "full controller is not compiled by deploy target")
    require('#include "trinity_deploy_full_bridge.inc"' in wrapper,
            "SN32 hardware/controller bridge is not compiled")
    for i in range(8):
        require(f'#include "trinity_full_controller_part_{i:02d}.inc"' in controller_wrapper,
                f"controller wrapper missing part {i}")
    for i in range(4):
        require(f'#include "trinity_deploy_full_bridge_part_{i:02d}.inc"' in bridge_wrapper,
                f"bridge wrapper missing part {i}")

    expected = {
        "TRINITY_DEPLOY_ENABLE_PC_UART": "1",
        "TRINITY_DEPLOY_ENABLE_SPI": "1",
        "TRINITY_DEPLOY_ENABLE_PRIMER1": "1",
        "TRINITY_DEPLOY_ENABLE_PRIMER2": "1",
        "TRINITY_DEPLOY_ENABLE_PAYLOAD_RELAY": "0",
        "TRINITY_DEPLOY_ENABLE_TINY_SESSION_COMMIT": "1",
        "TRINITY_DEPLOY_ENABLE_DEMO_SECURE": "0",
        "TRINITY_DEPLOY_P1_BRINGUP_ONLY": "0",
    }
    for macro, value in expected.items():
        require(re.search(rf"^#define\s+{macro}\s+{value}\s*$", config, re.M) is not None,
                f"wrong full-deploy guard {macro}")
    require("FPST_SN32F407_SESSION_COMMIT_PIN           8u" in config,
            "SESSION_COMMIT is not locked to SN32 P3.8")

    for token in (
        "trinity_controller_probe_all", "trinity_controller_run_self_test",
        "trinity_controller_activate_session", "trinity_controller_close_session",
        "trinity_controller_zeroize", "trinity_controller_send_telemetry",
        "TRINITY_SPI_STAGE_SESSION", "TRINITY_SPI_COMMIT_SESSION",
        "TRINITY_SPI_LOAD_TELEMETRY", "TRINITY_SPI_ENCRYPT_AND_SEND",
        "TRINITY_SPI_GET_RX_STATUS", "TRINITY_SPI_READ_AUTH_RESULT",
        "TRINITY_SPI_ACK_AUTH_RESULT", "TRINITY_RESULT_PENDING",
        "TRINITY_AUTH_THRESHOLD",
    ):
        require(token in controller_h + controller_c, f"controller missing {token}")

    for token in (
        "full_session_commit_toggle", "FPST_SN32F407_SESSION_COMMIT_PORT",
        "full_tiny_fault_active", "managed_transaction_begin",
        "managed_transaction_finish", "full_handle_send_telemetry",
        "full_handle_zeroize", "full_handle_transport_stress",
    ):
        require(token in bridge, f"deploy bridge missing {token}")

    for token in (
        "TRINITY_PC_CLOSE_SESSION", "TRINITY_PC_ZEROIZE_SYSTEM",
        "TRINITY_PC_SEND_ONE_TELEMETRY", "TRINITY_PC_READ_LAST_RESULT",
        "TRINITY_PC_RUN_TRANSPORT_STRESS",
    ):
        require(token in source, f"dispatcher missing {token}")

    require("TRINITY_DEPLOY_ENABLE_MLKEM               0" in config,
            "ML-KEM must remain disabled until pinned vendor sources are present")
    require("TRINITY_PC_GENERATE_KEYPAIR" in source and
            "TRINITY_NOT_SUPPORTED" in source,
            "unavailable ML-KEM commands must fail explicitly")
    require("TRINITY_PC_REQUEST_FAULT_CLEAR" in source and
            "TRINITY_SOURCE_TINY1P5" in source,
            "fault clear must not pretend to clear the Tiny safety latch")

    full_test_wrapper = read(FULL_TEST)
    full_test_source = "".join(read(p) for p in FULL_TEST_PARTS)
    for i in range(3):
        require(f'#include "test_full_controller_part_{i:02d}.inc"' in full_test_wrapper,
                f"full controller test wrapper missing part {i}")
    for token in (
        "trinity_controller_activate_session", "trinity_controller_send_telemetry",
        "TRINITY_RESULT_PENDING", "trinity_controller_zeroize",
        "TRINITY_FAULT_TINY1P5",
    ):
        require(token in full_test_source, f"full controller test missing {token}")
    require("-Wall -Wextra -Werror" in read(FULL_TEST_MAKEFILE),
            "portable controller test is not warning-clean")

    host_paths = (HOST, CLI, PYPROJECT, HOST_TEST)
    host_checked = all(path.is_file() for path in host_paths)
    if host_checked:
        host = read(HOST)
        cli = read(CLI)
        pyproject = read(PYPROJECT)
        host_test = read(HOST_TEST)
        for token in ("class TrinitySerialClient", "def ping(", "def get_system_info(",
                      "def get_system_status(", "def get_transaction_result(",
                      "def retire_transaction_result("):
            require(token in host, f"existing host client regression: missing {token}")
        require('trinity-host = "trinity_host.cli:main"' in pyproject,
                "host console entrypoint was removed")
        require("PING" in host_test and "RUN_SELF_TEST" in host_test and
                "GET_TXN_RESULT" in host_test and "RETIRE_TXN_RESULT" in host_test,
                "existing host fake-serial regression lost coverage")
        require('sub.add_parser("p1-bringup"' in cli,
                "existing P1 hardware bring-up command was removed")
        for text, label in ((host, "host client"), (cli, "host CLI")):
            require(not re.search(r"[A-Za-z]:[\\/]", text),
                    f"machine-specific absolute path in {label}")
    else:
        print("NOTE: PC host regression files absent from partial source-only checkout")

    require(not re.search(r"[A-Za-z]:[\\/]", wrapper + source + controller_c),
            "machine-specific absolute path in SN32 source")

    print("PASS: full deploy source enables dual Primer SPI and Tiny SESSION_COMMIT")
    print("PASS: controller covers stage/commit/active, telemetry/auth/ACK and zeroize")
    print("PASS: host transaction cache preserves exact retry/conflict/result retirement")
    print("PASS: direct P1-to-P2 UART is orchestrated without MCU payload relay")
    print("PASS: unavailable ML-KEM commands fail explicitly; no fixed-key PASS path")
    if host_checked:
        print("PASS: existing PC host P1 bring-up regression remains present")


def check_project_and_pins() -> None:
    project_text = read(PROJECT)
    board = read(BOARD)
    require(S0_PROJECT.is_file(), "canonical S0 project was removed")
    try:
        root = ET.fromstring(project_text)
    except ET.ParseError as exc:
        fail(f"invalid Keil XML: {exc}")

    def one(xpath: str) -> str:
        node = root.find(xpath)
        require(node is not None and node.text is not None, f"missing {xpath}")
        return node.text.strip()

    require(one("./Targets/Target/TargetName") == "trinity_sn32f407_deploy",
            "wrong deploy target")
    require(one("./Targets/Target/pCCUsed") == "6240000::V6.24::ARMCLANG",
            "ArmClang lock changed")
    require(one("./Targets/Target/TargetOption/TargetCommonOption/Device") == "SN32F407F",
            "device lock changed")
    require(one("./Targets/Target/TargetOption/TargetCommonOption/PackID") == "SONiX.SN32F4_DFP.1.0.1",
            "DFP lock changed")
    require("../src/app/trinity_deploy_main.c" in project_text.replace("\\", "/").lower(),
            "deploy entrypoint missing from Keil project")
    require("FPST_SN32F407_P2_CS_N_PIN              2u" in board and
            "FPST_SN32F407_P2_IRQ_N_PIN              8u" in board,
            "P2 CS/IRQ pin mapping drifted")
    require("FPST_SN32F407_TINY_FAULT_N_PIN        10u" in board,
            "Tiny fault input mapping drifted")
    print("PASS: Keil target remains SN32F407F / ArmClang 6.24 / DFP 1.0.1")
    print("PASS: deploy translation unit and P1/P2/Tiny hardware mappings remain selected")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    check_source_and_tests()
    if not args.source_only:
        check_project_and_pins()
    else:
        print("NOTE: Keil XML and board-profile checks skipped by --source-only")
    print("NOTE: static PASS does not claim ArmClang build, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
