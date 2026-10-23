"""Triangles without area (Toolgen 0.24 patch KG11).

Unity's importer drops a triangle whose corners lie on one line (Cube Escape 0.112: KG11 8640 -> 8624). Geometry QA counts
them on the triangulated mesh so that they are red before the package reaches the game. Pure numpy on the mesh data
(``mesh`` is a bpy mesh; no bpy import here, the unit tests feed small stand-ins).
"""
import numpy as np

# m2. Healthy bevel triangles of the concept parts are >= 4e-9; the collapsed bevel corners measured 0 .. 9e-13.
ZERO_AREA_M2 = 1e-11


def zero_area_triangles(mesh, limit=ZERO_AREA_M2):
    """Number of triangles of ``mesh`` (object space, after ``calc_loop_triangles``) with an area below ``limit``."""
    mesh.calc_loop_triangles()
    count = len(mesh.loop_triangles)
    if not count:
        return 0
    corners = np.empty(count * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("vertices", corners)
    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", coords)
    points = coords.reshape(-1, 3).astype(np.float64)[corners.reshape(-1, 3)]
    area = np.linalg.norm(np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0]), axis=1) / 2
    return int(np.count_nonzero(area < limit))
