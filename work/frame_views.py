import runpy
from pathlib import Path
import bpy
from mathutils import Vector
root=Path('/Users/ffunk/Documents/Codex/2026-10-14/ich-habe-die-konzepte-und-m/outputs/Portalkanone')
ns=runpy.run_path(str(root/'create_portal_gun.py'))
bpy.ops.wm.open_mainfile(filepath=str(root/'CubeEscape_PortalGun.blend'))
scene=bpy.context.scene
ns['render'](scene,scene.camera,Vector((0,-.104,.078)),root/'view_front.png',(0,-1,0),.62)
ns['render'](scene,scene.camera,Vector((0,-.104,.078)),root/'view_top.png',(0,0,1),.98)
