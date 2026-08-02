# Primer #1 ESP32-C3 hardware tests

This directory preserves the exact uploaded ESP32-C3 source package used to
qualify the Primer #1 source tree at commit
`c8135b5304c0318c7ec24787484dc8a4c4aa0278`. The archive is stored as
`primer1_hardware_test_evidence.zip`; extract it before use. The accepted run
used the exact-device bitstream identified in `../evidence/ARTIFACT_MANIFEST.md`.

## Archive contents

Extract with:

```text
unzip primer1_hardware_test_evidence.zip
```

| File | Purpose |
|---|---|
| `01_primer1_standalone_monitor.ino` | Observe heartbeat, fault, IRQ and UART-idle outputs without SPI traffic. |
| `02_spi_get_info_status_debug_snapshot.cpp` | Minimal GET_INFO/GET_STATUS transport and CRC bring-up. Rename to `.ino` when using the Arduino IDE as a single-file sketch. |
| `03_self_test_stage.md` | Retained RUN_SELF_TEST command sequence and expected result. |
| `04_primer1_remaining_tests_esp32c3.ino` | Comprehensive session, ABORT_SESSION, Ascon/UART and ZEROIZE test. |

The comprehensive sketch contains the software model used for byte-exact
comparison with the current RTL Ascon implementation. It is a model of this RTL
revision, not an independent implementation conformance claim beyond the tested
frame.

## Required equipment

- Gowin Primer #1 board with `GW2A-LV18PG256C8/I7`.
- ESP32-C3 Mini or compatible 3.3 V controller.
- Common ground between both boards.
- Gowin Programmer for SRAM Program.
- Arduino/ESP32 environment with `Arduino.h` and `SPI.h`.

All logic signals are 3.3 V. Do not connect a 5 V UART or GPIO signal directly.

## Wiring

### SPI and monitor signals

| ESP32-C3 | Primer package pin | Primer signal | Direction relative to ESP32 |
|---|---|---|---|
| GPIO0 | P16 | `spi_sck_i` | output |
| GPIO1 | P15 | `spi_mosi_i` | output |
| GPIO3 | T15 | `spi_miso_o` | input |
| GPIO10 | R14 | `spi_cs_ni` | output |
| GPIO4 | T11 | `heartbeat_o` | input |
| GPIO5 | T13 | `fault_o` | input |
| GPIO6 | T14 | `irq_no` | input |
| GPIO7 | R13 | `uart_tx_o` | UART RX input |
| GND | GND | common ground | — |

`GPIO10` must connect to **R14**. T14 is `irq_no`; a historical R14/T14 wiring
mistake produced failed bring-up attempts and is not an RTL failure.

### Safety and control straps

For standalone monitoring and the minimal SPI sketch:

```text
Primer R12 / fatal_latched_i  -> GND
Primer R11 / zeroize_ni       -> 3V3
Primer T12 / secure_enable_i  -> GND
```

For `04_primer1_remaining_tests_esp32c3.ino`:

```text
Primer R12 / fatal_latched_i  -> GND
Primer R11 / zeroize_ni       -> 3V3
Primer T12 / secure_enable_i  -> ESP32-C3 GPIO20
```

Never connect T12 to GND and GPIO20 simultaneously. The comprehensive sketch
keeps GPIO20 LOW during STAGE/COMMIT and drives it HIGH only after commit.

## Load the exact-device bitstream

1. Check out commit `c8135b5304c0318c7ec24787484dc8a4c4aa0278` or the later evidence-only commit that references it.
2. Open `primer1/gowin/trinity_primer1.gprj` in Gowin EDA V1.9.11.03 Education.
3. Confirm `GW2A-LV18PG256C8/I7`, database `GW2A-18C / gw2a18c-011`, and the 27 MHz constraint.
4. Use the newly generated `primer1/gowin/impl/pnr/trinity_primer1.fs` whose SHA-256 is recorded in `../evidence/ARTIFACT_MANIFEST.md`.
5. In Gowin Programmer select **SRAM Program** and program Primer #1.
6. SRAM configuration is volatile; repeat programming after a Primer power cycle.

The generated `.fs` remains ignored by repository policy. The manifest records
its exact size, SHA-256, header checksum, tool, device and creation timestamp.

## Power, reset and test order

1. Disconnect power while changing wiring.
2. Connect the common ground and all required 3.3 V signals.
3. Set `fatal_latched_i=0`, `zeroize_ni=1` and `secure_enable_i=0` before reset/configuration.
4. Power the Primer and ESP32-C3.
5. SRAM-program the Primer bitstream.
6. Reset the Primer or reprogram it before each clean acceptance run.
7. Reset/start the ESP32 sketch only after the Primer has completed startup scrub.
8. If IRQ is already LOW, the comprehensive sketch flushes one stale response mailbox before starting.
9. Run the programs in order: standalone monitor, minimal SPI snapshot, then comprehensive test.

## Expected results

### Standalone monitor

```text
heartbeat_o: approximately 5.0 Hz
fault_o:      0
irq_no:       1 while idle
uart_tx_o:    1 while idle
```

### Minimal SPI snapshot

GET_INFO must return:

```text
target_id        = 1
protocol_version = 1
capabilities     = 0x000011FF
build_id         = 0x50310001
reserved         = 0
```

GET_STATUS must pass response framing and CRC validation.

### Comprehensive sketch

The accepted run must end with:

```text
GET_INFO                    : PASS
INITIAL GET_STATUS          : PASS
SELF_TEST READY             : PASS
STAGE/ABORT ID VALIDATION   : PASS
COMMIT + SECURE_ENABLE      : PASS
ASCON + UART BYTE-EXACT     : PASS
ZEROIZE BAD SCOPE REJECT    : PASS
ZEROIZE_ALL                 : PASS
FINAL GET_STATUS            : PASS
OVERALL RESULT              : PASS
```

The UART frame must contain exactly 66 bytes, begin with `A5 5A`, and match the
software-model frame byte-for-byte.

## Interpreting sticky history

`last_error` and `diagnostic_summary` are sticky history, not live-fault bits.
The accepted run intentionally produces `ERR_BAD_SESSION` (`0x0402`) and
`ERR_ZEROIZED` (`0x0403`). Earlier empty or malformed CS transactions produced
`last_error=0x0103` and `diagnostic_summary=0x00000001`. Do not modify RTL merely
to erase this history. Qualification requires `fault_o=0` and the expected
transaction/state outcomes.

## Scope limits

This hardware suite does not independently qualify:

- external non-zero `POLY_BEGIN` / `POLY_WRITE_CHUNK` / `POLY_EXECUTE` /
  `POLY_READ_CHUNK` vectors over SPI;
- GET_STATUS/GET_TXN_RESULT arrival while the core is actively busy;
- POLY_BEGIN rejection during `OP_RESULT_READY` before result retirement.

Those behaviors remain covered by the committed RTL simulation suite. Hardware
evidence supplements that suite; it does not replace regression simulation.
