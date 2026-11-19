"""Le THÉÂTRE de bal, VERSION VOXEL NATIVE (règle des deux versions : docs/REGLE_DEUX_VERSIONS.md ; version PS1 : engines/pixel3d/theatre.py).

Le PLAN (`theatre.plan()` : poteaux, galeries, escaliers, tables, bougies, lanternes, cordages, projecteurs) est commun ; l'exécution est en BLOCS :
  * le mur du fond est fait de briques en relief (trois tons, suie vers le haut), pas d'une texture ;
  * le plancher est fait de lames (boîtes) ; le plateau tournant est deux anneaux de lames posés sur des pivots qui tournent (accessoire `btheatre`) ;
  * escaliers, limons, croix de Saint-André et mains courantes sont de vraies poutres inclinées ;
  * flammes, vitres de lanternes et lentilles des projecteurs sont des matières lumineuses PILOTÉES image par image (scintillement, gradateur, rideau de lumière) ;
  * les faisceaux du rideau et de la poursuite sont des cônes de lumière additifs (« brume »), les flaques au sol des disques additifs.
Rien n'est repeint depuis la version PS1 : seules les POSITIONS et les COULEURS viennent du plan.

Repère : celui de VOXEL (demi-tour + agrandissement K de b_sets) : x -> -K x, z -> -K z, y -> K y.
`native_bsets()` rend les accessoires (statique `bset` + dynamique `btheatre`) ; `frame_row(rec)` rend une image de lumière (stage.theatre.frames).
"""
import functools, math
import numpy as np
from ..engines.pixel3d import theatre as TH, stage_light as SL
from . import b_props as BP

K = BP.PROP_SCALE


def _hex(c):
    c = [int(max(0, min(255, round(v)))) for v in c[:3]]; return (c[0] << 16) | (c[1] << 8) | c[2]


def _sh(c, f): return tuple(max(0., min(255., v * f)) for v in c)


class Out:
    """boîtes VOXEL écrites depuis le repère PIXEL 3D"""
    def __init__(self): self.b = []

    def box(self, lo, hi, col, emis=0.):
        lo = np.asarray(lo, float); hi = np.asarray(hi, float); c = (lo + hi) / 2; s = np.abs(hi - lo)
        if (s <= 1e-5).any(): return
        o = dict(x=round(-K * c[0], 4), y=round(K * c[1], 4), z=round(-K * c[2], 4), w=round(K * s[0], 4), h=round(K * s[1], 4), d=round(K * s[2], 4), color=_hex(col))
        if emis: o['emis'] = emis
        self.b.append(o)

    def beam(self, p0, p1, w, h, col):
        """poutre inclinée entre deux points (repère PIXEL 3D) : rotation d'Euler XYZ de three.js"""
        p0 = np.asarray(p0, float); p1 = np.asarray(p1, float); c = (p0 + p1) / 2; d = p1 - p0; L = float(np.linalg.norm(d)); d = d / max(L, 1e-9)
        dv = np.array([-d[0], d[1], -d[2]])
        o = dict(x=round(-K * c[0], 4), y=round(K * c[1], 4), z=round(-K * c[2], 4), color=_hex(col))
        if abs(dv[2]) >= abs(dv[0]):                   # surtout le long de z : longueur sur z local
            o.update(w=round(K * w, 4), h=round(K * h, 4), d=round(K * L, 4), rx=round(math.atan2(-dv[1], dv[2]), 5), ry=round(math.asin(max(-1., min(1., dv[0]))), 5))
        else:                                           # surtout le long de x : longueur sur x local
            o.update(w=round(K * L, 4), h=round(K * h, 4), d=round(K * w, 4), ry=round(math.atan2(-dv[2], dv[0]), 5), rz=round(math.asin(max(-1., min(1., dv[1]))), 5))
        self.b.append(o)


R = np.random.default_rng


