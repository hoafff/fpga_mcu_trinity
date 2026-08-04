from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Final

from .protocol import (
    ErrorCode,
    HostCommand,
    SystemCapability,
    SystemState,
    SystemStatus,
    TargetReadyMask,
    TransactionState,
    ZeroizeScope,
)
from .serial_client import (
    HostProtocolError,
    Sn32QualificationResult,
    SystemInfo,
    TrinitySerialClient,
)

KEYPAIR_MODE_RANDOM: Final[int] = 0
KEYPAIR_MODE_DETERMINISTIC: Final[int] = 1
SESSION_MODE_DETERMINISTIC: Final[int] = 0
SESSION_MODE_KAT: Final[int] = 1

DEFAULT_KEYPAIR_SEED: Final[bytes] = bytes(range(0x00, 0x20))
DEFAULT_SESSION_SEED: Final[bytes] = bytes(range(0x20, 0x40))
DEFAULT_TELEMETRY_HEADER: Final[bytes] = bytes.fromhex("0200BEEF534E0000")
DEFAULT_PLAINTEXTS: Final[tuple[bytes, bytes]] = (
    bytes(range(0x00, 0x18)),
    bytes(range(0x80, 0x98)),
)

_REQUIRED_READY_MASK: Final[int] = int(
    TargetReadyMask.SN32 | TargetReadyMask.PRIMER1 | TargetReadyMask.PRIMER2
)
_REQUIRED_CAPABILITIES: Final[int] = int(
    SystemCapability.KAT
    | SystemCapability.MLKEM512
    | SystemCapability.ASCON_AEAD128
    | SystemCapability.PAYLOAD_UART
    | SystemCapability.TRANSACTION_RECONCILIATION
)


@dataclass(frozen=True, slots=True)
class KeypairResult:
    host_txid: int
    public_key_hash: bytes


@dataclass(frozen=True, slots=True)
class SessionResult:
    host_txid: int
    session_id: int
    initial_sequence: int


@dataclass(frozen=True, slots=True)
class TelemetryResult:
    host_txid: int
    session_id: int
    sequence: int
    plaintext: bytes
    status: ErrorCode


@dataclass(frozen=True, slots=True)
class SecureTelemetryQualificationResult:
    control_plane: Sn32QualificationResult
    info: SystemInfo
    status_before: SystemStatus
    keypair: KeypairResult
    session: SessionResult
    status_active: SystemStatus
    telemetry: tuple[TelemetryResult, ...]
    last_result: TelemetryResult
    status_final: SystemStatus


def parse_seed_hex(text: str) -> bytes:
    try:
        seed = bytes.fromhex(text)
    except ValueError as exc:
        raise ValueError("seed must be hexadecimal") from exc
    if len(seed) != 32:
        raise ValueError(f"seed must be exactly 32 bytes, got {len(seed)}")
    return seed


def parse_plaintext_hex(text: str) -> bytes:
    try:
        plaintext = bytes.fromhex(text)
    except ValueError as exc:
        raise ValueError("plaintext must be hexadecimal") from exc
    if len(plaintext) != 24:
        raise ValueError(
            f"plaintext must be exactly 24 bytes, got {len(plaintext)}"
        )
    return plaintext


def _require_seed(seed: bytes) -> bytes:
    if len(seed) != 32:
        raise ValueError(f"seed must be exactly 32 bytes, got {len(seed)}")
    return seed


def _retained_request(
    client: TrinitySerialClient,
    command: HostCommand,
    payload: bytes = b"",
    *,
    timeout: float,
) -> tuple[int, bytes]:
    response = client.request(command, payload, timeout=timeout)
    host_txid = response.transaction_id
    retained = client.get_transaction_result(host_txid)
    try:
        if retained.queried_txid != host_txid:
            raise HostProtocolError("retained transaction ID mismatch")
        if retained.state != TransactionState.SUCCEEDED:
            raise HostProtocolError(
                "managed command did not retain SUCCEEDED: "
                f"state={retained.state.name}, "
                f"result={retained.result_code.name}"
            )
        if retained.original_command != int(command):
            raise HostProtocolError(
                "retained command mismatch: "
                f"0x{retained.original_command:02X} != 0x{int(command):02X}"
            )
        if retained.result_code != ErrorCode.OK:
            raise HostProtocolError(
                f"retained result is {retained.result_code.name}"
            )
        if retained.data != response.payload:
            raise HostProtocolError(
                "immediate and retained managed-command results differ"
            )
        return host_txid, response.payload
    finally:
        client.retire_transaction_result(host_txid)


