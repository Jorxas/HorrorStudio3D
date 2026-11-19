"""« Ne touche pas le sol », partie 4 (101,433 s, 9:16, 30 fps) : remake in 3D of a given video, shot for shot, on the unified engine.

Same method as remake_pompe.py: the cuts, subtitles, HUD state and card timing are DATA measured on the source (analyse/sol/); the picture is
rendered by the voxel painter from the scene written here; the audio is the source's own track, muxed untouched. The last second of the source
is a flat 2D thumbnail: it is NOT reused, a 3D poster shot with the same title is rendered instead. Known differences: docs/REMAKES_VOXELGPU.md.
"""
import json
from pathlib import Path
from ...remake.dsl import k as _k, cam, hold, table, pulse

FPS = 30
CUTS = [0, 44, 107, 170, 209, 250, 352, 468, 512, 567, 642, 704, 766, 845, 956, 1004, 1101, 1141, 1205, 1285, 1410, 1452, 1539, 1602, 1746, 1804, 2096, 2175, 2209, 2257, 2361,
        2422, 2480, 2535, 2569, 2620, 2803, 2853, 2872, 3013, 3043]
T = [f / FPS for f in CUTS]
DUR = 3043 / FPS
ROOT = Path(__file__).resolve().parents[3] / 'examples' / 'remakes'
GAIN_FILE = ROOT / 'sol_gain.json'

HERO = {'preset': 'npc', 'variant': 1, 'look': {'skin': 0xf6dcc0, 'brow': 0x100c0a, 'hair': {'style': 'curly', 'color': 0x14100e, 'color2': 0x1c1612}, 'top': {'type': 'jacketOpen', 'color': 0x6a6a74, 'shirt': 0x22222a},
        'pants': {'color': 0x1e2230}, 'shoes': {'type': 'sneaker', 'color': 0x14141a, 'sole': 0xd8d8d4}},
        'extras': [{'bone': 'head', 'at': [-4.6, 0, 0.3], 'boxes': [{'x': 0, 'y': 0, 'z': 0, 'w': 1.4, 'h': 3.6, 'd': 3.2, 'color': 0x101014}, {'x': -.6, 'y': 1, 'z': 1.2, 'w': .5, 'h': .5, 'd': .5, 'color': 0x40e070}]}]}
GIRL = {'preset': 'npc', 'variant': 2, 'scale': .8, 'look': {'skin': 0xf2c4a0, 'hair': {'style': 'long', 'color': 0x8a3a1e, 'color2': 0x9a4a2a}, 'top': {'type': 'hoodie', 'color': 0xe6d63a, 'shirt': 0xe6d63a},
        'pants': {'color': 0xd8689a}, 'shoes': {'type': 'sneaker', 'color': 0xc03030, 'sole': 0xf0f0ee}}}
LADY = {'preset': 'npc', 'variant': 4, 'scale': .92, 'look': {'skin': 0xf0c8a8, 'hair': {'style': 'long', 'color': 0xece8e4, 'color2': 0xf4f0ec}, 'top': {'type': 'coat', 'color': 0xb02828}, 'pants': {'color': 0x3a2a30}, 'shoes': {'type': 'boot', 'color': 0x2a1e22}}}
DRIVER = {'preset': 'npc', 'variant': 5, 'look': {'skin': 0xe2a874, 'hair': None, 'hat': {'type': 'beanie', 'color': 0x1a2040, 'fur': 0x1a2040}, 'top': {'type': 'jacketOpen', 'color': 0x1c2850, 'shirt': 0xe8e8ee}, 'pants': {'color': 0x161a28}}}
MAN = {'preset': 'npc', 'variant': 6, 'look': {'skin': 0x8a5a3a, 'hair': {'style': 'curly', 'color': 0x3a2014, 'color2': 0x4a2c1c}, 'top': {'type': 'hoodie', 'color': 0x8a3030, 'shirt': 0x8a3030}, 'pants': {'color': 0x2a2428}}}
WOMAN = {'preset': 'npc', 'variant': 7, 'look': {'skin': 0xf0c0a0, 'hair': {'style': 'long', 'color': 0xe8c050, 'color2': 0xf0d070}, 'top': {'type': 'hoodie', 'color': 0xe8e04a, 'shirt': 0xe8e04a}, 'pants': {'color': 0xd0709a}}}
CREATURE = {'preset': 'npc', 'kind': 'creature', 'skin': 0xeedcc4, 'creature': {'height': 1.28, 'width': .62, 'head': 1.05}}

