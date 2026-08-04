#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STARTUP = ROOT / "sn32/keil/RTE/Device/SN32F407F/startup_SN32F400.s"
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
PART00 = ROOT / "sn32/src/app/trinity_deploy_main_part_00.inc"
PART06 = ROOT / "sn32/src/app/trinity_deploy_main_part_06.inc"
PART17 = ROOT / "sn32/src/app/trinity_deploy_main_part_17.inc"
HOST_PROJECT = ROOT / "pc_host/pyproject.toml"
HOST_FACADE = ROOT / "pc_host/src/trinity_host/serial_client.py"
HOST_IMPL = ROOT / "pc_host/src/trinity_host/serial_client_impl.py"

startup = STARTUP.read_text(encoding="utf-8")
config = CONFIG.read_text(encoding="utf-8")
p00 = PART00.read_text(encoding="utf-8")
p06 = PART06.read_text(encoding="utf-8")
p17 = PART17.read_text(encoding="utf-8")
host_project = HOST_PROJECT.read_text(encoding="utf-8")
host_facade = HOST_FACADE.read_text(encoding="utf-8")

assert "Stack_Size\t\tEQU\t\t0x00000800" in startup
assert "Stack_Size\t\tEQU\t\t0x00000200" not in startup
assert "TRINITY_DEPLOY_VERSION_PATCH 26u" in config
assert "DEPLOY_BUILD_ID UINT32_C(0x0007001A)" in p00
assert "g_spi_trace.transfer_direction !=" not in p06
assert "Transport continuation is determined by the caller's canonical" in p06
assert "!g_spi_retained_failure" in p17
assert 'version = "0.3.9"' in host_project
assert "EXPECTED_SN32_BUILD_ID = 0x0007001A" in host_facade
assert "EXPECTED_SN32_VERSION = (0, 7, 26)" in host_facade
assert "exec(compile(_impl_source" in host_facade
assert HOST_IMPL.is_file()
print("PASS: SN32 v0.7.26 stack, SPI trace and host identity contract")
