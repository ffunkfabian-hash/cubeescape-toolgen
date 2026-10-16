"""Weapon clips: boundaries, event timing, release windows and unchanged generator geometry (no Blender)."""
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
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

    def socket(self, name, location):
        self.sockets[name] = location

    def geometry_digest(self):
        return hashlib.sha256(json.dumps({"geometry": self.geometry, "sockets": self.sockets}, sort_keys=True).encode()).hexdigest()


# Primitive arguments and all sockets of the pre-reload designs (07df813); parentage is deliberately excluded.
REST_GEOMETRY = {
    'pistol': '3d6700ab484a77df860db78604abacc3837edc67c8d76a7264e138af8271e66a',   # 0.10.0: Socket_SupportHand at the grip
    'assault_rifle': '089c206226a86b2a7c9aa05e44d7609ad8c915ba7909c7e149b6a48e804df3e5',
    'pulse_rifle': 'bbddbf7b6ff9c3646ff3bfdcdb08bca5ba8c6866ce03f68f57a67c81b60be079',
    'shotgun': '2491986a481529dd79eb91c86b8486f841fb596d27d6d6685b5cf59aeb92b1ef',
    'sniper_rifle': '4fcf4ae9d41b9ea7be90bb150d83227a7fcfa6c7b8db31dacb7678ef7547e884',
    'smg': 'e6da85fa3089a499b3a23df8e4fad454ee922c7841a4ba5c84fc13419193ee73',
    'fusion_rifle': '3bfd949adbf11990c5bdceb79c370c0b62c71ba42053f28e4bdd9b0f06b30a5d',
    'scout_rifle': '4dac3eaf8b41641cf08ef91fc9fbbad07bf37cf5b03504467256551c393dd16b',
    'rocket_launcher': 'abdb6a660623d638e24692b9bbc625d015ac87a4e1d79b5d4cb7e762e49db48e',
}


class ReloadGeometryTests(unittest.TestCase):
    def test_rest_geometry_and_sockets_unchanged(self):
        for tool, spec in designs.DESIGNS.items():
            kit = RecordingKit(spec)
            spec["build"](kit)
            with self.subTest(tool=tool):
                self.assertEqual(REST_GEOMETRY[tool], kit.geometry_digest())
                self.assertEqual((0, 0, 0), kit.sockets["Socket_Hand"])
                self.assertEqual({"Socket_Hand", "Socket_SupportHand", "Socket_Muzzle", "Socket_CenterOfMass"}, set(kit.sockets))

    def test_reload_pivot_has_visible_parts_and_keeps_use_nodes(self):
        expected = {"pistol": "MagBaseplate", "assault_rifle": "Magazine", "pulse_rifle": "EnergyCell",
                    "shotgun": "ForeEnd", "sniper_rifle": "MagBox", "smg": "Drum",
                    "fusion_rifle": "PowerCellCore", "scout_rifle": "Magazine", "rocket_launcher": "Hatch"}
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
