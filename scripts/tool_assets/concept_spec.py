"""Concept geometry of cubeescape-formgen (geometry-spec 1, ``KXnn.geo.json``) for the weapons (Toolgen 0.18, TG-A).

Pure Python (no bpy): concept_kit.py builds the meshes from ``plan()``, tests/test_concepts.py checks the rules. The sheets
live in data/concepts/ with their provenance (``provenance.json``: release tag, zip sha256 and sha256 per file, written by
scripts/import_concepts.py); the pipeline copies that folder into the authoring copy as ``concepts/`` (no network in the
build). A file whose sha256 differs from its provenance entry is refused.

Frame of the spec = Toolgen's frame: metres, forward -Y, up +Z, left +X, origin Socket_Hand. What Toolgen decides on top of
the spec (docs/TECHNIK.md › Konzeptmodelle, docs/ENTSCHEIDUNGEN.md, 20.10.2026):

* **Glass** (user decision 20.10.2026, way A "open"): sight glass parts are not built; the window stays open, frame, emitter
  and housing are geometry. Cube Escape draws tint and reticle at Socket_Reticle (CE-A).
* **Open parts** (a part whose edges are not all shared by two faces, e.g. the four faces of a sight frame) are merged with
  the parts of the same look (label, channel, material, emissive, sight, moving node) into one closed mesh; closed parts
  stay one mesh each. Merged meshes keep the name of their first part and list all ids (``ids``).
* **Coplanar faces** (Toolgen rule: faces of different meshes, normals within 1 degree, closer than 0.5 mm, overlapping at
  least 1 mm2) are resolved by setting the faces of the smaller mesh 0.5 mm back along their normal (``coplanar_fixes``).
* **Collision**: a sight part around the open window (bounds holding Socket_Reticle) carries ``ce_collision`` "none"; the
  game export gives it no box, so the window stays open (opening probe at Socket_Reticle).
* **Bevels** (decision 3 of the formgen plan, 19.10.2026): 0.5-2 mm by part size (``BEVEL_RATIO`` x smallest extent),
  none on glowing parts; edges sharper than ``BEVEL_ANGLE`` next to a hard face.
* **Sockets**: Socket_Hand/SupportHand/Muzzle/CenterOfMass from ``anchors``; Socket_Sight from ``sight.socket_sight_rear_m``
  (rear end of the sight on its line, Toolgen's rule; ``anchors.Socket_Sight`` of the spec is the rail top); Socket_Reticle
  (new, additive) from ``sight.socket_reticle_m``; Socket_Eye only for scopes (the spec's eye point of open sights is a
  proposal and equals Socket_Sight). A named correction in ``corrections.json`` replaces an anchor (KG02 Socket_SupportHand,
  user decision 20.10.2026: the first-person framing rule comes before the sheet's measured anchor).
"""
import hashlib
import json
import math
from pathlib import Path

FORMAT = "cubeescape-design/geometry-spec"
FORMAT_VERSION = 1
PROVENANCE = "provenance.json"
CORRECTIONS = "corrections.json"     # named Toolgen corrections (anchor, spec value, Toolgen value, reason, decision)
FOLDERS = (Path(__file__).resolve().parent / "concepts",                       # authoring copy (generate_tools.py)
           Path(__file__).resolve().parents[2] / "data" / "concepts")           # repository

# MT_ channel of the spec -> source material of weapon_kit.Kit (data/game_palette.json maps it back to the MT_ slot);
# None = the element glow of the weapon (MT_Energy).
CHANNELS = {"MT_Primary": "Primary", "MT_Secondary": "Secondary", "MT_Accent": "Accent", "MT_Metal": "Metal",
            "MT_Detail": "Detail", "MT_Emission": "Display", "MT_Energy": None}
# Toolgen nodes of parts by their label where moving_parts has none (Toolgen's convention: the reload clip moves
# Anim_Magazine, data/ego_clips.json reload.part).
LABEL_NODES = {"Magazin": "Anim_Magazine"}
COPLANAR_GAP_M = .0005
COPLANAR_ANGLE_DEGREES = 1.0
COPLANAR_MIN_OVERLAP_M2 = 1e-6
BEVEL_MIN_M = .0005
BEVEL_MAX_M = .002
BEVEL_RATIO = .035
BEVEL_ANGLE = .7                # radians between face normals, like the kit's primitives (create_portal_gun.mesh)
DIGITS = 6


