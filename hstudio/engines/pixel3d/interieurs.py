"""Intérieurs variés (V3, chantier « bâtiments et intérieurs variés ») : DIX palettes franches, des sols qui ne sont plus « du brun », des détails de vie
(livres, plantes, cadres, rideaux, tapis, lampes, vaisselle, coussins, vases) et six lieux complets : appartement (4 dispositions), hall d'immeuble,
cage d'escalier, café, boutique, salon. Tout en PS1 ici ; la version VOXEL native des mêmes détails est dans `voxelgpu/b_interieurs.py`.

Le constat (31/10/2026) : « la maison qu'on a faite, on dirait la même que dans Ascenseur Zéro, la même partout ». Mesuré : `places.py` livre UNE pièce par type, aux mêmes
coordonnées, murs et sols pris dans `sets.WALLS` / `FLOORS` (beige, brun, gris : neuf teintes ternes), et la passe `variation` (environment_variation.py), opt-in, ne change
ni les couleurs ni la forme. Ici : une palette = murs + mur d'accent + plinthes + sol (motif ET couleur) + plafond + canapé + rideaux + tapis + abat-jour + bois, choisie
par la graine du lieu, et un dressage qui range les objets dans l'espace LIBRE de la pièce (mêmes garde-fous que `variation` : `Keepout`, `_wall_runs`).

Sans la clé d'épisode `diversite`, aucun lieu livré ne change : les nouveaux lieux ont des noms nouveaux, et `finish()` rend le lieu tel quel."""
import copy
import functools
import math
import zlib
import numpy as np
from PIL import Image
from .r3d import B, C, M_FABRIC, M_WOODV, M_METAL, M_PLASTER, h2, vnoise2, fbm
from . import quartiers as Q
from .assets import text_tex

