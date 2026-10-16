"""Use-clip preview GIF of the weapons (system Python, no Blender): the rendered frames of animate_weapon.py as a single-play GIF."""
from pathlib import Path
import subprocess
import sys

FRAMES = (1, 8, 14, 17, 22, 30, 45, 60, 75, 97)
DELAYS = (45, 40, 40, 40, 60, 60, 60, 60, 60, 70)


def make():
    root = Path(sys.argv[0]).resolve().parent
    command = ['magick']
    for frame, delay in zip(FRAMES, DELAYS):
        path = root / 'animation_frames' / ('apply_%03d.png' % frame)
        if not path.is_file():
            raise RuntimeError('Missing current animation render: ' + str(path))
        command += ['-delay', str(delay), str(path)]
    command += ['-loop', '1', str(root / 'preview_apply_once.gif')]
    subprocess.run(command, check=True)
