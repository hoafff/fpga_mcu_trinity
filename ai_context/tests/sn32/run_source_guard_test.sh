#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BUILD="${ROOT}/ai_context/evidence/generated/sn32_p010"
mkdir -p "${BUILD}"
CC_BIN="${CC:-cc}"
"${CC_BIN}" -std=c11 -Wall -Wextra -Werror -Wpedantic \
  -I"${ROOT}/sn32/firmware/platform/sn32f407" \
  "${ROOT}/sn32/firmware/platform/sn32f407/fpst_sn32f407_p010_guard.c" \
  "${ROOT}/ai_context/tests/sn32/test_sn32_p010_guard.c" \
  -o "${BUILD}/test_sn32_p010_guard"
"${BUILD}/test_sn32_p010_guard"
python3 "${ROOT}/ai_context/tests/sn32/check_p010_source_contract.py"
