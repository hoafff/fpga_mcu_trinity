# Primer #1 BAD_LENGTH diagnostic build

Date: 2026-08-04

## Scope

This image is a temporary Primer #1 diagnostic build for the SN32 dual-SPI hardware gate. It preserves the complete Primer #1 datapath and control plane, including NTT, INTT, BaseMul, Ascon encryption, UART transmit, retained transactions, session handling, heartbeat, fault handling, and zeroization.

Primer #2 and SN32 are unchanged.

## Diagnostic identity

```text
Primer #1 build_id = 0x5031D001
```

The diagnostic build ID must appear in `trinity-host system-info` before interpreting a test result.

## BAD_LENGTH detail encoding

Only a Primer #1 transport-generated `BAD_LENGTH` response uses the diagnostic detail format:

```text
detail[15:9] = transaction_byte_count seen by Primer #1
detail[8]    = 1 when the sampled payload-length high byte is nonzero
detail[7:0]  = sampled payload-length low byte
```

When fewer than eight request bytes were captured, `detail[7:0]` is `0xFF` because the payload-length field was incomplete.

Examples:

```text
detail=0x1200 -> count=9,  payload_length=0
detail=0x1400 -> count=10, payload_length=0
detail=0x1401 -> count=10, payload_length=1
detail=0x1500 -> count=10, payload-length high byte was nonzero
```

Decode formulas:

```text
count               = (detail >> 9) & 0x7F
length_high_nonzero = (detail >> 8) & 0x01
length_low          = detail & 0xFF
```

## Build and hardware procedure

1. Pull the locked `main` commit reported with this diagnostic source.
2. Open the existing Primer #1 Gowin project.
3. Run full synthesis, place-and-route, timing analysis, and bitstream generation for the exact device.
4. Require synthesis and place-and-route PASS. Any RTL edit invalidates the previous exact-device timing evidence.
5. Program only Primer #1 with the newly generated `.fs` file.
6. Leave Primer #2 on its existing qualified bitstream and leave SN32 on v0.7.17 (`0x00070011`).
7. Reset SN32 after Primer #1 and Primer #2 are running.
8. Run:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 system-info
trinity-host --port COM3 spi-diag --target p1 --command get-status
```

Expected identity:

```text
sn32_build_id=0x00070011
primer1_build_id=0x5031D001
primer2_build_id=0x50320001
```

## Interpretation

For the six-byte error payload:

```text
error_code | session_state | operation_state | detail
```

read the final two payload bytes as `detail`.

```text
count=9, length=0
    Primer #1 missed the final request byte before CS rose.

count=10, length!=0
    Primer #1 sampled the payload-length field incorrectly, or the error came from the command core with a nonzero sampled length.

count!=10, length=0
    Primer #1 counted an incorrect number of SPI bytes.

count=10, length=0 and BAD_LENGTH persists
    Investigate whether the error originated in the command core rather than the transport length check.
```

This diagnostic source does not constitute a hardware PASS. The normal Primer #1 build identity remains `0x50310001`; the diagnostic image must not be recorded as the final production bitstream.
