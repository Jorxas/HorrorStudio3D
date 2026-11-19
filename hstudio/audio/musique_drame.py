"""Musique de fond FABRIQUÉE pour les histoires dramatiques (pas d'horreur) : piano + cordes légères, synthétisés par le
code (aucun échantillon, licence : à nous). Enregistrée dans hstudio/audio/fabriques.py (kind 'bed') et mixée par le kit
sur son propre bus « musique » (hstudio/histoire/mixage.py), baissée moins fort que les nappes quand la voix parle.

    from hstudio.audio import musique_drame as MD
    a = MD.musique_piano_triste(95.0)         # float32 mono à MD.SR (44 100 Hz), exactement round(95 * SR) échantillons

Styles (une fonction par style, fn(dur) -> np.float32) :
  * musique_piano_triste  : la mineur, 62 bpm, deuil sous la pluie (Am F C G | Am F Dm E, cadence par mi majeur) ;
  * musique_piano_tendre  : ré majeur, 68 bpm, chaleureux, souvenirs d'amitié (basse qui descend D C# B A G F# E A) ;
  * musique_piano_suspens : sol majeur / mi mineur, 60 bpm, retenu et interrogatif (accords add9 / sus4 qui ne se
    résolvent presque jamais, notes tenues), SANS tension d'horreur (ni drone grave, ni dissonance, ni percussion).

Each style is a 16-bar cycle (two 8-bar phrases: a quieter statement, then a fuller answer) that loops without a seam: the
cycle is rendered once with the tails of its notes and of its reverb, and those tails are folded onto the start of the
next cycle, so a long piece is exactly what an endless linear performance would give (no click, no gap, no level jump).

Instruments (code comments in English):
  * piano: additive "physical" synthesis - stiff-string partials (inharmonicity B), two-stage decay (prompt sound, then
    aftersound) faster for the high partials and the high notes, 2-3 slightly detuned unison strings (slow beating),
    hammer contact edge and a soft felt knock, hammer-position comb, sustain pedal changed on every chord, soft pedal
    (una corda: darker timbre, third string only resonates), varied velocities (phrase arch, accents, humanised);
  * strings: an ensemble of 3 detuned band-limited saws per voice, smooth low-pass, slow attack, light delayed vibrato
    and a slow drift, voice-leading that keeps the common tones held across chords; a moving voice lifts its bow 50 ms
    before the chord change and releases in 0.4 s, so it never rubs against the next chord;
  * a small room reverb (synthetic impulse: early reflections + frequency-dependent diffuse tail, RT60 ~1.5 s).

DETERMINISTIC: every random value comes from local generators with fixed seeds, drawn in a fixed order for the whole
cycle; nothing reads the global numpy state, synth._rng or the clock. The same call always returns the same samples, and
the start of a piece is the same whatever its duration. Output level: NOMINAL_RMS_DB (RMS over a full cycle)."""
import functools
import itertools

import numpy as np

from . import synth as S

SR = S.SR
_R = SR // 2                 # internal rate: everything is below 7.2 kHz; upsampled once by FFT at the end
NOMINAL_RMS_DB = -22.        # RMS of every style over a full cycle (dBFS); the kit mixer reads it from fabriques.SOUNDS
_PRE = int(.3 * SR)          # pre-roll of a rendered cycle (even: it is made at _R): zero-phase filter skirts land there

_NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
_QUALITY = {'': (0, 4, 7), 'm': (0, 3, 7), '7': (0, 4, 7, 10), 'm7': (0, 3, 7, 10), 'sus4': (0, 5, 7),
            'sus2': (0, 2, 7), 'add9': (0, 4, 7, 2), 'madd9': (0, 3, 7, 2)}


def hz(m):
    return 440. * 2 ** ((m - 69) / 12.)


def _pc(s):
    """'F#' -> 6, 'Bb' -> 10"""
    p = _NOTE[s[0]]
    for ch in s[1:]: p += 1 if ch == '#' else -1
    return p % 12


def midi(name):
    """'F#4' -> 66, 'Bb3' -> 58 (C4 = 60)"""
    i = 1
    while name[i] in '#b': i += 1
    return _pc(name[:i]) + 12 * (int(name[i:]) + 1)


