"""Procedural sound effects (no samples, royalty free). Every function returns a mono float32 array at SR."""
import math, numpy as np
SR = 44100
_rng = np.random.default_rng(42)
def reseed(seed): global _rng; _rng = np.random.default_rng(seed)

def addat(x, o, c):
    if o >= len(x) or o + len(c) <= 0: return
    if o < 0: c = c[-o:]; o = 0
    m = min(len(c), len(x) - o); x[o:o + m] += c[:m]
def env(n, a=.002, d=.1):
    t = np.arange(n) / SR; return (np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(d, 1e-4))).astype(np.float32)
def noise(n): return _rng.standard_normal(n).astype(np.float32)
def band(x, lo, hi):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); X[(f < lo) | (f > hi)] = 0; return np.fft.irfft(X, len(x)).astype(np.float32)
def lp(x, fc): return band(x, 0, fc)
def hp(x, fc): return band(x, fc, SR)
def brown(n):
    w = noise(n); b = np.cumsum(w); b -= np.convolve(b, np.ones(4410) / 4410, 'same'); return (b / (np.abs(b).max() + 1e-9)).astype(np.float32)
def sweep_sin(f0, f1, dur, curve=18):
    n = int(dur * SR); t = np.arange(n) / SR; fr = f1 + (f0 - f1) * np.exp(-t * curve)
    return np.sin(2 * np.pi * np.cumsum(fr) / SR).astype(np.float32)
def thump(f0=60, dur=.25, f1=30, d=None): n = int(dur * SR); return sweep_sin(f0, f1, dur) * env(n, .001, d or dur / 3)
def click(dur=.03, f=2200):
    n = int(dur * SR); t = np.arange(n) / SR
    return (noise(n) * env(n, .0004, dur / 5) * .6 + np.sin(2 * np.pi * f * t) * env(n, .0004, dur / 4) * .4).astype(np.float32)
def tone(f, dur, a=.005, d=None, shape='sin'):
    n = int(dur * SR); t = np.arange(n) / SR; s = np.sin(2 * np.pi * f * t)
    if shape == 'saw': s = 2 * ((f * t) % 1) - 1
    if shape == 'square': s = np.sign(s)
    if shape == 'tri': s = 2 * np.abs(2 * ((f * t) % 1) - 1) - 1
    return (s * env(n, a, d or dur / 3)).astype(np.float32)
def boom(dur=1.6, f=42):
    n = int(dur * SR); return (sweep_sin(f * 1.8, f, dur, 6) * env(n, .003, dur / 2.5) + lp(noise(n), 160) * env(n, .002, dur / 4) * .8).astype(np.float32)
def whoosh(dur=.7, lo=200, hi=4000, rev=False):
    n = int(dur * SR); e = np.sin(np.linspace(0, np.pi, n)) ** 1.5
    if rev: e = np.linspace(0, 1, n) ** 3
    return (band(noise(n), lo, hi) * e).astype(np.float32)
def screech(dur=2.2, base=1300):
    n = int(dur * SR); t = np.arange(n) / SR; s = np.zeros(n, np.float32)
    for k, f in enumerate([base, base * 1.059, base * 1.122, base * 1.414, base * .5 * 1.03]):
        vib = 1 + .006 * np.sin(2 * np.pi * (5.5 + k) * t)
        s += (2 * ((f * np.cumsum(vib) / SR) % 1) - 1) * (.6 if k < 4 else .4)
    s = band(s, 400, 6000) * (1 + .5 * np.sin(2 * np.pi * 13 * t))
    return (s * env(n, .015, dur / 2.2) * .35).astype(np.float32)
def riser(dur=1.0):
    n = int(dur * SR); return (band(noise(n), 800, 9000) * np.linspace(0, 1, n) ** 3).astype(np.float32)
def step(heavy=1., wet=True, soft=False):
    n = int(.25 * SR); a = np.zeros(n, np.float32)
    addat(a, 0, thump(90 * (.8 + .4 * _rng.random()), .12, 45) * .9)
    if not soft: a += hp(noise(n), 900) * env(n, .0003, .012) * .55
    else: a += band(noise(n), 200, 1500) * env(n, .002, .03) * .3
    if wet: a += band(noise(n), 2500, 9000) * env(n, .004, .05) * .25
    return a * heavy
