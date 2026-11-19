"""Real-sample sound library (bruitages) with the procedural synthesis kept as fallback.

An event key (the same keys as `synth.SFX`: `step_wood`, `door_slam`, `creak`...) points to one or more
sample variants declared in `library/audio/manifest.json`. The mixer keeps calling `synth.make(name, dur, at=t)`:
this module answers first for the keys it covers and returns None otherwise, so every key without assets
takes the original procedural path, unchanged.

What it guarantees, because the rest of the studio depends on it:
- deterministic: the variant and its jitter come from (episode seed, event key, cue time in ms), never from
  the clock and never from a shared RNG stream; the same episode gives the same mix;
- the validated mix balance is not touched: by default a sample is scaled to the loudness the procedural
  sound would have had for the same event (`"match": "synth"`), so sound effects stay under the voice
  exactly where the owner validated them (levels are then only shaped by the mixer's own gains / ducking);
- licences: a variant is loaded only if its credit block is complete and says the licence allows
  redistribution; everything rejected is listed in `problems` and shown by `python tools/sfxlib.py check`;
- a missing or unreadable file is never fatal: the event falls back to synthesis and the problem is recorded.

Opt-in: an episode asks for the library with `"sfx_library": true` (the demos do). Without the key it stays on the
synthesis it was validated with, so an old episode never changes sound on its own. `HSTUDIO_SFX_LIBRARY=1` opts in
globally for a listening session; `HSTUDIO_SFX_LIBRARY=0` is a kill switch that overrides even an opted-in episode.
"""
import json, os, subprocess, wave, zlib
import numpy as np
from . import synth as S

SR = S.SR
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'library', 'audio')
DEFAULTS = {
    'match': 'synth_short',  # synth_short (loudest 50 ms, best for real material) | synth (full rms) | synth_peak | rms | none
    'align': 'attack',      # attack (the transient lands on the cue time) | start
    'gain_db': 0.0,
    'target_rms': 0.06,     # used by "rms", and by "synth" when the key has no procedural counterpart
    'target_peak': 0.7,
    'pre_roll': 0.004,      # kept before the detected attack (s)
    'loop_xfade': 0.05,
    'min_scale': 0.03, 'max_scale': 32.0,
    'peak_ceiling': 0.95,   # headroom left before the mixer's own gains and soft clipper
}
CREDIT_FIELDS = ('source', 'url', 'author', 'licence', 'verified')
# impact-like events: their cue must land on the main hit (align "transient"), not on the first noise
# that leads to it. Everything else keeps "attack" (start the sound on the cue, keep what follows).
IMPULSIVE_EVENTS = ('step', 'step_wood', 'step_hard', 'step_grass', 'pickup', 'knock', 'door_slam',
                    'door_handle', 'metal_hit', 'glass_crack', 'glass_shatter', 'boom', 'impact', 'thump',
                    'punch', 'drip', 'land', 'jump_push', 'click', 'button', 'coin', 'pop')


# ---------------------------------------------------------------- decoding helpers
def read_wav(path):
    """mono-ready float32 + sample rate, standard library only (PCM 8/16/24/32 bits)"""
    with wave.open(path, 'rb') as w:
        n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(n)
    if sw == 2: a = np.frombuffer(raw, '<i2').astype(np.float32) / 32768.
    elif sw == 1: a = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128.) / 128.
    elif sw == 4: a = np.frombuffer(raw, '<i4').astype(np.float32) / 2147483648.
    elif sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        a = ((b[:, 0] | b[:, 1] << 8 | b[:, 2].astype(np.int8).astype(np.int32) << 16).astype(np.float32) / 8388608.)
    else: raise ValueError(f'{sw * 8} bits non supportés')
    if ch > 1: a = a.reshape(-1, ch).mean(1)
    return np.ascontiguousarray(a, np.float32), sr


def write_wav(path, a, sr=SR):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    pcm = (np.clip(np.asarray(a, np.float32), -1, 1) * 32767).astype('<i2')
    with wave.open(path, 'wb') as o:
        o.setnchannels(1); o.setsampwidth(2); o.setframerate(sr); o.writeframes(pcm.tobytes())


