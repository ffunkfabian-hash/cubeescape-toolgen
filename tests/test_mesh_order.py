"""Fixed face order after triangulating n-gons (Toolgen 0.20, scripts/tool_assets/mesh_order.py). Pure Python, no Blender.

bmesh.ops.triangulate returns the same triangles in a varying order (0.19 finding 1: two cold KG02 builds differed in the viewer
indices and every GLB); mesh_order.face_order puts them back into one order, whatever order bmesh handed them in."""
import random
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))

import mesh_order  # noqa: E402


def ordered(places, corners):
    return [(places[i], corners[i]) for i in mesh_order.face_order(places, corners)]


class FaceOrderTests(unittest.TestCase):
    # a quad at place 0, a heptagon at place 1 (five triangles), a triangle at place 2 - as bmesh leaves them: the reused
    # n-gon slot first, the new triangles appended behind the other faces
    PLACES = [0, 1, 2, 1, 1, 1, 1]
    CORNERS = [[0, 1, 2, 3], [9, 8, 4], [11, 12, 13], [4, 5, 6], [4, 6, 7], [4, 7, 8], [10, 9, 4]]

    def test_triangles_follow_their_ngon_by_corner_indices(self):
        self.assertEqual([(0, [0, 1, 2, 3]), (1, [4, 5, 6]), (1, [4, 6, 7]), (1, [4, 7, 8]), (1, [9, 8, 4]),
                          (1, [10, 9, 4]), (2, [11, 12, 13])], ordered(self.PLACES, self.CORNERS))

    def test_any_input_order_gives_the_same_result(self):
        expected = ordered(self.PLACES, self.CORNERS)
        faces = list(zip(self.PLACES, self.CORNERS))
        generator = random.Random(19)
        for _ in range(50):
            generator.shuffle(faces)
            self.assertEqual(expected, ordered([place for place, _ in faces], [corners for _, corners in faces]))

    def test_winding_and_loop_start_are_kept(self):
        # the order only moves faces; the corners of each face stay as bmesh made them (normals, loop data)
        self.assertEqual(sorted(map(tuple, self.CORNERS)),
                         sorted(tuple(corners) for _, corners in ordered(self.PLACES, self.CORNERS)))

    def test_untouched_faces_keep_their_place(self):
        self.assertEqual([0, 1, 2], mesh_order.face_order([0, 1, 2], [[5, 6, 7], [0, 1, 2, 3], [1, 2, 3]]))


class CallerTests(unittest.TestCase):
    def test_every_triangulation_goes_through_mesh_order(self):
        """bmesh.ops.triangulate outside mesh_order would bring the varying order back."""
        found = []
        for folder in ("toolgen", "scripts"):
            for path in sorted((ROOT / folder).rglob("*.py")):
                if path.name != "mesh_order.py" and re.search(r"bmesh\.ops\.triangulate\(", path.read_text()):
                    found.append(str(path.relative_to(ROOT)))
        self.assertEqual([], found)

    def test_both_triangulating_steps_use_it(self):
        for relative in ("scripts/tool_assets/concept_kit.py", "toolgen/game_export.py"):
            self.assertIn("mesh_order.triangulate_ngons(bm)", (ROOT / relative).read_text(), relative)


if __name__ == "__main__":
    unittest.main()
