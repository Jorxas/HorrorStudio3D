"""Étape MIXER du kit : la voix + les bruitages de construit/bruitages.json (vrais bruitages de library/audio_real, sons
FABRIQUÉS de hstudio/audio/fabriques.py, synthèse du moteur) -> mix/mix_<version>.wav à -14 LUFS intégrés, crête vraie
≤ -1,3 dBTP sur le WAV (l'AAC 256k du film peut gagner ~0,3 dB : la livraison reste ≤ -1 dBTP), mesurés à l'ebur128.

Chaîne reprise de « Chambre 313 » (dirige/mixer.py) : voix passe-haut 70 Hz + compression douce ramenée à -20 LUFS ;
bruitages ponctuels (bus « fx ») et nappes (bus « bed ») baissés sous la voix (-37 % / -65 % quand elle parle) ; puis gain
vers -14 LUFS + limiteur, mesurés et répétés jusqu'à tomber juste. Les Shorts sont coupés dans le mélange long (mêmes
instants que construit/decoupe.json) puis normalisés chacun pour lui-même.

Musique de fond (opt-in) : les cues nommées `musique_*` (hstudio/audio/musique_drame.py) ou écrites avec bus='musique'
passent sur un 3e bus « musique », baissé moins fort que les nappes quand la voix parle (-40 % par défaut, avec une clé
plus lente : la musique respire dans les vraies pauses sans pomper entre deux phrases), fondus musicaux par défaut
(entrée 1,5 s, sortie 2,5 s). Sans cue musique, le mélange est identique au bit près.

    python -m hstudio.histoire mixer <dossier>

Réglages possibles dans histoire.py : MIXAGE = {'nappes': {'nom': (dB, gain_ref)}, 'corrections_db': {'nom': +3},
'fichiers': {'nom': 'sfx/.../fichier.wav'}, 'pas': {'nom': pas_par_seconde}, 'voix_lufs': -20, 'graine': 313,
'baisse_musique': 0.40}."""
import math
import os
import shutil
import subprocess
import tempfile

import numpy as np

from .common import ENGINE, KitError, Story, read_json, write_json, loudness as measure
from . import projet as PJ

TARGET_I, TARGET_TP = -14.0, -1.3
REAL = os.path.join(ENGINE, 'library', 'audio_real')
# bed levels: dB RMS for the reference gain written in the cue  (name: (dB, reference gain))
BED = {'amb_room': (-46., .35), 'fire_alarm_fr': (-27., .55), 'drone_creepy': (-33., .35), 'rumble': (-27., .6), 'electric_hum': (-35., .4),
       'crowd_panic': (-28., .3), 'night_wind': (-37., .4), 'engine': (-30., .45), 'siren_two_tone': (-25., .5), 'splash': (-34., .3),
       'clock_tick': (-27., .45), 'fire_crackle': (-38., .4), 'amb_city': (-44., .35), 'amb_rain': (-36., .4), 'amb_wind': (-38., .4),
       'amb_night': (-40., .35), 'amb_storm': (-34., .45), 'amb_forest': (-40., .35)}
# background music (bus « musique »): same convention; measured on « Le choix de demain » P1 (voice at -20 LUFS): at the
# reference gain the music sits 14 dB under the voice while it speaks, ~12.5 dB in the short pauses between phrases and
# ~10 dB in silences of 2 s or more (equal loudness of the three styles within 0.1 LU)
BED.update({'musique_piano_triste': (-29.4, .5), 'musique_piano_tendre': (-29.7, .5), 'musique_piano_suspens': (-29.3, .5)})
DUCK_MUSIC = .40                      # music ducking under the voice (-4.4 dB), lighter than the beds (-65 %, -9.1 dB)
MUSIC_KEY = (.15, .012)               # music ducking key per 10 ms: rises in ~60 ms, falls in ~0.8 s (no pumping between phrases)
ONE_DB = -18.                        # loudest 50 ms of a one-shot at gain 1.0 (the voice sits at -20 LUFS before the final gain)
FORCE = {'phone_ring': 'sfx/phone_ring/wyzowl_phone-ring-classic.wav', 'breath': 'sfx/breath/oculus_hmnbrth_femalebreathing_os_01.wav'}
STEPS = {'footsteps_run_step': 3.4, 'footsteps_heavy_step': 1.7, 'step': 1.9, 'step_wood': 1.9, 'step_hard': 1.9, 'footsteps_metal': 2.6}
# after the « Chambre 313 » balance check: the story sounds must come through the voice
TRIM = {'phone_ring': 4., 'scream': 5., 'siren_two_tone': 3., 'fire_alarm_fr': 2., 'footsteps_metal': 2., 'crowd_panic': 2., 'phone_vibrate': 3.}

