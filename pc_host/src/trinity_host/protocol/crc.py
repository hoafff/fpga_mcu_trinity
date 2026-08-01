from __future__ import annotations

def crc16_ccitt_false(data: bytes | bytearray | memoryview, init: int = 0xFFFF) -> int:
    crc = init & 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
    return crc

def crc32c(data: bytes | bytearray | memoryview, init: int = 0xFFFFFFFF) -> int:
    crc = init & 0xFFFFFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ 0x82F63B78 if (crc & 1) else crc >> 1
    return crc ^ 0xFFFFFFFF
