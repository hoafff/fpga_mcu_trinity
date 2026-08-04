from __future__ import annotations

import argparse
import json
import sys

from . import cli as legacy_cli
from .full_flow import (
    DEFAULT_KEYPAIR_SEED,
    DEFAULT_PLAINTEXTS,
    DEFAULT_SESSION_SEED,
    close_session,
    create_session,
    generate_keypair,
    parse_plaintext_hex,
    parse_seed_hex,
    run_secure_telemetry_qualification,
    send_telemetry,
    zeroize,
)
from .protocol import ZeroizeScope
from .serial_client import HostProtocolError, RemoteError, TrinitySerialClient

_FULL_COMMANDS = {
    "keypair-generate",
    "session-create",
    "telemetry-send",
    "session-close",
    "zeroize",
    "sn32-secure-telemetry-qualify",
}


def _emit(data: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, sort_keys=True))
        return
    label = data.pop("step", None)
    if label is not None:
        print(f"[{label}]")
    for key, value in data.items():
        print(f"{key}={value}")


def _contains_full_command(argv: list[str]) -> bool:
    return any(token in _FULL_COMMANDS for token in argv)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trinity-host",
        description="FPGA MCU Trinity secure-telemetry qualification client",
    )
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    keypair = sub.add_parser(
        "keypair-generate",
        help="generate an SN32 ML-KEM-512 keypair and retire the retained result",
    )
    keypair.add_argument(
        "--mode",
        choices=("deterministic", "random"),
        default="deterministic",
    )
    keypair.add_argument(
        "--seed",
        default=DEFAULT_KEYPAIR_SEED.hex(),
        help="32-byte hexadecimal seed for deterministic mode",
    )
    keypair.add_argument("--timeout", type=float, default=30.0)

    session = sub.add_parser(
        "session-create",
        help="derive, stage and commit one P1/P2 session",
    )
    session.add_argument(
        "--mode",
        choices=("kat", "deterministic"),
        default="kat",
    )
    session.add_argument(
        "--seed",
        default=DEFAULT_SESSION_SEED.hex(),
        help="32-byte hexadecimal seed for KAT mode",
    )
    session.add_argument("--timeout", type=float, default=30.0)

    telemetry = sub.add_parser(
        "telemetry-send",
        help="send one 24-byte plaintext through P1 UART to P2",
    )
    telemetry.add_argument("--plaintext-hex", required=True)
    telemetry.add_argument("--timeout", type=float, default=10.0)

    close = sub.add_parser("session-close", help="abort/close the active P1/P2 session")
    close.add_argument("--timeout", type=float, default=30.0)

    wipe = sub.add_parser("zeroize", help="zeroize SN32/P1/P2 state")
    wipe.add_argument(
        "--scope",
        choices=("all", "active", "staged", "telemetry", "transactions"),
        default="all",
    )
    wipe.add_argument("--timeout", type=float, default=30.0)

    qualify = sub.add_parser(
        "sn32-secure-telemetry-qualify",
        help=(
            "run dual-SPI qualification, deterministic ML-KEM/KDF session, "
            "two byte-exact telemetry packets and final full zeroize"
        ),
    )
    qualify.add_argument("--key-seed", default=DEFAULT_KEYPAIR_SEED.hex())
    qualify.add_argument("--session-seed", default=DEFAULT_SESSION_SEED.hex())
    qualify.add_argument(
        "--plaintext-hex",
        action="append",
        help="24-byte plaintext; repeat at least twice (defaults provide two vectors)",
    )
    qualify.add_argument("--timeout", type=float, default=30.0)
    qualify.add_argument("--poll", type=float, default=0.05)
    return parser


def _scope(name: str) -> ZeroizeScope:
    return {
        "all": ZeroizeScope.ALL,
        "active": ZeroizeScope.ACTIVE_SESSION,
        "staged": ZeroizeScope.STAGED_SESSION,
        "telemetry": ZeroizeScope.TELEMETRY_OR_AUTH_RESULT,
        "transactions": ZeroizeScope.TRANSACTION_STATE,
    }[name]


