"""One-shot draw/hold/release/reset, including exported limb/string morphs."""
import json
import math
from pathlib import Path
import sys

import bpy
import os
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from motion_profiles import draw_value

OUT=Path(__file__).resolve().parent
FRAMES=(1,16,31,43,44,48,79,85,97)
DRAW=tuple((frame,draw_value(frame)) for frame in range(1,98))


def curves(action):
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves


def finish_action(action,name,step=False):
    action.name=name; action.use_frame_range=True
    action.frame_start=1; action.frame_end=97; action.use_cyclic=False
    action['ce_loop']=False; action['ce_autoplay']=False
    for curve in curves(action):
        for key in curve.keyframe_points:
            key.interpolation='CONSTANT' if step else 'LINEAR'


def find(scene,name):
    """Exact object name first; a numeric Blender suffix (".001") is the only tolerated difference.

    Splitting at the first dot is wrong here: generated names may legitimately
    contain none, but a split would also truncate any name with a dot in it.
    """
    obj=scene.objects.get(name)
    if obj is not None:
        return obj
    for candidate in scene.objects:
        stem,dot,suffix=candidate.name.rpartition('.')
        if dot and stem==name and suffix.isdigit():
            return candidate
    raise KeyError('Object not found: '+name)


def setup(scene,root,factor):
    scene.frame_set(1); scene.render.fps=24
    scene.frame_start=1; scene.frame_end=97
    for obj in root.children_recursive:
        if obj.type=='MESH' and obj.data.shape_keys:
            keys=obj.data.shape_keys; keys.animation_data_clear()
            draw=keys.key_blocks['Draw']
            for frame,value in DRAW:
                draw.value=value; draw.keyframe_insert(data_path='value',frame=frame,group='Bow_Use')
            finish_action(keys.animation_data.action,'Bow_Use_'+obj.name)
    carrier=find(scene,'ArrowCarrier')
    nock=find(scene,'Socket_Nock')
    presence=find(scene,'LoadedArrowPresence')
    tip=scene.objects.get('Socket_ArrowTip')
    if tip is None:
        tip=bpy.data.objects.new('Socket_ArrowTip',None); root.users_collection[0].objects.link(tip)
        tip.parent=root; tip.location=carrier.matrix_world@Vector((0,-.715*factor,0))
    bpy.context.view_layer.update()
    for obj in (carrier,nock,tip):
        obj.animation_data_clear()
        base=obj.location.copy()
        delta=Vector((0,.23*factor,0))
        if obj!=carrier:
            delta=carrier.matrix_world.to_quaternion()@delta
        for frame,value in DRAW:
            obj.location=base+delta*value
            obj.keyframe_insert(data_path='location',frame=frame,group='Bow_Use')
        finish_action(obj.animation_data.action,'Bow_Use_'+obj.name)
    presence.animation_data_clear()
    for frame,value in ((1,1),(43,1),(44,.001),(78,.001),(79,1),(97,1)):
        presence.scale=(value,value,value)
        presence.keyframe_insert(data_path='scale',frame=frame,group='Bow_Use')
    finish_action(presence.animation_data.action,'Bow_Use_LoadedArrowVisibility',step=True)
    presence['ce_visibility_animation']='1 visible; 0.001 inactive visual; rest scale 1'
    root['ce_action_clip']='Bow_Use'; root['ce_autoplay']=False; root['ce_loop']=False
    root['ce_trigger']='explicit ShootAction'; root['ce_default_state']='Idle_Loaded'
    for name,frame in (('Idle_Loaded',1),('Drawn',31),('Release',44),('Reset',79),('Idle_Loaded_End',97)):
        scene.timeline_markers.new(name,frame=frame)
    scene.frame_set(1); bpy.context.view_layer.update()


def bounds(obj,depsgraph):
    evaluated=obj.evaluated_get(depsgraph)
    vertices=[evaluated.matrix_world@v.co for v in evaluated.data.vertices]
    return [[min(v[i] for v in vertices) for i in range(3)],
            [max(v[i] for v in vertices) for i in range(3)]]