def glass_crack():
    n = int(.4 * SR); x = np.zeros(n, np.float32)
    for _ in range(int(_rng.integers(3, 8))):
        addat(x, int(_rng.uniform(0, .25) * SR), click(.015, _rng.uniform(2500, 7000)) * _rng.uniform(.4, 1))
    return x + band(noise(n), 1500, 5000) * env(n, .001, .06) * .3
def shatter(dur=2.4):
    n = int(dur * SR); x = hp(noise(n), 2000) * env(n, .001, .22) * 1.1
    for _ in range(110):
        tt = _rng.uniform(0, dur * .85) ** 1.4
        addat(x, int(tt * SR), tone(_rng.uniform(2500, 9000), .06, .0005, .015) * _rng.uniform(.2, .9) * math.exp(-tt * 1.6))
    return x
def metal_hit(f=180, dur=1.2):
    n = int(dur * SR); s = np.zeros(n, np.float32)
    for r, a in ((1, 1), (2.76, .6), (5.4, .4), (8.9, .25)): s += tone(f * r, dur, .001, dur / (2 + r)) * a
    return s * .5 + band(noise(n), 200, 3000) * env(n, .001, .03) * .6
def creak(dur=1.2, f=380):
    n = int(dur * SR); t_ = np.arange(n) / SR
    fr = f * (1 + .3 * np.sin(2 * np.pi * .7 * t_)); ph = np.cumsum(fr) / SR
    pulses = (np.sin(2 * np.pi * ph) > .96).astype(np.float32)
    return (band(pulses * 2 + noise(n) * .05, 200, 3000) * np.sin(np.linspace(0, np.pi, n)) ** .5).astype(np.float32)
def growl(dur=2.0):
    n = int(dur * SR); t_ = np.arange(n) / SR
    am = (1 + np.sin(2 * np.pi * 28 * t_)) * (1 + .5 * np.sin(2 * np.pi * 3 * t_))
    out = band(noise(n), 60, 500) * am * np.sin(np.linspace(0, np.pi, n)) * .7; addat(out, 0, tone(55, dur, .2, dur) * .3); return out.astype(np.float32)
def buzz(dur=.4, f=120):
    n = int(dur * SR); t_ = np.arange(n) / SR; s = np.sign(np.sin(2 * np.pi * f * t_)) * .5 + band(noise(n), 2000, 8000) * .5
    return (s * (_rng.random(n) > .3) * env(n, .002, dur)).astype(np.float32)
def heartbeat(gain=1.):
    out = np.zeros(int(.5 * SR), np.float32); addat(out, 0, thump(58, .22, 36)); addat(out, int(.21 * SR), thump(50, .2, 33) * .7); return out * gain
def ding():
    a = tone(1046.5, 1.6, .002, .7); b = tone(1046.5 * 2.76, 1.0, .002, .25); a[:len(b)] += b * .3; return a * .5
def laugh(dur=2.6, f0=95):
    n = int(dur * SR); t_ = np.arange(n) / SR
    f = f0 * (1 + .08 * np.sin(2 * np.pi * .8 * t_)) * np.linspace(1.15, .85, n)
    ph = np.cumsum(f) / SR; pulse = ((ph % 1) < .08).astype(np.float32) - .08
    src = pulse + noise(n) * .25
    voc = band(src, 500, 900) + band(src, 1000, 1400) * .6 + band(src, 2300, 2800) * .3
    rate = 5.5 + 1.5 * t_ / dur; gate = np.clip(np.sin(2 * np.pi * np.cumsum(rate) / SR) * 1.6, 0, 1) ** 1.5
    return (voc * gate * np.sin(np.linspace(0, np.pi, n)) ** .4 * 1.4).astype(np.float32)
