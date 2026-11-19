"""CLIP MUSICAL : la musique comme partition de la mise en scène (repris du module « représentation musicale »
de moteur_voxel, engine/music.js, et branché sur le format de scène dirigée : il vaut pour PS1, VOXEL, CONSOLE).

Deux usages :

1. Dans le script du directeur (Python), pour POSER les plans sur la musique :

    from hstudio.audio import music_cues as MC
    M = MC.load('analysis.json')                  # sortie de hstudio/audio/music_analysis.py
    M.cuts(0, 24, every=2)                         # premiers temps de mesure, une coupe toutes les 2 mesures
    M.snap(13.1)                                   # le temps le plus proche
    M.pulse(t0, t1, dt, base=.2, amp=.8)           # une valeur par image qui « bat » (state_track d'une lumière)
    ep['music_clip'] = M.embed()                   # ce qu'il faut au moteur, dans l'épisode lui-même

2. Dans le moteur, une caméra en clés peut battre sur la musique :

    "camera": {"rig": "path", "keys": [...], "pulse": {"on": "beats", "fov": 2.5, "shake": 0.3, "decay": 0.18, "energy": 1}}

   `fov` : de combien de degrés le champ se resserre sur le temps (coup de zoom), `shake` : tremblé ajouté,
   `decay` : temps de retombée (s), `energy` : 0 = même force partout, 1 = proportionnel à l'énergie du moment.
   Sans `pulse` ou sans `music_clip` dans l'épisode, rien ne change.
"""
import json, math
from bisect import bisect_right


def _env(arr, t, decay):
    i = bisect_right(arr, t) - 1
    return 0. if i < 0 else math.exp(-(t - arr[i]) / max(1e-3, decay))


