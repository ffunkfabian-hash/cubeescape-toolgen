"""Encode the current Blender-rendered action frames as a single-play GIF."""
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parent
frames=(1,13,28,43,58,73,85,97)
delays=(45,60,60,60,60,60,50,70)
command=['magick']
for frame,delay in zip(frames,delays):
    path=root/'animation_frames'/('apply_%03d.png'%frame)
    if not path.is_file():
        raise RuntimeError('Missing current animation render: '+str(path))
    command+=['-delay',str(delay),str(path)]
command+=['-loop','1',str(root/'preview_apply_once.gif')]
subprocess.run(command,check=True)
