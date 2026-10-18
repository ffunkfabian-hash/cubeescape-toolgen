"""Author the camera-local robot hands, hold pose and synchronized viewmodel motion.

Mitt proportions/semantic joints follow Robogen; this lightweight FPS assembly uses
rigid articulated nodes so FBX, glTF and the native viewer share the same animation.
No installed Robogen checkout or downloaded assets are required at generation time.
"""
import argparse
import json
import math
import os
import sys
from itertools import pairwise
from pathlib import Path

import bmesh
import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
from motion_profiles import draw_hand_offset, envelope, recoil_impulse, settle, solve_elbow
import ego_clips


def aspect_ratio(name):
    width, height = (float(value) for value in name.split(":"))
    return width / height


def horizontal_fov(vertical_degrees, aspect):
    return math.degrees(2 * math.atan(math.tan(math.radians(vertical_degrees) / 2) * aspect))


def viewmodel_camera(config, profile):
    """Fixed viewmodel field of view (vertical, like Unity's Camera.fieldOfView) and its QA range.

    The game draws hands and tool with their own camera FOV, independent of the player's
    world FOV. A tool may override the global value; the QA covers value +/- tolerance."""
    camera = config["camera"]
    reference = camera["reference_aspect"]
    assert abs(horizontal_fov(camera["vertical_fov_degrees"], aspect_ratio(reference))
               - camera["horizontal_fov_degrees"]) < .05, "viewmodels.json: horizontal FOV does not match vertical FOV"
    vertical = profile.get("vertical_fov_degrees", camera["vertical_fov_degrees"])
    qa = camera["qa"]
    tolerance = qa["fov_tolerance_degrees"]
    samples = qa["fov_samples"]
    assert samples >= 3 and 0 < vertical - tolerance and vertical + tolerance < 120
    return {"vertical_fov_degrees": vertical,
            "horizontal_fov_degrees": {name: horizontal_fov(vertical, aspect_ratio(name))
                                       for name in dict.fromkeys([reference, *qa["aspects"]])},
            "reference_aspect": reference, "near_clip_m": camera["near_clip_m"],
            "override": "vertical_fov_degrees" in profile,
            "unity": camera["unity"],
            "qa_vertical_fov_degrees": [vertical - tolerance + 2 * tolerance * i / (samples - 1) for i in range(samples)],
            "qa_aspects": qa["aspects"], "qa": qa}


def frustum_configurations(settings):
    """Tangent half extents (horizontal, vertical) for every checked FOV/aspect pair."""
    result = []
    for vertical in settings["qa_vertical_fov_degrees"]:
        for name in settings["qa_aspects"]:
            tan_v = math.tan(math.radians(vertical) / 2)
            # Only the configured FOV is binding (Unity draws the viewmodel with a fixed FOV);
            # the surrounding range is measured and reported for later tuning.
            result.append({"vertical_fov_degrees": vertical, "aspect": name,
                           "tan_h": tan_v * aspect_ratio(name), "tan_v": tan_v,
                           "binding": abs(vertical - settings["vertical_fov_degrees"]) < 1e-6})
    return result


def camera_space(points):
    """Camera at the origin looking along -Y, Z up, screen right = -X: (u, v, depth)."""
    depth = -points[:, 1]
    safe = np.where(np.abs(depth) < 1e-9, 1e-9, depth)
    return -points[:, 0] / safe, points[:, 2] / safe, depth


def screen(u, v, frustum):
    return .5 + u / (2 * frustum["tan_h"]), .5 + v / (2 * frustum["tan_v"])


def world_vertices(obj, graph):
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.data
    local = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", local)
    local = local.reshape(-1, 3)
    matrix = np.array(evaluated.matrix_world)
    return local @ matrix[:3, :3].T + matrix[:3, 3]


def empty(name, parent, matrix=None):
    obj = bpy.data.objects.new(name, None)
    parent.users_collection[0].objects.link(obj)
    obj.parent = parent
    obj.empty_display_size = .015
    if matrix is not None:
        bpy.context.view_layer.update()
        obj.matrix_world = matrix
    obj.scale = (1, 1, 1)
    return obj


def material(name, color, metallic=.1, roughness=.4, emission=0):
    mat = bpy.data.materials.new("FPS_Robot_" + name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Emission Color"].default_value = (*color, 1)
    shader.inputs["Emission Strength"].default_value = emission
    return mat


def shape(name, parent, bm, center, mat, rotation=None, smooth=False):
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if rotation:
        for vertex in bm.verts:
            vertex.co = rotation @ vertex.co
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh); bm.free(); mesh.update()
    obj = bpy.data.objects.new("SM_FPS_" + name, mesh)
    parent.users_collection[0].objects.link(obj)
    obj.parent = parent; obj.location = center
    obj["ce_role"] = "first_person_robot"
    mesh.materials.append(mat)
    if smooth:
        for polygon in mesh.polygons:
            polygon.use_smooth = True
    uv = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        major = max(range(3), key=lambda i: abs(polygon.normal[i]))
        axes = ((1, 2), (0, 2), (0, 1))[major]
        # Per-face projection with fixed meter density; triangles retain nonzero UV area.
        for index in polygon.loop_indices:
            point = mesh.vertices[mesh.loops[index].vertex_index].co
            uv.data[index].uv = (point[axes[0]] * 2 + .5, point[axes[1]] * 2 + .5)
    return obj


def box(name, parent, center, size, mat, rotation=None, bevel=.006, taper=0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    for vertex in bm.verts:
        vertex.co = Vector([vertex.co[i] * size[i] for i in range(3)])
        factor = 1 + taper * vertex.co.z / size[2]
        vertex.co.x *= factor; vertex.co.y *= factor
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, min(size) * .35), segments=2,
                   profile=.5, affect="EDGES", clamp_overlap=True)
    return shape(name, parent, bm, center, mat, rotation)


def ball(name, parent, center, radius, mat):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=radius)
    # Blender's UV-sphere operator emits the same faces in a varying order between
    # identical runs; a canonical order keeps exports and triangulation reproducible.
    bm.verts.index_update()
    order = sorted(bm.verts, key=lambda vertex: (tuple(round(value, 6) for value in vertex.co), vertex.index))
    rank = {vertex.index: position for position, vertex in enumerate(order)}
    bm.verts.sort(key=lambda vertex: rank[vertex.index])
    bm.verts.index_update(); bm.faces.index_update()
    order = sorted(bm.faces, key=lambda face: (tuple(sorted(vertex.index for vertex in face.verts)), face.index))
    rank = {face.index: position for position, face in enumerate(order)}
    bm.faces.sort(key=lambda face: rank[face.index])
    return shape(name, parent, bm, center, mat, smooth=True)


def cylinder(name, parent, center, radius, length, mat, axis=(0, 0, 1)):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=20,
                         radius1=radius, radius2=radius, depth=length)
    bmesh.ops.bevel(bm, geom=[edge for edge in bm.edges if edge.is_manifold and edge.calc_face_angle() > .7],
                   offset=min(.002, length * .15), segments=2, affect="EDGES", clamp_overlap=True)
    return shape(name, parent, bm, center, mat, Vector((0, 0, 1)).rotation_difference(Vector(axis)))


def arm(side, root, joint, wrist_local, shoulder, mats, proportions):
    """Rigid posing chain and continuous forearm, with the proximal half outside the camera."""
    width = .62
    def arm_box(name, node, center, size, mat, **options):
        center = Vector(center)
        if node != joint:
            center.x *= width; center.y *= width
        options['bevel'] = options.get('bevel', .006) * width
        return box(name, node, center, (size[0] * width, size[1] * width, size[2]), mat, **options)
    def arm_ball(name, node, center, radius, mat):
        return ball(name, node, center, radius * width, mat)
    def arm_cylinder(name, node, center, radius, length, mat, axis=(0, 0, 1)):
        center = Vector(center)
        if node != joint:
            center.x *= width; center.y *= width
        return cylinder(name, node, center, radius * width, length if axis == (0, 0, 1) else length * width, mat, axis)
    bpy.context.view_layer.update()
    assert 0 < proportions["visible_forearm_fraction"] <= .5
    upper_length = proportions["upper_length_m"]
    lower_length = proportions["forearm_length_m"]
    upper = empty("UpperArm_" + side, root)
    lower = empty("LowerArm_" + side, upper)
    # Model the entire forearm so its geometry continues beyond the screen edge.
    # Framing shows only its distal half; there is no upper-arm/elbow mesh in FPS.
    length = lower_length
    start, fraction = 0, 1
    arm_cylinder("ForearmCore_" + side, lower, (0, 0, length * (start + fraction / 2)),
                 .034, length * fraction, mats["dark"])
    center, span = start + fraction * .5, fraction * .80
    arm_box("ForearmPlate_" + side, lower, (0, 0, length * center),
            (.124, .132, length * span), mats["white"], bevel=.020, taper=-.18)
    for face in (-1, 1):
        panel = Vector((0, face * .069, length * center))
        arm_box(f"ForearmInsetGasket_{side}_{face}", lower, panel,
                (.038, .009, length * span * .77), mats["dark"], bevel=.005)
        arm_box(f"ForearmInset_{side}_{face}", lower, panel + Vector((0, face * .005, 0)),
                (.024, .005, length * span * .67), mats["orange"], bevel=.004)
        for x in (-.043, .043):
            for offset in (-span * .3, span * .3):
                arm_box(f"ForearmBolt_{side}_{face}_{x}_{offset}", lower,
                        (x, face * .067, length * (center + offset)), (.009, .006, .009), mats["dark"], bevel=.002)
    for sign in (-1, 1):
        arm_cylinder(f"ForearmServo_{side}_{sign}", lower,
                     (sign * .045, 0, length * (start + fraction * .5)),
                     .010, length * fraction, mats["grey"])
    arm_cylinder("ForearmCuff_" + side, lower, (0, 0, length * .96), .049, .025, mats["dark"])
    arm_ball("WristBall_" + side, joint, wrist_local, .046, mats["dark"])
    arm_cylinder("WristGimbal_" + side, joint, wrist_local, .044, .086, mats["grey"], (1, 0, 0))
    for sign in (-1, 1):
        arm_cylinder(f"WristCap_{side}_{sign}", joint, wrist_local + Vector((sign * .047 * width, 0, 0)),
                 .034, .012, mats["white"], (1, 0, 0))
        arm_cylinder(f"WristHub_{side}_{sign}", joint, wrist_local + Vector((sign * .055 * width, 0, 0)),
                 .015, .007, mats["orange"], (1, 0, 0))
    result = {"upper": upper, "lower": lower, "hand": joint, "wrist": wrist_local,
              "shoulder": Vector(shoulder), "lengths": (upper_length, lower_length),
              "visible_fraction": proportions["visible_forearm_fraction"],
              "pole": Vector((proportions["elbow_pole"][0] * (1 if side == "L" else -1), *proportions["elbow_pole"][1:]))}
    pose_arm(result, bake=False)
    return result


def pose_arm(rig, bake=True, frame=1):
    bpy.context.view_layer.update()
    wrist = rig["hand"].matrix_world @ rig["wrist"]
    shoulder = rig["shoulder"]
    try:
        elbow = Vector(solve_elbow(shoulder, wrist, *rig["lengths"], rig["pole"]))
    except ValueError as error:
        raise ValueError((rig["hand"].name, frame, tuple(shoulder), tuple(wrist), rig["lengths"])) from error
    for node, first, last in ((rig["upper"], shoulder, elbow), (rig["lower"], elbow, wrist)):
        node.rotation_mode = "QUATERNION"
        node.matrix_world = Matrix.LocRotScale(first, (last - first).to_track_quat("Z", "Y"), Vector((1, 1, 1)))
        node.scale = (1, 1, 1)
        bpy.context.view_layer.update()
        if bake:
            node.keyframe_insert(data_path="location", frame=frame)
            node.keyframe_insert(data_path="rotation_quaternion", frame=frame)


def aim_arm(rig, spec, sign):
    """Arm pose as data (``arm_pose`` in the Ego profile, camera frame: right = -X, forward = -Y, up = +Z): ``forearm`` is the
    direction elbow -> wrist (or ``forearm_rise_degrees`` / ``forearm_yaw_degrees`` relative to the knuckle heading),
    ``upper`` the direction elbow -> shoulder. Shoulder and elbow plane follow from the rest pose,
    so the rigid two-link chain reproduces that elbow and keeps following the hand through the clip. A spec with only
    ``max_wrist_bend_degrees`` keeps the default shoulder and elbow pole (``arm`` in data/viewmodels.json) and adds the limit."""
    rig["arm_limits"] = {"max_wrist_bend_degrees": spec["max_wrist_bend_degrees"], "palm_side": sign}
    if "forearm" not in spec and "forearm_rise_degrees" not in spec:
        return
    bpy.context.view_layer.update()
    wrist = rig["hand"].matrix_world @ rig["wrist"]
    upper, lower = rig["lengths"]
    if "forearm" in spec:
        forearm = Vector(spec["forearm"]).normalized()
    else:
        # Relative to the hand: the knuckle heading (horizontal), turned outward to the palm side by forearm_yaw_degrees
        # and rising by forearm_rise_degrees; the wrist bend is then about rise + the downward knuckle angle.
        knuckles = rig["hand"].matrix_world.to_3x3() @ Vector((0, -1, 0))
        heading = Vector((knuckles.x, knuckles.y, 0)).normalized()
        outward = (rig["hand"].matrix_world.to_3x3() @ Vector((sign, 0, 0)))
        # the elbow (behind the wrist) goes to the palm side, so the forearm heading turns towards the finger side
        turn = math.radians(spec["forearm_yaw_degrees"]) * (1 if heading.cross(Vector((-outward.x, -outward.y, 0))).z > 0 else -1)
        heading = Matrix.Rotation(turn, 3, "Z") @ heading
        rise = math.radians(spec["forearm_rise_degrees"])
        forearm = (heading * math.cos(rise) + Vector((0, 0, math.sin(rise)))).normalized()
    elbow = wrist - forearm * lower
    shoulder = elbow + Vector(spec["upper"]).normalized() * upper
    rig["shoulder"] = shoulder
    rig["pole"] = elbow - shoulder
    pose_arm(rig, bake=False)


