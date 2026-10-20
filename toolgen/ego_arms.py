"""The shared first-person arm and hand rig of contract 5 (Toolgen 0.19 Kinetic, stage E1 of the arm rebuild).

One arm package for every Ego device instead of arms baked into each device's viewmodel: Shoulder -> UpperArm ->
LowerArm -> Hand per side, Prop_R/Prop_L, three gripping fingers with three links and a two-link thumb, a visible wrist
servo (WristServo on the forearm, WristRotor on the hand), rigid parts at the nodes (no armature, no skinning). Data:
data/ego_arms.json (rig), data/viewmodels.json (arm: lengths, shoulders, elbow pole, hand scale).

As a stage (runs like the other toolgen steps, in the work folder of the package ``ego_arms``):

    blender --background --factory-startup --python toolgen/run_asset.py -- \
        --script toolgen/ego_arms.py --directory <work>

writes ``CubeEscape_EgoArms_Game.blend/.fbx/.glb`` (rest pose, no animation), ``unity_contract_arms.json``, ``qa_arms.json``
(budget, renderers, hierarchy, finger poses within the joint limits and free of contact between non-adjacent parts, FBX
and glTF reimport) and in render tiers ``preview_arms.png``. Devices on contract 5 (toolgen/ego_rig.py) build the same
rig with ``build_rig`` so their clips bind to exactly these nodes (``rig.hash``).

The pure helpers (finger wrap, thumb solve, joint limits, rig hash) import without Blender for the unit tests.
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path

try:
    import bmesh
    import bpy
    from mathutils import Matrix, Quaternion, Vector
    from mathutils.bvhtree import BVHTree
except ImportError:  # unit tests import the pure helpers with the system Python
    bpy = None

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data/ego_arms.json"
VIEWMODELS_PATH = ROOT / "data/viewmodels.json"
PALETTE_PATH = ROOT / "data/game_palette.json"

CONTRACT_FORMAT = 5
SIDES = ("R", "L")
FINGERS = len(json.loads(DATA_PATH.read_text())["rig"]["hand"]["finger_x"])   # gripping fingers (data: one x per finger)
FINGER_LINKS = 3
THUMB_LINKS = 2
FINGER_CLEARANCE = .001          # hand units: the wrapped finger's centre line stays this far outside the cylinder + depth/2
CONTACT_GAP_M = .0005            # finger poses: non-adjacent parts closer than this count as touching (BVH overlap of a grown copy)
ROUNDTRIP_TOLERANCE = 1e-4       # reimported node matrices against the authored ones
# The four look slots of Cube Escape's EquipmentLimbColors.Slots (permanent names) and their look keys.
LOOK_SLOTS = {"M_RobotBody_Matte": "armor", "M_RobotDark_Matte": "mech", "M_Metal_Matte": "metal",
              "M_HazardOrange_Matte": "lights"}
ARMOR, MECH, METAL, LIGHTS = LOOK_SLOTS
SHARED_ARM_CONSUMER = ("Cube Escape „offen“ (E2 of the arm rebuild, version not reserved yet): contract 5 - the arm package "
                       "ego_arms (Assets/Art/ToolgenShared/EgoArms/), devices without arms at Prop_R, frame size 1.0 (the "
                       "factor 1.4 is baked in), support-hand IK between the rig events HandOff/HandOn. Cube Escape 0.104 "
                       "and older read only contract 4.")
OLDER_CONSUMERS = ("python3 toolgen/generate_tools.py --contract 4 (arms baked into each device like Toolgen 0.18; the "
                   "same anchors, maps and clip names)")


# --------------------------------------------------------------------------------------------- data
def load(path=DATA_PATH):
    return json.loads(Path(path).read_text())


def viewmodel_arm(path=VIEWMODELS_PATH):
    return json.loads(Path(path).read_text())["arm"]


def measures(rig, arm):
    """Game-picture measures of the rig: hand scale (hand units -> metres) and the two link lengths (the forearm longer by
    ``forearm_extension``: the elbow leaves the frame while the hand keeps its place, user 20.10.2026 „im Zweifel den
    Unterarm verlängern oder drehen“)."""
    scale = rig["scale"]
    return {"hand_scale": arm["hand_scale"] * scale, "upper_m": arm["upper_length_m"] * scale,
            "forearm_m": arm["forearm_length_m"] * scale * rig.get("forearm_extension", 1.0), "scale": scale}


def thumb_sign(side):
    """+1: the hand's +X is its thumb side (right hand), -1: the left hand (mirrored in X)."""
    return 1 if side == "R" else -1


def node_names(side):
    """Chain and hand nodes of one side in hierarchy order (the order of the rig hash)."""
    names = [f"Shoulder_{side}", f"UpperArm_{side}", f"LowerArm_{side}", f"Hand_{side}", f"Wrist_{side}",
             f"GripContact_{side}", f"Prop_{side}"]
    for finger in range(FINGERS):
        names += [finger_node(side, finger, link) for link in range(FINGER_LINKS)]
    names += [thumb_node(side, link) for link in range(THUMB_LINKS)]
    return names


def finger_node(side, finger, link):
    return f"Fingers_{side}_{finger}" + (f"_{link}" if link else "")


def thumb_node(side, link):
    return f"Thumb_{side}" + (f"_{link}" if link else "")


def all_nodes(asset):
    return [asset, "Socket_Camera", *(name for side in SIDES for name in node_names(side))]


def moving_nodes(side):
    """Nodes that carry a renderer <node>_Mesh (the upper arm never shows)."""
    return [f"LowerArm_{side}", f"Hand_{side}",
            *(finger_node(side, finger, link) for finger in range(FINGERS) for link in range(FINGER_LINKS)),
            *(thumb_node(side, link) for link in range(THUMB_LINKS))]


def rig_hash(entries):
    """sha256 over (name, parent, local rest transform rounded to 1e-6) of every node in hierarchy order: changes with
    the skeleton (clips break), not with meshes or colours. entries: [(name, parent, location, rotation_wxyz, scale)]."""
    def rounded(values):
        return [round(value, 6) + 0.0 for value in values]
    payload = [[name, parent, rounded(location), rounded(rotation), rounded(scale)]
               for name, parent, location, rotation, scale in entries]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


# --------------------------------------------------------------------------------------------- clips
RIG_EVENTS = ("HandOff", "HandOn")      # events of the channel "rig" (support-hand IK); every other event is "action"


