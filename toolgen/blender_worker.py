#!/usr/bin/env python3
"""Build, export, render, and measure the Blender source for a tool package."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


TOOLGEN_VERSION = "0.1.0"


def parse_arguments() -> argparse.Namespace:
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(arguments)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for material in list(bpy.data.materials):
        if material.users == 0:
            bpy.data.materials.remove(material)


def make_material(name: str, color: tuple[float, float, float, float], metallic: float = 0.0, emission: float = 0.0):
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = 0.36
    if emission > 0.0:
        shader.inputs["Emission Color"].default_value = color
        shader.inputs["Emission Strength"].default_value = emission
    return material


def apply_bevel(obj: bpy.types.Object, width: float) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    modifier = obj.modifiers.new("Edge bevel", "BEVEL")
    modifier.width = width
    modifier.segments = 1
    modifier.limit_method = "ANGLE"
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.select_set(False)


def add_box(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    material: bpy.types.Material,
    bevel: float = 0.008,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel > 0.0:
        apply_bevel(obj, bevel)
    return obj


def add_barrel(
    name: str,
    radius: float,
    depth: float,
    location: tuple[float, float, float],
    material: bpy.types.Material,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16,
        radius=radius,
        depth=depth,
        location=location,
        rotation=(math.radians(90.0), 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def add_socket(root: bpy.types.Object, name: str, position: list[float]) -> bpy.types.Object:
    socket = bpy.data.objects.new(name, None)
    socket.empty_display_type = "PLAIN_AXES"
    socket.empty_display_size = 0.04
    socket.location = position
    bpy.context.collection.objects.link(socket)
    socket.parent = root
    return socket


def build_portal_emitter(contract: dict) -> list[bpy.types.Object]:
    materials = {
        "dark": make_material("M_RobotDark", (0.075, 0.105, 0.14, 1.0), metallic=0.45),
        "white": make_material("M_White", (0.72, 0.79, 0.82, 1.0), metallic=0.2),
        "cyan": make_material("M_GlowCyan", (0.01, 0.72, 0.95, 1.0), metallic=0.1, emission=2.0),
    }
    root = bpy.data.objects.new(contract["unity_name"], None)
    root.empty_display_type = "CUBE"
    root.empty_display_size = 0.12
    bpy.context.collection.objects.link(root)

    parts = [
        add_box("Emitter_Body", (0.0, -0.355, 0.13), (0.30, 0.55, 0.24), materials["white"], 0.018),
        add_box("Emitter_Grip", (0.0, -0.02, -0.03), (0.16, 0.20, 0.30), materials["dark"], 0.012),
        add_box("Emitter_Rail", (0.0, -0.28, 0.29), (0.14, 0.29, 0.06), materials["dark"], 0.008),
        add_box("Emitter_Side_L", (-0.145, -0.35, 0.13), (0.025, 0.31, 0.14), materials["dark"], 0.004),
        add_box("Emitter_Side_R", (0.145, -0.35, 0.13), (0.025, 0.31, 0.14), materials["dark"], 0.004),
        add_barrel("Emitter_Barrel", 0.08, 0.18, (0.0, -0.68, 0.14), materials["dark"]),
        add_barrel("Emitter_Lens", 0.052, 0.008, (0.0, -0.774, 0.14), materials["cyan"]),
        add_box("Emitter_Trigger", (0.0, -0.08, -0.12), (0.08, 0.08, 0.10), materials["dark"], 0.006),
    ]
    for part in parts:
        part.parent = root

    sockets = (
        contract["hand_socket"],
        contract["muzzle_socket"],
        contract["support_hand_socket"],
        contract["fps_root"],
        contract["fps_hand_socket"],
    )
    for socket in sockets:
        add_socket(root, socket["name"], socket["position"])
    return [root, *parts, *(child for child in root.children if child.type == "EMPTY")]


def create_preview_scene() -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 960
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.world.color = (0.055, 0.07, 0.09)

    bpy.ops.object.camera_add(location=(1.25, -1.55, 1.15))
    camera = bpy.context.object
    camera.name = "Preview_Camera"
    camera.rotation_euler = (Vector((0.0, -0.36, 0.07)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 1.35
    scene.camera = camera

    for name, location, energy, size in (
        ("Key_Light", (2.0, -2.0, 3.0), 520.0, 3.0),
        ("Fill_Light", (-2.0, -0.5, 1.2), 260.0, 2.5),
    ):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.name = name
        light.data.energy = energy
        light.data.shape = "DISK"
        light.data.size = size
        light.rotation_euler = (Vector((0.0, -0.36, 0.07)) - light.location).to_track_quat("-Z", "Y").to_euler()

    scene.render.filepath = "//preview.png"


def geometry_metrics(mesh_objects: list[bpy.types.Object]) -> dict:
    coordinates: list[Vector] = []
    finite = True
    closed = True
    positive_volume = True
    valid_uvs = True
    total_volume = 0.0

    for obj in mesh_objects:
        mesh = obj.data
        if not mesh.uv_layers:
            valid_uvs = False
        elif any(not math.isfinite(value) for uv in mesh.uv_layers.active.data for value in uv.uv):
            valid_uvs = False

        bm = bmesh.new()
        bm.from_mesh(mesh)
        if any(not edge.is_manifold for edge in bm.edges):
            closed = False
        volume = bm.calc_volume(signed=True)
        if not math.isfinite(volume) or volume <= 0.0:
            positive_volume = False
        total_volume += volume
        bm.free()

        for vertex in mesh.vertices:
            point = obj.matrix_world @ vertex.co
            if not all(math.isfinite(value) for value in point):
                finite = False
            coordinates.append(point)

    mins = [min(point[axis] for point in coordinates) for axis in range(3)]
    maxs = [max(point[axis] for point in coordinates) for axis in range(3)]
    measured_size = [maxs[axis] - mins[axis] for axis in range(3)]
    measured_center = [(maxs[axis] + mins[axis]) / 2.0 for axis in range(3)]
    digest_source = []
    for obj in sorted(mesh_objects, key=lambda item: item.name):
        vertices = [
            tuple(round(float(value), 6) for value in (obj.matrix_world @ vertex.co))
            for vertex in obj.data.vertices
        ]
        faces = []
        for polygon in obj.data.polygons:
            points = [vertices[index] for index in polygon.vertices]
            rotations = [points[index:] + points[:index] for index in range(len(points))]
            canonical_points = min(rotations)
            material_index = polygon.material_index
            material_name = (
                obj.material_slots[material_index].material.name
                if material_index < len(obj.material_slots) and obj.material_slots[material_index].material is not None
                else ""
            )
            faces.append((material_name, canonical_points, bool(polygon.use_smooth)))
        digest_source.append(
            {
                "name": obj.name,
                "vertices": sorted(vertices),
                "faces": sorted(faces),
            }
        )
    canonical_geometry = json.dumps(digest_source, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return {
        "checks": {
            "mesh_closed": closed,
            "positive_volume": positive_volume and total_volume > 0.0,
            "finite_coordinates": finite,
            "uvs_valid": valid_uvs,
            "meter_scale": all(measured_size[axis] > 0.0 for axis in range(3)),
            "front_faces_negative_y": measured_center[1] < 0.0,
            "muzzle_in_front_of_grip": True,
        },
        "bounds_m": {"size": measured_size, "center": measured_center},
        "mesh_count": len(mesh_objects),
        "vertex_count": sum(len(obj.data.vertices) for obj in mesh_objects),
        "polygon_count": sum(len(obj.data.polygons) for obj in mesh_objects),
        "volume_m3": total_volume,
        "geometry_sha256": hashlib.sha256(canonical_geometry).hexdigest(),
    }


def validate_metrics(metrics: dict, contract: dict) -> None:
    bounds = contract["bounds_m"]
    for field in ("size", "center"):
        expected = bounds[field]
        measured = metrics["bounds_m"][field]
        if any(abs(actual - target) > 0.004 for actual, target in zip(measured, expected)):
            metrics["checks"]["meter_scale"] = False
    if metrics["bounds_m"]["center"][1] >= 0.0:
        metrics["checks"]["front_faces_negative_y"] = False
    muzzle_y = contract["muzzle_socket"]["position"][1]
    hand_y = contract["hand_socket"]["position"][1]
    if muzzle_y >= hand_y:
        metrics["checks"]["muzzle_in_front_of_grip"] = False
    failed = [name for name, passed in metrics["checks"].items() if not passed]
    if failed:
        raise RuntimeError(f"Geometry QA failed: {', '.join(failed)}")


def strip_png_text_metadata(path: Path) -> None:
    data = path.read_bytes()
    signature = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(signature):
        raise RuntimeError(f"Preview is not a PNG file: {path}")

    normalized = bytearray(signature)
    offset = len(signature)
    while offset < len(data):
        if offset + 12 > len(data):
            raise RuntimeError(f"Truncated PNG chunk in {path}")
        payload_length = int.from_bytes(data[offset : offset + 4], "big")
        end = offset + 12 + payload_length
        if end > len(data):
            raise RuntimeError(f"Invalid PNG chunk length in {path}")
        chunk_type = data[offset + 4 : offset + 8]
        if chunk_type not in {b"tEXt", b"zTXt", b"iTXt"}:
            normalized.extend(data[offset:end])
        offset = end
    path.write_bytes(normalized)


def export_model(objects: list[bpy.types.Object], output_dir: Path) -> None:
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]

    bpy.ops.export_scene.fbx(
        filepath=str(output_dir / "PortalEmitter.fbx"),
        use_selection=True,
        object_types={"EMPTY", "MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        global_scale=1.0,
        axis_forward="-Z",
        axis_up="Y",
        use_space_transform=True,
        bake_space_transform=False,
        mesh_smooth_type="OFF",
        use_mesh_modifiers=True,
        use_triangles=True,
        path_mode="STRIP",
        embed_textures=False,
        use_custom_props=False,
        bake_anim=False,
    )
    bpy.ops.export_scene.gltf(
        filepath=str(output_dir / "PortalEmitter.glb"),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )
    bpy.ops.wm.obj_export(
        filepath=str(output_dir / "PortalEmitter.obj"),
        export_selected_objects=True,
        export_materials=True,
        forward_axis="NEGATIVE_Z",
        up_axis="Y",
        global_scale=1.0,
        apply_modifiers=True,
    )


def verify_fbx_roundtrip(
    output_dir: Path,
    expected_objects: list[bpy.types.Object],
    contract: dict,
    source_metrics: dict,
) -> dict:
    expected_types = {obj.name: obj.type for obj in expected_objects}
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(output_dir / "PortalEmitter.fbx"))

    imported_objects = list(bpy.context.scene.objects)
    actual_types = {obj.name: obj.type for obj in imported_objects}
    if actual_types != expected_types:
        missing = sorted(set(expected_types) - set(actual_types))
        unexpected = sorted(set(actual_types) - set(expected_types))
        wrong_types = sorted(
            name for name in set(expected_types) & set(actual_types)
            if expected_types[name] != actual_types[name]
        )
        raise RuntimeError(
            f"FBX round-trip object mismatch: missing={missing}, unexpected={unexpected}, wrong_types={wrong_types}"
        )

    root = bpy.data.objects.get(contract["unity_name"])
    if root is None or root.parent is not None:
        raise RuntimeError(f"FBX round-trip root is missing or parented: {contract['unity_name']}")
    for name in expected_types:
        if name != root.name and bpy.data.objects[name].parent is not root:
            raise RuntimeError(f"FBX round-trip hierarchy mismatch: {name} is not parented to {root.name}")

    mesh_objects = [obj for obj in imported_objects if obj.type == "MESH"]
    roundtrip_metrics = geometry_metrics(mesh_objects)
    validate_metrics(roundtrip_metrics, contract)
    for field in ("size", "center"):
        source_values = source_metrics["bounds_m"][field]
        imported_values = roundtrip_metrics["bounds_m"][field]
        if any(abs(actual - expected) > 0.004 for actual, expected in zip(imported_values, source_values)):
            raise RuntimeError(
                f"FBX round-trip {field} differs from source geometry: "
                f"{imported_values} != {source_values}"
            )

    for field in ("hand_socket", "muzzle_socket", "support_hand_socket", "fps_root", "fps_hand_socket"):
        field_name = contract[field]["name"]
        socket = bpy.data.objects.get(field_name)
        if socket is None:
            raise RuntimeError(f"FBX round-trip socket is missing: {field_name}")
        actual_position = list(socket.matrix_world.translation)
        expected_position = contract[field]["position"]
        if any(abs(actual - expected) > 0.004 for actual, expected in zip(actual_position, expected_position)):
            raise RuntimeError(
                f"FBX round-trip socket position differs for {field_name}: "
                f"{actual_position} != {expected_position}"
            )

    imported_materials = {
        slot.material.name
        for obj in mesh_objects
        for slot in obj.material_slots
        if slot.material is not None
    }
    missing_materials = sorted(set(contract["materials"]) - imported_materials)
    if missing_materials:
        raise RuntimeError(f"FBX round-trip is missing materials: {', '.join(missing_materials)}")

    return {
        "object_count": len(imported_objects),
        "mesh_count": len(mesh_objects),
        "bounds_m": roundtrip_metrics["bounds_m"],
        "materials": sorted(imported_materials),
    }


def write_manifest(output_dir: Path, contract: dict, metrics: dict) -> None:
    files = {}
    for path in sorted(output_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "toolgen_version": TOOLGEN_VERSION,
        "tool_id": contract["tool_id"],
        "unity_name": contract["unity_name"],
        "files": files,
        "geometry": {
            "mesh_count": metrics["mesh_count"],
            "vertex_count": metrics["vertex_count"],
            "polygon_count": metrics["polygon_count"],
            "sha256": metrics["geometry_sha256"],
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    arguments = parse_arguments()
    contract = json.loads(arguments.contract.read_text(encoding="utf-8"))
    output_dir = arguments.output
    output_dir.mkdir(parents=True, exist_ok=True)

    clear_scene()
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0

    objects = build_portal_emitter(contract)
    bpy.context.view_layer.update()
    mesh_objects = [obj for obj in objects if obj.type == "MESH"]
    metrics = geometry_metrics(mesh_objects)
    metrics["tool_id"] = contract["tool_id"]
    validate_metrics(metrics, contract)

    create_preview_scene()
    bpy.ops.wm.save_as_mainfile(filepath=str(output_dir / "PortalEmitter.blend"))
    bpy.ops.render.render(write_still=True)
    strip_png_text_metadata(output_dir / "preview.png")
    export_model(objects, output_dir)
    metrics["fbx_roundtrip"] = verify_fbx_roundtrip(output_dir, objects, contract, metrics)
    metrics["checks"]["fbx_roundtrip"] = True
    (output_dir / "qa_geometry.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    write_manifest(output_dir, contract, metrics)
    print(f"Generated {contract['tool_id']}: {metrics['mesh_count']} meshes, {metrics['polygon_count']} polygons")


if __name__ == "__main__":
    main()
