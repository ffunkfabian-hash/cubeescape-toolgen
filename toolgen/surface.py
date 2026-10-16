"""Surface data of game contract 4 (Cube Escape 0.71 "Maskwork"): UV1, the channel weight maps, fields and normals.

* ``add_uv1`` (game_export.py, contract 4, before the merge): a second UV map ``UV1`` per tool part - smart projection,
  islands scaled to the same texel density, packed without rotation into one atlas per model, 8 px gaps at 1024.
  Faces of the first-person hands and arms (source materials ``FPS_*``) get no island: their UV1 is the point (0, 0) in a
  reserved band at the left and bottom edge that no island and no dilation reaches (weights 0 there, neutral fields).
  Collapse decimation and LOD1 keep the map (decimated meshes are checked like LOD0, see ``uv1_report``).
* ``surface_bake.py`` (stage ``surface_bake``) bakes W0/W1 (one-hot channel weights per material slot), Fields (AO, edge,
  up, height) and Normal (tangent space on UV1, OpenGL) from the LOD0 renderers and writes the ``surface`` block.

The pure helpers (channel table, PNG, rasterisation and the map checks) import without Blender; the raster helpers need
numpy (Blender's Python has it), the PNG reader does not.
"""
import hashlib
import json
import math
import struct
import zlib

try:
    import numpy as np
except ImportError:  # system Python of the unit tests: only the pure helpers
    np = None

SURFACE_CONTRACT = 4             # first game contract with UV1 and the surface block
SURFACE_VERSION = 1              # version of the surface block itself
UV1_NAME = "UV1"
UV0_NAME = "UVMap"
ANGLE_LIMIT_DEGREES = 66.0       # smart projection: a new island where faces bend more than this
PACK_MARGIN = .008               # pack_islands FRACTION margin: gaps between islands and to the border (8 px at 1024)
RESERVED_LOW = 16 / 1024         # band at u < 16/1024 and v < 16/1024 kept free for the unpainted point (0, 0)
CHECK_RESOLUTION = 1024          # the margin rule is stated at 1024
MARGIN_PX = 4                    # contract: at least 4 px between islands at 1024
OVERLAP_RESOLUTION = 2048        # overlap raster
MAP_RESOLUTION = {"world": 512, "viewmodel": 1024}
AO_SAMPLES = {"world": 16, "viewmodel": 32}
EDGE_SAMPLES = 16               # rays of the bevel and local AO nodes per shading sample
DETAIL_SAMPLES = 4              # Cycles samples of the EMIT and NORMAL bakes
AO_DISTANCE_M = .08
BEVEL_RADIUS_M = .004
EDGE_GAIN = 12.0                 # edge = gain x (1 - bevel normal . shading normal), times the convexity factor
EDGE_CONVEX = (.35, .7)          # local AO below .35: concave crease (edge 0); above .7: open (convex edge counts fully)
DILATION_PX = 8                  # every island continues 8 px outward (nearest texel, fixed neighbour order on ties)
MAX_SET_BYTES = 2_500_000        # four PNGs of one model
AO_MEAN_RANGE = (.3, .95)
EDGE_SHARE_RANGE = (.02, .25)
EDGE_THRESHOLD = .5
WEIGHT_SUM_MIN = 250
UNPAINTED_PREFIX = "FPS_"        # source materials of the first-person hands and arms
CHANNELS = ("Primary", "Secondary", "Accent", "Metal", "Energy", "Emission", "Detail")   # Cube Escape ColorChannels.cs
# Cube Escape 0.71 PAINT recipe, _EquipParams.x = 1: W0 = _RegionMask0, W1 = _RegionMask1.
REGIONS = {"W0.r": "Primary", "W0.g": "Secondary", "W0.b": "Accent", "W0.a": "Emission",
           "W1.r": "Metal", "W1.g": "Detail", "W1.b": "Energy"}
TARGETS = {channel: (key.split(".")[0], "rgba".index(key.split(".")[1])) for key, channel in REGIONS.items()}
MAP_KINDS = ("W0", "W1", "Fields", "Normal")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# --------------------------------------------------------------------------------------------- channel table
def channel_of(slot, palette):
    """Channel of a game material slot: MT_<Channel> by its name, palette names (M_*) by data/game_palette.json
    ``channel_map``; None for a slot without entry (it lies in no mask)."""
    if slot.startswith("MT_") and slot[3:] in CHANNELS:
        return slot[3:]
    return palette.get("channel_map", {}).get("materials", {}).get(slot)


