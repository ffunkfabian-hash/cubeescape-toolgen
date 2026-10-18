#!/usr/bin/env python3
"""Look check of the robot variant without Unity (Toolgen 0.14 Fieldfit): ``<output>/Previews/robot_variant.png`` and
``robot_contact.png``.

    blender --background --factory-startup --python scripts/robot_preview.py -- <output> [--tool assault_rifle ...]

* ``robot_variant.png``: per weapon the robot variant from its right side next to a reference of Cube Escape's robot
  (measured in Cube Escape 0.82: shoulder joint 0.82 m above the floor, chest front 0.18 m ahead of the body centre, arm
  0.42 m, fist 0.09 m): torso, shoulder, the arm, a 0.42 m arm-length bar and translucent fists of 0.09 m at Socket_Hand and
  Socket_SupportHand. Assumed pose for the picture only: the bore 0.06 m below the shoulder joint, the stock end 0.06 m behind
  the chest front (CE 0.82 finding: 4-9 cm, at the shoulder). The fit on the real robot is Cube Escape's check
  (HeldWeaponReelTests), not this sheet.
* ``robot_contact.png``: per weapon the life-size world model at Cube Escape 0.82's heldScale (what the robot held so far)
  against the robot variant at heldScale 1.0, side, top and back, at one scale for all panels.

Renders the authored models (``<asset>.blend``, ``<robot>.blend``) with Eevee; preview only, not part of any contract.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
import decals  # noqa: E402 - ImageMagick lookup shared with the decal pipeline

# Cube Escape 0.82 "Sidearm" Docs/EQUIPMENT.md: heldScale of the life-size world models in the robot's hand.
CE_HELD_SCALE = {"smg": .85, "assault_rifle": .72, "pulse_rifle": .76, "shotgun": .74, "fusion_rifle": .70, "scout_rifle": .66,
                 "sniper_rifle": .64, "rocket_launcher": .90}
SHOULDER_Z, CHEST_FRONT, ARM, FIST = .82, -.18, .42, .09
BORE_BELOW_SHOULDER, STOCK_INTO_CHEST = .06, .06
BACKGROUND = (.012, .016, .024, 1)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = BACKGROUND
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.4
    scene.world = world
    for rotation, energy in (((50, 10, 35), 3.0), ((60, 0, 200), 1.4), ((-40, 0, 90), 1.0)):
        light = bpy.data.objects.new("PreviewSun", bpy.data.lights.new("PreviewSun", "SUN"))
        light.data.energy = energy
        light.data.use_shadow = False          # no weapon shadow on the reference torso
        light.rotation_euler = tuple(math.radians(v) for v in rotation)
        scene.collection.objects.link(light)
    return scene


def append_model(blend, root_name, scene):
    """Append the model's root and its children (meshes and empties) into ``scene``; returns the root."""
    with bpy.data.libraries.load(str(blend), link=False) as (source, target):
        target.objects = list(source.objects)
    found = [obj for obj in target.objects if obj is not None]
    root = next(obj for obj in found if obj.name.split(".")[0] == root_name and obj.type == "EMPTY")
    keep = {root, *root.children_recursive}
    for obj in found:
        if obj in keep:
            scene.collection.objects.link(obj)
        else:
            bpy.data.objects.remove(obj)
    scene.frame_set(1)
    return root


def socket(root, name):
    return next(obj for obj in root.children_recursive if obj.name.split(".")[0] == name).matrix_world.translation.copy()


