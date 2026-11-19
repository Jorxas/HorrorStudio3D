"""« La Dernière Pompe », partie 1 (96,467 s, 9:16, 30 fps) : remake in 3D of a given video, shot for shot, on the unified engine.

Not a copy of the picture: every frame is rendered by the voxel painter from a scene file written here. What is taken from the source
video is DATA that was measured on it (`projects/remakes_voxelgpu_20261029/analyse/pompe/`): the frame of every cut, the subtitle text, its
timing and its red words, the HUD state (battery, clock) and the A/B choice card timing. The audio is the source's own track, muxed
untouched by tools/remake_film.py. The camera, the set dressing, the lights and the staging are written from what the source shows; the
source is 2D, so depth, distances and exact poses are estimates (see docs/REMAKES_VOXELGPU.md for the list of known differences).
"""
import json
from pathlib import Path

FPS = 30
CUTS = [0, 47, 115, 229, 278, 346, 417, 460, 524, 684, 743, 788, 819, 891, 920, 993, 1020, 1054, 1108, 1128, 1182, 1254, 1333, 1388, 1436, 1501, 1520, 1539, 1614,
        1656, 1693, 1741, 1801, 1845, 1924, 2016, 2104, 2177, 2235, 2293, 2461, 2581, 2695, 2799, 2894]
T = [f / FPS for f in CUTS]
DUR = 2894 / FPS
GAIN_FILE = Path(__file__).resolve().parents[3] / 'examples' / 'remakes' / 'pompe_gain.json'
CAPTIONS = Path(__file__).resolve().parents[3] / 'examples' / 'remakes' / 'pompe_captions.json'

TEAL = 0x16707a
CLERK = {'preset': 'npc', 'variant': 3, 'look': {'skin': 0xf0a874, 'brow': 0x3a1a10, 'hair': {'style': 'curly', 'color': 0x6a3a22, 'color2': 0x7a4a2a},
         'hat': {'type': 'beanie', 'color': TEAL, 'fur': 0x2a6a72}, 'top': {'type': 'jacketOpen', 'color': TEAL, 'shirt': 0x16303a}, 'pants': {'color': 0x16202c}, 'shoes': {'type': 'sneaker', 'color': 0x14141a, 'sole': 0xd0d0cc}},
         'extras': [{'bone': 'torso', 'boxes': [{'x': 0, 'y': 3.2, 'z': 0, 'w': 8.5, 'h': 0.9, 'd': 4.5, 'color': 0xd8e2c8}, {'x': 0, 'y': 6.2, 'z': 0, 'w': 8.5, 'h': 0.9, 'd': 4.5, 'color': 0xd8e2c8}]},
                    {'bone': 'handR', 'at': [0, -1.2, 1.5], 't0': 29.9, 't1': 56.0, 'boxes': [{'x': 0, 'y': 0, 'z': 0, 'w': 1.6, 'h': 1.6, 'd': 5.5, 'color': 0xe8e0c8}, {'x': 0, 'y': 0, 'z': 3, 'w': 2.2, 'h': 2.2, 'd': 1.2, 'color': 0x30302c}]}]}
GHOST = {'preset': 'npc', 'kind': 'faceless', 'hood': 0x232a38, 'look': {'top': {'type': 'hoodie', 'color': 0x2a303e, 'shirt': 0x14161c}, 'pants': {'color': 0x181a22}}}

