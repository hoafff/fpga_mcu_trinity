# Implementation status

Status date: 2026-08-05

## Qualified control-plane baseline

The active shared-SPI contract is recorded in:

```text
ai_context/interfaces/SPI_CONTROL_PLANE_ICD_v0.2.md
```

The corrected rule is:

```text
IRQ_N LOW  <=> one complete response mailbox is physically ready to read
retained/authenticated result state is queried explicitly and does not hold IRQ
non-magic request windows are discarded silently and create no error mailbox
```

## Active source and hardware identities

```text
Primer #1 build ID = 0x5031D003
Primer #2 build ID = 0x50320002
SN32 version/build = 0.7.26 / 0x0007001A
PC host version    = 0.3.9
```

SN32 source commits:

```text
472b9f263b47ef820c0034edd206c8a015cb9fd1
  fix(sn32): enlarge stack and isolate SPI trace state

c1ded1ece67fe9557a378c33115e1c7a2b59d969
  chore(sn32): publish v0.7.26 host identity contract
```

## Exact-device build and programming

| Target | Exact-device result | Programmed hardware |
|---|---|---|
| Primer #1 `0x5031D003` | Gowin synthesis/P&R/STA PASS; critical timing margin previously recorded | PASS |
| Primer #2 `0x50320002` | Gowin synthesis/P&R/STA PASS | PASS |
| SN32 `0.7.26 / 0x0007001A` | ArmClang 6.24: 0 errors, 0 warnings | Flash PASS; Verify OK |
| PC host `0.3.9` | Wheel build/install PASS | Active virtual environment confirmed |
| Tiny 1P5 | Unchanged by this gate | Not requalified by this gate |

SN32 program size:

```text
Code=25724
RO-data=776
RW-data=100
ZI-data=6788
Total ROM=26600 bytes
Total RAM=6888 bytes
```

SN32 linker stack lock:

```text
STACK start = 0x200012E8
STACK size  = 0x00000800 = 2048 bytes
__initial_sp = 0x20001AE8
map SHA-256 = 7b07e693a83d17d7b8069a1e95a45eaf4b5be6b2829be466feebf194870d5edf
```

## Hardware qualification result

Command:

```text
trinity-host --port COM3 sn32-qualify --timeout 10 --poll 0.1 --liveness 10
```

Final result:

```text
[SN32_P1_P2_HARDWARE_QUALIFICATION]
result=PASS
```

The run demonstrated:

```text
PREFLIGHT_PING: PASS
P1 GET_INFO: PASS, full frame and CRC match
P1 GET_STATUS: PASS, full frame and CRC match
P2 GET_INFO: PASS, full frame and CRC match
P2 GET_STATUS: PASS, full frame and CRC match
P1 KAT retained RUN/QUERY/RETIRE: SUCCEEDED
P2 KAT retained RUN/QUERY/RETIRE: SUCCEEDED
FINAL_SYSTEM_STATUS: READY_NO_KEYPAIR
fault_flags: 0x00
last_error: OK
POST_TEST_LIVENESS: PASS, 10 iterations
FINAL_SPI_FIRST_FAILURE: latched=False
```

Raw evidence:

```text
sn32/hardware/dual_spi_control_plane/evidence/
  v0_7_26_hardware_qualification_2026-08-05.txt
```

## Qualified scope

The following claims are now supported:

```text
SN32 exact-target build/flash/verify: PASS
PC <-> SN32 qualification command/liveness path: PASS
SN32 -> P1/P2 shared dual-SPI control plane: PASS
P1/P2 identity and status access through SN32: PASS
P1/P2 retained KAT transaction lifecycle through SN32: PASS
post-test PC-UART liveness: PASS
SN32 -> P1/P2 hardware qualification: PASS
```

## Non-claim boundary

The following are still open and must not be reported as PASS from this gate:

```text
ML-KEM keypair generation on hardware
ML-KEM session establishment and key derivation
session stage/commit across SN32, P1, P2 and Tiny
P1 encrypt + direct UART transmit -> P2 authenticate/decrypt
SN32 authenticated-result read and ACK
Tiny complete safety integration
full-system hardware qualification
```

## Next gate

The next sequence is:

```text
1. Keep P1, P2 and SN32 qualified images unchanged.
2. Run SN32 ML-KEM-512 keypair generation and verify terminal result.
3. Create and stage one session to P1 and P2.
4. Commit the session and verify both endpoints become ready.
5. Send one telemetry payload through P1 -> direct UART -> P2.
6. Read authenticated plaintext from P2 through SN32 and ACK it.
7. Verify replay/wrong-ACK/pending-result protection.
8. Only after that PASS, integrate and requalify the Tiny supervisor path.
```

Current full-system hardware qualified remains:

```text
false
```
