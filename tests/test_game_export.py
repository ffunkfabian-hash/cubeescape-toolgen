"""Game export (toolgen/game_export.py, data/game_palette.json): the pure helpers and the palette contract.

Runs without Blender: game_export imports without bpy (its Blender parts are only reached from main()). The
generator scripts are read with ``ast`` and never executed.
"""
import ast
import hashlib
import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))

import game_export as ge  # noqa: E402

PALETTE = json.loads((ROOT / "data/game_palette.json").read_text())
TOOLS = {tool["id"]: tool for tool in json.loads((ROOT / "data/tools.json").read_text())["tools"]}
ASSETS = ROOT / "scripts/tool_assets"
FIRST_PERSON = ROOT / "toolgen/first_person.py"

# Per tool: the script that creates the world model's materials and the script that defines the ``material`` helper
# (its name prefix). The flashlight reuses the portal gun's helper (``runpy.run_path`` of create_portal_gun.py);
# the bow calls ``bow_geometry.material`` through ``g``.
WORLD_MATERIALS = {
    "portal_emitter": (ASSETS / "Portalkanone/create_portal_gun.py", ASSETS / "Portalkanone/create_portal_gun.py"),
    "magnet_gripper": (ASSETS / "Magnetgreifer/create_magnet_gripper.py", ASSETS / "Magnetgreifer/create_magnet_gripper.py"),
    "flashlight": (ASSETS / "Taschenlampe/create_flashlight.py", ASSETS / "Portalkanone/create_portal_gun.py"),
    "bow": (ASSETS / "Bogen/create_standard_bow.py", ASSETS / "Bogen/bow_geometry.py"),
}


# --------------------------------------------------------------------------------------------- AST helpers
def parse(path):
    tree = ast.parse(Path(path).read_text(), filename=str(path))
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child.parent = parent
    return tree


def helper_prefix(path):
    """Prefix of ``bpy.data.materials.new(<prefix> + name)`` inside the file's ``def material``."""
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.FunctionDef) and node.name == "material":
            for call in ast.walk(node):
                if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "new"
                        and isinstance(call.args[0], ast.BinOp) and isinstance(call.args[0].left, ast.Constant)):
                    return call.args[0].left.value
    raise AssertionError(f"no material helper with a name prefix in {path}")


def loop_rows(call, names):
    """Rows (dicts name -> value) of the nearest enclosing ``for a, b in [(..), (..)]`` that binds all ``names``."""
    node = call.parent
    while node is not None:
        if isinstance(node, ast.For) and isinstance(node.target, ast.Tuple):
            targets = [element.id for element in node.target.elts if isinstance(element, ast.Name)]
            if all(name in targets for name in names):
                return [dict(zip(targets, ast.literal_eval(row))) for row in node.iter.elts]
        node = node.parent
    raise AssertionError(f"line {call.lineno}: {names} are not bound by a literal for loop")


def material_calls(path):
    """[(source name, emission, line)] of every ``material(...)`` / ``x.material(...)`` call except the definition.
    Names and the emission are literals or loop variables over literal tuple lists (the bow's material table)."""
    found = []
    for call in ast.walk(parse(path)):
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        if not ((isinstance(func, ast.Name) and func.id == "material")
                or (isinstance(func, ast.Attribute) and func.attr == "material")):
            continue
        emission_arg = call.args[4] if len(call.args) > 4 else next(
            (keyword.value for keyword in call.keywords if keyword.arg == "emission"), ast.Constant(0))
        variables = [arg.id for arg in (call.args[0], emission_arg) if isinstance(arg, ast.Name)]
        rows = loop_rows(call, variables) if variables else [{}]

        def value(expression, row):
            return row[expression.id] if isinstance(expression, ast.Name) else ast.literal_eval(expression)
        for row in rows:
            found.append((value(call.args[0], row), value(emission_arg, row), call.lineno))
    return found


