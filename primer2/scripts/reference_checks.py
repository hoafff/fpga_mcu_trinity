#!/usr/bin/env python3
"""Byte-exact Ascon-AEAD128 reference matching Primer #1 RTL ordering."""
from __future__ import annotations

MASK64 = (1 << 64) - 1
RC = [0xF0, 0xE1, 0xD2, 0xC3, 0xB4, 0xA5, 0x96, 0x87, 0x78, 0x69, 0x5A, 0x4B]
IV = 0x00001000808C0001


def ror(x: int, n: int) -> int:
    return ((x >> n) | ((x << (64 - n)) & MASK64)) & MASK64


def round_fn(s: tuple[int, int, int, int, int], rc: int) -> tuple[int, int, int, int, int]:
    a0, a1, a2, a3, a4 = s
    a2 ^= rc
    a0 ^= a4
    a4 ^= a3
    a2 ^= a1
    t0 = a0 ^ ((~a1 & MASK64) & a2)
    t1 = a1 ^ ((~a2 & MASK64) & a3)
    t2 = a2 ^ ((~a3 & MASK64) & a4)
    t3 = a3 ^ ((~a4 & MASK64) & a0)
    t4 = a4 ^ ((~a0 & MASK64) & a1)
    t1 ^= t0
    t0 ^= t4
    t3 ^= t2
    t2 = ~t2 & MASK64
    return (
        (t0 ^ ror(t0, 19) ^ ror(t0, 28)) & MASK64,
        (t1 ^ ror(t1, 61) ^ ror(t1, 39)) & MASK64,
        (t2 ^ ror(t2, 1) ^ ror(t2, 6)) & MASK64,
        (t3 ^ ror(t3, 10) ^ ror(t3, 17)) & MASK64,
        (t4 ^ ror(t4, 7) ^ ror(t4, 41)) & MASK64,
    )


def permute(s: tuple[int, int, int, int, int], first_round: int) -> tuple[int, int, int, int, int]:
    for rc in RC[first_round:]:
        s = round_fn(s, rc)
    return s


def words_le(data: bytes) -> list[int]:
    assert len(data) % 8 == 0
    return [int.from_bytes(data[i:i+8], "little") for i in range(0, len(data), 8)]


