"""python tools/b_style_stats.py [--json sortie.json]

Statistiques de couleur (teinte, saturation, valeur, contraste, blancs/noirs purs, nombre de couleurs) pondérées par le volume des boîtes :
nos décors de PIXEL 3D convertis (référence) contre chaque banque de modèles importés. Sert à régler `hstudio/voxelgpu/b_style.py`."""
import argparse, colorsys, json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import b_props as BP, vox_import as VI


def rgb(c): return np.array([(c >> 16) & 255, (c >> 8) & 255, c & 255], float) / 255.


def stats(cols, w):
    """cols (n,3) 0-1, w (n,) poids -> dict de statistiques"""
    w = np.asarray(w, float); w = w / w.sum(); hsv = np.array([colorsys.rgb_to_hsv(*c) for c in cols])
    S, V, H = hsv[:, 1], hsv[:, 2], hsv[:, 0]
    mean = lambda x: float((x * w).sum()); sd = lambda x: float(np.sqrt((((x - mean(x)) ** 2) * w).sum()))
    lum = cols @ np.array([.2126, .7152, .0722])
    chroma = S > .12
    hx = np.cos(2 * np.pi * H) * S; hy = np.sin(2 * np.pi * H) * S
    return dict(S_mean=mean(S), S_sd=sd(S), V_mean=mean(V), V_sd=sd(V), lum_mean=float((lum * w).sum()), pure_white=float(w[(V > .93) & (S < .1)].sum()), pure_black=float(w[V < .1].sum()),
                sat_high=float(w[S > .7].sum()), hue_vec=(float((hx * w).sum()), float((hy * w).sum())), n_colors=int(len({tuple(np.round(c * 31).astype(int)) for c in cols})),
                chroma_share=float(w[chroma].sum()))


def collect_boxes(boxes):
    cols = np.array([rgb(b['color']) for b in boxes]); vol = np.array([b['w'] * b['h'] * b['d'] for b in boxes]); return cols, vol


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--json'); a = ap.parse_args(); out = {}
    cols, vol = [], []
    for k in BP.catalogue():
        try: p, _ = BP.convert_item(dict(type='b:' + k, at=[0, 0]))
        except Exception: continue
        if not p['boxes']: continue
        c, v = collect_boxes(p['boxes']); cols.append(c); vol.append(v / v.sum())            # chaque décor pèse pareil
    out['decors (217)'] = stats(np.vstack(cols), np.concatenate(vol))
    for bank in sorted(VI.BANKS.glob('*')):
        cc, vv = [], []
        for p in sorted(bank.glob('*.vox')):
            try: m = VI.load(p)
            except Exception: continue
            c = np.array([rgb(b['color']) for b in m['boxes']]); v = np.array([b['w'] * b['h'] * b['d'] for b in m['boxes']], float); cc.append(c); vv.append(v / v.sum())
        if cc: out[bank.name] = stats(np.vstack(cc), np.concatenate(vv))
    print(f"{'source':<18}{'S moy':>7}{'S éc':>7}{'V moy':>7}{'V éc':>7}{'blanc':>7}{'noir':>7}{'S>.7':>7}{'chroma':>8}{'couleurs':>9}")
    for k, s in out.items(): print(f"{k:<18}{s['S_mean']:>7.2f}{s['S_sd']:>7.2f}{s['V_mean']:>7.2f}{s['V_sd']:>7.2f}{s['pure_white']:>7.2f}{s['pure_black']:>7.2f}{s['sat_high']:>7.2f}{s['chroma_share']:>8.2f}{s['n_colors']:>9}")
    if a.json: Path(a.json).write_text(json.dumps(out, indent=1), encoding='utf-8')


if __name__ == '__main__': main()