def notif():
    out = np.zeros(int(.7 * SR), np.float32); addat(out, 0, tone(1318.5, .35, .003, .12)); addat(out, int(.12 * SR), tone(1760, .5, .003, .18)); return out * .5
def vibrate(dur=.45):
    n = int(dur * SR); t_ = np.arange(n) / SR
    return (np.sign(np.sin(2 * np.pi * 165 * t_)) * .4 * (1 + .3 * np.sin(2 * np.pi * 30 * t_)) * np.minimum(1, t_ / .01) * np.minimum(1, (dur - t_) / .02)).astype(np.float32)
def crumble(dur=1.2):
    n = int(dur * SR); x = band(noise(n), 150, 2500) * env(n, .01, dur / 3) * .5
    for _ in range(14): addat(x, int(_rng.uniform(0, dur * .7) * SR), thump(_rng.uniform(70, 160), .1, 50) * _rng.uniform(.2, .6))
    return x
def knock(n_=3, gap=.32):
    out = np.zeros(int((n_ * gap + .4) * SR), np.float32)
    for k in range(n_):
        o = int(k * gap * SR); addat(out, o, thump(140, .18, 80) * .9); addat(out, o, band(noise(int(.08 * SR)), 300, 2500) * env(int(.08 * SR), .001, .02) * .5)
    return out
def door_open(): return creak(1.4, 320) * .7 + np.pad(whoosh(1.2, 80, 600), (0, max(0, int(1.4 * SR) - int(1.2 * SR))))[:int(1.4 * SR)] * .4
def door_slam():
    out = metal_hit(110, 1.6); addat(out, 0, boom(1.4, 42)); return out
def door_handle(): out = click(.05, 1200); out = np.pad(out, (0, int(.3 * SR))); addat(out, int(.1 * SR), click(.04, 900)); return out
def lock_rattle():
    out = np.zeros(int(1.0 * SR), np.float32)
    for k in range(5): addat(out, int(k * .17 * SR), metal_hit(220, .4) * .5)
    return out
def button(): out = click(.04, 1700); addat(out, 0, tone(1650, .08, .002, .03) * .3); return out
def elevator_motor(dur=2.0): return (whoosh(dur, 60, 700) * 1.0).astype(np.float32)
def elevator_ding(): return ding()
def static_burst(dur=.8):
    n = int(dur * SR); return (band(noise(n), 300, 9000) * np.linspace(1, 0, n) ** .5 * .5).astype(np.float32)
def breath(dur=2.5, tense=True):
    n = int(dur * SR); t_ = np.arange(n) / SR; rate = 1.4 if tense else .7
    e = np.clip(np.sin(2 * np.pi * rate * t_), 0, 1) ** 2
    return (band(noise(n), 300, 2500) * e * .35).astype(np.float32)
def whisper_noise(dur=1.5):
    n = int(dur * SR); e = np.abs(np.sin(np.linspace(0, 9, n))) ** 3
    return (band(noise(n), 2500, 9000) * e * .4).astype(np.float32)
def drip():
    return tone(_rng.uniform(900, 1600), .08, .001, .02) * .3
def thunder(dur=4.0):
    n = int(dur * SR); x = lp(brown(n), 260) * env(n, .05, dur / 2) * 1.6; addat(x, 0, boom(2.0, 36)); return x
def rain(dur=4.0, heavy=.6):
    n = int(dur * SR); x = band(noise(n), 800, 9000) * .12 * heavy
    for _ in range(int(dur * 60 * heavy)): addat(x, int(_rng.uniform(0, dur) * SR), click(.006, _rng.uniform(3000, 8000)) * _rng.uniform(.05, .2))
    return x
def tv_static(dur=2.0): return (hp(noise(int(dur * SR)), 1500) * .25).astype(np.float32)
def phone_ring(dur=2.4):
    n = int(dur * SR); t_ = np.arange(n) / SR
    s = (np.sin(2 * np.pi * 440 * t_) + np.sin(2 * np.pi * 480 * t_)) * .2 * ((t_ % 1.2) < .8)
    return s.astype(np.float32)
