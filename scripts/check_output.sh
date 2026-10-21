#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TASK_OUT="${1:-$TASK_ROOT/output}"
cd "$TASK_ROOT"
run_checks() {
    python3 -m unittest discover -s tests
    python3 scripts/verify_output.py "$TASK_OUT"
    BLENDER_BIN="$(python3 -c 'import sys; sys.path.insert(0, "toolgen"); from build_toolset import find_blender; print(find_blender(None))')"
    "$BLENDER_BIN" --background --factory-startup --python-exit-code 1 --python scripts/verify_surface.py -- "$TASK_OUT"
    bash viewer/build.sh "$TASK_OUT"
    bash viewer/test_viewer.sh "$TASK_OUT"
    python3 viewer/test_determinism.py "$TASK_OUT"   # same snapshot 8x: z-fighting / unstable renders (16.10.2026)
    python3 scripts/check_docs.py
}
if [[ "${1:-}" == "--locked" ]]; then
    TASK_OUT="${2:-$TASK_ROOT/output}"
    run_checks
elif [[ "${CE_HEAVY_HELD:-}" == "1" || "${CE_HEAVY_HELD:-}" == "blender" ]]; then
    run_checks
else
    python3 scripts/heavy_lock.py run --resource blender --what "toolgen check_output" --checkout "$TASK_ROOT" -- \
        bash "$0" --locked "$TASK_OUT"
fi
