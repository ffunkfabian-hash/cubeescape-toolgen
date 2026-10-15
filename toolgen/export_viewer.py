"""Export authored tool meshes and baked transforms for the native SceneKit viewer.

Like Robogen, use indexed binary geometry, Y-up coordinates and a separate animation
buffer. Shape keys remain morph targets; the SceneKit app never rebuilds a model.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

SCHEMA = 1
C = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))
CI = C.inverted()


def matrix_values(matrix):
    location, rotation, scale = (C @ matrix @ CI).decompose()
    return [*location, rotation.x, rotation.y, rotation.z, rotation.w, *scale]


def material_data(material):
    node = material.node_tree.nodes.get("Principled BSDF") if material.node_tree else None
    def value(name, default):
        return node.inputs[name].default_value if node and name in node.inputs else default
    return {"name": material.name, "color": list(value("Base Color", material.diffuse_color)),
            "metallic": float(value("Metallic", 0)), "roughness": float(value("Roughness", .5)),
            "emission": list(value("Emission Color", (0, 0, 0, 1))),
            "strength": float(value("Emission Strength", 0))}


def export_model(source, destination, root_name, clip):
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    scene.frame_set(1)
    bpy.context.view_layer.update()
    root = scene.objects[root_name]
    objects = [root, *sorted(root.children_recursive, key=lambda obj: obj.name)]
    names = {obj.name: index for index, obj in enumerate(objects)}
    frames = scene.frame_end - scene.frame_start + 1 if clip else 1
    fps = scene.render.fps / scene.render.fps_base
    nodes, parts, vertices, indices, materials, morphs = [], [], [], [], [], []
    material_names = {}
    vertex_offset = index_offset = 0
    triangles = 0
    for obj in objects:
        local = obj.parent.matrix_world.inverted() @ obj.matrix_world if obj.parent in objects else obj.matrix_world
        nodes.append({"name": obj.name, "parent": names.get(obj.parent.name) if obj.parent else None,
                      "rest": matrix_values(local), "stepScale": bool(obj.get("ce_visibility_animation"))})
        if obj.type != "MESH":
            continue
        mesh = obj.data
        if not mesh.vertices or not mesh.polygons:
            raise ValueError(f"Empty mesh: {obj.name}")
        if not mesh.uv_layers:
            raise ValueError(f"Missing UVs: {obj.name}")
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            if not all(edge.is_manifold for edge in bm.edges) or bm.calc_volume(signed=True) <= 0:
                raise ValueError(f"Non-manifold or inverted mesh: {obj.name}")
        finally:
            bm.free()
        mesh.calc_loop_triangles()
        loops = np.array([triangle.loops[:] for triangle in mesh.loop_triangles], dtype=np.int64)
        triangles += len(loops)
        positions = np.array([vertex.co[:] for vertex in mesh.vertices], dtype=np.float32)
        if not np.isfinite(positions).all():
            raise ValueError(f"Non-finite geometry: {obj.name}")
        vertex_ids = np.array([loop.vertex_index for loop in mesh.loops], dtype=np.int64)
        normals = np.array([normal.vector[:] for normal in mesh.corner_normals], dtype=np.float32)
        uvs = np.array([uv.uv[:] for uv in mesh.uv_layers[0].data], dtype=np.float32)
        if not np.isfinite(uvs).all():
            raise ValueError(f"Non-finite UVs: {obj.name}")
        uvs[:, 1] = 1 - uvs[:, 1]
        rotate = np.array(C.to_3x3(), dtype=np.float32)
        weights = []
        keys = mesh.shape_keys
        if keys:
            for key in list(keys.key_blocks)[1:]:
                weights.append((len(morphs), key))
                morphs.append({"node": names[obj.name], "name": key.name})
        for slot in sorted({triangle.material_index for triangle in mesh.loop_triangles}):
            if slot >= len(mesh.materials) or mesh.materials[slot] is None:
                raise ValueError(f"Missing material: {obj.name}, slot {slot}")
            material = mesh.materials[slot]
            if material.name not in material_names:
                material_names[material.name] = len(materials)
                materials.append(material_data(material))
            selected = np.array([i for i, tri in enumerate(mesh.loop_triangles) if tri.material_index == slot])
            corners = loops[selected].reshape(-1)
            ids = vertex_ids[corners]
            # Include the original vertex ID in deduplication so morph targets keep their correspondence.
            packed = np.c_[positions[ids] @ rotate.T, normals[corners] @ rotate.T, uvs[corners], ids]
            unique, first, inverse = np.unique(packed, axis=0, return_index=True, return_inverse=True)
            base = unique[:, :8].astype("<f4")
            target_ids = ids[first]
            target_info = []
            for weight, key in weights:
                target = base.copy()
                coordinates = np.array([vertex.co[:] for vertex in key.data], dtype=np.float32)
                target[:, :3] = coordinates[target_ids] @ rotate.T
                target_info.append({"weight": weight, "vertexOffset": vertex_offset})
                vertices.append(target)
                vertex_offset += len(target)
            # The base comes after its morph target blocks; indices are relative to this block.
            parts.append({"node": names[obj.name], "material": material_names[material.name],
                          "vertexOffset": vertex_offset, "vertexCount": len(base),
                          "indexOffset": index_offset, "indexCount": len(inverse), "targets": target_info})
            vertices.append(base)
            indices.append(inverse.astype("<u4"))
            vertex_offset += len(base)
            index_offset += len(inverse)
    if not parts:
        raise ValueError(f"No visible geometry under {root_name}")
    animation = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for frame in range(1, frames + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        row = []
        for obj in objects:
            evaluated = obj.evaluated_get(depsgraph)
            matrix = evaluated.matrix_world
            if obj.parent in objects:
                matrix = obj.parent.evaluated_get(depsgraph).matrix_world.inverted() @ matrix
            row.extend(matrix_values(matrix))
        for morph in morphs:
            obj = objects[morph["node"]]
            row.append(obj.data.shape_keys.key_blocks[morph["name"]].value)
        animation.append(row)
    arrays = {"vertices.bin": np.concatenate(vertices).astype("<f4"),
              "indices.bin": np.concatenate(indices).astype("<u4"),
              "anim.bin": np.array(animation, dtype="<f4")}
    destination.mkdir(parents=True, exist_ok=True)
    for filename, array in arrays.items():
        if not np.isfinite(array).all():
            raise ValueError(f"Non-finite viewer buffer: {filename}")
        array.tofile(destination / filename)
    scene.frame_set(1)
    bpy.context.view_layer.update()
    bounds = [C @ obj.matrix_world @ vertex.co for obj in objects if obj.type == "MESH" for vertex in obj.data.vertices]
    minimum = [min(point[axis] for point in bounds) for axis in range(3)]
    maximum = [max(point[axis] for point in bounds) for axis in range(3)]
    doc = {"format": SCHEMA, "vertexStride": 8, "fps": fps, "frames": frames,
           "clip": clip, "autoplay": False, "loop": False, "nodes": nodes, "parts": parts,
           "materials": materials, "morphs": morphs, "bounds": [minimum, maximum],
           "floatsPerFrame": len(nodes) * 10 + len(morphs), "triangles": triangles}
    (destination / "scene.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")
    digest = hashlib.sha256()
    for filename in sorted(arrays):
        digest.update(filename.encode())
        digest.update(arrays[filename].tobytes())
    digest.update(json.dumps(doc, sort_keys=True).encode())
    qa = {"passed": True, "meshes": sum(obj.type == "MESH" for obj in objects), "triangles": triangles,
          "frames": frames, "morph_channels": len(morphs), "geometry_sha256": digest.hexdigest(),
          "checks": {"manifold": True, "positive_volume": True, "finite": True, "uvs": True,
                     "materials": True, "animation_finite": True}}
    (destination / "qa_viewer.json").write_text(json.dumps(qa, indent=2) + "\n")
    print(f"VIEWER_EXPORT_OK {root_name}: {triangles} triangles, {frames} frames, {len(morphs)} morphs")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--clip")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    export_model(args.source, args.output, args.root, args.clip)


if __name__ == "__main__":
    main()