def wrist_bend(rig):
    """Angle (degrees) between the forearm (elbow -> wrist) and the knuckle direction of the hand, and whether the elbow lies
    on the palm side, i.e. opposite the fingertips (hand-local X)."""
    hand = rig["hand"].matrix_world
    wrist = hand @ rig["wrist"]
    forearm = (wrist - rig["lower"].matrix_world.translation).normalized()
    knuckles = (hand.to_3x3() @ Vector((0, -1, 0))).normalized()
    elbow_local = hand.inverted() @ rig["lower"].matrix_world.translation
    return math.degrees(forearm.angle(knuckles)), elbow_local.x * rig["arm_limits"]["palm_side"] > 0


def link(name, parent, first, last, width, depth, mat):
    first, last = Vector(first), Vector(last)
    delta = last - first
    rotation = Vector((0, 0, 1)).rotation_difference(delta.normalized())
    return box(name, parent, (first + last) / 2, (width, depth, delta.length), mat, rotation)


GRIPPING_FINGERS = 3
FOREARM_TWITCH_LIMIT_DEGREES = 2   # ego clips: largest change of a forearm's turn per frame between neighbouring frames
                                  # (clips under 16 frames count half: their quick, smooth turns accelerate harder)
PROXIMAL_MARGIN = .01             # ego clips keep the proximal forearm half this share of the screen below the frame
# Cube Escape 0.65 enlarges the weapon viewmodels 1.35-1.7x about Socket_Hand (Resources/Toolgen/viewmodel_holds.json);
# the proximal forearm halves must leave the frame at that size as well.
GAME_ENLARGEMENT_MAX = 1.7
ADS_TOP_LIMIT = .25               # ADS target pose: model at most this share of the screen height above the centre (CE 0.72)
ADS_CENTRE_ALLOWED = ("ScopeEyeLens",)   # the only part the centre ray may meet in the ADS target pose (scope picture)
SIGHT_LINE_TOLERANCE_M = .0001   # Socket_Sight against the AimIdle line of sight (lateral and vertical)
# Finger rows along the palm's Z axis (Robogen Mitt: three fingers at a 31 mm pitch).
# Thinner links than the Mitt keep visible gaps, so each finger reads at FPS distance.
GRIP_ROWS = (.029, 0, -.029)
# Archery hook: one finger above the arrow, two below (Mediterranean draw).
PINCH_ROWS = (.027, -.013, -.042)
FINGER_WIDTH, FINGER_DEPTH = .020, .021


def hand(side, parent, pose, shoulder, radius, mats, proportions, pinch=False):
    """Three gripping fingers and one opposing thumb, like Robogen's Mitt; centered wrist."""
    sign = 1 if side == "L" else -1
    joint = empty("Hand_" + side, parent, pose)
    joint["robogen_joint"] = "Hand_" + side
    joint["robogen_prop"] = "Prop_" + side
    rx, ry = radius
    palm = Vector((sign * (rx + .029), .014, -.005))
    box("Palm_" + side, joint, palm, (.050, .100, .094), mats["grey"], bevel=.018)
    box("HandArmor_" + side, joint, palm + Vector((sign * .028, .010, .005)),
        (.014, .084, .085), mats["white"], bevel=.008)
    # The concept's white back plate faces the camera, with an inset orange panel
    # and exposed dark seams instead of a solid grey mitten silhouette.
    back = palm + Vector((0, .054, .004))
    box("BackhandGasket_" + side, joint, back, (.055, .014, .084), mats["dark"], bevel=.010)
    box("BackhandArmor_" + side, joint, back + Vector((0, .007, 0)),
        (.051, .014, .078), mats["white"], bevel=.011, taper=.12)
    box("BackhandInset_" + side, joint, back + Vector((-sign * .011, .015, .002)),
        (.014, .003, .052), mats["orange"], bevel=.003)
    for x in (-.016, .016):
        for z in (-.032, .032):
            bolt = back + Vector((x, .015, z))
            box(f"BackhandBolt_{side}_{x}_{z}", joint, bolt, (.007, .004, .007), mats["dark"], bevel=.002)
            box(f"BackhandBoltSlot_{side}_{x}_{z}", joint, bolt + Vector((0, .0023, 0)),
                (.004, .001, .0015), mats["grey"], bevel=.0003)
    fingers = []
    for index, height in enumerate(PINCH_ROWS if pinch else GRIP_ROWS):
        finger = empty(f"Fingers_{side}_{index}", joint)
        finger.location = (0, 0, height)
        points = [(sign * (rx + .032), -.027, 0), (sign * (rx + .011), -(ry + .021), 0),
                  (-sign * (rx - .004), -(ry + .021), 0), (-sign * (rx + .009), -.012, 0)]
        if pinch:
            # A shallow archery hook contacts the string on its forward face;
            # it must not reuse the deep wrap of a cylindrical tool grip.
            points = [(sign * (rx + .032), -.015, 0), (sign * (rx + .006), -.010, 0),
                      (-sign * (rx - .004), -.010, 0), (-sign * rx, .004, 0)]
        hinge = Vector(points[0])
        finger.location = hinge + Vector((0, 0, height))
        points = [Vector(point) - hinge for point in points]
        for segment, (a, b) in enumerate(pairwise(points)):
            link(f"Finger_{side}_{index}_{segment}", finger, a, b, FINGER_WIDTH, FINGER_DEPTH, mats["dark"])
        box(f"KnuckleArmor_{side}_{index}", finger, Vector(points[0]) + Vector((sign * .009, .002, 0)),
            (.013, .025, FINGER_WIDTH + .001), mats["white"], bevel=.004)
        fingers.append(finger)
    thumb = empty("Thumb_" + side, joint)
    link("ThumbBase_" + side, thumb, (sign * (rx + .033), .034, .043),
         (sign * .014, ry + .016, .046), .030, .030, mats["grey"])
    link("ThumbTip_" + side, thumb, (sign * .014, ry + .016, .046),
         (-sign * (rx - .007), .020, .040), .025, .027, mats["dark"])
    hand_scale = proportions["hand_scale"]
    for obj in joint.children_recursive:
        obj.location *= hand_scale
        if obj.type == 'MESH':
            obj.data.transform(Matrix.Scale(hand_scale, 4))
    wrist_local = (palm + Vector(proportions["wrist_offset_m"])) * hand_scale
    rig = arm(side, parent.parent, joint, wrist_local, shoulder, mats, proportions)
    contact = empty("GripContact_" + side, joint)
    contact["ce_role"] = "hand_contact"
    # Wrist point for the game's own wrist check (Cube Escape 0.65): angle between LowerArm origin (elbow) -> Wrist_<side>
    # and the knuckle direction, local -Y of Hand_<side>; the same measure as wrist_bend in qa_viewmodel.json.
    wrist = empty("Wrist_" + side, joint)
    wrist.location = wrist_local
    wrist["ce_role"] = "wrist"
    wrist["ce_knuckle_axis"] = "-Y of Hand_" + side
    return joint, fingers, contact, rig


def matrix_rows(obj):
    return [list(row) for row in obj.matrix_world]


def bounds(obj, graph):
    evaluated = obj.evaluated_get(graph)
    points = [evaluated.matrix_world @ vertex.co for vertex in evaluated.data.vertices]
    return [[min(v[i] for v in points) for i in range(3)], [max(v[i] for v in points) for i in range(3)]]


def finish_keys(obj):
    if not obj.animation_data or not obj.animation_data.action:
        return
    action = obj.animation_data.action
    action.use_frame_range = True; action.frame_start = 1; action.frame_end = 97
    action.use_cyclic = False
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = "LINEAR"


def curves_of(owner):
    action = owner.animation_data.action if owner and owner.animation_data else None
    if action is None:
        return []
    return [curve for layer in action.layers for strip in layer.strips for bag in strip.channelbags for curve in bag.fcurves]


def clip_keys(owner, clips, fire_start, fire_scale=1.0, rest_frame=97):
    """Keys of parts the ego clips do not pose themselves (weapon mechanics, glows, shape keys): Fire and AimFire replay
    the Use clip from ``fire_start``, time-compressed by ``fire_scale`` like the recoil (slides, bolts and coils cycle
    with every shot), every other clip holds the rest
    value at both ends, so nothing drifts between clips (glTF also drops curves without keys in the clips' range)."""
    for curve in curves_of(owner):
        rest = curve.evaluate(rest_frame)
        for clip in clips:
            start, end = clip["frame_start"], clip["frame_end"]
            if any(start <= key.co.x <= end for key in curve.keyframe_points):
                continue                       # posed by first_person.py itself (rig, support hand, reload part)
            # a part away from rest at the shot belongs to the charge (fusion fins, coil): it rests through Fire
            if clip["motion"] in ("fire", "aim_fire") and abs(curve.evaluate(fire_start) - rest) < 1e-6:
                values = [(start + offset, curve.evaluate(fire_start + offset * fire_scale)) for offset in range(clip["length"] + 1)]
            else:
                values = [(start, rest), (end, rest)]
            for frame, value in values:
                curve.keyframe_points.insert(frame, value, options={"FAST"}).interpolation = "LINEAR"
        curve.update()


def exports(directory, root, clip):
    objects = {root, *root.children_recursive}
    for obj in bpy.context.scene.objects:
        obj.select_set(obj in objects)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(filepath=str(directory / (root.name + ".glb")), export_format="GLB", use_selection=True,
        export_yup=True, export_extras=True, export_animations=True, export_morph=True,
        export_animation_mode="ACTIVE_ACTIONS", export_merge_animation="ACTION",
        export_nla_strips_merged_animation_name=clip, export_frame_range=True,
        export_force_sampling=True, export_cameras=False, export_lights=False)
    bpy.ops.export_scene.fbx(filepath=str(directory / (root.name + ".fbx")), use_selection=True,
        object_types={"EMPTY", "MESH"}, axis_forward="-Z", axis_up="Y", global_scale=1,
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", bake_space_transform=False,
        use_mesh_modifiers=False, use_custom_props=True, bake_anim=True,
        bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True, bake_anim_step=1, bake_anim_simplify_factor=0, add_leaf_bones=False)


