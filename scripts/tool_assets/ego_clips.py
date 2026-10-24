"""Ego animation clips of the first-person models: clip list, timeline layout and the pose of every frame.

Pure Python (no bpy), shared by toolgen/first_person.py (keys the clips), toolgen/game_export.py (contract) and the
tests. data/ego_clips.json holds the clip list, lengths, loop flags, start/end poses and per-weapon parameters; the
motion of each clip is a function here (MOTIONS) that maps a clip frame to a Pose.

A Pose is measured against the rest pose (frame 1 of the Use clip), in camera axes as seen by the player:
``pitch`` muzzle up, ``yaw`` muzzle left, ``roll`` top tilts left (degrees, rotation about the grip hand), ``twist``
top tilts left by turning about the grip forearm's axis (pronation: the wrist does not bend, the cheapest cant);
``right``, ``up``, ``back`` (towards the player) in metres; ``aim`` 0..1 blends towards the aim-down-sights transform
first_person.py derives from the geometry (sight on the screen centre); ``follow`` 0..1 moves the shoulders with the
weapon (body sway, keeps wrists relaxed); ``support`` offsets the support hand (camera axes, metres) while
``detached`` releases it from Socket_SupportHand; ``part`` moves the reload part (tool axes, metres/degrees);
``trigger`` 0..1 lifts the grip hand's index finger off the trigger after the shot (``fingers.trigger_deg``) and
``regrip`` 0..1 opens the support fingers while the support hand lets go and grips again (``fingers.regrip_deg``);
``spin`` 0..1 turns the charge part once (``charge.spin``, the fusion rifle's coil in Charge).
"""
import json
import math
from pathlib import Path

from motion_profiles import envelope, recoil_impulse, settle, smooth

import ego_weapon_motions

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data/ego_clips.json"
ARMS_PATH = ROOT / "data/ego_arms.json"
AXES = ("pitch", "yaw", "roll", "twist", "right", "up", "back")
POSES = ("rest", "aim", "sprint", "lowered")
KINDS = ("weapon", "tool")


def ads_eye_distance_m(tool, arms_path=ARMS_PATH):
    """The one aim-down-sights eye distance of a tool (game metres). A device with an ``ads`` block in data/ego_arms.json
    (Toolgen 0.24 patch; user decision 23.10.2026: Cube Escape 0.112 uses these) takes it from there; every other tool keeps
    ``hold.eye_distance_m`` of data/tools.json (the Cube Escape 0.75 profile)."""
    device = json.loads(Path(arms_path).read_text())["devices"].get(tool.get("id"))
    ads = device.get("ads") if isinstance(device, dict) else None
    return ads["eye_distance_m"] if ads else tool["hold"]["eye_distance_m"]


def ads_provisional(tool, arms_path=ARMS_PATH):
    """0.27: True while a device's aim pose waits for its sight (data/ego_arms.json ``ads.provisional``, the pistol KG01
    until formgen's iron sights)."""
    device = json.loads(Path(arms_path).read_text())["devices"].get(tool.get("id"))
    return bool(isinstance(device, dict) and device.get("ads", {}).get("provisional"))


def load(path=DATA_PATH):
    return json.loads(Path(path).read_text())


def merged(base, override):
    result = dict(base)
    for key, value in override.items():
        result[key] = merged(base[key], value) if isinstance(value, dict) and isinstance(base.get(key), dict) else value
    return result


def tool_kind(tool):
    """Weapons carry a ``hold`` block in data/tools.json; every other first-person model is a tool."""
    return "weapon" if tool.get("hold") else "tool"


def class_params(data, tool_id, motion=None):
    """Defaults merged with the class entry; ``motion`` is the viewmodel recoil profile (data/viewmodels.json)."""
    params = merged(data["defaults"], data["classes"].get(tool_id, {}))
    params["tool"] = tool_id
    if motion:
        params["motion"] = motion
        # Fire starts one frame before the Use clip's shot (no charge: the fusion rifle's charge is a later clip) and covers
        # the recoil and the weapon's mechanics (pump, bolt, hatch: fire_end_frame of the class, a frame of the Use clip),
        # time-compressed to the weapon's cooldown in Cube Escape (fire_cooldown_s): the next shot restarts the clip.
        start = motion["fire_frame"] - 1
        natural = max(motion["fire_frame"] + motion["recovery_frames"], params.get("fire_end_frame", 0)) - start
        frames = min(natural, int(params["fire_cooldown_s"] * data["fps"])) if params.get("fire_cooldown_s") else natural
        params.update(fire_start=start, fire_frames=frames, fire_scale=natural / frames)
    return params


