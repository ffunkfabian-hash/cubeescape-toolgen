"""n-gons as triangles in a fixed face order (Toolgen 0.20).

``bmesh.ops.triangulate`` (bpy wheel 5.2.2 on Linux, BEAUTY; Blender.app on macOS was stable in two cold builds) finds the same
triangles with the same winding and loop start every time, but hands them back in a varying face order: between processes and
even twice in one process, so a fixed PYTHONHASHSEED does not help (0.19 finding 1: KG02 world model, viewer indices.bin
and every GLB differed between two cold builds, vertices equal). The order is therefore set afterwards: every face stays at
the place of the face it came from, the triangles of one n-gon follow each other by their corner (vertex) indices. Used by
concept_kit.make and game_export.reduce_to_budget.

``face_order`` is pure Python for the unit tests (tests/test_mesh_order.py).
"""
try:
    import bmesh
except ImportError:  # unit tests import the pure order with the system Python
    bmesh = None


def face_order(places, corners):
    """Positions of the faces in their fixed order: by the place of the face each came from, then by its corner indices."""
    return sorted(range(len(places)), key=lambda i: (places[i], tuple(corners[i])))


def triangulate_ngons(bm, method="BEAUTY"):
    """Triangulate the faces of ``bm`` with more than four corners and put all faces into their fixed order (module text).
    Returns whether anything was triangulated."""
    ngons = [face for face in bm.faces if len(face.verts) > 4]
    if not ngons:
        return False
    bm.verts.index_update()
    bm.faces.index_update()
    place = {face: face.index for face in bm.faces}
    source = bmesh.ops.triangulate(bm, faces=ngons, quad_method=method, ngon_method=method)["face_map"]
    faces = list(bm.faces)
    order = face_order([place[source.get(face, face)] for face in faces],
                       [[vert.index for vert in face.verts] for face in faces])
    rank = {faces[i]: position for position, i in enumerate(order)}
    bm.faces.sort(key=rank.__getitem__)
    bm.faces.index_update()
    return True
