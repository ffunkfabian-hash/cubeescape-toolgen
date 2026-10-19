"""Robot variant of the world models (Toolgen 0.14 Fieldfit, weapon_designs.ROBOT): measures against Cube Escape's robot,
the life-size designs untouched, the pipeline stages and the contract names.

Pure Python: the designs are built into a recording kit (tests/test_ego_weapon_motions.py) and their primitive bounds
mapped through the robot fit; the map is separable and monotonic, so the mapped bounds are the robot model's bounds. The
built models are checked again by weapon_kit.robot_report (qa_geometry_robot.json) and scripts/verify_output.py."""
import copy
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
sys.path.insert(0, str(ROOT / "tests"))

import decals  # noqa: E402
import game_export as ge  # noqa: E402
import weapon_designs as designs  # noqa: E402
from generate_tools import STAGES, catalog, expand, variants  # noqa: E402
from test_ego_weapon_motions import RecordingKit  # noqa: E402

TOOLS = {tool["id"]: tool for tool in catalog()}
# Cube Escape 0.82 "Sidearm" (Docs/EQUIPMENT.md, length in the hand = Toolgen length x heldScale): the robot variant is this
# long and is held at heldScale 1.0. The pistol keeps its model (scale 1.1, the cup grip fits).
CE_LENGTH = {"smg": .52, "assault_rifle": .67, "pulse_rifle": .66, "shotgun": .67, "fusion_rifle": .67, "trace_rifle": .69,
             "sniper_rifle": .73, "rocket_launcher": .65}
ROBOT_STAGES = ("robot", "game_robot", "surface_bake_robot")


def primitive_bounds(kind, values):
    """Axis-aligned (low, high) of one recorded primitive in the weapon frame (life metres)."""
    if kind == "box":
        center, size, _, _, rot = values
        corners = [(sx * size[0] / 2, sy * size[1] / 2, sz * size[2] / 2) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        if rot:
            a = math.radians(rot)       # the recording kit's tilt() keeps the degrees of a rotation about X
            corners = [(x, y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)) for x, y, z in corners]
        points = [(center[0] + x, center[1] + y, center[2] + z) for x, y, z in corners]
    elif kind in ("cyl", "tube"):
        if kind == "cyl":
            center, radius, length, _, axis, _, _ = values
        else:
            center, radius, _, length, _, axis, _ = values
        index = "xyz".index(axis)
        half = [length / 2 if i == index else radius for i in range(3)]
        points = [tuple(center[i] - half[i] for i in range(3)), tuple(center[i] + half[i] for i in range(3))]
    else:
        points_yz, width, _, x, _ = values
        points = [(x + side * width / 2, y, z) for side in (-1, 1) for y, z in points_yz]
    return [min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)]


def built(key):
    kit = RecordingKit(designs.DESIGNS[key])
    designs.DESIGNS[key]["build"](kit)
    return kit


def robot_bounds(key, names=None):
    """Robot-model bounds of all parts (or of the parts named ``names``), via the fit's map."""
    fit, kit = designs.ROBOT[key], built(key)
    found = [primitive_bounds(kind, values) for name, (kind, values) in kit.geometry.items()
             if names is None or name in names]
    low = [min(b[0][i] for b in found) for i in range(3)]
    high = [max(b[1][i] for b in found) for i in range(3)]
    return list(designs.robot_point(fit, low)), list(designs.robot_point(fit, high))