def _brick_wall(o):
    """le mur du fond en briques EN RELIEF : plaque de joint + briques à trois tons (suie vers le haut), porte sombre au centre"""
    r = R(7); z0 = TH.BACK; X = TH.WALL_X
    o.box((-X, 0, z0 + .02), (X, TH.WALL_H, z0 + TH.WALL_T), TH.MORTAR)
    bw, bh, gap = .44, .19, .06
    y = 0.; row = 0
    while y < TH.WALL_H - .05:
        off = 0. if row % 2 == 0 else (bw + gap) / 2; x = -X - off
        soot = .55 + .45 * max(0., min(1., 1.2 - y / TH.WALL_H * 1.1))
        while x < X:
            x0, x1 = max(-X, x), min(X, x + bw)
            if x1 - x0 > .08 and not (-.74 < (x0 + x1) / 2 < .74 and y < 2.7):
                k = r.uniform(.62, 1.15) * soot; t = r.choice(3, p=[.6, .28, .12])
                c = np.array(TH.BRICK, float) * k * np.array(([1, 1, 1], [1.1, .9, .82], [.72, .74, .8])[t]); dz = r.uniform(.0, .025)
                o.box((x0, y, z0 - .03 - dz), (x1, y + bh, z0 + .02), c)
            x += bw + gap
        y += bh + gap; row += 1
    o.box((-.72, 0, z0 - .01), (.72, 2.7, z0 + .02), (6, 5, 5))                                      # porte sombre du fond
    o.box((-.86, 2.7, z0 - .08), (.86, 2.86, z0 + .02), TH.WOOD_D); o.box((-.86, 0, z0 - .08), (-.72, 2.7, z0 + .02), TH.WOOD_D); o.box((.72, 0, z0 - .08), (.86, 2.7, z0 + .02), TH.WOOD_D)


def _floor_planks(o, r_hole):
    """plancher fixe : lames le long de x (longueurs variées), joints sombres, trou rond du plateau tournant, nez de scène en arc ; la salle est 1,2 m plus bas"""
    r = R(17); cx, cz = TH.TT[0], TH.TT[1]; pw = .16; z = -TH.APRON; A = TH.APRON
    while z < TH.BACK:
        zc = z + pw / 2
        xm = min(TH.WALL_X, 8.6 * math.sqrt(max(0., 1 + min(0., zc) / A)))                    # largeur de la scène à cette rangée (arc du nez de scène)
        if xm < .1: z += pw; continue
        o.box((-xm, -.07, z), (xm, -.03, z + pw), (14, 10, 8))                                     # dessous sombre : les joints
        L = 1.5 + r.random() * 1.1; x = -xm - r.random() * L
        dz = zc - cz; chord = math.sqrt(max(0., r_hole * r_hole - dz * dz)) if abs(dz) < r_hole else None
        while x < xm:
            segs = [(max(x, -xm), min(x + L, xm))]
            if chord is not None:
                a, b = cx - chord, cx + chord; segs = [(s0, min(s1, a)) for s0, s1 in segs if s0 < a] + [(max(s0, b), s1) for s0, s1 in segs if s1 > b]
            tone = r.uniform(.72, 1.08)
            for s0, s1 in segs:
                if s1 - s0 > .05: o.box((s0 + .006, -.03, z + .01), (s1 - .006, .012, z + pw - .01), _sh((92, 67, 47), tone))
            x += L; L = 1.5 + r.random() * 1.1
        z += pw
    n = 28; pts = [(x, float(TH.edge_z(x))) for x in np.linspace(-8.6, 8.6, n + 1)]
    for (x0, z0), (x1, z1) in zip(pts[:-1], pts[1:]):                                          # nez de scène (bois clair) et face avant de la scène (sombre), le long de l'arc
        o.beam((x0, -.01, z0 + .03), (x1, -.01, z1 + .03), .09, .05, (110, 80, 54)); o.beam((x0, -.62, z0 + .05), (x1, -.62, z1 + .05), .1, 1.2, (20, 15, 12))


