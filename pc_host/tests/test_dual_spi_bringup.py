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
    SpiPacket,
    SpiCommand,
    TargetId,
    TargetReadyMask,
    TransactionState,
    request_fingerprint_crc32c,
)
from trinity_host.serial_client import (
    EXPECTED_P1_BUILD_ID,
    EXPECTED_P2_BUILD_ID,
    EXPECTED_SN32_BUILD_ID,
    EXPECTED_SN32_VERSION,
    HostProtocolError,
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
        self.p1_build_id = EXPECTED_P1_BUILD_ID
        self.spi_result = ErrorCode.OK
        self.corrupt_spi_request = False
        self.corrupt_spi_response = False
        self.active_host_txid_after_self_tests = 0
        self.ping_uptimes = [123456]

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
            uptime = (
                self.ping_uptimes.pop(0)
                if len(self.ping_uptimes) > 1
                else self.ping_uptimes[0]
            )
            payload = struct.pack(">I", uptime)
        elif command == HostCommand.GET_SYSTEM_INFO:
            payload = bytes((1, *EXPECTED_SN32_VERSION)) + struct.pack(
                ">IIII",
                0x00000EFB,
                EXPECTED_SN32_BUILD_ID,
                self.p1_build_id,
                EXPECTED_P2_BUILD_ID,
            )
        elif command == HostCommand.SPI_DIAGNOSTIC:
            target, spi_command = request.payload
            if target not in {int(TargetId.PRIMER1), int(TargetId.PRIMER2)}:
                raise AssertionError(f"bad target {target}")
            if spi_command not in {
                int(SpiCommand.GET_INFO), int(SpiCommand.GET_STATUS)
            }:
                raise AssertionError(f"bad SPI command {spi_command}")
            target_txid = 0x1234
            request_bytes = SpiPacket(
                command=spi_command,
                flags=0,
                transaction_id=target_txid,
            ).encode()
            if self.corrupt_spi_request:
                corrupt = bytearray(request_bytes)
                corrupt[0] = 0x04
                request_bytes = bytes(corrupt)
            if spi_command == int(SpiCommand.GET_INFO):
                build_id = (
                    EXPECTED_P1_BUILD_ID
                    if target == int(TargetId.PRIMER1)
                    else EXPECTED_P2_BUILD_ID
                )
                response_payload = bytes((target, 1)) + struct.pack(
                    ">IIH", 0x00000EFB, build_id, 0
                )
            else:
                response_payload = bytes(16)
            response_bytes = SpiPacket(
                command=spi_command,
                flags=int(FrameFlags.RESPONSE),
                transaction_id=target_txid,
                payload=response_payload,
            ).encode()
            if self.corrupt_spi_response:
                corrupt = bytearray(response_bytes)
                corrupt[8] ^= 0x01
                response_bytes = bytes(corrupt)
            request_crc = int.from_bytes(request_bytes[-2:], "big")
            response_crc = int.from_bytes(response_bytes[-2:], "big")
            payload = struct.pack(
                ">BBBBHHIHHHHHH",
                target,
                spi_command,
                target,
                0x06,
                int(self.spi_result),
                target_txid,
                request_fingerprint_crc32c(spi_command, 0, b""),
                len(request_bytes),
                len(response_bytes),
                len(response_bytes),
                request_crc,
                response_crc,
                response_crc,
            ) + request_bytes + response_bytes
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
                (
                    self.active_host_txid_after_self_tests
                    if self.self_tests_completed == 2
                    else 0
                ),
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


class SilentFakeSerial:
    def write(self, data: bytes) -> int:
        return len(data)

    def read(self, size: int = 1) -> bytes:
        return b""

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class DualSpiBringupTests(unittest.TestCase):
    def test_timeout_identifies_exact_host_command_and_transaction(self) -> None:
        client = TrinitySerialClient(
            "COM_TEST",
            serial_factory=lambda **kwargs: SilentFakeSerial(),
        )

        with self.assertRaisesRegex(
            TimeoutError,
            r"command=GET_SYSTEM_STATUS\(0x03\), txid=0x0001",
        ):
            client.request(HostCommand.GET_SYSTEM_STATUS, timeout=0.0)
        client.close()

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
        self.assertEqual(result.info.architecture_patch, 25)
        self.assertEqual(result.info.sn32_build_id, EXPECTED_SN32_BUILD_ID)
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

    def test_one_shot_qualification_covers_live_spi_self_tests_and_liveness(self) -> None:
        fake = DualSpiFakeSerial()
        client = TrinitySerialClient(
            "COM_TEST",
            serial_factory=lambda **kwargs: fake,
        )

        result = client.run_sn32_hardware_qualification(
            timeout=0.5,
            poll_interval=0.0,
            liveness_iterations=3,
        )

        self.assertEqual(len(result.live_traces), 4)
        self.assertTrue(all(
            trace.result_code == ErrorCode.OK for trace in result.live_traces
        ))
        self.assertEqual(result.liveness_iterations, 3)
        self.assertEqual(result.final_uptime_ms, 123456)
        self.assertEqual(result.final_status.fault_flags, 0)
        self.assertEqual(
            fake.commands.count(int(HostCommand.SPI_DIAGNOSTIC)),
            4,
        )
        client.close()

    def test_one_shot_rejects_wrong_image_before_live_spi(self) -> None:
        fake = DualSpiFakeSerial()
        fake.p1_build_id = 0x50310001
        client = TrinitySerialClient(
            "COM_TEST",
            serial_factory=lambda **kwargs: fake,
        )

        with self.assertRaisesRegex(HostProtocolError, "wrong Primer image"):
            client.run_sn32_hardware_qualification()

        self.assertNotIn(int(HostCommand.SPI_DIAGNOSTIC), fake.commands)
        self.assertEqual(fake.self_tests_completed, 0)
        client.close()

    def test_one_shot_stops_before_self_test_on_live_spi_error(self) -> None:
        fake = DualSpiFakeSerial()
        fake.spi_result = ErrorCode.BAD_LENGTH
        client = TrinitySerialClient(
            "COM_TEST",
            serial_factory=lambda **kwargs: fake,
        )

        with self.assertRaisesRegex(HostProtocolError, "PRIMER1 GET_INFO failed"):
            client.run_sn32_hardware_qualification()

        self.assertEqual(fake.self_tests_completed, 0)
        client.close()

    def test_one_shot_independently_rejects_corrupt_raw_spi_response(self) -> None:
        fake = DualSpiFakeSerial()
        fake.corrupt_spi_response = True
        client = TrinitySerialClient(
            "COM_TEST",
            serial_factory=lambda **kwargs: fake,
        )

        with self.assertRaisesRegex(
            HostProtocolError,
            r"raw SPI response invalid:.*request_bytes=.*response_bytes=",
        ):
            client.run_sn32_hardware_qualification()

        self.assertEqual(fake.self_tests_completed, 0)
        client.close()

    def test_one_shot_identifies_corrupt_raw_spi_request_and_prints_evidence(self) -> None:
        fake = DualSpiFakeSerial()
        fake.corrupt_spi_request = True
        client = TrinitySerialClient(
            "COM_TEST",
            serial_factory=lambda **kwargs: fake,
        )

        with self.assertRaisesRegex(
            HostProtocolError,
            r"raw SPI request invalid: magic 0x04;.*request_bytes=04",
        ):
            client.run_sn32_hardware_qualification()

        self.assertEqual(fake.self_tests_completed, 0)
        client.close()

    def test_one_shot_detects_reset_in_post_test_liveness(self) -> None:
        fake = DualSpiFakeSerial()
        fake.ping_uptimes = [1000, 100]
        client = TrinitySerialClient(
            "COM_TEST",
            serial_factory=lambda **kwargs: fake,
        )

        with self.assertRaisesRegex(
            HostProtocolError, "SN32 reset during liveness loop"
        ):
            client.run_sn32_hardware_qualification(
                timeout=0.5,
                poll_interval=0.0,
                liveness_iterations=1,
            )

        self.assertEqual(fake.self_tests_completed, 2)
        client.close()

    def test_one_shot_rejects_unretired_host_transaction(self) -> None:
        fake = DualSpiFakeSerial()
        fake.active_host_txid_after_self_tests = 0xCAFE
        client = TrinitySerialClient(
            "COM_TEST",
            serial_factory=lambda **kwargs: fake,
        )

        with self.assertRaisesRegex(
            HostProtocolError, "host transaction remained active"
        ):
            client.run_sn32_hardware_qualification(
                timeout=0.5,
                poll_interval=0.0,
                liveness_iterations=1,
            )

        self.assertEqual(fake.self_tests_completed, 2)
        client.close()


if __name__ == "__main__":
    unittest.main()
