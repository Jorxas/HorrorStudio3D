"""Bibliothèque d'aide du KIT HISTOIRE : ce que `histoire.py` importe (`from hstudio.histoire.lib import *`).

Généralise la mise en scène de « Chambre 313 » (HISTOIRE_CHAMBRE_313/dirige/chambre313.py) et la caméra qui cadre
de « Satisfied » (CLIP_SATISFIED_VOXEL/dirige/satisfied_lib.py). Guide complet : docs/GUIDE_HISTOIRE_POUR_IA.md.

Tous les TEMPS écrits dans histoire.py sont ABSOLUS (secondes du film, comme dans PHRASES.md) : `shot()` les ramène au
début du plan. Repère des lieux : x vers la droite de l'image quand on regarde vers +z, y vers le haut ;
yaw = atan2(dx, dz) : 0 regarde vers +z, PI/2 vers +x, PI vers -z, -PI/2 vers -x.

    ls(i), le(i)        début / fin de la phrase i (secondes) ; i peut être un numéro OU le début du texte de la phrase
    L('Tu décroches')   numéro de la phrase qui commence par ce texte (accents et majuscules ignorés)
    K(t, p, yaw, ...)   clé d'acteur (p = (x, z) ou (x, y, z)) ; les nombres glissent, les noms tiennent
    C(t, pos, look, fov) / CUT(...)   clé de caméra (CUT = coupe franche à cet instant)
    head('moi', 1.6)    cible de caméra qui suit la tête d'un acteur
    F.frame(t, sujet, H, f35, ...)    clé de caméra qui CADRE : H mètres de haut à l'image, focale 35 mm équivalente
    F.v(a16, a9)        valeur selon le format en cours (16:9 / 9:16)
    F.shot(l0, l1, cams, tracks, state, fx, ui, set, lighting, **autres)   un plan qui couvre les phrases l0..l1
    F.sfx(nom, t, gain, dur, **options)                                  un bruitage à l'instant t du film
Rien d'aléatoire ici : le même histoire.py donne toujours le même film."""
import math
import re
import unicodedata

PI = math.pi
E_, W_, N_, S_ = PI / 2, -PI / 2, 0., PI          # yaw that looks towards +x, -x, +z, -z
PRE = .12                                           # a shot starts this long before its first phrase (engine default)

# covered image HEIGHT (metres, at the subject) per shot size, for the PS1 characters (about 1.95 m, head 0.40 m,
# head centre at y = 1.68). VOXEL heads are bigger (about 0.5 m, centre at y = 1.8): add 15 to 20 % in close-ups.
SIZES = {'TGP': .6, 'GP': 1.0, 'PR': 1.4, 'PM': 1.8, 'PA': 2.3, 'PE': 3.0, 'PL': 6.0}
HEAD_Y = 1.68                                       # standing PS1 actor, head centre
CHEST_Y = 1.40

_LINES = None
_KEYS = None


# ------------------------------------------------------------------ phrases
def use_lines(lines):
    """called by the kit before histoire.py is executed"""
    global _LINES, _KEYS
    _LINES = list(lines); _KEYS = [_norm(l['text']) for l in _LINES]


def _need():
    if _LINES is None:
        raise RuntimeError("Les phrases ne sont pas chargées. Lance histoire.py par le kit : "
                           "python -m hstudio.histoire construire <dossier> (pas « python histoire.py »).")
    return _LINES


def _norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode('ascii').lower()
    s = re.sub(r"[^a-z0-9]+", ' ', s)
    return ' '.join(s.split())


def L(text, after=None):
    """index of the first phrase whose text STARTS with `text` (accents, case and punctuation ignored); if none starts
    with it, the first one that contains it. `after` : search from that phrase on (index or text)."""
    lines = _need(); key = _norm(text); i0 = 0 if after is None else idx(after)
    if not key: raise ValueError('L() : texte vide')
    for i in range(i0, len(lines)):
        if _KEYS[i].startswith(key): return i
    for i in range(i0, len(lines)):
        if key in _KEYS[i]: return i
    raise ValueError(f"L({text!r}) : aucune phrase ne contient ce texte (voir PHRASES.md)")


