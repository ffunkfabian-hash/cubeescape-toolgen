"""Game export of a contract 5 first-person model (Toolgen 0.19 Kinetic): the device without arms on the shared arm rig.

Runs as the stage ``game_fps_rig`` (it replaces ``game_fps`` for tools with ``game_contract`` 5):

    blender --background --factory-startup --python toolgen/run_asset.py -- \
        --script toolgen/game_export_rig.py --directory <work> --tool <tool_id> [--preview]

Reads the assembly ``<asset>_FPS.blend`` of toolgen/ego_rig.py and writes

* ``<asset>_FPS_Game.blend/.fbx/.glb``: the device alone, no take - its root ``<asset>_FPS`` (origin = Socket_Hand, device
  axes, unrotated) with the anchors, Anim_* nodes and merged renderers like contract 4 (matte palette or MT_ slots, UV1,
  LOD0/LOD1, the device's own triangle budget of data/game_budget.json viewmodel), and the hand parts root
  ``<asset>_FPS_HandL`` (parts the left hand carries, e.g. HandMag_L) as a second root;
* ``<asset>_FPS_Game_Clips.fbx/.glb``: the assembly as nodes without meshes (the arm rig CubeEscape_EgoArms with the
  device root under Prop_R and the hand parts root under Prop_L), one take ``<Stem>_EgoClips`` with ``<Stem>_Use`` first
  and every ego clip after it;
* ``unity_contract_fps.json`` (format 5: attach, grip, arms_rig, assembly, finger_poses, support_ik, clips with event
  channels, minimum_consumer.shared_arm_rig) and ``qa_game_fps.json`` (renderers, budget, palette, reimport of both files
  against the assembly, the anchor test of the half turn).
"""
import argparse
import json
import math
import sys
import time
import traceback
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
import ego_arms  # noqa: E402
import ego_clips  # noqa: E402
import game_export as ge  # noqa: E402
import surface as surface_maps  # noqa: E402

CONTRACT = 5
SUPPORT_IK_BLEND_FRAMES = 3


def tree(root):
    return [root, *root.children_recursive]


def select_only(scene, objects, active):
    for obj in scene.objects:
        obj.select_set(obj in objects)
    bpy.context.view_layer.objects.active = active


def export_clips(scene, arms, work, name, take, end):
    """The assembly's nodes (empties only) with every clip on one take; FBX take = scene name, glTF animation name."""
    objects = [obj for obj in tree(arms) if obj.type == "EMPTY"]
    actions = {action: (action.use_frame_range, tuple(action.frame_range)) for action in bpy.data.actions}
    saved = (scene.name, scene.frame_start, scene.frame_end)
    try:
        for action in actions:
            action.use_frame_range = False
        scene.name = take
        scene.frame_start, scene.frame_end = 1, end
        ge.set_frame(scene, 1)
        select_only(scene, objects, arms)
        if "FINISHED" not in bpy.ops.export_scene.gltf(
                filepath=str(work / (name + ".glb")), export_format="GLB", use_selection=True, export_yup=True,
                export_extras=True, export_animations=True, export_morph=False, export_cameras=False, export_lights=False,
                use_active_scene=True, export_animation_mode="ACTIVE_ACTIONS", export_merge_animation="ACTION",
                export_nla_strips_merged_animation_name=take, export_frame_range=True, export_force_sampling=True):
            raise RuntimeError("glTF export of the clips failed")
        if "FINISHED" not in bpy.ops.export_scene.fbx(
                filepath=str(work / (name + ".fbx")), use_selection=True, object_types={"EMPTY"}, axis_forward="-Z",
                axis_up="Y", global_scale=1, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                bake_space_transform=False, use_mesh_modifiers=False, use_custom_props=True, add_leaf_bones=False,
                bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                bake_anim_force_startend_keying=True, bake_anim_step=1, bake_anim_simplify_factor=0):
            raise RuntimeError("FBX export of the clips failed")
    finally:
        scene.name = saved[0]
        scene.frame_start, scene.frame_end = saved[1], saved[2]
        for action, (manual, frame_range) in actions.items():
            action.use_frame_range = manual
            if manual:
                action.frame_start, action.frame_end = frame_range
        ge.set_frame(scene, scene.frame_start)


