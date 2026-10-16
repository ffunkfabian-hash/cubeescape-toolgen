"""Class-specific inspect and reload poses; pure Python, shared with the ego clip baker.

Part offsets use tool axes; support offsets use camera axes. Only translations of reload parts are baked by the
current framework. Every action returns to rest, including its optional part and support-hand offsets.
"""
import math

from motion_profiles import envelope


def _ego():
    import ego_clips  # circular import: ego_clips registers these functions
    return ego_clips


def wave(t, cycles=1):
    return math.sin(2 * math.pi * cycles * t)


def inspect(u, n, p, view):
    """Opposite forearm cants show the side and top; heavy weapons turn less and take longer to settle."""
    t = u / n
    weight = p["weight"]
    block = p["inspect"]
    ramp = min(.38, .20 + .10 * weight)
    amount = envelope(t, ((0, 0), (ramp, 1), (1 - ramp, 1), (1, 0)))
    result = _ego().scaled(block[view], amount / math.sqrt(weight))
    result["follow"] = block["shoulder_follow"] * amount
    # The fixed clip length has room for a slower, smaller breathing motion on heavy weapons.
    result["twist"] += block["wobble_deg"] * wave(t, 1 / weight) * amount / weight
    return result


def inspect_a(u, n, p):
    """Cant inward to read the receiver's side panels."""
    return inspect(u, n, p, "a")


def inspect_b(u, n, p):
    """Cant outward to check the top rail and muzzle assembly."""
    return inspect(u, n, p, "b")


def _offset(values, amount):
    return dict(zip(("right", "up", "back"), (value * amount for value in values)))


def _exchange(t, block):
    """Withdraw by MagOut, pause clear of the well, seat exactly at MagIn."""
    out, back = block["out_at"], block["in_at"]
    return envelope(t, ((0, 0), (out - .10, 0), (out, 1), (back - .12, 1), (back, 0), (1, 0)))


def _shell_strokes(t, block):
    """Three short loading strokes, with full returns between them; the last seats at MagIn."""
    out, back = block["out_at"], block["in_at"]
    step = (back - out) / 3
    keys = [(0, 0), (out - .10, 0), (out, 1)]
    for i in range(3):
        start = out + i * step
        keys.append((start + step * .45, 0))
        if i < 2:
            keys.append((start + step, 1))
    keys.append((1, 0))
    return envelope(t, keys)


def reload(u, n, p):
    """Magazine, cell, shell-loading or sliding-hatch reload, with a bounded support-hand release."""
    t = u / n
    block = dict(p["reload"])
    # Use the very same frame rounding as clip_list's events, including short pistol reloads.
    for key in ("out_at", "in_at"):
        block[key] = round(block[key] * n) / n
    style = block["style"]
    out, back = block["out_at"], block["in_at"]
    tilt = envelope(t, ((0, 0), (.18, 1), (back + .14, 1), (1, 0)))
    result = dict(_ego().scaled(block["pose"], tilt), follow=block["shoulder_follow"] * tilt)
    travel = _exchange(t, block)
    if style == "shells":
        travel = _shell_strokes(t, block)
    elif style == "cell":
        # The cell clears its latch sideways before it leaves the housing.
        latch = envelope(t, ((0, 0), (out - .15, 0), (out - .10, 1), (back - .06, 1), (back, 0), (1, 0)))
        result["part"] = _offset(block["latch_m"], latch)
    elif style == "hatch":
        # A sliding hatch lifts clear of the tube, then moves rearward while the tube is serviced.
        lift = envelope(t, ((0, 0), (out - .16, 0), (out - .08, 1), (back - .04, 1), (back, 0), (1, 0)))
        result["part"] = _offset(block["lift_m"], lift)
    elif style != "magazine":
        raise ValueError(f"Unknown reload style for {p['tool']}: {style}")
    shift = _offset(block["drop_m"], travel)
    result["part"] = {axis: value + (result["part"] or {}).get(axis, 0) for axis, value in shift.items()}
    if block["support"]:
        release, attach = block["detached"]
        reach = envelope(t, ((0, 0), (release, 0), (out - .10, 1), (back + .04, 1), (attach, 0), (1, 0)))
        # Return the hand before reattaching; there is no offset outside this explicit time window.
        result["detached"] = release < t < attach
        result["support"] = _offset(block["reach_m"], reach)
        # Re-grip (T5): the support fingers open as the hand lets go and close again as it grips (0 at both ends).
        open_for = p["fingers"]["regrip_ramp"]
        result["regrip"] = envelope(t, ((0, 0), (max(release - open_for, 0), 0), (release + open_for, 1),
                                        (attach - open_for, 1), (min(attach + open_for, 1), 0), (1, 0)))
        if style == "shells":
            for axis, value in _offset(block["stroke_m"], travel).items():
                result["support"][axis] += value
    return result
