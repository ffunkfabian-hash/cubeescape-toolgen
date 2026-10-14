import runpy,bpy,bmesh
p='/Users/ffunk/Documents/Codex/2026-10-14/ich-habe-die-konzepte-und-m/outputs/Bogen/create_standard_bow.py'
d=runpy.run_path(p)
try:d['main']()
except Exception as e:
    print(e)
    for o in bpy.context.scene.objects:
        if 'Bowstring' in o.name:
            bm=bmesh.new();bm.from_mesh(o.data)
            print(o.name,'vol',bm.calc_volume(signed=True),'bounds',tuple(o.dimensions),'coords',[(tuple(v.co)) for v in o.data.vertices][:4], 'shapekeys',[(k.name,k.value) for k in o.data.shape_keys.key_blocks])
