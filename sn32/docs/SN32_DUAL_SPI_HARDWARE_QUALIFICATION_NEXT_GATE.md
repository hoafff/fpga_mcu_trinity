# SN32 -> P1/P2 dual-SPI hardware qualification — next gate

## Scope

This gate qualifies only the SN32F407 controller path to Primer #1 and Primer #2
over one shared SPI bus with independent chip selects and IRQ inputs.

The permitted final statement, only after every criterion passes, is:

```text
SN32 -> P1/P2 DUAL-SPI CONTROL PLANE HARDWARE: PASS
```

This gate does not establish a live session, enable secure operation, send the
direct P1-to-P2 UART payload, integrate Tiny, execute live-session ML-KEM or
qualify the complete system.

## Locked prior results

Already qualified separately:

```text
PC <-> SN32 UART PING HARDWARE: PASS
```

The v0.7.1 split-response defect is fixed: a complete Primer response is read
under one CS assertion. The v0.7.2 manual P1 GET_INFO, P2 GET_INFO and P2
GET_STATUS transactions passed command/txid correlation, CRC and IRQ release.

The v0.7.3/v0.7.4 latch also proved that the exact startup-drain frame below is
a reset residue whose target follows the Primer reset last:

```text
context        = STARTUP_DRAIN_P1 or STARTUP_DRAIN_P2
command        = 0x00
target_txid    = 0x0000
result         = BAD_LENGTH 0x0103
request_length = 0
frame_length   = 16
CRC            = valid
response       = A5 01 00 03 00 00 00 06 01 03 01 00 00 00 A4 65
```

Only that exact signature may appear as:

```text
latched=False
startup_residue=True
```

Every non-matching startup-drain error remains an active failure.

## New v0.7.4 cold-boot evidence

Two runs performed after complete wire and power disconnection reproduced the
same first active failure:

```text
context               = STARTUP_PROBE
target_id              = 1
command                = GET_STATUS 0x02
target_txid            = 0x0002
transport_result       = FRAME_TIMEOUT 0x0505
request_length         = 10
response_capture_length= 0
irq_after_request      = 1
irq_before_response    = 1
irq_after_response     = 0
request_bytes          = A5 01 02 00 00 02 00 00 A2 28
```

The probe reaches target txid `0x0002`, therefore P1 GET_INFO txid `0x0001`
completed sufficiently for the controller to issue P1 GET_STATUS. Full power
removal did not change the failure. This rules out reset order and PC UART
back-power as the explanation for this specific timeout.

SW2 is not used as qualification evidence because observed uptime continued to
increase after pressing it. That reset-button issue is separate from the
reproducible SPI failure.

## Required v0.7.5 image

```text
architecture_version = 0.7.5
sn32_build_id         = 0x00070005
```

Locked transport and new guard:

```text
SPI frequency                       = 100000 Hz
SPI mode                            = 0
bit order                           = MSB first
word length                         = 8 bits
SPI0 CLKDIV                         = 59
CS/FIFO guard                       = 10 us nominal
startup settle                      = 5 ms
inter-exchange guard                 = 1 ms
complete response read under one CS = retained
```

The 1 ms guard is applied after a valid response before the next endpoint
command. It separates the P1 GET_INFO mailbox release from the following P1
GET_STATUS request without changing the protocol, clock mode or payload.

After the immutable first active failure is latched, automatic periodic probing
is disabled. PC UART remains available to read evidence, and an explicit
`spi-diag` command may still be issued only after the first-failure audit.

## Byte-level timeout telemetry

The command remains:

```bat
trinity-host --port COM3 spi-first-failure
```

It reads SN32 RAM only and does not assert either Primer CS.

For v0.7.5 a trace additionally reports:

```text
transfer_stage
transfer_direction
transfer_byte_index
transfer_length
transfer_completed
spi_status
```

`transfer_stage` values are:

```text
NONE
TX_FULL
BUSY
RX_EMPTY
```

