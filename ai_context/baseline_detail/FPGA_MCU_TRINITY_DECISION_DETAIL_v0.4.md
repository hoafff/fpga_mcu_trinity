# FPGA MCU Trinity — Decision Register

**Document status:** `APPROVED IMPLEMENTATION DECISIONS — CONSOLIDATED BASELINE`  
**Implementation status:** `DOCUMENT REVIEW REQUIRED / SOURCE NOT STARTED`  
**Version:** `v0.4`  
**Date:** `2026-08-01`  
**Project-memory entrypoint:** `ai_context/README_AI.md`

---

## 1. Authority

- Quyết định mới nhất của chủ dự án có ưu tiên cao nhất.
- System Specification v0.4, các ICD/backend spec được register này dẫn chiếu và
  các amendment có ID là active project memory.
- Repo cũ, Git history và `ai_context/migration/` không có thẩm quyền kiến trúc.
- Không tự điền open item hoặc nâng status khi chưa có phê duyệt/evidence.

---

## 2. Q01–Q100 baseline continuity

Toàn bộ Q01–Q100 của v0.3 tiếp tục `CONFIRMED`, ngoại trừ các chi tiết được D01–D60
làm rõ hoặc thay thế. Các thay đổi quan trọng:

- Q23: 64 byte là polynomial data chunk; command payload có thể 66 byte.
- Q24: SPI header/txid exact được khóa trong SPI ICD v0.1.
- Q50/A-006: golden model nằm tại `ai_context/verification/reference/`.
- Q52–Q54/A-008: KDF byte-exact được khóa và O-001 đóng.
- Q83/A-014: SESSION_COMMIT chọn toggle và O-005 đóng.
- Q17: PC timeout defaults được khóa và O-011 đóng.
- Q99 status vocabulary không thay đổi:
  `CONFIRMED`, `ASSUMED`, `OPEN`, `TESTED`, `BUILD-PENDING`,
  `PHYSICAL-PENDING`, `FAILED`, `DEPRECATED`.

---

## 3. D01–D60 decisions

