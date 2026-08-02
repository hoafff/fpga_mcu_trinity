# Primer #2 deployment build

Primer #2 is the authenticated receive target for the direct 66-byte UART payload
from Primer #1. The deployment source implements SPI control/reconciliation,
session stage/commit/activation, UART framing, replay checks, Ascon-AEAD128
decrypt/tag verification, single-entry plaintext quarantine, diagnostics,
zeroize and fail-closed safety handling.

## Locked target

```text
Device:           GW2A-LV18PG256C8/I7
Database:         GW2A-18C / gw2a18c-011
Device version:   C
Clock:            27.000 MHz
Top:              primer2_top
Tool:             Gowin EDA V1.9.11.03 Education x64
Project:          primer2/gowin/trinity_primer2.gprj
```

## Portable regression

```bash
python primer2/tb/run.py
```

The runner requires Python 3.11+, `iverilog` and `vvp`. It executes the
byte-exact Primer #1-compatible Ascon reference checks and every self-checking
SystemVerilog testbench listed in `primer2/tb/run.py`.

## Exact-device build

From a Gowin shell whose `gw_sh` belongs to V1.9.11.03 Education:

```bash
cd primer2/gowin
gw_sh run.tcl
```

Or open `trinity_primer2.gprj` in Gowin EDA and run Synthesis, Place & Route and
Generate Bitstream. Review timing, utilization, unconstrained paths, latches,
multiple drivers, inferred clocks and unrouted nets before accepting the build.
Generated `impl/`, reports and `.fs` remain excluded by repository policy.

## Hardware gate

A successful vendor build is not hardware qualification. Load
`primer2/gowin/impl/pnr/trinity_primer2.fs` with **SRAM Program**, then exercise
GET_INFO/STATUS, self-test, session stage/commit, a byte-exact Primer #1 frame,
READ/ACK_AUTH_RESULT, replay/tag failures, zeroize and safety inputs. Record the
bitstream SHA-256 and serial/SPI evidence before changing `hardware_qualified`.

## Current qualification boundary

In the authoring/execution environment, portable static and byte-exact reference
checks PASS. `iverilog`, `vvp` and Gowin EDA are unavailable, so RTL simulation,
exact-device synthesis/P&R/STA, utilization, WNS/TNS and bitstream generation
remain OPEN. `hardware_qualified` must remain false until SRAM programming and
physical P1-to-P2 evidence are supplied.
