"""Toolgen 0.23 Livery: fingerprints of the golden surface maps (toolgen/map_fingerprint.py) and the three verdicts of the golden
(toolgen/surface_golden.py: identical, within the tolerance, failed). Pure Python, no Blender."""
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
import map_fingerprint as mf  # noqa: E402
import surface  # noqa: E402
import surface_golden as golden  # noqa: E402

SIZE = 128                      # two texels per thumbnail block side
TOLERANCE = {"share": .005, "levels": 1, "block_levels": 1}


def image(fill=(128, 128, 255, 255), size=SIZE):
    return bytearray(bytes(fill) * (size * size))


def set_texel(pixels, x, y, channel, value, size=SIZE):
    pixels[(y * size + x) * 4 + channel] = value


def png(pixels, size=SIZE):
    """PNG with filter None on every row (surface.png_bytes), readable by both decoders."""
    stride = size * 4
    raw = b"".join(b"\x00" + bytes(pixels[y * stride:(y + 1) * stride]) for y in range(size))
    return surface.png_bytes(raw, size, size, 4)


def fp(pixels, size=SIZE):
    data = png(pixels, size)
    return mf.fingerprint(size, size, bytes(pixels), hashlib.sha256(data).hexdigest())


class FingerprintTests(unittest.TestCase):
    def test_means_histogram_and_blocks(self):
        pixels = image((0, 255, 10, 255))
        for y in range(2):                                   # the top-left block of channel R: 4 texels at 255, 0, 0, 0
            for x in range(2):
                set_texel(pixels, x, y, 0, 255 if (x, y) == (0, 0) else 0)
        entry = fp(pixels)
        self.assertEqual([SIZE, SIZE], entry["size"])
        self.assertEqual(mf.GRID, entry["grid"])
        self.assertAlmostEqual(255 / (SIZE * SIZE), entry["mean"][0], places=3)
        self.assertEqual([255.0, 10.0, 255.0], entry["mean"][1:])
        hist = mf.histograms(entry)
        self.assertEqual(1, hist[0][255])
        self.assertEqual(SIZE * SIZE - 1, hist[0][0])
        self.assertEqual(SIZE * SIZE, hist[2][10])
        thumbs = mf.thumbs(entry)
        self.assertEqual(64, thumbs[0][0], "255 / 4 = 63.75 rounds to 64")
        self.assertEqual(0, thumbs[0][1])
        self.assertTrue(all(value == 255 for value in thumbs[1]))

    def test_the_fingerprint_is_small_and_stable(self):
        pixels = image()
        first, second = fp(pixels), fp(bytearray(pixels))
        self.assertEqual(first, second)
        self.assertLess(len(json.dumps(first)), 4096)
        self.assertEqual(hashlib.sha256(png(pixels)).hexdigest(), first["sha256"])

    def test_sizes_off_the_grid_are_refused(self):
        with self.assertRaises(ValueError):
            mf.fingerprint(100, 100, bytes(100 * 100 * 4))
        with self.assertRaises(ValueError):
            mf.fingerprint(SIZE, SIZE, bytes(10))

    def test_block_uv_and_map_kind(self):
        self.assertEqual((0, 1 - 1 / 64, 1 / 64, 1), mf.block_uv(0), "row 0 of the PNG is v = 1")
        self.assertEqual((1 - 1 / 64, 0, 1, 1 / 64), mf.block_uv(64 * 64 - 1))
        self.assertEqual("W0", mf.map_kind("CubeEscape_X_FPS_Game_W0.png"))
        self.assertEqual("Normal", mf.map_kind("CubeEscape_X_Game_Normal.png"))


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.pixels = image()
        self.reference = fp(self.pixels)

    def judge(self, pixels, name="X_Game_Normal.png", model=None):
        return mf.judge(name, mf.compare(self.reference, fp(pixels)), TOLERANCE, model)

    def test_identical_maps_differ_nowhere(self):
        comparison = mf.compare(self.reference, fp(self.pixels))
        self.assertTrue(all(c["moved"] == 0 and c["shift"] == 0 and c["block"] == 0 for c in comparison["channels"]))
        within, text = mf.judge("X_Game_Normal.png", comparison, TOLERANCE)
        self.assertTrue(within)
        self.assertIn("same histograms and block means", text)

    def test_one_texel_one_level_is_bake_noise(self):
        """The noise of the normal bake (0.15.1-0.20): one texel, one level."""
        noisy = bytearray(self.pixels)
        set_texel(noisy, 40, 70, 1, 129)
        within, text = self.judge(noisy)
        self.assertTrue(within, text)
        self.assertIn("within the tolerance", text)
        self.assertIn("normal Y", text)

    def test_many_texels_one_level_fail(self):
        changed = bytearray(self.pixels)
        for index in range(int(SIZE * SIZE * .01)):            # 1 % of the texels, one level each, spread
            set_texel(changed, (index * 7) % SIZE, (index * 13) % SIZE, 0, 127)
        within, text = self.judge(changed)
        self.assertFalse(within)
        self.assertIn("texels changed", text)
        self.assertIn("normal X", text)

    def test_one_texel_by_many_levels_fails(self):
        changed = bytearray(self.pixels)
        set_texel(changed, 3, 3, 2, 200)
        within, text = self.judge(changed)
        self.assertFalse(within)
        self.assertIn("levels on average", text)

    def test_a_moved_region_fails_with_its_place(self):
        """A W0 region moved by one texel: the histogram stays, the block means move - map, channel, block and region."""
        def w0(offset):
            pixels = image((0, 0, 0, 0))
            for y in range(32, 48):
                for x in range(10 + offset, 20 + offset):
                    set_texel(pixels, x, y, 2, 255)             # Accent
            return pixels
        reference, moved = fp(w0(0)), fp(w0(1))
        comparison = mf.compare(reference, moved)
        self.assertEqual(0, comparison["channels"][2]["moved"], "same texel count")
        within, text = mf.judge("X_Game_W0.png", comparison, TOLERANCE, {"W0": reference}, moved)
        self.assertFalse(within)
        self.assertIn("channel Accent", text)
        self.assertIn("block u 0.156-0.172", text)              # texel 20 of 128 (new right edge) = block 10
        self.assertIn("region Accent", text)

    def test_another_size_fails(self):
        small = mf.fingerprint(64, 64, bytes(image(size=64)), "x")
        within, text = mf.judge("X_Game_W0.png", mf.compare(self.reference, small), TOLERANCE)
        self.assertFalse(within)
        self.assertIn("size", text)


