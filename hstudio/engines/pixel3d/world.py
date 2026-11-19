"""Worlds for the pixel3d engine: painted skies with horizon backdrops, ground materials, weather, a large prop
library, deterministic scattering, and generators of complete places (forest, beach, city, castle, classroom...).
Everything is built from boxes and procedural functions: no image is ever loaded."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .r3d import B, C, M_WOODV, M_PLASTER, M_METAL, M_CEIL, M_DOOR, M_CARD, M_FABRIC, vnoise2, fbm, h2
from ...paths import FONT_PIXEL

TIME = [0.]          # seconds since the start of the episode (set by frame.build_frame), for water and weather

# ================================================================== skies
PALETTES = {
    'day':      dict(zen=(.28, .50, .92), hor=(.70, .82, .96), sun=(1, .97, .88), cloud=(.98, .98, 1.), shade=(.70, .76, .88), light=1., cover=.38),
    'sunset':   dict(zen=(.20, .18, .44), hor=(1., .52, .28), sun=(1, .72, .40), cloud=(1., .64, .46), shade=(.46, .26, .36), light=.62, cover=.42),
    'dawn':     dict(zen=(.30, .36, .64), hor=(.98, .74, .64), sun=(1, .86, .70), cloud=(.98, .82, .80), shade=(.56, .50, .64), light=.72, cover=.36),
    'night':    dict(zen=(.008, .012, .045), hor=(.04, .06, .13), moon=(.94, .94, .86), cloud=(.08, .09, .14), shade=(.03, .03, .06), light=.09, cover=.30, stars=1.),
    'overcast': dict(zen=(.52, .55, .60), hor=(.72, .74, .76), cloud=(.80, .80, .82), shade=(.50, .52, .56), light=.75, cover=.9),
    'storm':    dict(zen=(.12, .13, .16), hor=(.26, .28, .31), cloud=(.28, .29, .32), shade=(.10, .10, .13), light=.3, cover=.95),
}
SKY_NAMES = tuple(PALETTES)
LAYER_COLORS = {'mountains': (.34, .38, .48), 'snow_mountains': (.36, .40, .52), 'hills': (.30, .44, .32), 'forest': (.10, .22, .12),
                'city': (.22, .24, .30), 'dunes': (.78, .62, .40), 'volcano': (.20, .16, .16), 'castle': (.24, .24, .28), 'islands': (.20, .36, .22)}

def _ridge(x, seed, oct=4):
    s = 0.; a = .5; f = 1.
    for o in range(oct):
        n = 1 - np.abs(2 * vnoise2(x * f, np.full_like(x, .5 + seed), seed + o) - 1); s = s + a * n * n; f *= 2.2; a *= .5
    return s

def make_sky(spec, sun_vec):
    """function(D (n,3)) -> rgb for rays that hit nothing"""
    pal = dict(PALETTES.get(spec.get('sky', 'day'), PALETTES['day']))
    cover = float(spec.get('clouds', pal.get('cover', .4))); seed = int(spec.get('seed', 0))
    zen, hor = np.array(pal['zen'], np.float32), np.array(pal['hor'], np.float32)
    sv = np.asarray(sun_vec, np.float32); sv = sv / (np.linalg.norm(sv) + 1e-9)
    mv = np.array([-.45, .42, .78], np.float32); mv /= np.linalg.norm(mv)
    layers = spec.get('backdrop') or []
    if isinstance(layers, str): layers = [layers]
    def fn(D):
        D = np.asarray(D, np.float32); y = np.clip(D[:, 1], -1, 1)
        el = np.arcsin(y); az = np.arctan2(D[:, 0], D[:, 2]); e = np.clip(el / (math.pi / 2), 0, 1)
        t = e ** .55; col = hor[None] * (1 - t[:, None]) + zen[None] * t[:, None]
        if 'sun' in pal and spec.get('sun', True):
            cs = D @ sv
            col += np.array(pal['sun'], np.float32)[None] * (np.where(cs > .9993, 1.6, 0.) + .5 * np.exp((cs - 1) * 90) + .22 * np.exp((cs - 1) * 9))[:, None]
        if pal.get('stars'):
            gx = np.floor((az + math.pi) * 160); gy = np.floor(el * 160)
            hs = h2(gx, gy, 5 + seed); tw = .6 + .4 * np.sin(TIME[0] * 3 + hs * 50)
            col += (np.where((hs > .985) & (el > .03), 1., 0.) * tw * (hs - .985) * 60)[:, None] * np.array([.8, .85, 1.], np.float32)
            cm = D @ mv; disc = cm > .9988; crescent = (D @ (mv + np.array([.03, .02, 0], np.float32)) / np.linalg.norm(mv + np.array([.03, .02, 0], np.float32))) > .9990
            col = np.where((disc & ~crescent)[:, None], np.array(pal['moon'], np.float32)[None], col) + (.15 * np.exp((cm - 1) * 40))[:, None] * np.array([.6, .7, 1.], np.float32)
        if cover > 0:
            up = np.maximum(y, .04); u = D[:, 0] / up * .55 + TIME[0] * .01; v = D[:, 2] / up * .55
            n = fbm(u, v, 31 + seed, 4); dens = np.clip((n - (1 - cover)) * 3.2, 0, 1) * np.clip(el * 7, 0, 1)
            sh = np.clip(fbm(u * 1.7 + 4, v * 1.7, 37 + seed, 2) * 1.3 - .2, 0, 1)
            cc = np.array(pal['cloud'], np.float32)[None] * (1 - sh[:, None] * .5) + np.array(pal['shade'], np.float32)[None] * sh[:, None] * .5
            col = col * (1 - dens[:, None]) + cc * dens[:, None]
        for i, L in enumerate(layers):         # far to near
            L = {'type': L} if isinstance(L, str) else dict(L); kind = L.get('type', 'mountains')
            base = math.radians(float(L.get('base', {'mountains': 1.5, 'snow_mountains': 2., 'hills': .6, 'forest': .4, 'city': .3, 'dunes': .3, 'volcano': 1., 'castle': .4, 'islands': .1}.get(kind, 1.))))
            amp = math.radians(float(L.get('height', {'mountains': 11, 'snow_mountains': 15, 'hills': 4, 'forest': 3.2, 'city': 7, 'dunes': 2.5, 'volcano': 12, 'castle': 9, 'islands': 2.5}.get(kind, 6))))
            sd = seed * 7 + i * 13 + 1; x = (az + math.pi) * float(L.get('freq', 1.))
            if kind in ('mountains', 'snow_mountains', 'volcano'):
                h = base + amp * _ridge(x * 2.2, sd)
                if kind == 'volcano': h = np.maximum(h * .5, base + amp * np.clip(1 - np.abs(np.angle(np.exp(1j * (az - float(L.get('at', 0)))))) * 3.2, 0, 1) ** 1.3)
            elif kind == 'hills': h = base + amp * fbm(x * 1.6, np.full_like(x, .3), sd, 3)
            elif kind == 'dunes': h = base + amp * (np.sin(x * 5 + fbm(x, np.full_like(x, .2), sd, 2) * 4) * .5 + .5) ** 2
            elif kind == 'forest':
                f_ = (x * 46) % 1; cell = np.floor(x * 46); th = .6 + .4 * h2(cell, np.zeros_like(cell), sd)
                h = base + amp * (th * (1 - np.abs(2 * f_ - 1)) * .9 + .25 * fbm(x * 3, np.full_like(x, .7), sd, 2))
            elif kind == 'islands': h = base + amp * np.clip(fbm(x * 2.5, np.full_like(x, .1), sd, 3) * 2 - 1.1, 0, 1)
            elif kind == 'castle':
                c0 = float(L.get('at', 0)); dx = np.angle(np.exp(1j * (az - c0)))
                body = np.abs(dx) < .16; tw = (np.abs(np.abs(dx) - .13) < .025)
                cren = ((dx * 140) % 2 < 1)
                h = np.where(tw, base + amp * 1.25 + np.where(cren, math.radians(.4), 0), np.where(body, base + amp * .75 + np.where(cren, math.radians(.35), 0), -1.))
            else:                                   # city skyline
                cell = np.floor(x * float(L.get('density', 30))); hb = h2(cell, np.ones_like(cell), sd)
                h = base + amp * (.25 + .75 * hb ** 1.6)
            m = el < h
            if not m.any(): continue
            lc = np.array(L.get('color', LAYER_COLORS.get(kind, (.3, .3, .35))), np.float32)
            lc = lc if max(lc) <= 1 else lc / 255.
            haze = float(L.get('haze', .45 if i == 0 and len(layers) > 1 else .25))
            lit = pal['light']
            c = lc[None] * lit * (np.where(np.gradient(h) > 0, 1.08, .86)[:, None] if kind in ('mountains', 'snow_mountains', 'volcano') else 1.)
            if kind == 'snow_mountains' or (kind == 'mountains' and L.get('snow')):
                snow = el > h - amp * .28
                c = np.where(snow[:, None], np.array([.92, .94, 1.], np.float32)[None] * lit, c)
            if kind == 'city':
                wx = (x * float(L.get('density', 30)) * 7) % 1; wy = (el * 900) % 1
                win = (wx > .35) & (wx < .7) & (wy > .4) & (h2(np.floor(x * 210), np.floor(el * 900), sd) > (.55 if pal.get('stars') else .2))
                wincol = np.array([1., .82, .45], np.float32) if pal.get('stars') else np.array([.55, .62, .75], np.float32) * lit
                c = np.where(win[:, None], wincol[None], c)
            if kind == 'volcano':
                glow_ = np.clip(1 - (h - el) / math.radians(2), 0, 1) * (np.abs(np.angle(np.exp(1j * (az - float(L.get('at', 0)))))) < .04)
                c = c + glow_[:, None] * np.array([1., .35, .1], np.float32)[None]
            c = c * (1 - haze) + col * haze
            col = np.where(m[:, None], c, col)
        return col
    return fn

# ================================================================== ground
GROUNDS = {'grass': (.16, .30, .12), 'sand': (.78, .66, .46), 'snow': (.86, .89, .94), 'dirt': (.32, .24, .16), 'mud': (.22, .16, .11),
           'stone': (.42, .41, .40), 'cobble': (.40, .38, .36), 'rock': (.36, .35, .34), 'asphalt': (.12, .12, .13), 'road': (.13, .13, .14),
           'water': (.06, .20, .30), 'ice': (.62, .74, .84), 'lava': (.40, .08, .02), 'moss': (.18, .26, .12), 'leaves': (.40, .22, .08),
           'wood': (.42, .28, .17), 'tiles': (.34, .34, .32), 'carpet': (.30, .12, .12), 'concrete': (.30, .30, .29), 'checker': (.38, .38, .38),
           'linoleum': (.30, .34, .30), 'marble': (.66, .65, .63), 'plank_dock': (.38, .27, .17)}

def ground(kind, x, z, wet=False):
    """albedo (n,3) and reflectivity (n) of a ground material"""
    n = len(x); base = np.array(GROUNDS.get(kind, GROUNDS['grass']), np.float32)
    refl = np.full(n, .25 if wet else .02, np.float32)
    if kind == 'grass':
        g = .75 + .35 * fbm(x * 1.3, z * 1.3, 51, 3) + .18 * vnoise2(x * 9, z * 9, 52)
        tuft = vnoise2(x * 23, z * 23, 53) > .72
        a = base[None] * g[:, None]; a[tuft] *= np.array([.75, 1.15, .7], np.float32); refl[:] = .02
    elif kind == 'sand':
        rip = .5 + .5 * np.sin(x * 7 + fbm(x * .5, z * .5, 54, 2) * 6)
        a = base[None] * (.86 + .1 * rip + .1 * vnoise2(x * 30, z * 30, 55))[:, None]; refl[:] = .03
    elif kind == 'snow':
        a = base[None] * (.92 + .08 * fbm(x * 1.1, z * 1.1, 56, 2))[:, None]
        spark = vnoise2(x * 60, z * 60, 57) > .93; a[spark] = (1., 1., 1.); refl[:] = .08
    elif kind in ('water', 'lava'):
        t = TIME[0]
        w = .5 + .25 * np.sin(x * 2.1 + t * 1.3) * np.sin(z * 1.7 - t * .9) + .25 * vnoise2(x * 3 + t * .3, z * 3, 58)
        a = base[None] * (.75 + .5 * w)[:, None]
        if kind == 'water':
            foam = vnoise2(x * 8 + t, z * 8, 59) * w > .62; a[foam] = (.70, .80, .86); refl[:] = .55
        else: a = a * 2.2; refl[:] = 0.
    elif kind == 'ice':
        a = base[None] * (.9 + .15 * vnoise2(x * 4, z * 4, 60))[:, None]
        crack = np.abs(vnoise2(x * 3, z * 3, 61) - .5) < .015; a[crack] *= .6; refl[:] = .45
    elif kind in ('stone', 'cobble'):
        s = .5 if kind == 'stone' else .28
        cx, cz = np.floor(x / s + np.floor(z / s) % 2 * .5), np.floor(z / s)
        fx, fz = (x / s + np.floor(z / s) % 2 * .5) % 1, (z / s) % 1
        joint = (fx < .07) | (fz < .07)
        a = base[None] * (.8 + .35 * h2(cx, cz, 62))[:, None]; a[joint] *= .45; refl[:] = .2 if wet else .04
    elif kind == 'road':
        a = base[None] * (.85 + .25 * vnoise2(x * 20, z * 20, 63))[:, None]
        line = (np.abs(x) < .06) & ((z % 3) < 1.6); a[line] = (.85, .80, .55)
        refl[:] = .3 if wet else .05
    elif kind == 'marble':
        vein = np.abs(np.sin(x * 3 + fbm(x * .8, z * .8, 64, 4) * 7)) < .06
        a = base[None] * (.95 + .05 * vnoise2(x * 5, z * 5, 65))[:, None]; a[vein] *= .7; refl[:] = .12
    elif kind == 'leaves':
        k = h2(np.floor(x * 9), np.floor(z * 9), 66)
        a = np.where((k > .5)[:, None], np.array([.46, .24, .06], np.float32)[None], np.array([.36, .16, .06], np.float32)[None]) * (.8 + .3 * vnoise2(x * 4, z * 4, 67))[:, None]
    elif kind == 'plank_dock':
        plank = np.floor(x / .25); seam = (x / .25) % 1 < .06
        a = base[None] * (.75 + .35 * h2(plank, np.floor(z / 2), 68))[:, None]; a[seam] *= .4
    else:
        a = base[None] * (.8 + .3 * fbm(x * 1.5, z * 1.5, 69, 3))[:, None]
        if kind == 'moss': a *= np.where((vnoise2(x * 5, z * 5, 70) > .5)[:, None], 1.15, .85)
    return a.astype(np.float32), refl

def zone_mask(z_, x, zz):
    if 'rect' in z_:
        x0, z0, x1, z1 = z_['rect']; return (x >= min(x0, x1)) & (x <= max(x0, x1)) & (zz >= min(z0, z1)) & (zz <= max(z0, z1))
    if 'circle' in z_:
        cx, cz, r = z_['circle']; wob = .35 * (vnoise2(x * 1.3, zz * 1.3, 71) - .5) * r ** .5
        return (x - cx) ** 2 + (zz - cz) ** 2 < (r + wob) ** 2
    if 'path' in z_:                         # polyline [[x, z], ...] with a width
        pts = np.asarray(z_['path'], np.float32); w = float(z_.get('width', 1.2)) / 2; m = np.zeros(len(x), bool)
        for (ax, az), (bx, bz) in zip(pts[:-1], pts[1:]):
            dx, dz = bx - ax, bz - az; L2 = dx * dx + dz * dz + 1e-9
            t = np.clip(((x - ax) * dx + (zz - az) * dz) / L2, 0, 1); px, pz = ax + t * dx, az + t * dz
            m |= (x - px) ** 2 + (zz - pz) ** 2 < (w * (1 + .2 * (vnoise2(x * 2, zz * 2, 72) - .5))) ** 2
        return m
    return np.zeros(len(x), bool)

# ================================================================== weather (drawn in the low-res raster, so it is pixel art)
WEATHERS = ('rain', 'storm', 'snow', 'blizzard', 'leaves', 'petals', 'fireflies', 'embers', 'dust', 'bubbles', 'sparkles', 'ash')

def weather(out, kind, g, amount=1.):
    if not kind or kind == 'none': return out
    H, W = out.shape[:2]; o = out.astype(np.float32); rng = np.random.default_rng(1234)
    def particles(n, speed, sway=0., size=1, col=(255, 255, 255), alpha=.8, life=None, rise=False, streak=0, blink=False, seed=0):
        r = np.random.default_rng(seed); px = r.random(n) * W; py = r.random(n) * H; sp = speed * (.6 + .8 * r.random(n)); ph = r.random(n) * 6.28
        yy = (py + (-1 if rise else 1) * g * sp) % H; xx = (px + sway * np.sin(g * 1.3 + ph) * 6 + (g * sp * .25 if streak else 0)) % W
        for k in range(n):
            a_ = alpha * (.5 + .5 * math.sin(g * 4 + ph[k])) if blink else alpha
            x0, y0 = int(xx[k]), int(yy[k])
            for s_ in range(max(1, streak)):
                yv, xv = y0 - s_, x0 - (s_ // 2 if streak else 0)
                for dy_ in range(size):
                    for dx_ in range(size):
                        Y, X = yv + dy_, xv + dx_
                        if 0 <= Y < H and 0 <= X < W: o[Y, X] = o[Y, X] * (1 - a_) + np.array(col, np.float32) * a_
    n = lambda k: int(k * amount * W * H / (384 * 216))
    if kind in ('rain', 'storm'):
        o *= .86; particles(n(260 if kind == 'rain' else 420), 340, 0, 1, (170, 185, 210), .55, streak=4, seed=1)
        if kind == 'storm':
            k = int(g * 3); r = (k * 2654435761) % 1000 / 1000.
            if r > .9 and (g * 3) % 1 < .25: o = o * .4 + 255 * .6
    elif kind in ('snow', 'blizzard'):
        particles(n(90), 22, 1.2, 1, (240, 244, 255), .85, seed=2); particles(n(40), 40, 1.6, 2, (250, 252, 255), .9, seed=3)
        if kind == 'blizzard': o = o * .8 + 200 * .2; particles(n(220), 90, 4, 1, (235, 240, 250), .7, seed=4)
    elif kind == 'leaves': particles(n(40), 28, 3, 2, (200, 100, 30), .9, seed=5); particles(n(25), 24, 3, 2, (230, 170, 40), .9, seed=6)
    elif kind == 'petals': particles(n(45), 20, 3, 2, (250, 170, 200), .9, seed=7)
    elif kind == 'fireflies': particles(n(30), 3, 2.5, 1, (220, 255, 120), 1., blink=True, rise=True, seed=8)
    elif kind == 'embers': particles(n(45), 30, 1.5, 1, (255, 140, 40), .95, blink=True, rise=True, seed=9)
    elif kind == 'ash': particles(n(70), 12, 2, 1, (150, 146, 140), .7, seed=10)
    elif kind == 'dust': particles(n(60), 6, 1.5, 1, (220, 200, 160), .35, rise=True, seed=11)
    elif kind == 'bubbles': particles(n(40), 25, .8, 2, (190, 230, 255), .5, rise=True, seed=12)
    elif kind == 'sparkles': particles(n(40), 4, 1, 1, (255, 250, 200), 1., blink=True, seed=13)
    return np.clip(o, 0, 255).astype(np.uint8)

# ================================================================== props
def _txt(lines, size=(64, 24), fg=(255, 255, 255), bg=(0, 0, 0, 0), fs=8):
    im = Image.new('RGBA', size, bg); d = ImageDraw.Draw(im); d.fontmode = '1'; f = ImageFont.truetype(FONT_PIXEL, fs); y = 3
    for l in lines:
        w = d.textlength(l, font=f); d.text(((size[0] - w) / 2, y), l, font=f, fill=tuple(fg) + (255,)); y += fs + 3
    return np.array(im)

def _stack(levels, col, trunk=(60, 44, 30), th=.25, mat=M_FABRIC):
    """trunk + stacked shrinking blocks (pine-like)"""
    out = [C((0, levels[0][0] / 2, 0), (th, levels[0][0], th), trunk, mat=M_WOODV)]
    for y, w, h in levels[1:]: out.append(C((0, y, 0), (w, h, w), col, mat=mat))
    return out

def P_pine(p, c):
    s = float(p.get('size', 1.)); g = c or (28, 62, 38)
    return [C((0, .5 * s, 0), (.25 * s, 1.0 * s, .25 * s), (60, 44, 30), mat=M_WOODV)] + [C((0, (1.0 + .6 * i) * s, 0), ((1.7 - .45 * i) * s, .7 * s, (1.7 - .45 * i) * s), g, mat=M_FABRIC) for i in range(4)]
def P_snow_pine(p, c):
    b = P_pine(p, c); s = float(p.get('size', 1.))
    return b + [C((0, (1.36 + .6 * i) * s, 0), ((1.5 - .45 * i) * s, .06 * s, (1.5 - .45 * i) * s), (236, 240, 248)) for i in range(4)]
def P_tree_round(p, c, canopy=(36, 84, 40)):
    s = float(p.get('size', 1.)); g = c or canopy
    return [C((0, 1.1 * s, 0), (.32 * s, 2.2 * s, .32 * s), (74, 54, 36), mat=M_WOODV), C((0, 2.7 * s, 0), (1.9 * s, 1.3 * s, 1.9 * s), g, mat=M_FABRIC),
            C((.3 * s, 3.45 * s, -.2 * s), (1.2 * s, .6 * s, 1.2 * s), tuple(int(v * 1.1) for v in g), mat=M_FABRIC), C((-.6 * s, 2.4 * s, .4 * s), (.8 * s, .7 * s, .8 * s), g, mat=M_FABRIC)]
def P_palm(p, c):
    s = float(p.get('size', 1.)); out = []
    for i in range(7): out.append(C((.06 * i * i * s * .1, (.35 + .5 * i) * s, 0), (.22 * s, .52 * s, .22 * s), (120, 90, 56), mat=M_WOODV))
    top = (.06 * 36 * s * .1, 3.6 * s, 0)
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (.7, .7), (-.7, -.7), (.7, -.7), (-.7, .7)):
        for k in range(1, 5): out.append(C((top[0] + dx * .32 * k * s, top[1] - .09 * k * k * s, top[2] + dz * .32 * k * s), (.42 * s, .14 * s, .42 * s), c or (50, 120, 50), mat=M_FABRIC))
    out.append(C(top, (.3 * s, .25 * s, .3 * s), (90, 70, 40)))
    return out
def P_bush(p, c):
    g = c or (40, 90, 44); s = float(p.get('size', 1.))
    return [C((0, .35 * s, 0), (1.0 * s, .7 * s, .9 * s), g, mat=M_FABRIC), C((.3 * s, .55 * s, .15 * s), (.6 * s, .5 * s, .6 * s), tuple(int(v * 1.12) for v in g), mat=M_FABRIC)]
def P_rock(p, c):
    s = float(p.get('size', 1.)); r = c or (110, 108, 104)
    return [C((0, .22 * s, 0), (.8 * s, .44 * s, .6 * s), r, mat=M_PLASTER), C((.15 * s, .5 * s, -.05 * s), (.45 * s, .25 * s, .4 * s), tuple(int(v * .9) for v in r), mat=M_PLASTER)]
def P_boulder(p, c):
    s = float(p.get('size', 1.)); r = c or (100, 98, 94)
    return [C((0, .6 * s, 0), (1.8 * s, 1.2 * s, 1.5 * s), r, mat=M_PLASTER), C((-.3 * s, 1.35 * s, .1 * s), (1.0 * s, .5 * s, .9 * s), tuple(int(v * .92) for v in r), mat=M_PLASTER)]
def P_flowers(p, c):
    out = []; cols = [c] if c else [(230, 60, 90), (250, 210, 60), (240, 240, 240), (150, 90, 220), (255, 130, 40)]
    for i in range(9):
        a = i * 2.4; r = .12 + .05 * i; x, z = r * math.cos(a), r * math.sin(a)
        out += [C((x, .12, z), (.02, .24, .02), (60, 140, 60)), C((x, .26, z), (.07, .06, .07), cols[i % len(cols)])]
    return out
def P_tall_grass(p, c):
    return [C(((i % 3 - 1) * .1, .2 + .05 * (i % 2), (i // 3 - 1) * .1), (.025, .4 + .1 * (i % 3), .025), c or (70, 120, 50)) for i in range(9)]
def P_log(p, c): return [C((0, .18, 0), (1.6, .36, .36), c or (90, 64, 40), mat=M_WOODV), C((.81, .18, 0), (.02, .3, .3), (150, 120, 80))]
def P_stump(p, c): return [C((0, .2, 0), (.5, .4, .5), c or (90, 64, 40), mat=M_WOODV), C((0, .405, 0), (.42, .01, .42), (160, 130, 90))]
def P_mushroom(p, c):
    s = float(p.get('size', 1.))
    return [C((0, .12 * s, 0), (.08 * s, .24 * s, .08 * s), (230, 222, 200)), C((0, .27 * s, 0), (.3 * s, .1 * s, .3 * s), c or (200, 40, 40)),
            C((.06 * s, .325 * s, .05 * s), (.04 * s, .01 * s, .04 * s), (250, 250, 250)), C((-.07 * s, .325 * s, -.03 * s), (.04 * s, .01 * s, .04 * s), (250, 250, 250))]
def P_cactus(p, c):
    g = c or (60, 130, 70)
    return [C((0, .9, 0), (.32, 1.8, .32), g), C((.36, .9, 0), (.4, .18, .18), g), C((.5, 1.25, 0), (.18, .6, .18), g), C((-.3, 1.2, 0), (.3, .16, .16), g), C((-.42, 1.45, 0), (.16, .4, .16), g)]
def P_dead_tree(p, c):
    w = c or (50, 42, 36)
    return [C((0, 1.4, 0), (.28, 2.8, .28), w, mat=M_WOODV), C((.35, 2.3, 0), (.7, .1, .1), w), C((.7, 2.6, 0), (.1, .6, .1), w),
            C((-.3, 1.9, .1), (.6, .09, .09), w), C((-.6, 2.15, .1), (.09, .5, .09), w), C((.05, 2.95, -.2), (.08, .5, .4), w)]
def P_birch(p, c):
    return [C((0, 1.4, 0), (.22, 2.8, .22), (226, 222, 210)), C((0, 1.0, .111), (.12, .05, .01), (40, 40, 40)), C((0, 1.9, .111), (.08, .04, .01), (40, 40, 40)),
            C((0, 3.1, 0), (1.4, 1.2, 1.4), c or (110, 160, 60), mat=M_FABRIC)]
def P_hedge(p, c):
    L = float(p.get('length', 3.)); return [B((-L / 2, 0, -.35), (L, 1.1, .7), c or (36, 80, 40), mat=M_FABRIC)]

def P_house(p, c):
    w = c or (196, 170, 140); roof = tuple(p.get('roof', (150, 60, 50)))
    out = [B((-2.5, 0, -2.0), (5.0, 3.0, 4.0), w, mat=M_PLASTER)]
    for i in range(5): out.append(B((-2.7 + i * .0, 3.0 + i * .35, -2.2 + i * .42), (5.4, .35, 4.4 - i * .84), roof, mat=M_WOODV))
    out += [B((-.45, 0, -2.03), (.9, 2.0, .04), (110, 70, 44), mat=M_DOOR), C((.3, 1.0, -2.06), (.05, .05, .03), (220, 190, 90))]
    for x in (-1.6, 1.6):
        night = p.get('night', False)
        out += [B((x - .45, 1.2, -2.03), (.9, .8, .03), (240, 200, 110) if night else (140, 170, 200), emis=1.2 if night else 0., refl=0 if night else .3),
                B((x - .5, 1.15, -2.02), (1.0, .9, .02), (240, 240, 236))]
    out.append(B((1.2, 3.5, .2), (.5, 1.2, .5), (120, 80, 70), mat=M_PLASTER))
    return out
def P_shop(p, c):
    w = c or (170, 150, 130); aw = tuple(p.get('awning', (190, 50, 50)))
    sign = str(p.get('sign', 'BOUTIQUE'))[:12]
    out = [B((-2.5, 0, -1.5), (5.0, 3.6, 3.0), w, mat=M_PLASTER), B((-2.0, .2, -1.53), (2.6, 2.0, .03), (150, 190, 210), refl=.4, emis=.2),
           B((1.0, 0, -1.53), (.9, 2.1, .03), (90, 60, 40), mat=M_DOOR), B((-2.6, 2.4, -2.3), (5.2, .1, .8), aw, mat=M_FABRIC),
           B((-2.0, 2.75, -1.54), (4.0, .6, .02), (30, 30, 34), tex={'-z': _txt([sign], (96, 16), (250, 230, 160))}, texemis=1.2)]
    for i in range(6): out.append(B((-2.6 + i * .866, 2.3, -2.3), (.43, .1, .8), (240, 240, 236), mat=M_FABRIC))
    return out
def P_tent(p, c):
    t = c or (60, 120, 80); out = []
    for i in range(6): out.append(B((-1.0 + i * .16, .0, -1.2), (2.0 - i * .32, .25, 2.4), t if i % 2 == 0 else tuple(int(v * .85) for v in t), mat=M_FABRIC))
    for i in range(6): out[i].lo[1] = i * .25; out[i].hi[1] = i * .25 + .25
    out.append(B((-.3, 0, -1.22), (.6, .9, .02), (20, 24, 20)))
    return out
def P_traffic_light(p, c):
    st = p.get('state', 'red'); on = lambda k: 2.5 if st == k else .1
    return [C((0, 1.6, 0), (.12, 3.2, .12), (40, 42, 46), mat=M_METAL), C((0, 3.1, -.1), (.3, .9, .25), (30, 30, 30)),
            C((0, 3.4, -.23), (.16, .16, .02), (255, 40, 40), emis=on('red')), C((0, 3.1, -.23), (.16, .16, .02), (255, 200, 40), emis=on('orange')),
            C((0, 2.8, -.23), (.16, .16, .02), (60, 255, 100), emis=on('green'))]
def P_bus_stop(p, c):
    return [B((-1.5, 0, -.1), (.08, 2.4, .08), (60, 60, 64), mat=M_METAL), B((1.42, 0, -.1), (.08, 2.4, .08), (60, 60, 64), mat=M_METAL),
            B((-1.6, 2.4, -.7), (3.2, .08, 1.0), c or (50, 90, 150), mat=M_METAL), B((-1.5, .3, .25), (3.0, 1.9, .03), (160, 190, 210), refl=.35),
            B((-1.2, .45, -.3), (2.4, .06, .4), (120, 90, 60), mat=M_WOODV), B((1.0, 1.2, .26), (.5, .8, .02), (240, 240, 230), tex={'-z': _txt(['BUS', '42'], (24, 24), (30, 30, 30))})]
def P_mailbox(p, c): return [C((0, .5, 0), (.1, 1.0, .1), (60, 60, 60)), C((0, 1.15, 0), (.35, .3, .5), c or (40, 70, 160), mat=M_METAL), C((.19, 1.3, .1), (.02, .2, .05), (220, 40, 40))]
def P_trash_can(p, c): return [C((0, .45, 0), (.55, .9, .55), c or (60, 90, 60), mat=M_METAL), C((0, .92, 0), (.6, .06, .6), tuple(int(v * .8) for v in (c or (60, 90, 60))), mat=M_METAL)]
def P_hydrant(p, c): return [C((0, .3, 0), (.24, .6, .24), c or (200, 40, 40), mat=M_METAL), C((0, .62, 0), (.18, .08, .18), (200, 40, 40)), C((0, .42, -.15), (.1, .1, .08), (180, 180, 180), mat=M_METAL)]
def P_signpost(p, c):
    txt = str(p.get('text', 'VILLAGE'))[:10]
    return [C((0, 1.0, 0), (.1, 2.0, .1), (110, 80, 50), mat=M_WOODV), B((-.6, 1.5, -.08), (1.2, .4, .05), c or (150, 110, 70), mat=M_WOODV, tex={'-z': _txt([txt], (64, 20), (30, 20, 10))})]
def P_sign(p, c):
    txt = [str(t)[:12] for t in (p.get('text', 'BIENVENUE') if isinstance(p.get('text', ''), list) else [p.get('text', 'BIENVENUE')])][:3]
    return [B((-.8, 1.8, -.03), (1.6, .6, .03), c or (30, 60, 40), tex={'-z': _txt(txt, (96, 36), (250, 240, 200))}, texemis=float(p.get('glow', .4)))]
def P_fountain(p, c):
    return [B((-1.3, 0, -1.3), (2.6, .5, 2.6), c or (170, 168, 160), mat=M_PLASTER), B((-1.15, .3, -1.15), (2.3, .21, 2.3), (40, 110, 150), refl=.6),
            C((0, .9, 0), (.3, 1.0, .3), (170, 168, 160), mat=M_PLASTER), C((0, 1.45, 0), (.9, .12, .9), (170, 168, 160), mat=M_PLASTER), C((0, 1.6, 0), (.12, .3, .12), (150, 200, 230), emis=.5)]
def P_phone_booth(p, c): return [B((-.5, 0, -.5), (1.0, 2.4, 1.0), c or (180, 30, 30), mat=M_METAL), B((-.4, .3, -.52), (.8, 1.8, .02), (170, 200, 220), refl=.3, emis=.3)]
def P_bicycle(p, c):
    f = c or (40, 120, 200)
    return [C((0, .35, -.5), (.06, .7, .7), (30, 30, 30)), C((0, .35, .5), (.06, .7, .7), (30, 30, 30)), C((0, .6, 0), (.05, .06, .9), f, mat=M_METAL),
            C((0, .75, .3), (.05, .35, .05), f), C((0, .95, .3), (.25, .04, .06), (40, 40, 40)), C((0, .82, -.3), (.08, .04, .22), (30, 30, 30)), C((0, .5, -.25), (.05, .5, .05), f)]
def P_bus(p, c):
    col = c or (230, 180, 40)
    out = [B((-1.25, .35, -5.5), (2.5, 2.6, 11.0), col, mat=M_METAL), B((-1.27, 1.6, -5.0), (.02, .9, 9.6), (40, 60, 80), refl=.4), B((1.25, 1.6, -5.0), (.02, .9, 9.6), (40, 60, 80), refl=.4),
           B((-1.1, 1.3, -5.52), (2.2, 1.3, .02), (40, 60, 80), refl=.4)]
    return out + [C((x, .4, z), (.3, .8, .8), (20, 20, 20)) for x in (-1.2, 1.2) for z in (-3.8, 3.8)]
def P_truck(p, c):
    col = c or (200, 200, 205)
    return [B((-1.2, .5, -1.0), (2.4, 2.8, 6.0), col, mat=M_METAL), B((-1.2, .5, -3.4), (2.4, 2.0, 2.4), (180, 40, 40), mat=M_METAL), B((-1.1, 1.6, -3.42), (2.2, .8, .02), (40, 60, 80), refl=.4)] + \
           [C((x, .45, z), (.3, .9, .9), (20, 20, 20)) for x in (-1.2, 1.2) for z in (-2.6, 1.0, 3.8)]
def P_boat(p, c):
    h = c or (150, 90, 50)
    return [B((-.8, .0, -1.8), (1.6, .5, 3.6), h, mat=M_WOODV), B((-.6, .0, -2.3), (1.2, .4, .5), h, mat=M_WOODV), B((-.7, .35, -.2), (1.4, .06, .35), (120, 80, 50), mat=M_WOODV),
            B((-.68, .25, -1.7), (1.36, .02, 3.4), (90, 60, 36), mat=M_WOODV)]
def P_sailboat(p, c):
    return P_boat(p, c) + [C((0, 2.2, 0), (.08, 4.0, .08), (120, 90, 60)), B((.05, .8, -1.2), (.02, 3.0, 1.15), (240, 240, 236), mat=M_FABRIC)]
def P_dock(p, c):
    L = float(p.get('length', 6.)); return [B((-1., .3, 0), (2., .1, L), c or (110, 80, 50), mat=M_WOODV)] + [C((x, .15, z), (.15, .5, .15), (80, 60, 40)) for x in (-.9, .9) for z in np.arange(.3, L, 1.5)]
def P_bridge(p, c):
    L = float(p.get('length', 6.)); w = c or (120, 86, 56)
    return [B((-1.2, .5, -L / 2), (2.4, .12, L), w, mat=M_WOODV), B((-1.25, .62, -L / 2), (.08, .8, L), w, mat=M_WOODV), B((1.17, .62, -L / 2), (.08, .8, L), w, mat=M_WOODV)] + \
           [C((x, .25, z), (.18, .5, .18), (90, 64, 40)) for x in (-1.1, 1.1) for z in (-L / 2 + .2, L / 2 - .2)]
def P_well(p, c):
    s = c or (130, 126, 120)
    return [B((-.7, 0, -.7), (1.4, .8, 1.4), s, mat=M_PLASTER), B((-.55, .7, -.55), (1.1, .12, 1.1), (20, 40, 60), refl=.4), C((-.6, 1.4, 0), (.1, 1.3, .1), (100, 70, 40)), C((.6, 1.4, 0), (.1, 1.3, .1), (100, 70, 40)),
            B((-.9, 2.0, -.8), (1.8, .1, 1.6), (130, 60, 40), mat=M_WOODV), C((0, 1.6, 0), (1.2, .08, .08), (100, 70, 40)), C((0, 1.25, 0), (.18, .2, .18), (110, 80, 50))]
def P_campfire(p, c):
    return [C((0, .08, 0), (.9, .12, .2), (90, 60, 36), mat=M_WOODV), C((0, .08, 0), (.2, .12, .9), (80, 56, 34), mat=M_WOODV),
            C((0, .3, 0), (.3, .35, .3), (255, 150, 40), emis=3., cast=False), C((.05, .52, -.02), (.15, .2, .15), (255, 220, 90), emis=3.5, cast=False)] + \
           [C((math.cos(a) * .55, .08, math.sin(a) * .55), (.18, .14, .18), (100, 98, 94)) for a in np.linspace(0, 6.28, 9)[:-1]]
def P_lantern(p, c): return [C((0, 1.1, 0), (.08, 2.2, .08), (40, 40, 44), mat=M_METAL), C((0, 2.3, 0), (.3, .4, .3), (255, 200, 110), emis=2.2), C((0, 2.55, 0), (.36, .08, .36), (40, 40, 44))]
def P_gravestone(p, c):
    s = c or (120, 120, 118); txt = str(p.get('text', 'R.I.P'))[:8]
    return [B((-.35, 0, -.08), (.7, .9, .16), s, mat=M_PLASTER, tex={'-z': _txt([txt], (32, 40), (50, 50, 50))}), C((0, .92, 0), (.5, .1, .16), s, mat=M_PLASTER), B((-.45, 0, -.7), (.9, .06, .6), (70, 60, 50))]
def P_cross(p, c): return [C((0, .7, 0), (.12, 1.4, .12), c or (110, 100, 90), mat=M_WOODV), C((0, 1.1, 0), (.6, .12, .12), c or (110, 100, 90), mat=M_WOODV)]
def P_statue(p, c):
    s = c or (180, 178, 170)
    return [B((-.6, 0, -.6), (1.2, 1.0, 1.2), (150, 148, 140), mat=M_PLASTER), C((0, 1.5, 0), (.5, 1.0, .3), s, mat=M_PLASTER), C((0, 2.2, 0), (.34, .34, .34), s, mat=M_PLASTER),
            C((.32, 1.75, 0), (.13, .6, .15), s), C((-.32, 1.55, 0), (.13, .6, .15), s)]
def P_market_stall(p, c):
    aw = c or (200, 60, 60)
    out = [B((-1.2, .8, -.6), (2.4, .1, 1.2), (130, 96, 60), mat=M_WOODV)] + [B((x, 0, z), (.08, 2.3, .08), (100, 70, 44)) for x in (-1.2, 1.12) for z in (-.6, .52)]
    out += [B((-1.3, 2.3, -.8), (2.6, .08, 1.6), aw, mat=M_FABRIC)]
    for i, col in enumerate([(220, 60, 40), (240, 180, 40), (90, 170, 60), (240, 120, 30), (150, 60, 140)]): out.append(C((-.9 + i * .45, .95, 0), (.3, .2, .5), col))
    return out
def P_swing(p, c):
    f = c or (180, 40, 40)
    return [C((-1.2, 1.25, 0), (.1, 2.5, .1), f, mat=M_METAL), C((1.2, 1.25, 0), (.1, 2.5, .1), f, mat=M_METAL), C((0, 2.5, 0), (2.5, .1, .1), f, mat=M_METAL),
            C((-.25, 1.5, 0), (.02, 2.0, .02), (60, 60, 60)), C((.25, 1.5, 0), (.02, 2.0, .02), (60, 60, 60)), C((0, .5, 0), (.6, .05, .25), (100, 70, 40))]
def P_slide(p, c):
    f = c or (240, 180, 40); out = [C((-.4, .9, -1.0), (.08, 1.8, .08), (60, 60, 64)), C((.4, .9, -1.0), (.08, 1.8, .08), (60, 60, 64)), B((-.45, 1.75, -1.3), (.9, .08, .6), f)]
    for i in range(8): out.append(B((-.4, 1.75 - i * .22, -.7 + i * .3), (.8, .06, .32), f, mat=M_METAL))
    return out
def P_beach_umbrella(p, c):
    col = c or (230, 70, 70); out = [C((0, 1.1, 0), (.05, 2.2, .05), (230, 230, 230))]
    for i in range(4): out.append(C((0, 2.2 - i * .07, 0), (1.9 - i * .4, .08, 1.9 - i * .4), col if i % 2 == 0 else (245, 245, 240), mat=M_FABRIC))
    return out
def P_beach_towel(p, c): return [B((-.45, 0, -.9), (.9, .015, 1.8), c or (60, 150, 220), mat=M_FABRIC, cast=False), B((-.45, .002, -.3), (.9, .015, .25), (250, 250, 250), mat=M_FABRIC, cast=False)]
def P_sandcastle(p, c):
    s = c or (210, 180, 120)
    return [C((0, .15, 0), (.8, .3, .8), s), C((-.3, .45, -.3), (.18, .3, .18), s), C((.3, .45, -.3), (.18, .3, .18), s), C((-.3, .45, .3), (.18, .3, .18), s), C((.3, .45, .3), (.18, .3, .18), s),
            C((0, .5, 0), (.28, .4, .28), s), C((0, .78, 0), (.02, .2, .02), (90, 70, 40)), C((.05, .84, 0), (.1, .06, .01), (220, 40, 40))]
def P_barrel(p, c): return [C((0, .45, 0), (.6, .9, .6), c or (120, 80, 46), mat=M_WOODV), C((0, .2, 0), (.62, .05, .62), (60, 60, 60)), C((0, .7, 0), (.62, .05, .62), (60, 60, 60))]
def P_hay_bale(p, c): return [C((0, .4, 0), (1.2, .8, .8), c or (200, 170, 80), mat=M_FABRIC)]
def P_scarecrow(p, c):
    return [C((0, 1.0, 0), (.08, 2.0, .08), (100, 70, 40)), C((0, 1.55, 0), (1.3, .08, .08), (100, 70, 40)), C((0, 1.35, 0), (.5, .6, .25), c or (90, 120, 160), mat=M_FABRIC),
            C((0, 1.85, 0), (.32, .32, .3), (220, 190, 120)), C((0, 2.06, 0), (.5, .04, .5), (150, 110, 50)), C((0, 2.15, 0), (.3, .16, .3), (150, 110, 50))]
def P_stairs(p, c):
    n = int(p.get('steps', 8)); h = float(p.get('height', 2.4)); d = float(p.get('depth', 3.2)); w = float(p.get('width', 1.4))
    return [B((-w / 2, 0, -d / 2 + i * d / n), (w, h * (i + 1) / n, d / n), c or (150, 146, 138), mat=M_PLASTER) for i in range(n)]
def P_ladder(p, c):
    h = float(p.get('height', 2.5)); w = c or (140, 100, 60)
    return [C((-.22, h / 2, 0), (.06, h, .06), w), C((.22, h / 2, 0), (.06, h, .06), w)] + [C((0, .3 + i * .3, 0), (.44, .04, .04), w) for i in range(int(h / .3) - 1)]
def P_arch(p, c):
    s = c or (150, 140, 128)
    return [B((-1.4, 0, -.3), (.5, 3.0, .6), s, mat=M_PLASTER), B((.9, 0, -.3), (.5, 3.0, .6), s, mat=M_PLASTER), B((-1.4, 3.0, -.3), (2.8, .5, .6), s, mat=M_PLASTER),
            B((-.9, 2.75, -.3), (.3, .25, .6), s, mat=M_PLASTER), B((.6, 2.75, -.3), (.3, .25, .6), s, mat=M_PLASTER)]
def P_castle_wall(p, c):
    L = float(p.get('length', 6.)); h = float(p.get('height', 4.)); s = c or (130, 126, 118)
    return [B((-L / 2, 0, -.5), (L, h, 1.0), s, mat=M_PLASTER)] + [B((-L / 2 + i * .8, h, -.5), (.45, .45, 1.0), s, mat=M_PLASTER) for i in range(int(L / .8) + 1) if -L / 2 + i * .8 + .45 <= L / 2 + 1e-3]
def P_tower(p, c):
    h = float(p.get('height', 7.)); s = c or (128, 124, 116)
    out = [B((-1.4, 0, -1.4), (2.8, h, 2.8), s, mat=M_PLASTER), B((-1.6, h, -1.6), (3.2, .3, 3.2), s, mat=M_PLASTER)]
    for i in range(4): out += [B((-1.6 + i * .9, h + .3, -1.6), (.5, .5, .3), s, mat=M_PLASTER), B((-1.6 + i * .9, h + .3, 1.3), (.5, .5, .3), s, mat=M_PLASTER)]
    out += [B((-.25, h * .6, -1.42), (.5, .8, .02), (20, 20, 24)), B((-.25, h * .3, -1.42), (.5, .8, .02), (255, 190, 90) if p.get('lit') else (20, 20, 24), emis=1.5 if p.get('lit') else 0)]
    if p.get('roof', True):
        for i in range(5): out.append(C((0, h + .55 + i * .45, 0), (2.4 - i * .5, .45, 2.4 - i * .5), (60, 50, 90), mat=M_WOODV))
    return out
def P_gate(p, c):
    s = c or (128, 124, 116)
    return [B((-2.5, 0, -.6), (1.4, 5.0, 1.2), s, mat=M_PLASTER), B((1.1, 0, -.6), (1.4, 5.0, 1.2), s, mat=M_PLASTER), B((-2.5, 3.6, -.6), (5.0, 1.4, 1.2), s, mat=M_PLASTER),
            B((-1.1, 0, -.05), (2.2, 3.6, .1), (90, 60, 36) if not p.get('open') else (20, 20, 20), mat=M_DOOR)]
def P_flag(p, c):
    return [C((0, 2.0, 0), (.06, 4.0, .06), (200, 200, 200), mat=M_METAL), B((.03, 3.2, -.01), (1.2, .75, .02), c or (40, 80, 200), mat=M_FABRIC)]
def P_throne(p, c):
    g = (210, 170, 60); r = c or (150, 30, 40)
    return [B((-.5, 0, -.45), (1.0, .55, .9), g, emis=.15), B((-.45, .55, -.4), (.9, .08, .8), r, mat=M_FABRIC), B((-.5, .55, .35), (1.0, 1.7, .12), g, emis=.15),
            B((-.4, .7, .33), (.8, 1.3, .02), r, mat=M_FABRIC), B((-.55, .55, -.45), (.12, .4, .8), g), B((.43, .55, -.45), (.12, .4, .8), g)]
def P_chest(p, c):
    w = c or (120, 76, 40); out = [B((-.45, 0, -.3), (.9, .5, .6), w, mat=M_WOODV), B((-.47, .1, -.32), (.94, .06, .64), (200, 170, 60), mat=M_METAL), C((0, .38, -.31), (.1, .12, .02), (220, 190, 70))]
    if p.get('open'): out += [B((-.45, .5, .25), (.9, .5, .08), w, mat=M_WOODV), B((-.4, .42, -.25), (.8, .1, .5), (255, 210, 60), emis=1.2)]
    else: out.append(B((-.45, .5, -.3), (.9, .15, .6), w, mat=M_WOODV))
    return out
def P_torch_wall(p, c): return [C((0, 1.6, 0), (.06, .4, .06), (80, 60, 40)), C((0, 1.85, 0), (.12, .14, .12), (255, 150, 40), emis=3., cast=False)]
def P_cauldron(p, c): return [C((0, .35, 0), (.8, .6, .8), (30, 30, 34), mat=M_METAL), C((0, .66, 0), (.66, .02, .66), c or (90, 220, 90), emis=1.5, cast=False)] + [C((x, .05, z), (.08, .1, .08), (30, 30, 34)) for x in (-.3, .3) for z in (-.3, .3)]
def P_bookshelf(p, c):
    out = [B((-.6, 0, -.2), (1.2, 2.0, .4), c or (100, 70, 44), mat=M_WOODV)]
    cols = [(150, 40, 40), (40, 80, 140), (200, 170, 60), (60, 120, 70), (120, 60, 130), (210, 120, 40)]
    for r_ in range(4):
        x = -.55
        for k in range(9):
            w = .07 + .03 * ((k * 7 + r_ * 3) % 3); hgt = .3 + .06 * ((k + r_) % 3)
            if x + w > .55: break
            out.append(B((x, .1 + r_ * .48, -.22), (w, hgt, .3), cols[(k + r_ * 2) % 6])); x += w + .01
    return out
def P_piano(p, c):
    b = c or (20, 18, 20)
    return [B((-.75, 0, -.3), (1.5, 1.25, .6), b, refl=.2), B((-.72, .72, -.55), (1.44, .06, .28), (240, 240, 236)), B((-.72, .78, -.5), (1.44, .02, .1), (20, 18, 20)),
            B((-.5, 0, -1.0), (1.0, .45, .4), b)]
def P_computer(p, c):
    return [B((-.7, .74, -.35), (1.4, .05, .7), c or (120, 90, 60), mat=M_WOODV)] + [B((x, 0, z), (.05, .74, .05), (60, 44, 30)) for x in (-.65, .6) for z in (-.3, .25)] + \
           [B((-.3, .8, .05), (.6, .4, .04), (20, 20, 24)), B((-.27, .83, .03), (.54, .34, .01), (90, 160, 230), emis=1.4), C((0, .78, .1), (.06, .08, .06), (30, 30, 30)), B((-.25, .79, -.25), (.5, .02, .16), (40, 40, 44))]
def P_laptop(p, c): return [B((-.18, .0, -.12), (.36, .02, .24), c or (170, 172, 178), mat=M_METAL), B((-.18, .02, .1), (.36, .23, .02), c or (170, 172, 178), mat=M_METAL), B((-.16, .04, .095), (.32, .19, .005), (120, 180, 240), emis=1.3)]
def P_stove(p, c): return [B((-.35, 0, -.32), (.7, .9, .64), c or (220, 220, 216), mat=M_METAL), B((-.3, .2, -.33), (.6, .45, .01), (30, 30, 30), refl=.3)] + [C((x, .91, z), (.18, .01, .18), (40, 40, 40)) for x in (-.16, .16) for z in (-.15, .15)]
def P_sink(p, c): return [B((-.5, 0, -.3), (1.0, .85, .6), c or (200, 196, 190), mat=M_WOODV), B((-.3, .8, -.2), (.6, .06, .4), (190, 196, 200), mat=M_METAL, refl=.3), C((0, 1.0, .15), (.04, .2, .04), (200, 200, 205), mat=M_METAL)]
def P_toilet(p, c): return [C((0, .2, 0), (.38, .4, .5), (240, 240, 236)), C((0, .42, -.02), (.4, .04, .5), (240, 240, 236)), C((0, .65, .24), (.38, .5, .16), (240, 240, 236))]
def P_bathtub(p, c): return [B((-.8, 0, -.4), (1.6, .55, .8), c or (240, 240, 236)), B((-.7, .3, -.3), (1.4, .26, .6), (150, 200, 230), refl=.5)]
def P_washing_machine(p, c): return [B((-.32, 0, -.32), (.64, .85, .64), (236, 236, 232), mat=M_METAL), C((0, .45, -.33), (.36, .36, .02), (60, 70, 80), refl=.4)]
def P_armchair(p, c):
    f = c or (140, 60, 50)
    return [B((-.5, 0, -.45), (1.0, .45, .9), f, mat=M_FABRIC), B((-.5, .45, .25), (1.0, .55, .2), f, mat=M_FABRIC), B((-.5, .45, -.45), (.18, .25, .9), f, mat=M_FABRIC), B((.32, .45, -.45), (.18, .25, .9), f, mat=M_FABRIC)]
def P_bunk_bed(p, c):
    w = c or (120, 90, 60); out = []
    for y in (.3, 1.4): out += [B((-.5, y, -1.0), (1.0, .12, 2.0), w, mat=M_WOODV), B((-.48, y + .12, -.98), (.96, .14, 1.96), (60, 90, 150), mat=M_FABRIC)]
    return out + [B((x, 0, z), (.08, 2.1, .08), w) for x in (-.5, .42) for z in (-1.0, .92)]
def P_crib(p, c):
    w = c or (230, 220, 200); return [B((-.4, .3, -.65), (.8, .08, 1.3), w), B((-.38, .38, -.63), (.76, .1, 1.26), (200, 220, 240), mat=M_FABRIC)] + [C((x, .55, z), (.03, 1.1, .03), w) for x in (-.4, .4) for z in np.linspace(-.65, .65, 7)]
def P_fireplace(p, c):
    s = c or (130, 80, 60)
    return [B((-1.0, 0, -.2), (2.0, 1.4, .5), s, mat=M_PLASTER), B((-.6, 0, -.22), (1.2, .9, .02), (20, 14, 12)), B((-1.1, 1.4, -.3), (2.2, .12, .6), (110, 80, 56), mat=M_WOODV),
            C((0, .2, -.15), (.6, .3, .2), (255, 140, 40), emis=3., cast=False), C((0, .4, -.15), (.3, .25, .15), (255, 220, 100), emis=3.5, cast=False)]
def P_clock(p, c): return [B((-.25, 1.9, -.03), (.5, .5, .04), c or (230, 226, 210), tex={'-z': _txt(['12', '9  3', '6'], (24, 24), (30, 30, 30), (230, 226, 210, 255), 6)})]
def P_vase(p, c): return [C((0, .2, 0), (.2, .4, .2), c or (60, 100, 170)), C((0, .5, 0), (.3, .25, .3), (220, 60, 90), mat=M_FABRIC)]
def P_candles(p, c): return [C((x, .08 + h / 2, z), (.05, h, .05), (236, 226, 196)) for x, z, h in ((-.08, 0, .2), (.06, .05, .28), (.02, -.08, .14))] + [C((x, .08 + h + .03, z), (.025, .04, .025), (255, 170, 60), emis=3., cast=False) for x, z, h in ((-.08, 0, .2), (.06, .05, .28), (.02, -.08, .14))]
def P_school_desk(p, c): return [B((-.35, .7, -.25), (.7, .04, .5), c or (180, 150, 110), mat=M_WOODV)] + [B((x, 0, z), (.04, .7, .04), (70, 70, 74)) for x in (-.32, .28) for z in (-.22, .18)] + [B((-.2, .45, .3), (.4, .04, .35), (180, 150, 110)), B((-.2, .45, .62), (.4, .4, .04), (180, 150, 110))]
def P_blackboard(p, c):
    lines = p.get('text', ['2 + 2 = 4', 'LEÇON 1']); lines = lines if isinstance(lines, list) else [lines]
    return [B((-1.6, .9, -.04), (3.2, 1.3, .04), (110, 80, 56)), B((-1.52, .97, -.06), (3.04, 1.16, .02), c or (30, 60, 46), tex={'-z': _txt([str(l)[:14] for l in lines][:3], (120, 46), (230, 236, 226), (30, 60, 46, 255))})]
def P_whiteboard(p, c):
    lines = p.get('text', ['IDÉE !']); lines = lines if isinstance(lines, list) else [lines]
    return [B((-1.2, 1.0, -.04), (2.4, 1.1, .04), (180, 180, 186), mat=M_METAL), B((-1.15, 1.05, -.06), (2.3, 1.0, .02), (246, 246, 244), tex={'-z': _txt([str(l)[:14] for l in lines][:3], (96, 40), (40, 70, 180), (246, 246, 244, 255))})]
def P_cash_register(p, c): return [B((-.25, 0, -.2), (.5, .2, .4), (60, 60, 64)), B((-.2, .2, -.05), (.4, .2, .2), (40, 40, 44)), B((-.15, .3, -.06), (.3, .1, .01), (120, 255, 140), emis=1.5)]
def P_vending_machine(p, c): return [B((-.45, 0, -.4), (.9, 1.9, .8), c or (200, 40, 40), mat=M_METAL), B((-.38, .5, -.41), (.76, 1.2, .01), (200, 230, 255), emis=1.3)]
def P_arcade(p, c): return [B((-.35, 0, -.4), (.7, 1.8, .8), c or (40, 30, 90)), B((-.3, 1.05, -.42), (.6, .5, .02), (120, 255, 200), emis=1.6), B((-.33, .8, -.6), (.66, .1, .25), (30, 30, 34)), B((-.3, 1.6, -.41), (.6, .15, .01), (255, 80, 200), emis=1.8)]
def P_control_panel(p, c):
    out = [B((-1.0, 0, -.3), (2.0, .9, .6), c or (70, 76, 90), mat=M_METAL), B((-1.0, .9, -.3), (2.0, .3, .3), c or (70, 76, 90), mat=M_METAL)]
    for i in range(12): out.append(C((-.85 + (i % 6) * .34, 1.0 + (i // 6) * .12, -.31), (.06, .05, .01), [(255, 60, 60), (60, 255, 120), (255, 200, 60), (80, 160, 255)][i % 4], emis=2.))
    return out + [B((-.6, 1.2, -.02), (1.2, .7, .03), (30, 60, 90), emis=1.0)]
def P_bed_double(p, c): return [B((-.8, 0, -1.0), (1.6, .35, 2.0), (90, 62, 42), mat=M_WOODV), B((-.78, .35, -.98), (1.56, .16, 1.96), (226, 222, 214), mat=M_FABRIC),
                                B((-.7, .5, .55), (.65, .1, .3), (240, 240, 236), mat=M_FABRIC), B((.05, .5, .55), (.65, .1, .3), (240, 240, 236), mat=M_FABRIC), B((-.8, 0, .95), (1.6, 1.0, .08), (90, 62, 42), mat=M_WOODV),
                                B((-.79, .44, -.9), (1.58, .12, 1.3), c or (120, 70, 90), mat=M_FABRIC)]
def P_dining_table(p, c): return [B((-1.0, .75, -.5), (2.0, .06, 1.0), c or (130, 90, 56), mat=M_WOODV)] + [B((x, 0, z), (.06, .75, .06), (90, 60, 36)) for x in (-.95, .9) for z in (-.45, .4)]
def P_tv_stand(p, c): return [B((-.8, 0, -.25), (1.6, .45, .5), c or (60, 44, 30), mat=M_WOODV), B((-.6, .5, -.05), (1.2, .7, .05), (20, 20, 24)), B((-.57, .53, -.06), (1.14, .64, .01), (60, 110, 170), emis=float(p.get('on', 1)) * 1.)]
def P_curtains(p, c): return [B((-.9, .8, -.06), (.4, 1.6, .04), c or (150, 50, 60), mat=M_FABRIC), B((.5, .8, -.06), (.4, 1.6, .04), c or (150, 50, 60), mat=M_FABRIC), B((-1., 2.42, -.08), (2., .04, .04), (60, 50, 40))]
def P_kitchen(p, c):
    out = P_counter_long(p, c)
    out += [B((-.3, .9, -.2), (.6, .06, .4), (190, 196, 200), mat=M_METAL, refl=.3), C((.0, 1.1, .15), (.04, .2, .04), (200, 200, 205))]
    out += [B((-1.9, 1.5, .0), (3.8, .7, .35), c or (200, 196, 186), mat=M_WOODV)]
    return out
def P_counter_long(p, c): return [B((-2.0, 0, -.3), (4.0, .9, .6), c or (200, 196, 186), mat=M_WOODV), B((-2.0, .9, -.32), (4.0, .04, .64), (90, 90, 96), mat=M_METAL)]
def P_bar(p, c): return [B((-2.0, 0, -.3), (4.0, 1.05, .6), c or (90, 56, 36), mat=M_WOODV), B((-2.1, 1.05, -.35), (4.2, .05, .7), (60, 40, 26), refl=.3)] + [C((x, .38, -.75), (.32, .76, .32), (60, 60, 64)) for x in (-1.4, -.5, .4, 1.3)]
def P_cafe_table(p, c): return [C((0, .37, 0), (.06, .74, .06), (60, 60, 64)), C((0, .75, 0), (.7, .04, .7), c or (220, 220, 214)), C((0, .02, 0), (.4, .04, .4), (60, 60, 64)), C((.1, .82, .05), (.08, .1, .08), (240, 240, 236))]
def P_hospital_monitor(p, c): return [C((0, .7, 0), (.06, 1.4, .06), (180, 180, 184)), B((-.25, 1.35, -.1), (.5, .35, .15), (40, 40, 44)), B((-.22, 1.38, -.11), (.44, .29, .01), (40, 255, 120), emis=1.5)]
def P_iv_stand(p, c): return [C((0, .9, 0), (.04, 1.8, .04), (200, 200, 204), mat=M_METAL), C((0, 1.75, 0), (.4, .03, .03), (200, 200, 204)), C((.15, 1.55, 0), (.12, .2, .05), (220, 240, 250), refl=.3)]
def P_wheelchair(p, c): return [C((x, .3, 0), (.04, .6, .6), (40, 40, 44)) for x in (-.3, .3)] + [B((-.25, .45, -.25), (.5, .06, .5), c or (60, 80, 140)), B((-.25, .5, .2), (.5, .5, .05), c or (60, 80, 140))]
def P_rocket(p, c):
    out = [C((0, 3.0 + i * .9, 0), (1.4 - max(0, i - 4) * .35, .9, 1.4 - max(0, i - 4) * .35), c or (236, 236, 240), mat=M_METAL) for i in range(8)]
    out += [C((0, 5.0, -.72), (.5, .5, .02), (80, 160, 230), refl=.5), C((0, 1.8, 0), (2.4, .6, .5), (200, 40, 40)), C((0, 1.8, 0), (.5, .6, 2.4), (200, 40, 40)), C((0, 2.3, 0), (1.0, 1.2, 1.0), (60, 60, 64), mat=M_METAL)]
    return out
def P_space_window(p, c): return [B((-1.5, .8, -.05), (3.0, 1.4, .05), (5, 5, 15), tex={'-z': _stars_tex()}, texemis=1.)]
def _stars_tex():
    r = np.random.default_rng(3); a = np.zeros((48, 96, 4), np.uint8); a[..., 3] = 255; a[..., 2] = 18
    for _ in range(120): y, x = r.integers(0, 48), r.integers(0, 96); a[y, x, :3] = r.integers(150, 255)
    yy, xx = np.mgrid[0:48, 0:96]; m = (xx - 70) ** 2 + (yy - 30) ** 2 < 120; a[m, :3] = (60, 120, 200); a[(xx - 70) ** 2 + (yy - 30) ** 2 < 40, :3] = (90, 170, 90)
    return a
def P_snowman(p, c):
    return [C((0, .35, 0), (.7, .7, .7), (240, 244, 250)), C((0, .95, 0), (.5, .5, .5), (240, 244, 250)), C((0, 1.38, 0), (.36, .36, .36), (240, 244, 250)),
            C((0, 1.38, -.2), (.06, .06, .14), (240, 120, 30)), C((-.07, 1.45, -.18), (.04, .04, .02), (20, 20, 20)), C((.07, 1.45, -.18), (.04, .04, .02), (20, 20, 20)),
            C((0, 1.6, 0), (.4, .04, .4), (30, 30, 30)), C((0, 1.75, 0), (.26, .3, .26), (30, 30, 30)), C((0, 1.15, 0), (.54, .06, .54), c or (200, 40, 40))]
def P_igloo(p, c): return [C((0, .4 + .35 * i, 0), (3.0 - .6 * i, .35, 3.0 - .6 * i), (230, 236, 246)) for i in range(5)] + [B((-.4, 0, -1.7), (.8, .9, .6), (230, 236, 246)), B((-.3, 0, -1.72), (.6, .8, .02), (20, 30, 40))]
def P_portal(p, c):
    col = c or (160, 80, 255)
    return [B((-1.0, 0, -.2), (.3, 2.6, .4), (60, 56, 66), mat=M_PLASTER), B((.7, 0, -.2), (.3, 2.6, .4), (60, 56, 66), mat=M_PLASTER), B((-1.0, 2.6, -.2), (2.0, .3, .4), (60, 56, 66), mat=M_PLASTER),
            B((-.7, 0, -.05), (1.4, 2.6, .05), col, emis=2.2, cast=False)]
def P_crystal(p, c): col = c or (120, 200, 255); return [C((0, .5, 0), (.3, 1.0, .3), col, emis=.55, refl=.3), C((.25, .3, .1), (.18, .6, .18), col, emis=.45), C((-.2, .25, -.1), (.16, .5, .16), col, emis=.45)]
def P_altar(p, c): return [B((-.8, 0, -.4), (1.6, .9, .8), c or (110, 106, 100), mat=M_PLASTER), B((-.9, .9, -.5), (1.8, .1, 1.0), (90, 86, 80), mat=M_PLASTER)] + P_candles(p, None)
def P_coffin(p, c): return [B((-.35, 0, -1.0), (.7, .5, 2.0), c or (60, 36, 24), mat=M_WOODV), B((-.37, .5, -1.02), (.74, .06, 2.04), (50, 30, 20), mat=M_WOODV), C((0, .56, -.3), (.08, .02, .3), (200, 170, 60))]
def P_cage(p, c): return [B((-.6, 0, -.6), (1.2, .05, 1.2), (40, 40, 44)), B((-.6, 1.6, -.6), (1.2, .05, 1.2), (40, 40, 44))] + [C((-.6 + i * .2, .8, z), (.03, 1.6, .03), (60, 60, 64)) for i in range(7) for z in (-.6, .6)] + [C((x, .8, -.6 + i * .2), (.03, 1.6, .03), (60, 60, 64)) for i in range(7) for x in (-.6, .6)]
def P_pumpkin(p, c): return [C((0, .18, 0), (.45, .36, .42), c or (230, 120, 30)), C((0, .4, 0), (.06, .1, .06), (60, 100, 40)), C((-.08, .22, -.215), (.06, .06, .01), (255, 210, 80), emis=1.5), C((.08, .22, -.215), (.06, .06, .01), (255, 210, 80), emis=1.5)]
def P_christmas_tree(p, c):
    out = P_pine(dict(p, size=.9), (30, 90, 50))
    for i, col in enumerate([(255, 60, 60), (255, 220, 60), (80, 160, 255), (255, 255, 255), (255, 120, 220)] * 3):
        a = i * 2.1; y = .9 + (i % 5) * .45; r = .65 - (i % 5) * .12; out.append(C((math.cos(a) * r, y, math.sin(a) * r), (.08, .08, .08), col, emis=2.))
    return out + [C((0, 3.4, 0), (.2, .2, .2), (255, 220, 60), emis=2.5)]
def P_gift_pile(p, c): return [C((-.3, .15, 0), (.3, .3, .3), (200, 40, 60)), C((.2, .12, .1), (.25, .24, .25), (40, 120, 200)), C((0, .36, -.05), (.2, .2, .2), (60, 170, 80))]
def P_balloons(p, c): return [C((x, 1.5 + h, z), (.28, .32, .28), col, refl=.15) for (x, z, h, col) in ((-.2, 0, .3, (230, 50, 70)), (.15, .1, .5, (60, 140, 230)), (0, -.15, .7, (250, 210, 60)))] + [C((0, .9, 0), (.01, 1.8, .01), (230, 230, 230))]
def P_billboard(p, c):
    txt = p.get('text', ['PUB', 'ICI']); txt = txt if isinstance(txt, list) else [txt]
    return [C((-1.5, 2.0, 0), (.15, 4.0, .15), (60, 60, 64)), C((1.5, 2.0, 0), (.15, 4.0, .15), (60, 60, 64)), B((-2.2, 3.0, -.1), (4.4, 2.0, .1), (30, 30, 34)),
            B((-2.1, 3.1, -.11), (4.2, 1.8, .01), c or (40, 120, 200), tex={'-z': _txt([str(t)[:10] for t in txt][:3], (96, 40), (255, 255, 255))}, texemis=1.0)]
def P_parking_car(p, c): return P_car_basic(c)
def P_car_basic(c):
    col = c or (120, 30, 30)
    return [B((-.9, .2, -2.0), (1.8, .7, 4.0), col, mat=M_METAL), B((-.8, .9, -1.0), (1.6, .55, 2.0), col, mat=M_METAL), B((-.78, .95, -1.02), (1.56, .45, .02), (30, 40, 60), refl=.5)] + \
           [C((x, .25, z), (.2, .5, .5), (20, 20, 20)) for x in (-.9, .9) for z in (-1.3, 1.3)] + [C((x, .6, -2.01), (.25, .12, .02), (255, 240, 200), emis=1.2) for x in (-.6, .6)]
def P_police_car(p, c):
    return P_car_basic((236, 236, 240)) + [B((-.92, .5, -1.0), (1.84, .2, 2.0), (30, 50, 140)), C((-.25, 1.5, 0), (.4, .12, .25), (255, 40, 40), emis=2.5), C((.25, 1.5, 0), (.4, .12, .25), (40, 80, 255), emis=2.5)]
def P_horse_cart(p, c): return [B((-.8, .6, -1.2), (1.6, .5, 2.4), c or (130, 90, 56), mat=M_WOODV)] + [C((x, .45, z), (.08, .9, .9), (80, 56, 36)) for x in (-.85, .85) for z in (-.7, .7)] + [C((0, .5, -1.8), (.08, .08, 1.4), (100, 70, 44))]
def P_hammock(p, c): return [C((-1.4, 1.0, 0), (.3, 2.0, .3), (74, 54, 36)), C((1.4, 1.0, 0), (.3, 2.0, .3), (74, 54, 36))] + [B((-1.2 + i * .4, .9 - .12 * math.sin(i / 6 * math.pi) * 2, -.4), (.4, .04, .8), c or (220, 120, 60), mat=M_FABRIC) for i in range(6)]
def P_picnic(p, c): return [B((-.9, 0, -.7), (1.8, .015, 1.4), c or (200, 50, 50), mat=M_FABRIC, cast=False), C((.3, .12, 0), (.4, .24, .28), (150, 110, 60)), C((-.3, .05, .2), (.2, .1, .2), (240, 240, 236))]
def P_rock_pile(p, c): return P_rock(dict(size=1.2), c) + [C((.7, .15, .3), (.4, .3, .35), (104, 100, 96), mat=M_PLASTER), C((-.6, .12, -.3), (.35, .24, .3), (96, 94, 90), mat=M_PLASTER)]
def P_ruins(p, c):
    s = c or (150, 144, 132)
    return [C((-1.5, 1.2, 0), (.6, 2.4, .6), s, mat=M_PLASTER), C((1.5, .7, 0), (.6, 1.4, .6), s, mat=M_PLASTER), C((-1.5, 2.55, 0), (1.2, .3, .7), s, mat=M_PLASTER), C((.4, .2, .6), (.8, .4, .5), s, mat=M_PLASTER), C((-.2, .15, -.7), (.5, .3, .9), s, mat=M_PLASTER)]
def P_waterfall(p, c):
    out = [B((-2.0, 0, .0), (4.0, 5.0, 1.5), (90, 88, 84), mat=M_PLASTER)]
    out += [B((-.8, .0, -.06), (1.6, 5.0, .06), (150, 210, 240), emis=.4, refl=.2), B((-1.4, 0, -1.6), (2.8, .1, 1.6), (60, 140, 180), refl=.5)]
    return out

# ---- rooftops (V3): usable on any level with "y" (a roof, a ledge), see compose.py
def P_water_tank(p, c):
    w = c or (120, 92, 66); s = float(p.get('size', 1.))
    out = [C((x * s, .8 * s, z * s), (.12 * s, 1.6 * s, .12 * s), (60, 58, 56), mat=M_METAL) for x in (-.7, .7) for z in (-.7, .7)]
    out += [C((0, 1.62 * s, 0), (1.8 * s, .1 * s, 1.8 * s), (70, 66, 62), mat=M_METAL)]
    out += [C((0, (2.3 + .32 * i) * s, 0), ((1.7 - .1 * (i == 3)) * s, .33 * s, (1.7 - .1 * (i == 3)) * s), w if i % 2 == 0 else tuple(int(v * .86) for v in w), mat=M_WOODV) for i in range(4)]
    out += [C((0, 3.68 * s, 0), (1.2 * s, .22 * s, 1.2 * s), (64, 60, 56), mat=M_METAL), C((0, 3.86 * s, 0), (.5 * s, .16 * s, .5 * s), (64, 60, 56), mat=M_METAL)]
    return out
def P_ac_unit(p, c):
    b = c or (176, 178, 176)
    return [B((-.6, 0, -.45), (1.2, .85, .9), b, mat=M_METAL), C((0, .44, -.46), (.7, .7, .02), (40, 42, 44)), C((0, .44, -.47), (.62, .05, .01), (120, 120, 120)),
            C((0, .44, -.47), (.05, .62, .01), (120, 120, 120)), B((-.62, .85, -.47), (1.24, .05, .94), tuple(int(v * .85) for v in b), mat=M_METAL)]
def P_antenna(p, c):
    h = float(p.get('height', 4.)); m = c or (150, 150, 156)
    out = [C((0, h / 2, 0), (.08, h, .08), m, mat=M_METAL), C((0, .05, 0), (.5, .1, .5), (80, 80, 84))]
    out += [C((0, h * f, 0), (.9 - .5 * f, .04, .04), m) for f in (.55, .7, .85)]
    return out + [C((0, h + .06, 0), (.14, .14, .14), (255, 40, 30), emis=2.5, cast=False)]
def P_roof_vent(p, c):
    m = c or (140, 142, 146)
    return [C((0, .35, 0), (.4, .7, .4), m, mat=M_METAL), C((0, .76, 0), (.62, .08, .62), m, mat=M_METAL), C((0, .86, 0), (.3, .12, .3), tuple(int(v * .8) for v in m))]
def P_skylight(p, c):
    return [B((-.9, 0, -.7), (1.8, .35, 1.4), c or (120, 120, 124), mat=M_METAL), B((-.82, .35, -.62), (1.64, .3, 1.24), (110, 150, 180), refl=.45, emis=.15 if p.get('lit') else 0.)]
def P_stair_hut(p, c):
    w = c or (150, 146, 138)
    return [B((-1.1, 0, -1.2), (2.2, 2.5, 2.4), w, mat=M_PLASTER), B((-1.2, 2.5, -1.3), (2.4, .15, 2.6), tuple(int(v * .8) for v in w), mat=M_PLASTER),
            B((-.45, 0, -1.22), (.9, 2.05, .04), (70, 74, 80), mat=M_DOOR), C((.3, 1.0, -1.25), (.05, .05, .04), (200, 190, 150), mat=M_METAL),
            C((0, 2.3, -1.28), (.3, .14, .08), (255, 214, 140), emis=1.8, cast=False)]
def P_satellite_dish(p, c):
    m = c or (220, 220, 224)
    return [C((0, .4, 0), (.08, .8, .08), (90, 90, 94), mat=M_METAL), C((0, .95, -.05), (.8, .7, .08), m, mat=M_METAL), C((0, .95, -.4), (.04, .04, .6), (90, 90, 94))]
def P_chimney_stack(p, c):
    b = c or (130, 70, 56)
    return [C((0, .7, 0), (.7, 1.4, .7), b, mat=M_PLASTER), C((0, 1.45, 0), (.8, .1, .8), tuple(int(v * .8) for v in b), mat=M_PLASTER)] + \
           [C((x, 1.6, 0), (.16, .2, .16), (60, 56, 52)) for x in (-.18, .18)]

def _art(name, paper):
    """small pixel drawings (kid art) for P_note: 24x24 RGBA"""
    im = Image.new('RGBA', (24, 24), tuple(paper) + (255,)); d = ImageDraw.Draw(im)
    if name == 'soleil':
        d.rectangle([0, 16, 23, 23], fill=(110, 190, 90, 255)); d.rectangle([14, 3, 20, 9], fill=(255, 210, 40, 255)); d.rectangle([4, 8, 10, 16], fill=(210, 80, 60, 255)); d.rectangle([5, 4, 9, 8], fill=(150, 60, 50, 255))
    elif name == 'maison':
        d.rectangle([0, 18, 23, 23], fill=(110, 190, 90, 255)); d.rectangle([5, 10, 18, 18], fill=(235, 200, 140, 255)); d.polygon([(3, 10), (12, 3), (20, 10)], fill=(200, 60, 50, 255)); d.rectangle([10, 13, 13, 18], fill=(110, 70, 40, 255))
    elif name == 'mer':
        d.rectangle([0, 0, 23, 11], fill=(170, 215, 245, 255)); d.rectangle([0, 12, 23, 23], fill=(50, 120, 210, 255)); d.rectangle([17, 2, 21, 6], fill=(255, 210, 40, 255))
        for x in range(1, 23, 6): d.rectangle([x, 15, x + 3, 15], fill=(240, 250, 255, 255)); d.rectangle([x + 3, 19, x + 6, 19], fill=(240, 250, 255, 255))
    elif name == 'cave':                                         # 'cave' : two grey figures behind bars, a smiling little figure above ("moi")
        d.rectangle([0, 11, 23, 23], fill=(120, 120, 130, 255))
        for x in range(1, 23, 3): d.rectangle([x, 11, x, 23], fill=(30, 30, 40, 255))
        d.rectangle([4, 14, 7, 16], fill=(70, 70, 80, 255)); d.rectangle([3, 17, 8, 22], fill=(70, 70, 80, 255)); d.rectangle([15, 14, 18, 16], fill=(70, 70, 80, 255)); d.rectangle([14, 17, 19, 22], fill=(70, 70, 80, 255))
        d.rectangle([9, 2, 14, 7], fill=(60, 40, 30, 255)); d.rectangle([10, 4, 10, 4], fill=(255, 255, 255, 255)); d.rectangle([13, 4, 13, 4], fill=(255, 255, 255, 255)); d.rectangle([10, 6, 13, 6], fill=(255, 230, 120, 255))
        d.rectangle([9, 8, 14, 10], fill=(60, 120, 220, 255))
    else:                                                        # 'bonhomme' : a big and a small figure holding hands
        d.rectangle([0, 20, 23, 23], fill=(110, 190, 90, 255)); d.rectangle([5, 4, 8, 7], fill=(60, 40, 30, 255)); d.rectangle([4, 8, 9, 15], fill=(200, 60, 120, 255)); d.rectangle([5, 16, 8, 19], fill=(60, 40, 30, 255))
        d.rectangle([15, 9, 17, 11], fill=(60, 40, 30, 255)); d.rectangle([14, 12, 18, 16], fill=(60, 120, 220, 255)); d.rectangle([15, 17, 17, 19], fill=(60, 40, 30, 255)); d.rectangle([9, 12, 14, 12], fill=(60, 40, 30, 255))
    return np.array(im)

def P_note(p, c):
    """a sheet of paper or kid drawing. {"type":"note","at":[x,z],"y":1.0,"w":.3,"text":["LIGNE 1","LIGNE 2"],"ink":[r,g,b],"fs":8,"art":"soleil|maison|mer|bonhomme","color":[r,g,b],"flat":true (on a table)}
    Height follows the text (or is square for art). Faces -z like a wall prop; rot as usual. Not on a table: use it on walls, doors, fridges or as an insert."""
    w = float(p.get('w', .3)); y = float(p.get('y', 1.0)); paper = tuple(c or (244, 238, 214))
    if p.get('art'): img = _art(p['art'], paper); h = w
    else:
        fs = int(p.get('fs', 8)); lines = [str(t) for t in (p.get('text') if isinstance(p.get('text'), list) else [p.get('text', '')])]
        tw = max(len(l) for l in lines) * fs + 10; th = len(lines) * (fs + 3) + 8
        img = _txt(lines, (tw, th), tuple(p.get('ink', (40, 40, 70))), tuple(paper) + (255,), fs); h = w * th / tw
    if p.get('flat'):                       # lies on a table: the top of the text points towards +z (rot turns it)
        return [B((-w / 2, y, -h / 2), (w, .008, h), paper, tex={'+y': img}, texemis=float(p.get('glow', .12)))]
    return [B((-w / 2, y, -.012), (w, h, .012), paper, tex={'-z': img}, texemis=float(p.get('glow', .12)))]

def P_cups(p, c):
    """deux tasses de thé qui fument, sur leurs soucoupes : {"type":"cups","at":[x,z],"y":0.8} (corps en croix pour arrondir, bord clair, thé, anse, vapeur)"""
    y = float(p.get('y', .8)); out = []; white = (236, 234, 228); rim = (250, 248, 242)
    for dx, dz in ((-.12, -.03), (.13, .05)):
        out += [B((dx - .07, y, dz - .07), (.14, .012, .14), white),                                             # soucoupe
                B((dx - .045, y + .012, dz - .03), (.09, .075, .06), white), B((dx - .03, y + .012, dz - .045), (.06, .075, .09), white),   # tasse « ronde »
                B((dx - .04, y + .08, dz - .04), (.08, .008, .08), rim), B((dx - .032, y + .081, dz - .032), (.064, .006, .064), (92, 52, 26)),   # bord, thé
                B((dx + .045, y + .05, dz - .008), (.025, .012, .016), white), B((dx + .062, y + .028, dz - .008), (.012, .03, .016), white), B((dx + .045, y + .025, dz - .008), (.025, .01, .016), white)]
        for k in range(4):                                                   # la vapeur : petits cubes qui se dissolvent en montant
            out.append(B((dx - .012 + .012 * (k % 2), y + .1 + .06 * k, dz - .012), (.024, .024, .024), (214, 216, 220), dissolve=.3 + .17 * k, cast=False))
    return out

def P_assemblage(p, c):
    """A supplied list of boxes, also usable by the existing mover effect."""
    from .assemblage import boxes
    return boxes(p)


PROPS = {k[2:]: v for k, v in globals().items() if k.startswith('P_') and callable(v) and k not in ('P_parking_car',)}
PROPS['tree_round'] = P_tree_round; PROPS['autumn_tree'] = lambda p, c: P_tree_round(p, c, (190, 100, 30)); PROPS['blossom_tree'] = lambda p, c: P_tree_round(p, c, (240, 170, 200))
PROPS['police_car'] = P_police_car
PROPS.pop('car_basic', None)
PROP_LIGHTS = {   # kind -> [(local position, colour, power, radius, flicker)]
    'campfire': [((0, .6, 0), (1, .55, .25), 2.4, 6.0, 'soft')], 'lantern': [((0, 2.3, 0), (1, .8, .5), 1.3, 4.5, False)],
    'torch_wall': [((0, 1.9, -.3), (1, .6, .3), 2.2, 6.0, 'soft')], 'fireplace': [((0, .5, -.6), (1, .55, .25), 1.6, 3.8, 'soft')],
    'candles': [((0, .4, 0), (1, .62, .3), .7, 2.0, 'soft')], 'vending_machine': [((0, 1.2, -.9), (.7, .85, 1.), .7, 2.2, False)],
    'arcade': [((0, 1.3, -.9), (.6, 1., .8), .7, 2.2, 'soft')], 'cauldron': [((0, 1.0, 0), (.4, 1., .4), .9, 2.4, 'soft')],
    'christmas_tree': [((0, 1.5, -.8), (1, .8, .6), .8, 2.5, 'soft')], 'portal': [((0, 1.3, -.6), (.6, .3, 1.), 1.5, 4.0, 'soft')],
    'crystal': [((0, .8, 0), (.5, .8, 1.), .7, 2.5, False)], 'police_car': [((0, 1.8, 0), (1, .2, .2), 1.0, 4.0, True)],
    'pumpkin': [((0, .3, -.4), (1, .6, .2), .4, 1.4, 'soft')], 'altar': [((0, 1.3, 0), (1, .62, .3), .7, 2.0, 'soft')],
    'traffic_light': [((0, 3.1, -.6), (1, .3, .2), .5, 2.5, False)], 'fountain': [((0, 1.7, 0), (.6, .8, 1.), .3, 2.0, False)],
    'waterfall': [((0, 2.5, -1.), (.6, .8, 1.), .4, 3.0, False)], 'computer': [((0, 1.0, -.4), (.5, .7, 1.), .5, 1.6, False)],
    'control_panel': [((0, 1.3, -.8), (.5, .8, 1.), .6, 2.2, 'soft')], 'hospital_monitor': [((0, 1.5, -.4), (.4, 1., .6), .4, 1.4, False)],
    'stair_hut': [((0, 2.2, -1.7), (1, .82, .55), 1.0, 4.0, False)], 'antenna': [((0, 4.1, 0), (1, .15, .1), .5, 3.0, True)],
}

def scatter(rules, seed=0, avoid=()):
    """[{"type": "pine", "count": 40, "area": [x0, z0, x1, z1], "min_dist": 2, "size": [0.8, 1.3], "colors": [...]}] -> props"""
    out = []
    for k, r in enumerate(rules):
        rng = np.random.default_rng(seed * 97 + k * 13 + 5); x0, z0, x1, z1 = r.get('area', [-10, 2, 10, 30])
        md = float(r.get('min_dist', 1.5)); placed = []; tries = 0; n = int(r.get('count', 10)); sz = r.get('size', [.85, 1.25])
        while len(placed) < n and tries < n * 30:
            tries += 1; x = rng.uniform(x0, x1); z = rng.uniform(z0, z1)
            if any(a[0] <= x <= a[2] and a[1] <= z <= a[3] for a in list(avoid) + [tuple(v) for v in r.get('avoid', [])]): continue
            if any((x - px) ** 2 + (z - pz) ** 2 < md * md for px, pz in placed): continue
            placed.append((x, z)); kinds = r['type'] if isinstance(r['type'], list) else [r['type']]
            p = {'type': kinds[int(rng.integers(0, len(kinds)))], 'at': [round(x, 2), round(z, 2)], 'rot': int(rng.integers(0, 4)),
                 'size': round(float(rng.uniform(sz[0], sz[1])), 2) if isinstance(sz, list) else sz}
            if r.get('colors'): p['color'] = r['colors'][int(rng.integers(0, len(r['colors'])))]
            out.append(p)
    return out
