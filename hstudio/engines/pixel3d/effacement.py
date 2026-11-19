"""Effet de plan `effacement` (14 novembre 2026, série « Le Phare qui efface ») : un élément du lieu s'efface DANS le plan, sans débris ni explosion.

    {"type": "effacement", "target": "cabane", "at": 1.2, "dur": .6, "garder": "marches"}
    {"type": "effacement", "target": "boulangerie", "at_abs": 31.4, "dur": .8}

  target   un groupe du lieu (`group` des blocs / décors : `cabane`, `boulangerie`, `maison0`... dans `phare_foret`) ; les sous-groupes
           `<target>.<nom>` partent avec lui, SAUF ceux de `garder`
  at       secondes dans le plan (ou `at_abs` : secondes dans le film) ; avant, l'élément est intact
  dur      durée de l'effacement (défaut 0,6 s) : un front d'effacement descend du haut vers le bas ; au-dessus du front, l'élément n'existe
           plus ; juste sous le front, une bande de 0,7 m se défait en pixels (tramage du moteur) ; quelques éclats blancs et froids
           s'allument sur le front puis s'éteignent ; une lueur froide passe ; aucun débris
  garder   'marches' (défaut) | liste : sous-groupes qui RESTENT (`<target>.marches` : les trois marches ; on écrit le suffixe ou le nom complet)
  contour  True (défaut) : si le lieu sait dessiner le contour de l'élément effacé (méthode `outline` : le mur invisible de la boulangerie),
           le contour apparaît à mesure que l'élément disparaît, identique à la variante `effacee` du lieu (le plan suivant raccorde)
  lueur    1.0 : force de la lueur froide du front ; eclats : nombre d'éclats (défaut 14) ; flash : petit flash de l'image (défaut 0)
  son      {"name": ..., "gain": ..., "dur": ...} : facultatif (aucun son par défaut : la mise en scène écrit ses bruitages)
Les lumières du lieu attachées à l'élément (lampe de porche, vitrine...) baissent avec lui si le lieu les déclare (`PhareSet.light_groups`).
Après la fin, l'élément reste effacé jusqu'à la fin du plan ; le plan suivant prend la variante `effacee` du lieu.

PS1 : exact (les boîtes fixes du groupe sont retirées image par image). VOXEL : le décor fixe est peint une fois pour le plan, l'élément n'y disparaît
donc PAS dans le plan (seuls les éclats et le contour sont dessinés) : en VOXEL, couper sur la variante `effacee` (avec un flash)."""
import copy
import math
import numpy as np
from .effects import effect, smooth
from .r3d import Box, C


def _groups(fx, target, keep):
    groups = getattr(fx.st, 'groups', {}) or {}
    keep = [keep] if isinstance(keep, str) else list(keep if keep is not None else ['marches'])
    keepset = {k if k.startswith(target + '.') else f'{target}.{k}' for k in keep} | {f'{target}.contour'}
    return [g for g in groups if (g == target or g.startswith(target + '.')) and g not in keepset]


def _slice(b, y0, y1, dissolve=0.):
    """the part of a static box between heights y0 and y1 (None if empty), optionally dissolving in pixels"""
    lo, hi = float(b.lo[1]), float(b.hi[1])
    a, c = max(lo, y0), min(hi, y1)
    if c - a < .004: return None
    n = copy.copy(b); n.lo = np.array(b.lo, np.float32); n.hi = np.array(b.hi, np.float32)
    n.lo[1] = a; n.hi[1] = c
    if b.tex and (a > lo + 1e-4 or c < hi - 1e-4):                     # crop the texture rows to the kept part
        H = max(hi - lo, 1e-6); tex = {}
        for k, arr in b.tex.items():
            if k in (2, 3): continue
            r0 = int(round(arr.shape[0] * (1 - (c - lo) / H))); r1 = int(round(arr.shape[0] * (1 - (a - lo) / H)))
            if r1 - r0 >= 1: tex[k] = arr[max(0, r0):min(arr.shape[0], r1)]
        n.tex = tex
    if dissolve > 0: n.dissolve = max(float(getattr(b, 'dissolve', 0.)), float(dissolve)); n.cast = False
    return n


def _sounds(o):
    s = o.get('son')
    if not isinstance(s, dict) or not s.get('name'): return []
    return [(float(o.get('at', 0.)), s['name'], float(s.get('gain', .8)), s.get('dur'))]


@effect('effacement', sounds=_sounds)
def effacement(fx, o):
    target = o.get('target')
    if not target: return [], []
    dt = fx.since(o)
    if dt < 0: return [], []                                          # not yet: the element is intact
    gids = _groups(fx, target, o.get('garder'))
    boxes = [b for g in gids for b in fx.group_boxes(g)]
    dur = max(.05, float(o.get('dur', .6))); p = min(1., dt / dur)
    for g in gids: fx.hide(g)
    fade = 1. - smooth(min(1., p * 1.25))
    lg = getattr(fx.st, 'light_groups', None)
    if lg is not None:                                                 # the element's own lights go down with it (read by the set's lights())
        cur = getattr(fx.st, '_efface_frame', None)
        f = dict(cur[1]) if cur and cur[0] == fx.g else {}
        for g in gids: f[g] = min(f.get(g, 1.), fade)
        fx.st._efface_frame = (fx.g, f)
    out = []; L = []
    outline = fx.st.outline(target) if (o.get('contour', True) and hasattr(fx.st, 'outline')) else []
    if outline:
        k = smooth(min(1., p * 1.4))
        for b in outline:
            n = copy.copy(b); n.emis = float(b.emis) * k; n.col = b.col * (.35 + .65 * k)
            if k > .02: out.append(n)
    if not boxes or p >= 1.: return out, L
    lo = np.min([b.lo for b in boxes], 0); hi = np.max([b.hi for b in boxes], 0)
    band = .7; ybot, ytop = float(lo[1]), float(hi[1])
    yf = ytop + band - (ytop - ybot + 2 * band) * smooth(p)          # the erasing front, from above the top to below the bottom
    for b in boxes:
        for (y0, y1, d) in ((-1e9, yf - band, 0.), (yf - band, yf - band * .5, .38), (yf - band * .5, yf, .78)):
            n = _slice(b, y0, y1, d)
            if n is not None: out.append(n)
    # a few cold white sparks on the front, flickering out ; a cold glow passing down
    cx, cz = float(lo[0] + hi[0]) / 2, float(lo[2] + hi[2]) / 2; sx, sz = float(hi[0] - lo[0]), float(hi[2] - lo[2])
    rng = np.random.default_rng(int(o.get('seed', 11)) * 7919 + int(dt * 30))
    for j in range(int(o.get('eclats', 14))):
        side = j % 4
        u_ = float(rng.uniform(-.5, .5))
        x = cx + (u_ * sx if side < 2 else (-.5 if side == 2 else .5) * sx)
        z = cz + ((-.5 if side == 0 else .5) * sz if side < 2 else u_ * sz)
        y = yf - float(rng.uniform(0., band)) + .35 * p
        if ybot - .05 <= y <= ytop + .05 and rng.random() > .25:
            out.append(C((x, y, z), (.07, .07, .07), (232, 242, 255), emis=3.2 * (1. - p) + .4, cast=False))
    yl = min(ytop, max(ybot + .3, yf))
    L.append(((cx, yl, cz), (.78, .86, 1.0), 2.6 * float(o.get('lueur', 1.)) * math.sin(math.pi * p), max(sx, sz) * .9 + 1.))
    if o.get('flash'): fx.flash(float(o['flash']) * math.sin(math.pi * p))
    return out, L
