"""End-to-end OFFLINE proof of the story layer: a brief becomes a real rendered frame, on both engines.

    Brief -> story.build(provider='mock') -> Outline
          -> to_script_text() -> hstudio/script.py:parse_script  (the EXISTING script entry)
          -> story.mock_timing()                                  (test stub, NOT the real alignment)
          -> to_episode() -> hstudio/director/validate.py:validate
          -> hstudio/pipeline.py:make_engine -> engine.frame(t)    (the EXISTING renderers)

No API key, no network, no ElevenLabs, no ffmpeg, nothing written outside --out. The story itself comes from the
deterministic MOCK fixture: it proves the plumbing, NOT that an AI wrote a good story.

  python tools/check_story_e2e.py              # checks only
  python tools/check_story_e2e.py --out /tmp/e2e   # also save the frames as PNG to look at them
"""
import os, sys, json, hashlib, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
FAIL = []
def check(name, ok, detail=''):
    print(f"{'OK   ' if ok else 'ÉCHEC'} {name}" + (f'  ({detail})' if detail and not ok else '')); ok or FAIL.append(name)

from hstudio.director import story as ST
from hstudio.director.validate import validate
from hstudio.script import parse_script
from hstudio.pipeline import make_engine

OUT = None
for i, a in enumerate(sys.argv):
    if a == '--out' and i + 1 < len(sys.argv): OUT = sys.argv[i + 1]
if OUT: os.makedirs(OUT, exist_ok=True)


def one(brief, aspect='9:16', tag=''):
    o = ST.build(brief, provider='mock')
    P = o.problems()
    check(f'{tag} : plan cohérent', not P, '; '.join(P[:3]))

    lines = ST.mock_timing(parse_script(o.to_script_text()))
    check(f'{tag} : script -> {len(lines)} lignes chronométrées', len(lines) == len(o.beats) and all('end' in l for l in lines))

    ep = o.to_episode(len(lines))
    vep, W = validate(ep, len(lines), brief.resolve_engine())
    bad = [w for w in W if 'inconnu' in w or 'inconnue' in w]
    check(f'{tag} : validate sans valeur inconnue', not bad, '; '.join(bad[:3]))
    check(f'{tag} : aucune intention caméra/action perdue', not o.check_episode(vep), '; '.join(o.check_episode(vep)[:3]))

    dur = lines[-1]['end'] + 1.5
    eng = make_engine(brief.resolve_engine(), vep, lines, np.zeros(10), dur, aspect)
    # one frame in the middle of the story, one on the first choice line, one on the last line (endcard)
    i_choice = next((i for i, b in enumerate(o.beats) if b.role == 'choice'), 0)
    ts = [lines[len(lines) // 2]['start'] + .2, lines[i_choice]['start'] + .2, lines[-1]['start'] + .2]
    imgs = []
    for k, t in enumerate(ts):
        im = eng.frame(t)
        a = np.asarray(im)
        check(f'{tag} : image {k} rendue', a.ndim == 3 and a.shape[2] >= 3 and a.size > 0, str(a.shape))
        check(f'{tag} : image {k} non vide', int(a.std()) > 2, f'std={a.std():.1f}')
        imgs.append(im)
        if OUT: im.save(os.path.join(OUT, f'{tag.replace("/", "_").replace(" ", "")}_{k}.png'))
    # determinism: the same frame twice gives the same pixels
    again = eng.frame(ts[1])
    check(f'{tag} : rendu déterministe', hashlib.sha1(np.asarray(again).tobytes()).digest() == hashlib.sha1(np.asarray(imgs[1]).tobytes()).digest())
    return o, vep, lines


if __name__ == '__main__':
    cases = [
        (ST.Brief(genre='horror',    duration_s=45, voice_mode='voice',    engine='pixel3d', n_choices=2, seed=3), '9:16', 'pixel3d/horreur/voix/2'),
        (ST.Brief(genre='adventure', duration_s=60, voice_mode='hybrid',   engine='pixel3d', n_choices=3, seed=1), '16:9', 'pixel3d/aventure/hybride/3'),
        (ST.Brief(genre='mystery',   duration_s=45, voice_mode='dialogue', engine='console', n_choices=2, seed=2), '9:16', 'console/mystere/dialogue/2'),
        (ST.Brief(genre='comedy',    duration_s=40, voice_mode='voice',    engine='console', n_choices=3, seed=5), '16:9', 'console/comedie/voix/3'),
    ]
    for br, asp, tag in cases:
        o, vep, lines = one(br, asp, tag)
        if br.n_choices == 3:
            ui = next((s['ui']['choice'] for s in vep['shots'] if (s.get('ui') or {}).get('choice')), {})
            check(f'{tag} : la carte de choix porte bien A, B et C', all(k in ui for k in 'ABC'), str(sorted(ui)))
    # the two engines really produce different images from the same brief
    br = ST.Brief(genre='mystery', duration_s=40, voice_mode='voice', n_choices=2, seed=4)
    hs = []
    for engine in ('pixel3d', 'console'):
        b2 = ST.Brief(**dict(br.to_dict(), engine=engine))
        o = ST.build(b2, provider='mock'); lines = ST.mock_timing(parse_script(o.to_script_text()))
        vep, _ = validate(o.to_episode(len(lines)), len(lines), engine)
        eng = make_engine(engine, vep, lines, np.zeros(10), lines[-1]['end'] + 1.5, '9:16')
        hs.append(hashlib.sha1(np.asarray(eng.frame(lines[1]['start'] + .2)).tobytes()).hexdigest())
    check('même brief, deux moteurs, deux images différentes', hs[0] != hs[1])
    print()
    if OUT: print(f'images écrites dans {OUT}')
    if FAIL: print(f'{len(FAIL)} ÉCHEC(S) : ' + ', '.join(FAIL[:10])); sys.exit(1)
    print('Tout est bon.')
