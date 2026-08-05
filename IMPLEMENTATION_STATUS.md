# Implementation status

Status date: 2026-08-05

## Active hardware-qualified identities

```text
Primer #1 build ID = 0x5031D003
Primer #2 build ID = 0x50320002
SN32 version/build = 0.7.28 / 0x0007001C
PC host version    = 0.4.3
```

The active shared-SPI contract remains:

```text
ai_context/interfaces/SPI_CONTROL_PLANE_ICD_v0.2.md
```

The qualified P1/P2 bitstreams, physical wiring, GPIO mode-0 SPI backend and
direct P1-to-P2 UART payload path were not changed by the v0.7.28 gate.

## v0.7.28 purpose

Hardware v0.7.27 showed transient automatic startup `GET_INFO` failures while
later explicit P1/P2 diagnostics passed without changing bitstreams or wiring.
Version 0.7.28 adds a bounded startup recovery window around:

```text
startup drain P1
-> startup drain P2
-> probe P1 GET_INFO/GET_STATUS
-> probe P2 GET_INFO/GET_STATUS
```

Intermediate startup transport evidence is cleared only after the complete P1
and P2 probe succeeds in the same boot. Persistent, non-transport and safety
failures remain fail-closed and retain the original first failure.

## Source and CI status

Main source commit before the hardware evidence lock:

```text
0c766733e76daa84d1e04937bf98fc6f13549e4b
```

The following source gates passed for v0.7.28:

```text
repository/project-memory checks
SN32 deploy static checks
bounded startup recovery source contract
Python host/protocol tests
portable C protocol tests
full controller tests
deploy crypto lifecycle tests
pinned ML-KEM Gate 3 tests
Primer #2 nine-bench RTL regression
```

The detailed v0.7.28 ArmClang build and MAP output was not included in the A1
hardware transcript. The running hardware identity nevertheless proves that a
v0.7.28 image with build ID `0x0007001C` was programmed and executed. Exact
program-size and MAP values must not be copied from the older v0.7.26 record.

## Startup and control-plane hardware qualification

Pre-qualification state:

```text
PING: PASS
system_state=SELF_TEST_REQUIRED
target_ready_mask=0x07
fault_flags=0x00
last_error=OK
active_host_txid=0x0000
SPI first failure: NONE
```

Command:

```text
trinity-host --port COM3 sn32-qualify --timeout 10 --poll 0.1 --liveness 10
```

The run demonstrated:

```text
P1 GET_INFO: PASS, full frame, CRC match, IRQ released
P1 GET_STATUS: PASS, full frame, CRC match, IRQ released
P2 GET_INFO: PASS, full frame, CRC match, IRQ released
P2 GET_STATUS: PASS, full frame, CRC match, IRQ released
P1 retained KAT RUN/QUERY/RETIRE: SUCCEEDED
P2 retained KAT RUN/QUERY/RETIRE: SUCCEEDED
FINAL_SYSTEM_STATUS: READY_NO_KEYPAIR
ready_mask: 0x07
fault_flags: 0x00
last_error: OK
POST_TEST_LIVENESS: PASS, 10 iterations
FINAL_SPI_FIRST_FAILURE: NONE
```

Final command result:

```text
[SN32_P1_P2_HARDWARE_QUALIFICATION]
result=PASS
```

## ML-KEM-512 low-RAM KeyGen A1 hardware qualification

Command:

```text
trinity-host --port COM3 keypair-generate --mode deterministic --timeout 120
```

Result:

```text
[MLKEM_KEYPAIR]
result=PASS
host_txid=0x0001
public_key_hash=e906a88a8a119a7321543a3cbdf0d6e3fa809951fec835e0e581d37f7eb3e0aa
```

The low-RAM implementation completed on the SN32F407F without the v0.7.26
post-command loss of UART liveness. The gate then executed full-scope zeroize:

```text
[ZEROIZE]
result=PASS
scope=all
```

Final state and liveness:

```text
system_state=READY_NO_KEYPAIR
target_ready_mask=0x07
fault_flags=0x00
last_error=OK
active_host_txid=0x0000
PING: PASS
uptime_ms=53596
```

## Evidence

Raw command transcript:

```text
sn32/hardware/mlkem_low_ram_a1/evidence/
  v0_7_28_keygen_hardware_qualification_2026-08-05.txt
```

Machine-readable qualification record:

```text
sn32/hardware/mlkem_low_ram_a1/
  qualification_v0_7_28.toml
```

Historical v0.7.26 dual-SPI evidence remains valid for its recorded scope and is
retained separately under `sn32/hardware/dual_spi_control_plane/`.

## Qualified scope

The following claims are supported:

```text
SN32 v0.7.28 startup recovery on hardware: PASS
PC <-> SN32 command and UART liveness path: PASS
SN32 -> P1/P2 shared dual-SPI control-plane regression: PASS
P1/P2 identity and status access through SN32: PASS
P1/P2 retained KAT transaction lifecycle through SN32: PASS
deterministic ML-KEM-512 low-RAM KeyGen A1 on SN32F407F: PASS
post-KeyGen zeroize across requested scope: PASS
post-KeyGen PC-UART liveness: PASS
```

## Non-claim boundary

The following remain open and must not be reported as PASS from A1:

```text
ML-KEM-512 Encaps on SN32 hardware
ML-KEM-512 Decaps on SN32 hardware
shared-secret equality on SN32 hardware
KDF-derived session material on SN32 hardware
session stage/commit across SN32, P1 and P2
P1 encrypt + direct UART transmit -> P2 authenticate/decrypt
SN32 authenticated-result read and ACK
replay/wrong-ACK/pending-result protection in the complete flow
Tiny complete safety integration
full-system hardware qualification
```

## Next gate: A2 low-RAM Encaps/Decaps

The next engineering sequence is:

```text
1. Audit stack and transient buffers in ML-KEM Encaps and Decaps.
2. Implement phase-shared low-RAM Encaps without adding a second large global workspace.
3. Implement phase-shared low-RAM Decaps, including implicit rejection behavior.
4. Compare ciphertext and shared secrets byte-for-byte against the pinned backend.
5. Rebuild the exact SN32 target and rerun the RAM/MAP gate.
6. Hardware-qualify isolated deterministic Encaps/Decaps and prove PING liveness.
7. Only after A2 PASS, run session KDF, stage/commit and secure telemetry gates.
8. Integrate and requalify Tiny only after the SN32/P1/P2 secure flow passes.
```

Current full-system hardware qualified remains:

```text
false
```
