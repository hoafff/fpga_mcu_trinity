# FPGA MCU Trinity — Project Memory / AI Handoff

**Status:** `IMPLEMENTATION DECISIONS CONSOLIDATED / SOURCE NOT STARTED`  
**Current baseline:** v0.4  
**Purpose:** mandatory first read for every new AI/chat/member.

## 1. Read order

1. `ai_context/architecture/FPGA_MCU_TRINITY_SYSTEM_SPEC_v0.4.md`
2. `ai_context/decisions/FPGA_MCU_TRINITY_DECISION_REGISTER_v0.4.md`
3. `ai_context/interfaces/SPI_CONTROL_PLANE_ICD_v0.1.md`
4. `ai_context/interfaces/PC_SN32_PROTOCOL_ICD_v0.1.md`
5. `ai_context/interfaces/MLKEM_BACKEND_SPEC_v0.1.md`
6. `ai_context/status/OPEN_ITEMS.md`
7. `ai_context/status/IMPLEMENTATION_STATUS.md`
8. `ai_context/toolchains/TOOLCHAIN_LOCK.md`
9. `ai_context/decisions/PROJECT_STRUCTURE_POLICY.md`
10. target `target.toml` when working on a target.

## 2. Architecture

```text
CONTROL: PC <-> SN32 -- shared SPI --> P1/P2
PAYLOAD: P1 == direct UART 66-byte frame ==> P2
SECURITY: SN32/P1/P2 -> Tiny; Tiny -> secure/zeroize P1/P2
```

SN32 runs full ML-KEM-512 lifecycle and KDF. P1 accelerates NTT/INTT/BaseMul,
performs Ascon encrypt and UART TX. P2 receives, checks replay/tag, quarantines
plaintext and exposes one authenticated result via SPI. Tiny supervises only.

## 3. Locked highlights

- mlkem-native v1.0.0 commit `048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa`.
- KDF exact: `SHAKE256("TRINITY-KDF-v1" || 00 || SS32 || SHA3-256(CT768), 28)`.
- SPI header 8 B, txid16 BE, polynomial data 64 B, payload 66 B, packet 76 B.
- P1→P2: `A5 5A || AD24 || C24 || TAG16`, no CRC, 20 ms timeout, 1 ms gap.
- SESSION_COMMIT uses toggle; heartbeat qualified 500 ms before commit.
- PC protocol: binary/CRC16/COBS/00, async events txid 0.
- Keep Git history; `.github/workflows/` portable-only CI is allowed.

## 4. Do not start full source yet

Before source integration, owner must review/close:

```text
O-012 exact toolchain versions
O-013 derived SPI command payloads/error numeric table
O-014 derived PC command payloads/event envelope
O-015 mlkem-native BaseMul/error-latch mapping
```

O-002 blocks secure-demo claim only. O-008 blocks final pin/CST/wiring. O-009
closes only after exact build/hardware evidence.

## 5. Current implementation truth

PC host, full SN32 firmware, P1 and P2 are not implemented. Tiny and SN32 P0.10
guard only have inherited source-only evidence. No exact vendor or hardware PASS.

## 6. Authority

Latest committed owner decision > current spec/register/ICDs > official hardware
and pinned upstream docs > source/evidence by exact scope. Repo
`fpga-pqc-secure-telemetry`, Git history and `ai_context/migration/` are reference
or provenance only.
