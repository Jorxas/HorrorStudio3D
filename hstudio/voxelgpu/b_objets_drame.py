"""OBJETS DÉTAILLÉS, LOT « drame » (09/11/2026), version VOXEL native (la version PS1 est engines/pixel3d/objets_drame.py).

Découvert tout seul par `b_objets._load_lots()` (fichier `b_objets_<lot>.py`). Même plan et mêmes réglages que PS1 (`objets_drame.carnet_params`,
`bouquet_params`, `billet_params`), autre exécution : chaque objet est SCULPTÉ en cubes sur une grille fine :
  carnet   plats de toile en cubes de 4 mm aux coins élimés (carton gris-beige), pages en couches alternées (la tranche se lit), dos déchiré, élastique
           et feuilles volantes en cubes de 2 mm ; la toile, les deux pages (dessin + légende) et la tranche restent des décalcomanies (images de PS1) ;
  bouquet  cornet de kraft lissé rang par rang (cubes de 8 mm, un pli), ruban qui fait le tour, nœud à deux boucles percées, pans, papier de soie en
           dents, roses en boules de cubes de 5 mm au cœur plus sombre, lys en étoiles à six pétales et étamines, gypsophile, feuillage ; la photo
           d'identité est une décalcomanie ;
  billet   une feuille : mêmes facettes que PS1 (un billet n'a pas d'épaisseur à sculpter), recto / verso en décalcomanies.
Une image découpée en décalcomanies côte à côte (billet froissé, toile de part et d'autre de l'élastique) est redistribuée par `vcols` / `vreverse` :
VOXEL les place en miroir sans retourner les images.
Un objet tenu est le même objet tourné vers l'avant (ou vers celui qui le tient), saisi plus loin du poing qu'en PS1 (le poing VOXEL fait 16 x 20 cm)."""
import math
import numpy as np
from ..engines.pixel3d import objets as OD, objets_tex as T, objets_drame as D, objets_souvenirs as S
from ..engines.pixel3d.r3d import B
from .b_objets import Vox, tex
from .b_objets_souvenirs import ell, _vhold

_g, _sh = OD._g, OD._sh
PAGE2 = (212, 202, 180)                                                 # couche de pages plus sombre (la tranche se lit en lignes)
GRIP_VOX = {'carnet_y': .04, 'carnet_d': .125, 'ouvert_e': .07, 'ouvert_d': .07, 'lire_y': -.06, 'lire_d': .05, 'bouquet_y': .07, 'bouquet_d': .02, 'billet_d': .11}       # poing VOXEL : 16 x 20 cm


def _cw(col, m): return T._shade(col, .8) if m else tuple(col)


# VOXEL place les décalcomanies côte à côte d'une même image EN MIROIR (x -> -x) sans retourner leurs images (vu sur planche : billet froissé lu
# « 2E CL... BILLET ») : une tranche [a, b] (repère PS1, objet centré en x) porte donc l'image de la tranche miroir [-b, -a].
def vcols(img, a, b, x0, x1, back=False):
    """colonnes d'image d'une tranche [a, b] d'un objet [x0, x1] (x0 = -x1) en VOXEL ; `back` : face arrière (+z, image lue de derrière)"""
    W = np.asarray(img).shape[1]; L = x1 - x0
    u0, u1 = ((x1 + a) / L, (x1 + b) / L) if back else ((-b - x0) / L, (-a - x0) / L)
    c0, c1 = int(round(max(0., u0) * W)), int(round(min(1., u1) * W))
    return D.cols(img, c0, max(c1, c0 + 1))


def vreverse(bx, key):
    """tranches d'égale largeur portant une même image sur la face `key` : ordre inversé pour VOXEL (voir vcols)"""
    st = sorted([b for b in bx if key in (b.tex or {})], key=lambda b: float(b.lo[0] + b.hi[0]))
    tx = [b.tex[key] for b in st]
    for b, t in zip(st, reversed(tx)): b.tex[key] = t
    return bx


# ================================================================== carnet
def _slab(x0, y0, z0, x1, y1, z1, col):
    """plaque fine (élastique, feuille volante) : une seule boîte, sans grain (une grille de 2 mm en ferait des centaines de rangées)"""
    return B((x0, y0, z0), (x1 - x0, y1 - y0, z1 - z0), col, grain=0.)


