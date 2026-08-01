# FPGA MCU Trinity — Decision Register

**Document status:** `APPROVED ARCHITECTURE BASELINE`  
**Implementation status:** `OPEN ITEMS REMAIN`  
**Version:** `v0.3`  
**Date:** `2026-08-01`  
**Baseline use:** Được phép đưa vào `main` làm nguồn kiến trúc và quản lý yêu cầu.  
**Implementation restriction:** Không được tự triển khai hoặc tự khóa phần phụ thuộc open item chưa được phê duyệt.

---

## 1. Authority

- Quyết định mới nhất của chủ dự án có ưu tiên cao nhất.
- Repo `fpga-pqc-secure-telemetry` không phải source of truth.
- Tài liệu AI chưa được kiểm chứng không có thẩm quyền.
- `Trinity_Spec_V2_1_DaKiemTra` và `Trinity_Spec_V2_TrienKhai_1Tuan` chỉ là tham khảo lịch sử.
- Không được chuyển `OPEN`, `BUILD-PENDING` hoặc `PHYSICAL-PENDING` thành `CONFIRMED/PASS` khi chưa có phê duyệt/evidence.

---

## 2. Q01–Q100 decisions

| ID | Status | Decision |
|---|---|---|
| Q01 | `CONFIRMED` | Demo end-to-end: ML-KEM session → P1 encrypt → direct UART → P2 verify/decrypt → PC display. |
| Q02 | `CONFIRMED` | KeyGen một lần sau cold boot; regenerate theo yêu cầu; Encaps/Decaps trên SN32 mỗi session; key pair không persistent qua power cycle. |
| Q03 | `CONFIRMED` | Hỗ trợ telemetry giả lập và ADC/cảm biến; giả lập là baseline tái lập. |
| Q04 | `CONFIRMED` | 64 frame/session là cấu hình demo/acceptance mặc định, không phải protocol maximum. |
| Q05 | `CONFIRMED` | 10 session liên tiếp cho acceptance. |
| Q06 | `CONFIRMED` | PC khởi tạo session; SN32 kiểm tra precondition. |
| Q07 | `CONFIRMED` | Modes: KAT, DEMO_DETERMINISTIC, DEMO_SECURE, DIAGNOSTIC. |
| Q08 | `CONFIRMED` | CLI chính; GUI tối giản chỉ sau core system. |
| Q09 | `CONFIRMED` | Windows và Linux; acceptance ưu tiên Windows. |
| Q10 | `CONFIRMED` | Console + JSON evidence; không log secret mặc định. |
| Q11 | `CONFIRMED` | PC–SN32 binary command; log người dùng dạng text. |
| Q12 | `CONFIRMED` | COBS framing, delimiter `0x00`. |
| Q13 | `CONFIRMED` | PC–SN32 CRC-16/CCITT-FALSE. |
| Q14 | `CONFIRMED` | PC–SN32 max payload 256 byte. |
| Q15 | `CONFIRMED` | Header PC–SN32 có version, command, flags, transaction ID, length. |
| Q16 | `CONFIRMED` | PC transaction ID 16 bit. |
| Q17 | `CONFIRMED` | Dùng timeout theo command class; exact per-command values được theo dõi tại O-011. |
| Q18 | `CONFIRMED` | Retry tối đa 2 lần, chỉ command idempotent. |
| Q19 | `CONFIRMED` | Mỗi target giữ đúng một last side-effect transaction/state/result/error/valid đến ACK/retire; duplicate cùng request trả cached result, request khác cùng ID trả conflict. |
| Q20 | `CONFIRMED` | Async event dùng cùng UART với frame type `EVENT`. |
| Q21 | `CONFIRMED` | SPI dùng packet command/response. |
| Q22 | `CONFIRMED` | P1/P2 dùng chung header/status/error; command target-specific. |
| Q23 | `CONFIRMED` | SPI chunk tối đa 64 byte. |
| Q24 | `CONFIRMED` | SPI header cố định 8 byte; exact byte layout và transaction-ID width được theo dõi tại O-004. |
| Q25 | `CONFIRMED` | SPI CRC-16. |
| Q26 | `CONFIRMED` | Request và response là hai CS transaction riêng. |
| Q27 | `CONFIRMED` | IRQ active-low level, giữ đến read/ack. |
| Q28 | `CONFIRMED` | Không dùng BUSY pin riêng; dùng status+IRQ. |
| Q29 | `CONFIRMED` | MISO high-Z khi `CS_N=1`. |
| Q30 | `CONFIRMED` | Không blind retry side-effect; `GET_STATUS/GET_TXN_RESULT` idempotent; transaction chưa reconcile chặn side-effect mới bằng BUSY/RESULT_PENDING. |
| Q31 | `CONFIRMED` | Chứng minh KeyGen + Encaps + Decaps đầy đủ. |
| Q32 | `CONFIRMED` | P1 offload NTT, INTT, MultiplyNTTs/BaseCaseMultiply. |
| Q33 | `CONFIRMED` | Một polynomial 256 hệ số mỗi command. |
| Q34 | `CONFIRMED` | Polynomial SPI serialization: 256 × uint16 little-endian. |
| Q35 | `CONFIRMED` | Interface coefficient canonical unsigned `0..q-1`. |
| Q36 | `CONFIRMED` | Montgomery nội bộ; boundary standard domain. |
| Q37 | `CONFIRMED` | Ordering phải khớp upstream ML-KEM reference; lựa chọn reference/version/commit được theo dõi tại O-003. |
| Q38 | `CONFIRMED` | Twiddle constants trong ROM/BSRAM. |
| Q39 | `CONFIRMED` | Khởi đầu một butterfly; chỉ tăng nếu benchmark cần. |
| Q40 | `CONFIRMED` | DSP khi phù hợp, có LUT fallback. |
| Q41 | `CONFIRMED` | Montgomery multiply/reduction; canonical reduction tại boundary. |
| Q42 | `CONFIRMED` | Logical polynomial buffer chia hai bank BSRAM; không DFF memory. |
| Q43 | `CONFIRMED` | NTT in-place; không mặc định full input/output copies. |
| Q44 | `CONFIRMED` | Pipeline butterfly 2–3 tầng. |
| Q45 | `CONFIRMED` | Một command outstanding. |
| Q46 | `CONFIRMED` | Zeroize preempt operation, hủy operation và trả trạng thái zeroized. |
| Q47 | `CONFIRMED` | Self-test command; bắt buộc trước session đầu sau reset/reconfiguration. |
| Q48 | `CONFIRMED` | Error set tối thiểu: BAD_CMD, BAD_LENGTH, BAD_STATE, ZEROIZED, INTERNAL_FAULT. |
| Q49 | `CONFIRMED` | Cycle counter 32 bit cho accelerator operations. |
| Q50 | `CONFIRMED` | Golden model ở `verification/reference/` hoặc `tests/reference/`; có provenance/license/hash. |
| Q51 | `CONFIRMED` | KAT dùng fixed seed; deterministic demo dùng PC seed; secure entropy/DRBG được theo dõi tại O-002. |
| Q52 | `CONFIRMED` | KDF dùng SHAKE256 có domain separation; byte-exact formula được theo dõi tại O-001. |
| Q53 | `CONFIRMED` | KDF output gồm key16 + nonce_prefix8 + session_id4; exact derivation được theo dõi tại O-001. |
| Q54 | `CONFIRMED` | Session ID lấy từ KDF output; byte-exact mapping được theo dõi tại O-001. |
| Q55 | `CONFIRMED` | Sequence 64 bit. |
| Q56 | `CONFIRMED` | Sequence bắt đầu từ 1. |
| Q57 | `CONFIRMED` | 64 frame/session mặc định; rekey sau fault/recovery/reset/nonce-risk. |
| Q58 | `CONFIRMED` | Stage P1/P2, verify status, then `SESSION_COMMIT`. |
| Q59 | `CONFIRMED` | Secret state lưu ở register/BSRAM zeroizable; không debug readback. |
| Q60 | `CONFIRMED` | SN32 wipe shared secret và KDF buffer ngay sau commit thành công. |
| Q61 | `CONFIRMED` | Telemetry layout 24 byte với integer types và `reserved=0`. |
| Q62 | `CONFIRMED` | AD layout 24 byte với typed fields và `reserved=0`. |
| Q63 | `CONFIRMED` | P1→P2 frame 66 byte: SYNC2 + AD24 + C24 + TAG16. |
| Q64 | `CONFIRMED` | SYNC `A5 5A`. |
| Q65 | `CONFIRMED` | Không CRC payload-plane; Ascon tag bảo vệ AD+ciphertext. |
| Q66 | `CONFIRMED` | Inter-byte timeout 20 ms. |
| Q67 | `CONFIRMED` | Nonce `prefix8 || sequence_be64`. |
| Q68 | `CONFIRMED` | Payload-plane multi-byte fields big-endian. |
| Q69 | `CONFIRMED` | Tag comparison toàn bộ, không early-exit. |
| Q70 | `CONFIRMED` | Plaintext quarantine 24 byte; release sau tag PASS. |
| Q71 | `CONFIRMED` | Chấp nhận sequence > `last_accepted`. |
| Q72 | `CONFIRMED` | Cho phép sequence nhảy cóc. |
| Q73 | `CONFIRMED` | Ba valid-framing bad-tag liên tiếp tạo crypto fault; valid frame reset counter. |
| Q74 | `CONFIRMED` | P2 exposes last sequence, error, tag-fail, replay và accepted counters. |
| Q75 | `CONFIRMED` | Heartbeat dạng toggle. |
| Q76 | `CONFIRMED` | Heartbeat nominal 100 ms. |
| Q77 | `CONFIRMED` | Heartbeat timeout 350 ms. |
| Q78 | `CONFIRMED` | Startup grace 1000 ms. |
| Q79 | `CONFIRMED` | Secure/zeroize logical semantics đã duyệt; physical polarity/pulls/pins thuộc O-008 (`PHYSICAL-PENDING`). |
| Q80 | `CONFIRMED` | Trusted/manual clear + session mới; không auto-resume. |
| Q81 | `CONFIRMED` | `Tiny_FAULT_N` logical/source policy là open-drain 0/Z; physical route thuộc O-008 (`PHYSICAL-PENDING`). |
| Q82 | `PHYSICAL-PENDING` | P2 crypto-fault riêng tới Tiny chỉ sau pin verification; physical details được theo dõi tại O-008. |
| Q83 | `CONFIRMED` | `SESSION_COMMIT` là event một lần và không dùng short pulse; lựa chọn toggle hay held-until-ACK thuộc O-005. |
| Q84 | `CONFIRMED` | Power-up fail-safe: secure inactive đến self-test + commit. |
| Q85 | `CONFIRMED` | P1/P2/Tiny có project build tự chứa riêng. |
| Q86 | `CONFIRMED` | Cho phép BSRAM/DSP/PLL IP khi cần và build tái lập. |
| Q87 | `CONFIRMED` | Resource/timing evaluation policy đã duyệt; exact result thuộc O-009 (`BUILD-PENDING`). |
| Q88 | `CONFIRMED` | Debug build profile riêng; release bỏ debug core không cần. |
| Q89 | `CONFIRMED` | SN32 không `malloc`; static buffer/stack controlled. |
| Q90 | `CONFIRMED` | Binary/report acceptance lưu GitHub Release/artifact archive với SHA-256, không commit vào `main` source tree. |
| Q91 | `CONFIRMED` | Official/reference KAT + integration vectors. |
| Q92 | `CONFIRMED` | 100 random NTT/INTT vectors + directed tests. |
| Q93 | `CONFIRMED` | 100 random Ascon packets + directed tests. |
| Q94 | `CONFIRMED` | Negative matrix: bad tag, AD/cipher corruption, replay, session mismatch, truncated, timeout. |
| Q95 | `CONFIRMED` | SPI stress 10.000 transactions. |
| Q96 | `CONFIRMED` | UART P1→P2 acceptance 1.000 frames. |
| Q97 | `CONFIRMED` | 10 end-to-end sessions without reprogramming. |
| Q98 | `CONFIRMED` | Exact-build evidence: Gowin/Keil reports, tool version, commit SHA. |
| Q99 | `CONFIRMED` | Status vocabulary: CONFIRMED, ASSUMED, OPEN, TESTED, BUILD-PENDING, PHYSICAL-PENDING, FAILED, DEPRECATED. |
| Q100 | `CONFIRMED` | Audit package gồm 8 tài liệu chính thức và traceability matrix. |

