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

## Locked hardware evidence through v0.7.9

The following facts are proven:

1. Startup GET_INFO request `txid=0x0001` is byte-exact and CRC-valid.
2. P1 accepts it and commits the correct 22-byte GET_INFO response.
3. P1 keeps IRQ active until the complete response is consumed.
4. A later manual diagnostic can recover the exact old response with valid CRC:

```text
a5 01 01 01 00 01 00 0c
01 01 00 00 11 ff 50 31 00 01 00 00 d2 6c
```

5. P1/P2 raw transactions work after the first malformed capture.
6. Startup warmup, response delay, FRESET sequencing and a bounded ten-byte
   mailbox-prime workaround did not eliminate the first malformed header.
7. Two v0.7.9 cold boots produced:

```text
2c 08 00 00 00 00 00 06
2c 08 00 00 00 01 00 0c
```

The trailing transaction and payload-length bytes are already correct while the
prefix remains stale. This is consistent with byte traffic being packed through
the reset-default 8 x 16-bit FIFO organization.

## Required corrective image

```text
architecture_version = 0.7.10
sn32_build_id         = 0x0007000A
```

The v0.7.10 change is deliberately narrow:

```text
FIFO_TH.NEW_TH_EN = 1
SPI FIFO organization = 16 x 8-bit
remove disproven startup mailbox prime
retain two fresh-CS reads of the same pending mailbox
retain SPIEN-on FRESET self-clear sequence
```

The protocol remains byte-oriented with `DL=7`; every DATA register access must
represent one 8-bit frame.

## Locked transport profile

```text
SPI frequency                = 100000 Hz
SPI mode                     = 0
bit order                    = MSB first
word length                  = 8 bits
SPI0 CLKDIV                  = 59
FIFO organization            = 16 x 8-bit (NEW_TH_EN=1)
CS guard                     = 10 us nominal
startup warmup               = 2000 ms
response settle              = 15 ms
response capture             = exact declared frame length
header + remainder           = one continuous CS
mailbox retry                = two reads, no reissued request
```

## Wiring preflight

Make wiring changes only while all boards are powered off.

```text
SN32 P1.0 SPI0_SCK   -> P1 P16 and P2 P16
SN32 P1.2 SPI0_MOSI  -> P1 P15 and P2 P15
SN32 P1.1 SPI0_MISO  <- P1 T15 and P2 T15
SN32 P2.1 P1_CS_N    -> P1 R14
SN32 P2.2 P2_CS_N    -> P2 R14
SN32 P2.3 P1_IRQ_N   <- P1 T14
SN32 P2.8 P2_IRQ_N   <- P2 T14
```

Use common ground and 3.3 V logic. Do not join independent 3.3 V output rails.
USB-UART VCC remains disconnected.

For this gate, Tiny remains disconnected and both Primers use:

```text
R11 zeroize_ni       -> 3.3 V
R12 fatal_latched_i  -> GND
T12 secure_enable_i  -> GND
```

Direct UART remains isolated:

```text
P1 R13 uart_tx_o -> disconnected
P2 R13 uart_rx_i -> 3.3 V through 10 kΩ
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

Flash and Verify through SN-LINK. Do not reuse any v0.7.9 HEX.

Before interpreting SPI evidence, run:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 system-info
```

Required identity:

```text
protocol_version=1
architecture_version=0.7.10
sn32_build_id=0x0007000A
```

system-info remains local and side-effect free. Endpoint build IDs may initially
be zero only when startup discovery failed.

## Mandatory v0.7.10 rerun

1. Power off SN32.
2. Reset or reconfigure P1 and P2 to clear pending mailboxes.
3. Keep common ground connected.
4. Power or reset SN32 last with the v0.7.10 image.
5. Wait at least 3 s.

Run:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 system-info
trinity-host --port COM3 spi-first-failure
```

Expected result:

```text
architecture_version=0.7.10
sn32_build_id=0x0007000A
primer1_build_id=0x50310001
primer2_build_id=0x50320001
latched=False
```

Only when the first-failure latch is clear, run:

```bat
trinity-host --port COM3 spi-diag --target p1 --command get-info
trinity-host --port COM3 spi-diag --target p1 --command get-status
trinity-host --port COM3 spi-diag --target p2 --command get-info
trinity-host --port COM3 spi-diag --target p2 --command get-status
trinity-host --port COM3 spi-first-failure
```

Each trace must satisfy:

```text
transport_result = OK
response command and txid correlate
response CRC received = calculated
IRQ sequence = 0 -> 1 -> 1 -> 0
GET_INFO response_capture_length = 22
GET_STATUS response_capture_length = 26
```

Then run:

```bat
trinity-host --port COM3 system-status
trinity-host --port COM3 dual-spi-bringup --timeout 10 --poll 0.1
trinity-host --port COM3 spi-first-failure
```

Retained KAT masks remain:

```text
P1 = 0x013E
P2 = 0x03E3
```

## Acceptance criteria

```text
v0.7.10 exact Keil rebuild:                       PASS
v0.7.10 SN-LINK program/verify:                   PASS
v0.7.10 local identity readback:                  PASS
v0.7.10 standalone PC UART PING:                  PASS
first active SPI failure immediately postboot:    CLEAR
P1 GET_INFO raw diagnostic:                       PASS
P1 GET_STATUS raw diagnostic:                     PASS
P2 GET_INFO raw diagnostic:                       PASS
P2 GET_STATUS raw diagnostic:                     PASS
P1/P2 identity and ready mask:                    PASS
P1 retained KAT mask 0x013E and retirement:       PASS
P2 retained KAT mask 0x03E3 and retirement:       PASS
final ready mask includes SN32/P1/P2:             PASS
final fault_flags = 0:                            PASS
P2 uart_rx_i remains idle high:                   PASS
MISO contention or abnormal heating:              NONE
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
