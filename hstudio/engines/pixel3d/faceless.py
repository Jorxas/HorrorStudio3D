"""L'homme sans visage (« faceless ») du premier moteur (films La Dernière Pompe et Le Remplaçant), porté tel quel dans PIXEL 3D : grand manteau à capuche trempé, tête = vide noir.
Paramètres de jeu (clés `x_tilt`, `x_recoil`, `x_reach`, `x_hunch`, `x_pitch`, `x_palm` d'une piste dirigée) : tilt -1..1 (tête penchée par à-coups), recoil 0..1 (rejeté en arrière, bras en bouclier),
reach 0..1 (un bras tendu devant), hunch 0..1 (voûté), pitch 0 (tête relevée) .. 1 (tête baissée, visage caché dans la capuche), palm (main droite à plat contre la vitre à cette hauteur)."""
import math
import numpy as np
from .r3d import C, M_FABRIC

DIRS = {'+z': (0, 1), '-z': (0, -1), '+x': (1, 0), '-x': (-1, 0)}
def frame(x, z, d):
    """local (fwd, side) -> world (x, z); size mapping"""
    fx, fz = DIRS[d]; sx, sz = fz, -fx            # side axis = forward rotated
    def P(f, y, s): return (x + fx * f + sx * s, y, z + fz * f + sz * s)
    def S(fw, h, sw): return (fw, h, sw) if fx != 0 else (sw, h, fw)
    return P, S


def limb(P, S, top, L, w, a, col, n=3, side=0., k=None, ws=None, mat=0, refl=0., emis=0.):
    """top=(f,y) joint, length L, thickness w, swing angle a (+ = forward). returns boxes, end point"""
    k = k or {}; out = []; ws = ws or w
    for q in range(n):
        u = (q + .5) / n
        f = top[0] + math.sin(a) * L * u; y = top[1] - math.cos(a) * L * u
        out.append(C(P(f, y, side), S(w + abs(math.sin(a)) * L / n * .6, L / n * (.6 + .4 * abs(math.cos(a))) + .04, ws), col, mat=mat, refl=refl, emis=emis, **k))
    return out, (top[0] + math.sin(a) * L, top[1] - math.cos(a) * L)


def lerp_(a, b, t): return a + (b - a) * max(0., min(1., t))

CR_COAT = (44, 46, 48); CR_COAT_D = (30, 32, 34); CR_SKIN = (8, 8, 10); CR_HEAD = (4, 4, 6)

