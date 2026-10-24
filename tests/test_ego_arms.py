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
        # 0.19 pilots; 0.24 Salvo: group 1 of the animation brief (SMG, pulse rifle, scout rifle)
        self.assertEqual({"assault_rifle", "portal_emitter", "smg", "pulse_rifle", "scout_rifle", "pistol"}, set(DEVICES))
        self.assertEqual(set(DEVICES), rig_devices())
        self.assertEqual({tool for tool, entry in tools.items() if game_contract(entry) >= RIG_CONTRACT}, set(DEVICES))

    def test_grip_modes(self):
        self.assertEqual("support", DEVICES["assault_rifle"]["grip"]["L"]["mode"])
        self.assertEqual("wrap", DEVICES["portal_emitter"]["grip"]["L"]["support_grip"])   # the left hand wraps the body
        for device in DEVICES.values():
            self.assertTrue(device["grip"]["R"]["pose"] in ego_arms.pose_library(RIG))

    def test_reload_events_follow_the_action_contract(self):
        for tool, device in DEVICES.items():
            if "reload" in device:
                with self.subTest(tool=tool):
                    self.reload_events(device)
        self.assertNotIn("ReloadEmpty", DEVICES["smg"]["reload"], "KG06 draws no bolt: no other work when empty")
        self.assertNotIn("ReloadEmpty", DEVICES["pulse_rifle"]["reload"], "KG03 swaps an energy cell, no bolt")

    def reload_events(self, device):
        reload = device["reload"]
        held = next(iter(device["hand_parts"].values()))["grip"]       # the grip that holds the magazine / cell
        for name in [key for key in ("Reload", "ReloadEmpty") if key in reload]:
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
            self.assertEqual(held, left[events["MagOut"]])
            self.assertEqual(held, left[events["MagIn"]])
            # 0.24 (animation brief § 8): first move, Ready (the real release) and Still (the model rests) apart
            if "Still" in events:
                self.assertEqual(1, events["Move"])
                self.assertLess(events["Ready"], events["Still"])
                self.assertLess(events["Still"], spec["length"])
                self.assertEqual(events["Still"], spec["weapon"][-1][0], "the weapon rests from Still on")
        if "ReloadEmpty" in reload:
            empty = reload["ReloadEmpty"]["events"]
            self.assertLess(empty["MagIn"], empty["Chamber"])
            self.assertLess(empty["Chamber"], empty["HandOn"])
            self.assertNotIn("Chamber", reload["Reload"]["events"])

    def test_reload_paths_go_around_the_rifle(self):
        # Toolgen 0.19 Mac acceptance: a straight path between two grips (handguard -> magazine, magazine -> charging
        # handle) ran through the rifle; at least one clearance key (offset from a grip) lies between two grips
        for tool, device in DEVICES.items():
            if "reload" in device:
                with self.subTest(tool=tool):
                    self.reload_paths(device["reload"])
                    # 0.27: an inspect choreography (the pistol's press-check) follows the same path rules
                    self.reload_paths(device.get("inspect", {}), list(device.get("inspect", {})))

    def reload_paths(self, reload, names=("Reload", "ReloadEmpty")):
        for name in [key for key in names if key in reload]:
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
                # the hand holds the part (its grip: "bolt", 0.27 the bolt's own "grip") through every pull; a part let go
                # may run home by itself (the pistol's slide snaps forward after Chamber)
                grip = bolt.get("grip", "bolt")
                held = [frame for frame, key in spec["left"]
                        if key == grip or (isinstance(key, dict) and key["from"] == grip)]
                pulls = [(a, b) for (a, va), (b, vb) in zip(bolt["keys"], bolt["keys"][1:]) if vb > va]
                self.assertTrue(pulls, name)
                self.assertLessEqual(min(held), pulls[0][0])
                self.assertGreaterEqual(max(held), pulls[-1][1])

    def test_reload_times_cite_a_named_destiny_example(self):
        self.assertIn("Chroma Rush", DATA["devices"]["note"])
        self.assertIn("z-chroma-rush", DATA["devices"]["note"])
        # 0.24: each device of group 1 names its examples (motiongen docs/destiny2.md)
        for tool, example in (("smg", "Extraordinary Rendition"), ("pulse_rifle", "Gridskipper"), ("scout_rifle", "Tone Patrol")):
            self.assertIn(example, DEVICES[tool]["timing_note"], tool)


