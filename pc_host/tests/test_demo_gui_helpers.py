from __future__ import annotations

import unittest

from trinity_host.demo_gui import grouped_hex, ready_mask_text, stage_for_progress


class DemoGuiHelperTests(unittest.TestCase):
    def test_progress_messages_map_to_presentation_stages(self) -> None:
        cases = {
            "Kiểm tra SN32 và dual-SPI P1/P2": "preflight",
            "Sinh cặp khóa ML-KEM-512 low-RAM": "keygen",
            "Encaps/Decaps, KDF và kích hoạt session": "session",
            "P1 mã hóa và truyền UART trực tiếp sang P2": "transmit",
            "Đọc lại kết quả đã xác thực từ P2": "verify",
            "Zeroize toàn hệ thống demo": "zeroize",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(stage_for_progress(message), expected)
        self.assertIsNone(stage_for_progress("PING PASS"))

    def test_grouped_hex_is_presentable_without_changing_bytes(self) -> None:
        payload = bytes(range(12))
        self.assertEqual(
            grouped_hex(payload),
            "00010203 04050607 08090A0B",
        )
        self.assertEqual(grouped_hex("00 01 02 03", group_bytes=2), "0001 0203")

    def test_ready_mask_is_decoded_for_presenter(self) -> None:
        self.assertEqual(ready_mask_text(0x07), "SN32 • P1 • P2")
        self.assertEqual(ready_mask_text(0x0F), "SN32 • P1 • P2 • Tiny")
        self.assertEqual(ready_mask_text(0x00), "KHÔNG CÓ ENDPOINT")


if __name__ == "__main__":
    unittest.main()