def chord(sym):
    """'G/B' -> dict(pcs, core, bass): pitch classes (with extensions), the triad core, the bass pitch class"""
    sym, _, bass = sym.partition('/')
    i = 2 if len(sym) > 1 and sym[1] in '#b' else 1
    root = _pc(sym[:i]); q = _QUALITY[sym[i:]]
    pcs = tuple((root + x) % 12 for x in q)
    return dict(sym=sym, pcs=pcs, core=pcs[:3], bass=_pc(bass) if bass else root)


# ------------------------------------------------------------------ the three pieces
# bars: one chord symbol per bar, or [(beat, symbol), ...] for a change inside the bar.
# melody: per bar, (beat, note, beats). arp: per bar, (beat, 'B' = bass | index of the upper chord tones | (i, j) dyad, velocity).
# dyn: phrase arch per bar (piano), cordes: strings level per bar. corda: soft pedal (una corda).
STYLES = {
    'triste': dict(
        bpm=62, seed=6201, bass_lo=41, upper_from=7, corda=True, mel_vel=(.44, .56), strings=.043, attack=1.1, release=.4,
        cutoff=1600., vibrato=.0032, wet=(.30, .40), gain=1.593,
        bars=['Am', 'F', 'C', 'G', 'Am', 'F', 'Dm', 'E',
              'Am', 'F', 'C', 'G/B', 'Am', 'Dm', 'F', 'E'],
        melody=[[(0, 'E5', 2), (2, 'D5', 1), (3, 'C5', 1)], [(0, 'C5', 3), (3, 'A4', 1)],
                [(0, 'G4', 2), (2, 'C5', 1), (3, 'E5', 1)], [(0, 'D5', 4)],
                [(0, 'C5', 1.5), (1.5, 'B4', .5), (2, 'C5', 1), (3, 'E5', 1)], [(0, 'F5', 2), (2, 'C5', 1), (3, 'A4', 1)],
                [(0, 'D5', 2), (2, 'C5', 1), (3, 'A4', 1)], [(0, 'B4', 2), (2, 'G#4', 2)],
                [(0, 'E5', 1), (1, 'A5', 2), (3, 'G5', 1)], [(0, 'F5', 2), (2, 'C5', 1), (3, 'D5', 1)],
                [(0, 'E5', 2), (2, 'G5', 2)], [(0, 'D5', 2), (2, 'B4', 2)],
                [(0, 'C5', 1), (1, 'E5', 1), (2, 'A5', 2)], [(0, 'F5', 2), (2, 'D5', 2)],
                [(0, 'C5', 2), (2, 'A4', 1), (3, 'C5', 1)], [(0, 'B4', 2), (2, 'G#4', 2)]],
        arp=[(0, 'B', .46), (.5, 0, .30), (1, 1, .32), (1.5, 2, .34), (2, 3, .36), (2.5, 2, .32), (3, 1, .30), (3.5, 0, .28)],
        dyn=[.80, .82, .86, .88, .92, .94, .90, .84, .92, .96, 1., 1., 1., .96, .90, .84],
        cordes=[.62, .66, .72, .76, .80, .84, .82, .76, .90, .96, 1., 1., 1., .96, .90, .78]),
    'tendre': dict(
        bpm=68, seed=6802, bass_lo=40, upper_from=7, corda=False, mel_vel=(.46, .58), strings=.045, attack=.9, release=.4,
        cutoff=2000., vibrato=.0030, wet=(.28, .38), gain=1.648,
        bars=['D', 'A/C#', 'Bm', 'F#m/A', 'G', 'D/F#', 'Em7', [(0, 'Asus4'), (2, 'A')],
              'G', 'D/F#', 'Em', 'Bm', 'G', 'A', 'D', [(0, 'Asus4'), (2, 'A')]],
        melody=[[(0, 'F#5', 1.5), (1.5, 'E5', .5), (2, 'D5', 1), (3, 'E5', 1)], [(0, 'E5', 2), (2, 'C#5', 1), (3, 'A4', 1)],
                [(0, 'D5', 1.5), (1.5, 'C#5', .5), (2, 'B4', 1), (3, 'D5', 1)], [(0, 'C#5', 3), (3, 'A4', 1)],
                [(0, 'B4', 1), (1, 'D5', 1), (2, 'G5', 2)], [(0, 'F#5', 2), (2, 'A5', 1), (3, 'F#5', 1)],
                [(0, 'G5', 1.5), (1.5, 'F#5', .5), (2, 'E5', 1), (3, 'D5', 1)], [(0, 'D5', 2), (2, 'C#5', 2)],
                [(0, 'D5', 1), (1, 'G5', 2), (3, 'E5', 1)], [(0, 'F#5', 2), (2, 'E5', 1), (3, 'D5', 1)],
                [(0, 'E5', 2), (2, 'B4', 1), (3, 'E5', 1)], [(0, 'F#5', 2), (2, 'D5', 2)],
                [(0, 'G5', 1.5), (1.5, 'F#5', .5), (2, 'E5', 1), (3, 'D5', 1)], [(0, 'C#5', 1), (1, 'E5', 1), (2, 'A5', 2)],
                [(0, 'F#5', 2), (2, 'E5', 1), (3, 'D5', 1)], [(0, 'D5', 2), (2, 'C#5', 1), (3, 'E5', 1)]],
        arp=[(0, 'B', .48), (.5, 0, .31), (1, 1, .34), (1.5, 2, .36), (2, 3, .38), (2.5, 1, .33), (3, 2, .35), (3.5, 0, .30)],
        dyn=[.84, .86, .88, .90, .94, .96, .94, .88, .92, .96, 1., 1., 1., .98, .94, .88],
        cordes=[.66, .70, .74, .78, .84, .88, .86, .80, .92, .96, 1., 1., 1., .98, .92, .80]),
    'suspens': dict(
        bpm=60, seed=6003, bass_lo=40, upper_from=12, corda=True, mel_vel=(.42, .50), strings=.049, attack=1.3, release=.45,
        cutoff=1500., vibrato=.0026, wet=(.34, .42), gain=2.051,
        bars=['Cadd9', 'G/B', 'Am7', 'Dsus4', 'Cadd9', 'Em', 'Am7', 'Dsus4',
              'Em', 'Cadd9', 'G/B', [(0, 'Dsus4'), (2, 'D')], 'Am7', 'Cadd9', 'Em7', 'Dsus4'],
        melody=[[(1, 'G4', 1), (2, 'D5', 2)], [(1, 'B4', 1), (2, 'D5', 2)],
                [(0, 'E5', 2), (2, 'C5', 2)], [(0, 'A4', 4)],
                [(1, 'G4', 1), (2, 'E5', 2)], [(0, 'B4', 2), (2, 'G4', 2)],
                [(0, 'C5', 2), (2, 'E5', 2)], [(0, 'D5', 2), (2, 'G4', 2)],
                [(1, 'B4', 1), (2, 'E5', 2)], [(0, 'D5', 2), (2, 'E5', 1), (3, 'G5', 1)],
                [(0, 'D5', 3), (3, 'B4', 1)], [(0, 'A4', 2), (2, 'F#4', 2)],
                [(0, 'E5', 2), (2, 'C5', 2)], [(0, 'D5', 2), (2, 'G4', 2)],
                [(0, 'B4', 2), (2, 'D5', 2)], [(0, 'A4', 4)]],
        arp=[(0, 'B', .42), (1, 1, .26), (2, (0, 2), .28)],
        dyn=[.80, .82, .86, .84, .86, .90, .92, .86, .88, .94, 1., .96, .96, .92, .88, .82],
        cordes=[.80, .82, .86, .84, .86, .90, .92, .88, .90, .96, 1., .98, .96, .92, .88, .82]),
}


