#!/usr/bin/env python3
"""Generate deterministic vectors and run the Primer #1 RTL verification suite."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

Q = 3329
ZETAS = [
    -1044,-758,-359,-1517,1493,1422,287,202,-171,622,1577,182,962,-1202,-1474,1468,
    573,-1325,264,383,-829,1458,-1602,-130,-681,1017,732,608,-1542,411,-205,-1571,
    1223,652,-552,1015,-1293,1491,-282,-1544,516,-8,-320,-666,-1618,-1162,126,1469,
    -853,-90,-271,830,107,-1421,-247,-951,-398,961,-1508,-725,448,-1065,677,-1275,
    -1103,430,555,843,-1251,871,1550,105,422,587,177,-235,-291,-460,1574,1653,
    -246,778,1159,-147,-777,1483,-602,1119,-1590,644,-872,349,418,329,-156,-75,
    817,1097,603,610,1322,-1285,-1465,384,-1215,-136,1218,-1335,-874,220,-1187,-1659,
    -1185,-1530,-1278,794,-1510,-854,-870,478,-108,-308,996,991,958,-1460,1522,1628,
]


def i16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def montgomery_reduce(value: int) -> int:
    low = i16(i16(value) * -3327)
    return i16((value - low * Q) >> 16)


def fqmul(a: int, b: int) -> int:
    return montgomery_reduce(i16(a) * i16(b))


def barrett(value: int) -> int:
    value = i16(value)
    return i16(value - (((20159 * value + (1 << 25)) >> 26) * Q))


def ntt(poly: list[int]) -> list[int]:
    result = [i16(value) for value in poly]
    k = 1
    length = 128
    while length >= 2:
        for start in range(0, 256, 2 * length):
            zeta = ZETAS[k]
            k += 1
            for index in range(start, start + length):
                product = fqmul(zeta, result[index + length])
                result[index + length] = i16(result[index] - product)
                result[index] = i16(result[index] + product)
        length //= 2
    return result


def intt(poly: list[int]) -> list[int]:
    result = [i16(value) for value in poly]
    k = 127
    length = 2
    while length <= 128:
        for start in range(0, 256, 2 * length):
            zeta = ZETAS[k]
            k -= 1
            for index in range(start, start + length):
                saved = result[index]
                result[index] = barrett(i16(saved + result[index + length]))
                result[index + length] = fqmul(zeta, i16(result[index + length] - saved))
        length *= 2
    return [fqmul(value, 512) for value in result]


def basemul(a: list[int], b: list[int]) -> list[int]:
    result = [0] * 256
    for group in range(64):
        for offset, zeta in ((0, ZETAS[64 + group]), (2, -ZETAS[64 + group])):
            index = 4 * group + offset
            out0 = i16(
                fqmul(fqmul(a[index + 1], b[index + 1]), zeta)
                + fqmul(a[index], b[index])
            )
            out1 = i16(
                fqmul(a[index], b[index + 1])
                + fqmul(a[index + 1], b[index])
            )
            result[index] = fqmul(out0, 1353)
            result[index + 1] = fqmul(out1, 1353)
    return result


def write_hex(path: Path, values: list[int]) -> None:
    path.write_text("".join(f"{value & 0xFFFF:04x}\n" for value in values), encoding="ascii")


def generate_vectors(root: Path) -> None:
    generated = root / "tb/generated"
    generated.mkdir(parents=True, exist_ok=True)
    a = [(17 * i * i + 31 * i + 7) % Q for i in range(256)]
    b = [(29 * i * i + 11 * i + 19) % Q for i in range(256)]
    ntt_a = ntt(a)
    ntt_b = ntt(b)
    write_hex(generated / "ntt_input.hex", a)
    write_hex(generated / "ntt_expected.hex", ntt_a)
    write_hex(generated / "intt_input.hex", ntt_a)
    write_hex(generated / "intt_expected.hex", intt(ntt_a))
    write_hex(generated / "basemul_a.hex", ntt_a)
    write_hex(generated / "basemul_b.hex", ntt_b)
    write_hex(generated / "basemul_expected.hex", basemul(ntt_a, ntt_b))


def main() -> int:
    if not shutil.which("iverilog") or not shutil.which("vvp"):
        print("ERROR: iverilog and vvp are required", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]
    repo = root.parent
    generate_vectors(root)

    sources = [repo / line.strip() for line in (root / "sources.f").read_text().splitlines() if line.strip()]
    suite = root / "tb/primer1_rtl_verification_suite.sv"
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
            compile_cmd = [
                "iverilog", "-g2012", "-Wall", "-Wno-timescale",
                "-I", str(root / "rtl/core"), "-s", top, "-o", str(output),
                *(str(path) for path in sources), str(suite),
            ]
            print(f"\n=== COMPILE {top} ===")
            compiled = subprocess.run(compile_cmd, cwd=repo, text=True, capture_output=True)
            if compiled.stdout:
                print(compiled.stdout, end="")
            if compiled.stderr:
                print(compiled.stderr, end="", file=sys.stderr)
            if compiled.returncode:
                failures.append(f"{top}: compile")
                continue

            print(f"=== RUN {top} ===")
            simulated = subprocess.run(["vvp", str(output)], cwd=repo, text=True, capture_output=True)
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
