"""« La marche » : the original score of the brief (section 8), synthesised here with NumPy. No sample, no API, no voice.

Tempo 80 (a bar = 3 s). Each world lasts two bars; beat 1 falls 0.6 s after the world starts. ONE four-note motif
(F# - A - D - E) crosses the whole piece and is re-orchestrated at every world. A breath rises during each dissolve,
a hit lands on the first beat of worlds 4 to 7 (stronger at the battle), the last world climbs to a D major chord with
a choir at the moment the light takes over (59 s), and rings until the end. Loudness is brought to about -13 LUFS
by ffmpeg's loudnorm afterwards.

    python tools/la_marche_music.py [out.wav]
"""
import sys, math, subprocess
from pathlib import Path
import numpy as np

SR = 48000
DUR = 61.0
BPM = 80.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT
T0 = [0, 6, 12, 18, 24, 30, 36, 42, 48, 54]
LEAD = 0.6                                       # beat 1 falls 0.6 s after the world starts
N = int(DUR * SR)
rng = np.random.default_rng(80)


def hz(m): return 440.0 * 2 ** ((m - 69) / 12.0)


# MIDI numbers of the motif: F#4 A4 D5 E5
MOTIF = [66, 69, 74, 76]
t_ = np.arange(int(8 * SR)) / SR


class Mix:
    def __init__(self): self.L = np.zeros(N, np.float32); self.R = np.zeros(N, np.float32); self.wet = np.zeros(N, np.float32)

    def add(self, t, sig, gain=1.0, pan=0.0, wet=0.2):
        i = int(round(t * SR))
        if i >= N or i + len(sig) <= 0: return
        a = max(0, -i); b = min(len(sig), N - i); s = sig[a:b] * gain
        l = math.cos((pan + 1) * math.pi / 4); r = math.sin((pan + 1) * math.pi / 4)
        self.L[i + a:i + b] += s * l; self.R[i + a:i + b] += s * r; self.wet[i + a:i + b] += s * wet


def env(n, a=0.01, d=0.2, s=0.6, r=0.1):
    e = np.ones(n, np.float32); na = max(1, int(a * SR)); nd = int(d * SR); nr = min(n, int(r * SR))
    e[:na] = np.linspace(0, 1, na)
    if nd > 0 and na + nd < n: e[na:na + nd] = np.linspace(1, s, nd); e[na + nd:] = s
    elif na < n: e[na:] = np.linspace(1, s, n - na) if nd > 0 else 1
    if nr > 0: e[-nr:] *= np.linspace(1, 0, nr)
    return e


def lp(x, fc):
    """brick-wall-ish low-pass by FFT (fine for synthesis, not for measurement)"""
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); X *= 1 / (1 + (f / fc) ** 4); return np.fft.irfft(X, len(x)).astype(np.float32)


def bp(x, f0, f1):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); X *= ((f > f0) & (f < f1)); return np.fft.irfft(X, len(x)).astype(np.float32)


def saw(f, n, detune=0.0, vib=0.0, vf=5.0):
    t = np.arange(n) / SR; ph = 2 * np.pi * f * t
    if vib: ph = ph + vib * np.sin(2 * np.pi * vf * t)
    out = np.zeros(n, np.float32)
    for k in range(1, 14):
        if f * k * (1 + detune) > 9000: break
        out += np.sin(k * ph * (1 + detune)) / k
    return out * .5