# ================================================================================================ palettes
PAL = {
    'terracotta':  dict(wall=(204, 108, 74), wall2=(240, 224, 196), trim=(246, 238, 224), floor=('parquet_chevron', (156, 100, 60), (124, 76, 46)), hard=('carreaux_ciment', (214, 120, 84), (246, 236, 216)),
                        sofa=(52, 116, 108), arm=(232, 170, 52), curt=(240, 226, 196), rug=((232, 170, 52), (52, 116, 108)), shade=(240, 170, 60), wood=(150, 94, 56), acc=(232, 170, 52)),
    'bleu_canard': dict(wall=(26, 108, 128), wall2=(238, 228, 208), trim=(244, 240, 230), floor=('lames_larges', (196, 150, 102), (178, 132, 88)), hard=('damier_couleur', (26, 108, 128), (240, 232, 214)),
                        sofa=(232, 150, 44), arm=(240, 226, 196), curt=(232, 150, 44), rug=((240, 226, 196), (26, 108, 128)), shade=(250, 190, 70), wood=(176, 128, 84), acc=(232, 150, 44)),
    'moutarde':    dict(wall=(226, 172, 48), wall2=(244, 236, 214), trim=(250, 246, 236), floor=('parquet_chevron', (190, 140, 92), (160, 112, 70)), hard=('carrelage_metro', (244, 240, 230), (140, 130, 118)),
                        sofa=(66, 80, 124), arm=(178, 70, 60), curt=(244, 236, 214), rug=((66, 80, 124), (244, 236, 214)), shade=(240, 120, 60), wood=(134, 90, 56), acc=(178, 70, 60)),
    'menthe':      dict(wall=(142, 212, 184), wall2=(250, 244, 232), trim=(252, 250, 244), floor=('lames_larges', (214, 184, 148), (196, 164, 128)), hard=('carreaux_ciment', (142, 212, 184), (252, 248, 238)),
                        sofa=(240, 120, 134), arm=(250, 214, 110), curt=(250, 244, 232), rug=((240, 120, 134), (250, 244, 232)), shade=(244, 150, 160), wood=(196, 156, 112), acc=(240, 120, 134)),
    'rose_poudre': dict(wall=(240, 174, 184), wall2=(252, 244, 236), trim=(252, 250, 246), floor=('parquet_chevron', (206, 168, 128), (186, 148, 110)), hard=('damier_couleur', (240, 174, 184), (252, 246, 240)),
                        sofa=(76, 108, 92), arm=(232, 196, 90), curt=(252, 244, 236), rug=((76, 108, 92), (240, 174, 184)), shade=(250, 206, 120), wood=(180, 140, 100), acc=(76, 108, 92)),
    'sauge':       dict(wall=(138, 170, 128), wall2=(244, 238, 220), trim=(248, 244, 232), floor=('lames_larges', (186, 142, 98), (166, 124, 84)), hard=('carrelage_metro', (244, 240, 228), (110, 130, 104)),
                        sofa=(214, 140, 90), arm=(244, 238, 220), curt=(244, 238, 220), rug=((214, 140, 90), (138, 170, 128)), shade=(240, 190, 110), wood=(150, 104, 66), acc=(214, 140, 90)),
    'bordeaux':    dict(wall=(128, 34, 58), wall2=(232, 214, 186), trim=(236, 220, 196), floor=('parquet_chevron', (120, 78, 52), (96, 60, 40)), hard=('damier_couleur', (128, 34, 58), (232, 218, 192)),
                        sofa=(32, 84, 72), arm=(214, 168, 70), curt=(214, 168, 70), rug=((32, 84, 72), (214, 168, 70)), shade=(240, 190, 90), wood=(100, 62, 40), acc=(214, 168, 70)),
    'nordique':    dict(wall=(238, 238, 232), wall2=(120, 156, 184), trim=(250, 250, 246), floor=('lames_larges', (226, 200, 164), (212, 184, 148)), hard=('beton_cire', (206, 208, 208), (206, 208, 208)),
                        sofa=(120, 156, 184), arm=(232, 176, 80), curt=(250, 250, 246), rug=((120, 156, 184), (240, 240, 236)), shade=(250, 230, 190), wood=(222, 190, 150), acc=(232, 176, 80)),
    'loft_brique': dict(wall=(176, 82, 60), wall2=(214, 208, 196), trim=(52, 52, 58), floor=('beton_cire', (150, 152, 156), (150, 152, 156)), hard=('beton_cire', (150, 152, 156), (150, 152, 156)),
                        sofa=(64, 74, 92), arm=(214, 138, 50), curt=(214, 208, 196), rug=((214, 138, 50), (64, 74, 92)), shade=(250, 200, 100), wood=(120, 84, 56), acc=(214, 138, 50)),
    'noir_neon':   dict(wall=(36, 32, 58), wall2=(255, 60, 170), trim=(80, 76, 118), floor=('moquette', (60, 50, 96), (60, 50, 96)), hard=('damier_couleur', (36, 32, 58), (80, 76, 118)),
                        sofa=(255, 60, 170), arm=(40, 220, 255), curt=(120, 80, 220), rug=((255, 60, 170), (40, 220, 255)), shade=(60, 230, 255), wood=(70, 56, 100), acc=(40, 220, 255)),
}
ORDER = tuple(PAL)
ALIASES = {'moutarde': 'moutarde', 'canard': 'bleu_canard', 'bleu': 'bleu_canard', 'rose': 'rose_poudre', 'vert': 'sauge', 'nordic': 'nordique', 'brique': 'loft_brique', 'neon': 'noir_neon'}


def palette(name, seed=0):
    if isinstance(name, str):
        k = ALIASES.get(name.strip().lower().replace(' ', '_'), name.strip().lower().replace(' ', '_'))
        if k in PAL: return k
    return ORDER[int(seed) % len(ORDER)]


