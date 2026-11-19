"""Regression guard for the v2 acting layer: frame fingerprints of the six v2 demos, both formats.

  python tools/regress_v2.py record   # store the fingerprints in tests/baseline_v2_local.json (only on purpose!)
  python tools/regress_v2.py check    # compare the current code with it (exit 1 on any difference)

tools/regress.py only covers v1 episodes; this one covers the shots played by the shared acting layer (skeleton,
régie, cinematographer). The episodes are built exactly as `python -m hstudio demo` builds them (draft voice
envelope, validation), nothing is written in projects/. The console demo draws with Pillow: record the baseline
on the machine that checks it."""
import os, sys, json, hashlib, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
BASE = os.path.join(ROOT, 'tests', 'baseline_v2_local.json')
DEMOS = ['demo1_mouvement', 'demo2_dialogue', 'demo3_groupe', 'demo4_tension', 'demo5_console', 'demo6_continuite']
SAMPLES = 6

def engine(demo_id, aspect):
    from hstudio import demos
    from hstudio.pipeline import make_engine, duration_of
    sc = demos.load(demo_id)
    lines = demos.timed_lines(sc['script'], float(sc.get('gap', .3)), float(sc.get('lead', .4)))
    env = demos.draft_voice(sc, lines)[1]
    ep = demos.episode_of(sc, lines, log=lambda *a: None)
    dur = duration_of(ep, lines)
    return make_engine(sc.get('style', 'pixel3d'), ep, lines, env, dur, aspect), dur

def fingerprints():
    out = {}
    for d in DEMOS:
        for aspect in ('9:16', '16:9'):
            eng, dur = engine(d, aspect)
            ts = [round(dur * (k + .5) / SAMPLES, 2) for k in range(SAMPLES)]
            out[f'{d}@{aspect}'] = [hashlib.sha1(np.asarray(eng.frame(t)).tobytes()).hexdigest()[:16] for t in ts]
            print(f'{d}@{aspect}', flush=True)
    return out

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if len(sys.argv) > 2: BASE = os.path.join(ROOT, sys.argv[2]) if not os.path.isabs(sys.argv[2]) else sys.argv[2]
    cur = fingerprints()
    if mode == 'record':
        json.dump(cur, open(BASE, 'w'), indent=1); print('baseline recorded:', sum(len(v) for v in cur.values()), 'frames')
    else:
        ref = json.load(open(BASE)); bad = 0
        for k, hs in ref.items():
            diff = [i for i, (a, b) in enumerate(zip(hs, cur.get(k, []))) if a != b]
            print(f'{k:28s} {"OK" if not diff else "DIFF at " + str(diff)}'); bad += len(diff)
        sys.exit(1 if bad else 0)
