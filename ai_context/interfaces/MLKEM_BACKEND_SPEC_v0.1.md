# FPGA MCU Trinity — ML-KEM Backend Specification

**Status:** `IMPLEMENTATION APPROVED / VERIFICATION PENDING`  
**Version:** `v0.1`

## Upstream pin

```text
repository = https://github.com/pq-code-package/mlkem-native
tag        = v1.0.0
commit     = 048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa
license    = Apache-2.0 OR MIT OR ISC
```

The adapter follows the exact pinned custom-backend API, including
`mlk_ntt_native`, `mlk_intt_native` and the ML-KEM-512 K=2 vector BaseMul
callback. Baseline does not enable custom NTT order.

## Approved decomposition

```text
P0 = P1_BASEMUL(a[0], b[0])
P1 = P1_BASEMUL(a[1], b[1])
r  = combine(P0, P1)
```

`combine` must preserve exact pinned upstream ordering, Montgomery/scaling and
coefficient semantics. Per-polynomial BaseMul result overwrites P1 slot A.

## Error latch

Because upstream callbacks return `void`, SN32 uses a single-threaded backend
error latch. The latch is cleared before each public KeyGen/Encaps/Decaps call.
On first accelerator/transport failure, the callback latches the error, zeroes
its output and returns. The public wrapper discards all outputs and zeroizes
intermediates after the upstream call returns.

## Permitted implementation work

- software reference backend;
- Primer #1 SPI backend;
- NTT/INTT adapter;
- BaseMul decomposition;
- error-latch wrapper;
- differential testbench.

## Verification gate V-001

Do not mark BaseMul mapping `TESTED` before all conditions pass:

- exact upstream ordering and Montgomery/scaling;
- coefficient-by-coefficient equality;
- directed vectors;
- at least 100 random vectors;
- hardware decomposition output equals the pinned software backend.

No Gowin/Keil/hardware PASS is implied by implementation approval.
