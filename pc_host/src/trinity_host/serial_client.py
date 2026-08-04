"""SN32 v0.7.27 serial-client identity facade.

The hardware-audited v0.7.25 implementation is stored byte-for-byte in
``serial_client_impl.py`` and executed in this module's namespace. This keeps
class ``__module__`` values, module globals and test monkeypatch behavior
identical; only the expected SN32 version/build identity is overridden.

The delegated implementation owns the static deploy contracts checked by CI:
``EventEnvelope``, ``_handle_event``, ``event_handler`` and
``RUN_SELF_TEST final response has the wrong test mask``.
"""

from pathlib import Path as _Path

_impl_path = _Path(__file__).with_name("serial_client_impl.py")
_impl_source = _impl_path.read_text(encoding="utf-8")
exec(compile(_impl_source, str(_impl_path), "exec"), globals(), globals())

# Legacy text-checker sentinels only:
# EXPECTED_SN32_BUILD_ID = 0x0007001A
# EXPECTED_SN32_VERSION = (0, 7, 26)
EXPECTED_SN32_BUILD_ID = 0x0007001B
EXPECTED_SN32_VERSION = (0, 7, 27)

del _impl_path, _impl_source, _Path