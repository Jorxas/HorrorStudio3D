"""Espace entre les acteurs et avec les décors : audit mesurable, obstacles issus des `props`, séparation lissée, distance de conversation.

Constat (mesuré par `audit()` sur des épisodes réels, voir docs/INTEGRATION_VOXEL_STUDIO.md) : les acteurs de VOXEL font ~2 m de haut et ~0,6 m de large ; la régie héritée de
PIXEL 3D les arrête à 0,95 m « centre à centre » d'une cible (`stop_dist`), les place là où l'épisode les écrit, et ne connaît d'obstacles que ceux du monde : les `props` d'un plan
(`bset`, `vox`, `craft`, décors convertis) ne comptaient pas pour l'A*, donc un personnage traversait un meuble.

Ce que fait ce module quand l'épisode porte `"spacing": true` (le studio le pose pour les nouveaux épisodes ; les films déjà faits ne bougent pas) :
  * `footprints(props)` : l'emprise au sol des boîtes entre 0,2 m et 1,6 m de haut -> obstacles de l'A* (`ObsWorld`) ;
  * `ConversationSpacing` : un acteur enveloppant autour de `ShotActing` qui écarte les acteurs image par image : distance PHYSIQUE minimale toujours (les corps ne se traversent
    pas), et distance de CONVERSATION (≈ 1,45 m) tant que l'un des deux parle dans le plan ; l'écartement est lissé (vitesse limitée) sauf à la première image du plan,
    et ne pousse jamais un acteur dans un obstacle ni un acteur assis hors de son siège ;
  * `"intimacy": true` (épisode ou plan) : la distance de conversation est levée (étreinte, combat, baiser), la distance physique reste ;
  * `spaced_actions(shot)` : les approches vers un acteur (`walk_to` avec `to` = un acteur) s'arrêtent à la distance de conversation au lieu de 0,95 m.
"""
import math
import numpy as np
from . import contract as C

RADIUS = .36                     # rayon d'un corps de taille 1 (m)
MARGIN = .10                     # jeu entre deux corps
CONV = 1.45                      # distance de conversation confortable, taille 1 (m)
VMAX = .9                        # vitesse maximale de l'écartement lissé (m/s)
SEATED = .55                     # deux personnes assises côte à côte
CI = {n: i for i, n in enumerate(C.ACTOR_COLS)}


def _kind(cast):
    k = (cast or {}).get('kind')
    return 'animal' if k == 'animal' else 'big' if k in ('creature', 'faceless') else 'human'


def radius_of(cast, scale=1.):
    return RADIUS * scale * {'human': 1., 'big': 1.2, 'animal': .6}[_kind(cast)]


def phys_dist(ca, sa, cb, sb, intimacy=False):
    d = radius_of(ca, sa) + radius_of(cb, sb) + MARGIN
    return d * (.9 if intimacy else 1.)


def conv_dist(ca, sa, cb, sb):
    if _kind(ca) == 'animal' or _kind(cb) == 'animal': return 0.
    big = {'human': 1., 'big': 1.3, 'animal': 1.}
    return CONV * (sa + sb) / 2. * (big[_kind(ca)] + big[_kind(cb)]) / 2.


# ---------------------------------------------------------------------------------------------------------------- obstacles
def footprints(props, lo=.2, hi=1.6, max_area=400.):
    """accessoires `bset` (ou toute liste de boîtes) -> rectangles (x0, z0, x1, z1) des boîtes qui barrent le passage d'un corps : au-dessus des chevilles, sous la tête"""
    out = []
    for p in props or []:
        for b in (p.get('boxes') or []) if isinstance(p, dict) else []:
            try:
                y0 = b['y'] - b['h'] / 2.; y1 = b['y'] + b['h'] / 2.
                if y1 < lo or y0 > hi or b['h'] < .04: continue
                ry = b.get('ry', 0.) or 0.; c, s = abs(math.cos(ry)), abs(math.sin(ry))
                hx = (b['w'] * c + b['d'] * s) / 2.; hz = (b['w'] * s + b['d'] * c) / 2.
                if 4 * hx * hz > max_area: continue
                out.append((b['x'] - hx, b['z'] - hz, b['x'] + hx, b['z'] + hz))
            except KeyError: continue
    return out


class ObsWorld:
    """un monde de la régie avec des obstacles en plus (les décors du plan) ; tout le reste est délégué au monde d'origine"""

    def __init__(self, world, extra):
        object.__setattr__(self, '_w', world); object.__setattr__(self, '_extra', list(extra))

    def obstacles(self): return list(self._w.obstacles()) + self._extra
    def __getattr__(self, k): return getattr(self._w, k)
    def __setattr__(self, k, v): setattr(self._w, k, v)


