"""Contract 5 first-person build of a device on the shared arm rig (Toolgen 0.19 Kinetic, E1 pilot).

Replaces first_person.py for tools with ``game_contract`` 5 (generate_tools.py stage ``ego_rig``). Runs like the other
toolgen steps in the tool's work folder:

    blender --background --factory-startup --python toolgen/run_asset.py -- \
        --script toolgen/ego_rig.py --directory <work> --tool <tool_id>

Reads ``<asset>_FPS.blend`` (the device of the fps stage, with its Use mechanics) and writes the same file as the
assembly: the shared arm rig of toolgen/ego_arms.py (root CubeEscape_EgoArms, camera space) with the device root
``<asset>_FPS`` hanging at Prop_R (origin = Socket_Hand, device axes) and hand parts under ``<asset>_FPS_HandL`` at
Prop_L. Every clip (the Use clip on frames 1-97, the ego clips of data/ego_clips.json after it, Reload/ReloadEmpty from
data/ego_arms.json devices) moves the whole arm chain frame by frame: the device follows only the right chain, the left
hand holds its grip (support) or follows the reload choreography between the rig events HandOff and HandOn; fingers close
on the real device mesh (BVH), the forearm lags the hand a little (servo). Also writes qa_viewmodel.json (hand touch,
wrist, framing, events, magazine swap), qa_viewmodel_roundtrip.json (FBX/glTF reimport of the assembly),
viewmodel_camera.json and the exports ``<asset>_FPS.fbx/.glb`` (assembly, Use clip).

The device is scaled by tool_scale x rig.scale about the grip, so the picture is the game picture (Cube Escape frame size
1.0): data/ego_arms.json devices.<tool>.
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
import ads_view  # noqa: E402 - the ADS rule (pure numpy)
import ego_arms  # noqa: E402
import ego_clips  # noqa: E402
import first_person as fp  # noqa: E402 - shared helpers (camera, clip matrix, ADS, recoil, clip keys)
from motion_profiles import envelope, settle  # noqa: E402

USE_FRAMES = (1, 97)
TOUCH_LIMIT_M = .008
CARDAN_TOLERANCE_DEGREES = .5    # rig version 2: the yoke's and the hand's local turn off their single axis (interpolation)
PENETRATION_STEP_M = .0005
VISIBLE_FRACTION = .5                # proximal forearm half stays out of the frame
FOREARM_LAG = (2, .3)                 # servo: the forearm direction keeps this share of its target two frames earlier
RIG_EVENTS = ego_arms.RIG_EVENTS
CHOREOGRAPHY = ego_arms.CHOREOGRAPHY_MOTIONS    # clips whose left hand leaves its grip (reload, 0.27 the press-check)
SWAP_TOLERANCE_M = .002
CURL_STEPS = 60
CURL_LEAD = .25                      # each joint further out starts curling this share of the sweep later
# 0.25: the clips aimed down sights keep the ADS rule, not the framing rule (validate)
AIM_MOTIONS = ("aim_in", "aim_idle", "aim_fire", "aim_out", "aim_auto_fire", "aim_burst")


# --------------------------------------------------------------------------------------------- data
def load_inputs(tool_id):
    tools = {tool["id"]: tool for tool in json.loads((ROOT / "data/tools.json").read_text())["tools"]}
    viewmodels = json.loads((ROOT / "data/viewmodels.json").read_text())
    arms = ego_arms.load()
    if tool_id not in arms["devices"]:
        raise RuntimeError(f"{tool_id}: no contract 5 entry in data/ego_arms.json devices")
    return tools[tool_id], viewmodels["tools"][tool_id], viewmodels, arms["rig"], arms["devices"][tool_id]


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def interpolate(keys, frame):
    """Piecewise smoothstep between [frame, value] keys (clip-relative frames); values: dicts of numbers or lists."""
    if frame <= keys[0][0]:
        return keys[0][1], keys[0][1], 0.0
    for (a, va), (b, vb) in zip(keys, keys[1:]):
        if a <= frame <= b:
            return va, vb, smooth((frame - a) / (b - a)) if b > a else 1.0
    return keys[-1][1], keys[-1][1], 0.0


def mix(a, b, t):
    keys = set(a) | set(b)
    return {key: (1 - t) * a.get(key, 0.0) + t * b.get(key, 0.0) for key in keys}


# --------------------------------------------------------------------------------------------- device preparation
def scale_device(root, factor):
    """Scales every part of the device about the camera origin like first_person.py's tool_scale (locations, meshes with
    their shape keys, location keys); the grip moves, rest_pose puts it back at the profile's hand position."""
    for obj in root.children_recursive:
        obj.location *= factor
        if obj.type == "MESH":
            obj.data.transform(Matrix.Scale(factor, 4), shape_keys=True)
        for curve in fp.curves_of(obj):
            if curve.data_path == "location":
                for key in curve.keyframe_points:
                    key.co.y *= factor
                    key.handle_left.y *= factor
                    key.handle_right.y *= factor
    bpy.context.view_layer.update()


def reroot(scene, root, frame_matrix):
    """Moves the device so ``frame_matrix`` (Socket_Hand of the fps model) becomes the root's origin and axes: static
    children are transformed once, animated direct children are re-keyed frame by frame over the Use clip."""
    inverse = frame_matrix.inverted()
    animated = [obj for obj in root.children if obj.animation_data and obj.animation_data.action]
    baked = {}
    for obj in animated:
        samples = []
        for frame in range(USE_FRAMES[0], USE_FRAMES[1] + 1):
            scene.frame_set(frame)
            samples.append(inverse @ obj.matrix_world)
        baked[obj] = samples
    scene.frame_set(USE_FRAMES[0])
    for obj in root.children:
        if obj in baked:
            continue
        obj.matrix_world = inverse @ obj.matrix_world
    for obj, samples in baked.items():
        obj.animation_data.action = None
        obj.rotation_mode = "QUATERNION"
        previous = None
        for frame, matrix in zip(range(USE_FRAMES[0], USE_FRAMES[1] + 1), samples):
            location, rotation, scale = matrix.decompose()
            if previous is not None and rotation.dot(previous) < 0:
                rotation = -rotation
            previous = rotation
            obj.matrix_parent_inverse = Matrix()
            obj.location, obj.rotation_quaternion, obj.scale = location, rotation, scale
            for path in ("location", "rotation_quaternion", "scale"):
                obj.keyframe_insert(data_path=path, frame=frame)
    bpy.context.view_layer.update()


def rest_pose(scene, profile):
    """Socket_Hand at rest in camera space (first_person.py's hold): at the profile's hand position, the muzzle ray on the
    aim target, rolled by roll_degrees."""
    local_muzzle = scene.objects["Socket_Muzzle"].matrix_world.translation.copy()      # device frame = world now
    position = Vector(profile["hand"])
    target = Vector(profile.get("aim_target_m", (0, -4, 0)))
    rotation = (target - position).to_track_quat("-Y", "Z") @ Quaternion((0, -1, 0), math.radians(profile["roll_degrees"]))
    for _ in range(12):
        ray = rotation @ Vector((0, -1, 0))
        desired = (target - position - rotation @ local_muzzle).normalized()
        rotation = ray.rotation_difference(desired) @ rotation
    return Matrix.LocRotScale(position, rotation, Vector((1, 1, 1)))


def device_meshes(root):
    return [obj for obj in root.children_recursive if obj.type == "MESH"]


def world_bvh(objects, inverse=None):
    graph = bpy.context.evaluated_depsgraph_get()
    points, polygons = [], []
    for obj in objects:
        evaluated = obj.evaluated_get(graph)
        matrix = evaluated.matrix_world if inverse is None else inverse @ evaluated.matrix_world
        offset = len(points)
        points += [matrix @ vertex.co for vertex in evaluated.data.vertices]
        polygons += [tuple(offset + index for index in polygon.vertices) for polygon in evaluated.data.polygons]
    return BVHTree.FromPolygons(points, polygons, epsilon=0.0)


# --------------------------------------------------------------------------------------------- grips
def grip_matrix(spec, device_bvh, nodes, side, gap, factor):
    """Hand pose in device space for a grip spec: the palm contact (GripContact_<S>) ``gap`` outside the outer surface
    met by a ray along ``palm`` towards ``center``, the palm facing the device, the hand's X along ``axis``."""
    n = Vector(spec["palm"]).normalized()
    center = Vector(spec["center"]) * factor            # device units of the fps model -> the scaled device
    # from outside inwards: the first hit is the outer surface, not a part inside the shell
    hit, _, _, _ = device_bvh.ray_cast(center - n * .5, n, .5)
    if hit is None:
        raise RuntimeError(f"grip of Hand_{side}: no device surface from {tuple(center)} along {tuple(-n)}")
    y = -n
    x = Vector(spec["axis"])
    x = (x - y * x.dot(y)).normalized()
    z = x.cross(y)
    rotation = Matrix((x, y, z)).transposed()
    contact = nodes[f"GripContact_{side}"].location.copy()
    origin = hit - n * gap - rotation @ contact
    return Matrix.LocRotScale(origin, rotation.to_quaternion(), Vector((1, 1, 1)))


def hand_link_meshes(state, side):
    names = {obj.name: obj for obj in state["renderers"]}
    fingers = [[names[ego_arms.finger_node(side, finger, link) + "_Mesh"] for link in range(ego_arms.FINGER_LINKS)]
               for finger in range(ego_arms.FINGERS)]
    thumb = [names[ego_arms.thumb_node(side, link) + "_Mesh"] for link in range(ego_arms.THUMB_LINKS)]
    return fingers, thumb, names[f"Hand_{side}_Mesh"]


def overlaps(objects, device_bvh, grow=PENETRATION_STEP_M):
    return any(device_bvh.overlap(ego_arms.bvh(obj, grow)) for obj in objects)


