# FPGA MCU Trinity

Competition project for PC host, SN32F407F, two Gowin Primer 20K boards and one
Tiny 1P5 supervisor.

```text
PC <-> SN32 -- shared SPI --> P1/P2
P1 == direct encrypted UART ==> P2
SN32/P1/P2 -> Tiny supervisor
```

Start with `ai_context/README_AI.md`.

Current milestone:

- architecture and implementation contracts v0.4 approved;
- Gate 1 PC protocol/common types implemented;
- Gate 2 SPI protocol/common types implemented;
- portable Python/C tests and registry consistency checks provided;
- SN32 S0 exact-target Keil project added from a hardware-proven donor;
- SN32 S0 exact ArmClang build, AXF/HEX/MAP and hardware evidence remain pending;
- no Gowin, Keil, timing or hardware PASS is claimed for Trinity.
