"""Tests hors ligne des SONS FABRIQUÉS de « Le Phare qui efface » (14/11/2026, hstudio/audio/fabriques.py) : aucun réseau,
aucune voix, aucun GPU.

    python tools/check_sons_phare.py

Couvre, pour `freinage_pneus`, `eclair_phare`, `effacement` et `frappe_mur_invisible` : registre (ponctuels, description
en français, absents de synth.SFX : aucun épisode existant ne change), déterminisme (état global perturbé, ordre inversé),
durée, crête sous 0 dBFS, aucun NaN, et la FORME mesurée de chaque son (glissade du crissement vers le grave et arrêt sec,
aspiration puis « whoom » sous 120 Hz puis queue tonale, sans craquement aigu ; souffle qui monte et se resserre,
crépitements qui s'éteignent puis silence exact ; quatre coups étouffés et une queue qui décroît), puis le passage par le
mixage du kit (render_cue : bus fx, niveau ponctuel). Les WAV et le spectrogramme regardé sont dans docs/catalogue/sons_phare/."""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

OK = []; BAD = []
NAMES = ('freinage_pneus', 'eclair_phare', 'effacement', 'frappe_mur_invisible')
DUR = {'freinage_pneus': 2.0, 'eclair_phare': 2.5, 'effacement': 1.6, 'frappe_mur_invisible': 1.4}


def check(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print(('  ok   ' if cond else '  ÉCHEC ') + name + (f'  ({detail})' if detail else ''))


def rms_db(x):
    x = np.asarray(x, np.float64); return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)


def seg(a, SR, t0, t1):
    return np.asarray(a[int(t0 * SR):int(t1 * SR)], np.float64)


def spectrum(x, SR):
    X = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2; return np.fft.rfftfreq(len(x), 1 / SR), X


def frac(x, SR, lo, hi):
    f, X = spectrum(x, SR); return float(X[(f >= lo) & (f < hi)].sum() / (X.sum() + 1e-20))


def peak_hz(x, SR, lo, hi):
    f, X = spectrum(x, SR); m = (f >= lo) & (f < hi); return float(f[m][np.argmax(X[m])])


def t_registry():
    from hstudio.audio import fabriques as FB, synth as S
    check('registre : les quatre noms connus de has(), ponctuels (kind one)', all(FB.has(k) and FB.SOUNDS[k]['kind'] == 'one' for k in NAMES))
    check('registre : description en français', all(len(FB.SOUNDS[k]['desc']) > 30 for k in NAMES))
    check('registre : absents de synth.SFX (aucun épisode existant ne change)', not any(k in S.SFX for k in NAMES))
    from hstudio.histoire import verif
    check('kit : noms reconnus par le contrôle des bruitages (verif.sound_known)', all(verif.sound_known(k) for k in NAMES))


def t_determinism():
    from hstudio.audio import fabriques as FB, synth as S
    a1 = {k: FB.make(k) for k in NAMES}
    S.reseed(777); _ = S.noise(500); np.random.seed(99); _ = np.random.rand(7)
    a2 = {k: FB.make(k) for k in reversed(NAMES)}
    check('déterministe : mêmes échantillons, quels que soient l\'état global et l\'ordre', all(np.array_equal(a1[k], a2[k]) for k in NAMES))
    check('sortie float32 mono', all(a.dtype == np.float32 and a.ndim == 1 for a in a1.values()))
    SR = FB.SR
    for k in NAMES:
        a = a1[k]
        check(f'{k} : durée {DUR[k]} s', abs(len(a) / SR - DUR[k]) < .005, f'{len(a) / SR:.3f} s')
        check(f'{k} : aucun NaN ni infini', bool(np.isfinite(a).all()))
        pk = float(np.abs(a).max())
        check(f'{k} : crête sous 0 dBFS et son présent', .3 < pk < 1., f'crête {pk:.3f}')
    return a1


