# Primer #1 hardware evidence artifact manifest

## Provenance

- Qualified source tree: `c8135b5304c0318c7ec24787484dc8a4c4aa0278`
- RTL logic fix commit: `38f90f4d724a0434ea1d347b78b69ae3acdf1ce8`
- Simulation evidence at source tree: `primer1/docs/RTL_SIMULATION_LATEST.md`
- Exact target: `GW2A-LV18PG256C8/I7`
- Database selection: `GW2A-18C / gw2a18c-011`
- Clock: 27 MHz, 37.037 ns
- Tool: Gowin EDA V1.9.11.03 Education
- Build/report timestamp: 2026-08-02 17:07 local tool time

## Uploaded artifact hashes

| Artifact | Size | SHA-256 |
|---|---:|---|
| `primer1_hardware_test_evidence.zip` | 16,770 bytes | `20c1ef0af1f83a624a0e7cc2252e0876131bcf1832ad453e6d2eb0154d77e8d2` |
| `serial_monitor_full_history.txt` source upload | 31,254 bytes | `a6c280ee00ac32976318f2205f63b3d204fba2983640182a6d17a8319c1506be` |
| comprehensive sketch duplicate upload | 47,660 bytes | `bfefd22093d57e9ba1b9a5b675b192799d42e5a93cb250bc9c0827c41b79ccdf` |
| detailed timing HTML | 530,588 bytes | `5055d6bdb6361aebd23b86cde5c8b8b9eef27d9b15e253b31f9df986dbde2a34` |
| text timing report | 330,680 bytes | `f90a922f87adf0ad0b8a0ca7a5c29f007ce5a9924fd2f25ad1578512b990e6da` |
| PnR HTML report | 63,333 bytes | `ba7cac86916e7581e6741cf7f1d1bc8c0f45f285e2504f2a1491f129e70bd88f` |
| `trinity_primer1.fs` | 7,264,152 bytes | `168459a32fe5545ff77ff5bf590f4b2d84b0fcdd148739324dbba568f8c1f510` |
| final PASS screenshot | 68,355 bytes | `bc14b7b440961d3f46c085050e9e261c4337bd5a0ba04e4d2293f41406e764bc` |

The table identifies the exact uploaded evidence. The source ZIP is retained
in Git unchanged; the large generated bitstream, detailed reports and screenshot
remain external evidence identified by these hashes.

## Extracted ZIP member hashes

| ZIP member | SHA-256 |
|---|---|
| `01_primer1_standalone_monitor.ino` | `8b618387eac8b1ec390821a1079899435b0c69c66909add75cdc0661a4780bc1` |
| `02_spi_get_info_status_debug_snapshot.cpp` | `8ccb4ca486254332950a30a9ddccbe2479e9065e09c02d736da44c60f8fe1984` |
| `03_self_test_stage.md` | `08ab5f8f7bbf0ebc089fd38b97e58885835a5a7143864f311aeec5700f67feef` |
| `04_primer1_remaining_tests_esp32c3.ino` | `6444bcd0c338a0228928de8d73d2edae5aac21c3949236d0dc3503448b0ed584` |
| `README_TEST_WIRING_AND_RESULTS.md` | `ff161220ebac199935dc3b70875c6e8e5c6c8300a19cd436ac37abe2a3b1daba` |

## Report rendering note

The timing HTML summary displays `27.025 MHz`; the text `.tr` report rounds the
same result to `27.026 MHz`. Qualification records the conservative value
`27.025 MHz`, consistent with the supplied acceptance summary and +0.035 ns WNS.

## Bitstream header identity

The supplied `.fs` header records:

```text
Tool Version:       V1.9.11.03 Education (81398)
Device:             GW2A-18
Device Version:     C
Part Number:        GW2A-LV18PG256C8/I7
Device-package:     GW2A-18C-PBGA256
CheckSum:           0x1E73
UserCode:           0x00001E73
CRCCheck:           ON
Created Time:       Sun Aug 2 17:07:01 2026
```

The `.fs` is generated output and remains excluded by `.gitignore`. Rebuilds
must not be called identical unless the resulting SHA-256 matches the value in
this manifest.

## Evidence retained in Git

- `../esp32c3/primer1_hardware_test_evidence.zip`: exact source package and its original wiring/results README.
- `../esp32c3/README.md`: reproducible wiring, programming, reset and execution procedure.
- `../../../docs/PRIMER1_HARDWARE_QUALIFICATION_c8135b53.md`: reviewed result and scope decision.

The raw serial log, detailed timing/PnR reports, screenshot and generated `.fs`
are not duplicated into Git. Their SHA-256 values above provide artifact
identity and the qualification document records the extracted, cross-checked
results.
