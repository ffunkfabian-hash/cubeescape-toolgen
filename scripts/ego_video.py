#!/usr/bin/env python3
"""Motion evidence of the first-person models (Toolgen 0.15 Toolgrip): one MP4 of the Use clip and every ego clip, plus a
contact sheet of the clip boundaries and midpoints, rendered from the authored ``<asset>_FPS.blend`` through its own
viewmodel camera (fixed, as in the game). Preview only, not part of any contract.

    python3 scripts/ego_video.py <output> <video-dir> [--tool portal_emitter ...] [--size 1280x720]
        [--engine eevee|cycles] [--samples N] [--clip Reload ...] [--suffix _reload]

Writes ``<video-dir>/<tool><suffix>.mp4`` (24 fps, the clip name in the frame) and ``<video-dir>/<tool><suffix>_contact.png``
(clip start, middle, end and every clip event). ``--clip`` keeps only the named clips (``Use`` or the clip name with or without
the tool stem). Renders with Eevee (default) or Cycles on the Metal GPU when one is available, in background Blender processes
under the shared heavy-run lock (scripts/heavy_lock.py); needs ffmpeg and magick. Contract 4 and 5 models alike: the clip
table sits on the device root, which hangs under ``Prop_R`` in contract 5.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def blender_main(argv):
    """Inside Blender: render every frame of the Use clip and the ego clips into ``frames`` with the clip name stamped."""
    import bpy
    frames_dir, size, engine, samples = Path(argv[0]), [int(value) for value in argv[1].split("x")], argv[2], int(argv[3])
    wanted = set(filter(None, argv[4].split(",")))
    scene = bpy.context.scene
    root = next(obj for obj in scene.objects if "toolgen_ego_clips" in obj)
    clips = json.loads(root["toolgen_ego_clips"])["clips"]
    use = {"name": str(root["ce_action_clip"]), "frame_start": 1, "frame_end": 97, "events": []}
    selected = [clip for clip in [use, *clips]
                if not wanted or clip["name"] in wanted or clip["name"].split("_", 1)[-1] in wanted]
    for obj in scene.objects:
        if obj.name.startswith("Preview_") or "Preview_" in obj.name:
            obj.hide_render = False                # the test room gives depth cues, as in preview_first_person.png
    if engine == "cycles":
        scene.render.engine = "CYCLES"
        preferences = bpy.context.preferences.addons["cycles"].preferences
        preferences.compute_device_type = "METAL"
        preferences.get_devices()
        for entry in preferences.devices:
            entry.use = entry.type == "METAL"
        scene.cycles.device = "GPU" if any(entry.use for entry in preferences.devices) else "CPU"
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        scene.cycles.seed = 0
    else:
        scene.render.engine = "BLENDER_EEVEE"
        scene.eevee.taa_render_samples = samples
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.use_stamp = True
    for flag in ("date", "time", "render_time", "frame", "frame_range", "memory", "hostname", "camera", "lens", "scene",
                 "marker", "filename", "sequencer_strip", "note"):
        setattr(scene.render, "use_stamp_" + flag, flag in ("frame", "note"))
    scene.render.use_stamp_note = True
    scene.render.stamp_font_size = 22
    index = 0
    sheet = []
    for clip in selected:
        middle = (clip["frame_start"] + clip["frame_end"]) // 2
        marks = {clip["frame_start"]: "", middle: "", clip["frame_end"]: ""}
        for event in clip.get("events", []):
            marks[event["frame"]] = (marks.get(event["frame"]) or "") + " " + event["name"]
        for frame in range(clip["frame_start"], clip["frame_end"] + 1):
            scene.frame_set(frame)
            scene.render.stamp_note_text = f"{clip['name']}  {frame - clip['frame_start']}/{clip['frame_end'] - clip['frame_start']}"
            path = frames_dir / f"frame-{index:05d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            if frame in marks:
                sheet.append({"path": str(path),
                              "label": f"{clip['name']} {frame - clip['frame_start']}{marks[frame]}"})
            index += 1
    (frames_dir / "sheet.json").write_text(json.dumps(sheet, indent=1) + "\n")
    print("EGO_VIDEO_FRAMES", index, engine, scene.render.engine, getattr(scene.cycles, "device", ""), frames_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path)
    parser.add_argument("video_dir", type=Path)
    parser.add_argument("--tool", action="append")
    parser.add_argument("--size", default="1280x720")
    parser.add_argument("--blender", default=None)
    parser.add_argument("--engine", choices=("eevee", "cycles"), default="eevee")
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--clip", action="append", default=[])
    parser.add_argument("--suffix", default="")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "toolgen"))
    from build_toolset import find_blender
    blender = args.blender or find_blender()
    tools = {tool["id"]: tool for tool in json.loads((ROOT / "data/tools.json").read_text())["tools"]}
    args.video_dir.mkdir(parents=True, exist_ok=True)
    for tool_id in args.tool or [tool for tool in tools if tool != "bow"]:
        blend = args.output / tool_id / (tools[tool_id]["asset"] + "_FPS.blend")
        stem = tool_id + args.suffix
        frames = args.video_dir / f"{stem}_frames"
        if frames.exists():
            shutil.rmtree(frames)
        frames.mkdir()
        subprocess.run([sys.executable, str(ROOT / "scripts/heavy_lock.py"), "run", "--resource", "blender",
                        "--what", f"toolgen ego_video {tool_id}",
                        "--checkout", str(ROOT), "--", blender, "--background", "--factory-startup", str(blend),
                        "--python-exit-code", "1", "--python", __file__, "--",
                        "--render", str(frames), args.size, args.engine, str(args.samples), ",".join(args.clip)],
                       check=True)
        movie = args.video_dir / f"{stem}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i", str(frames / "frame-%05d.png"),
                        "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(movie)], check=True)
        sheet = json.loads((frames / "sheet.json").read_text())
        command = ["magick", "montage"]
        for entry in sheet:
            command += ["-label", entry["label"], entry["path"]]
        command += ["-tile", "6x", "-geometry", "384x216+4+4", "-pointsize", "14", "-background", "#111", "-fill", "#ddd",
                    str(args.video_dir / f"{stem}_contact.png")]
        subprocess.run(command, check=True)
        print("EGO_VIDEO_OK", tool_id, movie)


if __name__ == "__main__":
    if "--render" in sys.argv:
        blender_main(sys.argv[sys.argv.index("--render") + 1:])
    else:
        main()
