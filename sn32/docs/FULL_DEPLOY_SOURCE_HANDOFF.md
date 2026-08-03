# SN32F407 Full Deploy Source Handoff

## Current state

The full SN32F407 controller source is implemented and the exact ArmClang 6.24
build at source commit `40ff6f06ed32d3139899aae291047f35d0740f86`
completed successfully:

```text
Program Size: Code=23228 RO-data=776 RW-data=100 ZI-data=4532
0 Error(s), 0 Warning(s)
Flash = 24104 / 32764 bytes
RAM   = 4632 / 8192 bytes
AXF / HEX generation = PASS
```

The same image was flashed and passed the scoped standalone hardware result:

```text
PC <-> SN32 UART PING HARDWARE: PASS
```

Evidence:

```text
sn32/docs/PC_TO_SN32_UART_PING_HARDWARE_QUALIFICATION_2026-08-03.md
sn32/hardware/pc_uart_ping/evidence/pc_uart_ping_2026-08-03.txt
```

This does not qualify either Primer, crypto execution on hardware, Tiny or the
full system.

## Current qualification image

`main` now identifies the next gate image as firmware architecture `0.7.1` with:

```text
sn32_build_id = 0x00070001
SPI0          = 100 kHz, mode 0, MSB first
```

The 100 kHz rate matches the already successful ESP32-C3 dual-Primer control
harness and is deliberately conservative for the first SN32 dual-SPI run.

Because this changes the deploy source after the accepted `40ff6f06...` image,
the current `main` must receive a new exact Keil rebuild, SN-LINK flash/verify and
standalone PING before P1/P2 are connected.

## Implemented runtime scope

- PC UART0 at 115200 8N1 with COBS and CRC16 framing.
- Shared SPI0 controller transport to Primer #1 and Primer #2.
- Independent CS and IRQ handling for both Primer endpoints.
- Packet validation, transaction IDs, timeout handling, retained transaction
  reconciliation, exact retry, and result retirement.
- SN32, P1, P2, and Tiny self-test orchestration.
- Pinned ML-KEM-512 source selected from `pq-code-package/mlkem-native` commit
  `048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa`.
- Deterministic ML-KEM key generation, encapsulation, decapsulation self-check,
  SHA3/SHAKE KDF, and explicit secret zeroization.
- Dual-Primer session stage and commit with the same session material.
- SN32 P3.8 session-commit edge to Tiny after both Primer endpoints report
  `COMMITTED_BLOCKED`.
- Direct P1 UART transmit to P2 receive; SN32 does not relay the encrypted
  payload.
- P2 authenticated-result read, session/sequence/plaintext verification, ACK,
  and pending-result protection.
- Close-session, system zeroize, Tiny-fault containment, heartbeat lease
  containment, diagnostics, deterministic demo, benchmark, and transport stress.

`DEMO_SECURE` remains unavailable until an entropy source is approved and
qualified. It fails explicitly rather than substituting deterministic material.

## Reproducible source gates

Clone and initialize the exact ML-KEM source:

```bash
git clone --recurse-submodules https://github.com/hoafff/fpga_mcu_trinity.git
cd fpga_mcu_trinity
git submodule update --init --recursive
git -C sn32/third_party/mlkem-native/upstream rev-parse HEAD
```

Expected submodule commit:

```text
048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa
```

Run:

```bash
make -C sn32/tests/mlkem_gate3 clean test
make -C sn32/tests/full_controller clean test
make -C sn32/tests/deploy_crypto clean test
make -C sn32/tests/portable clean test
PYTHONPATH=pc_host/src python -m unittest discover -s pc_host/tests -v
python sn32/tests/deploy/check_inc_boundaries.py
python sn32/tests/deploy/check_keil_size_profile.py
python sn32/tests/deploy/check_dual_spi_gate_profile.py
python sn32/tests/deploy/check_deploy_project.py
python sn32/tests/s0/check_s0_project.py
git diff --check
```

Exact target:

```text
sn32/keil/trinity_sn32f407_deploy.uvprojx
SN32F407F
ArmClang 6.24
SONiX.SN32F4_DFP 1.0.1
ARM CMSIS 6.2.0 / CORE 6.1.1
IROM 0x7FFC bytes
IRAM 0x2000 bytes
```

## Next hardware gate

The next isolated gate is:

```text
SN32 -> P1/P2 DUAL-SPI CONTROL PLANE HARDWARE
```

Execution plan:

```text
sn32/docs/SN32_DUAL_SPI_HARDWARE_QUALIFICATION_NEXT_GATE.md
```

PC command:

```bat
trinity-host --port COM3 dual-spi-bringup --timeout 10 --poll 0.1
```

It probes both exact Primer identities, runs separate retained KAT self-tests
with P1 mask `0x013E` and P2 mask `0x03E3`, retires both results, and confirms the
final ready/fault state. It does not stage a session, connect Tiny or send
telemetry.

## Qualification boundary

Current accepted status:

```text
SOURCE / STATIC / PORTABLE GATES:          PASS at 40ff6f06; rerun on current main pending CI
EXACT ARMC6 KEIL REBUILD:                   PASS at 40ff6f06
FLASH LINKER FIT:                           PASS at 40ff6f06
RAM LINKER FIT:                             PASS at 40ff6f06
AXF / HEX GENERATION:                       PASS at 40ff6f06
SN32 FLASH PROGRAMMING:                     PASS at 40ff6f06
PC <-> SN32 UART PING HARDWARE:             PASS at 40ff6f06
current v0.7.1 exact rebuild/flash/PING:     PENDING
SN32 -> P1/P2 dual-SPI hardware:            PENDING
session and telemetry integration:          PENDING
Tiny safety integration:                    PENDING
full-system hardware qualification:         PENDING
```

Therefore:

```text
hardware_qualified = false
full_system_hardware_qualified = false
```