def _ring(inner, r0, r1, seed):
    """lames d'un anneau du plateau tournant, au repère LOCAL VOXEL (centre de l'anneau = 0) : intérieur le long de x, extérieur le long de z"""
    r = R(seed); out = []; pw = .16 * K; R0, R1 = r0 * K, r1 * K
    v = -R1
    while v < R1:
        vc = v + pw / 2
        def span(rad): return math.sqrt(max(0., rad * rad - vc * vc)) if abs(vc) < rad else None
        a1 = span(R1)
        if a1 is not None:
            a0 = span(R0) if R0 > 0 else None
            segs = [(-a1, a1)] if a0 is None else [(-a1, -a0), (a0, a1)]
            for s0, s1 in segs:
                u = s0; L = (1.3 + r.random() * .9) * K
                while u < s1 - .03:
                    e = min(u + L, s1); tone = r.uniform(.74, 1.1) * (1. if inner else .93)
                    c = _hex(_sh((96, 69, 48), tone)); w = e - u - .012; cu = (u + e) / 2
                    if w > .04:
                        if inner: out.append(dict(x=round(cu, 4), y=-.0085, z=round(vc, 4), w=round(w, 4), h=.041, d=round(pw - .02, 4), color=c))
                        else: out.append(dict(x=round(vc, 4), y=-.0085, z=round(cu, 4), w=round(pw - .02, 4), h=.041, d=round(w, 4), color=c))
                    u = e; L = (1.3 + r.random() * .9) * K
        v += pw
    return out


def _stairs(o, s):
    n = s['n']; rise = TH.GAL_Y / n
    if s['axis'] == 'z':
        t = (s['z1'] - s['z0']) / n
        for i in range(n):
            z = s['z0'] + i * t; y = (i + 1) * rise
            o.box((s['x0'] + .07, y - .055, z), (s['x1'] - .07, y, z + t + .03), TH.WOOD_L); o.box((s['x0'] + .08, y - .055, z), (s['x1'] - .08, y - .045, z + t + .03), _sh(TH.WOOD_L, .7))
            o.box((s['x0'] + .09, y - rise, z + .01), (s['x1'] - .09, y - .055, z + .04), TH.WOOD_D)
        for x in (s['x0'] + .035, s['x1'] - .035): o.beam((x, -.02, s['z0'] - .1), (x, TH.GAL_Y + .02, s['z1'] + .02), .07, .32, TH.WOOD_D)
        hx = s['x1'] - .035; o.beam((hx, 1.02, s['z0'] - .05), (hx, TH.GAL_Y + 1.02, s['z1']), .08, .08, TH.WOOD)
        for i in range(0, n + 1, 3):
            z = s['z0'] + min(i, n - .5) * t + t / 2; y = min(i + 1, n) * rise; o.box((hx - .035, y, z - .035), (hx + .035, y + 1.0, z + .035), TH.WOOD)
    else:
        t = (s['x1'] - s['x0']) / n
        for i in range(n):
            x = s['x0'] + i * t; y = (i + 1) * rise
            o.box((x, y - .055, s['z0'] + .07), (x + t + .03, y, s['z1'] - .07), TH.WOOD_L); o.box((x, y - .055, s['z0'] + .08), (x + t + .03, y - .045, s['z1'] - .08), _sh(TH.WOOD_L, .7))
            o.box((x + .01, y - rise, s['z0'] + .09), (x + .04, y - .055, s['z1'] - .09), TH.WOOD_D)
        for z in (s['z0'] + .035, s['z1'] - .035): o.beam((s['x0'] - .1, -.02, z), (s['x1'] + .02, TH.GAL_Y + .02, z), .07, .32, TH.WOOD_D)
        hz = s['z0'] + .035; o.beam((s['x0'] - .05, 1.02, hz), (s['x1'], TH.GAL_Y + 1.02, hz), .08, .08, TH.WOOD)
        for i in range(0, n + 1, 3):
            x = s['x0'] + min(i, n - .5) * t + t / 2; y = min(i + 1, n) * rise; o.box((x - .035, y, hz - .035), (x + .035, y + 1.0, hz + .035), TH.WOOD)


