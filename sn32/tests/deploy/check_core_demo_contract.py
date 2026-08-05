#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
IDENTITY = ROOT / "sn32/src/app/trinity_deploy_main_part_00.inc"
MAIN04 = ROOT / "sn32/src/app/trinity_deploy_main_part_04.inc"
CONTROLLER_H = ROOT / "sn32/include/trinity_full_controller.h"
CONTROLLER02 = ROOT / "sn32/src/app/trinity_full_controller_part_02.inc"
CONTROLLER04 = ROOT / "sn32/src/app/trinity_full_controller_part_04.inc"
BRIDGE00 = ROOT / "sn32/src/app/trinity_deploy_full_bridge_part_00.inc"
BRIDGE02 = ROOT / "sn32/src/app/trinity_deploy_full_bridge_part_02.inc"
BRIDGE04 = ROOT / "sn32/src/app/trinity_deploy_full_bridge_part_04.inc"
MLKEM = ROOT / "sn32/src/trinity_mlkem.c"
A2 = ROOT / "sn32/src/trinity_mlkem_lowram_a2.inc"
CRYPTO = ROOT / "sn32/src/app/trinity_deploy_crypto_part_01.inc"
SERIAL = ROOT / "pc_host/src/trinity_host/serial_client.py"
FLOW = ROOT / "pc_host/src/trinity_host/full_flow.py"
CORE = ROOT / "pc_host/src/trinity_host/demo_core.py"
GUI = ROOT / "pc_host/src/trinity_host/demo_gui.py"
PACKAGE = ROOT / "pc_host/pyproject.toml"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def tokens(text: str, required: tuple[str, ...], label: str) -> None:
    for token in required:
        require(token in text, f"{label} missing {token}")


