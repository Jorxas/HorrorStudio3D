"""OBJETS DÉTAILLÉS, LOT B « bureau, souvenirs et horreur », version VOXEL native (la version PS1 est engines/pixel3d/objets_souvenirs.py).

Découvert tout seul par `b_objets._load_lots()` (fichier `b_objets_<lot>.py`). Même plan et mêmes réglages que PS1, autre exécution : chaque objet est
SCULPTÉ en cubes sur une grille fine (3 mm pour un couteau, 1 cm pour une peluche) : peluche et poupée en volumes arrondis, cylindres d'objectif en anneaux,
verre d'objectif en disque de cubes violets, grille de haut-parleur en damier, glace du miroir en cubes clairs fêlés, cernes d'un billot en couronnes.
Les textes et les images (page tapée, étiquette de cassette, photo, lettre, écran du canal, visage peint) restent des décalcomanies (images de PS1) ;
tenue, la photo instantanée (vue de dessus, hors décalcomanie) est peinte en cubes.
Un objet tenu est le même objet tourné vers l'avant (ou vers celui qui le tient), saisi par la même prise qu'en PS1 (`objets_souvenirs._grip`)."""
import math
import numpy as np
from ..engines.pixel3d import objets as OD, objets_tex as T, objets_souvenirs as S
from .b_objets import Vox, tex, glass, coil

_g, _col, _sh = OD._g, OD._col, OD._sh
METAL, BRASS, CHROME, STEEL, PAPER = OD.METAL, OD.BRASS, S.CHROME, S.STEEL, S.PAPER


# ================================================================== sculpting helpers
def ell(v, cx, cy, cz, rx, ry, rz, col, em=0.):
    """ellipsoïde plein"""
    for i in v._r(cx - rx, cx + rx):
        for j in v._r(cy - ry, cy + ry):
            for k in v._r(cz - rz, cz + rz):
                x, y, z = (v.c(i) - cx) / rx, (v.c(j) - cy) / ry, (v.c(k) - cz) / rz
                if x * x + y * y + z * z <= 1.1: v.put(i, j, k, col, em)
    return v


def cell(v, x, y, z, col, em=0.):
    v.put(int(math.floor(x / v.u)), int(math.floor(y / v.u)), int(math.floor(z / v.u)), col, em)
    return v


def paint_front(v, x0, y0, x1, y1, col, em=0., depth=1, bump=0):
    """recolore les cubes de façade (les plus en -z) d'une zone : une broderie, un rapiéçage ; `bump` cubes en relief devant (un bouton, un nœud)"""
    front = {}
    for (i, j, k) in v.v:
        if front.get((i, j), 10 ** 9) > k: front[(i, j)] = k
    for i in v._r(x0, x1):
        for j in v._r(y0, y1):
            if (i, j) in front:
                for d in range(-bump, depth): v.put(i, j, front[(i, j)] + d, col, em)
    return v


def oval(v, cx, cy, W, H, z0, z1, col, r0=0., r1=1.):
    """plaque ovale verticale (couronne si r0 > 0), entre z0 et z1"""
    for i in v._r(cx - W / 2, cx + W / 2):
        for j in v._r(cy - H / 2, cy + H / 2):
            d = math.hypot((v.c(i) - cx) / (W / 2), (v.c(j) - cy) / (H / 2))
            if r0 <= d <= r1 + .04:
                for k in v._r(z0, z1): v.put(i, j, k, col)
    return v


def paint_top(v, img, x0, z0, x1, z1, y0, y1, q=12):
    """une image vue de dessus peinte en cubes (haut de l'image vers +z, lisible depuis l'avant) ; couleurs arrondies pour fusionner les rangées"""
    img = np.asarray(img); H, W = img.shape[:2]
    for i in v._r(x0, x1):
        for k in v._r(z0, z1):
            u = (v.c(i) - x0) / (x1 - x0); w = (z1 - v.c(k)) / (z1 - z0)
            px = img[min(H - 1, max(0, int(w * H))), min(W - 1, max(0, int(u * W)))]
            col = tuple(int(min(255, round(float(c) / q) * q)) for c in px[:3])
            for j in v._r(y0, y1): v.put(i, j, k, col)
    return v


def _vhold(bx, anchor, face='front'):
    """boîtes d'un objet (repère posé) -> repère de la main de VOXEL (x = lat, y = haut, z = avant) : face avant vers l'avant (`front`) ou vers soi (`holder`)"""
    ax, ay, az = anchor; s = -1. if face == 'front' else 1.
    for b in bx:
        p0 = np.array([s * (float(b.lo[0]) - ax), float(b.lo[1]) - ay, s * (float(b.lo[2]) - az)], np.float32)
        p1 = np.array([s * (float(b.hi[0]) - ax), float(b.hi[1]) - ay, s * (float(b.hi[2]) - az)], np.float32)
        b.lo = np.minimum(p0, p1); b.hi = np.maximum(p0, p1)
        if s < 0 and b.tex: b.tex = S._half_tex(b.tex)
    return bx


def _stand_x(bx):
    """objet sculpté couché le long de x (rangées fusionnées sur sa longueur) -> debout : (x, y, z) -> (-y, x, z)"""
    for b in bx:
        lo, hi = b.lo.copy(), b.hi.copy()
        b.lo = np.array([-hi[1], lo[0], lo[2]], np.float32); b.hi = np.array([-lo[1], hi[0], hi[2]], np.float32); b.tex = {}
    return bx


def _glass_x(x0, x1, y, z, r, col, a=.3):
    """tube de verre couché le long de x (deux boîtes translucides en croix)"""
    return [glass(x0, y - r, z - r * .62, x1, y + r, z + r * .62, col, a), glass(x0, y - r * .62, z - r, x1, y + r * .62, z + r, col, a)]


