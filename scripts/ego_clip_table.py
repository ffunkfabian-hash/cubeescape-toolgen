#!/usr/bin/env python3
"""Generate the Cube Escape first-person clip reference as Markdown and JSON."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
sys.path.insert(0, str(ROOT / "toolgen"))

import ego_clips
import ego_arms


WEAPON_ORDER = ("pistol", "smg", "assault_rifle", "trace_rifle", "pulse_rifle",
                "shotgun", "fusion_rifle", "sniper_rifle", "rocket_launcher")
TOOL_ORDER = ("portal_emitter", "magnet_gripper", "flashlight", "bow")


def load_data():
    return tuple(json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))
                 for name in ("ego_clips.json", "tools.json", "viewmodels.json"))


def resolved():
    data, catalog, viewmodels = load_data()
    by_id = {tool["id"]: tool for tool in catalog["tools"]}
    result = {}
    for tool_id in (*WEAPON_ORDER, *TOOL_ORDER):
        tool = by_id[tool_id]
        profile = viewmodels.get("tools", {}).get(tool_id, {})
        motion = profile.get("motion")
        if int(tool.get("game_contract", 4)) >= ego_arms.CONTRACT_FORMAT:
            # contract 5 (0.19): the device's own Reload, the appended ReloadEmpty, event channels (data/ego_arms.json)
            clips, _ = ego_arms.clip_list_v5(tool, profile, ego_arms.load()["devices"][tool_id])
        else:
            clips, _ = ego_clips.clip_list(data, tool, motion)
        # Use clip event (timeline marker): the weapons' Fire on the shot, the ego tools' use_event (0.15.0); None where the
        # markers come from the model's own animation script (the bow: Idle_Loaded, Drawn, Release, ...), see its contract
        use = ({"name": "Fire", "frame": motion["fire_frame"]} if motion else profile.get("use_event"))
        result[tool_id] = {"tool": tool, "clips": clips, "transitions": ego_clips.transitions(clips),
                           "use_events": [use] if use else None}
    return data, result


def seconds(frames, fps):
    return f"{frames / fps:.2f}"


def json_data(data, result):
    return {
        "fps": data["fps"],
        "tools": {
            tool_id: {
                "clips": [{
                    "name": c["name"], "suffix": c["suffix"], "length": c["length"],
                    "frames": [c["frame_start"], c["frame_end"]],
                    "seconds": c["length"] / data["fps"], "loop": c["loop"],
                    "from": c["from"], "to": c["to"], "reticle_free": c["reticle_free"],
                    "interruptible": c["interruptible"],
                    "events": [{"name": e["name"], "frame": e["frame"] - c["frame_start"],
                                **({"channel": e["channel"]} if "channel" in e else {})} for e in c["events"]],
                } for c in item["clips"]],
                "transitions": item["transitions"],
                "use_events": None if item["use_events"] is None else
                              [{"name": e["name"], "frame": e["frame"] - 1} for e in item["use_events"]],
            } for tool_id, item in result.items()
        },
    }


def render_markdown(data, result):
    fps = data["fps"]
    lines = [
        "# Ego-Clips für Cube Escape", "",
        "Diese Tabelle ist die Referenz für Cube Escapes Ego-Zustandslogik. Quelle sind `data/ego_clips.json`,",
        "`data/tools.json` und `data/viewmodels.json`; Clipauflösung und Übergänge stammen aus",
        "`scripts/tool_assets/ego_clips.py`. Der Einzelclip liegt in `<Asset>_FPS_Game.fbx` als `<Name>_Use`;",
        "die Ego-Clips liegen in `<Asset>_FPS_Game_Clips.fbx` in einem Take `<Name>_EgoClips`, abgegrenzt über Frames.",
        f"Die Abtastrate beträgt {fps} fps. `length` zählt Frame-Intervalle, also hat ein Clip `length + 1` Samples.",
        "Bei Loop-Clips ist das letzte Sample identisch mit dem ersten.", "",
        "## Posen und Übergänge", "",
    ]
    pose_text = {
        "rest": "Hüftpose, identisch mit Frame 1 des Use-Clips",
        "aim": "Visierpose: Visierlinie auf Bildschirmmitte, Lauf parallel zur Blickrichtung",
        "sprint": "abgesenkte, nach innen geneigte Waffe; Hände bleiben im Bild",
        "lowered": "Anfang von Draw / Ende von Holster: abgesenkt und geneigt, weiterhin im Bild",
    }
    for name in data["poses"]:
        lines.append(f"- **{name}**: {pose_text[name]}")
    lines += ["", "Übergänge sind Schnitte ohne Überblendung, wenn `to` des vorherigen Clips dem `from` des nächsten entspricht.",
              "Loops dürfen an jedem Frame mit kurzer Überblendung verlassen werden. Bei `interruptible: false` ist ein Clip nur am Ende verlassbar.",
              "Events sind relativ zum Clipstart angegeben.",
              "In den Ziel-Clips (AimIn, AimIdle, AimFire, AimOut) darf der Unterarm der Stützhand sichtbar sein "
              "(`support_forearm_visible`, Entscheidung des Nutzers 16.10.2026); sonst bleiben die Ellbogenhälften der Unterarme außerhalb des Bildes.",
              "Vertrag 5 (0.19, Sturmgewehr und Portalkanone, `data/ego_arms.json`): alle Clips, der Use-Clip zuerst, liegen in "
              "`<Asset>_FPS_Game_Clips.fbx` und bewegen die gemeinsame Armkette; das Sturmgewehr hat eigene `Reload`/`ReloadEmpty` "
              "(Start/End und die Rig-Ereignisse `HandOff`/`HandOn`, Kanal „rig“, markiert mit ⟂). Einbau: docs/UNITY_EINBAU.md › Vertrag 5.", ""]
    lines += ["## Clips je Klasse", "", "Längen sind Frame-Intervalle; `—` bedeutet, dass die Klasse den Clip nicht besitzt.", ""]
    tool_heading = "Werkzeuge (" + " / ".join(result[x]["tool"]["label"] for x in TOOL_ORDER) + ")"
    headings = ["Suffix", *[result[x]["tool"]["label"] for x in WEAPON_ORDER], tool_heading, "Loop", "Von → nach",
                "Fadenkreuz frei", "Unterbrechbar", "Events (Frames je Werkzeug unten)"]
    lines.append("| " + " | ".join(headings) + " |")
    lines.append("|" + "|".join(["---"] * len(headings)) + "|")
    by_suffix = {}
    for tool_id, item in result.items():
        by_suffix[tool_id] = {c["suffix"]: c for c in item["clips"]}
    suffixes = []
    for tool_id in (*WEAPON_ORDER, *TOOL_ORDER):          # every suffix once (Charge: fusion rifle only)
        suffixes += [c["suffix"] for c in result[tool_id]["clips"] if c["suffix"] not in suffixes]
    suffixes = ["Use", *suffixes]
    for suffix in suffixes:
        exemplar = next((by_suffix[x][suffix] for x in (*WEAPON_ORDER, *TOOL_ORDER) if suffix in by_suffix[x]), None)
        if suffix == "Use":
            vals = ["97"] * len(WEAPON_ORDER) + ["97"]
            names = []
            for tool_id in (*WEAPON_ORDER, *TOOL_ORDER):
                names += [e["name"] for e in result[tool_id]["use_events"] or [] if e["name"] not in names]
            meta = ["Nein", "rest → rest", "Ja", "Ja", ", ".join(names) + "; Bogen: eigene Marker"]
        else:
            vals = [str(by_suffix[x][suffix]["length"]) if suffix in by_suffix[x] else "—" for x in WEAPON_ORDER]
            tool_vals = [str(by_suffix[x][suffix]["length"]) if suffix in by_suffix[x] else "—" for x in TOOL_ORDER]
            c = exemplar
            # event frames differ per class (lengths, charge of the fusion rifle): names here, frames per tool below
            events = ", ".join(e["name"] for e in c["events"]) or "—"
            meta = ["Ja" if c["loop"] else "Nein", f"{c['from']} → {c['to']}", "Ja" if c["reticle_free"] else "Nein",
                    "Ja" if c["interruptible"] else "Nein", events]
            vals.append(" / ".join(tool_vals))
        row = [suffix, *vals, *meta]
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## Clips je Werkzeug und Waffe", ""]
    for tool_id, item in result.items():
        tool = item["tool"]
        lines += [f"### {tool['label']} (`{tool_id}`)", "",
                  "| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |", "|---|---:|---:|---|"]
        # Use is the fixed opening range; generated clips are placed by clip_list.
        use_name = tool.get("fps_clip") or tool["clip"]
        use_events = ("Marker des Modells, `clips[0].events` im Vertrag" if item["use_events"] is None else
                      ", ".join(f"{e['name']} {e['frame'] - 1}" for e in item["use_events"]) or "—")
        lines.append(f"| `{use_name}` | 1–97 | {seconds(96, fps)} | {use_events} |")
        for c in item["clips"]:
            events = ", ".join(f"{e['name']}{'⟂' if e.get('channel') == 'rig' else ''} {e['frame'] - c['frame_start']}"
                               for e in c["events"]) or "—"
            lines.append(f"| `{c['name']}` | {c['frame_start']}–{c['frame_end']} | {seconds(c['length'], fps)} | {events} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", metavar="PFAD", help="zusätzliche maschinenlesbare JSON-Datei schreiben")
    parser.add_argument("--check", action="store_true", help="prüfen, ob docs/EGO_CLIPS.md aktuell ist")
    args = parser.parse_args(argv)
    data, result = resolved()
    markdown = render_markdown(data, result)
    target = ROOT / "docs/EGO_CLIPS.md"
    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != markdown:
            print("docs/EGO_CLIPS.md ist nicht aktuell; neu erzeugen mit python3 scripts/ego_clip_table.py", file=sys.stderr)
            return 1
    else:
        target.write_text(markdown, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(json_data(data, result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
