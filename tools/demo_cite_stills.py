"""Stills of the contract of « Le Dernier Noyau » at chosen instants (default: the middle of every shot), contact sheets of 6 x N. usage: python tools/demo_cite_stills.py [out_dir] [t1,t2,...] [--size 540x960]"""
import json, sys, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import render, contract as C
WORK = ROOT / 'projects' / 'demo_narrative_20261029'
out = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else WORK / 'stills'; out.mkdir(parents=True, exist_ok=True)
for f in out.glob('t_*.png'): f.unlink()
c = C.load(WORK / 'contract.json')
times = [float(x) for x in sys.argv[2].split(',')] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else [round((s['t0'] + s['t1']) / 2, 2) for s in c['stages']]
size = (540, 960)
if '--size' in sys.argv: w, h = sys.argv[sys.argv.index('--size') + 1].split('x'); size = (int(w), int(h))
render.run_painter(WORK / 'contract.json', None, 'nvidia', size=size, stills=times, stills_dir=out, quiet=True)
files = sorted(out.glob('t_*.png'), key=lambda p: float(p.stem[2:])); print(len(files), 'images')
for k in range(0, len(files), 12):
    subprocess.run([sys.executable, str(ROOT / 'tools' / 'demo_sheet.py'), str(out / f'sheet_{k // 12}.png'), '6', '300'] + [str(f) for f in files[k:k + 12]], check=True)
