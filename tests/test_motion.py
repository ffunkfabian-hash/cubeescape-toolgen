"""Contact-safe rest poses and continuous speed at authored phase boundaries."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/tool_assets"))
from motion_profiles import (
    draw_hand_offset,
    draw_value,
    envelope,
    recoil_impulse,
    settle,
    smooth,
    solve_elbow,
)


class MotionTests(unittest.TestCase):
    def test_easing_starts_and_stops_with_zero_speed(self):
        epsilon = .0001
        self.assertEqual(0, smooth(-1)); self.assertEqual(1, smooth(2))
        self.assertLess(smooth(epsilon) / epsilon, .00001)
        self.assertLess((1 - smooth(1 - epsilon)) / epsilon, .00001)
        self.assertAlmostEqual(.5, smooth(.5))

    def test_draw_holds_and_returns_without_negative_morphs(self):
        for frame in (1, 79, 97):
            self.assertEqual(0, draw_value(frame))
        for frame in range(31, 44):
            self.assertEqual(1, draw_value(frame))
        for index in range(970):
            self.assertGreaterEqual(draw_value(index / 10), 0)
            self.assertLessEqual(draw_value(index / 10), 1)
        self.assertLess(draw_value(2) - draw_value(1), draw_value(16) - draw_value(15))

    def test_draw_hand_keeps_contact_until_release_and_after_nocking(self):
        for frame in (*range(1, 44), *range(79, 98)):
            self.assertEqual((0, 0, 0), draw_hand_offset(frame))
        self.assertLess(draw_hand_offset(60)[2], -.2)

    def test_secondary_motion_has_no_start_or_end_jump(self):
        self.assertEqual(0, settle(43, 43, 22, 1))
        self.assertEqual(0, settle(65, 43, 22, 1))
        self.assertLess(abs(settle(43.001, 43, 22, 1)), .000001)
        self.assertLess(abs(settle(64.999, 43, 22, 1)), .000001)

    def test_keyed_hold_does_not_drift(self):
        keys = ((1, 0), (14, 1), (45, 1), (73, 0), (97, 0))
        self.assertEqual(1, envelope(27.5, keys))
        self.assertEqual(0, envelope(100, keys))

    def test_arm_preserves_both_link_lengths_through_hand_movement(self):
        shoulder = (-.1, -.3, -.4)
        previous = None
        for index in range(100):
            wrist = (-.18, -.72 + index * .002, -.2)
            elbow = solve_elbow(shoulder, wrist, .32, .30, (-.1, 0, -1))
            self.assertAlmostEqual(.32, math.dist(shoulder, elbow), places=8)
            self.assertAlmostEqual(.30, math.dist(elbow, wrist), places=8)
            if previous is not None:
                self.assertLess(math.dist(elbow, previous), .004)
            previous = elbow

    def test_arm_rejects_unreachable_target_and_collinear_pole(self):
        with self.assertRaises(ValueError):
            solve_elbow((0, 0, 0), (0, 0, 2), .4, .4, (1, 0, 0))
        with self.assertRaises(ValueError):
            solve_elbow((0, 0, 0), (0, 0, .5), .4, .4, (0, 0, 1))


class RecoilTests(unittest.TestCase):
    def test_recoil_is_zero_before_the_shot_and_after_the_recovery(self):
        for fire, recovery in ((14, 26), (46, 30), (14, 12)):
            with self.subTest(fire=fire, recovery=recovery):
                for frame in (1, fire - 1, fire + recovery, fire + recovery + 1, 97):
                    self.assertEqual(0, recoil_impulse(frame, fire, recovery), frame)

    def test_recoil_peaks_right_after_the_shot_and_decays(self):
        values = [recoil_impulse(frame, 14, 26) for frame in range(1, 98)]
        peak = max(range(len(values)), key=values.__getitem__) + 1
        self.assertEqual(16, peak, "the impulse peaks two frames after the shot")
        self.assertEqual(1.0, values[peak - 1])
        self.assertLessEqual(max(values), 1.0)
        self.assertGreaterEqual(min(values), 0.0, "never pulls the weapon forward")
        self.assertLess(values[14 + 26 - 2 - 1], .02, "almost back at rest shortly before the recovery ends")
        self.assertTrue(all(a >= b for a, b in zip(values[peak - 1:], values[peak:])), "monotone decay after the peak")

    def test_recoil_is_continuous(self):
        values = [recoil_impulse(frame, 14, 26) for frame in range(1, 98)]
        self.assertLess(max(abs(b - a) for a, b in zip(values, values[1:])), .75)


if __name__ == "__main__":
    unittest.main()
