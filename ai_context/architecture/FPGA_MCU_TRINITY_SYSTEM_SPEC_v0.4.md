# FPGA MCU Trinity — System Specification

**Document status:** `APPROVED IMPLEMENTATION DECISIONS — CONSOLIDATED BASELINE`  
**Implementation status:** `DOCUMENT REVIEW REQUIRED / SOURCE NOT STARTED`  
**Version:** `v0.4`  
**Date:** `2026-08-01`  
**Repository target:** `hoafff/fpga_mcu_trinity`  
**Project-memory entrypoint:** `ai_context/README_AI.md`

Tài liệu này hợp nhất architecture baseline v0.3 với các quyết định D01–D60 đã
được chủ dự án phê duyệt. Chưa được bắt đầu full integrated source cho tới khi
bản hợp nhất v0.4 và các ICD đi kèm được chủ dự án kiểm tra không còn mâu thuẫn.

---

## 1. Authority and source-of-truth

Thứ tự ưu tiên:

1. Quyết định mới nhất của chủ dự án đã commit trên `main`.
2. System Specification và Decision Register hiện hành.
3. ICD/backend specification hiện hành được Decision Register dẫn chiếu.
4. Schematic, pinout, datasheet, SDK và tool documentation đúng revision.
5. Source cùng executable evidence đúng scope.
6. Exact-device build và đo phần cứng.

Không có thẩm quyền kiến trúc:

- repository hỏng/tham khảo `fpga-pqc-secure-telemetry`;
- tài liệu AI chưa được phê duyệt;
- Git history hoặc nội dung dưới `ai_context/migration/`;
- tài liệu cũ `Trinity_Spec_V2_1_DaKiemTra` và
  `Trinity_Spec_V2_TrienKhai_1Tuan`.

Quyết định mới hơn ghi đè nội dung cũ mâu thuẫn. Không tự biến `OPEN`,
`BUILD-PENDING` hoặc `PHYSICAL-PENDING` thành `CONFIRMED`/`TESTED`.

---

## 2. Mục tiêu và kiến trúc hệ thống

```text
CONTROL PLANE
PC <---- UART/COBS ----> SN32F407F
                            |
                            | shared SPI Mode 0, MSB-first
                            | CS/IRQ riêng từng Primer
                            +------> Primer #1
                            +------> Primer #2

PAYLOAD PLANE
Primer #1 ==================================> Primer #2
             UART một chiều trực tiếp

SECURITY PLANE
SN32 heartbeat -------------------+
P1 heartbeat/fault ---------------+----> Tiny 1P5
P2 heartbeat/crypto-fault --------+
Tiny secure-enable/zeroize -------+----> P1/P2
```

Ràng buộc:

- PC không giao tiếp trực tiếp với FPGA.
- Payload mã hóa P1→P2 không đi vòng qua SN32, PC hoặc Tiny.
- Plaintext readback P2→SN32 chỉ là control-plane result phục vụ demo/verification.
- ML-KEM ciphertext và shared secret không đi qua payload plane.
- Tiny không nhận, lưu, mã hóa hoặc giải mã payload.

---

## 3. Phần cứng và project identity

| Thành phần | Thiết bị | Clock | Project/top đã chốt |
|---|---|---:|---|
| PC host | Windows/Linux PC | — | Python host |
| SN32 | SONiX SN32F407F | 12 MHz | project `trinity_sn32f407` |
| Primer #1 | GW2A-LV18PG256C8/I7 | 27 MHz | project `trinity_primer1`, top `primer1_top` |
| Primer #2 | GW2A-LV18PG256C8/I7 | 27 MHz | project `trinity_primer2`, top `primer2_top` |
| Tiny 1P5 | GW1N-UV1P5QN48XC7/I6 | 27 MHz | project `trinity_tiny1p5`, top `supervisor_top` |

Exact toolchain versions vẫn `OPEN` tại O-012 và phải được ghi trong
`ai_context/toolchains/TOOLCHAIN_LOCK.md` trước khi bắt đầu target implementation.

---

## 4. Chế độ vận hành

- `KAT`: seed/vector cố định; test context riêng; không tạo production session.
- `DEMO_DETERMINISTIC`: PC cấp seed để tái lập; không được gọi là secure entropy.
- `DEMO_SECURE`: enum/API tồn tại nhưng trả `NOT_SUPPORTED` đến khi O-002 đóng.
- `DIAGNOSTIC`: self-test, primitive tests, benchmark và transport stress.

