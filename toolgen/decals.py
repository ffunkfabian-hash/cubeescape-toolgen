"""Decals of the weapons (Toolgen 0.13 Enamel): one-colour masks from data/decals.json, rendered by ImageMagick, and their
projection onto the weight maps.

* ``render(decal_id)``: the decal's mask (height x width, uint8 0/255) - ImageMagick draws the elements (stroke font from
  the catalogue, polylines, polygons, circles) antialiased, then thresholds at 50 %, so ImageMagick 6 and 7 differ at most
  in single edge pixels (tests/test_decals.py compares both with a tolerance). Same call pattern as Cubegen's
  ``ImageMagick.run`` (magick or convert, PATH plus the Homebrew/MacPorts folders, no date chunks: PGM output has none).
* ``project``: box projection of one anchor (weapon_designs.py DECALS: part, face, rect in part coordinates, image, channel,
  rotation) onto the texels of the target part whose face looks along the face axis; the result is a texel mask that
  surface_bake.py writes into the channel raster before the dilation (one-hot 255 stays; the decal texel takes its channel).
* ``project_region`` (0.21 Livery, stage B): a concept sheet's decal as a mask region (concept_spec.decal_regions: part,
  face, polygon as fractions of the part's box) - the same box projection with an exact point-in-polygon test instead of an
  image; ``to_life`` maps a deformed model (robot variant) back to the life-size design, so the region follows the
  deformation exactly. ``region_coverage`` compares the painted surface with the polygon's area (QA).

Pure Python plus numpy for the projection (Blender's Python has numpy).
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    import numpy as np
except ImportError:  # system Python of the unit tests: rendering and catalogue only
    np = None

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data/decals.json"
GLYPH_ADVANCE = 5                # glyph cell 4 x 6 plus one unit gap
GLYPH_HEIGHT = 6
FACES = {                        # face -> (normal axis, sign, u axis, u sign, v axis, v sign): u right, v up seen from outside
    "+x": (0, 1, 1, 1, 2, 1), "-x": (0, -1, 1, -1, 2, 1),
    "+y": (1, 1, 0, -1, 2, 1), "-y": (1, -1, 0, 1, 2, 1),
    "+z": (2, 1, 0, 1, 1, 1), "-z": (2, -1, 0, 1, 1, -1),
}
FACING_MIN = .7                  # texels whose face normal . face axis is below this get no decal (bevels, sides)
AREA_SHARE = (.005, .06)         # decal texels per island texels (QA)
ASPECT_TOLERANCE = .25           # rect (mm) against image aspect
CHANNELS = ("Primary", "Secondary", "Accent", "Metal", "Energy", "Emission", "Detail")   # surface.CHANNELS
EXTRA_DIRS = ("/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin")


class ImageMagickError(RuntimeError):
    pass


def load(path=CATALOG_PATH):
    return json.loads(Path(path).read_text())


def _which(name):
    found = shutil.which(name)
    if found:
        return found
    for folder in EXTRA_DIRS:
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def magick_command(binary=None):
    """[magick] (ImageMagick 7) or [convert] (ImageMagick 6); TOOLGEN_MAGICK overrides."""
    binary = binary or os.environ.get("TOOLGEN_MAGICK")
    if binary:
        return [shutil.which(binary) or binary]
    for name in ("magick", "convert"):
        found = _which(name)
        if found:
            return [found]
    raise ImageMagickError("ImageMagick not found (magick or convert); set TOOLGEN_MAGICK")


def magick_version(command=None):
    command = command or magick_command()
    result = subprocess.run(command + ["-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout.splitlines()[0] if result.returncode == 0 and result.stdout else "unknown"


def run(args, command=None):
    """One ImageMagick call (single thread: same pixels whatever the core count)."""
    command = command or magick_command()
    env = dict(os.environ, MAGICK_THREAD_LIMIT="1")
    result = subprocess.run(command + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if result.returncode != 0:
        raise ImageMagickError(f"ImageMagick failed ({' '.join(command + list(args)[:3])} ...): {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


# --------------------------------------------------------------------------------------------- drawing
def text_polylines(text, glyphs, x, y, height):
    """Polylines (image fractions are not used here: x, y, height in pixels) of a text in the stroke font."""
    scale = height / GLYPH_HEIGHT
    lines = []
    for index, char in enumerate(text):
        if char not in glyphs:
            raise KeyError(f"glyph {char!r} missing in the stroke font")
        for line in glyphs[char]:
            lines.append([(x + (index * GLYPH_ADVANCE + gx) * scale, y + gy * scale) for gx, gy in line])
    return lines


def text_width(text, height):
    return (len(text) * GLYPH_ADVANCE - 1) * height / GLYPH_HEIGHT


def draw_args(decal, glyphs):
    """ImageMagick arguments that draw one decal white on black (before the output)."""
    width, height = decal["size"]
    stroke = decal["stroke"] * height

    def points(values):
        return " ".join(f"{px:.3f},{py:.3f}" for px, py in values)

    def scaled(values):
        return [(px * width, py * height) for px, py in values]

    strokes, fills = [], []
    for element in decal["elements"]:
        if "polyline" in element:
            strokes.append(f"polyline {points(scaled(element['polyline']))}")
        elif "polygon" in element:
            fills.append(f"polygon {points(scaled(element['polygon']))}")
        elif "circle" in element:
            cx, cy, radius = element["circle"]
            strokes.append(f"circle {cx * width:.3f},{cy * height:.3f} {cx * width + radius * height:.3f},{cy * height:.3f}")
        elif "text" in element:
            for line in text_polylines(element["text"], glyphs, element["x"] * width, element["y"] * height,
                                       element["height"] * height):
                strokes.append(f"polyline {points(line)}")
        else:
            raise ValueError(f"unknown decal element {sorted(element)}")
    args = ["-size", f"{width}x{height}", "xc:black"]
    if fills:
        args += ["-fill", "white", "-stroke", "none", "-draw", " ".join(fills)]
    if strokes:
        args += ["-fill", "none", "-stroke", "white", "-strokewidth", f"{stroke:.3f}",
                 "-draw", "stroke-linecap round stroke-linejoin round " + " ".join(strokes)]
    return args + ["-colorspace", "Gray", "-threshold", "50%", "-depth", "8"]


def read_pgm(data):
    """(width, height, bytes) of a binary 8-bit PGM (P5)."""
    fields, position = [], 0
    while len(fields) < 4:
        while data[position:position + 1].isspace():
            position += 1
        if data[position:position + 1] == b"#":
            position = data.index(b"\n", position) + 1
            continue
        end = position
        while not data[end:end + 1].isspace():
            end += 1
        fields.append(data[position:end])
        position = end
    if fields[0] != b"P5" or int(fields[3]) != 255:
        raise ValueError("not an 8-bit binary PGM")
    width, height = int(fields[1]), int(fields[2])
    start = position + 1
    return width, height, data[start:start + width * height]


def render(decal_id, catalog=None, command=None):
    """Mask of a decal: (width, height, bytes row by row, top row first, 0 or 255)."""
    catalog = catalog or load()
    decal = catalog["decals"][decal_id]
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "decal.pgm"
        run(draw_args(decal, catalog["glyphs"]) + [f"PGM:{target}"], command)
        width, height, pixels = read_pgm(target.read_bytes())
    if (width, height) != tuple(decal["size"]):
        raise ImageMagickError(f"{decal_id}: ImageMagick wrote {width}x{height}, expected {decal['size']}")
    return width, height, bytes(255 if value >= 128 else 0 for value in pixels)


def mask_array(rendered):
    width, height, pixels = rendered
    return np.frombuffer(pixels, dtype=np.uint8).reshape(height, width)


def catalog_errors(catalog):
    errors = []
    glyphs = catalog.get("glyphs", {})
    for decal_id, decal in catalog.get("decals", {}).items():
        width, height = decal.get("size", (0, 0))
        if not (16 <= width <= 1024 and 16 <= height <= 1024):
            errors.append(f"{decal_id}: size out of 16..1024")
        for element in decal.get("elements", []):
            if "text" in element:
                missing = sorted(set(element["text"]) - set(glyphs))
                if missing:
                    errors.append(f"{decal_id}: glyphs missing {missing}")
                elif element["x"] * width + text_width(element["text"], element["height"] * height) > width:
                    errors.append(f"{decal_id}: text wider than the image")
    return errors


REGION_OUTSIDE = .02             # a region polygon may reach this share of its box over the box (sheet rule: 1 mm)
REGION_COVERAGE = (.7, 1.3)      # painted surface / polygon area of a region (QA, regions with REGION_MIN_TEXELS or more)
REGION_MIN_TEXELS = 40


def is_region(anchor):
    return anchor.get("kind") == "region"


def region_errors(index, anchor, parts=None):
    """Problems of one region anchor (concept_spec.decal_regions)."""
    where = f"region {index} ({anchor.get('region')})"
    errors = []
    if anchor.get("face") not in FACES:
        errors.append(f"{where}: face must be one of {sorted(FACES)}")
    if anchor.get("channel") not in CHANNELS:
        errors.append(f"{where}: unknown channel")
    polygon = anchor.get("polygon", [])
    if len(polygon) < 3:
        errors.append(f"{where}: polygon needs three corners")
    elif any(not -REGION_OUTSIDE <= value <= 1 + REGION_OUTSIDE for point in polygon for value in point):
        errors.append(f"{where}: polygon reaches over its part")
    if parts is not None and anchor.get("part") not in parts:
        errors.append(f"{where}: part {anchor.get('part')} not in the model")
    return errors


def anchor_errors(anchors, catalog, parts=None):
    """Problems of the DECALS anchors of one weapon (parts: its source part names, optional); region anchors (0.21) have
    their own rules."""
    errors = []
    for index, anchor in enumerate(anchors):
        if is_region(anchor):
            errors += region_errors(index, anchor, parts)
            continue
        where = f"decal {index} ({anchor.get('image')})"
        if anchor.get("image") not in catalog["decals"]:
            errors.append(f"{where}: unknown image")
        if anchor.get("face") not in FACES:
            errors.append(f"{where}: face must be one of {sorted(FACES)}")
        if anchor.get("channel") not in CHANNELS:
            errors.append(f"{where}: unknown channel")
        if anchor.get("rotation", 0) not in (0, 90, 180, 270):
            errors.append(f"{where}: rotation must be 0, 90, 180 or 270")
        rect = anchor.get("rect", ())
        if len(rect) != 4 or not (0 <= rect[0] < rect[2] <= 1 and 0 <= rect[1] < rect[3] <= 1):
            errors.append(f"{where}: rect must be (u0, v0, u1, v1) inside 0..1")
        if parts is not None and anchor.get("part") not in parts:
            errors.append(f"{where}: part {anchor.get('part')} not in the model")
    return errors


# --------------------------------------------------------------------------------------------- projection (numpy)
def texel_positions(triangle_raster, uv_triangles, corners):
    """Barycentric interpolation per painted texel: (ys, xs, triangle index, position N x 3) of a raster of triangle
    indices (row 0 = v near 0)."""
    resolution = triangle_raster.shape[0]
    ys, xs = np.nonzero(triangle_raster >= 0)
    tris = triangle_raster[ys, xs]
    point = np.stack([(xs + .5) / resolution, (ys + .5) / resolution], axis=1)
    a, b, c = uv_triangles[tris, 0], uv_triangles[tris, 1], uv_triangles[tris, 2]
    v0, v1, v2 = b - a, c - a, point - a
    d00 = (v0 * v0).sum(1)
    d01 = (v0 * v1).sum(1)
    d11 = (v1 * v1).sum(1)
    d20 = (v2 * v0).sum(1)
    d21 = (v2 * v1).sum(1)
    denominator = d00 * d11 - d01 * d01
    safe = np.where(np.abs(denominator) > 1e-30, denominator, 1.0)
    wb = (d11 * d20 - d01 * d21) / safe
    wc = (d00 * d21 - d01 * d20) / safe
    wa = 1 - wb - wc
    positions = wa[:, None] * corners[tris, 0] + wb[:, None] * corners[tris, 1] + wc[:, None] * corners[tris, 2]
    return ys, xs, tris, positions


def face_normals(corners):
    normal = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    length = np.linalg.norm(normal, axis=1)
    return normal / np.where(length > 0, length, 1.0)[:, None]


def rotate_local(a, b, rotation):
    """Local rect coordinates (0..1, a right, b up) turned by the decal rotation (counter-clockwise, degrees)."""
    if rotation == 90:
        return b, 1 - a
    if rotation == 180:
        return 1 - a, 1 - b
    if rotation == 270:
        return 1 - b, a
    return a, b


def project(anchor, mask, texels, triangle_parts, normals, part_index, part_box):
    """Texel selection of one decal: boolean over ``texels`` (ys, xs, tris, positions of texel_positions).
    ``part_index``: index of the anchor's part; ``part_box``: (min xyz, max xyz) of that part in the tool frame."""
    ys, xs, tris, positions = texels
    axis, sign, u_axis, u_sign, v_axis, v_sign = FACES[anchor["face"]]
    low, high = np.asarray(part_box[0], dtype=np.float64), np.asarray(part_box[1], dtype=np.float64)
    span = np.where(high - low > 1e-9, high - low, 1.0)
    own = (triangle_parts[tris] == part_index) & (normals[tris, axis] * sign >= FACING_MIN)
    s = (positions[:, u_axis] - low[u_axis]) / span[u_axis]
    t = (positions[:, v_axis] - low[v_axis]) / span[v_axis]
    s = s if u_sign > 0 else 1 - s
    t = t if v_sign > 0 else 1 - t
    u0, v0, u1, v1 = anchor["rect"]
    a = (s - u0) / (u1 - u0)
    b = (t - v0) / (v1 - v0)
    inside = own & (a >= 0) & (a < 1) & (b >= 0) & (b < 1)
    a, b = rotate_local(a, b, anchor.get("rotation", 0))
    height, width = mask.shape
    column = np.clip((a * width).astype(np.int64), 0, width - 1)
    row = np.clip(((1 - b) * height).astype(np.int64), 0, height - 1)
    hit = np.zeros(len(ys), dtype=bool)
    hit[inside] = mask[row[inside], column[inside]] >= 128
    return hit


