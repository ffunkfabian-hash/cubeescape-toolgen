#!/usr/bin/env python3
"""Show the least expensive relevant Toolgen checks for changed files; --run executes them."""
import argparse
import fnmatch
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
RULES = [(".ce-repo.json", "docs"), ("check", "tests"), ("release", "tests"), ("scripts/ce_tools/*", "tests"),
         ("outputs/*", "docs"), ("work/*", "docs"),
         (".claude/agent-guard.json", "docs"), (".claude/settings.json", "docs"),
         (".claude/skills", "docs"), (".claude/hooks/*", "tests"), (".github/*", "docs"), (".gitignore", "docs"),
         ("*.md", "docs"), ("docs/*", "docs"), (".agents/*", "docs"),
         ("data/concepts/*", "concepts"), ("scripts/import_concepts.py", "concepts"),
         ("data/*", "data"), ("scripts/tool_assets/*", "assets"),
         ("toolgen/toolcache.py", "cache"), ("toolgen/generate_tools.py", "pipeline"),
         ("toolgen/*", "pipeline"), ("scripts/*", "pipeline"), ("viewer/*", "viewer"),
         ("tests/*", "tests")]
AREAS = {"docs": ("nothing", 0), "data": ("quick for affected tools", 45),
         "assets": ("quick for affected tools", 45), "tests": ("unit tests", 8),
         # 0.18: formgen concept sheets (data/concepts, provenance) and their import tool: test_concepts + the concept weapons
         "concepts": ("provenance check + quick for the concept weapons", 50),
         "pipeline": ("quick twice with cache-hit check, then standard", 100),
         "cache": ("quick twice with cache-hit check, then standard", 100),
         "viewer": ("viewer/build.sh + viewer/test_viewer.sh", 35), "unknown": ("quick twice + standard", 100)}


def area_of(path):
    return next((area for pattern, area in RULES if fnmatch.fnmatch(path, pattern)), "unknown")


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.splitlines()


def changed():
    files = set(git("diff", "--name-only", "HEAD"))
    files.update(git("ls-files", "--others", "--exclude-standard"))
    return sorted(files)


def make_plan(files):
    rows = [(name, area_of(name)) for name in sorted(set(files))]
    areas = {area for _, area in rows}
    steps = []
    if areas - {"docs"}:
        steps.append("unit")
    if "cache" in areas or "pipeline" in areas or "unknown" in areas:
        steps += ["quick1", "quick2 (verify hits)", "standard"]
    elif areas - {"docs", "tests", "viewer"}:
        steps.append("quick (affected tools)")
    if "viewer" in areas:      # mixed diffs keep their pipeline checks; the viewer step comes on top
        steps.append("viewer")
    seconds = sum(AREAS[a][1] for a in areas if a != "docs")
    return {"files": rows, "steps": steps, "seconds": seconds}


def affected_tools(files):
    from generate_tools import SourceIndex, catalog, expand, stage_sources
    changed = set(files)
    index = SourceIndex()
    selected = []
    for tool in catalog():
        closure = set()
        for run in expand(tool, "quick"):
            closure.update(stage_sources(run, tool, index))
        if changed & closure:
            selected.append(tool["id"])
    return selected or [tool["id"] for tool in catalog()]


def run_step(step, tools=()):
    if step == "unit": cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
    elif step == "viewer": cmd = ["bash", "-c", "bash viewer/build.sh output/_quick && bash viewer/test_viewer.sh output/_quick"]
    elif step == "quick (affected tools)":
        cmd = [sys.executable, "toolgen/generate_tools.py", "--tier", "quick"]
        for tool in tools: cmd += ["--tool", tool]
    elif step == "quick2 (verify hits)":
        # A cache check passes only when the second run builds and renders nothing.
        result = subprocess.run([sys.executable, "toolgen/generate_tools.py", "--tier", "quick"], cwd=ROOT,
                                capture_output=True, text=True)
        print(result.stdout, end="")
        return result.returncode == 0 and " 0 built, 0 rendered" in result.stdout
    elif step.startswith("quick"):
        cmd = [sys.executable, "toolgen/generate_tools.py", "--tier", "quick"]
    else: cmd = [sys.executable, "toolgen/generate_tools.py", "--tier", "standard"]
    return subprocess.call(cmd, cwd=ROOT) == 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="+")
    parser.add_argument("--tool", action="append", help="limit affected-tool quick runs (repeatable)")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    plan = make_plan(args.files or changed())
    tools = args.tool or affected_tools([name for name, _ in plan["files"]])
    print("Prüfplan:")
    for name, area in plan["files"]: print(f"  {area:8} {name}")
    print("Prüfweg: " + ("; ".join(plan["steps"]) if plan["steps"] else "nichts (nur Doku)"))
    print("Werkzeuge: " + (", ".join(tools) if tools else "keine"))
    print(f"Zeitschätzung: etwa {plan['seconds']} s")
    if args.run:
        for step in plan["steps"]:
            start = time.monotonic()
            print(f"\n>> {step}", flush=True)
            if not run_step(step, tools): return 1
            print(f"<< OK ({time.monotonic()-start:.1f} s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
