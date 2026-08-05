# SN32 v0.7.31 staged-session status contract

## Identity

```text
SN32 architecture  0.7.31
SN32 build ID       0x0007001F
PC host             0.5.2
Primer #1           0x5031D003, unchanged
Primer #2           0x50320002, unchanged
```

## Hardware observation from v0.7.30

The core demo reached:

```text
phase=STAGE_WAIT
P2.9_readback=LOW
P1=STAGED/secure=0x03
P2=STAGED/secure=0x03
emergency_zeroize=PASS
```

P2.9 LOW is correct during STAGE_WAIT because the secure-enable edge is emitted
only after both endpoints are committed and blocked.

## Root cause

The Primer GET_STATUS payload always exposes `active_session_id` in bytes 4..7.
While an endpoint is `STAGED`, its staged bank contains the new session ID but
its active bank is intentionally empty, so GET_STATUS returns session ID zero.

The previous SN32 controller required all four conditions during STAGE_WAIT:

```text
P1 state == STAGED
P2 state == STAGED
P1 GET_STATUS session_id == requested session_id
P2 GET_STATUS session_id == requested session_id
```

The final two conditions can never become true with the unchanged Primer RTL.

## Corrected controller rule

For `STAGED`, SN32 now requires:

```text
session_state == STAGED
secure_flags contains SECURE_SESSION_STAGED
```

For `COMMITTED_BLOCKED` and `ACTIVE`, SN32 still requires the exact requested
session ID because GET_STATUS then reports the populated active bank.

The security binding is not weakened: each Primer's existing COMMIT_SESSION
handler independently compares the 32-bit commit payload against its private
`staged_session_id` and rejects a mismatch before promoting the staged bank.

## Source regression

Portable CI requires a controller mock that reproduces the real contract:
GET_STATUS reports active session ID zero while STAGED, then reports the staged
ID only after COMMIT_SESSION succeeds. The full controller activation and
telemetry regression passes with that model.

## Required hardware gate

```bat
python sn32\tests\deploy\check_mlkem_lowram_map.py sn32\keil\Listings\deploy\trinity_sn32f407_deploy.map
trinity-host --port COM3 system-info
trinity-host --port COM3 sn32-qualify --timeout 10 --poll 0.1 --liveness 10
trinity-demo
```

Require ArmClang 6.24 with zero errors and zero warnings, MAP PASS, flash/verify
of SN32 v0.7.31, CREATE_SESSION reaching ACTIVE, one authenticated 24-byte
telemetry result returning byte-exact, final zeroize, and a live PING.

This source fix does not qualify Tiny or the full system.
