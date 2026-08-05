#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "sn32/src/app/trinity_deploy_main_part_14.inc"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    start = text.find("static void handle_get_first_spi_failure(")
    require(start >= 0, "missing first-SPI-failure handler")
    body = text[start:]

    compact_guard = "(uint32_t)payload_length + 12u > TRINITY_PC_MAX_PAYLOAD"
    detailed_guard = "(uint32_t)payload_length + 32u > TRINITY_PC_MAX_PAYLOAD"
    compact_length = (
        "g_pc_rsp.payload_length = (uint16_t)(payload_length + 12u);"
    )
    for token in (
        compact_guard,
        detailed_guard,
        compact_length,
        "trace->transfer_stage",
        "trace->transfer_direction",
        "trace->transfer_completed",
        "trace->spi_status",
    ):
        require(token in body, f"compact diagnostic fallback missing {token}")

    require(
        body.find(compact_guard) < body.find("trace->transfer_stage"),
        "mandatory 12-byte extension must be bounds-checked before writing",
    )
    require(
        body.find(detailed_guard) < body.find(compact_length),
        "detailed extension overflow must select the compact response",
    )
    require(
        body.find(compact_length) < body.find("trace->spi_ctrl0"),
        "compact response must return before optional register telemetry",
    )
    require(
        "serialize_spi_trace(trace,\n"
        "                             request_bytes,\n"
        "                             response_bytes,\n"
        "                             2u, &payload_length) ||\n"
        "        (uint32_t)payload_length + 32u" not in body,
        "large optional telemetry must not make GET_FIRST_SPI_FAILURE fail",
    )

    print("PASS: retained SPI diagnostics always preserve the compact extension")
    print("PASS: optional register/FIFO telemetry degrades without BAD_LENGTH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
