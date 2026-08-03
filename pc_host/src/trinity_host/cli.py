from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .protocol import ErrorCode, HostCommand, SystemStatus, TransactionState
from .serial_client import (
    HostProtocolError,
    RemoteError,
    SystemInfo,
    TrinitySerialClient,
    available_ports,
)


def _status_dict(status: SystemStatus) -> dict[str, object]:
    return {
        "system_state": status.system_state.name,
        "mode": status.mode.name,
        "target_ready_mask": f"0x{status.target_ready_mask:02X}",
        "fault_flags": f"0x{status.fault_flags:02X}",
        "session_id": f"0x{status.session_id:08X}",
        "current_sequence": status.current_sequence,
        "last_error": status.last_error.name,
        "active_host_txid": f"0x{status.active_host_txid:04X}",
    }


def _info_dict(info: SystemInfo) -> dict[str, object]:
    return {
        "protocol_version": info.protocol_version,
        "architecture_version": (
            f"{info.architecture_major}.{info.architecture_minor}."
            f"{info.architecture_patch}"
        ),
        "capabilities": f"0x{info.capabilities:08X}",
        "sn32_build_id": f"0x{info.sn32_build_id:08X}",
        "primer1_build_id": f"0x{info.primer1_build_id:08X}",
        "primer2_build_id": f"0x{info.primer2_build_id:08X}",
    }


def _transaction_dict(result) -> dict[str, object]:
    return {
        "queried_txid": f"0x{result.queried_txid:04X}",
        "state": result.state.name,
        "original_command": f"0x{result.original_command:02X}",
        "result_code": result.result_code.name,
        "result_data_hex": result.data.hex(),
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trinity-host",
        description="FPGA MCU Trinity PC↔SN32 hardware bring-up client",
    )
    parser.add_argument("--port", help="SN32 UART COM port, for example COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--json", action="store_true", help="emit one JSON object per step")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ports", help="list serial ports")
    sub.add_parser("ping", help="send standalone PC→SN32 PING")
    sub.add_parser("system-info", help="probe both Primer SPI endpoints and show build IDs")
    sub.add_parser("system-status", help="refresh both Primer SPI endpoints and show status")

    # Retained compatibility aliases for the earlier P1-only workflow.
    sub.add_parser("p1-info", help="compatibility alias for system-info")
    sub.add_parser("p1-status", help="compatibility alias for system-status")
    sub.add_parser("p1-self-test-start", help="start the P1 retained self-test")
    txn = sub.add_parser("txn-result", help="query a retained SN32 host transaction")
    txn.add_argument("txid", type=lambda text: int(text, 0))
    retire = sub.add_parser("txn-retire", help="retire a retained SN32 host transaction")
    retire.add_argument("txid", type=lambda text: int(text, 0))
    p1 = sub.add_parser("p1-bringup", help="run the retained P1 control-plane gate")
    p1.add_argument("--timeout", type=float, default=5.0)
    p1.add_argument("--poll", type=float, default=0.1)

    dual = sub.add_parser(
        "dual-spi-bringup",
        help="probe P1/P2 and run separate retained KAT self-tests over dual-SPI",
    )
    dual.add_argument("--timeout", type=float, default=10.0)
    dual.add_argument("--poll", type=float, default=0.1)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "ports":
        ports = available_ports()
        if args.json:
            for item in ports:
                print(json.dumps(item, sort_keys=True))
        else:
            if not ports:
                print("No serial ports found")
            for item in ports:
                print(f"{item['device']} | {item['description']} | {item['hwid']}")
        return 0

    if not args.port:
        parser.error("--port is required for this command")

    try:
        with TrinitySerialClient(args.port, baudrate=args.baud) as client:
            if args.command == "ping":
                uptime = client.ping()
                _emit({"step": "PING", "result": "PASS", "uptime_ms": uptime}, args.json)
            elif args.command in {"system-info", "p1-info"}:
                info = client.get_system_info()
                _emit({"step": "SYSTEM_INFO", "result": "PASS", **_info_dict(info)}, args.json)
            elif args.command in {"system-status", "p1-status"}:
                status = client.get_system_status()
                _emit({"step": "SYSTEM_STATUS", "result": "PASS", **_status_dict(status)}, args.json)
            elif args.command == "p1-self-test-start":
                txid = client.start_p1_self_test()
                _emit({
                    "step": "P1_RUN_SELF_TEST",
                    "result": "SUCCEEDED_RETAINED",
                    "host_txid": f"0x{txid:04X}",
                }, args.json)
            elif args.command == "txn-result":
                result = client.get_transaction_result(args.txid)
                _emit({"step": "GET_TXN_RESULT", **_transaction_dict(result)}, args.json)
            elif args.command == "txn-retire":
                client.retire_transaction_result(args.txid)
                _emit({
                    "step": "RETIRE_TXN_RESULT",
                    "result": "PASS",
                    "host_txid": f"0x{args.txid:04X}",
                }, args.json)
            elif args.command == "p1-bringup":
                result = client.run_p1_bringup(
                    timeout=args.timeout,
                    poll_interval=args.poll,
                )
                _emit({"step": "PING", "result": "PASS", "uptime_ms": result.uptime_ms}, args.json)
                _emit({"step": "SYSTEM_INFO", "result": "PASS", **_info_dict(result.info)}, args.json)
                _emit({"step": "SYSTEM_STATUS_BEFORE", "result": "PASS", **_status_dict(result.status_before)}, args.json)
                _emit({"step": "P1_SELF_TEST", "result": "PASS", **_transaction_dict(result.transaction)}, args.json)
                _emit({"step": "SYSTEM_STATUS_AFTER", "result": "PASS", **_status_dict(result.status_after)}, args.json)
                _emit({"step": "P1_CONTROL_PLANE_SELF_TEST", "result": "PASS"}, args.json)
            elif args.command == "dual-spi-bringup":
                result = client.run_dual_spi_bringup(
                    timeout=args.timeout,
                    poll_interval=args.poll,
                )
                _emit({"step": "PING", "result": "PASS", "uptime_ms": result.uptime_ms}, args.json)
                _emit({"step": "DUAL_SPI_GET_INFO", "result": "PASS", **_info_dict(result.info)}, args.json)
                _emit({"step": "DUAL_SPI_STATUS_BEFORE", "result": "PASS", **_status_dict(result.status_before)}, args.json)
                _emit({"step": "P1_KAT_SELF_TEST", "result": "PASS", **_transaction_dict(result.primer1_transaction)}, args.json)
                _emit({"step": "P2_KAT_SELF_TEST", "result": "PASS", **_transaction_dict(result.primer2_transaction)}, args.json)
                _emit({"step": "DUAL_SPI_STATUS_AFTER", "result": "PASS", **_status_dict(result.status_after)}, args.json)
                _emit({"step": "SN32_DUAL_SPI_CONTROL_PLANE", "result": "PASS"}, args.json)
            else:  # pragma: no cover
                parser.error(f"unsupported command {args.command}")
    except (RemoteError, HostProtocolError, TimeoutError, OSError, ValueError) as exc:
        if args.json:
            print(json.dumps({"result": "FAIL", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        else:
            print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
