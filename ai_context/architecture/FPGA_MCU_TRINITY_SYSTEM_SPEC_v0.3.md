# FPGA MCU Trinity — System Specification

**Document status:** `APPROVED ARCHITECTURE BASELINE`  
**Implementation status:** `OPEN ITEMS REMAIN`  
**Version:** `v0.3`  
**Date:** `2026-08-01`  
**Repository target:** `hoafff/fpga_mcu_trinity`  
**Baseline use:** Được phép đưa vào `main` làm nguồn kiến trúc và quản lý yêu cầu.  
**Implementation restriction:** Không được tự triển khai hoặc tự khóa phần phụ thuộc open item chưa được phê duyệt.

---

## 1. Authority and scope

### 1.1 Nguồn có thẩm quyền

Tài liệu này được dựng từ:

1. Các quyết định mới nhất do chủ dự án phê duyệt trong project `thi 3`.
2. Cấu hình phần cứng thực tế của hệ thống.
3. Schematic, pinout, datasheet, SDK và constraint của đúng revision phần cứng.
4. Kết quả simulation, exact-device build và đo phần cứng sau này.

### 1.2 Nguồn không có thẩm quyền

Các nguồn sau không tự động định nghĩa dự án mới:

- Repository `fpga-pqc-secure-telemetry`.
- Tài liệu do AI khác tạo nhưng chưa được chủ dự án kiểm tra.
- Git history của repository cũ.
- Source, protocol, packet format, pin hoặc trạng thái `IMPLEMENTED` chưa được kiểm chứng.
- Hai tài liệu `Trinity_Spec_V2_1_DaKiemTra` và `Trinity_Spec_V2_TrienKhai_1Tuan`.

Chúng chỉ được dùng làm tài liệu tham khảo sau khi từng nội dung được đối chiếu và phê duyệt riêng.

### 1.3 Quy tắc ưu tiên

Quyết định mới nhất của chủ dự án ghi đè mọi quyết định cũ mâu thuẫn.

---

## 2. Mục tiêu hệ thống

Xây dựng hoàn chỉnh một hệ thống demo bảo mật gồm PC, SN32F407F, hai FPGA Primer 20K và một FPGA Tiny 1P5, trong đó:

- SN32 điều phối toàn bộ lifecycle ML-KEM-512.
- Primer #1 tăng tốc các phép toán đa thức của ML-KEM và thực hiện Ascon-AEAD128 encrypt.
- Primer #1 truyền payload trực tiếp một chiều tới Primer #2.
- Primer #2 kiểm tra framing, session, sequence, replay và Ascon tag trước khi công bố plaintext.
- Tiny 1P5 giám sát heartbeat/fault độc lập và điều khiển containment/zeroize.
- Hệ thống phải fit trên đúng thiết bị, timing PASS, có bằng chứng test và chạy được trên phần cứng thật.

Dự án hướng tới cuộc thi: đủ chiều sâu kỹ thuật và khả năng phản biện, nhưng tránh kiến trúc quá phức tạp, quá đơn giản hoặc lãng phí tài nguyên.

---

## 3. Cấu hình phần cứng

| Thành phần | Thiết bị | Clock chính | Vai trò |
|---|---|---:|---|
| PC host | Windows/Linux PC | — | Điều khiển demo, test orchestration, log và evidence |
| MCU | SONiX SN32F407F | 12 MHz | Control plane, ML-KEM lifecycle, SHA3/SHAKE/KDF, session |
| Primer #1 | GW2A-LV18PG256C8/I7 | 27 MHz | NTT/INTT/MultiplyNTTs accelerator, Ascon encrypt, UART TX |
| Primer #2 | GW2A-LV18PG256C8/I7 | 27 MHz | UART RX, replay, Ascon decrypt/tag verify |
| Tiny 1P5 | GW1N-UV1P5QN48XC7/I6 | 27 MHz | Heartbeat/fault supervisor và containment |

---

## 4. Kiến trúc ba mặt phẳng

