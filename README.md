# FPGA MCU Trinity

`fpga_mcu_trinity` là dự án mới, tinh giản cho hệ thống gồm PC host, SONiX
SN32F407F, hai bo Gowin Primer 20K và một bo Gowin Tiny 1P5. Repository cũ
`fpga-pqc-secure-telemetry` chỉ là nguồn tham khảo; cây source cũ không phải cấu
trúc triển khai của repository này.

```text
PC host --UART--> SN32F407F --shared SPI--> Primer #1 / Primer #2
Primer #1 -------- UART frame 60 byte ----> Primer #2
SN32 + hai Primer --heartbeat/fault-------> Tiny 1P5
Tiny 1P5 ----------secure/zeroize---------> hai Primer
```

## Cấu trúc

- `pc_host/`: ứng dụng PC.
- `sn32/`: firmware SN32F407F.
- `primer1/`: RTL/project Primer #1.
- `primer2/`: RTL/project Primer #2.
- `tiny1p5/`: RTL/constraint Tiny 1P5.
- `ai_context/`: kiến trúc, quyết định, testbench, evidence và checker.

## Trạng thái hiện tại

| Hạng mục | Trạng thái |
|---|---|
| Kiến trúc v1.8 | `LOCKED` |
| Overlay P0-J19-001, đủ 29 file | `MIGRATED / EXACT HASH MANIFEST PROVIDED` |
| Tiny 1P5 source candidate | `PASS — SOURCE-ONLY (inherited evidence)` |
| Tiny exact-device Gowin build | `PENDING — USER BUILD` |
| SN32 P0.10/P0.11 guard | `PASS — SOURCE-ONLY (inherited evidence)` |
| SN32 exact-target Keil build | `NOT STARTED` |
| PC host, Primer #1, Primer #2 mới | `NOT IMPLEMENTED` |
| Hardware route J1-9 ↔ P0.10 | `BLOCKED / KEEP DISCONNECTED` |

Không được nối Tiny `J1-9` với SN32 `P0.10/J11-1`, program bo hoặc tuyên bố
hardware-qualified chỉ từ source trong repository. Hướng dẫn và trạng thái chi
tiết nằm tại `ai_context/README_AI.md`.
