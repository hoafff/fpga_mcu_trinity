# Implementation Status

## Baseline and gates

| Item | Status |
|---|---|
| Architecture/System Spec v0.4 | `CONFIRMED` |
| SPI ICD v0.1 | `CONFIRMED` — approved implementation baseline |
| PC↔SN32 ICD v0.1 | `CONFIRMED` — approved implementation baseline |
| ML-KEM backend mapping | `CONFIRMED` for implementation / verification `OPEN` |
| Toolchain policy | `CONFIRMED`; exact runtime evidence `OPEN` and non-blocking |
| Controlled source implementation | `OPEN` |
| Final pin/CST/wiring | `PHYSICAL-PENDING` |
| Exact vendor build/timing/hardware | `BUILD-PENDING` |

## Gate progress

| Gate | Scope | Status |
|---:|---|---|
| 1 | PC protocol/common types | `TESTED` — portable Python tests |
| 2 | SPI protocol/common types | `TESTED` — portable C tests and registry consistency |
| 3 | software ML-KEM reference backend | `OPEN` |
| 4 | Primer #1 arithmetic accelerator | `OPEN` |
| 5 | SN32 Primer #1 SPI backend | `OPEN` |
| 6 | Ascon P1/P2 | `OPEN` |
| 7 | payload UART P1→P2 | `OPEN` |
| 8 | session/commit/zeroize | `OPEN` |
| 9 | Tiny integration | `OPEN` |
| 10 | end-to-end tests | `OPEN` |

`TESTED` above is limited to portable protocol/common tests in this source commit.
It is not Gowin, Keil or hardware evidence.