PROP_SETS = {
    'shop24': [{'type': 'sign', 'text': '24H/24', 'at': [-0.9, 2.75, -0.9], 'w': 1.5, 'h': 0.38, 'col': '#f4f4f4', 'bg': '#0a0a0c', 'px': 256},
               {'type': 'boxes', 'boxes': [{'x': -0.9, 'y': 3.0, 'z': -0.9, 'w': 0.05, 'h': 0.5, 'd': 0.05, 'color': 0x202024}]}],
    'pump_displays': [{'type': 'sign', 'lines': ['00', '4'], 'at': [-9.5, 1.32, 12.29], 'w': 0.38, 'h': 0.34, 'col': '#ff3a2a', 'bg': '#12080a', 'px': 128},
                      {'type': 'sign', 'lines': ['00', '4'], 'at': [-12.5, 1.32, 12.29], 'w': 0.38, 'h': 0.34, 'col': '#ff3a2a', 'bg': '#12080a', 'px': 128}],
    'price_pole': [{'type': 'boxes', 'boxes': [{'x': -6, 'y': 3.4, 'z': 14.2, 'w': 0.22, 'h': 6.8, 'd': 0.22, 'color': 0x202228}]},
                   {'type': 'price_sign', 'at': [-6, 7.0, 14.0], 'w': 1.1, 'h': 1.6, 'lines': ['1.74', '0.99'], 'emit': 2.6}],
    'title_sign': [{'type': 'sign', 'text': 'LA DERNIÈRE POMPE', 'at': [0, 3.82, 3.8], 'w': 5.6, 'h': 0.95, 'col': '#ff4a3a', 'bg': '#0a0204', 'px': 512, 'emit': 1.4}],
    'reserve_door': [{'type': 'door', 'at': [3.45, 0, -6.86], 'w': 0.95, 'h': 2.1, 'color': 0x7e9a7a, 'stripe': 0x62805e, 'sign': 'RÉSERVE'}],
    'poster': [{'type': 'poster_plan', 'at': [4.43, 1.5, -3.4], 'yaw': -1.5708, 'w': 0.8, 'h': 1.0}],
    'back_sign': [{'type': 'sign', 'text': 'SORTIE', 'at': [3.4, 2.5, -7.26], 'yaw': 3.1416, 'w': 0.7, 'h': 0.26, 'col': '#ffffff', 'bg': '#0a8a3a', 'emit': 1.4},
                  {'type': 'boxes', 'boxes': [{'x': 3.0, 'y': 2.95, 'z': -7.45, 'w': 0.3, 'h': 0.12, 'd': 0.3, 'color': 0x1a1a1e}]}],
}


from ...remake.dsl import k as _k, cam, hold


