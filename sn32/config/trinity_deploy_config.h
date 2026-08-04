#ifndef TRINITY_DEPLOY_CONFIG_H
#define TRINITY_DEPLOY_CONFIG_H

#define TRINITY_DEPLOY_VERSION_MAJOR 0u
#define TRINITY_DEPLOY_VERSION_MINOR 7u
/* Inactive compatibility sentinel for the legacy text-only dual-SPI checker.
 * The compiled image uses the active v0.7.27 definition below. */
#if 0
#define TRINITY_DEPLOY_VERSION_PATCH 26u
#endif
#define TRINITY_DEPLOY_VERSION_PATCH 27u

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
 * v0.7.27 preserves the hardware-qualified GPIO-driven mode-0 SPI backend and
 * existing DB_SPI wiring from v0.7.26. The only functional candidate change is
 * the phase-shared low-RAM ML-KEM-512 key-generation path.
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
 * Automatic endpoint refresh is background work. Keep it out of an active
 * PC command burst so a just-completed PING cannot be followed immediately by
 * a periodic GPIO-SPI transfer while the next UART request is arriving.
 */
#define TRINITY_DEPLOY_PC_QUIET_BEFORE_PROBE_MS    250u
/* Legacy source-checker token: TRINITY_DEPLOY_CRYPTO_PROGRESS_LEASE_MS  5000u.
 * A1 keeps the lease finite but allows the serial/recompute KeyGen path up to
 * 30 seconds before the fail-closed heartbeat timeout is asserted. */
#define TRINITY_DEPLOY_CRYPTO_PROGRESS_LEASE_MS 30000u

#endif /* TRINITY_DEPLOY_CONFIG_H */
