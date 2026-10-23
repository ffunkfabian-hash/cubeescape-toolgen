"""The nine weapons (scripts/tool_assets/weapon_kit.py, weapon_designs.py): data consistency, anchors, Use clip, palette.

Pure Python: the design module and the kit are read without Blender (``ast`` for the kit and the build functions)."""
import ast
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "scripts/tool_assets"
sys.path.insert(0, str(ROOT / "toolgen"))
sys.path.insert(0, str(ASSETS))
sys.path.insert(0, str(ROOT / "tests"))

import concept_spec  # noqa: E402
import ego_clips  # noqa: E402
import game_export as ge  # noqa: E402
import sight  # noqa: E402
import weapon_designs as designs  # noqa: E402
from test_game_export import PALETTE, material_calls  # noqa: E402

TOOLS = {tool["id"]: tool for tool in json.loads((ROOT / "data/tools.json").read_text())["tools"]}
PROFILES = json.loads((ROOT / "data/viewmodels.json").read_text())["tools"]
BUDGET = json.loads((ROOT / "data/game_budget.json").read_text())
WEAPONS = {tool_id: tool for tool_id, tool in TOOLS.items() if tool.get("hold")}
ELEMENTS = {"kinetic": "PG_Kinetic", "energy": "PG_Cyan", "solar": "PG_Amber", "void": "PG_Void", "arc": "PG_Arc"}
LAUNCHERS = {"create_weapon.py": "world", "create_weapon_fps.py": "fps", "animate_weapon.py": "animate",
             "verify_weapon.py": "verify", "make_animation_preview.py": "make"}
SOCKETS = ("Socket_Hand", "Socket_Muzzle", "Socket_SupportHand", "Socket_CenterOfMass")


HELPERS = ("panel", "display", "energy_cell", "heat_sink", "accent", "side_armor")


def build_calls(key):
    """(method name, first string argument) of every ``k.<method>('Name', ...)`` call of the design's build function and
    of its ``<name>_modules`` function; the shared module helpers (panel, display ...) count as ``box`` with their name."""
    spec = designs.DESIGNS[key]
    if spec.get("concept"):
        # Toolgen 0.18: a concept weapon builds the sheet's meshes, the pivots of its nodes and the spec's sockets
        found = concept_spec.layout(spec["concept"], sorted({move["node"] for move in spec["use_clip"]}))
        return ([("box", mesh["name"].removeprefix("SM_PG_")) for mesh in found["meshes"]]
                + [("pivot", node) for node in found["pivots"]] + [("socket", name) for name in found["kit_sockets"]])
    tree = ast.parse((ASSETS / "weapon_designs.py").read_text())
    name = designs.DESIGNS[key]["build"].__name__
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in (name, name + "_modules")]
    calls = []
    for node in (child for function in functions for child in ast.walk(function)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in HELPERS
                and len(node.args) > 1 and isinstance(node.args[1], ast.Constant)):
            calls.append(("box", node.args[1].value))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "k" and node.args and isinstance(node.args[0], ast.Constant)):
            calls.append((node.func.attr, node.args[0].value))
    return calls


class CatalogTests(unittest.TestCase):
    def test_nine_weapons_without_the_bow(self):
        # 0.24: the scout rifle (KG11) is the tenth weapon
        self.assertEqual({"pistol", "assault_rifle", "pulse_rifle", "shotgun", "sniper_rifle", "smg", "fusion_rifle",
                          "trace_rifle", "rocket_launcher", "scout_rifle"}, set(WEAPONS))
        self.assertEqual(set(WEAPONS), set(designs.DESIGNS))
        self.assertNotIn("bow", WEAPONS)

    def test_tools_json_mirrors_the_design_table(self):
        for key, tool in WEAPONS.items():
            spec = designs.DESIGNS[key]
            with self.subTest(weapon=key):
                self.assertEqual(spec["asset"], tool["asset"])
                self.assertEqual(spec["clip"], tool["clip"])
                self.assertEqual(spec["clip"], tool["fps_clip"])
                self.assertEqual(spec["element"], tool["element"])
                self.assertEqual(spec["grip_tilt_degrees"], tool["hold"]["grip_tilt_degrees"])
                self.assertTrue(tool["hold"]["two_handed"])          # 0.10.0: the pistol too (cup grip)
                self.assertEqual(("create_weapon.py", "create_weapon_fps.py", "verify_weapon.py", "animate_weapon.py"),
                                 (tool["world"], tool["fps"], tool["verify"], tool["animation"]))

    def test_every_folder_has_the_launchers_for_its_weapon(self):
        folders = set()
        for key, tool in WEAPONS.items():
            self.assertNotIn(tool["folder"], folders, "tools need their own folder (their output is the folder)")
            folders.add(tool["folder"])
            for name, function in LAUNCHERS.items():
                with self.subTest(weapon=key, launcher=name):
                    text = (ASSETS / tool["folder"] / name).read_text()
                    module = "weapon_gif" if function == "make" else "weapon_kit"
                    self.assertIn("import " + module, text)
                    self.assertIn("%s.%s(" % (module, function), text)
                    if function != "make":
                        self.assertIn("('%s')" % key, text)

    def test_names_are_unique_and_follow_the_conventions(self):
        assets = [tool["asset"] for tool in TOOLS.values()]
        clips = [tool["clip"] for tool in TOOLS.values() if tool.get("clip")]
        self.assertEqual(len(assets), len(set(assets)))
        self.assertEqual(len(clips), len(set(clips)))
        for tool in WEAPONS.values():
            self.assertTrue(tool["asset"].startswith("CubeEscape_"))
            self.assertTrue(tool["clip"].endswith("_Use"))

    def test_every_element_is_used(self):
        # Since 0.13 the glow follows the concept sheet (user, 17.10.2026): no weapon is kinetic any more; its palette
        # material stays for older contracts and as a choice in Cube Escape.
        self.assertEqual(set(ELEMENTS) - {"kinetic"}, {tool["element"] for tool in WEAPONS.values()})