def clock_tick(n_=8, gap=.5):
    out = np.zeros(int((n_ * gap + .2) * SR), np.float32)
    for k in range(n_): addat(out, int(k * gap * SR), click(.03, 1000 if k % 2 else 1300) * .7)
    return out
def glitch_sfx(dur=.5):
    n = int(dur * SR); s = np.sign(np.sin(2 * np.pi * np.cumsum(_rng.uniform(80, 2000, n)) / SR)) * .3
    return (s * (_rng.random(n) > .5) * env(n, .001, dur)).astype(np.float32)
def sting(dur=2.2, base=1150): return screech(dur, base)
def impact(): out = boom(1.6, 40); addat(out, 0, thump(70, .3, 30)); return out
def footsteps_run(dur=2.0, rate=3.5, wet=True):
    out = np.zeros(int((dur + .3) * SR), np.float32); t = 0; k = 0
    while t < dur: addat(out, int(t * SR), step(1., wet) * (1 if k % 2 == 0 else .82)); t += 1 / rate; k += 1
    return out
def footsteps_walk(dur=2.0, wet=False): return footsteps_run(dur, 1.9, wet)
def footsteps_heavy(dur=2.0): return footsteps_run(dur, 1.6, True) * 1.3
def skitter(dur=1.5):
    out = np.zeros(int(dur * SR), np.float32)
    for t in np.arange(0, dur, .12): addat(out, int((t + _rng.uniform(0, .05)) * SR), click(.01, _rng.uniform(3000, 6500)) * .5)
    return out

# ---- chiptune (CONSOLE style)
def chip_note(f, dur, duty=.5, vol=.25):
    n = int(dur * SR); t_ = np.arange(n) / SR; ph = (f * t_) % 1
    return ((ph < duty).astype(np.float32) * 2 - 1) * env(n, .002, dur * .8) * vol
def chip_blip(): out = chip_note(1320, .06, .25, .3); addat(out, int(.05 * SR), chip_note(1760, .08, .25, .3)); return np.pad(out, (0, 2000))
def chip_alert():
    out = np.zeros(int(.8 * SR), np.float32)
    for k in range(4): addat(out, int(k * .18 * SR), chip_note(880 if k % 2 == 0 else 660, .12, .5, .3))
    return out
def chip_gameover():
    out = np.zeros(int(1.6 * SR), np.float32)
    for k, f in enumerate((659, 587, 523, 392, 330)): addat(out, int(k * .26 * SR), chip_note(f, .3, .5, .3))
    return out
def chip_save():
    out = np.zeros(int(1.0 * SR), np.float32)
    for k, f in enumerate((523, 659, 784, 1046)): addat(out, int(k * .09 * SR), chip_note(f, .12, .25, .25))
    return out
def chip_pause(): out = chip_note(988, .08, .5, .3); addat(out, int(.1 * SR), chip_note(784, .12, .5, .3)); return np.pad(out, (0, 3000))

