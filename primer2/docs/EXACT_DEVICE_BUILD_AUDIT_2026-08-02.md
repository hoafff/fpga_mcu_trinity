# Primer #2 exact-device build audit — 2026-08-02

## Evidence identity

User-supplied reports were generated on a physical Windows workstation at
`2026-08-02 22:58:45 +07:00` with:

```text
Gowin EDA:      V1.9.11.03 Education
Part:           GW2A-LV18PG256C8/I7
Device:         GW2A-18
Device version: C
Top:            primer2_top
Clock:          sys_clk_27m, 27.000 MHz
```

The report does not embed a Git commit SHA or bitstream SHA-256. It proves the
reported local source/configuration built, but it does not cryptographically bind
that build to a repository commit.

## Accepted pre-fix result

```text
Exact-device synthesis:       PASS WITH EX2664 WARNING
Place & Route:                PASS
Timing 27 MHz:                PASS
Bitstream generated:          PASS (reported by user; SHA-256 not supplied)
Hardware qualification:       NOT PERFORMED
```

Timing evidence:

```text
Actual Fmax:               52.874 MHz
Worst setup slack:         +18.124 ns
Worst hold slack:          +0.307 ns
Setup violated endpoints:  0
Hold violated endpoints:   0
Setup TNS:                 0.000 ns
Hold TNS:                  0.000 ns
Paths analyzed:            20,947
Endpoints analyzed:        18,880
```

Resource evidence:

```text
Logic:       16,337 / 20,736 = 79%
Registers:    6,890 / 16,173 = 43%
CLS:          8,880 / 10,368 = 86%
I/O ports:       13 / 207    = 7%
Logic latches:                 0
PRIMARY:                       3 / 8
LW:                            8 / 8
GCLK pin:                      1 / 8
```

All 13 deployment ports were constrained and reported as LVCMOS33 at the locked
pin locations. No CST location is changed by this audit.

## EX2664 root cause and correction

The old `always_comb` block calculated `rx_accept_enable_o` using `!fault_o`, then
assigned `fault_o` later in the same block. Gowin therefore saw a combinational
output read before assignment and warned that synthesis and simulation could
differ.

The corrected block assigns:

```systemverilog
fault_o = fault_latched | (session_state == SESSION_FAULT_LOCKED);
```

and derives receive enable directly from the same registered state expression.
`fault_latched` is a sequential register. It is set by external fatal, self-test
failure, or the bad-tag threshold and is cleared only by reset. The session state
is also sequential. The correction introduces no latch, no combinational
feedback and no weakening of fail-closed behavior.

## Clock/global-routing audit

The STA report contains exactly one clock:

```text
sys_clk_27m, base clock, 37.037 ns
```

All listed setup and hold paths launch and capture on `sys_clk_27m`. The PnR
"Global Clock Signals" table also lists Ascon/plaintext/SPI/internal nets on
PRIMARY or LW resources. Since these nets do not appear as STA clocks and the RTL
uses only `clk_i`/`sys_clk_i` as positive-edge clocks, they are treated as Gowin
high-fanout routing promotion rather than generated clock domains.

The design does have broad datapaths and decode/control fanout: Ascon state/key
and quarantine plaintext are 64–192 bits wide; the SPI mailbox is 528 bits; and
status/session controls feed many registers. This explains why data/control nets
may be promoted. The submitted timing report also identifies very high fanout on
internal control nets while still reporting positive slack.

`LW = 8/8` is accepted only as a risk note for the superseded build. It leaves no
LW routing margin. No global-promotion option is disabled without a clean rebuild
showing a functional/timing benefit. The post-fix build must compare PRIMARY/LW,
logic/CLS, WNS/TNS and warnings because small RTL changes can alter promotion and
placement.

## Pin and bias audit

The report shows `Pull Mode NONE` on:

```text
uart_rx_i
fatal_latched_i
secure_enable_i
zeroize_ni
```

The controlled wiring contract assigns these to active external drivers:
Primer #1 drives UART RX; Tiny drives fatal, secure-enable and zeroize. No
external resistor bias for these four nets is proven by the current evidence, so
no pull is added to the CST.

When Tiny/Primer #1 are disconnected, the inputs must not float. A standalone
3.3 V harness must drive `secure_enable_i=0`, `fatal_latched_i=0`,
`zeroize_ni=1`, and UART idle high until the test sequence intentionally changes
them. This is a bring-up fixture, not a production wiring change.

## Supersession boundary

The accepted reports predate the `fault_o` correction and clean SystemVerilog
build-flow update. Their timing and bitstream are therefore superseded. They may
not be reused to mark the current source as an exact-device PASS.

Required next evidence:

1. static/reference checks on the corrected commit;
2. all nine Icarus benches, including deterministic fault output and three-bad-
   tag threshold;
3. clean `gw_sh run.tcl` build after deleting old `impl/`;
4. new synthesis warning list, PnR/resource/clock report, timing report and `.fs`
   SHA-256;
5. later SRAM programming and physical P1-to-P2 testing before any hardware PASS.