class DesignTests(unittest.TestCase):
    def test_every_build_creates_the_four_sockets_once(self):
        for key in WEAPONS:
            names = [name for method, name in build_calls(key) if method == "socket"]
            with self.subTest(weapon=key):
                for socket in SOCKETS:
                    self.assertEqual(1, names.count(socket), socket)

    def test_part_names_are_unique_per_weapon(self):
        for key in WEAPONS:
            literal = [name for method, name in build_calls(key) if method in ("box", "cyl", "tube", "slab", "glow", "pivot")
                       and "%" not in name]
            with self.subTest(weapon=key):
                self.assertEqual(len(literal), len(set(literal)), sorted(n for n in set(literal) if literal.count(n) > 1))

    def test_grip_and_support_parts_exist(self):
        for key, spec in designs.DESIGNS.items():
            names = [name for method, name in build_calls(key) if method in ("box", "cyl", "tube", "slab", "glow")]
            with self.subTest(weapon=key):
                self.assertTrue(any(name.startswith(spec["grip_part"]) for name in names)
                                or "grip(k" in (ASSETS / "weapon_designs.py").read_text())
                # the pistol's cup grip (0.10.0) puts Socket_SupportHand on the grip itself, built by grip()
                self.assertTrue(any(name.startswith(spec["support_part"]) for name in names)
                                or spec["support_part"] == spec["grip_part"], spec["support_part"])

    def test_the_use_clip_moves_child_nodes_only(self):
        for key, spec in designs.DESIGNS.items():
            pivots = {name for method, name in build_calls(key) if method == "pivot"}
            self.assertTrue(spec["use_clip"])
            for move in spec["use_clip"]:
                with self.subTest(weapon=key, node=move["node"], channel=move["channel"]):
                    self.assertIn(move["node"], pivots)
                    self.assertTrue(move["node"].startswith("Anim_"))
                    self.assertNotEqual(spec["asset"], move["node"], "never the root")
                    self.assertIn(move["channel"], ("location", "rotation"))
                    self.assertIn(move["axis"], (0, 1, 2))

    def test_the_use_clip_ends_in_the_rest_pose(self):
        """First key frame 1, last key frame 97 (the clip length), both at the rest value; rotations may turn whole turns."""
        for key, spec in designs.DESIGNS.items():
            for move in spec["use_clip"]:
                keys = move["keys"]
                frames = [frame for frame, _ in keys]
                with self.subTest(weapon=key, node=move["node"]):
                    self.assertEqual((1, 0), keys[0])
                    self.assertEqual(97, keys[-1][0])
                    self.assertEqual(sorted(set(frames)), frames, "key frames strictly ascending")
                    last = keys[-1][1]
                    full_turn = move["channel"] == "rotation" and abs(last) % 360 == 0
                    self.assertTrue(last == 0 or full_turn, last)
                    # at least one key away from rest, and the motion is over well before the end of the clip
                    moving = [frame for frame, value in keys if value != 0 and 1 < frame < 97]
                    self.assertTrue(moving)
                    self.assertLess(max(frames[-2], 1), 90 if move["channel"] == "location" else 97)

    def test_world_renderers_stay_within_the_game_export_limit(self):
        for key, spec in designs.DESIGNS.items():
            owners = {move["node"] for move in spec["use_clip"]}
            with self.subTest(weapon=key):
                self.assertLessEqual(1 + len(owners), ge.MAX_RENDERERS)

    def test_dimensions_leave_room_for_a_hand(self):
        for key, spec in designs.DESIGNS.items():
            self.assertGreater(len(spec["view_center"]), 2)
            self.assertGreater(spec["view_scale"], .4)


