"""viewer/test_determinism.py: the verdict logic only (the renders need the macOS viewer)."""
import unittest
from pathlib import Path

import importlib.util

# Loaded by path: the viewer script shares its file name with this test module.
SPEC = importlib.util.spec_from_file_location("viewer_determinism",
                                              Path(__file__).resolve().parents[1] / "viewer/test_determinism.py")
determinism = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(determinism)


class VerdictTests(unittest.TestCase):
    def test_noise_below_the_limit_is_stable(self):
        self.assertEqual(("STABLE", .98, 0), determinism.classify("pistol/fps", [0.0, .98, .02], known={}))

    def test_one_flip_makes_a_model_unstable(self):
        verdict = determinism.classify("shotgun/fps", [0.0, 57.5, 0.0], known={})
        self.assertEqual(("UNSTABLE", 57.5, 1), verdict)
        self.assertEqual(["shotgun/fps"], determinism.failed({"shotgun/fps": verdict, "bow/fps": ("STABLE", 0.0, 0)}))

    def test_known_models_are_reported_not_skipped(self):
        known = {"smg/world": 30.0}
        self.assertEqual(("EXPECTED_UNSTABLE", 30.0, 2), determinism.classify("smg/world", [30.0, 0, 30.0], known=known))
        self.assertEqual(("KNOWN_NOW_STABLE", 0.5, 0), determinism.classify("smg/world", [0.5, 0.0], known=known))
        self.assertEqual([], determinism.failed({"smg/world": ("EXPECTED_UNSTABLE", 30.0, 2)}))

    def test_defaults(self):
        self.assertEqual((8, 1.0), (determinism.RUNS, determinism.LIMIT_PX))
        self.assertTrue(all(value > determinism.LIMIT_PX for value in determinism.KNOWN_UNSTABLE.values()))


if __name__ == "__main__":
    unittest.main()
