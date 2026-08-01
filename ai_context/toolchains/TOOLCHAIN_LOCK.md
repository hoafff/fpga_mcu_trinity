# FPGA MCU Trinity — Toolchain Lock

**Policy status:** `CONFIRMED`  
**Runtime evidence:** `PENDING`  
**Source implementation:** `NON-BLOCKING`

| Tool | Baseline policy | Runtime evidence rule |
|---|---|---|
| Gowin EDA | `V1.9.11.03 Education x64` | record exact banner/build in synthesis/P&R log |
| Gowin Programmer | bundled/current installation used with the above Gowin suite | record exact About/version output at programming |
| ModelSim | installer observed: `20.1.1.720`; local primary simulator | capture `vsim -version` at first regression/acceptance run |
| Keil µVision | latest installed KeilV6 project environment | capture exact µVision version in acceptance evidence |
| ARM Compiler | `ARM Compiler 6` | capture compiler banner in build log |
| SONiX DFP | `SONIX.SN32F4_DFP 1.1.1.1` | retain pack filename/version in build evidence |
| SONiX reference | SN32F407 CMSIS Firmware Library + SN32F407 EVK DEMO KeilV6 | record exact source/package revision when imported |
| Python | latest stable installed, project minimum `3.11+` | capture `python --version` |
| GCC | latest stable installed | capture `gcc --version` |
| Icarus Verilog | optional portable CI/regression only; ModelSim remains local primary | capture `iverilog -V` when used |

Exact ModelSim/Keil/Python/GCC runtime versions are acceptance evidence, not a
source-start blocker. After an acceptance baseline is created, no tool may be
upgraded or replaced without updating this lock file and rerunning applicable
evidence.
