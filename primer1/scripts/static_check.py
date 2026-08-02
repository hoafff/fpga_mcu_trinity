#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
required = [line.strip() for line in (root / "sources.f").read_text().splitlines() if line.strip()]
core_parts = [f"rtl/core/primer1_command_core_part_{i}.svh" for i in range(6)]
tracked_sources = required + core_parts

for rel in tracked_sources:
    path = root / rel
    assert path.is_file(), f"missing source: {rel}"
    text = path.read_text()
    assert not re.search(r"[A-Za-z]:[\\/]|/home/|/Users/", text), f"absolute path in {rel}"

core_main = (root / "rtl/core/primer1_command_core.sv").read_text()
for i, rel in enumerate(core_parts):
    assert f'`include "primer1_command_core_part_{i}.svh"' in core_main
core_text = "\n".join((root / rel).read_text() for rel in core_parts)
all_text = "\n".join(
    core_text if rel == "rtl/core/primer1_command_core.sv" else (root / rel).read_text()
    for rel in required
)

for module in [
    "primer1_top", "spi_packet_endpoint", "mlkem_poly_accel",
    "ascon_aead128_encrypt", "uart_frame_tx", "uart_tx_byte",
    "primer1_command_core",
]:
    assert re.search(rf"\bmodule\s+{module}\b", all_text), f"missing module {module}"

for token in [
    "CMD_POLY_EXECUTE", "CMD_ENCRYPT_AND_SEND", "SESSION_COMMITTED_BLOCKED",
    "secure_enable_i", "zeroize_ni", "uart_tx_o", "retained_fingerprint",
    "heartbeat_o", "fault_o",
]:
    assert token in all_text, f"missing mandatory token {token}"

for rel in required:
    text = core_text if rel == "rtl/core/primer1_command_core.sv" else (root / rel).read_text()
    assert len(re.findall(r"\bmodule\b", text)) == len(re.findall(r"\bendmodule\b", text)), f"module imbalance {rel}"
    assert len(re.findall(r"\bbegin\b", text)) >= len(re.findall(r"\bendcase\b", text)), f"structural imbalance {rel}"

# Canonical exact-device project identity and portable relative paths.
gprj = (root / "gowin/trinity_primer1.gprj").read_text()
assert '<Device name="GW2A-18C" pn="GW2A-LV18PG256C8/I7">gw2a18c-011</Device>' in gprj
assert not re.search(r"[A-Za-z]:[\\/]", gprj), "absolute path in canonical gprj"
for rel in required:
    assert f'path="../{rel}"' in gprj, f"gprj missing {rel}"
for rel in ["constraints/primer1.cst", "constraints/primer1.sdc"]:
    assert f'path="../{rel}"' in gprj, f"gprj missing {rel}"

# Both Gowin process-config names are committed because V1.9.11.03 may consult
# either the generic or project-specific file when opening a pre-existing gprj.
for rel in [
    "gowin/impl/project_process_config.json",
    "gowin/impl/trinity_primer1_process_config.json",
]:
    config = json.loads((root / rel).read_text())
    assert config["TopModule"] == "primer1_top"
    assert config["Verilog_Standard"] == "Vlg_Std_Sysv2017"
    assert config["IncludePath"] == ["../rtl/core"]
    assert config["Resource_Sharing"] is True
    assert config["Replicate_Resources"] is False

run_tcl = (root / "gowin/run.tcl").read_text()
assert "set_device -name GW2A-18C GW2A-LV18PG256C8/I7" in run_tcl
assert "set_option -verilog_std sysv2017" in run_tcl
assert "set_option -include_path {../rtl/core}" in run_tcl
assert not re.search(r"[A-Za-z]:[\\/]", run_tcl)

target = (root / "target.toml").read_text()
assert 'device_database_name = "GW2A-18C"' in target
assert 'device_database_id = "gw2a18c-011"' in target

