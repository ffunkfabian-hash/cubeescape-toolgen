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
from motion_profiles import draw_hand_offset, envelope, settle, solve_elbow


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


def link(name, parent, first, last, width, depth, mat):
    first, last = Vector(first), Vector(last)
    delta = last - first
    rotation = Vector((0, 0, 1)).rotation_difference(delta.normalized())
    return box(name, parent, (first + last) / 2, (width, depth, delta.length), mat, rotation)


GRIPPING_FINGERS = 3
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
    if tool == "bow":
        nock = scene.objects["Socket_Nock"]
        draw_pose = nock.matrix_world @ twists["R"]
        draw, fingers, draw_contact, rig = hand("R", motion, draw_pose, shoulders["R"], (.012, .015), mats, proportions, pinch=True)
        hands.append(draw); arms.append(rig); contact_targets[draw_contact.name] = "Socket_Nock"
    elif profile["support"]:
        support_pose = pose @ Matrix.Translation(profile["support_offset"])
        # Turning the support hand about the barrel keeps its fingers off the tool head.
        support_pose = support_pose @ Matrix.Rotation(math.radians(profile.get("support_roll_degrees", 0)), 4, "Y")
        support_pose = support_pose @ Matrix(((0, -1, 0, 0), (0, 0, 1, 0), (-1, 0, 0, 0), (0, 0, 0, 1)))
        support, _, _, rig = hand("L", motion, support_pose, shoulders["L"], (.086, .085), mats, proportions)
        hands.append(support); arms.append(rig)
    rest = {obj: obj.matrix_world.copy() for obj in hands}
    scene.render.fps = 24; scene.frame_start = 1; scene.frame_end = 97
    clip = spec.get("fps_clip") or spec["clip"]
    root["ce_action_clip"] = clip; root["ce_autoplay"] = False; root["ce_loop"] = False
    root["ce_hand_style"] = "Robogen Mitt / articulated FPS, three fingers and thumb"
    # Exported as glTF extras / FBX user properties so the game can adopt the viewmodel camera.
    root["ce_viewmodel_vertical_fov_degrees"] = settings["vertical_fov_degrees"]
    root["ce_viewmodel_horizontal_fov_degrees"] = settings["horizontal_fov_degrees"][settings["reference_aspect"]]
    root["ce_viewmodel_reference_aspect"] = settings["reference_aspect"]
    root["ce_viewmodel_near_clip_m"] = settings["near_clip_m"]
    for frame in range(1, 98):
        scene.frame_set(frame)
        motion.location = (0, 0, 0); motion.rotation_euler = (0, 0, 0)
        if tool == "bow":
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
        else:
            pressure = envelope(frame, ((1, 0), (14, 1), (45, 1), (73, 0), (97, 0)))
            kick = settle(frame, 14, 28, 1)
            motion.location = (0, -.012 * pressure + .010 * kick, .016 * pressure)
            motion.rotation_euler = (math.radians(1.5) * pressure, math.radians(.9) * kick, 0)
        motion.keyframe_insert(data_path="location", frame=frame)
        motion.keyframe_insert(data_path="rotation_euler", frame=frame)
        bpy.context.view_layer.update()
        if tool == "bow":
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
    for obj in [motion, *hands, *(node for rig in arms for node in (rig["upper"], rig["lower"])), *(obj for obj in root.children_recursive if obj.name.startswith("Fingers_"))]:
        finish_keys(obj)
    scene.frame_set(1); bpy.context.view_layer.update()
    # Grip hand remains rigidly attached to the tool throughout the clip.
    assert (main.matrix_world.translation - socket.matrix_world.translation).length < 1e-5
    report = validate(scene, root, contact_targets, tool, arms, settings, profile.get("head"))
    report["robogen_reference"] = config["reference"]
    report["clip"] = clip; report["hand_sides"] = [obj.name for obj in hands]
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
    print(f"VIEWMODEL_OK {tool}: {len(hands)} hands, 97 frames, contact={report['max_contact_error_m']:.8f} m, "
          f"FOV {settings['vertical_fov_degrees']:.2f} deg vertical, {summary['binding_configurations']} binding framings, "
          f"range {summary['range_ok']}/{summary['range_checked']} ok, hand margin {summary['min_hand_margin']:.4f}, head {json.dumps(report['head'])}")


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


