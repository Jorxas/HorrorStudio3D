"""Ancien style / PIXEL 3D v2: the same demo rendered twice, with and without the episode key "art".

  python tools/art_sheet.py                               # docs/art_v2/avant_apres_art.png + mesures.json
  python tools/art_sheet.py --demo demo13_art_pixel3d --aspect 16:9 --out out.png
  python tools/art_sheet.py --faces docs/art_v2/visages.png     # the 48x48 face grid alone
  python tools/art_sheet.py --preset voxel_hd_flat        # geometry only, stock image finish

It renders the same seconds of the same scenario twice (the art key removed, then kept), writes a contact sheet
and the measurements that back the comparison: number of boxes per frame, seconds per frame, how many pixels
and how many distinct colours differ. Nothing here claims a verdict: the verdict is a human looking at the sheet.
"""
import os, sys, json, time, argparse
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw, ImageFont
from hstudio import demos
from hstudio.pipeline import make_engine, duration_of
from hstudio.paths import FONT_MONTSERRAT


def build(demo_id, aspect, art):
    """engine for the scenario, with `art` forced into (or removed from) the episode"""
    sc = demos.load(demo_id)
    lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    env = demos.draft_voice(sc, lines)[1]
    ep = demos.episode_of(sc, lines, log=lambda *a: None)
    if art: ep['art'] = art
    else: ep.pop('art', None)
    dur = duration_of(ep, lines)
    return make_engine(sc.get('style', 'pixel3d'), ep, lines, env, dur, aspect), dur


def strip(eng, ts, size):
    """low-res frames (before the x5 upscale and the UI) + per-frame cost"""
    out = []; costs = []
    for t in ts:
        t0 = time.perf_counter()
        img = eng.render_lowres(t)[0]
        costs.append(time.perf_counter() - t0)
        out.append(Image.fromarray(img).resize(size, Image.NEAREST))
    return out, costs


def boxes_at(eng, t):
    """boxes the ray caster sees at time t, under this engine's own art direction"""
    from hstudio.engines.pixel3d.frame import build_frame
    from hstudio.engines.pixel3d import art as A
    A.use(eng.art)
    sc = build_frame(eng.ctx, t)[0]
    return len(sc.boxes) + len(A.decor(sc.boxes, sc.ceil_y))


