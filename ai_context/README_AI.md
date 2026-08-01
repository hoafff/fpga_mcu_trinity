# AI Handoff — FPGA MCU Trinity

## 1. Authority and scope

This repository is a new project. The old `fpga-pqc-secure-telemetry` tree is
reference material only. The active root layout is fixed to five target folders
plus `ai_context/`. Do not restore legacy root folders such as `rtl/`, `targets/`,
`tb/`, `software/`, `constraints/` or `docs/`.

Status vocabulary:

- `CONFIRMED`: fixed by approved architecture or authoritative source.
- `TESTED`: executable test evidence exists for the exact stated source scope.
- `BUILD-PENDING`: exact vendor build has not passed.
- `PHYSICAL-PENDING`: wiring/electrical evidence is incomplete.
- `FAILED`: a required check failed.
- `DEPRECATED`: retained only for traceability; not active deployment source.

## 2. Locked architecture

- PC ↔ SN32: UART 115200 8N1.
- SN32 ↔ two Primer boards: shared SPI Mode 0, MSB first, separate CS/IRQ;
  deselected MISO must be high-Z.
- Primer #1: ML-KEM arithmetic acceleration, Ascon-AEAD128 encrypt and UART TX.
- Primer #2: UART RX, replay handling and Ascon decrypt/tag verification.
- P1 → P2: one-way fixed 60-byte frame.
- Tiny 1P5: supervisor only; it is outside the payload path.

The 60-byte frame is:
`A5 5A | command | transaction_id | length | session_id | sequence |
ciphertext[24] | tag[16] | CRC16`, with sequence starting at 1.

## 3. Current implementation truth

- `tiny1p5/` contains the accepted P0-J19-001 source candidate plus all seven
  synthesizable dependencies and exact CST/SDC. Source-only evidence is inherited
  from the accepted package. Exact Gowin synthesis/P&R/timing is still pending.
- `sn32/` contains only the accepted P0.10/P0.11 guard integration slice. It is
  not a complete Keil firmware project and must not be described as buildable.
- `pc_host/`, `primer1/` and `primer2/` remain unimplemented in this new tree.
- The exact 29 candidate files are preserved. The repository provides
  `ai_context/scripts/check_candidate_hashes.py` to verify them locally.

## 4. P0-J19-001 safety boundary

`P0-J19-001` is an evidence ID, not a connector. The physical candidate is Tiny
J1-9/pin 12 ↔ SN32 P0.10/J11-1. Tiny source drives only `0/Z`; SN32 source locks
P0.10/P0.11 as input/no-pull and disables alternate output owners. This is not
sufficient to authorize the wire. Keep the endpoints disconnected until exact
I/O reports, power-order/injection tests and measured levels pass review.

## 5. Checks

Run from repository root:

```text
python3 ai_context/scripts/check_repository_layout.py
python3 ai_context/scripts/check_candidate_hashes.py
python3 ai_context/tests/tiny1p5/check_j1_9_open_drain.py
bash ai_context/tests/sn32/run_source_guard_test.sh
bash ai_context/tests/tiny1p5/run_iverilog.sh
```

The final two commands require a C compiler and Icarus Verilog respectively.
Do not convert inherited source-only evidence into exact-device or hardware PASS.
