# Primer #2 deployment build

Primer #2 is the authenticated receive target for the direct 66-byte UART
payload from Primer #1. The deployment source implements SPI
control/reconciliation, session stage/commit/activation, UART framing, replay
checks, Ascon-AEAD128 decrypt/tag verification, single-entry plaintext
quarantine, diagnostics, zeroize and fail-closed safety handling.

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

The same gate is available in GitHub Actions through the
`portable-protocol` workflow. Accept the RTL gate only when both jobs are green.

The 2026-08-03 qualification record contains current reference and static PASS
results. A current nine-bench Icarus result was not included with that hardware
evidence and remains separately tracked.

## Authoritative SystemVerilog 2017 build flow

`trinity_primer2.gprj` is the source/device/file-list project. Generated local
state below `primer2/gowin/impl/` is not authoritative.

The source-controlled authority is `primer2/gowin/run.tcl`. It deletes stale
implementation state, selects the exact device and top, then applies:

```tcl
set_option -verilog_std sysv2017
```

Clean build:

```bash
cd primer2/gowin
gw_sh run.tcl
```

Windows evidence build:

```powershell
powershell -ExecutionPolicy Bypass -File primer2/scripts/run_exact_device_build.ps1 `
  -GwSh "C:\path\to\Gowin\IDE\bin\gw_sh.exe" `
  -Python "py" -PythonArgs @("-3")
```

The evidence runner executes static/reference checks, invokes the clean exact
device build, verifies the `.fs`, computes its SHA-256, extracts implementation
metrics, records Git state, checks whitespace and guards qualified Primer #1
implementation paths. It rejects warning `EX2664`.

## Post-fix exact-device candidate

Qualification source:

```text
7588063e636da225bbe81632efe1060f4c825c37
```

Recorded build:

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

The bitstream path is
`primer2/gowin/impl/pnr/trinity_primer2.fs`. Its SHA-256 was not recorded.
`LW = 8/8` remains an accepted routing-capacity risk.

## Safety-input boundary

Integrated signal ownership remains:

```text
Primer #1 uart_tx_o       -> Primer #2 uart_rx_i
Tiny secure_enable_o      -> Primer #2 secure_enable_i
Tiny zeroize_no           -> Primer #2 zeroize_ni
Tiny fault_latched_o      -> Primer #2 fatal_latched_i
```

The CST remains unchanged. Inputs must not float when their production driver is
absent.

The ESP32-C3 standalone and direct-link fixtures temporarily emulate only the
controlled enable level. They do not qualify Tiny behavior.

## Primer #2 standalone hardware result

Official fixture:

```text
primer2/hardware/esp32c3_standalone_qualification/
```

Recorded result:

```text
PASS count = 23
FAIL count = 0
OVERALL    = PASS
```

This permits:

```text
Primer #2 standalone hardware qualification: PASS
standalone_hardware_qualified = true
```

The external fatal input and physical active-low zeroize input remain untested.

## P1 -> P2 direct UART hardware result

Official dual-SPI fixture:

```text
primer2/hardware/p1_to_p2_uart_integration/
```

Locked physical payload connection:

```text
Primer #1 R13 uart_tx_o -> Primer #2 R13 uart_rx_i
ESP32-C3 GPIO7          -> INPUT/high-impedance monitor only
```

Harness commit:

```text
7fcf9171938114f07fb3e21157abbbc77074720c
```

Recorded result:

```text
PASS count = 11
FAIL count = 0
OVERALL = PASS
P1 -> P2 direct UART integration: PASS
```

The run demonstrated common stage/commit/activation, sequence 1 and sequence 2
byte-exact authenticated transfer, wrong-ACK fail-closed behavior and
pending-result overwrite protection. The expected protected-drop record was:

```text
last_error         = 0x0506
diagnostic_summary = 0x00000080
```

Evidence:

```text
primer2/docs/P1_TO_P2_UART_HARDWARE_QUALIFICATION_2026-08-03.md
primer2/hardware/p1_to_p2_uart_integration/evidence/serial_monitor_2026-08-03.txt
```

This permits:

```text
p1_to_p2_uart_hardware_qualified = true
```

It does not permit SN32, Tiny or full-system qualification claims.

## Qualification boundary

```text
Primer #2 exact-device build candidate:        PASS
Primer #2 standalone ESP32-C3 qualification:   PASS
P1 -> P2 direct UART integration:              PASS
SN32 -> P1/P2 control plane:                   NOT RUN
Tiny safety integration:                       NOT RUN
full-system hardware qualification:            NOT RUN
```

Therefore:

```text
hardware_qualified             = false
full_system_hardware_qualified = false
```

## Next integration gate

Recommended but not yet implemented:

```text
SN32 -> P1/P2 dual-SPI control plane
```

The next harness must preserve the qualified direct P1-to-P2 UART payload path.
Tiny safety integration remains separate.

Detailed evidence and status are in:

- `docs/VERIFICATION_STATUS.md`;
- `docs/STANDALONE_HARDWARE_QUALIFICATION_2026-08-03.md`;
- `docs/P1_TO_P2_UART_HARDWARE_QUALIFICATION_2026-08-03.md`;
- `hardware/esp32c3_standalone_qualification/`;
- `hardware/p1_to_p2_uart_integration/`.