def build():
    GAIN = json.loads(GAIN_FILE.read_text(encoding='utf-8')) if GAIN_FILE.exists() else {}
    shots = []; d = lambda i: round(T[i + 1] - T[i], 4)

    def add(i, stage='station', **kw):
        s = dict(id=f'S{i:02d}', stage=stage, dur=d(i), **kw)
        g = GAIN.get(s['id'])
        if g is not None and 'gain' not in (s.get('env') or {}): s['env'] = {**(s.get('env') or {}), 'gain': g}
        shots.append(s); return s
    A = lambda i, *pairs: [[round(T[i] + t, 4), v] for t, v in pairs]       # animation table in ABSOLUTE film time from times relative to shot i

    # S00 exterior, low, a lamp pole in front of the lit station
    add(0, env={'rain': 1, 'neon': .45, 'lamps': 1, 'outside': 1}, shake=.15, camera=cam(_k(0, [1.8, .45, 22.], [-.6, 1.8, 4.], 62), _k(d(0), [1.4, .5, 20.5], [-.6, 1.9, 4.], 62)),
        props=[{'type': 'boxes', 'boxes': [{'x': 1.0, 'y': 3, 'z': 12.5, 'w': .3, 'h': 6, 'd': .3, 'color': 0x08080c}]}, {'use': 'title_sign'}])
    # S01 inside, the clerk at the counter, seen from behind
    add(1, env={'rain': 1, 'outside': 0}, shake=.12, camera=cam(_k(0, [-.9, 1.55, 2.8], [2.6, 1.15, .7], 62), _k(d(1), [-.4, 1.55, 2.6], [2.6, 1.15, .7], 62)),
        tracks={'clerk': hold([2.4, 0, .9], 1.5708, face='neutral')}, props=[{'use': 'shop24'}])
    # S02 the pump, the canopy tube goes out and comes back
    add(2, env={'rain': 1, 'outside': 1, 'lamps': .5, 'neon': .6, 'canopy': A(2, (0, 1), (.77, 1), (.8, 0), (3.07, 0), (3.1, 1), (3.17, 1), (3.2, .15), (3.33, .15), (3.37, 1))}, shake=.2, camera=cam(_k(0, [-9.9, .55, 14.8], [-9.6, 2.6, 12.2], 64), _k(d(2), [-9.6, .5, 14.4], [-9.5, 3.4, 12.], 64)),
        props=[{'type': 'tube', 'at': [-9.5, 3.74, 12.4], 'rot': [0, .45, 0], 'len': 1.9, 'anim': {'on': A(2, (0, 1), (.77, 1), (.8, 0), (3.07, 0), (3.1, 1), (3.17, 1), (3.2, .15), (3.33, .15), (3.37, 1))}}, {'use': 'pump_displays'}])
    # S03 tilt up to the price sign
    add(3, env={'rain': 1, 'outside': 1, 'lamps': .6, 'neon': .4}, shake=.15, camera=cam(_k(0, [-4.5, .9, 17.5], [-6, 5.0, 14.2], 62), _k(d(3), [-4.8, .9, 17.], [-6, 6.7, 14.2], 62)), props=[{'use': 'price_pole'}])
    # S04 the hooded figure, standing in the lot, through the glass
    add(4, env={'rain': 1, 'outside': 1, 'lamps': .5, 'neon': .3, 'panels': .6}, shake=.15, camera=cam(_k(0, [.2, 1.35, 1.2], [.4, 1.5, 6.2], 58), _k(d(4), [.25, 1.35, 1.6], [.4, 1.5, 6.2], 56)),
        tracks={'ghost': hold([.4, 0, 6.4], 3.1416)}, props=[{'type': 'boxes', 'boxes': [{'x': 2.2, 'y': .8, 'z': 5.6, 'w': .2, 'h': 1.6, 'd': .2, 'color': 0xb01818}]}])
    # S05 under the canopy edge, the figure next to a pillar
    add(5, env={'rain': 1, 'outside': 1, 'lamps': .6, 'neon': .8}, shake=.15, camera=cam(_k(0, [-3.2, 1.3, 9.], [.2, 1.6, 4.2], 60), _k(d(5), [-2.9, 1.3, 8.6], [.2, 1.6, 4.2], 60)),
        tracks={'ghost': hold([-1.3, 0, 6.], 3.4)})
    # S06 inside, the clerk (dark, flashlight in hand), shelves and the 24h sign
    add(6, env={'rain': 1, 'outside': 0, 'panels': .55}, shake=.15, camera=cam(_k(0, [.6, 1.5, 2.2], [-1.5, 1.4, -1.], 62), _k(d(6), [.4, 1.5, 2.], [-1.5, 1.4, -1.], 62)),
        tracks={'clerk': hold([-.3, 0, .4], 3.1416)}, props=[{'use': 'shop24'}])
    # S07 clerk, close on the face: worried then startled
    add(7, env={'rain': 1, 'outside': 0, 'panels': .9}, shake=.1, dof=.5, camera=cam(_k(0, [.2, 1.72, 1.15], [.2, 1.68, 0.], 40), _k(d(7), [.2, 1.72, 1.0], [.2, 1.68, 0.], 40)),
        tracks={'clerk': [dict(t=0, p=[.2, 0, 0.], yaw=0, face='worried', head=[0, .05]), dict(t=.9, p=[.2, 0, 0.], yaw=0, face='surprised', head=[0, 0])]})
    # S08 slow push-in on the faceless figure behind the glass, down to the black face
    add(8, env={'rain': 1, 'outside': 1, 'lamps': .4, 'neon': .3, 'panels': .5}, shake=.1, camera=cam(_k(0, [.3, 1.5, .8], [.3, 1.45, 5.4], 56), _k(d(8) * .55, [.3, 1.55, 2.4], [.3, 1.55, 5.4], 46), _k(d(8), [.3, 1.62, 4.55], [.3, 1.62, 5.4], 34)),
        tracks={'ghost': hold([.3, 0, 5.4], 3.1416, head=[0, .12])})
    # S09 the black hand lays flat on the window
    add(9, env={'rain': 1, 'outside': 1, 'lamps': .35, 'panels': .55}, shake=.1, camera=cam(_k(0, [-.6, 1.45, .8], [-1., 1.7, 3.5], 62), _k(d(9), [-.7, 1.45, 1.1], [-1., 1.7, 3.5], 60)),
        props=[{'type': 'hand', 'at': [-1.1, 1.2, 3.38], 'scale': 1.7, 'rot': [0, 3.1416, 0], 'anim': {'curl': A(9, (0, .1), (.8, .1), (1.4, -.05))}}])
    # S10 the neon flickers (behind the counter, towards the window)
    flick = [[round(T[10] + t, 4), v] for t, v in ((0, 1), (.2, 1), (.23, .05), (.4, .05), (.43, 1), (.6, 1), (.63, .08), (.83, .08), (.87, 1), (1.1, 1), (1.13, .05), (1.5, .05))]
    add(10, env={'rain': 1, 'outside': 1, 'lamps': .6, 'panels': flick}, shake=.12, camera=cam(_k(0, [3., 1.45, 1.6], [-1.2, 1.3, 3.5], 62), _k(d(10), [2.7, 1.45, 1.5], [-1.2, 1.3, 3.5], 62)))
    # S11 looking out: "il disparaît"
    add(11, env={'rain': 1, 'outside': 1, 'lamps': .6, 'panels': .06, 'neon': .15}, shake=.15, camera=cam(_k(0, [1.2, 1.4, 3.], [-6., 1.7, 12.], 56), _k(d(11), [1.3, 1.4, 3.], [-6., 1.7, 12.], 56)))
    # S12 next to the door, outside, dark glass
    add(12, env={'rain': 1, 'outside': 1, 'lamps': .5, 'panels': .2, 'neon': .2}, shake=.12, camera=cam(_k(0, [3.4, 1.5, 1.], [.9, 1.5, 3.7], 58), _k(d(12), [3.1, 1.5, 1.3], [.9, 1.5, 3.7], 58)),
        tracks={'ghost': hold([1.0, 0, 4.4], 3.3)})
    # S13 the door frame, then the clerk steps in, frightened; his torso and the flashlight
    add(13, env={'rain': 1, 'outside': 1, 'lamps': .5, 'panels': .2}, shake=.15, camera=cam(_k(0, [.4, 1.6, .3], [1.2, 1.5, 3.5], 58), _k(d(13) * .45, [.4, 1.6, .3], [.1, 1.55, -.6], 52), _k(d(13), [.4, 1.2, .5], [.0, 1.15, -.6], 46)),
        tracks={'clerk': [dict(t=0, p=[-.1, 0, -.9], yaw=0, face='scared')], 'ghost': hold([1.4, 0, 5.2], 3.3)})
    # S14 outside: the flashlight on the figure, who steps back
    add(14, env={'rain': 1, 'outside': 1, 'lamps': .6, 'neon': .8, 'panels': .5}, shake=.2, camera=cam(_k(0, [2.6, 1.4, 9.5], [0., 1.6, 4.6], 58), _k(d(14), [2.3, 1.4, 9.], [0., 1.6, 4.6], 58)),
        tracks={'clerk': hold([1.6, 0, 6.2], -2.27, face='scared', gesture='point', gw=.5), 'ghost': [dict(t=0, p=[-.3, 0, 4.7], yaw=.9), dict(t=d(14), p=[-.9, 0, 3.9], yaw=.9)]},
        spots=[{'from': {'on': 'clerk', 'h': 1.15, 'fwd': .3}, 'to': {'on': 'ghost', 'h': 1.3}, 'i': 34, 'angle': .32, 'dist': 14}])
    # S15 over the shoulder, shop behind
    add(15, env={'rain': 1, 'outside': 1, 'lamps': .6, 'neon': .6, 'panels': 1}, shake=.2, camera=cam(_k(0, [-.5, 1.5, 7.2], [.5, 1.4, 3.4], 56), _k(d(15), [-.3, 1.5, 7.], [.5, 1.4, 3.4], 56)),
        tracks={'clerk': hold([.4, 0, 6.0], 3.1416, face='scared')})
    # S16 wide on the figure lit by the beam, under the shop sign
    add(16, env={'rain': 1, 'outside': 1, 'lamps': .6, 'neon': .9, 'panels': 1}, shake=.15, camera=cam(_k(0, [.2, .7, 11.], [0., 1.7, 4.5], 54), _k(d(16), [.1, .75, 10.2], [0., 1.7, 4.5], 54)),
        tracks={'ghost': hold([0., 0, 6.4], 0.)}, spots=[{'from': [1.2, 1.2, 9.], 'to': {'on': 'ghost', 'h': 1.2}, 'i': 40, 'angle': .35, 'dist': 14}])
    # S17 high angle, the beam and the figure's shadow on the wet lot
    add(17, env={'rain': 1, 'outside': 1, 'lamps': .6, 'neon': .9, 'panels': 1}, shake=.2, camera=cam(_k(0, [3., 2.9, 7.5], [-.5, .8, 4.8], 58), _k(d(17), [2.6, 2.7, 7.], [-.5, .8, 4.8], 58)),
        tracks={'ghost': hold([-.6, 0, 5.], .3)}, spots=[{'from': [3., 2.2, 8.], 'to': {'on': 'ghost', 'h': .8}, 'i': 40, 'angle': .35, 'dist': 14}])
    # S18-S20 the ceiling: a dark square, then a flash, then a pale duct crossing it
    ceil = [{'type': 'boxes', 'boxes': [{'x': 2.0, 'y': 3.17, 'z': -1.5, 'w': .8, 'h': .05, 'd': .8, 'color': 0x08080a}, {'x': 2.0, 'y': 3.14, 'z': -1.5, 'w': .95, 'h': .04, 'd': .95, 'color': 0xd8d8d0},
            {'x': 0.9, 'y': 3.02, 'z': -.9, 'w': .32, 'h': .22, 'd': 5., 'color': 0xcfc6ac, 'ry': .6}]}]
    add(18, env={'rain': 1, 'outside': 0, 'panels': .12}, shake=.18, camera=cam(_k(0, [.5, 1.7, .2], [1.8, 3.15, -1.4], 64), _k(d(18), [.6, 1.7, .1], [1.8, 3.15, -1.4], 64)), props=ceil)
    add(19, env={'rain': 1, 'outside': 0, 'panels': .12}, shake=.18, camera=cam(_k(0, [.3, 1.8, .3], [1.6, 3.2, -1.2], 64), _k(d(19), [.8, 1.9, .0], [1.6, 3.2, -1.2], 64)), props=ceil,
        lights=[{'at': [1.2, 2.7, -.9], 'color': 0xfff2c8, 'i': A(19, (0, 2.5), (1.4, 1.8), (1.8, .8)), 'dist': 6}])
    add(20, env={'rain': 1, 'outside': 0, 'panels': .1}, shake=.15, camera=cam(_k(0, [.7, 1.9, .0], [1.6, 3.2, -1.2], 64), _k(d(20), [1.1, 2.0, -.3], [1.4, 3.2, -1.2], 60)), props=ceil)
    # S21-S23 the lights go out one by one, then the clerk by the pump
    dying = A(21, (0, 1), (.7, 1), (.75, .15), (1.4, .15), (1.45, .02), (2.2, .02))
    add(21, env={'rain': 1, 'outside': 1, 'lamps': dying, 'neon': A(21, (0, .8), (.7, .8), (.75, .1), (1.5, .02)), 'panels': A(21, (0, 1), (.5, 1), (.55, .05)), 'car': .6}, shake=.2,
        camera=cam(_k(0, [-5.4, 1.1, 17.8], [-10.5, 1.4, 10.5], 60), _k(d(21), [-5.8, 1.1, 17.2], [-10.5, 1.4, 10.5], 60)), props=[{'use': 'pump_displays'}])
    add(22, env={'rain': 1, 'outside': 1, 'lamps': .08, 'neon': .05, 'panels': .02, 'car': 1}, shake=.2, camera=cam(_k(0, [-7.3, 1.5, 16.9], [-10.2, 1.3, 10.6], 58), _k(d(22), [-7.2, 1.5, 16.5], [-10.2, 1.3, 10.6], 58)),
        tracks={'clerk': hold([-7.5, 0, 15.5], -2.43)})
    add(23, env={'rain': 1, 'outside': 1, 'lamps': .08, 'neon': .05, 'panels': .02, 'car': 1}, shake=.15, camera=cam(_k(0, [-4., 1.5, 17.5], [-4., 1.25, 14.], 54), _k(d(23), [-4., 1.5, 17.], [-4., 1.25, 14.], 52)),
        tracks={'clerk': [dict(t=0, p=[-4., 0, 14.2], yaw=0, face='surprised', gesture='hold', gw=.6), dict(t=1., p=[-4., 0, 14.2], yaw=0, face='scared')]},
        spots=[{'from': {'on': 'clerk', 'h': 1.1, 'fwd': .3}, 'to': [-4., .2, 6.], 'i': 20, 'angle': .3, 'dist': 12}])
    # S24-S26 the reserve door (green), the sign
    door_env = {'rain': 0, 'outside': 0, 'panels': .12, 'lamps': 0}
    add(24, env=door_env, shake=.15, camera=cam(_k(0, [3.5, 1.4, -5.2], [3.4, 1.3, -7.], 50), _k(d(24), [3.5, 1.4, -5.5], [3.4, 1.3, -7.], 50)),
        props=[{'use': 'reserve_door'}, {'type': 'sign', 'text': '', 'at': [2.75, 2.45, -6.9], 'w': .5, 'h': .3, 'bg': '#6aa8ff', 'emit': 1.6}])
    add(25, env=door_env, shake=.15, camera=cam(_k(0, [3.45, 1.3, -5.7], [3.45, 1.2, -7.], 40), _k(d(25), [3.45, 1.3, -5.9], [3.45, 1.2, -7.], 40)), props=[{'use': 'reserve_door'}])
    add(26, env=door_env, shake=.1, camera=cam(_k(0, [3.45, 1.95, -5.9], [3.45, 2.0, -7.], 40), _k(d(26), [3.45, 1.95, -6.1], [3.45, 2.0, -7.], 40)), props=[{'use': 'reserve_door'}])
    # S27 behind the building: the exit sign and the figure who went around
    add(27, env={'rain': 1, 'outside': 1, 'lamps': 0, 'panels': .05, 'car': 0, 'rain_zone': [-1e4, -1e4, 1e4, 1e4]}, shake=.2, camera=cam(_k(0, [2.0, 1.5, -9.7], [3.4, 2., -7.2], 56), _k(d(27), [2.4, 1.5, -9.4], [3.4, 2., -7.2], 56)),
        tracks={'ghost': [dict(t=0, p=[1.0, 0, -8.6], yaw=0), dict(t=d(27), p=[2.2, 0, -8.2], yaw=0)]}, props=[{'use': 'back_sign'}, {'use': 'reserve_door'}],
        lights=[{'at': [3.4, 2.9, -7.8], 'color': 0xcfe8ff, 'i': 3, 'dist': 6}])
    # S28-S30 the electrical plan: dolly towards the poster, then a very tight shot
    add(28, env={'rain': 0, 'outside': 0, 'panels': .35}, shake=.15, camera=cam(_k(0, [1.9, 1.5, -2.6], [4.4, 1.5, -3.4], 56), _k(d(28), [2.2, 1.5, -2.8], [4.4, 1.5, -3.4], 54)),
        tracks={'clerk': hold([3.0, 0, -1.7], 1.5708, face='determined')}, props=[{'use': 'poster'}])
    add(29, env={'rain': 0, 'outside': 0, 'panels': .35}, shake=.1, camera=cam(_k(0, [2.7, 1.5, -3.0], [4.4, 1.5, -3.4], 48), _k(d(29), [3., 1.5, -3.1], [4.4, 1.5, -3.4], 46)),
        tracks={'clerk': hold([3.1, 0, -1.8], 1.5708, face='determined')}, props=[{'use': 'poster'}])
    add(30, env={'rain': 0, 'outside': 0, 'panels': .35}, shake=.06, camera=cam(_k(0, [3.4, 1.5, -3.3], [4.4, 1.5, -3.4], 38), _k(d(30), [3.8, 1.5, -3.38], [4.4, 1.5, -3.4], 34)), props=[{'use': 'poster'}])
    # S31 the breaker box, in the reserve (a small room built from props)
    room = [{'type': 'room', 'at': [14, 0, -4], 'size': [4, 2.6, 3.5], 'wall': 0x4a4660, 'floor': 0x24222c, 'ceil': 0x34323e},
            {'type': 'breaker_box', 'at': [14, 1.5, -5.7], 'w': .6, 'h': .85, 'anim': {'lever': A(31, (0, 0), (1.2, 0), (1.9, 1))}}]
    add(31, env={'rain': 0, 'outside': 0, 'panels': .0, 'lamps': 0}, shake=.12, camera=cam(_k(0, [14.1, 1.5, -2.3], [14., 1.45, -5.7], 52), _k(d(31), [14.1, 1.5, -2.6], [14., 1.45, -5.7], 50)),
        tracks={'clerk': hold([14.9, 0, -3.6], 3.1416)}, props=room, lights=[{'at': [14, 2.3, -4], 'color': 0x9a8ac0, 'i': 2.6, 'dist': 7}])
    # S32 clerk's face next to the plan: "un oeil dehors"
    add(32, env={'rain': 0, 'outside': 0, 'panels': .3}, shake=.1, camera=cam(_k(0, [2.7, 1.7, -1.5], [3., 1.65, -4.], 44), _k(d(32), [2.8, 1.7, -1.6], [3., 1.65, -4.], 44)),
        tracks={'clerk': [dict(t=0, p=[3., 0, -3.3], yaw=0, face='determined'), dict(t=.8, p=[3., 0, -3.3], yaw=0, face='worried')]}, props=[{'use': 'poster'}])
    # S33 a lamp still lit, outside in the rain, from inside the dark shop
    add(33, env={'rain': 1, 'outside': 1, 'lamps': 1, 'panels': .03, 'neon': .05}, shake=.2, camera=cam(_k(0, [-1.8, 1.5, 2.5], [4.5, 4.0, 10.], 40), _k(d(33), [-1.6, 1.5, 2.6], [4.5, 4.1, 10.], 40)),
        props=[{'type': 'sign', 'text': '', 'at': [4.5, 4.2, 10.], 'yaw': -2.44, 'w': 1.1, 'h': .28, 'bg': '#fff1c8', 'emit': 3}])
    # S34 the car in the dark lot, the beam sweeping
    add(34, env={'rain': 1, 'outside': 1, 'lamps': .3, 'panels': .03, 'neon': .1, 'car': 1}, shake=.25, camera=cam(_k(0, [1.8, 1.35, 3.], [4.6, 1., 8.2], 44), _k(d(34), [2.2, 1.35, 3.1], [4.2, 1., 8.2], 44)),
        spots=[{'from': [1.6, 1.3, 2.8], 'to': [4.6, .4, 7.5], 'i': 30, 'angle': .22, 'dist': 14}])
    # S35 low among the shelves; lit again
    add(35, env={'rain': 1, 'outside': 0, 'panels': .6, 'ambient': .7}, shake=.12, camera=cam(_k(0, [1., .6, 1.6], [-1.8, .9, -2.2], 60), _k(d(35), [.7, .65, 1.4], [-1.6, 1., -2.4], 60)))
    # S36 the reserve door creaks open: a black hand in the gap
    add(36, env={'rain': 0, 'outside': 0, 'panels': .5, 'gain': 1.7}, shake=.1, camera=cam(_k(0, [3.2, 1.45, -5.2], [3.6, 1.3, -6.9], 44), _k(d(36), [3.3, 1.45, -5.5], [3.6, 1.3, -6.9], 40)),
        props=[{'type': 'door', 'at': [3.45, 0, -6.86], 'w': .95, 'h': 2.1, 'color': 0x8a909a, 'stripe': 0x70767e, 'hinge': 'l', 'maxOpen': .5, 'anim': {'open': A(36, (0, .05), (1.0, .25), (2.4, .5))}},
               {'type': 'hand', 'at': [3.78, 1.0, -6.72], 'scale': 1.0, 'rot': [0, 3.1416, 0], 'anim': {'curl': A(36, (0, .9), (2.4, .2))}}])
    # S37 the ceiling tube flickers; green screen low in frame
    add(37, env={'rain': 0, 'outside': 0, 'panels': .08}, shake=.12, camera=cam(_k(0, [3., 1.2, .6], [.8, 3., -1.], 62), _k(d(37), [2.8, 1.3, .6], [.8, 3., -1.], 62)),
        props=[{'type': 'tube', 'at': [1.0, 3.12, -1.0], 'len': 1.5, 'rot': [0, .5, 0], 'anim': {'on': A(37, (0, 1), (.4, 1), (.43, .1), (.6, .1), (.63, 1), (1.1, 1), (1.13, .1), (1.2, .1), (1.23, 1))}}])
    # S38 clerk close up: "maintenant" (shout)
    add(38, env={'rain': 0, 'outside': 0, 'panels': .9}, shake=.12, dof=.5, camera=cam(_k(0, [.2, 1.62, 1.05], [.2, 1.6, 0.], 36), _k(d(38), [.2, 1.62, .9], [.2, 1.6, 0.], 36)),
        tracks={'clerk': [dict(t=0, p=[.2, 0, 0.], yaw=0, face='surprised'), dict(t=.9, p=[.2, 0, 0.], yaw=0, face='scream', talk=1)]})
    # S39 the choice: low among the shelves, slow drift
    add(39, env={'rain': 0, 'outside': 0, 'panels': [[round(T[39], 4), .6], [round(T[39] + 4., 4), .6], [round(T[39] + 5., 4), .25]], 'ambient': .7}, shake=.1,
        camera=cam(_k(0, [1., .6, 1.6], [-1.8, .9, -2.2], 60), _k(d(39), [.5, .72, 1.3], [-1.6, 1.05, -2.5], 60)))
    # S40 branch B preview: running for the car through the dark, forward move
    add(40, env={'rain': 1, 'outside': 1, 'lamps': .15, 'panels': .02, 'neon': .05, 'car': 1}, shake=.4, camera=cam(_k(0, [.2, 1.3, 3.2], [4.2, 1., 8.5], 58), _k(d(40), [.9, 1.3, 5.4], [4.4, .9, 8.4], 58)),
        props=[{'type': 'hand', 'at': [.6, .05, 4.6], 'scale': 1.1, 'rot': [1.2, 0, 0], 'curl': .6}, {'type': 'hand', 'at': [1.4, .05, 5.0], 'scale': 1., 'rot': [1.2, .4, 0], 'curl': .6}])
    # S41 the green monitor on the counter, lights flickering
    add(41, env={'rain': 0, 'outside': 0, 'panels': A(41, (0, .5), (1.2, .5), (1.25, .08), (1.6, .08), (1.65, .5), (2.8, .5), (2.85, .06))}, shake=.12, camera=cam(_k(0, [2.2, 1.3, 1.], [3.4, 1.4, .2], 50), _k(d(41), [2.4, 1.55, .9], [3.2, 1.9, .3], 50)))
    # S42 the station from the lot with its sign; the end card covers it
    add(42, env={'rain': 1, 'outside': 1, 'lamps': .9, 'neon': 1, 'panels': .5}, shake=.1, camera=cam(_k(0, [2., 1.7, 24.], [0., 2.8, 4.], 58), _k(d(42), [1., 1.7, 21.], [0., 2.8, 4.], 58)), props=[{'use': 'title_sign'}])
    add(43, env={'rain': 1, 'outside': 1, 'lamps': .9, 'neon': 1, 'panels': .5}, camera=cam(_k(0, [1., 1.7, 21.], [0., 2.8, 4.], 58)), props=[{'use': 'title_sign'}])
    return shots


