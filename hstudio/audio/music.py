"""Procedural background music for non-horror stories (no samples, royalty free, deterministic).
render(style, n_samples) -> mono float32 at synth.SR, mixed under the voice like the horror bed."""
import math, numpy as np
from . import synth as S
SR = S.SR

CHORDS = {'maj': (0, 4, 7), 'min': (0, 3, 7), 'maj7': (0, 4, 7, 11), 'min7': (0, 3, 7, 10), 'dom7': (0, 4, 7, 10), 'sus': (0, 5, 7)}
STYLES = {
    'adventure': dict(bpm=100, key=60, prog=[(0, 'maj'), (7, 'maj'), (9, 'min'), (5, 'maj')], arp='up8', bass='root4', drums='light', pad=.5, melody=True),
    'comedy':    dict(bpm=124, key=65, prog=[(0, 'maj'), (9, 'min'), (2, 'min'), (7, 'dom7')], arp='bounce', bass='oompah', drums='wood', pad=0, melody=True),
    'romance':   dict(bpm=72, key=62, prog=[(0, 'maj7'), (9, 'min7'), (5, 'maj7'), (7, 'dom7')], arp='slow', bass='root1', drums=None, pad=.8, keys=True, melody=True),
    'mystery':   dict(bpm=84, key=57, prog=[(0, 'min'), (8, 'maj'), (3, 'maj'), (10, 'maj')], arp='echo8', bass='pulse', drums='tick', pad=.7),
    'sad':       dict(bpm=64, key=57, prog=[(0, 'min'), (8, 'maj'), (5, 'min'), (7, 'maj')], arp=None, bass='root1', drums=None, pad=.6, keys=True),
    'action':    dict(bpm=140, key=52, prog=[(0, 'min'), (0, 'min'), (8, 'maj'), (10, 'maj')], arp='power', bass='eighths', drums='rock', pad=.3),
    'calm':      dict(bpm=70, key=60, prog=[(0, 'maj'), (5, 'maj'), (9, 'min'), (7, 'sus')], arp='slow', bass='root1', drums=None, pad=.7, keys=True),
    'epic':      dict(bpm=90, key=50, prog=[(0, 'min'), (10, 'maj'), (8, 'maj'), (7, 'maj')], arp='up8', bass='root4', drums='epic', pad=1.0),
}
NAMES = tuple(STYLES) + ('horror', 'none')

def hz(m): return 440. * 2 ** ((m - 69) / 12)

def pluck(f, dur, bright=1., decay=1.):
    n = int(dur * SR); t = np.arange(n) / SR; s = np.zeros(n, np.float32)
    for k in range(1, 7): s += (1 / k) * np.sin(2 * np.pi * k * f * t) * np.exp(-t * (2.5 + 2.2 * k / bright) / decay)
    return (s * np.minimum(1, t / .003)).astype(np.float32)
def keynote(f, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * f * t) + .35 * np.sin(2 * np.pi * 2 * f * t) + .12 * np.sin(2 * np.pi * 3 * f * t)) * np.exp(-t * 1.3) * np.minimum(1, t / .005)
    return s.astype(np.float32)
def pad(fs, dur, att=.5):
    n = int(dur * SR); t = np.arange(n) / SR; s = np.zeros(n, np.float32)
    for f in fs:
        for det in (-.004, .004): s += np.sin(2 * np.pi * f * (1 + det) * t + 2 * np.sin(2 * np.pi * .3 * t) * .01)
    e = np.minimum(1, t / att) * np.minimum(1, (dur - t) / att); return (s * e / max(1, len(fs))).astype(np.float32)
