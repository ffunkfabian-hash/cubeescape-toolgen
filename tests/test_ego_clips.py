"""Ego clips of the first-person models: clip list, timeline, exact pose boundaries, loops, contract entries."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
sys.path.insert(0, str(ROOT / "toolgen"))

import ego_clips  # noqa: E402
import game_export as ge  # noqa: E402

DATA = ego_clips.load()
TOOLS = {tool["id"]: tool for tool in json.loads((ROOT / "data/tools.json").read_text())["tools"]}
PROFILES = json.loads((ROOT / "data/viewmodels.json").read_text())["tools"]
WEAPONS = [tool_id for tool_id, tool in TOOLS.items() if tool.get("hold")]
EGO_TOOLS = ("portal_emitter", "magnet_gripper", "flashlight")   # 0.15.0 Toolgrip: arm_pose, Use event, Inspect_B


def clips_of(tool_id, tool=None):
    return ego_clips.clip_list(DATA, tool or TOOLS[tool_id], PROFILES[tool_id].get("motion"))


class ClipListTests(unittest.TestCase):
    def test_weapons_and_tools_get_their_clip_sets(self):
        self.assertEqual(9, len(WEAPONS))
        for tool_id in TOOLS:
            clips, _ = clips_of(tool_id)
            suffixes = [clip["suffix"] for clip in clips]
            self.assertEqual((16 if tool_id == "fusion_rifle" else 15) if tool_id in WEAPONS else 9 if tool_id in EGO_TOOLS else 8,
                             len(clips), tool_id)
            self.assertEqual(len(set(suffixes)), len(suffixes), tool_id)
            for wanted in ("Idle", "Walk", "Sprint", "Draw", "Holster", "Inspect_A"):
                self.assertIn(wanted, suffixes, tool_id)
            if tool_id in WEAPONS:
                for wanted in ("Fire", "AimIn", "AimIdle", "AimOut", "Reload", "Inspect_B"):
                    self.assertIn(wanted, suffixes, tool_id)

    def test_names_follow_the_use_clip(self):
        for tool_id, tool in TOOLS.items():
            stem = (tool.get("fps_clip") or tool["clip"])[:-len("_Use")]
            for clip in clips_of(tool_id)[0]:
                self.assertEqual(stem + "_" + clip["suffix"], clip["name"])

    def test_timeline_follows_the_use_clip_without_overlap(self):
        for tool_id in TOOLS:
            clips, _ = clips_of(tool_id)
            self.assertGreater(clips[0]["frame_start"], 97)
            for first, second in zip(clips, clips[1:]):
                self.assertGreater(second["frame_start"], first["frame_end"] + 1, tool_id)
            for clip in clips:
                self.assertEqual(clip["length"], clip["frame_end"] - clip["frame_start"])
                for event in clip["events"]:
                    self.assertTrue(clip["frame_start"] <= event["frame"] <= clip["frame_end"], (clip["name"], event))
                self.assertIs(ego_clips.clip_at(clips, clip["frame_start"]), clip)
            self.assertIsNone(ego_clips.clip_at(clips, 97))

    def test_only_idle_walk_sprint_and_aim_idle_loop(self):
        for tool_id in TOOLS:
            loops = {clip["suffix"] for clip in clips_of(tool_id)[0] if clip["loop"]}
            # Charge (fusion rifle, 0.11.0): a state like Idle, started and stopped by Cube Escape (task of 16.10.2026)
            self.assertEqual({"Idle", "Walk", "Sprint"} | ({"AimIdle"} if tool_id in WEAPONS else set())
                             | ({"Charge"} if tool_id == "fusion_rifle" else set()), loops)

    def test_charge_is_last_so_earlier_frame_ranges_stay(self):
        data = ego_clips.load()
        for tool_id in WEAPONS:
            clips, _ = clips_of(tool_id)
            if tool_id != "fusion_rifle":
                self.assertNotIn("Charge", [clip["suffix"] for clip in clips])
                continue
            self.assertEqual("Charge", clips[-1]["suffix"])
            without = dict(data, clips=[entry for entry in data["clips"] if entry["suffix"] != "Charge"])
            before, _ = ego_clips.clip_list(without, TOOLS[tool_id], PROFILES[tool_id]["motion"])
            self.assertEqual([(c["name"], c["frame_start"], c["frame_end"]) for c in before],
                             [(c["name"], c["frame_start"], c["frame_end"]) for c in clips[:-1]])
            charge = clips[-1]
            self.assertEqual(["ChargeCycle"], [event["name"] for event in charge["events"]])
            params = ego_clips.class_params(data, tool_id, PROFILES[tool_id]["motion"])
            self.assertEqual(1.0, ego_clips.pose_at(charge, charge["frame_end"], params)["spin"], "one coil turn per loop")

    def test_fingers_move_and_rest_at_clip_ends(self):
        """T5: the trigger finger lifts in Fire/AimFire, the support fingers open in Reload (support hand released)."""
        for tool_id in WEAPONS:
            clips, params = clips_of(tool_id)
            for clip in clips:
                values = [ego_clips.pose_at(clip, frame, params) for frame in range(clip["frame_start"], clip["frame_end"] + 1)]
                with self.subTest(tool=tool_id, clip=clip["suffix"]):
                    for key in ("trigger", "regrip"):
                        self.assertEqual(0.0, values[0][key])
                        self.assertEqual(0.0, values[-1][key])
                        self.assertTrue(all(0 <= value[key] <= 1 for value in values))
                    trigger = max(value["trigger"] for value in values)
                    regrip = max(value["regrip"] for value in values)
                    self.assertEqual(clip["motion"] in ("fire", "aim_fire"), trigger > .99)
                    self.assertEqual(clip["motion"] == "reload" and params["reload"]["support"], regrip > .99)
                    if regrip:          # open only around the release window, closed while gripping the handguard
                        for value in values:
                            if value["regrip"] > 0:
                                self.assertTrue(value["detached"] or value["support"] is not None)

    def test_fire_follows_the_recoil_profile(self):
        for tool_id in WEAPONS:
            clips, params = clips_of(tool_id)
            motion = PROFILES[tool_id]["motion"]
            fire = next(clip for clip in clips if clip["suffix"] == "Fire")
            natural = max(motion["fire_frame"] + motion["recovery_frames"], params.get("fire_end_frame", 0)) - params["fire_start"]
            self.assertEqual(motion["fire_frame"] - 1, params["fire_start"])          # no charge in Fire (fusion: later clip)
            self.assertEqual(min(natural, int(params["fire_cooldown_s"] * DATA["fps"])), fire["length"])
            self.assertLessEqual(fire["length"] / DATA["fps"], params["fire_cooldown_s"])   # the next shot restarts it
            shot = fire["events"][0]
            self.assertEqual("Shot", shot["name"])
            pose = ego_clips.pose_at(fire, shot["frame"] + 1, params)
            self.assertGreater(pose["back"], 0, tool_id)        # kick towards the player after the shot

    def test_colour_and_material_do_not_change_a_clip(self):
        for tool_id in WEAPONS:
            plain = {key: value for key, value in TOOLS[tool_id].items() if key not in ("materials", "element")}
            self.assertEqual(clips_of(tool_id), clips_of(tool_id, plain))


class EgoToolTests(unittest.TestCase):
    """Toolgen 0.15.0 Toolgrip (Cube Escape 0.85 phase 4): the three ego tools as the weapons since 0.9-0.13."""

    def test_ego_tools_are_the_tools_with_a_use_event(self):
        self.assertEqual(set(EGO_TOOLS), {tool_id for tool_id, profile in PROFILES.items() if profile.get("use_event")})
        self.assertEqual({"portal_emitter": "Fire", "magnet_gripper": "Grab", "flashlight": "Switch"},
                         {tool_id: PROFILES[tool_id]["use_event"]["name"] for tool_id in EGO_TOOLS})
        for tool_id in EGO_TOOLS:
            self.assertTrue(1 < PROFILES[tool_id]["use_event"]["frame"] < 97, tool_id)

    def test_every_ego_tool_arm_has_the_wrist_limit(self):
        for tool_id in EGO_TOOLS:
            profile = PROFILES[tool_id]
            arms = {"R", "L"} if profile["support"] else {"R"}
            self.assertEqual(arms, set(profile["arm_pose"]), tool_id)
            for side in arms:
                self.assertEqual(55, profile["arm_pose"][side]["max_wrist_bend_degrees"], (tool_id, side))
            self.assertIn("forearm", profile["arm_pose"]["R"], tool_id)     # the grip forearm is aimed, not the default
        self.assertNotIn("arm_pose", PROFILES["bow"])                       # the bow keeps its rig

    def test_inspect_b_for_the_ego_tools_only(self):
        for tool_id in TOOLS:
            clips, params = clips_of(tool_id)
            inspect_b = [clip for clip in clips if clip["suffix"] == "Inspect_B"]
            self.assertEqual(tool_id != "bow", bool(inspect_b), tool_id)
            if tool_id in EGO_TOOLS:
                clip = inspect_b[0]
                self.assertIs(clips[-1], clip, "after every earlier clip, so their frame ranges stay")
                self.assertEqual(("rest", "rest", False), (clip["from"], clip["to"], clip["loop"]))
                middle = ego_clips.pose_at(clip, clip["frame_start"] + clip["length"] // 2, params)
                inspect_a = next(entry for entry in clips if entry["suffix"] == "Inspect_A")
                other = ego_clips.pose_at(inspect_a, inspect_a["frame_start"] + inspect_a["length"] // 2, params)
                self.assertLess(middle["twist"] * other["twist"], 0, "Inspect_B cants the other way")

    def test_ego_tool_lowered_pose_drops(self):
        """Draw starts and Holster ends lower than the weapons' cant only (measured at Socket_Hand: qa_viewmodel.json)."""
        for tool_id in EGO_TOOLS:
            clips, params = clips_of(tool_id)
            lowered = ego_clips.named_pose("lowered", params)
            self.assertLessEqual(lowered["up"], -.008, tool_id)
            for suffix, frame in (("Draw", "frame_start"), ("Holster", "frame_end")):
                clip = next(entry for entry in clips if entry["suffix"] == suffix)
                self.assertLess(ego_clips.pose_error(ego_clips.pose_at(clip, clip[frame], params), lowered), 1e-9)

    def test_weapon_clips_unchanged_by_the_tool_entries(self):
        """The tool entries (Inspect_B for tools, tool classes) do not reach a weapon's clip list or parameters. Not a proof that
        the weapons are unchanged against 0.14 (defaults and weapon classes are not compared): that is compare_models.py."""
        data = json.loads(json.dumps(DATA))
        entry = next(entry for entry in data["clips"] if entry["suffix"] == "Inspect_B")
        entry["kinds"] = ["weapon"]
        del entry["except_tools"]
        for tool_id in EGO_TOOLS:
            data["classes"].pop(tool_id, None)
        for tool_id in WEAPONS:
            self.assertEqual(clips_of(tool_id), ego_clips.clip_list(data, TOOLS[tool_id], PROFILES[tool_id]["motion"]), tool_id)


