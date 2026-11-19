"""OBJETS DÉTAILLÉS, VERSION VOXEL NATIVE (règle des deux versions : docs/REGLE_DEUX_VERSIONS.md ; la version PS1 est engines/pixel3d/objets.py).

Même plan que PS1 (mêmes dimensions, mêmes réglages : texte d'écran, heure, contenu), autre exécution : ici chaque objet est SCULPTÉ en cubes sur une
grille fine (de 4 mm pour des clés à 2 cm pour un téléviseur) : cylindres en anneaux de cubes, anses en boucles de cubes, cordon spiralé en chapelet,
vapeur en cubes translucides. Seuls les écrans, étiquettes et pages gardent une image (décalcomanie nette du peintre), sinon tout est volume.
  PS1    une tasse = une croix de boîtes + un filet peint ; un cadran = une texture ronde
  VOXEL  une tasse = des anneaux de cubes de 8 mm, anse en boucle, café en disque de cubes, soucoupe en disque à rebord ; un cadran = un disque de cubes percé de dix trous

Branchements (tous inertes sans objet détaillé dans la scène) :
  * `natives(boxes)` : dans une liste de boîtes PS1 posées, retrouve les objets détaillés par leurs marqueurs, rend (indices à cacher, boîtes VOXEL posées au même endroit)
    -> utilisé par b_sets.BSet (décor fixe), from_ps1 (objets de plan, éléments mobiles) ;
  * `held_contract(name, col, cfg)` : un objet tenu en volumes + décalcomanies dans le repère de la main de VOXEL (paume de `handR`) ;
  * `add_held_tracks(...)` : contrat `casts[id].held` + `stage.held` (objet tenu image par image, main droite / gauche) sous la clé `objets`."""
import base64, math
import numpy as np
from ..engines.pixel3d.r3d import B, Box
from ..engines.pixel3d import objets as OD, objets_tex as T

M_TRANSLUCENT = 77            # boîte VOXEL translucide (vapeur, verre, faisceau) : b_props._to_voxel en fait `alpha` ; aucune boîte PS1 n'a ce matériau
HOLD_K = 1.35                 # main de PIXEL 3D -> main de VOXEL pour les objets détaillés (b_chars.HOLD_K = 1,15 pour les anciens) : le poing de VOXEL fait 16 x 20 cm, la tête 50 cm ;
                              # à 1,15 une tasse disparaissait dans le poing (vérifié sur planche)
FRONT = {'od_cup': .045, 'od_mug': .045, 'od_glass': .045, 'od_wine_glass': .04, 'od_smartphone': .05, 'od_smartphone_montre': .05, 'od_book': .04, 'od_book_open': .03,
         'od_notebook': .04, 'od_keys': .04, 'od_photo_frame': .04, 'od_candle': .04, 'od_paper': .02, 'od_crowbar': .14}      # objets tenus devant le poing : poussés vers l'avant d'autant (m, repère PS1)
_g, _col, _sh = OD._g, OD._col, OD._sh


# ================================================================== a tiny voxel sculptor
class Vox:
    """grille de cubes de côté u (mètres) ; les cubes d'une même rangée en x et de même couleur sont fusionnés en une boîte"""

    def __init__(s, u):
        s.u = float(u); s.v = {}

    def _r(s, a, b):
        return range(int(math.floor(a / s.u + 1e-6)), int(math.ceil(b / s.u - 1e-6)))

    def c(s, i): return (i + .5) * s.u

    def put(s, i, j, k, col, em=0.):
        s.v[(i, j, k)] = (tuple(int(v) for v in col[:3]), float(em))

    def box(s, x0, y0, z0, x1, y1, z1, col, em=0.):
        for i in s._r(x0, x1):
            for j in s._r(y0, y1):
                for k in s._r(z0, z1): s.put(i, j, k, col, em)
        return s

    def erase(s, x0, y0, z0, x1, y1, z1):
        for i in s._r(x0, x1):
            for j in s._r(y0, y1):
                for k in s._r(z0, z1): s.v.pop((i, j, k), None)
        return s

    def cyl(s, cx, cz, r, y0, y1, col, r_in=-1., em=0.):
        """cylindre vertical (axe y), creux si r_in >= 0"""
        for i in s._r(cx - r, cx + r):
            for k in s._r(cz - r, cz + r):
                d = math.hypot(s.c(i) - cx, s.c(k) - cz)
                if d <= r + s.u * .2 and d >= r_in:
                    for j in s._r(y0, y1): s.put(i, j, k, col, em)
        return s

    def cylz(s, cx, cy, r, z0, z1, col, r_in=-1., em=0.):
        """cylindre couché le long de z (disque vertical vu de face)"""
        for i in s._r(cx - r, cx + r):
            for j in s._r(cy - r, cy + r):
                d = math.hypot(s.c(i) - cx, s.c(j) - cy)
                if d <= r + s.u * .2 and d >= r_in:
                    for k in s._r(z0, z1): s.put(i, j, k, col, em)
        return s

    def cylx(s, cy, cz, r, x0, x1, col, r_in=-1., em=0.):
        for j in s._r(cy - r, cy + r):
            for k in s._r(cz - r, cz + r):
                d = math.hypot(s.c(j) - cy, s.c(k) - cz)
                if d <= r + s.u * .2 and d >= r_in:
                    for i in s._r(x0, x1): s.put(i, j, k, col, em)
        return s

    def line(s, a, b, r, col, em=0.):
        a = np.asarray(a, float); b = np.asarray(b, float); L = float(np.linalg.norm(b - a)); n = max(2, int(L / (s.u * .5)) + 1)
        for t in np.linspace(0, 1, n):
            p = a + (b - a) * t
            for i in s._r(p[0] - r, p[0] + r):
                for j in s._r(p[1] - r, p[1] + r):
                    for k in s._r(p[2] - r, p[2] + r):
                        if (s.c(i) - p[0]) ** 2 + (s.c(j) - p[1]) ** 2 + (s.c(k) - p[2]) ** 2 <= (r + s.u * .3) ** 2: s.put(i, j, k, col, em)
        return s

    def loop_y(s, cx, cy, cz, r0, r1, half_z, col, side='+x'):
        """anse : demi-anneau dans le plan (x, y) d'épaisseur 2*half_z en z, ouvert vers le corps"""
        for i in s._r(cx - r1, cx + r1):
            for j in s._r(cy - r1, cy + r1):
                x, y = s.c(i) - cx, s.c(j) - cy; d = math.hypot(x, y)
                if r0 <= d <= r1 + s.u * .2 and ((x >= -s.u * .5) if side == '+x' else (x <= s.u * .5)):
                    for k in s._r(cz - half_z, cz + half_z): s.put(i, j, k, col)
        return s

    def boxes(s, **kw):
        """fusionne en boîtes PS1 (le convertisseur b_props les porte dans VOXEL)"""
        out = []; rows = {}
        for (i, j, k), cv in s.v.items(): rows.setdefault((j, k), []).append((i, cv))
        for (j, k) in sorted(rows):
            row = sorted(rows[(j, k)]); i0, cv0 = row[0]; n = 1; prev = i0
            for i, cv in row[1:] + [(None, None)]:
                if i is not None and i == prev + 1 and cv == cv0: n += 1; prev = i; continue
                out.append(B((i0 * s.u, j * s.u, k * s.u), (n * s.u, s.u, s.u), cv0[0], emis=cv0[1], cast=cv0[1] == 0, grain=0., **kw))
                if i is not None: i0, cv0, n, prev = i, cv, 1, i
        return out


def tex(x0, y0, z0, x1, y1, z1, face, img, col=(30, 30, 34), emis=0.):
    """plaque d'image posée sur une face (devient une décalcomanie nette dans VOXEL)"""
    return Box((x0, y0, z0), (x1, y1, z1), col, tex={face: img}, texemis=emis, grain=0.)


def glass(x0, y0, z0, x1, y1, z1, col, a=.35, em=0.):
    """boîte translucide (vapeur, verre, faisceau) : `alpha` dans le contrat"""
    b = B((x0, y0, z0), (x1 - x0, y1 - y0, z1 - z0), col, emis=em, cast=False, grain=0.); b.mat = M_TRANSLUCENT; b.dissolve = 1. - a
    return b


_FACE = {4: (2, -1), 5: (2, 1), 0: (0, -1), 1: (0, 1), 3: (1, 1), 2: (1, -1)}


def fix_plates(bx):
    """une image (écran, étiquette, page) doit rester DEVANT les cubes : la grille arrondit un volume vers l'extérieur (jusqu'à un cube), ce qui pouvait
    enfouir la plaque et sa décalcomanie (vu sur planche : photo d'un cadre, couverture d'un livre tenu). On sort chaque plaque devant le cube qui couvre son centre."""
    solids = [b for b in bx if not b.tex and getattr(b, 'mat', 0) != M_TRANSLUCENT]
    for p in bx:
        if not p.tex: continue
        for key in list(p.tex):
            ax, sg = _FACE.get(key, (None, 0))
            if ax is None: continue
            c = (np.asarray(p.lo, float) + np.asarray(p.hi, float)) / 2; oth = [a for a in range(3) if a != ax]
            for s in solids:
                if not all(s.lo[a] - 1e-6 <= c[a] <= s.hi[a] + 1e-6 for a in oth): continue
                if sg < 0 and s.lo[ax] < p.lo[ax] - 1e-6 and s.hi[ax] >= p.lo[ax] - 1e-6:
                    d = float(s.lo[ax] - .0008 - p.lo[ax]); p.lo[ax] += d; p.hi[ax] += d
                elif sg > 0 and s.hi[ax] > p.hi[ax] + 1e-6 and s.lo[ax] <= p.hi[ax] + 1e-6:
                    d = float(s.hi[ax] + .0008 - p.hi[ax]); p.lo[ax] += d; p.hi[ax] += d
    return bx


def coil(vx, pts, col, r=.004):
    """cordon spiralé : chapelet de cubes qui tourne autour de la ligne"""
    P = [np.asarray(p, float) for p in pts]; ph = 0
    for a, b in zip(P[:-1], P[1:]):
        v = b - a; L = float(np.linalg.norm(v))
        if L < 1e-6: continue
        u = v / L; side = np.cross(u, [0, 1, 0]); side = side / (np.linalg.norm(side) or 1.) if np.linalg.norm(side) > 1e-3 else np.array([1., 0, 0]); up = np.cross(side, u)
        n = max(1, int(L / (vx.u * 1.2)))
        for t in range(n):
            q = a + v * (t + .5) / n; ang = ph * 1.4; ph += 1
            q = q + side * r * math.cos(ang) + up * r * math.sin(ang)
            vx.put(int(math.floor(q[0] / vx.u)), int(math.floor(q[1] / vx.u)), int(math.floor(q[2] / vx.u)), col)
    return vx


