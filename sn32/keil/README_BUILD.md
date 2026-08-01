# SN32F407F S0 Keil build

This project is the Trinity v0.4 exact-target bring-up project. It is not the
clock application and it does not compile either legacy FPST `main()`.

## Locked environment

- Device: `SN32F407F`, Cortex-M0
- Keil µVision: `5.43.1`
- Compiler: ArmClang `6.24` / ARM Compiler 6
- Pack: `SONiX.SN32F4_DFP.1.0.1`
- CMSIS package: `ARM.CMSIS.6.2.0` (`CORE` component `6.1.1`)
- Baseline clock: `12 MHz`
- IROM: `0x00000000`, size `0x7FFC`
- IRAM: `0x20000000`, size `0x2000`
- Startup stack: `0x200` bytes; heap: `0`

The original project metadata was derived from the known-good
`hoafff/MCU_dong_ho_so` donor. Its CMSIS 6.3.0 / CORE 6.2.0 and DFP 1.1.1
versions are historical provenance only. They are not Trinity S0 dependencies.

## Open and build

1. Pull the latest `main` branch.
2. Confirm these packs are installed in Pack Installer:
   - `ARM::CMSIS@6.2.0`
   - `SONiX::SN32F4_DFP@1.0.1`
3. Open `sn32/keil/trinity_sn32f407.uvprojx` in µVision.
4. If µVision reports unresolved RTE files, open **Project → Manage → Run-Time
   Environment**, keep **CMSIS:CORE** and **Device:Startup** selected, then click
   **Resolve** and **OK**. This creates ignored local `RTE/` instances from the
   installed packs.
5. Select target `trinity_sn32f407`.
6. Run **Project → Rebuild all target files**.
7. Do not connect or exercise P1, P2 or Tiny during S0. UART, SPI, ML-KEM,
   SESSION_COMMIT and DEMO_SECURE remain compile-time disabled.

The project requests executable/AXF, Intel HEX, debug information, linker MAP,
cross-reference and call-graph information.

## S0 acceptance rule

A build passes S0 only when:

```text
0 errors
0 warnings from Trinity-owned source
maximum 1 warning, exactly:
  file: RTE/Device/SN32F407F/system_SN32F400.c
  pack: SONiX.SN32F4_DFP 1.0.1
  cause: possible uninitialized use of AHB_prescaler
```

Waiver ID:
`KNOWN_ACCEPTED_VENDOR_WARNING_SN32_DFP_1_0_1_AHB_PRESCALER`.

Do not patch the RTE source, copy a replacement from DFP 1.1.1, or suppress the
warning globally. Any second warning or any Trinity-source warning fails S0.

## Validated S0 build

The sanitized evidence records:

```text
0 Error(s), 1 Warning(s)
Program Size: Code=1240 RO-data=208 RW-data=0 ZI-data=616
FromELF: creating hex file
```

The map confirms only `startup_SN32F400.s`, `system_SN32F400.c` and
`trinity_main.c` are linked; IROM/IRAM match the lock; stack is 0x200 and heap is
0. Hardware programming and execution have not been tested.

Expected generated paths remain under ignored `Objects/`, `Listings/` and `RTE/`
directories. Do not commit AXF, HEX, MAP, raw build logs, user metadata or local
machine paths. See the sanitized evidence document under
`ai_context/evidence/sn32/`.
