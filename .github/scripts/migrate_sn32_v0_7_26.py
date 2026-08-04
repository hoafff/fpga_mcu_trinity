#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{path}: expected one occurrence, found {count}: {old!r}"
        )
    write(path, text.replace(old, new, 1))


# Pin the exact SONiX DFP v1.0.3 startup instance and enlarge STACK from the
# hardware-proven unsafe 0x200 bytes to 0x800 bytes.
startup_url = (
    "https://raw.githubusercontent.com/ltkdt/EtherCAT_MCU_FPGA/"
    "ff803251ea35b035130cc9e2a95d55e43d5cb672/"
    "MCU_controller/RTE/Device/SN32F407F/"
    "startup_SN32F400.s.update%401.0.3"
)
startup = urlopen(startup_url, timeout=30).read().decode("utf-8")
if "@version  V1.0.3" not in startup:
    raise SystemExit("unexpected SONiX startup source version")
old_stack = "Stack_Size\t\tEQU\t\t0x00000200"
if startup.count(old_stack) != 1:
    raise SystemExit("startup source does not contain the expected 0x200 stack")
startup = startup.replace(
    old_stack, "Stack_Size\t\tEQU\t\t0x00000800", 1
)
write("sn32/keil/RTE/Device/SN32F407F/startup_SN32F400.s", startup)

replace_once(
    "sn32/config/trinity_deploy_config.h",
    "#define TRINITY_DEPLOY_VERSION_PATCH 25u",
    "#define TRINITY_DEPLOY_VERSION_PATCH 26u",
)
replace_once(
    "sn32/config/trinity_deploy_config.h",
    " * v0.7.25 uses a GPIO-driven mode-0 SPI backend on the existing DB_SPI pins.",
    " * v0.7.26 keeps the GPIO-driven mode-0 SPI backend on the existing DB_SPI pins.",
)
replace_once(
    "sn32/src/app/trinity_deploy_main_part_00.inc",
    '#error "v0.7.25 deploy requires the deterministic GPIO SPI backend"',
    '#error "v0.7.26 deploy requires the deterministic GPIO SPI backend"',
)
replace_once(
    "sn32/src/app/trinity_deploy_main_part_00.inc",
    "#define DEPLOY_BUILD_ID UINT32_C(0x00070019)",
    "#define DEPLOY_BUILD_ID UINT32_C(0x0007001A)",
)

# Real transport state is independent from diagnostic trace metadata.
replace_once(
    "sn32/src/app/trinity_deploy_main_part_01.inc",
    "    SPI_TRACE_CONTEXT_HOST_DIAGNOSTIC = 5u\n};\n\ntypedef struct {",
    "    SPI_TRACE_CONTEXT_HOST_DIAGNOSTIC = 5u\n};\n\n"
    "typedef enum {\n"
    "    SPI_TRANSPORT_PHASE_IDLE = 0u,\n"
    "    SPI_TRANSPORT_PHASE_REQUEST = 1u,\n"
    "    SPI_TRANSPORT_PHASE_RESPONSE = 2u\n"
    "} spi_transport_phase_t;\n\ntypedef struct {",
)
replace_once(
    "sn32/src/app/trinity_deploy_main_part_01.inc",
    "static volatile bool g_spi_selected;\n",
    "static volatile bool g_spi_selected;\n"
    "static volatile spi_transport_phase_t g_spi_phase;\n",
)
replace_once(
    "sn32/src/app/trinity_deploy_main_part_03.inc",
    "    g_spi_selected = false;\n}",
    "    g_spi_selected = false;\n"
    "    g_spi_phase = SPI_TRANSPORT_PHASE_IDLE;\n}",
)

