from __future__ import annotations

import argparse
import sys

from . import cli as legacy_cli
from . import full_cli
from .serial_client import HostProtocolError, RemoteError, TrinitySerialClient

_UNSAFE_MLKEM_BUILD_IDS = frozenset({0x0007001A})
_UNSAFE_MLKEM_COMMANDS = frozenset(
    {
        "keypair-generate",
        "session-create",
        "sn32-secure-telemetry-qualify",
    }
)


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


def _option_value(argv: list[str], name: str) -> str | None:
    prefix = f"{name}="
    for index, token in enumerate(argv):
        if token.startswith(prefix):
            return token[len(prefix):]
        if token == name and index + 1 < len(argv):
            return argv[index + 1]
    return None


def _unsafe_mlkem_guard(argv: list[str], command: str | None) -> int | None:
    if command not in _UNSAFE_MLKEM_COMMANDS:
        return None
    port = _option_value(argv, "--port")
    if port is None:
        return None
    baud_text = _option_value(argv, "--baud")
    try:
        baud = 115200 if baud_text is None else int(baud_text, 0)
        with TrinitySerialClient(port, baudrate=baud) as client:
            info = client.get_system_info()
    except (RemoteError, HostProtocolError, TimeoutError, OSError, ValueError) as exc:
        print(f"FAIL: ML-KEM safety preflight failed: {exc}", file=sys.stderr)
        return 1

    if info.sn32_build_id not in _UNSAFE_MLKEM_BUILD_IDS:
        return None
    print(
        "FAIL: SN32 build 0x0007001A has a confirmed 8 KiB-RAM/2 KiB-stack "
        "ML-KEM key-generation blocker. Do not run keypair, session creation "
        "or full secure-telemetry qualification on this image. The dual-SPI "
        "control-plane command sn32-qualify remains valid within its locked "
        "scope.",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    actual = list(sys.argv[1:] if argv is None else argv)
    commands = _all_command_names()
    command = next((token for token in actual if token in commands), None)
    has_command = command is not None
    asks_for_help = "-h" in actual or "--help" in actual

    if asks_for_help and not has_command:
        _build_combined_help_parser().print_help()
        return 0
    if not actual:
        _build_combined_help_parser().print_help()
        return 2
    if not asks_for_help:
        guarded = _unsafe_mlkem_guard(actual, command)
        if guarded is not None:
            return guarded
    return full_cli.main(actual)


if __name__ == "__main__":
    raise SystemExit(main())
