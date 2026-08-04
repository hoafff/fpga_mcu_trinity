#ifndef TRINITY_DEPLOY_CONFIG_H
#define TRINITY_DEPLOY_CONFIG_H

#define TRINITY_DEPLOY_VERSION_MAJOR 0u
#define TRINITY_DEPLOY_VERSION_MINOR 7u
#define TRINITY_DEPLOY_VERSION_PATCH 25u

#define TRINITY_DEPLOY_ENABLE_PC_UART            1
#define TRINITY_DEPLOY_ENABLE_SPI                1
#define TRINITY_DEPLOY_ENABLE_PRIMER1            1
#define TRINITY_DEPLOY_ENABLE_PRIMER2            1
/* Default remains off until the exact pinned vendor tree is selected by Keil. */
#ifndef TRINITY_DEPLOY_ENABLE_MLKEM
#define TRINITY_DEPLOY_ENABLE_MLKEM               0
#endif
/* P1 drives the qualified direct UART link to P2; SN32 never relays payload. */
#define TRINITY_DEPLOY_ENABLE_PAYLOAD_RELAY       0
#define TRINITY_DEPLOY_ENABLE_TINY_SESSION_COMMIT 1
#define TRINITY_DEPLOY_ENABLE_DEMO_SECURE         0
#define TRINITY_DEPLOY_P1_BRINGUP_ONLY            0

/* SN32 P3.8 / PAT17 -> Tiny J1-6 session_commit_toggle_i. */
#define FPST_SN32F407_SESSION_COMMIT_PORT          3u
#define FPST_SN32F407_SESSION_COMMIT_PIN           8u

#define TRINITY_DEPLOY_UART_BAUD              115200u
/*
 * v0.7.25 uses a GPIO-driven mode-0 SPI backend on the existing DB_SPI pins.
 * Repeated hardware captures proved that SPI0 polling could emit a request for
 * which P1 captured only four or nine of ten bytes, while the same P1/P2 RTL
 * and wiring protocol passed with the ESP32-C3 controller. Driving every edge
 * explicitly removes the SPI0 FIFO/start race without changing the wire
 * protocol, board wiring, CS/IRQ ownership or fail-closed transaction policy.
 *
 * The half-period loop is deliberately conservative: loop overhead can only
 * make SCK slower than the 100 kHz ceiling. Both Primer endpoints accept gaps
 * while CS is asserted and were qualified at this maximum rate.
 */
#define TRINITY_DEPLOY_SPI_HZ                 100000u
#define TRINITY_DEPLOY_SPI_SOFTWARE_BACKEND          1
#define TRINITY_DEPLOY_SPI_HALF_PERIOD_CYCLES        60u
#define TRINITY_DEPLOY_SPI_TIMEOUT_MS            100u
#define TRINITY_DEPLOY_ENDPOINT_PROBE_MS         2000u
/* Keep the proven 200 us select/de-select margin around every transaction. */
#define TRINITY_DEPLOY_SPI_CS_GUARD_US            200u
#define TRINITY_DEPLOY_SPI_STARTUP_SETTLE_MS        5u
#define TRINITY_DEPLOY_SPI_READ_REISSUE_MAX          2u
#define TRINITY_DEPLOY_SPI_READ_RETRY_BACKOFF_MS    20u
/* Allow the Primer mailbox/IRQ synchronizers to settle after a complete
 * response before issuing the next command to either endpoint. */
#define TRINITY_DEPLOY_SPI_INTER_EXCHANGE_MS        1u
/*
 * Automatic endpoint refresh is background work.  Keep it out of an active
 * PC command burst so a just-completed PING cannot be followed immediately by
 * a periodic GPIO-SPI transfer while the next UART request is arriving.
 */
#define TRINITY_DEPLOY_PC_QUIET_BEFORE_PROBE_MS    250u
/* A long cryptographic call may keep heartbeat alive only for this bounded
 * lease. A wedged operation loses the lease and Tiny remains fail-closed. */
#define TRINITY_DEPLOY_CRYPTO_PROGRESS_LEASE_MS  5000u

#endif /* TRINITY_DEPLOY_CONFIG_H */
