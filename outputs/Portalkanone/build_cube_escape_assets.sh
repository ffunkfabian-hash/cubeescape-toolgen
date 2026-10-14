#!/usr/bin/env bash
# Standalone tool asset build; does not rebuild or modify the environment kit.
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_BLENDER="${BLENDER_BIN:-/Applications/Blender.app/Contents/MacOS/Blender}"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/create_portal_gun.py" -- --output "$TASK_ROOT"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/verify_portal_gun.py"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/create_portal_gun_fps.py" -- --output "$TASK_ROOT"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/verify_portal_gun.py" -- --variant fps
