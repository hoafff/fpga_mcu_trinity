# P1 -> P2 direct UART hardware qualification — 2026-08-03

## Decision

**PASS within the direct Primer #1-to-Primer #2 UART integration scope.**

The physical path

```text
Primer #1 uart_tx_o -> Primer #2 uart_rx_i
```

was exercised on hardware using the ESP32-C3 dual-SPI qualification harness at:

```text
controller_harness_commit = 7fcf9171938114f07fb3e21157abbbc77074720c
```

The accepted terminal result is:

```text
PASS count = 11
FAIL count = 0
OVERALL = PASS
P1 -> P2 direct UART integration: PASS
```

This decision does not qualify SN32, Tiny or the full system.

## Evidence identity

Raw Serial Monitor evidence:

```text
path   = primer2/hardware/p1_to_p2_uart_integration/evidence/serial_monitor_2026-08-03.txt
bytes  = 14172
lines  = 209
sha256 = 1a682823c17fde2ab4ea4664c1acd7f7123139756988ab30d8f457d254a00597
```

The repository copy is LF-normalized so `git diff --check` remains clean. The
original uploaded CRLF byte stream was 14,322 bytes with SHA-256:

```text
f4938a961212c7884fd014e973fe183a5fcca7fbb424c560234eb4c090690216
```

Harness source:

```text
primer2/hardware/p1_to_p2_uart_integration/Primer1ToPrimer2UartIntegration.ino
primer2/hardware/p1_to_p2_uart_integration/P1P2Control.hpp
primer2/hardware/p1_to_p2_uart_integration/P1P2Gate.hpp
```

Existing FPGA implementation identities retained from their separate qualification
records:

```text
Primer #1 qualified source = c8135b5304c0318c7ec24787484dc8a4c4aa0278
Primer #1 bitstream SHA256 = 168459a32fe5545ff77ff5bf590f4b2d84b0fcdd148739324dbba568f8c1f510
Primer #2 qualified source = 7588063e636da225bbe81632efe1060f4c825c37
Primer #2 bitstream SHA256 = NOT RECORDED
```

The missing Primer #2 bitstream hash remains an artifact-traceability limitation.
It does not change the observed hardware result, but a future rebuild or board
replacement must record the exact `.fs` SHA-256 before reusing this evidence as
a cryptographically bound artifact qualification.

## Wiring and controller boundary

The run used one shared SPI bus with independent chip selects and IRQ inputs.
The direct payload net had exactly one transmitter:

```text
P1 R13 uart_tx_o -> P2 R13 uart_rx_i
ESP32-C3 GPIO7   -> passive INPUT/high-impedance monitor tap
```

The ESP32-C3 drove the shared `secure_enable_i` level only after both targets
reported `SESSION_COMMITTED_BLOCKED`. `fatal_latched_i` remained strapped low and
`zeroize_ni` remained strapped high. Therefore this run emulates only the enable
level and does not qualify Tiny safety behavior.

## Full-log audit

The complete log was parsed independently rather than accepting only the final
summary.

```text
complete SPI request packets:   67
complete SPI response packets:  67
request/response pairs:         67
packet magic/version failures:   0
packet length failures:          0
CRC16-CCITT-FALSE failures:      0
command/TXID pairing failures:   0
harness PASS checks:             11
harness FAIL checks:              0
```

The startup IRQ mailboxes were drained before qualification traffic. Primer #1's
drained mailbox decoded as historical `ERR_BAD_LENGTH`. Primer #2 printed only
the first 16 bytes of its stale mailbox, so that startup fragment cannot be
independently CRC-validated from the retained log. Both targets then returned
fresh, CRC-valid `GET_INFO` responses with the expected identity.

Primer #1 retains historical startup diagnostics:

```text
last_error         = 0x0103
diagnostic_summary = 0x00000001
```

These are sticky history from the drained startup mailbox, not a live fault.
Primer #1 remained `SESSION_ACTIVE`, had no pending result and ended with
`irq_no=1`. Primer #2 diagnostics were cleared before the direct-link tests.

## Identity and fail-closed startup

The log proves:

```text
P1 target_id    = 1
P1 protocol     = 1
P1 capabilities = 0x000011FF
P1 build_id     = 0x50310001

P2 target_id    = 2
P2 protocol     = 1
P2 capabilities = 0x00001E0F
P2 build_id     = 0x50320001
```

Both devices initially reported `SESSION_SELF_TEST_REQUIRED`, no active session
and `secure_enable=0`.

## Self-test and provisioning

