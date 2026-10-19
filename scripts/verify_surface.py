#!/usr/bin/env python3
"""Independently verify the exported contract-4 surface data of Toolgen packages."""
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
import surface  # noqa: E402 - toolgen/ is no package

COMPONENTS = {5126: ("f", 4), 5123: ("H", 2), 5125: ("I", 4)}
# MikkTSpace averages tangents per corner group, this check per vertex over its triangles: a few vertices on hard edges or
# next to zero-area UV triangles disagree (measured 94.4-100 % per primitive on UV1 (lowest: decimated LOD1 of the bow), 0-67 % on UV0).
TANGENT_PRIMITIVE_QUOTE = .9
TANGENT_MODEL_QUOTE = .98
TYPE_WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
# Golden maps of the weapons (Toolgen 0.13): sha256 of every map in manifest.json, no reference images (user, 17.10.2026).
# Every changed map fails until it is confirmed with --update-golden.
GOLDEN = ROOT / "tests/golden/surface"


def blender_executable():
    """Resolve Blender like the Toolgen command-line entry point."""
    for candidate in (os.environ.get("TOOLGEN_BLENDER"), os.environ.get("BLENDER_BIN"), shutil.which("blender"),
                      "/Applications/Blender.app/Contents/MacOS/Blender"):
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise FileNotFoundError("Blender was not found; set TOOLGEN_BLENDER or BLENDER_BIN")


def read_glb(path):
    """Return the glTF JSON document and its BIN chunk."""
    data = Path(path).read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or length != len(data):
        raise ValueError(f"invalid GLB header: {path}")
    offset, document, binary = 12, None, b""
    while offset < length:
        size, kind = struct.unpack_from("<I4s", data, offset)
        chunk = data[offset + 8:offset + 8 + size]
        if kind == b"JSON":
            document = json.loads(chunk.decode("utf-8").rstrip(" \0"))
        elif kind == b"BIN\0":
            binary = chunk
        offset += 8 + size
    if document is None:
        raise ValueError("GLB has no JSON chunk")
    return document, binary


def accessor(document, binary, index):
    """Decode FLOAT, UNSIGNED_SHORT, or UNSIGNED_INT accessor values with byteStride support."""
    item = document["accessors"][index]
    view = document["bufferViews"][item["bufferView"]]
    component, size = COMPONENTS[item["componentType"]]
    width = TYPE_WIDTH[item["type"]]
    stride = view.get("byteStride", size * width)
    start = view.get("byteOffset", 0) + item.get("byteOffset", 0)
    fmt = "<" + component * width
    result = np.empty((item["count"], width), dtype={"f": np.float32, "H": np.uint16, "I": np.uint32}[component])
    for row in range(item["count"]):
        result[row] = struct.unpack_from(fmt, binary, start + row * stride)
    return result[:, 0] if width == 1 else result


def primitive_rows(document, binary, lod0_only=False):
    """Yield primitive arrays and material/node names, resolving node mesh names."""
    mesh_names = [mesh.get("name", f"mesh_{i}") for i, mesh in enumerate(document.get("meshes", []))]
    node_names = {}
    for node in document.get("nodes", []):
        if "mesh" in node:
            node_names.setdefault(node["mesh"], []).append(node.get("name", ""))
    materials = [m.get("name", f"material_{i}") for i, m in enumerate(document.get("materials", []))]
    for mesh_index, mesh in enumerate(document.get("meshes", [])):
        names = [mesh_names[mesh_index], *node_names.get(mesh_index, [])]
        lod0 = any(name.endswith("_LOD0") for name in names)
        if lod0_only and not lod0:
            continue
        for primitive in mesh.get("primitives", []):
            attrs = primitive["attributes"]
            arrays = {name: accessor(document, binary, attrs[name]) for name in ("POSITION", "NORMAL", "TANGENT", "TEXCOORD_0", "TEXCOORD_1") if name in attrs}
            indices = accessor(document, binary, primitive["indices"])
            if primitive.get("mode", 4) != 4:
                raise ValueError("surface verifier accepts triangle primitives only")
            triangles = np.asarray(indices, dtype=np.int64).reshape(-1, 3)
            yield {"name": names[0], "lod0": lod0, "arrays": arrays, "indices": triangles,
                   "material": materials[primitive.get("material", -1)] if primitive.get("material", -1) >= 0 else ""}


