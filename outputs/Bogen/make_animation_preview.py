"""Encode the rendered Bow_Use frames as a single-play GIF (ImageMagick)."""
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parent
frames=(1,16,31,43,44,48,79,97)
delays=(45,55,55,60,30,45,55,70)
command=['magick']
for frame,delay in zip(frames,delays):
    path=root/'animation_frames'/('bow_%03d.png'%frame)
    if not path.is_file():
        raise RuntimeError('Missing current animation render: '+str(path))
    command+=['-delay',str(delay),str(path)]
command+=['-loop','1',str(root/'preview_draw_once.gif')]
subprocess.run(command,check=True)
