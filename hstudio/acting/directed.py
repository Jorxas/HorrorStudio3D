"""Scène DIRIGÉE : la mise en scène écrite à la main (par Claude), la même pour tous les styles.

C'est la logique des films La Dernière Pompe et Le Remplaçant (premier moteur) : au lieu de verbes que la régie automatique interprète, le directeur écrit
  * les acteurs en CLÉS dans le temps (position, cap, expression, geste, regard, assis, main tendue, apparition `dissolve`...),
  * la caméra en CLÉS (position, cible, champ, tremblé),
  * l'état du monde dans le temps (lumières, portes, objets : clés `state`, `objects`, `lights` du plan).
Le format est celui du mode `tracks` de VOXEL, dans le repère des lieux du studio (PIXEL 3D) : x vers la droite de l'écran quand on regarde vers +z, y vers le haut.
La classe `DirectedActing` a la même interface que `timeline.ShotActing` : tous les styles (PS1, VOXEL, CONSOLE, Blender) la lisent sans rien changer à leur façon de peindre.

    "tracks": {"hero": [ {"t": 0, "p": [x, y, z], "yaw": 3.14, "face": "scared", "talk": 0, "head": [yaw, pitch], "vis": 1, "gesture": "point", "gw": 1,
                          "sit": 0, "crouch": 0, "air": 0, "lean": 0, "run": 0, "hands": "fist", "dissolve": 0.0, "reach_r": [x, y, z, w], "hold": "phone"},
                         {"t": 2.0, "p": [x2, y, z2], "yaw": 3.14} ]}
    "camera": {"rig": "path", "keys": [ {"t": 0, "pos": [x, y, z], "look": [x, y, z] | {"on": id, "h": 1.5, "dx": 0, "dz": 0}, "fov": 56, "roll": 0, "shake": 0, "cut": false} ]}

Les nombres (p, yaw, head, sit, crouch, air, lean, run, dissolve, reach_*) glissent (smoothstep) d'une clé à l'autre ; les noms (face, gesture, hands, hold) et drapeaux (talk, vis, back) tiennent jusqu'à
la clé suivante qui les change. `"cut": true` fait SAUTER les nombres (téléportation, changement de cadre). `yaw` = atan2(dx, dz) : 0 regarde vers +z. Rien d'aléatoire, aucune horloge.
Les gestes sont ceux de `acting/gestures.py` ; `reach_r` / `reach_l` = point à atteindre dans le repère du personnage (x vers sa droite pour `r`, z devant lui) et poids.
31/10/2026 : `side: "left"` joue le geste avec le bras GAUCHE (miroir) et met l'objet tenu dans la main gauche ; `kneel` (0..1) à genoux ; `sit_floor` (0..1) assis par terre,
jambes repliées sur le côté. Absents : rien ne change.
"""
import math

NUM = ('yaw', 'gw', 'sit', 'crouch', 'air', 'lean', 'run', 'slump', 'tension', 'dissolve', 'kneel', 'sit_floor')
VEC = ('p', 'head', 'reach_r', 'reach_l')
HOLD = ('face', 'gesture', 'hands', 'talk', 'vis', 'back', 'hold', 'noblink', 'side')            # noblink : le personnage ne cligne jamais des yeux (« elle ne cligne pas des yeux »)
STRIDE_WALK, STRIDE_RUN = 1.25, 2.1
DT = 1. / 60.


def smooth(k): k = max(0., min(1., k)); return k * k * (3 - 2 * k)


def _wrap(a): return (a + math.pi) % (2 * math.pi) - math.pi


class _Track:
    def __init__(self, aid, keys, seed):
        self.id = aid; self.seed = seed
        ks = sorted((dict(k) for k in keys), key=lambda k: float(k['t']))
        for k in ks: k['t'] = float(k['t'])
        if not ks or 'p' not in ks[0]: raise ValueError(f"piste {aid!r} : la première clé doit donner la position `p`")
        self.keys = ks; self.talk = []; self.events = []; self.visible = None; self.base_gesture = None; self.crouch0 = 0.; self.seat = None; self.airs = []; self.squats = []; self.reacts = []; self.reaches = []; self.gestures = []; self.ctrl = None


