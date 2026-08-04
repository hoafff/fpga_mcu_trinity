from __future__ import annotations

import contextlib
import io
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


if __name__ == "__main__":
    unittest.main()