def _candle(o, glow, c, gi):
    x, z, y, h, w, st = c['x'], c['z'], c['y'], c['h'], c['w'], c['stick']
    if st > 0:
        o.box((x - .05, y, z - .05), (x + .05, y + .025, z + .05), TH.BRASS); o.box((x - .014, y + .025, z - .014), (x + .014, y + st, z + .014), TH.BRASS)
        o.box((x - .035, y + st, z - .035), (x + .035, y + st + .03, z + .035), _sh(TH.BRASS, 1.1)); y = y + st + .03
    o.box((x - w / 2, y, z - w / 2), (x + w / 2, y + h, z + w / 2), TH.WAX)
    if w > .05: o.box((x - w / 2 + .012, y + h, z - w / 2 + .012), (x + w / 2 - .012, y + h + .012, z + w / 2 - .012), _sh(TH.WAX, .9))      # bord de cire fondue
    o.box((x - .005, y + h, z - .005), (x + .005, y + h + .02, z + .005), (20, 16, 12))
    f = Out(); f.box((x - .016, y + h + .018, z - .016), (x + .016, y + h + .07, z + .016), TH.FLAME); f.box((x - .009, y + h + .07, z - .009), (x + .009, y + h + .095, z + .009), (255, 236, 180))
    glow[gi % len(glow)].extend(f.b)


def _lantern(o, glass, x, y, z, gi):
    o.box((x - .014, y + .33, z - .014), (x + .014, 14.5, z + .014), TH.IRON)                         # chaîne
    o.box((x - .05, y + .3, z - .05), (x + .05, y + .36, z + .05), TH.IRON)                            # anneau
    o.box((x - .17, y + .17, z - .17), (x + .17, y + .22, z + .17), TH.IRON); o.box((x - .12, y + .22, z - .12), (x + .12, y + .26, z + .12), TH.IRON); o.box((x - .07, y + .26, z - .07), (x + .07, y + .3, z + .07), TH.IRON)
    for (ax, az) in ((-1, -1), (1, -1), (-1, 1), (1, 1)): o.box((x + ax * .12 - .02, y - .17, z + az * .12 - .02), (x + ax * .12 + .02, y + .18, z + az * .12 + .02), TH.IRON)
    o.box((x - .14, y - .21, z - .14), (x + .14, y - .15, z + .14), TH.IRON); o.box((x - .05, y - .25, z - .05), (x + .05, y - .21, z + .05), TH.IRON)
    for yy in (-.02, .1): o.box((x - .125, y + yy, z - .125), (x + .125, y + yy + .02, z + .125), TH.IRON)
    g = Out(); g.box((x - .105, y - .15, z - .105), (x + .105, y + .17, z + .105), TH.GLASS); g.box((x - .03, y - .08, z - .03), (x + .03, y + .03, z + .03), (255, 230, 170))
    glass[gi % len(glass)].extend(g.b)


COIL = (92, 72, 50)                     # corde enroulée : plus sombre que les cordes pendantes (le liseré de contre-jour l'éclaircit déjà)


def _coil(o, x, y, z, rad, along_x, outward):
    n = 16
    for k in range(n):
        a0 = k / n * 2 * math.pi; a1 = (k + 1) / n * 2 * math.pi
        p = lambda a: (math.sin(a) * rad, -rad - math.cos(a) * rad * 1.3)
        (u0, v0), (u1, v1) = p(a0), p(a1)
        if along_x: o.beam((x + u0, y + v0, z - .03), (x + u1, y + v1, z - .03), .07, .07, COIL)
        else: o.beam((x - outward * .04, y + v0, z + u0), (x - outward * .04, y + v1, z + u1), .07, .07, COIL)
    if along_x: o.box((x - .03, y - 2.6 * rad - .9, z - .06), (x + .03, y - 2.6 * rad + .05, z), COIL)          # brin qui pend sous le rouleau