| ID | Status | Decision |
|---|---|---|
| D01 | `CONFIRMED` | KDF = SHAKE256(domain || 0x00 || shared_secret32 || SHA3-256(ciphertext768), 28). |
| D02 | `CONFIRMED` | Domain string exact `TRINITY-KDF-v1`. |
| D03 | `CONFIRMED` | KDF binds SHA3-256 hash of the 768-byte ML-KEM ciphertext. |
| D04 | `CONFIRMED` | KDF output split key16, nonce_prefix8, session_id4; session ID wire interpretation big-endian. |
| D05 | `CONFIRMED` | Session-ID collision retries Encaps/KDF max 3; then SESSION_ID_COLLISION; KAT isolated. |
| D06 | `CONFIRMED` | Three fixed KDF vectors plus random differential tests. |
| D07 | `CONFIRMED` | Normative algorithm is FIPS 203 final plus recorded errata/potential updates. |
| D08 | `CONFIRMED` | Upstream is pq-code-package/mlkem-native. |
| D09 | `CONFIRMED` | Pin v1.0.0 commit 048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa; license Apache-2.0 OR MIT OR ISC; verified 2026-08-01. |
| D10 | `CONFIRMED` | Use pinned upstream as normative reference; project low-RAM adapter preserves semantics. |
| D11 | `CONFIRMED` | Use pinned upstream FIPS-202 implementation initially; changes require amendment. |
| D12 | `CONFIRMED` | Separate deterministic KAT APIs from production APIs. |
| D13 | `CONFIRMED` | Adapter follows exact pinned custom-backend API; exact mapping documented in MLKEM_BACKEND_SPEC. |
| D14 | `CONFIRMED` | Ordering/scaling match pinned upstream; no independent FPGA ordering. |
| D15 | `CONFIRMED` | Constant-time shared-secret compare; mismatch aborts and zeroizes. |
| D16 | `CONFIRMED` | SPI header 8 bytes: A5, version, command, flags, txid16 BE, payload_len16 BE. |
| D17 | `CONFIRMED` | SPI transaction ID is 16 bit. |
| D18 | `CONFIRMED` | SPI multi-byte header fields are big-endian. |
| D19 | `CONFIRMED` | SPI payload length counts payload only. |
| D20 | `CONFIRMED` | CRC16 covers header+payload, excludes CRC field. |
| D21 | `CONFIRMED` | Responses reuse command and set RESPONSE; reserved flags must be zero. |
| D22 | `CONFIRMED` | Polynomial data chunk 64 B; polynomial payload 66 B; whole packet max 76 B. |
| D23 | `CONFIRMED` | SPI command registry ranges locked; exact payloads documented in ICD, review O-013. |
| D24 | `CONFIRMED` | NTT/INTT use 8 chunks slot A; BaseMul uses A+B and result overwrites A. |
| D25 | `CONFIRMED` | No default third BaseMul result slot or concurrent operations. |
| D26 | `CONFIRMED` | Retry-safe list and non-blind-retry list locked; retire command does not retain itself. |
| D27 | `CONFIRMED` | Duplicate fingerprint uses CRC32C over command, flags, payload length and payload. |
| D28 | `CONFIRMED` | IRQ is OR of response mailbox, side-effect result and authenticated result pending. |
| D29 | `CONFIRMED` | SPI timeouts are initial defaults and may change only by evidence-backed amendment. |
| D30 | `CONFIRMED` | Zeroize retains ZEROIZED result; reset produces OUTCOME_UNKNOWN_TARGET_RESET; no unimplemented boot epoch. |
| D31 | `CONFIRMED` | 16-bit error domains and required symbolic error set locked; numeric table review O-013. |
| D32 | `CONFIRMED` | Session, P1 operation and P2 receive state sets locked. |
| D33 | `CONFIRMED` | SESSION_COMMIT uses toggle event. |
| D34 | `CONFIRMED` | Tiny samples current toggle after reset; no assumption of simultaneous reset. |
| D35 | `CONFIRMED` | Two-target stage/commit then Tiny toggle then ACTIVE verification sequence locked. |
| D36 | `CONFIRMED` | 500 ms heartbeat qualification is before commit, not a post-commit delay. |
| D37 | `CONFIRMED` | Unqualified commit is rejected and latched; old event is never applied later. |
| D38 | `CONFIRMED` | Partial commit failure aborts/zeroizes both targets and clears SN32 secret state. |
| D39 | `CONFIRMED` | SN32 confirms Tiny acceptance by polling both Primer ACTIVE status. |
| D40 | `CONFIRMED` | Minimum UART inter-frame idle gap is 1 ms. |
| D41 | `CONFIRMED` | P1 TX FSM enforces the gap. |
| D42 | `CONFIRMED` | UART framing/parity/overrun drops frame and does not increment bad-tag counter. |
| D43 | `CONFIRMED` | RESULT_PENDING_DROP increments once per attempted frame/sync candidate. |
| D44 | `CONFIRMED` | P2-ready gating and one-frame-at-a-time flow locked. |
| D45 | `CONFIRMED` | PC raw frame fixed then COBS+0 delimiter. |
| D46 | `CONFIRMED` | PC command registry includes GET/RETIRE_TXN_RESULT; payload review O-014. |
| D47 | `CONFIRMED` | PC timeout defaults: 0.5/2/5/20/120 seconds by class. |
| D48 | `CONFIRMED` | Long operations emit progress events without replacing final response. |
| D49 | `CONFIRMED` | Events may interleave and use transaction ID 0. |
| D50 | `CONFIRMED` | PC disconnect does not start new work; reconnect reconciles retained result. |
| D51 | `CONFIRMED` | Host stack Python 3.11+, pyserial, argparse, json; no initial GUI. |
| D52 | `CONFIRMED` | JSON evidence excludes secret material. |
| D53 | `CONFIRMED` | DEMO_SECURE API returns NOT_SUPPORTED until O-002 closes. |
| D54 | `CONFIRMED` | Future secure mode uses verified entropy-seeded SHAKE256 DRBG; source remains O-002 OPEN. |
| D55 | `OPEN` | Exact toolchain versions are O-012 and must be locked before target implementation. |
| D56 | `CONFIRMED` | Project/top names locked. |
| D57 | `CONFIRMED` | Single board clock, clock enables, synchronized deassert reset and fail-safe defaults. |
| D58 | `CONFIRMED` | Vendor IP allowed with reproducible config and tool dependency documentation. |
| D59 | `CONFIRMED` | Core/logical ports allowed; AI may not choose final pins; O-008 remains. |
| D60 | `CONFIRMED` | Keep Git history; no rewrite; permit .github/workflows portable-only CI exception. |

---

## 4. Normative documents

