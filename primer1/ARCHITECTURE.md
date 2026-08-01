# Primer #1 implementation notes

The implementation is deliberately iterative and resource bounded:

- one NTT/INTT butterfly is executed per clock;
- BaseMul reuses the same Montgomery multiplication/reduction functions;
- polynomial slot A and B are the only full 256-coefficient memories;
- Ascon executes one permutation round per clock and reuses the same 320-bit state;
- UART retains one 66-byte frame and serializes it byte-by-byte;
- zeroization overwrites both polynomial memories sequentially.

This architecture retains NTT, INTT, BaseMul, Ascon, UART TX, session and safety
interfaces. Reducing functional scope is not an accepted resource workaround.

The logical CST is committed from the current Trinity pin plan. Its presence does
not upgrade physical qualification; continuity, voltage, timing and board behavior
remain evidence-pending.
