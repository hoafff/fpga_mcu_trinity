from __future__ import annotations

import struct
import unittest

from trinity_host.cli import _first_spi_failure_dict
from trinity_host.protocol import ErrorCode, SpiCommand, TargetId
from trinity_host.serial_client import HostProtocolError


def transfer_extension(
    stage: int,
    direction: int,
    byte_index: int,
    transfer_length: int,
    completed: int,
    spi_status: int,
) -> bytes:
    return struct.pack(">BBHHHI", stage, direction, byte_index,
                       transfer_length, completed, spi_status)


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
        transfer = transfer_extension(3, 2, 17, 76, 17, 0x00000004)

        decoded = _first_spi_failure_dict(bytes((1, 3)) + diagnostic + transfer)

        self.assertTrue(decoded["latched"])
        self.assertFalse(decoded["startup_residue"])
        self.assertEqual(decoded["context"], "STARTUP_PROBE")
        self.assertEqual(decoded["target_id"], int(TargetId.PRIMER2))
        self.assertEqual(decoded["command"], "0x01")
        self.assertEqual(decoded["transport_result"], "BAD_FLAGS(0x0105)")
        self.assertEqual(decoded["target_txid"], "0x0003")
        self.assertEqual(decoded["request_bytes"], request.hex(" "))
        self.assertEqual(decoded["response_bytes"], response.hex(" "))
        self.assertTrue(decoded["response_crc_match"])
        self.assertEqual(decoded["transfer_stage"], "RX_EMPTY")
        self.assertEqual(decoded["transfer_direction"], "RESPONSE")
        self.assertEqual(decoded["transfer_byte_index"], 17)
        self.assertEqual(decoded["transfer_length"], 76)
        self.assertEqual(decoded["transfer_completed"], 17)
        self.assertEqual(decoded["spi_status"], "0x00000004")

    def test_startup_drain_reset_residue_is_not_latched_failure(self) -> None:
        response = bytes.fromhex(
            "A5 01 00 03 00 00 00 06 01 03 01 00 00 00 A4 65"
        ) + bytes(76 - 16)
        diagnostic = bytes((
            int(TargetId.PRIMER1),
            0,
            1,
            0x04,
        )) + struct.pack(
            ">HHIHHHHHH",
            int(ErrorCode.BAD_LENGTH),
            0,
            0,
            0,
            len(response),
            16,
            0,
            0xA465,
            0xA465,
        ) + response
        transfer = transfer_extension(0, 2, 0, 76, 76, 0)

        decoded = _first_spi_failure_dict(bytes((0, 1)) + diagnostic + transfer)

        self.assertFalse(decoded["latched"])
        self.assertTrue(decoded["startup_residue"])
        self.assertEqual(decoded["context"], "STARTUP_DRAIN_P1")
        self.assertEqual(decoded["target_id"], int(TargetId.PRIMER1))
        self.assertEqual(decoded["command"], "0x00")
        self.assertEqual(decoded["transport_result"], "BAD_LENGTH(0x0103)")
        self.assertEqual(decoded["target_txid"], "0x0000")
        self.assertEqual(decoded["request_length"], 0)
        self.assertEqual(decoded["response_bytes"], response.hex(" "))
        self.assertTrue(decoded["response_crc_match"])
        self.assertEqual(decoded["transfer_stage"], "NONE")
        self.assertEqual(decoded["transfer_completed"], 76)

    def test_unlatched_response_has_no_trace(self) -> None:
        self.assertEqual(
            _first_spi_failure_dict(bytes((0, 0))),
            {
                "latched": False,
                "startup_residue": False,
                "context": "NONE",
            },
        )

    def test_invalid_latch_value_is_rejected(self) -> None:
        with self.assertRaisesRegex(HostProtocolError, "invalid first SPI failure"):
            _first_spi_failure_dict(bytes((2, 0)))

    def test_unlatched_non_startup_trace_is_rejected(self) -> None:
        response = bytes.fromhex(
            "A5 01 00 03 00 00 00 06 01 03 01 00 00 00 A4 65"
        ) + bytes(76 - 16)
        diagnostic = bytes((int(TargetId.PRIMER1), 0, 1, 0x04)) + struct.pack(
            ">HHIHHHHHH",
            int(ErrorCode.BAD_LENGTH), 0, 0, 0, len(response), 16,
            0, 0xA465, 0xA465,
        ) + response
        transfer = transfer_extension(0, 2, 0, 76, 76, 0)
        with self.assertRaisesRegex(HostProtocolError, "startup-drain"):
            _first_spi_failure_dict(bytes((0, 3)) + diagnostic + transfer)


if __name__ == "__main__":
    unittest.main()
