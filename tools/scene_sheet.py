"""Fast visual check of a scene: a contact sheet of low-resolution frames taken every N seconds (no audio, no video).

  python tools/scene_sheet.py tests/scenes/demo1_walk.json out.png [--aspect 16:9] [--every .5] [--cols 6] [--full]

The scene file is an episode.json; when it has no "lines" timings, each shot lasts "dur" seconds (default 4)."""
import os, sys, json, argparse, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw

def scene_lines(ep):
    """lines.json for a scene file: one silent line per shot, using shot "dur" (seconds) or the "texts" of the shot"""
    if ep.get('_lines'): return ep['_lines']
    out = []; t = 0.
    for i, s in enumerate(ep['shots']):
        d = float(s.get('dur', 4.)); txt = s.get('text', '')
        out.append({'tts': txt or '.', 'display': txt, 'text': txt, 'tags': [], 'dialogue': bool(s.get('speaker')), 'i': i,
                    'start': t + .05, 'end': t + d - .05, 'segs': [[t + .05, t + d - .05]]})
        if s.get('speaker'): ep.setdefault('lines', {})[str(i)] = dict(ep.get('lines', {}).get(str(i), {}), speaker=s['speaker'])
        t += d
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('scene'); ap.add_argument('out'); ap.add_argument('--aspect', default='16:9')
    ap.add_argument('--every', type=float, default=.5); ap.add_argument('--cols', type=int, default=6); ap.add_argument('--full', action='store_true')
    a = ap.parse_args()
    ep = json.load(open(a.scene, encoding='utf-8'))
    if 'script' in ep and 'episode' in ep:                 # a demo scenario (examples/demos/*.json)
        from hstudio.demos import timed_lines
        sc = ep; ep = sc['episode']; ep['style'] = sc.get('style', 'pixel3d'); lines = timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
        if ep.get('series'):
            from hstudio.demos import state_after
            ep['series_state'] = state_after(sc['follows']) if sc.get('follows') else {}
        for i, s_ in enumerate(sc['script']):
            if s_.get('who'): ep.setdefault('lines', {}).setdefault(str(i), {})['speaker'] = s_['who']
    else: lines = scene_lines(ep)
    from hstudio.pipeline import make_engine
    eng = make_engine(ep.get('style', 'pixel3d'), ep, lines, np.zeros(10), lines[-1]['end'] + .1, a.aspect)
    ts = np.arange(0, lines[-1]['end'], a.every); tiles = []
    for t in ts:
        if a.full or ep.get('style') == 'console': im = eng.frame(float(t)).resize((384, 216) if a.aspect == '16:9' else (216, 384))
        else:
            lo = eng.render_lowres(float(t))[0]; im = Image.fromarray(lo)
        ImageDraw.Draw(im).text((4, 2), f'{t:.1f}s', fill=(255, 255, 0)); tiles.append(im)
    w, h = tiles[0].size; c = a.cols; sh = Image.new('RGB', (w * c, h * ((len(tiles) + c - 1) // c)))
    for i, im in enumerate(tiles): sh.paste(im, ((i % c) * w, (i // c) * h))
    sh.save(a.out); print(a.out, len(tiles), 'frames')

if __name__ == '__main__': main()
