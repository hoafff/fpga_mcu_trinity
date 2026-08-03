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

## Locked prior results

Already qualified separately:

```text
PC <-> SN32 UART PING HARDWARE: PASS
```

The v0.7.1 dual-SPI image failed because SN32 split each Primer response across
two CS assertions. Primer restarts mailbox transmission at byte zero on every
CS falling edge. That root cause is fixed by the single-CS response read.

The v0.7.2 image then established that all three manual raw transactions work:

```text
P1 GET_INFO:   PASS
P2 GET_INFO:   PASS
P2 GET_STATUS: PASS
```

For those transactions, command and target txid correlated, received CRC equaled
calculated CRC, and IRQ followed `0 -> 1 -> 1 -> 0`.

However, an immediate first-boot capture used manual target txid `0x0004` and
showed that P2 had already recorded:

```text
last_error         = BAD_FLAGS 0x0105
diagnostic_summary = DIAG_TRANSPORT | DIAG_CRC = 0x00000003
```

Therefore the v0.7.2 automatic startup drain/probe path is not qualified. The
failure happened before periodic refresh. Do not use v0.7.1 or v0.7.2 for this
gate.

Failure evidence remains retained at:

```text
sn32/docs/SN32_DUAL_SPI_CLEAN_BOOT_FAILURE_2026-08-03.md
sn32/hardware/dual_spi_control_plane/evidence/clean_boot_failure_2026-08-03.txt
```

## Required v0.7.3 image

```text
architecture_version = 0.7.3
sn32_build_id         = 0x00070003
```

The image keeps the locked transport:

```text
SPI frequency = 100000 Hz
SPI mode      = 0
bit order     = MSB first
word length   = 8 bits
SPI0 CLKDIV   = 59
```

It adds:

```text
CS/FIFO software guard nominal value = 10 us
startup settle before drain/probe     = 5 ms
complete response read under one CS   = retained
first failed SPI trace                = immutable until SN32 reset
```

The software guard loop intentionally lasts at least the nominal value on the
12 MHz SN32 qualification image.

The new PC command:

```bat
trinity-host --port COM3 spi-first-failure
```

reads SN32 RAM only. It does not assert either Primer CS and does not allocate a
target transaction ID.

Trace contexts are:

```text
NONE
STARTUP_DRAIN_P1
STARTUP_DRAIN_P2
STARTUP_PROBE
PERIODIC_PROBE
HOST_DIAGNOSTIC
```

Expected Primer identities remain:

```text
Primer #1 target_id = 1
Primer #1 build_id  = 0x50310001
Primer #2 target_id = 2
Primer #2 build_id  = 0x50320001
protocol_version    = 1
```

## Wiring preflight

Perform all wiring with every board powered off.

### Shared ground and power boundary

- Connect SN32, P1, P2 and FT232 grounds together.
- Use 3.3 V logic only.
- Power each board through its intended board power input.
- Do not join independent 3.3 V output rails.
- Do not connect FT232 VCC to an SN32 or Primer power rail.

### Shared SPI bus

```text
SN32 P1.0 SPI0_SCK   -> P1 P16 spi_sck_i
                      -> P2 P16 spi_sck_i

SN32 P1.2 SPI0_MOSI  -> P1 P15 spi_mosi_i
                      -> P2 P15 spi_mosi_i

SN32 P1.1 SPI0_MISO  <- P1 T15 spi_miso_o
                      <- P2 T15 spi_miso_o
```

Both Primer MISO outputs share the same wire. Only the selected device may drive
it.

### Independent selects and IRQ inputs

```text
SN32 P2.1 P1_CS_N  -> P1 R14 spi_cs_ni
SN32 P2.2 P2_CS_N  -> P2 R14 spi_cs_ni
SN32 P2.3 P1_IRQ_N <- P1 T14 irq_no
SN32 P2.8 P2_IRQ_N <- P2 T14 irq_no
```

### Primer safety levels

Tiny remains disconnected. On both Primer boards:

```text
R11 zeroize_ni       -> 3.3 V
R12 fatal_latched_i  -> GND
T12 secure_enable_i  -> GND
```

SN32 P3.8 remains disconnected from Tiny.

### Direct P1-to-P2 UART isolation

```text
P1 R13 uart_tx_o -> disconnected
P2 R13 uart_rx_i -> 3.3 V through 10 kΩ
```