class FitTests(unittest.TestCase):
    def test_the_eight_underhand_weapons_have_a_robot_variant(self):
        underhand = {key for key, tool in TOOLS.items() if tool.get("hold", {}).get("support_grip") == "underhand"}
        self.assertEqual(underhand, set(designs.ROBOT))
        self.assertEqual(set(CE_LENGTH), set(designs.ROBOT))
        self.assertNotIn("pistol", designs.ROBOT, "the pistol's cup grip fits at heldScale 1.1 (CE 0.82)")
        for key, tool in TOOLS.items():
            with self.subTest(tool=key):
                if key in designs.ROBOT:
                    self.assertEqual(tool["asset"] + designs.ROBOT_SUFFIX, tool["robot"])
                    self.assertEqual("CubeEscape_", tool["robot"][:11])
                else:
                    self.assertNotIn("robot", tool)

    def test_the_bore_map_is_monotonic_and_keeps_the_grip_tilt(self):
        for key, fit in designs.ROBOT.items():
            knots = designs.robot_knots(fit)
            with self.subTest(weapon=key):
                self.assertTrue(all(a0 < a1 and b0 < b1 for (a0, b0), (a1, b1) in zip(knots, knots[1:])), knots)
                self.assertEqual((0.0, 0.0), (designs.robot_y(fit, 0.0) + 0.0, designs.robot_point(fit, (0, 0, 0))[2] + 0.0))
                # inside the grip zone y and z scale alike, so the grip axis keeps hold.grip_tilt_degrees exactly
                for y in (-.03, -.01, .01, .03):
                    self.assertAlmostEqual(fit["cross"], designs.robot_slope(fit, y), places=6)
                tilt = math.radians(designs.DESIGNS[key]["grip_tilt_degrees"])
                bottom = designs.robot_point(fit, (0, .04 * math.sin(tilt), -.04 * math.cos(tilt)))
                top = designs.robot_point(fit, (0, -.04 * math.sin(tilt), .04 * math.cos(tilt)))
                self.assertAlmostEqual(math.degrees(tilt), math.degrees(math.atan2(bottom[1] - top[1], top[2] - bottom[2])), 6)

    def test_length_is_the_ce_length_in_the_hand(self):
        for key, fit in designs.ROBOT.items():
            low, high = robot_bounds(key)
            with self.subTest(weapon=key):
                self.assertEqual(CE_LENGTH[key], fit["length_m"])
                self.assertLessEqual(abs(high[1] - low[1] - fit["length_m"]), designs.ROBOT_LIMITS["length_tolerance_m"],
                                     (low[1], high[1]))

    def test_stock_ends_close_behind_the_hand(self):
        for key in designs.ROBOT:
            _low, high = robot_bounds(key)
            with self.subTest(weapon=key):
                self.assertLessEqual(high[1], designs.ROBOT_LIMITS["stock_behind_m"])

    def test_support_hand_is_in_reach_on_its_part(self):
        for key, fit in designs.ROBOT.items():
            kit = built(key)
            support = designs.robot_point(fit, fit["support"])
            parts = [primitive_bounds(kind, values) for name, (kind, values) in kit.geometry.items()
                     if name.startswith(fit["support_part"])]
            with self.subTest(weapon=key):
                self.assertTrue(parts, fit["support_part"])
                self.assertTrue(any(all(b[0][i] - .004 <= fit["support"][i] <= b[1][i] + .004 for i in range(3)) for b in parts),
                                "Socket_SupportHand floats beside %s" % fit["support_part"])
                ahead = -support[1]
                self.assertGreater(ahead, 0)
                self.assertLessEqual(ahead, designs.ROBOT_LIMITS["support_ahead_m"])
                self.assertLessEqual(math.dist(support, (0, 0, 0)), .12)
                self.assertLessEqual(abs(support[2]), .08, "about level with the grip")
                self.assertEqual(0, support[0])

    def test_silhouette_is_stronger(self):
        for key, fit in designs.ROBOT.items():
            with self.subTest(weapon=key):
                low, high = robot_bounds(key, (fit["barrel"],))
                self.assertGreaterEqual(min(high[0] - low[0], high[2] - low[2]), designs.ROBOT_LIMITS["barrel_m"])
                low, high = robot_bounds(key, fit["body"])
                self.assertGreaterEqual(high[2] - low[2], designs.ROBOT_LIMITS["body_m"])
                self.assertGreaterEqual(fit["cross"], 1.15)

    def test_muzzle_stays_at_the_front(self):
        for key, fit in designs.ROBOT.items():
            kit, (low, _high) = built(key), robot_bounds(key)
            muzzle = designs.robot_point(fit, kit.sockets["Socket_Muzzle"])
            with self.subTest(weapon=key):
                self.assertLessEqual(abs(muzzle[1] - low[1]), .015)


