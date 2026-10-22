"""Renamed tools (Toolgen 0.17 Retrace): the trace rifle was scout_rifle until 0.16 (user decision 19.10.2026).

tools.json ``renamed_from`` keeps the former names; the game contract carries them (game_export.renamed_block) and
generate_tools.py --tool accepts the former id while no tool carries it again. Runs without Blender.
"""
import contextlib
import inspect
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))

import game_export as ge  # noqa: E402
from generate_tools import catalog, foreign_packages, former_ids, resolve_tool_ids  # noqa: E402

TOOLS = {tool["id"]: tool for tool in catalog()}
FORMER = {"scout_rifle": "trace_rifle"}


class RenamedFromTests(unittest.TestCase):
    def test_trace_rifle_was_scout_rifle(self):
        self.assertNotIn("scout_rifle", TOOLS)
        tool = TOOLS["trace_rifle"]
        self.assertEqual(("Spurgewehr", "CubeEscape_TraceRifle", "TraceRifle_Use", "CubeEscape_TraceRifle_Robot"),
                         (tool["label"], tool["asset"], tool["clip"], tool["robot"]))
        self.assertEqual({"id": "scout_rifle", "asset": "CubeEscape_ScoutRifle", "robot": "CubeEscape_ScoutRifle_Robot",
                          "clip_stem": "ScoutRifle", "since": "0.17.0"}, tool["renamed_from"])

    def test_former_names_never_name_a_current_tool(self):
        """A former id is reserved for another tool (KG11 scout rifle); once a tool carries it, renamed_from must go."""
        current = {name for tool in TOOLS.values() for name in (tool["id"], tool["asset"], tool.get("robot"))}
        for tool in TOOLS.values():
            old = tool.get("renamed_from")
            if old:
                self.assertTrue({old["id"], old["asset"], old.get("robot")}.isdisjoint(current), tool["id"])
                self.assertNotEqual(old["clip_stem"] + "_Use", tool["clip"])
        self.assertEqual(FORMER, former_ids())

    def test_former_id_resolves_with_a_warning(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(["trace_rifle", "pistol"], resolve_tool_ids(["scout_rifle", "pistol"]))
        self.assertIn("--tool trace_rifle", stderr.getvalue())
        self.assertEqual([], resolve_tool_ids(None))

    def test_alias_ends_when_a_tool_takes_the_id(self):
        tools = [*catalog(), {"id": "scout_rifle", "asset": "CubeEscape_ScoutRifle"}]
        self.assertEqual({}, former_ids(tools))
        self.assertEqual(["scout_rifle"], resolve_tool_ids(["scout_rifle"], tools))

    def test_contract_block_maps_old_to_new(self):
        block = ge.renamed_block(TOOLS["trace_rifle"])
        self.assertEqual({"scout_rifle": "trace_rifle", "CubeEscape_ScoutRifle": "CubeEscape_TraceRifle",
                          "CubeEscape_ScoutRifle_Robot": "CubeEscape_TraceRifle_Robot", "ScoutRifle_": "TraceRifle_"},
                         block["map"])
        self.assertEqual(("scout_rifle", "0.17.0"), (block["tool"], block["since"]))
        self.assertIn("v0.16.0", block["older_consumers"])
        json.dumps(block)

    def test_contract_block_uses_the_catalogue_names(self):
        """export() takes the block from the catalogue entry before the robot/ego variant renames the asset (a block built
        after it mapped CubeEscape_ScoutRifle to CubeEscape_TraceRifle_FPS in the ego contract, found in 0.17.0)."""
        source = inspect.getsource(ge.export)
        block = source.index("renamed = renamed_block(tool)")
        self.assertLess(block, source.index("tool = dict(tool, asset="))
        self.assertNotIn("renamed_block(", inspect.getsource(ge.build_contract))

    def test_minimum_consumer_keeps_both_requirements_apart(self):
        """Every contract names the 2048 first-person maps (Cube Escape 0.96) and the renamed ids (the CE version with the
        migration version separately, and says that Cube Escape 0.96 does not read this package."""
        block = ge.consumer_block()
        self.assertEqual({"first_person_maps_2048", "renamed_tool_ids", "triangle_budgets"}, set(block))   # 0.18: budgets +25 %
        self.assertIn("FrameBudgetEnvelopeTests", block["triangle_budgets"])
        self.assertIn("Cube Escape 0.96", block["first_person_maps_2048"])
        self.assertNotIn("0.94", block["first_person_maps_2048"])
        self.assertIn("Cube Escape 0.98 „Recast“", block["renamed_tool_ids"])
        self.assertIn("0.96 and older do NOT read this package", block["renamed_tool_ids"])
        self.assertIn("git checkout v0.16.0", block["renamed_tool_ids"])
        self.assertEqual(block["renamed_tool_ids"], ge.renamed_block(TOOLS["trace_rifle"])["minimum_consumer"])
        # 0.19: the contract format joins the call (contract 5 adds shared_arm_rig)
        self.assertIn('"minimum_consumer": consumer_block(tool, contract)', inspect.getsource(ge.build_contract))
        # 0.18: a concept weapon adds its own requirement, the others keep exactly the two
        self.assertEqual({"first_person_maps_2048", "renamed_tool_ids", "triangle_budgets", "concept_models"},
                         set(ge.consumer_block(TOOLS["assault_rifle"])))
        self.assertEqual(block, ge.consumer_block(TOOLS["pistol"]))
        self.assertIn("v0.17.2", ge.consumer_block(TOOLS["assault_rifle"])["concept_models"])
        report = {"provenance": {"variant": "G", "release": "claude-v0.14", "sha256": "x"},
                  "source": {"format": "f", "format_version": 1, "repository": "r", "commit": "c", "asset": "a",
                             "asset_sha256": "z"}, "corrections": []}
        self.assertEqual("KG02", ge.concept_block(TOOLS["assault_rifle"], report)["sheet"])
        self.assertNotIn("data/concepts", inspect.getsource(ge), "the export reads the concept from qa_geometry*.json")

    def test_consumer_of_budgets_and_arm_rig_is_cube_escape_0_106(self):
        """0.23: Cube Escape 0.106 „Knuckleline“ raised FrameBudgetEnvelopeTests (device 20000, world 10000) and took the shared
        arm rig - the contracts name it instead of „offen“ (game_export.py and the arm package's own copy alike)."""
        import ego_arms
        knuckleline = "Cube Escape 0.106 „Knuckleline“"
        self.assertTrue(ge.BUDGET_CONSUMER.startswith(knuckleline))
        self.assertIn("device 20000, world 10000", ge.BUDGET_CONSUMER)
        for text in (ge.SHARED_ARM_CONSUMER, ego_arms.SHARED_ARM_CONSUMER):
            self.assertTrue(text.startswith(knuckleline), text)
            self.assertNotIn("offen", text)
        self.assertEqual(knuckleline, ge.consumer_block(TOOLS["assault_rifle"], 5)["shared_arm_rig"][:len(knuckleline)])

    def test_foreign_packages_are_named_not_deleted(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            for name in ("scout_rifle", "trace_rifle", "logs"):
                (output / name).mkdir()
            (output / "scout_rifle/manifest.json").write_text("{}")
            (output / "trace_rifle/manifest.json").write_text("{}")
            self.assertEqual(["scout_rifle"], foreign_packages(output))
            self.assertTrue((output / "scout_rifle").is_dir())

    def test_no_current_file_names_the_old_id(self):
        """Only the history (CHANGELOG, version reports), this test and the renamed_from block may name scout_rifle."""
        allowed = {"CHANGELOG.md", "data/tools.json", "tests/test_rename.py", "toolgen/game_export.py",
                   "toolgen/generate_tools.py", "toolgen/README.md", "docs/ENTSCHEIDUNGEN.md", "docs/TECHNIK.md",
                   "docs/UNITY_EINBAU.md"}
        found = []
        for folder in ("data", "scripts", "tests", "toolgen", "viewer", "docs", ".agents"):
            for path in (ROOT / folder).rglob("*"):
                relative = path.relative_to(ROOT).as_posix()
                if (not path.is_file() or path.suffix not in {".py", ".json", ".md", ".swift", ".sh"}
                        or relative.startswith(("docs/versions/", "docs/archive/")) or relative in allowed):
                    continue
                text = path.read_text(errors="ignore")
                if "scout_rifle" in text or "ScoutRifle" in text:
                    found.append(relative)
        self.assertEqual([], found)


if __name__ == "__main__":
    unittest.main()