def piano(m, dur=1.6, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; f = hz(m); o = np.zeros(n, np.float32)
    for k, a in enumerate([1, .55, .3, .18, .1, .06], 1):
        o += a * np.sin(2 * np.pi * f * k * (1 + .0004 * k * k) * t) * np.exp(-t * (2.2 + k * 1.1) * (1 if m > 55 else .6))
    o *= (1 - np.exp(-t * 400)); return o * vel * .35


def pluck(m, dur=1.0, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; f = hz(m)
    o = np.sin(2 * np.pi * f * t) * np.exp(-t * 7) + .4 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 12)
    return (o * (1 - np.exp(-t * 600))).astype(np.float32) * vel * .4


def bell(m, dur=3.0, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; f = hz(m); o = np.zeros(n, np.float32)
    for r_, a, d in [(1, 1, 1.4), (2.76, .5, 2), (5.4, .3, 3), (8.93, .15, 4)]:
        o += a * np.sin(2 * np.pi * f * r_ * t) * np.exp(-t * d)
    return (o * (1 - np.exp(-t * 800))).astype(np.float32) * vel * .25


def glass(m, dur=3.5, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; f = hz(m)
    o = np.sin(2 * np.pi * f * t) + .45 * np.sin(2 * np.pi * f * 3.01 * t) * np.exp(-t * 1.3) + .2 * np.sin(2 * np.pi * f * 5.02 * t) * np.exp(-t * 2)
    return (o * np.minimum(1, t / .02) * np.exp(-t * .9)).astype(np.float32) * vel * .22


def strings(m, dur, vel=1.0, bright=2200):
    n = int(dur * SR); o = saw(hz(m), n, 0.0) + saw(hz(m), n, .004) + saw(hz(m), n, -.004)
    o = lp(o, bright) * env(n, a=min(.5, dur / 3), d=0, s=1, r=min(.6, dur / 3)); return o * vel * .16


def cello(m, dur, vel=1.0):
    n = int(dur * SR); o = saw(hz(m), n, 0, vib=.006, vf=5.2); o = lp(o, 1400) * env(n, a=.12, d=.3, s=.8, r=.25); return o * vel * .34


def brass(m, dur, vel=1.0):
    n = int(dur * SR); o = saw(hz(m), n, 0) + .6 * saw(hz(m), n, .002); t = np.arange(n) / SR
    o = lp(o, 1000 + 2500 * np.minimum(1, t / .25).mean()) * env(n, a=.08, d=.2, s=.85, r=.15); return o * vel * .3


def theremin(m0, m1, dur, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; f = hz(m0) * (hz(m1) / hz(m0)) ** np.minimum(1, t / (dur * .35))
    ph = 2 * np.pi * np.cumsum(f * (1 + .012 * np.sin(2 * np.pi * 5.8 * t))) / SR
    return (np.sin(ph) + .25 * np.sin(2 * ph)).astype(np.float32) * env(n, a=.2, d=0, s=1, r=.3) * vel * .22


def synth_bass(m, dur, vel=1.0):
    n = int(dur * SR); o = saw(hz(m), n); o = lp(o, 600) * env(n, a=.005, d=.1, s=.5, r=.05); return o * vel * .45


def pad(ms, dur, vel=1.0, bright=1500):
    return sum(strings(m, dur, 1.0, bright) for m in ms) * vel


def choir(ms, dur, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; out = np.zeros(n, np.float32)
    for m in ms:
        for dt_ in (-.006, 0, .007):
            s = saw(hz(m) * (1 + dt_), n, 0, vib=.004, vf=4.6 + 3 * abs(dt_) * 100)
            out += bp(s, 400, 1100) * 1.4 + bp(s, 1800, 2700) * .5 + bp(s, 100, 400) * .6
    return out * env(n, a=1.0, d=0, s=1, r=2.0) * vel * .07


def noise_band(dur, f0, f1, sweep=False):
    n = int(dur * SR); x = rng.standard_normal(n).astype(np.float32)
    return bp(x, f0, f1)


def whoosh(dur=1.2, vel=1.0):
    n = int(dur * SR); x = rng.standard_normal(n).astype(np.float32); out = np.zeros(n, np.float32)
    for a, b in ((200, 700), (700, 2200), (2200, 6000)):
        out += bp(x, a, b) * (1 if a < 2000 else .6)
    t = np.arange(n) / SR; return out * np.sin(np.pi * np.minimum(1, t / dur) ** 1.4) ** 2 * vel * .12


def kick(vel=1.0):
    n = int(.5 * SR); t = np.arange(n) / SR; f = 45 + 110 * np.exp(-t * 30)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)).astype(np.float32) * vel * .8


def taiko(vel=1.0):
    n = int(1.6 * SR); t = np.arange(n) / SR; f = 58 + 60 * np.exp(-t * 14)
    return ((np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.8) + .25 * lp(rng.standard_normal(n).astype(np.float32), 900) * np.exp(-t * 18))).astype(np.float32) * vel


def snare(vel=1.0):
    n = int(.3 * SR); t = np.arange(n) / SR; x = bp(rng.standard_normal(n).astype(np.float32), 1500, 7000)
    return (x * np.exp(-t * 22) * .5 + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25) * .3).astype(np.float32) * vel


def shaker(vel=1.0):
    n = int(.12 * SR); t = np.arange(n) / SR; x = bp(rng.standard_normal(n).astype(np.float32), 5000, 12000)
    return x * np.exp(-t * 40) * vel * .25


def hit(vel=1.0):
    n = int(2.4 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 36 * t) * np.exp(-t * 2.2) + .6 * lp(rng.standard_normal(n).astype(np.float32), 700) * np.exp(-t * 7)).astype(np.float32) * vel * .9


