"""Fingerprints of the golden surface maps (Toolgen 0.21 Livery; user 21.10.2026, "Mittelweg", Sightline 6315367022).

The golden manifest (tests/golden/surface/manifest.json) keeps the sha256 of every map; this module adds a small fingerprint
per map (tests/golden/surface/fingerprints/<tool>.json), so a map that is not byte-identical can still be judged without a
reference image in the repository (17.10.2026: no reference images, ~24 MB):

* ``thumb``: 64 x 64 block means per channel (rounded to a level, zlib + base64) - where a change is;
* ``hist``: the 256-level histogram per channel (zlib + base64) - how many texels moved and how far;
* ``mean`` per channel (readable), ``sha256`` of the map it was taken from, ``size``.

``compare`` measures a map against its fingerprint per channel: ``moved`` = texels that changed their level (lower bound,
histogram L1 / 2), ``shift`` = histogram transport in levels (earth mover's distance: at least the sum of the changes'
sizes the histogram can see), ``block`` = the largest change of a block mean in levels and where it is. ``judge`` turns that
into the three verdicts of verify_surface.py: byte-identical (sha256), within the tolerance (green with a note) or failed
(red, with map, channel and block). A change that keeps every histogram bin and every rounded block mean (e.g. two texels
swapping their values) is invisible to a fingerprint - the sha256 still names it, the tolerance accepts it.

Pure Python on bytes (the unit tests run without numpy); verify_surface.py decodes the PNG with numpy and passes the bytes.
"""
import base64
import hashlib
import struct
import zlib

FORMAT = 1
GRID = 64                        # blocks per side of the thumbnail
LEVELS = 256
CHANNELS = 4                     # every map is RGBA (toolgen/surface.py png_encode)
# what the channels of each map kind mean (docs/UNITY_EINBAU.md › Maskenkarten), for the location of a failure
CHANNEL_NAMES = {"W0": ("Primary", "Secondary", "Accent", "Emission"), "W1": ("Metal", "Detail", "Energy", "unused"),
                 "Fields": ("AO", "edge", "up", "height"), "Normal": ("normal X", "normal Y", "normal Z", "alpha")}
REGION_MAPS = ("W0", "W1")       # the weight maps name the region of a block (the channel with the largest weight there)


def map_kind(name):
    """W0, W1, Fields or Normal of a map file name (<model>_W0.png ...)."""
    return name.rsplit("_", 1)[-1].removesuffix(".png")


def _pack(values, fmt):
    return base64.b64encode(zlib.compress(struct.pack(f"<{len(values)}{fmt}", *values), 9)).decode("ascii")


def _unpack(text, fmt, count):
    return list(struct.unpack(f"<{count}{fmt}", zlib.decompress(base64.b64decode(text))))


