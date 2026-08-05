# FPGA MCU Trinity — Logical Pin Plan

**Status:** `CONFIRMED`  
**Physical qualification:** `PHYSICAL-PENDING`  
**Version:** `v0.1`  
**Date:** `2026-08-05`

This document authorizes RTL top ports, SN32 pinmux and CST entries. It does not
claim continuity, voltage, programming, timing or hardware PASS.

## PC ↔ SN32

```text
SN32 P3.1 TX -> USB-UART RX
SN32 P3.2 RX <- USB-UART TX
115200 8N1
```

## SN32 shared SPI ↔ Primer #1/#2

```text
SN32 P1.0 SCK  -> P1 J2-3 / P16; P2 J2-3 / P16
SN32 P1.2 MOSI -> P1 J2-5 / P15; P2 J2-5 / P15
SN32 P1.1 MISO <- P1 J2-7 / T15; P2 J2-7 / T15
SN32 P2.1 CS1_N  -> P1 J2-8  / R14
SN32 P2.3 IRQ1_N <- P1 J2-10 / T14
SN32 P2.2 CS2_N  -> P2 J2-8  / R14
SN32 P2.8 IRQ2_N <- P2 J2-10 / T14
```

Mode 0, MSB-first, bring-up 1 MHz. Never assert both CS signals. Deselected
MISO is high-Z. SN32 P1.8 remains inactive so the onboard W25Q16 is not selected.

## Direct payload UART

```text
P1 J2-11 / R13 / uart_tx_o -> P2 J2-11 / R13 / uart_rx_i
115200 8N1; frame 66 bytes; inter-frame idle >= 1 ms
```

`busy_o` is removed from R13 and deployment tops. It may not coexist with the
UART port on that net.

## Primer #1 CST mapping

```text
sys_clk_i          H11
rst_ni             A5
spi_sck_i          P16
spi_mosi_i         P15
spi_miso_o         T15
spi_cs_ni          R14
irq_no              T14
uart_tx_o          R13
fault_o            T13
fatal_latched_i    R12
secure_enable_i    T12
zeroize_ni         R11
heartbeat_o        T11
```

## Primer #2 CST mapping

```text
sys_clk_i          H11
rst_ni             A5
spi_sck_i          P16
spi_mosi_i         P15
spi_miso_o         T15
spi_cs_ni          R14
irq_no              T14
uart_rx_i          R13
fault_o            T13
fatal_latched_i    R12
secure_enable_i    T12
zeroize_ni         R11
heartbeat_o        T11
```

## Complete architecture with Tiny

Heartbeat and crypto-fault inputs:

```text
SN32 P2.9      -> Tiny J1-1  / pin 2 / hb_mcu_i
P1 J2-18 / T11 -> Tiny J1-2  / pin 3 / hb_pqc_i
P2 J2-18 / T11 -> Tiny J1-3  / pin 5 / hb_crypto_i
P2 J2-12 / T13 -> Tiny J1-11 / pin 15 / crypto_fault_i
```

Tiny outputs to both Primers:

```text
Tiny J1-7  / pin 10 / secure_enable_o -> P1/P2 J2-15 / T12
Tiny J1-8  / pin 11 / zeroize_no      -> P1/P2 J2-16 / R11
Tiny J1-10 / pin 14 / fault_latched_o -> P1/P2 J2-13 / R12
```

Polarity:

```text
secure_enable_o active-high
zeroize_no      active-low
fault_latched_o active-high
```

SESSION_COMMIT in the complete Tiny architecture:

```text
SN32 P3.8 / PAT17 / session_commit_toggle_o
-> Tiny J1-6 / pin 9 / session_commit_toggle_i
```

SN32 P3.8 has no alternate LED0 owner in the logical architecture, but the EVK
physical route remains evidence-sensitive. Tiny uses a two-flop synchronizer and
toggle detection. After Tiny reset, the observed level establishes the baseline
and is not a commit event. SN32 toggles only after both Primers report
`COMMITTED_BLOCKED`.

## Time-bounded no-Tiny core-demo override

This override applies only to SN32 v0.7.29 core-demo source candidate and must
not be combined with the Tiny wiring above.

```text
SN32 P2.9 / board-visible J7 header pin
    +--> P1 J2-15 / T12 / secure_enable_i
    +--> P2 J2-15 / T12 / secure_enable_i
```

Rules:

```text
Tiny is not connected.
P2.9 MCU heartbeat GPIO output is compile-time disabled.
P2.9 has one owner only: direct shared secure-enable.
P2.9 stays LOW through reset/staging and rises at session commit.
No ESP32, Tiny or second output may drive the shared T12 net.
Common 3.3 V logic ground is mandatory.
```

SysTick, cooperative progress leases, UART liveness and the internal fail-closed
heartbeat timeout remain enabled; only the physical P2.9 heartbeat waveform is
removed in this no-Tiny profile.

## Tiny logical CST

```text
clk_27m                  pin 4
hb_mcu_i                 pin 2
hb_pqc_i                 pin 3
hb_crypto_i              pin 5
tamper_ext_ni            pin 7
manual_fault_i           pin 8
session_commit_toggle_i  pin 9
secure_enable_o          pin 10
zeroize_no               pin 11
tiny_fault_no            pin 12
fault_latched_o          pin 14
crypto_fault_i           pin 15
btn_tamper_n             pin 35
btn_clear_n              pin 36
led_fault_o              pin 27
led_secure_o             pin 28
```

S2/pin 36 remains trusted manual clear. J1-6 no longer carries external
`clear_fault_i`; it carries the session-commit toggle. `tiny_fault_no` remains an
open-drain 0/Z output but is not wired to SN32 in the competition baseline.