_LIB = None


def library(seed=313):
    global _LIB
    if _LIB is None:
        from hstudio.audio import library as LB
        _LIB = LB.SoundLibrary(root=REAL).load()
    _LIB.seed = seed
    return _LIB


def db(x): return 10 ** (x / 20.)
def rms(a): return float(np.sqrt(np.mean(np.asarray(a, np.float64) ** 2))) if len(a) else 0.


def fade(a, fi=0., fo=0.):
    from hstudio.audio import synth as S
    a = np.array(a, np.float32); i = min(len(a) // 2, int(fi * S.SR)); o = min(len(a) // 2, int(fo * S.SR))
    if i > 1: a[:i] *= np.linspace(0, 1, i, dtype=np.float32)
    if o > 1: a[-o:] *= np.linspace(1, 0, o, dtype=np.float32)
    return a


class Mixer:
    def __init__(self, st, mod, log=print):
        from hstudio.audio import synth as S, library as LB, fabriques as FB
        self.S, self.LB, self.FB = S, LB, FB; self.SR = S.SR; self.st = st; self.log = log
        cfg = dict(getattr(mod, 'MIXAGE', {}) or {})
        self.bed = dict(BED, **{FB.canonical(k): tuple(v) for k, v in (cfg.get('nappes') or {}).items()})
        self.trim = dict(TRIM, **{FB.canonical(k): float(v) for k, v in (cfg.get('corrections_db') or {}).items()})
        self.force = dict(FORCE, **(cfg.get('fichiers') or {}))
        self.steps = dict(STEPS, **(cfg.get('pas') or {}))
        self.voice_lufs = float(cfg.get('voix_lufs', -20.)); self.duck_fx = float(cfg.get('baisse_fx', .37)); self.duck_bed = float(cfg.get('baisse_nappes', .65))
        self.duck_mus = float(cfg.get('baisse_musique', DUCK_MUSIC))
        self.lib = library(int(cfg.get('graine', 313)))

    def wav_file(self, rel):
        p = rel if os.path.isabs(rel) else os.path.join(REAL, rel)
        if not os.path.exists(p): raise KitError(f'fichier son introuvable : {p}')
        a, sr = self.LB.read_wav(p)
        if sr != self.SR: a = np.interp(np.arange(0, len(a), sr / self.SR), np.arange(len(a)), a).astype(np.float32)
        return self.LB.edges(a)

    def fit(self, a, dur):
        if dur is None: return a
        n = int(dur * self.SR)
        if len(a) < n: a = self.LB.tile(a, n, int(.08 * self.SR))
        return fade(a[:n], 0., min(.25, dur / 6))

    def source(self, c, dur):
        """the raw sound of a cue (before its level)"""
        name, t = c['name'], float(c['t']); k = self.FB.canonical(name)
        if c.get('file'): a = self.wav_file(c['file']); return self.fit(a, dur) if dur else a
        if name in self.force: a = self.wav_file(self.force[name]); return self.fit(a, dur) if dur else a
        if self.FB.has(name): return self.FB.make(k, dur)
        if self.lib.has(name):
            a = self.lib.render(name, dur, t)
            if a is not None and len(a): return self.fit(np.asarray(a, np.float32), dur) if dur else np.asarray(a, np.float32)
        if name in self.S.SFX: return np.asarray(self.S.make(name, dur, at=t), np.float32)
        raise KitError(f"bruitage inconnu « {name} » (à {t:.2f} s) : python -m hstudio.histoire catalogue --sons")

    def is_bed(self, c):
        k = self.FB.canonical(c['name'])
        if c.get('bus') in ('fx', 'bed'): return c['bus'] == 'bed'
        if k in self.bed: return True
        if self.FB.has(c['name']) and self.FB.SOUNDS[k]['kind'] == 'bed': return True
        return bool(c.get('dur')) and k not in self.steps

    def is_music(self, c):
        """the « musique » bus: bus='musique', or a name starting with musique_ (an explicit bus 'fx' / 'bed' wins)"""
        if c.get('bus') in ('fx', 'bed'): return False
        return c.get('bus') == 'musique' or self.FB.canonical(c['name']).startswith('musique_')

    def render_cue(self, c):
        """-> (array, start sample, bus)"""
        S, SR = self.S, self.SR
        name, t, g, dur = c['name'], float(c['t']), float(c['gain']), c.get('dur'); k = self.FB.canonical(name)
        if self.is_music(c):                                # background music: level from its nominal RMS, musical fades
            d = float(dur or 30.)
            a = np.asarray(self.source(c, d), np.float32)
            ref_db, ref_g = self.bed.get(k, (-33., g))
            spec = self.FB.SOUNDS.get(k) if self.FB.has(name) and not c.get('file') else None
            r = db(spec['rms_db']) if spec and spec.get('rms_db') is not None else rms(a[: int(SR * min(d, 30.))])
            a = a * (db(ref_db) * (g / max(ref_g, 1e-6)) / max(r, 1e-6))
            a = fade(a, float(c.get('fade_in', min(1.5, d / 5))), float(c.get('fade_out', min(2.5, d / 4))))
            bus = 'musique'
        elif self.is_bed(c):
            d = float(dur or 6.)
            a = np.asarray(self.source(c, d), np.float32)
            ref_db, ref_g = self.bed.get(k, (-30., g))
            a = a * (db(ref_db) * (g / max(ref_g, 1e-6)) / max(rms(a[: int(SR * min(d, 30.))]), 1e-6))
            a = fade(a, float(c.get('fade_in', min(.6, d / 5))), float(c.get('fade_out', min(1.2, d / 4))))
            bus = 'bed'
        elif k in self.steps and dur:
            out = np.zeros(int((dur + .6) * SR), np.float32); n = 0; tt = 0.
            while tt < dur:
                x = np.asarray(self.source(c, None), np.float32); x = x * (db(ONE_DB) * g / max(self.LB.short_rms(x), 1e-6)) * (1. if n % 2 == 0 else .8)
                S.addat(out, int(tt * SR), x); tt += 1. / self.steps[k]; n += 1
            a, bus = out, 'fx'
        else:
            x = np.asarray(self.source(c, None), np.float32); x = x * (db(ONE_DB) * g / max(self.LB.short_rms(x), 1e-6))
            rep = int(c.get('repeat') or 1); gap = float(c.get('gap') or 0.)
            if rep > 1:
                out = np.zeros(int((rep * (len(x) / SR + gap) + 1) * SR), np.float32)
                for i in range(rep): S.addat(out, int(i * (len(x) / SR + gap) * SR), x)
                x = out
            if c.get('fade_in') or c.get('fade_out'): x = fade(x, float(c.get('fade_in') or 0.), float(c.get('fade_out') or 0.))
            a, bus = x, 'fx'
        if c.get('stop') is not None:                       # the ringing stops when the handset is lifted...
            n = max(1, int((float(c['stop']) - t) * SR))
            if n < len(a): a = fade(a[:n], 0., .03)
        if c.get('phone'): a = S.band(a, 300., 3400.) * 1.4
        if c.get('lp'): a = S.lp(a, float(c['lp']))
        if c.get('hp'): a = S.hp(a, float(c['hp']))
        if c.get('muffle'):                                 # behind walls from that instant on
            m_t, ramp = (list(c['muffle']) + [1.5])[:2]
            tt = (int(t * SR) + np.arange(len(a))) / SR; m = np.clip((tt - float(m_t)) / max(float(ramp), .01), 0, 1).astype(np.float32)
            a = a * (1 - m) + S.lp(a, 900.) * m * .4
        a = np.asarray(a, np.float32) * db(self.trim.get(k, 0.))
        return a, int(t * SR), bus

    def voice(self, N, tmp):
        vp = os.path.join(tmp, 'voice.wav')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', self.st.voice, '-af', 'highpass=f=70,acompressor=threshold=0.063:ratio=2.5:attack=8:release=150:knee=3',
                        '-ac', '1', '-ar', str(self.SR), '-c:a', 'pcm_f32le', vp], check=True)
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', vp, '-f', 'f32le', '-ac', '1', '-ar', str(self.SR), '-'], capture_output=True, check=True).stdout
        v = np.frombuffer(raw, '<f4').astype(np.float32)
        Iv, _, _ = measure(vp); v = v * db(self.voice_lufs - Iv)
        out = np.zeros(N, np.float32); out[:min(N, len(v))] = v[:N]
        return out

    def activity(self, v, up=.5, down=.03):
        """0..1 per sample, quick to rise (30 ms), slow to fall (350 ms): the ducking key (music: MUSIC_KEY, slower)"""
        hop = self.SR // 100; n = len(v) // hop
        r = np.sqrt((v[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12); d = 20 * np.log10(r)
        act = np.clip((d + 48.) / 14., 0, 1); out = np.zeros(n); acc = 0.
        for i in range(n):
            k = up if act[i] > acc else down; acc += k * (act[i] - acc); out[i] = acc
        return np.interp(np.arange(len(v)) / hop, np.arange(n), out).astype(np.float32)


def write_wav(path, a, sr):
    a = np.asarray(a, np.float32)
    if a.ndim == 1: a = np.stack([a, a], 1)
    raw = path + '.f32'; a.astype('<f4').tofile(raw)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'f32le', '-ar', str(sr), '-ac', '2', '-i', raw, '-c:a', 'pcm_f32le', path], check=True); os.remove(raw)


