# Primer #2 authenticated receive target

Primer #2 is the fail-closed receive side of the direct encrypted link from
Primer #1. The committed deployment source targets `GW2A-LV18PG256C8/I7` with
top-level `primer2_top` at 27 MHz.

## Implemented path

```text
P1 UART TX (115200 8N1)
  -> P2 UART byte receiver
  -> fixed 66-byte frame receiver
  -> AD/session/sequence validation
  -> sequential Ascon-AEAD128 decrypt and 128-bit tag verification
  -> quarantined plaintext
  -> one retained authenticated result
  -> controller SPI READ_AUTH_RESULT / ACK_AUTH_RESULT
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

Session lifecycle:

```text
SELF_TEST_REQUIRED -> READY_NO_SESSION -> STAGED
-> COMMITTED_BLOCKED -> ACTIVE
```

`secure_enable_i` is required to enter `ACTIVE`. Zeroize, fatal latch, or loss
of secure enable while active takes priority and prevents automatic recovery.

## Current evidence

Qualification source:

```text
7588063e636da225bbe81632efe1060f4c825c37
```

Current post-fix status:

```text
reference checks:                              PASS
static RTL checks:                             PASS
exact-device synthesis/PnR/timing/bitstream:   PASS CANDIDATE
standalone ESP32-C3 hardware qualification:    PASS, 23 checks / 0 failures
P1 -> P2 direct UART integration:              NOT RUN
SN32 -> P2 control plane:                      NOT RUN
Tiny safety integration:                       NOT RUN
full-system hardware qualification:            NOT RUN
```

The exact-device rebuild removed warning `EX2664`, met 27 MHz with 41.700 MHz
reported Fmax, +13.056 ns setup slack and +0.425 ns hold slack, and generated a
new `.fs`. `LW = 8/8` remains an accepted routing-capacity risk because there are
no reported unrouted nets, only one clock domain and positive timing margin.
The bitstream SHA-256 was not supplied.

The ESP32-C3 fixture proved the physical SPI control path, 66-byte UART receive,
Ascon decrypt/authentication, byte-exact plaintext, session/replay rules,
command zeroize, re-provisioning and the three-bad-tag fault/zeroize threshold.
The final expected state was `SESSION_FAULT_LOCKED` with
`ERR_AUTH_THRESHOLD`.

The fixture did not physically assert `fatal_latched_i` or pulse `zeroize_ni`;
those pins were strapped low and high respectively. Command `ZEROIZE_ALL` was
exercised, but it is not a substitute for the external zeroize-pin test.

## Official standalone harness

```text
hardware/esp32c3_standalone_qualification/
```

The harness drives `spi_cs_ni` high before controller startup, drains a stale
startup response mailbox if IRQ is already low, and keeps the UART-injection pin
high impedance until `GET_INFO` proves the connected target is Primer #2.

## Next gate

The next scoped qualification is the direct payload connection:

```text
Primer #1 uart_tx_o -> Primer #2 uart_rx_i
```

Both targets must be staged and committed with identical session ID, Ascon key,
nonce prefix and contiguous sequence contract before Primer #1 transmits.
See `docs/P1_TO_P2_UART_INTEGRATION_NEXT_GATE.md`.

Detailed records:

- `README_BUILD.md`;
- `docs/VERIFICATION_STATUS.md`;
- `docs/EXACT_DEVICE_BUILD_AUDIT_2026-08-02.md` for superseded pre-fix evidence;
- `docs/STANDALONE_HARDWARE_QUALIFICATION_2026-08-03.md`;
- `hardware/esp32c3_standalone_qualification/README.md`.

`standalone_hardware_qualified` is true only for the recorded ESP32-C3 fixture
scope. Generic/full-system `hardware_qualified` remains false.
