# FPGA MCU Trinity — Decision Register

**Document status:** `APPROVED IMPLEMENTATION BASELINE`  
**Implementation status:** `CONTROLLED SOURCE IMPLEMENTATION OPEN`  
**Version:** `v0.4`  
**Date:** `2026-08-01`

Q01–Q100 and D01–D60 remain confirmed except where newer owner decisions below
clarify implementation status.

## New closures and amendments

### A-028 — Toolchain policy

`CONFIRMED`

- Gowin EDA `V1.9.11.03 Education x64`.
- ModelSim local primary simulator; installer observed `20.1.1.720`.
- KeilV6 project and ARM Compiler 6.
- SONIX SN32F4 DFP `1.1.1.1`, SN32F407 CMSIS library and EVK DEMO KeilV6 as
  known-good references.
- Python minimum 3.11+, GCC latest installed, Icarus optional CI.
- Exact runtime versions are acceptance evidence and do not block source.
- No toolchain change after acceptance baseline without lock update and rerun.

O-012 is policy-closed; exact evidence remains E-001.

### A-029 — SPI ICD approval

`CONFIRMED`

`SPI_CONTROL_PLANE_ICD_v0.1.md` is an approved implementation baseline.
Enum/bit registries, command registry, payloads, transaction rules, polynomial
flow and hexadecimal error registry may be implemented. O-013 is closed.

### A-030 — PC protocol ICD approval

`CONFIRMED`

`PC_SN32_PROTOCOL_ICD_v0.1.md` is an approved implementation baseline.
Mode registry is exactly KAT=0, DEMO_DETERMINISTIC=1, DEMO_SECURE=2.
`DEMO_SECURE` returns `NOT_SUPPORTED` until O-002 closes.
O-014 is closed.

### A-031 — ML-KEM backend implementation approval

`CONFIRMED`

The two per-polynomial BaseMul decomposition and SN32 void-callback error latch
may be implemented. O-015 no longer blocks source. Verification remains V-001
and requires directed plus at least 100 random coefficient-exact comparisons
against pinned mlkem-native.

### A-032 — Controlled implementation order

`CONFIRMED`

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

Final pins/CST remain forbidden until O-008. Vendor/hardware PASS remains
forbidden until O-009.

## Current open/pending

- O-002 `OPEN`: secure entropy/DEMO_SECURE.
- O-008 `PHYSICAL-PENDING`: final pins/polarity/pull/CST/wiring.
- O-009 `BUILD-PENDING`: exact Gowin/Keil/timing/resource/hardware.
- V-001 `OPEN`: BaseMul backend verification evidence.
- E-001 `OPEN`: exact runtime tool-version evidence.

Gate 1 and Gate 2 source may be committed and portable-tested now.
