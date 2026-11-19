"""OBJETS DÉTAILLÉS, LOT A « cuisine et salle de bain », VERSION VOXEL NATIVE (la version PS1 est engines/pixel3d/objets_cuisine.py).

Même plan, mêmes dimensions, mêmes réglages et MÊMES images (dessinées dans objets_cuisine.py) ; ici chaque objet est sculpté en cubes : les objets ronds
(bouilloire, casserole, bol, théière, verseuse) sont des solides de révolution cube par cube (`lathe`), creux pour de vrai au-dessus de leur contenu ;
le verre (verseuse, verre à dents, couvercle, vitre du micro-ondes) est une coque de cubes translucides ; seuls les écrans, étiquettes, graduations
et dessus peints gardent une image (décalcomanie), posée AU RAS du volume (`face`), jamais dedans.
Découvert tout seul par b_objets._load_lots (fichier `b_objets_<lot>.py`) : aucune ligne écrite ailleurs. Rien d'aléatoire, aucune horloge."""
import math
import numpy as np
from ..engines.pixel3d.r3d import B
from ..engines.pixel3d import objets as OD, objets_tex as T, objets_cuisine as K
from .b_objets import Vox, tex, glass, M_TRANSLUCENT

_g, _col, _sh = OD._g, OD._col, OD._sh
STEEL, DARK, WHITE, CERAM = K.STEEL, K.DARK, K.WHITE, K.CERAM


# ================================================================== sculpting helpers
def lathe(v, cx, cz, prof, col, hollow_from=None, wall=0., em=0.):
    """solide de révolution d'axe y : prof = [(y, rayon), ...] (y croissant), rayon interpolé rangée par rangée ; au-dessus de `hollow_from`, creux
    (paroi d'épaisseur `wall`) : bol, casserole, poêle"""
    ys = [q[0] for q in prof]; rs = [q[1] for q in prof]
    for j in v._r(ys[0], ys[-1]):
        y = v.c(j); r = float(np.interp(y, ys, rs))
        r_in = r - wall if (hollow_from is not None and y >= hollow_from) else -1.
        for i in v._r(cx - r, cx + r):
            for k in v._r(cz - r, cz + r):
                d = math.hypot(v.c(i) - cx, v.c(k) - cz)
                if r_in <= d <= r + v.u * .2: v.put(i, j, k, col, em)
    return v


def paint(v, x0, y0, z0, x1, y1, z1, col, em=0.):
    """recolore les cubes DÉJÀ là dans une boîte (liseré, reflet, filet doré) : rien n'est ajouté, le volume ne bouge pas"""
    for i in v._r(x0, x1):
        for j in v._r(y0, y1):
            for k in v._r(z0, z1):
                if (i, j, k) in v.v: v.put(i, j, k, col, em)
    return v


def paint_disc(v, cx, cz, r, y0, y1, col, r_in=-1.):
    """recolore les cubes déjà là dans un disque (ou un anneau) horizontal : contenu d'un bol, liseré, bord"""
    for (i, j, k) in list(v.v):
        if y0 - 1e-6 <= v.c(j) <= y1 + 1e-6 and r_in <= math.hypot(v.c(i) - cx, v.c(k) - cz) <= r: v.put(i, j, k, col)
    return v


def face(v, f, a0, a1, b0, b1):
    """coordonnée de la face extérieure des cubes occupés dans une fenêtre, pour y poser une image au ras du volume :
    f '-z' / '+z' (fenêtre a = x, b = y), '+x' / '-x' (a = z, b = y), '+y' (a = x, b = z)"""
    u = v.u; best = None
    for (i, j, k) in v.v:
        x, y, z = (i + .5) * u, (j + .5) * u, (k + .5) * u
        if f in ('-z', '+z'): ok, val = a0 <= x <= a1 and b0 <= y <= b1, (k if f == '-z' else k + 1)
        elif f in ('-x', '+x'): ok, val = a0 <= z <= a1 and b0 <= y <= b1, (i if f == '-x' else i + 1)
        else: ok, val = a0 <= x <= a1 and b0 <= z <= b1, j + 1
        if not ok: continue
        if best is None or (val < best if f[0] == '-' else val > best): best = val
    return (best if best is not None else 0) * u


def glassify(boxes, a=.3):
    """boîtes -> cubes translucides (alpha `a` dans le contrat VOXEL)"""
    for b in boxes: b.mat = M_TRANSLUCENT; b.dissolve = 1. - a; b.cast = False
    return boxes


def shift(bx, dx=0., dy=0., dz=0.):
    d = np.array([dx, dy, dz], np.float32)
    for b in bx: b.lo = b.lo + d; b.hi = b.hi + d
    return bx


def steam(x, y, z, n=4, s=.008, step=.026, a=.34):
    return [glass(x - s + .01 * math.sin(i * 2.1 + .4), y + step * i, z - s, x + s + .01 * math.sin(i * 2.1 + .4), y + step * i + 2 * s, z + s, (236, 238, 242), a - .055 * i) for i in range(n)]


