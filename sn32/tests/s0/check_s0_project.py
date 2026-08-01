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
BUILD_README = ROOT / "sn32/keil/README_BUILD.md"
TARGET = ROOT / "sn32/target.toml"
TOOLCHAIN = ROOT / "ai_context/toolchains/TOOLCHAIN_LOCK.md"
STATUS = ROOT / "ai_context/status/IMPLEMENTATION_STATUS.md"
ROOT_README = ROOT / "README.md"
EVIDENCE = ROOT / "ai_context/evidence/sn32/S0_KEIL_BUILD_EVIDENCE_2026-08-01.md"

errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def text(root: ET.Element, path: str) -> str:
    node = root.find(path)
    return "" if node is None or node.text is None else node.text.strip()


required_files = (
    PROJECT, CONFIG, MAIN, MANIFEST, BUILD_README, TARGET,
    TOOLCHAIN, STATUS, ROOT_README, EVIDENCE,
)
for path in required_files:
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
    require(text(project_root, ".//PackID") == "SONiX.SN32F4_DFP.1.0.1", "wrong DFP")
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

    components = {
        (node.get("Cvendor"), node.get("Cclass"), node.get("Cgroup"), node.get("Cversion"))
        for node in project_root.findall(".//RTE/components/component")
    }
    require(("ARM", "CMSIS", "CORE", "6.1.1") in components, "CMSIS CORE 6.1.1 component missing")

    packages = {
        (node.get("vendor"), node.get("name"), node.get("version"))
        for node in project_root.findall(".//RTE//package")
    }
    require(("ARM", "CMSIS", "6.2.0") in packages, "CMSIS 6.2.0 package missing")
    require(("SONiX", "SN32F4_DFP", "1.0.1") in packages, "SONiX DFP 1.0.1 package missing")

    project_text = PROJECT.read_text(encoding="utf-8")
    require(re.search(r"(?:^|[>\"'])\s*[A-Za-z]:[\\/]", project_text, re.MULTILINE) is None,
            "absolute Windows path in project")
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
        "pre_change_commit=bbe00bd6909848b86ec06c0335c837d02874c3b4",
        "post_change_commit=SELF",
        "dfp=SONiX.SN32F4_DFP.1.0.1",
        "cmsis_package=ARM.CMSIS.6.2.0",
        "cmsis_core_component=6.1.1",
        "waiver_id=KNOWN_ACCEPTED_VENDOR_WARNING_SN32_DFP_1_0_1_AHB_PRESCALER",
        "warning_file=RTE/Device/SN32F407F/system_SN32F400.c",
        "warning_pack=SONiX.SN32F4_DFP_1.0.1",
        "warning_cause=possible_uninitialized_use_of_AHB_prescaler",
        "maximum_total_warnings=1",
        "required_total_errors=0",
        "required_trinity_owned_source_warnings=0",
        "generic_vendor_warning_waiver=false",
        "vendor_source_patch_allowed=false",
        "warning_suppression_allowed=false",
        "fpst_sn32f407_main.c=legacy_FPST_not_Trinity_v0.4",
        "fpst_sn32f407_dual_main.c=legacy_P1_to_MCU_to_P2_payload_relay",
        "classification=HISTORICAL_PROVENANCE_NOT_TRINITY_DEPENDENCY",
    ):
        require(required in manifest_text, f"manifest entry missing: {required}")
    require(re.search(r"(?:^|[>\"'])\s*[A-Za-z]:[\\/]", manifest_text, re.MULTILINE) is None,
            "absolute Windows path in manifest")

if EVIDENCE.is_file():
    evidence_text = EVIDENCE.read_text(encoding="utf-8")
    for required in (
        "Target device:    SN32F407F",
        "Keil µVision:     5.43.1",
        "Compiler:         ArmClang 6.24 / ARM Compiler 6",
        "ARM CMSIS pack:   6.2.0",
        "CMSIS CORE:       6.1.1",
        "SONiX SN32F4 DFP: 1.0.1",
        "Total errors:                    0",
        "Trinity-owned source warnings:   0",
        "Accepted vendor warnings:        1",
        "KNOWN_ACCEPTED_VENDOR_WARNING_SN32_DFP_1_0_1_AHB_PRESCALER",
        "RTE/Device/SN32F407F/system_SN32F400.c",
        "possible uninitialized use of AHB_prescaler",
        "Hardware programming:             NOT TESTED",
        "Hardware execution:               NOT TESTED",
        "S1+:                              NOT STARTED",
    ):
        require(required in evidence_text, f"sanitized evidence entry missing: {required}")
    for forbidden in ("License Information:", "LIC=", "E:\\", "D:\\"):
        require(forbidden not in evidence_text, f"private/raw evidence leaked: {forbidden}")

# Active dependency documents must use the validated local baseline. Historical
# donor versions are allowed only in explicit provenance sections of TOOLCHAIN
# and SOURCES.lock.
active_docs = (PROJECT, BUILD_README, TARGET, STATUS, ROOT_README)
for path in active_docs:
    if not path.is_file():
        continue
    value = path.read_text(encoding="utf-8")
    require("ARM.CMSIS.6.3.0" not in value, f"active document requires old CMSIS pack: {path.relative_to(ROOT)}")
    require("SONiX.SN32F4_DFP.1.1.1" not in value, f"active document requires old DFP: {path.relative_to(ROOT)}")
    require("0 Error(s), 0 Warning(s)" not in value, f"obsolete zero-warning acceptance: {path.relative_to(ROOT)}")
    require("zero-warning" not in value.lower(), f"obsolete zero-warning claim: {path.relative_to(ROOT)}")

if TOOLCHAIN.is_file():
    toolchain_text = TOOLCHAIN.read_text(encoding="utf-8")
    require("package `6.2.0`, CORE component `6.1.1`" in toolchain_text, "toolchain baseline CMSIS mismatch")
    require("`SONiX.SN32F4_DFP 1.0.1`" in toolchain_text, "toolchain baseline DFP mismatch")
    require("Historical donor baseline — not a Trinity dependency" in toolchain_text,
            "old donor versions are not clearly historical")

for path in ROOT.rglob("*.uvguix.*"):
    errors.append(f"forbidden user project file: {path.relative_to(ROOT)}")

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(1)

print("PASS: S0 XML locks SN32F407F, ArmClang 6.24, CMSIS 6.2.0/CORE 6.1.1 and DFP 1.0.1")
print("PASS: one Trinity application entry; legacy mains and all S1 features remain excluded")
print("PASS: memory/output options, source manifest, sanitized evidence and exact warning-waiver contract are consistent")
print("NOTE: static checks do not replace the authoritative ArmClang build log")