def clip_list_v5(tool, profile, device):
    """The ego clips of data/ego_clips.json for this device with the contract 5 reload clips (data/ego_arms.json):
    Reload replaced, ReloadEmpty appended at the end; events carry ``channel`` (action or rig) and Reload/ReloadEmpty
    Start/End. Frames laid out again on the timeline."""
    sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
    import ego_clips
    data = ego_clips.load()
    clips, params = ego_clips.clip_list(data, tool, profile.get("motion"))
    if "ads" in device and "ads" in params:
        params["ads"] = dict(params["ads"], eye_distance_m=device["ads"]["eye_distance_m"])
    reload = device.get("reload")
    result = []
    for clip in clips:
        events = [{"name": event["name"], "offset": event["frame"] - clip["frame_start"]} for event in clip["events"]]
        entry = dict(clip, events=events)
        if clip["motion"] == "reload" and reload and "Reload" in reload:
            entry = reload_clip(clip, "Reload", reload["Reload"])
        result.append(entry)
    base = next((clip for clip in clips if clip["motion"] == "reload"), None)
    if reload and "ReloadEmpty" in reload and base is not None:
        result.append(reload_clip(base, "ReloadEmpty", reload["ReloadEmpty"]))
    start = data["timeline"]["start_frame"]
    for clip in result:
        clip["frame_start"], clip["frame_end"] = start, start + clip["length"]
        clip["events"] = [{"name": event["name"], "frame": start + event["offset"],
                           "channel": "rig" if event["name"] in RIG_EVENTS else "action"} for event in clip["events"]]
        start += clip["length"] + 1 + data["timeline"]["gap_frames"]
    return result, params


def reload_clip(base, suffix, spec):
    stem = base["name"][:-len(base["suffix"])]
    events = [{"name": "Start", "offset": 0}]
    events += [{"name": name, "offset": frame} for name, frame in sorted(spec["events"].items(), key=lambda item: item[1])]
    events.append({"name": "End", "offset": spec["length"]})
    return dict(base, name=stem + suffix, suffix=suffix, motion="reload5", length=spec["length"], events=events,
                choreography=suffix)


# --------------------------------------------------------------------------------------------- finger poses
def _rotate_x(point, degrees):
    """Point (x, y, z) turned about +X: +angle carries +Z towards -Y (a finger curls towards the palm)."""
    angle = math.radians(degrees)
    x, y, z = point
    return (x, y * math.cos(angle) - z * math.sin(angle), y * math.sin(angle) + z * math.cos(angle))


def _rotate_y(point, degrees):
    angle = math.radians(degrees)
    x, y, z = point
    return (x * math.cos(angle) + z * math.sin(angle), y, -x * math.sin(angle) + z * math.cos(angle))


def finger_points(hand, finger, angles):
    """Joint points (y, z) of a finger in the hand's YZ plane (the finger plane) for joint angles in degrees."""
    point = (0.0, hand["knuckle_z"])
    points, total = [point], 0.0
    for length, angle in zip(hand["finger_links"], angles):
        total += angle
        point = (point[0] - length * math.sin(math.radians(total)), point[1] + length * math.cos(math.radians(total)))
        points.append(point)
    return points


def grip_centre(hand, radius):
    """Centre (y, z) of a grip cylinder of ``radius`` (hand units, axis along the hand's X) seated in the palm behind the
    knuckle bar (``grip_seat``: along = share of the radius behind the knuckles, depth = share of palm half thickness +
    radius below the palm's centre plane; below 1 the cylinder presses slightly into the palm pad, like a gloved grip)."""
    seat = hand["grip_seat"]
    return (-(hand["palm_thickness"] / 2 + radius) * seat["depth"], hand["knuckle_z"] - seat["along"] * radius)


def wrap_finger(hand, radius, limits):
    """Joint angles (degrees) that lay the finger links around a cylinder of ``radius`` about the hand's X axis at
    grip_centre: the first joint turns until the first link ends on the cylinder (plus half the finger depth), every
    further link is a chord of that circle in the curl direction. Clamped to the joint limits."""
    cy, cz = grip_centre(hand, radius)
    ring = radius + hand["finger_depth"] / 2 + FINGER_CLEARANCE
    ky, kz = 0.0, hand["knuckle_z"]
    first = hand["finger_links"][0]

    def distance(angle):
        y = ky - first * math.sin(math.radians(angle))
        z = kz + first * math.cos(math.radians(angle))
        return math.hypot(y - cy, z - cz) - ring

    low, high = limits[0]
    angle = high
    if distance(low) <= 0:
        angle = low
    else:
        steps = [low + (high - low) * i / 180 for i in range(181)]
        for a, b in zip(steps, steps[1:]):
            if distance(a) > 0 >= distance(b):
                for _ in range(40):
                    middle = (a + b) / 2
                    a, b = (middle, b) if distance(middle) > 0 else (a, middle)
                angle = b
                break
    angles = [min(max(angle, low), high)]
    joint = (ky - first * math.sin(math.radians(angles[0])), kz + first * math.cos(math.radians(angles[0])))
    total = angles[0]
    for length, (low, high) in zip(hand["finger_links"][1:], limits[1:]):
        step = 2 * math.asin(min(1.0, length / (2 * ring)))
        # clockwise about the centre in the (z, y) plane = the curl direction of +angle
        oy, oz = joint[0] - cy, joint[1] - cz
        cos, sin = math.cos(step), math.sin(step)
        ny, nz = cy + oy * cos - oz * sin, cz + oz * cos + oy * sin
        heading = math.degrees(math.atan2(-(ny - joint[0]), nz - joint[1]))
        best = ((heading - total + 180) % 360 - 180,)
        delta = min(max(best[0], low), high)
        angles.append(delta)
        total += delta
        joint = (joint[0] - length * math.sin(math.radians(total)), joint[1] + length * math.cos(math.radians(total)))
    return [round(value, 3) for value in angles]


def _normal(vector):
    length = math.sqrt(sum(value * value for value in vector))
    return tuple(value / length for value in vector)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def thumb_frame(hand, side):
    """Rest axes (X, Y, Z) of Thumb_<S> in hand space: +Z along the thumb (``rest`` direction, mirrored in X for the left
    hand), -Y towards ``curl`` (where the flexing thumb goes: across the palm to the fingers), X = Y x Z."""
    sign = thumb_sign(side)
    rest = hand["thumb_rest"]
    z = _normal((sign * rest["direction"][0], rest["direction"][1], rest["direction"][2]))
    curl = (sign * rest["curl"][0], rest["curl"][1], rest["curl"][2])
    along = sum(a * b for a, b in zip(curl, z))
    y = _normal(tuple(-(c - along * a) for c, a in zip(curl, z)))
    return _cross(y, z), y, z


def _apply(frame, point):
    return tuple(sum(frame[k][i] * point[k] for k in range(3)) for i in range(3))


def thumb_points(hand, side, angles):
    """Base, middle joint and tip (x, y, z) of the thumb in hand units for [flex, out, tip] (degrees): Thumb_<S> =
    rest frame x R_y(sign * out) x R_x(flex), Thumb_<S>_1 = R_x(tip)."""
    flex, out, tip = angles
    sign = thumb_sign(side)
    frame = thumb_frame(hand, side)
    base = (hand["thumb_base"][0] * sign, hand["thumb_base"][1], hand["thumb_base"][2])

    def oriented(point, extra=0.0):
        return _apply(frame, _rotate_y(_rotate_x(_rotate_x(point, extra), flex), sign * out))
    first, second = hand["thumb_links"]
    middle = tuple(b + v for b, v in zip(base, oriented((0, 0, first))))
    end = tuple(m + v for m, v in zip(middle, oriented((0, 0, second), tip)))
    return base, middle, end


