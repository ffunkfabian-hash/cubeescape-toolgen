"""Verify manifests and every required model/animation/export in a completed library."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
from generate_tools import catalog, valid_package

output = Path(sys.argv[1])
index = json.loads((output / "catalog.json").read_text())
checks = 0
for tool in catalog():
    package = output / tool["id"]
    assert valid_package(package), tool["id"]
    manifest = json.loads((package / "manifest.json").read_text())
    for variant in ["world", "fps", *(["arrow"] if tool.get("arrow") else [])]:
        asset = tool["arrow"] if variant == "arrow" else tool["asset"] + ("_FPS" if variant == "fps" else "")
        for ext in ("blend", "fbx", "glb"):
            assert asset + "." + ext in manifest["files"], (asset, ext)
            checks += 1
        scene = json.loads((package / "ViewerData" / variant / "scene.json").read_text())
        assert scene["autoplay"] is False and scene["loop"] is False
        if tool["clip"] and variant != "arrow":
            assert scene["frames"] == 97, (asset, "animation frame count")
            assert scene["clip"] == tool["clip"]
        assert any(entry["id"] == tool["id"] + "/" + variant for entry in index["models"])
        checks += 3
    if manifest["tier"] != "quick":
        for suffix in ["", "_fps", *(["_arrow"] if tool.get("arrow") else [])]:
            roundtrip = json.loads((package / ("qa_roundtrip" + suffix + ".json")).read_text())
            assert all(result["passed"] is True for result in roundtrip["checks"].values())
            checks += len(roundtrip["checks"])
print(f"OUTPUT_OK {checks} checks, {len(index['models'])} models")
