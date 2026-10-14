#!/usr/bin/env bash
# Standalone bow build: world model, large first-person variant, standalone arrow,
# one-shot Bow_Use animation, GIF preview and independent reimport of every export.
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_BLENDER="${BLENDER_BIN:-/Applications/Blender.app/Contents/MacOS/Blender}"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/create_standard_bow.py"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/create_standard_bow_fps.py" -- --output "$TASK_ROOT"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/animate_standard_bow.py"
python3 "$TASK_ROOT/make_animation_preview.py"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/verify_standard_bow.py"
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/verify_standard_bow.py" -- --variant fps
"$TASK_BLENDER" --background --factory-startup --python-exit-code 1 --python "$TASK_ROOT/verify_standard_bow.py" -- --variant arrow
