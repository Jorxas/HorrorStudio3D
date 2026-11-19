"""« La marche » : the ten worlds, as plain data for the existing pixel3d engine (no engine change).

Every world is its OWN episode, `engine_version` 2, ONE shot that lasts the whole film, so that every world is
rendered at the SAME absolute time as the others. That is what the dissolves need: the old and the new world are
both evaluated at instant t, Noe is in the same pose in both (the gait phase is tied to the distance walked, and the
walk of world k starts a whole number of gait cycles after the walk of world 0 -- see `walk_start`).

Nothing here is a renderer: it only writes the DSL of docs/FORMAT_EPISODE.md.
"""
import math
import numpy as np

FPS = 24
DUR = 61.0
V = 0.95                       # m/s, Noe's speed, the same for the whole film
TA = 0.45                      # s, the engine's walk acceleration (acting/timeline.Path)
T0 = [0, 6, 12, 18, 24, 30, 36, 42, 48, 54]
XF = 1.2                       # s, dissolve at the start of each world but the first
NAMES = ['Ville au matin', 'Parc au printemps', 'Automne', 'Ville sous la pluie', 'Glacier',
         'Ruines en feu', 'Champ de bataille', 'Invasion', 'Vaisseau spatial', 'La Lune']


# camera marks of the brief: time, angle (rad), distance, camera height, look height, field (deg)
CAM = [(0, .30, 7.5, 1.7, 1.6, 46), (6, .70, 6.2, 1.5, 1.5, 46), (14, 1.10, 5.8, 1.4, 1.45, 46), (22, .85, 5.6, 1.6, 1.5, 46),
       (27, 1.45, 5.8, 2.1, 1.25, 46), (30, .50, 6.0, 1.0, 1.7, 48), (38, .95, 6.8, 1.6, 1.4, 48), (45, .55, 6.5, .8, 2.2, 52),
       (52, 1.30, 5.2, 1.5, 1.5, 48), (57, 1.50, 6.0, 3.1, .85, 46), (61, 2.45, 8.5, 2.6, 1.2, 48)]


def smooth(x): x = min(1., max(0., x)); return x * x * (3 - 2 * x)


def cam_params(t):
    if t <= CAM[0][0]: return CAM[0][1:]
    for a, b in zip(CAM, CAM[1:]):
        if t <= b[0]:
            w = smooth((t - a[0]) / (b[0] - a[0])); return tuple(a[i] * (1 - w) + b[i] * w for i in range(1, 6))
    return CAM[-1][1:]


def camera_for(hx, hz, t):
    ang, dist, ch, lh, fov = cam_params(t)
    # Noe walks along +z; the camera sits on the +x side so that he crosses the screen from left to right.
    pos = (hx + math.sin(ang) * dist, ch, hz + math.cos(ang) * dist)
    tgt = (hx, lh, hz + .25)
    roll = math.radians(.7) * math.sin(2 * math.pi * t / 16.)
    return pos, tgt, roll, fov



def stride():
    from hstudio.acting import rig
    return rig.stride_for(V)


def walk_start(k):
    """absolute time at which Noe starts walking in world k: a whole number of gait cycles after world 0, and early
    enough (>= TA + margin) for the acceleration to be over when the world first appears."""
    if k == 0: return 0.0
    period = stride() / V
    n = math.floor((T0[k] - TA - 0.15) / period)
    return n * period


def hero_z(k, z0):
    """z of Noe (at the world's first visible instant z0), given the walk start of that world"""
    s = walk_start(k)
    return z0 - V * (T0[k] - s) + V * TA / 2           # z at the start of the walk, standing


def rgb(h):
    h = h.lstrip('#'); return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


# ------------------------------------------------------------------ people
NOE = dict(skin=rgb('F0A874'), hair=rgb('3A2418'), hair_style='curly', outfit='hoodie', hood=rgb('8A8890'), jeans=rgb('2C2C32'),
           headphones=False, backpack=False)
LINA = dict(skin=rgb('E8B090'), hair=rgb('5A3420'), hair_style='long', outfit='coat', hood=rgb('8A1A24'), jeans=rgb('2A2630'),
            headphones=False, backpack=False, scale=0.95)


def person(skin, hair, top, legs, style='short', outfit='tshirt', **kw):
    d = dict(skin=skin, hair=hair, hair_style=style, outfit=outfit, hood=top, jeans=legs, headphones=False, backpack=False)
    d.update(kw); return d