def export_device(scene, roots, work, name):
    """The device file: both roots, no animation (like game_export.export_files without a clip)."""
    objects = {obj for root in roots for obj in tree(root)}
    select_only(scene, objects, roots[0])
    uv1 = any(obj.type == "MESH" and surface_maps.UV1_NAME in obj.data.uv_layers for obj in objects)
    for obj in objects:
        if uv1 and obj.type == "MESH":
            obj.data.uv_layers.active = obj.data.uv_layers[surface_maps.UV1_NAME]
    if "FINISHED" not in bpy.ops.export_scene.gltf(
            filepath=str(work / (name + ".glb")), export_format="GLB", use_selection=True, export_yup=True,
            export_extras=True, export_animations=False, export_morph=True, export_cameras=False, export_lights=False,
            use_active_scene=True, export_tangents=uv1):
        raise RuntimeError("glTF export failed")
    if "FINISHED" not in bpy.ops.export_scene.fbx(
            filepath=str(work / (name + ".fbx")), use_selection=True, object_types={"EMPTY", "MESH"}, axis_forward="-Z",
            axis_up="Y", global_scale=1, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
            bake_space_transform=False, use_mesh_modifiers=False, use_custom_props=True, add_leaf_bones=False,
            bake_anim=False):
        raise RuntimeError("FBX export failed")


def sample_frames(ego):
    frames = {1, 14, 49, 97}
    for clip in ego["clips"]:
        frames |= {clip["frame_start"] + round(clip["length"] * share) for share in (0, .25, .5, .75, 1)}
        frames |= {event["frame"] for event in clip["events"]}
    return sorted(frames)


def clip_entries(ego, game, take, fps, animated_nodes, use_events):
    """clips[]: the Use clip first (take frames 0-96), then every ego clip; all in the clips file."""
    entries = [{"name": ego["use"], "suffix": "Use", "state": "Use", "file": game + "_Clips.fbx", "glb": game + "_Clips.glb",
                "take": take, "frame_start": 1, "frame_end": 97, "frames": 97, "take_frame_start": 0, "take_frame_end": 96,
                "take_seconds_start": 0.0, "fps": fps, "duration_seconds": 96 / fps, "loop": False, "autoplay": False,
                "from_pose": "rest", "to_pose": "rest", "from": "rest", "to": "rest", "reticle_free": True,
                "interruptible": True, "support_forearm_visible": False,
                "events": [{"name": name, "frame": frame, "seconds": (frame - 1) / fps, "channel": "action"}
                           for name, frame in use_events],
                "animated_nodes": animated_nodes, "root_curves": []}]
    for clip in ego["clips"]:
        entries.append({"name": clip["name"], "suffix": clip["suffix"], "state": clip["suffix"],
                        "file": game + "_Clips.fbx", "glb": game + "_Clips.glb", "take": take,
                        "frame_start": clip["frame_start"], "frame_end": clip["frame_end"], "frames": clip["length"] + 1,
                        "take_frame_start": clip["frame_start"] - 1, "take_frame_end": clip["frame_end"] - 1,
                        "take_seconds_start": (clip["frame_start"] - 1) / fps, "fps": fps,
                        "duration_seconds": clip["length"] / fps, "loop": clip["loop"], "autoplay": False,
                        "from_pose": clip["from"], "to_pose": clip["to"], "from": clip["from"], "to": clip["to"],
                        "reticle_free": clip["reticle_free"], "interruptible": clip["interruptible"],
                        "support_forearm_visible": clip["support_forearm_visible"],
                        "events": [{"name": event["name"], "frame": event["frame"],
                                    "seconds": (event["frame"] - clip["frame_start"]) / fps, "channel": event["channel"]}
                                   for event in clip["events"]],
                        "animated_nodes": animated_nodes, "root_curves": []})
    return entries


