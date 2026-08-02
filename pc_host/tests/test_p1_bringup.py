from __future__ import annotations

import struct
import unittest

from trinity_host.protocol import (
    ErrorCode,
    FrameFlags,
    HostCommand,
    HostFrame,
    Mode,
    SystemState,
    TargetReadyMask,
    TransactionState,
)
from trinity_host.serial_client import TrinitySerialClient


class FakeSerial:
    def __init__(self, **_kwargs):
        self.rx = bytearray()
        self.commands: list[int] = []
        self.self_test_host_txid: int | None = None
        self.result_queries = 0
        self.closed = False

    def _queue(self, frame: HostFrame) -> None:
        self.rx.extend(frame.encode_wire())

    def write(self, data: bytes) -> int:
        request = HostFrame.decode_wire(data)
        self.commands.append(request.command)
        command = HostCommand(request.command)
        payload = b""

        if command == HostCommand.PING:
            payload = struct.pack(">I", 1234)
        elif command == HostCommand.GET_SYSTEM_INFO:
            payload = bytes([1, 0, 5, 0]) + struct.pack(">IIII", 0x830, 0x00050100, 0x50310001, 0)
        elif command == HostCommand.GET_SYSTEM_STATUS:
            payload = struct.pack(
                ">BBBBIQHH",
                int(SystemState.SELF_TEST_REQUIRED if self.result_queries == 0 else SystemState.READY_NO_SESSION),
                int(Mode.KAT),
                int(TargetReadyMask.SN32 | TargetReadyMask.PRIMER1),
                0,
                0,
                0,
                int(ErrorCode.OK),
                0,
            )
        elif command == HostCommand.RUN_SELF_TEST:
            self.assert_payload(request.payload, b"\x02\x02\x00\x3E")
            self.self_test_host_txid = request.transaction_id
        elif command == HostCommand.GET_TXN_RESULT:
            assert self.self_test_host_txid is not None
            self.assert_payload(request.payload, struct.pack(">H", self.self_test_host_txid))
            self.result_queries += 1
            state = TransactionState.RUNNING if self.result_queries == 1 else TransactionState.SUCCEEDED
            data_field = b"" if state == TransactionState.RUNNING else b"\x01\x3E"
            payload = struct.pack(
                ">HBBHH",
                self.self_test_host_txid,
                int(state),
                int(HostCommand.RUN_SELF_TEST),
                int(ErrorCode.OK),
                len(data_field),
            ) + data_field
        elif command == HostCommand.RETIRE_TXN_RESULT:
            assert self.self_test_host_txid is not None
            self.assert_payload(request.payload, struct.pack(">H", self.self_test_host_txid))
        else:  # pragma: no cover
            raise AssertionError(command)

        self._queue(HostFrame(request.command, int(FrameFlags.RESPONSE), request.transaction_id, payload))
        return len(data)

    @staticmethod
    def assert_payload(actual: bytes, expected: bytes) -> None:
        if actual != expected:
            raise AssertionError(f"payload {actual.hex()} != {expected.hex()}")

    def read(self, size: int = 1) -> bytes:
        if not self.rx:
            return b""
        out = bytes(self.rx[:size])
        del self.rx[:size]
        return out

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class P1BringupClientTests(unittest.TestCase):
    def test_exact_control_plane_sequence(self) -> None:
        fake = FakeSerial()
        client = TrinitySerialClient("COM_TEST", serial_factory=lambda **kwargs: fake)
        result = client.run_p1_bringup(timeout=0.5, poll_interval=0.0)
        self.assertEqual(result.uptime_ms, 1234)
        self.assertEqual(result.info.primer1_build_id, 0x50310001)
        self.assertEqual(result.transaction.state, TransactionState.SUCCEEDED)
        self.assertEqual(result.transaction.data, b"\x01\x3E")
        self.assertEqual(
            fake.commands,
            [
                int(HostCommand.PING),
                int(HostCommand.GET_SYSTEM_INFO),
                int(HostCommand.GET_SYSTEM_STATUS),
                int(HostCommand.RUN_SELF_TEST),
                int(HostCommand.GET_TXN_RESULT),
                int(HostCommand.GET_TXN_RESULT),
                int(HostCommand.RETIRE_TXN_RESULT),
                int(HostCommand.GET_SYSTEM_STATUS),
            ],
        )
        client.close()
        self.assertTrue(fake.closed)


if __name__ == "__main__":
    unittest.main()
