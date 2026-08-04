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

## Locked hardware evidence through v0.7.8

The v0.7.8 image identity was verified on hardware as:

```text
architecture_version = 0.7.8
sn32_build_id         = 0x00070008
```

Its startup trace proved:

1. SN32 sent byte-exact P1 GET_INFO request txid `0x0001` with CRC `0x3598`.
2. P1 accepted that request, asserted IRQ and built the valid 22-byte response.
3. The first two eight-byte SN32 response captures returned malformed headers
   while IRQ remained active, so the mailbox was not consumed.
4. A later host `spi-diag --target p1 --command get-info` first clocked ten bytes
   from the already-pending mailbox during its nominal request phase.
5. Under the next fresh CS, SN32 recovered the exact original response:

```text
a5 01 01 01 00 01 00 0c 01 01 00 00 11 ff 50 31 00 01 00 00 d2 6c
```

6. Received and calculated CRC both equalled `0xD26C` and IRQ released `1 -> 0`.
7. The apparent `TRANSACTION_CONFLICT` was only host correlation against the new
   diagnostic txid `0x0002`; the recovered frame correctly belonged to startup
   txid `0x0001`.

This proves the Primer request path, command core, response builder, mailbox,
CRC, CS restart and IRQ release are correct. The remaining defect is restricted
to SN32's initial mailbox receive sequence.

## Required corrective image

```text
architecture_version = 0.7.9
sn32_build_id         = 0x00070009
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

## v0.7.9 bounded recovery

Normal behavior is unchanged:

1. Send one GET_INFO request with one target transaction ID.
2. Wait for the target IRQ.
3. Attempt to read the eight-byte header and declared remainder under one CS.
4. If a malformed header leaves IRQ active, retry the same mailbox under a fresh
   CS without sending another request.

Only when both normal eight-byte startup GET_INFO reads fail while IRQ remains
active, v0.7.9 performs the exact sequence proven by the v0.7.8 hardware log:

```text
selected-CS mailbox prime = 10 bytes discarded
release CS
fresh CS
read the same pending mailbox from byte 0
```

Safety constraints:

```text
no new SPI request
no new target transaction ID
only context STARTUP_PROBE
only command GET_INFO
only while endpoint IRQ remains active
prime length exactly 10 bytes
known GET_INFO response length = 22 bytes
```

Ten clocks cannot retire the 22-byte GET_INFO mailbox. The FPGA resets its
mailbox transmit index on the next CS, so the final capture starts at byte zero.
The existing two-attempt path remains unchanged for all other commands.

`system-info` remains local and side-effect free, allowing the SN32 firmware
identity to be verified even if SPI startup fails.

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

Flash and Verify through SN-LINK. Do not reuse any v0.7.8 HEX.

After reset, verify the loaded image before interpreting SPI evidence:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 system-info
```

Required local identity:

```text
protocol_version=1
architecture_version=0.7.9
sn32_build_id=0x00070009
```

`primer1_build_id` and `primer2_build_id` may initially be zero only if endpoint
probing has not completed. `system-info` itself must not generate SPI traffic.

## Mandatory v0.7.9 rerun

1. Power off SN32 completely.
2. Reset or reconfigure P1 and P2 to clear the old pending mailbox.
3. Keep common ground connected.
4. Power or reset SN32 last with the verified v0.7.9 image.
5. Wait at least 3 seconds.

Run only:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 system-info
trinity-host --port COM3 spi-first-failure
```

Expected result:

```text
architecture_version=0.7.9
sn32_build_id=0x00070009
primer1_build_id=0x50310001
primer2_build_id=0x50320001
latched=False
```

If `latched=True`, stop and retain the full first-failure trace. Do not issue a
new diagnostic request until that trace has been audited.

Only when the first active failure latch is clear, run:

```bat
trinity-host --port COM3 spi-diag --target p1 --command get-info
trinity-host --port COM3 spi-diag --target p1 --command get-status
trinity-host --port COM3 spi-diag --target p2 --command get-info
trinity-host --port COM3 spi-diag --target p2 --command get-status
trinity-host --port COM3 spi-first-failure
```

Each active diagnostic must satisfy:

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
v0.7.9 exact Keil rebuild:                         PASS
v0.7.9 SN-LINK program/verify:                     PASS
v0.7.9 local identity readback:                    PASS
v0.7.9 standalone PC UART PING:                    PASS
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
