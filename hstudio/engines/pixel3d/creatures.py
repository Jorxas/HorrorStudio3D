"""Animals and fantasy creatures for the pixel3d engine (built from boxes, facing +z at the origin, then placed),
and character presets (zombie, knight, astronaut...) that are plain looks for the human figure."""
import math, functools
import numpy as np
from PIL import Image, ImageDraw
from .r3d import C, M_FABRIC, M_METAL

ANIMALS = ('dog', 'cat', 'bird', 'horse', 'cow', 'rabbit', 'chicken', 'pig', 'sheep', 'duck', 'dragon', 'spider', 'ghost')
EXTRA = {}      # creatures added by extensions (capabilities/extensions.py): kind -> fn(color, swing, t, k, posture) -> boxes

@functools.lru_cache(maxsize=64)
def animal_face(fur, eye=(20, 16, 20), nose=(30, 20, 20), kind='dog'):
    im = Image.new('RGBA', (12, 12), tuple(fur) + (255,)); d = ImageDraw.Draw(im)
    if kind == 'ghost':
        d.rectangle([2, 3, 4, 6], fill=(10, 10, 14)); d.rectangle([7, 3, 9, 6], fill=(10, 10, 14)); d.rectangle([4, 8, 7, 10], fill=(10, 10, 14))
    elif kind == 'spider':
        for x, y in ((2, 3), (5, 2), (8, 3), (3, 6), (7, 6)): d.rectangle([x, y, x + 1, y + 1], fill=(240, 40, 40))
    else:
        d.rectangle([2, 4, 3, 5], fill=eye); d.rectangle([8, 4, 9, 5], fill=eye); d.point([(2, 4), (8, 4)], fill=(240, 240, 240))
        if kind in ('dog', 'cat', 'rabbit', 'sheep'): d.rectangle([5, 7, 6, 8], fill=nose)
        if kind == 'cat': d.point([(1, 8), (10, 8), (2, 9), (9, 9)], fill=(230, 230, 230))
        if kind == 'pig': d.rectangle([4, 7, 7, 9], fill=(230, 140, 150)); d.point([(5, 8), (6, 8)], fill=(120, 50, 60))
    return np.array(im)

def _legs(bx, xs_zs, top, length, col, swing, k, w=.08):
    for i, (x, z) in enumerate(xs_zs):
        s = swing * (1 if i % 2 == 0 else -1) * (1 if i < 2 else -1)
        bx.append(C((x, top - length / 2, z + s * .5), (w, length, w), col, **k))

