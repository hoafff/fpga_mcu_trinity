#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STARTUP = ROOT / "sn32/keil/RTE/Device/SN32F407F/startup_SN32F400.s"
PART06 = ROOT / "sn32/src/app/trinity_deploy_main_part_06.inc"
PART17 = ROOT / "sn32/src/app/trinity_deploy_main_part_17.inc"

startup = STARTUP.read_text(encoding="utf-8")
p06 = PART06.read_text(encoding="utf-8")
p17 = PART17.read_text(encoding="utf-8")

assert "Stack_Size\t\tEQU\t\t0x00000800" in startup
assert "Stack_Size\t\tEQU\t\t0x00000200" not in startup
assert "g_spi_trace.transfer_direction !=" not in p06
assert "Transport continuation is determined by the caller's canonical" in p06
assert "!g_spi_retained_failure" in p17
print("PASS: SN32 stack and observation-only SPI trace contract")
