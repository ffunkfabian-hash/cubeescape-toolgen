"""Pure helper tests for the contract-4 surface acceptance script."""
import importlib.util
import struct
import sys
import types
import unittest
from pathlib import Path

try:
    import numpy  # noqa: F401
except ImportError:
    NUMPY_AVAILABLE = False
else:
    NUMPY_AVAILABLE = True


@unittest.skipUnless(NUMPY_AVAILABLE, "numpy is available in Blender's Python")
class VerifySurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        sys.modules.setdefault("bpy", types.ModuleType("bpy"))
        sys.path.insert(0, str(root / "toolgen"))
        spec = importlib.util.spec_from_file_location("verify_surface", root / "scripts/verify_surface.py")
        cls.verify = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.verify)

    def test_accessor_honours_interleaved_stride_and_offsets(self):
        values = b"\x00\x00\x80?PAD!\x00\x00\x00@PAD!"
        document = {"accessors": [{"bufferView": 0, "byteOffset": 0, "componentType": 5126,
                                   "count": 2, "type": "SCALAR"}],
                    "bufferViews": [{"byteOffset": 0, "byteStride": 8}]}
        decoded = self.verify.accessor(document, values, 0)
        self.assertEqual(decoded.tolist(), [1.0, 2.0])

    def test_accessor_reads_unsigned_indices(self):
        document = {"accessors": [{"bufferView": 0, "componentType": 5123, "count": 3, "type": "SCALAR"}],
                    "bufferViews": [{}]}
        self.assertEqual(self.verify.accessor(document, struct.pack("<3H", 0, 12, 65535), 0).tolist(), [0, 12, 65535])

    def test_tangent_score_uses_uv_derivative_and_projects_normal(self):
        import numpy as np
        position = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])
        normal = np.tile([0., 0., 1.], (3, 1))
        tangent = np.tile([1., 0., 0., 1.], (3, 1))
        uv = np.array([[0., 0.], [1., 0.], [0., 1.]])
        score = self.verify.tangent_scores(position, normal, tangent, uv, np.array([[0, 1, 2]]))
        self.assertEqual(score["vertices"], 3)
        self.assertEqual(score["quote"], 1.0)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(NUMPY_AVAILABLE, "numpy is available in Blender's Python")
class GoldenAlternatesTests(unittest.TestCase):
    """Toolgen 0.15.1: a map may match its golden hash or a confirmed alternate (the robot normal bake flips one texel)."""

    @classmethod
    def setUpClass(cls):
        VerifySurfaceTests.setUpClass()
        cls.verify = VerifySurfaceTests.verify

    def manifest(self):
        return {"maps": {"t": {"a.png": "A", "b.png": "B"}}, "alternates": {"t": {"a.png": ["A2"]}}}

    def test_primary_and_alternate_pass_anything_else_fails(self):
        m = self.manifest()
        self.assertTrue(self.verify.golden_accepts(m, "t", "a.png", "A"))
        self.assertTrue(self.verify.golden_accepts(m, "t", "a.png", "A2"))
        self.assertFalse(self.verify.golden_accepts(m, "t", "a.png", "B"))
        self.assertFalse(self.verify.golden_accepts(m, "t", "b.png", "A2"), "alternates belong to one map")
        self.assertFalse(self.verify.golden_accepts(m, "u", "a.png", "A"))

    def test_update_keeps_a_flip_and_drops_alternates_of_new_content(self):
        m = self.manifest()
        self.verify.golden_update(m, "t", {"a.png": "A2", "b.png": "B"})       # the bake flipped: both stay accepted
        self.assertEqual("A2", m["maps"]["t"]["a.png"])
        self.assertEqual({"a.png": ["A"]}, m["alternates"]["t"])
        self.verify.golden_update(m, "t", {"a.png": "NEW", "b.png": "B"})      # a deliberate change: no stale alternate
        self.assertEqual("NEW", m["maps"]["t"]["a.png"])
        self.assertNotIn("t", m["alternates"])
        self.assertFalse(self.verify.golden_accepts(m, "t", "a.png", "A"))

    def test_the_repository_golden_names_only_existing_maps(self):
        import json
        golden = json.loads((Path(__file__).resolve().parents[1] / "tests/golden/surface/manifest.json").read_text())
        for tool, maps in golden.get("alternates", {}).items():
            for name, hashes in maps.items():
                self.assertIn(name, golden["maps"][tool])
                self.assertNotIn(golden["maps"][tool][name], hashes)
                self.assertTrue(all(len(value) == 64 for value in hashes))
