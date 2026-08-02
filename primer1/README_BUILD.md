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

Commit `927aa99e2e2ee732f95686fde165e9755e31f43a` and its generated
`gowin/impl/pnr/trinity_primer1.fs` remain the accepted standalone hardware
bring-up baseline:

```text
Synthesis:                    PASS
Place and route:              PASS
Bitstream generation:         PASS
Clock constraint:             27.000 MHz
Actual Fmax:                  27.009 MHz
Worst setup slack:            +0.012 ns
Setup violated endpoints:     0
Hold violated endpoints:      0
Setup/Hold TNS:               0.000 / 0.000 ns
Logic/Register/CLS:           75% / 57% / 90%
BSRAM:                        2 DPB
DSP:                          1 MULT18X18
LW clock:                     8/8 = 100%
JTAG SRAM program:            PASS
heartbeat_o:                  PASS, approximately 5.0 Hz
fault_o:                      PASS, logic 0
irq_no idle:                  PASS, logic 1
uart_tx_o idle:               PASS, logic 1
```

This baseline is intentionally preserved for regression comparison. It is not a
build result for the current RTL and is not full hardware qualification.

## Current RTL verification status

The command-core review findings were first reproduced by RTL tests and then
corrected. Current verification covers:

- nonzero NTT, INTT and BaseMul differential vectors;
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

The machine-generated result is committed at
`docs/RTL_SIMULATION_LATEST.md`.

## Exact-device rebuild boundary

The timing result from `927aa99` is invalid for the current RTL. Before producing
or programming a replacement bitstream, rerun from a clean Gowin project:

```text
Device:      GW2A-LV18PG256C8/I7
Database:    GW2A-18C / gw2a18c-011
Clock:       27.000 MHz / 37.037 ns
Tool:        Gowin EDA V1.9.11.03 Education x64
Project:     primer1/gowin/trinity_primer1.gprj
```

Required acceptance evidence:

```text
Synthesis PASS
Place and route PASS
Actual Fmax >= 27.000 MHz
Worst setup slack >= 0
Setup violated endpoints = 0
Hold violated endpoints = 0
Setup TNS = 0
Hold TNS = 0
Unconstrained paths reviewed
Unrouted nets = 0
2 DPB retained
1 MULT18X18 retained
new trinity_primer1.fs generated
```

Until that exact-device rerun passes, the current status is:

```text
RTL verification:             PASS
Current exact-device build:   PENDING
Current bitstream:            NOT GENERATED
Current hardware-qualified:   NO
```

Do not move to another target or full-system qualification before this Primer #1
build gate is closed.
