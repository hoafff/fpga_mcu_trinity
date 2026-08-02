# Primer #2 verification status

Status date: 2026-08-03

## Qualification identity

```text
source_commit = 7588063e636da225bbe81632efe1060f4c825c37
source_title  = test(primer2): enforce single positive-edge clock policy
```

The reports and bitstream generated before the `fault_o` correction are
superseded. Their historical audit remains in
`EXACT_DEVICE_BUILD_AUDIT_2026-08-02.md` and is not used as current evidence.

## Current portable source checks

The following were run on the post-fix source:

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

Current nine-bench Icarus evidence was not supplied with this qualification
record, so RTL simulation remains separately unclaimed.

## Current exact-device clean build

Environment:

```text
Gowin EDA:      V1.9.11.03 Education
Part:           GW2A-LV18PG256C8/I7
Device version: C
Top:            primer2_top
Clock:          27.000 MHz
```

Result:

```text
Primer #2 exact-device synthesis:      PASS
EX2664:                                ABSENT
Primer #2 Place & Route:               PASS
Primer #2 timing 27 MHz:               PASS
Primer #2 bitstream generation:        PASS
Primer #2 power analysis:              COMPLETED
```

Timing:

```text
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

The accepted build status is:

```text
Primer #2 exact-device build candidate: PASS
```

The reported bitstream path is:

```text
primer2/gowin/impl/pnr/trinity_primer2.fs
```

No bitstream SHA-256 was supplied. The build is therefore not cryptographically
bound to the source commit in this record.

`LW = 8/8` remains an accepted routing-capacity risk. The clean build has no
reported unrouted nets, one clock domain and positive timing margin. No global
promotion setting is disabled merely to reduce the utilization figure.

## ESP32-C3 standalone hardware qualification

The official harness and preserved raw log are under:

```text
primer2/hardware/esp32c3_standalone_qualification/
```

Recorded summary:

```text
PASS count = 23
FAIL count = 0
OVERALL    = PASS
```

The run qualified the physical Primer #2 board for:

- ESP32-C3 SPI control and response-mailbox handling;
- ESP32-C3 66-byte UART frame injection;
- target/build identification and initial fail-closed state;
- SPI CRC rejection and retained transaction reconciliation;
- Ascon self-test, decrypt, tag verification and byte-exact plaintext;
- stage, abort, commit, activate and re-provision lifecycle;
- replay, wrong-session, zero-sequence and forward-gap rejection;
- authenticated-result overwrite protection;
- command `ZEROIZE_ALL`;
- three-bad-tag fault threshold, session/key zeroize and heartbeat continuation.

The final deliberate destructive test ended at:

```text
session_state      = 8
fault_o            = 1
last_error         = 0x0601
diagnostic_summary = 0x000001B0
session_id         = 0
```

This is the expected PASS state for `SESSION_FAULT_LOCKED` after the third bad
tag.

The first attempt exposed a startup mailbox caused by CS/SCK activity while the
ESP32 was booting. The official harness now drives `spi_cs_ni` high before Serial
and SPI initialization, drains any stale mailbox when `irq_no` is already low,
and keeps the UART GPIO high impedance until `GET_INFO` proves target 2.

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
P1 -> P2 direct UART integration:              NOT RUN
SN32 -> P2 control plane:                      NOT RUN
Tiny safety integration:                       NOT RUN
full-system hardware qualification:            NOT RUN
```

The physical active-low zeroize pin was not exercised; command `ZEROIZE_ALL` is
a separate tested path. The physical fatal input was not asserted. The ESP32
fixture leaves secure enable high during the final fault state, so Tiny behavior
is not inferred from this standalone run.

`standalone_hardware_qualified` may be true for the recorded ESP32-C3 scope.
The generic/full-system `hardware_qualified` flag must remain false.

See:

- `STANDALONE_HARDWARE_QUALIFICATION_2026-08-03.md`;
- `P1_TO_P2_UART_INTEGRATION_NEXT_GATE.md`;
- `../hardware/esp32c3_standalone_qualification/README.md`.