class ViewmodelProfileTests(unittest.TestCase):
    def test_profile_follows_the_grip_tilt(self):
        for key, tool in WEAPONS.items():
            profile = PROFILES[key]
            with self.subTest(weapon=key):
                self.assertEqual([tool["hold"]["grip_tilt_degrees"], 0, 0], profile["hand_rotation_degrees"]["R"])

    def test_second_hand_closes_around_the_support_socket(self):
        for key, tool in WEAPONS.items():
            profile = PROFILES[key]
            if not tool["hold"]["two_handed"]:
                self.assertFalse(profile["support"], key)
                continue
            with self.subTest(weapon=key):
                self.assertTrue(profile["support"])
                self.assertEqual("Socket_SupportHand", profile["support_socket"])
                self.assertEqual(2, len(profile["support_radius"]))
                # 0.18: the concept KG02's handguard is 9 cm tall (spec support.radius_m half height 44.7 mm); 0.24: KG03's
                # vertical foregrip p40 is 11.8 cm long (half height 59 mm; only the contract 4 way back reads the radius)
                self.assertTrue(all(.015 <= value <= .06 for value in profile["support_radius"]))

    def test_support_hand_grips_from_below(self):
        """0.8.0: relaxed underhand support (palm under the handguard, thumb on the camera side) on every rifle; 0.10.0: the
        pistol's left hand cups the right one from below left (Destiny)."""
        for key, tool in WEAPONS.items():
            with self.subTest(weapon=key):
                self.assertEqual("cup" if key == "pistol" else "underhand", PROFILES[key].get("support_grip"))
        source = (ROOT / "toolgen/first_person.py").read_text()
        self.assertIn('profile.get("support_grip") == "underhand"', source)
        self.assertIn('profile.get("support_grip") == "cup"', source)

    def test_arms_come_in_diagonally_from_below(self):
        """0.8.0 (Cube Escape 0.65 finding, user decision 16.10.2026: target 45 deg, hard limit 55 deg per wrist): forearms
        rise from the lower screen corners (right hand from the right, support hand from the left), elbows bent; the
        generator measures the bend in every clip frame against max_wrist_bend_degrees."""
        for key, tool in WEAPONS.items():
            profile = PROFILES[key]
            pose = profile["arm_pose"]
            with self.subTest(weapon=key):
                self.assertEqual({"R", "L"} if tool["hold"]["two_handed"] else {"R"}, set(pose))
                self.assertNotIn("shoulders", profile, "arm_pose sets the shoulders")
                for side, spec in pose.items():
                    self.assertLessEqual(spec["max_wrist_bend_degrees"], 55)
                    upper = spec["upper"]
                    self.assertEqual(-1 if side == "R" else 1, math.copysign(1, upper[0]), "elbow to the shoulder of its side")
                    if "forearm" in spec:
                        forearm = spec["forearm"]
                        self.assertGreater(forearm[2], .3, "the forearm rises to the hand")
                        self.assertLess(forearm[1], 0, "the forearm points forward")
                        cosine = sum(a * b for a, b in zip(forearm, upper)) / math.dist((0, 0, 0), forearm) / math.dist((0, 0, 0), upper)
                        self.assertGreater(cosine, -.87, "the elbow is bent (less than 150 deg between the links)")
                    else:
                        self.assertTrue(15 <= spec["forearm_rise_degrees"] <= 45)
                        self.assertTrue(0 < spec["forearm_yaw_degrees"] <= 20, "elbow out to the palm side")
                if profile.get("support_grip") == "underhand":
                    self.assertEqual(35, profile["support_roll_degrees"], "support palm turned to the camera side")
                # the barrel lies almost level in the authored Ego pose (the knuckles point less downward)
                aim, hand = profile["aim_target_m"], profile["hand"]
                pitch = math.degrees(math.atan2(hand[2] - aim[2], math.dist(aim[:2], hand[:2])))
                self.assertLess(pitch, 4, key)
        source = (ROOT / "toolgen/first_person.py").read_text()
        self.assertIn('wrist = empty("Wrist_" + side, joint)', source, "Wrist_<side> node for the game's wrist check")
        self.assertIn("def aim_arm(", source)
        self.assertIn("GAME_ENLARGEMENT_MAX = 1.7", source)

    def test_hands_must_touch_the_weapon(self):
        for key in WEAPONS:
            with self.subTest(weapon=key):
                self.assertTrue(0 < PROFILES[key]["touch_tolerance_m"] <= .01)

    def test_recoil_data_is_complete_and_small(self):
        for key in WEAPONS:
            motion = PROFILES[key]["motion"]
            with self.subTest(weapon=key):
                self.assertTrue({"fire_frame", "kick_m", "pitch_degrees", "recovery_frames"} <= set(motion))
                self.assertTrue(1 < motion["fire_frame"] < 60)
                self.assertTrue(motion["fire_frame"] + motion["recovery_frames"] < 90, "back at rest before the clip ends")
                self.assertTrue(0 < motion["kick_m"] <= .06 and 0 < motion["pitch_degrees"] <= 8)

    def test_heads_are_muzzle_parts(self):
        for key in WEAPONS:
            head = PROFILES[key]["head"]
            with self.subTest(weapon=key):
                self.assertEqual("Socket_Muzzle", head["anchor"])
                self.assertTrue(all(part.startswith("SM_PG_") for part in head["parts"]))

    def test_hold_and_aim_leave_the_reticle_to_the_framing_qa(self):
        for key in WEAPONS:
            profile = PROFILES[key]
            self.assertLess(profile["aim_target_m"][1], profile["hand"][1] - .5)
            self.assertLess(profile["hand"][0], 0, "right-hand weapon: the grip hand sits right of the view centre")

    def test_recoil_pose_is_zero_outside_the_shot(self):
        first_person = ROOT / "toolgen/first_person.py"
        source = first_person.read_text()
        self.assertIn("def recoil_pose(", source)
        self.assertIn('profile.get("support_socket")', source)


