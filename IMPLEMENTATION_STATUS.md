# Implementation status

Status date: 2026-08-05

## Corrective control-plane baseline

A structural mismatch was found between the Primer IRQ contract and the SN32
master policy:

```text
old Primer IRQ_N LOW = response mailbox OR retained/authenticated result state
old SN32 policy       = any IRQ_N LOW means a response mailbox must be drained
```

That combination could prevent `GET_TXN_RESULT`, `RETIRE_TXN_RESULT`,
`READ_AUTH_RESULT` and `ACK_AUTH_RESULT` from being issued after the preceding
mailbox had already been consumed. Dummy response-read clocks could then be
parsed as a malformed request and create another error mailbox.

The corrected implementation contract is recorded in:

```text
ai_context/interfaces/SPI_CONTROL_PLANE_ICD_v0.2.md
```

The corrected rule is:

```text
IRQ_N LOW  <=> one complete response mailbox is physically ready to read
retained/authenticated result state is queried explicitly and does not hold IRQ
non-magic request windows are discarded silently and create no error mailbox
```

## Current source identities

```text
Primer #1 build ID = 0x5031D003
Primer #2 build ID = 0x50320002
SN32 version/build = 0.7.25 / 0x00070019
PC host version    = 0.3.8
```

Key source/evidence commits:

```text
Primer #1 corrected source baseline: 0b78e007dca49f8f309ba99f3ede54bd6f3349e7
Primer #2 corrected source/test baseline: a14abb631b66e43acfedcea292d84dd8fcf63291
PC-host corrected identity baseline: a153ce41bd5f0396db4684801e449dbd38783ea5
SPI ICD v0.2 baseline: d0856c36a23ad5942e4fd8f19edd4945ef7ee248
```

## Verification boundary

| Target | Portable/static/RTL | Exact-device build | Programmed hardware |
|---|---|---|---|
| Primer #1 corrected image | RTL regression PASS; silent non-magic-window test PASS | REBUILD REQUIRED | NOT PROGRAMMED / NOT QUALIFIED |
| Primer #2 corrected image | Reference/static/full RTL regression PASS; silent non-magic-window test PASS | REBUILD REQUIRED | NOT PROGRAMMED / NOT QUALIFIED |
| SN32 v0.7.25 | Existing portable controller/host checks PASS in repository CI | Keil ArmClang rebuild required on current source | User hardware still reported v0.7.24; v0.7.25 must be flashed |
| PC host 0.3.8 | Unit tests PASS before identity migration commit | Not applicable | Reinstall editable package required |
| Tiny 1P5 | Unchanged by this correction | Unchanged | No new programming required for the first corrected SPI gate |

Primer #1 RTL evidence:

```text
primer1/docs/RTL_SIMULATION_LATEST.md
```

Primer #2 RTL evidence:

```text
primer2/docs/RTL_SIMULATION_LATEST.md
primer2/docs/TESTBENCH_PORTABILITY_MIGRATION_LATEST.md
```

The RTL/source PASS results do not constitute Gowin synthesis, place-and-route,
STA, bitstream generation or physical qualification.

## Hardware evidence boundary

Previous ESP32-C3 standalone and direct P1-to-P2 UART results remain historical
evidence for the older programmed images. They do not qualify the corrected
`0x5031D003` / `0x50320002` images.

The current corrected system state is:

```text
corrected Primer source:                  PASS
corrected Primer RTL regression:          PASS
corrected Primer exact-device build:      NOT RUN
corrected Primer bitstream SHA-256:        NOT RECORDED
corrected Primer programming:              NOT RUN
SN32 v0.7.25 exact rebuild/programming:    NOT RUN ON USER HARDWARE
corrected shared-SPI hardware gate:        NOT RUN
corrected retained RUN/QUERY/RETIRE gate:  NOT RUN
current full-system hardware qualified:    false
```

## Required next sequence

```text
1. Preserve the user's existing modified/untracked local files.
2. Fast-forward the local repository to current origin/main.
3. Rebuild Primer #1 in Gowin; require synthesis/P&R/STA PASS and record .fs hash.
4. Rebuild Primer #2 in Gowin; require synthesis/P&R/STA PASS and record .fs hash.
5. Program P1 build 0x5031D003 and P2 build 0x50320002.
6. Rebuild and flash SN32 v0.7.25 / 0x00070019.
7. Reinstall PC host 0.3.8.
8. Cold boot P1/P2 first and SN32 last.
9. Run the one-shot corrected control-plane qualification.
10. Only after that PASS, rerun direct UART/session/telemetry and Tiny gates.
```

No full-system or corrected-hardware PASS is claimed by this status file.