def defined_materials(tool_id):
    script, helper = WORLD_MATERIALS[tool_id]
    prefix = helper_prefix(helper)
    return [(prefix + name, emission, line) for name, emission, line in material_calls(script)]


def first_person_materials():
    prefix = helper_prefix(FIRST_PERSON)
    return [(prefix + name, emission, line) for name, emission, line in material_calls(FIRST_PERSON)]


# --------------------------------------------------------------------------------------------- rotation helpers
def axis_angle_matrix(axis, degrees):
    length = math.sqrt(sum(a * a for a in axis))
    x, y, z = (a / length for a in axis)
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    t = 1 - c
    return [[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c]]


def apply_matrix(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def apply_quaternion(q, v):
    """Rotate v by the unit quaternion (x, y, z, w): v + 2 w (u x v) + 2 u x (u x v) with u = (x, y, z)."""
    u, w = q[:3], q[3]
    cross = lambda a, b: [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
    t = [2 * c for c in cross(u, v)]
    return [v[i] + w * t[i] + cross(u, t)[i] for i in range(3)]


ROTATIONS = [(axis, angle) for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, -2, 3), (-1, 1, 1))
             for angle in (0, 30, 90, 135, 180, -90, 200)]
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


class Near(unittest.TestCase):
    def assertVectorNear(self, a, b, places=5):
        self.assertEqual(len(a), len(b))
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, places=places, msg=f"{a} != {b}")


# --------------------------------------------------------------------------------------------- 1. palette complete
class PaletteCoverageTests(unittest.TestCase):
    def test_parser_finds_the_material_tables(self):
        self.assertEqual("PG_", helper_prefix(WORLD_MATERIALS["portal_emitter"][1]))
        self.assertEqual("MG_", helper_prefix(WORLD_MATERIALS["magnet_gripper"][1]))
        self.assertEqual("BW_", helper_prefix(WORLD_MATERIALS["bow"][1]))
        self.assertEqual("FPS_Robot_", helper_prefix(FIRST_PERSON))
        names = {name for name, _, _ in defined_materials("bow")}
        self.assertTrue({"BW_Armor", "BW_Cyan", "BW_Amber", "BW_Rubber", "BW_PaleCyan"} <= names, names)  # tuple list + calls
        self.assertIn("PG_WarmCore", {name for name, _, _ in defined_materials("flashlight")})  # via the portal helper
        self.assertEqual({"FPS_Robot_White", "FPS_Robot_Grey", "FPS_Robot_Dark", "FPS_Robot_Cyan", "FPS_Robot_Orange"},
                         {name for name, _, _ in first_person_materials()})

    def test_flashlight_really_uses_the_portal_gun_helper(self):
        text = WORLD_MATERIALS["flashlight"][0].read_text()
        self.assertIn("create_portal_gun.py", text)
        self.assertIn("HELPER['material']", text)

    def test_every_tool_script_is_listed(self):
        self.assertEqual(set(TOOLS), set(WORLD_MATERIALS), "a new tool needs an entry in WORLD_MATERIALS")
        for tool_id, (script, _) in WORLD_MATERIALS.items():
            self.assertEqual(script.name, TOOLS[tool_id]["world"])
            self.assertEqual(script.parent.name, TOOLS[tool_id]["folder"])

    def test_no_material_is_created_behind_the_parsers_back(self):
        """Only the known helpers create Blender materials in the generator scripts (game_export builds the palette)."""
        creators = {path.resolve() for path in (WORLD_MATERIALS["portal_emitter"][1], WORLD_MATERIALS["magnet_gripper"][1],
                                                 WORLD_MATERIALS["bow"][1], FIRST_PERSON)}
        for path in [*ASSETS.rglob("*.py"), *(ROOT / "toolgen").glob("*.py")]:
            if path.name == "game_export.py":
                continue
            with self.subTest(path=str(path.relative_to(ROOT))):
                has_new = "materials.new(" in path.read_text()
                if has_new:
                    self.assertIn(path.resolve(), creators)

    def test_every_defined_material_is_in_the_palette_map(self):
        for tool_id in WORLD_MATERIALS:
            for name, _, line in defined_materials(tool_id):
                with self.subTest(tool=tool_id, material=name, line=line):
                    self.assertIn(name, PALETTE["map"])
        for name, _, line in first_person_materials():
            with self.subTest(first_person=name, line=line):
                self.assertIn(name, PALETTE["map"])

    def test_every_map_target_exists(self):
        self.assertTrue(set(PALETTE["map"].values()) <= set(PALETTE["materials"]))

    def test_emission_survives_the_mapping(self):
        """Glowing sources land on a glow material, matte sources never on one."""
        sources = [item for tool_id in WORLD_MATERIALS for item in defined_materials(tool_id)] + first_person_materials()
        for name, emission, line in sources:
            target = PALETTE["materials"][PALETTE["map"][name]]
            with self.subTest(material=name, line=line):
                self.assertEqual(emission > 0, target["emission"] > 0, f"{name} -> {PALETTE['map'][name]}")


