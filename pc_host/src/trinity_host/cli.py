from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .protocol import (
    ErrorCode, HostCommand, SystemState, SystemStatus, TargetReadyMask,
    TransactionState,
)
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
        "architecture_version": f"{info.architecture_major}.{info.architecture_minor}",
        "capabilities": f"0x{info.capabilities:08X}",
        "sn32_build_id": f"0x{info.sn32_build_id:08X}",
        "primer1_build_id": f"0x{info.primer1_build_id:08X}",
        "primer2_build_id": f"0x{info.primer2_build_id:08X}",
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
        description="FPGA MCU Trinity PC↔SN32 bring-up client",
    )
    parser.add_argument("--port", help="SN32 UART COM port, for example COM7")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--json", action="store_true", help="emit one JSON object per step")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ports", help="list serial ports")
    sub.add_parser("ping", help="send PC→SN32 PING")
    sub.add_parser("p1-info", help="force SN32→P1 GET_INFO and display cached system info")
    sub.add_parser("p1-status", help="force SN32→P1 GET_STATUS and display system status")
    sub.add_parser("p1-self-test-start", help="send P1 RUN_SELF_TEST and print retained host txid")
    txn = sub.add_parser("txn-result", help="query P1 retained transaction through SN32")
    txn.add_argument("txid", type=lambda text: int(text, 0))
    retire = sub.add_parser("txn-retire", help="retire P1 retained transaction through SN32")
    retire.add_argument("txid", type=lambda text: int(text, 0))
    bringup = sub.add_parser("p1-bringup", help="run PING→GET_INFO→GET_STATUS→SELF_TEST→GET/RETIRE")
    bringup.add_argument("--timeout", type=float, default=5.0)
    bringup.add_argument("--poll", type=float, default=0.1)
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
            elif args.command == "p1-info":
                info = client.get_system_info()
                _emit({"step": "P1_GET_INFO", "result": "PASS", **_info_dict(info)}, args.json)
            elif args.command == "p1-status":
                status = client.get_system_status()
                _emit({"step": "P1_GET_STATUS", "result": "PASS", **_status_dict(status)}, args.json)
            elif args.command == "p1-self-test-start":
                txid = client.start_p1_self_test()
                _emit({"step": "P1_RUN_SELF_TEST", "result": "ACCEPTED", "host_txid": f"0x{txid:04X}"}, args.json)
            elif args.command == "txn-result":
                result = client.get_transaction_result(args.txid)
                _emit({
                    "step": "P1_GET_TXN_RESULT",
                    "queried_txid": f"0x{result.queried_txid:04X}",
                    "state": result.state.name,
                    "original_command": f"0x{result.original_command:02X}",
                    "result_code": result.result_code.name,
                    "result_data_hex": result.data.hex(),
                }, args.json)
            elif args.command == "txn-retire":
                client.retire_transaction_result(args.txid)
                _emit({"step": "P1_RETIRE_TXN_RESULT", "result": "PASS", "host_txid": f"0x{args.txid:04X}"}, args.json)
            elif args.command == "p1-bringup":
                uptime = client.ping()
                _emit({"step": "PING", "result": "PASS", "uptime_ms": uptime}, args.json)
                info = client.get_system_info()
                if info.primer1_build_id == 0:
                    raise HostProtocolError("P1 GET_INFO returned build_id=0")
                _emit({"step": "P1_GET_INFO", "result": "PASS", **_info_dict(info)}, args.json)
                status = client.get_system_status()
                required_ready = int(TargetReadyMask.SN32 | TargetReadyMask.PRIMER1)
                if (status.target_ready_mask & required_ready) != required_ready:
                    raise HostProtocolError(
                        f"P1 is not ready: ready_mask=0x{status.target_ready_mask:02X}"
                    )
                if status.fault_flags != 0:
                    raise HostProtocolError(
                        f"fault flags before self-test: 0x{status.fault_flags:02X}"
                    )
                _emit({"step": "P1_GET_STATUS", "result": "PASS", **_status_dict(status)}, args.json)
                txid = client.start_p1_self_test()
                _emit({"step": "P1_RUN_SELF_TEST", "result": "ACCEPTED", "host_txid": f"0x{txid:04X}"}, args.json)

                import time
                deadline = time.monotonic() + args.timeout
                result = None
                while time.monotonic() < deadline:
                    result = client.get_transaction_result(txid)
                    _emit({
                        "step": "P1_GET_TXN_RESULT",
                        "queried_txid": f"0x{result.queried_txid:04X}",
                        "state": result.state.name,
                        "result_code": result.result_code.name,
                        "result_data_hex": result.data.hex(),
                    }, args.json)
                    if result.state in {
                        TransactionState.SUCCEEDED,
                        TransactionState.FAILED,
                        TransactionState.ZEROIZED,
                        TransactionState.OUTCOME_UNKNOWN,
                    }:
                        break
                    time.sleep(args.poll)
                if result is None or result.state != TransactionState.SUCCEEDED or result.result_code != ErrorCode.OK:
                    raise HostProtocolError("P1 self-test did not complete successfully")
                if result.queried_txid != txid or result.original_command != int(HostCommand.RUN_SELF_TEST):
                    raise HostProtocolError("P1 retained-result correlation mismatch")
                client.retire_transaction_result(txid)
                _emit({"step": "P1_RETIRE_TXN_RESULT", "result": "PASS", "host_txid": f"0x{txid:04X}"}, args.json)
                final_status = client.get_system_status()
                if final_status.system_state != SystemState.READY_NO_SESSION:
                    raise HostProtocolError(
                        f"unexpected final state: {final_status.system_state.name}"
                    )
                if final_status.fault_flags != 0:
                    raise HostProtocolError(
                        f"fault flags after self-test: 0x{final_status.fault_flags:02X}"
                    )
                _emit({"step": "P1_GET_STATUS_FINAL", "result": "PASS", **_status_dict(final_status)}, args.json)
                _emit({"step": "P1_CONTROL_PLANE_SELF_TEST", "result": "PASS"}, args.json)
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