Không log private key, decapsulation key, shared secret, Ascon key, raw KDF output
hoặc seed nhạy cảm trong JSON mặc định.

---

## 5. ML-KEM-512 lifecycle và upstream pin

### 5.1 Lifecycle

- SN32 điều phối toàn bộ ML-KEM-512 lifecycle.
- KeyGen chạy một lần sau cold boot; cho phép regenerate theo lệnh.
- Reset session thông thường không chạy lại KeyGen.
- Power loss, watchdog reset, fault recovery hoặc reset không tin cậy phải chạy lại
  KeyGen và thiết lập session mới.
- Không lưu private/decapsulation key vào flash trong competition baseline.
- Trước KeyGen mới phải zeroize key pair/session state cũ nếu còn tồn tại.
- Encaps và Decaps chạy trên SN32 cho mỗi session.
- Shared secret hai phía được so sánh constant-time. Nếu khác nhau:

```text
abort session
-> zeroize key/session intermediates
-> MLKEM_SHARED_SECRET_MISMATCH
```

Không retry Decaps với cùng ciphertext như lỗi transport.

### 5.2 Normative source and exact pin

```text
algorithm_standard       = NIST FIPS 203 final + current recorded errata/potential updates
upstream_repository      = https://github.com/pq-code-package/mlkem-native
release_tag              = v1.0.0
exact_commit_sha         = 048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa
license                  = Apache-2.0 OR MIT OR ISC
date_verified            = 2026-08-01
FIPS_203_errata_revision = fips-203-potential-updates.xlsx;
                            CSRC planning note 2025-11-17;
                            verified 2026-08-01
```

Không theo floating `main`. FIPS-202 implementation ban đầu và reference lấy từ
upstream đã pin. Nếu exact Keil build không phù hợp Flash/RAM, phải mở amendment
riêng; không tự trộn SHA3/SHAKE implementation khác.

### 5.3 FPGA acceleration

Primer #1 chỉ tăng tốc:

- NTT;
- INTT;
- MultiplyNTTs/BaseCaseMultiply.

SN32 truyền polynomial qua SPI và nhận kết quả. Backend mapping được khóa tại:

```text
ai_context/interfaces/MLKEM_BACKEND_SPEC_v0.1.md
```

Các tham số:

- `n = 256`;
- `q = 3329`;
- wire coefficient: uint16 little-endian, canonical `0..q-1`;
- không truyền Montgomery representation qua SPI;
- semantic ordering/domain theo exact upstream operation:
  - NTT input và INTT output: normal order;
  - NTT output, INTT input và BaseMul input/output: upstream bit-reversed NTT order;
- không dùng custom NTT order trong baseline đầu tiên.

### 5.4 Polynomial storage

- NTT/INTT: logical in-place slot A, chia hai bank BSRAM.
- BaseMul: input slots A và B; result ghi đè slot A.
- Không mặc định full result slot thứ ba.
- Chỉ thêm result slot nếu access schedule hoặc exact build chứng minh cần.
- Không infer polynomial memory bằng DFF.
- Một operation tại một thời điểm.

---

## 6. KDF byte-exact và session identity

```text
CT_HASH = SHA3-256(mlkem_ciphertext[768])

KDF_INPUT =
    ASCII("TRINITY-KDF-v1")
    || 0x00
    || shared_secret[32]
    || CT_HASH[32]

KDF_OUTPUT = SHAKE256(KDF_INPUT, 28)

out[0..15]  = ascon_key[16]
out[16..23] = nonce_prefix[8]
out[24..27] = session_id_bytes[4]
```

- Domain string là 14 ASCII byte `TRINITY-KDF-v1`, theo sau bởi `0x00`.
- `session_id_bytes` diễn giải big-endian khi đưa lên wire.
- Nếu session ID trùng session active hoặc session ngay trước:
  - zeroize KDF output vừa tạo;
  - chạy Encaps/KDF lại;
  - tối đa ba lần;
  - vẫn trùng → `SESSION_ID_COLLISION`.
- Quy tắc collision production không áp dụng cho KAT fixed context; KAT không được
  kích hoạt production session.
- Verification: ba fixed vectors (normal, all-zero input class, all-`0xFF` input
  class) và random differential tests.

Session:

