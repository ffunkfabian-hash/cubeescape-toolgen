"""Which files compare_models.py may let differ (Toolgen 0.20). Pure Python, no Blender.

0.20 changed the face order of four robot game models (three with new maps); compare_models hid it because the whole robot
game export counted as unstable. On the Mac its viewer data are byte-identical between cold builds (13 tools, twice), only the robot game GLB still
varies in a few float bytes - so the viewer data are compared again."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import compare_models  # noqa: E402


def package(root, files):
    folder = root / "tool"
    for name, content in files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    manifest = {"files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}
    (folder / "manifest.json").write_text(json.dumps(manifest))


class KnownUnstableTests(unittest.TestCase):
    def test_first_person_game_export_and_robot_game_glb_stay_unstable(self):
        for name in ("CubeEscape_Tool_FPS_Game.glb", "ViewerData/fps_game/indices.bin", "CubeEscape_Tool_Robot_Game.glb"):
            self.assertTrue(compare_models.known_unstable(name), name)

    def test_robot_game_viewer_data_are_compared(self):
        for name in ("ViewerData/robot_game/indices.bin", "ViewerData/robot_game/vertices.bin", "ViewerData/robot/indices.bin",
                     "CubeEscape_Tool_Robot.glb", "CubeEscape_Tool_Game.glb"):
            self.assertFalse(compare_models.known_unstable(name), name)

    def test_new_face_order_of_a_robot_game_model_fails_the_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            base, new = Path(temp) / "base", Path(temp) / "new"
            files = {"CubeEscape_Tool.glb": b"world", "CubeEscape_Tool_Robot_Game.glb": b"glb",
                     "ViewerData/robot_game/indices.bin": b"\x00\x01\x02", "ViewerData/robot_game/vertices.bin": b"v"}
            package(base, files)
            package(new, files | {"CubeEscape_Tool_Robot_Game.glb": b"glb2", "ViewerData/robot_game/indices.bin": b"\x02\x00\x01"})
            report = compare_models.compare(base, new)
        self.assertEqual(["tool/ViewerData/robot_game/indices.bin"], report["different"])
        self.assertEqual(["tool/CubeEscape_Tool_Robot_Game.glb"], report["unstable"])


if __name__ == "__main__":
    unittest.main()