# ================================================================== the objects (VOXEL)
def v_phone_rotary(p):
    col = _col(p.get('color'), OD.BLACK); dk = _sh(col, .6); lab = str(_g(p, 'numero', 'label', default=''))[:4]
    v = Vox(.008)
    v.box(-.108, 0, -.1, .108, .012, .12, dk)
    v.box(-.104, .012, -.1, .104, .07, .12, col).box(-.094, .07, -.06, .094, .104, .12, col).box(-.076, .104, -.03, .076, .12, .1, col)
    v.box(-.06, .07, -.1, .06, .1, -.06, col)
    v.cylz(0, .066, .052, -.112, -.1, _sh(col, 1.15))                                      # cadran : disque en relief, couronne chiffrée en décalcomanie, butée
    v.line((.03, .03, -.118), (.04, .022, -.118), .003, OD.METAL)
    on = bool(_g(p, 'voyant', default=False)); v.box(.072, .018, -.104, .086, .026, -.1, (255, 60, 40) if on else (80, 24, 20), 2.4 if on else 0.)
    if _g(p, 'combine', 'handset', default=True):
        v.box(.042, .12, .016, .058, .132, .054, dk).box(-.058, .12, .016, -.042, .132, .054, dk)
        v.box(-.085, .132, .02, .085, .152, .05, col)
        v.cylx(.142, .035, .026, .062, .11, col).cylx(.142, .035, .026, -.11, -.062, col)
        a0 = (-.11, .128, .04)
    else:
        v.box(.042, .12, .016, .058, .136, .054, dk).box(-.058, .12, .016, -.042, .136, .054, dk); a0 = (-.1, .05, .06)
    if _g(p, 'cordon', 'cord', default=True): coil(v, [a0, (-.124, .08, .05), (-.13, .02, .03), (-.17, .006, -.03), (-.15, .006, -.1), (-.108, .014, -.06)], dk)
    v.box(-.004, .004, .12, .004, .012, .2, dk)
    out = v.boxes() + [tex(-.05, .016, -.114, .05, .116, -.112, '-z', T.rotary_dial(col, lab or ''), _sh(col, 1.15))]
    return out


def v_phone_desk(p):
    col = _col(p.get('color'), OD.IVORY); dk = _sh(col, .55); keyc = _col(_g(p, 'touches'), (230, 226, 214) if sum(col) < 400 else (56, 56, 62))
    v = Vox(.008)
    v.box(-.1, 0, -.11, .1, .03, .11, col).box(-.1, .03, -.01, .1, .05, .11, col).box(-.1, .05, .05, .1, .064, .11, col)
    for r in range(4):                                                                       # touches en relief : 4 rangées de 3 cubes
        for cc in range(3):
            x = -.004 + cc * .024; z = -.096 + (3 - r) * .022
            v.box(x, .03, z, x + .016, .04 + r * .003, z + .014, keyc)
    for i, fc in enumerate(((190, 40, 40), (70, 70, 76), (70, 70, 76), (60, 130, 70))): v.box(i * .02 - .004, .04, .0, i * .02 + .008, .048, .016, fc)
    on = bool(_g(p, 'voyant', default=False)); v.box(.08, .05, .04, .09, .058, .05, (255, 60, 40) if on else (90, 26, 22), 2.5 if on else 0.)
    if _g(p, 'combine', 'handset', default=True):
        hy = .066
        v.box(-.076, hy - .004, -.07, -.044, hy + .012, -.05, dk).box(-.076, hy - .004, .06, -.044, hy + .03, .08, dk)
        v.box(-.08, hy + .02, -.09, -.04, hy + .04, .1, col)
        v.box(-.088, hy + .008, .056, -.032, hy + .04, .108, col).box(-.088, hy + .008, -.1, -.032, hy + .04, -.05, col)
        a0 = (-.076, hy + .01, -.1)
    else: a0 = (-.1, .02, -.05)
    if _g(p, 'cordon', 'cord', default=True): coil(v, [a0, (-.1, .035, -.125), (-.13, .006, -.09), (-.14, .006, .0), (-.105, .02, .05)], dk)
    out = v.boxes()
    kp = T.keypad(4, 3, keyc, (24, 24, 28) if sum(keyc) > 400 else (230, 230, 236), dk)          # chiffres des touches : à plat sur le pavé
    out.append(tex(-.006, .0505, -.098, .07, .0515, -.006, '+y', T.flat(kp), dk))
    if _g(p, 'ecran', 'screen', default=True) is not False:
        txt = str(_g(p, 'ecran', 'screen', default='')) if isinstance(_g(p, 'ecran', 'screen'), str) else T.hhmm(_g(p, 'heure', 'time'), '02:13')
        out.append(tex(-.0, .052, .046, .075, .064, .048, '-z', T.lcd(txt or '02:13', 36, 10), (40, 60, 40), .6))
    return out


def v_smartphone(p):
    case = _col(p.get('color'), (44, 48, 66)); scr = OD._screen_img(p)
    v = Vox(.004)
    if _g(p, 'debout', default=False):
        v.box(-.037, .03, -.004, .037, .184, .008, case).box(-.05, 0, -.03, .05, .012, .03, (60, 60, 66)).box(-.04, .012, .008, .04, .07, .016, (60, 60, 66)).box(-.044, .012, -.03, .044, .03, -.02, (60, 60, 66))
        return v.boxes() + [tex(-.033, .035, -.0055, .033, .179, -.0045, '-z', scr, (20, 24, 40), .9)]
    v.box(-.037, 0, -.077, .037, .008, .077, case).box(-.034, .008, -.074, .034, .009, .074, _sh(case, .8))
    v.box(.037, .002, .01, .041, .006, .05, _sh(case, .7)).box(-.041, .002, .0, -.037, .006, .04, _sh(case, .7))
    return v.boxes() + [tex(-.033, .009, -.072, .033, .0105, .072, '+y', T.flat(scr), (20, 24, 40), .9)]


def v_switchboard(p):
    wood = _col(p.get('color'), (92, 60, 38)); panel = (54, 50, 44)
    rows = [str(r) for r in (_g(p, 'etages', 'rows', default=['3', '2', '1', '0']))][:6]
    n = int(_g(p, 'chambres', 'rooms', default=13)); lit = tuple(str(x) for x in (_g(p, 'allumes', 'lit', default=[]) or []))
    plugged = [str(x) for x in (_g(p, 'fiches', 'plugs', default=['104', '212']) or [])]
    v = Vox(.02); W_ = .74; nr = len(rows); sh, sd = .06, .06
    v.box(-.38, 0, -.2, .38, .08, .24, wood).box(-.4, 0, -.2, -.36, .08 + nr * sh + .04, .24, _sh(wood, .85)).box(.36, 0, -.2, .4, .08 + nr * sh + .04, .24, _sh(wood, .85))
    for j in range(nr): v.box(-.36, .08 + j * sh, -.14 + j * sd, .36, .08 + (j + 1) * sh, .24, panel)
    for i in range(8): v.box(-.32 + i * .045, .08, -.18, -.3 + i * .045, .12, -.16, (200, 40, 40) if i % 3 == 0 else (30, 30, 34))
    v.box(.16, .08, -.2, .3, .1, -.06, (30, 30, 34))
    hs = (24, 24, 28); v.box(-.44, .12, -.02, -.4, .3, .02, hs).box(-.46, .26, -.03, -.4, .32, .03, hs).box(-.46, .1, -.03, -.4, .16, .03, hs)
    out = v.boxes()
    w = Vox(.006); x0, x1 = -.33, .33; cell = (x1 - x0) / (8 + n * 7 + 2)
    for i, r in enumerate(rows):
        j = nr - 1 - i; y = .08 + j * sh; z = -.14 + j * sd
        for k_ in range(n):
            lab = f'{r}{k_ + 1:02d}'; cx = x0 + (8 + k_ * 7 + 2.5) * cell
            on = lab in lit
            w.box(cx - .006, y + .012, z - .006, cx + .006, y + .03, z, (255, 150, 40) if on else (70, 40, 22), 2.2 if on else 0.)
            w.box(cx - .004, y + sh, z + .02, cx + .004, y + sh + .006, z + .028, (12, 12, 14))
            if lab in plugged:
                w.box(cx - .006, y + sh, z + .018, cx + .006, y + sh + .04, z + .03, (30, 30, 34)).box(cx - .007, y + sh + .036, z + .016, cx + .007, y + sh + .048, z + .032, (190, 40, 40) if k_ % 2 else (40, 90, 170))
                w.line((cx, y + sh + .05, z + .024), (cx - .03, .1, -.2), .004, (34, 30, 28)).line((cx - .03, .1, -.2), (cx - .07, .09, -.17), .004, (34, 30, 28))
        out.append(tex(x0, y + .034, z - .001, x1, y + sh - .004, z, '-z', np.ascontiguousarray(T.switch_strip(r, n, lit)[:6]), panel, .1))
    out += w.boxes()
    out.append(tex(-.12, .025, -.202, .12, .065, -.2, '-z', T.plate(str(_g(p, 'plaque', default='STANDARD')), 48, 9), (176, 150, 90)))
    d = Vox(.008); d.cyl(.23, -.13, .045, .1, .108, (30, 30, 34))                                  # cadran d'opératrice : disque de cubes percé de dix trous
    for kk in range(10):
        a_ = math.radians(60 + kk * 27); d.erase(.23 + math.cos(a_) * .03 - .004, .1, -.13 + math.sin(a_) * .03 - .004, .23 + math.cos(a_) * .03 + .004, .108, -.13 + math.sin(a_) * .03 + .004)
    return out + d.boxes()


def v_cup(p):
    col = _col(p.get('color'), (238, 236, 230)); v = Vox(.008)
    sau = _g(p, 'soucoupe', default=True) is not False
    y0 = 0.
    if sau:
        v.cyl(0, 0, .075, 0, .008, col).cyl(0, 0, .075, .008, .016, col, r_in=.06); y0 = .008
    v.cyl(0, 0, .026, y0, y0 + .008, _sh(col, .92))
    v.cyl(0, 0, .036, y0 + .008, y0 + .016, col).cyl(0, 0, .043, y0 + .016, y0 + .072, col).cyl(0, 0, .044, y0 + .064, y0 + .072, (200, 160, 60))
    if _g(p, 'cafe', 'plein', default=True):
        v.cyl(0, 0, .036, y0 + .072, y0 + .08, (70, 40, 22)).box(-.008, y0 + .072, -.016, .016, y0 + .08, .0, (118, 78, 44))
        v.cyl(0, 0, .046, y0 + .072, y0 + .08, col, r_in=.037)
    else: v.cyl(0, 0, .046, y0 + .072, y0 + .08, col, r_in=.037)
    v.loop_y(.046, y0 + .044, 0, .012, .024, .006, col)
    if sau and _g(p, 'cuillere', 'spoon', default=True):
        v.box(-.05, y0 + .0, -.058, .012, y0 + .006, -.05, OD.METAL).box(.008, y0, -.062, .028, y0 + .008, -.046, OD.METAL)
    out = v.boxes()
    if _g(p, 'vapeur', 'steam', default=True):
        for k_ in range(5):
            x = .012 * math.sin(k_ * 2.1 + .4); y = y0 + .09 + .026 * k_; z = .01 * math.cos(k_ * 1.6)
            out.append(glass(x - .008, y, z - .008, x + .008, y + .016, z + .008, (236, 238, 242), .34 - .055 * k_))
    return out


def v_mug(p):
    col = _col(p.get('color'), (60, 120, 150)); v = Vox(.008)
    v.cyl(0, 0, .048, 0, .104, col).cyl(0, 0, .049, .096, .104, _sh(col, 1.15))
    if _g(p, 'cafe', 'plein', default=True): v.cyl(0, 0, .04, .096, .104, (66, 38, 20))
    v.loop_y(.05, .054, 0, .018, .034, .01, col)
    out = v.boxes()
    pr = T.mug_print(str(_g(p, 'texte', 'text', default='')), str(_g(p, 'motif', default='coeur')), col, _col(_g(p, 'encre'), (250, 246, 236)))
    out.append(tex(-.028, .024, -.0505, .028, .08, -.0485, '-z', pr, col))
    if _g(p, 'vapeur', 'steam', default=False):
        for k_ in range(4): out.append(glass(-.008, .12 + .026 * k_, -.008, .008, .136 + .026 * k_, .008, (236, 238, 242), .3 - .06 * k_))
    return out