def v_carnet_ferme(col, m):
    cw = _cw(col, m); v = Vox(.004); out = []
    v.box(-.104, 0, -.076, .104, .004, .076, _sh(cw, .9))
    for j, y in enumerate((.004, .008, .012)): v.box(-.1, y, -.072, .1, y + .004, .072, D.PAGE if j % 2 == 0 else PAGE2)
    v.box(-.108, 0, -.076, -.104, .02, .076, _sh(cw, .82)).box(-.108, .008, .016, -.104, .012, .044, D.BOARD)          # dos, déchirure qui montre le carton
    cv = D.canvas(col, m); W = cv.shape[1]
    if m:                                                               # pages gonflées : le plat monte vers la tranche en trois marches
        for i, (a, b) in enumerate(D.segs(3, W)):
            x0 = -.104 + .208 * i / 3; y = .016 + .002 * i
            out.append(B((x0, y, -.076), (.208 / 3, .004, .152), cw))
        top = .024
    else:
        v.box(-.104, .016, -.076, .104, .02, .076, cw); top = .02
    for (x, z) in ((-.104, -.076), (.096, -.076), (-.104, .068), (.096, .068)): v.box(x, top - .004, z, x + .008, top, z + .008, D.BOARD)
    out += [_slab(.07, top, -.078, .078, top + .002, .078, D.ELASTIC), _slab(.07, 0, -.08, .078, top + .002, -.078, D.ELASTIC), _slab(.07, 0, .078, .078, top + .002, .08, D.ELASTIC),
            _slab(.05, .008, -.052, .118, .01, .044, D.SHEET), _slab(-.04, .012, .02, .046, .014, .09, D.OLD_SHEET), _slab(-.086, .004, -.086, -.036, .006, -.046, (244, 240, 228))]
    xe0, xe1 = .07, .078
    if m:
        for i in range(3):
            x0 = -.104 + .208 * i / 3; x1 = x0 + .208 / 3; y = .02 + .002 * i
            for (u0, u1) in ((x0, min(x1, xe0)), (max(x0, xe1), x1)):
                if u1 - u0 > .004: out.append(tex(u0, y, -.075, u1, y + .001, .075, '+y', T.flat(vcols(cv, u0, u1, -.104, .104)), cw))
    else:
        out += [tex(-.104, top, -.075, xe0, top + .001, .075, '+y', T.flat(vcols(cv, -.104, xe0, -.104, .104)), cw),
                tex(xe1, top, -.075, .104, top + .001, .075, '+y', T.flat(vcols(cv, xe1, .104, -.104, .104)), cw)]
    out += [tex(-.1085, .001, -.075, -.1082, .019, .075, '-x', D.spine(col, m), _sh(cw, .82)), tex(-.085, .006, -.0855, -.037, .0062, -.0755, '+y', T.flat(D.scrap()), (244, 240, 228))]
    return v.boxes() + out


def v_carnet_ouvert(col, dessin, leg, m):
    cw = _cw(col, m); v = Vox(.004); out = []
    v.box(-.212, 0, -.076, -.004, .004, .076, cw).box(.004, 0, -.076, .212, .004, .076, cw).box(-.004, 0, -.076, .004, .004, .076, _sh(cw, .7))
    for x0, x1 in ((-.208, -.004), (.004, .208)):
        v.box(x0, .004, -.072, x1, .008, .072, PAGE2).box(x0, .008, -.072, x1, .012, .072, D.PAGE)
    for (x, z) in ((-.212, -.076), (.204, -.076), (-.212, .068), (.204, .068)): v.box(x, 0, z, x + .008, .004, z + .008, D.BOARD)
    out += [_slab(.206, .002, -.046, .226, .004, -.038, D.ELASTIC), _slab(.222, 0, -.06, .228, .002, .06, D.ELASTIC), _slab(-.16, .01, .05, -.084, .012, .102, D.OLD_SHEET)]
    sp = D.spread(dessin, leg, m); H = sp.shape[0]
    if m:
        for i, (a, b) in enumerate(D.segs(4, H)):
            z1 = .072 - .144 * a / H; z0 = .072 - .144 * b / H; dy = (0., .0012, .0004, .0016)[i]
            out += [B((-.206, .012, z0), (.412, dy + .0004, z1 - z0), D.PAPER_SK), tex(-.206, .012 + dy, z0, .206, .0122 + dy, z1, '+y', T.flat(D.rows(sp, a, b)), D.PAPER_SK)]
    else:
        out.append(tex(-.206, .012, -.0715, .206, .0122, .0715, '+y', T.flat(sp), D.PAPER_SK))
    return v.boxes() + out


def v_carnet(p):
    col, ouvert, dessin, leg, m = D.carnet_params(p)
    return v_carnet_ouvert(col, dessin, leg, m) if ouvert else v_carnet_ferme(col, m)


