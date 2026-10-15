"""Reopen the flashlight asset and independently reimport its exchange formats."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--variant', choices=('world', 'fps'), default='world')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
suffix = '_fps' if args.variant == 'fps' else ''
name = 'CubeEscape_Flashlight' + ('_FPS' if args.variant == 'fps' else '')
expected = json.loads((OUT / ('qa_geometry' + suffix + '.json')).read_text())
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
    report['checks'][kind] = {
        'passed': True,
        'mesh_count': len(meshes),
        'bounds_m': bounds,
        'sockets': True,
        'uvs_and_materials': True
    }


bpy.ops.wm.open_mainfile(filepath=str(OUT / (name + '.blend')))
check(bpy.context.scene, 'blend')
for ext in ('glb', 'fbx'):
    scene = bpy.data.scenes.new('Verify_' + ext)
    bpy.context.window.scene = scene
    if ext == 'glb':
        bpy.ops.import_scene.gltf(filepath=str(OUT / (name + '.glb')))
    else:
        bpy.ops.import_scene.fbx(filepath=str(OUT / (name + '.fbx')))
    bpy.context.view_layer.update()
    check(scene, ext)
(OUT / ('qa_roundtrip' + suffix + '.json')).write_text(json.dumps(report, indent=2) + '\n')
files = [name + '.blend', name + '.glb', name + '.fbx',
         'qa_geometry' + suffix + '.json', 'qa_roundtrip' + suffix + '.json']
files += ['preview_first_person.png', 'preview_large.png'] if args.variant == 'fps' else [
    'preview_white.png', 'view_side.png', 'view_front.png', 'view_top.png'
]
records = []
for filename in files:
    path = OUT / filename
    assert path.is_file() and path.stat().st_size > 100, filename
    records.append({'path': filename, 'bytes': path.stat().st_size,
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
if args.variant == 'world':
    contract = OUT / 'flashlight_runtime_contract.json'
    records.append({'path': contract.name, 'bytes': contract.stat().st_size,
                    'sha256': hashlib.sha256(contract.read_bytes()).hexdigest()})
(OUT / ('build_complete' + suffix + '.json')).write_text(
    json.dumps({'passed': True, 'files': records}, indent=2) + '\n')
print('FLASHLIGHT_ROUNDTRIP_OK', json.dumps(report))