def uv1_for_copies(roots):
    """Hand parts are copies of device parts (ce_copy_of): they take the source's UV1 (same topology)."""
    names = {obj.name: obj for root in roots for obj in tree(root) if obj.type == "MESH"}
    for obj in names.values():
        source = names.get(obj.get("ce_copy_of", ""))
        if source is None or surface_maps.UV1_NAME not in source.data.uv_layers:
            continue
        layer = obj.data.uv_layers.get(surface_maps.UV1_NAME) or obj.data.uv_layers.new(name=surface_maps.UV1_NAME)
        values = [0.0] * (len(source.data.loops) * 2)
        source.data.uv_layers[surface_maps.UV1_NAME].data.foreach_get("uv", values)
        layer.data.foreach_set("uv", values)


def check_clips_import(checks, kind, path, expected, take, end):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(filepath=str(path)) if kind == "glb" else bpy.ops.import_scene.fbx(filepath=str(path))
    if "FINISHED" not in result:
        raise RuntimeError(f"{kind} import failed")
    scene = bpy.context.scene
    found = {ge.base_name(obj.name): obj for obj in scene.objects}
    meshes = sorted(obj.name for obj in scene.objects if obj.type == "MESH")
    missing = sorted(name for name in expected["nodes"] if name not in found)
    parents = sorted(name for name, parent in expected["parents"].items() if name in found and parent
                     and (ge.base_name(found[name].parent.name) if found[name].parent else None) != parent)
    actions = [ge.action_of(obj) for obj in found.values() if ge.action_of(obj)]
    start = min((float(action.frame_range[0]) for action in actions), default=1.0)
    length = max((float(action.frame_range[1]) for action in actions), default=0.0) - start + 1
    worst = 0.0
    for frame, matrices in expected["matrices"].items():
        ge.set_frame(scene, frame + start - 1)
        for name, matrix in matrices.items():
            if name in found:
                worst = max(worst, ge.matrix_error(ge.matrix_list(found[name].matrix_world), matrix))
    names = ([animation.get("name") for animation in ge.glb_document(path).get("animations", [])] if kind == "glb"
             else sorted({action.name.split("|")[-1] for action in actions}))
    checks.add(f"roundtrip_clips_{kind}", not missing and not parents and not meshes and worst <= ge.ROUNDTRIP_MATRIX_TOLERANCE
               and abs(length - end) < .01 and names == [take], missing=missing[:10], wrong_parent=parents[:10],
               meshes=meshes[:5], max_matrix_error=worst, frames=length, takes=names, sampled_frames=len(expected["matrices"]))


def unity_matrix(position, rotation_xyzw):
    """4x4 of a Unity transform (left-handed values as the contract writes them), as a matrix acting on Unity points."""
    x, y, z, w = rotation_xyzw
    from mathutils import Quaternion
    return Matrix.LocRotScale(Vector(position), Quaternion((w, x, y, z)), Vector((1, 1, 1)))


def to_unity(matrix):
    """A Blender transform in Unity axes: M T M^T (M = game_export.TO_UNITY)."""
    m = Matrix([list(row) + [0.0] for row in ge.TO_UNITY] + [[0.0, 0.0, 0.0, 1.0]])
    return m @ matrix @ m.transposed()


