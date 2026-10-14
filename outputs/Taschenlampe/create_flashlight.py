"""Build the Cube Escape flashlight using the shared local asset helpers."""
import argparse
import json
import math
from pathlib import Path
import runpy
import sys

import bpy
import bmesh
from mathutils import Matrix

ASSET = 'CubeEscape_Flashlight'
HELPER_PATH = Path(__file__).resolve().parents[1] / 'Portalkanone' / 'create_portal_gun.py'
HELPER = runpy.run_path(str(HELPER_PATH))
STATE = HELPER['validate'].__globals__
MATS = STATE['MATS']
OBJECTS = STATE['OBJECTS']


def ring(name, center_y, center_z, outer, inner, depth, material, segments=48):
    bm = bmesh.new()
    layers = []
    for y, radius in ((-depth / 2, outer), (depth / 2, outer),
                      (depth / 2, inner), (-depth / 2, inner)):
        layers.append([
            bm.verts.new((radius * math.cos(2 * math.pi * i / segments),
                          y, radius * math.sin(2 * math.pi * i / segments)))
            for i in range(segments)
        ])
    for layer in range(4):
        for i in range(segments):
            j = (i + 1) % segments
            bm.faces.new((layers[layer][i], layers[layer][j],
                          layers[(layer + 1) % 4][j], layers[(layer + 1) % 4][i]))
    return HELPER['mesh'](name, bm, (0, center_y, center_z), material,
                          STATE['ROOT'], .001, 2)


