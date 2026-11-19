"""Procedural ambiences (continuous beds for places) and extra sound effects for stories of every genre.
Everything is synthesized (royalty free, deterministic)."""
import math, numpy as np
from . import synth as S
SR = S.SR
addat, env, noise, band, lp, hp, brown, tone, click = S.addat, S.env, S.noise, S.band, S.lp, S.hp, S.brown, S.tone, S.click

def _slow(n, period=6., depth=.5, seed=0):
    t = np.arange(n) / SR; r = np.random.default_rng(seed)
    return (1 - depth + depth * (.5 + .5 * np.sin(2 * np.pi * t / period + r.uniform(0, 6)) * (.7 + .3 * np.sin(2 * np.pi * t / (period * 2.7))))).astype(np.float32)

def chirp(f0=3200, f1=4200, dur=.12):
    n = int(dur * SR); t = np.arange(n) / SR; f = f0 + (f1 - f0) * (t / dur) + 300 * np.sin(2 * np.pi * 30 * t)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .005, dur / 3)).astype(np.float32)
def bird(): r = S._rng; out = np.zeros(int(.6 * SR), np.float32); [addat(out, int(i * .11 * SR), chirp(r.uniform(2500, 4000), r.uniform(3500, 5500), r.uniform(.05, .1)) * .3) for i in range(int(r.integers(2, 5)))]; return out
def gull():
    n = int(.7 * SR); t = np.arange(n) / SR; f = 1500 - 600 * t / .7 + 60 * np.sin(2 * np.pi * 12 * t)
    return (np.tanh(2 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * env(n, .03, .3) * .2).astype(np.float32)
def cricket(): out = np.zeros(int(.35 * SR), np.float32); [addat(out, int(i * .06 * SR), tone(4600, .03, .002, .008) * .15) for i in range(4)]; return out
def owl():
    out = np.zeros(int(1.6 * SR), np.float32)
    for i, (d, f) in enumerate(((.25, 420), (.6, 400))): addat(out, int((.0 if i == 0 else .45) * SR), (tone(f, d, .05, d / 2) + .3 * tone(f * 2, d, .05, d / 3)) * .3)
    return out
def wolf():
    n = int(3. * SR); t = np.arange(n) / SR; f = 380 + 260 * np.sin(np.pi * np.clip(t / 2.6, 0, 1)) + 6 * np.sin(2 * np.pi * 5 * t)
    return ((np.sin(2 * np.pi * np.cumsum(f) / SR) + .3 * np.sin(4 * np.pi * np.cumsum(f) / SR)) * np.sin(np.pi * np.clip(t / 3., 0, 1)) * .3).astype(np.float32)
def dog_bark():
    out = np.zeros(int(.7 * SR), np.float32)
    for k in range(2):
        n = int(.13 * SR); t = np.arange(n) / SR; f = 520 - 200 * t / .13
        b = (np.tanh(3 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * .6 + band(noise(n), 400, 2500) * .4) * env(n, .004, .05)
        addat(out, int(k * .22 * SR), b.astype(np.float32) * .5)
    return out
def cat_meow():
    n = int(.8 * SR); t = np.arange(n) / SR; f = 650 + 250 * np.sin(np.pi * t / .8) - 150 * t
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) + .5 * np.sin(4 * np.pi * np.cumsum(f) / SR) + .25 * np.sin(6 * np.pi * np.cumsum(f) / SR)
    return (s * np.sin(np.pi * t / .8) ** .7 * .25).astype(np.float32)
def cow_moo():
    n = int(1.6 * SR); t = np.arange(n) / SR; f = 130 + 25 * np.sin(np.pi * t / 1.6)
    s = sum((1 / k) * np.sin(2 * np.pi * k * np.cumsum(f) / SR) for k in range(1, 7))
    return lp((s * np.sin(np.pi * t / 1.6) ** .5 * .3).astype(np.float32), 1500)
def horse_neigh():
    n = int(1.3 * SR); t = np.arange(n) / SR; f = 700 + 300 * np.sin(2 * np.pi * 9 * t) * np.exp(-t * 1.5) - 300 * t
    return (np.tanh(2 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * env(n, .03, .5) * .25).astype(np.float32)
def car_horn():
    n = int(.5 * SR); t = np.arange(n) / SR
    return lp(((np.sign(np.sin(2 * np.pi * 420 * t)) + np.sign(np.sin(2 * np.pi * 520 * t))) * .12 * np.minimum(1, (.5 - t) / .03)).astype(np.float32), 3000)
def car_pass():
    n = int(2.4 * SR); t = np.arange(n) / SR; e = np.exp(-((t - 1.2) / .45) ** 2)
    return (lp(brown(n), 300) * .5 * e + band(noise(n), 300, 2500) * .08 * e).astype(np.float32)
def church_bell():
    n = int(4. * SR); t = np.arange(n) / SR; s = np.zeros(n, np.float32)
    for f, a, d in ((220, 1, 3.), (440, .5, 2.), (523, .35, 1.6), (660, .25, 1.2), (880, .2, .8)): s += a * np.sin(2 * np.pi * f * t) * np.exp(-t / d)
    return (s * .15).astype(np.float32)
def doorbell(): out = np.zeros(int(1.4 * SR), np.float32); addat(out, 0, tone(784, .7, .003, .4) * .3); addat(out, int(.45 * SR), tone(622, .9, .003, .5) * .3); return out
def splash(): n = int(.9 * SR); return (band(noise(n), 300, 6000) * env(n, .003, .25) * .5).astype(np.float32)
def pop(): x = tone(900, .08, .001, .02) * .4; addat(x, 0, click(.02, 2000) * .3); return x
def magic():
    out = np.zeros(int(1.2 * SR), np.float32)
    for i, f in enumerate((1047, 1319, 1568, 2093, 2637, 3136)): addat(out, int(i * .08 * SR), tone(f, .5, .002, .2) * .12)
    return out + band(noise(len(out)), 5000, 12000) * env(len(out), .3, .4) * .05
def coin(): out = np.zeros(int(.5 * SR), np.float32); addat(out, 0, tone(988, .08, .001, .05, 'square') * .12); addat(out, int(.07 * SR), tone(1319, .35, .001, .15, 'square') * .12); return out
def success():
    out = np.zeros(int(1.2 * SR), np.float32)
    for i, f in enumerate((523, 659, 784, 1047)): addat(out, int(i * .1 * SR), (tone(f, .6, .003, .3) + .3 * tone(f * 2, .6, .003, .2)) * .14)
    return out
def fail():
    out = np.zeros(int(1.6 * SR), np.float32)
    for i, f in enumerate((392, 370, 349)): addat(out, int(i * .3 * SR), lp(tone(f, .35, .01, .2, 'saw'), 1500) * .15)
    n = int(.7 * SR); t = np.arange(n) / SR; addat(out, int(.9 * SR), lp((2 * ((330 * t + 8 * np.sin(2 * np.pi * 6 * t)) % 1) - 1).astype(np.float32) * np.exp(-t * 2), 1200) * .15)
    return out
def crowd(dur=3.):
    n = int(dur * SR); x = band(noise(n), 300, 3000) * (.6 + .4 * np.abs(np.sin(2 * np.pi * 3.3 * np.arange(n) / SR + 2 * np.sin(np.arange(n) / SR * 1.7))))
    return (x * .12).astype(np.float32)
def cheer(): n = int(2.5 * SR); return (crowd(2.5) * 3 * env(n, .1, 1.)).astype(np.float32)
def applause(dur=3.):
    n = int(dur * SR); out = np.zeros(n, np.float32); r = S._rng
    for _ in range(int(dur * 120)): addat(out, int(r.uniform(0, dur - .02) * SR), click(.012, r.uniform(1200, 4000)) * r.uniform(.05, .15))
    return out * np.minimum(1, (dur - np.arange(n) / SR) / .5).astype(np.float32)
def punch(): return S.thump(110, .2, 50) * .8 + band(noise(int(.2 * SR)), 300, 3000) * env(int(.2 * SR), .001, .03) * .4
def sword_clash():
    n = int(1.2 * SR); t = np.arange(n) / SR; s = sum(np.sin(2 * np.pi * f * t) * np.exp(-t / d) for f, d in ((2200, .5), (3100, .35), (4700, .25), (5900, .15)))
    return (s * .12 + band(noise(n), 3000, 9000) * env(n, .001, .03) * .3).astype(np.float32)
def explosion():
    b = S.boom(2.4, 38); n = len(b); return (b * 1.2 + band(noise(n), 100, 4000) * env(n, .002, .5) * .5).astype(np.float32)
def fire_whoosh(): n = int(1.2 * SR); return (band(noise(n), 150, 2500) * np.sin(np.linspace(0, np.pi, n)) ** 2 * .45).astype(np.float32)
def engine(dur=3.):
    n = int(dur * SR); t = np.arange(n) / SR; f = 45 + 25 * np.clip(t / dur * 2, 0, 1)
    return lp((np.tanh(3 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * .25 + lp(brown(n), 200) * .2).astype(np.float32), 900)
def shutter(): return np.concatenate([click(.03, 3000) * .6, np.zeros(int(.03 * SR), np.float32), click(.03, 2400) * .5])
def typing(dur=2.):
    n = int(dur * SR); out = np.zeros(n, np.float32); r = S._rng; tt = 0.
    while tt < dur - .05: addat(out, int(tt * SR), click(.02, r.uniform(1500, 3000)) * r.uniform(.15, .3)); tt += r.uniform(.06, .18)
    return out
def page_turn(): n = int(.5 * SR); return (band(noise(n), 1500, 8000) * np.sin(np.linspace(0, np.pi, n)) * .2).astype(np.float32)
def steps_soft(dur=2., surface='grass'):
    out = np.zeros(int(dur * SR), np.float32); tt = .05; r = S._rng
    lo, hi, d = {'grass': (300, 3000, .09), 'snow': (600, 6000, .12), 'sand': (200, 2500, .1), 'gravel': (800, 7000, .08)}[surface]
    while tt < dur - .2:
        n = int(d * SR); addat(out, int(tt * SR), band(noise(n), lo, hi) * env(n, .005, d / 2) * .35 * r.uniform(.7, 1)); tt += .5
    return out
def boing():
    n = int(.6 * SR); t = np.arange(n) / SR; f = 180 + 300 * np.exp(-t * 6) * (1 + .5 * np.sin(2 * np.pi * 14 * t))
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .002, .3) * .35).astype(np.float32)
def slide_whistle():
    n = int(.9 * SR); t = np.arange(n) / SR; f = 600 + 900 * t / .9
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / .9) * .2).astype(np.float32)
def drum_roll(dur=2.):
    n = int(dur * SR); out = np.zeros(n, np.float32); tt = 0.
    while tt < dur - .05: addat(out, int(tt * SR), band(noise(int(.05 * SR)), 300, 5000) * env(int(.05 * SR), .001, .02) * (.2 + .2 * tt / dur)); tt += .045
    return out
