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

Evidence is retained under:

```text
sn32/hardware/mlkem_low_ram_a1/
```

## Active source candidate: core demo v0.7.29

```text
SN32 version/build = 0.7.29 / 0x0007001D
PC host version    = 0.5.0
P1/P2 bitstreams   = unchanged
Tiny 1P5           = not used by this demo profile
```

The candidate adds a serialized/recomputed low-RAM ML-KEM-512 A2 path for
Encaps and Decaps while retaining the existing phase-shared 1792-byte crypto
workspace. Portable tests compare it against the exact pinned mlkem-native
reference and currently pass for:

```text
KeyGen public key and secret key: byte-exact
Encaps ciphertext and shared secret: byte-exact
valid Decaps shared secret equality
modified-ciphertext implicit rejection: byte-exact
KDF vector
one-packet host demo workflow and cleanup
Primer #2 RTL regression
```

The minimum real demo sequence is:

```text
ML-KEM KeyGen -> Encaps/Decaps -> KDF
-> stage/commit one session to P1/P2
-> P1 Ascon encrypt + direct UART transmit
-> P2 authenticate/decrypt
-> SN32 read/ACK authenticated plaintext
-> PC byte-exact verification
-> full zeroize and PING
```

## PC demo dashboard

Install the editable host package:

```bat
python -m pip install -e pc_host
```

Launch the GUI:

```bat
trinity-demo
```

The Tkinter dashboard provides serial-port selection, quick preflight, one-click
core demo, progress display, SN32/P1/P2 identities, session and sequence status,
authenticated plaintext display, emergency zeroize and log export. Serial I/O
runs in a worker thread so the UI remains responsive during the slow 12 MHz
Cortex-M0 cryptographic phases.

## Temporary wiring without Tiny

Keep the qualified SPI and direct P1-to-P2 UART wiring unchanged. Add:

```text
SN32 P2.9 / board-visible J7 header pin
    +--> Primer #1 secure_enable_i / FPGA T12
    +--> Primer #2 secure_enable_i / FPGA T12
```

Use one common 3.3 V logic ground. No ESP32, Tiny or second output may drive
this shared net. In the no-Tiny profile, firmware disables the normal P2.9 MCU
heartbeat GPIO and gives P2.9 one owner only: direct shared secure-enable.
Internal SysTick/progress leases and fail-closed timeout checks remain active.

## Required before calling the candidate demo-ready

Version 0.7.29 is a source candidate until all of the following pass:

```text
ArmClang 6.24 exact-target rebuild: 0 errors, 0 warnings
IRAM/MAP gate within the 8 KB SN32 limit
flash and verify SN32
clean startup and dual-SPI qualification
CREATE_SESSION reaches ACTIVE
one authenticated 24-byte telemetry packet returns byte-exact
full zeroize restores READY_NO_KEYPAIR
post-demo PING remains live
```

Procedure:

```text
sn32/docs/CORE_DEMO_V0_7_29_HARDWARE_GATE.md
```

## Non-claim boundary

The current source and future core-demo PASS do not establish:

```text
Tiny supervisor integration or fault-containment PASS
random/entropy-qualified ML-KEM PASS
power-fail recovery PASS
full-system hardware qualification PASS
```

See `IMPLEMENTATION_STATUS.md` for the exact evidence and current boundary.
