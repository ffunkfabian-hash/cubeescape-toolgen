#!/usr/bin/env bash
# Standalone tool asset build; does not rebuild or modify the environment kit.
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_BLENDER="${BLENDER_BIN:-/Applications/Blender.app/Contents/MacOS/Blender}"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/create_magnet_gripper.py" -- --output "$TASK_ROOT"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/create_magnet_gripper_fps.py" -- --output "$TASK_ROOT"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/animate_magnet_gripper.py"
python3 "$TASK_ROOT/make_animation_preview.py"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/verify_magnet_gripper.py"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/verify_magnet_gripper.py" -- --variant fps
