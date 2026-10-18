#!/usr/bin/env python3
"""Compare the models of two Toolgen outputs of the same tier (Toolgen 0.14: the robot variant must not change the existing
models).

    python3 scripts/compare_models.py <base output> <new output>

Byte-compares, per tool package, every GLB and the viewer data (vertices/indices/anim .bin) the base package lists. FBX and
.blend files carry export timestamps and the absolute path of the build folder (so even their size differs between
worktrees); they come from the same Blender scene as the GLB and are listed for information only (sizes), never failing.
Files new in the second output (the robot variant) are counted, not compared. Exit 1 when a compared file differs or is gone.
Known limit (Toolgen 0.13): the first-person game GLB (<asset>_FPS_Game*.glb, ViewerData/fps_game) is not byte-identical
between builds; it is reported separately and does not fail. The same holds for the robot game GLB (<asset>_Robot_Game.glb,
measured 0.15: two values per weapon 1e-4 apart between builds in different folders, JSON chunk identical).
"""
import hashlib
import json
import sys
from pathlib import Path

BINARY = (".glb", ".bin")
SIZE_ONLY = (".fbx", ".blend")


def known_unstable(name):
    return "_FPS_Game" in name or "_Robot_Game" in name or name.startswith(("ViewerData/fps_game/", "ViewerData/robot_game/"))


def digest_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def compare(base, new):
    report = {"identical": 0, "different": [], "unstable": [], "size_only": {"same": 0, "different": []}, "added": [],
              "missing": []}
    for manifest in sorted(base.glob("*/manifest.json")):
        tool = manifest.parent.name
        old = json.loads(manifest.read_text())["files"]
        path = new / tool / "manifest.json"
        if not path.exists():
            report["missing"].append(tool)
            continue
        current = json.loads(path.read_text())["files"]
        report["added"] += [f"{tool}/{name}" for name in current if name not in old]
        for name, digest in old.items():
            if name not in current:
                report["missing"].append(f"{tool}/{name}")
            elif name.endswith(BINARY):
                # the files themselves, not the manifests' claims; a file gone from either folder is missing
                old_file, new_file = digest_of(base / tool / name), digest_of(new / tool / name)
                if old_file is None or new_file is None:
                    report["missing"].append(f"{tool}/{name}")
                elif old_file == new_file:
                    report["identical"] += 1
                else:
                    (report["unstable"] if known_unstable(name) else report["different"]).append(f"{tool}/{name}")
            elif name.endswith(SIZE_ONLY):
                same = (base / tool / name).stat().st_size == (new / tool / name).stat().st_size
                if same:
                    report["size_only"]["same"] += 1
                else:
                    report["size_only"]["different"].append(f"{tool}/{name}")
    return report


def main():
    base, new = Path(sys.argv[1]), Path(sys.argv[2])
    report = compare(base, new)
    print(f"identical GLB/viewer files: {report['identical']}")
    print(f"different: {len(report['different'])} {report['different'][:20]}")
    print(f"known unstable (first-person and robot game GLB): {len(report['unstable'])}")
    print(f"FBX/blend (information only, paths and timestamps inside): same size {report['size_only']['same']}, "
          f"other size {len(report['size_only']['different'])}")
    print(f"added files: {len(report['added'])}, missing: {report['missing'][:20]}")
    failed = report["different"] or report["missing"] or not report["identical"]   # nothing compared: wrong base folder
    print("MODELS_UNCHANGED" if not failed else "MODELS_CHANGED")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