def material(name, rgba, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = .7
    bsdf.inputs["Alpha"].default_value = alpha
    if alpha < 1:
        mat.surface_render_method = "BLENDED"
    mat.diffuse_color = rgba
    return mat


def box(scene, name, center, size, mat):
    mesh = bpy.data.meshes.new(name)
    x, y, z = (v / 2 for v in size)
    verts = [(sx * x, sy * y, sz * z) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = center
    scene.collection.objects.link(obj)
    return obj


def bar(scene, name, start, end, thickness, mat):
    """A square rod from ``start`` to ``end``."""
    start, end = Vector(start), Vector(end)
    obj = box(scene, name, (start + end) / 2, (thickness, thickness, (end - start).length), mat)
    obj.rotation_euler = Vector((0, 0, 1)).rotation_difference(end - start).to_euler()
    return obj


def camera_view(scene, center, direction, ortho, size, path, roll=None):
    data = bpy.data.cameras.new("PreviewCamera")
    data.type = "ORTHO"
    data.ortho_scale = ortho
    data.clip_end = 50
    camera = bpy.data.objects.new("PreviewCamera", data)
    scene.collection.objects.link(camera)
    camera.location = Vector(center) + Vector(direction).normalized() * 5
    camera.rotation_euler = (Vector(center) - camera.location).to_track_quat("-Z", "Y").to_euler()
    if roll is not None:                       # top view: muzzle (-Y) to the left like the side view
        camera.rotation_euler = (0, 0, math.radians(roll))
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(camera)


def reference_panel(folder, tool, path):
    """The robot variant in the hand of the reference robot, seen from its right side (+X)."""
    scene = reset_scene()
    root = append_model(folder / (tool["robot"] + ".blend"), tool["robot"], scene)
    fit = json.loads((folder / "qa_geometry_robot.json").read_text())["robot"]
    muzzle = socket(root, "Socket_Muzzle")
    stock = fit["measures"]["stock_behind_hand_m"]
    hand = Vector((0, CHEST_FRONT + STOCK_INTO_CHEST - stock, SHOULDER_Z - BORE_BELOW_SHOULDER - muzzle.z))
    root.location = hand
    bpy.context.view_layer.update()
    grip, support = socket(root, "Socket_Hand"), socket(root, "Socket_SupportHand")
    body = material("RefBody", (.10, .15, .22, 1))
    arm = material("RefArm", (.45, .55, .65, 1))
    joint = material("RefJoint", (.95, .75, .25, 1))
    fist = material("RefFist", (1, .55, .15, 1), .35)
    scale = material("RefScale", (.55, .85, 1, 1))
    # behind the weapon plane (x < 0): torso from the hip to the shoulders, shoulder joint, arm to the grip hand
    box(scene, "RefTorso", (-.30, (CHEST_FRONT + .16) / 2, .70), (.3, .16 - CHEST_FRONT, .56), body)
    box(scene, "RefChestFront", (-.14, CHEST_FRONT, .70), (.01, .006, .62), joint)
    box(scene, "RefShoulder", (-.10, 0, SHOULDER_Z), (.07, .07, .07), joint)
    bar(scene, "RefArm", (-.10, 0, SHOULDER_Z), (-.10, grip.y, grip.z), .045, arm)
    bar(scene, "RefArmLength", (-.10, CHEST_FRONT - .05, .40), (-.10, CHEST_FRONT - .05 - ARM, .40), .012, scale)
    for x in (CHEST_FRONT - .05, CHEST_FRONT - .05 - ARM):
        box(scene, "RefArmTick", (-.10, x, .40), (.012, .006, .04), scale)
    box(scene, "RefShoulderHeight", (-.10, .20, SHOULDER_Z / 2), (.012, .012, SHOULDER_Z), scale)
    box(scene, "RefFloor", (-.10, -.30, 0), (.012, 1.2, .006), scale)
    for name, point in (("RefFistGrip", grip), ("RefFistSupport", support)):
        box(scene, name, point, (FIST, FIST, FIST), fist)
    center = (0, -.33, .58)
    camera_view(scene, center, (1, 0, 0), 1.25, (960, 720), path)
    return fit


def model_views(blend, root_name, scale, prefix, ortho):
    scene = reset_scene()
    root = append_model(blend, root_name, scene)
    root.scale = (scale, scale, scale)
    bpy.context.view_layer.update()
    paths = []
    for view, direction, size, factor, roll in (("side", (1, 0, 0), (480, 300), 1.0, None),
                                                ("top", (0, 0, 1), (480, 300), 1.0, 90),
                                                ("back", (0, 1, 0), (300, 300), .62, None)):
        path = Path(f"{prefix}_{view}.png")
        camera_view(scene, (0, -.22, .03), direction, ortho * factor, size, path, roll)
        paths.append(path)
    return paths


def magick_run(magick, arguments):
    subprocess.run(magick + arguments, check=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    output = Path(argv[0]).resolve()
    wanted = [argv[i + 1] for i, value in enumerate(argv) if value == "--tool"]
    tools = [entry for entry in json.loads((ROOT / "data/tools.json").read_text())["tools"] if entry.get("robot")]
    previews = output / "Previews"
    scratch = previews / "_robot"
    scratch.mkdir(parents=True, exist_ok=True)
    magick = decals.magick_command()
    references, rows = [], []
    for tool in tools:
        folder = output / tool["id"]
        if wanted and tool["id"] not in wanted:
            continue
        if not (folder / (tool["robot"] + ".blend")).exists():
            print(f"ROBOT_PREVIEW_SKIP {tool['id']}: no robot variant (contract 4 packages only)")
            continue
        panel = scratch / f"{tool['id']}_reference.png"
        fit = reference_panel(folder, tool, panel)
        m = fit["measures"]
        label = (f"{tool['label']}  {m['length_m']:.2f} m, Schaft {m['stock_behind_hand_m']:.2f} m hinter, Stützhand "
                 f"{m['support_ahead_of_hand_m']:.2f} m vor Socket_Hand ({fit['support_part']}), Lauf {m['barrel_diameter_m'] * 100:.1f} cm, "
                 f"Gehäuse {m['body_height_m'] * 100:.1f} cm")
        magick_run(magick, [str(panel), "-gravity", "North", "-background", "#10131a", "-splice", "0x30", "-fill", "#e8e8e8",
                            "-pointsize", "17", "-annotate", "+0+6", label, "-define", "png:exclude-chunks=date,time",
                            str(panel)])
        references.append(panel)
        life = model_views(folder / (tool["asset"] + ".blend"), tool["asset"], CE_HELD_SCALE[tool["id"]],
                           scratch / f"{tool['id']}_life", .85)
        robot = model_views(folder / (tool["robot"] + ".blend"), tool["robot"], 1.0, scratch / f"{tool['id']}_robot", .85)
        row = scratch / f"{tool['id']}_row.png"
        magick_run(magick, [*(str(p) for pair in zip(life, robot) for p in pair), "+append", "-gravity", "West",
                            "-background", "#10131a", "-splice", "190x0", "-fill", "#e8e8e8", "-pointsize", "18",
                            "-annotate", "+8+0", f"{tool['label']}\nalt x{CE_HELD_SCALE[tool['id']]:.2f} | Roboter x1.0",
                            "-define", "png:exclude-chunks=date,time", str(row)])
        rows.append(row)
        print(f"ROBOT_PREVIEW_OK {tool['id']}")
    if references:
        sheet = previews / "robot_variant.png"
        legend = ("Roboter-Referenz (CE 0.82): Schultergelenk 0,82 m (gelbes Quadrat, Höhenstab rechts), Brustfront 0,18 m vor "
                  "der Mitte (gelbe Linie), Arm (hell) zur Griffhand, Balken unten = Armlänge 0,42 m, Fäuste 0,09 m (orange) an "
                  "Socket_Hand/Socket_SupportHand. Haltung nur fürs Bild; die Passung prüft Cube Escape.")
        magick_run(magick, ["montage", *(str(p) for p in references), "-tile", "4x", "-geometry", "+4+4", "-background",
                            "#10131a", "-define", "png:exclude-chunks=date,time", str(sheet)])
        magick_run(magick, [str(sheet), "-gravity", "North", "-background", "#10131a", "-splice", "0x34", "-fill", "#e8e8e8",
                            "-pointsize", "20", "-annotate", "+0+8", legend, "-define", "png:exclude-chunks=date,time",
                            str(sheet)])
        print(f"ROBOT_PREVIEW_SHEET {sheet}")
        contact = previews / "robot_contact.png"
        header = ("Seite: alt | Roboter     Oben: alt | Roboter     Hinten: alt | Roboter   "
                  "(alt = Weltmodell mit heldScale aus CE 0.82, ein Maßstab für alle Felder)")
        magick_run(magick, [*(str(p) for p in rows), "-append", "+repage", "-gravity", "North", "-background", "#10131a", "-splice",
                            "0x30", "-fill", "#e8e8e8", "-pointsize", "18", "-annotate", "+0+6", header,
                            "-define", "png:exclude-chunks=date,time", str(contact)])
        print(f"ROBOT_PREVIEW_CONTACT {contact}")


if __name__ == "__main__":
    main()
