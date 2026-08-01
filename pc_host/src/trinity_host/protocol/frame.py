from __future__ import annotations

from dataclasses import dataclass
import struct

from .cobs import cobs_decode, cobs_encode
from .constants import (
    ErrorCode, FrameFlags, PC_MAX_PAYLOAD, PROTOCOL_VERSION, SPI_MAGIC,
    SPI_MAX_PAYLOAD,
)
from .crc import crc16_ccitt_false, crc32c

_PC_HEADER = struct.Struct(">BBBBHH")
_SPI_HEADER = struct.Struct(">BBBBHH")

class ProtocolDecodeError(ValueError):
    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code

def _check_flags(flags: int) -> None:
    if flags & ~int(FrameFlags.RESPONSE | FrameFlags.ERROR | FrameFlags.MORE | FrameFlags.EVENT):
        raise ProtocolDecodeError(ErrorCode.BAD_FLAGS, f"reserved flag bits set: 0x{flags:02X}")

@dataclass(frozen=True, slots=True)
class HostFrame:
    command: int
    flags: int
    transaction_id: int
    payload: bytes = b""
    version: int = PROTOCOL_VERSION

    def encode_raw(self) -> bytes:
        if self.version != PROTOCOL_VERSION:
            raise ValueError("unsupported protocol version")
        _check_flags(self.flags)
        if not 0 <= self.transaction_id <= 0xFFFF:
            raise ValueError("transaction_id out of range")
        if len(self.payload) > PC_MAX_PAYLOAD:
            raise ValueError("payload exceeds 256 bytes")
        header = _PC_HEADER.pack(
            self.version, self.command & 0xFF, self.flags & 0xFF, 0,
            self.transaction_id, len(self.payload),
        )
        body = header + self.payload
        return body + struct.pack(">H", crc16_ccitt_false(body))

    def encode_wire(self) -> bytes:
        return cobs_encode(self.encode_raw()) + b"\x00"

    @classmethod
    def decode_raw(cls, raw: bytes) -> "HostFrame":
        if len(raw) < _PC_HEADER.size + 2:
            raise ProtocolDecodeError(ErrorCode.BAD_LENGTH, "raw host frame too short")
        version, command, flags, reserved, txid, payload_len = _PC_HEADER.unpack_from(raw)
        if version != PROTOCOL_VERSION:
            raise ProtocolDecodeError(ErrorCode.BAD_VERSION, f"version {version}")
        if reserved != 0:
            raise ProtocolDecodeError(ErrorCode.BAD_FLAGS, "reserved header byte is non-zero")
        _check_flags(flags)
        if payload_len > PC_MAX_PAYLOAD:
            raise ProtocolDecodeError(ErrorCode.BAD_LENGTH, "payload exceeds 256 bytes")
        expected = _PC_HEADER.size + payload_len + 2
        if len(raw) != expected:
            raise ProtocolDecodeError(ErrorCode.BAD_LENGTH, f"expected {expected}, got {len(raw)}")
        expected_crc = struct.unpack_from(">H", raw, len(raw) - 2)[0]
        actual_crc = crc16_ccitt_false(raw[:-2])
        if expected_crc != actual_crc:
            raise ProtocolDecodeError(ErrorCode.BAD_CRC, "host frame CRC mismatch")
        return cls(command=command, flags=flags, transaction_id=txid,
                   payload=bytes(raw[_PC_HEADER.size:-2]), version=version)

    @classmethod
    def decode_wire(cls, wire: bytes) -> "HostFrame":
        if not wire or wire[-1] != 0:
            raise ProtocolDecodeError(ErrorCode.MALFORMED_FRAME, "missing COBS delimiter")
        if 0 in wire[:-1]:
            raise ProtocolDecodeError(ErrorCode.MALFORMED_FRAME, "multiple delimiters in one frame")
        try:
            raw = cobs_decode(wire[:-1])
        except ValueError as exc:
            raise ProtocolDecodeError(ErrorCode.MALFORMED_FRAME, str(exc)) from exc
        return cls.decode_raw(raw)

@dataclass(frozen=True, slots=True)
class SpiPacket:
    command: int
    flags: int
    transaction_id: int
    payload: bytes = b""
    version: int = PROTOCOL_VERSION

    def encode(self) -> bytes:
        if self.version != PROTOCOL_VERSION:
            raise ValueError("unsupported protocol version")
        _check_flags(self.flags)
        if not 0 <= self.transaction_id <= 0xFFFF:
            raise ValueError("transaction_id out of range")
        if len(self.payload) > SPI_MAX_PAYLOAD:
            raise ValueError("SPI payload exceeds 66 bytes")
        header = _SPI_HEADER.pack(
            SPI_MAGIC, self.version, self.command & 0xFF, self.flags & 0xFF,
            self.transaction_id, len(self.payload),
        )
        body = header + self.payload
        return body + struct.pack(">H", crc16_ccitt_false(body))

    @classmethod
    def decode(cls, packet: bytes) -> "SpiPacket":
        if len(packet) < _SPI_HEADER.size + 2:
            raise ProtocolDecodeError(ErrorCode.BAD_LENGTH, "SPI packet too short")
        magic, version, command, flags, txid, payload_len = _SPI_HEADER.unpack_from(packet)
        if magic != SPI_MAGIC:
            raise ProtocolDecodeError(ErrorCode.BAD_MAGIC, f"magic 0x{magic:02X}")
        if version != PROTOCOL_VERSION:
            raise ProtocolDecodeError(ErrorCode.BAD_VERSION, f"version {version}")
        _check_flags(flags)
        if payload_len > SPI_MAX_PAYLOAD:
            raise ProtocolDecodeError(ErrorCode.BAD_LENGTH, "SPI payload exceeds 66 bytes")
        expected = _SPI_HEADER.size + payload_len + 2
        if len(packet) != expected:
            raise ProtocolDecodeError(ErrorCode.BAD_LENGTH, f"expected {expected}, got {len(packet)}")
        expected_crc = struct.unpack_from(">H", packet, len(packet) - 2)[0]
        if expected_crc != crc16_ccitt_false(packet[:-2]):
            raise ProtocolDecodeError(ErrorCode.BAD_CRC, "SPI packet CRC mismatch")
        return cls(command=command, flags=flags, transaction_id=txid,
                   payload=bytes(packet[_SPI_HEADER.size:-2]), version=version)

def request_fingerprint_crc32c(command: int, flags: int, payload: bytes) -> int:
    _check_flags(flags)
    if len(payload) > 0xFFFF:
        raise ValueError("payload too large for fingerprint")
    material = bytes((command & 0xFF, flags & 0xFF)) + len(payload).to_bytes(2, "big") + payload
    return crc32c(material)