p06_path = "sn32/src/app/trinity_deploy_main_part_06.inc"
p06 = read(p06_path)
replacements = [
    (
        "if (!g_spi_ready || g_spi_selected) return TRINITY_BAD_STATE;",
        "if (!g_spi_ready || g_spi_selected ||\n"
        "        g_spi_phase != SPI_TRANSPORT_PHASE_IDLE)\n"
        "        return TRINITY_BAD_STATE;",
    ),
    (
        "if (!g_spi_ready || !g_spi_selected || rx == NULL)\n"
        "        return TRINITY_BAD_STATE;",
        "if (!g_spi_ready || !g_spi_selected ||\n"
        "        g_spi_phase == SPI_TRANSPORT_PHASE_IDLE || rx == NULL)\n"
        "        return TRINITY_BAD_STATE;",
    ),
    (
        "if (g_fault || !g_spi_selected) {",
        "if (g_fault || !g_spi_selected ||\n"
        "            g_spi_phase == SPI_TRANSPORT_PHASE_IDLE) {",
    ),
    (
        "if (g_fault || !g_spi_selected)\n"
        "        return g_fault ? TRINITY_FAULT_LOCKED : TRINITY_BAD_STATE;",
        "if (g_fault || !g_spi_selected ||\n"
        "        g_spi_phase == SPI_TRANSPORT_PHASE_IDLE)\n"
        "        return g_fault ? TRINITY_FAULT_LOCKED : TRINITY_BAD_STATE;",
    ),
    (
        "if (!g_spi_ready || !g_spi_selected || tx == NULL)\n"
        "        return TRINITY_BAD_STATE;",
        "if (!g_spi_ready || !g_spi_selected ||\n"
        "        g_spi_phase != SPI_TRANSPORT_PHASE_REQUEST || tx == NULL)\n"
        "        return TRINITY_BAD_STATE;",
    ),
    (
        "if (!g_spi_ready || !g_spi_selected)\n"
        "        return TRINITY_BAD_STATE;",
        "if (!g_spi_ready || !g_spi_selected ||\n"
        "        g_spi_phase != SPI_TRANSPORT_PHASE_RESPONSE)\n"
        "        return TRINITY_BAD_STATE;",
    ),
    (
        "        } else if (g_spi_trace.transfer_direction !=\n"
        "                   SPI_TRANSFER_DIRECTION_RESPONSE) {\n"
        "            return TRINITY_BAD_STATE;\n"
        "        }\n",
        "        }\n",
    ),
    (
        "static trinity_error_code_t spi_select(const endpoint_t *ep) {\n",
        "static trinity_error_code_t spi_select(\n"
        "    const endpoint_t *ep, spi_transport_phase_t phase) {\n",
    ),
    (
        "if (ep == NULL || !g_spi_ready || g_spi_selected || g_fault)\n"
        "        return TRINITY_BAD_STATE;",
        "if (ep == NULL || !g_spi_ready || g_spi_selected || g_fault ||\n"
        "        g_spi_phase != SPI_TRANSPORT_PHASE_IDLE ||\n"
        "        (phase != SPI_TRANSPORT_PHASE_REQUEST &&\n"
        "         phase != SPI_TRANSPORT_PHASE_RESPONSE))\n"
        "        return TRINITY_BAD_STATE;",
    ),
    (
        "    g_spi_selected = true;\n    spi_guard_delay();",
        "    g_spi_selected = true;\n"
        "    g_spi_phase = phase;\n"
        "    spi_guard_delay();",
    ),
]
for old, new in replacements:
    count = p06.count(old)
    if count != 1:
        raise SystemExit(
            f"{p06_path}: expected one occurrence, found {count}: {old!r}"
        )
    p06 = p06.replace(old, new, 1)
write(p06_path, p06)

replace_once(
    "sn32/src/app/trinity_deploy_main_part_07.inc",
    "    rc = spi_select(ep);\n"
    "    if (rc == TRINITY_OK) {\n"
    "        rc = spi_read_response_segment",
    "    rc = spi_select(ep, SPI_TRANSPORT_PHASE_RESPONSE);\n"
    "    if (rc == TRINITY_OK) {\n"
    "        rc = spi_read_response_segment",
)
replace_once(
    "sn32/src/app/trinity_deploy_main_part_07.inc",
    "    rc = spi_select(ep);\n"
    "    if (rc == TRINITY_OK)\n"
    "        rc = spi_write_request_bytes",
    "    rc = spi_select(ep, SPI_TRANSPORT_PHASE_REQUEST);\n"
    "    if (rc == TRINITY_OK)\n"
    "        rc = spi_write_request_bytes",
)
replace_once(
    "sn32/src/app/trinity_deploy_main_part_07.inc",
    "        spi_retain_current_trace(true);\n    }\n}",
    "        spi_retain_current_trace(true);\n"
    "        /* Stop background SPI after the first active failure. */\n"
    "        g_automatic_probe_active = false;\n"
    "    }\n}",
)
replace_once(
    "sn32/src/app/trinity_deploy_main_part_16.inc",
    "    g_fault = g_spi_selected = false;\n",
    "    g_fault = g_spi_selected = false;\n"
    "    g_spi_phase = SPI_TRANSPORT_PHASE_IDLE;\n",
)
replace_once(
    "sn32/src/app/trinity_deploy_main_part_17.inc",
    "        if (!g_fault && !g_host_txn.valid &&\n",
    "        if (!g_fault && !g_spi_retained_failure &&\n"
    "            !g_host_txn.valid &&\n",
)

