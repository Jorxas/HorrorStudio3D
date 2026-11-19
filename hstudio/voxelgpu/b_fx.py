"""Les effets V3 de PIXEL 3D (foudre, effondrement, objets et créatures en vol) dans le peintre VOXEL : versions NATIVES, adaptées, pas les boîtes de PIXEL 3D repeintes.

La LOGIQUE est celle de PIXEL 3D, appelée telle quelle (`effects.py` : même instant de départ, même chemin de l'éclair, mêmes graines et mêmes lois de chute des débris, même chemin
et même inclinaison du mobile via `mover_state`, mêmes lumières) : un personnage qui saute vers l'hélicoptère le trouve au même endroit dans les deux styles. Seul l'habillage change :

  * éclair       : une chaîne de cubes calés sur un réseau de 0,5 m (l'éclair d'un jeu de blocs), cœur blanc émissif, étincelles cubiques ;
  * effondrement : la tour est refaite en VOXEL (étages de blocs, fenêtres en cubes, liserés) ; chaque étage tient jusqu'à l'instant où le front de rupture le traverse (accessoire à `t1`), puis
                   se brise en gros blocs qui tombent (calque dynamique), avec poussière en bouffées cubiques translucides et braises ;
  * hélicoptère  : modèle VOXEL (carlingue en blocs ombrés, pare-brise en gradins, pale unique en boîte qui tourne, disque flou, queue en gradins), cabine à la même place que dans PIXEL 3D ;
  * dragon       : modèle VOXEL (corps en tiers, cou en gradins, cornes, yeux émissifs, épines, queue qui ondule, ailes à membrane articulées au battement de PIXEL 3D).

Sortie : des lignes `[x, y, z, w, h, d, couleur, émission, rx, ry, rz, opacité]` dans le repère de VOXEL (demi-tour et agrandissement K, comme `b_props`), lues par le calque dynamique du plan
(`stage.dyn`, voxelgpu_js/engine/b_kit.js). Un effet inconnu du catalogue (extension) passe par la conversion générique de ses boîtes, et le dit dans `LIMITS`.
Rien n'est aléatoire (graines de PIXEL 3D) ; rien n'est dessiné ici."""
import math
import numpy as np
from ..acting import rig
from . import b_props as BP

K = BP.PROP_SCALE
HALF = np.diag([-1., 1., -1.])               # le demi-tour de VOXEL (voir ps1_bake.to_voxel)
G = 9.81
LIMITS = []


def _hex(c):
    return (int(max(0, min(255, c[0]))) << 16) | (int(max(0, min(255, c[1]))) << 8) | int(max(0, min(255, c[2])))


def _euler(R):
    """matrice de rotation -> (rx, ry, rz) dans l'ordre XYZ de three.js (celui de `boxesGeometry`)"""
    m = np.asarray(R, float); y = math.asin(max(-1., min(1., m[0][2])))
    if abs(m[0][2]) < .9999999: return math.atan2(-m[1][2], m[2][2]), y, math.atan2(-m[0][1], m[0][0])
    return math.atan2(m[2][1], m[1][1]), y, 0.


def row(c, size, col, emis=0., R=None, alpha=1.):
    """une boîte (centre `c`, taille `size`, repère de PIXEL 3D, orientation monde `R` ou None) -> ligne du calque dynamique, repère de VOXEL"""
    rx = ry = rz = 0.
    if R is not None: rx, ry, rz = _euler(HALF @ np.asarray(R, float))
    return [round(-K * float(c[0]), 3), round(K * float(c[1]), 3), round(-K * float(c[2]), 3), round(K * float(size[0]), 3), round(K * float(size[1]), 3), round(K * float(size[2]), 3),
            _hex(col), round(float(emis), 2), round(rx, 3), round(ry, 3), round(rz, 3), round(float(alpha), 2)]


def light(lp, col, pw, rad):
    """lumière de PIXEL 3D (position, couleur 0..1, puissance, rayon) -> [x, y, z, couleur, intensité, portée] de VOXEL (même gain que `from_ps1`)"""
    d = BP.light_to_voxel(lp, col, pw, rad, gain=2.2); return [*d['at'], d['color'], d['i'], d['dist']]


def _snap(v, q): return round(float(v) / q) * q


def as_box(r):
    """ligne du calque dynamique -> boîte d'un accessoire `bset` (b_kit.js) : {x, y, z, w, h, d, color, emis, rx, ry, rz}"""
    o = dict(x=r[0], y=r[1], z=r[2], w=r[3], h=r[4], d=r[5], color=r[6])
    if r[7]: o['emis'] = r[7]
    for k, v in zip(('rx', 'ry', 'rz'), r[8:11]):
        if v: o[k] = v
    return o