def normalize(src, dst, log=print):
    """gain to -14 LUFS + limiter; repeated until -14 ± 0.2 LUFS and a true peak at or under -1.3 dBTP"""
    I0, _, _ = measure(src); gain = TARGET_I - I0; lim = db(-1.6); I = tp = lra = None
    for it in range(6):
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-af', f'volume={gain:.3f}dB,alimiter=limit={lim:.4f}:attack=2:release=60:level=disabled:latency=1',
                        '-c:a', 'pcm_s24le', dst], check=True)
        I, tp, lra = measure(dst)
        log(f'    passe {it + 1} : gain {gain:+.2f} dB, plafond {20 * math.log10(lim):.2f} dBFS -> {I:.1f} LUFS, crête {tp:.1f} dBTP')
        if abs(I - TARGET_I) <= .2 and tp <= TARGET_TP: break
        if tp > TARGET_TP: lim *= db(TARGET_TP - tp - .15)
        gain += TARGET_I - I
    return I, tp, lra


def mix(folder, log=print):
    st = Story(folder); st.need(st.voice, "fais l'étape voix")
    dec, mod = PJ.build(folder, log, quiet=True)
    M = Mixer(st, mod, log); SR = M.SR
    cues = read_json(st.cues); D = float(dec['duree_long']); N = int((D + 1) * SR)
    lines = read_json(st.lignes)
    tmp = tempfile.mkdtemp(prefix='kit_mix_')
    try:
        voice = M.voice(N, tmp)
        fx = np.zeros(N, np.float32); bed = np.zeros(N, np.float32); mus = None
        for c in cues:
            a, o, bus = M.render_cue(c)
            if bus == 'musique':
                if mus is None: mus = np.zeros(N, np.float32)
                M.S.addat(mus, o, a); continue
            M.S.addat(fx if bus == 'fx' else bed, o, a)
        act = M.activity(voice)
        full = voice + fx * (1. - M.duck_fx * act) + bed * (1. - M.duck_bed * act)
        if mus is not None:                                 # only with music cues: without them the mix is bit-identical
            full = full + mus * (1. - M.duck_mus * M.activity(voice, *MUSIC_KEY))
            log(f'  musique : bus dédié, baisse {M.duck_mus:.0%} sous la voix (nappes {M.duck_bed:.0%})')
        e0 = int(min(D - .3, lines[-1]['end'] + .1) * SR); e1 = int(D * SR)
        full[e0:e1] *= np.linspace(1, 0, e1 - e0, dtype=np.float32); full = full[:e1]
        os.makedirs(st.mix, exist_ok=True); res = {}
        for v in [x for x in dec['versions'] if x['id'] != 'complet_9x16']:
            a = int(v['t0'] * SR); b = int((v['t0'] + v['dur']) * SR)
            part = full[a:b].copy()
            fi = .1 if v['t0'] > 0 else 0.; fo = float(v.get('fade_out') or 0.)
            part = fade(part, fi, fo)
            pre = os.path.join(tmp, f"pre_{v['id']}.wav"); write_wav(pre, part, SR)
            log(f"  {v['id']} ({v['dur']:.1f} s)")
            I, tp, lra = normalize(pre, st.mix_wav(v['id']), log)
            ok = abs(I - TARGET_I) <= .5 and tp <= -1.0
            res[v['id']] = dict(LUFS=round(I, 2), dBTP=round(tp, 2), LRA=round(lra, 2), duree=round(v['dur'], 3), conforme=ok)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    write_json(os.path.join(st.mix, 'mesures.json'), res)
    for k, r in res.items():
        log(f"{k} : {r['LUFS']:.1f} LUFS intégrés, crête vraie {r['dBTP']:.1f} dBTP, LRA {r['LRA']:.1f} LU {'✓' if r['conforme'] else '✗ HORS CIBLE'}")
    if not all(r['conforme'] for r in res.values()): raise KitError('mixage hors cible (-14 LUFS ±0,5, crête ≤ -1 dBTP)')
    log('Étape suivante : rendre (si ce n\'est pas fait), puis livrer')
    return res
