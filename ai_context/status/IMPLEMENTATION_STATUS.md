# Implementation Status

## Baseline and evidence gates

| Item | Status |
|---|---|
| Architecture/System Spec v0.4 | `CONFIRMED` |
| SPI ICD v0.1 | `CONFIRMED` — approved implementation baseline |
| PC↔SN32 ICD v0.1 | `CONFIRMED` — approved implementation baseline |
| ML-KEM backend mapping | `CONFIRMED` for implementation / verification `OPEN` |
| Logical pin mapping | `CONFIRMED` |
| Physical pin/wiring qualification | `PHYSICAL-PENDING` |
| Toolchain policy | `CONFIRMED`; S0 project locks donor versions |
| SN32 S0 exact-target Keil project | `IMPLEMENTED / BUILD-PENDING` |
| Exact vendor build/timing/hardware | `BUILD-PENDING` |

## Gate progress

| Gate | Scope | Status |
|---:|---|---|
| 1 | PC protocol/common types | `TESTED` — portable Python scope |
| 2 | SPI protocol/common types | `TESTED` — portable C/registry scope |
| 3 | SN32 pinned ML-KEM reference/backend | `OPEN` — source and remote verification gate staged |
| 4 | Primer #1 arithmetic accelerator | `OPEN` |
| 5 | SN32 Primer #1 SPI backend | `OPEN` |
| 6 | Ascon P1/P2 | `OPEN` |
| 7 | payload UART P1→P2 | `OPEN` |
| 8 | session/commit/zeroize | `OPEN` |
| 9 | Tiny integration | `OPEN` |
| 10 | end-to-end tests | `OPEN` |

## SN32 milestone progress

| Milestone | Scope | Status |
|---:|---|---|
| S0 | clean exact-target Keil project | `SOURCE IMPLEMENTED / USER KEIL BUILD PENDING` |
| S1+ | GPIO, UART, protocol and later integration | `NOT STARTED` |

S0 compiles only the new `trinity_main.c` plus SONiX pack startup/system sources.
UART, SPI, ML-KEM, Tiny session commit and DEMO_SECURE remain compile-time
disabled. Gate 1/2 `TESTED` remains limited to portable source tests. No status
here implies Gowin, Keil, timing, resource, programming or hardware PASS.
