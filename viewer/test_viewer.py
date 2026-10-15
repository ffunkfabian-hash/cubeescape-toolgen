"""Render the native viewer: all models, motion, looks, corrupt data and sidebar layout."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

output = Path(sys.argv[1]).resolve()
binary = output / "ToolGenViewer.app/Contents/MacOS/ToolGenViewer"
shots = output / "QA/Viewer"
shots.mkdir(parents=True, exist_ok=True)
catalog = json.loads((output / "catalog.json").read_text())
passed = 0


def run(*args, success=True):
    result = subprocess.run([str(binary), *map(str, args)], capture_output=True, text=True, timeout=45, check=False)
    if (result.returncode == 0) != success:
        raise AssertionError(f"Unexpected viewer exit {result.returncode}: {result.stdout} {result.stderr}")
    return result


def difference(first, second):
    result = subprocess.run(["magick", "compare", "-metric", "AE", "-fuzz", "2%", str(first), str(second), "null:"],
                            capture_output=True, text=True, check=False)
    if result.returncode not in (0, 1): raise RuntimeError(result.stderr)
    return float(result.stderr.split()[0])


def check(name):
    global passed
    passed += 1
    print("PASS", name, flush=True)


for model in catalog["models"]:
    identifier = model["id"].replace("/", "-")
    path = shots / (identifier + ".png")
    run("--snapshot", path, "--model", model["id"], "--size", "600x400", "--no-floor")
    colors = int(subprocess.check_output(["magick", str(path), "-format", "%k", "info:"], text=True))
    assert colors > 200, (model["id"], "blank preview", colors)
    check("visible model " + model["id"])
    if model["frames"] > 1:
        drawn = shots / (identifier + "-drawn.png")
        reset = shots / (identifier + "-reset.png")
        run("--snapshot", drawn, "--model", model["id"], "--frame", "31", "--size", "600x400", "--no-floor")
        run("--snapshot", reset, "--model", model["id"], "--frame", str(model["frames"]), "--size", "600x400", "--no-floor")
        assert difference(path, drawn) > 30, (model["id"], "motion not visible")
        assert difference(path, reset) < 20, (model["id"], "reset does not restore rest pose")
        check("motion and reset " + model["id"])
    if model["variant"] == "world":
        run("--sidebar-check", shots / (identifier + "-sidebar.png"), "--model", model["id"])
        check("sidebar fits " + model["id"])

run("--check-navigation")
check("Ego button, A/B variants, repeated clicks and tool switches")
for model in catalog["models"]:
    if model["variant"] != "world":
        continue
    path = shots / (model["tool"] + "-ego-button.png")
    result = run("--snapshot", path, "--model", model["id"], "--view", "FPS", "--size", "600x400", "--no-floor")
    assert f"{model['tool']}/fps" in result.stdout, result.stdout
    # Metal antialiasing can vary by a fraction of a pixel between processes.
    assert difference(path, shots / (model["tool"] + "-fps.png")) < 1
    check("Ego button renders FPS asset " + model["tool"])

with tempfile.TemporaryDirectory(prefix="toolgen-viewer-tests-") as temporary:
    root = Path(temporary)
    look_path = root / "look.json"
    saved_path = root / "saved.json"
    original = shots / "look-original.png"
    tinted = shots / "look-tinted.png"
    run("--snapshot", original, "--save-look", saved_path, "--size", "400x400")
    look = json.loads(saved_path.read_text())
    look.update(armor=[1, 0, 0], finish="Matt", glow=0)
    look_path.write_text(json.dumps(look))
    run("--snapshot", tinted, "--look", look_path, "--save-look", saved_path, "--size", "400x400")
    assert json.loads(saved_path.read_text()) == look
    assert difference(original, tinted) > 200
    check("look roundtrip and visible material change")
    for name, change in [("future version", {"version": 2}), ("unknown model", {"model": "invalid"}),
                         ("invalid color", {"armor": [float("nan"), 0, 0]})]:
        look_path.write_text(json.dumps(dict(look, **change)))
        run("--snapshot", root / "rejected.png", "--look", look_path, success=False)
        check("rejected " + name)
    run("--snapshot", root / "unknown.png", "--model", "unknown", success=False)
    check("rejected unknown selection")
    library = root / "data"
    shutil.copytree(binary.parents[1] / "Resources/ViewerData", library)
    first = catalog["models"][0]
    (library / first["path"] / "vertices.bin").write_bytes(b"broken")
    run("--snapshot", root / "broken.png", "--data", library, success=False)
    check("rejected truncated mesh buffer")

(shots / "report.json").write_text(json.dumps({"passed": True, "checks": passed}, indent=2) + "\n")
print(f"VIEWER_TESTS_OK {passed} checks")
