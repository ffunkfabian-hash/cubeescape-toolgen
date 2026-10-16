"""Stage surface_bake (contract 4, tiers standard and full): mask maps of both game models of a tool.

    blender --background --factory-startup --python toolgen/run_asset.py -- \
        --script toolgen/surface_bake.py --directory <work> --tool <tool_id>

Reads ``<asset>_Game.blend`` and ``<asset>_FPS_Game.blend`` (with UV1 from game_export.py), the two contracts and their
QA files, and writes per model ``<model>_W0.png``, ``_W1.png``, ``_Fields.png``, ``_Normal.png`` (8 bit RGBA, linear, no
colour chunks; world 512, first-person 1024), the block ``surface`` in ``unity_contract.json`` / ``unity_contract_fps.json``
and ``qa_surface.json`` (exit code 1 when a check fails).

* W0/W1: per LOD0 triangle the channel of its material slot (toolgen/surface.py ``channel_of``) rasterised on UV1, one-hot
  255, then continued 8 px outward (nearest texel). Faces of the hands (UV1 at (0, 0)) and slots without channel stay 0.
* Fields: R ambient occlusion (Cycles AO bake), G convex edge (bevel normal against the shading normal, concave creases
  removed with a local AO), B up (max(0, world normal . up)), A height (0..1 over the model's LOD0 height), Cycles EMIT bake.
* Normal: Cycles NORMAL bake in tangent space of UV1, OpenGL (Y+), from the bevel normal (rounded edges), flat = 128,128,255.

All bakes run on the CPU with a fixed seed and fixed samples per variant (never the tier's render samples), so standard and
full give the same files; the hands are removed before baking (no occlusion from them) and moving parts bake at rest.
"""
import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import bpy
import bmesh
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
import surface  # noqa: E402

PALETTE_PATH = ROOT / "data/game_palette.json"
TOOLS_PATH = ROOT / "data/tools.json"
BAKE_SCHEMA = 1                  # raise when the baked content changes without any key part changing
VARIANTS = (("world", "", "unity_contract.json", "qa_game.json"),
            ("viewmodel", "_FPS", "unity_contract_fps.json", "qa_game_fps.json"))


def renderers_at_rest(asset):
    scene = bpy.context.scene
    scene.frame_set(scene.frame_start)
    root = scene.objects[asset]
    meshes = [obj for obj in root.children_recursive if obj.type == "MESH"]
    lod0 = sorted((obj for obj in meshes if obj.get("ce_lod") == 0), key=lambda obj: obj.name)
    for obj in meshes:
        if obj.get("ce_lod") != 0:
            bpy.data.objects.remove(obj)
    return scene, root, lod0


def mesh_key(objects):
    """Positions, topology, UV0, UV1, corner normals and slots of the LOD0 renderers (tangents follow from these)."""
    parts = []
    for obj in objects:
        mesh = obj.data
        arrays = []
        for collection, attribute, dtype, width in ((mesh.vertices, "co", np.float32, 3), (mesh.loops, "vertex_index", np.int32, 1),
                                                    (mesh.polygons, "loop_start", np.int32, 1),
                                                    (mesh.polygons, "material_index", np.int32, 1)):
            values = np.empty(len(collection) * width, dtype=dtype)
            collection.foreach_get(attribute, values)
            arrays.append(values.tobytes())
        for name in (surface.UV0_NAME, surface.UV1_NAME):
            arrays.append(surface._uv_array(mesh, name).tobytes())
        normals = np.empty(len(mesh.loops) * 3, dtype=np.float32)
        mesh.corner_normals.foreach_get("vector", normals)
        arrays.append(normals.tobytes())
        parts.append(surface.digest(obj.name, [list(row) for row in obj.matrix_world], [m.name for m in mesh.materials], *arrays))
    return parts


