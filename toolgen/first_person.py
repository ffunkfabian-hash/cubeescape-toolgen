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
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
from motion_profiles import draw_hand_offset, envelope, settle, solve_elbow


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


def hand(side, parent, pose, shoulder, radius, mats, proportions, pinch=False):
    """Two gripping fingers and one opposing thumb: three digits total, centered wrist."""
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
    for index, height in enumerate((.023, -.023)):
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
            link(f"Finger_{side}_{index}_{segment}", finger, a, b, .023, .024, mats["dark"])
        box(f"KnuckleArmor_{side}_{index}", finger, Vector(points[0]) + Vector((sign * .009, .002, 0)),
            (.013, .025, .025), mats["white"], bevel=.004)
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
    original = socket.matrix_world.copy()
    local_muzzle = original.inverted() @ scene.objects["Socket_Muzzle"].matrix_world.translation
    position = Vector(profile["hand"]); target = Vector((0, -4, 0))
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
    proportions = json.loads((ROOT / "data/viewmodels.json").read_text())["arm"]
    shoulders = proportions["shoulders"]
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
        support_pose = support_pose @ Matrix(((0, -1, 0, 0), (0, 0, 1, 0), (-1, 0, 0, 0), (0, 0, 0, 1)))
        support, _, _, rig = hand("L", motion, support_pose, shoulders["L"], (.086, .085), mats, proportions)
        hands.append(support); arms.append(rig)
    rest = {obj: obj.matrix_world.copy() for obj in hands}
    scene.render.fps = 24; scene.frame_start = 1; scene.frame_end = 97
    clip = spec.get("fps_clip") or spec["clip"]
    root["ce_action_clip"] = clip; root["ce_autoplay"] = False; root["ce_loop"] = False
    root["ce_hand_style"] = "Robogen Mitt / articulated FPS"
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
    report = validate(scene, root, contact_targets, tool, arms)
    report["robogen_reference"] = json.loads((ROOT / "data/viewmodels.json").read_text())["reference"]
    report["clip"] = clip; report["hand_sides"] = [obj.name for obj in hands]
    for obj, matrix in rest.items():
        assert max(abs(obj.matrix_world[i][j] - matrix[i][j]) for i in range(4) for j in range(4)) < 1e-5, obj.name
    (directory / "qa_viewmodel.json").write_text(json.dumps(report, indent=2) + "\n")
    refresh_geometry(directory, root, profile, report)
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
    print(f"VIEWMODEL_OK {tool}: {len(hands)} hands, 97 frames, contact={report['max_contact_error_m']:.8f} m")


def validate(scene, root, targets, tool, arms):
    max_contact = 0; minimum_depth = float("inf")
    maximum_arm_error = 0
    minimum_hand_side_clearance = float("inf")
    visible_forearms = {rig["hand"].name: 0 for rig in arms}
    proximal_screen_y = {rig["hand"].name: -float("inf") for rig in arms}
    tracking = [obj for obj in root.children_recursive if obj.type == "EMPTY" and
                (obj.name.startswith(("Hand_", "GripContact_", "UpperArm_", "LowerArm_", "Thumb_", "Fingers_")) or obj.name == "Viewmodel_Motion")]
    poses = {}
    rest = None
    grip_rest = None
    grip_draw = None
    centered_wrist_error = 0
    camera = scene.camera
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
            length = rig["lengths"][1]
            # A conservative box encloses the entire proximal half, including faces
            # which cross the viewport even when their vertices lie outside it.
            for z in (0, length * (1 - rig["visible_fraction"])):
                for x in (-.047, .047):
                    for y in (-.047, .047):
                        point = world_to_camera_view(scene, camera, rig["lower"].matrix_world @ Vector((x, y, z)))
                        proximal_screen_y[rig["hand"].name] = max(proximal_screen_y[rig["hand"].name], point.y)
            for obj in rig["lower"].children:
                if obj.type != "MESH":
                    continue
                for vertex in obj.data.vertices:
                    local = obj.matrix_local @ vertex.co
                    point = world_to_camera_view(scene, camera, rig["lower"].matrix_world @ local)
                    if 0 <= point.x <= 1 and 0 <= point.y <= 1 and point.z > .03:
                        visible_forearms[rig["hand"].name] = max(visible_forearms[rig["hand"].name], 1 - local.z / length)
        for contact_name, target in targets.items():
            if tool == "bow" and target == "Socket_Nock" and 43 < frame < 79:
                continue
            error = (scene.objects[contact_name].matrix_world.translation - scene.objects[target].matrix_world.translation).length
            assert error < .0001, (tool, frame, contact_name, "hand detached", error)
            max_contact = max(max_contact, error)
        for obj in root.children_recursive:
            if obj.type != "MESH":
                continue
            evaluated = obj.evaluated_get(graph)
            for vertex in evaluated.data.vertices:
                point = world_to_camera_view(scene, camera, evaluated.matrix_world @ vertex.co)
                assert point.z > .03, (tool, frame, obj.name, "near clip", point.z)
                assert not (.47 < point.x < .53 and .47 < point.y < .53), (tool, frame, obj.name, "reticle blocked")
                minimum_depth = min(minimum_depth, point.z)
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
    assert all(value < 0 for value in proximal_screen_y.values()), (tool, "proximal forearm enters viewport", proximal_screen_y)
    assert not any(obj.type == "MESH" and obj.get("ce_role") == "first_person_robot" and obj.name.startswith(("SM_FPS_UpperArm", "SM_FPS_Elbow")) for obj in root.children_recursive)
    for rig in arms:
        side = rig["hand"].name[-1]
        assert all(scene.objects.get(f"Fingers_{side}_{index}") is not None for index in range(2))
        assert scene.objects.get(f"Fingers_{side}_2") is None
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
    scene.frame_set(1); bpy.context.view_layer.update()
    return {"passed": True, "frames_checked": 97, "max_contact_error_m": max_contact,
            "centered_wrist_max_error_m": centered_wrist_error, "bow_grip_draw_shift_m": bow_shift,
            "bow_draw_rotation_degrees": bow_rotation,
            "max_arm_link_error_m": maximum_arm_error, "rigid_arm_links": len(arms) * 2,
            "visible_forearm_vertex_extents": visible_forearms, "proximal_forearm_max_screen_y": proximal_screen_y,
            "proximal_forearm_offscreen": True, "visible_forearm_fraction_limit": max(rig["visible_fraction"] for rig in arms),
            "finger_count_per_hand": 3, "gripping_fingers_per_hand": 2, "thumb_count_per_hand": 1, "handedness_checked": tool == "bow",
            "min_hand_side_clearance_m": minimum_hand_side_clearance if tool == "bow" else None,
            "min_camera_depth_m": minimum_depth, "reticle_clear": True, "max_reset_matrix_error": maximum_reset,
            "poses": poses, "fps": 24, "autoplay": False, "loop": False}


def refresh_geometry(directory, root, profile, report):
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
    qa["framing"] = {"min_camera_depth_m": report["min_camera_depth_m"], "reticle_clear": True,
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
