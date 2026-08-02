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
byte-exact Primer #1-compatible Ascon reference checks and all nine
self-checking SystemVerilog benches listed in `primer2/tb/run.py`.

The same gate is available in GitHub Actions. Open **Actions**, select
**portable-protocol**, choose **Run workflow**, select branch `main`, and run it.
Accept the RTL gate only when both jobs are green; the `primer2-rtl` job installs
Icarus Verilog, runs all nine benches, checks whitespace, and guards the
qualified Primer #1 implementation paths.

## Authoritative SystemVerilog 2017 build flow

`trinity_primer2.gprj` is the source/device/file-list project. Gowin EDA stores
process options such as **Verilog Language** in generated local state below
`primer2/gowin/impl/`; that directory is intentionally excluded from Git and is
not an authoritative clean-clone configuration.

The source-controlled authority is `primer2/gowin/run.tcl`. It deletes stale
`impl/` state, selects the exact device and top, then applies:

```tcl
set_option -verilog_std sysv2017
```

A clean clone therefore must be built with the batch flow rather than by opening
the bare `.gprj` and inheriting a GUI default of Verilog 2001:

```bash
cd primer2/gowin
gw_sh run.tcl
```

For a Windows build that also captures qualification evidence:

```powershell
powershell -ExecutionPolicy Bypass -File primer2/scripts/run_exact_device_build.ps1 `
  -GwSh "C:\path\to\Gowin\IDE\bin\gw_sh.exe" `
  -Python "py -3"
```

The PowerShell runner executes the portable static/reference checks, invokes the
clean exact-device Gowin script, verifies that `trinity_primer2.fs` exists,
computes its SHA-256, extracts utilization/timing/warning lines, records
`git status`, checks committed and working-tree whitespace, and guards the
qualified Primer #1 implementation paths. It writes a timestamped directory
below `primer2/local_evidence/`; that local evidence directory is intentionally
ignored by Git.

After this batch flow has regenerated local process state, the project may be
opened in the GUI for inspection. Manually selecting System Verilog 2017 is not
part of the reproducible build procedure and must not be required after each
clone. Generated `impl/`, reports and `.fs` remain excluded by repository policy.

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

## Safety-input drive and standalone bring-up

The integrated wiring contract assigns three actively driven Tiny outputs:

```text
Tiny secure_enable_o  -> Primer #2 secure_enable_i  (active high)
Tiny zeroize_no       -> Primer #2 zeroize_ni       (active low)
Tiny fault_latched_o  -> Primer #2 fatal_latched_i  (active high)
```

The direct payload link assigns Primer #1 `uart_tx_o` to Primer #2 `uart_rx_i`.
The accepted PnR evidence reports `Pull Mode NONE` for all four Primer #2 inputs,
and the controlled hardware documents do not establish an external resistor
bias for them. The CST therefore remains unchanged: no pull-up or pull-down is
added without schematic/continuity evidence.

These inputs must not float. With Tiny disconnected, a standalone 3.3 V logic
harness or emulator must actively hold:

```text
secure_enable_i = 0  during reset, self-test, stage and commit
fatal_latched_i = 0  unless testing the fatal path
zeroize_ni      = 1  unless testing zeroize
uart_rx_i       = 1  when no UART transmitter is attached (UART idle)
```

Raise `secure_enable_i` only after the session reaches `COMMITTED_BLOCKED`.
Drive all signals from 3.3 V-compatible outputs with a common ground; do not
short them to power rails while Tiny or Primer #1 is simultaneously driving.
A floating, disconnected Tiny is not a valid fail-closed hardware test setup.

## Clock-resource audit boundary

The accepted pre-fix PnR report uses one STA clock domain, `sys_clk_27m`. Gowin
also promoted several high-fanout control/data nets, including Ascon state,
plaintext-result and SPI payload nets, onto PRIMARY/LW routing. They are not
reported as generated clocks or as launch/capture clocks in STA. RTL uses only
the system clock as a positive-edge clock; SPI and UART inputs are synchronized
and edge-detected as data.

`LW = 8/8` is therefore recorded as a routing-capacity risk, not an automatic
functional failure. Do not disable global promotion blindly. The fault-output
RTL change and every future placement must be rebuilt and compared for PRIMARY,
LW, WNS/TNS and utilization. Escalate only if a clean build introduces an
additional clock domain, timing regression, unrouted net, or unstable routing.

## Hardware gate

A successful vendor build is not hardware qualification. Load
`primer2/gowin/impl/pnr/trinity_primer2.fs` with **SRAM Program**, then exercise
GET_INFO/STATUS, self-test, session stage/commit, a byte-exact Primer #1 frame,
READ/ACK_AUTH_RESULT, replay/tag failures, zeroize and safety inputs. Record the
bitstream SHA-256 and serial/SPI evidence before changing `hardware_qualified`.

## Current qualification boundary

The user-supplied build created on 2026-08-02 with Gowin EDA V1.9.11.03
Education passed synthesis with EX2664, PnR, 27 MHz timing and bitstream
generation. It is superseded because `fault_o` RTL and the clean build flow have
changed. The current source requires a fresh static/reference run, nine-bench
RTL regression and clean exact-device rebuild. `hardware_qualified` remains
false until SRAM programming and physical P1-to-P2 evidence are supplied.