replace_once("sn32/keil/SOURCES.lock", "stack_bytes=0x200", "stack_bytes=0x800")
replace_once(
    "sn32/keil/SOURCES.lock",
    "sn32/keil/README_BUILD.md=updated\n",
    "sn32/keil/README_BUILD.md=updated\n"
    "sn32/keil/RTE/Device/SN32F407F/startup_SN32F400.s="
    "tracked_v1.0.3_stack_0x800\n",
)
readme_build = read("sn32/keil/README_BUILD.md")
stack_note = """

## Deploy stack lock (v0.7.26)

The deploy target must compile the tracked startup instance
`RTE/Device/SN32F407F/startup_SN32F400.s` with
`Stack_Size = 0x00000800` (2048 bytes). The v0.7.25 hardware map proved
that the vendor-default 0x200-byte stack was smaller than the linker's
1000-byte-plus-unknown maximum and immediately adjacent to `g_spi_trace`.
Do not accept a pack merge that restores 0x00000200.
"""
if "## Deploy stack lock (v0.7.26)" not in readme_build:
    write("sn32/keil/README_BUILD.md", readme_build.rstrip() + stack_note + "\n")

replace_once("pc_host/pyproject.toml", 'version = "0.3.8"', 'version = "0.3.9"')
replace_once(
    "pc_host/src/trinity_host/serial_client.py",
    "EXPECTED_SN32_BUILD_ID = 0x00070019\nEXPECTED_SN32_VERSION = (0, 7, 25)",
    "EXPECTED_SN32_BUILD_ID = 0x0007001A\nEXPECTED_SN32_VERSION = (0, 7, 26)",
)
replace_once(
    "pc_host/src/trinity_host/cli.py",
    "from .protocol import HostCommand, SpiCommand, SystemStatus, TargetId",
    "from .protocol import (\n"
    "    HostCommand, SPI_CRC_SIZE, SPI_HEADER_SIZE, SPI_MAX_PACKET,\n"
    "    SpiCommand, SystemStatus, TargetId,\n"
    ")",
)
replace_once(
    "pc_host/src/trinity_host/cli.py",
    "            trace.response_frame_length != 0\n"
    "            and trace.response_crc_received == trace.response_crc_calculated\n",
    "            trace.response_frame_length >= SPI_HEADER_SIZE + SPI_CRC_SIZE\n"
    "            and trace.response_capture_length == trace.response_frame_length\n"
    "            and trace.response_crc_received == trace.response_crc_calculated\n",
)
replace_once(
    "pc_host/src/trinity_host/cli.py",
    "    transfer_stage_raw, transfer_direction_raw = extension[:2]\n",
    "    transfer_stage_raw, transfer_direction_raw = extension[:2]\n"
    "    if transfer_stage_raw not in _SPI_TRANSFER_STAGE_NAMES:\n"
    "        raise HostProtocolError(\n"
    "            f\"invalid SPI transfer stage {transfer_stage_raw}\"\n"
    "        )\n"
    "    if transfer_direction_raw not in _SPI_TRANSFER_DIRECTION_NAMES:\n"
    "        raise HostProtocolError(\n"
    "            f\"invalid SPI transfer direction {transfer_direction_raw}\"\n"
    "        )\n",
)
replace_once(
    "pc_host/src/trinity_host/cli.py",
    "    transfer: dict[str, object] = {\n",
    "    if (transfer_length > SPI_MAX_PACKET or\n"
    "            transfer_completed > transfer_length or\n"
    "            transfer_byte_index > transfer_length):\n"
    "        raise HostProtocolError(\n"
    "            \"invalid SPI transfer progress telemetry\"\n"
    "        )\n"
    "    transfer: dict[str, object] = {\n",
)
replace_once(
    "pc_host/src/trinity_host/cli.py",
    "        sample_count = extension[28]\n"
    "        expected_extension_length = 32 + sample_count * 12\n",
    "        sample_count = extension[28]\n"
    "        if sample_count > 8:\n"
    "            raise HostProtocolError(\n"
    "                f\"invalid SPI response sample count {sample_count}\"\n"
    "            )\n"
    "        expected_extension_length = 32 + sample_count * 12\n",
)
replace_once(
    "pc_host/src/trinity_host/cli.py",
    "        if spi_ctrl0 == 0x4750494F:\n"
    "            transfer[\"spi_backend\"] = \"GPIO_MODE0\"\n",
    "        if spi_ctrl0 == 0x4750494F:\n"
    "            if spi_ctrl1 == 0 or spi_clkdiv == 0:\n"
    "                raise HostProtocolError(\n"
    "                    \"invalid GPIO SPI timing telemetry\"\n"
    "                )\n"
    "            transfer[\"spi_backend\"] = \"GPIO_MODE0\"\n",
)

