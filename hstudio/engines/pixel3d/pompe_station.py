"""LA DERNIÈRE POMPE dans le studio : la station-service de nuit du premier moteur (r3d), portée telle quelle dans PIXEL 3D (style PS1).

Repère du premier moteur (celui des films La Dernière Pompe et Le Remplaçant) : x en travers, y vers le haut, la route loin à -z, l'auvent et les pompes autour de z=0, la façade vitrée de la boutique à z=FRONT (8), la réserve derrière.
Le lieu s'appelle `pompe_station` (`"set": "pompe_station"`). L'état du monde vient de la clé `state` du plan (tubeL, tubeR, porch, shop, till, fridge, head, door, sdoor, ... voir `ctx_default`),
les lumières sont à zones (dehors / boutique / réserve : la lumière de dehors n'entre pas) et à projecteurs (phares, lampadaire), fonctions ajoutées à `r3d.shade`.
Le code de la station est celui du premier moteur, sans changement de géométrie ni de textures."""
import os, math, functools, copy, numpy as np
from PIL import Image, ImageDraw, ImageFont
from .r3d import *
from ...paths import FONT_PIXEL


import math, functools, numpy as np
from PIL import Image, ImageDraw, ImageFont
FONT = FONT_PIXEL

FRONT = 8.0                    # outer face of the shop front
SX0, SX1 = -7.0, 7.0           # shop walls (x)
BACK = 15.0                    # shop back wall (storeroom behind)
REAR = 19.0                    # outer back wall
ROOFY = 3.6; CEIL = 3.2
DOOR = (-.65, .65)             # front door opening (x)
SDOOR = (-4.0, -3.0)           # storeroom door (x) in the back wall
RDOOR = (-5.2, -4.2)           # rear exit door (x) in the outer back wall
PART_X = -1.0                  # storeroom partition (storeroom: x < PART_X, BACK < z < REAR)
CAN = (-6.2, 6.2, -3.2, 4.2)   # canopy x0 x1 z0 z1
CANY = 4.6
TUBE_L = (-2.6, .5); TUBE_R = (2.6, .5)      # canopy neon tubes (x, z centre)
PUMP_L = (-2.6, .5); PUMP_R = (2.6, .5)      # pump islands
CAR = (-4.35, .4)                            # hero's car (centre), facing +z, headlights toward the shop
CAR_FRONT = CAR[1] + 2.15
PORCH = (0., 7.35)                           # porch lamp (x, z) under the awning
TILL = (4.4, 9.55)                           # the till (counter centre)
TILL_TUBE = (4.4, 9.9)
SHOP_TUBES = [(-4.0, 10.6), (-4.0, 13.4), (0., 10.6), (0., 13.4), (4.2, 13.4)]
PANEL = (-1.12, 1.45, 17.3)                  # main breaker panel (storeroom side of the partition)
LAMP = (13.5, -27.)                          # far sodium street lamp by the road
PYLON = (-9.5, -9.0)
VOX_CAR_ROT = 0                       # quarts de tour du modèle de voiture natif VOXEL (réglé sur une planche de contrôle)
TREES = ((-15, 14, 7), (-13, 22, 6), (-18, 4, 8), (16, 18, 7), (19, 6, 6), (14, 26, 8), (-22, -8, 7), (24, -6, 6), (-6, 28, 7), (6, 30, 9))

def _font(sz): return ImageFont.truetype(FONT, sz)

def text_tex(lines, size=(64, 32), fg=(255, 255, 255), bg=(0, 0, 0, 0), fs=8, pad=2, cols=None):
    im = Image.new('RGBA', size, bg); d = ImageDraw.Draw(im); d.fontmode = '1'
    f = _font(fs); y = pad
    for k, l in enumerate(lines):
        w = d.textlength(l, font=f); d.text(((size[0] - w) / 2, y), l, font=f, fill=(cols[k] if cols else fg) + (255,)); y += fs + 3
    return np.array(im)

# ---------------- textures ----------------
@functools.lru_cache(maxsize=4)
def shelf_tex(seed=0, w=48, h=32):
    """shop gondola side: 4 shelves of coloured packs"""
    r = np.random.default_rng(seed); im = Image.new('RGBA', (w, h), (70, 72, 78, 255)); d = ImageDraw.Draw(im)
    pal = [(220, 60, 50), (240, 200, 60), (60, 140, 220), (240, 240, 230), (90, 190, 90), (230, 120, 40), (160, 70, 160)]
    for row in range(4):
        y0 = 1 + row * 8; d.rectangle([0, y0 + 6, w - 1, y0 + 7], fill=(150, 152, 160, 255))
        x = 0
        while x < w:
            pw = int(r.integers(2, 5)); ph = int(r.integers(3, 6)); c = pal[int(r.integers(0, len(pal)))]
            d.rectangle([x, y0 + 6 - ph, x + pw - 1, y0 + 5], fill=c + (255,)); x += pw + int(r.integers(0, 2))
    return np.array(im)

@functools.lru_cache(maxsize=2)
def fridge_tex(on=1):
    im = Image.new('RGBA', (32, 32), (20, 24, 30, 255)); d = ImageDraw.Draw(im)
    r = np.random.default_rng(5); pal = [(220, 40, 40), (40, 160, 230), (240, 240, 240), (60, 200, 80), (250, 190, 40)]
    for row in range(5):
        y0 = 2 + row * 6; d.rectangle([0, y0 + 5, 31, y0 + 5], fill=(200, 210, 220, 255) if on else (60, 60, 70, 255))
        for x in range(1, 31, 3):
            c = pal[int(r.integers(0, 5))]
            if not on: c = tuple(int(v * .3) for v in c)
            d.rectangle([x, y0 + 1, x + 1, y0 + 4], fill=c + (255,))
    for x in (0, 10, 21, 31): d.line([(x, 0), (x, 31)], fill=(120, 130, 140, 255))
    return np.array(im)