def build(directory, spec, profile):
    tool = spec["id"]; name = spec["asset"] + "_FPS"
    source = directory / (name + ".blend")
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene; scene.frame_set(1); bpy.context.view_layer.update()
    root = scene.objects[name]; socket = scene.objects["Socket_Hand"]
    tool_scale = profile.get('tool_scale', 1)
    if tool_scale != 1:
        for obj in root.children_recursive:
            obj.location *= tool_scale
            if obj.type == 'MESH':
                obj.data.transform(Matrix.Scale(tool_scale, 4), shape_keys=True)
            if obj.animation_data and obj.animation_data.action:
                for layer in obj.animation_data.action.layers:
                    for strip in layer.strips:
                        for bag in strip.channelbags:
                            for curve in bag.fcurves:
                                if curve.data_path == 'location':
                                    for key in curve.keyframe_points:
                                        key.co.y *= tool_scale
                                        key.handle_left.y *= tool_scale; key.handle_right.y *= tool_scale
        scene.frame_set(1); bpy.context.view_layer.update()
    config = json.loads((ROOT / "data/viewmodels.json").read_text())
    settings = viewmodel_camera(config, profile)
    configure_camera(scene, settings)
    original = socket.matrix_world.copy()
    local_muzzle = original.inverted() @ scene.objects["Socket_Muzzle"].matrix_world.translation
    # The muzzle aims at the reticle unless a tool turns its head into view (aim_target_m).
    position = Vector(profile["hand"]); target = Vector(profile.get("aim_target_m", (0, -4, 0)))
    rotation = (target - position).to_track_quat("-Y", "Z") @ Quaternion((0, -1, 0), math.radians(profile["roll_degrees"]))
    # Solve the actual muzzle ray including the rolled bore offset.
    for _ in range(12):
        ray = rotation @ Vector((0, -1, 0))
        desired = (target - position - rotation @ local_muzzle).normalized()
        rotation = ray.rotation_difference(desired) @ rotation
    pose = Matrix.LocRotScale(position, rotation, Vector((1, 1, 1)))
    delta = pose @ original.inverted()
    moving = [obj for obj in root.children if obj.name != "Socket_Camera"]
    # Preserve local animation curves by inserting one static hold transform.
    hold = empty("Viewmodel_Hold", root, delta)
    for obj in moving:
        obj.parent = hold
    bpy.context.view_layer.update()
    motion = empty("Viewmodel_Motion", root)
    hold.parent = motion
    mats = {"white": material("White", (.66, .685, .72), .28, .32),
            "grey": material("Grey", (.20, .23, .27), .25, .46),
            "dark": material("Dark", (.035, .045, .055), .3, .42),
            "cyan": material("Cyan", (.01, .55, .80), .1, .3, .6),
            "orange": material("Orange", (.95, .24, .035), .18, .34)}
    hands = []; arms = []; contact_targets = {}
    grip_side = "L" if tool == "bow" else "R"
    proportions = config["arm"]
    # Fixed shoulder anchors; a tool held at a different reach may override them as data.
    shoulders = profile.get("shoulders", proportions["shoulders"])
    twists = {side: Euler(tuple(math.radians(value) for value in profile.get("hand_rotation_degrees", {}).get(side, (0, 0, 0))), "XYZ").to_matrix().to_4x4() for side in ("L", "R")}
    main, _, contact, rig = hand(grip_side, motion, socket.matrix_world @ twists[grip_side], shoulders[grip_side], [r * tool_scale / proportions["hand_scale"] for r in profile["grip_radius"]], mats, proportions)
    hands.append(main); arms.append(rig); contact_targets[contact.name] = "Socket_Hand"
    arm_pose = profile.get("arm_pose", {})
    if grip_side in arm_pose:
        aim_arm(rig, arm_pose[grip_side], 1 if grip_side == "L" else -1)
    if tool == "bow":
        nock = scene.objects["Socket_Nock"]
        draw_pose = nock.matrix_world @ twists["R"]
        draw, fingers, draw_contact, rig = hand("R", motion, draw_pose, shoulders["R"], (.012, .015), mats, proportions, pinch=True)
        hands.append(draw); arms.append(rig); contact_targets[draw_contact.name] = "Socket_Nock"
    elif profile["support"]:
        support_radius = (.086, .085)
        if profile.get("support_socket"):
            # The support hand closes around the handguard at the tool's own anchor (cross-section half extents
            # support_radius: height, width), so it grips the tool in every pose instead of hovering near it.
            anchor = scene.objects[profile["support_socket"]].matrix_world.translation
            support_pose = Matrix.LocRotScale(anchor, rotation, Vector((1, 1, 1)))
            support_radius = [r * tool_scale / proportions["hand_scale"] for r in profile["support_radius"]]
        else:
            support_pose = pose @ Matrix.Translation(profile["support_offset"])
        # Turning the support hand about the barrel keeps its fingers off the tool head.
        support_pose = support_pose @ Matrix.Rotation(math.radians(profile.get("support_roll_degrees", 0)), 4, "Y")
        if profile.get("support_grip") == "cup":
            # Two-handed pistol (cup grip, 0.10.0): the left hand is oriented like the grip hand (fingers forward, palm on
            # the left of the grip) and wraps the right hand's fingers from below left (support_radius beyond them).
            support_pose = support_pose @ twists["L"]
        elif profile.get("support_grip") == "underhand":
            # Relaxed underhand support (weapons): palm under the handguard, index finger forward (-Y), thumb on the
            # camera side (+X), fingers curling up the far side; the wrist lies on the camera side, so the forearm
            # comes in from the left shoulder without crossing under the tool.
            support_pose = support_pose @ Matrix(((0, 1, 0, 0), (0, 0, -1, 0), (-1, 0, 0, 0), (0, 0, 0, 1)))
        else:
            support_pose = support_pose @ Matrix(((0, -1, 0, 0), (0, 0, 1, 0), (-1, 0, 0, 0), (0, 0, 0, 1)))
        support, _, support_contact, rig = hand("L", motion, support_pose, shoulders["L"], support_radius, mats, proportions)
        hands.append(support); arms.append(rig)
        if "L" in arm_pose:
            aim_arm(rig, arm_pose["L"], 1)
        if profile.get("support_socket"):
            contact_targets[support_contact.name] = profile["support_socket"]
    rest = {obj: obj.matrix_world.copy() for obj in hands}
    scene.render.fps = 24; scene.frame_start = 1; scene.frame_end = 97
    # Ego clips (data/ego_clips.json) follow the Use clip on the same timeline; the scene range stays the Use clip.
    clips, clip_params = ego_clips.clip_list(ego_clips.load(), spec, profile.get("motion"))
    aim = ads_setup(scene, root, hold, clip_params) if any(clip["motion"].startswith("aim") for clip in clips) else None
    support_hand = next((obj for obj in hands if obj.name == "Hand_L"), None) if tool != "bow" and profile["support"] else None
    support_rest = support_hand.location.copy() if support_hand else None
    part_name = clip_params.get("reload", {}).get("part") if any(clip["motion"] == "reload" for clip in clips) else None
    part = scene.objects.get(part_name) if part_name else None
    part_rest = part.location.copy() if part is not None else None
    base_shoulders = [rig["shoulder"].copy() for rig in arms]
    base_poles = [rig["pole"].copy() for rig in arms]
    scene.frame_set(1); bpy.context.view_layer.update()
    # Wrist target of the ego clips (data/ego_clips.json "wrist"): 45 degrees, or the rest bend plus an allowance when that
    # is larger, always below the arm_pose limit (55) less a margin.
    wrist = ego_clips.load()["wrist"]
    rest_arms = [rest_arm(rig) for rig in arms]
    grip_forearm = (arms[0]["hand"].matrix_world @ arms[0]["wrist"], rest_arms[0][0])
    arm_view = {"tan_v": math.tan(math.radians(settings["vertical_fov_degrees"]) / 2), "near": settings["near_clip_m"],
                "pivot": socket.matrix_world.translation.copy() if tool != "bow" else None}
    arm_view["rest_top"] = {rig["hand"].name: proximal_top(rig, rig["hand"].matrix_world @ rig["wrist"] - forearm * rig["lengths"][1],
                                                           forearm, arm_view) for rig, (forearm, _) in zip(arms, rest_arms)}
    # Arms without arm_pose (the bow) have no wrist limit; their clips only keep the rest bend plus the allowance.
    bend_targets = {rig["hand"].name: min(rig["arm_limits"]["max_wrist_bend_degrees"] - wrist["limit_margin_degrees"]
                                          if "arm_limits" in rig else 180.0,
                                          max(wrist["target_degrees"], arm_bend(rig, rig["shoulder"], rig["pole"])
                                              + wrist["rest_allowance_degrees"]))
                    for rig in arms}
    def place(ego, frame, previous):
        """Pose of an ego clip frame on Viewmodel_Motion, the support hand and the reload part (not keyed)."""
        values = ego_clips.pose_at(ego, frame, clip_params)
        location, rotation, _ = clip_matrix(values, aim and aim["matrix"], Vector(profile["hand"]), grip_forearm).decompose()
        motion.location = location
        motion.rotation_euler = rotation.to_euler("XYZ", previous)
        bpy.context.view_layer.update()
        if support_hand is not None:
            offset = values["support"]
            support_hand.location = support_rest + (motion.matrix_world.to_quaternion().inverted() @ Vector(
                (-offset["right"], offset["back"], offset["up"])) if offset else Vector())
        if part is not None:
            offset = values["part"]
            part.location = part_rest + (Vector((-offset["right"], offset["back"], offset["up"])) if offset else Vector())
        bpy.context.view_layer.update()
        return values

    def natural_arms(ego, values):
        """Relaxed forearm directions of the posed frame; the support arm is left out while it may show (aiming)."""
        turn = Quaternion().slerp(motion.matrix_world.to_quaternion(), values["follow"])
        view = dict(arm_view, pivot=socket.matrix_world.translation.copy() if tool != "bow" else None)
        result = {}
        for rig, rest_pose in zip(arms, rest_arms):
            forearm, data = relaxed_forearm(rig, rest_pose, turn, bend_targets[rig["hand"].name])
            data["view"] = view
            data["free"] = bool(ego["support_forearm_visible"] and rig["hand"] is support_hand)
            result[rig["hand"].name] = (forearm, data)
        return result

    # Framing plan of the forearms: one pass over every ego clip frame, then one correction axis per arm (plan_corrections).
    samples = {rig["hand"].name: {} for rig in arms}
    previous = Euler((0, 0, 0), "XYZ")
    for ego in clips:
        for frame in range(ego["frame_start"], ego["frame_end"] + 1):
            scene.frame_set(frame)
            values = place(ego, frame, previous)
            previous = motion.rotation_euler.copy()
            for name, (forearm, data) in natural_arms(ego, values).items():
                if not data["free"]:
                    samples[name][frame] = (forearm, data)
    plans = {rig["hand"].name: plan_corrections(rig, samples[rig["hand"].name], clips,
                                                max(-PROXIMAL_MARGIN, arm_view["rest_top"][rig["hand"].name] + .003))
             for rig in arms}
    frames = [*range(1, 98), *(frame for clip in clips for frame in range(clip["frame_start"], clip["frame_end"] + 1))]
    clip_records = {clip["name"]: {"wrist_bend_max_degrees": {}, "aim_max": 0.0} for clip in clips}
    detached_frames, reticle_exempt, aim_frames, support_visible_frames = set(), set(), set(), set()
    previous_euler = Euler((0, 0, 0), "XYZ")
    clip = spec.get("fps_clip") or spec["clip"]
    root["ce_action_clip"] = clip; root["ce_autoplay"] = False; root["ce_loop"] = False
    # Event of a tool's Use clip (use_event in data/viewmodels.json: Fire, Grab, Switch), a timeline marker like the weapons'
    # Fire; the game export writes the markers of this scene into the contract's Use clip events.
    event = profile.get("use_event")
    if event:
        for marker in [marker for marker in scene.timeline_markers if marker.name == event["name"]]:
            scene.timeline_markers.remove(marker)
        scene.timeline_markers.new(event["name"], frame=event["frame"])
    # Every clip of the model (T3): the Use clip, then the ego clips in timeline order (JSON list; ce_action_clip stays).
    root["ce_action_clips"] = json.dumps([clip, *(entry["name"] for entry in clips)])
    # Finger nodes (T5): the grip hand's index finger lifts off the trigger after the shot (Fire, AimFire), the support
    # fingers open and close while the support hand lets go in Reload. Opening turns about the finger's hinge (local Z),
    # the same direction as the bow's draw fingers open; the rest pose stays unchanged (zero at every clip end).
    finger_params = clip_params.get("fingers", {})
    finger_nodes = []
    if profile.get("motion") and tool != "bow" and clips:
        finger_nodes.append((scene.objects[f"Fingers_{grip_side}_0"], "trigger", -1 if grip_side == "R" else 1))
        if support_hand is not None and clip_params.get("reload", {}).get("support"):
            finger_nodes += [(scene.objects[f"Fingers_L_{index}"], "regrip", 1) for index in range(GRIPPING_FINGERS)]
    finger_rest = {obj.name: obj.rotation_euler.z for obj, _, _ in finger_nodes}
    spin = clip_params.get("charge", {}).get("spin") if any(entry["motion"] == "charge" for entry in clips) else None
    spin_node = scene.objects[spin["node"]] if spin else None
    root["ce_hand_style"] = "Robogen Mitt / articulated FPS, three fingers and thumb"
    # Exported as glTF extras / FBX user properties so the game can adopt the viewmodel camera.
    root["ce_viewmodel_vertical_fov_degrees"] = settings["vertical_fov_degrees"]
    root["ce_viewmodel_horizontal_fov_degrees"] = settings["horizontal_fov_degrees"][settings["reference_aspect"]]
    root["ce_viewmodel_reference_aspect"] = settings["reference_aspect"]
    root["ce_viewmodel_near_clip_m"] = settings["near_clip_m"]
    for frame in frames:
        scene.frame_set(frame)
        ego = ego_clips.clip_at(clips, frame) if frame > 97 else None
        motion.location = (0, 0, 0); motion.rotation_euler = (0, 0, 0)
        for rig, shoulder, pole in zip(arms, base_shoulders, base_poles):
            rig["shoulder"], rig["pole"] = shoulder.copy(), pole.copy()
        if ego:
            values = place(ego, frame, previous_euler)
            previous_euler = motion.rotation_euler.copy()
            if not ego["reticle_free"]:
                reticle_exempt.add(frame)
            if ego["support_forearm_visible"]:
                support_visible_frames.add(frame)
            if values["aim"] > 0:
                aim_frames.add(frame)
            clip_records[ego["name"]]["aim_max"] = max(clip_records[ego["name"]]["aim_max"], values["aim"])
        elif tool == "bow":
            tension = envelope(frame, ((1, 0), (31, 1), (43, 1), (49, 0), (97, 0)))
            kick = settle(frame, 43, 22, 1)
            # Rotate the bow and its grip hand together about the grip, rather
            # than treating the camera origin as their pivot.
            rotation = Euler((math.radians(3) * kick,
                              math.radians(profile["draw_roll_degrees"]) * tension + math.radians(2) * kick,
                              math.radians(1.3) * kick), "XYZ")
            pivot = Vector(profile["hand"])
            shift = Vector((-.012 * tension, -.035 * tension + .025 * kick, .008 * tension - .004 * kick))
            motion.rotation_euler = rotation
            motion.location = pivot + shift - rotation.to_matrix() @ pivot
        elif profile.get("motion"):
            # Weapon: recoil impulse about the hand (back toward the player, muzzle up), then settling to rest.
            motion.rotation_euler, motion.location = recoil_pose(profile["motion"], frame, Vector(profile["hand"]))
        else:
            pressure = envelope(frame, ((1, 0), (14, 1), (45, 1), (73, 0), (97, 0)))
            kick = settle(frame, 14, 28, 1)
            motion.location = (0, -.012 * pressure + .010 * kick, .016 * pressure)
            motion.rotation_euler = (math.radians(1.5) * pressure, math.radians(.9) * kick, 0)
        motion.keyframe_insert(data_path="location", frame=frame)
        motion.keyframe_insert(data_path="rotation_euler", frame=frame)
        bpy.context.view_layer.update()
        if support_hand is not None:
            if not ego:
                support_hand.location = support_rest
            support_hand.keyframe_insert(data_path="location", frame=frame)
            if ego and values["detached"]:
                detached_frames.add(frame)
        if part is not None:
            if not ego:
                part.location = part_rest
            part.keyframe_insert(data_path="location", frame=frame)
        for finger, kind, sign in finger_nodes:
            amount = values[kind] if ego else 0.0
            finger.rotation_euler.z = finger_rest[finger.name] - sign * math.radians(finger_params[kind + "_deg"] * amount)
            finger.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)
        if spin_node is not None and ego and ego["motion"] == "charge":
            # one turn of the coil per Charge loop (rest 0 of the Use clip; a full turn is the rest matrix again)
            spin_node.rotation_euler[spin["axis"]] = math.radians(spin["degrees"] * values["spin"])
            spin_node.keyframe_insert(data_path="rotation_euler", index=spin["axis"], frame=frame)
        if ego:
            natural = natural_arms(ego, values)
            for rig in arms:
                forearm, data = natural[rig["hand"].name]
                index, angles = plans[rig["hand"].name]
                if not data["free"] and angles.get(frame):
                    forearm = corrected(forearm, index, angles[frame])
                elbow = data["wrist"] - forearm * rig["lengths"][1]
                rig["shoulder"] = elbow + data["upper"]
                rig["pole"] = elbow - rig["shoulder"]
                record = clip_records[ego["name"]]
                record["forearm_turn_max_degrees"] = max(record.get("forearm_turn_max_degrees", 0.0),
                                                         round(math.degrees(data["rest"].angle(forearm)), 2))
        bpy.context.view_layer.update()
        if tool == "bow" and ego:
            draw.matrix_world = nock.matrix_world @ twists["R"]
            draw.keyframe_insert(data_path="location", frame=frame)
            draw.keyframe_insert(data_path="rotation_euler", frame=frame)
        elif tool == "bow":
            offset = Vector(draw_hand_offset(frame))
            # Nock is evaluated after weapon motion; convert back into the common rig space.
            draw.matrix_world = nock.matrix_world @ twists["R"]
            draw.location += motion.matrix_world.to_quaternion().inverted() @ offset
            draw.keyframe_insert(data_path="location", frame=frame)
            draw.keyframe_insert(data_path="rotation_euler", frame=frame)
            opening = envelope(frame, ((1, 0), (43, 0), (47, .7), (66, .7), (79, 0), (97, 0)))
            for index, finger in enumerate(fingers):
                finger.rotation_euler.z = opening * (1 - index * .12)
                finger.keyframe_insert(data_path="rotation_euler", frame=frame)
        for rig in arms:
            pose_arm(rig, frame=frame)
            if "arm_limits" in rig:
                bend, palm_side = wrist_bend(rig)
                record = rig.setdefault("bend", {"max_degrees": 0.0, "elbow_on_palm_side": True})
                record["max_degrees"] = max(record["max_degrees"], round(bend, 2))
                record["elbow_on_palm_side"] = record["elbow_on_palm_side"] and palm_side
                if ego:
                    per_clip = clip_records[ego["name"]]["wrist_bend_max_degrees"]
                    per_clip[rig["hand"].name] = max(per_clip.get(rig["hand"].name, 0.0), round(bend, 2))
                    if not palm_side:
                        clip_records[ego["name"]]["elbow_off_palm_side"] = True
    for rig, shoulder, pole in zip(arms, base_shoulders, base_poles):
        rig["shoulder"], rig["pole"] = shoulder, pole
    if spin_node is not None:                  # the Charge keys interpolate linearly; the Use clip's keys stay as they are
        for curve in curves_of(spin_node):
            for key in curve.keyframe_points:
                if key.co.x > 97:
                    key.interpolation = "LINEAR"
    if clips:
        owners = [root, *root.children_recursive, *(obj.data.shape_keys for obj in root.children_recursive
                                                    if obj.type == "MESH" and obj.data.shape_keys)]
        for owner in owners:
            clip_keys(owner, clips, clip_params.get("fire_start", 1), clip_params.get("fire_scale", 1.0))
    for obj in [motion, *hands, *(node for rig in arms for node in (rig["upper"], rig["lower"])), *(obj for obj in root.children_recursive if obj.name.startswith("Fingers_")), *([part] if part is not None else [])]:
        finish_keys(obj)
    scene.frame_set(1); bpy.context.view_layer.update()
    # Grip hand remains rigidly attached to the tool throughout the clip.
    assert (main.matrix_world.translation - socket.matrix_world.translation).length < 1e-5
    clip_check = {"clips": clips, "params": clip_params, "frames": frames, "detached": detached_frames,
                  "support_forearm_visible": support_visible_frames,
                  "support_hand": support_hand.name if support_hand else None,
                  "reticle_exempt": reticle_exempt, "support_contact": support_hand and next(
                      (name for name, target in contact_targets.items() if target == profile.get("support_socket")), None)}
    report = validate(scene, root, contact_targets, tool, arms, settings, profile.get("head"), profile.get("touch_tolerance_m"),
                      clip_check)
    if os.environ.get("TOOLGEN_FPS_DEBUG"):
        bpy.ops.wm.save_as_mainfile(filepath=os.environ["TOOLGEN_FPS_DEBUG"], copy=True)
    report["ego_clips"] = ego_clip_report(scene, root, clips, clip_records, aim, aim_frames, settings, part_name, part)
    # T6 (Cube Escape 0.72 Sightline): Socket_Sight on the AimIdle line, hand touch in every clip frame, ADS target pose.
    sight_line = sight_socket_check(scene, hold, aim)
    report["ego_clips"]["sight_socket"] = sight_line
    if sight_line and not sight_line["ok"]:
        report["ego_clips"]["failures"].append(f"Socket_Sight off the AimIdle line of sight ({sight_line})")
    touch_limit = profile.get("touch_tolerance_m")
    if clips and touch_limit is not None:
        touch = clip_hand_touch(scene, root, arms, clips, detached_frames, support_hand.name if support_hand else None)
        for entry in report["ego_clips"]["clips"]:
            entry["hand_touch_max_m"] = touch[entry["name"]]
            report["ego_clips"]["failures"].extend(
                f"{entry['name']}: {name} leaves the tool (nearest {value['m'] * 1000:.1f} mm at frame {value['frame']}, "
                f"limit {touch_limit * 1000:.0f} mm)" for name, value in touch[entry["name"]].items() if value["m"] > touch_limit)
        report["ego_clips"]["hand_touch_limit_m"] = touch_limit
    report["ads_target"] = None
    if spec.get("hold") and scene.objects.get("Socket_Sight") is not None:
        report["ads_target"] = ads_target_report(scene, root, arms, settings, spec["hold"]["eye_distance_m"],
                                                 support_hand.name if support_hand else None)
        print("ADS_TARGET", tool, json.dumps({key: report["ads_target"][key] for key in
                                              ("eye_distance_m", "passed", "eye_distance_range_m", "centre_hit",
                                               "model_top_above_centre", "failures")}), flush=True)
    root["toolgen_ego_clips"] = json.dumps({"timeline_start": clips[0]["frame_start"] if clips else None,
                                            "timeline_end": ego_clips.timeline_end(clips),
                                            "reload_part": part.name if part is not None else None,
                                            "clips": clips})
    print("EGO_CLIP_WRIST", tool, json.dumps({clip["name"]: clip["wrist_bend_max_degrees"] for clip in report["ego_clips"]["clips"]}),
          flush=True)
    failures = report["ego_clips"]["failures"]
    assert not failures, (tool, "ego clips", failures)
    report["robogen_reference"] = config["reference"]
    report["clip"] = clip; report["hand_sides"] = [obj.name for obj in hands]
    # Relaxed wrists (Cube Escape 0.65 finding: forearm straight under the grip, wrist bent ~105 deg / folded ~160 deg).
    report["wrist_bend"] = {rig["hand"].name: dict(rig["bend"], limit_degrees=rig["arm_limits"]["max_wrist_bend_degrees"])
                            for rig in arms if "bend" in rig}
    bent = [f"{name}: wrist bent {value['max_degrees']:.1f} deg (limit {value['limit_degrees']}), elbow on the palm side "
            f"{value['elbow_on_palm_side']}"
            for name, value in report["wrist_bend"].items()
            if value["max_degrees"] > value["limit_degrees"] or not value["elbow_on_palm_side"]]
    print("WRIST_BEND", tool, json.dumps({name: value["max_degrees"] for name, value in report["wrist_bend"].items()}), flush=True)
    assert not bent, (tool, bent)
    for obj, matrix in rest.items():
        assert max(abs(obj.matrix_world[i][j] - matrix[i][j]) for i in range(4) for j in range(4)) < 1e-5, obj.name
    (directory / "qa_viewmodel.json").write_text(json.dumps(report, indent=2) + "\n")
    assert report["passed"], (tool, "viewmodel framing", report["failures"])
    (directory / "viewmodel_camera.json").write_text(json.dumps(camera_document(tool, settings, report), indent=2) + "\n")
    refresh_geometry(directory, root, profile, report, settings)
    refresh_motion(directory, scene)
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    exports(directory, root, clip)
    if not os.environ.get("TOOLGEN_NO_RENDER"):
        scene.render.filepath = str(directory / "preview_first_person.png")
        bpy.ops.render.render(write_still=True)
        hero = next(obj for obj in scene.objects if obj.type == "CAMERA" and obj != scene.camera)
        low, high = (Vector(value) for value in json.loads((directory / "qa_geometry_fps.json").read_text())["bounds_m"])
        center = (low + high) / 2
        span = max(high - low)
        hero.location = center + Vector((span, -span, span * .6))
        hero.rotation_euler = (center - hero.location).to_track_quat("-Z", "Y").to_euler()
        hero.data.type = "ORTHO"; hero.data.ortho_scale = span * 1.4
        for obj in scene.objects:
            if "Preview_" in obj.name:
                obj.hide_render = True
        scene.camera = hero
        scene.render.resolution_x = 1400; scene.render.resolution_y = 1000
        scene.render.filepath = str(directory / "preview_large.png")
        bpy.ops.render.render(write_still=True)
    summary = report["framing_range"]["summary"]
    print(f"VIEWMODEL_OK {tool}: {len(hands)} hands, {report['frames_checked']} frames ({len(clips)} ego clips), contact={report['max_contact_error_m']:.8f} m, "
          f"FOV {settings['vertical_fov_degrees']:.2f} deg vertical, {summary['binding_configurations']} binding framings, "
          f"range {summary['range_ok']}/{summary['range_checked']} ok, hand margin {summary['min_hand_margin']:.4f}, head {json.dumps(report['head'])}")