def power(f, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    s = np.tanh(3 * (np.sin(2 * np.pi * f * t) + .7 * np.sin(2 * np.pi * 1.5 * f * t))) * np.exp(-t * 4)
    return S.lp(s.astype(np.float32), 2500)
def bassnote(f, dur, decay=4.):
    n = int(dur * SR); t = np.arange(n) / SR
    return ((np.sin(2 * np.pi * f * t) + .3 * np.sin(4 * np.pi * f * t)) * np.exp(-t * decay) * np.minimum(1, t / .004)).astype(np.float32)
def kick(): return S.thump(120, .28, 45, .09) * 1.1
def snare():
    n = int(.18 * SR); return (S.band(S.noise(n), 1200, 6000) * S.env(n, .001, .05) * .7 + S.tone(190, .18, .001, .04) * .5).astype(np.float32)
def hat(d=.025): n = int(.08 * SR); return (S.hp(S.noise(n), 7000) * S.env(n, .0005, d)).astype(np.float32)
def wood(): return S.click(.05, 1800) * .8
def tick(): return S.click(.03, 3200) * .5

def render(style, n, seed=0, intensity=None):
    """n samples of music in the given style (looping chord progression, arpeggio, bass, drums, optional melody)"""
    out = np.zeros(n, np.float32)
    if style not in STYLES: return out
    c = STYLES[style]; S.reseed(1000 + seed); rng = np.random.default_rng(77 + seed)
    beat = 60. / c['bpm']; bar = 4 * beat; dur = n / SR; key = c['key']
    def put(sig, t, g=1.):
        S.addat(out, int(t * SR), sig * g)
    scale = [0, 2, 4, 5, 7, 9, 11] if CHORDS[c['prog'][0][1]][1] == 4 else [0, 2, 3, 5, 7, 8, 10]
    mel_prev = 7; bi = 0; tt = 0.
    while tt < dur:
        root, q = c['prog'][bi % len(c['prog'])]; tones = [key + root + i for i in CHORDS[q]]
        inten = float(intensity[min(len(intensity) - 1, int(tt * SR))]) if intensity is not None else .5
        if c.get('pad'): put(pad([hz(m - 12) for m in tones], bar + .4, .6), tt, .055 * c['pad'])
        if c.get('keys'):
            for j, m in enumerate(tones[:3]): put(keynote(hz(m), bar), tt + j * .14, .05)
        a = c.get('arp')
        if a == 'up8':
            seq = tones + [tones[0] + 12]
            for i in range(8): put(pluck(hz(seq[i % len(seq)] + 12), beat * .9), tt + i * beat / 2, .045)
        elif a == 'bounce':
            pat = [1, 0, 1, 1, 0, 1, 0, 1]
            for i in range(8):
                if pat[i]: put(pluck(hz(tones[i % len(tones)] + 12), .2, 1.6, .35), tt + i * beat / 2, .05)
        elif a == 'slow':
            seq = tones + [tones[1] + 12]
            for i in range(4): put(pluck(hz(seq[i % len(seq)] + 12), beat * 1.8, .8, 1.6), tt + i * beat, .04)
        elif a == 'echo8':
            seq = [tones[0], tones[2], tones[1], tones[2]]
            for i in range(8):
                nt = pluck(hz(seq[i % 4] + 12), beat, .9, 1.2); put(nt, tt + i * beat / 2, .04); put(nt, tt + i * beat / 2 + beat * .75, .016)
        elif a == 'power':
            for i in range(8):
                if i % 4 != 3: put(power(hz(tones[0]), beat * .45), tt + i * beat / 2, .035)
        b = c.get('bass')
        if b == 'root4':
            for i in range(4): put(bassnote(hz(tones[0] - 24), beat * .9), tt + i * beat, .09)
        elif b == 'oompah':
            for i in range(4): put(bassnote(hz((tones[0] if i % 2 == 0 else tones[2]) - 24), beat * .5, 9), tt + i * beat, .1)
        elif b == 'root1': put(bassnote(hz(tones[0] - 24), bar, 1.2), tt, .08)
        elif b == 'pulse':
            for i in range(4): put(bassnote(hz(tones[0] - 24), beat * .8, 6), tt + i * beat, .07)
        elif b == 'eighths':
            for i in range(8): put(bassnote(hz(tones[0] - 24), beat * .45, 10), tt + i * beat / 2, .1)
        d = c.get('drums'); dg = .6 + .6 * inten
        if d == 'light':
            for i in range(4):
                if i % 2 == 0: put(kick(), tt + i * beat, .22 * dg)
                put(hat(), tt + i * beat + beat / 2, .05 * dg)
        elif d == 'wood':
            for i in range(4): put(wood(), tt + i * beat + (beat / 2 if i % 2 else 0), .1)
        elif d == 'tick':
            for i in range(8): put(tick(), tt + i * beat / 2, .05 if i % 2 else .08)
        elif d == 'rock':
            for i in range(4):
                put(kick(), tt + i * beat, .3 * dg) if i % 2 == 0 else put(snare(), tt + i * beat, .2 * dg)
                put(hat(), tt + i * beat + beat / 2, .06 * dg); put(hat(), tt + i * beat, .04 * dg)
        elif d == 'epic':
            put(kick(), tt, .35 * dg); put(kick(), tt + beat * 2.5, .25 * dg); put(S.boom(1.4, 50), tt, .12 * dg)
        if c.get('melody'):                   # gentle stepwise melody on chord tones
            steps = 4 if c['bpm'] < 90 else 8
            for i in range(steps):
                if rng.random() < .3: continue
                if i % (steps // 2) == 0: deg = rng.choice([0, 2, 4])
                else: deg = int(np.clip(mel_prev + rng.choice([-1, 1, -2, 2]), 0, 9))
                mel_prev = deg; m = key + 12 + scale[deg % 7] + 12 * (deg // 7)
                ln = bar / steps
                put(keynote(hz(m), ln * 1.6) if c.get('keys') else pluck(hz(m), ln * 1.4, 1.2, 1.4), tt + i * ln, .035)
        tt += bar; bi += 1
    f = min(int(1.5 * SR), n // 2); r = np.ones(n, np.float32)
    if f > 0: r[:f] = np.linspace(0, 1, f); r[n - f:] = np.minimum(r[n - f:], np.linspace(1, 0, f))
    return out * r
