#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "sn32/src/app"
PARTS = [APP / f"trinity_deploy_main_part_{index:02d}.inc" for index in range(18)]
SYSTEM_SOURCE = ROOT / "sn32/keil/RTE/Device/SN32F407F/system_SN32F400.c"

# Expected open-delimiter stack after each include fragment. These signatures
# document every intentional cross-file continuation in trinity_deploy_main.c.
EXPECTED_STACKS = (
    "{",   # 00 -> enum continues
    "{",   # 01 -> g_p1 initializer continues
    "{",   # 02 -> gpio_set_cfg continues
    "{",   # 03 -> set_error continues
    "{(",  # 04 -> gpio_init and gpio_set_cfg call continue
    "{",   # 05 -> uart_read continues
    "{",   # 06 -> next_spi_txid continues
    "{{",  # 07 -> endpoint_exchange while loop continues
    "",    # 08 -> endpoint_exchange complete
    "",    # 09 -> standalone retired-helper marker
    "{(",  # 10 -> response_send and encode call continue
    "",    # 11 -> response_send and handle_ping complete
    "{",   # 12 -> handle_run_self_test continues
    "",    # 13 -> self-test and transaction-result handlers complete
    "",    # 14 -> retire handler complete
    "{",   # 15 -> handle_request continues
    "{",   # 16 -> hardware_init continues
    "",    # 17 -> hardware_init and main complete
)

OPEN_TO_CLOSE = {"{": "}", "(": ")", "[": "]"}
CLOSE_TO_OPEN = {value: key for key, value in OPEN_TO_CLOSE.items()}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def scan_fragment(
    path: Path,
    stack: list[tuple[str, Path, int, int]],
    state: str,
) -> str:
    text = path.read_text(encoding="utf-8")
    line = 1
    column = 0
    index = 0
    escape = False

    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        column += 1

        if state == "line_comment":
            if char == "\n":
                state = "normal"
        elif state == "block_comment":
            if char == "*" and next_char == "/":
                state = "normal"
                index += 1
                column += 1
        elif state in {"string", "character"}:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif (state == "string" and char == '"') or (
                state == "character" and char == "'"
            ):
                state = "normal"
            elif char == "\n":
                fail(f"unterminated {state} at {path.relative_to(ROOT)}:{line}")
        else:
            if char == "/" and next_char == "/":
                state = "line_comment"
                index += 1
                column += 1
            elif char == "/" and next_char == "*":
                state = "block_comment"
                index += 1
                column += 1
            elif char == '"':
                state = "string"
                escape = False
            elif char == "'":
                state = "character"
                escape = False
            elif char in OPEN_TO_CLOSE:
                stack.append((char, path, line, column))
            elif char in CLOSE_TO_OPEN:
                if not stack:
                    fail(
                        f"unmatched {char} at {path.relative_to(ROOT)}:"
                        f"{line}:{column}"
                    )
                opening, opening_path, opening_line, opening_column = stack.pop()
                if opening != CLOSE_TO_OPEN[char]:
                    fail(
                        f"mismatched {opening} from "
                        f"{opening_path.relative_to(ROOT)}:{opening_line}:"
                        f"{opening_column} closed by {char} at "
                        f"{path.relative_to(ROOT)}:{line}:{column}"
                    )

        if char == "\n":
            line += 1
            column = 0
        index += 1

    if state == "line_comment":
        state = "normal"
    return state


def check_fragment_boundaries() -> None:
    stack: list[tuple[str, Path, int, int]] = []
    state = "normal"

    for part, expected in zip(PARTS, EXPECTED_STACKS, strict=True):
        if not part.is_file():
            fail(f"missing {part.relative_to(ROOT)}")
        state = scan_fragment(part, stack, state)
        if state != "normal":
            fail(f"lexical state {state} crosses {part.relative_to(ROOT)} boundary")
        actual = "".join(item[0] for item in stack)
        if actual != expected:
            fail(
                f"unexpected delimiter stack after {part.name}: "
                f"expected {expected!r}, got {actual!r}"
            )

    if stack:
        opening, path, line, column = stack[-1]
        fail(
            f"unclosed {opening} from {path.relative_to(ROOT)}:"
            f"{line}:{column}"
        )

    part_12 = PARTS[12].read_text(encoding="utf-8")
    first_code_line = next(
        (line.strip() for line in part_12.splitlines() if line.strip()), ""
    )
    if first_code_line != "static void handle_get_system_info(const trinity_pc_frame_t *req) {":
        fail("part_12 must begin with the complete handle_get_system_info definition")
    for token in (
        "trinity_error_code_t rc;",
        "if (!request_length_is(req, 0u))",
        "rc = full_probe_all();",
        "static void handle_get_system_status",
    ):
        if token not in part_12:
            fail(f"part_12 missing {token}")

    assembled = "\n".join(part.read_text(encoding="utf-8") for part in PARTS)
    for handler in (
        "handle_ping",
        "handle_get_system_info",
        "handle_get_system_status",
        "handle_get_last_error",
        "handle_run_self_test",
        "handle_get_txn_result",
        "handle_retire_txn_result",
        "handle_request",
        "hardware_init",
    ):
        definitions = len(re.findall(rf"\b(?:static\s+)?(?:void|bool|uint8_t|uint16_t|uint32_t|trinity_error_code_t)\s+{handler}\s*\(", assembled))
        if definitions != 1:
            fail(f"expected one definition of {handler}, found {definitions}")

    print("PASS: all 18 deploy .inc delimiter signatures match the locked composition")
    print("PASS: handle_get_system_info has a complete declaration, validation and body")


def check_system_clock_fallback() -> None:
    if not SYSTEM_SOURCE.is_file():
        fail(f"missing tracked {SYSTEM_SOURCE.relative_to(ROOT)}")
    source = SYSTEM_SOURCE.read_text(encoding="utf-8")
    if re.search(r"uint32_t\s+AHB_prescaler\s*=\s*0", source):
        fail("AHB_prescaler must not be initialized to zero")
    switch_match = re.search(
        r"switch\s*\(SN_SYS0->AHBCP_b\.AHBPRE\)(.*?)"
        r"SystemCoreClock\s*/=\s*AHB_prescaler\s*;",
        source,
        re.S,
    )
    if switch_match is None:
        fail("cannot locate the AHB prescaler switch and division")
    switch_body = switch_match.group(1)
    if re.search(
        r"default\s*:\s*(?:/\*.*?\*/\s*)?"
        r"AHB_prescaler\s*=\s*1u?\s*;\s*break\s*;",
        switch_body,
        re.S,
    ) is None:
        fail("reserved AHBPRE encoding must select a divide-by-one fallback")
    print("PASS: reserved AHBPRE values use a non-zero divide-by-one fallback")


def main() -> int:
    check_fragment_boundaries()
    check_system_clock_fallback()
    return 0


if __name__ == "__main__":
    sys.exit(main())