def v_glass(p):
    gl = _col(p.get('color'), (190, 206, 216)); mod = _g(p, 'modele', default='gobelet'); cont = _g(p, 'contenu', default='vin' if mod == 'pied' else 'eau')
    v = Vox(.006); out = []
    if mod == 'pied':
        v.cyl(0, 0, .034, 0, .006, gl).cyl(0, 0, .006, .006, .084, gl)
        if cont in OD.LIQ: v.cyl(0, 0, .03, .084, .12, OD.LIQ[cont])
        out = v.boxes()
        out += [glass(-.036, .084, -.036, .036, .186, .036, gl, .28)] + _rim(.037, .182, .188)
        return out
    v.cyl(0, 0, .036, 0, .012, gl)
    if cont in OD.LIQ: v.cyl(0, 0, .03, .012, .072, OD.LIQ[cont])
    if cont == 'whisky': v.box(-.018, .06, -.006, .006, .084, .018, (226, 236, 240)).box(.004, .056, -.02, .024, .078, .0, (226, 236, 240))
    out = v.boxes() + [glass(-.037, .012, -.037, .037, .1, .037, gl, .28)] + _rim(.038, .097, .102)
    return out


def _rim(r, y0, y1):
    """bord d'un verre : un anneau clair (quatre côtés), pas un couvercle"""
    t = .005; c = (240, 248, 250)
    return [glass(-r, y0, -r, r, y1, -r + t, c, .55, .25), glass(-r, y0, r - t, r, y1, r, c, .55, .25), glass(-r, y0, -r + t, -r + t, y1, r - t, c, .55, .25), glass(r - t, y0, -r + t, r, y1, r - t, c, .55, .25)]


def v_bottle(p):
    mod = _g(p, 'modele', default='vin'); g_, liq, t1, t2 = OD.BOTTLES.get(mod, OD.BOTTLES['vin']); gl = _col(p.get('color'), g_)
    et = str(_g(p, 'etiquette', 'texte', 'text', default=t1)); sous = str(_g(p, 'sous', default=t2)); v = Vox(.008)
    if mod == 'whisky':
        v.box(-.044, 0, -.028, .044, .17, .028, gl).box(-.028, .17, -.02, .028, .19, .02, gl).cyl(0, 0, .016, .19, .23, gl).cyl(0, 0, .02, .222, .25, (30, 26, 22))
        return v.boxes() + [tex(-.034, .04, -.0305, .034, .11, -.0285, '-z', T.label(et, sous, (232, 222, 196), (60, 30, 20)), (230, 220, 190))]
    h = {'vin': .2, 'biere': .14, 'eau': .22}.get(mod, .2); w = {'vin': .074, 'biere': .062, 'eau': .084}.get(mod, .074)
    v.cyl(0, 0, w / 2, 0, h, gl).cyl(0, 0, w * .36, h, h + .016, gl).cyl(0, 0, w * .24, h + .016, h + .028, gl)
    neck = .07 if mod != 'biere' else .045
    v.cyl(0, 0, w * .2, h + .028, h + .025 + neck, gl).cyl(0, 0, w * .23, h + neck, h + .025 + neck + .006, {'vin': (150, 20, 30), 'biere': (200, 170, 60), 'eau': (40, 90, 190)}.get(mod, (150, 20, 30)))
    v.box(w * .26, h * .2, -w * .42, w * .26 + .008, h * .9, -w * .42 + .008, _sh(gl, 1.9))
    out = v.boxes()
    lab = T.label(et, sous, (236, 226, 200) if mod != 'eau' else (60, 120, 200), (90, 20, 30) if mod != 'eau' else (250, 250, 250))
    out.append(tex(-w * .36, h * .22, -w / 2 - .006, w * .36, h * .64, -w / 2 - .004, '-z', lab, (236, 226, 200)))
    return out


def v_plate(p):
    col = _col(p.get('color'), (240, 238, 232)); fil = _col(_g(p, 'filet'), (60, 90, 160)); v = Vox(.008)
    v.cyl(0, 0, .12, 0, .008, col).cyl(0, 0, .12, .008, .016, col, r_in=.08).cyl(0, 0, .108, .012, .016, fil, r_in=.1)
    cont = _g(p, 'contenu', default='vide')
    if cont == 'gateau': v.box(-.04, .008, -.03, .04, .044, .03, (120, 70, 40)).box(-.04, .044, -.03, .04, .052, .03, (240, 230, 220)).box(.008, .052, -.008, .024, .064, .008, (200, 30, 40))
    elif cont == 'pain': v.box(-.07, .008, -.03, .03, .032, .03, (210, 160, 90)).box(-.068, .032, -.028, .028, .036, .028, (240, 220, 180))
    elif cont == 'fruits': v.cyl(-.03, -.02, .024, .008, .056, (220, 40, 40)).cyl(.03, .02, .022, .008, .052, (240, 190, 40)).cyl(0, .04, .02, .008, .048, (110, 180, 60))
    return v.boxes()


def v_cutlery(p):
    m = _col(p.get('color'), OD.METAL); e = float(_g(p, 'ecart', default=.17)); v = Vox(.004)
    v.box(-e - .006, 0, -.09, -e + .006, .004, .01, m).box(-e - .012, 0, .01, -e + .012, .004, .04, m)
    for i in range(4): v.box(-e - .012 + i * .0064, 0, .04, -e - .009 + i * .0064, .004, .072, m)
    v.box(e - .008, 0, -.092, e + .008, .008, -.008, (60, 40, 30)).box(e - .008, 0, -.008, e + .008, .004, .104, _sh(m, 1.05))
    x = e + .035; v.box(x - .006, 0, -.09, x + .006, .004, .02, m).cyl(x, .045, .016, 0, .008, m).cyl(x, .045, .01, .004, .008, _sh(m, .8))
    return v.boxes()


def v_couvert(p):
    out = v_plate(dict(p)) + v_cutlery(dict(p, ecart=.155))
    v = Vox(.01); v.box(-.24, 0, -.07, -.18, .01, .05, _col(_g(p, 'serviette'), (180, 40, 50))); out += v.boxes()
    for b in v_glass({'modele': 'pied', 'contenu': _g(p, 'contenu_verre', default='vin')}): b.lo = b.lo + np.array([.16, 0, .16], np.float32); b.hi = b.hi + np.array([.16, 0, .16], np.float32); out.append(b)
    return out


def v_book(p):
    col = _col(p.get('color'), (120, 30, 36)); titre = str(_g(p, 'titre', 'title', default='LE SILENCE')); aut = str(_g(p, 'auteur', default='M. ARNAUD'))
    v = Vox(.006); W_, H_, D_ = .15, .03, .22
    if _g(p, 'ouvert', 'open', default=False):
        v.box(-W_ - .006, 0, -D_ / 2 - .006, W_ + .006, .006, D_ / 2 + .006, col).box(-W_, .006, -D_ / 2, -.006, .018, D_ / 2, (232, 226, 206)).box(.006, .006, -D_ / 2, W_, .018, D_ / 2, (232, 226, 206))
        v.box(-.012, .006, -D_ / 2, .012, .012, D_ / 2, (200, 190, 166)).box(-.003, .012, D_ / 2 - .06, .003, .02, D_ / 2 + .02, (190, 30, 40))
        pg = T.open_pages(T.lines(_g(p, 'texte', 'text'))); Wt = pg.shape[1] // 2
        return v.boxes() + [tex(-W_ + .006, .018, -D_ / 2 + .006, -.012, .019, D_ / 2 - .006, '+y', T.flat(np.ascontiguousarray(pg[:, :Wt])), (238, 232, 212)),
                            tex(.012, .018, -D_ / 2 + .006, W_ - .006, .019, D_ / 2 - .006, '+y', T.flat(np.ascontiguousarray(pg[:, Wt:])), (238, 232, 212))]
    if _g(p, 'debout', default=False):
        v.box(-H_ / 2, 0, -D_ / 2 + .02, H_ / 2, D_, -D_ / 2 + .17, col).box(-H_ / 2 + .004, .004, -D_ / 2 + .026, H_ / 2 - .004, D_ - .004, -D_ / 2 + .17, (232, 226, 206))
        return v.boxes() + [tex(-H_ / 2, 0, -D_ / 2 + .016, H_ / 2, D_, -D_ / 2 + .02, '-z', T.book_spine(titre, col), col)]
    v.box(-W_ / 2, 0, -D_ / 2, W_ / 2, .006, D_ / 2, col).box(-W_ / 2 + .006, .006, -D_ / 2 + .006, W_ / 2 - .006, H_ - .006, D_ / 2 - .006, (232, 226, 206))
    v.box(-W_ / 2 - .006, 0, -D_ / 2, -W_ / 2 + .006, H_, D_ / 2, _sh(col, .85)).box(-W_ / 2, H_ - .006, -D_ / 2, W_ / 2, H_, D_ / 2, col)
    for y in (.012, .018, .024): v.box(-W_ / 2 + .006, y, -D_ / 2 + .002, W_ / 2 - .004, y + .002, -D_ / 2 + .006, (206, 198, 176))
    v.box(.024, .012, D_ / 2, .036, .018, D_ / 2 + .04, (190, 30, 40))
    return v.boxes() + [tex(-W_ / 2 + .004, H_, -D_ / 2 + .004, W_ / 2 - .004, H_ + .001, D_ / 2 - .004, '+y', T.flat(T.book_cover(titre, aut, col)), col)]


def v_notebook(p):
    col = _col(p.get('color'), (40, 44, 60)); W_, D_ = .1, .15; v = Vox(.004); out = []
    if _g(p, 'ouvert', 'open', default=True):
        v.box(-W_ / 2, 0, -D_ / 2, W_ / 2, .004, D_ / 2, col).box(-W_ / 2 + .002, .004, -D_ / 2 + .002, W_ / 2 - .002, .012, D_ / 2 - .002, (232, 230, 220))
        img = T.flat(T.notebook_page(T.lines(_g(p, 'texte', 'text')))); top = .012
    else:
        v.box(-W_ / 2, 0, -D_ / 2, W_ / 2, .012, D_ / 2, col).box(W_ / 2 - .016, .012, -D_ / 2, W_ / 2 - .008, .014, D_ / 2, (20, 20, 22))
        img = T.flat(T.notebook_cover(col)); top = .012
    for i in range(9): v.box(-W_ / 2 + .004 + i * .0105, top, D_ / 2 - .008, -W_ / 2 + .008 + i * .0105, top + .008, D_ / 2, (170, 172, 180))
    if _g(p, 'stylo', 'pen', default=True): v.box(W_ / 2 + .016, 0, -.065, W_ / 2 + .024, .008, .065, (30, 60, 160)).box(W_ / 2 + .016, 0, .06, W_ / 2 + .024, .008, .076, (220, 220, 226))
    return v.boxes() + [tex(-W_ / 2 + .004, top, -D_ / 2 + .004, W_ / 2 - .004, top + .001, D_ / 2 - .01, '+y', img, (240, 238, 228))]


def v_paper(p):
    pap = _col(p.get('color'), (238, 236, 228))
    img = T.paper(T.lines(_g(p, 'texte', 'text'), ('RAPPORT DE NUIT', '', '02:13 APPEL CH 313', '02:14 LIGNE COUPEE', '02:16 PERSONNE', '', 'VU PAR : M. R.')),
                  str(_g(p, 'titre', 'title', default='')), entete=bool(_g(p, 'entete', default=True)), pli=bool(_g(p, 'pli', default=False)), papier=pap, surligne=str(_g(p, 'surligne', default='')))
    v = Vox(.004)
    if _g(p, 'mur', 'wall', default=False):
        y = float(_g(p, 'hauteur', default=1.3)); v.box(-.105, y, -.004, .105, y + .297, 0, pap).box(-.008, y + .28, -.008, .008, y + .292, -.004, (200, 40, 40))
        return v.boxes() + [tex(-.103, y + .002, -.005, .103, y + .295, -.004, '-z', img, pap, .1)]
    y = 0.
    if _g(p, 'pile', default=False):
        for i in range(3): v.box(-.103 + .004 * i, .004 * i, -.146 - .003 * i, .107 + .004 * i, .004 * (i + 1), .151 - .003 * i, _sh(pap, .96))
        y = .012
    v.box(-.105, y, -.1485, .105, y + .004, .1485, pap).box(.09, y + .004, .133, .105, y + .008, .1485, _sh(pap, .82))
    return v.boxes() + [tex(-.104, y + .004, -.1475, .104, y + .005, .1475, '+y', T.flat(img), pap, .1)]