def recoil_pose(config, frame, pivot):
    """Euler rotation and location of Viewmodel_Motion for a weapon shot: ``fire_frame`` (impulse), ``kick_m`` (travel
    toward the player), ``pitch_degrees`` (muzzle up), ``recovery_frames``; optional ``charge_m`` pulls the weapon back
    slowly before the shot (charged weapons). Rotation about the hand; zero before the charge and after the recovery."""
    fire, recovery = config["fire_frame"], config["recovery_frames"]
    impulse = recoil_impulse(frame, fire, recovery)
    charge = envelope(frame, ((1, 0), (fire - 2, 1), (fire - 1, 0))) * config.get("charge_m", 0) if config.get("charge_m") else 0
    rotation = Euler((-math.radians(config["pitch_degrees"]) * impulse, math.radians(config.get("yaw_degrees", 0)) * impulse, 0), "XYZ")
    shift = Vector((0, config["kick_m"] * impulse + charge, .004 * impulse))
    return rotation, pivot + shift - rotation.to_matrix() @ pivot


def ads_setup(scene, root, hold, params):
    """Aim-down-sights transform of Viewmodel_Motion (ego clip pose ``aim`` = 1): the tool's forward axis along the view
    without roll, and its line of sight on the camera axis at ``ads.eye_distance_m``. The line of sight runs
    ``eye_above_m`` over the top of the sight parts (``ads.sight_mode`` "top", iron sights) or through their centre
    ("center", optics); sight parts are ``ads.sight_parts`` (mesh names without SM_PG_) or every mesh whose name contains
    one of ``ads.sight_markers``. Without sight parts the line runs over the highest point of the tool."""
    block = params["ads"]
    scene.frame_set(1); bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    tool_meshes = [obj for obj in hold.children_recursive if obj.type == "MESH"]
    if block.get("sight_parts"):
        parts = [obj for obj in tool_meshes if obj.name.removeprefix("SM_PG_") in block["sight_parts"]]
        assert len(parts) == len(block["sight_parts"]), ("ads.sight_parts not found", block["sight_parts"])
    else:
        parts = [obj for obj in tool_meshes if any(marker in obj.name for marker in block["sight_markers"])]
    inverse = hold.matrix_world.inverted()
    def local_points(objects):
        return np.concatenate([world_vertices(obj, graph) @ np.array(inverse)[:3, :3].T + np.array(inverse)[:3, 3]
                               for obj in objects])
    mode = block.get("sight_mode", "top")
    if parts:
        points = local_points(parts)
        low, high = points.min(axis=0), points.max(axis=0)
        sight = Vector(((low[0] + high[0]) / 2, (low[1] + high[1]) / 2, high[2] if mode == "top" else (low[2] + high[2]) / 2))
    else:
        mode = "top"
        points = local_points(tool_meshes)
        sight = Vector((0, float(points[:, 1].mean()), float(points[:, 2].max())))
    eye = sight + Vector((0, 0, block["eye_above_m"] if mode == "top" else 0))
    rotation = hold.matrix_world.to_quaternion().inverted()
    world_eye = rotation.to_matrix() @ (hold.matrix_world @ eye)
    # Default distance: the sight's own depth at rest less pull_back_m, so the grip hand mostly moves sideways.
    distance = block["eye_distance_m"] or -(hold.matrix_world @ eye).y - block["pull_back_m"]
    matrix = Matrix.Translation(Vector((0, -distance, 0)) - world_eye) @ rotation.to_matrix().to_4x4()
    return {"matrix": matrix, "sight_parts": sorted(obj.name for obj in parts), "mode": mode,
            "sight_local_m": list(sight), "eye_local_m": list(eye)}