---

## 3. Explicit amendments

### A-001 — ML-KEM allocation and key-pair lifecycle

`CONFIRMED`

- SN32 điều phối full ML-KEM-512 lifecycle.
- KeyGen một lần sau cold boot; người dùng có thể yêu cầu regenerate.
- Reset session thông thường không chạy lại KeyGen.
- Power loss, watchdog reset, fault recovery hoặc reset không tin cậy phải chạy lại KeyGen và tạo session mới.
- Key pair không persistent qua power cycle trong baseline competition build.
- Không lưu ML-KEM private/decapsulation key vào flash.
- Trước KeyGen mới phải zeroize key pair/session state cũ nếu còn tồn tại.
- Encaps/Decaps mỗi session trên SN32.
- P1 chỉ accelerator NTT/INTT/MultiplyNTTs.
- ML-KEM ciphertext/shared secret không đi qua telemetry.
- KDF và session stage/commit do SN32 điều phối.
- Claim chính xác: ML-KEM đầy đủ có FPGA acceleration.

### A-002 — Side-effect transaction reconciliation

`CONFIRMED`

Mỗi P1/P2 giữ đúng một record:

```text
last_side_effect_transaction_id
last_transaction_state
last_transaction_result
last_transaction_error
last_transaction_valid
```

- Record được giữ đến khi SN32 ACK/retire hoặc target reset/zeroize theo lifecycle.
- Retry cùng transaction ID và cùng request trả kết quả đã lưu; không thực hiện side effect lần hai.
- Cùng transaction ID nhưng request khác trả `TRANSACTION_CONFLICT`.
- `GET_TXN_RESULT` là idempotent.
- Transaction chưa reconcile chặn side-effect transaction mới bằng `BUSY` hoặc `RESULT_PENDING`.
- Không cần response cache lớn vì mỗi target chỉ có một command outstanding.
- Độ rộng transaction ID và byte layout vẫn `OPEN` trong ICD.

