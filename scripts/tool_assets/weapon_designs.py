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

``concept`` (Toolgen 0.18, TG-A): the geometry comes from a formgen concept sheet in data/concepts/ (concept_spec.py,
concept_kit.py) instead of ``build``; part names are those of the spec (``SM_PG_<Label>_<id>``), the sockets come from the
spec and Socket_Reticle is added. ``DESIGN_PICK`` lists the weapons that use a concept.
"""
import importlib
import math
import re


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
    # 0.12.0: 1 mm proud of the objective's front face (coplanar faces z-fought)
    k.cyl('ScopeLens', (0, y - length / 2 - length * .30 / 2 + .011, z), lens * .86, .004, k.glow_material, n=24, bevel=.0005)
    k.cyl('ScopeTurret', (0, y, z + radius + .006), radius * .55, .016, 'Metal', axis='z', n=16, bevel=.001)
    for dy in (-length * .28, length * .24):
        k.box('ScopeMount_%d' % int(dy * 1000), (0, y + dy, z - radius - .012), (.020, .026, .030), 'Metal', .003)


def muzzle_device(k, y, z, radius, length, rings=2):
    """Muzzle brake with an element-glow ring and a metal end ring."""
    k.cyl('MuzzleBrake', (0, y, z), radius, length, 'Secondary', n=28)
    k.tube('MuzzleGlow', (0, y - length * .18, z), radius + .0015, radius * .55, .006, k.glow_material, n=28)
    # 0.12.0: 1 mm ahead of the brake's front face (coplanar faces z-fought in the Mac viewer)
    k.tube('MuzzleRing', (0, y - length / 2 + .003, z), radius + .002, radius * .5, .008, 'Metal', n=28)
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
    """Pistol (0.27): concept KG01, variant G (data/concepts/KG01.geo.json) without its reflex sight VS01 and rail p12
    (named correction omit_parts: iron sights from formgen, user decision 24.10.2026); slide p06 and its rib p09 under
    Anim_Slide, magazine base p01 under Anim_Magazine; cup grip (no support part, Socket_SupportHand a named correction)."""
    concept_build(k, 'pistol')


# ----------------------------------------------------------------------------------------------- 2 assault rifle
def concept_build(k, key):
    """A weapon from its formgen concept sheet (Toolgen 0.18, TG-A): the kit builds the sheet's meshes, pivots (the Use
    clip's nodes; nodes without a part stay empty) and sockets."""
    spec = DESIGNS[key]
    return k.concept(spec['concept'], sorted({move['node'] for move in spec['use_clip']}))


def assault_rifle(k):
    """Assault rifle (0.18): concept KG02 "Kantenläufer", variant G (data/concepts/KG02.geo.json), holo sight VS02 open."""
    concept_build(k, 'assault_rifle')


# ------------------------------------------------------------------------------------------------ 3 pulse rifle


def pulse_rifle(k):
    """Pulse rifle (0.24): concept KG03, variant G (data/concepts/KG03.geo.json), holo sight VS02 open, foregrip p40,
    pulse cube p17 under Anim_Cell, energy cell p18 under Anim_EnergyCell."""
    concept_build(k, 'pulse_rifle')


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
        # 0.12.0: 0.8 mm proud of the vent slots (coplanar faces z-fought)
        k.glow('HandguardGlow_%d' % side, (side * .0223, -.24, zb), (.002, .13, .006))
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
    """Submachine gun (0.24): concept KG06, variant G (data/concepts/KG06.geo.json), reflex sight VS06 (closed frame, open
    window), grip magazine p11 under Anim_Magazine; KG06 draws no bolt, Anim_Bolt stays an empty pivot."""
    concept_build(k, 'smg')


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
    k.box('SightPost', (0, -.1206, .108), (.008, .012, .022), 'Metal', .002)   # 0.12.0: rear face 0.6 mm off the rail slot's
    cell = k.pivot('Anim_Magazine', (.024, .220, .040))
    fusion_rifle_modules(k, fins, cell)
    k.socket('Socket_Hand', (0, 0, 0))
    k.socket('Socket_Muzzle', (0, -.603, zb))
    k.socket('Socket_SupportHand', (0, -.17, .060))
    k.socket('Socket_CenterOfMass', (0, -.08, .06))


