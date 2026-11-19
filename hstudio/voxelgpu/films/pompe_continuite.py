"""« La Dernière Pompe », partie 1 : la même histoire, la même piste son, les mêmes coupes (44 plans, 96,467 s, 9:16, 30 fps) mais dans UN lieu continu.

What changed against `remake_pompe.py` (kept untouched as the counter-example) and why:
  * the story is a BLOCKING (hstudio/voxelgpu/blocking.py): one trajectory per actor for the whole film, in absolute time, planned on the real
    geometry of the place (stagegeo.station: walls, counter, shelves, car, pumps, the back room, the doors). The shots only choose a camera.
  * the clerk stays INSIDE the shop for the whole film (the narration says "tu verrouilles la porte"); the faceless man stays OUTSIDE until he
    walks round the building to the service door, goes in through it, and waits behind the inner door. Nobody crosses a wall.
  * the back room is a real room (reserve.js) behind the shop's back wall, recognisable by its fittings, with no label on screen.
  * the world is one: doors, lights, car, torch are tables in absolute time shared by every shot (`world_env`, `world_props`).
  * the camera says WHAT MUST BE SEEN (`frame`): the car whole when the narration is about the car, the door in its surroundings, no zoom.
Every cut of the source is kept (the same CUTS), so captions, HUD and the source's own audio track line up as before.
"""
import json, math
from pathlib import Path
from ...remake.dsl import k as _k, cam
from . import remake_pompe as OLD
from .. import stagegeo, blocking as BLK, camplan as CP

FPS, CUTS, T, DUR = OLD.FPS, OLD.CUTS, OLD.T, OLD.DUR
d = lambda i: round(T[i + 1] - T[i], 4)
A = lambda *pairs: [[round(t, 4), v] for t, v in pairs]

# ---------------------------------------------------------------------------------------------------------------------- the world, in absolute time
DOORS = {'reserve': A((0, 0), (69.2, 0), (70.6, .5)),              # the inner door creaks to a gap of ~20 cm at 69-70.6 s and stays there
         'service': A((0, 0), (52.6, 0), (53.6, 1)),               # the service door is pushed open from outside at 52.6 s
         'entree': A((0, 0))}                                      # locked all along
KNOCKS = [47.2, 48.7, 50.3]
PANELS = A((0, 1), (24.9, 1), (25.0, .1), (25.2, 1), (25.5, .15), (25.7, 1), (26.0, .1), (27.3, .1), (27.4, .7), (37.0, .7), (37.1, .3), (72.6, .3), (72.7, .05), (72.9, .5), (73.1, .05), (73.5, .5), (73.7, .08), (74.6, .12), (88.2, .12), (88.3, .02))
NEON = A((0, .3), (24.9, .3), (25.0, .03), (25.2, .3), (25.5, .03), (25.7, .3), (26.0, .03), (27.3, .03), (27.4, .25), (41.9, .25), (42.6, .01))
LAMPS = A((0, 1), (41.9, 1), (42.35, .55), (42.4, .55), (43.0, .3), (43.05, .3), (43.6, .12), (43.65, .12), (44.4, 0))
CANOPY = A((0, 1), (4.6, 1), (4.65, 0), (6.6, 0), (6.7, 1), (41.9, 1), (43.0, 0))
WORLD_ENV = dict(rain=1, panels=PANELS, neon=NEON, lamps=LAMPS, canopy=CANOPY, car=.7, res_door=DOORS['reserve'], svc_door=DOORS['service'],
                 svc_shake=A((0, 0), *[p for h in KNOCKS for p in ((h - .01, 0), (h, 1), (h + .12, 0))]),
                 res_light=A((0, .8), (41.9, .8), (42.0, .25)), res_tube=A((0, 1), (41.9, 1), (42.0, .35), (56.0, .35), (56.1, .05), (56.3, .5), (56.5, .08), (72.0, .08)), res_lever=A((0, 0)))
