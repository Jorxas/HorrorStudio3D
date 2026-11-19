"""CONSOLE 2D: contact sheet of the faces, rendered by the real engine (no zoom, 1:1 crops).

Builds a real console episode (engine_version 2, shared acting layer), renders real frames with
ConsoleEngine.frame() and cuts the head out at native resolution. One tile per expression, so a
change in flat.py's face() is visible side by side.

  python tools/console_face_sheet.py out.png [--expr a,b,c] [--aspect 9:16] [--char noah]
  python tools/console_face_sheet.py out.png --talk        # the same expression over a talking beat
"""
import os, sys, json, argparse
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw, ImageFont
from hstudio.pipeline import make_engine
from hstudio.paths import FONT_MONTSERRAT

EXPR = ['neutral', 'tired', 'suspicious', 'thinking', 'nervous', 'scared', 'shocked', 'surprised',
        'sad', 'crying', 'happy', 'joy', 'smirk', 'determined', 'angry', 'confused', 'bored', 'calm',
        'proud', 'excited', 'cool', 'urgent', 'smile_sad', 'closed']
TILE = (300, 300)


def line(i, t0, t1, dialogue=False):
    return {'tts': '.', 'display': '', 'text': '', 'tags': [], 'dialogue': dialogue, 'i': i,
            'start': t0, 'end': t1, 'segs': [[t0, t1]]}


def episode(exprs, char='noah', talk=False, faces='flat'):
    """one shot per expression: the character sits on the bed of the console bedroom, medium shot"""
    shots, lines = [], []
    for i, ex in enumerate(exprs):
        t0 = .4 + i * 2.0
        lines.append(line(i, t0, t0 + 1.6, dialogue=talk))
        shots.append({'lines': [i, i], 'scene': {'type': 'room', 'console_on_bed': False},
                      'actors': [{'id': char, 'at': [0., 1.1], 'facing': 'camera', 'face': ex}],
                      'camera': {'shot': 'medium', 'on': char},
                      'ui': {'hud': False, 'subs': 'off'}})
    ep = {'style': 'console', 'engine_version': 2, 'cast': {char: {'ref': char}},
          'hud': {}, 'lines': {}, 'shots': shots, 'faces': faces}
    if talk:
        ep['names'] = {char: char.upper()}
    return ep, lines


def head_box(eng, k, t, char, pad=1.35):
    """pixel box of the head on the canvas, from the stage itself (no guessing, no zoom)"""
    from hstudio.acting import rig
    sh = eng.ep['shots'][k]; sc = sh.get('scene') or {}
    stg = eng.stage(sc.get('type', 'room'), sc)
    smp = eng.acting.shots[k].sample(t)[char]
    sk = rig.solve(smp['rig']); j = sk.joints['head']
    px, py, s = stg.to_px(smp['x'] + j[0], float(j[1]) + float(smp.get('y', 0.)), smp['z'] + j[2])
    r = .2 * s * pad
    return px, py, r, stg


def crop_head(eng, k, t, char, size=TILE):
    """1:1 crop of the head out of the real rendered frame (canvas -> framed image)"""
    im = eng.frame(t).convert('RGB')
    px, py, r, stg = head_box(eng, k, t, char)
    # frame() crops the oversized canvas down to (W, H): camera() leaves its box on the engine
    bx0, by0, bx1, by1 = getattr(eng, 'last_box', (0, 0, stg.CW, stg.CH))
    fx = (px - bx0) * eng.W / (bx1 - bx0); fy = (py - by0) * eng.H / (by1 - by0)
    w, h = size
    box = (int(fx - w / 2), int(fy - h / 2), int(fx - w / 2) + w, int(fy - h / 2) + h)
    out = Image.new('RGB', size, (10, 12, 26))
    out.paste(im.crop(box))
    return out


def sheet(exprs, out, char='noah', aspect='9:16', talk=False, cols=6, title='', faces='flat'):
    ep, lines = episode(exprs, char, talk, faces)
    dur = lines[-1]['end'] + 1.2
    eng = make_engine('console', json.loads(json.dumps(ep)), lines, np.zeros(10), dur, aspect)
    tiles = []
    for i, ex in enumerate(exprs):
        t0, t1 = eng.tl.spans[i]
        t = eyes_open(eng, i, t0 + (t1 - t0) * (.55 if not talk else .5), char, ex)
        tiles.append((ex, crop_head(eng, i, t, char)))
    return paste_sheet(tiles, out, cols, title)


def eyes_open(eng, k, t, char, expr):
    """nudge the sample time so the contact sheet does not catch the character mid-blink"""
    try:
        from hstudio.engines.console import expression as X
    except Exception:
        return t
    smp = eng.acting.shots[k].sample(t)[char]
    seed = float((smp.get('rig') or {}).get('seed', 0.))
    best, best_b = t, 2.
    for j in range(13):
        tt = t + (j - 6) * .035
        b = X.face_params(expr, t=tt, seed=seed)['blink']
        if b < best_b: best, best_b = tt, b
        if b <= 0.: break
    return best


def paste_sheet(tiles, out, cols=6, title=''):
    w, h = TILE; pad = 8; lab = 26
    rows = (len(tiles) + cols - 1) // cols
    top = 40 if title else 0
    sh = Image.new('RGB', (pad + cols * (w + pad), top + pad + rows * (h + lab + pad)), (14, 16, 24))
    d = ImageDraw.Draw(sh)
    try:
        f = ImageFont.truetype(FONT_MONTSERRAT, 18); ft = ImageFont.truetype(FONT_MONTSERRAT, 26)
    except Exception:
        f = ft = None
    if title: d.text((pad, 10), title, fill=(236, 232, 220), font=ft)
    for i, (name, im) in enumerate(tiles):
        cx, cy = i % cols, i // cols
        x = pad + cx * (w + pad); y = top + pad + cy * (h + lab + pad)
        sh.paste(im, (x, y))
        d.text((x + 2, y + h + 4), name, fill=(190, 196, 214), font=f)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sh.save(out); print(out)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out', nargs='?', default=os.path.join(ROOT, 'docs', 'proofs', 'console2d', 'faces.png'))
    ap.add_argument('--expr', default=','.join(EXPR))
    ap.add_argument('--aspect', default='9:16')
    ap.add_argument('--char', default='noah')
    ap.add_argument('--talk', action='store_true')
    ap.add_argument('--cols', type=int, default=6)
    ap.add_argument('--title', default='')
    ap.add_argument('--faces', default='flat', choices=('flat', 'expressive'))
    a = ap.parse_args()
    sheet([e for e in a.expr.split(',') if e], a.out, a.char, a.aspect, a.talk, a.cols, a.title, a.faces)