```text
CONTROL PLANE
PC <---- UART ----> SN32F407F
                       |
                       | shared SPI Mode 0, MSB-first
                       | CS/IRQ riêng từng Primer
                       +----------> Primer #1
                       +----------> Primer #2

PAYLOAD PLANE
Primer #1 ==================================> Primer #2
                UART một chiều trực tiếp

SECURITY PLANE
SN32 heartbeat -------------------+
P1 heartbeat/fault ---------------+----> Tiny 1P5
P2 heartbeat/crypto-fault --------+
Tiny secure-enable/zeroize -------+----> P1/P2
```

### 4.1 Ràng buộc kiến trúc

- PC không giao tiếp trực tiếp với FPGA.
- Payload P1→P2 không đi vòng qua SN32.
- Payload không đi qua PC hoặc Tiny.
- ML-KEM ciphertext và shared secret không đi qua đường telemetry P1→P2.
- Tiny không nhận, lưu, mã hóa hoặc giải mã payload.

---

## 5. Chế độ vận hành

1. `KAT`
   - Dùng seed/vector cố định.
   - Chỉ dùng cho kiểm thử tái lập.
   - Không được gọi là entropy an toàn.

2. `DEMO_DETERMINISTIC`
   - PC cấp seed để tái lập lỗi và kết quả.
   - Không dùng cho tuyên bố bảo mật thực tế.

3. `DEMO_SECURE`
   - Dùng nguồn entropy hoặc DRBG được xác định và phê duyệt riêng.
   - Nguồn entropy byte-exact hiện là `OPEN`.

4. `DIAGNOSTIC`
   - Chạy self-test, kiểm tra giao tiếp, benchmark và đọc trạng thái.

PC khởi tạo session. SN32 chỉ chấp nhận khi các precondition bắt buộc đã PASS.

---

## 6. Phân chia ML-KEM-512

### 6.1 Lifecycle

- SN32 điều phối toàn bộ lifecycle ML-KEM-512.
- `KeyGen` chạy một lần sau cold boot.
- Người dùng có thể chủ động yêu cầu regenerate key pair.
- Reset session thông thường không chạy lại `KeyGen`.
- Mất điện hoặc reset làm mất/không bảo đảm trạng thái RAM phải chạy lại `KeyGen`.
- Watchdog reset hoặc recovery sau fault mặc định chạy lại `KeyGen` và tạo session mới.
- Không lưu ML-KEM private/decapsulation key vào flash trong baseline competition build.
- Không phục hồi session cũ sau mất điện hoặc reset không tin cậy.
- Trước `KeyGen` mới phải zeroize key pair và session state cũ nếu còn tồn tại.
- Sau `KeyGen` mới, `Encaps`, `Decaps` và session establishment được thực hiện lại từ đầu.
- `Encaps` và `Decaps` chạy trên SN32 cho mỗi session.
- Sau Encaps và Decaps, SN32 phải xác minh hai phía tạo ra cùng shared secret.
- SN32 chạy KDF, stage session context cho P1 và P2, kiểm tra trạng thái rồi mới phát `SESSION_COMMIT`.
- Demo được mô tả là **ML-KEM-512 đầy đủ có FPGA acceleration và thiết lập session**.
- Không mô tả sai rằng P1 và P2 là hai thiết bị độc lập tự trao đổi khóa.

### 6.2 Phần offload sang Primer #1

Primer #1 chỉ offload:

- `NTT`
- `INTT`
- `MultiplyNTTs/BaseCaseMultiply`

SN32 gửi một polynomial 256 hệ số theo command SPI và nhận kết quả về.

### 6.3 Biểu diễn polynomial

- `n = 256`
- `q = 3329`
- Mỗi hệ số truyền qua SPI bằng 16 bit little-endian.
- Giá trị tại interface là canonical unsigned `0 ... q-1`.
- Standard domain tại boundary.
- Montgomery domain được phép dùng nội bộ.
- Thứ tự hệ số và twiddle phải khớp upstream ML-KEM reference được chọn.
- Upstream source/version/commit cụ thể hiện là `OPEN`.

---

## 7. Vi kiến trúc accelerator Primer #1

### 7.1 Bộ nhớ