def arm_bend(rig, shoulder, pole):
    """wrist_bend of the arm for a shoulder and elbow pole, without posing it (the hand is already placed)."""
    hand = rig["hand"].matrix_world
    wrist = hand @ rig["wrist"]
    elbow = Vector(solve_elbow(shoulder, wrist, *rig["lengths"], pole))
    return math.degrees((wrist - elbow).normalized().angle((hand.to_3x3() @ Vector((0, -1, 0))).normalized()))


def rest_arm(rig):
    """Forearm direction (elbow -> wrist) and upper arm (elbow -> shoulder) of the posed rest arm, camera axes."""
    wrist = rig["hand"].matrix_world @ rig["wrist"]
    elbow = Vector(solve_elbow(rig["shoulder"], wrist, *rig["lengths"], rig["pole"]))
    return (wrist - elbow).normalized(), rig["shoulder"] - elbow


def proximal_top(rig, elbow, forearm, view):
    """Highest screen y (0 = bottom edge) of a conservative box around the proximal forearm half, like validate: at the
    data FOV and, about Socket_Hand, at the game's largest enlargement (points behind the near plane count as hidden)."""
    length = rig["lengths"][1] * (1 - rig["visible_fraction"])
    side = forearm.cross(Vector((0, 0, 1))).normalized()
    up = side.cross(forearm).normalized()
    points = [elbow + forearm * along + side * x + up * y for along in (0, length) for x in (-.047, .047) for y in (-.047, .047)]
    result = -float("inf")
    for scale in ((1.0, GAME_ENLARGEMENT_MAX) if view["pivot"] is not None else (1.0,)):
        for point in points:
            if scale != 1.0:
                point = (point - view["pivot"]) * scale + view["pivot"]
            depth = -point.y
            result = max(result, .5 + point.z / depth / (2 * view["tan_v"]) if depth > view["near"] else -1.0)
    return result


def relaxed_forearm(rig, rest, turn, target):
    """Forearm direction of an ego clip frame before the framing correction. The forearm keeps its rest direction in camera
    space, turned by ``turn`` (the part ``follow`` of the weapon's turn), so the elbow only shifts with the hand; when the
    wrist would bend more than ``target`` degrees the forearm turns towards the knuckles just by the excess (sideways
    first, so the elbow keeps its height). Returns the direction and the frame data the correction needs."""
    hand = rig["hand"].matrix_world
    wrist = hand @ rig["wrist"]
    forearm, upper = turn @ rest[0], turn @ rest[1]
    knuckles = (hand.to_3x3() @ Vector((0, -1, 0))).normalized()
    limit = math.radians(target)
    if forearm.angle(knuckles) > limit:
        # First swing the forearm sideways (about the camera's up axis, the elbow keeps its height and stays below the
        # frame), towards the knuckle heading; only the rest of the excess lifts the forearm towards the knuckles.
        heading = math.atan2(knuckles.y, knuckles.x) - math.atan2(forearm.y, forearm.x)
        heading = (heading + math.pi) % (2 * math.pi) - math.pi
        def swung(angle):
            return Quaternion((0, 0, 1), angle) @ forearm
        side = rig.get("arm_limits", {}).get("palm_side")
        def palm_side(direction):        # wrist_bend's elbow test, with 1 cm to spare
            return side is None or (hand.inverted() @ (wrist - direction * rig["lengths"][1])).x * side > .01
        if not palm_side(swung(heading)):
            low, high = 0.0, 1.0
            for _ in range(20):
                middle = (low + high) / 2
                low, high = (middle, high) if palm_side(swung(heading * middle)) else (low, middle)
            heading *= low
        if swung(heading).angle(knuckles) <= limit:
            low, high = 0.0, 1.0
            for _ in range(20):
                middle = (low + high) / 2
                low, high = (middle, high) if swung(heading * middle).angle(knuckles) > limit else (low, middle)
            forearm = swung(heading * high)
        else:
            forearm = swung(heading)
            excess = forearm.angle(knuckles) - limit
            forearm = Quaternion(forearm.cross(knuckles).normalized(), excess) @ forearm
    return forearm, {"wrist": wrist, "knuckles": knuckles, "hand_inverse": hand.inverted(), "upper": upper,
                     "rest": turn @ rest[0]}


def correction_axis(forearm, index):
    """One of twelve axes perpendicular to the forearm (index 0 lifts it towards camera up)."""
    return Quaternion(forearm, math.tau * index / 12) @ forearm.cross(Vector((0, 0, 1))).normalized()


def corrected(forearm, index, angle):
    return Quaternion(correction_axis(forearm, index), angle) @ forearm


def correction_ok(rig, forearm, data, allowed):
    """Forearm direction keeps the proximal half below the frame, the wrist within its limit less 0.5 degrees and the
    elbow on the palm side."""
    elbow = data["wrist"] - forearm * rig["lengths"][1]
    side = rig.get("arm_limits", {}).get("palm_side")
    hard = rig["arm_limits"]["max_wrist_bend_degrees"] - .5 if "arm_limits" in rig else 180.0
    return (proximal_top(rig, elbow, forearm, data["view"]) <= allowed and math.degrees(forearm.angle(data["knuckles"])) <= hard
            and (side is None or (data["hand_inverse"] @ elbow).x * side > .01))


def smallest_correction(rig, forearm, data, allowed, index, limit=math.radians(60)):
    """Smallest turn about correction axis ``index`` that clears the frame (scanned outwards, the top is not monotone in
    the angle, then refined); None when no turn up to ``limit`` does."""
    def clear(angle):
        return proximal_top(rig, data["wrist"] - corrected(forearm, index, angle) * rig["lengths"][1],
                            corrected(forearm, index, angle), data["view"]) <= allowed
    high = next((math.radians(degrees) for degrees in range(1, 61) if math.radians(degrees) <= limit and clear(math.radians(degrees))), None)
    if high is None:
        return None
    low = high - math.radians(1)
    for _ in range(10):
        middle = (low + high) / 2
        low, high = (middle, high) if not clear(middle) else (low, middle)
    return high if correction_ok(rig, corrected(forearm, index, high), data, allowed) else None


def plan_corrections(rig, samples, clips, allowed, rate=math.radians(1.5)):
    """Framing correction of one arm over all ego clips: ONE axis for the whole timeline (the one whose largest needed turn
    is smallest), per frame the smallest turn about it, then within each clip raised to a slope of at most ``rate`` per
    frame (no twitch between neighbouring frames); clip ends keep their own value so equal poses stay equal. Returns
    the axis index and {frame: angle}."""
    needed = {frame: (forearm, data) for frame, (forearm, data) in samples.items()
              if proximal_top(rig, data["wrist"] - forearm * rig["lengths"][1], forearm, data["view"]) > allowed}
    if not needed:
        return 0, {}
    best = None
    for index in range(12):
        angles = {frame: smallest_correction(rig, forearm, data, allowed, index) for frame, (forearm, data) in needed.items()}
        missing = sum(angle is None for angle in angles.values())
        score = (missing, max((angle for angle in angles.values() if angle is not None), default=0.0))
        if best is None or score < best[0]:
            best = (score, index, angles)
    _, index, raw = best
    raw = {frame: angle or 0.0 for frame, angle in raw.items()}
    result = {}
    for clip in clips:
        frames = range(clip["frame_start"], clip["frame_end"] + 1)
        values = {frame: raw.get(frame, 0.0) for frame in frames}
        if not any(values.values()):
            continue
        for frame in frames:
            smooth = max(value - rate * abs(frame - other) for other, value in values.items())
            if frame in (clip["frame_start"], clip["frame_end"]):
                smooth = values[frame]
            forearm, data = samples[frame]
            if smooth > values[frame] and not correction_ok(rig, corrected(forearm, index, smooth), data, allowed):
                smooth = values[frame]
            result[frame] = smooth
    return index, result


def clip_matrix(values, aim, pivot, forearm=None):
    """Viewmodel_Motion of an ego clip pose (scripts/tool_assets/ego_clips.py): the aim blend moves the grip hand on a
    straight line and turns about it; ``twist`` turns about the grip forearm's rest axis through the wrist (``forearm``:
    wrist point and direction; pronation, the wrist does not bend), then the pose turns about the (aimed) hand and shifts
    in camera axes."""
    blend = Matrix.Identity(4)
    if aim is not None and values["aim"] > 0:
        rotation = aim.to_quaternion()
        target = aim @ pivot
        blend = (Matrix.Translation(pivot.lerp(target, values["aim"]))
                 @ Quaternion().slerp(rotation, values["aim"]).to_matrix().to_4x4() @ Matrix.Translation(-pivot))
    if values.get("twist") and forearm is not None:
        wrist, axis = blend @ forearm[0], blend.to_3x3() @ forearm[1]
        # positive twist: the top tilts left as the player sees it (clockwise about an axis pointing away is negative)
        blend = (Matrix.Translation(wrist) @ Quaternion(axis, -math.radians(values["twist"])).to_matrix().to_4x4()
                 @ Matrix.Translation(-wrist) @ blend)
    rotation = Euler((-math.radians(values["pitch"]), math.radians(values["roll"]), math.radians(values["yaw"])), "XYZ")
    center = blend @ pivot
    offset = Vector((-values["right"], values["back"], values["up"]))
    return Matrix.Translation(center + offset) @ rotation.to_matrix().to_4x4() @ Matrix.Translation(-center) @ blend


def ego_clip_report(scene, root, clips, records, aim, aim_frames, settings, part_name, part):
    """Per clip: wrist bend, aim; aim down sights: line of sight on the screen centre and the sight parts readable
    (not hidden by the hands or other parts); no clip animates a material or colour."""
    failures, warnings = [], []
    ads = None
    full_aim = [frame for clip in clips if clip["motion"] == "aim_idle" for frame in (clip["frame_start"],)]
    if aim and full_aim:
        frame = full_aim[0]
        scene.frame_set(frame); bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        hold = scene.objects["Viewmodel_Hold"]
        tan_v = math.tan(math.radians(settings["vertical_fov_degrees"]) / 2)
        base = {"tan_h": tan_v * aspect_ratio(settings["reference_aspect"]), "tan_v": tan_v}
        u, v, depth = camera_space(np.array([hold.matrix_world @ Vector(aim["eye_local_m"])]))
        x, y = screen(u, v, base)
        sight = [scene.objects[name] for name in aim["sight_parts"]]
        # The tool hides parts of its own sights from the side (slide, rails): only hands and arms count as occluders.
        others = [obj for obj in root.children_recursive if obj.type == "MESH" and obj.name.startswith("SM_FPS_")]
        vertices, polygons, owners = mesh_data(others, graph)
        blocker = BVHTree.FromPolygons(vertices, polygons)
        visible = total = 0
        occluders = {}
        for obj in sight:
            for point in world_vertices(obj, graph)[::7]:
                target = Vector(point.tolist())
                hit = blocker.ray_cast(Vector(), target.normalized(), target.length - 1e-4)
                total += 1
                if hit[0] is None:
                    visible += 1
                else:
                    occluders[owners[hit[2]]] = occluders.get(owners[hit[2]], 0) + 1
        ads = {"frame": frame, "line_of_sight_screen": [float(x[0]), float(y[0])], "depth_m": float(depth[0]),
               "sight_parts": aim["sight_parts"], "mode": aim["mode"], "eye_local_m": aim["eye_local_m"],
               "sight_visible_fraction": visible / total if total else None,
               "occluders": dict(sorted(occluders.items(), key=lambda item: -item[1])[:4])}
        if max(abs(x[0] - .5), abs(y[0] - .5)) > .002:
            failures.append(f"aim: line of sight off the screen centre ({x[0]:.4f}, {y[0]:.4f})")
        if total and visible / total < .9:
            failures.append(f"aim: sight hidden ({visible}/{total} sample points visible, {ads['occluders']})")
        if not total:
            warnings.append("aim: no sight parts, line of sight over the highest point of the tool")
        scene.frame_set(1); bpy.context.view_layer.update()
    if part_name and part is None:
        failures.append(f"reload: part {part_name} (data/ego_clips.json reload.part) missing in the model")
    animated_materials = sorted(item.name for item in [*bpy.data.materials, *bpy.data.node_groups]
                                if item.animation_data and item.animation_data.action)
    animated_materials += sorted(mat.name for mat in bpy.data.materials if mat.node_tree and mat.node_tree.animation_data
                                 and mat.node_tree.animation_data.action)
    if animated_materials:
        failures.append(f"materials animated: {animated_materials}")
    # Draw/Holster (0.15.0): travel of Socket_Hand from the rest pose to the lowered pose, camera axes; drop = downwards.
    holster = next((clip for clip in clips if clip["to"] == "lowered"), None)
    lowered = None
    if holster:
        socket = scene.objects["Socket_Hand"]
        points = []
        for frame in (1, holster["frame_end"]):
            scene.frame_set(frame); bpy.context.view_layer.update()
            points.append(socket.matrix_world.translation.copy())
        scene.frame_set(1); bpy.context.view_layer.update()
        lowered = {"clip": holster["name"], "hand_drop_m": round(points[0].z - points[1].z, 5),
                   "hand_travel_m": round((points[1] - points[0]).length, 5)}
    return {"clips": [{"name": clip["name"], "frame_start": clip["frame_start"], "frame_end": clip["frame_end"],
                       "length": clip["length"], "loop": clip["loop"], "from": clip["from"], "to": clip["to"],
                       **records[clip["name"]]} for clip in clips],
            "frames": sum(clip["length"] + 1 for clip in clips), "aim_frames": len(aim_frames), "ads": ads,
            "reload_part": part.name if part is not None else None, "lowered": lowered, "failures": failures,
            "warnings": warnings}