def channel_map_errors(palette):
    """Every palette material and every equipment slot has exactly one channel of CHANNELS."""
    table = palette.get("channel_map")
    if table is None:
        return ["channel_map missing in data/game_palette.json (contract 4)"]
    errors = []
    materials = table.get("materials", {})
    for name in palette["materials"]:
        if materials.get(name) not in CHANNELS:
            errors.append(f"{name}: channel_map needs a channel of {', '.join(CHANNELS)}")
    for name in materials:
        if name not in palette["materials"]:
            errors.append(f"{name}: channel_map names an unknown palette material")
    for name in palette.get("channels", {}).get("slots", {}):
        if channel_of(name, palette) != name[3:]:
            errors.append(f"{name}: equipment slots carry the channel of their name")
    return errors


def model_channel_map(palette, slots):
    """{slot: channel} for the slots of one model (sorted); slots without a channel are left out."""
    return {slot: channel_of(slot, palette) for slot in sorted(slots) if channel_of(slot, palette)}


def map_names(model):
    return {kind.lower(): f"{model}_{kind}.png" for kind in MAP_KINDS}


# --------------------------------------------------------------------------------------------- PNG
def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def png_bytes(filtered, width, height, channels=4):
    """PNG of already filtered scanlines (one filter byte per row): IHDR, IDAT, IEND only - no gamma, sRGB or ICC chunk,
    so readers take the values as they are (linear data). zlib level 9 is deterministic."""
    color = {1: 0, 2: 4, 3: 2, 4: 6}[channels]
    header = struct.pack(">IIBBBBB", width, height, 8, color, 0, 0, 0)
    return PNG_SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(filtered, 9)) + _chunk(b"IEND", b"")


def png_encode(pixels):
    """PNG of a (height, width, channels) uint8 array, row 0 = top of the image. Per row the smallest of the filters
    None, Sub and Up (sum of absolute signed bytes), which the reader undoes without a per-pixel loop."""
    height, width, channels = pixels.shape
    rows = pixels.reshape(height, width * channels).astype(np.int16)
    sub = rows.copy()
    sub[:, channels:] -= rows[:, :-channels]
    up = rows.copy()
    up[1:] -= rows[:-1]
    candidates = np.stack([rows, sub, up]) & 0xFF
    signed = np.where(candidates > 127, 256 - candidates, candidates).sum(axis=2)
    choice = np.argmin(signed, axis=0)
    picked = candidates[choice, np.arange(height)].astype(np.uint8)
    filtered = np.concatenate([choice.astype(np.uint8)[:, None], picked], axis=1)
    return png_bytes(filtered.tobytes(), width, height, channels)


def png_info(data):
    """Header and chunk names of a PNG (no decoding): {width, height, bit_depth, color_type, chunks}."""
    if data[:8] != PNG_SIGNATURE:
        raise ValueError("not a PNG")
    position, chunks, header = 8, [], None
    while position < len(data):
        length = struct.unpack(">I", data[position:position + 4])[0]
        kind = data[position + 4:position + 8].decode("ascii")
        if kind == "IHDR":
            header = struct.unpack(">IIBBBBB", data[position + 8:position + 21])
        chunks.append(kind)
        position += 12 + length
    return {"width": header[0], "height": header[1], "bit_depth": header[2], "color_type": header[3], "chunks": chunks}