The pull-up keeps P2 UART RX at idle high and does not revoke the earlier direct
UART qualification.

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

Flash and Verify through SN-LINK. Do not reuse the v0.7.2 HEX.

## Clean power and reset sequence

1. Power off or disconnect SN32.
2. Reset P1 and P2 and wait for both FPGA configurations to complete.
3. Confirm both CS inputs are high.
4. Confirm P2 R13 is idle high and unselected MISO is released.
5. Start the PC command sequence below.
6. Power or reset SN32 last.
7. Do not reset P1/P2 after SN32 starts.
8. Abort for abnormal heating, supply droop, contention or a CS stuck low.

## Mandatory first-boot sequence

Run only:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 spi-first-failure
```

The clean result is:

```text
[SPI_FIRST_FAILURE]
latched=False
context=NONE
```

A latched trace is not automatically discarded. Record the complete block. Its
context, target, command, txid, request bytes, response bytes, CRC fields and IRQ
levels identify the first observed failure before any manual Primer transaction.

If `latched=True`, stop this gate. Do not run `system-info`, `system-status` or
`dual-spi-bringup` in that boot.

## Mandatory raw diagnostic stage

Only after `latched=False`, run:

```bat
trinity-host --port COM3 spi-diag --target p1 --command get-info
trinity-host --port COM3 spi-diag --target p2 --command get-info
trinity-host --port COM3 spi-diag --target p2 --command get-status
```

Each request must have length 10. Expected response frame lengths are 22, 22 and
26 bytes. `response_capture_length=76` is intentional; only
`response_frame_length` bytes belong to the frame.

Audit each trace:

- request begins `A5 01` and contains the printed command and target txid;
- request flags are zero;
- request CRC equals the final two request bytes;
- response begins `A5 01`;
- response command and txid match the request;
- received and calculated response CRC match;
- IRQ asserts for the mailbox and releases after the complete read;
- `transport_result=OK`.

After those three traces, read the latch again:

```bat
trinity-host --port COM3 spi-first-failure
```

It must still report `latched=False`. This verifies that manual diagnostics did
not introduce the first failure.

## Discovery and retained KAT gate

Only after the startup latch and raw diagnostics are clean:

```bat
trinity-host --port COM3 system-info
trinity-host --port COM3 system-status
```

Expected identity fields:

```text
protocol_version=1
architecture_version=0.7.3
sn32_build_id=0x00070003
primer1_build_id=0x50310001
primer2_build_id=0x50320001
```

Then run once:

```bat
trinity-host --port COM3 dual-spi-bringup --timeout 10 --poll 0.1
```

This executes PING, P1/P2 discovery and status, the retained P1 KAT mask
`0x013E`, the retained P2 KAT mask `0x03E3`, both result retirements, and final
status verification.

Read the first-failure latch once more after the gate. It must remain clear.

## Acceptance criteria

```text
v0.7.3 exact Keil rebuild:                    PASS
v0.7.3 SN-LINK program/verify:                PASS
v0.7.3 standalone PC UART PING:               PASS
first SPI failure latch immediately postboot: CLEAR
P1 GET_INFO raw diagnostic:                   PASS
P2 GET_INFO raw diagnostic:                   PASS
P2 GET_STATUS raw diagnostic:                 PASS
first SPI failure latch after raw diagnostics:CLEAR
single-CS response capture and CRC:           PASS
P1 GET_INFO identity:                         PASS
P2 GET_INFO identity:                         PASS
P1/P2 ready mask:                             PASS
P1 retained KAT mask 0x013E:                  PASS
P1 result retirement:                         PASS
P2 retained KAT mask 0x03E3:                  PASS
P2 result retirement:                         PASS
final ready mask includes SN32/P1/P2:         PASS
final fault_flags = 0:                        PASS
first SPI failure latch after complete gate:  CLEAR
P2 uart_rx_i remains idle high:               PASS
MISO contention or abnormal heating:          NONE
```

Expected final marker:

```text
[SN32_DUAL_SPI_CONTROL_PLANE]
result=PASS
```

Only after complete log audit may the scoped statement be recorded.

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

Retain exact build and SN-LINK logs, all three first-failure-latch reads, the
three raw SPI traces, `system-info`, `system-status`, full
`dual-spi-bringup`, wiring photographs, source/submodule/bitstream identities,
and every failed attempt. Do not create a PASS record from only the final CLI
line.
