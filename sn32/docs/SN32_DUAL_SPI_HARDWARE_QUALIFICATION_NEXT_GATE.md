# SN32 -> P1/P2 dual-SPI hardware qualification — next gate

## Scope

This gate qualifies only the SN32F407 controller path to Primer #1 and Primer #2
over one shared SPI bus with independent CS and IRQ lines.

The permitted statement, only after every acceptance item passes, is:

```text
SN32 -> P1/P2 DUAL-SPI CONTROL PLANE HARDWARE: PASS
```

It does not qualify session activation, direct P1-to-P2 UART telemetry, Tiny,
live-session ML-KEM or the full system.

## Locked hardware evidence through v0.7.10

The following facts are proven:

1. Startup GET_INFO request `txid=0x0001` is byte-exact and CRC-valid.
2. P1 accepts it and retains the correct 22-byte GET_INFO response while IRQ is active.
3. A later manual diagnostic recovers the exact old response with valid CRC.
4. Startup warmup, response delay, FRESET sequencing, a ten-byte mailbox prime,
   and selecting `NEW_TH_EN=1` did not eliminate the malformed first header.
5. Two v0.7.10 cold boots produced:

```text
f9 07 00 00 00 01 00 0c
1c 08 00 00 00 01 00 0c
```

The final four header bytes are stable and correct while the first four bytes are
not. The evidence is insufficient to choose another FIFO packing, byte-lane, or
polling change. No further transport behavior may be changed without direct
register-level evidence.

## Required diagnostic image

```text
architecture_version = 0.7.11
sn32_build_id         = 0x0007000B
```

The v0.7.11 image deliberately retains the v0.7.10 transport behavior and adds
measurement only. For the first eight response bytes it records:

```text
SPI CTRL0
SPI CTRL1
SPI CLKDIV
SPI FIFO_TH
STAT immediately before each DATA read
full 32-bit DATA register value
STAT immediately after each DATA read
```

This distinguishes among:

```text
correct byte present in another DATA lane
stale DATA register value despite RX-ready status
RX FIFO not popping after DATA read
unexpected CTRL/FIFO configuration at runtime
incorrect interpretation of STAT bits
```

## Locked transport profile

```text
SPI frequency                = 100000 Hz
SPI mode                     = 0
bit order                    = MSB first
word length                  = 8 bits
SPI0 CLKDIV                  = 59
FIFO_TH                      = 0x80000000 retained for measurement
CS guard                     = 10 us nominal
startup warmup               = 2000 ms
response settle              = 15 ms
response capture             = exact declared frame length
header + remainder           = one continuous CS
mailbox retry                = two reads, no reissued request
startup mailbox prime        = removed
```

## Exact rebuild and image verification

```bat
git pull origin main
git submodule update --init --recursive
git rev-parse HEAD
```

Rebuild:

```text
sn32/keil/trinity_sn32f407_deploy.uvprojx
```

Accept only:

```text
0 Error(s), 0 Warning(s)
Flash fit: PASS
RAM fit: PASS
AXF generation: PASS
HEX generation: PASS
```

Flash and Verify through SN-LINK. Do not reuse any v0.7.10 HEX.

Required local identity:

```text
protocol_version=1
architecture_version=0.7.11
sn32_build_id=0x0007000B
```

`system-info` remains local and side-effect free. Endpoint build IDs may be zero
when startup discovery fails.

## Mandatory v0.7.11 measurement run

1. Power off SN32.
2. Reset or reconfigure P1 and P2 to clear pending mailboxes.
3. Keep common ground connected.
4. Power or reset SN32 last with the v0.7.11 image.
5. Wait at least 3 seconds.

Run only:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 system-info
trinity-host --port COM3 spi-first-failure
```

When a failure is present, the final command must print these additional fields:

```text
spi_ctrl0
spi_ctrl1
spi_clkdiv
spi_fifo_th
response_sample_count
response_status_before_read
response_data_words
response_status_after_read
```

Do not run `spi-diag`, `system-status`, or `dual-spi-bringup` until the telemetry
has been audited. The pending P1 mailbox must remain intact for correlation.

## Decision rules after telemetry

```text
Upper DATA lane contains A5/01/01/01:
    Correct byte-lane extraction using measured DATA layout.

DATA words themselves contain the same malformed low bytes:
    Inspect RX FIFO readiness/pop semantics and STAT bit definitions.

STAT does not change across DATA reads:
    Investigate FIFO pop behavior or register access width.

FIFO_TH readback is not 0x80000000:
    Investigate configuration write/readback and register definition.

CTRL0/CTRL1/CLKDIV differ from the locked profile:
    Fix runtime configuration before any protocol change.
```

## Acceptance criteria

```text
v0.7.11 exact Keil rebuild:                       PASS
v0.7.11 SN-LINK program/verify:                   PASS
v0.7.11 local identity readback:                  PASS
v0.7.11 standalone PC UART PING:                  PASS
register telemetry fields present:                PASS
first eight raw DATA words captured:              PASS
STAT before/after each DATA read captured:         PASS
runtime CTRL0/CTRL1/CLKDIV/FIFO_TH captured:       PASS
root cause selected from measured evidence:        PENDING
P1/P2 raw diagnostics:                             BLOCKED
SN32 dual-SPI hardware qualification:              BLOCKED
```

## Explicit non-claims

```text
session stage/commit hardware:            PENDING
direct UART under SN32 orchestration:      PENDING
authenticated telemetry result via SN32:   PENDING
ML-KEM live-session hardware:              PENDING
Tiny safety integration:                   PENDING
full-system qualification:                 PENDING
hardware_qualified:                        false
full_system_hardware_qualified:            false
```
