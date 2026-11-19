"""python tools/remake_calibrate.py <film> <source.mp4> [--rounds 2] [--size 288x512] [--shots S00,S01|all]
Matches the average luminance of every shot of a remake to the source's (same shot, middle frame; HUD strip and caption band masked).
Writes examples/remakes/<film>_gain.json : {shot id: gain}, read by the film module as the default `env.gain` of the shot (it scales the
ambient / key light and the exposure of the set; lamps, flashlights and emissive props keep their own strength). One GPU still per shot per round."""
import argparse, importlib, json, subprocess, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image
from hstudio.voxelgpu import director, render, contract as C

ap = argparse.ArgumentParser(); ap.add_argument('film'); ap.add_argument('source'); ap.add_argument('--rounds', type=int, default=2); ap.add_argument('--size', default='288x512'); ap.add_argument('--shots', default='all')
ap.add_argument('--lo', type=float, default=.25); ap.add_argument('--hi', type=float, default=4.0); a = ap.parse_args()
w, h = map(int, a.size.split('x')); gf = ROOT / 'examples' / 'remakes' / f'{a.film}_gain.json'
gains = json.loads(gf.read_text(encoding='utf-8')) if gf.exists() else {}


def lum(im):
    g = np.asarray(im.convert('L').resize((w, h)), float); m = np.ones(g.shape, bool); m[:int(.11 * h)] = False; m[int(.43 * h):int(.53 * h)] = False
    return float(g[m].mean())


def src_frame(t):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', a.source, '-frames:v', '1', '-vf', f'scale={w}:{h}', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True)
    import io; return Image.open(io.BytesIO(r.stdout))


for rnd in range(a.rounds):
    mod = importlib.import_module(f'hstudio.voxelgpu.films.remake_{a.film}'); importlib.reload(mod); ep = mod.episode()
    c = director.build(ep, '9:16', ep['fps']); out = ROOT / 'projects' / 'remakes_voxelgpu_20261029' / 'micro' / a.film; out.mkdir(parents=True, exist_ok=True); C.save(c, out / 'contract_cal.json')
    sel = [s for s in c['stages'] if a.shots == 'all' or s['id'] in a.shots.split(',')]; mids = [round((s['t0'] + s['t1']) / 2, 3) for s in sel]
    render.run_painter(out / 'contract_cal.json', None, 'nvidia', (w, h), stills=mids, stills_dir=out / 'cal', quiet=True)
    rep = []
    for s, t in zip(sel, mids):
        ours = lum(Image.open(out / 'cal' / f't_{t:.2f}.png')); ref = lum(src_frame(t)); g0 = gains.get(s['id'], 1.)
        g1 = float(np.clip(g0 * (max(ref, 4.) / max(ours, 4.)) ** .8, a.lo, a.hi)); gains[s['id']] = round(g1, 3); rep.append((s['id'], ref, ours, g0, g1))
    gf.write_text(json.dumps(gains, indent=1), encoding='utf-8')
    err = np.mean([abs(r[2] - r[1]) / max(r[1], 4.) for r in rep]); print(f'round {rnd + 1}: mean relative luminance error before this round {err:.2f}')
    for r in rep: print(f'  {r[0]} source {r[1]:5.1f} ours {r[2]:5.1f} gain {r[3]:.2f} -> {r[4]:.2f}')
