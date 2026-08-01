# Implementation Status

## Architecture and requirements

| Item | Status | Note |
|---|---|---|
| System Specification v0.3 | `CONFIRMED` | Approved baseline; A-018 overrides storage paths only |
| Decision Register v0.3 | `CONFIRMED` | Q01–Q100, amendments and open items |
| Full-system implementation | `OPEN` | Blocked by O-001, O-003, O-004, O-005, O-006 |
| Secure-demo claim | `OPEN` | Additionally blocked by O-002 |
| Final wiring/constraints | `PHYSICAL-PENDING` | O-008 |
| Exact resource/timing result | `BUILD-PENDING` | O-009 |

## Target truth

| Target/gate | Source | Test | Exact build | Hardware |
|---|---|---|---|---|
| PC host | `NOT IMPLEMENTED` | `NOT STARTED` | `NOT STARTED` | — |
| SN32 full firmware | `NOT IMPLEMENTED` | `NOT STARTED` | `NOT STARTED` | `PHYSICAL-PENDING` |
| SN32 P0.10 guard slice | `MIGRATED` | `TESTED — INHERITED SOURCE-ONLY` | `NOT STARTED` | `PHYSICAL-PENDING` |
| Primer #1 | `NOT IMPLEMENTED` | `NOT STARTED` | `NOT STARTED` | `PHYSICAL-PENDING` |
| Primer #2 | `NOT IMPLEMENTED` | `NOT STARTED` | `NOT STARTED` | `PHYSICAL-PENDING` |
| Tiny 1P5 supervisor candidate | `MIGRATED / SELF-CONTAINED SOURCE` | `TESTED — INHERITED SOURCE-ONLY` | `BUILD-PENDING` | `PHYSICAL-PENDING` |
| P0-J19-001 migration | `COMPLETE` | `29 FILE HASH CHECK AVAILABLE` | — | `PHYSICAL-PENDING` |

Inherited evidence chỉ áp dụng cho exact accepted candidate content và đúng scope đã nêu. Di chuyển file không tạo exact-device hoặc hardware PASS.
