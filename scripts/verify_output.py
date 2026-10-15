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
        clip = tool.get("fps_clip", tool["clip"]) if variant == "fps" else tool["clip"] if variant != "arrow" else None
        if clip:
            assert scene["frames"] == 97, (asset, "animation frame count")
            assert scene["clip"] == clip
        if variant == "fps":
            rig = json.loads((package / "qa_viewmodel.json").read_text())
            assert rig["passed"] and rig["frames_checked"] == 97 and rig["max_contact_error_m"] < .0001
            assert rig["proximal_forearm_offscreen"] and rig["visible_forearm_fraction_limit"] <= .5
            assert all(y < 0 for y in rig["proximal_forearm_max_screen_y"].values())
            assert rig["centered_wrist_max_error_m"] < .00001
            assert rig["finger_count_per_hand"] == 4 and rig["gripping_fingers_per_hand"] == 3 and rig["thumb_count_per_hand"] == 1
            camera = json.loads((package / "viewmodel_camera.json").read_text())
            assert camera["vertical_fov_degrees"] == rig["viewmodel_camera"]["vertical_fov_degrees"]
            assert set(camera["horizontal_fov_degrees"]) >= {"16:9", "16:10"}
            assert rig["hands_in_frame"] and rig["framing_range"]["summary"]["passed"]
            assert all(item["ok"] for item in rig["fov_range"] if item["binding"]) and len(rig["fov_range"]) >= 2
            assert (rig["head"] is None) == (tool["id"] == "bow")
            if rig["head"]:
                limits = rig["head"]["limits"]
                assert rig["head"]["min_unoccluded_on_screen_fraction"] >= limits["unoccluded_fraction"]
                assert rig["head"]["min_anchor_margin"] >= limits["anchor_margin"]
            if tool["id"] == "bow":
                assert rig["handedness_checked"] and rig["min_hand_side_clearance_m"] > .01
                assert rig["bow_grip_draw_shift_m"] > .02 and rig["bow_draw_rotation_degrees"] > 5
            assert rig["reticle_clear"] and rig["min_camera_depth_m"] > .03
            assert rig["max_arm_link_error_m"] < .0001 and rig["rigid_arm_links"] == len(rig["hand_sides"]) * 2
            assert all(any(node["name"] == hand for node in scene["nodes"]) for hand in rig["hand_sides"])
            if manifest["tier"] != "quick":
                imported = json.loads((package / "qa_viewmodel_roundtrip.json").read_text())
                assert all(result["passed"] for result in imported["checks"].values())
            checks += 4
        assert any(entry["id"] == tool["id"] + "/" + variant for entry in index["models"])
        checks += 3
    ego = json.loads((package / "unity_contract_fps.json").read_text())
    assert ego["variant"] == "viewmodel" and not ego["colliders"] and ego["viewmodel"]["player_fov_dependency"] == "none"
    assert ego["viewmodel"]["vertical_fov_degrees"] == json.loads((package / "viewmodel_camera.json").read_text())["vertical_fov_degrees"]
    assert ego["lods"]["LOD0"]["triangles"] <= ego["budget"]["triangles_limit"] * 1.05, (tool["id"], "ego triangle budget")
    assert len(ego["materials"]) <= 7 and len(ego["nodes"]) + len(ego["renderers"]) <= 60, (tool["id"], "ego nodes")
    assert json.loads((package / "qa_game_fps.json").read_text())["passed"]
    assert tool["asset"] + "_FPS_Game.glb" in manifest["files"]
    checks += 5
    if manifest["tier"] != "quick":
        for suffix in ["", "_fps", *(["_arrow"] if tool.get("arrow") else [])]:
            roundtrip = json.loads((package / ("qa_roundtrip" + suffix + ".json")).read_text())
            assert all(result["passed"] is True for result in roundtrip["checks"].values())
            checks += len(roundtrip["checks"])
print(f"OUTPUT_OK {checks} checks, {len(index['models'])} models")
