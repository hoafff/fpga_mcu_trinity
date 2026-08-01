# Implementation Status

## Documentation and gates

| Item | Status | Note |
|---|---|---|
| System Specification v0.4 | `CONFIRMED` | approved D01–D60 consolidated; final consistency review required before source |
| Decision Register v0.4 | `CONFIRMED` | records closures and remaining items |
| SPI ICD v0.1 | `ASSUMED` | header confirmed; derived payload/error details O-013 |
| PC↔SN32 ICD v0.1 | `ASSUMED` | frame/registry confirmed; derived payload/event details O-014 |
| ML-KEM Backend Spec v0.1 | `ASSUMED` | exact pin/API confirmed; BaseMul/error mapping O-015 |
| Toolchain lock | `OPEN` | O-012 |
| Full integrated source | `OPEN` | do not start until owner review + O-012/O-013/O-014/O-015 closure |
| DEMO_SECURE | `OPEN` | O-002; API must return NOT_SUPPORTED |
| Final wiring/constraints | `PHYSICAL-PENDING` | O-008 |
| Exact resource/timing/hardware | `BUILD-PENDING` | O-009 |

## Target truth

| Target | Source | Portable/source test | Exact build | Hardware |
|---|---|---|---|---|
| PC host | `OPEN` | `OPEN` | — | — |
| SN32 full firmware | `OPEN` | `OPEN` | `OPEN` | `PHYSICAL-PENDING` |
| SN32 P0.10 guard slice | `TESTED` | inherited source-only | `OPEN` | `PHYSICAL-PENDING` |
| Primer #1 | `OPEN` | `OPEN` | `BUILD-PENDING` | `PHYSICAL-PENDING` |
| Primer #2 | `OPEN` | `OPEN` | `BUILD-PENDING` | `PHYSICAL-PENDING` |
| Tiny supervisor candidate | `TESTED` | inherited source-only | `BUILD-PENDING` | `PHYSICAL-PENDING` |
| P0-J19-001 migration | `TESTED` | 29-file hash checker available | — | `PHYSICAL-PENDING` |

No code target was modified by the v0.4 documentation update.
