"""Game export of a toolgen world model for Cube Escape (Unity 6, URP).

Runs like the other toolgen steps:

    blender --background --factory-startup --python toolgen/run_asset.py -- \
        --script toolgen/game_export.py --directory <work> --tool <tool_id> [--preview]

Reads ``<work>/<asset>.blend`` (the world model of ``data/tools.json``) and writes to ``<work>``:

* ``<asset>_Game.blend/.fbx/.glb``: static parts merged into ONE mesh with material slots. Only animated parts
  stay separate: meshes below an object with an animation (merged per animated owner, the owner and its hierarchy
  are kept) and shape-key meshes (merged per parent and identical key animation). Every empty, including all
  ``Socket_*`` anchors, keeps its world matrix and parent; the clip keeps its name, length and event frames.
* matte palette from ``data/game_palette.json`` (matte variants of Cube Escape materials, glow names, at most six per tool).
* ``<part>_LOD0`` / ``<part>_LOD1`` (about 30 % of the triangles), the suffix convention Cube Escape's Cubegen import
  understands (Unity builds the LODGroup); box colliders in the Cubegen sidecar format (part-relative, Unity axes).
* ``unity_contract.json`` and ``qa_game.json``; the exit code is 1 when a check fails.

The pure helpers (axes, palette validation, box clustering) import without Blender for the unit tests.
"""
import argparse
import hashlib
import json
import math
import struct
import sys
import time
import traceback
from pathlib import Path

try:
    import bpy
    import numpy as np
    from mathutils import Matrix, Vector
    from mathutils.bvhtree import BVHTree
    from mathutils.geometry import barycentric_transform
except ImportError:  # unit tests import the pure helpers with the system Python
    bpy = None

ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "data/game_palette.json"
TOOLS_PATH = ROOT / "data/tools.json"
CONTRACT_FORMAT = 1
LOD1_TARGET = .30
LOD1_RANGE = (.25, .40)
MAX_RENDERERS = 4                 # LOD0 renderers: one static plus the moving parts
BOUNDS_TOLERANCE_M = .001         # LOD0 against the world model, every frame of the clip
ROUNDTRIP_BOUNDS_TOLERANCE_M = .002
ANCHOR_TOLERANCE = 1e-6           # native .blend: the empties are not touched at all
ROUNDTRIP_MATRIX_TOLERANCE = 1e-3
LOD1_BOUNDS_RELATIVE = .02        # LOD1 bounds within 2 % of the part diagonal (silhouette check)
COLLIDER_SLACK_M = .002
MIN_COLLIDER_SIZE_M = .004
COLLIDER_LIMITS = {"root": 6, "moving": 3}
MIN_PART_SIZE_M = .012            # bolts, hubs and caps below 12 mm get no collider
SPLIT_FILL = .45                  # parts filling less of their box are cut into slabs ...
MIN_SLAB_M = .05                  # ... of at least 5 cm ...
MAX_SLABS = 4                     # ... at most four
MERGE_FILL = .5                   # merge two boxes while the common box stays at least half full
# QA probes inside openings that a collider must leave free: (socket, socket or None, blend factor,
# offset in metres along the root axes).
OPENING_PROBES = {
    "portal_emitter": [("Socket_Muzzle", None, 0.0, (0.0, -.075, 0.0))],
    "magnet_gripper": [("Socket_Grab", None, 0.0, (0.0, 0.0, 0.0)), ("Socket_Grab", None, 0.0, (0.0, .06, 0.0))],
    "bow": [("Socket_Hand", "Socket_Nock", .5, (0.0, 0.0, 0.0)), ("Socket_Hand", "Socket_Nock", .75, (0.0, 0.0, 0.0)),
            ("Socket_Nock", None, 0.0, (0.0, -.05, .235)), ("Socket_Nock", None, 0.0, (0.0, -.05, -.365))],
}
# Blender (Z up, front -Y) -> Unity (Y up, front +Z): FBX axis_forward -Z / axis_up Y imported with Unity's
# bakeAxisConversion, glTF Y up with the X mirror of Unity's importers. Same mapping as Cubegen (asset.to_unity).
TO_UNITY = ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))


# --------------------------------------------------------------------------------------------- pure helpers
def srgb_to_linear(value):
    return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4


def unity_position(vector):
    return [-vector[0] + 0.0, vector[2] + 0.0, -vector[1] + 0.0]


def unity_scale(vector):
    return [vector[0], vector[2], vector[1]]


