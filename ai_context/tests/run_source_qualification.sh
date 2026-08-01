#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python3 "${ROOT}/ai_context/scripts/check_repository_layout.py"
python3 "${ROOT}/ai_context/scripts/check_candidate_hashes.py"
python3 "${ROOT}/ai_context/tests/tiny1p5/check_j1_9_open_drain.py"
bash "${ROOT}/ai_context/tests/sn32/run_source_guard_test.sh"
bash "${ROOT}/ai_context/tests/tiny1p5/run_iverilog.sh"
