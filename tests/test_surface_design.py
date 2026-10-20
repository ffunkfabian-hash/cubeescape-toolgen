"""Toolgen 0.13 Enamel: surface recipes (data/surface_recipes.json), decals (data/decals.json, weapon_designs.py DECALS,
toolgen/decals.py) and their place in the weight maps - no Blender."""
import json
import math
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
import concept_spec  # noqa: E402
import decals  # noqa: E402
import surface  # noqa: E402
import surface_relief  # noqa: E402
import weapon_designs  # noqa: E402

RECIPES = surface_relief.load()
CATALOG = decals.load()
TOOLS = {tool["id"]: tool for tool in json.loads((ROOT / "data/tools.json").read_text())["tools"]}
WEAPONS = sorted(tool_id for tool_id, tool in TOOLS.items() if tool.get("hold"))
GOLDEN = ROOT / "tests/golden/decals"
HAVE_NUMPY = surface.np is not None
try:
    MAGICK = decals.magick_command()
except decals.ImageMagickError:
    MAGICK = None


class RecordingKit:
    """Stands in for weapon_kit.Kit: records the part names (and axis-aligned boxes) a build function creates."""

    def __init__(self, design):
        self.grip_tilt = design["grip_tilt_degrees"]
        self.element = design["element"]
        self.parts = {}
        self.root = None

    @staticmethod
    def tilt(degrees):
        return degrees

    def _add(self, name, low, high):
        self.parts[name] = (tuple(low), tuple(high))
        return name

    def box(self, name, center, size, mat="Primary", bevel=.006, parent=None, rot=None):
        return self._add(name, [c - s / 2 for c, s in zip(center, size)], [c + s / 2 for c, s in zip(center, size)])

    def cyl(self, name, center, radius, length, mat="Secondary", axis="y", bevel=.002, parent=None, n=28):
        half = [radius] * 3
        half["xyz".index(axis)] = length / 2
        return self._add(name, [c - h for c, h in zip(center, half)], [c + h for c, h in zip(center, half)])

    def tube(self, name, center, outer, inner, length, mat="Secondary", axis="y", parent=None, n=40):
        return self.cyl(name, center, outer, length, mat, axis)

    def slab(self, name, points, width, mat="Primary", x=0.0, bevel=.004, parent=None):
        ys, zs = [p[0] for p in points], [p[1] for p in points]
        return self._add(name, (x - width / 2, min(ys), min(zs)), (x + width / 2, max(ys), max(zs)))

    def glow(self, name, center, size, parent=None, mat=None, rot=None):
        return self.box(name, center, size)

    def bolts(self, name, positions, radius=.0035, axis="x", parent=None, depth=.004):
        for index, position in enumerate(positions):
            self.cyl("%s_%d" % (name, index), position, radius, depth, axis=axis)

    def concept(self, file, clip_nodes):
        """Toolgen 0.18: the parts of a concept sheet (concept_spec.layout) with their bounds."""
        for mesh in concept_spec.layout(file, clip_nodes)["meshes"]:
            self._add(mesh["name"].removeprefix("SM_PG_"), *concept_spec.bounds(mesh["vertices"]))

    def __getattr__(self, name):            # socket, pivot and helpers that create no named part here
        return lambda *args, **kwargs: args[0] if args else None


def parts_of(tool_id):
    kit = RecordingKit(weapon_designs.DESIGNS[tool_id])
    weapon_designs.DESIGNS[tool_id]["build"](kit)
    return kit.parts


