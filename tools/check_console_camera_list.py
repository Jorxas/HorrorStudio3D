"""CONSOLE 2D: the documented list form of `camera.on` must frame, not crash (seconds, no video, no API).

`docs/FORMAT_EPISODE.md` documents the subjects of a shot as a list:

    "camera": {"shot": "dialogue", "on": ["lea", "tom"], "speaker": "lea"}

`render.ConsoleEngine.qc_observe()` already reads that list (`subjects = [on] if isinstance(on, str) else
list(on) ...`), but `scene_at()` asked `if on in samples` — a dict lookup keyed by a list, i.e.
`TypeError: unhashable type: 'list'`. Two delivered demos rendered on the CONSOLE engine died on it:
`demo2_dialogue` and `demo3_groupe`.

What is checked here: the two demos that crashed, the scalar form byte for byte, a single-element list equal to
the scalar, a group framed between its members, `on` naming a place instead of a character, and determinism.
Exit 1 on any failure.

  python tools/check_console_camera_list.py
"""
import os, sys, json, hashlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np

FAIL = []
def check(name, ok, detail=''):
    print(f"{'OK   ' if ok else 'ÉCHEC'} {name}" + (f'  ({detail})' if detail else '')); ok or FAIL.append(name)


def build(demo_id):
    """the episode of a delivered demo, forced onto the CONSOLE 2D engine (the engine under test)"""
    from hstudio import demos
    from hstudio.pipeline import duration_of
    sc = demos.load(demo_id); lines = []
    for i, s in enumerate(sc['script']):                      # fixed timings: no voice, no API, reproducible
        t0 = 0.4 + i * 3.0
        lines.append(dict(tts=s['text'], display=s['text'], text=s['text'], tags=[],
                          dialogue=True, i=i, start=t0, end=t0 + 2.4, segs=[[t0, t0 + 2.4]]))
    ep = dict(demos.episode_of(sc, lines, log=lambda *a: None), style='console')
    return ep, lines, duration_of(ep, lines)


def engine(ep, lines, dur, aspect='9:16'):
    from hstudio.engines.console.render import ConsoleEngine
    return ConsoleEngine(json.loads(json.dumps(ep)), lines, np.zeros(10), dur, aspect)


def sig(im):
    return hashlib.sha1(np.asarray(im.convert('RGB')).tobytes()).hexdigest()[:16]


# ---------------------------------------------------------------- the two demos that crashed

def crashing_demos_checks():
    """the reproduction: every shot of the two demos, both formats, scene + real frame"""
    for demo_id in ('demo2_dialogue', 'demo3_groupe'):
        ep, lines, dur = build(demo_id)
        forms = {k: (sh.get('camera') or {}).get('on') for k, sh in enumerate(ep['shots'])}
        listed = [k for k, v in forms.items() if isinstance(v, list)]
        check(f'{demo_id} : la forme documentée en liste est bien celle de la démo',
              bool(listed), f'{len(listed)}/{len(ep["shots"])} plans, ex. {forms[listed[0]] if listed else None}')
        for aspect in ('9:16', '16:9'):
            eng = engine(ep, lines, dur, aspect)
            err = None
            try:
                for k, sh in enumerate(ep['shots']):
                    t0, t1 = eng.tl.spans[k]
                    eng.scene_at(k, sh, t0 + .1, .1)
            except Exception as e:
                err = f'{type(e).__name__}: {e}'
            check(f'{demo_id}@{aspect} : les {len(ep["shots"])} plans se cadrent sans planter', err is None, err or '')
            eng = engine(ep, lines, dur, aspect)
            err = None
            try:
                for j in range(6): eng.frame(dur * (j + .5) / 6.)
            except Exception as e:
                err = f'{type(e).__name__}: {e}'
            check(f'{demo_id}@{aspect} : 6 vraies images rendues', err is None, err or '')


# ---------------------------------------------------------------- semantics of the list

