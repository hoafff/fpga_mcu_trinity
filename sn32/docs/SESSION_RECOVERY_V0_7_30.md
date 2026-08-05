# SN32 v0.7.30 session recovery hardware gate

## Candidate

```text
SN32 architecture 0.7.30
SN32 build ID      0x0007001E
PC host            0.5.1
P1                 0x5031D003
P2                 0x50320002
```

P1/P2 RTL and bitstreams are unchanged.

## Purpose

This candidate addresses two observations from v0.7.29 hardware:

1. session activation ended with `SESSION_COMMIT_FAILED` without retaining the
   endpoint state immediately before fail-safe zeroize;
2. the failed host transaction blocked the next full zeroize with
   `RESULT_PENDING`.

Version 0.7.30 records the activation phase, P2.9 GPIO readback, P1/P2 session
states and secure flags, then allows full emergency zeroize to recover without a
manual MCU reset.

## Exact-target gate

```bat
python sn32\tests\deploy\check_mlkem_lowram_map.py sn32\keil\Listings\deploy\trinity_sn32f407_deploy.map
```

Require ArmClang 6.24, zero errors, zero warnings and MAP PASS before flashing.

## Hardware sequence

After flashing only SN32 and waiting for startup recovery:

```bat
trinity-host --port COM3 system-info
trinity-host --port COM3 system-status
trinity-host --port COM3 sn32-qualify --timeout 10 --poll 0.1 --liveness 10
trinity-demo
```

If activation fails, the GUI must report a decoded line containing:

```text
phase=STAGE_WAIT, COMMIT_WAIT or ACTIVE_WAIT
P2.9_readback=HIGH or LOW
P1=<session state>/secure=0x..
P2=<session state>/secure=0x..
emergency_zeroize=PASS
```

CLI fallback before zeroize:

```bat
trinity-host --port COM3 session-diagnostic
trinity-host --port COM3 zeroize --scope all --timeout 30
trinity-host --port COM3 system-status
trinity-host --port COM3 ping
```

A recovered failure must leave no retained host transaction and a clean status.
A successful core demo additionally requires ACTIVE session, one authenticated
24-byte telemetry result, byte-exact readback, final zeroize and PING.

This gate does not qualify Tiny or the full system.