def clip_stem(tool):
    """Clip names follow the Use clip: Pistol_Use -> Pistol_<Suffix>."""
    name = tool.get("fps_clip") or tool["clip"]
    assert name.endswith("_Use"), name
    return name[:-len("_Use")]


def lookup(params, key):
    value = params
    for part in key.split("."):
        value = value[part]
    return value


def clip_list(data, tool, motion=None):
    """Resolved clips of one first-person model in timeline order: name, length, loop, poses, frames, events."""
    kind = tool_kind(tool)
    params = class_params(data, tool["id"], motion)
    start = data["timeline"]["start_frame"]
    clips = []
    for entry in data["clips"]:
        if kind not in entry["kinds"] or (entry["motion"] in ("fire", "aim_fire") and not motion):
            continue
        if "tools" in entry and tool["id"] not in entry["tools"]:
            continue                           # clip of a few weapons only (Charge: fusion rifle)
        if tool["id"] in entry.get("except_tools", ()):
            continue                           # not for these models (Inspect_B: not the bow)
        length = entry["length"] if isinstance(entry["length"], int) else lookup(params, entry["length"])
        assert length >= 2, (tool["id"], entry["suffix"], length)
        events = []
        for event in entry["events"]:
            at = event["at"] if isinstance(event["at"], (int, float)) else lookup(params, event["at"])
            events.append({"name": event["name"], "frame": start + round(at * length)})
        clips.append({"name": f"{clip_stem(tool)}_{entry['suffix']}", "suffix": entry["suffix"], "motion": entry["motion"],
                      "length": length, "frame_start": start, "frame_end": start + length,
                      "loop": entry["loop"], "from": entry["from"], "to": entry["to"],
                      "reticle_free": entry["reticle_free"], "interruptible": entry["interruptible"],
                      "support_forearm_visible": entry.get("support_forearm_visible", False), "events": events})
        start += length + 1 + data["timeline"]["gap_frames"]
    return clips, params


def timeline_end(clips):
    return clips[-1]["frame_end"] if clips else None


def clip_at(clips, frame):
    """The clip covering a timeline frame (None in the gaps and in the Use range)."""
    return next((clip for clip in clips if clip["frame_start"] <= frame <= clip["frame_end"]), None)


# ------------------------------------------------------------------------------------------------- poses
def pose(**values):
    result = {axis: 0.0 for axis in AXES}
    result.update(aim=0.0, follow=0.0, support=None, detached=False, part=None, trigger=0.0, regrip=0.0, spin=0.0)
    result.update(values)
    return result


def scaled(values, factor):
    """Axis values of a parameter block (``pitch_deg``, ``up_m`` ...) as a pose scaled by ``factor``."""
    result = pose()
    for axis in AXES:
        for suffix in ("_deg", "_m"):
            if axis + suffix in values:
                result[axis] = values[axis + suffix] * factor
    return result


def added(*poses):
    result = pose()
    for item in poses:
        for axis in AXES:
            result[axis] += item[axis]
        for key in ("aim", "trigger", "regrip", "spin"):
            result[key] = max(result[key], item[key])
        result["follow"] = max(result["follow"], item["follow"])
        for key in ("support", "part"):
            if item[key] is not None:
                result[key] = item[key]
        result["detached"] = result["detached"] or item["detached"]
    return result


def wave(t, cycles=1):
    return math.sin(2 * math.pi * cycles * t)


def bump(t, cycles=1):
    """0 at t = 0 and every full cycle, 1 halfway."""
    return (1 - math.cos(2 * math.pi * cycles * t)) / 2


def idle(u, n, p):
    t = u / n
    block = p["idle"]
    return pose(up=block["up_m"] * wave(t), pitch=block["pitch_deg"] * bump(t), roll=block["roll_deg"] * wave(t, 1) * .5)


def walk(u, n, p):
    t = u / n
    block = p["walk"]
    scale = math.sqrt(p["weight"])
    # two steps per loop: a symmetric figure eight (sway once, bob twice), zero at the loop seam
    return pose(up=block["up_m"] * scale * wave(t, 2), right=block["right_m"] * scale * wave(t),
                twist=block["twist_deg"] * scale * wave(t), pitch=block["pitch_deg"] * scale * wave(t, 2))


def sprint_pose(p, factor):
    return dict(scaled(p["sprint"], factor), follow=p["sprint"]["shoulder_follow"] * factor)


def sprint_in(u, n, p):
    return sprint_pose(p, smooth(u / n))


