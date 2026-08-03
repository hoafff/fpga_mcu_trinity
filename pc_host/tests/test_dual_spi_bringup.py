from __future__ import annotations

import struct
import unittest

from trinity_host.protocol import (
    ErrorCode,
    EventType,
    FrameFlags,
    HostCommand,
    HostFrame,
    Mode,
    Source,
    SystemState,
    TargetReadyMask,
    TransactionState,
)
from trinity_host.serial_client import (
    EXPECTED_P1_BUILD_ID,
    EXPECTED_P2_BUILD_ID,
    P1_KAT_TEST_MASK,
    P2_KAT_TEST_MASK,
    TrinitySerialClient,
)


class DualSpiFakeSerial:
    def __init__(self, **_kwargs):
        self.rx = bytearray()
        self.commands: list[int] = []
        self.retained_txid: int | None = None
        self.retained_mask = 0
        self.self_tests_completed = 0
        self.closed = False

    def _queue(self, frame: HostFrame) -> None:
        self.rx.extend(frame.encode_wire())

    def _queue_progress(self, related_txid: int) -> None:
        payload = struct.pack(
            ">HBBHBB",
            int(EventType.PROGRESS),
            0,
            int(Source.SN32),
            related_txid,
            100,
            0,
        )
        self._queue(
            HostFrame(
                int(HostCommand.EVENT),
                int(FrameFlags.EVENT),
                0,
                payload,
            )
        )

    def write(self, data: bytes) -> int:
        request = HostFrame.decode_wire(data)
        self.commands.append(request.command)
        command = HostCommand(request.command)
        payload = b""

        if command == HostCommand.PING:
            payload = struct.pack(">I", 123456)
        elif command == HostCommand.GET_SYSTEM_INFO:
            payload = bytes([1, 0, 7, 1]) + struct.pack(
                ">IIII",
                0x00000EFB,
                0x00070001,
                EXPECTED_P1_BUILD_ID,
                EXPECTED_P2_BUILD_ID,
            )
        elif command == HostCommand.GET_SYSTEM_STATUS:
            state = (
                SystemState.READY_NO_KEYPAIR
                if self.self_tests_completed == 2
                else SystemState.SELF_TEST_REQUIRED
            )
            payload = struct.pack(
                ">BBBBIQHH",
                int(state),
                int(Mode.KAT),
                int(
                    TargetReadyMask.SN32
                    | TargetReadyMask.PRIMER1
                    | TargetReadyMask.PRIMER2
                ),
                0,
                0,
                0,
                int(ErrorCode.OK),
                0,
            )
        elif command == HostCommand.RUN_SELF_TEST:
            target, profile, mask = struct.unpack(">BBH", request.payload)
            if self.self_tests_completed == 0:
                self.assertEqual(target, int(TargetReadyMask.PRIMER1))
                self.assertEqual(mask, P1_KAT_TEST_MASK)
            else:
                self.assertEqual(target, int(TargetReadyMask.PRIMER2))
                self.assertEqual(mask, P2_KAT_TEST_MASK)
            self.assertEqual(profile, 2)
            self.retained_txid = request.transaction_id
            self.retained_mask = mask
            self.self_tests_completed += 1
            self._queue_progress(request.transaction_id)
            payload = struct.pack(">H", mask)
        elif command == HostCommand.GET_TXN_RESULT:
            if self.retained_txid is None:
                raise AssertionError("GET_TXN_RESULT without retained transaction")
            self.assertEqual(request.payload, struct.pack(">H", self.retained_txid))
            data_field = struct.pack(">H", self.retained_mask)
            payload = struct.pack(
                ">HBBHH",
                self.retained_txid,
                int(TransactionState.SUCCEEDED),
                int(HostCommand.RUN_SELF_TEST),
                int(ErrorCode.OK),
                len(data_field),
            ) + data_field
        elif command == HostCommand.RETIRE_TXN_RESULT:
            if self.retained_txid is None:
                raise AssertionError("RETIRE_TXN_RESULT without retained transaction")
            self.assertEqual(request.payload, struct.pack(">H", self.retained_txid))
            self.retained_txid = None
            self.retained_mask = 0
        else:  # pragma: no cover
            raise AssertionError(command)

        self._queue(
            HostFrame(
                request.command,
                int(FrameFlags.RESPONSE),
                request.transaction_id,
                payload,
            )
        )
        return len(data)

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

    def assertEqual(self, actual, expected) -> None:
        if actual != expected:
            raise AssertionError(f"{actual!r} != {expected!r}")


class DualSpiBringupTests(unittest.TestCase):
    def test_probe_and_separate_p1_p2_retained_self_tests(self) -> None:
        fake = DualSpiFakeSerial()
        events = []
        client = TrinitySerialClient(
            "COM_TEST",
            serial_factory=lambda **kwargs: fake,
            event_handler=events.append,
        )

        result = client.run_dual_spi_bringup(timeout=0.5, poll_interval=0.0)

        self.assertEqual(result.uptime_ms, 123456)
        self.assertEqual(result.info.architecture_patch, 1)
        self.assertEqual(result.info.sn32_build_id, 0x00070001)
        self.assertEqual(result.info.primer1_build_id, EXPECTED_P1_BUILD_ID)
        self.assertEqual(result.info.primer2_build_id, EXPECTED_P2_BUILD_ID)
        self.assertEqual(result.primer1_transaction.data, struct.pack(">H", P1_KAT_TEST_MASK))
        self.assertEqual(result.primer2_transaction.data, struct.pack(">H", P2_KAT_TEST_MASK))
        self.assertEqual(result.status_after.system_state, SystemState.READY_NO_KEYPAIR)
        self.assertEqual(result.status_after.fault_flags, 0)
        self.assertEqual(len(events), 2)
        self.assertTrue(all(event.event_type == EventType.PROGRESS for event in events))
        self.assertEqual(
            fake.commands,
            [
                int(HostCommand.PING),
                int(HostCommand.GET_SYSTEM_INFO),
                int(HostCommand.GET_SYSTEM_STATUS),
                int(HostCommand.RUN_SELF_TEST),
                int(HostCommand.GET_TXN_RESULT),
                int(HostCommand.RETIRE_TXN_RESULT),
                int(HostCommand.RUN_SELF_TEST),
                int(HostCommand.GET_TXN_RESULT),
                int(HostCommand.RETIRE_TXN_RESULT),
                int(HostCommand.GET_SYSTEM_STATUS),
            ],
        )
        client.close()
        self.assertTrue(fake.closed)


if __name__ == "__main__":
    unittest.main()
