# Primer #2 deployment architecture

```text
UART RX synchronizer/8N1 decoder
  -> 66-byte frame receiver (A5 5A + 64-byte body)
  -> structural/session/sequence validation
  -> sequential shared Ascon-AEAD128 decrypt datapath
  -> 24-byte plaintext quarantine
  -> single authenticated-result buffer
  -> SPI READ_AUTH_RESULT / ACK_AUTH_RESULT
```

The SPI path reuses the same packet endpoint and registry as Primer #1. Three
independent IRQ sources are preserved: response mailbox, retained side-effect
result and authenticated result.

## Security ordering

1. Receive the complete body without resynchronizing inside it.
2. Validate AD version, message type, payload length, reserved bytes, active
   session and sequence candidate.
3. Reconstruct `nonce_prefix || sequence_be64`.
4. Decrypt into an internal candidate register and compare the complete 128-bit
   tag.
5. Only on tag PASS copy plaintext into the retained authenticated-result buffer
   and commit `last_accepted_sequence`.
6. On the next cycle scrub the complete Ascon working state while preserving only
   the retained authenticated result until SN32 acknowledges it.

Bad tag, replay, stale sequence, malformed frame, UART timeout and UART framing
error never create an authenticated result. Zeroize/abort clears both the Ascon
state and command-core shadow registers. Fatal input enters FAULT_LOCKED and does
not auto-resume.

## Sequence contract

The first accepted sequence is exactly `1`. Later accepted frames must be exactly
`last_accepted_sequence + 1`; equality is replay, a lower value is stale, and a
forward gap is rejected fail-closed. Sequence state advances only after the full
128-bit tag has passed.
