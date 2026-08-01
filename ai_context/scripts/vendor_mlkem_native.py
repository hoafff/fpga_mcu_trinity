#!/usr/bin/env python3
"""Import the minimal portable-C mlkem-native dependency closure.

The importer downloads one immutable GitHub archive, optionally runs upstream's
ML-KEM-512 KAT, resolves quoted includes from the portable C translation units,
and writes only the required files under the SN32 target.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / "sn32/third_party/mlkem-native/VENDOR.lock"
DEST_ROOT = ROOT / "sn32/third_party/mlkem-native"
UPSTREAM_DEST = DEST_ROOT / "upstream"
MANIFEST_PATH = DEST_ROOT / "UPSTREAM_MANIFEST.json"
NOTES_PATH = DEST_ROOT / "VENDOR_NOTES.txt"
INCLUDE_RE = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.MULTILINE)


def parse_lock(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            raise ValueError(f"invalid lock line: {raw}")
        values[key.strip()] = value.strip()
    required = {"repository", "tag", "commit", "archive_sha256"}
    missing = required - values.keys()
    if missing:
        raise ValueError(f"missing lock keys: {sorted(missing)}")
    if len(values["commit"]) != 40:
        raise ValueError("commit must be a full 40-hex SHA")
    return values


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "fpga-mcu-trinity-vendor-import/1"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def safe_extract_tar(data: bytes, destination: Path) -> Path:
    """Extract regular files/directories only; ignore archive links.

    The upstream repository may contain convenience symlinks in examples. They
    are not needed by the portable source closure and must not be materialized by
    this importer.
    """
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        members = archive.getmembers()
        roots = {PurePosixPath(member.name).parts[0] for member in members if member.name}
        if len(roots) != 1:
            raise ValueError(f"archive must have one root, got {sorted(roots)}")
        destination_resolved = destination.resolve()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if member.name.startswith("/") or ".." in parts:
                raise ValueError(f"unsafe archive member: {member.name}")
            target = (destination / Path(*parts)).resolve()
            try:
                target.relative_to(destination_resolved)
            except ValueError as exc:
                raise ValueError(f"archive member escapes destination: {member.name}") from exc
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"cannot read archive member: {member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as output:
                shutil.copyfileobj(source, output)
            os.chmod(target, member.mode & 0o777)
    return destination / next(iter(roots))


def resolve_include(source_root: Path, current: Path, include: str) -> Path | None:
    candidates = (
        current.parent / include,
        source_root / "mlkem" / include,
        source_root / "mlkem/src" / include,
        source_root / "mlkem/src/fips202" / include,
    )
    for candidate in candidates:
        candidate = candidate.resolve()
        try:
            candidate.relative_to(source_root.resolve())
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    return None


def dependency_closure(source_root: Path) -> list[Path]:
    seeds = [source_root / "mlkem/mlkem_native.h"]
    seeds.extend(sorted((source_root / "mlkem/src").glob("*.c")))
    seeds.extend(sorted((source_root / "mlkem/src/fips202").glob("*.c")))
    pending = list(seeds)
    selected: set[Path] = set()
    unresolved: set[tuple[str, str]] = set()

    while pending:
        current = pending.pop().resolve()
        if current in selected:
            continue
        if not current.is_file():
            raise FileNotFoundError(current)
        selected.add(current)
        text = current.read_text(encoding="utf-8")
        for include in INCLUDE_RE.findall(text):
            resolved = resolve_include(source_root, current, include)
            if resolved is None:
                unresolved.add((str(current.relative_to(source_root)), include))
            elif resolved not in selected:
                pending.append(resolved)

    if unresolved:
        details = "\n".join(f"{path}: {include}" for path, include in sorted(unresolved))
        raise ValueError(f"unresolved quoted includes:\n{details}")
    return sorted(selected)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_selected(source_root: Path, selected: list[Path], lock: dict[str, str]) -> None:
    staging = DEST_ROOT / ".upstream-staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    copied: list[dict[str, object]] = []
    for source in selected:
        relative = source.relative_to(source_root)
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied.append(
            {
                "path": relative.as_posix(),
                "size": target.stat().st_size,
                "sha256": sha256_file(target),
            }
        )

    for extra in ("LICENSE", "RELEASE.md", "REFERENCE.md"):
        source = source_root / extra
        if source.is_file():
            target = staging / extra
            shutil.copyfile(source, target)
            copied.append(
                {"path": extra, "size": target.stat().st_size, "sha256": sha256_file(target)}
            )

    shutil.rmtree(UPSTREAM_DEST, ignore_errors=True)
    staging.rename(UPSTREAM_DEST)

    manifest = {
        "schema_version": 1,
        "repository": lock["repository"],
        "tag": lock["tag"],
        "commit": lock["commit"],
        "archive_sha256": lock["archive_sha256"],
        "profile": "ML-KEM-512 portable C plus upstream FIPS-202",
        "selection": "recursive quoted-include closure from mlkem/src/*.c, mlkem/src/fips202/*.c and mlkem_native.h",
        "files": sorted(copied, key=lambda item: str(item["path"])),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    NOTES_PATH.write_text(
        "Vendored mlkem-native subset\n\n"
        f"Pinned upstream: {lock['tag']} / {lock['commit']}.\n\n"
        "upstream/ is generated by ai_context/scripts/vendor_mlkem_native.py. "
        "Do not edit imported files. The selection contains the portable C ML-KEM "
        "translation units, upstream FIPS-202, their recursive quoted-header closure, "
        "and upstream license/reference records. Native assembly backends and unrelated "
        "repository material are not imported.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-upstream-kat", action="store_true")
    args = parser.parse_args()
    lock = parse_lock(LOCK_PATH)
    archive_url = f"{lock['repository']}/archive/{lock['commit']}.tar.gz"
    archive = download(archive_url)
    actual_hash = hashlib.sha256(archive).hexdigest()
    expected_hash = lock["archive_sha256"]
    if expected_hash != "PENDING_FIRST_IMPORT" and actual_hash != expected_hash:
        raise ValueError(f"archive SHA-256 mismatch: {actual_hash} != {expected_hash}")
    lock["archive_sha256"] = actual_hash

    with tempfile.TemporaryDirectory(prefix="trinity-mlkem-") as temp_dir:
        source_root = safe_extract_tar(archive, Path(temp_dir))
        if args.verify_upstream_kat:
            subprocess.run(
                ["make", "run_kat_512", "OPT=0"],
                cwd=source_root,
                check=True,
            )
        selected = dependency_closure(source_root)
        copy_selected(source_root, selected, lock)

    if expected_hash == "PENDING_FIRST_IMPORT":
        text = LOCK_PATH.read_text(encoding="utf-8")
        LOCK_PATH.write_text(
            text.replace("archive_sha256=PENDING_FIRST_IMPORT", f"archive_sha256={actual_hash}"),
            encoding="utf-8",
        )
    print(f"Imported {len(selected)} upstream files at {lock['commit']}")
    print(f"Archive SHA-256: {actual_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
