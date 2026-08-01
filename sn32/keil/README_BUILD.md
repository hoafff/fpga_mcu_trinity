# SN32F407F S0 Keil build

This project is the Trinity v0.4 exact-target bring-up project. It is not the
clock application and it does not compile either legacy FPST `main()`.

## Locked environment

- Device: `SN32F407F`, Cortex-M0
- Keil µVision: `5.43.1`
- Compiler: ArmClang `6.24` / ARM Compiler 6
- Pack: `SONiX.SN32F4_DFP.1.1.1`
- CMSIS package: `ARM.CMSIS.6.3.0` (`CORE` component `6.2.0`)
- Baseline clock: `12 MHz`
- IROM: `0x00000000`, size `0x7FFC`
- IRAM: `0x20000000`, size `0x2000`
- Startup stack: `0x200` bytes; heap: `0`

The project uses the same SONiX RTE startup/system selection as the known-good
`hoafff/MCU_dong_ho_so` donor at commit
`d4412745f30f518f1c7a128cc494fa2678b4926c`.

## Open and build

1. Pull the latest `main` branch.
2. Confirm these packs are installed in Pack Installer:
   - `ARM::CMSIS@6.3.0`
   - `SONiX::SN32F4_DFP@1.1.1`
3. Open `sn32/keil/trinity_sn32f407.uvprojx` in µVision.
4. If µVision reports unresolved RTE files, open **Project → Manage → Run-Time
   Environment**, keep **CMSIS:CORE** and **Device:Startup** selected, then click
   **Resolve** and **OK**. This creates the ignored local `RTE/` instances from
   the installed packs.
5. Select target `trinity_sn32f407`.
6. Run **Project → Rebuild all target files** or press `F7`.
7. Do not connect or exercise P1, P2 or Tiny during S0. UART, SPI, ML-KEM,
   SESSION_COMMIT and DEMO_SECURE are compile-time disabled.

The project is configured to request:

- executable/AXF;
- Intel HEX;
- debug information;
- linker map;
- cross-reference and call-graph information.

Expected generated locations after a successful local build:

```text
sn32/keil/Objects/trinity_sn32f407.axf
sn32/keil/Objects/trinity_sn32f407.hex
sn32/keil/Objects/trinity_sn32f407.build_log.htm
sn32/keil/Listings/trinity_sn32f407.map
```

Exact output naming may vary slightly with µVision, but generated files must stay
uncommitted.

## Files to return after build

- complete build log;
- linker `.map`;
- every error and warning;
- Program Size line;
- screenshot of target device, compiler and selected packs;
- generated `.hex`, or the exact reason it was not generated.

No Keil, resource, programming or hardware PASS is claimed by the S0 source
commit itself.