class DirectedActing:
    """interface de `timeline.ShotActing` pour des acteurs écrits en clés"""
    directed = True             # la tête et le regard sont écrits par le directeur : les lisseurs de la régie (eyeline, eye_smooth) s'effacent

    def __init__(self, shot, dur, world, cast=None):
        self.dur = float(dur); self.lines = []; self.world = world; self.doors = {}; self.items = {}; self.gaze = None; self.eyeflow = None
        self.spec_actors = {a.get('id'): a for a in (shot.get('actors') or []) if isinstance(a, dict)}
        self.tracks = {}
        for i, (aid, keys) in enumerate((shot.get('tracks') or {}).items()): self.tracks[aid] = _Track(aid, keys, float(i) * 1.7)
        self.lights = []; self.lightning = []; self.world_events = []
        self._dist = {}
        for aid in self.tracks: self._precompute(aid)

    # ------------------------------------------------------------ interpolation des clés
    def _state(self, ks, t):
        out = {}
        extra = sorted({k for key in ks for k in key if k.startswith('x_')})            # clés libres `x_...` : paramètres de jeu propres à une créature (faceless : x_tilt, x_recoil...)
        for name in VEC + NUM + tuple(extra):
            pts = [(k['t'], k[name], bool(k.get('cut'))) for k in ks if name in k]
            if not pts: continue
            i = 0
            while i + 1 < len(pts) and pts[i + 1][0] <= t: i += 1
            ta, va, _ = pts[i]
            if i + 1 >= len(pts) or pts[i + 1][2] or t <= ta: out[name] = va; continue
            tb, vb, _ = pts[i + 1]; kk = smooth((t - ta) / max(1e-6, tb - ta))
            if name == 'yaw': out[name] = va + _wrap(vb - va) * kk
            elif name in VEC: out[name] = [x + (y - x) * kk for x, y in zip(va, vb)]
            else: out[name] = va + (vb - va) * kk
        for name in HOLD:
            for k in ks:
                if k['t'] <= t and name in k: out[name] = k[name]
        return out

    def _precompute(self, aid):
        """distance parcourue (au pas de 1/60 s) : la phase de marche en découle, les pieds ne glissent pas"""
        tr = self.tracks[aid]; n = int(math.ceil(self.dur / DT)) + 2; xs = []; zs = []
        for j in range(n):
            p = self._state(tr.keys, j * DT).get('p', [0., 0., 0.]); xs.append(p[0]); zs.append(p[2])
        cum = [0.]
        for j in range(1, n): cum.append(cum[-1] + math.hypot(xs[j] - xs[j - 1], zs[j] - zs[j - 1]))
        self._dist[aid] = (cum, xs, zs)

    def _speed_dist(self, aid, t):
        cum, xs, zs = self._dist[aid]; n = len(cum)
        f = max(0., min(n - 1.001, t / DT)); i = int(f); w = f - i; d = cum[i] * (1 - w) + cum[i + 1] * w
        a = max(0, i - 9); b = min(n - 1, i + 9)
        v = (cum[b] - cum[a]) / max(1e-6, (b - a) * DT)
        return v, d

    # ------------------------------------------------------------ interface de la régie
    def end_states(self):
        out = {}
        for aid, tr in self.tracks.items():
            s = self._state(tr.keys, self.dur); p = s.get('p', [0., 0., 0.])
            out[aid] = dict(x=p[0], z=p[2], heading=s.get('yaw', 0.))
        return out

    def position(self, tr, t):
        p = self._state(tr.keys, t).get('p', [0., 0., 0.]); return (p[0], p[2])

    def door_angle(self, did, t): return 0.
    def door_handle(self, did, t): return (0., 1., 0.)
    def item_owner(self, item, t): return None
    def all_events(self):
        """pas calés sur les trajets écrits (un pas tous les ~0,62 m parcourus, plus longs en courant) : le bruitage suit le sol sous les pieds, sans que le directeur ait à les écrire"""
        ev = []
        for aid, tr in self.tracks.items():
            cum, xs, zs = self._dist[aid]; nxt = .3
            for j in range(1, len(cum)):
                if cum[j] - cum[j - 1] > .3: nxt = cum[j] + .3; continue          # saut de clé (`cut`) : pas de pas
                if cum[j] < nxt: continue
                t = j * DT; s = self._state(tr.keys, t)
                v = (cum[min(len(cum) - 1, j + 6)] - cum[max(0, j - 6)]) / (12 * DT)
                run = v > 2.2 or float(s.get('run', 0.)) > .5
                if s.get('vis', 1) and v > .15: ev.append((t, 'step', aid, {'run': run}))
                nxt = cum[j] + (.95 if run else .62)
        return sorted(ev, key=lambda e: e[0])

    def sample(self, t, look_at_camera=None):
        out = {}
        for aid, tr in self.tracks.items():
            s = self._state(tr.keys, t); p = s.get('p', [0., 0., 0.]); v, d = self._speed_dist(aid, t)
            w = max(0., min(1., (v - .08) / .35)); run = max(0., min(1., (v - 2.2) / 1.0)) if w > 0 else float(s.get('run', 0.))
            if 'run' in s and s['run'] > run: run = float(s['run'])
            stride = STRIDE_WALK + (STRIDE_RUN - STRIDE_WALK) * run
            phase = d / stride * 2 * math.pi
            if s.get('back'): phase = -phase
            gest = s.get('gesture'); gw = float(s.get('gw', 1.))
            rig = dict(t=t, seed=tr.seed, phase=phase, gait=w, run=run, stride=stride, sit=float(s.get('sit', 0.)), crouch=float(s.get('crouch', 0.)),
                       gestures=[(gest, gw, t)] if gest else [], lean=float(s.get('lean', 0.)), slump=float(s.get('slump', 0.)), tension=float(s.get('tension', 0.)),
                       head=tuple(s.get('head', (0., 0.))), hands=s.get('hands'), back=bool(s.get('back', 0)), bounce=0.)
            if s.get('air'): rig['air'] = float(s['air']); rig['air_k'] = .5
            if s.get('kneel'): rig['kneel'] = float(s['kneel'])                       # à genoux / assis par terre (rig.solve) ; absents : le dict d'avant
            if s.get('sit_floor'): rig['sit_floor'] = float(s['sit_floor'])
            if s.get('side') == 'left': rig['left'] = True                             # geste et objet tenu côté gauche
            h = float(s.get('yaw', 0.)); y = float(p[1]) if len(p) > 2 else 0.
            reach = {}
            for side, key in ((1, 'reach_r'), (-1, 'reach_l')):
                rc = s.get(key)
                if rc and rc[3] > 1e-3: reach[side] = ((rc[0], rc[1], rc[2]), rc[3])
            rig['reach'] = reach
            blink = (t * (1 / 3.3) + tr.seed) % 1. < .036 and not s.get('noblink')
            xs = {n[2:]: float(s[n]) for n in s if n.startswith('x_')}
            out[aid] = dict(x=float(p[0]), z=float(p[2]), xp=xs, y=y, heading=h, rig=rig, face=s.get('face', 'neutral'), hold=s.get('hold'), talking=bool(s.get('talk', 0)),
                            gaze=None, blink=blink, eye=(0., 0.), visible=bool(s.get('vis', 1)), seat=None, dissolve=float(s.get('dissolve', 0.)))
        return out


