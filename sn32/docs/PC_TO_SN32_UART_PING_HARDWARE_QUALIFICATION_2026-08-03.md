# PC -> SN32 UART PING hardware qualification — 2026-08-03

## Decision

**PASS within the standalone PC-to-SN32 UART PING scope.**

Locked statement:

```text
PC <-> SN32 UART PING HARDWARE: PASS
```

The accepted run used the official `trinity-host` CLI and a byte-exact raw PING
check over an FT232RL YP-05 USB-to-UART adapter on Windows COM3.

This decision does not qualify Primer #1, Primer #2, dual-SPI, ML-KEM/Ascon
hardware execution, session establishment, Tiny 1P5 or the full system.

## Source and build identity

```text
repository = hoafff/fpga_mcu_trinity
source_commit = 40ff6f06ed32d3139899aae291047f35d0740f86
source_message = ci(sn32): enforce exact 32K Keil size profile
mlkem_submodule = 048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa
```

Exact Keil rebuild evidence:

```text
ArmClang 6.24
Program Size: Code=23228 RO-data=776 RW-data=100 ZI-data=4532
0 Error(s), 0 Warning(s)
```

Accepted linker fit:

```text
Flash = 24104 / 32764 bytes = PASS
RAM   = 4632 / 8192 bytes   = PASS
AXF generation              = PASS
HEX generation              = PASS
SN32 flash programming      = PASS as reported by the hardware run
```

The Flash/RAM result applies to the exact full-deploy image at the source commit
above. It is not a hardware-functional qualification of the cryptographic or
Primer-control paths.

## Hardware boundary

Connected:

```text
PC -> FT232RL YP-05 -> SN32F407 UART0
COM port = COM3
UART     = 115200 baud, 8 data bits, no parity, 1 stop bit
```

Explicitly disconnected:

```text
Primer #1
Primer #2
Tiny 1P5
```

The test therefore isolates the PC host, USB-UART adapter, SN32 UART pins,
firmware receive/dispatch/transmit path and the PING command.

## Preconditions

The following checks were completed before accepting the CLI result:

```text
PC import points to current checkout: PASS
PING wire frame byte-exact:          PASS
FT232 TX<->RX loopback:              PASS
Raw PING PC -> SN32 -> PC:           PASS
```

Host environment:

```text
Python 3.11.6
trinity-host 0.2.0 installed editable from .\pc_host
COM3 | USB Serial Port (COM3) | USB VID:PID=0403:6001 SER=A5069RR4A
```

## Raw frame evidence

Request transmitted:

```text
03 01 01 01 01 02 01 01 03 f9 bc 00
```

Response received:

```text
04 01 01 01 01 02 01 02 04 01 05 17 f3 44 7f 00
```

Decoded response raw frame:

```text
01 01 01 00 00 01 00 04 00 00 17 f3 44 7f
```

Decoded fields:

```text
protocol_version = 0x01
command          = 0x01 PING
flags            = 0x01 RESPONSE
reserved         = 0x00
transaction_id   = 0x0001
payload_length   = 4
uptime_ms         = 6131
crc16             = 0x447f
```

This confirms a valid response rather than an adapter echo: the response has a
response flag, four-byte uptime payload and a new CRC.

## Official CLI evidence

Three accepted runs:

```text
trinity-host --port COM3 ping
[PING]
result=PASS
uptime_ms=126699

trinity-host --port COM3 ping
[PING]
result=PASS
uptime_ms=166390

trinity-host --port COM3 ping
[PING]
result=PASS
uptime_ms=171063
```

The monotonically increasing uptime confirms that the SN32 millisecond timebase
and foreground PC-command loop continued running between independent CLI
processes.

Raw evidence is retained at:

```text
sn32/hardware/pc_uart_ping/evidence/pc_uart_ping_2026-08-03.txt
```

## Earlier timeout disposition

The earlier repeated timeout is not retained as a firmware or UART failure. The
observed cause was a loose/intermittent USB cable connection to the USB-to-UART
adapter. Replacing the cable produced successful raw and official-CLI PING runs.

## Qualification boundary

Permitted claim:

```text
PC <-> SN32 UART PING HARDWARE: PASS
```

Not permitted from this evidence:

```text
SN32 -> Primer #1 SPI:              NOT RUN
SN32 -> Primer #2 SPI:              NOT RUN
SN32 dual-SPI control plane:        NOT RUN
ML-KEM hardware execution:          NOT RUN
Ascon hardware execution:           NOT RUN
session integration:                NOT RUN
Tiny safety integration:            NOT RUN
full-system hardware qualification: NOT RUN
```

The global flags therefore remain:

```text
hardware_qualified = false
full_system_hardware_qualified = false
```

## Next gate

The next isolated hardware gate is:

```text
SN32 -> Primer #1 / Primer #2 dual-SPI control plane
```

It must preserve the already qualified direct P1-to-P2 UART implementation but
must initially test only SPI discovery/status/self-test behavior. Tiny remains
disconnected and no full-system claim is allowed.

Execution plan:

```text
sn32/docs/SN32_DUAL_SPI_HARDWARE_QUALIFICATION_NEXT_GATE.md
```