# ------------------------------------------------------------------ score
def _voicing(core, prev, lo=55, hi=76):
    """3 string voices covering the triad core, closest to the previous voicing (common tones stay where they are)"""
    cands = [m for m in range(lo, hi + 1) if m % 12 in core]
    best, best_cost = None, 1e9
    for combo in itertools.combinations(cands, 3):
        if {c % 12 for c in combo} != set(core): continue
        gaps = np.diff(combo)
        if gaps.min() < 2 or gaps.max() > 9: continue             # no semitone cluster, no hole in the middle
        cost = (sum(abs(a - b) for a, b in zip(combo, prev)) if prev else abs(np.mean(combo) - 64.) + .2 * (combo[2] - combo[0]))
        cost += 1.5 * (gaps.min() == 2)                           # whole tones are allowed (sus2) but not preferred
        if cost < best_cost: best, best_cost = combo, cost
    return list(best)


@functools.lru_cache(maxsize=None)
def _score(style):
    """-> (cycle samples, piano notes [(onset s, midi, hold s, velocity)], string notes [(t0, t1, midi, gain, voice)])
    every humanisation is drawn here, in a fixed order, for the whole cycle"""
    sp = STYLES[style]; rng = np.random.default_rng(sp['seed'])
    nb = len(sp['bars']); P = int(round(nb * 4 * 60. / sp['bpm'] * SR)); beat = P / SR / (nb * 4)
    segs = []
    for b, bar in enumerate(sp['bars']):
        items = [(0., bar)] if isinstance(bar, str) else [(float(x), y) for x, y in bar]
        for i, (bt, sym) in enumerate(items):
            nxt = items[i + 1][0] if i + 1 < len(items) else 4.
            segs.append(dict(t0=(4 * b + bt) * beat, t1=(4 * b + nxt) * beat, bar=b, beat=bt, ch=chord(sym)))
    for i, s in enumerate(segs): s['next'] = segs[(i + 1) % len(segs)]

    def seg_at(bar, bt):
        t = (4 * bar + bt) * beat
        return [s for s in segs if s['bar'] == bar and s['t0'] <= t + 1e-9][-1]

    def pedal_end(s, m):
        """the damper falls at the next chord change; a note of the next chord inside the same bar keeps ringing"""
        end = s['t1']; n = s['next']
        while n['bar'] == s['bar'] and n['beat'] > 0 and m % 12 in n['ch']['pcs']:
            end = n['t1']; s, n = n, n['next']
        return end + .06

    piano = []
    for b in range(nb):
        bass_seg = seg_at(b, 0.); ch0 = bass_seg['ch']
        bass = sp['bass_lo'] + (ch0['bass'] - sp['bass_lo']) % 12
        for bt, idx, v in sp['arp']:
            s = seg_at(b, bt); ch = s['ch']
            up = [m for m in range(bass + sp['upper_from'], 84) if m % 12 in ch['pcs']]
            ms = [bass] if idx == 'B' else [up[min(i, len(up) - 1)] for i in (idx if isinstance(idx, tuple) else (idx,))]
            for m in ms:
                t = (4 * b + bt) * beat + float(rng.normal(0., .006)) + (.012 * (len(ms) > 1) * ms.index(m))
                vel = float(np.clip(v * sp['dyn'][b] + rng.normal(0., .025), .12, .9))
                end = pedal_end(s, m) if idx != 'B' else max(pedal_end(s, m), (4 * b + 4) * beat + .06)
                piano.append((max(0., t), m, end - max(0., t), vel))
        va, vb = sp['mel_vel']
        for bt, name, beats in sp['melody'][b]:
            m = midi(name); t = (4 * b + bt) * beat - .012 + float(rng.normal(0., .005))      # melody leads by ~12 ms
            accent = .05 if bt in (0, 2) else (-.04 if bt % 1 else 0.)
            vel = float(np.clip(((va if b < nb // 2 else vb) + accent) * (.6 + .4 * sp['dyn'][b]) + rng.normal(0., .02), .15, .9))
            hold = beats * beat + .05                                                             # legato, finger off
            piano.append((max(0., t), m, hold, vel))
    # strings: a cello on the bass, three voices led smoothly; a held common tone is not bowed again
    voices = [[], [], [], []]; prev = None
    for s in segs:
        ch = s['ch']; bass = sp['bass_lo'] + (ch['bass'] - sp['bass_lo']) % 12
        cello = bass + 12 if bass + 12 <= 57 else bass
        prev = _voicing(ch['core'], prev)
        for v, m in enumerate([cello] + prev):
            if voices[v] and voices[v][-1][2] == m and abs(voices[v][-1][1] - s['t0']) < 1e-6: voices[v][-1][1] = s['t1']
            else: voices[v].append([s['t0'], s['t1'], m])
    strings = [(a, b, m, (.75, 1., .9, .85)[v], v) for v in range(4) for a, b, m in voices[v]]
    return P, piano, strings


# ------------------------------------------------------------------ instruments
def _piano_shape(m, vq, n_hold, corda):
    """one piano note at velocity vq (timbre), held n_hold samples, then damped; unit-ish peak"""
    f0 = hz(m); hold = n_hold / _R
    rel = .09 + .16 * float(np.clip((62 - m) / 24., 0, 1))               # damper: quick in the treble, slower in the bass
    n = n_hold + int(rel * 7 * _R); t = np.arange(n) / _R
    rng = np.random.default_rng(7000 + m)                                 # one fixed set of strings per key
    nstr = 3 if m >= 48 else 2
    det = np.array([0., rng.uniform(.5, 1.3), -rng.uniform(.4, 1.1)])[:nstr] / 1731.23
    amp = np.array([1., 1., .3 if corda else .9])[:nstr]                 # una corda: the 3rd string only resonates
    Bc = 1.1e-4 * 2 ** ((m - 60) / 16.)                                   # inharmonicity, stiffer toward the treble
    tau1 = .62 * (262. / f0) ** .55; tau2 = min(7., 4.4 * (262. / f0) ** .5)
    tilt = 1.0 - .6 * vq + (.22 if corda else 0.)                         # soft touch / una corda: darker
    K = int(min(16, max(3, 5600. / f0)))
    out = np.zeros(n); norm = 0.
    for k in range(1, K + 1):
        fk = k * f0 * np.sqrt(1. + Bc * k * k)
        if fk > 7200.: break
        ak = k ** -tilt * (abs(np.sin(np.pi * k / 7.7)) + .1)             # hammer at ~1/8 of the string
        t1 = tau1 / (1. + .30 * (k - 1)); t2 = tau2 / (1. + .20 * (k - 1))
        env = .78 * np.exp(-t / t1) + .22 * np.exp(-t / t2)               # prompt sound, then aftersound
        ph = rng.uniform(0, 2 * np.pi, nstr)
        sn = sum(amp[j] * np.sin(2 * np.pi * fk * (1. + det[j]) * t + ph[j]) for j in range(nstr))
        out += ak * env * sn; norm += ak
    out /= norm * amp.sum()
    out *= 1. - np.exp(-t / (.0015 + .0025 * (1. - vq)))                 # felt hammer contact
    nk = int(.05 * _R); kn = rng.standard_normal(nk)                      # the soft knock of the felt on the string
    X = np.fft.rfft(kn); f = np.fft.rfftfreq(nk, 1. / _R); X /= np.sqrt(1. + (f / (700. + 1800. * vq)) ** 4)
    kn = np.fft.irfft(X, nk) * np.exp(-np.arange(nk) / _R / .007) * (.035 + .05 * vq) * (.5 if corda else 1.)
    out[:nk] += kn
    d = t > hold
    out[d] *= np.exp(-(t[d] - hold) / rel)                                # the damper falls
    e = min(n, int(.004 * _R)); out[-e:] *= np.linspace(1., 0., e)
    return out


def _saw(f_inst, phase0):
    """band-limited sawtooth (polyBLEP) for an instantaneous frequency array"""
    inc = f_inst / _R; ph = (phase0 + np.cumsum(inc)) % 1.
    s = 2. * ph - 1.
    a = ph < inc
    x = ph[a] / inc[a]; s[a] -= x + x - x * x - 1.
    b = ph > 1. - inc
    x = (ph[b] - 1.) / inc[b]; s[b] -= x * x + x + x + 1.
    return s


def _string_note(m, dur, att, rel, vib, rng):
    """one bowed string-section note: 3 detuned saws, delayed light vibrato, slow drift, raised-cosine attack/release"""
    n = int((dur + rel) * _R); t = np.arange(n) / _R; f0 = hz(m)
    out = np.zeros(n)
    ramp = np.clip((t - .35) / .8, 0., 1.)
    for c in (-7., 1., 6.5):
        c += rng.uniform(-1.5, 1.5)
        rate = rng.uniform(4.8, 5.6); p = rng.uniform(0, 2 * np.pi); dr = rng.uniform(.08, .17)
        f = f0 * 2 ** (c / 1200.) * (1. + vib * ramp * np.sin(2 * np.pi * rate * t + p) + .0009 * np.sin(2 * np.pi * dr * t + p * 2))
        out += _saw(f, rng.uniform(0, 1))
    env = np.ones(n)
    a = min(n, int(att * _R)); env[:a] = .5 - .5 * np.cos(np.pi * np.arange(a) / max(a, 1))
    r0 = int(dur * _R); r = n - r0
    if r > 0: env[r0:] *= .5 + .5 * np.cos(np.pi * np.arange(r) / r)
    return out * env / 3.


def _shape(x, hp=None, lp=None, lp_order=2):
    """zero-phase smooth filters (Butterworth-like magnitudes) by FFT at the internal rate, padded so nothing wraps"""
    n = len(x); N = 1 << int(np.ceil(np.log2(n + _R // 2)))
    X = np.fft.rfft(x, N); f = np.fft.rfftfreq(N, 1. / _R); H = np.ones_like(f)
    if hp: H /= np.sqrt(1. + (hp / np.maximum(f, 1e-3)) ** 4)
    if lp: H /= np.sqrt(1. + (f / lp) ** (2 * lp_order))
    return np.fft.irfft(X * H, N)[:n]


def _upsample(x, hp):
    """internal rate -> SR (exactly x2) by zero-padding the spectrum, with the master high-pass in the same pass"""
    n = len(x); N = 1 << int(np.ceil(np.log2(n + _R // 2)))
    X = np.fft.rfft(x, N); f = np.fft.rfftfreq(N, 1. / _R)
    X /= np.sqrt(1. + (hp / np.maximum(f, 1e-3)) ** 4); X[-1] = 0.
    Y = np.zeros(N + 1, complex); Y[:N // 2 + 1] = X
    return np.fft.irfft(Y, 2 * N)[:2 * n] * 2.


@functools.lru_cache(maxsize=1)
def _room():
    """impulse response of a small hall: pre-delay, early reflections, diffuse tail decaying faster in the treble"""
    rng = np.random.default_rng(1515); n = int(2.4 * _R); t = np.arange(n) / _R
    X = np.fft.rfft(rng.standard_normal(n)); f = np.fft.rfftfreq(n, 1. / _R)
    bands = [(f < 400.), (f >= 400.) & (f < 3000.), (f >= 3000.)]
    ir = np.zeros(n)
    for msk, rt in zip(bands, (1.7, 1.45, .8)):
        ir += np.fft.irfft(X * msk, n) * np.exp(-6.91 * t / rt)
    ir *= np.clip((t - .018) / .03, 0., 1.)                              # 18 ms pre-delay, diffuse build-up
    ir /= np.sqrt(np.sum(ir ** 2))
    for d, g in ((.011, .42), (.017, -.33), (.023, .28), (.031, -.22), (.043, .17), (.059, -.12)):
        ir[int(d * _R)] += g
    return ir / np.sqrt(np.sum(ir ** 2))


def _convolve(x, h):
    N = 1 << int(np.ceil(np.log2(len(x) + len(h))))
    return np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(h, N), N)[:len(x) + len(h) - 1]


def _bar_curve(levels, P, t):
    """piecewise-linear per-bar levels, periodic over the cycle (continuous across the loop point)"""
    nb = len(levels); x = np.arange(nb + 1) * P / nb / SR
    return np.interp(np.mod(t, P / SR), x, list(levels) + [levels[0]])


def _render_span(style, t_end):
    """the performance of one cycle (events with onset < t_end): dry piano + strings -> room -> master high-pass, made
    at the internal rate and returned at SR, starting _PRE samples before the cycle"""
    sp = STYLES[style]; P, piano, strings = _score(style); pre = _PRE // 2; q = int(.02 * _R)
    events = [e for e in piano if e[0] < t_end]
    n = pre + int((max([e[0] + e[2] for e in events] + [0.]) + 2.) * _R)
    dry_p = np.zeros(n); cache = {}
    for t0, m, hold, vel in events:
        vq = round(vel * 8.) / 8.; nh = max(1, int(round(hold * _R / q))) * q; key = (m, vq, nh)     # hold on a 20 ms grid
        if key not in cache: cache[key] = _piano_shape(m, vq, nh, sp['corda'])
        x = cache[key] * vel ** 1.3; o = pre + int(round(t0 * _R))
        if o + len(x) > n: x = x[:n - o]
        dry_p[o:o + len(x)] += x
    sevents = [e for e in strings if e[0] < t_end]
    n_s = pre + int((max([e[1] for e in sevents] + [0.]) + sp['release'] + 1.) * _R)
    dry_s = np.zeros(max(n, n_s))
    for i, (t0, t1, m, g, v) in enumerate(strings):
        rng = np.random.default_rng(sp['seed'] * 100 + i)                 # one generator per string note: order-free
        if t0 >= t_end: continue
        x = _string_note(m, t1 - t0 - .05, sp['attack'], sp['release'], sp['vibrato'], rng) * g
        o = pre + int(round(t0 * _R)); dry_s[o:o + len(x)] += x[:len(dry_s) - o]
    dry_s = _shape(dry_s, hp=110., lp=sp['cutoff'], lp_order=3)
    dry_s *= _bar_curve(sp['cordes'], P, (np.arange(len(dry_s)) - pre) / _R) * sp['strings']
    if len(dry_p) < len(dry_s): dry_p = np.pad(dry_p, (0, len(dry_s) - len(dry_p)))
    wp, ws = sp['wet']
    out = _convolve(dry_p * wp + dry_s * ws, _room()); out[:len(dry_p)] += dry_p + dry_s
    return _upsample(out, 70.) * sp['gain']


@functools.lru_cache(maxsize=3)
def _cycle(style):
    """(first cycle, looping cycle): the looping one carries the tails of the previous cycle and the pre-roll of the next"""
    P = _score(style)[0]
    W = _render_span(style, P / SR + 1.)
    first = np.zeros(P); cyc = np.zeros(P)
    for i in range(-1, len(W) // P + 2):                                  # V(x) = W[x + _PRE]; cyc(u) = sum_i V(u + iP)
        a = i * P + _PRE; lo, hi = max(a, 0), min(a + P, len(W))
        if hi <= lo: continue
        cyc[lo - a:hi - a] += W[lo:hi]
        if i <= 0: first[lo - a:hi - a] += W[lo:hi]
    first = first.astype(np.float32); cyc = cyc.astype(np.float32)
    first.flags.writeable = False; cyc.flags.writeable = False
    return first, cyc


def cycle_seconds(style):
    """length of one loop of the style (s)"""
    return _score(style)[0] / SR


def render(style, dur):
    """`dur` seconds of the style, float32 mono at SR, exactly round(dur * SR) samples"""
    if style not in STYLES: raise KeyError(f'style de musique inconnu : {style}')
    n = int(round(float(dur) * SR))
    if n <= 0: return np.zeros(0, np.float32)
    P = _score(style)[0]
    if n <= P - _PRE:                                                     # shorter than a loop: render only what is heard
        W = _render_span(style, n / SR + .5)
        out = np.zeros(n); m = min(n, len(W) - _PRE); out[:m] = W[_PRE:_PRE + m]
        out = out.astype(np.float32)
    else:
        first, cyc = _cycle(style)
        k = int(np.ceil(max(0, n - P) / P))
        out = np.concatenate([first] + [cyc] * k)[:n].copy()
    e = min(n // 2, int(.01 * SR))                                        # no click where the piece is cut
    if e > 1: out[-e:] *= (.5 + .5 * np.cos(np.pi * np.arange(e) / e)).astype(np.float32)
    return out


def musique_piano_triste(dur=60.):
    """piano + strings, A minor, 62 bpm: mourning in the rain (warm, not lugubrious)"""
    return render('triste', dur)


def musique_piano_tendre(dur=60.):
    """piano + strings, D major with its relative minor colours, 68 bpm: late afternoon, friendship memories"""
    return render('tendre', dur)


def musique_piano_suspens(dur=60.):
    """sparse piano + held strings, add9 / sus4 chords left open, 60 bpm: a hard choice, no horror tension"""
    return render('suspens', dur)