def idx(x):
    """a phrase number from an int or a text"""
    lines = _need()
    if isinstance(x, str): return L(x)
    i = int(x)
    if not 0 <= i < len(lines): raise ValueError(f'phrase {i} hors du script (0 à {len(lines) - 1}, voir PHRASES.md)')
    return i


def ls(i):
    """start of phrase i (seconds of the film)"""
    return float(_need()[idx(i)]['start'])


def le(i):
    """end of phrase i (seconds of the film)"""
    return float(_need()[idx(i)]['end'])


def shot_start(i, pre=PRE):
    """the instant a shot that begins on phrase i starts (0 for the first phrase)"""
    i = idx(i); return 0. if i == 0 else ls(i) - pre


def n_lines():
    return len(_need())


def text(i):
    return _need()[idx(i)]['text']


# ------------------------------------------------------------------ geometry
def _xz(p):
    p = tuple(float(c) for c in p)
    return (p[0], p[2]) if len(p) == 3 else (p[0], p[1])


def toward(a, b):
    """yaw for something at `a` to look at `b` ((x, z) or (x, y, z))"""
    (ax, az), (bx, bz) = _xz(a), _xz(b)
    return math.atan2(bx - ax, bz - az)


def ahead(p, yaw, d):
    """the point `d` metres in front of `p` for a body facing `yaw` (same form as p)"""
    p = tuple(float(c) for c in p)
    if len(p) == 3: return (p[0] + d * math.sin(yaw), p[1], p[2] + d * math.cos(yaw))
    return (p[0] + d * math.sin(yaw), p[1] + d * math.cos(yaw))


def right_of(p, yaw, d):
    """the point `d` metres to the RIGHT of a body at `p` facing `yaw` (negative = to its left)"""
    return ahead(p, yaw + PI / 2, d)


def K(t, p, yaw, **kw):
    """actor key at absolute time t: p = (x, z) or (x, y, z); other keys: face, gesture, hold, talk, head=[yaw, pitch],
    lean, crouch, sit, kneel, sit_floor, run, reach_r=[x, y, z, w], dissolve, vis, side, noblink, cut"""
    p = [float(x) for x in p]
    if len(p) == 2: p = [p[0], 0., p[1]]
    return dict({'t': round(float(t), 3), 'p': [round(x, 3) for x in p], 'yaw': round(float(yaw), 4)}, **kw)


def C(t, pos, look, fov, **kw):
    """camera key at absolute time t (look = point [x, y, z] or head('id')); kw: shake, roll"""
    return (t, list(pos), look, fov, kw)


def CUT(t, pos, look, fov, **kw):
    """camera key that CUTS (jumps) at absolute time t"""
    return (t, list(pos), look, fov, dict(kw, cut=True))


def head(aid, h=1.6, dx=0., dz=0.):
    """camera target that follows actor `aid` (h = height of the aimed point above its feet)"""
    return {'on': aid, 'h': h, 'dx': dx, 'dz': dz}


# focal length, 35 mm equivalent, measured on the LONG side of the frame (36 mm): in 16:9 the frame is 36 x 20.25 mm,
# in 9:16 it is 20.25 x 36 mm. Engine `fov`: vertical, times 0.72 in 16:9 (hstudio/engines/pixel3d/r3d.py BASE).
_VHALF = {'16:9': 10.125, '9:16': 18.0}
_FOVK = {'16:9': .72, '9:16': 1.0}


def fov_for(f35, aspect):
    """engine `fov` (degrees) for a 35 mm equivalent focal length in this format"""
    tv = _VHALF[aspect] / float(f35)
    return round(math.degrees(2 * math.atan(tv / _FOVK[aspect])), 2)


def covered_height(dist, fov, aspect):
    """image height (metres) covered at `dist` metres by an engine `fov` in this format"""
    return 2 * dist * math.tan(math.radians(fov) / 2) * _FOVK[aspect]


def distance_for(H, f35, aspect):
    """distance (metres) at which a f35 lens covers H metres of height in this format"""
    return H / (2 * _VHALF[aspect] / float(f35))


