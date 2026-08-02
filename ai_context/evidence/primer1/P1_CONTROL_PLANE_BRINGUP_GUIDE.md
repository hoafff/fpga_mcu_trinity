# SN32 ↔ Primer #1 control-plane bring-up guide

## Authorized scope

Only the following gate is authorized:

```text
PC -> SN32 PING
SN32 -> P1 GET_INFO
SN32 -> P1 GET_STATUS
SN32 -> P1 RUN_SELF_TEST
SN32 -> P1 GET_TXN_RESULT
SN32 -> P1 RETIRE_TXN_RESULT
```

Do not connect Primer #2 or issue session/encryption commands in this gate.

## Required projects

- Primer #1 bitstream: `primer1/gowin/impl/pnr/trinity_primer1.fs`.
- SN32 Keil project: `sn32/keil/trinity_sn32f407_deploy.uvprojx`.
- PC host: install `pc_host/`, then run `python -m trinity_host.cli`.

The SN32 deploy source is configured with `TRINITY_DEPLOY_P1_BRINGUP_ONLY=1`.
Its exact ArmClang build and flash must be repeated after pulling the commit that
contains this guide.

## Wiring

Shared logic ground is mandatory. Do not connect the boards' 5 V or 3.3 V rails
together when they are powered independently.

```text
SN32F407 EVK                 Primer #1
P1.0 / J12 DB_SPI SCK   ->   P16 / J2-3  spi_sck_i
P1.2 / J12 DB_SPI MOSI  ->   P15 / J2-5  spi_mosi_i
P1.1 / J12 DB_SPI MISO  <-   T15 / J2-7  spi_miso_o
P2.1 / J7 CS1_N         ->   R14 / J2-8  spi_cs_ni
P2.3 / J7 IRQ1_N        <-   T14 / J2-10 irq_no
GND                      <->  GND / J2-14
```

PC UART through the USB-UART adapter:

```text
SN32 P3.1 / J10 UTX -> adapter RX
SN32 P3.2 / J10 URX <- adapter TX
SN32 GND            <-> adapter GND
baud 115200, 8N1
```

## Safety jumpers before Tiny integration

Keep the standalone safety jumpers installed:

```text
Primer fatal_latched_i R12/J2-13 -> GND/J2-14
Primer secure_enable_i T12/J2-15 -> GND/J2-14
Primer zeroize_ni      R11/J2-16 -> 3V3/J2-17
```

This keeps P1 safe and permits self-test while preventing session activation.

## Power/program/reset order

1. Turn both boards off and complete wiring/common-ground checks.
2. Install the three safety jumpers above.
3. Power Primer #1 and load `trinity_primer1.fs` with JTAG `SRAM Program`.
4. Verify Programmer reports success and the P1 heartbeat is present.
5. Power SN32, build/flash the deploy Keil target, then reset or run SN32.
6. Connect/open the PC USB-UART port only after SN32 is running.
7. Run the PC command below.

If Primer #1 loses power, reload `.fs` and reset SN32 so it reprobes P1.

## PC command

From the repository root on Windows:

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install -e pc_host
python -m trinity_host.cli ports
python -m trinity_host.cli --port COM7 p1-bringup
```

Replace `COM7` with the USB-UART port connected to SN32.

## Expected result

```text
[PING]
result=PASS

[P1_GET_INFO]
result=PASS
primer1_build_id=0x50310001

[P1_GET_STATUS]
result=PASS
target_ready_mask=0x03
system_state=SELF_TEST_REQUIRED
fault_flags=0x00

[P1_RUN_SELF_TEST]
result=ACCEPTED

[P1_GET_TXN_RESULT]
state=RUNNING
...
[P1_GET_TXN_RESULT]
state=SUCCEEDED
result_code=OK
result_data_hex=013e

[P1_RETIRE_TXN_RESULT]
result=PASS

[P1_GET_STATUS_FINAL]
result=PASS
system_state=READY_NO_SESSION
fault_flags=0x00

[P1_CONTROL_PLANE_SELF_TEST]
result=PASS
```

A different COM port number or transaction ID is normal. A missing P1 returns a
remote error or a ready mask without bit `0x02`; do not proceed to later gates.
