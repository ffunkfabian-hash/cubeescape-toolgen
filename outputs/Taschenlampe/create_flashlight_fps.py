"""Create the separate camera-mounted flashlight from the compact asset."""
import argparse
import json
import math
from pathlib import Path
import runpy
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Quaternion, Vector

NAME = 'CubeEscape_Flashlight_FPS'
ENLARGEMENT = 1.5
HAND_POSITION = Vector((-.26, -.66, -.50))
AIM_TARGET = Vector((0, -4, 0))
HORIZONTAL_FOV = 75
HELPER_PATH = Path(__file__).resolve().parents[1] / 'Portalkanone' / 'create_portal_gun.py'
HELPER = runpy.run_path(str(HELPER_PATH))
STATE = HELPER['validate'].__globals__


def depth(obj):
    count = 0
    while obj.parent:
        count += 1
        obj = obj.parent
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    out = args.output.resolve()
    source = out / 'CubeEscape_Flashlight.blend'
    if not source.is_file():
        raise RuntimeError('Build the compact flashlight first')
    (out / 'build_complete_fps.json').unlink(missing_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    original = bpy.context.scene
    source_root = original.objects['CubeEscape_Flashlight']
    source_objects = [source_root] + list(source_root.children_recursive)
    source_hand = original.objects['Socket_Hand'].matrix_world.translation.copy()
    aim_delta = AIM_TARGET - HAND_POSITION
    bore_height = (original.objects['Socket_Muzzle'].matrix_world.translation.z - source_hand.z) * ENLARGEMENT
    distance = math.sqrt(aim_delta.length_squared - bore_height * bore_height)
    rotation = aim_delta.to_track_quat('-Y', 'Z') @ Quaternion(
        Vector((1, 0, 0)), math.atan2(bore_height, distance))
    transform = (Matrix.Translation(HAND_POSITION) @ rotation.to_matrix().to_4x4()
                 @ Matrix.Scale(ENLARGEMENT, 4) @ Matrix.Translation(-source_hand))
    source_world = {obj: obj.matrix_world.copy() for obj in source_objects}
    scene = bpy.data.scenes.new(NAME)
    bpy.context.window.scene = scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    geo = bpy.data.collections.new('FL_FPS_GEOMETRY')
    scene.collection.children.link(geo)
    root = bpy.data.objects.new(NAME, None)
    geo.objects.link(root)
    root['ce_category'] = 'Interactive'
    root['ce_variant'] = 'first_person_large'
    root['ce_camera_attachment'] = 'origin, identity transform; forward -Y, up Z'
    root.empty_display_size = .05
    objects = [root]
    mapping = {source_root: root}
    for old in sorted((obj for obj in source_objects if obj != source_root), key=depth):
        new = old.copy()
        if old.type == 'MESH':
            new.data = old.data.copy()
            new.data.transform(Matrix.Scale(ENLARGEMENT, 4))
        geo.objects.link(new)
        mapping[old] = new
        new.parent = mapping[old.parent]
        location, quaternion, _scale = (transform @ source_world[old]).decompose()
        new.matrix_world = Matrix.LocRotScale(location, quaternion, Vector((1, 1, 1)))
        new.scale = (1, 1, 1)
        bpy.context.view_layer.update()
        objects.append(new)

    old_objects = list(original.objects)
    bpy.data.scenes.remove(original)
    for old in old_objects:
        if not old.users_scene:
            bpy.data.objects.remove(old, do_unlink=True)
    for old, new in list(mapping.items())[1:]:
        new.name = new.name.removesuffix('.001')
    socket = bpy.data.objects.new('Socket_Camera', None)
    geo.objects.link(socket)
    socket.parent = root
    socket.empty_display_size = .06
    objects.append(socket)

    STATE.update(ASSET=NAME, OBJECTS=objects, ROOT=root, GEO=geo)
    qa = HELPER['validate']()
    qa.update(variant='first_person_large', enlargement=ENLARGEMENT,
              tags=['tool', 'flashlight', 'handheld', 'robot-classic', 'white-shell', 'first-person-large'],
              pivot='camera attachment at origin; all export object scales are 1',
              integration='visual asset only; runtime light and input not included',
              camera={'horizontal_fov_degrees': HORIZONTAL_FOV, 'near_m': .03,
                      'hand_position_blender_m': list(HAND_POSITION),
                      'hand_position_unity_m': [HAND_POSITION.x, HAND_POSITION.z, -HAND_POSITION.y],
                      'aim_target_blender_m': list(AIM_TARGET),
                      'note': 'Camera offset and enlargement are baked; attach root with identity transform.'})

    camera, _target = HELPER['presentation'](scene)
    camera.location = (0, 0, 0)
    camera.rotation_euler = Vector((0, -1, 0)).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'PERSP'
    camera.data.sensor_fit = 'HORIZONTAL'
    camera.data.sensor_width = 36
    camera.data.lens = 36 / (2 * math.tan(math.radians(HORIZONTAL_FOV) / 2))
    camera.data.clip_start = .03
    camera.data.clip_end = 100
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900

    present = STATE['PRESENT']
    mats = STATE['MATS']
    for obj in objects:
        if obj.type == 'MESH':
            for mat in obj.data.materials:
                mats[mat.name.removeprefix('PG_')] = mat
    HELPER['material']('Room', (.025, .04, .055), .05, .8)
    HELPER['material']('RoomPanel', (.05, .075, .09), .2, .65)
    HELPER['material']('TargetLight', (.55, .24, .08), .1, .3, 1.3)
    HELPER['material']('Floor', (.045, .058, .068), 0, .7)

    def prop(name, center, size, material, bevel=.02):
        obj = HELPER['box']('Preview_' + name, center, size, material, bevel, parent=root)
        objects.pop()
        obj.parent = None
        geo.objects.unlink(obj)
        present.objects.link(obj)
        return obj

    prop('Floor', (0, -5, -1.60), (20, 20, .10), 'Floor')
    prop('Wall', (0, -7, 1.25), (12, .2, 5.7), 'Room')
    for x in range(-5, 6):
        prop('WallRib_' + str(x), (x, -6.85, 1.15), (.022, .10, 5.2), 'RoomPanel', .005)
    for z in (-1., 0., 1., 2., 3.):
        prop('WallSeam_' + str(z), (0, -6.82, z), (12, .08, .012), 'RoomPanel', .003)
    for y in (-2, -4, -6, -8):
        prop('FloorSeam_' + str(y), (0, y, -1.543), (12, .015, .009), 'RoomPanel', .003)
    prop('Crate', (-1.35, -4, -1.03), (.85, .75, 1.02), 'RoomPanel', .055)
    prop('CrateTrim', (-1.35, -3.61, -1.03), (.65, .025, .025), 'TargetLight', .005)
    for side in (-1, 1):
        prop('LightColumn_' + str(side), (side * 2.8, -6.68, .7), (.035, .045, 3.4), 'TargetLight', .008)
    for axis, size in [('H', (.038, .006, .006)), ('V', (.006, .006, .038))]:
        prop('Reticle_' + axis, (0, -4, 0), size, 'TargetLight', .001)

    light_data = bpy.data.lights.new('FL_PreviewBeam', 'SPOT')
    light_data.energy = 170
    light_data.color = (1., .68, .36)
    light_data.spot_size = math.radians(42)
    light_data.spot_blend = .35
    beam = bpy.data.objects.new('FL_PreviewBeam', light_data)
    present.objects.link(beam)
    muzzle = next(obj for obj in objects if obj.name == 'Socket_Muzzle')
    beam.location = muzzle.matrix_world.translation
    beam.rotation_euler = (rotation @ Vector((0, -1, 0))).to_track_quat('-Z', 'Y').to_euler()

    hero_data = bpy.data.cameras.new('FL_FPS_HeroCamera')
    hero = bpy.data.objects.new(hero_data.name, hero_data)
    present.objects.link(hero)
    center = (Vector(qa['bounds_m'][0]) + Vector(qa['bounds_m'][1])) / 2
    hero.location = center + Vector((1.4, -1.3, .9))
    hero.rotation_euler = (center - hero.location).to_track_quat('-Z', 'Y').to_euler()
    hero_data.type = 'ORTHO'
    hero_data.ortho_scale = 1.0
    scene.camera = camera
    bpy.context.view_layer.update()
    projected = [world_to_camera_view(scene, camera, obj.matrix_world @ vertex.co)
                 for obj in objects if obj.type == 'MESH' for vertex in obj.data.vertices]
    if not all(point.z > camera.data.clip_start for point in projected):
        raise RuntimeError('Flashlight crosses near clipping plane')
    if min(point.x for point in projected) <= .5:
        raise RuntimeError('Flashlight must stay in the right half of the view')
    muzzle_location = muzzle.matrix_world.translation
    firing_direction = rotation @ Vector((0, -1, 0))
    aim_error = ((AIM_TARGET - muzzle_location).cross(firing_direction)).length
    if aim_error >= 1e-5:
        raise RuntimeError('Flashlight beam axis misses the reticle')
    qa['framing'] = {
        'min_camera_depth_m': min(point.z for point in projected),
        'screen_bounds_normalized': [[min(point[i] for point in projected) for i in (0, 1)],
                                      [max(point[i] for point in projected) for i in (0, 1)]],
        'reticle_clear': True,
        'render_resolution': [1600, 900],
        'beam_axis_error_m': aim_error
    }
    for obj in objects:
        if obj.type == 'MESH':
            for vertex in obj.data.vertices:
                point = world_to_camera_view(scene, camera, obj.matrix_world @ vertex.co)
                if .44 < point.x < .56 and .44 < point.y < .56:
                    raise RuntimeError('Flashlight covers the central aiming area')
    (out / 'qa_geometry_fps.json').write_text(json.dumps(qa, indent=2) + '\n')
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.shading.type = 'MATERIAL'
    for obj in present.objects:
        obj.hide_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / (NAME + '.blend')))
    HELPER['export'](out)
    scene.render.filepath = str(out / 'preview_first_person.png')
    bpy.ops.render.render(write_still=True)
    for obj in present.objects:
        if obj.name.startswith('SM_PG_Preview_') or obj.name == 'FL_PreviewBeam':
            obj.hide_render = True
    scene.camera = hero
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1000
    scene.render.filepath = str(out / 'preview_large.png')
    bpy.ops.render.render(write_still=True)
    print('FLASHLIGHT_FPS_BUILD_OK', json.dumps(qa))


if __name__ == '__main__':
    main()
