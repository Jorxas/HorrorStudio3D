"""Tests hors ligne de la MUSIQUE DE FOND fabriquée (hstudio/audio/musique_drame.py) et du bus « musique » du kit
(hstudio/histoire/mixage.py) : aucun réseau, aucune voix réelle, aucun GPU.

    python tools/check_musique_drame.py

Couvre : noms connus de fabriques (kind 'bed', rms_db), déterminisme (graines locales, indépendant de l'état global et de
l'ordre d'appel), durée exacte, pas d'écrêtage, RMS nominal, énergie surtout entre 100 et 3000 Hz (rien de grave),
mineur / majeur reconnaissables, cordes sans demi-ton ni triton, raccords de boucle sans clic (boucle exacte), début
identique quelle que soit la durée, bus « musique » choisi par render_cue (nom musique_* ou bus='musique', bus explicite
prioritaire, nappes et bruitages inchangés), niveau de référence indépendant de la durée de la cue, baisse sous la voix
plus légère que les nappes, clé de baisse plus lente (moins de pompage) et clé par défaut inchangée au bit près."""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

OK = []; BAD = []
STYLES = ('triste', 'tendre', 'suspens')
NAMES = tuple(f'musique_piano_{s}' for s in STYLES)


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(('  ok   ' if cond else '  ÉCHEC ') + name + (f'  ({detail})' if detail else ''))


def rms_db(x):
    x = np.asarray(x, np.float64); return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)


def t_registry():
    from hstudio.audio import fabriques as FB, musique_drame as MD, synth as S
    check('fabriques : les trois noms connus de has(), en nappe (kind bed)', all(FB.has(k) and FB.SOUNDS[k]['kind'] == 'bed' for k in NAMES))
    check('fabriques : description en français et RMS nominal déclaré', all(len(FB.SOUNDS[k]['desc']) > 20 and FB.SOUNDS[k]['rms_db'] == MD.NOMINAL_RMS_DB for k in NAMES))
    check('fabriques : absents de synth.SFX (aucun épisode existant ne change)', not any(k in S.SFX for k in NAMES))


def t_determinism():
    from hstudio.audio import fabriques as FB, musique_drame as MD, synth as S
    a1 = {k: FB.make(k, 4.) for k in NAMES}
    S.reseed(999); _ = S.noise(1000); np.random.seed(4242); _ = np.random.rand(10)        # disturb every global state
    a2 = {k: FB.make(k, 4.) for k in reversed(NAMES)}
    check('déterministe : mêmes échantillons, quels que soient l\'état global et l\'ordre', all(np.array_equal(a1[k], a2[k]) for k in NAMES))
    st = 'triste'; c1 = MD._cycle(st)[1].copy()
    MD._cycle.cache_clear(); MD._score.cache_clear(); MD._room.cache_clear()
    check('déterministe : boucle recalculée sans cache identique au bit près', np.array_equal(c1, MD._cycle(st)[1]))
    check('sortie float32 mono', all(a.dtype == np.float32 and a.ndim == 1 for a in a1.values()))


