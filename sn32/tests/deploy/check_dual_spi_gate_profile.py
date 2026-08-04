#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "sn32/config/trinity_deploy_config.h"
PART00 = ROOT / "sn32/src/app/trinity_deploy_main_part_00.inc"
PART01 = ROOT / "sn32/src/app/trinity_deploy_main_part_01.inc"
PART02 = ROOT / "sn32/src/app/trinity_deploy_main_part_02.inc"
PART04 = ROOT / "sn32/src/app/trinity_deploy_main_part_04.inc"
PART05 = ROOT / "sn32/src/app/trinity_deploy_main_part_05.inc"
PART06 = ROOT / "sn32/src/app/trinity_deploy_main_part_06.inc"
PART07 = ROOT / "sn32/src/app/trinity_deploy_main_part_07.inc"
PART08 = ROOT / "sn32/src/app/trinity_deploy_main_part_08.inc"
PART12 = ROOT / "sn32/src/app/trinity_deploy_main_part_12.inc"
PART14 = ROOT / "sn32/src/app/trinity_deploy_main_part_14.inc"
PART15 = ROOT / "sn32/src/app/trinity_deploy_main_part_15.inc"
PART16 = ROOT / "sn32/src/app/trinity_deploy_main_part_16.inc"
PART17 = ROOT / "sn32/src/app/trinity_deploy_main_part_17.inc"
CONTROLLER_PART00 = ROOT / "sn32/src/app/trinity_full_controller_part_00.inc"
CONTROLLER_PART03 = ROOT / "sn32/src/app/trinity_full_controller_part_03.inc"
CONTROLLER_PART07 = ROOT / "sn32/src/app/trinity_full_controller_part_07.inc"
SPI_PROTOCOL = ROOT / "sn32/src/trinity_spi_protocol.c"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(text: str, token: str, label: str) -> None:
    if token not in text:
        fail(f"{label} missing {token}")


def forbid(text: str, token: str, label: str) -> None:
    if token in text:
        fail(f"{label} contains forbidden token {token}")


def macro(text: str, name: str) -> int:
    match = re.search(
        rf"^#define\s+{re.escape(name)}\s+(0x[0-9A-Fa-f]+|\d+)u?\s*$",
        text,
        re.M,
    )
    if match is None:
        fail(f"missing numeric macro {name}")
    return int(match.group(1), 0)


def section(text: str, start: str, end: str, label: str) -> str:
    first = text.find(start)
    last = text.find(end, first + len(start))
    if first < 0 or last < 0:
        fail(f"cannot isolate {label}")
    return text[first:last]