def solve_thumb(hand, side, radius, limits, fingers):
    """Thumb angles [flex, out, tip] that close the thumb around the same grip cylinder as the fingers: the tip on the
    cylinder (plus half the thumb width) just beyond the index fingertip in the curl direction, near the hand's middle,
    the middle joint not inside it. Grid search in 2-degree steps, then 0.5-degree refinement (deterministic)."""
    cy, cz = grip_centre(hand, radius)
    ring = radius + hand["thumb_width"] / 2 + FINGER_CLEARANCE
    sign = thumb_sign(side)
    tip_y, tip_z = finger_points(hand, 0, fingers)[-1]
    reach = math.atan2(tip_y - cy, tip_z - cz) - math.radians(hand["thumb_rest"]["beyond_tip_degrees"])
    target = (sign * hand["thumb_rest"]["tip_x"], cy + ring * math.sin(reach), cz + ring * math.cos(reach))

    def cost(angles):
        _, middle, end = thumb_points(hand, side, angles)
        inside = max(0.0, ring - math.hypot(middle[1] - cy, middle[2] - cz))
        return sum((a - b) ** 2 for a, b in zip(end, target)) + 25 * inside * inside

    def axis(name, step, centre=None, span=None):
        low, high = limits[name]
        if centre is not None:
            low, high = max(low, centre - span), min(high, centre + span)
        count = int(round((high - low) / step))
        return [low + step * i for i in range(count + 1)]
    best = min(((cost((f, o, t)), (f, o, t)) for f in axis("flex", 2) for o in axis("out", 2) for t in axis("tip", 2)))
    f0, o0, t0 = best[1]
    best = min(((cost((f, o, t)), (f, o, t)) for f in axis("flex", .5, f0, 2) for o in axis("out", .5, o0, 2)
                for t in axis("tip", .5, t0, 2)))
    return [round(value, 3) for value in best[1]]


def pose_angles(rig, name, side="R"):
    """Joint angles of the named finger pose: {"fingers": [[a0, a1, a2] x 3], "thumb": [flex, out, tip]}."""
    spec = rig["finger_poses"][name]
    hand, limits = rig["hand"], rig["limits_degrees"]
    if "wrap" in spec:
        finger = wrap_finger(hand, spec["wrap"], limits["finger"])
        fingers = [list(finger) for _ in range(FINGERS)]
        thumb = solve_thumb(hand, side, spec["wrap"], limits["thumb"], finger)
    else:
        fingers = [list(values) for values in spec["fixed"]]
        thumb = list(spec["thumb"])
    if "finger_0" in spec:
        fingers[0] = list(spec["finger_0"])
    return {"fingers": fingers, "thumb": thumb}


def limit_errors(rig, name, angles):
    limits = rig["limits_degrees"]
    errors = []
    for index, finger in enumerate(angles["fingers"]):
        for link, (value, (low, high)) in enumerate(zip(finger, limits["finger"])):
            if not low - 1e-6 <= value <= high + 1e-6:
                errors.append(f"{name}: finger {index} joint {link} at {value} outside {low}..{high}")
    for value, key in zip(angles["thumb"], ("flex", "out", "tip")):
        low, high = limits["thumb"][key]
        if not low - 1e-6 <= value <= high + 1e-6:
            errors.append(f"{name}: thumb {key} at {value} outside {low}..{high}")
    return errors


def pose_library(rig):
    """Every named finger pose for both sides (the right hand's angles; the left hand mirrors only the thumb's out)."""
    return {name: pose_angles(rig, name) for name in rig["finger_poses"] if name != "note"}


# --------------------------------------------------------------------------------------------- Blender: geometry
class PartMesh:
    """Rigid parts of one node merged into one mesh (one renderer per moving node)."""

    def __init__(self, materials):
        self.bm = bmesh.new()
        self.materials = list(materials)

    def _add(self, part, matrix, material):
        index = [entry.name for entry in self.materials].index(material)
        mapping = {}
        for vertex in part.verts:
            mapping[vertex] = self.bm.verts.new(matrix @ vertex.co)
        for face in part.faces:
            new = self.bm.faces.new([mapping[vertex] for vertex in face.verts])
            new.material_index = index
        part.free()

    def box(self, center, size, material, rotation=None, bevel=.004, taper=0.0, segments=2):
        part = bmesh.new()
        bmesh.ops.create_cube(part, size=1)
        for vertex in part.verts:
            vertex.co = Vector([vertex.co[i] * size[i] for i in range(3)])
            factor = 1 + taper * vertex.co.z / size[2]
            vertex.co.x *= factor
            vertex.co.y *= factor
        if bevel > 0:
            bmesh.ops.bevel(part, geom=list(part.edges), offset=min(bevel, min(size) * .35), segments=segments,
                            profile=.5, affect="EDGES", clamp_overlap=True)
        self._add(part, Matrix.LocRotScale(Vector(center), rotation or Quaternion(), Vector((1, 1, 1))), material)

    def cylinder(self, center, radius, length, material, axis=(0, 0, 1), segments=12, bevel=.0015):
        part = bmesh.new()
        bmesh.ops.create_cone(part, cap_ends=True, cap_tris=False, segments=segments, radius1=radius, radius2=radius,
                              depth=length)
        if bevel > 0:
            bmesh.ops.bevel(part, geom=[edge for edge in part.edges if edge.is_manifold and edge.calc_face_angle() > .7],
                            offset=min(bevel, length * .15), segments=1, affect="EDGES", clamp_overlap=True)
        rotation = Vector((0, 0, 1)).rotation_difference(Vector(axis))
        self._add(part, Matrix.LocRotScale(Vector(center), rotation, Vector((1, 1, 1))), material)

    def finish(self, name, parent):
        bmesh.ops.recalc_face_normals(self.bm, faces=list(self.bm.faces))
        used = sorted({face.material_index for face in self.bm.faces})
        for face in self.bm.faces:
            face.material_index = used.index(face.material_index)
        mesh = bpy.data.meshes.new(name)
        self.bm.to_mesh(mesh)
        self.bm.free()
        for index in used:           # only the slots in use (glTF drops empty ones)
            mesh.materials.append(self.materials[index])
        uv = mesh.uv_layers.new(name="UVMap")
        for polygon in mesh.polygons:
            major = max(range(3), key=lambda i: abs(polygon.normal[i]))
            axes = ((1, 2), (0, 2), (0, 1))[major]
            for index in polygon.loop_indices:
                point = mesh.vertices[mesh.loops[index].vertex_index].co
                uv.data[index].uv = (point[axes[0]] * 2 + .5, point[axes[1]] * 2 + .5)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        parent.users_collection[0].objects.link(obj)
        obj.parent = parent
        obj.matrix_parent_inverse = Matrix()
        obj["ce_role"] = "ego_arm"
        return obj


