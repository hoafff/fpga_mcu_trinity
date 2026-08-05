# Implementation status

Status date: 2026-08-05

## Hardware-qualified baseline

```text
Primer #1 build ID = 0x5031D003
Primer #2 build ID = 0x50320002
SN32 version/build = 0.7.28 / 0x0007001C
PC host version    = 0.4.3
```

Valid hardware claims:

```text
SN32 bounded startup recovery: PASS
PC <-> SN32 command/UART liveness: PASS
SN32 -> P1/P2 shared dual-SPI control plane: PASS
P1/P2 retained KAT lifecycle: PASS
deterministic ML-KEM-512 low-RAM KeyGen A1: PASS
post-KeyGen zeroize and PING: PASS
```

## Hardware evidence from the failed core-demo candidates

Version 0.7.29 reached ML-KEM KeyGen, Encaps, Decaps and KDF, then returned
`SESSION_COMMIT_FAILED`. Its retained failed host transaction blocked a later
full zeroize with `RESULT_PENDING`.

Version 0.7.30 corrected recovery and produced the decisive snapshot:

```text
phase=STAGE_WAIT
P2.9_readback=LOW
P1=STAGED/secure=0x03
P2=STAGED/secure=0x03
emergency_zeroize=PASS
```

This proves both STAGE_SESSION commands completed and emergency recovery works.
P2.9 LOW is expected during STAGE_WAIT; the secure-enable HIGH edge has not yet
been issued.

## Root cause identified from v0.7.30

The Primer GET_STATUS payload exposes `active_session_id` in bytes 4..7. While
the endpoint is STAGED, the new ID exists only in the private staged bank and
the active bank is empty, so GET_STATUS reports zero.

The SN32 controller incorrectly required the requested session ID during
STAGE_WAIT. Therefore it timed out even though both endpoints had already
reported STAGED and `SECURE_SESSION_STAGED`.

## Active source candidate

```text
SN32 version/build = 0.7.31 / 0x0007001F
PC host version    = 0.5.2
Primer #1          = unchanged, 0x5031D003
Primer #2          = unchanged, 0x50320002
Tiny 1P5           = omitted from this demo profile
```

Version 0.7.31 changes only the SN32/host-side status contract:

```text
STAGED:
  require endpoint state STAGED
  require SECURE_SESSION_STAGED
  do not compare GET_STATUS.active_session_id

COMMIT_SESSION:
  each Primer still compares the exact 32-bit payload against staged_session_id

COMMITTED_BLOCKED and ACTIVE:
  SN32 still requires the exact active session ID
```

This does not weaken session binding. A wrong commit ID remains rejected inside
each unchanged Primer before the staged bank can become active.

Version 0.7.31 retains all v0.7.30 recovery features:

```text
P2.9 readback at secure-enable HIGH
pre-zeroize P1/P2 state/secure snapshot
STAGE_WAIT / COMMIT_WAIT / ACTIVE_WAIT diagnostics
ZEROIZE_ALL preemption of a terminal retained failure
PC auto-retirement of failed managed commands
GUI automatic diagnostic read and emergency zeroize
CLI session-diagnostic command
```

## Portable source status

```text
static deploy gate: PASS
Python protocol tests: PASS
portable C protocol tests: PASS
full SN32 controller tests: PASS with real staged/active ID split
SN32 deploy crypto lifecycle tests: PASS
pinned ML-KEM Gate 3 tests: PASS
Primer2 RTL regression: PASS, RTL unchanged
```

These results are not exact-target or hardware demo qualification.

## No-Tiny wiring

```text
SN32 P2.9 / J7
    +--> P1 secure_enable_i / T12
    +--> P2 secure_enable_i / T12
```

P2.9 heartbeat output is disabled in this profile. No Tiny, ESP32 or second
output may drive the shared T12 net.

## Required hardware gate for v0.7.31

```text
1. ArmClang 6.24 rebuild with 0 errors and 0 warnings.
2. MAP checker PASS within the 8 KB IRAM limit.
3. Flash/Verify only SN32.
4. Confirm identity 0.7.31 / 0x0007001F.
5. Re-run sn32-qualify.
6. Run one core-demo attempt.
7. Require CREATE_SESSION to pass STAGED, COMMITTED_BLOCKED and reach ACTIVE.
8. Require one authenticated 24-byte packet to return byte-exact.
9. Require final zeroize to restore READY_NO_KEYPAIR and PING to remain live.
```

Detailed record:

```text
sn32/docs/STAGED_STATUS_CONTRACT_V0_7_31.md
sn32/hardware/core_demo/qualification_v0_7_31.toml
```

## Non-claim boundary

Until the hardware gate succeeds, do not claim:

```text
ML-KEM Encaps/Decaps hardware PASS
session activation hardware PASS
core secure telemetry hardware PASS
Tiny integration PASS
full-system hardware qualification PASS
```

Current full-system hardware qualified remains `false`.