def animal(kind, color=None, swing=0., g=0., k=None, posture=None, size=1.):
    """boxes of an animal facing +z, feet on y = 0 at the origin"""
    k = k or {}; bx = []; t = g
    sit = posture in ('sit', 'lie')
    if kind in ('dog', 'cat'):
        fur = tuple(color or ((150, 100, 60) if kind == 'dog' else (90, 90, 96))); L = .62 if kind == 'dog' else .5; h = .42 if kind == 'dog' else .3
        by = h + .14 - (.16 if posture == 'lie' else 0)
        bx.append(C((0, by, 0), (.28 if kind == 'dog' else .22, .26 if kind == 'dog' else .2, L), fur, mat=M_FABRIC, **k))
        if not sit: _legs(bx, [(-.09, L * .35), (.09, L * .35), (-.09, -L * .35), (.09, -L * .35)], h + .02, h, fur, swing, k)
        else:
            bx.append(C((0, by - .12, -L * .2), (.3, .24, .3), fur, **k))
            for x in (-.08, .08): bx.append(C((x, (h if posture == 'sit' else .1) / 2, L * .38), (.07, h if posture == 'sit' else .1, .07), fur, **k))
        hy = by + (.18 if posture == 'sit' else .1); hz = L / 2 + .1
        bx.append(C((0, hy, hz), (.24, .22, .22), fur, tex={'+z': animal_face(fur, kind=kind)}, **k))
        if kind == 'dog':
            bx.append(C((0, hy - .05, hz + .14), (.12, .1, .1), tuple(int(c * .8) for c in fur), **k))
            for x in (-.12, .12): bx.append(C((x, hy + .02, hz - .02), (.04, .16, .1), tuple(int(c * .7) for c in fur), **k))
            wag = .12 * math.sin(t * 14)
            bx.append(C((wag * .5, by + .14, -L / 2 - .08), (.05, .05, .2), fur, **k))
        else:
            for x in (-.07, .07): bx.append(C((x, hy + .14, hz - .02), (.06, .08, .05), fur, **k))
            sw = .08 * math.sin(t * 3)
            bx += [C((sw * .5, by + .12, -L / 2 - .06), (.04, .04, .14), fur, **k), C((sw, by + .3, -L / 2 - .12), (.04, .3, .04), fur, **k)]
    elif kind in ('bird', 'duck', 'chicken'):
        col = tuple(color or {'bird': (60, 110, 200), 'duck': (240, 240, 230), 'chicken': (236, 232, 222)}[kind]); s = {'bird': .6, 'duck': 1., 'chicken': 1.1}[kind]
        fly = posture == 'fly'; by = (.25 * s) + (1.6 if fly else 0)
        bx.append(C((0, by, 0), (.2 * s, .2 * s, .32 * s), col, mat=M_FABRIC, **k))
        bx.append(C((0, by + .16 * s, .16 * s), (.14 * s, .14 * s, .14 * s), (40, 110, 60) if kind == 'duck' else col, tex={'+z': animal_face(col, kind='bird')}, **k))
        bx.append(C((0, by + .14 * s, .27 * s), (.06 * s, .04 * s, .1 * s), (240, 160, 40), **k))
        if kind == 'chicken': bx.append(C((0, by + .26 * s, .16 * s), (.04 * s, .06 * s, .1 * s), (220, 40, 40), **k))
        flap = math.sin(t * (22 if fly else 2)) * (.5 if fly else .05)
        for x in (-1, 1): bx.append(C((x * (.12 * s + abs(flap) * .1), by + flap * .12 * s, -.02), (.06 * s + (abs(flap) * .18 if fly else 0), .04 * s, .22 * s), col, **k))
        if not fly and kind != 'duck': _legs(bx, [(-.05 * s, 0), (.05 * s, 0)], .15 * s, .15 * s, (230, 150, 40), swing * .5, k, .025)
    elif kind in ('horse', 'cow', 'pig', 'sheep'):
        col = tuple(color or {'horse': (120, 76, 44), 'cow': (236, 232, 226), 'pig': (236, 160, 170), 'sheep': (240, 238, 230)}[kind])
        dims = {'horse': (.5, .55, 1.4, .95), 'cow': (.7, .7, 1.4, .7), 'pig': (.45, .42, .8, .3), 'sheep': (.55, .5, .8, .4)}[kind]
        w, hh, L, leg = dims; by = leg + hh / 2
        bx.append(C((0, by, 0), (w, hh, L), col, mat=M_FABRIC, **k))
        if kind == 'cow': bx += [C((w / 2 + .001, by + .05, .1), (.01, .3, .4), (30, 30, 30), **k), C((-w / 2 - .001, by - .05, -.3), (.01, .3, .35), (30, 30, 30), **k)]
        legc = (30, 30, 30) if kind == 'sheep' else (tuple(int(c * .85) for c in col) if kind != 'horse' else (90, 60, 36))
        _legs(bx, [(-w * .32, L * .38), (w * .32, L * .38), (-w * .32, -L * .38), (w * .32, -L * .38)], leg, leg, legc, swing, k, .12 if kind != 'pig' else .1)
        if kind == 'horse':
            for i in range(4): bx.append(C((0, by + .2 + i * .14, L / 2 + .05 + i * .07), (.24, .2, .22), col, **k))
            bx.append(C((0, by + .72, L / 2 + .35), (.22, .24, .48), col, tex={'+z': animal_face(col, kind='horse')}, **k))
            bx += [C((0, by + .55 + i * .1, L / 2 - .02 + i * .06), (.06, .14, .1), (40, 26, 18), **k) for i in range(4)]
            bx.append(C((0, by - .05, -L / 2 - .15), (.08, .5, .1), (40, 26, 18), **k))
        else:
            hc = (30, 30, 30) if kind == 'sheep' else col
            hs = {'cow': .4, 'pig': .3, 'sheep': .26}[kind]
            bx.append(C((0, by + .1, L / 2 + hs / 2), (hs, hs, hs), hc, tex={'+z': animal_face(hc, kind=kind)}, **k))
            if kind == 'cow': bx += [C((x, by + .1 + hs / 2 + .04, L / 2 + hs / 2), (.04, .1, .04), (230, 220, 190), **k) for x in (-.15, .15)]
            if kind == 'pig': bx.append(C((0, by + .05, L / 2 + hs + .03), (.14, .1, .06), (230, 140, 150), **k))
            if kind == 'sheep': bx.append(C((0, by + .12, 0), (w + .1, hh + .1, L - .1), col, mat=M_FABRIC, **k))
    elif kind == 'rabbit':
        col = tuple(color or (220, 214, 206)); hop = .12 * abs(math.sin(t * 8)) if swing else 0
        bx += [C((0, .16 + hop, 0), (.2, .22, .3), col, mat=M_FABRIC, **k), C((0, .32 + hop, .13), (.16, .16, .16), col, tex={'+z': animal_face(col, kind='rabbit')}, **k)]
        bx += [C((x, .5 + hop, .1), (.05, .22, .04), col, **k) for x in (-.04, .04)] + [C((0, .2 + hop, -.17), (.08, .08, .06), (250, 250, 250), **k)]
    elif kind == 'dragon' and posture == 'fly':        # V3: in flight (effects.mover): legs folded, slow wide wingbeats, tail waving
        col = tuple(color or (170, 40, 40)); dk = tuple(int(c * .78) for c in col); ph = t * 2 * math.pi * .8; flap = math.sin(ph)
        bx.append(C((0, 1.3, 0), (1.0, .85, 2.3), col, mat=M_FABRIC, **k))
        bx += [C((x, 1.0, z), (.22, .3, .5), col, **k) for x in (-.35, .35) for z in (.6, -.7)]
        for i in range(5): bx.append(C((0, 1.45 + i * .12, 1.15 + i * .28), (.42 - .02 * i, .34, .34), col, **k))
        bx.append(C((0, 2.05, 2.65), (.52, .46, .85), col, tex={'+z': animal_face(col, eye=(255, 220, 60), kind='dragon')}, **k))
        bx += [C((x, 2.38, 2.35), (.08, .3, .08), (230, 220, 190), **k) for x in (-.18, .18)]
        for i in range(8):
            wv = math.sin(ph - i * .6) * .25 * i / 8
            bx.append(C((wv, 1.3 - i * .04, -1.2 - i * .38), (.3 - i * .025, .24, .4), col, **k))
        for x in (-1, 1):
            for i in range(5):
                r = .75 + i * .62; y = 1.55 + flap * (.25 + .32 * i) * (1 if i else .5)
                bx.append(C((x * r, y, .25 - i * .12), (.66, .07, 1.5 - i * .2), dk if i else col, **k))
            bx.append(C((x * (.75 + 4 * .62 + .35), 1.55 + flap * 1.6, -.2), (.1, .1, .5), (230, 220, 190), **k))
    elif kind == 'dragon':
        col = tuple(color or (170, 40, 40)); flap = math.sin(t * 4) * .4
        bx.append(C((0, 1.3, 0), (1.0, .9, 2.2), col, mat=M_FABRIC, **k))
        _legs(bx, [(-.35, .7), (.35, .7), (-.35, -.7), (.35, -.7)], .9, .9, col, swing, k, .22)
        for i in range(5): bx.append(C((0, 1.6 + i * .25, 1.1 + i * .18), (.4, .32, .32), col, **k))
        bx.append(C((0, 2.85, 2.25), (.5, .45, .8), col, tex={'+z': animal_face(col, eye=(255, 220, 60), kind='dragon')}, **k))
        bx += [C((x, 3.15, 2.0), (.08, .25, .08), (230, 220, 190), **k) for x in (-.18, .18)]
        for i in range(6): bx.append(C((0, 1.3 - i * .08, -1.1 - i * .3), (.3 - i * .03, .25, .35), col, **k))
        for x in (-1, 1):
            for i in range(4): bx.append(C((x * (.7 + i * .45), 2.0 + flap * i * .3, .1 - i * .1), (.5, .06, 1.0 - i * .15), tuple(int(c * .8) for c in col), **k))
    elif kind == 'spider':
        col = tuple(color or (30, 28, 30)); s = size
        bx += [C((0, .45 * s, -.15 * s), (.6 * s, .45 * s, .7 * s), col, mat=M_FABRIC, **k), C((0, .4 * s, .35 * s), (.35 * s, .3 * s, .3 * s), col, tex={'+z': animal_face(col, kind='spider')}, **k)]
        for side in (-1, 1):
            for i in range(4):
                z = .3 * s - i * .2 * s; w_ = math.sin(t * 10 + i * 1.7) * .06 * s if swing else 0
                bx += [C((side * .45 * s, .55 * s, z + w_), (.4 * s, .05 * s, .05 * s), col, **k), C((side * .7 * s, .3 * s, z + w_), (.05 * s, .55 * s, .05 * s), col, **k)]
    elif kind == 'ghost':
        col = tuple(color or (236, 240, 246)); bob = .08 * math.sin(t * 2.5)
        bx.append(C((0, 1.3 + bob, 0), (.6, 1.1, .5), col, emis=.35, **k))
        bx.append(C((0, 1.85 + bob, 0), (.5, .3, .45), col, emis=.35, tex={'+z': animal_face(col, kind='ghost')}, **k))
        for i, x in enumerate((-.22, 0, .22)): bx.append(C((x, .68 + bob + .05 * math.sin(t * 5 + i), 0), (.16, .16 + .06 * (i % 2), .46), col, emis=.35, **k))
        for x in (-1, 1): bx.append(C((x * .38, 1.4 + bob + .05 * math.sin(t * 3 + x), .1), (.16, .3, .12), col, emis=.35, **k))
    elif kind in EXTRA:
        bx = list(EXTRA[kind](color, swing, t, k, posture))
    if size != 1. and kind != 'spider':
        for b in bx: b.lo = b.lo * size; b.hi = b.hi * size
    return bx

