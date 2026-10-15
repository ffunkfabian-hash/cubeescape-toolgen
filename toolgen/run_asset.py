"""Run an authoring step inside a fresh Blender worker with shared presentation limits."""
import argparse
import os
import runpy
import sys
from pathlib import Path

import bpy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True)
    args, remaining = parser.parse_known_args(sys.argv[sys.argv.index("--") + 1:])
    script = Path(args.script).resolve()
    sys.path.insert(0, str(script.parent))
    sys.path.insert(0, str(script.parent.parent))
    sys.argv = [str(script), "--", *remaining]
    device = os.environ.get("TOOLGEN_DEVICE", "cpu")
    if device == "metal":
        preferences = bpy.context.preferences.addons["cycles"].preferences
        preferences.compute_device_type = "METAL"
        preferences.get_devices()
        for entry in preferences.devices:
            entry.use = entry.type == "METAL"
        if not any(entry.use for entry in preferences.devices):
            raise RuntimeError("No Metal render device is available")

    @bpy.app.handlers.persistent
    def configure(scene):
        scene.render.threads_mode = "FIXED"
        scene.render.threads = int(os.environ.get("TOOLGEN_THREADS", "4"))
        scene.cycles.samples = int(os.environ.get("TOOLGEN_SAMPLES", "40"))
        scene.cycles.device = "GPU" if device == "metal" else "CPU"
        scene.render.resolution_percentage = int(os.environ.get("TOOLGEN_RENDER_PERCENT", "100"))

    bpy.app.handlers.render_init.append(configure)
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
