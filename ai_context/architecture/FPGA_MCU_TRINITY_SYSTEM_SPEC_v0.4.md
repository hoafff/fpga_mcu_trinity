# FPGA MCU Trinity — System Specification

**Document status:** `APPROVED IMPLEMENTATION BASELINE`  
**Implementation status:** `CONTROLLED SOURCE IMPLEMENTATION OPEN`  
**Version:** `v0.4`  
**Date:** `2026-08-01`

## Authority

Latest committed owner decision > this specification and Decision Register >
approved ICD/backend specifications > exact official hardware/tool documents >
source/evidence by exact scope. Legacy repo/history/migration documents are not
architectural authority.

## Architecture

```text
CONTROL: PC <-> SN32 -- shared SPI --> P1/P2
PAYLOAD: P1 == direct UART 66-byte frame ==> P2
SECURITY: SN32/P1/P2 -> Tiny; Tiny -> secure/zeroize P1/P2
```

SN32 owns the ML-KEM-512 lifecycle, KDF and session orchestration. P1 accelerates
NTT/INTT/BaseMul, encrypts with Ascon and transmits directly to P2. P2 performs
framing/session/replay/tag checks, quarantines plaintext and exposes one
authenticated result to SN32. Tiny is outside the payload plane.

All v0.3/v0.4 cryptographic, frame, replay, result-buffer, transaction, zeroize,
self-test, heartbeat and acceptance decisions remain in force.

## Normative implementation contracts

- `ai_context/interfaces/SPI_CONTROL_PLANE_ICD_v0.1.md`
- `ai_context/interfaces/PC_SN32_PROTOCOL_ICD_v0.1.md`
- `ai_context/interfaces/MLKEM_BACKEND_SPEC_v0.1.md`
- `ai_context/interfaces/PROTOCOL_REGISTRY_v0.1.json`

SPI and PC ICDs are approved implementation baselines. The ML-KEM backend is
implementation-approved and verification-pending.

## Toolchain policy

- Gowin EDA `V1.9.11.03 Education x64`.
- Gowin Programmer from the current Gowin installation.
- ModelSim local primary, installer observed `20.1.1.720`.
- KeilV6 / ARM Compiler 6.
- SONIX SN32F4 DFP `1.1.1.1`, SN32F407 CMSIS library and EVK DEMO KeilV6.
- Python latest installed with minimum 3.11+; GCC latest installed.
- Icarus is optional portable CI only.

Exact runtime versions are captured at build/test and become acceptance evidence.
They do not block source implementation.

## Implementation order

```text
1 PC protocol/common types
2 SPI protocol/common types
3 software ML-KEM reference backend
4 Primer #1 arithmetic accelerator
5 SN32 Primer #1 SPI backend
6 Ascon P1/P2
7 payload UART P1→P2
8 session/commit/zeroize
9 Tiny integration
10 end-to-end tests
```

Each gate must update implementation status and add scope-accurate tests.

## Remaining restrictions

- `DEMO_SECURE` returns `NOT_SUPPORTED` until O-002 closes.
- AI may write core logic and logical ports but may not choose final pins or CST
  while O-008 is `PHYSICAL-PENDING`.
- No Gowin, Keil, timing, resource or hardware PASS claim before O-009 evidence.
- BaseMul may be implemented but is not `TESTED` until V-001 passes directed and
  at least 100 random coefficient-exact differential tests.

## Current source milestone

Gate 1 and Gate 2 are authorized: PC binary/COBS/CRC/common types and SPI
header/CRC/enum/common types for Python, SN32 C and Primer SystemVerilog.
Portable test success does not imply vendor or hardware qualification.
