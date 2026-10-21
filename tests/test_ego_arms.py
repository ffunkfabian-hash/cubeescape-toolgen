"""Contract 5 (Toolgen 0.19 Kinetic): the shared Ego arm rig, its data and its place in the pipeline (no Blender)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
import ego_arms  # noqa: E402
from generate_tools import (ARMS, ARMS_ROOT, ARMS_STAGES, RIG_CONTRACT, STAGES, catalog, declaration, expand,  # noqa: E402
                            game_contract, rig_devices, variants, with_arms, with_contract)

DATA = ego_arms.load()
RIG = DATA["rig"]
DEVICES = {key: value for key, value in DATA["devices"].items() if key != "note"}
BUDGET = json.loads((ROOT / "data/game_budget.json").read_text())


class RigDataTests(unittest.TestCase):
    def test_nodes_are_the_draft_skeleton(self):
        names = ego_arms.node_names("R")
        # rig version 2 (user, 21.10.2026): cardan wrist - WristYoke_ between forearm and hand
        self.assertEqual(["Shoulder_R", "UpperArm_R", "LowerArm_R", "WristYoke_R", "Hand_R", "Wrist_R", "GripContact_R",
                          "Prop_R"], names[:8])
        self.assertIn("Fingers_R_0", names)
        self.assertIn("Fingers_R_2_2", names)
        self.assertIn("Thumb_R_1", names)
        self.assertEqual(3, ego_arms.FINGERS)                      # three gripping fingers + thumb (user, 20.10.2026)
        self.assertEqual(8 + 3 * 3 + 2, len(names))
        self.assertEqual(2 + 2 * len(names), len(ego_arms.all_nodes(RIG["asset"])))
        renderers = [node for side in ego_arms.SIDES for node in ego_arms.moving_nodes(side)]
        self.assertEqual(RIG["max_renderers"], len(renderers))     # 28: no mesh on the upper arm, one on the yoke

    def test_budget_and_scale(self):
        self.assertEqual(12000, RIG["budget_triangles"])
        self.assertEqual(1.4, RIG["scale"])
        for tool in DEVICES:
            self.assertLessEqual(BUDGET["viewmodel"][tool] + RIG["budget_triangles"], 32000)
        measures = ego_arms.measures(RIG, json.loads((ROOT / "data/viewmodels.json").read_text())["arm"])
        self.assertAlmostEqual(.65 * 1.4, measures["hand_scale"])

    def test_four_look_slots(self):
        self.assertEqual(["armor", "mech", "metal", "lights"], list(ego_arms.LOOK_SLOTS.values()))
        palette = json.loads((ROOT / "data/game_palette.json").read_text())["materials"]
        for name in ego_arms.LOOK_SLOTS:
            self.assertIn(name, palette)

    def test_finger_poses_stay_in_their_joint_limits(self):
        library = ego_arms.pose_library(RIG)
        for name in ("open", "grip", "regrip", "trigger", "underhand", "cup", "wrap", "mag_hold", "pinch"):
            self.assertIn(name, library)                            # the draft's names (permanent, append only)
            self.assertEqual([], ego_arms.limit_errors(RIG, name, library[name]))

    def test_wrapped_fingers_curl_more_around_a_thinner_grip(self):
        limits = RIG["limits_degrees"]["finger"]
        thin, thick = (sum(ego_arms.wrap_finger(RIG["hand"], radius, limits)) for radius in (.025, .045))
        self.assertGreater(thin, thick)

    def test_rig_hash_follows_the_skeleton_only(self):
        entry = [("Hand_R", "LowerArm_R", (0, 0, .42), (1, 0, 0, 0), (1, 1, 1))]
        moved = [("Hand_R", "LowerArm_R", (0, 0, .43), (1, 0, 0, 0), (1, 1, 1))]
        self.assertEqual(ego_arms.rig_hash(entry), ego_arms.rig_hash(list(entry)))
        self.assertNotEqual(ego_arms.rig_hash(entry), ego_arms.rig_hash(moved))
        self.assertEqual(ego_arms.rig_hash(entry), ego_arms.rig_hash([("Hand_R", "LowerArm_R", (0, 0, .4200000001),
                                                                       (1, 0, 0, 0), (1, 1, 1))]))

    def test_thumb_frames_are_mirrored(self):
        right, left = ego_arms.thumb_frame(RIG["hand"], "R"), ego_arms.thumb_frame(RIG["hand"], "L")
        self.assertAlmostEqual(right[2][0], -left[2][0])           # +Z of the thumb: mirrored in X
        self.assertAlmostEqual(right[2][2], left[2][2])


class DeviceDataTests(unittest.TestCase):
    def test_pilots_are_the_contract_5_tools(self):
        tools = {tool["id"]: tool for tool in catalog()}
        self.assertEqual({"assault_rifle", "portal_emitter"}, set(DEVICES))
        self.assertEqual(set(DEVICES), rig_devices())
        self.assertEqual({tool for tool, entry in tools.items() if game_contract(entry) >= RIG_CONTRACT}, set(DEVICES))

    def test_grip_modes(self):
        self.assertEqual("support", DEVICES["assault_rifle"]["grip"]["L"]["mode"])
        self.assertEqual("wrap", DEVICES["portal_emitter"]["grip"]["L"]["support_grip"])   # the left hand wraps the body
        for device in DEVICES.values():
            self.assertTrue(device["grip"]["R"]["pose"] in ego_arms.pose_library(RIG))

    def test_reload_events_follow_the_action_contract(self):
        reload = DEVICES["assault_rifle"]["reload"]
        for name in ("Reload", "ReloadEmpty"):
            spec = reload[name]
            events = spec["events"]
            self.assertLess(events["HandOff"], events["MagOut"])
            self.assertLess(events["MagOut"], events["MagIn"])
            self.assertLess(events["MagIn"], events["HandOn"])
            self.assertLessEqual(events["MagIn"], events["Ready"])
            self.assertLess(max(events.values()), spec["length"])
            # the hand stays on its grip for the IK blend after HandOff and is back by HandOn
            left = dict((frame, key) for frame, key in spec["left"])
            self.assertTrue(all(left.get(frame, "support") == "support" for frame in range(events["HandOff"] + 3)
                                if frame in left))
            self.assertEqual("support", spec["left"][-1][1])
            self.assertLessEqual(spec["left"][-1][0], events["HandOn"])
            # the magazine swaps hands exactly where the hand holds it at the well
            self.assertEqual("mag", left[events["MagOut"]])
            self.assertEqual("mag", left[events["MagIn"]])
        empty = reload["ReloadEmpty"]["events"]
        self.assertLess(empty["MagIn"], empty["Chamber"])
        self.assertLess(empty["Chamber"], empty["HandOn"])
        self.assertNotIn("Chamber", reload["Reload"]["events"])

    def test_reload_paths_go_around_the_rifle(self):
        # Toolgen 0.19 Mac acceptance: a straight path between two grips (handguard -> magazine, magazine -> charging
        # handle) ran through the rifle; at least one clearance key (offset from a grip) lies between two grips
        reload = DEVICES["assault_rifle"]["reload"]
        for name in ("Reload", "ReloadEmpty"):
            spec = reload[name]
            for track in ("left", "fingers"):
                frames = [frame for frame, _ in spec[track]]
                self.assertEqual(sorted(set(frames)), frames, f"{name} {track}: keys strictly increasing")
            grips = [(index, key) for index, (_, key) in enumerate(spec["left"]) if isinstance(key, str)]
            for (a, grip_a), (b, grip_b) in zip(grips, grips[1:]):
                if grip_a != grip_b:
                    self.assertGreater(b - a, 1, f"{name}: no clearance key between {grip_a} and {grip_b}")
            bolt = spec.get("bolt")
            if bolt:
                held = [frame for frame, key in spec["left"]
                        if key == "bolt" or (isinstance(key, dict) and key["from"] == "bolt")]
                self.assertLessEqual(min(held), bolt["keys"][0][0])
                self.assertGreaterEqual(max(held), bolt["keys"][-1][0])

    def test_reload_times_cite_a_named_destiny_example(self):
        self.assertIn("Chroma Rush", DATA["devices"]["note"])
        self.assertIn("z-chroma-rush", DATA["devices"]["note"])


class PipelineTests(unittest.TestCase):
    def tool(self, tool_id):
        return next(tool for tool in catalog() if tool["id"] == tool_id)

    def test_contract_5_runs_replace_the_baked_arm_stages(self):
        runs = [run.name for run in expand(self.tool("assault_rifle"), "standard")]
        self.assertIn("ego_rig", runs)
        self.assertIn("game_fps_rig", runs)
        for name in ("first_person", "viewmodel_roundtrip", "game_fps", "roundtrip_fps"):
            self.assertNotIn(name, runs)
        self.assertLess(runs.index("ego_rig"), runs.index("game_fps_rig"))

    def test_contract_4_tools_keep_their_runs(self):
        for tool in catalog():
            if game_contract(tool) >= RIG_CONTRACT:
                continue
            runs = [run.name for run in expand(tool, "quick")]
            self.assertIn("first_person", runs)
            self.assertNotIn("ego_rig", runs)
            self.assertNotIn("game_fps_rig", runs)

    def test_new_stages_leave_old_declarations_alone(self):
        for stage in STAGES:
            if stage.name not in ("ego_rig", "game_fps_rig"):
                self.assertNotIn("replaces", declaration(stage))

    def test_way_back_is_contract_4(self):
        tools = catalog()
        back = with_contract(tools, 4)
        for old, new in zip(tools, back):
            self.assertNotIn("game_contract", new)
            if "game_contract" not in old:
                self.assertEqual(old, new)                         # same entry, same stage keys
        self.assertEqual(tools, with_contract(tools, None))
        with self.assertRaises(ValueError):
            with_contract([self.tool("pistol")], 5)

    def test_arm_package_joins_contract_5_runs(self):
        self.assertEqual(ARMS, with_arms(catalog(), None)[0])
        self.assertNotIn(ARMS, with_arms(with_contract(catalog(), 4), None))
        self.assertEqual([ARMS], with_arms([], ["ego_arms"]))
        runs = [run.name for run in expand(ARMS, "quick", ARMS_STAGES, ())]
        self.assertEqual(["ego_arms"], runs[:1])

    def test_contract_5_viewer_shows_the_assembly(self):
        found = {variant.name: variant for variant in variants(self.tool("portal_emitter"))}
        self.assertEqual(ARMS_ROOT, found["fps"].node)
        self.assertFalse(found["fps"].roundtrip)
        self.assertEqual((), found["fps_game"].clip)
        names = [variant.name for variant in variants(self.tool("portal_emitter"))]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
