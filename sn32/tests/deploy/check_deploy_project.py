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
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
BOARD = ROOT / "sn32/firmware/platform/sn32f407/board_profile.h"
PARTS = [ROOT / f"sn32/src/app/trinity_deploy_main_part_{i:02d}.inc" for i in range(18)]
CONTROLLER_H = ROOT / "sn32/include/trinity_full_controller.h"
CONTROLLER_C = ROOT / "sn32/src/app/trinity_full_controller.c"
CONTROLLER_PARTS = [ROOT / f"sn32/src/app/trinity_full_controller_part_{i:02d}.inc" for i in range(8)]
BRIDGE = ROOT / "sn32/src/app/trinity_deploy_full_bridge.inc"
BRIDGE_PARTS = [ROOT / f"sn32/src/app/trinity_deploy_full_bridge_part_{i:02d}.inc" for i in range(5)]
CRYPTO_H = ROOT / "sn32/include/trinity_deploy_crypto.h"
CRYPTO_C = ROOT / "sn32/src/app/trinity_deploy_crypto.c"
CRYPTO_PARTS = [ROOT / f"sn32/src/app/trinity_deploy_crypto_part_{i:02d}.inc" for i in range(2)]
MLKEM_H = ROOT / "sn32/include/trinity_mlkem.h"
MLKEM_C = ROOT / "sn32/src/trinity_mlkem.c"
MLKEM_BACKEND = ROOT / "sn32/src/trinity_mlkem_backend.c"
FIPS_BRIDGE = ROOT / "sn32/src/trinity_fips202_bridge.c"
VENDOR_LOCK = ROOT / "sn32/third_party/mlkem-native/VENDOR.lock"
FULL_TEST = ROOT / "sn32/tests/full_controller/test_full_controller.c"
FULL_TEST_PARTS = [ROOT / f"sn32/tests/full_controller/test_full_controller_part_{i:02d}.inc" for i in range(3)]
FULL_TEST_MAKEFILE = ROOT / "sn32/tests/full_controller/Makefile"
CRYPTO_TEST = ROOT / "sn32/tests/deploy_crypto/test_deploy_crypto.c"
CRYPTO_TEST_MAKEFILE = ROOT / "sn32/tests/deploy_crypto/Makefile"
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


def require_tokens(text: str, tokens: tuple[str, ...], label: str) -> None:
    for token in tokens:
        require(token in text, f"{label} missing {token}")


