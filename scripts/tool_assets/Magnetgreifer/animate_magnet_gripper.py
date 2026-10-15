"""Add one-shot grip and axial spin to both asset variants; no autoplay.

Build static variants first. This post-process runs in a background Blender
instance, saves frame 1, and exports active actions as one clip named MG_Apply.
"""
import json
import math
from pathlib import Path
import sys

import bpy
import os
from mathutils import Matrix, Vector

OUT=Path(__file__).resolve().parent
FRAMES=(1,13,28,43,58,73,85,97)
FPS=24
CLOSE_DEGREES=5


def all_curves(action):
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves


def track(obj,axis,keys,name):
    previous=obj.animation_data.action if obj.animation_data else None
    obj.animation_data_clear()
    if previous and previous.users==0:
        bpy.data.actions.remove(previous)
    obj.rotation_mode='XYZ'
    obj.rotation_euler=(0,0,0)
    for frame,value in keys:
        obj.rotation_euler[axis]=value
        obj.keyframe_insert(data_path='rotation_euler',index=axis,frame=frame,group='MG_Apply')
    action=obj.animation_data.action
    action.name=name
    action.use_frame_range=True; action.frame_start=1; action.frame_end=97
    action.use_cyclic=False
    action['ce_loop']=False; action['ce_autoplay']=False; action['ce_trigger']='GrabAction'
    for curve in all_curves(action):
        for key in curve.keyframe_points:
            key.interpolation='BEZIER'
            key.handle_left_type='AUTO_CLAMPED'; key.handle_right_type='AUTO_CLAMPED'


def owned(scene,name):
    return next(o for o in scene.objects if o.name.split('.')[0]==name)


def setup(scene,root):
    scene.frame_set(1)
    upper=owned(scene,'Pivot_Upper'); lower=owned(scene,'Pivot_Lower')
    core=owned(scene,'SM_MG_MagnetCoreMount')
    grab=owned(scene,'Socket_Grab')
    worlds={o:o.matrix_world.copy() for o in (upper,lower,grab)}
    center=(upper.matrix_world.translation+lower.matrix_world.translation)/2
    coll=root.users_collection[0]
    mount=scene.objects.get('Pivot_MagnetAxis')
    if mount is None:
        mount=bpy.data.objects.new('Pivot_MagnetAxis',None); coll.objects.link(mount)
    mount.parent=root
    mount.matrix_world=Matrix.LocRotScale(center,core.matrix_world.to_quaternion(),Vector((1,1,1)))
    mount.scale=(1,1,1)
    spin=scene.objects.get('Pivot_HeadSpin')
    if spin is None:
        spin=bpy.data.objects.new('Pivot_HeadSpin',None); coll.objects.link(spin)
    spin.parent=mount
    spin.empty_display_size=.035; spin['ce_role']='interactive'; spin['ce_axis']='local Y'
    bpy.context.view_layer.update()
    for obj,world in worlds.items():
        obj.parent=spin; obj.matrix_world=world; obj.scale=(1,1,1)
        bpy.context.view_layer.update()
    angle=math.radians(CLOSE_DEGREES)
    for obj,sign in ((upper,1),(lower,-1)):
        track(obj,0,[(1,0),(13,sign*angle),(73,sign*angle),(85,0),(97,0)],'MG_Apply_'+obj.name)
    track(spin,1,[(1,0),(13,0),(73,2*math.pi),(97,2*math.pi)],'MG_Apply_Spin')
    scene.frame_start=1; scene.frame_end=97; scene.render.fps=FPS
    root['ce_action_clip']='MG_Apply'; root['ce_autoplay']=False; root['ce_loop']=False
    root['ce_default_state']='Idle_Open'; root['ce_trigger']='explicit GrabAction'
    scene.frame_set(1); bpy.context.view_layer.update()
    return mount,spin,upper,lower


def matrix_record(obj):
    return [list(row) for row in obj.matrix_world]


