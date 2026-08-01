# FPGA MCU Trinity — SPI Control Plane ICD

**Status:** `ASSUMED — FINAL OWNER REVIEW REQUIRED`  
**Version:** `v0.1`  
**Date:** `2026-08-01`  
**Applies to:** SN32↔Primer #1 and SN32↔Primer #2

Header/transaction/size rules are confirmed by D16–D22. Byte-exact command
payloads, success/error envelope details and numeric error assignments below are
engineering details derived to complete the ICD and are tracked by O-013.

## 1. Electrical/transaction contract

- SPI Mode 0, MSB-first.
- Shared SCK/MOSI/MISO; CS/IRQ separate per target.
- Bring-up 1 MHz; measured qualification before increasing toward 5 MHz.
- Never assert both CS simultaneously.
- Deselect target MISO must be high-Z.
- One request per CS assertion; response is a later separate CS assertion.
- IRQ active-low level.

## 2. Packet

```text
offset  size  field
0       1     MAGIC = A5
1       1     VERSION = 01
2       1     COMMAND
3       1     FLAGS
4       2     TRANSACTION_ID, big-endian
6       2     PAYLOAD_LENGTH, big-endian, payload bytes only
8       N     PAYLOAD
8+N     2     CRC16/CCITT-FALSE, big-endian
```

CRC parameters: poly `0x1021`, init `0xFFFF`, refin false, refout false, xorout `0x0000`.
CRC covers header[0..7] + payload and excludes CRC field.

Flags:

```text
bit0 RESPONSE
bit1 ERROR
bit2 MORE
bit3 EVENT
bit4..7 reserved = 0
```

Any reserved flag set → `BAD_FLAGS`.

Limits:

```text
maximum polynomial data chunk = 64 B
maximum polynomial payload    = 66 B
maximum whole packet          = 8 + 66 + 2 = 76 B
```

## 3. Response/error rule — O-013 review item

- Success response: same COMMAND, `RESPONSE=1`, `ERROR=0`, command-specific payload.
- Error response: same COMMAND, `RESPONSE=1`, `ERROR=1`, payload:

```text
offset  size  field
0       2     ERROR_CODE, big-endian
2       1     SESSION_STATE
3       1     OPERATION_STATE
4       2     DETAIL, big-endian; 0 when unused
```

- Malformed header with no trustworthy command/txid may be dropped and reflected
  by diagnostic counter rather than generating a response.

## 4. Command registry

```text
0x01 GET_INFO
0x02 GET_STATUS
0x03 RUN_SELF_TEST
0x04 GET_TXN_RESULT
0x05 RETIRE_TXN_RESULT
0x06 ZEROIZE
0x07 STAGE_SESSION
0x08 COMMIT_SESSION
0x09 ABORT_SESSION

P1:
0x20 POLY_BEGIN
0x21 POLY_WRITE_CHUNK
0x22 POLY_EXECUTE
0x23 POLY_READ_CHUNK
0x24 POLY_RETIRE
0x30 LOAD_TELEMETRY
0x31 ENCRYPT_AND_SEND

P2:
0x40 GET_RX_STATUS
0x41 READ_AUTH_RESULT
0x42 ACK_AUTH_RESULT
0x43 CLEAR_DIAGNOSTIC_COUNTERS
```

## 5. Common command payloads — O-013 review item

### 0x01 GET_INFO

Request: empty.

Success response, 12 bytes:

```text
0 target_id: 1=P1, 2=P2
1 protocol_version=1
2..5 capability_bits u32 BE
6..9 build_id u32 BE
10..11 reserved=0
```

### 0x02 GET_STATUS

Request: empty.

Success response, 16 bytes:

```text
0 session_state
1 operation_state
2 pending_flags: bit0 mailbox, bit1 side_effect_result, bit2 authenticated_result
3 secure_flags: bit0 self_test_pass, bit1 session_staged, bit2 secure_enable,
                bit3 zeroize_busy, bit4 fault_locked
4..7 session_id u32 BE; 0 if none
8..9 last_error u16 BE
10..11 active_transaction_id u16 BE; 0 if none
12..15 diagnostic_summary u32 BE
```

