"""The ADS rule of Toolgen 0.25 (user decision 23.10.2026, sight sizes like Destiny 2) on small meshes - no Blender.

Sight frame of scripts/tool_assets/ads_view.py: Socket_Sight at the origin, view along -Y, the camera of an eye distance d at
(0, d, 0). Codex sol (0.25, two rounds): the first sweep of contract 5 placed the camera with the sign flipped, and the
tests only fed finished QA results - these cases run the geometry itself."""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
import ads_view  # noqa: E402

TAN_V = math.tan(math.radians(46.69) / 2)
FRUSTA = [{"tan_h": TAN_V * 16 / 9, "tan_v": TAN_V}, {"tan_h": TAN_V * 16 / 10, "tan_v": TAN_V}]
NEAR = .03


def mesh(*parts):
    """(vertices, triangles, owners) of named parts, each a list of triangles (3 corners)."""
    vertices, triangles, owners = [], [], []
    for name, faces in parts:
        for face in faces:
            triangles.append([len(vertices), len(vertices) + 1, len(vertices) + 2])
            vertices.extend(face)
            owners.append(name)
    return np.array(vertices, float), np.array(triangles), owners


def square(y, half, x=0.0, z=0.0):
    """Two triangles of a square facing the camera at depth y, centred on (x, z)."""
    a, b, c, d = ((x - half, y, z - half), (x + half, y, z - half), (x + half, y, z + half), (x - half, y, z + half))
    return [(a, b, c), (a, c, d)]


def cuts(*parts, camera_y=0.0):
    return ads_view.near_plane_cuts(*mesh(*parts), FRUSTA, NEAR, camera_y)


class NearPlaneTests(unittest.TestCase):
    def test_a_face_crossing_the_view_without_a_corner_inside(self):
        """2 cm in front of the camera, 1 m wide: every corner lies outside the view, the face still cuts it."""
        self.assertEqual(["Stock"], cuts(("Stock", square(-.02, .5))))

    def test_a_triangle_inside_the_pyramid(self):
        self.assertEqual(["Pin"], cuts(("Pin", square(-.02, .001))))

    def test_free_near_plane(self):
        self.assertEqual([], cuts(("Beyond", square(-.05, .5))), "beyond the near plane: drawn, not cut")
        self.assertEqual([], cuts(("Behind", square(.02, .5))), "behind the camera")
        self.assertEqual([], cuts(("Beside", square(-.02, .002, z=.05))), "in front of the near plane, outside the view")

    def test_a_face_through_the_pyramid_sides_near_the_apex(self):
        """A vertical sheet 1 cm in front of the camera along the view (edge-on, x = 0): no corner inside, no hit of the
        near rectangle's face plane - it crosses through the side faces."""
        sheet = [((0, -.01, -.5), (0, -.012, .5), (0, -.008, .5))]
        self.assertEqual(["Sheet"], cuts(("Sheet", sheet)))

    def test_the_wider_view_counts(self):
        """At 2 cm the 16:9 view reaches |x| <= 0.0153, 16:10 only 0.0138: a part at x 0.0145 cuts the 16:9 view."""
        self.assertEqual(["Edge"], cuts(("Edge", square(-.02, .0003, x=.0145))))

    def test_camera_position_of_an_eye_distance(self):
        """A wall 10 cm behind the sight (towards the camera): cut only while 0.10 < d < 0.13."""
        wall = ("Wall", square(.10, .5))
        found = {d: bool(cuts(wall, camera_y=d)) for d in (.09, .105, .12, .125, .135, .2)}
        self.assertEqual({.09: False, .105: True, .12: True, .125: True, .135: False, .2: False}, found)


class CentreAndRangeTests(unittest.TestCase):
    def test_centre_ray_meets_the_nearest_part_in_front(self):
        vertices, triangles, owners = mesh(("SM_PG_Far", square(-.3, .05)), ("SM_PG_Near", square(-.1, .05)),
                                           ("SM_PG_Behind", square(.2, .05)))
        self.assertEqual("SM_PG_Near", ads_view.centre_hit(vertices, triangles, owners, .1))
        self.assertIsNone(ads_view.centre_hit(*mesh(("SM_PG_Ring", square(-.1, .05, x=.07))), .1), "beside the axis")

    def test_rule_lets_the_eye_lens_through(self):
        model = mesh(("SM_PG_ScopeEyeLens", square(-.008, .008)))
        reasons, hit, found = ads_view.rule(*model, FRUSTA, NEAR, .05, ("ScopeEyeLens",))
        self.assertEqual(([], "SM_PG_ScopeEyeLens", []), (reasons, hit, found))
        reasons, _, _ = ads_view.rule(*mesh(("SM_PG_Housing", square(-.05, .02))), FRUSTA, NEAR, .2, ("ScopeEyeLens",))
        self.assertEqual(["the centre ray meets SM_PG_Housing"], reasons)

    def test_range_starts_where_the_stock_leaves_the_near_plane(self):
        """A flat stock from the sight 6 cm back towards the eye, 6 cm wide. At eye distance d the pyramid spans
        y in [d - 0.03, d] with |z| <= (d - y) tan_v: 4 cm under the axis it needs d - y >= 0.093 m, deeper than the near
        plane, so it never cuts; 5 mm under the axis it is cut while 0.0116 <= d <= 0.09, the range starts at 0.095 m."""
        def stock(z):
            return [((-.03, 0, z), (.03, 0, z), (.03, .06, z)), ((-.03, 0, z), (.03, .06, z), (-.03, .06, z))]
        low = ads_view.eye_distance_range(*mesh(("SM_PG_Stock", stock(-.04))), FRUSTA, NEAR)
        self.assertEqual([.02, .8], low["eye_distance_range_m"])
        close = ads_view.eye_distance_range(*mesh(("SM_PG_Stock", stock(-.005))), FRUSTA, NEAR)
        self.assertEqual([.095, .8], close["eye_distance_range_m"])
        self.assertTrue(close["eye_distance_range_contiguous"])
        self.assertEqual([[.095, .8]], close["eye_distance_intervals_m"])

    def test_intervals_name_the_gaps(self):
        """A rib close to the sight and a bolt farther back cut at different eye distances: two passing stretches. The rib
        (5 mm over the axis) is cut while 0.0116 <= d - y <= 0.03 for y in [0, 0.01], the bolt (3 mm under it, y 0.30-0.31)
        while 0.307 <= d <= 0.34."""
        rib = [((-.002, .0, .005), (.002, .0, .005), (0, .01, .005))]          # 1 cm behind the sight, 5 mm over the axis
        bolt = [((-.002, .3, -.003), (.002, .3, -.003), (0, .31, -.003))]     # 30 cm behind the sight
        block = ads_view.eye_distance_range(*mesh(("Rib", rib), ("Bolt", bolt)), FRUSTA, NEAR)
        self.assertFalse(block["eye_distance_range_contiguous"])
        self.assertEqual(2, len(block["eye_distance_intervals_m"]))
        self.assertEqual([[.045, .305], [.345, .8]], block["eye_distance_intervals_m"])
        self.assertEqual([.045, .8], block["eye_distance_range_m"])

if __name__ == "__main__":
    unittest.main()