| Document | Status | Scope |
|---|---|---|
| `ai_context/architecture/FPGA_MCU_TRINITY_SYSTEM_SPEC_v0.4.md` | `CONFIRMED` | system allocation and requirements |
| `ai_context/interfaces/SPI_CONTROL_PLANE_ICD_v0.1.md` | `ASSUMED` | header confirmed; derived payload/error details require O-013 review |
| `ai_context/interfaces/PC_SN32_PROTOCOL_ICD_v0.1.md` | `ASSUMED` | frame/registry confirmed; derived command/event payloads require O-014 review |
| `ai_context/interfaces/MLKEM_BACKEND_SPEC_v0.1.md` | `ASSUMED` | exact upstream API pin confirmed; BaseMul/error mapping requires O-015 review |
| `ai_context/toolchains/TOOLCHAIN_LOCK.md` | `OPEN` | exact installed tool versions O-012 |

---

## 5. Open-item closures

| ID | Status | Closure evidence |
|---|---|---|
| O-001 | `CONFIRMED` | KDF formula and collision policy in System Spec §6 |
| O-003 | `CONFIRMED` | mlkem-native v1.0.0 commit `048fc2a7...d5bfa`, license and errata record |
| O-004 | `CONFIRMED` | SPI header, flags, txid, length, CRC and max packet sizes in SPI ICD |
| O-005 | `CONFIRMED` | toggle mechanism and reset/qualification semantics |
| O-006 | `CONFIRMED` | 1 ms minimum inter-frame idle gap |
| O-011 | `CONFIRMED` | initial PC command timeout classes |

---

## 6. Remaining open items

| ID | Status | Must resolve before |
|---|---|---|
| O-002 | `OPEN` | `DEMO_SECURE` claim/support |
| O-008 | `PHYSICAL-PENDING` | final pin/polarity/pull/CST/wiring/programming |
| O-009 | `BUILD-PENDING` | exact-device resource/timing/hardware qualification |
| O-012 | `OPEN` | target implementation and reproducible build setup |
| O-013 | `OPEN` | implementing SPI command decoder/encoder/error numeric table |
| O-014 | `OPEN` | implementing PC/SN32 command payloads and event decoder |
| O-015 | `OPEN` | implementing mlkem-native FPGA backend adapter |

---

## 7. New amendments

### A-019 — KDF and session-collision profile

`CONFIRMED`

Locks D01–D06 exactly, including max-three production collision retries and KAT isolation.

### A-020 — ML-KEM source pin

`CONFIRMED`

Pins FIPS 203 + recorded potential updates and mlkem-native v1.0.0 commit
`048fc2a7a7b4ba0ad4c989c1ac82491aa94d5bfa`, uniformly licensed
Apache-2.0 OR MIT OR ISC.

### A-021 — SPI transport header and sizing

`CONFIRMED`

Locks 8-byte header, txid16, BE header fields, CRC16, 64-byte polynomial data,
66-byte polynomial payload and 76-byte maximum packet. Derived command payloads
and numeric error assignments remain O-013.

### A-022 — Transaction fingerprint and pending-source model

`CONFIRMED`

Locks CRC32C request fingerprint, one retained side-effect result, non-recursive
retire semantics and IRQ OR-of-three-pending-sources behavior.

### A-023 — Tiny toggle commit

`CONFIRMED`

Locks toggle event, reset baseline sampling, pre-commit 500 ms heartbeat
qualification, rejection without delayed replay and dual-Primer ACTIVE confirmation.

### A-024 — UART flow control

`CONFIRMED`

Locks 1 ms TX gap, error recovery and one-frame-at-a-time P2 result gating.

### A-025 — Host protocol and timeout profile

`CONFIRMED`

Locks COBS frame, command registry, event txid zero and initial timeout classes.
Derived per-command payloads/event envelope remain O-014.

### A-026 — Toolchain gate

`OPEN`

Exact versions/builds listed in O-012 must be recorded before target implementation.

### A-027 — Git history and CI policy

`CONFIRMED`

Keep history without rewrite. Probe commits are provenance-only and absent from
active tree. `.github/workflows/` is allowed only for portable CI and must never
claim vendor/hardware PASS.

---

## 8. Implementation gate

Full integrated source remains prohibited until the owner reviews this v0.4
consolidation and closes O-012, O-013, O-014 and O-015. O-002, O-008 and O-009
retain the narrower scopes stated above.