- sequence uint64, bắt đầu từ 1;
- nonce = `nonce_prefix[8] || sequence_be64[8]`;
- tuyệt đối không reuse nonce dưới cùng key;
- 64 frame/session là demo/acceptance default, không phải protocol maximum;
- session mới bắt buộc sau fault, recovery, state loss hoặc nonce-risk.

---

## 7. Self-test, session commit và Tiny

### 7.1 Boot gate

```text
BOOT
-> SELF_TEST_REQUIRED
-> RUN_SELF_TEST
-> READY_NO_SESSION
-> SESSION_STAGED
-> COMMITTED_BLOCKED
-> ACTIVE
```

Self-test bắt buộc trước session đầu tiên sau reset/reconfiguration.

### 7.2 Commit sequence

```text
P1/P2 self-test PASS
-> stage cùng session context
-> verify staged status
-> COMMIT_SESSION P1
-> COMMIT_SESSION P2
-> verify cả hai COMMITTED_BLOCKED
-> SN32 toggle SESSION_COMMIT
-> Tiny kiểm tra heartbeat/fault qualification
-> Tiny assert SECURE_ENABLE
-> P1/P2 chuyển ACTIVE
-> SN32 poll xác nhận cả hai ACTIVE
```

- `SESSION_COMMIT` dùng toggle event, không pulse ngắn và không cần ACK pin riêng.
- Sau reset, Tiny lấy mức toggle hiện tại làm baseline; không coi mức tồn tại là event.
- Tiny reset làm `SECURE_ENABLE=0` và vô hiệu session hiện tại.
- SN32 chỉ đảo toggle sau self-test, stage mới và heartbeat qualification.
- Heartbeat phải khỏe liên tục ≥500 ms **trước commit**.
- Nếu chưa đủ qualification khi nhận toggle: latch `COMMIT_REJECTED`, giữ secure
  disabled; không tự chờ rồi kích hoạt event cũ.
- Nếu một Primer commit thất bại: không toggle Tiny; abort+zeroize cả hai target;
  SN32 xóa shared secret/KDF material và báo `SESSION_COMMIT_FAILED`.
- SN32 xác nhận Tiny chấp nhận bằng cách poll P1/P2 đến khi cả hai thấy
  `SECURE_ENABLE` và báo `ACTIVE`.

### 7.3 Heartbeat/recovery

- Heartbeat toggle nominal 100 ms.
- Timeout 350 ms.
- Startup grace 1000 ms.
- Recovery cần trusted/manual clear và session mới; không auto-resume.

Physical pins, polarity, pull, voltage và final route vẫn O-008
`PHYSICAL-PENDING`.

---

## 8. Zeroize

- Zeroize ưu tiên cao hơn operation mật mã.
- Operation đang chạy bị hủy.
- Crypto command mới bị từ chối trong lúc zeroize.
- Xóa active/staged key, key pair/session intermediates, shared secret, KDF output,
  nonce prefix, plaintext quarantine và temporary secret state.
- BSRAM được ghi đè tuần tự; không giả định clear một chu kỳ.
- Expose `zeroize_busy`, `zeroize_done`.
- Sau zeroize phải self-test/session establishment lại theo nguyên nhân reset/fault.

Transaction behavior:

- giữ một result `ZEROIZED` đủ để SN32 reconcile;
- clear sau ACK/retire;
- hardware reset xóa transaction record, về `SELF_TEST_REQUIRED`;
- SN32 đánh dấu outstanding transaction là `OUTCOME_UNKNOWN_TARGET_RESET`;
- không dùng boot epoch khi chưa có nguồn epoch cụ thể.

---

## 9. SPI control plane

Normative byte-level contract:

```text
ai_context/interfaces/SPI_CONTROL_PLANE_ICD_v0.1.md
```

Tóm tắt:

- shared SPI Mode 0, MSB-first;
- bring-up 1 MHz, sau evidence tăng dần tới 5 MHz;
- CS/IRQ riêng; không assert hai CS đồng thời;
- MISO high-Z khi deselected;
- request/response là hai CS transaction riêng;
- header 8 byte, transaction ID 16 bit, CRC-16/CCITT-FALSE;
- polynomial data chunk 64 byte;
- polynomial command payload 66 byte;
- maximum whole packet 76 byte;
- flags reserved phải 0; bit lạ → `BAD_FLAGS`;
- exact command payloads trong ICD v0.1 hiện được đánh dấu `ASSUMED` và theo dõi
  tại O-013 cho vòng review cuối.