Retained self-test transactions completed with `TXN_SUCCEEDED` and `ERR_OK`:

```text
P1 self-test mask = 0x013E
P2 self-test mask = 0x03E3
```

Both devices reached `SESSION_READY_NO_SESSION`.

The two `STAGE_SESSION` request payloads were byte-identical:

```text
session_id   = 11223344
key          = 00112233445566778899AABBCCDDEEFF
nonce_prefix = 1021324354657687
```

Both commit transactions completed with `TXN_SUCCEEDED`, `ERR_OK` and zero-length
result data. Both devices first reached `SESSION_COMMITTED_BLOCKED`; only then
was `secure_enable` raised. Both subsequently reported `SESSION_ACTIVE` with
session `0x11223344`. Primer #2 reported receive acceptance enabled and
`last_accepted_sequence=0`.

## Direct payload sequence 1

Primer #1 accepted the 24-byte plaintext, completed `ENCRYPT_AND_SEND`, and
reported:

```text
session_id = 0x11223344
sequence   = 1
bytes_sent = 66
```

Primer #2 reported an authenticated result pending for the same session and
sequence. `READ_AUTH_RESULT` returned:

```text
01 02 03 04 05 06 07 08
09 0A 0B 0C 0D 0E 0F 10
11 12 13 14 15 16 17 00
```

The returned plaintext was byte-exact.

A deliberately wrong ACK used session `0x11223345`. Primer #2 rejected it with:

```text
ERR_BAD_SESSION = 0x0402
```

The authenticated result remained pending and unchanged. The correct ACK then
released it and re-enabled receive acceptance.

## Direct payload sequence 2 and pending-result protection

Primer #1 completed the next UART transaction and reported:

```text
session_id = 0x11223344
sequence   = 2
bytes_sent = 66
```

Primer #2 returned the expected byte-exact plaintext:

```text
A0 A1 A2 A3 A4 A5 A6 A7
A8 A9 AA AB AC AD AE AF
B0 B1 B2 B3 B4 B5 B6 B7
```

While this authenticated result remained pending, Primer #1 transmitted sequence
3. Primer #2 rejected the incoming frame from replacing the protected result:

```text
last_error         = 0x0506
diagnostic_summary = 0x00000080
auth_pending       = 1
last_sequence      = 2
```

A second `READ_AUTH_RESULT` returned the original sequence-2 plaintext exactly.
After the correct ACK, Primer #2 returned to receive acceptance with no pending
authenticated result and `last_accepted_sequence=2`.

The sequence-3 transmission completed at Primer #1, but it was intentionally not
accepted by Primer #2. A new integration run/session is required before treating
sequence 3 as delivered.

## Final observed state

```text
secure_enable = 1
P1 session    = SESSION_ACTIVE
P2 session    = SESSION_ACTIVE
session_id    = 0x11223344
P1 irq_no     = 1
P2 irq_no     = 1
UART idle     = 1
test_aborted  = 0
P2 auth_pending = 0
P2 last_accepted_sequence = 2
```

Primer #2 retained the expected pending-drop diagnostic:

```text
last_error         = ERR_RESULT_PENDING_DROP (0x0506)
diagnostic_summary = DIAG_RESULT_PENDING_DROP (0x00000080)
```

No bad-tag, replay/stale, malformed-frame or fault diagnostic was added by this
run.

## Locked qualification statement

The repository may state exactly:

```text
P1 -> P2 direct UART integration: PASS
p1_to_p2_uart_hardware_qualified = true
```

The following statements remain prohibited:

```text
SN32 integration PASS
Tiny integration PASS
full-system qualification PASS
```

## Scope not newly qualified by this run

This evidence does not newly exercise:

- SN32 control of either Primer;
- Tiny `secure_enable`, fault-latch or zeroize behavior;
- physical assertion of either `fatal_latched_i`;
- physical pulsing of either `zeroize_ni`;
- independent logic-analyzer capture of all 66 UART bits/bytes;
- replay, corrupted-tag or command-zeroize tests over the direct P1 transmitter.

Replay, bad-tag, command-zeroize and fault-threshold behavior remain covered by
the separate Primer #2 standalone hardware qualification; they are not claimed
as newly demonstrated by this direct-link log.

## Next gate

The recommended next separate gate is:

```text
SN32 -> P1/P2 dual-SPI control plane
```

It should replace the ESP32-C3 provisioning/result controller while retaining
the now-qualified direct P1-to-P2 UART payload connection. Tiny safety integration
and full-system qualification remain later independent gates.