def png_decode(data):
    """(width, height, channels, rows) of an 8-bit PNG written by png_bytes; rows top to bottom as bytearrays.
    Pure Python with every filter type: for tests and small checks (use png_array for full maps)."""
    info = png_info(data)
    channels = {0: 1, 4: 2, 2: 3, 6: 4}[info["color_type"]]
    width, height = info["width"], info["height"]
    position, compressed = 8, b""
    while position < len(data):
        length = struct.unpack(">I", data[position:position + 4])[0]
        if data[position + 4:position + 8] == b"IDAT":
            compressed += data[position + 8:position + 8 + length]
        position += 12 + length
    raw = zlib.decompress(compressed)
    stride, rows, previous = width * channels, [], bytearray(width * channels)
    for y in range(height):
        kind, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):
            left = line[x - channels] if x >= channels else 0
            above, corner = previous[x], previous[x - channels] if x >= channels else 0
            if kind == 1:
                line[x] = (line[x] + left) & 0xFF
            elif kind == 2:
                line[x] = (line[x] + above) & 0xFF
            elif kind == 3:
                line[x] = (line[x] + (left + above) // 2) & 0xFF
            elif kind == 4:
                p = left + above - corner
                pa, pb, pc = abs(p - left), abs(p - above), abs(p - corner)
                line[x] = (line[x] + (left if pa <= pb and pa <= pc else above if pb <= pc else corner)) & 0xFF
        rows.append(line)
        previous = line
    return width, height, channels, rows


def png_array(data):
    """(height, width, channels) uint8 array of a PNG written by png_encode (filters None/Sub/Up), row 0 = top."""
    info = png_info(data)
    channels = {0: 1, 4: 2, 2: 3, 6: 4}[info["color_type"]]
    width, height = info["width"], info["height"]
    position, compressed = 8, b""
    while position < len(data):
        length = struct.unpack(">I", data[position:position + 4])[0]
        if data[position + 4:position + 8] == b"IDAT":
            compressed += data[position + 8:position + 8 + length]
        position += 12 + length
    raw = np.frombuffer(zlib.decompress(compressed), dtype=np.uint8).reshape(height, width * channels + 1)
    kinds, rows = raw[:, 0], raw[:, 1:].astype(np.int64)
    if not set(np.unique(kinds).tolist()) <= {0, 1, 2}:
        raise ValueError("png_array reads the filters None, Sub and Up only")
    for y in range(height):
        if kinds[y] == 1:
            line = rows[y].reshape(width, channels)
            rows[y] = (np.cumsum(line, axis=0) & 0xFF).reshape(-1)
        elif kinds[y] == 2 and y:
            rows[y] = (rows[y] + rows[y - 1]) & 0xFF
    return rows.astype(np.uint8).reshape(height, width, channels)


# --------------------------------------------------------------------------------------------- raster (numpy)
def _edges(triangle):
    a, b, c = triangle
    area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return a, b, c, area


def rasterize(triangles, labels, resolution, strict=False, image=None, counts=None):
    """Texel-centre raster of UV triangles (N x 3 x 2, 0..1, v up: row 0 = v near 0).

    Writes labels[i] into ``image`` (int32, -1 = empty) where the first triangle covers a texel centre (inclusive edges,
    earlier triangles win: deterministic). With ``counts`` it also counts the triangles strictly containing each centre
    (shared edges never count twice, so counts > 1 is real overlap). Degenerate triangles are skipped."""
    if image is None:
        image = np.full((resolution, resolution), -1, dtype=np.int32)
    epsilon = 1e-12
    for triangle, label in zip(triangles, labels):
        a, b, c, area = _edges(triangle)
        if abs(area) < 1e-14:
            continue
        if area < 0:
            b, c = c, b
            area = -area
        low = np.floor(np.minimum(np.minimum(a, b), c) * resolution - .5).astype(int)
        high = np.ceil(np.maximum(np.maximum(a, b), c) * resolution - .5).astype(int)
        x0, y0 = max(low[0], 0), max(low[1], 0)
        x1, y1 = min(high[0], resolution - 1), min(high[1], resolution - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs = (np.arange(x0, x1 + 1) + .5) / resolution
        ys = (np.arange(y0, y1 + 1) + .5) / resolution
        px, py = np.meshgrid(xs, ys)
        w0 = (b[0] - a[0]) * (py - a[1]) - (b[1] - a[1]) * (px - a[0])
        w1 = (c[0] - b[0]) * (py - b[1]) - (c[1] - b[1]) * (px - b[0])
        w2 = (a[0] - c[0]) * (py - c[1]) - (a[1] - c[1]) * (px - c[0])
        tolerance = epsilon * area
        inside = (w0 >= -tolerance) & (w1 >= -tolerance) & (w2 >= -tolerance)
        window = image[y0:y1 + 1, x0:x1 + 1]
        free = inside & (window < 0)
        window[free] = label
        if counts is not None:
            core = (w0 > tolerance) & (w1 > tolerance) & (w2 > tolerance)
            counts[y0:y1 + 1, x0:x1 + 1] += core
    return image


# Neighbour order of the dilation (fixed, so ties between islands resolve the same way on every run).
NEIGHBOURS = ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (-1, 1), (1, -1), (1, 1))


def shifted(image, dy, dx, fill=-1):
    """image moved by (dy, dx): result[y, x] = image[y - dy, x - dx], outside = fill."""
    result = np.full_like(image, fill)
    h, w = image.shape[:2]
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    result[yd, xd] = image[ys, xs]
    return result


def dilate(labels, steps):
    """Each step fills empty texels (-1) from the first labelled neighbour in NEIGHBOURS order (chessboard distance)."""
    current = labels.copy()
    for _ in range(steps):
        source = current
        current = source.copy()
        for dy, dx in NEIGHBOURS:
            moved = shifted(source, dy, dx)
            fill = (current < 0) & (moved >= 0)
            current[fill] = moved[fill]
    return current


def min_gap_px(islands, limit):
    """Smallest distance in texels (Euclidean, between texel centres) between two different islands of an island-id
    raster, searched up to ``limit``; returns ``limit`` when no pair is closer."""
    best = float(limit)
    for dy in range(0, limit + 1):
        for dx in range(-limit, limit + 1):
            if dy == 0 and dx <= 0:
                continue
            distance = math.hypot(dx, dy)
            if distance >= best:
                continue
            moved = shifted(islands, dy, dx)
            if np.any((islands >= 0) & (moved >= 0) & (moved != islands)):
                best = distance
    return best


def weight_maps(channel_raster, steps=DILATION_PX):
    """W0, W1 (resolution x resolution x 4 uint8, row 0 = v near 0) of a channel-index raster (index into CHANNELS,
    -1 = no paint): one-hot 255 inside the islands and the dilated border, 0 elsewhere."""
    filled = dilate(channel_raster, steps)
    resolution = channel_raster.shape[0]
    maps = {"W0": np.zeros((resolution, resolution, 4), dtype=np.uint8),
            "W1": np.zeros((resolution, resolution, 4), dtype=np.uint8)}
    for index, channel in enumerate(CHANNELS):
        kind, component = TARGETS[channel]
        maps[kind][..., component][filled == index] = 255
    return maps, filled


def map_checks(maps, channel_raster, expected_channels, set_bytes):
    """Acceptance values of one map set: weight sums inside the islands, nothing beyond the dilation, every channel of
    the channel map painted, AO mean and edge share inside the islands, set size."""
    w0, w1 = maps["W0"].astype(np.int32), maps["W1"].astype(np.int32)
    total = w0.sum(axis=2) + w1[..., :3].sum(axis=2)
    inside = channel_raster >= 0
    reach = dilate(channel_raster, DILATION_PX) >= 0
    painted = {channel: int(np.count_nonzero(maps[TARGETS[channel][0]][..., TARGETS[channel][1]]))
               for channel in CHANNELS}
    fields = maps["Fields"].astype(np.float64) / 255
    ao_mean = float(fields[..., 0][inside].mean()) if inside.any() else 0.0
    edge_share = float((fields[..., 1][inside] > EDGE_THRESHOLD).mean()) if inside.any() else 0.0
    return {
        "texels_inside": int(inside.sum()),
        "min_weight_sum_inside": int(total[inside].min()) if inside.any() else 0,
        "one_hot_inside": bool(inside.any() and np.all(np.count_nonzero(np.concatenate([w0, w1[..., :3]], axis=2)[inside], axis=1) == 1)),
        "weights_beyond_dilation": int(np.count_nonzero(total[~reach])),
        "w1_alpha_nonzero": int(np.count_nonzero(maps["W1"][..., 3])),
        "texels_per_channel": painted,
        "missing_channels": sorted(channel for channel in expected_channels if painted[channel] == 0),
        "ao_mean": round(ao_mean, 4), "edge_share": round(edge_share, 4), "set_bytes": int(set_bytes),
    }


def map_errors(values):
    errors = []
    if values["texels_inside"] == 0:
        errors.append("no painted texel")
    if values["min_weight_sum_inside"] < WEIGHT_SUM_MIN or not values["one_hot_inside"]:
        errors.append("weights inside the islands are not one-hot 255")
    if values["weights_beyond_dilation"] or values["w1_alpha_nonzero"]:
        errors.append("weights outside the dilation border or in W1.a")
    if values["missing_channels"]:
        errors.append(f"channels without texels: {values['missing_channels']}")
    if not AO_MEAN_RANGE[0] <= values["ao_mean"] <= AO_MEAN_RANGE[1]:
        errors.append(f"AO mean {values['ao_mean']} outside {AO_MEAN_RANGE}")
    if not EDGE_SHARE_RANGE[0] <= values["edge_share"] <= EDGE_SHARE_RANGE[1]:
        errors.append(f"edge share {values['edge_share']} outside {EDGE_SHARE_RANGE}")
    if values["set_bytes"] > MAX_SET_BYTES:
        errors.append(f"map set {values['set_bytes']} bytes > {MAX_SET_BYTES}")
    return errors


def island_ids(faces, uvs, precision=6):
    """Island index per face: faces sharing a vertex with the same UV (rounded) belong together. faces: vertex index
    tuples, uvs: per face the UV tuples of its corners."""
    parent = list(range(len(faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner = {}
    for index, (vertices, corners) in enumerate(zip(faces, uvs)):
        for vertex, uv in zip(vertices, corners):
            key = (vertex, round(uv[0], precision), round(uv[1], precision))
            if key in owner:
                a, b = find(owner[key]), find(index)
                if a != b:
                    parent[max(a, b)] = min(a, b)
            else:
                owner[key] = index
    roots, result = {}, []
    for index in range(len(faces)):
        result.append(roots.setdefault(find(index), len(roots)))
    return result


def layout_report(triangles, islands, unpainted):
    """UV1 layout values of a set of triangles (N x 3 x 2) with island ids; unpainted triangles (hands) only have to sit
    at (0, 0)."""
    painted = ~unpainted
    tris = triangles[painted]
    in_range = bool(np.all((triangles >= 0) & (triangles <= 1)))
    counts = np.zeros((OVERLAP_RESOLUTION, OVERLAP_RESOLUTION), dtype=np.int16)
    rasterize(tris, np.zeros(len(tris), dtype=np.int32), OVERLAP_RESOLUTION, counts=counts)
    raster = rasterize(tris, np.asarray(islands)[painted].astype(np.int32), CHECK_RESOLUTION)
    gap = min_gap_px(raster, 8)
    reserved = int(RESERVED_LOW * CHECK_RESOLUTION)
    corner_clear = bool(np.all(dilate(raster, DILATION_PX)[:reserved, :reserved] < 0))
    return {"triangles": int(len(triangles)), "unpainted_triangles": int(unpainted.sum()),
            "unpainted_at_origin": bool(np.all(triangles[unpainted] == 0)),
            "islands": int(len(set(np.asarray(islands)[painted].tolist()))), "in_range": in_range,
            "overlap_texels": int(np.count_nonzero(counts > 1)), "overlap_resolution": OVERLAP_RESOLUTION,
            "min_gap_px": round(gap, 3), "margin_px": MARGIN_PX, "check_resolution": CHECK_RESOLUTION,
            "reserved_corner_clear": corner_clear,
            "used_share": round(float(np.count_nonzero(raster >= 0)) / CHECK_RESOLUTION ** 2, 4)}


def layout_errors(report, overlap_allowed=False):
    errors = []
    if not report["in_range"]:
        errors.append("UV1 outside 0..1")
    if report["overlap_texels"] and not overlap_allowed:
        errors.append(f"UV1 overlap: {report['overlap_texels']} texels at {report['overlap_resolution']}")
    if report["min_gap_px"] < MARGIN_PX and not overlap_allowed:
        errors.append(f"UV1 gap {report['min_gap_px']} px < {MARGIN_PX} px at {CHECK_RESOLUTION}")
    if not report["unpainted_at_origin"] or not report["reserved_corner_clear"]:
        errors.append("unpainted faces not at (0, 0) or the reserved corner is not free")
    return errors


def digest(*parts):
    value = hashlib.sha256()
    for part in parts:
        value.update(part if isinstance(part, bytes) else json.dumps(part, sort_keys=True).encode())
    return value.hexdigest()


# --------------------------------------------------------------------------------------------- Blender: UV1
def _uv_array(mesh, name):
    values = np.empty(len(mesh.loops) * 2, dtype=np.float32)
    mesh.uv_layers[name].data.foreach_get("uv", values)
    return values.reshape(-1, 2)


def _face_angles(mesh):
    """Direction (radians) of each face's first UV1 edge, NaN for degenerate edges."""
    uv = _uv_array(mesh, UV1_NAME)
    starts = np.empty(len(mesh.polygons), dtype=np.int64)
    mesh.polygons.foreach_get("loop_start", starts)
    delta = uv[starts + 1] - uv[starts]
    length = np.hypot(delta[:, 0], delta[:, 1])
    return np.where(length > 1e-7, np.arctan2(delta[:, 1], delta[:, 0]), np.nan)


def is_unpainted(obj):
    names = [material.name for material in obj.data.materials if material]
    unpainted = [name.startswith(UNPAINTED_PREFIX) for name in names]
    if any(unpainted) and not all(unpainted):
        raise RuntimeError(f"{obj.name}: mixes first-person hand materials with tool materials")
    return bool(names) and all(unpainted)


def new_uv1(objects):
    """UV1 (zeros, index 1) on every mesh; UVMap stays the render map. Shared mesh data is made single-user first."""
    for obj in objects:
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        mesh = obj.data
        if UV1_NAME in mesh.uv_layers:
            mesh.uv_layers.remove(mesh.uv_layers[UV1_NAME])
        if len(mesh.uv_layers) != 1:
            raise RuntimeError(f"{obj.name}: expected exactly one UV map before UV1, found {len(mesh.uv_layers)}")
        layer = mesh.uv_layers.new(name=UV1_NAME, do_init=False)
        layer.data.foreach_set("uv", np.zeros(len(mesh.loops) * 2, dtype=np.float32))
        mesh.uv_layers[0].active_render = True
        mesh.uv_layers.active = layer


def add_uv1(objects):
    """UV1 for ``objects`` (one model's meshes): one atlas, islands without rotation; hand meshes stay at (0, 0).
    Returns {"islands_rotated_max_degrees", "painted_objects", "unpainted_objects", "sha256"}."""
    import bpy
    objects = sorted(objects, key=lambda obj: obj.name)
    new_uv1(objects)
    painted = [obj for obj in objects if not is_unpainted(obj)]
    rotation = 0.0
    if painted:
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)
        for obj in painted:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = painted[0]
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="FACE")
        bpy.ops.mesh.reveal()
        bpy.ops.mesh.select_all(action="SELECT")
        if "FINISHED" not in bpy.ops.uv.smart_project(angle_limit=math.radians(ANGLE_LIMIT_DEGREES), island_margin=0.0,
                                                       area_weight=0.0, correct_aspect=True, scale_to_bounds=False):
            raise RuntimeError("UV1 smart projection failed")
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.average_islands_scale()
        bpy.ops.object.mode_set(mode="OBJECT")
        before = {obj.name: _face_angles(obj.data) for obj in painted}
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.select_all(action="SELECT")
        if "FINISHED" not in bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=False, scale=True,
                                                      merge_overlap=False, margin_method="FRACTION", margin=PACK_MARGIN,
                                                      pin=False, shape_method="CONCAVE"):
            raise RuntimeError("UV1 packing failed")
        bpy.ops.object.mode_set(mode="OBJECT")
        for obj in painted:
            after = _face_angles(obj.data)
            change = np.abs((after - before[obj.name] + math.pi) % (2 * math.pi) - math.pi)
            if np.any(np.isfinite(change)):
                rotation = max(rotation, float(np.degrees(np.nanmax(change))))
            uv = _uv_array(obj.data, UV1_NAME)
            uv = RESERVED_LOW + uv * (1 - RESERVED_LOW)
            obj.data.uv_layers[UV1_NAME].data.foreach_set("uv", uv.astype(np.float32).reshape(-1))
        for obj in painted:
            obj.select_set(False)
    return {"islands_rotated_max_degrees": round(rotation, 6), "painted_objects": len(painted),
            "unpainted_objects": len(objects) - len(painted), "sha256": uv1_digest(objects)}


def uv1_digest(objects):
    """Hash over name, loop count and UV1 of every mesh (sorted by name)."""
    value = hashlib.sha256()
    for obj in sorted(objects, key=lambda obj: obj.name):
        value.update(obj.name.encode() + struct.pack("<I", len(obj.data.loops)))
        value.update(_uv_array(obj.data, UV1_NAME).tobytes())
    return value.hexdigest()


def uv1_signature(obj):
    """What must agree for a UV1 transfer: loop count and the loop count of every face."""
    totals = np.empty(len(obj.data.polygons), dtype=np.int32)
    obj.data.polygons.foreach_get("loop_total", totals)
    return len(obj.data.loops), hashlib.sha256(totals.tobytes()).hexdigest()


def capture_uv1(objects):
    """{name: (signature, UV1 array)} of painted meshes, for transfer_uv1."""
    return {obj.name: (uv1_signature(obj), _uv_array(obj.data, UV1_NAME).copy()) for obj in objects
            if not is_unpainted(obj)}


def transfer_uv1(objects, captured):
    """UV1 of the world model's parts on the first-person model: every painted mesh must have a twin (same name, same
    face structure). Returns the missing names; on success UV1 equals the world model's."""
    painted = [obj for obj in objects if not is_unpainted(obj)]
    missing = sorted(obj.name for obj in painted if obj.name not in captured or captured[obj.name][0] != uv1_signature(obj))
    if missing:
        return missing
    new_uv1(objects)
    for obj in painted:
        obj.data.uv_layers[UV1_NAME].data.foreach_set("uv", captured[obj.name][1].reshape(-1))
    return []


def mesh_triangles(mesh, layer=UV1_NAME):
    """(UV triangles N x 3 x 2 float64, face index per triangle, loop triangles' vertex indices) of a mesh."""
    mesh.calc_loop_triangles()
    count = len(mesh.loop_triangles)
    loops = np.empty(count * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("loops", loops)
    faces = np.empty(count, dtype=np.int64)
    mesh.loop_triangles.foreach_get("polygon_index", faces)
    uv = _uv_array(mesh, layer).astype(np.float64)
    vertex = np.empty(len(mesh.loops), dtype=np.int64)
    mesh.loops.foreach_get("vertex_index", vertex)
    return uv[loops].reshape(count, 3, 2), faces, vertex[loops].reshape(count, 3)


def signed_areas(triangles):
    return ((triangles[:, 1, 0] - triangles[:, 0, 0]) * (triangles[:, 2, 1] - triangles[:, 0, 1])
            - (triangles[:, 1, 1] - triangles[:, 0, 1]) * (triangles[:, 2, 0] - triangles[:, 0, 0]))


def clip_area(subject, clip):
    """Area of the intersection of two counter-clockwise triangles (Sutherland-Hodgman)."""
    polygon = [tuple(point) for point in subject]
    for i in range(3):
        if not polygon:
            return 0.0
        (ax, ay), (bx, by) = clip[i], clip[(i + 1) % 3]
        inside = [(bx - ax) * (py - ay) - (by - ay) * (px - ax) for px, py in polygon]
        result = []
        for j, point in enumerate(polygon):
            following, side, side_next = polygon[(j + 1) % len(polygon)], inside[j], inside[(j + 1) % len(polygon)]
            if side >= 0:
                result.append(point)
            if (side >= 0) != (side_next >= 0):
                share = side / (side - side_next)
                result.append((point[0] + share * (following[0] - point[0]), point[1] + share * (following[1] - point[1])))
        polygon = result
    if len(polygon) < 3:
        return 0.0
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1]))) / 2


