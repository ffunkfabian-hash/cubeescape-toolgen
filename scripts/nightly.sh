#!/usr/bin/env bash
# Nachtlauf (0.20 "Nightshift"): die gebuendelten Bildstufen einmal taeglich auf main, nicht vor jedem Commit.
#   bash scripts/nightly.sh [output-dir]      (./check --nightly ruft dies ueber .ce-repo.json > check.nightly)
# Laeuft auf dem Mac (Blender, Metal, Swift), wartet auf die Blender-Sperre; nie als GitHub-Workflow.
# Inhalt: --tier full aller Werkzeuge (volle Aufloesung, Bake 2048, Samples 40), dann scripts/check_output.sh
# (Reimport, verify_surface, Viewer-Build/-Tests, Determinismus 8x, Docs). Bericht: logs/toolgen_report.json und
# logs/nightly.log im Ausgabeordner; Befunde am naechsten Tag als Patch beheben.
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TASK_OUT="${1:-$TASK_ROOT/output}"
cd "$TASK_ROOT"
mkdir -p "$TASK_OUT/logs"
LOG="$TASK_OUT/logs/nightly.log"
{
    echo "nightly start $(date '+%Y-%m-%d %H:%M:%S') HEAD=$(git rev-parse --short HEAD) branch=$(git rev-parse --abbrev-ref HEAD)"
    python3 scripts/heavy_lock.py run --resource blender --what "toolgen nightly full" --checkout "$TASK_ROOT" -- \
        python3 toolgen/generate_tools.py --tier full --output "$TASK_OUT"
    bash scripts/check_output.sh "$TASK_OUT"
    echo "nightly end $(date '+%Y-%m-%d %H:%M:%S')"
} 2>&1 | tee "$LOG"