WORLD_KEYS = list(WORLD_ENV)
TORCH_BOXES = [{'x': 0, 'y': 0, 'z': 0, 'w': 1.6, 'h': 1.6, 'd': 5.5, 'color': 0xe8e0c8}, {'x': 0, 'y': 0, 'z': 3, 'w': 2.2, 'h': 2.2, 'd': 1.2, 'color': 0x30302c}]
WORLD_PROPS = [
    {'type': 'sign', 'text': '24H/24', 'at': [-0.9, 2.75, -0.9], 'w': 1.5, 'h': 0.38, 'col': '#f4f4f4', 'bg': '#0a0a0c', 'px': 256},
    {'type': 'boxes', 'boxes': [{'x': -0.9, 'y': 3.0, 'z': -0.9, 'w': 0.05, 'h': 0.5, 'd': 0.05, 'color': 0x202024}]},
    {'type': 'sign', 'lines': ['00', '4'], 'at': [-9.5, 1.32, 12.29], 'w': 0.38, 'h': 0.34, 'col': '#ff3a2a', 'bg': '#12080a', 'px': 128},
    {'type': 'sign', 'lines': ['00', '4'], 'at': [-12.5, 1.32, 12.29], 'w': 0.38, 'h': 0.34, 'col': '#ff3a2a', 'bg': '#12080a', 'px': 128},
    {'type': 'tube', 'at': [-9.5, 3.74, 12.4], 'rot': [0, .45, 0], 'len': 1.9, 'anim': {'on': CANOPY}},
    {'type': 'boxes', 'boxes': [{'x': -6, 'y': 3.4, 'z': 14.2, 'w': 0.22, 'h': 6.8, 'd': 0.22, 'color': 0x202228}]},
    {'type': 'price_sign', 'at': [-6, 7.0, 14.0], 'w': 1.1, 'h': 1.6, 'lines': ['1.74', '0.99'], 'emit': 2.6},
    {'type': 'sign', 'text': 'LA DERNIÈRE POMPE', 'at': [0, 3.82, 3.8], 'w': 5.6, 'h': 0.95, 'col': '#ff4a3a', 'bg': '#0a0204', 'px': 512, 'emit': 1.4},
    {'type': 'poster_plan', 'at': [4.43, 1.5, -3.4], 'yaw': -1.5708, 'w': 0.8, 'h': 1.0},
    {'type': 'boxes', 'boxes': [{'x': 3.0, 'y': 1.07, 'z': 1.58, 'w': .06, 'h': .06, 'd': .22, 'color': 0xe8e0c8, 'ry': .5}, {'x': 3.03, 'y': 1.07, 'z': 1.67, 'w': .08, 'h': .08, 'd': .05, 'color': 0x30302c, 'ry': .5}], 't1': 30.1},
    {'type': 'boxes', 'boxes': [{'x': 2.6, 'y': 3.17, 'z': .2, 'w': .8, 'h': .05, 'd': .8, 'color': 0x08080a}, {'x': 2.6, 'y': 3.14, 'z': .2, 'w': .95, 'h': .04, 'd': .95, 'color': 0xd8d8d0}], 't0': 37.1},
    {'type': 'boxes', 'boxes': [{'x': 0.9, 'y': 3.02, 'z': -.9, 'w': .32, 'h': .22, 'd': 5., 'color': 0xcfc6ac, 'ry': .6}]},
]

TEAL = OLD.TEAL
CLERK = json.loads(json.dumps({k: v for k, v in OLD.CLERK.items() if k != 'extras'}))
CLERK['look'] = OLD.CLERK['look']
GHOST = OLD.GHOST
STRAP = [{'bone': 'torso', 'boxes': [{'x': 0, 'y': 3.2, 'z': 0, 'w': 8.5, 'h': 0.9, 'd': 4.5, 'color': 0xd8e2c8}, {'x': 0, 'y': 6.2, 'z': 0, 'w': 8.5, 'h': 0.9, 'd': 4.5, 'color': 0xd8e2c8}]}]