def generate_keypair(
    client: TrinitySerialClient,
    *,
    deterministic: bool = True,
    seed: bytes = DEFAULT_KEYPAIR_SEED,
    timeout: float = 30.0,
) -> KeypairResult:
    if deterministic:
        payload = bytes((KEYPAIR_MODE_DETERMINISTIC,)) + _require_seed(seed)
    else:
        payload = bytes((KEYPAIR_MODE_RANDOM,)) + bytes(32)
    host_txid, result = _retained_request(
        client,
        HostCommand.GENERATE_KEYPAIR,
        payload,
        timeout=timeout,
    )
    if len(result) != 32:
        raise HostProtocolError(
            f"GENERATE_KEYPAIR result must be 32 bytes, got {len(result)}"
        )
    return KeypairResult(host_txid, result)


def create_session(
    client: TrinitySerialClient,
    *,
    kat: bool = True,
    seed: bytes = DEFAULT_SESSION_SEED,
    timeout: float = 30.0,
) -> SessionResult:
    if kat:
        payload = bytes((SESSION_MODE_KAT,)) + _require_seed(seed)
    else:
        payload = bytes((SESSION_MODE_DETERMINISTIC,)) + bytes(32)
    host_txid, result = _retained_request(
        client,
        HostCommand.CREATE_SESSION,
        payload,
        timeout=timeout,
    )
    if len(result) != 12:
        raise HostProtocolError(
            f"CREATE_SESSION result must be 12 bytes, got {len(result)}"
        )
    session_id, sequence = struct.unpack(">IQ", result)
    if session_id == 0:
        raise HostProtocolError("CREATE_SESSION returned session_id=0")
    return SessionResult(host_txid, session_id, sequence)


def _decode_telemetry_result(host_txid: int, payload: bytes) -> TelemetryResult:
    if len(payload) != 38:
        raise HostProtocolError(
            f"telemetry result must be 38 bytes, got {len(payload)}"
        )
    session_id, sequence = struct.unpack_from(">IQ", payload, 0)
    plaintext = payload[12:36]
    status_raw = struct.unpack_from(">H", payload, 36)[0]
    try:
        status = ErrorCode(status_raw)
    except ValueError as exc:
        raise HostProtocolError(
            f"unknown telemetry status 0x{status_raw:04X}"
        ) from exc
    return TelemetryResult(host_txid, session_id, sequence, plaintext, status)


def send_telemetry(
    client: TrinitySerialClient,
    plaintext: bytes,
    *,
    header: bytes = DEFAULT_TELEMETRY_HEADER,
    timeout: float = 10.0,
) -> TelemetryResult:
    if len(header) != 8:
        raise ValueError(f"telemetry header must be 8 bytes, got {len(header)}")
    if header[1] != 0 or header[6] != 0 or header[7] != 0:
        raise ValueError("telemetry reserved header bytes must be zero")
    if len(plaintext) != 24:
        raise ValueError(
            f"plaintext must be exactly 24 bytes, got {len(plaintext)}"
        )
    host_txid, payload = _retained_request(
        client,
        HostCommand.SEND_ONE_TELEMETRY,
        header + plaintext,
        timeout=timeout,
    )
    result = _decode_telemetry_result(host_txid, payload)
    if result.status != ErrorCode.OK:
        raise HostProtocolError(
            f"telemetry returned status {result.status.name}"
        )
    if result.plaintext != plaintext:
        raise HostProtocolError("authenticated plaintext differs byte-for-byte")
    return result


def read_last_result(
    client: TrinitySerialClient,
    *,
    timeout: float = 2.0,
) -> TelemetryResult:
    response = client.request(HostCommand.READ_LAST_RESULT, timeout=timeout)
    return _decode_telemetry_result(response.transaction_id, response.payload)


def close_session(
    client: TrinitySerialClient,
    *,
    timeout: float = 30.0,
) -> int:
    host_txid, payload = _retained_request(
        client,
        HostCommand.CLOSE_SESSION,
        timeout=timeout,
    )
    if payload:
        raise HostProtocolError("CLOSE_SESSION result must be empty")
    return host_txid


def zeroize(
    client: TrinitySerialClient,
    *,
    scope: ZeroizeScope = ZeroizeScope.ALL,
    timeout: float = 30.0,
) -> int:
    host_txid, payload = _retained_request(
        client,
        HostCommand.ZEROIZE_SYSTEM,
        bytes((int(scope) & 0xFF,)),
        timeout=timeout,
    )
    if payload:
        raise HostProtocolError("ZEROIZE_SYSTEM result must be empty")
    return host_txid