# ================================================================================================ sols (motifs ET couleurs)
def _fl(kind, x, z, c1, c2):
    c1 = np.asarray(c1, np.float32); c2 = np.asarray(c2, np.float32); n = len(x)
    if kind == 'parquet_chevron':
        s = .2; u = x / s; v = z / (s * 4); cell = np.floor(v) % 2
        diag = ((u + (v % 1) * 2 * np.where(cell > 0, 1, -1)) % 1)
        t = (np.floor(u + (v % 1) * 2 * np.where(cell > 0, 1, -1)) + np.floor(v) * 3) % 2
        a = np.where((t > 0)[:, None], c1[None], c2[None]) * (.9 + .2 * vnoise2(x * 20, z * 20, 31))[:, None]
        a[(diag < .05) | ((v % 1) < .02)] *= .62
        return a, .1
    if kind == 'lames_larges':
        pl = np.floor(x / .24); seam = (x / .24) % 1 < .04
        a = np.where((h2(pl, np.floor(z / 1.6), 12) > .5)[:, None], c1[None], c2[None]) * (.92 + .16 * vnoise2(x * 3, z * 40, 13))[:, None]
        a[seam] *= .6
        return a, .1
    if kind == 'carreaux_ciment':
        s = .22; fx = (x / s) % 1; fz = (z / s) % 1; ix = np.floor(x / s); iz = np.floor(z / s)
        r = np.maximum(np.abs(fx - .5), np.abs(fz - .5)); d = np.hypot(fx - .5, fz - .5)
        pat = np.where(((ix + iz) % 2 == 0), (d < .32) | (r > .44), (np.abs(fx - .5) + np.abs(fz - .5) < .5) ^ (r > .44))
        a = np.where(pat[:, None], c1[None], c2[None]) * (.95 + .08 * vnoise2(x * 30, z * 30, 14))[:, None]
        a[(fx < .03) | (fz < .03)] *= .7
        return a, .14
    if kind == 'damier_couleur':
        s = .5; chk = (np.floor(x / s) + np.floor(z / s)) % 2
        a = np.where((chk > 0)[:, None], c1[None], c2[None]) * (.96 + .06 * vnoise2(x * 22, z * 22, 15))[:, None]
        a[((x / s) % 1 < .025) | ((z / s) % 1 < .025)] *= .75
        return a, .18
    if kind == 'carrelage_metro':
        s = .15; row = np.floor(z / s); off = (row % 2) * .5
        fx = (x / (s * 2) + off) % 1; fz = (z / s) % 1
        a = np.where(((fx < .04) | (fz < .06))[:, None], c2[None], c1[None]) * (.97 + .06 * h2(np.floor(x / (s * 2) + off), row, 16))[:, None]
        return a, .22
    if kind == 'terrazzo':
        sp = vnoise2(x * 14, z * 14, 17) > .72
        a = np.where(sp[:, None], c2[None], c1[None]) * (.96 + .08 * vnoise2(x * 40, z * 40, 18))[:, None]
        return a, .12
    if kind == 'moquette':
        a = c1[None] * (.9 + .2 * vnoise2(x * 60, z * 60, 19))[:, None]
        return a, 0.
    a = c1[None] * (.9 + .12 * fbm(x * 1.5, z * 1.5, 20, 2))[:, None]                    # beton_cire : béton lissé, une teinte, un reflet doux
    return a, .2


FLOOR_FNS = {k: _fl for k in ('parquet_chevron', 'lames_larges', 'carreaux_ciment', 'damier_couleur', 'carrelage_metro', 'terrazzo', 'moquette', 'beton_cire')}


def floor(kind, xm, zm, colr):
    """sol d'une pièce : `colr` = 3 flottants (une teinte) ou 6 (deux teintes du motif), 0..1"""
    c = list(colr)
    return _fl(kind, xm, zm, c[:3], c[3:6] if len(c) >= 6 else c[:3])


# ================================================================================================ détails (PS1)
def _rgb(c): return tuple(int(v) for v in c)


@functools.lru_cache(maxsize=128)
def _books_tex(seed, w):
    rng = np.random.default_rng(seed); n = max(6, int(w * 22)); a = np.zeros((6, n, 4), np.uint8)
    pal = ((200, 50, 50), (50, 90, 170), (240, 200, 60), (60, 140, 90), (240, 240, 232), (210, 110, 40), (110, 70, 150), (30, 30, 40), (60, 170, 180))
    for i in range(n):
        c = pal[int(rng.integers(0, len(pal)))]; h = int(rng.integers(4, 7)); a[6 - h:, i] = c + (255,); a[6 - h:6 - h + 1, i] = tuple(min(255, int(v * 1.25)) for v in c) + (255,)
    return a


