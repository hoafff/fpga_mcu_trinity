#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
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
CONTROLLER_H = SN32 / "include/trinity_full_controller.h"
CONTROLLER_WRAPPER = SN32 / "src/app/trinity_full_controller.c"
CONTROLLER_PARTS = [SN32 / f"src/app/trinity_full_controller_part_{i:02d}.inc" for i in range(8)]
BRIDGE_WRAPPER = SN32 / "src/app/trinity_deploy_full_bridge.inc"
BRIDGE_PARTS = [SN32 / f"src/app/trinity_deploy_full_bridge_part_{i:02d}.inc" for i in range(7)]
CRYPTO_H = SN32 / "include/trinity_deploy_crypto.h"
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
VENDOR = SN32 / "third_party/mlkem-native/upstream"
EXPECTED_MLKEM_COMMIT = "048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa"
FULL_TEST_PARTS = [SN32 / f"tests/full_controller/test_full_controller_part_{i:02d}.inc" for i in range(3)]
CRYPTO_TEST = SN32 / "tests/deploy_crypto/test_deploy_crypto.c"
CRYPTO_TEST_MAKEFILE = SN32 / "tests/deploy_crypto/Makefile"
GATE3_MAKEFILE = SN32 / "tests/mlkem_gate3/Makefile"
HOST_CLIENT = ROOT / "pc_host/src/trinity_host/serial_client.py"
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


