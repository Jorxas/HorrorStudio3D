"""How many V4 characters does the painter hold at 30 i/s? A wide shot of N walkers in the 'ville' world, 2 s, rendered on the GPU,
timed from the painter's own report. No audio, nothing kept but the numbers (printed and written to projects/demo_narrative_20261029/load_probe.json)."""
import json, sys, time, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import director, render, contract as C

def episode(n):
    casts = {f'w{i}': {'preset': 'npc', 'variant': i} for i in range(n)}
    actors = [dict(id=f'w{i}', at=[-12 + i * 24. / max(1, n - 1), -.5 + (i % 3) * .5], facing='+x' if i % 2 else '-x') for i in range(n)]
    acts = [dict(who=f'w{i}', do='walk_to', to=[(-12 + i * 24. / max(1, n - 1)) + (6 if i % 2 else -6), -.5 + (i % 3) * .5], at=.1) for i in range(n)]
    return dict(title='probe', genre='neutral', aspect='9:16', fps=30, casts=casts,
                shots=[dict(stage='ville', dur=2., camera=dict(shot='wide', on=[f'w{i}' for i in range(min(n, 3))]), actors=actors, actions=acts)])

def main():
    out = {}; work = ROOT / 'projects' / 'demo_narrative_20261029' / 'probe'; work.mkdir(parents=True, exist_ok=True)
    for n in (2, 12, 24, 40):
        c = director.build(episode(n), '9:16', 30); p = work / f'c{n}.json'; C.save(c, p)
        t0 = time.time()
        import subprocess, io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            render.run_painter(p, work / f'c{n}.mp4', 'nvidia', size=(1080, 1920), crf=20, quiet=False)
        m = re.findall(r'([\d.]+) i/s', buf.getvalue()); out[n] = dict(wall_s=round(time.time() - t0, 1), ips=m[-1] if m else None, log=buf.getvalue()[-300:])
        print(n, out[n]['wall_s'], out[n]['ips'], flush=True)
    (ROOT / 'projects' / 'demo_narrative_20261029' / 'load_probe.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')

if __name__ == '__main__': main()