@functools.lru_cache(maxsize=1)
def native():
    """le lieu en blocs VOXEL : (accessoire statique `bset`, accessoire dynamique `btheatre`) -- construit une fois"""
    P = TH.plan(); o = Out()
    _brick_wall(o)
    for (x, y0, y1) in P['studs']: o.box((x - .14, y0, TH.BACK - .12), (x + .14, y1, TH.BACK - .01), TH.WOOD_D); o.box((x - .1, y0, TH.BACK - .14), (x + .1, y1, TH.BACK - .12), _sh(TH.WOOD_D, .8))
    for (x, z, y0, y1) in P['posts']:
        o.box((x - .1, y0, z - .1), (x + .1, y1, z + .1), TH.WOOD); o.box((x - .12, y0, z - .12), (x + .12, y0 + .12, z + .12), TH.WOOD_D)
    for (x0, z0, x1, z1, y) in P['decks']:
        o.box((x0, y - .16, z0), (x1, y - .04, z1), TH.WOOD_D)
        zz = z0
        while zz < z1 - .01:                                                                       # lames du plancher des galeries
            o.box((x0, y - .04, zz + .006), (x1, y, min(z1, zz + .2) - .006), _sh(TH.WOOD, .85 + .25 * ((int(zz * 7) * 37 % 11) / 11))); zz += .2
    for (p0, p1, w, h) in P['beams']: o.box(*_axis(p0, p1, w, h), TH.WOOD_D)
    for (p0, p1, y) in P['rails']:
        o.box(*_axis(p0, p1, .085, .085), TH.WOOD)
        if abs(p0[1] - y - 1.02) < 1e-3:
            p0a = np.array(p0); p1a = np.array(p1); L = float(np.linalg.norm(p1a - p0a)); n = max(1, int(L / 1.1))
            for i in range(n + 1):
                q = p0a + (p1a - p0a) * i / n; o.box((q[0] - .05, y, q[2] - .05), (q[0] + .05, y + 1.02, q[2] + .05), TH.WOOD)
            for i in range(n):                                                                     # deux barreaux fins par travée
                for f in (.33, .66):
                    q = p0a + (p1a - p0a) * (i + f) / n; o.box((q[0] - .022, y, q[2] - .022), (q[0] + .022, y + .52, q[2] + .022), _sh(TH.WOOD, .85))
    for (p0, p1) in P['braces']: o.beam(p0, p1, .14, .12, TH.WOOD_D)
    for s in P['stairs']: _stairs(o, s)
    for (x0, z0, x1, z1, h, step) in P['tables']:
        o.box((x0, 0, z0), (x1, h - .04, z1), TH.WOOD_L); o.box((x0 - .03, h - .045, z0 - .03), (x1 + .03, h, z1 + .03), (176, 136, 98))
        o.box((x0 + .05, .06, z0 - .012), (x1 - .05, h - .1, z0), _sh(TH.WOOD_L, .82)); o.box((x0, 0, z0 - .02), (x1, .06, z1 + .02), _sh(TH.WOOD_L, .7))
        if step: o.box((x0 + .05, h, z1 - .28), (x1 - .05, h + .2, z1), TH.WOOD_L); o.box((x0 + .04, h + .17, z1 - .3), (x1 - .04, h + .2, z1), (176, 136, 98))
    for (x, z, s, rot) in P['crates']:
        o.box((x - s / 2, 0, z - s / 2), (x + s / 2, s, z + s / 2), (118, 86, 56))
        for yy in (0., s - .06): o.box((x - s / 2 - .01, yy, z - s / 2 - .01), (x + s / 2 + .01, yy + .06, z + s / 2 + .01), (84, 60, 38))
        o.box((x - s / 2 - .012, 0, z - s / 2 - .012), (x - s / 2 + .05, s, z - s / 2 + .05), (84, 60, 38)); o.box((x + s / 2 - .05, 0, z - s / 2 - .012), (x + s / 2 + .012, s, z - s / 2 + .05), (84, 60, 38))
    for (x, z, h) in P['stands']:
        o.box((x - .17, 0, z - .17), (x + .17, .05, z + .17), TH.BRASS); o.box((x - .1, .05, z - .1), (x + .1, .12, z + .1), _sh(TH.BRASS, .9))
        o.box((x - .035, .12, z - .035), (x + .035, h - .06, z + .035), TH.BRASS); o.box((x - .06, h * .55, z - .06), (x + .06, h * .55 + .05, z + .06), _sh(TH.BRASS, 1.1))
        o.box((x - .11, h - .06, z - .11), (x + .11, h, z + .11), TH.BRASS)
    flames = [[] for _ in range(6)]; glass = [[] for _ in range(4)]
    for i, c in enumerate(P['candles']): _candle(o, flames, c, i * 7)
    for i, (x, y, z) in enumerate(P['lanterns']): _lantern(o, glass, x, y, z, i)
    for (x, z, yb) in P['ropes']:
        o.box((x - .028, yb, z - .028), (x + .028, 14.5, z + .028), TH.ROPE)
        if yb < .3:                                                                                # le bout posé en rond au sol
            for k in range(8): a = k / 8 * 2 * math.pi; o.box((x + math.cos(a) * .16 - .03, 0, z + math.sin(a) * .16 - .03), (x + math.cos(a) * .16 + .03, .05, z + math.sin(a) * .16 + .03), TH.ROPE)
    for (x, y, z, rad) in P['coils']:
        along_x = abs(z - (TH.GAL_Z - .02)) < .05; _coil(o, x, y, z, rad, along_x, 1 if x > 0 else -1)
    sx_, sz_ = P['souffleur']; o.box((sx_ - .3, 0, sz_ - .15), (sx_ + .3, .12, sz_ + .2), (22, 19, 17))
    o.box((sx_ - .24, .09, sz_ - .16), (sx_ + .24, .11, sz_ - .14), (230, 170, 90), emis=.5)                          # boîte du souffleur
    for y, z in ((9.0, 9.35), (7.75, 9.15)): o.box((-6.4, y + .22, z - .03), (6.4, y + .28, z + .03), TH.IRON)
    lens = []
    for f in P['fixtures']:
        x, y, z = f['p']
        o.box((x - .16, y - .16, z + .02), (x + .16, y + .16, z + .4), (14, 14, 16)); o.box((x - .18, y - .18, z), (x + .18, y + .18, z + .05), (20, 20, 22))
        o.box((x - .02, y + .16, z + .12), (x + .02, y + .3, z + .16), TH.IRON); o.box((x - .2, y - .02, z + .1), (x - .17, y + .3, z + .3), TH.IRON); o.box((x + .17, y - .02, z + .1), (x + .2, y + .3, z + .3), TH.IRON)
        lo = Out(); lo.box((x - .13, y - .13, z - .02), (x + .13, y + .13, z + .005), (255, 255, 255)); lens += lo.b
    _floor_planks(o, TH.TT[3] + .03)
    static = dict(type='bset', boxes=o.b, rim=.25, var=.07)
    cx, cz, r1, r2 = TH.TT
    beams = [[round(-K * f['p'][0], 3), round(K * f['p'][1], 3), round(-K * f['p'][2], 3), round(-f['d'][0], 4), round(f['d'][1], 4), round(-f['d'][2], 4), f['row']] for f in P['fixtures']]
    dyn = dict(type='btheatre', center=[round(-K * cx, 3), 0., round(-K * cz, 3)], inner=_ring(True, 0., r1 - .02, 3), outer=_ring(False, r1 + .02, r2, 5),
               flames=flames, glass=glass, lens=lens, beams=beams, half=.12, beam_len=round(10.5 * K, 3),
               groups=[[round(-K * g_['x'], 3), round(K * g_['y'], 3), round(-K * g_['z'], 3), g_['n']] for g_ in P['groups']],
               lanterns=[[round(-K * x, 3), round(K * y, 3), round(-K * z, 3)] for (x, y, z) in P['lanterns']],
               wash=[[round(-K * p[0], 3), round(K * p[1], 3), round(-K * p[2], 3)] for p in TH.WASH_POS], back=[round(-K * TH.BACK_POS[0], 3), round(K * TH.BACK_POS[1], 3), round(-K * TH.BACK_POS[2], 3)])
    return static, dyn