class MaterialTests(unittest.TestCase):
    CHANNEL_SOURCES = ("Primary", "Secondary", "Accent", "Metal", "Detail", "Display")

    def kit_materials(self):
        return {name: emission for name, emission, _ in material_calls(ASSETS / "weapon_kit.py")}

    def test_kit_materials_are_the_equipment_channels(self):
        found = self.kit_materials()
        self.assertEqual(set(self.CHANNEL_SOURCES) | {"Cyan", "Amber", "Void", "Arc", "Kinetic"}, set(found))
        for name, emission in found.items():
            with self.subTest(material=name):
                target = PALETTE["materials"][PALETTE["map"]["PG_" + name]]
                self.assertEqual(emission > 0, target["emission"] > 0, "contract 1 (palette names)")
                slot = PALETTE["channels"]["slots"][PALETTE["channels"]["map"]["PG_" + name]]
                self.assertEqual(emission > 0, slot["emission"] > 0, "contract 2 (MT_<Channel>)")

    def test_designs_only_use_kit_materials(self):
        text = (ASSETS / "weapon_designs.py").read_text()
        for old in ("'Armor'", "'Dark'", "'Rubber'", "'Visor'"):
            self.assertNotIn(old, text)

    def test_every_weapon_uses_the_channel_convention(self):
        for key, tool in WEAPONS.items():
            with self.subTest(weapon=key):
                self.assertEqual("equipment_channels", tool["materials"])
        self.assertFalse([tool_id for tool_id, tool in TOOLS.items() if tool.get("materials") and tool_id not in WEAPONS])

    def test_channel_slots_per_weapon(self):
        """Contract 2: the seven MT_ slots, MT_Energy in the element colour; contract 1: the 0.7 palette names."""
        for key, tool in WEAPONS.items():
            with self.subTest(weapon=key):
                palette = ge.tool_palette(PALETTE, tool, 2)
                used = {palette["map"]["PG_" + name] for name in self.CHANNEL_SOURCES} | {palette["map"][ELEMENTS[tool["element"]]]}
                self.assertEqual({"MT_" + channel for channel in ge.CHANNELS}, used)
                self.assertLessEqual(len(used), palette["max_materials_per_tool"])
                energy = palette["materials"]["MT_Energy"]
                glow = PALETTE["materials"][PALETTE["map"][ELEMENTS[tool["element"]]]]
                self.assertEqual(glow["color_srgb"], energy["color_srgb"])
                self.assertEqual(tool["element"], energy["element"])
                legacy = ge.tool_palette(PALETTE, tool, 1)
                old = {legacy["map"]["PG_" + name] for name in self.CHANNEL_SOURCES} | {legacy["map"][ELEMENTS[tool["element"]]]}
                self.assertTrue(all(name.startswith("M_") for name in old))
                self.assertLessEqual(len(old), legacy["max_materials_per_tool"])
                self.assertLessEqual(len(old | {"M_HazardOrange_Matte", "M_RobotBody_Matte", "M_Metal_Matte"}),
                                     legacy["max_materials_per_viewmodel"])

    def test_element_glow_maps_to_its_own_palette_material(self):
        targets = {element: PALETTE["map"][source] for element, source in ELEMENTS.items()}
        self.assertEqual(5, len(set(targets.values())), targets)
        self.assertEqual("M_GlowCyan", targets["energy"])
        self.assertEqual("M_GlowOrange", targets["solar"])
        for element, name in targets.items():
            self.assertTrue(name.startswith("M_Glow"), element)
        self.assertEqual(ELEMENTS, ge.ELEMENT_SOURCES)

    def test_kit_glow_table_matches_the_elements(self):
        text = (ASSETS / "weapon_kit.py").read_text()
        for element, source in ELEMENTS.items():
            self.assertIn("'%s': '%s'" % (element, source.removeprefix("PG_")), text)


