"""Cube Escape standard bow and standard arrow; Blender 5.2.2 CLI."""
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Matrix,Vector

ROOT_DIR=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT_DIR))
import bow_geometry as g

NAME='CubeEscape_Bow_Standard'
NOCK=Vector((0,.15,.065))
DRAW_NOCK=Vector((0,.38,.065))


def material_library():
    for key,pal,metal,rough,emit in [
        ('Armor','armor',.42,.30,0),('AccentArmor','armor',.42,.30,0),
        ('Dark','mech',.70,.39,0),('Metal','metal',.60,.31,0),
        ('Visor','visor',.25,.25,0),('Cyan','eye',.15,.24,3),
        ('Amber','accent',.1,.3,1.5)]:
        g.material(key,g.PALETTE[pal],metal,rough,emit)
    g.material('Rubber',(.017,.022,.027),0,.75)
    g.material('PaleCyan',(.36,.91,1),.05,.25,1.5)


def bent(co):
    p=co.copy(); u=min(1,abs(p.z)/.49)
    p.y+=.07*u*u; p.z*=1-.035*u*u
    return p


def shape(obj,mapper):
    bpy.context.view_layer.update()
    obj.shape_key_add(name='Basis')
    key=obj.shape_key_add(name='Draw')
    inv=obj.matrix_world.inverted()
    for source,target in zip(obj.data.vertices,key.data):
        target.co=inv@mapper(obj.matrix_world@source.co)
    key.value=0
    obj.active_shape_key_index=0
    obj['bow_flex']=True


def cable(name,a,b,draw_a,draw_b):
    bm=bmesh.new(); delta=b-a
    bmesh.ops.create_cone(bm,cap_ends=True,cap_tris=False,segments=8,
                         radius1=.0017,radius2=.0017,depth=delta.length)
    q=Vector((0,0,1)).rotation_difference(delta)
    for v in bm.verts:
        v.co=q@v.co+(a+b)/2
    obj=g.mesh(name,bm,(0,0,0),'Cyan',g.ROOT)
    # Affine mapping pins both end rings to the moving limb tip and nock.
    def move(p):
        t=(p-a).dot(delta)/delta.length_squared
        return p+(draw_a-a)*(1-t)+(draw_b-b)*t
    shape(obj,move)
    return obj


def arrow(parent,prefix):
    g.cylinder(prefix+'Shaft',(0,-.34,0),.0036,.64,'Dark',parent=parent,n=16,bevel=.0005)
    for y in (-.02,-.05,-.60):
        g.cylinder(prefix+'Band'+str(y),(0,y,0),.005,.013,'Metal',parent=parent,n=12,bevel=.001)
    g.box(prefix+'Nock',(0,.006,0),(.010,.022,.010),'Amber',.002,parent=parent)
    bm=bmesh.new()
    verts=[bm.verts.new(p) for p in [(-.016,-.63,-.006),(.016,-.63,-.006),
           (.016,-.63,.006),(-.016,-.63,.006),(0,-.715,0)]]
    bm.faces.new((verts[3],verts[2],verts[1],verts[0]))
    for i in range(4):
        bm.faces.new((verts[i],verts[(i+1)%4],verts[4]))
    g.mesh(prefix+'Head',bm,(0,0,0),'Metal',parent,bevel=.0004,segments=1)
    for i in range(3):
        feather=g.prism(prefix+'Fletching'+str(i),[(-.035,.005),(-.062,.026),(-.155,.020),(-.17,.005)],.0025,'Armor',parent)
        feather.data.transform(Matrix.Rotation(2*math.pi*i/3,4,'Y'))
        # A shared parent at zero keeps the standalone arrow root at its nock.