def _axis(p0, p1, w, h):
    p0 = np.asarray(p0, float); p1 = np.asarray(p1, float); ax = int(np.argmax(np.abs(p1 - p0))); c = (p0 + p1) / 2
    half = {0: (abs(p1[0] - p0[0]) / 2, h / 2, w / 2), 1: (w / 2, abs(p1[1] - p0[1]) / 2, w / 2), 2: (w / 2, h / 2, abs(p1[2] - p0[2]) / 2)}[ax]
    return c - np.array(half), c + np.array(half)


# ------------------------------------------------------------------------------------------------- une image de lumière (contrat : stage.theatre.frames)
COLS = ['wash_r', 'wash_g', 'wash_b', 'wash_i', 'back_r', 'back_g', 'back_b', 'back_i', 'amb_r', 'amb_g', 'amb_b', 'fog_r', 'fog_g', 'fog_b', 'haze', 'practicals',
        'curtain', 'cur_r', 'cur_g', 'cur_b', 'turn_in', 'turn_out', 'nfollow']
FOLLOW_COLS = ['sx', 'sy', 'sz', 'ax', 'ay', 'az', 'half', 'i', 'r', 'g', 'b', 'tx', 'ty', 'tz', 'rad', 'soft']
POOL_COLS = ['x', 'z', 'rad', 'ring', 'i', 'r', 'g', 'b', 'dapple']          # après les poursuites : le nombre de disques, puis POOL_COLS par disque