class RecipeTests(unittest.TestCase):
    def test_every_weapon_has_a_recipe_and_nothing_else_has(self):
        self.assertEqual(WEAPONS, sorted(RECIPES["weapons"]))

    def test_shipped_recipes_are_valid_and_every_selector_finds_a_part(self):
        parts = {tool_id: sorted(parts_of(tool_id)) for tool_id in WEAPONS}
        self.assertEqual([], surface_relief.recipe_errors(RECIPES, set(TOOLS), parts))

    def test_relief_stays_below_the_silhouette_limit(self):
        self.assertLessEqual(RECIPES["limits"]["max_height_mm"], .3)
        for tool_id, entry in RECIPES["weapons"].items():
            for selector, value in entry["relief"].items():
                with self.subTest(tool=tool_id, selector=selector):
                    self.assertLessEqual(sum(p["strength"] for p in surface_relief.patterns_of(value)), 1.0)

    def test_errors_are_found(self):
        broken = json.loads(json.dumps(RECIPES))
        pistol = broken["weapons"]["pistol"]
        pistol["relief"]["GripShell*"] = [{"type": "knurl", "size_mm": 2, "direction": "z", "across": "z", "strength": .8},
                                          {"type": "grain", "size_mm": .1, "strength": .5}]
        pistol["relief"]["@Glow"] = {"type": "wave", "size_mm": 1, "strength": 1}
        pistol["relief"]["Frame"] = []
        pistol["relief"]["SlideBody"] = {"type": "seams", "size_mm": float("nan"), "width_mm": 1, "direction": "y",
                                         "across": "q", "across_mm": -2, "strength": .5}
        pistol["channels"]["Metal"]["smoothness"] = .9
        pistol["wear"] = "extreme"
        broken["limits"]["max_height_mm"] = .5
        errors = "\n".join(surface_relief.recipe_errors(broken))
        for expected in ("across", "size_mm", "more than 1", "unknown channel", "type 'wave'", "smoothness", "wear",
                         "max_height_mm", "at least one pattern", "finite", "across_mm", "width_mm < size_mm"):
            self.assertIn(expected, errors)

    def test_selectors_first_match_wins_and_channels_catch_the_rest(self):
        relief = {"GripShell*": {}, "SlideBody": {}, "@Metal": {}}
        self.assertEqual(0, surface_relief.select(relief, "GripShell_1", "Primary"))
        self.assertEqual(1, surface_relief.select(relief, "SlideBody", "Primary"))
        self.assertEqual(2, surface_relief.select(relief, "Barrel", "Metal"))
        self.assertEqual(0, surface_relief.select(relief, "GripShell_-1", "Metal"))
        self.assertIsNone(surface_relief.select(relief, "Frame", "Secondary"))
        self.assertEqual(2, surface_relief.select(relief, None, "Metal"))
        self.assertEqual([0, -1, 2], surface_relief.relief_index(relief, ["GripShell_1", "Frame", None],
                                                                 ["Primary", "Secondary", "Metal"]))
        self.assertEqual("GripShell_1", surface_relief.part_name("SM_PG_GripShell_1"))

    def test_recipe_block_carries_the_sheet_values(self):
        entry = RECIPES["weapons"]["sniper_rifle"]
        block = surface_relief.recipe_block("sniper_rifle", entry, RECIPES["limits"], [{"image": "serial_s07"}], "void")
        self.assertEqual(1, block["version"])
        self.assertEqual({"level": "subtle", "amount": .2, "levels": {"subtle": .2, "medium": .5, "strong": .8}}, block["wear"])
        self.assertEqual(set(surface.CHANNELS), set(block["channels"]))
        self.assertEqual("void", block["glow"]["model_element"])
        self.assertEqual("serial_s07", block["decals"][0]["image"])
        self.assertTrue(all(isinstance(v, list) for v in block["relief"]["parts"].values()))
        self.assertIn("0.76", block["minimum_consumer"])

    def test_smoothness_stays_inside_the_matte_finish(self):
        palette = json.loads((ROOT / "data/game_palette.json").read_text())
        ceiling = 1 - palette["finish"]["min_roughness"]
        self.assertLessEqual(RECIPES["limits"]["smoothness_max"], ceiling + 1e-9)


