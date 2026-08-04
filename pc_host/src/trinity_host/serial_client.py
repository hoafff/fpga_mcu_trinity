"""SN32 v0.7.26 serial-client identity facade.

The hardware-audited v0.7.25 implementation is stored byte-for-byte in
``serial_client_impl.py`` and executed in this module's namespace. This keeps
class ``__module__`` values, module globals and test monkeypatch behavior
identical; only the expected SN32 version/build identity is overridden.
"""

from pathlib import Path as _Path

_impl_path = _Path(__file__).with_name("serial_client_impl.py")
_impl_source = _impl_path.read_text(encoding="utf-8")
exec(compile(_impl_source, str(_impl_path), "exec"), globals(), globals())

EXPECTED_SN32_BUILD_ID = 0x0007001A
EXPECTED_SN32_VERSION = (0, 7, 26)

del _impl_path, _impl_source, _Path