# Resource architecture checks: one shared modular multiplier, iterative Ascon,
# sequential CRC32C, shift-register UART frame serializer, and sequential chunk validation.
accel = (root / "rtl/crypto/mlkem_poly_accel.sv").read_text()
assert accel.count("mul_result = montgomery_reduce") == 1, "modular multiplier is not shared"
assert "P_NTT_MUL" in accel and "P_INTT_MUL" in accel and "P_BM0_M6" in accel
assert accel.count("poly_a [0:255]") == 1 and accel.count("poly_b [0:255]") == 1
assert "ram_style = \"block\"" in accel
assert "function automatic logic signed [15:0] fqmul" not in accel, "parallel fqmul datapaths remain"

# GW2A-18C does not support DPB read-before-write mode (WRITE_MODE=2'b10).
# Each inferred DPB port must hold its output register during a write, matching
# normal/no-change mode, and the arithmetic FSM must keep separate read/write phases.
for write_enable, memory, address, output in [
    ("a_we0", "poly_a", "a_addr0", "a_q0"),
    ("a_we1", "poly_a", "a_addr1", "a_q1"),
    ("b_we0", "poly_b", "b_addr0", "b_q0"),
    ("b_we1", "poly_b", "b_addr1", "b_q1"),
]:
    pattern = (
        rf"if\s*\({write_enable}\)\s*"
        rf"{memory}\[{address}\]\s*<=\s*[^;]+;\s*"
        rf"else\s*{output}\s*<=\s*{memory}\[{address}\];"
    )
    assert re.search(pattern, accel, re.S), f"unsupported DPB write template on {write_enable}"
assert "read_start_hold" not in accel, "dead prefetch control returned"
for read_state, write_state in [
    ("P_NTT_READ", "P_NTT_WRITE"),
    ("P_INTT_READ", "P_INTT_WRITE"),
    ("P_SCALE_READ", "P_SCALE_WRITE"),
    ("P_BM0_READ", "P_BM0_WRITE"),
    ("P_BM1_READ", "P_BM1_WRITE"),
]:
    assert read_state in accel and write_state in accel, f"missing separated RAM phases: {read_state}/{write_state}"

ascon = (root / "rtl/crypto/ascon_aead128_encrypt.sv").read_text()
assert "round_index" in ascon and "ascon_round(x0, x1, x2, x3, x4" in ascon
assert ascon.count("ascon_round(") == 2, "Ascon rounds appear unrolled"

spi = (root / "rtl/io/spi_packet_endpoint.sv").read_text()
core = core_text
assert "crc32c_update_byte" in spi and "request_fingerprint_o" in spi
assert "build_payload_shift[7:0]" in spi and "build_payload[8*(index-8) +: 8]" not in spi
assert "function automatic logic [31:0] request_fingerprint" not in core
assert "request_fingerprint_i" in core
assert "chunk_coefficients_valid" not in core
compact = core.replace(" ", "").replace("\n", "")
assert "saved_chunk_data<={16'd0,saved_chunk_data[511:16]}" in compact
for exact in [
    "saved_chunk_slot<=request_payload_i[0]",
    "saved_chunk_index<=request_payload_i[10:8]",
    "saved_read_slot<=request_payload_i[0]",
    "saved_read_chunk<=request_payload_i[10:8]",
    "poly_read_slot<=request_payload_i[0]",
]:
    assert exact in compact, f"missing explicit slice: {exact}"

uart_frame = (root / "rtl/io/uart_frame_tx.sv").read_text()
assert "byte_data <= frame_shift[7:0]" in uart_frame
assert "frame_reg[8*byte_index +: 8]" not in uart_frame
uart_byte = (root / "rtl/io/uart_tx_byte.sv").read_text()
assert "logic [31:0] baud_acc" in uart_byte
assert "CLOCK_HZ_U - BAUD_U" in uart_byte

print("PASS source_manifest")
print("PASS no_absolute_paths")
print("PASS mandatory_blocks_present")
print("PASS exact_device_identity")
print("PASS canonical_systemverilog_config")
print("PASS shared_iterative_resource_architecture")
print("PASS gowin_dpb_normal_write_template")
print("PASS no_read_during_write_dependency_guard")
print("PASS explicit_width_and_slice_guards")
print("PASS basic_structural_checks")
