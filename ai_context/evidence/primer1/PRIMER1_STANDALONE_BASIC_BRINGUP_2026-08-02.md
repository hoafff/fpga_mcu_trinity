# Primer #1 standalone basic hardware bring-up — 2026-08-02

## Scope and identity

- Repository commit used for bitstream: `927aa99e2e2ee732f95686fde165e9755e31f43a`.
- FPGA: Kiwi Primer 20K, exact part `GW2A-LV18PG256C8/I7`, device version C.
- Bitstream: `primer1/gowin/impl/pnr/trinity_primer1.fs`.
- Programming method: Gowin Programmer, JTAG, `SRAM Program`.

## Safety inputs during standalone test

Tiny 1P5, Primer #2 and SN32 were not connected. The inputs were fixed as:

```text
fatal_latched_i  R12/J2-13 -> GND/J2-14 = 0
secure_enable_i  T12/J2-15 -> GND/J2-14 = 0
zeroize_ni       R11/J2-16 -> 3V3/J2-17 = 1
```

`rst_ni` and `spi_cs_ni` used their current pull-ups.

## Measurement setup

An ESP32-C3 Super Mini was used only as a digital monitor. The two boards used
separate power sources and shared GND; no 5 V or 3.3 V rails were tied together.

```text
Primer T11/J2-18 heartbeat_o -> ESP32 GPIO4
Primer T13/J2-12 fault_o     -> ESP32 GPIO5
Primer T14/J2-10 irq_no      -> ESP32 GPIO6
Primer R13/J2-11 uart_tx_o   -> ESP32 GPIO7
```

The monitor counted both heartbeat edges and sampled fault/IRQ/UART once per
second. Open, unconnected GPIO measurements were noisy and were discarded.

## Observed stable result

After correct connection and ESP32 reset, repeated samples were:

```text
heartbeat frequency: approximately 5.0 Hz
fault_o:              0
irq_no:               1
uart_tx_o:            1
```

The first 0.0 Hz line immediately after ESP32 startup is not used. Repeated
5.0 Hz edge-count results are the heartbeat evidence; the sampled heartbeat bit
can repeatedly show the same value because the one-second sample interval equals
five complete heartbeat periods.

## Accepted status

```text
JTAG SRAM PROGRAM:             PASS
BITSTREAM EXECUTION:           PASS
27 MHz CLOCK PATH:             operational for heartbeat execution
HEARTBEAT:                     PASS, approximately 5.0 Hz
FAULT OUTPUT:                  PASS, fault_o=0
IRQ OUTPUT IDLE:               PASS, irq_no=1
UART TX IDLE:                  PASS, uart_tx_o=1
```

**Primer #1 standalone basic hardware bring-up: PASS.**

## Explicitly not proven

This evidence does not prove SN32/P1 SPI communication, SPI framing, GET_INFO,
GET_STATUS, RUN_SELF_TEST, retained transaction operations, NTT, INTT, BaseMul,
Ascon encryption, P1-to-P2 UART frames, session stage/commit, Tiny-driven
secure-enable, zeroize behavior or full-system hardware operation.

`HARDWARE_QUALIFIED` remains false.
