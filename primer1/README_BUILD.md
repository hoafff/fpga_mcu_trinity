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

## Exact-device build candidate evidence

Commit `927aa99e2e2ee732f95686fde165e9755e31f43a` was built for the exact device:

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
```

Classification: **exact-device build candidate PASS with critical margin risk**.
The timing margin is only `+0.012 ns`; CLS is 90% and LW clock use is 100%.
Any RTL, constraint, tool-option or placement change requires a complete rerun.

## Standalone basic hardware bring-up evidence

The generated `trinity_primer1.fs` was loaded with Gowin Programmer using
`SRAM Program`. With `fatal_latched_i=0`, `secure_enable_i=0` and
`zeroize_ni=1`, an ESP32-C3 digital monitor measured:

```text
JTAG SRAM program:            PASS
Bitstream execution:          PASS
heartbeat_o:                  PASS, approximately 5.0 Hz
fault_o:                      PASS, logic 0
irq_no idle:                  PASS, logic 1
uart_tx_o idle:               PASS, logic 1
```

Classification: **Primer #1 standalone basic hardware bring-up PASS**.
This does not prove SPI, control-plane framing, self-test, polynomial arithmetic,
Ascon, payload UART, session, zeroize or integrated-system behavior.

Because SRAM Program is volatile, power cycling Primer #1 requires reloading
`gowin/impl/pnr/trinity_primer1.fs` before resetting/running the SN32 controller.

## Next acceptance gate

The next gate is strictly:

```text
PC -> SN32 PING
SN32 -> P1 GET_INFO
SN32 -> P1 GET_STATUS
SN32 -> P1 RUN_SELF_TEST
SN32 -> P1 GET_TXN_RESULT
SN32 -> P1 RETIRE_TXN_RESULT
```

Do not start session, encryption, Primer #2 or Tiny integration until this gate
passes on hardware.
