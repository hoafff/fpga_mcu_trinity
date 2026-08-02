# Primer #1 to Primer #2 UART integration — next hardware gate

The standalone ESP32-C3 qualification proves Primer #2 receive/decrypt behavior,
but it does not prove the direct Primer #1 transmitter path. The next gate must
replace the ESP32 UART injector with Primer #1 `uart_tx_o` while preserving a
separate control path for provisioning and result inspection.

## Qualification boundary before this gate

Accepted before starting:

```text
Primer #1 exact-device qualification:                 existing qualified scope
Primer #2 exact-device build candidate:               PASS
Primer #2 ESP32-C3 standalone qualification:          PASS
P1 -> P2 direct UART integration:                     NOT RUN
SN32 -> P2 control plane:                             NOT RUN
Tiny safety integration:                              NOT RUN
```

No result from this procedure may be labeled full-system qualification unless
SN32 and Tiny are also present and exercised under their own acceptance gates.

## Physical payload connection

Connect only the direct one-way payload path:

```text
Primer #1 uart_tx_o  -> Primer #2 uart_rx_i
common GND           -> common GND
```

Both pins must use the locked 3.3 V LVCMOS deployment mapping. Remove or place in
high impedance the ESP32 GPIO7 UART output before connecting Primer #1. Never
allow two transmitters to drive Primer #2 `uart_rx_i`.

## Locked UART and frame contract

```text
UART:             115200 baud, 8 data bits, no parity, 1 stop bit
Inter-frame idle: at least 1 ms
Frame length:     66 bytes
Frame:            A5 5A || AD[24] || ciphertext[24] || tag[16]
```

Primer #1 and Primer #2 must use identical values for:

```text
session_id
Ascon key
nonce_prefix
sequence
AD layout and byte ordering
ciphertext/tag byte ordering
```

The first accepted sequence after a new commit is `1`. Every later accepted
frame advances contiguously by one. Replay, zero, stale and forward-gap sequence
values must remain fail-closed.

For deterministic bring-up, the already qualified standalone vector may be used:

```text
session_id  = 0x11223344
key         = 00112233445566778899AABBCCDDEEFF
nonce_prefix= 1021324354657687
first_seq   = 1
```

These constants are test material only. They do not establish production key
management.

## Required provisioning sequence

With `secure_enable` low:

1. confirm Primer #1 and Primer #2 identify the expected target/build;
2. run and reconcile self-test on both targets;
3. stage the same session ID, key and nonce prefix on both;
4. read status from both and confirm `SESSION_STAGED` with the same session ID;
5. commit Primer #1 and Primer #2;
6. reconcile retained commit results;
7. confirm both targets are `SESSION_COMMITTED_BLOCKED`;
8. raise the controlled `secure_enable` level;
9. confirm both targets enter `SESSION_ACTIVE`;
10. only then command Primer #1 to transmit sequence 1.

For this scoped gate, the ESP32-C3 may remain as an SPI controller and temporary
secure-enable source, but it must not drive the payload UART pin. Such a result
qualifies only the P1-to-P2 payload integration, not SN32 or Tiny integration.

## Positive-path acceptance

Record evidence that:

1. Primer #1 reports successful frame construction/transmission for sequence 1;
2. Primer #2 reports authenticated result pending;
3. Primer #2 reports the same session ID and sequence 1;
4. `READ_AUTH_RESULT` returns the expected 24-byte plaintext exactly;
5. a wrong ACK is rejected without releasing the result;
6. the correct ACK releases the result;
7. sequence 2 is transmitted and authenticated successfully;
8. no UART framing, timeout, result-drop or authentication diagnostic is set on
   the clean positive path.

Capture the exact 66 transmitted bytes using a logic analyzer or independent UART
monitor where possible. The captured bytes must match the Primer #1 frame record
and the Primer #2 interpretation.

## Negative-path acceptance

After a new clean session, demonstrate without weakening RTL:

- replay of an already accepted frame is rejected;
- a deliberately corrupted tag does not expose plaintext;
- a pending authenticated result is not overwritten;
- session abort or command zeroize clears both targets and requires a new session.

The three-bad-tag destructive threshold need not be repeated in the first direct
link run because it is already proven on Primer #2 standalone hardware, but it
must eventually be covered in integrated safety testing.

## Evidence to retain

Record:

```text
P1 source commit and bitstream SHA-256
P2 source commit and bitstream SHA-256
controller/harness source commit
pin wiring and board identities
P1 and P2 GET_INFO responses
staged and active session status from both targets
captured 66-byte frame(s)
P2 authenticated plaintext result
negative-path error/status records
final git status and qualification scope
```

Only after these checks may the repository state be updated to:

```text
P1 -> P2 direct UART integration: PASS
```

The following remain separate gates:

```text
SN32 -> P2 control plane
Tiny safety integration
full-system hardware qualification
```