def P_books(p, c):
    w = float(p.get('w', .7)); seed = int(p.get('seed', 1)); tx = _books_tex(seed, round(w, 2))
    return [B((-w / 2, 0, -.1), (w, .24, .2), (60, 50, 44), tex={'-z': tx}, texemis=0.), B((w / 2 - .02, 0, -.1), (.03, .26, .2), (60, 50, 44))]


def P_bookcase(p, c):
    col = _rgb(c or p.get('color') or (150, 94, 56)); w = float(p.get('w', .9)); h = float(p.get('h', 1.9)); seed = int(p.get('seed', 1)); rng = np.random.default_rng(seed)
    out = [B((-w / 2, 0, -.16), (w, h, .04), _sh(col, .8)), B((-w / 2, 0, -.16), (.05, h, .32), col, mat=M_WOODV), B((w / 2 - .05, 0, -.16), (.05, h, .32), col, mat=M_WOODV), B((-w / 2, h - .05, -.16), (w, .05, .32), col, mat=M_WOODV)]
    n = int(p.get('shelves', 5)); gap = (h - .05) / n
    for i in range(n):
        y = i * gap
        out.append(B((-w / 2, y, -.16), (w, .04, .32), col, mat=M_WOODV))
        k = int(rng.integers(0, 4))
        if k < 3: out.append(B((-w / 2 + .05, y + .04, -.28), (w - .1, min(.3, gap - .08), .2), (60, 50, 44), tex={'-z': _books_tex(seed * 10 + i, round(w - .1, 2))}))
        elif k == 3:
            pc = ((240, 200, 60), (60, 140, 90), (200, 50, 50), (60, 150, 190))[int(rng.integers(0, 4))]; x = float(rng.uniform(-w / 3, w / 3))
            out += [B((x - .06, y + .04, -.2), (.12, .26, .12), pc), B((x - .03, y + .3, -.17), (.06, .08, .06), (50, 140, 70))]
    return out


def _sh(c, f): return tuple(int(max(0, min(255, v * f))) for v in c)


def P_plant(p, c):
    k = p.get('kind', 'monstera'); pot = _rgb(p.get('pot') or (176, 92, 60)); g1 = (44, 140, 66); g2 = (70, 170, 90); s = float(p.get('size', 1.))
    if k == 'cactus':
        return [C((0, .16 * s, 0), (.3 * s, .32 * s, .3 * s), pot), C((0, .65 * s, 0), (.2 * s, .75 * s, .2 * s), (70, 150, 84)), C((.16 * s, .75 * s, 0), (.1 * s, .3 * s, .1 * s), (70, 150, 84)), C((-.15 * s, .62 * s, 0), (.1 * s, .24 * s, .1 * s), (70, 150, 84)), C((0, 1.06 * s, 0), (.08 * s, .06 * s, .08 * s), (240, 90, 140))]
    if k == 'palm':
        out = [C((0, .22 * s, 0), (.36 * s, .44 * s, .36 * s), pot), C((0, .9 * s, 0), (.08 * s, 1.0 * s, .08 * s), (110, 84, 56))]
        for a in range(4): ang = a * math.pi / 2 + .4; out.append(B((math.cos(ang) * .3 * s - .22 * s, 1.35 * s - .1 * a % .2, math.sin(ang) * .3 * s - .06), (.44 * s, .07, .12), g1 if a % 2 else g2, mat=M_FABRIC))
        return out
    if k == 'ficus':
        return [C((0, .2 * s, 0), (.34 * s, .4 * s, .34 * s), pot), C((0, .7 * s, 0), (.06 * s, .6 * s, .06 * s), (110, 84, 56)), C((0, 1.25 * s, 0), (.6 * s, .6 * s, .6 * s), g1, mat=M_FABRIC), C((.12 * s, 1.5 * s, .05), (.36 * s, .3 * s, .36 * s), g2, mat=M_FABRIC)]
    return [C((0, .18 * s, 0), (.36 * s, .36 * s, .36 * s), pot), C((0, .6 * s, 0), (.5 * s, .44 * s, .5 * s), g1, mat=M_FABRIC), C((.1 * s, .9 * s, .06), (.4 * s, .3 * s, .4 * s), g2, mat=M_FABRIC), C((-.12 * s, .8 * s, -.08), (.3 * s, .3 * s, .3 * s), g1, mat=M_FABRIC)]