class BudgetTests(unittest.TestCase):
    def test_every_weapon_has_both_budgets(self):
        for key in WEAPONS:
            with self.subTest(weapon=key):
                self.assertIn(key, BUDGET["world"])
                self.assertIn(key, BUDGET["viewmodel"])
                self.assertLess(BUDGET["world"][key], BUDGET["viewmodel"][key])
                # 0.18: +25 % (user decision 20.10.2026), still below what Cube Escape measured as unproblematic
                self.assertLessEqual(BUDGET["world"][key], 10000, "Cube Escape measured 12k world / 25k ego as unproblematic")
                self.assertLessEqual(BUDGET["viewmodel"][key], 20000)


class HoldContractTests(unittest.TestCase):
    def test_hold_block_axes(self):
        tool = {"hold": {"grip_tilt_degrees": 14, "two_handed": False}, "element": "kinetic"}
        hold = ge.hold_block(tool)
        grip, muzzle = hold["grip_axis"], hold["muzzle_axis"]
        self.assertAlmostEqual(1.0, math.dist([0, 0, 0], grip["blender"]), places=5)
        self.assertEqual([0.0, -1.0, 0.0], muzzle["blender"])
        self.assertEqual([0.0, 0.0, 1.0], muzzle["unity"])
        self.assertAlmostEqual(76.0, hold["grip_to_muzzle_degrees"], places=3)
        self.assertGreater(grip["unity"][2], 0, "the grip leans forward (+Z in Unity) at the top")
        self.assertEqual("Socket_SupportHand", hold["support_socket"])
        self.assertFalse(hold["two_handed"])

    def test_hold_axes_stay_unit_vectors_after_the_import_yaw(self):
        for tilt in (0, 12, 18):
            hold = ge.hold_block({"hold": {"grip_tilt_degrees": tilt, "two_handed": True}})
            turned = ge.import_yaw_correction(hold["grip_axis"]["unity"])
            self.assertAlmostEqual(1.0, math.dist([0, 0, 0], turned), places=5)
            self.assertAlmostEqual(hold["grip_axis"]["unity"][1], turned[1], places=6, msg="the yaw is about Y: up stays")

    def test_hold_block_names_the_sight(self):
        for key, tool in WEAPONS.items():
            with self.subTest(weapon=key):
                hold = ge.hold_block(tool)
                self.assertEqual("Socket_Sight", hold["sight_socket"])
                self.assertEqual(tool["hold"]["sight_kind"], hold["sight_kind"])
                self.assertEqual("Socket_Eye" if hold["sight_kind"] == "scope" else None, hold["eye_socket"])
                self.assertEqual(tool["hold"].get("eye_radius_m"), hold["eye_radius_m"])
                self.assertEqual(tool["hold"]["eye_distance_m"], hold["ads_eye_distance_m"])
        old = ge.hold_block({"hold": {"grip_tilt_degrees": 14, "two_handed": True}})
        self.assertNotIn("sight_socket", old, "tools without a sight keep the 0.10 hold block")

    def test_opening_probes_cover_every_weapon(self):
        for key in WEAPONS:
            self.assertIn(key, ge.OPENING_PROBES)


