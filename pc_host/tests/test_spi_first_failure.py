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


def register_extension(
    *,
    ctrl0: int,
    ctrl1: int,
    clkdiv: int,
    fifo_th: int,
    samples: list[tuple[int, int, int]],
) -> bytes:
    out = bytearray(struct.pack(">IIII", ctrl0, ctrl1, clkdiv, fifo_th))
    out.extend(bytes((len(samples), 0, 0, 0)))
    for before, data_word, after in samples:
        out.extend(struct.pack(">III", before, data_word, after))
    return bytes(out)


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

    def test_extended_register_telemetry_is_decoded(self) -> None:
        request = bytes.fromhex("A5 01 01 00 00 01 00 00 35 98")
        response = bytes.fromhex("1C 08 00 00 00 01 00 0C")
        diagnostic = bytes((
            int(TargetId.PRIMER1),
            int(SpiCommand.GET_INFO),
            1,
            0x0E,
        )) + struct.pack(
            ">HHIHHHHHH",
            int(ErrorCode.BAD_MAGIC),
            0x0001,
            0x9522E17F,
            len(request),
            len(response),
            0,
            0x3598,
            0,
            0,
        ) + request + response
        transfer = transfer_extension(0, 2, 0, 8, 8, 0x25)
        samples = [
            (0x21, 0x0000001C, 0x25),
            (0x21, 0x00000008, 0x25),
        ]
        registers = register_extension(
            ctrl0=0x00010007,
            ctrl1=0,
            clkdiv=59,
            fifo_th=0x80000000,
            samples=samples,
        )

        decoded = _first_spi_failure_dict(
            bytes((1, 3)) + diagnostic + transfer + registers
        )

        self.assertEqual(decoded["spi_ctrl0"], "0x00010007")
        self.assertEqual(decoded["spi_ctrl1"], "0x00000000")
        self.assertEqual(decoded["spi_clkdiv"], "0x0000003B")
        self.assertEqual(decoded["spi_fifo_th"], "0x80000000")
        self.assertEqual(decoded["response_sample_count"], 2)
        self.assertEqual(
            decoded["response_status_before_read"],
            "0x00000021 0x00000021",
        )
        self.assertEqual(
            decoded["response_data_words"],
            "0x0000001C 0x00000008",
        )
        self.assertEqual(
            decoded["response_status_after_read"],
            "0x00000025 0x00000025",
        )

        gpio_registers = register_extension(
            ctrl0=0x4750494F,
            ctrl1=100_000,
            clkdiv=60,
            fifo_th=0,
            samples=[(0, 0xA5, 0)],
        )
        gpio_decoded = _first_spi_failure_dict(
            bytes((1, 3)) + diagnostic + transfer + gpio_registers
        )
        self.assertEqual(gpio_decoded["spi_backend"], "GPIO_MODE0")
        self.assertEqual(gpio_decoded["spi_max_hz"], 100_000)
        self.assertEqual(gpio_decoded["spi_half_period_cycles"], 60)

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

    def test_startup_probe_reset_residue_is_decoded(self) -> None:
        response = bytes.fromhex(
            "A5 01 00 03 00 00 00 06 01 03 01 00 00 00 A4 65"
        ) + bytes(76 - 16)
        diagnostic = bytes((int(TargetId.PRIMER1), 0, 1, 0x04)) + struct.pack(
            ">HHIHHHHHH",
            int(ErrorCode.BAD_LENGTH), 0, 0, 0, len(response), 16,
            0, 0xA465, 0xA465,
        ) + response
        transfer = transfer_extension(0, 2, 0, 76, 76, 0)
        decoded = _first_spi_failure_dict(
            bytes((0, 3)) + diagnostic + transfer
        )
        self.assertFalse(decoded["latched"])
        self.assertTrue(decoded["startup_residue"])
        self.assertEqual(decoded["context"], "STARTUP_PROBE")

    def test_unlatched_host_diagnostic_trace_is_rejected(self) -> None:
        response = bytes.fromhex(
            "A5 01 00 03 00 00 00 06 01 03 01 00 00 00 A4 65"
        ) + bytes(76 - 16)
        diagnostic = bytes((int(TargetId.PRIMER1), 0, 1, 0x04)) + struct.pack(
            ">HHIHHHHHH",
            int(ErrorCode.BAD_LENGTH), 0, 0, 0, len(response), 16,
            0, 0xA465, 0xA465,
        ) + response
        transfer = transfer_extension(0, 2, 0, 76, 76, 0)
        with self.assertRaisesRegex(HostProtocolError, "startup/periodic"):
            _first_spi_failure_dict(bytes((0, 5)) + diagnostic + transfer)


if __name__ == "__main__":
    unittest.main()
