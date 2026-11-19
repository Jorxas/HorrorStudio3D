"""Read the burned-in subtitles of a source video: text, exact first/last frame, and which words are drawn in red.

The subtitle band is cropped and OCR'd (rapidocr) every `step` frames; equal texts are merged into chunks; each chunk
boundary is then refined to the exact frame by comparing the band pixels (the subtitle is a hard on/off). The result is DATA
for a scene file (`captions`), not a rendering: nothing of the source picture survives except the words and their timing."""
import re, subprocess
import numpy as np

W = 1080


def _norm(t):
    t = t.upper().replace('·', "'").replace('’', "'").replace('`', "'")
    return re.sub(r'\s+', ' ', t).strip()


def _textmask(img):
    """pixels that can belong to the caption: near-white fill or saturated red fill (the dark outline is ignored)"""
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    return ((r > 225) & (g > 225) & (b > 225)) | ((r > 170) & (g < 120) & (b < 120))


def red_runs(img, x0, x1):
    """x ranges (pixels) of strongly red columns inside [x0, x1]"""
    r, g, b = img[..., 0].astype(int), img[..., 1].astype(int), img[..., 2].astype(int)
    m = ((r > 170) & (g < 120) & (b < 120) & (r - g > 80)).sum(0) >= 2
    runs = []; s = None
    for x in range(max(0, int(x0)), min(len(m), int(x1) + 1)):
        if m[x] and s is None: s = x
        if not m[x] and s is not None:
            runs.append((s, x - 1)); s = None
    if s is not None: runs.append((s, int(x1)))
    return runs


def read(path, y0=820, y1=1090, step=5, ignore=()):
    """-> (chunks, n_frames); chunk = dict(f0, f1 (frame indices, f1 exclusive), text, red [bool per word], y)"""
    from rapidocr import RapidOCR
    eng = RapidOCR(); h = y1 - y0; n = W * h * 3
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'crop={W}:{h}:0:{y0}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    sig = []; samples = []; i = 0
    while True:
        b = p.stdout.read(n)
        if len(b) < n: break
        img = np.frombuffer(b, np.uint8).reshape(h, W, 3)
        sig.append(_textmask(img)[::4, ::4].astype(np.int16))
        if i % step == 0:
            res = eng(img); lines = []
            if res.txts is not None:
                for bx, tx, sc in zip(res.boxes, res.txts, res.scores):
                    t = _norm(tx)
                    if float(sc) < .6 or t in ignore or re.fullmatch(r'[\W\d_]{0,2}', t): continue
                    xs = [q[0] for q in bx]; ys = [q[1] for q in bx]
                    x0, x1, ya, yb = min(xs), max(xs), int(min(ys)), int(max(ys))
                    lines.append(dict(text=t, x0=x0, x1=x1, y=(ya + yb) / 2 + y0, runs=red_runs(img[max(0, ya):yb + 1], x0, x1)))
            samples.append((i, sorted(lines, key=lambda l: (round(l['y'] / 45.), l['x0']))))     # reading order: line first, then left to right
        i += 1
    p.wait(); N = i
    key = lambda ls: ' / '.join(l['text'] for l in ls)
    # merge equal consecutive samples (a lone differing sample between two equal ones is an OCR glitch)
    ks = [key(ls) for _, ls in samples]
    for j in range(1, len(ks) - 1):
        if ks[j] != ks[j - 1] and ks[j - 1] == ks[j + 1]: ks[j] = ks[j - 1]
    chunks = []
    for j, (f, ls) in enumerate(samples):
        if chunks and ks[j] == chunks[-1]['k']: chunks[-1]['n'] += 1; chunks[-1]['samples'].append(ls); continue
        chunks.append(dict(k=ks[j], f0=f, n=1, samples=[ls]))
    out = []
    for c in chunks:
        if not c['k']: continue
        out.append(c)
    # refine boundaries: first frame (after the last sample of the previous chunk) whose band differs from the previous sample's band
    def refine(a, b):
        """a: frame of the old state, b: first sampled frame of the new state -> first frame of the new state"""
        da = lambda i, j: float(np.abs(sig[i] - sig[j]).mean())
        for f in range(a + 1, b + 1):
            if da(f, b) < da(f, a): return f
        return b
    for c in out:
        prev = max([f for f, _ in samples if f < c['f0']], default=None)
        c['f0'] = refine(prev, c['f0']) if prev is not None and c['f0'] > 0 else c['f0']
    for k, c in enumerate(out):
        last = c['f0'] + (c['n'] - 1) * step
        nxt = out[k + 1]['f0'] if k + 1 < len(out) else N
        # end = first frame where the band is no longer the same as inside the chunk (it may go empty before the next chunk)
        f = last
        while f + 1 < min(nxt, N) and float(np.abs(sig[f + 1] - sig[last]).mean()) < .12: f += 1
        c['f1'] = f + 1
        ls = c['samples'][len(c['samples']) // 2]
        words = []; red = []
        for l in ls:
            ws = l['text'].split(' ')
            if len(ws) == 1: words.append(ws[0]); red.append(bool(l['runs'])); continue
            tot = max(1, len(l['text'])); pos = 0
            for w in ws:
                cx = l['x0'] + (l['x1'] - l['x0']) * (pos + len(w) / 2) / tot; pos += len(w) + 1
                words.append(w); red.append(any(a - 6 <= cx <= b + 6 for a, b in l['runs']))
        c['text'] = c['k'].replace(' / ', ' '); c['words'] = words; c['red'] = red; c['y'] = float(np.mean([l['y'] for l in ls])) if ls else None
        del c['samples']
    return out, N
