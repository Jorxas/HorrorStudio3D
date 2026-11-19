"""python tools/fusion_preview.py [--out dir] [--size 360x640] [--gpu nvidia] [--rows continuity,fusion] [--moments key,...]
Stills (never a film) of the critical moments of « La Dernière Pompe », continuity film (row 1) against the fusion film (row 2), one labelled sheet per group of moments, and the
numbers measured on the same pixels (luminance, deep-shadow share, red share) in metrics.json. Needs the GPU painter."""
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
from PIL import Image, ImageDraw
from hstudio.voxelgpu import render, contract as C, director
from hstudio.voxelgpu.films import pompe_continuite as N, pompe_fusion as F
from genre_horror_preview import metrics

MOMENTS = [(12.9, 'S05 vitre + pompiste'), (23.6, 'S09 main sur la vitre'), (26.35, 'S11 avant'), (26.9, 'S11 disparu'), (27.5, 'S12 apparu'), (28.6, 'S12 apres'), (31.9, 'S14 faisceau'),
           (33.55, 'S15 epaule'), (52.3, 'S27 porte service'), (62.8, 'S33 voiture'), (65.6, 'S34 3 metres'), (70.8, 'S36 porte du fond')]


def stills(name, ep, times, out, size, gpu):
    c = director.build(ep, '9:16', ep['fps']); d = out / name; d.mkdir(parents=True, exist_ok=True); C.save(c, d / 'contract.json')
    render.run_painter(d / 'contract.json', None, gpu, size, stills=times, stills_dir=d / 'stills', quiet=True)
    return [Image.open(d / 'stills' / f't_{t:.2f}.png').convert('RGB') for t in times]


def sheet(rows, labels, size, path, per=6):
    w, h = size
    for part in range(0, len(labels), per):
        L = labels[part:part + per]; S = Image.new('RGB', (len(L) * w, len(rows) * h)); dr = ImageDraw.Draw(S)
        for r, (name, ims) in enumerate(rows):
            for k, im in enumerate(ims[part:part + per]):
                S.paste(im, (k * w, r * h)); dr.rectangle((k * w, r * h, k * w + 200, r * h + 12), fill=(0, 0, 0)); dr.text((k * w + 3, r * h + 1), f'{name} | {L[k]}', fill=(255, 255, 0))
        S.save(path.with_name(f'{path.stem}_{part // per}.png'))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(ROOT / 'projects' / 'fusion_finale_20261029' / 'preview')); ap.add_argument('--size', default='360x640'); ap.add_argument('--gpu', default='nvidia')
    ap.add_argument('--rows', default='continuity,fusion'); ap.add_argument('--only', default=''); ap.add_argument('--tag', default='sheet'); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); size = tuple(map(int, a.size.split('x')))
    mom = [m for m in MOMENTS if not a.only or any(m[1].startswith(k) for k in a.only.split(','))]; ts = [t for t, _ in mom]; rows = []; met = {}
    for r in a.rows.split(','):
        ep = N.episode() if r == 'continuity' else F.episode(); ims = stills(r, ep, ts, out, size, a.gpu); rows.append((r, ims)); met[r] = [dict(t=t, **metrics(im)) for (t, _), im in zip(mom, ims)]
    sheet(rows, [l for _, l in mom], size, out / a.tag); (out / f'{a.tag}_metrics.json').write_text(json.dumps(met, indent=1), encoding='utf-8')
    for r in met: print(r, [(m['t'], m['luma'], m['shadow_share']) for m in met[r]])