def faceless(x, z, d='-z', phase=0., run=0., tilt=0., recoil=0., reach=0., hunch=0., hidden=False, dissolve=0., arms_up=0., scale=1.12,
             hood=True, pitch=0., palm=None):
    """tall soaked faceless man in a hooded coat. tilt -1..1 (head leaning sideways, stepped), recoil 0..1 (thrown back, arms shielding),
    reach 0..1 (one arm reaching forward), hunch 0..1, pitch 0 (head up) .. 1 (head bowed, face hidden in the hood),
    palm: right hand pressed flat forward at this local height (on the glass)"""
    P0, S0 = frame(x, z, d); k = dict(hidden=hidden, dissolve=dissolve); s = scale
    def P(f, y, sd): return P0(f * s, y * s, sd * s)
    def S(a, b, c): return S0(a * s, b * s, c * s)
    sw = math.sin(2 * math.pi * phase)
    A = .3 + .55 * run if run > 0 else 0.
    leg_a = A * sw
    hip_y = 1.0 + (.05 * run * abs(math.cos(2 * math.pi * phase)) if run else 0.)
    lean = .16 * run + .12 * hunch - .25 * recoil
    bx = []
    for sd, a in ((-1, leg_a), (1, -leg_a)):
        b, end = limb(P, S, (0., hip_y), hip_y - .05, .17, a - .2 * recoil, CR_COAT_D, n=3, side=sd * .1, k=k, mat=M_FABRIC, refl=.12)
        bx += b; bx.append(C(P(end[0] + .05, max(.05, end[1]), sd * .1), S(.26, .1, .18), (12, 12, 12), **k))
    ty = hip_y + .45
    bx.append(C(P(lean * .5, ty, 0), S(.26, .9, .44), CR_COAT, mat=M_FABRIC, refl=.16, **k))
    fl = .08 * sw * run
    for sd in (-1, 1): bx.append(C(P(lean * .3 - .02 + fl * sd, hip_y - .22, sd * .12), S(.24, .5, .2), CR_COAT_D, mat=M_FABRIC, refl=.14, **k))
    # head: a black void (no face) inside the hood; pitch bows it, tilt = stacked slabs shifted sideways
    hy = ty + .45 + .28 - .1 * pitch
    hx = lean + .05 * hunch + .08 * pitch
    for q in range(4):
        u = (q - 1.5) / 1.5
        bx.append(C(P(hx, hy + u * .19 - abs(tilt) * .06, tilt * .11 * (u + 1.2)), S(.42, .14, .4), CR_HEAD, **k))
    if hood:
        HC = (62, 64, 68); tx_ = tilt * .11
        bx.append(C(P(hx - .03, hy + .27, tx_ * 1.4), S(.52, .08, .54), HC, mat=M_FABRIC, **k))              # top
        bx.append(C(P(hx - .26, hy - .02, tx_), S(.07, .56, .54), HC, mat=M_FABRIC, **k))                    # back
        for sd in (-1, 1): bx.append(C(P(hx - .03, hy - .03, tx_ + sd * .25), S(.52, .54, .06), HC, mat=M_FABRIC, **k))
        bx.append(C(P(hx + .24, hy + .21 - .12 * pitch, tx_ * 1.4), S(.07, .12 + .12 * pitch, .54), HC, mat=M_FABRIC, **k))  # brim
        bx.append(C(P(hx - .08, hy - .33, 0), S(.42, .1, .58), HC, mat=M_FABRIC, **k))                       # drape on the shoulders
    sh_y = ty + .36
    for sd in (-1, 1):
        if palm is not None and sd > 0:
            a = 1.35
            b, end = limb(P, S, (lean * .5, sh_y), .78, .15, a, CR_COAT, n=4, side=sd * .3, k=k, mat=M_FABRIC, refl=.12)
            bx += b
            bx.append(C(P(end[0] + .05, palm, sd * .3), S(.03, .18, .16), CR_SKIN, refl=.05, **k))
            for q in range(4): bx.append(C(P(end[0] + .05, palm + .17 + .02 * abs(q - 1.5), sd * .3 + (q - 1.5) * .045), S(.03, .2, .03), CR_SKIN, refl=.05, **k))
            bx.append(C(P(end[0] + .05, palm - .02, sd * .3 - .12), S(.03, .05, .1), CR_SKIN, refl=.05, **k))
            continue
        if recoil > 0 or arms_up > 0:
            au = max(recoil, arms_up)
            a = math.pi * (.35 + .4 * au) * (1 if sd > 0 else .85)
            b, end = limb(P, S, (lean * .5, sh_y), .95, .15, a, CR_COAT, n=4, side=sd * .3, k=k, mat=M_FABRIC, refl=.12)
        elif reach > 0 and sd > 0:
            a = lerp_(.05, 1.45, reach)
            b, end = limb(P, S, (lean * .5, sh_y), 1.0, .15, a, CR_COAT, n=4, side=sd * .3, k=k, mat=M_FABRIC, refl=.12)
        else:
            a = (-.7 * leg_a if sd > 0 else .7 * leg_a) if run else .04 * sd + .05 * math.sin(phase * 6.28 + sd)
            b, end = limb(P, S, (lean * .5, sh_y), 1.05, .15, a + .2 * run, CR_COAT, n=4, side=sd * .3, k=k, mat=M_FABRIC, refl=.12)
        bx += b
        bx.append(C(P(end[0], end[1] - .04, sd * .3), S(.14, .12, .14), CR_SKIN, refl=.3, **k))
        for q in (-1, 0, 1):
            bx.append(C(P(end[0] + .02 * q, end[1] - .2, sd * .3 + q * .045), S(.035, .26, .035), CR_SKIN, refl=.3, **k))
    return bx