def camera_document(tool, settings, report):
    """Small, game-facing summary of the viewmodel camera next to the exports."""
    return {"format": 1, "tool": tool, "vertical_fov_degrees": settings["vertical_fov_degrees"],
            "horizontal_fov_degrees": settings["horizontal_fov_degrees"],
            "reference_aspect": settings["reference_aspect"], "near_clip_m": settings["near_clip_m"],
            "override": settings["override"], "unity": settings["unity"],
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


def validate(scene, root, targets, tool, arms, settings, head):
    limits = settings["qa"]
    frusta = frustum_configurations(settings)
    tan_v = math.tan(math.radians(settings["vertical_fov_degrees"]) / 2)
    base = {"tan_h": tan_v * aspect_ratio(settings["reference_aspect"]), "tan_v": tan_v}
    reticle = limits["reticle_half_extent"]
    near = settings["near_clip_m"]
    failures = []
    max_contact = 0; minimum_depth = float("inf")
    maximum_arm_error = 0
    minimum_hand_side_clearance = float("inf")
    visible_forearms = {rig["hand"].name: 0 for rig in arms}
    proximal = [{rig["hand"].name: -float("inf") for rig in arms} for _ in frusta]
    proximal_base = {rig["hand"].name: -float("inf") for rig in arms}
    hand_margin = [{rig["hand"].name: float("inf") for rig in arms} for _ in frusta]
    hand_worst_frame = [{rig["hand"].name: None for rig in arms} for _ in frusta]
    hand_edges = [{rig["hand"].name: [float("inf")] * 4 for rig in arms} for _ in frusta]
    rest_hand_margin = [{rig["hand"].name: float("inf") for rig in arms} for _ in frusta]
    reticle_hits = [set() for _ in frusta]
    hand_meshes = {rig["hand"].name: {obj.name for obj in rig["hand"].children_recursive if obj.type == "MESH"} for rig in arms}
    tracking = [obj for obj in root.children_recursive if obj.type == "EMPTY" and
                (obj.name.startswith(("Hand_", "GripContact_", "UpperArm_", "LowerArm_", "Thumb_", "Fingers_")) or obj.name == "Viewmodel_Motion")]
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
    for frame in range(1, 98):
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
            length = rig["lengths"][1]
            matrix = np.array(rig["lower"].matrix_world)
            # A conservative box encloses the entire proximal half, including faces
            # which cross the viewport even when their vertices lie outside it.
            corners = np.array([(x, y, z) for z in (0, length * (1 - rig["visible_fraction"]))
                                for x in (-.047, .047) for y in (-.047, .047)])
            u, v, _ = camera_space(corners @ matrix[:3, :3].T + matrix[:3, 3])
            for index, frustum in enumerate(frusta):
                proximal[index][name] = max(proximal[index][name], float(screen(u, v, frustum)[1].max()))
            proximal_base[name] = max(proximal_base[name], float(screen(u, v, base)[1].max()))
            for local in forearm_local.get(name, ()):
                u, v, depth = camera_space(local @ matrix[:3, :3].T + matrix[:3, 3])
                x, y = screen(u, v, base)
                inside = (x >= 0) & (x <= 1) & (y >= 0) & (y <= 1) & (depth > near)
                if inside.any():
                    visible_forearms[name] = max(visible_forearms[name], float((1 - local[inside, 2] / length).max()))
        for contact_name, target in targets.items():
            if tool == "bow" and target == "Socket_Nock" and 43 < frame < 79:
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
            if owner == "Hand_R" and tool == "bow" and frame not in (1, 97):
                owner = None
            for index, frustum in enumerate(frusta):
                x, y = screen(u, v, frustum)
                if ((np.abs(x - .5) < reticle) & (np.abs(y - .5) < reticle)).any():
                    reticle_hits[index].add(obj.name)
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
        if frame in (1, 16, 31, 43, 44, 48, 60, 79, 97):
            poses[str(frame)] = current
    maximum_reset = max(abs(current[name][i][j] - matrix[i][j]) for name, matrix in rest.items() for i in range(4) for j in range(4))
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
    head_results = head_visibility(scene, root, head, frusta, settings) if head else [None] * len(frusta)
    configurations = []
    fov_range = []
    for index, frustum in enumerate(frusta):
        label = f"{frustum['vertical_fov_degrees']:.2f} deg vertical, {frustum['aspect']}"
        reasons = []
        if reticle_hits[index]:
            reasons.append(f"reticle blocked by {sorted(reticle_hits[index])[:4]}")
        for name, margin in hand_margin[index].items():
            if margin < limits["hand_margin"]:
                reasons.append(f"{name} leaves the frame (margin {margin:.4f}, frame {hand_worst_frame[index][name]}, "
                               f"rest {rest_hand_margin[index][name]:.4f})")
        for name, value in proximal[index].items():
            if value >= 0:
                reasons.append(f"proximal forearm of {name} enters the viewport (y {value:.4f})")
        result = head_results[index]
        if head:
            if result["anchor_margin"] < limits["head_anchor_margin"]:
                reasons.append(f"{head['anchor']} too close to the frame edge ({result['anchor_margin']:.4f})")
            if result["unoccluded_on_screen_fraction"] < limits["head_min_unoccluded_fraction"]:
                reasons.append(f"tool head occluded ({result['unoccluded_on_screen_fraction']:.3f})")
            if result["screen_fraction"] < limits["head_min_screen_fraction"]:
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
                        "limits": {"anchor_margin": limits["head_anchor_margin"],
                                   "unoccluded_fraction": limits["head_min_unoccluded_fraction"],
                                   "screen_fraction": limits["head_min_screen_fraction"]}}
    scene.frame_set(1); bpy.context.view_layer.update()
    report = {"passed": not failures, "failures": failures, "frames_checked": 97, "max_contact_error_m": max_contact,
              "viewmodel_camera": {key: value for key, value in settings.items() if key != "qa"},
              "framing_range": {"summary": summary, "limits": limits, "configurations": configurations},
              "fov_range": fov_range,
              "hands_in_frame": summary["min_hand_margin"] >= limits["hand_margin"],
              "head": head_summary,
              "centered_wrist_max_error_m": centered_wrist_error, "bow_grip_draw_shift_m": bow_shift,
              "bow_draw_rotation_degrees": bow_rotation,
              "max_arm_link_error_m": maximum_arm_error, "rigid_arm_links": len(arms) * 2,
              "visible_forearm_vertex_extents": visible_forearms, "proximal_forearm_max_screen_y": proximal_base,
              "proximal_forearm_offscreen": summary["proximal_forearm_max_screen_y"] < 0,
              "visible_forearm_fraction_limit": max(rig["visible_fraction"] for rig in arms),
              "finger_count_per_hand": GRIPPING_FINGERS + 1, "gripping_fingers_per_hand": GRIPPING_FINGERS,
              "thumb_count_per_hand": 1, "handedness_checked": tool == "bow",
              "min_hand_side_clearance_m": minimum_hand_side_clearance if tool == "bow" else None,
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
