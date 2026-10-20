"""Coverage tests for the file-to-check mapping."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import testplan


class TestPlanTests(unittest.TestCase):
    def test_every_versioned_file_has_a_rule(self):
        files = testplan.git("ls-files")
        self.assertTrue(files)
        self.assertEqual([path for path in files if testplan.area_of(path) == "unknown"], [])

    def test_examples_and_minimal_paths(self):
        cases = {"README.md": "docs", "data/tools.json": "data", "scripts/tool_assets/Portalkanone/create.py": "assets",
                 "toolgen/toolcache.py": "cache", "toolgen/generate_tools.py": "pipeline",
                 "viewer/build.sh": "viewer", "tests/test_pipeline.py": "tests",
                 "data/concepts/KG02.geo.json": "concepts", "scripts/import_concepts.py": "concepts"}
        for path, area in cases.items(): self.assertEqual(testplan.area_of(path), area, path)
        self.assertEqual(testplan.make_plan(["README.md"])["steps"], [])
        self.assertEqual(testplan.make_plan(["tests/test_pipeline.py"])["steps"], ["unit"])
        self.assertEqual(testplan.make_plan(["toolgen/toolcache.py"])["steps"],
                         ["unit", "quick1", "quick2 (verify hits)", "standard"])
        self.assertEqual(testplan.make_plan(["viewer/build.sh"])["steps"], ["unit", "viewer"])
        self.assertEqual(testplan.make_plan(["data/concepts/provenance.json"])["steps"], ["unit", "quick (affected tools)"])

    def test_mixed_diff_keeps_pipeline_checks(self):
        steps = testplan.make_plan(["viewer/build.sh", "toolgen/generate_tools.py"])["steps"]
        self.assertEqual(steps, ["unit", "quick1", "quick2 (verify hits)", "standard", "viewer"])
        self.assertIn("quick (affected tools)", testplan.make_plan(["viewer/build.sh", "data/tools.json"])["steps"])


if __name__ == "__main__":
    unittest.main()
