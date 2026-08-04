# SN32 ML-KEM-512 low-RAM A1 hardware gate

## Scope

Candidate identity:

- architecture version: `0.7.27`
- SN32 build ID: `0x0007001B`
- PC host package: `0.4.2`

This gate qualifies only deterministic ML-KEM-512 KeyGen on the SN32F407F.
It preserves the v0.7.26 GPIO dual-SPI transport, P1/P2 bitstreams and wiring.
It does not qualify Encaps, Decaps, session activation, secure telemetry, Tiny,
or the full system.

## Source contract

The pinned `mlkem-native` keypair implementation remains the byte-level
reference. The SN32 candidate replaces its stack-heavy orchestration with a
serial implementation that retains only one matrix polynomial, one vector
polynomial, one accumulator and one multiplication cache. Portable tests must
show byte-exact public-key and secret-key equality against the pinned backend.

The 1792-byte polynomial scratch area time-shares the existing crypto session
workspace. The exact-target image must not contain the host-only fallback
symbol `g_host_low_ram_storage`.

## Gate A1.1 — exact-target build and map

Build only the existing Keil target:

```text
sn32/keil/trinity_sn32f407_deploy.uvprojx
```

Required environment remains unchanged:

- Keil uVision 5.43.1
- ArmClang 6.24
- SN32F407F
- SONiX DFP 1.0.1
- CMSIS 6.2.0 / CORE 6.1.1

Acceptance:

- zero errors and zero warnings;
- IROM maximum `0x7FFC`;
- IRAM maximum `0x2000`;
- `Total RW <= 8192` bytes;
- stack exactly 2048 bytes;
- `g_crypto <= 3520` bytes;
- at least 256 bytes IRAM headroom;
- no `g_host_low_ram_storage` symbol;
- AXF, HEX and MAP generated.

Run from the repository root:

```bat
python sn32\tests\deploy\check_mlkem_lowram_map.py sn32\keil\Objects\trinity_sn32f407_deploy.map
```

Use the actual MAP path emitted by Keil if it differs.

Do not flash if this gate fails.

## Gate A1.2 — programming and identity

Program and verify only SN32. Do not reprogram P1 or P2 and do not change
wiring.

After reset:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 system-info
```

Required identity:

```text
architecture_version=0.7.27
sn32_build_id=0x0007001B
primer1_build_id=0x5031D003
primer2_build_id=0x50320002
```

## Gate A1.3 — control-plane regression

Power-cycle SN32, P1 and P2 together, then run:

```bat
trinity-host --port COM3 sn32-qualify --timeout 10 --poll 0.1 --liveness 10
```

Required result:

```text
[SN32_DUAL_SPI_CONTROL_PLANE]
result=PASS
```

The final state must be `READY_NO_KEYPAIR`, with `target_ready_mask=0x07`, no
fault flags and no first SPI failure.

## Gate A1.4 — isolated deterministic KeyGen

Run exactly one KeyGen request:

```bat
trinity-host --port COM3 keypair-generate --mode deterministic --timeout 120
```

Required result:

```text
[MLKEM_KEYPAIR]
result=PASS
```

Immediately prove post-operation liveness and state:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 system-status
```

Required state:

```text
system_state=READY_NO_SESSION
fault_flags=0x00
last_error=OK
active_host_txid=0x0000
```

Then remove key material:

```bat
trinity-host --port COM3 zeroize --scope all --timeout 30
trinity-host --port COM3 system-status
trinity-host --port COM3 ping
```

Required final state is `READY_NO_KEYPAIR`, clean status and live PING.

## Stop conditions

Stop immediately and retain the complete output if any of the following occurs:

- KeyGen exceeds 120 seconds;
- PING fails after KeyGen;
- `HEARTBEAT_TIMEOUT`, `INTERNAL_FAULT` or `FAULT_LOCKED` appears;
- target readiness changes from `0x07`;
- the MCU resets unexpectedly;
- MAP headroom is below 256 bytes.

Do not run `session-create` or `sn32-secure-telemetry-qualify` under A1.
Encaps/Decaps remain on the original upstream stack-heavy path and require a
separate A2 low-RAM implementation and hardware gate.
