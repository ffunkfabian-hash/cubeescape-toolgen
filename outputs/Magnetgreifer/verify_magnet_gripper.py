"""Reopen the native asset and independently reimport both exchange formats."""
import bpy
import json
import hashlib
import argparse
import sys
import math
from pathlib import Path
from mathutils import Vector

OUT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--variant',choices=('world','fps'),default='world')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
SUFFIX='_fps' if args.variant=='fps' else ''
NAME='CubeEscape_MagnetGripper'+('_FPS' if args.variant=='fps' else '')
expected=json.loads((OUT/('qa_geometry'+SUFFIX+'.json')).read_text())
animation_path=OUT/('qa_animation'+SUFFIX+'.json')
motion=json.loads(animation_path.read_text()) if animation_path.exists() else None
report={'blender':bpy.app.version_string, 'checks':{}}


def check(scene,kind):
    animation_start=1
    if motion:
        spin=next(o for o in scene.objects if o.name.split('.')[0]=='Pivot_HeadSpin')
        assert spin.animation_data and spin.animation_data.action, (kind,'missing spin animation')
        animation_start=float(spin.animation_data.action.frame_range[0])
        assert abs(float(spin.animation_data.action.frame_range[1])-animation_start-96)<.01,(kind,'clip length')
        scene.frame_set(math.floor(animation_start),subframe=animation_start%1)
        bpy.context.view_layer.update()
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
    if motion:
        max_error=0
        for frame,pose in motion['poses'].items():
            current=animation_start+int(frame)-1
            scene.frame_set(math.floor(current),subframe=current%1)
            bpy.context.view_layer.update()
            for name,matrix in pose.items():
                ob=next(o for o in scene.objects if o.name.split('.')[0]==name)
                error=max(abs(ob.matrix_world[i][j]-matrix[i][j]) for i in range(4) for j in range(4))
                assert error<.001,(kind,frame,name,'animation pose mismatch',error)
                max_error=max(max_error,error)
        report['checks'][kind]['animation']={'passed':True,'sampled_poses':len(motion['poses']),
                                             'max_matrix_error':max_error,'duration_seconds':4}


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
if motion:
    files+=['qa_animation'+SUFFIX+'.json','action_contract.json','preview_apply_once.gif','qa_action_player.json']
    player_check=json.loads((OUT/'qa_action_player.json').read_text())
    assert player_check['source_sha256']==hashlib.sha256((OUT/'MagnetGripperActionPlayer.cs').read_bytes()).hexdigest(), 'Action player source changed since compilation'
files+=['preview_first_person.png','preview_large.png'] if args.variant=='fps' else ['preview_white.png','preview_concept_colors.png','view_side.png','view_front.png','view_top.png']
records=[]
for name in files:
    path=OUT/name
    assert path.is_file() and path.stat().st_size>100,name
    records.append({'path':name,'bytes':path.stat().st_size,
                    'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/('build_complete'+SUFFIX+'.json')).write_text(json.dumps({'passed':True,'files':records},indent=2)+'\n')
print('MAGNET_GRIPPER_ROUNDTRIP_OK',json.dumps(report))
