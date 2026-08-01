# FPGA MCU Trinity — Toolchain Lock

**Policy status:** `CONFIRMED`
**Trinity exact-build evidence:** `PENDING`
**Known-good SN32 donor evidence:** `CONFIRMED BY OWNER`

| Tool | Locked baseline | Evidence rule |
|---|---|---|
| Keil µVision | `5.43.1` | donor build log confirms; capture Trinity S0 build log |
| ARM Compiler | ArmClang `6.24` / ARM Compiler 6 | donor build log confirms; capture Trinity compiler banner |
| ARM CMSIS | package `6.3.0`, CORE component `6.2.0` | resolve through Keil RTE and retain selected-pack evidence |
| SONiX DFP | `SONiX.SN32F4_DFP 1.1.1` | project PackID locked; retain Pack Installer evidence |
| SONiX startup | Device:Startup component `1.0.1`; `startup_SN32F400.s` instance `1.0.3` | generated from installed DFP; stack `0x200`, heap `0` |
| SONiX system | `system_SN32F400.c` instance `1.0.1` | generated from installed DFP; 12 MHz IHRC baseline |
| Gowin EDA | `V1.9.11.03 Education x64` | record exact banner/build in synthesis/P&R log |
| Gowin Programmer | bundled/current installation used with the above Gowin suite | record exact About/version output at programming |
| ModelSim | installer observed: `20.1.1.720`; local primary simulator | capture `vsim -version` at first regression/acceptance run |
| Python | latest stable installed, project minimum `3.11+` | capture `python --version` |
| GCC | latest stable installed | capture `gcc --version` |
| Icarus Verilog | optional portable CI/regression only; ModelSim remains local primary | capture `iverilog -V` when used |

Known-good donor:

```text
repository = hoafff/MCU_dong_ho_so
commit     = d4412745f30f518f1c7a128cc494fa2678b4926c
board      = SN32F407F EVK, owner-confirmed programmed and running
```

The donor proves that this exact device/tool/pack combination is viable. It does
not prove the new Trinity S0 project until that project is built locally and its
AXF/HEX/MAP evidence is reviewed. After a Trinity acceptance baseline is created,
no tool may be upgraded or replaced without updating this lock and rerunning the
applicable evidence.