# ------------------------------------------------------------------------------------------------ 8 trace rifle
def trace_rifle(k):
    """Trace rifle: slim long-range rifle, thin handguard, slender barrel, small scope, bolt knob on the side."""
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
        # 0.12.0: 0.8 mm proud of the vent slots (coplanar faces z-fought)
        k.glow('HandguardGlow_%d' % side, (side * .0213, -.25, zb), (.002, .16, .005))
    side_vents(k, 'HandguardVent', -.17, .026, 7, zb + .006, .0205, (.002, .010, .012))
    k.cyl('Barrel', (0, -.50, zb), .0095, .22, 'Metal', n=20)
    muzzle_device(k, -.635, zb, .016, .05, rings=2)
    scope(k, -.04, .125, .16, .015, .024)
    bolt = k.pivot('Anim_Bolt', (0, 0, .066))
    k.box('BoltCover', (.0215, -.04, .066), (.006, .075, .020), 'Metal', .003, parent=bolt)
    k.cyl('BoltKnob', (.027, -.005, .068), .007, .010, 'Secondary', axis='x', n=12, bevel=.001, parent=bolt)
    trace_rifle_modules(k)
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


# ------------------------------------------------------------------------------------------------ 10 scout rifle
def scout_rifle(k):
    """Scout rifle (0.24, new tool; the id scout_rifle named the trace rifle until 0.16): concept KG11, variant G
    (data/concepts/KG11.geo.json), precision scope VS03 (glass not built), box magazine p11 under Anim_Magazine, left
    charging handle p05 under Anim_Bolt."""
    concept_build(k, 'scout_rifle')


# ---------------------------------------------------------------------------------------------- per-weapon modules
# Additions of 0.8.0 (Gunmetal) on top of the 0.7 bodies: sockets, pivots, clip and the grip/support parts are unchanged.
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
    # 0.12.0: proud of the stock inset (its face lies at x = .0255): coplanar faces z-fought in the viewer (Mac, shotgun/fps)
    accent(k, 'StockAccent', (.0262, .250, .030), (.002, .060, .030))
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


def fusion_rifle_modules(k, fins, cell):
    """Fusion rifle: side charge readout, side heat sinks, rear power cell, accent fin tips, core braces."""
    display(k, 'ChargeDisplay', (.0286, .040, .080), (.0016, .045, .014), 'x', bars=5)
    for side in (-1, 1):
        heat_sink(k, 'HeatVent_%d' % side, (side * .0300, -.020, .045), 4, .012, (.004, .004, .020))
        accent(k, 'FinAccent_%d' % side, (side * .045, -.5608, .075), (.0112, .020, .047), parent=fins[side])   # 0.12.0: 0.8 mm proud of the fin's front face
        k.box('CoreBrace_%d' % side, (side * .022, -.205, .075), (.010, .022, .030), 'Secondary', .002)
    energy_cell(k, 'PowerCell', (.024, .220, .040), .008, .080, parent=cell)
    panel(k, 'BodyPlate', (.0290, -.090, .080), (.0025, .07, .018))


def trace_rifle_modules(k):
    """Trace rifle: scope readout, receiver panels, handguard fins, stock cell, muzzle accent ring, barrel spine."""
    display(k, 'ScopeDisplay', (.0168, -.005, .125), (.0016, .030, .010), 'x', bars=3)
    for side in (-1, 1):
        panel(k, 'ReceiverPanel_%d' % side, (side * .0212, .040, .060), (.0025, .060, .022))
    heat_sink(k, 'HandguardFin', (0, -.300, .0935), 4, .02, (.026, .005, .005))
    energy_cell(k, 'StockCell', (.019, .220, .050), .007, .070)
    k.tube('MuzzleAccent', (0, -.604, .072), .0175, .009, .008, 'Accent', n=24)
    k.box('BarrelSpine', (0, -.47, .0835), (.008, .14, .005), 'Secondary', .0015)
    # 0.12.0: 0.8 mm proud of the stock inset (its face lies at x = .0195; coplanar faces z-fought)
    accent(k, 'StockAccent', (.0193, .300, .030), (.002, .050, .028))


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


