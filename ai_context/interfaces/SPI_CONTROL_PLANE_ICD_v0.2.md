# FPGA MCU Trinity — SPI Control Plane ICD

**Status:** `CORRECTIVE IMPLEMENTATION BASELINE`  
**Version:** `v0.2`  
**Supersedes:** transport-direction and IRQ semantics in `SPI_CONTROL_PLANE_ICD_v0.1.md`

All packet fields, command values, error values, payload limits, CRC parameters,
Mode-0 timing polarity, shared SCK/MOSI/MISO wiring and separate CS/IRQ wiring
remain unchanged unless this document states otherwise.

## 1. Response-mailbox IRQ contract

`IRQ_N` is an active-low transport signal.

```text
IRQ_N = LOW  if and only if a complete response mailbox is ready to clock out
IRQ_N = HIGH when no response mailbox bytes are available
```

Persistent application state must not assert `IRQ_N` directly. In particular:

```text
retained side-effect result present   != response mailbox pending
authenticated telemetry result present != response mailbox pending
```

Those states remain observable through `GET_STATUS.PENDING_FLAGS` and through
their explicit query/read commands. They do not block the master from opening a
new request window after the preceding response mailbox has been consumed.

## 2. Retained transaction flow

A retained side-effect operation uses the following sequence:

```text
RUN/START command
  -> immediate response mailbox
  -> master reads the complete mailbox; IRQ_N returns HIGH
  -> master polls GET_TXN_RESULT(original_txid)
  -> terminal result SUCCEEDED / FAILED / ZEROIZED
  -> master sends RETIRE_TXN_RESULT(original_txid)
```

`GET_TXN_RESULT` and `RETIRE_TXN_RESULT` are valid request windows while a
retained result exists. Their transmission does not require `IRQ_N` to be LOW.

## 3. Primer #2 authenticated-result flow

Authenticated plaintext remains protected in Primer #2 until explicitly read
and acknowledged:

```text
master polls GET_RX_STATUS or GET_STATUS
  -> AUTHENTICATED_RESULT pending is reported in status
  -> master sends READ_AUTH_RESULT
  -> master sends ACK_AUTH_RESULT
```

`authenticated_result_pending` does not assert `IRQ_N` by itself.

## 4. Request qualification and silent discard

When no response mailbox is pending, a CS assertion is a request candidate.
The first complete received byte qualifies that candidate:

```text
first byte = 0xA5  -> receive and validate a request packet
first byte != 0xA5 -> silently discard the entire CS window
no complete byte   -> silently discard the entire CS window
```

A silently discarded window:

- does not emit `BAD_MAGIC` or `BAD_LENGTH`;
- does not create a response mailbox;
- does not assert `IRQ_N`;
- does not alter retained or authenticated application state.

Once `0xA5` has qualified a request, malformed version, flags, length or CRC are
reported through the normal protocol error response mailbox.

This rule prevents stale/dummy response-read clocks from being interpreted as a
new malformed request and creating a self-sustaining mailbox/IRQ loop.

## 5. Response window

If a complete response mailbox is pending at CS assertion, the endpoint enters
response-transmit mode and starts at mailbox byte zero. The mailbox is consumed
only after the complete mailbox bit length has been clocked. A partial read does
not authorize a new request in that same CS window.

The master must read exactly one complete response mailbox per asserted IRQ. If
`IRQ_N` remains LOW after a complete, CRC-valid mailbox read and the documented
settle interval, the master reports a transport/protocol fault instead of
opening unbounded dummy-read windows.

## 6. Clock stretching

The SPI slave has no intra-frame timeout while CS remains asserted. The master
may stretch the SCK-low phase for an arbitrary finite interval, including while
servicing PC UART ingress. SCK must be LOW whenever the master suspends progress
inside a transaction.

Any future addition of an SPI frame timeout requires a new evidence-backed ICD
revision and must preserve the qualified UART-service latency budget.

## 7. Electrical deselection

When `CS_N = HIGH`, each Primer MISO output is high-impedance. The implementation
constraints explicitly set `PULL_MODE=NONE` on both Primer MISO pins so the
shared line does not depend on a tool default.

## 8. Corrective build identities

The first source images implementing this contract use:

```text
Primer #1 build ID = 0x5031D003
Primer #2 build ID = 0x50320002
```

These source changes are not hardware-qualified merely by being committed.
Both Primers require exact-device synthesis, place-and-route, STA, bitstream
hash recording, reprogramming and the retained lifecycle hardware gate before
any control-plane PASS claim.
