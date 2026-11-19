"""Lip sync for a PIXEL 3D (directed) episode painted by VOXEL: opt-in episode key `lipsync`.

    "lipsync": {"wav": "musique/stems/voix.wav",            # the voice alone (Demucs stem of a song, or a narration track)
                "actors": ["angelica", "eliza"] | "all",    # who gets a face layer (default: all actors)
                "gain": 1.0, "floor": 0.35, "max": 0.9,     # mouth = clamp((env - floor) / (1 - floor) * gain, 0, max)
                "range_db": 24, "offset": 0.0}              # loudness range mapped to 0..1 ; `offset` shifts the voice in time (s)

The mouth opens with the voice envelope ONLY while the actor's `talk` key is on (an envelope of a song holds every singer), so the
director says who sings when, the voice says how wide. The painter's own babble is switched off for those actors (their `talk`
column is zeroed) and replaced by a face layer (`faces` + `face_cols`, read by film_unified.js applyFace): expression from the
actor's own `face` key, mouth from the voice, deterministic blinks. Without the key nothing changes, byte for byte.
"""
import json, math, os
from . import contract as C

FACE_COLS = ['lx', 'ly', 'blink', 'bdi', 'bdo', 'mo', 'ms', 'tilt', 'e1', 'i1', 'e2', 'i2']
HZ = 100.
_CACHE = {}


def envelope_from_wav(path, hz=HZ, range_db=24.):
    """voice loudness, `hz` values per second, 0..1 (98th percentile = 1, `range_db` below it = 0: a sung note sits near the top,
    the gaps between syllables fall clearly), attack ~10 ms / release ~70 ms; cached next to the wav"""
    cache = f'{path}.env{int(hz)}_{int(range_db)}.json'
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(path):
        d = json.load(open(cache, encoding='utf-8')); return d['v'], float(d['hz'])
    import numpy as np, subprocess
    sr = 16000
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(sr), '-f', 's16le', '-'], capture_output=True, check=True).stdout
    y = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.
    hop = int(sr / hz); n = len(y) // hop
    rms = np.sqrt((y[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9); ref = np.percentile(db, 98); lo = ref - range_db
    e = np.clip((db - lo) / (ref - lo), 0, 1)
    out = np.zeros_like(e); a_up, a_dn = 1 - math.exp(-1 / (hz * .010)), 1 - math.exp(-1 / (hz * .070)); v = 0.
    for i, x in enumerate(e):
        v += (x - v) * (a_up if x > v else a_dn); out[i] = v
    vals = [round(float(x), 3) for x in out]
    json.dump(dict(hz=hz, v=vals, source=os.path.basename(path)), open(cache, 'w', encoding='utf-8'))
    return vals, float(hz)


def _h(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)


class Layer:
    def __init__(self, spec, base_dir, ids):
        wav = spec.get('wav')
        if not wav: raise ValueError('lipsync : `wav` (la voix seule) est obligatoire')
        if not os.path.isabs(wav): wav = os.path.join(base_dir or '.', wav)
        if not os.path.exists(wav): raise ValueError(f'lipsync : voix introuvable {wav}')
        rng = float(spec.get('range_db', 24.)); key = (wav, os.path.getmtime(wav), rng)
        if key not in _CACHE: _CACHE[key] = envelope_from_wav(wav, HZ, rng)
        self.v, self.hz = _CACHE[key]
        acts = spec.get('actors', 'all')
        self.actors = set(ids) if acts == 'all' else set(acts)
        self.gain = float(spec.get('gain', 1.)); self.floor = float(spec.get('floor', .35)); self.offset = float(spec.get('offset', 0.)); self.cap = float(spec.get('max', .9))
        self.seeds = {a: 1.7 + 3.1 * i for i, a in enumerate(sorted(self.actors))}
        self.used = False

    def env(self, t):
        x = (t - self.offset) * self.hz
        if x <= 0 or not self.v: return 0.
        i = int(x)
        if i >= len(self.v) - 1: return 0.
        f = x - i; return self.v[i] * (1 - f) + self.v[i + 1] * f

    def mouth(self, t):
        e = (self.env(t) - self.floor) / (1. - self.floor)
        return max(0., min(self.cap, e * self.gain))

    def blink(self, aid, t):
        """deterministic blinks: one per 4 s cell, at a hashed instant, 0.16 s each"""
        s = self.seeds.get(aid, 1.); k = int(math.floor(t / 4.))
        for c in (k - 1, k):
            u = (t - (c * 4. + .4 + 3. * _h(s + c * 1.37))) / .16
            if 0. <= u <= 1.: return 1. - abs(2 * u - 1.)
        return 0.

    def add_stage(self, stage, t0, fps):
        """face rows for the lip-synced actors of one stage (rows aligned with its camera rows); zeroes their `talk` column"""
        ti = C.ACTOR_COLS.index('talk'); ei = C.ACTOR_COLS.index('expr'); vi = C.ACTOR_COLS.index('vis')
        faces = {}
        for aid, rows in (stage.get('actors') or {}).items():
            if aid not in self.actors: continue
            out = []
            for j, r in enumerate(rows):
                t = t0 + j / fps
                talking = r[ti] >= .5 and r[vi] >= .5
                mo = self.mouth(t) if talking else 0.
                out.append([0., 0., round(self.blink(aid, t), 3), 0., 0., round(mo, 3), 0., 0., int(r[ei]), 1., 0, 0.])
                r2 = list(r); r2[ti] = 0.; rows[j] = r2          # a copy: two slices of a stage share their boundary rows
            faces[aid] = out
        if faces:
            stage['faces'] = {**(stage.get('faces') or {}), **faces}; self.used = True


def prepare(ep, ids):
    """-> Layer or None (no `lipsync` key: nothing changes)"""
    spec = ep.get('lipsync')
    if not spec: return None
    return Layer(spec, ep.get('_dir') or ep.get('base_dir') or '', ids)
