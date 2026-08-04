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

## Locked evidence through v0.7.7

Repeated cold boots established one deterministic failure:

1. P1 accepted startup GET_INFO txid `0x0001` and committed a valid mailbox.
2. The first SN32 response capture returned an invalid eight-byte header such as
   `68 00 00 20 00 00 00 06` while P1 IRQ remained active.
3. A later read recovered the complete old txid-1 response with valid CRC.
4. Once that pending mailbox was consumed, P1 GET_STATUS, P2 GET_INFO and P2
   GET_STATUS all completed with exact frame lengths, valid CRC and IRQ sequence.
5. Increasing startup warmup to 2 s and response settle to 15 ms did not change
   the deterministic first-read signature.

Therefore the remaining failure is local to SN32 SPI FSM/FIFO reset completion,
not Primer command processing, CRC, wiring, common ground or endpoint timing.

## Required corrective image

```text
architecture_version = 0.7.8
sn32_build_id         = 0x00070008
```

Locked transport profile:

```text
SPI frequency                      = 100000 Hz
SPI mode                           = 0
bit order                          = MSB first
word length                        = 8 bits
SPI0 CLKDIV                        = 59
CS guard                           = 10 us nominal
startup warmup                     = 2000 ms
response settle                    = 15 ms
header + declared remainder        = one continuous CS
response capture                   = exact declared frame length
```

The v0.7.8 correction is:

```text
keep SPIEN enabled during FRESET
wait for FRESET self-clear before CS
apply one reset before each CS only
read DATA[7:0] after BUSY clear and RX ready
system-info is local and side-effect free
```

Detailed behavior:

1. Keep all CS lines high and wait for `BUSY=0`.
2. With `SPIEN=1`, write `FRESET=3`.
3. Wait until hardware self-clears `FRESET` before asserting any CS.
4. Verify RX FIFO is empty; bounded drain is retained only as a safeguard.
5. Assert exactly one Primer CS after the guard interval.
6. For each byte, write DATA, wait for BUSY to clear, wait for RX non-empty,
   then read the right-justified byte from `DATA[7:0]`.
7. Release CS without performing a second reset. The next `spi_select()` owns the
   single reset for the next transfer window.
8. Read the eight-byte response header and declared remainder under one CS.
9. A malformed header may retry the same pending mailbox without issuing a new
   request or allocating a new target transaction ID.
10. P1 discovery remains fail-fast before P2.
11. `system-info` returns local firmware identity and cached endpoint IDs without
    generating hidden SPI traffic.

## Wiring preflight

Perform wiring changes only with all boards powered off.

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

Rebuild `sn32/keil/trinity_sn32f407_deploy.uvprojx` and accept only:

```text
0 Error(s), 0 Warning(s)
Flash fit: PASS
RAM fit: PASS
AXF generation: PASS
HEX generation: PASS
```

Flash and Verify through SN-LINK. Do not reuse any v0.7.7 HEX.

After reset, verify the loaded image before interpreting SPI evidence:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 system-info
```

Required local identity:

```text
protocol_version=1
architecture_version=0.7.8
sn32_build_id=0x00070008
```

`primer1_build_id` and `primer2_build_id` may be zero until successful probes are
cached. `system-info` must succeed even when the startup SPI latch is set.

## Mandatory v0.7.8 rerun

1. Power off SN32 completely.
2. Reset or reconfigure P1 and P2 to clear pending mailboxes.
3. Keep common ground connected.
4. Power or reset SN32 last with the v0.7.8 image.
5. Wait at least 3 s.

Run:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 system-info
trinity-host --port COM3 spi-first-failure
```

Expected result:

```text
architecture_version=0.7.8
sn32_build_id=0x00070008
latched=False
```

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

Expected final endpoint identity:

```text
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
v0.7.8 exact Keil rebuild:                         PASS
v0.7.8 SN-LINK program/verify:                     PASS
v0.7.8 local identity readback:                    PASS
v0.7.8 standalone PC UART PING:                    PASS
first active SPI failure immediately postboot:     CLEAR
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
