"""Geometry and Use-clip data of the nine hand weapons (no bpy: the kit passes in the modelling primitives).

Conventions (Blender): forward -Y, up +Z, X lateral; the origin is the centre of the pistol grip (Socket_Hand).
``DESIGNS[key]`` fields: ``asset``, ``clip``, ``class`` (readable name), ``element`` (glow colour: kinetic grey/white,
energy cyan, solar orange, void violet, arc blue), ``grip_tilt_degrees`` (the grip axis leans forward at the top; the hand
follows it; mirrored in the tools.json entry and data/viewmodels.json, which tests/test_weapons.py compares),
``grip_part`` / ``support_part`` (mesh-name prefix after ``SM_PG_`` of the parts that contain Socket_Hand / Socket_SupportHand),
``view_center`` / ``view_scale`` (presentation camera), ``use_clip`` (moves of the one-shot Use clip: child nodes only, each
move {node, channel location|rotation, axis 0..2, keys [(frame, offset m | degrees)]}), ``fire_frame`` (the shot: marker
``Fire`` of the Use clip, equal to ``motion.fire_frame`` in data/viewmodels.json), ``sight`` (line of sight for sight.py:
Socket_Sight / Socket_Eye, equal to the AimIdle line of data/ego_clips.json), ``trigger`` and ``build(kit)``.
Every weapon needs the sockets Socket_Hand, Socket_Muzzle, Socket_SupportHand and Socket_CenterOfMass; the kit adds
Socket_Sight (and Socket_Eye for scopes).
"""
import math


def along(k, ly, lz):
    """World (y, z) of the grip-local offset (ly, lz): the grip frame is tilted about X by the grip tilt."""
    a = math.radians(k.grip_tilt)
    return ly * math.cos(a) - lz * math.sin(a), ly * math.sin(a) + lz * math.cos(a)


def grip(k, height, width=.036, depth=.046, ribs=3, cap='Metal'):
    """Pistol grip centred on the origin (Socket_Hand), tilted by the grip tilt; hand-wrap cross-section width x depth."""
    r = k.tilt(k.grip_tilt)
    k.box('GripCore', (0, 0, 0), (width, depth, height), 'Secondary', .009, rot=r)
    for side in (-1, 1):
        y, z = along(k, 0, 0)
        k.box('GripShell_%d' % side, (side * (width / 2 + .0015), y, z), (.006, depth - .006, height - .012), 'Primary', .003, rot=r)
    for i in range(ribs):
        lz = height * .30 - i * height * .60 / max(ribs - 1, 1)
        y, z = along(k, -depth / 2 - .0005, lz)
        k.box('GripRib_%d' % i, (0, y, z), (width * .66, .006, .008), 'Detail', .0015, rot=r)
    y, z = along(k, 0, -height / 2 - .004)
    k.box('GripCap', (0, y, z), (width + .004, depth + .004, .012), cap, .004, rot=r)
    y, z = along(k, depth / 2 + .006, height / 2 - .007)
    k.box('GripTail', (0, y, z), (width * .8, .014, .010), 'Secondary', .003, rot=r)
    k.bolts('GripScrew', [(side * (width / 2 + .0045), *along(k, 0, -height * .30)) for side in (-1, 1)],
            radius=.0028, depth=.0016)


def trigger_group(k, front, back, bottom, top):
    """Trigger guard (bottom bar and front bar) and trigger between y=front..back and z=bottom..top."""
    k.box('GuardBottom', (0, (front + back) / 2, bottom), (.012, back - front, .005), 'Secondary', .002)
    k.box('GuardFront', (0, front, (bottom + top) / 2), (.012, .005, top - bottom), 'Secondary', .002)
    k.box('Trigger', (0, back - .014, (bottom + top) / 2 + .004), (.007, .007, top - bottom - .008), 'Metal', .002)


def rail(k, name, y0, y1, z, width=.020, slots=True, parent=None):
    """Top rail with dark slots every 14 mm."""
    k.box(name, (0, (y0 + y1) / 2, z), (width, y1 - y0, .010), 'Metal', .002, parent)
    if slots:
        count = int((y1 - y0) / .014) - 1
        for i in range(count):
            k.box('%sSlot_%d' % (name, i), (0, y0 + .014 * (i + 1), z + .0052), (width * .8, .004, .0016), 'Secondary', .0004, parent)


def side_vents(k, name, y0, step, count, z, x, size=(.002, .010, .018), mat='Secondary'):
    """Vent slots down the handguard: on both sides at x, or once on the centre line (x = 0)."""
    for side in ((-1, 1) if x else (1,)):
        for i in range(count):
            k.box('%s_%d_%d' % (name, side, i), (side * x, y0 - step * i, z), size, mat, .0008)


def stock(k, name, points, width, pad, pad_size, pad_y, pad_z, mat='Primary'):
    k.slab(name, points, width, mat, bevel=.006)
    cy = sum(p[0] for p in points) / len(points)
    cz = sum(p[1] for p in points) / len(points)
    k.slab(name + 'Inset', [(cy + (y - cy) * .55, cz + (z - cz) * .55) for y, z in points], width + .003, 'Secondary', bevel=.0015)
    k.box('Buttpad', (0, pad_y, pad_z), pad_size, pad, .004)


EYE_LENS = .9          # eye lens radius / scope tube radius (inner radius of the open eyepiece)
EYE_RECESS = .008      # the eye lens sits this far inside the eyepiece's rear end


def scope(k, y, z, length, radius, lens_radius=None):
    """Optical sight along Y: tube, objective, eyepiece, glowing front lens, turret, two mounts."""
    lens = lens_radius or radius * 1.35
    k.cyl('ScopeTube', (0, y, z), radius, length, 'Secondary', n=24)
    k.cyl('ScopeObjective', (0, y - length / 2 + .01, z), lens, length * .30, 'Primary', n=24)
    # Open eyepiece (0.11.0, Cube Escape 0.72): a ring with the eye lens set in from its rear end, where the game draws its
    # scope picture (Socket_Eye at the lens centre, hold.eye_radius_m = its radius in the first-person model).
    k.tube('ScopeEyepiece', (0, y + length / 2 - .005, z), radius * 1.2, radius * EYE_LENS, length * .22, 'Primary', n=24)
    k.cyl('ScopeEyeLens', (0, y + length / 2 - .005 + length * .11 - EYE_RECESS, z), radius * EYE_LENS, .002, 'Detail',
          n=24, bevel=.0003)
    k.cyl('ScopeLens', (0, y - length / 2 - length * .30 / 2 + .012, z), lens * .86, .004, k.glow_material, n=24, bevel=.0005)
    k.cyl('ScopeTurret', (0, y, z + radius + .006), radius * .55, .016, 'Metal', axis='z', n=16, bevel=.001)
    for dy in (-length * .28, length * .24):
        k.box('ScopeMount_%d' % int(dy * 1000), (0, y + dy, z - radius - .012), (.020, .026, .030), 'Metal', .003)


def muzzle_device(k, y, z, radius, length, rings=2):
    """Muzzle brake with an element-glow ring and a metal end ring."""
    k.cyl('MuzzleBrake', (0, y, z), radius, length, 'Secondary', n=28)
    k.tube('MuzzleGlow', (0, y - length * .18, z), radius + .0015, radius * .55, .006, k.glow_material, n=28)
    k.tube('MuzzleRing', (0, y - length / 2 + .004, z), radius + .002, radius * .5, .008, 'Metal', n=28)
    for i in range(rings):
        k.box('MuzzleSlot_%d' % i, (0, y + length * .12 + i * length * .22, z + radius), (radius * .8, .006, .003), 'Detail', .0006)


