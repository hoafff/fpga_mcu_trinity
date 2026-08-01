# FPGA MCU Trinity — Project Memory / AI Handoff

**Status:** `APPROVED ARCHITECTURE BASELINE / OPEN ITEMS REMAIN`  
**Purpose:** Điểm đọc đầu tiên cho mọi AI, thành viên hoặc bên phản biện khi mở repository trong phiên mới.

## 1. Thứ tự đọc bắt buộc

1. `ai_context/decisions/A-018_PROJECT_MEMORY_PLACEMENT.md`
2. `ai_context/architecture/FPGA_MCU_TRINITY_SYSTEM_SPEC_v0.3.md`
3. `ai_context/decisions/FPGA_MCU_TRINITY_DECISION_REGISTER_v0.3.md`
4. `ai_context/status/IMPLEMENTATION_STATUS.md`
5. `ai_context/decisions/PROJECT_STRUCTURE_POLICY.md`
6. `target.toml` của target đang làm việc.

A-018 chỉ sửa vị trí lưu tài liệu/golden model của baseline v0.3 và có ưu tiên hơn các đường dẫn cũ tại System Spec §25, Q50 và A-006. Nó không thay đổi kiến trúc mật mã, giao thức hay phân chia chức năng.

## 2. Nguồn chân lý

Ưu tiên: quyết định mới nhất đã commit trên `main` → System Specification hiện hành → tài liệu phần cứng chính thức → source cùng test đúng scope → exact build/đo phần cứng. Repo `fpga-pqc-secure-telemetry`, Git history và mọi file dưới `ai_context/migration/` chỉ là tham khảo/provenance.

Không tự biến `OPEN`, `BUILD-PENDING` hoặc `PHYSICAL-PENDING` thành `CONFIRMED`/`TESTED`; không tự điền open item bằng lựa chọn “hợp lý”.

## 3. Kiến trúc đã chốt

```text
CONTROL: PC <-> SN32 -- shared SPI, CS/IRQ riêng --> Primer #1 / Primer #2
PAYLOAD: Primer #1 == UART một chiều, frame 66 byte ==> Primer #2
SECURITY: SN32/P1/P2 -- heartbeat/fault --> Tiny; Tiny -- secure/zeroize --> P1/P2
```

- Payload P1→P2 đi trực tiếp, không đi vòng qua SN32, PC hoặc Tiny.
- SN32 điều phối toàn bộ lifecycle ML-KEM-512; KeyGen sau cold boot, Encaps/Decaps mỗi session.
- P1 chỉ tăng tốc `NTT`, `INTT`, `MultiplyNTTs/BaseCaseMultiply`, rồi Ascon encrypt và UART TX.
- P2 nhận UART, kiểm tra framing/session/sequence/replay, Ascon decrypt/tag verify; chỉ release plaintext sau tag PASS.
- Tiny không xử lý payload; Tiny giám sát liveness/fault và containment.

## 4. Hợp đồng nổi bật

- ML-KEM: `n=256`, `q=3329`, hệ số interface canonical unsigned 16 bit; standard domain tại boundary, Montgomery nội bộ.
- Ascon-AEAD128 theo NIST SP 800-232: key 16 B, nonce 16 B, AD 24 B, plaintext/ciphertext 24 B, tag 16 B.
- Nonce: `nonce_prefix[8] || sequence_be64[8]`.
- Frame P1→P2: `A5 5A || AD24 || C24 || TAG16` = 66 B; không CRC; timeout 20 ms; chỉ tìm sync trong `HUNT_SYNC`.
- Replay state chỉ cập nhật sau tag PASS.
- P2 dùng single-entry authenticated result buffer; SN32 đọc qua SPI rồi `ACK/consume`; đây chỉ là result readback control-plane.
- Mỗi target giữ một side-effect transaction gần nhất; duplicate cùng ID+nội dung trả kết quả cũ, khác nội dung trả `TRANSACTION_CONFLICT`.
- Self-test bắt buộc trước session đầu; zeroize hủy operation, ghi đè BSRAM tuần tự và bắt buộc session mới.
- Heartbeat toggle 100 ms, timeout 350 ms, startup grace 1000 ms; ba framing-valid bad tag liên tiếp tạo crypto fault.

## 5. Gate chưa khóa

Không triển khai toàn bộ hệ thống trước khi khóa `O-001`, `O-003`, `O-004`, `O-005`, `O-006`.

- `O-002` chỉ chặn claim `DEMO_SECURE`.
- `O-008` chặn wiring, final constraint và physical qualification.
- `O-009` chỉ đóng sau exact-device build evidence.
- `O-011` chặn hoàn thiện timeout PC↔SN32.

## 6. Trạng thái hiện tại

PC host, SN32 full firmware, Primer #1 và Primer #2 chưa triển khai. SN32 hiện chỉ có candidate P0.10/P0.11 guard. Tiny có source candidate tự chứa và inherited source-only evidence; exact Gowin build vẫn `BUILD-PENDING`. Chưa có hardware qualification.

## 7. Phân vùng `ai_context`

- `architecture/`: baseline kiến trúc hiện hành.
- `decisions/`: Decision Register và các amendment/policy hiện hành.
- `status/`: implementation truth.
- `tests/`, `testbenches/`, `verification/`: kiểm thử/reference, không tham gia deployment build.
- `evidence/`: bằng chứng theo scope.
- `build_guides/`: hướng dẫn, không có quyền ghi đè baseline.
- `migration/`: legacy/provenance; không có thẩm quyền kiến trúc.

## 8. Lưu quyết định mới

Mọi quyết định mới phải commit trực tiếp lên `main`, có ID, cập nhật Decision Register hoặc amendment được Decision Register dẫn chiếu. Nếu thay đổi kiến trúc thì cập nhật System Specification cùng commit. Chi tiết chưa khóa phải tạo open item riêng; không dùng trạng thái ghép hoặc tạo bản quyết định cạnh tranh.