FIG = {
    'f_marc': person([225, 170, 130], [40, 30, 24], [180, 60, 50], [50, 60, 90]),
    'f_ines': person([120, 80, 56], [20, 16, 14], [240, 200, 60], [40, 40, 52], 'ponytail', 'tshirt'),
    'f_paul': person([245, 200, 170], [180, 130, 60], [60, 120, 170], [90, 80, 70], 'short', 'shirt'),
    'f_awa': person([90, 58, 40], [16, 12, 12], [230, 230, 235], [30, 30, 40], 'bun', 'dress'),
    'f_hugo': person([235, 185, 150], [110, 70, 40], [70, 140, 80], [60, 60, 70], 'spiky', 'hoodie'),
    'f_lea': person([250, 205, 180], [200, 80, 40], [120, 60, 150], [40, 50, 80], 'ponytail', 'coat'),
    'f_omar': person([170, 120, 90], [30, 24, 20], [200, 120, 40], [50, 50, 60], 'short', 'shirt'),
    'f_yuki': person([245, 215, 190], [24, 20, 24], [60, 60, 70], [30, 30, 36], 'long', 'coat'),
    'f_sam': person([200, 150, 110], [90, 60, 40], [140, 140, 150], [40, 50, 60], 'short', 'hoodie', glasses=True),
    'f_rose': person([235, 190, 160], [210, 210, 215], [160, 60, 100], [60, 50, 60], 'bun', 'coat'),
    'alien1': dict(kind='alien', scale=1.05), 'alien2': dict(kind='alien', scale=1.05), 'alien3': dict(kind='alien', scale=1.05),
    'crew': person([245, 205, 175], [60, 44, 30], [60, 130, 80], [50, 54, 66], 'short', 'uniform'),
}


def opp(k, z0, v, dt):
    """a walker coming TOWARDS Noe at speed v who passes him dt seconds after the world starts:
    (start time of its walk, its z at that time)"""
    s = T0[k] - 1.0; zmeet = z0 + V * dt
    return s, zmeet + v * (T0[k] + dt - s) - v * TA / 2


def same(k, z_at_t0, v):
    """a walker going the same way at speed v who is at z_at_t0 when the world starts"""
    s = T0[k] - 1.0
    return s, z_at_t0 - v * (T0[k] - s) + v * TA / 2


def clear(props, x, z0, z1, half=1.1):
    """remove the props that stand on Noe's lane"""
    return [p for p in props if not (abs(p['at'][0] - x) < half + p.get('r', 0) and z0 - 1 <= p['at'][1] <= z1 + 1)]


def expanded(kind, spec, lane, z0, z1, half=1.1):
    from hstudio.engines.pixel3d import places as PL
    o = PL.expand(kind, spec)
    o = dict(o); o['props'] = clear(o['props'], lane, z0, z1, half)
    o['type'] = 'room'; o['generated'] = True
    return o


def rng(seed): return np.random.default_rng(seed)


def blocks_ring(cx, cz, r, n, h, w, col, seed=0):
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        out.append({'at': [cx + math.cos(a) * r - w / 2, 0, cz + math.sin(a) * r - w / 2], 'size': [w, h * (0.7 + 0.5 * ((i * 7 + seed) % 5) / 4), w], 'color': col, 'material': 'stone'})
    return out