def close_hand(state, side, hand_matrix, device_bvh, start, limits, skip=()):
    """Sets Hand_<S> to ``hand_matrix`` (device at the origin) and closes fingers and thumb on the device: every chain
    curls from ``start`` towards its joint limits together, a link that meets the device locks itself and the joints
    before it, the rest keeps curling (a grasp, not a fixed pose). Also pushes the hand out along its palm normal while the
    palm cuts into the device. Returns the joint angles and the push-out (metres)."""
    nodes, rig = state["nodes"], state["rig"]
    fingers, thumb, palm = hand_link_meshes(state, side)
    hand = nodes[f"Hand_{side}"]
    basis = hand.matrix_basis.copy()
    ego_arms.apply_pose(nodes, rig, side, ego_arms.pose_angles(rig, "open", side))
    axes = hand_matrix.to_3x3()
    out, along = -(axes @ Vector((0, -1, 0))), axes @ Vector((1, 0, 0))
    # the smallest shift that frees the palm: out of the surface, along the grip axis or both (short grips meet the body)
    directions = [out, -along, along, (out - along).normalized(), (out + along).normalized()]
    shift = None
    for distance in [step * PENETRATION_STEP_M for step in range(41)]:
        for direction in directions:
            hand.matrix_world = Matrix.Translation(direction * distance) @ hand_matrix
            bpy.context.view_layer.update()
            if not overlaps([palm], device_bvh):
                shift = direction * distance
                break
        if shift is not None:
            break
    shift = shift if shift is not None else out * 40 * PENETRATION_STEP_M
    hand.matrix_world = Matrix.Translation(shift) @ hand_matrix
    bpy.context.view_layer.update()
    angles = {"fingers": [list(values) for values in start["fingers"]], "thumb": list(start["thumb"])}
    report_start = []
    chains = [("finger", index, links) for index, links in enumerate(fingers)] + [("thumb", 0, thumb)]
    for kind, index, links in chains:
        if (kind, index) in skip:
            continue
        if kind == "finger":
            begin = list(angles["fingers"][index])
            ends = [high for _, high in limits["finger"]]
            joints = [0, 1, 2]
        else:
            begin = list(angles["thumb"])
            ends = [limits["thumb"]["flex"][1], begin[1], limits["thumb"]["tip"][1]]
            joints = [0, 2]
        locked = set()
        current = list(begin)
        set_chain(state, side, kind, index, current)
        if kind == "thumb" and any(overlaps([obj], device_bvh) for obj in links):
            # the open thumb points into the device: swing it out (or in) along the palm first, then close
            low, high = limits["thumb"]["out"]
            for out in sorted({*range(int(low), int(high) + 1, 5)}, key=lambda value: abs(value - begin[1])):
                trial = [0.0, float(out), 0.0]
                set_chain(state, side, kind, index, trial)
                if not any(overlaps([obj], device_bvh) for obj in links):
                    begin = current = trial
                    ends[1] = trial[1]
                    break
            set_chain(state, side, kind, index, current)
        if any(overlaps([obj], device_bvh) for obj in links):
            report_start.append(f"{kind} {index}")
        for step in range(1, CURL_STEPS + 1):
            trial = list(current)
            for order, joint in enumerate(joints):
                if joint not in locked:
                    # the proximal joints lead (a grasp wraps from the palm out), the distal ones follow later
                    share = min(1.0, max(0.0, (step / CURL_STEPS - CURL_LEAD * order) / (1 - CURL_LEAD * order)))
                    trial[joint] = begin[joint] + (ends[joint] - begin[joint]) * share
            set_chain(state, side, kind, index, trial)
            hit = [link for link, obj in enumerate(links) if overlaps([obj], device_bvh)]
            if hit:
                set_chain(state, side, kind, index, current)
                first = min(hit)
                joint_of = (lambda link: link) if kind == "finger" else (lambda link: 0 if link == 0 else 2)
                locked.update(joint for joint in joints if joint <= joint_of(first))
                if all(joint in locked for joint in joints):
                    break
                continue
            current = trial
        if kind == "finger":
            angles["fingers"][index] = [round(value, 3) for value in current]
        else:
            angles["thumb"] = [round(value, 3) for value in current]
        set_chain(state, side, kind, index, current)
    hand.matrix_basis = basis
    bpy.context.view_layer.update()
    if report_start:
        print("CLOSE_HAND_START_OVERLAP", side, report_start, flush=True)
    return angles, shift


def cup_surface(state, root, grip_r, closed_r):
    """Device and grip hand as one BVH (device root at the origin): Hand_R placed on its grip with its closed fingers, the
    surface a cup-gripping left hand meets. Hand_R keeps its rest basis afterwards."""
    nodes = state["nodes"]
    hand = nodes["Hand_R"]
    basis = hand.matrix_basis.copy()
    hand.matrix_world = grip_r
    set_fingers(nodes, state["rig"], "R", closed_r["fingers"], closed_r["thumb"])
    bpy.context.view_layer.update()
    fingers, thumb, palm = hand_link_meshes(state, "R")
    surface = world_bvh([*device_meshes(root), palm, *thumb, *(link for links in fingers for link in links)])
    hand.matrix_basis = basis
    bpy.context.view_layer.update()
    return surface


def grip_hand_bvh(state, device_inverse):
    """The grip hand's renderers of this frame in the device root's frame (the cup grip's second surface)."""
    fingers, thumb, palm = hand_link_meshes(state, "R")
    return world_bvh([palm, *thumb, *(link for links in fingers for link in links)], device_inverse)


def thumb_blocked(state, side, thumb, device_bvh, limits):
    """True while no swing of the open thumb along the palm keeps its base link out of the device."""
    low, high = limits["thumb"]["out"]
    for out in range(int(low), int(high) + 1, 5):
        set_chain(state, side, "thumb", 0, [0.0, float(out), 0.0])
        if not overlaps([thumb[0]], device_bvh):
            return False
    return True


def set_chain(state, side, kind, index, values):
    nodes, rig = state["nodes"], state["rig"]
    if kind == "finger":
        for link, value in enumerate(values):
            nodes[ego_arms.finger_node(side, index, link)].rotation_quaternion = ego_arms.finger_rotation(value)
    else:
        flex, out, tip = values
        nodes[ego_arms.thumb_node(side, 0)].rotation_quaternion = ego_arms.thumb_rotation(rig, side, flex, out)
        nodes[ego_arms.thumb_node(side, 1)].rotation_quaternion = ego_arms.finger_rotation(tip)
    bpy.context.view_layer.update()


def hand_touch(state, side, device_bvh_local, device_inverse, sample=3):
    """Nearest distance (metres) of the hand's renderers (palm and fingers, every ``sample``-th vertex) to the device
    surface; device_inverse maps world points into the frame of device_bvh_local."""
    fingers, thumb, palm = hand_link_meshes(state, side)
    graph = bpy.context.evaluated_depsgraph_get()
    best = float("inf")
    for obj in [palm, *thumb, *(link for links in fingers for link in links)]:
        evaluated = obj.evaluated_get(graph)
        matrix = device_inverse @ evaluated.matrix_world
        local = np.empty(len(evaluated.data.vertices) * 3)
        evaluated.data.vertices.foreach_get("co", local)
        for point in local.reshape(-1, 3)[::sample]:
            found = device_bvh_local.find_nearest(matrix @ Vector(point))
            if found[0] is not None:
                best = min(best, found[3])
    return best


def live_device_bvh(root, hand_parts, device_inverse):
    """Device BVH of this frame in the device root's frame: moving parts where the clip has them, hidden parts (visibility
    scale 0.001) left out, the parts in the left hand (HandMag_L) included."""
    parts = [*device_meshes(root), *(device_meshes(hand_parts["root"]) if hand_parts else [])]
    return world_bvh([obj for obj in parts if obj.matrix_world.to_scale().x > .01], device_inverse)


def hand_penetration(state, side, device_bvh_local, device_inverse):
    """Renderers of the hand (palm, fingers, thumb) whose triangles cut the device surface (live_device_bvh, in the frame
    of device_bvh_local): touching within the contact gap passes, cutting in fails."""
    fingers, thumb, palm = hand_link_meshes(state, side)
    return [obj.name for obj in [palm, *thumb, *(link for links in fingers for link in links)]
            if device_bvh_local.overlap(world_bvh([obj], device_inverse))]


