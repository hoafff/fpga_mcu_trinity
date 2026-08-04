from __future__ import annotations

import argparse
import json
import struct
import sys

from .protocol import HostCommand, SpiCommand, SystemStatus, TargetId
from .serial_client import (
    HostProtocolError,
    RemoteError,
    SpiDiagnosticTrace,
    SystemInfo,
    TrinitySerialClient,
    available_ports,
)


_SPI_TRACE_CONTEXT_NAMES = {
    0: "NONE",
    1: "STARTUP_DRAIN_P1",
    2: "STARTUP_DRAIN_P2",
    3: "STARTUP_PROBE",
    4: "PERIODIC_PROBE",
    5: "HOST_DIAGNOSTIC",
}

_SPI_TRANSFER_STAGE_NAMES = {
    0: "NONE",
    1: "TX_FULL",
    2: "BUSY",
    3: "RX_EMPTY",
}

_SPI_TRANSFER_DIRECTION_NAMES = {
    0: "NONE",
    1: "REQUEST",
    2: "RESPONSE",
}


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


def _spi_trace_dict(trace: SpiDiagnosticTrace) -> dict[str, object]:
    return {
        "target_id": trace.target_id,
        "command": f"0x{trace.command:02X}",
        "error_source": trace.source,
        "transport_result": (
            f"{trace.result_code.name}(0x{int(trace.result_code):04X})"
        ),
        "target_txid": f"0x{trace.target_transaction_id:04X}",
        "request_fingerprint": f"0x{trace.request_fingerprint:08X}",
        "request_length": trace.request_length,
        "response_capture_length": trace.response_capture_length,
        "response_frame_length": trace.response_frame_length,
        "request_crc": f"0x{trace.request_crc:04X}",
        "response_crc_received": f"0x{trace.response_crc_received:04X}",
        "response_crc_calculated": f"0x{trace.response_crc_calculated:04X}",
        "response_crc_match": (
            trace.response_frame_length != 0
            and trace.response_crc_received == trace.response_crc_calculated
        ),
        "irq_before_request": int(trace.irq_before_request),
        "irq_after_request": int(trace.irq_after_request),
        "irq_before_response": int(trace.irq_before_response),
        "irq_after_response": int(trace.irq_after_response),
        "request_bytes": trace.request_bytes.hex(" "),
        "response_bytes": trace.response_bytes.hex(" "),
    }


def _hex_words(words: list[int]) -> str:
    return " ".join(f"0x{word:08X}" for word in words)