class Crash:
    """a raised exception, carried as a value so one broken case reports instead of killing the run"""
    def __init__(self, e): self.err = f'{type(e).__name__}: {e}'
    def __eq__(self, o): return False
    def __getitem__(self, i): return float('nan')
    def __repr__(self): return f'<plantage {self.err}>'


def focus_of(ep, lines, dur, k, on):
    """the normalised focus point the 2D camera recenters on, for one `camera.on` value"""
    ep = json.loads(json.dumps(ep))
    if on is _ABSENT: (ep['shots'][k].setdefault('camera', {})).pop('on', None)
    else: ep['shots'][k].setdefault('camera', {})['on'] = on
    try:
        eng = engine(ep, lines, dur)
        t0, t1 = eng.tl.spans[k]
        eng._focus = None
        eng.scene_at(k, ep['shots'][k], t0 + .1, .1)
        return getattr(eng, '_focus', None)
    except Exception as e:
        return Crash(e)

_ABSENT = object()

def is_point(f):
    """a real framing point, not None and not a raised exception"""
    return isinstance(f, tuple) and len(f) == 2 and all(isinstance(v, float) for v in f)


def semantics_checks():
    """a list of subjects frames those subjects; one subject is exactly the historical point"""
    ep, lines, dur = build('demo2_dialogue')
    k = 3                                                     # a two_shot of lea + tom, both acted on stage
    f_lea, f_tom = focus_of(ep, lines, dur, k, 'lea'), focus_of(ep, lines, dur, k, 'tom')
    check('cas scalaire : "on": "lea" cadre toujours un point', is_point(f_lea), str(f_lea))
    check('cas scalaire : deux personnages donnent deux cadrages distincts', f_lea != f_tom, f'{f_lea} vs {f_tom}')

    check('liste d\'un seul sujet ["lea"] == scalaire "lea", au bit près',
          focus_of(ep, lines, dur, k, ['lea']) == f_lea, f'{focus_of(ep, lines, dur, k, ["lea"])} vs {f_lea}')
    check('liste d\'un seul sujet ["tom"] == scalaire "tom", au bit près',
          focus_of(ep, lines, dur, k, ['tom']) == f_tom)

    pair = focus_of(ep, lines, dur, k, ['lea', 'tom'])
    check('liste de deux sujets : un cadrage est choisi', is_point(pair), str(pair))
    lo, hi = sorted((f_lea[0], f_tom[0]))
    check('liste de deux sujets : le cadrage tient les deux dans l\'image (entre les deux)',
          is_point(pair) and lo - 1e-9 <= pair[0] <= hi + 1e-9,
          f'{lo:.4f} <= {pair[0]:.4f} <= {hi:.4f}' if is_point(pair) else str(pair))
    check('liste de deux sujets : ce n\'est ni « le premier » ni « le dernier » de la liste',
          is_point(pair) and pair != f_lea and pair != f_tom, f'{pair}')
    check('liste de deux sujets : l\'ordre d\'écriture ne change pas le cadrage',
          focus_of(ep, lines, dur, k, ['tom', 'lea']) == pair)

    ep3, l3, d3 = build('demo3_groupe')
    k3 = next(k for k, sh in enumerate(ep3['shots']) if len(((sh.get('camera') or {}).get('on')) or []) >= 3)
    on3 = (ep3['shots'][k3].get('camera') or {}).get('on')
    g3 = focus_of(ep3, l3, d3, k3, on3)
    singles = [focus_of(ep3, l3, d3, k3, a) for a in on3]
    singles = [s for s in singles if s is not None and not isinstance(s, Crash)]
    check(f'groupe de {len(on3)} sujets {on3} : un cadrage est choisi', is_point(g3), str(g3))
    check('groupe : le cadrage reste entre les membres du groupe',
          is_point(g3) and len(singles) >= 2 and min(s[0] for s in singles) - 1e-9 <= g3[0] <= max(s[0] for s in singles) + 1e-9,
          f'{[round(s[0], 4) for s in singles]} -> {round(g3[0], 4) if is_point(g3) else g3}')


