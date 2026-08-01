# Tiny 1P5 exact-target build from the new layout

Create a clean Gowin project outside generated-output folders.

- Device: `GW1N-UV1P5QN48XC7/I6`
- Top: `supervisor_top`
- Clock: 27 MHz
- Add sources in the exact order listed by `tiny1p5/sources.f`.
- Add `tiny1p5/constraints/kiwi_tiny1p5_fpst.cst` and `.sdc`.
- Do not add files under `ai_context/` to the synthesis project.
- Run synthesis, P&R and timing; do not program the board yet.

Return the complete synthesis/P&R/timing logs, utilization, unconstrained-path
report and final I/O/pad report. The `tiny_fault_no` row must show pin 12,
LVCMOS33, open-drain enabled and no internal pull. An emitted `.fs` remains an
unqualified generated artifact and must not be committed or programmed.
