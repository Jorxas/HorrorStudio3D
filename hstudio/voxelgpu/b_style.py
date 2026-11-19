"""Le style du studio, mesuré : de quoi noter un élément (recette `craft`, `bset`, modèle) par rapport à NOS décors de PIXEL 3D convertis.

Référence : `style_reference.json` (fabriquée par `tools/b_style_measure.py` sur les 217 décors) : centiles de chaque indicateur et palette réelle. Ce module ne MODIFIE jamais un
élément : il mesure et il dit ce qui s'écarte (`check` -> alertes lisibles). Les règles en clair sont dans `docs/STYLE_GUIDE_STUDIO.md`.

Ce que la mesure a montré (voir le guide) : nos décors sont faits de PEU de boîtes franches (médiane 5, 95e centile 17), de 2 à 6 couleurs, de pièces fines (pieds, cadres, montants),
presque aucun petit cube ; le grain est ajouté par le peintre, pas dans les données. Les figurines importées font l'inverse : des centaines de petits cubes, des dizaines de couleurs.
"""
import colorsys, json
from pathlib import Path
import numpy as np

PX = 1. / 16.
REF = Path(__file__).with_name('style_reference.json')
_REF = None
KIND_SIZE = {'decor': (.15, 9.), 'item': (.08, 1.6), 'creature': (.2, 4.5), 'structure': (2., 24.)}      # plage plausible de la plus grande dimension (m), par genre
KIND_BOXES = {'decor': 3, 'item': 3, 'creature': 6, 'structure': 12}                                       # facteur de tolérance sur le 95e centile du nombre de boîtes


def reference():
    global _REF
    if _REF is None: _REF = json.loads(REF.read_text(encoding='utf-8'))
    return _REF


def rgb(c): return np.array([(c >> 16) & 255, (c >> 8) & 255, c & 255], float) / 255.


def lab(c):
    """(r, g, b) 0-255 -> CIE Lab"""
    c = np.array(c, float) / 255.; c = np.where(c > .04045, ((c + .055) / 1.055) ** 2.4, c / 12.92)
    x, y, z = (np.array([[.4124, .3576, .1805], [.2126, .7152, .0722], [.0193, .1192, .9505]]) @ c) / np.array([.9505, 1., 1.089])
    f = lambda t: np.where(t > .008856, np.cbrt(t), 7.787 * t + 16 / 116.); fx, fy, fz = f(x), f(y), f(z)
    return np.array([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)])


def metrics(boxes):
    """boîtes VOXEL ({x,y,z,w,h,d,color[,emis]}, en mètres) -> indicateurs (définis dans tools/b_style_measure.py) ; None si aucune boîte"""
    boxes = [b for b in boxes if b['w'] > 0 and b['h'] > 0 and b['d'] > 0]
    if not boxes: return None
    cols = np.array([rgb(b['color']) for b in boxes]); vol = np.array([b['w'] * b['h'] * b['d'] for b in boxes]); w = vol / vol.sum()
    hsv = np.array([colorsys.rgb_to_hsv(*c) for c in cols]); S, V = hsv[:, 1], hsv[:, 2]
    mean = lambda x: float((x * w).sum())
    lo = np.array([min(b[k] - b[s] / 2 for b in boxes) for k, s in (('x', 'w'), ('y', 'h'), ('z', 'd'))]); hi = np.array([max(b[k] + b[s] / 2 for b in boxes) for k, s in (('x', 'w'), ('y', 'h'), ('z', 'd'))])
    ext = hi - lo; bbox_vol = max(float(np.prod(np.maximum(ext, .05))), 1e-3)
    mins = np.array([min(b['w'], b['h'], b['d']) / PX for b in boxes]); maxs = np.array([max(b['w'], b['h'], b['d']) / PX for b in boxes])
    return dict(S_mean=mean(S), V_mean=mean(V), V_sd=float(np.sqrt((((V - mean(V)) ** 2) * w).sum())), pure_white=float(w[(V > .97) & (S < .06)].sum()), pure_black=float(w[V < .06].sum()),
                sat_high=float(w[S > .7].sum()), n_colors=len({tuple(np.round(c * 31).astype(int)) for c in cols}), n_boxes=len(boxes), density=len(boxes) / bbox_vol,
                min_side_med=float(np.median(mins)), thin_share=float((mins < 2).mean()), chunk_share=float(w[mins >= 8].sum()),
                micro_cube_share=float(((maxs <= 4.5) & (maxs / np.maximum(mins, 1e-6) < 1.6)).mean()), height_m=float(ext[1]), extent_m=float(ext.max()))


def palette_gap(boxes, pal=None):
    """part du volume dont la couleur est à plus de 16 (ΔE) de toutes nos couleurs ; + les pires couleurs avec la couleur de `PAL` la plus proche -> (part, [(hex, ΔE, nom PAL)])"""
    ref = reference()['ref_colors']; RL = np.array([lab(c[:3]) for c in ref]); RW = np.array([c[3] for c in ref])
    pal = pal or {}; PL = {n: lab(c) for n, c in pal.items()}
    vol = np.array([b['w'] * b['h'] * b['d'] for b in boxes if not b.get('emis')]); bx = [b for b in boxes if not b.get('emis')]
    if not len(bx): return 0., []
    vol = vol / vol.sum(); far = 0.; worst = {}
    for b, v in zip(bx, vol):
        c = ((b['color'] >> 16) & 255, (b['color'] >> 8) & 255, b['color'] & 255); d = float(np.min(np.linalg.norm(RL - lab(c), axis=1)))
        if d > 16.: far += v; worst[c] = (worst.get(c, (0., 0.))[0] + v, d)
    top = sorted(worst.items(), key=lambda kv: -kv[1][0])[:3]; out = []
    for c, (v, d) in top:
        near = min(PL.items(), key=lambda kv: np.linalg.norm(kv[1] - lab(c)))[0] if PL else ''
        out.append(('#%02x%02x%02x' % c, round(d, 1), near))
    return float(far), out