def t_signal():
    from hstudio.audio import musique_drame as MD
    SR = MD.SR
    for st in STYLES:
        P = MD._score(st)[0]; first, cyc = MD._cycle(st)
        durs = (.37, 3., 12.345, P / SR + 7.5)
        lens = [len(MD.render(st, d)) for d in durs[:3]]
        long_ = MD.render(st, 2.4 * P / SR)
        check(f'{st} : durée exacte (0,37 s, 3 s, 12,345 s, plus d\'une boucle)',
              lens == [int(round(d * SR)) for d in durs[:3]] and len(MD.render(st, durs[3])) == int(round(durs[3] * SR)) and len(long_) == int(round(2.4 * P / SR * SR)))
        pk = 20 * np.log10(max(np.abs(first).max(), np.abs(cyc).max()))
        check(f'{st} : pas d\'écrêtage (crête ≤ -1 dBFS)', pk <= -1., f'{pk:.2f} dBFS')
        r = rms_db(cyc)
        check(f'{st} : RMS de la boucle au niveau nominal ({MD.NOMINAL_RMS_DB:.0f} dBFS ± 0,5)', abs(r - MD.NOMINAL_RMS_DB) <= .5, f'{r:.2f} dBFS')
        X = np.abs(np.fft.rfft(cyc.astype(np.float64))) ** 2; f = np.fft.rfftfreq(len(cyc), 1. / SR); tot = X.sum()
        band = X[(f >= 100) & (f <= 3000)].sum() / tot; low = X[f < 80].sum() / tot
        check(f'{st} : énergie surtout entre 100 et 3000 Hz (≥ 90 %)', band >= .90, f'{band:.1%}')
        check(f'{st} : pas de grave inquiétant (< 0,5 % sous 80 Hz)', low < .005, f'{low:.2%}')
        # loop seam: the loop is exact (period P) and its junctions are no rougher than the music itself
        x = long_.astype(np.float64); end = len(x) - int(.01 * SR) - 2 * P
        check(f'{st} : boucle exacte (période d\'une boucle, au bit près)', np.array_equal(x[P:P + end], x[2 * P:2 * P + end]))
        d = np.abs(np.diff(x)); ref = np.percentile(d, 99.9)
        h = np.fft.irfft(np.fft.rfft(x) * (np.fft.rfftfreq(len(x), 1. / SR) > 5000.), len(x)); w = int(.01 * SR)
        win = np.sqrt(np.mean(h[:len(h) // w * w].reshape(-1, w) ** 2, 1)); p99 = np.percentile(win, 99)
        seams = [(d[j - 200:j + 200].max() / ref, np.sqrt(np.mean(h[j - w // 2:j + w // 2] ** 2)) / p99) for j in (P, 2 * P)]
        check(f'{st} : pas de clic aux raccords de boucle', all(a <= 1. and b <= 1. for a, b in seams),
              ', '.join(f'saut {a:.2f}, aigus {b:.2f}' for a, b in seams))
        short = MD.render(st, 8.); n = len(short) - int(.01 * SR)
        diff = float(np.abs(short[:n] - long_[:n]).max())
        check(f'{st} : début identique quelle que soit la durée (< 1e-4)', diff < 1e-4, f'{diff:.1e}')


def t_harmony():
    from hstudio.audio import musique_drame as MD
    SR = MD.SR

    def chroma(st):
        x = MD._cycle(st)[1].astype(np.float64); X = np.abs(np.fft.rfft(x)) ** 2; f = np.fft.rfftfreq(len(x), 1. / SR)
        sel = (f > 100) & (f < 1200); pc = np.round(12 * np.log2(f[sel] / 440.) + 69).astype(int) % 12
        return np.bincount(pc, X[sel], 12)
    c = chroma('triste')
    check('triste : mineur (do plus fort que do#, la parmi les 3 notes dominantes)', c[0] > 3 * c[1] and 9 in np.argsort(c)[-3:])
    c = chroma('tendre')
    check('tendre : majeur (fa# plus fort que fa, do# plus fort que do)', c[6] > 3 * c[5] and c[1] > 2 * c[0])
    ok = True; worst = ''
    for st in STYLES:
        P, piano, strings = MD._score(st)
        for t in np.arange(0., P / SR, .25):
            ms = sorted({m for t0, t1, m, g, v in strings if t0 + .5 <= t < t1 - .1})
            for i in range(len(ms)):
                for j in range(i + 1, len(ms)):
                    ic = (ms[j] - ms[i]) % 12
                    if min(ic, 12 - ic) in (1, 6): ok = False; worst = f'{st} à {t:.2f} s : {ms}'
    check('cordes : accords tenus sans demi-ton ni triton (aucune dissonance de tension)', ok, worst)


def t_mixer():
    from hstudio.histoire import mixage as MX
    M = MX.Mixer(None, types.SimpleNamespace(MIXAGE={}), log=lambda *a: None)
    cue = lambda name, **kw: dict(dict(name=name, t=1., gain=.5, dur=6.), **kw)
    bus = lambda c: M.render_cue(c)[2]
    check('render_cue : bus musique pour les noms musique_*', all(bus(cue(k)) == 'musique' for k in NAMES))
    check('render_cue : bus musique pour bus=\'musique\' (autre son)', bus(cue('night_wind', bus='musique')) == 'musique')
    check('render_cue : un bus explicite fx / bed reste prioritaire', bus(cue('musique_piano_tendre', bus='bed')) == 'bed' and bus(cue('musique_piano_tendre', bus='fx')) == 'fx')
    check('render_cue : nappes et bruitages existants inchangés', bus(cue('night_wind')) == 'bed' and bus(dict(name='cough', t=1., gain=.5, dur=None)) == 'fx')
    # the level comes from the generator's nominal RMS: the same cue is scaled the same whatever its duration
    a20 = M.render_cue(cue('musique_piano_tendre', dur=20.))[0]; a8 = M.render_cue(cue('musique_piano_tendre', dur=8.))[0]
    SR = M.SR; s = slice(int(2 * SR), int(5 * SR)); ratio = float(np.sqrt(np.mean(a20[s].astype(np.float64) ** 2) / np.mean(a8[s].astype(np.float64) ** 2)))
    check('niveau : indépendant de la durée de la cue (même gain à 8 s et 20 s)', abs(ratio - 1.) < 1e-3, f'rapport {ratio:.5f}')
    ref_db, ref_g = M.bed['musique_piano_tendre']
    a = M.render_cue(cue('musique_piano_tendre', dur=40., gain=ref_g))[0][int(2 * SR):int(37 * SR)]
    check('niveau : RMS au gain de référence proche du niveau BED (± 2 dB)', abs(rms_db(a) - ref_db) <= 2., f'{rms_db(a):.1f} dB pour {ref_db} dB')
    body = np.abs(a20[int(3 * SR):int(6 * SR)]).max()
    check('fondus musicaux par défaut (entrée 1,5 s, sortie 2,5 s)', np.abs(a20[:int(.1 * SR)]).max() < .2 * body and np.abs(a20[-int(.05 * SR):]).max() < .1 * body)
    check(f'baisse musique par défaut {M.duck_mus:.2f} : entre 0,35 et 0,45, plus légère que les nappes ({M.duck_bed:.2f})', .35 <= M.duck_mus <= .45 and M.duck_mus < M.duck_bed)
    M2 = MX.Mixer(None, types.SimpleNamespace(MIXAGE={'baisse_musique': .3}), log=lambda *a: None)
    check('baisse musique réglable par MIXAGE[\'baisse_musique\']', M2.duck_mus == .3 and M2.duck_bed == M.duck_bed)
    # ducking key: a synthetic "voice" (speech-like noise at -20 dBFS) with a 0.3 s gap, then a 3 s silence
    rng = np.random.default_rng(5); seg = lambda d: (rng.standard_normal(int(d * SR)) * .1).astype(np.float32)
    v = np.concatenate([seg(2.), np.zeros(int(.3 * SR), np.float32), seg(2.), np.zeros(int(3. * SR), np.float32), seg(1.)])
    kb = M.activity(v); km = M.activity(v, *MX.MUSIC_KEY)
    check('clé par défaut inchangée (nappes / bruitages : mélanges existants identiques)', np.array_equal(kb, M.activity(v, .5, .03)))
    gap = slice(int(2.05 * SR), int(2.3 * SR))
    gm = 20 * np.log10(1. - M.duck_mus * km[gap].min()); gb_ = 20 * np.log10(1. - M.duck_mus * kb[gap].min())
    check('clé musique plus lente : la musique pompe moins dans une pause de 0,3 s', gm < gb_ - .5, f'remontée {gm + 4.44:.1f} dB contre {gb_ + 4.44:.1f} dB')
    t2 = int((2. + .3 + 2. + 2.) * SR); g2 = 20 * np.log10(1. - M.duck_mus * km[t2])
    check('clé musique : pleine présence après 2 s de vrai silence (≥ -0,5 dB)', g2 >= -.5, f'{g2:.2f} dB')
    sp = slice(int(.5 * SR), int(1.9 * SR)); gs = 20 * np.log10(1. - M.duck_mus * km[sp].mean())
    check('pendant la parole : musique baissée de 3,7 à 5,2 dB seulement', -5.2 <= gs <= -3.7, f'{gs:.2f} dB')


def main():
    print('registre des sons fabriqués'); t_registry()
    print('déterminisme'); t_determinism()
    print('signal (durée, niveau, spectre, boucle)'); t_signal()
    print('harmonie'); t_harmony()
    print('bus musique du mixeur'); t_mixer()
    n = len(OK) + len(BAD)
    print(f'\n{len(OK)}/{n} OK' + (f' — {len(BAD)} échec(s)' if BAD else ''))
    sys.exit(1 if BAD else 0)


if __name__ == '__main__':
    main()