def build_bow():
    g.box('Grip',(0,-.015,-.035),(.055,.065,.15),'Rubber',.013)
    for i in range(4):
        g.box('GripRib'+str(i),(0,-.051,-.082+i*.026),(.049,.007,.008),'Dark',.002)
    g.box('RiserWindowSide',(.050,-.010,.081),(.033,.090,.156),'Dark',.011)
    g.box('RiserWindowArmor',(.069,-.012,.092),(.013,.077,.11),'Armor',.006)
    for s in (-1,1):
        g.box('RiserCollar'+str(s),(0,-.014,s*.175),(.103,.096,.113),'Dark',.016)
        g.box('RiserArmor'+str(s),(0,-.044,s*.175),(.110,.043,.090),'Armor',.012)
        for x in (-.042,.042):
            g.cylinder('RiserBolt'+str(s)+str(x),(x,-.068,s*.175),.004,.004,'Metal',n=12,bevel=.0006)
    g.box('ControlModule',(.079,.005,.012),(.075,.095,.094),'Dark',.014)
    g.box('ControlShell',(.087,-.038,.012),(.060,.016,.073),'Armor',.006)
    g.box('StatusBezel',(.119,.005,.012),(.013,.066,.069),'Visor',.006)
    g.box('StatusDisplay',(.127,.005,.012),(.004,.046,.048),'Cyan',.003)
    for i in range(3):
        g.box('StatusBar'+str(i),(.130,.006,-.002+i*.013),(.002,.031-i*.004,.003),'PaleCyan',.0006)
    g.cylinder('StatusAmber',(.131,-.024,.034),.003,.002,'Amber',axis=(1,0,0),n=12,bevel=.0004)
    g.box('ArrowRest',(0,-.01,.052),(.034,.060,.009),'Metal',.003)
    g.box('ArrowRestPad',(0,-.01,.058),(.018,.047,.004),'Rubber',.001)
    profile=[(-.023,.202),(-.037,.265),(.002,.354),(.075,.449),(.146,.501),
             (.168,.482),(.111,.424),(.055,.333),(.023,.259),(.027,.204)]
    armor=[(-.027,.246),(-.021,.277),(.014,.352),(.064,.416),(.085,.405),
           (.040,.329),(.012,.263)]
    upper=[(.067,.425),(.132,.487),(.150,.477),(.099,.416)]
    for s,label in [(1,'Upper'),(-1,'Lower')]:
        before=len(g.OBJECTS)
        g.prism(label+'LimbSpine',[(y,s*z) for y,z in profile],.037,'Dark',g.ROOT)
        g.prism(label+'LimbArmor',[(y,s*z) for y,z in armor],.045,'Armor',g.ROOT)
        g.prism(label+'TipArmor',[(y,s*z) for y,z in upper],.042,'Armor',g.ROOT)
        for z,y in ((.277,-.010),(.417,.078)):
            g.cylinder(label+'LimbJoint'+str(z),(0,y,s*z),.020,.054,'Dark',axis=(1,0,0),n=24,bevel=.002)
            for side in (-1,1):
                g.cylinder(label+'JointCap'+str(z)+str(side),(side*.030,y,s*z),.012,.008,'Metal',axis=(1,0,0),n=16)
        tip=Vector((0,.15,s*.49))
        g.cylinder(label+'TipCam',tip,.025,.040,'Dark',axis=(1,0,0),n=32,bevel=.003)
        for side in (-1,1):
            g.cylinder(label+'CamHub'+str(side),(side*.023,.15,s*.49),.010,.007,'Metal',axis=(1,0,0),n=16)
        g.box(label+'LimbStatus',(0,.037,s*.355),(.027,.008,.037),'Cyan',.002)
        for obj in g.OBJECTS[before:]:
            if obj.type=='MESH': shape(obj,bent)
        cable(label+'Bowstring',tip,NOCK,bent(tip),DRAW_NOCK)
    presence=g.empty('LoadedArrowPresence',g.GEO,g.ROOT)
    carrier=g.empty('ArrowCarrier',g.GEO,presence,NOCK)
    bpy.context.view_layer.update()
    # Arrow helper accepts world coordinates, so construct locally then offset
    # mesh origins only; all original arrow geometry is reusable at its nock.
    before=len(g.OBJECTS); arrow(carrier,'Arrow_')
    for obj in g.OBJECTS[before:]: obj.location+=NOCK
    bpy.context.view_layer.update()
    assert (bpy.context.scene.objects['SM_BW_Arrow_Nock'].matrix_world.translation-(NOCK+Vector((0,.006,0)))).length<1e-6
    g.empty('Socket_Hand',g.GEO,g.ROOT)
    g.empty('Socket_SupportHand',g.GEO,g.ROOT,(0,.15,.065))
    g.empty('Socket_Nock',g.GEO,g.ROOT,NOCK)
    g.empty('Socket_Muzzle',g.GEO,g.ROOT,(0,-.12,.065))
    g.empty('Socket_ArrowTip',g.GEO,g.ROOT,(0,NOCK.y-.715,.065))
    return carrier