class DecalCatalogTests(unittest.TestCase):
    def test_catalog_and_anchors_are_valid(self):
        self.assertEqual([], decals.catalog_errors(CATALOG))
        for tool_id in WEAPONS:
            with self.subTest(tool=tool_id):
                anchors = weapon_designs.DECALS[tool_id]
                self.assertTrue(anchors, "every weapon of the sheet has decals")
                self.assertEqual([], decals.anchor_errors(anchors, CATALOG, set(parts_of(tool_id))))

    def test_anchor_rects_fit_their_image_and_part(self):
        for tool_id in WEAPONS:
            parts = parts_of(tool_id)
            for anchor in weapon_designs.DECALS[tool_id]:
                width, height = CATALOG["decals"][anchor["image"]]["size"]
                with self.subTest(tool=tool_id, image=anchor["image"]):
                    error = decals.rect_aspect_error(anchor, parts[anchor["part"]], (height, width))
                    self.assertLess(error, decals.ASPECT_TOLERANCE)

    def test_text_needs_its_glyphs(self):
        catalog = json.loads(json.dumps(CATALOG))
        catalog["decals"]["serial_s07"]["elements"][0]["text"] = "Q-07"
        self.assertTrue(any("glyphs missing" in e for e in decals.catalog_errors(catalog)))
        catalog["decals"]["serial_s07"]["elements"][0]["text"] = "S-07-07-07"
        self.assertTrue(any("wider" in e for e in decals.catalog_errors(catalog)))

    def test_bad_anchors_are_found(self):
        bad = [{"part": "Nope", "face": "+w", "rect": (.5, .5, .4, .6), "image": "x", "channel": "Glow", "rotation": 45}]
        errors = "\n".join(decals.anchor_errors(bad, CATALOG, {"SlideBody"}))
        for expected in ("unknown image", "face", "channel", "rotation", "rect", "not in the model"):
            self.assertIn(expected, errors)

    def test_draw_arguments_use_no_font(self):
        for decal_id, decal in CATALOG["decals"].items():
            arguments = decals.draw_args(decal, CATALOG["glyphs"])
            with self.subTest(decal=decal_id):
                self.assertNotIn("-font", arguments)
                self.assertNotIn("text", " ".join(arguments).split("-draw")[-1].split()[:1])

    def test_pgm_reader(self):
        self.assertEqual((2, 1, b"\x00\xff"), decals.read_pgm(b"P5\n# comment\n2 1\n255\n\x00\xff"))
        with self.assertRaises(ValueError):
            decals.read_pgm(b"P6\n1 1\n255\n\x00\x00\x00")


@unittest.skipUnless(MAGICK, "ImageMagick needed")
class DecalRenderingTests(unittest.TestCase):
    """Masks against tests/golden/decals (rendered on the Mac, ImageMagick 7); ImageMagick 6 (Linux) may differ in edge
    pixels only: at most 1.5 % of the texels and 6 % of the lit texels. Pure Python (runs in ./check)."""
    TOLERANCE = .015

    def compare(self, decal_id, command):
        width, height, pixels = decals.render(decal_id, CATALOG, command)
        golden_width, golden_height, _, rows = surface.png_decode((GOLDEN / f"{decal_id}.png").read_bytes())
        golden = b"".join(bytes(row) for row in rows)
        self.assertEqual((golden_width, golden_height), (width, height))
        self.assertTrue(set(pixels) <= {0, 255})
        differ = sum(a != b for a, b in zip(pixels, golden))
        lit = sum(1 for value in golden if value)
        self.assertLessEqual(differ, self.TOLERANCE * len(golden), decal_id)
        self.assertLessEqual(differ, self.TOLERANCE * 4 * max(lit, 1), decal_id)
        return pixels

    def test_every_decal_matches_its_golden_mask(self):
        for decal_id in CATALOG["decals"]:
            with self.subTest(decal=decal_id):
                pixels = self.compare(decal_id, None)
                share = sum(1 for value in pixels if value) / len(pixels)
                self.assertTrue(.03 < share < .7, f"{decal_id}: {share:.3f} of the image is lit")

    def test_rendering_is_repeatable(self):
        self.assertEqual(decals.render("serial_s07", CATALOG), decals.render("serial_s07", CATALOG))

    @unittest.skipUnless(shutil.which("convert"), "convert (ImageMagick 6 entry) missing")
    def test_the_convert_entry_gives_the_same_masks(self):
        for decal_id in CATALOG["decals"]:
            with self.subTest(decal=decal_id):
                self.compare(decal_id, [shutil.which("convert")])