class PoseTests(unittest.TestCase):
    def test_every_clip_starts_and_ends_in_its_named_pose(self):
        for tool_id in TOOLS:
            clips, params = clips_of(tool_id)
            for clip in clips:
                for frame, name in ((clip["frame_start"], clip["from"]), (clip["frame_end"], clip["to"])):
                    error = ego_clips.pose_error(ego_clips.pose_at(clip, frame, params), ego_clips.named_pose(name, params))
                    self.assertLess(error, 1e-9, (clip["name"], frame, name))

    def test_loops_are_seamless_and_move(self):
        for tool_id in TOOLS:
            clips, params = clips_of(tool_id)
            for clip in (clip for clip in clips if clip["loop"]):
                first = ego_clips.pose_at(clip, clip["frame_start"], params)
                last = ego_clips.pose_at(clip, clip["frame_end"], params)
                middle = ego_clips.pose_at(clip, clip["frame_start"] + clip["length"] // 4, params)
                self.assertLess(ego_clips.pose_error(first, last), 1e-9, clip["name"])
                self.assertGreater(ego_clips.pose_error(first, middle), 1e-4, clip["name"])

    def test_poses_change_smoothly(self):
        """No jump between neighbouring frames: at most 15 degrees or mm per frame on any axis (recoil: 40)."""
        for tool_id in TOOLS:
            clips, params = clips_of(tool_id)
            for clip in clips:
                limit = 40 if clip["motion"] in ("fire", "aim_fire") else 15
                previous = None
                for frame in range(clip["frame_start"], clip["frame_end"] + 1):
                    pose = ego_clips.pose_at(clip, frame, params)
                    if previous:
                        self.assertLess(ego_clips.pose_error(previous, pose), limit, (clip["name"], frame))
                    previous = pose

    def test_support_hand_moves_only_while_detached(self):
        for tool_id in WEAPONS:
            clips, params = clips_of(tool_id)
            for clip in clips:
                for frame in range(clip["frame_start"], clip["frame_end"] + 1):
                    pose = ego_clips.pose_at(clip, frame, params)
                    if pose["support"] and any(abs(value) > 1e-9 for value in pose["support"].values()):
                        self.assertTrue(pose["detached"], (clip["name"], frame))

    def test_transitions_are_pose_cuts(self):
        clips, _ = clips_of("assault_rifle")
        rules = {rule["clip"]: rule for rule in ego_clips.transitions(clips)}
        by_name = {clip["name"]: clip for clip in clips}
        for name, rule in rules.items():
            for follower in rule["next"]:
                self.assertEqual(by_name[name]["to"], by_name[follower]["from"])
        self.assertIn("AssaultRifle_AimIdle", rules["AssaultRifle_AimIn"]["next"])
        self.assertNotIn("AssaultRifle_AimIdle", rules["AssaultRifle_Idle"]["next"])


class ContractTests(unittest.TestCase):
    def test_ego_contract_entries(self):
        tool = TOOLS["shotgun"]
        clips, _ = clips_of("shotgun")
        ego = {"timeline_start": clips[0]["frame_start"], "timeline_end": ego_clips.timeline_end(clips), "clips": clips,
               "reload_part": "Anim_Magazine"}
        take = ge.ego_take_name(tool["fps_clip"])
        self.assertEqual("Shotgun_EgoClips", take)
        infos, block = ge.ego_contract(ego, "CubeEscape_Shotgun_FPS_Game", take, 24.0, ["Viewmodel_Motion"])
        self.assertEqual([clip["name"] for clip in clips], [info["name"] for info in infos])
        self.assertEqual(0, infos[0]["take_frame_start"])
        for info, clip in zip(infos, clips):
            self.assertEqual("CubeEscape_Shotgun_FPS_Game_Clips.fbx", info["file"])
            self.assertEqual(clip["length"] + 1, info["frames"])
            self.assertEqual(info["take_frame_end"] - info["take_frame_start"], clip["length"])
            self.assertAlmostEqual(clip["length"] / 24, info["duration_seconds"])
            self.assertFalse(info["autoplay"])
        self.assertEqual({clip["suffix"]: clip["name"] for clip in clips}, block["names"])
        self.assertEqual(set(DATA["poses"]), set(block["poses"]))
        self.assertIn("--contract 2", block["older_consumers"])

    def test_sample_frames_cover_ends_and_events(self):
        clips, _ = clips_of("pistol")
        frames = set(ge.ego_sample_frames(clips))
        for clip in clips:
            self.assertTrue({clip["frame_start"], clip["frame_end"], *(e["frame"] for e in clip["events"])} <= frames)

    def test_ego_clips_start_at_contract_three(self):
        self.assertEqual(4, ge.CONTRACT_FORMAT)          # 0.11: contract 4 (surface maps) keeps the ego clips
        self.assertEqual(3, ge.EGO_CLIPS_CONTRACT)


if __name__ == "__main__":
    unittest.main()