def box_fractions(points, face, part_box):
    """(s, t) of points (N x 3) as fractions of the box seen on ``face`` (s to the right, t up, from outside)."""
    _, _, u_axis, u_sign, v_axis, v_sign = FACES[face]
    low, high = np.asarray(part_box[0], dtype=np.float64), np.asarray(part_box[1], dtype=np.float64)
    span = np.where(high - low > 1e-9, high - low, 1.0)
    s = (points[:, u_axis] - low[u_axis]) / span[u_axis]
    t = (points[:, v_axis] - low[v_axis]) / span[v_axis]
    return (s if u_sign > 0 else 1 - s), (t if v_sign > 0 else 1 - t)


def inside_polygon(s, t, polygon):
    """Even-odd test of the points (s, t) against ``polygon`` [(s, t), ...] (fixed edge order: same result everywhere)."""
    inside = np.zeros(len(s), dtype=bool)
    corners = [(float(a), float(b)) for a, b in polygon]
    for (s0, t0), (s1, t1) in zip(corners, corners[1:] + corners[:1]):
        crosses = (t0 > t) != (t1 > t)
        with np.errstate(divide="ignore", invalid="ignore"):
            at = s0 + (t - t0) * (s1 - s0) / np.where(t1 != t0, t1 - t0, 1.0)
        inside ^= crosses & (s < at)
    return inside


