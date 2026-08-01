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
- SN32 S0 exact-target project structure, compile/link, AXF/HEX/MAP generation
  and memory layout validated with the authoritative local Keil environment;
- S0 has zero Trinity-owned source warnings and one narrowly accepted SONiX DFP
  1.0.1 warning in `system_SN32F400.c`;
- SN32 hardware programming and execution remain untested;
- S1 and later milestones are not started;
- no Gowin, timing, integrated hardware or full-deployment PASS is claimed.
