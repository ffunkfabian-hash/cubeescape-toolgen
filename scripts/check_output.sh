#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TASK_OUT="${1:-$TASK_ROOT/output}"
cd "$TASK_ROOT"
run_checks() {
    python3 -m unittest discover -s tests
    python3 scripts/verify_output.py "$TASK_OUT"
    bash viewer/build.sh "$TASK_OUT"
    bash viewer/test_viewer.sh "$TASK_OUT"
    python3 scripts/check_docs.py
}
if [[ "${1:-}" == "--locked" ]]; then
    TASK_OUT="${2:-$TASK_ROOT/output}"
    run_checks
elif [[ "${CE_HEAVY_HELD:-0}" == "1" ]]; then
    run_checks
else
    python3 scripts/heavy_lock.py run --what "toolgen check_output" --checkout "$TASK_ROOT" -- \
        bash "$0" --locked "$TASK_OUT"
fi