def magazine(k, name, points, width, mat='Secondary', glow_height=.04, parent=None):
    k.slab(name, points, width, mat, bevel=.004, parent=parent)


# ------------------------------------------------------------------------------------------- modular components
# Hard-surface modules shared by the nine weapons (industrial sci-fi: panels with seams, displays, energy cells, heat
# sinks, accents). Positions are in the weapon frame; the first-person camera looks at the +X side and the top, so the
# readouts face +X or the player (+Y). None of them touches the grip or the support-hand zone.
def panel(k, name, center, size, mat='Primary', parent=None):
    """Cladding plate with a dark seam: a slightly larger, thinner Detail plate behind it shows as a panel gap."""
    thin = min(range(3), key=lambda i: size[i])
    seam = [size[i] + (.003 if i != thin else -size[i] * .4) for i in range(3)]
    k.box(name + 'Seam', center, seam, 'Detail', 0, parent)
    k.box(name, center, size, mat, min(.002, size[thin] * .4), parent)


def display(k, name, center, size, facing='x', bars=3, parent=None):
    """Status readout (ammunition, charge, lock): Secondary bezel, dark glass and glowing segment bars.
    ``facing`` 'x' = screen normal +X (size = depth, length y, height z), 'y' = towards the player +Y (width x, depth, height z)."""
    axis = 0 if facing == 'x' else 1
    k.box(name + 'Bezel', center, size, 'Secondary', .001, parent)
    glass = list(size)
    glass[axis] = .0008
    for i in range(3):
        if i != axis:
            glass[i] = size[i] - .003
    out = list(center)
    out[axis] += size[axis] / 2 + .0002
    k.box(name + 'Glass', tuple(out), glass, 'Detail', 0, parent)
    long = 1 if facing == 'x' else 0
    bar = list(glass)
    bar[axis] = .0006
    bar[long] = glass[long] * .8 / bars
    bar[2] = glass[2] * .35
    for i in range(bars):
        spot = list(out)
        spot[axis] += .0005
        spot[long] += (i - (bars - 1) / 2) * glass[long] / bars
        spot[2] += glass[2] * (.12 if i % 2 else -.12)
        k.box('%sBar_%d' % (name, i), tuple(spot), bar, 'Display', 0, parent)


def energy_cell(k, name, center, radius, length, axis='y', parent=None):
    """Exposed energy module: glowing core between metal end caps, held by four Secondary cage bars."""
    k.cyl(name + 'Core', center, radius * .72, length * .84, k.glow_material, axis, .0005, parent, n=16)
    index = {'x': 0, 'y': 1, 'z': 2}[axis]
    for side in (-1, 1):
        cap = list(center)
        cap[index] += side * length * .44
        k.cyl('%sCap_%d' % (name, side), tuple(cap), radius, length * .12, 'Metal', axis, .0008, parent, n=16)
    others = [i for i in range(3) if i != index]
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        spot = list(center)
        spot[others[0]] += radius * .82 * math.cos(a)
        spot[others[1]] += radius * .82 * math.sin(a)
        size = [radius * .28] * 3
        size[index] = length * .78
        k.box('%sCage_%d' % (name, i), tuple(spot), size, 'Secondary', 0, parent)


def heat_sink(k, name, center, count, step, fin, mat='Metal', parent=None):
    """``count`` cooling fins of size ``fin`` from ``center`` backwards along -Y in ``step`` intervals."""
    for i in range(count):
        k.box('%s_%d' % (name, i), (center[0], center[1] - i * step, center[2]), fin, mat, 0, parent)


def side_armor(k, name, points, x, thickness=.003, mat='Secondary', parent=None):
    """Chamfered side plate (profile [(y, z), ...]) on both sides of a body of half width ``x``, with a dark seam."""
    cy = sum(p[0] for p in points) / len(points)
    cz = sum(p[1] for p in points) / len(points)
    grown = []
    for y, z in points:
        d = math.hypot(y - cy, z - cz) or 1.0
        grown.append((y + (y - cy) / d * .0016, z + (z - cz) / d * .0016))
    for side in (-1, 1):
        k.slab('%sSeam_%d' % (name, side), grown, thickness * .5, 'Detail', x=side * x, bevel=0, parent=parent)
        k.slab('%s_%d' % (name, side), points, thickness, mat, x=side * (x + thickness / 2), bevel=.001, parent=parent)


def accent(k, name, center, size, parent=None, rot=None):
    k.box(name, center, size, 'Accent', min(.0015, min(size) * .3), parent, rot)


# ----------------------------------------------------------------------------------------------------- 1 pistol
def pistol(k):
    """Sidearm: one-handed, short slide that cycles back, glowing slide strips and magazine windows."""
    grip(k, .102, .034, .044, ribs=4)
    r = k.tilt(k.grip_tilt)
    for side in (-1, 1):
        y, z = along(k, .0, -.030)
        k.glow('MagWindow_%d' % side, (side * .0225, y, z), (.002, .016, .036), rot=r)
    k.box('Frame', (0, -.045, .034), (.030, .165, .020), 'Secondary', .006)
    k.box('FrameRail', (0, -.108, .026), (.020, .060, .008), 'Metal', .002)
    trigger_group(k, -.071, -.011, .008, .036)
    k.box('Hammer', (0, .060, .069), (.010, .014, .016), 'Secondary', .003)
    slide = k.pivot('Anim_Slide', (0, -.045, .062))
    k.box('SlideBody', (0, -.045, .062), (.036, .205, .034), 'Primary', .008, parent=slide)
    k.box('SlideTop', (0, -.045, .082), (.016, .190, .007), 'Secondary', .003, parent=slide)
    k.box('SlideNose', (0, -.140, .060), (.030, .014, .030), 'Secondary', .004, parent=slide)
    for i in range(4):
        k.box('SlideSerration_%d' % i, (0, .030 + i * .010, .062), (.0385, .004, .026), 'Secondary', .001, parent=slide)
    for side in (-1, 1):
        k.glow('SlideStripe_%d' % side, (side * .0185, -.062, .066), (.002, .105, .007), parent=slide)
    k.box('FrontSight', (0, -.128, .0825), (.006, .012, .010), 'Metal', .002, parent=slide)
    for side in (-1, 1):
        k.box('RearSight_%d' % side, (side * .009, .040, .0825), (.006, .010, .010), 'Metal', .002, parent=slide)
    k.cyl('Barrel', (0, -.158, .062), .0095, .036, 'Metal', n=20)
    k.tube('MuzzleRing', (0, -.171, .062), .0125, .0065, .008, 'Secondary', n=24)
    mag = k.pivot('Anim_Magazine', (0, *along(k, 0, -.0635)))
    pistol_modules(k, slide, mag)
    k.socket('Socket_Hand', (0, 0, 0))
    k.socket('Socket_Muzzle', (0, -.176, .062))
    # 0.10.0: two-handed cup grip (Destiny): the left hand wraps the right one from below left, its centre at the grip's
    # left side, below the right hand (was the frame in front of the trigger guard, (0, -.05, .034), in 0.7-0.9).
    k.socket('Socket_SupportHand', (.017, *along(k, 0, -.016)))
    k.socket('Socket_CenterOfMass', (0, -.02, .03))