def path_camera(c, samp, T, shake_fn=None):
    """caméra écrite en clés -> (pos, cible, fov, roll en radians, tremblé) à l'instant T du plan ; `look` peut être un point ou {"on": acteur, "h", "dx", "dz"}"""
    keys = c['keys']; j = 0
    while j < len(keys) - 2 and T > float(keys[j + 1]['t']): j += 1
    a, b = keys[j], keys[min(j + 1, len(keys) - 1)]
    k = smooth((T - float(a['t'])) / max(1e-6, float(b['t']) - float(a['t']))) if b is not a else 0.
    if b is not a and (b.get('cut') or a.get('hold')): k = 0.

    def pt(v):
        if isinstance(v, dict):
            s_ = samp.get(v['on'])
            if s_ is None: raise ValueError(f"caméra : l'acteur {v['on']!r} n'est pas dans le plan")
            return (s_['x'] + float(v.get('dx', 0.)), float(v.get('h', 1.4)) + s_.get('y', 0.), s_['z'] + float(v.get('dz', 0.)))
        return tuple(float(x) for x in v)
    mix = lambda p, q: tuple(p[i] * (1 - k) + q[i] * k for i in range(3))
    fov = float(a.get('fov', c.get('fov', 56))) * (1 - k) + float(b.get('fov', c.get('fov', 56))) * k
    roll = float(a.get('roll', 0.)) * (1 - k) + float(b.get('roll', 0.)) * k
    shake = float(a.get('shake', 0.)) * (1 - k) + float(b.get('shake', 0.)) * k
    return mix(pt(a['pos']), pt(b['pos'])), mix(pt(a['look']), pt(b['look'])), fov, math.radians(roll), shake