# ------------------------------------------------------------------ the worlds
# each returns dict(set, lane, z0, cast, actors, actions, faces, weather, lighting, foot, grade)
def w0():
    lane, z0 = -5.0, 2.5
    s = expanded('city_street', {'seed': 2, 'sky': 'day', 'fog': .02}, lane, 0, 14)
    s['props'] = [p for p in s['props'] if p['type'] not in ('car',)] + [
        {'type': 'car', 'at': [-2.0, 6.5], 'color': [190, 40, 36]}, {'type': 'car', 'at': [2.1, 13], 'color': [50, 90, 170]},
        {'type': 'car', 'at': [-2.0, 22], 'color': [235, 235, 235]}, {'type': 'car', 'at': [2.0, 4], 'color': [235, 200, 40]}]
    s['sun'] = True; s['ambient'] = (.2, .2, .22)
    cast = {'f_marc': FIG['f_marc'], 'f_ines': FIG['f_ines'], 'f_paul': FIG['f_paul'], 'f_awa': FIG['f_awa']}
    s1, zA1 = opp(0, z0, 1.1, 3.2); s2, zA2 = opp(0, z0, 1.0, 1.5); s3, zA3 = same(0, 3.0, 1.2)
    actors = [dict(id='f_marc', at=[lane - 1.1, zA1], facing='-z'), dict(id='f_ines', at=[5.3, zA2], facing='-z'),
              dict(id='f_paul', at=[5.7, zA3], facing='+z'), dict(id='f_awa', at=[4.4, 9.5], facing='-x')]
    acts = [dict(who='f_marc', do='walk_to', to=[lane - 1.1, zA1 - 14.0], speed=1.1, at=s1),
            dict(who='f_ines', do='walk_to', to=[5.3, zA2 - 14.0], speed=1.0, at=s2),
            dict(who='f_paul', do='walk_to', to=[5.7, zA3 + 20.0], speed=1.2, at=s3),
            dict(who='f_awa', do='gesture', name='phone', at=0.5, dur=5.0), dict(who='f_awa', do='look_around', at=0.5, dur=5.0, amount=.5)]
    return dict(set=s, lane=lane, z0=z0, cast=cast, actors=actors, actions=acts, faces=[(0, 'neutral')], weather=None,
                lighting={'mood': 'warm', 'mood_power': .6}, foot=None)


def w1():
    lane, z0 = 0.6, 1.0
    s = expanded('park', {'seed': 5, 'sky': 'day', 'weather': 'petals'}, lane, -2, 11, 1.4)
    s['zones'] = [{'path': [[0, -2], [0, 30]], 'width': 2.6, 'ground': 'sand'}, {'path': [[-12, 12], [12, 12]], 'width': 2.2, 'ground': 'sand'}, {'circle': [-7, 21, 3], 'ground': 'water'}]
    s['props'] = [p for p in s['props'] if not (p['type'] == 'bench')] + [{'type': 'bench', 'at': [-2.7, 6.5], 'rot': 3}]
    s['props'] += [{'type': 'flowers', 'at': [x, z], 'color': c} for (x, z, c) in
                   [(2.6, 2.0, [235, 120, 170]), (-2.4, 3.0, [240, 220, 70]), (2.8, 9.0, [250, 250, 250]), (-2.6, 8.0, [160, 90, 200]), (3.4, 4.0, [235, 120, 170]), (-3.2, 5.5, [240, 220, 70])]]
    cast = {'lina': LINA, 'f_hugo': FIG['f_hugo']}
    lz = z0 + 0.5
    actors = [dict(id='f_hugo', at=[-2.5, 6.5], facing='+x', posture='sit')]
    acts = [dict(who='f_hugo', do='face', name='happy', at=0.0)]
    return dict(set=s, lane=lane, z0=z0, cast=cast, actors=actors, actions=acts, faces=[(6, 'happy')], weather='petals',
                lighting=None, foot=([90, 64, 32], .6), companion=dict(id='lina', dx=-1.3, dz=0.5, face=[(6, 'happy')], looks=[(7.5, 'noe')]), noe_looks=[(8.3, 'lina', 1.4)])


def w2():
    lane, z0 = 0.4, 1.0
    s = expanded('forest', {'seed': 8, 'sky': 'sunset', 'fog': .035, 'weather': 'leaves'}, lane, -2, 11, 1.4)
    s['props'] = [dict(p, type='autumn_tree') if p['type'] in ('tree', 'tree_round', 'pine', 'birch') else p for p in s['props']]
    s['ground'] = 'leaves'; s['zones'] = [{'path': [[0, -2], [0.3, 30]], 'width': 2.4, 'ground': 'dirt'}]
    s['props'] += [{'type': 'fence', 'at': [-2.6, z], 'rot': 1} for z in range(0, 14, 3)] + [{'type': 'autumn_tree', 'at': [4.5, 4.0]}, {'type': 'autumn_tree', 'at': [-5.0, 7.0]}, {'type': 'autumn_tree', 'at': [5.8, 10.0]}]
    cast = {'lina': LINA}
    return dict(set=s, lane=lane, z0=z0, cast=cast, actors=[], actions=[], faces=[(12, 'calm'), (15.6, 'sad')], weather='leaves',
                lighting={'mood': 'warm', 'mood_power': 1.0, 'back': 1.1, 'fill': 1.2}, foot=([58, 34, 8], .6), grade={'saturation': 1.05, 'exposure': 1.1},
                companion=dict(id='lina', dx=-1.6, dz=0.9, face=[(12, 'happy'), (15.0, 'smile_sad')], stop_at=15.0, wave=(15.7, 2.2), looks=[(13.0, 'noe')]))