# ----------------------------------------------------------------------------------------------- 2 assault rifle
def assault_rifle(k):
    """Assault rifle: long receiver with top rail and optic, curved magazine, stock, handguard with glow strips."""
    zb = .085
    grip(k, .100, .036, .046, ribs=3)
    k.box('ReceiverLower', (0, 0, .058), (.046, .19, .040), 'Primary', .008)
    k.box('ReceiverUpper', (0, -.03, .092), (.050, .30, .040), 'Primary', .008)
    rail(k, 'TopRail', -.17, .11, .117)
    k.box('MagWell', (0, -.092, .040), (.040, .070, .020), 'Secondary', .005)
    mag = k.pivot('Anim_Magazine', (0, -.095, .038))
    magazine(k, 'Magazine', [(-.115, .038), (-.072, .038), (-.070, -.030), (-.082, -.095), (-.122, -.100), (-.118, -.030)], .032, parent=mag)
    for side in (-1, 1):
        k.glow('MagWindow_%d' % side, (side * .0165, -.095, -.040), (.002, .018, .050), parent=mag)
    trigger_group(k, -.066, -.008, .010, .040)
    stock(k, 'Stock', [(.095, .093), (.27, .103), (.345, .098), (.345, -.045), (.31, -.05), (.205, .008), (.095, .040)],
          .040, 'Detail', (.044, .014, .148), .352, .028)
    k.box('StockCore', (0, .16, .052), (.030, .13, .030), 'Secondary', .006)
    k.box('Handguard', (0, -.235, zb), (.058, .21, .054), 'Primary', .010)
    k.box('HandguardRail', (0, -.235, zb - .031), (.024, .20, .008), 'Secondary', .002)
    side_vents(k, 'HandguardVent', -.175, .028, 5, zb + .004, .0295)
    for side in (-1, 1):
        k.glow('HandguardGlow_%d' % side, (side * .0295, -.235, zb - .016), (.002, .15, .006))
    k.cyl('Barrel', (0, -.43, zb), .011, .17, 'Metal', n=20)
    k.cyl('GasBlock', (0, -.37, zb), .016, .035, 'Secondary', n=20)
    k.box('FrontSight', (0, -.37, zb + .032), (.010, .012, .030), 'Metal', .002)
    muzzle_device(k, -.54, zb, .019, .07)
    k.box('Optic', (0, -.025, .138), (.034, .085, .038), 'Secondary', .007)
    k.glow('OpticGlow', (0, -.025, .1585), (.012, .05, .002))
    k.box('OpticLensFrame', (0, -.0675, .138), (.028, .004, .030), 'Detail', .002)
    bolt = k.pivot('Anim_Bolt', (0, 0, .095))
    k.box('BoltCover', (.0275, -.02, .095), (.007, .085, .026), 'Metal', .003, parent=bolt)
    k.cyl('BoltKnob', (.034, .02, .098), .008, .012, 'Secondary', axis='x', n=14, bevel=.001, parent=bolt)
    assault_rifle_modules(k, mag)
    k.socket('Socket_Hand', (0, 0, 0))
    k.socket('Socket_Muzzle', (0, -.578, zb))
    k.socket('Socket_SupportHand', (0, -.235, zb))
    k.socket('Socket_CenterOfMass', (0, -.06, .06))


# ------------------------------------------------------------------------------------------------ 3 pulse rifle
def pulse_rifle(k):
    """Bullpup pulse rifle: one chassis from muzzle shroud to shoulder, energy cell behind the grip, glowing pulse coils."""
    zb = .075
    grip(k, .095, .036, .046, ribs=3)
    k.slab('Chassis', [(-.20, .055), (-.165, .105), (.08, .112), (.20, .108), (.315, .098), (.33, .060), (.315, -.02),
                       (.235, -.04), (.125, -.04), (.065, .022), (-.20, .022)], .052, 'Primary', bevel=.008)
    k.slab('ChassisPanel', [(-.12, .035), (.04, .035), (.04, .09), (-.12, .09)], .056, 'Secondary', bevel=.004)
    for side in (-1, 1):
        k.glow('ChassisGlow_%d' % side, (side * .0285, .09, .102), (.002, .17, .006))
    k.box('CellWell', (0, .18, -.035), (.040, .070, .020), 'Secondary', .005)
    mag = k.pivot('Anim_EnergyCell', (0, .18, -.03))
    magazine(k, 'EnergyCell', [(.145, -.03), (.215, -.03), (.215, -.100), (.145, -.100)], .034, glow_height=.04, parent=mag)
    for side in (-1, 1):
        k.glow('CellWindow_%d' % side, (side * .0175, .18, -.065), (.002, .040, .040), parent=mag)
    trigger_group(k, -.060, -.010, .014, .040)
    k.box('Buttpad', (0, .335, .030), (.052, .014, .130), 'Detail', .004)
    k.cyl('Shroud', (0, -.29, zb), .030, .19, 'Primary', n=32, bevel=.003)
    k.cyl('ShroudCore', (0, -.25, zb), .024, .26, 'Secondary', n=28)
    for i, y in enumerate((-.27, -.32, -.37)):
        k.tube('PulseCoil_%d' % i, (0, y, zb), .0335, .026, .010, k.glow_material, n=32)
    k.cyl('Barrel', (0, -.43, zb), .010, .13, 'Metal', n=20)
    k.tube('MuzzleCup', (0, -.50, zb), .026, .012, .040, 'Secondary', n=28)
    k.cyl('MuzzleCore', (0, -.516, zb), .010, .004, k.glow_material, n=20, bevel=.0005)
    for side in (-1, 1):
        k.box('MuzzleFin_%d' % side, (side * .030, -.49, zb), (.006, .05, .020), 'Metal', .002)
    k.box('Sight', (0, 0, .135), (.026, .075, .030), 'Secondary', .006)
    k.glow('SightGlow', (0, 0, .1515), (.012, .05, .003))
    k.box('FrontPost', (0, -.17, .122), (.008, .012, .020), 'Metal', .002)
    cell = k.pivot('Anim_Cell', (0, -.075, .128))
    k.box('TopCell', (0, -.075, .128), (.040, .090, .016), 'Primary', .004, parent=cell)
    k.glow('TopCellGlow', (0, -.075, .1375), (.020, .060, .002), parent=cell)
    pulse_rifle_modules(k)
    k.socket('Socket_Hand', (0, 0, 0))
    k.socket('Socket_Muzzle', (0, -.522, zb))
    k.socket('Socket_SupportHand', (0, -.235, zb))
    k.socket('Socket_CenterOfMass', (0, .06, .06))


