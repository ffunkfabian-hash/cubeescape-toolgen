"""Golden of the weapons' surface maps (tests/golden/surface): sha256 per map (Toolgen 0.13), confirmed alternates (0.15.1-0.20,
legacy) and a fingerprint per map with a tolerance (0.21 Livery, toolgen/map_fingerprint.py). scripts/verify_surface.py
uses it after its Blender checks; pure Python (the decoder is passed in), so the unit tests run without Blender."""
import hashlib
import json
from pathlib import Path

import map_fingerprint
import surface

ROOT = Path(__file__).resolve().parents[1]
# Golden maps of the weapons (Toolgen 0.13): sha256 of every map in manifest.json, no reference images (user, 17.10.2026).
# 0.21 (Livery, user 21.10.2026 "Mittelweg"): plus a fingerprint per map (fingerprints/<tool>.json, toolgen/map_fingerprint.py);
# a map is byte-identical (green), within manifest["tolerance"] of its fingerprint (green with a note) or failed (red, with
# map, channel and block). The confirmed alternates of 0.15.1-0.20 still count as identical until they are retired.
GOLDEN = ROOT / "tests/golden/surface"
FINGERPRINTS = "fingerprints"
# Richtwert of the user (21.10.2026) until the measured bake noise sets the final values (manifest["tolerance"] wins)
DEFAULT_TOLERANCE = {"share": .005, "levels": 1, "block_levels": 1}
GOLDEN_NOTE = ("Golden surface maps of the weapons (Toolgen 0.13 Enamel; the robot variants' <Asset>_Robot_Game_* maps since "
               "0.14 Fieldfit; baked on the Mac, full tier since 0.22): sha256 of every map plus a fingerprint per map "
               "(fingerprints/<tool>.json, 0.21 Livery), no reference images. Rewrite with verify_surface.py --update-golden "
               "after a deliberate change: only maps that are not green get a new hash and fingerprint.")
FINGERPRINT_NOTE = ("0.21 Livery (user 21.10.2026, 'Mittelweg'): a map that is not byte-identical passes with a note when "
                    "its fingerprint (64 x 64 block means and 256-level histogram per channel, toolgen/map_fingerprint.py) "
                    "stays within 'tolerance': in every channel at most 'share' of the texels changed, by at most 'levels' "
                    "on average, and no block mean moved more than 'block_levels'; else it fails with map, channel and block. "
                    "The values come from measured bake noise (docs/versions/0.21.md); the alternates of 0.15.1-0.20 stay "
                    "until a map is rewritten, no new ones are written.")


def golden_stale(manifest, tool, name):
    """Is the golden hash of the map marked stale (``manifest["stale"]["maps"]``: known to be outdated, e.g. Toolgen 0.16 first-person
    maps at 2048 until the Mac bake confirms them)? A stale map fails until ``--update-golden`` rewrites it."""
    return name in manifest.get("stale", {}).get("maps", {}).get(tool, [])


def golden_accepts(manifest, tool, name, digest):
    """Is ``digest`` a golden hash of the map: the primary one or a confirmed alternate (``manifest["alternates"]``)?"""
    return digest == manifest["maps"].get(tool, {}).get(name) or digest in manifest.get("alternates", {}).get(tool, {}).get(name, [])


def png_pixels(data):
    """(width, height, RGBA bytes top to bottom) of a map: numpy when there is numpy (Blender), else pure Python (tests)."""
    if surface.np is not None:
        pixels = surface.png_array(data)
        return pixels.shape[1], pixels.shape[0], pixels.tobytes()
    width, height, _, rows = surface.png_decode(data)
    return width, height, b"".join(bytes(row) for row in rows)


def load_fingerprints(tool, folder=GOLDEN):
    path = folder / FINGERPRINTS / f"{tool}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def write_fingerprints(tool, entries, folder=GOLDEN):
    path = folder / FINGERPRINTS / f"{tool}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(entries.items())), indent=1, sort_keys=True) + "\n")


def model_of(name):
    return name.rsplit("_", 1)[0]


