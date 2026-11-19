"""python tools/blocking_gain.py <film> [--target 50] [--out examples/remakes/<film>_gain.json]
Per-shot exposure of a blocked film, measured on real GPU stills (middle of every shot, HUD and captions excluded): the gain that brings the mean luminance of the
SCENE to the target, damped (power 0.8) and clamped to [0.6, 2.2] so a shot that is dark by story (a dark lot, a back room) stays dark but readable.
Unlike the first remakes' gains (0.25 .. 4.0, each fitted to a different source frame) this only levels the film against itself."""
import argparse, importlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np
from PIL import Image
from hstudio.voxelgpu import director, render, contract as C

ap = argparse.ArgumentParser(); ap.add_argument('film'); ap.add_argument('--target', type=float, default=50.); ap.add_argument('--out'); ap.add_argument('--gpu', default='nvidia'); a = ap.parse_args()
mod = importlib.import_module(f'hstudio.voxelgpu.films.{a.film}'); mod.GAIN.clear(); ep = mod.episode()
out = ROOT / 'projects' / 'pompe_continuite_20261029' / 'gain'; out.mkdir(parents=True, exist_ok=True)
c = director.build(ep, '9:16', ep['fps']); C.save(c, out / 'contract.json')
times = [round((st['t0'] + st['t1']) / 2, 3) for st in c['stages']]
render.run_painter(out / 'contract.json', None, a.gpu, (270, 480), stills=times, stills_dir=out / 'stills', quiet=True)
g = {}
for st, t in zip(c['stages'], times):
    im = np.asarray(Image.open(out / 'stills' / f't_{t:.2f}.png').convert('L'), float)[int(.2 * 480):int(.9 * 480)]       # the band without HUD and end-card text
    lum = max(5., float(im.mean())); g[st['id']] = round(float(min(2.2, max(.6, (a.target / lum) ** .8))), 3)
dest = Path(a.out or ROOT / 'examples' / 'remakes' / f'{a.film}_gain.json'); dest.write_text(json.dumps(g, indent=1), encoding='utf-8'); print(dest, g)