def configure_camera(scene, settings):
    """Set the preview camera to the data FOV and confirm the analytic QA projection matches it."""
    camera = scene.camera
    assert camera is not None and camera.data.type == "PERSP"
    assert scene.render.resolution_x * 9 == scene.render.resolution_y * 16, "Ego preview must stay 16:9"
    camera.data.sensor_fit = "VERTICAL"
    camera.data.sensor_height = 24
    camera.data.lens = 12 / math.tan(math.radians(settings["vertical_fov_degrees"]) / 2)
    camera.data.clip_start = settings["near_clip_m"]
    bpy.context.view_layer.update()
    tan_v = math.tan(math.radians(settings["vertical_fov_degrees"]) / 2)
    frustum = {"tan_h": tan_v * 16 / 9, "tan_v": tan_v}
    for probe in (Vector((-.21, -.8, .13)), Vector((.35, -.5, -.2))):
        expected = world_to_camera_view(scene, camera, probe)
        u, v, _ = camera_space(np.array([probe]))
        x, y = screen(u[0], v[0], frustum)
        assert abs(expected.x - x) < 1e-5 and abs(expected.y - y) < 1e-5, ("camera differs from QA projection", expected, x, y)


def validated_fovs(fov_range):
    """Vertical FOVs (degrees) of the measured range at which the framing holds for every checked aspect."""
    found = {}
    for entry in fov_range:
        found.setdefault(entry["vertical_fov_degrees"], []).append(entry["ok"])
    return [value for value, results in sorted(found.items()) if all(results)]


def camera_document(tool, settings, report):
    """Small, game-facing summary of the viewmodel camera next to the exports."""
    return {"format": 1, "tool": tool, "vertical_fov_degrees": settings["vertical_fov_degrees"],
            "horizontal_fov_degrees": settings["horizontal_fov_degrees"],
            "reference_aspect": settings["reference_aspect"], "near_clip_m": settings["near_clip_m"],
            "override": settings["override"], "unity": settings["unity"],
            "player_fov_dependency": "none",
            "validated_vertical_fov_degrees": validated_fovs(report["fov_range"]),
            "aspect_policy": "Vertical FOV is the fixed value; the horizontal FOV follows the aspect ratio. Framing is "
                             "binding for " + ", ".join(settings["qa_aspects"]) + "; wider screens show the same "
                             "image with more room at the sides, the hands stay in frame.",
            "camera_offset_m": [0.0, 0.0, 0.0],
            "runtime": "The model sits in camera space (Socket_Camera = identity). Render it with a separate camera "
                       "(or URP camera stack overlay) whose Camera.fieldOfView is vertical_fov_degrees and whose "
                       "nearClipPlane is near_clip_m. The framing (hands in frame, free reticle, forearms out of "
                       "view) is verified at vertical_fov_degrees only; a game setting may use another value only "
                       "from validated_vertical_fov_degrees (measured, see checked_range). The player's world FOV "
                       "never scales the viewmodel and is not baked into it.",
            "checked_range": report["framing_range"]["summary"],
            "root_properties": ["ce_viewmodel_vertical_fov_degrees", "ce_viewmodel_horizontal_fov_degrees",
                                "ce_viewmodel_reference_aspect", "ce_viewmodel_near_clip_m"]}


def mesh_data(objects, graph):
    """World-space polygons of the evaluated meshes for occlusion rays."""
    vertices, polygons, owners = [], [], []
    for obj in objects:
        evaluated = obj.evaluated_get(graph)
        matrix = evaluated.matrix_world
        offset = len(vertices)
        vertices.extend(matrix @ vertex.co for vertex in evaluated.data.vertices)
        for polygon in evaluated.data.polygons:
            polygons.append([offset + index for index in polygon.vertices])
            owners.append(obj.name)
    return vertices, polygons, owners


def head_visibility(scene, root, head, frusta, settings):
    """Rest-pose head check: anchor inside the frame and enough unoccluded head on screen.

    Rays sample the head's screen footprint; a sample counts when the first surface hit
    belongs to the head (housing, hands and arms in front of it occlude it)."""
    scene.frame_set(1); bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    limits = settings["qa"]
    meshes = [obj for obj in root.children_recursive if obj.type == "MESH"]
    parts = [obj for obj in meshes if obj.name.startswith(tuple(head["parts"]))]
    assert parts, (head, "no head geometry")
    all_vertices, all_polygons, owners = mesh_data(meshes, graph)
    head_vertices, head_polygons, _ = mesh_data(parts, graph)
    every = BVHTree.FromPolygons(all_vertices, all_polygons)
    only = BVHTree.FromPolygons(head_vertices, head_polygons)
    names = {obj.name for obj in parts}
    u, v, depth = camera_space(np.array(head_vertices))
    assert (depth > 0).all()
    tan_v = math.tan(math.radians(settings["vertical_fov_degrees"]) / 2)
    step = 2 * tan_v / 360
    origin = Vector((0, 0, 0))
    total = 0
    occluders = {}
    visible = [0] * len(frusta)
    for a in np.arange(u.min(), u.max() + step, step):
        for b in np.arange(v.min(), v.max() + step, step):
            direction = Vector((-a, -1, b)).normalized()
            hit = only.ray_cast(origin, direction)
            if hit[0] is None:
                continue
            total += 1
            first = every.ray_cast(origin, direction)
            if first[0] is None or owners[first[2]] not in names and first[3] < hit[3] - 1e-6:
                if first[0] is not None:
                    occluders[owners[first[2]]] = occluders.get(owners[first[2]], 0) + 1
                continue
            for index, frustum in enumerate(frusta):
                if abs(a) <= frustum["tan_h"] and abs(b) <= frustum["tan_v"]:
                    visible[index] += 1
    anchor = scene.objects[head["anchor"]].matrix_world.translation
    au, av, ad = camera_space(np.array([anchor]))
    assert ad[0] > settings["near_clip_m"], (head["anchor"], "behind the near clip")
    occluders = dict(sorted(occluders.items(), key=lambda item: -item[1])[:5])
    results = []
    for index, frustum in enumerate(frusta):
        x, y = screen(au[0], av[0], frustum)
        results.append({"anchor_margin": float(min(x, 1 - x, y, 1 - y)), "parts": len(parts), "samples": total,
                        "unoccluded_on_screen_fraction": visible[index] / max(total, 1),
                        "screen_fraction": visible[index] * step * step / (4 * frustum["tan_h"] * frustum["tan_v"]),
                        "main_occluders": occluders})
    return results


def hand_touch(scene, root, arms):
    """Smallest distance (m) from each hand's finger, thumb and palm vertices to the tool surface at rest (the hands
    are rigid with the tool; the rest pose is the pose of the whole clip). A hand in the air shows a large value."""
    scene.frame_set(1); bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    tool = [obj for obj in root.children_recursive if obj.type == "MESH" and not obj.name.startswith("SM_FPS_")]
    vertices, polygons, _ = mesh_data(tool, graph)
    surface = BVHTree.FromPolygons(vertices, polygons)
    result = {}
    for rig in arms:
        nearest = float("inf")
        for obj in rig["hand"].children_recursive:
            if obj.type == "MESH" and obj.name.startswith(("SM_FPS_Finger_", "SM_FPS_Thumb", "SM_FPS_Palm", "SM_FPS_Knuckle")):
                evaluated = obj.evaluated_get(graph)
                for vertex in evaluated.data.vertices:
                    hit = surface.find_nearest(evaluated.matrix_world @ vertex.co)
                    if hit[0] is not None:
                        nearest = min(nearest, float(hit[3]))
        result[rig["hand"].name] = nearest
    return result


def hand_vertex_sets(rig, graph):
    """Finger, thumb and palm vertices of a hand (the surface hand_touch measures)."""
    for obj in rig["hand"].children_recursive:
        if obj.type == "MESH" and obj.name.startswith(("SM_FPS_Finger_", "SM_FPS_Thumb", "SM_FPS_Palm", "SM_FPS_Knuckle")):
            yield world_vertices(obj, graph)


def clip_hand_touch(scene, root, arms, clips, detached, support_hand):
    """hand_touch per ego clip frame (T6, Cube Escape 0.72): the largest per-frame distance of each hand to the tool
    surface within a clip. A hand released on purpose (reload: ``detached`` frames of the support hand) is left out."""
    tool = [obj for obj in root.children_recursive if obj.type == "MESH" and not obj.name.startswith("SM_FPS_")]
    result = {}
    for clip in clips:
        worst = {}
        for frame in range(clip["frame_start"], clip["frame_end"] + 1):
            scene.frame_set(frame); bpy.context.view_layer.update()
            graph = bpy.context.evaluated_depsgraph_get()
            vertices, polygons, _ = mesh_data(tool, graph)
            surface = BVHTree.FromPolygons(vertices, polygons)
            for rig in arms:
                name = rig["hand"].name
                if name == support_hand and frame in detached:
                    continue
                nearest = min((float(surface.find_nearest(Vector(point))[3]) for points in hand_vertex_sets(rig, graph)
                               for point in points.tolist()), default=float("inf"))
                if nearest > worst.get(name, (-1.0, None))[0]:
                    worst[name] = (nearest, frame)
        result[clip["name"]] = {name: {"m": round(value, 6), "frame": frame} for name, (value, frame) in worst.items()}
    scene.frame_set(1); bpy.context.view_layer.update()
    return result


def sight_socket_check(scene, hold, aim):
    """Socket_Sight (sight.py, placed in the world model) lies on the AimIdle line of sight: same lateral and vertical
    position in the tool's space as the eye point of ads_setup, and its rotation is the tool's (+Z Unity = along the bore)."""
    socket = scene.objects.get("Socket_Sight")
    if socket is None or aim is None:
        return None
    scene.frame_set(1); bpy.context.view_layer.update()
    inverse = hold.matrix_world.inverted()
    local = inverse @ socket.matrix_world.translation
    eye = Vector(aim["eye_local_m"])
    offset = max(abs(local.x - eye.x), abs(local.z - eye.z))
    turn = math.degrees((inverse.to_quaternion() @ socket.matrix_world.to_quaternion()).angle)
    return {"socket_local_m": [round(v, 6) for v in local], "aim_eye_local_m": [round(v, 6) for v in eye],
            "line_offset_m": round(offset, 7), "rotation_error_degrees": round(min(turn, 360 - turn), 5),
            "ok": offset <= SIGHT_LINE_TOLERANCE_M and min(turn, 360 - turn) <= .01}