# --------------------------------------------------------------------------------------------- 2. palette rules
class PaletteRulesTests(unittest.TestCase):
    def test_shipped_palette_is_valid(self):
        self.assertEqual([], ge.validate_palette(PALETTE))

    def test_matte_limits_hold_for_every_non_glow_material(self):
        for name, spec in PALETTE["materials"].items():
            with self.subTest(material=name):
                if spec["emission"] > 0:
                    self.assertTrue(name.startswith("M_Glow"))
                else:
                    self.assertFalse(name.startswith("M_Glow"))
                    self.assertLessEqual(spec["metallic"], .35)
                    self.assertGreaterEqual(spec["roughness"], .55)

    def test_palette_names_are_cube_escape_materials(self):
        for name in PALETTE["materials"]:
            self.assertTrue(name.startswith("M_"), name)

    def test_at_most_six_palette_materials_per_tool(self):
        self.assertEqual(6, PALETTE["max_materials_per_tool"])
        for tool_id in WORLD_MATERIALS:
            targets = {PALETTE["map"][name] for name, _, _ in defined_materials(tool_id)}
            with self.subTest(tool=tool_id):
                self.assertTrue(0 < len(targets) <= PALETTE["max_materials_per_tool"], sorted(targets))
        self.assertLessEqual(len(PALETTE["materials"]), 6 + 3, "palette grew, review the per-tool limit")

    def test_map_prefixes_match_the_tool_helpers(self):
        prefixes = {helper_prefix(helper) for _, helper in WORLD_MATERIALS.values()} | {helper_prefix(FIRST_PERSON)}
        self.assertEqual({"PG_", "MG_", "BW_", "FPS_Robot_"}, prefixes)
        for source in PALETTE["map"]:
            self.assertTrue(source.startswith(tuple(prefixes)), source)

    def valid(self):
        return json.loads(json.dumps(PALETTE))

    def test_validate_rejects_a_foreign_material_name(self):
        palette = self.valid()
        palette["materials"]["Steel"] = palette["materials"]["M_Metal"]
        self.assertTrue(any("Steel" in error and "M_" in error for error in ge.validate_palette(palette)))

    def test_validate_rejects_shiny_or_rough_violations(self):
        palette = self.valid()
        palette["materials"]["M_Metal"]["metallic"] = .36
        self.assertTrue(any("M_Metal" in error and "not matte" in error for error in ge.validate_palette(palette)))
        palette = self.valid()
        palette["materials"]["M_RobotBody"]["roughness"] = .3
        self.assertTrue(any("M_RobotBody" in error and "not matte" in error for error in ge.validate_palette(palette)))

    def test_validate_lets_glow_materials_be_shiny(self):
        palette = self.valid()
        palette["materials"]["M_GlowCyan"]["metallic"] = .9
        palette["materials"]["M_GlowCyan"]["roughness"] = .1
        self.assertEqual([], ge.validate_palette(palette))

    def test_validate_binds_emission_to_glow_names(self):
        palette = self.valid()
        palette["materials"]["M_Metal"]["emission"] = 1.0
        self.assertTrue(any("M_Metal" in error and "emit" in error for error in ge.validate_palette(palette)))
        palette = self.valid()
        palette["materials"]["M_GlowOrange"]["emission"] = 0.0
        self.assertTrue(any("M_GlowOrange" in error and "emit" in error for error in ge.validate_palette(palette)))

    def test_validate_rejects_bad_colors(self):
        for color in ([1, 1], [1.2, 0, 0], [0, 0, -.1]):
            palette = self.valid()
            palette["materials"]["M_Metal"]["color_srgb"] = color
            with self.subTest(color=color):
                self.assertTrue(any("color_srgb" in error for error in ge.validate_palette(palette)))

    def test_validate_rejects_a_map_entry_to_an_unknown_material(self):
        palette = self.valid()
        palette["map"]["PG_Armor"] = "M_Nothing"
        self.assertEqual(["PG_Armor: unknown palette material M_Nothing"], ge.validate_palette(palette))

    def test_srgb_to_linear(self):
        self.assertEqual(0.0, ge.srgb_to_linear(0.0))
        self.assertAlmostEqual(1.0, ge.srgb_to_linear(1.0))
        self.assertAlmostEqual(.04045 / 12.92, ge.srgb_to_linear(.04045))
        self.assertAlmostEqual(.214041, ge.srgb_to_linear(.5), places=6)


