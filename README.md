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

Hardware-qualified identities:

```text
Primer #1 build ID = 0x5031D003
Primer #2 build ID = 0x50320002
SN32 version/build = 0.7.28 / 0x0007001C
PC host version    = 0.4.3
```

## Hardware qualification status

```text
SN32 v0.7.28 bounded startup recovery:                   PASS
PC <-> SN32 qualification command path:                  PASS
SN32 -> P1/P2 shared dual-SPI control-plane regression:  PASS
P1/P2 identity and status transactions:                  PASS
P1/P2 retained KAT RUN/QUERY/RETIRE lifecycle:            PASS
Deterministic ML-KEM-512 low-RAM KeyGen A1 on SN32F407F: PASS
Post-KeyGen full-scope zeroize:                           PASS
Post-KeyGen PC-UART liveness:                             PASS
Retained first SPI failure before/after qualification:   NONE
```

The qualified control-plane command ended with:

```text
[SN32_P1_P2_HARDWARE_QUALIFICATION]
result=PASS
```

The isolated KeyGen command ended with:

```text
[MLKEM_KEYPAIR]
result=PASS
public_key_hash=e906a88a8a119a7321543a3cbdf0d6e3fa809951fec835e0e581d37f7eb3e0aa
```

Evidence:

```text
sn32/hardware/mlkem_low_ram_a1/evidence/
  v0_7_28_keygen_hardware_qualification_2026-08-05.txt

sn32/hardware/mlkem_low_ram_a1/
  qualification_v0_7_28.toml
```

## Boundary of this PASS

This milestone qualifies startup recovery, the SN32/P1/P2 control plane and
isolated deterministic low-RAM ML-KEM-512 KeyGen. It does **not** claim:

```text
ML-KEM Encaps or Decaps hardware PASS
session KDF/stage/commit hardware PASS
P1 -> P2 secure telemetry end-to-end PASS
Tiny supervisor complete integration PASS
full-system hardware qualification PASS
```

The next gate is A2: low-RAM ML-KEM-512 Encaps/Decaps on SN32, followed by
session establishment and the direct P1-to-P2 secure telemetry flow.

See `IMPLEMENTATION_STATUS.md` for the exact evidence and non-claim boundary.