class SpecTests(unittest.TestCase):
    def test_robot_spec_derives_and_leaves_the_life_design_alone(self):
        before = copy.deepcopy({key: {k: v for k, v in spec.items() if k != "build"} for key, spec in designs.DESIGNS.items()})
        for key, fit in designs.ROBOT.items():
            kit = built(key)
            pivots = {name: location[1] for name, (location, _parent) in kit.pivots.items()}
            spec = designs.robot_spec(key, pivots)
            life = designs.DESIGNS[key]
            with self.subTest(weapon=key):
                self.assertEqual(life["asset"] + "_Robot", spec["asset"])
                for same in ("clip", "class", "element", "grip_tilt_degrees", "grip_part", "trigger", "fire_frame", "build"):
                    self.assertEqual(life[same], spec[same], same)
                self.assertEqual(fit["support_part"], spec["support_part"])
                self.assertEqual(dict(life["sight"], above_m=life["sight"]["above_m"] * fit["cross"]), spec["sight"])
                self.assertEqual(len(life["use_clip"]), len(spec["use_clip"]))
                for old, new in zip(life["use_clip"], spec["use_clip"]):
                    self.assertEqual([frame for frame, _ in old["keys"]], [frame for frame, _ in new["keys"]])
                    self.assertEqual((1, 0), tuple(new["keys"][0]))
                    self.assertEqual(0, new["keys"][-1][1] % 360 if new["channel"] == "rotation" else new["keys"][-1][1])
                    if new["channel"] == "rotation":
                        self.assertEqual(old["keys"], new["keys"])
                    else:
                        rest = pivots[old["node"]]
                        for (_, a), (_, b) in zip(old["keys"], new["keys"]):
                            # the pivot's displaced position goes through the map (exact where the travel crosses a knot)
                            expected = (designs.robot_y(fit, rest + a) - designs.robot_y(fit, rest) if old["axis"] == 1
                                        else a * fit["cross"])
                            self.assertAlmostEqual(expected, b)
                            if old["axis"] == 1 and a:
                                low, high = sorted((rest, rest + a))
                                slopes = [designs.robot_slope(fit, low + (high - low) * i / 8) for i in range(8)]
                                self.assertLessEqual(abs(b), abs(a) * max(slopes) + 1e-9, "travel beyond the local map")
        self.assertEqual(before, {key: {k: v for k, v in spec.items() if k != "build"} for key, spec in designs.DESIGNS.items()})

    def test_bolt_travel_follows_the_map_across_the_grip_zone(self):
        """Codex finding (0.14): the shotgun bolt (rest y 0, 70 mm back) leaves the grip zone at +0.04; the slope at rest
        (1.35) would push it 94.5 mm back, the map puts it 58.8 mm back."""
        spec = designs.robot_spec("shotgun", {"Anim_Bolt": 0.0})
        travel = max(value for _, value in spec["use_clip"][0]["keys"])
        self.assertAlmostEqual(designs.robot_y(designs.ROBOT["shotgun"], .07), travel)
        self.assertLess(travel, .07 * designs.ROBOT["shotgun"]["cross"] - .03)

    def test_location_moves_need_the_pivots(self):
        with self.assertRaises(ValueError):
            designs.robot_spec("assault_rifle")