---

## 10. Transaction reconciliation và IRQ

Mỗi target giữ đúng một retained side-effect record:

```text
transaction_id
command
flags
payload_length
request_fingerprint_crc32c
last_transaction_state
last_transaction_result
last_transaction_error
last_transaction_valid
```

```text
request_fingerprint_crc32c =
    CRC32C(command || flags || payload_length || payload)
```

CRC32C chỉ là operational fingerprint.

- Cùng transaction ID + cùng fingerprint: trả retained result, không chạy lại.
- Cùng ID + khác fingerprint: `TRANSACTION_CONFLICT`.
- Record giữ đến `RETIRE_TXN_RESULT`, reset hoặc zeroize rule tương ứng.
- Transaction chưa reconcile chặn side-effect mới bằng `BUSY`/`RESULT_PENDING`.
- `RETIRE_TXN_RESULT` không tự tạo retained result mới.

Ba nguồn pending tách biệt:

```text
response_mailbox_pending
side_effect_result_valid
authenticated_result_valid
```

IRQ active-low khi ít nhất một nguồn pending. Chỉ deassert khi toàn bộ nguồn đã
được clear/retire/ACK đúng command.

---

## 11. PC↔SN32 protocol và host

Normative contract:

```text
ai_context/interfaces/PC_SN32_PROTOCOL_ICD_v0.1.md
```

- UART 115200 8N1.
- Raw binary frame → COBS encode → delimiter `0x00`.
- CRC-16/CCITT-FALSE.
- Transaction ID 16 bit.
- Payload max 256 byte.
- Async event dùng command `0xE0`, transaction ID 0.
- Retry tối đa hai lần, chỉ retry-safe/idempotent command.
- Long operation phát progress event; progress không thay response cuối.
- Mất PC connection: SN32 hoàn tất operation an toàn đang chạy, không tự tạo
  operation mới, giữ result để reconnect/reconcile.
- Host vòng đầu: Python 3.11+, `pyserial`, `argparse`, standard `json`; không GUI.
- Exact command payloads/event envelope trong ICD v0.1 hiện `ASSUMED`, theo dõi
  tại O-014 cho vòng review cuối.

Initial timeout defaults:

| Class | Timeout |
|---|---:|
| ping/status/read | 500 ms |
| target primitive | 2 s |
| self-test | 5 s |
| KeyGen/Encaps/Decaps/session | 20 s |
| stress/benchmark | 120 s hoặc progress events |

Timeout có thể tăng/giảm bằng amendment có benchmark evidence; không tự tăng vô hạn.

---

## 12. Telemetry, AD và Ascon

### 12.1 Plaintext 24 byte — big-endian

| Offset | Size | Field | Type | Constraint |
|---:|---:|---|---|---|
| 0 | 4 | `timestamp_ms` | uint32 | big-endian |
| 4 | 2 | `sensor_id` | uint16 | big-endian |
| 6 | 2 | `flags` | uint16 | big-endian |
| 8 | 4 | `temperature_mC` | int32 | big-endian |
| 12 | 4 | `humidity_milli_percent` | uint32 | big-endian |
| 16 | 4 | `sample_counter` | uint32 | big-endian |
| 20 | 4 | `reserved` | uint32 | phải bằng 0 |

### 12.2 AD 24 byte — big-endian

| Offset | Size | Field | Type | Constraint |
|---:|---:|---|---|---|
| 0 | 1 | `version` | uint8 | protocol version |
| 1 | 1 | `message_type` | uint8 | telemetry type |
| 2 | 2 | `flags` | uint16 | big-endian |
| 4 | 4 | `session_id` | uint32 | big-endian |
| 8 | 8 | `sequence` | uint64 | big-endian |
| 16 | 2 | `payload_len` | uint16 | phải bằng 24 |
| 18 | 2 | `source_id` | uint16 | big-endian |
| 20 | 4 | `reserved` | uint32 | phải bằng 0 |

### 12.3 Ascon-AEAD128

- NIST SP 800-232.
- P1 encrypt-only; P2 decrypt + tag verify.
- key 16 B; nonce 16 B; AD 24 B; plaintext/ciphertext 24 B; tag 16 B.
- Tag compare toàn bộ, không early-exit.
- Plaintext quarantine đủ 24 B; chỉ release sau tag PASS.

---

## 13. UART payload frame và receiver behavior

