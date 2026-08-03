from __future__ import annotations

from dataclasses import dataclass
import struct
import time
from typing import Callable, Protocol

from .protocol import (
    ErrorCode,
    EventEnvelope,
    FrameFlags,
    HostCommand,
    HostFrame,
    SystemState,
    SystemStatus,
    TargetReadyMask,
    TestMask,
    TestProfile,
    TransactionResult,
    TransactionState,
)

try:
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
except ImportError:  # pragma: no cover - exercised only on systems without pyserial
    serial = None
    list_ports = None

EXPECTED_P1_BUILD_ID = 0x50310001
EXPECTED_P2_BUILD_ID = 0x50320001
P1_KAT_TEST_MASK = 0x013E
P2_KAT_TEST_MASK = 0x03E3


class SerialPortLike(Protocol):
    def write(self, data: bytes) -> int: ...
    def read(self, size: int = 1) -> bytes: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...


class HostProtocolError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RemoteError(HostProtocolError):
    code: ErrorCode
    system_state: int
    source: int
    related_target_txid: int

    def __str__(self) -> str:
        return (
            f"remote error {self.code.name}(0x{int(self.code):04X}), "
            f"system_state={self.system_state}, source={self.source}, "
            f"related_target_txid=0x{self.related_target_txid:04X}"
        )


@dataclass(frozen=True, slots=True)
class SystemInfo:
    protocol_version: int
    architecture_major: int
    architecture_minor: int
    architecture_patch: int
    capabilities: int
    sn32_build_id: int
    primer1_build_id: int
    primer2_build_id: int

    @classmethod
    def decode(cls, payload: bytes) -> "SystemInfo":
        if len(payload) != 20:
            raise HostProtocolError(f"system info must be 20 bytes, got {len(payload)}")
        capabilities, sn32_build, p1_build, p2_build = struct.unpack_from(">IIII", payload, 4)
        return cls(
            payload[0], payload[1], payload[2], payload[3], capabilities,
            sn32_build, p1_build, p2_build,
        )


@dataclass(frozen=True, slots=True)
class BringupResult:
    uptime_ms: int
    info: SystemInfo
    status_before: SystemStatus
    transaction: TransactionResult
    status_after: SystemStatus


@dataclass(frozen=True, slots=True)
class DualSpiBringupResult:
    uptime_ms: int
    info: SystemInfo
    status_before: SystemStatus
    primer1_transaction: TransactionResult
    primer2_transaction: TransactionResult
    status_after: SystemStatus


