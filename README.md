# FPGA MCU Trinity

`fpga_mcu_trinity` là dự án mới cho hệ thống gồm PC host, SONiX
SN32F407F, hai bo Gowin Primer 20K và một bo Gowin Tiny 1P5.

Repository này **không phải bản sao** của `fpga-pqc-secure-telemetry`. Repo cũ
chỉ được dùng làm tài liệu tham khảo theo từng module/thuật toán; cây thư mục,
wrapper, interface và lịch sử của repo cũ không phải baseline triển khai ở đây.

## Kiến trúc đã chốt

```text
PC host
   | UART 115200 8N1
   v
SN32F407F
   | shared SPI Mode 0, MSB-first, bring-up 1 MHz
   +---------------------> Primer #1: ML-KEM math + Ascon encrypt + TX
   +---------------------> Primer #2: Ascon decrypt/tag verify + replay + RX

Primer #1 -- UART một chiều, frame cố định 60 byte --> Primer #2

SN32 / Primer #1 / Primer #2 -- heartbeat/fault --> Tiny 1P5
Tiny 1P5 -- secure_enable / zeroize -----------> hai Primer
```

Tiny 1P5 nằm ngoài đường payload. SN32 điều khiển ML-KEM-512 cấp cao, hash/KDF,
entropy/session và giao tiếp PC; Primer #1 chỉ tăng tốc phép toán ML-KEM thực
(`NTT`, `INTT`, `MultiplyNTTs/BaseCaseMultiply`) rồi mã hóa; Primer #2 xác thực
tag trước khi cho phép plaintext đi tiếp.

## Hợp đồng mật mã và frame

- ML-KEM-512 hoàn chỉnh trong demo.
- `n = 256`, `q = 3329`, hệ số 16 bit; I/O NTT ở standard domain, Montgomery
  chỉ dùng nội bộ.
- Ascon-AEAD128 theo NIST SP 800-232: encrypt ở Primer #1, decrypt/tag verify ở
  Primer #2.
- Mỗi session cần 32 byte CSPRNG entropy từ PC; KAT dùng seed vector cố định.
- Plaintext 24 byte, ciphertext 24 byte, tag 16 byte.
- Frame UART P1→P2 cố định 60 byte: `SYNC(2) + COMMAND(1) + btp_txn_id(1) +
  LENGTH(2) + session_id(4) + sequence(8) + ciphertext(24) + tag(16) + CRC-16(2)`.
- `SYNC = A5 5A`, `COMMAND = 0x60`, `LENGTH = 0x0034`, sequence bắt đầu từ 1,
  `btp_txn_id = (sequence - 1) mod 256`.
- Không giữ retry timeout, response cache, retained packet hoặc payload buffer
  lớn của kiến trúc cũ.

## Cấu trúc repository

```text
/
├── pc_host/       # ứng dụng chạy trên PC
├── sn32/          # firmware/project Keil cho SN32F407F
├── primer1/       # project Gowin self-contained cho Primer #1
├── primer2/       # project Gowin self-contained cho Primer #2
├── tiny1p5/       # project Gowin self-contained cho Tiny 1P5
├── ai_context/    # kiến trúc, interface, KAT, test, evidence và checker
├── README.md
├── .gitignore
└── LICENSE
```

Năm thư mục target phải tự build độc lập. Không tạo kho source dùng chung kiểu
`rtl/`, `targets/`, `tb/`, `software/` hay `constraints/` ở root. Nếu hai target
cùng cần CRC hoặc Ascon permutation thì mỗi target giữ một bản source của chính
nó; checker trong `ai_context/` chịu trách nhiệm phát hiện các bản copy bị lệch.
Target không được phụ thuộc `ai_context/` để build hoặc nạp.

## Trạng thái hiện tại

Đây là baseline cấu trúc sạch sau khi loại bỏ lần import nhầm repo cũ. Các file
`target.toml` chỉ khóa thiết bị, vai trò và công cụ dự kiến; source triển khai mới
chưa được coi là hoàn thành hoặc hardware-qualified.

| Hạng mục | Trạng thái |
|---|---|
| Kiến trúc và chính sách source | `LOCKED` |
| Cấu trúc repository mới | `PASS` |
| PC host mới | `NOT IMPLEMENTED` |
| SN32 exact-target firmware | `NOT IMPLEMENTED` |
| Primer #1 exact-device RTL | `NOT IMPLEMENTED` |
| Primer #2 exact-device RTL | `NOT IMPLEMENTED` |
| Tiny 1P5 exact-device RTL | `NOT IMPLEMENTED` |
| Hardware-qualified | `NO` |

Không dùng commit import cũ làm baseline build/nạp. Trạng thái triển khai chi
tiết nằm tại `ai_context/status/IMPLEMENTATION_STATUS.md`.