def t_shapes(A):
    from hstudio.audio import fabriques as FB
    SR = FB.SR
    # --- tyre squeal: pitch glides down, dry stop at 1.72 s, no impact afterwards
    a = A['freinage_pneus']
    p0 = peak_hz(seg(a, SR, .1, .3), SR, 300, 2500); p1 = peak_hz(seg(a, SR, 1.45, 1.65), SR, 300, 2500)
    check('freinage : le crissement glisse vers le grave', p0 > 1250 and p1 < 1000 and p0 - p1 > 350, f'{p0:.0f} -> {p1:.0f} Hz')
    check('freinage : énergie surtout entre 600 et 5000 Hz pendant le crissement', frac(seg(a, SR, .2, 1.5), SR, 600, 5000) > .7)
    drop = rms_db(seg(a, SR, 1.6, 1.7)) - rms_db(seg(a, SR, 1.78, 1.86))
    check('freinage : arrêt sec (au moins 10 dB de moins en 80 ms)', drop > 10., f'{drop:.1f} dB')
    after = seg(a, SR, 1.76, 2.0)
    check('freinage : après l\'arrêt, seulement un tassement grave (pas de choc aigu)', frac(after, SR, 0, 400) > .7 and rms_db(after) < rms_db(seg(a, SR, .5, 1.)) - 12)
    # --- lighthouse flash: breath rising, deep whoom, tonal singing tail, no crack
    a = A['eclair_phare']
    check('éclair : le souffle aspiré monte (0,25-0,32 s ≫ 0-0,1 s)', rms_db(seg(a, SR, .25, .32)) - rms_db(seg(a, SR, 0., .1)) > 15.)
    lo = frac(seg(a, SR, .37, .75), SR, 0, 120)
    check('éclair : le « whoom » est sous 120 Hz', lo > .5, f'{lo:.2f} de l\'énergie')
    w0 = peak_hz(seg(a, SR, .37, .6), SR, 25, 110)
    check('éclair : fondamentale du « whoom » entre 40 et 65 Hz', 40 <= w0 <= 65, f'{w0:.0f} Hz')
    tail = seg(a, SR, .8, 1.7); f, X = spectrum(tail, SR); m = (f > 400) & (f < 4500)
    ptm = float(X[m].max() / (np.median(X[m]) + 1e-20))
    gap = 10 * np.log10((X[f < 150].sum() + 1e-20) / (X[m].sum() + 1e-20))
    # the singing glass must stand within 8 dB of the sub in ENERGY (it is far louder to the ear, and the only part a phone plays)
    check('éclair : queue tonale (verre qui chante) entre 400 et 4500 Hz, pas noyée sous le grave', ptm > 1e3 and gap < 8., f'grave - chant {gap:.1f} dB')
    check('éclair : pas de craquement aigu (moins de 2 % au-dessus de 6 kHz)', frac(a, SR, 6000, SR / 2) < .02)
    k = int(.35 * SR); step = float(np.abs(np.diff(a[k - 500:k + 500])).max()); typ = float(np.abs(np.diff(a[k + 3000:k + 4000])).max())
    check('éclair : pas de clic au passage souffle -> « whoom »', step < 2.5 * typ + .01, f'saut {step:.3f}, ordinaire {typ:.3f}')
    # --- erasure: swell that tightens, crackles that die, exact silence
    a = A['effacement']
    check('effacement : le souffle monte jusqu\'à 0,9 s', rms_db(seg(a, SR, .78, .88)) - rms_db(seg(a, SR, 0., .2)) > 15.)

    def spread(x):
        f, X = spectrum(x, SR); c = (X * f).sum() / (X.sum() + 1e-20); return float(np.sqrt((X * (f - c) ** 2).sum() / (X.sum() + 1e-20)))
    s0, s1 = spread(seg(a, SR, .05, .3)), spread(seg(a, SR, .7, .88))
    check('effacement : la bande se resserre', s1 < .7 * s0, f'{s0:.0f} -> {s1:.0f} Hz')
    c1 = seg(a, SR, .9, 1.32); kurt = float(np.mean(c1 ** 4) / (np.mean(c1 ** 2) ** 2 + 1e-20))
    check('effacement : crépitements (impulsions, kurtosis élevé)', kurt > 6., f'kurtosis {kurt:.1f}')
    check('effacement : les crépitements s\'éteignent', rms_db(seg(a, SR, .9, 1.02)) - rms_db(seg(a, SR, 1.18, 1.32)) > 10.)
    check('effacement : silence exact à la fin (dès 1,35 s)', float(np.abs(a[int(1.35 * SR):]).max()) == 0.)
    # --- fists on an invisible wall: 3 to 5 muffled knocks, decaying tail
    a = A['frappe_mur_invisible']
    e = np.array([rms_db(a[j:j + int(.01 * SR)]) for j in range(0, len(a) - int(.01 * SR), int(.01 * SR))])
    on = [i for i in range(1, len(e)) if e[i] - e[i - 1] > 12. and e[i] > -25.]
    onsets = [i for j, i in enumerate(on) if j == 0 or i - on[j - 1] > 5] + ([0] if e[0] > -20. else [])
    check('frappes : 3 à 5 coups', 3 <= len(set(onsets)) <= 5, f'{len(set(onsets))} coups')
    check('frappes : étouffées (plus de 70 % sous 1500 Hz)', frac(a, SR, 0, 1500) > .7)
    check('frappes : la queue décroît (1,0-1,2 s ≪ 0,8-0,9 s)', rms_db(seg(a, SR, .8, .9)) - rms_db(seg(a, SR, 1.0, 1.2)) > 12.)


def t_mixer():
    from hstudio.histoire import mixage as MX
    M = MX.Mixer(None, types.SimpleNamespace(MIXAGE={}), log=lambda *a: None)
    for k in NAMES:
        a, start, bus = M.render_cue(dict(name=k, t=2., gain=.8, dur=None))
        loud = M.LB.short_rms(a); target = MX.db(MX.ONE_DB) * .8
        check(f'mixage : {k} en bus fx, niveau ponctuel au gain demandé', bus == 'fx' and start == 2 * M.SR and abs(20 * np.log10(loud / target)) < .1,
              f'{20 * np.log10(loud / target):+.2f} dB')


def main():
    print('registre'); t_registry()
    print('déterminisme, durée, crête'); A = t_determinism()
    print('forme mesurée de chaque son'); t_shapes(A)
    print('mixage du kit'); t_mixer()
    print(f'\n{len(OK)} contrôles OK, {len(BAD)} en échec' + (f' : {BAD}' if BAD else ''))
    sys.exit(1 if BAD else 0)


if __name__ == '__main__':
    main()
