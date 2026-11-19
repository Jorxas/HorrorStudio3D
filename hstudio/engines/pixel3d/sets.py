"""PIXEL 3D sets.

Every set is a `SetBuilder` with:
  - anchors: named points {name: (x, z)} the director can use instead of raw coordinates
  - build(): static boxes, built once per worker
  - scene(state, t): Scene with the dynamic parts (doors, mirror, lights, signs...) applied
  - lights(state, t, cam_pos): list of point lights (pos, colour, intensity, radius)

Prefabs: `etage_zero` (elevator cabin + corridor + emergency exit + stairwell) and `apartment`
(clean building elevator, hallway, apartment 7B with mirror). `room` builds any set from a JSON
description (rooms, doors, windows, props) so new stories don't need code.
State values may be a number, a string, or [from, to] which is interpolated over the shot.
"""
import math, copy, numpy as np
from .r3d import B, C, Box, Scene, M_FABRIC, M_WOODV, M_PLASTER, M_METAL, M_CEIL, M_DOOR, M_CARD, M_CLEAN, M_CEIL_CLEAN, vnoise2, fbm, h2
from . import world as W, places as PL
from . import environment_variation as EV     # V3: extra props and places, and the opt-in "variation" dressing
from . import interieurs as QI                # V3 : sols à palette et détails d'intérieur (opt-in : cle d'episode `diversite`)
from .assets import (text_tex, panel_tex, panel_tex_open, mirror_tex, wetsign_tex, digit_tex, city_tex,
                     ceil_crack_tex)

def sv(state, key, u, default=None):
    """state value at shot progress u (supports [a, b] interpolation)"""
    v = state.get(key, default)
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
        e = u * u * (3 - 2 * u)
        return v[0] + (v[1] - v[0]) * e
    return v

def flicker_hash(t, rate, seed=0):
    k = int(t * rate); return ((k * 2654435761 + seed * 97) & 0xffff) / 65535.

# =====================================================================================
# ETAGE ZERO prefab
# =====================================================================================
CORR_Z = 18.0
RED_Z = (5.0, 11.0, 16.4)
NEONS = (3.5, 8.0, 12.5, 17.0)
BLOOD = [(-.5, 4.6, .8), (.7, 9.6, .6), (-.2, 15.2, .7), (.3, 1.3, .5)]

def _ez_floor(P):
    x, z = P[:, 0], P[:, 2]; n = P.shape[0]
    alb = np.zeros((n, 3), np.float32); refl = np.zeros(n, np.float32)
    cab = (np.abs(x) < 1.0) & (z < 0) & (z > -2.5)
    cor = (~cab) & (z >= -.1) & (z <= CORR_Z) & (np.abs(x) < 1.9)
    sta = (z > CORR_Z)
    if cab.any():
        g = .8 + .3 * vnoise2(x[cab] * 20, z[cab] * 20, 51)
        alb[cab] = np.array((.20, .17, .15)) * g[:, None]; refl[cab] = .08
    if cor.any():
        xc, zc = x[cor], z[cor]
        tx = np.floor(xc / .45); tz = np.floor(zc / .45)
        tv = .8 + .35 * h2(tx, tz, 61)
        gr = (((xc / .45) % 1) < .06) | (((zc / .45) % 1) < .06)
        dirt = fbm(xc * 1.3, zc * 1.3, 63, 3)
        base = np.array((.30, .29, .25)) * (tv * (1 - .5 * np.clip((dirt - .45) * 2.5, 0, 1)))[:, None]
        base[gr] *= .45
        bl = np.zeros_like(xc)
        for (bx_, bz_, r) in BLOOD:
            dd = np.sqrt((xc - bx_) ** 2 + ((zc - bz_) * 1.3) ** 2) / r + (fbm(xc * 4, zc * 4, 71, 2) - .5) * .9
            bl = np.maximum(bl, np.clip((1 - dd) * 4, 0, 1))
        base = base * (1 - bl[:, None]) + np.array((.34, .05, .04)) * bl[:, None]
        alb[cor] = base
        pud = fbm(xc * .8 + 3, zc * .8, 67, 2)
        refl[cor] = np.where(pud > .55, .42, .1) * (1 - .5 * gr)
    if sta.any():
        alb[sta] = np.array((.36, .34, .30)) * (.85 + .25 * vnoise2(x[sta] * 6, z[sta] * 6, 81))[:, None]; refl[sta] = .04
    return alb, refl

def _ez_ao(P, nrm, ib):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    halfw = np.where(z < 0, 1.0, np.where(z > CORR_Z, 1.5, 1.8))
    dx = np.clip(halfw - np.abs(x), 0, 3)
    ao = np.ones(len(x), np.float32)
    fl = ib == -1; ao[fl] = .42 + .58 * np.clip(dx[fl] / .7, 0, 1)
    ce = ib == -2; ao[ce] = .55 + .45 * np.clip(dx[ce] / .6, 0, 1)
    vert = (ib >= 0) & (np.abs(nrm[:, 1]) < .5)
    ao[vert] = (.5 + .5 * np.clip(y[vert] / .5, 0, 1)) * (.7 + .3 * np.clip((2.6 - y[vert]) / .4, 0, 1))
    return ao