- NTT chạy in-place trên một logical polynomial buffer.
- Logical buffer được chia thành hai bank BSRAM để phục vụ hai truy cập butterfly.
- Không giữ hai bản sao full input/output theo mặc định.
- Không infer polynomial memory bằng DFF.
- Chỉ dùng full-buffer ping-pong nếu access schedule hoặc exact build chứng minh cần thiết.

### 7.2 Datapath

- Khởi đầu với một butterfly datapath dùng lại theo thời gian.
- Có thể tăng lên hai butterfly nếu benchmark không đạt.
- Modular multiply ưu tiên DSP khi phù hợp; phải có phương án LUT fallback.
- Montgomery reduction cho multiply; canonical reduction tại interface.
- Pipeline vừa phải 2–3 tầng.
- Twiddle đặt trong ROM/BSRAM.
- Mỗi target chỉ xử lý một command outstanding.

### 7.3 Benchmark và trạng thái

P1 phải có cycle counter 32 bit riêng cho NTT, INTT và MultiplyNTTs/BaseCaseMultiply.

Các lỗi tối thiểu:

- `BAD_CMD`
- `BAD_LENGTH`
- `BAD_STATE`
- `ZEROIZED`
- `INTERNAL_FAULT`

---

## 8. Self-test và boot gate

```text
BOOT
  -> RUN_SELF_TEST
  -> SELF_TEST_PASS
  -> STAGE_SESSION
  -> SESSION_COMMIT
  -> ACTIVE
```

- Self-test bắt buộc trước session đầu tiên sau reset hoặc FPGA reconfiguration.
- Self-test được SN32 yêu cầu qua command.
- Không được bật trạng thái secure/active nếu self-test chưa PASS.
- SN32 chỉ phát `SESSION_COMMIT` sau khi cả P1 và P2 báo self-test PASS và session context đã stage hợp lệ.

---

## 9. Entropy, KDF và session

### 9.1 Entropy

- `KAT`: seed cố định.
- `DEMO_DETERMINISTIC`: PC cấp seed tái lập.
- `DEMO_SECURE`: nguồn entropy/DRBG riêng, hiện `OPEN`.
- Không log private key, decapsulation key, shared secret, session key hoặc seed nhạy cảm trong JSON mặc định.

### 9.2 KDF

Chốt ở mức primitive:

- Dùng `SHAKE256`.
- Phải có domain separation.
- Output phải tạo Ascon key 16 byte, nonce prefix 8 byte và session ID 4 byte.

Chưa khóa byte-exact:

- Domain string.
- Input fields.
- Thứ tự nối.
- Độ dài từng trường.
- Endianness.
- Output length byte-exact.
- Cách tách output.

Chi tiết byte-exact có trạng thái `OPEN` và được theo dõi bởi O-001; cần phê duyệt riêng trước khi triển khai KDF/session code.

### 9.3 Session

- Session ID lấy từ KDF output sau khi công thức được phê duyệt.
- Sequence là uint64, bắt đầu từ 1.
- Nonce: `nonce_prefix[8] || sequence_be64[8]`.
- Không được lặp nonce dưới cùng key.
- 64 frame/session là cấu hình mặc định cho demo và acceptance, không phải protocol maximum.
- Bắt buộc tạo session mới sau fault, recovery, reset làm mất state hoặc nguy cơ nonce reuse.
- KAT phải được cô lập để không vô tình tái sử dụng key+nonce trong demo thông thường.

### 9.4 Commit

```text
SN32:
  stage P1
  stage P2
  read P1/P2 status
  verify both staged
  emit SESSION_COMMIT event
  enter ACTIVE
```

`SESSION_COMMIT` không được là pulse ngắn không handshake. Dùng toggle event qua synchronizer hoặc level giữ đến ACK. Lựa chọn cuối cùng sẽ được khóa trong ICD.

---

## 10. Zeroize

### 10.1 Ưu tiên

- Zeroize có ưu tiên cao hơn mọi operation mật mã.
- Operation đang chạy phải bị hủy.
- Mọi command mật mã mới bị từ chối trong lúc zeroize.

### 10.2 Dữ liệu phải xóa

- Active key.
- Staged key.
- Shared secret.
- KDF output.
- Nonce prefix.
- Plaintext quarantine.
- Temporary secret state.
- Session metadata nhạy cảm.
- BSRAM chứa secret/intermediate.