def w3():
    lane, z0 = -5.0, 2.5
    s = expanded('city_street', {'seed': 9, 'sky': 'storm', 'fog': .045, 'wet': True, 'weather': 'rain'}, lane, 0, 14)
    s['wet'] = True
    cast = {'u1': dict(FIG['f_marc'], ), 'u2': FIG['f_ines'], 'u3': FIG['f_sam']}
    acts = []; actors = []
    for i, (aid, x, dt, v) in enumerate([('u1', lane - 0.9, 2.5, 1.0), ('u2', -3.9, 1.0, 1.1), ('u3', -6.1, 4.5, .9)]):
        s_, zA = opp(3, z0, v, dt)
        actors.append(dict(id=aid, at=[x, zA], facing='-z', hold='umbrella'))
        acts.append(dict(who=aid, do='walk_to', to=[x, zA - 16.0], speed=v, at=s_))
    return dict(set=s, lane=lane, z0=z0, cast=cast, actors=actors, actions=acts, faces=[(18, 'sad')], weather='rain',
                lighting={'mood': 'cold', 'mood_power': .7}, foot=None, grade={'saturation': .8, 'exposure': 1.05})


def w4():
    lane, z0 = 0.0, 2.0
    r = rng(40)
    blocks = []
    for i in range(16):
        x = float(r.choice([-1, 1])) * float(r.uniform(2.6, 9)); z = float(r.uniform(-2, 30)); s_ = float(r.uniform(.6, 4.0))
        blocks.append({'at': [x, 0, z], 'size': [s_ * float(r.uniform(.8, 1.2)), s_ * float(r.uniform(.8, 1.4)), s_ * float(r.uniform(.8, 1.2))], 'color': [170, 215, 245], 'material': 'glass'})
    s = {'type': 'room', 'generated': True, 'outdoor': True, 'rooms': [], 'props': [{'type': 'snow_pine', 'at': [-9, 10]}, {'type': 'snow_pine', 'at': [9, 18]}], 'zones': [],
         'ground': 'snow', 'sky': 'day', 'backdrop': ['snow_mountains', {'type': 'snow_mountains', 'height': 2}], 'fog': .012, 'fill': .6, 'blocks': blocks, 'textured_ground': True, 'weather': 'snow', 'ambience': 'wind'}
    return dict(set=s, lane=lane, z0=z0, cast={}, actors=[], actions=[], faces=[(24, 'determined')], weather='snow',
                lighting={'mood': 'cold', 'mood_power': .4, 'fill': .8}, foot=([52, 68, 94], 1.0), grade={'saturation': 1.0, 'exposure': .78})


def w5():
    lane, z0 = 0.0, 2.0
    r = rng(50)
    blocks = []
    props = []
    for i in range(14):
        x = float(r.choice([-1, 1])) * float(r.uniform(3, 10)); z = float(r.uniform(-2, 28))
        kind = i % 3
        if kind == 0: blocks.append({'at': [x, 0, z], 'size': [0.7, float(r.uniform(2.5, 5)), 0.7], 'color': [46, 40, 38], 'material': 'stone'})
        elif kind == 1: blocks.append({'at': [x, 0, z], 'size': [float(r.uniform(2, 4)), float(r.uniform(1.5, 3.5)), 0.5], 'color': [52, 44, 40], 'material': 'stone'})
        else: props.append({'type': 'ruins', 'at': [x, z]})
    for (x, z) in [(2.2, 5), (-2.4, 8), (3.1, 12), (-3.0, 3), (2.6, 17), (-2.6, 14), (4.2, 8.5), (-4.2, 6.5)]:
        props.append({'type': 'campfire', 'at': [x, z], 'light_power': 1.0})
    s = {'type': 'room', 'generated': True, 'outdoor': True, 'rooms': [], 'props': props, 'ground': 'rock', 'sky': 'sunset', 'backdrop': ['volcano'], 'fog': .05, 'fog_color': (.25, .09, .04), 'fill': .5, 'ambient': (.11, .05, .03),
         'zones': [{'path': [[-9, -2], [-5, 8], [-8, 22]], 'width': .45, 'ground': 'lava'}, {'path': [[9, 0], [5.5, 10], [8, 24]], 'width': .45, 'ground': 'lava'}, {'path': [[-4, 24], [0.6, 30], [5, 24]], 'width': .6, 'ground': 'lava'}],
         'blocks': blocks, 'textured_ground': True, 'weather': 'embers', 'ambience': 'campfire'}
    s['props'] = clear(s['props'], lane, -2, 12, 1.6)
    cast = {'f_omar': FIG['f_omar']}
    s_, zA = opp(5, z0, 3.4, 3.4)
    actors = [dict(id='f_omar', at=[1.5, zA], facing='-z')]
    acts = [dict(who='f_omar', do='face', name='shocked', at=0.0), dict(who='f_omar', do='run_to', to=[1.5, zA - 24.0], speed=3.4, at=s_)]
    return dict(set=s, lane=lane, z0=z0, cast=cast, actors=actors, actions=acts, faces=[(30, 'angry')], weather='embers',
                lighting={'mood': 'red', 'mood_power': .9, 'fill': .9}, foot=None, grade={'saturation': .95, 'exposure': 1.05}, noe_around=(31.0, 3.5))