# -------------------------------------------------------------------------------------------------- 4 shotgun
def shotgun(k):
    """Shotgun: broad receiver, wide-bore barrel with shroud, tube magazine and fore-end, solar glow plates, bolt rack."""
    zb = .070
    grip(k, .100, .040, .048, ribs=3)
    k.box('Receiver', (0, -.03, .058), (.060, .19, .062), 'Primary', .010)
    k.box('StockNeck', (0, .10, .052), (.046, .08, .050), 'Secondary', .006)
    for side in (-1, 1):
        k.box('SidePlate_%d' % side, (side * .0315, -.02, .058), (.004, .12, .040), 'Secondary', .002)
        k.glow('SideGlow_%d' % side, (side * .0335, -.02, .058), (.002, .10, .008))
    rail(k, 'TopRail', -.09, .045, .093, .024)
    trigger_group(k, -.066, -.008, .012, .040)
    stock(k, 'Stock', [(.095, .085), (.28, .090), (.36, .075), (.375, -.04), (.34, -.050), (.20, .01), (.095, .03)],
          .048, 'Detail', (.05, .014, .12), .382, .02)
    k.cyl('Bore', (0, -.30, zb), .027, .39, 'Secondary', n=32, bevel=.002)
    k.cyl('BarrelShroud', (0, -.31, zb), .0315, .30, 'Primary', n=32, bevel=.003)
    side_vents(k, 'ShroudVent', -.20, .03, 6, zb + .0295, 0.0, (.014, .010, .003))
    k.tube('MuzzleCup', (0, -.495, zb), .037, .022, .040, 'Secondary', n=32)
    k.tube('MuzzleGlow', (0, -.468, zb), .0365, .030, .006, k.glow_material, n=32)
    k.cyl('BoreLiner', (0, -.480, zb), .023, .005, 'Detail', n=28, bevel=.0005)
    k.cyl('TubeMagazine', (0, -.28, .030), .015, .31, 'Metal', n=24)
    loader = k.pivot('Anim_Magazine', (0, -.26, .037))
    k.box('ForeEnd', (0, -.26, .037), (.048, .15, .042), 'Primary', .010, parent=loader)
    k.box('ForeEndRail', (0, -.26, .014), (.024, .13, .008), 'Secondary', .002, parent=loader)
    for side in (-1, 1):
        k.glow('ForeGlow_%d' % side, (side * .0245, -.26, .040), (.002, .09, .006), parent=loader)
    k.box('FrontBead', (0, -.455, .1055), (.008, .008, .012), 'Metal', .002)
    bolt = k.pivot('Anim_Bolt', (0, 0, .092))
    k.box('BoltSlider', (0, -.005, .098), (.034, .080, .014), 'Metal', .003, parent=bolt)
    k.cyl('BoltKnob', (0, .04, .105), .009, .014, 'Secondary', axis='z', n=14, bevel=.001, parent=bolt)
    shotgun_modules(k)
    k.socket('Socket_Hand', (0, 0, 0))
    k.socket('Socket_Muzzle', (0, -.518, zb))
    k.socket('Socket_SupportHand', (0, -.26, .037))
    k.socket('Socket_CenterOfMass', (0, -.05, .05))


# ----------------------------------------------------------------------------------------------- 5 sniper rifle
def sniper_rifle(k):
    """Sniper rifle: long barrel with heavy muzzle brake, big scope with glowing lens, side bolt handle, cheek riser."""
    zb = .068
    grip(k, .095, .034, .044, ribs=3)
    k.box('Receiver', (0, -.04, .062), (.044, .30, .046), 'Primary', .008)
    k.box('Chassis', (0, -.03, .036), (.036, .34, .016), 'Secondary', .004)
    rail(k, 'TopRail', -.18, .08, .090, .018)
    mag = k.pivot('Anim_Magazine', (0, -.05, .030))
    k.box('MagBox', (0, -.05, .004), (.032, .070, .052), 'Secondary', .005, parent=mag)
    for side in (-1, 1):
        k.glow('MagWindow_%d' % side, (side * .0165, -.05, .004), (.002, .040, .028), parent=mag)
    trigger_group(k, -.058, -.008, .014, .040)
    stock(k, 'Stock', [(.12, .090), (.30, .100), (.40, .090), (.42, .080), (.42, -.07), (.38, -.075), (.34, -.03), (.22, -.01), (.12, .02)],
          .040, 'Detail', (.046, .014, .16), .427, .005)
    k.box('CheekRiser', (0, .28, .118), (.036, .12, .020), 'Secondary', .005)
    k.box('Handguard', (0, -.24, zb), (.042, .20, .040), 'Primary', .008)
    for side in (-1, 1):
        k.glow('HandguardGlow_%d' % side, (side * .0215, -.24, zb), (.002, .13, .006))
    side_vents(k, 'HandguardVent', -.19, .025, 5, zb + .008, .0215, (.002, .010, .014))
    k.cyl('Barrel', (0, -.47, zb), .0105, .31, 'Metal', n=22)
    k.cyl('BarrelSleeve', (0, -.40, zb), .015, .12, 'Secondary', n=22)
    muzzle_device(k, -.655, zb, .021, .09, rings=3)
    scope(k, -.04, .145, .24, .020, .032)
    for side in (-1, 1):
        k.box('BipodLeg_%d' % side, (side * .022, -.30, .026), (.008, .15, .008), 'Metal', .002)
        k.box('BipodMount_%d' % side, (side * .022, -.22, .036), (.008, .012, .020), 'Metal', .002)
    bolt = k.pivot('Anim_Bolt', (0, .05, .075))
    k.cyl('BoltBody', (0, .05, .075), .014, .09, 'Metal', n=20, parent=bolt)
    k.cyl('BoltStem', (.030, .06, .075), .005, .035, 'Metal', axis='x', n=12, bevel=.0008, parent=bolt)
    k.cyl('BoltKnob', (.052, .06, .075), .011, .016, 'Secondary', axis='x', n=16, bevel=.0012, parent=bolt)
    sniper_rifle_modules(k)
    k.socket('Socket_Hand', (0, 0, 0))
    k.socket('Socket_Muzzle', (0, -.70, zb))
    k.socket('Socket_SupportHand', (0, -.18, zb))
    k.socket('Socket_CenterOfMass', (0, -.05, .05))


# ----------------------------------------------------------------------------------------------------- 6 SMG
def smg(k):
    """Submachine gun: compact body, drum magazine with glowing hub, short shroud, folded stock, red-dot sight."""
    zb = .056
    grip(k, .090, .034, .044, ribs=3)
    k.box('Body', (0, -.05, .052), (.048, .24, .056), 'Primary', .010)
    k.box('BodyPlate', (0, -.05, .082), (.034, .22, .006), 'Secondary', .002)
    trigger_group(k, -.062, -.008, .010, .036)
    mag = k.pivot('Anim_Magazine', (0, -.125, .016))
    k.cyl('Drum', (0, -.125, -.030), .049, .044, 'Secondary', axis='x', n=32, bevel=.004, parent=mag)
    for side in (-1, 1):
        k.cyl('DrumCap_%d' % side, (side * .0245, -.125, -.030), .040, .006, 'Primary', axis='x', n=32, bevel=.002, parent=mag)
    k.cyl('DrumHub', (0, -.125, -.030), .018, .054, k.glow_material, axis='x', n=24, bevel=.001, parent=mag)
    k.box('DrumMount', (0, -.125, .016), (.040, .044, .018), 'Secondary', .004)
    k.box('BodyRear', (0, .095, .056), (.040, .05, .044), 'Secondary', .006)
    k.box('Stock', (0, .15, .056), (.036, .10, .040), 'Primary', .008)
    k.box('StockPad', (0, .205, .050), (.040, .012, .090), 'Detail', .003)
    for side in (-1, 1):
        k.box('StockStrut_%d' % side, (side * .022, .16, .036), (.006, .08, .012), 'Metal', .002)
    k.cyl('Shroud', (0, -.255, zb), .028, .16, 'Secondary', n=28, bevel=.003)
    side_vents(k, 'ShroudVent', -.23, .022, 4, zb + .026, 0.0, (.014, .008, .003))
    k.tube('ShroudRing_0', (0, -.205, zb), .0295, .024, .008, k.glow_material, n=28)
    k.tube('ShroudRing_1', (0, -.325, zb), .0295, .024, .008, k.glow_material, n=28)
    k.cyl('Barrel', (0, -.345, zb), .009, .06, 'Metal', n=18)
    muzzle_device(k, -.38, zb, .017, .05, rings=2)
    k.box('Sight', (0, -.02, .102), (.028, .060, .028), 'Secondary', .006)
    k.glow('SightGlow', (0, -.02, .1175), (.012, .04, .002))
    k.box('FrontPost', (0, -.17, .092), (.008, .012, .018), 'Metal', .002)
    bolt = k.pivot('Anim_Bolt', (0, 0, .060))
    k.box('BoltCover', (.0255, -.03, .060), (.006, .075, .022), 'Metal', .003, parent=bolt)
    k.cyl('BoltKnob', (.031, .00, .062), .007, .010, 'Secondary', axis='x', n=12, bevel=.001, parent=bolt)
    smg_modules(k, mag)
    k.socket('Socket_Hand', (0, 0, 0))
    k.socket('Socket_Muzzle', (0, -.407, zb))
    k.socket('Socket_SupportHand', (0, -.20, zb))
    k.socket('Socket_CenterOfMass', (0, -.05, .04))