def save_asset(scene,name,filename):
    bpy.context.view_layer.update()
    qa=g.validate(); qa['asset']=name
    qa['purpose']='standard bow with flexing limbs and string' if name==NAME else 'standalone standard arrow; nock origin'
    (ROOT_DIR/filename).write_text(json.dumps(qa,indent=2)+'\n')
    g.ASSET=name; g.export(ROOT_DIR)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT_DIR/(name+'.blend')))
    return qa


def main():
    assert bpy.app.background, 'Run this generator in a background Blender instance'
    assert bpy.app.version==(5,2,2)
    scene=bpy.data.scenes.new(NAME); bpy.context.window.scene=scene
    for old in list(bpy.data.scenes):
        if old!=scene:
            objects=list(old.objects); bpy.data.scenes.remove(old)
            for obj in objects:
                if not obj.users_scene: bpy.data.objects.remove(obj,do_unlink=True)
    scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1
    g.GEO=g.collection('BW_GEOMETRY',scene.collection); g.ROOT=g.empty(NAME,g.GEO)
    g.ROOT['ce_category']='Interactive'; g.ROOT['ce_forward']='-Y'
    material_library(); carrier=build_bow(); bpy.context.view_layer.update()
    cam,target=g.presentation(scene); target=Vector((0,-.10,0))
    cam.location=target+Vector((1,-1,.5)); cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.ortho_scale=1.65
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_location=target
                area.spaces.active.region_3d.view_distance=1.6
                area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
                area.spaces.active.shading.type='MATERIAL'
    save_asset(scene,NAME,'qa_geometry.json')
    for filename,offset in [('preview_white.png',(1,-1,.5)),('view_side.png',(1,0,0)),('view_front.png',(0,-1,0))]:
        g.render(scene,cam,target,ROOT_DIR/filename,offset,1.65)
    # Independent arrow, with no bow, camera or extra geometry in its exports.
    arrow_scene=bpy.data.scenes.new('CubeEscape_Arrow_Standard'); bpy.context.window.scene=arrow_scene
    arrow_scene.unit_settings.system='METRIC'; arrow_scene.unit_settings.scale_length=1
    g.OBJECTS=[]; g.GEO=g.collection('BW_ARROW_GEOMETRY',arrow_scene.collection)
    g.ROOT=g.empty('CubeEscape_Arrow_Standard',g.GEO); arrow(g.ROOT,'Arrow_')
    g.empty('Socket_Nock',g.GEO,g.ROOT)
    g.empty('Socket_Tip',g.GEO,g.ROOT,(0,-.715,0))
    for old in list(bpy.data.scenes):
        if old!=arrow_scene:
            objects=list(old.objects); bpy.data.scenes.remove(old)
            for obj in objects:
                if not obj.users_scene: bpy.data.objects.remove(obj,do_unlink=True)
    for obj in g.OBJECTS:
        obj.name=obj.name.removesuffix('.001')
    save_asset(arrow_scene,'CubeEscape_Arrow_Standard','qa_arrow.json')
    print('STANDARD_BOW_AND_ARROW_OK')


if __name__=='__main__': main()
