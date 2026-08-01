#include <stdint.h>

#include <SN32F400.h>

#include "trinity_build_config.h"

/* Provided by SONiX.SN32F4_DFP.1.1.1 Device:Startup component. */
extern void SystemInit(void);
extern void SystemCoreClockUpdate(void);
extern uint32_t SystemCoreClock;

/* Debug-visible S0 marker; it is not a deployment or health indication. */
static volatile uint32_t g_trinity_s0_boot_marker;

void trinity_main(void)
{
    /*
     * The known-good SONiX startup instance transfers to __main without calling
     * SystemInit. S0 therefore invokes the exact DFP SystemInit explicitly,
     * then refreshes the CMSIS clock variable before entering a safe idle loop.
     */
    SystemInit();
    SystemCoreClockUpdate();

    g_trinity_s0_boot_marker =
        (SystemCoreClock == TRINITY_EXACT_TARGET_CLOCK_HZ)
            ? UINT32_C(0x53304F4B) /* "S0OK" */
            : UINT32_C(0x53304552); /* "S0ER" */

    /*
     * S0 intentionally leaves UART, SPI, ML-KEM, SESSION_COMMIT and all
     * inter-board access disabled. No Trinity GPIO is changed from reset state.
     */
    for (;;) {
        __NOP();
    }
}

int main(void)
{
    trinity_main();
    return 0;
}