@unittest.skipUnless(HAVE_NUMPY, "numpy needed")
class DecalProjectionTests(unittest.TestCase):
    """A box part (two triangles per face) in its own UV island: the decal lands on its +x face only."""

    def setUp(self):
        np = surface.np
        # +x face of a 40 x 20 mm part at x = 0.01, its UV island at u, v in [0.25, 0.75] x [0.25, 0.5]
        self.corners = np.array([[[.01, -.02, 0], [.01, .02, 0], [.01, .02, .02]],
                                 [[.01, -.02, 0], [.01, .02, .02], [.01, -.02, .02]],
                                 [[-.01, .02, 0], [-.01, -.02, 0], [-.01, -.02, .02]]])    # -x face
        self.uv = np.array([[[.25, .25], [.75, .25], [.75, .5]], [[.25, .25], [.75, .5], [.25, .5]],
                            [[.8, .8], [.9, .8], [.9, .9]]])
        self.raster = surface.rasterize(self.uv, np.arange(3, dtype=np.int32), 64)
        self.texels = decals.texel_positions(self.raster, self.uv, self.corners)
        self.normals = decals.face_normals(self.corners)
        self.parts = np.array([0, 0, 0])
        self.box = ((-.01, -.02, 0), (.01, .02, .02))

    def test_barycentric_positions_lie_on_the_face(self):
        ys, xs, tris, positions = self.texels
        on_plus = tris < 2
        self.assertTrue(surface.np.allclose(positions[on_plus, 0], .01))
        self.assertTrue(surface.np.all((positions[:, 1] >= -.0201) & (positions[:, 1] <= .0201)))

    def test_full_mask_fills_the_rect_on_the_facing_side_only(self):
        np = surface.np
        mask = np.full((10, 20), 255, dtype=np.uint8)
        anchor = {"part": "P", "face": "+x", "rect": (.25, .25, .75, .75), "image": "x", "channel": "Accent"}
        hit = decals.project(anchor, mask, self.texels, self.parts, self.normals, 0, self.box)
        ys, xs, tris, positions = self.texels
        self.assertTrue(hit.any())
        self.assertFalse(hit[tris == 2].any(), "the -x face gets nothing")
        self.assertTrue(np.all((positions[hit, 1] >= -.0101) & (positions[hit, 1] <= .0101)))
        self.assertTrue(np.all((positions[hit, 2] >= .0049) & (positions[hit, 2] <= .0151)))
        share = hit.sum() / (tris < 2).sum()
        self.assertAlmostEqual(.25, share, delta=.06)

    def test_other_parts_and_rotations(self):
        np = surface.np
        mask = np.zeros((10, 10), dtype=np.uint8)
        mask[:, :5] = 255                                   # left half lit
        anchor = {"part": "P", "face": "+x", "rect": (0, 0, 1, 1), "image": "x", "channel": "Accent"}
        ys, xs, tris, positions = self.texels
        hit = decals.project(anchor, mask, self.texels, self.parts, self.normals, 0, self.box)
        self.assertTrue(np.all(positions[hit, 1] < .0005), "u runs along +y on the +x face: left half = -y")
        turned = decals.project(dict(anchor, rotation=180), mask, self.texels, self.parts, self.normals, 0, self.box)
        self.assertTrue(np.all(positions[turned, 1] > -.0005))
        none = decals.project(anchor, mask, self.texels, np.array([1, 1, 1]), self.normals, 0, self.box)
        self.assertFalse(none.any())

    def test_decal_texels_keep_the_weights_one_hot(self):
        np = surface.np
        channel = np.where(self.raster >= 0, 0, -1).astype(np.int32)        # Primary everywhere
        hit = decals.project({"part": "P", "face": "+x", "rect": (.25, .25, .75, .75), "image": "x", "channel": "Accent"},
                             np.full((4, 4), 255, dtype=np.uint8), self.texels, self.parts, self.normals, 0, self.box)
        ys, xs, _, _ = self.texels
        channel[ys[hit], xs[hit]] = surface.CHANNELS.index("Accent")
        maps, _ = surface.weight_maps(channel)
        maps["Fields"] = np.full(maps["W0"].shape, 255, dtype=np.uint8)
        values = surface.map_checks(maps, channel, ["Primary", "Accent"], 0)
        self.assertTrue(values["one_hot_inside"])
        self.assertEqual(255, values["min_weight_sum_inside"])
        self.assertGreaterEqual(values["texels_per_channel"]["Accent"], int(hit.sum()))
        self.assertGreater(values["texels_per_channel"]["Accent"], 0)

    def test_aspect_error(self):
        anchor = {"face": "+x", "rect": (0, 0, 1, 1), "rotation": 0}
        self.assertAlmostEqual(0, decals.rect_aspect_error(anchor, ((0, 0, 0), (0, .04, .02)), (100, 200)))
        self.assertAlmostEqual(3, decals.rect_aspect_error(dict(anchor, rotation=90), ((0, 0, 0), (0, .04, .02)), (100, 200)))
        self.assertTrue(math.isinf(decals.rect_aspect_error(anchor, ((0, 0, 0), (0, 0, .02)), (100, 200))))


if __name__ == "__main__":
    unittest.main()
