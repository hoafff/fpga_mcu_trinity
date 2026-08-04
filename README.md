# FPGA MCU Trinity

Competition project for PC host, SN32F407F, two Gowin Primer 20K boards and one
Tiny 1P5 supervisor.

```text
PC <-> SN32 -- shared SPI --> P1/P2
P1 == direct encrypted UART ==> P2
SN32/P1/P2 -> Tiny supervisor
```

Start with `ai_context/README_AI.md`.

## Current implementation milestone

The shared-SPI control plane follows:

```text
ai_context/interfaces/SPI_CONTROL_PLANE_ICD_v0.2.md
```

The active contract is:

- Primer `IRQ_N` is LOW only while a complete response mailbox is ready;
- retained side-effect and authenticated-result state is queried explicitly;
- non-magic/dummy CS windows are discarded silently;
- P1/P2 MISO remains high-impedance while deselected;
- shared SCK/MOSI/MISO, separate CS/IRQ and the direct P1-to-P2 UART payload
  wiring remain unchanged.

Qualified identities:

```text
Primer #1 build ID = 0x5031D003
Primer #2 build ID = 0x50320002
SN32 version/build = 0.7.26 / 0x0007001A
PC host version    = 0.3.9
```

## Hardware qualification status

```text
Primer #1 corrected exact-device build/programming: PASS
Primer #2 corrected exact-device build/programming: PASS
SN32 ArmClang build/flash/verify:                     PASS
SN32 stack lock:                                      0x800 bytes
PC <-> SN32 qualification command path:               PASS
SN32 -> P1/P2 shared dual-SPI control plane:           PASS
P1/P2 identity and status transactions:               PASS
P1/P2 retained KAT RUN/QUERY/RETIRE lifecycle:         PASS
Post-test PC-UART liveness:                            PASS
Retained first SPI failure:                            NONE
```

Evidence:

```text
sn32/hardware/dual_spi_control_plane/evidence/
  v0_7_26_hardware_qualification_2026-08-05.txt
```

The qualified command ended with:

```text
[SN32_P1_P2_HARDWARE_QUALIFICATION]
result=PASS
```

## Boundary of this PASS

This milestone qualifies the SN32/P1/P2 control plane and KAT transaction
lifecycle. It does **not** yet claim:

```text
ML-KEM keypair/session hardware integration PASS
P1 -> P2 secure telemetry end-to-end PASS
Tiny supervisor complete integration PASS
full-system hardware qualification PASS
```

The next integration gate is keypair/session establishment followed by direct
P1-to-P2 secure telemetry and authenticated-result read/ACK through SN32.

See `IMPLEMENTATION_STATUS.md` for the exact evidence and non-claim boundary.
