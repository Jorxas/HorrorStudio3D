"""OCR chunks (subtitles.read) -> caption entries of a scene file: {t0, t1, text, words: [[word, red], ...]}.
Consecutive chunks that read the same set of words are one caption (the OCR re-reads the same caption several times and may swap word order);
the caption lasts from the first frame of the first reading to the first frame of the next different caption (or the end of the last reading)."""
import re


def key(c): return tuple(sorted(w.strip('.,?!:;').upper() for w in c['words']))


def merge(chunks, fps=30):
    out = []
    for c in chunks:
        if not c['words']: continue
        if out and key(out[-1]['_c'][-1]) == key(c): out[-1]['_c'].append(c); continue
        out.append({'_c': [c]})
    caps = []
    for g in out:
        cs = g['_c']; best = max(cs, key=lambda c: (sum(c['red']) and 0, len(c['words']), c['f1'] - c['f0']))
        caps.append(dict(f0=cs[0]['f0'], f1=cs[-1]['f1'], words=[[w, bool(r)] for w, r in zip(best['words'], best['red'])], text=' '.join(best['words'])))
    for i, c in enumerate(caps):
        nxt = caps[i + 1]['f0'] if i + 1 < len(caps) else None
        if nxt is not None and c['f1'] > nxt: c['f1'] = nxt
    return caps


def to_scene(caps, fps=30):
    return [dict(t0=round(c['f0'] / fps, 4), t1=round(c['f1'] / fps, 4), text=c['text'], words=c['words']) for c in caps]
