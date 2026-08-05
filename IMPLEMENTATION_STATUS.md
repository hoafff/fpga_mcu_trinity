# Implementation status

Status date: 2026-08-05

## Hardware-qualified baseline

```text
Primer #1 build ID = 0x5031D003
Primer #2 build ID = 0x50320002
SN32 version/build = 0.7.28 / 0x0007001C
PC host version    = 0.4.3
```

The following hardware claims remain valid:

```text
SN32 v0.7.28 bounded startup recovery: PASS
PC <-> SN32 command/UART liveness: PASS
SN32 -> P1/P2 shared dual-SPI control plane: PASS
P1/P2 retained KAT lifecycle: PASS
deterministic ML-KEM-512 low-RAM KeyGen A1: PASS
post-KeyGen zeroize and PING: PASS
```

Evidence:

```text
sn32/hardware/mlkem_low_ram_a1/evidence/
  v0_7_28_keygen_hardware_qualification_2026-08-05.txt
sn32/hardware/mlkem_low_ram_a1/
  qualification_v0_7_28.toml
```

## Active source candidate for the time-bounded demo

```text
SN32 version/build = 0.7.29 / 0x0007001D
PC host version    = 0.5.0
Primer #1          = unchanged, 0x5031D003
Primer #2          = unchanged, 0x50320002
Tiny 1P5           = explicitly omitted from this demo profile
```

Version 0.7.29 preserves the v0.7.28 startup recovery, GPIO mode-0 dual-SPI
backend and low-RAM KeyGen. It adds:

```text
serialized/recomputed low-RAM ML-KEM-512 Encaps
serialized/recomputed low-RAM ML-KEM-512 Decaps
byte-exact ciphertext comparison without a second 768-byte buffer
constant-time implicit rejection
Encaps/Decaps shared-secret self-check
KDF and P1/P2 session activation path
one-packet authenticated telemetry demo workflow
Tkinter PC dashboard with progress, identities, result and log export
```

The pinned reference remains:

```text
pq-code-package/mlkem-native@048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa
```

Portable source tests prove:

```text
KeyGen public key and secret key: byte-exact versus pinned reference
Encaps ciphertext and shared secret: byte-exact versus pinned reference
valid Decaps shared secret: equal to Encaps
modified-ciphertext implicit rejection secret: byte-exact versus pinned reference
KDF vector: PASS
host one-packet core workflow and cleanup: PASS
Primer #2 RTL regression: PASS
```

These are source/portable results. They are not ArmClang fit or hardware demo
qualification.

## Temporary no-Tiny demo wiring

The qualified SPI and direct P1-to-P2 UART wiring remains unchanged. For the
v0.7.29 competition demo, connect:

```text
SN32 P2.9 / board-visible J7 header pin
    +--> Primer #1 secure_enable_i / FPGA T12
    +--> Primer #2 secure_enable_i / FPGA T12
```

P2.9 is normally the MCU heartbeat output in the complete Tiny architecture.
For this no-Tiny candidate, the periodic GPIO heartbeat is compile-time disabled
and P2.9 has one output owner only: LOW-at-staging then HIGH-at-commit direct
shared secure-enable. Internal SysTick/progress leases and fail-closed timeout
checks remain active. No Tiny, ESP32 or second output may drive this net.

## Required exact-target and hardware gate

Before v0.7.29 can be called demo-ready:

```text
1. ArmClang 6.24 rebuild: 0 errors, 0 warnings.
2. MAP gate: Total RW <= 8192, stack=2048, g_crypto<=3520,
   at least 256 bytes static RAM headroom, no host fallback workspace.
3. Flash/Verify only SN32; P1/P2 images remain unchanged.
4. Startup and SN32/P1/P2 qualification PASS with no first SPI failure.
5. Deterministic KeyGen PASS.
6. Encaps/Decaps/KDF and CREATE_SESSION reach ACTIVE.
7. One 24-byte payload travels P1 -> direct UART -> P2 and returns
   authenticated plaintext byte-exact through SN32.
8. READ_LAST_RESULT matches the packet result.
9. Full zeroize restores READY_NO_KEYPAIR and PING remains live.
```

Detailed procedure:

```text
sn32/docs/CORE_DEMO_V0_7_29_HARDWARE_GATE.md
```

PC GUI command after installing the host package:

```text
trinity-demo
```

## Non-claim boundary

Until the exact-target and hardware gate is executed, do not claim:

```text
v0.7.29 exact-target fit PASS
ML-KEM Encaps/Decaps hardware PASS
session activation hardware PASS
core secure telemetry hardware PASS
```

Even after the core demo passes, do not claim:

```text
Tiny supervisor integration or fault-containment PASS
random/entropy-qualified ML-KEM PASS
power-fail recovery PASS
full-system hardware qualification PASS
```

Current full-system hardware qualified remains:

```text
false
```