@functools.lru_cache(maxsize=64)
def _art_tex(kind, c1, c2, c3, seed):
    a = np.zeros((20, 16, 4), np.uint8); a[:, :] = c3 + (255,); rng = np.random.default_rng(seed)
    if kind == 'soleil':
        a[:11, :] = c2 + (255,); yy, xx = np.mgrid[0:20, 0:16]; a[(xx - 8) ** 2 + (yy - 6) ** 2 < 14] = c1 + (255,); a[12:, :] = _sh(c2, .6) + (255,)
        for k in range(0, 16, 3): a[11:14, k:k + 2] = _sh(c3, 1.2) + (255,)
    elif kind == 'geo':
        for i in range(6):
            x, y = int(rng.integers(0, 12)), int(rng.integers(0, 16)); a[y:y + 5, x:x + 5] = (c1, c2, c3, _sh(c1, .6))[i % 4] + (255,)
    elif kind == 'rayures':
        for i in range(0, 16, 4): a[:, i:i + 2] = c1 + (255,); a[:, i + 2:i + 4] = c2 + (255,)
        a[6:14, 4:12] = c3 + (255,)
    else:
        a[:] = c2 + (255,); a[4:16, 3:13] = c1 + (255,); a[6:9, 5:8] = c3 + (255,); a[10:14, 7:12] = _sh(c3, .5) + (255,)
    return a


def P_frame(p, c):
    w = float(p.get('w', .7)); h = float(p.get('h', .85)); fr = _rgb(p.get('frame') or (40, 30, 24)); col = [tuple(x) for x in (p.get('cols') or [(232, 170, 52), (52, 116, 108), (240, 232, 214)])]
    tx = _art_tex(p.get('art', 'soleil'), col[0], col[1], col[2 % len(col)], int(p.get('seed', 1)))
    return [B((-w / 2, 0, -.03), (w, h, .03), fr), B((-w / 2 + .05, .05, -.045), (w - .1, h - .1, .015), (240, 236, 224), tex={'-z': tx})]


@functools.lru_cache(maxsize=32)
def _fold_tex(c):
    a = np.zeros((4, 12, 4), np.uint8)
    for i in range(12): a[:, i] = _sh(c, .78 + .3 * (i % 3 == 1)) + (255,)
    return a


def P_curtain(p, c):
    w = float(p.get('w', 1.8)); h = float(p.get('h', 2.3)); col = _rgb(p.get('color') or (240, 226, 196)); pw = max(.4, w * .3); tx = _fold_tex(col)
    return [B((-w / 2 - .06, h, -.12), (w + .12, .04, .04), (60, 50, 44)), B((-w / 2, .08, -.12), (pw, h - .08, .08), col, mat=M_FABRIC, tex={'-z': tx}), B((w / 2 - pw, .08, -.12), (pw, h - .08, .08), col, mat=M_FABRIC, tex={'-z': tx})]


@functools.lru_cache(maxsize=64)
def _rug_tex(c1, c2, kind):
    a = np.zeros((12, 18, 4), np.uint8); a[:, :] = c1 + (255,)
    a[1:11, 1:17] = c2 + (255,); a[2:10, 2:16] = c1 + (255,)
    if kind == 'rayures':
        for k in range(3, 15, 3): a[2:10, k:k + 1] = c2 + (255,)
    else: a[4:8, 5:13] = c2 + (255,); a[5:7, 7:11] = c1 + (255,)
    return a


