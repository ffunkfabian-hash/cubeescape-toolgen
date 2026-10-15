"""Shared geometry, material, validation and export helpers of the Cube Escape bow.

Blender 5.2.2, meters, forward -Y. Imported by create_standard_bow.py and
create_standard_bow_fps.py; not a generator on its own. Object names never
contain a dot: Blender appends ".001" to duplicates, and the verification
scripts strip exactly that suffix when they look objects up.
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

ASSET = 'CubeEscape_Bow_Standard'
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
    mat = bpy.data.materials.new('BW_' + name)
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
    # Long thin tubes facing -Z can receive inward winding from the normal
    # solver. Explicitly choose the positive-volume orientation before UVs.
    if bm.calc_volume(signed=True)<0:
        bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
        bm.normal_update()
    # Smooth curved transitions, preserve the planar faces of plates and caps.
    for face in bm.faces:
        face.smooth = max(abs(c) for c in face.normal) < .99999
    data = bpy.data.meshes.new('ME_BW_' + name)
    bm.to_mesh(data)
    bm.free()
    data.update()
    require(not data.validate(), 'Invalid mesh: ' + name)
    obj = bpy.data.objects.new('SM_BW_' + name, data)
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


def validate():
    bpy.context.view_layer.update()
    result={'blender':bpy.app.version_string, 'meshes':0, 'triangles':0,
            'manifold':True, 'uv_projection':'per-face box; overlapping islands',
            'scale':[1,1,1], 'forward':'-Y', 'category':'Interactive',
            'tags':['tool','bow','handheld','robot-classic','white-shell'],
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
    PRESENT=collection('BW_PRESENTATION', scene.collection)
    scene.world=bpy.data.worlds.new('BW_World')
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.035,.055,.075,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
    target=Vector((0,-.104,.078))
    for name, pos, energy, size, color in [
        ('Key',(1.1,-.8,1.65),100,1.15,(.84,.93,1)),
        ('Fill',(-.7,-.3,.45),45,.85,(.36,.7,1)),
        ('Rim',(.0,1.2,1.1),140,.8,(1,.89,.72))]:
        data=bpy.data.lights.new('BW_'+name,'AREA'); data.energy=energy
        data.shape='DISK'; data.size=size; data.color=color
        ob=bpy.data.objects.new(data.name,data); PRESENT.objects.link(ob); ob.location=pos
        ob.rotation_euler=(target-ob.location).to_track_quat('-Z','Y').to_euler()
    data=bpy.data.cameras.new('BW_Camera'); cam=bpy.data.objects.new(data.name,data)
    PRESENT.objects.link(cam); data.type='ORTHO'; data.ortho_scale=.76
    scene.camera=cam
    scene.render.engine='CYCLES'; scene.cycles.samples=40; scene.cycles.use_denoising=True
    scene.render.resolution_x=1400; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='AgX'
    tree=bpy.data.node_groups.new('BW_Compositor','CompositorNodeTree')
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

