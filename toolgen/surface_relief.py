"""Relief detail of the weapons in the normal map (Toolgen 0.13 Enamel) and the contract block ``surface.recipe``.

``data/surface_recipes.json`` holds per weapon the recipe (material kind, smoothness, wear, glow per channel - Cube Escape
computes colour, wear, dirt and noise in its shader, Toolgen only passes the recipe on) and the relief: part selector ->
pattern(s) {type, size_mm, direction, across, width_mm, strength}. ``surface_bake.py`` labels every LOD0 triangle with its
source part (``part_labels``), resolves the relief per triangle (``relief_index``) and, right before the NORMAL bake, puts the
node tree of ``relief_nodes`` between the bevel normal and the bake material's normal input: the height of the patterns
(0..1 x strength) drives a Bump node with the distance ``max_height_mm`` (0.3 mm), so the silhouette, the collision and the
other maps never change. All patterns are functions of the position in the tool frame (Socket_Hand), the same in the world
and the first-person model: no random numbers, Blender's noise is fixed (seed 0 of the bake).

The pure part (loading, checks, selectors, the recipe block) imports without Blender.
"""
import fnmatch
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPES_PATH = ROOT / "data/surface_recipes.json"
RECIPE_VERSION = 1               # version of the contract block surface.recipe
PART_PREFIX = "SM_PG_"
AXES = ("x", "y", "z")
TYPES = ("knurl", "grooves", "lamellae", "seams", "brushed", "grain")
NEEDS_DIRECTION = ("knurl", "grooves", "lamellae", "seams", "brushed")
MIN_SIZE_MM = .3
CHANNELS = ("Primary", "Secondary", "Accent", "Metal", "Energy", "Emission", "Detail")   # surface.CHANNELS


def load(path=RECIPES_PATH):
    return json.loads(Path(path).read_text())


def part_name(name):
    """Source mesh name without the kit prefix (``SM_PG_GripShell_1`` -> ``GripShell_1``)."""
    return name[len(PART_PREFIX):] if name.startswith(PART_PREFIX) else name


def patterns_of(value):
    return list(value) if isinstance(value, list) else [value]


def recipe_errors(data, tool_ids=None, parts=None):
    """Problems of the recipe file; ``tool_ids`` (catalogue) and ``parts`` ({tool: [part names]}) are optional."""
    errors = []
    limits = data.get("limits", {})
    height = limits.get("max_height_mm")
    if not isinstance(height, (int, float)) or not 0 < height <= .3:
        errors.append("limits.max_height_mm must be in (0, 0.3]")
    smooth_max = limits.get("smoothness_max", 1)
    wear_levels = limits.get("wear_levels", {})
    materials = set(data.get("materials", []))
    for tool, entry in data.get("weapons", {}).items():
        where = f"weapons.{tool}"
        if tool_ids is not None and tool not in tool_ids:
            errors.append(f"{where}: unknown tool id")
        if entry.get("wear") not in wear_levels:
            errors.append(f"{where}.wear must be one of {sorted(wear_levels)}")
        channels = entry.get("channels", {})
        if sorted(channels) != sorted(CHANNELS):
            errors.append(f"{where}.channels must name every channel of {', '.join(CHANNELS)}")
        for channel, spec in channels.items():
            if spec.get("material") not in materials:
                errors.append(f"{where}.channels.{channel}.material unknown: {spec.get('material')}")
            smooth = spec.get("smoothness")
            if not isinstance(smooth, (int, float)) or not 0 <= smooth <= smooth_max:
                errors.append(f"{where}.channels.{channel}.smoothness must be in [0, {smooth_max}]")
        if not _is_colour(entry.get("glow", {}).get("color")):
            errors.append(f"{where}.glow.color must be #RRGGBB")
        if not all(_is_colour(colour) for colour in entry.get("palette", [])) or not entry.get("palette"):
            errors.append(f"{where}.palette must be a list of #RRGGBB")
        for selector, value in entry.get("relief", {}).items():
            if not patterns_of(value):
                errors.append(f"{where}.relief.{selector}: needs at least one pattern")
            if sum(pattern.get("strength", 0) for pattern in patterns_of(value)
                   if isinstance(pattern, dict) and _number(pattern.get("strength"))) > 1 + 1e-9:
                errors.append(f"{where}.relief.{selector}: strengths add up to more than 1 (relief > max_height_mm)")
            if selector.startswith("@") and selector[1:] not in CHANNELS:
                errors.append(f"{where}.relief.{selector}: unknown channel")
            elif parts is not None and tool in parts and not selector.startswith("@") \
                    and not any(fnmatch.fnmatchcase(name, selector) for name in parts[tool]):
                errors.append(f"{where}.relief.{selector}: matches no part")
            for pattern in patterns_of(value):
                errors += [f"{where}.relief.{selector}: {error}" for error in pattern_errors(pattern)]
    return errors