def sight_rule(kind, parts, mode, tool_scale, above=0.0, rear_parts=(), eye_part=None):
    """Line of sight for sight.py in world-model metres: ``above`` (ads.eye_above_m) is a first-person value, divided by
    the weapon's tool_scale (data/viewmodels.json). 0.24, concept sights: ``rear_parts`` end the line at their rear face
    (the rear ring or eyecup of the sheet's Socket_Sight) without moving it off the window, ``eye_part`` puts Socket_Eye
    of a scope without its eye glass at the front face of that part instead of the centre of ScopeEyeLens."""
    rule = {'kind': kind, 'parts': list(parts), 'mode': mode, 'above_m': above / tool_scale}
    if rear_parts:
        rule['rear_parts'] = list(rear_parts)
    if eye_part:
        rule['eye_part'] = eye_part
    return rule


DESIGNS = {
    'pistol': {
        'asset': 'CubeEscape_Pistol', 'clip': 'Pistol_Use', 'class': 'sidearm', 'element': 'solar',
        # cup grip: the left hand wraps the right one (no support part on the sheet, Socket_SupportHand on the grip's left)
        'concept': 'KG01.geo.json', 'grip_tilt_degrees': 6.39, 'grip_part': 'Griff_p00', 'support_part': 'Griff_p00',
        'view_center': (0, -.08, .02), 'view_scale': .55, 'trigger': 'FireAction', 'build': pistol,
        # provisional line until formgen's iron sights (KG01 patch): Toolgen's iron rule (eye_above_m over the top) over the
        # slide p06 and its rib p09, ending at the slide's rear face where the rear sight will sit; no sight geometry. Contract
        # 5: first-person metres are the game picture, the model scaled by tool_scale 1.5 x rig scale 1.4 (data/ego_arms.json)
        'fire_frame': 14, 'sight': sight_rule('iron', ('Schlitten_p06', 'Part_p09'), 'top', 2.1, .012),
        # semi-automatic: the slide p06 (and its rib p09) runs back 24 mm at the shot and forward again
        'use_clip': [{'node': 'Anim_Slide', 'channel': 'location', 'axis': 1,
                      'keys': slide_keys((14, 0), (15, .024), (17, .006), (18, 0))}],
    },
    'assault_rifle': {
        'asset': 'CubeEscape_AssaultRifle', 'clip': 'AssaultRifle_Use', 'class': 'assault_rifle', 'element': 'arc',
        'concept': 'KG02.geo.json', 'grip_tilt_degrees': 10.27, 'grip_part': 'Griff_p03', 'support_part': 'Handschutz_p11',
        'view_center': (0, -.15, .08), 'view_scale': 1.15, 'trigger': 'FireAction', 'build': assault_rifle,
        # holo sight with an open window (user decision 20.10.2026, glass way A): the line runs through the window frame
        'fire_frame': 14, 'sight': sight_rule('holo', ('Rahmen_p24',), 'center', .72),
        # Anim_Bolt: KG02 draws no bolt (formgen moving_parts parts null, question in cubeescape-rules#1); the node stays
        # (contract), an empty pivot until formgen names a part
        'use_clip': [{'node': 'Anim_Bolt', 'channel': 'location', 'axis': 1,
                      'keys': slide_keys((14, 0), (16, .05), (22, .006), (28, 0))}],
    },
    'pulse_rifle': {
        'asset': 'CubeEscape_PulseRifle', 'clip': 'PulseRifle_Use', 'class': 'pulse_rifle', 'element': 'void',
        'concept': 'KG03.geo.json', 'grip_tilt_degrees': 9.48, 'grip_part': 'Griff_p02', 'support_part': 'Vordergriff_p40',
        'view_center': (0, -.17, .09), 'view_scale': 1.05, 'trigger': 'FireAction', 'build': pulse_rifle,
        # holo sight VS02 with an open window like KG02 (glass way A): the line runs through the window frame
        'fire_frame': 14, 'sight': sight_rule('holo', ('Rahmen_p32',), 'center', .744),
        # the pulse cube p17 times the burst on its axles (sheet: three pulses per trigger pull), one stroke per pulse
        'use_clip': [{'node': 'Anim_Cell', 'channel': 'location', 'axis': 1,
                      'keys': slide_keys((14, 0), (15, .012), (17, 0), (18, 0), (19, .012), (21, 0), (22, 0), (23, .012), (25, 0))}],
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
        'asset': 'CubeEscape_SniperRifle', 'clip': 'SniperRifle_Use', 'class': 'sniper_rifle', 'element': 'energy',
        'grip_tilt_degrees': 12, 'grip_part': 'Grip', 'support_part': 'Handguard',
        'view_center': (0, -.14, .05), 'view_scale': 1.45, 'trigger': 'FireAction', 'build': sniper_rifle,
        'fire_frame': 14, 'sight': sight_rule('scope', ('ScopeTube',), 'center', .624),
        'use_clip': [{'node': 'Anim_Bolt', 'channel': 'rotation', 'axis': 1,
                      'keys': slide_keys((38, 0), (46, -75), (68, -75), (76, 0))},
                     {'node': 'Anim_Bolt', 'channel': 'location', 'axis': 1,
                      'keys': slide_keys((46, 0), (56, .085), (66, 0))}],
    },
    'smg': {
        'asset': 'CubeEscape_SubmachineGun', 'clip': 'SubmachineGun_Use', 'class': 'smg', 'element': 'energy',
        # support: the unlabelled foregrip p09 under the shroud (named correction of Socket_SupportHand, corrections.json)
        'concept': 'KG06.geo.json', 'grip_tilt_degrees': 6.71, 'grip_part': 'Griff_p10', 'support_part': 'Part_p09',
        'view_center': (0, -.07, .07), 'view_scale': .80, 'trigger': 'FireAction', 'build': smg,
        # reflex sight VS06: closed frame, open window (glass way A); the line runs through the window frame and ends at
        # the rear ring p29 (the sheet's Socket_Sight)
        'fire_frame': 14, 'sight': sight_rule('reflex', ('Rahmen_p25',), 'center', 1.02, rear_parts=('Rueckring_p29',)),
        # Anim_Bolt: KG06 draws no bolt (moving_parts parts null, "Mechanik im Gehäuse nicht gezeichnet"); the node stays
        # (contract) as an empty pivot, like KG02 before formgen added its charging handle. 0.24: the visible motion is the
        # trigger p12 under Anim_Trigger (concept_spec.PART_NODES), pulled 6 mm at the shot and let go
        'use_clip': [{'node': 'Anim_Bolt', 'channel': 'location', 'axis': 1,
                      'keys': slide_keys((14, 0), (15, .032), (17, 0), (18, 0), (19, .032), (21, 0), (22, 0), (23, .032), (25, 0))},
                     {'node': 'Anim_Trigger', 'channel': 'location', 'axis': 1,
                      # at rest until frame 13 (the ego Fire clips start there: first_person.clip_keys replays the stroke
                      # with every shot only for a part at rest at that frame)
                      'keys': slide_keys((13, 0), (14, .006), (24, .006), (28, 0))}],
    },
    'fusion_rifle': {
        'asset': 'CubeEscape_FusionRifle', 'clip': 'FusionRifle_Use', 'class': 'fusion_rifle', 'element': 'void',
        'grip_tilt_degrees': 14, 'grip_part': 'Grip', 'support_part': 'Handguard',
        'view_center': (0, -.13, .05), 'view_scale': 1.15, 'trigger': 'ChargeFireAction', 'build': fusion_rifle,
        'fire_frame': 46, 'sight': sight_rule('energy', ('SightPost',), 'top', .672, .008),
        'use_clip': [{'node': 'Anim_FinL', 'channel': 'rotation', 'axis': 2, 'keys': slide_keys((10, 0), (44, 9), (47, 0))},
                     {'node': 'Anim_FinR', 'channel': 'rotation', 'axis': 2, 'keys': slide_keys((10, 0), (44, -9), (47, 0))},
                     {'node': 'Anim_Coil', 'channel': 'rotation', 'axis': 1, 'keys': slide_keys((10, 0), (46, 720))}],
    },
    'trace_rifle': {
        'asset': 'CubeEscape_TraceRifle', 'clip': 'TraceRifle_Use', 'class': 'trace_rifle', 'element': 'arc',
        'grip_tilt_degrees': 12, 'grip_part': 'Grip', 'support_part': 'Handguard',
        'view_center': (0, -.14, .05), 'view_scale': 1.35, 'trigger': 'FireAction', 'build': trace_rifle,
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
    # 0.24: new tool (KG11); the id scout_rifle named the trace rifle until 0.16, its old asset/clip names stay with the
    # trace rifle's renamed_from map, so this design takes CubeEscape_Scout / Scout_ (user decision 22.10.2026)
    'scout_rifle': {
        'asset': 'CubeEscape_Scout', 'clip': 'Scout_Use', 'class': 'scout_rifle', 'element': 'energy',
        'concept': 'KG11.geo.json', 'grip_tilt_degrees': 8.04, 'grip_part': 'Griff_p06', 'support_part': 'Handschutz_p13',
        'view_center': (0, -.21, .10), 'view_scale': 1.30, 'trigger': 'FireAction', 'build': scout_rifle,
        # precision scope VS03, glass not built (glass way A): the line runs along the tube's axis to the eyecup p45 (the
        # sheet's Socket_Sight); Socket_Eye sits where the omitted eye glass p50 was (front face of the eyecup; spec
        # Socket_Eye 0.75 mm further ahead)
        'fire_frame': 14, 'sight': sight_rule('scope', ('Gehaeuse_p21',), 'center', .66, rear_parts=('Augenmuschel_p45',),
                                              eye_part='Augenmuschel_p45'),
        # semi-automatic: the bolt runs back in the housing, the left charging handle p05 shows the stroke (like KG02,
        # 50 mm); 55 mm so the robot variant, squashed to slope 0.16 between grip and magazine, still moves it 8.6 mm (with
        # 35 mm the robot game model showed 26 changed pixels in the viewer test, below its 30)
        'use_clip': [{'node': 'Anim_Bolt', 'channel': 'location', 'axis': 1,
                      'keys': slide_keys((14, 0), (16, .055), (22, .006), (28, 0))}],
    },
}


# Weapons built from a formgen concept sheet (Toolgen 0.18, TG-A; formgen plan decision 1: variant G): tool id -> sheet.
DESIGN_PICK = {key: spec['concept'].removesuffix('.geo.json') for key, spec in DESIGNS.items() if spec.get('concept')}


def decal(part, face, rect, image, channel, rotation=0):
    """Decal anchor (toolgen/decals.py): ``part`` source part (without SM_PG_), ``face`` the box face it is projected on
    (+x is the side the first-person camera sees), ``rect`` (u0, v0, u1, v1) as fractions of the part's bounding box on that
    face (u to the right and v up, seen from outside), ``image`` an id of data/decals.json, ``channel`` the weight channel
    its texels take (Emission glows), ``rotation`` 0/90/180/270 degrees."""
    return {'part': part, 'face': face, 'rect': rect, 'image': image, 'channel': channel, 'rotation': rotation}


# Decals of the concept sheet "Waffen Texturen 1-9" (Toolgen 0.13 Enamel): baked into the weight maps by surface_bake.py.
# A weapon built from a formgen concept sheet has none here: the sheet's own decals are its mask regions (0.23 Livery,
# surface_bake.design_anchors; the assault rifle's two 0.13 decals on Gehaeuse_p09/Handschutz_p11 went into KG02's 63; 0.24: the
# pulse rifle's and the SMG's into the 11 of KG03 and the 54 of KG06).
DECALS = {
    'shotgun': [decal('SidePlate_1', '+x', (.667, .31, .8, .69), 'warning_triangle', 'Accent'),
                decal('BarrelShroud', '+x', (.033, .175, .167, .41), 'hazard_stripes', 'Accent')],
    'sniper_rifle': [decal('Receiver', '+x', (.233, .348, .333, .63), 'serial_s07', 'Accent')],
    'fusion_rifle': [decal('Body', '+x', (.577, .217, .654, .55), 'research', 'Emission'),
                     decal('Handguard', '+x', (.25, .37, .5, .63), 'fusion_px7', 'Secondary')],
    'trace_rifle': [decal('Handguard', '+x', (.077, .34, .231, .66), 'tech_lines', 'Energy')],
    'rocket_launcher': [decal('Tube', '+x', (.70, .3, .783, .7), 'warning_triangle', 'Accent'),
                        decal('Tube', '+x', (.033, .41, .133, .59), 'hazard_stripes', 'Accent')],
}


def decal_anchors(key):
    """The decal anchors surface_bake.py writes into a weapon's weight maps: for a weapon built from a concept sheet the
    sheet's decals as mask regions (0.23 Livery, stage B; concept_spec.decal_regions), then its DECALS."""
    anchors = list(DECALS.get(key, []))
    if DESIGNS.get(key, {}).get('concept'):
        concept_spec = concepts()
        sheet = concept_spec.load(DESIGNS[key]['concept'])
        anchors = concept_spec.decal_regions(sheet, concept_spec.plan(sheet)[0]) + anchors
    return anchors


def palettes(key):
    """The colour palettes of the weapon's concept sheet (0.23, weapon spec), [] for a weapon without one."""
    return concepts().palettes(DESIGN_PICK[key]) if key in DESIGN_PICK else []


def concepts():
    """concept_spec, imported on use: an import statement would put concept_spec.py into the cache key of every weapon's
    stages (generate_tools.concept_sources adds it for the weapons built from a sheet; judge finding 22.10.2026)."""
    return importlib.import_module('concept_spec')


# ------------------------------------------------------------------------------------ robot variant (Toolgen 0.14 Fieldfit)
# Cube Escape's robot (1.50 m, shoulder joints 0.82 m high and 0.56 m apart, arm 0.42 m, fist 0.09 m, chest front 0.18 m
# ahead of the body centre; measured in Cube Escape 0.82 "Sidearm") holds the world model in its hand. The life-size
# rifles are too long behind the grip and their handguard is out of reach of the support hand, and scaling alone cannot fix
# that (CE 0.82 findings). The robot variant <asset>_Robot is the same design, deformed after the build:
#
# * x and z scale by ``cross`` about Socket_Hand (the silhouette ~1.5 times stronger: barrel >= 3 cm, housing >= 8 cm high);
# * y (the bore) maps piecewise linearly through ``knots`` [(life y, robot y), ...]: the stock is pressed against the
#   grip (end at most 0.12 m behind Socket_Hand), the grip zone keeps the slope ``cross`` (so the grip tilt, a contract
#   value of the hold block, stays exact), and the overall length is the CE "length in the hand" (heldScale 1.0 after);
# * Socket_SupportHand moves to ``support`` (life metres, on ``support_part``) before the deformation: at most 0.10 m
#   ahead of Socket_Hand, at the magazine well or the front of the housing, about level with the grip.
#
# Everything else (parts, names, sockets, sight rule, Use clip, decals, recipes) is the life-size design, so later changes
# of a design reach both models. A monotonic map keeps parts that were apart apart (no new intersections). ``body`` and
# ``barrel`` name the parts whose robot height / diameter the tests hold against the minimums.
ROBOT_SUFFIX = '_Robot'
ROBOT_LIMITS = {'support_ahead_m': .10, 'stock_behind_m': .12, 'barrel_m': .03, 'body_m': .08, 'length_tolerance_m': .005}
GRIP_ZONE = .04        # life metres around Socket_Hand that keep the slope ``cross`` (grip, tail and cap)
# Energy cells (energy_cell: <name>Core, <name>Cap_<i>, <name>Cage_<i>) are pressed along the bore at most to this slope, about
# their common centre: in a squashed stock their 2-3 mm steps between core, caps and cage would shrink below 0.5 mm and
# z-fight (viewer determinism, trace rifle 0.14).
RIGID_SLOPE = .35
CELL_PART = re.compile(r'^(.+?)(Core|Cap_-?\d+|Cage_\d+)$')


def robot_fit(length, cross, knots, support, support_part, body, barrel, grip_zone=None):
    """The robot variant of one weapon: ``length`` = CE length in the hand (m), ``cross`` = x/z factor, ``knots`` the bore map
    without the grip zone (which robot_knots adds), ``support`` the support-hand socket (life metres), ``grip_zone`` the
    half length of the zone around Socket_Hand with slope ``cross`` when the grip is deeper than GRIP_ZONE (0.18)."""
    fit = {'length_m': length, 'cross': cross, 'knots': knots, 'support': support, 'support_part': support_part,
           'body': body, 'barrel': barrel}
    if grip_zone is not None:
        fit['grip_zone'] = grip_zone
    return fit


def grip_zone(fit):
    return fit.get('grip_zone', GRIP_ZONE)


def robot_knots(fit):
    """The full bore map: the weapon's knots plus the grip zone (slope ``cross`` around Socket_Hand), sorted by life y."""
    zone = [(grip_zone(fit), grip_zone(fit) * fit['cross']), (-grip_zone(fit), -grip_zone(fit) * fit['cross'])]
    return sorted(fit['knots'] + zone)


def robot_y(fit, y):
    """Robot y of the life y (piecewise linear, the end segments extend beyond the outer knots)."""
    if -grip_zone(fit) <= y <= grip_zone(fit):
        return y * fit['cross']           # exact in the grip zone: Socket_Hand stays at the origin
    knots = robot_knots(fit)
    index = min(max(next((i for i, (a, _) in enumerate(knots) if a > y), len(knots)) - 1, 0), len(knots) - 2)
    (a0, b0), (a1, b1) = knots[index], knots[index + 1]
    return b0 + (y - a0) * (b1 - b0) / (a1 - a0)


def robot_life_y(fit, y):
    """Life y of the robot y (the inverse of robot_y; the map is strictly increasing)."""
    knots = [(b, a) for a, b in robot_knots(fit)]
    index = min(max(next((i for i, (b, _) in enumerate(knots) if b > y), len(knots)) - 1, 0), len(knots) - 2)
    (b0, a0), (b1, a1) = knots[index], knots[index + 1]
    return a0 + (y - b0) * (a1 - a0) / (b1 - b0)


def robot_slope(fit, y):
    """d(robot y) / d(life y) at the life y (the right-hand segment at a knot)."""
    return (robot_y(fit, y + 1e-4) - robot_y(fit, y)) / 1e-4


def robot_point(fit, point, cell=None):
    """Robot position of a life point; ``cell`` = robot_cell_map(...) of the energy cell the point belongs to."""
    c = fit['cross']
    y = cell[1] + (point[1] - cell[0]) * cell[2] if cell else robot_y(fit, point[1])
    return (point[0] * c, y, point[2] * c)


def robot_life_point(fit, point):
    """Life point of a robot position (the inverse of robot_point outside energy cells; 0.23 mask regions)."""
    c = fit['cross']
    return (point[0] / c, robot_life_y(fit, point[1]), point[2] / c)


def robot_cells(names):
    """Energy-cell groups among part names (without SM_PG_): {part name: group}, only groups with core, caps and cage."""
    found = {}
    for name in names:
        match = CELL_PART.match(name)
        if match:
            found.setdefault(match.group(1), []).append((name, match.group(2)))
    groups = {}
    for group, members in found.items():
        kinds = {kind.split('_')[0] for _, kind in members}
        if kinds == {'Core', 'Cap', 'Cage'}:
            groups.update({name: group for name, _ in members})
    return groups


def robot_cell_map(fit, low_y, high_y):
    """(life centre, robot centre, slope) of an energy cell spanning life y low..high: its mean slope, at least RIGID_SLOPE."""
    centre = (low_y + high_y) / 2
    mean = (robot_y(fit, high_y) - robot_y(fit, low_y)) / (high_y - low_y)
    return centre, robot_y(fit, centre), max(mean, RIGID_SLOPE)


ROBOT = {
    # CE length in the hand (Docs/EQUIPMENT.md, 0.82): length = Toolgen length x heldScale; stock end at +0.11 m.
    # 0.18 KG02: the grip is 93 mm deep (zone +-50 mm keeps it unbent), support at the rear bottom of the magazine well p08
    'assault_rifle': robot_fit(.67, 1.5, [(.3132, .11), (-.14, -.09), (-.6208, -.56)], (0, -.14, .050), 'Part_p08',
                               ('Gehaeuse_p09',), 'Lauf_p13', grip_zone=.05),
    # 0.24 KG03: support at the rear of the energy cell p18 (the magazine of the sheet), the grip (88 mm deep) in a +-45 mm zone
    'pulse_rifle': robot_fit(.66, 1.5, [(.2542, .11), (-.165, -.095), (-.6078, -.55)], (0, -.165, .040), 'Energiezelle_p18',
                             ('Gehaeuse_p06',), 'Muendung_p22', grip_zone=.045),
    'shotgun': robot_fit(.67, 1.35, [(.389, .11), (-.10, -.09), (-.515, -.56)], (0, -.10, .035), 'Receiver',
                         ('Receiver',), 'BarrelShroud'),
    'sniper_rifle': robot_fit(.73, 1.45, [(.434, .11), (-.10, -.09), (-.701, -.62)], (0, -.10, .036), 'Chassis',
                              ('Receiver', 'Chassis'), 'Barrel'),
    # 0.24 KG06: support under the front of the housing p04, just ahead of the trigger guard (the grip holds the magazine);
    # the shroud and muzzle stretch a little to the CE length; the trigger p12 (the Use clip's moving part) keeps slope
    # 0.75 up to y -0.076 (at 0.46 its decimated LOD1 folded: UV1 tangents 81 % aligned, verify_surface wants 90 %)
    'smg': robot_fit(.52, 1.35, [(.2357, .11), (-.076, -.081), (-.13, -.095), (-.3803, -.41)], (0, -.13, .054), 'Gehaeuse_p04',
                     ('Gehaeuse_p04',), 'Laufmantel_p06'),
    # fusion rifle: the sight post (0.6 mm off a rail slot at y -0.12) sits where the map is almost 1:1
    'fusion_rifle': robot_fit(.67, 1.35, [(.359, .11), (-.11, -.08), (-.135, -.1025), (-.601, -.56)], (0, -.12, .040), 'Handguard',
                              ('Body', 'BodyDark'), 'Core'),
    # trace rifle: the handguard 1:1 (its vents and glow strip end 1 mm apart; at 0.82 they flickered in the viewer)
    'trace_rifle': robot_fit(.69, 1.6, [(.384, .11), (-.065, -.09), (-.385, -.41), (-.661, -.58)], (0, -.065, .036), 'MagWell',
                             ('Receiver', 'ReceiverTop', 'TopRail'), 'Barrel'),
    'rocket_launcher': robot_fit(.65, 1.15, [(.2, .11), (-.10, -.09), (-.525, -.54)], (0, -.10, .040), 'Tube',
                                 ('Tube',), 'Tube'),
    # 0.24 KG11 (new): CE names no length for a scout rifle yet (spec robot_fit.applies false); 0.70 m keeps the class order
    # of CE's EquipmentCatalogTests (trace rifle 0.69 < scout < sniper rifle 0.73); support at the rear face of the box
    # magazine p11 (the magazine well p10 sits 6 cm high: 0.137 m from the grip, out of reach), the grip (92 mm deep) in
    # a +-45 mm zone (with 50 mm the charging handle's stroke shrank to 3.7 mm, below the Use clip's 4 mm), cross 1.6
    # for a barrel of at least 3 cm
    'scout_rifle': robot_fit(.70, 1.6, [(.2923, .11), (-.192, -.095), (-.7077, -.59)], (0, -.192, .035), 'Magazin_p11',
                             ('Gehaeuse_p03',), 'Lauf_p14', grip_zone=.045),
}


def robot_spec(key, pivots=None):
    """The design entry of the robot variant: asset <asset>_Robot, the moved support socket's part, the sight rule's height,
    the presentation camera on the robot model and, given ``pivots`` (node name -> life y of the Use clip's empties), the
    clip's travel in robot metres (along the bore the mapped displaced pivot, exact across knots; across it ``cross``)."""
    spec, fit = DESIGNS[key], ROBOT[key]
    c = fit['cross']
    moves = []
    for move in spec['use_clip']:
        if move['channel'] == 'location':
            if pivots is None:
                raise ValueError('robot_spec needs the pivots to scale a location move')
            if move['axis'] == 1:
                rest = pivots[move['node']]
                keys = [(frame, robot_y(fit, rest + value) - robot_y(fit, rest)) for frame, value in move['keys']]
            else:
                keys = [(frame, value * c) for frame, value in move['keys']]
            move = dict(move, keys=keys)
        moves.append(move)
    center = spec['view_center']
    return dict(spec, asset=spec['asset'] + ROBOT_SUFFIX, support_part=fit['support_part'], use_clip=moves,
                sight=dict(spec['sight'], above_m=spec['sight']['above_m'] * c), robot=fit,
                view_center=robot_point(fit, center), view_scale=fit['length_m'] * 1.25)