def tangent_scores(position, normal, tangent, uv, triangles):
    """Per-vertex proportion with UV-derived dP/du aligned to tangent.xyz."""
    sums = np.zeros_like(position, dtype=np.float64)
    counts = np.zeros(len(position), dtype=np.int64)
    for tri in triangles:
        p, t = position[tri], uv[tri]
        duv1, duv2 = t[1] - t[0], t[2] - t[0]
        determinant = duv1[0] * duv2[1] - duv1[1] * duv2[0]
        if abs(determinant) < 1e-12:
            continue
        direction = ((p[1] - p[0]) * duv2[1] - (p[2] - p[0]) * duv1[1]) / determinant
        for vertex in tri:
            sums[vertex] += direction
            counts[vertex] += 1
    useful = counts > 0
    direction = sums[useful]
    n = normal[useful].astype(np.float64)
    direction -= n * np.sum(direction * n, axis=1, keepdims=True)
    length = np.linalg.norm(direction, axis=1)
    valid = length > 1e-10
    direction = direction[valid] / length[valid, None]
    t = tangent[useful][valid, :3].astype(np.float64)
    tlen = np.linalg.norm(t, axis=1)
    valid_t = tlen > 1e-10
    dots = np.sum(direction[valid_t] * (t[valid_t] / tlen[valid_t, None]), axis=1)
    return {"vertices": int(len(dots)), "aligned": int(np.count_nonzero(dots > .9)),
            "quote": float(np.mean(dots > .9)) if len(dots) else 0.0,
            "mean_dot": float(np.mean(dots)) if len(dots) else 0.0}


def tangent_check(document, binary, name):
    rows = list(primitive_rows(document, binary))
    out = {"file": name, "primitives": len(rows), "uv0_quote": [], "uv1_quote": [], "errors": []}
    for row in rows:
        a, idx = row["arrays"], row["indices"]
        missing = [key for key in ("POSITION", "NORMAL", "TANGENT", "TEXCOORD_0", "TEXCOORD_1") if key not in a]
        if missing:
            out["errors"].append(f"{row['name']}: missing {', '.join(missing)}")
            continue
        if idx.size == 0:
            out["errors"].append(f"{row['name']}: no indices")
            continue
        if np.any(a["TEXCOORD_1"] < -1e-6) or np.any(a["TEXCOORD_1"] > 1 + 1e-6):
            out["errors"].append(f"{row['name']}: TEXCOORD_1 outside 0..1")
        for uv_name, dest in (("TEXCOORD_0", "uv0_quote"), ("TEXCOORD_1", "uv1_quote")):
            score = tangent_scores(a["POSITION"], a["NORMAL"], a["TANGENT"], a[uv_name], idx)
            out[dest].append(score)
            if uv_name == "TEXCOORD_1" and score["vertices"] and score["quote"] < TANGENT_PRIMITIVE_QUOTE:
                out["errors"].append(f"{row['name']}: UV1 tangent alignment {score['quote']:.5f} < {TANGENT_PRIMITIVE_QUOTE}")
    vertices = sum(score["vertices"] for score in out["uv1_quote"])
    aligned = sum(score["aligned"] for score in out["uv1_quote"])
    out["uv1_model_quote"] = aligned / vertices if vertices else 0.0
    out["uv0_model_quote"] = (sum(score["aligned"] for score in out["uv0_quote"])
                              / max(1, sum(score["vertices"] for score in out["uv0_quote"])))
    if vertices and out["uv1_model_quote"] < TANGENT_MODEL_QUOTE:
        out["errors"].append(f"UV1 tangent alignment {out['uv1_model_quote']:.5f} < {TANGENT_MODEL_QUOTE} over the model")
    return out


