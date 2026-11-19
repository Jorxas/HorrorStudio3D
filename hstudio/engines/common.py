"""Shared helpers for both engines: subtitles chunking/timing, text drawing, hearts timeline."""
import re, unicodedata
from PIL import ImageFont, ImageDraw

_fonts = {}
def font(path, size, variation=None):
    key = (path, size, variation)
    if key not in _fonts:
        f = ImageFont.truetype(path, size)
        if variation:
            try: f.set_variation_by_name(variation)
            except Exception: pass
        _fonts[key] = f
    return _fonts[key]

def norm(w):
    w = unicodedata.normalize('NFD', w.lower())
    w = ''.join(c for c in w if unicodedata.category(c) != 'Mn')
    return re.sub(r"[^a-z0-9']", '', w)

def line_tokens(line):
    """words of a line with keyword flags. Keywords come from line['keywords'] or *markup* in the text."""
    text = line.get('display', line['text'])
    kws = {norm(k) for k in line.get('keywords', []) or [] for k in k.split()}
    out = []; inside = False
    for w in text.split():
        star = '*' in w; flag = inside or star
        if w.count('*') % 2 == 1: inside = not inside
        clean = w.replace('*', '')
        if not clean: continue
        out.append((clean, flag or (norm(clean) in kws and norm(clean) != '')))
    return out

def chunk_tokens(tokens, max_chars=15, max_words=4, upper=True):
    chunks = []; cur = []
    for w, k in tokens:
        ww = w.upper() if upper else w
        cand = cur + [(ww, k)]
        if cur and (len(' '.join(x for x, _ in cand)) > max_chars or len(cand) > max_words):
            chunks.append(cur); cand = [(ww, k)]
        cur = cand
        if ww[-1] in '.?!' or (ww.endswith(',') and len(cur) >= 2) or ww.endswith('...') or ww.endswith('…'):
            chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    if len(chunks) > 1 and len(chunks[-1]) == 1 and len(chunks[-1][0][0]) <= 3 and len(chunks[-2]) < max_words \
            and len(' '.join(x for x, _ in chunks[-2] + chunks[-1])) <= max_chars:
        last = chunks.pop(); chunks[-1] = chunks[-1] + last
    return [c for c in chunks if c]

def build_subs(lines, max_chars=15, max_words=4, upper=True):
    """-> list of {a, b, words:[(w, is_keyword)], line}"""
    subs = []
    for i, ln in enumerate(lines):
        if ln.get('no_subtitle'): continue
        chunks = chunk_tokens(line_tokens(ln), max_chars, max_words, upper)
        if not chunks: continue
        wt = ln.get('word_times')                   # [[start, end], ...] one per word, from the aligner
        nw = sum(len(c) for c in chunks)
        if wt and len(wt) == nw:
            k = 0
            for c in chunks:
                a = wt[k][0]; b = wt[k + len(c) - 1][1]; k += len(c)
                subs.append(dict(a=a, b=b, words=c, line=i))
        else:
            segs = ln.get('segs') or [[ln['start'], ln['end']]]
            tot = sum(e - s for s, e in segs) or 1e-3
            def tm(p):
                x = p * tot
                for s, e in segs:
                    if x <= e - s: return s + x
                    x -= e - s
                return segs[-1][1]
            weights = [sum(len(w) + 1 for w, _ in c) for c in chunks]; W_ = sum(weights); acc = 0
            for c, wgt in zip(chunks, weights):
                a = tm(acc / W_); acc += wgt; b = tm(acc / W_)
                subs.append(dict(a=a, b=b, words=c, line=i))
    for k in range(len(subs) - 1):
        if subs[k + 1]['a'] - subs[k]['b'] < .45: subs[k]['b'] = subs[k + 1]['a']
        else: subs[k]['b'] += .12
    if subs: subs[-1]['b'] += .3
    return subs

def active_sub(subs, g):
    for s in subs:
        if s['a'] - .03 <= g < s['b']: return s
    return None

def outlined(d, xy, text, fnt, fill, off=5, outline=(0, 0, 0)):
    x, y = xy
    for dx, dy in ((off, off), (-off + 2, off), (off, -off + 2), (-off + 2, -off + 2), (0, off), (off, 0)):
        d.text((x + dx, y + dy), text, font=fnt, fill=outline)
    d.text((x, y), text, font=fnt, fill=fill)

def hearts_at(ep, lines, g):
    """hearts state at time g from episode['hearts'] = [{"line": i | "t": sec, "value": [1,1,0]}] (+ hud default)"""
    hud = ep.get('hud', {}) or {}
    cur = list(hud.get('hearts', [1, 1, 1]))
    for ev in sorted(ep.get('hearts', []) or [], key=lambda e: _ev_time(e, lines)):
        if g >= _ev_time(ev, lines): cur = list(ev.get('value', cur))
    return cur

def _ev_time(ev, lines):
    if 't' in ev: return float(ev['t'])
    li = int(ev.get('line', 0)); li = max(0, min(li, len(lines) - 1))
    return lines[li]['start'] + float(ev.get('offset', 0))
