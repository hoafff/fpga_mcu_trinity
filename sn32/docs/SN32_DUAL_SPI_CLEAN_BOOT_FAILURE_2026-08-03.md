# SN32 dual-SPI clean-boot failure audit — 2026-08-03

## Decision

The first correctly sequenced dual-SPI hardware run at source commit
`409e11944c539aaebe2e77f74ed88b252b13c6ed` failed before the retained
self-tests began.

Locked status:

```text
PC <-> SN32 UART:                    PASS
DUAL-SPI clean-boot qualification: FAIL
First PC command that failed:        GET_SYSTEM_INFO
Reported error source:               P2 / source=2
First failing endpoint:              NOT PROVEN BY v0.7.1 TELEMETRY
Exact failing target command:        NOT RECOVERABLE FROM v0.7.1 TELEMETRY
Reported error:                      TRANSACTION_CONFLICT 0x0205
related_target_txid:                 0x0000
```

This result does not qualify P1, P2, dual-SPI, session, cryptography, Tiny or the
full system.

Raw command evidence is retained at:

```text
sn32/hardware/dual_spi_control_plane/evidence/clean_boot_failure_2026-08-03.txt
```

## Observed run

Power/reset order was P1/P2 first, both FPGA configurations completed, then SN32
was powered/reset last. P1/P2 were not reset after SN32 started. Only one PING
and one `dual-spi-bringup` command were issued.

```text
[PING]
result=PASS
uptime_ms=6946

FAIL: remote error TRANSACTION_CONFLICT(0x0205), system_state=9,
source=2, related_target_txid=0x0000
```

The PC command sequence proves that the failing PC command was
`GET_SYSTEM_INFO`: `dual-spi-bringup` performs PING and then calls
`GET_SYSTEM_INFO` before any system-status query or retained self-test.

## Why the exact target command is not recoverable

`GET_SYSTEM_INFO` calls the SN32 dual-endpoint probe. The v0.7.1 controller:

1. probed P1 with target `GET_INFO`, then `GET_STATUS` after a successful info;
2. probed P2 in the same way even when the P1 probe had already failed;
3. returned the earlier non-OK code but allowed a later endpoint probe to
   overwrite the controller error source and detail;
4. serialized `related_target_txid=0` unconditionally.

Therefore `source=2` is the final reported source, not proof that P2 was the
first endpoint to fail. The old response cannot distinguish P2 `GET_INFO`, P2
`GET_STATUS`, or an earlier P1 failure overwritten by the P2 probe.

## Transaction ID and retained-state audit

The Primer does not allocate request transaction IDs. SN32 owns one global
16-bit SPI transaction counter initialized to one after SN32 reset and shared by
both endpoints. P2 stores a transaction ID only when it accepts a retained
side-effect operation.

On P2 reset, the following are cleared:

```text
retained_valid       = 0
retained_txid        = 0
retained_command     = 0
retained_fingerprint = 0
mailbox_pending      = 0
SPI parser/build state reset
```

P2 emits `ERR_TRANSACTION_CONFLICT` only when all of the following are true:

- the command is a retained side-effect operation;
- a retained result already exists;
- the new request reuses exactly the retained transaction ID;
- its command or request fingerprint differs.

`GET_INFO` and `GET_STATUS` do not enter that branch. Because this run failed
before `RUN_SELF_TEST`, the reported `0x0205` is not accepted as proof of a real
P2 exact-retry conflict.

`related_target_txid=0x0000` was caused by lost telemetry in v0.7.1:

- `GET_INFO` and `GET_STATUS` passed a null issued-txid output pointer;
- the transport assigned the output only after a successful correlated response;
- `handle_get_system_info()` serialized a literal zero for all errors.

It does not mean SN32 necessarily transmitted target transaction ID zero.

## Proven transport defect

The v0.7.1 SN32 transport read one Primer response using two separate chip-select
assertions:

```text
CS low  -> read 8-byte response header -> CS high
CS low  -> read payload and CRC         -> CS high
```

The Primer `spi_packet_endpoint` resets its transmit byte index to zero at every
CS falling edge. Consequently, the second read starts again at response byte
zero rather than continuing at byte eight. Every response with a payload is
therefore assembled incorrectly by SN32.

This explains both possible outcomes observed in the source:

- CRC failure after combining unrelated byte positions;
- command/transaction correlation mismatch, which v0.7.1 mapped locally to
  `TRINITY_TRANSACTION_CONFLICT`.

The previously successful ESP32-C3 qualification harness kept CS asserted while
reading the entire header, payload and CRC. It also drained a startup mailbox
before the first request.

## Startup, CS, IRQ and mailbox state

SN32 v0.7.1 did issue startup probes before entering the PC command loop.

Both SN32 CS GPIOs are initialized high. The P2 MISO output is high-impedance
while P2 CS is high. The P2 IRQ remains low while any response mailbox, retained
result or authenticated result is pending.

A full P2 reset clears parser, mailbox and retained state. Resetting only SN32
does not clear state inside P2. The v0.7.2 correction therefore drains a
pre-existing startup mailbox before issuing the initial probe, while preserving
the fail-closed retained-state rules.

## Corrective image

The corrective source is versioned independently:

```text
architecture_version = 0.7.2
sn32_build_id         = 0x00070002
SPI                   = 100 kHz, mode 0, MSB first
```

Corrections:

- read the complete maximum Primer response under one CS assertion;
- derive the true response frame length after the single capture;
- preserve request command, target transaction ID and request fingerprint;
- record request/response bytes, CRC values and IRQ levels;
- drain a stale startup mailbox before the initial probe;
- expose only side-effect-free raw diagnostics for `GET_INFO` and `GET_STATUS`;
- return the failing target transaction ID instead of a literal zero.

The source and portable/static gates do not establish a new exact Keil build,
flash result or hardware result. Those gates must be repeated for v0.7.2.

## Next diagnostic sequence

After exact rebuild, Flash/RAM fit, SN-LINK program/verify and standalone PING,
run only:

```text
trinity-host --port COM3 spi-diag --target p1 --command get-info
trinity-host --port COM3 spi-diag --target p2 --command get-info
trinity-host --port COM3 spi-diag --target p2 --command get-status
```

Each trace reports command, target txid, request fingerprint, complete request
bytes, maximum response capture, received/calculated CRC, IRQ state before and
after request/response, and error source. Do not run the retained self-test gate
until these side-effect-free exchanges have been audited.
