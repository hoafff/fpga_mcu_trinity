#ifndef TRINITY_BUILD_CONFIG_H
#define TRINITY_BUILD_CONFIG_H

#define TRINITY_BASELINE_VERSION_MAJOR 0u
#define TRINITY_BASELINE_VERSION_MINOR 4u
#define TRINITY_EXACT_TARGET_CLOCK_HZ   12000000u

/* S0 is exact-target bring-up only. These gates must remain disabled. */
#define TRINITY_ENABLE_PC_UART             0
#define TRINITY_ENABLE_SPI                 0
#define TRINITY_ENABLE_MLKEM               0
#define TRINITY_ENABLE_TINY_SESSION_COMMIT 0
#define TRINITY_ENABLE_DEMO_SECURE         0

#if (TRINITY_ENABLE_PC_UART != 0)
#error "S0 must not enable PC UART"
#endif
#if (TRINITY_ENABLE_SPI != 0)
#error "S0 must not enable SPI"
#endif
#if (TRINITY_ENABLE_MLKEM != 0)
#error "S0 must not enable ML-KEM"
#endif
#if (TRINITY_ENABLE_TINY_SESSION_COMMIT != 0)
#error "S0 must not toggle SESSION_COMMIT"
#endif
#if (TRINITY_ENABLE_DEMO_SECURE != 0)
#error "DEMO_SECURE remains NOT_SUPPORTED"
#endif

#endif /* TRINITY_BUILD_CONFIG_H */
