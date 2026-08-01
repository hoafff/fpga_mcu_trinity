#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = (
    "ai_context/interfaces/README.md",
    "ai_context/interfaces/SPI_CONTROL_PLANE_PAYLOAD_DETAIL_v0.1.md",
    "ai_context/interfaces/PC_SN32_PROTOCOL_PAYLOAD_DETAIL_v0.1.md",
    "ai_context/interfaces/MLKEM_BACKEND_API_DETAIL_v0.1.md",
    "ai_context/baseline_detail/README.md",
    "ai_context/baseline_detail/FPGA_MCU_TRINITY_SYSTEM_REQUIREMENTS_DETAIL_v0.4.md",
    "ai_context/baseline_detail/FPGA_MCU_TRINITY_DECISION_DETAIL_v0.4.md",
)

errors = [path for path in REQUIRED if not (ROOT / path).is_file()]
handoff = (ROOT / "ai_context/README_AI.md").read_text(encoding="utf-8")
for path in REQUIRED:
    if path not in handoff:
        errors.append(f"handoff missing reference: {path}")

for index in ("ai_context/interfaces/README.md", "ai_context/baseline_detail/README.md"):
    text = (ROOT / index).read_text(encoding="utf-8")
    if "supersed" not in text.lower() or "status" not in text.lower():
        errors.append(f"precedence/status note incomplete: {index}")

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(1)
print("PASS: detailed requirements, decisions and interface payload context are indexed")