def _is_colour(value):
    return isinstance(value, str) and len(value) == 7 and value[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in value[1:])


def _number(value):
    """A finite int or float (JSON also reads NaN and Infinity)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def pattern_errors(pattern):
    errors = []
    if not isinstance(pattern, dict):
        return ["a pattern is an object"]
    kind = pattern.get("type")
    if kind not in TYPES:
        return [f"type {kind!r} not in {TYPES}"]
    if not _number(pattern.get("size_mm")) or pattern["size_mm"] < MIN_SIZE_MM:
        errors.append(f"size_mm must be a finite number >= {MIN_SIZE_MM}")
    strength = pattern.get("strength")
    if not _number(strength) or not 0 < strength <= 1:
        errors.append("strength must be in (0, 1]")
    if kind in NEEDS_DIRECTION and pattern.get("direction") not in AXES:
        errors.append(f"{kind} needs direction x, y or z")
    if kind == "knurl" and (pattern.get("across") not in AXES or pattern.get("across") == pattern.get("direction")):
        errors.append("knurl needs an 'across' axis other than its direction")
    if kind == "seams":
        width = pattern.get("width_mm")
        size = pattern.get("size_mm") if _number(pattern.get("size_mm")) else 0
        if not _number(width) or not 0 < width < size / 4:
            errors.append("seams need 0 < width_mm < size_mm / 4")
        if "across_mm" in pattern:
            across = pattern["across_mm"]
            if pattern.get("across") not in AXES or pattern.get("across") == pattern.get("direction"):
                errors.append("seams with across_mm need an 'across' axis other than their direction")
            if not _number(across) or not _number(width) or not across > 4 * width:
                errors.append("seams need across_mm > 4 x width_mm")
    return errors


def select(relief, part, channel):
    """Index into the relief entries (dict order) of the first selector matching a part (name without prefix) or its
    channel; None when no selector matches."""
    for index, selector in enumerate(relief):
        if selector.startswith("@"):
            if selector[1:] == channel:
                return index
        elif part is not None and fnmatch.fnmatchcase(part, selector):
            return index
    return None


def relief_index(relief, parts, channels):
    """Per triangle the relief entry (index, -1 = none) from its part name (None = unknown) and channel."""
    return [(-1 if (found := select(relief, part, channel)) is None else found) for part, channel in zip(parts, channels)]


def palette_block(palettes, entry):
    """0.21 (Livery, stage B), additive: the colour palettes of the weapon's concept sheet (formgen weapon spec ``palette``)
    as proposals for Cube Escape's presets; ``default`` = the recipe's ``palette_default`` or the sheet's first palette
    (formgen lists ``base``, the sheet's own colours, first; user decision 22.10.2026: base)."""
    default = entry.get("palette_default", palettes[0]["id"])
    if default not in [item["id"] for item in palettes]:
        raise ValueError(f"palette_default {default} is not a palette of the sheet")
    return {"source": "formgen weapon spec palette (data/concepts/<sheet>.spec.json)", "default": default,
            "channels": "Primary ... Detail = the MT_ slots; null = the sheet leaves the channel free",
            "items": palettes}


def recipe_block(tool_id, entry, limits, decals, design_element, regions=(), palettes=()):
    """Block surface.recipe of the contract (additive, contract stays 4): data for Cube Escape's presets. 0.21: a weapon
    built from a concept sheet adds ``regions`` (the sheet's decals as mask regions) and ``palettes``."""
    levels = limits["wear_levels"]
    extra = {}
    if regions:
        extra["regions"] = {"source": "concept sheet decals[] (geometry spec), baked into W0/W1 like decals: the region's "
                                      "texels take its channel; part_channel = the channel of the part beneath",
                            "items": list(regions)}
    if palettes:
        extra["palettes"] = palette_block(list(palettes), entry)
    return {
        "version": RECIPE_VERSION,
        "source": "Cube Escape Docs/EQUIPMENT.md > Zielbild > Texturen 1-9 (sheet %d, %s)" % (entry["sheet"], entry["title"]),
        "tool": tool_id,
        "palette": list(entry["palette"]),
        "glow": {"color": entry["glow"]["color"], "element": entry["glow"]["element"], "model_element": design_element},
        "wear": {"level": entry["wear"], "amount": levels[entry["wear"]], "levels": dict(levels)},
        "channels": {channel: {key: value for key, value in entry["channels"][channel].items()} for channel in CHANNELS},
        "decals": decals,
        "relief": {"in": "Normal", "max_height_mm": limits["max_height_mm"],
                   "parts": {selector: patterns_of(value) for selector, value in entry.get("relief", {}).items()}},
        "computed_by_consumer": "colour, material kind, smoothness, wear/dirt/scratches, noise and glow are Cube Escape's "
                                "(shader, SurfaceGenerator1, EquipmentDesign.surface); smoothness is a mask-mode value - "
                                "game_palette.json finish stays for the slot path",
        "minimum_consumer": "Cube Escape 0.76 (Equipment presets); 0.71-0.75 ignore the block",
        **extra,
    }


# --------------------------------------------------------------------------------------------- Blender
def relief_nodes(material, normal_socket, relief, frame_object, max_height_mm, attribute):
    """Bump node chain for the relief entries on the bake material; returns the bumped normal socket (connect it to the
    BSDF normal before the NORMAL bake). ``attribute``: the face attribute (int) with the relief entry per face (-1 none),
    ``frame_object``: an empty at Socket_Hand (Texture Coordinate 'Object' = tool frame)."""
    nodes, links = material.node_tree.nodes, material.node_tree.links

    def node(kind, **inputs):
        created = nodes.new(kind)
        for key, value in inputs.items():
            if isinstance(value, (int, float, tuple)):
                created.inputs[key].default_value = value
            else:
                links.new(value, created.inputs[key])
        return created

    def math(operation, a, b=None, c=None, clamp=False):
        created = nodes.new("ShaderNodeMath")
        created.operation = operation
        created.use_clamp = clamp
        for socket, value in ((0, a), (1, b), (2, c)):
            if value is None:
                continue
            if isinstance(value, (int, float)):
                created.inputs[socket].default_value = value
            else:
                links.new(value, created.inputs[socket])
        return created.outputs[0]

    coords = nodes.new("ShaderNodeTexCoord")
    coords.object = frame_object
    millimetres = nodes.new("ShaderNodeVectorMath")
    millimetres.operation = "SCALE"
    links.new(coords.outputs["Object"], millimetres.inputs[0])
    millimetres.inputs["Scale"].default_value = 1000.0
    position = millimetres.outputs[0]
    axes = nodes.new("ShaderNodeSeparateXYZ")
    links.new(position, axes.inputs[0])
    axis = {"x": axes.outputs["X"], "y": axes.outputs["Y"], "z": axes.outputs["Z"]}
    face = nodes.new("ShaderNodeAttribute")
    face.attribute_type = "GEOMETRY"
    face.attribute_name = attribute

    def wave(value, pitch):
        """0.5 + 0.5 cos(2 pi value / pitch)"""
        return math("MULTIPLY_ADD", math("COSINE", math("MULTIPLY", value, 6.283185307179586 / pitch)), .5, .5)

    def triangle(value, pitch):
        """0 at the joints, 1 half way between them: 2 |fract(value / pitch) - 0.5| inverted."""
        return math("SUBTRACT", 1.0, math("MULTIPLY", math("ABSOLUTE", math("SUBTRACT", math("FRACT", math("DIVIDE", value, pitch)), .5)), 2.0))

    def noise(vector, scale, detail):
        texture = nodes.new("ShaderNodeTexNoise")
        texture.noise_dimensions = "3D"
        texture.inputs["Scale"].default_value = scale
        texture.inputs["Detail"].default_value = detail
        texture.inputs["Roughness"].default_value = .5
        links.new(vector, texture.inputs["Vector"])
        return texture.outputs["Fac"]

    def height(pattern):
        kind, size = pattern["type"], float(pattern["size_mm"])
        if kind == "grooves":
            return wave(axis[pattern["direction"]], size)
        if kind == "lamellae":
            node_ = nodes.new("ShaderNodeMapRange")
            node_.clamp = True
            node_.inputs["From Min"].default_value, node_.inputs["From Max"].default_value = .35, .65
            links.new(triangle(axis[pattern["direction"]], size), node_.inputs["Value"])
            return node_.outputs["Result"]
        if kind == "knurl":
            a, b = axis[pattern["direction"]], axis[pattern["across"]]
            pitch = size * 1.4142135623730951
            return math("MINIMUM", wave(math("ADD", a, b), pitch), wave(math("SUBTRACT", a, b), pitch))
        if kind == "seams":
            width = float(pattern["width_mm"])

            def joints(value, pitch):
                # distance to the nearest joint plane (mm) -> 1 inside the joint, 0 outside (smooth over 30 % of the width)
                distance = math("MULTIPLY", math("ABSOLUTE", math("SUBTRACT", math("FRACT", math("DIVIDE", value, pitch)), .5)), pitch)
                ramp = nodes.new("ShaderNodeMapRange")
                ramp.clamp = True
                ramp.inputs["From Min"].default_value = pitch / 2 - width / 2
                ramp.inputs["From Max"].default_value = pitch / 2 - width * .2
                links.new(distance, ramp.inputs["Value"])
                return ramp.outputs["Result"]

            joint = joints(axis[pattern["direction"]], size)
            if pattern.get("across_mm"):
                joint = math("MAXIMUM", joint, joints(axis[pattern["across"]], float(pattern["across_mm"])))
            return math("SUBTRACT", 1.0, joint)          # surface 1, joint pressed in to 0
        if kind == "brushed":
            stretch = {"x": (.02, 1, 1), "y": (1, .02, 1), "z": (1, 1, .02)}[pattern["direction"]]
            scaled = nodes.new("ShaderNodeVectorMath")
            scaled.operation = "MULTIPLY"
            links.new(position, scaled.inputs[0])
            scaled.inputs[1].default_value = tuple(value / size for value in stretch)
            return noise(scaled.outputs[0], 1.0, 3.0)
        if kind == "grain":
            scaled = nodes.new("ShaderNodeVectorMath")
            scaled.operation = "SCALE"
            links.new(position, scaled.inputs[0])
            scaled.inputs["Scale"].default_value = 1.0 / size
            return noise(scaled.outputs[0], 1.0, 4.0)
        raise ValueError(f"unknown relief type {kind}")

    total = None
    for index, value in enumerate(relief.values()):
        part = None
        for pattern in patterns_of(value):
            term = math("MULTIPLY", height(pattern), float(pattern["strength"]))
            part = term if part is None else math("ADD", part, term)
        mask = math("COMPARE", face.outputs["Fac"], float(index))
        mask.node.inputs[2].default_value = .25                         # epsilon of COMPARE
        term = math("MULTIPLY", part, mask)
        total = term if total is None else math("ADD", total, term)
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 1.0
    bump.inputs["Distance"].default_value = max_height_mm / 1000.0
    links.new(total if total is not None else math("ADD", 0.0, 0.0), bump.inputs["Height"])
    links.new(normal_socket, bump.inputs["Normal"])
    return bump.outputs["Normal"]