def w6():
    lane, z0 = 0.0, 2.0
    r = rng(60)
    props = [{'type': 'flag', 'at': [-3.5, 4], 'color': [200, 40, 40]}, {'type': 'flag', 'at': [3.8, 9], 'color': [40, 80, 200]}, {'type': 'flag', 'at': [-4.2, 15], 'color': [40, 80, 200]},
             {'type': 'flag', 'at': [4.6, 3], 'color': [200, 40, 40]}]
    props += [{'type': 'rock', 'at': [float(r.choice([-1, 1])) * float(r.uniform(5, 11)), float(r.uniform(-2, 25))]} for _ in range(9)]
    props += [{'type': 'castle_wall', 'at': [x, 30]} for x in (-12, -6, 0, 6, 12)]
    s = {'type': 'room', 'generated': True, 'outdoor': True, 'rooms': [], 'props': props, 'ground': 'dirt', 'sky': 'overcast', 'backdrop': ['hills'], 'fog': .06, 'fog_color': (.5, .42, .2), 'fill': .55,
         'zones': [], 'blocks': [], 'textured_ground': True, 'weather': 'dust', 'ambience': 'crowd'}
    s['props'] = clear(s['props'], lane, -2, 14, 1.4)
    cast = {}; actors = []; acts = []
    pairs = [(-2.9, 4.6), (-4.6, 0.6), (-3.4, 9.0)]
    s6 = walk_start(6)
    for i, (px, pz) in enumerate(pairs):
        for side, nm in ((0, f'r{i}'), (1, f'b{i}')):
            col = [190, 40, 40] if side == 0 else [40, 80, 190]
            cast[nm] = person([230, 180, 140], [60, 40, 30], col, [60, 56, 52], 'short', 'armor', hat='helmet', hat_color=[150, 150, 156])
            zA = hero_z(6, pz + (-0.55 if side == 0 else 0.55))
            actors.append(dict(id=nm, at=[px, zA], facing='+z' if side == 0 else '-z', hold='sword' if side == 0 else 'shield', face='angry'))
            # they advance with Noe, always facing each other, striking
            acts.append(dict(who=nm, do='walk_to', to=[px, zA + 16.0], speed=V, at=s6, face='+z' if side == 0 else '-z'))
            for j in range(14):
                acts.append(dict(who=nm, do='gesture', name=['arm_up', 'extend', 'stop', 'knock', 'arm_up'][(j + i + side) % 5], at=35.5 + j * 0.6 + 0.15 * side, dur=.5))
    return dict(set=s, lane=lane, z0=z0, cast=cast, actors=actors, actions=acts, faces=[(36, 'determined')], weather='dust',
                lighting={'mood': 'warm', 'mood_power': .5}, foot=([30, 18, 8], 1.0), grade={'saturation': .9, 'exposure': 1.05})