def face_grid(out_path):
    """every expression of assets.FACE_KINDS, stock 24x24 on top, art v2 48x48 below"""
    from hstudio.engines.pixel3d import assets as A, art
    kinds = A.FACE_KINDS
    cell = 96; cols = 11; rows = (len(kinds) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cell, rows * (2 * cell + 18) + 8), (14, 16, 22))
    d = ImageDraw.Draw(sheet)
    try: fnt = ImageFont.truetype(FONT_MONTSERRAT, 11)
    except Exception: fnt = ImageFont.load_default()
    for i, kind in enumerate(kinds):
        cx = (i % cols) * cell; cy = (i // cols) * (2 * cell + 18) + 4
        old = Image.fromarray(A.face_tex(kind)).convert('RGB').resize((cell - 6, cell - 6), Image.NEAREST)
        new = Image.fromarray(art.face_hd(kind)).convert('RGB').resize((cell - 6, cell - 6), Image.NEAREST)
        sheet.paste(old, (cx + 3, cy)); sheet.paste(new, (cx + 3, cy + cell))
        d.text((cx + 4, cy + 2 * cell - 2), kind, font=fnt, fill=(210, 214, 226))
    sheet.save(out_path)
    return out_path, len(kinds)


def bench(demo_id, aspect, n=5, rounds=3):
    """cost of each feature, one at a time, on the same frames of the same scenario. The configurations are
    interleaved and repeated: measured in blocks, a loaded machine makes whatever runs last look expensive."""
    cfgs = [('ancien style (reference)', None),
            ('figure (corps + cheveux)', {'style': 'voxel_hd', 'face': False, 'decor': False, 'grade': False}),
            ('visage 48x48', {'style': 'voxel_hd', 'figure': False, 'decor': False, 'grade': False}),
            ('decor (plinthes/corniches)', {'style': 'voxel_hd', 'figure': False, 'face': False, 'grade': False}),
            ('etalonnage', {'style': 'voxel_hd', 'figure': False, 'face': False, 'decor': False}),
            ('voxel_hd (tout)', 'voxel_hd')]
    engines = []
    for label, pre in cfgs:
        eng, dur = build(demo_id, aspect, pre)
        ts = [round(dur * (k + .5) / n, 2) for k in range(n)]
        for t in ts: eng.render_lowres(t)                           # warm every cache before any measurement
        engines.append((label, eng, ts))
    costs = {label: [] for label, _, _ in engines}
    for _ in range(rounds):
        for label, eng, ts in engines:
            for t in ts:
                t0 = time.perf_counter(); eng.render_lowres(t); costs[label].append(time.perf_counter() - t0)
    ref = float(np.median(costs[cfgs[0][0]]))
    return [dict(config=label, seconds_per_frame=round(float(np.median(costs[label])), 3),
                 vs_reference=round(float(np.median(costs[label])) / ref, 2),
                 spread=round(float(np.percentile(costs[label], 90) - np.percentile(costs[label], 10)), 3))
            for label, _, _ in engines]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--demo', default='demo13_art_pixel3d')
    ap.add_argument('--aspect', default='16:9')
    ap.add_argument('--preset', default='voxel_hd')
    ap.add_argument('--out', default=os.path.join(ROOT, 'docs', 'art_v2', 'avant_apres_art.png'))
    ap.add_argument('--measures', default=os.path.join(ROOT, 'docs', 'art_v2', 'mesures.json'))
    ap.add_argument('--faces', default='')
    ap.add_argument('--bench', action='store_true')
    ap.add_argument('--n', type=int, default=6)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    if a.bench:
        rows = bench(a.demo, a.aspect)
        for r in rows: print(f"{r['config']:30s} {r['seconds_per_frame']:>7.3f} s/image   x{r['vs_reference']}   (p90-p10 {r['spread']:.3f})")
        json.dump(rows, open(os.path.join(ROOT, 'docs', 'art_v2', 'bench.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        return
    if a.faces:
        os.makedirs(os.path.dirname(os.path.abspath(a.faces)), exist_ok=True)
        p, n = face_grid(a.faces); print(f'{n} expressions -> {p}'); return
    eng_old, dur = build(a.demo, a.aspect, None)
    eng_new, _ = build(a.demo, a.aspect, a.preset)
    ts = [round(dur * (k + .5) / a.n, 2) for k in range(a.n)]
    W, H = (480, 270) if a.aspect == '16:9' else (270, 480)
    old, c_old = strip(eng_old, ts, (W, H))
    new, c_new = strip(eng_new, ts, (W, H))
    diffs = []
    for i, t in enumerate(ts):
        o = np.asarray(old[i], np.int16); n_ = np.asarray(new[i], np.int16)
        changed = float((np.abs(o - n_).max(-1) > 6).mean())
        co = len(np.unique(o.reshape(-1, 3), axis=0)); cn = len(np.unique(n_.reshape(-1, 3), axis=0))
        diffs.append(dict(t=t, pixels_changed=round(changed, 4), colours_before=co, colours_after=cn))
    boxes = dict(before=boxes_at(eng_old, ts[len(ts) // 2]), after=boxes_at(eng_new, ts[len(ts) // 2]))
    pad, head = 10, 40
    sheet = Image.new('RGB', (pad + len(ts) * (W + pad), 2 * (head + H) + pad), (14, 16, 22))
    d = ImageDraw.Draw(sheet)
    try: fnt = ImageFont.truetype(FONT_MONTSERRAT, 18)
    except Exception: fnt = ImageFont.load_default()
    rows = [("ANCIEN STYLE (rendu livré, sans la clé \"art\")", old),
            (f"PIXEL 3D v2 — prototype opt-in (\"art\": \"{a.preset}\")", new)]
    for r, (label, imgs) in enumerate(rows):
        y = pad + r * (head + H)
        d.text((pad, y + 8), label, font=fnt, fill=(232, 228, 220))
        for c, im in enumerate(imgs): sheet.paste(im, (pad + c * (W + pad), y + head))
    sheet.save(a.out)
    meas = dict(demo=a.demo, aspect=a.aspect, preset=a.preset, times=ts, boxes=boxes,
                seconds_per_frame=dict(before=round(float(np.mean(c_old)), 3), after=round(float(np.mean(c_new)), 3)),
                frames=diffs)
    os.makedirs(os.path.dirname(os.path.abspath(a.measures)), exist_ok=True)
    json.dump(meas, open(a.measures, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(json.dumps(meas, indent=1, ensure_ascii=False))
    print('planche ->', a.out)


if __name__ == '__main__':
    main()