class EtageZero:
    name = 'etage_zero'
    anchors = {
        'cabin': (0, -1.2), 'cabin.back': (0, -2.0), 'mirror': (0, -2.42), 'panel': (.9, -1.25), 'elevator_doors': (0, 0.0),
        'corridor.start': (0, 1.2), 'corridor.mid': (0, 9.0), 'corridor.far': (0, 14.0), 'corridor.end': (0, 16.8),
        'desk': (-1.25, 2.9), 'boxes': (1.0, 5.4), 'side_door_04': (-1.7, 3.6), 'side_door_07': (1.7, 6.8),
        'side_door_11': (-1.7, 10.1), 'side_door_13': (1.7, 13.4), 'exit_door': (0, 17.9), 'red_handle': (.82, 17.85),
        'stairs': (0, 20.5), 'stairs.top': (0, 23.0),
    }
    LIGHT_ORDER = sorted([('cab', -1.2)] + [('neon', z) for z in NEONS] + [('sconce', z + 1.5) for z in np.arange(2.0, CORR_Z, 3.0)]
                         + [('red', z) for z in RED_Z], key=lambda a: a[1])

    def __init__(self, spec=None):
        self.spec = spec or {}
        self.base = None

    def build(self):
        sc = Scene(); sc.floor_fn = _ez_floor; sc.ao_fn = _ez_ao; sc.ceil_y = 2.6
        sc.ambient = (.05, .045, .04); sc.fog = (.012, .010, .009); sc.fogk = .07
        wood = (122, 100, 84); steel = (96, 100, 104); plaster = (124, 118, 100); wains = (66, 50, 40)
        floor_label = self.spec.get('floor_label', '0')
        sc.add(B((-1.1, 0, -2.5), (.1, 2.5, 2.5), wood, mat=M_WOODV, grain=.05))
        sc.add(B((1.0, 0, -2.5), (.1, 2.5, 2.5), wood, mat=M_WOODV, grain=.05))
        sc.add(B((-1.1, 0, -2.6), (2.2, 2.5, .12), wood, mat=M_WOODV, grain=.05))
        sc.add(B((-1.1, 2.4, -2.6), (2.2, .2, 2.6), (120, 120, 116), mat=M_METAL))
        sc.add(C((0, 2.37, -1.2), (.9, .03, .9), (255, 240, 205), emis=2.0))
        sc.add(B((.93, .95, -1.55), (.07, 1.1, .6), (52, 54, 60), tex={'-x': panel_tex()}, grain=.02, mat=M_METAL))
        sc.add(B((.93, .70, -1.55), (.07, .25, .6), (52, 54, 60), tex={'-x': panel_tex_open()}, grain=.02))
        sc.add(B((-.92, .48, -2.50), (1.84, 1.84, .06), (40, 40, 44), mat=M_METAL))
        sc.mirror_idx = len(sc.boxes)
        sc.add(B((-.84, .56, -2.44), (1.68, 1.68, .04), (170, 182, 190), refl=.74, grain=0.))
        sc.add(B((-1.0, 1.0, -2.0), (.06, .05, 1.8), (150, 150, 150), mat=M_METAL), B((.94, 1.0, -2.0), (.06, .05, 1.8), (150, 150, 150), mat=M_METAL))
        sc.add(B((-1.0, 1.0, -2.44), (2.0, .05, .06), (150, 150, 150), mat=M_METAL))
        sc.door_idx = len(sc.boxes)
        sc.add(B((-.55, 0, -.06), (.55, 2.2, .06), steel, grain=.05, mat=M_METAL), B((0, 0, -.06), (.55, 2.2, .06), steel, grain=.05, mat=M_METAL))
        sc.add(B((-.60, 2.2, -.1), (1.2, .4, .14), steel, mat=M_METAL))
        sc.add(B((-.18, 2.24, -.14), (.36, .14, .04), (12, 4, 4), tex={'-z': digit_tex(floor_label)}, texemis=1.6))
        sc.add(B((-.2, 2.26, .04), (.4, .18, .04), (12, 4, 4), tex={'+z': digit_tex(floor_label)}, texemis=1.6))
        sc.add(B((-1.8, 0, -.1), (1.25, 2.6, .14), plaster, mat=M_PLASTER), B((.55, 0, -.1), (1.25, 2.6, .14), plaster, mat=M_PLASTER))
        sc.add(B((-1.9, 0, 0), (.1, 2.6, CORR_Z), plaster, mat=M_PLASTER, grain=.06), B((1.8, 0, 0), (.1, 2.6, CORR_Z), plaster, mat=M_PLASTER, grain=.06))
        sc.add(B((-1.8, 0, 0), (.04, .95, CORR_Z), wains, mat=M_WOODV), B((1.76, 0, 0), (.04, .95, CORR_Z), wains, mat=M_WOODV))
        sc.add(B((-1.8, .95, 0), (.06, .05, CORR_Z), (50, 38, 30)), B((1.74, .95, 0), (.06, .05, CORR_Z), (50, 38, 30)))
        sc.sconce_idx = []
        for zz in np.arange(2.0, CORR_Z, 3.0):
            sc.add(B((-1.8, 0, zz), (.08, 2.6, .3), (78, 64, 52), mat=M_WOODV), B((1.72, 0, zz), (.08, 2.6, .3), (78, 64, 52), mat=M_WOODV))
            sc.sconce_idx.append((zz + 1.5, len(sc.boxes)))
            sc.add(C((-1.74, 1.75, zz + 1.5), (.08, .2, .14), (255, 160, 80), emis=1.2), C((1.74, 1.75, zz + 1.5), (.08, .2, .14), (255, 160, 80), emis=1.2))
        for side, zc, num in ((-1, 3.6, '04'), (1, 6.8, '07'), (-1, 10.1, '11'), (1, 13.4, '13')):
            xin = -1.8 if side < 0 else 1.8; o = -side
            def xs(a, b): return (min(xin + o * a, xin + o * b), abs(b - a))
            x0, w0 = xs(0, .04); sc.add(B((x0, 0, zc - .52), (w0, 2.18, 1.04), (52, 38, 30), mat=M_WOODV))
            x0, w0 = xs(0, .06); sc.add(B((x0, 0, zc - .44), (w0, 2.1, .88), (96, 70, 50), mat=M_DOOR))
            sc.add(C((xin + o * .09, 1.0, zc + .32), (.05, .05, .05), (180, 170, 140), mat=M_METAL))
            x0, w0 = xs(.06, .07)
            sc.add(B((x0, 1.65, zc - .12), (w0, .12, .24), (190, 180, 150), tex={('+x' if side < 0 else '-x'): text_tex([num], (24, 12), (20, 20, 20), (190, 180, 150, 255), 8, 2)}))
        sc.ceil_idx = len(sc.boxes)
        sc.add(B((-1.9, 2.6, -.1), (3.8, .15, CORR_Z + .3), (130, 128, 120), mat=M_CEIL))
        sc.neon_idx = {}
        for zz in NEONS:
            sc.neon_idx[zz] = len(sc.boxes)
            sc.add(C((0, 2.58, zz), (.55, .04, 1.2), (255, 246, 220), emis=1.7))
        sc.red_idx = []
        for zz in RED_Z: sc.red_idx.append((zz, len(sc.boxes))); sc.add(C((-1.75, 2.25, zz), (.07, .14, .24), (255, 30, 24), emis=2.8))
        dk = (88, 70, 54)
        sc.add(B((-1.74, .72, 2.3), (.7, .05, 1.3), dk, mat=M_WOODV), B((-1.72, 0, 2.32), (.06, .72, .06), (40, 40, 40)), B((-1.1, 0, 2.32), (.06, .72, .06), (40, 40, 40)),
               B((-1.72, 0, 3.52), (.06, .72, .06), (40, 40, 40)), B((-1.1, 0, 3.52), (.06, .72, .06), (40, 40, 40)), B((-1.7, .2, 2.4), (.5, .5, .4), (70, 56, 44), mat=M_WOODV))
        sc.add(B((-1.0, .42, 2.9), (.42, .06, .42), (40, 42, 46)), B((-1.0, .48, 3.27), (.42, .45, .05), (40, 42, 46)), B((-.82, 0, 3.08), (.06, .42, .06), (30, 30, 30)))
        sc.add(B((1.2, 0, 5.2), (.5, .42, .45), (140, 108, 72), mat=M_CARD), B((1.25, .42, 5.25), (.42, .36, .4), (128, 98, 66), mat=M_CARD), B((.75, 0, 5.4), (.42, .34, .4), (134, 104, 70), mat=M_CARD))
        sc.add(B((.9, 0, 2.6), (.34, .62, .05), (232, 196, 40), tex={'-z': wetsign_tex(), '+z': wetsign_tex()}))
        rng = np.random.default_rng(9)
        for i in range(14):
            px, pz = rng.uniform(-1.5, 1.5), rng.uniform(.8, CORR_Z - 1.0)
            sc.add(C((px, .004, pz), (rng.uniform(.18, .26), .006, rng.uniform(.22, .3)), (196, 192, 178), grain=.15, cast=False))
        sc.add(C((1.62, .32, 11.6), (.16, .62, .16), (190, 30, 30)), C((1.62, .7, 11.6), (.08, .1, .08), (40, 40, 40)))
        sc.add(C((-1.55, .3, 8.6), (.36, .6, .36), (60, 66, 60), mat=M_METAL))
        sc.add(B((.9, 0, 9.0), (.6, .75, .05), (70, 72, 70), mat=M_METAL), B((.9, .7, 9.0), (.6, .05, .5), (70, 72, 70), mat=M_METAL))
        sc.add(B((-1.9, 0, CORR_Z), (1.25, 2.8, .2), plaster, mat=M_PLASTER), B((.65, 0, CORR_Z), (1.25, 2.8, .2), plaster, mat=M_PLASTER), B((-.65, 2.3, CORR_Z), (1.3, .5, .2), plaster, mat=M_PLASTER))
        sc.exit_idx = len(sc.boxes)
        sc.add(B((-.55, 0, CORR_Z - .08), (1.1, 2.2, .1), (92, 34, 38), grain=.06, mat=M_METAL))
        sc.add(B((-.65, 0, CORR_Z - .05), (.1, 2.3, .08), (40, 40, 46)), B((.55, 0, CORR_Z - .05), (.1, 2.3, .08), (40, 40, 46)), B((-.65, 2.2, CORR_Z - .05), (1.3, .1, .08), (40, 40, 46)))
        sc.window_idx = len(sc.boxes)
        sc.add(B((-.22, 1.35, CORR_Z - .1), (.44, .6, .04), (18, 26, 34)))
        sc.add(B((-.42, .96, CORR_Z - .13), (.84, .08, .05), (190, 190, 196), mat=M_METAL))
        sc.add(B((-.45, 2.28, CORR_Z - .12), (.9, .26, .06), (10, 60, 24), tex={'-z': text_tex([self.spec.get('exit_label', 'SORTIE DE SECOURS')], (112, 24), (210, 255, 220), (20, 120, 50, 255), 8, 8)}, texemis=1.3, emis=.5))
        sc.handle_idx = len(sc.boxes)
        sc.add(B((.80, .85, CORR_Z - .10), (.07, .40, .08), (230, 28, 34), emis=.4))
        sc.add(B((.74, .78, CORR_Z - .06), (.19, .55, .04), (60, 60, 66), mat=M_METAL))
        cream = (190, 178, 150)
        sc.add(B((-1.6, 0, CORR_Z + .2), (.1, 3.6, 7), cream, mat=M_PLASTER), B((1.5, 0, CORR_Z + .2), (.1, 3.6, 7), cream, mat=M_PLASTER), B((-1.6, 3.5, CORR_Z + .2), (3.2, .2, 7), (200, 190, 170)))
        sc.add(B((-1.6, 0, CORR_Z + 7.1), (3.2, 3.6, .2), cream, mat=M_PLASTER))
        for i in range(10):
            sc.add(B((-1.5, 0, CORR_Z + 1.3 + i * .35), (2.9, .18 * (i + 1), .35), (150 + (i % 2) * 14, 146 + (i % 2) * 14, 140 + (i % 2) * 14), grain=.1))
        sc.add(B((-1.5, 1.0, CORR_Z + 1.5), (.06, .06, 3.4), (60, 40, 30)))
        sc.add(B((1.1, 1.2, CORR_Z + .5), (.4, .5, .1), (120, 110, 90), mat=M_METAL))
        self.base = sc

    # ---------------- dynamic state ----------------
    def _light_on(self, kind, z, state, u):
        p = sv(state, 'lights_off', u, 0.) or 0.
        if p <= 0: return 1.
        n = len(self.LIGHT_ORDER)
        for k, (kk, zz) in enumerate(self.LIGHT_ORDER):
            if kk == kind and abs(zz - z) < .05: return 0. if k < p * n else 1.
        return 1.

    def neon_level(self, zz, t, state, u):
        if not self._light_on('neon', zz, state, u): return 0.
        if state.get('past'): return 1.
        if abs(zz - 8.0) < .1: return 0.                       # the dead tube
        if abs(zz - 12.5) < .1:                                  # the flickering tube
            r = flicker_hash(t, 13)
            return 0. if r > .55 else (.35 if r > .4 else 1.)
        return 1.

    def scene(self, state, t, u):
        if self.base is None: self.build()
        b = self.base; sc = copy.copy(b); bx = list(b.boxes)
        o = float(sv(state, 'elevator_doors', u, 0.) or 0.)
        jud = float(sv(state, 'door_judder', u, 0.) or 0.)
        if jud: o = max(o, .03 * jud * (1 + math.sin(t * 40)))
        d0, d1 = bx[b.door_idx], bx[b.door_idx + 1]
        bx[b.door_idx] = Box(d0.lo - [o, 0, 0], d0.hi - [o, 0, 0], d0.col * 255, grain=.05, mat=M_METAL)
        bx[b.door_idx + 1] = Box(d1.lo + [o, 0, 0], d1.hi + [o, 0, 0], d1.col * 255, grain=.05, mat=M_METAL)
        m = bx[b.mirror_idx]; mir = state.get('mirror', 'writing')
        if mir == 'broken':
            bx[b.mirror_idx] = Box(m.lo, m.hi, (70, 14, 20), emis=.55 + .25 * math.sin(t * 1.7), grain=.3)
        elif mir == 'clean':
            bx[b.mirror_idx] = Box(m.lo, m.hi, (170, 182, 190), refl=.74, grain=0.)
        else:
            crack = float(sv(state, 'crack', u, .45 if mir == 'writing' else .8) or 0.)
            bx[b.mirror_idx] = Box(m.lo, m.hi, (170, 182, 190), refl=.7, grain=0., tex={'+z': mirror_tex(int(round(crack * 20)))}, texemis=.9)
        e = bx[b.exit_idx]; xo = float(sv(state, 'exit_door', u, 0.) or 0.)
        bx[b.exit_idx] = Box(e.lo + [xo, 0, 0], e.hi + [xo, 0, 0], (92, 34, 38), grain=.06, mat=M_METAL)
        w = bx[b.window_idx]; wm = float(sv(state, 'window_reflect', u, 0.) or 0.)
        bx[b.window_idx] = Box(w.lo + [xo, 0, 0], w.hi + [xo, 0, 0], (30, 40, 52), refl=.9 * wm, grain=0.)
        pb = bx[b.window_idx + 1]; bx[b.window_idx + 1] = Box(pb.lo + [xo, 0, 0], pb.hi + [xo, 0, 0], (190, 190, 196), mat=M_METAL)
        unlocked = state.get('lock', 'locked') == 'unlocked'
        lights_dead = (sv(state, 'lights_off', u, 0.) or 0.) >= .99
        bx.append(C((.62, 1.15, CORR_Z - .10), (.06, .06, .04), (60, 255, 110) if unlocked else (255, 40, 40),
                    emis=(.2 if lights_dead else 2.2) if (unlocked or int(t * 3) % 2 == 0) else .3))
        pull = float(sv(state, 'handle', u, 0.) or 0.)
        hb = bx[b.handle_idx]; bx[b.handle_idx] = Box(hb.lo - [0, .12 * pull, 0], hb.hi - [0, .12 * pull, 0], (230, 28, 34), emis=.4)
        sign = state.get('sign')
        if sign and not lights_dead:
            k = float(sv(state, 'sign_on', u, 1.) or 0.)
            fl = .25 if (state.get('sign_flicker') and int(t * 17) % 5 == 0) else 1.
            lines = sign if isinstance(sign, list) else str(sign).split('\n')
            bx.append(B((-.95, 2.0, CORR_Z - .15), (1.9, .56, .05), (50, 6, 8),
                        tex={'-z': text_tex([s.upper() for s in lines][:3], (190, 62), (255, 70, 60), (40, 4, 6, 255), 8, 4)}, texemis=1.6 * k * fl, emis=.2 * k))
        for zz in NEONS:
            i = b.neon_idx[zz]; nb = bx[i]; lvl = self.neon_level(zz, t, state, u)
            bx[i] = Box(nb.lo, nb.hi, (255, 246, 220) if lvl > 0 else (70, 70, 70), emis=1.6 * lvl + .03)
        for zz, i in b.sconce_idx:
            on = self._light_on('sconce', zz, state, u)
            for j in (i, i + 1): s_ = bx[j]; bx[j] = Box(s_.lo, s_.hi, (255, 160, 80) if on else (60, 50, 40), emis=1.2 if on else 0.)
        for zz, i in b.red_idx:
            rb = bx[i]; on = self._light_on('red', zz, state, u); bx[i] = Box(rb.lo, rb.hi, (255, 30, 24) if on else (50, 20, 18), emis=2.8 if on else 0.)
        cp = float(sv(state, 'ceiling_cracks', u, 0.) or 0.)
        if cp > 0:
            cb = bx[b.ceil_idx]; bx[b.ceil_idx] = Box(cb.lo, cb.hi, (130, 128, 120), mat=M_CEIL, tex={'-y': ceil_crack_tex(int(cp * 16))})
        sc.boxes = bx
        return sc

    def lights(self, state, t, u, cam_pos):
        cam_z = cam_pos[2]
        mode = state.get('lights', 'normal')
        f = 1.0
        if mode == 'flicker': f = 1 - .8 * (flicker_hash(t, 10, 3) > .6)
        if mode == 'dark': f = .15
        if state.get('quake'): f *= (1 - .5 * float(sv(state, 'quake', u, 0.)) * (int(t * 11) % 3 == 0))
        f *= (1 - .5 * (flicker_hash(t, 8) > .8) * (.4 + .6 * ((t * 8) % 1 < .5)))
        L = []
        if self._light_on('cab', -1.2, state, u):
            L.append(((0, 2.15, -1.2), (1, .92, .74), .95 * f, 2.4))
        if state.get('mirror', 'writing') == 'broken':
            L.append(((-.85, 1.9, -1.7), (1, .08, .06), .75 * (.7 + .3 * math.sin(t * 2.2)), 1.3))
        for zz in NEONS:
            lv = self.neon_level(zz, t, state, u)
            if abs(zz - cam_z) < 10 and lv > 0: L.append(((0, 2.35, zz), (1.0, .95, .82), 1.25 * lv * f, 2.8))
        for zz in np.arange(2.0, CORR_Z, 3.0):
            if abs(zz + 1.5 - cam_z) < 7 and self._light_on('sconce', zz + 1.5, state, u):
                L.append(((-1.5, 1.75, zz + 1.5), (1.0, .62, .36), .3 * f, 1.5)); L.append(((1.5, 1.75, zz + 1.5), (1.0, .62, .36), .3 * f, 1.5))
        pulse = .75 + .25 * math.sin(t * 2.2)
        for zz in RED_Z:
            if abs(zz - cam_z) < 11 and self._light_on('red', zz, state, u): L.append(((-1.45, 2.1, zz), (1.0, .08, .05), 1.25 * pulse, 2.3))
        red = float(sv(state, 'red', u, 0.) or 0.)
        if red: L.append(((0, 2.3, CORR_Z - .5), (1.0, .1, .1), red * 2.0 * (.6 + .4 * (1 - .8 * (flicker_hash(t, 11, 1) > .8))), 4.0))
        xo = float(sv(state, 'exit_door', u, 0.) or 0.)
        if xo > .08:
            L.append(((0, 2.6, CORR_Z + 3.0), (1., .9, .74), 1.1 * min(1, xo), 3.0)); L.append(((0, 1.8, CORR_Z + .6), (1., .9, .74), .75 * min(1, xo), 2.2))
        return L