# ================================================================== the objects (VOXEL)
def v_kettle(p):
    on = bool(_g(p, 'allumee', 'on', default=False)); lvl = float(_g(p, 'niveau', default=.6))
    if _g(p, 'modele', default='electrique') == 'gaz': return _kettle_gas(p, on)
    col = _col(p.get('color'), WHITE); dk = DARK; v = Vox(.006)
    v.cyl(0, 0, .095, 0, .02, dk)
    lathe(v, 0, 0, [(.02, .08), (.032, .086), (.1, .086), (.1001, .081), (.17, .081), (.1701, .075), (.205, .075), (.2051, .069), (.222, .069)], col)      # trois pans droits (pas une pente : une pente en cubes fait une marche par rangée, qui scintille sous la lumière)
    v.cyl(0, 0, .062, .222, .23, _sh(col, .9)).cyl(0, 0, .05, .23, .236, _sh(col, .96))
    v.box(-.096, .18, -.024, -.066, .222, .024, col).box(-.11, .2, -.02, -.09, .23, .02, col).box(-.118, .222, -.016, -.104, .232, .016, _sh(col, .9))
    v.box(.066, .196, -.017, .106, .222, .017, dk).box(.1, .059, -.017, .126, .222, .017, dk).box(.07, .055, -.017, .106, .075, .017, dk)
    v.box(.126, .074, -.009, .132, .096, .009, (255, 120, 40) if on else (90, 40, 30), 2.2 if on else 0.)
    v.box(.033, .236, -.012, .057, .242, .012, dk).box(-.004, 0, .09, .004, .008, .12, dk)
    zf = face(v, '-z', .01, .04, .045, .165); zp = face(v, '-z', -.034, -.008, .138, .151)
    out = v.boxes() + [tex(.01, .045, zf - .0015, .04, .165, zf - .0005, '-z', K.gauge(lvl, lit=on), (150, 170, 190), .6 if on else 0.),
                       tex(-.034, .14, zp - .0015, -.008, .149, zp - .0005, '-z', K.plaque('KETL', 20, 7), (200, 200, 206))]
    if on or _g(p, 'vapeur', 'steam', default=False): out += steam(-.112, .24, 0, 5)
    return out


def _kettle_gas(p, on):
    col = _col(p.get('color'), (176, 40, 36)); dk = DARK; cr = (232, 226, 212); v = Vox(.006)
    v.cyl(0, 0, .085, 0, .01, _sh(col, .55))
    lathe(v, 0, 0, [(.01, .098), (.03, .105), (.07, .1), (.09, .088), (.105, .072), (.117, .056), (.125, .048)], col)
    v.cyl(0, 0, .045, .125, .133, cr).cyl(0, 0, .014, .133, .149, dk)
    v.box(-.056, .118, -.006, -.044, .19, .006, STEEL).box(.044, .118, -.006, .056, .19, .006, STEEL).box(-.065, .18, -.013, .065, .2, .013, dk)
    v.line((-.088, .045, 0), (-.122, .095, 0), .013, col).line((-.122, .095, 0), (-.152, .135, 0), .01, col).box(-.172, .137, -.015, -.142, .159, .015, dk)
    out = v.boxes()
    if on: out += steam(-.165, .17, 0, 5)
    return out


def v_coffee_maker(p):
    body = _col(p.get('color'), (36, 36, 40)); on = bool(_g(p, 'allumee', 'on', default=False)); plein = float(_g(p, 'plein', default=.6)); cz = -.04; blk = (30, 30, 34)
    v = Vox(.008)
    v.box(-.1, 0, -.12, .1, .035, .12, body).box(-.1, .035, .04, .1, .265, .12, body).box(-.1, .265, -.12, .1, .32, .12, body).box(-.092, .32, -.11, .092, .328, .09, _sh(body, 1.25))
    v.cyl(0, cz, .065, .035, .043, (64, 64, 68))
    v.cyl(0, cz, .055, .235, .265, _sh(body, .85)).cyl(0, cz, .035, .222, .235, _sh(body, .85))
    if plein > .02: v.cyl(0, cz, .052, .043, .045 + .11 * min(1., plein), K.COFFEE)
    v.cyl(0, cz, .053, .171, .203, blk).cyl(0, cz, .044, .203, .213, blk).box(-.016, .19, -.112, .016, .202, -.09, blk)
    v.box(.054, .184, cz - .008, .086, .196, cz + .008, blk).box(.084, .076, cz - .01, .1, .196, cz + .01, blk).box(.054, .074, cz - .008, .086, .086, cz + .008, blk)
    v.box(.054, .012, -.128, .076, .024, -.12, (255, 60, 40) if on else (90, 26, 22), 2.4 if on else 0.).box(-.004, .0, .12, .004, .008, .14, blk)
    xg = face(v, '+x', .05, .11, .07, .24); zp = face(v, '-z', -.03, .03, .28, .296)
    out = v.boxes()
    out += glassify(Vox(.008).cyl(0, cz, .064, .043, .171, (200, 214, 222), r_in=.057).boxes(), .09) + glassify(Vox(.008).cyl(0, cz, .064, .043, .051, (200, 214, 222), r_in=.052).boxes(), .25)
    out += [tex(-.085, .01, -.1215, -.035, .026, -.1205, '-z', T.lcd(T.hhmm(_g(p, 'heure', 'time'), '07:00'), 24, 8), (40, 60, 40), .6),
            tex(xg + .0005, .07, .05, xg + .0015, .24, .11, '+x', K.gauge(float(_g(p, 'niveau', default=.4)), water=(150, 180, 210)), (150, 170, 190)),
            tex(-.03, .28, zp - .0015, .03, .296, zp - .0005, '-z', K.plaque('CAFE', 24, 7), (200, 200, 206))]
    if on: out += steam(.03, .34, .07, 4)
    return out


