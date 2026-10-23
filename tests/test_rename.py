"""Renamed tools (Toolgen 0.17 Retrace): the trace rifle was scout_rifle until 0.16 (user decision 19.10.2026).

tools.json ``renamed_from`` keeps the former names; the game contract carries them (game_export.renamed_block) and
generate_tools.py --tool accepts the former id while no tool carries it again. 0.24 Salvo: the new scout rifle (KG11)
carries the id scout_rifle again, so the trace rifle's renamed_from went (the rule of 0.17); its former asset and clip
names (CubeEscape_ScoutRifle, ScoutRifle_) stay unused, the scout rifle is CubeEscape_Scout / Scout_ (user decision
22.10.2026). Runs without Blender.
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
FORMER = {}                 # 0.24: scout_rifle names the scout rifle again
OLD_TRACE = {"id": "scout_rifle", "asset": "CubeEscape_ScoutRifle", "robot": "CubeEscape_ScoutRifle_Robot",
             "clip_stem": "ScoutRifle", "since": "0.17.0"}     # the trace rifle's renamed_from until 0.23


class RenamedFromTests(unittest.TestCase):
    def test_trace_rifle_was_scout_rifle(self):
        tool = TOOLS["trace_rifle"]
        self.assertEqual(("Spurgewehr", "CubeEscape_TraceRifle", "TraceRifle_Use", "CubeEscape_TraceRifle_Robot"),
                         (tool["label"], tool["asset"], tool["clip"], tool["robot"]))
        self.assertNotIn("renamed_from", tool, "0.24: a tool carries the former id again, the alias went")

    def test_the_new_scout_rifle_takes_none_of_the_trace_rifles_former_names(self):
        """0.24: the id came back for the scout rifle (KG11), but the old asset, robot and clip stem would be renamed to the
        trace rifle by a consumer that still applies the 0.17 map and would carry the trace rifle's GUIDs in an old
        project; the scout rifle has names of its own that contain none of them."""
        tool = TOOLS["scout_rifle"]
        self.assertEqual(("Scout-Gewehr", "CubeEscape_Scout", "Scout_Use", "CubeEscape_Scout_Robot", "KG11"),
                         (tool["label"], tool["asset"], tool["clip"], tool["robot"], tool["concept"]))
        for name in (tool["asset"], tool["robot"], tool["asset"] + "_FPS_Game", tool["clip"], "Scout_Fire"):
            for old in (OLD_TRACE["asset"], OLD_TRACE["robot"], OLD_TRACE["clip_stem"] + "_"):
                self.assertNotIn(old, name)

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
        tools = [dict(tool, renamed_from=OLD_TRACE) if tool["id"] == "trace_rifle" else tool
                 for tool in catalog() if tool["id"] != "scout_rifle"]       # the catalogue of 0.17-0.23
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(["trace_rifle", "pistol"], resolve_tool_ids(["scout_rifle", "pistol"], tools))
        self.assertIn("--tool trace_rifle", stderr.getvalue())
        self.assertEqual([], resolve_tool_ids(None))
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):                           # 0.24: the scout rifle, no warning
            self.assertEqual(["scout_rifle"], resolve_tool_ids(["scout_rifle"]))
        self.assertEqual("", stderr.getvalue())

    def test_alias_ends_when_a_tool_takes_the_id(self):
        tools = [dict(tool, renamed_from=OLD_TRACE) if tool["id"] == "trace_rifle" else tool for tool in catalog()]
        self.assertEqual({}, former_ids(tools))
        self.assertEqual(["scout_rifle"], resolve_tool_ids(["scout_rifle"], tools))

    def test_contract_block_maps_old_to_new(self):
        block = ge.renamed_block(dict(TOOLS["trace_rifle"], renamed_from=OLD_TRACE))
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
        self.assertEqual(block["renamed_tool_ids"],
                         ge.renamed_block(dict(TOOLS["trace_rifle"], renamed_from=OLD_TRACE))["minimum_consumer"])
        # 0.19: the contract format joins the call (contract 5 adds shared_arm_rig)
        self.assertIn('"minimum_consumer": consumer_block(tool, contract)', inspect.getsource(ge.build_contract))
        # 0.18: a concept weapon adds its own requirement, the others keep exactly the two
        self.assertEqual({"first_person_maps_2048", "renamed_tool_ids", "triangle_budgets", "concept_models"},
                         set(ge.consumer_block(TOOLS["assault_rifle"])))
        self.assertEqual(block, ge.consumer_block(TOOLS["pistol"]))
        self.assertIn("v0.17.2", ge.consumer_block(TOOLS["assault_rifle"])["concept_models"])
        # 0.24: the three tools of group 1 (tools.json animation_group 1) name the CE version that builds their clips
        for tool_id in ("smg", "pulse_rifle", "scout_rifle"):
            self.assertIn("group_1_clips", ge.consumer_block(TOOLS[tool_id], 5), tool_id)
            # 0.24: Sightline reserved Cube Escape 0.112 for building group 1 (no longer „offen“)
            self.assertTrue(ge.consumer_block(TOOLS[tool_id], 5)["group_1_clips"].startswith("Cube Escape 0.112 "), tool_id)
            self.assertNotIn("offen", ge.consumer_block(TOOLS[tool_id], 5)["group_1_clips"])
        self.assertNotIn("group_1_clips", ge.consumer_block(TOOLS["assault_rifle"], 5))
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
            for name in ("retired_tool", "trace_rifle", "logs"):
                (output / name).mkdir()
            (output / "retired_tool/manifest.json").write_text("{}")
            (output / "trace_rifle/manifest.json").write_text("{}")
            self.assertEqual(["retired_tool"], foreign_packages(output))
            self.assertTrue((output / "retired_tool").is_dir())

    def test_no_current_file_names_the_old_id(self):
        """Only the history (CHANGELOG, version reports), this test and the docs may name the trace rifle's former asset and
        clip names (0.24: the id scout_rifle is the scout rifle's, so only ScoutRifle is searched)."""
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
                if "ScoutRifle" in text:
                    found.append(relative)
        self.assertEqual([], found)


if __name__ == "__main__":
    unittest.main()
