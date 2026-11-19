"""python tools/genre_horror_preview.py [--out dir] [--size 360x640] [--gpu nvidia] [--only sheet,vanish,gallery]
Micro-preview of the genre-horror lane on « La Dernière Pompe » : a few stills (never a film) for the variants of films/pompe_genre_preview.py, one labelled sheet each,
and the numbers measured on the same pixels (luminance, saturation, share of red pixels, share of deep shadow, contrast) in metrics.json.
  sheet   rows = legacy / monster / monster_dread, columns = five moments of the film (ghost behind the glass, hand on the glass, in the torch beam, at the service door, at the inner door)
  gallery the same station under five presets (dread / calm_day / golden_hour / cold_dawn / clean_future), human cast: the graphics reused outside horror
  vanish  « il disparaît » : the same four instants (26.2 / 26.5 / 26.8 / 27.5 s) with the walk (monster_dread) and with the declared vanish (vanish)
Needs the GPU painter (voxelgpu_js, playwright from engine A's folder). No audio, no encode."""
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np
from PIL import Image, ImageDraw
from hstudio.voxelgpu import render, contract as C
from hstudio.voxelgpu.films import pompe_genre_preview as P

MOMENTS = [(10.4, 'S04 derrière la vitre'), (23.5, 'S09 main sur la vitre'), (33.55, 'S15 dans le faisceau'), (51.3, 'S27 porte de service'), (70.8, 'S36 porte du fond')]
VANISH_T = [26.2, 26.5, 26.8, 27.5]
GALLERY_T = [(.8, 'S00 la station du parking'), (12.7, 'S05 devant la vitre'), (25.5, 'S10 allée')]


def metrics(im):
    """measured on the picture without the top HUD band and the caption band (rows 12%..45% and 52%..100%)"""
    a = np.asarray(im.convert('RGB')).astype(np.float32) / 255.; h = a.shape[0]
    a = np.concatenate([a[int(.12 * h):int(.45 * h)], a[int(.52 * h):]], axis=0)
    mx, mn = a.max(2), a.min(2); sat = np.where(mx > 1e-4, (mx - mn) / np.maximum(mx, 1e-4), 0.)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]; d = np.maximum(mx - mn, 1e-4)
    hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60.
    luma = .2126 * r + .7152 * g + .0722 * b
    red = (((hue < 15) | (hue > 345)) & (sat > .45) & (mx > .35)).mean()
    hist, _ = np.histogram(hue[sat > .15], bins=24, range=(0, 360)); p = hist / max(1, hist.sum()); ent = float(-(p[p > 0] * np.log2(p[p > 0])).sum())
    warm = float(r.mean() - b.mean())
    return dict(luma=round(float(luma.mean()), 4), warmth=round(warm, 4), sat=round(float(sat.mean()), 4), red_share=round(float(red), 5), shadow_share=round(float((luma < .12).mean()), 4),
                contrast=round(float(np.percentile(luma, 95) - np.percentile(luma, 5)), 4), hue_entropy_bits=round(ent, 3))


def stills(variant, times, out, size, gpu):
    c = P.contract(variant); d = out / variant; d.mkdir(parents=True, exist_ok=True); C.save(c, d / 'contract.json')
    render.run_painter(d / 'contract.json', None, gpu, size, stills=times, stills_dir=d / 'stills', quiet=True)
    return [Image.open(d / 'stills' / f't_{t:.2f}.png').convert('RGB') for t in times]


def gallery_stills(preset, out, size, gpu):
    c = P.gallery_contract(preset); d = out / ('gallery_' + preset); d.mkdir(parents=True, exist_ok=True); C.save(c, d / 'contract.json'); ts = [t for t, _ in GALLERY_T]
    render.run_painter(d / 'contract.json', None, gpu, size, stills=ts, stills_dir=d / 'stills', quiet=True)
    return [Image.open(d / 'stills' / f't_{t:.2f}.png').convert('RGB') for t in ts]


def sheet(rows, cols_labels, size, path):
    w, h = size; S = Image.new('RGB', (len(cols_labels) * w, len(rows) * h)); dr = ImageDraw.Draw(S)
    for r, (name, ims) in enumerate(rows):
        for k, im in enumerate(ims):
            S.paste(im, (k * w, r * h)); dr.rectangle((k * w, r * h, k * w + 215, r * h + 12), fill=(0, 0, 0)); dr.text((k * w + 3, r * h + 1), f'{name} | {cols_labels[k]}', fill=(255, 255, 0))
    S.save(path)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(ROOT / 'projects' / 'genre_horror_20261029' / 'preview')); ap.add_argument('--size', default='360x640')
    ap.add_argument('--gpu', default='nvidia'); ap.add_argument('--only', default='sheet,vanish'); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); size = tuple(map(int, a.size.split('x'))); met = {}
    if 'sheet' in a.only:
        rows = []
        for v in ('legacy', 'monster', 'monster_dread'):
            ims = stills(v, [t for t, _ in MOMENTS], out, size, a.gpu); rows.append((v, ims)); met[v] = [dict(t=t, **metrics(im)) for (t, _), im in zip(MOMENTS, ims)]
        sheet(rows, [l for _, l in MOMENTS], size, out / 'sheet_variantes.png'); print(out / 'sheet_variantes.png')
    if 'vanish' in a.only:
        rows = []
        for v in ('monster_dread', 'vanish'):
            ims = stills(v, VANISH_T, out, size, a.gpu); rows.append((v, ims)); met['vanish_' + v] = [dict(t=t, **metrics(im)) for t, im in zip(VANISH_T, ims)]
        sheet(rows, [f'{t:.1f}s' for t in VANISH_T], size, out / 'sheet_disparition.png'); print(out / 'sheet_disparition.png')
    if 'gallery' in a.only:
        rows = []
        for pn in P.GALLERY:
            ims = gallery_stills(pn, out, size, a.gpu); rows.append((pn, ims)); met['gallery_' + pn] = [dict(t=t, **metrics(im)) for (t, _), im in zip(GALLERY_T, ims)]
        sheet(rows, [l for _, l in GALLERY_T], size, out / 'sheet_genres.png'); print(out / 'sheet_genres.png')
    (out / 'metrics.json').write_text(json.dumps(met, indent=1, ensure_ascii=False), encoding='utf-8')
    for k, rows in met.items():
        print(k, 'moyennes :', {m: round(float(np.mean([r[m] for r in rows])), 4) for m in ('luma', 'warmth', 'sat', 'red_share', 'shadow_share', 'contrast', 'hue_entropy_bits')})
