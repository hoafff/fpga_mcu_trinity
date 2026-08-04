# SN32 v0.7.26 ML-KEM hardware blocker

## Scope

This record applies to the exact SN32F407 deploy image:

- architecture: `0.7.26`
- build ID: `0x0007001A`
- Cortex-M0 at 12 MHz
- IROM: `0x7FFC` bytes
- IRAM: `0x2000` bytes
- reserved stack: `0x0800` bytes

## Observed hardware failure

A deterministic `GENERATE_KEYPAIR` request was accepted after the dual-SPI and retained self-test gate completed. The PC host timed out waiting for the response. Subsequent `PING` commands also timed out until the SN32 image was reloaded.

This behavior is consistent with the weak `HardFault_Handler` in the deploy startup file, which loops forever.

## Root cause

The exact v0.7.26 linker record reports:

- total RW size: 6888 bytes
- reserved stack: 2048 bytes
- total IRAM: 8192 bytes

The pinned portable `mlkem-native` ML-KEM-512 key generation path allocates the K-PKE key-generation polynomial matrix and multiple polynomial vectors as automatic local objects. For ML-KEM-512, the simultaneous automatic storage in `mlk_indcpa_keypair_derand()` alone exceeds the reserved 2048-byte stack. Nested FIPS-202 and sampling calls increase the peak further.

Therefore the current portable ML-KEM key-generation path is not deployable on the exact 8 KiB SN32F407 memory profile. Increasing the PC timeout cannot make it safe.

## Required correction

Do not claim ML-KEM keypair/session hardware integration PASS for v0.7.26.

Before hardware qualification resumes, one of the following must be implemented and exact-target linked:

1. a low-RAM sequential ML-KEM-512 implementation that reuses explicit static workspace and proves bounded stack use; or
2. an orchestrated P1-assisted ML-KEM datapath that streams polynomial operations through the already required NTT/INTT/BaseMul interface.

The correction must retain ML-KEM, NTT, INTT, BaseMul, session, Ascon, UART and safety functionality. Disabling ML-KEM is not an acceptable completion strategy.

## Immediate safety rule

PC host tooling must reject `GENERATE_KEYPAIR`, `CREATE_SESSION`, and the full secure-telemetry qualification command when connected to SN32 build `0x0007001A`. The dual-SPI control-plane qualification remains valid within its previously recorded scope.