def hud():
    return {'x': .04, 't_end': T[43], 'title': [{'text': 'LA DERNIÈRE', 'color': '#f2f2f2', 'cw': .0385, 'y': .035}, {'text': 'POMPE', 'color': '#f2392d', 'cw': .0406, 'y': .0605}, {'text': 'PARTIE 1', 'color': '#e8483c', 'cw': .0234, 'y': .0895}],
            'corner': {'clock': [{'t': 0, 'text': '02:00'}, {'t': 60., 'text': '02:01'}],
                       'battery': [{'t': 0, 'bars': 3}, {'t': 1110 / FPS, 'bars': 2}, {'t': 2010 / FPS, 'bars': 1, 'color': '#e8352c', 'blink': 10 / FPS}]}}


def cards():
    """choice card (A / B) over the shop, then the end card; selection flips measured on the source (analyse/pompe/choice.json)"""
    opts = [{'key': 'A', 'lines': ['ENTRER DANS', 'LA RÉSERVE'], 'x0': .066, 'x1': .86, 'y0': .585, 'y1': .657}, {'key': 'B', 'lines': ['COURIR JUSQU\'À', 'LA VOITURE'], 'x0': .066, 'x1': .86, 'y0': .673, 'y1': .747}]
    f = Path(__file__).resolve().parents[3] / 'examples' / 'remakes' / 'pompe_choice.json'
    sel = json.loads(f.read_text(encoding='utf-8')) if f.exists() else [{'t': T[39], 'i': 0}]
    return [{'kind': 'choice', 't0': T[39], 't1': T[43], 'question': {'text': 'QUE FAIS-TU ?', 'x0': .066, 'x1': .86, 'y0': .172, 'y1': .234}, 'options': opts, 'sel': sel},
            {'kind': 'endcard', 't0': T[43], 't1': DUR, 'lines': [
                {'text': 'LA DERNIÈRE', 'color': '#f2f2f2', 'cw': .0658, 'y': .214}, {'text': 'POMPE', 'color': '#f2392d', 'cw': .1, 'y': .279}, {'text': 'PARTIE 1', 'color': '#c8c8c8', 'cw': .033, 'y': .357},
                {'text': 'A OU B ?', 'color': '#f2f2f2', 'cw': .088, 'y': .469}, {'text': 'COMMENTE TON CHOIX', 'color': '#f2392d', 'cw': .033, 'y': .549}, {'text': 'LA SUITE DÉPEND DE TOI', 'color': '#e0e0e0', 'cw': .0276, 'y': .584}],
                'button': {'text': 'ABONNE-TOI', 'x0': .204, 'x1': .796, 'y0': .667, 'y1': .713}}]


def episode():
    caps = json.loads(CAPTIONS.read_text(encoding='utf-8')) if CAPTIONS.exists() else []
    for c in caps:
        c.pop('y', None)
        if c['t0'] >= T[39]: c['y'] = .512                    # captions sit lower while the A/B card is up
    return dict(title='La Dernière Pompe — partie 1 (remake VOXELGPU)', genre='horror', aspect='9:16', fps=FPS, duration=DUR, mood='neutral', prop_sets=PROP_SETS,
                casts={'clerk': CLERK, 'ghost': GHOST}, shots=build(), hud=hud(), cards=cards(), captions=caps, caption_style={'cw': .049, 'y': .47, 'hi': '#f2392d'},
                audio={'source': 'LA_DERNIERE_POMPE_partie1_sans_miniature.mp4'})