class CoplanarRobotTests(unittest.TestCase):
    """The decor rule of CoplanarDecorTests (>= 0.5 mm proud) on the deformed faces: steps along the bore shrink with the map's
    slope (stock 0.13-0.4), which brought z-fighting into the viewer (trace rifle stock cell, 0.14). Energy cells keep at least
    weapon_designs.RIGID_SLOPE about their centre, the same mapping as weapon_kit.apply_robot_fit."""

    def test_deformed_decors_are_not_coplanar(self):
        from test_weapons import flat_faces
        found = []
        for key, fit in designs.ROBOT.items():
            spec, kit = designs.DESIGNS[key], built(key)
            groups = designs.robot_cells(kit.geometry)
            spans = {}
            for name, group in groups.items():
                low, high = primitive_bounds(*kit.geometry[name])
                old = spans.get(group, (low[1], high[1]))
                spans[group] = (min(old[0], low[1]), max(old[1], high[1]))
            cells = {group: designs.robot_cell_map(fit, *span) for group, span in spans.items()}

            def mapped(name, axis, value):
                return designs.robot_point(fit, (value, value, value), cells.get(groups.get(name)))[axis]

            decor = {name for name, (kind, values) in kit.geometry.items()
                     if (kind == "box" and (values[2] in ("Accent", spec["element"]) or "Glow" in name or "Accent" in name
                                            or name.startswith("StockCell")))
                     or name in ("MuzzleRing", "ScopeLens", "SightPost", "Hammer", "StockCore", "Trigger")}
            faces = [(name, axis, sign, mapped(name, axis, plane), [mapped(name, i, low[i]) for i in range(3)],
                      [mapped(name, i, high[i]) for i in range(3)])
                     for name, (kind, values) in kit.geometry.items() for axis, sign, plane, low, high in flat_faces(kind, values)]
            for name, axis, sign, plane, low, high in faces:
                if name not in decor:
                    continue
                for other, axis2, sign2, plane2, low2, high2 in faces:
                    if other == name or axis2 != axis or sign2 != sign or abs(plane - plane2) > .0005 - 1e-9:
                        continue
                    if all(min(high[b], high2[b]) - max(low[b], low2[b]) > 1e-4 for b in range(3) if b != axis):
                        found.append((key, name, other, "xyz"[axis], round(plane - plane2, 6)))
        self.assertEqual([], found)

    def test_cells_are_found_and_only_cells(self):
        for key in designs.ROBOT:
            groups = designs.robot_cells(built(key).geometry)
            with self.subTest(weapon=key):
                self.assertTrue(all(name.startswith(group) for name, group in groups.items()))
                self.assertFalse({"Grip", "Drum", "Stock", "Shroud"} & set(groups.values()))
        self.assertEqual({"StockCell_-1", "StockCell_1"}, set(designs.robot_cells(built("pulse_rifle").geometry).values()))


class DecalRefitTests(unittest.TestCase):
    """Decals on the robot variant (surface_bake.robot_refit, decals.refit_rect): the rect follows the deformation, keeps its
    aspect in millimetres and stays inside the part (Toolgen 0.14; the plain rect fractions came out stretched 0.36-0.54)."""

    @staticmethod
    def maps(fit):
        def to_life(axis, value):
            return designs.robot_life_y(fit, value) if axis == 1 else value / fit["cross"]

        def to_model(axis, value):
            return designs.robot_y(fit, value) if axis == 1 else value * fit["cross"]
        return to_life, to_model

    def test_inverse_map(self):
        for key, fit in designs.ROBOT.items():
            for y in (-.7, -.3, -.1, -.05, 0.0, .02, .06, .2, .4):
                with self.subTest(weapon=key, y=y):
                    self.assertAlmostEqual(y, designs.robot_life_y(fit, designs.robot_y(fit, y)), places=9)

    def test_every_decal_keeps_its_aspect_and_stays_on_its_part(self):
        for key, fit in designs.ROBOT.items():
            kit, (to_life, to_model) = built(key), self.maps(fit)
            for anchor in designs.DECALS[key]:
                life_box = primitive_bounds(*kit.geometry[anchor["part"]])
                box = (designs.robot_point(fit, life_box[0]), designs.robot_point(fit, life_box[1]))
                for scale in (fit["cross"], 1.0):
                    with self.subTest(weapon=key, decal=anchor["image"], scale=scale):
                        moved = decals.refit_rect(anchor, box, to_life, to_model, scale)
                        u0, v0, u1, v1 = moved["rect"]
                        self.assertTrue(0 <= u0 < u1 <= 1 and 0 <= v0 < v1 <= 1, moved["rect"])
                        life_aspect = decals.rect_aspect_error(anchor, life_box, (1, 1))
                        robot_aspect = decals.rect_aspect_error(moved, box, (1, 1))
                        self.assertAlmostEqual(life_aspect, robot_aspect, places=6)

    def test_a_decal_on_the_squashed_stock_moves_inward_before_it_shrinks(self):
        fit, to_life, to_model = designs.ROBOT["pulse_rifle"], *self.maps(designs.ROBOT["pulse_rifle"])
        anchor = next(a for a in designs.DECALS["pulse_rifle"] if a["part"] == "Chassis")
        kit = built("pulse_rifle")
        life_box = primitive_bounds(*kit.geometry["Chassis"])
        box = (designs.robot_point(fit, life_box[0]), designs.robot_point(fit, life_box[1]))
        moved = decals.refit_rect(anchor, box, to_life, to_model, fit["cross"])
        u0, v0, u1, v1 = moved["rect"]
        width = (u1 - u0) * (box[1][1] - box[0][1])
        life_width = (anchor["rect"][2] - anchor["rect"][0]) * (life_box[1][1] - life_box[0][1])
        self.assertAlmostEqual(width, life_width * fit["cross"], places=6)
        self.assertLessEqual(u1, .98 + 1e-9)