def glb_layout_map(document, binary, block, model):
    rows = list(primitive_rows(document, binary, lod0_only=True))
    # glTF splits vertices at UV0 seams, hard normals and material borders: join corners by position over the whole model
    positions = np.concatenate([row["arrays"]["POSITION"] for row in rows]).astype(np.float64)
    _, welded = np.unique(np.round(positions, 6), axis=0, return_inverse=True)
    welded = welded.reshape(-1)
    faces, uvs, tri_values, labels = [], [], [], []
    vertex_base = 0
    channel_map = block["channel_map"]
    channel_index = {name: index for index, name in enumerate(surface.CHANNELS)}
    for row in rows:
        a, tri = row["arrays"], row["indices"]
        if "TEXCOORD_1" not in a:
            continue
        uv = a["TEXCOORD_1"].astype(np.float64).copy()
        uv[:, 1] = 1.0 - uv[:, 1]
        faces.extend(welded[tri + vertex_base].tolist())
        uvs.extend(uv[tri].tolist())
        tri_values.extend(uv[tri])
        labels.extend([channel_index.get(channel_map.get(row["material"]), -1)] * len(tri))
        vertex_base += len(a["POSITION"])
    if not tri_values:
        raise ValueError(f"{model}: no LOD0 UV1 triangles found")
    tri_values = np.asarray(tri_values, dtype=np.float64)
    face_array = np.asarray(faces, dtype=np.int64)
    uv_faces = np.asarray(uvs, dtype=np.float64)
    # Vertex ids are globalized per mesh; UV corner values retain exact glTF seams.
    islands = np.asarray(surface.island_ids(face_array, uv_faces))
    unpainted = np.all(tri_values == 0, axis=(1, 2))
    layout = surface.layout_report(tri_values, islands, unpainted)
    errors = surface.layout_errors(layout)
    resolution = int(block["maps"]["resolution"])
    counts = np.zeros((resolution, resolution), dtype=np.int32)
    channels = np.asarray(labels, dtype=np.int32)
    raster = surface.rasterize(tri_values[~unpainted & (channels >= 0)], channels[~unpainted & (channels >= 0)],
                               resolution, counts=counts)
    return layout, errors, raster, counts, channels, tri_values, unpainted


REACH_EPSILON = 1e-5   # edge tolerance of the re-rasterisation that bounds the dilation: the GLB holds float32 UV1 (measured 0.16: 1e-7 misses
                       # one edge texel the bake covers at 2048, 1e-5 covers it and adds only a few texels)


def map_validate(folder, block, raster, counts, labels, reach_raster=None):
    maps_info = block["maps"]
    decoded, hashes, total_bytes, errors = {}, {}, 0, []
    for key in ("w0", "w1", "fields", "normal"):
        path = folder / maps_info[key]
        data = path.read_bytes()
        total_bytes += len(data)
        hashes[path.name] = hashlib.sha256(data).hexdigest()
        info = surface.png_info(data)
        if (info["bit_depth"], info["color_type"], info["width"], info["height"], info["chunks"]) != (8, 6, maps_info["resolution"], maps_info["resolution"], ["IHDR", "IDAT", "IEND"]):
            errors.append(f"{path.name}: invalid PNG format/header {info}")
        decoded[key.upper() if key in ("w0", "w1") else key.title()] = surface.png_array(data)[::-1].copy()
    if total_bytes != maps_info.get("set_bytes"):
        errors.append(f"map set bytes {total_bytes} != contract {maps_info.get('set_bytes')}")
    limit = surface.set_bytes_limit(maps_info["resolution"])
    if total_bytes > limit:
        errors.append(f"map set {total_bytes} > {limit}")
    if maps_info.get("dilation_px") != surface.dilation_at(maps_info["resolution"]):
        errors.append(f"dilation_px {maps_info.get('dilation_px')} != {surface.dilation_at(maps_info['resolution'])} at {maps_info['resolution']}")
    expected_files = maps_info.get("files", {})
    for name, digest in hashes.items():
        if expected_files.get(name) != digest:
            errors.append(f"{name}: sha256 differs from contract")
    targets = np.zeros((len(surface.CHANNELS), 2), dtype=np.int64)
    for i, channel in enumerate(surface.CHANNELS):
        kind, component = surface.TARGETS[channel]
        targets[i] = (0 if kind == "W0" else 1, component)
    observed = np.zeros((len(surface.CHANNELS),), dtype=np.int64)
    unique = (counts == 1) & (raster >= 0)
    pixels = np.stack([decoded["W0"][..., surface.TARGETS[c][1]] if surface.TARGETS[c][0] == "W0"
                       else decoded["W1"][..., surface.TARGETS[c][1]] for c in surface.CHANNELS], axis=2)
    mismatch = np.zeros_like(unique)
    for channel in range(len(surface.CHANNELS)):
        own = (raster == channel) & unique
        mismatch |= own & (pixels[..., channel] != 255)
        for other in range(len(surface.CHANNELS)):
            if other != channel:
                mismatch |= own & (pixels[..., other] != 0)
    # Decals (Toolgen 0.13, surface.recipe.decals): their texels carry the decal's channel instead of the slot's; they
    # count apart, up to the number the bake declared, and only in the decal channels.
    # The bake's QA (qa_surface.json design_*) checks part, island and area; here each decal channel has its own budget.
    decal_list = block.get("recipe", {}).get("decals", [])
    budgets = {}
    for entry in decal_list:
        index = surface.CHANNELS.index(entry["channel"])
        budgets[index] = budgets.get(index, 0) + int(entry.get("texels", 0))
    declared = sum(budgets.values())
    decal_texels = 0
    if budgets:
        hot = np.argmax(pixels, axis=2)
        clean = (pixels.max(axis=2) == 255) & ((pixels == 255).sum(axis=2) == 1)
        for index, budget in sorted(budgets.items()):
            as_decal = mismatch & (hot == index) & clean
            count = int(as_decal.sum())
            if count > budget:
                errors.append(f"decal texels in {surface.CHANNELS[index]} {count} > declared {budget}")
            decal_texels += count
            mismatch &= ~as_decal
    denominator = int(unique.sum())
    mismatch_count = int(mismatch.sum())
    ratio = mismatch_count / denominator if denominator else 0.0
    if ratio > .001:
        errors.append(f"one-hot raster mismatches {mismatch_count}/{denominator} ({ratio:.4%}) > 0.1%")
    values = surface.map_checks(decoded, raster, sorted({surface.CHANNELS[i] for i in set(labels.tolist()) if i >= 0}),
                                total_bytes, maps_info.get("dilation_px"), reach_raster)
    errors.extend(surface.map_errors(values))
    return {"bytes": total_bytes, "unique_texels": denominator, "mismatches": mismatch_count, "decal_texels": decal_texels,
            "decal_texels_declared": declared,
            "mismatch_ratio": ratio, "hashes": hashes, "map_checks": values, "errors": errors}