# ------------------------------------------------------------------------------------------------ 7 fusion rifle
def fusion_rifle(k):
    """Fusion rifle: heavy body, exposed glowing core between two hinged fin shells, spinning coil ring (charges, then fires)."""
    zb = .075
    grip(k, .100, .038, .048, ribs=3)
    k.box('Body', (0, -.02, .062), (.056, .26, .060), 'Primary', .010)
    k.box('BodyDark', (0, -.02, .036), (.040, .20, .014), 'Secondary', .003)
    for side in (-1, 1):
        k.glow('BodyGlow_%d' % side, (side * .0285, -.02, .065), (.002, .16, .008))
    rail(k, 'TopRail', -.13, .06, .097, .020)
    trigger_group(k, -.066, -.008, .012, .040)
    stock(k, 'Stock', [(.10, .092), (.27, .105), (.335, .095), (.345, -.02), (.30, -.045), (.20, .005), (.10, .030)],
          .044, 'Detail', (.048, .014, .13), .352, .03)
    k.box('Handguard', (0, -.17, .060), (.052, .12, .046), 'Primary', .009)
    k.box('HandguardRail', (0, -.17, .033), (.022, .11, .008), 'Secondary', .002)
    k.cyl('Core', (0, -.38, zb), .022, .40, 'Secondary', n=28, bevel=.002)
    k.cyl('CoreGlow', (0, -.38, zb), .0245, .34, k.glow_material, n=28, bevel=.0008)
    for i, y in enumerate((-.205, -.57)):
        k.tube('CoreCollar_%d' % i, (0, y, zb), .036, .020, .028, 'Metal', n=28)
    k.tube('FrontRing', (0, -.585, zb), .040, .024, .014, 'Secondary', n=28)
    k.cyl('MuzzleCore', (0, -.598, zb), .012, .006, k.glow_material, n=20, bevel=.0006)
    fins = {1: k.pivot('Anim_FinL', (.034, -.235, zb)), -1: k.pivot('Anim_FinR', (-.034, -.235, zb))}
    for side in (-1, 1):
        fin = fins[side]
        k.box('Fin_%d' % side, (side * .045, -.40, zb), (.010, .34, .046), 'Primary', .006, parent=fin)
        k.box('FinEdge_%d' % side, (side * .052, -.40, zb), (.004, .30, .020), 'Secondary', .002, parent=fin)
        k.glow('FinGlow_%d' % side, (side * .0505, -.40, zb + .020), (.002, .26, .005), parent=fin)
    coil = k.pivot('Anim_Coil', (0, -.19, zb))
    k.tube('CoilRing', (0, -.19, zb), .041, .030, .022, 'Metal', n=32, parent=coil)
    for i in range(3):
        a = 2 * math.pi * i / 3
        k.glow('CoilCell_%d' % i, (.0415 * math.cos(a), -.19, zb + .0415 * math.sin(a)), (.008, .016, .008), parent=coil)
    k.box('SightPost', (0, -.12, .108), (.008, .012, .022), 'Metal', .002)
    cell = k.pivot('Anim_Magazine', (.024, .220, .040))
    fusion_rifle_modules(k, fins, cell)
    k.socket('Socket_Hand', (0, 0, 0))
    k.socket('Socket_Muzzle', (0, -.603, zb))
    k.socket('Socket_SupportHand', (0, -.17, .060))
    k.socket('Socket_CenterOfMass', (0, -.08, .06))


# ------------------------------------------------------------------------------------------------ 8 scout rifle
def scout_rifle(k):
    """Scout rifle: slim long-range rifle, thin handguard, slender barrel, small scope, bolt knob on the side."""
    zb = .072
    grip(k, .095, .034, .044, ribs=3)
    k.box('Receiver', (0, -.03, .060), (.040, .24, .040), 'Primary', .007)
    k.box('ReceiverTop', (0, -.03, .083), (.026, .22, .010), 'Secondary', .003)
    rail(k, 'TopRail', -.14, .06, .092, .016)
    k.box('MagWell', (0, -.065, .036), (.032, .050, .016), 'Secondary', .004)
    mag = k.pivot('Anim_Magazine', (0, -.066, .032))
    magazine(k, 'Magazine', [(-.088, .032), (-.044, .032), (-.044, -.045), (-.050, -.075), (-.090, -.075), (-.090, -.045)], .026, parent=mag)
    for side in (-1, 1):
        k.glow('MagWindow_%d' % side, (side * .0135, -.066, -.018), (.002, .016, .030), parent=mag)
    trigger_group(k, -.060, -.008, .012, .038)
    stock(k, 'Stock', [(.09, .090), (.24, .096), (.35, .088), (.37, .078), (.37, -.04), (.335, -.045), (.22, -.01), (.09, .03)],
          .036, 'Detail', (.040, .014, .13), .377, .02)
    k.box('Handguard', (0, -.25, zb), (.040, .26, .038), 'Primary', .008)
    k.box('HandguardUnder', (0, -.25, zb - .023), (.020, .24, .008), 'Secondary', .002)
    for side in (-1, 1):
        k.glow('HandguardGlow_%d' % side, (side * .0205, -.25, zb), (.002, .16, .005))
    side_vents(k, 'HandguardVent', -.17, .026, 7, zb + .006, .0205, (.002, .010, .012))
    k.cyl('Barrel', (0, -.50, zb), .0095, .22, 'Metal', n=20)
    muzzle_device(k, -.635, zb, .016, .05, rings=2)
    scope(k, -.04, .125, .16, .015, .024)
    bolt = k.pivot('Anim_Bolt', (0, 0, .066))
    k.box('BoltCover', (.0215, -.04, .066), (.006, .075, .020), 'Metal', .003, parent=bolt)
    k.cyl('BoltKnob', (.027, -.005, .068), .007, .010, 'Secondary', axis='x', n=12, bevel=.001, parent=bolt)
    scout_rifle_modules(k)
    k.socket('Socket_Hand', (0, 0, 0))
    k.socket('Socket_Muzzle', (0, -.662, zb))
    k.socket('Socket_SupportHand', (0, -.19, zb))
    k.socket('Socket_CenterOfMass', (0, -.06, .05))


