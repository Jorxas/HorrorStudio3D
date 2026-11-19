"""Quick checks of the CONSOLE 2D expressivity (seconds, no video, no API): opt-in off by default,
determinism, one readable face per expression, eyelids, gaze, speaking mouth, flat aplats.
Exit 1 on any failure.

  python tools/check_console2d.py"""
import os, sys, json, hashlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
from PIL import Image, ImageDraw

FAIL = []
def check(name, ok, detail=''):
    print(f"{'OK   ' if ok else 'ÉCHEC'} {name}" + (f'  ({detail})' if detail and not ok else '')); ok or FAIL.append(name)

SKIN = (224, 172, 136); HAIR = (24, 26, 46)
R = 90


def tile(expr, t=.0, seed=.21, talking=False, gaze=(0., 0.), persona=None, size=240):
    """one face drawn by the real drawing code, on a plain skin background"""
    from hstudio.engines.console import expression as X
    im = Image.new('RGB', (size, size), SKIN)
    d = ImageDraw.Draw(im)
    p = X.face_params(expr, t=t, seed=seed, talking=talking, gaze=gaze, persona=persona)
    X.draw_face(d, size / 2, size / 2, R, p, SKIN, HAIR)
    return im


def sig(im): return hashlib.sha1(np.asarray(im).tobytes()).hexdigest()[:16]


def opt_in_checks():
    """nothing moves unless it is asked for"""
    from hstudio.engines.console import flat
    from hstudio.acting import rig
    sample = dict(x=0., z=1., y=0., heading=0., face='tired', talking=False, blink=False,
                  rig=dict(t=1., seed=.3, head=(0., 0.)), gaze=None)
    outs = {}
    for look in (None, {'faces': 'flat'}, {'faces': 'expressive'}):
        im = Image.new('RGB', (240, 240), SKIN); d = ImageDraw.Draw(im)
        flat.face(d, 120, 120, R, sample, 1., look, SKIN, HAIR)
        outs[str(look)] = sig(im)
    check('figure : look=None et faces=flat dessinent le même visage historique',
          outs['None'] == outs["{'faces': 'flat'}"])
    check('figure : faces=expressive change vraiment le visage',
          outs['None'] != outs["{'faces': 'expressive'}"])

    from hstudio.engines.console.render import ConsoleEngine
    lines = [{'tts': 'il est derriere la porte', 'display': 'Il est derrière la porte.',
              'text': 'Il est derrière la porte.', 'tags': [], 'dialogue': True, 'i': 0,
              'start': .2, 'end': 2.0, 'segs': [[.2, 2.0]]}]
    base = {'style': 'console', 'engine_version': 2, 'hud': {}, 'lines': {},
            'shots': [{'lines': [0, 0], 'scene': {'type': 'face', 'expression': 'scared'},
                       'camera': {'move': 'drift'}, 'ui': {'hud': False, 'subs': 'off'}}]}
    e0 = ConsoleEngine(json.loads(json.dumps(base)), lines, np.zeros(10), 3.2, '9:16')
    e1 = ConsoleEngine(dict(json.loads(json.dumps(base)), faces='expressive'), lines, np.zeros(10), 3.2, '9:16')
    check('épisode : "faces" absent => flat', e0.faces == 'flat')
    check('épisode : "faces": "expressive" => le gros plan change',
          sig(e0.frame(1.0)) != sig(e1.frame(1.0)))
    sc = e1.scene_at(0, e1.ep['shots'][0], 1.0, .8)
    check('gros plan : l\'opt-in descend dans la scène', sc.get('faces') == 'expressive')
    check('gros plan : la parole suit les répliques', sc.get('_talk') is True)
    sc0 = e0.scene_at(0, e0.ep['shots'][0], 1.0, .8)
    check('gros plan : par défaut rien n\'est injecté',
          sc0.get('faces') == 'flat' and '_talk' not in sc0)


def determinism_checks():
    from hstudio.engines.console import expression as X
    a = X.face_params('scared', t=3.3, seed=.4, talking=True, gaze=(.2, -.1))
    b = X.face_params('scared', t=3.3, seed=.4, talking=True, gaze=(.2, -.1))
    check('déterminisme : mêmes entrées, mêmes paramètres', a == b)
    check('déterminisme : même image deux fois', sig(tile('scared', 3.3)) == sig(tile('scared', 3.3)))
    s1 = [X.face_params('neutral', t=i * .1, seed=.11)['blink'] for i in range(400)]
    s2 = [X.face_params('neutral', t=i * .1, seed=.73)['blink'] for i in range(400)]
    check('identités : deux personnages ne clignent pas ensemble', s1 != s2)