def _inside(p, rects, margin=.2):
    x, z = p
    for (x0, z0, x1, z1) in rects:
        if x0 - margin <= x <= x1 + margin and z0 - margin <= z <= z1 + margin: return True
    return False


# ---------------------------------------------------------------------------------------------------------------- actions
def spaced_actions(shot, casts, scale_of, intimacy=False):
    """copie du plan où chaque approche vers un acteur s'arrête à la distance de conversation (sauf `stop_dist` plus grand, ou intimité) : walk_to / run_to / sneak_to / go"""
    if intimacy or not shot.get('actions'): return shot
    acts = []; ch = False
    for a in shot['actions']:
        tgt = a.get('to')
        if a.get('do') in ('walk_to', 'run_to', 'sneak_to', 'go') and isinstance(tgt, str) and tgt in casts:
            who = a.get('who', 'hero'); d = conv_dist(casts.get(who), scale_of(casts, who), casts.get(tgt), scale_of(casts, tgt))
            if d and float(a.get('stop_dist', .95)) < d - 1e-6: a = dict(a, stop_dist=round(d, 3)); ch = True
        acts.append(a)
    return dict(shot, actions=acts) if ch else shot


# ---------------------------------------------------------------------------------------------------------------- séparation
def _resolve(pos, req, fixed, rects, iters=10):
    """positions {id: (x, z)} -> positions corrigées pour que chaque paire (i, j) soit au moins à req[(i, j)] ; un acteur `fixed` ne bouge pas ; on ne pousse pas dans un obstacle"""
    q = {k: np.array(v, float) for k, v in pos.items()}
    for _ in range(iters):
        worst = 0.
        for (i, j), dm in req.items():
            d = q[j] - q[i]; L = float(np.hypot(*d))
            if L >= dm - 1e-5: continue
            u = d / L if L > 1e-6 else np.array([1., 0.]); push = dm - L; worst = max(worst, push)
            wi = 0. if i in fixed else 1.; wj = 0. if j in fixed else 1.
            if wi + wj == 0: continue
            ni = q[i] - u * push * wi / (wi + wj); nj = q[j] + u * push * wj / (wi + wj)
            if rects:
                if wi and _inside(ni, rects) and not _inside(q[i], rects): nj = q[j] + u * push * (wj / (wi + wj) + wi / (wi + wj)); ni = q[i]
                elif wj and _inside(nj, rects) and not _inside(q[j], rects): ni = q[i] - u * push; nj = q[j]
            q[i], q[j] = ni, nj
        if worst < 1e-4: break
    return {k: (float(v[0]), float(v[1])) for k, v in q.items()}


class ConversationSpacing:
    """enveloppe d'un `ShotActing` : mêmes méthodes, positions corrigées (écartement physique + distance de conversation), calculées une fois sur tout le plan"""

    def __init__(self, sa, fps, casts, scale_of, intimacy=False, rects=()):
        self._sa = sa; self.fps = float(fps); self.intimacy = intimacy; self.rects = list(rects)
        self.ids = list(sa.tracks.keys()); n = int(math.ceil(sa.dur * self.fps)) + 6; self.times = np.arange(n) / self.fps
        sc = {a: scale_of(casts, a) for a in self.ids}; ca = {a: casts.get(a) or {} for a in self.ids}
        talkers = {a for a in self.ids if sa.tracks[a].talk}
        self.phys = {}; self.conv = {}
        for i, a in enumerate(self.ids):
            for b in self.ids[i + 1:]:
                self.phys[(a, b)] = phys_dist(ca[a], sc[a], ca[b], sc[b], intimacy)
                if (a in talkers or b in talkers) and not intimacy: self.conv[(a, b)] = conv_dist(ca[a], sc[a], ca[b], sc[b])
        self.off = {a: np.zeros((n, 2)) for a in self.ids}; self.stats = dict(pushed_frames=0, max_push=0.)
        if len(self.ids) >= 2: self._build(n)

    def _raw(self, t):
        s = self._sa.sample(t)
        return {a: (s[a]['x'], s[a]['z']) for a in self.ids if a in s}, {a for a in self.ids if a in s and (not s[a].get('visible', True) or s[a].get('seat') is not None)}, s

    def _build(self, n):
        prev = None
        for j, t in enumerate(self.times):
            raw, fixed, smp = self._raw(float(t)); vis = [a for a in raw if smp[a].get('visible', True)]
            req = {k: d for k, d in self.conv.items() if k[0] in vis and k[1] in vis}
            for k, d in self.phys.items():
                if k[0] in vis and k[1] in vis: req[k] = max(req.get(k, 0.), d if not (k[0] in fixed and k[1] in fixed) else SEATED)
            want = _resolve({a: raw[a] for a in vis}, req, fixed, self.rects)
            o_star = {a: np.array(want[a]) - np.array(raw[a]) for a in vis}
            cur = {}
            for a in vis:
                tgt = o_star[a]
                if prev is None or a not in prev: cur[a] = tgt                      # première image du plan : écartement immédiat, personne ne glisse depuis la position écrite
                else:
                    step = tgt - prev[a]; L = float(np.hypot(*step)); mx = VMAX / self.fps
                    cur[a] = prev[a] + (step if L <= mx else step * (mx / L))
            prev = cur
            P = {a: (raw[a][0] + cur[a][0], raw[a][1] + cur[a][1]) for a in vis}
            hard = {k: d for k, d in self.phys.items() if k[0] in vis and k[1] in vis}
            fin = _resolve(P, hard, fixed, self.rects)                                # la distance physique tient toujours, même si le lissage a du retard
            for a in vis:
                o = np.array(fin[a]) - np.array(raw[a]); self.off[a][j] = o
                if float(np.hypot(*o)) > 1e-3: self.stats['max_push'] = max(self.stats['max_push'], float(np.hypot(*o)))
            if any(float(np.hypot(*self.off[a][j])) > 1e-3 for a in vis): self.stats['pushed_frames'] += 1

    def _at(self, a, t):
        f = max(0., min(len(self.times) - 1.001, t * self.fps)); i = int(f); k = f - i
        return self.off[a][i] * (1 - k) + self.off[a][i + 1] * k

    def sample(self, t, *args, **kw):
        out = self._sa.sample(t, *args, **kw)
        for a in self.ids:
            if a in out:
                o = self._at(a, t)
                if abs(o[0]) + abs(o[1]) > 1e-6: out[a] = dict(out[a], x=out[a]['x'] + float(o[0]), z=out[a]['z'] + float(o[1]))
        return out

    def end_states(self):
        es = self._sa.end_states()
        for a, st in es.items():
            if a in self.off: o = self._at(a, self._sa.dur); st['x'] += float(o[0]); st['z'] += float(o[1])
        return es

    def __getattr__(self, k): return getattr(self._sa, k)