def w7():
    lane, z0 = 0.0, 2.0
    blds = []
    r = rng(70)
    for i, z in enumerate(range(-2, 40, 7)):
        for side in (-1, 1):
            blds.append({'rect': [side * 11 - 2.5, z, side * 11 + 2.5, z + 6], 'height': 7 + float(r.uniform(0, 8)), 'color': [110 + 15 * (i % 2), 70, 150], 'lit': .6})
    blocks = []
    for (cx, cz, cy) in [(-6, 3, 7.5), (-8.5, 10, 8.5), (-5, -1.5, 6.8), (-12, 6, 9.5)]:
        blocks += [{'at': [cx - 3, cy, cz - 3], 'size': [6, .55, 6], 'color': [120, 126, 134], 'material': 'metal'},
                   {'at': [cx - 2, cy + .55, cz - 2], 'size': [4, .5, 4], 'color': [150, 156, 164], 'material': 'metal'},
                   {'at': [cx - 1, cy + 1.0, cz - 1], 'size': [2, .5, 2], 'color': [110, 190, 140], 'material': 'glass'}]
        for k in range(8):
            a = k * math.pi / 4
            blocks.append({'at': [cx + math.cos(a) * 2.8 - .15, cy + .2, cz + math.sin(a) * 2.8 - .15], 'size': [.3, .25, .3], 'color': [120, 255, 140], 'material': 'light', 'emissive': 1.0, 'light': .5, 'light_color': [.4, 1, .5], 'light_radius': 4})
        blocks.append({'at': [cx - .6, 0, cz - .6], 'size': [1.2, cy, 1.2], 'color': [120, 230, 190], 'material': 'glass', 'emissive': .15})
    s = {'type': 'room', 'generated': True, 'outdoor': True, 'rooms': [], 'props': [], 'buildings': blds, 'ground': 'asphalt', 'sky': 'sunset', 'backdrop': ['city'], 'fog': .018, 'fill': .6,
         'zones': [{'rect': [-5, -4, 5, 60], 'ground': 'road'}], 'blocks': blocks, 'textured_ground': True, 'ambience': 'wind'}
    cast = {'alien1': FIG['alien1'], 'alien2': FIG['alien2'], 'alien3': FIG['alien3'], 'f_yuki': FIG['f_yuki'], 'f_sam': FIG['f_sam'], 'f_rose': FIG['f_rose']}
    s7 = walk_start(7); actors = []; acts = []
    for nm, ax, az in (('alien1', -1.9, 4.2), ('alien2', -3.1, 1.6), ('alien3', -2.4, 7.0)):
        actors.append(dict(id=nm, at=[ax, hero_z(7, az)], facing='+z')); acts.append(dict(who=nm, do='walk_to', to=[ax, hero_z(7, az) + 20.0], speed=V, at=s7))
    acts += [dict(who='alien1', do='gesture', name='point', at=44.0, dur=3.0), dict(who='alien2', do='look_at', target='noe', at=44.2, dur=2.5), dict(who='alien3', do='gesture', name='cheer', at=44.6, dur=2.5)]
    for nm, x, dt in (('f_yuki', -1.2, 1.6), ('f_sam', 2.0, 2.8), ('f_rose', -2.2, 4.0)):
        s_, zA = opp(7, z0, 3.2, dt)
        actors.append(dict(id=nm, at=[x, zA], facing='-z', face='shocked')); acts.append(dict(who=nm, do='run_to', to=[x, zA - 26.0], speed=3.2, at=s_))
    return dict(set=s, lane=lane, z0=z0, cast=cast, actors=actors, actions=acts, faces=[(42, 'surprised')], weather=None,
                lighting={'mood': 'red', 'mood_power': .6, 'halo': {'from': [0, 6], 'color': 'green', 'power': 1.2, 'radius': 6, 'y': 6}}, foot=None)