# =====================================================================================
# APARTMENT prefab (ordinary building, 7th floor)
# =====================================================================================
APT_Z1 = 16.0
def _apt_floor(P):
    x, z = P[:, 0], P[:, 2]; n = P.shape[0]
    alb = np.full((n, 3), .2, np.float32); refl = np.zeros(n, np.float32)
    cab = (np.abs(x) < 1.0) & (z < 0)
    hall = (z >= 0) & (z < 9.05)
    apt = z >= 9.05
    if cab.any(): alb[cab] = np.array((.36, .36, .38)) * (.9 + .15 * vnoise2(x[cab] * 20, z[cab] * 20, 5))[:, None]; refl[cab] = .1
    if hall.any():
        xc, zc = x[hall], z[hall]
        pat = ((np.floor((xc + zc) / .3) + np.floor((xc - zc) / .3)) % 2)
        alb[hall] = np.array((.36, .12, .11)) * (.85 + .12 * pat + .1 * vnoise2(xc * 30, zc * 30, 7))[:, None]
    if apt.any():
        idx = np.nonzero(apt)[0]; xa, za = x[apt], z[apt]
        plank = np.floor(xa / .18); off = (za + h2(plank, plank * 0, 9) * 3) / 1.2
        seam = ((xa / .18) % 1 < .06) | ((off % 1) < .02)
        g = .8 + .3 * vnoise2(xa * 4, za * 30, 11) + .15 * h2(plank, np.floor(off), 12)
        alb[idx] = np.array((.42, .28, .17)) * g[:, None]
        alb[idx[seam]] *= .55; refl[idx] = .12
    return alb, refl

def _simple_ao(P, nrm, ib):
    y = P[:, 1]; ao = np.ones(len(y), np.float32)
    vert = (ib >= 0) & (np.abs(nrm[:, 1]) < .5)
    ao[vert] = (.55 + .45 * np.clip(y[vert] / .5, 0, 1)) * (.75 + .25 * np.clip((2.6 - y[vert]) / .4, 0, 1))
    return ao

def _levels_ao(levels):
    """contact shadow of vertical faces above the nearest level below them (the ground, a roof, a ledge)"""
    levels = sorted(set(levels))
    def ao_fn(P, nrm, ib):
        y = P[:, 1]; ao = np.ones(len(y), np.float32)
        vert = (ib >= 0) & (np.abs(nrm[:, 1]) < .5)
        yv = y[vert]; lv = np.full(len(yv), levels[0], np.float32)
        for L in levels[1:]: lv = np.where(yv >= L - 1e-3, np.maximum(lv, L), lv)
        ao[vert] = .55 + .45 * np.clip((yv - lv) / .5, 0, 1)
        return ao
    return ao_fn

def _lobby_floor(P):
    """hall d'immeuble (variante `lobby` du décor apartment) : carrelage gris et blanc dans le hall, le reste comme l'appartement"""
    alb, refl = _apt_floor(P)
    x, z = P[:, 0], P[:, 2]; hall = (z >= 0) & (z < 9.05)
    if hall.any():
        xc, zc = x[hall], z[hall]; chk = (np.floor(xc / .4) + np.floor(zc / .4)) % 2
        alb[hall] = np.where(chk[:, None] > 0, np.array((.62, .62, .6)), np.array((.24, .25, .27))) * (.92 + .1 * vnoise2(xc * 25, zc * 25, 3))[:, None]; refl[hall] = .12
    return alb, refl

