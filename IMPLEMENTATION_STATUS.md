# Implementation status

Status date: 2026-08-03

| Target | Source | Portable checks | Exact-device build | Bitstream | Hardware |
|---|---|---|---|---|---|
| Primer #1 | Qualified/locked | PASS at qualified source | PASS in its qualification record | Generated in qualification | Scoped hardware qualification recorded |
| Primer #2 | Deployment source complete | Reference/static PASS on post-fix commit | PASS candidate at 27 MHz | New `.fs` generated; SHA-256 not recorded | ESP32-C3 standalone PASS; system integration pending |
| SN32 / Tiny / PC | Unchanged by this change | See their target records | Unchanged | Unchanged | Unchanged |

## Primer #2 qualification identity

```text
source_commit = 7588063e636da225bbe81632efe1060f4c825c37
```

## Primer #2 exact-device result

```text
implementation_status   = DEPLOYMENT_SOURCE_COMPLETE
deployment_buildable    = true
reference/static        = PASS
RTL simulation          = NOT REPORTED FOR THIS QUALIFICATION COMMIT
exact-device build      = PASS CANDIDATE
EX2664                   = ABSENT
Fmax                     = 41.700 MHz
worst setup slack        = +13.056 ns
worst hold slack         = +0.425 ns
setup/hold violations    = 0 / 0
logic/registers/CLS      = 79% / 43% / 86%
PRIMARY/LW               = 3/8 / 8/8
bitstream_generated      = true
bitstream_sha256         = NOT RECORDED
```

`LW = 8/8` is retained as a routing-capacity risk. The post-fix build has no
reported unrouted nets, only one clock domain and positive timing margin. No
global-routing optimization is made solely to lower the LW count.

## Primer #2 standalone hardware result

```text
standalone_hardware_qualified = true
fixture                       = ESP32-C3 SPI control + UART injection
PASS count                    = 23
FAIL count                    = 0
final expected state          = SESSION_FAULT_LOCKED
final last_error              = ERR_AUTH_THRESHOLD (0x0601)
```

The standalone fixture demonstrated SPI control, UART frame injection, Ascon
decrypt/authentication, byte-exact plaintext, retained transactions, session
stage/abort/commit/activate, replay and sequence rejection, pending-result
protection, command `ZEROIZE_ALL`, re-provisioning and the three-bad-tag
fault/zeroize threshold.

The external `fatal_latched_i` pin was strapped low and not asserted. The
external `zeroize_ni` pin was strapped high and not pulsed. Command zeroize is a
separate tested path. The ESP32 fixture emulates only the secure-enable level and
does not qualify Tiny safety behavior.

## Open integration gates

```text
P1 -> P2 direct UART integration:    NOT RUN
SN32 -> P2 control plane:            NOT RUN
Tiny safety integration:             NOT RUN
external fatal input test:           NOT RUN
external zeroize input test:         NOT RUN
full-system hardware qualification:  NOT RUN
```

Therefore:

```text
standalone_hardware_qualified = true
hardware_qualified            = false
full_system_hardware_qualified= false
next_gate                     = P1_TO_P2_DIRECT_UART_INTEGRATION
```

The protected Primer #1 RTL/test/script/constraint/project paths were not
modified by this Primer #2 evidence update.
