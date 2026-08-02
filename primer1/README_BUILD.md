# Trinity Primer #1 deploy target

## Locked target

- Device part: `GW2A-LV18PG256C8/I7`
- Gowin database identity: `GW2A-18C` / `gw2a18c-011`
- Device version: C; package: PBGA256; speed: C8/I7
- Clock: 27 MHz on `sys_clk_i`
- Top: `primer1_top`
- Tool: Gowin EDA `V1.9.11.03 Education x64`
- GUI project: `gowin/trinity_primer1.gprj`
- Batch project: run `gw_sh run.tcl` from `primer1/gowin/`

The canonical project keeps all file paths relative. SystemVerilog 2017 is locked
in both `gowin/impl/project_process_config.json` and
`gowin/impl/trinity_primer1_process_config.json`; `run.tcl` also locks
`sysv2017` for batch builds.

## Implemented source scope

The target is self-contained under `primer1/` and implements:

- SPI Mode-0, MSB-first request/response endpoint with CRC16/CCITT-FALSE;
- high-impedance MISO while deselected and active-low level IRQ;
- GET_INFO/GET_STATUS, retained transaction reconciliation and all Primer #1 commands;
- two 256x16 polynomial memories intended for Gowin BSRAM inference;
- iterative ML-KEM-512 NTT, INTT and BaseMul;
- NIST SP 800-232 Ascon-AEAD128 encrypt-only, fixed AD=24 B and plaintext=24 B;
- direct 66-byte UART frame `A5 5A || AD || ciphertext || tag` at 115200 8N1;
- staged/active session state, sequence and fail-closed Tiny safety controls;
- sequential zeroization, heartbeat, fault latch and primitive self-test flow.

No mandatory block is stubbed, bypassed or removed for fitting.

## Resource architecture after exact-synthesis feedback

The first exact-device synthesis parsed and mapped the complete design but failed
with `22693 / 20736` logic. The source is now restructured without changing the
wire protocol or mandatory functions:

- one Montgomery multiplier/reducer is time-shared by NTT, INTT, scaling and BaseMul;
- NTT and INTT share the same two-port BSRAM access datapath;
- BaseMul is decomposed into sequential micro-operations instead of parallel `fqmul` trees;
- request CRC32C fingerprints are accumulated byte-by-byte during the existing SPI parse;
- polynomial coefficient validation and chunk extraction are sequential;
- SPI response payload and UART frame serialization use shift registers instead of wide variable-index muxes;
- Ascon remains one-round iterative; no rounds are unrolled across cycles.

Exact resource fit and timing remain pending a new Gowin run.

## Polynomial interface contract

SPI coefficients are canonical unsigned little-endian values `0..3328`.

- NTT input: standard domain, normal order.
- NTT output: standard-domain residues, upstream bit-reversed order.
- INTT input: standard-domain residues, upstream bit-reversed order.
- INTT output: standard domain, normal order, with `INTT(NTT(a)) = a mod q`.
- BaseMul input/output: standard-domain residues in the same bit-reversed NTT order.

Internally the zeta table is Montgomery encoded. BaseMul and INTT results are
converted at the hardware interface boundary so Montgomery scaling is not
exposed over SPI.

## Current evidence state

- SystemVerilog parse/RTL compilation/top recognition: PASS on the previous exact run.
- Previous resource fit: FAIL (`22693` used vs `20736` available).
- Optimized source static/reference checks: PASS.
- Optimized RTL simulation: NOT EXECUTED in the current environment.
- Optimized exact-device synthesis/place-and-route/timing/bitstream: PENDING RERUN.

## Build and evidence to preserve

Open `gowin/trinity_primer1.gprj`, then run Synthesis and Place & Route. Preserve:

1. complete synthesis log and hierarchy/resource report;
2. place-and-route log and report;
3. timing report including unconstrained paths;
4. utilization report (LUT, DFF, BSRAM, DSP, PLL);
5. pin report;
6. all warnings/errors and generated `.fs` status.