### A-003 — NTT memory

`CONFIRMED`

- Một logical in-place polynomial buffer.
- Chia hai bank BSRAM cho butterfly dual access.
- Không infer DFF memory.
- Không mặc định hai full-buffer copies.

### A-004 — Zeroize FSM

`CONFIRMED`

- Preempt operation.
- Sequentially overwrite BSRAM.
- Expose `zeroize_busy/zeroize_done`.
- Reject crypto commands while busy.
- New session mandatory afterward.

### A-005 — Mandatory self-test

`CONFIRMED`

- Self-test trước first session sau reset/reconfiguration.
- Session commit chỉ sau P1/P2 PASS.
- Secure state không active trước self-test PASS.

### A-006 — Golden model location and provenance

`CONFIRMED`

- `verification/reference/` hoặc `tests/reference/`.
- Ghi upstream, version/commit, license, vector hash, comparison scripts.

### A-007 — Entropy modes and secret logging

`CONFIRMED`

- KAT, DEMO_DETERMINISTIC, DEMO_SECURE.
- Secure entropy/DRBG source được theo dõi tại O-002 (`OPEN`).
- Không log secret/seed nhạy cảm mặc định.

### A-008 — KDF

`CONFIRMED`

- Primitive SHAKE256 và domain separation đã chốt.
- Byte-exact formula thuộc O-001 (`OPEN`).
- Không được tự ghi một formula là approved.

