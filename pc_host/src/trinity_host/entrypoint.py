from __future__ import annotations

import argparse
import sys

from . import cli as legacy_cli
from . import full_cli


def _subcommand_help(
    parser: argparse.ArgumentParser,
) -> tuple[tuple[str, str | None], ...]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return tuple(
                (choice.dest, choice.help)
                for choice in action._choices_actions
            )
    return ()


def _all_command_names() -> frozenset[str]:
    commands = {
        name
        for parser in (legacy_cli._build_parser(), full_cli._build_parser())
        for name, _help in _subcommand_help(parser)
    }
    return frozenset(commands)


def _build_combined_help_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trinity-host",
        description=(
            "FPGA MCU Trinity PC↔SN32 bring-up and secure-telemetry "
            "qualification client"
        ),
    )
    parser.add_argument("--port", help="SN32 UART COM port, for example COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit one JSON object per step",
    )
    subparsers = parser.add_subparsers(dest="command")
    added: set[str] = set()
    for source in (legacy_cli._build_parser(), full_cli._build_parser()):
        for name, help_text in _subcommand_help(source):
            if name in added:
                continue
            subparsers.add_parser(name, help=help_text)
            added.add(name)
    return parser


def main(argv: list[str] | None = None) -> int:
    actual = list(sys.argv[1:] if argv is None else argv)
    commands = _all_command_names()
    has_command = any(token in commands for token in actual)
    asks_for_help = "-h" in actual or "--help" in actual

    if asks_for_help and not has_command:
        _build_combined_help_parser().print_help()
        return 0
    if not actual:
        _build_combined_help_parser().print_help()
        return 2
    return full_cli.main(actual)


if __name__ == "__main__":
    raise SystemExit(main())