class Music:
    def __init__(self, A, offset=0.):
        self.A = A; self.offset = float(offset)
        sh = lambda xs: [float(x) - self.offset for x in xs]
        self.beats = sh(A.get('beats') or []); self.downbeats = sh(A.get('downbeats') or []); self.onsets = sh(A.get('onsets') or [])
        self.sections = [dict(s, t0=float(s['t0']) - self.offset, t1=float(s['t1']) - self.offset) for s in A.get('sections') or []]
        self.silences = [[a - self.offset, b - self.offset] for a, b in A.get('silences') or []]
        self.phrases = [[a - self.offset, b - self.offset] for a, b in (A.get('vocal') or {}).get('phrases') or []]
        self.syllables = sh((A.get('vocal') or {}).get('onsets') or [])
        e = A.get('energy') or {}; self.ehz = float(e.get('hz', 10)); self.ev = list(e.get('v') or [0.])
        self.tempo = float(A.get('tempo', 0)); self.period = float(A.get('beat_period', 0.5))

    def energy(self, t):
        k = (t + self.offset) * self.ehz; i = max(0, min(len(self.ev) - 2, int(math.floor(k)))) if len(self.ev) > 1 else 0
        if len(self.ev) < 2: return float(self.ev[0])
        f = min(1., max(0., k - i)); return float(self.ev[i] * (1 - f) + self.ev[i + 1] * f)

    def beat_env(self, t, decay=.16): return _env(self.beats, t, decay)
    def down_env(self, t, decay=.35): return _env(self.downbeats, t, decay)
    def beats_in(self, a, b): return [x for x in self.beats if a <= x < b]
    def downs_in(self, a, b): return [x for x in self.downbeats if a <= x < b]
    def snap(self, t, on='beats'):
        arr = self.downbeats if on == 'downbeats' else self.beats
        return min(arr, key=lambda x: abs(x - t)) if arr else t
    def section_at(self, t):
        for s in self.sections:
            if s['t0'] <= t < s['t1']: return s
        return self.sections[-1] if self.sections else None

    def cuts(self, a, b, every=1):
        """instants de coupe sur les premiers temps de mesure dans [a, b[, une toutes les `every` mesures"""
        d = self.downs_in(a, b); return d[::max(1, int(every))]

    def pulse(self, t0, t1, dt, base=0., amp=1., on='beats', decay=.18, energy=1.):
        """une valeur par image de t0 à t1 (bornes incluses + 1 image), qui monte sur chaque temps et retombe"""
        n = int(round((t1 - t0) / dt)) + 2; out = []
        for j in range(n):
            t = t0 + j * dt
            e = (self.down_env if on == 'downbeats' else self.beat_env)(t, decay)
            k = (1 - energy) + energy * self.energy(t)
            out.append(round(base + amp * e * k, 4))
        return out

    _NDC = ([0., .18], [-.2, -.08], [.2, .06], [0., -.2])

    def words_on_syllables(self, text, t0, t1, on='onsets', every=1, hold=1.4, ndc=None, enter='pop', leave='shrink', **style):
        """MOTS 3D (cubes, VOXEL) sur les syllabes chantées : un mot de `text` par attaque de syllabe dans [t0, t1[
        (`on="phrases"` : un par début de phrase chantée ; `every` : une attaque sur N). -> la liste à mettre dans `ep["words"]`.
        Le texte doit être ORIGINAL (jamais les paroles de la chanson). Chaque mot reste jusqu'à l'attaque suivante (au plus
        `hold` s) ; `ndc` : une position [x, y] dans le cadre (-1..1) ou une liste qu'on parcourt en boucle ; `style` : `size`, `dist`,
        `color`, `glow`, `lock`, `yaw`, `pitch`, `roll`, `tracking`, `stagger` (voir docs/FORMAT_EPISODE.md, « Mots 3D »)."""
        words = str(text).split()
        src = [p[0] for p in self.phrases] if on == 'phrases' else self.syllables
        times = [t for t in src if t0 <= t < t1][::max(1, int(every))]
        if not times: raise ValueError(f'aucune attaque de syllabe dans [{t0:.2f}, {t1:.2f}[ : lance la séparation de la voix (tools/clip_musical.py --separer)')
        if len(words) > len(times): raise ValueError(f'{len(words)} mots pour {len(times)} attaques dans [{t0:.2f}, {t1:.2f}[ : raccourcis le texte ou élargis l\'intervalle')
        pos = ndc if (ndc and isinstance(ndc[0], (list, tuple))) else ([ndc] if ndc else list(self._NDC))
        out = []
        for i, w in enumerate(words):
            end = min(times[i + 1], times[i] + hold) if i + 1 < len(times) else times[i] + hold
            out.append(dict(text=w, t0=round(times[i], 3), t1=round(max(end, times[i] + .25), 3), ndc=list(pos[i % len(pos)]), **{'in': enter, 'out': leave}, **style))
        return out

    def embed(self):
        """ce que le moteur lit dans l'épisode (`ep["music_clip"]`), temps déjà décalés"""
        return {'beats': [round(x, 3) for x in self.beats], 'downbeats': [round(x, 3) for x in self.downbeats],
                'energy': {'hz': self.ehz, 'v': self.ev, 'offset': self.offset}, 'tempo': self.tempo}


def load(path, offset=0.):
    with open(path, encoding='utf-8') as fh: return Music(json.load(fh), offset)


# ------------------------------------------------------------------ côté moteur
_CACHE = {}


def _from_ep(ep):
    mc = (ep or {}).get('music_clip')
    if not mc: return None
    key = id(mc)
    if key not in _CACHE:
        e = mc.get('energy') or {}
        A = {'beats': mc.get('beats') or [], 'downbeats': mc.get('downbeats') or [], 'energy': {'hz': e.get('hz', 10), 'v': e.get('v') or [0.]},
             'tempo': mc.get('tempo', 0)}
        m = Music(A); m.offset = float(e.get('offset', 0.)); _CACHE[key] = m       # les temps sont déjà décalés ; l'énergie garde son origine
        m.beats = [float(x) for x in A['beats']]; m.downbeats = [float(x) for x in A['downbeats']]
    return _CACHE[key]


def camera_pulse(ep, spec, g, fov, shake):
    """caméra en clés + `pulse` : (fov, tremblé) à l'instant absolu `g` du film"""
    m = _from_ep(ep)
    if m is None or not isinstance(spec, dict): return fov, shake
    on = spec.get('on', 'beats'); decay = float(spec.get('decay', .18 if on == 'beats' else .35))
    e = (m.down_env if on == 'downbeats' else m.beat_env)(g, decay)
    ke = float(spec.get('energy', 1.)); k = (1 - ke) + ke * m.energy(g)
    return fov - float(spec.get('fov', 2.)) * e * k, shake + float(spec.get('shake', 0.)) * e * k