# ---------------------------------------------------------------------------------------------- 9 rocket launcher
def rocket_launcher(k):
    """Rocket launcher: big launch tube with a visible warhead, rear exhaust, targeting module, foregrip bar, reload hatch."""
    zt = .095
    grip(k, .100, .040, .048, ribs=3)
    k.box('GripMount', (0, 0, .040), (.062, .10, .030), 'Secondary', .006)
    trigger_group(k, -.066, -.008, .014, .042)
    k.cyl('Tube', (0, -.20, zt), .062, .60, 'Primary', n=40, bevel=.004)
    k.tube('Exhaust', (0, .16, zt), .076, .054, .080, 'Secondary', n=40)
    k.cyl('ExhaustFlare', (0, .11, zt), .070, .040, 'Metal', n=40, bevel=.003)
    k.tube('MuzzleBand', (0, -.50, zt), .068, .046, .050, 'Secondary', n=40)
    k.cyl('Warhead', (0, -.455, zt), .045, .070, 'Metal', n=32, bevel=.003)
    k.cyl('WarheadTip', (0, -.495, zt), .022, .014, k.glow_material, n=24, bevel=.001)
    for i, y in enumerate((-.38, -.02)):
        k.cyl('TubeBand_%d' % i, (0, y, zt), .0665, .024, 'Secondary', n=40, bevel=.002)
    for i, y in enumerate((-.30, -.20, -.10)):
        k.tube('TubeGlow_%d' % i, (0, y, zt), .0645, .060, .008, k.glow_material, n=40)
    k.box('Targeting', (0, -.12, .182), (.044, .13, .040), 'Secondary', .008)
    k.box('TargetingLensFrame', (0, -.187, .183), (.034, .004, .030), 'Detail', .002)
    k.glow('TargetingGlow', (0, -.12, .2025), (.016, .08, .002))
    k.box('RearSight', (0, .02, .170), (.030, .030, .024), 'Secondary', .005)
    k.box('SightMount', (0, -.12, .158), (.030, .08, .012), 'Metal', .003)
    k.cyl('Foregrip', (0, -.28, .008), .021, .13, 'Detail', n=20, bevel=.002)
    for y in (-.34, -.22):
        k.box('ForegripStrut_%d' % int(-y * 100), (0, y, .034), (.030, .018, .050), 'Secondary', .004)
    loader = k.pivot('Anim_Magazine', (0, 0, 0))
    hatch = k.pivot('Anim_Hatch', (0, -.28, .1555), parent=loader)
    k.box('Hatch', (0, -.34, .1595), (.060, .12, .008), 'Primary', .003, parent=hatch)
    k.glow('HatchGlow', (0, -.34, .1645), (.030, .08, .002), parent=hatch)
    rocket_launcher_modules(k, hatch)
    k.socket('Socket_Hand', (0, 0, 0))
    k.socket('Socket_Muzzle', (0, -.535, zt))
    k.socket('Socket_SupportHand', (0, -.28, .008))
    k.socket('Socket_CenterOfMass', (0, -.1, .08))


# ---------------------------------------------------------------------------------------------- per-weapon modules
# Additions of 0.8.0 (Gunmetal) on top of the 0.7 bodies: sockets, pivots, clip and the grip/support parts are unchanged.
def pistol_modules(k, slide, mag):
    """Sidearm: compensator with accent, rear ammo readout on the slide, exposed side cell, slide panels, baseplate."""
    k.box('SlideCompensator', (0, -.137, .0785), (.026, .020, .009), 'Secondary', .002, parent=slide)
    accent(k, 'SlideCompensatorAccent', (0, -.137, .0837), (.014, .016, .0015), parent=slide)
    for side in (-1, 1):
        panel(k, 'SlidePanel_%d' % side, (side * .0182, -.072, .052), (.0025, .07, .010), 'Secondary', parent=slide)
    display(k, 'SlideDisplay', (0, .0582, .066), (.020, .0016, .013), 'y', bars=3, parent=slide)
    for i in range(3):
        k.box('SlideRib_%d' % i, (0, -.105 - i * .009, .0858), (.011, .0035, .0016), 'Detail', 0, parent=slide)
    energy_cell(k, 'FrameCell', (.0152, -.098, .033), .0058, .040)
    k.bolts('FrameBolt', [(.0152, -.03, .034), (.0152, -.128, .030)], radius=.0028, depth=.003)
    accent(k, 'HammerAccent', (0, .060, .0775), (.0105, .010, .0015))
    r = k.tilt(k.grip_tilt)
    y, z = along(k, 0, -.102 / 2 - .0125)
    accent(k, 'MagBaseplate', (0, y, z), (.036, .046, .005), rot=r, parent=mag)


def assault_rifle_modules(k, mag):
    """Assault rifle: ammo readouts (side, optic back), receiver panels, stock cell window, handguard fins, accent cap."""
    side_armor(k, 'UpperArmor', [(-.178, .077), (-.088, .077), (-.074, .097), (-.090, .108), (-.165, .108), (-.178, .097)], .025)
    side_armor(k, 'LowerArmor', [(-.093, .043), (-.052, .043), (-.040, .074), (-.093, .074)], .023, .0025, 'Metal')
    for side in (-1, 1):
        panel(k, 'ReceiverPanel_%d' % side, (side * .0262, .075, .092), (.0025, .058, .024))
    display(k, 'AmmoDisplay', (.0236, .042, .058), (.0016, .036, .018), 'x', bars=4)
    display(k, 'OpticDisplay', (0, .0184, .138), (.024, .0016, .016), 'y', bars=3)
    k.box('OpticHood', (0, -.060, .1595), (.038, .020, .007), 'Primary', .002)
    k.box('StockCellFrame', (.0205, .245, .050), (.002, .070, .026), 'Secondary', .0006)
    k.glow('StockCellWindow', (.0218, .245, .050), (.0012, .056, .014))
    k.bolts('StockBolt', [(.0215, .200, .050), (.0215, .290, .050)], radius=.0026, depth=.003)
    heat_sink(k, 'HandguardFin', (0, -.175, .1145), 5, .03, (.042, .006, .005))
    accent(k, 'HandguardCap', (0, -.3425, .085), (.060, .005, .056))
    accent(k, 'MagazineBase', (0, -.102, -.101), (.034, .044, .007), parent=mag)
    for side in (-1, 1):
        k.box('MuzzleFin_%d' % side, (side * .022, -.55, .085), (.006, .04, .014), 'Metal', .0015)
    k.cyl('ChargingConduit', (.026, -.110, .070), .0035, .075, 'Detail', n=10, bevel=.0005)


def pulse_rifle_modules(k):
    """Pulse rifle: side burst readout, twin rear energy cells, chassis heat sink, accent stripes, shroud cap."""
    side_armor(k, 'NoseArmor', [(-.195, .036), (-.135, .036), (-.124, .062), (-.140, .098), (-.190, .098)], .026)
    display(k, 'BurstDisplay', (.0286, -.045, .062), (.0016, .050, .020), 'x', bars=3)
    display(k, 'SightDisplay', (0, .0383, .137), (.018, .0016, .012), 'y', bars=3)
    for side in (-1, 1):
        energy_cell(k, 'StockCell_%d' % side, (side * .029, .245, .040), .009, .090)
        accent(k, 'ChassisAccent_%d' % side, (side * .0266, -.150, .030), (.002, .080, .006))
    heat_sink(k, 'ChassisFin', (0, .220, .1165), 5, .025, (.040, .006, .008))
    k.tube('ShroudCap', (0, -.192, .075), .034, .024, .012, 'Metal', n=32)
    panel(k, 'ChassisPlate', (.0275, .140, .080), (.0025, .07, .030))