class Apartment:
    name = 'apartment'
    anchors = {'elevator': (0, -1.2), 'elevator_doors': (0, 0), 'hall.start': (0, 1.5), 'hall.mid': (0, 5.0), 'hall.end': (0, 8.3),
               'apt_door': (0, 9.0), 'entrance': (0, 9.8), 'table': (1.15, 10.2), 'sofa': (-2.5, 12.2), 'living': (-.8, 12.5),
               'window': (2.8, 12.5), 'lamp': (-2.6, 14.8), 'mirror': (0, 15.9), 'mirror.front': (0, 15.1)}
    def __init__(self, spec=None):
        self.spec = spec or {}; self.base = None
    def build(self):
        lobby = bool(self.spec.get('lobby'))                                  # variante « hall d'immeuble » (rez-de-chaussée) : autres murs, carrelage, boîtes aux lettres
        sc = Scene(); sc.floor_fn = _lobby_floor if lobby else _apt_floor; sc.ao_fn = _simple_ao; sc.ceil_y = 2.6
        sc.ambient = (.09, .085, .08); sc.fog = (.02, .02, .025); sc.fogk = .03
        steel = (170, 172, 176); paint = tuple(self.spec.get('wall_color', (150, 160, 172) if lobby else (196, 186, 166))); aptw = tuple(self.spec.get('apt_wall', (176, 182, 186))); white = (226, 224, 216); sofac = tuple(self.spec.get('sofa_color', (52, 70, 62)))
        flo = str(self.spec.get('floor_label', '7')); door_label = self.spec.get('door_label', '7B')
        sc.add(B((-1.1, 0, -2.5), (.1, 2.5, 2.5), steel, mat=M_METAL), B((1.0, 0, -2.5), (.1, 2.5, 2.5), steel, mat=M_METAL), B((-1.1, 0, -2.6), (2.2, 2.5, .12), steel, mat=M_METAL))
        sc.add(B((-1.1, 2.4, -2.6), (2.2, .2, 2.6), white), C((0, 2.37, -1.2), (.9, .03, .9), (255, 248, 230), emis=2.2))
        sc.door_idx = len(sc.boxes)
        sc.add(B((-.55, 0, -.06), (.55, 2.2, .06), steel, mat=M_METAL), B((0, 0, -.06), (.55, 2.2, .06), steel, mat=M_METAL))
        sc.add(B((-.6, 2.2, -.1), (1.2, .4, .14), steel, mat=M_METAL))
        sc.add(B((-.2, 2.26, .04), (.4, .18, .04), (12, 6, 2), tex={'+z': text_tex([flo], (16, 12), (255, 190, 70), (12, 6, 2, 255), 8, 2)}, texemis=1.6))
        sc.add(B((-1.6, 0, -.1), (1.05, 2.6, .14), paint, mat=M_PLASTER), B((.55, 0, -.1), (1.05, 2.6, .14), paint, mat=M_PLASTER))
        sc.add(B((-1.6, 0, 0), (.1, 2.6, 9.1), paint, mat=M_PLASTER), B((1.5, 0, 0), (.1, 2.6, 9.1), paint, mat=M_PLASTER))
        sc.add(B((-1.5, 0, 0), (.03, .12, 9.0), (90, 66, 46)), B((1.47, 0, 0), (.03, .12, 9.0), (90, 66, 46)))
        sc.add(B((-1.5, 1.1, 3.0), (.03, .6, .8), (60, 80, 110), tex={'+x': city_tex()}), B((-1.52, 1.05, 2.95), (.02, .7, .9), (40, 30, 22)))
        sc.add(B((1.47, 1.2, 5.6), (.03, .5, .7), (120, 90, 60), mat=M_WOODV))
        for zz in (2.0, 5.0, 8.0): sc.add(C((0, 2.56, zz), (.35, .06, .35), (255, 236, 200), emis=1.8))
        sc.add(B((-1.6, 2.6, -.1), (3.2, .15, 9.3), white))
        if lobby:                                                             # boîtes aux lettres (mur de gauche), plante, paillasson
            sc.add(B((-1.5, .95, 5.0), (.1, .7, 1.4), (110, 114, 122), mat=M_METAL))
            for r_ in range(2):
                for c_ in range(4): sc.add(B((-1.41, 1.0 + r_ * .33, 5.05 + c_ * .34), (.02, .26, .3), (150, 154, 162), mat=M_METAL), B((-1.395, 1.19 + r_ * .33, 5.12 + c_ * .34), (.01, .03, .14), (30, 30, 34)))
            sc.add(C((1.15, .2, 8.4), (.32, .4, .32), (120, 72, 50)), C((1.15, .7, 8.4), (.55, .65, .55), (40, 92, 52), mat=M_FABRIC), B((-.6, 0, 8.3), (1.2, .02, .6), (70, 50, 40), mat=M_FABRIC))
        sc.add(B((-3.1, 0, 9.0), (2.6, 2.6, .1), aptw, mat=M_PLASTER), B((.5, 0, 9.0), (2.6, 2.6, .1), aptw, mat=M_PLASTER), B((-.5, 2.1, 9.0), (1.0, .5, .1), aptw, mat=M_PLASTER))
        sc.apt_door_idx = len(sc.boxes)
        sc.add(B((-.5, 0, 8.96), (1.0, 2.1, .05), (110, 74, 48), mat=M_DOOR))
        sc.add(B((-.15, 1.62, 8.93), (.3, .12, .01), (200, 186, 140), tex={'-z': text_tex([door_label], (24, 12), (30, 20, 10), (200, 186, 140, 255), 8, 2)}))
        sc.add(B((-3.1, 0, 9.0), (.1, 2.6, 7.1), aptw, mat=M_PLASTER), B((3.0, 0, 9.0), (.1, 2.6, 7.1), aptw, mat=M_PLASTER), B((-3.1, 0, APT_Z1), (6.2, 2.6, .1), aptw, mat=M_PLASTER))
        sc.add(B((2.96, .9, 11.0), (.04, 1.3, 3.0), (30, 40, 70), tex={'-x': city_tex()}, texemis=.8), B((2.94, .85, 10.95), (.03, 1.4, 3.1), (230, 230, 226)))
        sc.add(B((-3.0, 0, 11.0), (1.0, .45, 2.4), sofac, mat=M_FABRIC), B((-3.0, .45, 11.0), (.25, .45, 2.4), sofac, mat=M_FABRIC),
               B((-3.0, .45, 10.95), (1.0, .25, .25), sofac, mat=M_FABRIC), B((-3.0, .45, 13.15), (1.0, .25, .25), sofac, mat=M_FABRIC))
        sc.add(B((-1.7, 0, 11.6), (.8, .4, .9), (96, 70, 48), mat=M_WOODV))
        sc.add(C((-2.6, .75, 14.8), (.06, 1.5, .06), (40, 40, 40)), C((-2.6, 1.6, 14.8), (.35, .3, .35), (250, 220, 160), emis=1.4))
        sc.add(B((.9, .78, 10.0), (.6, .05, .5), (120, 86, 56), mat=M_WOODV), B((.95, 0, 10.05), (.05, .78, .05), (60, 44, 30)), B((1.4, 0, 10.05), (.05, .78, .05), (60, 44, 30)),
               B((.95, 0, 10.4), (.05, .78, .05), (60, 44, 30)), B((1.4, 0, 10.4), (.05, .78, .05), (60, 44, 30)))
        sc.add(B((-.6, .82, APT_Z1 - .04), (1.2, 1.38, .04), (40, 30, 22)))
        sc.mirror_idx = len(sc.boxes)
        sc.add(B((-.5, .9, APT_Z1 - .08), (1.0, 1.22, .04), (190, 196, 200), refl=.86, grain=0.))
        sc.add(B((-.45, 2.18, APT_Z1 - .12), (.9, .06, .08), (255, 240, 210), emis=2.0))
        sc.add(B((1.0, 1.2, APT_Z1 - .02), (.6, .8, .02), (150, 60, 50), tex={'-z': text_tex(['~'], (12, 16), (240, 220, 180), (150, 60, 50, 255), 8, 4)}))
        sc.add(B((-3.1, 2.6, 9.0), (6.2, .15, 7.2), white))
        self.base = sc
    def scene(self, state, t, u):
        if self.base is None: self.build()
        b = self.base; sc = copy.copy(b); bx = list(b.boxes)
        o = float(sv(state, 'elevator_doors', u, .5) or 0.)
        d0, d1 = bx[b.door_idx], bx[b.door_idx + 1]
        bx[b.door_idx] = Box(d0.lo - [o, 0, 0], d0.hi - [o, 0, 0], d0.col * 255, mat=M_METAL)
        bx[b.door_idx + 1] = Box(d1.lo + [o, 0, 0], d1.hi + [o, 0, 0], d1.col * 255, mat=M_METAL)
        ad = float(sv(state, 'apt_door', u, 0.) or 0.); dd = bx[b.apt_door_idx]
        bx[b.apt_door_idx] = Box(dd.lo + [.95 * ad, 0, 0], dd.hi + [.95 * ad, 0, 0], dd.col * 255, mat=M_DOOR)
        mr = float(sv(state, 'mirror_reflect', u, 1.) or 0.); mm = bx[b.mirror_idx]
        bx[b.mirror_idx] = Box(mm.lo, mm.hi, (40, 44, 50) if mr < .05 else (190, 196, 200), refl=.86 * mr, grain=0.)
        sc.boxes = bx
        return sc
    def voxel_native(self):
        """VOXEL : les portes animées (ascenseur, appartement) sont posées à part, à chaque tranche de plan, avec les lumières de l'état (néon qui grésille)"""
        self.build(); b = self.base; return {b.door_idx, b.door_idx + 1, b.apt_door_idx}, []

    def mobile(self, state, t):
        self.build(); b = self.base; sc = self.scene(state, t, 0.)
        return [sc.boxes[i] for i in (b.door_idx, b.door_idx + 1, b.apt_door_idx)], [l[:4] for l in self.lights(state, t, 0., (0., 1.6, 0.))[:-1]]

    def lights(self, state, t, u, cam_pos):
        k = 1 - .85 * float(sv(state, 'dim', u, 0.) or 0.)
        L = [((0, 2.2, -1.2), (1, .95, .85), 1.2 * k, 2.6)]
        for zz in (2.0, 5.0, 8.0): L.append(((0, 2.35, zz), (1, .86, .66), 1.0 * k, 2.6))
        L += [((0, 2.1, APT_Z1 - .35), (1, .92, .8), .9 * k, 1.6), ((-2.6, 1.55, 14.8), (1, .78, .5), 1.3 * k, 3.0),
              ((0, 2.4, 12.6), (1, .9, .76), .8 * k, 3.4), ((2.6, 1.6, 12.5), (.5, .6, 1.0), .35 * k, 3.0)]
        L.append(((cam_pos[0], cam_pos[1] + .3, cam_pos[2]), (1, .9, .78), .35, 1.8))
        return L

