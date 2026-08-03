from __future__ import annotations

import struct
import unittest

from trinity_host.cli import _first_spi_failure_dict
from trinity_host.protocol import ErrorCode, SpiCommand, TargetId
from trinity_host.serial_client import HostProtocolError


class FirstSpiFailureTests(unittest.TestCase):
    def test_startup_probe_failure_is_decoded_byte_exact(self) -> None:
        request = bytes.fromhex("A5 01 01 00 00 03 00 00 4D 4A")
        response = bytes.fromhex(
            "A5 01 01 03 00 03 00 06 01 05 01 00 00 00 7B 1C"
        ) + bytes(76 - 16)
        diagnostic = bytes((
            int(TargetId.PRIMER2),
            int(SpiCommand.GET_INFO),
            2,
            0x0E,
        )) + struct.pack(
            ">HHIHHHHHH",
            int(ErrorCode.BAD_FLAGS),
            0x0003,
            0x9522E17F,
            len(request),
            len(response),
            16,
            0x4D4A,
            0x7B1C,
            0x7B1C,
        ) + request + response

        decoded = _first_spi_failure_dict(bytes((1, 3)) + diagnostic)

        self.assertTrue(decoded["latched"])
        self.assertEqual(decoded["context"], "STARTUP_PROBE")
        self.assertEqual(decoded["target_id"], int(TargetId.PRIMER2))
        self.assertEqual(decoded["command"], "0x01")
        self.assertEqual(decoded["transport_result"], "BAD_FLAGS(0x0105)")
        self.assertEqual(decoded["target_txid"], "0x0003")
        self.assertEqual(decoded["request_bytes"], request.hex(" "))
        self.assertEqual(decoded["response_bytes"], response.hex(" "))
        self.assertTrue(decoded["response_crc_match"])

    def test_unlatched_response_has_no_trace(self) -> None:
        self.assertEqual(
            _first_spi_failure_dict(bytes((0, 0))),
            {"latched": False, "context": "NONE"},
        )

    def test_invalid_latch_value_is_rejected(self) -> None:
        with self.assertRaisesRegex(HostProtocolError, "invalid first SPI failure"):
            _first_spi_failure_dict(bytes((2, 0)))


if __name__ == "__main__":
    unittest.main()
