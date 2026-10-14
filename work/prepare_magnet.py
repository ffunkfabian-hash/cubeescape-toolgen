from pathlib import Path
src=Path('outputs/Portalkanone/create_portal_gun.py').read_text()
start=src.index('    # Short segmented barrel, concentric blue ring, black recessed bore.')
end=src.index('\n\ndef validate():',start)
head='''    # Compact magnetic head with a recessed core, distinct from the portal ring.
    cylinder('MagnetNeck', (0,-.153,.084), .068,.058,'Dark',n=40,bevel=.003)
    ring('MagnetRearBand',-.143,.074,.064,.013,'Metal',n=40)
    cylinder('MagnetHead', (0,-.192,.084), .072,.034,'Dark',n=40,bevel=.004)
    ring('MagnetFaceArmor',-.212,.070,.046,.009,'Armor',n=40)
    cylinder('MagnetCoreMount',(0,-.215,.084),.044,.014,'Visor',n=40,bevel=.002)
    ring('MagnetCoreTrim',-.225,.037,.030,.006,'Metal',n=48)
    cylinder('MagnetCore',(0,-.230,.084),.030,.006,'DeepBlue',n=40,bevel=.001)
    cylinder('MagnetCoreGlow',(0,-.234,.084),.016,.003,'Cyan',n=32,bevel=.0006)
    for i in range(8):
        a=2*math.pi*i/8
        cylinder('MagnetCoil_%d'%i,(.053*math.cos(a),-.222,.084+.053*math.sin(a)),
                 .003,.003,'Cyan',n=12,bevel=.0005)
    spine=[(-.163,.063),(-.202,.124),(-.266,.157),(-.316,.143),
           (-.382,.092),(-.418,.053),(-.414,.031),(-.394,.031),
           (-.362,.066),(-.301,.112),(-.265,.119),(-.225,.100),(-.204,.054)]
    armor=[(-.179,.073),(-.208,.127),(-.266,.149),(-.308,.138),
           (-.372,.091),(-.398,.059),(-.386,.059),(-.306,.128),
           (-.266,.137),(-.223,.114),(-.199,.070)]
    inner=[(-.207,.066),(-.228,.094),(-.268,.114),(-.305,.106),
           (-.368,.059),(-.397,.027),(-.411,.034),(-.380,.078),
           (-.309,.127),(-.265,.128),(-.223,.107),(-.195,.071)]
    for s,name in [(1,'Upper'),(-1,'Lower')]:
        pivot=(0,-.165,.084+s*.064)
        group=empty('Pivot_'+name,GEO,ROOT,pivot)
        bpy.context.view_layer.update()
        prism(name+'JawSpine',[(y,.084+s*z) for y,z in spine],.075,'Dark',group)
        prism(name+'JawArmor',[(y,.084+s*z) for y,z in armor],.080,'AccentArmor',group)
        prism(name+'InnerContactRail',[(y,.084+s*z) for y,z in inner],.082,'Metal',group)
        cylinder(name+'Hinge',pivot,.026,.089,'Dark',axis=(1,0,0),parent=group)
        for side in (-1,1):
            cylinder(name+'HingeCap'+str(side),(side*.049,pivot[1],pivot[2]),
                     .019,.013,'Armor',axis=(1,0,0),parent=group)
            cylinder(name+'HingeHub'+str(side),(side*.057,pivot[1],pivot[2]),
                     .009,.004,'Metal',axis=(1,0,0),parent=group,n=16)
            for yy,zz in [(-.237,.128),(-.310,.132),(-.373,.082)]:
                cylinder(name+'JawBolt'+str(side)+str(yy),(side*.043,yy,.084+s*zz),
                         .0037,.004,'Metal',axis=(1,0,0),parent=group,n=12,bevel=.0005)
        box(name+'ContactPad',(0,-.404,.084+s*.042),(.058,.030,.022),
            'Rubber',.004,parent=group,rot=Matrix.Rotation(s*math.radians(-38),3,'X'))
        for j in range(3):
            box(name+'ContactRib'+str(j),(-.018+j*.018,-.411,.084+s*.028),
                (.007,.021,.007),'Dark',.002,parent=group)
        box(name+'JawStatus',(0,-.266,.084+s*.158),(.036,.020,.005),
            'Cyan',.0015,parent=group)
    empty('Socket_Hand',GEO,ROOT,(0,.116,-.057))
    empty('Socket_Muzzle',GEO,ROOT,(0,-.237,.084))
    empty('Socket_SupportHand',GEO,ROOT,(0,-.045,-.008))
    empty('Socket_Grab',GEO,ROOT,(0,-.406,.084))
'''
src=src[:start]+head+src[end:]
src=src.replace('CubeEscape_PortalGun','CubeEscape_MagnetGripper').replace('PG_','MG_')
src=src.replace('portal gun','magnet gripper').replace("'tool','portal'","'tool','magnet-gripper'")
src=src.replace('portal ring and two opposed brackets','magnetic head and two opposed gripping jaws')
Path('outputs/Magnetgreifer/create_magnet_gripper.py').write_text(src)
fps=Path('outputs/Portalkanone/create_portal_gun_fps.py').read_text()
fps=fps.replace('CubeEscape_PortalGun','CubeEscape_MagnetGripper').replace('PG_','MG_')
fps=fps.replace('create_portal_gun.py','create_magnet_gripper.py')
fps=fps.replace('portal gun','magnet gripper').replace('(.44<p.x<.56 and .44<p.y<.56)','(.46<p.x<.54 and .46<p.y<.54)')
Path('outputs/Magnetgreifer/create_magnet_gripper_fps.py').write_text(fps)
verify=Path('outputs/Portalkanone/verify_portal_gun.py').read_text().replace('CubeEscape_PortalGun','CubeEscape_MagnetGripper').replace('PORTAL_GUN_ROUNDTRIP_OK','MAGNET_GRIPPER_ROUNDTRIP_OK')
Path('outputs/Magnetgreifer/verify_magnet_gripper.py').write_text(verify)
sh=Path('outputs/Portalkanone/build_cube_escape_assets.sh').read_text().replace('create_portal_gun','create_magnet_gripper').replace('verify_portal_gun','verify_magnet_gripper')
Path('outputs/Magnetgreifer/build_cube_escape_assets.sh').write_text(sh)