# ---------------------------------------------------------------------------------------------------------------- audit
def audit(contract, scale_of=None, intimacy=False):
    """contrat -> mesures : par plan et par paire d'acteurs la distance minimale, le nombre d'images sous la distance physique et sous la distance de conversation pendant qu'un des deux parle ;
    par acteur le nombre d'images dont les pieds sont dans l'emprise d'un décor du plan. Rien n'est modifié."""
    casts = contract.get('casts') or {}
    if scale_of is None:
        def scale_of(cs, a):
            d = cs.get(a) or {}; return float(d.get('scale') or (.95 if d.get('preset') == 'lina' else 1.05 if d.get('preset') == 'alien' else 1.))
    rep = dict(frames=0, pair_frames_below_phys=0, pair_frames_below_conv_talking=0, penetration_frames=0, min_pair=None, stages=[])
    for st in contract['stages']:
        rows = st.get('actors') or {}; ids = list(rows); n = min((len(r) for r in rows.values()), default=0); rects = footprints(st.get('props'))
        ent = dict(id=st.get('id'), pairs={}, penetration={})
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                ph = phys_dist(casts.get(a), scale_of(casts, a), casts.get(b), scale_of(casts, b)); cv = conv_dist(casts.get(a), scale_of(casts, a), casts.get(b), scale_of(casts, b))
                lo_ = 1e9; bp = bc = 0
                for j in range(n):
                    ra, rb = rows[a][j], rows[b][j]
                    if ra[CI['vis']] < .5 or rb[CI['vis']] < .5: continue
                    d = math.hypot(ra[CI['x']] - rb[CI['x']], ra[CI['z']] - rb[CI['z']]); lo_ = min(lo_, d)
                    if d < ph - 1e-3: bp += 1
                    if (ra[CI['talk']] > .3 or rb[CI['talk']] > .3) and cv and d < cv * .85 and not intimacy: bc += 1
                if lo_ < 1e8: ent['pairs'][f'{a}|{b}'] = dict(min=round(lo_, 2), below_phys=bp, below_conv=bc, phys=round(ph, 2), conv=round(cv, 2)); rep['pair_frames_below_phys'] += bp; rep['pair_frames_below_conv_talking'] += bc; rep['min_pair'] = lo_ if rep['min_pair'] is None else min(rep['min_pair'], lo_)
        for a in ids:
            pen = 0
            for j in range(n):
                r = rows[a][j]
                if r[CI['vis']] < .5: continue
                if _inside((r[CI['x']], r[CI['z']]), rects, margin=.0): pen += 1
            if pen: ent['penetration'][a] = pen; rep['penetration_frames'] += pen
        rep['frames'] += n; rep['stages'].append(ent)
    if rep['min_pair'] is not None: rep['min_pair'] = round(rep['min_pair'], 2)
    return rep