def channel_raster(objects, palette, resolution):
    """Channel index per texel (CHANNELS order, -1 = none) and the set of channels painted by some face."""
    triangles, labels = [], []
    for obj in objects:
        tris, faces, _ = surface.mesh_triangles(obj.data)
        slots = [surface.channel_of(material.name, palette) for material in obj.data.materials]
        index = np.empty(len(obj.data.polygons), dtype=np.int32)
        obj.data.polygons.foreach_get("material_index", index)
        per_face = np.array([surface.CHANNELS.index(slots[i]) if slots[i] else -1 for i in index], dtype=np.int32)
        painted = ~np.all(tris == 0, axis=(1, 2)) & (per_face[faces] >= 0)
        triangles.append(tris[painted])
        labels.append(per_face[faces][painted])
    triangles, labels = np.concatenate(triangles), np.concatenate(labels)
    raster = surface.rasterize(triangles, labels, resolution)
    return raster, sorted({surface.CHANNELS[i] for i in set(labels.tolist())})


def strip_unpainted(objects):
    """Remove the faces with UV1 at (0, 0) (hands, arms) so they neither get baked nor occlude the tool."""
    for obj in objects:
        mesh = obj.data
        if mesh.shape_keys:
            continue                # morph parts are tool parts (unpainted faces only come from FPS_* hand meshes)
        uv = surface._uv_array(mesh, surface.UV1_NAME)
        starts = np.empty(len(mesh.polygons), dtype=np.int64)
        totals = np.empty(len(mesh.polygons), dtype=np.int64)
        mesh.polygons.foreach_get("loop_start", starts)
        mesh.polygons.foreach_get("loop_total", totals)
        zero = np.all(uv == 0, axis=1)
        drop = [i for i, (s, t) in enumerate(zip(starts, totals)) if zero[s:s + t].all()]
        if drop:
            data = bmesh.new()
            data.from_mesh(mesh)
            data.faces.ensure_lookup_table()
            bmesh.ops.delete(data, geom=[data.faces[i] for i in drop], context="FACES")
            data.to_mesh(mesh)
            data.free()
    return [obj for obj in objects if len(obj.data.polygons)]


def bake_material(z_range):
    material = bpy.data.materials.new("SurfaceBake")
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
    bsdf.inputs["Emission Strength"].default_value = 1.0
    geometry = nodes.new("ShaderNodeNewGeometry")
    bevel = nodes.new("ShaderNodeBevel")
    bevel.samples = surface.EDGE_SAMPLES
    bevel.inputs["Radius"].default_value = surface.BEVEL_RADIUS_M
    occlusion = nodes.new("ShaderNodeAmbientOcclusion")
    occlusion.samples = surface.EDGE_SAMPLES
    occlusion.only_local = True
    occlusion.inputs["Distance"].default_value = 4 * surface.BEVEL_RADIUS_M

    def math(operation, a, b=None, clamp=False):
        node = nodes.new("ShaderNodeMath")
        node.operation = operation
        node.use_clamp = clamp
        for socket, value in ((0, a), (1, b)):
            if value is None:
                continue
            if isinstance(value, (int, float)):
                node.inputs[socket].default_value = value
            else:
                links.new(value, node.inputs[socket])
        return node.outputs[0]

    def map_range(value, low, high):
        node = nodes.new("ShaderNodeMapRange")
        node.clamp = True
        node.inputs["From Min"].default_value, node.inputs["From Max"].default_value = low, high
        links.new(value, node.inputs["Value"])
        return node.outputs["Result"]

    dot = nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    links.new(bevel.outputs["Normal"], dot.inputs[0])
    links.new(geometry.outputs["Normal"], dot.inputs[1])
    bend = math("MULTIPLY", math("SUBTRACT", 1.0, dot.outputs["Value"]), surface.EDGE_GAIN)
    edge = math("MULTIPLY", bend, map_range(occlusion.outputs["AO"], *surface.EDGE_CONVEX), clamp=True)
    normal = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geometry.outputs["Normal"], normal.inputs[0])
    up = math("MAXIMUM", normal.outputs["Z"], 0.0, clamp=True)
    position = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geometry.outputs["Position"], position.inputs[0])
    height = map_range(position.outputs["Z"], *z_range)
    combine = nodes.new("ShaderNodeCombineColor")
    links.new(edge, combine.inputs[0])
    links.new(up, combine.inputs[1])
    links.new(height, combine.inputs[2])
    links.new(combine.outputs[0], bsdf.inputs["Emission Color"])
    links.new(bevel.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs[0], output.inputs["Surface"])
    image_node = nodes.new("ShaderNodeTexImage")
    nodes.active = image_node
    return material, image_node


