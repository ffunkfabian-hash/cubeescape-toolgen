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