def sprint(u, n, p):
    t = u / n
    block = p["sprint"]
    bob = pose(up=-block["bob_up_m"] * bump(t, 2), right=block["bob_right_m"] * wave(t), twist=block["bob_twist_deg"] * wave(t))
    return added(sprint_pose(p, 1), bob)


def sprint_out(u, n, p):
    return sprint_pose(p, 1 - smooth(u / n))


def recoil(u, p, scale=1.0):
    """The Use clip's recoil (viewmodel profile ``motion``) from one frame before its shot, time-compressed by fire_scale."""
    motion = p["motion"]
    frame = p["fire_start"] + u * p["fire_scale"]
    impulse = recoil_impulse(frame, motion["fire_frame"], motion["recovery_frames"]) * scale
    return pose(pitch=motion["pitch_degrees"] * impulse, roll=motion.get("yaw_degrees", 0) * impulse,
                back=motion["kick_m"] * impulse, up=.004 * impulse)


def trigger(u, n, p):
    """Index finger of the grip hand: rests on the trigger at the shot (clip start), lifts to reset and settles again."""
    block = p["fingers"]
    lifted = min(block["trigger_lift_frames"], n / 3)
    return envelope(u, ((0, 0), (lifted, 1), (min(lifted + block["trigger_return_frames"], n * .8), 0), (n, 0)))


def fire(u, n, p):
    return dict(recoil(u, p), trigger=trigger(u, n, p))


def aim_follow(p, amount):
    return p["ads"]["shoulder_follow"] * amount


def aim_in(u, n, p):
    t = u / n
    amount = smooth(t)
    return pose(aim=amount, follow=aim_follow(p, amount), up=-.004 * math.sin(math.pi * t))


def aim_idle(u, n, p):
    breath = idle(u, n, p)
    return dict(breath, **{axis: breath[axis] * p["ads"]["breath_scale"] for axis in AXES}, aim=1.0, follow=aim_follow(p, 1))


def aim_fire(u, n, p):
    return dict(recoil(u, p, p["ads"]["recoil_scale"]), aim=1.0, follow=aim_follow(p, 1), trigger=trigger(u, n, p))


def charge(u, n, p):
    """Charging state of a charge weapon (fusion rifle, loop): a fine tremor of whole cycles and one turn of the charge
    part per loop; rest pose at both ends, so Charge loops seamlessly and cuts into Fire."""
    t = u / n
    block = p["charge"]
    cycles = block["tremor_cycles"]
    return pose(pitch=block["tremor_deg"] * wave(t, cycles), yaw=block["tremor_deg"] * .6 * wave(t, cycles + 1),
                back=block["back_m"] * bump(t, cycles), spin=t)


def aim_out(u, n, p):
    """ADS out; a scope (``ads.lens_lead_frames``, 0.24) holds the aim while the lens picture goes first (ScopeOff), the
    model follows (Dead Man's Tale: lens 2, model 8 frames at 60/s)."""
    lead = p["ads"].get("lens_lead_frames", 0)
    t = max(0.0, u - lead) / (n - lead)
    amount = 1 - smooth(t)
    return pose(aim=amount, follow=aim_follow(p, amount), up=-.003 * math.sin(math.pi * t))


# 0.24 (Salvo): fire clips of a device's fire pattern (data/ego_arms.json devices.<tool>.fire, toolgen/ego_arms.fire_clips).
def kick(t, rise, recovery):
    """One shot's model impulse 0..1, ``t`` frames after the shot: up in ``rise`` frames, back to 0 at ``recovery``."""
    return envelope(t, ((0, 0), (rise, 1), (recovery, 0))) if 0 <= t <= recovery else 0.0


def shot_pose(p, amount, scale=1.0):
    """The Use clip's recoil direction (viewmodel profile ``motion``) at ``amount`` of one shot."""
    motion = p["motion"]
    return pose(pitch=motion["pitch_degrees"] * amount * scale, roll=motion.get("yaw_degrees", 0) * amount * scale,
                back=motion["kick_m"] * amount * scale, up=.004 * amount * scale)


def auto_fire(u, n, p, scale=1.0):
    """Held fire (loop): every cycle one real shot whose kick returns before the next (a steady rhythm, no drift and no
    reset of the whole pose per shot), plus one slow sway over the loop; rest pose at both ends."""
    pattern = p["fire_pattern"]
    cycle = pattern["cycle_frames"]
    amount = kick(u % cycle if u < n else 0, 1, cycle) * pattern["kick_share"]
    result = shot_pose(p, amount, scale)
    sway = math.sin(2 * math.pi * u / n) * pattern["sway_deg"] * scale
    result.update(yaw=result["yaw"] + sway, roll=result["roll"] - sway * .5)
    return result