def ads_target_report(scene, root, arms, settings, eye_distance_m, support_hand):
    """Cube Escape's aim-down-sights target pose (FIRST_PERSON_EQUIPMENT.md 5.3): the whole first-person model in its rest
    pose (frame 1) moved rigidly so Socket_Sight lies on the camera axis at an eye distance and looks along the view
    (rotation = inverse of Socket_Sight's, scale 1). Framing rule per binding frustum (configured FOV, 16:9 and 16:10):
    sight on the screen centre; the three gripping fingers and the thumb of each hand inside the frame; the proximal
    forearm halves below the frame (the support forearm may show while aiming, user decision 16.10.2026: measured, not
    binding); no vertex inside the frame closer than the near clip. Reported at ``eye_distance_m`` (the game profile,
    data/tools.json hold) and as the eye-distance range that keeps the rule (``eye_distance_range_m``). Wrist bend and
    hand touch do not change under a rigid move; they are reported from the rest pose. The whole hand's margin is
    measured, not binding (the palm may leave the frame at the bottom)."""
    socket = scene.objects.get("Socket_Sight")
    if socket is None:
        return None
    scene.frame_set(1); bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    near = settings["near_clip_m"]
    sight = socket.matrix_world
    rotation = sight.to_quaternion().inverted().to_matrix()
    turned = np.array(rotation)
    base = -np.array(rotation @ sight.translation)

    def moved(points, distance):
        return points @ turned.T + base + np.array((0.0, -distance, 0.0))

    frusta = [frustum for frustum in frustum_configurations(settings) if frustum["binding"]]
    meshes = [obj for obj in root.children_recursive if obj.type == "MESH"]
    every = np.concatenate([world_vertices(obj, graph) for obj in meshes])
    sight_point = np.array([sight.translation])
    parts = {}
    for rig in arms:
        side = rig["hand"].name[-1]
        groups = {f"Fingers_{side}_{index}": scene.objects[f"Fingers_{side}_{index}"] for index in range(GRIPPING_FINGERS)}
        groups["Thumb_" + side] = scene.objects["Thumb_" + side]
        groups[rig["hand"].name] = rig["hand"]
        parts[rig["hand"].name] = {name: np.concatenate([world_vertices(obj, graph) for obj in node.children_recursive
                                                        if obj.type == "MESH"]) for name, node in groups.items()}
    forearms = {}
    for rig in arms:
        lower = np.array(rig["lower"].matrix_world)
        corners = np.array([(cx, cy, cz) for cz in (0, rig["lengths"][1] * (1 - rig["visible_fraction"]))
                            for cx in (-.047, .047) for cy in (-.047, .047)])
        forearms[rig["hand"].name] = corners @ lower[:3, :3].T + lower[:3, 3]

    def evaluate(distance):
        configurations, failures = [], []
        for frustum in frusta:
            label = f"{frustum['vertical_fov_degrees']:.2f} deg vertical, {frustum['aspect']}"
            u, v, _ = camera_space(moved(sight_point, distance))
            x, y = screen(u, v, frustum)
            entry = {"vertical_fov_degrees": frustum["vertical_fov_degrees"], "aspect": frustum["aspect"],
                     "sight_screen": [round(float(x[0]), 6), round(float(y[0]), 6)], "margins": {},
                     "proximal_forearm_max_screen_y": {}}
            reasons = []
            if max(abs(x[0] - .5), abs(y[0] - .5)) > .002:
                reasons.append(f"sight off the screen centre ({x[0]:.4f}, {y[0]:.4f})")
            for hand_name, groups in parts.items():
                margins = {}
                for name, points in groups.items():
                    pu, pv, pdepth = camera_space(moved(points, distance))
                    px, py = screen(pu, pv, frustum)
                    margins[name] = round(float(min(px.min(), (1 - px).min(), py.min(), (1 - py).min())), 5) \
                        if (pdepth > near).all() else -1.0
                entry["margins"][hand_name] = margins
                outside = sorted(name for name, margin in margins.items() if name != hand_name and margin < 0)
                if outside:
                    reasons.append(f"{hand_name}: {outside} not in the frame")
            for name, corners in forearms.items():
                cu, cv, cdepth = camera_space(moved(corners, distance))
                top = float(np.where(cdepth > near, screen(cu, cv, frustum)[1], -1.0).max())
                entry["proximal_forearm_max_screen_y"][name] = round(top, 5)
                if top >= 0 and name != support_hand:
                    reasons.append(f"proximal forearm of {name} enters the viewport (y {top:.4f})")
            eu, ev, edepth = camera_space(moved(every, distance))
            ex, ey = screen(eu, ev, frustum)
            seen = (ex >= 0) & (ex <= 1) & (ey >= 0) & (ey <= 1) & (edepth > 0)
            beside = (ex >= 0) & (ex <= 1) & (edepth > near)
            entry["model_top_screen_y"] = round(float(ey[beside].max()), 5) if beside.any() else None
            closest = float(edepth[seen].min()) if seen.any() else None
            entry["min_visible_depth_m"] = closest and round(closest, 5)
            if closest is not None and closest <= near:
                reasons.append(f"a visible vertex lies in front of the near clip ({closest:.4f} m)")
            entry["ok"] = not reasons
            entry["reasons"] = reasons
            configurations.append(entry)
            failures.extend(f"{label}: {reason}" for reason in reasons)
        return configurations, failures

    configurations, failures = evaluate(eye_distance_m)
    # Cube Escape 0.72: the screen centre stays free (the ray along the view meets no part, a scope's eye lens excepted)
    # and the model reaches at most ADS_TOP_LIMIT of the screen height above the centre, at the profile distance.
    vertices, polygons, owners = mesh_data(meshes, graph)
    shifted = moved(np.array([tuple(vertex) for vertex in vertices]), eye_distance_m)
    tree = BVHTree.FromPolygons([Vector(point) for point in shifted.tolist()], polygons)
    hit = tree.ray_cast(Vector((0, 0, 0)), Vector((0, -1, 0)), 50.0)
    centre_hit = owners[hit[2]] if hit[0] is not None else None
    centre_clear = centre_hit is None or centre_hit.removeprefix("SM_PG_") in ADS_CENTRE_ALLOWED
    tops = [entry["model_top_screen_y"] for entry in configurations if entry["model_top_screen_y"] is not None]
    top_above = round(max(tops) - .5, 5) if tops else None
    steps = [round(.10 + .005 * index, 3) for index in range(141)]           # 0.10 ... 0.80 m
    passing = [distance for distance in steps if not evaluate(distance)[1]]
    bends = {}
    for rig in arms:
        if "arm_limits" in rig:
            bend, _ = wrist_bend(rig)
            bends[rig["hand"].name] = {"degrees": round(bend, 2), "limit_degrees": rig["arm_limits"]["max_wrist_bend_degrees"]}
    matrix = Matrix.Translation(Vector(base.tolist()) + Vector((0, -eye_distance_m, 0))) @ rotation.to_4x4()
    return {"pose": "rest pose (frame 1) moved rigidly: Socket_Sight on the camera axis at the eye distance, rotation = "
                    "inverse of Socket_Sight's (FIRST_PERSON_EQUIPMENT.md 5.3); scale 1",
            "rule": "three gripping fingers and the thumb of each hand in the frame, proximal forearm halves below it "
                    "(support forearm measured only, user decision 16.10.2026), no visible vertex before the near clip",
            "sight_socket": "Socket_Sight", "eye_distance_m": eye_distance_m,
            "frame_matrix_blender": [[round(float(value), 7) for value in row] for row in matrix],
            "near_clip_m": near, "support_forearm_exempt": support_hand, "configurations": configurations,
            "passed": not failures, "failures": failures,
            "centre_clear": centre_clear, "centre_hit": centre_hit, "model_top_above_centre": top_above,
            "model_top_limit": ADS_TOP_LIMIT, "model_top_ok": top_above is None or top_above <= ADS_TOP_LIMIT,
            "eye_distance_range_m": [passing[0], passing[-1]] if passing else None,
            "eye_distance_steps_m": [steps[0], steps[-1], .005],
            "eye_distance_range_contiguous": bool(passing) and len(passing) == round((passing[-1] - passing[0]) / .005) + 1,
            "wrist_bend": bends}


