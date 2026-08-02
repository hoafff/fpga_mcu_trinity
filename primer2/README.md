# Primer #2 authenticated receive target

Primer #2 is the fail-closed receive side of the direct encrypted link from
Primer #1. The committed deployment source is self-contained and targets
`GW2A-LV18PG256C8/I7` with top-level `primer2_top` at 27 MHz.

## Implemented path

```text
P1 UART TX (115200 8N1)
  -> P2 UART byte receiver
  -> fixed 66-byte frame receiver
  -> AD/session/sequence validation
  -> sequential Ascon-AEAD128 decrypt and 128-bit tag verification
  -> quarantined plaintext
  -> one retained authenticated result
  -> SN32 SPI READ_AUTH_RESULT / ACK_AUTH_RESULT
```

The fixed frame is:

```text
A5 5A || AD[24] || CIPHERTEXT[24] || TAG[16]
```

The receiver does not search for sync inside a frame body. It implements a
20 ms inter-byte timeout, a 1 ms inter-frame idle gate, UART framing-error drop,
and one pending-result drop report per blocked receive attempt window.

## Control plane

Primer #2 uses the common Mode-0, MSB-first SPI packet endpoint with CRC-16,
response mailbox, retained side-effect result, transaction fingerprinting and
conflict detection.

| Command | Value | Purpose |
|---|---:|---|
| `GET_INFO` | `0x01` | Target/build/capability information |
| `GET_STATUS` | `0x02` | Session, operation, RX and diagnostic status |
| `RUN_SELF_TEST` | `0x03` | Retained self-test transaction |
| `GET_TXN_RESULT` | `0x04` | Reconcile retained side-effect result |
| `RETIRE_TXN_RESULT` | `0x05` | Retire the retained result |
| `ZEROIZE` | `0x06` | Selective or full zeroize |
| `STAGE_SESSION` | `0x07` | Stage session ID, key and nonce prefix |
| `COMMIT_SESSION` | `0x08` | Commit staged session, initially blocked |
| `ABORT_SESSION` | `0x09` | Abort and scrub session material |
| `GET_RX_STATUS` | `0x40` | Receive/auth-result status and counters |
| `READ_AUTH_RESULT` | `0x41` | Read the retained authenticated result |
| `ACK_AUTH_RESULT` | `0x42` | Acknowledge and release the result buffer |
| `CLEAR_DIAGNOSTIC_COUNTERS` | `0x43` | Clear selected diagnostics |

Session lifecycle is:

```text
SELF_TEST_REQUIRED -> READY_NO_SESSION -> STAGED
-> COMMITTED_BLOCKED -> ACTIVE
```

`secure_enable_i` is required to enter `ACTIVE`. Zeroize, fatal latch, or loss
of secure enable while active takes priority and prevents automatic recovery.

## Verification status

Completed in the execution environment:

- source-policy/static RTL checks: PASS;
- byte-exact P1-compatible reference frame and Ascon checks: PASS;
- official NIST SP 800-232 Count 817 compatibility check: PASS;
- AD/ciphertext/tag bit-flip rejection in the reference model: PASS;
- wrong-key and wrong-nonce rejection in the reference model: PASS.

Not executed here because the required tools are absent:

- seven self-checking SystemVerilog simulations (`iverilog`/`vvp` unavailable);
- Gowin synthesis, place-and-route, STA and `.fs` generation;
- physical SRAM programming and P1-to-P2 hardware qualification.

See `README_BUILD.md` and `docs/VERIFICATION_STATUS.md` for exact commands and
the acceptance boundary. No exact-device or hardware PASS is claimed yet.