def v_keys(p):
    br = _col(p.get('color'), OD.BRASS); v = Vox(.004)
    v.cyl(0, 0, .018, 0, .004, OD.METAL, r_in=.012)
    for (dx, dz, cc, L) in ((.03, .01, br, .055), (.02, .03, OD.METAL, .05), (-.015, .035, (150, 152, 160), .035)):
        ang = math.atan2(dz, dx); ux, uz = math.cos(ang), math.sin(ang); b0 = (dx * .9, .002, dz * .9)
        v.cyl(b0[0], b0[2], .011, 0, .004, cc, r_in=.004)
        v.line((b0[0] + ux * .012, .002, b0[2] + uz * .012), (b0[0] + ux * L, .002, b0[2] + uz * L), .003, cc)
        for t in (.5, .7, .85): v.line((b0[0] + ux * L * t, .002, b0[2] + uz * L * t), (b0[0] + ux * L * t - uz * .008, .002, b0[2] + uz * L * t + ux * .008), .002, cc)
    tg = _g(p, 'etiquette', 'tag', default='313'); out = []
    if tg:
        v.box(-.06, 0, -.06, -.024, .006, -.025, (190, 50, 36)); v.line((-.02, .002, -.02), (-.028, .002, -.028), .002, OD.METAL)
        out = v.boxes() + [tex(-.058, .006, -.058, -.026, .007, -.027, '+y', T.flat(T.tag(str(tg))), (190, 50, 36))]
    else: v.box(-.06, 0, -.045, -.025, .008, -.025, (110, 60, 36)); out = v.boxes()
    return out


def v_desk_lamp(p):
    on = float(_g(p, 'allumee', 'on', default=1.) or 0.)
    v = Vox(.012)
    if _g(p, 'modele', default='banquier') == 'articulee':
        col = _col(p.get('color'), (56, 92, 132))
        v.cyl(0, 0, .09, 0, .024, _sh(col, .8)).box(-.02, .024, .0, .02, .04, .04, (40, 40, 44))
        v.line((0, .04, .02), (0, .3, .06), .012, col).line((0, .3, .06), (0, .36, -.16), .011, col).line((.016, .06, .03), (.016, .28, .065), .004, (190, 190, 196))
        v.cyl(0, -.2, .05, .31, .36, col).cyl(0, -.21, .08, .28, .31, col).cyl(0, -.21, .065, .276, .284, (255, 236, 186), em=1.8 * on)
        return v.boxes()
    br = OD.BRASS; sh = _col(p.get('color'), (24, 104, 58))
    v.box(-.1, 0, -.065, .1, .02, .065, br).box(-.08, .02, -.05, .08, .03, .05, _sh(br, .9)).cyl(0, .02, .01, .03, .26, br)
    v.box(-.14, .252, -.06, .14, .264, .04, br)
    v.cylx(.264, -.012, .056, -.135, .135, sh)                                                   # abat-jour : demi-cylindre de verre vert
    v.erase(-.14, .2, -.08, .14, .264, .06)
    v.box(-.12, .256, -.05, .12, .262, .03, (255, 238, 186), em=1.8 * on)
    for i in range(5): v.box(.084, .23 - .012 * i - .006, -.066, .094, .23 - .012 * i, -.056, br)
    v.box(.082, .16, -.068, .096, .176, -.054, br)
    return v.boxes()


def v_bedside_lamp(p):
    base = _col(p.get('color'), (180, 90, 70)); shade = _col(_g(p, 'abat_jour', 'shade'), (236, 216, 176)); on = float(_g(p, 'allumee', 'on', default=1.) or 0.)
    v = Vox(.01)
    v.cyl(0, 0, .05, 0, .02, _sh(base, .8)).cyl(0, 0, .055, .02, .05, base).cyl(0, 0, .062, .05, .09, base).cyl(0, 0, .05, .09, .12, base).cyl(0, 0, .03, .12, .15, base)
    v.cyl(0, 0, .014, .15, .17, OD.BRASS).cyl(0, 0, .007, .17, .23, OD.BRASS)
    for i, (r, y) in enumerate(((.13, .195), (.12, .225), (.11, .255), (.1, .285))): v.cyl(0, 0, r, y, y + .03, shade, r_in=r - .016)
    v.cyl(0, 0, .11, .19, .2, (255, 226, 170), em=1.4 * on).cyl(0, 0, .03, .2, .24, (255, 240, 200), em=2. * on)
    v.line((0, .02, .05), (0, .006, .14), .005, (240, 240, 236))
    return v.boxes()


def v_nightstand(p):
    wood = _col(p.get('color'), (90, 66, 46)); v = Vox(.02)
    v.box(-.22, .06, -.2, .22, .5, .2, wood).box(-.24, .5, -.22, .24, .52, .22, _sh(wood, 1.15)).box(-.2, .3, -.22, .2, .48, -.2, _sh(wood, .9)).box(-.2, .08, -.22, .2, .28, -.2, _sh(wood, .85))
    for x in (-.22, .18):
        for z in (-.2, .16): v.box(x, 0, z, x + .04, .06, z + .04, _sh(wood, .7))
    out = v.boxes()
    w = Vox(.01); w.box(-.02, .38, -.24, .02, .4, -.22, OD.BRASS); out += w.boxes()
    for b in v_bedside_lamp(p if not p.get('lampe') else dict(p, color=p['lampe'])): b.lo = b.lo + np.array([.04, .52, .03], np.float32); b.hi = b.hi + np.array([.04, .52, .03], np.float32); out.append(b)
    if _g(p, 'livre', default=True):
        for b in v_book({'titre': 'NUIT', 'color': (40, 60, 110)}): b.lo = b.lo + np.array([-.1, .52, -.07], np.float32); b.hi = b.hi + np.array([-.1, .52, -.07], np.float32); out.append(b)
    return out


def v_laptop(p):
    alu = _col(p.get('color'), (176, 178, 186)); on = _g(p, 'ecran', 'screen', default='bureau') not in ('noir', 'off', False)
    v = Vox(.008)
    v.box(-.17, 0, -.12, .17, .016, .12, alu).box(-.15, .016, .11, .15, .028, .13, _sh(alu, .7))
    v.box(-.17, .024, .12, .17, .24, .136, alu).box(-.016, .12, .136, .016, .152, .14, (230, 232, 240), .3 * float(on))
    out = v.boxes()
    out.append(tex(-.168, .016, -.118, .168, .017, .11, '+y', T.flat(T.laptop_deck()), alu))
    out.append(tex(-.16, .034, .118, .16, .232, .12, '-z', OD._computer_img(p, 'bureau'), (16, 18, 24), .9 if on else 0.))
    return out


def v_monitor(p):
    col = _col(p.get('color'), (40, 40, 44)); on = _g(p, 'ecran', 'screen', default='bureau') not in ('noir', 'off', False)
    v = Vox(.012)
    v.box(-.11, 0, -.05, .11, .012, .11, col).box(-.024, .012, .056, .024, .2, .084, col).box(-.27, .14, .04, .27, .48, .072, col).box(-.07, .2, .072, .07, .4, .084, _sh(col, .8))
    v.box(.23, .144, .036, .246, .152, .04, (80, 220, 120) if on else (40, 60, 40), 2. if on else 0.)
    out = v.boxes() + [tex(-.25, .16, .038, .25, .46, .04, '-z', OD._computer_img(p), (10, 14, 20), .85 if on else 0.)]
    if _g(p, 'clavier', 'keyboard', default=True):
        w = Vox(.008); w.box(-.2, 0, -.2, .2, .016, -.064, (36, 36, 40)).box(.264, 0, -.176, .32, .024, -.088, (40, 40, 46)).line((.29, .004, -.084), (.2, .004, .02), .004, (30, 30, 34))
        out += w.boxes() + [tex(-.196, .016, -.196, .196, .017, -.068, '+y', T.flat(T.keyboard_top()), (36, 36, 40))]
    return out


def v_computer(p):
    top = _col(p.get('color'), (120, 90, 60)); v = Vox(.025)
    v.box(-.7, .74, -.35, .7, .79, .35, top)
    for x in (-.675, .6):
        for z in (-.3, .25): v.box(x, 0, z, x + .05, .74, z + .05, (60, 44, 30))
    v.box(.35, 0, -.2, .55, .45, .25, (44, 44, 50))
    out = v.boxes() + Vox(.01).box(.44, .39, -.21, .46, .41, -.2, (80, 220, 120), 2.).boxes()
    for fn, pp, d in ((v_monitor, dict(p, clavier=True), (0, .79, .05)), (v_mug, {'texte': 'CAFE', 'color': (180, 60, 50)}, (-.5, .79, -.1)), (v_paper, {'pile': True, 'texte': _g(p, 'papier')}, (-.42, .79, .12))):
        for b in fn(pp): b.lo = b.lo + np.array(d, np.float32); b.hi = b.hi + np.array(d, np.float32); out.append(b)
    return out


def v_tv(p):
    cab = _col(p.get('color'), (60, 44, 30)); mode = OD._tv_mode(p); W_ = float(_g(p, 'largeur', default=1.0)); v = Vox(.02)
    v.box(-.6, 0, -.24, .6, .44, .26, cab).box(-.62, .44, -.26, .62, .46, .26, _sh(cab, 1.15)).box(-.58, .06, -.26, -.02, .42, -.24, _sh(cab, .9)).box(.02, .06, -.26, .58, .42, -.24, _sh(cab, .9))
    v.box(-.14, .46, -.08, .14, .48, .08, (30, 30, 34)).box(-.04, .48, -.02, .04, .54, .02, (30, 30, 34))
    h = W_ * .58; v.box(-W_ / 2, .52, -.04, W_ / 2, .52 + h, .02, (18, 18, 22))
    v.box(W_ / 2 - .06, .52, -.06, W_ / 2 - .04, .54, -.04, (255, 40, 30) if mode == 'noir' else (60, 200, 90), 2.2)
    out = v.boxes() + Vox(.01).box(-.04, .2, -.27, -.02, .26, -.26, OD.BRASS).box(.02, .2, -.27, .04, .26, -.26, OD.BRASS).box(.36, .46, -.2, .4, .47, -.05, (26, 26, 30)).boxes()
    out.append(tex(-W_ / 2 + .02, .54, -.042, W_ / 2 - .02, .5 + h, -.04, '-z', T.tv_screen(mode, T.lines(_g(p, 'texte', 'text'))), (20, 30, 50), 0. if mode == 'noir' else .9))
    return out