### 10.3 FSM

BSRAM phải được ghi đè tuần tự. Không được giả định xóa toàn bộ trong một chu kỳ.

Tín hiệu/trạng thái:

- `zeroize_busy`
- `zeroize_done`

Sau `zeroize_done`, session cũ không hợp lệ và phải tạo session mới.

---

## 11. PC host

### 11.1 Chức năng

- CLI là giao diện chính.
- GUI tối giản chỉ thực hiện sau nếu không ảnh hưởng core system.
- Hỗ trợ Windows và Linux; acceptance ưu tiên Windows.
- Console hiển thị trạng thái.
- JSON lưu evidence có cấu trúc.
- Không log secret mặc định.

### 11.2 PC↔SN32 protocol

- UART 115200 8N1.
- Binary command; log người dùng dạng text.
- COBS framing với `0x00` delimiter.
- CRC-16/CCITT-FALSE.
- Payload tối đa 256 byte.
- Header gồm version, command, flags, transaction ID và length.
- Transaction ID PC-side: 16 bit.
- Event bất đồng bộ dùng cùng UART với loại frame `EVENT`.
- Timeout theo class: control nhanh khoảng 500 ms; ML-KEM/benchmark 5–10 s, khóa cụ thể trong ICD.
- Retry tối đa 2 lần và chỉ cho command idempotent.

---

## 12. Transaction và side-effect reconciliation

- Không blind retry command có side effect.
- SN32 giữ tối thiểu transaction ID, trạng thái và kết quả command có side effect gần nhất trên từng target.
- Mỗi P1 và P2 giữ đúng một transaction có side effect gần nhất:
  - `last_side_effect_transaction_id`
  - `last_transaction_state`
  - `last_transaction_result`
  - `last_transaction_error`
  - `last_transaction_valid`
- Kết quả được giữ đến khi SN32 `ACK/RETIRE`, hoặc target bị reset/zeroize theo lifecycle đã định nghĩa.
- Retry cùng transaction ID và cùng nội dung request chỉ trả lại kết quả đã lưu; không thực hiện side effect lần thứ hai.
- Cùng transaction ID nhưng nội dung request khác phải trả `TRANSACTION_CONFLICT`.
- `GET_TXN_RESULT` là command idempotent.
- Khi transaction cũ chưa được reconcile, target không được âm thầm ghi đè bằng side-effect transaction mới; trả `BUSY` hoặc `RESULT_PENDING`.
- Không cần response cache lớn vì mỗi target chỉ có một command outstanding.
- Khi response SN32↔target bị mất, dùng `GET_STATUS` hoặc `GET_TXN_RESULT`.
- Độ rộng transaction ID và byte layout chính xác vẫn được khóa trong ICD.

---

## 13. SPI control plane SN32↔Primer

- Shared SPI, Mode 0, MSB-first.
- Bring-up 1 MHz; sau đo điện/timing tăng dần tới 5 MHz.
- CS/IRQ riêng từng target.
- Không assert hai CS đồng thời.
- MISO target không được chọn phải high-Z.
- Packet command/response chung header/status/error; command riêng theo target.
- Chunk tối đa 64 byte.
- Header cố định 8 byte.
- CRC-16.
- Request và response dùng hai CS transaction riêng.
- IRQ active-low dạng level, giữ đến khi SN32 đọc/ack.
- Không dùng chân BUSY riêng; dùng status+IRQ.
- Exact 8-byte header layout và SPI transaction ID width hiện `OPEN` cho ICD.

---

## 14. Telemetry plaintext

Plaintext cố định 24 byte, big-endian trên payload plane:

| Offset | Size | Field | Type | Constraint |
|---:|---:|---|---|---|
| 0 | 4 | `timestamp_ms` | uint32 | big-endian |
| 4 | 2 | `sensor_id` | uint16 | big-endian |
| 6 | 2 | `flags` | uint16 | big-endian |
| 8 | 4 | `temperature_mC` | int32 | big-endian |
| 12 | 4 | `humidity_milli_percent` | uint32 | big-endian |
| 16 | 4 | `sample_counter` | uint32 | big-endian |
| 20 | 4 | `reserved` | uint32 | bắt buộc 0 |

