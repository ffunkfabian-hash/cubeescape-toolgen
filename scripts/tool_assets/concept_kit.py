"""Build of a concept weapon (Toolgen 0.18, TG-A): the meshes of a formgen geometry spec instead of a weapon_designs.py build.

weapon_kit.world() calls ``build(kit, spec)`` for a design with ``concept`` (weapon_designs.DESIGNS); everything after the
geometry (Socket_Sight check, first-person copy, clips, game export, maps, robot variant) is the shared weapon path. The
rules (glass, merged open parts, coplanar faces, bevels, sockets) live in concept_spec.py, which reads no bpy.

Each planned mesh becomes one object ``SM_PG_<Label>_<id>`` with the Kit source material of its channel, the spec's
smoothing (``hard`` faces flat, others smooth), n-gons as triangles, a bevel of ``bevel_m`` with two segments on edges sharper than
concept_spec.BEVEL_ANGLE next to a hard face, and the kit's per-face box UVs. Moving parts hang under their Toolgen node
(``Anim_*`` pivot at the top centre of the part); Use-clip nodes without a part are empty pivots (reported in the QA).
"""
import bpy
import bmesh
from mathutils import Vector

import concept_spec

SEGMENTS = 2


def make(kit, mesh, parent, state):
    """One object: origin at the centre of its bounds (like the kit's primitives), identity parent inverse."""
    low, high = concept_spec.bounds(mesh["vertices"])
    centre = Vector([(low[i] + high[i]) / 2 for i in range(3)])
    bm = bmesh.new()
    verts = [bm.verts.new(Vector(vertex) - centre) for vertex in mesh["vertices"]]
    for face, hard in zip(mesh["faces"], mesh["hard"]):
        bm.faces.new([verts[i] for i in face]).smooth = not hard
    bm.normal_update()
    if mesh["bevel_m"]:
        edges = [edge for edge in bm.edges if edge.is_manifold and edge.calc_face_angle(0) > concept_spec.BEVEL_ANGLE
                 and any(not face.smooth for face in edge.link_faces)]
        if edges:
            result = bmesh.ops.bevel(bm, geom=edges, offset=mesh["bevel_m"], segments=SEGMENTS, profile=.5,
                                     affect='EDGES', clamp_overlap=True)
            for face in result["faces"]:
                face.smooth = True
        bm.normal_update()
    # n-gons (the spec's faces are planar n-gons, also concave) become triangles: tangents on UV1 need tris and quads
    # (an under-budget model is not decimated, which would triangulate them), and concave faces shade wrongly otherwise
    ngons = [face for face in bm.faces if len(face.verts) > 4]
    if ngons:
        bmesh.ops.triangulate(bm, faces=ngons, quad_method='BEAUTY', ngon_method='BEAUTY')
        bm.normal_update()
    name = mesh["name"].removeprefix("SM_PG_")
    data = bpy.data.meshes.new("ME_PG_" + name)
    bm.to_mesh(data)
    bm.free()
    data.update()
    if data.validate():
        raise RuntimeError("Invalid mesh: " + name)
    obj = bpy.data.objects.new("SM_PG_" + name, data)
    state["GEO"].objects.link(obj)
    obj.parent = parent
    obj.location = centre - parent.matrix_world.translation
    material = mesh["material"] or kit.glow_material
    data.materials.append(state["MATS"][material])
    obj["ce_role"] = "neon" if material in ("Cyan", "Amber") else "static"
    obj["ce_component"] = name
    obj["ce_concept_parts"] = " ".join(mesh["ids"])
    if not mesh["collision"]:
        obj["ce_collision"] = "none"
    # per-face box projection over the mesh bounds, exactly like the kit's primitives (create_portal_gun.mesh)
    uv = data.uv_layers.new(name="UVMap")
    low = [min(v.co[i] for v in data.vertices) for i in range(3)]
    high = [max(v.co[i] for v in data.vertices) for i in range(3)]
    for poly in data.polygons:
        major = max(range(3), key=lambda i: abs(poly.normal[i]))
        axes = ((1, 2), (0, 2), (0, 1))[major]
        for index in poly.loop_indices:
            co = data.vertices[data.loops[index].vertex_index].co
            uv.data[index].uv = [(co[i] - low[i]) / (high[i] - low[i]) for i in axes]
    state["OBJECTS"].append(obj)
    return obj


def build(kit, file, clip_nodes, state):
    """Meshes, pivots and sockets of the concept ``file`` (data/concepts, with its named corrections); returns the report
    for qa_geometry.json."""
    found = concept_spec.layout(file, clip_nodes)
    spec, meshes, report = found["spec"], found["meshes"], found["report"]
    nodes = {node: kit.pivot(node, location) for node, location in found["pivots"].items()}
    for mesh in meshes:
        make(kit, mesh, nodes.get(mesh["node"]) or state["ROOT"], state)
    for name, position in found["kit_sockets"].items():
        kit.socket(name, position)
    bpy.context.view_layer.update()
    record = concept_spec.provenance()
    entry = record["imported"][spec["sheet"]["id"]]
    source = {key: value for key, value in record["releases"][entry["release"]].items() if key != "files"}
    report.update(file=file, provenance=entry, source=source, empty_clip_nodes=found["empty"],
                  nodes={name: [round(c, 6) for c in node.matrix_world.translation] for name, node in sorted(nodes.items())},
                  sockets=found["sockets"], hold=concept_spec.hold(spec),
                  bevels={mesh["name"]: mesh["bevel_m"] for mesh in meshes})
    return report
