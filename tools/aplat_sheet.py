"""Before / after of the CONSOLE 2D art direction: the same episode, the same staging, the same frames,
rendered once in the original style and once in aplats (`"art": "aplat"`).

  python tools/aplat_sheet.py [demo_id] [out.png] [--aspect 9:16] [--bench]

The comparison is honest by construction: only the `art` key differs between the two rows, so every difference
on the sheet comes from the art direction and from nothing else (same shots, same camera, same acting, same
palette of the game screen). `--bench` also measures the cost per frame of both paths on the same shots.
"""
import os, sys, time, json
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw, ImageFont
from hstudio import demos
from hstudio.pipeline import make_engine, duration_of
from hstudio.paths import FONT_MONTSERRAT

def build(demo_id, aspect, art):
    """the engine of this demo with (art='aplat') or without (art=None) the new art direction"""
    sc = demos.load(demo_id)
    lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    env = demos.draft_voice(sc, lines)[1]
    ep = demos.episode_of(sc, lines, log=lambda *a: None)
    lines = demos.lines_with_meta(ep, lines)      # labels and keywords, as the renderer gets them in production
    ep = json.loads(json.dumps(ep))
    if art:
        ep['art'] = art
    else:
        ep.pop('art', None)
    dur = duration_of(ep, lines)
    return make_engine(sc.get('style', 'console'), ep, lines, env, dur, aspect), dur

def shot_times(eng, dur):
    return [t0 + (t1 - t0) * .6 for (t0, t1) in eng.tl.spans]

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    demo_id = args[0] if args else 'demo11_aplat'
    out = args[1] if len(args) > 1 else os.path.join(ROOT, 'docs', 'catalogue', 'console2d_avant_apres.png')
    aspect = '9:16'
    if '--aspect' in sys.argv:
        aspect = sys.argv[sys.argv.index('--aspect') + 1]

    rows = []
    for label, art in (("AVANT — style d'origine (dégradés, grain, vignettage)", None),
                       ('APRÈS — aplats (palette limitée, encre, lumière en formes)', 'aplat')):
        eng, dur = build(demo_id, aspect, art)
        ts = shot_times(eng, dur)
        ims = [eng.frame(t) for t in ts]
        k = 7 if aspect == '9:16' else 9
        rows.append((label, [im.resize((im.size[0] // k, im.size[1] // k), Image.LANCZOS) for im in ims]))

    W, H = rows[0][1][0].size
    pad, head = 12, 34
    sheet = Image.new('RGB', (pad + len(rows[0][1]) * (W + pad), pad + 2 * (head + H + pad)), (16, 16, 22))
    d = ImageDraw.Draw(sheet)
    try: f = ImageFont.truetype(FONT_MONTSERRAT, 20)
    except Exception: f = None
    for r, (title, ims) in enumerate(rows):
        y = pad + r * (head + H + pad)
        d.text((pad, y), title, fill=(236, 232, 220), font=f)
        for i, im in enumerate(ims):
            sheet.paste(im, (pad + i * (W + pad), y + head))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    print(out)

    if '--bench' in sys.argv:
        print(f'\ncoût par image ({demo_id}, une image par plan, caches chauds)')
        for label, art in (('origine', None), ('aplat  ', 'aplat')):
            for asp in ('9:16', '16:9'):
                eng, dur = build(demo_id, asp, art)
                ts = shot_times(eng, dur)
                for t in ts: eng.frame(t)                      # warm the set caches and the fonts
                t0 = time.perf_counter()
                for t in ts: eng.frame(t)
                print(f'  {label} {asp:5s} {(time.perf_counter() - t0) / len(ts) * 1000:7.1f} ms/image')

if __name__ == '__main__':
    main()
