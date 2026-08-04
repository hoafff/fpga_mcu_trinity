#ifndef TRINITY_DEPLOY_CONFIG_H
#define TRINITY_DEPLOY_CONFIG_H

#define TRINITY_DEPLOY_VERSION_MAJOR 0u
#define TRINITY_DEPLOY_VERSION_MINOR 7u
#define TRINITY_DEPLOY_VERSION_PATCH 22u

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
/* First SN32 dual-SPI hardware qualification uses the same conservative clock
 * already proven by the ESP32-C3 P1/P2 harness. With a 12 MHz peripheral clock,
 * SPI0 SCK = PCLK / (2 * (CLKDIV + 1)); CLKDIV=59 gives exactly 100 kHz. */
#define TRINITY_DEPLOY_SPI_HZ                 100000u
#define TRINITY_DEPLOY_SPI_CLKDIV                 59u
#define TRINITY_DEPLOY_SPI_TIMEOUT_MS            100u
#define TRINITY_DEPLOY_ENDPOINT_PROBE_MS         2000u
/* P1 diagnostic D002 returned fields matching the request after its first six
 * bits were removed. At 100 kHz that is 60 us. v0.7.18 expanded the existing
 * CS guard to 200 us before and after every transaction. v0.7.22 retains that
 * timing, validates a complete mailbox before accepting it and permits two
 * bounded reissues of side-effect-free discovery/status reads after transport
 * corruption. Applying the same policy to P2 avoids a target-dependent path;
 * packet bytes, SPI mode and clock rate remain unchanged. */
#define TRINITY_DEPLOY_SPI_CS_GUARD_US            200u
#define TRINITY_DEPLOY_P1_CS_SETUP_US              200u
#define TRINITY_DEPLOY_SPI_STARTUP_SETTLE_MS        5u
#define TRINITY_DEPLOY_SPI_READ_REISSUE_MAX          2u
#define TRINITY_DEPLOY_SPI_READ_RETRY_BACKOFF_MS    20u
/* Allow the Primer mailbox/IRQ synchronizers to settle after a complete
 * response before issuing the next command to either endpoint. */
#define TRINITY_DEPLOY_SPI_INTER_EXCHANGE_MS        1u
/* A long cryptographic call may keep heartbeat alive only for this bounded
 * lease. A wedged operation loses the lease and Tiny remains fail-closed. */
#define TRINITY_DEPLOY_CRYPTO_PROGRESS_LEASE_MS  5000u

#endif /* TRINITY_DEPLOY_CONFIG_H */
