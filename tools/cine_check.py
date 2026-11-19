"""Measure how readable the faces are in an acted scene, and save the frames of the worst moments.

  python tools/cine_check.py examples/demos/demo6_continuite.json out/ [--aspect 9:16] [--every .25] [--save 3]

For every sample it computes, for each character the camera is on, the angle between the direction his face looks at
(body heading + head yaw, the axis the front of the cubic head is on) and the direction of the camera. A close shot
whose angle goes beyond ~60 degrees shows the flat side of the head instead of the face: that is what this measures.
Prints one line per shot (kind, worst and mean angle) and a verdict, then saves a PNG of the worst moments.
No audio, no video, no API: it builds the engine exactly like tools/scene_sheet.py."""
import os, sys, json, math, argparse, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)        # HERE: scene_sheet.scene_lines, for plain scene files

CLOSE = ('close', 'extreme_close', 'medium', 'medium_full', 'ots')
LIMIT = {'extreme_close': 50., 'close': 60., 'medium': 68., 'medium_full': 75., 'ots': 60.}


def wrap(a): return (a + math.pi) % (2 * math.pi) - math.pi


def build(path, aspect, face_track=False):
    ep = json.load(open(path, encoding='utf-8'))
    if 'script' in ep and 'episode' in ep:
        from hstudio.demos import timed_lines, state_after
        sc = ep; ep = sc['episode']; ep['style'] = sc.get('style', 'pixel3d')
        lines = timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
        if ep.get('series'): ep['series_state'] = state_after(sc['follows']) if sc.get('follows') else {}
        for i, s_ in enumerate(sc['script']):
            if s_.get('who'): ep.setdefault('lines', {}).setdefault(str(i), {})['speaker'] = s_['who']
    else:
        from scene_sheet import scene_lines
        lines = scene_lines(ep)
    if face_track: ep['camera_face_track'] = True        # the opt-in, without touching the demo file
    from hstudio.pipeline import make_engine
    return ep, lines, make_engine(ep.get('style', 'pixel3d'), ep, lines, np.zeros(10), lines[-1]['end'] + .1, aspect)


def measure(eng, ep, lines, every=.25):
    """-> (samples, per_shot) using the engine's own quality-control observations: only the characters the camera
    really frames count (in 9:16 a "dialogue" becomes a clean single: the partner is not a subject)."""
    ctx = eng.ctx
    out = []; end = ctx.tl.spans[-1][1]
    t = 0.
    while t < end:
        ob = eng.qc_observe(t)
        if ob:
            kind = (ob.get('cam') or {}).get('shot') or 'medium'
            for a in ob.get('subjects') or []:
                p_ = (ob.get('people') or {}).get(a)
                if p_ is None or p_.get('face_angle') is None: continue
                out.append(dict(t=round(t, 2), shot=ob['shot'], kind=kind, who=a, angle=p_['face_angle'],
                                head_share=p_.get('head_share'),
                                in_frame=bool(p_['in_frame']), visible=bool(p_['visible']),
                                talking=bool(p_.get('talking')), limit=LIMIT.get(kind)))
        t += every
    per = {}
    for s_ in out:
        p_ = per.setdefault(s_['shot'], dict(kind=s_['kind'], n=0, bad=0, out=0, hid=0, worst=0., sum=0., worst_t=None, worst_who=None))
        p_['n'] += 1; p_['sum'] += s_['angle']
        if s_.get('head_share'): p_['hs'] = max(p_.get('hs', 0.), s_['head_share'])
        p_['out'] += not s_['in_frame']; p_['hid'] += s_['in_frame'] and not s_['visible']
        if s_['angle'] > p_['worst']: p_['worst'] = s_['angle']; p_['worst_t'] = s_['t']; p_['worst_who'] = s_['who']
        if s_['limit'] is not None and s_['angle'] > s_['limit']: p_['bad'] += 1
    return out, per


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('scene'); ap.add_argument('out')
    ap.add_argument('--aspect', default='16:9'); ap.add_argument('--every', type=float, default=.25)
    ap.add_argument('--save', type=int, default=3); ap.add_argument('--at', default='')
    ap.add_argument('--sheet', type=float, default=0., help='also save a contact sheet, one low-res frame every N seconds')
    ap.add_argument('--face-track', action='store_true', help='switch the face-aware framing on (episode key camera_face_track)')
    a = ap.parse_args()
    ep, lines, eng = build(a.scene, a.aspect, a.face_track)
    samples, per = measure(eng, ep, lines, a.every)
    close_n = sum(p['n'] for p in per.values() if p['kind'] in CLOSE)
    close_bad = sum(p['bad'] for p in per.values() if p['kind'] in CLOSE)
    print(f"{a.scene}  {a.aspect}  {len(samples)} samples on {len(per)} acted shots")
    for k in sorted(per):
        p = per[k]
        flag = '!!' if p['bad'] else 'OK'
        lim = LIMIT.get(p['kind'])
        print(f"  {flag} shot {k:2d} {p['kind']:13s} worst {p['worst']:5.1f}deg at {p['worst_t']}s ({p.get('worst_who')})"
              f"  mean {p['sum'] / p['n']:5.1f}deg  beyond {'-' if lim is None else int(lim)}: {p['bad']}/{p['n']}"
              f"  out {p['out']} hidden {p['hid']}  head takes {100 * p.get('hs', 0.):.0f}% of the width")
    print(f"  close/medium samples past the readable cone: {close_bad}/{close_n}"
          f" = {0. if not close_n else 100. * close_bad / close_n:.1f} %")
    worst = sorted([s for s in samples if s['limit'] is not None], key=lambda s: -s['angle'])[:a.save]
    times = [float(x) for x in a.at.split(',') if x.strip()] or [s['t'] for s in worst]
    os.makedirs(a.out, exist_ok=True)
    tag = a.aspect.replace(':', '-')
    for t in times:
        im = eng.frame(float(t))
        p = os.path.join(a.out, f'{os.path.basename(a.scene).split(".")[0]}_{tag}_{t:.2f}s.png')
        im.save(p); print('  saved', p)
    if a.sheet > 0:                                        # contact sheet: the whole scene at a glance, no ffmpeg needed
        from PIL import Image, ImageDraw
        ts = [i * a.sheet for i in range(int(lines[-1]['end'] / a.sheet) + 1)]
        tiles = []
        for t in ts:
            im = Image.fromarray(eng.render_lowres(float(t))[0])
            ImageDraw.Draw(im).text((4, 2), f'{t:.1f}s', fill=(255, 255, 0)); tiles.append(im)
        w, h = tiles[0].size; cols = 8
        sh = Image.new('RGB', (w * cols, h * ((len(tiles) + cols - 1) // cols)))
        for i, im in enumerate(tiles): sh.paste(im, ((i % cols) * w, (i // cols) * h))
        sp = os.path.join(a.out, f'sheet_{os.path.basename(a.scene).split(".")[0]}_{tag}.png')
        sh.save(sp); print('  saved', sp, len(tiles), 'frames')
    json.dump(dict(aspect=a.aspect, per_shot={str(k): v for k, v in per.items()}, samples=samples),
              open(os.path.join(a.out, f'cine_check_{tag}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__': main()
