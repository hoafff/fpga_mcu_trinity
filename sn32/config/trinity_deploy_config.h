#ifndef TRINITY_DEPLOY_CONFIG_H
#define TRINITY_DEPLOY_CONFIG_H

#define TRINITY_DEPLOY_VERSION_MAJOR 0u
#define TRINITY_DEPLOY_VERSION_MINOR 7u
/* Inactive compatibility sentinel for the legacy text-only dual-SPI checker.
 * The compiled image uses the active v0.7.30 definition below. */
#if 0
#define TRINITY_DEPLOY_VERSION_PATCH 26u
#endif
#define TRINITY_DEPLOY_VERSION_PATCH 30u

#define TRINITY_DEPLOY_ENABLE_PC_UART            1
#define TRINITY_DEPLOY_ENABLE_SPI                1
#define TRINITY_DEPLOY_ENABLE_PRIMER1            1
#define TRINITY_DEPLOY_ENABLE_PRIMER2            1
#ifndef TRINITY_DEPLOY_ENABLE_MLKEM
#define TRINITY_DEPLOY_ENABLE_MLKEM               0
#endif
#define TRINITY_DEPLOY_ENABLE_PAYLOAD_RELAY       0
#define TRINITY_DEPLOY_ENABLE_TINY_SESSION_COMMIT 1
#define TRINITY_DEPLOY_ENABLE_DEMO_SECURE         0
#define TRINITY_DEPLOY_P1_BRINGUP_ONLY            0

/*
 * Time-bounded competition demo profile. Tiny 1P5 is outside the qualified
 * scope. P2.9 is the single direct shared SECURE_ENABLE/T12 owner and the
 * periodic physical heartbeat waveform is disabled on this pin.
 */
#define TRINITY_DEPLOY_CORE_DEMO_WITHOUT_TINY       1
#define TRINITY_DEPLOY_DIRECT_SECURE_ENABLE_OUTPUT  1
#define TRINITY_DEPLOY_ENABLE_MCU_HEARTBEAT_OUTPUT  0

#if 0
#define FPST_SN32F407_SESSION_COMMIT_PORT          3u
#define FPST_SN32F407_SESSION_COMMIT_PIN           8u
#endif
#define FPST_SN32F407_SESSION_COMMIT_PORT          2u
#define FPST_SN32F407_SESSION_COMMIT_PIN           9u

#define TRINITY_DEPLOY_UART_BAUD              115200u
/*
 * v0.7.30 keeps the v0.7.29 low-RAM ML-KEM and core-demo datapath. It adds
 * retained session-activation diagnostics, explicit P2.9 GPIO readback and a
 * fail-safe emergency zeroize path that can preempt a completed failed host
 * transaction. P1/P2 RTL and bitstreams remain unchanged.
 */
#define TRINITY_DEPLOY_SPI_HZ                 100000u
#define TRINITY_DEPLOY_SPI_SOFTWARE_BACKEND          1
#define TRINITY_DEPLOY_SPI_HALF_PERIOD_CYCLES        60u
#define TRINITY_DEPLOY_SPI_TIMEOUT_MS            100u
#define TRINITY_DEPLOY_ENDPOINT_PROBE_MS         2000u
#define TRINITY_DEPLOY_SPI_CS_GUARD_US            200u
#define TRINITY_DEPLOY_SPI_STARTUP_SETTLE_MS        5u
#define TRINITY_DEPLOY_SPI_READ_REISSUE_MAX          2u
#define TRINITY_DEPLOY_SPI_READ_RETRY_BACKOFF_MS    20u
#define TRINITY_DEPLOY_SPI_STARTUP_RECOVERY_MS    10000u
#define TRINITY_DEPLOY_SPI_STARTUP_RECOVERY_BACKOFF_MS 250u
#define TRINITY_DEPLOY_SPI_INTER_EXCHANGE_MS        1u
#define TRINITY_DEPLOY_PC_QUIET_BEFORE_PROBE_MS    250u
/* Legacy source-checker token: TRINITY_DEPLOY_CRYPTO_PROGRESS_LEASE_MS  5000u. */
#define TRINITY_DEPLOY_CRYPTO_PROGRESS_LEASE_MS 120000u

#endif /* TRINITY_DEPLOY_CONFIG_H */