class SightTests(unittest.TestCase):
    """T1 (Cube Escape 0.72 Sightline): Socket_Sight / Socket_Eye follow the AimIdle line of sight of data/ego_clips.json."""
    # 0.18: the assault rifle carries the holo sight VS02 of its concept KG02 (formgen sight_kind; was reflex)
    KINDS = {"pistol": "iron", "assault_rifle": "holo", "pulse_rifle": "holo", "shotgun": "iron", "sniper_rifle": "scope",
             "smg": "reflex", "fusion_rifle": "energy", "trace_rifle": "scope", "rocket_launcher": "iron", "scout_rifle": "scope"}
    # Cube Escape 0.72 profile classes: sidearm 0.30, rifle 0.26, submachine_gun 0.24, shotgun 0.28, sniper 0.22,
    # heavy 0.30, trace rifle 0.20 (FIRST_PERSON_EQUIPMENT.md 20, T6).
    # Cube Escape 0.75 aims with these distances (CE ads.eye_distance_m / hip.scale, table in CE Docs/versions/0.75.md;
    # Toolgen 0.13 adopted them so the ADS QA checks the real pose).
    EYE = {"pistol": .40, "assault_rifle": .379, "pulse_rifle": .357, "shotgun": .65, "sniper_rifle": .221, "smg": .421,
           "fusion_rifle": .40, "trace_rifle": .221, "rocket_launcher": .453,
           # 0.24: no CE profile for the new scout rifle yet; the scope class distance of the sniper and trace rifle
           "scout_rifle": .221}

    def test_sight_kinds_and_eye_distances(self):
        for key, tool in WEAPONS.items():
            with self.subTest(weapon=key):
                self.assertEqual(self.KINDS[key], tool["hold"]["sight_kind"])
                self.assertEqual(self.KINDS[key], designs.DESIGNS[key]["sight"]["kind"])
                self.assertEqual(self.EYE[key], tool["hold"]["eye_distance_m"])
                self.assertIn(tool["hold"]["sight_kind"], sight.SIGHT_KINDS)

    def test_design_rule_is_the_aim_idle_line(self):
        data = ego_clips.load()
        for key, tool in WEAPONS.items():
            rule, ads = designs.DESIGNS[key]["sight"], ego_clips.class_params(data, key)["ads"]
            scale = PROFILES[key]["tool_scale"]
            with self.subTest(weapon=key):
                self.assertEqual(ads.get("sight_mode", "top"), rule["mode"])
                if ads.get("sight_parts"):
                    self.assertEqual(sorted(ads["sight_parts"]), sorted(rule["parts"]))
                else:                       # marker match (pistol, smg): every listed part carries a marker
                    self.assertTrue(all(any(marker in part for marker in ads["sight_markers"]) for part in rule["parts"]))
                if rule["mode"] == "top":
                    self.assertAlmostEqual(ads["eye_above_m"], rule["above_m"] * scale, places=12)
                if rule["kind"] == "scope" and designs.DESIGNS[key].get("concept"):
                    # 0.24: a concept scope (glass not built): the eye radius of the sheet in first-person metres
                    spec = concept_spec.load(designs.DESIGNS[key]["concept"])
                    self.assertAlmostEqual(round(spec["sight"]["eye_radius_m"] * scale, 6), tool["hold"]["eye_radius_m"], places=6)
                    self.assertEqual("center", rule["mode"])
                elif rule["kind"] == "scope":       # eye lens inside the open eyepiece, radius in first-person metres
                    radius = {"sniper_rifle": .020, "trace_rifle": .015}[key] * designs.EYE_LENS * scale
                    self.assertAlmostEqual(radius, tool["hold"]["eye_radius_m"], places=6)
                    self.assertEqual("center", rule["mode"])
                elif designs.DESIGNS[key].get("concept"):
                    # 0.18: a concept sight has an open window (no glass, user decision 20.10.2026): the line runs
                    # through the centre of the window frame, which holds Socket_Reticle
                    self.assertNotIn("eye_radius_m", tool["hold"])
                    self.assertEqual("center", rule["mode"])
                    found = concept_spec.layout(designs.DESIGNS[key]["concept"], [])
                    reticle = found["sockets"]["Socket_Reticle"]
                    for mesh in found["meshes"]:
                        if mesh["name"].removeprefix("SM_PG_") in rule["parts"]:
                            low, high = concept_spec.bounds(mesh["vertices"])
                            self.assertTrue(all(low[i] <= reticle[i] <= high[i] for i in range(3)))
                else:
                    self.assertNotIn("eye_radius_m", tool["hold"])
                    # Cube Escape 0.72: iron, reflex and holo lines run over the top of the housing (free centre)
                    self.assertEqual("top", rule["mode"])
                # Names the build function writes literally (scope() and the rear-sight loop build theirs inside).
                built = {name for _, name in build_calls(key)} | {"ScopeTube", "RearSight_-1", "RearSight_1"}
                self.assertTrue(set(rule["parts"]) <= built, (key, rule["parts"]))

    def test_line_puts_the_socket_at_the_rear_of_the_sight(self):
        bounds = {"SM_PG_Front": ((-.003, -.13, .07), (.003, -.12, .08)), "SM_PG_Rear": ((-.01, .03, .07), (.01, .04, .08)),
                  "SM_PG_Body": ((-.02, -.2, -.1), (.02, .1, .07))}
        found = sight.line(bounds, {"kind": "iron", "parts": ["Front", "Rear"], "mode": "top", "above_m": .01})
        self.assertEqual(["SM_PG_Front", "SM_PG_Rear"], found["parts"])
        self.assertEqual((0.0, .04, .09), tuple(round(v, 9) for v in found["sight"]))
        self.assertIsNone(found["eye"])
        scope = {"SM_PG_ScopeTube": ((-.02, -.16, .12), (.02, .08, .16)),
                 "SM_PG_ScopeEyepiece": ((-.024, .05, .116), (.024, .11, .164)),
                 "SM_PG_ScopeEyeLens": ((-.018, .101, .122), (.018, .103, .158))}
        found = sight.line(scope, {"kind": "scope", "parts": ["ScopeTube"], "mode": "center", "above_m": 0.0})
        self.assertEqual((0.0, .11, .14), tuple(round(v, 9) for v in found["sight"]), "eyepiece rear, tube axis")
        self.assertEqual((0.0, .102, .14), tuple(round(v, 9) for v in found["eye"]), "eye lens centre")
        with self.assertRaises(AssertionError):
            sight.line(bounds, {"kind": "iron", "parts": ["Missing"], "mode": "top", "above_m": 0.0})

    def test_fire_marker_is_the_ego_shot(self):
        """T2: the Use clip's marker Fire sits on motion.fire_frame of data/viewmodels.json (weapon_kit.animate)."""
        kit = (ASSETS / "weapon_kit.py").read_text()
        self.assertIn("scene.timeline_markers.new(FIRE_MARKER, frame=spec['fire_frame'])", kit)
        self.assertIn("FIRE_MARKER = 'Fire'", kit)
        for key in WEAPONS:
            with self.subTest(weapon=key):
                self.assertEqual(PROFILES[key]["motion"]["fire_frame"], designs.DESIGNS[key]["fire_frame"])
                self.assertTrue(1 < designs.DESIGNS[key]["fire_frame"] < 97)

    def test_ego_fire_clips_carry_the_fire_event(self):
        data = ego_clips.load()
        for key, tool in WEAPONS.items():
            clips, _ = ego_clips.clip_list(data, tool, PROFILES[key]["motion"])
            for clip in clips:
                if clip["suffix"] in ("Fire", "AimFire"):
                    names = {event["name"]: event["frame"] for event in clip["events"]}
                    self.assertEqual(names["Shot"], names["Fire"], (key, clip["name"]))


