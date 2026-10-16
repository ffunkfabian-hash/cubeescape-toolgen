"""Contract 4 surface data: channel table, PNG format, raster rules and the surface_bake stage (no Blender)."""
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
import surface  # noqa: E402
from generate_tools import (  # noqa: E402
    GAME_CONTRACT, ROUNDTRIP_TIERS, STAGES, assemble_package, catalog, declaration, expand, surface_note,
)

PALETTE = json.loads((ROOT / "data/game_palette.json").read_text())
HAVE_NUMPY = surface.np is not None


class ChannelTableTests(unittest.TestCase):
    def test_regions_are_cube_escapes_mask_layout(self):
        # Cube Escape 0.71 SurfacePaint.hlsl: weights = {w0.r, w0.g, w0.b, w1.r, w1.g, w1.b, w0.a}
        self.assertEqual({"W0.r": "Primary", "W0.g": "Secondary", "W0.b": "Accent", "W0.a": "Emission",
                          "W1.r": "Metal", "W1.g": "Detail", "W1.b": "Energy"}, surface.REGIONS)
        self.assertEqual(set(surface.CHANNELS), set(surface.REGIONS.values()))
        self.assertEqual(("W1", 2), surface.TARGETS["Energy"])
        self.assertEqual(("W0", 3), surface.TARGETS["Emission"])

    def test_shipped_channel_map_is_complete(self):
        self.assertEqual([], surface.channel_map_errors(PALETTE))
        for name in PALETTE["materials"]:
            self.assertIn(surface.channel_of(name, PALETTE), surface.CHANNELS)

    def test_equipment_slots_carry_their_channel(self):
        for slot in PALETTE["channels"]["slots"]:
            self.assertEqual(slot[3:], surface.channel_of(slot, PALETTE))

    def test_same_assignment_as_cube_escapes_definitions(self):
        expected = {"M_RobotBody_Matte": "Primary", "M_RobotDark_Matte": "Secondary", "M_HazardOrange_Matte": "Accent",
                    "M_Metal_Matte": "Metal", "M_GlowOrange": "Emission", "M_GlowCyan": "Energy", "M_GlowWarm": "Energy"}
        for name, channel in expected.items():
            self.assertEqual(channel, surface.channel_of(name, PALETTE), name)

    def test_errors_for_missing_and_unknown_entries(self):
        palette = json.loads(json.dumps(PALETTE))
        del palette["channel_map"]["materials"]["M_Metal_Matte"]
        palette["channel_map"]["materials"]["M_Unknown"] = "Primary"
        errors = surface.channel_map_errors(palette)
        self.assertTrue(any("M_Metal_Matte" in error for error in errors))
        self.assertTrue(any("M_Unknown" in error for error in errors))
        palette = json.loads(json.dumps(PALETTE))
        palette["channel_map"]["materials"]["M_GlowCyan"] = "Glow"
        self.assertTrue(surface.channel_map_errors(palette))
        self.assertTrue(surface.channel_map_errors({k: v for k, v in PALETTE.items() if k != "channel_map"}))

    def test_model_channel_map_leaves_out_unmapped_slots(self):
        result = surface.model_channel_map(PALETTE, ["MT_Primary", "M_RobotBody_Matte", "Foreign"])
        self.assertEqual({"MT_Primary": "Primary", "M_RobotBody_Matte": "Primary"}, result)

    def test_map_names(self):
        self.assertEqual({"w0": "X_Game_W0.png", "w1": "X_Game_W1.png", "fields": "X_Game_Fields.png",
                          "normal": "X_Game_Normal.png"}, surface.map_names("X_Game"))

    def test_constants_meet_the_contract(self):
        self.assertGreaterEqual(surface.PACK_MARGIN * surface.CHECK_RESOLUTION, surface.MARGIN_PX)
        self.assertEqual({"world": 512, "viewmodel": 1024}, surface.MAP_RESOLUTION)
        self.assertEqual({"world": 16, "viewmodel": 32}, surface.AO_SAMPLES)
        # the unpainted point (0, 0) stays out of reach of the dilation at both resolutions
        for resolution in surface.MAP_RESOLUTION.values():
            first_island_px = (surface.RESERVED_LOW + surface.PACK_MARGIN * (1 - surface.RESERVED_LOW)) * resolution
            self.assertGreater(first_island_px - surface.DILATION_PX, 1)
        self.assertEqual(2_500_000, surface.MAX_SET_BYTES)