def _ccw(triangle):
    a, b, c = triangle
    return (a, b, c) if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) >= 0 else (a, c, b)


def untangle(triangles, vertices, iterations=60):
    """Folds a collapse decimation leaves in UV1: triangles whose UV winding is against their island's. Each round tries,
    for every UV corner of a folded triangle (shared by vertex and UV inside the island), the mean of its UV neighbours,
    each neighbour and the midpoints towards them, and keeps the first position with the fewest folds around it (fewer
    than now). Moving onto a neighbour leaves a zero-area triangle (no texels), never an overlap. Fixed order, so the
    result is deterministic. Returns (new triangles, folds before, folds after)."""
    triangles = triangles.copy()
    keys, corner_ids = {}, np.empty(vertices.shape, dtype=np.int64)
    for t in range(len(triangles)):
        for c in range(3):
            key = (int(vertices[t, c]), round(float(triangles[t, c, 0]), 6), round(float(triangles[t, c, 1]), 6))
            corner_ids[t, c] = keys.setdefault(key, len(keys))
    painted = ~np.all(triangles == 0, axis=(1, 2))
    islands = np.asarray(island_ids([tuple(v) for v in vertices.tolist()], [tuple(map(tuple, t)) for t in triangles.tolist()]))
    positions = np.zeros((len(keys), 2))
    positions[corner_ids.reshape(-1)] = triangles.reshape(-1, 2)
    incident = [[] for _ in keys]
    for t in range(len(triangles)):
        for c in range(3):
            incident[corner_ids[t, c]].append(t)
    incident = [np.asarray(entry) for entry in incident]
    neighbours = [sorted({int(i) for t in incident[k] for i in corner_ids[t] if i != k}) for k in range(len(keys))]
    areas = signed_areas(triangles)
    sign = np.zeros(len(triangles))
    for island in set(islands[painted].tolist()):
        member = (islands == island) & painted
        sign[member] = 1.0 if (areas[member] > 0).sum() >= (areas[member] < 0).sum() else -1.0

    def folds(ids):
        return int(np.count_nonzero(signed_areas(positions[corner_ids[ids]]) * sign[ids] < -1e-14))

    def all_folded():
        return np.nonzero(signed_areas(positions[corner_ids]) * sign < -1e-14)[0]

    before = len(all_folded())
    for _ in range(iterations):
        bad = all_folded()
        if not len(bad):
            break
        changed = False
        for k in sorted({int(i) for t in bad for i in corner_ids[t]}):
            around = incident[k]
            current = folds(around)
            if not current or not neighbours[k]:
                continue
            old = positions[k].copy()
            ring = positions[neighbours[k]]
            candidates = [ring.mean(axis=0), *ring, *((ring + old) / 2)]
            best, best_folds = None, current
            for candidate in candidates:
                positions[k] = candidate
                found = folds(around)
                if found < best_folds:
                    best, best_folds = candidate.copy(), found
            positions[k] = old if best is None else best
            changed = changed or best is not None
        if not changed:
            break
    # Second pass: overlaps without a fold (a decimated island border lying over the island itself). Same moves, scored by
    # (folds, overlap area with the triangles nearby), until the overlap raster is clean.
    def overlapping():
        tris = positions[corner_ids]
        counts = np.zeros((OVERLAP_RESOLUTION, OVERLAP_RESOLUTION), dtype=np.int16)
        rasterize(tris[painted], np.zeros(int(painted.sum()), dtype=np.int32), OVERLAP_RESOLUTION, counts=counts)
        ys, xs = np.nonzero(counts > 1)
        if not len(ys):
            return []
        points = np.stack([(xs + .5) / OVERLAP_RESOLUTION, (ys + .5) / OVERLAP_RESOLUTION], axis=1)
        low, high = tris.min(axis=1), tris.max(axis=1)
        found = []
        for t in np.nonzero(painted)[0]:
            near = np.all((points >= low[t]) & (points <= high[t]), axis=1)
            if near.any():
                found.append(int(t))
        return found

    def overlap_area(ids):
        tris = positions[corner_ids]
        low, high = tris.min(axis=1), tris.max(axis=1)
        box_low, box_high = low[ids].min(axis=0), high[ids].max(axis=0)
        others = np.nonzero(painted & np.all(high >= box_low, axis=1) & np.all(low <= box_high, axis=1))[0]
        own = set(int(t) for t in ids)
        total = 0.0
        for t in ids:
            if not painted[t]:
                continue
            a = _ccw(tris[t].tolist())
            for o in others:
                if int(o) == int(t) or (int(o) in own and int(o) < int(t)):
                    continue
                if np.all(high[o] >= low[t]) and np.all(low[o] <= high[t]):
                    total += clip_area(a, _ccw(tris[o].tolist()))
        return total

    for _ in range(iterations):
        involved = overlapping()
        if not involved:
            break
        changed = False
        for k in sorted({int(i) for t in involved for i in corner_ids[t]}):
            around = incident[k]
            current = (folds(around), overlap_area(around))
            if not current[1] or not neighbours[k]:
                continue
            old = positions[k].copy()
            ring = positions[neighbours[k]]
            best, best_score = None, current
            for candidate in [ring.mean(axis=0), *ring, *((ring + old) / 2)]:
                positions[k] = candidate
                score = (folds(around), overlap_area(around))
                if score[0] <= current[0] and score[1] < best_score[1] - 1e-15:
                    best, best_score = candidate.copy(), score
            positions[k] = old if best is None else best
            changed = changed or best is not None
        if not changed:
            break
    after = len(all_folded()) + len(overlapping())
    return positions[corner_ids], before, after


