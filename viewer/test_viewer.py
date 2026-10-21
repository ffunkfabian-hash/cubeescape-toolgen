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
        # The clips differ in timing (bow draw at 31, weapon shots at 15-17, bolts and fins later): the motion must show
        # in at least one of these frames.
        motion = 0
        # 1200x800: long weapons are small in the default framing, their moving parts only a few pixels at 600x400.
        large = shots / (identifier + "-large.png")
        run("--snapshot", large, "--model", model["id"], "--size", "1200x800", "--no-floor")
        for frame in ("15", "16", "19", "31", "46", "56", "60"):
            run("--snapshot", drawn, "--model", model["id"], "--frame", frame, "--size", "1200x800", "--no-floor")
            motion = max(motion, difference(large, drawn))
        run("--snapshot", reset, "--model", model["id"], "--frame", str(model["frames"]), "--size", "1200x800", "--no-floor")
        assert motion > 30, (model["id"], "motion not visible")
        assert difference(large, reset) < 40, (model["id"], "reset does not restore rest pose")
        check("motion and reset " + model["id"])
    if model["variant"] in ("world", "fps", "fps_game"):
        # The Ego sidebar adds the field-of-view section; both layouts must fit 360 pt.
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


def ego_view(model):
    """Shown through the viewmodel camera: the authored Ego model, and the reduced one up to contract 4 (contract 5: the
    device alone, inspected in the orbit view)."""
    return model["variant"] == "fps" or (model["variant"] == "fps_game" and model.get("contract", 4) < 5)


for model in catalog["models"]:
    if not ego_view(model):
        continue
    camera_path = output / model["tool"] / "viewmodel_camera.json"
    assert camera_path.is_file(), (model["id"], "missing viewmodel camera")
    default = json.loads(camera_path.read_text())["vertical_fov_degrees"]
    identifier = model["id"].replace("/", "-")
    base = shots / (identifier + ".png")
    explicit = shots / (identifier + "-fov-default.png")
    run("--snapshot", explicit, "--model", model["id"], "--fov", default, "--size", "600x400", "--no-floor")
    assert difference(base, explicit) < 1, (model["id"], "data FOV is not the Ego default")
    for degrees in (35, 75):
        path = shots / f"{identifier}-fov-{degrees}.png"
        run("--snapshot", path, "--model", model["id"], "--fov", degrees, "--size", "600x400", "--no-floor")
        assert difference(base, path) > 200, (model["id"], degrees, "FOV has no visible effect")
    check("field of view default and slider range " + model["id"])
run("--snapshot", shots / "rejected-fov.png", "--model", catalog["models"][0]["id"], "--fov", 120, success=False)
check("rejected out-of-range field of view")

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
    # Game models come from the game export; the viewer shows them when present and works without them.
    game_library = root / "game"
    shutil.copytree(binary.parents[1] / "Resources/ViewerData", game_library)
    game_catalog = json.loads((game_library / "catalog.json").read_text())
    games = [model for model in game_catalog["models"] if model["variant"] == "game"]
    if games:
        for game in games:
            shot = shots / (game["id"].replace("/", "-") + ".png")
            run("--snapshot", shot, "--data", game_library, "--model", game["id"], "--size", "600x400", "--no-floor")
            assert shot.stat().st_size > 1000, f"empty game snapshot: {shot}"
        game = games[0]
        run("--check-navigation", "--data", game_library)
        run("--sidebar-check", shots / "game-sidebar.png", "--data", game_library, "--model", game["id"])
        without = dict(game_catalog, models=[model for model in game_catalog["models"]
                                             if model["variant"] not in ("game", "fps_game")])
        (game_library / "catalog.json").write_text(json.dumps(without))
        run("--check-navigation", "--data", game_library)
        (game_library / "catalog.json").write_text(json.dumps(game_catalog))
    else:
        world = next(model for model in game_catalog["models"] if model["variant"] == "world")
        shutil.copytree(game_library / world["path"], game_library / world["tool"] / "ViewerData/game")
        game = dict(world, id=world["tool"] + "/game", variant="game", path=world["tool"] + "/ViewerData/game")
        game.pop("qa")
        game_catalog["models"].append(game)
        (game_library / "catalog.json").write_text(json.dumps(game_catalog))
        run("--snapshot", shots / "game-model.png", "--data", game_library, "--model", game["id"], "--size", "600x400", "--no-floor")
        assert difference(shots / "game-model.png", shots / (world["id"].replace("/", "-") + ".png")) < 1
        run("--check-navigation", "--data", game_library)
        run("--sidebar-check", shots / "game-sidebar.png", "--data", game_library, "--model", game["id"])
    check("game model variant shown, navigable and optional")
    egos = [model for model in game_catalog["models"] if model["variant"] == "fps_game"]
    assert egos, "catalog has no Ego game model (stage game_fps)"
    for ego in egos:
        authored = next(model for model in game_catalog["models"] if model["tool"] == ego["tool"] and model["variant"] == "fps")
        shot = shots / (ego["id"].replace("/", "-") + "-view.png")
        result = run("--snapshot", shot, "--data", game_library, "--model", ego["id"], "--size", "600x400", "--no-floor")
        assert ego["id"] in result.stdout and ego["triangles"] <= authored["triangles"], (ego["id"], result.stdout)
        if not ego_view(ego):
            continue      # contract 5: the device alone in the orbit view ("visible model" above), no Ego framing to keep
        # The reduced model keeps the framing of the authored one: same camera, silhouette within a few percent.
        reference = shots / (authored["id"].replace("/", "-") + ".png")
        pixels = 600 * 400
        assert difference(shot, reference) < pixels * .10, (ego["id"], "reduced Ego model differs from the authored one")
    check("reduced Ego model shown as its own variant, optional and framed like the authored one")
    for tool in {model["tool"] for model in game_catalog["models"]}:
        (game_library / tool / "viewmodel_camera.json").unlink(missing_ok=True)
    run("--snapshot", root / "fallback.png", "--data", game_library, "--model", next(
        model["id"] for model in game_catalog["models"] if model["variant"] == "fps"), "--size", "600x400")
    check("missing viewmodel camera falls back to the default FOV")
    library = root / "data"
    shutil.copytree(binary.parents[1] / "Resources/ViewerData", library)
    first = catalog["models"][0]
    (library / first["path"] / "vertices.bin").write_bytes(b"broken")
    run("--snapshot", root / "broken.png", "--data", library, success=False)
    check("rejected truncated mesh buffer")

(shots / "report.json").write_text(json.dumps({"passed": True, "checks": passed}, indent=2) + "\n")
print(f"VIEWER_TESTS_OK {passed} checks")