def w8():
    lane, z0 = 0.0, 2.5
    props = []
    for z in range(0, 46, 4):
        for sx in (-1, 1): props.append({'type': 'column', 'at': [sx * 5.4, z], 'color': [120, 132, 150]})
    for z in range(2, 46, 9):
        props.append({'type': 'space_window', 'at': [-6.3, z + 2], 'rot': 3}); props.append({'type': 'space_window', 'at': [6.3, z + 2], 'rot': 1})
    blocks = [{'at': [-2.2, 3.55, 0], 'size': [.6, .08, 46], 'color': [255, 255, 255], 'material': 'light', 'emissive': 1.4, 'light': 1.0, 'light_radius': 7, 'light_color': [.85, .92, 1]},
              {'at': [1.6, 3.55, 0], 'size': [.6, .08, 46], 'color': [255, 255, 255], 'material': 'light', 'emissive': 1.4}]
    for i, z in enumerate(range(3, 46, 4)):
        blocks.append({'at': [-5.5, 1.6, z + .3], 'size': [.1, .12, .12], 'color': [[255, 60, 50], [60, 255, 90], [80, 140, 255]][i % 3], 'material': 'light', 'emissive': 1.5})
        blocks.append({'at': [5.5, 1.6, z + 1.3], 'size': [.1, .12, .12], 'color': [[60, 255, 90], [80, 140, 255], [255, 60, 50]][i % 3], 'material': 'light', 'emissive': 1.5})
    blocks += [{'at': [-16, 0, 2], 'size': [8, 8, 8], 'color': [230, 130, 50], 'material': 'light', 'emissive': .5}, {'at': [-14, 1, 4], 'size': [6, 6, 6], 'color': [210, 110, 40], 'material': 'light', 'emissive': .5}]
    s = {'type': 'room', 'generated': True, 'outdoor': False, 'height': 3.6, 'fog': .02, 'fill': .9, 'ambient': (.34, .37, .45), 'props': props, 'blocks': blocks, 'zones': [],
         'rooms': [{'id': 'couloir', 'origin': [0, 0], 'size': [13, 46], 'walls': 'concrete', 'wall_color': [96, 110, 132], 'floor': 'tiles', 'light': 'cold', 'light_power': 2.4, 'height': 3.6, 'props': [], 'windows': [], 'doors': []}],
         'ambience': 'space'}
    s['props'] = clear(s['props'], lane, -2, 14, 1.2)
    cast = {'crew': FIG['crew']}
    s_, zA = opp(8, z0, 1.0, 2.6)
    actors = [dict(id='crew', at=[1.5, zA], facing='-z')]
    acts = [dict(who='crew', do='walk_to', to=[1.5, zA - 18.0], speed=1.0, at=s_)]
    return dict(set=s, lane=lane, z0=z0, cast=cast, actors=actors, actions=acts, faces=[(48, 'neutral')], weather=None,
                lighting={'mood': 'cold', 'mood_power': .5}, foot=None)


def w9():
    lane, z0 = 0.0, 2.0
    r = rng(90)
    blocks = []
    for i in range(7):
        x = float(r.choice([-1, 1])) * float(r.uniform(4.5, 12)); z = float(r.uniform(-2, 30)); rr = float(r.uniform(1.4, 3.2))
        blocks += blocks_ring(x, z, rr, 10, .45, .55, [74, 78, 92], seed=i)
    earth = []
    for dx in (-2, 0, 2):
        for dy in (-2, 0, 2):
            for dz in (-2, 0, 2):
                if dx * dx + dy * dy + dz * dz <= 9: earth.append({'at': [-70 + dx - 1, 40 + dy - 1, -22 + dz - 1], 'size': [2, 2, 2], 'color': [60, 120, 230] if (dx + dy) % 4 else [70, 170, 90], 'material': 'light', 'emissive': .9})
    door = {'at': [-.7, 0, 24], 'size': [1.4, 4.2, .25], 'color': [255, 244, 224], 'material': 'light', 'emissive': 3.0, 'light': 4.0, 'light_color': [1, .94, .82], 'light_radius': 14}
    s = {'type': 'room', 'generated': True, 'outdoor': True, 'rooms': [], 'props': [], 'zones': [], 'ground': 'rock', 'sky': 'night', 'stars': True, 'fog': .004, 'fill': .5, 'ambient': (.11, .12, .17),
         'blocks': blocks + earth + [door], 'textured_ground': True, 'ambience': 'space', 'anchors': {'porte': (0, 24)}}
    return dict(set=s, lane=lane, z0=z0, cast={}, actors=[], actions=[], faces=[(54, 'determined'), (58.5, 'happy')], weather=None,
                lighting={'mood': 'cold', 'mood_power': .3, 'halo': {'from': 'porte', 'color': 'warm', 'power': 2.0, 'radius': 9, 'y': 2.0}, 'back': 0.9}, foot=([22, 22, 26], 1.0),
                grade={'saturation': .85, 'exposure': 1.05}, lights=[{'at': [14, 4], 'y': 30, 'color': [1, 1, 1], 'power': 1.5, 'radius': 70}])


WORLDS = [w0, w1, w2, w3, w4, w5, w6, w7, w8, w9]