@functools.lru_cache(maxsize=8)
def pump_tex(num='2', on=1):
    im = Image.new('RGBA', (24, 48), (210, 30, 36, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
    d.rectangle([2, 4, 21, 15], fill=(16, 22, 18, 255))
    if on:
        f = _font(8); d.text((3, 6), '00.0', font=f, fill=(255, 170, 40, 255))
    d.rectangle([2, 19, 21, 30], fill=(236, 236, 230, 255)); d.text((8, 21), num, font=_font(8), fill=(20, 20, 30, 255))
    d.rectangle([0, 34, 23, 37], fill=(250, 250, 250, 255)); d.rectangle([4, 40, 19, 46], fill=(40, 40, 46, 255))
    return np.array(im)

@functools.lru_cache(maxsize=8)
def sign_tex(kind):
    if kind == 'shopband':
        return text_tex(['STATION   24H/24'], (192, 12), (255, 255, 255), (180, 24, 30, 255), 8, 2)
    if kind == 'canopy':
        im = Image.new('RGBA', (96, 12), (200, 26, 32, 255)); d = ImageDraw.Draw(im)
        d.rectangle([0, 8, 95, 9], fill=(240, 240, 240, 255)); return np.array(im)
    if kind == 'door':
        return text_tex(['OUVERT', '24H/24'], (24, 24), (255, 230, 120), (0, 0, 0, 0), 8, 1)
    if kind == 'poster1':
        im = Image.new('RGBA', (24, 32), (240, 200, 40, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
        d.text((1, 2), 'CAFE', font=_font(8), fill=(120, 20, 20, 255)); d.text((4, 14), '1E', font=_font(8), fill=(120, 20, 20, 255))
        d.rectangle([4, 24, 19, 29], fill=(120, 60, 30, 255)); return np.array(im)
    if kind == 'poster2':
        im = Image.new('RGBA', (24, 32), (40, 120, 220, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
        d.text((1, 2), 'GAZ', font=_font(8), fill=(255, 255, 255, 255)); d.text((1, 14), '-5%', font=_font(8), fill=(255, 240, 80, 255)); return np.array(im)
    if kind == 'reserve':
        return text_tex(['RESERVE'], (64, 12), (20, 20, 20), (230, 200, 40, 255), 8, 2)
    if kind == 'breaker':      # the inscription on the shop wall
        im = Image.new('RGBA', (96, 40), (232, 232, 222, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
        d.rectangle([0, 0, 95, 39], outline=(200, 30, 30, 255)); d.rectangle([1, 1, 94, 38], outline=(200, 30, 30, 255))
        f = _font(8)
        for y, t in ((5, 'DISJONCTEUR'), (16, 'GENERAL')):
            w = d.textlength(t, font=f); d.text(((96 - w) / 2, y), t, font=f, fill=(20, 20, 20, 255))
        d.polygon([(8, 31), (16, 26), (16, 36)], fill=(200, 30, 30, 255)); d.rectangle([16, 29, 26, 33], fill=(200, 30, 30, 255))
        d.text((32, 28), 'RESERVE', font=f, fill=(200, 30, 30, 255))
        d.polygon([(70, 6), (76, 6), (72, 13), (77, 13), (68, 23), (71, 15), (66, 15)], fill=(240, 190, 30, 255))
        return np.array(im)
    if kind == 'plan':        # (LE REMPLACANT) affiche des horaires a la place du plan electrique
        return text_tex(['HORAIRES', '', 'OUVERT', 'JOUR ET NUIT'], (128, 88), (20, 20, 30), (236, 236, 226, 255), 8, 10)
    if kind == 'plan_old':
        im = Image.new('RGBA', (128, 88), (236, 236, 226, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'; f = _font(8)
        d.rectangle([0, 0, 127, 87], outline=(40, 60, 150, 255)); d.rectangle([0, 0, 127, 12], fill=(40, 60, 150, 255))
        d.text((4, 2), 'PLAN ELECTRIQUE', font=f, fill=(255, 255, 255, 255))
        d.rectangle([8, 20, 119, 80], outline=(30, 30, 40, 255)); d.line([(8, 42), (70, 42)], fill=(30, 30, 40, 255)); d.line([(70, 20), (70, 42)], fill=(30, 30, 40, 255))
        d.rectangle([9, 21, 69, 41], fill=(250, 210, 200, 255)); d.text((11, 23), 'RESERVE', font=f, fill=(200, 30, 30, 255))
        d.polygon([(52, 30), (58, 30), (54, 36), (59, 36), (49, 45), (52, 38), (47, 38)], fill=(230, 160, 20, 255))
        d.ellipse([44, 26, 66, 46], outline=(220, 30, 30, 255), width=2)
        d.text((40, 58), 'BOUTIQUE', font=f, fill=(30, 30, 40, 255)); d.rectangle([56, 78, 70, 81], fill=(236, 236, 226, 255))
        d.text((12, 70), 'X', font=f, fill=(200, 30, 30, 255))
        return np.array(im)
    if kind == 'panel':
        im = Image.new('RGBA', (24, 32), (150, 154, 158, 255)); d = ImageDraw.Draw(im)
        d.rectangle([2, 2, 21, 29], fill=(120, 124, 128, 255))
        for y in (5, 11, 17):
            for x in range(4, 20, 3): d.rectangle([x, y, x + 1, y + 3], fill=(30, 30, 34, 255))
        d.rectangle([7, 22, 16, 27], fill=(40, 40, 44, 255))
        d.polygon([(19, 3), (22, 3), (20, 7)], fill=(240, 190, 30, 255))
        return np.array(im)
    if kind == 'exit':
        return text_tex(['SORTIE'], (48, 12), (255, 255, 255), (20, 140, 70, 255), 8, 2)
    if kind == 'pylon':
        im = Image.new('RGBA', (32, 64), (16, 30, 120, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
        d.rectangle([0, 0, 31, 13], fill=(200, 24, 30, 255)); d.text((4, 3), 'GAZ', font=_font(8), fill=(255, 255, 255, 255))
        for k, (lab, pr) in enumerate((('SP95', '1.89'), ('DIES', '1.74'), ('E85', '0.99'))):
            y = 18 + k * 15; d.rectangle([2, y, 29, y + 11], fill=(8, 8, 10, 255)); d.text((3, y + 2), pr, font=_font(8), fill=(255, 60, 40, 255))
        return np.array(im)
    if kind == 'plate':
        return text_tex(['NP-317'], (40, 10), (20, 20, 30), (230, 230, 225, 255), 8, 1)
    if kind == 'ice':
        return text_tex(['GLACE'], (40, 12), (40, 120, 220), (240, 244, 250, 255), 8, 2)
    return None

@functools.lru_cache(maxsize=4)
def lock_tex(state=0):
    """door lock seen close: 0 open (vertical), 1 locked (horizontal)"""
    im = Image.new('RGBA', (16, 16), (170, 172, 176, 255)); d = ImageDraw.Draw(im)
    d.ellipse([2, 2, 13, 13], fill=(120, 122, 126, 255), outline=(60, 60, 64, 255))
    if state: d.rectangle([3, 7, 12, 8], fill=(30, 30, 34, 255))
    else: d.rectangle([7, 3, 8, 12], fill=(30, 30, 34, 255))
    return np.array(im)

# ---------------- ground ----------------
class St: pass
ST = St(); ST.t = 0.; ST.wet = 1.; ST.road_ext = False

def floor_fn(P):
    x, z = P[:, 0], P[:, 2]; n = P.shape[0]
    alb = np.zeros((n, 3), np.float32); refl = np.zeros(n, np.float32)
    inb = (x > SX0) & (x < SX1) & (z > FRONT) & (z < REAR)
    if inb.any():                                   # shop tiles / storeroom concrete
        xi, zi = x[inb], z[inb]
        store = zi > BACK
        chk = ((np.floor(xi / .5) + np.floor(zi / .5)) % 2 == 0)
        g = .86 + .14 * vnoise2(xi * 2, zi * 2, 3)
        tile = np.where(chk[:, None], np.array((.62, .62, .60), np.float32), np.array((.42, .43, .44), np.float32)) * g[:, None]
        grout = (np.abs(xi / .5 - np.round(xi / .5)) < .04) | (np.abs(zi / .5 - np.round(zi / .5)) < .04)
        tile[grout] *= .6
        conc = np.array((.22, .22, .21), np.float32)[None] * (.8 + .3 * fbm(xi * 1.5, zi * 1.5, 9, 2))[:, None]
        alb[inb] = np.where(store[:, None], conc, tile); refl[inb] = np.where(store, .02, .10)
    out = ~inb
    if out.any():
        xo, zo = x[out], z[out]
        can = (xo > CAN[0] - .3) & (xo < CAN[1] + .3) & (zo > CAN[2] - .3) & (zo < CAN[3] + .3)
        walk = (zo > FRONT - 2.0) & (zo <= FRONT + .01) & (np.abs(xo) < SX1 + .6)
        road = zo < -21.
        grass = (np.abs(xo) > 17.) | (zo > REAR + 3.)
        if getattr(ST, 'road_ext', False): grass = (grass & ~road) | (zo < -31.)        # la route continue (segments sur la route)
        g = .7 + .3 * fbm(xo * 1.6, zo * 1.6, 31, 3)
        base = np.array((.085, .085, .095), np.float32)[None] * g[:, None]
        # concrete under the canopy: big slabs + oil stains
        cs = (np.abs(xo / 1.6 - np.round(xo / 1.6)) < .025) | (np.abs(zo / 1.6 - np.round(zo / 1.6)) < .025)
        cbase = np.array((.30, .30, .29), np.float32)[None] * (.8 + .25 * fbm(xo, zo, 41, 2))[:, None]
        cbase[cs] *= .5
        oil = fbm(xo * .9 + 7, zo * .9, 43, 2) > .62
        cbase[oil] *= .45
        base = np.where(can[:, None], cbase, base)
        pav = np.array((.36, .35, .33), np.float32)[None] * (.85 + .2 * vnoise2(xo * 3, zo * 3, 47))[:, None]
        pj = (np.abs(xo / .6 - np.round(xo / .6)) < .05) | (np.abs(zo / .6 - np.round(zo / .6)) < .05)
        pav[pj] *= .55
        base = np.where(walk[:, None], pav, base)
        # parking lines on the right, road with a dashed yellow line far away
        lines = (xo > 7.5) & (xo < 15) & (zo > -1) & (zo < 7) & (np.abs(((xo - 7.5) / 2.6) - np.round((xo - 7.5) / 2.6)) < .04)
        base[lines] = (.62, .62, .58)
        rb = np.array((.05, .05, .055), np.float32)[None] * g[:, None]
        base = np.where(road[:, None], rb, base)
        dash = road & (np.abs(zo + 26.) < .07) & (((xo / 3.) % 1) < .5)
        base[dash] = (.6, .5, .15)
        gb = np.array((.05, .07, .035), np.float32)[None] * (.6 + .6 * fbm(xo * 2, zo * 2, 51, 2))[:, None]
        base = np.where(grass[:, None], gb, base)
        pud = fbm(xo * .45 + 3, zo * .45, 33, 3)
        r_ = np.where(pud > .52, .58, .26) * ST.wet
        r_ = np.where(can, np.where(oil | (pud > .58), .45, .2), r_)
        r_ = np.where(grass, .03, r_); r_ = np.where(walk, .22, r_)
        base = np.where(((pud > .52) & ~can & ~grass)[:, None], base * .55, base)
        alb[out] = base; refl[out] = r_
    return alb, refl

def zone_fn(P):
    """0 outside, 1 shop, 2 storeroom (lights only reach their own zone, plus small spills)"""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    zz = np.zeros(len(x), np.int64)
    shop = (x > SX0 - .01) & (x < SX1 + .01) & (z > FRONT + .15) & (z < BACK + .01) & (y < CEIL + .05)
    zz[shop] = 1
    store = (x > SX0 - .01) & (x < PART_X + .01) & (z > BACK + .15) & (z < REAR + .01) & (y < CEIL + .05)
    zz[store] = 2
    return zz

def ao_fn(P, nrm, ib):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ao = np.ones(len(x), np.float32)
    fl = ib == -1
    if fl.any():   # darker in the corners of the rooms and along the facade
        xf, zf = x[fl], z[fl]
        inb = (xf > SX0) & (xf < SX1) & (zf > FRONT) & (zf < REAR)
        dw = np.minimum.reduce([np.abs(xf - SX0), np.abs(xf - SX1), np.abs(zf - FRONT), np.abs(zf - BACK), np.abs(zf - REAR)])
        ao[fl] = np.where(inb, .55 + .45 * np.clip(dw / .6, 0, 1), np.where(np.abs(zf - FRONT) < .5, .6 + .4 * np.abs(zf - FRONT) / .5, 1.))
    vert = (ib >= 0) & (np.abs(nrm[:, 1]) < .5)
    ao[vert] *= .6 + .4 * np.clip(y[vert] / .5, 0, 1)
    return ao

# ---------------- props ----------------
def car(cx, cz, lights_on=1., col=(120, 22, 28)):
    bx = []; k = dict(mat=M_METAL)
    bx.append(C((cx, .55, cz), (1.8, .55, 4.3), col, refl=.18, **k))
    bx.append(C((cx, .9, cz + .2), (1.76, .16, 3.6), col, refl=.18, **k))
    bx.append(C((cx, 1.25, cz - .25), (1.6, .55, 2.1), (26, 28, 34), refl=.35))                # glass cabin
    bx.append(C((cx, 1.55, cz - .25), (1.62, .08, 1.9), col, refl=.18, **k))                    # roof
    for sx in (-1, 1):
        for sz in (-1, 1): bx.append(C((cx + sx * .82, .33, cz + sz * 1.35), (.26, .66, .7), (14, 14, 16)))
        bx.append(C((cx + sx * .62, .78, cz + 2.16), (.4, .14, .04), (255, 240, 200) if lights_on > 0 else (90, 90, 80), emis=2.4 * lights_on, cast=False))
        bx.append(C((cx + sx * .66, .8, cz - 2.16), (.34, .12, .04), (255, 40, 30), emis=1.2, cast=False))
    bx.append(C((cx, .5, cz + 2.17), (.5, .12, .03), (230, 230, 225), tex={'+z': sign_tex('plate')}))
    bx.append(C((cx, .5, cz + 2.15), (1.7, .1, .06), (40, 40, 44)))
    return bx

def pump(px, pz, num, on=1, hose=True):
    bx = [C((px, .1, pz), (.9, .2, 3.4), (150, 150, 146), mat=M_METAL)]
    bx.append(C((px, 1.05, pz), (.5, 1.7, .9), (210, 30, 36), tex={'+x': pump_tex(num, on), '-x': pump_tex(num, on)}, mat=M_METAL))
    bx.append(C((px, 1.95, pz), (.56, .12, .96), (236, 236, 230)))
    for sx in (-1, 1):
        bx.append(C((px + sx * .27, 1.05, pz + .25), (.05, .22, .1), (30, 30, 30)))
        if hose: bx += [C((px + sx * .3, .75, pz + .25 + .08 * q), (.04, .5 - .1 * q, .04), (24, 24, 26)) for q in range(1)]
    for bz in (-1.55, 1.55): bx.append(C((px, .5, pz + bz), (.16, .8, .16), (232, 190, 40), mat=M_METAL))
    return bx

def cart(cx, cz, crates=True, along='z'):
    """stock trolley (platform + handle) loaded with boxes"""
    bx = [C((cx, .2, cz), (.64, .1, .9) if along == 'z' else (.9, .1, .64), (60, 64, 72), mat=M_METAL)]
    for sx in (-1, 1):
        for sz in (-1, 1): bx.append(C((cx + sx * .26, .07, cz + sz * .36), (.08, .14, .08), (20, 20, 22)))
    bx.append(C((cx, .8, cz - .42), (.64, 1.1, .05), (90, 94, 102), mat=M_METAL))
    if crates:
        bx.append(C((cx, .48, cz + .05), (.6, .45, .75), (170, 128, 80), mat=M_CARD))
        bx.append(C((cx - .04, .9, cz + .02), (.5, .38, .6), (160, 120, 74), mat=M_CARD))
        bx.append(C((cx + .05, 1.22, cz + .08), (.4, .26, .46), (180, 140, 90), mat=M_CARD))
    return bx

def tree(x, z, h=6., w=2.6, seed=0):
    r = np.random.default_rng(seed); bx = [C((x, h * .25, z), (.35, h * .5, .35), (24, 18, 14))]
    for k in range(3):
        y = h * (.45 + .17 * k); ww = w * (1 - .22 * k)
        bx.append(C((x + r.uniform(-.2, .2), y, z + r.uniform(-.2, .2)), (ww, h * .22, ww), (14, 22, 16)))
    return bx

# ---------------- the station ----------------
def build_station():
    sc = Scene(); sc.floor_fn = floor_fn; sc.ao_fn = ao_fn; sc.zone_fn = zone_fn; sc.ceil_y = None
    sc.ambient = (.022, .026, .036); sc.fog = (.018, .022, .032); sc.fogk = .035
    idx = {}
    wall = (150, 146, 136); dark = (46, 48, 54); frame = (60, 62, 68); white = (210, 210, 204)
    # ---- shop front: low wall, mullions, glass band top, sign band, door frame, awning
    sc.add(B((SX0 - .2, 0, FRONT), (SX1 - SX0 + .4, .62, .22), wall, mat=M_PLASTER))
    for xm in (-7.0, -5.1, -3.1, -1.05, 1.05, 3.1, 5.1, 7.0):
        if abs(xm) > 1: sc.add(B((xm - .07, .62, FRONT), (.14, 2.0, .22), frame, mat=M_METAL))
    for xd in DOOR: sc.add(B((xd - (.1 if xd < 0 else 0), 0, FRONT), (.1, 2.62, .22), frame, mat=M_METAL))
    sc.add(B((DOOR[0], 2.3, FRONT), (DOOR[1] - DOOR[0], .32, .22), frame, mat=M_METAL))
    sc.add(B((-1.05, .62, FRONT), (DOOR[0] + 1.05, .02, .22), frame), B((DOOR[1], .62, FRONT), (1.05 - DOOR[1], .02, .22), frame))
    sc.add(B((SX0 - .2, 2.62, FRONT), (SX1 - SX0 + .4, ROOFY - 2.62, .22), wall, mat=M_PLASTER))
    sc.add(B((SX0 - .2, 2.82, FRONT - .03), (SX1 - SX0 + .4, .55, .04), (180, 24, 30), tex={'-z': sign_tex('shopband')}, texemis=1.1))
    idx['awning'] = len(sc.boxes)
    sc.add(B((-1.6, 2.95, FRONT - 1.25), (3.2, .12, 1.25), (190, 30, 36), mat=M_METAL))
    sc.add(B((-1.62, 2.88, FRONT - 1.27), (3.24, .08, .06), (230, 230, 225)))
    idx['porch'] = len(sc.boxes)
    sc.add(C((PORCH[0], 2.9, PORCH[1]), (.9, .05, .22), (255, 236, 190), emis=2.2, cast=False))
    # door (glass leaf: frame boxes; glass itself is a screen-space effect)
    idx['door'] = len(sc.boxes)
    sc.add(B((DOOR[0], 0, FRONT + .08), (DOOR[1] - DOOR[0], .12, .06), frame), B((DOOR[0], 2.18, FRONT + .08), (DOOR[1] - DOOR[0], .12, .06), frame),
           B((DOOR[0], 0, FRONT + .08), (.08, 2.3, .06), frame), B((DOOR[1] - .08, 0, FRONT + .08), (.08, 2.3, .06), frame),
           B((DOOR[1] - .22, .95, FRONT + .03), (.05, .3, .04), (200, 200, 205)), B((DOOR[1] - .22, .95, FRONT + .14), (.05, .3, .04), (200, 200, 205)))
    idx['door_n'] = len(sc.boxes) - idx['door']
    sc.add(B((.15, 1.6, FRONT + .04), (.36, .36, .01), (0, 0, 0), tex={'-z': sign_tex('door')}, texemis=1.4, cast=False))
    sc.add(B((-4.4, 1.0, FRONT + .2), (.7, .95, .01), (240, 200, 40), tex={'-z': sign_tex('poster1')}, texemis=.5), B((-6.2, 1.0, FRONT + .2), (.7, .95, .01), (40, 120, 220), tex={'-z': sign_tex('poster2')}, texemis=.5))
    # ---- side + back walls, roof, interior ceiling
    sc.add(B((SX0 - .2, 0, FRONT), (.2, ROOFY, REAR - FRONT + .2), wall, mat=M_PLASTER), B((SX1, 0, FRONT), (.2, ROOFY, REAR - FRONT + .2), wall, mat=M_PLASTER))
    sc.add(B((SX1 - .01, 1.0, 9.6), (.22, 1.2, 2.2), (30, 40, 50), refl=.3))          # side window (dark glass)
    sc.add(B((SX0 - .2, 0, REAR), (RDOOR[0] - SX0 + .2, ROOFY, .2), wall, mat=M_PLASTER), B((RDOOR[1], 0, REAR), (SX1 + .2 - RDOOR[1], ROOFY, .2), wall, mat=M_PLASTER))
    sc.add(B((RDOOR[0], 2.2, REAR), (RDOOR[1] - RDOOR[0], ROOFY - 2.2, .2), wall, mat=M_PLASTER))
    idx['rdoor'] = len(sc.boxes)
    sc.add(B((RDOOR[0], 0, REAR + .07), (RDOOR[1] - RDOOR[0], 2.2, .06), (84, 92, 88), mat=M_DOOR))
    sc.add(B((RDOOR[1] - .2, 1.0, REAR + .2), (.12, .05, .06), (180, 180, 186)))
    sc.add(B((RDOOR[0] + .1, 2.3, REAR + .2), (.8, .16, .02), (20, 140, 70), tex={'+z': sign_tex('exit')}, texemis=.25))
    sc.add(C(((RDOOR[0] + RDOOR[1]) / 2, 2.75, REAR + .3), (.3, .14, .2), (40, 40, 44)), C(((RDOOR[0] + RDOOR[1]) / 2, 2.66, REAR + .32), (.16, .04, .1), (255, 210, 150), emis=1.2, cast=False))   # weak lamp over the rear door
    sc.add(B((-5.6, 2.3, REAR - .01), (1.0, .45, .02), (120, 140, 190), emis=.5, cast=False))      # small high window of the storeroom
    sc.add(B((SX0 - .3, ROOFY, FRONT - .05), (SX1 - SX0 + .6, .2, REAR - FRONT + .4), (70, 70, 74), mat=M_METAL))
    sc.add(B((SX0, CEIL, FRONT + .2), (SX1 - SX0, .1, REAR - FRONT - .2), (190, 190, 186), mat=M_CEIL))
    # back wall of the shop with the storeroom door opening, partition, storeroom door
    sc.add(B((SX0, 0, BACK), (SDOOR[0] - SX0, CEIL, .2), (196, 196, 188), mat=M_PLASTER), B((SDOOR[1], 0, BACK), (SX1 - SDOOR[1], CEIL, .2), (196, 196, 188), mat=M_PLASTER))
    sc.add(B((SDOOR[0], 2.15, BACK), (SDOOR[1] - SDOOR[0], CEIL - 2.15, .2), (196, 196, 188), mat=M_PLASTER))
    sc.add(B((PART_X, 0, BACK + .2), (.2, CEIL, REAR - BACK - .2), (170, 170, 164), mat=M_PLASTER))
    idx['sdoor'] = len(sc.boxes)
    sc.add(B((SDOOR[0], 0, BACK + .06), (SDOOR[1] - SDOOR[0], 2.15, .08), (130, 136, 142), mat=M_DOOR))
    idx['handle'] = len(sc.boxes)
    sc.add(B((SDOOR[1] - .32, 1.0, BACK + .0), (.2, .05, .06), (200, 200, 206), mat=M_METAL), B((SDOOR[1] - .14, .96, BACK + .0), (.05, .12, .06), (200, 200, 206), mat=M_METAL))
    sc.add(B((SDOOR[0] + .2, 1.75, BACK - .01), (.6, .12, .01), (230, 200, 40), tex={'-z': sign_tex('reserve')}, texemis=.2))
    idx['plan'] = len(sc.boxes)
    sc.add(B((SX1 - .015, 1.25, 8.55), (.01, .95, 1.4), (236, 236, 226), tex={'-x': sign_tex('plan')}, texemis=.1))
    sc.add(B((-1.42, 1.2, FRONT + .22), (.06, .06, .05), (40, 40, 44)))                                   # torch hook by the door
    idx['jbox'] = len(sc.boxes)
    sc.add(B((1.5, CEIL - .14, FRONT + .35), (.36, .14, .3), (120, 124, 130), mat=M_METAL), B((1.62, CEIL - .02, FRONT + .2), (.06, .02, 2.2), (90, 94, 100)))
    sc.add(B((1.3, CEIL - .005, FRONT + .3), (.7, .01, .6), (52, 48, 36), cast=False))                    # wet stain on the ceiling
    sc.add(B((1.55, CEIL - .1, FRONT + .34), (.2, .06, .01), (230, 190, 30), cast=False))                 # warning label on the box
    # ---- shop interior: tubes, counter + till, gondolas, fridges, coffee
    idx['tubes'] = len(sc.boxes)
    for (tx, tz) in SHOP_TUBES: sc.add(C((tx, CEIL - .04, tz), (1.3, .05, .16), (235, 250, 240), emis=1.7, cast=False))
    idx['till_tube'] = len(sc.boxes)
    sc.add(C((TILL_TUBE[0], CEIL - .04, TILL_TUBE[1]), (1.3, .05, .16), (235, 250, 240), emis=1.7, cast=False))
    sc.add(B((TILL[0] - 1.5, 0, TILL[1] - .4), (3.0, 1.05, .8), (120, 40, 40), mat=M_WOODV), B((TILL[0] - 1.55, 1.05, TILL[1] - .45), (3.1, .06, .9), (200, 200, 196)))
    idx['till_screen'] = len(sc.boxes)
    sc.add(C((TILL[0] + .5, 1.3, TILL[1]), (.4, .32, .06), (30, 34, 40)), C((TILL[0] + .5, 1.3, TILL[1] - .035), (.34, .24, .01), (60, 200, 120), emis=1.0, cast=False))
    sc.add(B((TILL[0] - 1.6, 1.0, 11.4), (3.3, 1.8, .4), (70, 72, 78), tex={'-z': shelf_tex(3, 64, 32)}))
    for gx, seed in ((-5.4, 1), (-2.0, 2), (1.6, 4)):
        sc.add(B((gx - .45, 0, 9.8), (.9, 1.55, 3.8), (70, 72, 78), tex={'+x': shelf_tex(seed), '-x': shelf_tex(seed + 10)}))
        sc.add(B((gx - .5, 1.55, 9.75), (1.0, .06, 3.9), (180, 180, 184)))
    idx['fridge'] = len(sc.boxes)
    sc.add(B((SX0, 0, 9.4), (.75, 2.2, 5.2), (40, 44, 50), mat=M_METAL))
    sc.add(B((SX0 + .76, .15, 9.5), (.01, 1.95, 5.0), (210, 230, 255), tex={'+x': fridge_tex(1)}, texemis=1.0, cast=False))
    sc.add(B((5.2, 0, 13.6), (1.2, .95, .7), (60, 40, 30), mat=M_WOODV), C((5.6, 1.2, 13.9), (.4, .5, .35), (30, 30, 34)), C((5.6, 1.2, 13.72), (.2, .1, .01), (220, 60, 40), emis=1.2, cast=False))
    # ---- storeroom: shelves, boxes, panel, mop bucket
    sc.add(B((SX0, 0, BACK + .5), (.6, 2.2, 3.0), (90, 92, 98), mat=M_METAL))
    for k in range(4):
        y = .25 + k * .5
        sc.add(B((SX0 + .05, y, BACK + .6), (.5, .35, 2.8), (150, 112, 70), mat=M_CARD))
    sc.add(B((-3.0, 0, REAR - 1.0), (1.2, .9, .8), (150, 112, 70), mat=M_CARD), B((-2.8, .9, REAR - .9), (.8, .6, .6), (160, 120, 74), mat=M_CARD))
    idx['panel'] = len(sc.boxes)
    sc.add(C(PANEL, (.12, .8, .6), (150, 154, 158), tex={'-x': sign_tex('panel')}, mat=M_METAL))
    sc.add(C((PANEL[0] - .1, PANEL[1] - .1, PANEL[2] + .12), (.1, .22, .06), (200, 30, 30)))         # main breaker lever (down)
    sc.add(C((PANEL[0] - .07, PANEL[1] + .3, PANEL[2] - .2), (.02, .03, .03), (255, 40, 30), emis=2.5, cast=False))
    sc.add(B((PANEL[0] - .02, PANEL[1] + .45, PANEL[2] - .45), (.01, .2, .9), (232, 232, 222), tex={'-x': text_tex(['DISJONCTEUR'], (64, 10), (20, 20, 20), (232, 232, 222, 255), 8, 1)}))
    # ---- canopy: columns, slab, fascia, tubes
    for cx in (-4.6, 4.6):
        for cz in (-2.2, 3.2): sc.add(C((cx, CANY / 2, cz), (.34, CANY, .34), (210, 210, 206), mat=M_METAL))
    sc.add(B((CAN[0], CANY, CAN[2]), (CAN[1] - CAN[0], .5, CAN[3] - CAN[2]), (40, 40, 44), mat=M_METAL))
    sc.add(B((CAN[0] - .05, CANY - .05, CAN[2] - .05), (CAN[1] - CAN[0] + .1, .62, .06), (200, 26, 32), tex={'-z': sign_tex('canopy')}, texemis=.25))
    sc.add(B((CAN[0] - .05, CANY - .05, CAN[3]), (CAN[1] - CAN[0] + .1, .62, .06), (200, 26, 32), tex={'+z': sign_tex('canopy')}, texemis=.25))
    sc.add(B((CAN[0] - .06, CANY - .05, CAN[2]), (.06, .62, CAN[3] - CAN[2]), (200, 26, 32)), B((CAN[1], CANY - .05, CAN[2]), (.06, .62, CAN[3] - CAN[2]), (200, 26, 32)))
    sc.add(B((CAN[0] - .07, CANY - .1, CAN[2] - .07), (CAN[1] - CAN[0] + .14, .05, .03), (60, 120, 255), emis=1.6, cast=False))     # blue LED line
    idx['tubeL'] = len(sc.boxes); sc.add(C((TUBE_L[0], CANY - .05, TUBE_L[1]), (.22, .07, 3.0), (235, 248, 255), emis=1.8, cast=False))
    idx['tubeR'] = len(sc.boxes); sc.add(C((TUBE_R[0], CANY - .05, TUBE_R[1]), (.22, .07, 3.0), (235, 248, 255), emis=1.8, cast=False))
    sc.add(*pump(PUMP_L[0], PUMP_L[1], '3'), *pump(PUMP_R[0], PUMP_R[1], '4'))
    idx['car'] = len(sc.boxes); sc.add(*car(CAR[0], CAR[1]))
    sc.add(C((CAR[0], 1.32, CAR[1] - .2), (1.4, .3, 1.6), (255, 220, 150), emis=.35, cast=False))      # interior light left on
    # ---- exterior props
    sc.add(B((7.4, 0, 8.6), (1.0, 1.1, .7), (230, 234, 240), tex={'-x': sign_tex('ice')}), B((7.4, 0, 12.5), (1.4, 1.3, 2.0), (40, 70, 50), mat=M_METAL))
    sc.add(B((-8.6, 0, 10.0), (.6, 1.0, .6), (60, 60, 64), mat=M_METAL), C((-8.3, 1.05, 10.3), (.2, .1, .2), (30, 30, 30)))
    sc.add(C((PYLON[0], 3.5, PYLON[1]), (.3, 7.0, .3), (60, 60, 66), mat=M_METAL))
    idx['pylon'] = len(sc.boxes)
    sc.add(C((PYLON[0], 6.2, PYLON[1]), (1.4, 2.8, .3), (16, 30, 120), tex={'+z': sign_tex('pylon'), '-z': sign_tex('pylon')}, texemis=1.2))
    sc.add(C((LAMP[0], 3.4, LAMP[1]), (.2, 6.8, .2), (50, 50, 54)), C((LAMP[0] - .7, 6.75, LAMP[1]), (1.4, .1, .2), (50, 50, 54)))
    idx['lamp'] = len(sc.boxes); sc.add(C((LAMP[0] - 1.2, 6.65, LAMP[1]), (.4, .08, .25), (255, 170, 70), emis=2.4, cast=False))
    idx['trees0'] = len(sc.boxes)
    for k, (tx, tz, h) in enumerate(TREES):
        sc.add(*tree(tx, tz, h, 2.4 + .3 * (k % 3), k))
    idx['trees1'] = len(sc.boxes)
    for fx in np.arange(-16, 17, 2.0): sc.add(C((fx, .55, REAR + 4.0), (.08, 1.1, .08), (40, 40, 44)))
    sc.add(B((-16, .9, REAR + 3.97), (32, .05, .05), (50, 50, 54)), B((-16, .4, REAR + 3.97), (32, .05, .05), (50, 50, 54)))
    sc.add(B((-40, 0, -21.2), (80, .14, .2), (90, 90, 90)))
    for hx, hz, hw, hh in ((-30, 60, 30, 9), (10, 70, 40, 12), (-60, 20, 20, 7)): sc.add(B((hx, 0, hz), (hw, hh, 6), (8, 10, 14)))
    sc.idx = idx
    return sc

_SC = None
def station():
    global _SC
    if _SC is None: _SC = build_station()
    return _SC

def nrm3(v): v = np.asarray(v, np.float32); return v / (np.linalg.norm(v) + 1e-9)
class Light:
    __slots__ = ('pos', 'col', 'i', 'r', 'shadow', 'spot', 'zone', 'vol', 'key')
    def __init__(s, pos, col, i, r, shadow=False, spot=None, zone=None, vol=0., key=''):
        s.pos = np.asarray(pos, np.float32); s.col = col; s.i = i; s.r = r; s.shadow = shadow
        s.spot = None if spot is None else (nrm3(spot[0]), spot[1], spot[2]); s.zone = zone; s.vol = vol; s.key = key
    def tup(s, sh): return (tuple(s.pos), s.col, s.i, s.r, sh, s.spot, s.zone)

OUT = (1., .12, 0.); SHOP = (.22, 1., 0.); STORE = (0., 0., 1.); ALL = None
def spot_light(pos, d, i=2.6, r=6., ci=.965, co=.9, col=(1., .96, .84), vol=1.6, zone=ALL, shadow=True, key='torch'):
    return Light(pos, col, i, r, shadow, (d, ci, co), zone, vol, key)

def ctx_default():
    return dict(tubeR=1., tubeL=1., porch=1., blue=1., shop=1., till=1., fridge=1., pylon=1., head=1., door=0., lock=0, handle=0., sdoor=0.,
                sshake=0., cart=None, finger=0., rdoor=0., flash=0., rshake=0.)

def flick(g, rate=9., depth=.6, seed=0, p=.8):
    k = int(g * rate); r = ((k * 2654435761 + seed * 97) & 0xffff) / 65535.
    return 1 - depth * (1 if r > p else 0)

HIDE = lambda: Box((0, -9, 0), (.01, -8.9, .01), (0, 0, 0), hidden=True)
CAR_N = len(car(CAR[0], CAR[1])) + 1                       # boîtes de la voiture fixe + sa veilleuse intérieure

# ---------------- scene for a frame ----------------
def _leaf(x0, z0, length, ang, h, col, th=.07, n=5, sgn=1., mat=M_DOOR):
    """door leaf hinged at (x0,z0), closed along +x, opening toward -z (sgn=1) or +z (sgn=-1) by ang (rad): stepped slabs"""
    out = []
    for q in range(n):
        u0, u1 = q / n, (q + 1) / n
        xa, za = x0 + math.cos(ang) * length * u0, z0 - math.sin(ang) * length * u0 * sgn
        xb, zb = x0 + math.cos(ang) * length * u1, z0 - math.sin(ang) * length * u1 * sgn
        out.append(Box((min(xa, xb) - th / 2, 0, min(za, zb) - th / 2), (max(xa, xb) + th / 2, h, max(za, zb) + th / 2), col, mat=mat))
    return out

def scene_for(ctx, extra):
    base = station(); sc = copy.copy(base); bx = list(base.boxes); I = base.idx
    def setemis(i, on, col=None):
        o = bx[i]; c = tuple((o.col * 255).astype(int)) if col is None else col
        if on <= .02: bx[i] = Box(o.lo, o.hi, tuple(int(v * .35) for v in c), cast=False)
        else: bx[i] = Box(o.lo, o.hi, c, emis=(o.emis or 1.7) * on, cast=False)
    sm = ctx.get('shopmask') or [1.] * len(SHOP_TUBES)
    for k in range(len(SHOP_TUBES)): setemis(I['tubes'] + k, ctx['shop'] * sm[k])
    setemis(I['till_tube'], ctx['till']); setemis(I['porch'], ctx['porch']); setemis(I['tubeL'], ctx['tubeL'])
    if ctx['tubeR'] < 0:      # exploded: broken housing only
        o = bx[I['tubeR']]; bx[I['tubeR']] = Box(o.lo + np.array([0, .03, 1.1], np.float32), o.hi - np.array([0, 0, 1.1], np.float32), (40, 40, 44), cast=False)
    else: setemis(I['tubeR'], ctx['tubeR'])
    setemis(I['tubeL'] - 1, ctx['blue'], (60, 120, 255))
    o = bx[I['fridge'] + 1]; on = ctx['fridge'] > .1
    bx[I['fridge'] + 1] = Box(o.lo, o.hi, (210, 230, 255) if on else (40, 46, 56), tex={'+x': fridge_tex(1 if on else 0)}, texemis=1.0 * ctx['fridge'] + .05, cast=False)
    o = bx[I['till_screen'] + 1]; bx[I['till_screen'] + 1] = Box(o.lo, o.hi, (60, 200, 120), emis=1.0 * min(1, ctx['till'] + ctx['shop']), cast=False)
    o = bx[I['pylon']]; bx[I['pylon']] = Box(o.lo, o.hi, (16, 30, 120), tex={'+z': sign_tex('pylon'), '-z': sign_tex('pylon')}, texemis=1.1 * ctx['pylon'])
    # front door: closed (default) or open (leaf swung inward)
    d0, dn = I['door'], I['door_n']
    if ctx['door'] > 0:
        ang = ctx['door'] * math.pi / 2
        for i in range(dn): bx[d0 + i] = HIDE()
        L = DOOR[1] - DOOR[0] - .02; fr = (60, 62, 68)
        for q in range(4):
            u0, u1 = q / 4, (q + 1) / 4
            xa, za = DOOR[0] + math.cos(ang) * L * u0, FRONT + .1 + math.sin(ang) * L * u0
            xb, zb = DOOR[0] + math.cos(ang) * L * u1, FRONT + .1 + math.sin(ang) * L * u1
            for (ya, yb) in ((0, .12), (2.18, 2.3)):
                bx.append(Box((min(xa, xb) - .03, ya, min(za, zb) - .03), (max(xa, xb) + .03, yb, max(za, zb) + .03), fr))
        xe, ze = DOOR[0] + math.cos(ang) * L, FRONT + .1 + math.sin(ang) * L
        bx.append(Box((xe - .04, 0, ze - .04), (xe + .04, 2.3, ze + .04), fr)); bx.append(Box((DOOR[0] - .04, 0, FRONT + .06), (DOOR[0] + .04, 2.3, FRONT + .14), fr))
    if ctx['lock']:
        bx.append(Box((DOOR[1] - .21, 1.17, FRONT + .14), (DOOR[1] - .13, 1.23, FRONT + .17), (230, 40, 40), emis=.6))
    # storeroom door: handle turning, shaking, opening toward the shop (-z)
    h0 = I['handle']; hu = ctx['handle']; sang = ctx['sdoor']; shk = ctx['sshake']
    if hu > 0:
        ang = hu * .9; bx[h0] = HIDE()
        for q in range(3):
            u = (q + .5) / 3; cx = SDOOR[1] - .14 - math.cos(ang) * .2 * u; cy = 1.025 - math.sin(ang) * .2 * u
            bx.append(C((cx, cy, BACK + .025), (.08, .06, .05), (200, 200, 206), mat=M_METAL))
    if sang > 0 or shk:
        bx[I['sdoor']] = HIDE()
        bx += _leaf(SDOOR[0], BACK + .1 - shk, SDOOR[1] - SDOOR[0] - .02, sang, 2.15, (130, 136, 142), th=.08, n=6 if sang > 0 else 1)
        if sang > 0 and ctx.get('sdoor_black', True): bx.append(Box((SDOOR[0] + .25, 0, BACK + .2), (SDOOR[1], 2.1, BACK + .7), (1, 1, 2), cast=False))
    if ctx['cart'] is not None:
        cx, cz = ctx['cart']; bx += cart(cx, cz)
    if ctx['finger'] > 0: bx += finger(ctx['finger'], -3.06, BACK + .02, ctx.get('t', 0.))
    if ctx['rshake'] and ctx['rdoor'] <= 0:      # knocks on the rear service door
        o = bx[I['rdoor']]; bx[I['rdoor']] = Box(o.lo - np.array([0, 0, ctx['rshake']], np.float32), o.hi - np.array([0, 0, ctx['rshake']], np.float32), (84, 92, 88), mat=M_DOOR)
    if ctx['rdoor'] > 0:     # rear exit door opening outward (+z)
        bx[I['rdoor']] = HIDE()
        bx += _leaf(RDOOR[0], REAR + .1, RDOOR[1] - RDOOR[0] - .02, ctx['rdoor'], 2.2, (84, 92, 88), n=5, sgn=-1.)
        if ctx.get('rdoor_black', True): bx.append(Box((RDOOR[0] + .2, 0, REAR - .3), (RDOOR[1] - .05, 2.15, REAR + .02), (1, 1, 2), cast=False))
    if ctx.get('car_static', 1) == 0:                     # la voiture bouge : on retire la voiture fixe de P1
        for i in range(I['car'], I['car'] + CAR_N): bx[i] = HIDE()
    for (lo, hi) in ctx.get('hide', ()):                   # zones retirées du décor (ex. le mur du fond « avalé » par le noir)
        for i, b in enumerate(bx):
            c_ = (b.lo + b.hi) / 2
            if all(lo[k] <= c_[k] <= hi[k] for k in range(3)): bx[i] = HIDE()
    sc.boxes = bx + list(extra)
    return sc

def lights_for(ctx, cm, extra, g):
    L = []; f = ctx
    for (x, on) in ((TUBE_L[0], f['tubeL']), (TUBE_R[0], f['tubeR'])):
        if on > .02:
            for dz in (-.6, 1.6): L.append(Light((x, 4.4, TUBE_L[1] + dz), (.86, .94, 1.), 1.25 * on, 3.8, True, None, OUT, .35, 'can'))
    if f['porch'] > .02: L.append(Light((PORCH[0], 2.82, PORCH[1]), (1., .84, .58), 4.4 * f['porch'], 3.4, True, ((0, -1, -.1), .80, .71), OUT, .5, 'porch'))
    if f['blue'] > .02: L.append(Light((0, 4.35, CAN[2] - .3), (.3, .5, 1.), .7 * f['blue'], 5., False, None, OUT, .3, 'blue'))
    if f['pylon'] > .02:
        L.append(Light((PYLON[0], 7.4, PYLON[1] + 1.0), (1., .18, .16), 1.3 * f['pylon'], 5.5, False, None, OUT, .5, 'pyl'))
        L.append(Light((PYLON[0], 5.0, PYLON[1] + 1.0), (.25, .4, 1.), 1.3 * f['pylon'], 5.5, False, None, OUT, .5, 'pyl'))
    L.append(Light((LAMP[0] - 1.2, 6.4, LAMP[1]), (1., .6, .26), 2.6, 10., False, None, OUT, .12, 'lamp'))
    L.append(Light((-25, 32, -38), (.32, .40, .62), f.get('sky', .62), 60., False, None, (1., 0., 0.), 0., 'sky'))
    L.append(Light((30, 25, 40), (.25, .30, .45), .35, 60., False, None, (1., 0., 0.), 0., 'sky2'))
    if f.get('rearlamp', 1.) > 0: L.append(Light(((RDOOR[0] + RDOOR[1]) / 2, 2.6, REAR + .55), (1., .78, .5), .7 * f.get('rearlamp', 1.) * flick(g, 7, .8, 31, .75), 3.2, False, None, OUT, .2, 'rear'))
    if f.get('carin', 1.) > 0: L.append(Light((CAR[0], 1.3, CAR[1] - .2), (1., .85, .6), .8 * f.get('carin', 1.), 2.2, False, None, OUT, 0., 'carin'))
    if f.get('lamp', 1.) <= 0: L = [l for l in L if l.key != 'lamp']
    if f['head'] > .02:
        for sx in (-1, 1):
            L.append(Light((CAR[0] + sx * .62, .8, CAR_FRONT + .08), (1., .95, .8), 3.4 * f['head'], 7.5, True, ((0, -.13, 1), .96, .86), OUT, 1.3, 'head'))
    if f['shop'] > .02:
        sm = f.get('shopmask') or [1.] * len(SHOP_TUBES)
        for k_, (tx, tz) in enumerate(SHOP_TUBES):
            if sm[k_] > .02: L.append(Light((tx, 3.0, tz), (1., .97, .9), .8 * f['shop'] * sm[k_], 3.3, False, None, SHOP, .12, 'shop'))
        L.append(Light((SDOOR[0] + .5, .08, BACK + .45), (.9, 1., .95), .35 * f['shop'], .9, False, None, STORE, 0., 'leak'))
    if f['till'] > .02: L.append(Light((TILL_TUBE[0], 3.0, TILL_TUBE[1]), (1., .97, .9), 1.0 * f['till'], 3.6, True, None, SHOP, .15, 'till'))
    if f['fridge'] > .02:
        for fz in (10.4, 13.0): L.append(Light((SX0 + 1.3, 1.2, fz), (.68, .84, 1.), .5 * f['fridge'], 2.2, False, None, (0., 1., 0.), 0., 'fridge'))
    L.append(Light((PANEL[0] - .2, PANEL[1] + .3, PANEL[2] - .2), (1., .1, .08), .3, 1.1, False, None, STORE, 0., 'led'))
    if f['flash'] > 0: L.append(Light((TUBE_R[0], 4.2, TUBE_R[1]), (.9, .95, 1.), 9 * f['flash'], 6., False, None, (1., .3, 0.), .8, 'flash'))
    if f.get('fill', 1.) > 0:
        p = cm[0]; L.append(Light((p[0], p[1] + .35, p[2]), (.6, .68, .9), .5 * f.get('fill', 1.), 3.0, False, None, None, 0., 'fill'))
    L += list(extra)
    return [l for l in L if l.i > 1e-3]


def finger(prog, door_x, door_z, t=0.):
    """long black finger sliding out under the storeroom door along the floor (toward -z)"""
    if prog <= 0: return []
    L = .55 * prog; bx = []
    n = max(1, int(L / .06))
    for q in range(n):
        u = q / max(1, n - 1)
        zz = door_z + .02 - u * L
        bx.append(C((door_x + .02 * math.sin(t * 6 + u * 3) * u, .035, zz), (.07 + (.015 if q % 4 == 0 else 0), .06, .07), (4, 4, 6), refl=.04, cast=False))
    bx.append(C((door_x + .02 * math.sin(t * 6 + 3), .02, door_z - L - .03), (.045, .03, .04), (30, 30, 34), refl=.6, cast=False))     # nail
    return bx


# ---------------------------------------------------------------- éléments mobiles du film « Le Remplaçant » (mot, écran, téléphone fixe, voiture), pilotés par `state`
COL_CAR = (120, 22, 28)
COUNTER_TOP = 1.11

@functools.lru_cache(maxsize=2)
def note_tex():
    im = Image.new('RGBA', (72, 50), (240, 236, 214, 255)); dr = ImageDraw.Draw(im); dr.fontmode = '1'
    f = _font(8)
    for i, t in enumerate(('NE', 'LAISSE', 'ENTRER', 'PERSONNE', 'APRES 3H')):
        w = dr.textlength(t, font=f); dr.text(((72 - w) / 2, 2 + i * 9), t, font=f, fill=(24, 20, 20, 255))
    dr.line([(2, 48), (70, 48)], fill=(160, 150, 130, 255))
    return np.flipud(np.array(im))                       # le texte se lit depuis la face avant (-z) : la face du dessus est lue de bas en haut

def note(x=4.0, z=9.8):
    """le mot de Marc, posé À PLAT sur le comptoir (son dessous touche le plateau)"""
    return [B((x - .26, COUNTER_TOP, z - .19), (.52, .012, .38), (240, 236, 214), tex={'+y': note_tex()}, texemis=.12, cast=False)]

MON = (3.1, 9.45)                                        # écran de surveillance, sur son pied, sur le comptoir
def monitor(feed=None, on=1.):
    x, z = MON; bx = [B((x - .16, COUNTER_TOP, z - .12), (.32, .03, .24), (40, 42, 46), mat=M_METAL),     # pied
                      B((x - .03, COUNTER_TOP + .03, z - .03), (.06, .2, .06), (40, 42, 46), mat=M_METAL),  # col
                      B((x - .28, COUNTER_TOP + .22, z - .09), (.56, .42, .2), (44, 46, 52), mat=M_METAL)]  # coque
    tex = feed if (feed is not None and on > 0) else np.full((24, 32, 4), (6, 12, 8, 255), np.uint8)
    bx.append(B((x - .24, COUNTER_TOP + .26, z - .095), (.48, .34, .005), (10, 12, 10), tex={'-z': tex}, texemis=(.6 if feed is not None else 1.5) * on, cast=False))
    bx.append(C((x + .22, COUNTER_TOP + .27, z - .098), (.025, .025, .005), (255, 40, 30), emis=2. * on, cast=False))
    return bx

LAND_X, LAND_Z = 5.5, 9.72
def landline(ring=0.):
    """téléphone de la boutique, sur le comptoir (le combiné est décalé quand on décroche : lifted=1 le retire)"""
    bx = [B((LAND_X - .13, COUNTER_TOP, LAND_Z - .12), (.26, .07, .24), (28, 28, 32)), B((LAND_X - .1, COUNTER_TOP + .07, LAND_Z - .1), (.2, .035, .07), (200, 200, 205))]
    bx.append(C((LAND_X + .09, COUNTER_TOP + .09, LAND_Z + .02), (.05, .03, .03), (255, 60, 40) if int(ring * 9) % 2 else (90, 20, 16), emis=2.2 if int(ring * 9) % 2 else 0.2, cast=False))
    return bx
def handset_on_base(on_cradle=True):
    if not on_cradle: return []
    return [B((LAND_X - .14, COUNTER_TOP + .07, LAND_Z + .01), (.28, .05, .07), (24, 24, 28))]

def _parts(lights=1., high=0., brake=0., rev=0., fog=0.):
    """pièces de la voiture de P1 en coordonnées locales (x droite, z avant) : (centre, taille, couleur, options)"""
    P = [((0, .55, 0), (1.8, .55, 4.3), COL_CAR, dict(refl=.18, mat=M_METAL)),
         ((0, .9, .2), (1.76, .16, 3.6), COL_CAR, dict(refl=.18, mat=M_METAL)),
         ((0, 1.25, -.25), (1.6, .55, 2.1), tuple(int(lerp_(a, b, fog)) for a, b in zip((26, 28, 34), (176, 182, 188))), dict(refl=.35 * (1 - fog))),
         ((0, 1.55, -.25), (1.62, .08, 1.9), COL_CAR, dict(refl=.18, mat=M_METAL))]
    for sx in (-1, 1):
        for sz in (-1, 1): P.append(((sx * .82, .33, sz * 1.35), (.26, .66, .7), (14, 14, 16), {}))
        on = max(lights, high)
        P.append(((sx * .62, .78, 2.16), (.4, .14, .04), (255, 240, 200) if on > 0 else (90, 90, 80), dict(emis=(2.4 + 1.6 * high) * (1 if on > 0 else 0), cast=False)))
        P.append(((sx * .66, .8, -2.16), (.34, .12, .04), (255, 40, 30), dict(emis=1.2 + 1.6 * brake, cast=False)))
        if rev > 0: P.append(((sx * .3, .62, -2.165), (.14, .08, .03), (255, 255, 240), dict(emis=2.5 * rev, cast=False)))
    P.append(((0, .5, 2.17), (.5, .12, .03), (230, 230, 225), dict(tex={'+z': sign_tex('plate')})))
    P.append(((0, .5, 2.15), (1.7, .1, .06), (40, 40, 44), {}))
    return P

def lerp_(a, b, t): return a + (b - a) * t
def car_pose(cx, cz, h=0., lights=1., high=0., brake=0., rev=0., shake=(0., 0.), cell=.42, cabin=True, fog=0.):
    """la voiture de P1 posée en (cx, cz) avec un cap h (radians, 0 = vers +z). Hors des quatre caps droits,
    les grandes pièces sont découpées en colonnes (même principe en escalier que les portes)."""
    c, s = math.cos(h), math.sin(h); bx = []; ox, oy = shake
    def W(lx, lz): return (cx + ox + lx * c + lz * s, cz - lx * s + lz * c)
    straight = min(abs(s), abs(c)) < 1e-3
    for k_, (p, sz, col, kw) in enumerate(_parts(lights, high, brake, rev, fog)):
        if not cabin and k_ == 2: continue
        if straight or (sz[0] < .7 and sz[2] < .8):
            x, z = W(p[0], p[2]); wx = abs(c) * sz[0] + abs(s) * sz[2]; wz = abs(s) * sz[0] + abs(c) * sz[2]
            kw2 = dict(kw)
            if 'tex' in kw2 and not straight: kw2.pop('tex')
            if 'tex' in kw2 and straight:
                face = {(1, 0): '+z', (-1, 0): '-z', (0, 1): '+x', (0, -1): '-x'}[(round(c), round(s))]
                kw2['tex'] = {face: kw2['tex']['+z']}
            bx.append(C((x, p[1] + oy, z), (wx, sz[1], wz), col, **kw2)); continue
        nx = max(1, int(round(sz[0] / cell))); nz = max(1, int(round(sz[2] / cell)))
        ex, ez = sz[0] / nx, sz[2] / nz; kw2 = {k: v for k, v in kw.items() if k != 'tex'}
        for i in range(nx):
            for j in range(nz):
                lx = p[0] - sz[0] / 2 + (i + .5) * ex; lz = p[2] - sz[2] / 2 + (j + .5) * ez
                x, z = W(lx, lz); e = .9
                bx.append(C((x, p[1] + oy, z), ((abs(c) * ex + abs(s) * ez) * e, sz[1], (abs(s) * ex + abs(c) * ez) * e), col, **kw2))
    return bx

def car_lights(cx, cz, h=0., lights=1., high=0., brake=0., rev=0., inner=.8, flick_=1.):
    c, s = math.cos(h), math.sin(h); L = []
    def W(lx, y, lz): return (cx + lx * c + lz * s, y, cz - lx * s + lz * c)
    f = (s, -.13 + .09 * high, c)
    if lights > 0 or high > 0:
        for sx in (-1, 1):
            L.append(Light(W(sx * .62, .8, 2.24), (1., .96, .84), (3.4 + 3.2 * high) * flick_, 7.5 + 9 * high, True,
                           (f, .96 - .015 * high, .86 - .03 * high), OUT, 1.3 + .9 * high, 'head'))
    for sx in (-1, 1): L.append(Light(W(sx * .66, .8, -2.4), (1., .15, .1), .35 + .9 * brake, 1.6, False, None, OUT, .15, 'tail'))
    if rev > 0: L.append(Light(W(0, .7, -2.6), (1., 1., .95), 1.4 * rev, 3.5, False, ((-s, -.2, -c), .7, .3), OUT, .2, 'rev'))
    if inner > 0: L.append(Light(W(0, 1.3, -.2), (1., .85, .6), inner, 2.2, False, None, None, 0., 'carin'))
    return L


WX_PHONE, WZ_PHONE = 2.41, 7.95
@functools.lru_cache(maxsize=4)
def _photo_tex(path):
    im = Image.open(path).convert('RGBA').resize((18, 32), Image.BILINEAR)
    return np.array(im)

@functools.lru_cache(maxsize=64)
def _feed_tex(folder, i):
    return np.array(Image.open(os.path.join(folder, f'f_{i:03d}.png')).convert('RGBA'))

def mobile_parts(state, t, skip_car=False):
    """boîtes et lumières des éléments qui bougent, selon `state` : note (0/1), monitor (0..1), landline_ring (temps de sonnerie, 0 = muet), handset (1 = sur son socle), car ([cx, cz, cap, feux, marche arrière])"""
    bx = []; lx = []; s = state or {}
    if s.get('note'): bx += note(*s.get('note_at', (4.15, 9.8)))
    if s.get('monitor') is not None: bx += monitor(_feed_tex(s['monitor_feed_dir'], int(s['monitor_feed'])) if (s.get('monitor_feed') is not None and int(s['monitor_feed']) >= 0 and s.get('monitor_feed_dir')) else None, float(s['monitor']))
    if s.get('landline'): bx += landline(float(s.get('landline_ring', 0.))) + handset_on_base(bool(s.get('handset', 1)))
    if s.get('handset_pos'):                                          # combiné en main (à l'oreille) : même main du décrochage au raccrochage
        hx, hy, hz = s['handset_pos']; bx += [C((hx, hy, hz), (.08, .34, .1), (30, 30, 34)), C((hx, hy - .14, hz - .02), (.1, .06, .1), (24, 24, 28))]
    if s.get('phone_photo'):                                          # le téléphone de la femme contre la vitre : une vraie photo (rendue par le moteur), écran tourné vers la boutique (+z)
        bx += [C((WX_PHONE, 1.5 + float(s.get('phone_y', 0.)), WZ_PHONE), (.17, .30, .03), (24, 24, 28), tex={'+z': _photo_tex(s['phone_photo'])}, texemis=.3, cast=False)]
    car_ = s.get('car')
    if car_ is not None:
        cx, cz, h, li, rv = (list(car_) + [0., 1., 0.])[:5]
        if cz > -60:
            if not skip_car: bx += car_pose(cx, cz, h, lights=li, rev=rv)
            lx += car_lights(cx, cz, h, lights=li, rev=rv, inner=0.)
    return bx, lx


# ---------------------------------------------------------------- le lieu pour PIXEL 3D
class PompeStation:
    """interface d'un lieu de PIXEL 3D (`RoomSet`) : base, ancres, scène par image (état du monde), lumières par image"""
    ZONES = {'OUT': OUT, 'SHOP': SHOP, 'STORE': STORE}

    def __init__(self, spec):
        self.spec = dict(spec or {}); self.spec.setdefault('outdoor', True); self.spec.setdefault('weather', 'rain'); self.base = None; self.room_rects = []; self.light_defs = []; self.door_info = {}
        self.anchors = {'hero': (5.1, 10.5), 'comptoir': (4.4, 9.55), 'vitre': (2.0, 7.4), 'porte': (0., 7.6), 'pompes': (0., 1.), 'voiture': (CAR[0], CAR[1]), 'reserve': (-2.0, 17.0), 'route': (0., -20.)}

    def build(self):
        if self.base is None: self.base = build_station()
        return self

    def _ctx(self, state, g):
        c = ctx_default(); c.update(dict(sky=.62, fill=1., lamp=1., rearlamp=1., carin=1., car_static=1, shopmask=None, sdoor_black=True, rdoor_black=True, hide=(), t=g))
        for k, v in (state or {}).items():
            if k in c or k in ('shopmask', 'hide', 'rain', 'sdoor_black', 'rdoor_black', 'carin', 'rearlamp', 'lamp', 'fill', 'sky', 'car_static'): c[k] = v
        return c

    def scene(self, state, t, u):
        self.build(); ctx = self._ctx(state, t)
        mb, _ = mobile_parts(state, t)
        sc = scene_for(ctx, mb); self._sc = sc
        return sc

    def voxel_native(self):
        """VOXEL a ses propres éléments pour ceci : (indices de boîtes PS1 à ne pas peindre, éléments natifs [{type, at, ...}] en repère PS1). Un élément « adapté » à chaque style, pas le même objet peint deux fois"""
        self.build(); I = self.base.idx
        hide = set(range(I['trees0'], I['trees1'])) | set(range(I['car'], I['car'] + CAR_N))
        items = [{'type': 'craft:pine_tree' if k % 2 else 'craft:spruce_tree', 'at': [tx, tz], 'scale': h / 7., 'seed': k} for k, (tx, tz, h) in enumerate(TREES)]
        items.append({'type': 'vox:kk_city/car_sedan', 'at': [CAR[0], CAR[1]], 'rot': VOX_CAR_ROT, 'length': 4.3, 'native_heading': 0.})
        return hide, items

    def mobile_native(self, state, t):
        """éléments mobiles pour VOXEL : boîtes (sans la voiture), lumières, et la voiture en élément natif VOXEL"""
        mb, ml = mobile_parts(state, t, skip_car=True)
        c = (state or {}).get('car'); items = []
        if c is not None and c[1] > -60: items.append({'type': 'vox:kk_city/car_sedan', 'at': [c[0], c[1]], 'rot': VOX_CAR_ROT, 'length': 4.3})
        return mb, [(tuple(float(v) for v in l.pos), l.col, float(l.i), float(l.r)) for l in ml], items

    def mobile(self, state, t):
        """éléments mobiles seuls (pour un autre peintre que PS1) : (boîtes, [(position, couleur, puissance, rayon)])"""
        mb, ml = mobile_parts(state, t)
        return mb, [(tuple(float(v) for v in l.pos), l.col, float(l.i), float(l.r)) for l in ml]

    def lights(self, state, t, u, cam_pos):
        self.build(); ctx = self._ctx(state, t)
        cm = (tuple(cam_pos), 0., 0., 0., 60.)
        sc = getattr(self, '_sc', None)
        if sc is not None:                                    # brume et lumière ambiante du premier moteur : dehors ou dans la boutique selon la caméra
            inside = sc.zone_fn(np.asarray(cam_pos, np.float32)[None])[0] > 0
            sc.fogk = ctx.get('fogk', .012 if inside else .03); sc.fog = ctx.get('fogcol', (.016, .02, .03))
            sc.ambient = ctx.get('amb', (.035, .037, .046) if inside else (.04, .045, .062))
        _, ml = mobile_parts(state, t)
        L = lights_for(ctx, cm, ml, t)
        return [l.tup(bool(l.shadow)) for l in L]
