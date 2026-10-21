import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ego_clip_table


class EgoClipTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.tools = ego_clip_table.resolved()

    def test_document_is_current(self):
        self.assertEqual(ego_clip_table.main(["--check"]), 0)

    def test_use_is_first_table_row(self):
        markdown = ego_clip_table.render_markdown(self.data, self.tools)
        table = markdown.split("## Clips je Klasse", 1)[1]
        rows = [line for line in table.splitlines() if line.startswith("| ")]
        self.assertTrue(rows[1].startswith("| Use |"))
        self.assertIn("97", rows[1])

    def test_clip_counts_by_kind(self):
        for tool_id in ego_clip_table.WEAPON_ORDER:
            # 0.11.0: the fusion rifle adds its Charge loop (T3); 0.19: the contract 5 assault rifle its ReloadEmpty
            self.assertEqual(len(self.tools[tool_id]["clips"]), 16 if tool_id in ("fusion_rifle", "assault_rifle") else 15, tool_id)
        for tool_id in ego_clip_table.TOOL_ORDER:
            # 0.15.0: Inspect_B for the three ego tools, not the bow
            self.assertEqual(len(self.tools[tool_id]["clips"]), 8 if tool_id == "bow" else 9, tool_id)

    def test_only_expected_clips_loop(self):
        expected = {"Idle", "Walk", "Sprint", "AimIdle"}
        for tool_id, item in self.tools.items():
            loops = {clip["suffix"] for clip in item["clips"] if clip["loop"]}
            wanted = expected if tool_id in ego_clip_table.WEAPON_ORDER else expected - {"AimIdle"}
            self.assertEqual(loops, wanted | ({"Charge"} if tool_id == "fusion_rifle" else set()), tool_id)


if __name__ == "__main__":
    unittest.main()