class AdsCheckTests(unittest.TestCase):
    """game_export.check_ads: the binding part (sight centred, socket on the AimIdle line, some eye distance keeps the
    framing) against the reported part (the game profile's distance)."""
    TOOL = {"hold": {"sight_kind": "scope", "eye_distance_m": .22, "eye_radius_m": .011}}

    def contract(self, eye_y=-.008):
        socket = {"parent": "Viewmodel_Hold", "blender": {"location": [0.0, .1, .2], "rotation_wxyz": [1.0, 0.0, 0.0, 0.0]}}
        eye = {"parent": "Viewmodel_Hold", "blender": {"location": [0.0, .1 + eye_y, .2], "rotation_wxyz": [1.0, 0.0, 0.0, 0.0]}}
        return {"anchors": [dict(socket, name="Socket_Sight"), dict(eye, name="Socket_Eye")]}

    def run_check(self, ads, contract=None, on_line=True):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            (work / "qa_viewmodel.json").write_text(json.dumps({"ads_target": ads, "ego_clips": {"sight_socket": {"ok": on_line}}}))
            checks = ge.Checks()
            block = ge.check_ads(checks, work, contract or self.contract(), self.TOOL)
            return checks.results, block

    def ads(self, passed, distances, screen=(.5, .5), clear=True, top_ok=True):
        return {"passed": passed, "eye_distance_range_m": distances, "failures": [] if passed else ["too close"],
                "eye_distance_m": .22, "configurations": [{"sight_screen": list(screen)}], "centre_clear": clear,
                "centre_hit": None if clear else "SM_PG_Optic", "model_top_above_centre": .1 if top_ok else .3,
                "model_top_ok": top_ok}

    def test_profile_distance_is_reported_not_binding(self):
        results, block = self.run_check(self.ads(False, [.3, .5]))
        self.assertTrue(results["ads_target_pose"]["passed"])
        self.assertFalse(results["ads_target_pose"]["profile_distance_passed"])
        self.assertTrue(results["sight_anchors"]["passed"])
        self.assertEqual("scope", block["sight_kind"])

    def test_binding_failures(self):
        self.assertFalse(self.run_check(self.ads(True, None))[0]["ads_target_pose"]["passed"], "no distance keeps the framing")
        self.assertFalse(self.run_check(self.ads(True, [.2, .4], (.51, .5)))[0]["ads_target_pose"]["passed"], "off centre")
        self.assertFalse(self.run_check(self.ads(True, [.2, .4]), on_line=False)[0]["ads_target_pose"]["passed"])
        self.assertFalse(self.run_check(self.ads(True, [.2, .4]), self.contract(.3))[0]["sight_anchors"]["passed"],
                         "Socket_Eye far behind the eyepiece")
        self.assertFalse(self.run_check(self.ads(True, [.2, .4], clear=False))[0]["ads_target_pose"]["passed"],
                         "a closed housing on the screen centre")
        self.assertFalse(self.run_check(self.ads(True, [.2, .4], top_ok=False))[0]["ads_target_pose"]["passed"],
                         "model over 25 % of the screen height above the centre")


