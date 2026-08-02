# Implementation status

Status date: 2026-08-02

| Target | Source | Portable checks | Exact-device build | Bitstream | Hardware |
|---|---|---|---|---|---|
| Primer #1 | Qualified/locked | PASS at qualified source | PASS in its qualification record | Generated in qualification | Scoped hardware qualification recorded |
| Primer #2 | Deployment source complete; fault/config fix committed | Rerun required on current source | Pre-fix build passed with EX2664 and is superseded | Pre-fix generated; current source requires new `.fs` | Pending physical test |
| SN32 / Tiny / PC | Unchanged by this change | See their target records | Unchanged | Unchanged | Unchanged |

## Primer #2 gate detail

```text
implementation_status   = DEPLOYMENT_SOURCE_COMPLETE_REBUILD_REQUIRED
deployment_buildable    = true
pre-fix exact build     = synthesis/PnR/timing/bitstream PASS with EX2664 warning
pre-fix timing          = 27 MHz PASS; setup +18.124 ns; hold +0.307 ns
current reference/static= RERUN REQUIRED
current RTL simulation  = RERUN REQUIRED (nine benches)
current exact build     = CLEAN REBUILD REQUIRED
current bitstream       = not accepted
hardware_qualified      = false
```

The pre-fix reports are recorded in
`primer2/docs/EXACT_DEVICE_BUILD_AUDIT_2026-08-02.md`. They validate the submitted
local build but do not bind a Git commit or `.fs` SHA-256, and they predate the
`fault_o` correction and clean SystemVerilog 2017 flow.

The protected Primer #1 RTL/test/script/constraint/project paths are not modified
by this Primer #2 correction.