def untangle_uv1(mesh):
    """untangle on a triangulated mesh's UV1 (decimated LOD0/LOD1). Returns (folds before, folds and overlapping
    triangles after)."""
    tris, _, vertices = mesh_triangles(mesh)
    fixed, before, after = untangle(tris, vertices)
    if not np.array_equal(fixed, tris):
        loops = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int64)
        mesh.loop_triangles.foreach_get("loops", loops)
        uv = _uv_array(mesh, UV1_NAME).copy()
        uv[loops] = fixed.reshape(-1, 2)
        mesh.uv_layers[UV1_NAME].data.foreach_set("uv", uv.astype(np.float32).reshape(-1))
    return before, after


def uv1_report(objects):
    """Layout report (layout_report) over the UV1 of several meshes (one atlas)."""
    triangles, islands, unpainted, offset = [], [], [], 0
    for obj in sorted(objects, key=lambda obj: obj.name):
        tris, _, vertices = mesh_triangles(obj.data)
        ids = island_ids([tuple(v) for v in vertices.tolist()], [tuple(map(tuple, t)) for t in tris.tolist()])
        triangles.append(tris)
        islands += [offset + i for i in ids]
        offset += max(ids, default=-1) + 1
        unpainted.append(np.all(tris == 0, axis=(1, 2)))
    if not triangles:
        return None
    return layout_report(np.concatenate(triangles), islands, np.concatenate(unpainted))