def motion_qa(scene,root):
    spin=owned(scene,'Pivot_HeadSpin')
    targets=['Pivot_HeadSpin','Pivot_Upper','Pivot_Lower','Socket_Grab','Socket_Muzzle','Socket_Hand','SM_MG_MagnetCoreMount']
    report={'clip':'MG_Apply','fps':FPS,'frame_start':1,'frame_end':97,
            'duration_seconds':4,'loop':False,'autoplay':False,
            'default_state':'Idle_Open','trigger':'explicit GrabAction',
            'closure_degrees':CLOSE_DEGREES,'spin_degrees':360,'poses':{},
            'min_contact_gap_m':float('inf')}
    core_start=owned(scene,'SM_MG_MagnetCoreMount').matrix_world.copy()
    frame_camera=scene.camera if root.name.endswith('_FPS') else None
    if frame_camera:
        from bpy_extras.object_utils import world_to_camera_view
        fps_min_depth=float('inf')
    # Check every frame. Contact gap is measured in the rotating head's space,
    # so a full axial turn does not change the meaning of upper/lower contacts.
    for frame in range(1,98):
        scene.frame_set(frame); bpy.context.view_layer.update()
        inverse=spin.matrix_world.inverted()
        contact={}
        for side in ('Upper','Lower'):
            parts=[o for o in root.children_recursive if o.type=='MESH' and
                   o.name.startswith('SM_MG_'+side+'Contact')]
            zvalues=[(inverse@o.matrix_world@v.co).z for o in parts for v in o.data.vertices]
            contact[side]=min(zvalues) if side=='Upper' else max(zvalues)
        gap=contact['Upper']-contact['Lower']
        assert gap>.001, ('Gripping pads intersect',frame,gap)
        report['min_contact_gap_m']=min(report['min_contact_gap_m'],gap)
        assert max(abs(core_start[i][j]-owned(scene,'SM_MG_MagnetCoreMount').matrix_world[i][j]) for i in range(4) for j in range(4))<1e-6
        if frame_camera:
            for side in ('Pivot_Upper','Pivot_Lower'):
                pivot=owned(scene,side)
                for obj in pivot.children_recursive:
                    if obj.type=='MESH':
                        for v in obj.data.vertices:
                            p=world_to_camera_view(scene,frame_camera,obj.matrix_world@v.co)
                            assert p.z>frame_camera.data.clip_start
                            assert not (.47<p.x<.53 and .47<p.y<.53), ('Animated jaw covers reticle',frame)
                            fps_min_depth=min(fps_min_depth,p.z)
        if frame in FRAMES:
            report['poses'][str(frame)]={name:matrix_record(owned(scene,name)) for name in targets}
    if frame_camera:
        report['animated_fps_min_depth_m']=fps_min_depth
        report['animated_reticle_clear']=True
    # A 360-degree final turn has the same rest orientation as the initial pose.
    for name in targets:
        a=report['poses']['1'][name]; b=report['poses']['97'][name]
        assert max(abs(a[i][j]-b[i][j]) for i in range(4) for j in range(4))<1e-5
    scene.frame_set(1); bpy.context.view_layer.update()
    return report


def exports(name,root):
    objects={root,*root.children_recursive}
    for obj in bpy.context.scene.objects:
        obj.select_set(obj in objects)
    bpy.context.view_layer.objects.active=root
    kwargs={'filepath':str(OUT/(name+'.glb')),'export_format':'GLB','use_selection':True,
            'export_yup':True,'export_extras':True,'export_animations':True,
            'export_animation_mode':'ACTIVE_ACTIONS','export_merge_animation':'ACTION',
            'export_nla_strips_merged_animation_name':'MG_Apply','export_frame_range':True,
            'export_force_sampling':True,'export_cameras':False,'export_lights':False}
    props=bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    assert all(k in props for k in kwargs)
    assert 'FINISHED' in bpy.ops.export_scene.gltf(**kwargs)
    assert 'FINISHED' in bpy.ops.export_scene.fbx(
        filepath=str(OUT/(name+'.fbx')),use_selection=True,object_types={'EMPTY','MESH'},
        axis_forward='-Z',axis_up='Y',global_scale=1,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',bake_space_transform=False,
        use_mesh_modifiers=True,use_custom_props=True,bake_anim=True,
        bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True,bake_anim_step=1,
        bake_anim_simplify_factor=0,add_leaf_bones=False)


def preview(scene,root):
    # A static studio camera reveals both articulation and the shared spin axis.
    coll=bpy.data.collections.new('MG_ANIMATION_PREVIEW'); scene.collection.children.link(coll)
    data=bpy.data.cameras.new('MG_AnimationCamera'); camera=bpy.data.objects.new(data.name,data); coll.objects.link(camera)
    center=Vector((0,-.10,.078)); camera.location=center+Vector((.9,-.8,.52))
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    data.type='ORTHO'; data.ortho_scale=.85
    scene.camera=camera; scene.render.resolution_x=900; scene.render.resolution_y=640
    scene.cycles.samples=16
    frames=OUT/'animation_frames'; frames.mkdir(exist_ok=True)
    for frame in FRAMES:
        scene.frame_set(frame); scene.render.filepath=str(frames/('apply_%03d.png'%frame))
        if not os.environ.get('TOOLGEN_NO_RENDER'):
            bpy.ops.render.render(write_still=True)
    scene.frame_set(1)


def main():
    assert bpy.app.background, 'Run the animation builder in a background Blender instance'
    for suffix in ('','_FPS'):
        name='CubeEscape_MagnetGripper'+suffix
        bpy.ops.wm.open_mainfile(filepath=str(OUT/(name+'.blend')))
        scene=bpy.context.scene; root=scene.objects[name]
        setup(scene,root)
        qa=motion_qa(scene,root)
        key='_fps' if suffix else ''
        (OUT/('qa_animation'+key+'.json')).write_text(json.dumps(qa,indent=2)+'\n')
        exports(name,root)
        scene.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(name+'.blend')))
        if not suffix and '--no-preview' not in sys.argv:
            preview(scene,root)
        print('MAGNET_ONE_SHOT_ANIMATION_OK',suffix,qa['min_contact_gap_m'])
    contract={'default_state':'Idle_Open','auto_play':False,'loop':False,
              'clip':'MG_Apply','duration_seconds':4,'trigger':'GrabAction',
              'timing_seconds':{'close':[0,.5],'rotate_360':[.5,3],'open':[3,3.5],'rest':[3.5,4]},
              'runtime':'Use the supplied action player or explicitly play the imported clip once; do not use an autoplay loop.'}
    (OUT/'action_contract.json').write_text(json.dumps(contract,indent=2)+'\n')


if __name__=='__main__':
    main()