class GoldenTests(unittest.TestCase):
    """The three verdicts of the golden (surface_golden.golden_check) on a temporary golden and output folder."""

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)
        self.output, self.golden = self.folder / "output", self.folder / "golden"
        (self.output / "t").mkdir(parents=True)
        self.base = {"X_Game_Normal.png": image(), "X_Game_W0.png": image((255, 0, 0, 0))}
        self.write(self.base)
        golden.golden_check(self.output, ["t"], update=True, folder=self.golden)

    def write(self, maps):
        for name, pixels in maps.items():
            (self.output / "t" / name).write_bytes(png(pixels))

    def check(self, update=False):
        return golden.golden_check(self.output, ["t"], update=update, folder=self.golden)

    def manifest(self):
        return json.loads((self.golden / "manifest.json").read_text())

    def test_identical_maps_are_green(self):
        result = self.check()
        self.assertEqual((2, [], [], []), (result["compared"], result["errors"], result["tolerated"],
                                           result["alternate_matches"]))
        self.assertEqual(golden.DEFAULT_TOLERANCE, self.manifest()["tolerance"])
        self.assertEqual({"X_Game_Normal.png", "X_Game_W0.png"},
                         set(golden.load_fingerprints("t", self.golden)))

    def test_bake_noise_is_green_with_a_note_and_update_keeps_the_reference(self):
        noisy = bytearray(self.base["X_Game_Normal.png"])
        set_texel(noisy, 5, 9, 0, 129)
        self.write({"X_Game_Normal.png": noisy})
        before = self.manifest()["maps"]["t"]["X_Game_Normal.png"]
        result = self.check()
        self.assertEqual([], result["errors"])
        self.assertEqual(1, len(result["tolerated"]))
        self.assertIn("t/X_Game_Normal.png: within the tolerance", result["tolerated"][0])
        self.check(update=True)
        self.assertEqual(before, self.manifest()["maps"]["t"]["X_Game_Normal.png"], "noise never moves the reference")

    def test_a_real_change_is_red_until_updated(self):
        changed = bytearray(self.base["X_Game_W0.png"])
        for y in range(40):
            for x in range(40):
                set_texel(changed, x, y, 0, 0)
                set_texel(changed, x, y, 1, 255)
        self.write({"X_Game_W0.png": changed})
        result = self.check()
        self.assertEqual(1, len(result["errors"]))
        self.assertIn("t/X_Game_W0.png: channel", result["errors"][0])
        self.assertIn("region Primary", result["errors"][0])
        updated = self.check(update=True)
        self.assertEqual(["t/X_Game_W0.png"], updated["updated"])
        self.assertEqual(hashlib.sha256(png(changed)).hexdigest(), self.manifest()["maps"]["t"]["X_Game_W0.png"])
        self.assertEqual([], self.check()["errors"])

    def test_a_weight_map_change_inside_a_block_is_red(self):
        """Judge finding 22.10.2026: W0/W1 are one-hot - a region moved inside one block keeps histogram and block means, so
        the fingerprint sees nothing; only Normal maps (the measured bake noise) get a tolerance, W0/W1/Fields stay sha256."""
        def w0(x, y):                                           # all Primary, one Secondary texel at (x, y)
            pixels = bytearray(self.base["X_Game_W0.png"])
            set_texel(pixels, x, y, 0, 0)
            set_texel(pixels, x, y, 1, 255)
            return pixels
        self.write({"X_Game_W0.png": w0(0, 0)})
        self.check(update=True)
        swapped = w0(1, 1)                                      # the same texel moves inside block 0 (2 x 2 texels)
        reference = golden.load_fingerprints("t", self.golden)["X_Game_W0.png"]
        self.assertTrue(mf.judge("X_Game_W0.png", mf.compare(reference, fp(swapped)), golden.DEFAULT_TOLERANCE)[0],
                        "the fingerprint alone cannot see it")
        self.write({"X_Game_W0.png": swapped})
        result = self.check()
        self.assertEqual(1, len(result["errors"]))
        self.assertIn("only Normal maps have a tolerance", result["errors"][0])
        self.assertEqual([], result["tolerated"])

    def test_legacy_alternates_still_count_and_stale_maps_fail(self):
        manifest = self.manifest()
        noisy = bytearray(self.base["X_Game_Normal.png"])
        set_texel(noisy, 5, 9, 0, 129)
        manifest["alternates"] = {"t": {"X_Game_Normal.png": [hashlib.sha256(png(noisy)).hexdigest()]}}
        manifest["stale"] = {"note": "pending", "maps": {"t": ["X_Game_W0.png"]}}
        (self.golden / "manifest.json").write_text(json.dumps(manifest))
        self.write({"X_Game_Normal.png": noisy})
        result = self.check()
        self.assertEqual(["t/X_Game_Normal.png"], result["alternate_matches"])
        self.assertEqual(1, len(result["errors"]))
        self.assertIn("stale", result["errors"][0])
        self.check(update=True)
        self.assertNotIn("stale", self.manifest())
        self.assertIn("X_Game_Normal.png", self.manifest()["alternates"]["t"], "an alternate goes only with new content")

    def test_a_map_without_fingerprint_fails_when_it_differs(self):
        shutil.rmtree(self.golden / golden.FINGERPRINTS)
        self.assertEqual([], self.check()["errors"], "identical maps need no fingerprint")
        noisy = bytearray(self.base["X_Game_Normal.png"])
        set_texel(noisy, 5, 9, 0, 129)
        self.write({"X_Game_Normal.png": noisy})
        self.assertIn("no fingerprint", self.check()["errors"][0])


