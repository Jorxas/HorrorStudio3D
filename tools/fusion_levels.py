"""python tools/fusion_levels.py [--target .12] [--passes 3] [--size 270x480] [--only S09,S14]
Levels the exposure of each shot of the fusion film on MEASURED pixels (the middle still of each shot, HUD and caption bands excluded, tools/genre_horror_preview.metrics): the dread mood plus the
new cameras left some shots at 0.04 luminance. Damped iteration on `exposure_k` (shot env), clamped to [.5, 3.5]; writes examples/remakes/pompe_fusion_levels.json. Needs the GPU painter.
It levels the mean; it does not decide that the creature is readable (that is read on the sheets, tools/fusion_preview.py)."""
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
from PIL import Image
from hstudio.voxelgpu import render, contract as C, director
from hstudio.voxelgpu.films import pompe_fusion as F, remake_pompe as OLD
from genre_horror_preview import metrics

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--target', type=float, default=.12); ap.add_argument('--passes', type=int, default=3); ap.add_argument('--size', default='270x480')
    ap.add_argument('--only', default=''); ap.add_argument('--gpu', default='nvidia'); a = ap.parse_args()
    size = tuple(map(int, a.size.split('x'))); T = OLD.T; ids = [f'S{i:02d}' for i in range(len(T) - 1)]
    if a.only: ids = [i for i in ids if i in a.only.split(',')]
    lv = json.loads(F.LEVELS_FILE.read_text(encoding='utf-8')) if F.LEVELS_FILE.exists() else {}
    work = ROOT / 'projects' / 'fusion_finale_20261029' / 'levels'; work.mkdir(parents=True, exist_ok=True)
    for p in range(a.passes):
        F.LEVELS_FILE.write_text(json.dumps(lv, indent=1), encoding='utf-8')
        c = director.build(F.episode(), '9:16', 30); C.save(c, work / 'contract.json')
        ts = [round((T[int(i[1:])] + T[int(i[1:]) + 1]) / 2, 2) for i in ids]
        render.run_painter(work / 'contract.json', None, a.gpu, size, stills=ts, stills_dir=work / 'stills', quiet=True)
        worst = 0.
        for i, t in zip(ids, ts):
            m = metrics(Image.open(work / 'stills' / f't_{t:.2f}.png').convert('RGB'))['luma']; k = lv.get(i, F.DREAD_WORLD['exposure_k'])
            lv[i] = round(max(.5, min(3.5, k * (a.target / max(m, .01)) ** .7)), 3); worst = max(worst, abs(m - a.target))
            print(f'pass {p} {i} luma {m:.3f} exposure_k {k:.3f} -> {lv[i]:.3f}')
        print('pass', p, 'worst |luma - target| =', round(worst, 3), flush=True)
    F.LEVELS_FILE.write_text(json.dumps(lv, indent=1), encoding='utf-8'); print('écrit', F.LEVELS_FILE)