def check_motion(scene,root,factor):
    mesh_names=[o.name for o in root.children_recursive if o.type=='MESH' and (o.get('bow_flex') or 'Arrow_' in o.name)]
    tracking=('ArrowCarrier','LoadedArrowPresence','Socket_Nock','Socket_ArrowTip','Socket_Muzzle','Socket_Hand')
    report={'clip':'Bow_Use','fps':24,'frame_start':1,'frame_end':97,'duration_seconds':4,
            'autoplay':False,'loop':False,'default_state':'Idle_Loaded','trigger':'ShootAction',
            'morph_meshes':sum(1 for o in root.children_recursive if o.type=='MESH' and o.data.shape_keys),
            'poses':{},'min_string_attachment_error_m':0,'max_string_attachment_error_m':0,
            'arrow_visibility_node_scale_exception':[1,.001]}
    min_depth=float('inf'); max_attachment=0
    for frame in range(1,98):
        scene.frame_set(frame); bpy.context.view_layer.update()
        deps=bpy.context.evaluated_depsgraph_get()
        carrier=find(scene,'ArrowCarrier')
        nock=find(scene,'Socket_Nock')
        presence=find(scene,'LoadedArrowPresence')
        if presence.matrix_world.to_scale().x>.5:
            assert (carrier.matrix_world.translation-nock.matrix_world.translation).length<1e-5, ('Loaded arrow leaves the nock',frame)
        else:
            # Hidden phase: the presence node is scaled to 0.001, so the model arrow collapses
            # onto its pivot (the grip origin) instead of following the string.
            collapsed=(carrier.matrix_world.translation-presence.matrix_world.translation).length
            assert collapsed<.002*factor, ('Hidden arrow drifts from its pivot',frame,collapsed)
        for side in ('Upper','Lower'):
            string=find(scene,'SM_BW_'+side+'Bowstring')
            vertices=[string.evaluated_get(deps).matrix_world@v.co for v in string.evaluated_get(deps).data.vertices]
            # The tube surface stays within its radius of the animated nock.
            error=min((co-nock.matrix_world.translation).length for co in vertices)
            assert error<.0020*factor, ('String detaches from nock',frame,side,error)
            max_attachment=max(max_attachment,error)
        if root.name.endswith('_FPS'):
            for obj in root.children_recursive:
                if obj.type=='MESH':
                    evaluated=obj.evaluated_get(deps)
                    for vertex in evaluated.data.vertices:
                        p=world_to_camera_view(scene,scene.camera,evaluated.matrix_world@vertex.co)
                        assert p.z>scene.camera.data.clip_start, ('Near clipping',frame,obj.name,p.z)
                        assert not (.47<p.x<.53 and .47<p.y<.53),('Reticle obscured',frame,obj.name)
                        min_depth=min(min_depth,p.z)
        if frame in FRAMES:
            report['poses'][str(frame)]={
                'matrices':{name:[list(row) for row in find(scene,name).matrix_world] for name in tracking},
                'mesh_bounds':{name:bounds(find(scene,name),deps) for name in mesh_names}}
    report['max_string_attachment_error_m']=max_attachment
    if root.name.endswith('_FPS'):
        report['animated_fps_min_depth_m']=min_depth; report['animated_reticle_clear']=True
    for name in tracking:
        a=report['poses']['1']['matrices'][name]; b=report['poses']['97']['matrices'][name]
        assert max(abs(a[i][j]-b[i][j]) for i in range(4) for j in range(4))<1e-5
    scene.frame_set(1); bpy.context.view_layer.update()
    return report


def export(scene,root,name):
    objects={root,*root.children_recursive}
    for obj in scene.objects: obj.select_set(obj in objects)
    bpy.context.view_layer.objects.active=root
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'.glb')),export_format='GLB',use_selection=True,
        export_yup=True,export_extras=True,export_animations=True,export_morph=True,
        export_animation_mode='ACTIVE_ACTIONS',export_merge_animation='ACTION',
        export_nla_strips_merged_animation_name='Bow_Use',export_frame_range=True,
        export_force_sampling=True,export_cameras=False,export_lights=False)
    bpy.ops.export_scene.fbx(filepath=str(OUT/(name+'.fbx')),use_selection=True,
        object_types={'EMPTY','MESH'},axis_forward='-Z',axis_up='Y',global_scale=1,
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',bake_space_transform=False,
        use_mesh_modifiers=False,use_custom_props=True,bake_anim=True,
        bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True,bake_anim_step=1,bake_anim_simplify_factor=0,
        add_leaf_bones=False)


def preview(scene,root):
    coll=bpy.data.collections.new('BW_ACTION_PREVIEW'); scene.collection.children.link(coll)
    data=bpy.data.cameras.new('BW_ActionCamera'); camera=bpy.data.objects.new(data.name,data); coll.objects.link(camera)
    target=Vector((0,-.08,0)); camera.location=target+Vector((1,-1,.5))
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    data.type='ORTHO'; data.ortho_scale=1.65
    scene.camera=camera; scene.render.resolution_x=900; scene.render.resolution_y=640
    scene.cycles.samples=16
    out=OUT/'animation_frames'; out.mkdir(exist_ok=True)
    for frame in (1,16,31,43,44,48,79,97):
        scene.frame_set(frame); scene.render.filepath=str(out/('bow_%03d.png'%frame))
        if not os.environ.get('TOOLGEN_NO_RENDER'):
            bpy.ops.render.render(write_still=True)


def main():
    for suffix,factor in (('',1),('_FPS',1.5)):
        name='CubeEscape_Bow_Standard'+suffix
        bpy.ops.wm.open_mainfile(filepath=str(OUT/(name+'.blend')))
        scene=bpy.context.scene; root=scene.objects[name]
        setup(scene,root,factor)
        motion=check_motion(scene,root,factor)
        key='_fps' if suffix else ''
        (OUT/('qa_animation'+key+'.json')).write_text(json.dumps(motion,indent=2)+'\n')
        geo_path=OUT/('qa_geometry'+key+'.json'); geo=json.loads(geo_path.read_text())
        geo['sockets']['Socket_ArrowTip']=list(find(scene,'Socket_ArrowTip').matrix_world.translation)
        geo_path.write_text(json.dumps(geo,indent=2)+'\n')
        export(scene,root,name)
        scene.frame_set(1); bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(name+'.blend')))
        if not suffix and '--no-preview' not in sys.argv: preview(scene,root)
        print('BOW_MOTION_OK',name,motion['morph_meshes'])
    contract={'clip':'Bow_Use','autoplay':False,'loop':False,'duration_seconds':4,
        'trigger':'explicit ShootAction','default_state':'Idle_Loaded',
        'phases_seconds':{'draw':[0,1.25],'hold':[1.25,1.75],'release':[1.75,1.9583],'reset':[1.9583,3.25],'idle':[3.25,4]},
        'release_event_seconds':43/24,
        'projectile':'Spawn the separate standard arrow through the game action at Socket_ArrowTip; no projectile physics is implemented.',
        'visibility':'LoadedArrowPresence uses scale 0.001 while the model arrow is inactive; rest and authored mesh scales are 1.'}
    (OUT/'action_contract.json').write_text(json.dumps(contract,indent=2)+'\n')


if __name__=='__main__': main()
