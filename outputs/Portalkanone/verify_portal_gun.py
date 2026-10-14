"""Reopen the native asset and independently reimport both exchange formats."""
import bpy
import json
import hashlib
import argparse
import sys
from pathlib import Path
from mathutils import Vector

OUT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--variant',choices=('world','fps'),default='world')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
SUFFIX='_fps' if args.variant=='fps' else ''
NAME='CubeEscape_PortalGun'+('_FPS' if args.variant=='fps' else '')
expected=json.loads((OUT/('qa_geometry'+SUFFIX+'.json')).read_text())
report={'blender':bpy.app.version_string, 'checks':{}}


def check(scene,kind):
    root=next(o for o in scene.objects if o.name.split('.')[0]==NAME)
    assert tuple(root.scale)==(1,1,1) and root.matrix_world.translation.length<1e-6
    meshes=[o for o in root.children_recursive if o.type=='MESH']
    assert len(meshes)==expected['meshes'], (kind,'mesh count',len(meshes))
    assert not any(o.type in ('CAMERA','LIGHT') for o in scene.objects) or kind=='blend'
    coords=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
    bounds=[[min(v[i] for v in coords) for i in range(3)],
            [max(v[i] for v in coords) for i in range(3)]]
    assert all(abs(bounds[j][i]-expected['bounds_m'][j][i])<.0001 for i in range(3) for j in range(2)),(kind,bounds)
    for ob in meshes:
        assert len(ob.data.uv_layers)>0, (kind,ob.name,'UV')
        assert all(m is not None for m in ob.data.materials), (kind,ob.name,'material')
    for name,loc in expected['sockets'].items():
        ob=next(o for o in scene.objects if o.name.split('.')[0]==name)
        assert (ob.matrix_world.translation-Vector(loc)).length<.0001,(kind,name,'socket')
    for name in ('Pivot_Upper','Pivot_Lower'):
        ob=next(o for o in scene.objects if o.name.split('.')[0]==name)
        assert len(ob.children)>2, (kind,name,'arm hierarchy')
    report['checks'][kind]={'passed':True,'mesh_count':len(meshes),'bounds_m':bounds,
                           'sockets':True,'arm_hierarchy':True,'uvs_and_materials':True}


bpy.ops.wm.open_mainfile(filepath=str(OUT/(NAME+'.blend')))
check(bpy.context.scene,'blend')
for ext in ('glb','fbx'):
    scene=bpy.data.scenes.new('Verify_'+ext)
    bpy.context.window.scene=scene
    if ext=='glb':
        bpy.ops.import_scene.gltf(filepath=str(OUT/(NAME+'.glb')))
    else:
        bpy.ops.import_scene.fbx(filepath=str(OUT/(NAME+'.fbx')))
    bpy.context.view_layer.update()
    check(scene,ext)
(OUT/('qa_roundtrip'+SUFFIX+'.json')).write_text(json.dumps(report,indent=2)+'\n')
files=[NAME+'.blend',NAME+'.glb',NAME+'.fbx','qa_geometry'+SUFFIX+'.json','qa_roundtrip'+SUFFIX+'.json']
files+=['preview_first_person.png','preview_large.png'] if args.variant=='fps' else ['preview_white.png','preview_concept_colors.png','view_side.png','view_front.png','view_top.png']
records=[]
for name in files:
    path=OUT/name
    assert path.is_file() and path.stat().st_size>100,name
    records.append({'path':name,'bytes':path.stat().st_size,
                    'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/('build_complete'+SUFFIX+'.json')).write_text(json.dumps({'passed':True,'files':records},indent=2)+'\n')
print('PORTAL_GUN_ROUNDTRIP_OK',json.dumps(report))
