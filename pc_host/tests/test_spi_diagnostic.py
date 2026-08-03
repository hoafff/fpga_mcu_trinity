from __future__ import annotations

import struct
import unittest

from trinity_host.protocol import (
    ErrorCode,
    FrameFlags,
    HostCommand,
    HostFrame,
    SpiCommand,
    TargetId,
)
from trinity_host.serial_client import TrinitySerialClient


class FakeDiagnosticSerial:
    def __init__(self, **_kwargs):
        self.rx = bytearray()
        self.closed = False
        self.request = b""
        self.request_bytes = bytes.fromhex(
            "A5 01 01 00 12 34 00 00 11 11"
        )
        self.response_bytes = bytes.fromhex(
            "A5 01 01 01 12 34 00 0C "
            "02 01 00 00 1E 0F 50 32 00 01 00 00 22 22"
        ) + bytes(76 - 22)

    def write(self, data: bytes) -> int:
        request = HostFrame.decode_wire(data)
        self.request = request.payload
        if request.command != int(HostCommand.SPI_DIAGNOSTIC):
            raise AssertionError(f"unexpected command 0x{request.command:02X}")
        if request.payload != bytes((int(TargetId.PRIMER2), int(SpiCommand.GET_INFO))):
            raise AssertionError(f"unexpected diagnostic payload {request.payload.hex()}")

        payload = bytes((
            int(TargetId.PRIMER2),
            int(SpiCommand.GET_INFO),
            2,
            0x0E,
        )) + struct.pack(
            ">HHIHHHHHH",
            int(ErrorCode.OK),
            0x1234,
            0x89ABCDEF,
            len(self.request_bytes),
            len(self.response_bytes),
            22,
            0x1111,
            0x2222,
            0x2222,
        ) + self.request_bytes + self.response_bytes

        response = HostFrame(
            request.command,
            int(FrameFlags.RESPONSE),
            request.transaction_id,
            payload,
        )
        self.rx.extend(response.encode_wire())
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


class SpiDiagnosticTests(unittest.TestCase):
    def test_p2_get_info_trace_is_byte_exact(self) -> None:
        fake = FakeDiagnosticSerial()
        with TrinitySerialClient(
            "COM_TEST", serial_factory=lambda **kwargs: fake
        ) as client:
            trace = client.spi_diagnostic(TargetId.PRIMER2, SpiCommand.GET_INFO)

        self.assertTrue(fake.closed)
        self.assertEqual(trace.target_id, int(TargetId.PRIMER2))
        self.assertEqual(trace.command, int(SpiCommand.GET_INFO))
        self.assertEqual(trace.source, 2)
        self.assertEqual(trace.result_code, ErrorCode.OK)
        self.assertEqual(trace.target_transaction_id, 0x1234)
        self.assertEqual(trace.request_fingerprint, 0x89ABCDEF)
        self.assertEqual(trace.request_crc, 0x1111)
        self.assertEqual(trace.response_crc_received, 0x2222)
        self.assertEqual(trace.response_crc_calculated, 0x2222)
        self.assertFalse(trace.irq_before_request)
        self.assertTrue(trace.irq_after_request)
        self.assertTrue(trace.irq_before_response)
        self.assertTrue(trace.irq_after_response)
        self.assertEqual(trace.request_bytes, fake.request_bytes)
        self.assertEqual(trace.response_bytes, fake.response_bytes)
        self.assertEqual(trace.response_frame_length, 22)

    def test_side_effect_command_is_rejected_locally(self) -> None:
        fake = FakeDiagnosticSerial()
        client = TrinitySerialClient(
            "COM_TEST", serial_factory=lambda **kwargs: fake
        )
        with self.assertRaisesRegex(ValueError, "not side-effect-free"):
            client.spi_diagnostic(TargetId.PRIMER2, SpiCommand.RUN_SELF_TEST)
        client.close()


if __name__ == "__main__":
    unittest.main()