def ffmpeg_decode(path, cache_dir):
    """any other format (mp3, ogg, flac, float wav) through ffmpeg, decoded once into library/audio/.cache"""
    tag = zlib.crc32(f'{os.path.abspath(path)}|{os.path.getmtime(path)}'.encode()) & 0xffffffff
    dst = os.path.join(cache_dir, f'{os.path.splitext(os.path.basename(path))[0]}_{tag:08x}.wav')
    if not os.path.exists(dst):
        os.makedirs(cache_dir, exist_ok=True)
        subprocess.run(f'ffmpeg -v error -y -i "{path}" -ac 1 -ar {SR} -c:a pcm_s16le "{dst}"', shell=True, check=True)
    return read_wav(dst)


def edges(a, fin=.0005, fout=.005):
    """tiny fades so a cut sample never clicks"""
    a = np.array(a, np.float32)
    i = min(len(a) // 2, int(fin * SR)); o = min(len(a) // 2, int(fout * SR))
    if i > 1: a[:i] *= np.linspace(0, 1, i, dtype=np.float32)
    if o > 1: a[-o:] *= np.linspace(1, 0, o, dtype=np.float32)
    return a


def align_attack(a, pre=.004, win=.5, thr=.2):
    """drop the dead air at the head so the sound starts exactly on the cue time.

    Keeps everything that follows: right for an evolving sound (a creak, a rustle, a riser) whose
    loudest moment is not its beginning."""
    if not len(a): return a
    seg = np.abs(a[:min(len(a), int(win * SR))]); p = float(seg.max())
    if p <= 1e-6: return a
    i = max(0, int(np.argmax(seg > thr * p)) - int(pre * SR))
    return a[i:] if i > 0 else a


def align_transient(a, pre=.004, thr=.25):
    """put the MAIN hit on the cue time, dropping whatever leads up to it.

    Needed by real recordings: a door slam recorded in a room often starts with 300 ms of handle and
    hinge noise before the bang. For an impact cue the bang is what must land on the beat."""
    if not len(a): return a
    e = np.abs(a); p = float(e.max())
    if p <= 1e-6: return a
    i = max(0, int(np.argmax(e > thr * p)) - int(pre * SR))
    return a[i:] if i > 0 else a


def repitch(a, ratio):
    """resampling: for a short foley a ±1 semitone shift is the cheapest honest variation"""
    n = int(len(a) / ratio)
    if n < 8 or len(a) < 2: return a
    return np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)