# =====================================================================================
# Generic set builder: rooms + props from JSON (for new stories)
# =====================================================================================
WALLS = {'plaster': ((150, 144, 124), M_PLASTER), 'plaster_blue': ((86, 100, 128), M_PLASTER), 'plaster_green': ((96, 116, 96), M_PLASTER),
         'wallpaper': ((140, 116, 96), M_WOODV), 'wood': ((122, 100, 84), M_WOODV), 'concrete': ((118, 118, 114), M_PLASTER),
         'tiles': ((176, 182, 178), M_CEIL), 'brick': ((120, 64, 50), M_PLASTER), 'hospital': ((170, 182, 170), M_PLASTER),
         'dark': ((60, 58, 56), M_PLASTER)}
FLOORS = {'wood': (.42, .28, .17), 'tiles': (.34, .34, .32), 'carpet': (.30, .12, .12), 'concrete': (.30, .30, .29),
          'checker': (.38, .38, .38), 'linoleum': (.30, .34, .30), 'grass': (.12, .2, .1), 'asphalt': (.12, .12, .13), 'dirt': (.22, .17, .12)}
LIGHTS = {'warm': (1, .86, .66), 'cold': (.86, .92, 1.0), 'neon': (1.0, .95, .82), 'red': (1, .1, .08), 'blue': (.4, .55, 1.0), 'green': (.5, 1, .6)}

def _rot(lx, lz, rot):
    rot %= 4
    if rot == 0: return lx, lz
    if rot == 1: return lz, -lx
    if rot == 2: return -lx, -lz
    return -lz, lx

def place(boxes_local, x, z, rot, y=0.):
    """boxes defined around a local origin (lx, y, lz) -> world, rotated by quarter turns, raised by y (a roof, a ledge)"""
    out = []
    for b in boxes_local:
        lo, hi = b.lo.copy(), b.hi.copy()
        cs = [_rot(lo[0], lo[2], rot), _rot(hi[0], hi[2], rot)]
        x0, x1 = sorted([cs[0][0], cs[1][0]]); z0, z1 = sorted([cs[0][1], cs[1][1]])
        b.lo = np.array([x + x0, lo[1] + y if y else lo[1], z + z0], np.float32); b.hi = np.array([x + x1, hi[1] + y if y else hi[1], z + z1], np.float32)
        if b.tex and rot % 4:
            mp = {0: {}, 1: {5: 1, 4: 0, 1: 4, 0: 5}, 2: {5: 4, 4: 5, 1: 0, 0: 1}, 3: {5: 0, 4: 1, 1: 5, 0: 4}}[rot % 4]
            b.tex = {mp.get(k, k): v for k, v in b.tex.items()}
        out.append(b)
    return out

def prop_boxes(kind, p):
    """props in local coordinates: front faces -z (towards the viewer of an unrotated prop)"""
    c = tuple(p.get('color', ())) or None
    if _OD.active() is not None:                 # clé d'épisode `objets` (objets détaillés) : la version détaillée d'un nom d'avant ; sans la clé ce test est le seul coût
        _b = _OD.prop_hook(kind, p, c)
        if _b is not None: return _b
    if kind == 'bed':
        return [B((-.5, 0, -1.0), (1.0, .35, 2.0), (70, 50, 36), mat=M_WOODV), B((-.48, .35, -.98), (.96, .16, 1.96), c or (190, 186, 176), mat=M_FABRIC),
                B((-.4, .5, .6), (.8, .1, .3), (226, 224, 216), mat=M_FABRIC), B((-.5, 0, .95), (1.0, .9, .08), (70, 50, 36), mat=M_WOODV),
                B((-.49, .44, -.9), (.98, .12, 1.3), c or (60, 76, 120), mat=M_FABRIC)]
    if kind == 'nightstand':
        return [B((-.22, 0, -.2), (.44, .5, .4), (90, 66, 46), mat=M_WOODV), C((0, .62, 0), (.14, .22, .14), (250, 220, 160), emis=1.2)]
    if kind == 'desk':
        return [B((-.6, .72, -.3), (1.2, .05, .6), c or (88, 70, 54), mat=M_WOODV)] + [B((x, 0, z), (.05, .72, .05), (40, 40, 40)) for x in (-.58, .53) for z in (-.28, .23)]
    if kind == 'chair':
        return [B((-.21, .42, -.21), (.42, .06, .42), c or (40, 42, 46)), B((-.21, .48, .16), (.42, .45, .05), c or (40, 42, 46))] + [B((x, 0, z), (.04, .42, .04), (30, 30, 30)) for x in (-.2, .16) for z in (-.2, .16)]
    if kind == 'wardrobe':
        return [B((-.6, 0, -.3), (1.2, 2.0, .6), c or (96, 70, 50), mat=M_DOOR), B((-.01, .1, -.31), (.02, 1.8, .01), (40, 30, 22)),
                C((-.08, 1.0, -.32), (.03, .12, .02), (180, 170, 140), mat=M_METAL), C((.08, 1.0, -.32), (.03, .12, .02), (180, 170, 140), mat=M_METAL)]
    if kind == 'shelf':
        return [B((-.5, 0, -.15), (1.0, 1.8, .3), c or (90, 66, 46), mat=M_WOODV)] + [B((-.46, h, -.17), (.92, .25, .02), (120 + 20 * (i % 3), 60 + 30 * (i % 2), 50), mat=M_CARD) for i, h in enumerate((.1, .55, 1.0, 1.45))]
    if kind == 'sofa':
        return [B((-1.0, 0, -.45), (2.0, .45, .9), c or (52, 70, 62), mat=M_FABRIC), B((-1.0, .45, .2), (2.0, .45, .25), c or (52, 70, 62), mat=M_FABRIC),
                B((-1.0, .45, -.45), (.22, .25, .9), c or (52, 70, 62), mat=M_FABRIC), B((.78, .45, -.45), (.22, .25, .9), c or (52, 70, 62), mat=M_FABRIC)]
    if kind == 'table':
        return [B((-.6, .75, -.4), (1.2, .05, .8), c or (120, 86, 56), mat=M_WOODV)] + [B((x, 0, z), (.05, .75, .05), (60, 44, 30)) for x in (-.55, .5) for z in (-.35, .3)]
    if kind == 'lamp':
        return [C((0, .75, 0), (.06, 1.5, .06), (40, 40, 40)), C((0, 1.6, 0), (.35, .3, .35), c or (250, 220, 160), emis=1.4)]
    if kind == 'tv':
        return [B((-.6, 0, -.25), (1.2, .5, .5), (50, 40, 32), mat=M_WOODV), B((-.5, .5, -.05), (1.0, .6, .08), (16, 16, 20)),
                B((-.46, .54, -.06), (.92, .52, .01), (40, 60, 90), emis=float(p.get('on', 1)) * .9)]
    if kind == 'mirror':
        return [B((-.55, .8, -.04), (1.1, 1.4, .04), (40, 30, 22)), B((-.48, .87, -.08), (.96, 1.26, .04), (190, 196, 200), refl=.85, grain=0.)]
    if kind == 'boxes':
        return [B((-.25, 0, -.22), (.5, .42, .45), (140, 108, 72), mat=M_CARD), B((-.2, .42, -.18), (.42, .36, .4), (128, 98, 66), mat=M_CARD), B((-.7, 0, -.1), (.42, .34, .4), (134, 104, 70), mat=M_CARD)]
    if kind == 'plant':
        return [C((0, .2, 0), (.3, .4, .3), (120, 70, 50)), C((0, .65, 0), (.5, .6, .5), (40, 90, 50), mat=M_FABRIC)]
    if kind == 'painting':
        return [B((-.4, 1.2, -.02), (.8, .6, .02), (40, 30, 22)), B((-.35, 1.25, -.03), (.7, .5, .01), c or (60, 80, 110), tex={'-z': city_tex()})]
    if kind == 'rug':
        return [B((-.9, 0, -.6), (1.8, .01, 1.2), c or (110, 40, 36), mat=M_FABRIC, cast=False)]
    if kind == 'fridge':
        return [B((-.32, 0, -.32), (.64, 1.8, .64), c or (210, 210, 206), mat=M_METAL), C((-.25, 1.2, -.33), (.03, .3, .02), (120, 120, 120))]
    if kind == 'counter':
        return [B((-1.0, 0, -.3), (2.0, .9, .6), c or (150, 140, 120), mat=M_WOODV), B((-1.0, .9, -.32), (2.0, .04, .64), (200, 200, 196), mat=M_METAL)]
    if kind == 'locker':
        return [B((-.6, 0, -.25), (1.2, 1.9, .5), c or (80, 96, 110), mat=M_METAL)] + [B((x, .1, -.26), (.01, 1.7, .01), (30, 30, 34)) for x in (-.2, .2)]
    if kind == 'hospital_bed':
        return [B((-.45, .5, -1.0), (.9, .12, 2.0), (220, 222, 226), mat=M_FABRIC), B((-.45, 0, -1.0), (.9, .5, .05), (150, 150, 156), mat=M_METAL),
                B((-.45, 0, .95), (.9, .9, .05), (150, 150, 156), mat=M_METAL)]
    if kind == 'door':      # standalone closed door (in a wall gap)
        return [B((-.5, 0, -.03), (1.0, 2.1, .06), c or (96, 70, 50), mat=M_DOOR), C((.35, 1.0, -.05), (.05, .05, .05), (180, 170, 140), mat=M_METAL)]
    if kind == 'window':
        night = p.get('night', True)
        return [B((-.6, .9, -.03), (1.2, 1.2, .04), (30, 40, 70) if night else (150, 180, 210), tex={'-z': city_tex()} if night else None, texemis=.8 if night else 0),
                B((-.65, .85, -.02), (1.3, 1.3, .02), (220, 220, 214))]
    if kind == 'streetlight':
        return [C((0, 2.0, 0), (.1, 4.0, .1), (50, 52, 56), mat=M_METAL), C((0, 3.95, -.3), (.3, .1, .6), (255, 220, 160), emis=1.6)]
    if kind == 'tree':
        return [C((0, 1.2, 0), (.3, 2.4, .3), (60, 44, 30), mat=M_WOODV), C((0, 2.9, 0), (1.6, 1.4, 1.6), (30, 60, 34), mat=M_FABRIC)]
    if kind == 'car':
        return [B((-.9, .2, -2.0), (1.8, .7, 4.0), c or (120, 30, 30), mat=M_METAL), B((-.8, .9, -1.0), (1.6, .55, 2.0), c or (120, 30, 30), mat=M_METAL),
                B((-.78, .95, -1.02), (1.56, .45, .02), (30, 40, 60), refl=.5)] + [C((x, .25, z), (.2, .5, .5), (20, 20, 20)) for x in (-.9, .9) for z in (-1.3, 1.3)]
    if kind == 'bench':
        return [B((-.8, .45, -.25), (1.6, .06, .5), (110, 80, 50), mat=M_WOODV), B((-.8, .5, .2), (1.6, .45, .06), (110, 80, 50), mat=M_WOODV)] + [B((x, 0, -.2), (.06, .45, .4), (40, 40, 40)) for x in (-.75, .69)]
    if kind == 'fence':
        return [B((-1.5, 0, -.03), (3.0, 1.2, .06), c or (70, 60, 50), mat=M_WOODV)]
    if kind == 'column':
        return [C((0, 1.3, 0), (.4, 2.6, .4), c or (130, 128, 120), mat=M_PLASTER)]
    if kind == 'crate':
        return [C((0, .3, 0), (.6, .6, .6), c or (120, 90, 56), mat=M_WOODV)]
    if kind == 'toy':        # teddy bear, small and unsettling
        return [C((0, .12, 0), (.2, .24, .16), c or (150, 110, 70), mat=M_FABRIC), C((0, .3, 0), (.16, .14, .14), c or (150, 110, 70), mat=M_FABRIC)]
    if kind in W.PROPS: return W.PROPS[kind](p, c)
    from . import ps1_elements as PE                    # éléments nés dans VOXEL (craft, banques .vox) : version PS1
    if PE.is_element(kind):
        try: return PE.boxes(kind, p)
        except Exception as e: print(f'[ps1] élément {kind} : {e}')
    return [C((0, .25, 0), (.5, .5, .5), c or (120, 120, 120))]