# ================================================================== the objects (VOXEL), local frame = PS1
def v_typewriter(p):
    col = _col(p.get('color'), (30, 30, 34)); dk = _sh(col, .6); cap = (232, 226, 210)
    v = Vox(.008)
    for x in (-.125, .125):
        for z in (-.1, .1): v.box(x - .016, 0, z - .016, x + .016, .01, z + .016, (20, 20, 20))
    v.box(-.152, .01, -.12, .152, .04, .128, col).box(-.144, .01, -.144, .144, .032, -.12, dk)
    rows = ((-.122, 8, .046), (-.098, 9, .057), (-.074, 10, .068), (-.05, 10, .079))
    for (z, n, yt) in rows: v.box(-.144, .032, z - .012, .144, yt - .02, z + .012, col)
    v.box(-.152, .04, -.04, .152, .11, -.024, col).box(-.152, .04, -.024, -.128, .12, .104, col).box(.128, .04, -.024, .152, .12, .104, col).box(-.128, .04, .032, .128, .104, .104, col)
    v.box(-.128, .084, -.024, .128, .092, .032, (16, 16, 18))
    v.box(-.168, .096, .032, .168, .112, .104, col).box(-.152, .128, .08, .152, .232, .088, col)
    v.cylx(.13, .06, .024, -.156, .156, (22, 22, 24)).cylx(.13, .06, .02, -.192, -.156, dk).cylx(.13, .06, .02, .156, .192, dk)
    w = Vox(.004)
    for r, (z, n, yt) in enumerate(rows):
        x0 = -(n - 1) * .0115 + (.004 if r % 2 else 0.)
        for i in range(n):
            x = x0 + i * .023
            w.box(x - .002, yt - .02, z - .002, x + .002, yt - .002, z + .002, METAL).cyl(x, z, .01, yt - .002, yt + .002, CHROME).cyl(x, z, .008, yt + .002, yt + .006, cap)
    w.box(-.064, .032, -.144, .064, .04, -.132, CHROME).box(-.052, .028, -.136, -.048, .036, -.124, METAL).box(.048, .028, -.136, .052, .036, -.124, METAL)
    for sx in (-1, 1): w.cyl(sx * .093, .01, .026, .112, .12, CHROME).cyl(sx * .093, .01, .022, .108, .112, (60, 24, 26)).box(sx * .093 - .004, .12, .006, sx * .093 + .004, .124, .014, dk)
    w.box(-.012, .112, .024, .012, .124, .032, CHROME).box(-.084, .108, .028, .084, .112, .032, (60, 24, 26))
    w.box(-.104, .156, .032, .104, .16, .038, CHROME)
    for sx in (-1, 1): w.box(sx * .05 - .008, .152, .028, sx * .05 + .008, .164, .04, (30, 30, 30))
    w.line((-.165, .14, .045), (-.2, .165, .0), .004, CHROME).box(-.214, .16, -.01, -.196, .172, .004, CHROME)
    if _g(p, 'feuille', 'paper', default=True) is not False: w.box(-.104, .156, .044, .104, .306, .048, PAPER)
    out = v.boxes() + w.boxes()
    out.append(tex(-.06, .085, -.0412, .06, .101, -.0402, '-z', T.plate('NOCTA', 30, 8, col, (212, 176, 90)), col))
    out.append(tex(-.124, .092, -.022, .124, .093, .03, '+y', T.flat(S.typebar_fan()), (16, 16, 18)))
    if _g(p, 'feuille', 'paper', default=True) is not False:
        out.append(tex(-.103, .158, .0425, .103, .305, .0435, '-z', S.typed_page(T.lines(_g(p, 'texte', 'text'))), PAPER))
    return out


def _vcassette(v, x0, y0, z0, label, shell=(36, 36, 40), band=(190, 40, 40)):
    """cassette couchée (10 x 6,4 x 1,2 cm) sculptée dans `v`, l'étiquette en décalcomanie -> la plaque d'image"""
    v.box(x0, y0, z0, x0 + .1, y0 + .012, z0 + .064, shell).box(x0 + .02, y0 + .002, z0 - .002, x0 + .08, y0 + .008, z0, (20, 20, 22))
    return tex(x0 + .001, y0 + .012, z0 + .001, x0 + .099, y0 + .013, z0 + .063, '+y', T.flat(S.cassette_face(tuple(label), shell=tuple(shell), band=tuple(band))), shell)


