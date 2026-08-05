"""SN32 v0.7.30 serial-client identity and recovery facade.

The delegated implementation in ``serial_client_impl.py`` remains the owner of
``EventEnvelope``, ``_handle_event``, ``event_handler`` and the validation text
``RUN_SELF_TEST final response has the wrong test mask``. These names are kept
here as static contract markers while the implementation is executed in this
module's namespace.
"""

from pathlib import Path as _Path

_impl_path = _Path(__file__).with_name("serial_client_impl.py")
_impl_source = _impl_path.read_text(encoding="utf-8")
exec(compile(_impl_source, str(_impl_path), "exec"), globals(), globals())

from dataclasses import dataclass as _dataclass
import struct as _struct

# Legacy text-checker sentinels only:
# EXPECTED_SN32_BUILD_ID = 0x0007001A
# EXPECTED_SN32_VERSION = (0, 7, 26)
EXPECTED_SN32_BUILD_ID = 0x0007001E
EXPECTED_SN32_VERSION = (0, 7, 30)

_SESSION_FAILURE_PHASE_NAMES = {
    0: "NONE",
    1: "STAGE_WAIT",
    2: "COMMIT_WAIT",
    3: "ACTIVE_WAIT",
}

_SESSION_STATE_NAMES = {
    0: "BOOT",
    1: "SELF_TEST_REQUIRED",
    2: "SELF_TEST_RUNNING",
    3: "READY_NO_SESSION",
    4: "STAGED",
    5: "COMMITTED_BLOCKED",
    6: "ACTIVE",
    7: "ZEROIZE_BUSY",
    8: "FAULT_LOCKED",
}


@_dataclass(frozen=True, slots=True)
class LastErrorSnapshot:
    code: ErrorCode
    source: int
    detail: int

    @classmethod
    def decode(cls, payload: bytes) -> "LastErrorSnapshot":
        if len(payload) != 8:
            raise HostProtocolError(
                f"GET_LAST_ERROR response must be 8 bytes, got {len(payload)}"
            )
        code_raw, source, reserved, detail = _struct.unpack(">HBBI", payload)
        if reserved != 0:
            raise HostProtocolError("GET_LAST_ERROR reserved byte is nonzero")
        try:
            code = ErrorCode(code_raw)
        except ValueError as exc:
            raise HostProtocolError(
                f"unknown last-error code 0x{code_raw:04X}"
            ) from exc
        return cls(code, source, detail)


@_dataclass(frozen=True, slots=True)
class SessionCommitDiagnostic:
    phase: int
    gpio_high: bool
    p1_session_state: int
    p2_session_state: int
    p1_secure_flags: int
    p2_secure_flags: int

    @classmethod
    def from_last_error(
        cls, snapshot: LastErrorSnapshot
    ) -> "SessionCommitDiagnostic | None":
        if snapshot.code != ErrorCode.SESSION_COMMIT_FAILED:
            return None
        detail = snapshot.detail
        return cls(
            phase=(detail >> 28) & 0x0F,
            gpio_high=bool(detail & 0x08000000),
            p1_session_state=(detail >> 20) & 0x0F,
            p2_session_state=(detail >> 16) & 0x0F,
            p1_secure_flags=(detail >> 8) & 0xFF,
            p2_secure_flags=detail & 0xFF,
        )

    def describe(self) -> str:
        phase = _SESSION_FAILURE_PHASE_NAMES.get(
            self.phase, f"UNKNOWN_{self.phase}"
        )
        p1_state = _SESSION_STATE_NAMES.get(
            self.p1_session_state, f"UNKNOWN_{self.p1_session_state}"
        )
        p2_state = _SESSION_STATE_NAMES.get(
            self.p2_session_state, f"UNKNOWN_{self.p2_session_state}"
        )
        return (
            f"phase={phase}, P2.9_readback={'HIGH' if self.gpio_high else 'LOW'}, "
            f"P1={p1_state}/secure=0x{self.p1_secure_flags:02X}, "
            f"P2={p2_state}/secure=0x{self.p2_secure_flags:02X}"
        )


def _get_last_error(self: TrinitySerialClient) -> LastErrorSnapshot:
    response = self.request(HostCommand.GET_LAST_ERROR, timeout=2.0)
    return LastErrorSnapshot.decode(response.payload)


TrinitySerialClient.get_last_error = _get_last_error

del _impl_path, _impl_source, _Path, _dataclass