def v_tv_crt(p):
    wood = _col(p.get('color'), (96, 64, 40)); mode = OD._tv_mode(p); v = Vox(.02)
    v.box(-.36, .12, -.28, .36, .64, .24, wood)
    for x in (-.32, .28):
        for z in (-.26, .16): v.box(x, 0, z, x + .04, .12, z + .04, (40, 30, 22))
    v.box(-.32, .16, -.3, .14, .6, -.28, (30, 28, 26)).box(.16, .2, -.3, .32, .56, -.28, (60, 50, 40))
    v.box(-.06, .64, -.04, .06, .66, .04, (40, 40, 44))
    v.line((-.03, .66, 0), (-.18, .98, .05), .008, OD.METAL).line((.03, .66, 0), (.2, .95, -.04), .008, OD.METAL)
    out = v.boxes() + Vox(.01).cylz(.24, .5, .025, -.31, -.29, (200, 196, 186)).cylz(.24, .43, .02, -.31, -.29, (200, 196, 186)).boxes()
    out.append(tex(-.3, .18, -.302, .12, .58, -.3, '-z', T.tv_screen(mode, T.lines(_g(p, 'texte', 'text')), 64, 52), (30, 40, 50), 0. if mode == 'noir' else .95))
    return out


def v_radio(p):
    on = bool(_g(p, 'allumee', 'on', default=True)); v = Vox(.01)
    if _g(p, 'modele', default='ancienne') == 'reveil':
        col = _col(p.get('color'), (30, 30, 34)); v.box(-.11, 0, -.06, .11, .07, .06, col).box(-.1, .07, -.05, .1, .08, .05, _sh(col, 1.3))
        for i in range(4): v.box(-.075 + i * .04, .08, -.01, -.045 + i * .04, .09, .01, (80, 80, 86))
        return v.boxes() + [tex(-.07, .012, -.062, .03, .057, -.06, '-z', T.led_clock(T.hhmm(_g(p, 'heure', 'time'), '02:13'), True), (12, 8, 8), 1.2)]
    wood = _col(p.get('color'), (110, 70, 40))
    v.box(-.2, 0, -.09, .2, .02, .09, _sh(wood, .6)).box(-.2, .02, -.09, .2, .26, .09, wood).box(-.18, .26, -.08, .18, .29, .08, wood)
    for i in range(5): v.box(-.14 + i * .05, .29, -.05, -.1 + i * .05, .31, -.01, (236, 230, 210))
    out = v.boxes() + Vox(.008).cylz(.05, .06, .02, -.11, -.09, (226, 214, 180)).cylz(.15, .06, .02, -.11, -.09, (226, 214, 180)).boxes()
    out.append(tex(-.19, .03, -.092, .19, .25, -.09, '-z', T.radio_face(on), wood, .25 if on else 0.))
    return out


def v_clock(p):
    hh = T.hhmm(_g(p, 'heure', 'time'), '10:10'); mod = _g(p, 'modele', default='murale')
    if mod == 'led':
        y = float(_g(p, 'hauteur', default=2.1)); on = bool(_g(p, 'allumee', 'on', default=True))
        return Vox(.02).box(-.17, y - .07, -.04, .17, y + .07, 0, (16, 14, 14)).boxes() + [tex(-.155, y - .058, -.042, .155, y + .058, -.04, '-z', T.led_clock(hh, on), (12, 8, 8), 1.3 if on else 0.)]
    if mod == 'reveil':
        rim = _col(p.get('color'), (190, 40, 40)); v = Vox(.008); S = .11; y0 = .03
        v.cylz(0, y0 + S / 2, S / 2, -.024, .024, rim).cylz(0, y0 + S / 2, S / 2 - .008, -.026, -.022, (240, 236, 224))
        v.cyl(-.035, 0, .02, y0 + S - .004, y0 + S + .02, OD.BRASS).cyl(.035, 0, .02, y0 + S - .004, y0 + S + .02, OD.BRASS).box(-.04, y0 + S + .024, -.004, .04, y0 + S + .032, .004, OD.BRASS)
        v.box(-.044, 0, -.006, -.032, y0, .006, OD.BRASS).box(.032, 0, -.006, .044, y0, .006, OD.BRASS)
        _hands(v, 0, y0 + S / 2, -.028, S * .42, hh, (30, 28, 26))
        return v.boxes()
    y = float(_g(p, 'hauteur', 'at_y', default=2.0)); S = float(_g(p, 'taille', default=.34)); rim = _col(p.get('color'), (46, 42, 40)); v = Vox(.01)
    v.cylz(0, y, S / 2, -.05, 0, rim).cylz(0, y, S / 2 - .02, -.056, -.05, (236, 232, 218))
    for kk in range(12):
        a = kk * math.pi / 6; r = S / 2 - .04
        v.box(math.sin(a) * r - .006, y + math.cos(a) * r - .006, -.064, math.sin(a) * r + .006, y + math.cos(a) * r + .006, -.056, (30, 28, 26) if kk % 3 else (160, 30, 30))
    _hands(v, 0, y, -.066, S / 2 - .04, hh, (30, 28, 26))
    return v.boxes()


def _hands(v, cx, cy, z, R, hh, col):
    """aiguilles en cubes. Le passage PS1 -> VOXEL est un demi-tour, mais les deux peintres n'ont pas la même main (l'image VOXEL est le miroir de
    l'image PS1) : un dessin EN VOLUME qui a un sens (des aiguilles) est donc tracé en miroir ici (x = -sin), sinon 2 h 13 se lirait 9 h 47.
    Les images (écrans, étiquettes) ne sont pas concernées : une décalcomanie se lit toujours depuis sa face."""
    h, m = (int(x) for x in hh.split(':'))
    ah = ((h % 12) + m / 60.) * math.pi / 6; am = m * math.pi / 30
    v.line((cx, cy, z), (cx - math.sin(ah) * R * .55, cy + math.cos(ah) * R * .55, z), v.u * .7, col)
    v.line((cx, cy, z - .002), (cx - math.sin(am) * R * .85, cy + math.cos(am) * R * .85, z - .002), v.u * .5, col)
    v.line((cx, cy, z - .004), (cx - math.sin(am + 2.2) * R * .9, cy + math.cos(am + 2.2) * R * .9, z - .004), v.u * .4, (200, 30, 30))


def v_crowbar(p):
    col = _col(p.get('color'), (150, 26, 24)); st = (80, 82, 88); v = Vox(.008)
    v.box(-.32, 0, -.014, .32, .028, .014, col)
    for (dx, dy) in ((.33, .02), (.355, .035), (.38, .055), (.392, .078), (.384, .098)): v.box(dx - .016, dy - .016, -.014, dx + .016, dy + .016, .014, col)
    v.box(.34, .1, -.016, .38, .116, -.004, st).box(.34, .1, .004, .38, .116, .016, st)
    v.box(-.36, 0, -.016, -.32, .02, .016, col).box(-.4, 0, -.018, -.36, .012, .018, st)
    for x in (-.2, -.05, .12, .24): v.box(x - .008, .024, -.004, x + .008, .032, .008, st)
    return v.boxes()


def v_flashlight(p):
    col = _col(p.get('color'), (40, 40, 46)); on = bool(_g(p, 'allumee', 'on', default=False)); v = Vox(.006)
    v.cylz(0, .02, .018, -.05, .1, col)
    for z in (.0, .03, .06): v.cylz(0, .02, .021, z - .004, z + .004, _sh(col, .7))
    v.cylz(0, .026, .027, -.09, -.05, _sh(col, 1.2)).cylz(0, .026, .029, -.096, -.088, OD.METAL).cylz(0, .026, .02, -.1, -.094, (255, 248, 220) if on else (150, 160, 170), em=3. if on else 0.)
    v.box(-.006, .036, -.03, .006, .044, -.012, (200, 40, 40))
    out = v.boxes()
    if on:
        for i in range(4):
            w = .05 + i * .07; out.append(glass(-w / 2, .025 - w * .35, -.13 - i * .12 - .06, w / 2, .025 + w * .35, -.13 - i * .12 + .06, (255, 246, 210), .08 - .016 * i))
    return out


def v_candle(p):
    wax = _col(p.get('color'), (236, 226, 196)); lit = bool(_g(p, 'allumee', 'on', default=True)); v = Vox(.006); out = []
    if _g(p, 'modele', default='pilier') == 'chandelier':
        v.cyl(0, 0, .05, 0, .016, OD.BRASS).cyl(0, 0, .02, .016, .045, OD.BRASS).cyl(0, 0, .01, .045, .175, OD.BRASS).cyl(0, 0, .03, .175, .184, OD.BRASS).cyl(0, 0, .012, .184, .344, wax)
        top = .344
    else:
        y0 = 0.
        if _g(p, 'bougeoir', default=True):
            v.cyl(0, 0, .058, 0, .012, OD.BRASS).cyl(0, 0, .058, .012, .02, OD.BRASS, r_in=.05).loop_y(.07, .024, 0, .008, .016, .004, OD.BRASS); y0 = .012
        h = float(_g(p, 'hauteur', default=.11))
        v.cyl(0, 0, .028, y0, y0 + h, wax).cyl(0, 0, .036, y0, y0 + .006, _sh(wax, .97))
        v.box(.024, y0 + h - .04, -.004, .032, y0 + h, .004, wax).box(-.026, y0 + h - .028, -.02, -.018, y0 + h, -.012, wax).box(.004, y0 + h - .05, -.032, .012, y0 + h, -.024, wax)
        v.cyl(0, 0, .02, y0 + h - .006, y0 + h, _sh(wax, .9))
        top = y0 + h
    v.box(-.002, top, -.002, .004, top + .012, .004, (30, 24, 20))
    out = v.boxes()
    if lit:
        out += Vox(.006).box(-.006, top + .01, -.006, .006, top + .03, .006, (255, 240, 180), 2.8).boxes()
        out.append(glass(-.01, top + .008, -.01, .01, top + .044, .01, (255, 150, 50), .55, 1.6))
    return out


def v_photo_frame(p):
    fr = _col(p.get('color'), (70, 46, 30)); W_, H_ = float(_g(p, 'largeur', default=.18)), float(_g(p, 'haut', default=.23))
    img = T.photo(str(_g(p, 'photo', default='portrait')), int(_g(p, 'seed', default=0)), 24, 30, bool(_g(p, 'raye', default=False)))
    wall = _g(p, 'mur', 'wall', default=False); y = float(_g(p, 'hauteur', 'at_y', default=1.5)) - H_ / 2 if wall else 0.
    v = Vox(.01)
    v.box(-W_ / 2, y, -.02, W_ / 2, y + H_, .0, fr).box(-W_ / 2 + .02, y + .02, -.024, W_ / 2 - .02, y + H_ - .02, -.02, _sh(fr, 1.3)).erase(-W_ / 2 + .03, y + .03, -.03, W_ / 2 - .03, y + H_ - .03, -.019)
    v.box(-W_ / 2 + .03, y + .03, -.014, W_ / 2 - .03, y + H_ - .03, -.006, (236, 230, 214))                     # passe-partout (cubes jusqu'à z = -0,02)
    if not wall: v.line((0, y + H_ * .7, .004), (0, .0, .1), .008, _sh(fr, .7))
    return v.boxes() + [tex(-W_ / 2 + .04, y + .04, -.0215, W_ / 2 - .04, y + H_ - .04, -.0205, '-z', img, (150, 150, 150))]