def P_rug(p, c):
    w = float(p.get('w', 2.0)); d = float(p.get('d', 1.4)); c1, c2 = (p.get('cols') or ((232, 170, 52), (52, 116, 108)))
    return [B((-w / 2, 0, -d / 2), (w, .014, d), _rgb(c1), mat=M_FABRIC, cast=False, tex={'+y': _rug_tex(_rgb(c1), _rgb(c2), p.get('pattern', 'bordure'))})]


def P_lamp(p, c):
    sh = _rgb(p.get('shade') or (240, 170, 60)); k = p.get('kind', 'floor'); s = float(p.get('size', 1.))
    if k == 'table':
        return [C((0, .04, 0), (.2, .08, .2), (60, 50, 44)), C((0, .2, 0), (.04, .3, .04), (60, 50, 44)), C((0, .42, 0), (.26, .2, .26), sh, emis=1.0)]
    return [C((0, .03, 0), (.3, .06, .3), (50, 46, 44)), C((0, .78, 0), (.04, 1.5, .04), (50, 46, 44)), C((0, 1.62, 0), (.4, .3, .4), sh, emis=1.1), C((0, 1.78, 0), (.3, .04, .3), _sh(sh, .8), emis=.5)]


def P_tableware(p, c):
    k = p.get('kind', 'dinner'); seed = int(p.get('seed', 1)); rng = np.random.default_rng(seed); a = tuple(p.get('acc') or (232, 170, 52))
    if k == 'fruit':
        return [C((0, .05, 0), (.34, .1, .34), (240, 236, 224)), C((-.07, .13, 0), (.1, .1, .1), (230, 60, 50)), C((.07, .13, .03), (.1, .1, .1), (250, 200, 50)), C((0, .17, -.05), (.1, .1, .1), (110, 190, 70))]
    if k == 'coffee':
        return [C((0, .09, 0), (.12, .18, .12), a), C((.22, .04, .05), (.1, .08, .1), (240, 236, 224)), C((-.22, .04, -.05), (.1, .08, .1), (240, 236, 224)), C((0, .01, .22), (.3, .02, .2), (240, 236, 224))]
    return [C((-.28, .01, 0), (.26, .02, .26), (240, 236, 224)), C((.28, .01, 0), (.26, .02, .26), (240, 236, 224)), C((-.28, .01, 0), (.14, .025, .14), a), C((.28, .01, 0), (.14, .025, .14), a), C((-.5, .06, 0), (.08, .12, .08), (240, 236, 224)), C((0, .12, .12), (.07, .24, .07), (60, 140, 90))]


def P_cushions(p, c):
    cols = [tuple(x) for x in (p.get('cols') or [(232, 170, 52), (52, 116, 108), (240, 226, 196)])]; w = float(p.get('w', 1.6)); n = max(2, int(w / .55)); out = []
    for i in range(n): out.append(B((-w / 2 + .1 + i * (w - .5) / max(1, n - 1), 0, -.12), (.4, .36, .12 + .02 * (i % 2)), cols[i % len(cols)], mat=M_FABRIC))
    return out


def P_vase(p, c):
    col = _rgb(p.get('color') or (60, 140, 190)); fl = [(236, 60, 90), (250, 210, 50), (250, 250, 250), (200, 90, 230)]
    return [C((0, .13, 0), (.14, .26, .14), col), C((0, .3, 0), (.06, .12, .06), (50, 140, 70))] + [C((.07 * (i - 1.5), .38 + .03 * (i % 2), .03 * (i - 1)), (.09, .09, .09), fl[i % 4]) for i in range(4)]


def P_stool(p, c):
    col = _rgb(p.get('color') or (232, 170, 52)); return [C((0, .66, 0), (.34, .06, .34), col), C((0, .33, 0), (.06, .66, .06), (60, 60, 66), mat=M_METAL), C((0, .03, 0), (.3, .06, .3), (60, 60, 66), mat=M_METAL), C((0, .2, 0), (.22, .02, .22), (60, 60, 66))]


