"""python tools/remake_stills.py <film> <shots> [--at 0.15,0.5,0.85] [--size 540x960] [--out dir] [--gpu nvidia]
Micro-render of chosen shots of a remake film module (hstudio/voxelgpu/films/remake_<film>.py) as stills on the GPU, assembled in one
labelled sheet, so a hard shot can be judged and tuned before the whole film is rendered. <shots> = comma list of ids (S08,S09) or `all`."""
import argparse, importlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from hstudio.voxelgpu import director, render, contract as C

ap = argparse.ArgumentParser(); ap.add_argument('film'); ap.add_argument('shots'); ap.add_argument('--at', default='0.12,0.5,0.88'); ap.add_argument('--size', default='540x960')
ap.add_argument('--env', default=None, help='JSON merged into every shot env (look tuning)'); ap.add_argument('--out', default=None); ap.add_argument('--gpu', default='nvidia'); ap.add_argument('--cols', type=int, default=0); a = ap.parse_args()
mod = importlib.import_module(f'hstudio.voxelgpu.films.remake_{a.film}'); ep = mod.episode()
out = Path(a.out or ROOT / 'projects' / 'remakes_voxelgpu_20261029' / 'micro' / a.film); out.mkdir(parents=True, exist_ok=True)
if a.env:
    for sh in ep['shots']: sh['env'] = {**(sh.get('env') or {}), **json.loads(a.env)}
c = director.build(ep, '9:16', ep['fps']); C.save(c, out / 'contract.json')
ids = [s['id'] for s in c['stages']] if a.shots == 'all' else a.shots.split(','); fr = [float(x) for x in a.at.split(',')]; w, h = map(int, a.size.split('x'))
times = []; lab = []
for st in c['stages']:
    if st['id'] in ids:
        for f in fr: times.append(round(st['t0'] + f * (st['t1'] - st['t0']), 3)); lab.append(f"{st['id']} {times[-1]:.2f}s")
render.run_painter(out / 'contract.json', None, a.gpu, (w, h), stills=times, stills_dir=out / 'stills', quiet=True)
ims = [Image.open(out / 'stills' / f't_{t:.2f}.png') for t in times]; cols = a.cols or (len(fr) if len(fr) > 1 else 4); rows = (len(ims) + cols - 1) // cols
S = Image.new('RGB', (cols * w, rows * h)); d = ImageDraw.Draw(S)
for k, im in enumerate(ims): S.paste(im, ((k % cols) * w, (k // cols) * h)); d.text(((k % cols) * w + 6, (k // cols) * h + 4), lab[k], fill=(255, 255, 0))
import numpy as np
print('luminance moyenne par image :', ', '.join(f"{l.split()[0]}={np.asarray(im.convert('L')).mean():.0f}" for l, im in zip(lab, ims)))
dest = out / f"sheet_{a.shots.replace(',', '_')[:40]}.png"; S.save(dest); print(dest)
