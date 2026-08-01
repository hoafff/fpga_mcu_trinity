#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "sn32/keil/trinity_sn32f407_deploy.uvprojx"
S0_PROJECT = ROOT / "sn32/keil/trinity_sn32f407.uvprojx"
SOURCE = ROOT / "sn32/src/app/trinity_deploy_main.c"
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
BOARD = ROOT / "sn32/firmware/platform/sn32f407/board_profile.h"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def read(path: Path) -> str:
    require(path.is_file(), f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def main() -> int:
    project_text = read(PROJECT)
    source = read(SOURCE)
    config = read(CONFIG)
    board = read(BOARD)
    require(S0_PROJECT.is_file(), "canonical S0 project was removed")

    try:
        root = ET.fromstring(project_text)
    except ET.ParseError as exc:
        fail(f"invalid deploy project XML: {exc}")

    def one(xpath: str) -> str:
        node = root.find(xpath)
        require(node is not None and node.text is not None,
                f"missing XML field {xpath}")
        return node.text.strip()

    require(one("./Targets/Target/TargetName") == "trinity_sn32f407_deploy",
            "wrong deploy target name")
    require(one("./Targets/Target/pCCUsed") == "6240000::V6.24::ARMCLANG",
            "ArmClang 6.24 lock changed")
    require(one("./Targets/Target/TargetOption/TargetCommonOption/Device") ==
            "SN32F407F", "device lock changed")
    require(one("./Targets/Target/TargetOption/TargetCommonOption/PackID") ==
            "SONiX.SN32F4_DFP.1.0.1", "DFP lock changed")

    cpu = one("./Targets/Target/TargetOption/TargetCommonOption/Cpu")
    for token in ("IRAM(0x20000000,0x2000)",
                  "IROM(0x00000000,0x7FFC)",
                  'CPUTYPE("Cortex-M0")', "CLOCK(12000000)"):
        require(token in cpu, f"memory/CPU lock missing {token}")

    common = "./Targets/Target/TargetOption/TargetCommonOption/"
    for field in ("CreateExecutable", "CreateHexFile", "DebugInformation"):
        require(one(common + field) == "1", f"{field} is not enabled")
    arm = "./Targets/Target/TargetOption/TargetArmAds/ArmAdsMisc/"
    for field in ("ldXref", "AdsLmap", "AdsLcgr"):
        require(one(arm + field) == "1", f"{field} is not enabled")

    define = one("./Targets/Target/TargetOption/TargetArmAds/Cads/VariousControls/Define")
    require(define == "TRINITY_DEPLOY_TARGET=1", "deploy define drifted")

    packages = {(n.get("vendor"), n.get("name")): n.get("version")
                for n in root.findall("./RTE/components/component/package")}
    require(packages.get(("ARM", "CMSIS")) == "6.2.0",
            "CMSIS pack is not 6.2.0")
    require(packages.get(("SONiX", "SN32F4_DFP")) == "1.0.1",
            "SONiX DFP is not 1.0.1")
    core = root.find("./RTE/components/component[@Cclass='CMSIS']")
    require(core is not None and core.get("Cversion") == "6.1.1",
            "CMSIS CORE is not 6.1.1")

    paths = [(n.text or "").replace("\\", "/").lower()
             for n in root.findall(".//FilePath")]
    expected_c = {
        "../src/app/trinity_deploy_main.c",
        "../firmware/platform/sn32f407/fpst_sn32f407_p010_guard.c",
        "../src/trinity_protocol_common.c",
        "../src/trinity_pc_protocol.c",
        "../src/trinity_spi_protocol.c",
    }
    require({p for p in paths if p.endswith(".c")} == expected_c,
            "unexpected deploy C source set")
    for name in ("trinity_main.c", "fpst_sn32f407_dual_main.c",
                 "fpst_sn32f407_main.c", "fpst_sn32f407_port.c",
                 "pair_bridge", "mlkem", "telemetry", "session.c"):
        require(all(name not in p for p in paths),
                f"forbidden source in deploy target: {name}")

    flags = {
        "TRINITY_DEPLOY_ENABLE_PC_UART": "1",
        "TRINITY_DEPLOY_ENABLE_SPI": "1",
        "TRINITY_DEPLOY_ENABLE_PRIMER1": "1",
        "TRINITY_DEPLOY_ENABLE_PRIMER2": "1",
        "TRINITY_DEPLOY_ENABLE_MLKEM": "0",
        "TRINITY_DEPLOY_ENABLE_PAYLOAD_RELAY": "0",
        "TRINITY_DEPLOY_ENABLE_TINY_SESSION_COMMIT": "0",
        "TRINITY_DEPLOY_ENABLE_DEMO_SECURE": "0",
    }
    for macro, value in flags.items():
        require(re.search(rf"^#define\s+{macro}\s+{value}\s*$",
                          config, re.M) is not None,
                f"wrong deploy guard {macro}")

    for token in ("SystemInit();", "SystemCoreClockUpdate();", "SysTick_Config(",
                  "SN_UART0->CTRL", "SN_SPI0->CTRL0_b.SPIEN", "expired(",
                  "TRINITY_PC_PING", "TRINITY_PC_GET_SYSTEM_INFO",
                  "TRINITY_PC_GET_SYSTEM_STATUS", "TRINITY_SPI_GET_INFO",
                  "TRINITY_SPI_GET_STATUS", "cs_all_high();",
                  "fpst_sn32f407_p010_guard_apply"):
        require(token in source, f"deploy source missing {token}")
    for token in ('#include "trinity_mlkem', "fpst_pair_bridge",
                  "fpst_mlkem", "fpst_session", "fpst_telemetry"):
        require(token not in source, f"disabled feature leaked into source: {token}")

    for token in ("FPST_SN32F407_UART_TX_PIN               1u",
                  "FPST_SN32F407_UART_RX_PIN               2u",
                  "FPST_SN32F407_P1_CS_N_PIN              1u",
                  "FPST_SN32F407_P2_CS_N_PIN              2u",
                  "FPST_SN32F407_P1_IRQ_N_PIN              3u",
                  "FPST_SN32F407_P2_IRQ_N_PIN              8u"):
        require(token in board, f"board profile pin drift: {token}")

    absolute = re.compile(r"(?:^|[>\s])(?:[A-Za-z]:\\|[A-Za-z]:/)")
    require(absolute.search(project_text) is None,
            "absolute Windows path in deploy project")
    require(".uvguix" not in project_text.lower(), "user GUI state in project")

    print("PASS: deploy XML locks SN32F407F, ArmClang 6.24, CMSIS 6.2.0/CORE 6.1.1 and DFP 1.0.1")
    print("PASS: deploy target contains UART/SPI/P0.10 guard and only current Trinity protocol sources")
    print("PASS: ML-KEM, Tiny session commit, DEMO_SECURE and MCU payload relay remain disabled")
    print("NOTE: static checks and host syntax checks do not replace the authoritative ArmClang build log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
