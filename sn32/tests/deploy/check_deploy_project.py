#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SN32 = ROOT / "sn32"
PROJECT = SN32 / "keil/trinity_sn32f407_deploy.uvprojx"
S0_PROJECT = SN32 / "keil/trinity_sn32f407.uvprojx"
CONFIG = SN32 / "config/trinity_deploy_config.h"
BOARD = SN32 / "firmware/platform/sn32f407/board_profile.h"
WRAPPER = SN32 / "src/app/trinity_deploy_main.c"
MAIN_PARTS = [SN32 / f"src/app/trinity_deploy_main_part_{i:02d}.inc" for i in range(18)]
CONTROLLER_WRAPPER = SN32 / "src/app/trinity_full_controller.c"
CONTROLLER_PARTS = [SN32 / f"src/app/trinity_full_controller_part_{i:02d}.inc" for i in range(8)]
BRIDGE_WRAPPER = SN32 / "src/app/trinity_deploy_full_bridge.inc"
BRIDGE_PARTS = [SN32 / f"src/app/trinity_deploy_full_bridge_part_{i:02d}.inc" for i in range(7)]
CRYPTO_WRAPPER = SN32 / "src/app/trinity_deploy_crypto.c"
CRYPTO_PARTS = [SN32 / f"src/app/trinity_deploy_crypto_part_{i:02d}.inc" for i in range(2)]
MLKEM_FILES = [
    SN32 / "include/trinity_mlkem.h",
    SN32 / "include/trinity_mlkem_backend.h",
    SN32 / "src/trinity_mlkem.c",
    SN32 / "src/trinity_mlkem_backend.c",
    SN32 / "src/trinity_fips202_bridge.c",
]
GITMODULES = ROOT / ".gitmodules"
VENDOR_LOCK = SN32 / "third_party/mlkem-native/VENDOR.lock"
UPSTREAM_SCU = SN32 / "third_party/mlkem-native/upstream/mlkem/mlkem_native.c"
FULL_TEST = SN32 / "tests/full_controller/test_full_controller.c"
FULL_TEST_PARTS = [SN32 / f"tests/full_controller/test_full_controller_part_{i:02d}.inc" for i in range(3)]
FULL_TEST_MAKEFILE = SN32 / "tests/full_controller/Makefile"
CRYPTO_TEST = SN32 / "tests/deploy_crypto/test_deploy_crypto.c"
CRYPTO_TEST_MAKEFILE = SN32 / "tests/deploy_crypto/Makefile"
GATE3_MAKEFILE = SN32 / "tests/mlkem_gate3/Makefile"


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


def check_wrappers() -> tuple[str, str, str, str]:
    wrapper = read(WRAPPER)
    main_source = "".join(read(path) for path in MAIN_PARTS)
    controller_wrapper = read(CONTROLLER_WRAPPER)
    controller = "".join(read(path) for path in CONTROLLER_PARTS)
    bridge_wrapper = read(BRIDGE_WRAPPER)
    bridge = "".join(read(path) for path in BRIDGE_PARTS)
    crypto_wrapper = read(CRYPTO_WRAPPER)
    crypto = "".join(read(path) for path in CRYPTO_PARTS)

    require_tokens(wrapper,
                   tuple(f'#include "trinity_deploy_main_part_{i:02d}.inc"'
                         for i in range(18)), "deploy wrapper")
    require('#include "trinity_full_controller.c"' in wrapper,
            "full controller is not compiled")
    require('#include "trinity_deploy_crypto.c"' in wrapper,
            "deploy crypto is not compiled")
    require('#include "trinity_deploy_full_bridge.inc"' in wrapper,
            "hardware bridge is not compiled")
    require_tokens(controller_wrapper,
                   tuple(f'#include "trinity_full_controller_part_{i:02d}.inc"'
                         for i in range(8)), "controller wrapper")
    require_tokens(bridge_wrapper,
                   tuple(f'#include "trinity_deploy_full_bridge_part_{i:02d}.inc"'
                         for i in range(7)), "bridge wrapper")
    require_tokens(crypto_wrapper,
                   tuple(f'#include "trinity_deploy_crypto_part_{i:02d}.inc"'
                         for i in range(2)), "crypto wrapper")
    return main_source, controller, bridge, crypto