def v_toaster(p):
    c = p.get('color'); col = _col(c, (196, 198, 206)); on = bool(_g(p, 'allumee', 'on', default=False)); tart = _g(p, 'tartines', default=False)
    down = on or tart == 'dedans'; v = Vox(.008); bread, crust = (222, 168, 96), (168, 104, 50)
    v.box(-.142, 0, -.082, .142, .014, .082, DARK).box(-.14, .014, -.08, .14, .182, .08, col).box(-.134, .182, -.074, .134, .192, .074, col)
    v.box(-.148, .024, -.07, -.14, .174, .07, DARK).box(.14, .024, -.07, .148, .174, .07, DARK)
    for zc in (-.032, .032):
        v.erase(-.104, .15, zc - .012, .104, .2, zc + .012).box(-.104, .15, zc - .012, .104, .158, zc + .012, (255, 110, 40) if on else (14, 12, 10), 1.8 if on else 0.)
        if tart in ('sorties', 'dedans', True):
            yt = .2 if tart == 'dedans' else .25
            v.box(-.088, .158, zc - .008, .088, yt, zc + .008, bread).box(-.088, .158, zc - .008, -.08, yt, zc + .008, crust).box(.08, .158, zc - .008, .088, yt, zc + .008, crust)
            if tart != 'dedans': v.box(-.088, yt - .008, zc - .008, .088, yt, zc + .008, crust)
    v.box(.09, .045, -.088, .098, .17, -.08, (14, 14, 16)).box(.08, .064 if down else .148, -.104, .112, .08 if down else .164, -.08, (30, 30, 34))
    v.cylz(.05, .06, .016, -.096, -.08, (36, 36, 40)).box(.048, .064, -.1, .052, .076, -.096, (240, 240, 240))
    v.box(.04, .104, -.088, .06, .112, -.08, (200, 40, 40)).box(.04, .12, -.088, .06, .128, -.08, (60, 120, 200)).box(-.05, .016, -.088, .05, .024, -.08, (60, 60, 64))
    if c is None: paint(v, -.12, .03, -.088, -.112, .17, -.072, (250, 250, 255), .35)
    v.box(-.124, 0, .08, -.116, .008, .1, DARK)
    zp = face(v, '-z', -.08, -.01, .075, .091)
    return v.boxes() + [tex(-.08, .075, zp - .0015, -.01, .091, zp - .0005, '-z', K.plaque('TOAST', 28, 7), (200, 200, 206))]


def v_microwave(p):
    cab = _col(p.get('color'), (214, 214, 210)); on = bool(_g(p, 'allume', 'allumee', 'on', default=False)); door = (34, 34, 38); inner = (206, 204, 196); em = .45 if on else 0.
    txt = _g(p, 'ecran', 'screen'); txt = str(txt) if txt not in (None, True) else T.hhmm(_g(p, 'heure', 'time'), '02:13')
    sh = Vox(.02)                                                                                    # le caisson en cubes de 2 cm, le reste en cubes de 1 cm
    sh.box(-.24, .01, -.17, .24, .03, .19, cab).box(-.24, .27, -.17, .24, .29, .19, cab).box(-.24, .03, -.17, -.22, .27, .19, cab).box(-.22, .03, .17, .1, .27, .19, cab).box(.1, .03, -.17, .24, .27, .19, cab)
    lin = [B((-.22, .03, -.17), (.32, .002, .34), inner, emis=em, grain=0.), B((-.22, .268, -.17), (.32, .002, .34), inner, emis=em, grain=0.), B((-.22, .032, -.17), (.002, .236, .34), inner, emis=em, grain=0.),
           B((-.22, .032, .168), (.32, .236, .002), inner, emis=em * 1.2, grain=0.), B((.098, .032, -.17), (.002, .236, .34), inner, emis=em, grain=0.)]
    v = Vox(.01)
    v.box(.07, .24, .09, .09, .26, .11, (255, 236, 180) if on else (180, 176, 168), 2.2 if on else 0.)
    v.cyl(-.06, -.005, .125, .03, .036, (206, 216, 220)).box(-.07, .03, -.015, -.05, .04, .005, (90, 90, 96))
    for x in (-.22, .2):
        for z in (-.16, .14): v.box(x, 0, z, x + .02, .01, z + .02, DARK)
    out = []
    mesh_a = _mesh_alpha()
    if _g(p, 'ouverte', 'open', default=False):
        v.box(-.26, .025, -.51, -.24, .275, -.18, door).erase(-.26, .06, -.48, -.24, .235, -.24).box(-.27, .07, -.5, -.26, .23, -.48, STEEL)
        out += [glass(-.26, .06, -.48, -.24, .235, -.24, (22, 24, 28), .45), tex(-.2395, .06, -.48, -.2385, .235, -.24, '+x', mesh_a, (22, 24, 28))]
    else:
        v.box(-.235, .235, -.19, .095, .275, -.17, door).box(-.235, .025, -.19, .095, .06, -.17, door).box(-.235, .06, -.19, -.205, .235, -.17, door).box(.035, .06, -.19, .095, .235, -.17, door)
        v.box(.062, .07, -.21, .078, .23, -.2, STEEL).box(.062, .07, -.2, .078, .08, -.19, STEEL).box(.062, .22, -.2, .078, .23, -.19, STEEL)
        out += [glass(-.205, .06, -.185, .035, .235, -.175, (22, 24, 28), .5), tex(-.205, .06, -.1865, .035, .235, -.1855, '-z', mesh_a, (22, 24, 28))]
    ky = .275 - 62. / 76 * .25
    v.cylz(.1675, ky, .021, -.19, -.17, (40, 40, 44)).cylz(.1675, ky, .015, -.196, -.19, (60, 60, 66)).box(.1655, ky + .004, -.2, .1695, ky + .018, -.196, (240, 240, 240))
    if _g(p, 'contenu', default='') == 'bol': out += shift(v_bowl({'contenu': 'soupe', 'cuillere': False, 'vapeur': on}), -.06, .036, -.005)
    out = sh.boxes() + lin + v.boxes() + out
    out += [tex(.1, .025, -.1715, .235, .275, -.1705, '-z', K.mw_panel(), (44, 44, 48)), tex(.107, .23, -.1728, .222, .266, -.1718, '-z', K.mw_display(txt), (8, 12, 10), 1.1),
            tex(.2405, .18, -.06, .2415, .24, .06, '+x', K.vents(24, 12, cab), cab)]
    return out