# ---------------------------------------------------------------------------------------------------------------------- the story
def plan():
    P = []
    B = lambda who, t, do, **kw: P.append(dict(who=who, t=t, do=do, **kw))
    # ---- the clerk (inside) ------------------------------------------------------------------------------------------------
    B('clerk', 0., 'face', at=.67); B('clerk', 0., 'emote', face='neutral')
    B('clerk', 3.2, 'emote', face='calm')
    B('clerk', 9.8, 'look', at='ghost', speed=2.2); B('clerk', 9.9, 'emote', face='worried')
    B('clerk', 11.0, 'go', to='porte_dedans', by=13.8, face='ghost')                       # to the glass door: 3.9 m
    B('clerk', 14.0, 'touch', target=[0.0, 1.2, 3.43], hand='R', dur=.75, pose='grip')     # the lock of the glass door
    B('clerk', 14.0, 'look', at='ghost', speed=3.)
    B('clerk', 15.3, 'talk', until=17.3); B('clerk', 15.3, 'emote', face='worried')
    B('clerk', 21.6, 'emote', face='scared'); B('clerk', 21.6, 'event', kind='tension', until=27.4, value=.7)
    B('clerk', 22.6, 'go', to=[0.3, 2.55], by=24.2, face='ghost')                          # a step back from the glass when the hand lands on it
    B('clerk', 27.3, 'look', at='ghost', speed=4.)
    B('clerk', 27.6, 'go', to='comptoir_clients', by=29.6, face=math.pi)                        # to the counter: 3.2 m, the torch lies on it
    B('clerk', 30.1, 'take', target='torche', hand='R', until=1e9, up=.35, down=.2)
    B('clerk', 30.3, 'face', at='ghost'); B('clerk', 30.45, 'look', at='ghost', speed=4.)
    B('clerk', 31.2, 'aim', at='ghost', until=37.1, hand='R', pose='grip', reach=.42, h=1.3)
    B('clerk', 31.8, 'emote', face='scared'); B('clerk', 33.2, 'emote', face='determined'); B('clerk', 36.0, 'emote', face='worried')
    B('clerk', 37.1, 'look', at=[2.6, .2, 3.1], speed=5.); B('clerk', 37.1, 'emote', face='surprised')       # the ceiling bangs: a glance up at the tile
    B('clerk', 38.9, 'emote', face='worried')
    B('clerk', 41.6, 'go', to='fenetre_est', by=43.4, face=0.); B('clerk', 41.7, 'look', at=[0.4, 9., 1.6], speed=3.)      # to the glass: the lot lights die one by one
    B('clerk', 45.4, 'emote', face='scared')
    B('clerk', 46.4, 'look', at=[3.45, -7.1, 1.4], speed=4.); B('clerk', 47.1, 'face', at=math.pi); B('clerk', 47.1, 'emote', face='scared')       # three knocks, from the back
    B('clerk', 47.8, 'go', to='affiche', by=53.4, face=math.pi / 2)                     # down the aisle towards the sound, to the electrical plan on the wall
    B('clerk', 53.5, 'look', at=[4.45, -3.4, 1.5], speed=3.); B('clerk', 53.5, 'emote', face='determined')
    B('clerk', 56.5, 'go', to='fenetre_est', by=60.1, face=0.); B('clerk', 56.5, 'emote', face='worried')   # back to the glass: "un œil dehors"
    B('clerk', 60.4, 'look', at=[4.2, 7.3, 1.1], speed=3.); B('clerk', 61.0, 'emote', face='worried')
    B('clerk', 64.4, 'emote', face='scared')
    B('clerk', 67.4, 'look', at=[3.45, -7.1, 1.4], speed=2.2, delay=.5); B('clerk', 68.6, 'face', at=math.pi); B('clerk', 68.6, 'emote', face='scared')    # the creak, behind him
    B('clerk', 70.4, 'event', kind='tension', until=96., value=.9)
    B('clerk', 74.5, 'go', to='allee_est', by=76.3, face=math.pi); B('clerk', 74.7, 'emote', face='determined')      # "il faut choisir": he steps into the middle of the shop, the door behind, the glass ahead
    B('clerk', 76.5, 'look', at=[3.45, -7.1, 1.4], speed=3.); B('clerk', 81.9, 'look', at=[4.2, 7.3, 1.1], speed=3.)   # A / B: the door behind, the car in front
    B('clerk', 82.0, 'face', at=0.); B('clerk', 86.2, 'emote', face='scared'); B('clerk', 88.2, 'look', at=[2.6, -2., 2.9], speed=4.)
    # reactions to causes: each starts after a human latency, looks where the cause is, then fades back to the tonic state
    B('clerk', 10.3, 'react', face='surprised', i=.55, hold=.3, decay=1.0, look='ghost')
    B('clerk', 22.9, 'react', face='scared', i=1., hold=.7, decay=1.6, look=[0.8, 3.57, 1.5])         # the hand lands on the glass
    B('clerk', 25.0, 'react', face='surprised', i=.5, hold=.2, decay=.8)                                 # the neon flickers
    B('clerk', 27.4, 'react', face='scared', i=.9, hold=.5, decay=1.4, look='ghost')                    # he is suddenly beside the door
    B('clerk', 31.9, 'react', face='determined', i=.8, hold=.8, decay=1.5)                              # he recoils from the beam
    B('clerk', 37.1, 'react', face='surprised', i=1., hold=.45, decay=1.3, look=[2.6, .2, 3.1])         # the bang in the ceiling
    B('clerk', 41.9, 'react', face='worried', i=.9, hold=1.2, decay=1.5, look=[0.4, 9., 1.6])           # the lot lights go out one by one
    B('clerk', 47.1, 'react', face='scared', i=1., hold=.6, decay=1.2, look=[3.45, -7.1, 1.4])          # first knock, from the back
    B('clerk', 48.7, 'react', face='scared', i=.7, hold=.3, decay=.9, look=[3.45, -7.1, 1.4])
    B('clerk', 50.3, 'react', face='scared', i=.7, hold=.3, decay=.9, look=[3.45, -7.1, 1.4])
    B('clerk', 69.3, 'react', face='scared', i=1., hold=.8, decay=1.6, look=[3.45, -7.1, 1.4])          # the creak, behind him
    B('clerk', 70.4, 'react', face='shocked', i=.9, hold=.8, decay=1.8, look=[3.68, -7.69, 1.35])       # the black hand in the gap
    B('clerk', 72.7, 'react', face='surprised', i=.6, hold=.2, decay=.9, look=[2.6, .2, 3.1])           # the last ceiling light flickers
    # ---- the faceless man (outside, then round the back, then inside the back room) -----------------------------------------
    B('ghost', 0., 'face', at=math.pi)
    B('ghost', 0.5, 'look', at=[.4, 9.5, .6], speed=1.)
    B('ghost', 6.3, 'go', to='vitre', by=10.8, face='clerk')
    B('ghost', 10.9, 'look', at='clerk', speed=1.2)
    B('ghost', 17.4, 'look', at=[.4, 3.9, 3.2], speed=.55); B('ghost', 19.9, 'look', at='clerk', speed=.7)          # he slowly lifts the head
    B('ghost', 22.7, 'touch', target=[0.8, 1.5, 3.57], hand='R', dur=2.7, pose='open', up=.6, down=.35)           # the hand on the glass (outer face)
    B('ghost', 26.2, 'go', to=[0.5, 6.4], by=27.3)                                          # away from the light, into the dark
    B('ghost', 27.4, 'go', to='vitre_porte_est', by=29.0, face='clerk')                     # and back, beside the door
    B('ghost', 31.6, 'go', to=[1.75, 5.5], by=32.5, backwards=True, face='clerk')
    B('ghost', 32.7, 'go', to=[1.75, 4.8], by=33.8, face='clerk')
    B('ghost', 34.0, 'go', to=[1.75, 5.4], by=34.7, backwards=True, face='clerk')
    B('ghost', 35.2, 'go', to=[1.75, 5.0], by=36.1, face='clerk')
    B('ghost', 40.9, 'go', to='service_dehors', by=47.0, via=['cote_est_sud', 'cote_est_nord'], face=-math.pi / 2)    # round the building, at a run
    B('ghost', 47.0, 'knock', target=[4.62, 1.45, -11.35], normal=[1., 0., 0.], hits=KNOCKS, hand='R', up=.5, down=.4, back=.14)
    B('ghost', 52.3, 'touch', target=[4.62, 1.2, -11.35], hand='R', dur=.9, pose='open', up=.4, down=.3)                  # he pushes the service door open
    B('ghost', 53.6, 'go', to='derriere_porte', by=59.0, face=0.)                                                          # in through it, round the shelves, behind the inner door
    B('ghost', 70.0, 'touch', target=[3.68, 1.35, -7.69], hand='R', dur=4.5, pose='grip', up=.8, down=.5)                  # a black hand on the edge of the door
    return dict(duration=DUR, actors={'clerk': dict(kind='human', start='caisse'), 'ghost': dict(kind='faceless', start='parking_loin')}, beats=P)