def aim_auto_fire(u, n, p):
    return dict(auto_fire(u, n, p, p["ads"]["recoil_scale"]), aim=1.0, follow=aim_follow(p, 1))


def burst_amount(u, pattern):
    """The burst's model impulse: each shot flicks (back before the next), the series builds without a return between
    the shots and settles at ``still_frame`` (Gridskipper: no return inside the burst, back after about 0.35 s)."""
    shots = [index * pattern["spacing_frames"] for index in range(pattern["count"])]
    build = sum(kick(u - shot, 1, pattern["still_frame"] - shot) for shot in shots) / pattern["count"]
    flick = sum(kick(u - shot, 1, pattern["spacing_frames"]) for shot in shots)
    return pattern["build_share"] * build + pattern["flick_share"] * flick


def burst(u, n, p, scale=1.0):
    pattern = p["fire_pattern"]
    amount = burst_amount(u, pattern)
    result = shot_pose(p, amount, scale)
    # the burst drifts right and settles back (Gridskipper: +5.1 % right after the third shot)
    result["yaw"] -= pattern["drift_yaw_deg"] * scale * burst_amount(u, dict(pattern, flick_share=0, build_share=1))
    last = pattern["spacing_frames"] * (pattern["count"] - 1)
    return dict(result, trigger=trigger(max(0, u - last), n - last, p) if u >= last else 0.0)


def aim_burst(u, n, p):
    return dict(burst(u, n, p, p["ads"]["recoil_scale"]), aim=1.0, follow=aim_follow(p, 1))


def slide_locked(u, n, p):
    """0.27: the state SlideLocked (toolgen/ego_arms.slide_lock_clips) - the rest pose; the clip carries the slide held back,
    Cube Escape reads only that node from it."""
    return pose()


def lowered_pose(p, factor):
    return dict(scaled(p["lowered"], factor), follow=p["lowered"]["shoulder_follow"] * factor)


def draw(u, n, p):
    t = u / n
    result = lowered_pose(p, 1 - smooth(min(1, t / .8)))
    result["pitch"] += 1.2 * settle(u, .8 * n, .2 * n + 1e-9, 1)
    return result


def holster(u, n, p):
    return lowered_pose(p, smooth(u / n))


MOTIONS = {"idle": idle, "walk": walk, "sprint_in": sprint_in, "sprint": sprint, "sprint_out": sprint_out,
           "fire": fire, "aim_in": aim_in, "aim_idle": aim_idle, "aim_fire": aim_fire, "aim_out": aim_out,
           "draw": draw, "holster": holster, "charge": charge, "inspect_a": ego_weapon_motions.inspect_a,
           "inspect_b": ego_weapon_motions.inspect_b, "reload": ego_weapon_motions.reload,
           "auto_fire": auto_fire, "aim_auto_fire": aim_auto_fire, "burst": burst, "aim_burst": aim_burst,
           "slide_locked": slide_locked}


def pose_at(clip, frame, params):
    """Pose of a timeline frame inside ``clip``."""
    u = frame - clip["frame_start"]
    assert 0 <= u <= clip["length"], (clip["name"], frame)
    return MOTIONS[clip["motion"]](u, clip["length"], params)


def named_pose(name, params):
    """Reference pose of a clip boundary (``from`` / ``to``)."""
    return {"rest": pose(), "aim": pose(aim=1.0, follow=aim_follow(params, 1)), "sprint": sprint_pose(params, 1),
            "lowered": lowered_pose(params, 1)}[name]


def pose_error(a, b):
    """Largest difference of two poses (degrees and millimetres on one scale, plus aim/follow)."""
    values = [abs(a[axis] - b[axis]) for axis in ("pitch", "yaw", "roll", "twist")]
    values += [abs(a[axis] - b[axis]) * 1000 for axis in ("right", "up", "back")]
    values += [abs(a[key] - b[key]) for key in ("aim", "follow", "trigger", "regrip")]
    return max(values)


def transitions(clips):
    """Cut rules: a clip may follow another when its start pose is the other's end pose (no crossfade needed).
    Loops may also be left at any frame with a short crossfade into a clip that starts in the same pose."""
    rules = []
    for clip in clips:
        follows = [other["name"] for other in clips if other["from"] == clip["to"]]
        rules.append({"clip": clip["name"], "from_pose": clip["from"], "to_pose": clip["to"], "next": follows,
                      "exit": "any frame, crossfade" if clip["loop"] else
                              ("at the end; interruptible with a crossfade" if clip["interruptible"] else "at the end only")})
    return rules
