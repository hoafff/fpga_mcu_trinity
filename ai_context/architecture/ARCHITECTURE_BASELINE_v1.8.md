# FPGA MCU Trinity — Architecture Baseline v1.8

Status: `ARCHITECTURE LOCKED / IMPLEMENTATION PENDING`

Tài liệu này ghi lại baseline dùng để triển khai **dự án mới**
`fpga_mcu_trinity`. Nó không hợp thức hóa bất kỳ source nào được import từ repo
cũ và không phải bằng chứng build hoặc phần cứng.

## 1. Phạm vi hệ thống

| Thành phần | Thiết bị | Clock | Trách nhiệm |
|---|---|---:|---|
| PC host | Windows/Linux PC | — | UART UI, gửi 32 B entropy/session, KAT, log |
| SN32 | SONiX SN32F407F | 12 MHz | ML-KEM cấp cao, SHA3/SHAKE/KDF, session, điều phối |
| Primer #1 | GW2A-LV18PG256C8/I7 | 27 MHz | NTT/INTT/MultiplyNTTs, Ascon encrypt, UART TX |
| Primer #2 | GW2A-LV18PG256C8/I7 | 27 MHz | UART RX, replay, Ascon decrypt/tag verify |
| Tiny 1P5 | GW1N-UV1P5QN48XC7/I6 | 27 MHz | Giám sát heartbeat/fault và containment |

## 2. Topology

1. PC trao đổi lệnh/session với SN32 qua UART `115200 8N1`.
2. SN32 dùng một bus SPI chung tới hai Primer: Mode 0, MSB-first, 1 MHz khi
   bring-up; `CS1_N/IRQ1_N` và `CS2_N/IRQ2_N` tách riêng; không được assert hai
   CS cùng lúc; MISO của target không được chọn phải high-Z.
3. Primer #1 gửi đúng một frame telemetry 60 byte sang Primer #2 bằng UART một
   chiều. Route ứng viên đã chốt ở mức schematic/constraint là
   `P1 J2-11/R13 uart_tx_o → P2 J2-11/R13 uart_rx_i`, Bank 2 3.3 V; exact
   Gowin I/O report vẫn phải xác nhận lại.
4. Primer #2 chỉ công bố plaintext sau khi tag hợp lệ và replay check PASS; kết
   quả/trạng thái được SN32 đọc qua endpoint điều khiển.
5. Tiny 1P5 không nhận hoặc lưu payload. Nó chỉ quan sát heartbeat/fault và điều
   khiển `secure_enable`/`zeroize` cho hai Primer.

## 3. ML-KEM-512 và KDF

- Demo phải chạy ML-KEM-512 thật, không phải NTT self-test độc lập.
- SN32 thực hiện điều khiển cấp cao, SHA3/SHAKE, KDF và quản lý dữ liệu.
- Primer #1 tăng tốc NTT, INTT và `MultiplyNTTs/BaseCaseMultiply` đúng ML-KEM;
  không thay bằng phép nhân độc lập từng hệ số.
- Tham số: `n=256`, `q=3329`, hệ số 16 bit; giao diện vào/ra standard domain,
  Montgomery domain chỉ được dùng nội bộ.
- Mỗi session DEMO bắt buộc nhận 32 byte CSPRNG entropy từ PC và trộn với entropy
  cục bộ SN32; profile KAT dùng seed vector chính thức cố định.
- KDF baseline:

  ```text
  SHAKE256("FPST-KDF-v1" || shared_secret || SHA3-256(mlkem_ciphertext_768B), 28B)
  ```

  28 byte đầu ra được tách thành `ascon_key[16]`, `nonce_prefix[8]` và
  `session_id[4]`.

## 4. Ascon-AEAD128