def main() -> int:
    config = read(CONFIG)
    p00 = read(PART00)
    p01 = read(PART01)
    p02 = read(PART02)
    p04 = read(PART04)
    p05 = read(PART05)
    p06 = read(PART06)
    p07 = read(PART07)
    p08 = read(PART08)
    p12 = read(PART12)
    p14 = read(PART14)
    p15 = read(PART15)
    p16 = read(PART16)
    p17 = read(PART17)
    controller00 = read(CONTROLLER_PART00)
    controller03 = read(CONTROLLER_PART03)
    controller07 = read(CONTROLLER_PART07)
    spi_protocol = read(SPI_PROTOCOL)

    version = (
        macro(config, "TRINITY_DEPLOY_VERSION_MAJOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_MINOR"),
        macro(config, "TRINITY_DEPLOY_VERSION_PATCH"),
    )
    if version != (0, 7, 26):
        fail(f"UART-live GPIO-SPI image must be v0.7.26, got {version}")
    if macro(config, "TRINITY_DEPLOY_SPI_HZ") != 100_000:
        fail("qualification SPI ceiling must remain 100 kHz")
    if macro(config, "TRINITY_DEPLOY_SPI_SOFTWARE_BACKEND") != 1:
        fail("deploy image must select the GPIO SPI backend")
    if macro(config, "TRINITY_DEPLOY_SPI_HALF_PERIOD_CYCLES") < 60:
        fail("GPIO SPI half-period must not exceed the 100 kHz ceiling")
    if macro(config, "TRINITY_DEPLOY_SPI_CS_GUARD_US") != 200:
        fail("v0.7.26 must retain the 200 us CS guard")
    if macro(config, "TRINITY_DEPLOY_PC_QUIET_BEFORE_PROBE_MS") != 250:
        fail("automatic probe must require a 250 ms quiet PC window")
    if macro(config, "TRINITY_DEPLOY_SPI_READ_REISSUE_MAX") != 2:
        fail("read-only recovery must permit exactly two bounded reissues")
    if macro(config, "TRINITY_DEPLOY_SPI_READ_RETRY_BACKOFF_MS") != 20:
        fail("read-only recovery backoff must remain 20 ms")
    require(p00, "#define DEPLOY_BUILD_ID UINT32_C(0x0007001A)", "identity")
    require(
        p00,
        "#if TRINITY_DEPLOY_SPI_SOFTWARE_BACKEND != 1",
        "GPIO SPI backend contract",
    )
    require(p00, "SPI_TRACE_BACKEND_GPIO_MODE0", "GPIO SPI trace identity")

    for token in (
        "static bool g_pc_service_enabled;",
        "static bool g_pc_poll_active;",
        "static bool g_pc_frame_pending;",
        "static bool g_automatic_probe_active;",
        "static uint32_t g_pc_last_activity_ms;",
        "static spi_exchange_trace_t g_spi_trace;",
        "static spi_retained_trace_t g_spi_retained_trace;",
        "static bool g_spi_retained_failure;",
        "static bool g_spi_retained_startup_residue;",
    ):
        require(p01, token, "runtime state")
    for token in ("g_spi_trace_slots", "g_spi_trace_work",
                  "*g_spi_retained_trace"):
        forbid(p01, token, "immutable retained trace state")

    for token in (
        "static uint8_t g_pc_raw[TRINITY_PC_MAX_RAW_FRAME];",
        "static uint8_t g_spi_request_wire[TRINITY_SPI_MAX_PACKET];",
        "static uint8_t g_spi_response_wire[TRINITY_SPI_MAX_PACKET];",
        "static trinity_spi_packet_t g_spi_req;",
        "static trinity_spi_packet_t g_spi_rsp;",
    ):
        require(p02, token, "disjoint transport storage")
    forbid(p02, "g_transport_scratch", "disjoint transport storage")

    progress_body = section(
        p04,
        "static void progress(void)",
        "static void crypto_progress_lease_begin(void)",
        "progress body",
    )
    for token in (
        "static void pc_receive(void);",
        "static void pc_poll(void);",
        "if (g_pc_service_enabled && !g_pc_poll_active)",
        "pc_receive();",
    ):
        require(p04, token, "deferred PC service")
    forbid(progress_body, "pc_poll();", "progress body")
    forbid(progress_body, "handle_request", "progress body")

    for token in (
        "SN_SPI0->CTRL0_b.SPIEN = 0u;",
        "SN_PFPA->SPI0 = 0u;",
        "FPST_SN32F407_SPI_SCK_PIN, true",
        "FPST_SN32F407_SPI_MOSI_PIN, true",
        "FPST_SN32F407_SPI_MISO_PIN, false",
    ):
        require(p05, token, "GPIO SPI init")
    forbid(p05, "SN_SPI0->CTRL0_b.SPIEN = 1u;", "disabled SPI0 backend")

    request_tx = section(
        p06,
        "static trinity_error_code_t spi_write_request_bytes(",
        "static trinity_error_code_t spi_read_response_segment(",
        "request TX",
    )
    for token in (
        "soft_spi_transfer_byte(tx[i], &ignored)",
        "g_spi_trace.transfer_completed = (uint16_t)(i + 1u);",
    ):
        require(request_tx, token, "GPIO request TX")

    response_rx = section(
        p06,
        "static trinity_error_code_t spi_read_response_segment(",
        "static trinity_error_code_t spi_select(",
        "response RX",
    )
    for token in (
        "soft_spi_transfer_byte(0u, &value)",
        "SPI_TRACE_BACKEND_GPIO_MODE0",
        "g_spi_response_wire[trace_index] = value;",
    ):
        require(response_rx, token, "GPIO response RX")
    forbid(response_rx, "g_spi_trace.response_bytes[trace_index]",
           "single-authority response bytes")
    for token in ("SN_SPI0->DATA", "SN_SPI0->STAT", "SN_SPI0->CLKDIV"):
        forbid(p06, token, "GPIO transport isolation")
    forbid(p06, "spi_bytes_segment", "split transport")
    require(
        p06,
        "TRINITY_DEPLOY_SPI_CS_GUARD_US;",
        "200 us guard implementation",
    )
    require(p06, "spi_guard_delay();", "CS guard use")
    for token in (
        "static void soft_spi_half_delay(void)",
        "static trinity_error_code_t soft_spi_transfer_byte(",
        "FPST_SN32F407_SPI_MOSI_PIN",
        "FPST_SN32F407_SPI_SCK_PIN, true",
        "FPST_SN32F407_SPI_MISO_PIN",
        "FPST_SN32F407_SPI_SCK_PIN, false",
    ):
        require(p06, token, "mode-0 GPIO edge sequence")
    soft_transfer = section(
        p06,
        "static trinity_error_code_t soft_spi_transfer_byte(",
        "static trinity_error_code_t spi_write_request_bytes(",
        "GPIO byte transfer",
    )
    if soft_transfer.count("progress();") != 1:
        fail("each GPIO SPI bit loop must contain exactly one ingress progress pump")
    progress_position = soft_transfer.find("progress();")
    low_position = soft_transfer.rfind(
        "FPST_SN32F407_SPI_SCK_PIN, false", 0, progress_position
    )
    if low_position < 0:
        fail("UART ingress progress must run only after SCK returns low")

    for token in (
        "static void spi_retain_current_trace(bool failure)",
        "memcpy(&g_spi_retained_trace.metadata, &g_spi_trace,",
        "memcpy(g_spi_retained_trace.request_bytes,",
        "g_spi_request_wire, request_length);",
        "memcpy(g_spi_retained_trace.response_bytes,",
        "g_spi_response_wire, response_length);",
        "g_spi_retained_failure = failure;",
        "g_spi_retained_startup_residue = !failure;",
        "static trinity_error_code_t spi_prepare_request_window(",
        "spi_write_request_bytes(g_spi_request_wire, request_len)",
        "static bool spi_decoded_proves_truncated_request(",
        "trinity_spi_bad_length_detail_proves_truncation(",
        "static bool spi_command_allows_read_retry(",
        "static bool spi_error_allows_read_retry(",
        "rc == TRINITY_BAD_CRC",
        "command == TRINITY_SPI_GET_INFO",
        "command == TRINITY_SPI_GET_STATUS",
        "unsigned read_reissues = 0u;",
        "retry_request:",
    ):
        require(p07, token, "bounded read transport recovery")
    if p07.count("trinity_spi_bad_length_detail_is_short_cs(") != 2:
        fail("startup drain and decoded retry must share the short-CS helper")
    forbid(p07, "g_spi_trace.request_bytes[i] =",
           "single-authority request bytes")
    forbid(p07, "g_spi_trace.response_bytes[i] =",
           "single-authority response bytes")
    forbid(p07, "rsp[12] == 0u && rsp[13] == 0u",
           "legacy-only trace residue check")
    forbid(p07, "g_spi_rsp.payload[5] == 0u",
           "legacy-only decoded residue check")
    for token in ("spi_trace_rotate_work_slot", "g_spi_trace_work",
                  "g_spi_retained_trace ="):
        forbid(p07, token, "copy-retained trace")
    forbid(p07, "TRINITY_SPI_RUN_SELF_TEST ||",
           "residue retry command scope")
    forbid(p07, "TRINITY_SPI_ZEROIZE ||",
           "residue retry command scope")

    for token in (
        "trinity_crc16_ccitt_false(g_spi_response_wire",
        "trinity_spi_decode(g_spi_response_wire",
        "rc == TRINITY_BAD_CRC",
        "if (rc == TRINITY_OK) return TRINITY_OK;",
    ):
        require(p07, token, "complete mailbox validation retry")

    for token in (
        "spi_decoded_proves_truncated_request(request_len)",
        "spi_command_allows_read_retry(command, payload_length)",
        "spi_error_allows_read_retry(rc)",
        "read_reissues < TRINITY_DEPLOY_SPI_READ_REISSUE_MAX",
        "g_spi_trace.result_code = TRINITY_BAD_LENGTH;",
        "spi_record_startup_residue();",
        "retry_read_request:",
        "++read_reissues;",
        "wait_ms(TRINITY_DEPLOY_SPI_READ_RETRY_BACKOFF_MS);",
        "rc = TRINITY_BAD_LENGTH;",
        "goto retry_request;",
    ):
        require(p07 + p08, token, "bounded read-only transport recovery")
    require(p07, "if (rc != TRINITY_OK) goto retry_read_request;",
            "capture failure recovery routing")
    if p08.count("spi_error_allows_read_retry(rc)") != 1:
        fail("all response failures must share one read-only retry decision")
    if p08.count("read_reissues < TRINITY_DEPLOY_SPI_READ_REISSUE_MAX") != 1:
        fail("all response failures must share one reissue bound")
    forbid(p07 + p08, "read_reissues = 1u", "bounded read retry")
    forbid(p08, "endpoint_exchange(", "non-recursive read retry")

    for token in (
        "int trinity_spi_bad_length_detail_proves_truncation(",
        "byte_count >= expected_wire_length",
        "byte_count < TRINITY_SPI_HEADER_SIZE",
    ):
        require(spi_protocol, token, "BAD_LENGTH truncation proof")

    system_info = section(
        p12,
        "static void handle_get_system_info(",
        "static void handle_get_system_status(",
        "system info",
    )
    for token in (
        "TRINITY_DEPLOY_VERSION_PATCH",
        "DEPLOY_BUILD_ID",
        "g_controller.p1.build_id",
        "g_controller.p2.build_id",
    ):
        require(system_info, token, "system info")

    system_status = section(
        p12,
        "static void handle_get_system_status(",
        "static void handle_get_last_error(",
        "system status",
    )
    for token in (
        "GET_SYSTEM_STATUS is a local snapshot",
        "g_controller.last_error",
        "g_fault && g_error.code != TRINITY_OK",
        "response_send();",
    ):
        require(system_status, token, "nonblocking system status")
    for token in ("full_probe_all", "full_refresh_all", "endpoint_exchange"):
        forbid(system_status, token, "nonblocking system status")

    for token in (
        "if (g_spi_retained_failure)",
        "trace = &g_spi_retained_trace.metadata;",
        "g_spi_retained_startup_residue",
        "request_bytes = g_spi_retained_trace.request_bytes;",
        "response_bytes = g_spi_retained_trace.response_bytes;",
    ):
        require(p14, token, "retained trace serializer")
    live_diagnostic = section(
        p14,
        "static void handle_spi_diagnostic(",
        "static void handle_get_first_spi_failure(",
        "live SPI diagnostic",
    )
    for token in (
        "serialize_spi_trace(&g_spi_trace,",
        "g_spi_request_wire,",
        "g_spi_response_wire,",
    ):
        require(live_diagnostic, token, "canonical live SPI trace")
    forbid(live_diagnostic, "g_spi_trace.request_bytes,",
           "canonical live SPI trace")
    forbid(live_diagnostic, "g_spi_trace.response_bytes,",
           "canonical live SPI trace")

    for token in (
        "if (g_automatic_probe_active &&",
        "req->command != TRINITY_PC_PING",
        "req->command != TRINITY_PC_GET_SYSTEM_INFO",
        "response_error(req, TRINITY_BUSY, TRINITY_SOURCE_SN32, 0u);",
    ):
        require(p15, token, "automatic probe command guard")

    receive_body = section(
        p16,
        "static void pc_receive(void)",
        "static void pc_poll(void)",
        "PC receive body",
    )
    poll_body = section(
        p16,
        "static void pc_poll(void)",
        "static trinity_error_code_t hardware_init(void)",
        "PC poll body",
    )
    for token in (
        "if (!g_pc_service_enabled || g_pc_frame_pending) return;",
        "while (!g_pc_frame_pending && uart_read(&byte))",
        "g_pc_last_activity_ms = g_ms;",
        "g_pc_frame_pending = true;",
    ):
        require(receive_body, token, "PC ingress queue")
    forbid(receive_body, "pc_process();", "PC ingress queue")
    forbid(receive_body, "handle_request", "PC ingress queue")
    for token in (
        "g_pc_poll_active = true;",
        "pc_receive();",
        "if (g_pc_frame_pending) pc_process();",
        "g_pc_poll_active = false;",
    ):
        require(poll_body, token, "main-level PC execution")
    for token in (
        "g_pc_frame_pending = false;",
        "g_pc_last_activity_ms = 0u;",
        "memset(&g_spi_trace, 0, sizeof(g_spi_trace));",
        "memset(&g_spi_retained_trace, 0, sizeof(g_spi_retained_trace));",
    ):
        require(p16, token, "runtime initialization")
    probe_quiet = section(
        p16,
        "static bool pc_quiet_for_automatic_probe(void)",
        "static trinity_error_code_t hardware_init(void)",
        "automatic probe UART arbitration",
    )
    for token in (
        "!g_pc_frame_pending",
        "g_pc_wire_len == 0u",
        "g_ms - g_pc_last_activity_ms",
        "TRINITY_DEPLOY_PC_QUIET_BEFORE_PROBE_MS",
    ):
        require(probe_quiet, token, "automatic probe UART arbitration")

    for token in (
        "static bool controller_error_is_transport(",
        "code == TRINITY_BAD_LENGTH",
        "static void controller_clear_recovered_transport_error(",
        "controller->last_error = TRINITY_OK;",
        "controller->last_error_detail = 0u;",
    ):
        require(controller00, token, "recovered controller state")
    if controller03.count(
        "controller_clear_recovered_transport_error(controller);"
    ) != 2:
        fail("probe and full refresh must both clear recovered active errors")
    require(
        controller07,
        "controller_error_is_transport(controller->last_error)",
        "transport fault mask",
    )
    require(
        p12,
        "g_error.code != TRINITY_OK",
        "historical last_error telemetry",
    )

    for token in (
        "startup_wait_start = g_ms;",
        "while (!expired(startup_wait_start, SPI_STARTUP_WARMUP_MS))",
        "pc_poll();",
        "pc_quiet_for_automatic_probe()",
        "g_automatic_probe_active = false;",
        "g_automatic_probe_active = true;",
    ):
        require(p17, token, "main-level startup/periodic service")
    forbid(p17, "!g_spi_retained_failure",
           "periodic read-only recovery after retained history")

    print("PASS: v0.7.26 identity and GPIO mode-0 backend are locked")
    print("PASS: encoded four/nine-byte BAD_LENGTH captures prove truncation")
    print("PASS: GPIO SCK/MOSI/MISO ownership and 100 kHz ceiling are locked")
    print("PASS: every CS guard remains 200 us")
    print("PASS: CRC-invalid active mailboxes are reread before request replay")
    print("PASS: only zero-payload GET_INFO/GET_STATUS may be reissued twice")
    print("PASS: side-effect commands remain non-replayed")
    print("PASS: periodic read-only recovery continues after retained history")
    print("PASS: system-status is a local snapshot and cannot nest SPI refresh")
    print("PASS: retained failure bytes use a dedicated copy snapshot")
    print("PASS: live diagnostics serialize the canonical decoded wire buffers")
    print("PASS: GPIO SPI pumps UART ingress only while SCK is low")
    print("PASS: periodic probes require a complete 250 ms quiet PC window")
    print("PASS: a full refresh clears active transport fault but keeps history")
    print("PASS: non-recursive PC service and deterministic SPI transport remain locked")
    print("NOTE: source PASS does not claim Keil build, flash or hardware PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
