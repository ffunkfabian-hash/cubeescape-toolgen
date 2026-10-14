import runpy, sys, json
from pathlib import Path
import bpy
root=Path('/Users/ffunk/Documents/Codex/2026-10-14/ich-habe-die-konzepte-und-m')
sys.argv=['blender','--factory-startup','--','--output',str(root/'work/idempotence'),'--no-render']
script=runpy.run_path(str(root/'outputs/Portalkanone/create_portal_gun.py'))
script['main']()
first=script['validate']()
names=sorted(o.name for o in bpy.context.scene.objects)
script['main']()
assert first==script['validate']()
assert names==sorted(o.name for o in bpy.context.scene.objects)
print('IDEMPOTENCE_OK')
