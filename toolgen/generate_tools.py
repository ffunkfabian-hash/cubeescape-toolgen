#!/usr/bin/env python3
"""Shared authoring pipeline: tiers, declarative build stages, a shared content cache, bounded workers and reports.

Each tool is built by the stages in STAGES, a viewer export per model variant and, in roundtrip tiers, the
independent reimport checks. Every stage has its own content key (stage_key) made of what the stage reads: its script
and the sources that script imports or names, the tool's data, the Blender version, the hashes of the generated files
it reads and, for images, samples/percent/device. Results live in the shared cache (toolcache.py): a change to
first_person.py rebuilds only the first-person stages and what reads their files, quick -> standard -> full reuse the
geometry and only render images, and a new worktree or output folder starts warm.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import functools
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
from dataclasses import asdict, dataclass
from pathlib import Path

import toolcache
from build_toolset import find_blender, install_output
from version import CODENAME, VERSION

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import heavy_lock  # noqa: E402 - scripts/ is no package; the lock protocol is shared with Robogen and Cube Escape

TIERS = {"quick": {"samples": 0, "percent": 100, "roundtrip": False},
         "standard": {"samples": 12, "percent": 50, "roundtrip": True},
         "full": {"samples": 40, "percent": 100, "roundtrip": True}}
ALL_TIERS = tuple(TIERS)
RENDER_TIERS = tuple(tier for tier, settings in TIERS.items() if settings["samples"])
ROUNDTRIP_TIERS = tuple(tier for tier, settings in TIERS.items() if settings["roundtrip"])
# Package manifest format. 3: per-stage records ("stages") and "required_qa".
CACHE_SCHEMA = 3
# Stage results: raise when stages would write something else although none of their key parts changed.
STAGE_SCHEMA = 1
GAME_CONTRACT = 2               # default contract of toolgen/game_export.py (CONTRACT_FORMAT there; tests compare)
# Source fingerprints (ASTs) of the functions that decide what a stage writes and how a package is assembled.
# Timing, reporting and orchestration edits stay outside, so they rebuild nothing (Robogen's producer fingerprint).
# New helpers that write stage outputs or packages belong in these lists.
STAGE_CACHE_FUNCTIONS = ("run_stage", "blender_command", "stage_environment", "snapshot", "is_generated", "hash_file")
PIPELINE_CACHE_FUNCTIONS = ("assemble_package", "cleanup_work", "hash_file")

# Generated files are everything a stage writes into the tool's work folder except Blender backups and Python caches.
IMAGE_PATTERNS = ("*.png", "*.gif", "animation_frames/*")
# Default input of a stage: all generated files so far except images (no model stage reads a preview), so quick,
# standard and full share the geometry. fnmatch patterns ("*" also matches "/"); "!" excludes.
GENERATED = ("*", *("!" + pattern for pattern in IMAGE_PATTERNS))
# The roundtrip checks hash the previews into build_complete*.json, so they read images too.
WITH_IMAGES = ("*", "!ViewerData/*")
# Not part of the reference closure: data/tools.json is in every key as the tool's own entry (first_person.py reads
# only its own spec), the pipeline modules as function fingerprints, the version only in the package key.
POOL_EXCLUDED = {"data/tools.json", "toolgen/generate_tools.py", "toolgen/toolcache.py", "toolgen/build_toolset.py",
                 "toolgen/version.py", "toolgen/tool_contract.py"}


@dataclass(frozen=True)
class Variant:
    """A viewer model of the package: export root, clip and the exports that must exist for it."""
    name: str
    root: str                       # template from the tool entry: {asset}, {arrow}, ...
    clip: tuple = ()                # tool keys tried in order; the first one present names the clip
    when: str | None = None         # tool key that must be set
    roundtrip: bool = False         # the tool's verify script checks it (--variant) in roundtrip tiers
    exports: tuple = ("blend", "fbx", "glb")
    node: str | None = None         # root object in the export when it differs from the file name


@dataclass(frozen=True)
class Stage:
    """One build step of every tool. A new step is one entry in STAGES (example: "game" below)."""
    name: str
    script: str                     # "{world}" etc.: author script in the tool folder; "toolgen/x.py": pipeline script
    runner: str = "blender"         # "blender" (isolated worker through run_asset.py) or "python" (system Python)
    args: tuple = ()                # templates from the tool entry; {work} is the tool's work folder at run time
    quiet_args: tuple = ()          # added when the stage runs without rendering
    render_args: tuple = ()         # added when the stage renders (render tiers)
    reads: tuple = GENERATED        # generated files it reads (templates allowed)
    sources: tuple = ()             # repository files it reads besides its script and that script's references
    renders: bool = False           # writes images in render tiers (cached apart, keyed by samples/percent/device)
    tiers: tuple = ALL_TIERS
    when: str | None = None         # tool key that must be set
    programs: tuple = ()            # external programs whose version line belongs to the key
    qa: tuple = ()                  # QA files that must say "passed": true in the package
    variants: tuple = ()            # viewer models it adds (after BASE_VARIANTS)


BASE_VARIANTS = (
    Variant("world", "{asset}", clip=("clip",), roundtrip=True),
    Variant("fps", "{asset}_FPS", clip=("fps_clip", "clip"), roundtrip=True),
    Variant("arrow", "{arrow}", when="arrow", roundtrip=True),
)

STAGES = (
    Stage("world", "{world}", renders=True),
    # create_*_fps.py also renders preview_first_person.png/preview_large.png, but first_person.py overwrites both
    # with the hands: those images never reached a package, so the FPS author step never renders.
    Stage("fps", "{fps}"),
    Stage("animation", "{animation}", when="animation", renders=True, quiet_args=("--no-preview",)),
    Stage("animation_gif", "make_animation_preview.py", runner="python", when="animation", tiers=RENDER_TIERS,
          reads=("animation_frames/*",), programs=("magick",)),
    Stage("first_person", "toolgen/first_person.py", args=("--directory", "{work}", "--tool", "{id}"),
          sources=("data/viewmodels.json",), renders=True),
    Stage("viewmodel_roundtrip", "toolgen/verify_viewmodel.py", args=("--directory", "{work}", "--asset", "{asset}_FPS"),
          tiers=ROUNDTRIP_TIERS, reads=("qa_viewmodel.json", "{asset}_FPS.blend", "{asset}_FPS.glb", "{asset}_FPS.fbx")),
    # Game export of the world model: merged renderers, matte palette, LOD1, collision, unity_contract.json; adds the
    # viewer model "game" (root <asset>_Game, world clip).
    Stage("game", "toolgen/game_export.py", args=("--directory", "{work}", "--tool", "{id}", "--contract", "{game_contract}"),
          reads=("{asset}.blend",), sources=("data/game_palette.json", "data/game_budget.json", "toolgen/version.py"), renders=True,
          render_args=("--preview",), qa=("qa_game.json",),
          variants=(Variant("game", "{asset}_Game", clip=("clip",), node="{asset}"),)),
    # The same for the first-person model (hands, arms, tool): own triangle budget, no collision, camera data in
    # unity_contract_fps.json. Viewer model "fps_game" (root <asset>_FPS_Game, LOD0 only): the Ego view of the reduced model.
    Stage("game_fps", "toolgen/game_export.py",
          args=("--directory", "{work}", "--tool", "{id}", "--viewmodel", "--contract", "{game_contract}"),
          reads=("{asset}_FPS.blend", "viewmodel_camera.json"),
          sources=("data/game_palette.json", "data/game_budget.json", "toolgen/version.py"), renders=True,
          render_args=("--preview",), qa=("qa_game_fps.json",),
          variants=(Variant("fps_game", "{asset}_FPS_Game", clip=("fps_clip", "clip"), node="{asset}_FPS"),)),
)


@dataclass
class Run:
    """A stage resolved for one tool and tier: what runs, what it reads, how it is keyed."""
    name: str
    declaration: dict
    runner: str
    script: str                     # author file name or ROOT-relative toolgen path
    args: tuple
    quiet_args: tuple
    reads: tuple
    sources: tuple
    render: bool                    # renders images in this tier
    programs: tuple = ()
    qa: tuple = ()
    variant: dict | None = None     # viewer export: {"name", "root", "clip", "exports"}
    render_args: tuple = ()


def catalog():
    return json.loads((ROOT / "data/tools.json").read_text())["tools"]


def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def template(text, tool):
    values = {key: value for key, value in tool.items() if isinstance(value, str)}
    values["work"] = "{work}"
    values.setdefault("game_contract", str(GAME_CONTRACT))   # set in the tool entry (and so in the key) only for --contract 1
    return text.format(**values)


def variant_clip(variant, tool):
    for key in variant.clip:
        if key in tool:
            return tool[key]
    return None


def variants(tool, stages=None):
    found = [variant for variant in BASE_VARIANTS if not variant.when or tool.get(variant.when)]
    for stage in STAGES if stages is None else stages:
        if not stage.when or tool.get(stage.when):
            found += [variant for variant in stage.variants if not variant.when or tool.get(variant.when)]
    return found


def expand(tool, tier, stages=None):
    """The concrete runs of one tool in one tier in build order: STAGES, viewer exports, roundtrip checks."""
    stages = STAGES if stages is None else stages
    settings = TIERS[tier]
    runs = []
    for stage in stages:
        if tier not in stage.tiers or stage.when and not tool.get(stage.when):
            continue
        runs.append(Run(stage.name, asdict(stage), stage.runner, template(stage.script, tool),
                        tuple(template(argument, tool) for argument in stage.args), stage.quiet_args,
                        tuple(template(pattern, tool) for pattern in stage.reads), stage.sources,
                        stage.renders and bool(settings["samples"]), stage.programs, stage.qa,
                        render_args=stage.render_args))
    for variant in variants(tool, stages):
        root, clip = template(variant.root, tool), variant_clip(variant, tool)
        node = template(variant.node, tool) if variant.node else root
        args = ("--source", f"{{work}}/{root}.blend", "--output", f"{{work}}/ViewerData/{variant.name}", "--root", node)
        if clip:
            args += ("--clip", clip)
        runs.append(Run("viewer_" + variant.name, {"viewer": asdict(variant), "root": root, "clip": clip}, "blender",
                        "toolgen/export_viewer.py", args, (), (root + ".blend",), (), False,
                        variant={"name": variant.name, "root": root, "clip": clip, "exports": variant.exports}))
    if settings["roundtrip"]:
        for variant in variants(tool, stages):
            if variant.roundtrip:
                runs.append(Run("roundtrip_" + variant.name, {"roundtrip": variant.name}, "blender", tool["verify"],
                                ("--variant", variant.name), (), WITH_IMAGES, (), False))
    return runs


# ------------------------------------------------------------------------------------------------------------------
# Keys: what a stage reads
# ------------------------------------------------------------------------------------------------------------------

class SourceIndex:
    """Content hashes and the reference closure of repository sources, memoised for one build.

    A source references another one when it imports its module or names its file in a string constant
    ('create_portal_gun.py', "data/viewmodels.json"); the closure follows references transitively. Same-named files
    resolve like run_asset.py's sys.path: the same folder first, then its parent, then scripts/tool_assets."""

    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.hashes, self.references = {}, {}
        found = [*(self.root / "scripts/tool_assets").rglob("*"), *(self.root / "toolgen").glob("*.py"),
                 *(self.root / "data").glob("*.json")]
        relative = (str(path.relative_to(self.root)) for path in found
                    if path.is_file() and path.suffix in (".py", ".json", ".cs") and "__pycache__" not in path.parts)
        self.pool = sorted(path for path in relative if path not in POOL_EXCLUDED)

    def digest(self, relative):
        if relative not in self.hashes:
            self.hashes[relative] = hashlib.sha256((self.root / relative).read_bytes()).hexdigest()
        return self.hashes[relative]

    def resolve(self, name, origin, module):
        found = [path for path in self.pool
                 if (Path(path).stem == name and path.endswith(".py") if module else Path(path).name == name)]
        if len(found) > 1:
            folder = str(Path(origin).parent)
            for preferred in (folder, str(Path(folder).parent), "scripts/tool_assets"):
                local = [path for path in found if str(Path(path).parent) == preferred]
                if local:
                    return local
        return found

    def direct(self, relative):
        if relative not in self.references:
            found = set()
            if relative.endswith(".py"):
                for node in ast.walk(ast.parse((self.root / relative).read_bytes())):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            found.update(self.resolve(alias.name.split(".")[0], relative, True))
                    elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                        found.update(self.resolve(node.module.split(".")[0], relative, True))
                    elif isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) < 200:
                        name = node.value.rsplit("/", 1)[-1]
                        if "." in name:
                            found.update(self.resolve(name, relative, False))
            found.discard(relative)
            self.references[relative] = sorted(found)
        return self.references[relative]

    def closure(self, roots):
        seen, todo = set(), list(roots)
        while todo:
            relative = todo.pop()
            if relative not in seen:
                seen.add(relative)
                todo += self.direct(relative)
        return sorted(seen)


