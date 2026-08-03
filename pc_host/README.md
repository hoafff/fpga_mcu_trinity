# Trinity PC host — SN32 hardware bring-up

The CLI implements the binary PC↔SN32 protocol used by the full SN32F407 deploy
firmware. It supports the standalone UART PING gate, retained transaction
inspection, the earlier P1 control-plane flow, and the scoped P1/P2 dual-SPI
qualification flow.

## Install

From the repository root on Windows:

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e pc_host
```

List ports:

```bat
trinity-host ports
```

## Standalone PC ↔ SN32 UART gate

No Primer or Tiny board is required:

```bat
trinity-host --port COM3 --baud 115200 ping
```

Accepted result:

```text
[PING]
result=PASS
uptime_ms=<increasing value>
```

This command qualifies only the PC-to-SN32 UART PING path.

## Generic system queries

These commands cause SN32 to access both Primer SPI endpoints:

```bat
trinity-host --port COM3 system-info
trinity-host --port COM3 system-status
```

They are not standalone UART tests. Both P1 and P2 must be correctly wired and
running compatible bitstreams.

The older `p1-info` and `p1-status` spellings remain compatibility aliases for
these full-system queries.

## Scoped SN32 dual-SPI control-plane gate

After completing the wiring and safety preflight in:

```text
sn32/docs/SN32_DUAL_SPI_HARDWARE_QUALIFICATION_NEXT_GATE.md
```

run:

```bat
trinity-host --port COM3 dual-spi-bringup --timeout 10 --poll 0.1
```

The command performs:

```text
PC -> SN32 PING
SN32 -> P1 GET_INFO
SN32 -> P2 GET_INFO
SN32 -> P1 GET_STATUS
SN32 -> P2 GET_STATUS
SN32 -> P1 RUN_SELF_TEST with mask 0x013E
SN32 -> P1 GET_TXN_RESULT / RETIRE_TXN_RESULT
SN32 -> P2 RUN_SELF_TEST with mask 0x03E3
SN32 -> P2 GET_TXN_RESULT / RETIRE_TXN_RESULT
SN32 -> P1/P2 GET_STATUS final confirmation
```

It requires exact build IDs:

```text
P1 = 0x50310001
P2 = 0x50320001
```

It does not stage or commit a session, drive Tiny, send telemetry, exercise the
direct P1-to-P2 UART payload path, or qualify the full system.

## Earlier P1-only compatibility flow

The previous command remains available:

```bat
trinity-host --port COM3 p1-bringup
```

For new integration work, use `dual-spi-bringup` because the full SN32 firmware
requires both Primer endpoints for system discovery and status refresh.
