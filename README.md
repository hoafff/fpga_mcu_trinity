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

The current corrective control-plane source follows
`ai_context/interfaces/SPI_CONTROL_PLANE_ICD_v0.2.md`:

- Primer `IRQ_N` is LOW only while a complete SPI response mailbox is ready;
- retained side-effect and authenticated-result state is queried explicitly and
  no longer holds IRQ LOW after a mailbox has been consumed;
- a non-magic/dummy CS window is discarded silently and cannot create a new
  `BAD_MAGIC`/`BAD_LENGTH` mailbox;
- P1/P2 MISO outputs remain high-impedance while deselected and their Gowin
  constraints explicitly disable internal pulls;
- the existing shared SCK/MOSI/MISO wiring, separate CS/IRQ lines and direct
  P1-to-P2 UART payload link are unchanged.

Corrected source identities:

```text
Primer #1 build ID = 0x5031D003
Primer #2 build ID = 0x50320002
SN32 version/build = 0.7.25 / 0x00070019
PC host version    = 0.3.8
```

Current evidence boundary:

```text
Primer #1 corrected RTL regression:     PASS
Primer #2 corrected full RTL regression: PASS
PC-host unit tests:                       PASS
P1/P2 exact-device Gowin rebuild:         REQUIRED
P1/P2 corrected bitstreams programmed:    NOT YET
SN32 v0.7.25 rebuilt/flashed by user:      NOT YET
corrected shared-SPI hardware gate:        NOT RUN
full-system hardware qualified:            false
```

Historical ESP32-C3 and P1-to-P2 UART hardware results do not automatically
qualify the corrected Primer images. The next action is exact-device Gowin
build/programming of both Primers, followed by the SN32 v0.7.25 rebuild/flash
and one cold-boot control-plane qualification.

See `IMPLEMENTATION_STATUS.md` for the exact evidence and non-claim boundary.