def v_plant(p):
    pot = _col(p.get('color'), (176, 92, 60)); s = float(_g(p, 'taille', 'size', default=1.)); sp = _g(p, 'espece', 'kind', default='monstera')
    g1, g2, g3 = (40, 110, 52), (62, 140, 70), (30, 90, 44); v = Vox(.02 * max(.6, s))
    v.cyl(0, 0, .17 * s, 0, .02 * s, _sh(pot, .75)).cyl(0, 0, .11 * s, .02 * s, .14 * s, pot).cyl(0, 0, .13 * s, .14 * s, .24 * s, pot).cyl(0, 0, .15 * s, .24 * s, .27 * s, _sh(pot, 1.1)).cyl(0, 0, .125 * s, .25 * s, .28 * s, (52, 36, 26))
    y0 = .27 * s
    if sp == 'cactus':
        v.cyl(0, 0, .05 * s, y0, y0 + .4 * s, (70, 140, 80)).box(.04 * s, y0 + .15 * s, -.025 * s, .12 * s, y0 + .2 * s, .025 * s, (70, 140, 80)).box(.08 * s, y0 + .2 * s, -.025 * s, .13 * s, y0 + .33 * s, .025 * s, (70, 140, 80))
        v.cyl(0, 0, .025 * s, y0 + .4 * s, y0 + .43 * s, (236, 80, 130))
    elif sp == 'sansevieria':
        for i, (dx, dz, h) in enumerate(((0, 0, .7), (-.06, .03, .55), (.06, -.02, .6), (.03, .06, .45), (-.04, -.05, .5), (.08, .05, .38))):
            v.box((dx - .025) * s, y0, (dz - .008) * s, (dx + .025) * s, y0 + h * s, (dz + .008) * s, g1 if i % 2 else g2).box((dx - .028) * s, y0 + h * s * .1, (dz - .01) * s, (dx - .022) * s, y0 + h * s * .95, (dz + .01) * s, (190, 190, 80))
    elif sp == 'ficus':
        v.line((0, y0, 0), (0, y0 + .6 * s, 0), .015 * s, (100, 72, 46)); rng = np.random.default_rng(int(_g(p, 'seed', default=1)))
        for i in range(22):
            a = rng.uniform(0, 6.283); r = rng.uniform(.0, .2); yy = rng.uniform(.5, .92)
            v.box(math.cos(a) * r * s - .03 * s, y0 + yy * s, math.sin(a) * r * s - .03 * s, math.cos(a) * r * s + .03 * s, y0 + (yy + .04) * s, math.sin(a) * r * s + .03 * s, [g1, g2, g3][i % 3])
    elif sp == 'fougere':
        for i in range(7):
            a = i * 6.283 / 7
            v.line((0, y0, 0), (math.cos(a) * .2 * s, y0 + .22 * s, math.sin(a) * .2 * s), .02 * s, g2 if i % 2 else g1).line((math.cos(a) * .2 * s, y0 + .22 * s, math.sin(a) * .2 * s), (math.cos(a) * .34 * s, y0 + .12 * s, math.sin(a) * .34 * s), .016 * s, g1)
    else:
        for i, (sx, sz, h, lx, lz) in enumerate(((-.06, .02, .55, -.24, .1), (.07, -.03, .62, .26, -.08), (.0, .07, .72, .03, .26), (-.03, -.07, .48, -.1, -.25), (.04, .04, .4, .22, .2))):
            v.line((sx * s, y0, sz * s), ((sx + lx * .5) * s, y0 + h * s, (sz + lz * .5) * s), .012 * s, g3)
            cx, cy, cz = (sx + lx * .6) * s, y0 + (h + .04) * s, (sz + lz * .6) * s
            v.box(cx - .09 * s, cy, cz - .075 * s, cx + .09 * s, cy + .02 * s, cz + .075 * s, g1 if i % 2 else g2)
            v.erase(cx - .01 * s, cy - .01, cz + .02 * s, cx + .01 * s, cy + .03, cz + .075 * s)                                   # découpe de monstera
            v.box(cx + (.06 if lx >= 0 else -.12) * s, cy - .02 * s, cz - .04 * s, cx + (.12 if lx >= 0 else -.06) * s, cy, cz + .04 * s, g3)
    return v.boxes()


def v_bag(p):
    col = _col(p.get('color'), (120, 60, 40)); mod = _g(p, 'modele', default='main'); dk = _sh(col, .7); v = Vox(.015)
    if mod == 'dos':
        v.box(-.15, 0, -.08, .15, .42, .08, col).box(-.13, .04, -.11, .13, .22, -.08, dk).box(-.04, .42, -.01, .04, .44, .01, dk)
        for x in (-.11, .07): v.box(x, .05, .08, x + .04, .39, .1, dk)
        return v.boxes()
    if mod == 'cabas':
        v.box(-.2, 0, -.07, .2, .34, .07, col)
        for x in (-.12, .12): v.line((x, .34, -.06), (x, .52, -.04), .012, dk).line((x, .52, -.04), (0, .56, -.04), .012, dk)
        return v.boxes()
    v.box(-.14, 0, -.06, .14, .12, .06, col).box(-.12, .12, -.055, .12, .18, .055, col).box(-.126, .09, -.068, .126, .18, -.06, dk).box(-.016, .09, -.074, .016, .114, -.066, OD.BRASS)
    for x in (-.07, .07): v.line((x, .18, 0), (x * .5, .25, 0), .01, dk)
    v.line((-.035, .25, 0), (.035, .25, 0), .01, dk)
    return v.boxes()


def v_suitcase(p):
    mod = _g(p, 'modele', default='rigide'); v = Vox(.02)
    if mod == 'cuir':
        col = _col(p.get('color'), (110, 66, 40)); v.box(-.32, 0, -.1, .32, .44, .1, col).box(-.33, .2, -.11, .33, .24, .11, _sh(col, .7))
        for x in (-.18, .18): v.box(x - .02, 0, -.11, x + .02, .44, .11, (60, 36, 22))
        for x in (-.34, .3):
            for y in (0, .4): v.box(x, y, -.11, x + .04, y + .04, .11, OD.BRASS)
        v.box(-.08, .44, -.02, .08, .48, .02, (60, 36, 22))
        return v.boxes() + [tex(-.27, .08, -.112, -.19, .14, -.11, '-z', T.label('PARIS', '', (230, 200, 80), (40, 40, 90), 16, 12), (230, 200, 80))]
    col = _col(p.get('color'), (60, 90, 140)); dk = _sh(col, .7)
    v.box(-.2, .04, -.12, .2, .62, .12, col)
    for x in (-.14, -.06, .02, .1): v.box(x, .08, -.14, x + .02, .58, -.12, _sh(col, 1.2))
    v.box(-.22, .3, -.14, .22, .32, .14, (30, 30, 34))
    for x in (-.2, .16):
        for y in (.04, .58): v.box(x, y, -.14, x + .04, y + .04, .14, dk)
    for x in (-.18, .14):
        for z in (-.1, .08): v.box(x, 0, z, x + .04, .04, z + .02, (24, 24, 26))
    v.box(-.06, .5, -.16, .06, .52, -.12, (30, 30, 34))
    up = _g(p, 'poignee', default='rentree') == 'sortie'; ht = .42 if up else .04
    v.box(-.1, .62, .08, -.08, .62 + ht, .1, (150, 152, 160)).box(.08, .62, .08, .1, .62 + ht, .1, (150, 152, 160)).box(-.1, .62 + ht, .08, .1, .64 + ht, .1, (30, 30, 34))
    out = v.boxes()
    et = _g(p, 'etiquette', default='M. ROUX - CH 313')
    if et: out.append(tex(.12, .3, -.162, .19, .4, -.16, '-z', T.label(str(et).split(' - ')[0], (str(et).split(' - ') + [''])[1], (226, 214, 180), (30, 30, 60), 16, 22), (226, 214, 180)))
    out.append(tex(-.15, .38, -.142, -.07, .46, -.14, '-z', T.label('NY', '', (240, 190, 60), (180, 30, 30), 16, 16, False), (240, 190, 60)))
    return out


VOX = {'od_phone_rotary': v_phone_rotary, 'od_phone_desk': v_phone_desk, 'od_smartphone': v_smartphone, 'od_switchboard': v_switchboard, 'od_cup': v_cup, 'od_mug': v_mug,
       'od_glass': v_glass, 'od_bottle': v_bottle, 'od_plate': v_plate, 'od_cutlery': v_cutlery, 'od_couvert': v_couvert, 'od_book': v_book, 'od_notebook': v_notebook,
       'od_paper': v_paper, 'od_keys': v_keys, 'od_desk_lamp': v_desk_lamp, 'od_bedside_lamp': v_bedside_lamp, 'od_nightstand': v_nightstand, 'od_laptop': v_laptop,
       'od_monitor': v_monitor, 'od_computer': v_computer, 'od_tv': v_tv, 'od_tv_crt': v_tv_crt, 'od_radio': v_radio, 'od_clock': v_clock, 'od_crowbar': v_crowbar,
       'od_flashlight': v_flashlight, 'od_candle': v_candle, 'od_photo_frame': v_photo_frame, 'od_plant': v_plant, 'od_bag': v_bag, 'od_suitcase': v_suitcase}


def _raw(kind, p):
    """versions VOXEL des anciens décors groupés (`cups`, `bottles`, `note`) sous la clé"""
    if kind == 'cups':
        y = float(p.get('y', .8)); out = []
        for dx, dz in ((-.12, -.03), (.13, .05)):
            for b in v_cup({'vapeur': True, 'color': p.get('color')}): b.lo = b.lo + np.array([dx, y, dz], np.float32); b.hi = b.hi + np.array([dx, y, dz], np.float32); out.append(b)
        return out
    if kind == 'bottles':
        rng = np.random.default_rng(int(p.get('seed', 0)) * 23 + 7); out = []; mods = ('vin', 'biere', 'vin', 'eau')
        for k_ in range(int(p.get('count', 4))):
            x = float(rng.uniform(-.22, .22)); z = float(rng.uniform(-.18, .18))
            for b in v_bottle({'modele': mods[k_ % 4]}): b.lo = b.lo + np.array([x, 0, z], np.float32); b.hi = b.hi + np.array([x, 0, z], np.float32); out.append(b)
        return out
    if kind == 'note':
        y = float(p.get('y', 1.0)); w = float(p.get('w', .3)); lines_ = p.get('text') if isinstance(p.get('text'), list) else [p.get('text', '')]; s = w / .21
        out = v_paper({'texte': lines_, 'entete': False, 'mur': not p.get('flat'), 'hauteur': 0.})
        for b in out:
            sc = np.array([s, 1, s], np.float32) if p.get('flat') else np.array([s, s, 1], np.float32)
            b.lo = b.lo * sc + np.array([0, y, 0], np.float32); b.hi = b.hi * sc + np.array([0, y, 0], np.float32)
        return out
    return None


def native_boxes(kind, p):
    """boîtes de la version VOXEL d'un objet détaillé (repère local, face avant vers -z), ou None"""
    if kind.startswith('_raw:'): out = _raw(kind[5:], p)
    else:
        fn = VOX.get(kind); out = fn(dict(p or {})) if fn else None
    return fix_plates(out) if out is not None else None


def natives(boxes):
    """boîtes PS1 posées -> (indices à ne pas convertir, boîtes VOXEL natives posées au même endroit, même quart de tour, même hauteur). Rien si aucun marqueur."""
    from ..engines.pixel3d import sets as S
    hide = set(); out = []
    for (i, kind, p, x, y, z, rot, n) in OD.read_markers(boxes):
        nb = native_boxes(kind, p)
        if nb is None: continue
        hide.update(range(i, i + 2 + n))
        out += S.place(nb, x, z, rot, y)
    return hide, out


def split(boxes):
    """une liste de boîtes PS1 (objets d'un plan, éléments mobiles) -> (boîtes à convertir telles quelles, boîtes natives VOXEL) ; la même liste sans objet détaillé"""
    hide, nat = natives(boxes)
    if not hide: return list(boxes), []
    return [b for i, b in enumerate(boxes) if i not in hide], nat


# ================================================================== held objects (VOXEL native), in the PS1 hand frame P(lat, up, fwd), f = +1
def _P(lat, up, fwd): return (lat, up, fwd)


