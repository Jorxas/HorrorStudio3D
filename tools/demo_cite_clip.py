"""Render a short span of the contract (1080x1920, 30 fps) with its own slice of the sound, to judge motion, light and speed before the one full render. usage: python tools/demo_cite_clip.py t0 t1 [name]"""
import subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from hstudio.voxelgpu import render
WORK = ROOT / 'projects' / 'demo_narrative_20261029'
t0, t1 = float(sys.argv[1]), float(sys.argv[2]); name = sys.argv[3] if len(sys.argv) > 3 else f'clip_{int(t0)}_{int(t1)}'
(WORK / 'clips').mkdir(exist_ok=True); v = WORK / 'clips' / (name + '_v.mp4'); t = time.time()
for tr in ('bin', 'b64'):
    try: render.run_painter(WORK / 'contract.json', v, 'nvidia', size=(1080, 1920), start=t0, end=t1, crf=20, quiet=True, transport=tr); print('transport', tr); break
    except RuntimeError as e: print('transport', tr, 'en échec :', str(e)[:120]); t = time.time()
print('rendu', round(time.time() - t, 1), 's pour', t1 - t0, 's ->', round((t1 - t0) * 30 / (time.time() - t), 2), 'i/s')
out = WORK / 'clips' / (name + '.mp4')
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(v), '-ss', f'{t0:.3f}', '-t', f'{t1 - t0:.3f}', '-i', str(WORK / 'audio.wav'), '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', str(out)], check=True); print(out)
