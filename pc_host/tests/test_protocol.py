import unittest

from trinity_host.protocol import (
    HostFrame, SpiPacket, ProtocolDecodeError, cobs_decode, cobs_encode,
    crc16_ccitt_false, crc32c, request_fingerprint_crc32c,
)
from trinity_host.protocol.constants import ErrorCode, FrameFlags, HostCommand, SpiCommand

class ProtocolTests(unittest.TestCase):
    def test_crc_known_vectors(self):
        self.assertEqual(crc16_ccitt_false(b"123456789"), 0x29B1)
        self.assertEqual(crc32c(b"123456789"), 0xE3069283)

    def test_cobs_roundtrip(self):
        for data in (b"", b"\x00", b"abc", b"a\x00b\x00", bytes(range(1, 255)), b"\x00"*8):
            self.assertEqual(cobs_decode(cobs_encode(data)), data)

    def test_host_frame_roundtrip(self):
        frame = HostFrame(HostCommand.PING, 0, 0x1234, b"\x00abc\x00")
        self.assertEqual(HostFrame.decode_wire(frame.encode_wire()), frame)

    def test_host_crc_failure(self):
        raw = bytearray(HostFrame(HostCommand.PING, 0, 1).encode_raw())
        raw[-1] ^= 1
        with self.assertRaises(ProtocolDecodeError) as ctx:
            HostFrame.decode_raw(bytes(raw))
        self.assertEqual(ctx.exception.code, ErrorCode.BAD_CRC)

    def test_spi_max_payload_roundtrip(self):
        payload = bytes(range(66))
        packet = SpiPacket(SpiCommand.POLY_WRITE_CHUNK, 0, 0xBEEF, payload)
        encoded = packet.encode()
        self.assertEqual(len(encoded), 76)
        self.assertEqual(SpiPacket.decode(encoded), packet)

    def test_reserved_flags_rejected(self):
        with self.assertRaises(ProtocolDecodeError) as ctx:
            HostFrame(HostCommand.PING, 0x80, 1).encode_raw()
        self.assertEqual(ctx.exception.code, ErrorCode.BAD_FLAGS)

    def test_request_fingerprint(self):
        a = request_fingerprint_crc32c(SpiCommand.STAGE_SESSION, 0, b"abc")
        b = request_fingerprint_crc32c(SpiCommand.STAGE_SESSION, 0, b"abc")
        c = request_fingerprint_crc32c(SpiCommand.STAGE_SESSION, 0, b"abd")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

if __name__ == "__main__":
    unittest.main()