def empty(name, parent, location=(0, 0, 0), rotation=None, collection=None):
    obj = bpy.data.objects.new(name, None)
    (collection or parent.users_collection[0]).objects.link(obj)
    obj.empty_display_size = .015
    if parent is not None:
        obj.parent = parent
        obj.matrix_parent_inverse = Matrix()
    obj.rotation_mode = "QUATERNION"
    obj.location = location
    obj.rotation_quaternion = rotation or Quaternion()
    return obj


def forearm_mesh(materials, node, side, rig, length):
    """Unterarm with plates, insets, servo rods, cuff and the wrist servo housing (fork) at the wrist."""
    f = rig["forearm"]
    part = PartMesh(materials)
    start, span = .0, f["plate_span"]
    centre = length * (start + .5)
    part.cylinder((0, 0, length * .5), f["core_radius"], length, MECH)
    part.box((0, 0, centre), (f["plate"][0], f["plate"][1], length * span), ARMOR, bevel=.012, taper=-.18)
    for face in (-1, 1):
        panel = (0, face * f["plate"][1] / 2 * .985, centre)
        part.box(panel, (.0326, .0078, length * span * .77), MECH, bevel=.004)
        part.box((0, face * (f["plate"][1] / 2 * .985 + .0043), centre), (.0206, .0043, length * span * .67), LIGHTS,
                 bevel=.003)
        for x in (-.037, .037):
            for offset in (-span * .3, span * .3):
                part.box((x, face * f["plate"][1] / 2 * .975, length * (.5 + offset)), (.0078, .0052, .0078), MECH,
                         bevel=0)
    for sign in (-1, 1):
        part.cylinder((sign * .039, 0, length * .5), .0086, length, METAL, segments=10)
    part.cylinder((0, 0, length * .955), f["cuff_radius"], .0217, MECH)
    # WristServo: housing across the wrist with two fork cheeks that carry the hand's rotor axle (hand-local X)
    servo_z = length - f["fork_reach"] * .25
    part.cylinder((0, 0, servo_z), f["servo_radius"], f["servo_length"], METAL, axis=(1, 0, 0), segments=16)
    for sign in (-1, 1):
        part.box((sign * (f["servo_length"] / 2 + .0045), 0, length + f["fork_reach"] * .15),
                 (.009, f["servo_radius"] * 1.7, f["fork_reach"] * 1.5), ARMOR, bevel=.003)
    obj = part.finish(node.name + "_Mesh", node)
    obj["ce_parts"] = json.dumps(["Forearm", f"WristServo_{side}"])
    return obj


def hand_mesh(materials, node, side, rig, scale):
    """Palm, back plate with inset and bolts, knuckle bar and the wrist rotor (drum, caps, hubs) at the wrist pivot."""
    hand = rig["hand"]
    sign = thumb_sign(side)
    s = scale
    part = PartMesh(materials)
    length, start = hand["palm_length"], hand["palm_start"]
    mid = start + length / 2
    part.box((0, 0, mid * s), (hand["palm_width"] * s, hand["palm_thickness"] * .72 * s, length * s), METAL, bevel=.010 * s)
    part.box((0, -hand["palm_thickness"] * .36 * s, (mid + .004) * s),
             (hand["palm_width"] * .86 * s, .010 * s, length * .78 * s), MECH, bevel=.004 * s)
    back = hand["palm_thickness"] * .36
    part.box((0, (back + .004) * s, (mid + .002) * s), (hand["palm_width"] * .96 * s, .012 * s, length * .92 * s), MECH,
             bevel=.005 * s)
    part.box((0, (back + .010) * s, (mid + .002) * s), (hand["palm_width"] * .90 * s, .012 * s, length * .86 * s), ARMOR,
             bevel=.006 * s, taper=.10)
    part.box((-sign * .010 * s, (back + .0168) * s, (mid + .006) * s), (.014 * s, .003 * s, length * .56 * s), LIGHTS,
             bevel=.0015 * s)
    for x in (-.026, .026):
        for z in (-.024, .024):
            part.box((x * s, (back + .0165) * s, (mid + z) * s), (.007 * s, .004 * s, .007 * s), MECH, bevel=0)
    part.cylinder((0, .002 * s, hand["knuckle_z"] * s), .011 * s, hand["palm_width"] * 1.04 * s, MECH, axis=(1, 0, 0),
                  segments=12)
    # WristRotor: drum on the hand's flex axis inside the servo fork, white caps and orange hubs that turn with the hand
    servo = rig["forearm"]
    part.cylinder((0, 0, 0), servo["servo_radius"] * .78, servo["servo_length"] * .82, MECH, axis=(1, 0, 0), segments=16)
    for x in (-1, 1):
        part.cylinder((x * (servo["servo_length"] / 2 + .0105), 0, 0), servo["servo_radius"] * .82, .006, ARMOR,
                      axis=(1, 0, 0), segments=16)
        part.cylinder((x * (servo["servo_length"] / 2 + .0145), 0, 0), servo["servo_radius"] * .36, .004, LIGHTS,
                      axis=(1, 0, 0), segments=12)
    part.box((0, 0, start * .55 * s), (hand["palm_width"] * .55 * s, hand["palm_thickness"] * .55 * s, start * 1.3 * s),
             MECH, bevel=.003 * s)
    obj = part.finish(node.name + "_Mesh", node)
    obj["ce_parts"] = json.dumps(["Palm", "Backhand", f"WristRotor_{side}"])
    return obj


def finger_mesh(materials, node, rig, link, scale, last):
    hand = rig["hand"]
    s = scale
    length = (hand["finger_links"] if not node.name.startswith("Thumb_") else hand["thumb_links"])[link]
    width = hand["finger_width"] if not node.name.startswith("Thumb_") else hand["thumb_width"]
    depth = hand["finger_depth"] * (1.0 if not node.name.startswith("Thumb_") else 1.08)
    part = PartMesh(materials)
    part.box((0, 0, length * .52 * s), (width * .86 * s, depth * .86 * s, length * .96 * s), MECH,
             bevel=(.0055 if last else .0035) * s, taper=-.08 if last else 0.0)
    if not last or node.name.startswith("Thumb_"):
        part.box((0, depth * .40 * s, length * .52 * s), (width * .94 * s, depth * .34 * s, length * .74 * s),
                 ARMOR, bevel=.003 * s)
    part.cylinder((0, 0, 0), depth * .40 * s, width * 1.02 * s, METAL, axis=(1, 0, 0), segments=8, bevel=0)
    return part.finish(node.name + "_Mesh", node)