def shotgun_modules(k):
    """Shotgun: side shell carrier with two shells, rear readout, receiver solar cell, shroud bands and rib, stock accent."""
    k.box('ShellCarrier', (.0250, .100, .052), (.004, .050, .036), 'Secondary', .001)
    for i, z in enumerate((.042, .062)):
        k.cyl('Shell_%d' % i, (.0305, .100, z), .0065, .040, 'Accent', n=14, bevel=.0008)
        k.cyl('ShellCap_%d' % i, (.0305, .1215, z), .0068, .004, 'Metal', n=14, bevel=.0004)
    display(k, 'ReceiverDisplay', (0, .0662, .084), (.030, .0016, .010), 'y', bars=2)
    energy_cell(k, 'ReceiverCell', (.031, -.105, .035), .007, .040)
    for i, y in enumerate((-.22, -.40)):
        k.tube('ShroudBand_%d' % i, (0, y, .070), .0345, .030, .012, 'Secondary', n=32)
    k.box('ShroudRib', (0, -.310, .1045), (.012, .26, .006), 'Secondary', .0015)
    accent(k, 'StockAccent', (.0245, .250, .030), (.002, .060, .030))
    for side in (-1, 1):
        panel(k, 'ReceiverPanel_%d' % side, (side * .0315, -.105, .074), (.0025, .036, .018))


def sniper_rifle_modules(k):
    """Sniper rifle: scope readout and side turret, sunshade, void side cell, sleeve fins, accents."""
    display(k, 'ScopeDisplay', (.0225, .015, .145), (.0016, .036, .012), 'x', bars=4)
    k.box('ScopeDisplayMount', (.0205, .015, .145), (.004, .030, .008), 'Secondary', .0008)
    k.cyl('ScopeTurretSide', (.0245, -.045, .145), .008, .010, 'Metal', axis='x', n=16, bevel=.001)
    k.tube('ScopeHood', (0, -.200, .145), .034, .031, .030, 'Primary', n=32)
    energy_cell(k, 'ReceiverCell', (.023, -.120, .062), .0075, .070)
    for i, y in enumerate((-.36, -.40, -.44)):
        k.tube('SleeveFin_%d' % i, (0, y, .068), .021, .015, .006, 'Metal', n=24)
    accent(k, 'HandguardAccent', (0, -.24, .0885), (.016, .12, .002))
    for side in (-1, 1):
        accent(k, 'StockAccent_%d' % side, (side * .0212, .33, .020), (.002, .050, .030))
        panel(k, 'ReceiverPanel_%d' % side, (side * .0228, .040, .066), (.0025, .06, .024))


def smg_modules(k, mag):
    """SMG: side readout, top arc cell, drum bolts, shroud spine, stock accent."""
    display(k, 'AmmoDisplay', (.0246, .046, .052), (.0016, .030, .016), 'x', bars=3)
    energy_cell(k, 'ArcCell', (.012, -.110, .0875), .006, .050)
    k.bolts('DrumBolt', [(.0278, -.125 + .028 * math.cos(a), -.030 + .028 * math.sin(a))
                         for a in (math.pi / 4, 3 * math.pi / 4, 5 * math.pi / 4, 7 * math.pi / 4)], radius=.003, depth=.003, parent=mag)
    k.box('ShroudSpine', (0, -.255, .0855), (.010, .14, .006), 'Secondary', .0015)
    accent(k, 'StockAccent', (0, .150, .0765), (.020, .060, .002))
    for side in (-1, 1):
        panel(k, 'BodyPanel_%d' % side, (side * .0245, -.125, .062), (.0025, .06, .020))


def fusion_rifle_modules(k, fins, cell):
    """Fusion rifle: side charge readout, side heat sinks, rear power cell, accent fin tips, core braces."""
    display(k, 'ChargeDisplay', (.0286, .040, .080), (.0016, .045, .014), 'x', bars=5)
    for side in (-1, 1):
        heat_sink(k, 'HeatVent_%d' % side, (side * .0300, -.020, .045), 4, .012, (.004, .004, .020))
        accent(k, 'FinAccent_%d' % side, (side * .045, -.560, .075), (.0112, .020, .047), parent=fins[side])
        k.box('CoreBrace_%d' % side, (side * .022, -.205, .075), (.010, .022, .030), 'Secondary', .002)
    energy_cell(k, 'PowerCell', (.024, .220, .040), .008, .080, parent=cell)
    panel(k, 'BodyPlate', (.0290, -.090, .080), (.0025, .07, .018))


def scout_rifle_modules(k):
    """Scout rifle: scope readout, receiver panels, handguard fins, stock cell, muzzle accent ring, barrel spine."""
    display(k, 'ScopeDisplay', (.0168, -.005, .125), (.0016, .030, .010), 'x', bars=3)
    for side in (-1, 1):
        panel(k, 'ReceiverPanel_%d' % side, (side * .0212, .040, .060), (.0025, .060, .022))
    heat_sink(k, 'HandguardFin', (0, -.300, .0935), 4, .02, (.026, .005, .005))
    energy_cell(k, 'StockCell', (.019, .220, .050), .007, .070)
    k.tube('MuzzleAccent', (0, -.604, .072), .0175, .009, .008, 'Accent', n=24)
    k.box('BarrelSpine', (0, -.47, .0835), (.008, .14, .005), 'Secondary', .0015)
    accent(k, 'StockAccent', (.0185, .300, .030), (.002, .050, .028))


def rocket_launcher_modules(k, hatch):
    """Rocket launcher: lock-on screen, antenna, tube panels, side solar cell, exhaust struts, warning accents."""
    display(k, 'TargetingDisplay', (0, -.0542, .182), (.032, .0016, .024), 'y', bars=4)
    k.cyl('Antenna', (.020, -.070, .216), .002, .030, 'Metal', axis='z', n=8, bevel=.0003)
    for side in (-1, 1):
        panel(k, 'TubePanel_%d' % side, (side * .0640, -.150, .095), (.004, .080, .050))
        accent(k, 'HatchAccent_%d' % side, (side * .024, -.34, .1645), (.006, .10, .002), parent=hatch)
    energy_cell(k, 'SideCell', (.058, .050, .060), .010, .080)
    for i in range(4):
        a = i * math.pi / 2
        k.box('ExhaustStrut_%d' % i, (.070 * math.cos(a), .180, .095 + .070 * math.sin(a)), (.008, .02, .008), 'Metal', .001)
    k.tube('MuzzleAccent', (0, -.470, .095), .0695, .062, .010, 'Accent', n=40)


def slide_keys(*pairs):
    return [(1, 0)] + list(pairs) + [(97, 0)]


def sight_rule(kind, parts, mode, tool_scale, above=0.0):
    """Line of sight for sight.py in world-model metres: ``above`` (ads.eye_above_m) is a first-person value, divided by
    the weapon's tool_scale (data/viewmodels.json)."""
    return {'kind': kind, 'parts': list(parts), 'mode': mode, 'above_m': above / tool_scale}