class FireClipTests(unittest.TestCase):
    """0.24 Salvo: the fire mechanics of a device are data (devices.<tool>.fire) with one Shot per real shot."""

    def clips(self, tool_id):
        tool = next(tool for tool in catalog() if tool["id"] == tool_id)
        profile = json.loads((ROOT / "data/viewmodels.json").read_text())["tools"][tool_id]
        return {clip["suffix"]: clip for clip in ego_arms.clip_list_v5(tool, profile, DEVICES[tool_id])[0]}

    def test_held_fire_is_a_loop_of_real_shots(self):
        fire = DEVICES["smg"]["fire"]
        self.assertEqual("auto", fire["mode"])
        self.assertEqual(round(60 * 24 / fire["cycle_frames"]), fire["cadence_rpm"])      # 720/min = 2 frames at 24/s
        clips = self.clips("smg")
        for suffix, pose in (("AutoFire", "rest"), ("AimAutoFire", "aim")):
            clip = clips[suffix]
            self.assertTrue(clip["loop"])
            self.assertEqual((pose, pose), (clip["from"], clip["to"]))
            shots = [event["frame"] - clip["frame_start"] for event in clip["events"] if event["name"] == "Shot"]
            self.assertEqual(list(range(0, clip["length"], fire["cycle_frames"])), shots)
        self.assertEqual(["AutoFire", "AimAutoFire"], list(clips)[-2:], "new clips only at the end")

    def test_burst_has_count_shots_and_its_end_ready_and_still_apart(self):
        fire = DEVICES["pulse_rifle"]["fire"]
        self.assertEqual(("burst", 3), (fire["mode"], fire["count"]))       # user decision 22.10.2026: three pulses
        clips = self.clips("pulse_rifle")
        for suffix in ("Burst", "AimBurst"):
            clip = clips[suffix]
            self.assertFalse(clip["loop"])
            events = [(event["name"], event["frame"] - clip["frame_start"]) for event in clip["events"]]
            shots = [frame for name, frame in events if name == "Shot"]
            self.assertEqual([0, 2, 4], shots)
            named = dict((name, frame) for name, frame in events if name != "Shot")
            self.assertEqual(shots[-1], named["BurstEnd"])
            self.assertEqual((0, 1), (named["Start"], named["Move"]))      # input = first shot, first move one frame later
            self.assertLess(named["BurstEnd"], named["Ready"])
            self.assertLess(named["Ready"], named["Still"])
            self.assertLess(named["Still"], named["End"])
            self.assertEqual(clip["length"], named["End"])
        self.assertEqual(["Burst", "AimBurst"], list(clips)[-2:])

    def test_fire_block_is_the_device_data_in_seconds(self):
        """The contract block fire (game_export_rig): clips, shot interval and the burst's Ready/Still from the device data."""
        for tool_id, shots in (("smg", "held"), ("pulse_rifle", 3)):
            clips = self.clips(tool_id)
            fire = DEVICES[tool_id]["fire"]
            entries = [{"name": clip["name"], "suffix": suffix} for suffix, clip in clips.items()]
            block = ego_arms.fire_block(fire, entries, 24)
            with self.subTest(tool=tool_id):
                self.assertEqual(shots, block["shots_per_trigger"])
                self.assertEqual([clips[s]["name"] for s, _, _ in ego_arms.FIRE_CLIPS[fire["mode"]]], block["clips"])
                self.assertAlmostEqual(2 / 24, block["shot_interval_seconds"], places=6)
                if fire["mode"] == "burst":
                    self.assertAlmostEqual(fire["ready_frame"] / 24, block["ready_seconds"], places=6)
                    self.assertLess(block["ready_seconds"], block["still_seconds"])
                else:
                    self.assertEqual(720, block["cadence_rpm"])

    def test_fire_poses_keep_their_named_ends(self):
        sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
        import ego_clips
        for tool_id in ("smg", "pulse_rifle"):
            tool = next(tool for tool in catalog() if tool["id"] == tool_id)
            profile = json.loads((ROOT / "data/viewmodels.json").read_text())["tools"][tool_id]
            clips, params = ego_arms.clip_list_v5(tool, profile, DEVICES[tool_id])
            for clip in clips:
                if not clip.get("shots"):
                    continue
                with self.subTest(clip=clip["name"]):
                    for frame, name in ((clip["frame_start"], clip["from"]), (clip["frame_end"], clip["to"])):
                        self.assertLess(ego_clips.pose_error(ego_clips.pose_at(clip, frame, params),
                                                             ego_clips.named_pose(name, params)), 1e-9)
                    # every shot moves the model (the series is readable shot by shot)
                    for shot in clip["shots"]:
                        moved = ego_clips.pose_at(clip, clip["frame_start"] + shot + 1, params)
                        self.assertGreater(abs(moved["pitch"]) + abs(moved["back"]) * 1000, .2)

    def test_aim_clips_follow_the_ads_rule_for_every_device(self):
        """0.24 let only a scope's grip hand leave the aim frame (ads.hands_may_leave). 0.25 (user decision 23.10.2026,
        Destiny 2 shows no hands while aiming): the framing rule does not hold in the aim clips of any device
        (ego_rig.AIM_MOTIONS), so there is no per-device exception left - one truth, in ego_rig - and every ads block has
        the eye distance of its sight kind (holo/reflex window 30 %, scope eyepiece 65 % of the picture height)."""
        import ast
        sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
        import ego_clips
        source = (ROOT / "toolgen/ego_rig.py").read_text()          # bpy module: read, not imported
        assigned = next(node.value for node in ast.parse(source).body if isinstance(node, ast.Assign)
                        and getattr(node.targets[0], "id", None) == "AIM_MOTIONS")
        aimed = {entry["motion"] for entry in ego_clips.load()["clips"] if "aim" in (entry["from"], entry["to"])}
        aimed |= {motion for pair in ego_arms.FIRE_CLIPS.values() for _, motion, pose in pair if pose == "aim"}
        self.assertEqual(aimed, set(ast.literal_eval(assigned)), "every clip from or to the aim pose")
        self.assertNotIn("hands_may_leave", source)
        tools = {tool["id"]: tool for tool in catalog()}
        for tool_id, device in DEVICES.items():
            with self.subTest(tool=tool_id):
                self.assertNotIn("hands_may_leave", device.get("ads", {}))
                if "ads" in device:
                    kind = tools[tool_id]["hold"]["sight_kind"]
                    self.assertLessEqual(device["ads"]["eye_distance_m"], .06 if kind == "scope" else .21)

    def test_scope_markers_and_lens_lead(self):
        clips = self.clips("scout_rifle")
        aim_in = {event["name"]: event["frame"] - clips["AimIn"]["frame_start"] for event in clips["AimIn"]["events"]}
        aim_out = {event["name"]: event["frame"] - clips["AimOut"]["frame_start"] for event in clips["AimOut"]["events"]}
        self.assertLess(aim_in["ScopeOn"], aim_in["Aimed"])
        self.assertEqual((0, 1), (aim_out["ScopeOff"], aim_out["Move"]))
        self.assertEqual("ReloadEmpty", list(clips)[-1])
        self.assertIn("Chamber", [event["name"] for event in clips["ReloadEmpty"]["events"]])