def build():
    box = HELPER['box']
    cylinder = HELPER['cylinder']
    empty = HELPER['empty']
    root = STATE['ROOT']

    # Rear battery cap, faceted grip, and a broad reflector head make the concept silhouette.
    cylinder('BatteryCore', (0, .085, .112), .054, .13, 'Dark', bevel=.004, n=40)
    cylinder('BatteryShell', (0, .105, .112), .061, .075, 'Armor', bevel=.006, n=40)
    cylinder('RearCap', (0, .162, .112), .058, .025, 'Metal', bevel=.003, n=40)
    cylinder('RearSeal', (0, .178, .112), .048, .008, 'Dark', bevel=.001, n=40)
    cylinder('BodySleeve', (0, .010, .112), .057, .14, 'Armor', bevel=.006, n=40)
    cylinder('BodyBand', (0, -.047, .112), .066, .018, 'Metal', bevel=.002, n=40)
    cylinder('HeadHousing', (0, -.103, .112), .083, .105, 'Armor', bevel=.008, n=48)
    cylinder('HeadBackCollar', (0, -.065, .112), .076, .020, 'Dark', bevel=.002, n=48)
    cylinder('HeadFrontCollar', (0, -.154, .112), .086, .022, 'Dark', bevel=.002, n=48)
    ring('ReflectorRim', -.167, .112, .079, .052, .012, 'Metal')
    cylinder('ReflectorCup', (0, -.161, .112), .050, .006, 'Visor', bevel=.001, n=48)
    cylinder('Lens', (0, -.172, .112), .035, .006, 'WarmLens', bevel=.001, n=48)
    cylinder('EmitterCore', (0, -.176, .112), .013, .003, 'WarmCore', bevel=.0005, n=32)

    # The downward-sloping grip is readable from the side and sized for the robot hand.
    grip_rot = Matrix.Rotation(math.radians(-12), 3, 'X')
    box('GripMount', (0, .075, .052), (.080, .091, .047), 'Dark', .012, rot=grip_rot)
    box('GripCore', (0, .088, -.025), (.071, .086, .145), 'Dark', .018, rot=grip_rot)
    box('GripSideArmor_L', (-.037, .088, -.025), (.012, .076, .125), 'Armor', .008, rot=grip_rot)
    box('GripSideArmor_R', (.037, .088, -.025), (.012, .076, .125), 'Armor', .008, rot=grip_rot)
    box('GripHeel', (0, .090, -.101), (.082, .090, .019), 'Metal', .006, rot=grip_rot)
    for i in range(4):
        box('GripRib_%d' % i, (0, .043, -.073 + i * .027),
            (.058, .008, .008), 'Rubber', .002, rot=grip_rot)

    # Small, separated controls and status indicators; no decorative cable clutter.
    box('TopRail', (0, .012, .174), (.058, .105, .017), 'Dark', .006)
    box('TopSwitch', (0, -.006, .185), (.026, .036, .009), 'Amber', .003)
    box('SideDisplayBezel_L', (-.060, .074, .119), (.008, .054, .036), 'Visor', .004)
    box('SideDisplay_L', (-.065, .074, .119), (.003, .036, .020), 'Cyan', .002)
    box('SideDisplayBezel_R', (.060, .074, .119), (.008, .054, .036), 'Visor', .004)
    box('SideDisplay_R', (.065, .074, .119), (.003, .036, .020), 'Cyan', .002)
    for side in (-1, 1):
        for y in (-.019, .113):
            cylinder('ShellBolt_%s_%s' % (side, y), (side * .058, y, .112),
                     .0032, .003, 'Metal', axis=(1, 0, 0), n=12, bevel=.0004)

    # Semantic anchors: local forward is -Y and the light axis is the emitter centerline.
    empty('Socket_Hand', STATE['GEO'], root, (0, .088, -.025))
    empty('Socket_SupportHand', STATE['GEO'], root, (0, -.018, .018))
    empty('Socket_Muzzle', STATE['GEO'], root, (0, -.179, .112))
    empty('Socket_CenterOfMass', STATE['GEO'], root, (0, .038, .066))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--no-render', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'build_complete.json').unlink(missing_ok=True)
    if bpy.app.version != (5, 2, 2):
        raise RuntimeError('Validated target is Blender 5.2.2 LTS')

    STATE.update(ASSET=ASSET, OBJECTS=OBJECTS, MATS=MATS)
    OBJECTS.clear()
    MATS.clear()
    scene = bpy.data.scenes.new(ASSET)
    bpy.context.window.scene = scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    geo = HELPER['collection']('FL_GEOMETRY', scene.collection)
    root = HELPER['empty'](ASSET, geo)
    root['ce_category'] = 'Interactive'
    root['ce_forward'] = '-Y'
    STATE.update(GEO=geo, ROOT=root)

    material = HELPER['material']
    material('Armor', (.66, .685, .72), .42, .30)
    material('Dark', (.075, .08, .092), .7, .39)
    material('Metal', (.38, .395, .42), .6, .31)
    material('Visor', (.006, .007, .01), .25, .25)
    material('Rubber', (.017, .022, .027), 0, .75)
    material('Cyan', (.02, .62, .95), .15, .24, 4)
    material('Amber', (1., .38, .05), .1, .3, 1.5)
    material('WarmLens', (1., .52, .19), .12, .22, 2.2)
    material('WarmCore', (1., .78, .42), .05, .2, 4.5)
    build()
    qa = HELPER['validate']()
    qa.update(tags=['tool', 'flashlight', 'handheld', 'robot-classic', 'white-shell'],
              pivot='asset root; use Socket_Hand for hand attachment',
              integration='visual asset only; runtime light and input not included')
    (out / 'qa_geometry.json').write_text(json.dumps(qa, indent=2) + '\n')

    camera, target = HELPER['presentation'](scene)
    camera.data.ortho_scale = .55
    for obj in STATE['PRESENT'].objects:
        obj.hide_set(True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_distance = .70
                area.spaces.active.region_3d.view_location = target
                area.spaces.active.shading.type = 'MATERIAL'
    bpy.ops.wm.save_as_mainfile(filepath=str(out / (ASSET + '.blend')))
    HELPER['export'](out)
    if not args.no_render:
        HELPER['render'](scene, camera, target, out / 'preview_white.png', (.62, -.72, .43), .55)
        HELPER['render'](scene, camera, target, out / 'view_side.png', (1, 0, 0), .52)
        HELPER['render'](scene, camera, target, out / 'view_front.png', (0, -1, 0), .48)
        HELPER['render'](scene, camera, target, out / 'view_top.png', (0, 0, 1), .58)
    print('FLASHLIGHT_BUILD_OK', json.dumps(qa))


if __name__ == '__main__':
    main()