class ConceptError(ValueError):
    pass


def folder():
    for candidate in FOLDERS:
        if (candidate / PROVENANCE).is_file():
            return candidate
    raise ConceptError(f"no {PROVENANCE} in {[str(path) for path in FOLDERS]}")


def provenance(where=None):
    return json.loads(((where or folder()) / PROVENANCE).read_text())


def load(file, where=None):
    """The verified spec ``file`` (e.g. 'KG02.geo.json'): sha256 equal to its provenance entry, format and version known.
    Unknown fields are ignored (geometry-spec contract)."""
    where = where or folder()
    record = next((entry for entry in provenance(where)["imported"].values() if entry["file"] == file), None)
    if record is None:
        raise ConceptError(f"{file} has no provenance entry")
    data = (where / file).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != record["sha256"]:
        raise ConceptError(f"{file}: sha256 {digest} differs from its provenance {record['sha256']}")
    spec = json.loads(data)
    if spec.get("format") != FORMAT or spec.get("format_version") != FORMAT_VERSION:
        raise ConceptError(f"{file}: {spec.get('format')} {spec.get('format_version')} is not {FORMAT} {FORMAT_VERSION}")
    if spec["sheet"]["kind"] != "weapon":
        raise ConceptError(f"{file}: sheet kind {spec['sheet']['kind']} is not a weapon")
    return spec


# ------------------------------------------------------------------------------------------------------- geometry
def sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def face_normal(points):
    """Newell normal of a planar polygon (unit; concave polygons are fine)."""
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    length = math.sqrt(dot(n, n))
    return [c / length for c in n] if length else [0.0, 0.0, 0.0]


def edge_counts(faces):
    counts = {}
    for face in faces:
        for i, a in enumerate(face):
            key = tuple(sorted((a, face[(i + 1) % len(face)])))
            counts[key] = counts.get(key, 0) + 1
    return counts


def is_closed(faces):
    return all(count == 2 for count in edge_counts(faces).values())


def volume(vertices, faces):
    total = 0.0
    for face in faces:
        a = vertices[face[0]]
        for i in range(1, len(face) - 1):
            total += dot(a, cross(vertices[face[i]], vertices[face[i + 1]])) / 6
    return total


def bounds(vertices):
    return ([min(v[i] for v in vertices) for i in range(3)], [max(v[i] for v in vertices) for i in range(3)])


def weld(parts):
    """One mesh of several parts: equal positions (0.01 mm grid of the spec) become one vertex."""
    vertices, index, faces, hard = [], {}, [], []
    for part in parts:
        mesh = part["mesh"]
        local = []
        for vertex in mesh["vertices"]:
            key = tuple(round(c, 5) for c in vertex)
            if key not in index:
                index[key] = len(vertices)
                vertices.append(list(vertex))
            local.append(index[key])
        faces += [[local[i] for i in face] for face in mesh["faces"]]
        hard += list(mesh["hard"])
    return vertices, faces, hard


# ------------------------------------------------------------------------------------- coplanar overlap (2D)
def project(points, normal):
    """2D coordinates of points in the plane with ``normal``."""
    axis = min(range(3), key=lambda i: abs(normal[i]))
    helper = [0.0, 0.0, 0.0]
    helper[axis] = 1.0
    u = cross(normal, helper)
    length = math.sqrt(dot(u, u))
    u = [c / length for c in u]
    v = cross(normal, u)
    return [(dot(p, u), dot(p, v)) for p in points]


def area2(polygon):
    return sum(polygon[i][0] * polygon[(i + 1) % len(polygon)][1] - polygon[(i + 1) % len(polygon)][0] * polygon[i][1]
               for i in range(len(polygon))) / 2


