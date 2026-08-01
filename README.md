# FPGA MCU Trinity

New competition project for PC host, SN32F407F, two Gowin Primer 20K boards and
one Tiny 1P5 supervisor. The old `fpga-pqc-secure-telemetry` repository is
reference history only.

```text
PC <---UART---> SN32 ---shared SPI---> P1 / P2
P1 ===== direct UART 66-byte frame ===> P2
SN32/P1/P2 ---- heartbeat/fault ------> Tiny
Tiny ---------- secure/zeroize -------> P1/P2
```

## Project memory

Start at `ai_context/README_AI.md`. Active baseline:

- `ai_context/architecture/FPGA_MCU_TRINITY_SYSTEM_SPEC_v0.4.md`
- `ai_context/decisions/FPGA_MCU_TRINITY_DECISION_REGISTER_v0.4.md`
- `ai_context/interfaces/` ICD/backend specifications
- `ai_context/status/OPEN_ITEMS.md`

The v0.4 documentation consolidates approved D01–D60 decisions. Full integrated
source is not yet authorized until the owner reviews the derived ICD details and
closes O-012–O-015 as stated in the open-item register.

## Repository placement

Target build/program source belongs in `pc_host/`, `sn32/`, `primer1/`,
`primer2/`, `tiny1p5/`. Everything else belongs under `ai_context/`.
`.github/workflows/` is an explicit portable-CI-only exception.

No current exact-device or hardware PASS is claimed.
