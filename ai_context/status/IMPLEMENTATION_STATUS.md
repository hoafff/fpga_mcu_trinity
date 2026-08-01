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
| SN32 S0 toolchain/pack lock | `CONFIRMED` — validated local environment |
| SN32 S0 project structure | `PASS` |
| SN32F407F compile/link | `PASS` |
| SN32 S0 AXF/HEX/MAP generation | `PASS` |
| SN32 S0 memory layout | `PASS` |
| SN32 S0 warning policy | `PASS` — 0 Trinity warnings; 1 exact vendor warning accepted |
| SN32 hardware programming/execution | `NOT TESTED` |
| Gowin/timing/integrated hardware | `BUILD-PENDING / PHYSICAL-PENDING` |

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
| S0 | clean exact-target Keil project | `BUILD VALIDATED / HARDWARE NOT TESTED` |
| S1+ | GPIO, UART, protocol and later integration | `NOT STARTED` |

Exact S0 status:

```text
S0 project structure:              PASS
SN32F407F compile/link:            PASS
AXF/HEX/MAP generation:           PASS
Memory layout:                    PASS
Exact current-environment lock:   PASS
Trinity-owned source warnings:    PASS — 0
Known vendor warning:             ACCEPTED — 1
Hardware programming:             NOT TESTED
Hardware execution:               NOT TESTED
S1+:                              NOT STARTED
```

The accepted warning is restricted to `system_SN32F400.c` from
`SONiX.SN32F4_DFP 1.0.1`, for the possible uninitialized use of
`AHB_prescaler`. No generic vendor-warning waiver exists. UART, SPI, ML-KEM,
Tiny session commit and DEMO_SECURE remain compile-time disabled. No status here
implies Gowin, timing, programming, hardware or full-deployment PASS.