class PngTests(unittest.TestCase):
    def test_plain_rows_round_trip_without_colour_chunks(self):
        width, height = 3, 2
        pixels = [bytes(range(y * 12, y * 12 + 12)) for y in range(height)]
        data = surface.png_bytes(b"".join(b"\x00" + row for row in pixels), width, height)
        info = surface.png_info(data)
        self.assertEqual(["IHDR", "IDAT", "IEND"], info["chunks"])   # no gAMA, sRGB, iCCP: linear data
        self.assertEqual((3, 2, 8, 6), (info["width"], info["height"], info["bit_depth"], info["color_type"]))
        self.assertEqual((3, 2, 4, [bytearray(row) for row in pixels]), surface.png_decode(data))

    def test_decoder_undoes_every_filter(self):
        width, channels = 2, 4
        original = [bytes([10, 20, 30, 40, 50, 60, 70, 80]), bytes([15, 25, 35, 45, 200, 100, 0, 255])]
        # Sub on row 0, Paeth on row 1 (filters the encoder never writes, the reader still handles)
        sub = bytes([original[0][x] - (original[0][x - channels] if x >= channels else 0) & 0xFF for x in range(8)])

        def paeth(a, b, c):
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            return a if pa <= pb and pa <= pc else b if pb <= pc else c
        row = original[1]
        prior = original[0]
        filtered = bytes([(row[x] - paeth(row[x - channels] if x >= channels else 0, prior[x],
                                          prior[x - channels] if x >= channels else 0)) & 0xFF for x in range(8)])
        data = surface.png_bytes(b"\x01" + sub + b"\x04" + filtered, width, 2)
        self.assertEqual([bytearray(r) for r in original], surface.png_decode(data)[3])

    def test_png_is_deterministic(self):
        raw = b"\x00" + bytes(range(16))
        self.assertEqual(surface.png_bytes(raw, 4, 1), surface.png_bytes(raw, 4, 1))
        crc = struct.unpack(">I", surface.png_bytes(raw, 4, 1)[29:33])[0]
        self.assertEqual(zlib.crc32(b"IHDR" + struct.pack(">IIBBBBB", 4, 1, 8, 6, 0, 0, 0)) & 0xFFFFFFFF, crc)

    def test_island_ids_join_faces_by_shared_uv_corners(self):
        faces = [(0, 1, 2), (1, 2, 3), (4, 5, 6)]
        uvs = [((0, 0), (1, 0), (0, 1)), ((1, 0), (0, 1), (1, 1)), ((0, 0), (1, 0), (0, 1))]
        self.assertEqual([0, 0, 1], surface.island_ids(faces, uvs))
        seam = [((0, 0), (1, 0), (0, 1)), ((.5, 0), (0, 1), (1, 1)), ((0, 0), (1, 0), (0, 1))]
        self.assertEqual([0, 0, 1], surface.island_ids(faces, seam))   # one shared corner keeps them together
        apart = [((0, 0), (1, 0), (0, 1)), ((.5, 0), (0, .5), (1, 1)), ((0, 0), (1, 0), (0, 1))]
        self.assertEqual([0, 1, 2], surface.island_ids(faces, apart))


@unittest.skipUnless(HAVE_NUMPY, "numpy (Blender's Python) needed for the raster helpers")
class RasterTests(unittest.TestCase):
    def test_shared_edges_never_count_as_overlap(self):
        np = surface.np
        quad = np.array([[[.1, .1], [.9, .1], [.9, .9]], [[.1, .1], [.9, .9], [.1, .9]]])
        counts = np.zeros((64, 64), dtype=np.int16)
        surface.rasterize(quad, np.array([0, 1]), 64, counts=counts)
        self.assertEqual(0, int((counts > 1).sum()))
        folded = np.concatenate([quad, quad[:1]])
        counts[:] = 0
        surface.rasterize(folded, np.array([0, 1, 2]), 64, counts=counts)
        self.assertGreater(int((counts > 1).sum()), 100)

    def test_weights_are_one_hot_and_stop_after_the_dilation(self):
        np = surface.np
        raster = np.full((64, 64), -1, dtype=np.int32)
        raster[20:30, 20:30] = surface.CHANNELS.index("Energy")
        maps, filled = surface.weight_maps(raster, 8)
        self.assertTrue(np.all(maps["W1"][25, 25] == [0, 0, 255, 0]))
        self.assertTrue(np.all(maps["W1"][12, 12] == [0, 0, 255, 0]))   # 8 px diagonal (chessboard)
        self.assertTrue(np.all(maps["W1"][11, 25] == 0))
        self.assertEqual(0, int(maps["W0"].sum()))

    def test_ties_between_islands_resolve_the_same_way(self):
        np = surface.np
        raster = np.full((16, 16), -1, dtype=np.int32)
        raster[:, 4] = 0
        raster[:, 6] = 1
        first, second = surface.dilate(raster, 3), surface.dilate(raster, 3)
        self.assertTrue(np.array_equal(first, second))
        self.assertIn(int(first[5, 5]), (0, 1))

    def test_gap_and_png_array(self):
        np = surface.np
        islands = np.full((32, 32), -1, dtype=np.int32)
        islands[5:10, 5:10] = 0
        islands[5:10, 14:20] = 1
        self.assertEqual(5.0, surface.min_gap_px(islands, 8))
        pixels = (np.arange(8 * 6 * 4) % 251).astype(np.uint8).reshape(8, 6, 4)
        self.assertTrue(np.array_equal(pixels, surface.png_array(surface.png_encode(pixels))))


