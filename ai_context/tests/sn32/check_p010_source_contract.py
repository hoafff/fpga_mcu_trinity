#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
PLATFORM = ROOT / "sn32/firmware/platform/sn32f407"

def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)

def ordered(text: str, needles: list[str], label: str) -> None:
    cursor = 0
    for needle in needles:
        position = text.find(needle, cursor)
        if position < 0:
            fail(f"{label}: missing or out-of-order token {needle!r}")
        cursor = position + len(needle)

guard = (PLATFORM / "fpst_sn32f407_p010_guard.c").read_text()
port = (PLATFORM / "fpst_sn32f407_port.c").read_text()
profile = (PLATFORM / "board_profile.h").read_text()
for token in (
    "P010_PIN = 10u", "P011_PIN = 11u", "GPIO_CFG_NO_PULL_SCHMITT = 2u",
    "PFPA_UART0_P31_P32 = 0x0Au", "PFPA_I2C0_AWAY_FROM_P010_P011 = 0x00u",
    "PFPA_CT16B1_AWAY_FROM_P010_P011 = 0x00u", "I2C0_CLOCK_OR_RESET = (1u << 21)",
    "CMP_CLOCK_OR_RESET = (1u << 14)", "CT16B1_CLOCK_OR_RESET = (1u << 6)",
    "*regs->sys1_prst = FORBIDDEN_CLOCK_MASK",
    "*regs->sys1_ahbclken &= ~FORBIDDEN_CLOCK_MASK",
):
    if token not in guard:
        fail(f"register policy token missing: {token}")
ordered(guard, ["*regs->gpio0_mode &= ~GPIO_MODE_INPUT_MASK", "*regs->pfpa_uart0 =", "*regs->pfpa_i2c0 =", "*regs->pfpa_ct16b1 =", "*regs->sys1_prst = FORBIDDEN_CLOCK_MASK", "*regs->sys1_ahbclken &= ~FORBIDDEN_CLOCK_MASK"], "P0.10/P0.11 guard application order")
for binding in (
    ".gpio0_mode = &SN_GPIO0->MODE", ".gpio0_cfg = &SN_GPIO0->CFG",
    ".pfpa_uart0 = &SN_PFPA->UART0", ".pfpa_i2c0 = &SN_PFPA->I2C0",
    ".pfpa_ct16b1 = &SN_PFPA->CT16B1", ".sys1_ahbclken = &SN_SYS1->AHBCLKEN",
    ".sys1_prst = &SN_SYS1->PRST",
):
    if binding not in port:
        fail(f"DFP register binding missing: {binding}")
if "#define FPST_SN32F407_PFPA_UART0_VALUE       0x0000000Au" not in profile:
    fail("board profile does not lock UART0 to PFPA route 2/2")
ordered(port, ["init_pinmux();", "rc = init_uart0();"], "platform init")
for filename in ("fpst_sn32f407_main.c", "fpst_sn32f407_dual_main.c"):
    source = (PLATFORM / filename).read_text()
    ordered(source, ["fpst_sn32f407_p010_early_lock();", "SystemInit();", "fpst_sn32f407_p010_early_lock();", "SystemCoreClockUpdate();"], filename)
handler = re.search(r"void SysTick_Handler\(void\) \{(.*?)\n\}", port, re.DOTALL)
if handler is None:
    fail("SysTick_Handler body not found")
for token in ("g_p010_guard_armed", "p010_guard_check()", "g_p010_guard_failed = true", "g_p010_guard_violations |= violations", "g_heartbeat_ready = false", "p010_guard_restore()"):
    if token not in handler.group(1):
        fail(f"runtime guard action missing: {token}")
print("PASS: relocated SN32 P0.10/P0.11 static integration contract")