class SidearmClipTests(unittest.TestCase):
    """0.27 Sidearm: the pistol KG01 - semi-automatic Fire markers, the slide lock clips and the press-check (user decisions
    24.10.2026)."""

    def clips(self):
        return FireClipTests.clips(self, "pistol")

    def frames(self, clip):
        return {event["name"]: event["frame"] - clip["frame_start"] for event in clip["events"]}

    def test_semi_automatic_fire_has_ready_at_the_cadence(self):
        fire = DEVICES["pistol"]["fire"]
        self.assertEqual(("semi", 360, 15), (fire["mode"], fire["cadence_rpm"], fire["magazine_rounds"]))
        self.assertEqual(60 * 24 // fire["cadence_rpm"], fire["ready_frame"])     # 360/min = 4 frames at 24/s
        for suffix in ("Fire", "AimFire", "FireLast", "AimFireLast"):
            clip = self.clips()[suffix]
            frames = self.frames(clip)
            with self.subTest(clip=suffix):
                self.assertEqual("Start", clip["events"][0]["name"])
                self.assertEqual([0], [event["frame"] - clip["frame_start"] for event in clip["events"]
                                       if event["name"] == "Shot"])
                self.assertEqual((0, 1, 4, 7, clip["length"]),
                                 (frames["Start"], frames["Move"], frames["Ready"], frames["Still"], frames["End"]))
        entries = [{"name": clip["name"], "suffix": suffix} for suffix, clip in self.clips().items()]
        block = ego_arms.fire_block(fire, entries, 24)
        self.assertEqual(("semi", 1, 4), (block["mode"], block["shots_per_trigger"], block["shot_interval_frames"]))
        self.assertEqual(["Pistol_Fire", "Pistol_AimFire", "Pistol_FireLast", "Pistol_AimFireLast"], block["clips"])

    def test_slide_lock_clips_come_last_and_hold_the_slide(self):
        lock = DEVICES["pistol"]["slide_lock"]
        clips = self.clips()
        self.assertEqual(["FireLast", "AimFireLast", "SlideLocked"], list(clips)[-3:], "new clips only at the end")
        self.assertEqual(["Reload", "ReloadEmpty"], [s for s in clips if s.startswith("Reload")])
        for suffix in ("FireLast", "AimFireLast"):
            keys = clips[suffix]["slide_keys"]["keys"]
            self.assertEqual(0.0, keys[0][1])
            self.assertEqual(lock["locked_m"], keys[-1][1])
            self.assertEqual(clips[suffix]["length"], keys[-1][0])
            self.assertEqual(keys[-2][0], self.frames(clips[suffix])["SlideLock"])
        state = clips["SlideLocked"]
        self.assertTrue(state["loop"])
        self.assertEqual(["Anim_Slide"], state["mask"])
        self.assertEqual([[0, lock["locked_m"]], [state["length"], lock["locked_m"]]], state["slide_keys"]["keys"])
        # ReloadEmpty starts with the slide back and closes it right after Chamber
        empty = DEVICES["pistol"]["reload"]["ReloadEmpty"]
        self.assertEqual(lock["locked_m"], empty["bolt"]["keys"][0][1])
        self.assertEqual(0.0, empty["bolt"]["keys"][-1][1])
        self.assertLessEqual(empty["events"]["Chamber"], empty["bolt"]["keys"][-1][0])
        block = ego_arms.slide_lock_block(lock, [{"name": clip["name"], "suffix": suffix} for suffix, clip in clips.items()], 24)
        # Codex sol 0.27: the overlay stops when ReloadEmpty starts (its own slide track), an interruption before Chamber
        # leaves the slide locked
        self.assertEqual(("Pistol_SlideLocked", {"clip": "Pistol_ReloadEmpty", "event": "Chamber", "own_track": True,
                                                 "interrupted_before_event": "Pistol_SlideLocked"}),
                         (block["state"], block["release"]))
        self.assertIn("not over ReloadEmpty", block["rule"])

    def test_reload_times_follow_the_decision(self):
        reload = DEVICES["pistol"]["reload"]
        self.assertAlmostEqual(1.1, reload["Reload"]["events"]["Ready"] / 24, delta=.05)        # Reload about 1.1 s
        self.assertAlmostEqual(1.5, reload["ReloadEmpty"]["events"]["Ready"] / 24, delta=.05)   # ReloadEmpty about 1.5 s

    def test_press_check_is_an_inspect_choreography(self):
        clip = self.clips()["Inspect_B"]
        spec = DEVICES["pistol"]["inspect"]["Inspect_B"]
        self.assertEqual("inspect5", clip["motion"])
        self.assertIs(spec, ego_arms.choreography(DEVICES["pistol"], clip))
        frames = self.frames(clip)
        self.assertLess(frames["HandOff"], frames["PressCheck"])
        self.assertLess(frames["PressCheck"], frames["HandOn"])
        travel = max(value for _, value in spec["bolt"]["keys"])
        scale = DEVICES["pistol"]["tool_scale"] * RIG["scale"]
        self.assertAlmostEqual(.008, travel / scale, places=4)               # 8 mm on the model (decision 5 A)
        self.assertEqual(96, clip["length"])
        self.assertEqual("inspect_a", self.clips()["Inspect_A"]["motion"])   # the other side stays the class motion

    def test_cup_grip(self):
        grip = DEVICES["pistol"]["grip"]
        self.assertEqual(("cup", "cup"), (grip["L"]["mode"], grip["L"]["support_grip"]))
        # thumbs up the grip: the left hand's axis (little-finger side) runs down the right hand's axis
        self.assertAlmostEqual(-1.0, sum(a * b for a, b in zip(grip["L"]["axis"], grip["R"]["axis"])), places=3)


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
            with_contract([self.tool("shotgun")], 5)          # 0.27: the pistol is a contract 5 device now

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
