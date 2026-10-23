"""Triangles without area (Toolgen 0.24 patch KG11): the QA counts them so that Unity's import drop is red beforehand."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
import mesh_check  # noqa: E402


class Buffer:
    def __init__(self, array):
        self.array = np.asarray(array)

    def foreach_get(self, _name, out):
        out[:] = self.array.reshape(-1)

    def __len__(self):
        return len(self.array)


class Mesh:
    def __init__(self, vertices, triangles):
        self.vertices, self.loop_triangles = Buffer(vertices), Buffer(triangles)

    def calc_loop_triangles(self):
        pass


class ZeroAreaTests(unittest.TestCase):
    def test_collinear_and_repeated_corners_count(self):
        vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (2, 0, 0), (.0005, 0, 0)]
        mesh = Mesh(vertices, [(0, 1, 2), (0, 1, 3), (0, 1, 1), (0, 4, 1)])
        self.assertEqual(3, mesh_check.zero_area_triangles(mesh))

    def test_small_healthy_triangles_pass(self):
        mesh = Mesh([(0, 0, 0), (1e-3, 0, 0), (0, 1e-3, 0)], [(0, 1, 2)])
        self.assertEqual(0, mesh_check.zero_area_triangles(mesh))

    def test_empty_mesh(self):
        self.assertEqual(0, mesh_check.zero_area_triangles(Mesh(np.zeros((0, 3)), np.zeros((0, 3), dtype=int))))


if __name__ == "__main__":
    unittest.main()
