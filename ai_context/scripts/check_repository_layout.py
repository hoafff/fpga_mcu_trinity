#!/usr/bin/env python3
"""Fail closed when fpga_mcu_trinity drifts back to the legacy tree."""

from __future__ import annotations

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
TARGETS = ("pc_host", "sn32", "primer1", "primer2", "tiny1p5")
ALLOWED_ROOT = {
    ".git",
    ".gitignore",
    "LICENSE",
    "README.md",
    "ai_context",
    *TARGETS,
}
FORBIDDEN_ROOT = {
    ".github",
    "boards",
    "build",
    "constraints",
    "docs",
    "rtl",
    "scripts",
    "software",
    "targets",
    "tb",
    "tools",
}
FORBIDDEN_TARGET_NAMES = {"README.md", "README", "CONTRIBUTING.md"}
FORBIDDEN_SUFFIXES = {
    ".axf",
    ".bin",
    ".bit",
    ".fs",
    ".hex",
    ".log",
    ".rpt",
    ".zip",
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []
    root_entries = {path.name for path in ROOT.iterdir()}

    for name in sorted(root_entries - ALLOWED_ROOT):
        fail(errors, f"unexpected root entry: {name}")
    for name in sorted(FORBIDDEN_ROOT & root_entries):
        fail(errors, f"legacy root is forbidden: {name}/")

    for required in ("README.md", ".gitignore", "LICENSE", "ai_context", *TARGETS):
        if not (ROOT / required).exists():
            fail(errors, f"missing required root entry: {required}")

    for target in TARGETS:
        target_root = ROOT / target
        manifest = target_root / "target.toml"
        if not manifest.is_file():
            fail(errors, f"missing target manifest: {target}/target.toml")

        for path in target_root.rglob("*"):
            if path.is_symlink():
                fail(errors, f"symlink is forbidden in target: {path.relative_to(ROOT)}")
            if path.is_file() and path.name in FORBIDDEN_TARGET_NAMES:
                fail(errors, f"target documentation is forbidden: {path.relative_to(ROOT)}")
            if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
                fail(errors, f"generated/artifact file is forbidden: {path.relative_to(ROOT)}")
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="ignore")
                if "../ai_context" in text or "..\\ai_context" in text:
                    fail(errors, f"target depends on ai_context: {path.relative_to(ROOT)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("PASS: canonical six-folder project layout")
    print("PASS: no legacy root/source tree")
    print("PASS: target manifests are self-contained")
    print("PASS: no forbidden build artifacts in targets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