_MESH = {}


def _mesh_alpha():
    """la trame de la porte en décalcomanie : les trous opaques, le fond à demi transparent (on voit le four derrière la vitre)"""
    if 'm' not in _MESH:
        a = np.array(K.mesh(), np.uint8); bg = (a[..., :3].astype(int).sum(-1) < 3 * 30); a[bg, 3] = 70; _MESH['m'] = a
    return _MESH['m']


def v_saucepan(p):
    st = _col(p.get('color'), STEEL); cont = _g(p, 'contenu', default='eau'); bout = bool(_g(p, 'bout', default=False))
    v = Vox(.006); yl = .014 if cont == 'vide' else .07; liq = K.CONTENTS.get(cont, K.WATER) if cont != 'vide' else _sh(st, .72)
    v.cyl(0, 0, .086, 0, .008, _sh(st, .7)).cyl(0, 0, .09, .008, yl, st).cyl(0, 0, .085, yl - .006, yl, liq)
    v.cyl(0, 0, .09, yl, .1, st, r_in=.083).cyl(0, 0, .0915, .1, .104, _sh(st, 1.15), r_in=.083)
    v.box(.088, .066, -.012, .106, .092, .012, st)
    for i in range(6): v.box(.106 + i * .03, .084 + i * .004, -.013 + i * .0006, .136 + i * .03, .093 + i * .004, .013 - i * .0006, st)
    v.box(.274, .104, -.013, .304, .113, .013, st).erase(.284, .1, -.006, .296, .12, .006)
    if bout:
        for (x, z) in ((-.03, .02), (.02, -.03), (.04, .03), (-.01, -.045)): v.box(x - .004, yl, z - .004, x + .004, yl + .006, z + .004, _sh(liq, 1.4))
    yt = face(v, '+y', -.03, .03, -.03, .03)
    out = v.boxes()
    if cont != 'vide': out.append(tex(-.046, yt, -.046, .046, yt + .001, .046, '+y', T.flat(K.surface(cont if cont in K.CONTENTS else 'eau', 16, bout)), liq))
    if _g(p, 'couvercle', 'lid', default=False):
        out += glassify(Vox(.006).cyl(0, 0, .093, .104, .11, (190, 204, 214)).boxes(), .14) + Vox(.006).cyl(0, 0, .094, .104, .11, st, r_in=.086).cyl(0, 0, .013, .11, .128, DARK).boxes()
    if bout: out += steam(0, .13, 0, 5)
    return out


def v_frying_pan(p):
    ext = _col(p.get('color'), (58, 58, 64)); cont = _g(p, 'contenu', default='vide'); coat = (28, 28, 30); v = Vox(.006)
    v.cyl(0, 0, .1, 0, .006, _sh(ext, .8))
    lathe(v, 0, 0, [(.006, .116), (.024, .124), (.042, .131)], ext, hollow_from=.012, wall=.01)
    v.cyl(0, 0, .107, .006, .012, coat)
    v.cyl(0, 0, .132, .042, .046, _sh(ext, 1.35), r_in=.121)
    v.box(.128, .022, -.016, .152, .044, .016, STEEL)
    for i in range(6): v.box(.152 + i * .032, .026 + i * .0045, -.014, .184 + i * .032, .046 + i * .0045, .014, coat)
    v.erase(.322, .04, -.006, .334, .08, .006)
    y = .012
    for (x, z) in {'oeuf': [(-.01, .01)], 'oeufs': [(-.045, .02), (.04, -.025)]}.get(cont, []):
        v.cyl(x, z, .045, y, y + .006, (246, 244, 236)).box(x + .012, y, z + .012, x + .048, y + .006, z + .044, (246, 244, 236)).box(x - .048, y, z - .038, x - .02, y + .006, z - .002, (242, 240, 230))
        v.cyl(x + .004, z - .004, .017, y + .006, y + .012, (250, 176, 30)).cyl(x + .004, z - .004, .01, y + .012, y + .018, (250, 176, 30)).box(x, y + .012, z - .012, x + .006, y + .018, z - .006, (255, 232, 160))
    if cont == 'bacon':
        for zz in (-.05, -.01, .03): v.box(-.075, y, zz, .075, y + .006, zz + .026, (170, 60, 50)).box(-.075, y, zz + .008, .075, y + .006, zz + .014, (236, 200, 180))
    out = v.boxes()
    if cont not in ('oeuf', 'oeufs', 'bacon'): out.append(tex(-.05, .0125, -.05, .05, .0135, .05, '+y', T.flat(K.surface('vide', 16)), coat))
    return out


def _blade(n_col, L=.188, w0=.046, x0=-.028):
    """profil de la lame de chef, colonne par colonne de cubes (le tranchant remonte vers le dos jusqu'à la pointe)"""
    return [(x0 + L * i / n_col, w0 * (1 - ((i + .5) / n_col) ** 2.4) + .004) for i in range(n_col)]