# ---------------------------------------------------------------------------------------------------------------------- the camera (what must be seen)
GAIN_FILE = Path(__file__).resolve().parents[3] / 'examples' / 'remakes' / 'pompe_continuite_gain.json'
GAIN = json.loads(GAIN_FILE.read_text(encoding='utf-8')) if GAIN_FILE.exists() else {}


def episode(preflight_only=False):
    geo = stagegeo.station(DOORS)
    pl = plan(); C = BLK.compile_plan(pl, geo)
    shots = []; S = {}

    def add(i, frame, camera, env=None, **kw):
        s = dict(id=f'S{i:02d}', stage='station', dur=d(i), frame=frame, camera=camera, env=dict(env or {}), **kw); shots.append(s); S[i] = s; return s

    def fixed(i, pos, look, fov=60., drift=None, lk=None, **kw):
        """a camera at a place chosen by hand, with an optional slow push of `drift` metres along its axis"""
        a = _k(0, pos, look, fov)
        if drift:
            f = [look[j] - pos[j] for j in range(3)]; n = math.sqrt(sum(v * v for v in f)); p2 = [pos[j] + f[j] / n * drift for j in range(3)]
            return cam(a, _k(d(i), p2, look, fov))
        return cam(a, _k(d(i), pos, look, fov))

    def solved(i, frame, fov=60., prefer=None, drift=0., hint=None, **kw):
        fr = dict(frame);
        if hint: fr['from'] = hint
        sol = CP.solve(geo, C, fr, T[i], T[i + 1], '9:16', fov, prefer)
        c = cam(_k(0, sol['pos'], sol['look'], sol['fov']), _k(d(i), sol['pos'], sol['look'], sol['fov']))
        return c

    out = lambda **kw: dict(outside=1, **kw)
    ins = lambda **kw: dict(outside=0, **kw)
    # S00 establishing, from the lot: the whole shop front, the lamp, the faceless man far in the lot (he was waiting there)
    add(0, dict(show=['vitrine'], actors=['ghost'], kind='wide'), fixed(0, [-1.5, 1.55, 21.5], [.2, 1.9, 4.], 62., drift=.8), out(), shake=.12)
    # S01 the clerk closing the till, seen from the customer side
    add(1, dict(actors=['clerk'], kind='medium'), fixed(1, [1.1, 1.6, 3.0], [2.9, 1.35, .3], 60., drift=.3), ins(), shake=.1)
    # S02 pump 4 and the canopy tube that goes out and comes back
    add(2, dict(show=['pompes'], kind='medium', context=True), fixed(2, [-11.0, 1.5, 22.5], [-10.9, 2.0, 12.], 66.), out(), shake=.15)
    # S03 the price sign on its pole, with the shop behind
    add(3, dict(show=['prix'], kind='medium', context=True), fixed(3, [-2.5, 1.4, 22.], [-5.8, 4.2, 14.2], 62.), out(), shake=.12)
    # S04 from inside, at the glass, the faceless man arriving behind it
    add(4, dict(actors=['ghost'], kind='medium', face=['ghost']), fixed(4, [-1.8, 1.55, .8], [.3, 1.7, 5.2], 64., drift=.4), ins(), shake=.1)
    # S05 outside, the faceless man in front, the clerk walking to the door behind the glass
    add(5, dict(actors=['ghost', 'clerk'], kind='wide'), fixed(5, [-4.2, 1.5, 9.2], [.5, 1.6, 3.8], 66.), out(), shake=.12)
    # S06 inside, the clerk at the door lock, the man behind the glass
    add(6, dict(actors=['clerk', 'ghost'], kind='medium'), fixed(6, [-2.0, 1.55, 1.4], [.4, 1.55, 3.8], 62.), ins(), shake=.1)
    # S07 the clerk's face through the glass, over the faceless man's shoulder
    add(7, dict(actors=['clerk'], kind='medium', face=['clerk']), fixed(7, [-1.2, 1.55, 5.9], [.3, 1.6, 3.1], 56., drift=.3), out(), shake=.1)
    # S08 push towards the faceless man behind the glass, past the clerk's shoulder
    add(8, dict(actors=['ghost'], kind='medium', face=['ghost']), fixed(8, [2.0, 1.55, .6], [.4, 1.65, 3.95], 58., drift=.9), ins(), shake=.08)
    # S09 the hand on the glass
    add(9, dict(actors=['ghost'], kind='medium'), fixed(9, [2.1, 1.5, 1.0], [.7, 1.5, 3.8], 60., drift=.3), ins(), shake=.08)
    # S10 the neon over the door flickers: the whole aisle, the door, the two of them
    add(10, dict(actors=['clerk', 'ghost'], kind='wide'), fixed(10, [2.6, 1.65, -0.5], [.4, 1.7, 3.6], 70.), ins(), shake=.1)
    # S11 he leaves the glass, into the dark lot
    add(11, dict(actors=['ghost'], kind='wide'), fixed(11, [1.8, 1.55, .6], [.4, 1.3, 8.], 68.), out(), shake=.12)
    # S12 beside the door, outside
    add(12, dict(actors=['ghost'], kind='medium'), fixed(12, [-.8, 1.5, .9], [1.0, 1.5, 5.4], 66., drift=.3), ins(), shake=.1)
    # S13 the clerk takes the torch from the counter
    add(13, dict(actors=['clerk'], kind='medium'), fixed(13, [-.3, 1.55, 3.0], [2.9, 1.3, 1.8], 64.), ins(), shake=.1)
    # S14 the torch on the faceless man, seen from the lot : the clerk behind the glass, the beam crossing it
    add(14, dict(actors=['ghost', 'clerk'], kind='wide'), solved(14, dict(actors=['ghost', 'clerk'], kind='wide'), 66., prefer=(-5.6, 9.2), hint=dict(at=[-5.6, 9.2], r=4.), fovs=[64., 70.]), out(), shake=.12, spots=True)
    # S15 over the clerk's shoulder, the faceless man in the beam
    add(15, dict(actors=['ghost'], kind='medium', face=['ghost']), solved(15, dict(actors=['ghost'], kind='medium', face=['ghost']), 62., prefer=(3.9, 2.4), hint=dict(at=[3.9, 2.4], r=1.4)), ins(), shake=.1, spots=True)
    # S16 from the east end of the lot, along the glass
    add(16, dict(actors=['ghost', 'clerk'], kind='wide'), solved(16, dict(actors=['ghost', 'clerk'], kind='wide'), 66., prefer=(7.4, 4.6), hint=dict(at=[7.4, 4.6], r=3.), fovs=[64., 70.]), out(), shake=.1, spots=True)
    # S17 high angle: the beam, the wet lot, the man's shadow
    add(17, dict(actors=['ghost'], kind='medium'), fixed(17, [4.15, 2.65, 2.2], [1.8, .9, 5.1], 62.), ins(), shake=.12, spots=True)
    # S18 a glance up : the clerk and the ceiling tile that has just banged
    add(18, dict(show=['dalle'], actors=['clerk'], kind='wide'), fixed(18, [-1.2, 1.4, 3.0], [3.0, 2.2, .8], 72.), ins(), shake=.18)
    # S19 the tile and the duct, the clerk below
    add(19, dict(show=['dalle'], actors=['clerk'], kind='wide'), fixed(19, [-1.4, 1.3, 2.4], [3.0, 2.3, .6], 72.), ins(), shake=.18)
    # S20 the leak: the tile, the duct, the clerk looking up
    add(20, dict(show=['dalle'], actors=['clerk'], kind='wide'), fixed(20, [3.9, 1.0, -2.9], [2.8, 2.4, .9], 72., drift=.3), ins(), shake=.12)
    # S21 the lot lights go out one by one, seen from the shop; the clerk's back at the glass
    add(21, dict(actors=['clerk'], kind='wide'), fixed(21, [2.6, 1.6, -.8], [2.6, 1.5, 10.], 72.), out(), shake=.15)
    # S22 the dark lot, the car, nobody there any more
    add(22, dict(show=['voiture'], kind='wide'), solved(22, dict(show=['voiture'], kind='wide'), 74., prefer=(-1.5, 2.4), hint=dict(at=[-1.5, 2.4], r=3.5), fovs=[72., 76., 80.]), out(), shake=.12)
    # S23 the clerk at the glass, from the lot: he turns towards the back
    add(23, dict(actors=['clerk'], kind='medium', face=['clerk']), fixed(23, [2.0, 1.5, 7.2], [2.3, 1.75, 2.9], 58.), out(), shake=.1)
    # S24 down the aisle: the clerk walks towards the knocks, the door at the far end
    add(24, dict(actors=['clerk'], kind='wide'), solved(24, dict(show=['porte_reserve'], actors=['clerk'], kind='wide'), 62., prefer=(2.7, 1.8)), ins(), shake=.1)
    # S25 inside the back room: the service door takes the third blow
    add(25, dict(show=['porte_service'], kind='wide', context=True), fixed(25, [2.0, 1.5, -9.6], [4.4, 1.2, -11.0], 66.), ins(), shake=.1)
    # S26 the clerk on the way, the inner door ahead
    add(26, dict(show=['porte_reserve'], actors=['clerk'], kind='wide'), solved(26, dict(show=['porte_reserve'], actors=['clerk'], kind='wide'), 62., prefer=(2.4, -1.0)), ins(), shake=.1)
    # S27 behind the building: the faceless man at the service door
    add(27, dict(show=['porte_service'], actors=['ghost'], kind='wide'), fixed(27, [9.2, 1.6, -13.5], [4.8, 1.3, -11.0], 64., drift=.4), out(), shake=.15)
    # S28 the clerk reaches the plan on the wall
    add(28, dict(show=['affiche'], actors=['clerk'], kind='medium'), fixed(28, [2.5, 1.55, .6], [3.9, 1.5, -3.4], 60.), ins(), shake=.1)
    # S29 the plan and the clerk reading it
    add(29, dict(show=['affiche'], actors=['clerk'], kind='medium'), fixed(29, [2.3, 1.5, -1.4], [4.0, 1.5, -3.5], 58.), ins(), shake=.08)
    # S30 inside the back room: the electrical board
    add(30, dict(show=['tableau_elec'], kind='medium', context=True), solved(30, dict(show=['tableau_elec'], kind='medium'), 62., prefer=(3.2, -11.2), hint=dict(at=[3.2, -11.2], r=1.6)), ins(), shake=.08)
    # S31 the back room from its far corner: board, shelves, bench
    add(31, dict(show=['tableau_elec'], kind='wide', context=True), solved(31, dict(show=['tableau_elec'], kind='wide'), 70., prefer=(3.8, -7.6), hint=dict(at=[3.8, -7.6], r=1.4), fovs=[68., 74.]), ins(), shake=.08)
    # S32 "un œil dehors": the clerk's face at the glass, from the lot
    add(32, dict(actors=['clerk'], kind='medium', face=['clerk']), solved(32, dict(actors=['clerk'], kind='medium', face=['clerk']), 56., prefer=(1.0, 7.4), hint=dict(at=[1.0, 7.4], r=3.)), out(), shake=.08)
    # S33 the car, whole, in front of the shop, the clerk behind the glass
    add(33, dict(show=['voiture', 'vitrine'], actors=['clerk'], kind='wide', min_share=dict(voiture=.3)), solved(33, dict(show=['voiture', 'vitrine'], actors=['clerk'], kind='wide', min_share=dict(voiture=.3)), 70., prefer=(-6.5, 17.5), hint=dict(at=[-6.5, 17.5], r=6.)), out(), shake=.1)
    # S34 three metres of dark between the door and the car, from inside, behind the clerk
    add(34, dict(show=['entree', 'voiture'], actors=['clerk'], kind='wide', min_share=dict(voiture=.3)), solved(34, dict(show=['entree', 'voiture'], actors=['clerk'], kind='wide', min_share=dict(voiture=.3)), 70., prefer=(9., 12.), fovs=[66., 72., 78.], rs=[4., 6., 8., 10., 12., 14., 17.]), out(), shake=.1)
    # S35 "derrière toi": from the lot, the clerk and, far behind him, the back door
    add(35, dict(show=['porte_reserve'], actors=['clerk'], kind='wide'), solved(35, dict(show=['porte_reserve'], actors=['clerk'], kind='wide'), 70., prefer=(2.2, 9.0), hint=dict(at=[2.2, 9.0], r=4.)), out(), shake=.1)
    # S36 the back door and its gap, from the middle of the shop
    add(36, dict(show=['porte_reserve'], kind='medium', context=True), fixed(36, [3.0, 1.55, -2.6], [3.45, 1.35, -7.1], 62.), ins(), shake=.1)
    # S37 the last ceiling light flickers: the shop from the glass end, the door at the far end
    add(37, dict(show=['porte_reserve'], kind='wide', context=True), fixed(37, [1.9, 1.7, 2.8], [3.2, 1.6, -6.8], 72.), ins(), shake=.12)
    # S38 "il faut choisir": the clerk facing the back, the glass and the car behind him
    add(38, dict(actors=['clerk'], kind='medium', face=['clerk']), fixed(38, [3.0, 1.6, -3.9], [2.6, 1.6, 1.4], 62., drift=.3), ins(), shake=.08)
    # S39 choice A: over the clerk's shoulder, the whole length of the shop to the door
    add(39, dict(show=['porte_reserve'], actors=['clerk'], kind='wide'), solved(39, dict(show=['porte_reserve'], actors=['clerk'], kind='wide'), 72., prefer=(3.0, 3.0), hint=dict(at=[3.0, 2.8], r=1.4), fovs=[70., 76., 80.]), ins(), shake=.08)
    # S40 choice B: from the aisle, the clerk, the glass and the car beyond
    add(40, dict(show=['voiture'], actors=['clerk'], kind='wide'), solved(40, dict(show=['voiture'], actors=['clerk'], kind='wide'), 72., prefer=(3.0, -5.6), hint=dict(at=[3.0, -5.4], r=2.2), fovs=[70., 76., 80.]), ins(), shake=.1)
    # S41 the last light
    add(41, dict(actors=['clerk'], kind='medium', face=['clerk']), solved(41, dict(actors=['clerk'], kind='medium', face=['clerk']), 58., prefer=(-1.5, 6.0), hint=dict(at=[-1.5, 6.0], r=3.)), out(), shake=.1)
    # S42 / S43 the station from the lot, the end card covers the lower half
    add(42, dict(show=['vitrine'], kind='wide'), fixed(42, [-1.5, 1.7, 22.], [.2, 2.4, 4.], 62., drift=.5), out(), shake=.08)
    add(43, dict(show=['vitrine'], kind='wide'), fixed(43, [-1.0, 1.7, 21.5], [.2, 2.4, 4.], 62.), out())
    for s in shots:                                           # the beam of the torch belongs to the story, not to a shot: it is there in every shot that sees that stretch of time
        t0, t1 = T[int(s['id'][1:])], T[int(s['id'][1:]) + 1]
        if t1 > 31.1 and t0 < 37.2 and s.get('spots') is not True: s['spots'] = True
        if s.get('spots') is True:
            s['spots'] = [{'from': {'on': 'clerk', 'h': 1.3, 'fwd': .5}, 'to': {'on': 'ghost', 'h': 1.3}, 'i': A((31.1, 0), (31.25, 34), (32.9, 34), (33.0, 0), (33.2, 34), (37.0, 34), (37.2, 0)), 'angle': .3, 'dist': 14}]
    ep = dict(title='La Dernière Pompe — partie 1 (continuité)', genre='horror', aspect='9:16', fps=FPS, duration=DUR, mood='neutral',
              casts={'clerk': dict(CLERK, extras=STRAP + BLK.held_extras(C, 'clerk', {'torche': TORCH_BOXES})), 'ghost': GHOST}, shots=shots, hud=OLD.hud(), cards=OLD.cards(),
              captions=OLD.episode()['captions'], caption_style={'cw': .049, 'y': .47, 'hi': '#f2392d'}, audio={'source': 'LA_DERNIERE_POMPE_partie1_sans_miniature.mp4'},
              world_env=WORLD_ENV, world_props=WORLD_PROPS,
              blocking=dict(world='station', doors=DOORS, plan=pl, world_keys=WORLD_KEYS, audit='strict', tight_max=.2, insert_max=3))
    if GAIN:
        for s in ep['shots']:
            if s['id'] in GAIN: s['env']['gain'] = GAIN[s['id']]
    return ep