### A-009 — Session/rekey

`CONFIRMED`

- 64 frame là demo default, không phải maximum.
- New session sau fault/recovery/reset state loss/nonce risk.
- Không nonce reuse dưới cùng key.

### A-010 — Telemetry and AD layouts

`CONFIRMED`

- Telemetry 24 byte typed integer layout, `reserved=0`.
- AD 24 byte typed layout, `reserved=0`.
- Payload plane big-endian.

### A-011 — P1→P2 frame

`CONFIRMED`

- 66 byte, `A5 5A` sync.
- `HUNT_SYNC` FSM.
- Body 64 byte atomic receive.
- 20 ms timeout.
- No CRC.
- Ciphertext-contained sync does not resync receiver.
- Exact idle gap remains open.

### A-012 — Replay processing order

`CONFIRMED`

- Structure/session check.
- Sequence candidate check.
- Tag verify.
- Release/update replay state only after tag PASS.

### A-013 — Bad-tag policy

`CONFIRMED`

- Three consecutive framing-valid bad tags → crypto fault.
- Valid accepted frame resets counter.
- Malformed/timeout not counted.

### A-013A — P2 authenticated result buffer

`CONFIRMED`

- P2 dùng single-entry authenticated result buffer.
- Buffer có `result_valid`, `session_id`, `sequence`, `plaintext[24]` và authentication status/result.
- Không overwrite kết quả hợp lệ chưa được SN32 đọc và ACK.
- Baseline demo chỉ phát frame tiếp theo sau khi kết quả trước đã consume.
- SN32 đọc plaintext/metadata qua SPI rồi ACK/consume.
- ACK, zeroize, fault hoặc đổi session phải clear buffer.
- Đây là result readback qua control plane; encrypted payload vẫn đi trực tiếp P1→P2.