class PipelineTests(unittest.TestCase):
    def test_robot_stages_close_the_chain_for_contract_4(self):
        names = [stage.name for stage in STAGES]
        self.assertEqual(list(ROBOT_STAGES), names[-3:], "no earlier stage may read the robot files")
        for stage in STAGES[-3:]:
            with self.subTest(stage=stage.name):
                self.assertEqual("robot", stage.when)
                self.assertEqual(4, stage.min_contract)
        robot, game, bake = STAGES[-3:]
        self.assertEqual(("--variant", "robot"), robot.args)
        self.assertEqual((), robot.reads)
        self.assertIn("--robot", game.args)
        self.assertEqual(("qa_game_robot.json",), game.qa)
        self.assertIn("{robot}.blend", game.reads)
        self.assertIn("qa_geometry_robot.json", game.reads)
        self.assertIn("--robot", bake.args)
        self.assertTrue(bake.heavy)
        self.assertEqual(("qa_surface_robot.json",), bake.qa)
        self.assertEqual(("standard", "full"), bake.tiers)

    def test_runs_and_viewer_models_per_tool_and_contract(self):
        for key, tool in TOOLS.items():
            with self.subTest(tool=key):
                for tier in ("quick", "standard"):
                    runs = [run.name for run in expand(tool, tier)]
                    has = key in designs.ROBOT
                    self.assertEqual(has, "robot" in runs)
                    self.assertEqual(has, "game_robot" in runs)
                    self.assertEqual(has and tier == "standard", "surface_bake_robot" in runs)
                    self.assertEqual(has, "viewer_robot" in runs and "viewer_robot_game" in runs)
                    self.assertEqual(has and tier == "standard", "roundtrip_robot" in runs)
                old = dict(tool, game_contract="3")
                self.assertFalse([run.name for run in expand(old, "standard") if "robot" in run.name],
                                 "contract 3 packages carry no robot variant")
                self.assertNotIn("robot", [variant.name for variant in variants(old)])
        tool = TOOLS["assault_rifle"]
        viewer = {run.name: run for run in expand(tool, "quick")}
        self.assertEqual("CubeEscape_AssaultRifle_Robot", viewer["viewer_robot"].variant["root"])
        self.assertEqual("CubeEscape_AssaultRifle_Robot_Game", viewer["viewer_robot_game"].variant["root"])
        self.assertEqual("AssaultRifle_Use", viewer["viewer_robot_game"].variant["clip"])

    def test_contract_and_qa_names(self):
        self.assertEqual("unity_contract_robot.json", ge.contract_name(False, robot=True))
        self.assertEqual("unity_contract.json", ge.contract_name(False))
        self.assertEqual("unity_contract_fps.json", ge.contract_name(True))
        self.assertEqual(("qa_game.json", "qa_game_fps.json", "qa_game_robot.json"),
                         (ge.qa_name(False), ge.qa_name(True), ge.qa_name(False, True)))

    def test_budget_and_opening_probes_cover_the_variant(self):
        budget = json.loads((ROOT / "data/game_budget.json").read_text())
        for key in designs.ROBOT:
            self.assertIn(key, budget["world"])
            self.assertIn(key, ge.OPENING_PROBES)


if __name__ == "__main__":
    unittest.main()
