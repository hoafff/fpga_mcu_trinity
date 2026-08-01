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
| Toolchain policy | `CONFIRMED`; exact runtime evidence `OPEN` and non-blocking |
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

Gate 1/2 `TESTED` is limited to portable source tests. Gate 3 is not complete
until the pinned upstream KAT and Trinity wrapper tests actually run and pass.
No status here implies Gowin, Keil, timing, resource or hardware PASS.