### A-014 — Tiny event synchronization

`CONFIRMED`

- `SESSION_COMMIT` không được là short pulse; exact toggle/held-to-ACK mechanism thuộc O-005 (`OPEN`).
- Synchronizers mandatory.
- Physical pin/polarity/pull/voltage thuộc O-008 (`PHYSICAL-PENDING`).

### A-015 — Resource evaluation

`CONFIRMED`

- Evaluate LUT/FF/BSRAM/DSP/I/O/clock/WNS/TNS/hold/congestion separately.
- Exact result được theo dõi tại O-009 (`BUILD-PENDING`).
- No fit claim before exact build.

### A-016 — Release artifacts

`CONFIRMED`

- No acceptance binaries in `main` source tree.
- Store exact acceptance binaries/reports in Release/artifact archive.
- Record tool versions, commit and SHA-256.

### A-017 — Directed verification

`CONFIRMED`

- Directed NTT/INTT and Ascon negative tests are mandatory in addition to random/KAT.

---

## 4. Remaining open items

| ID | Item | Status | Must resolve before |
|---|---|---|---|
| O-001 | KDF byte-exact formula | `OPEN` | KDF/session code |
| O-002 | DEMO_SECURE entropy/DRBG source | `OPEN` | secure demo claim |
| O-003 | ML-KEM upstream reference/version/commit/license | `OPEN` | accelerator RTL/reference tests |
| O-004 | SPI 8-byte header exact byte layout and transaction-ID width | `OPEN` | SPI RTL/firmware |
| O-005 | `SESSION_COMMIT` toggle vs held-to-ACK | `OPEN` | Tiny/SN32 interface implementation |
| O-006 | Minimum UART idle gap | `OPEN` | final UART TX/RX timing |
| O-008 | Physical pins, polarity, pull and I/O voltage | `PHYSICAL-PENDING` | wiring/programming |
| O-009 | Exact-device utilization/timing | `BUILD-PENDING` | hardware qualification |
| O-011 | Exact PC↔SN32 timeout values per command class | `OPEN` | final PC↔SN32 ICD and timeout handling |

---

## 5. Review closures

| ID | Decision | Status |
|---|---|---|
| C01 / former O-010 | P2 single-entry authenticated result buffer with SN32 ACK/consume lifecycle | `CONFIRMED` |
| C02 | Per-target single-entry side-effect transaction record with duplicate/conflict/reconcile rules | `CONFIRMED` |
| C03 / former O-007 | Key pair non-persistent across power cycle; regenerate after cold boot/watchdog/fault recovery/untrusted reset | `CONFIRMED` |

---

## 6. Baseline approval and implementation gate

- Decision Register v0.3 đã được chủ dự án phê duyệt làm architecture baseline và được phép commit vào `main` dưới dạng docs-only.
- Không triển khai toàn bộ hệ thống cho đến khi tối thiểu O-001, O-003, O-004, O-005 và O-006 được khóa.
- O-002 chỉ chặn `DEMO_SECURE` claim.
- O-008 chặn wiring/final constraint/physical qualification.
- O-009 chỉ được đóng sau exact-device build evidence.
- O-011 phải được khóa trước khi hoàn thiện PC↔SN32 ICD và timeout handling.
- Không được tự chọn giá trị cho open item rồi ghi là đã được phê duyệt.