# --------------------------------------------------------------------------------------------- Blender: rig
def finger_rotation(degrees):
    return Quaternion((1, 0, 0), math.radians(degrees))


def thumb_rotation(rig, side, flex, out):
    frame = Matrix(thumb_frame(rig["hand"], side)).transposed().to_quaternion()
    return frame @ Quaternion((0, 1, 0), math.radians(thumb_sign(side) * out)) @ Quaternion((1, 0, 0), math.radians(flex))


def apply_pose(rig_nodes, rig, side, angles):
    """Sets the finger and thumb joint rotations of one hand (does not key)."""
    for finger, values in enumerate(angles["fingers"]):
        for link, value in enumerate(values):
            rig_nodes[finger_node(side, finger, link)].rotation_quaternion = finger_rotation(value)
    flex, out, tip = angles["thumb"]
    rig_nodes[thumb_node(side, 0)].rotation_quaternion = thumb_rotation(rig, side, flex, out)
    rig_nodes[thumb_node(side, 1)].rotation_quaternion = finger_rotation(tip)


def facing(kind, side):
    """Hand rotation in camera space for the bind pose: grip (knuckles forward, palm to the tool's side, thumb up) or
    underhand (palm up, knuckles forward)."""
    if kind == "grip":
        columns = ((0, 0, 1), (-1, 0, 0), (0, -1, 0)) if side == "R" else ((0, 0, -1), (1, 0, 0), (0, -1, 0))
    else:
        columns = ((-1, 0, 0), (0, 0, -1), (0, -1, 0)) if side == "L" else ((1, 0, 0), (0, 0, -1), (0, -1, 0))
    return Matrix(columns).transposed().to_quaternion()


def place_chain(nodes, side, shoulder, elbow, hand_matrix):
    """Rotations of one chain for given shoulder and elbow points and a hand pose (camera space): Shoulder at ``shoulder``
    (unrotated), UpperArm towards the elbow with the elbow hinge as its X axis, LowerArm towards the wrist rolled with the
    hand (the wrist only bends, the servo shows it), Hand at the pose. The caller keeps the link lengths (rigid chain)."""
    shoulder, elbow = Vector(shoulder), Vector(elbow)
    wrist = hand_matrix.to_translation()
    hand_rotation = hand_matrix.to_quaternion()
    z_f = (wrist - elbow).normalized()
    y_h = hand_rotation @ Vector((0, 1, 0))
    y_f = y_h - z_f * y_h.dot(z_f)
    if y_f.length < 1e-6:
        y_f = (hand_rotation @ Vector((0, 0, 1))) - z_f * (hand_rotation @ Vector((0, 0, 1))).dot(z_f)
    y_f.normalize()
    x_f = y_f.cross(z_f)
    forearm_rotation = Matrix((x_f, y_f, z_f)).transposed().to_quaternion()
    z_u = (elbow - shoulder).normalized()
    hinge = z_u.cross(z_f)
    if hinge.length < 1e-6:
        hinge = x_f - z_u * x_f.dot(z_u)
    x_u = hinge.normalized()
    y_u = z_u.cross(x_u)
    upper_rotation = Matrix((x_u, y_u, z_u)).transposed().to_quaternion()
    shoulder_node = nodes[f"Shoulder_{side}"]
    shoulder_node.location = shoulder
    shoulder_node.rotation_quaternion = Quaternion()
    nodes[f"UpperArm_{side}"].rotation_quaternion = upper_rotation
    nodes[f"LowerArm_{side}"].rotation_quaternion = upper_rotation.inverted() @ forearm_rotation
    nodes[f"Hand_{side}"].rotation_quaternion = forearm_rotation.inverted() @ hand_rotation


def solve_chain(nodes, side, shoulder, hand_matrix, lengths, pole):
    """place_chain with the elbow from the two-link solution in the plane of ``pole``."""
    sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
    from motion_profiles import solve_elbow
    wrist = hand_matrix.to_translation()
    elbow = Vector(solve_elbow(tuple(shoulder), tuple(wrist), *lengths, tuple(pole)))
    place_chain(nodes, side, shoulder, elbow, hand_matrix)
    return elbow


def wrist_bend_degrees(nodes, side):
    """Wrist measure of contract 5: angle between LowerArm_<S> +Z (elbow -> wrist) and Hand_<S> +Z (wrist -> knuckles)."""
    lower = nodes[f"LowerArm_{side}"].matrix_world.to_quaternion() @ Vector((0, 0, 1))
    hand = nodes[f"Hand_{side}"].matrix_world.to_quaternion() @ Vector((0, 0, 1))
    return math.degrees(lower.angle(hand))


def build_rig(collection, rig=None, arm=None, materials=None, meshes=True):
    """The rig in ``collection``: root CubeEscape_EgoArms (camera space), Socket_Camera, both chains with hands, fingers
    and thumbs, the renderers <node>_Mesh (``meshes``), in the bind pose. Returns {"root", "nodes", "renderers",
    "measures", "rig", "arm", "pose": {side: angles}}."""
    rig = rig or load()["rig"]
    arm = arm or viewmodel_arm()
    size = measures(rig, arm)
    hs = size["hand_scale"]
    hand = rig["hand"]
    root = empty(rig["asset"], None, collection=collection)
    root["ce_role"] = "ego_arms"
    root["ce_rig_id"] = rig["id"]
    root["ce_rig_version"] = rig["version"]
    nodes = {root.name: root}
    camera = empty("Socket_Camera", root)
    camera["ce_role"] = "camera"
    nodes[camera.name] = camera
    renderers = []
    open_pose = pose_angles(rig, "open")
    for side in SIDES:
        sign = thumb_sign(side)
        shoulder = empty(f"Shoulder_{side}", root)
        upper = empty(f"UpperArm_{side}", shoulder)
        lower = empty(f"LowerArm_{side}", upper, (0, 0, size["upper_m"]))
        joint = empty(f"Hand_{side}", lower, (0, 0, size["forearm_m"]))
        joint["robogen_joint"] = joint.name
        wrist = empty(f"Wrist_{side}", joint)
        wrist["ce_role"] = "wrist"
        wrist["ce_knuckle_axis"] = f"+Z of Hand_{side}"
        contact = empty(f"GripContact_{side}", joint, Vector(hand["contact"]) * hs)
        contact["ce_role"] = "hand_contact"
        prop_y, prop_z = grip_centre(hand, hand["prop_radius"])
        prop = empty(f"Prop_{side}", joint, Vector((0, prop_y, prop_z)) * hs)
        prop["ce_role"] = "prop"
        prop["ce_note"] = "grip point inside the curled fingers (Robogen Prop_); devices hang here (attach)"
        for obj in (shoulder, upper, lower, joint, wrist, contact, prop):
            nodes[obj.name] = obj
        for finger in range(FINGERS):
            parent = joint
            location = Vector((sign * hand["finger_x"][finger], 0, hand["knuckle_z"])) * hs
            for link in range(FINGER_LINKS):
                node = empty(finger_node(side, finger, link), parent, location)
                nodes[node.name] = node
                parent = node
                location = Vector((0, 0, hand["finger_links"][link] * hs))
        base = Vector((sign * hand["thumb_base"][0], hand["thumb_base"][1], hand["thumb_base"][2])) * hs
        thumb = empty(thumb_node(side, 0), joint, base)
        tip = empty(thumb_node(side, 1), thumb, (0, 0, hand["thumb_links"][0] * hs))
        nodes[thumb.name], nodes[tip.name] = thumb, tip
        if meshes:
            renderers.append(forearm_mesh(materials, lower, side, rig, size["forearm_m"]))
            renderers.append(hand_mesh(materials, joint, side, rig, hs))
            for finger in range(FINGERS):
                for link in range(FINGER_LINKS):
                    renderers.append(finger_mesh(materials, nodes[finger_node(side, finger, link)], rig, link, hs,
                                                 link == FINGER_LINKS - 1))
            for link in range(THUMB_LINKS):
                renderers.append(finger_mesh(materials, nodes[thumb_node(side, link)], rig, link, hs,
                                             link == THUMB_LINKS - 1))
        apply_pose(nodes, rig, side, open_pose)
    bind_pose(nodes, rig, arm, size)
    bpy.context.view_layer.update()
    return {"root": root, "nodes": nodes, "renderers": renderers, "measures": size, "rig": rig, "arm": arm,
            "pose": {side: open_pose for side in SIDES}}