def v_kitchen_knife(p):
    hc = _col(p.get('color'), (44, 34, 30)); sang = bool(_g(p, 'sang', 'blood', default=False)); u = .004; v = Vox(u); zs = .012
    v.box(-.16, 0, -.021, -.04, .016, .003, hc).box(-.155, .016, -.018, -.045, .02, .0, _sh(hc, 1.2)).box(-.164, .002, -.019, -.16, .014, .001, _sh(hc, .8))
    for x in (-.14, -.105, -.07): v.box(x - .004, .016, -.012, x + .004, .02, -.004, STEEL)
    v.box(-.04, 0, -.024, -.028, .018, .008, STEEL)
    n = int(round(.188 / u))
    for (x, w) in _blade(n):
        v.box(x, 0, zs - w, x + u, u, zs, STEEL).box(x, 0, zs - w, x + u, u, zs - w + .004, (236, 240, 246))
    if sang:
        for (x, z, w, d) in ((.02, -.02, .05, .012), (.07, -.01, .03, .01), (.1, -.002, .02, .006), (.04, -.004, .02, .008)): paint(v, x, 0, z, x + w, u, z + d, (110, 8, 12))
        for (x, z) in ((.19, -.01), (.205, .015), (.175, .03)): v.box(x - .004, 0, z - .004, x + .004, u, z + .004, (100, 6, 10))
    return v.boxes()


def v_cutting_board(p):
    wood = _col(p.get('color'), (178, 128, 80)); cont = _g(p, 'contenu', default='vide'); v = Vox(.006)
    v.box(-.19, 0, -.12, .19, .022, .12, wood).box(-.18, 0, -.13, .18, .022, .13, wood).box(.152, .018, -.01, .172, .024, .01, (40, 26, 16))
    yt = face(v, '+y', -.1, .1, -.1, .1); y = 0.                                               # le contenu est sculpté au sol puis posé 1 mm AU-DESSUS de l'image du dessus
    w = Vox(.006); orr = (230, 120, 30)
    if cont == 'carottes':
        for i in range(5): w.cylx(y + .008, -.03, .008 - i * .0008, -.095 + i * .03, -.065 + i * .03, orr)
        w.box(-.108, y + .004, -.036, -.095, y + .014, -.024, (90, 150, 50)).box(-.124, y + .008, -.04, -.106, y + .014, -.032, (90, 150, 50))
        for (x, z) in ((.04, .04), (.07, .03), (.06, .065), (.095, .05), (.03, .075)): w.cyl(x, z, .011, y, y + .006, orr).cyl(x, z, .005, y + .006 - .001, y + .006, (250, 170, 80))
    elif cont == 'pain':
        w.box(-.15, y, -.045, .05, y + .06, .045, (196, 136, 70)).box(-.14, y + .054, -.032, .04, y + .066, .032, (214, 160, 90))
        for i in range(3): w.box(.064 + i * .022, y, -.045, .076 + i * .022, y + .054, .036, (232, 206, 160)).box(.064 + i * .022, y, -.045, .076 + i * .022, y + .054, -.039, (180, 120, 60))
    elif cont == 'oignon':
        w.cyl(-.03, 0, .035, y, y + .036, (220, 180, 120)).cyl(-.03, 0, .025, y + .03, y + .036, (240, 230, 220))
        for i in range(3): w.box(.04, y, -.024 + i * .02, .08, y + .006, -.016 + i * .02, (240, 226, 230))
    out = v.boxes() + shift(w.boxes(), 0., yt + .0012, 0.) + [tex(-.18, yt, -.12, .14, yt + .0008, .12, '+y', T.flat(K.board_top(76, 52, wood)), wood)]
    if _g(p, 'couteau', 'knife', default=False): out += shift(v_kitchen_knife({}), .0, yt + .005, .08)          # au-dessus de l'image du dessus (posée 4 mm plus haut)
    return out


BOWL_PROF = [(.008, .05), (.02, .061), (.032, .068), (.046, .072), (.058, .075), (.068, .075)]


def _bowl(x, y, z, col, fil, cont, spoon=True, steam_=False, decal=True):
    """bol creux (repère : x, y = le bas, z) : pied, panse de révolution, contenu au niveau, paroi au-dessus, liseré, bord clair"""
    v = Vox(.005); yc = .022 if cont == 'vide' else .056; wall = .007
    v.cyl(x, z, .034, y, y + .008, _sh(col, .88))
    lathe(v, x, z, [(y + a, r) for (a, r) in BOWL_PROF], col, hollow_from=y + yc, wall=wall)
    rc = float(np.interp(yc, [q[0] for q in BOWL_PROF], [q[1] for q in BOWL_PROF])) - wall
    liq = K.CONTENTS.get(cont, K.SOUP) if cont != 'vide' else _sh(col, .86)
    yt = max(v.c(j) for (i, j, k) in v.v if math.hypot(v.c(i) - x, v.c(k) - z) < rc * .5) + v.u / 2           # dessus du contenu (le haut de la dernière rangée pleine)
    paint_disc(v, x, z, rc, yt - v.u * .9, yt, liq)
    paint_disc(v, x, z, .08, y + .06, y + .064, fil, r_in=.066); paint_disc(v, x, z, .08, y + .0645, y + .068, _sh(col, 1.06), r_in=.066)
    if spoon: v.line((x + .02, y + yc + .004, z - .01), (x + .085, y + .1, z - .035), .004, STEEL).box(x + .01, y + yc, z - .016, x + .036, y + yc + .005, z + .004, STEEL)
    out = v.boxes()
    if decal: out.append(tex(x - .036, yt + .0002, z - .036, x + .036, yt + .0012, z + .036, '+y', T.flat(K.surface(cont if cont in K.CONTENTS else 'soupe' if cont != 'vide' else 'vide')), liq))
    if steam_: out += steam(x - .01, y + .085, z, 4)
    return out


def v_bowl(p):
    cont = _g(p, 'contenu', default='soupe')
    return _bowl(0, 0, 0, _col(p.get('color'), CERAM), _col(_g(p, 'filet'), (60, 90, 160)), cont, spoon=_g(p, 'cuillere', 'spoon', default=True), steam_=_g(p, 'vapeur', 'steam', default=cont == 'soupe'))