def blender_import_check(path, kind):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    if kind == "fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    errors = [f"{obj.name}: only {len(obj.data.uv_layers)} UV layers" for obj in meshes if len(obj.data.uv_layers) < 2]
    return {"meshes": len(meshes), "errors": errors}


def verify_model(folder, contract_path, clip=False):
    contract = json.loads(contract_path.read_text())
    block, model, asset = contract["surface"], contract["model"], contract["asset"]
    glb_path = folder / (model + ".glb")
    doc, binary = read_glb(glb_path)
    tangent = tangent_check(doc, binary, glb_path.name)
    errors = list(tangent["errors"])
    if not clip:
        layout, layout_errors, raster, counts, labels, tri_values, unpainted_mask = glb_layout_map(doc, binary, block, model)
        errors.extend(layout_errors)
        painted = labels[~unpainted_mask]
        use = ~unpainted_mask & (labels >= 0)
        loose = surface.rasterize(tri_values[use], labels[use], int(block["maps"]["resolution"]), epsilon=REACH_EPSILON)
        maps = map_validate(folder, block, raster, counts, painted, loose)
        errors.extend(maps["errors"])
    else:
        layout, maps = None, None
    result = {"model": model, "asset": asset, "tangent": tangent, "layout": layout, "maps": maps, "errors": errors}
    for suffix in (".fbx", ".glb"):
        path = folder / (model + suffix)
        imported = blender_import_check(path, suffix[1:])
        result[suffix[1:] + "_import"] = imported
        result["errors"].extend(imported["errors"])
    clips = model + "_Clips.glb"
    if (folder / clips).exists():
        cdoc, cbin = read_glb(folder / clips)
        clip_check = tangent_check(cdoc, cbin, clips)
        result["clip_tangent"] = clip_check
        result["errors"].extend(clip_check["errors"])
    return result