class TrinitySerialClient:
    """Synchronous PC↔SN32 client with validated interleaved EVENT support."""

    def __init__(
        self,
        port: str,
        *,
        baudrate: int = 115200,
        read_timeout: float = 0.05,
        serial_factory: Callable[..., SerialPortLike] | None = None,
        event_handler: Callable[[EventEnvelope], None] | None = None,
    ) -> None:
        if serial_factory is None:
            if serial is None:
                raise RuntimeError("pyserial is required: python -m pip install -e pc_host")
            serial_factory = serial.Serial
        self._serial = serial_factory(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=read_timeout,
            write_timeout=1.0,
        )
        self._next_transaction_id = 1
        self._rx = bytearray()
        self._event_handler = event_handler

    def close(self) -> None:
        self._serial.close()

    def __enter__(self) -> "TrinitySerialClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _allocate_txid(self) -> int:
        txid = self._next_transaction_id
        self._next_transaction_id = (txid + 1) & 0xFFFF
        if self._next_transaction_id == 0:
            self._next_transaction_id = 1
        return txid

    def _read_wire_frame(self, deadline: float) -> HostFrame:
        while time.monotonic() < deadline:
            chunk = self._serial.read(1)
            if not chunk:
                continue
            value = chunk[0]
            self._rx.append(value)
            if value == 0:
                wire = bytes(self._rx)
                self._rx.clear()
                return HostFrame.decode_wire(wire)
            if len(self._rx) > 272:
                self._rx.clear()
                raise HostProtocolError("incoming PC frame exceeds maximum wire size")
        raise TimeoutError("timed out waiting for SN32 response")

    @staticmethod
    def _raise_remote_error(frame: HostFrame) -> None:
        if len(frame.payload) != 6:
            raise HostProtocolError("malformed SN32 error payload")
        code, system_state, source, related = struct.unpack(">HBBH", frame.payload)
        try:
            error_code = ErrorCode(code)
        except ValueError as exc:
            raise HostProtocolError(f"unknown remote error code 0x{code:04X}") from exc
        raise RemoteError(error_code, system_state, source, related)

    def _handle_event(self, frame: HostFrame) -> None:
        if frame.command != int(HostCommand.EVENT):
            raise HostProtocolError(
                f"EVENT flag used with command 0x{frame.command:02X}"
            )
        if frame.transaction_id != 0:
            raise HostProtocolError("EVENT frame transaction ID must be zero")
        if frame.flags != int(FrameFlags.EVENT):
            raise HostProtocolError("EVENT frame has invalid flags")
        try:
            event = EventEnvelope.decode(frame.payload)
        except (ValueError, struct.error) as exc:
            raise HostProtocolError(f"malformed EVENT frame: {exc}") from exc
        if self._event_handler is not None:
            self._event_handler(event)

    def request(
        self,
        command: HostCommand | int,
        payload: bytes = b"",
        *,
        timeout: float = 0.5,
    ) -> HostFrame:
        command_value = int(command)
        txid = self._allocate_txid()
        request = HostFrame(command_value, 0, txid, payload)
        encoded = request.encode_wire()
        written = self._serial.write(encoded)
        if written != len(encoded):
            raise HostProtocolError(f"short serial write: {written}/{len(encoded)}")
        self._serial.flush()

        deadline = time.monotonic() + timeout
        while True:
            frame = self._read_wire_frame(deadline)
            if frame.flags & int(FrameFlags.EVENT):
                self._handle_event(frame)
                continue
            if frame.command != command_value or frame.transaction_id != txid:
                raise HostProtocolError(
                    "response correlation failure: "
                    f"command=0x{frame.command:02X}, txid=0x{frame.transaction_id:04X}"
                )
            if (frame.flags & int(FrameFlags.RESPONSE)) == 0:
                raise HostProtocolError("SN32 frame is not marked as a response")
            if frame.flags & int(FrameFlags.MORE | FrameFlags.EVENT):
                raise HostProtocolError("unexpected MORE/EVENT flag in synchronous response")
            if frame.flags & int(FrameFlags.ERROR):
                self._raise_remote_error(frame)
            return frame

    def ping(self) -> int:
        response = self.request(HostCommand.PING)
        if len(response.payload) != 4:
            raise HostProtocolError("PING response must be 4 bytes")
        return struct.unpack(">I", response.payload)[0]

    def get_system_info(self) -> SystemInfo:
        return SystemInfo.decode(
            self.request(HostCommand.GET_SYSTEM_INFO, timeout=1.0).payload
        )

    def get_system_status(self) -> SystemStatus:
        return SystemStatus.decode(
            self.request(HostCommand.GET_SYSTEM_STATUS, timeout=1.0).payload
        )

    def start_self_test(
        self,
        target_mask: int,
        *,
        profile: TestProfile = TestProfile.KAT,
        test_mask: int,
    ) -> int:
        allowed = int(
            TargetReadyMask.SN32
            | TargetReadyMask.PRIMER1
            | TargetReadyMask.PRIMER2
            | TargetReadyMask.TINY1P5
        )
        if target_mask == 0 or target_mask & ~allowed:
            raise ValueError(f"invalid self-test target mask 0x{target_mask:02X}")
        payload = struct.pack(">BBH", target_mask, int(profile), test_mask & 0xFFFF)
        response = self.request(HostCommand.RUN_SELF_TEST, payload, timeout=10.0)
        if response.payload != struct.pack(">H", test_mask & 0xFFFF):
            raise HostProtocolError("RUN_SELF_TEST final response has the wrong test mask")
        return response.transaction_id

    def start_p1_self_test(
        self,
        *,
        profile: TestProfile = TestProfile.KAT,
        test_mask: int = int(
            TestMask.MEMORY
            | TestMask.NTT
            | TestMask.INTT
            | TestMask.BASEMUL
            | TestMask.ASCON
        ),
    ) -> int:
        return self.start_self_test(
            int(TargetReadyMask.PRIMER1),
            profile=profile,
            test_mask=test_mask,
        )

    def get_transaction_result(self, host_txid: int) -> TransactionResult:
        response = self.request(
            HostCommand.GET_TXN_RESULT,
            struct.pack(">H", host_txid),
            timeout=0.5,
        )
        return TransactionResult.decode(response.payload)

    def retire_transaction_result(self, host_txid: int) -> None:
        response = self.request(
            HostCommand.RETIRE_TXN_RESULT,
            struct.pack(">H", host_txid),
            timeout=0.5,
        )
        if response.payload:
            raise HostProtocolError("RETIRE_TXN_RESULT response must be empty")

    def wait_for_transaction(
        self,
        host_txid: int,
        *,
        expected_command: HostCommand | int,
        timeout: float,
        poll_interval: float,
    ) -> TransactionResult:
        deadline = time.monotonic() + timeout
        result: TransactionResult | None = None
        terminal = {
            TransactionState.SUCCEEDED,
            TransactionState.FAILED,
            TransactionState.ZEROIZED,
            TransactionState.OUTCOME_UNKNOWN,
        }
        while time.monotonic() < deadline:
            result = self.get_transaction_result(host_txid)
            if result.state in terminal:
                break
            time.sleep(poll_interval)
        if result is None or result.state not in terminal:
            raise TimeoutError(f"transaction 0x{host_txid:04X} did not finish")
        if result.queried_txid != host_txid:
            raise HostProtocolError("retained transaction ID mismatch")
        if result.original_command != int(expected_command):
            raise HostProtocolError("retained transaction command mismatch")
        if result.state != TransactionState.SUCCEEDED or result.result_code != ErrorCode.OK:
            raise HostProtocolError(
                f"transaction failed: state={result.state.name}, "
                f"code={result.result_code.name}"
            )
        return result

    def run_p1_bringup(
        self,
        *,
        timeout: float = 5.0,
        poll_interval: float = 0.1,
    ) -> BringupResult:
        uptime = self.ping()
        info = self.get_system_info()
        status_before = self.get_system_status()
        required_ready = int(TargetReadyMask.SN32 | TargetReadyMask.PRIMER1)
        if (status_before.target_ready_mask & required_ready) != required_ready:
            raise HostProtocolError(
                f"P1 is not ready on SPI: ready_mask=0x{status_before.target_ready_mask:02X}"
            )

        host_txid = self.start_p1_self_test()
        result = self.wait_for_transaction(
            host_txid,
            expected_command=HostCommand.RUN_SELF_TEST,
            timeout=timeout,
            poll_interval=poll_interval,
        )
        self.retire_transaction_result(host_txid)

        status_after = self.get_system_status()
        if status_after.system_state not in {
            SystemState.READY_NO_KEYPAIR,
            SystemState.READY_NO_SESSION,
        }:
            raise HostProtocolError(
                f"unexpected final P1 state: {status_after.system_state.name}"
            )
        if (status_after.target_ready_mask & required_ready) != required_ready:
            raise HostProtocolError(
                f"P1 lost readiness: ready_mask=0x{status_after.target_ready_mask:02X}"
            )
        if status_after.fault_flags != 0:
            raise HostProtocolError(
                f"fault flags asserted after self-test: 0x{status_after.fault_flags:02X}"
            )
        return BringupResult(uptime, info, status_before, result, status_after)

    def run_dual_spi_bringup(
        self,
        *,
        timeout: float = 10.0,
        poll_interval: float = 0.1,
    ) -> DualSpiBringupResult:
        uptime = self.ping()
        info = self.get_system_info()
        if info.primer1_build_id != EXPECTED_P1_BUILD_ID:
            raise HostProtocolError(
                f"unexpected P1 build ID 0x{info.primer1_build_id:08X}"
            )
        if info.primer2_build_id != EXPECTED_P2_BUILD_ID:
            raise HostProtocolError(
                f"unexpected P2 build ID 0x{info.primer2_build_id:08X}"
            )

        required_ready = int(
            TargetReadyMask.SN32 | TargetReadyMask.PRIMER1 | TargetReadyMask.PRIMER2
        )
        status_before = self.get_system_status()
        if (status_before.target_ready_mask & required_ready) != required_ready:
            raise HostProtocolError(
                "dual-SPI endpoints are not both ready: "
                f"ready_mask=0x{status_before.target_ready_mask:02X}"
            )
        if status_before.fault_flags != 0:
            raise HostProtocolError(
                f"fault flags before dual-SPI test: 0x{status_before.fault_flags:02X}"
            )

        p1_txid = self.start_self_test(
            int(TargetReadyMask.PRIMER1),
            profile=TestProfile.KAT,
            test_mask=P1_KAT_TEST_MASK,
        )
        p1_result = self.wait_for_transaction(
            p1_txid,
            expected_command=HostCommand.RUN_SELF_TEST,
            timeout=timeout,
            poll_interval=poll_interval,
        )
        self.retire_transaction_result(p1_txid)

        p2_txid = self.start_self_test(
            int(TargetReadyMask.PRIMER2),
            profile=TestProfile.KAT,
            test_mask=P2_KAT_TEST_MASK,
        )
        p2_result = self.wait_for_transaction(
            p2_txid,
            expected_command=HostCommand.RUN_SELF_TEST,
            timeout=timeout,
            poll_interval=poll_interval,
        )
        self.retire_transaction_result(p2_txid)

        status_after = self.get_system_status()
        if status_after.system_state not in {
            SystemState.READY_NO_KEYPAIR,
            SystemState.READY_NO_SESSION,
        }:
            raise HostProtocolError(
                f"unexpected final dual-SPI state: {status_after.system_state.name}"
            )
        if (status_after.target_ready_mask & required_ready) != required_ready:
            raise HostProtocolError(
                "endpoint readiness lost after dual-SPI test: "
                f"ready_mask=0x{status_after.target_ready_mask:02X}"
            )
        if status_after.fault_flags != 0:
            raise HostProtocolError(
                f"fault flags after dual-SPI test: 0x{status_after.fault_flags:02X}"
            )

        return DualSpiBringupResult(
            uptime,
            info,
            status_before,
            p1_result,
            p2_result,
            status_after,
        )


def available_ports() -> list[dict[str, str]]:
    if list_ports is None:
        raise RuntimeError("pyserial is required: python -m pip install -e pc_host")
    return [
        {
            "device": item.device,
            "description": item.description or "",
            "hwid": item.hwid or "",
        }
        for item in list_ports.comports()
    ]