TEAPOT_PROF = [(0, .045), (.008, .062), (.022, .076), (.034, .083), (.07, .083), (.092, .072), (.106, .06), (.114, .05)]


def _teapot_vox(v, x, y, z, col):
    lathe(v, x, z, [(y + a, r) for (a, r) in TEAPOT_PROF], col)
    v.cyl(x, z, .046, y + .114, y + .122, _sh(col, .97)).cyl(x, z, .034, y + .122, y + .13, col).cyl(x, z, .01, y + .13, y + .136, col).cyl(x, z, .016, y + .136, y + .146, col)
    v.cyl(x, z, .054, y + .108, y + .114, (200, 160, 70), r_in=.046)
    return v


def v_teapot(p):
    col = _col(p.get('color'), CERAM); ink = _col(_g(p, 'motif'), (50, 80, 160)); v = Vox(.006)
    _teapot_vox(v, 0, 0, 0, col)
    v.line((-.075, .04, 0), (-.105, .075, 0), .012, col).line((-.105, .075, 0), (-.134, .108, 0), .008, col)
    v.loop_y(.08, .07, 0, .022, .034, .008, col, '+x')
    zf = face(v, '-z', -.038, .038, .036, .058)
    out = v.boxes() + [tex(-.038, .036, zf - .0015, .038, .058, zf - .0005, '-z', K.teapot_band(col, ink), col)]
    if _g(p, 'vapeur', 'steam', default=False): out += steam(-.14, .13, 0, 4)
    return out


def v_pill_box(p):
    nom, dose, sous, band, pat, pos = K._pill_cfg(p)
    out = [B((-.055, 0, -.0275), (.11, .025, .055), (246, 246, 242), grain=0.), B((-.055, .0248, -.0275), (.11, .0006, .006), (230, 230, 226), grain=0.)]
    out += [tex(-.054, .0256, -.021, .054, .0266, .0265, '+y', T.flat(K.pill_top(nom, dose, sous, band, pat)), (246, 246, 242)),
            tex(-.055, 0, -.0287, .055, .025, -.0277, '-z', K.pill_side(nom, dose, band), (246, 246, 242)), tex(-.055, 0, .0277, .055, .025, .0287, '+z', K.pill_side(nom, dose, band), (246, 246, 242)),
            tex(.0552, 0, -.0275, .0562, .025, .0275, '+x', K.pill_end(dose, band), band), tex(-.0562, 0, -.0275, -.0552, .025, .0275, '-x', K.pill_end(dose, band), band)]
    if _g(p, 'plaquette', 'blister', default=True):
        rest = int(_g(p, 'restants', default=7)); v = Vox(.004); v.box(-.03, 0, -.1, .07, .004, -.056, (196, 198, 206))
        for i in range(min(10, max(0, rest))):
            r, c_ = divmod(i, 5); v.cyl(-.03 + (3 + c_ * 9 + 3) / 48 * .1, -.1 + .045 - (3 + r * 9 + 3) / 20 * .045, .005, .004, .008, (226, 228, 232))
        out += v.boxes() + [tex(-.03, .0042, -.1, .07, .0050, -.056, '+y', T.flat(K.blister(rest)), (196, 198, 206))]
    return out


def v_toothbrush_glass(p):
    gl = _col(p.get('color'), (196, 214, 222)); n = int(_g(p, 'brosses', default=2)); v = Vox(.004)
    out = glassify(Vox(.004).cyl(0, 0, .036, 0, .012, gl).boxes(), .5) + glassify(Vox(.004).cyl(0, 0, .036, .012, .096, gl, r_in=.032).boxes(), .1)
    out += glassify(Vox(.004).cyl(0, 0, .037, .096, .1, (240, 248, 250), r_in=.031).boxes(), .55)
    for (col, a, b) in (((40, 110, 200), (-.008, .012, .008), (-.048, .2, .03)), ((230, 90, 130), (.01, .012, -.006), (.05, .19, -.025)),
                        ((70, 170, 110), (.0, .012, .012), (.006, .205, .05)))[:max(1, min(3, n))]:
        d = np.subtract(b, a); d = d / np.linalg.norm(d); hd = np.add(b, d * .02)
        v.line(a, b, .005, col).line(b, tuple(hd + d * .014), .0065, col)
        q = np.add(hd, (0, 0, -.011)); v.box(q[0] - .005, q[1] - .012, q[2] - .005, q[0] + .005, q[1] + .012, q[2] + .005, (246, 246, 250))
        q = np.add(hd, (0, .004, -.016)); v.box(q[0] - .004, q[1] - .006, q[2] - .002, q[0] + .004, q[1] + .006, q[2] + .002, (90, 170, 230))
    if _g(p, 'dentifrice', default=True):
        v.box(.05, 0, -.075, .17, .024, -.033, (250, 250, 250)).box(.17, 0, -.078, .192, .008, -.03, (240, 240, 240)).cylx(.012, -.054, .011, .034, .05, (200, 40, 40)).cylx(.012, -.054, .008, .026, .034, (200, 40, 40))
    out += v.boxes()
    if _g(p, 'dentifrice', default=True): out.append(tex(.05, .0242, -.075, .17, .0252, -.033, '+y', T.flat(K.toothpaste()), (250, 250, 250)))
    return out


