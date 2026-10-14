"""Build a large camera-mounted FPS variant from the verified base asset.

Blender coordinates: camera looks -Y with Z up (screen right is -X). The camera attachment
root stays at zero. Presentation and test-room geometry never enter exports.
"""
import argparse
import json
import math
from pathlib import Path
import runpy
import sys

import bpy
from mathutils import Matrix, Vector, Quaternion
from bpy_extras.object_utils import world_to_camera_view

NAME='CubeEscape_Bow_Standard_FPS'
ENLARGEMENT=1.5
HAND_POSITION=Vector((-.26,-.66,-.50))
AIM_TARGET=Vector((0,-4,0))
HORIZONTAL_FOV=75


def depth(obj):
    count=0
    while obj.parent:
        count+=1; obj=obj.parent
    return count


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    out=args.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    source=out/'CubeEscape_Bow_Standard.blend'
    assert source.is_file(), 'Build the base asset first'
    (out/'build_complete_fps.json').unlink(missing_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    original=bpy.context.scene
    source_root=original.objects['CubeEscape_Bow_Standard']
    source_objects=[source_root]+list(source_root.children_recursive)
    source_hand=original.objects['Socket_Hand'].matrix_world.translation.copy()
    aim_delta=AIM_TARGET-HAND_POSITION
    bore_height=(original.objects['Socket_Muzzle'].matrix_world.translation.z-source_hand.z)*ENLARGEMENT
    distance=math.sqrt(aim_delta.length_squared-bore_height*bore_height)
    rotation=aim_delta.to_track_quat('-Y','Z') @ Quaternion(Vector((1,0,0)),math.atan2(bore_height,distance))
    transform=Matrix.Translation(HAND_POSITION) @ rotation.to_matrix().to_4x4() @ Matrix.Scale(ENLARGEMENT,4) @ Matrix.Translation(-source_hand)
    source_world={o:o.matrix_world.copy() for o in source_objects}
    scene=bpy.data.scenes.new(NAME)
    bpy.context.window.scene=scene
    scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1
    geo=bpy.data.collections.new('BW_FPS_GEOMETRY'); scene.collection.children.link(geo)
    root=bpy.data.objects.new(NAME,None); geo.objects.link(root)
    root['ce_category']='Interactive'; root['ce_variant']='first_person_large'
    root['ce_camera_attachment']='origin, identity transform; forward -Y, up Z'
    root.empty_display_size=.05
    objects=[root]; mapping={source_root:root}
    for old in sorted((o for o in source_objects if o!=source_root),key=depth):
        new=old.copy()
        new.animation_data_clear()
        if old.type=='MESH':
            new.data=old.data.copy()
            new.data.transform(Matrix.Scale(ENLARGEMENT,4),shape_keys=True)
            if new.data.shape_keys: new.data.shape_keys.animation_data_clear()
        geo.objects.link(new); mapping[old]=new
        new.parent=mapping[old.parent]
        loc,quat,_scale=(transform@source_world[old]).decompose()
        new.matrix_world=Matrix.LocRotScale(loc,quat,Vector((1,1,1)))
        # Parent-space decomposition can introduce tiny floating-point scale drift.
        new.scale=(1,1,1)
        bpy.context.view_layer.update()
        objects.append(new)
    # Drop the source scene and its objects; copied FPS meshes/materials stay intact.
    old_objects=list(original.objects)
    bpy.data.scenes.remove(original)
    for old in old_objects:
        if not old.users_scene:
            bpy.data.objects.remove(old,do_unlink=True)
    # Restore stable semantic names after releasing originals.
    for old,new in list(mapping.items())[1:]:
        new.name=new.name.removesuffix('.001')
    socket=bpy.data.objects.new('Socket_Camera',None); geo.objects.link(socket)
    socket.parent=root; socket.empty_display_size=.06; objects.append(socket)
    helper=runpy.run_path(str(Path(__file__).with_name('bow_geometry.py')))
    state=helper['validate'].__globals__
    state.update(ASSET=NAME,OBJECTS=objects,ROOT=root,GEO=geo)
    qa=helper['validate']()
    qa.update(variant='first_person_large',enlargement=ENLARGEMENT,
              pivot='camera attachment at origin; all export object scales are 1',
              camera={'horizontal_fov_degrees':HORIZONTAL_FOV,'near_m':.03,
                      'hand_position_blender_m':list(HAND_POSITION),
                      'hand_position_unity_m':[HAND_POSITION.x,HAND_POSITION.z,-HAND_POSITION.y],
                      'aim_target_blender_m':list(AIM_TARGET),
                      'note':'Camera offset and enlargement are already baked; attach root with identity transform.'})
    qa['tags'].append('first-person-large')
    camera,_=helper['presentation'](scene)
    camera.location=(0,0,0)
    camera.rotation_euler=Vector((0,-1,0)).to_track_quat('-Z','Y').to_euler()
    camera.data.type='PERSP'; camera.data.sensor_fit='HORIZONTAL'
    camera.data.sensor_width=36
    camera.data.lens=36/(2*math.tan(math.radians(HORIZONTAL_FOV)/2))
    camera.data.clip_start=.03; camera.data.clip_end=100
    scene.render.resolution_x=1600; scene.render.resolution_y=900
    present=state['PRESENT']
    state['MATS']={}
    for ob in objects:
        if ob.type=='MESH':
            for mat in ob.data.materials:
                state['MATS'][mat.name.removeprefix('BW_')]=mat
    helper['material']('Room',(.025,.04,.055),.05,.8)
    helper['material']('RoomPanel',(.05,.075,.09),.2,.65)
    helper['material']('TargetLight',(.018,.33,.48),.1,.3,1.3)
    helper['material']('Floor',(.045,.058,.068),.0,.7)
    # A restrained test room supplies depth cues, not a claim of game integration.
    def prop(name,center,size,material,bevel=.02):
        before=len(objects)
        obj=helper['box']('Preview_'+name,center,size,material,bevel,parent=root)
        objects.pop()
        assert len(objects)==before
        obj.parent=None
        geo.objects.unlink(obj); present.objects.link(obj)
        return obj
    prop('Floor',(0,-5,-1.60),(20,20,.10),'Floor')
    prop('Wall',(0,-7,1.25),(12,.2,5.7),'Room')
    for x in range(-5,6):
        prop('WallRib_'+str(x),(x,-6.85,1.15),(.022,.10,5.2),'RoomPanel',.005)
    for z in (-1.,0.,1.,2.,3.):
        prop('WallSeam_'+str(z),(0,-6.82,z),(12,.08,.012),'RoomPanel',.003)
    for y in (-2,-4,-6,-8):
        prop('FloorSeam_'+str(y),(0,y,-1.543),(12,.015,.009),'RoomPanel',.003)
    for x in (-2,0,2):
        prop('FloorLine_'+str(x),(x,-5,-1.543),(.012,9,.009),'RoomPanel',.003)
    prop('Crate',(-1.35,-4,-1.03),(.85,.75,1.02),'RoomPanel',.055)
    prop('CrateTrim',(-1.35,-3.61,-1.03),(.65,.025,.025),'TargetLight',.005)
    for s in (-1,1):
        prop('LightColumn_'+str(s),(s*2.8,-6.68,.7),(.035,.045,3.4),'TargetLight',.008)
    # Small reticle in the presentation only, located at the actual aiming target.
    for axis,size in [('H',(.038,.006,.006)),('V',(.006,.006,.038))]:
        prop('Reticle_'+axis,(0,-4,0),size,'TargetLight',.001)
    # Separate hero camera permits inspection of the large variant independently.
    hero_data=bpy.data.cameras.new('BW_FPS_HeroCamera')
    hero=bpy.data.objects.new(hero_data.name,hero_data); present.objects.link(hero)
    center=sum((Vector(qa['bounds_m'][0]),Vector(qa['bounds_m'][1])),Vector())/2
    hero.location=center+Vector((1.4,-1.3,.9)); hero.rotation_euler=(center-hero.location).to_track_quat('-Z','Y').to_euler()
    hero_data.type='ORTHO'; hero_data.ortho_scale=2.45
    scene.camera=camera
    bpy.context.view_layer.update()
    projected=[world_to_camera_view(scene,camera,o.matrix_world@v.co) for o in objects if o.type=='MESH' for v in o.data.vertices]
    assert all(p.z>camera.data.clip_start for p in projected), 'Weapon crosses near clipping plane'
    assert min(p.x for p in projected)>.5, 'Weapon must be in the right half of the image'
    qa['framing']={'min_camera_depth_m':min(p.z for p in projected),
                   'screen_bounds_normalized':[[min(p[i] for p in projected) for i in (0,1)],
                                               [max(p[i] for p in projected) for i in (0,1)]],
                   'reticle_clear':True,'render_resolution':[1600,900]}
    muzzle=next(o for o in objects if o.name=='Socket_Muzzle').matrix_world.translation
    firing_direction=rotation@Vector((0,-1,0))
    aim_error=((AIM_TARGET-muzzle).cross(firing_direction)).length
    assert aim_error<1e-5, 'Muzzle ray misses the reticle'
    qa['framing']['muzzle_ray_error_m']=aim_error
    # Keep the aiming region clear. Intentionally allow a cropped grip at the lower edge.
    for o in objects:
        if o.type=='MESH':
            for v in o.data.vertices:
                p=world_to_camera_view(scene,camera,o.matrix_world@v.co)
                assert not (.46<p.x<.54 and .46<p.y<.54),'Weapon covers central aiming area'
    (out/'qa_geometry_fps.json').write_text(json.dumps(qa,indent=2)+'\n')
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA'
                area.spaces.active.shading.type='MATERIAL'
    for obj in present.objects:
        obj.hide_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/(NAME+'.blend')))
    helper['export'](out)
    scene.render.filepath=str(out/'preview_first_person.png')
    bpy.ops.render.render(write_still=True)
    # A hero view excludes the test room and uses the studio world and lamps.
    for obj in present.objects:
        if obj.name.startswith('SM_BW_Preview_'):
            obj.hide_render=True
    scene.camera=hero; scene.render.resolution_x=1400; scene.render.resolution_y=1000
    scene.render.filepath=str(out/'preview_large.png')
    bpy.ops.render.render(write_still=True)
    print('STANDARD_BOW_FPS_BUILD_OK',json.dumps(qa))


if __name__=='__main__':
    main()
