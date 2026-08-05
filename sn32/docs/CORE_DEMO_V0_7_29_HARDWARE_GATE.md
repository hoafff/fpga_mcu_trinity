# Trinity core demo v0.7.29 hardware gate

## Scope

Candidate identities:

- SN32 architecture: `0.7.29`
- SN32 build ID: `0x0007001D`
- PC host: `0.5.0`
- Primer #1: `0x5031D003`
- Primer #2: `0x50320002`

The purpose is the minimum real competition demonstration:

```text
PC -> SN32 ML-KEM-512 KeyGen/Encaps/Decaps/KDF
   -> stage and commit the same session to P1/P2
   -> P1 Ascon encrypt + direct UART transmit
   -> P2 authenticate/decrypt
   -> SN32 read/ACK authenticated plaintext
   -> PC byte-exact verification
   -> full zeroize
```

Tiny 1P5 is intentionally omitted. This gate must never be reported as Tiny or
full-system qualification.

## Temporary demo wiring without Tiny

Keep all hardware-qualified SPI and P1-to-P2 UART wiring unchanged. Add the
single shared control net below:

```text
SN32 P2.9 / board-visible J7 header pin
    +--> Primer #1 secure_enable_i / FPGA T12
    +--> Primer #2 secure_enable_i / FPGA T12
```

Requirements:

- common 3.3 V ground among SN32, P1 and P2;
- P2.9 LOW during reset/startup;
- one SN32 output drives both Primer inputs;
- no ESP32, Tiny or second output may drive that net;
- verify continuity and absence of contention before power-on.

P2.9 is the normal MCU-heartbeat pin in the full Tiny profile. In the explicit
no-Tiny v0.7.29 demo profile, firmware disables periodic heartbeat toggling and
gives P2.9 one owner only: direct shared secure-enable. SysTick, progress leases,
UART liveness and the internal fail-closed heartbeat timeout remain active.

The firmware drives P2.9 LOW for at least 2 ms and then HIGH at commit. In this
demo profile that edge acts directly as shared `secure_enable`; it is not a Tiny
session-commit qualification.

## Source gates

The pinned `mlkem-native` reference remains:

```text
pq-code-package/mlkem-native@048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa
```

Portable tests must prove byte-exact equality for deterministic KeyGen and
Encaps, valid Decaps shared-secret equality, and tampered-ciphertext implicit
rejection equal to the pinned implementation.

A2 may retain only the existing phase-shared 1792-byte workspace. It must not
allocate a complete matrix, polyvector or second 768-byte ciphertext buffer.

## Exact-target build and map gate

Build:

```text
sn32/keil/trinity_sn32f407_deploy.uvprojx
```

Required:

```text
ArmClang 6.24
0 errors
0 warnings
AXF/HEX/MAP generated
```

Run:

```bat
python sn32\tests\deploy\check_mlkem_lowram_map.py sn32\keil\Listings\deploy\trinity_sn32f407_deploy.map
```

Acceptance remains:

- Total RW `<= 8192` bytes;
- stack exactly `2048` bytes;
- `g_crypto <= 3520` bytes;
- at least `256` bytes static IRAM headroom;
- no `g_host_low_ram_storage` target symbol.

Do not flash if the build or map gate fails.

## Programming and identity

Program and Verify only SN32. P1/P2 bitstreams are unchanged. Allow up to 13
seconds after reset for startup recovery, then run:

```bat
trinity-host --port COM3 ping
trinity-host --port COM3 system-info
trinity-host --port COM3 system-status
trinity-host --port COM3 spi-first-failure
```

Required identity and clean baseline:

```text
architecture_version=0.7.29
sn32_build_id=0x0007001D
primer1_build_id=0x5031D003
primer2_build_id=0x50320002
target_ready_mask=0x07
fault_flags=0x00
last_error=OK
latched=False
```

## Operator GUI

Install the host package:

```bat
python -m pip install -e pc_host
```

Launch:

```bat
trinity-demo
```

The dashboard performs the core sequence in a worker thread and displays:

- SN32/P1/P2 identities;
- system/session state;
- progress and event frames;
- session ID and sequence;
- authenticated 24-byte plaintext;
- final zeroize and PING result;
- exportable text log.

The yellow scope banner must remain visible: Tiny is omitted, P2.9 is the direct
demo secure-enable source, and P2.9 heartbeat output is disabled.

## CLI fallback hardware sequence

First qualify the existing control plane:

```bat
trinity-host --port COM3 sn32-qualify --timeout 10 --poll 0.1 --liveness 10
```

Then run the existing full-flow command after v0.7.29 is installed, or use the
GUI one-packet workflow. At minimum the evidence must contain:

```text
KeyGen PASS
CREATE_SESSION PASS
system_state=ACTIVE
session_id != 0
one telemetry result_code=OK
plaintext output equals plaintext input byte-exact
READ_LAST_RESULT equals the telemetry result
ZEROIZE PASS
READY_NO_KEYPAIR
PING PASS
```

## Stop conditions

Stop and retain all output if any of these occurs:

- exact-target map gate fails;
- KeyGen or session creation exceeds 120 seconds;
- session never reaches ACTIVE;
- either Primer secure-enable flag remains clear;
- authenticated plaintext differs by one byte;
- sequence/session ID mismatch;
- `FAULT_LOCKED`, `HEARTBEAT_TIMEOUT`, `INTERNAL_FAULT` or SPI first failure;
- zeroize does not restore `READY_NO_KEYPAIR`;
- post-demo PING fails.

## Non-claim boundary

Even after this core demo passes, do not claim:

```text
Tiny supervisor integration PASS
Tiny fault containment PASS
random/entropy-qualified ML-KEM PASS
power-fail recovery PASS
full-system hardware qualification PASS
```