`transfer_direction` is `REQUEST` or `RESPONSE`. On another timeout these fields
identify the exact SPI peripheral wait condition and byte offset. For example,
`RX_EMPTY`, `RESPONSE`, byte 17 means the SN32 transmitted the response-read
clock for that byte but the SPI receive FIFO did not become non-empty before the
100 ms transfer deadline.

## Wiring preflight

Perform wiring changes with all boards powered off.

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

Tiny remains disconnected. On both Primers:

```text
R11 zeroize_ni       -> 3.3 V
R12 fatal_latched_i  -> GND
T12 secure_enable_i  -> GND
```

Direct UART isolation for this gate:

```text
P1 R13 uart_tx_o -> disconnected
P2 R13 uart_rx_i -> 3.3 V through 10 kΩ
```

## Exact rebuild and flash gate

```bat
git pull origin main
git submodule update --init --recursive
py -m pip install -e .\pc_host
git log -1 --oneline
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

Flash and Verify through SN-LINK. Do not reuse the v0.7.4 HEX.

## Mandatory v0.7.5 rerun

Do not use SW2. Use a complete SN32 power cycle after P1 and P2 are configured.
Then run only:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 spi-first-failure
```

Possible outcomes:

1. `latched=False`, optionally with the exact `startup_residue=True` signature:
   the 1 ms inter-exchange guard removed the active P1 timeout.
2. `latched=True`: stop and retain the complete block, especially
   `transfer_stage`, `transfer_direction`, `transfer_byte_index`,
   `transfer_completed` and `spi_status`.

Do not repeat power cycles merely to seek a passing run. One coherent v0.7.5
capture is sufficient to select the next source correction.

## Raw diagnostic stage

Only after the v0.7.5 first active failure latch is clear, run:

```bat
trinity-host --port COM3 spi-diag --target p1 --command get-info
trinity-host --port COM3 spi-diag --target p1 --command get-status
trinity-host --port COM3 spi-diag --target p2 --command get-info
trinity-host --port COM3 spi-diag --target p2 --command get-status
trinity-host --port COM3 spi-first-failure
```

Each active trace must satisfy:

```text
request flags = 0
request CRC valid
response command and txid correlate
response CRC received = calculated
IRQ sequence = 0 -> 1 -> 1 -> 0
transport_result = OK
```

Expected active response frame lengths are 22 bytes for GET_INFO and 26 bytes
for GET_STATUS. `response_capture_length=76` is intentional.

## Discovery and retained KAT gate

Only after all four active raw transactions pass:

```bat
trinity-host --port COM3 system-info
trinity-host --port COM3 system-status
trinity-host --port COM3 dual-spi-bringup --timeout 10 --poll 0.1
trinity-host --port COM3 spi-first-failure
```

Expected identity:

```text
protocol_version=1
architecture_version=0.7.5
sn32_build_id=0x00070005
primer1_build_id=0x50310001
primer2_build_id=0x50320001
```

Retained KAT masks:

```text
P1 = 0x013E
P2 = 0x03E3
```

## Acceptance criteria

```text
v0.7.5 exact Keil rebuild:                         PASS
v0.7.5 SN-LINK program/verify:                     PASS
v0.7.5 standalone PC UART PING:                    PASS
first active SPI failure immediately postboot:     CLEAR
startup reset residue:                             NONE or EXACT-MATCH ONLY
P1 GET_INFO raw active diagnostic:                 PASS
P1 GET_STATUS raw active diagnostic:               PASS
P2 GET_INFO raw active diagnostic:                 PASS
P2 GET_STATUS raw active diagnostic:               PASS
first active SPI failure after raw diagnostics:    CLEAR
P1/P2 identity and ready mask:                     PASS
P1 retained KAT mask 0x013E and retirement:        PASS
P2 retained KAT mask 0x03E3 and retirement:        PASS
final ready mask includes SN32/P1/P2:              PASS
final fault_flags = 0:                             PASS
P2 uart_rx_i remains idle high:                    PASS
MISO contention or abnormal heating:               NONE
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

Use `sn32/hardware/dual_spi_control_plane/evidence/run_manifest_TEMPLATE.txt`
to retain the exact build, flash, first-failure telemetry, raw traces and every
failed attempt.
