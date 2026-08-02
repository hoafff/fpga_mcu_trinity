# Primer #2 verification status

Status date: 2026-08-02

## Portable evidence before the fault-output correction

The earlier source completed the following portable checks:

```text
STATIC RTL CHECK PASS (7 files)
KAT_CT E6896DFDE9C67FB12505040A2B87C401917A1A93C02CAE64
KAT_TAG E85FD9296FE784086CC5665283819E4B
PASS ascon_zero_and_nonzero_decrypt
PASS ad_ciphertext_tag_bit_flip_rejection
PASS wrong_key_and_nonce_rejection
PASS official_count817_sender_compatibility
PASS uart_frame_layout_66_bytes
```

The byte-exact qualified-sender-compatible frame used by the reference check is:

```text
A55A010212341122334400000000000000010018334400000000
0C320E28037E35D1B855C290826D379B13703BA378B2CC30
6571AF37ED854B37A89E92C0D861901A
```

Because the RTL and build contract have since changed, static/reference checks
must be rerun on the current commit before they are recorded as current PASS.

## RTL regression inventory

`primer2/tb/run.py` compiles and runs these self-checking benches when
`iverilog` and `vvp` are installed:

1. `tb_ascon_aead128_decrypt`
2. `tb_uart_rx_byte`
3. `tb_uart_frame_receiver`
4. `tb_spi_packet_endpoint`
5. `tb_primer2_command_core`
6. `tb_bad_tag_threshold`
7. `tb_fault_output`
8. `tb_reset_states`
9. `tb_primer2_top`

The suite covers successful decrypt/read/ACK, retained transaction behavior,
SPI CRC rejection, UART timeout/framing/truncation/sync-in-body behavior,
wrong AD type, sequence zero, replay, stale/forward-gap sequence, tag failure,
three-consecutive-bad-tag fault/zeroize threshold, deterministic `fault_o` on
reset and idle, external fatal, persistence after fatal removal, zeroize while
fault-locked, trusted-reset recovery, result-pending protection, abort/zeroize
during decrypt, secure-enable loss and fatal latch. The reset bench poisons
secret, transaction, diagnostic, quarantine and Ascon state, then verifies
asynchronous reset from all critical lifecycle states returns to a scrubbed,
fail-closed state.

## Exact-device evidence

The user-supplied pre-fix build on Gowin EDA V1.9.11.03 Education completed:

```text
Synthesis:       PASS WITH EX2664 WARNING
Place & Route:   PASS
Timing 27 MHz:   PASS, WNS +18.124 ns, WHS +0.307 ns, TNS 0
Fmax:            52.874 MHz
Bitstream:       GENERATED, SHA-256 not supplied
Hardware test:   NOT RUN
```

Resource usage was Logic 79%, Registers 43%, CLS 86%, PRIMARY 3/8 and LW 8/8.
This evidence is preserved in `EXACT_DEVICE_BUILD_AUDIT_2026-08-02.md`, but it is
superseded by the `fault_o` and clean-build-flow changes.

## Current open gates

```text
Primer #2 reference checks:          RERUN REQUIRED
Primer #2 static RTL checks:         RERUN REQUIRED
Primer #2 nine-bench RTL regression: RERUN REQUIRED
Primer #2 exact-device synthesis:    CLEAN REBUILD REQUIRED
Primer #2 place and route:            CLEAN REBUILD REQUIRED
Primer #2 static timing analysis:     CLEAN REBUILD REQUIRED
Primer #2 bitstream generation:       CLEAN REBUILD REQUIRED
Primer #2 hardware qualification:     PENDING PHYSICAL TEST
```

`hardware_qualified` remains false. The old `.fs` and reports must not be reused
for the corrected source.