def validate(scene, root, targets, tool, arms, settings, head, touch_limit=None, clip_check=None):
    limits = settings["qa"]
    frusta = frustum_configurations(settings)
    tan_v = math.tan(math.radians(settings["vertical_fov_degrees"]) / 2)
    base = {"tan_h": tan_v * aspect_ratio(settings["reference_aspect"]), "tan_v": tan_v}
    reticle = limits["reticle_half_extent"]
    near = settings["near_clip_m"]
    # A tool may relax the two head limits in its profile (head.limits: slender barrels under the support hand);
    # the effective values are reported with the head summary and checked again by scripts/verify_output.py.
    head_limits = {key: (head or {}).get("limits", {}).get(key, limits[key])
                   for key in ("head_anchor_margin", "head_min_unoccluded_fraction", "head_min_screen_fraction")}
    failures = []
    max_contact = 0; minimum_depth = float("inf")
    maximum_arm_error = 0
    minimum_hand_side_clearance = float("inf")
    visible_forearms = {rig["hand"].name: 0 for rig in arms}
    proximal = [{rig["hand"].name: -float("inf") for rig in arms} for _ in frusta]
    proximal_base = {rig["hand"].name: -float("inf") for rig in arms}
    proximal_worst_frame = {rig["hand"].name: None for rig in arms}
    grip_socket = scene.objects.get("Socket_Hand") if tool != "bow" else None
    # only measured hands get a value (the bow is not enlarged by the game; no -Infinity in the JSON report)
    proximal_enlarged = {rig["hand"].name: -float("inf") for rig in arms} if grip_socket is not None else {}
    hand_margin = [{rig["hand"].name: float("inf") for rig in arms} for _ in frusta]
    hand_worst_frame = [{rig["hand"].name: None for rig in arms} for _ in frusta]
    hand_edges = [{rig["hand"].name: [float("inf")] * 4 for rig in arms} for _ in frusta]
    rest_hand_margin = [{rig["hand"].name: float("inf") for rig in arms} for _ in frusta]
    reticle_hits = [set() for _ in frusta]
    reticle_frames = [{} for _ in frusta]
    hand_meshes = {rig["hand"].name: {obj.name for obj in rig["hand"].children_recursive if obj.type == "MESH"} for rig in arms}
    tracking = [obj for obj in root.children_recursive if obj.type == "EMPTY" and
                (obj.name.startswith(("Hand_", "GripContact_", "UpperArm_", "LowerArm_", "Thumb_", "Fingers_", "Anim_"))
                 or obj.name == "Viewmodel_Motion")]
    meshes = [obj for obj in root.children_recursive if obj.type == "MESH"]
    forearm_local = {}
    for rig in arms:
        for obj in rig["lower"].children:
            if obj.type == "MESH":
                local = np.empty(len(obj.data.vertices) * 3)
                obj.data.vertices.foreach_get("co", local)
                matrix = np.array(obj.matrix_local)
                forearm_local.setdefault(rig["hand"].name, []).append(local.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3])
    poses = {}
    rest = None
    grip_rest = None
    grip_draw = None
    centered_wrist_error = 0
    clip_check = clip_check or {"clips": [], "frames": list(range(1, 98)), "detached": set(), "reticle_exempt": set(),
                                "support_contact": None, "support_forearm_visible": set(), "support_hand": None}
    exempt_forearm = {}
    previous_forearm, forearm_step = {}, {}
    clip_frames = {frame for clip in clip_check["clips"] for frame in range(clip["frame_start"], clip["frame_end"] + 1)}
    boundaries = {}
    for frame in clip_check["frames"]:
        scene.frame_set(frame); bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        for rig in arms:
            wrist = rig["hand"].matrix_world @ rig["wrist"]
            if tool == "bow":
                sign = 1 if rig["hand"].name == "Hand_L" else -1
                clearance = sign * (wrist.x - rig["hand"].matrix_world.translation.x)
                assert clearance > .01, (tool, frame, rig["hand"].name, "wrist crossed to the wrong side of its grip")
                minimum_hand_side_clearance = min(minimum_hand_side_clearance, clearance)
            elbow = rig["lower"].matrix_world.translation
            shoulder = rig["upper"].matrix_world.translation
            upper, lower = rig["lengths"]
            end = rig["lower"].matrix_world @ Vector((0, 0, lower))
            error = max(abs((elbow - shoulder).length - upper), abs((wrist - elbow).length - lower), (end - wrist).length)
            assert error < .0001, (tool, frame, rig["hand"].name, "arm joint detached or stretched", error)
            maximum_arm_error = max(maximum_arm_error, error)
        for rig in arms:
            name = rig["hand"].name
            direction = rig["lower"].matrix_world.to_3x3() @ Vector((0, 0, 1))
            # twitch = change of the forearm's turn rate between neighbouring frames (a fast but smooth turn passes)
            if frame in clip_frames and frame - 1 in clip_frames and name in previous_forearm:
                rate = previous_forearm[name][0].cross(direction)
                if frame - 2 in clip_frames and previous_forearm[name][1] is not None:
                    step = math.degrees((rate - previous_forearm[name][1]).length)
                    # short transitions (aim in/out, sprint in/out: 6-12 frames) turn fast by design: half the weight
                    if ego_clips.clip_at(clip_check["clips"], frame)["length"] < 16:
                        step /= 2
                    if step > forearm_step.get(name, (0.0, None))[0]:
                        forearm_step[name] = (step, frame)
                previous_forearm[name] = (direction, rate)
            else:
                previous_forearm[name] = (direction, None)
            length = rig["lengths"][1]
            matrix = np.array(rig["lower"].matrix_world)
            # A conservative box encloses the entire proximal half, including faces
            # which cross the viewport even when their vertices lie outside it.
            corners = np.array([(x, y, z) for z in (0, length * (1 - rig["visible_fraction"]))
                                for x in (-.047, .047) for y in (-.047, .047)])
            u, v, _ = camera_space(corners @ matrix[:3, :3].T + matrix[:3, 3])
            if frame in clip_check["support_forearm_visible"] and name == clip_check["support_hand"]:
                # Aiming down sights (user decision 16.10.2026): the support forearm may show; measured, not binding.
                exempt_forearm[name] = max(exempt_forearm.get(name, -float("inf")), float(screen(u, v, base)[1].max()))
                continue
            for index, frustum in enumerate(frusta):
                proximal[index][name] = max(proximal[index][name], float(screen(u, v, frustum)[1].max()))
            value = float(screen(u, v, base)[1].max())
            if value > proximal_base[name]:
                proximal_base[name] = value; proximal_worst_frame[name] = frame
            if grip_socket is not None:
                pivot = np.array(grip_socket.matrix_world.translation)
                world = corners @ matrix[:3, :3].T + matrix[:3, 3]
                u, v, depth = camera_space((world - pivot) * GAME_ENLARGEMENT_MAX + pivot)
                y = screen(u, v, base)[1]
                # behind the near plane is out of view (the projection would flip it)
                proximal_enlarged[name] = max(proximal_enlarged[name], float(np.where(depth > near, y, -1.0).max()))
            for local in forearm_local.get(name, ()):
                u, v, depth = camera_space(local @ matrix[:3, :3].T + matrix[:3, 3])
                x, y = screen(u, v, base)
                inside = (x >= 0) & (x <= 1) & (y >= 0) & (y <= 1) & (depth > near)
                if inside.any():
                    visible_forearms[name] = max(visible_forearms[name], float((1 - local[inside, 2] / length).max()))
        for contact_name, target in targets.items():
            if tool == "bow" and target == "Socket_Nock" and 43 < frame < 79:
                continue
            # Reload: the support hand leaves the handguard (ego clip ``detached``); it is framed like every hand.
            if contact_name == clip_check["support_contact"] and frame in clip_check["detached"]:
                continue
            error = (scene.objects[contact_name].matrix_world.translation - scene.objects[target].matrix_world.translation).length
            assert error < .0001, (tool, frame, contact_name, "hand detached", error)
            max_contact = max(max_contact, error)
        for obj in meshes:
            u, v, depth = camera_space(world_vertices(obj, graph))
            assert depth.min() > near, (tool, frame, obj.name, "near clip", float(depth.min()))
            minimum_depth = min(minimum_depth, float(depth.min()))
            owner = next((hand for hand, names in hand_meshes.items() if obj.name in names), None)
            # The bow's draw hand travels to the cheek and down for the next arrow; it is
            # framed in its rest pose only. Grip and support hands stay framed all clip long.
            if owner == "Hand_R" and tool == "bow" and 1 < frame < 97:
                owner = None
            for index, frustum in enumerate(frusta):
                x, y = screen(u, v, frustum)
                # Aim down sights, inspect and reload may cover the reticle (ego clip ``reticle_free``: false).
                if frame not in clip_check["reticle_exempt"] and ((np.abs(x - .5) < reticle) & (np.abs(y - .5) < reticle)).any():
                    reticle_hits[index].add(obj.name)
                    reticle_frames[index].setdefault(obj.name, frame)
                if owner:
                    edges = (float(x.min()), float((1 - x).min()), float(y.min()), float((1 - y).min()))
                    hand_edges[index][owner] = [min(a, b) for a, b in zip(hand_edges[index][owner], edges)]
                    margin = min(edges)
                    if margin < hand_margin[index][owner]:
                        hand_margin[index][owner] = margin; hand_worst_frame[index][owner] = frame
                    if frame == 1:
                        rest_hand_margin[index][owner] = min(rest_hand_margin[index][owner], margin)
        if tool == "bow" and frame in (1, 31):
            matrix = scene.objects["Socket_Hand"].matrix_world.copy()
            if frame == 1:
                grip_rest = matrix
            else:
                grip_draw = matrix
        current = {obj.name: matrix_rows(obj) for obj in tracking}
        if frame == 1:
            rest = current
        if frame == 97:
            use_end = current
        for clip in clip_check["clips"]:
            if frame in (clip["frame_start"], clip["frame_end"]):
                boundaries[(clip["name"], "from" if frame == clip["frame_start"] else "to")] = current
        if frame in (1, 16, 31, 43, 44, 48, 60, 79, 97):
            poses[str(frame)] = current
    def difference(a, b):
        return max(abs(a[name][i][j] - matrix[i][j]) for name, matrix in b.items() for i in range(4) for j in range(4))
    maximum_reset = difference(use_end, rest)
    # Every clip starts and ends exactly in its named pose (rest = frame 1 of Use; aim, sprint, lowered: first occurrence),
    # so clips that meet in a pose can be cut together without a crossfade.
    references = {"rest": rest}
    boundary_errors = {}
    for clip in clip_check["clips"]:
        for end in ("from", "to"):
            matrices = boundaries[(clip["name"], end)]
            reference = references.setdefault(clip[end], matrices)
            boundary_errors[f"{clip['name']}.{end}"] = difference(matrices, reference)
    for name, error in boundary_errors.items():
        if error > .0001:
            clip_name, end = name.rsplit(".", 1)
            matrices = boundaries[(clip_name, end)]
            reference = references[next(clip[end] for clip in clip_check["clips"] if clip["name"] == clip_name)]
            worst = max(reference, key=lambda node: difference({node: matrices[node]}, {node: reference[node]}))
            failures.append(f"{name}: pose differs from its named pose ({error:.6f}, {worst})")
    assert maximum_reset < .0001, (tool, "rig does not return to rest", maximum_reset)
    assert not any(obj.type == "MESH" and obj.get("ce_role") == "first_person_robot" and obj.name.startswith(("SM_FPS_UpperArm", "SM_FPS_Elbow")) for obj in root.children_recursive)
    for rig in arms:
        side = rig["hand"].name[-1]
        assert all(scene.objects.get(f"Fingers_{side}_{index}") is not None for index in range(GRIPPING_FINGERS))
        assert scene.objects.get(f"Fingers_{side}_{GRIPPING_FINGERS}") is None
        assert scene.objects.get(f"Thumb_{side}") is not None
        palm = scene.objects["SM_FPS_Palm_" + side].location
        wrist = scene.objects["SM_FPS_WristBall_" + side].location
        error = max(abs(palm.x - wrist.x), abs(palm.z - wrist.z))
        assert error < .00001 and wrist.y > palm.y, (tool, side, "wrist is not centered behind the palm")
        centered_wrist_error = max(centered_wrist_error, error)
    bow_shift = (grip_draw.translation - grip_rest.translation).length if tool == "bow" else None
    bow_rotation = math.degrees(grip_rest.to_quaternion().rotation_difference(grip_draw.to_quaternion()).angle) if tool == "bow" else None
    if tool == "bow":
        assert bow_shift > .02 and bow_rotation > 5, ("bow stays static during draw", bow_shift, bow_rotation)
    touch = hand_touch(scene, root, arms)
    if touch_limit is not None:
        failures.extend(f"{name} does not touch the tool (nearest {distance * 1000:.1f} mm, limit {touch_limit * 1000:.0f} mm)"
                        for name, distance in touch.items() if distance > touch_limit)
    head_results = head_visibility(scene, root, head, frusta, settings) if head else [None] * len(frusta)
    configurations = []
    fov_range = []
    for index, frustum in enumerate(frusta):
        label = f"{frustum['vertical_fov_degrees']:.2f} deg vertical, {frustum['aspect']}"
        reasons = []
        if reticle_hits[index]:
            reasons.append(f"reticle blocked by {sorted(reticle_hits[index])[:4]} (first frame "
                           f"{min(reticle_frames[index].values())})")
        for name, margin in hand_margin[index].items():
            if margin < limits["hand_margin"]:
                reasons.append(f"{name} leaves the frame (margin {margin:.4f}, frame {hand_worst_frame[index][name]}, "
                               f"rest {rest_hand_margin[index][name]:.4f})")
        for name, value in proximal[index].items():
            if value >= 0:
                reasons.append(f"proximal forearm of {name} enters the viewport (y {value:.4f}, worst frame {proximal_worst_frame[name]})")
        result = head_results[index]
        if head:
            if result["anchor_margin"] < head_limits["head_anchor_margin"]:
                reasons.append(f"{head['anchor']} too close to the frame edge ({result['anchor_margin']:.4f})")
            if result["unoccluded_on_screen_fraction"] < head_limits["head_min_unoccluded_fraction"]:
                reasons.append(f"tool head occluded ({result['unoccluded_on_screen_fraction']:.3f})")
            if result["screen_fraction"] < head_limits["head_min_screen_fraction"]:
                reasons.append(f"tool head too small on screen ({result['screen_fraction']:.4f})")
        entry = {"vertical_fov_degrees": frustum["vertical_fov_degrees"], "aspect": frustum["aspect"],
                 "horizontal_fov_degrees": math.degrees(2 * math.atan(frustum["tan_h"])), "binding": frustum["binding"],
                 "ok": not reasons, "reasons": reasons,
                 "min_hand_margin": hand_margin[index], "worst_hand_frame": hand_worst_frame[index],
                 "rest_hand_margin": rest_hand_margin[index],
                 "hand_edge_margins": {name: dict(zip(("left", "right", "bottom", "top"), values)) for name, values in hand_edges[index].items()},
                 "proximal_forearm_max_screen_y": proximal[index],
                 "reticle_blocked_by": sorted(reticle_hits[index]), "head": result}
        configurations.append(entry)
        fov_range.append({"vertical_fov_degrees": round(frustum["vertical_fov_degrees"], 3), "aspect": frustum["aspect"],
                          "binding": frustum["binding"], "ok": not reasons, "reasons": reasons})
        if frustum["binding"]:
            failures.extend(f"{label}: {reason}" for reason in reasons)
    # Measured in the reference frustum (configured FOV and aspect), binding like the configured framings.
    # The arm rule picks a forearm direction per frame; a jump between neighbouring clip frames would show as a twitch.
    failures.extend(f"forearm of {name} twitches: turn rate changes by {step:.1f} deg per frame (frame {frame})"
                    for name, (step, frame) in forearm_step.items() if step > FOREARM_TWITCH_LIMIT_DEGREES)
    failures.extend(f"proximal forearm of {name} enters the viewport at {GAME_ENLARGEMENT_MAX}x (y {value:.4f})"
                    for name, value in proximal_enlarged.items() if value >= 0)
    binding = [index for index, frustum in enumerate(frusta) if frustum["binding"]]
    summary = {"vertical_fov_degrees": settings["vertical_fov_degrees"], "aspects": settings["qa_aspects"],
               "binding_configurations": len(binding),
               "min_hand_margin": min(value for index in binding for value in hand_margin[index].values()),
               "proximal_forearm_max_screen_y": max(value for index in binding for value in proximal[index].values()),
               "reticle_clear": not any(reticle_hits[index] for index in binding), "passed": not failures,
               "range_vertical_fov_degrees": [frusta[0]["vertical_fov_degrees"], frusta[-1]["vertical_fov_degrees"]],
               "range_ok": sum(item["ok"] for item in fov_range), "range_checked": len(fov_range)}
    head_summary = None
    if head:
        values = [head_results[index] for index in binding]
        head_summary = {"anchor": head["anchor"], "parts": values[0]["parts"], "samples": values[0]["samples"],
                        "min_anchor_margin": min(item["anchor_margin"] for item in values),
                        "min_unoccluded_on_screen_fraction": min(item["unoccluded_on_screen_fraction"] for item in values),
                        "min_screen_fraction": min(item["screen_fraction"] for item in values),
                        "main_occluders": values[0]["main_occluders"],
                        "limits": {"anchor_margin": head_limits["head_anchor_margin"],
                                   "unoccluded_fraction": head_limits["head_min_unoccluded_fraction"],
                                   "screen_fraction": head_limits["head_min_screen_fraction"]}}
    scene.frame_set(1); bpy.context.view_layer.update()
    report = {"passed": not failures, "failures": failures, "frames_checked": len(clip_check["frames"]),
              "ego_clip_boundary_max_error": max(boundary_errors.values(), default=0.0),
              "support_forearm_visible_max_screen_y": exempt_forearm or None,
              "ego_forearm_max_twitch_degrees": {name: {"degrees": round(step, 3), "frame": frame}
                                               for name, (step, frame) in forearm_step.items()},
              "max_contact_error_m": max_contact,
              "viewmodel_camera": {key: value for key, value in settings.items() if key != "qa"},
              "framing_range": {"summary": summary, "limits": limits, "configurations": configurations},
              "fov_range": fov_range,
              "hands_in_frame": summary["min_hand_margin"] >= limits["hand_margin"],
              "head": head_summary,
              "centered_wrist_max_error_m": centered_wrist_error, "bow_grip_draw_shift_m": bow_shift,
              "bow_draw_rotation_degrees": bow_rotation,
              "max_arm_link_error_m": maximum_arm_error, "rigid_arm_links": len(arms) * 2,
              "visible_forearm_vertex_extents": visible_forearms, "proximal_forearm_max_screen_y": proximal_base,
              "proximal_forearm_max_screen_y_enlarged": {"enlargement": GAME_ENLARGEMENT_MAX, "about": "Socket_Hand",
                                                         "values": proximal_enlarged},
              "proximal_forearm_offscreen": summary["proximal_forearm_max_screen_y"] < 0,
              "visible_forearm_fraction_limit": max(rig["visible_fraction"] for rig in arms),
              "finger_count_per_hand": GRIPPING_FINGERS + 1, "gripping_fingers_per_hand": GRIPPING_FINGERS,
              "thumb_count_per_hand": 1, "handedness_checked": tool == "bow",
              "min_hand_side_clearance_m": minimum_hand_side_clearance if tool == "bow" else None,
              "hand_touch_m": touch, "hand_touch_limit_m": touch_limit,
              "min_camera_depth_m": minimum_depth, "reticle_clear": summary["reticle_clear"], "max_reset_matrix_error": maximum_reset,
              "poses": poses, "fps": 24, "autoplay": False, "loop": False}
    return report


def refresh_geometry(directory, root, profile, report, settings):
    path = directory / "qa_geometry_fps.json"
    qa = json.loads(path.read_text())
    meshes = [obj for obj in root.children_recursive if obj.type == "MESH"]
    coordinates = [obj.matrix_world @ vertex.co for obj in meshes for vertex in obj.data.vertices]
    qa["bounds_m"] = [[min(v[i] for v in coordinates) for i in range(3)], [max(v[i] for v in coordinates) for i in range(3)]]
    qa["dimensions_m"] = [qa["bounds_m"][1][i] - qa["bounds_m"][0][i] for i in range(3)]
    qa["enlargement"] *= profile.get("tool_scale", 1)
    qa["meshes"] = len(meshes); qa["triangles"] = 0
    for obj in meshes:
        obj.data.calc_loop_triangles(); qa["triangles"] += len(obj.data.loop_triangles)
    qa["sockets"] = {obj.name: list(obj.matrix_world.translation) for obj in root.children_recursive if obj.name.startswith("Socket_")}
    qa["camera"]["hand_position_blender_m"] = profile["hand"]
    qa["camera"]["hand_position_unity_m"] = [profile["hand"][0], profile["hand"][2], -profile["hand"][1]]
    qa["camera"]["roll_degrees"] = profile["roll_degrees"]
    qa["camera"]["aim_target_blender_m"] = list(profile.get("aim_target_m", (0, -4, 0)))
    qa["camera"].pop("horizontal_fov_degrees", None)
    qa["camera"].update(vertical_fov_degrees=settings["vertical_fov_degrees"],
                        horizontal_fov_degrees=settings["horizontal_fov_degrees"],
                        reference_aspect=settings["reference_aspect"], near_m=settings["near_clip_m"])
    qa["framing"] = {"min_camera_depth_m": report["min_camera_depth_m"], "reticle_clear": True,
                     "hands_in_frame": report["hands_in_frame"], "head_visible": report["head"] is not None,
                     "checked_range": report["framing_range"]["summary"],
                     "render_resolution": [1600, 900], "robot_hands": report["hand_sides"]}
    path.write_text(json.dumps(qa, indent=2) + "\n")


def refresh_motion(directory, scene):
    path = directory / "qa_animation_fps.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    for frame, pose in data["poses"].items():
        scene.frame_set(int(frame)); bpy.context.view_layer.update()
        matrices = pose.get("matrices", pose)
        for name in matrices:
            matrices[name] = matrix_rows(scene.objects[name])
        if "mesh_bounds" in pose:
            graph = bpy.context.evaluated_depsgraph_get()
            for name in pose["mesh_bounds"]:
                pose["mesh_bounds"][name] = bounds(scene.objects[name], graph)
    scene.frame_set(1); bpy.context.view_layer.update()
    path.write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--tool", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    specs = json.loads((ROOT / "data/tools.json").read_text())["tools"]
    profiles = json.loads((ROOT / "data/viewmodels.json").read_text())["tools"]
    build(args.directory, next(spec for spec in specs if spec["id"] == args.tool), profiles[args.tool])