DESIGNS = {
    'pistol': {
        'asset': 'CubeEscape_Pistol', 'clip': 'Pistol_Use', 'class': 'sidearm', 'element': 'kinetic', 'grip_tilt_degrees': 14,
        'grip_part': 'Grip', 'support_part': 'Grip', 'view_center': (0, -.04, .02), 'view_scale': .50,
        'trigger': 'FireAction', 'build': pistol,
        'fire_frame': 14, 'sight': sight_rule('iron', ('FrontSight', 'RearSight_-1', 'RearSight_1'), 'top', 1.35, .012),
        'use_clip': [{'node': 'Anim_Slide', 'channel': 'location', 'axis': 1,
                      'keys': slide_keys((14, 0), (16, .034), (24, .004), (30, 0))}],
    },
    'assault_rifle': {
        'asset': 'CubeEscape_AssaultRifle', 'clip': 'AssaultRifle_Use', 'class': 'assault_rifle', 'element': 'kinetic',
        'grip_tilt_degrees': 16, 'grip_part': 'Grip', 'support_part': 'Handguard',
        'view_center': (0, -.12, .05), 'view_scale': 1.15, 'trigger': 'FireAction', 'build': assault_rifle,
        'fire_frame': 14, 'sight': sight_rule('reflex', ('Optic', 'OpticGlow', 'OpticHood'), 'top', .72, .004),
        'use_clip': [{'node': 'Anim_Bolt', 'channel': 'location', 'axis': 1,
                      'keys': slide_keys((14, 0), (16, .05), (22, .006), (28, 0))}],
    },
    'pulse_rifle': {
        'asset': 'CubeEscape_PulseRifle', 'clip': 'PulseRifle_Use', 'class': 'pulse_rifle', 'element': 'energy',
        'grip_tilt_degrees': 14, 'grip_part': 'Grip', 'support_part': 'Shroud',
        'view_center': (0, -.09, .05), 'view_scale': .95, 'trigger': 'FireAction', 'build': pulse_rifle,
        'fire_frame': 14, 'sight': sight_rule('holo', ('Sight', 'SightGlow'), 'top', .744, .004),
        'use_clip': [{'node': 'Anim_Cell', 'channel': 'location', 'axis': 1,
                      'keys': slide_keys((14, 0), (15, .026), (17, 0), (18, 0), (19, .026), (21, 0), (22, 0), (23, .026), (25, 0))}],
    },
    'shotgun': {
        'asset': 'CubeEscape_Shotgun', 'clip': 'Shotgun_Use', 'class': 'shotgun', 'element': 'solar', 'grip_tilt_degrees': 15,
        'grip_part': 'Grip', 'support_part': 'ForeEnd', 'view_center': (0, -.06, .05), 'view_scale': 1.05,
        'trigger': 'FireAction', 'build': shotgun,
        'fire_frame': 14, 'sight': sight_rule('iron', ('FrontBead',), 'top', .72, .006),
        'use_clip': [{'node': 'Anim_Bolt', 'channel': 'location', 'axis': 1,
                      'keys': slide_keys((36, 0), (46, .07), (56, 0))}],
    },
    'sniper_rifle': {
        'asset': 'CubeEscape_SniperRifle', 'clip': 'SniperRifle_Use', 'class': 'sniper_rifle', 'element': 'void',
        'grip_tilt_degrees': 12, 'grip_part': 'Grip', 'support_part': 'Handguard',
        'view_center': (0, -.14, .05), 'view_scale': 1.45, 'trigger': 'FireAction', 'build': sniper_rifle,
        'fire_frame': 14, 'sight': sight_rule('scope', ('ScopeTube',), 'center', .624),
        'use_clip': [{'node': 'Anim_Bolt', 'channel': 'rotation', 'axis': 1,
                      'keys': slide_keys((38, 0), (46, -75), (68, -75), (76, 0))},
                     {'node': 'Anim_Bolt', 'channel': 'location', 'axis': 1,
                      'keys': slide_keys((46, 0), (56, .085), (66, 0))}],
    },
    'smg': {
        'asset': 'CubeEscape_SubmachineGun', 'clip': 'SubmachineGun_Use', 'class': 'smg', 'element': 'arc',
        'grip_tilt_degrees': 18, 'grip_part': 'Grip', 'support_part': 'Shroud',
        'view_center': (0, -.08, .03), 'view_scale': .75, 'trigger': 'FireAction', 'build': smg,
        'fire_frame': 14, 'sight': sight_rule('reflex', ('Sight', 'SightGlow'), 'top', 1.02, .012),
        'use_clip': [{'node': 'Anim_Bolt', 'channel': 'location', 'axis': 1,
                      'keys': slide_keys((14, 0), (15, .032), (17, 0), (18, 0), (19, .032), (21, 0), (22, 0), (23, .032), (25, 0))}],
    },
    'fusion_rifle': {
        'asset': 'CubeEscape_FusionRifle', 'clip': 'FusionRifle_Use', 'class': 'fusion_rifle', 'element': 'energy',
        'grip_tilt_degrees': 14, 'grip_part': 'Grip', 'support_part': 'Handguard',
        'view_center': (0, -.13, .05), 'view_scale': 1.15, 'trigger': 'ChargeFireAction', 'build': fusion_rifle,
        'fire_frame': 46, 'sight': sight_rule('energy', ('SightPost',), 'top', .672, .008),
        'use_clip': [{'node': 'Anim_FinL', 'channel': 'rotation', 'axis': 2, 'keys': slide_keys((10, 0), (44, 9), (47, 0))},
                     {'node': 'Anim_FinR', 'channel': 'rotation', 'axis': 2, 'keys': slide_keys((10, 0), (44, -9), (47, 0))},
                     {'node': 'Anim_Coil', 'channel': 'rotation', 'axis': 1, 'keys': slide_keys((10, 0), (46, 720))}],
    },
    'scout_rifle': {
        'asset': 'CubeEscape_ScoutRifle', 'clip': 'ScoutRifle_Use', 'class': 'scout_rifle', 'element': 'kinetic',
        'grip_tilt_degrees': 12, 'grip_part': 'Grip', 'support_part': 'Handguard',
        'view_center': (0, -.14, .05), 'view_scale': 1.35, 'trigger': 'FireAction', 'build': scout_rifle,
        'fire_frame': 14, 'sight': sight_rule('scope', ('ScopeTube',), 'center', .648),
        'use_clip': [{'node': 'Anim_Bolt', 'channel': 'location', 'axis': 1,
                      'keys': slide_keys((14, 0), (16, .045), (24, .005), (30, 0))}],
    },
    'rocket_launcher': {
        'asset': 'CubeEscape_RocketLauncher', 'clip': 'RocketLauncher_Use', 'class': 'rocket_launcher', 'element': 'solar',
        'grip_tilt_degrees': 14, 'grip_part': 'Grip', 'support_part': 'Foregrip',
        'view_center': (0, -.17, .07), 'view_scale': 1.20, 'trigger': 'FireAction', 'build': rocket_launcher,
        'fire_frame': 14, 'sight': sight_rule('iron', ('Targeting', 'TargetingGlow'), 'top', .6, .004),
        'use_clip': [{'node': 'Anim_Hatch', 'channel': 'rotation', 'axis': 0, 'keys': slide_keys((30, 0), (40, -30), (62, -30), (72, 0))}],
    },
}