Nguồn telemetry hỗ trợ dữ liệu giả lập xác định và ADC/cảm biến thật; dữ liệu giả lập là baseline tái lập.

---

## 15. Associated Data

AD cố định 24 byte, big-endian:

| Offset | Size | Field | Type | Constraint |
|---:|---:|---|---|---|
| 0 | 1 | `version` | uint8 | phiên bản protocol |
| 1 | 1 | `message_type` | uint8 | telemetry type |
| 2 | 2 | `flags` | uint16 | big-endian |
| 4 | 4 | `session_id` | uint32 | big-endian |
| 8 | 8 | `sequence` | uint64 | big-endian |
| 16 | 2 | `payload_len` | uint16 | phải bằng 24 |
| 18 | 2 | `source_id` | uint16 | big-endian |
| 20 | 4 | `reserved` | uint32 | bắt buộc 0 |

AD được xác thực bởi Ascon tag.

---

## 16. Ascon-AEAD128

- Algorithm: Ascon-AEAD128 theo NIST SP 800-232.
- P1: encrypt-only.
- P2: decrypt + tag verify.
- Key: 16 byte.
- Nonce: 16 byte.
- AD: 24 byte.
- Plaintext/ciphertext: 24 byte.
- Tag: 16 byte.
- P2 phải so sánh toàn bộ tag, không early-exit.
- Plaintext giữ trong quarantine đủ 24 byte và chỉ release sau tag PASS.

---

## 17. Payload frame P1→P2

Frame cố định 66 byte:

```text
SYNC[2] || AD[24] || CIPHERTEXT[24] || TAG[16]
```

- `SYNC = A5 5A`.
- UART 115200 8N1.
- Big-endian cho field đa byte.
- Không CRC riêng; Ascon tag xác thực AD và ciphertext.

### 17.1 Receiver FSM

```text
HUNT_SYNC
  -> RECEIVE_BODY_64
  -> VALIDATE_STRUCTURE
  -> CHECK_SESSION_SEQUENCE_CANDIDATE
  -> VERIFY_TAG
  -> RELEASE_OR_REJECT
  -> HUNT_SYNC
```

- Chỉ tìm `A5 5A` trong `HUNT_SYNC`.
- Không tìm sync mới khi đang nhận 64 byte body.
- `A5 5A` trong ciphertext không ảnh hưởng receiver state.
- Inter-byte timeout 20 ms.
- Frame thiếu/timeout: bỏ toàn bộ buffer và về `HUNT_SYNC`.
- Tag fail: về `HUNT_SYNC`.
- Có idle gap giữa frame; exact minimum idle gap hiện `OPEN`.
- Chỉ chuyển sang COBS/escaping nếu hardware evidence cho thấy resync không ổn định.

---

## 18. Replay và authentication policy

Thứ tự bắt buộc:

1. Nhận đủ frame.
2. Kiểm tra version, session và cấu trúc.
3. Kiểm tra sequence là candidate hợp lệ.
4. Xác thực Ascon tag.
5. Chỉ sau tag PASS mới release plaintext và cập nhật `last_accepted_sequence`.

Replay policy:

- Chỉ chấp nhận sequence lớn hơn `last_accepted_sequence`.
- Cho phép sequence nhảy cóc.
- Không cập nhật replay state trước tag PASS.

Error taxonomy:

- `BAD_SESSION`
- `REPLAY`
- `STALE_SEQUENCE`
- `BAD_TAG`
- `MALFORMED_FRAME`
- `FRAME_TIMEOUT`

### 18.1 Bad-tag threshold

- Chỉ frame framing hợp lệ nhưng tag sai mới tăng counter.
- Ba bad tag liên tiếp tạo crypto fault.
- Một frame hợp lệ tiếp theo reset counter.
- Malformed frame và timeout không tính là bad tag.
- Bad tag đơn lẻ bị từ chối, plaintext quarantine bị xóa và lỗi được log.

---

## 19. P2 authenticated result path

Sau khi tag PASS:

