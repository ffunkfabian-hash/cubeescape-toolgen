"""Reopen a bow asset and independently reimport both exchange formats.

Variants: world (CubeEscape_Bow_Standard), fps (CubeEscape_Bow_Standard_FPS)
and arrow (CubeEscape_Arrow_Standard). When qa_animation*.json exists, the
sampled poses of the one-shot Bow_Use clip are compared after every reimport,
including the morphing limb and string meshes.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

OUT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--variant',choices=('world','fps','arrow'),default='world')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
VARIANTS={'world':('CubeEscape_Bow_Standard','qa_geometry.json','qa_animation.json',''),
          'fps':('CubeEscape_Bow_Standard_FPS','qa_geometry_fps.json','qa_animation_fps.json','_fps'),
          'arrow':('CubeEscape_Arrow_Standard','qa_arrow.json',None,'_arrow')}
NAME,GEOMETRY,ANIMATION,SUFFIX=VARIANTS[args.variant]
expected=json.loads((OUT/GEOMETRY).read_text())
motion=json.loads((OUT/ANIMATION).read_text()) if ANIMATION and (OUT/ANIMATION).exists() else None
FACTOR=expected.get('enlargement',1)
report={'blender':bpy.app.version_string,'variant':args.variant,'checks':{}}


def find(scene,name):
    """Exact name first; a numeric Blender suffix (".001") is the only tolerated difference."""
    obj=scene.objects.get(name)
    if obj is not None:
        return obj
    for candidate in scene.objects:
        stem,dot,suffix=candidate.name.rpartition('.')
        if dot and stem==name and suffix.isdigit():
            return candidate
    raise KeyError('Object not found: '+name)


def frame_at(scene,value):
    scene.frame_set(math.floor(value),subframe=value%1)
    bpy.context.view_layer.update()


def bounds(obj,depsgraph):
    evaluated=obj.evaluated_get(depsgraph)
    vertices=[evaluated.matrix_world@v.co for v in evaluated.data.vertices]
    return [[min(v[i] for v in vertices) for i in range(3)],
            [max(v[i] for v in vertices) for i in range(3)]]


def check(scene,kind):
    start=1
    if motion:
        carrier=find(scene,'ArrowCarrier')
        assert carrier.animation_data and carrier.animation_data.action,(kind,'missing draw animation')
        start=float(carrier.animation_data.action.frame_range[0])
        assert abs(float(carrier.animation_data.action.frame_range[1])-start-96)<.01,(kind,'clip length')
        frame_at(scene,start)
    root=find(scene,NAME)
    assert tuple(root.scale)==(1,1,1) and root.matrix_world.translation.length<1e-6,(kind,'root transform')
    meshes=[o for o in root.children_recursive if o.type=='MESH']
    assert len(meshes)==expected['meshes'],(kind,'mesh count',len(meshes))
    assert kind=='blend' or not any(o.type in ('CAMERA','LIGHT') for o in scene.objects),(kind,'presentation leaked')
    coords=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
    found=[[min(v[i] for v in coords) for i in range(3)],
           [max(v[i] for v in coords) for i in range(3)]]
    assert all(abs(found[j][i]-expected['bounds_m'][j][i])<.0001 for i in range(3) for j in range(2)),(kind,found)
    for ob in meshes:
        assert len(ob.data.uv_layers)>0,(kind,ob.name,'UV')
        assert all(m is not None for m in ob.data.materials),(kind,ob.name,'material')
    for name,loc in expected['sockets'].items():
        ob=find(scene,name)
        assert (ob.matrix_world.translation-Vector(loc)).length<.0001,(kind,name,'socket')
    result={'passed':True,'mesh_count':len(meshes),'bounds_m':found,'sockets':True,'uvs_and_materials':True}
    if args.variant!='arrow':
        carrier=find(scene,'ArrowCarrier'); find(scene,'LoadedArrowPresence')
        loaded=[o for o in carrier.children_recursive if o.type=='MESH']
        assert len(loaded)>=5,(kind,'loaded arrow hierarchy',len(loaded))
        result['loaded_arrow_meshes']=len(loaded)
        for name in ('SM_BW_UpperBowstring','SM_BW_LowerBowstring'):
            find(scene,name)
    if motion:
        flex=[o for o in meshes if o.data.shape_keys]
        assert len(flex)==motion['morph_meshes'],(kind,'morph meshes',len(flex))
        max_matrix=0; max_bounds=0
        for frame,pose in motion['poses'].items():
            frame_at(scene,start+int(frame)-1)
            depsgraph=bpy.context.evaluated_depsgraph_get()
            for name,matrix in pose['matrices'].items():
                ob=find(scene,name)
                error=max(abs(ob.matrix_world[i][j]-matrix[i][j]) for i in range(4) for j in range(4))
                assert error<.001,(kind,frame,name,'animation pose mismatch',error)
                max_matrix=max(max_matrix,error)
            for name,box in pose['mesh_bounds'].items():
                current=bounds(find(scene,name),depsgraph)
                error=max(abs(current[j][i]-box[j][i]) for i in range(3) for j in range(2))
                assert error<.002*FACTOR,(kind,frame,name,'morph bounds mismatch',error)
                max_bounds=max(max_bounds,error)
        frame_at(scene,start)
        result['animation']={'passed':True,'sampled_poses':len(motion['poses']),'morph_meshes':len(flex),
                             'max_matrix_error':max_matrix,'max_morph_bounds_error_m':max_bounds,
                             'duration_seconds':motion['duration_seconds']}
    report['checks'][kind]=result


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
files=[NAME+'.blend',NAME+'.glb',NAME+'.fbx',GEOMETRY,'qa_roundtrip'+SUFFIX+'.json']
if args.variant=='world':
    files+=['preview_white.png','view_side.png','view_front.png','view_top.png']
    if motion: files+=['qa_animation.json','action_contract.json','preview_draw_once.gif']
elif args.variant=='fps':
    files+=['preview_first_person.png','preview_large.png']
    if motion: files+=['qa_animation_fps.json']
records=[]
for name in files:
    path=OUT/name
    assert path.is_file() and path.stat().st_size>100,name
    records.append({'path':name,'bytes':path.stat().st_size,
                    'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/('build_complete'+SUFFIX+'.json')).write_text(json.dumps({'passed':True,'files':records},indent=2)+'\n')
print('STANDARD_BOW_ROUNDTRIP_OK',args.variant,json.dumps(report))
