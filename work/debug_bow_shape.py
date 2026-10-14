import runpy,bpy,bmesh
p='/Users/ffunk/Documents/Codex/2026-10-14/ich-habe-die-konzepte-und-m/outputs/Bogen/create_standard_bow.py'
d=runpy.run_path(p);scope=d['main'].__globals__;old=scope['shape']
def volume(o):
 b=bmesh.new();b.from_mesh(o.data);v=b.calc_volume(signed=True);b.free();return v
def traced(o,fn):
 before=volume(o);old(o,fn);after=volume(o)
 if 'Bowstring' in o.name: print('TRACE',o.name,before,after,[(k.name,k.value) for k in o.data.shape_keys.key_blocks])
scope['shape']=traced
try:d['main']()
except Exception as e:print('FAIL',e)