def script_source(run, tool):
    """The stage script as a repository path (author scripts live in the tool folder)."""
    return run.script if run.script.startswith("toolgen/") else f"scripts/tool_assets/{tool['folder']}/{run.script}"


def stage_sources(run, tool, index):
    roots = [script_source(run, tool), *run.sources]
    if run.runner == "blender":
        roots.append("toolgen/run_asset.py")
    return index.closure(roots)


@functools.lru_cache(maxsize=8)
def function_fingerprint(names):
    tree = ast.parse(Path(__file__).read_text())
    producers = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    return hashlib.sha256("".join(ast.dump(producers[name], include_attributes=False) for name in names)
                          .encode()).hexdigest()


@functools.lru_cache(maxsize=8)
def program_version(name):
    try:
        output = subprocess.run([name, "-version"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return "missing"
    return (output.splitlines() or ["unknown"])[0]


def matches(path, patterns):
    included = any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns if not pattern.startswith("!"))
    return included and not any(fnmatch.fnmatchcase(path, pattern[1:]) for pattern in patterns if pattern.startswith("!"))


def is_image(path):
    return matches(path, IMAGE_PATTERNS)


def stage_key(run, tool, state, blender_version, index, render=None):
    """Content key of one stage result. render=None: the geometry part (everything but images); else the images
    rendered with {"samples", "percent", "device"}. state: {generated file: sha256} in the work folder before it."""
    payload = {
        "schema": STAGE_SCHEMA, "stage": run.name, "declaration": run.declaration, "tool": tool,
        "blender": blender_version, "pipeline": function_fingerprint(STAGE_CACHE_FUNCTIONS),
        "sources": {relative: index.digest(relative) for relative in stage_sources(run, tool, index)},
        "inputs": {path: digest for path, digest in sorted(state.items()) if matches(path, run.reads)},
        "programs": {name: program_version(name) for name in run.programs}, "render": render,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


# ------------------------------------------------------------------------------------------------------------------
# Running stages
# ------------------------------------------------------------------------------------------------------------------

def is_generated(relative, sources):
    parts = Path(relative).parts
    return (relative not in sources and "__pycache__" not in parts
            and Path(relative).suffix not in (".pyc", ".blend1", ".blend2") and not parts[-1].startswith(toolcache.TMP_PREFIX))


def snapshot(work, sources):
    return {str(path.relative_to(work)): hash_file(path) for path in sorted(work.rglob("*"))
            if path.is_file() and is_generated(str(path.relative_to(work)), sources)}


def stage_environment(threads, settings, device, render):
    environment = dict(os.environ, TOOLGEN_THREADS=str(threads), OMP_NUM_THREADS=str(threads),
                       OPENBLAS_NUM_THREADS="1", TOOLGEN_SAMPLES=str(settings["samples"] or 12),
                       TOOLGEN_RENDER_PERCENT=str(settings["percent"]), TOOLGEN_DEVICE=device)
    if render:
        environment.pop("TOOLGEN_NO_RENDER", None)
    else:
        environment["TOOLGEN_NO_RENDER"] = "1"
    return environment


def blender_command(blender, threads, script, arguments):
    return [blender, "--background", "--factory-startup", "--threads", str(threads), "--python-exit-code", "1",
            "--python", str(ROOT / "toolgen/run_asset.py"), "--", "--script", str(script), *arguments]


def run_stage(run, work, blender, threads, settings, device, render, log):
    """Runs one stage in work (the tool folder of an authoring copy); render: with images."""
    arguments = [argument.replace("{work}", str(work)) for argument in run.args]
    arguments += list(run.render_args if render else run.quiet_args)
    script = ROOT / run.script if run.script.startswith("toolgen/") else work / run.script
    if run.runner == "python":
        command = [sys.executable, str(script), *arguments]
    else:
        command = blender_command(blender, threads, script, arguments)
    with log.open("w") as stream:
        result = subprocess.run(command, env=stage_environment(threads, settings, device, render), stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f"stage {run.name} failed (exit {result.returncode}); log: {log}")


def changes(before, after):
    return ({path: digest for path, digest in after.items() if before.get(path) != digest},
            sorted(path for path in before if path not in after))


def apply(state, meta):
    state.update(meta["files"])
    for path in meta.get("removed", []):
        state.pop(path, None)


def record(run, part, key, meta):
    return {"stage": run.name, "part": part, "key": key, "files": dict(meta["files"]),
            "removed": list(meta.get("removed", []))}


class ToolBuild:
    """Builds one tool package: resolves the stage keys, restores hits from the shared cache, runs the misses."""

    def __init__(self, tool, output, tier, blender, blender_version, threads, no_cache, device, store, index=None):
        self.tool, self.output, self.tier = tool, output, tier
        self.blender, self.blender_version, self.threads = blender, blender_version, threads
        self.no_cache, self.device, self.store = no_cache, device, store
        self.index = index or SourceIndex()
        self.settings = TIERS[tier]
        self.render = {"samples": self.settings["samples"], "percent": self.settings["percent"], "device": device}
        self.runs = expand(tool, tier)
        self.steps = []

    def keys(self, run, state):
        geometry = stage_key(run, self.tool, state, self.blender_version, self.index)
        images = stage_key(run, self.tool, state, self.blender_version, self.index, self.render) if run.render else None
        return geometry, images

    def resolve(self, previous):
        """Records of the whole chain without building: from the shared cache, else from the installed package's own
        records (a pruned or different cache still recognises a current package). None when a stage is unknown."""
        known = {(item["stage"], item["part"], item["key"]): item for item in previous}
        state, records = {}, []
        for run in self.runs:
            for part, key in zip(("geometry", "images"), self.keys(run, state)):
                if key is None:
                    continue
                meta = self.store.lookup(key) or known.get((run.name, part, key))
                if meta is None:
                    return None
                records.append(record(run, part, key, meta))
                apply(state, meta)
        return records

    def package_key(self, records):
        folder = ROOT / "scripts/tool_assets" / self.tool["folder"]
        data = {path.name: hash_file(path) for path in sorted(folder.iterdir())
                if path.is_file() and path.suffix not in (".py", ".sh")}
        payload = [CACHE_SCHEMA, VERSION, CODENAME, self.tier, self.device, self.tool["id"],
                   [(item["stage"], item["part"], item["key"]) for item in records], data,
                   function_fingerprint(PIPELINE_CACHE_FUNCTIONS)]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def log(self, run, suffix=""):
        (self.output / "logs").mkdir(exist_ok=True)
        return self.output / "logs" / f"{self.tool['id']}-{self.runs.index(run):02d}-{run.name}{suffix}.log"

    def materialize(self, run, work, authors, sources, state):
        """Brings work to the state after run - restored from the cache or built - and returns its records."""
        tool_id, start = self.tool["id"], time.perf_counter()
        if run.variant:
            for extension in run.variant["exports"]:
                if not (work / f"{run.variant['root']}.{extension}").is_file():
                    raise RuntimeError(f"Missing export: {run.variant['root']}.{extension}")
        geometry_key, images_key = self.keys(run, state)
        geometry = None if self.no_cache else self.store.lookup(geometry_key)
        scratch = None
        try:
            if geometry and images_key:
                # The state before the stage, kept in case its images must be rendered (APFS clones: instant).
                scratch = Path(tempfile.mkdtemp(prefix=".scratch-", dir=authors.parent))
                toolcache.clone_tree(authors, scratch / "authoring")
            if geometry and self.store.restore(geometry_key, work, geometry):
                print(f"STAGE_HIT {tool_id}/{run.name}", flush=True)
                records, images_state, log = [record(run, "geometry", geometry_key, geometry)], None, None
                apply(state, geometry)
                if images_key:
                    images = self.store.restore(images_key, work)
                    images_state = "hit"
                    if images is None:
                        images, log = self.render_images(run, scratch / "authoring", sources, images_key)
                        for path in images["files"]:
                            (work / path).parent.mkdir(parents=True, exist_ok=True)
                            (work / path).unlink(missing_ok=True)
                            toolcache.clone(scratch / "authoring" / self.tool["folder"] / path, work / path)
                        images_state = "rendered"
                    records.append(record(run, "images", images_key, images))
                    apply(state, images)
                self.step(run, "hit", images_state, start, log)
                return records
        finally:
            if scratch:
                shutil.rmtree(scratch, ignore_errors=True)
        # Miss: run the stage here. In a render tier the same run renders its images - every script renders after
        # saving and exporting its models, so rendering adds images and changes nothing else.
        print(f"BUILD {tool_id}: {run.name}", flush=True)
        log = self.log(run)
        before = snapshot(work, sources)
        run_stage(run, work, self.blender, self.threads, self.settings, self.device, bool(images_key), log)
        after = snapshot(work, sources)
        changed, removed = changes(before, after)
        info = {"tool": tool_id, "stage": run.name, "toolgen": VERSION}
        geometry = {"files": {path: digest for path, digest in changed.items()
                              if not (images_key and is_image(path))}, "removed": removed}
        self.store.store(geometry_key, work, geometry["files"], removed, dict(info, part="geometry"))
        records = [record(run, "geometry", geometry_key, geometry)]
        if images_key:
            images = {"files": {path: digest for path, digest in changed.items() if is_image(path)}}
            self.store.store(images_key, work, images["files"], (), dict(info, part="images", render=self.render))
            records.append(record(run, "images", images_key, images))
        state.clear()
        state.update(after)
        self.step(run, "run", "run" if images_key else None, start, log)
        return records

    def render_images(self, run, scratch_authors, sources, images_key):
        """Renders a stage's images in a scratch copy of the state before it (its geometry came from the cache)."""
        scratch = scratch_authors / self.tool["folder"]
        log = self.log(run, "-images")
        print(f"RENDER {self.tool['id']}: {run.name} (geometry from the cache)", flush=True)
        before = snapshot(scratch, sources)
        run_stage(run, scratch, self.blender, self.threads, self.settings, self.device, True, log)
        changed, _ = changes(before, snapshot(scratch, sources))
        images = {path: digest for path, digest in changed.items() if is_image(path)}
        self.store.store(images_key, scratch, images, (), {"tool": self.tool["id"], "stage": run.name,
                                                           "part": "images", "render": self.render})
        return {"files": images, "removed": []}, log

    def step(self, run, geometry, images, start, log):
        entry = {"stage": run.name, "geometry": geometry, "images": images, "seconds": time.perf_counter() - start}
        if log:
            entry["log"] = log.name
        self.steps.append(entry)

    def build(self):
        start = time.perf_counter()
        target = self.output / self.tool["id"]
        if not self.no_cache:
            records = self.resolve(installed_records(target))
            if records is not None and valid_package(target, self.package_key(records)):
                print(f"CACHE_HIT {self.tool['id']}: unchanged outputs kept", flush=True)
                return self.result(start, True)
        with tempfile.TemporaryDirectory(prefix=f".{self.tool['id']}-", dir=self.output) as temporary:
            authors = Path(temporary) / "authoring"
            shutil.copytree(ROOT / "scripts/tool_assets", authors)
            work = authors / self.tool["folder"]
            sources = {str(path.relative_to(work)) for path in work.rglob("*") if path.is_file()}
            state, records = {}, []
            for run in self.runs:
                records += self.materialize(run, work, authors, sources, state)
            assemble_package(work, self.tool, self.tier, self.device, self.runs, records, self.package_key(records))
            install_output(work, target, force=True)
        return self.result(start, False)

    def result(self, start, package_hit):
        counts = {"hit": sum(step["geometry"] == "hit" for step in self.steps),
                  "run": sum(step["geometry"] == "run" for step in self.steps),
                  "rendered": sum(step["images"] == "rendered" for step in self.steps)}
        return {"tool": self.tool["id"], "seconds": time.perf_counter() - start, "cache_hit": package_hit,
                "stages": counts, "steps": self.steps}


def installed_records(target):
    try:
        return list(json.loads((target / "manifest.json").read_text()).get("stages", []))
    except (OSError, ValueError, AttributeError):
        return []


def cleanup_work(work):
    for path in work.iterdir():
        if path.suffix in (".py", ".sh", ".blend1", ".blend2") or path.name == "__pycache__":
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def assemble_package(work, tool, tier, device, runs, records, key):
    """Writes manifest.json for the finished work folder: models from the viewer exports, every file's hash."""
    models = []
    for run in runs:
        if run.variant:
            variant = run.variant
            scene = json.loads((work / "ViewerData" / variant["name"] / "scene.json").read_text())
            models.append({"id": tool["id"] + "/" + variant["name"], "tool": tool["id"], "label": tool["label"],
                           "variant": variant["name"], "path": "ViewerData/" + variant["name"], "asset": variant["root"],
                           "clip": variant["clip"], "triangles": scene["triangles"], "frames": scene["frames"],
                           "qa": "roundtrip" if TIERS[tier]["roundtrip"] else "geometry"})
    cleanup_work(work)
    files = {str(path.relative_to(work)): hash_file(path) for path in sorted(work.rglob("*")) if path.is_file()}
    (work / "manifest.json").write_text(json.dumps({"version": VERSION, "codename": CODENAME,
        "cache_schema": CACHE_SCHEMA, "cache_key": key, "tier": tier, "device": device, "tool": tool["id"],
        "models": models, "files": files, "required_qa": sorted({name for run in runs for name in run.qa}),
        "stages": records}, ensure_ascii=False, indent=2) + "\n")
    if not valid_package(work, key):
        raise RuntimeError(f"Staged package failed integrity validation: {tool['id']}")


def build(tool, output, tier, blender, blender_version, threads, no_cache, device="cpu", store=None):
    return ToolBuild(tool, output, tier, blender, blender_version, threads, no_cache, device,
                     store or toolcache.Store()).build()


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
        required = list(manifest.get("required_qa", []))
        if any(model.get("variant") == "fps" for model in entries):
            required.append("qa_viewmodel.json")
            if manifest.get("tier") in ("standard", "full"):
                required.append("qa_viewmodel_roundtrip.json")
        for name in required:
            if name not in files or json.loads((package / name).read_text()).get("passed") is not True:
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
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    try:
        if (output / "catalog.json").read_text() == text:
            return      # a warm run leaves the catalog untouched, like the packages
    except OSError:
        pass
    temporary = output / ".catalog.json.tmp"
    temporary.write_text(text)
    temporary.replace(output / "catalog.json")


def cache_state(results):
    """warm: no stage was built or rendered; cold: nothing came from the cache; partial: both."""
    built = sum(result["stages"]["run"] + result["stages"]["rendered"] for result in results)
    reused = sum(result["stages"]["hit"] + result["cache_hit"] for result in results)
    return "warm" if not built else "cold" if not reused else "partial"


def evaluate_timing(output, tier, seconds, load, cache, workers, threads, tools, device):
    folder = output / "cache"
    folder.mkdir(exist_ok=True)
    path = folder / "timings.json"
    history = json.loads(path.read_text()) if path.exists() else {}
    machine = [os.uname().machine, os.cpu_count(), workers, threads]
    key = json.dumps([tier, tools, cache, machine, device])
    previous = history.get(key, [])
    normalized = load / (os.cpu_count() or 1)
    band = "busy" if normalized > .6 else "light" if normalized > .3 else "quiet"
    median = statistics.median(previous) if previous else None
    limit = median * (1.3 if band == "quiet" else 2.6) if median else None
    result = {"load": load, "band": band, "cache": cache, "reference_median_seconds": median,
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
    parser.add_argument("--contract", type=int, choices=(1, GAME_CONTRACT), default=GAME_CONTRACT,
                        help="game export contract: 2 (default) or 1 (Toolgen 0.7 layout for Cube Escape before 0.64)")
    args = parser.parse_args()
    lock = None
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
        if args.contract != GAME_CONTRACT:
            selected = [dict(tool, game_contract=str(args.contract)) for tool in selected]
        if args.tier == "full":     # one heavy run at a time on this Mac (shared with Robogen, Cube Escape, Cubegen)
            lock = heavy_lock.HeavyLock(f"toolgen full {output}", str(ROOT)).acquire()
        store = toolcache.Store()
        started = time.perf_counter()
        load = os.getloadavg()[0]
        print(f"Toolgen {VERSION} {CODENAME}: tier={args.tier}, {workers} workers x {threads} threads, "
              f"device={device}, cache={store.base}", flush=True)
        with output_lock(output):
            results = []
            failures = []
            with ThreadPoolExecutor(max_workers=workers) as pool:
                jobs = [pool.submit(build, tool, output, args.tier, blender, blender_version, threads, args.no_cache,
                                    device, store) for tool in selected]
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
            cache = cache_state(results)
            timing = evaluate_timing(output, args.tier, elapsed, load, cache, workers, threads,
                                     [tool["id"] for tool in selected], device)
            stages = {name: sum(result["stages"][name] for result in results) for name in ("hit", "run", "rendered")}
            hits = sum(result["cache_hit"] for result in results)
            report = {"version": VERSION, "tier": args.tier, "passed": True, "seconds": elapsed,
                      "workers": workers, "threads_per_worker": threads, "device": device, "timings": timing,
                      "cache": {"root": str(store.base), "state": cache, "package_hits": hits, "stages": stages,
                                "prune": toolcache.prune(store.base)},
                      "heavy_lock": lock.state() if lock else "not needed", "tools": results}
            (output / "logs/toolgen_report.json").write_text(json.dumps(report, indent=2) + "\n")
            print(f"TOOLGEN_OK {elapsed:.2f}s, {hits} cache hits, stages: {stages['hit']} from cache, "
                  f"{stages['run']} built, {stages['rendered']} rendered ({cache}); {output}", flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"toolgen failed: {error}", file=sys.stderr)
        return 1
    finally:
        if lock:
            lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
