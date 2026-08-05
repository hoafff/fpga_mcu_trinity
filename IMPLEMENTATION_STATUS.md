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

## Hardware result that triggered the current fix

The v0.7.29 candidate passed exact-target MAP and dual-SPI qualification, then
reached ML-KEM KeyGen, Encaps, Decaps and KDF. Session activation ended with:

```text
SESSION_COMMIT_FAILED
system_state=FAULT_LOCKED
fault_flags=0x11
```

A later full zeroize was blocked by the retained failed host transaction and
returned `RESULT_PENDING`. This did not qualify session activation or telemetry.

## Active source candidate

```text
SN32 version/build = 0.7.30 / 0x0007001E
PC host version    = 0.5.1
Primer #1          = unchanged, 0x5031D003
Primer #2          = unchanged, 0x50320002
Tiny 1P5           = omitted from this demo profile
```

Version 0.7.30 retains the v0.7.29 low-RAM cryptographic datapath and adds:

```text
P2.9 GPIO readback immediately after secure-enable HIGH
pre-zeroize P1/P2 session-state and secure-flag snapshot
failure phase encoding: STAGE_WAIT / COMMIT_WAIT / ACTIVE_WAIT
ZEROIZE_ALL preemption of a terminal retained host failure
PC auto-retirement of failed managed commands
GUI automatic diagnostic read followed by emergency zeroize
CLI session-diagnostic command
```

The packed `GET_LAST_ERROR.detail` records:

```text
failure phase
P2.9 readback HIGH/LOW
P1 session state and secure flags
P2 session state and secure flags
```

Portable source tests cover the recovery path, retained diagnostics, emergency
cleanup, low-RAM ML-KEM reference equivalence and P1/P2 regressions. These are
not exact-target or hardware PASS claims.

## No-Tiny wiring

```text
SN32 P2.9 / J7
    +--> P1 secure_enable_i / T12
    +--> P2 secure_enable_i / T12
```

P2.9 heartbeat output is disabled in this profile. No Tiny, ESP32 or second
output may drive the shared T12 net.

## Required hardware gate for v0.7.30

```text
1. ArmClang 6.24 rebuild with 0 errors and 0 warnings.
2. MAP checker PASS within the 8 KB IRAM limit.
3. Flash/Verify only SN32.
4. Confirm identity 0.7.30 / 0x0007001E.
5. Re-run sn32-qualify.
6. Run one core-demo attempt.
7. If activation fails, retain the decoded diagnostic and verify automatic
   emergency zeroize restores a clean controller without reset.
8. If activation succeeds, require one authenticated telemetry packet,
   byte-exact readback, final zeroize and PING.
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
