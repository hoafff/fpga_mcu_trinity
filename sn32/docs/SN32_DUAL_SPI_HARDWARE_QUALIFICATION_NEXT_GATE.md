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

## Prerequisite evidence

Already locked separately:

```text
PC <-> SN32 UART PING HARDWARE: PASS
```

Evidence:

```text
sn32/docs/PC_TO_SN32_UART_PING_HARDWARE_QUALIFICATION_2026-08-03.md
sn32/hardware/pc_uart_ping/evidence/pc_uart_ping_2026-08-03.txt
```

That result belongs to source commit:

```text
40ff6f06ed32d3139899aae291047f35d0740f86
```

The dual-SPI gate uses the later v0.7.1 qualification image and therefore
requires a new exact Keil rebuild, flash operation and standalone PING check
before connecting either Primer.

## Locked qualification transport

The first SN32 dual-SPI run uses the same transport settings as the previously
successful ESP32-C3 dual-Primer harness:

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

Do not raise the SPI frequency during this qualification. A later speed increase
requires a separate evidence run.

## Required image identity

The qualification build reports:

```text
architecture_version = 0.7.1
sn32_build_id         = 0x00070001
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
- Do not join independent 3.3 V output rails merely because the grounds are
  common.
- Do not connect FT232 VCC to the SN32 or Primer power rail.

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
it. Do not proceed if either board drives MISO while its chip select is high.

### Independent selects and IRQ inputs

```text
SN32 P2.1 P1_CS_N  -> P1 R14 spi_cs_ni
SN32 P2.2 P2_CS_N  -> P2 R14 spi_cs_ni
SN32 P2.3 P1_IRQ_N <- P1 T14 irq_no
SN32 P2.8 P2_IRQ_N <- P2 T14 irq_no
```

Do not swap P2.1/P2.2 or P2.3/P2.8. The host gate verifies fixed P1 and P2 build
IDs, so a swapped pair must fail rather than being accepted.

### Primer safety levels for this control-plane-only gate

Tiny is not connected. Apply fixed safe levels independently to both Primer
boards:

```text
R11 zeroize_ni       -> 3.3 V
R12 fatal_latched_i  -> GND
T12 secure_enable_i  -> GND
```

`secure_enable_i` must stay low for the entire gate. The SN32 P3.8
session-commit output remains disconnected from Tiny.

Do not leave R11, R12 or T12 floating.

### Direct P1-to-P2 UART isolation

Do not connect P1 R13 to P2 R13 in this dual-SPI control-plane gate.

Because P2 `uart_rx_i` has no internal pull configured, hold the isolated P2 R13
input at the UART idle-high level through a 10 kΩ pull-up:

```text
P1 R13 uart_tx_o -> disconnected
P2 R13 uart_rx_i -> 3.3 V through 10 kΩ
```

Do not tie P2 R13 directly to P1 or to a push-pull test source during this gate.
The 10 kΩ pull-up prevents a floating UART input without creating a hard drive
conflict when the later direct-UART connection is restored after power-off.

This isolation does not revoke the earlier independent P1-to-P2 UART hardware
qualification.

## Power and reset sequence

1. Confirm all SPI, safety, P2 UART pull-up and ground wiring with power removed.
2. Power P1 and P2 and wait for both FPGA configurations to complete.
3. Confirm both CS inputs are high before starting SN32.
4. Confirm P2 R13 is idle high and both unselected MISO outputs are released.
5. Connect/power the FT232 without connecting its VCC pin.
6. Power or reset SN32 last so its initial `GET_INFO` requests reach configured
   Primer endpoints.
7. Abort immediately for abnormal heating, supply droop, MISO contention or a
   chip-select line stuck low.

Power-cycling P1/P2 before SN32 also prevents an old response mailbox from being
mistaken for the first SN32 transaction.

## Pre-connection rebuild and flash gate

After pulling the qualification source:

```bat
git pull origin main
git submodule update --init --recursive
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

Flash and verify through SN-LINK. Before connecting P1/P2, repeat:

```bat
trinity-host --port COM3 ping
```

This standalone PING must pass with the new v0.7.1 image.

## Hardware execution

After wiring and power sequencing, run diagnostic queries:

```bat
trinity-host --port COM3 system-info
trinity-host --port COM3 system-status
```

Expected discovery fields:

```text
protocol_version=1
architecture_version=0.7.1
sn32_build_id=0x00070001
primer1_build_id=0x50310001
primer2_build_id=0x50320001
target_ready_mask includes 0x01 | 0x02 | 0x04
fault_flags=0x00
```

Then run the complete scoped gate:

```bat
trinity-host --port COM3 dual-spi-bringup --timeout 10 --poll 0.1
```

The command executes, in order:

```text
1. PC -> SN32 PING
2. SN32 -> P1 GET_INFO
3. SN32 -> P2 GET_INFO
4. SN32 -> P1 GET_STATUS
5. SN32 -> P2 GET_STATUS
6. SN32 -> P1 retained RUN_SELF_TEST, mask 0x013E
7. SN32 -> P1 GET_TXN_RESULT and RETIRE_TXN_RESULT
8. SN32 -> P2 retained RUN_SELF_TEST, mask 0x03E3
9. SN32 -> P2 GET_TXN_RESULT and RETIRE_TXN_RESULT
10. SN32 -> P1/P2 final GET_STATUS
```

The two self-tests are deliberately separate because P1 and P2 have different
functional masks.

## Acceptance criteria

Every item must pass:

```text
v0.7.1 exact Keil rebuild:               PASS
v0.7.1 SN-LINK program/verify:            PASS
v0.7.1 standalone PC UART PING:           PASS
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

Expected final CLI marker:

```text
[SN32_DUAL_SPI_CONTROL_PLANE]
result=PASS
```

Only then may the scoped statement be recorded:

```text
SN32 -> P1/P2 DUAL-SPI CONTROL PLANE HARDWARE: PASS
```

## Explicit non-claims

Even after this gate passes, retain:

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

Save the following under:

```text
sn32/hardware/dual_spi_control_plane/evidence/
```

Start from:

```text
sn32/hardware/dual_spi_control_plane/evidence/run_manifest_TEMPLATE.txt
```

Required records:

- full exact Keil rebuild log;
- Program Size line and Flash/RAM calculation;
- SN-LINK program/verify log;
- standalone v0.7.1 PING output;
- complete `system-info`, `system-status` and `dual-spi-bringup` output;
- wiring photograph showing all shared bus, CS, IRQ, P2 UART pull-up, ground and
  safety straps;
- source commit, submodule commit and P1/P2 bitstream identities;
- failure notes, even if a later retry passes.

Do not write a PASS record from partial output or only the final CLI line. Audit
the complete command sequence and endpoint identities.