def check_source_and_tests() -> None:
    wrapper = read(WRAPPER)
    config = read(CONFIG)
    main_source = "".join(read(path) for path in PARTS)
    controller_wrapper = read(CONTROLLER_C)
    controller = read(CONTROLLER_H) + "".join(read(path) for path in CONTROLLER_PARTS)
    bridge_wrapper = read(BRIDGE)
    bridge = "".join(read(path) for path in BRIDGE_PARTS)
    crypto_wrapper = read(CRYPTO_C)
    crypto = read(CRYPTO_H) + "".join(read(path) for path in CRYPTO_PARTS)
    mlkem = read(MLKEM_H) + read(MLKEM_C) + read(MLKEM_BACKEND) + read(FIPS_BRIDGE)
    vendor_lock = read(VENDOR_LOCK)
    combined = wrapper + main_source + controller + bridge + crypto + mlkem

    require_tokens(
        wrapper,
        tuple(f'#include "trinity_deploy_main_part_{i:02d}.inc"' for i in range(18)),
        "deploy wrapper",
    )
    require('#include "trinity_full_controller.c"' in wrapper,
            "full controller is not compiled by the deploy translation unit")
    require('#include "trinity_deploy_crypto.c"' in wrapper,
            "deploy crypto lifecycle is not compiled")
    require('#include "trinity_deploy_full_bridge.inc"' in wrapper,
            "hardware/controller bridge is not compiled")
    require_tokens(
        controller_wrapper,
        tuple(f'#include "trinity_full_controller_part_{i:02d}.inc"' for i in range(8)),
        "controller wrapper",
    )
    require_tokens(
        bridge_wrapper,
        tuple(f'#include "trinity_deploy_full_bridge_part_{i:02d}.inc"' for i in range(5)),
        "bridge wrapper",
    )
    require_tokens(
        crypto_wrapper,
        tuple(f'#include "trinity_deploy_crypto_part_{i:02d}.inc"' for i in range(2)),
        "crypto wrapper",
    )

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
    require("#ifndef TRINITY_DEPLOY_ENABLE_MLKEM" in config and
            re.search(r"^#define\s+TRINITY_DEPLOY_ENABLE_MLKEM\s+0\s*$", config, re.M),
            "ML-KEM default must remain off until the pinned vendor target is selected")
    require("FPST_SN32F407_SESSION_COMMIT_PORT          3u" in config and
            "FPST_SN32F407_SESSION_COMMIT_PIN           8u" in config,
            "SESSION_COMMIT is not locked to SN32 P3.8")

    require_tokens(
        controller,
        (
            "trinity_controller_probe_all", "trinity_controller_run_self_test",
            "trinity_controller_activate_session", "trinity_controller_close_session",
            "trinity_controller_zeroize", "trinity_controller_send_telemetry",
            "TRINITY_SPI_STAGE_SESSION", "TRINITY_SPI_COMMIT_SESSION",
            "TRINITY_SPI_LOAD_TELEMETRY", "TRINITY_SPI_ENCRYPT_AND_SEND",
            "TRINITY_SPI_GET_RX_STATUS", "TRINITY_SPI_READ_AUTH_RESULT",
            "TRINITY_SPI_ACK_AUTH_RESULT", "TRINITY_RESULT_PENDING",
            "TRINITY_AUTH_THRESHOLD",
        ),
        "full controller",
    )
    require_tokens(
        bridge,
        (
            "full_session_commit_toggle", "full_tiny_fault_active",
            "full_contain_tiny_fault", "trinity_deploy_crypto_zeroize",
            "managed_transaction_begin", "managed_transaction_finish",
            "full_handle_generate_keypair", "full_handle_create_session",
            "full_handle_send_telemetry", "full_handle_zeroize",
            "full_handle_transport_stress",
        ),
        "deploy bridge",
    )
    require_tokens(
        crypto + mlkem,
        (
            "trinity_deploy_crypto_generate_keypair",
            "trinity_deploy_crypto_create_session",
            "trinity_mlkem512_keygen_deterministic",
            "trinity_mlkem512_encaps_deterministic",
            "trinity_mlkem512_decaps",
            "trinity_kdf_derive_session",
            "trinity_deploy_crypto_zeroize",
            "trinity_sha3_256", "trinity_shake256",
        ),
        "deploy crypto",
    )
    require_tokens(
        main_source,
        (
            "TRINITY_PC_GENERATE_KEYPAIR", "TRINITY_PC_CREATE_SESSION",
            "TRINITY_PC_CLOSE_SESSION", "TRINITY_PC_ZEROIZE_SYSTEM",
            "TRINITY_PC_SEND_ONE_TELEMETRY", "TRINITY_PC_READ_LAST_RESULT",
            "TRINITY_PC_RUN_TRANSPORT_STRESS", "full_contain_tiny_fault",
        ),
        "host dispatcher/main loop",
    )
    require("req->payload[0] == 2u" in bridge and "TRINITY_NOT_SUPPORTED" in bridge,
            "DEMO_SECURE must fail explicitly until entropy qualification")
    require("TRINITY_PC_REQUEST_FAULT_CLEAR" in main_source and
            "TRINITY_SOURCE_TINY1P5" in main_source,
            "fault clear must not pretend to clear the Tiny safety latch")
    require("repository=https://github.com/pq-code-package/mlkem-native" in vendor_lock and
            "commit=048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa" in vendor_lock,
            "ML-KEM vendor lock drifted")

    full_test_wrapper = read(FULL_TEST)
    full_test_source = "".join(read(path) for path in FULL_TEST_PARTS)
    require_tokens(
        full_test_wrapper,
        tuple(f'#include "test_full_controller_part_{i:02d}.inc"' for i in range(3)),
        "controller test wrapper",
    )
    require_tokens(
        full_test_source,
        (
            "trinity_controller_activate_session", "trinity_controller_send_telemetry",
            "TRINITY_RESULT_PENDING", "trinity_controller_zeroize",
            "TRINITY_FAULT_TINY1P5",
        ),
        "controller test",
    )
    require("-Wall -Wextra -Werror" in read(FULL_TEST_MAKEFILE),
            "controller test is not warning-clean")

    crypto_test = read(CRYPTO_TEST)
    crypto_makefile = read(CRYPTO_TEST_MAKEFILE)
    require_tokens(
        crypto_test,
        (
            "trinity_deploy_crypto_generate_keypair",
            "trinity_deploy_crypto_create_session",
            "TRINITY_MLKEM_SHARED_SECRET_MISMATCH",
            "trinity_deploy_crypto_zeroize",
        ),
        "deploy crypto test",
    )
    require("-DTRINITY_DEPLOY_ENABLE_MLKEM=1" in crypto_makefile and
            "-Wall -Wextra -Werror" in crypto_makefile,
            "deploy crypto test does not compile the enabled warning-clean path")

    host_paths = (HOST, CLI, PYPROJECT, HOST_TEST)
    host_checked = all(path.is_file() for path in host_paths)
    if host_checked:
        host = read(HOST)
        cli = read(CLI)
        pyproject = read(PYPROJECT)
        host_test = read(HOST_TEST)
        require_tokens(
            host,
            ("class TrinitySerialClient", "def ping(", "def get_system_info(",
             "def get_system_status(", "def get_transaction_result(",
             "def retire_transaction_result("),
            "host client",
        )
        require('trinity-host = "trinity_host.cli:main"' in pyproject,
                "host console entrypoint was removed")
        require("PING" in host_test and "RUN_SELF_TEST" in host_test and
                "GET_TXN_RESULT" in host_test and "RETIRE_TXN_RESULT" in host_test,
                "existing host fake-serial regression lost coverage")
        require('sub.add_parser("p1-bringup"' in cli,
                "existing P1 hardware bring-up command was removed")
    else:
        print("NOTE: PC host regression files absent from partial source-only checkout")

    require(not re.search(r"[A-Za-z]:[\\/]", combined),
            "machine-specific absolute path in SN32 source")

    print("PASS: dual-Primer SPI, Tiny SESSION_COMMIT and direct P1-to-P2 flow are wired")
    print("PASS: self-test -> keypair -> session ordering and Tiny fault containment are present")
    print("PASS: retained host transactions, authenticated result ACK and zeroize are present")
    print("PASS: ML-KEM keygen/encaps/decaps/KDF lifecycle is wired and portable-tested")
    print("NOTE: default deploy target still has ML-KEM off until pinned vendor sources enter Keil")
    if host_checked:
        print("PASS: existing PC host regression remains present")


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
    require(one("./Targets/Target/TargetOption/TargetCommonOption/PackID") ==
            "SONiX.SN32F4_DFP.1.0.1", "DFP lock changed")
    normalized = project_text.replace("\\", "/").lower()
    require("../src/app/trinity_deploy_main.c" in normalized,
            "deploy entrypoint missing from Keil project")
    require("trinity_deploy_enable_mlkem=1" not in normalized,
            "Keil must not enable ML-KEM before pinned vendor sources are selected")
    require("FPST_SN32F407_P2_CS_N_PIN              2u" in board and
            "FPST_SN32F407_P2_IRQ_N_PIN              8u" in board,
            "P2 CS/IRQ pin mapping drifted")
    require("FPST_SN32F407_TINY_FAULT_N_PIN        10u" in board,
            "Tiny fault input mapping drifted")
    print("PASS: Keil target remains SN32F407F / ArmClang 6.24 / DFP 1.0.1")
    print("PASS: deploy entrypoint and P1/P2/Tiny mappings remain selected")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    check_source_and_tests()
    if args.source_only:
        print("NOTE: Keil XML and board-profile checks skipped by --source-only")
    else:
        check_project_and_pins()
    print("NOTE: static PASS does not claim ArmClang build, flash, memory fit or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