# 15/11/2026 (Le Phare qui efface, parties 2 à 4) : in 9:16 the WIDTH is the constraint. With an engine fov of 50 the horizontal half
# field is only atan(tan(25°) x 9/16) ≈ 14.7° : two actors 1 m apart need ~2 m of distance, and a face 1.5 m away fills the frame.
def covered_width(dist, fov, aspect='9:16'):
    """image WIDTH (metres) covered at `dist` metres by an engine `fov` in this format"""
    h = covered_height(dist, fov, aspect)
    return h * (9 / 16 if aspect == '9:16' else 16 / 9)


def distance_for_width(W, fov, aspect='9:16'):
    """distance (metres) at which an engine `fov` covers W metres of WIDTH in this format (a face ~0.9, two actors side by side ~1.6)"""
    return W / max(1e-6, covered_width(1., fov, aspect))


def beside(cam, look, dist, deg, y=0.):
    """a floor point at `dist` metres from the camera, `deg` degrees right (+) or left (-) of its line of sight : where to put an actor
    so that he is IN the narrow 9:16 frame (keep |deg| under the horizontal half field, about 14 to 19 degrees)"""
    a = math.atan2(look[0] - cam[0], look[2] - cam[2]) + math.radians(deg)
    return (cam[0] + math.sin(a) * dist, y, cam[2] + math.cos(a) * dist)


