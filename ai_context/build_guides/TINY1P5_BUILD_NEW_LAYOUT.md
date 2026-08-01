# Tiny 1P5 P0-J19-001 candidate exact-target build guide

**Scope:** source candidate qualification only.  
**Architecture authority:** none; use the approved v0.3 baseline and Decision Register.  
**Physical status:** `PHYSICAL-PENDING` under O-008.  
**Build status:** `BUILD-PENDING` under O-009.

Create a clean Gowin project outside generated-output folders.

- Device: `GW1N-UV1P5QN48XC7/I6`
- Top: `supervisor_top`
- Clock: 27 MHz
- Add sources in the exact order listed by `tiny1p5/sources.f`.
- Add `tiny1p5/constraints/kiwi_tiny1p5_fpst.cst` and `.sdc`.
- Do not add files under `ai_context/` to the synthesis project.
- Run synthesis, P&R and timing for report collection only.
- Do not wire or program the board from this guide.

Return synthesis/P&R/timing logs, utilization by resource class, WNS/TNS/hold,
routing congestion, unconstrained-path report and final I/O/pad report.

The candidate I/O report may be checked against the candidate constraint, but
that check does not close O-008 or authorize the inter-board route. Generated
`.fs` is an unqualified artifact until the applicable architecture, build and
physical gates pass.
