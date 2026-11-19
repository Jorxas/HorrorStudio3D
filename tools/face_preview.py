"""python tools/face_preview.py [--out dir] [--gpu nvidia] [--size 360x640]
SHORT visual proof of the face layer (a few stills, no video): the same clerk of « La Dernière Pompe » at the same instants, once with the layer that shipped with the
continuity film (`legacy`) and once with the human model (`human`, with lip-sync from the text), the camera put on his face. The camera is a close-up written for this
proof only (it is NOT the film's camera, which keeps heads small on purpose); nothing is written to the film's folders. The face rows are re-read at FILM time here (faceact.stage_rows): director.build reads them at stage time, which shifts them in every stage but the first.
  row 1 / 2  a bang at 5.0 s (calm face before): lids, brow flash, startle blink, eyes turning towards the cause
  row 3 / 4  a spoken line (6.0 s - 7.6 s): the jaw follows the syllables and closes on the pauses (legacy: a sinusoid whatever is said)
Needs the GPU painter (node + playwright, see hstudio/voxelgpu/render.py)."""
import argparse, copy, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from hstudio.voxelgpu import director, render, blocking as B, faceact as FA, contract as C
from hstudio.voxelgpu.films import pompe_continuite as NEW

ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(ROOT / 'docs' / 'face_physics_proofs')); ap.add_argument('--gpu', default='nvidia'); ap.add_argument('--size', default='360x640')
a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True); w, h = map(int, a.size.split('x'))
LINE = "Je ne peux pas rester ici. Tu m'entends ?"


def episode(human):
    """the film's plan plus, in the calm shot S02 (3.8 - 7.6 s), a bang at 5.0 s and a spoken line from 6.0 s to 7.6 s. human: the bang is an `event_type` (who perceives it,
    when, and what the face does about it comes from eventreact / faceact) and the line carries its text; legacy: the same stimulus as an explicit `react` beat and the same
    `talk` window with no text (the painter babbles)."""
    ep = NEW.episode(); pl = ep['blocking']['plan']; beats = pl['beats']
    beats.append(dict(who='clerk', t=6.0, do='talk', until=7.6, **(dict(text=LINE) if human else {})))
    if human:
        pl['face'] = {'model': 'human'}; pl['actors']['clerk']['lipsync'] = True
        beats.append(dict(who='ghost', t=5.0, do='event', event_type='bang', source=[2.0, 0.0], loud=1.0))
    else: beats.append(dict(who='clerk', t=5.0, do='react', face='scared', i=.9, look=[2.0, 0.0]))
    return ep


def close_up(c):
    """replace the camera of every shot by a close-up on the clerk's head, following his head turn (proof only)"""
    ix = {n: i for i, n in enumerate(c['actor_cols'])}
    for st in c['stages']:
        rows = st['actors'].get('clerk')
        if not rows: continue
        cam = []
        for r in rows[:len(st['camera'])]:
            yaw = r[ix['yaw']] + r[ix['hyaw']]; hx, hz = r[ix['x']], r[ix['z']]
            cam.append([hx + math.sin(yaw) * 1.45, 1.72, hz + math.cos(yaw) * 1.45, hx, 1.74, hz, 34., 0.])
        st['camera'] = cam + [cam[-1]] * (len(st['camera']) - len(cam))
    return c


def at(t, base): return [round(base + d, 3) for d in t]


SHOCK = at((-.25, .05, .12, .25, .5, 1.1), 5.18); SPEECH = at((.15, .35, .55, .75, .95, 1.3), 6.0)
sheet = []
for name in ('legacy', 'human'):
    ep = episode(name == 'human'); c = director.build(ep, '9:16', 30); Cb, _ = B.compile_episode(ep); tr = FA.build_all(Cb, director.EXPR_MAP, c['expressions'], c['duration'] + 1.)
    for st in c['stages']:                       # director.build reads the face rows with the stage-local time; the proof plays them at FILM time (FA.stage_rows)
        if st.get('faces'): st['faces'] = {a: FA.stage_rows(tr[a], st['t0'], len(rows), c['fps']) for a, rows in st['faces'].items()}
    c = close_up(c); p = out / f'contract_{name}.json'; C.save(c, p)
    times = SHOCK + SPEECH; render.run_painter(p, None, a.gpu, (w, h), stills=times, stills_dir=out / f'stills_{name}', quiet=True)
    sheet.append([Image.open(out / f'stills_{name}' / f't_{t:.2f}.png') for t in times]); p.unlink()
S = Image.new('RGB', (6 * w, 4 * h)); d = ImageDraw.Draw(S)
for r, (name, grp) in enumerate((('legacy · choc', 0), ('human · choc', 0), ('legacy · parole', 6), ('human · parole', 6))):
    ims = sheet[r % 2][grp:grp + 6]; ts = (SHOCK if grp == 0 else SPEECH)
    for k, im in enumerate(ims):
        S.paste(im, (k * w, r * h)); d.rectangle((k * w, r * h, k * w + 150, r * h + 14), fill=(0, 0, 0)); d.text((k * w + 4, r * h + 2), f'{name} {ts[k]:.2f}s', fill=(255, 255, 0))
dest = out / 'visages_legacy_vs_human.jpg'; S.save(dest, quality=85)
for name in ('legacy', 'human'):
    for f in (out / f'stills_{name}').glob('*.png'): f.unlink()
    (out / f'stills_{name}').rmdir()
print(dest, S.size)
