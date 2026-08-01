# P0-J19-001 migration into fpga_mcu_trinity

Source package: `FPST_PHASE0_P0-J19-001_SOURCE_OVERLAY_v1.0.zip`

- Package SHA-256: `510fd17e6811d76bf6cbdb929e9e207f4f1bea6ca53ec333eaef532ef1600997`
- Original baseline: `7f5cf5971da3af10d8d8c8d3d0c80b0ee59a3c27`
- Candidate inventory: exactly 23 modified + 6 new = 29 files.

This migration preserves all 29 exact file contents. Active source candidate files
remain inside their target or test location. Legacy architecture, decision,
hardware and build documents from the package are isolated byte-for-byte under:

```text
ai_context/migration/P0-J19-001/legacy_docs/
```

Those legacy documents are evidence/provenance only. They do not define the
current architecture, packet format, protocol, pin assignment, implementation
status or acceptance criteria. The active project memory is:

```text
ai_context/README_AI.md
ai_context/architecture/FPGA_MCU_TRINITY_SYSTEM_SPEC_v0.3.md
ai_context/decisions/FPGA_MCU_TRINITY_DECISION_REGISTER_v0.3.md
```

Files whose old paths cannot operate in the new layout remain under `original_overlay/`. `FILE_MAP.tsv` and the SHA-256 manifest track all relocated
candidate files.

The migration does not authorize wiring or programming. Physical routes remain
controlled by O-008 and exact build evidence by O-009.