def bake_pass(kind, image_node, resolution, fill, samples, **options):
    image = bpy.data.images.new(f"Bake_{kind}", resolution, resolution, alpha=True, float_buffer=True)
    image.colorspace_settings.name = "Non-Color"
    image.generated_color = fill
    image_node.image = image
    bpy.context.scene.cycles.samples = samples
    result = bpy.ops.object.bake(type=kind, uv_layer=surface.UV1_NAME, margin=surface.DILATION_PX, margin_type="EXTEND",
                                 use_clear=False, target="IMAGE_TEXTURES", **options)
    if "FINISHED" not in result:
        raise RuntimeError(f"bake {kind} failed")
    pixels = np.empty(resolution * resolution * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    return pixels.reshape(resolution, resolution, 4)


def to_bytes(values):
    return np.clip(np.rint(values * 255.0), 0, 255).astype(np.uint8)


def bake_model(work, model, asset, variant, palette):
    """Maps (v-up arrays), channel raster, channels used, the content key parts and the LOD0 layout report."""
    bpy.ops.wm.open_mainfile(filepath=str(work / (model + ".blend")))
    scene, root, lod0 = renderers_at_rest(asset)
    resolution, samples = surface.MAP_RESOLUTION[variant], surface.AO_SAMPLES[variant]
    key_parts = mesh_key(lod0)
    layout = surface.uv1_report(lod0)
    raster, channels = channel_raster(lod0, palette, resolution)
    maps, _ = surface.weight_maps(raster)
    slots = sorted({material.name for obj in lod0 for material in obj.data.materials})
    targets = strip_unpainted(lod0)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    heights = [(obj.matrix_world @ vertex.co).z for obj in targets for vertex in obj.evaluated_get(depsgraph).data.vertices]
    z_range = (min(heights), max(heights))
    for obj in [obj for obj in scene.objects if obj not in targets]:
        if obj.type == "MESH":
            bpy.data.objects.remove(obj)
    material, image_node = bake_material(z_range)
    for obj in targets:
        for index in range(len(obj.data.materials)):
            obj.data.materials[index] = material
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.seed = 0
    scene.cycles.use_animated_seed = False
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("SurfaceBakeWorld")
    scene.world.light_settings.distance = surface.AO_DISTANCE_M
    for obj in bpy.context.view_layer.objects:
        obj.select_set(obj in targets)
    bpy.context.view_layer.objects.active = targets[0]
    timings, phase = {}, time.perf_counter()
    ao = bake_pass("AO", image_node, resolution, (1, 1, 1, 1), samples)
    timings["ao"], phase = time.perf_counter() - phase, time.perf_counter()
    emit = bake_pass("EMIT", image_node, resolution, (0, 0, 0, 1), surface.DETAIL_SAMPLES)
    timings["emit"], phase = time.perf_counter() - phase, time.perf_counter()
    normal = bake_pass("NORMAL", image_node, resolution, (.5, .5, 1, 1), surface.DETAIL_SAMPLES, normal_space="TANGENT",
                       normal_r="POS_X", normal_g="POS_Y", normal_b="POS_Z")
    timings["normal"] = time.perf_counter() - phase
    maps["Fields"] = to_bytes(np.stack([ao[..., 0], emit[..., 0], emit[..., 1], emit[..., 2]], axis=2))
    maps["Normal"] = to_bytes(np.concatenate([normal[..., :3], np.ones_like(normal[..., :1])], axis=2))
    settings = {"schema": BAKE_SCHEMA, "resolution": resolution, "ao_samples": samples, "edge_samples": surface.EDGE_SAMPLES,
                "detail_samples": surface.DETAIL_SAMPLES,
                "ao_distance_m": surface.AO_DISTANCE_M, "bevel_radius_m": surface.BEVEL_RADIUS_M, "edge_gain": surface.EDGE_GAIN,
                "edge_convex": surface.EDGE_CONVEX, "dilation_px": surface.DILATION_PX, "device": "CPU", "seed": 0,
                "height_range_m": [round(z, 6) for z in z_range]}
    return maps, raster, channels, slots, key_parts, settings, layout, timings


def surface_block(model, variant, palette, slots, settings, files, set_bytes, key, layout, shared, minimum, clips):
    return {
        "version": surface.SURFACE_VERSION,
        "uv1": {"attribute": "TEXCOORD_1", "uv_map": surface.UV1_NAME, "fbx_uv_set": 1, "resolution": surface.CHECK_RESOLUTION,
                "margin_px": surface.MARGIN_PX, "islands_rotated": False, "shared_with_world": shared,
                "layout": {key_: layout[key_] for key_ in ("islands", "used_share", "min_gap_px", "overlap_texels")},
                "unpainted": {"uv": [0.0, 0.0], "faces": "first-person hands and arms (source materials FPS_*)",
                              "weights": 0, "reserved_band": surface.RESERVED_LOW,
                              "note": "these faces sample one texel with weight 0 in every channel; keep the slot's own colour "
                                      "where the weight sum is 0"},
                "shared_note": "true: the first-person model's tool parts carry exactly the world model's UV1 (same islands); "
                               "each model still has its own map set (other resolution, own decimation)"},
        "tangents": {"for": "uv1", "glb": "TANGENT, MikkTSpace on TEXCOORD_1, w = handedness",
                     "fbx": "none: compute MikkTSpace tangents from UV1 at import (Unity's FBX import reads UV0 tangents only, "
                            "measured in Cube Escape 0.71)"},
        "regions": dict(surface.REGIONS),
        "channel_map": surface.model_channel_map(palette, slots),
        "unmapped_slots": sorted(slot for slot in slots if not surface.channel_of(slot, palette)),
        "maps": {"resolution": settings["resolution"], **surface.map_names(model), "format": "PNG RGBA, 8 bit",
                 "color_space": "linear (import with sRGB off)", "rows": "PNG top row = v 1 (Unity texture orientation)",
                 "dilation_px": surface.DILATION_PX, "set_bytes": set_bytes,
                 "import": "sRGB off, alphaIsTransparency off, no premultiply (W0.a carries Emission); Normal: OpenGL (Y+), "
                           "flat 128,128,255",
                 "applies_to": [model + ".fbx", model + ".glb", *clips],
                 "files": files},
        "fields": {"r": f"ambient occlusion, 1 = open (Cycles, {settings['ao_samples']} samples, {surface.AO_DISTANCE_M} m)",
                   "g": f"edge, 1 = convex edge (bevel {surface.BEVEL_RADIUS_M} m against the shading normal)",
                   "b": "up = max(0, world normal . up)", "a": "height 0..1 over the LOD0 model height at rest"},
        "bake": {"stage": "surface_bake", "blender": bpy.app.version_string, "key": key, "settings": settings},
        "minimum_consumer": minimum,
        "older_consumers": "generate_tools.py --contract 3 (or game_export.py --contract 3): no UV1, no surface block "
                           "(Toolgen 0.10 layout)",
    }


def main():
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description="Bake the contract 4 surface maps of both game models")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--tool", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    work = args.directory.resolve()
    # run_asset.py sets the tier's render samples and device on render_init; the bake keeps its own fixed settings.
    bpy.app.handlers.render_init.clear()
    report = {"tool": args.tool, "passed": False, "checks": {}}
    try:
        tool = {entry["id"]: entry for entry in json.loads(TOOLS_PATH.read_text())["tools"]}[args.tool]
        palette = json.loads(PALETTE_PATH.read_text())
        errors = surface.channel_map_errors(palette)
        report["checks"]["channel_map"] = {"passed": not errors, "errors": errors}
        if errors:
            raise RuntimeError("; ".join(errors))
        qa = {variant: json.loads((work / qa_name).read_text()) for variant, _, _, qa_name in VARIANTS}
        world_uv1, ego_uv1 = qa["world"]["checks"]["uv1_source"], qa["viewmodel"]["checks"]["uv1_source"]
        shared = bool(ego_uv1.get("shared_with_world")) and ego_uv1.get("world_sha256") == world_uv1.get("sha256")
        report["checks"]["uv1_shared"] = {"passed": shared == bool(ego_uv1.get("shared_with_world")), "shared_with_world": shared,
                                          "world_sha256": world_uv1.get("sha256"), "ego_world_sha256": ego_uv1.get("world_sha256")}
        for variant, suffix, contract_name, _ in VARIANTS:
            phase = time.perf_counter()
            asset = tool["asset"] + suffix
            model = asset + "_Game"
            maps, raster, channels, slots, key_parts, settings, layout, timings = bake_model(work, model, asset, variant,
                                                                                             palette)
            names = surface.map_names(model)
            files, set_bytes = {}, 0
            for kind in surface.MAP_KINDS:
                data = surface.png_encode(maps[kind][::-1])
                (work / names[kind.lower()]).write_bytes(data)
                files[names[kind.lower()]] = surface.digest(data)
                set_bytes += len(data)
            values = surface.map_checks(maps, raster, channels, set_bytes)
            layout_errors = surface.layout_errors(layout)
            errors = surface.map_errors(values) + layout_errors
            key = surface.digest(key_parts, surface.model_channel_map(palette, slots), settings, bpy.app.version_string)
            clips = [model + "_Clips.fbx", model + "_Clips.glb"] if (work / (model + "_Clips.fbx")).exists() else []
            contract_path = work / contract_name
            contract = json.loads(contract_path.read_text())
            contract["surface"] = surface_block(model, variant, palette, slots, settings, files, set_bytes, key, layout,
                                                shared, "Cube Escape 0.71 (mask mode of the PAINT recipe)", clips)
            contract_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n")
            report["checks"][f"maps_{variant}"] = {"passed": not errors, "errors": errors, "model": model, **values,
                                                    "channels": channels, "seconds": round(time.perf_counter() - phase, 3),
                                                    "bake_seconds": {k: round(v, 3) for k, v in timings.items()}}
            report["checks"][f"uv1_{variant}"] = {"passed": not layout_errors, **layout}
    except Exception as error:  # noqa: BLE001 - reported as a failed QA with exit code 1
        traceback.print_exc()
        report["checks"]["surface_bake"] = {"passed": False, "error": f"{type(error).__name__}: {error}"}
    report["passed"] = bool(report["checks"]) and all(check["passed"] for check in report["checks"].values())
    report["seconds"] = round(time.perf_counter() - started, 3)
    (work / "qa_surface.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    failed = [name for name, check in report["checks"].items() if not check["passed"]]
    if failed:
        print(f"SURFACE_BAKE_FAILED {args.tool}: {', '.join(failed)}", flush=True)
        sys.exit(1)
    print(f"SURFACE_BAKE_OK {args.tool}: {report['seconds']:.1f}s", flush=True)


if __name__ == "__main__":
    main()
