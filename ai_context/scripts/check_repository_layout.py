#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
TARGETS = ("pc_host", "sn32", "primer1", "primer2", "tiny1p5")
ALLOWED_ROOT = {".git", ".github", ".gitignore", "LICENSE", "README.md", "ai_context", *TARGETS}
FORBIDDEN_ROOT = {"boards", "constraints", "docs", "rtl", "scripts", "software", "targets", "tb", "tools"}
FORBIDDEN_TARGET_NAMES = {"README.md", "README", "CONTRIBUTING.md"}
FORBIDDEN_SUFFIXES = {".axf", ".bin", ".bit", ".fs", ".hex", ".log", ".rpt", ".zip"}

REQUIRED_CONTEXT = (
    "ai_context/README_AI.md",
    "ai_context/architecture/FPGA_MCU_TRINITY_SYSTEM_SPEC_v0.4.md",
    "ai_context/decisions/FPGA_MCU_TRINITY_DECISION_REGISTER_v0.4.md",
    "ai_context/decisions/PROJECT_STRUCTURE_POLICY.md",
    "ai_context/interfaces/SPI_CONTROL_PLANE_ICD_v0.1.md",
    "ai_context/interfaces/PC_SN32_PROTOCOL_ICD_v0.1.md",
    "ai_context/interfaces/MLKEM_BACKEND_SPEC_v0.1.md",
    "ai_context/interfaces/PROTOCOL_REGISTRY_v0.1.json",
    "ai_context/status/OPEN_ITEMS.md",
    "ai_context/status/IMPLEMENTATION_STATUS.md",
    "ai_context/toolchains/TOOLCHAIN_LOCK.md",
)

FORBIDDEN_ACTIVE_LEGACY = (
    "ai_context/architecture/ARCHITECTURE_BASELINE_v1.8.md",
    "ai_context/architecture/tiny1p5-supervisor-profile-v1.1.md",
    "ai_context/decisions/FPST-v1.1-implementation-decisions.md",
    "ai_context/hardware/FPST-PRE-HARDWARE-SIGNOFF-v1.0.md",
    "ai_context/hardware/FPST-WIRING-GUIDE-v1.1.md",
)

errors: list[str] = []
root_entries = {p.name for p in ROOT.iterdir()}
for name in sorted(root_entries - ALLOWED_ROOT):
    errors.append(f"unexpected root entry: {name}")
for name in sorted(FORBIDDEN_ROOT & root_entries):
    errors.append(f"legacy root is forbidden: {name}/")

github_root = ROOT / ".github"
if github_root.exists():
    unexpected = {p.name for p in github_root.iterdir()} - {"workflows"}
    for name in sorted(unexpected):
        errors.append(f"unexpected .github entry: {name}")
    workflows = github_root / "workflows"
    if workflows.exists():
        for path in workflows.rglob("*"):
            if path.is_file() and path.suffix not in {".yml", ".yaml"}:
                errors.append(f"non-YAML workflow file: {path.relative_to(ROOT)}")

for required in ("README.md", ".gitignore", "LICENSE", "ai_context", *TARGETS):
    if not (ROOT / required).exists():
        errors.append(f"missing required root entry: {required}")

for relative in REQUIRED_CONTEXT:
    if not (ROOT / relative).is_file():
        errors.append(f"missing canonical project-memory file: {relative}")

for relative in FORBIDDEN_ACTIVE_LEGACY:
    if (ROOT / relative).exists():
        errors.append(f"legacy document remains in active context: {relative}")

handoff = ROOT / "ai_context/README_AI.md"
if handoff.is_file():
    text = handoff.read_text(encoding="utf-8")
    for required_ref in REQUIRED_CONTEXT[1:]:
        if required_ref not in text:
            errors.append(f"AI handoff does not reference canonical file: {required_ref}")

for target in TARGETS:
    target_root = ROOT / target
    manifest_path = target_root / "target.toml"
    if not manifest_path.is_file():
        errors.append(f"missing target manifest: {target}/target.toml")
        continue
    data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("target") != target:
        errors.append(f"target identity mismatch in {target}/target.toml")
    for path in target_root.rglob("*"):
        if path.is_symlink():
            errors.append(f"symlink forbidden: {path.relative_to(ROOT)}")
        if path.is_file() and path.name in FORBIDDEN_TARGET_NAMES:
            errors.append(f"target documentation forbidden: {path.relative_to(ROOT)}")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"generated artifact forbidden: {path.relative_to(ROOT)}")
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "../ai_context" in text or "..\\ai_context" in text:
                errors.append(f"deployment dependency on ai_context: {path.relative_to(ROOT)}")

required_tiny = [
    "sources.f",
    "rtl/fpst_sync_bit.sv",
    "rtl/fpst_sync_rise_pulse.sv",
    "rtl/fpst_ms_tick.sv",
    "rtl/fpst_debounce_active_low.sv",
    "rtl/fpst_heartbeat_watchdog.sv",
    "rtl/fpst_supervisor_core.sv",
    "rtl/supervisor_top.sv",
    "constraints/kiwi_tiny1p5_fpst.cst",
    "constraints/kiwi_tiny1p5_fpst.sdc",
]
for relative in required_tiny:
    if not (ROOT / "tiny1p5" / relative).is_file():
        errors.append(f"missing Tiny candidate file: tiny1p5/{relative}")

source_lines = [
    line.strip() for line in (ROOT / "tiny1p5/sources.f").read_text().splitlines()
    if line.strip() and not line.lstrip().startswith("#")
]
for relative in source_lines:
    path = (ROOT / "tiny1p5" / relative).resolve()
    try:
        path.relative_to((ROOT / "tiny1p5").resolve())
    except ValueError:
        errors.append(f"Tiny source escapes target: {relative}")
    if not path.is_file():
        errors.append(f"Tiny manifest source missing: {relative}")

required_sn32_guard = [
    "firmware/platform/sn32f407/board_profile.h",
    "firmware/platform/sn32f407/fpst_sn32f407_main.c",
    "firmware/platform/sn32f407/fpst_sn32f407_dual_main.c",
    "firmware/platform/sn32f407/fpst_sn32f407_p010_guard.c",
    "firmware/platform/sn32f407/fpst_sn32f407_p010_guard.h",
    "firmware/platform/sn32f407/fpst_sn32f407_port.c",
    "firmware/platform/sn32f407/fpst_sn32f407_port.h",
]
for relative in required_sn32_guard:
    if not (ROOT / "sn32" / relative).is_file():
        errors.append(f"missing SN32 guard candidate file: sn32/{relative}")

required_protocol = [
    "pc_host/src/trinity_host/protocol/constants.py",
    "pc_host/src/trinity_host/protocol/frame.py",
    "sn32/include/trinity_protocol_common.h",
    "sn32/include/trinity_pc_protocol.h",
    "sn32/include/trinity_spi_protocol.h",
    "primer1/rtl/common/trinity_spi_pkg.sv",
    "primer2/rtl/common/trinity_spi_pkg.sv",
]
for relative in required_protocol:
    if not (ROOT / relative).is_file():
        errors.append(f"missing protocol implementation file: {relative}")

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(1)

print("PASS: canonical target/ai_context root plus portable-CI exception")
print("PASS: project-memory v0.4 and approved protocol ICDs are indexed")
print("PASS: Tiny and SN32 guard candidate files remain present")
print("PASS: Gate 1 and Gate 2 protocol/common source files are present")