TITLE_Y = (.035, .0605, .0895)


def build():
    GAIN = json.loads(GAIN_FILE.read_text(encoding='utf-8')) if GAIN_FILE.exists() else {}
    shots = []; d = lambda i: round(T[i + 1] - T[i], 4)
    A = lambda i, *pairs: table(T[i], *pairs)

    def add(i, stage='bus', **kw):
        s = dict(id=f'S{i:02d}', stage=stage, dur=d(i), **kw)
        g = GAIN.get(s['id'])
        if g is not None and 'gain' not in (s.get('env') or {}): s['env'] = {**(s.get('env') or {}), 'gain': g}
        shots.append(s); return s
    red = lambda r=.75, **kw: {'red': round(r * .5, 3), 'rain': 0, 'drive': 0, **kw}
    btn = lambda i: [{'type': 'alarm_button', 'at': [.1, 1.03, -12.4], 'rot': [-1.25, 0, 0], 'scale': 1.4, 'text': 'ALARM', 'anim': {'on': pulse(T[i], T[i + 1], .5)}}]

    add(0, env=red(.8), shake=.15, camera=cam(_k(0, [.05, 1.45, -8.4], [.1, 1.35, -4.8], 48), _k(d(0), [.05, 1.45, -8.0], [.1, 1.35, -4.8], 48)),
        tracks={'hero': hold([.45, 0, -4.6], 3.1416, face='scared'), 'creature1': hold([-.3, 0, -5.8], 3.1416)})
    add(1, env=red(.7), shake=.1, camera=cam(_k(0, [.1, 1.62, -7.5], [0., 1.58, -9.9], 38), _k(d(1), [.05, 1.62, -7.8], [0., 1.58, -9.9], 38)),
        tracks={'hero': [dict(t=0, p=[0, 0, -9.9], yaw=0, face='neutral', talk=0), dict(t=1., p=[0, 0, -9.9], yaw=0, face='neutral', talk=1)]})
    add(2, env=red(.8, bloom=.15), shake=.1, camera=cam(_k(0, [0., 1.55, -10.8], [.05, 1.6, -12.9], 46), _k(d(2), [.05, 1.55, -11.1], [.05, 1.6, -12.9], 46)),
        props=[{'type': 'sign', 'text': 'SILENCE', 'at': [.1, 2.3, -13.0], 'w': 1.4, 'h': .3, 'col': '#ff3a2a', 'bg': '#100606', 'emit': 1.4}, {'type': 'mirror_eyes', 'at': [.2, 1.95, -12.97], 'w': .7, 'h': .22}] + btn(2))
    add(3, env=red(.8, bloom=.15), shake=.08, camera=cam(_k(0, [.1, 1.5, -12.0], [.1, 1.03, -12.5], 40), _k(d(3), [.1, 1.4, -12.1], [.1, 1.03, -12.5], 38)), props=btn(3))
    add(4, env=red(.85), shake=.15, camera=cam(_k(0, [.2, 1.4, -3.2], [-1.6, 1.5, -3.6], 50), _k(d(4), [.1, 1.4, -3.3], [-1.6, 1.5, -3.6], 50)),
        tracks={'lady': hold([-.55, 0, -2.6], -1.2, face='scared'), 'creature1': hold([-2.6, -.96, -3.8], 1.5708)})
    add(5, env=red(.85), shake=.15, camera=cam(_k(0, [.6, 1.4, -4.2], [-1.5, 1.5, -6.], 50), _k(d(5), [.5, 1.4, -4.6], [-1.5, 1.5, -6.2], 50)),
        tracks={'creature1': hold([-2.5, -.96, -6.2], 1.5708), 'lady': hold([-.4, 0, -3.2], -1.2, face='scared')})
    add(6, env={**red(.6), 'rain': 1}, shake=.2, camera=cam(_k(0, [-.9, 1.5, -7.], [-8., .9, -7.], 50), _k(d(6), [-.9, 1.5, -7.], [-8., .9, -7.4], 50)),
        tracks={f'creature{n}': [dict(t=0, p=[-8. - n * 1.6, -.96, -7. + (n % 3) * 1.4], yaw=1.5708), dict(t=d(6), p=[-6. - n * 1.4, -.96, -7. + (n % 3) * 1.2], yaw=1.5708)] for n in range(1, 6)})
    add(7, env={**red(.6), 'rain': 1}, shake=.2, camera=cam(_k(0, [-.9, 1.4, -6.5], [-5., 1., -6.5], 48), _k(d(7), [-.9, 1.4, -6.5], [-5., 1., -6.6], 48)),
        tracks={f'creature{n}': hold([-3.6 - n * 1.5, -.96, -6.4 + (n % 2) * 1.2], 1.5708) for n in range(1, 5)})
    add(8, env=red(.95), shake=.12, camera=cam(_k(0, [.9, 1.6, -4.7], [0., 1.55, -7.2], 34), _k(d(8), [.8, 1.6, -4.9], [0., 1.55, -7.2], 34)),
        tracks={'hero': [dict(t=0, p=[0, 0, -7.2], yaw=.5, face='worried', head=[.5, 0]), dict(t=1., p=[0, 0, -7.2], yaw=.5, face='scared', head=[.5, 0], talk=1)]})
    add(9, env=red(.8), shake=.12, camera=cam(_k(0, [0., 1.4, -1.], [0., 1.2, -9.], 56), _k(d(9), [0., 1.4, -2.2], [0., 1.2, -9.], 56)), tracks={'man': hold([0, 0, -8.6], 0., face='scared')})
    add(10, env=red(.8), shake=.15, camera=cam(_k(0, [0., .9, -1.4], [0., 1.1, -8.], 56), _k(d(10), [0., .8, -2.4], [0., 1.1, -8.], 56)))
    hatch = [{'type': 'boxes', 'boxes': [{'x': 0, 'y': 2.36, 'z': -8., 'w': 1.0, 'h': .06, 'd': 1.0, 'color': 0xd8a02a}, {'x': 0, 'y': 2.34, 'z': -8., 'w': .8, 'h': .06, 'd': .8, 'color': 0x201a18}, {'x': 0, 'y': 2.3, 'z': -7.45, 'w': .22, 'h': .08, 'd': .22, 'color': 0xe02a1e}]}]
    ladder = [{'type': 'boxes', 'boxes': [{'x': sx * .22, 'y': 1.2, 'z': -7.1 - .5 * 0, 'w': .05, 'h': 2.4, 'd': .05, 'color': 0x101012, 'rx': .5} for sx in (-1, 1)] + [{'x': 0, 'y': .3 + r * .26, 'z': -6.5 - r * .2, 'w': .5, 'h': .04, 'd': .05, 'color': 0x16161a} for r in range(8)]}]
    add(11, env=red(.85), shake=.12, camera=cam(_k(0, [0., 1.6, -6.], [.1, 2.4, -7.6], 52), _k(d(11), [0., 1.7, -6.6], [.1, 2.4, -7.8], 52)), props=hatch + ladder)
    add(12, env=red(.8, rain=.5), shake=.15, camera=cam(_k(0, [0., 1.4, -6.4], [0., 2.5, -8.], 54), _k(d(12), [0., 1.7, -7.2], [0., 2.7, -8.], 54)), props=ladder,
        tracks={'girl': hold([0, 2.0, -7.9], 3.1416, face='scared', gesture='arm_up')})
    add(13, env=red(.9), shake=.15, camera=cam(_k(0, [.5, .7, -6.2], [0., 1.7, -7.6], 54), _k(d(13), [.3, .8, -6.4], [0., 2.3, -7.8], 54)), props=ladder,
        tracks={'girl': [dict(t=0, p=[0, .8, -7.0], yaw=3.1416, face='scared', gesture='arm_up'), dict(t=d(13), p=[0, 2.0, -7.7], yaw=3.1416, face='determined', gesture='arm_up')]})
    add(14, stage='toit', env={'glow': 1}, shake=.15, camera=cam(_k(0, [-1.5, 2.8, 4.], [1.8, .2, .2], 56), _k(d(14), [-1.2, 2.7, 3.8], [1.8, .2, .2], 56)),
        tracks={'hero': hold([1.6, 0, .6], -2.3, face='scared', gesture='reach'), 'girl': hold([2.4, 0, .2], 3.1416, face='scared')})
    add(15, stage='toit', env={'glow': 1}, shake=.15, camera=cam(_k(0, [-.5, 2.5, 3.6], [2.5, .6, 0.], 56), _k(d(15), [-.3, 2.3, 3.4], [2.5, .6, 0.], 56)),
        tracks={'hero': hold([1.4, 0, .8], -2.3, face='scared'), 'girl': hold([2.6, 0, .4], 3.1416, face='scared'), 'lady': hold([3.6, 0, -.3], 3.1416, face='scared')})
    add(16, env=red(1., hands=.3), shake=.15, camera=cam(_k(0, [0., 1.5, -5.], [0., 1.3, -9.], 52), _k(d(16), [0., 1.5, -5.6], [0., 1.3, -9.], 52)), tracks={'creature1': hold([0, 0, -8.6], 0.)})
    add(17, env=red(.95), shake=.12, camera=cam(_k(0, [0., 2.1, -6.3], [0., 2.1, -8.], 44), _k(d(17), [0., 2.12, -6.7], [0., 2.12, -8.], 42)), tracks={'creature1': hold([0, 0, -8.3], 0., head=[0, .05])})
    add(18, env=red(.8, bloom=.15), shake=.08, camera=cam(_k(0, [.1, 1.5, -12.0], [.1, 1.03, -12.5], 40), _k(d(18), [.1, 1.42, -12.15], [.1, 1.03, -12.5], 38)), props=btn(18))
    add(19, stage='toit', env={'glow': 1}, shake=.2, camera=cam(_k(0, [-1.5, 2.4, 4.4], [2.8, .5, -.2], 54), _k(d(19), [-1.2, 2.3, 4.], [2.8, .5, -.2], 54)),
        tracks={'hero': hold([1.5, 0, .8], -2.4, face='scared'), 'girl': hold([2.4, 0, .6], 3.1416, face='scared'), 'lady': hold([3.3, 0, -.2], 3.1416, face='scared'), 'man': hold([3.9, 0, .6], 3.1416, face='scared')})
    add(20, stage='toit', env={'glow': 1}, shake=.2, camera=cam(_k(0, [-.6, .8, 2.4], [1.8, .6, 0.], 50), _k(d(20), [-.4, .8, 2.2], [1.8, .6, 0.], 50)),
        tracks={'hero': [dict(t=0, p=[1.8, 0, 0.], yaw=-1.5708, crouch=.6, face='determined', gesture='knock', gw=1)]})
    add(21, env=red(1.), shake=.1, camera=cam(_k(0, [0., 2.12, -6.9], [0., 2.12, -8.1], 36), _k(d(21), [0., 2.12, -7.2], [0., 2.12, -8.1], 34)), tracks={'creature1': hold([0, 0, -8.3], 0.)})
    add(22, env=red(.85), shake=.1, camera=cam(_k(0, [0., 1.55, -10.4], [0., 1.55, -11.7], 34), _k(d(22), [0., 1.55, -10.6], [0., 1.55, -11.7], 32)),
        tracks={'driver': [dict(t=0, p=[0, 0, -11.75], yaw=0, face='scared'), dict(t=1.2, p=[0, 0, -11.75], yaw=0, face='shout', talk=1)]})
    add(23, env=red(.95), shake=.15, camera=cam(_k(0, [0., 1.5, -2.], [0., 1.3, -9.], 54), _k(d(23), [0., 1.5, -3.5], [0., 1.3, -9.], 54)),
        tracks={'creature1': [dict(t=0, p=[-.3, 0, -8.6], yaw=0), dict(t=d(23), p=[-.3, 0, -6.8], yaw=0)], 'driver': [dict(t=0, p=[.1, 0, -9.4], yaw=0, face='scared'), dict(t=d(23), p=[.1, 0, -6.0], yaw=0, face='determined')]})
    add(24, stage='toit', env={'glow': 1}, shake=.2, camera=cam(_k(0, [-1.4, 2.4, 3.6], [2.4, .5, 0.], 54), _k(d(24), [-1.2, 2.3, 3.4], [2.4, .5, 0.], 54)),
        tracks={'hero': hold([1.4, 0, .5], -1.2, face='scared', gesture='reach'), 'girl': hold([2.8, 0, -.1], 3.1416, face='scared', gesture='reach')})
    # S25 .. S37 : outside, on the grass, bus on the road, tunnel far
    add(25, stage='talus', env={'rain': 1, 'tubes': .5}, shake=.15, camera=cam(_k(0, [10., 1.8, 16.], [-1., 1.2, -6.], 50), _k(d(25), [9., 1.8, 15.], [-1., 1.2, -6.], 50)),
        tracks={'hero': hold([8., 0, 3.5], 2.4, face='scared'), 'girl': hold([7.2, 0, 4.2], 2.4, face='scared'), **{f'creature{n}': [dict(t=0, p=[-28. - n * 3, 0, -6.2], yaw=1.5708), dict(t=d(25), p=[-14. - n * 3, 0, -6.2], yaw=1.5708)] for n in range(1, 5)}})
    add(26, stage='talus', env={'rain': 1}, shake=.2, camera=cam(_k(0, [2., .5, 4.5], [1., .6, 1.], 56), _k(d(26), [2.2, .5, 4.], [1., .6, 1.], 56)),
        tracks={'hero': [dict(t=0, p=[.6, 0, 1.2], yaw=3.1416), dict(t=d(26), p=[.4, 0, 1.4], yaw=3.1416)], 'lady': [dict(t=0, p=[1.4, 0, 1.4], yaw=3.1416), dict(t=d(26), p=[1.3, 0, 1.6], yaw=3.1416)]})
    add(27, stage='talus', env={'rain': 1}, shake=.1, camera=cam(_k(0, [2., 1.6, 4.2], [2., 1.55, 2.5], 36), _k(d(27), [2., 1.6, 4.], [2., 1.55, 2.5], 36)), tracks={'hero': hold([2., 0, 2.5], 0., face='worried')})
    add(28, stage='talus', env={'rain': 1, 'tubes': .5}, shake=.15, camera=cam(_k(0, [-2., 1.2, 4.], [2., 1.4, -6.], 52), _k(d(28), [-1., 1.2, 4.], [3., 1.4, -6.], 52)),
        tracks={'creature1': hold([-6.5, 0, -8.6], 1.5708)})
    add(29, stage='talus', env={'rain': 1, 'tubes': .5}, shake=.15, camera=cam(_k(0, [-4., 1.6, 3.], [-4., 2.2, -7.5], 48), _k(d(29), [-3., 1.5, 2.5], [-3., 2.0, -7.5], 48)),
        tracks={'creature1': hold([-3.2, 0, -9.0], 3.1416, head=[0, .1])})
    add(30, stage='talus', env={'rain': 1}, shake=.25, camera=cam(_k(0, [1., .45, 3.], [1., .6, 0.4], 52), _k(d(30), [1.2, .45, 2.8], [1., .6, 0.4], 52)),
        tracks={'woman': [dict(t=0, p=[.8, 0, 0.4], yaw=3.1416), dict(t=d(30), p=[.8, 0, 1.0], yaw=3.1416)], 'man': [dict(t=0, p=[1.7, 0, .4], yaw=3.1416), dict(t=d(30), p=[1.7, 0, 1.0], yaw=3.1416)]})
    add(31, stage='talus', env={'rain': 1, 'tubes': .5}, shake=.2, camera=cam(_k(0, [4., 1.5, 7.], [2.5, 1., 1.], 50), _k(d(31), [4., 1.5, 6.4], [2.5, 1., 1.], 50)),
        tracks={'woman': [dict(t=0, p=[1.4, 0, 1.6], yaw=3.1416), dict(t=d(31), p=[1.6, 0, 3.4], yaw=3.1416)], 'girl': [dict(t=0, p=[2.2, 0, 1.8], yaw=3.1416), dict(t=d(31), p=[2.2, 0, 3.6], yaw=3.1416)]})
    add(32, stage='talus', env={'rain': 1}, shake=.2, camera=cam(_k(0, [1.5, 1.5, 6.5], [1.5, 1.2, 2.], 50), _k(d(32), [1.5, 1.5, 6.], [1.5, 1.2, 2.], 50)),
        tracks={'hero': [dict(t=0, p=[1., 0, 2.], yaw=0, face='scared'), dict(t=d(32), p=[1., 0, 3.4], yaw=0, face='scared')], 'driver': [dict(t=0, p=[2.2, 0, 1.6], yaw=0, face='scared'), dict(t=d(32), p=[2.2, 0, 3.0], yaw=0)],
                'woman': [dict(t=0, p=[.2, 0, 2.2], yaw=0), dict(t=d(32), p=[.2, 0, 3.6], yaw=0)]})
    add(33, stage='talus', env={'rain': 1}, shake=.2, camera=cam(_k(0, [3., 1.5, 7.], [2., 1.2, 2.], 50), _k(d(33), [3., 1.5, 6.6], [2., 1.2, 2.], 50)),
        tracks={'woman': [dict(t=0, p=[1.6, 0, 3.0], yaw=0), dict(t=d(33), p=[1.7, 0, 4.2], yaw=0)], 'girl': [dict(t=0, p=[2.4, 0, 3.2], yaw=0), dict(t=d(33), p=[2.4, 0, 4.4], yaw=0)], 'lady': [dict(t=0, p=[.8, 0, 3.0], yaw=0), dict(t=d(33), p=[.8, 0, 4.2], yaw=0)]})
    add(34, stage='talus', env={'rain': 1}, shake=.2, camera=cam(_k(0, [1.4, 1.2, 5.6], [1.4, 1.0, 3.], 52), _k(d(34), [1.4, 1.2, 5.3], [1.4, 1.0, 3.], 52)),
        tracks={'girl': hold([1.4, 0, 3.6], 0., face='relief'), 'woman': hold([.6, 0, 3.4], 0.)})
    add(35, stage='talus', env={'rain': 1, 'tubes': .5}, shake=.12, camera=cam(_k(0, [4., 1.8, 12.], [3., 1.6, -6.], 50), _k(d(35), [4., 2.2, 20.], [3., 1.4, -6.], 50)),
        tracks={'hero': hold([1.4, 0, 8.], 0., face='relief'), 'girl': hold([2.2, 0, 8.4], 0.), 'lady': hold([.6, 0, 8.6], 0.)})
    add(36, stage='talus', env={'rain': 1}, shake=.1, camera=cam(_k(0, [2., 1.7, 5.4], [2., 1.65, 3.8], 34), _k(d(36), [2., 1.7, 5.2], [2., 1.65, 3.8], 34)),
        tracks={'hero': [dict(t=0, p=[2., 0, 3.8], yaw=0, face='neutral'), dict(t=1., p=[2., 0, 3.8], yaw=0, face='relief')]})
    add(37, stage='talus', env={'rain': 1, 'tubes': .4}, shake=.08, camera=cam(_k(0, [4., 1.6, 30.], [0., 1.2, -6.], 40), _k(d(37), [4., 1.6, 29.], [0., 1.2, -6.], 40)))
    add(38, stage='talus', env={'rain': 1, 'tubes': .4}, camera=cam(_k(0, [4., 1.6, 29.], [0., 1.2, -6.], 40)))
    # S39: the poster, in 3D (the source has a flat illustration there)
    add(39, env={'red': 1., 'hands': 1., 'rain': 0}, shake=.05, camera=cam(_k(0, [0., 1.5, -4.], [0., 1.4, -6.], 44), _k(d(39), [0., 1.5, -4.3], [0., 1.4, -6.], 44)),
        tracks={'hero': hold([.5, 0, -6.2], 3.1416, face='scared'), 'girl': hold([-.45, 0, -6.], 3.1416, face='scared')})
    return shots


