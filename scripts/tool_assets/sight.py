"""Line of sight of the nine weapons: Socket_Sight / Socket_Eye (Cube Escape 0.66 "Deadeye", Toolgen T1).

Pure Python (no bpy, no data files: the authoring copy has no data/ folder), used by weapon_kit.py (places the sockets in
the world model) and the tests. ``DESIGNS[key]['sight']`` (weapon_designs.py) holds the rule in world-model metres:

* ``kind``: iron, reflex, holo, scope or energy (contract ``hold.sight_kind``, mirrored in data/tools.json);
* ``parts``: the sight meshes (names without SM_PG_), the same as ``ads.sight_parts`` / the ``ads.sight_markers`` match of
  data/ego_clips.json, so the line is the AimIdle line of sight;
* ``mode``: "top" (iron: ``above_m`` over the top of the parts) or "center" (optics: through their centre);
* ``above_m`` / ``eye_back_m``: the first-person values (``ads.eye_above_m``, ``hold.eye_distance_m``) divided by the
  weapon's ``tool_scale`` (data/viewmodels.json): the first-person model is the world model scaled by ``tool_scale``,
  so both models carry the very same line and the first-person eye distance comes out in camera metres.

Socket_Sight sits on that line at the rear end of the sight (rear notch, rear face of the optic, eyepiece of a scope),
rotation identity: Unity +Z (Blender -Y) looks along the bore, Unity +Y (Blender +Z) is up. Scopes add Socket_Eye on the
same line ``eye_back_m`` behind Socket_Sight. tests/test_weapons.py keeps the rule equal to the data;
toolgen/first_person.py checks the socket against the AimIdle pose (``ego_clips.sight_socket`` in qa_viewmodel.json).
"""
SIGHT_KINDS = ("iron", "reflex", "holo", "scope", "energy")
# Meshes (without SM_PG_) whose rear end counts as the rear of the sight besides the parts (the eyepiece of a scope
# reaches past the tube).
REAR_PARTS = {"scope": ("ScopeEyepiece",)}


def line(bounds, rule):
    """Socket positions: ``bounds`` maps mesh names (SM_PG_ prefix optional) to (low, high) corners in the weapon root's
    space. Returns {"sight": (x, y, z), "eye": (x, y, z) | None, "parts": [...]}."""
    assert rule["kind"] in SIGHT_KINDS, rule
    assert rule["mode"] in ("top", "center"), rule
    parts = sorted(name for name in bounds if name.removeprefix("SM_PG_") in rule["parts"])
    assert len(parts) == len(rule["parts"]), ("sight parts not found", rule["parts"], parts)
    low = [min(bounds[name][0][axis] for name in parts) for axis in range(3)]
    high = [max(bounds[name][1][axis] for name in parts) for axis in range(3)]
    rear = max([high[1], *(corners[1][1] for name, corners in bounds.items()
                           if name.removeprefix("SM_PG_") in REAR_PARTS.get(rule["kind"], ()))])
    x = (low[0] + high[0]) / 2
    z = high[2] + rule["above_m"] if rule["mode"] == "top" else (low[2] + high[2]) / 2
    eye = (x, rear + rule["eye_back_m"], z) if rule["kind"] == "scope" else None
    return {"sight": (x, rear, z), "eye": eye, "parts": parts}
