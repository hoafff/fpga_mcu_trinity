# FPGA MCU Trinity

Competition project for PC host, SN32F407F, two Gowin Primer 20K boards and one
Tiny 1P5 supervisor.

```text
PC <-> SN32 -- shared SPI --> P1/P2
P1 == direct encrypted UART ==> P2
SN32/P1/P2 -> Tiny supervisor
```

Start with `ai_context/README_AI.md`.

## Current implementation milestone

- architecture and implementation contracts v0.4 remain the system baseline;
- common PC/SN32/SPI protocol foundations are present;
- Primer #1 qualified source is locked at
  `c8135b5304c0318c7ec24787484dc8a4c4aa0278`, with qualification documentation
  at `36822a09c234f509adfa5dace6aa05e4bbd40d54`;
- Primer #2 now contains a self-contained deployment source target for the
  66-byte P1 UART frame, session lifecycle, replay/continuity checks,
  Ascon-AEAD128 authenticated receive, retained result, SPI reconciliation,
  zeroize and safety interfaces;
- Primer #2 portable static/reference checks PASS;
- Primer #2 SystemVerilog simulation is not yet executed because `iverilog` and
  `vvp` are unavailable in the current execution environment;
- Primer #2 Gowin synthesis, P&R, STA, `.fs` generation and physical hardware
  qualification remain OPEN;
- no integrated P1-to-P2 hardware PASS is claimed.

See `IMPLEMENTATION_STATUS.md` and `primer2/README.md` for the evidence boundary.