def check_submodule() -> None:
    gitmodules = read(GITMODULES)
    lock = read(VENDOR_LOCK)
    require("path = sn32/third_party/mlkem-native/upstream" in gitmodules,
            "ML-KEM submodule path drifted")
    require("url = https://github.com/pq-code-package/mlkem-native.git" in gitmodules,
            "ML-KEM submodule URL drifted")
    require(f"commit={EXPECTED_MLKEM_COMMIT}" in lock,
            "VENDOR.lock commit drifted")
    require((VENDOR / "mlkem/mlkem_native.c").is_file(),
            "initialize the pinned ML-KEM submodule")
    try:
        actual = subprocess.check_output(
            ["git", "-C", str(VENDOR), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        fail(f"cannot read ML-KEM submodule HEAD: {exc}")
    require(actual == EXPECTED_MLKEM_COMMIT,
            f"ML-KEM submodule HEAD {actual} != {EXPECTED_MLKEM_COMMIT}")
    print("PASS: exact mlkem-native v1.0.0 submodule is initialized")


def check_source() -> None:
    wrapper = read(WRAPPER)
    config = read(CONFIG)
    main = "".join(read(path) for path in MAIN_PARTS)
    controller_wrapper = read(CONTROLLER_WRAPPER)
    controller = read(CONTROLLER_H) + "".join(read(path) for path in CONTROLLER_PARTS)
    bridge_wrapper = read(BRIDGE_WRAPPER)
    bridge = "".join(read(path) for path in BRIDGE_PARTS)
    crypto_wrapper = read(CRYPTO_WRAPPER)
    crypto = read(CRYPTO_H) + "".join(read(path) for path in CRYPTO_PARTS)
    mlkem = "".join(read(path) for path in MLKEM_FILES)

    require_tokens(wrapper,
                   tuple(f'#include "trinity_deploy_main_part_{i:02d}.inc"'
                         for i in range(18)), "deploy wrapper")
    require_tokens(wrapper,
                   ('#include "trinity_full_controller.c"',
                    '#include "trinity_deploy_crypto.c"',
                    '#include "trinity_deploy_full_bridge.inc"'),
                   "deploy wrapper")
    require_tokens(controller_wrapper,
                   tuple(f'#include "trinity_full_controller_part_{i:02d}.inc"'
                         for i in range(8)), "controller wrapper")
    require_tokens(bridge_wrapper,
                   tuple(f'#include "trinity_deploy_full_bridge_part_{i:02d}.inc"'
                         for i in range(7)), "bridge wrapper")
    require_tokens(crypto_wrapper,
                   tuple(f'#include "trinity_deploy_crypto_part_{i:02d}.inc"'
                         for i in range(2)), "crypto wrapper")

    for macro, value in {
        "TRINITY_DEPLOY_ENABLE_PC_UART": "1",
        "TRINITY_DEPLOY_ENABLE_SPI": "1",
        "TRINITY_DEPLOY_ENABLE_PRIMER1": "1",
        "TRINITY_DEPLOY_ENABLE_PRIMER2": "1",
        "TRINITY_DEPLOY_ENABLE_PAYLOAD_RELAY": "0",
        "TRINITY_DEPLOY_ENABLE_TINY_SESSION_COMMIT": "1",
        "TRINITY_DEPLOY_ENABLE_DEMO_SECURE": "0",
        "TRINITY_DEPLOY_P1_BRINGUP_ONLY": "0",
    }.items():
        require(re.search(rf"^#define\s+{macro}\s+{value}\s*$", config, re.M)
                is not None, f"wrong deploy guard {macro}")
    require("TRINITY_DEPLOY_VERSION_MINOR 7u" in config,
            "full deploy version is not v0.7.x")
    require("TRINITY_DEPLOY_CRYPTO_PROGRESS_LEASE_MS  5000u" in config,
            "bounded crypto lease drifted")
    require("FPST_SN32F407_SESSION_COMMIT_PORT          3u" in config and
            "FPST_SN32F407_SESSION_COMMIT_PIN           8u" in config,
            "SESSION_COMMIT is not P3.8")

    require_tokens(controller, (
        "session_commit_low", "session_commit_high",
        "CONTROLLER_SESSION_COMMIT_LOW_MS = 2u",
        "controller_error_is_polling_state",
        "memset(result, 0, sizeof(*result))",
        "TRINITY_SPI_STAGE_SESSION", "TRINITY_SPI_COMMIT_SESSION",
        "TRINITY_SPI_LOAD_TELEMETRY", "TRINITY_SPI_ENCRYPT_AND_SEND",
        "TRINITY_SPI_READ_AUTH_RESULT", "TRINITY_SPI_ACK_AUTH_RESULT",
    ), "controller")
    require_tokens(bridge, (
        "full_session_commit_low", "full_session_commit_high",
        "full_contain_tiny_fault", "full_sn32_self_test", "full_tiny_self_test",
        "managed_transaction_respond", "result_system_state", "result_source",
        "full_crypto_generate_keypair", "full_crypto_create_session",
        "full_send_progress_event", "TRINITY_EVENT_PROGRESS",
        "full_handle_run_demo", "full_handle_ntt_test", "full_handle_ascon_test",
        "full_handle_benchmark", "full_handle_transport_stress",
    ), "deploy bridge")
    require_tokens(crypto + mlkem, (
        "TRINITY_MLKEM512_PUBLIC_KEY_IN_SECRET_KEY_OFFSET",
        "public_key_hash[32]", "embedded_public_key",
        "trinity_mlkem512_keygen_deterministic",
        "trinity_mlkem512_encaps_deterministic",
        "trinity_mlkem512_decaps", "trinity_kdf_derive_session",
        "trinity_sha3_256", "trinity_shake256",
    ), "deploy crypto")
    require_tokens(main, (
        "g_transport_scratch", "g_spi_packet",
        "crypto_progress_lease_begin", "crypto_progress_lease_end",
        "safety_error_latched", "TRINITY_PC_GENERATE_KEYPAIR",
        "TRINITY_PC_CREATE_SESSION", "TRINITY_PC_RUN_DEMO",
        "TRINITY_PC_RUN_NTT_TEST", "TRINITY_PC_RUN_ASCON_TEST",
        "TRINITY_PC_RUN_BENCHMARK", "TRINITY_PC_RUN_TRANSPORT_STRESS",
    ), "deploy main")
    require("g_pc_tx" not in main, "duplicate PC TX buffer returned")
    require("uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES];" not in
            read(CRYPTO_H).split("union", 1)[0],
            "duplicate persistent ML-KEM public key returned")
    require("TRINITY_PC_REQUEST_FAULT_CLEAR" in main and
            "TRINITY_SOURCE_TINY1P5" in main,
            "Tiny fault clear must not be faked")

    full_test = "".join(read(path) for path in FULL_TEST_PARTS)
    require_tokens(full_test, (
        "retained_not_ready_reads", "commit_low_calls", "commit_high_calls",
        "TRINITY_RESULT_PENDING", "TRINITY_FAULT_TINY1P5",
    ), "controller tests")
    crypto_test = read(CRYPTO_TEST)
    require_tokens(crypto_test, (
        "TRINITY_MLKEM512_PUBLIC_KEY_IN_SECRET_KEY_OFFSET",
        "sizeof(crypto) <= 2600u", "TRINITY_MLKEM_SHARED_SECRET_MISMATCH",
    ), "crypto tests")
    require("-DTRINITY_DEPLOY_ENABLE_MLKEM=1" in read(CRYPTO_TEST_MAKEFILE),
            "enabled crypto path is not tested")
    gate3 = read(GATE3_MAKEFILE)
    require("mlkem_native.c" in gate3 and "MLK_CONFIG_PARAMETER_SET=512" in gate3,
            "Gate 3 is not pinned to ML-KEM-512 SCU")

    host = read(HOST_CLIENT)
    host_test = read(HOST_TEST)
    require_tokens(host, (
        "EventEnvelope", "_handle_event", "event_handler",
        "RUN_SELF_TEST final response has the wrong test mask",
    ), "PC host")
    require_tokens(host_test, (
        "_queue_progress", "EventType.PROGRESS", "progress_percent",
    ), "PC host tests")

    combined = main + controller + bridge + crypto + mlkem + host
    require(not re.search(r"[A-Za-z]:[\\/]", combined),
            "machine-specific path in source")
    print("PASS: full dual-Primer, Tiny, ML-KEM and PC EVENT paths are wired")
    print("PASS: immutable retries, retained polling, progress and zeroization are wired")
    print("PASS: RAM overlays, embedded public key and bounded crypto lease are present")


def check_project() -> None:
    project = read(PROJECT)
    board = read(BOARD)
    require(S0_PROJECT.is_file(), "canonical S0 project was removed")
    try:
        root = ET.fromstring(project)
    except ET.ParseError as exc:
        fail(f"invalid Keil XML: {exc}")

    def value(xpath: str) -> str:
        node = root.find(xpath)
        require(node is not None and node.text is not None, f"missing {xpath}")
        return node.text.strip()

    require(value("./Targets/Target/TargetName") == "trinity_sn32f407_deploy",
            "wrong deploy target")
    require(value("./Targets/Target/pCCUsed") == "6240000::V6.24::ARMCLANG",
            "ArmClang lock changed")
    require(value("./Targets/Target/TargetOption/TargetCommonOption/Device") ==
            "SN32F407F", "device lock changed")
    require(value("./Targets/Target/TargetOption/TargetCommonOption/PackID") ==
            "SONiX.SN32F4_DFP.1.0.1", "DFP lock changed")
    normalized = project.replace("\\", "/").lower()
    require_tokens(normalized, (
        "../src/app/trinity_deploy_main.c",
        "trinity_deploy_enable_mlkem=1", "mlk_config_parameter_set=512",
        "mlk_config_namespace_prefix=trinity_mlkem512",
        "../src/trinity_mlkem_backend.c", "../src/trinity_mlkem.c",
        "../src/trinity_fips202_bridge.c",
        "../third_party/mlkem-native/upstream/mlkem/mlkem_native.c",
        "../third_party/mlkem-native/upstream/mlkem",
        "iram(0x20000000,0x2000)", "irom(0x00000000,0x7ffc)",
    ), "Keil project")
    require("FPST_SN32F407_P2_CS_N_PIN              2u" in board and
            "FPST_SN32F407_P2_IRQ_N_PIN              8u" in board,
            "P2 CS/IRQ mapping drifted")
    require("FPST_SN32F407_TINY_FAULT_N_PIN        10u" in board,
            "Tiny fault mapping drifted")
    require("FPST_SN32F407_FLASH_CS_N_PIN           8u" in board,
            "flash CS safety mapping drifted")
    print("PASS: valid Keil SN32F407F project with pinned ML-KEM-512 SCU")
    print("PASS: Keil memory regions remain IROM 0x7FFC and IRAM 0x2000")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    check_source()
    if args.source_only:
        print("NOTE: submodule, Keil XML and board checks skipped")
    else:
        check_submodule()
        check_project()
    print("NOTE: static PASS does not claim ArmClang link, memory fit, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