- Thuật toán: Ascon-AEAD128 theo NIST SP 800-232.
- Primer #1: encrypt-only.
- Primer #2: decrypt + tag verify.
- Key: 16 byte.
- Nonce: 16 byte = `nonce_prefix[8] || sequence_be64[8]`.
- Associated Data: `COMMAND || btp_txn_id || LENGTH || session_id || sequence`.
- Plaintext/ciphertext: cố định 24 byte.
- Tag: 16 byte.

## 5. Frame UART P1 → P2

| Offset | Kích thước | Trường | Giá trị/quy tắc |
|---:|---:|---|---|
| 0 | 2 | `SYNC` | `A5 5A` |
| 2 | 1 | `COMMAND` | `0x60` |
| 3 | 1 | `btp_txn_id` | `(sequence - 1) mod 256` |
| 4 | 2 | `LENGTH` | `0x0034`, big-endian |
| 6 | 4 | `session_id` | big-endian |
| 10 | 8 | `sequence` | big-endian, bắt đầu từ 1 |
| 18 | 24 | `ciphertext` | Ascon output |
| 42 | 16 | `tag` | Ascon tag |
| 58 | 2 | `CRC-16` | CRC-16/CCITT-FALSE, big-endian |

Tổng kích thước luôn là 60 byte. Frame reference của artifact tái lập v1.8 có
CRC `0x50AF`; giá trị này chỉ có ý nghĩa với đúng vector reference đầy đủ.
UART receiver dùng inter-byte inactivity watchdog 20 ms để bỏ frame dở dang.

## 6. Session và lỗi

- Sequence bắt đầu từ 1; profile demo giới hạn tối đa 256 frame/session.
- Replay key là cặp `session_id + sequence`; chỉ cập nhật trạng thái replay sau
  khi tag PASS.
- CRC sai hoặc replay: drop frame + báo lỗi, không zeroize.
- Tag sai: không công bố plaintext; tăng bộ đếm liên tiếp.
- Ba tag sai liên tiếp hoặc mất heartbeat: latch fault và zeroize.
- Fault latch chỉ được xóa bởi trusted reset hoặc khởi tạo session mới theo luồng
  commit hợp lệ.
- Không có retry timeout, response-cache timeout, response cache, retained
  packet hoặc buffer payload lớn từ kiến trúc cũ.

## 7. Tối ưu tài nguyên

- Mục tiêu mỗi loại tài nguyên FPGA không quá 80%; trần chấp nhận tuyệt đối 90%.
- Timing phải PASS ở 27 MHz.
- Được tuần tự hóa và tái sử dụng butterfly, modular arithmetic, RAM và Ascon
  datapath.
- Ưu tiên giảm FF rồi LUT; dữ liệu khối đặt vào BSRAM; DSP/BSRAM vendor IP được
  phép dùng khi có bằng chứng build.
- SN32 chỉ có 32 KiB Flash và 8 KiB SRAM: ML-KEM phải dùng overlay, streaming
  theo polynomial và SHAKE incremental; Keil `.map` là gate bắt buộc.

## 8. Wiring an toàn đang bị gate

- `Tiny_FAULT_N → SN32 P0.10/J11-1`: active-low, dùng pull-up 10 kΩ có sẵn;
  P0.10/P0.11 phải input/no-pull và I2C/EEPROM firmware phải tắt.
- `SN32_SESSION_COMMIT: P3.8/PAT17 → Tiny J1-6`.
- Không dùng SN32 J8/P3.10–P3.13 vì thuộc mạng crystal/clock.
- Route Tiny J1-9/pin 12 và các thuộc tính open-drain/no-pull chưa được coi là
  hardware-qualified cho đến khi có exact I/O report và schematic/revision đầy
  đủ của Tiny 1P5.
- Không nối dây, program hoặc cấp nguồn chỉ dựa trên tài liệu baseline này.

## 9. Acceptance gate

Mỗi target phải có source/project tự chứa, unit/KAT độc lập trong `ai_context/`,
generic simulation sạch, exact vendor build PASS, timing PASS, utilization theo
ngân sách, rồi mới được chuyển sang hardware qualification.