def v_tape_recorder(p):
    col = _col(p.get('color'), (44, 44, 48)); dk = _sh(col, .6); sil = (176, 176, 182); rec = bool(_g(p, 'enregistre', 'rec', default=False))
    v = Vox(.006); out = []
    v.box(-.12, .006, -.075, .12, .045, .075, col).box(-.122, 0, -.078, .122, .006, .078, dk)
    v.box(-.118, .045, -.042, -.004, .048, .066, sil)
    for i in v._r(-.112, -.01):
        for k in v._r(-.036, .06): v.put(i, 7, k, (22, 22, 24) if (i // 2 + k // 2) % 2 else (62, 62, 66))          # grille du haut-parleur en damier
    v.box(-.004, .045, -.042, .116, .048, .066, sil).erase(.002, .036, -.036, .11, .049, .048)
    v.box(.002, .03, -.036, .11, .036, .048, (20, 20, 22))
    lab = T.lines(_g(p, 'etiquette', 'label'), ('NE PAS', 'ECOUTER'))
    out.append(_vcassette(v, .006, .036, -.024, lab))
    for i, sym in enumerate(('rec', 'rew', 'ff', 'play', 'stop', 'pause')):
        x = -.09 + i * .036; kc = (180, 30, 30) if sym == 'rec' else (34, 34, 36); y1 = .054 if not (rec and sym in ('rec', 'play')) else .048
        v.box(x - .015, .036, -.078, x + .015, y1, -.042, kc)
        out += [tex(x - .013, .038, -.0795, x + .013, y1 - .002, -.0785, '-z', S.tape_key(sym, bg=kc), kc), tex(x - .012, y1, -.072, x + .012, y1 + .001, -.048, '+y', T.flat(S.tape_key(sym, bg=kc)), kc)]
    v.box(.018, .045, .048, .054, .048, .066, (14, 14, 16)).box(.066, .045, .054, .072, .051, .06, (255, 40, 30) if rec else (90, 20, 20), 2.5 if rec else 0.)
    v.box(-.09, .045, .06, -.078, .066, .072, dk).box(.078, .045, .06, .09, .066, .072, dk).box(-.09, .06, .06, .09, .072, .072, dk)
    v.box(.12, .018, -.018, .126, .03, .018, sil)
    out.append(tex(.02, .048, .05, .05, .049, .063, '+y', T.flat(S.counter_img(str(_g(p, 'compteur', default='013')))), (14, 14, 16)))
    out.append(tex(-.06, .012, -.0792, .06, .028, -.0786, '-z', T.plate('NOCTA  K7', 40, 6, col, (200, 200, 206)), col))
    if _g(p, 'cassette', default=True) is not False:
        out.append(_vcassette(v, .14, 0., -.072, T.lines(_g(p, 'etiquette2', default=None), ('POUR', 'CLAIRE')), band=(40, 90, 170)))
    return v.boxes() + out + [glass(.006, .049, -.03, .106, .051, .044, (40, 44, 52), .3)]


def v_cassette(p):
    lab = T.lines(_g(p, 'etiquette', 'label'), ('NE PAS', 'ECOUTER')); v = Vox(.004)
    v.box(-.052, .004, .028, .052, .016, .034, (200, 60, 50))
    plate = _vcassette(v, -.05, .004, -.036, lab, _col(p.get('color'), (36, 36, 40)))
    return v.boxes() + [plate, glass(-.056, 0, -.036, .056, .004, .036, (226, 228, 232), .5), glass(-.056, .004, .036, .056, .074, .04, (226, 228, 232), .35)]


def v_film_camera(p):
    ch = _col(p.get('color'), CHROME); blk = (30, 30, 32); v = Vox(.004)
    v.box(-.07, 0, -.022, .07, .008, .022, ch).box(-.068, .008, -.022, .068, .066, .022, blk).box(-.07, .066, -.022, .07, .078, .022, ch)
    v.box(-.024, .078, -.02, .024, .098, .02, ch).box(-.018, .098, -.016, .018, .11, .016, ch).box(-.01, .11, -.008, .01, .114, .008, ch)
    v.cyl(-.048, 0, .011, .078, .09, blk).box(-.05, .09, -.008, -.046, .094, .008, ch)
    v.cyl(.036, 0, .013, .078, .082, blk).cyl(.036, 0, .012, .082, .088, ch).cyl(.054, -.01, .005, .078, .088, ch).box(.034, .082, .004, .068, .086, .012, ch)
    y = .044
    v.cylz(0, y, .029, -.03, -.022, ch).cylz(0, y, .028, -.04, -.03, blk).cylz(0, y, .029, -.044, -.04, ch).cylz(0, y, .031, -.062, -.044, (22, 22, 24))
    for z in (-.05, -.058): v.cylz(0, y, .032, z, z + .004, (86, 86, 92))
    v.cylz(0, y, .026, -.074, -.062, blk).cylz(0, y, .027, -.078, -.074, ch, r_in=.02).cylz(0, y, .021, -.077, -.074, (44, 36, 86)).cylz(0, y, .011, -.076, -.074, (18, 14, 40))
    cell(v, -.008, y + .008, -.0765, (210, 216, 250))
    v.box(.042, .042, -.026, .048, .058, -.022, ch).box(-.036, .026, -.026, -.028, .034, -.022, ch).box(-.012, .078, .022, .012, .094, .03, blk)
    for sx in (-1, 1): v.box(sx * .072 - .004, .056, -.004, sx * .072 + .004, .064, .004, ch)
    if _g(p, 'courroie', 'strap', default=True):
        st = (86, 52, 30); v.line((-.076, .058, 0), (-.1, .004, .03), .004, st).line((-.1, .004, .03), (.1, .004, .055), .005, st).line((.1, .004, .055), (.076, .058, 0), .004, st)
    return v.boxes() + [tex(-.023, .081, -.0222, .023, .094, -.0212, '-z', T.plate('NOCTA', 24, 6, blk, (226, 226, 232)), blk)]


def _vpolaroid(p, photo, painted=False):
    col = _col(p.get('color'), (232, 230, 222)); blk = (30, 30, 32); v = Vox(.005); out = []
    v.box(-.0575, 0, -.06, .0575, .075, .07, col).box(-.0575, .075, -.06, .0575, .105, .0, col).box(-.0575, .075, .0, .0575, .09, .03, col)
    v.box(-.055, .01, -.065, .055, .1, -.06, blk)
    v.cylz(0, .056, .027, -.075, -.065, blk).cylz(0, .056, .022, -.078, -.075, CHROME, r_in=.015).cylz(0, .056, .016, -.077, -.075, (44, 36, 86))
    cell(v, -.006, .062, -.0765, (210, 216, 250))
    fl = bool(_g(p, 'flash', default=False))
    v.box(-.048, .09, -.068, -.0, .1, -.065, (238, 238, 232), 2.5 if fl else 0.).box(.02, .09, -.068, .042, .1, -.065, (16, 18, 28))
    v.box(-.05, .06, -.07, -.038, .072, -.065, (200, 30, 30)).box(-.01, .012, -.068, -.005, .03, -.065, (200, 40, 40)).box(-.005, .012, -.068, .0, .03, -.065, (232, 136, 40))
    v.box(-.046, .004, -.066, .046, .009, -.063, (8, 8, 8)).box(.014, .09, .03, .03, .102, .036, blk)
    if photo:
        img = S.polaroid_img(str(_g(p, 'photo', default='silhouette')), str(_g(p, 'legende', 'caption', default='')))
        vis = np.ascontiguousarray(img[int(img.shape[0] * .2):])
        if painted:
            w = Vox(.004); paint_top(w, vis, -.044, -.148, .044, -.06, .004, .008); out += w.boxes()
        else:
            v.box(-.044, .004, -.148, .044, .008, -.062, (242, 240, 232))
            out.append(tex(-.043, .008, -.147, .043, .009, -.064, '+y', T.flat(vis), (242, 240, 232)))
    else: v.line((.058, .03, .02), (.07, .0, .05), .003, (40, 40, 44))
    return v.boxes() + out


def v_polaroid(p): return _vpolaroid(p, _g(p, 'photo', default='silhouette') is not False)


def v_walkie(p):
    col = _col(p.get('color'), (40, 42, 46)); rub = (22, 22, 24); v = Vox(.005)
    v.box(-.03, 0, -.018, .03, .19, .018, col)
    for sx in (-1, 1):
        for sz in (-1, 1): v.erase(sx * .03 - (.005 if sx > 0 else 0), 0, sz * .018 - (.005 if sz > 0 else 0), sx * .03 + (.005 if sx < 0 else 0), .19, sz * .018 + (.005 if sz < 0 else 0))
    for i in v._r(-.025, .025):
        for j in v._r(.1, .162): v.put(i, j, -5, (26, 26, 28) if (i + j) % 2 else (56, 56, 60))
    for r in range(2):
        for i in range(3): x = -.014 + i * .014; y = .053 - r * .013; v.box(x - .005, y - .004, -.025, x + .005, y + .004, -.02, (64, 64, 68))
    v.box(-.025, .19, -.008, -.01, .21, .008, rub).cyl(-.017, 0, .006, .21, .31, rub).box(-.023, .31, -.006, -.011, .32, .006, rub)
    v.cyl(.004, 0, .007, .19, .2, (30, 30, 32)).cyl(.02, 0, .008, .19, .205, (30, 30, 32))
    vl = _g(p, 'voyant', 'led', default='rouge'); vc = (60, 230, 90) if vl == 'vert' else (255, 40, 30)
    v.box(.004, .185, -.025, .01, .19, -.02, vc if vl else (70, 20, 20), 2.6 if vl else 0.)
    v.box(-.035, .1, -.01, -.03, .145, .01, rub).box(.03, .03, -.01, .035, .15, .01, rub).box(-.015, .07, .02, .015, .17, .025, (52, 52, 56))
    ch = str(_g(p, 'canal', 'channel', default='03'))
    return v.boxes() + [tex(-.021, .071, -.0262, .021, .091, -.0252, '-z', T.lcd(f'CH {ch}', 24, 11, (20, 40, 20), (150, 190, 110)), (150, 190, 110), .6),
                        tex(-.02, .012, -.0212, .02, .022, -.0204, '-z', T.plate('NOCTA', 20, 5, col, (200, 200, 206)), col)]


def v_binoculars(p, strap=True):
    col = _col(p.get('color'), (34, 34, 36)); rub = (20, 20, 22); v = Vox(.005)
    for sx in (-1, 1):
        x = sx * .05
        v.cylz(x, .028, .025, -.064, -.005, col).cylz(x, .028, .026, -.069, -.064, rub, r_in=.019).cylz(x, .028, .019, -.067, -.064, (40, 36, 96)).cylz(x, .028, .009, -.066, -.064, (18, 14, 44))
        cell(v, x - .007, .036, -.0665, (200, 206, 250))
        for z in (-.05, -.035, -.02): v.cylz(x, .028, .0265, z, z + .005, _sh(col, .7))
        v.box(sx * .04 - .03, .004, -.01, sx * .04 + .03, .056, .05, col)
        v.erase(sx * .04 - .03, .051, -.01, sx * .04 + .03, .056, -.005).erase(sx * .04 - .03, .051, .045, sx * .04 + .03, .056, .05)
        xe = sx * .03
        v.cylz(xe, .036, .014, .05, .07, col).cylz(xe, .036, .016, .07, .082, rub, r_in=.008).cylz(xe, .036, .008, .07, .078, (30, 30, 60))
        v.box(sx * .072 - .004, .036, .015, sx * .072 + .004, .046, .025, METAL)
    v.cylz(0, .044, .011, -.004, .052, (46, 46, 48)).box(-.03, .038, .0, .03, .046, .042, (46, 46, 48)).cylx(.058, .04, .014, -.012, .012, (54, 54, 56))
    for z in (.03, .04): v.box(-.012, .07, z, .012, .074, z + .005, (110, 110, 116))
    if strap and _g(p, 'courroie', 'strap', default=True):
        st = (40, 40, 42); v.line((-.076, .042, .02), (-.095, .003, .07), .004, st).line((-.095, .003, .07), (0, .003, .115), .005, st).line((0, .003, .115), (.095, .003, .07), .005, st).line((.095, .003, .07), (.076, .042, .02), .004, st)
    return v.boxes() + [tex(-.07, .0565, .0, -.042, .0575, .012, '+y', T.flat(T.plate('8X40', 14, 6, col, (210, 210, 214))), col)]


def v_bear(p, mode='assis'):
    fur = _col(p.get('color'), (150, 100, 60)); lt = (222, 192, 146); dark = (40, 26, 20); rib = _col(_g(p, 'ruban', 'ribbon'), (150, 30, 40)); v = Vox(.01)
    ell(v, 0, .09, .01, .072, .075, .062, fur)
    if mode == 'assis':
        for sx in (-1, 1): ell(v, sx * .045, .035, -.06, .03, .03, .055, fur); ell(v, sx * .045, .04, -.108, .034, .038, .013, fur)
    else:
        for sx in (-1, 1): ell(v, sx * .045, -.03, -.005, .03, .055, .03, fur); ell(v, sx * .045, -.09, -.012, .034, .014, .037, fur)
    ell(v, 0, .205, .0, .066, .058, .056, fur); ell(v, 0, .185, -.052, .03, .023, .022, lt)
    for sx in (-1, 1): ell(v, sx * .056, .264, .004, .023, .022, .014, fur)
    if mode == 'assis':
        for sx in (-1, 1): ell(v, sx * .082, .1, -.025, .022, .045, .024, fur); ell(v, sx * .09, .058, -.055, .02, .018, .02, fur)
    else:
        ell(v, -.078, .24, 0, .021, .1, .021, fur); ell(v, -.086, .345, 0, .02, .02, .02, fur)
        ell(v, .08, .095, -.005, .022, .045, .022, fur); ell(v, .086, .04, -.012, .02, .018, .02, fur)
    band = set(v._r(.146, .158))
    for key in list(v.v):
        if key[1] in band and abs(v.c(key[0])) < .056: v.v[key] = (tuple(rib), 0.)                                                     # ruban noué autour du cou
    paint_front(v, -.04, .05, .04, .13, lt)
    paint_front(v, .012, .08, .042, .11, (56, 84, 60)); paint_front(v, .022, .08, .032, .11, (170, 40, 40))
    for sx in (-1, 1): paint_front(v, sx * .056 - .01, .258, sx * .056 + .01, .272, lt)
    if mode == 'assis':
        for sx in (-1, 1): paint_front(v, sx * .045 - .018, .02, sx * .045 + .018, .06, lt)
    paint_front(v, -.01, .19, .01, .2, dark, bump=1)
    paint_front(v, -.04, .214, -.02, .232, (12, 12, 14)); paint_front(v, .018, .21, .04, .234, (70, 110, 160), bump=1); paint_front(v, .022, .218, .03, .226, (230, 222, 200), bump=1)
    paint_front(v, -.012, .252, -.004, .26, (96, 62, 38)); paint_front(v, .004, .244, .012, .252, (96, 62, 38))                     # couture recousue au front
    paint_front(v, -.03, .146, .03, .162, rib, bump=1); paint_front(v, -.008, .126, .008, .146, rib, bump=1)
    v.box(-.074, .14, -.04, -.054, .16, -.02, (244, 240, 230))
    return v.boxes()


def v_doll(p, mode='assis'):
    dress = _col(p.get('color'), (110, 34, 54)); lace = (238, 232, 218); skin = (242, 228, 216); hair = _col(_g(p, 'cheveux', 'hair'), (150, 96, 46))
    boot = (24, 20, 20); stk = (236, 232, 226); v = Vox(.006); out = []
    if mode == 'assis':
        v.cyl(0, 0, .098, 0, .006, lace).cyl(0, 0, .094, .006, .07, dress).cyl(0, .005, .068, .07, .12, dress)
        for sx in (-1, 1): v.box(sx * .03 - .013, .004, -.14, sx * .03 + .013, .03, -.08, stk).box(sx * .03 - .015, .004, -.162, sx * .03 + .015, .05, -.136, boot)
        y0 = .12
    else:
        for sx in (-1, 1): v.box(sx * .022 - .013, 0, -.022, sx * .022 + .013, .03, .014, boot).box(sx * .022 - .011, .03, -.011, sx * .022 + .011, .07, .011, stk)
        v.cyl(0, 0, .072, .062, .068, lace).cyl(0, 0, .07, .068, .138, dress).cyl(0, 0, .052, .138, .198, dress)
        y0 = .198
    v.box(-.04, y0, -.03, .04, y0 + .08, .03, dress).box(-.044, y0 + .075, -.033, .044, y0 + .087, .033, lace).box(-.042, y0, -.032, .042, y0 + .012, .032, _sh(dress, .6))
    for yy in (.02, .038, .056): cell(v, -.003, y0 + yy, -.034, (244, 240, 230))
    for sx in (-1, 1):
        ell(v, sx * .055, y0 + .062, 0, .019, .018, .022, dress)
        v.box(sx * .06 - .011, y0 - .004, -.023, sx * .06 + .011, y0 + .046, -.001, dress).box(sx * .06 - .013, y0 - .012, -.027, sx * .06 + .013, y0 - .004, .0, lace).box(sx * .06 - .009, y0 - .03, -.025, sx * .06 + .009, y0 - .012, -.007, skin)
    v.box(-.013, y0 + .084, -.013, .013, y0 + .1, .013, skin)
    hy = y0 + .1
    v.box(-.042, hy, -.039, .042, hy + .08, .039, skin).erase(-.042, hy, -.039, -.036, hy + .006, .039).erase(.036, hy, -.039, .042, hy + .006, .039)
    v.box(-.047, hy + .074, -.04, .047, hy + .094, .05, hair).box(-.047, hy + .0, .024, .047, hy + .09, .05, hair).box(-.04, hy + .066, -.044, .04, hy + .076, -.036, hair)
    for sx in (-1, 1):
        for i in range(4): v.box(sx * (.05 + .002 * i) - .009, hy + .042 - i * .022, .002 - .004 * i, sx * (.05 + .002 * i) + .009, hy + .068 - i * .022, .022 - .004 * i, _sh(hair, 1. - .1 * (i % 2)))
    bow = _col(_g(p, 'noeud', 'bow'), (238, 230, 214))
    v.box(-.011, hy + .088, -.01, .011, hy + .108, .01, bow).box(-.042, hy + .086, -.007, -.011, hy + .114, .007, bow).box(.011, hy + .086, -.007, .042, hy + .114, .007, bow)
    out.append(tex(-.036, hy + .004, -.0402, .036, hy + .074, -.0396, '-z', S.doll_face(fele=bool(_g(p, 'fele', 'cracked', default=True))), skin))
    out.append(tex(-.03, y0 + .004, -.0312, .03, y0 + .07, -.0306, '-z', S.doll_dress(col=dress), dress))
    return v.boxes() + out


def v_music_box(p):
    wood = _col(p.get('color'), (110, 60, 34)); vel = _col(_g(p, 'velours', 'velvet'), (140, 22, 42)); v = Vox(.005); out = []
    for sx in (-1, 1):
        for sz in (-1, 1): v.box(sx * .07 - .006, 0, sz * .04 - .006, sx * .07 + .006, .006, sz * .04 + .006, BRASS)
    y0 = .006
    v.box(-.08, y0, -.05, .08, y0 + .06, .05, wood)
    out.append(tex(-.078, y0 + .002, -.0512, .078, y0 + .058, -.0505, '-z', S.marquetry(wood=wood), wood))
    if _g(p, 'ferme', 'closed', default=False):
        v.box(-.082, y0 + .06, -.052, .082, y0 + .076, .052, wood).box(-.006, y0 + .046, -.056, .006, y0 + .058, -.05, BRASS)
        return v.boxes() + out + [tex(-.078, y0 + .076, -.048, .078, y0 + .077, .048, '+y', T.flat(S.marquetry(wood=wood)), wood)]
    v.erase(-.072, y0 + .042, -.042, .072, y0 + .061, .042)
    v.box(-.072, y0 + .036, -.042, .072, y0 + .042, .042, vel)
    w = Vox(.003)
    w.cylx(y0 + .03 + .012, .0, .008, -.066, -.032, BRASS).box(-.066, y0 + .048, -.024, -.032, y0 + .051, -.012, STEEL)
    for i in range(6): w.box(-.064 + i * .006, y0 + .051, -.002, -.061 + i * .006, y0 + .054, .001, (240, 236, 220))
    v.box(-.023, y0 + .036, -.042, -.018, y0 + .06, .042, _sh(wood, 1.2))
    bx_, fy = .025, y0 + .042
    w.cyl(bx_, 0, .016, fy, fy + .006, BRASS)
    pink = (238, 186, 196); sk = (240, 220, 206)
    w.box(bx_ - .003, fy + .006, -.002, bx_ + .0, fy + .034, .002, pink).box(bx_ + .003, fy + .024, -.002, bx_ + .006, fy + .036, .002, pink)
    w.cyl(bx_, 0, .016, fy + .03, fy + .036, (250, 240, 244)).cyl(bx_, 0, .012, fy + .036, fy + .04, (246, 230, 236))
    w.box(bx_ - .005, fy + .039, -.003, bx_ + .005, fy + .054, .003, pink).box(bx_ - .004, fy + .054, -.004, bx_ + .004, fy + .063, .004, sk).box(bx_ - .003, fy + .063, -.001, bx_ + .003, fy + .068, .005, (60, 36, 26))
    w.box(bx_ - .009, fy + .05, -.0015, bx_ - .006, fy + .066, .0015, sk).box(bx_ + .006, fy + .05, -.0015, bx_ + .009, fy + .066, .0015, sk).box(bx_ - .009, fy + .066, -.0015, bx_ + .009, fy + .069, .0015, sk)
    v.box(-.08, y0 + .06, .04, .08, y0 + .17, .052, wood).box(-.072, y0 + .066, .036, .072, y0 + .164, .04, vel)
    m = Vox(.004); oval(m, 0, y0 + .114, .07, .058, .032, .036, (200, 170, 90)); oval(m, 0, y0 + .114, .062, .05, .03, .036, (196, 208, 220))
    m.box(-.024, y0 + .126, .028, -.016, y0 + .13, .032, (246, 250, 255))
    v.box(.08, y0 + .027, -.003, .086, y0 + .033, .003, BRASS).box(.086, y0 + .02, -.008, .092, y0 + .045, .008, BRASS)
    out.append(tex(-.078, y0 + .062, .0525, .078, y0 + .168, .0532, '+z', S.marquetry(wood=wood), wood))
    return v.boxes() + w.boxes() + m.boxes() + out + [glass(-.072, y0 + .046, -.042, -.023, y0 + .048, .042, (150, 180, 200), .16)]


def v_mirror(p):
    """miroir debout, glace vers -z (couché pour être posé : objets_souvenirs._lay_up)"""
    fr = _col(p.get('color'), (186, 186, 192)); gl = (172, 192, 208); v = Vox(.005); W_, H_, yc = .14, .18, .24
    oval(v, 0, yc, W_, H_, -.005, .005, fr); oval(v, 0, yc, W_ - .024, H_ - .024, -.01, -.005, gl)
    oval(v, 0, yc, W_, H_, .005, .01, _sh(fr, 1.15), r0=.72, r1=.86); oval(v, 0, yc, .05, .07, .005, .01, _sh(fr, 1.15), r0=.7)
    for (x, y) in ((-.03, yc + .05), (-.026, yc + .045), (-.022, yc + .04)): cell(v, x, y, -.0075, (236, 244, 250))
    v.box(-.017, yc + H_ / 2 - .002, -.006, .017, yc + H_ / 2 + .016, .006, fr).box(-.006, yc + H_ / 2 + .016, -.005, .006, yc + H_ / 2 + .026, .005, fr)
    v.box(-.015, yc - H_ / 2 - .016, -.008, .015, yc - H_ / 2 + .004, .008, fr).box(-.013, .136, -.01, .013, .144, .01, fr)
    v.cyl(0, 0, .011, .035, .136, fr).cyl(0, 0, .013, .03, .036, fr).cyl(0, 0, .015, 0, .03, fr)
    if _g(p, 'fele', 'cracked', default=True):
        o = (.028, yc - .04)
        for (a, b_) in (((.018, -.012), (.034, -.03)), ((-.012, -.02), (-.018, -.048)), ((.004, .026), (-.01, .062)), ((-.022, .006), (-.044, .018)), ((.02, .01), (.03, .02))):
            for (p0, p1) in ((o, (o[0] + a[0], o[1] + a[1])), ((o[0] + a[0], o[1] + a[1]), (o[0] + b_[0], o[1] + b_[1]))):
                for t in np.linspace(0, 1, 10): cell(v, p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, -.0075, (70, 72, 80))
    return v.boxes()


def v_envelope(p):
    pap = _col(p.get('color'), (226, 214, 186)); v = Vox(.004); out = []
    if _g(p, 'dos', 'back', default=False): img = S.envelope_back(paper=pap, broken=bool(_g(p, 'lettre', 'letter', default=True)))
    else: img = S.envelope_front(str(_g(p, 'nom', 'name', default='MME C. ROUX')), T.lines(_g(p, 'adresse', 'address'), ('12 RUE DES LILAS', '76000 ROUEN')), paper=pap)
    v.box(-.17, 0, -.06, -.008, .004, .054, pap); out.append(tex(-.169, .004, -.059, -.009, .005, .053, '+y', T.flat(img), pap))
    if _g(p, 'lettre', 'letter', default=True):
        lt = S.letter_img(T.lines(_g(p, 'texte', 'text'))); H = lt.shape[0]
        for i, ya in enumerate((.004, .0, .004)):
            r0, r1 = H * i // 3, H * (i + 1) // 3; z0 = .105 - .21 * (i + 1) / 3
            v.box(0, ya, z0, .148, ya + .004, z0 + .07, (240, 234, 216))
            out.append(tex(.001, ya + .004, z0 + .001, .147, ya + .005, z0 + .069, '+y', T.flat(np.ascontiguousarray(lt[r0:r1])), (240, 234, 216)))
    return v.boxes() + out


def v_candelabra(p):
    m = _col(p.get('color'), (170, 134, 70)); wax = _col(_g(p, 'cire', 'wax'), (232, 222, 196)); lit = bool(_g(p, 'allumee', 'on', 'lit', default=True)); v = Vox(.006); out = []
    v.cyl(0, 0, .07, 0, .014, m).cyl(0, 0, .052, .014, .028, m).cyl(0, 0, .026, .028, .05, m).cyl(0, 0, .011, .05, .11, m).cyl(0, 0, .02, .11, .13, m).cyl(0, 0, .009, .13, .19, m).cyl(0, 0, .018, .19, .21, m).cyl(0, 0, .01, .21, .3, m)
    for sx in (-1, 1): v.line((0, .228, 0), (sx * .07, .212, 0), .0065, m).line((sx * .07, .212, 0), (sx * .115, .238, 0), .0065, m).line((sx * .115, .238, 0), (sx * .13, .268, 0), .0065, m)
    w = Vox(.004)
    for x, cy, h in ((-.13, .268, .11), (0., .3, .145), (.13, .268, .125)):
        v.cyl(x, 0, .02, cy, cy + .012, m).cyl(x, 0, .028, cy + .01, cy + .016, m)
        y0 = cy + .016; w.cyl(x, 0, .011, y0, y0 + h, wax).cyl(x, 0, .007, y0 + h - .004, y0 + h, _sh(wax, .9))
        w.box(x + .008, y0 + h - .03, -.002, x + .014, y0 + h, .004, wax).box(x - .014, y0 + h - .05, -.01, x - .008, y0 + h - .01, -.004, wax).box(x + .008, y0, .002, x + .02, y0 + .006, .014, wax)
        top = y0 + h; w.box(x - .002, top, -.002, x + .002, top + .01, .002, (26, 20, 18))
        if lit:
            w.box(x - .004, top + .008, -.004, x + .004, top + .024, .004, (255, 240, 180), 2.8)
            out.append(glass(x - .008, top + .006, -.008, x + .008, top + .038, .008, (255, 150, 50), .5, 1.6))
    return v.boxes() + w.boxes() + out


def _vaxe_lying(p):
    """hache sculptée couchée le long de x (fer en +x, tranchant vers -z, joues vers le haut et le bas)"""
    wood = _col(p.get('color'), (156, 112, 68)); st = (74, 76, 82); br = (206, 210, 216); rust = (122, 64, 32); v = Vox(.004)
    v.box(0, -.014, -.016, .05, .014, .028, wood).box(.05, -.012, -.012, .21, .012, .022, _sh(wood, .78)).box(.21, -.012, -.014, .47, .012, .018, wood).box(.47, -.012, -.015, .6, .012, .015, wood)
    v.box(.6, -.012, -.032, .71, .012, .032, st).box(.615, -.011, .032, .695, .011, .06, st).box(.618, -.012, .06, .692, .012, .064, (90, 92, 98))
    v.box(.59, -.01, -.07, .72, .01, -.032, st).box(.578, -.008, -.11, .732, .008, -.07, st).box(.566, -.006, -.14, .744, .006, -.11, _sh(st, 1.15)).box(.562, -.004, -.152, .748, .004, -.14, br)
    v.box(.71, -.008, -.014, .718, .008, .014, wood)
    for (x, z) in ((.63, -.09), (.66, -.05), (.64, .0)): v.box(x, .008, z, x + .02, .012, z + .016, rust)
    return v.boxes()


def v_axe(p):
    if not _g(p, 'billot', 'block', default=False): return S._floor(S._shift(_vaxe_lying(p), -.36, 0., 0.))
    wood = (128, 92, 58); bark = (70, 52, 38); st = (74, 76, 82); v = Vox(.01)
    v.cyl(0, 0, .2, 0, .33, bark)
    for i in v._r(-.2, .2):
        for k in v._r(-.2, .2):
            d = math.hypot(v.c(i), v.c(k))
            if d < .19: v.put(i, 33, k, wood if int(d / .03) % 2 == 0 else _sh(wood, .82))
    v.box(.0, .33, .01, .1, .34, .02, _sh(wood, .5))
    w = Vox(.006); top = .34
    w.box(-.012, top - .02, -.07, .012, top + .025, .03, st).box(-.012, top + .025, -.045, .012, top + .055, .005, st).box(-.011, top + .045, .0, .011, top + .075, .03, st)
    hw = _col(p.get('color'), (156, 112, 68)); w.line((0, top + .05, .02), (0, top + .3, .55), .014, hw).box(-.016, top + .29, .55, .016, top + .33, .59, hw)
    return v.boxes() + w.boxes()


def _vknife_lying(p):
    """grand couteau sculpté couché le long de x (pointe en +x, tranchant vers -z, à plat)"""
    hd = _col(p.get('color'), (26, 24, 24)); st = (138, 142, 150); br = (184, 188, 196); v = Vox(.003)          # acier plus sombre qu'en PS1 : le peintre VOXEL fait briller l'acier clair
    v.box(.0, -.009, -.015, .12, .009, .015, hd).box(0, -.0105, -.017, .008, .0105, .017, (60, 60, 64))
    for x in (.025, .06, .095):
        for sy in (-1, 1): v.box(x - .004, sy * .009 - (.0015 if sy < 0 else 0), -.004, x + .004, sy * .009 + (.0015 if sy > 0 else 0), .004, METAL)
    v.box(.12, -.006, -.022, .134, .006, .018, st)
    n = 24; x0, L = .134, .22
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n; tm = (t0 + t1) / 2
        ze = -.036 + .036 * tm ** 1.8; zs = .016 - .012 * tm ** 3
        v.box(x0 + L * t0, -.0015, ze + .004, x0 + L * t1, .0015, zs, st).box(x0 + L * t0, -.0015, ze, x0 + L * t1, .0015, ze + .004, br)
    v.box(.2, .0015, -.012, .218, .003, -.0, (90, 82, 70))
    return v.boxes()


def v_knife(p): return S._floor(S._shift(_vknife_lying(p), -.18, 0., 0.))


def v_syringe(p):
    m = _col(p.get('color'), METAL); y = .009; v = Vox(.003)
    liq = {'vert': (110, 220, 120), 'ambre': (214, 140, 40), 'clair': (190, 220, 236), 'noir': (30, 30, 34)}.get(str(_g(p, 'contenu', default='vert')), (110, 220, 120))
    v.cylx(y, 0, .0064, -.005, .078, liq, em=.25 if _g(p, 'contenu', default='vert') == 'vert' else 0.)
    v.cylx(y, 0, .0064, -.01, -.005, (40, 40, 44)).cylx(y, 0, .0022, -.02, -.01, m)
    for i in range(10): x = -.012 + i * .009; v.box(x, y + .0075, -.001, x + .0015, y + .0095, .001, (40, 52, 64))
    v.cylx(y, 0, .0092, .078, .088, m).cylx(y, 0, .0042, .088, .1, m).box(.1, y - .0015, -.0015, .145, y + .0015, .0015, (226, 230, 236))
    v.cylx(y, 0, .0098, -.027, -.019, m)
    for sz in (-1, 1):
        cz = sz * .023; v.box(-.033, .0, cz - .01, -.013, .004, cz + .01, m).erase(-.029, .0, cz - .006, -.017, .004, cz + .006).box(-.026, .003, sz * .009 - .003, -.02, .007, sz * .014 + .003, m)
    v.box(-.069, y - .002, -.002, -.027, y + .002, .002, m).box(-.071, .003, -.004, -.067, .009, .004, m)
    v.box(-.091, 0, -.011, -.069, .004, .011, m).erase(-.087, 0, -.007, -.073, .004, .007)
    return v.boxes() + _glass_x(-.02, .08, y, 0, .0085, (206, 220, 226), .3)


# ================================================================== held (VOXEL), same grips as PS1
def _f(cfg, d='front'): return S._face(cfg, d)


def hv_polaroid(col, cfg):
    fc = _f(cfg); cfg = dict(cfg); cfg['color'] = col
    return _vhold(_vpolaroid(cfg, _g(cfg, 'photo', default='silhouette') is not False, painted=True), S._grip(fc, 0., .0, 0., .095), fc), []


def hv_polaroid_photo(col, cfg):
    fc = _f(cfg); img = S.polaroid_img(str(_g(cfg, 'photo', default='silhouette')), str(_g(cfg, 'legende', 'caption', default='')))
    v = Vox(.004); v.box(-.044, 0, .0, .044, .108, .004, (70, 72, 74))
    bx = v.boxes() + [tex(-.044, 0, -.002, .044, .108, -.001, '-z', img, (242, 240, 232))]
    return _vhold(bx, S._grip(fc, 0., .0, 0., .095), fc), []


def hv_walkie(col, cfg):
    fc = _f(cfg, 'holder'); c = dict(cfg); c['color'] = col
    return _vhold(v_walkie(c), S._grip(fc, 0., .02, 0., .07), fc), []


def hv_binoculars(col, cfg):
    fc = _f(cfg); c = dict(cfg); c['color'] = col
    return _vhold(v_binoculars(c, strap=False), S._grip(fc, 0., -.035, 0., .08), fc), []


def hv_bear(col, cfg):
    fc = _f(cfg); c = dict(cfg); c['color'] = col
    return _vhold(v_bear(c, 'pendu'), S._grip(fc, -.086, .345, 0., .05), fc), []


def hv_doll(col, cfg):
    fc = _f(cfg); c = dict(cfg); c['color'] = col
    return _vhold(v_doll(c, 'debout'), S._grip(fc, 0., .215, 0., .055), fc), []


def hv_mirror(col, cfg):
    fc = _f(cfg, 'holder'); c = dict(cfg); c['color'] = col
    return _vhold(v_mirror(c), S._grip(fc, 0., .07, 0., .04), fc), []


def hv_envelope(col, cfg):
    lt = S.letter_img(T.lines(cfg.get('texte'))); pap = _col(col, (226, 214, 186))
    env = S.envelope_front(str(cfg.get('nom', 'MME C. ROUX')), T.lines(cfg.get('adresse'), ('12 RUE DES LILAS', '76000 ROUEN')), paper=pap)
    v = Vox(.004); v.box(-.074, 0, -.002, .074, .21, .002, (240, 234, 216)); v.box(-.03, -.03, .006, .132, .084, .01, pap)
    bx = v.boxes() + [tex(-.073, .001, -.0035, .073, .209, -.0025, '-z', lt, (240, 234, 216)), tex(-.073, .001, .0025, .073, .209, .0035, '+z', lt, (240, 234, 216)),
                      tex(-.029, -.029, .0105, .131, .083, .0115, '+z', S.envelope_back(paper=pap), pap)]
    return _vhold(bx, S._grip('front', 0., .03, 0., .09), 'front'), []


def hv_axe(col, cfg):
    c = dict(cfg); c['color'] = col; bx = _stand_x(_vaxe_lying(c)); ay = .52 if cfg.get('prise') == 'haut' else .16
    if cfg.get('tranchant') != 'avant': return _vhold(S._edge_out(bx), (.004, ay, .02), 'front'), []
    return _vhold(bx, (0., ay, .024), 'front'), []


def hv_knife(col, cfg):
    c = dict(cfg); c['color'] = col; bx = _stand_x(_vknife_lying(c)); ay = .06
    if cfg.get('lame') == 'bas':
        for b in bx:
            lo, hi = b.lo.copy(), b.hi.copy(); b.lo = np.array([-hi[0], -hi[1], lo[2]], np.float32); b.hi = np.array([-lo[0], -lo[1], hi[2]], np.float32)
        ay = -.06
    if cfg.get('tranchant') != 'avant': bx = S._edge_out(bx)
    return _vhold(bx, (0., ay, .02), 'front'), []


def hv_cassette(col, cfg):
    lab = T.lines(_g(cfg, 'etiquette', 'label'), ('NE PAS', 'ECOUTER')); fc = _f(cfg); sh = _col(col, (36, 36, 40))
    v = Vox(.004); v.box(-.05, 0, -.004, .05, .064, .008, sh).box(-.03, -.002, -.003, .03, .0, .006, (20, 20, 22))
    bx = v.boxes() + [tex(-.049, .001, -.0055, .049, .063, -.0045, '-z', S.cassette_face(lab, shell=sh), sh)]
    return _vhold(bx, S._grip(fc, 0., -.02, 0., .09), fc), []


# ================================================================== registration (b_objets._load_lots)
POSED = {'od_typewriter': v_typewriter, 'od_tape_recorder': v_tape_recorder, 'od_cassette': v_cassette, 'od_film_camera': v_film_camera, 'od_polaroid': v_polaroid,
         'od_walkie_talkie': v_walkie, 'od_binoculars': v_binoculars, 'od_teddy_bear': lambda p: v_bear(p, 'assis'), 'od_porcelain_doll': lambda p: v_doll(p, 'assis'),
         'od_music_box': v_music_box, 'od_hand_mirror': lambda p: S._floor(S._shift(S._lay_up(v_mirror(p)), 0., 0., -.18)), 'od_envelope': v_envelope,
         'od_candelabra': v_candelabra, 'od_axe': v_axe, 'od_knife_horror': v_knife, 'od_syringe': v_syringe}
HELD = {'od_polaroid': hv_polaroid, 'od_polaroid_photo': hv_polaroid_photo, 'od_walkie_talkie': hv_walkie, 'od_binoculars': hv_binoculars, 'od_teddy_bear': hv_bear,
        'od_porcelain_doll': hv_doll, 'od_hand_mirror': hv_mirror, 'od_envelope': hv_envelope, 'od_axe': hv_axe, 'od_knife_horror': hv_knife, 'od_cassette': hv_cassette}


def enregistrer(R):
    for k, fn in POSED.items():
        try: R.objet(k, fn)
        except ValueError as e: print(e)
    for k, fn in HELD.items():
        try: R.tenu(k, fn)
        except ValueError as e: print(e)
