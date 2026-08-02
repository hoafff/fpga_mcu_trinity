# Primer #1 RTL verification

Run from the repository root with Icarus Verilog installed:

```text
python3 primer1/tb/run.py
```

The runner generates deterministic non-zero NTT, INTT and BaseMul vectors under
`primer1/tb/generated/`, compiles each testbench independently and runs all seven
DUT-level suites:

- `mlkem_poly_accel`
- `ascon_aead128_encrypt`
- `spi_packet_endpoint`
- `uart_tx_byte`
- `uart_frame_tx`
- `primer1_command_core`
- `primer1_top`

The command-core suite is intentionally written against the required behavior.
On the unmodified `927aa99` Primer #1 RTL it must reproduce the five review
findings before any RTL fix is accepted. A later PASS is valid only when the same
tests run unchanged against the corrected RTL.

The generated `.fs` from commit `927aa99` remains the standalone hardware
bring-up baseline. RTL simulation commits do not replace that bitstream or its
exact-device evidence.
