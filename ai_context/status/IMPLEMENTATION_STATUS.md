# Implementation Status

## Evidence summary

| Item | Status |
|---|---|
| Architecture/System Spec v0.4 | `CONFIRMED` |
| SPI and PC↔SN32 ICDs | `CONFIRMED` implementation baseline |
| SN32 S0 exact Keil build | `PASS` for the prior S0 scope |
| Primer #1 exact-device synthesis | `PASS` at commit `927aa99` |
| Primer #1 place and route | `PASS` |
| Primer #1 timing at 27 MHz | `PASS WITH CRITICAL MARGIN` — Fmax 27.009 MHz, WNS +0.012 ns |
| Primer #1 bitstream generation | `PASS` |
| Primer #1 JTAG SRAM programming | `PASS` |
| Primer #1 standalone heartbeat/fault/IRQ/UART-idle | `PASS` |
| Primer #1 standalone basic hardware bring-up | `PASS` |
| SN32↔Primer #1 SPI/control-plane | `PENDING HARDWARE TEST` |
| Primer #1 retained self-test lifecycle | `PENDING HARDWARE TEST` |
| Primer #1 full hardware qualification | `NO` |
| Primer #2/Tiny/full system | `NOT TESTED` |

Primer #1 risk remains high: WNS is only `+0.012 ns`, CLS utilization is 90%,
and LW clock utilization is 100%. Any P1 RTL/project/constraint change requires
complete exact-device synthesis, P&R and timing evidence again.

## Current source gate

The repository now contains a P1-only control-plane bring-up path:

```text
PC PING
-> SN32/P1 GET_INFO
-> SN32/P1 GET_STATUS
-> SN32/P1 RUN_SELF_TEST
-> SN32/P1 GET_TXN_RESULT
-> SN32/P1 RETIRE_TXN_RESULT
```

- SN32 project: `sn32/keil/trinity_sn32f407_deploy.uvprojx`.
- PC command: `python -m trinity_host.cli --port COMx p1-bringup`.
- P1-only mode does not require or probe Primer #2.
- Session, encryption, payload UART and Tiny integration remain outside this gate.

The modified SN32 deploy source still requires a new exact ArmClang build, flash
and runtime log. Source/static/portable tests are not hardware evidence.

## Hardware qualification boundary

`Primer #1 standalone basic hardware bring-up: PASS` proves only JTAG SRAM load,
bitstream execution, heartbeat, inactive fault, idle IRQ and idle UART TX. It
does not prove SPI framing, GET/STATUS, self-test, NTT/INTT/BaseMul, Ascon,
session, zeroize or integrated behavior. `hardware_qualified` therefore remains
false for every target and for the full system.