def ear_clip(polygon):
    """Triangles of a simple 2D polygon (counter-clockwise after this call)."""
    points = list(polygon) if area2(polygon) > 0 else list(reversed(polygon))
    index = list(range(len(points)))
    triangles = []

    def inside(p, a, b, c):
        return all(((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) >= -1e-15
                   for a, b in ((a, b), (b, c), (c, a)))

    guard = 0
    while len(index) > 3 and guard < 10000:
        guard += 1
        for k in range(len(index)):
            i0, i1, i2 = index[k - 1], index[k], index[(k + 1) % len(index)]
            a, b, c = points[i0], points[i1], points[i2]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) <= 1e-18:
                continue
            if any(inside(points[j], a, b, c) for j in index if j not in (i0, i1, i2)):
                continue
            triangles.append((a, b, c))
            index.pop(k)
            break
        else:
            break                                   # degenerate rest (collinear points): nothing left with area
    if len(index) == 3:
        triangles.append(tuple(points[i] for i in index))
    return triangles


def clip(subject, clipper):
    """Sutherland-Hodgman: subject polygon clipped by a convex counter-clockwise polygon."""
    output = list(subject)
    for i in range(len(clipper)):
        a, b = clipper[i], clipper[(i + 1) % len(clipper)]
        source, output = output, []
        if not source:
            break

        def side(p):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        for j, p in enumerate(source):
            q = source[(j + 1) % len(source)]
            sp, sq = side(p), side(q)
            if sp >= 0:
                output.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq)
                output.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return output


def overlap(first, second, normal):
    """Overlap area (m2) of two planar polygons (3D points) seen along ``normal``."""
    one, two = ear_clip(project(first, normal)), ear_clip(project(second, normal))
    total = 0.0
    for a in one:
        for b in two:
            piece = clip(list(a), list(b))
            if len(piece) >= 3:
                total += abs(area2(piece))
    return total


def coplanar_pairs(meshes, gap=COPLANAR_GAP_M):
    """Pairs of faces of different meshes that would z-fight: same direction (within 1 degree), closer than ``gap`` along
    the normal, overlapping at least 1 mm2. Returns sorted [(mesh a, mesh b, face a, face b, distance, overlap)]."""
    cosine = math.cos(math.radians(COPLANAR_ANGLE_DEGREES))
    faces = []
    for m, mesh in enumerate(meshes):
        for f, face in enumerate(mesh["faces"]):
            points = [mesh["vertices"][i] for i in face]
            normal = face_normal(points)
            centre = [sum(p[i] for p in points) / len(points) for i in range(3)]
            low, high = bounds(points)
            faces.append((m, f, points, normal, centre, low, high))
    found = []
    for i, (ma, fa, pa, na, ca, la, ha) in enumerate(faces):
        for mb, fb, pb, nb, cb, lb, hb in faces[i + 1:]:
            if ma == mb or dot(na, nb) < cosine:
                continue
            if any(la[k] > hb[k] + gap or lb[k] > ha[k] + gap for k in range(3)):
                continue
            distance = abs(dot(na, sub(cb, ca)))
            if distance >= gap - 1e-7:              # exactly the gap counts as resolved (0.01 mm grid of the spec)
                continue
            area = overlap(pa, pb, na)
            if area >= COPLANAR_MIN_OVERLAP_M2:
                pair = (ma, mb, fa, fb) if ma < mb else (mb, ma, fb, fa)
                found.append((*pair, round(distance, 9), round(area, 9)))
    return sorted(found)


def resolve_coplanar(meshes):
    """Sets the coplanar faces of the smaller mesh of each pair 0.5 mm back along their normal (vertices move, so the
    neighbouring faces follow). Returns the fixes; raises when pairs remain."""
    fixes = {}
    for _ in range(4):
        pairs = coplanar_pairs(meshes)
        if not pairs:
            break
        moved = {}
        for ma, mb, fa, fb, distance, area in pairs:
            size = [abs(volume(meshes[m]["vertices"], meshes[m]["faces"])) for m in (ma, mb)]
            m, f = (ma, fa) if size[0] <= size[1] else (mb, fb)
            moved.setdefault(m, set()).add(f)
            key = (meshes[m]["name"], meshes[mb if m == ma else ma]["name"])
            fix = fixes.setdefault(key, {"moved": key[0], "other": key[1], "faces": 0, "min_distance_m": distance,
                                         "max_overlap_m2": area, "gap_m": COPLANAR_GAP_M})
            fix["faces"] += 1
            fix["min_distance_m"] = min(fix["min_distance_m"], distance)
            fix["max_overlap_m2"] = max(fix["max_overlap_m2"], area)
        for m, face_ids in sorted(moved.items()):
            mesh = meshes[m]
            shift = {}
            for f in sorted(face_ids):
                face = mesh["faces"][f]
                normal = face_normal([mesh["vertices"][i] for i in face])
                for i in face:
                    shift.setdefault(i, [0.0, 0.0, 0.0])
                    for k in range(3):
                        # one step per vertex and direction (two faces of a corner both move it)
                        if abs(shift[i][k]) < abs(normal[k]) * COPLANAR_GAP_M:
                            shift[i][k] = -normal[k] * COPLANAR_GAP_M
            for i, delta in shift.items():
                mesh["vertices"][i] = [round(mesh["vertices"][i][k] + delta[k], 7) for k in range(3)]
    remaining = coplanar_pairs(meshes)
    if remaining:
        raise ConceptError(f"coplanar faces remain: {remaining[:3]}")
    return [fixes[key] for key in sorted(fixes)]


