#ifndef TRINITY_DEPLOY_CONFIG_H
#define TRINITY_DEPLOY_CONFIG_H

#define TRINITY_DEPLOY_VERSION_MAJOR 0u
#define TRINITY_DEPLOY_VERSION_MINOR 6u
#define TRINITY_DEPLOY_VERSION_PATCH 0u

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
#define TRINITY_DEPLOY_SPI_HZ                1000000u
#define TRINITY_DEPLOY_SPI_TIMEOUT_MS            100u
#define TRINITY_DEPLOY_ENDPOINT_PROBE_MS         2000u

#endif /* TRINITY_DEPLOY_CONFIG_H */
