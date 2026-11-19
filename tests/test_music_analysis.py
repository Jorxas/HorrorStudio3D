"""Clip musical : l'analyseur retrouve le tempo, les temps et les premiers temps d'une piste dont on connaît tout.

    python tests/test_music_analysis.py

La piste est fabriquée ici (aucun fichier, aucun réseau) : une grosse caisse sur le premier temps de chaque mesure,
un charleston sur les autres, un accord tenu, à 96 BPM, premier temps à 0,5 s, 24 s. Puis un silence de 1,5 s et
une reprise plus forte, pour les sections et les silences.
"""
import os, sys, subprocess, tempfile, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from hstudio.audio import music_analysis as MA          # noqa: E402
from hstudio.audio import music_cues as MC              # noqa: E402

SR = 44100; BPM = 96.; P = 60. / BPM; T0 = .5


def track():
    n1 = int(24 * SR); n2 = int(1.5 * SR); n3 = int(10 * SR); y = np.zeros(n1 + n2 + n3, np.float32)
    t = np.arange(int(.25 * SR)) / SR
    kick = (np.sin(2 * np.pi * (55 + 90 * np.exp(-t * 30)) * t) * np.exp(-t * 14)).astype(np.float32)
    hat = (np.random.default_rng(1).standard_normal(len(t)) * np.exp(-t * 60)).astype(np.float32) * .25
    def put(sig, at, g):
        i = int(at * SR); j = min(len(y), i + len(sig)); y[i:j] += g * sig[:j - i]
    k = 0; at = T0
    while at < 24 - .3:
        put(kick if k % 4 == 0 else hat, at, .9 if k % 4 == 0 else .6); k += 1; at = T0 + k * P
    tt = np.arange(n1) / SR
    y[:n1] += .08 * (np.sin(2 * np.pi * 220 * tt) + np.sin(2 * np.pi * 277 * tt))
    at = 25.5; k = 0
    while at < 35.2:
        put(kick if k % 2 == 0 else hat, at, 1.); k += 1; at = 25.5 + k * P / 2
    tt = np.arange(n3) / SR; y[n1 + n2:] += .2 * np.sin(2 * np.pi * 110 * tt)
    return np.clip(y, -1, 1)


def main():
    fails = []
    def check(name, ok, info=''):
        print(('OK    ' if ok else 'ECHEC ') + name + (f'   [{info}]' if info else ''))
        if not ok: fails.append(name)
    y = track(); fd, path = tempfile.mkstemp(suffix='.wav'); os.close(fd)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((y * 32000).astype(np.int16).tobytes())
    try:
        A = MA.analyse(path); B = MA.analyse(path)
    finally:
        os.remove(path)
    check('déterministe : deux analyses donnent le même résultat', A == B)
    check('tempo retrouvé à 1,5 BPM près', abs(A['tempo'] - BPM) < 1.5 or abs(A['tempo'] - 2 * BPM) < 3, f"{A['tempo']} BPM pour {BPM}")
    b = np.array([x for x in A['beats'] if x < 23.5]); grid = T0 + np.arange(0, 40) * P
    err = np.array([np.min(np.abs(grid - x)) for x in b])
    check('les temps tombent sur la grille (médiane < 30 ms)', len(b) > 20 and float(np.median(err)) < .03, f'{len(b)} temps, médiane {1000 * float(np.median(err)):.1f} ms')
    d = [x for x in A['downbeats'] if x < 23.5]; dgrid = T0 + np.arange(0, 12) * 4 * P
    derr = [float(np.min(np.abs(dgrid - x))) for x in d]
    check('les premiers temps de mesure sont ceux de la grosse caisse', len(d) >= 4 and float(np.median(derr)) < .05, f'{len(d)} premiers temps, médiane {1000 * float(np.median(derr)):.1f} ms')
    check('le silence de 24 à 25,5 s est trouvé', any(a <= 24.4 and b_ >= 25.1 for a, b_ in A['silences']), str(A['silences']))
    check('une coupe de section près de la reprise (25,5 s)', any(abs(s['t0'] - 25.5) < 2.5 for s in A['sections'][1:]), str([(s['t0'], s['niveau']) for s in A['sections']]))
    check('la reprise est la section la plus forte', max(A['sections'], key=lambda s: s['energy'])['t0'] > 20, '')
    M = MC.Music(A)
    check('M.cuts donne des premiers temps', M.cuts(0, 24, 2) == d[::2][:len(M.cuts(0, 24, 2))], '')
    p = M.pulse(0, 4, 1 / 30)
    check('M.pulse : une valeur par image, plus haute juste après un temps', len(p) == 122 and p[int(round(T0 * 30)) + 1] > p[int(round((T0 + P / 2) * 30))], '')
    ep = {'music_clip': M.embed()}
    f0, s0 = MC.camera_pulse(ep, {'fov': 3., 'shake': .2}, A['beats'][3] + .01, 50., 0.)
    f1, s1 = MC.camera_pulse(ep, {'fov': 3., 'shake': .2}, A['beats'][3] + P * .6, 50., 0.)
    check('caméra « pulse » : le champ se resserre sur le temps et revient', f0 < f1 <= 50. and s0 > s1, f'{f0:.2f} / {f1:.2f}')
    check('sans music_clip, la caméra ne change pas', MC.camera_pulse({}, {'fov': 3.}, 1., 50., 0.) == (50., 0.))
    S = MC.Music({'beats': [], 'vocal': {'phrases': [[1., 3.], [4., 6.]], 'onsets': [1., 1.5, 2., 4., 4.5, 5.]}}, offset=0.)
    w = S.words_on_syllables('UN DEUX TROIS', 0., 3.5, hold=.8)
    check('mots 3D : un mot par attaque de syllabe, au bon instant', [x['text'] for x in w] == ['UN', 'DEUX', 'TROIS'] and [x['t0'] for x in w] == [1., 1.5, 2.], str([(x['text'], x['t0']) for x in w]))
    check('mots 3D : chaque mot reste jusqu\'à l\'attaque suivante, au plus `hold`', w[0]['t1'] == 1.5 and w[2]['t1'] == 2.8, str([x['t1'] for x in w]))
    ph = S.words_on_syllables('A B', 0., 7., on='phrases', ndc=[.1, .2])
    check('mots 3D : un mot par début de phrase, position fixe', [x['t0'] for x in ph] == [1., 4.] and ph[1]['ndc'] == [.1, .2], '')
    try: S.words_on_syllables('a b c d e f g', 0., 7.); ok = False
    except ValueError: ok = True
    check('mots 3D : trop de mots pour les attaques -> erreur claire', ok, '')
    print(f'\n{15 - len(fails)} OK, {len(fails)} échec(s)')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