def clear_view(spec, k, lane, z0, r=1.15):
    """drop the props / blocks that would stand between the camera and Noe at any instant the world is visible
    (the camera orbits, so a lamp post or a column can cross the line of sight)"""
    ta = T0[k]; tb = (T0[k + 1] if k + 1 < len(T0) else DUR) + XF
    segs = []
    for t in np.arange(ta, tb + .01, .5):
        hz = z0 + V * (t - ta); p, _, _, _ = camera_for(lane, hz, t); segs.append(((lane, hz), (p[0], p[2])))
    def hit(x, z, rad):
        for (a, b) in segs:
            dx, dz = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dz * dz
            u = max(0., min(1., ((x - a[0]) * dx + (z - a[1]) * dz) / L2)) if L2 > 1e-9 else 0.
            if math.hypot(x - (a[0] + u * dx), z - (a[1] + u * dz)) < rad and u > .08: return True
        return False
    spec = dict(spec)
    spec['props'] = [p for p in spec.get('props', []) if not hit(p['at'][0], p['at'][1], r + p.get('r', 0))]
    spec['blocks'] = [b for b in spec.get('blocks', []) if b.get('emissive') or b.get('light') or not hit(b['at'][0] + b['size'][0] / 2, b['at'][2] + b['size'][2] / 2, r + max(b['size'][0], b['size'][2]) / 2)]
    return spec

def episode(k):
    """(episode dict, lines) of world k. One shot, the whole film long."""
    w = WORLDS[k](); lane, z0 = w['lane'], w['z0']; w['set'] = clear_view(w['set'], k, lane, z0)
    s = walk_start(k); zA = hero_z(k, z0)
    t_end = (T0[k + 1] if k + 1 < len(T0) else DUR) + XF + 0.6
    m = int(math.ceil(V * (t_end - s) / stride())) + 1
    D = m * stride()
    cast = {'noe': dict(NOE)}; cast.update(w.get('cast', {}))
    actors = [dict(id='noe', at=[lane, zA], facing='+z', face=w['faces'][0][1])] + list(w.get('actors', []))
    acts = [dict(who='noe', do='walk_to', to=[lane, zA + D], speed=V, at=s)]
    for t, f in w['faces']:
        if t > 0 or True: acts.append(dict(who='noe', do='face', name=f, at=max(0.0, float(t))))
    for (t, tgt, dur) in w.get('noe_looks', []): acts.append(dict(who='noe', do='look_at', target=tgt, at=t, dur=dur))
    if w.get('noe_around'): acts.append(dict(who='noe', do='look_around', at=w['noe_around'][0], dur=w['noe_around'][1], amount=.9))
    comp = w.get('companion')
    if comp:
        cx = lane + comp['dx']; cz = z0 + comp['dz']
        czA = cz - V * (T0[k] - s) + V * TA / 2
        actors.append(dict(id=comp['id'], at=[cx, czA], facing='+z', face=comp['face'][0][1]))
        stop = comp.get('stop_at')
        if stop is None: acts.append(dict(who=comp['id'], do='walk_to', to=[cx, czA + D], speed=V, at=s))
        else:
            dz = V * (stop - s) - V * TA / 2
            acts.append(dict(who=comp['id'], do='walk_to', to=[cx, czA + dz], speed=V, at=s))
            acts.append(dict(who=comp['id'], do='turn_to', target='noe', at=stop + 0.05))
            acts.append(dict(who=comp['id'], do='gesture', name='wave', at=comp['wave'][0], dur=comp['wave'][1]))
        for t, f in comp['face']: acts.append(dict(who=comp['id'], do='face', name=f, at=float(t)))
        for t, tgt in comp.get('looks', []): acts.append(dict(who=comp['id'], do='look_at', target=tgt, at=t, dur=1.6))
    acts += w.get('actions', [])
    shot = dict(lines=[0, 0], actors=actors, actions=acts, camera={'preset': 'free', 'keys': [{'pos': [lane + 5, 1.5, z0], 'look': [lane, 1.5, z0], 'fov': 46}]},
                ui={'hud': False, 'subs': 'off'}, fx={})
    if w.get('weather'): shot['weather'] = w['weather']
    if w.get('lighting'): shot['lighting'] = w['lighting']
    if w.get('lights'): shot['lights'] = w['lights']
    ep = dict(style='pixel3d', engine_version=2, default_set='w', sets={'w': w['set']}, cast=cast, shots=[shot], hud={'show': False},
              body='voxel_premium', env='riche', finish='net_rapide', eye_aim='aim_doux', eye_smooth='saccade', foot_plant=True,
              grade=w.get('grade', {'saturation': 1.0, 'exposure': .95}), music='none')
    lines = [dict(tts='', display='', text='', tags=[], dialogue=False, i=0, start=0.0, end=DUR - 1.2, segs=[[0.0, DUR - 1.2]])]
    return ep, lines, w
