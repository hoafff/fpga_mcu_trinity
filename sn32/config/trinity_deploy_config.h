#ifndef TRINITY_DEPLOY_CONFIG_H
#define TRINITY_DEPLOY_CONFIG_H

#define TRINITY_DEPLOY_VERSION_MAJOR 0u
#define TRINITY_DEPLOY_VERSION_MINOR 5u
#define TRINITY_DEPLOY_VERSION_PATCH 1u

#define TRINITY_DEPLOY_ENABLE_PC_UART            1
#define TRINITY_DEPLOY_ENABLE_SPI                1
#define TRINITY_DEPLOY_ENABLE_PRIMER1            1
#define TRINITY_DEPLOY_ENABLE_PRIMER2            1
#define TRINITY_DEPLOY_ENABLE_MLKEM               0
#define TRINITY_DEPLOY_ENABLE_PAYLOAD_RELAY       0
#define TRINITY_DEPLOY_ENABLE_TINY_SESSION_COMMIT 0
#define TRINITY_DEPLOY_ENABLE_DEMO_SECURE         0

/*
 * Hardware gate currently authorized: PC -> SN32 -> Primer #1 control plane.
 * Primer #2 remains in the shared pin profile but is neither required nor
 * probed until this flag is changed after the P1 gate is accepted.
 */
#define TRINITY_DEPLOY_P1_BRINGUP_ONLY            1

#define TRINITY_DEPLOY_UART_BAUD              115200u
#define TRINITY_DEPLOY_SPI_HZ                1000000u
#define TRINITY_DEPLOY_SPI_TIMEOUT_MS            100u
#define TRINITY_DEPLOY_ENDPOINT_PROBE_MS         2000u

#endif /* TRINITY_DEPLOY_CONFIG_H */
