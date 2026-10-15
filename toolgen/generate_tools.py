#!/usr/bin/env python3
"""Shared authoring pipeline: tiers, bounded workers, content cache and measured reports."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path

from build_toolset import find_blender, install_output
from version import CODENAME, VERSION

ROOT = Path(__file__).resolve().parents[1]
TIERS = {"quick": {"samples": 0, "percent": 100, "roundtrip": False},
         "standard": {"samples": 12, "percent": 50, "roundtrip": True},
         "full": {"samples": 40, "percent": 100, "roundtrip": True}}
CACHE_SCHEMA = 2
PIPELINE_CACHE_FUNCTIONS = ("build", "hash_file")


def catalog():
    return json.loads((ROOT / "data/tools.json").read_text())["tools"]


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cache_key(tool, tier, blender_version, device="cpu"):
    digest = hashlib.sha256(json.dumps([CACHE_SCHEMA, VERSION, tool, tier, TIERS[tier], blender_version, device],
                                       sort_keys=True).encode())
    sources = [*sorted(path for path in (ROOT / "scripts/tool_assets" / tool["folder"]).iterdir()
                       if path.suffix in (".py", ".cs", ".json")),
               ROOT / "scripts/tool_assets/design_profiles.py",
               *(ROOT / "toolgen" / name for name in ("export_viewer.py", "run_asset.py", "version.py"))]
    if tool["id"] == "flashlight":
        sources += sorted((ROOT / "scripts/tool_assets/Portalkanone").glob("*.py"))
    for path in sources:
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    # Fingerprint output producers, like Robogen; timing/report-only edits do not rebuild models.
    tree = ast.parse(Path(__file__).read_text())
    producers = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for name in PIPELINE_CACHE_FUNCTIONS:
        digest.update(ast.dump(producers[name], include_attributes=False).encode())
    return digest.hexdigest()


def valid_package(package, key=None):
    try:
        manifest = json.loads((package / "manifest.json").read_text())
        if key is not None and manifest["cache_key"] != key:
            return False
        files = manifest["files"]
        if not files:
            return False
        for name, expected in files.items():
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                return False
            file = package / name
            if not file.is_file() or file.is_symlink() or hash_file(file) != expected:
                return False
        entries = manifest["models"]
        if not entries:
            return False
        for model in entries:
            for name in ("scene.json", "vertices.bin", "indices.bin", "anim.bin", "qa_viewer.json"):
                if model["path"] + "/" + name not in files:
                    return False
            if json.loads((package / model["path"] / "qa_viewer.json").read_text())["passed"] is not True:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def worker_budget(requested=None, threads=None):
    cores = os.cpu_count() or 2
    # Two Blender processes fit comfortably on the 16-GB machine while the user's editor is open.
    workers = min(2, max(1, cores // 4)) if requested is None else requested
    if workers < 1 or workers > cores:
        raise ValueError(f"workers must be between 1 and {cores}")
    per_worker = max(1, cores // workers) if threads is None else threads
    if per_worker < 1 or per_worker * workers > cores:
        raise ValueError(f"worker threads exceed the {cores} available CPU cores")
    return workers, per_worker


@contextmanager
def output_lock(root):
    lock = root / ".toolgen-lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise RuntimeError(f"Output is already in use: {lock}; inspect its owner.json before removing a stale lock")
    try:
        (lock / "owner.json").write_text(json.dumps({"pid": os.getpid(), "started": time.time()}))
        yield
    finally:
        shutil.rmtree(lock)


def build(tool, output, tier, blender, blender_version, threads, no_cache, device="cpu"):
    start = time.perf_counter()
    key = cache_key(tool, tier, blender_version, device)
    target = output / tool["id"]
    if not no_cache and valid_package(target, key):
        print(f"CACHE_HIT {tool['id']}: unchanged outputs kept", flush=True)
        return {"tool": tool["id"], "seconds": time.perf_counter() - start, "cache_hit": True, "steps": []}
    settings = TIERS[tier]
    environment = dict(os.environ, TOOLGEN_THREADS=str(threads), OMP_NUM_THREADS=str(threads),
                       OPENBLAS_NUM_THREADS="1", TOOLGEN_SAMPLES=str(settings["samples"] or 12),
                       TOOLGEN_RENDER_PERCENT=str(settings["percent"]), TOOLGEN_DEVICE=device)
    if not settings["samples"]:
        environment["TOOLGEN_NO_RENDER"] = "1"
    else:
        environment.pop("TOOLGEN_NO_RENDER", None)
    steps = []
    log_dir = output / "logs"
    log_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{tool['id']}-", dir=output) as temporary:
        staging = Path(temporary)
        authors = staging / "authoring"
        shutil.copytree(ROOT / "scripts/tool_assets", authors)
        work = authors / tool["folder"]
        def run(script, arguments=(), author=True):
            step_start = time.perf_counter()
            command = [blender, "--background", "--factory-startup", "--threads", str(threads),
                       "--python-exit-code", "1", "--python"]
            if author:
                command += [str(ROOT / "toolgen/run_asset.py"), "--", "--script", str(work / script), *arguments]
            else:
                command += [str(ROOT / "toolgen" / script), "--", *arguments]
            log_name = f"{tool['id']}-{len(steps):02d}-{Path(script).stem}.log"
            print(f"BUILD {tool['id']}: {script} {' '.join(arguments)}", flush=True)
            with (log_dir / log_name).open("w") as stream:
                subprocess.run(command, env=environment, stdout=stream, stderr=subprocess.STDOUT, check=True)
            steps.append({"step": script, "seconds": time.perf_counter() - step_start, "log": log_name})
        run(tool["world"])
        run(tool["fps"])
        if tool["animation"]:
            run(tool["animation"], ["--no-preview"] if not settings["samples"] else [])
            if settings["samples"]:
                subprocess.run([sys.executable, str(work / "make_animation_preview.py")], check=True,
                               stdout=subprocess.DEVNULL, env=environment)
        if settings["roundtrip"]:
            for variant in ["world", "fps", *(["arrow"] if tool.get("arrow") else [])]:
                run(tool["verify"], ["--variant", variant])
        viewer = work / "ViewerData"
        models = []
        for variant, asset in [("world", tool["asset"]), ("fps", tool["asset"] + "_FPS"),
                               *([("arrow", tool["arrow"])] if tool.get("arrow") else [])]:
            for extension in ("blend", "fbx", "glb"):
                if not (work / f"{asset}.{extension}").is_file():
                    raise RuntimeError(f"Missing export: {asset}.{extension}")
            args = ["--source", str(work / (asset + ".blend")), "--output", str(viewer / variant), "--root", asset]
            if tool["clip"] and variant != "arrow":
                args += ["--clip", tool["clip"]]
            run("export_viewer.py", args, author=False)
            scene = json.loads((viewer / variant / "scene.json").read_text())
            models.append({"id": tool["id"] + "/" + variant, "tool": tool["id"], "label": tool["label"],
                           "variant": variant, "path": "ViewerData/" + variant, "asset": asset,
                           "clip": tool["clip"] if variant != "arrow" else None,
                           "triangles": scene["triangles"], "frames": scene["frames"],
                           "qa": "roundtrip" if settings["roundtrip"] else "geometry"})
        for path in work.iterdir():
            if path.suffix in (".py", ".sh", ".blend1", ".blend2") or path.name == "__pycache__":
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        files = {str(path.relative_to(work)): hash_file(path) for path in sorted(work.rglob("*")) if path.is_file()}
        (work / "manifest.json").write_text(json.dumps({"version": VERSION, "codename": CODENAME,
            "cache_schema": CACHE_SCHEMA, "cache_key": key, "tier": tier, "device": device, "tool": tool["id"],
            "models": models, "files": files}, ensure_ascii=False, indent=2) + "\n")
        if not valid_package(work, key):
            raise RuntimeError(f"Staged package failed integrity validation: {tool['id']}")
        install_output(work, target, force=True)
    return {"tool": tool["id"], "seconds": time.perf_counter() - start, "cache_hit": False, "steps": steps}


def write_catalog(output):
    models = []
    for tool in catalog():
        package = output / tool["id"]
        if not valid_package(package):
            continue
        manifest = json.loads((package / "manifest.json").read_text())
        for item in manifest["models"]:
            models.append(dict(item, path=tool["id"] + "/" + item["path"]))
    document = {"format": 1, "version": VERSION, "codename": CODENAME, "models": models}
    temporary = output / ".catalog.json.tmp"
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(output / "catalog.json")


def evaluate_timing(output, tier, seconds, load, warm, workers, threads, tools, device):
    cache = output / "cache"
    cache.mkdir(exist_ok=True)
    path = cache / "timings.json"
    history = json.loads(path.read_text()) if path.exists() else {}
    machine = [os.uname().machine, os.cpu_count(), workers, threads]
    key = json.dumps([tier, tools, warm, machine, device])
    previous = history.get(key, [])
    normalized = load / (os.cpu_count() or 1)
    band = "busy" if normalized > .6 else "light" if normalized > .3 else "quiet"
    median = statistics.median(previous) if previous else None
    limit = median * (1.3 if band == "quiet" else 2.6) if median else None
    result = {"load": load, "band": band, "cache": "warm" if warm else "cold", "reference_median_seconds": median,
              "comparison": "not_evaluated" if band == "busy" or median is None else "SLOWER" if seconds > limit else "OK"}
    if band == "quiet":
        history[key] = [*previous, seconds][-9:]
        path.write_text(json.dumps(history, indent=2) + "\n")
    return result


def render_device(blender, requested):
    if requested == "cpu" or requested == "auto" and sys.platform != "darwin":
        return "cpu"
    expression = ("import bpy; p=bpy.context.preferences.addons['cycles'].preferences; "
                  "p.compute_device_type='METAL'; p.get_devices(); "
                  "print('TOOLGEN_METAL',any(d.type=='METAL' for d in p.devices))")
    result = subprocess.run([blender, "--background", "--factory-startup", "--python-exit-code", "1",
                             "--python-expr", expression], capture_output=True, text=True, check=False)
    if result.returncode == 0 and "TOOLGEN_METAL True" in result.stdout:
        return "metal"
    if requested == "metal":
        raise RuntimeError("Metal rendering is not available; use --device cpu")
    return "cpu"


def main():
    parser = argparse.ArgumentParser(description="Generate the authored Cube Escape tools and native viewer data")
    parser.add_argument("--tier", choices=TIERS, default="quick")
    parser.add_argument("--tool", action="append", choices=[tool["id"] for tool in catalog()])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--blender")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--threads", type=int)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--device", choices=("auto", "cpu", "metal"), default="auto")
    args = parser.parse_args()
    try:
        workers, threads = worker_budget(args.workers, args.threads)
        blender = find_blender(args.blender)
        blender_version = subprocess.check_output([blender, "--version"], text=True).splitlines()[0]
        device = render_device(blender, args.device) if TIERS[args.tier]["samples"] else "cpu"
        output = (args.output or ROOT / "output" / ("_" + args.tier if args.tier != "full" else "")).resolve()
        if output == ROOT or ROOT in output.parents and "outputs" in output.relative_to(ROOT).parts:
            raise ValueError("Choose a generated output directory, not the repository or baseline outputs")
        output.mkdir(parents=True, exist_ok=True)
        (output / "logs").mkdir(exist_ok=True)
        selected = [tool for tool in catalog() if not args.tool or tool["id"] in args.tool]
        started = time.perf_counter()
        load = os.getloadavg()[0]
        print(f"Toolgen {VERSION} {CODENAME}: tier={args.tier}, {workers} workers x {threads} threads, device={device}", flush=True)
        with output_lock(output):
            results = []
            failures = []
            with ThreadPoolExecutor(max_workers=workers) as pool:
                jobs = [pool.submit(build, tool, output, args.tier, blender, blender_version, threads, args.no_cache, device)
                        for tool in selected]
                for job in as_completed(jobs):
                    try:
                        results.append(job.result())
                    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                        failures.append(str(error))
            if failures:
                (output / "logs/toolgen_report.json").write_text(json.dumps({"passed": False, "tier": args.tier,
                    "tools": results, "errors": failures}, indent=2) + "\n")
                raise RuntimeError("; ".join(failures))
            results.sort(key=lambda result: [tool["id"] for tool in selected].index(result["tool"]))
            write_catalog(output)
            elapsed = time.perf_counter() - started
            load = max(load, os.getloadavg()[0])
            timing = evaluate_timing(output, args.tier, elapsed, load, all(r["cache_hit"] for r in results), workers, threads,
                                     [tool["id"] for tool in selected], device)
            report = {"version": VERSION, "tier": args.tier, "passed": True, "seconds": elapsed,
                      "workers": workers, "threads_per_worker": threads, "device": device, "timings": timing, "tools": results}
            (output / "logs/toolgen_report.json").write_text(json.dumps(report, indent=2) + "\n")
            print(f"TOOLGEN_OK {elapsed:.2f}s, {sum(r['cache_hit'] for r in results)} cache hits; {output}", flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"toolgen failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