def camera_choice_checks():
    """`on` may also name a place, a door, an object: that is a camera choice, not a character"""
    ep, lines, dur = build('demo2_dialogue')
    k = 3
    for on, label in ((_ABSENT, 'absent'), (None, 'null'), ('porte', 'un lieu « porte »'),
                      (['porte'], 'une liste de lieux ["porte"]'), ([], 'une liste vide'),
                      (['lea', 'porte'], 'un sujet et un lieu ["lea", "porte"]')):
        f = focus_of(ep, lines, dur, k, on)
        check(f'camera.on = {label} : pas de plantage', not isinstance(f, Crash), f.err if isinstance(f, Crash) else '')
        if label in ('absent', 'null', 'un lieu « porte »', 'une liste de lieux ["porte"]', 'une liste vide'):
            check(f'camera.on = {label} : aucun recadrage imposé (le choix de caméra est gardé)', f is None, str(f))
    f_mixed = focus_of(ep, lines, dur, k, ['lea', 'porte'])
    check('camera.on = ["lea", "porte"] : cadre le personnage connu, ignore le lieu',
          f_mixed == focus_of(ep, lines, dur, k, 'lea'), str(f_mixed))


def qc_agreement_checks():
    """the framing and the quality control must read the same list of subjects"""
    for demo_id in ('demo2_dialogue', 'demo3_groupe'):
        ep, lines, dur = build(demo_id)
        eng = engine(ep, lines, dur)
        bad = None
        for k, sh in enumerate(ep['shots']):
            t0, t1 = eng.tl.spans[k]
            try: r = eng.qc_observe(t0 + .1)
            except Exception as e: bad = f'plan {k}: {type(e).__name__}: {e}'; break
        check(f'{demo_id} : le contrôle qualité lit la même liste de sujets sans planter', bad is None, bad or '')


def determinism_checks():
    ep, lines, dur = build('demo3_groupe')
    try:
        a = [sig(engine(ep, lines, dur).frame(dur * (j + .5) / 4.)) for j in range(4)]
        b = [sig(engine(ep, lines, dur).frame(dur * (j + .5) / 4.)) for j in range(4)]
    except Exception as e:
        check('déterminisme : deux rendus de la même liste donnent les mêmes images', False, f'{type(e).__name__}: {e}'); return
    check('déterminisme : deux rendus de la même liste donnent les mêmes images', a == b, f'{a[0]} vs {b[0]}')


def scalar_identity_checks():
    """the episodes that never crashed must render exactly as before: 96 frame fingerprints"""
    ref_path = os.path.join(ROOT, 'tests', 'baseline_console_camera.json')
    if not os.path.exists(ref_path):
        check('empreintes des démos CONSOLE scalaires : fichier de référence présent', False, ref_path)
        return
    ref = json.load(open(ref_path, encoding='utf-8'))
    for demo_id in ('demo5_console', 'demo10_console_saut', 'demo11_aplat', 'demo12_aplat_ui'):
        ep, lines, dur = build(demo_id)
        for aspect in ('9:16', '16:9'):
            key = f'{demo_id}|{aspect}'
            eng = engine(ep, lines, dur, aspect)
            got = [sig(eng.frame(dur * (j + .5) / 12.)) for j in range(12)]
            want = ref.get(key)
            same = want is not None and got == want
            diff = '' if same else f'{sum(1 for x, y in zip(got, want or []) if x != y)}/12 images diffèrent'
            check(f'{key} : identique au bit près à l\'état d\'avant correction', same, diff)


if __name__ == '__main__':
    crashing_demos_checks(); semantics_checks(); camera_choice_checks()
    qc_agreement_checks(); determinism_checks(); scalar_identity_checks()
    print('\n' + ('Tout est OK' if not FAIL else f'{len(FAIL)} ÉCHEC(S) : ' + ', '.join(FAIL)))
    sys.exit(1 if FAIL else 0)
