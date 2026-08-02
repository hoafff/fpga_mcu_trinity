# Primer #2 ESP32-C3 standalone qualification harness

This fixture qualifies Primer #2 without claiming P1, SN32, Tiny or full-system
integration. The ESP32-C3 Mini acts as:

- SPI Mode-0 master for the Primer #2 control plane;
- 115200 8N1 UART transmitter emulating Primer #1;
- `secure_enable_i` source emulating only the enable level from Tiny;
- monitor for heartbeat, fault and active-low IRQ.

The qualification sketch is:

```text
Primer2StandaloneQualification.ino
```

The exact ESP32 Arduino core/board-package version used for the recorded run was
not supplied. Preserve that information in future evidence captures.

## Required wiring

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

All driven signals must be 3.3 V compatible. Do not connect the ESP32 output to
a net that is simultaneously driven by Primer #1 or Tiny.

## Mandatory startup behavior

`spi_cs_ni` must not float or pulse low while the configured FPGA is alive.
The sketch therefore performs this sequence before the serial startup delay:

```text
pinMode(CS_N, OUTPUT)
digitalWrite(CS_N, HIGH)
secure_enable_i = LOW
UART injection pin = INPUT
```

Only afterwards does it initialize Serial and SPI.

If `irq_no` is already low, the fixture clocks the maximum response length and
drains the stale startup mailbox before sending `GET_INFO`. A recorded startup
mailbox contained an `ERR_BAD_LENGTH` response with command and transaction ID
zero, consistent with unintended CS/SCK activity during controller boot.

GPIO7 remains high impedance until `GET_INFO` proves:

```text
target_id = 2
protocol  = 1
build_id  = 0x50320001
```

This prevents output contention if the connected FPGA is not the expected
Primer #2 image.

## Test sequence

The harness checks:

1. heartbeat and initial fault level;
2. `GET_INFO`, initial fail-closed state and pre-authentication read rejection;
3. SPI CRC error handling;
4. retained self-test transaction;
5. stage/abort and stage/commit/activate lifecycle;
6. valid 66-byte UART frames with byte-exact plaintext readback;
7. wrong ACK, replay, wrong-session, sequence-zero and forward-gap rejection;
8. authenticated-result overwrite protection;
9. command `ZEROIZE_ALL` and re-provisioning;
10. three consecutive bad tags causing fault latch and zeroize;
11. heartbeat continuation in `SESSION_FAULT_LOCKED`.

The final bad-tag test is deliberately destructive. A successful run ends in
`SESSION_FAULT_LOCKED`; reprogram SRAM or reset the FPGA before repeating it.

## Recorded result

The 2026-08-03 evidence for source commit
`7588063e636da225bbe81632efe1060f4c825c37` reported:

```text
PASS count = 23
FAIL count = 0
OVERALL    = PASS
```

Harness source SHA-256 before repository insertion:

```text
e1c8c49cb22f4e2813c8f39f92449841705ad062aa5d5be0d587584415084dea
```

Serial log SHA-256 before repository insertion:

```text
795175484c4845fe629354fa668b5a772a099dbe0b345483064d218579406faa
```

See `../../docs/STANDALONE_HARDWARE_QUALIFICATION_2026-08-03.md` for the
qualification boundary.

## Scope exclusions

The fixture does not qualify:

- direct Primer #1 `uart_tx_o` to Primer #2 `uart_rx_i` operation;
- SN32 control-plane operation;
- Tiny fault/zeroize/secure-enable behavior;
- physical assertion of `fatal_latched_i`;
- physical pulsing of `zeroize_ni`;
- full-system operation.

Command-driven `ZEROIZE_ALL` is exercised, but that is distinct from testing the
external active-low zeroize pin.
