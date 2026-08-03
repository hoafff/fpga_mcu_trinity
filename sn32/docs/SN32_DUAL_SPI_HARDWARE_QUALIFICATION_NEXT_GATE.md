# SN32 -> P1/P2 dual-SPI hardware qualification — next gate

## Scope

This gate qualifies only the SN32F407 controller path to both Primer boards over
one shared SPI bus with independent chip selects and IRQ inputs.

Target statement, only after every acceptance criterion passes:

```text
SN32 -> P1/P2 DUAL-SPI CONTROL PLANE HARDWARE: PASS
```

This gate does not establish a live session, enable secure operation, send
telemetry, exercise the direct P1-to-P2 UART payload, integrate Tiny, execute
ML-KEM as part of a live session, or qualify the full system.

## Locked prior results and reset-order evidence

Already qualified separately:

```text
PC <-> SN32 UART PING HARDWARE: PASS
```

The v0.7.1 split-response defect is fixed: every Primer response is now read
under one CS assertion. The v0.7.2 manual raw transactions passed command/txid
correlation, CRC and IRQ release.

The v0.7.3 immutable latch then captured the actual pre-controller mailbox:

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

Reset order proved that this mailbox follows the Primer reset last:

```text
reset P1 then P2 -> STARTUP_DRAIN_P2
reset P2 then P1 -> STARTUP_DRAIN_P1
```

Therefore this exact frame is a pre-controller reset residue, not a failed
active GET_INFO/GET_STATUS transaction and not a P2-specific wiring defect.
Every non-matching startup-drain error remains a failure.

## Required v0.7.4 image

```text
architecture_version = 0.7.4
sn32_build_id         = 0x00070004
```

Locked transport:

```text
SPI frequency = 100000 Hz
SPI mode      = 0
bit order     = MSB first
word length   = 8 bits
SPI0 CLKDIV   = 59
CS/FIFO guard = 10 us nominal
startup settle= 5 ms
```

The PC command remains:

```bat
trinity-host --port COM3 spi-first-failure
```

It reads SN32 RAM only. It does not assert either Primer CS and does not allocate
a target transaction ID.

### v0.7.4 classification contract

Only the following exact trace may be reported as startup residue rather than an
active SPI failure:

```text
context in {STARTUP_DRAIN_P1, STARTUP_DRAIN_P2}
command = 0x00
target_txid = 0x0000
request_length = 0
transport_result = BAD_LENGTH 0x0103
response_frame_length = 16
response flags = RESPONSE | ERROR
response payload length = 6
session_state = SELF_TEST_REQUIRED
operation_state = IDLE
detail = 0
response CRC received = response CRC calculated
```

Expected CLI form:

```text
[SPI_FIRST_FAILURE]
latched=False
startup_residue=True
context=STARTUP_DRAIN_P1
```

or:

```text
[SPI_FIRST_FAILURE]
latched=False
startup_residue=True
context=STARTUP_DRAIN_P2
```

A completely clean startup may instead report:

```text
[SPI_FIRST_FAILURE]
latched=False
startup_residue=False
context=NONE
```

Any other trace must report `latched=True` and stops the gate. The reset residue
is retained as evidence; it is not silently discarded. The Primer target may
continue to expose historical `BAD_LENGTH/DIAG_TRANSPORT` in its own GET_STATUS.
That historical bit alone is not treated as a new active-transport failure.

## Wiring preflight

Perform all wiring with every board powered off.

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
FT232 VCC remains disconnected.

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

Flash and Verify through SN-LINK. Do not reuse a v0.7.2 or v0.7.3 HEX.

## Mandatory first-boot sequence

After a controlled reset/power sequence, run only:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 spi-first-failure
```

Proceed only when:

```text
latched=False
```

`startup_residue=False` is clean. `startup_residue=True` is accepted only when
the complete trace matches the exact reset-residue contract above. Record the
whole block.

If `latched=True`, stop. Do not run `system-info`, `system-status` or
`dual-spi-bringup` in that boot.

## Mandatory raw diagnostic stage

After the latch audit:

```bat
trinity-host --port COM3 spi-diag --target p1 --command get-info
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

Expected active response frame lengths are 22, 22 and 26 bytes.
`response_capture_length=76` is intentional.

The final `spi-first-failure` read must still show `latched=False`. A previously
recorded `startup_residue=True` may remain visible unchanged; it must not be
replaced by an active failure.

## Discovery and retained KAT gate

Only after raw active transactions pass:

```bat
trinity-host --port COM3 system-info
trinity-host --port COM3 system-status
trinity-host --port COM3 dual-spi-bringup --timeout 10 --poll 0.1
trinity-host --port COM3 spi-first-failure
```

Expected identity:

```text
protocol_version=1
architecture_version=0.7.4
sn32_build_id=0x00070004
primer1_build_id=0x50310001
primer2_build_id=0x50320001
```

The retained KAT masks remain:

```text
P1 = 0x013E
P2 = 0x03E3
```

## Acceptance criteria

```text
v0.7.4 exact Keil rebuild:                         PASS
v0.7.4 SN-LINK program/verify:                     PASS
v0.7.4 standalone PC UART PING:                    PASS
first active SPI failure latch immediately postboot:CLEAR
startup reset residue:                             NONE or EXACT-MATCH ONLY
P1 GET_INFO raw active diagnostic:                 PASS
P2 GET_INFO raw active diagnostic:                 PASS
P2 GET_STATUS raw active diagnostic:               PASS
first active SPI failure after raw diagnostics:    CLEAR
P1/P2 identity and ready mask:                     PASS
P1 retained KAT mask 0x013E and retirement:        PASS
P2 retained KAT mask 0x03E3 and retirement:        PASS
final ready mask includes SN32/P1/P2:              PASS
final fault_flags = 0:                             PASS
first active SPI failure after complete gate:      CLEAR
P2 uart_rx_i remains idle high:                    PASS
MISO contention or abnormal heating:               NONE
```

Expected final marker:

```text
[SN32_DUAL_SPI_CONTROL_PLANE]
result=PASS
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

## Evidence to retain

Use:

```text
sn32/hardware/dual_spi_control_plane/evidence/run_manifest_TEMPLATE.txt
```

Retain the exact build and SN-LINK logs, startup residue or first-failure trace,
all raw SPI traces, discovery/status logs, full retained-KAT run, wiring photos,
source/submodule/bitstream identities and every failed attempt.