def clock_chime(): return church_bell() * .7
def ghost_moan():
    n = int(2.5 * SR); t = np.arange(n) / SR; f = 300 + 80 * np.sin(2 * np.pi * .6 * t)
    return (lp((np.sin(2 * np.pi * np.cumsum(f) / SR) * .3 + band(noise(n), 400, 1500) * .2).astype(np.float32), 1800) * np.sin(np.pi * t / 2.5) * .4).astype(np.float32)
def roar():
    n = int(2. * SR); t = np.arange(n) / SR; f = 90 + 40 * np.sin(np.pi * t / 2)
    return (np.tanh(4 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * .3 + band(noise(n), 150, 1800) * .35).astype(np.float32) * np.sin(np.pi * t / 2.) ** .5
def teleport(): return np.concatenate([S.whoosh(.5, 400, 6000, True) * .5, magic()[:int(.6 * SR)]])
def cash_register(): out = coin(); out = np.concatenate([click(.04, 1500) * .5, out]); return np.concatenate([out, church_bell()[:int(.6 * SR)] * .4])
def wave_crash(): n = int(3. * SR); t = np.arange(n) / SR; return (band(noise(n), 150, 5000) * (np.sin(np.pi * np.clip(t / 2.6, 0, 1)) ** 3) * .4).astype(np.float32)

# single footsteps and small Foley, triggered by the acting timeline (one sound per foot contact / action)
def _step(lo, hi, body, tail, gain):
    r = S._rng; n = int(tail * SR)
    x = band(noise(n), lo * r.uniform(.85, 1.15), hi) * env(n, .001, tail / 3.5) * .8
    addat(x, 0, S.thump(body * r.uniform(.9, 1.1), .07, body * .6)[:n] * .5)
    return (x * gain * r.uniform(.75, 1.0)).astype(np.float32)
def step(): return _step(250, 2400, 90, .09, .55)
def step_wood(): return _step(300, 3200, 120, .11, .6)
def step_grass(): return _step(900, 5000, 70, .12, .35)
def step_hard(): return _step(500, 6000, 140, .07, .6)
def cloth():
    n = int(.35 * SR); return (band(noise(n), 1500, 6000) * env(n, .06, .12) * .25).astype(np.float32)
def pickup():
    out = np.zeros(int(.25 * SR), np.float32); addat(out, 0, click(.02, 3200) * .4); addat(out, int(.05 * SR), click(.015, 4500) * .25); return out
def paper():
    n = int(.4 * SR); return (band(noise(n), 2500, 9000) * env(n, .01, .12) * (.6 + .4 * np.sin(np.arange(n) / SR * 2 * np.pi * 23)) * .25).astype(np.float32)

# V3: vertical actions (acting/motion.py) and large effects (engines/pixel3d/effects.py)
def jump_push():
    out = cloth() * 1.4; n = int(.3 * SR); addat(out, 0, (band(noise(n), 300, 1800) * env(n, .02, .08) * .35).astype(np.float32)); return out
def land():
    out = np.zeros(int(.5 * SR), np.float32); addat(out, 0, S.thump(70, .25, 38) * .9); addat(out, 0, step_hard() * 1.3); addat(out, int(.04 * SR), cloth()); return out
def wing_flap():
    n = int(.7 * SR); t = np.arange(n) / SR; e = np.sin(np.pi * np.clip(t / .55, 0, 1)) ** 2
    out = (lp(band(noise(n), 40, 900), 600) * e * .9).astype(np.float32); addat(out, int(.2 * SR), S.thump(55, .3, 30) * .4); return out
def wings(dur=4., rate=.85):
    out = np.zeros(int((dur + .8) * SR), np.float32); tt = 0.
    while tt < dur: addat(out, int(tt * SR), wing_flap()); tt += 1 / rate
    return out
def collapse(dur=6.):
    n = int(dur * SR); t = np.arange(n) / SR
    out = (lp(brown(n), 180) * 1.4 * np.clip(t / .6, 0, 1) * np.clip((dur - t) / 1.5, 0, 1)).astype(np.float32)
    addat(out, 0, S.boom(2.2, 34) * .9); r = S._rng
    for _ in range(int(dur * 9)): addat(out, int(r.uniform(.2, dur - .3) * SR), S.crumble() * r.uniform(.15, .45))
    for _ in range(int(dur * 2)): addat(out, int(r.uniform(.8, dur - .3) * SR), S.thump(r.uniform(45, 80), .3, 30) * r.uniform(.3, .7))
    return out
def thunder_close():
    n = int(.25 * SR); out = S.thunder(4.); addat(out, 0, (hp(noise(n), 1200) * env(n, .0005, .05) * 1.2).astype(np.float32)); return out

EXTRA_SFX = {'step': step, 'step_wood': step_wood, 'step_grass': step_grass, 'step_hard': step_hard, 'cloth': cloth, 'pickup': pickup, 'paper': paper, 'bird': bird, 'seagull': gull, 'cricket': cricket, 'owl': owl, 'wolf_howl': wolf, 'dog_bark': dog_bark, 'cat_meow': cat_meow, 'cow_moo': cow_moo,
             'horse_neigh': horse_neigh, 'car_horn': car_horn, 'car_pass': car_pass, 'church_bell': church_bell, 'doorbell': doorbell, 'splash': splash, 'pop': pop,
             'magic': magic, 'coin': coin, 'success': success, 'fail': fail, 'cheer': cheer, 'applause': applause, 'punch': punch, 'sword_clash': sword_clash,
             'explosion': explosion, 'fire_whoosh': fire_whoosh, 'engine': engine, 'camera_shutter': shutter, 'typing': typing, 'page_turn': page_turn,
             'footsteps_grass': lambda dur=2.: steps_soft(dur, 'grass'), 'footsteps_snow': lambda dur=2.: steps_soft(dur, 'snow'), 'footsteps_sand': lambda dur=2.: steps_soft(dur, 'sand'),
             'footsteps_gravel': lambda dur=2.: steps_soft(dur, 'gravel'), 'boing': boing, 'slide_whistle': slide_whistle, 'drum_roll': drum_roll, 'clock_chime': clock_chime,
             'ghost_moan': ghost_moan, 'roar': roar, 'teleport': teleport, 'cash_register': cash_register, 'wave_crash': wave_crash, 'crowd': crowd,
             'jump_push': jump_push, 'land': land, 'wing_flap': wing_flap, 'wings': wings, 'collapse': collapse, 'thunder_close': thunder_close}
EXTRA_DESCRIPTIONS = {'step': 'un pas', 'step_wood': 'un pas sur parquet', 'step_grass': 'un pas dans l\'herbe', 'step_hard': 'un pas sur carrelage / béton', 'cloth': 'froissement de vêtement (s\'asseoir)', 'pickup': 'petit objet pris en main', 'paper': 'papier, lettre', 'bird': 'chant d\'oiseau', 'seagull': 'mouette', 'cricket': 'grillon', 'owl': 'hibou', 'wolf_howl': 'hurlement de loup', 'dog_bark': 'aboiement',
                      'cat_meow': 'miaulement', 'cow_moo': 'meuglement', 'horse_neigh': 'hennissement', 'car_horn': 'klaxon', 'car_pass': 'voiture qui passe',
                      'church_bell': 'cloche d\'église', 'doorbell': 'sonnette', 'splash': 'plouf', 'pop': 'pop', 'magic': 'magie scintillante', 'coin': 'pièce (jeu)',
                      'success': 'jingle de réussite', 'fail': 'jingle d\'échec', 'cheer': 'foule qui acclame', 'applause': 'applaudissements', 'punch': 'coup de poing',
                      'sword_clash': 'choc d\'épées', 'explosion': 'explosion', 'fire_whoosh': 'flamme', 'engine': 'moteur', 'camera_shutter': 'appareil photo',
                      'typing': 'clavier', 'page_turn': 'page tournée', 'footsteps_grass': 'pas dans l\'herbe', 'footsteps_snow': 'pas dans la neige',
                      'footsteps_sand': 'pas dans le sable', 'footsteps_gravel': 'pas sur le gravier', 'boing': 'boing (comique)', 'slide_whistle': 'sifflet glissé (comique)',
                      'drum_roll': 'roulement de tambour', 'clock_chime': 'carillon', 'ghost_moan': 'gémissement de fantôme', 'roar': 'rugissement (dragon, monstre)',
                      'teleport': 'téléportation', 'cash_register': 'caisse enregistreuse', 'wave_crash': 'vague qui se brise', 'crowd': 'brouhaha de foule',
                      'jump_push': 'élan d\'un saut', 'land': 'réception d\'un saut', 'wing_flap': 'un battement de grandes ailes', 'wings': 'battements d\'ailes (durée)',
                      'collapse': 'effondrement d\'un bâtiment (durée)', 'thunder_close': 'foudre qui tombe tout près'}
LONG_SFX = ('applause', 'engine', 'typing', 'footsteps_grass', 'footsteps_snow', 'footsteps_sand', 'footsteps_gravel', 'drum_roll', 'crowd', 'wings', 'collapse')

# ------------------------------------------------------------------ ambience beds
def _events(n, every, fn, gain, seed, jitter=.6):
    out = np.zeros(n, np.float32); r = np.random.default_rng(seed); tt = r.uniform(.2, every)
    while tt < n / SR - .5:
        addat(out, int(tt * SR), fn() * gain * r.uniform(.6, 1.)); tt += every * r.uniform(1 - jitter, 1 + jitter)
    return out

def _fit(a, n):
    """exactly n samples (a sound synthesised for n / SR seconds can be one sample short)"""
    a = np.asarray(a, np.float32)[:n]
    return a if len(a) == n else np.pad(a, (0, n - len(a)))

def ambience(name, n, seed=0):
    """continuous bed of n samples"""
    S.reseed(500 + seed); t = np.arange(n) / SR
    wind = lambda lo, hi, a, p=7.: band(noise(n), lo, hi) * _slow(n, p, .6, seed) * a
    if name == 'forest': x = wind(150, 1200, .05) + _events(n, 2.2, bird, .5, seed + 1) + _events(n, 3.7, bird, .3, seed + 2)
    elif name == 'park': x = wind(150, 1000, .03) + _events(n, 3., bird, .35, seed + 3) + lp(brown(n), 200) * .03
    elif name == 'beach': x = band(noise(n), 150, 3000) * (.15 + .5 * np.clip(np.sin(2 * np.pi * t / 7.5 + seed), 0, 1) ** 2) * .3 + _events(n, 6., gull, .5, seed + 4)
    elif name == 'city': x = lp(brown(n), 250) * .12 + _events(n, 3.5, car_pass, .4, seed + 5) + _events(n, 11., car_horn, .2, seed + 6, .3)
    elif name in ('rain', 'storm'):
        x = _fit(S.rain(n / SR, .9 if name == 'storm' else .6), n)
        if name == 'storm': x = x + _events(n, 7., S.thunder, .5, seed + 7, .4)
    elif name == 'wind': x = wind(200, 1500, .09, 5.) + wind(80, 400, .05, 11.)
    elif name == 'snow': x = wind(150, 900, .04, 8.)
    elif name == 'night': x = _events(n, .45, cricket, .5, seed + 8, .3) + _events(n, .6, cricket, .3, seed + 9, .5) + _events(n, 9., owl, .4, seed + 10, .4) + wind(100, 600, .015)
    elif name == 'campfire':
        x = lp(brown(n), 400) * .05 + _events(n, .5, cricket, .25, seed + 11, .4)
        for _ in range(int(n / SR * 9)): addat(x, int(S._rng.uniform(0, n / SR - .05) * SR), click(.015, S._rng.uniform(800, 3000)) * S._rng.uniform(.05, .25))
    elif name == 'river': x = band(noise(n), 400, 6000) * (.7 + .3 * np.sin(2 * np.pi * 3.1 * t) * np.sin(2 * np.pi * .4 * t)) * .09
    elif name == 'cave': x = wind(60, 300, .05, 13.) + _events(n, 1.8, S.drip, .5, seed + 12)
    elif name == 'village': x = wind(150, 1000, .025) + _events(n, 3., bird, .3, seed + 13) + _events(n, 14., dog_bark, .2, seed + 14, .4) + _fit(crowd(n / SR), n) * .15
    elif name == 'countryside': x = wind(150, 1200, .04) + _events(n, 2.5, bird, .35, seed + 15) + _events(n, 15., cow_moo, .25, seed + 16, .4)
    elif name in ('cafe', 'school', 'crowd'):
        x = _fit(crowd(n / SR), n) * (.5 if name == 'cafe' else .7)
        if name == 'cafe': x = x + _events(n, 2.5, lambda: tone(2800, .2, .001, .08) * .2, .4, seed + 17)
    elif name == 'office': x = lp(brown(n), 300) * .04 + np.sin(2 * np.pi * 60 * t).astype(np.float32) * .006 + _events(n, 4., lambda: typing(1.2), .5, seed + 18)
    elif name == 'space': x = (np.sin(2 * np.pi * 48 * t) * .03 + lp(brown(n), 150) * .06).astype(np.float32) + _events(n, 5., lambda: tone(1400, .12, .002, .05) * .3, .4, seed + 19)
    elif name == 'room': x = lp(brown(n), 300) * .025
    else: x = np.zeros(n, np.float32)
    return np.asarray(x[:n], np.float32)

AMBIENCES = ('forest', 'park', 'beach', 'city', 'rain', 'storm', 'wind', 'snow', 'night', 'campfire', 'river', 'cave', 'village', 'countryside',
             'cafe', 'school', 'crowd', 'office', 'space', 'room', 'none')