def _run_full_command(args: argparse.Namespace) -> int:
    with TrinitySerialClient(args.port, baudrate=args.baud) as client:
        if args.command == "keypair-generate":
            seed = parse_seed_hex(args.seed)
            result = generate_keypair(
                client,
                deterministic=args.mode == "deterministic",
                seed=seed,
                timeout=args.timeout,
            )
            _emit(
                {
                    "step": "MLKEM_KEYPAIR",
                    "result": "PASS",
                    "host_txid": f"0x{result.host_txid:04X}",
                    "public_key_hash": result.public_key_hash.hex(),
                },
                args.json,
            )
        elif args.command == "session-create":
            seed = parse_seed_hex(args.seed)
            result = create_session(
                client,
                kat=args.mode == "kat",
                seed=seed,
                timeout=args.timeout,
            )
            _emit(
                {
                    "step": "SESSION_ACTIVE",
                    "result": "PASS",
                    "host_txid": f"0x{result.host_txid:04X}",
                    "session_id": f"0x{result.session_id:08X}",
                    "initial_sequence": result.initial_sequence,
                },
                args.json,
            )
        elif args.command == "telemetry-send":
            result = send_telemetry(
                client,
                parse_plaintext_hex(args.plaintext_hex),
                timeout=args.timeout,
            )
            _emit(
                {
                    "step": "SECURE_TELEMETRY",
                    "result": "PASS",
                    "host_txid": f"0x{result.host_txid:04X}",
                    "session_id": f"0x{result.session_id:08X}",
                    "sequence": result.sequence,
                    "plaintext_hex": result.plaintext.hex(),
                    "auth_status": result.status.name,
                },
                args.json,
            )
        elif args.command == "session-close":
            txid = close_session(client, timeout=args.timeout)
            _emit(
                {
                    "step": "SESSION_CLOSE",
                    "result": "PASS",
                    "host_txid": f"0x{txid:04X}",
                },
                args.json,
            )
        elif args.command == "zeroize":
            txid = zeroize(
                client,
                scope=_scope(args.scope),
                timeout=args.timeout,
            )
            _emit(
                {
                    "step": "ZEROIZE",
                    "result": "PASS",
                    "scope": args.scope,
                    "host_txid": f"0x{txid:04X}",
                },
                args.json,
            )
        elif args.command == "sn32-secure-telemetry-qualify":
            plaintexts = (
                tuple(parse_plaintext_hex(item) for item in args.plaintext_hex)
                if args.plaintext_hex
                else DEFAULT_PLAINTEXTS
            )
            result = run_secure_telemetry_qualification(
                client,
                keypair_seed=parse_seed_hex(args.key_seed),
                session_seed=parse_seed_hex(args.session_seed),
                plaintexts=plaintexts,
                timeout=args.timeout,
                poll_interval=args.poll,
            )
            _emit(
                {
                    "step": "CONTROL_PLANE_REGRESSION",
                    "result": "PASS",
                    "sn32_build_id": f"0x{result.info.sn32_build_id:08X}",
                    "primer1_build_id": f"0x{result.info.primer1_build_id:08X}",
                    "primer2_build_id": f"0x{result.info.primer2_build_id:08X}",
                },
                args.json,
            )
            _emit(
                {
                    "step": "MLKEM_KEYPAIR",
                    "result": "PASS",
                    "public_key_hash": result.keypair.public_key_hash.hex(),
                },
                args.json,
            )
            _emit(
                {
                    "step": "SESSION_STAGE_COMMIT",
                    "result": "PASS",
                    "session_id": f"0x{result.session.session_id:08X}",
                    "initial_sequence": result.session.initial_sequence,
                    "system_state": result.status_active.system_state.name,
                },
                args.json,
            )
            for index, packet in enumerate(result.telemetry, start=1):
                _emit(
                    {
                        "step": f"SECURE_TELEMETRY_{index}",
                        "result": "PASS",
                        "session_id": f"0x{packet.session_id:08X}",
                        "sequence": packet.sequence,
                        "plaintext_hex": packet.plaintext.hex(),
                        "auth_status": packet.status.name,
                    },
                    args.json,
                )
            _emit(
                {
                    "step": "FINAL_ZEROIZE",
                    "result": "PASS",
                    "system_state": result.status_final.system_state.name,
                    "session_id": f"0x{result.status_final.session_id:08X}",
                    "current_sequence": result.status_final.current_sequence,
                },
                args.json,
            )
            _emit(
                {
                    "step": "SN32_P1_P2_SECURE_TELEMETRY_QUALIFICATION",
                    "result": "PASS",
                    "scope": "SN32+P1+P2; Tiny/full-system not claimed",
                },
                args.json,
            )
        else:  # pragma: no cover
            raise AssertionError(args.command)
    return 0


def main(argv: list[str] | None = None) -> int:
    actual = list(sys.argv[1:] if argv is None else argv)
    if not _contains_full_command(actual):
        return legacy_cli.main(actual)
    parser = _build_parser()
    args = parser.parse_args(actual)
    try:
        return _run_full_command(args)
    except (RemoteError, HostProtocolError, TimeoutError, OSError, ValueError) as exc:
        if args.json:
            print(
                json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True),
                file=sys.stderr,
            )
        else:
            print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
