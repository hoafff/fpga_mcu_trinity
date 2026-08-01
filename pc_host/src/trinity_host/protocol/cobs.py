from __future__ import annotations

class CobsDecodeError(ValueError):
    pass

def cobs_encode(data: bytes | bytearray | memoryview) -> bytes:
    out = bytearray(b"\x00")
    code_index = 0
    code = 1
    for value in data:
        if value == 0:
            out[code_index] = code
            code_index = len(out)
            out.append(0)
            code = 1
        else:
            out.append(value)
            code += 1
            if code == 0xFF:
                out[code_index] = code
                code_index = len(out)
                out.append(0)
                code = 1
    out[code_index] = code
    return bytes(out)

def cobs_decode(data: bytes | bytearray | memoryview) -> bytes:
    if not data:
        raise CobsDecodeError("empty COBS frame")
    if 0 in data:
        raise CobsDecodeError("encoded COBS frame contains zero")
    out = bytearray()
    index = 0
    n = len(data)
    while index < n:
        code = data[index]
        if code == 0:
            raise CobsDecodeError("zero code")
        index += 1
        count = code - 1
        if index + count > n:
            raise CobsDecodeError("COBS block exceeds input")
        out.extend(data[index:index + count])
        index += count
        if code != 0xFF and index < n:
            out.append(0)
    return bytes(out)
