# FPGA MCU Trinity — PC↔SN32 Protocol ICD

**Status:** `ASSUMED — FINAL OWNER REVIEW REQUIRED`  
**Version:** `v0.1`  
**Date:** `2026-08-01`

Frame, registry and timeout decisions are confirmed by D45–D52. Derived
per-command payloads and event envelope are tracked by O-014.

## 1. Transport

- UART 115200 8N1.
- Raw frame below is COBS-encoded and terminated by one `0x00` delimiter.
- Raw payload max 256 bytes.

```text
offset  size  field
0       1     VERSION = 01
1       1     COMMAND
2       1     FLAGS
3       1     RESERVED = 00
4       2     TRANSACTION_ID, big-endian
6       2     PAYLOAD_LENGTH, big-endian
8       N     PAYLOAD
8+N     2     CRC16/CCITT-FALSE, big-endian
```

CRC covers raw bytes from VERSION through payload and excludes CRC field.
Reserved header byte and reserved flag bits must be zero.

Flags:

```text
bit0 RESPONSE
bit1 ERROR
bit2 MORE
bit3 EVENT
bit4..7 reserved=0
```

## 2. Response/error rule — O-014 review item

Success: same command, RESPONSE=1, ERROR=0, command-specific payload.

Error payload:

```text
error_code u16 BE
system_state u8
source u8
related_target_txid u16 BE
```

## 3. Command registry

```text
01 PING
02 GET_SYSTEM_INFO
03 GET_SYSTEM_STATUS
04 GET_LAST_ERROR
05 GET_TXN_RESULT
06 RETIRE_TXN_RESULT

10 RUN_SELF_TEST
11 GENERATE_KEYPAIR
12 CREATE_SESSION
13 CLOSE_SESSION
14 ZEROIZE_SYSTEM

20 SEND_ONE_TELEMETRY
21 RUN_DEMO
22 READ_LAST_RESULT

30 RUN_NTT_TEST
31 RUN_ASCON_TEST
32 RUN_BENCHMARK
33 RUN_TRANSPORT_STRESS

40 INJECT_TEST_FAULT
41 REQUEST_FAULT_CLEAR

E0 EVENT
```

## 4. Core query commands — O-014 review item

### 0x01 PING

Request empty. Response: `uptime_ms u32 BE`.

### 0x02 GET_SYSTEM_INFO

Request empty. Response, 20 bytes:

```text
0 protocol_version
1 architecture_version_major=0
2 architecture_version_minor=4
3 reserved=0
4..7 capability_bits u32 BE
8..11 sn32_build_id u32 BE
12..15 primer1_build_id u32 BE
16..19 primer2_build_id u32 BE
```

### 0x03 GET_SYSTEM_STATUS

Request empty. Response, 20 bytes:

```text
0 system_state
1 mode
2 target_ready_mask
3 fault_flags
4..7 session_id u32 BE
8..15 current_sequence u64 BE
16..17 last_error u16 BE
18..19 active_host_txid u16 BE
```

### 0x04 GET_LAST_ERROR

Request empty. Response:

```text
error_code u16 BE || source u8 || reserved u8 || detail u32 BE
```

### 0x05 GET_TXN_RESULT

Request: host transaction ID u16 BE.
Response:

```text
queried_txid u16 BE
transaction_state u8
original_command u8
result_code u16 BE
result_length u16 BE
result_data[result_length]
```

### 0x06 RETIRE_TXN_RESULT

Request: host transaction ID u16 BE. Response empty. Retry-safe and does not
create a retained transaction record.

## 5. Lifecycle commands

### 0x10 RUN_SELF_TEST

Request, 4 bytes:

```text
target_mask u8
test_profile u8
test_mask u16 BE
```

Target mask: bit0 SN32, bit1 P1, bit2 P2, bit3 Tiny.

### 0x11 GENERATE_KEYPAIR

Request, 33 bytes:

```text
mode u8: 0=normal, 1=deterministic/KAT
seed[32]: zero when mode=0; fixed/test seed when mode=1
```

Seed must not be logged by default.

### 0x12 CREATE_SESSION

Request, 33 bytes:

```text
mode u8: 0=normal deterministic-demo source policy, 1=explicit deterministic seed,
         2=DEMO_SECURE (currently NOT_SUPPORTED)
seed[32]: used only for mode=1; otherwise all zero
```