def main() -> int:
    config = read(CONFIG)
    identity = read(IDENTITY)
    main04 = read(MAIN04)
    controller_h = read(CONTROLLER_H)
    controller02 = read(CONTROLLER02)
    controller04 = read(CONTROLLER04)
    bridge00 = read(BRIDGE00)
    bridge02 = read(BRIDGE02)
    bridge04 = read(BRIDGE04)
    mlkem = read(MLKEM)
    a2 = read(A2)
    crypto = read(CRYPTO)
    serial = read(SERIAL)
    flow = read(FLOW)
    core = read(CORE)
    gui = read(GUI)
    package = read(PACKAGE)

    require(re.search(r"^#define\s+TRINITY_DEPLOY_VERSION_PATCH\s+31u$",
                      config, re.MULTILINE) is not None,
            "SN32 candidate is not v0.7.31")
    require(re.search(r"^#define\s+DEPLOY_BUILD_ID\s+UINT32_C\(0x0007001F\)$",
                      identity, re.MULTILINE) is not None,
            "SN32 build ID is not 0x0007001F")
    tokens(config, (
        "TRINITY_DEPLOY_CORE_DEMO_WITHOUT_TINY       1",
        "TRINITY_DEPLOY_DIRECT_SECURE_ENABLE_OUTPUT  1",
        "TRINITY_DEPLOY_ENABLE_MCU_HEARTBEAT_OUTPUT  0",
        "FPST_SN32F407_SESSION_COMMIT_PORT          2u",
        "FPST_SN32F407_SESSION_COMMIT_PIN           9u",
        "TRINITY_DEPLOY_CRYPTO_PROGRESS_LEASE_MS 120000u",
    ), "demo config")
    tokens(identity, (
        "P2.9 cannot drive heartbeat and shared secure-enable simultaneously",
        "v0.7.31 no-Tiny demo requires SN32 P2.9 as shared secure-enable",
    ), "compile-time pin ownership")
    tokens(main04, (
        "#if TRINITY_DEPLOY_ENABLE_MCU_HEARTBEAT_OUTPUT",
        "gpio_write(FPST_SN32F407_MCU_HEARTBEAT_PORT",
    ), "heartbeat ownership")

    tokens(mlkem, (
        '#include "trinity_mlkem_lowram_a2.inc"',
        "trinity_mlkem512_encaps_deterministic_lowram",
        "trinity_mlkem512_decaps_lowram",
    ), "ML-KEM route")
    tokens(a2, (
        "TRINITY_MLKEM512_LOW_RAM_WORKSPACE_BYTES",
        "trinity_lowram_indcpa_encrypt",
        "trinity_lowram_indcpa_decrypt",
        "trinity_lowram_ciphertext_emit",
        "rejection_input = (uint8_t *)(void *)&workspace->accumulator",
        "valid_mask",
        "trinity_lowram_encoded_polyvec_is_canonical",
    ), "low-RAM A2")
    require("uint8_t reencrypted_ciphertext[" not in a2,
            "A2 contains a forbidden full re-encryption ciphertext buffer")
    require("mlk_polymat" not in a2 and "mlk_polyvec" not in a2,
            "A2 retains a forbidden full matrix/polyvector")
    tokens(crypto, (
        "uint8_t encapsulated_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES]",
        "memcpy(encapsulated_secret",
        "trinity_mlkem512_decaps",
        "trinity_constant_time_equal",
        "trinity_kdf_derive_session",
    ), "session crypto")

    tokens(controller_h, (
        "TRINITY_SESSION_FAILURE_PHASE_ACTIVE_WAIT",
        "TRINITY_SESSION_FAILURE_GPIO_HIGH",
        "TRINITY_SESSION_FAILURE_DETAIL_PACK",
    ), "session diagnostic format")
    tokens(controller02, (
        "controller_session_state_matches",
        "expected_state == TRINITY_SESSION_STAGED",
        "TRINITY_SECURE_SESSION_STAGED",
        "GET_STATUS exposes active_session_id",
        "COMMIT_SESSION",
    ), "staged status contract")
    tokens(controller04, (
        "failure_detail",
        "TRINITY_SESSION_FAILURE_PHASE_STAGE_WAIT",
        "TRINITY_SESSION_FAILURE_PHASE_COMMIT_WAIT",
        "TRINITY_SESSION_FAILURE_PHASE_ACTIVE_WAIT",
    ), "controller failure snapshot")
    tokens(bridge00, (
        "g_session_commit_readback_at_high",
        "gpio_set_mode(FPST_SN32F407_SESSION_COMMIT_PORT",
        "gpio_read(FPST_SN32F407_SESSION_COMMIT_PORT",
    ), "P2.9 readback")
    tokens(bridge02, (
        "const bool emergency_all",
        "memset(&g_host_txn, 0, sizeof(g_host_txn))",
        "g_controller.last_error = TRINITY_OK",
        "g_trinity_deploy_marker = DEPLOY_MARKER_OK",
    ), "emergency zeroize")
    tokens(bridge04, (
        "g_session_commit_readback_at_high = false",
        "TRINITY_SESSION_FAILURE_GPIO_HIGH",
    ), "session readback attachment")

    tokens(serial, (
        "EXPECTED_SN32_BUILD_ID = 0x0007001F",
        "EXPECTED_SN32_VERSION = (0, 7, 31)",
        "class LastErrorSnapshot",
        "class SessionCommitDiagnostic",
        "P2.9_readback",
    ), "host diagnostic decoder")
    tokens(flow, (
        "_retire_active_host_transaction",
        "except RemoteError",
        "emergency_zeroize",
        "read_session_commit_diagnostic",
    ), "host recovery flow")
    tokens(core, (
        "run_core_demo",
        "run_sn32_hardware_qualification",
        "generate_keypair",
        "create_session",
        "send_telemetry",
        "read_last_result",
        "SESSION COMMIT DIAGNOSTIC",
        "emergency_zeroize",
        "CORE DEMO PASS — Tiny 1P5 không thuộc phạm vi",
    ), "host core demo")
    tokens(gui, (
        "class TrinityDemoApp",
        "CHẠY CORE DEMO",
        "ZEROIZE KHẨN CẤP",
        "SN32 P2.9 phải nối trực tiếp",
        "emergency_zeroize",
        "threading.Thread",
        "Xuất log",
    ), "demo GUI")
    require(re.search(r'^version = "0\.5\.2"$', package, re.MULTILINE) is not None,
            "host package is not 0.5.2")
    require('trinity-demo = "trinity_host.demo_gui:main"' in package,
            "trinity-demo entry point is missing")

    print("PASS: v0.7.31 retains the low-RAM ML-KEM core-demo datapath")
    print("PASS: STAGED validation follows the Primer active-session status contract")
    print("PASS: exact session IDs remain enforced by COMMIT_SESSION and active states")
    print("PASS: v0.7.30 recovery diagnostics and emergency zeroize remain wired")
    print("PASS: PC host v0.5.2 expects the corrected SN32 identity")
    print("NOTE: source PASS is not ArmClang fit or hardware core-demo PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
