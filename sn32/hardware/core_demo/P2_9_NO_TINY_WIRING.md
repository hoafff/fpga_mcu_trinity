# SN32 P2.9 no-Tiny core-demo wiring

Status: source candidate, hardware pending.

For the v0.7.29 time-bounded demo only:

```text
SN32 P2.9 / J7
    +--> Primer #1 J2-15 / T12 / secure_enable_i
    +--> Primer #2 J2-15 / T12 / secure_enable_i
```

The complete Tiny profile normally uses P2.9 as `hb_mcu_i`. Therefore:

- Tiny must be disconnected in this demo profile;
- the firmware compile-time disables periodic P2.9 heartbeat output;
- P2.9 has one GPIO owner only: direct shared secure-enable;
- P2.9 is initialized LOW and rises only at session commit;
- no ESP32, Tiny output or other driver may share the T12 net;
- SN32, P1 and P2 must share 3.3 V logic ground.

This file does not claim continuity, voltage or hardware PASS.
