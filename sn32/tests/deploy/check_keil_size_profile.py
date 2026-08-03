#!/usr/bin/env python3
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "sn32/keil/trinity_sn32f407_deploy.uvprojx"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def value(root: ET.Element, xpath: str) -> str:
    node = root.find(xpath)
    if node is None or node.text is None:
        fail(f"missing {xpath}")
    return node.text.strip()


def main() -> int:
    try:
        root = ET.fromstring(PROJECT.read_text(encoding="utf-8"))
    except (OSError, ET.ParseError) as exc:
        fail(f"cannot parse deploy project: {exc}")

    base = "./Targets/Target/TargetOption/TargetArmAds"
    if value(root, f"{base}/ArmAdsMisc/useUlib") != "1":
        fail("deploy target must use MicroLib for the 32 KiB image")
    if value(root, f"{base}/ArmAdsMisc/uLtcg") != "1":
        fail("deploy target must enable target-level link-time optimization")
    if value(root, f"{base}/Cads/Optim") != "8":
        fail("deploy target must select the ArmClang Oz size profile")
    if value(root, f"{base}/Cads/v6Lto") != "1":
        fail("deploy C compilation must emit LTO bitcode")

    compiler_misc = value(root, f"{base}/Cads/VariousControls/MiscControls")
    for token in ("-Oz", "-flto", "-fno-unroll-loops"):
        if token not in compiler_misc.split():
            fail(f"deploy compiler controls missing {token}")

    linker_misc = value(root, f"{base}/LDads/Misc")
    if "--lto-level=Oz" not in linker_misc.split():
        fail("deploy linker must use --lto-level=Oz")

    cpu = value(root, "./Targets/Target/TargetOption/TargetCommonOption/Cpu")
    if "IROM(0x00000000,0x7FFC)" not in cpu:
        fail("Flash region must remain the real 0x7FFC-byte SN32F407F region")
    if "IRAM(0x20000000,0x2000)" not in cpu:
        fail("RAM region must remain the real 8 KiB SN32F407F region")

    project_text = PROJECT.read_text(encoding="utf-8")
    required_features = (
        "TRINITY_DEPLOY_ENABLE_MLKEM=1",
        "MLK_CONFIG_PARAMETER_SET=512",
        "..\\src\\app\\trinity_deploy_main.c",
        "..\\third_party\\mlkem-native\\upstream\\mlkem\\mlkem_native.c",
    )
    for token in required_features:
        if token not in project_text:
            fail(f"size profile removed required deploy input {token}")

    print("PASS: Keil deploy target uses Oz + full LTO + MicroLib")
    print("PASS: real 32 KiB/8 KiB memory regions and ML-KEM-512 remain enabled")
    print("NOTE: this is a static project-profile check, not an exact ArmClang link PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