def rain(dur, vel=1.0):
    n = int(dur * SR); x = rng.standard_normal(n).astype(np.float32); x = bp(x, 1800, 9000)
    return x * (.6 + .4 * np.sin(np.linspace(0, 40, n))) * vel * .09


# chords (MIDI), D major world: D, Bm, G, A
D_ = [50, 57, 62, 66]; BM = [47, 54, 59, 62]; G_ = [55, 59, 62, 67]; A_ = [57, 61, 64, 69]; EM = [52, 59, 62, 67]


def score():
    M = Mix()
    for k, t0 in enumerate(T0):
        b0 = t0 + LEAD; b1 = b0 + BAR                    # the two bars of this world
        M.add(t0, whoosh(XF if k else .8, 1.0 if k else .5), 1.0, 0.0, .5) if k else None
        if k == 0:
            for bi, (b, ch) in enumerate(((b0, D_), (b1, G_))):
                for j in range(8):                      # piano arpeggios, eighth notes
                    M.add(b + j * BEAT / 2, piano(ch[[0, 1, 2, 1, 3, 2, 1, 2][j] % 4] + (12 if j in (4, 6) else 0), 1.4, .9), .8, -.2 + .05 * j, .25)
                for j in range(8): M.add(b + j * BEAT / 2 + BEAT / 4, shaker(.7 if j % 2 else 1), 1.0, .3, .05)
                for j, m in enumerate(MOTIF): M.add(b + j * BEAT + (BAR if False else 0), piano(m + 12, 1.8, 1.0), .9, .2, .35)
        elif k == 1:
            for b, ch in ((b0, G_), (b1, A_)): M.add(b, pad(ch, BAR + .6, 1.0), .9, 0, .5)
            for bi, b in enumerate((b0, b1)):
                for j, m in enumerate(MOTIF): M.add(b + j * BEAT + (BEAT / 2 if bi else 0), bell(m + 12, 3.0, 1.0), .8, -.3 + .2 * j, .5)
        elif k == 2:                                    # B minor, cello, the motif comes down
            for b, ch in ((b0, BM), (b1, G_)): M.add(b, pad(ch, BAR + .5, .6, 1000), .7, 0, .5)
            for bi, b in enumerate((b0, b1)):
                for j, m in enumerate(MOTIF[::-1]): M.add(b + j * BEAT, cello(m - 12, BEAT * .95, 1.0), .9, -.1, .4)
        elif k == 3:                                    # rain, E minor, lone piano plucked like drops
            M.add(t0, rain(6.4, 1.0), 1.0, 0.0, .1)
            for bi, (b, ch) in enumerate(((b0, EM), (b1, EM))):
                for j in range(8):
                    M.add(b + j * BEAT / 2, pluck(ch[(j * 3) % 4] + 12 + (12 if j % 4 == 3 else 0), .9, .8), .9, -.3 + .1 * j, .45)
                for j, m in enumerate(MOTIF): M.add(b + j * BEAT + BEAT / 4, piano(m, 2.0, .9), .8, 0, .5)
        elif k == 4:                                    # glass and air
            M.add(b0 - .4, pad([62, 69, 74, 81], 6.4, .35, 4000), .8, 0, .7)
            for bi, b in enumerate((b0, b1)):
                for j, m in enumerate(MOTIF): M.add(b + j * BEAT, glass(m + 12 + (12 if (j + bi) % 2 else 0), 3.5, 1.0), .8, -.5 + .33 * j, .7)
            M.add(b0, hit(.6), .8, 0, .4)
        elif k == 5:                                    # fire: taiko, ostinato bass, tension
            M.add(t0, pad([38, 45, 50], 6.4, .5, 600), .8, 0, .3)
            for bi, b in enumerate((b0, b1)):
                for j in range(4): M.add(b + j * BEAT, taiko(1.0 if j % 2 == 0 else .6), .9, 0, .3)
                for j in range(8): M.add(b + j * BEAT / 2, synth_bass(26 if j % 4 != 3 else 29, BEAT * .45, .9), .9, 0, .1)
                M.add(b + BAR - BEAT * .5, theremin(66, 69, BEAT * .5, .5), .5, .3, .5)
            M.add(b0, hit(1.0), .9, 0, .4)
        elif k == 6:                                    # tutti
            for bi, b in enumerate((b0, b1)):
                for j in range(8): M.add(b + j * BEAT / 2, kick(1.0 if j % 4 == 0 else .0) if j % 4 == 0 else (snare(1.0) if j % 4 == 2 else shaker(.8)), 1.0, 0, .15)
                for j in range(16): M.add(b + j * BEAT / 4, strings(D_[j % 3] + 12, BEAT / 4 * .9, .8, 3000), .8, -.4 + .05 * j, .2)
                for j, m in enumerate(MOTIF): M.add(b + j * BEAT, brass(m - 12 + 12, BEAT * .95, 1.0), 1.0, .1, .3)
                for j, m in enumerate(MOTIF): M.add(b + j * BEAT, brass(m, BEAT * .95, .7), .8, -.2, .3)
            M.add(b0, hit(1.4), 1.0, 0, .4); M.add(b1, hit(.9), 1.0, 0, .4)
        elif k == 7:                                    # invasion: synths and theremin
            for bi, b in enumerate((b0, b1)):
                for j in range(8): M.add(b + j * BEAT / 2, synth_bass([38, 45, 50, 57][j % 4] if bi == 0 else [43, 50, 55, 62][j % 4], BEAT * .45, .8), .9, 0, .1)
                for j, m in enumerate(MOTIF): M.add(b + j * BEAT, theremin(m + (0 if j == 0 else MOTIF[j - 1] - m) * 0 + 12 - 1, m + 12, BEAT * 1.2, 1.0), .8, -.3 + .2 * j, .6)
            M.add(b0, hit(1.0), .9, 0, .4)
        elif k == 8:                                    # ship: round calm pad, arpeggio sequence
            M.add(t0, pad([50, 57, 62, 66], 6.6, .8, 1300), .8, 0, .6)
            for bi, b in enumerate((b0, b1)):
                for j in range(8): M.add(b + j * BEAT / 2, pluck([62, 66, 69, 74, 76, 74, 69, 66][j] + (2 if bi else 0), .8, .7), .8, -.4 + .1 * j, .5)
        elif k == 9:                                    # the Moon: a climb, then D major with choir at 59 s
            M.add(t0 + .3, pad([50, 57, 62], 5.4, .6, 800), .8, 0, .6)
            n = int(5.0 * SR); tt = np.arange(n) / SR
            riser = lp(rng.standard_normal(n).astype(np.float32), 300) + bp(rng.standard_normal(n).astype(np.float32), 2000, 7000) * (tt / 5.0)
            M.add(54.5, riser * (tt / 5.0) ** 2 * .12, 1.0, 0, .5)
            for j, m in enumerate([50, 54, 57, 62, 66, 69, 74, 78]): M.add(b0 + j * BEAT / 2, pluck(m + 12, 1.0, .7 + .04 * j), .9, -.3 + .08 * j, .6)
            for j, m in enumerate(MOTIF): M.add(b1 + j * BEAT, piano(m + 12, 2.6, 1.0), 1.0, .2, .6)
            tc = 59.0
            M.add(tc, pad([38, 50, 57, 62, 66, 69, 74], 6.0, 1.6, 2500), 1.0, 0, .7)
            M.add(tc, choir([62, 66, 69, 74, 78], 6.0, 1.4), 1.0, 0, .8)
            M.add(tc, hit(1.2), 1.0, 0, .5)
            M.add(tc, bell(86, 5.0, 1.0), .8, .3, .8); M.add(tc + .2, bell(90, 5.0, .8), .8, -.3, .8)
    # reverb: a synthetic decaying-noise impulse, applied to the wet bus
    n_ir = int(2.2 * SR); ir = rng.standard_normal(n_ir).astype(np.float32) * np.exp(-np.arange(n_ir) / SR * 2.4)
    ir = lp(ir, 5000); ir[:int(.012 * SR)] *= np.linspace(0, 1, int(.012 * SR))
    nfft = 1 << int(np.ceil(np.log2(N + n_ir))); wet = np.fft.irfft(np.fft.rfft(M.wet, nfft) * np.fft.rfft(ir, nfft), nfft)[:N].astype(np.float32) * .05
    L = M.L + wet; R = M.R + np.roll(wet, int(.011 * SR)) * 1.0
    fade = np.ones(N, np.float32); fade[:int(.05 * SR)] = np.linspace(0, 1, int(.05 * SR)); fade[-int(.3 * SR):] = np.linspace(1, 0, int(.3 * SR))
    out = np.stack([L * fade, R * fade], 1)
    return out / (np.abs(out).max() + 1e-9) * .8


XF = 1.2


def write_wav(path, x):
    import wave
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'projects' / 'la_marche_20261028' / 'la_marche_musique.wav'
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_name('musique_brute.wav'); write_wav(raw, score())
    r = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(raw), '-af', 'loudnorm=I=-13:TP=-1.5:LRA=9,aresample=48000', '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', str(out)], capture_output=True, text=True)
    if r.returncode: raise SystemExit(r.stderr)
    print('musique écrite :', out)


if __name__ == '__main__':
    main()