def anchor_test(checks, contract, expected):
    """Self-consistency of the contract for the half turn (Vertrag-5-Entwurf 2.2): Prop_R at rest (frame 0 of the Use clip),
    ``attach`` and each anchor's chain of Unity values (anchors and nodes up to the device root) compose to the anchor's
    Unity point in the assembly (unity_position of the authored world point). That shows the arm rig and the device share
    one conversion, so one half turn at the root of the ASSEMBLED hierarchy is the rule; it is no measurement of Unity's
    FBX import - Cube Escape measures that in E2 (anchor test of the Vertrag-5-Entwurf 8.2). Reported besides: how far a
    second half turn at the device root would move the anchors."""
    prop = to_unity(expected["prop_r_rest"])
    attach = unity_matrix(contract["attach"]["unity"]["localPosition"], contract["attach"]["unity"]["localRotation"])
    entries = {entry["name"]: entry for entry in [*contract["anchors"], *contract["nodes"]]}

    def chain(name):
        matrix = Matrix()
        while name in entries:
            entry = entries[name]
            matrix = unity_matrix(entry["unity"]["localPosition"], entry["unity"]["localRotation"]) @ matrix
            name = entry["parent"]
        return matrix
    worst = double = 0.0
    for anchor in contract["anchors"]:
        local = chain(anchor["name"])
        authored = Vector(ge.unity_position(expected["rest_anchors"][anchor["name"]]))
        worst = max(worst, ((prop @ attach @ local).to_translation() - authored).length)
        turned = prop @ attach @ Matrix.Rotation(math.pi, 4, "Y") @ local
        double = max(double, (turned.to_translation() - authored).length)
    checks.add("anchor_half_turn", worst <= 2e-4, max_error_m=worst,
               second_turn_at_device_root_moves_anchors_m=round(double, 4), kind="self-consistency of the contract values",
               rule="one 180 degree turn about Unity's Y at the root of the ASSEMBLED hierarchy (arms + device); none at "
                    "the device root under Prop_R; Unity's import is measured in Cube Escape E2")


def build_contract5(tool, work, ego, arms_contract, rig_report, files, base_contract, fps, animated_nodes, use_events,
                    assembly, device_name, handl_name):
    game = tool["asset"] + "_FPS_Game"
    take = ego_clips.clip_stem(tool) + "_EgoClips"
    entries = clip_entries(dict(ego, use=tool.get("fps_clip") or tool["clip"]), game, take, fps, animated_nodes, use_events)
    document = dict(base_contract)
    data = ego_clips.load()
    enlargement = float(json.loads((work / "qa_geometry_fps.json").read_text()).get("enlargement", 1.0))
    document.update({
        "format": CONTRACT, "clips": entries,
        "ego_clips": {"format": data["format"], "file": game + "_Clips.fbx", "glb": game + "_Clips.glb", "take": take,
                      "timeline": [1, ego["timeline_end"]], "fps": fps,
                      "names": {entry["suffix"]: entry["name"] for entry in entries}, "poses": data["poses"],
                      "reload_part": ego.get("reload_part"),
                      "transitions": ego_clips.transitions(ego["clips"]),
                      "rules": "Contract 5: every clip (the Use clip first) is in the clips file and animates the whole "
                               "assembly: Shoulder_<S> (location and rotation), UpperArm/LowerArm/Hand/finger and thumb "
                               "rotations, the device's Anim_* nodes and the visibility scale of visibility_nodes. Never the "
                               "rig root, Prop_R/Prop_L, the device root or materials. Every clip starts and ends in its "
                               "named pose (rest = frame 0 of the Use clip, for every node). Loop clips: "
                               + ", ".join(entry["suffix"] for entry in entries if entry["loop"])
                               + " (last sample = first). Nothing plays by itself.",
                      "unity": "Import the clips file Generic with bakeAxisConversion and optimizeGameObjects off; split "
                               "its take with ModelImporter.clipAnimations (firstFrame/lastFrame = take start + "
                               "take_frame_start/take_frame_end). Its node paths are 'assembly': build the prefab as "
                               "arm package + device under Prop_R (local = the device root's transform in the clips file "
                               "at frame 0, checked against attach) + hand parts root under Prop_L, so the paths match.",
                      "older_consumers": ego_arms.OLDER_CONSUMERS},
        "attach": rig_report["attach_contract"], "attach_left": rig_report.get("attach_left"),
        "grip": rig_report["grip_contract"],
        "arms_rig": {"id": arms_contract["rig"]["id"], "version": arms_contract["rig"]["version"],
                     "hash": arms_contract["rig"]["hash"], "package": "ego_arms/unity_contract_arms.json"},
        "assembly": assembly, "device_root": device_name, "hand_parts_root": handl_name,
        "finger_poses": rig_report["finger_poses"],
        "support_ik": {"mode": rig_report["grip_contract"]["L"]["mode"], "blend_frames": SUPPORT_IK_BLEND_FRAMES,
                       "events": "rig channel: HandOff = last frame with the support hand on its grip, HandOn = first "
                                 "frame back; the IK weight falls over blend_frames after HandOff and rises over "
                                 "blend_frames from HandOn; Toolgen keeps the hand on the grip in both blends",
                       "target": "Hand_L = device root x grip.L (position and rotation)"},
        "frame_size": {"value": 1.0, "note": "contract 5: the factor 1.4 is baked in; hip.scale does not apply"},
        "device_scale": {"factor": rig_report["device_factor"], "tool_scale": rig_report["tool_scale"],
                         "rig_scale": rig_report["rig_scale"], "fps_enlargement": enlargement,
                         "world_factor": round(rig_report["device_factor"] * enlargement, 6),
                         "note": "factor = the scale applied to the fps step's model (tool_scale relative to the hand x the "
                                 "rig's baked 1.4), as tool_scale in contract 4; surface_bake places the decals with it. "
                                 "world_factor = the device against its world model (factor x the fps step's own "
                                 "enlargement, Portalkanone 1.5)"},
        "hand_parts": rig_report["hand_parts"],
        "event_channels": {"action": "EquipmentActionEvent (default when channel is missing)",
                           "rig": "read only by the support-hand IK (HandOff, HandOn)"},
    })
    device = ego_arms.load()["devices"].get(tool["id"], {})
    if "fire" in device:
        document["fire"] = ego_arms.fire_block(device["fire"], entries, fps)
    document["minimum_consumer"] = dict(document.get("minimum_consumer", {}), shared_arm_rig=ge.SHARED_ARM_CONSUMER)
    document["older_consumers"] = ego_arms.OLDER_CONSUMERS
    document["files"] = {kind: {"path": path.name, "sha256": ge.file_sha256(path)} for kind, path in files.items()}
    return document