def check(boxes, kind='decor', pal=None):
    """-> dict(score 0-100, alerts [(niveau 'attention'|'à revoir', texte)], metrics). Ne modifie rien."""
    m = metrics(boxes)
    if m is None: return dict(score=0, alerts=[('à revoir', 'aucune boîte')], metrics=None)
    R = reference()['percentiles']; A = []
    def add(level, txt): A.append((level, txt))
    p = lambda k, q: R[k][q]
    big = m['extent_m'] >= .6          # un petit objet (jouet, cadeau, caillou) est naturellement fait de petites boîtes : l'effet Lego ne se juge que sur ce qui est grand
    if big and m['micro_cube_share'] > .65: add('à revoir', f"effet Lego : {m['micro_cube_share']:.0%} des boîtes sont de petits cubes (nos décors : au plus {p('micro_cube_share', 'p95'):.0%}). Fusionner en pans plus grands, en pièces allongées, en volumes simples.")
    elif big and m['micro_cube_share'] > p('micro_cube_share', 'p95') + .02: add('attention', f"beaucoup de petits cubes ({m['micro_cube_share']:.0%}, nos décors : au plus {p('micro_cube_share', 'p95'):.0%}) : risque d'effet Lego/pixel.")
    lim = p('n_boxes', 'p95') * KIND_BOXES.get(kind, 3)
    if m['n_boxes'] > lim * 4: add('à revoir', f"trop de boîtes : {m['n_boxes']} (nos décors : 17 au plus au 95e centile ; limite de ce genre ≈ {lim:.0f}). Simplifier : le grain vient du peintre, pas des données.")
    elif m['n_boxes'] > lim: add('attention', f"beaucoup de boîtes : {m['n_boxes']} (limite de ce genre ≈ {lim:.0f}).")
    if m['n_colors'] > p('n_colors', 'p95') * 4: add('à revoir', f"trop de couleurs : {m['n_colors']} (nos décors : 6 au plus au 95e centile). Garder 2 à 6 teintes ; la variation vient du grain du peintre, pas de `jitter` par boîte.")
    elif m['n_colors'] > p('n_colors', 'p95') * 2: add('attention', f"beaucoup de couleurs : {m['n_colors']} (nos décors : 6 au 95e centile).")
    if m['S_mean'] > p('S_mean', 'p95') + .05: add('attention', f"couleurs trop vives : saturation moyenne {m['S_mean']:.2f} (nos décors : {p('S_mean', 'p50'):.2f} médiane, {p('S_mean', 'p95'):.2f} au 95e). Désaturer vers la palette `PAL`.")
    if m['V_mean'] > p('V_mean', 'p95') + .03: add('attention', f"trop clair : valeur moyenne {m['V_mean']:.2f} (nos décors : {p('V_mean', 'p95'):.2f} au 95e).")
    if m['pure_white'] > p('pure_white', 'p95') + .05: add('attention', f"blancs purs sur {m['pure_white']:.0%} du volume (nos décors : au plus {p('pure_white', 'p95'):.0%}) : utiliser `bone`, `white` ou `snow` de `PAL`, jamais (255,255,255).")
    if m['pure_black'] > .02: add('attention', f"noirs purs sur {m['pure_black']:.0%} du volume (nos décors : ~0 %) : utiliser `coal` ou `black` de `PAL`.")
    if m['n_colors'] == 1 and m['extent_m'] > 1.2 and m['n_boxes'] >= 4: add('attention', 'monotone : une seule teinte sur un grand élément ; ajouter une ou deux teintes (ombre, usure, détail).')
    lo_, hi_ = KIND_SIZE.get(kind, KIND_SIZE['decor'])
    if not lo_ <= m['extent_m'] <= hi_: add('attention', f"taille {m['extent_m']:.2f} m hors de la plage plausible d'un « {kind} » ({lo_}–{hi_} m).")
    if kind in ('creature', 'structure') and m['n_boxes'] < 4 and m['extent_m'] > 1.0: add('à revoir', f"détail insuffisant : {m['n_boxes']} boîtes pour {m['extent_m']:.1f} m (une tête, des pattes, un toit manquent).")
    if m['thin_share'] == 0 and m['n_boxes'] > 10 and kind in ('decor', 'item', 'creature'): add('attention', 'aucune pièce fine (< 2 voxels) : nos décors en ont presque toujours (pieds, montants, cadres, queues).')
    gap, worst = palette_gap(boxes, pal)
    if gap > .25: add('attention', f"{gap:.0%} du volume hors de notre palette (ΔE > 16) : " + ', '.join(f"{c} (écart {d}" + (f", proche de PAL['{n}']" if n else '') + ')' for c, d, n in worst))
    score = max(0, 100 - sum(20 if lv == 'à revoir' else 8 for lv, _ in A))
    return dict(score=score, alerts=A, metrics=m)
