#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
IDENTITY = ROOT / "sn32/src/app/trinity_deploy_main_part_00.inc"
STARTUP = ROOT / "sn32/src/app/trinity_deploy_main_part_17.inc"
HOST = ROOT / "pc_host/src/trinity_host/serial_client.py"
PACKAGE = ROOT / "pc_host/pyproject.toml"
EVIDENCE = ROOT / "sn32/docs/STARTUP_PROBE_RECOVERY_V0_7_28.md"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def require_token(text: str, token: str, label: str) -> None:
    require(token in text, f"{label} missing {token}")


def main() -> int:
    config = read(CONFIG)
    identity = read(IDENTITY)
    startup = read(STARTUP)
    host = read(HOST)
    package = read(PACKAGE)
    evidence = read(EVIDENCE)
    evidence_words = " ".join(evidence.split())

    require(re.search(r"^#define\s+TRINITY_DEPLOY_VERSION_PATCH\s+30u$",
                      config, re.MULTILINE) is not None,
            "active deploy identity is not v0.7.30")
    require(re.search(r"^#define\s+DEPLOY_BUILD_ID\s+UINT32_C\(0x0007001E\)$",
                      identity, re.MULTILINE) is not None,
            "active deploy build ID is not 0x0007001E")
    require("EXPECTED_SN32_BUILD_ID = 0x0007001E" in host and
            "EXPECTED_SN32_VERSION = (0, 7, 30)" in host,
            "host identity is not v0.7.30 / 0x0007001E")
    require(re.search(r'^version = "0\.5\.1"$', package, re.MULTILINE) is not None,
            "host package is not 0.5.1")

    for token in (
        "TRINITY_DEPLOY_SPI_STARTUP_RECOVERY_MS    10000u",
        "TRINITY_DEPLOY_SPI_STARTUP_RECOVERY_BACKOFF_MS 250u",
    ):
        require_token(config, token, "startup recovery config")

    for token in (
        "startup_probe_error_is_retryable",
        "startup_recovery_wait",
        "startup_clear_recovered_transport_evidence",
        "startup_drain_and_probe_with_recovery",
        "SPI_TRACE_CONTEXT_STARTUP_DRAIN_P1",
        "SPI_TRACE_CONTEXT_STARTUP_DRAIN_P2",
        "SPI_TRACE_CONTEXT_STARTUP_PROBE",
        "spi_drain_startup_mailbox(&g_p1)",
        "spi_drain_startup_mailbox(&g_p2)",
        "rc = full_probe_all()",
        "expired(recovery_started",
        "TRINITY_DEPLOY_SPI_STARTUP_RECOVERY_MS",
        "startup_rc = startup_drain_and_probe_with_recovery()",
    ):
        require_token(startup, token, "startup recovery source")

    require("if (rc == TRINITY_OK) {\n            if (saw_retryable_failure)\n                startup_clear_recovered_transport_evidence();"
            in startup,
            "recovered evidence is not cleared only after complete probe success")
    require("memset(&g_spi_retained_trace, 0, sizeof(g_spi_retained_trace));"
            in startup and
            "g_spi_retained_failure = false;" in startup,
            "recovered transient evidence is not explicitly cleared")
    require("if (!startup_probe_error_is_retryable(rc) || g_fault ||"
            in startup,
            "non-retryable/safety failures are not fail-closed")
    require("return rc;" in startup,
            "persistent startup failure does not return without clearing evidence")

    for token in (
        "P1 and P2 `SPI_DIAGNOSTIC GET_INFO/GET_STATUS` exchanges pass",
        "`STARTUP_PROBE`, P1 `GET_INFO`",
        "`FRAME_TIMEOUT`",
        "ML-KEM KeyGen is correctly rejected with `BAD_STATE`",
        "do not execute or qualify the low-RAM KeyGen path",
    ):
        require_token(evidence_words, token, "hardware evidence")

    print("PASS: v0.7.30 retains the v0.7.28 startup recovery contract")
    print("PASS: complete drain/probe retries are bounded to 10 seconds")
    print("PASS: transient evidence clears only after full P1+P2 recovery")
    print("PASS: persistent and non-transport failures remain fail-closed")
    print("NOTE: source PASS is not exact-target build or hardware qualification PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
