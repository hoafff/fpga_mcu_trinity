# FPGA MCU Trinity

`fpga_mcu_trinity` là dự án mới cho hệ thống gồm PC host, SONiX SN32F407F,
hai bo Gowin Primer 20K và một bo Gowin Tiny 1P5. Repository
`fpga-pqc-secure-telemetry` chỉ là nguồn tham khảo lịch sử; không phải baseline
kiến trúc hoặc source tree của dự án này.

```text
PC host <---UART---> SN32F407F ---shared SPI---> Primer #1 / Primer #2
Primer #1 ===== direct UART frame 66 byte =====> Primer #2
SN32 + hai Primer -------- heartbeat/fault ----> Tiny 1P5
Tiny 1P5 ----------------- secure/zeroize -----> hai Primer
```

## Nguồn chân lý

Đọc theo thứ tự:

1. `ai_context/README_AI.md`
2. `ai_context/architecture/FPGA_MCU_TRINITY_SYSTEM_SPEC_v0.3.md`
3. `ai_context/decisions/FPGA_MCU_TRINITY_DECISION_REGISTER_v0.3.md`
4. `ai_context/status/IMPLEMENTATION_STATUS.md`

Hai baseline v0.3 đã được phê duyệt về kiến trúc nhưng vẫn còn open item. Không
được tự triển khai phần phụ thuộc O-001, O-003, O-004, O-005 hoặc O-006.

## Cấu trúc repository

- `pc_host/`: code chạy trên PC.
- `sn32/`: firmware/project nạp SN32F407F.
- `primer1/`: RTL/project nạp Primer #1.
- `primer2/`: RTL/project nạp Primer #2.
- `tiny1p5/`: RTL/project nạp Tiny 1P5.
- `ai_context/`: toàn bộ kiến trúc, quyết định, memory/handoff, test, evidence,
  build guide và migration records.

Không tạo `docs/`, `rtl/`, `targets/`, `software/`, `tb/` hoặc `constraints/` ở
root. Nội dung không trực tiếp tham gia build/nạp của một target phải nằm trong
`ai_context/`.

## Trạng thái hiện tại

| Hạng mục | Trạng thái |
|---|---|
| Architecture baseline v0.3 | `CONFIRMED / OPEN ITEMS REMAIN` |
| PC host | `NOT IMPLEMENTED` |
| SN32 full firmware | `NOT IMPLEMENTED` |
| Primer #1 | `NOT IMPLEMENTED` |
| Primer #2 | `NOT IMPLEMENTED` |
| Tiny 1P5 source candidate | `TESTED — INHERITED SOURCE-ONLY` |
| Tiny exact-device build | `BUILD-PENDING` |
| P0-J19-001 migration | `29 FILES HASH-VERIFIABLE` |
| Wiring/hardware qualification | `PHYSICAL-PENDING` |

Không nối dây, program bo hoặc tuyên bố hardware-qualified chỉ từ source/evidence
hiện có.
