"""Regression guard: frame fingerprints of reference episodes, both formats.

  python tools/regress.py record    # store the fingerprints in tests/baseline.json (only on purpose!)
  python tools/regress.py check     # compare the current code with tests/baseline.json (exit 1 on any difference)
  python tools/regress.py check tests/baseline_local.json    # another baseline file (e.g. one machine's own)

An episode that does not use a new feature must render bit for bit as before.
The console engine draws with Pillow, whose antialiasing changes between versions: on a machine with another
Pillow, record a local baseline from the untouched code (record tests/baseline_local.json) and check against it."""
import os, sys, json, hashlib, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
FIX = os.path.join(ROOT, 'tests', 'fixtures'); BASE = os.path.join(ROOT, 'tests', 'baseline.json')
# fixture -> times (seconds) to fingerprint
CASES = {'partie4': [1.2, 9.5, 22.0, 31.0, 44.4, 58.0, 71.3, 86.0, 99.9, 112.0, 126.5, 141.5],
         'console_demo': [1.0, 12.0, 25.0, 40.0, 55.0, 70.0, 88.0, 104.0, 121.0, 139.0],
         'monde': [1.5, 6.0, 12.0, 17.5, 23.0, 29.0, 35.0, 41.0, 46.0]}

def load(name):
    d = os.path.join(FIX, name)
    ep = json.load(open(os.path.join(d, 'episode.json'), encoding='utf-8')); lines = json.load(open(os.path.join(d, 'lines.json'), encoding='utf-8'))
    env = np.load(os.path.join(d, 'env.npy')) if os.path.exists(os.path.join(d, 'env.npy')) else np.zeros(10)
    return ep, lines, env

def engine(name, aspect):
    from hstudio.pipeline import make_engine
    ep, lines, env = load(name)
    return make_engine(ep.get('style', 'pixel3d'), ep, lines, env, lines[-1]['end'] + 1.5, aspect)

def fingerprints():
    out = {}
    for name, ts in CASES.items():
        for aspect in ('9:16', '16:9'):
            eng = engine(name, aspect)
            out[f'{name}@{aspect}'] = [hashlib.sha1(np.asarray(eng.frame(t)).tobytes()).hexdigest()[:16] for t in ts]
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
            print(f'{k:22s} {"OK" if not diff else "DIFF at " + str(diff)}'); bad += len(diff)
        sys.exit(1 if bad else 0)