def project_region(anchor, texels, triangle_parts, normals, part_index, part_box, to_life=None):
    """Texel selection of one region anchor: texels of its part whose face looks along the face axis (FACING_MIN) and whose
    position lies inside the polygon. ``to_life(points N x 3)``: the deformed model mapped back to the design (robot variant;
    monotonic per axis, so the box maps to the box), None for an undeformed or uniformly scaled model."""
    ys, xs, tris, positions = texels
    axis, sign = FACES[anchor["face"]][:2]
    own = (triangle_parts[tris] == part_index) & (normals[tris, axis] * sign >= FACING_MIN)
    box = np.asarray(part_box, dtype=np.float64)
    if to_life is not None:
        positions, box = to_life(positions), to_life(box)
    s, t = box_fractions(positions, anchor["face"], box)
    hit = np.zeros(len(ys), dtype=bool)
    hit[own] = inside_polygon(s[own], t[own], anchor["polygon"])
    return hit


def polygon_area(polygon):
    corners = np.asarray(polygon, dtype=np.float64)
    return abs(float(np.dot(corners[:, 0], np.roll(corners[:, 1], -1)) - np.dot(corners[:, 1], np.roll(corners[:, 0], -1)))) / 2


def region_coverage(anchor, hit, texels, uv_triangles, corners, part_box, resolution, to_life=None):
    """Painted surface of a region (sum over its texels of the texel's area on the model, projected onto the face plane)
    against the polygon's area, both in the design's metres (``to_life``); 1.0 = the region lands exactly on its part."""
    tris = texels[2]
    axis, _, u_axis, _, v_axis, _ = FACES[anchor["face"]]
    box = np.asarray(part_box, dtype=np.float64)
    life = corners if to_life is None else to_life(corners.reshape(-1, 3)).reshape(corners.shape)
    if to_life is not None:
        box = to_life(box)
    used = tris[hit]
    if not len(used):
        return 0.0
    a, b, c = life[used, 0], life[used, 1], life[used, 2]
    normal = np.cross(b - a, c - a)
    projected = np.abs(normal[:, axis]) / 2                                    # triangle area projected on the face plane
    uv = uv_triangles[used]
    uv_area = np.abs((uv[:, 1, 0] - uv[:, 0, 0]) * (uv[:, 2, 1] - uv[:, 0, 1])
                     - (uv[:, 2, 0] - uv[:, 0, 0]) * (uv[:, 1, 1] - uv[:, 0, 1])) / 2 * resolution * resolution
    painted = float(np.sum(projected / np.where(uv_area > 1e-12, uv_area, np.inf)))
    span = box[1] - box[0]
    expected = polygon_area(anchor["polygon"]) * span[u_axis] * span[v_axis]
    return painted / expected if expected > 0 else 0.0


