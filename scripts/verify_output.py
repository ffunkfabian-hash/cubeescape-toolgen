"""Verify manifests and every required model/animation/export in a completed library."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
import concept_spec  # noqa: E402
import ego_arms  # noqa: E402 - pure helpers (contract 5 clip list, rig data)
import ego_clips  # noqa: E402
import game_export  # noqa: E402 - pure helpers, no bpy at import
import surface  # noqa: E402
from generate_tools import ARMS, RIG_CONTRACT, catalog, valid_package  # noqa: E402

PALETTE = json.loads((ROOT / "data/game_palette.json").read_text())
EGO = ego_clips.load()
PROFILES = json.loads((ROOT / "data/viewmodels.json").read_text())["tools"]

RIG = ego_arms.load()

output = Path(sys.argv[1])
index = json.loads((output / "catalog.json").read_text())
checks = 0
arms_hash = None
def fps_format(tool):
    try:
        return json.loads((output / tool["id"] / "unity_contract_fps.json").read_text())["format"]
    except (OSError, ValueError, KeyError):
        return 0


if any(fps_format(tool) >= RIG_CONTRACT for tool in catalog()):        # what was built, not what tools.json asks for
    # 0.19 Kinetic: the shared arm package of contract 5
    package = output / ARMS["id"]
    assert valid_package(package), "ego_arms"
    arms = json.loads((package / "unity_contract_arms.json").read_text())
    qa = json.loads((package / "qa_arms.json").read_text())
    assert qa["passed"] and all(check["passed"] for check in qa["checks"].values()), "qa_arms"
    assert arms["format"] == 5 and arms["rig"]["id"] == "ego_arms" and arms["rig"]["version"] == RIG["rig"]["version"]
    assert [node["name"] for node in arms["nodes"]] == ego_arms.all_nodes(RIG["rig"]["asset"]), "ego_arms nodes"
    assert sum(r["triangles"] for r in arms["renderers"]) <= RIG["rig"]["budget_triangles"], "ego_arms budget"
    assert set(m for r in arms["renderers"] for m in r["materials"]) <= set(ego_arms.LOOK_SLOTS), "ego_arms slots"
    assert not arms["colliders"] and arms["minimum_consumer"]["shared_arm_rig"]
    assert any(entry["id"] == "ego_arms/arms" for entry in index["models"]), "ego_arms in the viewer catalogue"
    arms_hash = arms["rig"]["hash"]
    checks += 8
for tool in catalog():
    package = output / tool["id"]
    assert valid_package(package), tool["id"]
    manifest = json.loads((package / "manifest.json").read_text())
    rigged = fps_format(tool) >= RIG_CONTRACT
    if rigged:
        clips, _ = ego_arms.clip_list_v5(tool, PROFILES[tool["id"]], RIG["devices"][tool["id"]])
    else:
        clips, _ = ego_clips.clip_list(EGO, tool, PROFILES[tool["id"]].get("motion"))
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
        if variant == "fps" and rigged:
            # contract 5: the assembly on the shared rig (toolgen/ego_rig.py)
            rig = json.loads((package / "qa_viewmodel.json").read_text())
            assert rig["passed"] and not rig["failures"], (tool["id"], rig["failures"][:3])
            assert rig["rig"]["hash"] == arms_hash, (tool["id"], "clips built on another arm rig")
            assert max(rig["hand_touch_max_m"].values()) <= rig["hand_touch_limit_m"] <= .008, tool["id"]
            assert max(rig["wrist_bend_max_degrees"].values()) <= rig["wrist_limit_degrees"] <= 55, tool["id"]
            assert [name for name in rig["events"]] == [clip["name"] for clip in clips], (tool["id"], "clip names")
            roundtrip = json.loads((package / "qa_viewmodel_roundtrip.json").read_text())
            assert roundtrip["passed"], (tool["id"], roundtrip["failures"])
            assert any(node["name"] == "Hand_R" for node in scene["nodes"]), (tool["id"], "viewer shows the arms")
            checks += 6
        elif variant == "fps":
            rig = json.loads((package / "qa_viewmodel.json").read_text())
            assert rig["passed"] and rig["max_contact_error_m"] < .0001
            # every frame of the Use clip and of every ego clip is checked; each clip starts and ends in its named pose
            assert rig["frames_checked"] == 97 + sum(clip["length"] + 1 for clip in clips), (tool["id"], "frames checked")
            assert [clip["name"] for clip in rig["ego_clips"]["clips"]] == [clip["name"] for clip in clips]
            assert not rig["ego_clips"]["failures"] and rig["ego_clip_boundary_max_error"] < .0001
            assert all(value["max_degrees"] <= value["limit_degrees"] and value["elbow_on_palm_side"]
                       for value in rig["wrist_bend"].values()), (tool["id"], "wrist bend")
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
    # equipment tools (contract 2): seven MT_ slots plus the hands' palette materials
    equipment = ego.get("material_convention") == "equipment_channels"
    limit = PALETTE["channels"]["max_materials_per_viewmodel"] if equipment else PALETTE["max_materials_per_viewmodel"]
    assert len(ego["materials"]) <= limit and len(ego["nodes"]) + len(ego["renderers"]) <= 60, (tool["id"], "ego nodes")
    if equipment:
        expected = {"Primary", "Secondary", "Accent", "Metal", "Energy", "Emission", "Detail"}
        if tool.get("concept"):     # 0.18: a concept weapon carries the channels its sheet uses (KG02: no MT_Energy)
            sheet = concept_spec.load(tool["concept"] + ".geo.json")
            expected = {part["channel"].removeprefix("MT_") for part in sheet["parts"] if not part["glass"]}
        assert set(ego["equipment"]["channels"]) == expected, (tool["id"], sorted(ego["equipment"]["channels"]))
        assert all(name.startswith("M_") for name in ego["equipment"]["untouched_slots"]), tool["id"]
        checks += 2
    game_qa = json.loads((package / "qa_game_fps.json").read_text())
    assert game_qa["passed"]
    assert tool["asset"] + "_FPS_Game.glb" in manifest["files"]
    # contract 3: Use clip first (main files), then the ego clips in the clips file, each with its frame range
    names = [clip["name"] for clip in ego["clips"]]
    assert names[0] == tool.get("fps_clip", tool["clip"]), (tool["id"], "Use clip first")
    if ego["format"] >= 3:
        assert names[1:] == [clip["name"] for clip in clips], (tool["id"], "ego clip names")
        for kind in ("fbx", "glb"):
            assert tool["asset"] + "_FPS_Game_Clips." + kind in manifest["files"], (tool["id"], kind)
            assert game_qa["checks"]["roundtrip_clips_" + kind]["passed"], (tool["id"], kind)
        assert all(entry["take"] == ego["ego_clips"]["take"] for entry in ego["clips"][1:])
        checks += 4
    if rigged:
        # contract 5 blocks: attach, grip, arms_rig, assembly, event channels, the device alone, the half turn
        assert ego["format"] == 5 and ego["arms_rig"]["hash"] == arms_hash, tool["id"]
        assert ego["attach"]["bone"] == "Prop_R" and set(ego["grip"]) == {"R", "L"}, tool["id"]
        paths = {entry["name"] for entry in ego["assembly"]}
        assert {"Prop_R", "Hand_L", ego["device_root"]} <= paths, (tool["id"], "assembly")
        assert all("channel" in event for clip in ego["clips"] for event in clip["events"]), (tool["id"], "event channels")
        for name in ("device_without_arms", "socket_hand_at_origin", "anchor_half_turn", "triangle_budget"):
            assert game_qa["checks"][name]["passed"], (tool["id"], name)
        checks += 8
    if tool.get("hold", {}).get("sight_kind") and rigged:
        rig = json.loads((package / "qa_viewmodel.json").read_text())
        assert rig["sight_aim_idle"] and max(rig["sight_aim_idle"]["lateral_m"], rig["sight_aim_idle"]["vertical_m"]) <= .001
        checks += 1
    elif tool.get("hold", {}).get("sight_kind"):
        # 0.11.0 (Cube Escape 0.72 T1/T2/T6): sight anchors in both contracts, Fire marker on the shot, ADS target pose
        world = json.loads((package / "unity_contract.json").read_text())
        scope = tool["hold"]["sight_kind"] == "scope"
        for contract in (world, ego):
            anchors = {anchor["name"] for anchor in contract["anchors"]}
            assert "Socket_Sight" in anchors and ("Socket_Eye" in anchors) == scope, (tool["id"], "sight anchors")
            assert contract["hold"]["sight_kind"] == tool["hold"]["sight_kind"], tool["id"]
            fire = [event["frame"] for event in contract["clips"][0]["events"] if event["name"] == "Fire"]
            assert fire == [PROFILES[tool["id"]]["motion"]["fire_frame"]], (tool["id"], "Fire marker", fire)
        assert game_qa["checks"]["sight_anchors"]["passed"] and game_qa["checks"]["ads_target_pose"]["passed"], tool["id"]
        assert game_qa["ads"]["eye_distance_range_m"], (tool["id"], "no eye distance keeps the ADS framing")
        checks += 5
    event = PROFILES[tool["id"]].get("use_event")
    if event and rigged:
        assert [(e["name"], e["frame"]) for e in ego["clips"][0]["events"]] == [(event["name"], event["frame"])], tool["id"]
        checks += 1
    elif event:
        # 0.15.0 Toolgrip (Cube Escape 0.85 phase 4): the ego tools' wrists at most 55 degrees in every frame of every clip,
        # their Use event (Fire, Grab, Switch), Inspect_B and a lowered pose with Socket_Hand at least 6 mm lower than rest
        assert ego["clips"][0]["events"] == [{"name": event["name"], "frame": event["frame"],
                                              "seconds": (event["frame"] - 1) / ego["clips"][0]["fps"]}], (tool["id"], "Use event")
        rig = json.loads((package / "qa_viewmodel.json").read_text())
        assert set(rig["wrist_bend"]) == set(rig["hand_sides"]), (tool["id"], "wrist limit on every arm")
        assert all(value["limit_degrees"] <= 55 for value in rig["wrist_bend"].values()), tool["id"]
        assert all(set(clip["wrist_bend_max_degrees"]) == set(rig["hand_sides"])
                   and max(clip["wrist_bend_max_degrees"].values()) <= 55 for clip in rig["ego_clips"]["clips"]), tool["id"]
        assert any(clip["name"].endswith("_Inspect_B") for clip in rig["ego_clips"]["clips"]), (tool["id"], "Inspect_B")
        assert rig["ego_clips"]["lowered"]["hand_drop_m"] >= .006, (tool["id"], "Draw/Holster lowered", rig["ego_clips"]["lowered"])
        checks += 6
    checks += 5
    # contract 4: surface block and maps in standard/full (manifest "surface"), never in quick or older contracts
    world = json.loads((package / "unity_contract.json").read_text())
    # 0.17 Retrace: every contract names both consumer requirements apart; a renamed tool carries its former names
    for path in sorted(package.glob("unity_contract*.json")):
        document = json.loads(path.read_text())
        expected = game_export.consumer_block(tool, document["format"])
        assert document["minimum_consumer"] == expected, (tool["id"], path.name, "minimum_consumer")
        assert document.get("renamed_from") == (game_export.renamed_block(tool) if tool.get("renamed_from") else None), \
            (tool["id"], path.name, "renamed_from")
        if "surface" in document and path.name == "unity_contract_fps.json":
            assert surface.EGO_MAPS_CONSUMER in document["surface"]["minimum_consumer"], (tool["id"], "ego maps consumer")
        checks += 2
    included = manifest["surface"]["included"]
    assert included == (manifest["tier"] != "quick" and world["format"] >= 4), (tool["id"], "surface in the package")
    for contract, variant in ((world, "world"), (ego, "viewmodel")):
        assert ("surface" in contract) == included, (tool["id"], variant, "surface block")
        if not included:
            continue
        block = contract["surface"]
        assert block["version"] == 1 and block["uv1"]["attribute"] == "TEXCOORD_1" and block["uv1"]["margin_px"] >= 4
        assert block["regions"] == surface.REGIONS and block["tangents"]["for"] == "uv1"
        assert not block["uv1"]["islands_rotated"] and block["uv1"]["layout"]["overlap_texels"] == 0
        assert block["uv1"]["shared_with_world"] == ego["surface"]["uv1"]["shared_with_world"]
        assert set(block["channel_map"].values()) <= set(surface.CHANNELS) and block["channel_map"]
        assert all(slot in contract["materials"] for slot in block["channel_map"]), (tool["id"], variant, "channel_map slots")
        maps = block["maps"]
        assert maps["resolution"] == surface.MAP_RESOLUTION[variant], (tool["id"], variant, "map resolution")
        total = 0
        for kind in ("w0", "w1", "fields", "normal"):
            name = maps[kind]
            assert name in manifest["files"] and maps["files"][name] == manifest["files"][name], (tool["id"], name)
            data = (package / name).read_bytes()
            info = surface.png_info(data)
            assert (info["width"], info["height"], info["bit_depth"], info["color_type"]) == \
                (maps["resolution"], maps["resolution"], 8, 6), (tool["id"], name, "8-bit RGBA")
            assert info["chunks"] == ["IHDR", "IDAT", "IEND"], (tool["id"], name, "no colour chunks")
            total += len(data)
        assert total == maps["set_bytes"] <= surface.set_bytes_limit(maps["resolution"]), (tool["id"], variant, "set size")
        assert maps["dilation_px"] == surface.dilation_at(maps["resolution"]), (tool["id"], variant, "dilation")
        assert block["uv1"]["margin_px_at_map"] == surface.margin_px_at(maps["resolution"]), (tool["id"], variant, "margin at map")
        assert block["bake"]["stage"] == "surface_bake" and len(block["bake"]["key"]) == 64
        checks += 12
    if included:
        qa = json.loads((package / "qa_surface.json").read_text())
        assert qa["passed"] and all(check["passed"] for check in qa["checks"].values()), (tool["id"], "qa_surface")
        assert ego["surface"]["maps"]["applies_to"][-1].endswith("_Clips.glb"), (tool["id"], "clips file shares the set")
        checks += 2
    robot_built = bool(tool.get("robot")) and world["format"] >= 4
    if robot_built:
        # 0.14 Fieldfit: the robot variant of the world model (same anchors, hold block and clip; own fit, maps and QA)
        robot = json.loads((package / "unity_contract_robot.json").read_text())
        assert json.loads((package / "qa_game_robot.json").read_text())["passed"], (tool["id"], "qa_game_robot")
        fit = json.loads((package / "qa_geometry_robot.json").read_text())["robot"]
        assert robot["variant"] == "robot" and robot["asset"] == tool["robot"] and robot["model"] == tool["robot"] + "_Game"
        for name in (tool["robot"], tool["robot"] + "_Game"):
            for ext in ("blend", "fbx", "glb"):
                assert name + "." + ext in manifest["files"], (name, ext)
        assert [a["name"] for a in robot["anchors"]] == [a["name"] for a in world["anchors"]], (tool["id"], "robot anchors")
        assert robot["hold"] == world["hold"], (tool["id"], "robot hold block")
        assert [c["name"] for c in robot["clips"]] == [world["clips"][0]["name"]], (tool["id"], "robot clip")
        assert robot["colliders"] and robot["lods"]["LOD0"]["triangles"] <= robot["budget"]["triangles_limit"]
        assert all(fit["checks"].values()) and robot["robot"]["measures_m"] == fit["measures"], (tool["id"], "robot fit")
        measures, limits = fit["measures"], fit["limits"]
        assert measures["stock_behind_hand_m"] <= limits["stock_behind_m"], (tool["id"], "robot stock")
        assert 0 < measures["support_ahead_of_hand_m"] <= limits["support_ahead_m"], (tool["id"], "robot support hand")
        assert measures["barrel_diameter_m"] >= limits["barrel_m"] and measures["body_height_m"] >= limits["body_m"]
        for variant in ("robot", "robot_game"):
            scene = json.loads((package / "ViewerData" / variant / "scene.json").read_text())
            assert scene["clip"] == tool["clip"] and scene["frames"] == 97 and not scene["autoplay"], (tool["id"], variant)
            assert any(entry["id"] == tool["id"] + "/" + variant for entry in index["models"]), (tool["id"], variant)
        assert ("surface" in robot) == included, (tool["id"], "robot surface block")
        if included:
            block = robot["surface"]
            assert block["maps"]["resolution"] == surface.MAP_RESOLUTION["robot"] and not block["uv1"]["shared_with_world"]
            assert block["uv1"]["layout"]["overlap_texels"] == 0 and block["regions"] == surface.REGIONS
            for kind in ("w0", "w1", "fields", "normal"):
                name = block["maps"][kind]
                assert name.startswith(tool["robot"] + "_Game_") and block["maps"]["files"][name] == manifest["files"][name]
            qa = json.loads((package / "qa_surface_robot.json").read_text())
            assert qa["passed"] and all(check["passed"] for check in qa["checks"].values()), (tool["id"], "qa_surface_robot")
        checks += 16
    else:
        assert not any(name.startswith("unity_contract_robot") or "_Robot" in name for name in manifest["files"]), tool["id"]
    if manifest["tier"] != "quick":
        # contract 5: no roundtrip_fps run (ego_rig.py's qa_viewmodel_roundtrip.json, checked above)
        for suffix in ["", *([] if rigged else ["_fps"]), *(["_arrow"] if tool.get("arrow") else []),
                       *(["_robot"] if robot_built else [])]:
            roundtrip = json.loads((package / ("qa_roundtrip" + suffix + ".json")).read_text())
            assert all(result["passed"] is True for result in roundtrip["checks"].values())
            checks += len(roundtrip["checks"])
print(f"OUTPUT_OK {checks} checks, {len(index['models'])} models")