### 0x03 RUN_SELF_TEST

Request, 4 bytes: `test_mask u16 BE || reserved u16=0`.

Success mailbox response: empty. Final result is retained and read via
`GET_TXN_RESULT`.

### 0x04 GET_TXN_RESULT

Request, 2 bytes: queried transaction ID u16 BE.

Success response, 10+N bytes:

```text
0..1 queried_txid
2 transaction_state
3 original_command
4..5 result_code u16 BE
6..7 result_length N u16 BE
8..9 reserved=0
10.. result_data[N]
```

### 0x05 RETIRE_TXN_RESULT

Request: transaction ID u16 BE. Success response empty. This command is
retry-safe and does not create a retained side-effect record.

### 0x06 ZEROIZE

Request, 4 bytes: `scope u8 || reserved[3]=0`; baseline scope `0xFF` means all.
Success mailbox response empty; retained final result is `ZEROIZED`.

### 0x07 STAGE_SESSION

Request, 28 bytes:

```text
0..3 session_id u32 BE
4..19 ascon_key[16]
20..27 nonce_prefix[8]
```

Same session ID + byte-identical context is retry-safe.

### 0x08 COMMIT_SESSION

Request: session_id u32 BE. Final result retained.

### 0x09 ABORT_SESSION

Request: session_id u32 BE; zero means current session. Retry-safe.

## 6. Polynomial commands

Slot IDs: A=`0`, B=`1`. Chunk index must be 0..7. Each chunk contains 32
coefficients serialized uint16 little-endian and canonical `0..3328`.

Operations: NTT=`1`, INTT=`2`, BASEMUL=`3`.

### 0x20 POLY_BEGIN

Request, 4 bytes:

```text
0 operation
1 slot_mask: bit0 A, bit1 B
2 expected_chunks_per_slot = 8
3 reserved=0
```

Required slot mask: NTT/INTT=`0x01`, BASEMUL=`0x03`.

### 0x21 POLY_WRITE_CHUNK

Request exactly 66 bytes:

```text
0 slot_id
1 chunk_index
2..65 data[64]
```

Retry same slot/index/data is safe. Same slot/index with different data →
`CHUNK_CONFLICT`. Index outside 0..7 → `BAD_CHUNK_INDEX`.

### 0x22 POLY_EXECUTE

Request, 2 bytes: `operation || reserved=0`. Reject if required chunks incomplete.
Final result retained. Same txid is reconciled, not executed twice.

### 0x23 POLY_READ_CHUNK

Request, 2 bytes: `slot_id || chunk_index`.

Success response exactly 66 bytes: `slot_id || chunk_index || data[64]`.
Reject before result-ready with `RESULT_NOT_READY`.

### 0x24 POLY_RETIRE

Request, 2 bytes: `slot_mask || reserved=0`. Retry-safe; clear selected polynomial
valid/result state. Does not create a retained side-effect record.

### Operation flow

NTT/INTT:

```text
POLY_BEGIN
-> 8 x WRITE A
-> EXECUTE
-> IRQ/result
-> 8 x READ A
-> POLY_RETIRE
```

BASEMUL:

```text
POLY_BEGIN
-> 8 x WRITE A
-> 8 x WRITE B
-> EXECUTE
-> IRQ/result
-> 8 x READ A
-> POLY_RETIRE
```

BaseMul result overwrites slot A.

## 7. P1 telemetry commands

### 0x30 LOAD_TELEMETRY

Request, 32 bytes:

```text
0 message_type
1 reserved=0
2..3 AD flags u16 BE
4..5 source_id u16 BE
6..7 reserved=0
8..31 plaintext[24]
```

Byte-identical retry is safe while telemetry is loaded and not sent.

### 0x31 ENCRYPT_AND_SEND

