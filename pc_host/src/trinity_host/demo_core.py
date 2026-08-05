from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .full_flow import (
    DEFAULT_KEYPAIR_SEED,
    DEFAULT_PLAINTEXTS,
    DEFAULT_SESSION_SEED,
    KeypairResult,
    SessionResult,
    TelemetryResult,
    _validate_full_preflight,
    create_session,
    emergency_zeroize,
    generate_keypair,
    read_last_result,
    read_session_commit_diagnostic,
    send_telemetry,
)
from .protocol import ErrorCode, SystemState, SystemStatus
from .serial_client import (
    HostProtocolError,
    Sn32QualificationResult,
    SystemInfo,
    TrinitySerialClient,
)

ProgressCallback = Callable[[str, int | None], None]


@dataclass(frozen=True, slots=True)
class CoreDemoResult:
    control_plane: Sn32QualificationResult
    info: SystemInfo
    status_before: SystemStatus
    keypair: KeypairResult
    session: SessionResult
    status_active: SystemStatus
    telemetry: TelemetryResult
    last_result: TelemetryResult
    status_final: SystemStatus
    final_uptime_ms: int


def _emit(callback: ProgressCallback | None, message: str, percent: int | None) -> None:
    if callback is not None:
        callback(message, percent)


def _require_active(status: SystemStatus, session: SessionResult) -> None:
    if status.system_state != SystemState.ACTIVE:
        raise HostProtocolError(
            f"session activation did not enter ACTIVE: {status.system_state.name}"
        )
    if status.session_id != session.session_id:
        raise HostProtocolError("active status session ID differs from CREATE_SESSION")
    if status.current_sequence != session.initial_sequence:
        raise HostProtocolError("active status sequence differs from CREATE_SESSION")
    if status.fault_flags != 0 or status.last_error != ErrorCode.OK:
        raise HostProtocolError(
            "session activation left a fault: "
            f"flags=0x{status.fault_flags:02X}, error={status.last_error.name}"
        )


def run_core_demo(
    client: TrinitySerialClient,
    *,
    plaintext: bytes = DEFAULT_PLAINTEXTS[0],
    keypair_seed: bytes = DEFAULT_KEYPAIR_SEED,
    session_seed: bytes = DEFAULT_SESSION_SEED,
    timeout: float = 120.0,
    on_progress: ProgressCallback | None = None,
) -> CoreDemoResult:
    """Run the minimum real PC→SN32→P1→P2 secure-telemetry demonstration."""

    if len(plaintext) != 24:
        raise ValueError(f"plaintext must be exactly 24 bytes, got {len(plaintext)}")

    _emit(on_progress, "Kiểm tra SN32 và dual-SPI P1/P2", 5)
    control_plane = client.run_sn32_hardware_qualification(
        timeout=min(timeout, 30.0),
        poll_interval=0.05,
        liveness_iterations=2,
    )
    info = control_plane.dual_spi.info
    status_before = client.get_system_status()
    _validate_full_preflight(info, status_before)

    keypair: KeypairResult | None = None
    session: SessionResult | None = None
    telemetry: TelemetryResult | None = None
    last_result: TelemetryResult | None = None
    status_active: SystemStatus | None = None

    try:
        _emit(on_progress, "Sinh cặp khóa ML-KEM-512 low-RAM", 25)
        keypair = generate_keypair(
            client,
            deterministic=True,
            seed=keypair_seed,
            timeout=timeout,
        )
        after_keypair = client.get_system_status()
        if after_keypair.system_state != SystemState.READY_NO_SESSION:
            raise HostProtocolError(
                "keypair generation did not enter READY_NO_SESSION: "
                f"{after_keypair.system_state.name}"
            )

        _emit(on_progress, "Encaps/Decaps, KDF và kích hoạt session", 50)
        session = create_session(
            client,
            kat=True,
            seed=session_seed,
            timeout=timeout,
        )
        status_active = client.get_system_status()
        _require_active(status_active, session)

        _emit(on_progress, "P1 mã hóa và truyền UART trực tiếp sang P2", 72)
        telemetry = send_telemetry(client, plaintext, timeout=min(timeout, 30.0))
        expected_sequence = session.initial_sequence + 1
        if telemetry.session_id != session.session_id:
            raise HostProtocolError("telemetry session ID mismatch")
        if telemetry.sequence != expected_sequence:
            raise HostProtocolError(
                f"telemetry sequence {telemetry.sequence} != {expected_sequence}"
            )

        _emit(on_progress, "Đọc lại kết quả đã xác thực từ P2", 85)
        last_result = read_last_result(client, timeout=5.0)
        if (
            last_result.session_id != telemetry.session_id
            or last_result.sequence != telemetry.sequence
            or last_result.plaintext != telemetry.plaintext
            or last_result.status != ErrorCode.OK
        ):
            raise HostProtocolError("READ_LAST_RESULT differs from authenticated telemetry")

        _emit(on_progress, "Zeroize toàn hệ thống demo", 94)
        emergency_zeroize(client, timeout=min(timeout, 30.0))
    except Exception as original_error:
        if keypair is None:
            raise

        diagnostic_text = "không có session-commit diagnostic"
        try:
            snapshot, diagnostic = read_session_commit_diagnostic(client)
            if diagnostic is not None:
                diagnostic_text = diagnostic.describe()
            else:
                diagnostic_text = (
                    f"last_error={snapshot.code.name}, "
                    f"source={snapshot.source}, detail=0x{snapshot.detail:08X}"
                )
        except Exception as diagnostic_error:
            diagnostic_text = f"đọc diagnostic thất bại: {diagnostic_error}"

        cleanup_text = "PASS"
        _emit(on_progress, "Dọn trạng thái bằng emergency zeroize", 92)
        try:
            emergency_zeroize(client, timeout=min(timeout, 30.0))
        except Exception as cleanup_error:
            cleanup_text = f"FAIL: {cleanup_error}"

        raise HostProtocolError(
            f"{original_error}; SESSION COMMIT DIAGNOSTIC: {diagnostic_text}; "
            f"emergency_zeroize={cleanup_text}"
        ) from original_error

    status_final = client.get_system_status()
    if status_final.system_state != SystemState.READY_NO_KEYPAIR:
        raise HostProtocolError(
            "zeroize did not restore READY_NO_KEYPAIR: "
            f"{status_final.system_state.name}"
        )
    if (
        status_final.session_id != 0
        or status_final.current_sequence != 0
        or status_final.fault_flags != 0
        or status_final.last_error != ErrorCode.OK
        or status_final.active_host_txid != 0
    ):
        raise HostProtocolError("zeroize did not leave a clean final status")

    final_uptime_ms = client.ping()
    _emit(on_progress, "CORE DEMO PASS — Tiny 1P5 không thuộc phạm vi", 100)

    assert keypair is not None
    assert session is not None
    assert status_active is not None
    assert telemetry is not None
    assert last_result is not None
    return CoreDemoResult(
        control_plane=control_plane,
        info=info,
        status_before=status_before,
        keypair=keypair,
        session=session,
        status_active=status_active,
        telemetry=telemetry,
        last_result=last_result,
        status_final=status_final,
        final_uptime_ms=final_uptime_ms,
    )
