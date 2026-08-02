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
byte-exact Primer #1-compatible Ascon reference checks and all nine self-checking
SystemVerilog benches listed in `primer2/tb/run.py`.

The same gate is available in GitHub Actions. Open **Actions**, select
**portable-protocol**, choose **Run workflow**, select branch `main`, and run it.
Accept the RTL gate only when both jobs are green; the `primer2-rtl` job installs
Icarus Verilog, runs all nine benches, checks whitespace, and guards the
qualified Primer #1 implementation paths.

The 2026-08-03 qualification record contains current reference and static PASS
results. A current nine-bench Icarus result was not included with that hardware
evidence and remains separately tracked.

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

Build a clean clone with:

```bash
cd primer2/gowin
gw_sh run.tcl
```

For a Windows build that also captures evidence:

```powershell
powershell -ExecutionPolicy Bypass -File primer2/scripts/run_exact_device_build.ps1 `
  -GwSh "C:\path\to\Gowin\IDE\bin\gw_sh.exe" `
  -Python "py" -PythonArgs @("-3")
```

The PowerShell runner executes the portable static/reference checks, invokes the
clean exact-device Gowin script, verifies that `trinity_primer2.fs` exists,
computes its SHA-256, extracts utilization/timing/warning lines, records
`git status`, checks committed and working-tree whitespace, and guards the
qualified Primer #1 implementation paths. It rejects the build candidate if
Gowin warning `EX2664` remains. Generated evidence is written under
`primer2/local_evidence/`, which is intentionally ignored by Git.

After the batch flow regenerates local process state, the project may be opened
in the GUI for inspection. Manually selecting System Verilog 2017 is not part of
the reproducible clean-clone procedure.

## Post-fix exact-device candidate

Qualification source:

```text
7588063e636da225bbe81632efe1060f4c825c37
```

The recorded clean rebuild completed synthesis without `EX2664`, PnR, timing,
power analysis and bitstream generation.

```text
Constraint:                27.000 MHz
Actual Fmax:               41.700 MHz
Worst setup slack:         +13.056 ns
Worst hold slack:          +0.425 ns
Setup/Hold violations:     0 / 0
Logic / Registers / CLS:   79% / 43% / 86%
PRIMARY / LW:              3/8 / 8/8
```

Accepted status:

```text
Primer #2 exact-device build candidate: PASS
```

The new bitstream was reported at
`primer2/gowin/impl/pnr/trinity_primer2.fs`. Its SHA-256 was not supplied, so
future evidence should rerun the evidence script and retain that hash.

`LW = 8/8` is retained as a routing-capacity risk. The clean build has no
reported unrouted nets, one clock domain and positive setup/hold margin. Do not
disable global promotion merely to lower the utilization number.

## Safety-input drive and standalone bring-up

The integrated wiring contract assigns active external drivers:

```text
Primer #1 uart_tx_o       -> Primer #2 uart_rx_i
Tiny secure_enable_o      -> Primer #2 secure_enable_i
Tiny zeroize_no           -> Primer #2 zeroize_ni
Tiny fault_latched_o      -> Primer #2 fatal_latched_i
```

The CST remains unchanged because no external resistor bias has been proven for
these nets. When P1/Tiny are disconnected, a 3.3 V-compatible harness must not
leave the inputs floating.

The official ESP32-C3 standalone fixture is:

```text
primer2/hardware/esp32c3_standalone_qualification/
```

Its fixed safety levels are:

```text
secure_enable_i = 0 during reset/self-test/stage/commit
fatal_latched_i = 0 using R12 strapped to GND
zeroize_ni      = 1 using R11 strapped to 3V3
uart_rx_i       = high impedance until GET_INFO proves target 2
```

The fixture may raise `secure_enable_i` only after P2 reaches
`SESSION_COMMITTED_BLOCKED`.

## Mandatory SPI startup rule

`spi_cs_ni` must be driven high before the ESP32 serial delay and before
`SPI.begin()`. It must not float or pulse low while the configured FPGA is alive.

If `irq_no` is low at controller startup, the fixture must drain the stale
response mailbox before issuing `GET_INFO`. The recorded qualification run
observed and successfully drained a startup `ERR_BAD_LENGTH` mailbox generated
with command and transaction ID zero.

The UART-injection GPIO remains an input until `GET_INFO` confirms:

```text
target_id = 2
protocol  = 1
build_id  = 0x50320001
```

## Standalone hardware result

The ESP32-C3 run produced:

```text
PASS count = 23
FAIL count = 0
OVERALL    = PASS
```

It proved SPI control, 66-byte UART injection, Ascon decrypt/authentication,
byte-exact plaintext, stage/abort/commit/activate, replay and sequence rejection,
pending-result protection, command `ZEROIZE_ALL`, re-provisioning and the
three-bad-tag fault/zeroize threshold.

The deliberate final test ended in:

```text
SESSION_FAULT_LOCKED
fault_o = 1
last_error = ERR_AUTH_THRESHOLD (0x0601)
session_id = 0
```

Heartbeat continued in the locked fault state.

This permits:

```text
Primer #2 standalone hardware qualification: PASS
standalone_hardware_qualified = true
```

The external `fatal_latched_i` input was not asserted and the external
`zeroize_ni` input was not pulsed because they were strapped. Command zeroize is
a separate tested path. The fixture does not qualify Tiny behavior even though
it emulates the secure-enable level.

## Next integration gate

The next scoped gate is:

```text
Primer #1 uart_tx_o -> Primer #2 uart_rx_i
```

P1 and P2 must be staged and committed with byte-identical session ID, Ascon key
and nonce prefix. Both must enter `ACTIVE` before P1 sends sequence 1. Sequence
must start at 1 and remain contiguous.

See `docs/P1_TO_P2_UART_INTEGRATION_NEXT_GATE.md` for the wiring, provisioning,
positive-path, negative-path and evidence requirements.

## Qualification boundary

Current accepted status:

```text
Primer #2 exact-device build candidate:        PASS
Primer #2 standalone ESP32-C3 qualification:   PASS
P1 -> P2 direct UART integration:              NOT RUN
SN32 -> P2 control plane:                      NOT RUN
Tiny safety integration:                       NOT RUN
full-system hardware qualification:            NOT RUN
```

Therefore the generic/full-system `hardware_qualified` flag remains false.
Detailed evidence is in:

- `docs/VERIFICATION_STATUS.md`;
- `docs/STANDALONE_HARDWARE_QUALIFICATION_2026-08-03.md`;
- `hardware/esp32c3_standalone_qualification/README.md`;
- `hardware/esp32c3_standalone_qualification/evidence/serial_monitor_2026-08-03.txt`.
