#!/usr/bin/env python3
"""Guard the Primer #1 RAM-read to retained-result timing architecture."""
from __future__ import annotations

import re
from pathlib import Path


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def validate(root: Path) -> None:
    core_dir = root / "rtl/core"
    parts = [
        (core_dir / f"primer1_command_core_part_{index}.svh").read_text(encoding="utf-8")
        for index in range(6)
    ]
    core = "\n".join(parts)
    core_compact = compact(core)

    task_match = re.search(
        r"task\s+automatic\s+complete_retained\b(?P<body>.*?)endtask",
        core,
        re.S,
    )
    assert task_match, "complete_retained task missing"
    task_body = task_match.group("body")
    assert "retained_commit_pending <= 1'b1;" in task_body
    assert "retained_completion_kind <=" in task_body
    assert "retained_data <=" not in task_body
    assert "retained_state <=" not in task_body
    assert "active_transaction_id <=" not in task_body

    assert "if (retained_commit_pending) begin" in core
    assert "retained_commit_pending <= 1'b0;" in core
    for assignment in [
        "retained_state <= TXN_SUCCEEDED;",
        "retained_code <= ERR_OK;",
        "retained_data_length <= 0;",
        "retained_data <= '0;",
        "active_transaction_id <= 0;",
    ]:
        assert assignment in core, f"wide retained commit missing: {assignment}"

    commit_pos = core.index("if (retained_commit_pending) begin")
    state_case_pos = core.index("case (core_state)")
    request_pos = core.index("else if (request_valid_i && response_ready_i) begin")
    assert commit_pos < state_case_pos < request_pos, (
        "retained commit must be registered before state dispatch without gating requests"
    )
    assert "end else if (transport_error_valid_i" not in core[commit_pos:state_case_pos]
    assert "C_IDLE: begin\nif (transport_error_valid_i" in core

    assert "poly_read_sample<=poly_read_data;" in core_compact
    assert "poly_read_sample!=16'd0" in core_compact
    assert "poly_read_data!=0" not in core_compact
    assert "poly_read_data!=16'd0" not in core_compact

    required_pipeline = [
        "C_ST_NTT_SCAN:begin core_state<=C_ST_INTT_SCAN;end",
        "C_ST_INTT_SCAN:begin poly_read_sample<=poly_read_data;core_state<=C_ST_BM_SCAN;end",
        "poly_read_addr<=selftest_index+1'b1;core_state<=C_ST_NTT_SCAN;",
    ]
    for fragment in required_pipeline:
        normalized = compact(fragment)
        assert normalized in core_compact, f"self-test read pipeline regression: {fragment}"


    assert "C_READ_CHUNK:begin//RegisterthecanonicalDPBoutputbeforethevariable-indexresponsewrite.poly_read_sample<=poly_read_data;core_state<=C_READ_RESP;end" in core_compact
    assert "read_response_data[8*(2+2*read_word_index)+:8]<=poly_read_sample[7:0];" in core_compact
    assert "read_response_data[8*(2+2*read_word_index)+:8]<=poly_read_data[7:0];" not in core_compact
    assert "read_response_emit_pending<=1'b1;core_state<=C_READ_RESP;" in core_compact

    assert "retained_completion_data <= data;" in task_body
    assert "if (length == 16'd14)" in task_body
    assert "RETAIN_COMMIT_UART_SUCCESS" in core
    assert "retained_data <= retained_completion_data;" in core

    # No timing exception may be introduced to conceal this synchronous path.
    sdc = (root / "constraints/primer1.sdc").read_text(encoding="utf-8")
    assert "set_multicycle_path" not in sdc
    assert "retained_data" not in sdc
    assert "poly_a" not in sdc and "poly_b" not in sdc


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    validate(root)
    print("PASS retained_commit_registered_enable")
    print("PASS poly_read_output_pipeline")
    print("PASS retained_protocol_completion_mapping")
    print("PASS retained_commit_does_not_drop_spi_request")
    print("PASS no_timing_exception_masking")


if __name__ == "__main__":
    main()
