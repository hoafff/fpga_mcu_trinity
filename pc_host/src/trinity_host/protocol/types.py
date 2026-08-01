from __future__ import annotations

from dataclasses import dataclass
import struct

from .constants import ErrorCode, EventType, Mode, Source, SystemState, TransactionState

@dataclass(frozen=True, slots=True)
class SystemStatus:
    system_state: SystemState
    mode: Mode
    target_ready_mask: int
    fault_flags: int
    session_id: int
    current_sequence: int
    last_error: ErrorCode
    active_host_txid: int

    _STRUCT = struct.Struct(">BBBBIQHH")

    @classmethod
    def decode(cls, payload: bytes) -> "SystemStatus":
        if len(payload) != cls._STRUCT.size:
            raise ValueError(f"system status must be {cls._STRUCT.size} bytes")
        state, mode, ready, faults, session, seq, error, txid = cls._STRUCT.unpack(payload)
        return cls(SystemState(state), Mode(mode), ready, faults, session, seq,
                   ErrorCode(error), txid)

@dataclass(frozen=True, slots=True)
class TransactionResult:
    queried_txid: int
    state: TransactionState
    original_command: int
    result_code: ErrorCode
    data: bytes

    @classmethod
    def decode(cls, payload: bytes) -> "TransactionResult":
        if len(payload) < 8:
            raise ValueError("transaction result too short")
        txid, state, command, result_code, length = struct.unpack_from(">HBBHH", payload)
        if len(payload) != 8 + length:
            raise ValueError("transaction result length mismatch")
        return cls(txid, TransactionState(state), command, ErrorCode(result_code), payload[8:])

@dataclass(frozen=True, slots=True)
class AuthenticatedResult:
    session_id: int
    sequence: int
    plaintext: bytes
    result_code: ErrorCode

    @classmethod
    def decode(cls, payload: bytes) -> "AuthenticatedResult":
        if len(payload) != 38:
            raise ValueError("authenticated result must be 38 bytes")
        session_id, sequence = struct.unpack_from(">IQ", payload)
        return cls(session_id, sequence, payload[12:36],
                   ErrorCode(struct.unpack_from(">H", payload, 36)[0]))

@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_type: EventType
    severity: int
    source: Source
    related_transaction_id: int
    progress_percent: int | None
    data: bytes

    @classmethod
    def decode(cls, payload: bytes) -> "EventEnvelope":
        if len(payload) < 8:
            raise ValueError("event payload too short")
        event_type, severity, source, txid, progress, reserved = struct.unpack_from(">HBBHBB", payload)
        if reserved != 0:
            raise ValueError("event reserved byte is non-zero")
        if progress != 0xFF and progress > 100:
            raise ValueError("invalid progress")
        return cls(EventType(event_type), severity, Source(source), txid,
                   None if progress == 0xFF else progress, payload[8:])
