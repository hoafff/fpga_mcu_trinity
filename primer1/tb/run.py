#!/usr/bin/env python3
"""Generate deterministic vectors and run all Primer #1 RTL testbenches."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def load_reference(root: Path):
    path = root / "scripts/reference_checks.py"
    spec = importlib.util.spec_from_file_location("primer1_reference_checks", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_hex(path: Path, values: list[int]) -> None:
    path.write_text(
        "".join(f"{value & 0xFFFF:04x}\n" for value in values),
        encoding="ascii",
    )


def generate_vectors(root: Path) -> None:
    reference = load_reference(root)
    generated = root / "tb/generated"
    generated.mkdir(parents=True, exist_ok=True)

    vector_a = [(17 * index * index + 31 * index + 7) % reference.Q for index in range(256)]
    vector_b = [(29 * index * index + 11 * index + 19) % reference.Q for index in range(256)]
    ntt_a = reference.ntt(vector_a)
    ntt_b = reference.ntt(vector_b)

    write_hex(generated / "ntt_input.hex", vector_a)
    write_hex(generated / "ntt_expected.hex", ntt_a)
    write_hex(generated / "intt_input.hex", ntt_a)
    write_hex(generated / "intt_expected.hex", reference.intt_standard(ntt_a))
    write_hex(generated / "basemul_a.hex", ntt_a)
    write_hex(generated / "basemul_b.hex", ntt_b)
    write_hex(
        generated / "basemul_expected.hex",
        reference.basemul_standard(ntt_a, ntt_b),
    )


def main() -> int:
    if not shutil.which("iverilog") or not shutil.which("vvp"):
        print("ERROR: iverilog and vvp are required", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]
    repo = root.parent
    generate_vectors(root)

    sources = [
        root / line.strip()
        for line in (root / "sources.f").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tops = [
        "tb_mlkem_poly_accel",
        "tb_ascon_aead128_encrypt",
        "tb_spi_packet_endpoint",
        "tb_uart_tx_byte",
        "tb_uart_frame_tx",
        "tb_primer1_command_core",
        "tb_primer1_top",
    ]

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="primer1-rtl-sim-") as temp_dir:
        temp = Path(temp_dir)
        for top in tops:
            output = temp / f"{top}.vvp"
            compile_command = [
                "iverilog",
                "-g2012",
                "-Wall",
                "-Wno-timescale",
                "-I",
                str(root / "rtl/core"),
                "-s",
                top,
                "-o",
                str(output),
                *(str(path) for path in sources),
                str(root / "tb" / f"{top}.sv"),
            ]

            print(f"\n=== COMPILE {top} ===")
            compiled = subprocess.run(
                compile_command,
                cwd=repo,
                text=True,
                capture_output=True,
                check=False,
            )
            if compiled.stdout:
                print(compiled.stdout, end="")
            if compiled.stderr:
                print(compiled.stderr, end="", file=sys.stderr)
            if compiled.returncode:
                failures.append(f"{top}: compile")
                continue

            print(f"=== RUN {top} ===")
            simulated = subprocess.run(
                ["vvp", str(output)],
                cwd=repo,
                text=True,
                capture_output=True,
                check=False,
            )
            if simulated.stdout:
                print(simulated.stdout, end="")
            if simulated.stderr:
                print(simulated.stderr, end="", file=sys.stderr)
            if simulated.returncode:
                failures.append(f"{top}: simulation")

    if failures:
        print("\nRTL VERIFICATION FAIL")
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("\nRTL VERIFICATION PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
