#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_BLENDER="${BLENDER_BIN:-/Applications/Blender.app/Contents/MacOS/Blender}"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/create_flashlight.py" -- --output "$TASK_ROOT"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/create_flashlight_fps.py" -- --output "$TASK_ROOT"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/verify_flashlight.py"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/verify_flashlight.py" -- --variant fps
