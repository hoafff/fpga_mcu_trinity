# Primer #2 verification status

Status date: 2026-08-03

## Qualification identity

```text
Primer #2 source commit = 7588063e636da225bbe81632efe1060f4c825c37
Primer #2 source title  = test(primer2): enforce single positive-edge clock policy
P1-to-P2 harness commit = 7fcf9171938114f07fb3e21157abbbc77074720c
```

Reports and bitstreams generated before the `fault_o` correction remain
superseded and are not reused as current evidence.

## Portable source checks

Recorded post-fix source results:

```text
PASS ascon_zero_and_nonzero_decrypt
PASS ad_ciphertext_tag_bit_flip_rejection
PASS wrong_key_and_nonce_rejection
PASS official_count817_sender_compatibility
PASS uart_frame_layout_66_bytes
STATIC RTL CHECK PASS (7 files)
```

A current nine-bench Icarus result was not supplied with the hardware evidence,
so that specific qualification item remains separately unclaimed.

## Exact-device build candidate

```text
Gowin EDA:      V1.9.11.03 Education
Part:           GW2A-LV18PG256C8/I7
Device version: C
Top:            primer2_top
Clock:          27.000 MHz
```

Recorded result:

```text
Synthesis:                    PASS
EX2664:                       ABSENT
Place and route:              PASS
Timing at 27 MHz:             PASS
Bitstream generation:         PASS
Power analysis:               COMPLETED
Actual Fmax:                  41.700 MHz
Worst setup slack:            +13.056 ns
Worst hold slack:              +0.425 ns
Setup/Hold violations:         0 / 0
Logic/Register/CLS:            79% / 43% / 86%
PRIMARY/LW:                    3/8 / 8/8
```

Accepted status:

```text
Primer #2 exact-device build candidate: PASS
```

The reported bitstream path is
`primer2/gowin/impl/pnr/trinity_primer2.fs`. Its SHA-256 was not recorded.
`LW = 8/8` remains an accepted routing-capacity risk.

## Primer #2 standalone hardware qualification

The official standalone harness and raw evidence remain under:

```text
primer2/hardware/esp32c3_standalone_qualification/
```

Recorded result:

```text
PASS count = 23
FAIL count = 0
OVERALL    = PASS
```

That run qualified ESP32-C3 SPI control, UART injection, identity, initial
fail-closed state, CRC rejection, retained transaction handling, Ascon decrypt
and tag verification, byte-exact plaintext, session lifecycle, replay and
sequence rejection, pending-result protection, command zeroize, bad-tag fault
threshold and heartbeat continuation.

The deliberate final standalone test ended in expected
`SESSION_FAULT_LOCKED`. External `fatal_latched_i` and `zeroize_ni` pins were not
physically exercised.

## P1 -> P2 direct UART hardware qualification

The direct physical payload connection:

```text
Primer #1 uart_tx_o -> Primer #2 uart_rx_i
```

has now passed on hardware using the dual-SPI ESP32-C3 controller harness.

Evidence:

```text
qualification record =
  primer2/docs/P1_TO_P2_UART_HARDWARE_QUALIFICATION_2026-08-03.md

raw log =
  primer2/hardware/p1_to_p2_uart_integration/evidence/
  serial_monitor_2026-08-03.txt

raw log SHA256 =
  1a682823c17fde2ab4ea4664c1acd7f7123139756988ab30d8f457d254a00597
```

Recorded summary:

```text
PASS count = 11
FAIL count = 0
OVERALL = PASS
P1 -> P2 direct UART integration: PASS
```

The run proved:

- correct P1 and P2 target/build/capability identity;
- initial fail-closed state on both targets;
- retained self-test and transition to `READY_NO_SESSION`;
- byte-identical session stage material;
- commit while secure enable was low;
- both targets reaching `COMMITTED_BLOCKED`, then `ACTIVE`;
- P1 sequence-1 encryption and 66-byte UART transmission;
- P2 sequence-1 authentication/decryption and byte-exact plaintext;
- wrong ACK rejection with `ERR_BAD_SESSION = 0x0402`;
- P1/P2 sequence-2 byte-exact transfer;
- pending-result overwrite protection when sequence 3 arrived;
- `ERR_RESULT_PENDING_DROP = 0x0506`;
- `DIAG_RESULT_PENDING_DROP = 0x00000080`;
- preservation and reread of the original sequence-2 plaintext;
- final active, non-aborted state with both IRQ outputs high and UART idle.

Independent parsing of the full log found 67 complete SPI request/response pairs.
All 134 complete packets passed magic/version, length and CRC checks; all
responses matched their request command and transaction ID.

This direct-link run did not newly qualify SN32 or Tiny. It also did not repeat
the standalone replay, corrupted-tag, command-zeroize or fault-threshold cases.

## Current status matrix

```text
Primer #2 reference checks:                    PASS
Primer #2 static RTL checks:                   PASS
Primer #2 nine-bench RTL regression:           NOT REPORTED FOR THIS COMMIT
Primer #2 exact-device build candidate:        PASS
Primer #2 standalone ESP32-C3 qualification:   PASS
ESP32-C3 SPI control path:                     PASS
ESP32-C3 UART frame injection:                 PASS
Ascon decrypt/authentication on FPGA:          PASS
Session/replay/command-zeroize/fault lifecycle:PASS
external fatal_latched_i pin:                  NOT RUN, STRAPPED LOW
external zeroize_ni pin:                       NOT RUN, STRAPPED HIGH
P1 -> P2 direct UART integration:              PASS
SN32 -> P1/P2 control plane:                   NOT RUN
Tiny safety integration:                       NOT RUN
full-system hardware qualification:            NOT RUN
```

Scoped flags:

```text
standalone_hardware_qualified       = true
p1_to_p2_uart_hardware_qualified    = true
hardware_qualified                  = false
full_system_hardware_qualified      = false
```

The generic/full-system flag remains false because SN32 and Tiny are separate
unrun gates.

## Next gate

The recommended next independent gate is:

```text
SN32 -> P1/P2 dual-SPI control plane
```

It should retain the qualified direct UART payload path and replace only the
ESP32-C3 provisioning/result controller. Tiny safety integration remains a later
separate gate.

See:

- `STANDALONE_HARDWARE_QUALIFICATION_2026-08-03.md`;
- `P1_TO_P2_UART_INTEGRATION_NEXT_GATE.md`;
- `P1_TO_P2_UART_HARDWARE_QUALIFICATION_2026-08-03.md`;
- `../hardware/esp32c3_standalone_qualification/README.md`.