```text
P2 tag PASS
  -> lưu plaintext 24 byte vào authenticated result buffer
  -> SN32 đọc plaintext và metadata qua SPI
  -> SN32 gửi kết quả về PC để hiển thị/đối chiếu
  -> SN32 ACK/consume
  -> P2 xóa trạng thái valid của buffer
```

Baseline đầu tiên dùng **single-entry authenticated result buffer** với tối thiểu:

- `result_valid`
- `session_id`
- `sequence`
- `plaintext[24]`
- `authentication_status/result`

Quy tắc:

- P2 không được ghi đè kết quả hợp lệ chưa được SN32 đọc và ACK.
- Trong baseline demo, SN32 chỉ yêu cầu P1 phát frame tiếp theo sau khi kết quả frame trước đã được đọc/consume.
- Cơ chế này cố ý tránh FIFO lớn trên P2.
- Sau `ACK/consume`, zeroize, fault hoặc đổi session, buffer phải được xóa và `result_valid=0`.
- Plaintext readback qua SPI chỉ là result/control-plane phục vụ demo và verification.
- Payload mã hóa vẫn truyền trực tiếp P1→P2 và không đi vòng qua SN32.

---

## 20. Tiny supervisor

### 20.1 Heartbeat

- Heartbeat dạng toggle.
- Chu kỳ danh định 100 ms.
- Timeout 350 ms.
- Startup grace 1000 ms.
- Đồng bộ CDC bắt buộc.

### 20.2 CDC

Phải có synchronizer cho `SESSION_COMMIT`, heartbeat, crypto fault, secure enable, zeroize và fault line.

### 20.3 Recovery

- Không tự động trở lại session cũ.
- Cần manual/trusted clear.
- Sau clear phải tạo session mới.

### 20.4 Tín hiệu vật lý

Logical function được xác định, nhưng polarity/pull/voltage/pin chỉ khóa sau schematic+constraint.

- `Tiny_FAULT_N` source candidate: open-drain `0/Z`; physical route vẫn `PHYSICAL-PENDING`.
- P2 crypto-fault riêng: `PHYSICAL-PENDING`.
- `SESSION_COMMIT`: toggle hoặc level-to-ACK, không pulse ngắn.
- `SECURE_ENABLE` và zeroize logical semantics đã chốt; physical polarity chưa khóa.
- Power-up fail-safe: secure chưa active cho đến self-test và session commit hợp lệ.

---

## 21. Tài nguyên và timing

Đánh giá riêng LUT, FF, BSRAM, DSP, I/O, clock resources, WNS, TNS, hold và routing congestion.

Ngưỡng:

- Mục tiêu ≤75%.
- 75–85%: review bắt buộc.
- 85–90%: chỉ chấp nhận nếu có lý do và margin đủ.
- >90%: reject.
- Không kết luận fit chỉ dựa trên tổng phần trăm.
- Timing phải PASS ở 27 MHz.
- Mọi kết luận hiện tại: `BUILD-PENDING`.

Debug dùng profile riêng; release bỏ debug core không cần. SN32 không dùng `malloc`; static buffer và stack phải được kiểm soát.

---

## 22. Build và artifact

- P1, P2 và Tiny có project Gowin tự chứa riêng.
- Cho phép BSRAM/DSP/PLL vendor IP khi cần và project tái lập.
- Không commit `.fs`, `.hex`, `.axf` vào source tree `main`.
- Release acceptance phải lưu bitstream, firmware binary, map/report, tool version, commit SHA và SHA-256 dưới GitHub Release hoặc artifact archive.
- Phải lấy lại chính xác binary đã dùng trong acceptance.

---

## 23. Verification

### 23.1 ML-KEM/NTT

- Official/reference KAT.
- Vector tích hợp riêng.
- Ít nhất 100 random polynomial.
- Directed tests: zero polynomial, toàn `q-1`, impulse, alternating values, boundary reduction, `INTT(NTT(a)) = a`, so sánh từng hệ số với reference.

### 23.2 Ascon

- Official NIST KAT.
- Ít nhất 100 random packet.
- Directed tests: flip AD bit, flip ciphertext bit, sửa tag, sai nonce, sai key, sai session, replay, frame thiếu, timeout, chứng minh plaintext không release khi tag fail.