def ascon_encrypt(key: bytes, nonce: bytes, ad: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    assert len(key) == len(nonce) == 16
    assert len(ad) == len(plaintext) == 24
    k0, k1 = words_le(key)
    n0, n1 = words_le(nonce)
    a0, a1, a2 = words_le(ad)
    p0, p1, p2 = words_le(plaintext)
    x0, x1, x2, x3, x4 = permute((IV, k0, k1, n0, n1), 0)
    x3 ^= k0
    x4 ^= k1
    x0 ^= a0
    x1 ^= a1
    x0, x1, x2, x3, x4 = permute((x0, x1, x2, x3, x4), 4)
    x0 ^= a2
    x1 ^= 1
    x0, x1, x2, x3, x4 = permute((x0, x1, x2, x3, x4), 4)
    x4 ^= 0x8000000000000000
    x0 ^= p0
    x1 ^= p1
    c0, c1 = x0, x1
    x0, x1, x2, x3, x4 = permute((x0, x1, x2, x3, x4), 4)
    c2 = x0 ^ p2
    x0 ^= p2
    x1 ^= 1
    x2 ^= k0
    x3 ^= k1
    x0, x1, x2, x3, x4 = permute((x0, x1, x2, x3, x4), 0)
    tag = (x3 ^ k0).to_bytes(8, "little") + (x4 ^ k1).to_bytes(8, "little")
    ciphertext = c0.to_bytes(8, "little") + c1.to_bytes(8, "little") + c2.to_bytes(8, "little")
    return ciphertext, tag


def ascon_decrypt(key: bytes, nonce: bytes, ad: bytes, ciphertext: bytes, tag: bytes) -> tuple[bytes, bool]:
    assert len(key) == len(nonce) == len(tag) == 16
    assert len(ad) == len(ciphertext) == 24
    k0, k1 = words_le(key)
    n0, n1 = words_le(nonce)
    a0, a1, a2 = words_le(ad)
    c0, c1, c2 = words_le(ciphertext)
    x0, x1, x2, x3, x4 = permute((IV, k0, k1, n0, n1), 0)
    x3 ^= k0
    x4 ^= k1
    x0 ^= a0
    x1 ^= a1
    x0, x1, x2, x3, x4 = permute((x0, x1, x2, x3, x4), 4)
    x0 ^= a2
    x1 ^= 1
    x0, x1, x2, x3, x4 = permute((x0, x1, x2, x3, x4), 4)
    x4 ^= 0x8000000000000000
    p0, p1 = x0 ^ c0, x1 ^ c1
    x0, x1 = c0, c1
    x0, x1, x2, x3, x4 = permute((x0, x1, x2, x3, x4), 4)
    p2 = x0 ^ c2
    x0 = c2
    x1 ^= 1
    x2 ^= k0
    x3 ^= k1
    x0, x1, x2, x3, x4 = permute((x0, x1, x2, x3, x4), 0)
    expected = (x3 ^ k0).to_bytes(8, "little") + (x4 ^ k1).to_bytes(8, "little")
    plaintext = p0.to_bytes(8, "little") + p1.to_bytes(8, "little") + p2.to_bytes(8, "little")
    return plaintext, expected == tag


def make_ad(session_id: int, sequence: int, message_type: int = 2, flags: int = 0x1234, source_id: int = 0x3344) -> bytes:
    return bytes([
        1,
        message_type,
        (flags >> 8) & 0xFF,
        flags & 0xFF,
        (session_id >> 24) & 0xFF,
        (session_id >> 16) & 0xFF,
        (session_id >> 8) & 0xFF,
        session_id & 0xFF,
    ]) + sequence.to_bytes(8, "big") + b"\x00\x18" + source_id.to_bytes(2, "big") + b"\x00" * 4


def make_nonce(prefix: bytes, sequence: int) -> bytes:
    assert len(prefix) == 8
    return prefix + sequence.to_bytes(8, "big")


def self_test() -> None:
    kat_ct, kat_tag = ascon_encrypt(bytes(16), bytes(16), bytes(24), bytes(24))
    print("KAT_CT", kat_ct.hex().upper())
    print("KAT_TAG", kat_tag.hex().upper())
    plain, ok = ascon_decrypt(bytes(16), bytes(16), bytes(24), kat_ct, kat_tag)
    assert ok and plain == bytes(24)

    key = bytes.fromhex("00112233445566778899AABBCCDDEEFF")
    prefix = bytes.fromhex("1021324354657687")
    ad = make_ad(0x11223344, 1)
    plaintext = bytes.fromhex("0102030405060708090A0B0C0D0E0F101112131415161700")
    ciphertext, tag = ascon_encrypt(key, make_nonce(prefix, 1), ad, plaintext)
    recovered, ok = ascon_decrypt(key, make_nonce(prefix, 1), ad, ciphertext, tag)
    assert ok and recovered == plaintext
    for index in range(len(ad)):
        corrupt = bytearray(ad)
        corrupt[index] ^= 1
        _, accepted = ascon_decrypt(key, make_nonce(prefix, 1), bytes(corrupt), ciphertext, tag)
        assert not accepted
    for index in range(len(ciphertext)):
        corrupt = bytearray(ciphertext)
        corrupt[index] ^= 1
        _, accepted = ascon_decrypt(key, make_nonce(prefix, 1), ad, bytes(corrupt), tag)
        assert not accepted
    for index in range(len(tag)):
        corrupt = bytearray(tag)
        corrupt[index] ^= 1
        _, accepted = ascon_decrypt(key, make_nonce(prefix, 1), ad, ciphertext, bytes(corrupt))
        assert not accepted

    _, accepted = ascon_decrypt(bytes(16), make_nonce(prefix, 1), ad, ciphertext, tag)
    assert not accepted
    _, accepted = ascon_decrypt(key, bytes(16), ad, ciphertext, tag)
    assert not accepted
    # Official NIST SP 800-232 Count 817 vector used by the qualified P1 sender.
    official_ct, official_tag = ascon_encrypt(
        bytes(range(0x00, 0x10)), bytes(range(0x10, 0x20)),
        bytes(range(0x30, 0x48)), bytes(range(0x20, 0x38)))
    assert (official_ct + official_tag).hex() == (
        "9d29f9d52adf9470af4cbce0a4481ac7fcb1b32976469892"
        "dfebaf445205ec9b019d022c7042ae59")
    body = ad + ciphertext + tag
    assert len(body) == 64 and len(b"\xA5\x5A" + body) == 66
    assert int.from_bytes(ad[4:8], "big") == 0x11223344
    assert int.from_bytes(ad[8:16], "big") == 1
    assert ad[16:18] == b"\x00\x18" and ad[20:24] == bytes(4)
    print("PASS ascon_zero_and_nonzero_decrypt")
    print("PASS ad_ciphertext_tag_bit_flip_rejection")
    print("PASS wrong_key_and_nonce_rejection")
    print("PASS official_count817_sender_compatibility")
    print("PASS uart_frame_layout_66_bytes")


if __name__ == "__main__":
    self_test()
    key = bytes.fromhex("00112233445566778899AABBCCDDEEFF")
    prefix = bytes.fromhex("1021324354657687")
    ad = make_ad(0x11223344, 1)
    plaintext = bytes.fromhex("0102030405060708090A0B0C0D0E0F101112131415161700")
    ciphertext, tag = ascon_encrypt(key, make_nonce(prefix, 1), ad, plaintext)
    print("AD=" + ad.hex().upper())
    print("PT=" + plaintext.hex().upper())
    print("CT=" + ciphertext.hex().upper())
    print("TAG=" + tag.hex().upper())
    print("FRAME=A55A" + ad.hex().upper() + ciphertext.hex().upper() + tag.hex().upper())
