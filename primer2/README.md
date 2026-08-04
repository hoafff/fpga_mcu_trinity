# Primer #2 deployment target

Primer #2 is the authenticated telemetry receiver and the second endpoint on the
SN32 shared-SPI control plane.

## Corrected source baseline

The current source implements the corrective SPI contract in:

```text
ai_context/interfaces/SPI_CONTROL_PLANE_ICD_v0.2.md
```

Current build identity:

```text
Primer #2 build ID = 0x50320002
```

The correction keeps the physical interface unchanged:

```text
shared SCK/MOSI/MISO
independent P2 CS_N
independent P2 IRQ_N
P1 uart_tx_o -> P2 uart_rx_i direct payload path
```

Behavioral corrections:

- `IRQ_N` is LOW only while a complete response mailbox is ready to read;
- retained side-effect and authenticated-result state remains visible through
  status/query commands but does not hold IRQ LOW;
- `GET_TXN_RESULT`, `RETIRE_TXN_RESULT`, `READ_AUTH_RESULT` and
  `ACK_AUTH_RESULT` remain issuable after the preceding mailbox is consumed;
- CS windows that do not begin with SPI magic `0xA5` are discarded silently;
- malformed requests that have already qualified with magic still return the
  normal protocol errors;
- deselected MISO remains high-impedance with `PULL_MODE=NONE` explicit in the
  Gowin constraints.

## Source verification

The corrected source passes:

```text
portable reference checks
static RTL checks
Ascon decrypt KAT and negative tests
UART byte and frame receiver tests
SPI request/response endpoint tests
silent non-magic CS-window test
retained transaction tests
session lifecycle tests
authenticated-result read/ACK tests
replay, stale-sequence and bad-tag tests
three-bad-tag fault/zeroize test
reset/fault/top-level integration tests
```

Evidence:

```text
primer2/docs/RTL_SIMULATION_LATEST.md
primer2/docs/TESTBENCH_PORTABILITY_MIGRATION_LATEST.md
```

## Exact-device and hardware boundary

The previous exact-device and ESP32-C3 standalone results belong to the older
programmed image. They remain useful historical evidence but do not qualify the
corrected `0x50320002` image.

Current state:

```text
corrected RTL/source regression: PASS
corrected Gowin synthesis/P&R/STA: NOT RUN
corrected .fs generated:           NOT RUN
corrected bitstream SHA-256:        NOT RECORDED
corrected image programmed:         NOT RUN
corrected SN32 shared-SPI gate:     NOT RUN
full-system hardware qualified:     false
```

## Next required gate

1. Build the current Primer #2 project in Gowin for the exact device.
2. Require synthesis, place-and-route and STA PASS.
3. Record utilization, timing and the generated `.fs` SHA-256.
4. Program the board and confirm `GET_INFO` reports `0x50320002`.
5. Run the corrected SN32 shared-SPI qualification with P1 build `0x5031D003`
   and SN32 v0.7.25 / `0x00070019`.
6. Only after that PASS, rerun the direct UART/session/authenticated-result gate.

No corrected-image hardware PASS is claimed by this README.
