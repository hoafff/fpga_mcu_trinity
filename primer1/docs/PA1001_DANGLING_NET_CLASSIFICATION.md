# Primer #1 Gowin PA1001 classification

## Evidence source

Exact-device run on commit `63b5ab2b6335557683a6e536170b6a41a3246c14`:

- Gowin EDA V1.9.11.03 Education x64;
- `GW2A-LV18PG256C8/I7`, database `GW2A-18C`;
- synthesis completed and generated `trinity_primer1.vg` and the synthesis report;
- place-and-route stopped while processing the netlist because inferred DPB ports used unsupported read-before-write mode `WRITE_MODE=2'b10`.

The same log contains 782 `PA1001 Dangling net` warnings.

## Classification

Run:

```text
python scripts/classify_pa1001.py <gowin-log.txt> --require-known
```

The supplied run classifies as:

```text
PA1001 total: 782
module mlkem_poly_accel: 53
module primer1_command_core: 701
module spi_packet_endpoint: 28
category DSP_OPTIONAL_OUTPUT: 40
category EXPLICITLY_TRUNCATED_ARITHMETIC_TAIL: 13
category SYNTHESIZED_FIXED_WIDTH_SUM_TAIL: 729
unknown: 0
```

### `mlkem_poly_accel`: 53

- 18 `SOA[*]` and 18 `SOB[*]`: unused optional/cascade outputs of the inferred multiplier macro.
- 4 `DOUT[32:35]`: upper physical multiplier output bits above the required signed 32-bit product.
- 5 `add_*_SUM` and 8 `n299..n306_*_SUM`: high arithmetic tails discarded at explicit modular-representation boundaries.

These are generated primitive/carry outputs, not disconnected NTT, INTT or BaseMul result signals.

### `spi_packet_endpoint`: 28

All match generated `n<id>_<bit>_SUM` names. They are carry/sum tails produced while implementing fixed-width packet length, index and CRC datapaths. No source-level request, response, CRC or mailbox output is unconnected.

### `primer1_command_core`: 701

All match generated `n<id>_<bit>_SUM` names. They are pruned high bits from fixed-width additions, shifts, response packing and address/index arithmetic. The warning names are synthesis-generated and do not identify a disconnected source-level command, session, retained-result, UART, zeroize or safety signal.

This classification is structural, not a waiver. Any new PA1001 name or module that does not match the known categories is reported as `UNKNOWN_*`; `--require-known` then exits nonzero.

## Source correction made in this phase

The polynomial memories now use an explicit normal/no-change DPB template. During a write, the corresponding output register holds its previous value instead of requesting read-before-write behavior. NTT, INTT and BaseMul already separate read and write FSM phases, so arithmetic does not depend on collision data.

The unused `read_start_hold` prefetch register was also removed. No warning is suppressed and no generated `.vg` file is edited.

## Build status

After this source correction:

- reference and static source checks can pass;
- exact-device synthesis, P&R, timing and bitstream generation must be rerun;
- build PASS must not be claimed until P&R succeeds, 27 MHz timing passes, unrouted nets are zero and a new `.fs` is generated.