def _validate_full_preflight(info: SystemInfo, status: SystemStatus) -> None:
    missing = _REQUIRED_CAPABILITIES & ~info.capabilities
    if missing:
        raise HostProtocolError(
            f"SN32 is missing secure-telemetry capabilities 0x{missing:08X}"
        )
    if (status.target_ready_mask & _REQUIRED_READY_MASK) != _REQUIRED_READY_MASK:
        raise HostProtocolError(
            "P1/P2 are not ready for secure telemetry: "
            f"ready_mask=0x{status.target_ready_mask:02X}"
        )
    if status.fault_flags != 0 or status.last_error != ErrorCode.OK:
        raise HostProtocolError(
            "preflight is not clean: "
            f"fault_flags=0x{status.fault_flags:02X}, "
            f"last_error={status.last_error.name}"
        )
    if status.active_host_txid != 0:
        raise HostProtocolError(
            f"host transaction 0x{status.active_host_txid:04X} is still retained"
        )
    if status.system_state != SystemState.READY_NO_KEYPAIR:
        raise HostProtocolError(
            "secure telemetry qualification requires READY_NO_KEYPAIR, got "
            f"{status.system_state.name}; zeroize or power-cycle first"
        )


def run_secure_telemetry_qualification(
    client: TrinitySerialClient,
    *,
    keypair_seed: bytes = DEFAULT_KEYPAIR_SEED,
    session_seed: bytes = DEFAULT_SESSION_SEED,
    plaintexts: tuple[bytes, ...] = DEFAULT_PLAINTEXTS,
    timeout: float = 30.0,
    poll_interval: float = 0.05,
) -> SecureTelemetryQualificationResult:
    if len(plaintexts) < 2:
        raise ValueError("qualification requires at least two plaintexts")

    control_plane = client.run_sn32_hardware_qualification(
        timeout=timeout,
        poll_interval=poll_interval,
        liveness_iterations=2,
    )
    info = control_plane.dual_spi.info
    status_before = client.get_system_status()
    _validate_full_preflight(info, status_before)

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

    session = create_session(
        client,
        kat=True,
        seed=session_seed,
        timeout=timeout,
    )
    status_active = client.get_system_status()
    if status_active.system_state != SystemState.ACTIVE:
        raise HostProtocolError(
            f"session activation did not enter ACTIVE: {status_active.system_state.name}"
        )
    if status_active.session_id != session.session_id:
        raise HostProtocolError("active status session ID differs from CREATE_SESSION")
    if status_active.current_sequence != session.initial_sequence:
        raise HostProtocolError(
            "active status sequence differs from CREATE_SESSION"
        )

    results: list[TelemetryResult] = []
    expected_sequence = session.initial_sequence
    try:
        for plaintext in plaintexts:
            expected_sequence += 1
            result = send_telemetry(client, plaintext, timeout=timeout)
            if result.session_id != session.session_id:
                raise HostProtocolError("telemetry session ID mismatch")
            if result.sequence != expected_sequence:
                raise HostProtocolError(
                    f"telemetry sequence {result.sequence} != {expected_sequence}"
                )
            results.append(result)

        last_result = read_last_result(client)
        final_result = results[-1]
        if (
            last_result.session_id != final_result.session_id
            or last_result.sequence != final_result.sequence
            or last_result.plaintext != final_result.plaintext
            or last_result.status != final_result.status
        ):
            raise HostProtocolError(
                "READ_LAST_RESULT differs from the final telemetry result"
            )
    finally:
        zeroize(client, scope=ZeroizeScope.ALL, timeout=timeout)

    status_final = client.get_system_status()
    if status_final.system_state != SystemState.READY_NO_KEYPAIR:
        raise HostProtocolError(
            "full zeroize did not restore READY_NO_KEYPAIR: "
            f"{status_final.system_state.name}"
        )
    if status_final.session_id != 0 or status_final.current_sequence != 0:
        raise HostProtocolError("full zeroize retained session metadata")
    if status_final.fault_flags != 0 or status_final.last_error != ErrorCode.OK:
        raise HostProtocolError("full zeroize did not leave a clean final status")

    return SecureTelemetryQualificationResult(
        control_plane=control_plane,
        info=info,
        status_before=status_before,
        keypair=keypair,
        session=session,
        status_active=status_active,
        telemetry=tuple(results),
        last_result=last_result,
        status_final=status_final,
    )