Request empty. Uses current session/sequence and loaded telemetry. Same txid is
reconciled, never executed twice. Final result data:

```text
session_id u32 BE || sequence u64 BE || bytes_sent u16 BE
```

Sequence advances only after full 66-byte frame transmission completes.

## 8. P2 result commands

### 0x40 GET_RX_STATUS

Request empty. Response, 16 bytes:

```text
0 rx_state
1 result_valid
2 rx_ready
3 consecutive_bad_tag_count
4..7 session_id u32 BE
8..15 last_accepted_sequence u64 BE
```

### 0x41 READ_AUTH_RESULT

Request empty. Success response, 38 bytes:

```text
0..3 session_id u32 BE
4..11 sequence u64 BE
12..35 plaintext[24]
36..37 authentication_status u16 BE
```

### 0x42 ACK_AUTH_RESULT

Request, 12 bytes: `session_id u32 BE || sequence u64 BE`. Repeated ACK for the
same already-cleared result succeeds idempotently.

### 0x43 CLEAR_DIAGNOSTIC_COUNTERS

Request: counter mask u32 BE. Retry-safe.

## 9. Retry classification

Retry-safe/idempotent:

```text
GET_INFO GET_STATUS GET_TXN_RESULT RETIRE_TXN_RESULT POLY_READ_CHUNK
READ_AUTH_RESULT LOAD_TELEMETRY(byte-identical, unsent)
POLY_WRITE_CHUNK(same slot/index/data) STAGE_SESSION(byte-identical)
ABORT_SESSION ZEROIZE POLY_RETIRE ACK_AUTH_RESULT CLEAR_DIAGNOSTIC_COUNTERS
```

No blind retry with a new transaction ID:

```text
RUN_SELF_TEST COMMIT_SESSION POLY_EXECUTE ENCRYPT_AND_SEND
```

## 10. Request fingerprint

```text
CRC32C(command || flags || payload_length_be16 || payload)
```

Store with transaction ID. Same ID/different fingerprint → `TRANSACTION_CONFLICT`.

## 11. IRQ sources

```text
response_mailbox_pending
side_effect_result_valid
authenticated_result_valid
```

IRQ remains low while any source is pending. Reading the mailbox clears only the
mailbox. `RETIRE_TXN_RESULT` clears retained side-effect result.
`ACK_AUTH_RESULT` clears authenticated result.

## 12. Initial timeout defaults

| Operation | Timeout |
|---|---:|
| status/read | 100 ms |
| NTT/INTT/BaseMul | 500 ms |
| self-test | 2 s |
| zeroize | 500 ms |
| Ascon/frame path | 500 ms |

On timeout SN32 performs one status/reconciliation read before reset/abort policy.

## 13. Numeric error table — O-013 review item

```text
0000 OK
0101 BAD_MAGIC
0102 BAD_VERSION
0103 BAD_LENGTH
0104 BAD_CRC
0105 BAD_FLAGS
0201 BAD_COMMAND
0202 BAD_STATE
0203 BUSY
0204 RESULT_PENDING
0205 TRANSACTION_CONFLICT
0206 OUTCOME_UNKNOWN_TARGET_RESET
0301 BAD_CHUNK_INDEX
0302 CHUNK_CONFLICT
0303 INCOMPLETE_INPUT
0304 RESULT_NOT_READY
0305 SELF_TEST_FAILED
0306 MLKEM_SHARED_SECRET_MISMATCH
0401 SESSION_ID_COLLISION
0402 BAD_SESSION
0403 ZEROIZED
0501 REPLAY
0502 STALE_SEQUENCE
0503 BAD_TAG
0504 MALFORMED_FRAME
0505 FRAME_TIMEOUT
0506 RESULT_PENDING_DROP
0601 AUTH_THRESHOLD
0602 COMMIT_REJECTED
0603 SESSION_COMMIT_FAILED
0604 HEARTBEAT_TIMEOUT
0605 FAULT_LOCKED
0701 INTERNAL_FAULT
0702 NOT_SUPPORTED
```
