# FPGA MCU Trinity — Project Memory / AI Handoff

**Status:** `CONTROLLED SOURCE IMPLEMENTATION OPEN`  
**Baseline:** `v0.4`

Read in order:

1. `ai_context/architecture/FPGA_MCU_TRINITY_SYSTEM_SPEC_v0.4.md`
2. `ai_context/decisions/FPGA_MCU_TRINITY_DECISION_REGISTER_v0.4.md`
3. `ai_context/interfaces/SPI_CONTROL_PLANE_ICD_v0.1.md`
4. `ai_context/interfaces/PC_SN32_PROTOCOL_ICD_v0.1.md`
5. `ai_context/interfaces/MLKEM_BACKEND_SPEC_v0.1.md`
6. `ai_context/interfaces/PROTOCOL_REGISTRY_v0.1.json`
7. `ai_context/status/OPEN_ITEMS.md`
8. `ai_context/status/IMPLEMENTATION_STATUS.md`
9. `ai_context/toolchains/TOOLCHAIN_LOCK.md`
10. `ai_context/decisions/PROJECT_STRUCTURE_POLICY.md`
11. the active target's `target.toml`

Current implementation sequence is Gate 1 through Gate 10 as recorded in the
Decision Register. Gate 1 and Gate 2 protocol/common source are present.

Never choose final pins/CST while O-008 is pending. Never claim Gowin/Keil/timing/
hardware PASS without O-009 evidence. `DEMO_SECURE` stays `NOT_SUPPORTED` until
O-002 closes. BaseMul implementation is allowed but verification remains V-001.

Legacy repo/history and `ai_context/migration/` are provenance only.
