# FPGA MCU Trinity — Open Items and Closures

**Baseline:** `v0.4`  
**Date:** `2026-08-01`

## Closed / implementation-approved

| ID | Status | Result |
|---|---|---|
| O-001 | `CONFIRMED` | KDF byte-exact and collision policy |
| O-003 | `CONFIRMED` | mlkem-native v1.0.0 exact pin |
| O-004 | `CONFIRMED` | SPI header/transaction/CRC/sizing |
| O-005 | `CONFIRMED` | SESSION_COMMIT toggle |
| O-006 | `CONFIRMED` | UART idle gap 1 ms |
| O-008-L | `CONFIRMED` | logical pin mapping in `hardware/TRINITY_LOGICAL_PIN_PLAN_v0.1.md` |
| O-011 | `CONFIRMED` | PC timeout classes |
| O-012 | `CONFIRMED` | toolchain policy confirmed; exact runtime evidence pending and non-blocking |
| O-013 | `CONFIRMED` | SPI ICD v0.1 approved implementation baseline |
| O-014 | `CONFIRMED` | PC↔SN32 ICD v0.1 approved implementation baseline |
| O-015 | `CONFIRMED` | backend implementation approved; verification evidence remains pending |

## Remaining pending evidence/scope

| ID | Status | Blocks |
|---|---|---|
| O-002 | `OPEN` | DEMO_SECURE support/claim only |
| O-008-P | `PHYSICAL-PENDING` | continuity, voltage, final wiring and hardware qualification of the confirmed logical mapping |
| O-009 | `BUILD-PENDING` | Gowin/Keil/timing/resource/hardware PASS |
| V-001 | `OPEN` | claiming BaseMul accelerator backend `TESTED`; directed + >=100 random coefficient-exact differential tests |
| E-001 | `OPEN` | exact runtime tool-version evidence at build/test/acceptance |

Controlled source implementation is open. Logical pin source/CST work is
authorized, but physical and vendor-build PASS claims remain prohibited.
