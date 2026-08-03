# SN32 -> P1/P2 dual-SPI hardware qualification — next gate

## Scope

This gate qualifies only the SN32F407 controller path to both Primer boards over
one shared SPI bus with independent chip selects and IRQ inputs.

Target statement, only after all acceptance criteria pass:

```text
SN32 -> P1/P2 DUAL-SPI CONTROL PLANE HARDWARE: PASS
```

This gate does not establish a session, enable secure operation, send telemetry,
exercise the direct P1-to-P2 UART payload, integrate Tiny, execute ML-KEM as part
of a live session, or qualify the full system.

## Prior results

Already locked separately:

```text
PC <-> SN32 UART PING HARDWARE: PASS
```

Evidence:

```text
sn32/docs/PC_TO_SN32_UART_PING_HARDWARE_QUALIFICATION_2026-08-03.md
sn32/hardware/pc_uart_ping/evidence/pc_uart_ping_2026-08-03.txt
```

The first v0.7.1 clean-boot dual-SPI run failed during PC `GET_SYSTEM_INFO` with
reported error `TRANSACTION_CONFLICT`, source 2 and related target txid zero.
The old telemetry cannot prove which endpoint or target command failed first.
The source audit found that SN32 split a Primer response across two CS
assertions, while the Primer mailbox restarts at response byte zero on every CS
falling edge.

Failure audit:

```text
sn32/docs/SN32_DUAL_SPI_CLEAN_BOOT_FAILURE_2026-08-03.md
sn32/hardware/dual_spi_control_plane/evidence/clean_boot_failure_2026-08-03.txt
```

Do not reuse the v0.7.1 image for this gate.

## Locked qualification transport

```text
SPI frequency = 100000 Hz
SPI mode      = 0
bit order     = MSB first
word length   = 8 bits
```

For the 12 MHz SN32 peripheral clock:

```text
SCK = 12000000 / (2 * (59 + 1)) = 100000 Hz
SPI0 CLKDIV = 59
```

The corrected transport captures the complete maximum response under one CS
assertion, then derives and validates the declared frame length. It drains a
pre-existing startup mailbox before the initial probe.

## Required image identity

```text
architecture_version = 0.7.2
sn32_build_id         = 0x00070002
```

Expected Primer identities:

```text
Primer #1 target_id = 1
Primer #1 build_id  = 0x50310001
Primer #2 target_id = 2
Primer #2 build_id  = 0x50320001
protocol_version    = 1
```

The P1 and P2 FPGA bitstreams must be the same implementations used for their
previous hardware qualification. Record the exact `.fs` hashes when available.

## Wiring preflight

Perform all wiring with every board powered off.

### Shared ground and power boundary

- Connect SN32, P1, P2 and FT232 grounds together.
- Use 3.3 V logic only.
- Power each development board through its intended board power input.
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

Do not swap P2.1/P2.2 or P2.3/P2.8.

### Primer safety levels

Tiny remains disconnected. On both Primer boards:

```text
R11 zeroize_ni       -> 3.3 V
R12 fatal_latched_i  -> GND
T12 secure_enable_i  -> GND
```

`secure_enable_i` must remain low. SN32 P3.8 remains disconnected from Tiny.

### Direct P1-to-P2 UART isolation

```text
P1 R13 uart_tx_o -> disconnected
P2 R13 uart_rx_i -> 3.3 V through 10 kΩ
```

The pull-up keeps the isolated P2 UART input at idle high. This does not revoke
the earlier direct-UART qualification.

## Power and reset sequence

1. Confirm wiring with all boards powered off.
2. Power P1 and P2 and wait for both FPGA configurations to complete.
3. Confirm both CS inputs are high.
4. Confirm P2 R13 is idle high and both unselected MISO outputs are released.
5. Connect/power FT232 without its VCC pin.
6. Power or reset SN32 last.
7. Do not reset P1/P2 after SN32 starts.
8. Abort for abnormal heating, supply droop, MISO contention or a CS stuck low.

## Exact rebuild and flash gate

```bat
git pull origin main
git submodule update --init --recursive
py -m pip install -e .\pc_host
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

Flash and Verify through SN-LINK. Before connecting P1/P2, repeat standalone:

```bat
trinity-host --port COM3 ping
```

That PING must pass with the v0.7.2 image.

## Mandatory side-effect-free diagnostic stage

After wiring and the clean power sequence, do not start with
`dual-spi-bringup`. Run only:

```bat
trinity-host --port COM3 spi-diag --target p1 --command get-info
trinity-host --port COM3 spi-diag --target p2 --command get-info
trinity-host --port COM3 spi-diag --target p2 --command get-status
```

Each trace reports:

```text
target_id
command
target_txid
request_fingerprint
request_length
request_bytes
request_crc
response_capture_length
response_frame_length
response_bytes
response_crc_received
response_crc_calculated
response_crc_match
irq_before_request
irq_after_request
irq_before_response
irq_after_response
error_source
transport_result
```

The command is restricted in both host and firmware to target `GET_INFO` and
`GET_STATUS`; it cannot run self-test, stage/commit a session, zeroize or send
telemetry.

Audit each trace before continuing. At minimum:

- request begins `A5 01` and contains the printed command and target txid;
- request CRC matches the last two request bytes;
- response begins `A5 01` when a mailbox was captured;
- response command and txid correlate with the request;
- received and calculated response CRC match;
- IRQ asserts for the response and releases after the full single-CS read;
- no second response starts at byte zero inside the captured frame.

## Discovery and complete gate

Only after all three raw diagnostics are coherent:

```bat
trinity-host --port COM3 system-info
trinity-host --port COM3 system-status
```

Expected fields:

```text
protocol_version=1
architecture_version=0.7.2
sn32_build_id=0x00070002
primer1_build_id=0x50310001
primer2_build_id=0x50320001
target_ready_mask includes 0x01 | 0x02 | 0x04
fault_flags=0x00
```

Then run once:

```bat
trinity-host --port COM3 dual-spi-bringup --timeout 10 --poll 0.1
```

The command executes PING, P1/P2 discovery and status, separate retained P1 KAT
mask `0x013E`, separate retained P2 KAT mask `0x03E3`, both result retirements,
and final status verification.

## Acceptance criteria

```text
v0.7.2 exact Keil rebuild:               PASS
v0.7.2 SN-LINK program/verify:            PASS
v0.7.2 standalone PC UART PING:           PASS
P1 GET_INFO raw diagnostic:               PASS
P2 GET_INFO raw diagnostic:               PASS
P2 GET_STATUS raw diagnostic:             PASS
single-CS response capture and CRC:       PASS
P1 GET_INFO identity:                     PASS
P2 GET_INFO identity:                     PASS
P1/P2 ready mask:                         PASS
P1 retained KAT mask 0x013E:              PASS
P1 result retirement:                     PASS
P2 retained KAT mask 0x03E3:              PASS
P2 result retirement:                     PASS
final ready mask includes SN32/P1/P2:      PASS
final fault_flags = 0:                     PASS
P2 uart_rx_i remains idle high:            PASS
MISO contention or abnormal heating:      NONE
```

Expected final marker:

```text
[SN32_DUAL_SPI_CONTROL_PLANE]
result=PASS
```

Only after complete log audit may the scoped statement be recorded:

```text
SN32 -> P1/P2 DUAL-SPI CONTROL PLANE HARDWARE: PASS
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

Retain exact build and SN-LINK logs, standalone PING, all three raw SPI traces,
`system-info`, `system-status`, full `dual-spi-bringup`, wiring photographs,
source/submodule/bitstream identities, and every failed attempt. Do not create a
PASS record from only the final CLI line.
