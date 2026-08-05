# FPGA MCU Trinity

Competition project for PC host, SN32F407F and two Gowin Primer 20K boards.
Tiny 1P5 remains part of the target architecture but is intentionally omitted
from the current time-bounded core-demo profile.

```text
PC <-> SN32 -- shared SPI --> P1/P2
P1 == direct encrypted UART ==> P2
```

Start with `ai_context/README_AI.md`.

## Hardware-qualified baseline

```text
Primer #1 build ID = 0x5031D003
Primer #2 build ID = 0x50320002
SN32 version/build = 0.7.28 / 0x0007001C
PC host version    = 0.4.3
```

Qualified hardware results:

```text
SN32 bounded startup recovery:                          PASS
PC <-> SN32 command and UART liveness:                  PASS
SN32 -> P1/P2 shared dual-SPI control plane:            PASS
P1/P2 retained KAT transaction lifecycle:               PASS
Deterministic ML-KEM-512 low-RAM KeyGen A1 on SN32:     PASS
Post-KeyGen zeroize and PING:                           PASS
```

Evidence is retained under `sn32/hardware/mlkem_low_ram_a1/`.

## Active source candidate: staged-status fix v0.7.31

```text
SN32 version/build = 0.7.31 / 0x0007001F
PC host version    = 0.5.2
P1/P2 bitstreams   = unchanged
Tiny 1P5           = not used by this demo profile
```

Hardware v0.7.30 showed both Primers at:

```text
P1=STAGED/secure=0x03
P2=STAGED/secure=0x03
phase=STAGE_WAIT
P2.9_readback=LOW
emergency_zeroize=PASS
```

That result proved stage commands completed and recovery worked. P2.9 LOW is
correct before commit. The failure was a controller/endpoint status-contract
mismatch: Primer GET_STATUS reports `active_session_id`, which remains zero
while only the staged bank exists, but SN32 required the requested ID during
STAGE_WAIT.

Version 0.7.31 validates STAGED using state plus `SECURE_SESSION_STAGED`. The
exact 32-bit session ID remains enforced by each Primer's existing
COMMIT_SESSION handler and is still checked by SN32 in COMMITTED_BLOCKED and
ACTIVE states. P1/P2 RTL and bitstreams are unchanged.

Version 0.7.31 also retains the v0.7.30 recovery features:

```text
P2.9 GPIO readback at the secure-enable HIGH edge
pre-zeroize P1/P2 session-state and secure-flag snapshot
failure phase: STAGE_WAIT / COMMIT_WAIT / ACTIVE_WAIT
emergency ZEROIZE_ALL that preempts a retained failed host transaction
PC auto-retirement of failed managed commands
GUI/CLI decoded session-commit diagnostics
```

Portable CI passes the static deploy gate, Python protocol tests, portable C
protocol tests, full controller regression with the real staged/active ID split,
deploy crypto tests, pinned ML-KEM Gate 3 and Primer2 RTL regression.

## PC demo dashboard

Install and launch:

```bat
python -m pip install -e pc_host
trinity-demo
```

CLI diagnostic fallback:

```bat
trinity-host --port COM3 session-diagnostic
trinity-host --port COM3 zeroize --scope all --timeout 30
```

## Temporary wiring without Tiny

```text
SN32 P2.9 / board-visible J7 header pin
    +--> Primer #1 secure_enable_i / FPGA T12
    +--> Primer #2 secure_enable_i / FPGA T12
```

Use one common 3.3 V logic ground. No ESP32, Tiny or second output may drive
this net. P2.9 has one owner only in this profile.

## Required before calling v0.7.31 demo-ready

```text
ArmClang 6.24 exact-target rebuild: 0 errors, 0 warnings
MAP gate within the 8 KB SN32 limit
flash and verify only SN32
clean startup and dual-SPI qualification
CREATE_SESSION reaches ACTIVE
one authenticated 24-byte telemetry packet returns byte-exact
full zeroize restores READY_NO_KEYPAIR
post-demo PING remains live
```

Detailed contract: `sn32/docs/STAGED_STATUS_CONTRACT_V0_7_31.md`.

The current source candidate does not establish Tiny integration, random
entropy qualification, power-fail recovery or full-system hardware PASS.
See `IMPLEMENTATION_STATUS.md` for the exact boundary.
