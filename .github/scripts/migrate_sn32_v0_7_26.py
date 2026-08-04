#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

# Keep the reviewed migration body immutable at the commit that introduced it,
# then apply the one audited correction before execution.  The original source
# contains two valid braced `g_fault || !g_spi_selected` guards: one in the
# per-bit loop and one after CS assertion.  Both must gain the independent
# transport-phase check.
SOURCE_URL = (
    "https://raw.githubusercontent.com/hoafff/fpga_mcu_trinity/"
    "462698aad61fd848bb19c97aa42cdd3731f13002/"
    ".github/scripts/migrate_sn32_v0_7_26.py"
)

source = urlopen(SOURCE_URL, timeout=30).read().decode("utf-8")
old = '''for old, new in replacements:
    count = p06.count(old)
    if count != 1:
        raise SystemExit(
            f"{p06_path}: expected one occurrence, found {count}: {old!r}"
        )
    p06 = p06.replace(old, new, 1)
'''
new = '''for old, new in replacements:
    count = p06.count(old)
    expected = 2 if old == "if (g_fault || !g_spi_selected) {" else 1
    if count != expected:
        raise SystemExit(
            f"{p06_path}: expected {expected} occurrence(s), found {count}: {old!r}"
        )
    p06 = p06.replace(old, new, expected)
'''
if source.count(old) != 1:
    raise SystemExit("immutable migration source no longer matches audited patch")
source = source.replace(old, new, 1)

namespace = {
    "__name__": "__main__",
    "__file__": str(Path(__file__).resolve()),
}
exec(compile(source, str(Path(__file__).resolve()), "exec"), namespace)
