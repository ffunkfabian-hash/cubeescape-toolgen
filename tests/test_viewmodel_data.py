"""Viewmodel data contract: camera FOV, QA limits, tool heads and hand layout (pure Python)."""
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "data/viewmodels.json").read_text())
TOOLS = {tool["id"]: tool for tool in json.loads((ROOT / "data/tools.json").read_text())["tools"]}


def horizontal(vertical, aspect):
    return math.degrees(2 * math.atan(math.tan(math.radians(vertical) / 2) * aspect))


class ViewmodelCameraTests(unittest.TestCase):
    def test_default_matches_the_former_75_degree_horizontal_framing(self):
        camera = DATA["camera"]
        self.assertEqual("16:9", camera["reference_aspect"])
        self.assertAlmostEqual(75, horizontal(camera["vertical_fov_degrees"], 16 / 9), delta=.05)
        self.assertAlmostEqual(camera["horizontal_fov_degrees"], horizontal(camera["vertical_fov_degrees"], 16 / 9), delta=.05)
        self.assertAlmostEqual(.03, camera["near_clip_m"])

    def test_qa_covers_macbook_aspect_and_a_symmetric_range(self):
        qa = DATA["camera"]["qa"]
        self.assertIn("16:9", qa["aspects"]); self.assertIn("16:10", qa["aspects"])
        self.assertEqual(8, qa["fov_tolerance_degrees"])
        self.assertGreaterEqual(qa["fov_samples"], 3)
        self.assertEqual(1, qa["fov_samples"] % 2, "the configured FOV must be one of the samples")
        self.assertGreater(DATA["camera"]["vertical_fov_degrees"] - qa["fov_tolerance_degrees"], 20)
        self.assertTrue(0 < qa["head_min_unoccluded_fraction"] <= 1)

    def test_tool_overrides_stay_in_viewer_slider_range(self):
        for tool, profile in DATA["tools"].items():
            vertical = profile.get("vertical_fov_degrees", DATA["camera"]["vertical_fov_degrees"])
            self.assertTrue(35 <= vertical <= 75, tool)


class ViewmodelPoseTests(unittest.TestCase):
    def test_every_catalog_tool_has_a_profile(self):
        self.assertEqual(set(TOOLS), set(DATA["tools"]))

    def test_heads_use_semantic_anchors_except_the_bow(self):
        expected = {"portal_emitter": "Socket_Muzzle", "magnet_gripper": "Socket_Grab", "flashlight": "Socket_Muzzle"}
        for tool, profile in DATA["tools"].items():
            if tool == "bow":
                self.assertNotIn("head", profile)
                continue
            self.assertEqual(expected[tool], profile["head"]["anchor"])
            self.assertTrue(profile["head"]["parts"])
            self.assertTrue(all(part.startswith("SM_") for part in profile["head"]["parts"]))

    def test_aim_targets_lie_in_front_of_the_camera(self):
        for tool, profile in DATA["tools"].items():
            target = profile.get("aim_target_m", (0, -4, 0))
            self.assertLess(target[1], profile["hand"][1] - .5, tool)

    def test_shoulders_are_fixed_measures_for_both_sides(self):
        for profile in [DATA["arm"], *DATA["tools"].values()]:
            if "shoulders" in profile:
                self.assertEqual({"L", "R"}, set(profile["shoulders"]))

    def test_reference_style_names_three_fingers_and_a_thumb(self):
        style = DATA["reference"]["style"]
        self.assertIn("three gripping fingers", style)
        self.assertIn("thumb", style)


if __name__ == "__main__":
    unittest.main()
