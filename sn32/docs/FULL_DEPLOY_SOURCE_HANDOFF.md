# SN32F407 Full Deploy Source Handoff

## Locked source baseline

The SN32F407 full deploy source is implemented on `main` and is ready for the exact Keil build gate.

This statement means the firmware source and Keil project contain the intended controller functions. It does not claim exact ArmClang link, Flash/RAM fit, flashing, or hardware qualification.

## Implemented runtime scope

- PC UART0 at 115200 8N1 with COBS and CRC16 framing.
- Shared SPI0 controller transport to Primer #1 and Primer #2.
- Independent CS and IRQ handling for both Primer endpoints.
- Packet validation, transaction IDs, timeout handling, retained transaction reconciliation, exact retry, and result retirement.
- Mandatory SN32, P1, P2, and Tiny self-test orchestration.
- Pinned ML-KEM-512 source selected from `pq-code-package/mlkem-native` commit `048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa`.
- Deterministic ML-KEM key generation, encapsulation, decapsulation self-check, SHA3/SHAKE KDF, and explicit secret zeroization.
- Dual-Primer session stage and commit with the same session material.
- SN32 P3.8 session-commit edge to Tiny after both Primer endpoints report `COMMITTED_BLOCKED`.
- Direct P1 UART transmit to P2 receive; SN32 does not relay the encrypted payload.
- P2 authenticated-result read, session/sequence/plaintext verification, ACK, and pending-result protection.
- Close-session, system zeroize, Tiny-fault containment, heartbeat lease containment, diagnostics, deterministic demo, benchmark, and transport stress paths.

`DEMO_SECURE` remains deliberately unavailable until an entropy source is approved and qualified. The command fails explicitly rather than using deterministic or fixed material as a secure substitute.

## Exact build gate

Clone with the pinned submodule:

```bash
git clone --recurse-submodules https://github.com/hoafff/fpga_mcu_trinity.git
cd fpga_mcu_trinity
git submodule update --init --recursive
```

Confirm the source pin:

```bash
git -C sn32/third_party/mlkem-native/upstream rev-parse HEAD
```

Expected:

```text
048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa
```

Run portable and static gates:

```bash
make -C sn32/tests/mlkem_gate3 clean test
make -C sn32/tests/full_controller clean test
make -C sn32/tests/deploy_crypto clean test
make -C sn32/tests/portable clean test
PYTHONPATH=pc_host/src python -m unittest discover -s pc_host/tests -v
python sn32/tests/deploy/check_deploy_project.py
python sn32/tests/s0/check_s0_project.py
git diff --check
```

Open and rebuild:

```text
sn32/keil/trinity_sn32f407_deploy.uvprojx
```

Locked target:

```text
SN32F407F
ArmClang 6.24
SONiX.SN32F4_DFP 1.0.1
ARM CMSIS 6.2.0 / CORE 6.1.1
Flash 32 KiB
RAM 8 KiB
```

## Evidence required before deployment PASS

Retain the Keil build log, linker MAP, AXF and HEX locally. Verify:

- zero errors;
- no unresolved symbols;
- Flash and RAM fit the exact target;
- stack and zero-initialized data do not exceed the 8 KiB RAM budget;
- the pinned ML-KEM single compilation unit is present in the build;
- no generated Keil state or binary output is committed.

Only after that gate may the status be raised to `EXACT_TARGET_BUILD_PASS`. Flashing and hardware execution are separate gates.