def _vcarnet_debout(col, m):
    """carnet fermé debout : couverture vers -z, dos à gauche, y de 0 à 0,15"""
    cw = _cw(col, m); v = Vox(.004); out = []
    v.box(-.104, 0, -.012, .104, .152, -.008, cw).box(-.104, 0, .008, .104, .152, .012, _sh(cw, .92))
    for k_, z in enumerate((-.008, -.004, 0., .004)): v.box(-.1, .004, z, .1, .148, z + .004, D.PAGE if k_ % 2 == 0 else PAGE2)
    v.box(-.108, 0, -.012, -.104, .152, .012, _sh(cw, .82)).box(-.108, .09, -.008, -.104, .114, .008, D.BOARD)
    for (x, y) in ((-.104, 0), (.096, 0), (-.104, .144), (.096, .144)):
        v.box(x, y, -.012, x + .008, y + .008, -.008, D.BOARD).box(x, y, .008, x + .008, y + .008, .012, D.BOARD)
    out += [_slab(.07, -.002, -.0144, .078, .154, -.012, D.ELASTIC), _slab(.07, -.002, .012, .078, .154, .0144, D.ELASTIC), _slab(.07, .152, -.0144, .078, .154, .0144, D.ELASTIC),
            _slab(.07, -.002, -.0144, .078, 0, .0144, D.ELASTIC), _slab(.05, .03, -.002, .118, .12, 0, D.SHEET), _slab(-.06, -.012, .002, .016, .068, .004, D.OLD_SHEET)]
    cv = D.canvas(col, m); bk = D.canvas(col, m, seed=1)
    for (u0, u1) in ((-.104, .07), (.078, .104)):
        out += [tex(u0, .001, -.0122, u1, .151, -.0121, '-z', vcols(cv, u0, u1, -.104, .104), cw), tex(u0, .001, .0121, u1, .151, .0122, '+z', vcols(bk, u0, u1, -.104, .104, back=True), cw)]
    out.append(tex(-.1083, .001, -.011, -.1082, .151, .011, '-x', np.ascontiguousarray(np.rot90(D.spine(col, m))), _sh(cw, .82)))
    return v.boxes() + out


def _vcarnet_ouvert_debout(col, dessin, leg, m):
    """carnet ouvert debout : les deux pages vers -z (une image), les plats de toile derrière"""
    cw = _cw(col, m); v = Vox(.004); out = []
    v.box(-.212, 0, 0, -.004, .156, .004, cw).box(.004, 0, 0, .212, .156, .004, cw).box(-.004, 0, 0, .004, .156, .008, _sh(cw, .7))
    for x0, x1 in ((-.208, -.004), (.004, .208)):
        v.box(x0, .004, -.008, x1, .152, -.004, D.PAGE).box(x0, .004, -.004, x1, .152, 0, PAGE2)
    for (x, y) in ((-.212, 0), (.204, 0), (-.212, .148), (.204, .148)): v.box(x, y, 0, x + .008, y + .008, .004, D.BOARD)
    out += [_slab(.17, -.016, .004, .178, .154, .006, D.ELASTIC), _slab(-.17, .1, -.006, -.1, .17, -.004, D.OLD_SHEET)]
    sp = D.spread(dessin, leg, m); H = sp.shape[0]
    if m:
        for i, (a, b) in enumerate(D.segs(4, H)):
            y1 = .149 - .144 * a / H; y0 = .149 - .144 * b / H; dz = (0., .0012, .0004, .0016)[i]
            out += [B((-.206, y0, -.0082 - dz), (.412, y1 - y0, dz + .0002), D.PAPER_SK), tex(-.206, y0, -.0084 - dz, .206, y1, -.0082 - dz, '-z', D.rows(sp, a, b), D.PAPER_SK)]
    else:
        out.append(tex(-.206, .005, -.0084, .206, .149, -.0082, '-z', sp, D.PAPER_SK))
    out += [tex(-.211, .001, .0041, -.005, .155, .0042, '+z', D.canvas(col, m, seed=1), cw), tex(.005, .001, .0041, .211, .155, .0042, '+z', D.canvas(col, m, seed=2), cw)]
    return v.boxes() + out


# ================================================================== bouquet
def _front_cells(v):
    f = {}
    for (i, j, k) in v.v:
        if f.get((i, j), 10 ** 9) > k: f[(i, j)] = k
    return f