def side_pole(arm, side):
    pole = arm["elbow_pole"]
    return Vector((pole[0] * (1 if side == "L" else -1), pole[1], pole[2]))


def straight_hand(shoulder, wrist, lengths, pole, rotation):
    """Hand rotation with a straight wrist: +Z along the solved forearm, rolled so its +Y follows ``rotation``'s +Y."""
    sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
    from motion_profiles import solve_elbow
    elbow = Vector(solve_elbow(tuple(shoulder), tuple(wrist), *lengths, tuple(pole)))
    z = (Vector(wrist) - elbow).normalized()
    y = rotation @ Vector((0, 1, 0))
    y = (y - z * y.dot(z)).normalized()
    return Matrix((y.cross(z), y, z)).transposed().to_quaternion()


def bind_pose(nodes, rig, arm, size):
    bind = rig["bind"]
    lengths = (size["upper_m"], size["forearm_m"])
    for side in SIDES:
        shoulder, wrist, pole = Vector(arm["shoulders"][side]), Vector(bind["hand"][side]), side_pole(arm, side)
        rotation = straight_hand(shoulder, wrist, lengths, pole, facing(bind["facing"][side], side))
        solve_chain(nodes, side, shoulder, Matrix.LocRotScale(wrist, rotation, Vector((1, 1, 1))), lengths, pole)


def hierarchy_entries(nodes, order):
    entries = []
    for name in order:
        obj = nodes[name]
        location, rotation, scale = obj.location, obj.rotation_quaternion.normalized(), obj.scale
        if rotation.w < 0:
            rotation = -rotation
        entries.append((name, obj.parent.name if obj.parent else None, tuple(location), tuple(rotation), tuple(scale)))
    return entries


def rig_hash_of(nodes, asset):
    return rig_hash(hierarchy_entries(nodes, all_nodes(asset)))


def triangle_count(mesh):
    return sum(len(polygon.vertices) - 2 for polygon in mesh.polygons)


# --------------------------------------------------------------------------------------------- QA
def contact_pairs(renderers, side):
    """Pairs of renderers of one hand that must never touch: different fingers, the thumb against the fingers' outer
    links, outer finger links against the palm (adjacent links and the first links at the knuckle bar may meet)."""
    names = {obj.name: obj for obj in renderers}
    fingers = [[names[finger_node(side, finger, link) + "_Mesh"] for link in range(FINGER_LINKS)] for finger in range(FINGERS)]
    thumb = [names[thumb_node(side, link) + "_Mesh"] for link in range(THUMB_LINKS)]
    palm = names[f"Hand_{side}_Mesh"]
    pairs = []
    for a in range(FINGERS):
        for b in range(a + 1, FINGERS):
            pairs += [(x, y) for x in fingers[a] for y in fingers[b]]
    pairs += [(palm, links[2]) for links in fingers]
    pairs += [(thumb[1], links[link]) for links in fingers for link in (1, 2)]
    return pairs


def bvh(obj, grow=0.0):
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(graph)
    matrix = evaluated.matrix_world
    mesh = evaluated.data
    normals = [matrix.to_3x3() @ vertex.normal for vertex in mesh.vertices]
    points = [matrix @ vertex.co + normal.normalized() * grow for vertex, normal in zip(mesh.vertices, normals)]
    return BVHTree.FromPolygons(points, [tuple(polygon.vertices) for polygon in mesh.polygons], epsilon=0.0)


def pose_contacts(rig_state, side, angles):
    apply_pose(rig_state["nodes"], rig_state["rig"], side, angles)
    bpy.context.view_layer.update()
    trees = {}
    touching = []
    for a, b in contact_pairs(rig_state["renderers"], side):
        for obj in (a, b):
            if obj.name not in trees:
                trees[obj.name] = bvh(obj, CONTACT_GAP_M / 2)
        if trees[a.name].overlap(trees[b.name]):
            touching.append([a.name, b.name])
    return touching


def matrix_error(a, b):
    return max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4))