def determinism(folder, tool):
    # the bake also reads the source models (part labels of relief and decals, Toolgen 0.13)
    names = [p.name for p in folder.iterdir() if p.name.endswith(".blend") or p.name.endswith("_Game_Clips.fbx")
             or p.name.startswith("unity_contract") and p.suffix == ".json" or p.name.startswith("qa_game") and p.suffix == ".json"]
    with tempfile.TemporaryDirectory(prefix="verify_surface_") as temp:
        work = Path(temp)
        for name in names:
            shutil.copy2(folder / name, work / name)
        hashes = []
        for threads in (1, 8):
            env = os.environ.copy()
            env["TOOLGEN_THREADS"] = str(threads)
            command = [blender_executable(), "--background", "--factory-startup", "--threads", str(threads),
                       "--python-exit-code", "1", "--python", str(ROOT / "toolgen/run_asset.py"), "--",
                       "--script", str(ROOT / "toolgen/surface_bake.py"), "--directory", str(work), "--tool", tool]
            subprocess.run(command, cwd=ROOT, env=env, check=True)
            if (work / "unity_contract_robot.json").exists():      # the robot variant's maps (Toolgen 0.14)
                subprocess.run([*command, "--robot"], cwd=ROOT, env=env, check=True)
            hashes.append({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in work.glob("*_W*.png")}
                          | {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in work.glob("*_Fields.png")}
                          | {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in work.glob("*_Normal.png")})
        original = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob("*_W*.png")}
        original |= {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob("*_Fields.png")}
        original |= {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob("*_Normal.png")}
        return {"thread_hashes": hashes, "matches_original": hashes[0] == original and hashes[1] == original,
                "matches_each_other": hashes[0] == hashes[1]}


def golden_stale(manifest, tool, name):
    """Is the golden hash of the map marked stale (``manifest["stale"]["maps"]``: known to be outdated, e.g. Toolgen 0.16 first-person
    maps at 2048 until the Mac bake confirms them)? A stale map fails until ``--update-golden`` rewrites it."""
    return name in manifest.get("stale", {}).get("maps", {}).get(tool, [])


def golden_accepts(manifest, tool, name, digest):
    """Is ``digest`` a golden hash of the map: the primary one or a confirmed alternate (``manifest["alternates"]``)?"""
    return digest == manifest["maps"].get(tool, {}).get(name) or digest in manifest.get("alternates", {}).get(tool, {}).get(name, [])


def golden_update(manifest, tool, digests):
    """New golden entries of one tool from ``digests`` {map: sha256}. A map whose new hash is its old primary or an old
    alternate keeps its alternates (the old primary joins them: the bake flips between known values); a map with new
    content drops them, so a stale alternate never masks a later change."""
    old = manifest["maps"].get(tool, {})
    alternates = manifest.setdefault("alternates", {})
    kept = {}
    for name, digest in digests.items():
        known = [old[name]] if name in old else []
        known += alternates.get(tool, {}).get(name, [])
        if digest in known:
            others = sorted({value for value in known if value != digest})
            if others:
                kept[name] = others
    manifest["maps"][tool] = dict(digests)
    if kept:
        alternates[tool] = kept
    else:
        alternates.pop(tool, None)
    stale = manifest.get("stale", {}).get("maps", {})
    if tool in stale:
        remaining = [name for name in stale[tool] if name not in digests]
        if remaining:
            stale[tool] = remaining
        else:
            stale.pop(tool)
        if not stale:
            manifest.pop("stale", None)


