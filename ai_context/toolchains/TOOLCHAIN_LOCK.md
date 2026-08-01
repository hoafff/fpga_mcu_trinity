# FPGA MCU Trinity — Toolchain Lock

**Status:** `OPEN`  
**Open item:** O-012  
**Rule:** Không bắt đầu target implementation hoặc thay đổi toolchain cho tới khi
các giá trị chính xác dưới đây được trích xuất/cung cấp và commit.

| Tool | Exact version/build | Evidence source |
|---|---|---|
| Gowin EDA | `OPEN` | About dialog / installer / build log |
| Gowin Programmer | `OPEN` | About dialog |
| Keil µVision | `OPEN` | About dialog |
| ARM Compiler | `OPEN` | build log / compiler banner |
| SONiX DFP/SDK | `OPEN` | Pack Installer / SDK manifest |
| Python | `OPEN` | `python --version` |
| Icarus Verilog | `OPEN` | `iverilog -V` |
| GCC reference-test compiler | `OPEN` | `gcc --version` |

After lock, no automatic upgrade between baseline and acceptance. Any change
requires an amendment and rerun of applicable tests/build evidence.
