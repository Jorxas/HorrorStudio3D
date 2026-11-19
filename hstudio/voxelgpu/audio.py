"""Optional sound of a contract, composed with B's own synthesis (audio/music.py procedural score per style, audio/synth.py
~100 synthesised SFX, audio/ambience.py looping ambiences). Pure synthesis BY DEFAULT: the sample library is switched OFF here so that
nothing but code written for this studio ends up in a film, and old films render exactly as before. Deterministic (seeded).
REAL SOUNDS (opt-in): `"samples": true` in the contract's `audio` (or HSTUDIO_VOX_SAMPLES=1 when the key is absent) lets the real recordings of
library/audio_real (tools/sfx_bank_import.py : footsteps on 6 surfaces, doors, creaks, loops of rain / wind / city...) answer first for every key they cover ;
the synthesis stays the fallback for the others. `"samples": false` forces synthesis. Banks and licences : library/audio_real/banks/*/CREDITS.json.

contract["audio"] = {
  "music":    [{"t0": 0, "t1": 12, "style": "adventure|comedy|romance|mystery|sad|action|calm|epic", "gain": .5, "seed": 0, "fade": 1.0}],
  "ambience": [{"t0": 0, "t1": 12, "name": "park", "gain": .35}],
  "sfx":      [{"t": 3.2, "name": "door_slam", "gain": .8, "dur": null}],
  "foley":    {"steps": true, "gain": .5}          # footsteps at the heel strikes of every walker (ground from the world)
  "wav": "path.wav"                                 # OR an existing score to use as is (e.g. the one of « La marche »)
}"""
import math, os, subprocess, wave
from pathlib import Path
import numpy as np
from ..audio import synth as S, music as M, ambience as AMB
from .worlds import WORLDS

SR = S.SR
REAL_ROOT = str(Path(__file__).resolve().parents[2] / 'library' / 'audio_real')
SEQ = {'footsteps_walk': ('step_hard', 1.9, 1.), 'footsteps_run': ('footsteps_run_step', 3.5, 1.), 'footsteps_heavy': ('footsteps_heavy_step', 1.6, 1.3)}    # séquences de pas rebâties avec une variante par pas
_REAL = {}


def samples_on(a):
    """\"samples\" de l'audio du contrat ; sans la clé : HSTUDIO_VOX_SAMPLES ; sinon FAUX (comportement historique)"""
    v = a.get('samples')
    if v is not None: return bool(v)
    return str(os.environ.get('HSTUDIO_VOX_SAMPLES', '')).lower() in ('1', 'on', 'true', 'yes')


def real_library(a):
    """la bibliothèque de vrais sons (ou None si elle est absente ou vide) ; graine = `audio.seed` pour des variantes reproductibles"""
    if not samples_on(a): return None
    from ..audio import library as L
    if 'lib' not in _REAL: _REAL['lib'] = L.SoundLibrary(root=REAL_ROOT).load()
    lib = _REAL['lib']; lib.seed = int(a.get('seed', 42))
    return lib if lib.keys() else None


def _provider(lib):
    def provider(name, dur=None, at=0.0):
        if name in SEQ and dur:                                    # une séquence de pas : un pas réel par battement, variante tirée par instant
            base, rate, k = SEQ[name]
            if lib.has(base):
                out = np.zeros(int((float(dur) + .3) * SR), np.float32); t = 0.; j = 0
                while t < float(dur):
                    x = lib.render(base, None, float(at) + t)
                    if x is not None: S.addat(out, int(t * SR), x * (1. if j % 2 == 0 else .82) * k)
                    t += 1. / rate; j += 1
                return out
        return lib.render(name, dur, at)
    return provider
GROUND = {'ville': 'step_hard', 'parc': 'footsteps_grass', 'automne': 'footsteps_grass', 'pluie': 'step_hard', 'glace': 'footsteps_snow', 'feu': 'footsteps_gravel',
          'bataille': 'footsteps_heavy', 'invasion': 'footsteps_gravel', 'vaisseau': 'step_hard', 'lune': 'footsteps_sand', 'cite': 'step_hard', 'astroport': 'step_hard', 'selene': 'footsteps_sand'}


