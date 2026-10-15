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
    SourceIndex,
    catalog,
    expand,
    function_fingerprint,
    hash_file,
    main,
    stage_key,
    Stage,
    Variant,
    STAGES,
    assemble_package,
    output_lock,
    valid_package,
    variants,
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

    def test_fps_package_requires_successful_hand_qa(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); manifest = self.package(root)
            manifest["models"][0]["variant"] = "fps"
            (root / "manifest.json").write_text(json.dumps(manifest))
            self.assertFalse(valid_package(root))
            path = root / "qa_viewmodel.json"
            for passed in (False, True):
                path.write_text(json.dumps({"passed": passed}))
                manifest["files"][path.name] = hash_file(path)
                (root / "manifest.json").write_text(json.dumps(manifest))
                self.assertEqual(passed, valid_package(root))
            manifest["tier"] = "standard"
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

    def keys(self, tool, tier="quick", blender="Blender 5.2.2", state=None, render=None):
        index = SourceIndex()
        return {run.name: stage_key(run, tool, state or {}, blender, index, render) for run in expand(tool, tier)}

    def test_blender_version_and_render_settings_invalidate_cache(self):
        tool = catalog()[0]
        key = self.keys(tool)
        self.assertNotEqual(key, self.keys(tool, blender="Blender 5.3"))
        self.assertEqual(key, self.keys(tool))
        render = {"samples": 12, "percent": 50, "device": "cpu"}
        self.assertNotEqual(key["world"], self.keys(tool, render=render)["world"])
        # quick and standard share the geometry keys of every stage both tiers run
        standard = self.keys(tool, "standard")
        self.assertEqual({name: key[name] for name in key}, {name: standard[name] for name in key})

    def test_source_content_invalidates_cache(self):
        tool = catalog()[0]
        before = self.keys(tool)
        read_bytes = Path.read_bytes
        def changed(path):
            return read_bytes(path) + (b"\n# changed" if path.name == tool["world"] else b"")
        with patch.object(Path, "read_bytes", changed):
            self.assertNotEqual(before["world"], self.keys(tool)["world"])

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

    def test_hand_profiles_and_shared_motion_invalidate_only_first_person(self):
        tool = catalog()[3]; before = self.keys(tool)
        read_bytes = Path.read_bytes
        for source in ("viewmodels.json", "first_person.py", "motion_profiles.py"):
            with self.subTest(source=source):
                def changed(path, source=source):
                    return read_bytes(path) + (b"\n# changed" if path.name == source else b"")
                with patch.object(Path, "read_bytes", changed):
                    after = self.keys(tool)
                self.assertNotEqual(before["first_person"], after["first_person"])
                self.assertEqual(before["world"], after["world"])
                self.assertEqual(before["fps"], after["fps"])

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

    def test_report_changes_do_not_invalidate_model_cache(self):
        tool = catalog()[0]; function_fingerprint.cache_clear(); before = self.keys(tool)
        read_text = Path.read_text
        def changed(path):
            text = read_text(path)
            return text.replace('report = {"version": VERSION', 'report = {"label": "new", "version": VERSION') if path.name == "generate_tools.py" else text
        with patch.object(Path, "read_text", changed):
            function_fingerprint.cache_clear()
            self.assertEqual(before, self.keys(tool))
        function_fingerprint.cache_clear()

    def test_output_producer_changes_invalidate_cache(self):
        tool = catalog()[0]; function_fingerprint.cache_clear(); before = self.keys(tool)
        read_text = Path.read_text
        def changed(path):
            text = read_text(path)
            return text.replace('environment["TOOLGEN_NO_RENDER"] = "1"', 'environment["TOOLGEN_NO_RENDER"] = "yes"') if path.name == "generate_tools.py" else text
        with patch.object(Path, "read_text", changed):
            function_fingerprint.cache_clear()
            self.assertNotEqual(before, self.keys(tool))
        function_fingerprint.cache_clear()

    def test_package_hit_uses_new_stage_records_without_blender(self):
        import toolcache
        tool = catalog()[0]
        with tempfile.TemporaryDirectory() as name:
            output = Path(name); (output / tool["id"]).mkdir()
            builder = __import__("generate_tools").ToolBuild(
                tool, output, "quick", "blender-must-not-run", "5.2", 1, False, "cpu",
                toolcache.Store(Path(name) / "cache"))
            with patch.object(builder, "resolve", return_value=[]), \
                 patch.object(builder, "package_key", return_value="cached-key"), \
                 patch("generate_tools.valid_package", return_value=True), \
                 patch("generate_tools.run_stage", side_effect=AssertionError("Blender stage ran")):
                result = builder.build()
            self.assertTrue(result["cache_hit"])

    def test_one_added_stage_supplies_manifest_and_viewer_variant(self):
        tool = dict(catalog()[0], game="game_export.py", asset="Tool", clip="Idle")
        stage = Stage("game", "toolgen/game_export.py", reads=("Tool.blend",), qa=("qa_game.json",),
                      variants=(Variant("game", "{asset}_Game", clip=("clip",), exports=("blend",)),))
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            runs = [run for run in expand(tool, "quick", stages=(*STAGES, stage))
                    if run.name in ("game", "viewer_game")]
            game_run = next(run for run in runs if run.name == "game")
            viewer_run = next(run for run in runs if run.name == "viewer_game")
            self.assertEqual((game_run.name, viewer_run.variant["name"]), ("game", "game"))
            work = root / "work"; (work / "ViewerData/game").mkdir(parents=True)
            (work / "Tool_Game.blend").write_bytes(b"model")
            (work / "ViewerData/game/scene.json").write_text(json.dumps({"triangles": 1, "frames": 1}))
            with patch("generate_tools.valid_package", return_value=True):
                assemble_package(work, tool, "quick", "cpu", runs, [], "key")
            manifest = json.loads((work / "manifest.json").read_text())
            self.assertIn("game", [model["variant"] for model in manifest["models"]])
            self.assertIn("qa_game.json", manifest["required_qa"])


if __name__ == "__main__":
    unittest.main()


class GameFpsStageTest(unittest.TestCase):
    def test_viewmodel_game_export_is_a_stage_with_its_own_qa_and_inputs(self):
        stage = next(stage for stage in STAGES if stage.name == "game_fps")
        self.assertIn("--viewmodel", stage.args)
        self.assertEqual(("qa_game_fps.json",), stage.qa)
        self.assertIn("{asset}_FPS.blend", stage.reads)
        self.assertIn("viewmodel_camera.json", stage.reads)
        self.assertIn("data/game_budget.json", stage.sources)
        self.assertEqual(["fps_game"], [variant.name for variant in stage.variants])
        self.assertEqual("{asset}_FPS", stage.variants[0].node)
        self.assertEqual(("fps_clip", "clip"), stage.variants[0].clip)
        for tool in catalog():
            self.assertIn("fps_game", [variant.name for variant in variants(tool)])
        names = [stage.name for stage in STAGES]
        self.assertGreater(names.index("game_fps"), names.index("first_person"))
        for tool in catalog():
            runs = [run.name for run in expand(tool, "quick")]
            self.assertIn("game_fps", runs)