class RepositoryGoldenTests(unittest.TestCase):
    """The migrated golden (0.23): every map keeps its sha256 and has a fingerprint of a confirmed bake of it."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((golden.GOLDEN / "manifest.json").read_text())

    def test_every_map_has_a_fingerprint_of_its_primary_or_an_alternate(self):
        count = 0
        for tool, maps in self.manifest["maps"].items():
            fingerprints = golden.load_fingerprints(tool)
            self.assertEqual(set(maps), set(fingerprints), tool)
            for name, digest in maps.items():
                with self.subTest(tool=tool, map=name):
                    entry = fingerprints[name]
                    accepted = [digest, *self.manifest.get("alternates", {}).get(tool, {}).get(name, []),
                                *self.manifest.get("retired_alternates", {}).get(tool, {}).get(name, [])]
                    self.assertIn(entry["sha256"], accepted)
                    size = 2048 if "_FPS_Game_" in name else 512           # full tier (0.22): Ego 2048², world/robot 512²
                    self.assertEqual([size, size], entry["size"])
                    self.assertEqual(mf.FORMAT, entry["format"])
                    self.assertLess(len(json.dumps(entry)), 24 * 1024, "a few KB per map")
                    count += 1
        self.assertGreaterEqual(count, 104)

    def test_the_tolerance_stays_inside_the_users_guide_value(self):
        tolerance = self.manifest["tolerance"]
        self.assertEqual(["Normal"], tolerance["kinds"], "W0/W1/Fields showed no bake noise: sha256 only")
        self.assertLessEqual(tolerance["share"], .005)                  # user 21.10.2026: <= 0.5 % of the texels
        self.assertLessEqual(tolerance["levels"], 1)                    # by <= 1 level
        self.assertLessEqual(tolerance["block_levels"], 1)

    def test_the_measured_bake_noise_is_inside_the_tolerance(self):
        """22.10.2026, 8 rebakes of unchanged 0.22 packages: the normal maps moved at most 2 texels by 1 level (sniper rifle
        Ego 2048: 0d335739, 47dc547e), 1 at 512 (rocket launcher and sniper rifle robot); nothing else changed."""
        tolerance = self.manifest["tolerance"]
        for texels, moved in ((2048 * 2048, 2), (512 * 512, 1)):
            channel = {"moved": moved, "shift": moved, "block": 0, "block_index": 0, "blocks": 0, "mean": 0.0}
            comparison = {"texels": texels, "channels": [channel] + [dict(channel, moved=0, shift=0)] * 3}
            within, text = mf.judge("X_Game_Normal.png", comparison, tolerance)
            self.assertTrue(within, text)
        # and the step above it fails: one texel two levels off, or 0.02 % of the texels by one level
        two_levels = {"texels": 512 * 512, "channels": [{"moved": 1, "shift": 2, "block": 0, "block_index": 0, "blocks": 0,
                                                          "mean": 0.0}] * 4}
        self.assertFalse(mf.judge("X_Game_Normal.png", two_levels, tolerance)[0])
        many = {"texels": 512 * 512, "channels": [{"moved": 53, "shift": 53, "block": 0, "block_index": 0, "blocks": 0,
                                                    "mean": 0.0}] * 4}
        self.assertFalse(mf.judge("X_Game_Normal.png", many, tolerance)[0])

    def test_alternates_left_are_the_unreproduced_ones(self):
        """0.23 removed every alternate the rebakes reproduced inside the tolerance; only sniper rifle Ego f2718ede stays."""
        self.assertEqual({"sniper_rifle": {"CubeEscape_SniperRifle_FPS_Game_Normal.png": [
            "f2718ede0693bba9988cbaf87d4d4679daa4e5b73ec2939cb4dc41d82ca9ef10"]}}, self.manifest["alternates"])

    def test_fingerprints_unpack(self):
        entry = next(iter(golden.load_fingerprints("pistol").values()))
        self.assertEqual(4, len(mf.thumbs(entry)))
        self.assertEqual(256, len(mf.histograms(entry)[0]))
        self.assertEqual(zlib.decompress, zlib.decompress)


if __name__ == "__main__":
    unittest.main()