def P_menu(p, c):
    w = float(p.get('w', .9)); h = float(p.get('h', 1.2)); t = [str(x) for x in (p.get('text') or ['MENU', 'CAFÉ 2', 'THÉ 3', 'GÂTEAU 4'])][:5]
    tx = text_tex(t, (72, 96), (250, 244, 226), (34, 44, 40, 255), 8, 6)
    return [B((-w / 2, 0, -.03), (w, h, .03), (130, 90, 56)), B((-w / 2 + .05, .05, -.045), (w - .1, h - .1, .015), (34, 44, 40), tex={'-z': tx})]


def P_cakecase(p, c):
    cols = ((236, 90, 120), (250, 214, 110), (130, 80, 56), (240, 240, 232), (110, 190, 110)); out = [B((-.6, 0, -.3), (1.2, .5, .6), (210, 210, 206), mat=M_METAL), B((-.6, .5, -.3), (1.2, .5, .6), (150, 190, 214), refl=.3, emis=.3)]
    for i in range(5): out.append(C((-.46 + i * .23, .62, 0), (.16, .12, .16), cols[i % 5]))
    out.append(C((0, .96, 0), (1.1, .03, .5), (240, 240, 236)))
    return out


def P_pendants(p, c):
    cols = [tuple(x) for x in (p.get('cols') or [(240, 170, 60), (240, 230, 200), (232, 90, 70)])]; y = float(p.get('y', 2.6)); out = []
    for i, dx in enumerate((-.4, 0., .4)):
        hh = .5 + .25 * (i % 2); out += [B((dx - .01, y - hh, 0), (.02, hh, .02), (40, 40, 44)), C((dx, y - hh - .1, 0), (.28, .2, .28), cols[i % len(cols)], emis=1.3)]
    return out


@functools.lru_cache(maxsize=32)
def _goods_tex(seed, rows, cols_):
    rng = np.random.default_rng(seed); a = np.zeros((rows * 6, cols_ * 5, 4), np.uint8); pal = ((230, 60, 50), (250, 200, 50), (80, 170, 80), (70, 130, 220), (240, 240, 232), (240, 130, 40), (180, 90, 200))
    a[:, :] = (70, 60, 56, 255)
    for r in range(rows):
        a[r * 6 + 5, :] = (40, 34, 32, 255)
        for c_ in range(cols_):
            col = pal[int(rng.integers(0, len(pal)))]; h = int(rng.integers(3, 5)); a[r * 6 + 5 - h:r * 6 + 5, c_ * 5:c_ * 5 + 4] = col + (255,)
    return a


def P_shelving(p, c):
    w = float(p.get('w', 1.4)); h = float(p.get('h', 1.7)); seed = int(p.get('seed', 1)); rows = 3
    return [B((-w / 2, 0, -.2), (.05, h, .4), (150, 150, 156), mat=M_METAL), B((w / 2 - .05, 0, -.2), (.05, h, .4), (150, 150, 156), mat=M_METAL), B((-w / 2, 0, -.2), (w, h, .05), (110, 100, 94)),
            B((-w / 2 + .05, .2, -.22), (w - .1, h - .3, .02), (60, 50, 44), tex={'-z': _goods_tex(seed, rows, int(w * 9))}), B((-w / 2, h, -.2), (w, .05, .4), (150, 150, 156), mat=M_METAL)]


def P_crates(p, c):
    cols = ((230, 60, 50), (250, 200, 50), (80, 170, 80), (240, 130, 40)); out = []
    for i in range(3):
        x = -.7 + i * .7; out += [B((x - .3, 0, -.25), (.6, .28, .5), (150, 106, 66), mat=M_WOODV), B((x - .26, .28, -.21), (.52, .08, .42), cols[(i + int(p.get('seed', 0))) % 4], mat=M_FABRIC)]
    return out


def P_mannequin(p, c):
    col = _rgb(p.get('color') or (232, 90, 120)); return [C((0, .03, 0), (.4, .06, .4), (50, 50, 56)), C((0, .5, 0), (.04, .9, .04), (50, 50, 56)), C((0, 1.18, 0), (.36, .5, .2), col, mat=M_FABRIC), C((0, 1.55, 0), (.14, .16, .14), (232, 214, 190)), C((0, .85, 0), (.4, .36, .22), _sh(col, .7), mat=M_FABRIC)]


