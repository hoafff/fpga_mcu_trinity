#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "sn32/keil/trinity_sn32f407.uvprojx"
CONFIG = ROOT / "sn32/config/trinity_build_config.h"
MAIN = ROOT / "sn32/src/app/trinity_main.c"
MANIFEST = ROOT / "sn32/keil/SOURCES.lock"
README = ROOT / "sn32/keil/README_BUILD.md"

errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def text(root: ET.Element, path: str) -> str:
    node = root.find(path)
    return "" if node is None or node.text is None else node.text.strip()


for path in (PROJECT, CONFIG, MAIN, MANIFEST, README):
    require(path.is_file(), f"missing S0 file: {path.relative_to(ROOT)}")

if PROJECT.is_file():
    try:
        project_root = ET.parse(PROJECT).getroot()
    except ET.ParseError as exc:
        errors.append(f"invalid uvprojx XML: {exc}")
        project_root = ET.Element("invalid")

    require(text(project_root, ".//TargetName") == "trinity_sn32f407", "wrong target name")
    require(text(project_root, ".//Device") == "SN32F407F", "wrong device")
    require(text(project_root, ".//Vendor") == "SONiX", "wrong vendor")
    require(text(project_root, ".//PackID") == "SONiX.SN32F4_DFP.1.1.1", "wrong DFP")
    require(text(project_root, ".//pCCUsed") == "6240000::V6.24::ARMCLANG", "wrong ArmClang lock")
    require(text(project_root, ".//uAC6") == "1", "ARM Compiler 6 not enabled")

    cpu = text(project_root, ".//Cpu")
    for expected in (
        "IRAM(0x20000000,0x2000)",
        "IROM(0x00000000,0x7FFC)",
        'CPUTYPE("Cortex-M0")',
        "CLOCK(12000000)",
    ):
        require(expected in cpu, f"CPU/memory lock missing: {expected}")

    require(text(project_root, ".//CreateExecutable") == "1", "executable generation disabled")
    require(text(project_root, ".//CreateHexFile") == "1", "HEX generation disabled")
    require(text(project_root, ".//DebugInformation") == "1", "debug information disabled")
    require(text(project_root, ".//BrowseInformation") == "1", "browse information disabled")
    require(text(project_root, ".//AdsLmap") == "1", "linker MAP disabled")
    require(text(project_root, ".//ldXref") == "1", "cross-reference disabled")
    require(text(project_root, ".//AdsLcgr") == "1", "call graph disabled")
    require(text(project_root, ".//LDads/useFile") == "0", "S0 must use target-memory auto scatter")

    file_paths = [node.text or "" for node in project_root.findall(".//Groups//FilePath")]
    require(file_paths.count(r"..\src\app\trinity_main.c") == 1, "trinity_main.c must appear exactly once")
    require(r"..\config\trinity_build_config.h" in file_paths, "build config missing from project")
    require(not any("fpst_sn32f407_main.c" in value for value in file_paths), "legacy single-Primer main compiled")
    require(not any("fpst_sn32f407_dual_main.c" in value for value in file_paths), "legacy dual-Primer main compiled")

    instances = [node.text or "" for node in project_root.findall(".//RTE/files/file/instance")]
    require(r"RTE\Device\SN32F407F\startup_SN32F400.s" in instances, "startup RTE instance missing")
    require(r"RTE\Device\SN32F407F\system_SN32F400.c" in instances, "system RTE instance missing")

    packages = {(node.get("vendor"), node.get("name"), node.get("version")) for node in project_root.findall(".//RTE//package")}
    require(("ARM", "CMSIS", "6.3.0") in packages, "CMSIS 6.3.0 package missing")
    require(("SONiX", "SN32F4_DFP", "1.1.1") in packages, "SONiX DFP 1.1.1 package missing")

    project_text = PROJECT.read_text(encoding="utf-8")
    require(re.search(r"(?:^|[>\"'])\s*[A-Za-z]:[\\/]", project_text, re.MULTILINE) is None, "absolute Windows path in project")
    require("uvguix" not in project_text.lower(), "uvguix reference in project")

if CONFIG.is_file():
    config_text = CONFIG.read_text(encoding="utf-8")
    for feature in (
        "TRINITY_ENABLE_PC_UART",
        "TRINITY_ENABLE_SPI",
        "TRINITY_ENABLE_MLKEM",
        "TRINITY_ENABLE_TINY_SESSION_COMMIT",
        "TRINITY_ENABLE_DEMO_SECURE",
    ):
        require(
            re.search(rf"^#define\s+{feature}\s+0\s*$", config_text, re.MULTILINE) is not None,
            f"{feature} is not locked to zero",
        )

if MAIN.is_file():
    main_text = MAIN.read_text(encoding="utf-8")
    require("void trinity_main(void)" in main_text, "trinity_main() missing")
    require("int main(void)" in main_text, "C runtime main() missing")
    require("SystemInit();" in main_text, "SystemInit is not called")
    require("SystemCoreClockUpdate();" in main_text, "SystemCoreClockUpdate is not called")
    require("fpst_" not in main_text, "legacy FPST dependency in S0 main")
    require("TRINITY_ENABLE_SPI" not in main_text, "S0 main contains SPI implementation branch")

if MANIFEST.is_file():
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    for required in (
        "pre_change_commit=420c995eb6b64a327ec176b444139f5572da566d",
        "known_good_donor_commit=d4412745f30f518f1c7a128cc494fa2678b4926c",
        "hardware_documents_commit=0d78b6a4bdfa2732ca000851b08be13fb9294a6d",
        "post_change_commit=SELF",
        "fpst_sn32f407_main.c=legacy_FPST_not_Trinity_v0.4",
        "fpst_sn32f407_dual_main.c=legacy_P1_to_MCU_to_P2_payload_relay",
    ):
        require(required in manifest_text, f"manifest entry missing: {required}")
    require(re.search(r"(?:^|[>\"'])\s*[A-Za-z]:[\\/]", manifest_text, re.MULTILINE) is None, "absolute Windows path in manifest")

for path in ROOT.rglob("*.uvguix.*"):
    errors.append(f"forbidden user project file: {path.relative_to(ROOT)}")

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(1)

print("PASS: S0 Keil XML, exact target, RTE packs, source manifest and feature guards")
print("PASS: one Trinity main; legacy FPST main files excluded")
print("PASS: no absolute Windows paths or uvguix user metadata")
