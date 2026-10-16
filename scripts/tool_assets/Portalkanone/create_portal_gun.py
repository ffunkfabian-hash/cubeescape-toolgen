"""Deterministic Cube Escape portal gun. Blender 5.2.2, meters, forward -Y.

Run: Blender --background --factory-startup --python-exit-code 1
     --python create_portal_gun.py -- --output <directory>
Only the generated scene is replaced; other open scenes are preserved.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import os
import bmesh
from mathutils import Vector, Matrix
from design_profiles import slim_housing

ASSET = 'CubeEscape_PortalGun'
PALETTE = {'armor': (.66, .685, .72), 'mech': (.075, .08, .092),
           'metal': (.38, .395, .42), 'eye': (.02, .62, .95),
           'visor': (.006, .007, .01), 'accent': (1., .38, .05)}
MATS, OBJECTS = {}, []


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def collection(name, parent):
    coll = bpy.data.collections.new(name)
    parent.children.link(coll)
    return coll


def empty(name, coll, parent=None, loc=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    coll.objects.link(obj)
    obj.parent = parent
    obj.location = loc
    obj.empty_display_size = .025
    OBJECTS.append(obj)
    return obj


def material(name, rgb, metal=.0, rough=.3, emission=0):
    mat = bpy.data.materials.new('PG_' + name)
    if not mat.node_tree:
        mat.use_nodes = True
    mat.diffuse_color = (*rgb, 1)
    bs = mat.node_tree.nodes.get('Principled BSDF')
    for key, value in [('Base Color', (*rgb, 1)), ('Metallic', metal),
                       ('Roughness', rough), ('Emission Color', (*rgb, 1)),
                       ('Emission Strength', emission)]:
        require(key in bs.inputs, f'Missing shader socket: {key}')
        bs.inputs[key].default_value = value
    MATS[name] = mat
    return mat


def mesh(name, bm, loc, mat, parent, bevel=0, segments=3, coll=None):
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if bevel:
        edges=[e for e in bm.edges if e.is_manifold and e.calc_face_angle()>.7]
        bmesh.ops.bevel(bm, geom=edges, offset=bevel,
                        segments=segments, profile=.5, affect='EDGES', clamp_overlap=True)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # Smooth curved transitions, preserve the planar faces of plates and caps.
    for face in bm.faces:
        face.smooth = max(abs(c) for c in face.normal) < .99999
    data = bpy.data.meshes.new('ME_PG_' + name)
    bm.to_mesh(data)
    bm.free()
    data.update()
    require(not data.validate(), 'Invalid mesh: ' + name)
    obj = bpy.data.objects.new('SM_PG_' + name, data)
    (coll or GEO).objects.link(obj)
    obj.parent = parent
    obj.location = Vector(loc) - parent.matrix_world.translation if parent else loc
    data.materials.append(MATS[mat])
    obj['ce_role'] = 'neon' if mat in ('Cyan', 'Amber') else 'static'
    obj['ce_component'] = name
    # Explicit per-face box projection; intentionally reused islands, no lightmap claim.
    uv = data.uv_layers.new(name='UVMap')
    mins = [min(v.co[i] for v in data.vertices) for i in range(3)]
    maxs = [max(v.co[i] for v in data.vertices) for i in range(3)]
    for poly in data.polygons:
        major = max(range(3), key=lambda i: abs(poly.normal[i]))
        axes = ((1, 2), (0, 2), (0, 1))[major]
        for li in poly.loop_indices:
            co = data.vertices[data.loops[li].vertex_index].co
            uv.data[li].uv = [(co[i]-mins[i])/(maxs[i]-mins[i]) for i in axes]
    OBJECTS.append(obj)
    return obj


def box(name, center, size, mat='Armor', bevel=.008, parent=None, rot=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts:
        v.co = Vector([v.co[i]*size[i] for i in range(3)])
        if rot:
            v.co = rot @ v.co
    return mesh(name, bm, center, mat, parent or ROOT, min(bevel, min(size)*.45))


def cylinder(name, center, radius, depth, mat, axis=(0, 1, 0), bevel=.0015,
             parent=None, n=32):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=n,
                         radius1=radius, radius2=radius, depth=depth)
    q = Vector((0, 0, 1)).rotation_difference(Vector(axis))
    for v in bm.verts:
        v.co = q @ v.co
    return mesh(name, bm, center, mat, parent or ROOT, min(bevel, depth*.4, radius*.3), 2)


def ring(name, y, outer, inner, depth, mat, z=.084, parent=None, n=64):
    bm = bmesh.new()
    rings = []
    for yy, rr in [(-depth/2, outer), (depth/2, outer),
                   (depth/2, inner), (-depth/2, inner)]:
        rings.append([bm.verts.new((rr*math.cos(2*math.pi*i/n), yy,
                                   rr*math.sin(2*math.pi*i/n))) for i in range(n)])
    for j in range(4):
        for i in range(n):
            k = (i+1) % n
            bm.faces.new((rings[j][i], rings[j][k], rings[(j+1)%4][k], rings[(j+1)%4][i]))
    return mesh(name, bm, (0, y, z), mat, parent or ROOT, .0008, 2)


def prism(name, points, width, mat, parent):
    bm = bmesh.new()
    loops = [[bm.verts.new((xx, y, z)) for y, z in points] for xx in (-width/2, width/2)]
    bm.faces.new(list(reversed(loops[0])))
    bm.faces.new(loops[1])
    for i in range(len(points)):
        k = (i+1) % len(points)
        bm.faces.new((loops[0][i], loops[0][k], loops[1][k], loops[1][i]))
    return mesh(name, bm, (0, 0, 0), mat, parent, .006, 3)


def build():
    # Main silhouette from the supplied concept: rear cuff, long rectangular casing,
    # short cylindrical emitter, two opposed brackets. Grip is tucked below the rear.
    box('Chassis', (0, .018, .084), (.176, .273, .154), 'Dark', .024)
    box('MainShell', (0, .014, .092), (.188, .222, .159), 'Armor', .028)
    box('RearCuff', (0, .145, .084), (.199, .075, .168), 'Dark', .019)
    box('RearEndArmor', (0, .181, .09), (.168, .014, .135), 'Armor', .011)
    box('FrontCuff', (0, -.108, .084), (.194, .044, .163), 'AccentArmor', .012)
    box('RearBand', (0, .119, .084), (.202, .018, .158), 'AccentArmor', .006)
    box('GripSocket', (0, .117, -.010), (.095, .063, .033), 'Dark', .010)
    box('Grip', (0, .116, -.060), (.053, .052, .094), 'Dark', .013)
    box('GripHeel', (0, .116, -.11), (.071, .059, .021), 'Armor', .007)
    for i in range(3):
        box('GripRib_%d'%i, (0, .088, -.034-i*.019), (.047, .007, .008), 'Rubber', .002)
    # Rear cyan screen and tall protective shoulders match the rear block in the concept.
    box('RearDisplayBezel', (0, .191, .088), (.066, .012, .077), 'Visor', .008)
    box('RearDisplay', (0, .198, .088), (.043, .003, .054), 'Cyan', .003)
    for s in (-1, 1):
        tag = 'L' if s < 0 else 'R'
        box('SidePanel_'+tag, (s*.096, .010, .093), (.015, .119, .058), 'Dark', .008)
        box('PanelInset_'+tag, (s*.104, .011, .093), (.003, .088, .034), 'Visor', .003)
        box('StatusScreenBezel_'+tag, (s*.103, .147, .090), (.013, .034, .055), 'Visor', .004)
        box('StatusScreen_'+tag, (s*.110, .147, .090), (.003, .024, .040), 'Cyan', .003)
        for i in range(3):
            box('DisplayBar_'+tag+str(i), (s*.112, .147, .081+i*.009),
                (.002, .016-(i%2)*.004, .002), 'PaleCyan', .0006)
        cylinder('PanelAmber_'+tag, (s*.107, .032, .093), .0037, .003,
                 'Amber', axis=(1, 0, 0), n=12, bevel=.0005)
        box('PanelSlot_'+tag, (s*.107, -.009, .093), (.004, .020, .004), 'Metal', .001)
        for yy in (-.077, .080):
            for zz in (.045, .136):
                cylinder('ShellBolt_%s_%s_%s'%(tag, yy, zz), (s*.096, yy, zz),
                         .004, .004, 'Metal', axis=(1,0,0), n=12, bevel=.0006)
                box('BoltRecess_%s_%s_%s'%(tag, yy, zz), (s*.099, yy, zz),
                    (.001, .004, .0012), 'Dark', .0003)
    box('TopServiceRail', (0, .041, .175), (.079, .130, .019), 'Dark', .006)
    for i in range(5):
        box('CoolingSlot_%d'%i, (0, .004+i*.020, .186), (.053, .007, .003), 'Visor', .001)
    box('TopArmorTab', (0, -.051, .176), (.070, .037, .015), 'Armor', .006)
    # Expose the working head: a shorter, narrower housing over an open feed bridge.
    bpy.context.view_layer.update()
    slim_housing(OBJECTS)
    box('GripBridge',(0,.117,.020),(.068,.042,.040),'Dark',.006)
    cylinder('ExposedFeed',(0,-.078,.084),.038,.110,'Dark',n=32,bevel=.002)
    for side in (-1,1):
        cylinder('FeedRail'+str(side),(side*.048,-.079,.084),.004,.125,'Metal',n=12,bevel=.001)
    # Short segmented barrel, concentric blue ring, black recessed bore.
    cylinder('EmitterNeck', (0, -.156, .084), .073, .088, 'Dark', n=48, bevel=.004)
    ring('BarrelRearBand', -.139, .079, .068, .014, 'Metal')
    ring('BarrelFrontBand', -.203, .080, .065, .016, 'Dark')
    ring('FrontWhiteRim', -.217, .081, .064, .010, 'Armor')
    ring('EmitterOuterLip', -.235, .079, .061, .027, 'Dark')
    ring('PortalRingOuter', -.251, .080, .076, .005, 'Cyan')
    ring('PortalRingInner', -.253, .064, .061, .005, 'Cyan')
    ring('BoreLiner', -.217, .061, .047, .065, 'Visor')
    cylinder('BoreBack', (0, -.190, .084), .049, .012, 'Visor', n=48)
    ring('CoreRing', -.200, .028, .022, .008, 'Cyan')
    cylinder('CoreLens', (0, -.206, .084), .018, .009, 'DeepBlue', n=48)
    cylinder('CoreLight', (0, -.212, .084), .006, .003, 'Cyan', n=24)
    for i in range(8):
        a = 2*math.pi*i/8
        p=(.071*math.cos(a), -.259, .084+.071*math.sin(a))
        cylinder('MuzzleFastener_%d'%i, p, .0026, .003, 'Metal', n=10, bevel=.0005)
    for s in (-1,1):
        box('BarrelScreenBezel_'+str(s), (s*.074, -.165, .084), (.012, .032, .033), 'Visor', .004)
        box('BarrelScreen_'+str(s), (s*.081, -.165, .084), (.003, .021, .021), 'Cyan', .003)
    # The defining pair of open arms: angular profiles with rounded white overlays.
    outline=[(-.188,.062),(-.219,.120),(-.331,.146),(-.382,.131),
             (-.409,.104),(-.395,.091),(-.366,.111),(-.332,.116),
             (-.240,.093),(-.216,.048)]
    overlay=[(-.203,.066),(-.227,.112),(-.331,.134),(-.374,.121),
             (-.380,.113),(-.334,.124),(-.235,.102),(-.217,.063)]
    for s, name in [(1,'Upper'),(-1,'Lower')]:
        pivot=(0,-.192,.084+s*.065)
        group=empty('Pivot_'+name, GEO, ROOT, pivot)
        bpy.context.view_layer.update()
        prism(name+'ArmSpine', [(y,.084+s*z) for y,z in outline], .040, 'Dark', group)
        prism(name+'ArmArmor', [(y,.084+s*z) for y,z in overlay], .045, 'AccentArmor', group)
        cylinder(name+'Hinge', pivot, .024, .058, 'Dark', axis=(1,0,0), parent=group)
        for side in (-1,1):
            cylinder(name+'HingeCap'+str(side), (side*.032,pivot[1],pivot[2]),
                     .016,.011,'Armor',axis=(1,0,0),parent=group)
            cylinder(name+'HingeHub'+str(side), (side*.039,pivot[1],pivot[2]),
                     .008,.005,'Metal',axis=(1,0,0),parent=group,n=16)
            for yy, rr in [(-.254,.105),(-.331,.130)]:
                cylinder(name+'ArmBolt'+str(side)+str(yy), (side*.025,yy,.084+s*rr),
                         .0034,.004,'Metal',axis=(1,0,0),parent=group,n=12,bevel=.0005)
        tiprot=Matrix.Rotation(s*math.radians(-42),3,'X')
        box(name+'TipEmitter', (0,-.392,.084+s*.110), (.021,.012,.009),
            'Cyan',.002,parent=group,rot=tiprot)
    empty('Socket_Hand', GEO, ROOT, (0,.116,-.057))
    empty('Socket_Muzzle', GEO, ROOT, (0,-.257,.084))
    empty('Socket_SupportHand', GEO, ROOT, (0,-.045,.03))


def validate():
    bpy.context.view_layer.update()
    result={'blender':bpy.app.version_string, 'meshes':0, 'triangles':0,
            'manifold':True, 'uv_projection':'per-face box; overlapping islands',
            'scale':[1,1,1], 'forward':'-Y', 'category':'Interactive',
            'tags':['tool','portal','handheld','robot-classic','white-shell'],
            'integration':'visual asset only; no gameplay or Unity prefab'}
    coords=[]
    for obj in OBJECTS:
        require(tuple(obj.scale)==(1,1,1), 'Non-unit scale: '+obj.name)
        if obj.type != 'MESH':
            continue
        me=obj.data
        require(len(me.vertices)>0 and len(me.polygons)>0, 'Empty mesh: '+obj.name)
        bm=bmesh.new(); bm.from_mesh(me)
        require(all(e.is_manifold for e in bm.edges), 'Open mesh: '+obj.name)
        require(bm.calc_volume(signed=True)>0, 'Invalid volume: '+obj.name)
        bm.free()
        require(all(p.material_index<len(me.materials) for p in me.polygons), 'Invalid material slot')
        require(len(me.uv_layers)>0, 'Missing UV')
        for poly in me.polygons:
            uv=[me.uv_layers.active.data[i].uv for i in poly.loop_indices]
            area=abs(sum(uv[i].x*uv[(i+1)%len(uv)].y-uv[(i+1)%len(uv)].x*uv[i].y for i in range(len(uv))))/2
            require(area>1e-12, 'Degenerate UV: '+obj.name+' '+str((poly.index,poly.area,list(poly.normal),[list(v) for v in uv])))
        for v in me.vertices:
            co=obj.matrix_world@v.co
            require(all(math.isfinite(c) for c in co), 'Nonfinite vertex')
            coords.append(co)
        me.calc_loop_triangles()
        result['meshes']+=1; result['triangles']+=len(me.loop_triangles)
    low=[min(v[i] for v in coords) for i in range(3)]
    high=[max(v[i] for v in coords) for i in range(3)]
    result['bounds_m']=[low,high]
    result['dimensions_m']=[round(high[i]-low[i],4) for i in range(3)]
    result['sockets']={o.name:list(o.location) for o in OBJECTS if o.name.startswith('Socket_')}
    result['pivot']='asset root; use Socket_Hand for hand attachment'
    require(result['triangles']<60000, 'Unexpected polygon budget')
    return result


def presentation(scene):
    global PRESENT
    PRESENT=collection('PG_PRESENTATION', scene.collection)
    scene.world=bpy.data.worlds.new('PG_World')
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.035,.055,.075,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
    target=Vector((0,-.104,.078))
    for name, pos, energy, size, color in [
        ('Key',(1.1,-.8,1.65),100,1.15,(.84,.93,1)),
        ('Fill',(-.7,-.3,.45),45,.85,(.36,.7,1)),
        ('Rim',(.0,1.2,1.1),140,.8,(1,.89,.72))]:
        data=bpy.data.lights.new('PG_'+name,'AREA'); data.energy=energy
        data.shape='DISK'; data.size=size; data.color=color
        ob=bpy.data.objects.new(data.name,data); PRESENT.objects.link(ob); ob.location=pos
        ob.rotation_euler=(target-ob.location).to_track_quat('-Z','Y').to_euler()
    data=bpy.data.cameras.new('PG_Camera'); cam=bpy.data.objects.new(data.name,data)
    PRESENT.objects.link(cam); data.type='ORTHO'; data.ortho_scale=.76
    scene.camera=cam
    scene.render.engine='CYCLES'; scene.cycles.samples=40; scene.cycles.use_denoising=True
    scene.render.resolution_x=1400; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='AgX'
    tree=bpy.data.node_groups.new('PG_Compositor','CompositorNodeTree')
    tree.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
    scene.compositing_node_group=tree
    source=tree.nodes.new('CompositorNodeRLayers'); glare=tree.nodes.new('CompositorNodeGlare')
    glare.inputs['Type'].default_value='Fog Glow'; glare.inputs['Quality'].default_value='High'
    glare.inputs['Strength'].default_value=.18; glare.inputs['Size'].default_value=.15
    output=tree.nodes.new('NodeGroupOutput')
    tree.links.new(source.outputs['Image'],glare.inputs['Image']); tree.links.new(glare.outputs['Image'],output.inputs['Image'])
    return cam, target


def render(scene,cam,target,path,offset,scale=.76):
    cam.location=target+Vector(offset)
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.ortho_scale=scale
    scene.render.filepath=str(path)
    if not os.environ.get('TOOLGEN_NO_RENDER'):
        bpy.ops.render.render(write_still=True)


def export(out):
    for obj in bpy.context.scene.objects:
        obj.select_set(obj in OBJECTS)
    bpy.context.view_layer.objects.active=ROOT
    specs=[('glb',bpy.ops.export_scene.gltf,dict(export_format='GLB',use_selection=True,
                export_yup=True,export_extras=True,export_animations=False,export_cameras=False,export_lights=False)),
           ('fbx',bpy.ops.export_scene.fbx,dict(use_selection=True,object_types={'EMPTY','MESH'},
                axis_forward='-Z',axis_up='Y',global_scale=1.,apply_unit_scale=True,
                apply_scale_options='FBX_SCALE_UNITS',bake_space_transform=False,
                use_mesh_modifiers=True,use_custom_props=True,bake_anim=False,add_leaf_bones=False))]
    for ext,op,kwargs in specs:
        props=op.get_rna_type().properties.keys()
        require(all(k in props for k in kwargs), 'Unsupported exporter option: '+ext)
        path=out/(ASSET+'.'+ext)
        require('FINISHED' in op(filepath=str(path),**kwargs), 'Failed export: '+ext)
        require(path.stat().st_size>100, 'Empty export: '+ext)


def main():
    global GEO, ROOT
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument('--no-render',action='store_true')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    out=args.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    (out/'build_complete.json').unlink(missing_ok=True)
    OBJECTS.clear(); MATS.clear()
    require(bpy.app.version==(5,2,2), 'Validated target is Blender 5.2.2 LTS')
    old=bpy.data.scenes.get(ASSET)
    scene=bpy.data.scenes.new(ASSET+'_Build'); bpy.context.window.scene=scene
    if old:
        oldobjects=list(old.objects); bpy.data.scenes.remove(old)
        for obj in oldobjects:
            if not obj.users_scene:
                bpy.data.objects.remove(obj,do_unlink=True)
        for datablocks in (bpy.data.collections,bpy.data.meshes,bpy.data.materials,
                           bpy.data.worlds,bpy.data.cameras,bpy.data.lights,bpy.data.node_groups):
            for data in list(datablocks):
                if data.users==0 and data.name.startswith(('PG_','ME_PG_')):
                    datablocks.remove(data)
    scene.name=ASSET
    if '--factory-startup' in sys.argv:
        for other in list(bpy.data.scenes):
            if other!=scene:
                obs=list(other.objects); bpy.data.scenes.remove(other)
                for ob in obs:
                    if not ob.users_scene:
                        bpy.data.objects.remove(ob,do_unlink=True)
    scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1
    GEO=collection('PG_GEOMETRY',scene.collection)
    ROOT=empty(ASSET,GEO)
    ROOT['ce_category']='Interactive'; ROOT['ce_forward']='-Y'
    material('Armor',PALETTE['armor'],.42,.30)
    material('AccentArmor',PALETTE['armor'],.42,.30)
    material('Dark',PALETTE['mech'],.7,.39)
    material('Metal',PALETTE['metal'],.6,.31)
    material('Visor',PALETTE['visor'],.25,.25)
    material('Rubber',(.017,.022,.027),0,.75)
    material('Cyan',PALETTE['eye'],.15,.24,4)
    material('PaleCyan',(.36,.91,1),.05,.25,2)
    material('DeepBlue',(.003,.064,.20),.7,.16,.65)
    material('Amber',PALETTE['accent'],.1,.3,1.5)
    build(); qa=validate()
    (out/'qa_geometry.json').write_text(json.dumps(qa,indent=2)+'\n')
    cam,target=presentation(scene)
    cam.location=target+Vector((.9,-.8,.52))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    # Viewport starts on the gun, with no preview lamp/camera clutter.
    for ob in PRESENT.objects:
        ob.hide_set(True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_distance=.85
                area.spaces.active.region_3d.view_location=target
                area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
                area.spaces.active.shading.type='MATERIAL'
    bpy.ops.wm.save_as_mainfile(filepath=str(out/(ASSET+'.blend')))
    export(out)
    if not args.no_render:
        render(scene,cam,target,out/'preview_white.png',(.9,-.8,.52))
        render(scene,cam,target,out/'view_side.png',(1,0,0),.73)
        render(scene,cam,target,out/'view_front.png',(0,-1,0),.62)
        render(scene,cam,target,out/'view_top.png',(0,0,1),.98)
        # Concept colour comparison uses the same geometry and camera.
        bs=MATS['AccentArmor'].node_tree.nodes.get('Principled BSDF')
        bs.inputs['Base Color'].default_value=(*PALETTE['accent'],1)
        MATS['AccentArmor'].diffuse_color=(*PALETTE['accent'],1)
        render(scene,cam,target,out/'preview_concept_colors.png',(.9,-.8,.52))
        bs.inputs['Base Color'].default_value=(*PALETTE['armor'],1)
        MATS['AccentArmor'].diffuse_color=(*PALETTE['armor'],1)
    print('PORTAL_GUN_BUILD_OK',json.dumps(qa))


if __name__=='__main__':
    main()
