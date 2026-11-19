"""Rend un projet du studio (épisode PIXEL 3D, non modifié) avec le peintre VOXEL : tools/ps1_in_voxel.py <projet> <sortie_dir> [t1 t2 ...] [--aspect 16:9]"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
from hstudio import paths
from hstudio.voxelgpu import from_ps1, contract as C, render

def main():
    a = sys.argv[1:]; asp = '9:16'
    if '--aspect' in a: i = a.index('--aspect'); asp = a[i + 1]; del a[i:i + 2]
    proj, out = a[0], Path(a[1]); times = [float(x) for x in a[2:]]
    out.mkdir(parents=True, exist_ok=True)
    pdir = Path(proj) if os.path.isdir(proj) else Path('projects') / proj
    ep = json.loads((pdir / 'episode.json').read_text(encoding='utf-8')); lines = json.loads((pdir / 'lines.json').read_text(encoding='utf-8'))
    meta = ep.get('lines', {}) or {}
    for i, l in enumerate(lines):
        for k, v in (meta.get(str(i)) or {}).items(): l.setdefault(k, v)
    dur = float(lines[-1]['end']) + 1.2
    t0 = time.time(); c = from_ps1.build(ep, lines, dur, asp); print('contrat en %.0f s' % (time.time() - t0))
    cp = out / 'contract.json'; C.save(c, cp)
    if not times: times = [round(s['t0'] + (s['t1'] - s['t0']) * .6, 2) for s in c['stages']]
    w, h = render.SIZES[asp]
    render.run_painter(cp, None, 'nvidia', (w // 2, h // 2), stills=times, stills_dir=out, quiet=True, fallback=True)
    print('images :', [str(out / f't_{t:.2f}.png') for t in times][:20])
main()