def fingerprint(width, height, pixels, digest=None):
    """Fingerprint of an RGBA map: ``pixels`` = bytes, rows top to bottom (PNG order), 4 bytes per texel. ``digest``: the
    map file's sha256 (taken from the file, not from the pixels)."""
    if width % GRID or height % GRID:
        raise ValueError(f"map {width} x {height} is not a multiple of the {GRID} grid")
    if len(pixels) != width * height * CHANNELS:
        raise ValueError("pixels do not match the size")
    block_w, block_h = width // GRID, height // GRID
    count = block_w * block_h
    stride = width * CHANNELS
    sums = [[0] * (GRID * GRID) for _ in range(CHANNELS)]
    for y in range(height):
        row = pixels[y * stride:(y + 1) * stride]
        base = (y // block_h) * GRID
        for channel in range(CHANNELS):
            values, target = row[channel::CHANNELS], sums[channel]
            for bx in range(GRID):
                target[base + bx] += sum(values[bx * block_w:(bx + 1) * block_w])
    thumb, hist, mean = [], [], []
    for channel in range(CHANNELS):
        thumb += [(2 * value + count) // (2 * count) for value in sums[channel]]    # rounded half up, integers only
        values = pixels[channel::CHANNELS]
        hist += [values.count(level) for level in range(LEVELS)]
        mean.append(round(sum(sums[channel]) / (width * height), 3))
    return {"format": FORMAT, "sha256": digest, "size": [width, height], "grid": GRID, "mean": mean,
            "thumb": _pack(thumb, "B"), "hist": _pack(hist, "I")}


def of_png(data, decode):
    """Fingerprint of a PNG file's bytes; ``decode(data)`` -> (width, height, RGBA bytes top to bottom)."""
    width, height, pixels = decode(data)
    return fingerprint(width, height, pixels, hashlib.sha256(data).hexdigest())


def thumbs(entry):
    values = _unpack(entry["thumb"], "B", CHANNELS * GRID * GRID)
    return [values[c * GRID * GRID:(c + 1) * GRID * GRID] for c in range(CHANNELS)]


def histograms(entry):
    values = _unpack(entry["hist"], "I", CHANNELS * LEVELS)
    return [values[c * LEVELS:(c + 1) * LEVELS] for c in range(CHANNELS)]


def block_uv(index):
    """UV rectangle (u0, v0, u1, v1) of a thumbnail block (row 0 = top of the PNG = v 1)."""
    by, bx = divmod(index, GRID)
    return (bx / GRID, 1 - (by + 1) / GRID, (bx + 1) / GRID, 1 - by / GRID)


def compare(reference, current):
    """Per channel: ``moved`` (texels that changed level, lower bound), ``shift`` (histogram transport in levels),
    ``block`` (largest change of a block mean in levels), ``block_index``, ``blocks`` (blocks that changed), ``mean``."""
    if reference["size"] != current["size"] or reference.get("grid") != current.get("grid"):
        return {"size": [reference["size"], current["size"]], "channels": None}
    channels = []
    for (ref_hist, cur_hist), (ref_thumb, cur_thumb), ref_mean, cur_mean in zip(
            zip(histograms(reference), histograms(current)), zip(thumbs(reference), thumbs(current)),
            reference["mean"], current["mean"]):
        moved = sum(abs(a - b) for a, b in zip(ref_hist, cur_hist)) // 2
        shift, carried = 0, 0
        for a, b in zip(ref_hist, cur_hist):
            carried += a - b
            shift += abs(carried)
        deltas = [abs(a - b) for a, b in zip(ref_thumb, cur_thumb)]
        worst = max(range(len(deltas)), key=lambda i: (deltas[i], -i))
        channels.append({"moved": moved, "shift": shift, "block": deltas[worst], "block_index": worst,
                         "blocks": sum(1 for d in deltas if d), "mean": round(cur_mean - ref_mean, 3)})
    width, height = reference["size"]
    return {"texels": width * height, "channels": channels}


def region_at(model_fingerprints, index):
    """The weight region at a block (the W0/W1 channel with the largest mean there), from the model's reference
    fingerprints {map kind: fingerprint}; None without weight maps."""
    best = None
    for kind in REGION_MAPS:
        entry = model_fingerprints.get(kind)
        if entry is None:
            continue
        for channel, values in enumerate(thumbs(entry)):
            name = CHANNEL_NAMES[kind][channel]
            if name != "unused" and values[index] and (best is None or values[index] > best[0]):
                best = (values[index], name)
    return best[1] if best else None


def judge(name, comparison, tolerance, model_fingerprints=None, current=None):
    """(within tolerance, text) of a comparison. Within: in every channel at most ``tolerance["share"]`` of the texels
    changed (histogram), by at most ``tolerance["levels"]`` levels on average (shift / moved), the histogram transport
    stays within share x levels, and no block mean moved more than ``tolerance["block_levels"]``. The text names the map,
    the channel and the block (UV rectangle, weight region) of the largest change; the region comes from the model's
    reference weight maps, else from ``current`` (the map's own new fingerprint, when it is a weight map)."""
    if comparison["channels"] is None:
        return False, f"{name}: size {comparison['size'][1]} instead of {comparison['size'][0]}"
    texels, kind = comparison["texels"], map_kind(name)
    names = CHANNEL_NAMES.get(kind, ("R", "G", "B", "A"))
    budget_moved = tolerance["share"] * texels
    worst, failed = None, []
    for channel, values in enumerate(comparison["channels"]):
        reasons = []
        if values["moved"] > budget_moved:
            reasons.append(f"{values['moved']} texels changed ({values['moved'] / texels:.4%} > {tolerance['share']:.2%})")
        if values["moved"] and values["shift"] > tolerance["levels"] * values["moved"]:
            reasons.append(f"by {values['shift'] / values['moved']:.2f} levels on average (> {tolerance['levels']})")
        if values["shift"] > budget_moved * tolerance["levels"]:
            reasons.append(f"histogram transport {values['shift']} levels")
        if values["block"] > tolerance["block_levels"]:
            reasons.append(f"block mean {values['block']} levels (> {tolerance['block_levels']})")
        if reasons:
            failed.append((channel, reasons))
        if worst is None or (values["block"], values["moved"]) > (comparison["channels"][worst]["block"],
                                                                  comparison["channels"][worst]["moved"]):
            worst = channel
    channel = failed[0][0] if failed else worst
    values = comparison["channels"][channel]
    u0, v0, u1, v1 = block_uv(values["block_index"])
    region = region_at(model_fingerprints or {}, values["block_index"])
    if region is None and current is not None:
        region = region_at({kind: current}, values["block_index"])
    where = (f"channel {names[channel]}, block u {u0:.3f}-{u1:.3f} v {v0:.3f}-{v1:.3f}"
             + (f" (region {region})" if region else ""))
    if failed:
        return False, f"{name}: {where}: " + "; ".join(failed[0][1]) + \
            "".join(f"; channel {names[c]}: " + ", ".join(r) for c, r in failed[1:])
    moved = max(values["moved"] for values in comparison["channels"])
    return True, (f"{name}: within the tolerance, at most {moved} texels ({moved / texels:.5%}) changed by "
                  f"<= {tolerance['levels']} level; largest at {where}")
