from __future__ import annotations

import contextlib
import io
from types import SimpleNamespace
import unittest
from unittest import mock

from trinity_host import entrypoint


class EntrypointTests(unittest.TestCase):
    def test_top_level_help_lists_legacy_and_full_flow_commands(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = entrypoint.main(["--help"])

        text = output.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("sn32-qualify", text)
        self.assertIn("keypair-generate", text)
        self.assertIn("session-create", text)
        self.assertIn("telemetry-send", text)
        self.assertIn("zeroize", text)
        self.assertIn("sn32-secure-telemetry-qualify", text)

    def test_full_flow_command_delegates_to_full_cli(self) -> None:
        argv = ["--port", "COM3", "zeroize", "--scope", "all"]
        with mock.patch.object(entrypoint.full_cli, "main", return_value=7) as main:
            result = entrypoint.main(argv)

        self.assertEqual(result, 7)
        main.assert_called_once_with(argv)

    def test_legacy_command_also_delegates_to_full_cli_dispatcher(self) -> None:
        argv = ["--port", "COM3", "ping"]
        with mock.patch.object(entrypoint.full_cli, "main", return_value=0) as main:
            result = entrypoint.main(argv)

        self.assertEqual(result, 0)
        main.assert_called_once_with(argv)

    def test_v0726_keypair_is_blocked_before_command_dispatch(self) -> None:
        argv = ["--port", "COM3", "keypair-generate"]
        serial = mock.MagicMock()
        serial.__enter__.return_value.get_system_info.return_value = SimpleNamespace(
            sn32_build_id=0x0007001A
        )
        error = io.StringIO()
        with (
            mock.patch.object(entrypoint, "TrinitySerialClient", return_value=serial),
            mock.patch.object(entrypoint.full_cli, "main") as main,
            contextlib.redirect_stderr(error),
        ):
            result = entrypoint.main(argv)

        self.assertEqual(result, 1)
        self.assertIn("confirmed 8 KiB-RAM/2 KiB-stack", error.getvalue())
        main.assert_not_called()

    def test_newer_safe_image_delegates_mlkem_command(self) -> None:
        argv = ["--port", "COM3", "sn32-secure-telemetry-qualify"]
        serial = mock.MagicMock()
        serial.__enter__.return_value.get_system_info.return_value = SimpleNamespace(
            sn32_build_id=0x0007001B
        )
        with (
            mock.patch.object(entrypoint, "TrinitySerialClient", return_value=serial),
            mock.patch.object(entrypoint.full_cli, "main", return_value=0) as main,
        ):
            result = entrypoint.main(argv)

        self.assertEqual(result, 0)
        main.assert_called_once_with(argv)


if __name__ == "__main__":
    unittest.main()
