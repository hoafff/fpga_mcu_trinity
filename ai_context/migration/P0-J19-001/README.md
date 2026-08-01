# P0-J19-001 migration into fpga_mcu_trinity

Source package: `FPST_PHASE0_P0-J19-001_SOURCE_OVERLAY_v1.0.zip`

- Package SHA-256: `510fd17e6811d76bf6cbdb929e9e207f4f1bea6ca53ec333eaef532ef1600997`
- Original baseline: `7f5cf5971da3af10d8d8c8d3d0c80b0ee59a3c27`
- Candidate inventory: exactly 23 modified + 6 new = 29 files.

This migration preserves all 29 exact file contents while placing active source
under the new targets and documentation/tests under `ai_context/`. Files whose
old paths cannot operate in the new layout, such as the old CMake and test-runner
scripts, are preserved byte-for-byte under `original_overlay/`; layout-aware
replacements are provided separately.

The migration does not authorize wiring or programming. J1-9 ↔ P0.10 remains
disconnected and the next hardware-related gate is the Tiny exact-target Gowin
build/report review.
