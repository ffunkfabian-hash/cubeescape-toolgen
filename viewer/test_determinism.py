"""Render the same viewer snapshot several times and require identical images (macOS, like the viewer tests).

Unstable renders of unchanged data point at coplanar faces (z-fighting) that a draw-order change brings out: found on
shotgun/fps in 0.12.0 (the stock decor flipped between two states, 10 of 11 renders; user decision 16.10.2026 to keep
this test in check_output.sh). Usage:

    python3 viewer/test_determinism.py <output> [--model shotgun/fps ...] [--runs 8] [--limit 1] [--frame N] [--size WxH]

Without --model every catalog model is checked. Each render is compared with the first one (magick AE, fuzz 2 %); a
model is unstable when any comparison exceeds --limit pixels (below 1 px is antialiasing noise). Exit 1 with
DETERMINISM_FAILED when a model outside KNOWN_UNSTABLE is unstable; KNOWN_UNSTABLE models are reported, never skipped, and fail
above their known value plus the limit (0.19).
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RUNS = 8
LIMIT_PX = 1.0
# Known unstable models (largest differing pixels, Mac 16.10.2026). Reported as "expected", never skipped; remove an entry
# once the run prints KNOWN_NOW_STABLE. The muzzle faces of assault/sniper/trace rifle and SMG (2-30 px) and the fusion
# rifle (2.2 px) are fixed in 2ce69db and not listed: if they still flip, the check fails.
KNOWN_UNSTABLE = {"portal_emitter/world": 1.7,   # 3 of 11 at 1.6-1.7 px (Mac, 3396e1f), cause not found, borderline
                  # 0.18: 2 of 15 at 1.3 px; identical viewer data in v0.17.2 gave 0 of 15 (0.9 px) and 1 of 15 (1.0 px) on the
                  # same Mac - borderline before this version, cause not found
                  "magnet_gripper/world": 1.3,
                  # 0.19 (Mac, 21.10.2026): 1 of 7 at 2.4 px, 12 extra renders up to 2.4; the differing pixels are single edge
                  # pixels (finger tips, light strip end, elbow end; 6-13 of 960 000 at 3 %), no patch - antialiasing, not
                  # coplanar faces
                  "ego_arms/arms": 2.4,
                  # 0.19 (Mac, 21.10.2026): 4 of 14 at 1.3 px; cross check 0.18 viewer on 0.19 data 1 of 11 (1.26 px), 0.19 viewer
                  # on 0.18 data 1 of 11 (1.32 px), 0.18 on 0.18 0 of 14 - borderline in every version, viewer data unchanged
                  "pistol/world": 1.3}


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
        # a known model is expected only up to its measured value plus the noise limit: a larger flip is a new defect
        expected = model in known and worst <= known[model] + limit
        return ("EXPECTED_UNSTABLE" if expected else "UNSTABLE"), worst, len(over)
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
