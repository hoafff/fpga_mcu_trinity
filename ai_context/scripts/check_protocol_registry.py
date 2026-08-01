#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
registry = json.loads((ROOT / "ai_context/interfaces/PROTOCOL_REGISTRY_v0.1.json").read_text())

errors: list[str] = []

py_text = (ROOT / "pc_host/src/trinity_host/protocol/constants.py").read_text()
c_common = (ROOT / "sn32/include/trinity_protocol_common.h").read_text()
c_spi = (ROOT / "sn32/include/trinity_spi_protocol.h").read_text()
c_pc = (ROOT / "sn32/include/trinity_pc_protocol.h").read_text()
sv1 = (ROOT / "primer1/rtl/common/trinity_spi_pkg.sv").read_text()
sv2 = (ROOT / "primer2/rtl/common/trinity_spi_pkg.sv").read_text()

if sv1 != sv2:
    errors.append("Primer #1 and Primer #2 SPI packages differ")

def require(text: str, pattern: str, label: str) -> None:
    if re.search(pattern, text, re.MULTILINE) is None:
        errors.append(f"missing/mismatched {label}")

for name, value in registry["common"]["error_codes"].items():
    require(py_text, rf"^\s*{name}\s*=\s*0x{value:X}\s*$", f"Python error {name}")
    require(c_common, rf"TRINITY_{name}\s*=\s*0x{value:04X}", f"C error {name}")
    require(sv1, rf"ERR_{name}\s*=\s*16'h{value:04X}", f"SV error {name}")

for name, value in registry["spi"]["commands"].items():
    require(py_text, rf"^\s*{name}\s*=\s*0x{value:X}\s*$", f"Python SPI command {name}")
    require(c_spi, rf"TRINITY_SPI_{name}\s*=\s*0x{value:02X}", f"C SPI command {name}")
    require(sv1, rf"CMD_{name}\s*=\s*8'h{value:02X}", f"SV SPI command {name}")

for name, value in registry["pc"]["commands"].items():
    require(py_text, rf"^\s*{name}\s*=\s*0x{value:X}\s*$", f"Python PC command {name}")
    require(c_pc, rf"TRINITY_PC_{name}\s*=\s*0x{value:02X}", f"C PC command {name}")


for name, value in registry["spi"]["target_id"].items():
    require(py_text, rf"^\s*{name}\s*=\s*0x{value:X}\s*$", f"Python target {name}")
    require(c_spi, rf"TRINITY_TARGET_{name}\s*=\s*{value}", f"C target {name}")
    require(sv1, rf"TARGET_{name}\s*=\s*8'h{value:02X}", f"SV target {name}")

for name, value in registry["spi"]["session_state"].items():
    require(py_text, rf"^\s*{name}\s*=\s*0x{value:X}\s*$", f"Python session state {name}")
    c_suffix = name[len("SESSION_"):] if name.startswith("SESSION_") else name
    sv_suffix = c_suffix
    require(c_spi, rf"TRINITY_SESSION_{c_suffix}\s*=\s*{value}", f"C session state {name}")
    require(sv1, rf"SESSION_{sv_suffix}\s*=\s*4'd{value}", f"SV session state {name}")

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(1)
print("PASS: protocol registry matches Python, C and both SystemVerilog packages")