def v_soap(p):
    col = _col(p.get('color'), (232, 184, 196)); v = Vox(.004)
    if _g(p, 'modele', default='pain') == 'pompe':
        v.box(-.035, 0, -.022, .035, .13, .022, col).cyl(0, 0, .016, .13, .144, WHITE).box(-.004, .144, -.004, .004, .172, .004, WHITE).box(-.015, .17, -.016, .015, .184, .008, WHITE).box(-.004, .176, -.048, .004, .184, -.016, WHITE)
        zf = face(v, '-z', -.03, .03, .03, .09)
        return v.boxes() + [tex(-.03, .03, zf - .0015, .03, .09, zf - .0005, '-z', T.label('SAVON', 'LIQUIDE', (246, 244, 236), (120, 60, 90), 30, 20), (246, 244, 236))]
    cer = (236, 236, 232)
    v.box(-.0675, 0, -.05, .0675, .01, .05, cer).box(-.0675, .01, -.05, .0675, .022, -.044, cer).box(-.0675, .01, .044, .0675, .022, .05, cer)
    v.box(-.0675, .01, -.044, -.0615, .022, .044, cer).box(.0615, .01, -.044, .0675, .022, .044, cer)
    for (sx, sz) in ((-1, -1), (-1, 1), (1, -1), (1, 1)): v.erase(sx * .0675 - .004 if sx > 0 else -.0675, 0, sz * .05 - .004 if sz > 0 else -.05, sx * .0675 if sx > 0 else -.0635, .022, sz * .05 if sz > 0 else -.046)
    for zz in (-.026, 0, .026): v.box(-.05, .01, zz - .003, .05, .014, zz + .003, _sh(cer, .92))
    v.box(-.046, .014, -.029, .046, .038, .029, col).box(-.041, .038, -.025, .041, .042, .025, col)
    for (sx, sz) in ((-1, -1), (-1, 1), (1, -1), (1, 1)): v.erase(sx * .046 - .004 if sx > 0 else -.046, .014, sz * .029 - .004 if sz > 0 else -.029, sx * .046 if sx > 0 else -.042, .042, sz * .029 if sz > 0 else -.025)
    yt = face(v, '+y', -.02, .02, -.015, .015)
    out = v.boxes() + [tex(-.03, yt, -.018, .03, yt + .0008, .018, '+y', T.flat(K.soap_top(col)), col)]
    if _g(p, 'mousse', default=False):
        for (x, y, z) in ((-.03, .044, .01), (.02, .045, -.012), (.045, .03, .02), (-.046, .026, -.02), (.0, .046, .015)): out.append(glass(x - .006, y - .004, z - .006, x + .006, y + .004, z + .006, (250, 250, 252), .75))
    return out


def v_towel(p):
    n = max(1, min(4, int(_g(p, 'pile', default=1)))); band = _col(_g(p, 'bande'), (110, 130, 170)); cols = _g(p, 'couleurs') or []; H = .066
    v = Vox(.006); out = []
    for i in range(n):
        col = _col(cols[i] if i < len(cols) else p.get('color'), WHITE); y0 = i * .068; dx = .006 * (1 if i % 2 else -1) * (i > 0)
        v.box(-.152 + dx, y0 + .003, -.09, .152 + dx, y0 + H - .003, .09, col)
        for k_ in range(3): v.cylx(y0 + .012 + .021 * k_, -.092, .0105, -.149 + dx, .149 + dx, col)
        v.cylx(y0 + H / 2, .078, .024, -.148 + dx, .148 + dx, col)
        paint(v, -.143 + dx, y0 + .03, -.106, .143 + dx, y0 + .036, -.096, band)
        xr = face(v, '+x', -.06, .06, y0 + .01, y0 + H - .01); xl = face(v, '-x', -.06, .06, y0 + .01, y0 + H - .01)
        if i == n - 1: yt = face(v, '+y', -.1 + dx, .1 + dx, -.06, .06); out.append(tex(-.147 + dx, yt, -.09, .147 + dx, yt + .0008, .088, '+y', T.flat(K.towel_top(col, band)), col))
        out += [tex(xr + .0005, y0 + .008, -.08, xr + .0015, y0 + H - .008, .08, '+x', K.towel_side(col), col), tex(xl - .0015, y0 + .008, -.08, xl - .0005, y0 + H - .008, .08, '-x', K.towel_side(col), col)]
    return v.boxes() + out


def v_hair_dryer(p):
    col = _col(p.get('color'), (70, 120, 132)); dk = DARK; cy = .0375; v = Vox(.005)
    v.cylx(cy, 0, .0375, -.07, .085, col).cylx(cy, 0, .035, -.095, -.07, dk).cylx(cy, 0, .032, .085, .1, STEEL)
    v.box(.1, .02, -.028, .14, .055, .028, dk); paint(v, .135, .034, -.023, .14, .041, .023, (8, 8, 10))
    v.box(.007, .017, -.1, .053, .051, -.03, col).box(.001, .017, -.172, .043, .049, -.098, col).box(.0, .018, -.182, .036, .048, -.17, _sh(col, .8))
    v.box(.024, .051, -.091, .036, .054, -.069, (200, 40, 40)).box(.02, .049, -.124, .032, .052, -.106, (240, 240, 240))
    v.box(.003, .03, -.198, .033, .038, -.182, dk).erase(.013, .029, -.195, .023, .04, -.188)
    cord = [(.018, .02, -.185), (-.04, .005, -.22), (-.13, .005, -.21), (-.19, .005, -.13), (-.18, .005, -.02), (-.12, .005, .04)]
    for a, b in zip(cord[:-1], cord[1:]): v.line(a, b, .0035, dk)
    v.box(-.115, 0, .044, -.085, .024, .066, (230, 230, 226)).box(-.085, .006, .046, -.075, .012, .05, STEEL).box(-.085, .006, .06, -.075, .012, .064, STEEL)
    xf = face(v, '-x', -.02, .02, .02, .055)
    return v.boxes() + [tex(xf - .0015, cy - .026, -.026, xf - .0005, cy + .026, .026, '-x', K.grille_ronde(), dk)]