```text
SYNC[2] || AD[24] || CIPHERTEXT[24] || TAG[16] = 66 byte
SYNC = A5 5A
```

- UART 115200 8N1.
- Không CRC payload-plane; Ascon tag bảo vệ AD+ciphertext.
- Inter-byte timeout 20 ms.
- Minimum inter-frame idle gap 1 ms, do P1 TX FSM tạo bằng `INTERFRAME_IDLE`.
- Chỉ tìm sync trong `HUNT_SYNC`; sync trong body không resync.
- UART framing/parity/overrun error: drop body, clear index, tăng counter, về
  `HUNT_SYNC`, không tăng bad-tag counter.
- Khi authenticated result cũ chưa consume, P2 không arm frame mới;
  `RESULT_PENDING_DROP` tăng tối đa một lần cho mỗi attempted frame/sync candidate.

Baseline flow:

```text
P2 RX_READY && !result_valid
-> P1 LOAD_TELEMETRY
-> P1 ENCRYPT_AND_SEND
-> frame + idle >= 1 ms
-> P2 verify/result
-> SN32 read + ACK
-> frame tiếp theo
```

---

## 14. Replay, authentication và P2 result buffer

Processing order:

1. receive full frame;
2. check version/session/structure;
3. check sequence candidate;
4. verify Ascon tag;
5. only after PASS: release plaintext and update `last_accepted_sequence`.

- Accept sequence strictly greater than last accepted; gaps allowed.
- Three consecutive framing-valid bad tags → crypto fault.
- Accepted valid frame resets consecutive bad-tag counter.
- Malformed/timeout không tính bad tag.

Single-entry authenticated result buffer:

```text
result_valid
session_id
sequence
plaintext[24]
authentication_status/result
```

- Không overwrite result chưa ACK.
- `READ_AUTH_RESULT` đọc qua SPI.
- `ACK_AUTH_RESULT` clear buffer; repeated ACK cùng session/sequence phải an toàn.
- ACK, zeroize, fault hoặc đổi session clear buffer.

---

## 15. Target state machines

Session state:

```text
BOOT
SELF_TEST_REQUIRED
SELF_TEST_RUNNING
READY_NO_SESSION
SESSION_STAGED
COMMITTED_BLOCKED
ACTIVE
ZEROIZE_BUSY
FAULT_LOCKED
```

P1 operation state:

```text
IDLE
LOAD_INPUT
READY_TO_EXECUTE
EXECUTING
RESULT_READY
```

P2 RX state:

```text
HUNT_SYNC
RECEIVE_BODY
VALIDATE
VERIFY_TAG
RESULT_PENDING
```

---

## 16. Error-code domains

| Range | Domain |
|---|---|
| `0x0000` | OK |
| `0x01xx` | transport/framing/CRC |
| `0x02xx` | command/transaction/state |
| `0x03xx` | ML-KEM/NTT accelerator |
| `0x04xx` | session/KDF/key lifecycle |
| `0x05xx` | Ascon/telemetry/replay |
| `0x06xx` | supervisor/fault/zeroize |
| `0x07xx` | diagnostics/internal |

Minimum symbolic errors include:

```text
BAD_MAGIC BAD_VERSION BAD_LENGTH BAD_CRC BAD_FLAGS BAD_COMMAND BAD_STATE
BUSY RESULT_PENDING TRANSACTION_CONFLICT BAD_CHUNK_INDEX CHUNK_CONFLICT
INCOMPLETE_INPUT RESULT_NOT_READY ZEROIZED SELF_TEST_FAILED
SESSION_ID_COLLISION MLKEM_SHARED_SECRET_MISMATCH OUTCOME_UNKNOWN_TARGET_RESET
BAD_SESSION REPLAY STALE_SEQUENCE BAD_TAG MALFORMED_FRAME FRAME_TIMEOUT
RESULT_PENDING_DROP AUTH_THRESHOLD COMMIT_REJECTED SESSION_COMMIT_FAILED
INTERNAL_FAULT NOT_SUPPORTED
```

Numeric assignments in SPI ICD v0.1 are `ASSUMED` until O-013 closes.

---

## 17. RTL, memory and build policy