def tile(a, n, xfade=2205):
    """loop a sample up to n samples with a crossfade (ambience-like events)"""
    if not len(a): return np.zeros(n, np.float32)
    x = max(0, min(xfade, len(a) // 3))
    out = np.zeros(n + len(a), np.float32); fi = np.linspace(0, 1, x, dtype=np.float32) if x > 1 else None
    pos = 0
    while pos < n:
        seg = np.array(a, np.float32)
        if fi is not None and pos > 0:
            seg[:x] *= fi; out[pos:pos + x] *= (1 - fi)
        m = min(len(seg), len(out) - pos); out[pos:pos + m] += seg[:m]
        pos += max(1, len(a) - x)
    return out[:n]


def rms(a):
    a = np.asarray(a, np.float64)
    return float(np.sqrt((a ** 2).mean())) if a.size else 0.


def short_rms(a, win=.05):
    """loudest 50 ms of the sound: the right target for a transient.

    A real bruitage has a much higher crest factor (14-25 dB measured) than the dense procedural sounds
    (13-16 dB), so matching the *average* rms asks for 3 to 11 times the gain, blows through the ceiling
    and ends up quieter after clamping. Matching the loudest window is both perceptually closer and safe."""
    a = np.asarray(a, np.float64)
    n = int(win * SR)
    if a.size <= n or n < 2: return rms(a)
    return float(np.sqrt(np.convolve(a ** 2, np.ones(n) / n, 'valid').max()))


# ---------------------------------------------------------------- the library
class SoundLibrary:
    def __init__(self, root=ROOT):
        self.root = root; self.enabled = True; self.seed = 42
        self.manifest = {}; self.defaults = dict(DEFAULTS); self.events = {}
        self.problems = []          # [{event, file, why}] licences, missing files, unreadable assets
        self.used = {}              # event key -> how many times a real sample was served (for the report)
        self._audio = {}; self._ref = {}; self._loaded = False

    # ---- manifest
    def load(self, force=False):
        if self._loaded and not force: return self
        self._loaded = True; self.events = {}; self.problems = []; self._audio = {}
        path = os.path.join(self.root, 'manifest.json')
        if not os.path.exists(path):
            self.manifest = {}; return self                      # no library: everything stays procedural
        with open(path, encoding='utf-8') as f: self.manifest = json.load(f)
        self.defaults = dict(DEFAULTS, **(self.manifest.get('defaults') or {}))
        for key, ev in (self.manifest.get('events') or {}).items():
            kept = []
            for v in (ev.get('variants') or []):
                why = self._reject(v)
                if why: self.problems.append(dict(event=key, file=v.get('file', '?'), why=why)); continue
                kept.append(v)
            if kept: self.events[key] = dict(ev, variants=kept)
        return self

    def _reject(self, v):
        if not v.get('file'): return 'entrée sans fichier'
        c = v.get('credit') or {}
        missing = [f for f in CREDIT_FIELDS if not c.get(f)]
        if missing: return 'licence non vérifiée (champs manquants : ' + ', '.join(missing) + ')'
        if c.get('redistribute') is not True: return f"licence « {c.get('licence')} » sans droit de redistribution vérifié"
        if not os.path.exists(os.path.join(self.root, v['file'])): return 'fichier absent'
        return None

    def has(self, key):
        self.load()
        return bool(self.enabled and key in self.events)

    def keys(self):
        self.load(); return sorted(self.events)

    def _note(self, event, file, why):
        p = dict(event=event, file=file, why=why)
        if p not in self.problems: self.problems.append(p)

    # ---- rendering
    def render(self, key, dur=None, at=0.0):
        """the sample for this event, already aligned, scaled and fitted - or None (use synthesis)"""
        if not self.enabled: return None
        self.load()
        ev = self.events.get(key)
        if ev is None: return None
        try:
            v, rng = self._pick(key, ev, at)
            a = self._asset(v)
            if a is None or not len(a): return None
            a = self._shape(key, ev, v, a, rng)
            a = self._fit(ev, a, dur)
        except Exception as e:                                   # a broken asset must never stop a render
            self._note(key, '?', f'rendu impossible : {e}')
            return None
        self.used[key] = self.used.get(key, 0) + 1
        return a

    def _pick(self, key, ev, at):
        """variant + jitter stream from (seed, key, cue time): same episode -> same mix"""
        h = zlib.crc32(f'{int(self.seed)}|{key}|{int(round(float(at) * 1000))}'.encode()) & 0xffffffff
        rng = np.random.default_rng(h)
        vs = ev['variants']; w = np.array([max(0., float(x.get('weight', 1.))) for x in vs], float)
        p = (w / w.sum()) if w.sum() > 0 else np.full(len(vs), 1. / len(vs))
        return vs[int(rng.choice(len(vs), p=p))], rng

    def _asset(self, v):
        path = os.path.join(self.root, v['file'])
        ck = (path, tuple(v.get('trim') or ()))
        if ck in self._audio: return self._audio[ck]
        try: a, sr = read_wav(path)
        except Exception: a, sr = ffmpeg_decode(path, os.path.join(self.root, '.cache'))
        if sr != SR and len(a) > 1:
            a = np.interp(np.arange(0, len(a), sr / SR), np.arange(len(a)), a).astype(np.float32)
        tr = v.get('trim')
        if tr:
            i = int(max(0., float(tr[0] or 0.)) * SR)
            j = len(a) if tr[1] in (None, 0, '') else int(float(tr[1]) * SR)
            a = a[i:max(i, j)]
        a = edges(a); self._audio[ck] = a
        return a

    def _opt(self, ev, v, name):
        return v.get(name, ev.get(name, self.defaults.get(name)))

    def _shape(self, key, ev, v, a, rng):
        align = self._opt(ev, v, 'align'); pre = float(self.defaults['pre_roll'])
        if align == 'attack': a = align_attack(a, pre)
        elif align == 'transient': a = align_transient(a, pre)
        g = self._scale(key, ev, v, a)
        pj = float(self._opt(ev, v, 'pitch_jitter') or 0.)
        if pj: a = repitch(a, 2 ** (float(rng.uniform(-pj, pj)) / 1200.))
        gj = float(self._opt(ev, v, 'gain_jitter_db') or 0.)
        if gj: g *= 10 ** (float(rng.uniform(-gj, gj)) / 20.)
        a = np.asarray(a, np.float32) * g
        ceil = float(self.defaults.get('peak_ceiling', .95))
        peak = float(np.abs(a).max()) if len(a) else 0.
        if peak > ceil: a = a * (ceil / peak)
        return a.astype(np.float32)

    def _scale(self, key, ev, v, a):
        """relative normalisation: a real sample is brought to the level of the sound it replaces"""
        mode = self._opt(ev, v, 'match'); gain = 10 ** (float(self._opt(ev, v, 'gain_db') or 0.) / 20.)
        if mode == 'none': return gain
        if mode == 'synth_peak':
            ref = self.reference(key, 'peak') or float(self.defaults['target_peak'])
            peak = float(np.abs(a).max()) if len(a) else 0.
            return gain * (ref / peak if peak > 1e-9 else 1.)
        meter = short_rms if mode == 'synth_short' else rms
        r = meter(a)
        if r <= 1e-9: return gain
        if mode == 'rms': ref = float(self.defaults['target_rms'])
        else: ref = self.reference(key, 'short' if mode == 'synth_short' else 'rms') or float(self.defaults['target_rms'])
        return gain * min(float(self.defaults['max_scale']), max(float(self.defaults['min_scale']), ref / r))

    def reference(self, key, kind='rms'):
        """loudness of the procedural sound for this key (measured once, with the RNG stream restored)"""
        ck = (key, kind)
        if ck in self._ref: return self._ref[ck]
        val = None
        if S.SFX.get(key) is not None:
            keep = S._rng
            try:
                S.reseed(777)
                x = np.asarray(S.synthesize(key), np.float32)
                val = float(np.abs(x).max()) if kind == 'peak' else (short_rms(x) if kind == 'short' else rms(x))
            except Exception: val = None
            finally: S._rng = keep
        self._ref[ck] = val
        return val

    def _fit(self, ev, a, dur):
        if dur is None: return a
        n = int(float(dur) * SR)
        if n <= 0 or not len(a): return a
        if len(a) < n and ev.get('loop'): a = tile(a, n, int(float(self.defaults['loop_xfade']) * SR))
        if len(a) > n:
            a = np.array(a[:n], np.float32); k = min(len(a), int(.03 * SR))
            if k > 1: a[-k:] *= np.linspace(1, 0, k, dtype=np.float32)
        return a

    # ---- report (tools/sfxlib.py check, tests)
    def check(self):
        self.load(force=True)
        events = {}
        for key, ev in sorted(self.events.items()):
            vs = []
            for v in ev['variants']:
                c = v.get('credit') or {}
                row = dict(file=v['file'], licence=c.get('licence'), author=c.get('author'), source=c.get('source'),
                           kind=c.get('kind', 'synthetic_placeholder'))
                try:
                    a = self._asset(v); row.update(ok=True, seconds=round(len(a) / SR, 3), peak=round(float(np.abs(a).max()), 4), rms=round(rms(a), 5))
                except Exception as e:
                    row.update(ok=False, why=str(e)); self._note(key, v['file'], f'lecture impossible : {e}')
                vs.append(row)
            served = self.render(key, None, 0.0)
            events[key] = dict(variants=vs, synth_rms=self.reference(key, 'rms'), synth_short=self.reference(key, 'short'),
                               served_rms=round(rms(served), 5) if served is not None else None,
                               served_short=round(short_rms(served), 5) if served is not None else None,
                               description=ev.get('description'), loop=bool(ev.get('loop')))
        known = set(S.SFX)
        return dict(root=self.root, version=self.manifest.get('version'), events=events, problems=list(self.problems),
                    covered=sorted(set(self.events) & known), library_only=sorted(set(self.events) - known),
                    still_synthetic=sorted(known - set(self.events)))


LIB = SoundLibrary()


ON, OFF = ('1', 'on', 'true', 'yes'), ('0', 'off', 'false', 'no')


def env_default():
    """what an episode without the `sfx_library` key gets: off, unless HSTUDIO_SFX_LIBRARY asks for it."""
    return str(os.environ.get('HSTUDIO_SFX_LIBRARY', '')).lower() in ON


def provider(name, dur=None, at=0.0):
    """installed as synth.SAMPLE_PROVIDER by audio/__init__.py; HSTUDIO_SFX_LIBRARY=0 is a global kill switch"""
    if str(os.environ.get('HSTUDIO_SFX_LIBRARY', '1')).lower() in OFF: return None
    return LIB.render(name, dur, at)
