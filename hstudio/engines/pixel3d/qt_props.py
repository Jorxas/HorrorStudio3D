"""Quartiers (PS1) : les DÉTAILS EN BOÎTES, l'assemblage d'un bâtiment et le lieu `quartier`.

Un détail est un objet de la bibliothèque (`world.PROPS`, clé `qt_*`) : face avant vers -z, origine sur le plan de la façade, le dehors est -z.
Le plan du bâtiment (`quartiers.building`) dit OÙ ils vont ; la texture (`qt_facade.paint`) peint le reste. La version VOXEL des mêmes détails
est dans `voxelgpu/b_quartiers.py` (autres volumes, même plan)."""
import functools
import math
import numpy as np
from .r3d import B, C, M_PLASTER, M_METAL, M_WOODV, M_FABRIC, M_DOOR
from . import quartiers as Q, qt_facade as F
from .assets import text_tex

DARK = (40, 40, 46)


def _t(c, d=None): return tuple(int(v) for v in c) if c else d


@functools.lru_cache(maxsize=256)
def _sign_tex(text, w, h, fg, bg, fs=8):
    return text_tex([text], (w, h), fg, bg + (255,), fs, max(1, (h - fs) // 2))


@functools.lru_cache(maxsize=128)
def _vert_tex(text, h, fg, bg):
    return text_tex(list(text.replace(' ', '')), (16, h), fg, bg + (255,), 8, 3)


def _txtw(text): return max(32, len(text) * 8 + 10)


# ------------------------------------------------------------------------------------------------- détails de façade
def P_balcony(p, c):
    w = float(p.get('w', 2.0)); d = float(p.get('d', .95)); slab = _t(p.get('slab'), (200, 196, 188)); rail = _t(p.get('rail'), DARK)
    out = [B((-w / 2, 0, -d), (w, .13, d), slab, mat=M_PLASTER)]
    if p.get('bkind', 'rail') == 'solid':
        out += [B((-w / 2, .13, -d), (w, .86, .07), rail), B((-w / 2, .13, -d), (.07, .86, d), rail), B((w / 2 - .07, .13, -d), (.07, .86, d), rail)]
        out.append(B((-w / 2 - .03, .99, -d - .03), (w + .06, .06, d + .06), _t(slab)))
    else:
        out += [B((-w / 2, .98, -d), (w, .05, .05), rail), B((-w / 2, .98, -d), (.05, .05, d), rail), B((w / 2 - .05, .98, -d), (.05, .05, d), rail)]
        n = max(3, int(w / .28))
        out += [B((-w / 2 + i * (w - .04) / n, .13, -d), (.04, .85, .04), rail) for i in range(n + 1)]
        out += [B((-w / 2, .13, -d + k * (d - .04) / 2), (.04, .85, .04), rail) for k in (1, 2)] + [B((w / 2 - .04, .13, -d + k * (d - .04) / 2), (.04, .85, .04), rail) for k in (1, 2)]
    if p.get('plants'):
        for i, (x, ch) in enumerate(((-w / 2 + .3, (50, 150, 70)), (w / 2 - .32, (70, 170, 90)))):
            out += [C((x, .3, -d + .28), (.3, .34, .3), (176, 92, 60)), C((x, .62, -d + .28), (.42, .4, .42), ch, mat=M_FABRIC)]
        out += [B((-.12 + .1 * k, .75, -d + .26), (.07, .07, .07), (236, 64, 96)) for k in range(2)]
    if p.get('laundry'):
        out.append(B((-w / 2 + .05, 1.62, -d + .08), (w - .1, .02, .02), (90, 90, 96)))
        for i, col in enumerate(((240, 240, 236), (240, 90, 100), (90, 140, 230), (250, 210, 70), (240, 240, 236))):
            x = -w / 2 + .2 + i * (w - .4) / 5; out.append(B((x, 1.1, -d + .08), (.26, .5, .02), col, mat=M_FABRIC))
    if p.get('table'):
        out += [C((.0, .45, -d + .4), (.5, .03, .5), (236, 236, 230)), C((0, .25, -d + .4), (.06, .3, .06), DARK)]
    return out


@functools.lru_cache(maxsize=64)
def _stripes(c1, c2, n):
    a = np.zeros((2, n * 2, 4), np.uint8)
    for i in range(n * 2): a[:, i] = (c1 if (i // 2) % 2 == 0 else c2) + (255,)
    return a


def P_awning(p, c):
    """toile rayée en 4 boîtes (la rayure est une texture, pas une boîte par bande)"""
    w = float(p.get('w', 2.4)); d = float(p.get('d', 1.15)); c1 = _t(p.get('c1'), (200, 50, 50)); c2 = _t(p.get('c2'), (244, 240, 230))
    tx = _stripes(c1, c2, max(2, int(round(w / .32))))
    return [B((-w / 2, 0, -.45), (w, .07, .45), c1, mat=M_FABRIC, tex={'+y': tx}), B((-w / 2, -.1, -.85), (w, .07, .4), c1, mat=M_FABRIC, tex={'+y': tx}),
            B((-w / 2, -.2, -d), (w, .07, d - .85), c1, mat=M_FABRIC, tex={'+y': tx}), B((-w / 2, -.5, -d), (w, .32, .04), c1, mat=M_FABRIC, tex={'-z': tx})]


def P_blade(p, c):
    text = str(p.get('text', 'BAR'))[:12]; col = _t(p.get('col'), (230, 60, 60)); lit = bool(p.get('night'))
    tx = _sign_tex(text, _txtw(text), 16, (250, 240, 200), col)
    h = .55
    return [B((-.02, 0, -.95), (.05, .05, .95), DARK, mat=M_METAL), B((-.05, -h - .08, -.95), (.1, h, .8), col, tex={'-x': tx, '+x': tx}, texemis=1.1 if lit else 0.)]


def P_fascia(p, c):
    w = float(p.get('w', 2.2)); text = str(p.get('text', 'BOUTIQUE'))[:14]; col = _t(p.get('col'), (160, 40, 40)); lit = bool(p.get('night'))
    tx = _sign_tex(text, _txtw(text), 16, (252, 244, 214), col)
    return [B((-w / 2, 0, -.1), (w, .62, .1), col, tex={'-z': tx}, texemis=1.15 if lit else 0.), B((-w / 2 - .03, -.03, -.12), (w + .06, .04, .04), DARK)]


def P_ac(p, c):
    return [B((-.35, 0, -.34), (.7, .48, .34), (226, 229, 232)), B((-.3, .06, -.37), (.6, .3, .03), (72, 78, 88)), B((-.3, -.05, -.38), (.6, .04, .38), DARK)]


def P_windowbox(p, c):
    w = float(p.get('w', 1.0)); cols = [tuple(x) for x in p.get('flowers', [(236, 60, 90), (250, 210, 50), (250, 250, 250)])]
    tx = np.zeros((2, 8, 4), np.uint8)
    for i in range(8): tx[:, i] = cols[i % len(cols)] + (255,) if i % 2 == 0 else (44, 140, 64, 255)
    return [B((-w / 2, 0, -.26), (w, .22, .26), (116, 72, 46), mat=M_WOODV), B((-w / 2 + .02, .22, -.24), (w - .04, .2, .22), (44, 140, 64), mat=M_FABRIC, tex={'+y': tx, '-z': tx})]


def P_fire_escape(p, c):
    n = int(p.get('n', 3)); fh = float(p.get('fh', 3.1)); w = float(p.get('w', 2.2)); y0 = float(p.get('y0', 0.)); col = _t(p.get('col'), (36, 36, 42)); out = []
    for f in range(1, n + 1):
        y = y0 + f * fh - .06
        out += [B((-w / 2, y, -1.0), (w, .06, 1.0), col, mat=M_METAL), B((-w / 2, y + .98, -1.0), (w, .05, .05), col, mat=M_METAL),
                B((-w / 2, y + .98, -1.0), (.05, .05, 1.0), col, mat=M_METAL), B((w / 2 - .05, y + .98, -1.0), (.05, .05, 1.0), col, mat=M_METAL),
                ]
        if f < n:                                                                    # la volée vers l'étage au-dessus, en zigzag
            up = (f % 2 == 0)
            for k in range(4):
                xs = (-w / 2 + .1 + k * (w - .5) / 4) if up else (w / 2 - .5 - k * (w - .5) / 4)
                out.append(B((xs, y + .1 + k * fh / 4.4, -.7), (.5, .06, .5), col, mat=M_METAL))
    return out


def P_chimney(p, c):
    col = _t(c or p.get('col'), (150, 72, 54)); h = float(p.get('h', 1.9))
    return [B((-.35, 0, -.35), (.7, h, .7), col, mat=M_PLASTER), B((-.45, h, -.45), (.9, .16, .9), _t(p.get('cap'), (196, 190, 180))),
            C((-.15, h + .3, 0), (.2, .3, .2), (150, 60, 46)), C((.18, h + .3, 0), (.2, .3, .2), (150, 60, 46))]


def P_stoop(p, c):
    w = float(p.get('w', 1.4)); col = _t(p.get('col'), (196, 190, 178)); out = []
    for k in range(4):
        out.append(B((-w / 2, k * .16, -(1.7 - k * .42)), (w, .16, 1.7 - k * .42), col, mat=M_PLASTER))
    out += [B((-w / 2 - .06, 0, -1.7), (.06, 1.0, 1.7), DARK, mat=M_METAL), B((w / 2, 0, -1.7), (.06, 1.0, 1.7), DARK, mat=M_METAL)]
    if p.get('plant'):
        out += [C((-w / 2 - .4, .25, -1.5), (.4, .5, .4), (176, 92, 60)), C((-w / 2 - .4, .7, -1.5), (.55, .5, .55), (50, 150, 74), mat=M_FABRIC)]
    return out


def P_porch(p, c):
    col = _t(p.get('col'), (246, 244, 236)); roof = _t(p.get('roof'), (92, 70, 60)); out = [B((-1.7, 0, -1.9), (3.4, .3, 1.9), (170, 150, 128), mat=M_WOODV)]
    out += [B((-.7, 0, -2.55), (1.4, .1, .65), (186, 166, 140)), B((-.7, .1, -2.2), (1.4, .1, .3), (186, 166, 140))]
    out += [B((x, .3, -1.85), (.12, 2.2, .12), col) for x in (-1.65, 1.53)]
    out += [B((-1.8, 2.5, -2.0), (3.6, .16, 2.0), roof, mat=M_PLASTER), B((-1.7, 2.66, -1.8), (3.4, .14, 1.6), roof), B((-1.6, 2.8, -1.6), (3.2, .12, 1.2), roof)]
    out += [B((-1.65, .3, -1.85), (3.3, .06, .05), col), B((-1.65, 1.1, -1.85), (3.3, .05, .05), col)]
    if p.get('swing'): out += [B((.3, .45, -1.5), (1.0, .08, .4), (150, 100, 60)), B((.3, 1.3, -1.7), (1.0, .06, .08), DARK)]
    return out


def P_neon(p, c):
    text = str(p.get('text', 'BAR'))[:7]; col = _t(p.get('col'), (255, 40, 170)); h = float(p.get('h', 3.2)); lit = bool(p.get('night', True))
    hpx = max(24, len(text.replace(' ', '')) * 11 + 6)
    tx = _vert_tex(text, hpx, tuple(min(255, int(v * .9 + 40)) for v in col), (16, 14, 28))
    e = 1.9 if lit else .2
    return [B((-.3, 0, -.22), (.6, h, .12), (16, 14, 28), tex={'-z': tx}, texemis=e), B((-.34, -.04, -.26), (.68, .04, .2), col, emis=e), B((-.34, h, -.26), (.68, .04, .2), col, emis=e),
            B((-.34, 0, -.26), (.04, h, .2), col, emis=e), B((.3, 0, -.26), (.04, h, .2), col, emis=e), B((-.03, h, -.06), (.06, .5, .06), DARK)]


def P_canopy(p, c):
    w = float(p.get('w', 3.2)); col = _t(p.get('col'), (210, 216, 224))
    return [B((-w / 2, 0, -1.6), (w, .12, 1.6), col, mat=M_METAL), B((-w / 2, -.28, -1.6), (w, .28, .08), (250, 120, 30), mat=M_METAL), B((-w / 2 + .1, -3.0, -1.5), (.12, 3.0, .12), DARK, mat=M_METAL),
            B((w / 2 - .22, -3.0, -1.5), (.12, 3.0, .12), DARK, mat=M_METAL)]


def P_boug(p, c):
    w = float(p.get('w', 2.4)); h = float(p.get('h', 2.2)); rng = np.random.default_rng(int(p.get('seed', 1))); out = []
    for k in range(int(w * h * 2.4)):
        x = -w / 2 + rng.random() * w; y = rng.random() * h * (.4 + .6 * rng.random()); col = (214, 40, 124) if rng.random() < .62 else (52, 140, 66)
        out.append(B((x, y, -.14 - .12 * rng.random()), (.2, .16, .12), col, mat=M_FABRIC))
    return out


def P_terrace(p, c):
    pc = _t(p.get('col'), (210, 50, 50))
    return [C((0, .74, 0), (.7, .05, .7), (236, 232, 222)), C((0, .37, 0), (.06, .74, .06), DARK), C((-.62, .45, 0), (.4, .06, .4), (170, 110, 64)), C((.62, .45, 0), (.4, .06, .4), (170, 110, 64)),
            C((0, 1.3, 0), (.06, 2.6, .06), DARK), C((0, 2.7, 0), (2.4, .1, 2.4), pc, mat=M_FABRIC), C((0, 2.85, 0), (1.3, .1, 1.3), (244, 240, 230), mat=M_FABRIC)]


def P_lamp(p, c, style='old'):
    st = p.get('style', style)
    if st == 'modern':
        return [C((0, 2.6, 0), (.12, 5.2, .12), (88, 92, 100), mat=M_METAL), B((-.1, 5.1, -.9), (.16, .14, 1.0), (88, 92, 100)), B((-.18, 5.0, -.95), (.36, .08, .5), (240, 248, 255), emis=1.7)]
    if st == 'neon':
        return [C((0, 2.4, 0), (.1, 4.8, .1), (30, 30, 40), mat=M_METAL), B((-.9, 4.2, -.04), (1.1, .05, .05), (30, 30, 40)), B((-.9, 4.17, -.07), (1.0, .06, .06), (255, 60, 190), emis=2.3),
                B((-.04, 3.4, -.08), (.06, .8, .06), (60, 230, 255), emis=2.3)]
    if st == 'deco':
        return [C((0, 1.9, 0), (.2, 3.8, .2), (34, 90, 86), mat=M_METAL), C((0, .15, 0), (.4, .3, .4), (34, 90, 86)), B((-.3, 3.8, -.3), (.6, .5, .6), (255, 232, 170), emis=1.5), B((-.36, 4.3, -.36), (.72, .1, .72), (222, 176, 70)),
                B((-.04, 4.4, -.04), (.08, .3, .08), (222, 176, 70))]
    if st == 'lantern':
        return [C((0, 1.6, 0), (.08, 3.2, .08), (34, 34, 40), mat=M_METAL), B((-.9, 3.0, -.04), (.9, .05, .05), (34, 34, 40)), B((-1.0, 2.55, -.12), (.22, .4, .22), (255, 214, 130), emis=1.7), B((-1.06, 2.95, -.18), (.34, .06, .34), (34, 34, 40))]
    return [C((0, 1.9, 0), (.1, 3.8, .1), (30, 74, 66) if st == 'old' else (36, 36, 42), mat=M_METAL), C((0, .18, 0), (.3, .36, .3), (30, 74, 66) if st == 'old' else (36, 36, 42)),
            B((-.2, 3.75, -.2), (.4, .45, .4), (255, 220, 150), emis=1.6), B((-.26, 4.2, -.26), (.52, .1, .52), (30, 74, 66) if st == 'old' else (36, 36, 42)), B((-.22, 3.68, -.22), (.44, .08, .44), (30, 74, 66) if st == 'old' else (36, 36, 42))]


def P_lamp_cool(p, c): return P_lamp(dict(p, style=p.get('style', 'modern')), c)
def P_lamp_neon(p, c): return P_lamp(dict(p, style='neon'), c)


def P_dish_balcony(p, c):
    return [C((0, .1, 0), (.5, .06, .5), (230, 232, 236)), B((-.02, .1, -.02), (.04, .3, .04), DARK), B((-.2, .3, -.25), (.4, .4, .06), (236, 238, 240))]


NEW_PROPS = {'qt_balcony': P_balcony, 'qt_awning': P_awning, 'qt_blade': P_blade, 'qt_fascia': P_fascia, 'qt_ac': P_ac, 'qt_windowbox': P_windowbox,
             'qt_fire_escape': P_fire_escape, 'qt_chimney': P_chimney, 'qt_stoop': P_stoop, 'qt_porch': P_porch, 'qt_neon': P_neon, 'qt_canopy': P_canopy,
             'qt_boug': P_boug, 'qt_terrace': P_terrace, 'qt_lamp': P_lamp, 'qt_lamp_cool': P_lamp_cool, 'qt_lamp_neon': P_lamp_neon}
NEW_LIGHTS = {'qt_neon': [((0, 1.8, -.8), (1., .35, .8), .9, 4.0, False)], 'qt_lamp': [((0, 3.8, -.3), (1, .84, .58), 1.5, 5.2, False)], 'qt_lamp_cool': [((0, 4.8, -.8), (.86, .93, 1.), 1.5, 5.6, False)],
              'qt_lamp_neon': [((-.4, 4.0, -.2), (1., .3, .8), 1.5, 5.2, False)]}


# ------------------------------------------------------------------------------------------------- le repère d'un bâtiment
class Frame:
    """(u, v) -> monde : u = le long de la façade, de gauche à droite VU DE LA RUE ; v = en profondeur, vers l'intérieur du bâtiment."""

    def __init__(s, d):
        s.x0, s.z0, s.x1, s.z1 = d['rect']; s.front = d['front']; s.rot = {'+x': 3, '-x': 1, '-z': 0, '+z': 2}[s.front]

    def pt(s, u, v=0.):
        f = s.front
        if f == '+x': return (s.x1 - v, s.z0 + u)
        if f == '-x': return (s.x0 + v, s.z1 - u)
        if f == '-z': return (s.x0 + u, s.z0 + v)
        return (s.x1 - u, s.z1 - v)

    def box(s, u0, u1, v0, v1):
        (xa, za), (xb, zb) = s.pt(u0, v0), s.pt(u1, v1)
        return ((xa + xb) / 2, (za + zb) / 2, abs(xb - xa), abs(zb - za))


def _blk(out, gid, f, u0, u1, v0, v1, y, h, col, mat='flat', **kw):
    cx, cz, sx, sz = f.box(u0, u1, v0, v1)
    out.append(dict(at=[round(cx, 3), round(y, 3), round(cz, 3)], size=[round(max(sx, .02), 3), round(h, 3), round(max(sz, .02), 3)], color=list(col), material=mat, group=gid, **kw))


def _sh(c, f): return tuple(int(max(0, min(255, v * f))) for v in c)


# ------------------------------------------------------------------------------------------------- les toits
def roof_blocks(d, f, gid, night, detail=True):
    """blocs du toit et du couronnement ; -> (blocs, hauteur du dessus pour poser des objets)"""
    I = Q.IDENTITES[d['ident']]
    W, D, H = d['W'], d['D'], d['H']; kind = d['roof']; out = []; trim = d['trim']; body = d['body']; rc = d['roof_col']
    top = H
    def parapet(h=.8, col=None):
        if not detail: return                                                         # bâtiment lointain : pas de rebord (une boîte de moins par côté)
        col = col or _sh(body, .86)
        _blk(out, gid, f, 0, W, 0, .2, H, h, col); _blk(out, gid, f, 0, W, D - .2, D, H, h, col); _blk(out, gid, f, 0, .2, .2, D - .2, H, h, col); _blk(out, gid, f, W - .2, W, .2, D - .2, H, h, col)
    def cornice():
        if not detail: return
        _blk(out, gid, f, -.25, W + .25, -.25, D + .25, H - .12, .14, trim)
    def steps(u0, u1, v0, v1, y, rise, n, cols, ov=.0, ridge=.45, along='u'):
        h = rise / n
        for k in range(n):
            t = k / n
            if along == 'u': a0, a1, b0, b1 = u0 - ov + t * ((u1 - u0) / 2 - ridge / 2 + ov), u1 + ov - t * ((u1 - u0) / 2 - ridge / 2 + ov), v0 - ov, v1 + ov
            elif along == 'v': a0, a1, b0, b1 = u0 - ov, u1 + ov, v0 - ov + t * ((v1 - v0) / 2 - ridge / 2 + ov), v1 + ov - t * ((v1 - v0) / 2 - ridge / 2 + ov)
            else: a0, a1, b0, b1 = u0 - ov + t * ((u1 - u0) / 2 - ridge / 2 + ov), u1 + ov - t * ((u1 - u0) / 2 - ridge / 2 + ov), v0 - ov + t * ((v1 - v0) / 2 - ridge / 2 + ov), v1 + ov - t * ((v1 - v0) / 2 - ridge / 2 + ov)
            _blk(out, gid, f, a0, a1, b0, b1, y + k * h, h + .01, cols[k % 2])
        return y + rise
    cols = (rc, _sh(rc, .88))
    if kind in ('gable', 'gable_front', 'hip', 'terracotta'):
        cornice()
        rise = (D if kind == 'gable_front' else W) * (.34 if kind != 'terracotta' else .16) + .5
        rise = min(rise, 4.6)
        if kind == 'gable':                                                          # faîtage parallèle à la rue
            top = steps(0, W, 0, D, H, min(rise, D * .34 + .4), 4 if detail else 3, cols, .3, .5, 'v')
        elif kind == 'gable_front':                                                  # pignon sur rue : le triangle est du mur, pas du toit
            top = steps(0, W, .35, D, H, min(rise, W * .38 + .5), 4 if detail else 3, cols, .3, .5, 'u')
            n = 4 if detail else 3; h = min(rise, W * .38 + .5) / n
            for k in range(n):
                t = k / n; _blk(out, gid, f, t * W / 2 - .0, W - t * W / 2, -.04, .4, H + k * h, h + .01, _sh(body, .98) if k % 2 == 0 else body)
            if W > 3.4:
                _blk(out, gid, f, W / 2 - .3, W / 2 + .3, -.08, .2, H + h * .6, h * 1.6, (255, 214, 140) if night else (120, 160, 210), mat='flat', **({'emissive': 1.0} if night else {}))
        elif kind == 'hip':
            top = steps(0, W, 0, D, H, min(rise, min(W, D) * .3 + .4), 4 if detail else 3, cols, .3, .6, 'both')
        else:
            top = steps(0, W, 0, D, H, 1.5, 3, cols, .3, 1.2, 'both')
    elif kind == 'sawtooth':
        cornice(); parapet(.5)
        n = max(2, int(D / 4.2)); tw = D / n
        for k in range(n):                                                           # chaque dent : un dos incliné (3 marches) et un vitrage vertical côté nord
            v0 = k * tw
            for s in range(3): _blk(out, gid, f, .3, W - .3, v0 + s * tw * .26, v0 + tw * .9, H + .5 + s * .5, .5, _sh(rc, .8 + .1 * s), mat='metal')
            _blk(out, gid, f, .3, W - .3, v0 + tw * .88, v0 + tw * .96, H + .5, 2.0, (170, 220, 230) if not night else (255, 226, 150), **({'emissive': .9} if night else {}))
        top = H + 2.5
    elif kind in ('stepped', 'stepped_glass'):
        cornice(); parapet(.35, trim)
        tiers = [(.86, 2.8), (.66, 2.6), (.42, 3.2)] if kind == 'stepped' else [(.82, 2.4), (.5, 2.0)]
        y = H + .35
        for ti, (sc, hh) in enumerate(tiers):
            u0, u1 = W * (1 - sc) / 2, W * (1 + sc) / 2; v0, v1 = D * (1 - sc) / 2, D * (1 + sc) / 2
            _blk(out, gid, f, u0, u1, v0, v1, y, hh, body if kind == 'stepped' else _sh(body, .95), mat='flat')
            _blk(out, gid, f, u0 - .1, u1 + .1, v0 - .1, v1 + .1, y + hh - .16, .16, trim)
            if kind == 'stepped':
                for uu in (np.linspace(u0 + .3, u1 - .3, max(2, int((u1 - u0) / 1.6))) if detail else ()): _blk(out, gid, f, uu - .05, uu + .05, v0 - .06, v0, y + .3, hh - .7, trim)     # lames verticales dorées
            y += hh
        if kind == 'stepped':
            cx = W / 2; cz = D / 2
            _blk(out, gid, f, cx - .12, cx + .12, cz - .12, cz + .12, y, 4.2, trim, emissive=1.1 if night else 0.)
            for k, (dx, hh) in enumerate(((-.7, 1.4), (-.35, 1.9), (.35, 1.9), (.7, 1.4))):                                                                     # soleil levant : éventail d'ailerons
                _blk(out, gid, f, cx + dx - .05, cx + dx + .05, cz - .05, cz + .05, y, hh, trim)
            top = y + 4.2
        else: top = y
    elif kind in ('terrace', 'dome'):
        cornice(); parapet(.7, trim)
        if kind == 'dome':
            blue = I.get('blue_dome', (30, 100, 200)); r = min(W, D) * .36; cx, cz = W / 2, D / 2
            _blk(out, gid, f, cx - r - .3, cx + r + .3, cz - r - .3, cz + r + .3, H, .7, trim)
            n = 6
            for k in range(n):
                s = r * math.sqrt(max(.0, 1 - (k / n) ** 2)) + .15
                _blk(out, gid, f, cx - s, cx + s, cz - s, cz + s, H + .7 + k * .42, .43, blue if k % 2 == 0 else _sh(blue, .88))
            _blk(out, gid, f, cx - .08, cx + .08, cz - .08, cz + .08, H + .7 + n * .42, 1.1, (246, 240, 226))
            _blk(out, gid, f, cx - .35, cx + .35, cz - .05, cz + .05, H + .7 + n * .42 + .6, .1, (246, 240, 226))
            top = H + .7 + n * .42 + 1.1
        else:                                                                        # terrasse : pergola, plantes, auvent de toile
            for k in range(3 if detail else 0): _blk(out, gid, f, .3, W - .3, .5 + k * .9, .6 + k * .9, H + 2.2, .08, (110, 76, 50))
            for u in ((.4, W - .5) if detail else ()):
                for v in (.5, 2.2): _blk(out, gid, f, u, u + .1, v, v + .1, H + .7, 1.5, (110, 76, 50))
            for u in (np.linspace(.6, W - .6, 3) if detail else ()): _blk(out, gid, f, u - .3, u + .3, D - 1.4, D - .8, H + .7, .6, (176, 92, 60)); _blk(out, gid, f, u - .35, u + .35, D - 1.45, D - .75, H + 1.3, .5, (60, 160, 80), mat='fabric')
            top = H + .7
    else:                                                                            # flat
        cornice(); parapet(.8)
        cx, cz, sx, sz = f.box(.2, W - .2, .2, D - .2)
        out.append(dict(at=[cx, H - .02, cz], size=[sx, .03, sz], color=[52, 52, 56], material='flat', roof='tar', group=gid, seed=d['seed']))
        top = H
    return out, top


# ------------------------------------------------------------------------------------------------- un bâtiment complet
def build_ps1(d, night, detail=True):
    """-> (blocs, accessoires) d'un bâtiment. Le corps porte la texture ; le reste est géométrie (toit, corniche) et détails (props qt_*)."""
    f = Frame(d); gid = d['id']; I = Q.IDENTITES[d['ident']]
    W, D, H = d['W'], d['D'], d['H']
    cx, cz, sx, sz = f.box(0, W, 0, D)
    key = [d['ident'], int(d['id'][3:]), d['front'], list(d['rect']), bool(d['near']), int(d['seed']) // 1000, None]
    blocks = [dict(at=[round(cx, 3), 0, round(cz, 3)], size=[round(sx, 3), round(H - .02, 3), round(sz, 3)], color=list(d['body']), material='flat', group=gid,
                   facade={'style': 'qt', 'quartier': key, 'night': bool(night), 'lit': 0.})]
    rb, top = roof_blocks(d, f, gid, night, detail)
    blocks += rb
    props = []
    def prop(kind, u, y, v=0., **kw):
        x, z = f.pt(u, v); props.append(dict(type=kind, at=[round(x, 3), round(z, 3)], y=round(y, 3), rot=f.rot, group=gid, **kw))
    bw = W / d['bays']
    if detail:
        for fl, row in enumerate(d['cells']):
            y0 = d['fy'][fl]
            for b, cell in enumerate(row):
                u = (b + .5) * bw
                fl_ = cell.get('flat', ())
                if cell.get('bal') and 'bal' not in fl_:
                    bl = cell['bal']; prop('qt_balcony', u, y0, w=round(bl['w'], 2), slab=list(bl['slab']), rail=list(bl['rail']), bkind=bl['kind'], plants=bl['plants'], laundry=bl['laundry'])
                    if fl >= 1 and I['p'].get('dish') and cell.get('who', 0) == 4: prop('qt_blade', u, y0)
                if cell.get('ac') and 'ac' not in fl_ and cell['t'] == 'win': prop('qt_ac', u + (.55 if fl % 2 else -.55), y0 + .45)
                if cell.get('box') and 'box' not in fl_ and cell['t'] == 'win': prop('qt_windowbox', u, y0 + I['sill'] - .12, w=round(I['ww'] * 1.05, 2), flowers=[list(c) for c in cell['box']])
                if fl == 0:
                    if cell['t'] == 'shop':
                        w_ = bw - .3
                        prop('qt_fascia', u, y0 + d['gf'] - .95, w=round(w_, 2), text=cell['name'], col=list(cell['col']), night=night)
                        if cell.get('awn'): prop('qt_awning', u, y0 + 2.7, w=round(w_, 2), c1=list(cell['awn'][0]), c2=list(cell['awn'][1]))
                        if cell.get('blade') and b % 2 == 0: prop('qt_blade', u + bw / 2 - .2, y0 + 3.0, text=cell['blade'], col=list(cell['col']), night=night)
                    elif cell['t'] == 'door':
                        if d['stoop'] and not d['porch']: prop('qt_stoop', u, 0., v=0., w=round(I['ww'] * 1.3, 2), plant=bool(cell['lamp']))
                    elif cell['t'] == 'lobby' and d['canopy']: prop('qt_canopy', u, d['gf'] - .4, w=round(bw, 2))
                    elif cell['t'] == 'arch' and d['boug'] and b % 2 == 0: prop('qt_boug', u, 0., w=round(bw * .9, 2), h=2.4, seed=d['seed'] + b)
        if d['fire_bay'] is not None and d['floors'] >= 3:
            prop('qt_fire_escape', (d['fire_bay'] + .5) * bw, 0., n=d['floors'] - 1, fh=round(d['fh'], 2), y0=round(d['gf'] - d['fh'], 2), w=round(bw * .92, 2))
        if d['porch']: prop('qt_porch', (d['door_bay'] + .5) * bw, 0., swing=bool(d['seed'] % 2))
        for nv in d['neon_vert']: prop('qt_neon', nv['u'], nv['y'], text=nv['text'], col=list(nv['col']), h=round(nv['h'], 2), night=night)
    for ch in d['chimneys']:
        v = D * .4; x, z = f.pt(ch, v)
        props.append(dict(type='qt_chimney', at=[round(x, 3), round(z, 3)], y=round(H + (.2 if d['roof'] in ('flat', 'terrace', 'sawtooth') else (top - H) * .55), 3), group=gid, col=list(_sh(d['body'], .7) if I['kind'] != 'brick' else (150, 72, 54))))
    if d['roof'] in ('flat', 'terrace', 'stepped_glass', 'sawtooth') and detail:
        for (kind, uf, vf) in d['roof_objs']:
            if kind == 'chimney_stack': continue
            x, z = f.pt(uf * W, vf * D)
            props.append(dict(type=kind, at=[round(x, 3), round(z, 3)], y=round(top + (.0 if d['roof'] != 'terrace' else .1), 3), group=gid, size=1.0))
    return blocks, props


# ------------------------------------------------------------------------------------------------- les textures d'un bloc
def block_tex(bk):
    """(textures, émission) d'un bloc de façade de quartier : appelé par compose.block_textures quand le bloc porte `facade.quartier`"""
    ident, n, front, rect, near, seed, top = bk['facade']['quartier']
    night = bool(bk['facade'].get('night', True))
    d = Q.building(ident, n, front, tuple(rect), bool(near), int(seed), top)
    tex = {}
    for face, k in (('-z', 0), ('+z', 1), ('-x', 2), ('+x', 3)):
        role = 'front' if face == front else 'back' if face == {'+x': '-x', '-x': '+x', '-z': '+z', '+z': '-z'}[front] else 'side'
        tex[face] = _paint(ident, n, front, tuple(rect), bool(near), int(seed), top, role, night, k)
    return tex, (1.25 if night else 0.)


@functools.lru_cache(maxsize=256)
def _paint(ident, n, front, rect, near, seed, top, role, night, face):
    d = Q.building(ident, n, front, rect, near, seed, top)
    return F.paint(Q.plan_face(d, role, night), face, night)
