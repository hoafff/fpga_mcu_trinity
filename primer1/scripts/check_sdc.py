#!/usr/bin/env python3
"""Static guard for the canonical Primer #1 Gowin SDC file."""
from __future__ import annotations

import re
from pathlib import Path

EXPECTED_FALSE_PATHS = {
    "spi_sck_i": "sck_meta",
    "spi_mosi_i": "mosi_meta",
    "spi_cs_ni": "cs_meta",
    "fatal_latched_i": "fatal_meta",
    "secure_enable_i": "secure_meta",
    "zeroize_ni": "zeroize_meta",
}

CLOCK_RE = re.compile(
    r"^create_clock\s+-name\s+sys_clk_27m\s+-period\s+37\.037\s+"
    r"\[get_ports\s+\{sys_clk_i\}\]$"
)
FALSE_PATH_RE = re.compile(
    r"^set_false_path\s+-from\s+\[get_ports\s+\{(?P<source>[A-Za-z0-9_]+)\}\]\s+"
    r"-to\s+\[get_regs\s+\{\*(?P<target>[A-Za-z0-9_]+)\*\}\]$"
)


def validate_sdc(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count("[") == text.count("]"), "unbalanced square brackets in SDC"
    assert text.count("{") == text.count("}"), "unbalanced braces in SDC"
    assert "all_registers" not in text, "unsupported all_registers collection returned"

    commands = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        command = line.split(None, 1)[0]
        assert command in {"create_clock", "set_false_path"}, (
            f"unsupported SDC command at line {lineno}: {command}"
        )
        commands.append((lineno, line))

    clock_lines = [(lineno, line) for lineno, line in commands if line.startswith("create_clock ")]
    assert len(clock_lines) == 1, "exactly one canonical system clock is required"
    assert CLOCK_RE.fullmatch(clock_lines[0][1]), (
        f"invalid 27 MHz create_clock syntax at line {clock_lines[0][0]}"
    )

    observed: dict[str, str] = {}
    false_path_lines = [
        (lineno, line) for lineno, line in commands if line.startswith("set_false_path ")
    ]
    assert len(false_path_lines) == len(EXPECTED_FALSE_PATHS), (
        "false-path count changed; only asynchronous input-to-first-stage synchronizer arcs are allowed"
    )

    for lineno, line in false_path_lines:
        assert "all_inputs" not in line and "all_outputs" not in line and "all_clocks" not in line, (
            f"over-broad false-path collection at line {lineno}"
        )
        match = FALSE_PATH_RE.fullmatch(line)
        assert match, f"unsupported or over-broad set_false_path syntax at line {lineno}"
        source = match.group("source")
        target = match.group("target")
        assert source not in observed, f"duplicate false path for {source}"
        observed[source] = target

    assert observed == EXPECTED_FALSE_PATHS, (
        f"unexpected synchronizer exception map: {observed!r}"
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    validate_sdc(root / "constraints/primer1.sdc")
    print("PASS gowin_sdc_syntax_guard")
    print("PASS sys_clk_27m_constraint")
    print("PASS async_inputs_to_first_stage_only")


if __name__ == "__main__":
    main()
