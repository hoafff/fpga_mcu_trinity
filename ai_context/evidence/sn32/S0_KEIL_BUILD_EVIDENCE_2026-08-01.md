# SN32F407F S0 Keil Build Evidence — 2026-08-01

**Evidence class:** sanitized exact-build record
**Project source commit:** `bbe00bd6909848b86ec06c0335c837d02874c3b4`
**Hardware programming:** `NOT TESTED`
**Hardware execution:** `NOT TESTED`

This document was derived from the user-provided Keil build log and linker map.
License data, account names, machine-specific paths and local installation paths
were removed. The raw files are not committed.

## Input evidence identity

```text
raw build log SHA-256:
0dad9662ca13aaf78d2cfa07cc52f7ff8ef8cfddb96be6e546ac6d8c6817d6bf

raw linker map SHA-256:
0dfe9c7bf6aeb0e2fa0b287f7f5f1671e869c7a0cbf26ac7b7063947c4d5e121
```

## Validated environment

```text
Target device:    SN32F407F
Core:             Cortex-M0
Keil µVision:     5.43.1
Compiler:         ArmClang 6.24 / ARM Compiler 6
ARM CMSIS pack:   6.2.0
CMSIS CORE:       6.1.1
SONiX SN32F4 DFP: 1.0.1
```

## Build result

```text
Sources compiled/assembled:
- RTE/Device/SN32F407F/startup_SN32F400.s
- RTE/Device/SN32F407F/system_SN32F400.c
- sn32/src/app/trinity_main.c

Total errors:                    0
Total warnings:                  1
Trinity-owned source warnings:   0
Accepted vendor warnings:        1
AXF generated:                   yes
HEX generated:                   yes
MAP generated:                   yes
Program Size: Code=1240 RO-data=208 RW-data=0 ZI-data=616
```

## Exact accepted warning

```text
Classification: KNOWN_ACCEPTED_VENDOR_WARNING
Waiver ID: KNOWN_ACCEPTED_VENDOR_WARNING_SN32_DFP_1_0_1_AHB_PRESCALER
File: RTE/Device/SN32F407F/system_SN32F400.c
Pack: SONiX.SN32F4_DFP 1.0.1
Compiler diagnostic: variable 'AHB_prescaler' is used uninitialized whenever
                     switch default is taken [-Wsometimes-uninitialized]
Cause summary: possible uninitialized use of AHB_prescaler
```

The warning is in vendor RTE source, not `trinity_main.c`. The vendor file was
not modified, replaced, copied from DFP 1.1.1 or suppressed. This waiver permits
only this one warning under DFP 1.0.1. Any additional warning, any warning from
Trinity-owned source, or a different warning fails S0 acceptance.

## Linker-map validation

```text
IROM: 0x00000000, maximum size 0x7FFC
IRAM: 0x20000000, maximum size 0x2000
Load region used: 0x5A4 bytes
Total RO size: 1448 bytes
Total RW/ZI size: 616 bytes
Stack reservation: 0x200 bytes
Heap reservation: 0 bytes
Special SONiX region: 0x00007FFC, size 4 bytes
```

The map contains only the expected S0 application and pack sources. It does not
contain legacy FPST mains, UART, SPI, ML-KEM, session, Tiny-control or payload
relay implementation.

## Acceptance status

```text
S0 project structure:              PASS
SN32F407F compile/link:            PASS
AXF/HEX/MAP generation:           PASS
Memory layout:                    PASS
Exact current-environment lock:   PASS
Trinity-owned source warnings:    PASS — 0
Known vendor warning:             ACCEPTED — 1
Hardware programming:             NOT TESTED
Hardware execution:               NOT TESTED
S1+:                              NOT STARTED
```
