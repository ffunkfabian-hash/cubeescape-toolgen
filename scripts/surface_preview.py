#!/usr/bin/env python3
"""Look check of the surface maps without Unity (Toolgen 0.13 Enamel): per weapon with a recipe one sheet
``<output>/Previews/surface_<tool>.png`` and a contact sheet ``surface_contact.png`` of all of them.

    blender --background --factory-startup --python scripts/surface_preview.py -- <output> [--tool pistol ...]

A sheet shows the world model from the side the decals face (+x) and at three quarters, the first-person view through the
viewmodel camera, and per model (world, Ego) the regions colour-coded, Fields (AO, edge, up) and the normal map. The renders
use a preview material that only imitates Cube Escape's mask mode: the sheet's palette per channel from data/
surface_recipes.json, wear on the convex edges (Fields G x wear amount), AO, the normal map on UV1 and the glow. Preview only:
the game's shader, its noise and its finish rules decide the real look (Eevee, not deterministic, not part of any contract).

0.23 (Livery): a weapon built from a concept sheet is shown in the sheet's default palette (surface.recipe.palettes, ``base``)
and gets ``surface_palettes_<tool>.png``: the world model from +x in each of the sheet's palettes and the robot variant.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
import decals  # noqa: E402
import surface  # noqa: E402
import surface_relief  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
import weapon_designs  # noqa: E402

REGION_COLOURS = {"Primary": (225, 225, 225), "Secondary": (70, 80, 95), "Accent": (240, 140, 40), "Metal": (150, 165, 185),
                  "Detail": (30, 30, 30), "Energy": (60, 200, 255), "Emission": (255, 60, 200)}
METAL_COLOUR = "#8D939C"
RUBBER_COLOUR = "#24272C"
BARE_METAL = "#B9BEC6"
DIRT = "#3A332B"
HAND_COLOUR = "#9AA0A8"
ORDER = ("Primary", "Secondary", "Accent", "Metal", "Detail", "Energy", "Emission")   # W0.rgb, W1.rgb, W0.a
SOURCES = {"Primary": ("W0", 0), "Secondary": ("W0", 1), "Accent": ("W0", 2), "Metal": ("W1", 0), "Detail": ("W1", 1),
           "Energy": ("W1", 2), "Emission": ("W0", 3)}
METALLIC = {"brushed": .55, "satin": .5, "polished": .7, "rough_cast": .45}


def linear(colour):
    value = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in value) + (1.0,)


def channel_colours(recipe, sheet_palette=None):
    palette = recipe["palette"]
    colours = {"Primary": palette[0], "Secondary": palette[1], "Accent": palette[2], "Metal": METAL_COLOUR,
               "Detail": RUBBER_COLOUR, "Energy": recipe["glow"]["color"], "Emission": recipe["glow"]["color"]}
    if sheet_palette:                    # 0.23: a concept sheet's palette (channels it leaves free keep the colours above)
        colours.update({channel: colour for channel, colour in sheet_palette["channels"].items() if colour})
    return colours


def preview_material(model_folder, model, recipe, levels, sheet_palette=None):
    material = bpy.data.materials.new("SurfacePreview")
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs[0], output.inputs["Surface"])
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = surface.UV1_NAME
    textures = {}
    for kind in surface.MAP_KINDS:
        node = nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(str(model_folder / f"{model}_{kind}.png"))
        node.image.colorspace_settings.name = "Non-Color"
        node.image.alpha_mode = "CHANNEL_PACKED"
        node.extension = "EXTEND"
        links.new(uv.outputs["UV"], node.inputs["Vector"])
        textures[kind] = node
    split = {}
    for kind in ("W0", "W1", "Fields"):
        separate = nodes.new("ShaderNodeSeparateColor")
        links.new(textures[kind].outputs["Color"], separate.inputs[0])
        split[kind] = [separate.outputs[i] for i in range(3)] + [textures[kind].outputs["Alpha"]]
    weight = {channel: split[kind][index] for channel, (kind, index) in SOURCES.items()}

    def mix_colour(a, b, factor):
        node = nodes.new("ShaderNodeMix")
        node.data_type = "RGBA"
        for socket, value in ((6, a), (7, b)):
            if isinstance(value, tuple):
                node.inputs[socket].default_value = value
            else:
                links.new(value, node.inputs[socket])
        if isinstance(factor, float):
            node.inputs[0].default_value = factor
        else:
            links.new(factor, node.inputs[0])
        return node.outputs[2]

    def mix_value(a, b, factor):
        node = nodes.new("ShaderNodeMix")
        node.data_type = "FLOAT"
        for socket, value in ((2, a), (3, b)):
            if isinstance(value, float):
                node.inputs[socket].default_value = value
            else:
                links.new(value, node.inputs[socket])
        links.new(factor, node.inputs[0])
        return node.outputs[0]

    def math(operation, a, b, clamp=False):
        node = nodes.new("ShaderNodeMath")
        node.operation, node.use_clamp = operation, clamp
        for socket, value in ((0, a), (1, b)):
            if isinstance(value, (int, float)):
                node.inputs[socket].default_value = value
            else:
                links.new(value, node.inputs[socket])
        return node.outputs[0]

    colours = channel_colours(recipe, sheet_palette)
    channels = recipe["channels"]
    colour, rough, metal, total = linear(HAND_COLOUR), .6, 0.0, None
    for channel in ORDER:
        colour = mix_colour(colour, linear(colours[channel]), weight[channel])
        rough = mix_value(rough, 1.0 - channels[channel]["smoothness"], weight[channel])
        metal = mix_value(metal, METALLIC.get(channels[channel]["material"], 0.0), weight[channel])
        total = weight[channel] if total is None else math("ADD", total, weight[channel])
    ao, edge = split["Fields"][0], split["Fields"][1]
    wear = levels[recipe["wear"]]
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 60.0
    noise.inputs["Detail"].default_value = 6.0
    links.new(uv.outputs["UV"], noise.inputs["Vector"])
    chipped = math("MULTIPLY", math("MULTIPLY", edge, 1.8 * wear), math("SUBTRACT", math("MULTIPLY", noise.outputs["Fac"], 2.2), .55),
                   clamp=True)
    painted = math("SUBTRACT", 1.0, math("ADD", math("ADD", weight["Metal"], weight["Energy"]), weight["Emission"]), clamp=True)
    colour = mix_colour(colour, linear(BARE_METAL), math("MULTIPLY", chipped, painted))
    metal = mix_value(metal, .6, math("MULTIPLY", chipped, painted))
    dirt = math("MULTIPLY", math("SUBTRACT", 1.0, ao), .9 * wear)
    colour = mix_colour(colour, linear(DIRT), dirt)
    shade = nodes.new("ShaderNodeMix")
    shade.data_type = "RGBA"
    shade.blend_type = "MULTIPLY"
    shade.inputs[0].default_value = 1.0
    links.new(colour, shade.inputs[6])
    occlusion = nodes.new("ShaderNodeMapRange")
    occlusion.inputs["To Min"].default_value = .35
    links.new(ao, occlusion.inputs["Value"])
    grey = nodes.new("ShaderNodeCombineColor")
    for i in range(3):
        links.new(occlusion.outputs["Result"], grey.inputs[i])
    links.new(grey.outputs[0], shade.inputs[7])
    links.new(shade.outputs[2], bsdf.inputs["Base Color"])
    links.new(rough, bsdf.inputs["Roughness"])
    links.new(metal, bsdf.inputs["Metallic"])
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.space = "TANGENT"
    normal_map.uv_map = surface.UV1_NAME
    links.new(textures["Normal"].outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
    glow = math("ADD", weight["Energy"], weight["Emission"])
    links.new(glow, bsdf.inputs["Emission Strength"])
    bsdf.inputs["Emission Color"].default_value = tuple(c * 1.6 for c in linear(colours["Emission"])[:3]) + (1.0,)
    return material


def scene_for(blend, root_name, make_material):
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    material = make_material()             # after loading: the file load frees every earlier datablock
    scene = bpy.context.scene
    scene.frame_set(scene.frame_start)
    root = scene.objects[root_name]
    keep = {root, *root.children_recursive}
    for obj in list(scene.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj)
    meshes = [obj for obj in keep if obj.type == "MESH"]
    for obj in meshes:
        obj.hide_render = obj.get("ce_lod") != 0
        for index in range(len(obj.data.materials)):
            obj.data.materials[index] = material
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (.06, .075, .1, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.2
    scene.world = world
    for rotation, energy in (((50, 10, 35), 3.0), ((60, 0, 200), 1.2)):
        light = bpy.data.objects.new("PreviewSun", bpy.data.lights.new("PreviewSun", "SUN"))
        light.data.energy = energy
        light.rotation_euler = tuple(math.radians(v) for v in rotation)
        scene.collection.objects.link(light)
    return scene, [obj for obj in meshes if not obj.hide_render]


def bounds(objects):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = [obj.matrix_world @ v.co for obj in objects for v in obj.evaluated_get(depsgraph).data.vertices]
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    return lo, hi


def render_view(scene, objects, direction, path, size=(960, 420), ortho=True):
    lo, hi = bounds(objects)
    centre, extent = (lo + hi) / 2, max(hi - lo)
    data = bpy.data.cameras.new("PreviewCamera")
    data.type = "ORTHO" if ortho else "PERSP"
    camera = bpy.data.objects.new("PreviewCamera", data)
    scene.collection.objects.link(camera)
    camera.location = centre + Vector(direction).normalized() * extent * 3
    camera.rotation_euler = (centre - camera.location).to_track_quat("-Z", "Y").to_euler()
    view = camera.rotation_euler.to_matrix().inverted()
    corners = [view @ (Vector((x, y, z)) - centre) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    width = max(c.x for c in corners) - min(c.x for c in corners)
    height = max(c.y for c in corners) - min(c.y for c in corners)
    data.ortho_scale = max(width, height * size[0] / size[1]) * 1.08
    if not ortho:
        data.lens = 50
        camera.location = centre + Vector(direction).normalized() * data.ortho_scale * 1.25
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def render_ego(scene, path, fov_degrees):
    data = bpy.data.cameras.new("EgoCamera")
    data.sensor_fit = "VERTICAL"
    data.angle_y = math.radians(fov_degrees)
    data.clip_start = .01
    camera = bpy.data.objects.new("EgoCamera", data)
    scene.collection.objects.link(camera)
    camera.rotation_euler = (math.radians(90), 0, math.radians(180))      # Socket_Camera: looking along -Y, up +Z
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def map_panels(model_folder, model, out_prefix):
    """Regions colour-coded, Fields RGB and Normal as 8-bit RGB PNGs (row 0 = top)."""
    maps = {kind: surface.png_array((model_folder / f"{model}_{kind}.png").read_bytes()) for kind in surface.MAP_KINDS}
    regions = np.zeros(maps["W0"].shape[:2] + (3,), dtype=np.float64)
    for channel, (kind, index) in SOURCES.items():
        regions += maps[kind][..., index:index + 1].astype(np.float64) / 255 * np.array(REGION_COLOURS[channel])
    paths = []
    for name, pixels in (("regions", np.clip(regions, 0, 255).astype(np.uint8)), ("fields", maps["Fields"][..., :3]),
                         ("normal", maps["Normal"][..., :3])):
        path = Path(f"{out_prefix}_{name}.png")
        path.write_bytes(surface.png_encode(np.ascontiguousarray(pixels)))
        paths.append(path)
    return paths


def palette_sheet(folder, tool_id, tool, recipe, levels, palettes, previews, scratch, magick):
    """0.23: ``surface_palettes_<tool>.png`` (1280 px wide) - the world model from +x in every palette of the concept sheet
    (two per row), below the robot variant in the default palette from both sides; returns its path."""
    asset, tiles = tool["asset"], []
    for item in palettes:
        scene, objects = scene_for(folder / f"{asset}_Game.blend", asset,
                                   lambda: preview_material(folder, f"{asset}_Game", recipe, levels, item))
        tile = scratch / f"{tool_id}_palette_{item['id']}.png"
        render_view(scene, objects, (1, 0, 0), tile, size=(640, 280))
        subprocess.run(magick + [str(tile), "-gravity", "NorthWest", "-fill", "#e8e8e8", "-pointsize", "18", "-annotate",
                                 "+10+8", f"{item['id']}  {item['name']}", str(tile)], check=True)
        tiles.append(tile)
    robot = tool.get("robot")
    if robot and (folder / f"{robot}_Game_W0.png").exists():
        for side, direction in (("plus", (1, 0, 0)), ("minus", (-1, 0, 0))):
            scene, objects = scene_for(folder / f"{robot}_Game.blend", robot,
                                       lambda: preview_material(folder, f"{robot}_Game", recipe, levels, palettes[0]))
            tile = scratch / f"{tool_id}_robot_{side}.png"
            render_view(scene, objects, direction, tile, size=(640, 280))
            subprocess.run(magick + [str(tile), "-gravity", "NorthWest", "-fill", "#e8e8e8", "-pointsize", "18", "-annotate",
                                     "+10+8", f"robot variant {'+x' if side == 'plus' else '-x'}  {palettes[0]['id']}",
                                     str(tile)], check=True)
            tiles.append(tile)
    rows = [tiles[i:i + 2] for i in range(0, len(tiles), 2)]
    sheet = previews / f"surface_palettes_{tool_id}.png"
    command = magick[:]
    for row in rows:
        command += ["(", *[str(t) for t in row], "+append", ")"]
    subprocess.run(command + ["-append", "-gravity", "North", "-background", "#10131a", "-splice", "0x30", "-fill", "#e8e8e8",
                              "-pointsize", "20", "-annotate", "+0+5",
                              f"{tool_id}: sheet palettes and regions - Toolgen preview (not the game shader)",
                              "-define", "png:exclude-chunks=date,time", str(sheet)], check=True)
    print(f"SURFACE_PREVIEW_OK {tool_id} palettes: {sheet}")
    return sheet


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    output = Path(argv[0]).resolve()
    wanted = [argv[i + 1] for i, value in enumerate(argv) if value == "--tool"]
    recipes = surface_relief.load()
    tools = {entry["id"]: entry for entry in json.loads((ROOT / "data/tools.json").read_text())["tools"]}
    previews = output / "Previews"
    scratch = previews / "_parts"
    scratch.mkdir(parents=True, exist_ok=True)
    magick = decals.magick_command()
    sheets = []
    for tool_id, recipe in recipes["weapons"].items():
        if wanted and tool_id not in wanted:
            continue
        folder, asset = output / tool_id, tools[tool_id]["asset"]
        if not (folder / f"{asset}_Game_W0.png").exists():
            print(f"SURFACE_PREVIEW_SKIP {tool_id}: no maps (standard or full tier)")
            continue
        levels = recipes["limits"]["wear_levels"]
        palettes = weapon_designs.palettes(tool_id)
        default = surface_relief.default_palette(palettes, recipe) if palettes else None
        if palettes:
            sheets.append(palette_sheet(folder, tool_id, tools[tool_id], recipe, levels, palettes, previews, scratch, magick))
        scene, objects = scene_for(folder / f"{asset}_Game.blend", asset,
                                   lambda: preview_material(folder, f"{asset}_Game", recipe, levels, default))
        render_view(scene, objects, (1, 0, 0), scratch / f"{tool_id}_side.png")
        render_view(scene, objects, (1, -1.1, .6), scratch / f"{tool_id}_quarter.png", ortho=False)
        camera = json.loads((folder / "viewmodel_camera.json").read_text())
        scene, objects = scene_for(folder / f"{asset}_FPS_Game.blend", f"{asset}_FPS",
                                   lambda: preview_material(folder, f"{asset}_FPS_Game", recipe, levels, default))
        if json.loads((folder / "unity_contract_fps.json").read_text()).get("format", 4) >= 5:
            # contract 5 (0.19): the device hangs without arms at its own origin, the viewmodel camera sits in the rig's
            # space - show the first-person model (its own maps) at three quarters instead (0.23)
            render_view(scene, objects, (1, -1.1, .6), scratch / f"{tool_id}_ego.png", size=(640, 360), ortho=False)
        else:
            render_ego(scene, scratch / f"{tool_id}_ego.png", camera["vertical_fov_degrees"])
        world_maps = map_panels(folder, f"{asset}_Game", scratch / f"{tool_id}_world")
        ego_maps = map_panels(folder, f"{asset}_FPS_Game", scratch / f"{tool_id}_ego")
        title = f"{recipe['sheet']}  {recipe['title']}  -  Toolgen surface preview (not the game shader)"
        sheet = previews / f"surface_{tool_id}.png"
        subprocess.run(magick + [
            "(", str(scratch / f"{tool_id}_side.png"), str(scratch / f"{tool_id}_quarter.png"), "+append", ")",
            "(", str(scratch / f"{tool_id}_ego.png"), "-gravity", "SouthEast", "-crop", "640x360+0+0", "+repage",
            "-resize", "960x540", "-gravity", "NorthWest",
            "(", "(", *[str(p) for p in world_maps], "-resize", "320x320", "+append", ")",
            "(", *[str(p) for p in ego_maps], "-resize", "320x320", "+append", ")", "-append", "-resize", "960x540!", ")",
            "+append", ")", "-append",
            "-gravity", "North", "-background", "#10131a", "-splice", "0x34", "-fill", "#e8e8e8", "-pointsize", "22",
            "-annotate", "+0+6", title, "-define", "png:exclude-chunks=date,time", str(sheet)], check=True)
        sheets.append(sheet)
        print(f"SURFACE_PREVIEW_OK {tool_id}: {sheet}")
    if sheets and not wanted:
        contact = previews / "surface_contact.png"
        subprocess.run(magick + ["montage", *[str(s) for s in sheets], "-tile", "3x", "-geometry", "640x+6+6",
                                 "-background", "#10131a", "-define", "png:exclude-chunks=date,time", str(contact)]
                       if Path(magick[0]).name.startswith("magick") else
                       ["montage", *[str(s) for s in sheets], "-tile", "3x", "-geometry", "640x+6+6", "-background", "#10131a",
                        str(contact)], check=True)
        print(f"SURFACE_PREVIEW_CONTACT {contact}")


if __name__ == "__main__":
    main()