def main():
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description="Game export of a contract 5 first-person model")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    work = args.directory.resolve()
    checks = ge.Checks()
    report = {"tool": args.tool, "variant": "viewmodel", "contract_format": CONTRACT, "passed": False}
    try:
        tools = {tool["id"]: tool for tool in json.loads(ge.TOOLS_PATH.read_text())["tools"]}
        tool = tools[args.tool]
        palette = json.loads(ge.PALETTE_PATH.read_text())
        budget = json.loads(ge.BUDGET_PATH.read_text())
        errors = ge.validate_palette(palette)
        checks.add("palette", not errors, errors=errors)
        palette = ge.tool_palette(palette, tool, 4)
        rig_qa = json.loads((work / "qa_viewmodel.json").read_text())
        asset = tool["asset"] + "_FPS"
        game = asset + "_Game"
        captured, world_info = ge.world_uv1(work, tool["asset"])
        bpy.ops.wm.open_mainfile(filepath=str(work / (asset + ".blend")))
        scene = bpy.context.scene
        root = scene.objects[asset]
        arms = scene.objects[ego_arms.load()["rig"]["asset"]]
        handl = scene.objects.get(tool["asset"] + "_FPS_HandL")
        ego = json.loads(root["toolgen_ego_clips"])
        del root["toolgen_ego_clips"]
        end = ego["timeline_end"]
        fps = scene.render.fps / scene.render.fps_base
        take = ego_clips.clip_stem(tool) + "_EgoClips"
        use_events = sorted((marker.name, marker.frame) for marker in scene.timeline_markers)
        # the assembly as the clips file sees it
        empties = [obj for obj in tree(arms) if obj.type == "EMPTY"]
        assembly = [{"path": "/".join(reversed([o.name for o in [obj, *iter_parents(obj)] if o != arms])) or "",
                     "name": obj.name, "parent": obj.parent.name if obj.parent else None} for obj in empties]
        expected_clips = {"nodes": [obj.name for obj in empties],
                          "parents": {obj.name: obj.parent.name if obj.parent else None for obj in empties},
                          "matrices": {}}
        for frame in sample_frames(ego):
            ge.set_frame(scene, frame)
            expected_clips["matrices"][frame] = {obj.name: ge.matrix_list(obj.matrix_world) for obj in empties}
        ge.set_frame(scene, 1)
        rest_anchors = {obj.name: list(obj.matrix_world.translation) for obj in tree(root) if obj.name.startswith("Socket_")}
        prop_rest = scene.objects["Prop_R"].matrix_world.copy()
        attach = root.matrix_local.copy()
        animated_nodes = sorted(obj.name for obj in empties if ge.action_of(obj))
        export_clips(scene, arms, work, game + "_Clips", take, end)
        # the device alone: groups while the actions still mark the moving parts
        frames = list(range(1, 98))
        roots = [root, *([handl] if handl else [])]
        groups = [group for item in roots for group in ge.classify(item, frames, item.name if item != root else asset)]
        ge.set_frame(scene, 1)
        for item in roots:
            item.parent = None
            item.matrix_world = Matrix()
        keep = {obj for item in roots for obj in tree(item)}
        for obj in list(bpy.data.objects):
            if obj not in keep:
                bpy.data.objects.remove(obj)
        bpy.ops.outliner.orphans_purge(do_recursive=True)       # the arm rig's look materials (palette names)
        for obj in keep:
            obj.animation_data_clear()
            if obj.type == "MESH" and obj.data.shape_keys:
                obj.data.shape_keys.animation_data_clear()
        bpy.context.view_layer.update()
        camera = json.loads((work / "viewmodel_camera.json").read_text())
        source = ge.record_source(scene, root, [g for g in groups if g.owner in tree(root)], [1], camera["near_clip_m"])
        meshes = [obj for item in roots for obj in tree(item) if obj.type == "MESH"]
        source.update({"frame_start": 1, "frame_end": 1, "fps": fps, "markers": [], "key_frames": [],
                       "root_properties": {key: str(root[key]) for key in root.keys() if key.startswith("ce_")},
                       "mesh_count": len(meshes), "node_count": sum(len(tree(item)) for item in roots),
                       "triangles": sum(ge.triangles(obj.data) for obj in meshes)})
        uv1_info = ge.make_uv1(root, captured)
        uv1_for_copies(roots)
        if world_info:
            uv1_info["world_sha256"] = world_info["sha256"]
            if uv1_info.get("shared_with_world"):
                uv1_info["islands_rotated_max_degrees"] = world_info["islands_rotated_max_degrees"]
        materials = ge.palette_materials(palette)
        used = sorted({name for item in roots for name in ge.remap_materials(item, palette, materials)})
        collection = root.users_collection[0]
        ge.set_frame(scene, 1)
        renderers = [ge.merge_group(group, collection) for group in groups]
        merged = sum(ge.triangles(obj.data) for obj in renderers)
        limit = budget["viewmodel"][tool["id"]]
        renderers, kept = ge.reduce_to_budget(renderers, limit, collection)
        lods = ge.build_lods(renderers, collection)
        # like game_export.export: the collapse keeps UV1 but may fold single triangles; unfold them before the checks
        folds = {obj.name: surface_maps.untangle_uv1(obj.data) for obj in [*renderers, *lods]}
        uv1_info["decimation_folds"] = {name: {"before": a, "after": b} for name, (a, b) in folds.items() if a or b}
        bpy.ops.outliner.orphans_purge(do_recursive=True)
        files = {"blend": work / (game + ".blend"), "fbx": work / (game + ".fbx"), "glb": work / (game + ".glb")}
        bpy.ops.wm.save_as_mainfile(filepath=str(files["blend"]), compress=False)
        export_device(scene, roots, work, game)
        ge.check_uv1(checks, {"root": asset, "uv1": uv1_info})      # surface_bake reads checks.uv1_source like contract 4
        files.update({"clips_fbx": work / (game + "_Clips.fbx"), "clips_glb": work / (game + "_Clips.glb")})
        from version import CODENAME, VERSION
        source_info = {"asset": asset, "blend": asset + ".blend", "sha256": ge.file_sha256(work / (asset + ".blend")),
                       "nodes": source["node_count"], "meshes": source["mesh_count"], "triangles": source["triangles"],
                       "materials": used, "palette": {"path": "data/game_palette.json", "sha256": ge.file_sha256(ge.PALETTE_PATH)},
                       "version": f"{VERSION} {CODENAME}"}
        budget_info = {"source": "data/game_budget.json", "sha256": ge.file_sha256(ge.BUDGET_PATH), "triangles_limit": limit,
                       "merged_triangles": merged, "kept_ratio": round(kept, 4),
                       "triangles_lod0": sum(ge.triangles(obj.data) for obj in renderers),
                       "scope": "the device alone (contract 5); the arms are ego_arms (12000), together at most 32000"}
        viewmodel = {key: camera[key] for key in ("vertical_fov_degrees", "horizontal_fov_degrees", "reference_aspect",
                                                  "near_clip_m", "override", "unity", "player_fov_dependency",
                                                  "aspect_policy", "camera_offset_m", "runtime")}
        viewmodel["source"] = "viewmodel_camera.json"
        base = ge.build_contract(dict(tool, asset=asset, clip=None), source_info, root, renderers, lods, [], None, palette,
                                 files, budget_info, viewmodel, None, 4, (), None,
                                 ge.renamed_block(tool) if tool.get("renamed_from") else None, None)
        base["model"] = game
        base["visibility_nodes"] = sorted(obj.name for item in roots for obj in tree(item) if obj.get("ce_visibility_animation"))
        base["uv1"] = uv1_info
        arms_contract = {"rig": rig_qa["rig"]}
        rig_report = contract_blocks(rig_qa, attach, handl)
        document = build_contract5(tool, work, ego, arms_contract, rig_report, files, base, fps, animated_nodes, use_events,
                                   assembly, asset, handl.name if handl else None)
        if tool.get("concept"):
            document["concept"] = ge.concept_block(tool, json.loads((work / "qa_geometry.json").read_text())["concept"])
        (work / "unity_contract_fps.json").write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
        expected = {"root": asset, "renderers": [obj.name for obj in renderers], "lods": [obj.name for obj in lods],
                    "groups": [{"name": group.name, "renderer": group.name + "_LOD0"} for group in groups
                               if group.owner in tree(root)],
                    "materials": {obj.name: [m.name for m in obj.data.materials] for obj in [*renderers, *lods]},
                    "clip": None, "viewmodel": True, "camera": None, "root_free_required": True, "uv1": uv1_info,
                    "socket_surface": None, "sockets_on_tool_required": False, "max_renderers": ge.MAX_RENDERERS_VIEWMODEL,
                    "sample_frames": [1]}
        ge.check_budget(checks, document)
        checks.add("device_without_arms", not [obj.name for item in roots for obj in tree(item)
                                               if obj.name.startswith(("UpperArm_", "LowerArm_", "WristYoke_", "Hand_", "Fingers_",
                                                                       "Thumb_", "Viewmodel_", "Shoulder_"))],
                   note="contract 5: arms, hands and the viewmodel carrier live in ego_arms")
        socket = next(anchor for anchor in document["anchors"] if anchor["name"] == "Socket_Hand")
        checks.add("socket_hand_at_origin", max(abs(v) for v in socket["blender"]["location"]) <= 1e-4,
                   location=socket["blender"]["location"])
        anchor_test(checks, document, {"attach_matrix": attach, "prop_r_rest": prop_rest, "rest_anchors": rest_anchors})
        for kind in ("glb", "fbx"):
            try:
                ge.check_import(checks, kind, files[kind], source, expected)
            except Exception as error:  # noqa: BLE001
                traceback.print_exc()
                checks.add_error(f"roundtrip_{kind}", error)
            try:
                check_clips_import(checks, kind, files["clips_" + kind], expected_clips, take, end)
            except Exception as error:  # noqa: BLE001
                traceback.print_exc()
                checks.add_error(f"roundtrip_clips_{kind}", error)
        report.update({"renderers": {"LOD0": expected["renderers"], "LOD1": expected["lods"]},
                       "triangles": {"source": source["triangles"], "LOD0": document["lods"]["LOD0"]["triangles"],
                                     "LOD1": document["lods"]["LOD1"]["triangles"]},
                       "materials": sorted(document["materials"]), "colliders": 0})
        if args.preview:
            report["preview"] = ge.render_preview(work, asset, work / "preview_game_fps.png", "unity_contract_fps.json",
                                                  True).name
    except Exception as error:  # noqa: BLE001
        traceback.print_exc()
        checks.add_error("export", error)
    report.update({"passed": checks.passed, "checks": checks.results, "seconds": round(time.perf_counter() - started, 3)})
    (work / "qa_game_fps.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    failed = [name for name, result in checks.results.items() if not result["passed"]]
    if failed:
        print(f"GAME_EXPORT_FAILED {args.tool}: {', '.join(failed)}", flush=True)
        sys.exit(1)
    print(f"GAME_EXPORT_OK {args.tool} (contract 5): {report['renderers']['LOD0']} triangles={report['triangles']} "
          f"{report['seconds']:.1f}s", flush=True)


def iter_parents(obj):
    current = obj.parent
    while current is not None:
        yield current
        current = current.parent


def contract_blocks(rig_qa, attach, handl):
    """attach / grip blocks of the contract from ego_rig.py's report (Blender and Unity values)."""
    location, rotation, scale = attach.decompose()
    attach_block = {"bone": "Prop_R", "node": rig_qa["attach"]["node"], "blender": rig_qa["attach"]["blender"],
                    "unity": rig_qa["attach"]["unity"],
                    "note": "the device root's local transform under Prop_R (constant in every clip); the clips file "
                            "carries the same transform, this is the check value (<= 0.1 mm / 0.05 deg)"}
    grips = {}
    for side, entry in rig_qa["grips"].items():
        matrix = Matrix(entry["matrix_device"])
        loc, rot, _ = matrix.decompose()
        grips[side] = {"mode": entry["mode"], "node": f"Hand_{side}", "pose": entry["pose"],
                       "blender": {"location": [round(v, 6) + 0.0 for v in loc],
                                   "rotation_wxyz": [round(v, 7) + 0.0 for v in rot]},
                       "unity": {"localPosition": [round(v, 6) + 0.0 for v in ge.unity_position(loc)],
                                 "localRotation": ge.unity_rotation([list(row) for row in rot.to_matrix()])},
                       "space": "Hand_<S> in the device root's frame (position and rotation; rotation = the palm's facing)",
                       "tolerance": {"position_m": .008, "rotation_degrees": 5.0}}
        if side == "L":
            grips[side]["socket"] = "Socket_SupportHand"
    parts = [{"name": obj.name, "parent": obj.parent.name if obj.parent else None,
              "visibility_animation": bool(obj.get("ce_visibility_animation")), **ge.local_transform(obj)}
             for obj in tree(handl) if obj.type == "EMPTY"] if handl else []
    return {"attach_contract": attach_block, "grip_contract": grips, "finger_poses": rig_qa["finger_poses"],
            "device_factor": rig_qa["scale"]["device_factor"], "tool_scale": rig_qa["scale"]["tool_scale"],
            "rig_scale": rig_qa["scale"]["rig_scale"], "hand_parts": parts,
            "attach_left": {"bone": "Prop_L", "node": handl.name, "blender": {"location": [0.0, 0.0, 0.0],
                                                                         "rotation_wxyz": [1.0, 0.0, 0.0, 0.0]}}
            if handl else None}


if __name__ == "__main__":
    main()