SFX = {
    'heartbeat': heartbeat, 'boom': boom, 'impact': impact, 'sting': sting, 'screech': screech, 'riser': riser,
    'whoosh': whoosh, 'whoosh_rev': lambda: whoosh(.8, 200, 6000, True), 'glass_crack': glass_crack, 'glass_shatter': shatter,
    'metal_hit': metal_hit, 'creak': creak, 'growl': growl, 'buzz': buzz, 'neon_buzz': lambda: buzz(.3), 'ding': ding,
    'elevator_ding': elevator_ding, 'elevator_motor': elevator_motor, 'laugh': laugh, 'laugh_low': lambda: laugh(2.6, 85),
    'notification': notif, 'phone_vibrate': vibrate, 'phone_ring': phone_ring, 'crumble': crumble, 'knock': knock,
    'knock_slow': lambda: knock(3, .6), 'door_open': door_open, 'door_slam': door_slam, 'door_handle': door_handle,
    'lock_rattle': lock_rattle, 'button': button, 'static': static_burst, 'breath': breath, 'whisper': whisper_noise,
    'drip': drip, 'thunder': thunder, 'rain': rain, 'tv_static': tv_static, 'clock_tick': clock_tick, 'glitch': glitch_sfx,
    'footsteps_run': footsteps_run, 'footsteps_walk': footsteps_walk, 'footsteps_heavy': footsteps_heavy, 'skitter': skitter,
    'click': lambda: click(.04, 1200), 'thump': lambda: thump(80, .3, 40),
    'chip_blip': chip_blip, 'chip_alert': chip_alert, 'chip_gameover': chip_gameover, 'chip_save': chip_save, 'chip_pause': chip_pause,
}
SFX_DESCRIPTIONS = {
    'heartbeat': 'battement de cœur', 'boom': 'grave sourd (révélation)', 'impact': 'gros impact', 'sting': 'cordes stridentes (jump scare)',
    'screech': 'crissement aigu', 'riser': 'montée de souffle avant un choc', 'whoosh': 'souffle de passage', 'whoosh_rev': 'souffle inversé (flashback)',
    'glass_crack': 'verre qui se fissure', 'glass_shatter': 'verre qui explose', 'metal_hit': 'coup métallique', 'creak': 'grincement',
    'growl': 'grognement de créature', 'buzz': 'grésillement électrique', 'neon_buzz': 'néon qui grésille', 'ding': 'sonnette', 'elevator_ding': 'ding d\'ascenseur',
    'elevator_motor': 'moteur d\'ascenseur', 'laugh': 'rire inquiétant', 'laugh_low': 'rire grave', 'notification': 'notification de téléphone',
    'phone_vibrate': 'vibreur', 'phone_ring': 'sonnerie', 'crumble': 'gravats qui tombent', 'knock': 'trois coups à la porte', 'knock_slow': 'coups lents',
    'door_open': 'porte qui s\'ouvre', 'door_slam': 'porte qui claque', 'door_handle': 'poignée', 'lock_rattle': 'porte verrouillée secouée',
    'button': 'bouton pressé', 'static': 'parasites', 'breath': 'respiration', 'whisper': 'chuchotement', 'drip': 'goutte', 'thunder': 'tonnerre',
    'rain': 'pluie', 'tv_static': 'neige TV', 'clock_tick': 'tic-tac', 'glitch': 'glitch numérique', 'footsteps_run': 'pas de course',
    'footsteps_walk': 'pas de marche', 'footsteps_heavy': 'pas lourds', 'skitter': 'grattements rapides', 'click': 'clic', 'thump': 'coup sourd',
    'chip_blip': 'bip 8 bits', 'chip_alert': 'alerte 8 bits', 'chip_gameover': 'game over 8 bits', 'chip_save': 'sauvegarde 8 bits', 'chip_pause': 'pause 8 bits',
}

SAMPLE_PROVIDER = None     # real bruitages (audio/library.py), installed by audio/__init__.py; None = pure synthesis

def make(name, dur=None, at=0.0, **kw):
    """the sound of an event: a real sample from library/audio when the key has one, the procedural one otherwise.
    `at` is the cue time in the mix: it makes the choice of variant deterministic (see audio/library.py)."""
    if SAMPLE_PROVIDER is not None:
        a = SAMPLE_PROVIDER(name, dur, at)
        if a is not None and len(a): return np.asarray(a, np.float32)
    return synthesize(name, dur, **kw)

def synthesize(name, dur=None, **kw):
    f = SFX.get(name)
    if f is None: return np.zeros(int(.1 * SR), np.float32)
    try:
        if dur is not None and (name in ('footsteps_run', 'footsteps_walk', 'footsteps_heavy', 'skitter', 'rain', 'tv_static', 'breath', 'elevator_motor', 'growl', 'laugh', 'riser', 'whoosh', 'screech', 'sting', 'thunder', 'whisper', 'phone_ring') or name in LONG_SFX):
            return np.asarray(f(float(dur)), np.float32)
        return np.asarray(f(), np.float32)
    except TypeError:
        return np.asarray(f(), np.float32)

LONG_SFX = ()      # filled by audio/__init__.py with the long sounds of ambience.py