def expression_checks():
    from hstudio.engines.console import expression as X
    names = ['neutral', 'tired', 'suspicious', 'thinking', 'nervous', 'scared', 'shocked',
             'sad', 'crying', 'happy', 'joy', 'smirk', 'determined', 'angry', 'confused',
             'bored', 'calm', 'proud', 'excited', 'cool', 'urgent', 'smile_sad', 'closed']
    sigs = {n: sig(tile(n, t=.0)) for n in names}
    dup = [n for n in names if list(sigs.values()).count(sigs[n]) > 1]
    check(f'{len(names)} expressions, {len(set(sigs.values()))} visages distincts', not dup, ', '.join(dup))
    # the three that used to collapse into the same dead face
    check('tired, suspicious et neutral ne sont plus le même visage',
          len({sigs['neutral'], sigs['tired'], sigs['suspicious']}) == 3)
    # the historical face collapses 24 expression names onto 10 drawings; this one must not
    from hstudio.engines.console import flat
    def flat_sig(expr, faces):
        im = Image.new('RGB', (240, 240), SKIN); d = ImageDraw.Draw(im)
        smp = dict(x=0., z=1., y=0., heading=0., face=expr, talking=False, blink=False,
                   rig=dict(t=0., seed=.21, head=(0., 0.)), gaze=None)
        flat.face(d, 120, 120, R, smp, 0., {'faces': faces}, SKIN, HAIR)
        return sig(im)
    full = names + ['surprised', 'wide']
    n_flat = len({flat_sig(e, 'flat') for e in full})
    n_exp = len({flat_sig(e, 'expressive') for e in full})
    check(f'figures : {n_flat} dessins pour {len(full)} expressions avant, {n_exp} après',
          n_exp == len(full) and n_exp > n_flat, f'{n_exp}/{len(full)}')
    for bad in ('creature', 'robot', 'zzz_inconnu'):
        try:
            tile(bad); ok = True
        except Exception as e:
            ok = False
        check(f'expression inconnue « {bad} » : repli neutre sans planter', ok)
    check('alias : worried -> nervous', X.ALIAS.get('worried') == 'nervous')


def eye_checks():
    from hstudio.engines.console import expression as X
    # blink: the eye closes, but stays open most of the time
    vals = [X.face_params('neutral', t=i * .02, seed=.37)['blink'] for i in range(3000)]
    closed = sum(1 for v in vals if v > .8)
    check('clignement : la paupière se ferme vraiment', closed > 5, f'{closed} images fermées')
    check('clignement : l\'oeil reste ouvert la plupart du temps',
          sum(1 for v in vals if v < .05) / len(vals) > .9)
    # gaze really moves the pupils
    left = tile('neutral', gaze=(-.9, 0.)); right = tile('neutral', gaze=(.9, 0.))
    check('regard : les pupilles suivent la cible', sig(left) != sig(right))
    def pupil_x(im):                                          # centre of mass of the dark pixels of the eyes
        a = 255. - np.asarray(im.convert('L'), float)
        band = a[int(.40 * a.shape[0]):int(.56 * a.shape[0])]
        band = np.where(band > 90, band, 0.)
        return float((band * np.arange(band.shape[1])).sum() / max(1e-6, band.sum()))
    check('regard : le décalage est du bon côté', pupil_x(left) < pupil_x(right) - 1.,
          f'{pupil_x(left):.1f} vs {pupil_x(right):.1f}')
    # the brows stay in their band for every expression
    bad = []
    for n in list(X.EXPRESSIONS):
        for t in (0., 1.7, 4.1):
            p = X.face_params(n, t=t, seed=.5)
            if not (-.6 <= p['brow_y'] <= .6 and -.7 <= p['brow_in'] <= .7): bad.append(n)
    check('sourcils : paramètres bornés sur toutes les expressions', not bad, ', '.join(sorted(set(bad))))


def talk_checks():
    sigs = {sig(tile('neutral', t=i * .07, talking=True)) for i in range(28)}
    check('parole : la bouche bouge pendant la réplique', len(sigs) > 18, f'{len(sigs)} formes sur 28')
    still = {sig(tile('neutral', t=i * .07, talking=False)) for i in range(28)}
    check('silence : la bouche bouge beaucoup moins qu\'en parlant', len(still) < len(sigs))


def flat_checks():
    """the console look must stay flat: aplats, no gradient on the face"""
    for n in ('neutral', 'scared', 'joy', 'crying'):
        im = tile(n)
        cols = len({tuple(c) for c in np.asarray(im).reshape(-1, 3)[::3]})
        check(f'aplats : « {n} » reste en aplats ({cols} couleurs)', cols <= 24, f'{cols} couleurs')


def persona_checks():
    from hstudio.engines.console import expression as X
    shy = X.face_params('neutral', t=1., seed=.2, persona={'expressive': .5, 'energy': .4, 'shy': .9})
    bold = X.face_params('neutral', t=1., seed=.2, persona={'expressive': .5, 'energy': .4, 'shy': .0})
    check('identité : un timide regarde plus de côté', shy['gaze'][0] < bold['gaze'][0])
    soft = X.face_params('angry', t=1., seed=.2, persona={'expressive': .2})
    loud = X.face_params('angry', t=1., seed=.2, persona={'expressive': .95})
    check('identité : « expressive » règle l\'amplitude', abs(soft['brow_in']) < abs(loud['brow_in']))
    check('identité : intensité 0 ramène au neutre',
          abs(X.face_params('angry', t=1., intensity=0.)['brow_in']) < 1e-9)


if __name__ == '__main__':
    opt_in_checks(); determinism_checks(); expression_checks()
    eye_checks(); talk_checks(); flat_checks(); persona_checks()
    print('\n' + ('Tout est OK' if not FAIL else f'{len(FAIL)} ÉCHEC(S) : ' + ', '.join(FAIL)))
    sys.exit(1 if FAIL else 0)
