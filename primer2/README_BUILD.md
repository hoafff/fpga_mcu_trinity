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

For a Windows build that also captures qualification evidence:

```powershell
powershell -ExecutionPolicy Bypass -File primer2/scripts/run_exact_device_build.ps1 `
  -GwSh "C:\path\to\Gowin\IDE\bin\gw_sh.exe"
```

The PowerShell runner executes the portable static/reference checks, invokes the
exact-device Gowin script, verifies that `trinity_primer2.fs` exists, computes
its SHA-256, extracts utilization/timing/warning lines, records `git status`,
checks committed and working-tree whitespace, and guards the qualified Primer #1
implementation paths. It writes a timestamped directory below
`primer2/local_evidence/`; that local evidence directory is intentionally
ignored by Git.

Or open `trinity_primer2.gprj` in Gowin EDA and run Synthesis, Place & Route and
Generate Bitstream. Review timing, utilization, unconstrained paths, latches,
multiple drivers, inferred clocks and unrouted nets before accepting the build.
Generated `impl/`, reports and `.fs` remain excluded by repository policy.

## Control-plane dependency for the P1-to-P2 hardware test

Primer #2 is intentionally fail-closed. A programmed board does not accept the
UART payload merely because `uart_rx_i` is connected. Before a frame can be
accepted, a controller must:

1. run Primer #2 GET_INFO/GET_STATUS and self-test;
2. stage byte-identical session ID, Ascon key and nonce prefix in both Primers;
3. commit both Primers while `secure_enable_i` is low;
4. confirm that both report `COMMITTED_BLOCKED`;
5. issue the Tiny session-commit toggle so Tiny raises `secure_enable_i`;
6. confirm that both Primers enter `ACTIVE` before Primer #1 sends sequence 1.

The current SN32 deployment target is P1 bring-up only and does not yet perform
this P2 session choreography. Therefore the P1-to-P2 hardware gate requires a
scope-limited control-plane bring-up harness before SN32 full integration. That
harness may implement only the commands above plus result read/ACK and error
reporting; it is not permission to bypass self-test, hard-code an active session,
force `secure_enable_i`, remove replay checks or weaken any fail-closed path in
Primer #2 RTL.

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
