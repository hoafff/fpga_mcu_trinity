# Trinity Primer #1 deploy target

## Locked target

- Device: `GW2A-LV18PG256C8/I7`
- Clock: 27 MHz on `sys_clk_i`
- Top: `primer1_top`
- Tool: Gowin EDA `V1.9.11.03 Education x64`
- GUI project: `gowin/trinity_primer1.gprj`
- Batch project: run `gw_sh run.tcl` from `primer1/gowin/`

## Implemented source scope

The target is self-contained under `primer1/` and implements:

- SPI Mode-0, MSB-first request/response endpoint with CRC16/CCITT-FALSE;
- high-impedance MISO while deselected and active-low level IRQ;
- GET_INFO/GET_STATUS, retained transaction reconciliation and all Primer #1 commands;
- two 256x16 polynomial memories intended for Gowin BSRAM inference;
- iterative ML-KEM-512 NTT, INTT and BaseMul using one arithmetic datapath;
- NIST SP 800-232 Ascon-AEAD128 encrypt-only, fixed AD=24 B and plaintext=24 B;
- direct 66-byte UART frame `A5 5A || AD || ciphertext || tag` at 115200 8N1;
- staged/active session state, sequence and fail-closed Tiny safety controls;
- sequential zeroization, heartbeat, fault latch and built-in primitive self-test flow.

No mandatory block is stubbed, bypassed or removed for fitting.

## Polynomial interface contract

SPI coefficients are canonical unsigned little-endian values `0..3328`.

- NTT input: standard domain, normal order.
- NTT output: standard-domain residues, upstream bit-reversed order.
- INTT input: standard-domain residues, upstream bit-reversed order.
- INTT output: standard domain, normal order, with `INTT(NTT(a)) = a mod q`.
- BaseMul input/output: standard-domain residues in the same bit-reversed NTT order.

Internally the zeta table is Montgomery encoded. The iterative datapath converts
BaseMul and INTT results at the hardware interface boundary so Montgomery scaling
is not exposed over SPI.

## Build

Open `gowin/trinity_primer1.gprj`, confirm `primer1_top`, then run Synthesis and
Place & Route. Do not add source outside this directory.

The current source status is **GOWIN BUILD PENDING**. Simulation/reference checks
do not imply resource, timing, programming or hardware PASS.

After build, preserve and send:

1. synthesis log/report;
2. place-and-route log/report;
3. timing report including unconstrained paths;
4. utilization report (LUT, DFF, BSRAM, DSP, PLL);
5. pin report;
6. all warnings/errors and the generated `.fs` status.
