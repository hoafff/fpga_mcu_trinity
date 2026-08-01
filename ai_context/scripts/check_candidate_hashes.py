#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "ai_context/evidence/P0-J19-001/MIGRATED_FILE_SHA256SUMS.txt"

errors: list[str] = []
count = 0
for raw in MANIFEST.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    expected, relative = line.split(maxsplit=1)
    path = ROOT / relative
    count += 1
    if not path.is_file():
        errors.append(f"missing: {relative}")
        continue
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        errors.append(f"hash mismatch: {relative}: {actual} != {expected}")

if count != 29:
    errors.append(f"manifest must contain exactly 29 files, found {count}")
if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(1)
print("PASS: all 29 P0-J19-001 candidate files match accepted SHA-256 values")