def golden_check(output, tools, update=False):
    """Compare (or with ``update`` rewrite) the weapons' maps against tests/golden/surface. A map may also match one of its
    confirmed alternates (``alternates``, Toolgen 0.15.1): two robot normal maps flip one texel by one step between bakes."""
    manifest_path = GOLDEN / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"maps": {}}
    errors, compared, alternate = [], 0, []
    for tool in tools:
        folder = output / tool
        files = sorted(folder.glob("*_Game_*.png"))
        if not files:
            continue
        if update:
            golden_update(manifest, tool, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
            continue
        if tool not in manifest["maps"]:
            errors.append(f"{tool}: no golden maps")
            continue
        for path in files:
            compared += 1
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if golden_stale(manifest, tool, path.name):
                errors.append(f"{tool}/{path.name}: golden is stale ({manifest['stale'].get('note', 'rebake pending')}); confirm "
                              "the new bake with --update-golden")
            elif not golden_accepts(manifest, tool, path.name, digest):
                errors.append(f"{tool}/{path.name}: sha256 differs from the golden (confirm a deliberate change with "
                              "--update-golden)")
            elif digest != manifest["maps"][tool].get(path.name):
                alternate.append(f"{tool}/{path.name}")
    if update:
        manifest["note"] = ("Golden surface maps of the weapons (Toolgen 0.13 Enamel; the robot variants' <Asset>_Robot_Game_* "
                            "maps since 0.14 Fieldfit; baked on the Mac, standard tier): sha256 "
                            "of every map, no reference images. Rewrite with verify_surface.py "
                            "--update-golden after a deliberate change.")
        manifest["alternates_note"] = ("Confirmed alternate sha256 per map (Toolgen 0.15.1): the Cycles normal bake of the robot "
                                       "variants flips one texel by one step (trace and sniper rifle between runs of the same "
                                       "input, any thread count; measured 18.10.2026: 1 of 3 runs; SMG with the version string "
                                       "alone, 0.17.0: v0.16.0 sources with version.py 0.17.0 bake the alternate, three of three "
                                       "runs). Only flips seen in a bake of unchanged geometry belong here; a map with new "
                                       "content drops them.")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    stale = sum(len(names) for names in manifest.get("stale", {}).get("maps", {}).values())
    return {"compared": compared, "errors": errors, "alternate_matches": alternate, "stale": stale}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tool", action="append", default=[])
    parser.add_argument("--determinism", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--update-golden", action="store_true", help="rewrite tests/golden/surface from this output")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    output = args.output.resolve()
    packages = sorted(p for p in output.iterdir() if p.is_dir() and (p / "manifest.json").exists())
    if args.tool:
        packages = [p for p in packages if p.name in args.tool]
    report = {"output": str(output), "tools": [], "passed": True}
    checks = 0
    for folder in packages:
        tool_started = time.perf_counter()
        manifest = json.loads((folder / "manifest.json").read_text())
        if not manifest.get("surface", {}).get("included"):
            continue
        item = {"tool": folder.name, "models": [], "errors": []}
        contracts = ["unity_contract.json", "unity_contract_fps.json"]
        if (folder / "unity_contract_robot.json").exists():
            contracts.append("unity_contract_robot.json")             # robot variant (Toolgen 0.14)
        for contract_name in contracts:
            model = verify_model(folder, folder / contract_name)
            checks += 1
            item["models"].append(model)
            item["errors"].extend(f"{model['model']}: {e}" for e in model["errors"])
            for key in ("tangent", "layout", "maps", "fbx_import", "glb_import", "clip_tangent"):
                value = model.get(key)
                if value is None:
                    continue
                failure = value.get("errors", []) if isinstance(value, dict) else []
                print(f"{'PASS' if not failure else 'FAIL'} {folder.name}/{model['model']}/{key}")
            print(f"{'PASS' if not model['errors'] else 'FAIL'} {folder.name}/{model['model']} errors={len(model['errors'])}")
        if args.determinism:
            sys.path.insert(0, str(ROOT / "scripts"))
            import heavy_lock
            with heavy_lock.held("toolgen verify_surface", str(ROOT)):
                item["determinism"] = determinism(folder, folder.name)
            checks += 1
            if not item["determinism"]["matches_original"]:
                item["errors"].append("determinism hashes differ from package")
            print(f"{'PASS' if not item['errors'] else 'FAIL'} {folder.name}/determinism={item['determinism']['matches_original']}")
        report["tools"].append(item)
        item["seconds"] = round(time.perf_counter() - tool_started, 3)
        print(f"TIME {folder.name} {item['seconds']:.3f}s")
        report["passed"] &= not item["errors"]
    weapons = sorted(json.loads((ROOT / "data/surface_recipes.json").read_text())["weapons"])
    golden = golden_check(output, [p.name for p in packages if p.name in weapons], args.update_golden)
    report["golden"] = golden
    if golden["errors"]:
        report["passed"] = False
        report["tools"].append({"tool": "golden", "errors": golden["errors"]})
    print(f"{'PASS' if not golden['errors'] else 'FAIL'} golden maps compared={golden['compared']} "
          f"alternates={len(golden['alternate_matches'])} stale={golden['stale']}"
          f"{' (updated)' if args.update_golden else ''}")
    if args.report:
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if report["passed"]:
        print(f"SURFACE_ACCEPTANCE_OK {checks} checks")
        return 0
    failed = [f"{item['tool']}: {', '.join(item['errors'])}" for item in report["tools"] if item["errors"]]
    print("SURFACE_ACCEPTANCE_FAILED " + " | ".join(failed))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