def _first_spi_failure_dict(payload: bytes) -> dict[str, object]:
    if len(payload) < 2:
        raise HostProtocolError(
            f"first SPI failure payload must be at least 2 bytes, got {len(payload)}"
        )
    latched_raw, context = payload[:2]
    if latched_raw not in {0, 1}:
        raise HostProtocolError(f"invalid first SPI failure latch value {latched_raw}")
    context_name = _SPI_TRACE_CONTEXT_NAMES.get(context, f"UNKNOWN_{context}")
    if len(payload) == 2:
        if latched_raw != 0 or context != 0:
            raise HostProtocolError(
                "first SPI failure metadata names a trace but no trace is present"
            )
        return {
            "latched": False,
            "startup_residue": False,
            "context": context_name,
        }

    if len(payload) < 2 + 24 + 12:
        raise HostProtocolError(
            "first SPI failure trace is missing byte-level transfer telemetry"
        )
    trace_payload = payload[2:]
    request_length = struct.unpack_from(">H", trace_payload, 12)[0]
    response_capture_length = struct.unpack_from(">H", trace_payload, 14)[0]
    trace_length = 24 + request_length + response_capture_length
    extension = payload[2 + trace_length:]
    if len(extension) < 12:
        raise HostProtocolError("first SPI failure transfer extension is truncated")

    trace = SpiDiagnosticTrace.decode(payload[2:2 + trace_length])
    transfer_stage_raw, transfer_direction_raw = extension[:2]
    (
        transfer_byte_index,
        transfer_length,
        transfer_completed,
        spi_status,
    ) = struct.unpack_from(">HHHI", extension, 2)
    transfer: dict[str, object] = {
        "transfer_stage": _SPI_TRANSFER_STAGE_NAMES.get(
            transfer_stage_raw, f"UNKNOWN_{transfer_stage_raw}"
        ),
        "transfer_direction": _SPI_TRANSFER_DIRECTION_NAMES.get(
            transfer_direction_raw, f"UNKNOWN_{transfer_direction_raw}"
        ),
        "transfer_byte_index": transfer_byte_index,
        "transfer_length": transfer_length,
        "transfer_completed": transfer_completed,
        "spi_status": f"0x{spi_status:08X}",
    }

    if len(extension) == 12:
        pass
    elif len(extension) >= 32:
        spi_ctrl0, spi_ctrl1, spi_clkdiv, spi_fifo_th = struct.unpack_from(
            ">IIII", extension, 12
        )
        sample_count = extension[28]
        expected_extension_length = 32 + sample_count * 12
        if len(extension) != expected_extension_length:
            raise HostProtocolError(
                "first SPI failure register telemetry length "
                f"{len(extension)} != {expected_extension_length}"
            )
        status_before: list[int] = []
        data_words: list[int] = []
        status_after: list[int] = []
        offset = 32
        for _ in range(sample_count):
            before, data_word, after = struct.unpack_from(">III", extension, offset)
            status_before.append(before)
            data_words.append(data_word)
            status_after.append(after)
            offset += 12
        transfer.update({
            "spi_ctrl0": f"0x{spi_ctrl0:08X}",
            "spi_ctrl1": f"0x{spi_ctrl1:08X}",
            "spi_clkdiv": f"0x{spi_clkdiv:08X}",
            "spi_fifo_th": f"0x{spi_fifo_th:08X}",
            "response_sample_count": sample_count,
            "response_status_before_read": _hex_words(status_before),
            "response_data_words": _hex_words(data_words),
            "response_status_after_read": _hex_words(status_after),
        })
    else:
        raise HostProtocolError(
            f"unsupported first SPI failure extension length {len(extension)}"
        )

    if latched_raw == 0:
        if context not in {1, 2}:
            raise HostProtocolError(
                "unlatched SPI trace must be a startup-drain reset residue"
            )
        return {
            "latched": False,
            "startup_residue": True,
            "context": context_name,
            **_spi_trace_dict(trace),
            **transfer,
        }
    return {
        "latched": True,
        "startup_residue": False,
        "context": context_name,
        **_spi_trace_dict(trace),
        **transfer,
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

    spi_diag = sub.add_parser(
        "spi-diag",
        help="capture one side-effect-free raw Primer GET_INFO/GET_STATUS exchange",
    )
    spi_diag.add_argument("--target", choices=("p1", "p2"), required=True)
    spi_diag.add_argument(
        "--command",
        dest="spi_command",
        choices=("get-info", "get-status"),
        required=True,
    )
    sub.add_parser(
        "spi-first-failure",
        help=(
            "read the immutable first active SPI failure, or the exact startup "
            "reset residue when no active failure occurred"
        ),
    )

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
            elif args.command == "spi-diag":
                target = TargetId.PRIMER1 if args.target == "p1" else TargetId.PRIMER2
                command = (
                    SpiCommand.GET_INFO
                    if args.spi_command == "get-info"
                    else SpiCommand.GET_STATUS
                )
                trace = client.spi_diagnostic(target, command)
                _emit(
                    {"step": "SPI_DIAGNOSTIC", **_spi_trace_dict(trace)},
                    args.json,
                )
            elif args.command == "spi-first-failure":
                response = client.request(HostCommand.GET_FIRST_SPI_FAILURE)
                _emit(
                    {
                        "step": "SPI_FIRST_FAILURE",
                        **_first_spi_failure_dict(response.payload),
                    },
                    args.json,
                )
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