def hv_handset(col, cfg):
    col = _col(col, (30, 30, 34)); dk = _sh(col, .55); v = Vox(.008)
    ear = np.array((-.07, .2, -.03)); mic = np.array((-.075, -.1, .1))              # VOXEL : le poing fait 16 x 20 cm ; écouteur au-dessus, micro en dessous et devant, sinon le poing cache tout (planche)
    v.box(ear[0] - .016, ear[1] - .035, ear[2] - .033, ear[0] + .016, ear[1] + .035, ear[2] + .033, col).box(ear[0] - .024, ear[1] - .024, ear[2] - .024, ear[0] - .016, ear[1] + .024, ear[2] + .024, dk)
    v.box(mic[0] - .017, mic[1] - .032, mic[2] - .032, mic[0] + .017, mic[1] + .032, mic[2] + .032, col).box(mic[0] - .025, mic[1] - .022, mic[2] - .022, mic[0] - .017, mic[1] + .022, mic[2] + .022, dk)
    v.line(ear + (.012, -.03, .03), mic + (.012, .03, -.03), .02, col)
    coil(v, [mic + (0, -.035, 0), (-.1, -.15, .1), (-.08, -.3, .08), (-.06, -.42, .04)], dk, .006)
    return v.boxes(), []


def hv_smartphone(col, cfg, faces='holder'):
    case = _col(col, (44, 48, 66)); scr = OD._screen_img(cfg); v = Vox(.004)
    v.box(-.037, -.016, .045, .037, .136, .054, case)
    v.box(.037, .07, .048, .041, .11, .052, _sh(case, .7)).box(-.041, .06, .048, -.037, .09, .052, _sh(case, .7))
    out = []
    if faces in ('holder', 'both'): out.append(tex(-.033, -.01, .0435, .033, .13, .0445, '-z', scr, (20, 24, 40), .9))
    if faces in ('out', 'both'): out.append(tex(-.033, -.01, .0545, .033, .13, .0555, '+z', scr, (20, 24, 40), .9))
    if faces == 'holder':
        v.box(-.03, .1, .054, -.006, .13, .058, _sh(case, .6))                                  # bloc photo au dos (vu de face : en haut à gauche, comme vu de derrière la main)
        for (x, y) in ((-.026, .118), (-.016, .118), (-.026, .106)): v.box(x - .004, y - .004 + .004, .058, x + .004, y + .004 + .004, .06, (14, 14, 18))
    if faces == 'out':
        v.box(-.03, .1, .04, -.006, .13, .045, _sh(case, .6))
    return v.boxes() + out, ([((0, .09, -.06), (.55, .62, 1.), .3, .8)] if faces != 'out' else [])


def hv_cup(col, cfg):
    col = _col(col, (238, 236, 230)); v = Vox(.008); cx, cy, cz = -.035, -.01, .075
    v.cyl(cx, cz, .036, cy, cy + .01, col).cyl(cx, cz, .043, cy + .01, cy + .066, col).cyl(cx, cz, .044, cy + .058, cy + .066, (200, 160, 60))
    v.cyl(cx, cz, .036, cy + .066, cy + .072, (70, 40, 22)).cyl(cx, cz, .045, cy + .066, cy + .072, col, r_in=.037)
    v.loop_y(cx + .046, cy + .036, cz, .012, .024, .006, col)
    out = v.boxes()
    if cfg.get('vapeur', True):
        for i in range(4): out.append(glass(cx - .008 + .01 * math.sin(i * 1.7), cy + .085 + .026 * i, cz - .008, cx + .008 + .01 * math.sin(i * 1.7), cy + .101 + .026 * i, cz + .008, (236, 238, 242), .32 - .06 * i))
    return out, []


def hv_mug(col, cfg):
    col = _col(col, (60, 120, 150)); v = Vox(.008); cx, cy, cz = -.045, -.03, .07
    v.cyl(cx, cz, .048, cy, cy + .104, col).cyl(cx, cz, .04, cy + .096, cy + .104, (66, 38, 20)).loop_y(cx + .05, cy + .054, cz, .018, .034, .01, col)
    pr = T.mug_print(str(cfg.get('texte', '')), str(cfg.get('motif', 'coeur')), col)
    return v.boxes() + [tex(cx - .028, cy + .024, cz + .0485, cx + .028, cy + .08, cz + .0505, '+z', pr, col)], []


def hv_glass(col, cfg, wine=False):
    gl = _col(col, (190, 206, 216)); v = Vox(.006)
    if wine:
        cx, cz = 0, .06
        v.cyl(cx, cz, .03, -.034, -.028, gl).cyl(cx, cz, .005, -.028, .03, gl).cyl(cx, cz, .028, .03, .062, OD.LIQ.get(cfg.get('contenu', 'vin'), OD.LIQ['vin']))
        return v.boxes() + [glass(cx - .036, .03, cz - .036, cx + .036, .13, cz + .036, gl, .28)], []
    cx, cy, cz = -.02, -.02, .07
    v.cyl(cx, cz, .036, cy, cy + .012, gl).cyl(cx, cz, .03, cy + .012, cy + .072, OD.LIQ.get(cfg.get('contenu', 'eau'), OD.LIQ['eau']))
    return v.boxes() + [glass(cx - .037, cy + .012, cz - .037, cx + .037, cy + .1, cz + .037, gl, .28)], []


def hv_bottle(col, cfg):
    mod = cfg.get('modele', 'vin'); g_, liq, t1, t2 = OD.BOTTLES.get(mod, OD.BOTTLES['vin']); gl = _col(col, g_); v = Vox(.008); w = .074; cz = .05; y0 = -.24
    v.cyl(0, cz, w / 2, y0, y0 + .2, gl).cyl(0, cz, w * .36, y0 + .2, y0 + .216, gl).cyl(0, cz, w * .2, y0 + .216, y0 + .3, gl).cyl(0, cz, w * .23, y0 + .29, y0 + .316, (150, 20, 30))
    return v.boxes() + [tex(-w * .36, y0 + .044, cz + w / 2 + .004, w * .36, y0 + .128, cz + w / 2 + .006, '+z', T.label(str(cfg.get('etiquette', t1)), str(cfg.get('sous', t2))), (236, 226, 200))], []


def hv_book(col, cfg, opened=False):
    col = _col(col, (120, 30, 36)); v = Vox(.006)
    if opened:
        v.box(-.215, -.01, .118, .095, .21, .13, col).box(-.21, -.005, .108, .09, .205, .118, (232, 226, 206)).box(-.07, -.005, .104, -.05, .205, .108, (200, 190, 166))
        return v.boxes() + [tex(-.205, .0, .1025, .085, .2, .1035, '-z', T.open_pages(T.lines(cfg.get('texte'))), (238, 232, 212))], []
    v.box(-.105, -.03, .055, .045, .19, .085, col).box(-.1, -.026, .058, .044, .186, .082, (232, 226, 206))
    return v.boxes() + [tex(-.1, -.025, .0855, .04, .185, .0865, '+z', T.book_cover(str(cfg.get('titre', 'LE SILENCE')), str(cfg.get('auteur', 'M. ARNAUD')), col), col)], []


def hv_notebook(col, cfg):
    col = _col(col, (40, 44, 60)); v = Vox(.004)
    v.box(-.06, -.005, .084, .04, .145, .096, col)
    for i in range(9): v.box(-.056 + i * .0105, .144, .082, -.052 + i * .0105, .152, .098, (170, 172, 180))
    return v.boxes() + [tex(-.057, -.002, .0825, .037, .142, .0835, '-z', T.notebook_page(T.lines(cfg.get('texte'))), (240, 238, 228)),
                        tex(-.06, -.005, .0965, .04, .145, .0975, '+z', T.notebook_cover(col), col)], []


def hv_paper(col, cfg):
    pap = _col(col, (238, 236, 228))
    img = T.paper(T.lines(cfg.get('texte'), ('RAPPORT DE NUIT', '', '02:13 APPEL CH 313', '02:14 LIGNE COUPEE', '02:16 PERSONNE')), str(cfg.get('titre', '')), entete=bool(cfg.get('entete', True)), surligne=str(cfg.get('surligne', '')))
    v = Vox(.004); v.box(-.124, -.048, .128, .084, .248, .132, pap)
    return v.boxes() + [tex(-.123, -.047, .1265, .083, .247, .1275, '-z', img, pap, .12), tex(-.123, -.047, .1325, .083, .247, .1335, '+z', img, pap, .12)], []


def hv_keys(col, cfg):
    br = _col(col, OD.BRASS); v = Vox(.004)
    v.box(-.002, -.066, .036, .002, -.034, .064, OD.METAL)
    for dx, cc, L in ((-.012, br, .06), (.0, OD.METAL, .055), (.014, (150, 152, 160), .04)):
        v.box(dx - .01, -.085, .046, dx + .01, -.065, .052, cc).box(dx - .004, -.085 - L, .048, dx + .004, -.085, .052, cc).box(dx + .004, -.09 - L * .6, .048, dx + .01, -.082 - L * .6, .052, cc)
    tg = cfg.get('etiquette', '313'); out = []
    if tg:
        v.box(-.048, -.144, .048, -.012, -.096, .056, (190, 50, 36))
        out = [tex(-.046, -.142, .0565, -.014, -.098, .0575, '+z', T.tag(str(tg), 14, 18), (190, 50, 36)), tex(-.046, -.142, .0465, -.014, -.098, .0475, '-z', np.ascontiguousarray(T.tag(str(tg), 14, 18)[:, ::-1]), (190, 50, 36))]   # 6/11/2026 : le texte de l'étiquette se lit à l'endroit des DEUX côtés (le verso est retourné)
    return v.boxes() + out, []


def hv_crowbar(col, cfg):
    col = _col(col, (150, 26, 24)); st = (80, 82, 88); v = Vox(.008)
    v.box(-.014, -.1, .006, .014, .5, .034, col)
    for (dy, df) in ((.52, .03), (.545, .045), (.565, .07), (.575, .095), (.565, .118)): v.box(-.013, dy - .015, df - .015, .013, dy + .015, df + .015, col)
    v.box(.002, .54, .118, .014, .56, .152, st).box(-.014, .54, .118, -.002, .56, .152, st)
    v.box(-.013, -.15, .013, .013, -.09, .043, st).box(-.01, -.175, .018, .01, -.145, .052, st).box(-.018, -.08, .002, .018, .02, .038, (30, 30, 34))
    for y in (.12, .3, .42): v.box(.014, y - .01, .014, .018, y + .01, .026, st)
    return v.boxes(), []


def hv_flashlight(col, cfg):
    col = _col(col, (40, 40, 46)); v = Vox(.006)
    v.cylz(0, 0, .018, -.015, .135, col)
    for z in (.03, .06, .09): v.cylz(0, 0, .021, z - .004, z + .004, _sh(col, .7))
    v.cylz(0, 0, .026, .13, .17, _sh(col, 1.2)).cylz(0, 0, .028, .168, .176, OD.METAL).cylz(0, 0, .02, .174, .18, (255, 248, 220), em=3.)
    v.box(-.006, .016, .072, .006, .024, .09, (200, 40, 40))
    out = v.boxes()
    if cfg.get('faisceau', True):
        for i in range(4):
            w = .05 + i * .06; out.append(glass(-w / 2, -w * .4, .2 + i * .12, w / 2, w * .4, .31 + i * .12, (255, 246, 210), .07 - .015 * i))
    return out, [((0, 0, 2.5), (1, .95, .82), 2.4 * .45, 3.6 * 1.3)]