# --------------------------------------------------------------------------------------------- 3. axes
class AxisTests(Near):
    def test_mapping_matrix_is_orthogonal_and_mirrors(self):
        m = ge.TO_UNITY
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(1.0 if i == j else 0.0, sum(m[i][k] * m[j][k] for k in range(3)))
        det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
               + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
        self.assertEqual(-1.0, det)        # Blender is right handed, Unity left handed

    def test_position_known_values(self):
        self.assertEqual([-1.0, 3.0, -2.0], ge.unity_position((1, 2, 3)))
        self.assertEqual([0.0, 0.0, 1.0], ge.unity_position((0, -1, 0)))      # Blender front -Y -> Unity forward +Z
        self.assertEqual([0.0, 1.0, 0.0], ge.unity_position((0, 0, 1)))       # up stays up
        self.assertEqual([-1.0, 0.0, 0.0], ge.unity_position((1, 0, 0)))      # right is mirrored
        for value in ge.unity_position((0.0, 0.0, 0.0)):
            self.assertEqual(1.0, math.copysign(1.0, value), "no negative zero in the contract")

    def test_position_agrees_with_the_mapping_matrix(self):
        for vector in ((1, 2, 3), (-.5, .25, 4), (0, 0, 0)):
            self.assertVectorNear(ge.unity_position(vector), apply_matrix(ge.TO_UNITY, vector))

    def test_scale_swaps_y_and_z_without_a_sign(self):
        self.assertEqual([1, 3, 2], ge.unity_scale((1, 2, 3)))
        self.assertEqual([-1, 3, 2], ge.unity_scale((-1, 2, 3)))

    def test_quaternion_known_values(self):
        h = math.sqrt(.5)
        self.assertEqual([0.0, 0.0, 0.0, 1.0], ge.quaternion_xyzw(IDENTITY))
        self.assertVectorNear(ge.quaternion_xyzw(axis_angle_matrix((0, 0, 1), 90)), [0, 0, h, h], 6)
        self.assertVectorNear(ge.quaternion_xyzw(axis_angle_matrix((1, 0, 0), 90)), [h, 0, 0, h], 6)
        self.assertVectorNear(ge.quaternion_xyzw(axis_angle_matrix((0, 1, 0), 90)), [0, h, 0, h], 6)

    def test_quaternion_covers_every_branch_with_half_turns(self):
        for axis, expected in (((1, 0, 0), [1, 0, 0, 0]), ((0, 1, 0), [0, 1, 0, 0]), ((0, 0, 1), [0, 0, 1, 0])):
            with self.subTest(axis=axis):
                self.assertVectorNear(ge.quaternion_xyzw(axis_angle_matrix(axis, 180)), expected, 6)

    def test_quaternion_is_unit_with_nonnegative_w_and_reproduces_the_matrix(self):
        for axis, angle in ROTATIONS:
            matrix = axis_angle_matrix(axis, angle)
            q = ge.quaternion_xyzw(matrix)
            with self.subTest(axis=axis, angle=angle):
                self.assertAlmostEqual(1.0, sum(c * c for c in q), places=5)
                self.assertGreaterEqual(q[3], 0.0)
                for probe in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (.3, -.7, .2)):
                    self.assertVectorNear(apply_quaternion(q, probe), apply_matrix(matrix, probe), 5)

    def test_unity_rotation_known_values(self):
        h = math.sqrt(.5)
        self.assertEqual([0.0, 0.0, 0.0, 1.0], ge.unity_rotation(IDENTITY))
        # The mapping mirrors, so a +90 degree turn about Blender's up axis is a -90 degree turn about Unity's up axis.
        self.assertVectorNear(ge.unity_rotation(axis_angle_matrix((0, 0, 1), 90)), [0, -h, 0, h], 6)
        # Blender's X axis maps to Unity's -X: the rotation axis flips together with the mirror.
        self.assertVectorNear(ge.unity_rotation(axis_angle_matrix((1, 0, 0), 90)), [h, 0, 0, h], 6)
        # Blender's Y axis maps to Unity's -Z, mirrored again: +Z in Unity.
        self.assertVectorNear(ge.unity_rotation(axis_angle_matrix((0, 1, 0), 90)), [0, 0, h, h], 6)

    def test_unity_rotation_turns_unity_points_like_blender_turns_blender_points(self):
        """unity_position(R v) == unity_rotation(R) applied to unity_position(v), for turns about every axis."""
        for axis, angle in ROTATIONS:
            matrix = axis_angle_matrix(axis, angle)
            q = ge.unity_rotation(matrix)
            for probe in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (.4, .3, -.8)):
                with self.subTest(axis=axis, angle=angle, probe=probe):
                    expected = ge.unity_position(apply_matrix(matrix, probe))
                    self.assertVectorNear(apply_quaternion(q, ge.unity_position(probe)), expected, 5)

    def test_turn_about_the_front_axis_keeps_the_front_axis(self):
        """A roll about Blender's front axis (-Y) is a roll about Unity's front axis (+Z), mirrored in sign."""
        h = math.sqrt(.5)
        q = ge.unity_rotation(axis_angle_matrix((0, -1, 0), 90))
        self.assertVectorNear(q, [0, 0, -h, h], 6)
        self.assertVectorNear(apply_quaternion(q, [0, 0, 1]), [0, 0, 1])


