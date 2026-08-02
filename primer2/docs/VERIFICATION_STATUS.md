# Primer #2 verification status

Status date: 2026-08-02

## Evidence completed

The portable checks completed with the following result:

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

## RTL regression inventory

`primer2/tb/run.py` compiles and runs these self-checking benches when
`iverilog` and `vvp` are installed:

1. `tb_ascon_aead128_decrypt`
2. `tb_uart_rx_byte`
3. `tb_uart_frame_receiver`
4. `tb_spi_packet_endpoint`
5. `tb_primer2_command_core`
6. `tb_primer2_top`

The suite covers successful decrypt/read/ACK, retained transaction behavior,
SPI CRC rejection, UART timeout/framing/truncation/sync-in-body behavior,
wrong AD type, sequence zero, replay, stale/forward-gap sequence, tag failure,
result-pending protection, abort/zeroize during decrypt, secure-enable loss,
fatal latch, and reset/fail-closed behavior. It also checks that the Ascon
working registers are scrubbed after the authenticated result has been copied
to the retained result buffer.

## Open gates

The current execution environment does not contain `iverilog`, `vvp`, or Gowin
EDA. Therefore these gates remain OPEN and must not be reported as PASS:

```text
Primer #2 RTL simulation regression: NOT RUN
Primer #2 exact-device synthesis:     NOT RUN
Primer #2 place and route:             NOT RUN
Primer #2 static timing analysis:      NOT RUN
Primer #2 bitstream generation:        NOT RUN
Primer #2 hardware qualification:      PENDING PHYSICAL TEST
```

Consequently utilization, WNS, TNS and bitstream SHA-256 are not available.
