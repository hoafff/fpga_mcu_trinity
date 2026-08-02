# Trinity Primer #1 deploy target

## Locked target

- Device: `GW2A-LV18PG256C8/I7`, database `GW2A-18C/gw2a18c-011`.
- Device version C, PBGA256, C8/I7.
- Clock/top: 27 MHz, `primer1_top`.
- Tool: Gowin EDA `V1.9.11.03 Education x64`.
- Project: `gowin/trinity_primer1.gprj`.

The canonical project uses relative paths and SystemVerilog 2017. Mandatory
NTT, INTT, BaseMul, Ascon-AEAD128, SPI, UART, retained transactions, session,
zeroize, heartbeat and fail-closed safety logic are implemented; none is stubbed.

## Preserved hardware baseline

Commit `927aa99e2e2ee732f95686fde165e9755e31f43a` remains the earlier standalone
bring-up baseline:

```text
Synthesis/PnR/bitstream:       PASS
Actual Fmax:                   27.009 MHz
Worst setup slack:             +0.012 ns
Setup/Hold violations:         0 / 0
Logic/Register/CLS:            75% / 57% / 90%
BSRAM/DSP:                     2 DPB / 1 MULT18X18
Standalone heartbeat/fault/IRQ/UART-idle: PASS
```

It remains a regression reference only. The current source has its own complete
build and hardware evidence below; the baseline timing is not reused.

## RTL verification status

The command-core review findings were first reproduced by RTL tests and then
corrected. Verification covers:

- non-zero NTT, INTT and BaseMul differential vectors;
- two Ascon-AEAD128 vectors, including official Count 817, plus abort;
- SPI Mode 0 maximum payload, CRC rejection and response mailbox construction;
- UART byte and frame serialization;
- deployment-top idle, MISO high-Z, heartbeat and safety synchronization;
- RUN_SELF_TEST mask execution and returned mask;
- explicit ZEROIZE scope policy: only `ZEROIZE_ALL` is accepted;
- ABORT_SESSION ID validation and context preservation on mismatch;
- GET_STATUS/GET_TXN_RESULT during long-running retained operations;
- POLY_BEGIN rejection while an unretired result remains ready.

Run locally with Icarus Verilog installed:

```text
python primer1/scripts/reference_checks.py
python primer1/scripts/static_check.py
python primer1/scripts/check_command_arch.py
python primer1/tb/run.py
git diff --check
```

The machine-generated result remains at `docs/RTL_SIMULATION_LATEST.md`.

## Current exact-device build

The source tree at
`c8135b5304c0318c7ec24787484dc8a4c4aa0278` was rebuilt using the locked target
and toolchain. The supplied timing and PnR reports record:

```text
Synthesis:                    PASS, operator-reported
Place and route:              PASS
Output generation:            PASS
Clock constraint:             27.000 MHz / 37.037 ns
Actual Fmax:                  27.025 MHz
Worst setup slack:            +0.035 ns
Worst reported hold slack:    +0.307 ns
Setup violated endpoints:     0
Hold violated endpoints:      0
Setup/Hold TNS:               0.000 / 0.000 ns
Paths/endpoints analyzed:     28124 / 26241
Logic/Register/CLS:           79% / 57% / 91%
BSRAM:                        2 DPB
DSP:                          1 MULT18X18
LW clock:                     8/8 = 100%
```

The timing HTML shows 27.025 MHz; the text `.tr` rendering rounds the same result to 27.026 MHz. The conservative 27.025 MHz value is used here.

The clock and six narrow input-to-first-synchronizer false paths are active in
the report. No unexpected unconstrained-path or unrouted-net diagnostic appears
in the supplied reports. The reports do not expose a separate numeric
unconstrained-path count, so none is invented here.

The margin remains critical: WNS is only +0.035 ns, CLS is 91% and LW clock use
is 100%. Any RTL, constraint, tool-option or placement change requires a clean
rerun of synthesis, PnR and STA.

## Current bitstream

The generated `trinity_primer1.fs` was SRAM-programmed successfully. Its
SHA-256 is:

```text
168459a32fe5545ff77ff5bf590f4b2d84b0fcdd148739324dbba568f8c1f510
```

The `.fs` header identifies Gowin EDA V1.9.11.03 Education,
`GW2A-LV18PG256C8/I7`, device version C and PBGA256. Generated `*.fs` files
remain excluded by `.gitignore`; the complete artifact identity is recorded in
`hwtest/evidence/ARTIFACT_MANIFEST.md`.

SRAM Program is volatile. Reload the `.fs` after every Primer power cycle.

## Scoped hardware qualification

The current build passed the following on hardware with an ESP32-C3 master:

```text
Basic heartbeat/fault/IRQ/UART idle:          PASS
GET_INFO / GET_STATUS / CRC / mailbox / IRQ: PASS
RUN_SELF_TEST mask 0x013E and retirement:    PASS
STAGE and ABORT_SESSION ID validation:       PASS
COMMIT_SESSION and secure-enable activation: PASS
Non-zero Ascon current-RTL vector:            PASS
66-byte UART frame byte-exact comparison:    PASS
Unsupported ZEROIZE scope rejection:         PASS
ZEROIZE_ALL and final clean state:            PASS
Final aggregate result:                       PASS
```

The exact sketch ZIP and reproducible procedure are preserved under `hwtest/`.
SHA-256 identities for the supplied serial log, reports, screenshot and `.fs`
are recorded in the artifact manifest. The formal scope decision is
`docs/PRIMER1_HARDWARE_QUALIFICATION_c8135b53.md`.

Sticky `last_error` and `diagnostic_summary` values from earlier malformed CS
traffic and deliberately generated test errors are history, not a live hardware
fault. Do not change RTL merely to clear them.

## Remaining Primer #1 hardware gates

The current hardware package does not independently cover:

1. external non-zero POLY command vectors over SPI;
2. GET_STATUS/GET_TXN_RESULT arriving while a representative operation is busy;
3. POLY_BEGIN rejection while `OP_RESULT_READY` remains unretired.

Those behaviors remain regression-covered in simulation. Therefore the correct
classification is:

```text
RTL verification:                       PASS
Current exact-device build:             PASS
Current .fs SRAM programming:           PASS
Scoped hardware qualification:          PASS
Full external polynomial hardware test: OPEN
Full Primer #1 hardware qualification:  NOT CLAIMED
```
