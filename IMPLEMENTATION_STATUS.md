# Implementation status

Status date: 2026-08-02

| Target | Source | Portable checks | Exact-device build | Bitstream | Hardware |
|---|---|---|---|---|---|
| Primer #1 | Qualified/locked | PASS at qualified source | PASS in its qualification record | Generated in qualification | Scoped hardware qualification recorded |
| Primer #2 | Deployment source complete | Static/reference PASS | NOT RUN: Gowin unavailable here | Not generated | Pending physical test |
| SN32 / Tiny / PC | Unchanged by this change | See their target records | Unchanged | Unchanged | Unchanged |

## Primer #2 gate detail

```text
implementation_status = DEPLOYMENT_SOURCE_COMPLETE
deployment_buildable   = true
reference/static       = PASS
RTL simulation         = NOT RUN (iverilog/vvp unavailable)
exact-device build     = NOT RUN (Gowin unavailable)
bitstream_generated    = false
hardware_qualified     = false
next_gate              = PRIMER2_RTL_SIMULATION_AND_EXACT_DEVICE_BUILD
```

`deployment_buildable = true` means the synthesizable RTL hierarchy, exact-device
Gowin project, constraints and build script are present. It is not an exact-device
PASS claim. Utilization, WNS, TNS and `.fs` identity remain unavailable until the
vendor build is executed successfully.

The protected Primer #1 RTL/test/script/constraint/project paths are not modified
by the Primer #2 implementation commit.
