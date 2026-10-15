#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec bash "$TASK_ROOT/viewer/build.sh" "$@"