# ================================================================== held (VOXEL native), in the PS1 hand frame P(lat, up, fwd) with f = +1
def hv_kitchen_knife(col, cfg):
    hc = _col(col, (44, 34, 30)); prise = cfg.get('prise', 'bas'); sang = bool(cfg.get('sang', False)); u = .004; v = Vox(u); L = .19; n = int(round(L / u)); bl = []
    if prise in ('bas', 'haut'):
        sg = -1. if prise == 'bas' else 1.
        ya, yb = sorted((-sg * .07, sg * .06)); v.box(-.013, ya, -.011, .013, yb, .011, hc)
        ya, yb = sorted((-sg * .075, -sg * .067)); v.box(-.011, ya, -.01, .011, yb, .01, _sh(hc, .8))
        ya, yb = sorted((sg * .062, sg * .074)); v.box(-.014, ya, -.013, .018, yb, .013, STEEL)
        for y in (.05, .015): paint(v, -.004, -sg * y - .003, .008, .004, -sg * y + .003, .012, STEEL)
        for i, (y_, w) in enumerate(_blade(n, L, .046, 0.)):                                          # lame à plat face à l'avant, une rangée de cubes par pas, tranchant clair vers l'extérieur
            y = sg * (.074 + y_) - (u if sg < 0 else 0.)
            bl += [B((-.014, y, -.002), (w - .004, u, u), STEEL, grain=0.), B((-.018 + w, y, -.002), (.004, u, u), (236, 240, 246), grain=0.)]
            if sang and 10 <= i <= 24: bl.append(B((-.01, y, .002), (.014, u, .0006), (110, 8, 12), grain=0.))
        return v.boxes() + bl, []
    v.box(-.011, -.013, -.07, .011, .013, .06, hc).box(-.01, -.011, -.075, .01, .011, -.067, _sh(hc, .8))
    for z in (-.05, -.015): paint(v, .008, -.002, z - .003, .012, .006, z + .003, STEEL)
    v.box(-.013, -.014, .062, .013, .018, .074, STEEL)
    for i, (z_, w) in enumerate(_blade(n, L, .046, .074)):
        bl += [B((0, .018 - w, z_), (u, w - .004, u), STEEL, grain=0.), B((0, .014 - w, z_), (u, .004, u), (236, 240, 246), grain=0.)]
        if sang and 4 <= i <= 22: bl.append(B((u, .0 - w / 3, z_), (.0006, .012, u), (110, 8, 12), grain=0.))
    return v.boxes() + bl, []


def hv_bowl(col, cfg):
    cont = cfg.get('contenu', 'soupe')
    return _bowl(-.03, -.04, .125, _col(col, CERAM), _col(cfg.get('filet'), (60, 90, 160)), cont, spoon=bool(cfg.get('cuillere', False)), steam_=cfg.get('vapeur', cont == 'soupe'), decal=False), []


def hv_teapot(col, cfg):
    col = _col(col, CERAM); ink = _col(cfg.get('motif'), (50, 80, 160)); v = Vox(.006); x, y, z = 0., -.072, .118
    _teapot_vox(v, x, y, z, col)
    for k in v._r(z - .1, z + .02):                                                                 # anse dans le plan (avant, haut), ouverte vers la panse
        for j in v._r(-.04, .04):
            a, b = v.c(k) - .036, v.c(j) - (-.002); d = math.hypot(a, b)
            if .017 <= d <= .031 and a <= v.u * .5:
                for i in v._r(-.008, .008): v.put(i, j, k, col)
    v.line((0, -.032, .193), (0, .002, .222), .012, col).line((0, .002, .222), (0, .036, .251), .008, col)
    xf = face(v, '+x', z - .038, z + .038, y + .036, y + .058)
    return shift(v.boxes() + [tex(xf + .0005, y + .036, z - .038, xf + .0015, y + .058, z + .038, '+x', K.teapot_band(col, ink), col)], 0., 0., .03), []      # avancée de 3 cm : la main VOXEL est plus grosse


def hv_pill_box(col, cfg):
    nom, dose, sous, band, pat, pos = K._pill_cfg(dict(cfg, color=col) if col else cfg)
    out = [B((-.075, .0445, .0625), (.11, .055, .025), (246, 246, 242), grain=0.), B((-.075, .0995, .0625), (.11, .0008, .025), (230, 230, 226), grain=0.)]
    out += [tex(-.075, .0445, .0885, .035, .0995, .0895, '+z', K.pill_top(nom, dose, sous, band, pat), (246, 246, 242)),
            tex(-.075, .0445, .0605, .035, .0995, .0615, '-z', K.pill_back(pos, band), (246, 246, 242))]
    return shift(out, 0., .012, .02), []                                                          # au-dessus des doigts de la main VOXEL (plus grosse)


# ================================================================== registration
def enregistrer(R):
    for kind, fn in (('od_kettle', v_kettle), ('od_coffee_maker', v_coffee_maker), ('od_toaster', v_toaster), ('od_microwave', v_microwave), ('od_saucepan', v_saucepan),
                     ('od_frying_pan', v_frying_pan), ('od_kitchen_knife', v_kitchen_knife), ('od_cutting_board', v_cutting_board), ('od_bowl', v_bowl), ('od_teapot', v_teapot),
                     ('od_pill_box', v_pill_box), ('od_toothbrush_glass', v_toothbrush_glass), ('od_soap', v_soap), ('od_towel', v_towel), ('od_hair_dryer', v_hair_dryer)):
        R.objet(kind, fn)
    R.tenu('od_kitchen_knife', hv_kitchen_knife)
    R.tenu('od_bowl', hv_bowl)
    R.tenu('od_teapot', hv_teapot)
    R.tenu('od_pill_box', hv_pill_box)