def check_reimport(kind, path, expected):
    """FBX/glTF reimport: every node and renderer by name, the same parents, world matrices of the rest pose, the four
    slots on every renderer, the triangle count."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(filepath=str(path)) if kind == "glb" else bpy.ops.import_scene.fbx(filepath=str(path))
    if "FINISHED" not in result:
        raise RuntimeError(f"{kind} import failed")
    bpy.context.view_layer.update()

    def base(name):
        return name.split(".")[0]
    objects = {base(obj.name): obj for obj in bpy.context.scene.objects}
    missing = sorted(name for name in [*expected["nodes"], *expected["renderers"]] if name not in objects)
    parents = sorted(name for name, parent in expected["parents"].items()
                     if name in objects and (base(objects[name].parent.name) if objects[name].parent else None) != parent)
    worst = 0.0
    for name, matrix in expected["matrices"].items():
        if name in objects:
            worst = max(worst, matrix_error([list(row) for row in objects[name].matrix_world], matrix))
    slots = sorted(name for name in expected["renderers"] if name in objects
                   and sorted({base(m.name) for m in objects[name].data.materials if m}) != expected["slots"][name])
    count = sum(triangle_count(objects[name].data) for name in expected["renderers"] if name in objects)
    # glTF stores triangles; the FBX importer restores the authored n-gons: compare after triangulation
    passed = not missing and not parents and not slots and worst <= ROUNDTRIP_TOLERANCE and count == expected["triangles"]
    return {"passed": passed, "missing": missing, "wrong_parent": parents, "max_matrix_error": worst,
            "wrong_slots": slots, "triangles": count}


# --------------------------------------------------------------------------------------------- contract
def unity_local(obj):
    sys.path.insert(0, str(ROOT / "toolgen"))
    from game_export import local_transform
    return local_transform(obj)


def contract_document(state, files, report, palette, budget):
    from version import CODENAME, VERSION
    rig, size, nodes = state["rig"], state["measures"], state["nodes"]
    order = all_nodes(rig["asset"])
    renderers = state["renderers"]
    library = pose_library(rig)
    return {
        "format": CONTRACT_FORMAT, "kind": "ego_arms", "generator": "toolgen", "version": f"{VERSION} {CODENAME}",
        "asset": rig["asset"], "model": rig["asset"] + "_Game",
        "rig": {"id": rig["id"], "version": rig["version"], "hash": state["hash"],
                "hash_rule": "sha256 over [name, parent, local location, local rotation (w, x, y, z), local scale] of every "
                             "node in 'nodes' order, rounded to 1e-6, Blender space (JSON without spaces). Changes with "
                             "the skeleton (clips break), never with meshes or colours; version rises with it."},
        "units": "meter", "scale": 1.0,
        "axes": {"blender": {"up": "+Z", "forward": "-Y"}, "unity": {"up": "+Y", "forward": "+Z"},
                 "position": "unity = (-x, z, -y) of blender", "rotation": "unity quaternion (x, y, z, w) of M R M^T, "
                 "M = [[-1,0,0],[0,0,1],[0,-1,0]]",
                 "fbx": {"axis_forward": "-Z", "axis_up": "Y", "bake_space_transform": False,
                         "unity_import": "Generic, bakeAxisConversion on, optimizeGameObjects off (like contract 4)."},
                 "half_turn": "Turn the root of the ASSEMBLED hierarchy (arms + device) once by 180 degrees about Unity's Y, "
                              "like every Toolgen prefab root (contract 4 axes.fbx.export_yaw_degrees); the device root under "
                              "Prop_R gets no turn of its own. Measured in Toolgen with the anchor test of the clips files "
                              "(qa_viewmodel.json assembly_anchors); Cube Escape confirms it in E2."},
        "root": rig["asset"],
        "nodes": [{"name": name, "parent": nodes[name].parent.name if nodes[name].parent else None,
                   "role": nodes[name].get("ce_role"), **unity_local(nodes[name])} for name in order],
        "chains": {side: [f"Shoulder_{side}", f"UpperArm_{side}", f"LowerArm_{side}", f"Hand_{side}"] for side in SIDES},
        "fingers": {side: {"fingers": [[finger_node(side, finger, link) for link in range(FINGER_LINKS)]
                                       for finger in range(FINGERS)],
                           "thumb": [thumb_node(side, link) for link in range(THUMB_LINKS)],
                           "trigger_finger": finger_node(side, 0, 0)} for side in SIDES},
        "local_axes": {"chain": "+Z along every link from proximal to distal (Shoulder->elbow, elbow->wrist, wrist->knuckles); "
                                "local translations of LowerArm_<S> (0, 0, upper_m) and Hand_<S> (0, 0, forearm_m) are "
                                "constant: clips rotate the chain and may move only Shoulder_<S>",
                       "hand": "Hand_<S>: origin = wrist pivot, +Z to the knuckles, +Y back of the hand, -Y palm; +X is the "
                               "thumb side of the right hand, -X of the left (mirrored)",
                       "fingers": "every finger and thumb link bends about its local +X (positive = towards the palm); "
                                  "Thumb_<S> = thumb rest frame x R_y(sign * out) x R_x(flex), sign +1 right / -1 left "
                                  "(rest frame: hand.thumb_rest of data/ego_arms.json)",
                       "prop": "Prop_<S>: centre of the grip cylinder (radius prop_radius, axis along the hand's X) inside "
                               "the curled fingers; its own rotation is information only, contract is the device's attach"},
        "lengths_m": {"upper_arm": round(size["upper_m"], 6), "forearm": round(size["forearm_m"], 6),
                      "hand_scale": round(size["hand_scale"], 6)},
        "scale_reference": {"baked_factor": rig["scale"], "toolgen_hand_scale": state["arm"]["hand_scale"],
                            "note": "The hand of the Cube Escape rifles until Toolgen 0.18 (Toolgen hand_scale x hip.scale "
                                    "1.4) is baked in: Cube Escape uses frame size 1.0 for contract 5 devices and ignores "
                                    "hip.scale for them."},
        "joint_limits_degrees": rig["limits_degrees"],
        "measures": {"wrist_bend": "angle between LowerArm_<S> +Z (elbow -> wrist) and Hand_<S> +Z (wrist -> knuckles); target "
                                   f"{rig['limits_degrees']['wrist_target']}, limit {rig['limits_degrees']['wrist_limit']}",
                     "hand_touch": "nearest distance of the hand's renderers to the device surface (unity_contract_fps.json)"},
        "finger_poses": {"names": list(library), "right": library,
                         "left": "the same angles; the thumb's out turns about -Y (mirrored hand)",
                         "rule": "ids are permanent, append only; a device lists the angles of the poses it uses in "
                                 "unity_contract_fps.json finger_poses (its own grip radii)"},
        "bind_pose": {"fingers": "open", "note": rig["bind"]["note"]},
        "renderers": [{"name": obj.name, "node": obj.parent.name, "parts": json.loads(obj.get("ce_parts", "[]")),
                       "materials": [m.name for m in obj.data.materials], "triangles": triangle_count(obj.data),
                       "renderer": "MeshRenderer"} for obj in renderers],
        "materials": {name: palette["materials"][name] for name in LOOK_SLOTS},
        "look": {"slots": LOOK_SLOTS, "rule": "Cube Escape colours the four slots with EquipmentLimbColors (palette x look / "
                                              "classic); no MT_ slots, no UV1, no maps (UV1 comes additively with E5)"},
        "budget": budget,
        "colliders": [], "collision": "none: first-person arms (drawn by the viewmodel camera)",
        "clips": [], "animation": "none: the clips of each contract 5 device animate these nodes (unity_contract_fps.json)",
        "minimum_consumer": {"shared_arm_rig": SHARED_ARM_CONSUMER},
        "older_consumers": OLDER_CONSUMERS,
        "qa": "qa_arms.json",
        "files": {kind: {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                  for kind, path in files.items()},
    }


def render_preview(work, state):
    """preview_arms.png: the viewmodel camera (46.69 degrees vertical, 16:9) on both hands in the grip / underhand poses."""
    camera_data = json.loads(VIEWMODELS_PATH.read_text())["camera"]
    scene = bpy.context.scene
    data = bpy.data.cameras.new("PreviewCamera")
    data.sensor_fit = "VERTICAL"
    data.sensor_height = 24
    data.lens = 12 / math.tan(math.radians(camera_data["vertical_fov_degrees"]) / 2)
    data.clip_start = camera_data["near_clip_m"]
    camera = bpy.data.objects.new("PreviewCamera", data)
    scene.collection.objects.link(camera)
    camera.rotation_euler = (math.radians(90), 0, math.radians(180))      # looks along -Y, up +Z
    scene.camera = camera
    light = bpy.data.objects.new("PreviewLight", bpy.data.lights.new("PreviewLight", "SUN"))
    light.data.energy = 3.5
    light.rotation_euler = (math.radians(35), math.radians(-25), math.radians(20))
    scene.collection.objects.link(light)
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (.08, .09, .11, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = .8
    scene.world = world
    scene.render.engine = "CYCLES"
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    apply_pose(state["nodes"], state["rig"], "R", pose_angles(state["rig"], "grip"))
    apply_pose(state["nodes"], state["rig"], "L", pose_angles(state["rig"], "underhand", "L"))
    bpy.context.view_layer.update()
    scene.render.filepath = str(work / "preview_arms.png")
    bpy.ops.render.render(write_still=True)


def build_package(work):
    sys.path.insert(0, str(ROOT / "toolgen"))
    import game_export
    data = load()
    rig = data["rig"]
    palette = json.loads(PALETTE_PATH.read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = rig["asset"]
    collection = bpy.data.collections.new(rig["asset"])
    scene.collection.children.link(collection)
    created = game_export.palette_materials({"materials": {name: palette["materials"][name] for name in LOOK_SLOTS}})
    state = build_rig(collection, rig, materials=[created[name] for name in LOOK_SLOTS])
    state["hash"] = rig_hash_of(state["nodes"], rig["asset"])
    return state, palette, game_export


def main():
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description="Shared first-person arm rig of contract 5 (package ego_arms)")
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    work = args.directory.resolve()
    work.mkdir(parents=True, exist_ok=True)
    checks = {}
    report = {"kind": "ego_arms", "passed": False}
    try:
        state, palette, game_export = build_package(work)
        rig, nodes, renderers = state["rig"], state["nodes"], state["renderers"]
        game = rig["asset"] + "_Game"
        total = sum(triangle_count(obj.data) for obj in renderers)
        checks["budget"] = {"passed": total <= rig["budget_triangles"], "triangles": total, "limit": rig["budget_triangles"]}
        names = sorted(obj.name for obj in renderers)
        wanted = sorted(node + "_Mesh" for side in SIDES for node in moving_nodes(side))
        checks["renderers"] = {"passed": names == wanted and len(names) <= rig["max_renderers"]
                               and all(obj.parent.name + "_Mesh" == obj.name for obj in renderers)
                               and all({m.name for m in obj.data.materials} <= set(LOOK_SLOTS) for obj in renderers),
                               "count": len(names), "limit": rig["max_renderers"]}
        order = all_nodes(rig["asset"])
        checks["hierarchy"] = {"passed": sorted(order) == sorted(nodes), "nodes": len(order)}
        library = pose_library(rig)
        limit_problems = [error for name, angles in library.items() for error in limit_errors(rig, name, angles)]
        checks["finger_pose_limits"] = {"passed": not limit_problems, "errors": limit_problems, "poses": list(library)}
        touching = {}
        for name in library:
            for side in SIDES:
                found = pose_contacts(state, side, pose_angles(rig, name, side))
                if found:
                    touching[f"{name}/{side}"] = found
        checks["finger_pose_contacts"] = {"passed": not touching, "touching": touching, "gap_m": CONTACT_GAP_M,
                                          "note": "non-adjacent parts of a hand (other fingers, thumb tip, palm against "
                                                  "outer links) never touch in a library pose"}
        for side in SIDES:
            apply_pose(nodes, rig, side, state["pose"][side])
        bpy.context.view_layer.update()
        bend = {side: round(wrist_bend_degrees(nodes, side), 3) for side in SIDES}
        checks["bind_wrist"] = {"passed": all(value <= rig["limits_degrees"]["wrist_limit"] for value in bend.values()),
                                "degrees": bend}
        checks["rig_hash"] = {"passed": state["hash"] == rig_hash_of(nodes, rig["asset"]), "hash": state["hash"]}
        expected = {"nodes": order, "renderers": names, "parents": {name: nodes[name].parent.name if nodes[name].parent else None
                                                                    for name in order},
                    "matrices": {name: [list(row) for row in nodes[name].matrix_world] for name in order},
                    "slots": {obj.name: sorted({m.name for m in obj.data.materials}) for obj in renderers},
                    "triangles": total}
        scene = bpy.context.scene
        files = {"blend": work / (game + ".blend"), "fbx": work / (game + ".fbx"), "glb": work / (game + ".glb")}
        bpy.ops.wm.save_as_mainfile(filepath=str(files["blend"]), compress=False)
        game_export.export_files(scene, state["root"], work, game, None)
        budget = {"source": "data/ego_arms.json", "triangles_limit": rig["budget_triangles"], "triangles_lod0": total,
                  "device_budgets": "data/game_budget.json viewmodel (the device alone)",
                  "assembly_limit": 32000, "lods": "LOD0 only (always the same distance to the camera)"}
        document = contract_document(state, files, report, palette, budget)
        if not os.environ.get("TOOLGEN_NO_RENDER"):
            render_preview(work, state)       # after the contract: the preview poses the fingers, the contract keeps the bind pose
        for kind in ("fbx", "glb"):
            try:
                checks[f"roundtrip_{kind}"] = check_reimport(kind, files[kind], expected)
            except Exception as error:  # noqa: BLE001 - every failure belongs into the report
                traceback.print_exc()
                checks[f"roundtrip_{kind}"] = {"passed": False, "error": f"{type(error).__name__}: {error}"}
        (work / "unity_contract_arms.json").write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
        report.update({"rig": document["rig"], "triangles": total, "renderers": len(names), "wrist_bend_degrees": bend})
    except Exception as error:  # noqa: BLE001 - reported as a failed QA with exit code 1
        traceback.print_exc()
        checks["build"] = {"passed": False, "error": f"{type(error).__name__}: {error}"}
    report["checks"] = checks
    report["passed"] = bool(checks) and all(entry["passed"] for entry in checks.values())
    report["seconds"] = round(time.perf_counter() - started, 3)
    (work / "qa_arms.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    failed = [name for name, entry in checks.items() if not entry["passed"]]
    if failed:
        print(f"EGO_ARMS_FAILED: {', '.join(failed)}", flush=True)
        sys.exit(1)
    print(f"EGO_ARMS_OK: {report['triangles']} triangles, {report['renderers']} renderers, rig {report['rig']['hash'][:12]}, "
          f"wrist {report['wrist_bend_degrees']}", flush=True)


if __name__ == "__main__":
    main()
