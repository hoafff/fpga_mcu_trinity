# FPGA MCU Trinity — Toolchain Lock

**Policy status:** `CONFIRMED`
**Authoritative SN32 S0 baseline:** `VALIDATED LOCAL ENVIRONMENT`
**SN32 S0 exact-build evidence:** `PASS WITH ONE EXPLICIT VENDOR WARNING`

## Authoritative SN32 S0 baseline

| Tool | Locked baseline | Evidence rule |
|---|---|---|
| Target device | `SN32F407F`, Cortex-M0 | project XML and ArmClang build evidence |
| Keil µVision | `5.43.1` | local build log |
| ARM Compiler | ArmClang `6.24` / ARM Compiler 6 | local build log and project XML |
| ARM CMSIS | package `6.2.0`, CORE component `6.1.1` | local build log and RTE project metadata |
| SONiX DFP | `SONiX.SN32F4_DFP 1.0.1` | local build log and project PackID |
| SONiX startup | `startup_SN32F400.s` from DFP 1.0.1 | RTE source list and linker map |
| SONiX system | `system_SN32F400.c` from DFP 1.0.1 | RTE source list and linker map |
| Baseline clock | `12 MHz` | project CPU lock and S0 source check |
| IROM | start `0x00000000`, size `0x7FFC` | project XML and linker map |
| IRAM | start `0x20000000`, size `0x2000` | project XML and linker map |
| Stack / heap | stack `0x200`, heap `0` | linker map; peak stack still requires later measurement |
| Gowin EDA | `V1.9.11.03 Education x64` | record exact banner/build in synthesis/P&R log |
| Gowin Programmer | bundled/current installation used with the above Gowin suite | record exact About/version output at programming |
| ModelSim | installer observed: `20.1.1.720`; local primary simulator | capture `vsim -version` at first regression/acceptance run |
| Python | project minimum `3.11+` | capture `python --version` |
| GCC | current stable installed | capture `gcc --version` |
| Icarus Verilog | optional portable CI/regression only | capture `iverilog -V` when used |

## S0 warning acceptance contract

S0 is accepted only when the build log proves all of the following:

```text
total_errors = 0
trinity_owned_source_warnings = 0
total_warnings <= 1
accepted_warning_file = RTE/Device/SN32F407F/system_SN32F400.c
accepted_warning_pack = SONiX.SN32F4_DFP 1.0.1
accepted_warning_cause = possible uninitialized use of AHB_prescaler
```

Waiver ID: `KNOWN_ACCEPTED_VENDOR_WARNING_SN32_DFP_1_0_1_AHB_PRESCALER`.

This is not a generic vendor-warning waiver. Any second warning, any warning from
Trinity-owned source, a different file, a different message, or a different DFP
version fails S0 acceptance. The vendor RTE source must not be patched, copied
from another DFP version, or suppressed with a pragma/global warning option.

## Historical donor baseline — not a Trinity dependency

The known-good donor remains valid provenance:

```text
repository = hoafff/MCU_dong_ho_so
commit     = d4412745f30f518f1c7a128cc494fa2678b4926c
board      = SN32F407F EVK, owner-confirmed programmed and running
historical ARM CMSIS package = 6.3.0, CORE = 6.2.0
historical SONiX DFP          = 1.1.1
```

Those donor pack versions explain how the original project metadata was derived.
They are not required by Trinity S0 and must not override the validated local
baseline above. Any future tool or pack change requires updating this lock and
regenerating the applicable build evidence.