- Chỉ dùng 27 MHz board clock trên FPGA baseline.
- Không tạo generated clock bằng logic; dùng clock enable.
- External reset synchronize-deassert.
- Security state có fail-safe default.
- UART/heartbeat tick dùng counter/enable.
- Cho phép BSRAM/DSP/PLL IP khi cần và project tái lập.
- Commit wrapper/config cần thiết; không commit generated build output.
- SN32 không dùng `malloc`; static buffers/stack được kiểm soát.

Đánh giá riêng LUT, FF, BSRAM, DSP, I/O, clock resources, WNS, TNS, hold và
routing congestion:

- mục tiêu ≤75%;
- 75–85% review;
- 85–90% chỉ khi có lý do và margin;
- >90% reject;
- mọi kết luận hiện tại `BUILD-PENDING` O-009.

---

## 18. Toolchain, artifacts và CI

### 18.1 Toolchain

O-012 yêu cầu khóa chính xác:

```text
Gowin EDA version/build
Gowin Programmer version
Keil µVision version
ARM Compiler version
SONiX DFP/SDK version
Python version
Icarus Verilog version
GCC version
```

Không tự nâng toolchain giữa baseline và acceptance.

### 18.2 Artifacts

Không commit `.fs`, `.hex`, `.axf` vào `main`. Acceptance artifacts nằm trong
GitHub Release/artifact archive cùng report, tool version, commit SHA và SHA-256.

### 18.3 CI

Cho phép `.github/workflows/` làm ngoại lệ root policy. CI chỉ được chạy portable
checks như Python, layout/hash checker, GCC reference tests, Icarus simulation và
format/static checks. CI không được tuyên bố Gowin/Keil exact build hoặc hardware PASS.

---

## 19. Verification requirements

- ML-KEM official/reference KAT và integration vectors.
- NTT/INTT: 100 random vectors + zero, all `q-1`, impulse, alternating,
  reduction boundaries, `INTT(NTT(a))=a`, coefficient-by-coefficient compare.
- Ascon: 100 random packets + AD/cipher/tag bit flips, wrong nonce/key/session,
  replay, truncation, timeout, no plaintext release on tag failure.
- SPI stress: 10,000 transactions.
- UART stress: 1,000 frames.
- End-to-end: 10 sessions, 64 frames/session default, no reprogram between sessions.
- Exact build evidence: Gowin synthesis/P&R/timing/utilization/final I/O; Keil
  map/size; tool versions and commit SHA.

---

## 20. Repository placement

Only target deployment source/project:

```text
pc_host/ sn32/ primer1/ primer2/ tiny1p5/
```

Everything else:

```text
ai_context/
```

Golden/reference model:

```text
ai_context/verification/reference/
```

`.github/workflows/` is the only approved non-target/non-`ai_context` directory
exception and may contain CI YAML only.

---

## 21. Open items and implementation gate

### 21.1 Closed by v0.4 decisions

| ID | Closure |
|---|---|
| O-001 | KDF byte-exact locked in §6 |
| O-003 | mlkem-native v1.0.0 exact pin locked in §5.2 |
| O-004 | SPI header/transaction-ID/CRC/max-size locked in SPI ICD |
| O-005 | SESSION_COMMIT toggle mechanism locked in §7 |
| O-006 | UART minimum idle gap = 1 ms |
| O-011 | Initial PC timeout classes locked in §11 |

### 21.2 Remaining

| ID | Status | Scope |
|---|---|---|
| O-002 | `OPEN` | secure entropy/DRBG; blocks `DEMO_SECURE` claim only |
| O-008 | `PHYSICAL-PENDING` | pins/polarity/pulls/voltage/final constraints |
| O-009 | `BUILD-PENDING` | exact-device utilization/timing/hardware evidence |
| O-012 | `OPEN` | exact toolchain versions; blocks target implementation start |
| O-013 | `OPEN` | review SPI command payloads/error numeric assignments in ICD v0.1 |
| O-014 | `OPEN` | review PC command payloads/event envelope in ICD v0.1 |
| O-015 | `OPEN` | review mlkem-native BaseMul wrapper/error-latch mapping |

### 21.3 Gate

Không bắt đầu full integrated source cho tới khi:

1. chủ dự án kiểm tra v0.4 + ba interface/backend documents;
2. O-012, O-013, O-014 và O-015 được đóng;
3. source work được giao theo target/gate rõ ràng.

O-008 không chặn core logic/logical ports nhưng chặn final CST/pin mapping và
programming. O-009 chỉ đóng sau exact build. O-002 không chặn KAT hoặc deterministic demo.
