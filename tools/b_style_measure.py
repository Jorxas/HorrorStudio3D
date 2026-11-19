"""python tools/b_style_measure.py [--out hstudio/voxelgpu/style_reference.json] [--md docs/STYLE_GUIDE_STUDIO_MESURES.md]

Mesure NOTRE style : les 217 décors de PIXEL 3D convertis en boîtes VOXEL (`b_props.convert_item`), un par un, puis la distribution (5e, 50e, 95e centile) de chaque indicateur
sur l'ensemble. `tools/style_check.py` note n'importe quel élément contre ces centiles ; `docs/STYLE_GUIDE_STUDIO.md` en tire des règles courtes.

Indicateurs par décor (volume des boîtes pour poids de couleur ; unités de taille : voxels de 1/16 m = 0,0625 m) :
  S_mean, V_mean, V_sd (contraste), pure_white (V > .97, S < .06) / pure_black (V < .06) (part du volume), sat_high (part du volume à saturation > .7), n_colors (couleurs distinctes à 5 bits),
  n_boxes, density (boîtes par m³ d'emprise), min_side_med (plus petit côté médian des boîtes, en voxels), thin_share (part des boîtes dont le plus petit côté < 2 voxels),
  chunk_share (part du VOLUME en boîtes dont le plus petit côté ≥ 8 voxels = 0,5 m : gros pans pleins), micro_cube_share (part des boîtes qui sont de petits cubes : côté ≤ 4,5 voxels et
  rapport des côtés < 1,6 : c'est ce qui fait l'effet « Lego / pixel » des figurines importées), height_m, extent_m (plus grande dimension)."""
import argparse, colorsys, json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
PX = 1. / 16.


from hstudio.voxelgpu.b_style import metrics, rgb      # une seule définition des indicateurs (la bibliothèque), ce script ne fait que fabriquer la référence


def percentiles(rows, keys):
    out = {}
    for k in keys:
        v = np.array([r[k] for r in rows], float); out[k] = dict(p05=float(np.percentile(v, 5)), p50=float(np.percentile(v, 50)), p95=float(np.percentile(v, 95)), min=float(v.min()), max=float(v.max()))
    return out


def ref_colors(boxes_by_decor):
    """toutes nos couleurs (5 bits par canal), chaque décor pèse pareil, boîtes lumineuses exclues : sert à mesurer l'écart d'une couleur à notre palette"""
    acc = {}
    for boxes in boxes_by_decor:
        bx = [b for b in boxes if not b.get('emis')]
        if not bx: continue
        vol = np.array([b['w'] * b['h'] * b['d'] for b in bx]); vol = vol / vol.sum()
        for b, v in zip(bx, vol):
            c = b['color']; q = (((c >> 16) & 255) >> 3 << 3, ((c >> 8) & 255) >> 3 << 3, (c & 255) >> 3 << 3); acc[q] = acc.get(q, 0.) + float(v)
    tot = sum(acc.values()); return [[*map(int, k), round(v / tot, 6)] for k, v in sorted(acc.items(), key=lambda kv: -kv[1]) if v / tot >= 0.0002]


def palette(boxes_by_decor, n=28):
    """palette dominante de nos décors : couleurs quantifiées à 4 bits par canal, pondérées par le volume (chaque décor pèse pareil), les n plus fréquentes"""
    acc = {}
    for boxes in boxes_by_decor:
        vol = np.array([b['w'] * b['h'] * b['d'] for b in boxes]); vol = vol / vol.sum()
        for b, v in zip(boxes, vol):
            c = tuple((np.round(rgb(b['color']) * 15) * 17).astype(int)); acc[c] = acc.get(c, 0.) + float(v)
    return [dict(rgb=list(map(int, c)), weight=round(w / len(boxes_by_decor), 5)) for c, w in sorted(acc.items(), key=lambda kv: -kv[1])[:n]]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(ROOT / 'hstudio' / 'voxelgpu' / 'style_reference.json')); a = ap.parse_args()
    from hstudio.voxelgpu import b_props as BP
    rows, names, allboxes = [], [], []
    for k in BP.catalogue():
        try: p, _ = BP.convert_item(dict(type='b:' + k, at=[0, 0]))
        except Exception: continue
        m = metrics(p['boxes'])
        if m is None: continue
        rows.append(m); names.append(k); allboxes.append([b for b in p['boxes'] if b['w'] > 0 and b['h'] > 0 and b['d'] > 0])
    keys = [k for k in rows[0]]
    ref = dict(source='217 décors de PIXEL 3D convertis (b_props.convert_item), un poids par décor', n=len(rows), percentiles=percentiles(rows, keys), palette=palette(allboxes), ref_colors=ref_colors(allboxes),
               per_decor={n: {k: round(v, 4) for k, v in r.items()} for n, r in zip(names, rows)},
               render=dict(note='le peintre applique à TOUT `bset` le même grain (b_kit.js : vox(..., rim .3, var .08)) : le grain n\'est pas à ajouter dans les données', var=.08, rim=.3, voxel_m=PX))
    Path(a.out).write_text(json.dumps(ref, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'{len(rows)} décors mesurés -> {a.out}')
    for k in keys: print(f"  {k:<14} p05 {ref['percentiles'][k]['p05']:8.3f}   p50 {ref['percentiles'][k]['p50']:8.3f}   p95 {ref['percentiles'][k]['p95']:8.3f}")
    print('  palette :', ' '.join('#%02x%02x%02x' % tuple(c['rgb']) for c in ref['palette'][:14]))


if __name__ == '__main__': main()
