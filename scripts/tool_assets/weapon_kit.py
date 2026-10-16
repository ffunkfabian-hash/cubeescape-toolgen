"""Shared build kit of the nine hand weapons (pistol ... rocket launcher).

Every weapon folder holds four thin launchers (create_weapon.py, create_weapon_fps.py, animate_weapon.py,
verify_weapon.py) that call this module with the weapon key; the geometry lives in weapon_designs.py.
The primitives (box, cylinder, material, validate, export ...) come from the portal gun helper, like the flashlight.

Blender coordinates: forward -Y, up +Z, meters, root at the origin, the origin is the centre of the pistol grip
(Socket_Hand). Nothing here animates the root object: the Use clip moves only child empties (Anim_*), so the clip
stays valid whatever yaw the Unity import adds to the root (docs/UNITY_EINBAU.md).
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import runpy
import sys

import bpy
import bmesh
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

import weapon_designs
from weapon_gif import FRAMES

HELPER_PATH = Path(__file__).resolve().parent / 'Portalkanone' / 'create_portal_gun.py'
HELPER = runpy.run_path(str(HELPER_PATH))
STATE = HELPER['validate'].__globals__
FPS = 24
LAST_FRAME = 97
ENLARGEMENT = 1.0
HAND_POSITION = Vector((-.26, -.6, -.2))
HORIZONTAL_FOV = 75


class Kit:
    """Modelling shortcuts over the portal gun helper; ``element`` names the glow material of the weapon (MT_Energy).
    Materials are the equipment channels: Primary (shell), Secondary (frame, panels), Accent, Metal, Detail (rubber,
    glass), Display (status lights, MT_Emission) and the element glow (MT_Energy)."""

    def __init__(self, element, grip_tilt):
        self.element = element
        self.grip_tilt = grip_tilt
        self.glow_material = {'kinetic': 'Kinetic', 'energy': 'Cyan', 'solar': 'Amber', 'void': 'Void', 'arc': 'Arc'}[element]

    @staticmethod
    def tilt(degrees):
        return Matrix.Rotation(math.radians(degrees), 3, 'X')

    @property
    def root(self):
        return STATE['ROOT']

    def box(self, name, center, size, mat='Primary', bevel=.006, parent=None, rot=None):
        return HELPER['box'](name, center, size, mat, bevel, parent=parent, rot=rot)

    def cyl(self, name, center, radius, length, mat='Secondary', axis='y', bevel=.002, parent=None, n=28):
        vector = {'x': (1, 0, 0), 'y': (0, 1, 0), 'z': (0, 0, 1)}[axis]
        return HELPER['cylinder'](name, center, radius, length, mat, axis=vector, bevel=bevel, parent=parent, n=n)

    def tube(self, name, center, outer, inner, length, mat='Secondary', axis='y', parent=None, n=40):
        """Hollow cylinder along ``axis`` (a barrel shroud, a muzzle ring, a scope tube)."""
        bm = bmesh.new()
        layers = []
        for offset, radius in ((-length / 2, outer), (length / 2, outer), (length / 2, inner), (-length / 2, inner)):
            ring = []
            for i in range(n):
                a = 2 * math.pi * i / n
                point = {'y': (radius * math.cos(a), offset, radius * math.sin(a)),
                         'x': (offset, radius * math.cos(a), radius * math.sin(a)),
                         'z': (radius * math.cos(a), radius * math.sin(a), offset)}[axis]
                ring.append(bm.verts.new(point))
            layers.append(ring)
        for layer in range(4):
            for i in range(n):
                j = (i + 1) % n
                nxt = (layer + 1) % 4
                bm.faces.new((layers[layer][i], layers[layer][j], layers[nxt][j], layers[nxt][i]))
        return HELPER['mesh'](name, bm, center, mat, parent or self.root, min(.0012, (outer - inner) * .3), 2)

    def slab(self, name, points, width, mat='Primary', x=0.0, bevel=.004, parent=None):
        """Side profile ``points`` = [(y, z), ...] extruded along X (width), centred at ``x``."""
        bm = bmesh.new()
        loops = [[bm.verts.new((x + side * width / 2, y, z)) for y, z in points] for side in (-1, 1)]
        bm.faces.new(list(reversed(loops[0])))
        bm.faces.new(loops[1])
        for i in range(len(points)):
            k = (i + 1) % len(points)
            bm.faces.new((loops[0][i], loops[0][k], loops[1][k], loops[1][i]))
        return HELPER['mesh'](name, bm, (0, 0, 0), mat, parent or self.root, min(bevel, width * .4), 2)

    def glow(self, name, center, size, parent=None, mat=None, rot=None):
        """A flat light strip in the element colour."""
        return self.box(name, center, size, mat or self.glow_material, min(.0015, min(size) * .35), parent, rot)

    def bolts(self, name, positions, radius=.0035, axis='x', parent=None, depth=.004):
        for index, position in enumerate(positions):
            self.cyl('%s_%d' % (name, index), position, radius, depth, 'Metal', axis=axis, n=10, bevel=.0004, parent=parent)

    def socket(self, name, location):
        return HELPER['empty'](name, STATE['GEO'], self.root, location)

    def pivot(self, name, location, parent=None):
        """Empty that the Use clip animates (identity rotation; meshes parented to it keep world coordinates)."""
        obj = HELPER['empty'](name, STATE['GEO'], parent or self.root, location)
        obj['ce_role'] = 'interactive'
        obj.empty_display_size = .03
        bpy.context.view_layer.update()
        return obj


def design(key):
    return weapon_designs.DESIGNS[key]


def tool_entry(key):
    """Asset, clip and hold of a weapon: the design table is the source (the authoring copy has no data/ folder);
    tests/test_weapons.py keeps data/tools.json identical to it."""
    spec = design(key)
    return {'id': key, 'asset': spec['asset'], 'clip': spec['clip'],
            'hold': {'grip_tilt_degrees': spec['grip_tilt_degrees']}}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path(sys.argv[0]).resolve().parent)
    parser.add_argument('--no-render', action='store_true')
    parser.add_argument('--no-preview', action='store_true')
    parser.add_argument('--variant', choices=('world', 'fps'), default='world')
    return parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def define_materials():
    """One source material per Cube Escape equipment channel (data/game_palette.json 'channels': PG_Primary -> MT_Primary ...);
    the element glows all become MT_Energy, PG_Display the status lights MT_Emission."""
    material = HELPER['material']
    for name, rgb, metal, rough, emission in [
            ('Primary', (.66, .685, .72), .42, .30, 0), ('Secondary', (.075, .08, .092), .7, .39, 0),
            ('Accent', (.86, .36, .07), .25, .42, 0), ('Metal', (.38, .395, .42), .6, .31, 0),
            ('Detail', (.017, .022, .027), 0, .75, 0), ('Display', (.25, .85, 1.), .1, .3, 3),
            ('Cyan', (.02, .62, .95), .15, .24, 4),
            ('Amber', (1., .38, .05), .1, .3, 1.5), ('Void', (.52, .10, 1.), .15, .24, 4),
            ('Arc', (.08, .26, 1.), .15, .24, 4), ('Kinetic', (.9, .93, 1.), .1, .3, 2.5)]:
        material(name, rgb, metal, rough, emission)


# ----------------------------------------------------------------------------------------------------- world model
def world(key):
    """create_weapon.py: the world model (static pose; the Use clip is added by animate_weapon.py)."""
    spec = design(key)
    tool = tool_entry(key)
    asset = tool['asset']
    args = parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'build_complete.json').unlink(missing_ok=True)
    if bpy.app.version != (5, 2, 2):
        raise RuntimeError('Validated target is Blender 5.2.2 LTS')
    STATE.update(ASSET=asset, OBJECTS=HELPER['validate'].__globals__['OBJECTS'], MATS=STATE['MATS'])
    STATE['OBJECTS'].clear()
    STATE['MATS'].clear()
    scene = bpy.data.scenes.new(asset)
    bpy.context.window.scene = scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    geo = HELPER['collection']('WP_GEOMETRY', scene.collection)
    root = HELPER['empty'](asset, geo)
    root['ce_category'] = 'Interactive'
    root['ce_forward'] = '-Y'
    root['ce_weapon_class'] = spec['class']
    root['ce_weapon_element'] = spec['element']
    root['ce_grip_tilt_degrees'] = tool['hold']['grip_tilt_degrees']
    STATE.update(GEO=geo, ROOT=root)
    define_materials()
    kit = Kit(spec['element'], tool['hold']['grip_tilt_degrees'])
    spec['build'](kit)
    for name in ('Socket_Hand', 'Socket_Muzzle', 'Socket_SupportHand', 'Socket_CenterOfMass'):
        if not any(obj.name == name for obj in STATE['OBJECTS']):
            raise RuntimeError('Design %s lacks %s' % (key, name))
    qa = HELPER['validate']()
    qa.update(tags=['tool', 'weapon', spec['class'], spec['element'], 'handheld', 'robot-classic', 'white-shell'],
              pivot='asset root = grip centre (Socket_Hand); forward -Y, up +Z',
              integration='visual asset only; no ammunition, damage or rules (Cube Escape tool in hand)',
              weapon={'class': spec['class'], 'element': spec['element'],
                      'grip_tilt_degrees': tool['hold']['grip_tilt_degrees']})
    qa['sockets_checked'] = socket_report(spec)
    (out / 'qa_geometry.json').write_text(json.dumps(qa, indent=2) + '\n')
    camera, target = HELPER['presentation'](scene)
    center = Vector(spec['view_center'])
    camera.data.ortho_scale = spec['view_scale']
    for obj in STATE['PRESENT'].objects:
        obj.hide_set(True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_distance = spec['view_scale'] * 1.4
                area.spaces.active.region_3d.view_location = center
                area.spaces.active.shading.type = 'MATERIAL'
    bpy.ops.wm.save_as_mainfile(filepath=str(out / (asset + '.blend')))
    HELPER['export'](out)
    if not args.no_render:
        render(scene, camera, spec, out / 'preview_white.png', (.62, -.72, .43), 1.0)
        render(scene, camera, spec, out / 'view_side.png', (1, 0, 0), .98)
        render(scene, camera, spec, out / 'view_front.png', (0, -1, 0), .55)
        render(scene, camera, spec, out / 'view_top.png', (0, 0, 1), .98)
    print('WEAPON_BUILD_OK', key, json.dumps({'triangles': qa['triangles'], 'dimensions_m': qa['dimensions_m']}))


def render(scene, camera, spec, path, offset, factor):
    HELPER['render'](scene, camera, Vector(spec['view_center']), path, offset, spec['view_scale'] * factor)


def socket_report(spec):
    """Distances of the hand sockets to the grip parts (a floating socket means a hand in the air)."""
    scene = bpy.context.scene
    sockets = {obj.name: obj.matrix_world.translation.copy() for obj in STATE['OBJECTS'] if obj.name.startswith('Socket_')}
    report = {}
    for socket_name, part in (('Socket_Hand', spec['grip_part']), ('Socket_SupportHand', spec['support_part'])):
        meshes = [obj for obj in STATE['OBJECTS'] if obj.type == 'MESH' and obj.name.startswith('SM_PG_' + part)]
        if not meshes:
            raise RuntimeError('%s: grip part %s not found' % (spec['class'], part))
        bm = bmesh.new()
        for obj in meshes:
            piece = bmesh.new()
            piece.from_mesh(obj.data)
            piece.transform(obj.matrix_world)
            for vertex in piece.verts:
                bm.verts.new(vertex.co)
            piece.free()
        low = [min(v.co[i] for v in bm.verts) for i in range(3)]
        high = [max(v.co[i] for v in bm.verts) for i in range(3)]
        bm.free()
        point = sockets[socket_name]
        slack = max(max(low[i] - point[i], point[i] - high[i]) for i in range(3))
        if slack > .004:
            raise RuntimeError('%s lies %.1f mm outside %s (hand would float)' % (socket_name, slack * 1000, part))
        report[socket_name] = {'part': part, 'bounds_m': [low, high], 'outside_m': max(slack, 0.0)}
    return report


# ------------------------------------------------------------------------------------------------ first-person model
def depth(obj):
    count = 0
    while obj.parent:
        count += 1
        obj = obj.parent
    return count


def fps(key):
    """create_weapon_fps.py: the world model copied under a camera-attached root (hands are added by first_person.py)."""
    spec = design(key)
    tool = tool_entry(key)
    name = tool['asset'] + '_FPS'
    args = parse_args()
    out = args.output.resolve()
    source = out / (tool['asset'] + '.blend')
    if not source.is_file():
        raise RuntimeError('Build the world model first')
    (out / 'build_complete_fps.json').unlink(missing_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    original = bpy.context.scene
    source_root = original.objects[tool['asset']]
    source_objects = [source_root] + list(source_root.children_recursive)
    source_hand = original.objects['Socket_Hand'].matrix_world.translation.copy()
    transform = Matrix.Translation(HAND_POSITION) @ Matrix.Scale(ENLARGEMENT, 4) @ Matrix.Translation(-source_hand)
    source_world = {obj: obj.matrix_world.copy() for obj in source_objects}
    scene = bpy.data.scenes.new(name)
    bpy.context.window.scene = scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    geo = bpy.data.collections.new('WP_FPS_GEOMETRY')
    scene.collection.children.link(geo)
    root = bpy.data.objects.new(name, None)
    geo.objects.link(root)
    root['ce_category'] = 'Interactive'
    root['ce_variant'] = 'first_person_large'
    root['ce_camera_attachment'] = 'origin, identity transform; forward -Y, up Z'
    root['ce_weapon_class'] = spec['class']
    root['ce_weapon_element'] = spec['element']
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
    STATE.update(ASSET=name, OBJECTS=objects, ROOT=root, GEO=geo)
    qa = HELPER['validate']()
    qa.update(variant='first_person_large', enlargement=ENLARGEMENT,
              tags=['tool', 'weapon', spec['class'], spec['element'], 'handheld', 'robot-classic', 'first-person-large'],
              pivot='camera attachment at origin; all export object scales are 1',
              integration='visual asset only; no ammunition, damage or rules (Cube Escape tool in hand)',
              camera={'horizontal_fov_degrees': HORIZONTAL_FOV, 'near_m': .03,
                      'hand_position_blender_m': list(HAND_POSITION),
                      'hand_position_unity_m': [HAND_POSITION.x, HAND_POSITION.z, -HAND_POSITION.y],
                      'aim_target_blender_m': [0, -4, 0],
                      'note': 'Placeholder pose; first_person.py bakes the final hold from data/viewmodels.json.'})
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
    mats.clear()
    for obj in objects:
        if obj.type == 'MESH':
            for mat in obj.data.materials:
                mats[mat.name.removeprefix('PG_')] = mat
    make = HELPER['material']      # presentation-only materials, never in an export (the palette map does not list them)
    make('Room', (.025, .04, .055), .05, .8)
    make('RoomPanel', (.05, .075, .09), .2, .65)
    make('Floor', (.045, .058, .068), 0, .7)

    def prop(prop_name, center, size, mat, bevel=.02):
        obj = HELPER['box']('Preview_' + prop_name, center, size, mat, bevel, parent=root)
        objects.pop()
        obj.parent = None
        geo.objects.unlink(obj)
        present.objects.link(obj)
        return obj

    prop('Floor', (0, -5, -1.60), (20, 20, .10), 'Floor')
    prop('Wall', (0, -7, 1.25), (12, .2, 5.7), 'Room')
    for x in range(-5, 6):
        prop('WallRib_' + str(x), (x, -6.85, 1.15), (.022, .10, 5.2), 'RoomPanel', .005)
    for y in (-2, -4, -6, -8):
        prop('FloorSeam_' + str(y), (0, y, -1.543), (12, .015, .009), 'RoomPanel', .003)
    prop('Crate', (-1.35, -4, -1.03), (.85, .75, 1.02), 'RoomPanel', .055)
    for axis, size in (('H', (.038, .006, .006)), ('V', (.006, .006, .038))):
        prop('Reticle_' + axis, (0, -4, 0), size, 'RoomPanel', .001)
    hero_data = bpy.data.cameras.new('WP_FPS_HeroCamera')
    hero = bpy.data.objects.new(hero_data.name, hero_data)
    present.objects.link(hero)
    center = (Vector(qa['bounds_m'][0]) + Vector(qa['bounds_m'][1])) / 2
    hero.location = center + Vector((1.4, -1.3, .9))
    hero.rotation_euler = (center - hero.location).to_track_quat('-Z', 'Y').to_euler()
    hero_data.type = 'ORTHO'
    hero_data.ortho_scale = 1.4
    scene.camera = camera
    bpy.context.view_layer.update()
    projected = [world_to_camera_view(scene, camera, obj.matrix_world @ vertex.co)
                 for obj in objects if obj.type == 'MESH' for vertex in obj.data.vertices]
    if not all(point.z > camera.data.clip_start for point in projected):
        raise RuntimeError('Weapon crosses near clipping plane')
    (out / 'qa_geometry_fps.json').write_text(json.dumps(qa, indent=2) + '\n')
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.shading.type = 'MATERIAL'
    for obj in present.objects:
        obj.hide_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / (name + '.blend')))
    HELPER['export'](out)
    print('WEAPON_FPS_BUILD_OK', key, json.dumps({'triangles': qa['triangles']}))


# ---------------------------------------------------------------------------------------------------------- Use clip
def all_curves(action):
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves


def owned(scene, wanted):
    return next(obj for obj in scene.objects if obj.name.split('.')[0] == wanted)


def animate_object(obj, move, clip):
    """Keys of one Use-clip move: {'node', 'channel': 'location'|'rotation', 'axis', 'keys': [(frame, value)]}."""
    obj.rotation_mode = 'XYZ'
    path = 'location' if move['channel'] == 'location' else 'rotation_euler'
    rest = obj.location[move['axis']] if path == 'location' else 0.0
    for frame, value in move['keys']:
        if path == 'location':
            obj.location[move['axis']] = rest + value
        else:
            obj.rotation_euler[move['axis']] = math.radians(value)
        obj.keyframe_insert(data_path=path, index=move['axis'], frame=frame, group=clip)
    if path == 'location':
        obj.location[move['axis']] = rest
    else:
        obj.rotation_euler[move['axis']] = 0.0
    action = obj.animation_data.action
    action.name = '%s_%s' % (clip, obj.name)
    action.use_frame_range = True
    action.frame_start = 1
    action.frame_end = LAST_FRAME
    action.use_cyclic = False
    action['ce_loop'] = False
    action['ce_autoplay'] = False
    for curve in all_curves(action):
        for key in curve.keyframe_points:
            key.interpolation = 'BEZIER'
            key.handle_left_type = 'AUTO_CLAMPED'
            key.handle_right_type = 'AUTO_CLAMPED'


def matrix_record(obj):
    return [list(row) for row in obj.matrix_world]


def export_clip(out, name, root, clip):
    objects = {root, *root.children_recursive}
    for obj in bpy.context.scene.objects:
        obj.select_set(obj in objects)
    bpy.context.view_layer.objects.active = root
    kwargs = {'filepath': str(out / (name + '.glb')), 'export_format': 'GLB', 'use_selection': True,
              'export_yup': True, 'export_extras': True, 'export_animations': True,
              'export_animation_mode': 'ACTIVE_ACTIONS', 'export_merge_animation': 'ACTION',
              'export_nla_strips_merged_animation_name': clip, 'export_frame_range': True,
              'export_force_sampling': True, 'export_cameras': False, 'export_lights': False}
    properties = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    assert all(k in properties for k in kwargs)
    assert 'FINISHED' in bpy.ops.export_scene.gltf(**kwargs)
    assert 'FINISHED' in bpy.ops.export_scene.fbx(
        filepath=str(out / (name + '.fbx')), use_selection=True, object_types={'EMPTY', 'MESH'},
        axis_forward='-Z', axis_up='Y', global_scale=1, apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS', bake_space_transform=False, use_mesh_modifiers=True,
        use_custom_props=True, bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True, bake_anim_step=1, bake_anim_simplify_factor=0, add_leaf_bones=False)


def animate(key):
    """animate_weapon.py: the one-shot Use clip on both variants. Child empties only, never the root; the weapon
    returns to its rest pose at the last frame."""
    spec = design(key)
    tool = tool_entry(key)
    clip = tool['clip']
    args = parse_args()
    out = args.output.resolve()
    assert bpy.app.background, 'Run the animation builder in a background Blender instance'
    for suffix in ('', '_FPS'):
        name = tool['asset'] + suffix
        bpy.ops.wm.open_mainfile(filepath=str(out / (name + '.blend')))
        scene = bpy.context.scene
        root = scene.objects[name]
        scene.frame_set(1)
        for move in spec['use_clip']:
            animate_object(owned(scene, move['node']), move, clip)
        scene.frame_start, scene.frame_end = 1, LAST_FRAME
        scene.render.fps = FPS
        root['ce_action_clip'] = clip
        root['ce_autoplay'] = False
        root['ce_loop'] = False
        root['ce_trigger'] = spec['trigger']
        report = motion_qa(scene, root, spec, clip)
        (out / ('qa_animation' + ('_fps' if suffix else '') + '.json')).write_text(json.dumps(report, indent=2) + '\n')
        export_clip(out, name, root, clip)
        scene.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(out / (name + '.blend')))
        if not suffix and not args.no_preview:
            preview(scene, spec, out)
        print('WEAPON_USE_CLIP_OK', key, suffix, json.dumps({k: report[k] for k in ('clip', 'root_curves', 'max_travel_m')}))
    contract = {'clip': clip, 'frames': LAST_FRAME, 'fps': FPS, 'loop': False, 'autoplay': False,
                'trigger': spec['trigger'], 'returns_to_rest': True, 'root_curves': False,
                'moving_nodes': sorted({move['node'] for move in spec['use_clip']}),
                'runtime': 'Play once on the explicit trigger; the clip animates only child nodes of the root and '
                           'ends in the rest pose. Cube Escape keeps the weapon logic (no ammunition, no rules here).'}
    (out / 'action_contract.json').write_text(json.dumps(contract, indent=2) + '\n')


def motion_qa(scene, root, spec, clip):
    """Rest pose at the first and the last frame, a real move in between, and no curve on the root."""
    nodes = sorted({move['node'] for move in spec['use_clip']})
    sockets = [obj.name for obj in root.children_recursive if obj.name.startswith('Socket_')]
    poses, travel = {}, 0.0
    start = {name: owned(scene, name).matrix_world.copy() for name in nodes}
    for frame in range(1, LAST_FRAME + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        for name in nodes:
            travel = max(travel, (owned(scene, name).matrix_world.translation - start[name].translation).length)
        if frame in FRAMES:
            poses[str(frame)] = {name: matrix_record(owned(scene, name)) for name in [*nodes, *sockets]}
    for name in nodes:
        end = poses[str(LAST_FRAME)][name]
        first = poses['1'][name]
        assert max(abs(first[i][j] - end[i][j]) for i in range(4) for j in range(4)) < 1e-5, (name, 'not back at rest')
    root_curves = bool(root.animation_data and root.animation_data.action)
    assert not root_curves, 'the Use clip must not animate the root object'
    rotation = max((math.degrees(abs(value)) for move in spec['use_clip'] if move['channel'] == 'rotation'
                    for _, value in move['keys']), default=0.0)
    assert travel > .004 or rotation > 3, 'the Use clip does not move anything visible'
    scene.frame_set(1)
    bpy.context.view_layer.update()
    return {'clip': clip, 'fps': FPS, 'frame_start': 1, 'frame_end': LAST_FRAME, 'loop': False, 'autoplay': False,
            'trigger': spec['trigger'], 'root_curves': root_curves, 'max_travel_m': travel,
            'max_rotation_degrees': rotation, 'returns_to_rest': True, 'poses': poses}


def preview(scene, spec, out):
    collection = bpy.data.collections.new('WP_ANIMATION_PREVIEW')
    scene.collection.children.link(collection)
    data = bpy.data.cameras.new('WP_AnimationCamera')
    camera = bpy.data.objects.new(data.name, data)
    collection.objects.link(camera)
    center = Vector(spec['view_center'])
    camera.location = center + Vector((.9, -.8, .52))
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    data.type = 'ORTHO'
    data.ortho_scale = spec['view_scale']
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = 900, 640
    scene.cycles.samples = 16
    frames = out / 'animation_frames'
    frames.mkdir(exist_ok=True)
    for frame in FRAMES:
        scene.frame_set(frame)
        scene.render.filepath = str(frames / ('apply_%03d.png' % frame))
        if not os.environ.get('TOOLGEN_NO_RENDER'):
            bpy.ops.render.render(write_still=True)
    scene.frame_set(1)


# ------------------------------------------------------------------------------------------------------------ verify
def verify(key):
    """verify_weapon.py: reopen the .blend and reimport GLB and FBX independently."""
    tool = tool_entry(key)
    args = parse_args()
    out = Path(sys.argv[0]).resolve().parent
    suffix = '_fps' if args.variant == 'fps' else ''
    name = tool['asset'] + ('_FPS' if args.variant == 'fps' else '')
    expected = json.loads((out / ('qa_geometry' + suffix + '.json')).read_text())
    report = {'blender': bpy.app.version_string, 'checks': {}}

    def check(scene, kind):
        root = next(obj for obj in scene.objects if obj.name.split('.')[0] == name)
        assert tuple(root.scale) == (1, 1, 1)
        assert root.matrix_world.translation.length < 1e-6
        meshes = [obj for obj in root.children_recursive if obj.type == 'MESH']
        assert len(meshes) == expected['meshes'], (kind, 'mesh count', len(meshes))
        coords = [obj.matrix_world @ vertex.co for obj in meshes for vertex in obj.data.vertices]
        bounds = [[min(vertex[i] for vertex in coords) for i in range(3)],
                  [max(vertex[i] for vertex in coords) for i in range(3)]]
        assert all(abs(bounds[j][i] - expected['bounds_m'][j][i]) < .0001
                   for i in range(3) for j in range(2)), (kind, bounds)
        for obj in meshes:
            assert len(obj.data.uv_layers) > 0, (kind, obj.name, 'UV')
            assert all(mat is not None for mat in obj.data.materials), (kind, obj.name, 'material')
        for socket_name, loc in expected['sockets'].items():
            socket = next(obj for obj in scene.objects if obj.name.split('.')[0] == socket_name)
            assert (socket.matrix_world.translation - Vector(loc)).length < .0001, (kind, socket_name)
        report['checks'][kind] = {'passed': True, 'mesh_count': len(meshes), 'bounds_m': bounds, 'sockets': True,
                                  'uvs_and_materials': True}

    bpy.ops.wm.open_mainfile(filepath=str(out / (name + '.blend')))
    check(bpy.context.scene, 'blend')
    for ext in ('glb', 'fbx'):
        scene = bpy.data.scenes.new('Verify_' + ext)
        bpy.context.window.scene = scene
        if ext == 'glb':
            bpy.ops.import_scene.gltf(filepath=str(out / (name + '.glb')))
        else:
            bpy.ops.import_scene.fbx(filepath=str(out / (name + '.fbx')))
        bpy.context.view_layer.update()
        check(scene, ext)
    (out / ('qa_roundtrip' + suffix + '.json')).write_text(json.dumps(report, indent=2) + '\n')
    files = [name + '.blend', name + '.glb', name + '.fbx', 'qa_geometry' + suffix + '.json', 'qa_roundtrip' + suffix + '.json']
    files += ['preview_first_person.png', 'preview_large.png'] if args.variant == 'fps' else [
        'preview_white.png', 'view_side.png', 'view_front.png', 'view_top.png']
    records = []
    for filename in files:
        path = out / filename
        assert path.is_file() and path.stat().st_size > 100, filename
        records.append({'path': filename, 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (out / ('build_complete' + suffix + '.json')).write_text(json.dumps({'passed': True, 'files': records}, indent=2) + '\n')
    print('WEAPON_ROUNDTRIP_OK', key, json.dumps(report))