def quaternion_xyzw(m):
    """(x, y, z, w) of a 3x3 rotation matrix, the order of Unity's ``new Quaternion(x, y, z, w)``."""
    trace = m[0][0] + m[1][1] + m[2][2]
    if trace > 0:
        s = math.sqrt(trace + 1.0) * 2
        q = ((m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s, .25 * s)
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        q = (.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s, (m[2][1] - m[1][2]) / s)
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        q = ((m[0][1] + m[1][0]) / s, .25 * s, (m[1][2] + m[2][1]) / s, (m[0][2] - m[2][0]) / s)
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
        q = ((m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, .25 * s, (m[1][0] - m[0][1]) / s)
    if q[3] < 0:
        q = tuple(-value for value in q)
    return [round(value, 7) + 0.0 for value in q]


def unity_rotation(rotation):
    """Blender rotation matrix R -> Unity quaternion of M R M^T (M = TO_UNITY, orthogonal)."""
    m = TO_UNITY
    mr = [[sum(m[i][k] * rotation[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return quaternion_xyzw([[sum(mr[i][k] * m[j][k] for k in range(3)) for j in range(3)] for i in range(3)])


def validate_palette(palette):
    """Errors of data/game_palette.json: targets exist, matte limits, emission only on glow materials."""
    errors = []
    finish = palette["finish"]
    materials = palette["materials"]
    for name, spec in materials.items():
        if not name.startswith("M_"):
            errors.append(f"{name}: palette names are Cube Escape material names (M_...)")
        if len(spec["color_srgb"]) != 3 or not all(0 <= c <= 1 for c in spec["color_srgb"]):
            errors.append(f"{name}: color_srgb needs three values 0..1")
        glow = spec["emission"] > 0
        if glow != name.startswith("M_Glow"):
            errors.append(f"{name}: only M_Glow* materials emit")
        if not glow and (spec["metallic"] > finish["max_metallic"] or spec["roughness"] < finish["min_roughness"]):
            errors.append(f"{name}: not matte (metallic {spec['metallic']}, roughness {spec['roughness']})")
    for source, target in palette["map"].items():
        if target not in materials:
            errors.append(f"{source}: unknown palette material {target}")
    return errors


def symmetric_eigenvectors(matrix, sweeps=60):
    """Jacobi rotations for a symmetric 3x3 matrix: (eigenvalues, eigenvectors as rows)."""
    a = [list(map(float, row)) for row in matrix]
    v = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    for _ in range(sweeps):
        if a[0][1] ** 2 + a[0][2] ** 2 + a[1][2] ** 2 < 1e-30:
            break
        for p, q in ((0, 1), (0, 2), (1, 2)):
            if abs(a[p][q]) < 1e-30:
                continue
            theta = (a[q][q] - a[p][p]) / (2 * a[p][q])
            t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1))
            c = 1 / math.sqrt(t * t + 1)
            s = t * c
            for k in range(3):
                a[k][p], a[k][q] = c * a[k][p] - s * a[k][q], s * a[k][p] + c * a[k][q]
            for k in range(3):
                a[p][k], a[q][k] = c * a[p][k] - s * a[q][k], s * a[p][k] + c * a[q][k]
            for k in range(3):
                v[k][p], v[k][q] = c * v[k][p] - s * v[k][q], s * v[k][p] + c * v[k][q]
    return [a[i][i] for i in range(3)], [[v[k][i] for k in range(3)] for i in range(3)]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _box_from_axes(points, axes):
    projections = [[_dot(point, axis) for point in points] for axis in axes]
    lows = [min(values) for values in projections]
    highs = [max(values) for values in projections]
    center = [sum(axes[i][k] * (lows[i] + highs[i]) / 2 for i in range(3)) for k in range(3)]
    return (center, [list(axis) for axis in axes], [(highs[i] - lows[i]) / 2 for i in range(3)])


def box_excess(box, limits):
    """How far (m) the corners of a box reach outside an axis-aligned (low, high) region."""
    return max(max(limits[0][i] - corner[i], corner[i] - limits[1][i]) for corner in box_corners(box) for i in range(3))


def fit_box(points, prefer_aligned=.9, limits=None, slack=.002):
    """Box around points: (center, axes as rows, half extents). Axis aligned in the given space unless the
    principal-axes box is clearly smaller (curved or slanted parts like bow limbs) and its corners stay within
    ``limits`` (the model bounds in this space)."""
    points = [tuple(map(float, point)) for point in points]
    aligned = _box_from_axes(points, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    count = len(points)
    mean = [sum(point[k] for point in points) / count for k in range(3)]
    covariance = [[sum((point[i] - mean[i]) * (point[j] - mean[j]) for point in points) / count for j in range(3)]
                  for i in range(3)]
    _, axes = symmetric_eigenvectors(covariance)
    for axis in axes:                                  # deterministic signs: largest component positive
        if axis[max(range(3), key=lambda k: abs(axis[k]))] < 0:
            axis[:] = [-value for value in axis]
    cross = [axes[0][1] * axes[1][2] - axes[0][2] * axes[1][1], axes[0][2] * axes[1][0] - axes[0][0] * axes[1][2],
             axes[0][0] * axes[1][1] - axes[0][1] * axes[1][0]]
    axes[2] = cross                                    # right-handed rotation
    principal = _box_from_axes(points, axes)
    if limits is not None and box_excess(principal, limits) > slack:
        return aligned
    return principal if box_volume(principal) < prefer_aligned * box_volume(aligned) else aligned


def box_volume(box):
    return 8 * box[2][0] * box[2][1] * box[2][2]


def box_corners(box):
    center, axes, half = box
    return [[center[k] + sx * half[0] * axes[0][k] + sy * half[1] * axes[1][k] + sz * half[2] * axes[2][k]
             for k in range(3)] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def point_in_box(point, box, slack=0.0):
    center, axes, half = box
    offset = [point[k] - center[k] for k in range(3)]
    return all(abs(_dot(offset, axes[i])) <= half[i] + slack for i in range(3))


def box_contains(outer, inner, slack=0.0):
    return all(point_in_box(corner, outer, slack) for corner in box_corners(inner))


def box_rotation(box):
    """Rotation matrix (columns = box axes) of a box."""
    axes = box[1]
    return [[axes[j][i] for j in range(3)] for i in range(3)]


def merge_boxes(items, max_boxes, min_fill=MERGE_FILL, slack=.0005, limits=None):
    """Few boxes that follow the model. ``items`` holds (box, points, material volume) triples. Contained boxes are
    dropped (their volume counts for the container), then the pair whose common box is filled best is merged while
    that box stays at least ``min_fill`` full, or while there are more than ``max_boxes``. Openings stay free
    because a box across them is mostly empty. The score uses the box corners, a merged box is fitted tightly
    to the points of both."""
    def prune(entries):
        kept = []
        for entry in sorted(entries, key=lambda e: box_volume(e[0]), reverse=True):
            container = next((i for i, other in enumerate(kept) if box_contains(other[0], entry[0], slack)), None)
            if container is None:
                kept.append(entry)
            else:
                box, points, material = kept[container]
                kept[container] = (box, points, material + entry[2])
        return kept

    items = prune([(box, [tuple(point) for point in points], float(material)) for box, points, material in items])
    cache = {}

    def score(a, b):
        key = (id(a[0]), id(b[0]), a[2], b[2])
        if key not in cache:
            volume = box_volume(fit_box(box_corners(a[0]) + box_corners(b[0]), limits=limits))
            cache[key] = min(1.0, (a[2] + b[2]) / volume) if volume > 0 else 1.0
        return cache[key]

    while len(items) > 1:
        best = None
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                fill = score(items[i], items[j])
                if best is None or fill > best[0]:
                    best = (fill, i, j)
        fill, i, j = best
        if len(items) <= max_boxes and fill < min_fill:
            break
        points = items[i][1] + items[j][1]
        merged = (fit_box(points, limits=limits), points, items[i][2] + items[j][2])
        items = prune([item for index, item in enumerate(items) if index not in (i, j)] + [merged])
    return sorted((item[0] for item in items), key=lambda box: (-box_volume(box), box[0]))


def sample_frames(start, end, markers, key_frames, count=9):
    """Reimport poses: markers, the ends, evenly spaced frames and the key frames when they are few."""
    frames = {start, end, *markers}
    frames.update(round(start + (end - start) * i / (count - 1)) for i in range(count))
    if len(key_frames) <= 12:
        frames.update(key_frames)
    return sorted(frame for frame in frames if start <= frame <= end)


def base_name(name):
    stem, dot, suffix = name.rpartition(".")
    return stem if dot and suffix.isdigit() and len(suffix) == 3 else name


def glb_document(path):
    data = Path(path).read_bytes()
    magic, _, _ = struct.unpack_from("<4sII", data, 0)
    length, kind = struct.unpack_from("<I4s", data, 12)
    if magic != b"glTF" or kind != b"JSON":
        raise ValueError(f"Not a binary glTF file: {path}")
    return json.loads(data[20:20 + length])


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------------------------------------- Blender helpers
def tree(root):
    return [root, *sorted(root.children_recursive, key=lambda obj: obj.name)]


def action_of(owner):
    data = getattr(owner, "animation_data", None)
    return data.action if data and data.action else None


def action_curves(action):
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves


def key_action(obj):
    keys = obj.data.shape_keys if obj.type == "MESH" else None
    return action_of(keys) if keys else None


def matrix_list(matrix):
    return [[float(value) for value in row] for row in matrix]


def matrix_error(a, b):
    return max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4))


def mesh_points(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.data
    co = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", co)
    matrix = np.array(evaluated.matrix_world, dtype=np.float64)
    return co.reshape(-1, 3).astype(np.float64) @ matrix[:3, :3].T + matrix[:3, 3]


def bounds_of(objects, depsgraph):
    points = [mesh_points(obj, depsgraph) for obj in objects if obj.type == "MESH" and len(obj.data.vertices)]
    if not points:
        return None
    stacked = np.concatenate(points)
    return [stacked.min(axis=0).tolist(), stacked.max(axis=0).tolist()]


def bounds_error(a, b):
    return max(abs(a[j][i] - b[j][i]) for i in range(3) for j in range(2))


def triangles(mesh):
    mesh.calc_loop_triangles()
    return len(mesh.loop_triangles)


def set_frame(scene, frame):
    scene.frame_set(int(math.floor(frame)), subframe=frame % 1)
    bpy.context.view_layer.update()


def visibility_animated(obj, root):
    while obj is not None and obj != root:
        if obj.get("ce_visibility_animation"):
            return True
        obj = obj.parent
    return False


def animated_owner(obj, root):
    """Nearest object between the mesh and the root that carries an object animation."""
    current = obj.parent
    while current is not None and current != root:
        if action_of(current):
            return current
        current = current.parent
    return root if action_of(root) else None


class Group:
    def __init__(self, kind, owner, name, members, keys=None):
        self.kind, self.owner, self.name, self.members, self.keys = kind, owner, name, members, keys or []


def classify(root, frames, asset):
    """Renderer groups: one static group, one per animated owner and one per shape-key signature."""
    static, moving, morph = [], {}, {}
    for obj in tree(root):
        if obj.type != "MESH":
            continue
        if action_of(obj):
            raise RuntimeError(f"Mesh with an object animation is not supported, animate an empty: {obj.name}")
        if obj.data.shape_keys:
            keys = obj.data.shape_keys
            action = action_of(keys)
            curves = sorted((curve.data_path, tuple(round(curve.evaluate(frame), 6) for frame in frames))
                            for curve in action_curves(action)) if action else []
            signature = (obj.parent.name, tuple(block.name for block in keys.key_blocks), tuple(curves))
            morph.setdefault(signature, []).append(obj)
            continue
        owner = animated_owner(obj, root)
        if owner is None:
            static.append(obj)
        else:
            moving.setdefault(owner.name, []).append(obj)
    groups = [Group("static", root, asset + "_Static", static)] if static else []
    for index, (signature, members) in enumerate(sorted(morph.items(), key=lambda item: item[0][0])):
        parent = members[0].parent
        stem = asset if parent == root else parent.name
        groups.append(Group("morph", parent, stem + "_Morph" + (str(index + 1) if index else ""), members,
                            list(signature[1])))
    for owner_name, members in sorted(moving.items()):
        owner = bpy.data.objects[owner_name]
        groups.append(Group("moving", owner, owner_name + "_Mesh", members))
    for group in groups:
        group.member_names = [obj.name for obj in group.members]
    return groups


# --------------------------------------------------------------------------------------------- source record
def record_source(scene, root, groups, frames):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    empties = [obj for obj in tree(root) if obj.type == "EMPTY"]
    record = {"frames": frames, "matrices": {}, "group_bounds": {}, "bounds": {}}
    for frame in frames:
        set_frame(scene, frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        record["matrices"][frame] = {obj.name: matrix_list(obj.matrix_world) for obj in empties}
        record["group_bounds"][frame] = {group.name: bounds_of(group.members, depsgraph) for group in groups}
        record["bounds"][frame] = bounds_of([obj for obj in tree(root) if obj.type == "MESH"], depsgraph)
    set_frame(scene, frames[0])
    return record


def convex_hull_points(points):
    """Vertices of the convex hull: the same boxes as all points, far fewer to fit."""
    import bmesh
    bm = bmesh.new()
    try:
        for point in sorted({tuple(round(v, 6) for v in point) for point in points}):
            bm.verts.new(point)
        if len(bm.verts) < 4:
            return [tuple(vertex.co) for vertex in bm.verts]
        result = bmesh.ops.convex_hull(bm, input=list(bm.verts))
        hull = {vertex for vertex in result["geom"] if isinstance(vertex, bmesh.types.BMVert)}
        hull -= set(result["geom_interior"]) | set(result["geom_unused"])
        return [tuple(vertex.co) for vertex in hull] or [tuple(vertex.co) for vertex in bm.verts]
    finally:
        bm.free()


def part_boxes(obj, space, depsgraph, limits):
    """(box, hull points) of one LOD0 part in the collision space. Tiny details get no collider. A part that fills
    its box poorly (curved limbs, claws) is cut into slabs along its longest axis, so the boxes follow the curve
    instead of closing the opening it bends around."""
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.evaluated_get(depsgraph).data)
        bm.transform(space.matrix_world.inverted() @ obj.matrix_world)
        points = [tuple(vertex.co) for vertex in bm.verts]
        box = fit_box(convex_hull_points(points), limits=limits)
        lengths = [2 * value for value in box[2]]
        if max(lengths) < MIN_PART_SIZE_M:
            return []
        material = abs(bm.calc_volume())
        fill = material / max(box_volume(box), 1e-12)
        longest = max(range(3), key=lambda i: lengths[i])
        slabs = min(MAX_SLABS, int(lengths[longest] / MIN_SLAB_M))
        if fill >= SPLIT_FILL or slabs < 2:
            return [(box, convex_hull_points(points), material)]
        axis = Vector(box[1][longest])
        start = axis.dot(Vector(box[0])) - box[2][longest]
        step = lengths[longest] / slabs
        for index in range(1, slabs):
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-7,
                                   plane_co=axis * (start + index * step), plane_no=axis)
        bins = [[] for _ in range(slabs)]
        for vertex in bm.verts:
            position = (axis.dot(vertex.co) - start) / step
            for index in range(slabs):
                if index - 1e-4 <= position <= index + 1 + 1e-4:
                    bins[index].append(tuple(vertex.co))
        result = []
        for members in bins:
            if len(members) >= 4:
                hull = convex_hull_points(members)
                result.append((fit_box(hull, limits=limits), hull, material / slabs))
        return result
    finally:
        bm.free()


def collision_boxes(root, groups, scene):
    """Boxes per collision space from the actual LOD0 parts. Glow geometry and visibility-animated visuals
    (the loaded arrow) get no collision, like Cube Escape's import (glow parts never collide)."""
    set_frame(scene, scene.frame_start)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    spaces, limits = {}, {}
    model = [obj for obj in tree(root) if obj.type == "MESH"]
    for group in groups:
        space = root if group.kind in ("static", "morph") else group.owner
        if visibility_animated(space, root):
            continue
        if space.name not in limits:
            # Model bounds in this space at rest: a box may not reach beyond the visible model.
            inverse = np.array(space.matrix_world.inverted(), dtype=np.float64)
            points = np.concatenate([mesh_points(obj, depsgraph) for obj in model]) @ inverse[:3, :3].T + inverse[:3, 3]
            limits[space.name] = (points.min(axis=0).tolist(), points.max(axis=0).tolist())
        for obj in group.members:
            if obj.get("ce_role") == "neon" or visibility_animated(obj, root):
                continue
            spaces.setdefault(space.name, []).extend(part_boxes(obj, space, depsgraph, limits[space.name]))
    colliders = []
    for space_name, boxes in spaces.items():
        limit = COLLIDER_LIMITS["root" if space_name == root.name else "moving"]
        for center, axes, half in merge_boxes(boxes, limit, limits=limits[space_name]):
            half = [max(value, MIN_COLLIDER_SIZE_M / 2) for value in half]
            rotation = box_rotation((center, axes, half))
            colliders.append({"type": "box", "part": None if space_name == root.name else space_name,
                              "center": [round(v, 5) + 0.0 for v in unity_position(center)],
                              "size": [round(2 * v, 5) for v in unity_scale(half)],
                              "rotation": unity_rotation(rotation),
                              "blender": {"space": space_name, "center": [round(v, 6) + 0.0 for v in center],
                                          "axes": [[round(v, 7) + 0.0 for v in axis] for axis in axes],
                                          "half_extents": [round(v, 6) for v in half]}})
    return colliders


# --------------------------------------------------------------------------------------------- build
def palette_materials(palette):
    created = {}
    for name, spec in palette["materials"].items():
        material = bpy.data.materials.new(name)
        material.use_nodes = True
        linear = [srgb_to_linear(c) for c in spec["color_srgb"]]
        material.diffuse_color = (*linear, 1)
        material.metallic = spec["metallic"]
        material.roughness = spec["roughness"]
        node = material.node_tree.nodes.get("Principled BSDF")
        values = [("Base Color", (*linear, 1)), ("Metallic", spec["metallic"]), ("Roughness", spec["roughness"]),
                  ("Emission Color", (*linear, 1)), ("Emission Strength", spec["emission"])]
        for socket, value in values:
            node.inputs[socket].default_value = value
        material["ce_palette"] = spec["role"]
        created[name] = material
    return created


def remap_materials(root, palette, materials):
    used = set()
    for obj in tree(root):
        if obj.type != "MESH":
            continue
        for index, material in enumerate(obj.data.materials):
            if material is None:
                raise RuntimeError(f"Empty material slot: {obj.name}[{index}]")
            target = palette["map"].get(material.name)
            if target is None:
                raise RuntimeError(f"Source material missing in data/game_palette.json: {material.name}")
            used.add(material.name)
            obj.data.materials[index] = materials[target]
    return sorted(used)


def dedupe_slots(mesh):
    """One slot per used material (the join leaves an empty slot of the new target and may repeat materials)."""
    indices = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("material_index", indices)
    unique, lookup = [], np.zeros(len(mesh.materials), dtype=np.int32)
    for slot in sorted(set(indices.tolist())):
        material = mesh.materials[slot]
        if material is None:
            raise RuntimeError(f"Faces without material: {mesh.name}, slot {slot}")
        if material not in unique:
            unique.append(material)
        lookup[slot] = unique.index(material)
    indices = lookup[indices]
    mesh.materials.clear()
    for material in unique:
        mesh.materials.append(material)
    mesh.polygons.foreach_set("material_index", indices)


def assign_action(id_data, action):
    data = id_data.animation_data or id_data.animation_data_create()
    data.action = action
    if action.slots and data.action_slot is None:
        data.action_slot = action.slots[0]


def merge_group(group, collection):
    """Join the group's meshes into one new object below its owner (identity local transform)."""
    mesh = bpy.data.meshes.new(group.name + "_LOD0")
    target = bpy.data.objects.new(group.name + "_LOD0", mesh)
    collection.objects.link(target)
    target.parent = group.owner
    target.matrix_parent_inverse = Matrix.Identity(4)
    target.matrix_basis = Matrix.Identity(4)
    target["ce_role"] = group.kind
    target["ce_lod"] = 0
    action = None
    if group.kind == "morph":
        source_keys = group.members[0].data.shape_keys
        action = action_of(source_keys)
        for block in source_keys.key_blocks:
            added = target.shape_key_add(name=block.name, from_mix=False)
            added.slider_min, added.slider_max = block.slider_min, block.slider_max
        for block in source_keys.key_blocks:
            target.data.shape_keys.key_blocks[block.name].relative_key = \
                target.data.shape_keys.key_blocks[block.relative_key.name]
        target.data.shape_keys.use_relative = source_keys.use_relative
    bpy.context.view_layer.update()
    members = set(group.members)
    for member in group.members:
        for child in list(member.children):
            if child not in members:
                world = child.matrix_world.copy()
                child.parent = target
                child.matrix_world = world
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in [target, *group.members]:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = target
    with bpy.context.temp_override(active_object=target, object=target, selected_objects=[target, *group.members],
                                   selected_editable_objects=[target, *group.members]):
        result = bpy.ops.object.join()
    if "FINISHED" not in result:
        raise RuntimeError(f"Join failed: {group.name}")
    dedupe_slots(target.data)
    if action:
        assign_action(target.data.shape_keys, action)
    target.data.name = target.name
    return target


def transfer_shape_keys(source, target):
    """Shape keys of a decimated copy: each new vertex follows the nearest source triangle (barycentric)."""
    keys = source.data.shape_keys
    reference = keys.reference_key
    source.data.calc_loop_triangles()
    basis = [point.co.copy() for point in reference.data]
    faces = [tuple(triangle.vertices) for triangle in source.data.loop_triangles]
    lookup = BVHTree.FromPolygons(basis, faces, all_triangles=True)
    mapping = []
    for vertex in target.data.vertices:
        _, _, index, _ = lookup.find_nearest(vertex.co)
        mapping.append((vertex.co.copy(), faces[index]))
    for block in keys.key_blocks:
        added = target.shape_key_add(name=block.name, from_mix=False)
        added.slider_min, added.slider_max = block.slider_min, block.slider_max
        if block == reference:
            continue
        data = block.data
        for i, (co, (a, b, c)) in enumerate(mapping):
            added.data[i].co = barycentric_transform(co, basis[a], basis[b], basis[c], data[a].co, data[b].co, data[c].co)
    for block in keys.key_blocks:
        target.data.shape_keys.key_blocks[block.name].relative_key = \
            target.data.shape_keys.key_blocks[block.relative_key.name]
    target.data.shape_keys.use_relative = keys.use_relative
    action = action_of(keys)
    if action:
        assign_action(target.data.shape_keys, action)


def make_lod1(lod0, ratio, collection):
    copy = lod0.data.copy()
    temporary = bpy.data.objects.new("_GameExportDecimate", copy)
    collection.objects.link(temporary)
    if copy.shape_keys:
        temporary.shape_key_clear()
    modifier = temporary.modifiers.new("Decimate", "DECIMATE")
    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = ratio
    modifier.use_collapse_triangulate = True
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(temporary.evaluated_get(depsgraph), preserve_all_data_layers=True,
                                           depsgraph=depsgraph)
    bpy.data.objects.remove(temporary)
    bpy.data.meshes.remove(copy)
    name = lod0.name[:-len("_LOD0")] + "_LOD1"
    mesh.name = name
    lod1 = bpy.data.objects.new(name, mesh)
    collection.objects.link(lod1)
    lod1.parent = lod0.parent
    lod1.matrix_parent_inverse = lod0.matrix_parent_inverse.copy()
    lod1.matrix_basis = lod0.matrix_basis.copy()
    lod1["ce_role"] = lod0["ce_role"]
    lod1["ce_lod"] = 1
    lod1.hide_render = True          # Cubegen convention: LOD1 hidden in previews, the LODGroup switches in Unity
    if lod0.data.shape_keys:
        transfer_shape_keys(lod0, lod1)
    return lod1


def build_lods(renderers, collection):
    total = sum(triangles(obj.data) for obj in renderers)
    ratio, lods = LOD1_TARGET, []
    for _ in range(3):
        for obj in lods:
            mesh = obj.data
            bpy.data.objects.remove(obj)
            bpy.data.meshes.remove(mesh)
        lods = [make_lod1(obj, ratio, collection) for obj in renderers]
        achieved = sum(triangles(obj.data) for obj in lods) / total
        if abs(achieved - LOD1_TARGET) <= .02:
            break
        ratio = min(1.0, ratio * LOD1_TARGET / max(achieved, 1e-6))
    return lods


def export_files(scene, root, work, name, clip):
    objects = set(tree(root))
    for obj in scene.objects:
        obj.select_set(obj in objects)
    bpy.context.view_layer.objects.active = root
    animated = clip is not None
    gltf = {"filepath": str(work / (name + ".glb")), "export_format": "GLB", "use_selection": True,
            "export_yup": True, "export_extras": True, "export_animations": animated, "export_morph": True,
            "export_cameras": False, "export_lights": False, "use_active_scene": True}
    if animated:
        gltf.update({"export_animation_mode": "ACTIVE_ACTIONS", "export_merge_animation": "ACTION",
                     "export_nla_strips_merged_animation_name": clip, "export_frame_range": True,
                     "export_force_sampling": True})
    if "FINISHED" not in bpy.ops.export_scene.gltf(**gltf):
        raise RuntimeError("glTF export failed")
    result = bpy.ops.export_scene.fbx(
        filepath=str(work / (name + ".fbx")), use_selection=True, object_types={"EMPTY", "MESH"},
        axis_forward="-Z", axis_up="Y", global_scale=1, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        bake_space_transform=False, use_mesh_modifiers=False, use_custom_props=True, add_leaf_bones=False,
        bake_anim=animated, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True, bake_anim_step=1, bake_anim_simplify_factor=0)
    if "FINISHED" not in result:
        raise RuntimeError("FBX export failed")


# --------------------------------------------------------------------------------------------- contract
def local_transform(obj):
    local = obj.parent.matrix_world.inverted() @ obj.matrix_world if obj.parent else obj.matrix_world.copy()
    location, rotation, scale = local.decompose()
    rotation_matrix = rotation.to_matrix()
    return {"blender": {"location": [round(v, 6) + 0.0 for v in location],
                        "rotation_wxyz": [round(v, 7) + 0.0 for v in rotation], "scale": [round(v, 6) for v in scale]},
            "unity": {"localPosition": [round(v, 6) + 0.0 for v in unity_position(location)],
                      "localRotation": unity_rotation([list(row) for row in rotation_matrix]),
                      "localScale": [round(v, 6) for v in unity_scale(scale)]}}


def build_contract(tool, source_info, root, renderers, lods, colliders, clip_info, palette, files):
    def renderer_entry(obj):
        mesh = obj.data
        return {"name": obj.name, "parent": obj.parent.name, "role": obj["ce_role"], "lod": obj["ce_lod"],
                "materials": [material.name for material in mesh.materials], "triangles": triangles(mesh),
                "vertices": len(mesh.vertices),
                "blend_shapes": [block.name for block in mesh.shape_keys.key_blocks][1:] if mesh.shape_keys else [],
                "renderer": "SkinnedMeshRenderer" if mesh.shape_keys else "MeshRenderer"}

    anchors = [{"name": obj.name, "parent": obj.parent.name, "animated": bool(action_of(obj)), **local_transform(obj)}
               for obj in tree(root) if obj.type == "EMPTY" and obj.name.startswith("Socket_")]
    nodes = [{"name": obj.name, "parent": obj.parent.name if obj.parent else None, "type": obj.type,
              "animated": bool(action_of(obj)), **local_transform(obj)}
             for obj in tree(root) if obj.type == "EMPTY" and not obj.name.startswith("Socket_")]
    lod0_tris = sum(triangles(obj.data) for obj in renderers)
    lod1_tris = sum(triangles(obj.data) for obj in lods)
    parents = sorted({obj.parent.name for obj in renderers})
    return {
        "format": CONTRACT_FORMAT, "generator": "toolgen", "version": source_info["version"],
        "tool": tool["id"], "asset": tool["asset"], "model": tool["asset"] + "_Game",
        "units": "meter", "scale": 1.0,
        "axes": {"blender": {"up": "+Z", "forward": "-Y"}, "unity": {"up": "+Y", "forward": "+Z"},
                 "position": "unity = (-x, z, -y) of blender", "scale": "unity = (x, z, y) of blender",
                 "rotation": "unity quaternion (x, y, z, w) of M R M^T, M = [[-1,0,0],[0,0,1],[0,-1,0]]",
                 "fbx": {"axis_forward": "-Z", "axis_up": "Y", "bake_space_transform": False,
                         "unity_import": "ModelImporter.bakeAxisConversion = true: the root keeps no -90 degree X "
                                         "rotation, the conversion is baked into meshes, nodes and the clip. Blender's "
                                         "baked space transform is not used, it breaks object animation."},
                 "glb": "glTF +Y up; Unity glTF importers mirror X, giving the same mapping"},
        "root": {"name": root.name, "properties": {key: str(root[key]) for key in root.keys()
                                                   if key.startswith("ce_")}},
        "anchors": anchors, "nodes": nodes,
        "renderers": [renderer_entry(obj) for obj in [*renderers, *lods]],
        "materials": {name: palette["materials"][name] for name in
                      sorted({m.name for obj in renderers for m in obj.data.materials})},
        "lods": {"convention": "Cubegen <part>_LOD0 / <part>_LOD1 siblings; Unity's FBX import builds a LODGroup "
                               "on their parent; collision only from LOD0",
                 "groups": [{"parent": parent,
                             "LOD0": [obj.name for obj in renderers if obj.parent.name == parent],
                             "LOD1": [obj.name for obj in lods if obj.parent.name == parent]} for parent in parents],
                 "LOD0": {"triangles": lod0_tris}, "LOD1": {"triangles": lod1_tris,
                                                         "ratio": round(lod1_tris / lod0_tris, 4)}},
        "colliders": colliders,
        "clips": [clip_info] if clip_info else [],
        "source": source_info,
        "files": {kind: {"path": path.name, "sha256": file_sha256(path)} for kind, path in files.items()},
    }


# --------------------------------------------------------------------------------------------- QA
class Checks:
    def __init__(self):
        self.results = {}

    def add(self, name, passed, **details):
        self.results[name] = {"passed": bool(passed), **details}

    def add_error(self, name, error):
        self.results[name] = {"passed": False, "error": f"{type(error).__name__}: {error}"}

    @property
    def passed(self):
        return bool(self.results) and all(result["passed"] for result in self.results.values())


def find(name):
    exact = bpy.data.objects.get(name)
    if exact is not None:
        return exact
    matches = [obj for obj in bpy.data.objects if base_name(obj.name) == name]
    return matches[0] if len(matches) == 1 else None


def check_blend(checks, path, source, expected, palette):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene = bpy.context.scene
    root = scene.objects[expected["root"]]
    renderers = [obj for obj in tree(root) if obj.type == "MESH" and obj.get("ce_lod") == 0]
    lods = [obj for obj in tree(root) if obj.type == "MESH" and obj.get("ce_lod") == 1]
    stray = [obj.name for obj in tree(root) if obj.type == "MESH" and obj.get("ce_lod") not in (0, 1)]
    static = [obj for obj in renderers if obj["ce_role"] == "static"]
    checks.add("renderers_in_target", len(static) <= 1 and len(renderers) <= MAX_RENDERERS and not stray
               and len(renderers) == len(expected["groups"]) and len(lods) == len(renderers),
               lod0=len(renderers), lod1=len(lods), static=len(static), limit=MAX_RENDERERS,
               source_meshes=source["mesh_count"], source_nodes=source["node_count"],
               game_nodes=len(tree(root)), stray_meshes=stray)
    used = sorted({m.name for obj in [*renderers, *lods] for m in obj.data.materials})
    checks.add("materials_in_target", 0 < len(used) <= palette["max_materials_per_tool"]
               and all(name in palette["materials"] for name in used), materials=used,
               limit=palette["max_materials_per_tool"])
    frames = source["frames"]
    worst = {"bounds": 0.0, "groups": 0.0, "anchors": 0.0, "nodes": 0.0}
    missing = [name for name in source["matrices"][frames[0]] if name not in scene.objects]
    for frame in frames:
        set_frame(scene, frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        found = bounds_of(renderers, depsgraph)
        worst["bounds"] = max(worst["bounds"], bounds_error(found, source["bounds"][frame]))
        for group in expected["groups"]:
            current = bounds_of([scene.objects[group["renderer"]]], depsgraph)
            worst["groups"] = max(worst["groups"], bounds_error(current, source["group_bounds"][frame][group["name"]]))
        for name, matrix in source["matrices"][frame].items():
            if name in scene.objects:
                key = "anchors" if name.startswith("Socket_") else "nodes"
                worst[key] = max(worst[key], matrix_error(matrix_list(scene.objects[name].matrix_world), matrix))
    set_frame(scene, frames[0])
    first = bounds_of(renderers, bpy.context.evaluated_depsgraph_get())
    checks.add("bounds_lod0", worst["bounds"] <= BOUNDS_TOLERANCE_M and worst["groups"] <= BOUNDS_TOLERANCE_M,
               tolerance_m=BOUNDS_TOLERANCE_M, max_error_m=worst["bounds"], max_part_error_m=worst["groups"],
               frames=len(frames), bounds_m=first, source_bounds_m=source["bounds"][frames[0]])
    anchors = [name for name in source["matrices"][frames[0]] if name.startswith("Socket_")]
    checks.add("anchors_identical", not missing and anchors and worst["anchors"] <= ANCHOR_TOLERANCE
               and worst["nodes"] <= ANCHOR_TOLERANCE, anchors=anchors, missing=missing,
               max_matrix_error=worst["anchors"], max_node_error=worst["nodes"], frames=len(frames))
    if expected["clip"]:
        markers = sorted((marker.name, marker.frame) for marker in scene.timeline_markers)
        keys = sorted(game_key_frames(root))
        checks.add("clip_blend", scene.name == expected["clip"]["name"]
                   and [scene.frame_start, scene.frame_end] == [source["frame_start"], source["frame_end"]]
                   and abs(scene.render.fps / scene.render.fps_base - source["fps"]) < 1e-6
                   and markers == source["markers"] and keys == source["key_frames"]
                   and {k: str(root[k]) for k in root.keys() if k.startswith("ce_")} == source["root_properties"],
                   frames=scene.frame_end - scene.frame_start + 1, markers=markers, key_frames=len(keys))
    lod0_tris = sum(triangles(obj.data) for obj in renderers)
    lod1_tris = sum(triangles(obj.data) for obj in lods)
    ratio = lod1_tris / lod0_tris
    depsgraph = bpy.context.evaluated_depsgraph_get()
    lod_errors = {}
    for obj in lods:
        twin = scene.objects[obj.name[:-1] + "0"]
        reference = bounds_of([twin], depsgraph)
        diagonal = math.dist(reference[0], reference[1])
        lod_errors[obj.name] = {"error_m": bounds_error(bounds_of([obj], depsgraph), reference),
                                "limit_m": LOD1_BOUNDS_RELATIVE * diagonal,
                                "same_parent": obj.parent == twin.parent
                                and matrix_error(obj.matrix_world, twin.matrix_world) < 1e-9,
                                "same_materials": [m.name for m in obj.data.materials] ==
                                [m.name for m in twin.data.materials],
                                "same_shape_keys": (obj.data.shape_keys is None) == (twin.data.shape_keys is None)
                                and (obj.data.shape_keys is None or bool(action_of(obj.data.shape_keys)))}
    checks.add("lod1", LOD1_RANGE[0] <= ratio <= LOD1_RANGE[1]
               and all(e["error_m"] <= e["limit_m"] and e["same_parent"] and e["same_materials"]
                       and e["same_shape_keys"] for e in lod_errors.values()),
               lod0_triangles=lod0_tris, lod1_triangles=lod1_tris, ratio=round(ratio, 4), range=LOD1_RANGE,
               parts=lod_errors)
    return [obj.name for obj in renderers], [obj.name for obj in lods]


def game_key_frames(root):
    frames = set()
    for obj in tree(root):
        for owner in (obj, obj.data.shape_keys if obj.type == "MESH" and obj.data.shape_keys else None):
            action = action_of(owner) if owner is not None else None
            if action:
                for curve in action_curves(action):
                    frames.update(int(round(point.co.x)) for point in curve.keyframe_points)
    return frames


def collider_box(collider):
    data = collider["blender"]
    return (data["center"], data["axes"], data["half_extents"])


def check_colliders(checks, contract, source, tool_id):
    bounds = source["bounds"][source["frames"][0]]
    matrices = source["matrices"][source["frames"][0]]
    world_boxes, outside, worst = [], [], 0.0
    for collider in contract["colliders"]:
        matrix = Matrix(matrices[collider["blender"]["space"]])
        corners = [matrix @ Vector(corner) for corner in box_corners(collider_box(collider))]
        excess = max(max(bounds[0][i] - c[i], c[i] - bounds[1][i]) for c in corners for i in range(3))
        worst = max(worst, excess)
        if excess > COLLIDER_SLACK_M:
            outside.append(collider["blender"]["space"])
        world_boxes.append((matrix.inverted(), collider_box(collider)))
    probes = []
    for first, second, factor, offset in OPENING_PROBES.get(tool_id, []):
        a = Matrix(matrices[first]).to_translation()
        b = Matrix(matrices[second]).to_translation() if second else a
        point = a.lerp(b, factor) + Vector(offset)
        blocked = [i for i, (inverse, box) in enumerate(world_boxes) if point_in_box(inverse @ point, box)]
        probes.append({"between": [first, second, factor], "offset_m": list(offset), "point": [round(v, 5) for v in point], "blocked_by": blocked})
    sizes_ok = all(min(c["size"]) > 0 and abs(sum(q * q for q in c["rotation"]) - 1) < 1e-4
                   for c in contract["colliders"])
    checks.add("collision", bool(contract["colliders"]) and sizes_ok and not outside
               and not any(probe["blocked_by"] for probe in probes),
               shapes=len(contract["colliders"]), rotated=sum(c["rotation"] != [0.0, 0.0, 0.0, 1.0]
                                                              for c in contract["colliders"]),
               outside_bounds=outside, max_outside_m=round(worst, 6), slack_m=COLLIDER_SLACK_M,
               opening_probes=probes)


def check_import(checks, kind, path, source, expected):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if kind == "glb":
        result = bpy.ops.import_scene.gltf(filepath=str(path))
    else:
        result = bpy.ops.import_scene.fbx(filepath=str(path))
    if "FINISHED" not in result:
        raise RuntimeError(f"{kind} import failed")
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    names = {base_name(obj.name) for obj in scene.objects}
    wanted = [expected["root"], *expected["renderers"], *expected["lods"], *source["matrices"][source["frames"][0]]]
    missing = sorted({name for name in wanted if name not in names})
    slots = {}
    for name in [*expected["renderers"], *expected["lods"]]:
        obj = find(name)
        slots[name] = sorted({base_name(m.name) for m in obj.data.materials if m}) if obj else None
    slots_ok = all(slots[name] == sorted(set(expected["materials"][name])) for name in slots)
    details = {"missing_names": missing, "material_slots_ok": slots_ok}
    start = 1.0
    clip = expected["clip"]
    clip_ok = True
    if clip:
        animated = [find(name) for name in clip["animated_nodes"]]
        actions = [action_of(obj) for obj in animated if obj is not None]
        morphs = [find(name) for name in clip["morph_renderers"]]
        morph_actions = [key_action(obj) for obj in morphs if obj is not None]
        clip_ok = len(actions) == len(clip["animated_nodes"]) and len(morph_actions) == len(clip["morph_renderers"]) \
            and all(morph_actions)
        if actions:
            start = min(float(action.frame_range[0]) for action in actions)
            length = max(float(action.frame_range[1]) for action in actions) - start + 1
            clip_ok = clip_ok and abs(length - clip["frames"]) < .01
            details["frames"] = length
        if kind == "glb":
            document = glb_document(path)
            names_in_file = [animation.get("name") for animation in document.get("animations", [])]
            clip_ok = clip_ok and names_in_file == [clip["name"]]
            details["animations"] = names_in_file
        else:
            take = sorted({action.name.split("|")[-1] for action in actions + morph_actions if action})
            clip_ok = clip_ok and take == [clip["name"]]
            details["takes"] = take
    worst_matrix = worst_bounds = 0.0
    frames = expected["sample_frames"] if clip else [source["frames"][0]]
    offset = start - source["frame_start"]
    for frame in frames:
        set_frame(scene, frame + offset)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for name, matrix in source["matrices"][frame].items():
            obj = find(name)
            if obj is not None:
                worst_matrix = max(worst_matrix, matrix_error(matrix_list(obj.matrix_world), matrix))
        for group in expected["groups"]:
            obj = find(group["renderer"])
            if obj is not None:
                current = bounds_of([obj], depsgraph)
                worst_bounds = max(worst_bounds, bounds_error(current, source["group_bounds"][frame][group["name"]]))
    details.update({"sampled_frames": frames, "max_matrix_error": worst_matrix, "max_bounds_error_m": worst_bounds})
    checks.add(f"roundtrip_{kind}", not missing and slots_ok and clip_ok and worst_matrix <= ROUNDTRIP_MATRIX_TOLERANCE
               and worst_bounds <= ROUNDTRIP_BOUNDS_TOLERANCE_M, **details)


# --------------------------------------------------------------------------------------------- preview
def render_preview(work, asset, out):
    """Small Eevee comparison: world model | game LOD0 | game LOD1 | LOD0 with the collision boxes."""
    contract = json.loads((work / "unity_contract.json").read_text())
    panels = []
    for index, (source, lod, boxes) in enumerate(((asset + ".blend", None, False), (asset + "_Game.blend", 0, False),
                                                  (asset + "_Game.blend", 1, False), (asset + "_Game.blend", 0, True))):
        bpy.ops.wm.open_mainfile(filepath=str(work / source))
        scene = bpy.context.scene
        root = scene.objects[asset]
        keep = set(tree(root))
        for obj in list(scene.objects):
            if obj not in keep:
                bpy.data.objects.remove(obj)
        for obj in tree(root):
            if obj.type == "MESH" and lod is not None:
                obj.hide_render = obj.get("ce_lod") != lod
        set_frame(scene, scene.frame_start)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        visible = [obj for obj in tree(root) if obj.type == "MESH" and not obj.hide_render]
        lo, hi = bounds_of(visible, depsgraph)
        center = Vector([(lo[i] + hi[i]) / 2 for i in range(3)])
        size = max(hi[i] - lo[i] for i in range(3))
        camera_data = bpy.data.cameras.new("PreviewCamera")
        camera_data.type = "ORTHO"
        camera = bpy.data.objects.new("PreviewCamera", camera_data)
        scene.collection.objects.link(camera)
        camera.location = center + Vector((1.0, -1.0, .55)).normalized() * size * 3
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        view = camera.rotation_euler.to_matrix().inverted()
        corners = [view @ (Vector((x, y, z)) - center) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
                   for z in (lo[2], hi[2])]
        width = max(c.x for c in corners) - min(c.x for c in corners)
        height = max(c.y for c in corners) - min(c.y for c in corners)
        camera_data.ortho_scale = max(width, height * 16 / 9) * 1.12
        scene.camera = camera
        label = bpy.data.curves.new("PreviewLabel", "FONT")
        label.body = ("World model", "Game LOD0", "Game LOD1", "Collision (LOD0)")[index]
        label.size = camera_data.ortho_scale * .045
        text = bpy.data.objects.new("PreviewLabel", label)
        scene.collection.objects.link(text)
        text.rotation_euler = camera.rotation_euler
        text.location = center + camera.rotation_euler.to_matrix() @ Vector(
            (-camera_data.ortho_scale * .47, camera_data.ortho_scale * 9 / 16 * .40, size))
        glow = bpy.data.materials.new("PreviewLabel")
        glow.use_nodes = True
        glow.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1, 1, 1, 1)
        glow.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.0
        label.materials.append(glow)
        sun_data = bpy.data.lights.new("PreviewSun", "SUN")
        sun_data.energy = 3.0
        sun = bpy.data.objects.new("PreviewSun", sun_data)
        scene.collection.objects.link(sun)
        sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
        world = bpy.data.worlds.new("PreviewWorld")
        world.use_nodes = True
        world.node_tree.nodes["Background"].inputs["Color"].default_value = (.08, .09, .11, 1)
        world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
        scene.world = world
        if boxes:
            wire = bpy.data.materials.new("PreviewCollider")
            wire.diffuse_color = (1, .1, .6, 1)
            wire.use_nodes = True
            node = wire.node_tree.nodes["Principled BSDF"]
            node.inputs["Base Color"].default_value = (1, .1, .6, 1)
            node.inputs["Emission Color"].default_value = (1, .1, .6, 1)
            node.inputs["Emission Strength"].default_value = 2.0
            for number, collider in enumerate(contract["colliders"]):
                data = collider["blender"]
                space = scene.objects[data["space"]]
                mesh = bpy.data.meshes.new(f"PreviewBox{number}")
                corners = box_corners(collider_box(collider))
                edges = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
                mesh.from_pydata(corners, edges, [])
                box = bpy.data.objects.new(f"PreviewBox{number}", mesh)
                scene.collection.objects.link(box)
                box.matrix_world = space.matrix_world
                modifier = box.modifiers.new("Wire", "SKIN")
                for vertex in box.data.skin_vertices[0].data:
                    vertex.radius = (size * .004, size * .004)
                box.data.materials.append(wire)
        scene.render.engine = "BLENDER_EEVEE"
        scene.render.resolution_x, scene.render.resolution_y = 640, 360
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = False
        scene.view_settings.view_transform = "Standard"
        scene.render.filepath = str(work / f"_preview_{index}.png")
        bpy.ops.render.render(write_still=True)
        panels.append(work / f"_preview_{index}.png")
    images = [bpy.data.images.load(str(path)) for path in panels]
    width, height = images[0].size
    pixels = [np.array(image.pixels[:], dtype=np.float32).reshape(height, width, 4) for image in images]
    top = np.concatenate([pixels[2], pixels[3]], axis=1)      # Blender images start at the bottom row
    bottom = np.concatenate([pixels[0], pixels[1]], axis=1)
    combined = np.concatenate([top, bottom], axis=0)
    result = bpy.data.images.new("GamePreview", width * 2, height * 2)
    result.pixels = combined.ravel()
    result.filepath_raw = str(out)
    result.file_format = "PNG"
    result.save()
    for path in panels:
        path.unlink()
    return out


# --------------------------------------------------------------------------------------------- main
def export(work, tool, palette):
    asset, clip_name = tool["asset"], tool.get("clip")
    source_path = work / (asset + ".blend")
    game = asset + "_Game"
    bpy.ops.wm.open_mainfile(filepath=str(source_path))
    scene = bpy.context.scene
    root = scene.objects[asset]
    clip_name = clip_name if any(action_of(obj) or key_action(obj) for obj in tree(root)) else None
    frames = list(range(scene.frame_start, scene.frame_end + 1)) if clip_name else [scene.frame_start]
    groups = classify(root, frames, asset)
    meshes = [obj for obj in tree(root) if obj.type == "MESH"]
    source = record_source(scene, root, groups, frames)
    source.update({
        "frame_start": scene.frame_start, "frame_end": scene.frame_end, "fps": scene.render.fps / scene.render.fps_base,
        "markers": sorted((marker.name, marker.frame) for marker in scene.timeline_markers),
        "key_frames": sorted(game_key_frames(root)),
        "root_properties": {key: str(root[key]) for key in root.keys() if key.startswith("ce_")},
        "mesh_count": len(meshes), "node_count": len(tree(root)),
        "triangles": sum(triangles(obj.data) for obj in meshes)})
    source_clip_name = str(root.get("ce_action_clip", clip_name)) if clip_name else None
    colliders = collision_boxes(root, groups, scene)
    # Build: drop the presentation rig, palette, merge, LOD1.
    keep = set(tree(root))
    for other in [other for other in bpy.data.scenes if other != scene]:
        bpy.data.scenes.remove(other)
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj)
    materials = palette_materials(palette)
    used_sources = remap_materials(root, palette, materials)
    collection = root.users_collection[0]
    set_frame(scene, scene.frame_start)
    renderers = [merge_group(group, collection) for group in groups]
    lods = build_lods(renderers, collection)
    if clip_name:
        scene.name = clip_name                 # the FBX take carries the scene name
    set_frame(scene, scene.frame_start)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    files = {"blend": work / (game + ".blend"), "fbx": work / (game + ".fbx"), "glb": work / (game + ".glb")}
    bpy.ops.wm.save_as_mainfile(filepath=str(files["blend"]), compress=False)
    export_files(scene, root, work, game, clip_name)
    from version import CODENAME, VERSION
    animated_nodes = sorted(obj.name for obj in tree(root) if action_of(obj))
    morph_renderers = sorted(obj.name for obj in renderers if obj.data.shape_keys)
    clip_info = None
    if clip_name:
        clip_info = {"name": clip_name, "source_name": source_clip_name, "frame_start": scene.frame_start,
                     "frame_end": scene.frame_end, "frames": scene.frame_end - scene.frame_start + 1,
                     "fps": source["fps"],
                     "duration_seconds": (scene.frame_end - scene.frame_start) / source["fps"],
                     "loop": False, "autoplay": False,
                     "events": [{"name": name, "frame": frame, "seconds": (frame - scene.frame_start) / source["fps"]}
                                for name, frame in source["markers"]],
                     "key_frames": source["key_frames"] if len(source["key_frames"]) <= 24 else "every frame",
                     "animated_nodes": animated_nodes, "morph_renderers": morph_renderers,
                     "visibility_nodes": sorted(obj.name for obj in tree(root) if obj.get("ce_visibility_animation"))}
    source_info = {"asset": asset, "blend": source_path.name, "sha256": file_sha256(source_path),
                   "nodes": source["node_count"], "meshes": source["mesh_count"], "triangles": source["triangles"],
                   "materials": used_sources, "palette": {"path": "data/game_palette.json",
                                                          "sha256": file_sha256(PALETTE_PATH)},
                   "version": f"{VERSION} {CODENAME}"}
    contract = build_contract(tool, source_info, root, renderers, lods, colliders, clip_info, palette, files)
    (work / "unity_contract.json").write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n")
    expected = {"root": asset, "renderers": [obj.name for obj in renderers], "lods": [obj.name for obj in lods],
                "groups": [{"name": group.name, "renderer": group.name + "_LOD0"} for group in groups],
                "materials": {obj.name: [m.name for m in obj.data.materials] for obj in [*renderers, *lods]},
                "clip": clip_info and dict(clip_info, frames=clip_info["frames"]),
                "sample_frames": sample_frames(scene.frame_start, scene.frame_end, [f for _, f in source["markers"]],
                                               source["key_frames"]) if clip_name else frames}
    return source, contract, expected, files


def main():
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description="Merged, matte game export of a toolgen world model")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--preview", action="store_true", help="also render preview_game.png (Eevee, 2x2 panels)")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    work = args.directory.resolve()
    checks = Checks()
    timings = {}
    report = {"tool": args.tool, "passed": False}
    try:
        tools = {tool["id"]: tool for tool in json.loads(TOOLS_PATH.read_text())["tools"]}
        tool = tools[args.tool]
        report["asset"] = tool["asset"]
        palette = json.loads(PALETTE_PATH.read_text())
        errors = validate_palette(palette)
        checks.add("palette", not errors, errors=errors)
        if errors:
            raise RuntimeError("; ".join(errors))
        phase = time.perf_counter()
        source, contract, expected, files = export(work, tool, palette)
        timings["export"] = time.perf_counter() - phase
        phase = time.perf_counter()
        check_blend(checks, files["blend"], source, expected, palette)
        check_colliders(checks, contract, source, args.tool)
        for kind in ("glb", "fbx"):
            try:
                check_import(checks, kind, files[kind], source, expected)
            except Exception as error:  # noqa: BLE001 - every failure belongs into the report
                traceback.print_exc()
                checks.add_error(f"roundtrip_{kind}", error)
        timings["qa"] = time.perf_counter() - phase
        report.update({"renderers": {"LOD0": expected["renderers"], "LOD1": expected["lods"]},
                       "triangles": {"source": source["triangles"], "LOD0": contract["lods"]["LOD0"]["triangles"],
                                     "LOD1": contract["lods"]["LOD1"]["triangles"]},
                       "materials": sorted(contract["materials"]), "colliders": len(contract["colliders"])})
        if args.preview:
            phase = time.perf_counter()
            report["preview"] = render_preview(work, tool["asset"], work / "preview_game.png").name
            timings["preview"] = time.perf_counter() - phase
    except Exception as error:  # noqa: BLE001 - reported as a failed QA with exit code 1
        traceback.print_exc()
        checks.add_error("export", error)
    report.update({"passed": checks.passed, "checks": checks.results,
                   "seconds": round(time.perf_counter() - started, 3),
                   "timings_seconds": {key: round(value, 3) for key, value in timings.items()}})
    work.mkdir(parents=True, exist_ok=True)
    (work / "qa_game.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    failed = [name for name, result in checks.results.items() if not result["passed"]]
    if failed:
        print(f"GAME_EXPORT_FAILED {args.tool}: {', '.join(failed)}", flush=True)
        sys.stdout.flush()
        sys.exit(1)
    print(f"GAME_EXPORT_OK {args.tool}: {report['renderers']['LOD0']} materials={report['materials']} "
          f"triangles={report['triangles']} colliders={report['colliders']} {report['seconds']:.1f}s", flush=True)


if __name__ == "__main__":
    main()
