#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BUILD="${ROOT}/ai_context/evidence/generated/tiny1p5_sim"
mkdir -p "${BUILD}"
COMMON=(
  "${ROOT}/tiny1p5/rtl/fpst_sync_bit.sv"
  "${ROOT}/tiny1p5/rtl/fpst_sync_rise_pulse.sv"
  "${ROOT}/tiny1p5/rtl/fpst_ms_tick.sv"
  "${ROOT}/tiny1p5/rtl/fpst_debounce_active_low.sv"
  "${ROOT}/tiny1p5/rtl/fpst_heartbeat_watchdog.sv"
  "${ROOT}/tiny1p5/rtl/fpst_supervisor_core.sv"
)
run_tb(){
  local name="$1"; shift
  iverilog -g2012 -Wall -s "$name" -o "${BUILD}/${name}.vvp" "${COMMON[@]}" "$@"
  vvp "${BUILD}/${name}.vvp"
}
run_tb tb_fpst_heartbeat_watchdog "${ROOT}/ai_context/testbenches/supervisor/tb_fpst_heartbeat_watchdog.sv"
run_tb tb_fpst_debounce_active_low "${ROOT}/ai_context/testbenches/supervisor/tb_fpst_debounce_active_low.sv"
run_tb tb_fpst_supervisor_core "${ROOT}/ai_context/testbenches/supervisor/tb_fpst_supervisor_core.sv"
run_tb tb_supervisor_top_open_drain \
  "${ROOT}/tiny1p5/rtl/supervisor_top.sv" \
  "${ROOT}/ai_context/testbenches/supervisor/tb_supervisor_top_open_drain.sv"
echo "PASS: Tiny 1P5 relocated source regression"
