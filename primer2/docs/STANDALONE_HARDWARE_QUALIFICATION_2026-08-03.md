# Primer #2 post-fix exact-device and standalone qualification — 2026-08-03

## Evidence identity

The evidence in this record applies to:

```text
source_commit = 7588063e636da225bbe81632efe1060f4c825c37
source_title  = test(primer2): enforce single positive-edge clock policy
```

The reports and bitstream generated at 22:58 before the `fault_o` correction are
superseded and are not accepted as final evidence for this record.

The post-fix bitstream was reported at:

```text
primer2/gowin/impl/pnr/trinity_primer2.fs
```

A SHA-256 for that `.fs` was not supplied. The build and physical run are
therefore tied to the stated source commit by the operator's evidence, but the
bitstream is not cryptographically bound to the commit in this record.

## Portable source checks

The operator ran the following on the post-fix source:

```text
py -3 primer2/scripts/reference_checks.py
py -3 primer2/scripts/static_rtl_checks.py
```

Recorded results:

```text
PASS ascon_zero_and_nonzero_decrypt
PASS ad_ciphertext_tag_bit_flip_rejection
PASS wrong_key_and_nonce_rejection
PASS official_count817_sender_compatibility
PASS uart_frame_layout_66_bytes
STATIC RTL CHECK PASS (7 files)
```

No current nine-bench Icarus result was supplied with this evidence. The source
checks above are PASS; RTL simulation status remains separately tracked.

## Post-fix exact-device clean rebuild

Environment:

```text
Gowin EDA:      V1.9.11.03 Education
Part:           GW2A-LV18PG256C8/I7
Device version: C
Top:            primer2_top
Clock:          27.000 MHz
```

Recorded result:

```text
Synthesis:              PASS
EX2664:                 ABSENT
Place & Route:          PASS
Routing:                COMPLETED
Timing analysis:        PASS
Bitstream generation:   PASS
Power analysis:         COMPLETED
```

Timing:

```text
Constraint:                27.000 MHz
Actual Fmax:               41.700 MHz
Worst setup slack:         +13.056 ns
Worst hold slack:          +0.425 ns
Setup violated endpoints:  0
Hold violated endpoints:   0
Setup TNS:                 0.000 ns
Hold TNS:                  0.000 ns
```

Resources:

```text
Logic:       16,191 / 20,736 = 79%
Registers:    6,889 / 16,173 = 43%
CLS:          8,842 / 10,368 = 86%
Latches:                         0
PRIMARY:                     3 / 8
LW:                          8 / 8
```

The corrected source is therefore accepted as:

```text
Primer #2 exact-device build candidate: PASS
```

`LW = 8/8` remains a routing-capacity risk. It is not treated as a functional
failure because the clean build has no reported unrouted nets, only one clock
domain, no violated timing endpoints and positive setup/hold margin. Global
promotion must not be disabled merely to reduce this utilization number.

## Standalone hardware fixture

Primer #2 was programmed in SRAM with the reported post-fix bitstream. An
ESP32-C3 Mini provided the SPI control plane, injected the 66-byte UART payload,
and emulated `secure_enable_i`.

Wiring used:

| ESP32-C3 | Primer #2 | Direction |
|---|---|---|
| GPIO0 | P16 `spi_sck_i` | ESP32 to P2 |
| GPIO1 | P15 `spi_mosi_i` | ESP32 to P2 |
| GPIO3 | T15 `spi_miso_o` | P2 to ESP32 |
| GPIO10 | R14 `spi_cs_ni` | ESP32 to P2 |
| GPIO4 | T11 `heartbeat_o` | P2 to ESP32 |
| GPIO5 | T13 `fault_o` | P2 to ESP32 |
| GPIO6 | T14 `irq_no` | P2 to ESP32 |
| GPIO7 | R13 `uart_rx_i` | ESP32 UART TX to P2 |
| GPIO20 | T12 `secure_enable_i` | ESP32 to P2 |
| GND | R12 `fatal_latched_i` | fixed low |
| 3V3 | R11 `zeroize_ni` | fixed high |
| GND | GND | common ground |

The official harness is stored under:

```text
primer2/hardware/esp32c3_standalone_qualification/
```

## Startup mailbox finding

The first hardware attempt observed `irq_no` low at startup and a pending SPI
error response:

```text
ERR_BAD_LENGTH
command = 0
transaction_id = 0
```

This is consistent with CS/SCK activity or an insufficiently early high level on
`spi_cs_ni` while the ESP32-C3 was booting. It is not accepted as a normal clean
protocol transaction.

The harness correction is mandatory:

1. configure the CS GPIO as an output and drive `spi_cs_ni` high before the
   USB-serial startup delay and before `SPI.begin()`;
2. if `irq_no` is already low, clock and drain the stale response mailbox before
   issuing `GET_INFO`;
3. keep the UART-injection GPIO high impedance until `GET_INFO` proves
   `target_id == 2`.

The recorded run drained the startup mailbox successfully before beginning the
qualification sequence.

## Standalone result

Final harness summary:

```text
PASS count = 23
FAIL count = 0
OVERALL    = PASS
```

The run demonstrated on the physical Primer #2 board:

- heartbeat operation and initial `fault_o = 0`;
- correct target ID, protocol version, capabilities and build ID;
- SPI CRC rejection and initial fail-closed state;
- no plaintext read before authentication;
- Ascon self-test and retained transaction reconciliation;
- stage, wrong-session abort rejection and correct abort;
- commit while blocked and activation by `secure_enable_i`;
- byte-exact 66-byte UART receive and valid sequence 1/2/3 decryption;
- byte-exact 24-byte plaintext readback;
- wrong ACK rejection and correct ACK;
- replay, wrong-session, sequence-zero and forward-gap rejection;
- authenticated-result overwrite protection;
- `ZEROIZE_ALL`, retained zeroize result and successful re-provisioning;
- bad tag one and two without fault;
- third consecutive bad tag causing fault latch and secret/session zeroize;
- heartbeat continuing while `SESSION_FAULT_LOCKED`.

The deliberate destructive final test ended at:

```text
session_state      = 8       # SESSION_FAULT_LOCKED
fault_o            = 1
last_error         = 0x0601  # ERR_AUTH_THRESHOLD
diagnostic_summary = 0x000001B0
session_id         = 0
```

This is the expected PASS end state after the third consecutive bad tag.

## Qualification boundary

Accepted:

```text
Primer #2 exact-device build candidate:          PASS
Primer #2 standalone hardware qualification:    PASS
ESP32-C3 SPI control path:                       PASS
ESP32-C3 UART frame injection:                   PASS
Ascon decrypt/authentication on FPGA:            PASS
Session/replay/command-zeroize/fault lifecycle:  PASS
```

The standalone PASS is limited to the exercised fixture. The command-driven
`ZEROIZE_ALL` path was tested, but the physical `zeroize_ni` pin was not pulsed.
The physical `fatal_latched_i` pin was not asserted. They remained strapped high
and low respectively.

The final harness leaves `secure_enable_i` high while P2 remains fail-closed due
to its internal fault latch. This does not qualify Tiny behavior; an integrated
Tiny test must prove that Tiny removes secure enable and asserts the required
safety response.

Not accepted by this evidence:

```text
P1 -> P2 direct UART integration:    NOT RUN
SN32 -> P2 control plane:            NOT RUN
Tiny safety integration:             NOT RUN
external fatal_latched_i pin test:    NOT RUN
external zeroize_ni pin test:         NOT RUN
full-system hardware qualification:  NOT RUN
```

Accordingly, standalone qualification is recorded separately and the repository
must not set a generic full-system `hardware_qualified = true` flag.