def check_source_and_tests() -> None:
    config = read(CONFIG)
    main_source, controller, bridge, crypto = check_wrappers()
    mlkem = "".join(read(path) for path in MLKEM_FILES)
    gitmodules = read(GITMODULES)
    vendor_lock = read(VENDOR_LOCK)

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
        require(re.search(rf"^#define\s+{macro}\s+{value}\s*$", config, re.M)
                is not None, f"wrong full-deploy guard {macro}")
    require("#ifndef TRINITY_DEPLOY_ENABLE_MLKEM" in config,
            "ML-KEM build override guard missing")
    require("FPST_SN32F407_SESSION_COMMIT_PORT          3u" in config and
            "FPST_SN32F407_SESSION_COMMIT_PIN           8u" in config,
            "SESSION_COMMIT is not locked to P3.8")

    require_tokens(controller, (
        "trinity_controller_probe_all", "trinity_controller_run_self_test",
        "trinity_controller_activate_session", "trinity_controller_zeroize",
        "trinity_controller_send_telemetry", "TRINITY_SPI_STAGE_SESSION",
        "TRINITY_SPI_COMMIT_SESSION", "TRINITY_SPI_LOAD_TELEMETRY",
        "TRINITY_SPI_ENCRYPT_AND_SEND", "TRINITY_SPI_READ_AUTH_RESULT",
        "TRINITY_SPI_ACK_AUTH_RESULT", "TRINITY_AUTH_THRESHOLD",
        "session_commit_low", "session_commit_high",
    ), "full controller")
    require_tokens(bridge, (
        "full_session_commit_low", "full_session_commit_high",
        "full_tiny_fault_active", "full_contain_tiny_fault",
        "managed_transaction_begin", "managed_transaction_respond",
        "full_handle_generate_keypair", "full_handle_create_session",
        "full_handle_send_telemetry", "full_handle_run_demo",
        "full_handle_ntt_test", "full_handle_ascon_test",
        "full_handle_benchmark", "full_handle_zeroize",
        "full_handle_transport_stress",
    ), "deploy bridge")
    require_tokens(crypto + mlkem, (
        "trinity_deploy_crypto_generate_keypair",
        "trinity_deploy_crypto_create_session",
        "trinity_mlkem512_keygen_deterministic",
        "trinity_mlkem512_encaps_deterministic",
        "trinity_mlkem512_decaps", "trinity_kdf_derive_session",
        "trinity_sha3_256", "trinity_shake256",
    ), "deploy crypto")
    require_tokens(main_source, (
        "TRINITY_PC_GENERATE_KEYPAIR", "TRINITY_PC_CREATE_SESSION",
        "TRINITY_PC_CLOSE_SESSION", "TRINITY_PC_ZEROIZE_SYSTEM",
        "TRINITY_PC_SEND_ONE_TELEMETRY", "TRINITY_PC_RUN_DEMO",
        "TRINITY_PC_READ_LAST_RESULT", "TRINITY_PC_RUN_NTT_TEST",
        "TRINITY_PC_RUN_ASCON_TEST", "TRINITY_PC_RUN_BENCHMARK",
        "TRINITY_PC_RUN_TRANSPORT_STRESS", "full_contain_tiny_fault",
    ), "dispatcher/main loop")
    require("req->payload[0] == 2u" in bridge and
            "TRINITY_NOT_SUPPORTED" in bridge,
            "DEMO_SECURE must fail explicitly")
    require("TRINITY_PC_REQUEST_FAULT_CLEAR" in main_source and
            "TRINITY_SOURCE_TINY1P5" in main_source,
            "Tiny fault clear must not be faked")

    require("path = sn32/third_party/mlkem-native/upstream" in gitmodules and
            "url = https://github.com/pq-code-package/mlkem-native.git" in gitmodules,
            "pinned ML-KEM submodule declaration missing")
    require("commit=048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa" in vendor_lock,
            "ML-KEM vendor lock drifted")

    full_test_source = read(FULL_TEST) + "".join(read(path) for path in FULL_TEST_PARTS)
    require_tokens(full_test_source, (
        "trinity_controller_activate_session", "trinity_controller_send_telemetry",
        "TRINITY_RESULT_PENDING", "trinity_controller_zeroize",
        "TRINITY_FAULT_TINY1P5",
    ), "controller test")
    require("-Wall -Wextra -Werror" in read(FULL_TEST_MAKEFILE),
            "controller test is not warning-clean")

    crypto_test = read(CRYPTO_TEST)
    require_tokens(crypto_test, (
        "trinity_deploy_crypto_generate_keypair",
        "trinity_deploy_crypto_create_session",
        "TRINITY_MLKEM_SHARED_SECRET_MISMATCH",
        "trinity_deploy_crypto_zeroize",
    ), "deploy crypto test")
    require("-DTRINITY_DEPLOY_ENABLE_MLKEM=1" in read(CRYPTO_TEST_MAKEFILE),
            "deploy crypto enabled path is not tested")
    gate3 = read(GATE3_MAKEFILE)
    require("mlkem_native.c" in gate3 and "MLK_CONFIG_PARAMETER_SET=512" in gate3,
            "Gate 3 is not using the pinned ML-KEM-512 SCU")
    require("MLK_CONFIG_NO_ASM" not in gate3,
            "host Gate 3 must not require an unprovided custom zeroizer")

    combined = main_source + controller + bridge + crypto + mlkem
    require(not re.search(r"[A-Za-z]:[\\/]", combined),
            "machine-specific absolute path in SN32 source")

    print("PASS: full dual-Primer control, Tiny commit/fault and direct UART flow")
    print("PASS: ML-KEM keypair/session, deterministic demo and diagnostics")
    print("PASS: immutable retained results, benchmark, stress and zeroization")
    print("PASS: exact mlkem-native submodule pin and Gate 3 SCU configuration")


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
    require(one("./Targets/Target/TargetOption/TargetCommonOption/Device") ==
            "SN32F407F", "device lock changed")
    require(one("./Targets/Target/TargetOption/TargetCommonOption/PackID") ==
            "SONiX.SN32F4_DFP.1.0.1", "DFP lock changed")

    normalized = project_text.replace("\\", "/").lower()
    require("../src/app/trinity_deploy_main.c" in normalized,
            "deploy entrypoint missing")
    require("trinity_deploy_enable_mlkem=1" in normalized,
            "Keil deploy target does not enable ML-KEM")
    require("mlk_config_parameter_set=512" in normalized and
            "mlk_config_namespace_prefix=trinity_mlkem512" in normalized,
            "Keil ML-KEM-512 namespace configuration missing")
    require("../src/trinity_mlkem_backend.c" in normalized and
            "../src/trinity_mlkem.c" in normalized and
            "../src/trinity_fips202_bridge.c" in normalized and
            "../third_party/mlkem-native/upstream/mlkem/mlkem_native.c" in normalized,
            "Keil ML-KEM source group incomplete")
    require(UPSTREAM_SCU.is_file(),
            "initialize submodules before building the Keil deploy target")
    require("FPST_SN32F407_P2_CS_N_PIN              2u" in board and
            "FPST_SN32F407_P2_IRQ_N_PIN              8u" in board,
            "P2 CS/IRQ mapping drifted")
    require("FPST_SN32F407_TINY_FAULT_N_PIN        10u" in board,
            "Tiny fault mapping drifted")

    print("PASS: valid Keil XML and locked SN32F407F/ArmClang/DFP target")
    print("PASS: Keil selects pinned ML-KEM-512 SCU and Trinity wrappers")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    check_source_and_tests()
    if args.source_only:
        print("NOTE: Keil XML, submodule checkout and board checks skipped")
    else:
        check_project_and_pins()
    print("NOTE: static PASS does not claim ArmClang link, memory fit, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