def hv_candle(col, cfg):
    wax = _col(col, (236, 226, 196)); v = Vox(.006); cz = .05
    v.cyl(0, cz, .056, -.016, -.004, OD.BRASS).loop_y(.06, -.002, cz, .008, .016, .004, OD.BRASS).cyl(0, cz, .026, -.004, .1, wax).box(.018, .06, cz - .004, .028, .1, cz + .004, wax)
    v.box(-.002, .1, cz - .002, .004, .112, cz + .004, (30, 24, 20))
    out = v.boxes() + Vox(.006).box(-.006, .11, cz - .006, .006, .13, cz + .006, (255, 240, 180), 2.8).boxes() + [glass(-.01, .108, cz - .01, .01, .146, cz + .01, (255, 150, 50), .55, 1.6)]
    return out, [((0, .3, .1), (1, .62, .3), .9, 2.4)]


def hv_photo_frame(col, cfg):
    fr = _col(col, (70, 46, 30)); img = T.photo(str(cfg.get('photo', 'portrait')), int(cfg.get('seed', 0)), 24, 30, bool(cfg.get('raye', False))); v = Vox(.01)
    v.box(-.11, -.015, .068, .07, .215, .09, fr).box(-.09, .005, .09, .05, .195, .094, (236, 230, 214)).box(-.09, -.0, .062, .05, .18, .068, (150, 120, 80))
    return v.boxes() + [tex(-.07, .025, .0945, .03, .175, .0955, '+z', img, (150, 150, 150))], []


def hv_bag(col, cfg):
    col = _col(col, (120, 60, 40)); dk = _sh(col, .7); v = Vox(.015)
    v.box(-.14, -.3, -.06, .14, -.18, .06, col).box(-.12, -.18, -.055, .12, -.12, .055, col).box(-.126, -.21, .06, .126, -.12, .068, dk).box(-.016, -.18, .066, .016, -.156, .074, OD.BRASS)
    v.line((-.07, -.12, 0), (-.035, -.045, 0), .008, dk).line((.07, -.12, 0), (.035, -.045, 0), .008, dk).line((-.035, -.045, 0), (.035, -.045, 0), .008, dk)
    return v.boxes(), []


def hv_suitcase(col, cfg):
    col = _col(col, (60, 90, 140)); dk = _sh(col, .7); v = Vox(.02)
    v.box(-.12, -.65, -.2, .12, -.07, .2, col).box(-.124, -.38, -.204, .124, -.36, .204, (30, 30, 34))
    for dz in (-.18, .16): v.box(-.12, -.62, dz, .12, -.1, dz + .02, _sh(col, 1.2))
    v.box(-.016, -.07, -.05, .016, -.04, .05, (30, 30, 34))
    return v.boxes(), []


HELD_VOX = {'od_handset': hv_handset, 'od_smartphone': hv_smartphone, 'od_smartphone_montre': lambda c, g: hv_smartphone(c, g, 'out'), 'od_cup': hv_cup, 'od_mug': hv_mug,
            'od_glass': hv_glass, 'od_wine_glass': lambda c, g: hv_glass(c, g, True), 'od_bottle': hv_bottle, 'od_book': hv_book, 'od_book_open': lambda c, g: hv_book(c, g, True),
            'od_notebook': hv_notebook, 'od_paper': hv_paper, 'od_keys': hv_keys, 'od_crowbar': hv_crowbar, 'od_flashlight': hv_flashlight, 'od_candle': hv_candle,
            'od_photo_frame': hv_photo_frame, 'od_bag': hv_bag, 'od_suitcase': hv_suitcase}


def resolve_held(item):
    """nom tenu écrit -> (nom détaillé, réglages) ou (None, None) : un nom `od_*` toujours, un nom d'avant seulement sous la clé `objets`"""
    if item in HELD_VOX: return item, dict(OD._cfg(item))
    st = OD.active()
    if st is not None and st.get('tenus') and item in OD.UP_HELD:
        name, cfg = OD.UP_HELD[item]; c = dict(cfg); c.update(OD._cfg(name)); c.update(OD._cfg(item)); return name, c
    return None, None


def _hexc(c): return (int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])


def held_contract(item, col=None, mirror=False):
    """objet tenu -> {"boxes": [...], "decals": [...], "lights": [...]} dans le repère de la paume de VOXEL (x = -lat, y = haut, z = avant, x HOLD_K) ; None si l'objet n'a pas de version détaillée.
    `mirror=True` : x = +lat (la main principale de PS1 jouée par `handL` de VOXEL dans les scènes converties, voir add_held)"""
    name, cfg = resolve_held(item)
    if name is None: return None
    if col is None and cfg.get('couleur') is not None: col = tuple(cfg['couleur'])
    fn = HELD_VOX[name]
    if name == 'od_smartphone' and cfg.get('_faces'): bx, lights = hv_smartphone(col, cfg, cfg['_faces'])
    else: bx, lights = fn(tuple(col) if col else None, cfg)
    bx = fix_plates(bx)
    sx = 1. if mirror else -1.                                                                    # main droite de PS1 = handR de VOXEL (x < 0) ; main gauche : pas de miroir
    push = np.array([0., 0., FRONT.get(name, 0.)])
    boxes, decals = [], []
    for b in bx:
        lo, hi = np.asarray(b.lo, float) + push, np.asarray(b.hi, float) + push; c = (lo + hi) / 2; sz = np.abs(hi - lo)
        if (sz <= 1e-6).any(): continue
        o = dict(x=round(float(c[0] * sx * HOLD_K), 4), y=round(float(c[1] * HOLD_K), 4), z=round(float(c[2] * HOLD_K), 4), w=round(float(sz[0] * HOLD_K), 4), h=round(float(sz[1] * HOLD_K), 4), d=round(float(sz[2] * HOLD_K), 4), color=_hexc(np.asarray(b.col) * 255))
        if b.emis: o['emis'] = round(float(b.emis), 3)
        if getattr(b, 'mat', 0) == M_TRANSLUCENT: o['alpha'] = round(max(.05, 1. - float(b.dissolve)), 3)
        if not b.tex: boxes.append(o)
        for key, tx in (b.tex or {}).items():
            tx = np.asarray(tx)
            n = {4: (0, -1), 5: (0, 1), 0: (-1, 0), 1: (1, 0)}.get(key)
            if n is None or tx.ndim != 3: continue
            e = .003
            if key in (4, 5): pc = (c[0], c[1], (lo[2] - e) if key == 4 else (hi[2] + e)); w = sz[0]
            else: pc = ((lo[0] - e) if key == 0 else (hi[0] + e), c[1], c[2]); w = sz[2]
            nx, nz = n[0] * sx, n[1]
            rgba = np.ascontiguousarray(tx.astype(np.uint8)[::-1, :, :4])
            decals.append(dict(x=round(float(pc[0] * sx * HOLD_K), 4), y=round(float(pc[1] * HOLD_K), 4), z=round(float(pc[2] * HOLD_K), 4), w=round(float(w * HOLD_K), 4), h=round(float(sz[1] * HOLD_K), 4),
                               ry=round(math.atan2(nx, nz), 4), tw=int(rgba.shape[1]), th=int(rgba.shape[0]), rgba=base64.b64encode(rgba.tobytes()).decode('ascii'),
                               **({'emis': round(float(b.texemis), 3)} if b.texemis else {})))
    lt = [dict(at=[round(p_[0] * sx * HOLD_K, 3), round(p_[1] * HOLD_K, 3), round(p_[2] * HOLD_K, 3)], color=_hexc([int(v * 255) for v in c_]), i=round(float(pw) * 2.2, 3), dist=round(float(rd) * 1.5, 2)) for (p_, c_, pw, rd) in lights]
    return dict(name=name, boxes=boxes, decals=decals, lights=lt)


# ================================================================== contract: held object, frame by frame (from_ps1, under the key or with an `od_*` name)
def add_held(casts, baked, looks, ids):
    """casts[id]["held"] = {"items": [{boxes, decals, lights, side}...]} pour chaque personnage qui tient un objet détaillé ; rend {id: [(nom, gauche)...]} (vide = rien)"""
    out = {}
    for a in ids:
        d = casts.get(a) or {}
        if d.get('costume'): continue                                                              # costumes XVIIIe : leurs accessoires ont leur propre peintre
        lk = looks.get(a) or {}; col = tuple(lk['hold_color']) if lk.get('hold_color') else None
        seen = []
        for bs in baked:
            for fr in bs.frames:
                s = fr['samp'].get(a)
                if not s: continue
                it = s.get('hold')
                if not it or it == 'none': continue
                left = bool((s.get('rig') or {}).get('left'))
                if (it, left) not in seen and resolve_held(it)[0] is not None: seen.append((it, left))
        if not seen: continue
        items = []
        for it, left in seen:                                                                       # scène convertie : le bras des gestes de la main principale de PS1 est `handL` de VOXEL
            hc = held_contract(it, col, mirror=not left)                                            # (film_unified.js `arms`, b_costumes) ; l'image VOXEL étant le miroir de PS1, l'objet
            hc['side'] = 'R' if left else 'L'; hc['item'] = it; items.append(hc)                    # y garde son côté extérieur (x = +lat). Main gauche de PS1 (`side: left`) : `handR`, x = -lat
        d['held'] = dict(items=items)
        bx = d.get('bx')
        if isinstance(bx, dict) and bx.get('hold'):                                              # l'objet tenu « figé » de b_chars est remplacé par la piste image par image
            bx.pop('hold', None); bx.pop('hold_lights', None)
            if not bx: d.pop('bx', None)
        out[a] = seen
    return out


def add_stage_held(stage, held_map, frames, i0, e1, n):
    """stage["held"] = {id: [index de l'objet tenu par image, -1 = rien]}"""
    tr = {}
    for a, seen in held_map.items():
        if a not in (stage.get('actors') or {}): continue
        row = []
        for j in range(i0, e1):
            s = frames[min(j, n - 1)]['samp'].get(a) or {}
            it = s.get('hold'); left = bool((s.get('rig') or {}).get('left'))
            row.append(seen.index((it, left)) if (it, left) in seen else -1)
        if any(v >= 0 for v in row): tr[a] = row
    if tr: stage['held'] = tr


# ================================================================== lots d'objets en fichiers séparés (version VOXEL) : `b_objets_<lot>.py` de ce dossier, découverts tout seuls
class Registre:
    """ce qu'un lot VOXEL appelle dans `enregistrer(R)` :
        R.objet('od_grille_pain', fn)        fn(p) -> boîtes PS1-repère (B(...), Vox(...).boxes(), tex(...), glass(...)), face avant vers -z
        R.tenu('od_grille_pain', fn)         fn(col, cfg) -> (boîtes dans le repère de la main P(lat, haut, avant), lumières [(pos, couleur, puissance, rayon)])"""
    def __init__(self, source): self.source = source; self.noms = []

    def objet(self, kind, fn):
        if kind in VOX: raise ValueError(f'[objets voxel] {self.source} : « {kind} » déjà pris')
        VOX[kind] = fn; self.noms.append(kind)

    def tenu(self, name, fn):
        if name in HELD_VOX: raise ValueError(f'[objets voxel] {self.source} : « {name} » déjà pris')
        HELD_VOX[name] = fn; self.noms.append(name)


LOTS = []


def _load_lots():
    import importlib, pkgutil, os
    here = os.path.dirname(os.path.abspath(__file__))
    for m in sorted(pkgutil.iter_modules([here]), key=lambda m: m.name):
        if not m.name.startswith('b_objets_'): continue
        try:
            mod = importlib.import_module(f'{__package__}.{m.name}')
            if hasattr(mod, 'enregistrer'):
                R = Registre(m.name); mod.enregistrer(R); LOTS.append((m.name, R.noms))
        except Exception as e:
            print(f'[objets voxel] lot « {m.name} » non chargé : {type(e).__name__} : {e}')


_load_lots()
