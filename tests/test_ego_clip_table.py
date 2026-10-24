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
            # 0.11.0: the fusion rifle adds its Charge loop (T3); 0.19: the contract 5 assault rifle its ReloadEmpty; 0.24:
            # the scout rifle its ReloadEmpty, the SMG AutoFire/AimAutoFire, the pulse rifle Burst/AimBurst; 0.27 the pistol
            # ReloadEmpty, FireLast, AimFireLast and the state SlideLocked
            extra = {"fusion_rifle": 1, "assault_rifle": 1, "scout_rifle": 1, "smg": 2, "pulse_rifle": 2, "pistol": 4}
            self.assertEqual(len(self.tools[tool_id]["clips"]), 15 + extra.get(tool_id, 0), tool_id)
        for tool_id in ego_clip_table.TOOL_ORDER:
            # 0.15.0: Inspect_B for the three ego tools, not the bow
            self.assertEqual(len(self.tools[tool_id]["clips"]), 8 if tool_id == "bow" else 9, tool_id)

    def test_only_expected_clips_loop(self):
        expected = {"Idle", "Walk", "Sprint", "AimIdle"}
        for tool_id, item in self.tools.items():
            loops = {clip["suffix"] for clip in item["clips"] if clip["loop"]}
            wanted = expected if tool_id in ego_clip_table.WEAPON_ORDER else expected - {"AimIdle"}
            # state loops (user decisions): the fusion rifle's Charge, 0.24 the SMG's held fire (22.10.2026), 0.27 the
            # pistol's slide lock (24.10.2026)
            states = {"fusion_rifle": {"Charge"}, "smg": {"AutoFire", "AimAutoFire"}, "pistol": {"SlideLocked"}}.get(tool_id, set())
            self.assertEqual(loops, wanted | states, tool_id)


if __name__ == "__main__":
    unittest.main()