def bevel_width(vertices):
    low, high = bounds(vertices)
    smallest = min(high[i] - low[i] for i in range(3))
    return round(min(BEVEL_MAX_M, max(BEVEL_MIN_M, smallest * BEVEL_RATIO), smallest * .4), DIGITS)


# ---------------------------------------------------------------------------------------------------- the plan
def look(part):
    return (part["label"], part["channel"], part["material"], bool(part["emissive"]), bool(part["sight"]),
            (part.get("moving") or {}).get("toolgen_node"))


def node_of(part):
    moving = part.get("moving") or {}
    return moving.get("toolgen_node") or LABEL_NODES.get(part["label"])


def plan(spec):
    """The meshes Toolgen builds from ``spec``: [{name, ids, label, material (Kit material or None = element glow),
    surface, glow, sight, node, vertices, faces, hard, bevel_m}] in part order, plus the report of the decisions."""
    glass = [part["id"] for part in spec["parts"] if part["glass"]]
    parts = [part for part in spec["parts"] if not part["glass"]]
    groups, order = {}, []
    for part in parts:
        key = look(part) if not is_closed(part["mesh"]["faces"]) else ("closed", part["id"])
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(part)
    meshes, merged = [], []
    for key in order:
        members = groups[key]
        first = members[0]
        vertices, faces, hard = weld(members)
        if not is_closed(faces):
            raise ConceptError(f"{spec['sheet']['id']}: {[p['id'] for p in members]} stay open after the merge")
        if volume(vertices, faces) <= 0:
            raise ConceptError(f"{spec['sheet']['id']}: {first['id']} has no positive volume (normals inward)")
        if len(members) > 1:
            merged.append([p["id"] for p in members])
        meshes.append({"name": first["name"], "ids": [p["id"] for p in members], "label": first["label"],
                       "channel": first["channel"], "material": CHANNELS[first["channel"]], "surface": first["material"],
                       "glow": bool(first["emissive"]), "sight": bool(first["sight"]), "node": node_of(first),
                       "vertices": vertices, "faces": faces, "hard": hard})
    fixes = resolve_coplanar(meshes)
    window = spec["sight"].get("socket_reticle_m") if spec["sight"].get("present") else None
    for mesh in meshes:
        mesh["bevel_m"] = 0.0 if mesh["glow"] else bevel_width(mesh["vertices"])
        # a sight part around the open window (its bounds hold the window centre) gets no collider: the box would close it
        low, high = bounds(mesh["vertices"])
        mesh["collision"] = not (mesh["sight"] and window and all(low[i] <= window[i] <= high[i] for i in range(3)))
    report = {"sheet": spec["sheet"]["id"], "glass_omitted": glass, "merged": merged, "coplanar_fixes": fixes,
              "meshes": len(meshes), "no_collision": [mesh["name"] for mesh in meshes if not mesh["collision"]],
              "spec_coplanar": spec["checks"]["coplanar"], "decals_outside_part": spec["checks"]["decals_outside_part"]}
    return meshes, report


