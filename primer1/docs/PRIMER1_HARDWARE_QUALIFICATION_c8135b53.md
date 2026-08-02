# Primer #1 scoped hardware qualification — c8135b53

## Decision

**PASS within the explicitly tested scope.**

The source tree at commit `c8135b5304c0318c7ec24787484dc8a4c4aa0278`
passed the exact-device Gowin implementation gate, SRAM programming and the
hardware control-plane/session/Ascon/UART/ZEROIZE suite described below. No new
RTL defect was demonstrated, so this evidence-only update does not modify RTL,
constraints or the existing simulation suite.

This is a scoped qualification, not a claim that every Primer #1 command and
mathematical datapath has been independently exercised with external non-zero
hardware vectors.

## Evidence reviewed

- full serial-monitor history including failed bring-up attempts and the final PASS run;
- standalone monitor, minimal SPI diagnostic and comprehensive ESP32-C3 test sources;
- exact-device timing report and PnR report;
- generated `.fs` header and SHA-256;
- final serial-monitor screenshot;
- existing RTL simulation result at the qualified source commit.

Artifact identities are locked in
`primer1/hwtest/evidence/ARTIFACT_MANIFEST.md`. The exact ESP32 source ZIP is
retained in Git. Generated bitstream/report/image artifacts remain external and
are referenced by SHA-256 rather than being duplicated into the repository.

## Exact-device implementation result

| Item | Result |
|---|---|
| Qualified source tree | `c8135b5304c0318c7ec24787484dc8a4c4aa0278` |
| Device | `GW2A-LV18PG256C8/I7` |
| Device/version reported by tools | `GW2A-18`, version `C` |
| Database selection | `GW2A-18C / gw2a18c-011` |
| Tool | Gowin EDA V1.9.11.03 Education |
| Clock constraint | 27.000 MHz / 37.037 ns |
| Synthesis | PASS, operator-reported; downstream PnR used the generated `trinity_primer1.vg` |
| Placement and routing | PASS; placement, routing and output-file generation completed |
| Actual Fmax | 27.025 MHz |
| Worst setup slack | +0.035 ns |
| Worst reported hold slack | +0.307 ns |
| Setup violated endpoints | 0 |
| Hold violated endpoints | 0 |
| Setup/Hold TNS | 0.000 / 0.000 ns |
| Paths/endpoints analyzed | 28,124 / 26,241 |
| Logic | 16,289 / 20,736 = 79% |
| Registers | 9,170 / 16,173 = 57% |
| CLS | 9,396 / 10,368 = 91% |
| BSRAM | 2 DPB |
| DSP | 1 MULT18X18 |
| LW clock | 8 / 8 = 100% |

The timing HTML reports 27.025 MHz while the text `.tr` rendering rounds the same result to 27.026 MHz; this dossier uses the conservative 27.025 MHz value.

The timing report marks the 27 MHz clock and all six intended asynchronous
input-to-first-synchronizer false paths as active. No unexpected unconstrained-
path diagnostic appears in the supplied report. The PnR report contains no
routing error or unrouted-net warning and proceeds through output generation.
These statements describe the supplied reports; they do not invent a separate
numeric unconstrained-path counter that the reports do not provide.

The margin remains critical. WNS improved from the earlier +0.012 ns baseline
to +0.035 ns, but CLS is 91% and LW clock use is 100%. Any RTL, constraint,
tool-option or placement change invalidates this timing result.

## Bitstream and basic bring-up

The generated `trinity_primer1.fs` has SHA-256:

```text
168459a32fe5545ff77ff5bf590f4b2d84b0fcdd148739324dbba568f8c1f510
```

Its header identifies the correct tool, C-version part and PBGA256 package. It
was loaded successfully with Gowin Programmer using SRAM Program.

Observed stable basic signals:

```text
heartbeat_o: approximately 5.0 Hz
fault_o:      0
irq_no:       1 while idle
uart_tx_o:    1 while idle
abnormal heat: not observed
```

SRAM programming is volatile. A Primer power cycle requires reloading the `.fs`.

## Accepted hardware transaction sequence

### SPI transport and identity

GET_INFO and GET_STATUS passed request/response CRC, response mailbox and IRQ
handling. GET_INFO returned:

```text
target_id        = 1
protocol_version = 1
capabilities     = 0x000011FF
build_id         = 0x50310001
reserved         = 0
```

A historical GPIO10-to-T14 wiring mistake is excluded from RTL findings. The
accepted wiring uses GPIO10 to R14 (`spi_cs_ni`) and GPIO6 from T14 (`irq_no`).

### RUN_SELF_TEST

The hardware sent command `0x03`, retained transaction `0x0100`, payload
`01 3E 00 00`. ACK, polling, result and retirement passed:

```text
transaction_state = SUCCEEDED
original_command  = 0x03
result_code       = 0x0000
result_length     = 2
result_data       = 01 3E
```