# ------------------------------------------------------------------ the film of one format
class Film:
    """one format of the story (16:9 or 9:16): its shots and its sound cues, in absolute time"""

    def __init__(self, aspect, style='ps1', default_set=None):
        if aspect not in ('16:9', '9:16'): raise ValueError(f'format inconnu : {aspect}')
        self.aspect = aspect; self.style = style; self.default_set = default_set
        self.shots = []; self.cues = []; self.meta = []          # meta: per shot, absolute start and camera keys (for the checks)

    def v(self, a16, a9):
        """the value for the format being built"""
        return a16 if self.aspect == '16:9' else a9

    def fov(self, f35):
        return fov_for(f35, self.aspect)

    def frame(self, t, subj, H, f35=35., look_yaw=None, facing=None, angle=0., from_pt=None, el=4., look=None, cut=False, **kw):
        """camera key that FRAMES the point `subj` (x, y, z) with H metres of image height (see SIZES), lens `f35`.
        Direction, one of: `look_yaw` (yaw the camera looks along) ; `facing` = yaw of the subject (the camera stands in
        front of it, `angle` degrees off its axis, + = on the subject's RIGHT side, so we see more of its right cheek);
        `from_pt` = (x, z) the camera comes from. `el` : degrees above the axis (+ = looking down). `look` : replace the
        aimed point (e.g. head('moi') to pan with someone). Distance = H / (2 tan(vertical half-angle))."""
        if look_yaw is None:
            if facing is not None: look_yaw = facing + PI + math.radians(angle)
            elif from_pt is not None: look_yaw = toward(from_pt, subj)
            else: raise ValueError('frame() : donne look_yaw, facing ou from_pt (la direction de la caméra)')
        d = distance_for(H, f35, self.aspect); e = math.radians(el); s = [float(c) for c in subj]
        pos = [s[0] - d * math.sin(look_yaw) * math.cos(e), s[1] + d * math.sin(e), s[2] - d * math.cos(look_yaw) * math.cos(e)]
        k = dict(kw)
        if cut: k['cut'] = True
        return (t, [round(c, 3) for c in pos], look if look is not None else [round(c, 3) for c in s], self.fov(f35), k)

    def shot(self, l0, l1, cams, tracks=None, state=None, fx=None, ui=None, set=None, lighting=None, pre=None, **extra):
        """one shot covering phrases l0..l1 (numbers or texts). `cams` : list of C / CUT / F.frame keys (absolute
        times) ; `tracks` : {actor: [K(...), ...]} (absolute times) ; `state` : the place's state keys, numbers
        animated with [a, b] (whole shot) or [a, b, t0, t1] (absolute times) ; `extra` : any other shot key of
        docs/FORMAT_EPISODE.md (stage_light, objects, weather, actors, sfx...), copied as is (times relative to the shot)."""
        a, b = idx(l0), idx(l1)
        if b < a: raise ValueError(f'plan {l0}-{l1} : la dernière phrase est avant la première')
        pre_ = PRE if pre is None else float(pre)
        t0 = 0. if a == 0 else ls(a) - pre_
        if not cams: raise ValueError(f'plan {a}-{b} : aucune clé de caméra')
        keys = []
        for c in cams:
            if len(c) < 4: raise ValueError(f'plan {a}-{b} : clé de caméra incomplète {c!r}')
            look = c[2] if isinstance(c[2], dict) else [round(float(x), 3) for x in c[2]]
            k = {'t': max(0., round(float(c[0]) - t0, 3)), 'pos': [round(float(x), 3) for x in c[1]], 'look': look, 'fov': round(float(c[3]), 2)}
            if len(c) > 4 and c[4]: k.update(c[4])
            keys.append(k)
        keys[0].pop('cut', None)
        bad = [i for i in range(1, len(keys)) if keys[i]['t'] < keys[i - 1]['t']]
        if bad: raise ValueError(f'plan {a}-{b} : clés de caméra dans le désordre {[k["t"] for k in keys]}')
        hold = dict(keys[-1], t=round(keys[-1]['t'] + 600., 3)); hold.pop('cut', None); keys.append(hold)  # the path never passes a cut on its last key
        sh = {'lines': [a, b], 'set': set or self.default_set, 'camera': {'rig': 'path', 'keys': keys}, 'state': _rel_state(state or {}, t0)}
        if pre is not None: sh['pre'] = pre_
        tr = {}
        for aid, ks in (tracks or {}).items():
            if not ks: continue
            ks = sorted((dict(k) for k in ks), key=lambda k: float(k['t']))
            if 'p' not in ks[0]: raise ValueError(f"plan {a}-{b} : la première clé de l'acteur {aid!r} doit donner la position p")
            tr[aid] = [dict(k, t=max(0., round(float(k['t']) - t0, 3))) for k in ks]
        for k in keys:
            if isinstance(k['look'], dict) and k['look'].get('on') not in tr:
                raise ValueError(f"plan {a}-{b} : la caméra suit {k['look'].get('on')!r} qui n'a pas de piste dans ce plan")
        if not tr: tr['_cam'] = [{'t': 0, 'p': [0., -50., -80.], 'yaw': 0., 'vis': 0}]      # a directed shot needs a track (invisible dummy far away)
        sh['tracks'] = tr
        if fx: sh['fx'] = dict(fx)
        sh['ui'] = dict(ui or {}); sh['ui'].setdefault('subs', 'low')
        if lighting: sh['lighting'] = lighting
        for k_, val in extra.items():
            if val is not None: sh[k_] = val
        self.shots.append(sh); self.meta.append({'t0': t0, 'lines': [a, b]})
        return sh

    def sfx(self, name, t, gain=.8, dur=None, **kw):
        """a sound at ABSOLUTE time t. Options: repeat, gap, stop (absolute instant it is cut), lp / hp (Hz),
        phone (telephone band), muffle=[t, ramp] (muffled behind walls from t on), fade_in, fade_out, bus ('fx'|'bed'|'musique' ; `musique_*` sounds go to 'musique' by themselves),
        file (a precise file of library/audio_real). Names: python -m hstudio.histoire catalogue --sons"""
        self.cues.append(dict(name=str(name), t=round(float(t), 3), gain=float(gain), dur=(None if dur is None else round(float(dur), 3)), **kw))

    s = sfx


def _rel_state(state, t0):
    out = {}
    for k, val in state.items():
        if isinstance(val, (list, tuple)) and len(val) == 4 and all(isinstance(x, (int, float)) for x in val):
            out[k] = [val[0], val[1], round(max(0., val[2] - t0), 3), round(max(.01, val[3] - t0), 3)]
        else: out[k] = val
    return out


__all__ = ['PI', 'E_', 'W_', 'N_', 'S_', 'PRE', 'SIZES', 'HEAD_Y', 'CHEST_Y', 'L', 'idx', 'ls', 'le', 'shot_start', 'n_lines', 'text',
           'toward', 'ahead', 'right_of', 'K', 'C', 'CUT', 'head', 'fov_for', 'covered_height', 'distance_for', 'covered_width', 'distance_for_width',
           'beside', 'Film', 'math']