class SampleFramesTests(unittest.TestCase):
    def test_markers_ends_even_steps_and_few_key_frames(self):
        frames = ge.sample_frames(1, 25, [10, 18], [1, 5, 25])
        self.assertEqual([1, 4, 5, 7, 10, 13, 16, 18, 19, 22, 25], frames)

    def test_many_key_frames_are_not_added(self):
        self.assertEqual([1, 4, 7, 10, 13, 16, 19, 22, 25], ge.sample_frames(1, 25, [], list(range(1, 26))))
        self.assertIn(2, ge.sample_frames(1, 25, [], list(range(1, 13))))      # twelve are still few

    def test_out_of_range_markers_and_key_frames_are_dropped(self):
        frames = ge.sample_frames(10, 20, [5, 30], [0, 15, 99])
        self.assertEqual(frames, sorted(set(frames)))
        self.assertEqual((10, 20), (frames[0], frames[-1]))
        self.assertTrue(all(10 <= frame <= 20 for frame in frames))
        self.assertIn(15, frames)

    def test_single_frame_and_count(self):
        self.assertEqual([7], ge.sample_frames(7, 7, [], []))
        self.assertEqual([0, 5, 10], ge.sample_frames(0, 10, [], [], count=3))

    def test_ends_are_always_sampled(self):
        for start, end in ((0, 1), (1, 2), (3, 100), (-5, 5)):
            frames = ge.sample_frames(start, end, [], [])
            self.assertEqual((start, end), (frames[0], frames[-1]))


