"""python tools/remake_captions.py <film> <source.mp4>  -> examples/remakes/<film>_captions.json
Input  : examples/remakes/<film>_text.json = [[first_frame, end_frame, "TEXT"], ...]  (text re-read by a human from the OCR, frames measured on the source)
Output : [{t0, t1, text, words: [[word, red], ...], y}]  where the RED words and the caption's vertical position are measured on the source pixels:
         the caption band is located on two frames of each caption (white / red fill pixels), the text extent is split in equal character cells
         (the source font is monospaced) and a word is red when most of its fill pixels are red. Nothing of the source picture is kept."""
import json, subprocess, sys
from pathlib import Path
import numpy as np, cv2
ROOT = Path(__file__).resolve().parents[1]; film, src = sys.argv[1], sys.argv[2]; FPS = 30; W = 1080; Y0, Y1 = 780, 1120
rows = json.loads((ROOT / 'examples' / 'remakes' / f'{film}_text.json').read_text(encoding='utf-8'))
want = {}
for i, (f0, f1, t) in enumerate(rows):
    for k in (.35, .65): want.setdefault(min(f1 - 1, max(f0, int(f0 + (f1 - f0) * k))), []).append(i)
p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-vf', f'crop={W}:{Y1 - Y0}:0:{Y0}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
n = W * (Y1 - Y0) * 3; f = 0; last = max(want); obs = {i: [] for i in range(len(rows))}
while f <= last:
    b = p.stdout.read(n)
    if len(b) < n: break
    if f in want:
        a = np.frombuffer(b, np.uint8).reshape(Y1 - Y0, W, 3).astype(int); r, g, bl = a[..., 0], a[..., 1], a[..., 2]
        white = (r > 215) & (g > 215) & (bl > 215); red = (r > 170) & (g < 110) & (bl < 110) & (r - g > 80)
        # letters are thin strokes: drop every pixel that belongs to a wide blob of the same colour (a lit wall, a red canopy band behind the caption)
        def strokes(m, k=17):
            u = m.astype(np.uint8); core = cv2.erode(u, np.ones((k, k), np.uint8)); wide = cv2.dilate(core, np.ones((k + 4, k + 4), np.uint8)); return m & (wide == 0)
        white, red = strokes(white), strokes(red); txt = white | red
        prof = txt.sum(1); win = 60; best = max(range(0, len(prof) - win), key=lambda y: int(prof[y:y + win].sum())); band = slice(best, best + win)
        cols = txt[band].sum(0) >= 3; xs = np.where(cols)[0]
        if len(xs):
            clusters = []; s = xs[0]; prev = xs[0]
            for x in xs[1:]:
                if x - prev > 75: clusters.append((s, prev)); s = x
                prev = x
            clusters.append((s, prev)); c = max(clusters, key=lambda c: int(txt[band][:, c[0]:c[1] + 1].sum())); x0, x1 = c
            for i in want[f]: obs[i].append((x0, x1, red[band], txt[band], Y0 + best + win / 2))
    f += 1
p.kill()
out = []
for i, (f0, f1, text) in enumerate(rows):
    votes = []; ys = []
    for x0, x1, red, txt, yc in obs[i]:
        cw = (x1 - x0 + 1) / len(text); pos = 0; flags = []
        for w in text.split(' '):
            a, b = int(x0 + pos * cw), int(x0 + (pos + len(w)) * cw); pos += len(w) + 1
            tot = int(txt[:, a:b].sum()); flags.append(tot > 0 and int(red[:, a:b].sum()) > .5 * tot)
        votes.append(flags); ys.append(yc)
    flags = [sum(v[k] for v in votes) * 2 > len(votes) for k in range(len(text.split(' ')))] if votes else [False] * len(text.split(' '))
    out.append(dict(t0=round(f0 / FPS, 4), t1=round(f1 / FPS, 4), text=text, words=[[w, bool(r)] for w, r in zip(text.split(' '), flags)], y=round(float(np.median(ys)) / 1920, 4) if ys else .47))
ov = ROOT / 'examples' / 'remakes' / f'{film}_red_overrides.json'          # human corrections of the measurement: {first_frame: [indices of the red words]}
if ov.exists():
    fix = {int(k): v for k, v in json.loads(ov.read_text(encoding='utf-8')).items()}
    for (f0, f1, text), c in zip(rows, out):
        if f0 in fix: c['words'] = [[w, k in fix[f0]] for k, (w, _) in enumerate(c['words'])]
(ROOT / 'examples' / 'remakes' / f'{film}_captions.json').write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding='utf-8')
reds = [(c['text'], [w for w, r in c['words'] if r]) for c in out if any(r for _, r in c['words'])]
print(film, len(out), 'légendes,', len(reds), 'avec des mots rouges'); [print(' ', t, '->', r) for t, r in reds[:200]]
ys = sorted(set(c['y'] for c in out)); print('y distincts :', ys[:10], '...', ys[-5:])
