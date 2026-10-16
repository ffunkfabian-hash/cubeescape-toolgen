"""Deterministic eased motion; usable by authors and pure Python regression tests."""
import math
from itertools import pairwise


def smooth(value):
    value = min(1.0, max(0.0, value))
    return value * value * value * (value * (value * 6 - 15) + 10)


def envelope(frame, keys):
    if frame <= keys[0][0]:
        return keys[0][1]
    for (a, start), (b, end) in pairwise(keys):
        if frame <= b:
            return start + (end - start) * smooth((frame - a) / (b - a))
    return keys[-1][1]


def settle(frame, start, duration, amplitude):
    t = (frame - start) / duration
    if not 0 < t < 1:
        return 0.0
    return amplitude * math.sin(3 * math.pi * t) * (1 - smooth(t)) * smooth(min(1, t * 5))


def recoil_impulse(frame, fire_frame, recovery_frames):
    """Weapon recoil impulse 0..1: rises within three frames to 1 at ``fire_frame`` + 2 and decays smoothly to 0 at
    ``fire_frame`` + ``recovery_frames``; exactly 0 before the shot and after the recovery."""
    return envelope(frame, ((fire_frame - 1, 0), (fire_frame + 2, 1), (fire_frame + recovery_frames, 0)))


def draw_value(frame):
    return max(0, min(1, envelope(frame, ((1, 0), (31, 1), (43, 1), (48, 0), (97, 0))) + settle(frame, 48, 14, .035)))


def draw_hand_offset(frame):
    """Release, reach down for a fresh arrow, then return to the nock."""
    return tuple(envelope(frame, keys) for keys in (
        ((1, 0), (43, 0), (50, -.07), (60, -.18), (72, -.04), (79, 0), (97, 0)),
        ((1, 0), (43, 0), (50, .08), (60, .04), (72, -.10), (79, 0), (97, 0)),
        ((1, 0), (43, 0), (50, -.03), (60, -.22), (72, -.09), (79, 0), (97, 0))
    ))


def solve_elbow(shoulder, wrist, upper, lower, pole):
    """Two rigid links with an explicit elbow plane; no stretching or iterative IK."""
    delta = tuple(b - a for a, b in zip(shoulder, wrist))
    distance = math.sqrt(sum(value * value for value in delta))
    if not abs(upper - lower) + 1e-7 < distance < upper + lower - 1e-7:
        raise ValueError("Hand target lies outside the rigid arm reach")
    direction = tuple(value / distance for value in delta)
    projection = sum(a * b for a, b in zip(pole, direction))
    bend = tuple(a - projection * b for a, b in zip(pole, direction))
    length = math.sqrt(sum(value * value for value in bend))
    if length < 1e-7:
        raise ValueError("Elbow pole must not align with the arm")
    along = (upper * upper - lower * lower + distance * distance) / (2 * distance)
    height = math.sqrt(max(0, upper * upper - along * along))
    return tuple(shoulder[i] + direction[i] * along + bend[i] / length * height for i in range(3))