target = read("sn32/target.toml")
targeted = {
    'implementation_status = "V0_7_25_CORRECTED_P1_P2_CONTROL_PLANE_SOURCE_READY"':
        'implementation_status = "V0_7_26_STACK_AND_SPI_STATE_CORRECTION_SOURCE_READY"',
    'current_main_exact_target_build = "REBUILD_REQUIRED_FOR_V0_7_25_CORRECTED_CONTROL_PLANE_IMAGE"':
        'current_main_exact_target_build = "REBUILD_REQUIRED_FOR_V0_7_26_STACK_AND_SPI_STATE_IMAGE"',
    'dual_spi_hardware = "PENDING_CORRECTED_P1_P2_REBUILD_PROGRAM_AND_V0_7_25_ONE_SHOT"':
        'dual_spi_hardware = "PENDING_SN32_V0_7_26_REBUILD_PROGRAM_AND_ONE_SHOT"',
    'qualification_build_id = "0x00070019"':
        'qualification_build_id = "0x0007001A"',
    'qualification_architecture_version = "0.7.25"':
        'qualification_architecture_version = "0.7.26"',
    'qualification_periodic_probe_after_first_failure = true':
        'qualification_periodic_probe_after_first_failure = false',
}
for old, new in targeted.items():
    if target.count(old) != 1:
        raise SystemExit(f"sn32/target.toml missing unique field: {old}")
    target = target.replace(old, new, 1)
if "qualification_stack_bytes" not in target:
    target = target.replace(
        "qualification_spi_half_period_cycles = 60\n",
        "qualification_spi_half_period_cycles = 60\n"
        "qualification_stack_bytes = 2048\n"
        "qualification_transport_state = "
        '"DEDICATED_PHASE_NOT_DIAGNOSTIC_TRACE"\n',
        1,
    )
write("sn32/target.toml", target)

# Update current static gates and host tests, not historical hardware evidence.
gate_path = "sn32/tests/deploy/check_dual_spi_gate_profile.py"
gate = read(gate_path)
gate = gate.replace("(0, 7, 25)", "(0, 7, 26)")
gate = gate.replace("v0.7.25", "v0.7.26")
gate = gate.replace("V0.7.25", "V0.7.26")
gate = gate.replace("0x00070019", "0x0007001A")
write(gate_path, gate)

for path in (ROOT / "pc_host/tests").rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    text = text.replace("0x00070019", "0x0007001A")
    text = text.replace("(0, 7, 25)", "(0, 7, 26)")
    path.write_text(text, encoding="utf-8", newline="\n")

checker = r'''#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

def require(path: str, token: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    if token not in text:
        raise SystemExit(f"FAIL: {path} missing {token}")

def forbid(path: str, token: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    if token in text:
        raise SystemExit(f"FAIL: {path} contains forbidden {token}")

require("sn32/keil/RTE/Device/SN32F407F/startup_SN32F400.s",
        "Stack_Size\t\tEQU\t\t0x00000800")
require("sn32/config/trinity_deploy_config.h",
        "#define TRINITY_DEPLOY_VERSION_PATCH 26u")
require("sn32/src/app/trinity_deploy_main_part_00.inc",
        "#define DEPLOY_BUILD_ID UINT32_C(0x0007001A)")
require("sn32/src/app/trinity_deploy_main_part_01.inc",
        "SPI_TRANSPORT_PHASE_RESPONSE")
require("sn32/src/app/trinity_deploy_main_part_01.inc",
        "static volatile spi_transport_phase_t g_spi_phase;")
require("sn32/src/app/trinity_deploy_main_part_06.inc",
        "g_spi_phase != SPI_TRANSPORT_PHASE_RESPONSE")
require("sn32/src/app/trinity_deploy_main_part_07.inc",
        "spi_select(ep, SPI_TRANSPORT_PHASE_RESPONSE)")
require("sn32/src/app/trinity_deploy_main_part_07.inc",
        "spi_select(ep, SPI_TRANSPORT_PHASE_REQUEST)")
forbid("sn32/src/app/trinity_deploy_main_part_06.inc",
       "g_spi_trace.transfer_direction !=")
require("sn32/src/app/trinity_deploy_main_part_17.inc",
        "!g_spi_retained_failure")
require("pc_host/pyproject.toml", 'version = "0.3.9"')
require("pc_host/src/trinity_host/serial_client.py",
        "EXPECTED_SN32_BUILD_ID = 0x0007001A")
require("pc_host/src/trinity_host/cli.py",
        "trace.response_capture_length == trace.response_frame_length")
print("PASS: v0.7.26 stack and SPI transport-state contract")
'''
write("sn32/tests/deploy/check_v0_7_26_stack_spi_state.py", checker)
