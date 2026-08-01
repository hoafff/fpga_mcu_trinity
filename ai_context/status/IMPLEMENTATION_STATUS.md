# Implementation Status

Baseline: kiến trúc v1.8 của dự án mới `fpga_mcu_trinity`.

| Target/gate | Source | Generic test | Exact build | Hardware |
|---|---|---|---|---|
| PC host | `NOT IMPLEMENTED` | `NOT STARTED` | `NOT STARTED` | — |
| SN32F407F | `NOT IMPLEMENTED` | `NOT STARTED` | `NOT STARTED` | `NO` |
| Primer #1 | `NOT IMPLEMENTED` | `NOT STARTED` | `NOT STARTED` | `NO` |
| Primer #2 | `NOT IMPLEMENTED` | `NOT STARTED` | `NOT STARTED` | `NO` |
| Tiny 1P5 | `NOT IMPLEMENTED` | `NOT STARTED` | `NOT STARTED` | `NO` |
| Repository layout checker | `IMPLEMENTED` | `PASS` khi checker exit 0 | — | — |

Không kế thừa nhãn PASS/source-only/build/hardware từ repo cũ. Evidence cũ chỉ
có thể dùng làm known-good reference cho bo/toolchain hoặc module cụ thể sau khi
đối chiếu; nó không tự động qualify source mới.

## Gate tiếp theo

Triển khai theo target, bắt đầu từ interface và reference/KAT trong
`ai_context/`; không đưa source dùng chung trở lại root. Mỗi commit phải cập nhật
bảng này theo đúng mức bằng chứng thực tế.