def _fade(n, a, b):
    e = np.ones(n, np.float32); a = min(a, n // 2); b = min(b, n // 2)
    if a: e[:a] = np.linspace(0, 1, a) ** 1.5
    if b: e[n - b:] = np.linspace(1, 0, b) ** 1.5
    return e


def compose(contract, wav_path, steps_by_stage=None):
    """-> path of a stereo 16-bit WAV at 44.1 kHz, as long as the film"""
    a = contract.get('audio') or {}; prev = S.SAMPLE_PROVIDER; lib = real_library(a)
    try:
        S.SAMPLE_PROVIDER = _provider(lib) if lib is not None else None          # pure synthesis unless the contract asks for the real sounds (see module docstring)
        return _compose(contract, wav_path, lib)
    finally: S.SAMPLE_PROVIDER = prev


def _compose(contract, wav_path, lib):
    a = contract.get('audio') or {}; dur = float(contract['duration']); n = int(math.ceil(dur * SR)) + SR // 2
    mix = np.zeros(n, np.float32)
    if a.get('wav'):                                # an existing score is the base (e.g. the one of the brief), resampled to 44.1 kHz mono
        r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(a['wav']), '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True)
        base = np.frombuffer(r.stdout, np.float32); k = min(n, len(base)); mix[:k] += base[:k] * float(a.get('wav_gain', 1.))
    for i, m in enumerate(a.get('music') or []):
        i0 = int(m['t0'] * SR); i1 = min(n, int(m['t1'] * SR)); seg = M.render(m['style'], i1 - i0, seed=int(m.get('seed', i)))
        f = int(float(m.get('fade', 1.0)) * SR); mix[i0:i1] += seg[:i1 - i0] * _fade(i1 - i0, f, f) * float(m.get('gain', .5))
    for i, m in enumerate(a.get('ambience') or []):
        i0 = int(m['t0'] * SR); i1 = min(n, int(m['t1'] * SR))
        if m['name'] not in AMB.AMBIENCES: raise ValueError(f"ambiance sonore inconnue : {m['name']}")
        seg = lib.render('amb_' + m['name'], (i1 - i0) / SR, float(m['t0'])) if (lib is not None and lib.has('amb_' + m['name'])) else None          # vrai lit sonore bouclé, sinon la synthèse
        seg = np.asarray(seg if seg is not None else AMB.ambience(m['name'], i1 - i0, seed=500 + i), np.float32)[:i1 - i0]; f = SR
        mix[i0:i0 + len(seg)] += seg * _fade(len(seg), f, f) * float(m.get('gain', .3))
    for i, c in enumerate(a.get('sfx') or []):
        S.reseed(900 + i); x = S.make(c['name'], c.get('dur'), at=float(c['t'])); i0 = int(c['t'] * SR)
        if 0 <= i0 < n: S.addat(mix, i0, x[:max(0, n - i0)] * float(c.get('gain', .8)))
    fol = a.get('foley')
    if fol and fol.get('steps', True):
        g = float(fol.get('gain', .5)); k = 0
        for st in contract['stages']:
            kind = fol.get('sound') or GROUND.get(st['world'], 'step_hard')
            for aid, lst in (st.get('foley_steps') or {}).items():
                for (t, x, z, h, side) in lst:
                    if st['t0'] <= t < st['t1']:
                        S.reseed(2000 + k); x_ = S.make('step', None, at=t) if kind == 'step_hard' else S.make(kind, .22, at=t); k += 1
                        S.addat(mix, int(t * SR), x_[:SR // 3] * g * (.8 + .2 * math.sin(k * 1.7)))
    vo = a.get('voice')
    if vo:                                          # the dialogue (a local voice, see localvoice.py): the bed is pulled down under every spoken stretch (ducking), then the voice is laid on top
        r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(vo['wav']), '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True)
        v = np.frombuffer(r.stdout, np.float32); k = min(n, len(v)); voice = np.zeros(n, np.float32); voice[:k] = v[:k] * float(vo.get('gain', 1.))
        w = int(.12 * SR); env = np.convolve(np.abs(voice), np.ones(w, np.float32) / w, mode='same'); act = (env > .006).astype(np.float32)
        att, rel = int(.06 * SR), int(.35 * SR); duck = np.zeros(n, np.float32); cur = 0.
        for i0 in range(0, n, 441):                  # 10 ms steps: fast attack, slow release
            tgt = float(act[i0]); cur += (tgt - cur) * (441. / att if tgt > cur else 441. / rel); duck[i0:i0 + 441] = cur
        ceil = float(vo.get('bed_ceiling', .35)); mix = np.tanh(mix / ceil) * ceil                # a soft ceiling on the bed: one loud effect (an engine, an impact) must not push the whole film down under the voice
        mix = mix * (1. - float(vo.get('duck', .5)) * duck) + voice
    peak = float(np.max(np.abs(mix))) or 1.
    if peak > .95: mix = mix * (.95 / peak)
    st = np.stack([mix, mix], 1)
    with wave.open(str(wav_path), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(st, -1, 1) * 32767).astype('<i2').tobytes())
    return str(wav_path)