After retirement, the session was READY_NO_SESSION, operation IDLE,
SELF_TEST_PASS was set and `fault_o=0`.

This proves the masked self-test execution path on hardware. It does not replace
external non-zero polynomial vector testing.

### Session lifecycle and ABORT_SESSION

- STAGE_SESSION with `0x10203040`: PASS, entered STAGED.
- ABORT_SESSION with `0xDEADBEEF`: correctly rejected with `0x0402`; staged context remained intact.
- ABORT_SESSION with `0x10203040`: PASS, returned to READY_NO_SESSION.
- STAGE_SESSION with `0x11223344`: PASS.
- COMMIT_SESSION while secure-enable LOW: ACK and retained SUCCEEDED result passed; entered COMMITTED_BLOCKED.
- ESP32 GPIO20 asserted secure-enable: entered ACTIVE with session ID preserved and no fault.

### Ascon and UART

The accepted non-zero transaction sequence was:

```text
STAGE_SESSION
COMMIT_SESSION
secure_enable_i = 1
LOAD_TELEMETRY
ENCRYPT_AND_SEND
GET_TXN_RESULT
UART frame capture
RETIRE_TXN_RESULT
```

The retained result reported source command `0x31`, SUCCEEDED, code `0x0000`,
session `0x11223344`, sequence 1 and 66 bytes sent. The captured UART frame was
exactly 66 bytes, began with `A5 5A`, and matched the expected associated data,
ciphertext and tag byte-for-byte for the committed software model of this RTL.

Classification: **Ascon current-RTL vector and UART serialization hardware PASS**.
This is not a blanket independent certification of all Ascon inputs or another
Ascon implementation variant.

### ZEROIZE policy and execution

- Scope `0x01`: correctly rejected with `ERR_NOT_SUPPORTED` (`0x0702`), detail `0x0001`.
- Scope `0xFF`: ACK passed; retained state ZEROIZED, source command `0x06`, code `ERR_ZEROIZED` (`0x0403`), length 0; retirement passed.

Final status passed:

```text
session_state         = READY_NO_SESSION
operation_state       = IDLE
pending_flags         = 0
secure_flags          = 0x01
session_id            = 0
active_transaction_id = 0
fault_o               = 0
irq_no                = 1
uart_tx_o             = 1
heartbeat_o           = approximately 5 Hz
```

## Sticky history disposition

The accepted run contains sticky history values created by test or bring-up
traffic:

- `last_error=0x0103`, `diagnostic_summary=0x00000001`: earlier empty or malformed CS transactions;
- `last_error=0x0402`: deliberate wrong-session ABORT test;
- `last_error=0x0403`: deliberate successful ZEROIZE result history.

These values coexist with `fault_o=0` and later successful commands. They are
not a new RTL defect and must not be erased by an evidence-driven RTL change.

## Simulation-only confirmations retained

The following remain confirmed by the existing RTL regression suite and were
not independently reproduced in this hardware run:

- GET_STATUS and GET_TXN_RESULT are serviced while the core is busy;
- POLY_BEGIN is rejected while `OP_RESULT_READY` has not been retired;
- non-zero NTT, INTT and BaseMul differential vectors;
- standalone block-level SPI/UART/top edge cases beyond this transaction trace.

The simulation suite remains authoritative regression evidence for these cases
and was not deleted or altered.

## Remaining Primer #1 hardware gaps

1. External non-zero polynomial command flow over SPI:
   `POLY_BEGIN`, all required `POLY_WRITE_CHUNK` transfers, `POLY_EXECUTE`,
   `POLY_READ_CHUNK`, mathematical comparison and result retirement.
2. A deliberately timed hardware request proving GET_STATUS/GET_TXN_RESULT is
   not dropped during each representative long-running operation.
3. A hardware attempt proving POLY_BEGIN returns the expected rejection while
   an `OP_RESULT_READY` result remains unretired.
4. Optional extended robustness: repeated power cycles, repeated sessions,
   signal-integrity limits above the 100 kHz bring-up SPI rate and longer soak.

## Closed status

```text
RTL regression suite:                         PASS
Exact-device synthesis/PnR/STA at 27 MHz:    PASS
New .fs generation and SRAM Program:          PASS
Basic electrical/idle bring-up:               PASS
SPI identity/status/CRC/mailbox/IRQ:           PASS
RUN_SELF_TEST mask 0x013E:                    PASS
Session/ABORT/COMMIT/secure-enable:            PASS
Ascon current-RTL vector + 66-byte UART:       PASS
ZEROIZE scope policy and ZEROIZE_ALL:          PASS
Scoped Primer #1 hardware qualification:      PASS
Full external polynomial hardware coverage:   OPEN
Full Primer #1 hardware qualification:        NOT CLAIMED
```
