#!/usr/bin/env bash
set -euo pipefail
TASK_REPO="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$TASK_REPO/toolgen/generate_tools.py" --tier full --tool flashlight "$@"