class Uv1RotationTests(unittest.TestCase):
    def test_packer_noise_passes_and_real_turns_fail(self):
        """0.12.0: limit 0.5 degrees (packer noise Mac 0.097, Linux 0.1015; user decision 16.10.2026)."""
        self.assertEqual(.5, ge.UV1_ROTATION_LIMIT_DEGREES)
        for value in (0.0, .0918, .1015, .45):
            self.assertTrue(ge.uv1_rotation_ok(value), value)
        for value in (.6, 90, None):
            self.assertFalse(ge.uv1_rotation_ok(value), value)


def flat_faces(kind, values):
    """Axis-aligned faces (axis, sign, plane, low, high) of an unrotated box or a slab of the recorded design."""
    if kind == "box":
        center, size, _, _, rot = values
        if rot is not None:
            return []
        low = [center[i] - size[i] / 2 for i in range(3)]
        high = [center[i] + size[i] / 2 for i in range(3)]
        return [(axis, sign, (high if sign > 0 else low)[axis], low, high) for axis in range(3) for sign in (-1, 1)]
    if kind in ("cyl", "tube"):          # end discs along the axis (muzzle rings, lenses, caps)
        if kind == "cyl":
            center, radius, length, _, axis, _, _ = values
        else:
            center, radius, _, length, _, axis, _ = values
        index = "xyz".index(axis)
        low = [center[i] - (length / 2 if i == index else radius) for i in range(3)]
        high = [center[i] + (length / 2 if i == index else radius) for i in range(3)]
        return [(index, sign, (high if sign > 0 else low)[index], low, high) for sign in (-1, 1)]
    if kind == "slab":
        points, width, _, x, _ = values
        low = [x - width / 2, min(p[0] for p in points), min(p[1] for p in points)]
        high = [x + width / 2, max(p[0] for p in points), max(p[1] for p in points)]
        return [(0, -1, low[0], low, high), (0, 1, high[0], low, high)]
    return []


class CoplanarDecorTests(unittest.TestCase):
    """0.12.0 (Mac viewer, shotgun/fps): a decor face lying in another part's face z-fights; the result flipped with the
    draw order. Accent and glow decors, muzzle rings, lenses and the other parts the mesh scan found stand at least 0.5 mm
    proud of what they sit on (box, slab and cylinder end faces)."""
    KNOWN = set()          # no exceptions (0.12.0: the fusion rifle's fin accents were raised as well)

    def test_decors_are_not_coplanar(self):
        from test_ego_weapon_motions import RecordingKit
        found = []
        for key, spec in designs.DESIGNS.items():
            kit = RecordingKit(spec)
            spec["build"](kit)
            decor = {name for name, (kind, values) in kit.geometry.items()
                     if (kind == "box" and (values[2] in ("Accent", spec["element"]) or "Glow" in name or "Accent" in name
                                            or name.startswith("StockCell")))
                     or name in ("MuzzleRing", "ScopeLens", "SightPost", "Hammer", "StockCore", "Trigger")}
            faces = [(name, face) for name, (kind, values) in kit.geometry.items() for face in flat_faces(kind, values)]
            for name, (axis, sign, plane, low, high) in faces:
                if name not in decor or (key, name) in self.KNOWN:
                    continue
                for other, (axis2, sign2, plane2, low2, high2) in faces:
                    if other == name or axis2 != axis or sign2 != sign or abs(plane - plane2) > .0005 - 1e-9:
                        continue
                    if all(min(high[b], high2[b]) - max(low[b], low2[b]) > 1e-4 for b in range(3) if b != axis):
                        found.append((key, name, other, "xyz"[axis], round(plane - plane2, 6)))
        self.assertEqual([], found)


class FramesTests(unittest.TestCase):
    def test_kit_frame_constants_match_the_pipeline(self):
        constants = {}
        for name in ("weapon_kit.py", "weapon_gif.py"):
            module = ast.parse((ASSETS / name).read_text())
            constants.update({node.targets[0].id: ast.literal_eval(node.value) for node in module.body
                              if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                              and node.targets[0].id in ("FRAMES", "FPS", "LAST_FRAME")})
        self.assertEqual(len(constants["FRAMES"]), len(ast.literal_eval(next(
            node.value for node in ast.parse((ASSETS / "weapon_gif.py").read_text()).body
            if isinstance(node, ast.Assign) and node.targets[0].id == "DELAYS"))))
        self.assertEqual(97, constants["LAST_FRAME"])
        self.assertEqual(24, constants["FPS"])
        self.assertEqual((1, 97), (constants["FRAMES"][0], constants["FRAMES"][-1]))


if __name__ == "__main__":
    unittest.main()