Response after success:

```text
session_id u32 BE || starting_sequence u64 BE
```

### 0x13 CLOSE_SESSION

Request empty. Idempotently aborts/zeroizes current session context but does not
regenerate keypair.

### 0x14 ZEROIZE_SYSTEM

Request: scope u8; baseline `FF` all transient/key/session state.

## 6. Demo commands

### 0x20 SEND_ONE_TELEMETRY

Request, 32 bytes:

```text
0 message_type
1 reserved=0
2..3 AD flags u16 BE
4..5 source_id u16 BE
6..7 reserved=0
8..31 plaintext[24]
```

Response after readback:

```text
session_id u32 BE || sequence u64 BE || plaintext[24] || result_code u16 BE
```

### 0x21 RUN_DEMO

Request, 40 bytes:

```text
0 mode: 0=deterministic, 1=secure (NOT_SUPPORTED until O-002)
1 reserved=0
2..3 frame_count u16 BE; default 64
4..5 source_id u16 BE
6..7 AD flags u16 BE
8..39 seed[32]; used only deterministic mode
```

Long operation emits progress events and one final response.

### 0x22 READ_LAST_RESULT

Request empty. Response is the same authenticated result structure as
SEND_ONE_TELEMETRY response.

## 7. Diagnostic commands

### 0x30 RUN_NTT_TEST

Request: `profile u8 || reserved u8 || iterations u16 BE`.

### 0x31 RUN_ASCON_TEST

Request: `profile u8 || reserved u8 || iterations u16 BE`.

### 0x32 RUN_BENCHMARK

Request, 8 bytes:

```text
target_mask u8
reserved u8
operation_mask u16 BE
iterations u32 BE
```

### 0x33 RUN_TRANSPORT_STRESS

Request, 8 bytes:

```text
link_id u8: 1=PC-UART, 2=SPI-P1, 3=SPI-P2, 4=P1-P2-UART
reserved[3]=0
transaction_count u32 BE
```

## 8. Fault commands

### 0x40 INJECT_TEST_FAULT

Request, 4 bytes: `fault_id u16 BE || target u8 || reserved=0`.
Only accepted in KAT/DIAGNOSTIC mode.

### 0x41 REQUEST_FAULT_CLEAR

Request empty. Means trusted recovery authorization, not unconditional clear.

## 9. EVENT frame — O-014 review item

Command `E0`, flags EVENT=1 and transaction ID 0.

Payload:

```text
0..1 event_type u16 BE
2 severity: 0=info,1=warning,2=error,3=fatal
3 source: 0=SN32,1=P1,2=P2,3=Tiny,4=host-protocol
4..5 related_transaction_id u16 BE; 0 when none
6 progress_percent 0..100; FF when not a progress event
7 reserved=0
8.. event_data
```

Event may interleave between request and final response. It never replaces the
final response.

## 10. Timeout classes

| Commands | Timeout |
|---|---:|
| PING, GET_*, READ_LAST_RESULT | 500 ms |
| SEND_ONE_TELEMETRY, RUN_NTT_TEST, RUN_ASCON_TEST | 2 s |
| RUN_SELF_TEST | 5 s |
| GENERATE_KEYPAIR, CREATE_SESSION, CLOSE_SESSION, ZEROIZE_SYSTEM | 20 s |
| RUN_DEMO, RUN_BENCHMARK, RUN_TRANSPORT_STRESS | 120 s or progress events |

After timeout, PC may retry at most twice only for retry-safe commands or query
`GET_TXN_RESULT`. It must not issue a new transaction ID for an uncertain
non-idempotent operation.

## 11. Disconnect/reconnect

- SN32 finishes the currently running safe operation.
- SN32 starts no new operation automatically.
- Last host-side transaction result is retained.
- Reconnected PC queries system status and transaction result.
- Demo loop does not resume without a new command.

## 12. Host implementation

- Python 3.11+.
- `pyserial`, `argparse`, standard `json`.
- No GUI in first implementation.
- JSON may contain timestamps, versions, session ID, sequence, test IDs, cycle
  counts, status/error and hashes of public test values.
- JSON must not contain private/decapsulation key, shared secret, Ascon key,
  sensitive seed or raw KDF output.
