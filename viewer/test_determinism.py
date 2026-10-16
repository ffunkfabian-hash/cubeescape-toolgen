"""Render the same viewer snapshot several times and require identical images (macOS, like the viewer tests).

Unstable renders of unchanged data point at coplanar faces (z-fighting) that a draw-order change brings out: found on
shotgun/fps in 0.12.0 (the stock decor flipped between two states, 10 of 11 renders; user decision 16.10.2026 to keep
this test in check_output.sh). Usage:

    python3 viewer/test_determinism.py <output> [--model shotgun/fps ...] [--runs 8] [--limit 1] [--frame N] [--size WxH]

Without --model every catalog model is checked. Each render is compared with the first one (magick AE, fuzz 2 %); a
model is unstable when any comparison exceeds --limit pixels (below 1 px is antialiasing noise). Exit 1 with
DETERMINISM_FAILED when a model outside KNOWN_UNSTABLE is unstable; KNOWN_UNSTABLE models are reported, never skipped.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RUNS = 8
LIMIT_PX = 1.0
# Unstable before the z-fighting fixes of 0.12.0 (Mac, 16.10.2026, 8 runs, largest differing pixels). Reported as
# "expected" until the Mac shows them stable after the fix; then remove the entry (the run prints KNOWN_NOW_STABLE).
KNOWN_UNSTABLE = {"smg/world": 30.0, "smg/game": 4.4, "assault_rifle/world": 14.6, "sniper_rifle/world": 9.4,
                  "sniper_rifle/game": 3.3, "scout_rifle/world": 5.5, "scout_rifle/game": 3.8}


def difference(first, second):
    result = subprocess.run(["magick", "compare", "-metric", "AE", "-fuzz", "2%", str(first), str(second), "null:"],
                            capture_output=True, text=True, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr)
    return float(result.stderr.split()[0])


def classify(model, differences, limit=LIMIT_PX, known=None):
    """Verdict for one model from its comparisons with the first render: (status, largest difference, count)."""
    known = KNOWN_UNSTABLE if known is None else known
    over = [value for value in differences if value > limit]
    worst = max(differences, default=0.0)
    if over:
        return ("EXPECTED_UNSTABLE" if model in known else "UNSTABLE"), worst, len(over)
    return ("KNOWN_NOW_STABLE" if model in known else "STABLE"), worst, 0


def failed(verdicts):
    return [model for model, (status, _, _) in verdicts.items() if status == "UNSTABLE"]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument("--runs", type=int, default=RUNS)
    parser.add_argument("--frame", type=int, default=None)
    parser.add_argument("--size", default="1200x800")
    parser.add_argument("--limit", type=float, default=LIMIT_PX, help="pixels; below is antialiasing noise")
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    binary = output / "ToolGenViewer.app/Contents/MacOS/ToolGenViewer"
    models = args.model or [model["id"] for model in json.loads((output / "catalog.json").read_text())["models"]]
    verdicts = {}
    with tempfile.TemporaryDirectory() as folder:
        for model in models:
            shots = []
            for run in range(args.runs):
                path = Path(folder) / f"{model.replace('/', '-')}-{run}.png"
                command = [str(binary), "--data", str(output), "--snapshot", str(path), "--model", model,
                           "--size", args.size, "--no-floor"]
                if args.frame is not None:
                    command += ["--frame", str(args.frame)]
                subprocess.run(command, capture_output=True, timeout=45, check=True)
                shots.append(path)
            differences = [difference(shots[0], shot) for shot in shots[1:]]
            verdicts[model] = classify(model, differences, args.limit)
            status, worst, count = verdicts[model]
            note = f" (known: {KNOWN_UNSTABLE[model]} px)" if model in KNOWN_UNSTABLE else ""
            print(f"{status} {model} {count} of {args.runs - 1} differ, max {worst:.1f} px{note}", flush=True)
    bad = failed(verdicts)
    if bad:
        sys.exit(f"DETERMINISM_FAILED {len(bad)} model(s): {', '.join(bad)}")
    print(f"DETERMINISM_OK {len(models)} model(s), {args.runs} renders each, limit {args.limit} px")


if __name__ == "__main__":
    main()
