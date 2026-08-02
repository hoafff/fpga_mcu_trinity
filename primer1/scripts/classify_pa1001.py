#!/usr/bin/env python3
"""Classify Gowin PA1001 dangling-net warnings without suppressing them."""
from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

PATTERN = re.compile(
    r"WARN\s+\(PA1001\)\s*:\s*Dangling net '([^']+)'"
    r"\(source:'([^']+)'\) in module '([^']+)' has no destination"
)


def category(net: str, module: str) -> str:
    if module == "mlkem_poly_accel":
        if net.startswith(("SOA[", "SOB[", "DOUT[")):
            return "DSP_OPTIONAL_OUTPUT"
        if net.startswith("add_") or re.fullmatch(
            r"n(?:299|300|301|302|303|304|305|306)_\d+_SUM", net
        ):
            return "EXPLICITLY_TRUNCATED_ARITHMETIC_TAIL"
        return "UNKNOWN_MLKEM"
    if module in {"spi_packet_endpoint", "primer1_command_core"}:
        if re.fullmatch(r"n\d+_\d+_SUM", net):
            return "SYNTHESIZED_FIXED_WIDTH_SUM_TAIL"
        return "UNKNOWN_CONTROL"
    return "UNKNOWN_MODULE"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--require-known", action="store_true")
    args = parser.parse_args()

    text = args.log.read_text(encoding="utf-8", errors="replace")
    warnings = PATTERN.findall(text)
    by_module = Counter(module for _, _, module in warnings)
    by_category = Counter(category(net, module) for net, _, module in warnings)

    print(f"PA1001 total: {len(warnings)}")
    for module, count in sorted(by_module.items()):
        print(f"module {module}: {count}")
    for name, count in sorted(by_category.items()):
        print(f"category {name}: {count}")

    unknown = sum(count for name, count in by_category.items() if name.startswith("UNKNOWN"))
    print(f"unknown: {unknown}")
    if args.require_known and unknown:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
