# SN32 -> P1/P2 dual-SPI hardware qualification — next gate

## Scope

This gate qualifies only the SN32F407 controller path to Primer #1 and Primer #2
over one shared SPI bus with independent chip selects and IRQ inputs.

The permitted statement, only after every criterion passes, is:

```text
SN32 -> P1/P2 DUAL-SPI CONTROL PLANE HARDWARE: PASS
```

It does not qualify session activation, direct P1-to-P2 UART telemetry, Tiny,
live-session ML-KEM or the full system.

## Locked prior evidence

PC-to-SN32 UART PING is already hardware-qualified separately.

The v0.7.6 cold-boot trace established the following sequence:

1. P1 accepted GET_INFO txid `0x0001` and built a valid 22-byte response.
2. The first SN32 response read captured only an invalid eight-byte header:
   `13 00 00 00 00 01 00 0C` or `11 00 00 00 00 00 00 06`.
3. IRQ remained active, proving that the Primer mailbox was still pending.
4. A later transaction recovered a valid old response with matching CRC but the
   old txid, proving that the original request succeeded and the failure was in
   the SN32 receive path rather than the Primer command core.
5. Running further commands after that point produced transaction correlation
   errors because the old mailbox had not been consumed.

Removing SN32 power, common ground and all visible back-power did not change the
failure class. Therefore power order and the common-ground connection are not
accepted as the root cause for this trace.

## Required corrective image

```text
architecture_version = 0.7.7
sn32_build_id         = 0x00070007
```

Locked transport profile:

```text
SPI frequency                      = 100000 Hz
SPI mode                           = 0
bit order                          = MSB first
word length                        = 8 bits
SPI0 CLKDIV                        = 59
CS guard                           = 10 us nominal
startup settle                     = 5 ms
inter-exchange guard               = 1 ms
header + declared remainder        = one continuous CS
response capture                   = exact declared frame length
```

The v0.7.7 correction is:

```text
reset SPI/FIFO before every CS
BUSY clear before DATA read
retry the same pending mailbox
fail-fast P1 before P2
```

Detailed behavior:

1. With all CS lines high, disable SPI0, apply `FRESET=3`, re-enable SPI0 and
   drain any residual RX FIFO entries.
2. Assert exactly one Primer CS after the guard interval.
3. For each byte, write TX, wait for BUSY to clear, wait for RX to become
   non-empty, then read DATA. This matches the SONiX polling sequence.
4. Read the eight-byte header and its declared remainder under one continuous
   CS assertion.
5. If the first header is malformed or times out while IRQ remains active,
   release CS, reset the local SPI peripheral and make one bounded retry of the
   same pending response. Do not issue another request and do not allocate a new
   target transaction ID.
6. If P1 discovery fails, return immediately without probing P2. This prevents a
   second stale mailbox from obscuring the first failure.

## Wiring preflight

Perform all wiring changes with every board powered off.

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

## Exact rebuild and flash

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

Flash and Verify through SN-LINK. Do not reuse the v0.7.6 HEX.

## Mandatory v0.7.7 rerun

Because the current P1/P2 mailboxes may contain responses left by the failed
v0.7.6 run, perform one clean reset sequence:

1. Power off SN32 completely.
2. Reset or reconfigure P1 and P2.
3. Confirm no unexpected heating.
4. Power or reset SN32 last with the new v0.7.7 image.
5. Do not use SW2 as reset evidence.

Run only:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 spi-first-failure
```

Expected result:

```text
latched=False
```

An exact startup reset residue may appear only if it matches the previously
locked command-0, txid-0, BAD_LENGTH, 16-byte, valid-CRC signature.

Only when the first active failure latch is clear, run:

```bat
trinity-host --port COM3 spi-diag --target p1 --command get-info
trinity-host --port COM3 spi-diag --target p1 --command get-status
trinity-host --port COM3 spi-diag --target p2 --command get-info
trinity-host --port COM3 spi-diag --target p2 --command get-status
trinity-host --port COM3 spi-first-failure
```

Each active trace must satisfy:

```text
transport_result = OK
request CRC valid
response command and txid correlate
response CRC received = calculated
IRQ sequence = 0 -> 1 -> 1 -> 0
GET_INFO response_capture_length = 22
GET_STATUS response_capture_length = 26
```

Then run:

```bat
trinity-host --port COM3 system-info
trinity-host --port COM3 system-status
trinity-host --port COM3 dual-spi-bringup --timeout 10 --poll 0.1
trinity-host --port COM3 spi-first-failure
```

Expected identity:

```text
protocol_version=1
architecture_version=0.7.7
sn32_build_id=0x00070007
primer1_build_id=0x50310001
primer2_build_id=0x50320001
```

Retained KAT masks remain:

```text
P1 = 0x013E
P2 = 0x03E3
```

## Acceptance criteria

```text
v0.7.7 exact Keil rebuild:                         PASS
v0.7.7 SN-LINK program/verify:                     PASS
v0.7.7 standalone PC UART PING:                    PASS
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