BASE_PROP_TYPES = ['bed', 'nightstand', 'desk', 'chair', 'wardrobe', 'shelf', 'sofa', 'table', 'lamp', 'tv', 'mirror', 'boxes', 'plant',
              'painting', 'rug', 'fridge', 'counter', 'locker', 'hospital_bed', 'door', 'window', 'streetlight', 'tree', 'car',
              'bench', 'fence', 'column', 'crate', 'toy']
PROP_TYPES = BASE_PROP_TYPES + sorted(k for k in W.PROPS if k not in BASE_PROP_TYPES)
PLACE_TYPES = sorted(PL.PLACES)

class RoomSet:
    """{"type": "room", "rooms": [{"id", "origin":[x,z], "size":[w,d], "walls", "floor", "light", "doors":[{"wall","pos","open"}],
        "windows":[...], "props":[{"type","at":[x,z],"rot":0..3,"id"}]}], "outdoor": false, "sky": "night|storm|fog"}"""
    name = 'room'
    def __init__(self, spec):
        self.spec = spec; self.base = None; self.anchors = {}; self.room_rects = []; self.light_defs = []
        self.door_info = {}                       # door id -> geometry, for doors opened by characters (acting)
        self.groups = {}                          # element id -> indices of its static boxes (effects can replace them)
        self._compute_anchors()

    def _compute_anchors(self):
        for r in self.spec.get('rooms', []):
            ox, oz = r.get('origin', [0, 0]); w, d = r.get('size', [4, 5]); rid = r.get('id', 'room')
            self.anchors[rid] = (ox, oz + d / 2); self.anchors[rid + '.center'] = (ox, oz + d / 2)
            self.anchors[rid + '.front'] = (ox, oz + .6); self.anchors[rid + '.back'] = (ox, oz + d - .6)
            self.anchors[rid + '.left'] = (ox - w / 2 + .6, oz + d / 2); self.anchors[rid + '.right'] = (ox + w / 2 - .6, oz + d / 2)
            for k, dr in enumerate(r.get('doors', [])):
                did = dr.get('id', f'{rid}.door{k}'); self.anchors[did] = self._wall_point(r, dr.get('wall', 'S'), dr.get('pos', .5), inset=.0)
            for k, wn in enumerate(r.get('windows', [])):
                self.anchors[wn.get('id', f'{rid}.window{k}')] = self._wall_point(r, wn.get('wall', 'N'), wn.get('pos', .5), inset=.3)
            for k, p in enumerate(r.get('props', [])):
                if p.get('id'): self.anchors[p['id']] = (ox + p['at'][0], oz + p['at'][1])
        for k, p in enumerate(self.spec.get('props', [])):
            if p.get('id'): self.anchors[p['id']] = tuple(p['at'])
        for k, v in (self.spec.get('anchors') or {}).items(): self.anchors[k] = tuple(v)

    def _prop_lights(self, p, ox, oz):
        for (lp, col, pw, rad, fl) in W.PROP_LIGHTS.get(p.get('type'), []):
            lx, lz = _rot(lp[0], lp[2], int(p.get('rot', 0)))
            self.light_defs.append(((ox + p['at'][0] + lx, lp[1], oz + p['at'][1] + lz), col, pw * float(p.get('light_power', 1.)), rad, fl))

    def _wall_point(self, r, wall, pos, inset=0.):
        ox, oz = r.get('origin', [0, 0]); w, d = r.get('size', [4, 5])
        if wall == 'S': return (ox - w / 2 + w * pos, oz + inset)
        if wall == 'N': return (ox - w / 2 + w * pos, oz + d - inset)
        if wall == 'W': return (ox - w / 2 + inset, oz + d * pos)
        return (ox + w / 2 - inset, oz + d * pos)

    def build(self):
        sp = self.spec; outdoor = sp.get('outdoor', False)
        sc = Scene(); sc.ceil_y = None if outdoor else float(sp.get('height', 2.6))
        sc.ambient = tuple(sp.get('ambient', (.05, .05, .06) if not outdoor else (.03, .035, .05)))
        sc.fog = tuple(sp.get('fog_color', (.012, .012, .016) if not outdoor else (.02, .025, .04))); sc.fogk = float(sp.get('fog', .07))
        sky = sky_of(sp)
        if sky:                                  # daylight / sunset: bright ambient, the horizon fades into the sky colour
            sc.ambient = tuple(sp.get('ambient', sky['ambient'])); sc.fog = tuple(sp.get('fog_color', sky['sky'])); sc.fogk = float(sp.get('fog', .018))
            sc.sky_fn = W.make_sky(sp, sky['sun'])            # painted sky, clouds, stars and horizon backdrop
        rects = []
        for r in sp.get('rooms', []):
            ox, oz = r.get('origin', [0, 0]); w, d = r.get('size', [4, 5]); h = float(r.get('height', sp.get('height', 2.6)))
            col, mat = WALLS.get(r.get('walls', 'plaster'), WALLS['plaster'])
            col = tuple(r.get('wall_color', col))
            clean = bool(r.get('clean', sp.get('clean', False)))
            if clean and mat == M_PLASTER: mat = M_CLEAN
            if r.get('floor') != 'none': rects.append((ox - w / 2, oz, ox + w / 2, oz + d, tuple(r['floor_color']) if r.get('floor_color') else FLOORS.get(r.get('floor', 'wood'), W.GROUNDS.get(r.get('floor'), FLOORS['wood'])), r.get('floor', 'wood')))   # `floor_color` (0..1, 3 ou 6 valeurs) : sols à palette, voir interieurs.py
            gaps = {'S': [], 'N': [], 'W': [], 'E': []}
            for dr in r.get('doors', []): gaps[dr.get('wall', 'S')].append((dr.get('pos', .5), dr.get('width', 1.0), 'door', dr))
            for wn in r.get('windows', []): gaps[wn.get('wall', 'N')].append((wn.get('pos', .5), wn.get('width', 1.2), 'window', wn))
            th = .1
            for wall in 'SNWE':
                horiz = wall in 'SN'; L = w if horiz else d
                segs = sorted([(g[0] * L - g[1] / 2, g[0] * L + g[1] / 2, g) for g in gaps[wall]])
                cur = 0.
                def wall_box(a, b_, y0=0., y1=h):
                    if b_ - a < .01: return
                    if horiz:
                        zz = oz if wall == 'S' else oz + d - th
                        sc.add(B((ox - w / 2 + a, y0, zz), (b_ - a, y1 - y0, th), col, mat=mat, grain=.06))
                    else:
                        xx = ox - w / 2 if wall == 'W' else ox + w / 2 - th
                        sc.add(B((xx, y0, oz + a), (th, y1 - y0, b_ - a), col, mat=mat, grain=.06))
                for a, b_, g in segs:
                    wall_box(cur, a)
                    if g[2] == 'door':
                        wall_box(a, b_, 2.1, h)
                        dr = g[3]; is_open = float(dr.get('open', 0)) > .5
                        if not is_open and not dr.get('opening_only'):
                            mid = (a + b_) / 2
                            if horiz:
                                zz = oz + (.02 if wall == 'S' else d - .08)
                                sc.add(B((ox - w / 2 + a + .02, 0, zz), (b_ - a - .04, 2.08, .06), tuple(dr.get('color', (96, 70, 50))), mat=M_DOOR))
                                hinge = (ox - w / 2 + a + .02, zz + .03)
                            else:
                                xx = ox - w / 2 + .02 if wall == 'W' else ox + w / 2 - .08
                                sc.add(B((xx, 0, oz + a + .02), (.06, 2.08, b_ - a - .04), tuple(dr.get('color', (96, 70, 50))), mat=M_DOOR))
                                hinge = (xx + .03, oz + a + .02)
                            did = dr.get('id', f"{r.get('id', 'room')}.door{r.get('doors', []).index(dr)}")
                            self.door_info[did] = dict(id=did, box=len(sc.boxes) - 1, wall=wall, hinge=hinge, width=b_ - a - .04, color=tuple(dr.get('color', (96, 70, 50))))
                        if dr.get('light_under'):
                            p_ = self._wall_point(r, wall, (a + b_) / 2 / L, inset=-.4)
                            self.light_defs.append(((p_[0], .3, p_[1]), LIGHTS.get(dr.get('light_under'), LIGHTS['warm']), .6, 1.2, False))
                    else:
                        wall_box(a, b_, 0, .9); wall_box(a, b_, 2.1, h)
                        wn = g[3]; night = wn.get('night', True)
                        if horiz:
                            zz = oz + (.04 if wall == 'S' else d - .08)
                            sc.add(B((ox - w / 2 + a, .9, zz), (b_ - a, 1.2, .04), (30, 40, 70) if night else (150, 180, 210), tex={('+z' if wall == 'S' else '-z'): city_tex()} if night else None, texemis=.7 if night else 0))
                        else:
                            xx = ox - w / 2 + .04 if wall == 'W' else ox + w / 2 - .08
                            sc.add(B((xx, .9, oz + a), (.04, 1.2, b_ - a), (30, 40, 70) if night else (150, 180, 210), tex={('+x' if wall == 'W' else '-x'): city_tex()} if night else None, texemis=.7 if night else 0))
                        if night: self.light_defs.append(((*self._wall_point(r, wall, (a + b_) / 2 / L, inset=.5)[:1], 1.5, self._wall_point(r, wall, (a + b_) / 2 / L, inset=.5)[1]), LIGHTS['blue'], .35, 2.2, False))
                    cur = b_
                wall_box(cur, L)
            if r.get('wainscot', True) and r.get('walls', 'plaster') not in ('tiles', 'concrete', 'brick'):
                for wall in 'WE':
                    xx = ox - w / 2 + .1 if wall == 'W' else ox + w / 2 - .14
                    sc.add(B((xx, 0, oz + .1), (.04, .12, d - .2), (60, 44, 32)))
            if not outdoor:
                cmat = {'rock': M_PLASTER, 'wood': M_WOODV, 'plain': M_CLEAN}.get(r.get('ceiling'), M_CEIL_CLEAN if clean else M_CEIL)
                sc.add(B((ox - w / 2, h, oz), (w, .15, d), tuple(r.get('ceiling_color', (130, 128, 120))), mat=cmat))
            lt = r.get('light', 'warm')
            if lt and lt != 'none':
                lc = LIGHTS.get(lt, LIGHTS['warm'])
                sc.add(C((ox, h - .03, oz + d / 2), (.5, .04, .5), tuple(int(255 * c) for c in lc), emis=1.6))
                self.light_defs.append(((ox, h - .3, oz + d / 2), lc, float(r.get('light_power', 1.2)), max(w, d) * .7, bool(r.get('light_flicker'))))
            for p in r.get('props', []):
                bl = prop_boxes(p.get('type', 'crate'), p)
                for b in place(bl, ox + p['at'][0], oz + p['at'][1], int(p.get('rot', 0)), float(p.get('y', 0.))): sc.add(b)
                if p.get('type') in ('lamp', 'nightstand') and p.get('on', True):
                    self.light_defs.append(((ox + p['at'][0], 1.5 if p['type'] == 'lamp' else .7, oz + p['at'][1]), LIGHTS['warm'], 1.0, 2.2, False))
                if p.get('type') == 'tv' and p.get('on', 1):
                    self.light_defs.append(((ox + p['at'][0], .8, oz + p['at'][1] - .6), LIGHTS['blue'], .7, 2.0, True))
                self._prop_lights(p, ox, oz)
        for p in sp.get('props', []):
            py_ = float(p.get('y', 0.))
            for b in place(prop_boxes(p.get('type', 'crate'), p), p['at'][0], p['at'][1], int(p.get('rot', 0)), py_):
                sc.add(b)
                if p.get('group'): self.groups.setdefault(p['group'], []).append(len(sc.boxes) - 1)
            if p.get('type') == 'streetlight':
                self.light_defs.append(((p['at'][0], 3.8 + py_, p['at'][1] - .3), LIGHTS['warm'], 1.6, 5.0, False))
            n0 = len(self.light_defs); self._prop_lights(p, 0., 0.)
            if py_: self.light_defs[n0:] = [((l[0][0], l[0][1] + py_, l[0][2]),) + tuple(l[1:]) for l in self.light_defs[n0:]]
        for bk in sp.get('blocks', []) or []:        # free blocks: anything the library does not have
            sc.add(block_box(bk))
            if bk.get('group'): self.groups.setdefault(bk['group'], []).append(len(sc.boxes) - 1)
            if bk.get('light'): self.light_defs.append((tuple(bk['at']), tuple(bk.get('light_color', (1, .85, .6))), float(bk['light']), float(bk.get('light_radius', 3.)), bool(bk.get('flicker'))))
        if outdoor:
            from . import facades as FA
            for bld in sp.get('buildings', []):
                x0, z0, x1, z1 = bld['rect']; hb = bld.get('height', 8)
                col = tuple(bld.get('color', (54, 52, 60)))
                # A `buildings` entry was a plain coloured box: no window, no door, nothing. That is the
                # purest form of the "generic building" the owner's note is about, and it is what the mid
                # ground of a street is made of. With the opt-in facade on ("env"), the same box is built
                # through block_box so it gets the real facade; without the key it is the same B() as before,
                # box for box. The style is derived from the rect so a street stays stable frame to frame.
                if FA.active() and (x1 - x0) > 1.5 and hb > 3.:
                    k = (int(abs(x0) * 7) + int(abs(z0) * 13)) % 3
                    sc.add(block_box({'at': [(x0 + x1) / 2, 0, (z0 + z1) / 2], 'size': [x1 - x0, hb, z1 - z0],
                                      'color': list(col), 'material': bld.get('material', 'plaster'),
                                      'facade': {'style': bld.get('style', ('brick', 'old', 'concrete')[k]),
                                                 'lit': float(bld.get('lit', .34)),
                                                 'night': bool(sp.get('sky', 'day') in ('night', 'storm')),
                                                 'seed': int(abs(x0) * 31 + abs(z0) * 17) + int(sp.get('seed', 0))}}))
                    continue
                sc.add(B((x0, 0, z0), (x1 - x0, hb, z1 - z0), col, mat=M_PLASTER))
        self.room_rects = rects
        gk = sp.get('ground', 'asphalt' if outdoor else 'concrete'); zones = sp.get('zones') or []
        textured = sp.get('textured_ground', bool(zones) or gk not in FLOORS)
        def floor_fn(P):
            x, z = P[:, 0], P[:, 2]; n = len(x)
            if textured:                         # procedural grounds and zones (sand, water, snow, paths...)
                wet = bool(sp.get('wet', False))
                alb, refl = W.ground(gk, x, z, wet)
                for zn in zones:
                    m = W.zone_mask(zn, x, z)
                    if m.any(): a2, r2 = W.ground(zn.get('ground', 'dirt'), x[m], z[m], wet); alb[m] = a2; refl[m] = r2
            else:
                alb = np.tile(np.array(FLOORS.get(gk), np.float32), (n, 1))
                refl = np.full(n, .25 if (outdoor and sp.get('wet', True)) else .04, np.float32)
            for (x0, z0, x1, z1, colr, kind) in rects:
                m = (x >= x0) & (x <= x1) & (z >= z0) & (z <= z1)
                if not m.any(): continue
                xm, zm = x[m], z[m]
                if kind == 'wood':
                    plank = np.floor(xm / .18); g = .8 + .3 * vnoise2(xm * 4, zm * 30, 11) + .15 * h2(plank, np.floor(zm / 1.2), 12)
                    seam = (xm / .18) % 1 < .06
                    a_ = np.array(colr) * g[:, None]; a_[seam] *= .55; refl_v = .1
                elif kind in ('tiles', 'checker', 'linoleum'):
                    tl = .45 if kind != 'checker' else .5
                    chk = ((np.floor(xm / tl) + np.floor(zm / tl)) % 2) if kind == 'checker' else h2(np.floor(xm / tl), np.floor(zm / tl), 3) * .3
                    gr = ((xm / tl) % 1 < .05) | ((zm / tl) % 1 < .05)
                    a_ = np.array(colr) * (.75 + .5 * chk)[:, None] if kind == 'checker' else np.array(colr) * (.85 + chk)[:, None]
                    a_[gr] *= .5; refl_v = .2
                elif kind in QI.FLOOR_FNS:                          # sols à motif et à couleur (parquet à chevrons, carreaux de ciment...) : interieurs.py
                    a_, refl_v = QI.floor(kind, xm, zm, colr)
                elif kind not in FLOORS and kind in W.GROUNDS:     # marble, stone, cobble... inside a room
                    a_, refl_v = W.ground(kind, xm, zm, False)
                else:
                    a_ = np.array(colr) * (.8 + .3 * fbm(xm * 1.5, zm * 1.5, 5, 2))[:, None]; refl_v = .06 if kind != 'carpet' else 0.
                alb[m] = a_; refl[m] = refl_v
            if outdoor and not textured and sp.get('wet', not SKIES.get(sp.get('sky'))):
                pud = fbm(x * .6 + 3, z * .6, 67, 2); refl = np.where(pud > .5, .5, refl)
            elif outdoor and textured and sp.get('wet'):
                pud = fbm(x * .6 + 3, z * .6, 67, 2); refl = np.where(pud > .55, np.maximum(refl, .45), refl)
            return alb, refl
        sc.floor_fn = floor_fn; sc.ao_fn = _simple_ao
        if 'ground_y' in sp:                     # the ground lies below the walkable levels (rooftops, cliffs over a valley)
            sc.floor_y = float(sp['ground_y']); sc.ao_fn = _levels_ao([sc.floor_y] + [float(w.get('y', 0.)) for w in sp.get('walkable') or []])
        self.base = sc

    def scene(self, state, t, u):
        if self.base is None: self.build()
        sc = copy.copy(self.base); sc.boxes = list(self.base.boxes)
        return sc

    def lights(self, state, t, u, cam_pos):
        mode = state.get('lights', 'normal')
        f = {'normal': 1., 'dark': .15, 'off': 0.}.get(mode, 1.)
        L = []
        for (pos, col, inten, rad, flick) in self.light_defs:
            k = f
            if flick == 'soft' and mode != 'flicker':     # fire, candles: gentle breathing instead of on/off
                k *= .84 + .16 * math.sin(t * 9.3 + pos[0] * 3.7) * math.sin(t * 5.1 + pos[2] * 2.3)
            elif (flick or mode == 'flicker') and flicker_hash(t, 10, int(pos[0] * 10)) > .6: k *= .2
            if k > 0: L.append((pos, col, inten * k, rad))
        red = float(sv(state, 'red', u, 0.) or 0.)
        if red: L.append(((cam_pos[0], 2.3, cam_pos[2] + 2), (1, .1, .08), red * 1.6, 4.0))
        sky = sky_of(self.spec)
        if sky: L.append(((cam_pos[0] + sky['sun'][0], sky['sun'][1], cam_pos[2] + sky['sun'][2]), sky['sun_col'], sky['power'], 400.))
        fill = float(self.spec.get('fill', .28))           # soft light from the camera so faces stay readable
        L.append(((cam_pos[0], cam_pos[1] + .25, cam_pos[2]), (.62, .72, 1.0) if fill <= .3 else (.95, .93, .9), fill if mode != 'off' else .12, 1.8 if fill <= .3 else 3.0))
        return L

