# FPGA MCU Trinity — Open Items and Closures

**Version:** `v0.4`  
**Date:** `2026-08-01`

## Closed in this documentation update

| ID | Status | Closure |
|---|---|---|
| O-001 | `CONFIRMED` | KDF byte-exact and collision policy |
| O-003 | `CONFIRMED` | mlkem-native v1.0.0 exact pin and FIPS 203 errata record |
| O-004 | `CONFIRMED` | SPI header/txid/CRC/max-size contract |
| O-005 | `CONFIRMED` | SESSION_COMMIT toggle contract |
| O-006 | `CONFIRMED` | UART idle gap 1 ms |
| O-011 | `CONFIRMED` | initial PC timeout classes |

## Still open/pending

| ID | Status | Owner input/evidence needed | Blocks |
|---|---|---|---|
| O-002 | `OPEN` | secure entropy trust model/source/evidence | DEMO_SECURE claim only |
| O-008 | `PHYSICAL-PENDING` | schematic/constraint/pin/pull/voltage evidence | final CST/wiring/programming |
| O-009 | `BUILD-PENDING` | exact Gowin/Keil build and hardware evidence | resource/timing/hardware PASS |
| O-012 | `OPEN` | exact installed toolchain versions | target implementation start |
| O-013 | `OPEN` | owner review of SPI ICD derived payloads/error numbers | SPI RTL/firmware decoder |
| O-014 | `OPEN` | owner review of PC ICD derived payloads/event envelope | host/SN32 protocol implementation |
| O-015 | `OPEN` | owner review of BaseMul wrapper and error-latch mapping | ML-KEM accelerator adapter |
