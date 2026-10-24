"""Weapon clips: boundaries, event timing, release windows and unchanged generator geometry (no Blender)."""
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
import concept_spec  # noqa: E402
import ego_clips as ego  # noqa: E402
import ego_weapon_motions as motions  # noqa: E402
import weapon_designs as designs  # noqa: E402

DATA = ego.load()
TOOLS = {t["id"]: t for t in json.loads((ROOT / "data/tools.json").read_text())["tools"] if t.get("hold")}
PROFILES = json.loads((ROOT / "data/viewmodels.json").read_text())["tools"]


def clips_for(tool):
    return ego.clip_list(DATA, TOOLS[tool], PROFILES[tool]["motion"])


def offset_size(value):
    return max((abs(v) for v in (value or {}).values()), default=0)


class WeaponMotionTests(unittest.TestCase):
    def test_all_clip_boundaries_and_loop_seams(self):
        for tool in TOOLS:
            clips, params = clips_for(tool)
            self.assertEqual(16 if tool == "fusion_rifle" else 15, len(clips))
            for clip in clips:
                with self.subTest(tool=tool, clip=clip["suffix"]):
                    first = ego.pose_at(clip, clip["frame_start"], params)
                    last = ego.pose_at(clip, clip["frame_end"], params)
                    for actual, named in ((first, clip["from"]), (last, clip["to"])):
                        self.assertLess(ego.pose_error(actual, ego.named_pose(named, params)), 1e-9)
                        self.assertFalse(actual["detached"])
                        self.assertEqual(0, offset_size(actual["support"]))
                        self.assertEqual(0, offset_size(actual["part"]))
                    if clip["loop"]:
                        self.assertLess(ego.pose_error(first, last), 1e-9)
                        # No velocity discontinuity larger than frame sampling's curvature at the seam.
                        after = ego.pose_at(clip, clip["frame_start"] + 1, params)
                        before = ego.pose_at(clip, clip["frame_end"] - 1, params)
                        for axis in ego.AXES:
                            self.assertAlmostEqual(after[axis] - first[axis], last[axis] - before[axis], delta=.06)

    def test_events_order_and_part_seats_on_mag_in(self):
        for tool in TOOLS:
            clips, params = clips_for(tool)
            for clip in clips:
                events = clip["events"]
                with self.subTest(tool=tool, clip=clip["suffix"]):
                    self.assertEqual(sorted(e["frame"] for e in events), [e["frame"] for e in events])
                    self.assertTrue(all(clip["frame_start"] <= e["frame"] <= clip["frame_end"] for e in events))
            clip = next(c for c in clips if c["motion"] == "reload")
            events = clip["events"]
            with self.subTest(tool=tool):
                self.assertEqual(["MagOut", "MagIn", "Ready"], [e["name"] for e in events])
                self.assertTrue(events[0]["frame"] < events[1]["frame"] < events[2]["frame"])
                self.assertGreater(offset_size(ego.pose_at(clip, events[0]["frame"], params)["part"]), .02)
                for event in events[1:]:
                    self.assertEqual(0, offset_size(ego.pose_at(clip, event["frame"], params)["part"]))
                # A partly withdrawn magazine/cell remains stationary between the two exchange gestures.
                if params["reload"]["style"] == "magazine":
                    a = ego.pose_at(clip, events[0]["frame"], params)["part"]
                    b = ego.pose_at(clip, (events[0]["frame"] + events[1]["frame"]) // 2, params)["part"]
                    self.assertEqual(a, b)

    def test_support_only_moves_inside_release_window(self):
        for tool in TOOLS:
            clips, params = clips_for(tool)
            for clip in clips:
                saw_release = False
                for u in range(clip["length"] + 1):
                    pose = ego.pose_at(clip, clip["frame_start"] + u, params)
                    with self.subTest(tool=tool, clip=clip["suffix"], frame=u):
                        # the pistol's cup hand stays on the grip while reloading (0.10.0: reload.support false)
                        if clip["motion"] != "reload" or not params["reload"]["support"]:
                            self.assertFalse(pose["detached"])
                            self.assertEqual(0, offset_size(pose["support"]))
                        else:
                            release, attach = params["reload"]["detached"]
                            inside = release < u / clip["length"] < attach
                            self.assertEqual(inside, pose["detached"])
                            if not inside:
                                self.assertEqual(0, offset_size(pose["support"]))
                            saw_release |= pose["detached"] and offset_size(pose["support"]) > .005
                        if clip["motion"] != "reload":
                            self.assertEqual(0, offset_size(pose["part"]))
                if clip["motion"] == "reload" and params["reload"]["support"]:
                    self.assertTrue(saw_release)

    def test_reload_timing_windows_are_ordered(self):
        for tool in TOOLS:
            _, p = clips_for(tool)
            b = p["reload"]
            out = round(b["out_at"] * p["reload_frames"]) / p["reload_frames"]
            back = round(b["in_at"] * p["reload_frames"]) / p["reload_frames"]
            with self.subTest(tool=tool):
                self.assertLess(.18, out)
                self.assertLess(out, back - .12)
                self.assertLess(back + .14, 1)
                if b["support"]:
                    release, attach = b["detached"]
                    self.assertTrue(0 <= release < out - .10 < back + .04 < attach <= 1)

    def test_reload_styles_have_distinct_part_paths(self):
        samples = {}
        for tool in TOOLS:
            _, p = clips_for(tool)
            n = p["reload_frames"]
            poses = [motions.reload(u, n, p) for u in range(n + 1)]
            self.assertTrue(all(math.isfinite(v) for pose in poses for v in pose["part"].values()))
            samples[tool] = [tuple(motions.reload(u, 100, p)["part"].values()) for u in range(101)]
        self.assertEqual(len(TOOLS), len({tuple(v) for v in samples.values()}))
        p = clips_for("shotgun")[1]
        path = [motions.reload(u, 600, p)["part"]["back"] for u in range(601)]
        peaks = [i for i in range(1, len(path) - 1) if path[i] > path[i - 1] and path[i] >= path[i + 1]]
        self.assertEqual(3, len(peaks), peaks)
        for tool, axis in (("pulse_rifle", "right"), ("fusion_rifle", "right"), ("rocket_launcher", "up")):
            self.assertGreater(max(abs(v[("right", "up", "back").index(axis)]) for v in samples[tool]), .01)

    def test_inspect_views_are_opposite_and_heavier_weapons_move_slower(self):
        for tool in TOOLS:
            p = clips_for(tool)[1]
            a = motions.inspect_a(48, 96, p)
            b = motions.inspect_b(48, 96, p)
            self.assertGreater(a["twist"], 10)
            self.assertLess(b["twist"], -8)
            self.assertGreater(ego.pose_error(a, b), 20)
            for motion in (motions.inspect_a, motions.inspect_b):
                paths = [[motion(u, 96, dict(p, weight=w))["twist"] for u in range(97)] for w in (.6, 1.6)]
                self.assertLess(max(map(abs, paths[1])), max(map(abs, paths[0])))
                speeds = [max(abs(b - a) for a, b in zip(path, path[1:])) for path in paths]
                self.assertLess(speeds[1], speeds[0])


def rounded(value):
    if isinstance(value, float):
        return round(value, 10) + 0.0
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [rounded(item) for item in value]
    return value


class RecordingKit:
    """Record primitive parameters and parents without importing bpy or approximating mesh generation."""
    def __init__(self, spec):
        self.grip_tilt = spec["grip_tilt_degrees"]
        self.glow_material = spec["element"]
        self.geometry = {}
        self.parents = {}
        self.pivots = {}
        self.sockets = {}

    @staticmethod
    def tilt(degrees):
        return degrees

    def record(self, kind, name, values, parent):
        assert name not in self.geometry, name
        self.geometry[name] = (kind, values)
        self.parents[name] = parent

    def box(self, name, center, size, mat='Primary', bevel=.006, parent=None, rot=None):
        self.record('box', name, (center, size, mat, bevel, rot), parent)

    def cyl(self, name, center, radius, length, mat='Secondary', axis='y', bevel=.002, parent=None, n=28):
        self.record('cyl', name, (center, radius, length, mat, axis, bevel, n), parent)

    def tube(self, name, center, outer, inner, length, mat='Secondary', axis='y', parent=None, n=40):
        self.record('tube', name, (center, outer, inner, length, mat, axis, n), parent)

    def slab(self, name, points, width, mat='Primary', x=0.0, bevel=.004, parent=None):
        self.record('slab', name, (points, width, mat, x, bevel), parent)

    def glow(self, name, center, size, parent=None, mat=None, rot=None):
        self.box(name, center, size, mat or self.glow_material, min(.0015, min(size) * .35), parent, rot)

    def bolts(self, name, positions, radius=.0035, axis='x', parent=None, depth=.004):
        for i, position in enumerate(positions):
            self.cyl('%s_%d' % (name, i), position, radius, depth, 'Metal', axis=axis, n=10, bevel=.0004, parent=parent)

    def pivot(self, name, location, parent=None):
        self.pivots[name] = (location, parent)
        return name

    def concept(self, file, clip_nodes):
        """Toolgen 0.18: a concept sheet's meshes as 'mesh' records (bounds and material), pivots and sockets."""
        found = concept_spec.layout(file, clip_nodes)
        for name, location in found["pivots"].items():
            self.pivot(name, location)
        for mesh in found["meshes"]:
            low, high = concept_spec.bounds(mesh["vertices"])
            self.record('mesh', mesh["name"].removeprefix("SM_PG_"), (low, high, mesh["material"] or self.glow_material),
                        mesh["node"])
        for name, position in found["kit_sockets"].items():
            self.socket(name, tuple(position))

    def socket(self, name, location):
        self.sockets[name] = location

    def geometry_digest(self):
        # Rounded to 0.1 nm: the last float digits of math.cos/sin differ by platform (fusion rifle: Linux vs macOS).
        return hashlib.sha256(json.dumps(rounded({"geometry": self.geometry, "sockets": self.sockets}),
                                         sort_keys=True).encode()).hexdigest()


# Primitive arguments and all sockets of the pre-reload designs (07df813); parentage is deliberately excluded.
# 0.12.0: digests over values rounded to 0.1 nm (platform-independent) and the z-fighting fixes.
# 0.13.0: seven weapons glow in the concept sheet's colour (element, user 17.10.2026); only the glow material name changes,
# the geometry digest with the old element is unchanged (checked when the digests were updated).
REST_GEOMETRY = {
    'pistol': '83d409a1396e5bfeb2a5d454a03945c45e5c184b71d1679aeb71b8d926f8e4d2',   # 0.27.0: concept KG01 claude-v0.15.1 without VS01 and p12 (omit_parts), Socket_SupportHand a correction
    'assault_rifle': '3c0902cc5ea557e84be6543a8d60d87d7e372eedd4456b17af41882507d7b1c5',   # 0.18.0: concept KG02 claude-v0.15 (mesh bounds incl. lever p32, Socket_Reticle)
    'pulse_rifle': 'ca5840a4ffe60abb50274efb63aa22b0e48d693615fbdf95e8fe5327d7a1d41d',   # 0.24.0: concept KG03 claude-v0.15.1
    'shotgun': 'cf77d8ee2ffe99348fb8234929c40d1e81bb96e63e7602fe4fd0f89ae81c2746',   # 0.12.0: StockAccent raised off the stock inset (z-fighting)
    'sniper_rifle': '5f741e3dfbbea47ac37bbd07f024625968ac5a1c88cf1a926b3713e62ebc725a',   # 0.11.0: open eyepiece; 0.12.0: handguard glow raised
    'smg': 'ee13ce33853098f1a2e644ad1a672fc6fe5d5782393b3fca54097c7a5274ae7b',   # 0.24.0: concept KG06 claude-v0.15.1, support at the foregrip p09 (correction)
    'fusion_rifle': 'c916097c33cf27457430636e8b6e0ac3675be2ead2e1ec5c729b118c9ad27f06',
    'trace_rifle': '69a7fd1966b6fad42c12f65c42cfe3db097e00d07d86ddc467b235f1d0ca3da1',   # 0.11.0: open eyepiece; 0.12.0: glow and stock accent raised
    'rocket_launcher': 'ba6f02a8ad6c993dee3fbe1f5ba24beae0285e562be1da1a89208f47370d8675',
    'scout_rifle': '9cbb6e3262fdca1073b31aa89f7b64ac035febffdeb5f45987d2b594e9dbe237',   # 0.24.0: new, concept KG11 claude-v0.15.1
}


class ReloadGeometryTests(unittest.TestCase):
    def test_rest_geometry_and_sockets_unchanged(self):
        for tool, spec in designs.DESIGNS.items():
            kit = RecordingKit(spec)
            spec["build"](kit)
            with self.subTest(tool=tool):
                self.assertEqual(REST_GEOMETRY[tool], kit.geometry_digest())
                self.assertEqual((0, 0, 0), kit.sockets["Socket_Hand"])
                # 0.18: the open window's centre; 0.27: not for a concept weapon whose sheet sight is omitted (KG01)
                concept = {"Socket_Reticle"} if spec.get("concept") and tool != "pistol" else set()
                self.assertEqual({"Socket_Hand", "Socket_SupportHand", "Socket_Muzzle", "Socket_CenterOfMass"} | concept,
                                 set(kit.sockets))

    def test_reload_pivot_has_visible_parts_and_keeps_use_nodes(self):
        # 0.24: pulse rifle, SMG and scout rifle from their concept sheets (energy cell p18, grip magazine p11, box magazine p11);
        # 0.27: the pistol from KG01 (magazine base p01)
        expected = {"pistol": "Magazin_p01", "assault_rifle": "Magazin_p07", "pulse_rifle": "Energiezelle_p18",
                    "shotgun": "ForeEnd", "sniper_rifle": "MagBox", "smg": "Magazin_p11",
                    "fusion_rifle": "PowerCellCore", "trace_rifle": "Magazine", "rocket_launcher": "Hatch",
                    "scout_rifle": "Magazin_p11"}
        for tool, spec in designs.DESIGNS.items():
            kit = RecordingKit(spec)
            spec["build"](kit)
            with self.subTest(tool=tool):
                part = clips_for(tool)[1]["reload"]["part"]
                self.assertIn(part, kit.pivots)
                node = expected[tool]
                while node != part:
                    node = kit.parents.get(node, kit.pivots.get(node, (None, None))[1])
                    self.assertIsNotNone(node)
                self.assertTrue(all(move["node"] in kit.pivots for move in spec["use_clip"]))


if __name__ == '__main__':
    unittest.main()
