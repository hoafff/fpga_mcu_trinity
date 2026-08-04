#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

IRAM_LIMIT = 8192
STACK_REQUIRED = 2048
G_CRYPTO_LIMIT = 3520
MIN_FREE_RAM = 256


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def require_match(pattern: str, text: str, label: str) -> re.Match[str]:
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        fail(f"map is missing {label}")
    return match


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the SN32F407 v0.7.27 low-RAM ML-KEM Keil map"
    )
    parser.add_argument("map_file", type=Path)
    args = parser.parse_args()

    if not args.map_file.is_file():
        fail(f"map file not found: {args.map_file}")
    text = args.map_file.read_text(encoding="utf-8", errors="replace")

    total_rw = int(
        require_match(
            r"Total RW\s+Size \(RW Data \+ ZI Data\)\s+(\d+)",
            text,
            "Total RW Size",
        ).group(1)
    )
    stack = int(
        require_match(
            r"^\s*STACK\s+0x[0-9A-Fa-f]+\s+Section\s+(\d+)\s+",
            text,
            "STACK symbol",
        ).group(1)
    )
    g_crypto = int(
        require_match(
            r"^\s*g_crypto\s+0x[0-9A-Fa-f]+\s+Data\s+(\d+)\s+",
            text,
            "g_crypto symbol",
        ).group(1)
    )
    region = require_match(
        r"Execution Region RW_IRAM1 .*?Size: 0x([0-9A-Fa-f]+), "
        r"Max: 0x([0-9A-Fa-f]+)",
        text,
        "RW_IRAM1 execution region",
    )
    region_size = int(region.group(1), 16)
    region_max = int(region.group(2), 16)

    if "g_host_low_ram_storage" in text:
        fail("target image contains the host-only 1792-byte fallback workspace")
    if stack != STACK_REQUIRED:
        fail(f"stack is {stack} bytes, expected {STACK_REQUIRED}")
    if g_crypto > G_CRYPTO_LIMIT:
        fail(f"g_crypto is {g_crypto} bytes, limit is {G_CRYPTO_LIMIT}")
    if total_rw > IRAM_LIMIT or region_size > region_max or region_max != IRAM_LIMIT:
        fail(
            f"IRAM overflow/profile mismatch: total_rw={total_rw}, "
            f"region={region_size}/{region_max}"
        )
    free_ram = IRAM_LIMIT - total_rw
    if free_ram < MIN_FREE_RAM:
        fail(f"RAM headroom is {free_ram} bytes, require at least {MIN_FREE_RAM}")

    print(f"PASS: Total RW {total_rw}/{IRAM_LIMIT} bytes")
    print(f"PASS: stack {stack} bytes")
    print(f"PASS: g_crypto {g_crypto}/{G_CRYPTO_LIMIT} bytes")
    print(f"PASS: RAM headroom {free_ram} bytes")
    print("PASS: host-only low-RAM fallback workspace absent")
    print("NOTE: map PASS is not flash, boot, KeyGen or hardware qualification PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
