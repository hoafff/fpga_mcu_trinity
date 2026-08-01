# Chính sách cấu trúc source

## Quy tắc bắt buộc

1. Root chỉ có sáu thư mục `pc_host/`, `sn32/`, `primer1/`, `primer2/`,
   `tiny1p5/`, `ai_context/` và ba file `README.md`, `.gitignore`, `LICENSE`.
2. Năm target phải hoàn toàn self-contained và không tham chiếu source của target
   khác bằng đường dẫn tương đối.
3. Không tạo thư mục source dùng chung thứ bảy ở root.
4. Module cần dùng ở nhiều target (ví dụ CRC hoặc Ascon permutation) được copy
   vào từng target cần dùng. Mọi bản copy phải được kiểm checksum trong
   `ai_context/`.
5. Testbench, KAT, reference model, kiến trúc, interface, report, evidence và
   checker chỉ nằm trong `ai_context/`.
6. Target không được phụ thuộc `ai_context/` để build/nạp.
7. Không để README, log, report, ZIP, bitstream hoặc output/cache trong năm thư
   mục target.
8. Không import nguyên cây hoặc lịch sử `fpga-pqc-secure-telemetry`.

## Trạng thái scaffold

Trong commit khởi tạo sửa lỗi, mỗi target chỉ có `target.toml` để khóa danh tính
thiết bị, clock, vai trò và trạng thái triển khai. Khi source/project thật được
thêm, manifest phải đổi khỏi `NOT_IMPLEMENTED` trong cùng commit đã qua test.
