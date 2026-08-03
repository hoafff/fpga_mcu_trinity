# Primer #1 to Primer #2 direct UART integration — hardware-qualified gate

Status date: 2026-08-03

## Locked result

```text
P1 -> P2 direct UART integration: PASS
p1_to_p2_uart_hardware_qualified = true
controller_harness_commit = 7fcf9171938114f07fb3e21157abbbc77074720c
```

The accepted raw log and detailed audit are preserved at:

```text
primer2/hardware/p1_to_p2_uart_integration/evidence/serial_monitor_2026-08-03.txt
primer2/docs/P1_TO_P2_UART_HARDWARE_QUALIFICATION_2026-08-03.md
```

This gate qualifies only the physical direct payload path. It does not qualify
SN32, Tiny or the full system.

## Qualification boundary

Accepted state after this run:

```text
Primer #1 scoped exact-device hardware qualification: PASS
Primer #2 exact-device build candidate:               PASS
Primer #2 ESP32-C3 standalone qualification:          PASS
P1 -> P2 direct UART integration:                     PASS
SN32 -> P1/P2 control plane:                          NOT RUN
Tiny safety integration:                              NOT RUN
full-system hardware qualification:                   NOT RUN
```

## Locked physical connection

```text
Primer #1 R13 uart_tx_o -> Primer #2 R13 uart_rx_i
common GND              -> common GND
```

Both pins use the locked 3.3 V LVCMOS deployment mapping.

The ESP32-C3 was the shared SPI controller and temporary secure-enable source.
Its GPIO7 remained `INPUT`/high-impedance for the entire run and acted only as a
passive UART-level monitor. Primer #1 was the sole driver of Primer #2
`uart_rx_i`.

## Locked UART and frame contract

```text
UART:             115200 baud, 8 data bits, no parity, 1 stop bit
Inter-frame idle: at least 1 ms
Frame length:     66 bytes
Frame:            A5 5A || AD[24] || ciphertext[24] || tag[16]
```

The qualified run used:

```text
session_id   = 0x11223344
key          = 00112233445566778899AABBCCDDEEFF
nonce_prefix = 1021324354657687
```

These constants are test material only and do not define production key
management.

## Qualified provisioning sequence

With `secure_enable` low, the harness:

1. identified P1 as target 1/build `0x50310001`;
2. identified P2 as target 2/build `0x50320001`;
3. confirmed both targets were initially fail-closed;
4. completed and retired self-test transactions on both targets;
5. confirmed both reached `SESSION_READY_NO_SESSION`;
6. sent byte-identical `STAGE_SESSION` material to both targets;
7. confirmed both reached `SESSION_STAGED`;
8. committed both targets and reconciled retained results;
9. confirmed both reached `SESSION_COMMITTED_BLOCKED`;
10. raised the shared controlled `secure_enable` level;
11. confirmed both reached `SESSION_ACTIVE`;
12. confirmed P2 receive acceptance was enabled before P1 sequence 1.

## Qualified positive and protection paths

The hardware run demonstrated:

- P1 encrypt and 66-byte UART transmission for sequence 1;
- P2 authentication/decryption and byte-exact plaintext sequence 1;
- wrong ACK rejection with `ERR_BAD_SESSION = 0x0402`;
- preservation of the pending sequence-1 result after wrong ACK;
- correct ACK release;
- P1 encrypt and 66-byte UART transmission for sequence 2;
- P2 authentication/decryption and byte-exact plaintext sequence 2;
- sequence 3 arriving while sequence 2 was pending;
- `ERR_RESULT_PENDING_DROP = 0x0506`;
- `DIAG_RESULT_PENDING_DROP = 0x00000080`;
- preservation and reread of the exact sequence-2 plaintext;
- correct final ACK release and UART idle.

The independent packet audit found 67 request/response pairs and no CRC, length,
command or transaction-ID mismatch.

## Recorded result

```text
PASS count = 11
FAIL count = 0
OVERALL = PASS
P1 -> P2 direct UART integration: PASS
```

Final observed state:

```text
secure_enable = 1
P1_irq_n      = 1
P2_irq_n      = 1
UART idle     = 1
aborted       = 0
```

## Evidence limitations

The run did not include an independent logic-analyzer dump of every UART byte.
Primer #1 nevertheless reported `bytes_sent=66` for each completed transmit, and
Primer #2 authenticated the expected session, sequence and plaintext over the
physical P1-to-P2 net.

The direct-link log did not repeat replay, corrupted-tag, command-zeroize or
fault-threshold testing. Those remain covered by the separate Primer #2
standalone qualification and are not claimed as newly tested here.

Primer #2's exact `.fs` SHA-256 was not recorded in the pre-existing build
evidence. This is retained as an artifact-traceability limitation.

## Locked scope language

Permitted:

```text
P1 -> P2 direct UART integration: PASS
```

Not permitted:

```text
SN32 integration PASS
Tiny integration PASS
full-system qualification PASS
```

## Next separate gate

```text
SN32 -> P1/P2 dual-SPI control plane
```

Do not implement or claim this next gate until it has its own approved harness
and hardware evidence.
