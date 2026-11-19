"""Sons FABRIQUÉS par le code, réutilisables par toutes les histoires (licence : à nous, aucun échantillon extérieur).

Repris de la production « Chambre 313 » (HISTOIRE_CHAMBRE_313/dirige/mixer.py), où la banque de vrais bruitages
(`library/audio_real`) n'avait pas ces sons. Chaque générateur est DÉTERMINISTE : il tire son bruit d'un générateur
local à graine fixe, jamais de l'état global de `synth`, donc le même appel donne toujours les mêmes échantillons,
quel que soit l'ordre des appels dans le mixage.

    from hstudio.audio import fabriques as FB
    a = FB.make('fire_alarm_fr', dur=12.0)          # float32 mono à FB.SR (44 100 Hz)
    FB.SOUNDS['cough']['desc']                       # description en français

This module is NOT registered in `synth.SFX`: existing episodes that name one of these keys keep exactly the sound
they had. Only the story kit mixer (`hstudio/histoire/mixage.py`) reads it."""
import numpy as np
from . import synth as S
from . import musique_drame as MD          # background music for dramatic stories (bus « musique » of the kit mixer)

SR = S.SR


def _noise(n, seed):
    return np.random.default_rng(seed).standard_normal(int(n)).astype(np.float32)


def _env(n, a=.002, d=.1):
    t = np.arange(int(n)) / SR
    return (np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(d, 1e-4))).astype(np.float32)


def _click(dur, f, rng):
    n = int(dur * SR); t = np.arange(n) / SR
    nz = rng.standard_normal(n).astype(np.float32)
    return (nz * _env(n, .0004, dur / 5) * .6 + np.sin(2 * np.pi * f * t) * _env(n, .0004, dur / 4) * .4).astype(np.float32)


def _brown(n, seed):
    w = _noise(n, seed); b = np.cumsum(w); b -= np.convolve(b, np.ones(4410) / 4410, 'same')
    return (b / (np.abs(b).max() + 1e-9)).astype(np.float32)


# ------------------------------------------------------------------ generators
def fire_alarm_fr(dur=8.):
    """French evacuation signal (NF S 32-001): 554 Hz for 100 ms then 440 Hz for 400 ms, repeated; a hard, bell-like
    tone with the echoes of a corridor"""
    n = int(dur * SR); t = np.arange(n) / SR; ph = (t % .5)
    f = np.where(ph < .1, 554.37, 440.)
    w = np.zeros(n, np.float32); p = 2 * np.pi * np.cumsum(f) / SR
    for h, a in ((1, 1.), (3, .33), (5, .17), (7, .08)): w += (a * np.sin(h * p)).astype(np.float32)
    e = np.minimum(1, np.minimum(ph / .004, np.where(ph < .1, (.1 - ph) / .004 + 1, (.5 - ph) / .01)))
    w *= np.clip(e, 0, 1).astype(np.float32)
    out = w.copy()
    for d, g in ((.031, .35), (.047, .28), (.071, .2), (.113, .12)):
        k = int(d * SR)
        if k < n: out[k:] += g * w[:n - k]
    return out.astype(np.float32)


def siren_two_tone(dur=6.):
    """French fire-engine two-tone (435 / 488 Hz, 0.6 s each), coming closer: low-passed and quiet at first"""
    n = int(dur * SR); t = np.arange(n) / SR
    f = np.where((t % 1.2) < .6, 435., 488.); p = 2 * np.pi * np.cumsum(f) / SR
    w = sum((1. / h) * np.sin(h * p) for h in range(1, 9)).astype(np.float32)
    come = np.clip(t / max(dur, 1e-3), 0, 1) ** 1.5
    far = S.lp(w, 900.); w = far * (1 - come) + w * come
    return (w * (.25 + .75 * come)).astype(np.float32)


def electric_hum(dur=6.):
    """50 Hz electrical hum (panel, neon, transformer) with a faint hiss"""
    n = int(dur * SR); t = np.arange(n) / SR
    w = sum((1. / h ** .8) * np.sin(2 * np.pi * 50 * h * t + h) for h in range(1, 12)).astype(np.float32)
    return ((w * (1 + .15 * np.sin(2 * np.pi * .7 * t))).astype(np.float32) + S.band(_noise(n, 5), 2000, 6000) * .02).astype(np.float32)


def cough(dur=None):
    """three coughs, dry and close (a child or an adult behind a phone line: band-limit it in the mix)"""
    rng = np.random.default_rng(31); out = np.zeros(int(1.1 * SR), np.float32)
    for k, (t0, a) in enumerate(((0., 1.), (.34, .8), (.62, .55))):
        n = int(.22 * SR); e = _env(n, .004, .07)
        x = S.band(rng.standard_normal(n).astype(np.float32), 250, 2600) * e + np.sin(2 * np.pi * (190 - 25 * k) * np.arange(n) / SR).astype(np.float32) * e * .25
        S.addat(out, int(t0 * SR), x * a)
    return out