def refit_rect(anchor, box, to_life, to_model, scale, margin=.02, shift=(0.0, 0.0)):
    """The anchor on a deformed part (Toolgen 0.14 robot variant): ``box`` is the deformed part's box, ``to_life(axis, value)``
    and ``to_model(axis, value)`` map one coordinate between the life-size design and the deformed model, ``scale`` is the
    decal's uniform growth. The decal keeps its aspect in millimetres and its centre on the same spot of the part; where the
    part got too short for it (a squashed stock), it first moves inward and only then shrinks, so it stays inside the box
    with ``margin`` (share of the box) on every side. ``shift`` (u, v as shares of the box, seen from outside) moves it off a
    UV seam. Returns the new anchor."""
    _, _, u_axis, u_sign, v_axis, v_sign = FACES[anchor["face"]]
    low, high = [float(v) for v in box[0]], [float(v) for v in box[1]]
    u0, v0, u1, v1 = anchor["rect"]
    sides = []
    for axis, sign, f0, f1, move in ((u_axis, u_sign, u0, u1, shift[0]), (v_axis, v_sign, v0, v1, shift[1])):
        life_low, life_high = to_life(axis, low[axis]), to_life(axis, high[axis])
        ends = sorted(life_low + (f if sign > 0 else 1 - f) * (life_high - life_low) for f in (f0, f1))
        centre = to_model(axis, (ends[0] + ends[1]) / 2) + sign * move * (high[axis] - low[axis])
        sides.append((axis, sign, centre, (ends[1] - ends[0]) / 2 * scale))
    factor = 1.0
    for axis, _, _, half in sides:
        room = (high[axis] - low[axis]) * (.5 - margin)
        factor = min(factor, room / half) if half > 0 else factor
    rect = []
    for axis, sign, centre, half in sides:
        span, half = high[axis] - low[axis], half * factor
        centre = min(max(centre, low[axis] + margin * span + half), high[axis] - margin * span - half)
        a, b = (centre - half - low[axis]) / span, (centre + half - low[axis]) / span
        rect.append((a, b) if sign > 0 else (1 - b, 1 - a))
    return dict(anchor, rect=(rect[0][0], rect[1][0], rect[0][1], rect[1][1]))


def rect_aspect_error(anchor, part_box, mask_shape):
    """Relative difference of the rect's aspect (mm on the part) and the image's aspect (after the rotation)."""
    _, _, u_axis, _, v_axis, _ = FACES[anchor["face"]]
    low, high = part_box
    u0, v0, u1, v1 = anchor["rect"]
    width_mm = (u1 - u0) * (high[u_axis] - low[u_axis])
    height_mm = (v1 - v0) * (high[v_axis] - low[v_axis])
    rows, columns = mask_shape
    image = columns / rows if anchor.get("rotation", 0) in (0, 180) else rows / columns
    if height_mm <= 0 or width_mm <= 0:
        return float("inf")
    return abs((width_mm / height_mm) / image - 1)