SKIES = {'day':    dict(ambient=(.30, .32, .36), sky=(.56, .72, .94), sun=(25., 70., -25.), sun_col=(1, .96, .88), power=1.5),
         'sunset': dict(ambient=(.22, .16, .16), sky=(.95, .55, .38), sun=(-60., 14., 40.), sun_col=(1, .62, .38), power=1.4),
         'dawn':   dict(ambient=(.18, .18, .24), sky=(.70, .62, .80), sun=(50., 12., -30.), sun_col=(1, .78, .66), power=1.1),
         'overcast': dict(ambient=(.34, .35, .38), sky=(.72, .74, .76), sun=(10., 80., 10.), sun_col=(.9, .92, .95), power=.55),
         'storm':  dict(ambient=(.11, .12, .14), sky=(.26, .28, .31), sun=(0., 80., 0.), sun_col=(.7, .74, .8), power=.3),
         'night':  dict(ambient=(.08, .09, .14), sky=(.04, .06, .13), sun=(-40., 40., 70.), sun_col=(.55, .65, 1.), power=.8)}

def sky_of(sp):
    """lighting of an outdoor sky; a plain night without stars/backdrop keeps the original dark look"""
    if not sp.get('outdoor'): return None
    name = sp.get('sky')
    if name == 'night' and not (sp.get('backdrop') or sp.get('stars')): return None
    return SKIES.get(name)