def golden_verdict(manifest, tool, name, digest, data, fingerprints, decode=png_pixels):
    """("exact" | "alternate" | "tolerated" | "failed" | "stale", text) of one map against the golden: sha256 first, then
    the confirmed alternates (legacy, 0.15.1-0.20), then the fingerprint within manifest["tolerance"]."""
    if golden_stale(manifest, tool, name):
        return "stale", (f"{tool}/{name}: golden is stale ({manifest['stale'].get('note', 'rebake pending')}); confirm the "
                         "new bake with --update-golden")
    if digest == manifest["maps"].get(tool, {}).get(name):
        return "exact", f"{tool}/{name}"
    if digest in manifest.get("alternates", {}).get(tool, {}).get(name, []):
        return "alternate", f"{tool}/{name}: confirmed alternate (legacy, covered by the fingerprint tolerance)"
    reference = fingerprints.get(name)
    if reference is None:
        return "failed", f"{tool}/{name}: sha256 differs from the golden and there is no fingerprint (--update-golden)"
    current = map_fingerprint.fingerprint(*decode(data), digest)
    model = {map_fingerprint.map_kind(other): entry for other, entry in fingerprints.items()
             if model_of(other) == model_of(name)}
    within, text = map_fingerprint.judge(f"{tool}/{name}", map_fingerprint.compare(reference, current),
                                         manifest["tolerance"], model, current)
    return ("tolerated" if within else "failed"), text


def golden_update(manifest, tool, digests):
    """New golden hashes of one tool from ``digests`` {map: sha256} (0.21: golden_check passes only the maps whose verdict
    was not green - identical, alternate or within the tolerance keep their reference, so a noisy bake never moves it back
    and forth). A map with new content drops its alternates; alternates are no longer written (the tolerance replaces
    them); a rewritten map leaves the stale mark."""
    maps = manifest["maps"].setdefault(tool, {})
    alternates = manifest.setdefault("alternates", {})
    for name, digest in digests.items():
        if maps.get(name) != digest and digest not in alternates.get(tool, {}).get(name, []):
            maps[name] = digest
            alternates.get(tool, {}).pop(name, None)
    if not alternates.get(tool):
        alternates.pop(tool, None)
    if not alternates:
        manifest.pop("alternates", None)
    stale = manifest.get("stale", {}).get("maps", {})
    if tool in stale:
        remaining = [name for name in stale[tool] if name not in digests]
        if remaining:
            stale[tool] = remaining
        else:
            stale.pop(tool)
        if not stale:
            manifest.pop("stale", None)


def golden_check(output, tools, update=False, folder=GOLDEN, decode=png_pixels):
    """Compare (or with ``update`` rewrite) the weapons' maps against the golden in ``folder``: sha256, legacy alternates,
    then the fingerprint tolerance (0.21). ``update`` rewrites hash and fingerprint of every map that is not green and adds
    a missing fingerprint of an identical map."""
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"maps": {}}
    manifest.setdefault("tolerance", dict(DEFAULT_TOLERANCE))
    errors, compared, alternate, tolerated, updated = [], 0, [], [], []
    for tool in tools:
        files = sorted((output / tool).glob("*_Game_*.png"))
        if not files:
            continue
        if tool not in manifest["maps"] and not update:
            errors.append(f"{tool}: no golden maps")
            continue
        fingerprints = load_fingerprints(tool, folder)
        changed, digests = False, {}
        for path in files:
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            verdict, text = golden_verdict(manifest, tool, path.name, digest, data, fingerprints, decode)
            compared += 1
            if update:
                exact_without = verdict == "exact" and fingerprints.get(path.name, {}).get("sha256") != digest
                if verdict in ("failed", "stale") or exact_without or path.name not in fingerprints:
                    fingerprints[path.name] = map_fingerprint.fingerprint(*decode(data), digest)
                    digests[path.name] = digest
                    changed = True
                    updated.append(f"{tool}/{path.name}")
                continue
            if verdict in ("failed", "stale"):
                errors.append(text)
            elif verdict == "alternate":
                alternate.append(f"{tool}/{path.name}")
            elif verdict == "tolerated":
                tolerated.append(text)
        if update and changed:
            golden_update(manifest, tool, digests)
            write_fingerprints(tool, fingerprints, folder)
    if update:
        manifest["note"] = GOLDEN_NOTE
        manifest["fingerprint_note"] = FINGERPRINT_NOTE
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    stale = sum(len(names) for names in manifest.get("stale", {}).get("maps", {}).values())
    return {"compared": compared, "errors": errors, "alternate_matches": alternate, "tolerated": tolerated, "stale": stale,
            "updated": updated}
