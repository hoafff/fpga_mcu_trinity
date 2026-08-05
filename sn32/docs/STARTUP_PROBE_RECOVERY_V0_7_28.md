# SN32 v0.7.27 startup probe recovery requirement

Hardware observations on 2026-08-05 established a repeatable distinction:

- P1 and P2 `SPI_DIAGNOSTIC GET_INFO/GET_STATUS` exchanges pass with exact CRC,
  correct build IDs and IRQ `0 -> 1 -> 1 -> 0`;
- after resetting SN32 while leaving P1/P2 configured, the automatic startup
  probe can exhaust its three short read reissues before P1 raises IRQ;
- the retained first failure is `STARTUP_PROBE`, P1 `GET_INFO`,
  `FRAME_TIMEOUT`, request length 10, transfer completed 10 and response length
  zero;
- later explicit diagnostics pass without changing wiring or bitstreams;
- ML-KEM KeyGen is correctly rejected with `BAD_STATE`, so these observations do
  not execute or qualify the low-RAM KeyGen path.

Therefore v0.7.28 must add a bounded startup recovery window around the complete
startup drain/probe sequence. Intermediate transport errors may be discarded
only after a complete P1+P2 probe succeeds within that window. If the window
expires or a non-transport safety error occurs, the original immutable first
failure remains retained.

This document is evidence and a source requirement, not hardware qualification.
