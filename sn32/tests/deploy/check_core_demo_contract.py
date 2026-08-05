#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
IDENTITY = ROOT / "sn32/src/app/trinity_deploy_main_part_00.inc"
MLKEM = ROOT / "sn32/src/trinity_mlkem.c"
A2 = ROOT / "sn32/src/trinity_mlkem_lowram_a2.inc"
CRYPTO = ROOT / "sn32/src/app/trinity_deploy_crypto_part_01.inc"
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
    mlkem = read(MLKEM)
    a2 = read(A2)
    crypto = read(CRYPTO)
    core = read(CORE)
    gui = read(GUI)
    package = read(PACKAGE)

    require(re.search(r"^#define\s+TRINITY_DEPLOY_VERSION_PATCH\s+29u$",
                      config, re.MULTILINE) is not None,
            "SN32 candidate is not v0.7.29")
    require(re.search(r"^#define\s+DEPLOY_BUILD_ID\s+UINT32_C\(0x0007001D\)$",
                      identity, re.MULTILINE) is not None,
            "SN32 build ID is not 0x0007001D")
    tokens(config, (
        "TRINITY_DEPLOY_CORE_DEMO_WITHOUT_TINY       1",
        "TRINITY_DEPLOY_DIRECT_SECURE_ENABLE_OUTPUT  1",
        "TRINITY_DEPLOY_CRYPTO_PROGRESS_LEASE_MS 120000u",
    ), "demo config")

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

    tokens(core, (
        "run_core_demo",
        "run_sn32_hardware_qualification",
        "generate_keypair",
        "create_session",
        "send_telemetry",
        "read_last_result",
        "zeroize",
        "CORE DEMO PASS — Tiny 1P5 không thuộc phạm vi",
    ), "host core demo")
    tokens(gui, (
        "class TrinityDemoApp",
        "CHẠY CORE DEMO",
        "Tiny 1P5 tạm thời không sử dụng",
        "SN32 P3.8 phải nối trực tiếp",
        "threading.Thread",
        "Xuất log",
    ), "demo GUI")
    require(re.search(r'^version = "0\.5\.0"$', package, re.MULTILINE) is not None,
            "host package is not 0.5.0")
    require('trinity-demo = "trinity_host.demo_gui:main"' in package,
            "trinity-demo entry point is missing")

    print("PASS: v0.7.29 low-RAM A2 routes Encaps/Decaps without full vectors")
    print("PASS: session self-check, KDF, telemetry, readback and zeroize are wired")
    print("PASS: PC host v0.5.0 exposes a threaded Tkinter demo dashboard")
    print("PASS: Tiny omission and direct secure-enable wiring are explicit")
    print("NOTE: source PASS is not ArmClang fit or hardware core-demo PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
