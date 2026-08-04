# SN32 -> P1/P2 dual-SPI hardware qualification — v0.7.24

## Scope and decision

This gate qualifies the SN32F407 controller path to Primer #1 and Primer #2 on
the shared mode-0 SPI wires with independent CS and IRQ signals.

Only after the one-shot command reaches its final PASS line may the result be
recorded as:

```text
SN32 -> P1/P2 DUAL-SPI CONTROL PLANE HARDWARE: PASS
```

This gate does not qualify session activation, P1-to-P2 UART telemetry, Tiny,
live ML-KEM session creation or the full system.

## Why v0.7.24 keeps the deterministic transport and fixes qualification evidence

The v0.7.19–v0.7.22 hardware evidence proved all of the following:

- SN32's canonical request buffer contained the correct ten-byte frame and CRC;
- P1 sometimes captured only four or nine bytes, including CRC-valid
  `BAD_LENGTH` diagnostics;
- the same P1/P2 RTL and packet protocol passed with the ESP32-C3 controller;
- delay, FIFO reset, `NEW_TH_EN`, mailbox reread and bounded request replay did
  not make the SPI0 polling path deterministic;
- `system-status` liveness itself is fixed and passed 20/20 status plus 20/20
  immediate ping operations on v0.7.22.

v0.7.23 therefore disabled SPI0 for the deploy path and drove the existing
P1.0/P1.1/P1.2 DB_SPI pins directly as GPIO mode-0, MSB-first SPI. It retains
the same physical wiring, packet bytes, CRC, CS/IRQ ownership, timeout policy,
mailbox validation and non-replay rule for side-effect operations.

The first v0.7.23 one-shot run proved the startup probe and accepted live
transaction were functional, but the redundant trace mirror reported
`magic=0x04` after the canonical request/response buffers had already passed
local decode and CRC. v0.7.24 therefore serializes live qualification evidence
from those exact canonical accepted buffers. Retained first-failure history
continues to use its immutable snapshot. The host also distinguishes request
from response corruption and includes both raw frames in any failure line.

## Required image identities

```text
SN32 architecture_version = 0.7.24
SN32 build_id             = 0x00070018
Primer #1 build_id        = 0x5031D002
Primer #2 build_id        = 0x50320001
```

## Build and flash

From the repository root:

```bat
git pull --ff-only origin main
git submodule update --init --recursive
git rev-parse HEAD
git status --short
py -m pip install -e pc_host
```

Open and rebuild:

```text
sn32/keil/trinity_sn32f407_deploy.uvprojx
```

Accept only:

```text
0 Error(s), 0 Warning(s)
Flash fit: PASS
RAM fit: PASS
AXF/HEX generated
Programming Done
Verify OK
```

P1 and P2 do not need a new bitstream for this gate.

## Cold-boot sequence

1. Power off SN32, P1 and P2.
2. Keep the verified common ground and SPI/CS/IRQ wiring unchanged.
3. Power/configure P1 and P2 first.
4. Power or reset SN32 last.
5. Wait three seconds.
6. Run exactly one command:

```bat
trinity-host --port COM3 sn32-qualify --timeout 10 --poll 0.1 --liveness 10
```

Do not run separate `spi-diag`, `system-status` or self-test commands before
this qualification command; the immutable first-failure record must describe
the cold boot itself.

## What the one-shot command checks

```text
startup ready snapshot for SN32 + P1 + P2
clean initial state: no active fault, error or host transaction
immutable cold-boot SPI failure latch is clear
live P1 GET_INFO:   exact length + CRC + IRQ release
live P1 GET_STATUS: exact length + CRC + IRQ release
live P2 GET_INFO:   exact length + CRC + IRQ release
live P2 GET_STATUS: exact length + CRC + IRQ release
P1 retained KAT self-test and retirement
P2 retained KAT self-test and retirement
10 x system-status followed immediately by ping
monotonic uptime, ready state, ready_mask=0x07, active_host_txid=0
fault_flags=0, last_error=OK
final immutable SPI failure latch is still clear
```

## Acceptance

The run passes only when it ends with:

```text
[SN32_P1_P2_HARDWARE_QUALIFICATION]
result=PASS
```

Any earlier `FAIL`, a latched `SPI_FIRST_FAILURE`, wrong build identity, reset,
lost ready bit, nonzero fault flag or non-OK active error fails this gate. The
single command prints enough trace data to locate the failed target/command;
no speculative rerun is required before auditing that output.

## Explicit non-claims

```text
session stage/commit hardware:            PENDING
direct UART under SN32 orchestration:      PENDING
authenticated telemetry result via SN32:   PENDING
ML-KEM live-session hardware:              PENDING
Tiny safety integration:                   PENDING
full-system qualification:                 PENDING
hardware_qualified:                        false
full_system_hardware_qualified:            false
```
