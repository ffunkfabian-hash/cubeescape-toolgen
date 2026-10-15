import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TOOLGEN_ROOT = REPOSITORY_ROOT / "toolgen"
sys.path.insert(0, str(TOOLGEN_ROOT))

from build_toolset import REQUIRED_OUTPUTS, REQUIRED_QA_CHECKS, verify_generated_output
from tool_contract import PRESETS, build_tool_contract, validate_contract


class ToolContractTests(unittest.TestCase):
    def test_every_preset_builds_a_valid_contract(self):
        for tool_id in PRESETS:
            with self.subTest(tool_id=tool_id):
                self.assertEqual([], validate_contract(build_tool_contract(tool_id)))

    def test_unknown_preset_is_rejected(self):
        with self.assertRaisesRegex(KeyError, "unknown tool preset"):
            build_tool_contract("unknown_tool")

    def test_portal_emitter_contract_matches_runtime_model_names(self):
        contract = build_tool_contract("portal_emitter")
        self.assertEqual("PortalEmitter", contract["unity_name"])
        self.assertEqual("grip", contract["pivot"])
        self.assertEqual("Muzzle", contract["muzzle_socket"]["name"])
        self.assertEqual("-Y", contract["qa"]["facing"])


class GeneratedOutputTests(unittest.TestCase):
    def create_valid_output(self, output_dir: Path) -> None:
        for name in REQUIRED_OUTPUTS:
            if name != "manifest.json":
                (output_dir / name).write_bytes(name.encode("utf-8"))

        qa = {
            "tool_id": "portal_emitter",
            "checks": {name: True for name in REQUIRED_QA_CHECKS},
            "geometry_sha256": "0" * 64,
        }
        (output_dir / "qa_geometry.json").write_text(json.dumps(qa), encoding="utf-8")
        files = {
            name: hashlib.sha256((output_dir / name).read_bytes()).hexdigest()
            for name in REQUIRED_OUTPUTS
            if name != "manifest.json"
        }
        manifest = {
            "tool_id": "portal_emitter",
            "files": files,
            "geometry": {"sha256": qa["geometry_sha256"]},
        }
        (output_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_accepts_complete_hashed_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            self.create_valid_output(output_dir)
            verify_generated_output(output_dir, "portal_emitter")

    def test_rejects_failed_geometry_qa(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            self.create_valid_output(output_dir)
            qa_path = output_dir / "qa_geometry.json"
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            qa["checks"]["mesh_closed"] = False
            qa_path.write_text(json.dumps(qa), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "mesh_closed"):
                verify_generated_output(output_dir, "portal_emitter")

    def test_rejects_missing_fbx_roundtrip_qa(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            self.create_valid_output(output_dir)
            qa_path = output_dir / "qa_geometry.json"
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            del qa["checks"]["fbx_roundtrip"]
            qa_path.write_text(json.dumps(qa), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "fbx_roundtrip"):
                verify_generated_output(output_dir, "portal_emitter")

    def test_rejects_modified_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            self.create_valid_output(output_dir)
            with (output_dir / "PortalEmitter.fbx").open("ab") as output:
                output.write(b"changed")
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                verify_generated_output(output_dir, "portal_emitter")

    def test_rejects_manifest_geometry_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            self.create_valid_output(output_dir)
            manifest_path = output_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["geometry"]["sha256"] = "1" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "geometry checksum"):
                verify_generated_output(output_dir, "portal_emitter")


if __name__ == "__main__":
    unittest.main()