def wrist_side_degrees(nodes, side):
    """Sideways bend of the wrist (degrees): the servo is a hinge about LowerArm X, so Hand +Z should stay in the
    forearm's YZ plane; this is the angle out of it."""
    lower = nodes[f"LowerArm_{side}"].matrix_world.to_3x3()
    knuckles = (nodes[f"Hand_{side}"].matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    return math.degrees(math.asin(min(1.0, abs(knuckles.dot((lower @ Vector((1, 0, 0))).normalized())))))


# --------------------------------------------------------------------------------------------- arm chain
def forearm_from_spec(spec, hand_matrix):
    """Rest forearm direction (elbow -> wrist, camera axes): ``forearm`` explicit, or rise/yaw relative to the knuckle
    heading of the hand (like first_person.py aim_arm)."""
    if "forearm" in spec:
        return Vector(spec["forearm"]).normalized()
    knuckles = hand_matrix.to_3x3() @ Vector((0, 0, 1))
    heading = Vector((knuckles.x, knuckles.y, 0)).normalized()
    heading = Matrix.Rotation(math.radians(spec.get("yaw", 0)), 3, "Z") @ heading
    rise = math.radians(spec["rise"])
    return (heading * math.cos(rise) + Vector((0, 0, math.sin(rise)))).normalized()


def limited_forearm(forearm, knuckles, target):
    """Turns the forearm towards the knuckles by the excess over ``target`` degrees of wrist bend."""
    angle = forearm.angle(knuckles)
    limit = math.radians(target)
    if angle <= limit:
        return forearm
    axis = forearm.cross(knuckles)
    if axis.length < 1e-9:
        return forearm
    return Quaternion(axis.normalized(), angle - limit) @ forearm


# --------------------------------------------------------------------------------------------- clips
def v5_clips(tool, profile, device):
    return ego_arms.clip_list_v5(tool, profile, device)


def ego_values(clip, frame, params, device):
    if clip["motion"] not in CHOREOGRAPHY:
        return ego_clips.pose_at(clip, frame, params)
    spec = ego_arms.choreography(device, clip)
    u = frame - clip["frame_start"]
    a, b, t = interpolate(spec["weapon"], u)
    blend = mix(a, b, t)
    values = ego_clips.pose()
    for axis in ego_clips.AXES:
        values[axis] = blend.get(axis + "_deg", blend.get(axis + "_m", 0.0))
    values["follow"] = spec.get("shoulder_follow", params["reload"].get("shoulder_follow", .35))
    return values


def scaled_values(values, factor):
    result = dict(values)
    for axis in ("right", "up", "back"):
        result[axis] = values[axis] * factor
    return result


def use_motion(tool, profile, frame, pivot):
    """Viewmodel_Motion of the Use clip (first_person.py): recoil about the hand (weapons) or the press of a tool."""
    if profile.get("motion"):
        rotation, location = fp.recoil_pose(profile["motion"], frame, pivot)
        return Matrix.Translation(Vector(location)) @ Euler(rotation, "XYZ").to_matrix().to_4x4()
    pressure = envelope(frame, ((1, 0), (14, 1), (45, 1), (73, 0), (97, 0)))
    kick = settle(frame, 14, 28, 1)
    return (Matrix.Translation(Vector((0, -.012 * pressure + .010 * kick, .016 * pressure)))
            @ Euler((math.radians(1.5) * pressure, math.radians(.9) * kick, 0), "XYZ").to_matrix().to_4x4())


def conjugated(matrix, pivot, factor):
    """The rigid motion ``matrix`` of the unscaled model as seen on the model scaled by ``factor`` about ``pivot``."""
    scale = Matrix.Translation(pivot) @ Matrix.Scale(factor, 4) @ Matrix.Translation(-pivot)
    result = scale @ matrix @ scale.inverted()
    location, rotation, _ = result.decompose()
    return Matrix.LocRotScale(location, rotation, Vector((1, 1, 1)))


# --------------------------------------------------------------------------------------------- framing
def frusta(settings):
    tan_v = math.tan(math.radians(settings["vertical_fov_degrees"]) / 2)
    return {aspect: {"tan_h": tan_v * fp.aspect_ratio(aspect), "tan_v": tan_v} for aspect in settings["qa_aspects"]}


def screen_points(points, frustum, near):
    depth = -points[:, 1]
    visible = depth > near
    safe = np.where(visible, depth, 1.0)
    u = .5 - points[:, 0] / safe / (2 * frustum["tan_h"])
    v = .5 + points[:, 2] / safe / (2 * frustum["tan_v"])
    inside = visible & (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
    return u, v, inside


def mesh_world(obj, graph):
    evaluated = obj.evaluated_get(graph)
    local = np.empty(len(evaluated.data.vertices) * 3)
    evaluated.data.vertices.foreach_get("co", local)
    matrix = np.array(evaluated.matrix_world)
    return local.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3], local.reshape(-1, 3)


# --------------------------------------------------------------------------------------------- build
def build(directory, tool_id):
    started = time.perf_counter()
    spec, profile, viewmodels, rig, device = load_inputs(tool_id)
    name = spec["asset"] + "_FPS"
    source = directory / (name + ".blend")
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    scene.frame_set(1)
    root = scene.objects[name]
    for obj in [obj for obj in root.children_recursive if obj.name == "Socket_Camera"]:
        bpy.data.objects.remove(obj)              # the camera socket belongs to the arm rig
    size = ego_arms.measures(rig, viewmodels["arm"])
    factor = device["tool_scale"] * rig["scale"]
    scale_device(root, factor)
    reroot(scene, root, scene.objects["Socket_Hand"].matrix_world.copy())
    scene.frame_set(1)
    bpy.context.view_layer.update()
    settings = fp.viewmodel_camera(viewmodels, profile)
    fp.configure_camera(scene, settings)
    pose = rest_pose(scene, profile)
    pivot = pose.to_translation()
    # the shared rig, its four look slots from the palette
    import game_export
    palette = json.loads((ROOT / "data/game_palette.json").read_text())
    created = game_export.palette_materials({"materials": {key: palette["materials"][key] for key in ego_arms.LOOK_SLOTS}})
    collection = root.users_collection[0]
    state = ego_arms.build_rig(collection, rig, viewmodels["arm"], [created[key] for key in ego_arms.LOOK_SLOTS])
    state["hash"] = ego_arms.rig_hash_of(state["nodes"], rig["asset"])
    nodes = state["nodes"]
    arms_root = state["root"]
    # grips in device space (device root at the origin = Socket_Hand)
    bpy.context.view_layer.update()
    bvh = world_bvh(device_meshes(root))
    gap = device.get("gap_m", .001)
    grips, closed, pushes = {}, {}, {}
    for side in ego_arms.SIDES:
        entry = device["grip"][side]
        surface = bvh
        if side == "L" and entry.get("mode") == "cup":
            # 0.27 cup grip (pistol): the left hand closes around the right one - the grip hand in its closed pose is part
            # of the surface the support hand meets
            surface = cup_surface(state, root, grips["R"], closed["R"])
        grips[side] = grip_matrix(entry, surface, nodes, side, gap, factor)
        start = ego_arms.pose_angles(rig, "open", side)
        closed[side], shift = close_hand(state, side, grips[side], surface, start, rig["limits_degrees"])
        grips[side] = Matrix.Translation(shift) @ grips[side]
        pushes[side] = round(shift.length, 4)
    extra = {}
    for key, entry in device.get("reload", {}).get("grips", {}).items():
        matrix = grip_matrix(entry, bvh, nodes, "L", gap, factor)
        angles, shift = close_hand(state, "L", matrix, bvh, ego_arms.pose_angles(rig, "open", "L"), rig["limits_degrees"])
        extra[key] = (Matrix.Translation(shift) @ matrix, angles, entry["pose"])
    finger_poses = {"R": {device["grip"]["R"]["pose"]: closed["R"]},
                    "L": {device["grip"]["L"]["pose"]: closed["L"], **{entry[2]: entry[1] for entry in extra.values()}}}
    for side in ego_arms.SIDES:
        for key in ("open", "regrip"):
            finger_poses[side].setdefault(key, ego_arms.pose_angles(rig, key, side))
    # attach: the device root in Prop_R (constant); the hand parts root at Prop_L
    prop_r = nodes["Prop_R"]
    attach = (grips["R"] @ prop_r.matrix_local).inverted()
    # ADS transform with the device at its rest pose
    root.matrix_world = pose
    bpy.context.view_layer.update()
    clips, params = v5_clips(spec, profile, device)
    aim = fp.ads_setup(scene, root, root, params) if any(clip["motion"].startswith("aim") for clip in clips) else None
    root.matrix_world = Matrix()
    bpy.context.view_layer.update()
    root.parent = prop_r
    root.matrix_parent_inverse = Matrix()
    root.rotation_mode = "QUATERNION"
    root.matrix_basis = attach
    root["ce_attach_bone"] = "Prop_R"
    hand_parts = build_hand_parts(scene, root, nodes, device, extra, spec)
    # rest arm chains
    arm_specs = device.get("arm", default_arm_specs(profile))
    rest_hands = {"R": pose @ grips["R"], "L": pose @ grips["L"]}
    lengths = (size["upper_m"], size["forearm_m"])
    rest_arm = {}
    for side in ego_arms.SIDES:
        hand_matrix = rest_hands[side]
        forearm = forearm_from_spec(arm_specs[side], hand_matrix)
        upper = Vector(arm_specs[side]["upper"]).normalized()
        rest_arm[side] = {"forearm": forearm, "upper": upper}
    grip_forearm = (rest_hands["R"].to_translation(), rest_arm["R"]["forearm"])
    wrist_rule = ego_clips.load()["wrist"]
    limit = rig["limits_degrees"]["wrist_limit"]
    targets = {}
    for side in ego_arms.SIDES:
        knuckles = rest_hands[side].to_3x3() @ Vector((0, 0, 1))
        rest_bend = math.degrees(rest_arm[side]["forearm"].angle(knuckles))
        targets[side] = min(limit - wrist_rule["limit_margin_degrees"],
                            max(wrist_rule["target_degrees"], rest_bend + wrist_rule["rest_allowance_degrees"]))
    # every frame: device, hands, chains, fingers, parts
    frames = [*range(USE_FRAMES[0], USE_FRAMES[1] + 1),
              *(frame for clip in clips for frame in range(clip["frame_start"], clip["frame_end"] + 1))]
    plan = {}
    for frame in frames:
        clip = ego_clips.clip_at(clips, frame) if frame > USE_FRAMES[1] else None
        plan[frame] = frame_plan(frame, clip, spec, profile, device, params, aim, pivot, pose, grips, extra, rig,
                                 grip_forearm, closed, finger_poses)
    forearms = {side: {} for side in ego_arms.SIDES}
    for frame, item in plan.items():
        for side in ego_arms.SIDES:
            turn = item["turn"]
            knuckles = item["hands"][side].to_3x3() @ Vector((0, 0, 1))
            forearms[side][frame] = limited_forearm(turn @ rest_arm[side]["forearm"], knuckles, targets[side])
    lag, share = FOREARM_LAG
    for frame, item in plan.items():
        clip = item["clip"]
        for side in ego_arms.SIDES:
            target = forearms[side][frame]
            earlier = frame - lag
            start, end = (clip["frame_start"], clip["frame_end"]) if clip is not None else USE_FRAMES
            loop = clip is not None and clip["loop"]
            if earlier < start:
                earlier = end - (start - earlier) if loop else start
            # every clip starts and ends exactly in its named pose (loops too: they meet the clips of the same pose without a
            # crossfade): the lag fades in over the first and out over the last frames
            weight = share * min(1.0, (frame - start) / lag, (end - frame) / lag)
            direction = (target * (1 - weight) + forearms[side][earlier] * weight).normalized()
            knuckles = item["hands"][side].to_3x3() @ Vector((0, 0, 1))
            item.setdefault("forearm", {})[side] = limited_forearm(direction, knuckles, limit - .5)
    keyed, guarded = key_frames(scene, state, root, hand_parts, plan, rest_arm, lengths, clips, device,
                                finger_poses["L"]["open"])
    # device mechanics in the ego clips (first_person.py clip_keys: Fire replays the Use clip's slides and bolts)
    owners = [root, *root.children_recursive, *(obj.data.shape_keys for obj in root.children_recursive
                                                if obj.type == "MESH" and obj.data.shape_keys)]
    for owner in owners:
        fp.clip_keys(owner, clips, params.get("fire_start", 1), params.get("fire_scale", 1.0))
    for obj in [*keyed, *root.children_recursive, *(hand_parts["root"].children_recursive if hand_parts else [])]:
        fp.finish_keys(obj)
    constant_visibility(hand_parts)
    scene.frame_start, scene.frame_end = USE_FRAMES
    scene.render.fps = ego_clips.load()["fps"]
    scene.frame_set(1)
    bpy.context.view_layer.update()
    event = profile.get("use_event")         # the tools' Use event (Fire, Grab, Switch) as a timeline marker, like first_person.py
    if event:
        for marker in [marker for marker in scene.timeline_markers if marker.name == event["name"]]:
            scene.timeline_markers.remove(marker)
        scene.timeline_markers.new(event["name"], frame=event["frame"])
    properties(root, arms_root, spec, settings, state, clips, hand_parts)
    report = validate(scene, state, root, hand_parts, plan, clips, settings, device, rig, extra, frames, aim, attach)
    report.update({"tool": tool_id, "contract": 5, "rig": {"id": rig["id"], "version": rig["version"], "hash": state["hash"]},
                   "scale": {"device_factor": factor, "tool_scale": device["tool_scale"], "rig_scale": rig["scale"]},
                   "finger_poses": finger_poses, "palm_push_m": pushes,
                   "finger_guard": {"frames": guarded, "rule": "reload frames: a left-hand chain that would cut the "
                                                               "device of that frame opens towards open (5 % steps)"},
                   "attach": {"bone": "Prop_R", "node": name, **ego_arms.unity_local(root)},
                   "grips": {side: {"mode": "grip" if side == "R" else device["grip"]["L"].get("mode", "support"),
                                    "pose": device["grip"][side]["pose"],
                                    "matrix_device": [list(row) for row in grips[side]]} for side in ego_arms.SIDES},
                   "viewmodel_camera": settings, "hand_sides": ["Hand_R", "Hand_L"],
                   "seconds": round(time.perf_counter() - started, 2)})
    (directory / "qa_viewmodel.json").write_text(json.dumps(report, indent=2, default=float) + "\n")
    (directory / "viewmodel_camera.json").write_text(json.dumps(camera_document(tool_id, settings), indent=2) + "\n")
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    export_assembly(directory, arms_root, spec.get("fps_clip") or spec["clip"])
    roundtrip = check_roundtrip(directory, name, arms_root.name, report)
    (directory / "qa_viewmodel_roundtrip.json").write_text(json.dumps(roundtrip, indent=2) + "\n")
    if not os.environ.get("TOOLGEN_NO_RENDER"):
        bpy.ops.wm.open_mainfile(filepath=str(source))
        scene = bpy.context.scene
        scene.render.filepath = str(directory / "preview_first_person.png")
        bpy.ops.render.render(write_still=True)
    if not report["passed"] or not roundtrip["passed"]:
        print("EGO_RIG_FAILED", tool_id, json.dumps(report["failures"][:20]), json.dumps(roundtrip.get("failures", [])),
              flush=True)
        sys.exit(1)
    print(f"EGO_RIG_OK {tool_id}: {len(clips)} ego clips, {len(frames)} frames, touch R {report['hand_touch_max_m']['R']:.4f} m, "
          f"wrist {report['wrist_bend_max_degrees']}", flush=True)


def default_arm_specs(profile):
    return {"R": {"rise": 27, "yaw": 6, "upper": [-0.3, 0.95, 0.15]}, "L": {"rise": 40, "yaw": -10, "upper": [0.3, 0.95, 0.05]}}


def frame_plan(frame, clip, spec, profile, device, params, aim, pivot, pose, grips, extra, rig, grip_forearm, closed,
               finger_poses):
    """World poses of one frame: device root, both hands, the shoulders' turn, finger angles, part states."""
    factor = rig["scale"]
    values = None
    if clip is None:
        motion = conjugated(use_motion(spec, profile, frame, pivot), pivot, factor)
    else:
        values = ego_values(clip, frame, params, device)
        motion = fp.clip_matrix(scaled_values(values, factor), aim and aim["matrix"], pivot, grip_forearm)
    world = motion @ pose
    turn = Quaternion().slerp(motion.to_quaternion(), values["follow"] if values else 0.0)
    hands = {"R": world @ grips["R"], "L": world @ grips["L"]}
    fingers = {"R": [list(f) for f in closed["R"]["fingers"]], "L": [list(f) for f in closed["L"]["fingers"]]}
    thumbs = {"R": list(closed["R"]["thumb"]), "L": list(closed["L"]["thumb"])}
    if values and values.get("trigger") and device["grip"]["R"].get("trigger_finger"):
        lift = params["fingers"]["trigger_deg"] * values["trigger"]
        fingers["R"][0] = [max(0.0, fingers["R"][0][0] - lift), max(0.0, fingers["R"][0][1] - lift), fingers["R"][0][2]]
    if values and values.get("regrip"):
        open_pose = finger_poses["L"]["regrip"]
        t = values["regrip"]
        fingers["L"] = [[(1 - t) * a + t * b for a, b in zip(fa, fb)] for fa, fb in zip(fingers["L"], open_pose["fingers"])]
    if clip is not None and clip["motion"] in CHOREOGRAPHY:
        choreography = ego_arms.choreography(device, clip)
        u = frame - clip["frame_start"]
        events = choreography["events"]
        hands["L"] = left_hand(choreography["left"], u, world, pose, grips, extra)
        a, b, t = interpolate(choreography["fingers"], u)
        pa, pb = finger_poses["L"][a], finger_poses["L"][b]
        fingers["L"] = [[(1 - t) * x + t * y for x, y in zip(fa, fb)] for fa, fb in zip(pa["fingers"], pb["fingers"])]
        thumbs["L"] = [(1 - t) * x + t * y for x, y in zip(pa["thumb"], pb["thumb"])]
    return {"clip": clip, "world": world, "turn": turn, "hands": hands, "fingers": fingers, "thumbs": thumbs,
            "values": values}


def left_hand(keys, u, world, pose, grips, extra):
    """Left hand of a reload frame: smoothstep between the choreography's keys, each resolved at this frame (device keys
    move with the weapon, camera keys stay below the frame)."""
    def resolve(key):
        if isinstance(key, str):
            return world @ (grips["L"] if key == "support" else extra[key][0])
        base = grips["L"] if key["from"] == "support" else extra[key["from"]][0]
        if "device_m" in key:
            return world @ Matrix.Translation(Vector(key["device_m"])) @ base
        return Matrix.Translation(Vector(key["camera_m"])) @ pose @ base
    a, b, t = interpolate(keys, u)
    ma, mb = resolve(a), resolve(b)
    location = ma.to_translation().lerp(mb.to_translation(), t)
    rotation = ma.to_quaternion().slerp(mb.to_quaternion(), t)
    return Matrix.LocRotScale(location, rotation, Vector((1, 1, 1)))


def build_hand_parts(scene, root, nodes, device, extra, spec):
    """<asset>_FPS_HandL at Prop_L with the parts the left hand carries (HandMag_L: a copy of the magazine, placed where
    the magazine sits in the hand's 'mag' grip)."""
    parts = device.get("hand_parts")
    if not parts:
        return None
    holder = ego_arms.empty(spec["asset"] + "_FPS_HandL", nodes["Prop_L"])
    holder["ce_role"] = "hand_parts"
    holder["ce_attach_bone"] = "Prop_L"
    created = {}
    for part_name, entry in parts.items():
        source = scene.objects[entry["source"]]
        grip = extra[entry["grip"]][0]
        # the source in device space (device root at the origin before parenting = its matrix relative to the root)
        source_device = root.matrix_world.inverted() @ source.matrix_world
        prop_device = grip @ nodes["Prop_L"].matrix_local
        part = ego_arms.empty(part_name, holder)
        part.matrix_basis = prop_device.inverted() @ source_device
        part["ce_visibility_animation"] = "scale 1 / 0.001 at MagOut and MagIn"
        source["ce_visibility_animation"] = "scale 1 / 0.001 at MagOut and MagIn"
        for child in source.children:
            if child.type != "MESH":
                continue
            copy = child.copy()
            copy.data = child.data.copy()
            copy.animation_data_clear()
            root.users_collection[0].objects.link(copy)
            copy.parent = part
            copy.matrix_parent_inverse = Matrix()
            copy.matrix_basis = child.matrix_local
            copy.name = child.name.replace("SM_PG_", "SM_PG_Hand") if child.name.startswith("SM_PG_") else child.name + "_Hand"
            copy["ce_copy_of"] = child.name             # game_export_rig.py gives the copy the source's UV1
        created[part_name] = {"node": part, "source": source}
    return {"root": holder, "parts": created}


def set_fingers(nodes, rig, side, fingers, thumb):
    for finger, values in enumerate(fingers):
        for link, value in enumerate(values):
            nodes[ego_arms.finger_node(side, finger, link)].rotation_quaternion = ego_arms.finger_rotation(value)
    flex, out, tip = thumb
    nodes[ego_arms.thumb_node(side, 0)].rotation_quaternion = ego_arms.thumb_rotation(rig, side, flex, out)
    nodes[ego_arms.thumb_node(side, 1)].rotation_quaternion = ego_arms.finger_rotation(tip)


def guard_fingers(state, side, fingers, thumb, open_pose, device_bvh):
    """Reload frames: the left hand travels between grips and its keyed finger stellung was closed on the device at rest;
    every chain (finger or thumb) that cuts the device of this frame opens towards ``open`` in steps of 5 % until it is
    free. Returns the new angles and the opened share per chain (empty when nothing cut)."""
    nodes, rig = state["nodes"], state["rig"]
    fingers = [list(values) for values in fingers]
    thumb = list(thumb)
    links, thumb_links, _ = hand_link_meshes(state, side)
    opened = {}
    chains = [*((f"finger {index}", index) for index in range(ego_arms.FINGERS)), ("thumb", None)]
    for name, index in chains:
        start = fingers[index] if index is not None else thumb
        target = open_pose["fingers"][index] if index is not None else open_pose["thumb"]
        objects = links[index] if index is not None else thumb_links
        share = 0.0
        while overlaps(objects, device_bvh, 0.0) and share < 1.0:
            share = min(1.0, share + .05)
            values = [(1 - share) * a + share * b for a, b in zip(start, target)]
            if index is not None:
                fingers[index] = values
            else:
                thumb = values
            set_fingers(nodes, rig, side, fingers, thumb)
            bpy.context.view_layer.update()
        if share:
            opened[name] = round(share, 2)
    return fingers, thumb, opened


def key_frames(scene, state, root, hand_parts, plan, rest_arm, lengths, clips, device, open_pose):
    """Keys every node of the chains, the fingers, the reload part states (bolt, magazine swap). In reload frames the
    left hand's chains open where they would cut the device of that frame (guard_fingers). Returns the keyed objects and
    the guarded frames."""
    nodes, rig = state["nodes"], state["rig"]
    upper_m, forearm_m = lengths
    keyed = []
    guarded = []
    previous = {}
    swap = {}
    for clip in clips:
        if clip["motion"] in CHOREOGRAPHY and "MagOut" in ego_arms.choreography(device, clip)["events"]:
            events = ego_arms.choreography(device, clip)["events"]
            swap[clip["name"]] = (clip["frame_start"] + events["MagOut"], clip["frame_start"] + events["MagIn"])
    # device parts a clip moves itself: a choreography's bolt (ReloadEmpty's charging handle or slide, the press-check) and,
    # 0.27, the slide of the slide-lock clips (ego_arms.slide_lock_clips)
    bolt_specs = {clip["name"]: (ego_arms.choreography(device, clip).get("bolt") if clip["motion"] in CHOREOGRAPHY
                                 else clip.get("slide_keys")) for clip in clips}
    # rest locations once, before any frame is posed (frame_set would reset the posed values of a frame)
    scene.frame_set(1)
    bolt_rest = {spec["node"]: scene.objects[spec["node"]].location.copy() for spec in bolt_specs.values() if spec}
    for frame, item in plan.items():
        clip = item["clip"]
        # the frame's device state first (magazine swap, bolt), then the chains, then the guard, then the keys
        if hand_parts:
            inside = clip is not None and clip["name"] in swap and swap[clip["name"]][0] <= frame < swap[clip["name"]][1]
            for entry in hand_parts["parts"].values():
                entry["node"].scale = (1, 1, 1) if inside else (.001, .001, .001)
                entry["source"].scale = (.001, .001, .001) if inside else (1, 1, 1)
        bolt = None
        if clip is not None and bolt_specs.get(clip["name"]):
            spec = bolt_specs[clip["name"]]
            bolt = scene.objects[spec["node"]]
            u = frame - clip["frame_start"]
            keys = [[k, {"d": v}] for k, v in spec["keys"]]
            a, b, t = interpolate(keys, u)
            offset = (1 - t) * a["d"] + t * b["d"]
            bolt.location = bolt_rest[bolt.name] + Vector(spec["axis"]) * offset
        for side in ego_arms.SIDES:
            hand_matrix = item["hands"][side]
            forearm = item["forearm"][side]
            wrist = hand_matrix.to_translation()
            elbow = wrist - forearm * forearm_m
            upper = item["turn"] @ rest_arm[side]["upper"]
            shoulder = elbow + upper * upper_m
            ego_arms.place_chain(nodes, side, shoulder, elbow, hand_matrix)
            set_fingers(nodes, rig, side, item["fingers"][side], item["thumbs"][side])
        if clip is not None and clip["motion"] in CHOREOGRAPHY:
            bpy.context.view_layer.update()
            parts = [*device_meshes(root), *(device_meshes(hand_parts["root"]) if hand_parts else [])]
            live = world_bvh([obj for obj in parts if obj.matrix_world.to_scale().x > .01])
            fingers, thumb, opened = guard_fingers(state, "L", item["fingers"]["L"], item["thumbs"]["L"], open_pose, live)
            if opened:
                item["fingers"]["L"], item["thumbs"]["L"] = fingers, thumb
                guarded.append({"clip": clip["name"], "frame": frame - clip["frame_start"], "opened": opened})
        for side in ego_arms.SIDES:
            chain = [nodes[f"Shoulder_{side}"], nodes[f"UpperArm_{side}"], nodes[f"LowerArm_{side}"],
                     nodes[f"WristYoke_{side}"], nodes[f"Hand_{side}"],
                     *(nodes[ego_arms.finger_node(side, finger, link)] for finger in range(ego_arms.FINGERS)
                       for link in range(ego_arms.FINGER_LINKS)),
                     *(nodes[ego_arms.thumb_node(side, link)] for link in range(ego_arms.THUMB_LINKS))]
            for obj in chain:
                rotation = obj.rotation_quaternion.copy()
                if obj.name in previous and rotation.dot(previous[obj.name]) < 0:
                    rotation = -rotation
                    obj.rotation_quaternion = rotation
                previous[obj.name] = rotation.copy()
                obj.keyframe_insert(data_path="rotation_quaternion", frame=frame)
                if obj.name.startswith("Shoulder_"):
                    obj.keyframe_insert(data_path="location", frame=frame)
            keyed += chain if frame == next(iter(plan)) else []
        if hand_parts:
            for entry in hand_parts["parts"].values():
                entry["node"].keyframe_insert(data_path="scale", frame=frame)
                entry["source"].keyframe_insert(data_path="scale", frame=frame)
        if bolt is not None:
            bolt.keyframe_insert(data_path="location", frame=frame)
    return keyed, guarded


def constant_visibility(hand_parts):
    """The magazine swap is a step: scale keys of the swapped parts hold their value (after finish_keys made all linear)."""
    if not hand_parts:
        return
    for entry in hand_parts["parts"].values():
        for owner in (entry["node"], entry["source"]):
            for curve in fp.curves_of(owner):
                if curve.data_path == "scale":
                    for key in curve.keyframe_points:
                        key.interpolation = "CONSTANT"


def properties(root, arms_root, spec, settings, state, clips, hand_parts):
    clip = spec.get("fps_clip") or spec["clip"]
    for obj in (root, arms_root):
        obj["ce_viewmodel_vertical_fov_degrees"] = settings["vertical_fov_degrees"]
        obj["ce_viewmodel_horizontal_fov_degrees"] = settings["horizontal_fov_degrees"][settings["reference_aspect"]]
        obj["ce_viewmodel_reference_aspect"] = settings["reference_aspect"]
        obj["ce_viewmodel_near_clip_m"] = settings["near_clip_m"]
    root["ce_action_clip"] = clip
    root["ce_autoplay"] = False
    root["ce_loop"] = False
    root["ce_action_clips"] = json.dumps([clip, *(entry["name"] for entry in clips)])
    root["ce_hand_style"] = "shared ego arm rig (contract 5), three gripping fingers and thumb"
    root["ce_contract"] = 5
    root["toolgen_ego_clips"] = json.dumps({"timeline_start": clips[0]["frame_start"], "timeline_end": clips[-1]["frame_end"],
                                            "reload_part": (next(iter(hand_parts["parts"].values()))["source"].name if hand_parts
                                                            else None), "clips": clips,
                                            "rig": {"id": state["rig"]["id"], "version": state["rig"]["version"],
                                                    "hash": state["hash"]},
                                            "assembly_root": arms_root.name,
                                            "hand_parts_root": hand_parts["root"].name if hand_parts else None})


def camera_document(tool, settings):
    return {"format": 1, "tool": tool, "contract": 5, "vertical_fov_degrees": settings["vertical_fov_degrees"],
            "horizontal_fov_degrees": settings["horizontal_fov_degrees"], "reference_aspect": settings["reference_aspect"],
            "near_clip_m": settings["near_clip_m"], "override": settings["override"], "unity": settings["unity"],
            "player_fov_dependency": "none", "validated_vertical_fov_degrees": [settings["vertical_fov_degrees"]],
            "aspect_policy": "Vertical FOV is the fixed value; the horizontal FOV follows the aspect ratio. Framing is binding "
                             "for " + ", ".join(settings["qa_aspects"]) + " (contract 5: checked at the binding FOV only).",
            "camera_offset_m": [0.0, 0.0, 0.0],
            "runtime": "Arms and device sit in camera space (Socket_Camera of the arm rig = identity) at frame size 1.0; "
                       "render them with the viewmodel camera (Camera.fieldOfView = vertical_fov_degrees, nearClipPlane = "
                       "near_clip_m). The player's world FOV never scales the viewmodel."}


# --------------------------------------------------------------------------------------------- QA
def validate(scene, state, root, hand_parts, plan, clips, settings, device, rig, extra, frames, aim, attach):
    nodes = state["nodes"]
    failures = []
    limit = rig["limits_degrees"]["wrist_limit"]
    lengths = ego_arms.measures(rig, json.loads((ROOT / "data/viewmodels.json").read_text())["arm"])
    views = frusta(settings)
    near = settings["near_clip_m"]
    reticle = settings["qa"]["reticle_half_extent"]
    bvh_local = world_bvh_local(root)
    touch = {"R": 0.0, "L": 0.0}
    touch_frames = {"R": None, "L": None}
    bend = {"R": 0.0, "L": 0.0}
    side_bend = {"R": 0.0, "L": 0.0}
    cardan_worst = {"R": 0.0, "L": 0.0}
    proximal_visible, elbow_visible, chains_missing, reticle_hits = [], [], [], []
    aim_hands_out, near_cuts = [], []
    penetrating, self_contacts = [], []
    renderers = {obj.name: obj for obj in state["renderers"]}
    clip_ranges = {clip["name"]: clip for clip in clips}
    per_clip = {clip["name"]: {"hand_touch_max_m": {"R": 0.0, "L": 0.0}, "wrist_bend_max_degrees": {"R": 0.0, "L": 0.0}}
                for clip in clips}
    per_clip["Use"] = {"hand_touch_max_m": {"R": 0.0, "L": 0.0}, "wrist_bend_max_degrees": {"R": 0.0, "L": 0.0}}
    # every second frame, the clip borders and events; every frame of the reload clips, where the left hand travels between
    # grips and the finger guard works (Codex sol 0.19: a cut on a skipped frame passed)
    sample = sorted(set(frames[::2]) | {clip["frame_start"] for clip in clips} | {clip["frame_end"] for clip in clips}
                    | {event["frame"] for clip in clips for event in clip["events"]}
                    | {frame for clip in clips if clip["motion"] in CHOREOGRAPHY
                       for frame in range(clip["frame_start"], clip["frame_end"] + 1)})
    blend = 3
    for frame in sample:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        item = plan[frame]
        clip = item["clip"]
        key = clip["name"] if clip else "Use"
        device_inverse = root.matrix_world.inverted()
        live = live_device_bvh(root, hand_parts, device_inverse)
        # Toolgen 0.25 (user decision 23.10.2026, Destiny 2): while aiming no hand needs to stay in the frame; the framing
        # rule (fingers, forearm half, elbow) holds everywhere else, the aim frames keep the near plane free instead
        aiming = clip is not None and clip["motion"] in AIM_MOTIONS
        for side in ego_arms.SIDES:
            lower = nodes[f"LowerArm_{side}"].matrix_world
            hand = nodes[f"Hand_{side}"].matrix_world
            value = math.degrees((lower.to_3x3() @ Vector((0, 0, 1))).angle(hand.to_3x3() @ Vector((0, 0, 1))))
            bend[side] = max(bend[side], value)
            per_clip[key]["wrist_bend_max_degrees"][side] = max(per_clip[key]["wrist_bend_max_degrees"][side], round(value, 2))
            if value > limit + 1e-3:
                failures.append(f"{key} frame {frame}: wrist {side} bent {value:.1f} deg (limit {limit})")
            side_bend[side] = max(side_bend[side], wrist_side_degrees(nodes, side))
            # cardan wrist (rig version 2): the yoke turns only about its X, the hand only about its Y
            yoke_axis = nodes[f"WristYoke_{side}"].matrix_basis.to_3x3() @ Vector((1, 0, 0))
            hand_axis = nodes[f"Hand_{side}"].matrix_basis.to_3x3() @ Vector((0, 1, 0))
            residual = max(math.degrees(yoke_axis.angle(Vector((1, 0, 0)))), math.degrees(hand_axis.angle(Vector((0, 1, 0)))))
            cardan_worst[side] = max(cardan_worst[side], residual)
            if residual > CARDAN_TOLERANCE_DEGREES:
                failures.append(f"{key} frame {frame}: wrist {side} is no cardan turn ({residual:.2f} deg off its axes)")
            cut = hand_penetration(state, side, live, device_inverse)
            cup = side == "L" and device["grip"]["L"].get("mode") == "cup"
            if cup:
                # 0.27: the cup-gripping left hand touches the grip hand and never cuts into it
                grip_hand = grip_hand_bvh(state, device_inverse)
                cut += [name + " (grip hand)" for name in hand_penetration(state, side, grip_hand, device_inverse)]
            if cut:
                penetrating.append([key, frame, side, cut[:4]])
            touching = ego_arms.hand_contacts(state, side)
            if touching:
                self_contacts.append([key, frame, side, touching[:2]])
            free = side == "L" and clip is not None and clip["motion"] in CHOREOGRAPHY and in_window(clip, frame, device, blend)
            if not free:
                distance = hand_touch(state, side, bvh_local, device_inverse)
                if cup:
                    distance = min(distance, hand_touch(state, side, grip_hand, device_inverse))
                per_clip[key]["hand_touch_max_m"][side] = max(per_clip[key]["hand_touch_max_m"][side], round(distance, 5))
                if distance > touch[side]:
                    touch[side], touch_frames[side] = distance, frame
                if distance > TOUCH_LIMIT_M:
                    failures.append(f"{key} frame {frame}: Hand_{side} leaves the device ({distance * 1000:.1f} mm)")
            # framing at the binding FOV
            forearm_mesh = renderers[f"LowerArm_{side}_Mesh"]
            points, local = mesh_world(forearm_mesh, graph)
            proximal = points[local[:, 2] < lengths["forearm_m"] * VISIBLE_FRACTION]
            elbow = np.array([list(nodes[f"LowerArm_{side}"].matrix_world.translation)])
            support_free = side == "L" and clip is not None and clip.get("support_forearm_visible")
            for aspect, frustum in views.items():
                if not support_free and not aiming and screen_points(proximal, frustum, near)[2].any():
                    proximal_visible.append([key, frame, side, aspect])
                if not aiming and screen_points(elbow, frustum, near)[2].any():
                    elbow_visible.append([key, frame, side, aspect])
            if side == "R" or not free:
                fingers, thumb, _ = hand_link_meshes(state, side)
                for name, links in [*((f"finger {index}", chain) for index, chain in enumerate(fingers)), ("thumb", thumb)]:
                    # in every aspect (16:9 and 16:10): a finger only inside the wider frame is missing in 16:10
                    shown = all(any(screen_points(mesh_world(obj, graph)[0], frustum, near)[2].any() for obj in links)
                                for frustum in views.values())
                    if shown:
                        continue
                    if aiming:
                        aim_hands_out.append([key, frame, side, name])
                    elif clip is None or clip["motion"] not in ("draw", "holster", "sprint", "sprint_in", "sprint_out"):
                        chains_missing.append([key, frame, side, name])
        if aiming:
            cuts = viewmodel_cuts(state, root, hand_parts, graph, views, near)
            if cuts:
                near_cuts.append([key, frame, cuts[:4]])
        if clip is None or clip.get("reticle_free"):
            for obj in state["renderers"]:
                points = mesh_world(obj, graph)[0]
                u, v, inside = screen_points(points, views[settings["reference_aspect"]], near)
                if (inside & (np.abs(u - .5) < reticle) & (np.abs(v - .5) < reticle)).any():
                    reticle_hits.append([key, frame, obj.name])
                    break
    if proximal_visible:
        failures.append(f"proximal forearm half in frame: {len(proximal_visible)} samples, first {proximal_visible[:3]}")
    if elbow_visible:
        failures.append(f"elbow / upper arm in frame: {len(elbow_visible)} samples, first {elbow_visible[:3]}")
    if chains_missing:
        failures.append(f"finger or thumb of a holding hand out of frame: {len(chains_missing)} samples, first {chains_missing[:3]}")
    if near_cuts:
        failures.append(f"aim clips: the near plane cuts the viewmodel: {len(near_cuts)} samples, first {near_cuts[:3]}")
    if reticle_hits:
        failures.append(f"arms on the reticle in reticle-free frames: {reticle_hits[:3]}")
    if penetrating:
        failures.append(f"hand cuts into the device: {len(penetrating)} samples, first {penetrating[:3]}")
    if self_contacts:
        failures.append(f"fingers of one hand touch each other: {len(self_contacts)} samples, first {self_contacts[:3]}")
    poses = pose_checks(scene, state, root, clips, attach)
    failures += poses["failures"]
    events = event_checks(clips, device)
    failures += events["failures"]
    swap = swap_checks(scene, clips, device, hand_parts)
    failures += swap["failures"]
    sight = ads = None
    if aim is not None:
        idle = next((clip for clip in clips if clip["motion"] == "aim_idle"), None)
        socket = scene.objects.get("Socket_Sight")
        if idle and socket is not None:
            scene.frame_set(idle["frame_start"])
            point = socket.matrix_world.translation
            sight = {"lateral_m": round(abs(point.x), 6), "vertical_m": round(abs(point.z), 6), "depth_m": round(-point.y, 4)}
            if max(sight["lateral_m"], sight["vertical_m"]) > fp.SIGHT_LINE_TOLERANCE_M * 10:
                failures.append(f"Socket_Sight off the AimIdle line of sight {sight}")
            ads = ads_target(state, root, hand_parts, views, near, sight, aim_hands_out, near_cuts)
            failures += ads["failures"]
    return {"passed": not failures, "failures": failures, "sampled_frames": len(sample),
            "hand_touch_limit_m": TOUCH_LIMIT_M, "hand_touch_max_m": {side: round(value, 5) for side, value in touch.items()},
            "hand_touch_worst_frame": touch_frames, "wrist_bend_max_degrees": {side: round(value, 2) for side, value in bend.items()},
            "wrist_limit_degrees": limit,
            "wrist_side_max_degrees": {side: round(value, 2) for side, value in side_bend.items()},
            "wrist_cardan": {"axis_error_max_degrees": {side: round(value, 4) for side, value in cardan_worst.items()},
                             "limit_degrees": CARDAN_TOLERANCE_DEGREES,
                             "rule": "WristYoke_<S> turns about its +X only (flex), Hand_<S> about its +Y only (sideways)"},
            "penetration": {"samples": penetrating[:20], "rule": "no hand renderer cuts the device surface (the device "
                                                                  "of each frame with its moving and hand-held parts)"},
            "hand_self_contacts": {"samples": self_contacts[:20], "gap_m": ego_arms.CONTACT_GAP_M,
                                   "rule": "the keyed grip poses keep the finger_pose_contacts rule of the arm package"},
            "framing": {"proximal_forearm_visible": proximal_visible[:20],
                                                       "elbow_visible": elbow_visible[:20],
                                                       "chains_missing": chains_missing[:20], "reticle": reticle_hits[:20],
                                                       "aim_hands_out_of_frame": aim_hands_out[:20],
                                                       "aim_near_plane_cuts": near_cuts[:20],
                                                       "rule": "three gripping fingers + thumb of each holding hand in frame "
                                                               "(not while drawing, holstering, sprinting), proximal forearm "
                                                               "half and the elbow never; 16:9 and 16:10 at the binding FOV. "
                                                               "Not in the aim clips (AIM_MOTIONS, user decision 23.10.2026): "
                                                               "there the near plane stays free (" + fp.ADS_RULE + ")"},
            "clips": per_clip, "events": events["clips"], "named_poses": poses["checks"], "magazine_swap": swap["checks"], "sight_aim_idle": sight,
            "ads_target": ads,
            "support_ik_blend_frames": blend}


def visible_meshes(state, root, hand_parts):
    """Arms, device and the parts in the left hand as drawn in this frame (hidden parts: visibility scale 0.001)."""
    parts = [*state["renderers"], *device_meshes(root), *(device_meshes(hand_parts["root"]) if hand_parts else [])]
    return [obj for obj in parts if obj.matrix_world.to_scale().x > .01]


def viewmodel_cuts(state, root, hand_parts, graph, views, near):
    """Parts of the viewmodel between the camera and the near plane inside the view (ads_view; camera space = the camera
    at the origin)."""
    vertices, triangles, owners = fp.mesh_triangles(visible_meshes(state, root, hand_parts), graph)
    return ads_view.near_plane_cuts(vertices, triangles, owners, list(views.values()), near, 0.0)


def ads_target(state, root, hand_parts, views, near, sight, aim_hands_out, near_cuts):
    """The aim-down-sights block of contract 5 at the first AimIdle frame (the scene stands there), the same rule and keys
    as first_person.ads_target_report of contract 4 (ads_view): sight on the screen centre, the centre ray free (a scope's
    eye lens excepted), no near-plane cut in any sampled aim frame (binding); hands in the frame measured only. The
    eye-distance range moves the camera along the axis with the pose fixed."""
    graph = bpy.context.evaluated_depsgraph_get()
    vertices, triangles, owners = fp.mesh_triangles(visible_meshes(state, root, hand_parts), graph)
    point = bpy.context.scene.objects["Socket_Sight"].matrix_world.translation.copy()
    distance = -point.y
    # the sight frame of ads_view: Socket_Sight at the origin, the camera of an eye distance d at (0, d, 0) (Codex sol
    # 0.25: the sweep had placed the camera with the sign flipped)
    local = vertices - np.array(list(point))
    configurations, failures = [], []
    for aspect, frustum in views.items():
        u, v, _ = screen_points(np.array([list(point)]), frustum, 0.0)
        entry = {"aspect": aspect, "sight_screen": [round(float(u[0]), 6), round(float(v[0]), 6)]}
        configurations.append(entry)
        if max(abs(u[0] - .5), abs(v[0] - .5)) > .002:
            failures.append(f"{aspect}: sight off the screen centre {entry['sight_screen']}")
    frusta_list = list(views.values())
    reasons, hit, _ = ads_view.rule(local, triangles, owners, frusta_list, near, distance, fp.ADS_CENTRE_ALLOWED)
    failures += [f"AimIdle: {reason}" for reason in reasons if reason.startswith("the centre ray")]
    return {"pose": "the AimIdle clip as keyed (device, arms, hands), first frame", "rule": fp.ADS_RULE,
            "sight_socket": "Socket_Sight", "eye_distance_m": round(distance, 4), "near_clip_m": near,
            "configurations": configurations, "centre_hit": hit,
            "centre_clear": not any(reason.startswith("the centre ray") for reason in reasons),
            "near_plane_cuts": near_cuts[:20], "hands_in_frame": not aim_hands_out, "hands_out_of_frame": aim_hands_out[:20],
            "passed": not failures and not near_cuts, "failures": failures,
            **ads_view.eye_distance_range(local, triangles, owners, frusta_list, near, fp.ADS_CENTRE_ALLOWED),
            "sight_socket_line": dict(sight, ok=max(sight["lateral_m"], sight["vertical_m"]) <= fp.SIGHT_LINE_TOLERANCE_M * 10)}


POSE_TOLERANCE = 1e-4


def pose_checks(scene, state, root, clips, attach):
    """Every clip starts and ends exactly in its named pose (rest = frame 1 of the Use clip, for every rig node), a loop's
    last frame equals its first, the device root keeps ``attach`` under Prop_R, and the rig root, Prop_*, Socket_Camera
    and the device root carry no curves (contract 5: clips never move them)."""
    nodes = [obj for obj in state["root"].children_recursive if obj.type == "EMPTY" and obj.name in state["nodes"]]

    def snapshot(frame):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        return {obj.name: obj.matrix_world.copy() for obj in nodes}, root.matrix_local.copy()

    def error(a, b):
        return max(ego_arms.matrix_error([list(r) for r in a[name]], [list(r) for r in b[name]]) for name in a)
    failures, checks = [], []
    rest, local = snapshot(USE_FRAMES[0])
    named = {"rest": rest}
    end_use, end_local = snapshot(USE_FRAMES[1])
    checks.append({"clip": "Use", "end_error": error(end_use, rest)})
    worst_attach = max(ego_arms.matrix_error([list(r) for r in local], [list(r) for r in attach]),
                       ego_arms.matrix_error([list(r) for r in end_local], [list(r) for r in attach]))
    if checks[-1]["end_error"] > POSE_TOLERANCE:
        failures.append(f"Use ends {checks[-1]['end_error']:.2e} away from rest")
    for clip in clips:
        start, start_local = snapshot(clip["frame_start"])
        end, end_local = snapshot(clip["frame_end"])
        worst_attach = max(worst_attach, ego_arms.matrix_error([list(r) for r in start_local], [list(r) for r in attach]),
                           ego_arms.matrix_error([list(r) for r in end_local], [list(r) for r in attach]))
        named.setdefault(clip["from"], start)
        start_error = error(start, named[clip["from"]])
        named.setdefault(clip["to"], end)
        end_error = error(end, named[clip["to"]])
        loop_error = error(start, end) if clip["loop"] else None
        checks.append({"clip": clip["name"], "from": clip["from"], "to": clip["to"], "start_error": start_error,
                       "end_error": end_error, "loop_error": loop_error})
        for label, value in (("start", start_error), ("end", end_error), ("loop", loop_error)):
            if value is not None and value > POSE_TOLERANCE:
                failures.append(f"{clip['name']}: {label} {value:.2e} away from its named pose")
    if worst_attach > POSE_TOLERANCE:
        failures.append(f"device root leaves attach under Prop_R ({worst_attach:.2e})")
    still = [state["root"], *(state["nodes"][name] for name in ("Socket_Camera", "Prop_R", "Prop_L")), root]
    curved = [obj.name for obj in still if obj.animation_data and obj.animation_data.action]
    if curved:
        failures.append(f"clips move nodes they must not: {curved}")
    return {"failures": failures, "checks": checks, "attach_max_error": worst_attach}


def world_bvh_local(root):
    """Device BVH in the device root's own frame (built once; frames map hand points into it)."""
    inverse = root.matrix_world.inverted()
    return world_bvh(device_meshes(root), inverse)


def in_window(clip, frame, device, blend):
    events = ego_arms.choreography(device, clip)["events"]
    u = frame - clip["frame_start"]
    return events["HandOff"] + blend < u < events["HandOn"]


def event_checks(clips, device):
    failures, result = [], {}
    for clip in clips:
        names = [event["name"] for event in clip["events"]]
        result[clip["name"]] = clip["events"]
        if clip["motion"] == "reload5":
            wanted = ["MagOut", "MagIn", "Ready"] + (["Chamber"] if clip["suffix"] == "ReloadEmpty" else [])
            frames = {event["name"]: event["frame"] for event in clip["events"]}
            missing = [name for name in wanted + list(RIG_EVENTS) if name not in frames]
            if missing:
                failures.append(f"{clip['name']}: missing events {missing}")
                continue
            order = [*(["Move"] if "Move" in frames else []), "HandOff", "MagOut", "MagIn",
                     *(["Chamber"] if "Chamber" in frames else []), "HandOn"]
            values = [frames[name] for name in order]
            if any(a >= b for a, b in zip(values, values[1:])) or frames["Ready"] < frames["MagIn"]:
                failures.append(f"{clip['name']}: event order {frames} (strictly (Move <) HandOff < MagOut < MagIn "
                                f"(< Chamber) < HandOn)")
            # 0.24: Ready (the real release) and Still (the model rests) are separate markers; the clip end is neither
            if "Still" in frames and not frames["Ready"] < frames["Still"] < frames["End"]:
                failures.append(f"{clip['name']}: Ready < Still < End expected, got {frames}")
            repeated = sorted({name for name in names if names.count(name) > 1})
            if repeated:
                failures.append(f"{clip['name']}: events more than once {repeated}")
        elif clip["motion"] == "inspect5":
            failures += inspect_event_failures(clip)
        elif clip.get("shots"):
            failures += fire_event_failures(clip, device["fire"])
        elif device.get("fire", {}).get("mode") == "semi" and clip["motion"] in ("fire", "aim_fire"):
            failures += semi_event_failures(clip, device["fire"])
        failures += [f"{clip['name']}: extra event {name} at {offset} outside the clip"
                     for name, offset in device.get("events", {}).get(clip["suffix"], {}).items()
                     if not 0 <= offset <= clip["length"]]
    return {"failures": failures, "clips": result}


def inspect_event_failures(clip):
    """0.27: an inspect choreography (press-check): the left hand leaves after Move and is back before Still; every named
    event of the choreography lies between HandOff and HandOn; Still < End = the clip end."""
    frames = {event["name"]: event["frame"] - clip["frame_start"] for event in clip["events"]}
    names = [event["name"] for event in clip["events"]]
    failures = []
    missing = [name for name in ("Start", "Move", *RIG_EVENTS, "Still", "End") if name not in frames]
    if missing:
        return [f"{clip['name']}: missing events {missing}"]
    inner = [name for name in frames if name not in ("Start", "Move", *RIG_EVENTS, "Still", "End")]
    if not (frames["Start"] == 0 < frames["Move"] < frames["HandOff"] < frames["HandOn"] < frames["Still"] < frames["End"]
            == clip["length"]) or any(not frames["HandOff"] < frames[name] < frames["HandOn"] for name in inner):
        failures.append(f"{clip['name']}: Start 0 < Move < HandOff < (events) < HandOn < Still < End expected, got {frames}")
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        failures.append(f"{clip['name']}: events more than once {repeated}")
    return failures


def semi_event_failures(clip, pattern):
    """0.27: a semi-automatic fire clip (Fire, AimFire, FireLast, AimFireLast): Start = Shot = 0, Move 1, Ready at the
    pattern's ready_frame (the cadence), Still, End = the clip end; FireLast/AimFireLast add SlideLock before Ready."""
    frames = {event["name"]: event["frame"] - clip["frame_start"] for event in clip["events"]}
    shots = [event["frame"] - clip["frame_start"] for event in clip["events"] if event["name"] == "Shot"]
    failures = []
    if shots != [0] or not (frames.get("Start") == 0 and frames.get("Move") == 1
                            and frames.get("Ready") == pattern["ready_frame"] and frames.get("Still") == pattern["still_frame"]
                            and pattern["ready_frame"] < pattern["still_frame"] <= frames.get("End", -1) == clip["length"]):
        failures.append(f"{clip['name']}: Shot = Start 0, Move 1, Ready {pattern['ready_frame']} < Still "
                        f"{pattern['still_frame']} <= End = length expected, got {frames} shots {shots}")
    if clip["suffix"].endswith("FireLast") and not 1 <= frames.get("SlideLock", -1) < frames.get("Ready", 0):
        failures.append(f"{clip['name']}: SlideLock between Move and Ready expected, got {frames}")
    return failures


def fire_event_failures(clip, pattern):
    """0.24: a fire clip carries one Shot per real shot of the device's pattern, in order; a burst adds BurstEnd at its
    last shot, Ready (the next pull) after it and Still (the model rests) before the clip end."""
    start = clip["frame_start"]
    shots = [event["frame"] - start for event in clip["events"] if event["name"] == "Shot"]
    failures = []
    if shots != ego_arms.shot_offsets(pattern):
        failures.append(f"{clip['name']}: Shot at {shots}, the pattern says {ego_arms.shot_offsets(pattern)}")
    if pattern["mode"] == "auto":
        if not clip["loop"] or clip["length"] != pattern["cycle_frames"] * pattern["loop_shots"]:
            failures.append(f"{clip['name']}: held fire is a loop of whole cycles")
        return failures
    frames = {event["name"]: event["frame"] - start for event in clip["events"] if event["name"] != "Shot"}
    if not shots or frames.get("BurstEnd") != shots[-1]:
        failures.append(f"{clip['name']}: BurstEnd {frames.get('BurstEnd')} is not the last Shot {shots[-1:]}")
    if not shots or not (frames.get("Start") == 0 == shots[0] and frames.get("Move") == 1
                         and shots[-1] < frames["Ready"] < frames["Still"] < frames["End"] == clip["length"]):
        failures.append(f"{clip['name']}: Start = first Shot, Move 1, last Shot < Ready < Still < End expected, got {frames}")
    return failures


def swap_checks(scene, clips, device, hand_parts):
    checks, failures = [], []
    if not hand_parts:
        return {"checks": checks, "failures": failures}
    for clip in clips:
        if clip["motion"] != "reload5":
            continue
        events = ego_arms.choreography(device, clip)["events"]
        for event in ("MagOut", "MagIn"):
            frame = clip["frame_start"] + events[event]
            for name, entry in hand_parts["parts"].items():
                scene.frame_set(frame)
                held = entry["node"].matrix_world.translation.copy()
                source = entry["source"]
                # the device part's pose when shown (scale 1): compare positions, the scale swap is the event
                distance = (held - source.matrix_world.translation).length
                turn = math.degrees(entry["node"].matrix_world.to_quaternion().rotation_difference(
                    source.matrix_world.to_quaternion()).angle)
                if turn > 1.0:
                    failures.append(f"{clip['name']} {event}: {name} turned {turn:.1f} deg against {source.name}")
                checks.append({"clip": clip["name"], "event": event, "part": name, "distance_m": round(distance, 5),
                               "turn_degrees": round(turn, 3),
                               "held_scale": round(entry["node"].scale[0], 3), "device_scale": round(source.scale[0], 3)})
                if distance > SWAP_TOLERANCE_M:
                    failures.append(f"{clip['name']} {event}: {name} {distance * 1000:.1f} mm from {source.name}")
    return {"checks": checks, "failures": failures}


# --------------------------------------------------------------------------------------------- exports
def export_assembly(directory, arms_root, clip):
    """<asset>_FPS.fbx/.glb: the assembly (arms + device + hand parts) over the Use clip, like first_person.py's exports."""
    objects = {arms_root, *arms_root.children_recursive}
    for obj in bpy.context.scene.objects:
        obj.select_set(obj in objects)
    bpy.context.view_layer.objects.active = arms_root
    asset = next(obj.name for obj in arms_root.children_recursive if obj.get("ce_attach_bone") == "Prop_R")
    bpy.ops.export_scene.gltf(filepath=str(directory / (asset + ".glb")), export_format="GLB", use_selection=True,
        export_yup=True, export_extras=True, export_animations=True, export_morph=True,
        export_animation_mode="ACTIVE_ACTIONS", export_merge_animation="ACTION",
        export_nla_strips_merged_animation_name=clip, export_frame_range=True,
        export_force_sampling=True, export_cameras=False, export_lights=False)
    bpy.ops.export_scene.fbx(filepath=str(directory / (asset + ".fbx")), use_selection=True,
        object_types={"EMPTY", "MESH"}, axis_forward="-Z", axis_up="Y", global_scale=1,
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", bake_space_transform=False,
        use_mesh_modifiers=False, use_custom_props=True, bake_anim=True,
        bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True, bake_anim_step=1, bake_anim_simplify_factor=0, add_leaf_bones=False)


def check_roundtrip(directory, asset, arms_name, report):
    """Reimport of the assembly exports: every rig node, the device root under Prop_R, Use-clip poses of the chains."""
    bpy.ops.wm.open_mainfile(filepath=str(directory / (asset + ".blend")))
    scene = bpy.context.scene
    names = [obj.name for obj in scene.objects[arms_name].children_recursive if obj.type == "EMPTY"] + [arms_name]
    sample = [1, 14, 30, 60, 97]
    expected = {}
    for frame in sample:
        scene.frame_set(frame)
        expected[frame] = {name: [list(row) for row in scene.objects[name].matrix_world] for name in names}
    results, failures = {}, []
    for kind in ("fbx", "glb"):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path = directory / (asset + "." + kind)
        bpy.ops.import_scene.gltf(filepath=str(path)) if kind == "glb" else bpy.ops.import_scene.fbx(filepath=str(path))
        scene = bpy.context.scene
        found = {obj.name.split(".")[0]: obj for obj in scene.objects}
        missing = sorted(name for name in names if name not in found)
        actions = [obj.animation_data.action for obj in found.values() if obj.animation_data and obj.animation_data.action]
        start = min((action.frame_range[0] for action in actions), default=1.0)
        worst = 0.0
        for frame in sample:
            scene.frame_set(int(round(start)) + frame - 1)
            bpy.context.view_layer.update()
            for name, matrix in expected[frame].items():
                if name in found:
                    worst = max(worst, ego_arms.matrix_error([list(row) for row in found[name].matrix_world], matrix))
        parent = found.get(asset)
        parent_ok = parent is not None and parent.parent is not None and parent.parent.name.split(".")[0] == "Prop_R"
        passed = not missing and worst <= 1e-3 and parent_ok
        results[kind] = {"passed": passed, "missing": missing[:10], "max_matrix_error": worst, "device_under_prop_r": parent_ok}
        if not passed:
            failures.append(f"{kind}: {results[kind]}")
    return {"passed": not failures, "failures": failures, "checks": results, "frames": sample}


def main():
    parser = argparse.ArgumentParser(description="Contract 5 Ego build of a device on the shared arm rig")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--tool", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    build(args.directory.resolve(), args.tool)


if __name__ == "__main__":
    main()