def hud():
    return {'x': .04, 't_end': T[38], 'title': [{'text': 'NE TOUCHE', 'color': '#f2f2f2', 'cw': .037, 'y': TITLE_Y[0]}, {'text': 'PAS LE SOL', 'color': '#f2392d', 'cw': .037, 'y': TITLE_Y[1]},
            {'text': 'PARTIE 4', 'color': '#e8483c', 'cw': .0234, 'y': TITLE_Y[2]}],
            'corner': {'clock': [{'t': 0, 'text': '23:52'}, {'t': 60., 'text': '23:53'}], 'hearts': [{'t': 0, 'full': 2, 'total': 3}]}}


def cards():
    opts = [{'key': 'A', 'lines': ['SORTIR', 'SANS UN BRUIT'], 'x0': .066, 'x1': .934, 'y0': .75, 'y1': .828}, {'key': 'B', 'lines': ['DÉCLENCHER', "L'ALARME"], 'x0': .066, 'x1': .934, 'y0': .846, 'y1': .922}]
    return [{'kind': 'choice', 't0': 0., 't1': T[1], 'question': {'text': 'TU AS CHOISI :', 'x0': .066, 'x1': .934, 'y0': .197, 'y1': .27}, 'options': opts, 'sel': [{'t': 0, 'i': 1}]},
            {'kind': 'endcard', 't0': T[38], 't1': T[39], 'fade_out': .5, 'lines': [
                {'text': 'NE TOUCHE', 'color': '#f2f2f2', 'cw': .0664, 'y': .205}, {'text': 'PAS LE SOL', 'color': '#f2392d', 'cw': .083, 'y': .267}, {'text': 'PARTIE 4', 'color': '#c8c8c8', 'cw': .033, 'y': .346},
                {'text': 'FIN', 'color': '#e8e0d0', 'cw': .109, 'y': .474}, {'text': 'VOUS AVEZ SURVÉCU', 'color': '#f2392d', 'cw': .033, 'y': .555}, {'text': "MERCI D'AVOIR CHOISI", 'color': '#e0e0e0', 'cw': .0278, 'y': .589}],
                'button': {'text': 'ABONNE-TOI', 'x0': .204, 'x1': .796, 'y0': .677, 'y1': .723}},
            {'kind': 'endcard', 't0': T[39], 't1': DUR, 'bg': None, 'lines': [
                {'text': 'LE DERNIER BUS', 'color': '#f2f2f2', 'cw': .028, 'y': .03, 'stroke': .004}, {'text': 'NE TOUCHE', 'color': '#f4f4f4', 'cw': .105, 'y': .1, 'stroke': .01},
                {'text': 'PAS LE SOL', 'color': '#f2392d', 'cw': .1, 'y': .17, 'stroke': .01}, {'text': 'PARTIE 4', 'color': '#f4f4f4', 'cw': .075, 'y': .9, 'stroke': .01}]}]


def episode():
    caps = json.loads((ROOT / 'sol_captions.json').read_text(encoding='utf-8')) if (ROOT / 'sol_captions.json').exists() else []
    for c in caps: c.pop('y', None)
    casts = {'hero': HERO, 'girl': GIRL, 'lady': LADY, 'driver': DRIVER, 'man': MAN, 'woman': WOMAN, **{f'creature{n}': CREATURE for n in range(1, 6)}}
    return dict(title='Ne touche pas le sol — partie 4 (remake VOXELGPU)', genre='horror', aspect='9:16', fps=FPS, duration=DUR, mood='neutral', casts=casts, shots=build(), hud=hud(), cards=cards(),
                captions=caps, caption_style={'cw': .049, 'y': .47, 'hi': '#f2392d'}, audio={'source': 'NE_TOUCHE_PAS_LE_SOL_partie4.mp4'})
