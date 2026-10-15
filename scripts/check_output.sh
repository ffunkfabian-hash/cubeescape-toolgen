#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TASK_OUT="${1:-$TASK_ROOT/output}"
cd "$TASK_ROOT"
python3 -m unittest discover -s tests
python3 scripts/verify_output.py "$TASK_OUT"
bash viewer/build.sh "$TASK_OUT"
bash viewer/test_viewer.sh "$TASK_OUT"
python3 scripts/check_docs.py