def _vbouquet(fl, rib, pap, photo):
    """bouquet debout, y de 0 à 0,46 ; -> (boîtes, marques {'knot': (i0, i1)} du groupe photo + nœud + pans)"""
    fl2, fl3 = _sh(fl, .88), _sh(fl, .7); v = Vox(.01); f = Vox(.0065); kv = Vox(.004)
    for i, (x, z) in enumerate(((-.016, -.006), (-.006, .008), (.004, -.01), (.014, .004), (0., 0.), (-.012, .014), (.01, .014))):
        v.box(x * 1.5 - .004, .01, z * 1.5 - .004, x * 1.5 + .004, .05, z * 1.5 + .004, D.GREEN if i % 2 else D.GREEN2)
        v.box(x * 1.5 - .004, 0, z * 1.5 - .004, x * 1.5 + .004, .01, z * 1.5 + .004, (178, 198, 134))
    y0c, n, h, w0, dw = D.CONE
    def radius(y): return (w0 + dw * (y - y0c) / h) / 2
    for j in v._r(y0c, D.CONE_TOP):
        y = v.c(j); rx = radius(y); band = D.KNOT_Y - .015 <= y <= D.KNOT_Y + .004
        if band: rx += .004
        rz = rx * .62 + (.002 if band else 0.)
        for i in v._r(-rx, rx):
            for k in v._r(.006 - rz, .006 + rz):
                if (v.c(i) / rx) ** 2 + ((v.c(k) - .006) / rz) ** 2 <= 1.08: v.put(i, j, k, rib if band else _sh(pap, 1. - .05 * ((j // 3) % 2)))
    fr = _front_cells(v)
    for j in v._r(y0c, D.CONE_TOP):
        y = v.c(j)
        if D.KNOT_Y - .015 <= y <= D.KNOT_Y + .004: continue
        i = int(math.floor((-.03 + .004 * (y - y0c) / h) / v.u))
        if (i, j) in fr: v.put(i, j, fr[(i, j)], _sh(pap, .72))                                   # le pli du papier
    rt = radius(D.CONE_TOP - .01)
    for j in v._r(D.CONE_TOP - .01, D.CONE_TOP + .035):
        for a in range(0, 360, 6):
            r = math.radians(a); tooth = (a // 36) % 2
            if v.c(j) > D.CONE_TOP + .02 and not tooth: continue
            v.put(int(math.floor(math.cos(r) * rt / v.u)), j, int(math.floor((.006 + math.sin(r) * rt * .62) / v.u)), (246, 244, 238))
    for (x, y, z) in D.ROSES:
        ell(f, x, y, z, .026, .021, .026, fl)
        for key in list(f.v):
            cx, cy, cz = f.c(key[0]) - x, f.c(key[1]) - y, f.c(key[2]) - z
            if abs(cx) < .03 and abs(cz) < .03 and abs(cy) < .025:
                rr = math.hypot(cx, cz)
                if cy > .01 and (rr < .006 or .011 < rr < .015): f.v[key] = (fl3 if rr < .006 else fl2, 0.)          # cœur et anneau de pétales
        f.box(x - .01, y - .028, z - .01, x + .01, y - .02, z + .01, D.GREEN2)
    for (x, y, z) in D.LILIES:
        c0 = np.array((x, y, z)); f.box(x - .008, y - .01, z - .008, x + .008, y + .01, z + .008, (222, 232, 190))
        for kk in range(6):
            a = math.radians(kk * 60 + 30); tip = c0 + np.array((math.cos(a) * .058, .026, math.sin(a) * .046))
            f.line(tuple(c0 + (0, .006, 0)), tuple(tip), .006, fl if kk % 2 else fl2)
        for kk in range(3):
            a = math.radians(kk * 120); dx, dz = math.cos(a) * .008, math.sin(a) * .008
            f.line((x + dx, y + .008, z + dz), (x + dx, y + .026, z + dz), .001, (206, 216, 160)).box(x + dx - .0025, y + .026, z + dz - .0025, x + dx + .0025, y + .031, z + dz + .0025, (170, 82, 40))
    for kk in range(12):
        a = math.radians(kk * 30 + 7); r = .1 + .012 * (kk % 3); x, y, z = math.cos(a) * r, .31 + .07 * ((kk * 7) % 5) / 5, .006 + math.sin(a) * r * .75
        f.box(x - .005, y - .005, z - .005, x + .005, y + .005, z + .005, (250, 250, 248))
    for kk in range(9):
        a = math.radians(kk * 40 + 20)
        f.line((math.cos(a) * .05, .29, .006 + math.sin(a) * .04), (math.cos(a) * .135, .31 + .014 * (kk % 2), .006 + math.sin(a) * .1), .0075, D.GREEN if kk % 2 else D.GREEN3)
    f.line((-.03, .3, .05), (-.055, .455, .07), .006, D.GREEN3).line((.035, .3, .05), (.06, .445, .075), .006, D.GREEN3)
    ky = D.KNOT_Y; zf = .006 - (radius(ky) + .004) * .62 - .002; bx_ = .056
    for sx in (-1, 1):
        x0, x1 = (bx_ - .034, bx_ - .004) if sx < 0 else (bx_ + .004, bx_ + .034)
        kv.box(x0, ky - .009, zf - .01, x1, ky + .013, zf, rib).erase(x0 + .008, ky - .003, zf - .01, x1 - .008, ky + .007, zf)
    kv.box(bx_ - .006, ky - .012, zf - .014, bx_ + .006, ky + .004, zf - .002, _sh(rib, .82))
    kv.line((bx_ - .004, ky - .012, zf - .008), (bx_ - .016, ky - .08, zf - .011), .0035, rib).line((bx_ + .004, ky - .012, zf - .008), (bx_ + .02, ky - .072, zf - .01), .0035, rib)
    out = v.boxes() + f.boxes(); k0 = len(out)
    out += kv.boxes()
    if photo:                                                           # photo glissée sous le ruban : un brin de ruban passe devant son bas
        out += [B((-.02, ky - .012, zf - .006), (.04, .05, .002), (250, 250, 246)), tex(-.0195, ky - .0115, zf - .0064, .0195, ky + .0375, zf - .0062, '-z', D.id_photo(photo), (250, 250, 246)),
                B((-.026, ky - .015, zf - .013), (.052, .018, .006), rib, grain=0.)]
    return out, {'knot': (k0, len(out))}


def v_bouquet(p):
    fl, rib, pap, photo, debout = D.bouquet_params(p)
    bx, mk = _vbouquet(fl, rib, pap, photo)
    return D.lean(bx, .3, ref=D.knot_ref(mk)) if debout else D.lay_bouquet(bx, mk)


# ================================================================== billet (a sheet of paper: same facets as PS1, images as decals)
def v_billet(p):
    tx, fr, pap = D.billet_params(p)
    return vreverse(D.b_billet_flat(tx, fr, pap), 3)


# ================================================================== held (VOXEL) : repère de la main P(lat, haut, avant), même prise que PS1, plus loin du poing
def hv_carnet(col, cfg):
    p = D.merged('od_carnet', cfg); colr, _, _, _, m = D.carnet_params(p, col); fc = S._face(p)
    return _vhold(_vcarnet_debout(colr, m), S._grip(fc, 0., GRIP_VOX['carnet_y'], 0., GRIP_VOX['carnet_d']), fc), []


def hv_carnet_ouvert(col, cfg):
    p = D.merged('od_carnet_ouvert', cfg); colr, _, d, leg, m = D.carnet_params(p, col); fc = S._face(p, 'holder')
    return _vhold(_vcarnet_ouvert_debout(colr, d, leg, m), S._grip(fc, 0., GRIP_VOX['lire_y'], 0., GRIP_VOX['lire_d']), fc), []


def hv_carnet_montre(col, cfg):
    p = D.merged('od_carnet_montre', cfg); colr, _, d, leg, m = D.carnet_params(p, col); fc = S._face(p, 'front')
    return _vhold(_vcarnet_ouvert_debout(colr, d, leg, m), D.open_grip(fc, GRIP_VOX['ouvert_e'], GRIP_VOX['ouvert_d']), fc), []


def hv_bouquet(col, cfg):
    fl, rib, pap, photo, _ = D.bouquet_params(cfg, col); fc = S._face(cfg)
    bx, _mk = _vbouquet(fl, rib, pap, photo)
    return _vhold(bx, S._grip(fc, 0., GRIP_VOX['bouquet_y'], .006, GRIP_VOX['bouquet_d']), fc), []


def hv_billet(col, cfg):
    tx, fr, pap = D.billet_params(cfg, col); fc = S._face(cfg)
    return _vhold(vreverse(vreverse(D.b_billet_debout(tx, fr, pap), 4), 5), S._grip(fc, 0., -.04, 0., GRIP_VOX['billet_d']), fc), []


# ================================================================== registration (b_objets._load_lots)
POSED = {'od_carnet': v_carnet, 'od_bouquet': v_bouquet, 'od_billet': v_billet}
HELD = {'od_carnet': hv_carnet, 'od_carnet_ouvert': hv_carnet_ouvert, 'od_carnet_montre': hv_carnet_montre, 'od_bouquet': hv_bouquet, 'od_billet': hv_billet}


def enregistrer(R):
    for k, fn in POSED.items():
        try: R.objet(k, fn)
        except ValueError as e: print(e)
    for k, fn in HELD.items():
        try: R.tenu(k, fn)
        except ValueError as e: print(e)
