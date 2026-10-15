"""Independent native/GLB/FBX checks of articulated FPS hands and sampled motion."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np


def rest_hand_margin(scene, hands, frustum, frame):
    """Smallest distance of any hand vertex to the frame edge (camera at origin, -Y forward, Z up)."""
    scene.frame_set(math.floor(frame), subframe=frame % 1); bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    margin = float("inf")
    for hand in hands:
        for obj in hand.children_recursive:
            if obj.type != "MESH":
                continue
            evaluated = obj.evaluated_get(graph)
            local = np.empty(len(evaluated.data.vertices) * 3)
            evaluated.data.vertices.foreach_get("co", local)
            matrix = np.array(evaluated.matrix_world)
            points = local.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
            depth = -points[:, 1]
            x = .5 - points[:, 0] / depth / (2 * frustum["tan_h"])
            y = .5 + points[:, 2] / depth / (2 * frustum["tan_v"])
            margin = min(margin, float(np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y)).min()))
    return margin


def verify(directory, asset):
    expected = json.loads((directory / "qa_viewmodel.json").read_text())
    results = {}
    for kind in ("blend", "glb", "fbx"):
        if kind == "blend":
            bpy.ops.wm.open_mainfile(filepath=str(directory / (asset + ".blend")))
        else:
            scene = bpy.data.scenes.new("FPS_Reimport_" + kind); bpy.context.window.scene = scene
            if kind == "glb":
                bpy.ops.import_scene.gltf(filepath=str(directory / (asset + ".glb")))
            else:
                bpy.ops.import_scene.fbx(filepath=str(directory / (asset + ".fbx")))
        scene = bpy.context.scene
        def find(name, scene=scene, kind=kind):
            for obj in scene.objects:
                stem, dot, suffix = obj.name.rpartition(".")
                if obj.name == name or dot and stem == name and suffix.isdigit():
                    return obj
            raise AssertionError((kind, "missing FPS joint", name))
        motion = find("Viewmodel_Motion")
        assert motion.animation_data and motion.animation_data.action, (kind, "missing viewmodel animation")
        first, last = motion.animation_data.action.frame_range
        assert abs(last - first - 96) < .01, (kind, "clip length", first, last)
        maximum = 0
        for frame, poses in expected["poses"].items():
            current = first + int(frame) - 1
            scene.frame_set(math.floor(current), subframe=current % 1); bpy.context.view_layer.update()
            for name, matrix in poses.items():
                obj = find(name)
                error = max(abs(obj.matrix_world[i][j] - matrix[i][j]) for i in range(4) for j in range(4))
                assert error < .001, (kind, frame, name, "FPS pose changed", error)
                maximum = max(maximum, error)
        for side in expected["hand_sides"]:
            joint = find(side)
            assert len([obj for obj in joint.children_recursive if obj.type == "MESH"]) >= 12
        # The viewmodel FOV travels with the exports (glTF extras / FBX user properties).
        root = find(asset)
        vertical = expected["viewmodel_camera"]["vertical_fov_degrees"]
        assert abs(float(root.get("ce_viewmodel_vertical_fov_degrees", -1)) - vertical) < 1e-4, (kind, "viewmodel FOV lost")
        margins = {}
        for aspect in expected["viewmodel_camera"]["qa_aspects"]:
            width, height = (float(value) for value in aspect.split(":"))
            tan_v = math.tan(math.radians(vertical) / 2)
            margins[aspect] = rest_hand_margin(scene, [find(side) for side in expected["hand_sides"]],
                                               {"tan_h": tan_v * width / height, "tan_v": tan_v}, first)
            assert margins[aspect] >= expected["framing_range"]["limits"]["hand_margin"], (kind, aspect, "rest hands leave the frame")
        results[kind] = {"passed": True, "poses": len(expected["poses"]), "max_matrix_error": maximum,
                         "vertical_fov_degrees": vertical, "rest_hand_margin": margins}
    (directory / "qa_viewmodel_roundtrip.json").write_text(json.dumps({"passed": True, "checks": results}, indent=2) + "\n")
    print("VIEWMODEL_ROUNDTRIP_OK", asset)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--asset", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    verify(args.directory, args.asset)
