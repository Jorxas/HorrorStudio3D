"""Regression guard for the CONSOLE 2D "aplats" art direction (V3, opt-in).

  python tools/regress_aplat.py record   # store the fingerprints in tests/baseline_aplat_local.json
  python tools/regress_aplat.py check    # compare the current code with it (exit 1 on any difference)

tools/regress.py covers the v1 episodes and tools/regress_v2.py the six v2 demos: both of them prove the new
art direction changed *nothing* for an episode that did not ask for it. This third guard is the other half:
it proves the new style itself is deterministic and does not drift by accident.

It fingerprints the two demos of the style: demo11_aplat crosses the image in one pass (the four palettes, the
redrawn sets, the face close-up, the silhouette, a walk, a sit and a react) and demo12_aplat_ui crosses the
interface drawn on top of it (HUD cartouche, subtitle plate with its speaker tab and keywords, rule card in
full frame and as an overlay, countdown, the three states of the choice cards, end card). The console engine
draws with Pillow, whose antialiasing changes between versions, so record the baseline on the machine that
checks it.
"""
import os, sys, json, hashlib, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
BASE = os.path.join(ROOT, 'tests', 'baseline_aplat_local.json')
DEMOS = ['demo11_aplat', 'demo12_aplat_ui']
SAMPLES = {'demo11_aplat': 9, 'demo12_aplat_ui': 10}   # one sample per shot of each demo

def engine(demo_id, aspect):
    from hstudio import demos
    from hstudio.pipeline import make_engine, duration_of
    sc = demos.load(demo_id)
    lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    env = demos.draft_voice(sc, lines)[1]
    ep = demos.episode_of(sc, lines, log=lambda *a: None)
    assert ep.get('art') == 'aplat', f'{demo_id}: the "art" key did not survive validation'
    lines = demos.lines_with_meta(ep, lines)      # labels and keywords, as the renderer gets them in production
    return make_engine(sc.get('style', 'console'), ep, lines, env, duration_of(ep, lines), aspect), duration_of(ep, lines)

def fingerprints():
    out = {}
    for d in DEMOS:
        for aspect in ('9:16', '16:9'):
            eng, dur = engine(d, aspect)
            n = SAMPLES[d]
            ts = [round(dur * (k + .5) / n, 2) for k in range(n)]
            out[f'{d}@{aspect}'] = [hashlib.sha1(np.asarray(eng.frame(t)).tobytes()).hexdigest()[:16] for t in ts]
            print(f'{d}@{aspect}', flush=True)
    return out

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if len(sys.argv) > 2: BASE = sys.argv[2] if os.path.isabs(sys.argv[2]) else os.path.join(ROOT, sys.argv[2])
    cur = fingerprints()
    if mode == 'record':
        json.dump(cur, open(BASE, 'w'), indent=1); print('baseline recorded:', sum(len(v) for v in cur.values()), 'frames')
    else:
        ref = json.load(open(BASE)); bad = 0
        for k, hs in ref.items():
            diff = [i for i, (a, b) in enumerate(zip(hs, cur.get(k, []))) if a != b]
            print(f'{k:28s} {"OK" if not diff else "DIFF at " + str(diff)}'); bad += len(diff)
        sys.exit(1 if bad else 0)