@functools.lru_cache(maxsize=32)
def _mail_tex(seed, cols_):
    rng = np.random.default_rng(seed); pal = ((230, 60, 50), (250, 200, 50), (80, 170, 80), (70, 130, 220), (240, 130, 40), (180, 90, 200), (240, 240, 232), (60, 180, 180))
    a = np.zeros((3 * 8, cols_ * 8, 4), np.uint8); a[:, :] = (40, 40, 46, 255)
    for r in range(3):
        for c_ in range(cols_): a[r * 8 + 1:r * 8 + 7, c_ * 8 + 1:c_ * 8 + 7] = pal[int(rng.integers(0, len(pal)))] + (255,); a[r * 8 + 3:r * 8 + 4, c_ * 8 + 2:c_ * 8 + 6] = (30, 30, 36, 255)
    return a


def P_mailboxes(p, c):
    cols_ = int(p.get('cols', 4)); w = cols_ * .34
    return [B((-w / 2, 0, -.14), (w, .9, .14), (60, 60, 68), tex={'-z': _mail_tex(int(p.get('seed', 1)), cols_)}, mat=M_METAL)]


def P_elevator(p, c):
    col = _rgb(p.get('color') or (176, 180, 188)); return [B((-.8, 0, -.12), (1.6, 2.4, .12), (50, 50, 56)), B((-.55, 0, -.2), (.55, 2.15, .08), col, mat=M_METAL), B((0, 0, -.2), (.55, 2.15, .08), col, mat=M_METAL),
            B((-.3, 2.2, -.2), (.6, .14, .06), (20, 10, 6), emis=1.2), B((.7, 1.0, -.15), (.1, .2, .04), (255, 190, 70), emis=1.5)]


def P_stairs(p, c):
    n = int(p.get('n', 10)); w = float(p.get('w', 1.2)); rise = float(p.get('rise', .18)); run = float(p.get('run', .28)); col = _rgb(p.get('color') or (196, 150, 110)); rail = _rgb(p.get('rail') or (60, 60, 66)); out = []
    for i in range(n): out.append(B((-w / 2, 0, -(n - i) * run), (w, (i + 1) * rise, run), col if i % 2 == 0 else _sh(col, .92)))
    out += [B((w / 2, 0, -n * run), (.05, n * rise + .9, .05), rail), B((w / 2, .9, -n * run), (.05, .05, n * run), rail), B((-w / 2 - .05, .9, -n * run), (.05, .05, n * run), rail)]
    return out


def P_doormat(p, c):
    col = _rgb(p.get('color') or (52, 116, 108)); return [B((-.5, 0, -.3), (1.0, .02, .6), col, mat=M_FABRIC, cast=False), B((-.42, .02, -.24), (.84, .004, .48), _sh(col, 1.3), cast=False)]


NEW_PROPS = {'qi_books': P_books, 'qi_bookcase': P_bookcase, 'qi_plant': P_plant, 'qi_frame': P_frame, 'qi_curtain': P_curtain, 'qi_rug': P_rug, 'qi_lamp': P_lamp, 'qi_tableware': P_tableware,
             'qi_cushions': P_cushions, 'qi_vase': P_vase, 'qi_stool': P_stool, 'qi_menu': P_menu, 'qi_cakecase': P_cakecase, 'qi_pendants': P_pendants, 'qi_shelving': P_shelving,
             'qi_crates': P_crates, 'qi_mannequin': P_mannequin, 'qi_mailboxes': P_mailboxes, 'qi_elevator': P_elevator, 'qi_stairs': P_stairs, 'qi_doormat': P_doormat}
NEW_LIGHTS = {'qi_lamp': [((0, 1.5, 0), (1, .84, .58), .8, 3.0, False)], 'qi_pendants': [((0, 2.0, 0), (1, .84, .6), .8, 3.2, False)]}