# ---------------------------------------------------------------------------------------------- sockets / hold
def sockets(spec):
    """Socket positions (m, root space) of the world model."""
    anchors, sight = spec["anchors"], spec["sight"]
    found = {name: anchors[name]["position_m"] for name in ("Socket_Hand", "Socket_SupportHand", "Socket_Muzzle",
                                                            "Socket_CenterOfMass")}
    if sight.get("present"):
        found["Socket_Sight"] = sight["socket_sight_rear_m"]
        found["Socket_Reticle"] = sight["socket_reticle_m"]
        if sight["kind"] == "scope":
            found["Socket_Eye"] = sight["socket_eye_m"]
    return {name: [float(c) for c in position] for name, position in found.items()}


def hold(spec):
    """Hold values measured on the concept: grip tilt, sight kind, grip and support radii (data/viewmodels.json order:
    grip_radius = half width X, half depth; support_radius = half height, half width)."""
    grip, support = spec["grip"], spec["support"]
    section = grip["cross_section_m"]
    return {"grip_tilt_degrees": grip["grip_tilt_degrees"], "sight_kind": spec["sight"]["kind"],
            "grip_radius": [round(section["width_m"] / 2, 4), round(section["depth_m"] / 2, 4)],
            "support_radius": [round(support["radius_m"]["half_height_m"], 4), round(support["radius_m"]["half_width_m"], 4)]
            if support.get("radius_m") else None}


def pivot_point(meshes, node):
    """Rest place of a Toolgen node: the top centre of the meshes under it (the magazine hangs from the well)."""
    points = [vertex for mesh in meshes if mesh["node"] == node for vertex in mesh["vertices"]]
    low, high = bounds(points)
    return ((low[0] + high[0]) / 2, (low[1] + high[1]) / 2, high[2])


def empty_point(meshes):
    """Rest place of a Use-clip node without a part: the centre of the housing (first mesh labelled Gehäuse outside the
    sight)."""
    housing = next((mesh for mesh in meshes if mesh["label"] == "Gehäuse" and not mesh["sight"]), meshes[0])
    low, high = bounds(housing["vertices"])
    return tuple((low[i] + high[i]) / 2 for i in range(3))


def corrections(sheet, where=None):
    """The named Toolgen corrections of ``sheet`` (data/concepts/corrections.json), {} without any."""
    path = (where or folder()) / CORRECTIONS
    return json.loads(path.read_text())["sheets"].get(sheet, {}) if path.is_file() else {}


def apply_corrections(spec, found, where=None):
    """Replace anchors by their corrected Toolgen values; each correction must name the spec's current value (a changed
    sheet needs a new review). Returns the applied corrections for the report."""
    applied = []
    for name, entry in sorted(corrections(spec["sheet"]["id"], where).get("anchors", {}).items()):
        current = spec["anchors"][name]["position_m"]
        if [round(c, 6) for c in current] != [round(c, 6) for c in entry["spec_m"]]:
            raise ConceptError(f"{spec['sheet']['id']} {name}: the spec now says {current}, the correction was made for "
                               f"{entry['spec_m']}; review data/concepts/{CORRECTIONS}")
        found[name] = [float(c) for c in entry["toolgen_m"]]
        applied.append({"anchor": name, **entry})
    return applied


def layout(file, clip_nodes, where=None):
    """Everything a kit builds for the concept ``file``: planned meshes, pivots (node -> rest place; ``empty`` lists the
    Use-clip nodes without a part), sockets without Socket_Sight/Socket_Eye (weapon_kit sets those on the checked line)
    after the named corrections (``corrections.json``), and the report."""
    spec = load(file, where)
    meshes, report = plan(spec)
    pivots = {}
    for mesh in meshes:
        if mesh["node"] and mesh["node"] not in pivots:
            pivots[mesh["node"]] = pivot_point(meshes, mesh["node"])
    empty = [node for node in clip_nodes if node not in pivots]
    for node in empty:
        pivots[node] = empty_point(meshes)
    found = sockets(spec)
    report["corrections"] = apply_corrections(spec, found, where)
    return {"spec": spec, "meshes": meshes, "report": report, "pivots": pivots, "empty": empty, "sockets": found,
            "kit_sockets": {name: position for name, position in found.items() if name not in ("Socket_Sight", "Socket_Eye")}}


def part_names(meshes, label):
    """Mesh names (without SM_PG_) of the meshes carrying ``label``."""
    return [mesh["name"].removeprefix("SM_PG_") for mesh in meshes if mesh["label"] == label]
