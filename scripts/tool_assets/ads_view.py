"""The aim-down-sights rule on triangle meshes (Toolgen 0.25 Ocular, user decision 23.10.2026: sight sizes like Destiny 2).

While aiming no hand needs to stay in the frame; binding are the free screen centre (a scope's eye lens excepted) and no part
of weapon or arms between the camera and its near plane inside the view (Unity clips it: a visible cut). Pure numpy, shared by
toolgen/first_person.py (contract 4 ADS target pose) and toolgen/ego_rig.py (contract 5 aim clips); the unit tests feed small
meshes.

Sight frame: Socket_Sight at the origin, view along -Y, Z up, screen right = -X. The camera of an eye distance ``d`` sits at
(0, d, 0); ``frusta`` carry ``tan_h``/``tan_v`` (half extents of the binding views).
"""
import numpy as np

SEPARATION_M = 1e-9       # a gap below this counts as touching (an intersection)
PARALLEL = 1e-12          # cross products shorter than this are no separating axis


def pyramid(frustum, near, camera_y):
    """Apex (the camera) and the four corners of the near rectangle."""
    half_x, half_z = near * frustum["tan_h"], near * frustum["tan_v"]
    corners = [(x * half_x, camera_y - near, z * half_z) for x, z in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    return np.array([(0.0, camera_y, 0.0), *corners])


def in_pyramid(points, solid):
    """Which triangles (``points``: M x 3 corners x 3) meet the solid pyramid ``solid`` (5 x 3, apex first): separating axis
    test with the pyramid's face normals, the triangle's normal and the cross products of their edges."""
    apex, base = solid[0], solid[1:]
    faces = [(apex, base[i], base[(i + 1) % 4]) for i in range(4)] + [(base[0], base[1], base[2])]
    normals = np.array([np.cross(b - a, c - a) for a, b, c in faces])
    edges = np.array([*(corner - apex for corner in base), base[1] - base[0], base[2] - base[1]])
    sides = np.stack([points[:, 1] - points[:, 0], points[:, 2] - points[:, 1], points[:, 0] - points[:, 2]], axis=1)
    crosses = np.cross(sides[:, :, None, :], edges[None, None, :, :]).reshape(len(points), -1, 3)
    axes = np.concatenate([np.broadcast_to(normals, (len(points), 5, 3)),
                           np.cross(sides[:, 0], sides[:, 1])[:, None, :], crosses], axis=1)
    length = np.linalg.norm(axes, axis=2)
    usable = length > PARALLEL
    axes = axes / np.where(usable, length, 1.0)[:, :, None]
    triangle = np.einsum("mvk,mak->mav", points, axes)
    shape = np.einsum("pk,mak->map", solid, axes)
    apart = ((triangle.max(axis=2) < shape.min(axis=2) - SEPARATION_M)
             | (shape.max(axis=2) < triangle.min(axis=2) - SEPARATION_M)) & usable
    return ~apart.any(axis=1)


def near_plane_cuts(vertices, triangles, owners, frusta, near, camera_y):
    """Owners of the triangles inside the view between the camera at (0, ``camera_y``, 0) and its near plane."""
    points = vertices[triangles]
    found = set()
    for frustum in frusta:
        solid = pyramid(frustum, near, camera_y)
        low, high = solid.min(axis=0), solid.max(axis=0)
        near_box = ((points.max(axis=1) >= low - SEPARATION_M) & (points.min(axis=1) <= high + SEPARATION_M)).all(axis=1)
        candidates = np.flatnonzero(near_box)
        if len(candidates):
            found.update(owners[index] for index in candidates[in_pyramid(points[candidates], solid)])
    return sorted(found)


def centre_hit(vertices, triangles, owners, camera_y):
    """Owner of the first triangle the centre ray (from the camera along -Y) meets, or None."""
    points = vertices[triangles]
    a, b, c = points[:, 0], points[:, 1], points[:, 2]
    # barycentric coordinates of the axis (x = z = 0) in the triangle's X-Z projection
    e1, e2 = b - a, c - a
    det = e1[:, 0] * e2[:, 2] - e1[:, 2] * e2[:, 0]
    safe = np.where(np.abs(det) > 1e-18, det, 1.0)
    u = (-a[:, 0] * e2[:, 2] + a[:, 2] * e2[:, 0]) / safe
    v = (-e1[:, 0] * a[:, 2] + e1[:, 2] * a[:, 0]) / safe
    depth_y = a[:, 1] + u * e1[:, 1] + v * e2[:, 1]
    hit = (np.abs(det) > 1e-18) & (u >= 0) & (v >= 0) & (u + v <= 1) & (depth_y < camera_y)
    if not hit.any():
        return None
    candidates = np.flatnonzero(hit)
    return owners[candidates[np.argmax(depth_y[candidates])]]


def rule(vertices, triangles, owners, frusta, near, distance, allowed=("ScopeEyeLens",)):
    """Failures of the ADS rule at an eye distance (apart from the sight's centring, checked by the callers), the centre
    hit and the near-plane cuts. A centre hit named in ``allowed`` (without the SM_PG_ prefix) keeps the centre free."""
    reasons = []
    hit = centre_hit(vertices, triangles, owners, distance)
    if hit is not None and hit.removeprefix("SM_PG_") not in allowed:
        reasons.append(f"the centre ray meets {hit}")
    cuts = near_plane_cuts(vertices, triangles, owners, frusta, near, distance)
    if cuts:
        reasons.append(f"cut by the near plane ({near} m): {cuts[:6]}")
    return reasons, hit, cuts


def eye_distance_range(vertices, triangles, owners, frusta, near, allowed=("ScopeEyeLens",), steps=None):
    """The eye distances (default 0.02 ... 0.80 m in 5 mm steps) at which the rule holds: report block fields. The range
    runs from the first to the last passing step; ``eye_distance_intervals_m`` lists the passing stretches (a shotgun rib
    can cut the near plane close up and the bolt again farther back)."""
    steps = steps or [round(.02 + .005 * index, 3) for index in range(157)]
    passes = [not rule(vertices, triangles, owners, frusta, near, step, allowed)[0] for step in steps]
    intervals = []
    for index, ok in enumerate(passes):
        if ok and (index == 0 or not passes[index - 1]):
            intervals.append([steps[index], steps[index]])
        elif ok:
            intervals[-1][1] = steps[index]
    return {"eye_distance_range_m": [intervals[0][0], intervals[-1][1]] if intervals else None,
            "eye_distance_intervals_m": intervals,
            "eye_distance_steps_m": [steps[0], steps[-1], round(steps[1] - steps[0], 6) if len(steps) > 1 else 0],
            "eye_distance_range_contiguous": len(intervals) == 1}