# character presets: plain looks for the human figure (cast {"kind": "zombie"} or {"preset": "knight"})
PRESETS = {
    'zombie': dict(skin=(120, 160, 110), hood=(80, 90, 70), jeans=(60, 60, 50), hair=(40, 50, 30), headphones=False, backpack=False, face='tired'),
    'skeleton': dict(skin=(232, 228, 214), hood=(30, 30, 34), jeans=(30, 30, 34), hair_style='bald', headphones=False, backpack=False, face='skull'),
    'vampire': dict(skin=(226, 218, 218), hood=(24, 20, 24), jeans=(20, 18, 20), hair=(14, 12, 14), outfit='coat', cape=(150, 20, 30), headphones=False, backpack=False, face='evil'),
    'robot': dict(skin=(170, 176, 186), hood=(120, 126, 140), jeans=(90, 96, 110), hair_style='bald', hat='antenna', headphones=False, backpack=False, face='robot'),
    'alien': dict(skin=(120, 200, 120), hood=(150, 150, 170), jeans=(110, 110, 130), hair_style='bald', headphones=False, backpack=False, face='alien', outfit='spacesuit'),
    'knight': dict(hood=(150, 152, 160), jeans=(120, 122, 130), outfit='armor', hat='helmet', headphones=False, backpack=False),
    'wizard': dict(hood=(70, 50, 140), jeans=(70, 50, 140), hair=(230, 230, 230), outfit='robe', hat='wizard', hat_color=(70, 50, 140), beard=True, headphones=False, backpack=False, hold='staff'),
    'witch': dict(hood=(40, 30, 50), jeans=(40, 30, 50), hair=(40, 20, 40), hair_style='long', outfit='robe', hat='witch', headphones=False, backpack=False),
    'pirate': dict(hood=(150, 30, 30), jeans=(50, 40, 30), outfit='coat', hat='pirate', beard=True, headphones=False, backpack=False),
    'chef': dict(hood=(240, 240, 236), jeans=(40, 40, 44), outfit='apron', hat='chef', headphones=False, backpack=False),
    'doctor': dict(hood=(90, 140, 190), jeans=(60, 70, 90), outfit='lab_coat', glasses=True, headphones=False, backpack=False),
    'nurse': dict(hood=(120, 190, 200), jeans=(120, 190, 200), outfit='tshirt', hair_style='bun', headphones=False, backpack=False),
    'police': dict(hood=(30, 40, 80), jeans=(30, 34, 60), outfit='uniform', hat='police', headphones=False, backpack=False),
    'firefighter': dict(hood=(200, 160, 40), jeans=(200, 160, 40), outfit='coat', hat='helmet', hat_color=(200, 40, 30), headphones=False, backpack=False),
    'astronaut': dict(hood=(236, 236, 240), jeans=(236, 236, 240), outfit='spacesuit', hat='astronaut', headphones=False, backpack=True),
    'king': dict(hood=(150, 30, 40), jeans=(150, 30, 40), outfit='robe', hat='crown', beard=True, cape=(150, 30, 40), headphones=False, backpack=False),
    'queen': dict(hood=(110, 50, 140), jeans=(110, 50, 140), outfit='dress', hat='crown', hair_style='bun', headphones=False, backpack=False),
    'princess': dict(hood=(240, 150, 190), jeans=(240, 150, 190), outfit='dress', hat='crown', hair_style='long', hair=(230, 190, 90), headphones=False, backpack=False),
    'superhero': dict(hood=(40, 80, 200), jeans=(40, 80, 200), outfit='tshirt', shirt=(230, 200, 40), cape=(200, 30, 30), headphones=False, backpack=False),
    'ninja': dict(hood=(24, 24, 28), jeans=(24, 24, 28), hat='hood', headphones=False, backpack=False),
    'student': dict(hood=(40, 50, 90), jeans=(60, 60, 70), outfit='suit', tie=(150, 30, 40), backpack=True, headphones=False),
    'teacher': dict(hood=(150, 120, 90), jeans=(70, 70, 80), outfit='shirt', glasses=True, headphones=False, backpack=False),
    'businessman': dict(hood=(40, 42, 52), jeans=(40, 42, 52), outfit='suit', headphones=False, backpack=False),
    'grandpa': dict(hair=(210, 210, 210), hair_style='bald', beard='mustache', glasses=True, hood=(120, 100, 80), outfit='shirt', headphones=False, backpack=False),
    'grandma': dict(hair=(220, 220, 224), hair_style='bun', glasses=True, hood=(140, 90, 120), outfit='dress', headphones=False, backpack=False),
    'cowboy': dict(hood=(150, 90, 50), jeans=(60, 70, 110), outfit='shirt', hat='cowboy', headphones=False, backpack=False),
    'kid': dict(scale=.72), 'baby': dict(scale=.48, headphones=False, backpack=False, face='happy'),
}