class ClipAreaTests(unittest.TestCase):
    def test_overlap_area_of_triangles(self):
        a = ((0, 0), (1, 0), (0, 1))
        self.assertAlmostEqual(.5, surface.clip_area(a, a))
        self.assertAlmostEqual(.125, surface.clip_area(a, ((0, 0), (.5, 0), (0, .5))))
        self.assertEqual(0.0, surface.clip_area(a, ((2, 2), (3, 2), (2, 3))))

    def test_degenerate_triangles_overlap_nothing(self):
        a = ((0, 0), (1, 0), (0, 1))
        self.assertEqual(0.0, surface.clip_area(a, ((0, 0), (0, 0), (0, 0))))
        self.assertEqual(0.0, surface.clip_area(a, ((.1, .1), (.2, .2), (.3, .3))))
        self.assertEqual(0.0, surface.clip_area(((.1, .1), (.1, .1), (.1, .1)), a))


class StageTests(unittest.TestCase):
    def stage(self):
        return next(stage for stage in STAGES if stage.name == "surface_bake")

    def test_surface_bake_is_a_heavy_contract_four_stage_after_both_game_exports(self):
        stage = self.stage()
        names = [entry.name for entry in STAGES]
        self.assertGreater(names.index("surface_bake"), names.index("game_fps"))
        self.assertEqual(ROUNDTRIP_TIERS, stage.tiers)
        self.assertTrue(stage.heavy)
        self.assertEqual(4, stage.min_contract)
        self.assertFalse(stage.renders)   # fixed bake samples: standard and full share the result
        self.assertEqual(("qa_surface.json",), stage.qa)
        for name in ("{asset}_Game.blend", "{asset}_FPS_Game.blend", "qa_game.json", "qa_game_fps.json"):
            self.assertIn(name, stage.reads)
        self.assertIn("data/game_palette.json", stage.sources)
        self.assertIn("{asset}.blend", next(entry for entry in STAGES if entry.name == "game_fps").reads)

    def test_runs_in_standard_and_full_only_and_not_for_contract_three(self):
        tool = catalog()[0]
        self.assertEqual(4, GAME_CONTRACT)
        self.assertNotIn("surface_bake", [run.name for run in expand(tool, "quick")])
        for tier in ("standard", "full"):
            runs = [run for run in expand(tool, tier) if run.name == "surface_bake"]
            self.assertEqual(1, len(runs))
            self.assertTrue(runs[0].heavy)
            self.assertNotIn("surface_bake", [run.name for run in expand(dict(tool, game_contract="3"), tier)])

    def test_optional_fields_keep_the_old_stage_declarations(self):
        for stage in STAGES:
            entry = declaration(stage)
            if stage.name != "surface_bake":
                self.assertNotIn("heavy", entry)
                self.assertNotIn("min_contract", entry)
        self.assertTrue(declaration(self.stage())["heavy"])

    def test_manifest_says_whether_the_maps_are_in(self):
        tool = catalog()[0]
        self.assertEqual({"included": True, "qa": "qa_surface.json"},
                         surface_note("standard", expand(tool, "standard"), tool))
        self.assertIn("quick", surface_note("quick", expand(tool, "quick"), tool)["reason"])
        legacy = dict(tool, game_contract="3")
        self.assertIn("contract 3", surface_note("standard", expand(legacy, "standard"), legacy)["reason"])
        with tempfile.TemporaryDirectory() as name:
            work = Path(name)
            (work / "model.blend").write_bytes(b"x")
            with patch("generate_tools.valid_package", return_value=True):
                assemble_package(work, tool, "quick", "cpu", [], [], "key")
            self.assertFalse(json.loads((work / "manifest.json").read_text())["surface"]["included"])


if __name__ == "__main__":
    unittest.main()
