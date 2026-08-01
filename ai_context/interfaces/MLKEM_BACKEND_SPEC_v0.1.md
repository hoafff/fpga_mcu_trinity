# FPGA MCU Trinity — ML-KEM Backend Specification

**Status:** `ASSUMED — FINAL OWNER REVIEW REQUIRED`  
**Version:** `v0.1`  
**Date:** `2026-08-01`

The upstream pin and exact native API names are confirmed. The per-polynomial
BaseMul decomposition and void-API error-latch handling below are tracked by O-015.

## 1. Exact upstream pin

```text
repository = https://github.com/pq-code-package/mlkem-native
tag        = v1.0.0
commit     = 048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa
license    = Apache-2.0 OR MIT OR ISC
```

## 2. Exact relevant custom-backend API

From `mlkem/src/native/api.h` at the pinned tag:

```c
static MLK_INLINE void mlk_ntt_native(int16_t p[MLKEM_N]);
static MLK_INLINE void mlk_intt_native(int16_t p[MLKEM_N]);

static MLK_INLINE void mlk_polyvec_basemul_acc_montgomery_cached_k2_native(
    int16_t r[MLKEM_N],
    const int16_t a[2 * MLKEM_N],
    const int16_t b[2 * MLKEM_N],
    const int16_t b_cache[2 * (MLKEM_N / 2)]);
```

Baseline does not enable `MLK_USE_NATIVE_NTT_CUSTOM_ORDER`.

## 3. Representation adapter

Wire coefficients are canonical uint16 little-endian `0..q-1`. Upstream arrays
are int16_t. Adapter canonicalizes before SPI transmission and converts returned
canonical coefficients to int16_t without exposing Montgomery representation.

Ordering:

- NTT input normal order;
- NTT output upstream bit-reversed order;
- INTT input bit-reversed order;
- INTT output normal order;
- BaseMul input/output bit-reversed NTT order.

## 4. NTT and INTT mapping

`mlk_ntt_native(p)`:

```text
canonicalize p
-> SPI NTT slot A
-> read slot A
-> write canonical result back to p
```

`mlk_intt_native(p)` follows the same flow with operation INTT.

## 5. BaseMul mapping — O-015 review item

For ML-KEM-512, K=2. The upstream native callback is a length-2 vector dot
product, while the approved P1 SPI primitive multiplies one polynomial pair at a
time.

Proposed wrapper:

```text
P0 = P1_BASEMUL(a[0], b[0])
P1 = P1_BASEMUL(a[1], b[1])
r  = canonical_reduce(P0 + P1) with upstream-equivalent Montgomery/scaling semantics
```

- The wrapper retains the exact upstream function prototype.
- `b_cache` may be ignored by the hardware wrapper because P1 receives full B
  polynomials; upstream software may still compute it.
- P1 result overwrites slot A for each per-polynomial BaseMul operation.
- Differential tests must prove coefficient equality with the pinned software
  backend for all directed and random vectors.
- If performance is inadequate, any `BASEMUL_ACCUMULATE` extension requires an
  amendment; it is not in baseline v0.1.

## 6. Error propagation — O-015 review item

The pinned native callbacks return `void`. Project integration therefore uses a
single-threaded SN32 backend error latch:

```text
trinity_mlkem_backend_error
trinity_mlkem_backend_error_detail
```

Rules:

1. Clear latch before each public KeyGen/Encaps/Decaps call.
2. On SPI/target failure inside a native callback:
   - latch first error;
   - zero the callback output buffer;
   - return from callback without exposing partial data.
3. Upstream call may finish computation, but its entire output is discarded.
4. Immediately after the public call, project wrapper checks the latch.
5. On error: zeroize outputs/intermediates and return project-level failure.

No source may silently treat an accelerator failure as a valid ML-KEM result.

## 7. Backends

```text
software_reference_backend
primer1_spi_backend
```

KAT and differential tests run both on identical inputs. Production/deterministic
mode selects the SPI backend only after P1 self-test and transport readiness.

## 8. FIPS-202

Use the pinned upstream FIPS-202 implementation initially. A replacement due to
Keil Flash/RAM evidence requires a separately approved amendment and differential
KAT evidence.