def fire_crackle(dur=6., seed=7):
    """fire behind the walls: a low roar and dry crackles"""
    n = int(dur * SR); x = S.lp(_brown(n, seed), 350.) * .5
    r = np.random.default_rng(seed)
    for _ in range(int(dur * 7)):
        S.addat(x, int(r.uniform(0, max(dur - .05, .01)) * SR), _click(.012, r.uniform(900, 3200), r) * r.uniform(.1, .5))
    return x.astype(np.float32)


def night_wind(dur=8.):
    """night wind outside (the bank's only wind loop has birds in it)"""
    n = int(dur * SR); t = np.arange(n) / SR
    return (S.band(_noise(n, 23), 180., 1300.) * (.6 + .4 * np.sin(2 * np.pi * t / 5.3) * np.sin(2 * np.pi * t / 2.1 + 1.))).astype(np.float32)


def crowd_panic(dur=4.):
    """a panicked crowd (murmur and calls); the shared synth generator, run on a fixed seed without touching the
    caller's random state"""
    from . import ambience as A
    old = S._rng
    try:
        S.reseed(11); return np.asarray(A.crowd(dur), np.float32)
    finally:
        S._rng = old


# ------------------------------------------------------------------ « Le Phare qui efface » (14/11/2026): one-shots, opt-in by name
def _smooth_noise(n, seed, fc):
    """slow random curve in [-1, 1] (low-passed noise), for pitch jitter and chatter"""
    x = S.lp(_noise(n, seed), fc); return (x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def _ramp(n, k0, k1):
    """linear fade over samples [k0, k1) of an n-sample envelope: 1 before, 0 after"""
    e = np.ones(int(n), np.float32); k0, k1 = int(k0), int(k1)
    if k1 > k0: e[k0:k1] = np.linspace(1, 0, k1 - k0, dtype=np.float32)
    e[k1:] = 0.; return e


def freinage_pneus():
    """an emergency stop on night asphalt (2.0 s): the tyres squeal (a whistle gliding from ~1.5 kHz down to ~0.85 kHz with
    jitter and chatter, over a scrubbing rubber hiss), the body rumbles low, then a dry stop at 1.72 s (the squeal dies in
    25 ms) and only a short low settle of the body. No impact."""
    dur, t_stop = 2.0, 1.72
    n = int(dur * SR); t = np.arange(n) / SR; ks = int(t_stop * SR)
    p = np.clip(t / t_stop, 0, 1)
    jit = _smooth_noise(n, 101, 9.)
    f = (1480. - 630. * p ** .85 + 38. * jit).astype(np.float64)
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = (np.sin(ph) + .38 * np.sin(2 * ph + .7) + .16 * np.sin(3 * ph + 1.9)).astype(np.float32)
    chatter = (1. - .28 * (.5 + .5 * np.sin(2 * np.pi * np.cumsum(22. + 6. * _smooth_noise(n, 102, 3.)) / SR))).astype(np.float32)
    att = np.minimum(1, t / .07).astype(np.float32)
    body = (.75 + .25 * (1 - p)).astype(np.float32) * att * chatter
    stop = _ramp(n, ks, ks + int(.025 * SR))
    squeal = tone * body * stop * .8
    scrub = S.band(_noise(n, 103), 1400., 4200.) * body * stop * .28
    rumble_env = (att * (.6 + .4 * (1 - p)) * _ramp(n, ks, ks + int(.22 * SR))).astype(np.float32)
    rumble = (S.lp(_brown(n, 104), 140.) * .8 + np.sin(2 * np.pi * 52. * t).astype(np.float32) * .25) * rumble_env
    settle = np.zeros(n, np.float32)
    S.addat(settle, ks, S.thump(70, .28, 38) * .35)                  # the body settles on its springs: soft and low, not a crash
    out = squeal + scrub + rumble + settle
    return (out / (np.abs(out).max() + 1e-9) * .9).astype(np.float32)


def eclair_phare():
    """the « flash » of a supernatural lighthouse (2.5 s): a short breath sucked in (0 - 0.35 s), a deep « whoom » (sub sweep
    62 -> 42 Hz with its octave and a low body of noise), then a tail of glass / metal that sings (inharmonic partials of a
    glass bowl, slow beats). No crack, no thunder."""
    dur, t0 = 2.5, .35
    n = int(dur * SR); t = np.arange(n) / SR
    suck = S.band(_noise(n, 201), 450., 3200.) * (np.clip(t / t0, 0, 1) ** 3).astype(np.float32) * .55
    suck *= _ramp(n, int((t0 - .03) * SR), int(t0 * SR))               # the breath fades into the whoom: no click at t0
    tt = np.clip(t - t0, 0, None); on = (t >= t0).astype(np.float32)
    f = 42. + 20. * np.exp(-tt * 3.2)
    ph = 2 * np.pi * np.cumsum(f) / SR
    e_whoom = (np.minimum(1, tt / .03) * np.exp(-tt / .6)).astype(np.float32) * on
    whoom = (np.sin(ph) + .45 * np.sin(2 * ph + .4) + .12 * np.sin(3 * ph + 1.1)).astype(np.float32) * e_whoom
    body = S.lp(_brown(n, 202), 180.) * (np.minimum(1, tt / .02) * np.exp(-tt / .32)).astype(np.float32) * on * .6
    ts = np.clip(t - t0 - .04, 0, None)
    e_sing = (np.minimum(1, ts / .09) * np.exp(-ts / .95)).astype(np.float32) * (t >= t0 + .04)
    sing = np.zeros(n, np.float32)
    for r, a in ((1., 1.), (2.27, .55), (3.58, .34), (5.14, .2), (6.71, .11)):
        fr = 587. * r
        sing += (a * (np.sin(2 * np.pi * fr * t) + .8 * np.sin(2 * np.pi * (fr + .7 * r) * t + r))).astype(np.float32)
    sing = sing * e_sing * .2
    out = suck + whoom + body + sing
    out *= _ramp(n, n - int(.18 * SR), n)                             # clean end
    return (out / (np.abs(out).max() + 1e-9) * .9).astype(np.float32)


def effacement():
    """what the light takes disappears (1.6 s): a reversed whoosh that tightens (wide noise narrowing to a 2 kHz band, a tone
    climbing 260 -> 2200 Hz, swelling until 0.9 s), small digital crackles that die out (0.9 - 1.32 s), then an exact
    silence (from 1.35 s). No explosion."""
    dur, t1, t2 = 1.6, .9, 1.32
    n = int(dur * SR); t = np.arange(n) / SR; k1 = int(t1 * SR)
    pre = (t < t1).astype(np.float32)
    swell = (np.exp((np.minimum(t, t1) - t1) / .22)).astype(np.float32) * pre
    w = np.clip(t / t1, 0, 1).astype(np.float32)
    wide = S.band(_noise(n, 301), 200., 7000.) * (1 - w) ** 1.5
    narrow = S.band(_noise(n, 302), 1750., 2350.) * w ** 1.2 * 1.8
    f = 260. * (2200. / 260.) ** (np.clip(t / t1, 0, 1) ** 2)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR).astype(np.float32) * w * .35
    whoosh = (wide + narrow + tone) * swell
    whoosh *= _ramp(n, k1 - int(.004 * SR), k1)                       # the swell is cut, not faded
    crack = np.zeros(n, np.float32); rng = np.random.default_rng(303)
    k = 0
    while True:
        tc = t1 + .004 + (t2 - t1) * (k / 26.) ** 1.25
        if tc >= t2 - .006: break
        life = 1. - (tc - t1) / (t2 - t1)
        m = int(rng.uniform(.0015, .006) * SR)
        hold = int(rng.integers(3, 14))                               # sample-and-hold: a « digital » crushed click
        z = np.repeat(rng.standard_normal(m // hold + 1).astype(np.float32), hold)[:m]
        z = np.round(z * 4) / 4 * _env(m, .0002, m / SR / 2.5)
        S.addat(crack, int(tc * SR), z * .5 * life ** 1.6)
        k += 1
    crack *= _ramp(n, int((t2 - .004) * SR), int(t2 * SR))
    out = whoosh + crack
    out = out / (np.abs(out).max() + 1e-9) * .9
    out[int((t2 + .03) * SR):] = 0.                                   # exact silence: the void after the erasure
    return out.astype(np.float32)


def frappe_mur_invisible():
    """fists on a thick invisible pane (1.4 s): four irregular, muffled knocks (a low thud and a dull mid, a faint glassy
    ring), in a short cold reverberation"""
    dur = 1.4
    n = int(dur * SR); dry = np.zeros(n, np.float32); rng = np.random.default_rng(401)
    for tk, a, f0 in ((0., 1., 128.), (.26, .78, 141.), (.43, .92, 122.), (.79, .62, 134.)):
        m = int(.24 * SR); tt = np.arange(m) / SR
        thud = np.sin(2 * np.pi * (f0 + 40. * np.exp(-tt * 60.)) * tt).astype(np.float32) * _env(m, .0012, .055)
        mid = S.lp(rng.standard_normal(m).astype(np.float32), 1100.) * _env(m, .0006, .018) * .8
        ring = (np.sin(2 * np.pi * 1930. * tt) + .6 * np.sin(2 * np.pi * 3170. * tt + 1.)).astype(np.float32) * _env(m, .001, .09) * .05
        S.addat(dry, int(tk * SR), (thud + mid + ring) * a)
    m = int(.9 * SR); ir = S.band(_noise(m, 402), 300., 4800.) * np.exp(-np.arange(m) / SR / .22).astype(np.float32)
    ir /= np.sqrt(np.sum(ir.astype(np.float64) ** 2)) + 1e-9
    wet = np.convolve(dry, ir)[:n].astype(np.float32)
    out = dry + wet * .35
    out *= _ramp(n, n - int(.12 * SR), n)
    return (out / (np.abs(out).max() + 1e-9) * .9).astype(np.float32)


SOUNDS = {
    'fire_alarm_fr': dict(fn=fire_alarm_fr, kind='bed', desc="alarme incendie française (NF S 32-001 : 554 Hz 100 ms / 440 Hz 400 ms), échos de couloir"),
    'siren_two_tone': dict(fn=siren_two_tone, kind='bed', desc="sirène deux-tons des pompiers (435 / 488 Hz) qui s'approche"),
    'electric_hum': dict(fn=electric_hum, kind='bed', desc="bourdonnement électrique 50 Hz (panneau, néon, transformateur)"),
    'cough': dict(fn=cough, kind='one', desc="trois quintes de toux (passer en bande téléphone avec phone=True si on l'entend au bout du fil)"),
    'fire_crackle': dict(fn=fire_crackle, kind='bed', desc="feu derrière les murs : grondement grave et craquements secs"),
    'night_wind': dict(fn=night_wind, kind='bed', desc="vent de nuit dehors, sans oiseaux"),
    'crowd_panic': dict(fn=crowd_panic, kind='bed', desc="foule paniquée (brouhaha, appels)"),
    # music: rms_db = nominal RMS of the generator (the kit mixer levels it from there, whatever the cue duration)
    'musique_piano_triste': dict(fn=MD.musique_piano_triste, kind='bed', rms_db=MD.NOMINAL_RMS_DB,
                                 desc="musique piano + cordes légères, la mineur, 62 bpm : deuil, pluie, mélancolique sans être lugubre (bus musique)"),
    'musique_piano_tendre': dict(fn=MD.musique_piano_tendre, kind='bed', rms_db=MD.NOMINAL_RMS_DB,
                                 desc="musique piano + cordes légères, ré majeur, 68 bpm : chaleureuse, fin d'après-midi, souvenirs d'amitié (bus musique)"),
    'musique_piano_suspens': dict(fn=MD.musique_piano_suspens, kind='bed', rms_db=MD.NOMINAL_RMS_DB,
                                  desc="musique piano clairsemé + cordes tenues, accords suspendus, 60 bpm : choix difficile, sans tension d'horreur (bus musique)"),
    # « Le Phare qui efface » (14/11/2026) — one-shots, new names only: nothing existing changes
    'freinage_pneus': dict(fn=freinage_pneus, kind='one', desc="freinage d'urgence sur asphalte (2 s) : crissement de pneus qui glisse vers le grave, carrosserie qui gronde, arrêt sec à 1,72 s, sans choc"),
    'eclair_phare': dict(fn=eclair_phare, kind='one', desc="« éclair » d'un phare surnaturel (2,5 s) : souffle aspiré, « whoom » grave 62 → 42 Hz, queue de verre / métal qui chante ; ni craquement ni tonnerre"),
    'effacement': dict(fn=effacement, kind='one', desc="ce que la lumière efface disparaît (1,6 s) : souffle à l'envers qui se resserre, crépitements numériques qui s'éteignent, puis silence net (dès 1,35 s)"),
    'frappe_mur_invisible': dict(fn=frappe_mur_invisible, kind='one', desc="poings contre un mur de verre épais et invisible (1,4 s) : quatre coups irréguliers étouffés, réverbération froide"),
}
# names used by « Chambre 313 » (accepted by the story mixer, the canonical names above are preferred)
ALIASES = {'alarm': 'fire_alarm_fr', 'siren': 'siren_two_tone', 'hum': 'electric_hum', 'wind': 'night_wind', 'crowd': 'crowd_panic', 'crackle': 'fire_crackle'}


def canonical(name):
    return ALIASES.get(name, name)


def has(name):
    return canonical(name) in SOUNDS


def make(name, dur=None):
    """-> float32 mono array at SR; `dur` is required for the long (`bed`) sounds"""
    k = canonical(name)
    if k not in SOUNDS: raise KeyError(f'son fabriqué inconnu : {name}')
    spec = SOUNDS[k]
    if spec['kind'] == 'bed':
        return np.asarray(spec['fn'](float(dur if dur else 6.)), np.float32)
    return np.asarray(spec['fn'](), np.float32)