### 23.3 Transport

- SPI: 10.000 transaction acceptance.
- UART P1→P2: 1.000 frame acceptance.
- Negative matrix: bad tag, AD/cipher corruption, replay, session mismatch, truncated frame, timeout.

### 23.4 End-to-end

- 10 session liên tiếp.
- Không reprogram giữa các session.
- 64 frame/session mặc định.
- Fault/recovery tạo session mới.

### 23.5 Exact-build evidence

- Gowin synthesis, P&R, timing, utilization, final I/O report.
- Keil map/size.
- Tool version và commit SHA.

---

## 24. Status vocabulary

- `CONFIRMED`
- `ASSUMED`
- `OPEN`
- `TESTED`
- `BUILD-PENDING`
- `PHYSICAL-PENDING`
- `FAILED`
- `DEPRECATED`

Không dùng `PASS` nếu scope của bằng chứng không được ghi rõ.

---

## 25. Golden model và tài liệu verification

Golden/reference model đặt tại một trong:

```text
verification/reference/
tests/reference/
```

Không đặt golden model trong `ai_context/reference/`.

Phải ghi upstream source, version/commit, license, vector hash và script so sánh.

---

## 26. Bộ tài liệu audit cuối

1. System Requirements.
2. Architecture & Allocation.
3. Interface Control Document.
4. Cryptographic Profile.
5. Hardware Integration Specification.
6. Verification & Acceptance Plan.
7. Decision Register.
8. Requirements Traceability Matrix.

---

## 27. Open items không được tự khóa

| ID | Nội dung | Trạng thái |
|---|---|---|
| O-001 | KDF byte-exact | `OPEN` |
| O-002 | Nguồn entropy/DRBG cho `DEMO_SECURE` | `OPEN` |
| O-003 | Upstream ML-KEM reference, version/commit/license | `OPEN` |
| O-004 | SPI 8-byte header byte layout và SPI transaction-ID width | `OPEN` |
| O-005 | `SESSION_COMMIT`: toggle hay level-to-ACK | `OPEN` |
| O-006 | Minimum idle gap P1→P2 | `OPEN` |
| O-008 | Exact physical pins, polarity, pull và I/O voltage | `PHYSICAL-PENDING` |
| O-009 | Exact-device resource/timing result | `BUILD-PENDING` |
| O-011 | Exact timeout values theo từng PC↔SN32 command class | `OPEN` |

---

## 28. Các mục đã được khóa ở vòng review này

| ID | Nội dung | Trạng thái |
|---|---|---|
| C01 | P2 single-entry authenticated result buffer; SN32 read + ACK/consume; không overwrite kết quả chưa retire | `CONFIRMED` |
| C02 | Mỗi target giữ đúng một last side-effect transaction; duplicate-safe; conflict detection; ACK/retire lifecycle | `CONFIRMED` |
| C03 / O-007 | Key pair không persistent qua power cycle; KeyGen lại sau cold boot, watchdog/fault recovery hoặc reset không tin cậy | `CONFIRMED` |

---

## 29. Baseline approval and implementation gate

Tài liệu v0.3 này đã được chủ dự án phê duyệt làm **architecture baseline** và được phép commit vào `main` dưới dạng docs-only.

Không triển khai toàn bộ hệ thống cho đến khi tối thiểu các mục sau được khóa:

- O-001 — KDF byte-exact.
- O-003 — ML-KEM upstream reference/version/commit/license.
- O-004 — SPI header và transaction-ID.
- O-005 — `SESSION_COMMIT` mechanism.
- O-006 — UART minimum idle gap.

Phạm vi các mục còn lại:

- O-002 chỉ chặn tuyên bố/chế độ `DEMO_SECURE`; không chặn KAT hoặc deterministic demo.
- O-008 chặn wiring, polarity, pull, final constraint và physical qualification.
- O-009 chỉ được đóng sau exact-device synthesis, P&R, timing và utilization evidence.
- O-011 phải được khóa trước khi hoàn thiện PC↔SN32 ICD và timeout handling.

Mọi phần phụ thuộc open item phải dừng ở thiết kế interface/draft; không được tự chọn giá trị rồi ghi là đã phê duyệt.