# --------------------------------------------------------------------------------------------- boxes
def cuboid(center, half):
    return [(center[0] + sx * half[0], center[1] + sy * half[1], center[2] + sz * half[2])
            for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def item(points, material=None):
    box = ge.fit_box(points)
    return (box, points, ge.box_volume(box) if material is None else material)


class BoxTests(Near):
    def test_eigenvectors_of_a_diagonal_and_a_rotated_matrix(self):
        values, vectors = ge.symmetric_eigenvectors([[3, 0, 0], [0, 1, 0], [0, 0, 2]])
        self.assertEqual([3, 1, 2], values)
        c = math.cos(math.radians(30)); s = math.sin(math.radians(30))
        r = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
        d = [[4, 0, 0], [0, 1, 0], [0, 0, 1]]
        m = [[sum(r[i][k] * d[k][l] * r[j][l] for k in range(3) for l in range(3)) for j in range(3)] for i in range(3)]
        values, vectors = ge.symmetric_eigenvectors(m)
        self.assertAlmostEqual(4, max(values))
        axis = vectors[values.index(max(values))]
        self.assertAlmostEqual(1.0, abs(axis[0] * c + axis[1] * s), places=6)

    def test_axis_aligned_cuboid_gives_the_aligned_box(self):
        box = ge.fit_box(cuboid((1, 2, 3), (.5, .2, .1)))
        self.assertVectorNear(box[0], [1, 2, 3])
        self.assertEqual(IDENTITY, [list(map(float, axis)) for axis in box[1]])
        self.assertVectorNear(box[2], [.5, .2, .1])
        self.assertAlmostEqual(8 * .5 * .2 * .1, ge.box_volume(box))

    def test_slanted_bar_gets_a_tight_rotated_box(self):
        c = s = math.sqrt(.5)
        bar = [(c * x - s * y, s * x + c * y, z) for x, y, z in cuboid((0, 0, 0), (.5, .05, .03))]
        box = ge.fit_box(bar)
        self.assertAlmostEqual(8 * .5 * .05 * .03, ge.box_volume(box), places=6)
        self.assertAlmostEqual(.5, max(box[2]), places=6)
        axes = [ax for ax, half in zip(box[1], box[2]) if abs(half - .5) < 1e-6][0]
        self.assertAlmostEqual(1.0, abs(axes[0] * c + axes[1] * s), places=6)
        self.assertGreater(box_aligned_volume(bar), ge.box_volume(box) * 3)

    def test_axes_are_orthonormal_and_right_handed(self):
        c = s = math.sqrt(.5)
        bar = [(c * x - s * y, s * x + c * y, z) for x, y, z in cuboid((.2, 0, 0), (.5, .05, .03))]
        axes = ge.fit_box(bar)[1]
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(1.0 if i == j else 0.0, sum(a * b for a, b in zip(axes[i], axes[j])), places=6)
        cross = [axes[0][1] * axes[1][2] - axes[0][2] * axes[1][1], axes[0][2] * axes[1][0] - axes[0][0] * axes[1][2],
                 axes[0][0] * axes[1][1] - axes[0][1] * axes[1][0]]
        self.assertVectorNear(cross, axes[2], 6)

    def test_limits_keep_the_box_inside_the_model_bounds(self):
        """A thin arc fits tighter with its principal axes, but then the corners leave the model: aligned wins."""
        arc = [(math.cos(a) * r, math.sin(a) * r, z) for a in [i * math.pi / 2 / 8 for i in range(9)]
               for r in (1.0, 1.05) for z in (-.02, .02)]
        free = ge.fit_box(arc)
        low = [min(p[i] for p in arc) for i in range(3)]
        high = [max(p[i] for p in arc) for i in range(3)]
        limited = ge.fit_box(arc, limits=(low, high))
        self.assertLess(ge.box_volume(free), ge.box_volume(limited))
        self.assertLessEqual(ge.box_excess(limited, (low, high)), 1e-9)
        self.assertGreater(ge.box_excess(free, (low, high)), .002)

    def test_corner_and_membership_helpers(self):
        box = ge.fit_box(cuboid((0, 0, 0), (1, 2, 3)))
        corners = ge.box_corners(box)
        self.assertEqual(8, len(corners))
        self.assertEqual(sorted(cuboid((0, 0, 0), (1, 2, 3))), sorted(tuple(round(v, 9) + 0.0 for v in c) for c in corners))
        self.assertTrue(ge.point_in_box((0.9, -1.9, 2.9), box))
        self.assertFalse(ge.point_in_box((1.1, 0, 0), box))
        self.assertTrue(ge.point_in_box((1.001, 0, 0), box, slack=.002))
        inner = ge.fit_box(cuboid((0, 0, 0), (.5, .5, .5)))
        self.assertTrue(ge.box_contains(box, inner))
        self.assertFalse(ge.box_contains(inner, box))
        self.assertEqual(IDENTITY, [list(map(float, row)) for row in ge.box_rotation(box)])

    def test_box_rotation_columns_are_the_axes(self):
        axes = [[0, 1, 0], [-1, 0, 0], [0, 0, 1]]
        rotation = ge.box_rotation(((0, 0, 0), axes, (1, 1, 1)))
        for j in range(3):
            self.assertEqual(axes[j], [rotation[i][j] for i in range(3)])


def box_aligned_volume(points):
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    return (high[0] - low[0]) * (high[1] - low[1]) * (high[2] - low[2])


class MergeBoxesTests(unittest.TestCase):
    def test_an_opening_between_two_parts_stays_free(self):
        """Two jaws with a 1.6 m gap: merging would make a box that is mostly empty, so both stay."""
        left = cuboid((-.9, 0, 0), (.1, .1, .1))
        right = cuboid((.9, 0, 0), (.1, .1, .1))
        boxes = ge.merge_boxes([item(left), item(right)], max_boxes=6)
        self.assertEqual(2, len(boxes))
        for probe in ((0, 0, 0), (.5, 0, 0), (-.5, 0, 0), (0, .05, .05)):
            self.assertFalse(any(ge.point_in_box(probe, box) for box in boxes), probe)
        self.assertTrue(any(ge.point_in_box((.9, 0, 0), box) for box in boxes))
        self.assertTrue(any(ge.point_in_box((-.9, 0, 0), box) for box in boxes))

    def test_the_opening_stays_free_in_a_u_shaped_part(self):
        """A grip: back plate plus two prongs. The prongs do not merge across the slot between them."""
        back = cuboid((0, 0, -.45), (.5, .1, .05))
        prong_a = cuboid((-.45, 0, 0), (.05, .1, .4))
        prong_b = cuboid((.45, 0, 0), (.05, .1, .4))
        boxes = ge.merge_boxes([item(back), item(prong_a), item(prong_b)], max_boxes=6)
        self.assertFalse(any(ge.point_in_box((0, 0, .1), box) for box in boxes))
        self.assertFalse(any(ge.point_in_box((0, 0, .35), box) for box in boxes))
        self.assertTrue(any(ge.point_in_box((-.45, 0, .2), box) for box in boxes))

    def test_touching_parts_merge_into_one_box(self):
        a = cuboid((-.25, 0, 0), (.25, .1, .1))
        b = cuboid((.25, 0, 0), (.25, .1, .1))
        boxes = ge.merge_boxes([item(a), item(b)], max_boxes=6)
        self.assertEqual(1, len(boxes))
        self.assertAlmostEqual(8 * .5 * .1 * .1, ge.box_volume(boxes[0]), places=6)

    def test_box_limit_forces_a_merge_even_across_a_gap(self):
        boxes = ge.merge_boxes([item(cuboid((-.9, 0, 0), (.1, .1, .1))), item(cuboid((.9, 0, 0), (.1, .1, .1)))], max_boxes=1)
        self.assertEqual(1, len(boxes))

    def test_contained_boxes_are_dropped(self):
        big = cuboid((0, 0, 0), (1, 1, 1))
        small = cuboid((.2, 0, 0), (.1, .1, .1))
        boxes = ge.merge_boxes([item(big), item(small)], max_boxes=6)
        self.assertEqual(1, len(boxes))
        self.assertAlmostEqual(8.0, ge.box_volume(boxes[0]))

    def test_result_is_sorted_by_volume_and_deterministic(self):
        parts = [item(cuboid((-5, 0, 0), (.1, .1, .1))), item(cuboid((0, 0, 0), (.5, .5, .5))),
                 item(cuboid((5, 0, 0), (.2, .2, .2)))]
        first = ge.merge_boxes(parts, max_boxes=6)
        again = ge.merge_boxes(list(reversed(parts)), max_boxes=6)
        volumes = [ge.box_volume(box) for box in first]
        self.assertEqual(sorted(volumes, reverse=True), volumes)
        self.assertEqual(3, len(first))
        self.assertEqual([[round(v, 9) for v in box[0]] for box in first], [[round(v, 9) for v in box[0]] for box in again])

    def test_single_box_and_empty_input(self):
        part = item(cuboid((0, 0, 0), (.1, .1, .1)))
        self.assertEqual([part[0]], ge.merge_boxes([part], max_boxes=3))
        self.assertEqual([], ge.merge_boxes([], max_boxes=3))


# --------------------------------------------------------------------------------------------- small helpers
class SmallHelperTests(unittest.TestCase):
    def test_base_name_strips_only_blender_duplicate_suffixes(self):
        self.assertEqual("Socket_Muzzle", ge.base_name("Socket_Muzzle.001"))
        self.assertEqual("Socket_Muzzle", ge.base_name("Socket_Muzzle"))
        self.assertEqual("Part.01", ge.base_name("Part.01"))
        self.assertEqual("Part.0001", ge.base_name("Part.0001"))
        self.assertEqual("Part.abc", ge.base_name("Part.abc"))
        self.assertEqual("A.b", ge.base_name("A.b.012"))

    def test_glb_document_reads_the_json_chunk(self):
        document = {"asset": {"version": "2.0"}, "animations": [{"name": "Bow_Use"}]}
        payload = json.dumps(document).encode()
        payload += b" " * (-len(payload) % 4)
        data = struct.pack("<4sII", b"glTF", 2, 20 + len(payload)) + struct.pack("<I4s", len(payload), b"JSON") + payload
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.glb"
            path.write_bytes(data)
            self.assertEqual(document, ge.glb_document(path))
            self.assertEqual(hashlib.sha256(data).hexdigest(), ge.file_sha256(path))
            path.write_bytes(b"JUNK" + data[4:])
            with self.assertRaises(ValueError):
                ge.glb_document(path)

    def test_constants_are_consistent(self):
        self.assertTrue(ge.LOD1_RANGE[0] < ge.LOD1_TARGET < ge.LOD1_RANGE[1])
        self.assertGreaterEqual(ge.MAX_RENDERERS, 2)
        self.assertEqual(set(TOOLS), set(ge.OPENING_PROBES) | {"flashlight"})
        self.assertEqual(PALETTE["max_materials_per_tool"], 6)
        self.assertTrue(ge.MIN_COLLIDER_SIZE_M < ge.MIN_PART_SIZE_M)

    def test_game_export_imports_without_blender(self):
        self.assertIsNone(ge.bpy)


if __name__ == "__main__":
    unittest.main()
