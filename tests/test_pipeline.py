"""Pipeline invariants: content invalidation, failed replacement, isolation and worker limits."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolgen"))
from build_toolset import install_output
from generate_tools import (
    cache_key,
    catalog,
    hash_file,
    main,
    output_lock,
    valid_package,
    worker_budget,
)


class PipelineTests(unittest.TestCase):
    def package(self, root):
        directory = root / "ViewerData/world"
        directory.mkdir(parents=True)
        for filename in ("scene.json", "vertices.bin", "indices.bin", "anim.bin"):
            (directory / filename).write_bytes(b"test")
        (directory / "qa_viewer.json").write_text(json.dumps({"passed": True}))
        manifest = {"cache_key": "key", "models": [{"path": "ViewerData/world"}],
                    "files": {str(path.relative_to(root)): hash_file(path) for path in root.rglob("*") if path.is_file()}}
        (root / "manifest.json").write_text(json.dumps(manifest))
        return manifest

    def test_cache_rejects_modified_binary_even_with_matching_key(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); self.package(root)
            self.assertTrue(valid_package(root, "key"))
            (root / "ViewerData/world/anim.bin").write_bytes(b"changed")
            self.assertFalse(valid_package(root, "key"))

    def test_cache_rejects_missing_viewer_buffer_entry(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); manifest = self.package(root)
            del manifest["files"]["ViewerData/world/anim.bin"]
            (root / "manifest.json").write_text(json.dumps(manifest))
            self.assertFalse(valid_package(root, "key"))

    def test_cache_rejects_failed_qa(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); manifest = self.package(root)
            path = root / "ViewerData/world/qa_viewer.json"
            path.write_text(json.dumps({"passed": False}))
            manifest["files"][str(path.relative_to(root))] = hash_file(path)
            (root / "manifest.json").write_text(json.dumps(manifest))
            self.assertFalse(valid_package(root))

    def test_cache_cannot_escape_package(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); manifest = self.package(root)
            manifest["files"]["../outside"] = "x"
            (root / "manifest.json").write_text(json.dumps(manifest))
            self.assertFalse(valid_package(root))

    def test_cache_rejects_wrong_content_key(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); self.package(root)
            self.assertFalse(valid_package(root, "new-key"))

    def test_tier_and_blender_version_invalidate_cache(self):
        tool = catalog()[0]
        key = cache_key(tool, "quick", "Blender 5.2.2")
        self.assertNotEqual(key, cache_key(tool, "standard", "Blender 5.2.2"))
        self.assertNotEqual(key, cache_key(tool, "quick", "Blender 5.3"))
        self.assertEqual(key, cache_key(tool, "quick", "Blender 5.2.2"))

    def test_source_content_invalidates_cache(self):
        tool = catalog()[0]
        before = cache_key(tool, "quick", "5.2")
        read_bytes = Path.read_bytes
        def changed(path):
            return read_bytes(path) + (b"\n# changed" if path.name == tool["world"] else b"")
        with patch.object(Path, "read_bytes", changed):
            self.assertNotEqual(before, cache_key(tool, "quick", "5.2"))

    def test_failed_install_restores_previous_output(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); target = root / "tool"; staging = root / "staging"
            target.mkdir(); staging.mkdir(); (target / "model").write_text("old")
            rename = Path.rename
            def fail(path, destination):
                if path == staging: raise OSError("simulated volume failure")
                return rename(path, destination)
            with patch.object(Path, "rename", fail), self.assertRaises(OSError):
                install_output(staging, target, force=True)
            self.assertEqual("old", (target / "model").read_text())

    def test_output_lock_rejects_other_writer_and_releases_on_failure(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            with self.assertRaisesRegex(ValueError, "test failure"), output_lock(root):
                with self.assertRaises(RuntimeError), output_lock(root): pass
                raise ValueError("test failure")
            with output_lock(root): self.assertTrue((root / ".toolgen-lock/owner.json").is_file())

    def test_workers_do_not_oversubscribe_cpu(self):
        with patch("os.cpu_count", return_value=10):
            self.assertEqual((2, 5), worker_budget())
            with self.assertRaises(ValueError): worker_budget(3, 4)
            with self.assertRaises(ValueError): worker_budget(-1)

    def test_seeded_library_cache_hit_writes_report_without_existing_logs(self):
        tool = catalog()[0]
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); package = root / tool["id"]
            package.mkdir(); self.package(package)
            with patch("sys.argv", ["generate_tools.py", "--tier", "quick", "--output", name]), \
                 patch("generate_tools.catalog", return_value=[tool]), \
                 patch("generate_tools.find_blender", return_value="/blender"), \
                 patch("generate_tools.subprocess.check_output", return_value="Blender 5.2.2\n"), \
                 patch("generate_tools.cache_key", return_value="key"):
                self.assertEqual(0, main())
            report = json.loads((root / "logs/toolgen_report.json").read_text())
            self.assertTrue(report["passed"])
            self.assertTrue(report["tools"][0]["cache_hit"])

    def test_report_changes_do_not_invalidate_model_cache(self):
        tool = catalog()[0]; before = cache_key(tool, "quick", "5.2")
        read_text = Path.read_text
        def changed(path):
            text = read_text(path)
            return text.replace('report = {"version": VERSION', 'report = {"label": "new", "version": VERSION') if path.name == "generate_tools.py" else text
        with patch.object(Path, "read_text", changed):
            self.assertEqual(before, cache_key(tool, "quick", "5.2"))

    def test_output_producer_changes_invalidate_cache(self):
        tool = catalog()[0]; before = cache_key(tool, "quick", "5.2")
        read_text = Path.read_text
        def changed(path):
            text = read_text(path)
            return text.replace('(work / "manifest.json").write_text', '(work / "manifest-next.json").write_text') if path.name == "generate_tools.py" else text
        with patch.object(Path, "read_text", changed):
            self.assertNotEqual(before, cache_key(tool, "quick", "5.2"))


if __name__ == "__main__":
    unittest.main()