# ------------------------------------------------------------------ éclair : cubes sur un réseau de 0,5 m
def lightning(fx, o):
    from ..engines.pixel3d import effects as FX
    dt = fx.since(o)
    if dt < 0 or dt > 1.2: return [], []
    tgt = fx.point(o.get('to'), 0.)
    src = o.get('from') or [tgt[0] + float(o.get('drift', 6.)), tgt[1] + float(o.get('height', 45.)), tgt[2] + float(o.get('drift', 6.)) * .5]
    seed = int(o.get('seed', 7)); out = []; L = []
    on = dt < .08 or .13 < dt < .3 or .36 < dt < .4
    Q = .5
    if on and dt < float(o.get('dur', .45)):
        core = tuple(o.get('color', (225, 235, 255))); w = max(Q, float(o.get('width', .5)) * 1.1)
        pts = FX._bolt(src, tgt, seed)                          # le même tracé que PIXEL 3D (même graine)
        def chain(pp, ww, em):
            seen = set()
            for a, b in zip(pp[:-1], pp[1:]):
                n = max(1, int(float(np.linalg.norm(b - a)) / (ww * .9)))
                for k in range(n + 1):
                    p = a + (b - a) * (k / n); cell = tuple(int(round(float(v) / Q)) for v in p)
                    if cell in seen: continue
                    seen.add(cell); out.append(row([c * Q for c in cell], (ww, ww, ww), core, em))
        chain(pts, w, 4.)
        rng = np.random.default_rng(seed + 1)
        for k in range(int(o.get('branches', 2))):
            i = int(rng.integers(2, len(pts) // 2)); p = pts[i]; q = p + np.array([rng.uniform(-6, 6), -rng.uniform(4, 9), rng.uniform(-6, 6)], np.float32)
            chain(FX._bolt(p, q, seed + 10 + k, .22, 3), w * .6, 3.)
        mid = pts[len(pts) // 2]
        L += [light((tgt[0], tgt[1] + 2.5, tgt[2]), (.78, .84, 1.), 9., 28.), light((float(mid[0]), float(mid[1]), float(mid[2])), (.7, .78, 1.), 6., 45.)]
    rng = np.random.default_rng(seed + 3)
    for k in range(int(o.get('sparks', 26))):
        v = np.array([rng.uniform(-4, 4), rng.uniform(1, 6), rng.uniform(-4, 4)]); p = np.array(tgt) + v * dt + np.array([0, -.5 * G * dt * dt, 0])
        if dt < rng.uniform(.4, 1.1): out.append(row([_snap(p[0], .1), _snap(p[1], .1), _snap(p[2], .1)], (.12, .12, .12), (255, 190, 90), 3.))
    if dt < .9: L.append(light((tgt[0], tgt[1] + .5, tgt[2]), (1., .55, .25), 2.5 * (1 - dt / .9), 8.))
    return out, L


# ------------------------------------------------------------------ effondrement : tour en étages de blocs, front de rupture, gros blocs qui tombent
def _facade_rows(x0, z0, x1, z1, y_lo, y_hi, base, st, lit, seed, night):
    """fenêtres en cubes d'une tour, pour les étages dont le centre tombe dans [y_lo, y_hi) ; rangées [centre, taille, couleur, émission]"""
    out = []; w, d = x1 - x0, z1 - z0; fl = st['floor']; wh = fl * st['wh']
    faces = ((0, w, lambda b, bays: (x0 + (b + .5) * w / bays, z0 - .03), 'x'), (1, w, lambda b, bays: (x0 + (b + .5) * w / bays, z1 + .03), 'x'),
             (2, d, lambda b, bays: (x0 - .03, z0 + (b + .5) * d / bays), 'z'), (3, d, lambda b, bays: (x1 + .03, z0 + (b + .5) * d / bays), 'z'))
    for face, span, pos, ax in faces:
        bays = max(1, int(span // st['bay'])); ww = span / bays * st['ww']
        for f in range(max(1, int((float(y_hi) - base) // fl) + 2)):
            yc = base + f * fl + fl * .32 + wh / 2
            if not (y_lo <= yc < y_hi): continue
            h_row = ((f * 2654435761 + face * 40503 + seed * 9973) & 0xffff) / 65535.; rowlit = h_row < .35
            for b in range(bays):
                h = ((f * 73856093) ^ (b * 19349663) ^ (face * 83492791) ^ (seed * 2654435761)) & 0xffff; h = h / 65535.
                on = night and h < lit * (1.8 if rowlit else .7); x, z = pos(b, bays)
                size = (ww, wh, .1) if ax == 'x' else (.1, wh, ww)
                out.append(([x, yc, z], size, tuple(int(c * .82) for c in st['win']) if on else st['dark'], .6 if on else 0.))        # allumée sous le seuil du bloom : sinon la tour devient un bloc blanc
    return out


def _tower_boxes(lo, hi, col, style, lit, seed, night, y_lo, y_hi, base, band):
    """un tronçon [y_lo, y_hi] de la tour VOXEL : bloc plein (teinte alternée par étage), liseré en saillie, fenêtres en cubes -> lignes dans le repère de VOXEL"""
    from ..engines.pixel3d.compose import STYLES
    st = STYLES.get(style, STYLES['office']); x0, z0, x1, z1 = float(lo[0]), float(lo[2]), float(hi[0]), float(hi[2])
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2; k = .94 + .06 * (band % 2); c = tuple(int(v * k) for v in col)
    out = [row([cx, (y_lo + y_hi) / 2, cz], (x1 - x0, y_hi - y_lo, z1 - z0), c)]
    out.append(row([cx, y_lo + .07, cz], (x1 - x0 + .2, .14, z1 - z0 + .2), tuple(int(v * .78) for v in col)))
    for cxy, size, wc, em in _facade_rows(x0, z0, x1, z1, y_lo, y_hi, base, st, lit, seed, night): out.append(row(cxy, size, wc, em))
    return out


def collapse_plan(body, par):
    """(couches [(y bas, y haut, instant de rupture absolu)], y d'arrêt) : les étages de PIXEL 3D, du haut vers le bas ; le front de rupture traverse le centre de l'étage à son instant"""
    lo, hi = body.lo, body.hi; Hh = float(hi[1] - lo[1]); dur = float(par.get('dur', 6.)); stop = float(lo[1]) + Hh * float(par.get('remain', .35)); ch = float(par.get('chunk', 2.4))
    layers = []; y = float(hi[1])
    while y - ch > stop - 1e-3:
        yb = y - ch; yc = (y + yb) / 2; ts = float(par['ta']) + dur * ((float(hi[1]) - yc) / max(1e-3, float(hi[1]) - stop)) ** (1 / 1.25)
        layers.append((yb, y, ts)); y = yb
    return layers, y


def tower_props(bset, spec, gid, par):
    """les accessoires statiques de la tour qui s'effondre : un `bset` par étage (visible jusqu'à `t1` = sa rupture), le socle qui reste, et l'ancien mobilier de toit (parti avec le premier étage)"""
    from . import b_sets as BS
    st = bset.st; idx = (getattr(st, 'groups', {}) or {}).get(gid, []); boxes = [st.base.boxes[i] for i in idx]
    if not boxes: return []
    body = max(boxes, key=lambda b: float(b.hi[1] - b.lo[1]) * float((b.hi[0] - b.lo[0]) * (b.hi[2] - b.lo[2])))
    el = next((e for e in (spec.get('elements') or []) if isinstance(e, dict) and e.get('id') == gid), {})
    style = el.get('style', 'office'); lit = float(el.get('lit', .35)); seed = int(el.get('seed', 3)); night = bool(spec.get('night', spec.get('sky', 'night') in ('night', 'storm')))
    col = tuple(int(v) for v in (body.col * 255)); base = float(body.lo[1]); layers, ybot = collapse_plan(body, par); props = []
    for k, (yb, yt, ts) in enumerate(layers):
        props.append(dict(type='bset', boxes=[as_box(r) for r in _tower_boxes(body.lo, body.hi, col, style, lit, seed, night, yb, yt, base, k)], t1=round(ts, 3)))
    props.append(dict(type='bset', boxes=[as_box(r) for r in _tower_boxes(body.lo, body.hi, col, style, lit, seed, night, base, ybot, base, len(layers))]))                 # le socle reste debout
    rest = [BS._copy_box(b) for b in boxes if b is not body]
    if rest:
        p = BP.boxes_to_bset(rest, 0, 0., 0., 0., K, {}); p['t1'] = round(float(par['ta']) + .35, 3); props.append(p)
    return props


def collapse(fx, o):
    """gros blocs qui tombent (mêmes lois que PIXEL 3D : mêmes graines, mêmes vitesses, même sol), poussière en bouffées, braises au front de rupture"""
    from ..engines.pixel3d.effects import _rot
    dt = fx.since(o); t0 = fx.T - dt
    gid = o.get('target'); boxes = fx.group_boxes(gid)
    if dt < 0 or not boxes: return [], []
    fx.hide(gid)
    body = max(boxes, key=lambda b: float(b.hi[1] - b.lo[1]) * float((b.hi[0] - b.lo[0]) * (b.hi[2] - b.lo[2])))
    lo, hi = body.lo, body.hi; Hh = float(hi[1] - lo[1]); dur = float(o.get('dur', 6.)); stop = float(lo[1]) + Hh * float(o.get('remain', .35))
    floor = float(getattr(fx.st.base, 'floor_y', 0.)); front = float(hi[1]) - (float(hi[1]) - stop) * min(1., dt / dur) ** 1.25
    out = []; L = []
    lean = np.array(o.get('lean', [0., 1.]), np.float32); lean = lean / (np.linalg.norm(lean) + 1e-6)
    rng = np.random.default_rng(int(o.get('seed', 5))); ch = float(o.get('chunk', 2.4))
    w, d = float(hi[0] - lo[0]), float(hi[2] - lo[2]); col = body.col * 255; cx, cz = float(lo[0] + hi[0]) / 2, float(lo[2] + hi[2]) / 2
    layer = 0; y = float(hi[1])
    while y - ch > stop - 1e-3:
        yb = y - ch; yc = (y + yb) / 2; ts = t0 + dur * ((float(hi[1]) - yc) / max(1e-3, float(hi[1]) - stop)) ** (1 / 1.25)     # = l'instant de rupture de l'étage (voir collapse_plan)
        nx, nz = (2, 2) if layer % 2 == 0 else (3, 2)
        for i in range(nx):
            for j in range(nz):
                k = rng.random(12)
                if fx.T < ts: continue
                sx, sz = _snap(w / nx * (.75 + .25 * k[0]), .25), _snap(d / nz * (.75 + .25 * k[1]), .25); sy = max(.5, _snap(ch * (.6 + .4 * k[2]), .25))
                p0 = np.array([float(lo[0]) + w * (i + .5) / nx, yb + ch / 2, float(lo[2]) + d * (j + .5) / nz], np.float32)
                out_dir = np.array([p0[0] - cx, 0, p0[2] - cz], np.float32)
                v = np.array([lean[0] * (1 + 3 * k[3]) + out_dir[0] * .4 * k[4], 1.5 * k[5] - .5, lean[1] * (1 + 3 * k[3]) + out_dir[2] * .4 * k[4]], np.float32)
                tt = fx.T - ts; tl = (v[1] + math.sqrt(max(0., v[1] ** 2 + 2 * G * (p0[1] - floor - sy / 2)))) / G
                te = min(tt, tl); p = p0 + v * te + np.array([0, -.5 * G * te * te, 0], np.float32)
                wsp = (k[6:9] - .5) * 3.; R = _rot(*(wsp * te)); shade = .85 + .3 * k[9]
                cc = tuple(int(min(255, (c * .75 + 90 * .25) * shade * 1.35)) for c in col)
                out.append(row(p, (sx, sy, sz), cc, 0., R))
                if tt < 2.2:                                              # braise accrochée au bloc qui vient de se rompre : il se lit sur le ciel de nuit
                    out.append(row(p + np.asarray(R, float) @ np.array([sx * .3, sy * .5 + .1, 0.]), (.45, .45, .45), (255, 150, 60), 2.6 * (1. - tt / 2.2)))
                lit_win = k[10] < .22                                     # une fenêtre en cube sur une face du bloc : allumée (22 %) ou sombre
                wc = np.asarray(R, float) @ np.array([0., 0., sz / 2 + .04])
                out.append(row(p + wc, (min(sx, 1.), min(sy, 1.), .12), (255, 214, 150) if lit_win else (28, 38, 58), 1.6 * max(0., 1. - tt / 3.) if lit_win else 0., R))
                for q in range(2):                                        # poussière derrière le bloc : bouffées cubiques translucides
                    age = tt - .15 * q
                    if 0 < age < 2.5:
                        dp = p0 + v * min(age, tl) * .6 + np.array([0, -.25 * G * min(age, tl) ** 2, 0], np.float32); s_ = _snap(.8 + 1.5 * age, .25)
                        out.append(row(dp, (s_, s_ * .8, s_), (176, 172, 164), 0., None, 1. - min(.92, .4 + .2 * age)))
        y = yb; layer += 1
    if dt < dur + 1.5:                                                    # braises et lueur au front de rupture
        flick = .7 + .3 * math.sin(fx.g * 23) * math.sin(fx.g * 9)
        L.append(light((cx, front, cz), (1., .5, .2), 2.2 * flick, 14.))
        for k in range(14):
            a = k * 2.4 + fx.g * 3; r = .5 + (k % 3) * .5
            out.append(row([_snap(cx + math.cos(a) * w * .45, .1), _snap(front + .3 * math.sin(fx.g * 7 + k), .1), _snap(cz + math.sin(a) * d * .45, .1)], (.3, .3, .3), (255, 170, 70), 3.))
    for k in range(10):                                                   # la nappe qui monte de la rue
        age = dt - .8 - k * .3
        if age > 0:
            s_ = _snap(2 + 2.2 * age, .25); a = k * 1.9
            out.append(row([cx + math.cos(a) * (w * .4 + age), floor + s_ * .4, cz + math.sin(a) * (d * .4 + age)], (s_, s_ * .7, s_), (160, 156, 148), 0., None, 1. - min(.9, .4 + .08 * age)))
    return out, L


# ------------------------------------------------------------------ modèles VOXEL des objets et créatures en vol
def P(x, y, z, w, h, d, col, emis=0., rot=None, a=1.): return ([x, y, z], (w, h, d), col, emis, rot, a)


def place(parts, p, R, size=1.):
    R = np.eye(3) if R is None else np.asarray(R, float); p = np.asarray(p, float); out = []
    for (c, s, col, emis, rl, a) in parts:
        Rw = R if rl is None else R @ np.asarray(rl, float)
        out.append(row(R @ (np.asarray(c, float) * size) + p, [v * size for v in s], col, emis, Rw, a))
    return out


def _shade(c, k): return tuple(int(max(0, min(255, v * k))) for v in c)


def helicopter(t, col=None):
    """hélicoptère VOXEL, repère local de PIXEL 3D (origine au plancher de la cabine, nez vers +z, porte gauche ouverte) : la cabine est à la même place que celle de PIXEL 3D"""
    body = tuple(col) if col else (196, 36, 36); top = _shade(body, 1.14); under = _shade(body, .66); dark = _shade(body, .55); metal = (50, 52, 56); glass = (46, 70, 96); white = (236, 236, 236)
    m = []
    for x in (-.85, .85): m += [P(x, -.85, .25, .1, .1, 3.3, metal), P(x, -.7, 1.95, .1, .3, .1, metal), P(x, -.7, -1.45, .1, .3, .1, metal)]                         # patins relevés
    m += [P(x * .78, -.45, z, .08, .8, .08, metal) for x in (-1, 1) for z in (-.7, 1.1)]
    m += [P(0, -.22, .3, 1.84, .45, 3.4, under), P(0, .02, .3, 1.84, .1, 3.4, _shade(body, .85))]                                                                          # ventre en deux tons
    m += [P(.93, .8, .1, .08, 1.6, 2.8, body), P(.975, 1.05, -.6, .02, .55, .8, glass), P(.975, 1.05, .75, .02, .55, .8, glass), P(.975, .62, .1, .02, .2, 2.8, white)]    # paroi droite, hublots, bande
    m += [P(-.93, .8, 1.25, .08, 1.6, .26, body), P(-.93, .8, -1.2, .08, 1.6, .32, body), P(0, .8, -1.42, 1.84, 1.6, .1, body), P(0, 1.66, .1, 1.92, .12, 3.0, top)]              # montants (porte gauche ouverte), cloison, toit
    m += [P(0, .62, 2.12, 1.72, .75, .9, glass, 0., None, .8), P(0, 1.22, 1.92, 1.72, .5, .55, glass, 0., None, .8), P(0, 1.55, 1.7, 1.72, .14, .5, top)]                                      # pare-brise en gradins
    m += [P(0, .3, 2.62, 1.4, .7, .5, body), P(0, .22, 2.98, .9, .5, .3, under), P(0, 1.96, -.45, 1.0, .5, 1.6, dark), P(0, 2.0, -1.4, .8, .36, .5, dark)]                       # nez, moteur
    for i, (z, w, h) in enumerate(((-2.4, .62, .62), (-3.3, .52, .54), (-4.2, .44, .46), (-5.0, .36, .38))): m.append(P(0, 1.2 - i * .04, z, w, h, .95, body if i % 2 == 0 else top))   # queue en gradins
    m += [P(0, 1.65, -5.35, .1, 1.0, .6, body), P(0, 2.3, -5.55, .1, .5, .35, dark), P(0, 1.18, -4.95, 1.3, .08, .42, dark)]                                                  # dérive et plan fixe
    m += [P(0, .15, .1, 1.7, .02, 2.6, (60, 62, 66)), P(0, .5, -1.05, 1.5, .5, .5, (40, 40, 46)), P(-.55, .62, -1.05, .5, .12, .46, (90, 70, 56))]                              # plancher, banquette
    m += [P(0, 2.32, -.35, .14, .32, .14, (90, 92, 98)), P(0, 2.5, -.35, .38, .14, .38, dark)]
    ang = t * 2 * math.pi * 2.4                                                                                                                                            # pale unique en boîte, qui tourne (2,4 tr/s : 36° par image à 24 i/s)
    for k in (0, 1): m.append(P(0, 2.56, -.35, 9.6, .05, .3, (38, 38, 42), rot=rig.rot_y(ang + k * math.pi / 2)))
    for k in (0, 1): m.append(P(0, 2.54, -.35, 10., .02, 10., (200, 205, 215), rot=rig.rot_y(k * math.pi / 4), a=.1))                                                         # disque flou
    m.append(P(.28, 1.72, -5.4, .05, 1.1, .12, (38, 38, 42), rot=rig.rot_x(t * 2 * math.pi * 3.1)))
    m += [P(-1.0, 1.0, 1.35, .14, .14, .14, (255, 40, 40), 3.), P(1.0, 1.0, 1.35, .14, .14, .14, (40, 255, 90), 3.), P(0, -.42, 2.45, .36, .22, .36, (255, 250, 220), 3.5)]
    if int(t * 2.5) % 3 == 0: m.append(P(0, 2.05, -5.6, .16, .16, .16, (255, 255, 255), 4.))
    return m


HELI_LIGHTS = [((0, -.7, 3.2), (1., .96, .86), 3.2, 16.), ((0, 1.35, .1), (.9, .95, 1.), .7, 3.2)]


def dragon(t, col=None):
    """dragon VOXEL en vol (repère local de PIXEL 3D : nez vers +z, corps à y ≈ 1,3) : même battement que PIXEL 3D (0,8 Hz), ailes à bras et panneaux de membrane articulés à l'épaule"""
    c = tuple(col) if col else (170, 40, 40); dk = _shade(c, .7); lt = _shade(c, 1.2); belly = (214, 176, 126); bone = (230, 220, 190); ph = t * 2 * math.pi * .8; flap = math.sin(ph)
    m = [P(0, 1.5, 0, .9, .36, 2.2, c), P(0, 1.2, 0, 1.0, .46, 2.3, c), P(0, .95, .05, .8, .24, 2.0, belly)]
    m += [P(x, 1.0, z, .22, .3, .5, dk) for x in (-.35, .35) for z in (.6, -.7)]
    for i in range(5): m.append(P(0, 1.45 + i * .12, 1.15 + i * .28, .42 - .02 * i, .34, .34, c if i % 2 else lt))                                                             # cou en gradins
    m += [P(0, 2.05, 2.65, .52, .46, .85, c), P(0, 1.84, 2.78, .44, .14, .7, dk), P(0, 2.0, 3.1, .34, .24, .22, lt)]                                                        # tête, mâchoire, museau
    for x in (-1, 1): m += [P(x * .18, 2.14, 3.0, .1, .1, .08, (255, 200, 40), 2.4), P(x * .2, 2.42, 2.35, .08, .32, .08, bone), P(x * .24, 2.66, 2.2, .07, .22, .07, bone)]     # yeux, cornes
    m += [P(0, 1.78 + (.02 if i % 2 else 0), -.9 + i * .3, .1, .22, .2, dk) for i in range(8)]                                                                           # épines
    for i in range(8):
        wv = math.sin(ph - i * .6) * .25 * i / 8
        m.append(P(wv, 1.3 - i * .04, -1.2 - i * .38, .3 - i * .025, .24, .4, c if i % 2 else dk))                                                                       # queue qui ondule
    m.append(P(math.sin(ph - 8 * .6) * .25, 1.0, -4.45, .5, .1, .5, bone))
    th = flap * .5
    for x in (-1, 1):
        s = x * 1.; ct, st_ = math.cos(th), math.sin(th); sh = (x * .5, 1.55, .3)
        def at(r, dz=0.): return [x * r * ct + sh[0] * 0, sh[1] + r * st_, sh[2] + dz]
        rz = rig.rot_z(x * th)
        for i in range(5):                                                                                                                                                # panneaux de membrane
            r = .75 + i * .62; cc = at(r, -i * .12 - .1)
            m.append(([cc[0] + (0 if x > 0 else 0), cc[1], cc[2]], (.66, .07, 1.5 - i * .2), dk if i else c, 0., rz, 1.))
        for i in range(4):                                                                                                                                                # bras et doigts : os en tête d'aile
            r = .6 + i * .75; cc = at(r, .35 - i * .06)
            m.append(([cc[0], cc[1], cc[2]], (.78, .12, .12), bone if i else c, 0., rz, 1.))
        cc = at(.75 + 4 * .62 + .35, -.2); m.append(([cc[0], cc[1], cc[2]], (.12, .12, .5), bone, 0., rz, 1.))
    return m


def mover(fx, o):
    """un objet ou une créature qui suit un chemin 3D : même chemin et mêmes inclinaisons que PIXEL 3D, modèle VOXEL quand il existe (hélicoptère, dragon), sinon la conversion de ses boîtes"""
    from ..engines.pixel3d import effects as FX
    p, R, vis = FX.mover_state(o, fx.T)
    if not vis or not o.get('thing'): return [], []
    thing = str(o['thing']); size = float(o.get('size', 1.)); col = tuple(o['color']) if o.get('color') else None
    if thing == 'prop:assemblage':
        # These are already plain coloured volumes. Use the shared transform and
        # paint native dynamic cubes; there is no PS1 surface image to copy.
        bx, lt = FX.mover(fx, o)
        return boxes_rows(bx), [light(*l[:4]) for l in lt]
    if thing == 'prop:helicopter': parts = helicopter(fx.g, col); lk = float(o.get('light_power', 1.)); lts = [light(R @ (np.asarray(lp, np.float32) * size) + p, c_, pw * lk, rad) for (lp, c_, pw, rad) in HELI_LIGHTS]
    elif thing == 'creature:dragon' and o.get('posture', 'fly') == 'fly': parts = dragon(fx.g, col); lts = []
    else: return _generic(fx, o)
    return place(parts, p, R, size), lts


# ------------------------------------------------------------------ repli : les boîtes de PIXEL 3D d'un effet sans modèle VOXEL
def boxes_rows(boxes):
    """boîtes de PIXEL 3D (éventuellement dans un repère tourné) -> lignes du calque dynamique"""
    out = []
    for b in boxes:
        if getattr(b, 'hidden', False): continue
        lo, hi = np.asarray(b.lo, float), np.asarray(b.hi, float); c = (lo + hi) / 2; R = None
        if b.inst is not None: R = np.asarray(b.inst.R, float); c = R @ c + np.asarray(b.inst.piv, float)
        out.append(row(c, hi - lo, tuple(b.col * 255), float(b.emis or 0.), R, 1. - float(getattr(b, 'dissolve', 0.) or 0.)))
    return out


def _generic(fx, o):
    from ..engines.pixel3d import effects as FX
    typ = o.get('type'); msg = f"effet « {typ} » : boîtes de PIXEL 3D reprises sans version VOXEL native"
    if msg not in LIMITS: LIMITS.append(msg)
    bx, lt = FX.EFFECTS[typ](fx, o)
    return boxes_rows(bx), [light(*l[:4]) for l in lt]


NATIVE = {'lightning_bolt': lightning, 'collapse': collapse, 'mover': mover}


def sounds(shot, t_shot=0.):
    """[(t, nom, gain, durée)] des sons des effets V3 d'un plan, t en secondes depuis son début : la table de PIXEL 3D (`effects.sounds`), inchangée"""
    from ..engines.pixel3d import effects as FX
    return FX.sounds(shot, t_shot) if has_v3(shot) else []


def has_v3(shot):
    from ..engines.pixel3d import effects as FX
    return any(o.get('type') in FX.EFFECTS for o in (shot.get('objects') or []))


def frame(ctx, shot, st, actors, cam, T, u, g):
    """les effets V3 d'un plan à l'instant g -> (lignes, lumières) du calque dynamique"""
    from ..engines.pixel3d import effects as FX
    fx = FX.Fx(ctx, shot, st, actors, cam, T, u, g); rows = []; lts = []
    for o in shot.get('objects') or []:
        typ = o.get('type')
        if typ not in FX.EFFECTS: continue
        r, l = NATIVE.get(typ, _generic)(fx, o); rows += r; lts += l
    return rows, lts


def collapse_targets(baked):
    """{nom du lieu: {id d'élément: paramètres}} de tous les effondrements de l'épisode (instant de départ absolu `ta`) : le lieu les refait lui-même (b_sets.get(hide_groups=...))"""
    out = {}
    for bs in baked:
        for o in bs.shot.get('objects') or []:
            if o.get('type') != 'collapse' or not o.get('target'): continue
            ta = float(o['at_abs']) if o.get('at_abs') is not None else bs.t0 + float(o.get('at', 0.))
            par = dict(o, ta=ta); cur = out.setdefault(bs.set_name, {}).setdefault(o['target'], par)
            if par['ta'] < cur['ta']: out[bs.set_name][o['target']] = par
    return out


# ------------------------------------------------------------------ mise en page de PIXEL 3D
def wants_mirror(ep):
    """vrai si l'image VOXEL doit être retournée de gauche à droite pour retrouver la mise en page de PIXEL 3D : le demi-tour de `ps1_bake.to_voxel` change la main du repère (PIXEL 3D : main gauche,
    x vers la droite de l'image ; three.js : main droite), donc un personnage à droite en PIXEL 3D est à gauche en VOXEL (mesuré sur demo8 : Léa u = +0,09 contre -0,07).
    Clé d'épisode `voxel_mirror` (true / false) ; par défaut, vrai seulement pour les épisodes à lieux composés (V3, nouveaux : aucun film déjà fait n'en a) ; les autres gardent leur contrat à l'identique."""
    v = ep.get('voxel_mirror')
    if v is not None: return bool(v)
    return any(isinstance(sp, dict) and sp.get('type') in ('composed', 'theatre_bal') for sp in (ep.get('sets') or {}).values())       # + le théâtre (31/10/2026 : nouveau, aucun film déjà fait)


def _flip_png(d):
    import base64
    a = np.frombuffer(base64.b64decode(d['rgba']), np.uint8).reshape(int(d['th']), int(d['tw']), 4)[:, ::-1]
    return dict(d, rgba=base64.b64encode(np.ascontiguousarray(a).tobytes()).decode('ascii'))


def mirror_text_props(props):
    """en mode `mirror`, les images de face et à plat (enseignes, mots sur un comptoir) sont écrites à l'envers : l'image retournée les relit à l'endroit"""
    for p in props or []:
        if isinstance(p, dict) and p.get('type') == 'bset':
            if p.get('decals'): p['decals'] = [_flip_png(d) for d in p['decals']]
            if p.get('flats'): p['flats'] = [_flip_png(d) for d in p['flats']]


# ------------------------------------------------------------------ lieux composés : le dessus des falaises
SAND = ((100, 86, 64), (128, 110, 84), (152, 132, 100), (92, 88, 84))                  # terre foncée, sable, sable clair, éclat de roche


def rock_tops(spec):
    """le dessus des éléments `building`/`tower` de style `rock` d'un lieu composé, en version VOXEL : une plaque de sable et de terre au grain de cubes (blocs de 0,3 m, deux échelles de bruit).
    PIXEL 3D les montre en pierre grenue qui rend beige ; une couleur unie aurait l'air d'un parking. Déterministe (graine de l'élément)."""
    from . import b_sets as BS
    out = []
    for e in (spec.get('elements') or []):
        if not isinstance(e, dict) or e.get('kind') not in ('building', 'tower') or e.get('style') != 'rock': continue
        x0, z0, x1, z1 = (float(v) for v in e['rect']); x0, x1, z0, z1 = min(x0, x1), max(x0, x1), min(z0, z1), max(z0, z1); top = float(e.get('top', 0.))
        vx0, vx1, vz0, vz1 = -K * x1, -K * x0, -K * z1, -K * z0; w, d = vx1 - vx0, vz1 - vz0
        tw = int(min(512, max(8, round(w / .3)))); th = int(min(512, max(8, round(d / .3)))); rng = np.random.default_rng(int(e.get('seed', 0)) * 31 + 91)
        fine = np.kron(rng.random((th // 2 + 2, tw // 2 + 2)), np.ones((2, 2)))[:th, :tw]; coarse = np.kron(rng.random((th // 4 + 2, tw // 4 + 2)), np.ones((4, 4)))[:th, :tw]
        v = .6 * fine + .4 * coarse; idx = np.where(v < .30, 0, np.where(v > .72, 2, 1)); idx = np.where((fine > .96), 3, idx)
        alb = np.asarray(SAND, np.float32)[idx] / 255.                              # rangée 0 = z le plus grand, comme `BSet._floor`
        tw_, th_, b64 = BS._png(alb[::-1])
        out.append(dict(type='bset', boxes=[], planes=[dict(x=round((vx0 + vx1) / 2, 3), y=round(K * top + .02, 3), z=round((vz0 + vz1) / 2, 3), w=round(w, 3), d=round(d, 3), tw=tw_, th=th_, rgba=b64)]))
    return out
