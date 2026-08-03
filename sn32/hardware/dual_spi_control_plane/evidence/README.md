# SN32 dual-SPI control-plane evidence

This directory is reserved for the scoped hardware gate:

```text
SN32 -> P1/P2 DUAL-SPI CONTROL PLANE HARDWARE
```

Do not add a PASS summary until the complete command output has been audited.

Required evidence for one run:

```text
exact_keil_rebuild_<date>.txt
snlink_program_verify_<date>.txt
standalone_ping_<date>.txt
system_info_<date>.txt
system_status_before_<date>.txt
dual_spi_bringup_<date>.txt
system_status_after_<date>.txt
wiring_<date>.<jpg-or-png>
run_manifest_<date>.txt
```

The run manifest must record:

- repository commit;
- ML-KEM submodule commit;
- SN32 AXF/HEX hashes;
- P1 and P2 bitstream source commits and hashes when available;
- board identities;
- UART COM port;
- SPI frequency and mode;
- all safety straps;
- complete PASS/FAIL decision and explicit non-claims.

A local hardware log may be retained outside Git first if it contains machine
paths or transient information. Commit only normalized evidence intended for the
qualification record.
