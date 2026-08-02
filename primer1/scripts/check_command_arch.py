#!/usr/bin/env python3
"""Guard the five corrected Primer #1 command-core behaviors."""
from __future__ import annotations

import re
from pathlib import Path


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def command_body(core: str, command: str, next_command: str) -> str:
    match = re.search(
        rf"{command}\s*:\s*begin(?P<body>.*?)(?={next_command}\s*:\s*begin)",
        core,
        re.S,
    )
    assert match, f"cannot isolate {command} body"
    return match.group("body")


def validate(root: Path) -> None:
    core_dir = root / "rtl/core"
    core = "\n".join(
        (core_dir / f"primer1_command_core_part_{index}.svh").read_text(
            encoding="utf-8"
        )
        for index in range(6)
    )
    normalized = compact(core)

    # RUN_SELF_TEST must validate and retain the requested supported mask rather
    # than executing every stage and returning the historical fixed 0x013E mask.
    run_self_test = compact(
        command_body(core, "CMD_RUN_SELF_TEST", "CMD_GET_TXN_RESULT")
    )
    assert "SELFTEST_SUPPORTED_MASK" in core
    assert "selftest_requested_mask" in core
    assert "ERR_NOT_SUPPORTED" in run_self_test
    assert "&~SELFTEST_SUPPORTED_MASK" in run_self_test
    assert "selftest_requested_mask<={pbyte(request_payload_i,0),pbyte(request_payload_i,1)};" in run_self_test
    assert "finish_selftest_success" in core
    assert "selftest_data[7:0]=selftest_requested_mask[15:8];" in normalized
    assert "selftest_data[15:8]=selftest_requested_mask[7:0];" in normalized
    assert "retained_data[7:0]<=8'h01" not in normalized
    assert "retained_data[15:8]<=8'h3E" not in normalized

    # Partial ZEROIZE scopes are explicitly rejected until individually
    # implemented; ZEROIZE_ALL remains the only accepted command scope.
    zeroize = compact(command_body(core, "CMD_ZEROIZE", "CMD_STAGE_SESSION"))
    assert "pbyte(request_payload_i,0)!=ZEROIZE_ALL" in zeroize
    assert "ERR_NOT_SUPPORTED" in zeroize
    assert zeroize.index("ERR_NOT_SUPPORTED") < zeroize.index("begin_retained")

    # ABORT_SESSION must preserve staged/active context on a mismatched nonzero ID.
    abort = compact(command_body(core, "CMD_ABORT_SESSION", "CMD_POLY_BEGIN"))
    assert "ERR_BAD_SESSION" in abort
    assert "staged_valid&&staged_session_id==" in abort
    assert "active_valid&&active_session_id==" in abort
    assert abort.index("ERR_BAD_SESSION") < abort.index("staged_key<=0")

    # GET_STATUS and GET_TXN_RESULT are serviced while retained operations run;
    # the operation FSM still executes in the same clocked process.
    busy_dispatch = normalized.index("if((core_state==C_WAIT_POLY")
    state_dispatch = normalized.index("case(core_state)")
    assert busy_dispatch < state_dispatch
    busy_region = normalized[busy_dispatch:state_dispatch]
    assert "CMD_GET_STATUS" in busy_region
    assert "emit_status_response" in busy_region
    assert "CMD_GET_TXN_RESULT" in busy_region
    assert "emit_txn_result_response" in busy_region
    assert "ERR_BUSY" in busy_region

    # A result-ready polynomial bank cannot be overwritten before POLY_RETIRE.
    poly_begin = compact(command_body(core, "CMD_POLY_BEGIN", "CMD_POLY_WRITE_CHUNK"))
    assert "operation_state==OP_RESULT_READY" in poly_begin
    assert "ERR_RESULT_PENDING" in poly_begin
    assert poly_begin.index("ERR_RESULT_PENDING") < poly_begin.index("operation_state<=OP_LOAD_INPUT")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    validate(root)
    print("PASS selftest_mask_execution_and_result")
    print("PASS explicit_zeroize_scope_policy")
    print("PASS abort_session_id_validation")
    print("PASS busy_reconciliation_request_service")
    print("PASS poly_result_ready_overwrite_guard")


if __name__ == "__main__":
    main()