def frame_row(rec):
    """enregistrement de lumière (repère PIXEL 3D, stage_light.resolve) -> une ligne de nombres (repère VOXEL) : COLS puis FOLLOW_COLS par poursuite"""
    v = list(rec['wash']) + [rec['wash_i']] + list(rec['back']) + [rec['back_i']] + list(rec['ambient']) + list(rec['fog']) + [rec['haze'], rec['practicals'], rec['curtain']] + list(rec['curtain_col']) + list(rec['turn'])
    fl = [f for f in rec['follow'] if f['i'] > 1e-3]
    v.append(len(fl))
    for f in fl:
        s, a, t = f['src'], f['aim'], f['target']
        v += [-K * s[0], K * s[1], -K * s[2], -K * a[0], K * a[1], -K * a[2], f['half'], f['i']] + list(f['col']) + [-K * t[0], K * t[1], -K * t[2], K * f['r'], f.get('soft', 0.)]
    pl = [p_ for p_ in rec.get('pools', ()) if p_['i'] > 1e-3]
    v.append(len(pl))
    for p_ in pl: v += [-K * p_['at'][0], -K * p_['at'][1], K * p_['r'], K * p_['ring'], p_['i']] + list(p_['col']) + [p_['dapple']]
    return [round(float(x), 4) for x in v]


def native_bsets():
    """accessoires du lieu pour VOXEL (statique + dynamique), copies fraîches"""
    s, d = native()
    import copy
    return [copy.deepcopy(s), copy.deepcopy(d)]