def block_box(bk):
    """{"at": [x, y, z] (bottom centre), "size": [w, h, d], "color": [r,g,b], "material": "wood|metal|fabric|plaster|stone|card|door|glass|light", "emissive": 0..3,
    "facade": {"style", "lit", "seed"} procedural windows on the four sides, "roof": "tar|gravel|helipad|..." texture of the top (compose.py)}"""
    mats = {'wood': M_WOODV, 'metal': M_METAL, 'fabric': M_FABRIC, 'plaster': M_PLASTER, 'stone': M_PLASTER, 'card': M_CARD, 'door': M_DOOR}
    x, y, z = bk.get('at', (0, 0, 0)); w, h, d = bk.get('size', (1, 1, 1)); m = bk.get('material', 'plaster')
    tex = None; texemis = 0.
    if bk.get('facade') or bk.get('roof'):
        from .compose import block_textures
        tex, texemis = block_textures(bk)
    return B((x - w / 2, y, z - d / 2), (w, h, d), tuple(bk.get('color', (150, 150, 150))), mat=mats.get(m, 0), emis=float(bk.get('emissive', 2. if m == 'light' else 0.)),
             refl=.5 if m == 'glass' else float(bk.get('reflect', 0.)), cast=not bk.get('no_shadow', m == 'light'), tex=tex, texemis=texemis)

def make_set(name, spec=None):
    spec = spec or {}
    kind = spec.get('type', name)
    if kind == 'etage_zero': return EtageZero(spec)
    if kind == 'apartment':
        from . import qi_lieux as QL            # clé `diversite` : sans elle `make_apartment` rend Apartment(spec) tel quel
        return QL.make_apartment(Apartment, spec)
    if kind == 'pompe_station':                  # la station de La Dernière Pompe, portée du premier moteur (pompe_station.py)
        from .pompe_station import PompeStation
        return PompeStation(spec)
    if kind == 'theatre_bal':                    # la scène de théâtre (theatre.py) : deux versions natives, lumière de scène `stage_light`
        from .theatre import TheatreSet
        return TheatreSet(spec)
    if kind == 'hotel_nuit':                     # CHAMBRE 313 : l'hôtel de nuit (hotel.py), fumée en volume (hotel_smoke.py)
        from .hotel import HotelNuit
        return HotelNuit(spec)
    # EV.dress is the single entry point of environment_variation.py: without the "variation" key it returns the
    # expanded spec untouched, so sets written before it render box for box as before.
    if kind == 'phare_foret':                    # 14/11/2026 : le phare de « Le Phare qui efface » (phare_foret.py) : lieu prêt + passe de lieu (faisceau, brume basse)
        from .phare_foret import make as _make_phare
        return _make_phare(name, spec)
    if kind == 'phare_interieur':                # 15/11/2026 : l'intérieur de la tour (phare_interieur.py) : états `phare`, pièces mobiles, zones de lumière
        from .phare_interieur import make as _make_tour
        return _make_tour(name, spec)
    if kind in PL.PLACES:
        from . import qt_street as QS          # clé d'épisode `diversite` : sans elle `upgrade` rend (kind, spec) tels quels et `wrap` est RoomSet(...)
        k2, sp2 = QS.upgrade(kind, spec, name)
        return QS.wrap(QS.finish(EV.dress(PL.expand(k2, sp2), k2, sp2), k2, sp2, name))
    if kind == 'composed':                       # a place assembled from procedural elements (compose.py), not from a recipe
        from .compose import expand
        return RoomSet(EV.dress(expand(spec), 'composed', spec))
    from . import qt_street as QS
    return QS.wrap(QS.finish(EV.dress(spec, kind), kind, spec, name))

PREFABS = {'etage_zero': EtageZero, 'apartment': Apartment, 'theatre_bal': lambda spec=None: make_set('theatre_bal', spec)}
PREFABS['hotel_nuit'] = lambda spec=None: make_set('hotel_nuit', spec)
from . import hotel_cast as _HOTEL_CAST; _HOTEL_CAST.register()     # CHAMBRE 313 : préréglages, tenues, objets tenus (ajouts seulement : un nom déjà connu rend la main à l'original)
from . import objets as _OD; _OD.register()     # objets détaillés (01/11/2026) : décors et objets tenus `od_*` (noms nouveaux) ; les noms d'avant ne changent que sous la clé d'épisode `objets`
