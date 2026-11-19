"""The blocking: where every actor is, at every instant of the whole film, decided ONCE and checked against the place.

A film is written as a story of ACTORS moving through a PLACE in ABSOLUTE film time (`beats`), not as a pile of shots that each re-place
their actors. The shots only choose a camera (hstudio/voxelgpu/camplan.py). So an actor cannot be somewhere in one shot and somewhere else
in the next one: there is one trajectory per actor and every shot looks at it.

    beats = [
      {'who': 'hero', 't': 11.9, 'do': 'go', 'to': 'porte_dedans', 'by': 14.0, 'face': 'ghost'},       # path planned on the real grid, arrival time given
      {'who': 'hero', 't': 14.1, 'do': 'touch', 'target': [0.7, 1.05, 3.44], 'dur': .8, 'hand': 'R'},    # the hand really reaches that point
      {'who': 'hero', 't': 14.2, 'do': 'look', 'at': 'ghost'},
      {'who': 'ghost', 't': 47.1, 'do': 'knock', 'target': 'porte_service', 'hits': [47.2, 48.7, 50.3]},
    ]

`compile_plan(plan, geo)` plans the paths (A* on `geo.grid`, with the portals that are open at that time), integrates heading and head turn with
rate limits, builds the contact tracks and returns a `Compiled`; `Compiled.sample(t)` answers in the dict that `director.RowMaker` reads,
the same one `tracks.TrackActing` returns, so the gait still comes out of the distance travelled (planted feet).
`audit(...)` is the deterministic preflight: it says in French every place where the story is physically or cinematically impossible, BEFORE
any image is drawn. Nothing is random and nothing reads a clock.
"""
import math
import numpy as np
from ..acting.timeline import Path, round_corners

DT = 1. / 120.
SHOULDER_Y, ARM, SHOULDER_X = 1.51, .566, .38         # A's body at scale 1 (chars4.js: shoulder 10.2 px above the hips at 14 px, arm 4.0 + 5.05 px, shoulder 6.1 px off axis)
KINDS = {'human': dict(r=.28, vmax=3.8, walk=1.15, scale=1.), 'faceless': dict(r=.34, vmax=5.0, walk=1.1, scale=1.05)}


class PlanError(ValueError):
    pass


def _wrap(a): return (a + math.pi) % (2 * math.pi) - math.pi
def _sm(k): k = max(0., min(1., k)); return k * k * (3 - 2 * k)


class Violation:
    def __init__(self, code, msg, t=None, who=None, **data): self.code, self.msg, self.t, self.who, self.data = code, msg, t, who, data
    def __repr__(self): return f"[{self.code}]{'' if self.t is None else f' t={self.t:.2f}s'}{'' if not self.who else f' {self.who}'} : {self.msg}"
    def to_json(self): return dict(code=self.code, msg=self.msg, t=self.t, who=self.who, **self.data)


# ----------------------------------------------------------------------------------------------------------------------- compile
class _Actor:
    def __init__(self, aid, spec, geo):
        self.id = aid; self.spec = spec; k = KINDS[spec.get('kind', 'human')]
        self.r = float(spec.get('radius', k['r'])); self.vmax = float(spec.get('vmax', k['vmax'])); self.scale = float(spec.get('scale', k['scale'])); self.walk = float(spec.get('walk', k['walk']))
        st = spec['start']
        if isinstance(st, str): x, z, yaw = geo.marks[st]
        else: x, z = st['at']; yaw = float(st.get('yaw', 0.))
        self.p0 = (x, z); self.yaw0 = yaw; self.moves = []; self.faces = [(-1e9, ('yaw', yaw))]; self.looks = []; self.contacts = []; self.faces_expr = []; self.helds = []
        self.gestures = []; self.hands = []; self.talk = []; self.end_pos = (x, z)
        self.talk_info = []; self.kind = spec.get('kind', 'human'); self.vis = [(-1e9, True)]; self.lip = bool(spec.get('lipsync')); self.persona = dict(spec.get('persona') or {})

    def pos(self, t):
        for m in self.moves:
            if t < m['t0']: break
            if m.get('warp'): continue                                  # a declared warp (vanish / appear elsewhere) has no path: it is handled below
            if t <= m['t1']: return m['path'].point(m['path'].dist(t))
        last = self.p0
        for m in self.moves:
            if t >= m['t1']: last = m['to']
        return last

    def moving(self, t):
        for m in self.moves:
            if not m.get('warp') and m['t0'] <= t <= m['t1']: return m
        return None

    def visible_at(self, t):
        cur = True
        for (tt, v) in self.vis:
            if tt <= t: cur = v
            else: break
        return cur


class Compiled:
    def __init__(self, plan, geo, actors, contacts, events):
        self.plan, self.geo, self.actors, self.contacts, self.events = plan, geo, actors, contacts, events
        self.fps = DT; self.dur = float(plan.get('duration', 0.)); self.arr = {}; self.tracks = {a: None for a in actors}; self.warnings = []; self.beats = []

    # --- exposed to the director
    def sample(self, t):
        out = {}
        for aid, A in self.actors.items(): out[aid] = self._row(A, t)
        return out

    def _row(self, A, t):
        a = self.arr[A.id]; n = len(a['x']); u = min(max(t / DT, 0.), n - 1.001); i = int(u); w = u - i
        L = lambda k: a[k][i] * (1 - w) + a[k][i + 1] * w
        yaw = a['yaw'][i] + _wrap(a['yaw'][i + 1] - a['yaw'][i]) * w
        face = A.face_at(t); talk = A.talk_at(t) and not A.lip       # a mouth driven by faceact's own lip-sync must not also babble in the painter
        mv = A.moving(t)
        rig = dict(sit=0., crouch=float(L('crouch')), air=0., lean=L('lean'), slump=0., tension=L('tension'), run=1. if L('run') > .5 else 0., head=(L('hyaw'), L('hpit')), gestures=[], hands=A.hands_at(t), back=bool(mv and mv['back']))
        x, z = L('x'), L('z'); gy = self.geo.ground_y(x, z) if self.geo.floors else 0.
        return dict(x=x, y=0. if gy is None else gy, z=z, heading=yaw, face=face, talking=talk, visible=A.visible_at(t), rig=rig)

    def end_states(self): return {}
    def position(self, tr, t): return (0., 0.)

    # --- helpers for the film / audit
    def declared_warps(self):
        """the supernatural disappearances / appearances the story DECLARED (beats `vanish` / `appear`): [{who, t0, t1, kind, why, to}] where t0 is the instant the actor
        stops being seen and t1 the instant he is seen again (the end of the film if never). Only these are allowed to break continuity; nothing else is."""
        out = []
        for e in self.events:
            if e['kind'] == 'vanish': out.append(dict(who=e['who'], t0=e['t'], t1=self.dur, kind=e.get('why_kind', 'supernatural'), why=e.get('why', ''), to=None))
            elif e['kind'] == 'appear':
                op = [w for w in out if w['who'] == e['who'] and w['t1'] >= self.dur and w['t0'] <= e['t']]
                if op: op[-1]['t1'] = e['t']; op[-1]['to'] = e.get('to')
                else: out.append(dict(who=e['who'], t0=e['t'], t1=e['t'], kind=e.get('why_kind', 'supernatural'), why=e.get('why', ''), to=e.get('to')))
        return out

    def in_warp(self, aid, t, pad=0.):
        return any(w['who'] == aid and w['t0'] - pad <= t <= w['t1'] + pad for w in self.declared_warps())

    def pos(self, aid, t): return self.actors[aid].pos(t)
    def xz(self, aid, t):
        a = self.arr[aid]; n = len(a['x']); u = min(max(t / DT, 0.), n - 1.001); i = int(u); w = u - i       # same interpolation as _row, without building the whole row
        return a['x'][i] * (1 - w) + a['x'][i + 1] * w, a['z'][i] * (1 - w) + a['z'][i + 1] * w
    def contacts_of(self, aid): return [c for c in self.contacts if c['who'] == aid]


def _Actor_face_at(self, t):
    cur = 'neutral'
    for (tt, f) in self.faces_expr:
        if tt <= t: cur = f
        else: break
    return cur


def _Actor_talk_at(self, t):
    return any(a <= t <= b for a, b in self.talk)


def _Actor_hands_at(self, t):
    cur = None
    for (tt, h) in self.hands:
        if tt <= t: cur = h
        else: break
    return cur


_Actor.face_at = _Actor_face_at; _Actor.talk_at = _Actor_talk_at; _Actor.hands_at = _Actor_hands_at


def _resolve(geo, spec):
    """a place: a mark name, [x, z] or {'at': [x, z]}"""
    if isinstance(spec, str):
        if spec not in geo.marks: raise PlanError(f"repère inconnu : {spec!r} (connus : {', '.join(geo.marks)})")
        x, z, _ = geo.marks[spec]; return (x, z)
    if isinstance(spec, dict): return tuple(spec['at'])
    return (float(spec[0]), float(spec[1]))


def _point3(geo, spec):
    """a 3D point: [x, y, z], an item name, a landmark name (its centre of the face turned to +z / the lot is NOT guessed: give an explicit point for a surface)"""
    if isinstance(spec, str):
        if spec in geo.items: return tuple(geo.items[spec]['at'])
        b = geo.land(spec); return ((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2)
    return tuple(float(v) for v in spec)


def compile_plan(plan, geo, verbose=False):
    actors = {aid: _Actor(aid, sp, geo) for aid, sp in plan['actors'].items()}
    beats = sorted(plan['beats'], key=lambda b: (float(b['t']), 0 if b.get('do') in ('go', 'run') else 1))
    events = []; contacts = []
    for b in beats:
        if b['who'] not in actors: raise PlanError(f"beat à t={b['t']} : acteur inconnu {b['who']!r}")
    # pass 1 : moves (positions), so that every later beat (facing an actor, aiming at him) can ask where somebody is
    for b in beats:
        A = actors[b['who']]; do = b['do']; t0 = float(b['t'])
        if do in ('go', 'run'):
            if A.moves and t0 < A.moves[-1]['t1'] - 1e-6: raise PlanError(f"{A.id} t={t0}: déplacement commencé avant la fin du précédent ({A.moves[-1]['t1']:.2f}s)")
            frm = A.end_pos; dst = _resolve(geo, b['to']); by = float(b['by'])
            path = _plan_path(geo, A, frm, dst, t0, by, b.get('via'))
            A.moves.append(dict(t0=t0, t1=path.t1, by=by, path=path, to=dst, frm=frm, v=path.v, run=1. if path.v > 2.0 else 0., fin=b.get('face'), back=bool(b.get('backwards')))); A.end_pos = dst
            events.append(dict(t=t0, who=A.id, kind='go', to=b['to'], by=by, dist=path.D, v=path.v))
        elif do == 'appear':                       # a DECLARED supernatural reappearance: the only way to be somewhere else without walking there
            dst = _resolve(geo, b['at']) if b.get('at') is not None else A.end_pos
            A.moves.append(dict(t0=t0, t1=t0, by=t0, path=None, to=dst, frm=A.end_pos, v=0., run=0., fin=None, back=False, warp=True)); A.end_pos = dst
    # pass 2 : facing / head / gestures / contacts / faces
    for b in beats:
        A = actors[b['who']]; do = b['do']; t0 = float(b['t'])
        if do in ('go', 'run'):
            m = [m_ for m_ in A.moves if not m_.get('warp')][[m_['t0'] for m_ in A.moves if not m_.get('warp')].index(t0)]
            if b.get('face') is not None: A.faces.append((m['t1'] - .35, _facing(b['face'])))
            else: A.faces.append((m['t1'], ('yaw', m['path'].tangent(m['path'].D) + (math.pi if m['back'] else 0.))))         # no facing asked: the body stays the way it walked
        elif do == 'face': A.faces.append((t0, _facing(b['at'])))
        elif do == 'look': A.looks.append((t0, _facing(b['at']) if b.get('at') is not None else ('clear', None), float(b.get('speed', 3.2)), float(b.get('delay', .0))))
        elif do == 'emote': A.faces_expr.append((t0, b['face']))
        elif do == 'react': pass                                   # a phasic reaction with a cause: played by faceact.py
        elif do == 'talk': A.talk.append((t0, float(b['until']))); A.talk_info.append((t0, float(b['until']), b.get('text'), float(b.get('loud', 1.))))
        elif do == 'hands': A.hands.append((t0, b['pose']))
        elif do in ('touch', 'knock', 'take', 'aim'):
            c = _contact(geo, A, b, actors); contacts += c['contacts']; events += c['events']
            for f in c.get('faces', []): A.faces.append(f)
        elif do in ('event', 'note'): events.append({**{k: v for k, v in b.items() if k not in ('who', 'do')}, 't': t0, 'who': A.id, 'kind': b.get('kind', 'note')})
        elif do == 'vanish':
            if not b.get('why'): raise PlanError(f"{A.id} t={t0}: une disparition doit dire pourquoi (clé « why ») : seules les disparitions DÉCLARÉES échappent au contrôle de téléportation")
            A.vis.append((t0, False)); events.append(dict(t=t0, who=A.id, kind='vanish', why=b['why'], why_kind=b.get('kind', 'supernatural'), event_type=b.get('event_type', 'supernatural_vanish'), source=b.get('source')))
        elif do == 'appear':
            A.vis.append((t0, True)); events.append(dict(t=t0, who=A.id, kind='appear', why=b.get('why', ''), why_kind=b.get('kind', 'supernatural'), to=list(A.end_pos if b.get('at') is None else _resolve(geo, b['at'])), event_type=b.get('event_type', 'supernatural_appear'), source=b.get('source')))
            if b.get('face') is not None: A.faces.append((t0, _facing(b['face'])))
        elif do in ('strike', 'clash', 'guard', 'flinch', 'kneel', 'draw'):
            from . import combat; combat.pass2(A, b, t0, events)
        else: raise PlanError(f"beat t={t0}: verbe inconnu {do!r}")
        if b.get('event_type') and do not in ('event', 'note', 'vanish', 'appear'): events.append(dict(t=t0, who=A.id, kind='event', event_type=b['event_type'], source=b.get('source'), loud=b.get('loud', 1.)))
    for A in actors.values():
        A.faces.sort(key=lambda f: f[0]); A.looks.sort(key=lambda f: f[0]); A.faces_expr.sort(key=lambda f: f[0]); A.hands.sort(key=lambda f: f[0])
    from . import eventreact
    warns = []; beats = list(beats) + eventreact.derive(plan, beats, actors, geo, events, warns)         # who perceived which event of the story, and what their face does about it
    for b in sorted([b for b in beats if b['do'] == 'react' and b.get('look') is not None], key=lambda b: float(b['t'])):    # a reaction turns the head to its cause, then back to what it was looking at
        A = actors[b['who']]; on = float(b['t']) + float(b.get('latency', .18)); back = on + float(b.get('hold', .5)) + .5
        prev = [lk for lk in A.looks if lk[0] <= on]; prev = prev[-1] if prev else None
        A.looks = [lk for lk in A.looks if not (on <= lk[0] <= back)] + [(on, _facing(b['look']), 4.5, 0.), (back, prev[1] if prev else ('clear', None), 2.2, 0.)]; A.looks.sort(key=lambda f: f[0])
    C = Compiled(plan, geo, actors, sorted(contacts, key=lambda c: c['t0']), sorted(events, key=lambda e: e['t']))
    C.warnings = [Violation(code, msg, t) for (code, msg, t) in warns]; C.beats = beats
    _integrate(C, float(plan['duration']))
    from . import faceact; faceact.attach(beats, C)
    return C


def _facing(spec):
    """what the body turns to: ('yaw', rad) | ('actor', id) | ('point', (x, z)) | ('mark', name resolved later)"""
    if isinstance(spec, (int, float)): return ('yaw', float(spec))
    if isinstance(spec, str): return ('actor', spec) if not spec.startswith('@') else ('mark', spec[1:])
    if isinstance(spec, dict) and 'actor' in spec: return ('actor', spec['actor'])
    return ('point', (float(spec[0]), float(spec[1])) + ((float(spec[2]),) if len(spec) > 2 else ()))


def _plan_path(geo, A, frm, dst, t0, by, via):
    pts = [frm]
    for v in (via or []): pts.append(_resolve(geo, v))
    pts.append(dst); full = [frm]; tm = (t0 + by) / 2
    open_now = tuple(p.id for p in geo.portals.values() if p.open_at(tm) or p.open_at(by) or p.open_at(t0 + .5 * (by - t0)))
    gr = geo.grid(A.r + .04, open_now)
    for a, b in zip(pts[:-1], pts[1:]):
        seg = gr.path(a, b)
        for i in range(len(seg) - 1):
            bad = geo.seg_free(seg[i], seg[i + 1], A.r - .02, tm if not open_now else None)
            if bad and bad not in open_now:
                allp = tuple(geo.portals); why = ''
                if open_now != allp:
                    alt = geo.grid(A.r + .04, allp).path(a, b)
                    if all(not geo.seg_free(alt[i], alt[i + 1], A.r - .02, None, skip_portals=True) for i in range(len(alt) - 1)):
                        need = [p.id for p in geo.portals.values() if p.id not in open_now and any(_disc_seg(alt, p.rect, A.r))]
                        why = f" : il faut passer par {need} qui est fermé à ce moment"
                raise PlanError(f"{A.id} : aucun chemin de {a} à {b} entre t={t0:.1f}s et {by:.1f}s{why or f' (bloqué par {bad!r})'} ; portes ouvertes à ce moment : {list(open_now) or 'aucune'}")
        full += seg[1:]
    if len(full) > 2: full = round_corners(full, .3)
    D = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(full[:-1], full[1:]))
    if D < 1e-3: raise PlanError(f"{A.id} t={t0}: déplacement de longueur nulle vers {dst}")
    v = D / max(.2, by - t0 - .45)
    for _ in range(4):
        P = Path(full, t0, v, run=1. if v > 2.0 else 0.); T = P.t1 - t0
        if abs(T - (by - t0)) < .01: break
        v = max(.05, v * T / (by - t0))
    P = Path(full, t0, v, run=1. if v > 2.0 else 0.); P.D_total = D
    if v > A.vmax + 1e-6: raise PlanError(f"{A.id} : {D:.1f} m en {by - t0:.1f}s exige {v:.1f} m/s, plus que sa vitesse maximale {A.vmax:.1f} m/s (t={t0:.1f}s → {by:.1f}s, de {frm} à {dst})")
    return P


def _disc_seg(pts, rect, r):
    for p, q in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.hypot(q[0] - p[0], q[1] - p[1]) / .05))
        for k in range(n + 1):
            x = p[0] + (q[0] - p[0]) * k / n; z = p[1] + (q[1] - p[1]) * k / n
            cx = min(max(x, rect[0]), rect[2]); cz = min(max(z, rect[1]), rect[3])
            if (x - cx) ** 2 + (z - cz) ** 2 < (r + .05) ** 2: yield True; return


def _contact(geo, A, b, actors):
    t0 = float(b['t']); do = b['do']; hand = b.get('hand', 'R'); out = dict(contacts=[], events=[]); P = _point3(geo, b['target']) if do != 'aim' else None
    hold = float(b.get('dur', .6)); up = float(b.get('up', .35)); down = float(b.get('down', .3))
    pose = b.get('pose', 'fist' if do == 'knock' else 'open' if do == 'touch' else 'grip')
    if do == 'knock':
        hits = [float(h) for h in b['hits']]; n = tuple(b.get('normal', (0., 0., 1.))); back = float(b.get('back', .16)); keys = []
        for i, h in enumerate(hits):
            keys += [(h - .2, 1., tuple(P[k] + n[k] * back for k in range(3))), (h, 1., P), (h + .09, 1., tuple(P[k] + n[k] * back for k in range(3)))]
        t_a, t_b = hits[0] - .2 - up, hits[-1] + .09 + down
        out['contacts'].append(dict(who=A.id, hand=hand, t0=t_a, t1=t_b, keys=_keys(t_a, t_b, keys, up, down), pose=pose, kind='knock', point=P, hits=hits))
        for h in hits: out['events'].append(dict(t=h, who=A.id, kind='knock', target=b['target'], point=P))
    elif do == 'touch':
        t_a, t_b = t0 - up, t0 + hold + down
        out['contacts'].append(dict(who=A.id, hand=hand, t0=t_a, t1=t_b, keys=_keys(t_a, t_b, [(t0, 1., P), (t0 + hold, 1., P)], up, down), pose=pose, kind='touch', point=P, hits=[t0]))
        out['events'].append(dict(t=t0, who=A.id, kind='touch', target=b['target'], point=P, until=t0 + hold))
    elif do == 'take':
        item = b.get('item', b['target']); t_a, t_b = t0 - up, t0 + .25 + down
        out['contacts'].append(dict(who=A.id, hand=hand, t0=t_a, t1=t_b, keys=_keys(t_a, t_b, [(t0, 1., P), (t0 + .25, 1., P)], up, down), pose=pose, kind='take', point=P, hits=[t0]))
        out['events'].append(dict(t=t0, who=A.id, kind='take', item=item, point=P, hand=hand))
        A.helds.append((t0, float(b['until']) if b.get('until') else 1e9, item, hand))
    elif do == 'aim':
        # the arm raised towards a target while the actor faces it; the point is computed from the facing at that time, once positions are known: store the request
        out['events'].append(dict(t=t0, who=A.id, kind='aim', at=b['at'], until=float(b['until']), hand=hand, pose=pose, reach=float(b.get('reach', .5)), h=float(b.get('h', 1.3))))
    return out


def _keys(t_a, t_b, mid, up, down):
    ks = [(t_a, 0., mid[0][2])] + [(t, w, p) for (t, w, p) in mid] + [(t_b, 0., mid[-1][2])]
    return ks


def _integrate(C, duration):
    geo = C.geo; n = int(math.ceil(duration / DT)) + 3
    for aid, A in C.actors.items():
        a = {k: np.zeros(n) for k in ('x', 'z', 'yaw', 'hyaw', 'hpit', 'run', 'lean', 'tension', 'crouch')}
        for i in range(n):
            x, z = A.pos(i * DT); a['x'][i] = x; a['z'][i] = z
        # run flag
        for i in range(n):
            m = A.moving(i * DT); a['run'][i] = m['run'] if m else 0.
        C.arr[aid] = a
    # the aim requests need positions: turn each into a contact whose point follows the target
    for e in [e for e in C.events if e['kind'] == 'aim']:
        A = C.actors[e['who']]; t0, t1 = e['t'], e['until']; ks = []; ts = np.arange(t0, t1 + 1e-9, .1)
        for t in ts:
            x, z = C.xz(e['who'], t)
            tx, tz = _target_xz(C, e['at'], t); d = math.hypot(tx - x, tz - z) or 1.; ux, uz = (tx - x) / d, (tz - z) / d
            th = math.atan2(ux, uz); side = -1. if e['hand'] == 'R' else 1.; sc = A.scale * SHOULDER_X
            sx, sz = x + side * sc * math.cos(th), z - side * sc * math.sin(th)                      # the aiming shoulder, the body facing the target
            ks.append((float(t), 1., (sx + ux * e['reach'], e['h'], sz + uz * e['reach'])))
        t_a, t_b = t0 - .45, t1 + .35
        C.contacts.append(dict(who=e['who'], hand=e['hand'], t0=t_a, t1=t_b, keys=_keys(t_a, t_b, ks, .45, .35), pose=e['pose'], kind='aim', point=None, hits=[]))
    from . import combat; combat.resolve(C)                                  # blows, clashes, guards, flinches, kneeling: contacts and torso tracks (combat.py)
    # facing and head integration
    for aid, A in C.actors.items():
        a = C.arr[aid]; yaw = A.yaw0; hy = 0.; hp = 0.; look_i = 0; face_i = 0; head_t = None
        for i in range(n):
            t = i * DT; x, z = a['x'][i], a['z'][i]
            while face_i + 1 < len(A.faces) and A.faces[face_i + 1][0] <= t: face_i += 1
            tgt_yaw = _face_yaw(C, A, A.faces[face_i][1], t, x, z, yaw)
            m = A.moving(t)
            if m is not None and m['fin'] is None or (m is not None and t < m['t1'] - .35):
                d = m['path'].dist(t); tgt_yaw = m['path'].tangent(d) + (math.pi if m['back'] else 0.)
            # a body turns at most ~4.2 rad/s, with an ease at the ends
            err = _wrap(tgt_yaw - yaw); step = max(-4.2 * DT, min(4.2 * DT, err * min(1., 9. * DT))); yaw = _wrap(yaw + step)
            # head: own target, speed-limited, relative to the body; the body helps beyond +-.9 rad
            while look_i < len(A.looks) and A.looks[look_i][0] <= t: look_i += 1
            lk = A.looks[look_i - 1] if look_i else None
            if lk is None or lk[1][0] == 'clear': want_y, want_p, sp = 0., 0., 2.2
            else:
                tx, tz, ty = _look_target(C, lk[1], t); dx, dz = tx - x, tz - z; bear = math.atan2(dx, dz); want_y = _wrap(bear - yaw)
                want_p = math.atan2(ty - 1.78, max(.3, math.hypot(dx, dz))) * -1.; sp = lk[2]
                if t < lk[0] + lk[3]: want_y, want_p = hy, hp
            want_y = max(-1.0, min(1.0, want_y)); want_p = max(-.5, min(.5, want_p))
            dy = want_y - hy; hy += max(-sp * DT, min(sp * DT, dy)); dp = want_p - hp; hp += max(-sp * .6 * DT, min(sp * .6 * DT, dp))
            a['yaw'][i] = yaw; a['hyaw'][i] = hy; a['hpit'][i] = hp
        # a short lean into walks and the tension an actor carries (set by emote events with `tension`)
    for aid, A in C.actors.items():
        a = C.arr[aid]
        for e in C.events:
            if e['who'] == aid and e['kind'] == 'tension':
                i0 = int(e['t'] / DT); i1 = min(len(a['tension']), int(e['until'] / DT)); a['tension'][i0:i1] = e.get('value', .6)


def _target_xz(C, spec, t):
    if isinstance(spec, str) and spec in C.actors: return C.xz(spec, t)
    return _resolve(C.geo, spec)


def _look_target(C, f, t):
    kind, v = f[0], f[1]
    if kind == 'actor': x, z = C.xz(v, t); return x, z, 1.7
    if kind == 'point': return v[0], v[1], (v[2] if len(v) > 2 else 1.5)
    if kind == 'yaw': return None
    if kind == 'mark': x, z, _ = C.geo.marks[v]; return x, z, 1.5
    return 0., 0., 1.5


def _face_yaw(C, A, f, t, x, z, cur):
    kind, v = f
    if kind == 'yaw': return v
    if kind == 'actor':
        ox, oz = C.xz(v, t); dx, dz = ox - x, oz - z
        return math.atan2(dx, dz) if math.hypot(dx, dz) > .05 else cur
    if kind == 'point': return math.atan2(v[0] - x, v[1] - z)
    if kind == 'mark': mx, mz, _ = C.geo.marks[v]; return math.atan2(mx - x, mz - z)
    return cur


# ----------------------------------------------------------------------------------------------------------------------- audit
BODY_H = 2.13                    # A's body from sole to top of head at scale 1 (chars4.js: hips 14 px + torso 12 + head 8, of 16 px per metre)
HEAD_TOL = .05                   # a lintel less than 5 cm under the top of the head is not called a collision (the shipped service door is 2.2 m for a 2.23 m creature)
OVERLAP = .85                    # two bodies closer than this share of the sum of their radii overlap


def audit_actors(C, fps=30, window=.25):
    """what a body does, sampled at the film's frame rate: inside a solid, through a wall, too fast, a jump, a wrong passage, the head in a lintel, a step too high,
    two bodies in the same place. A DECLARED supernatural vanish / appear (beats `vanish` / `appear`) is the only thing excused from the jump test: while an actor is
    hidden nothing is tested, and the instant he is seen again he is tested as an ordinary body (inside a wall, or crossing one, is still a violation)."""
    geo = C.geo; v = []; step = 1. / fps; T = C.plan['duration']
    for aid, A in C.actors.items():
        prev = None; zprev = None; t = 0.; hist = []; flagged = set(); gprev = None; H = BODY_H * A.scale
        while t <= T + 1e-9:
            if not A.visible_at(t): prev = None; zprev = None; hist = []; gprev = None; t += step; continue
            x, z = C.xz(aid, t); g = geo.ground_y(x, z) if geo.floors else 0.
            h = geo.hit_body(x, z, A.r - .03, t, y=g, h=H) if g is not None else geo.hit_body(x, z, A.r - .03, t)
            if h and ('in', h) not in flagged: flagged.add(('in', h)); v.append(Violation('solide', f"{aid} est dans {h!r} en ({x:.2f}, {z:.2f})", t, aid, solid=h))
            if g is None and ('void', 0) not in flagged: flagged.add(('void', 0)); v.append(Violation('vide', f"{aid} marche au-dessus du vide en ({x:.2f}, {z:.2f})", t, aid))
            if gprev is not None and g is not None and abs(g - gprev) > .35 and ('step', int(t)) not in flagged:
                flagged.add(('step', int(t))); v.append(Violation('marche_haute', f"{aid} monte ou descend de {abs(g - gprev) * 100:.0f} cm d'une image à l'autre (une marche de plus de 35 cm se saute ou s'escalade)", t, aid, dy=g - gprev))
            for s in geo.solids:                                                        # a head into something that hangs at head height (a beam, a lintel that is not a wall)
                if not s.body and s.kind != 'ceiling' and 1.2 < s.y0 < H - HEAD_TOL and s.contains(x, z, A.r * .5) and ('head', s.id) not in flagged:
                    flagged.add(('head', s.id)); v.append(Violation('tête', f"{aid} se cogne la tête dans {s.id!r} (sous-face à {s.y0:.2f} m, taille {H:.2f} m)", t, aid, solid=s.id))
            if prev is not None:
                d = math.hypot(x - prev[0], z - prev[1])
                if d > A.vmax * step * 1.15 + .02: v.append(Violation('téléportation', f"{aid} saute de {d:.2f} m en {step * 1000:.0f} ms ({d / step:.1f} m/s)", t, aid, d=d))
                bad = geo.seg_free(prev, (x, z), A.r - .03, t, step=.05)
                if bad and ('wall', bad) not in flagged: flagged.add(('wall', bad)); v.append(Violation('mur', f"{aid} traverse {bad!r} entre ({prev[0]:.2f}, {prev[1]:.2f}) et ({x:.2f}, {z:.2f})", t, aid, solid=bad))
            hist.append((t, x, z))
            if len(hist) > int(window * fps) + 1:
                t_old, xo, zo = hist.pop(0); sp = math.hypot(x - xo, z - zo) / (t - t_old)
                if sp > A.vmax * 1.05 and ('speed', int(t)) not in flagged: flagged.add(('speed', int(t))); v.append(Violation('vitesse', f"{aid} va à {sp:.1f} m/s (maximum {A.vmax:.1f})", t, aid, v=sp))
            zn = geo.zone_at(x, z)
            if zprev is not None and zn != zprev and zn is not None:
                if not _zones_connected(geo, zprev, zn, t): v.append(Violation('passage', f"{aid} passe de « {zprev} » à « {zn} » sans porte ouverte", t, aid, a=zprev, b=zn))
            if zn is not None: zprev = zn
            prev = (x, z); gprev = g; t += step
    for e in C.events:                                                                  # an `appear` that was never preceded by a `vanish` is a teleport, declared or not
        if e['kind'] == 'appear':
            A = C.actors[e['who']]; before = A.pos(e['t'] - 1e-3); after = tuple(e['to']) if e.get('to') else before
            if A.visible_at(e['t'] - 1e-3) and math.hypot(after[0] - before[0], after[1] - before[1]) > .3:
                v.append(Violation('téléportation', f"{e['who']} apparaît ailleurs sans avoir disparu avant (apparition non précédée d'une disparition déclarée)", e['t'], e['who']))
    v += audit_overlap(C, fps)
    return v


def audit_overlap(C, fps=30):
    """two visible bodies in the same place (their discs overlap by more than 15 %), except in the windows the plan declares with `contact_ok` ({a, b, t0, t1}: a hug,
    a grab, somebody carried). One violation per pair, with the first instant, how long it lasts and how close they got."""
    v = []; ids = list(C.actors); T = C.plan['duration']; step = 1. / fps; ok = C.plan.get('contact_ok') or []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            if a.split('#')[0] == b.split('#')[0]: continue            # two lives of one actor (genre_intent.split_plan) are never on stage together: the painter draws one at a time
            A, B = C.actors[a], C.actors[b]; lim = (A.r + B.r) * OVERLAP; first = None; n = 0; dmin = 9.; t = 0.
            win = [w for w in ok if {w['a'], w['b']} == {a, b}]
            while t <= T + 1e-9:
                if A.visible_at(t) and B.visible_at(t) and not any(w['t0'] - 1e-6 <= t <= w['t1'] + 1e-6 for w in win):
                    xa, za = C.xz(a, t); xb, zb = C.xz(b, t); d = math.hypot(xa - xb, za - zb)
                    if d < lim:
                        n += 1; dmin = min(dmin, d)
                        if first is None: first = t
                t += step
            if first is not None: v.append(Violation('chevauchement', f"{a} et {b} se traversent : {n / fps:.1f} s à moins de {lim:.2f} m l'un de l'autre (au plus près {dmin:.2f} m)", first, a, other=b, dmin=dmin, dur=n / fps))
    return v


def _zones_connected(geo, a, b, t):
    if hasattr(geo, 'zones_ok'): return geo.zones_ok(a, b, t)             # a place that knows its own doors (placesgeo.demo_world)
    ina, inb = geo.zones[a]['indoor'], geo.zones[b]['indoor']
    if not ina and not inb: return True
    for p in geo.portals.values():
        if {p.a, p.b} == {a, b} and p.open_at(t): return True
        if {p.a, p.b} <= {a, b, 'parking', 'arriere', 'sous_porche'} and (a in (p.a, p.b) or b in (p.a, p.b)) and p.open_at(t) and (a in (p.a, p.b) and b in (p.a, p.b)): return True
    if {a, b} == {'sous_porche', 'parking'}: return True
    if {a, b} == {'sous_porche', 'pompes'}: return True
    return False


def arm_ok(A, stand, yaw, P, hand):
    """horizontal and vertical reach of A's arm to a 3D point from where the actor stands"""
    side = -1. if hand == 'R' else 1.                                         # A's right shoulder is at -x of the body frame (anim.reach: sg = -1 for R)
    sx = stand[0] + math.cos(yaw) * (side * SHOULDER_X) * A.scale; sz = stand[1] - math.sin(yaw) * (side * SHOULDER_X) * A.scale
    d = math.sqrt((P[0] - sx) ** 2 + (P[1] - SHOULDER_Y * A.scale) ** 2 + (P[2] - sz) ** 2)
    return d, ARM * A.scale


END_MARGIN = .06                                      # the last 6 cm of a hand's approach are ON the surface it touches, not through it


def shoulder_of(A, stand, yaw, hand, ground=0.):
    """the 3D position of A's shoulder for a hand ('R' | 'L') when the actor stands at `stand` facing `yaw`"""
    side = -1. if hand == 'R' else 1.
    return (stand[0] + math.cos(yaw) * (side * SHOULDER_X) * A.scale, ground + SHOULDER_Y * A.scale, stand[1] - math.sin(yaw) * (side * SHOULDER_X) * A.scale)


def audit_contacts(C, tol=.06):
    """a hand only touches what it reaches: the target must be within the arm's length of the shoulder, the body must face it, and be on the right side of the glass"""
    v = []; geo = C.geo
    for c in C.contacts:
        A = C.actors[c['who']]
        for (t, w, P) in c['keys']:
            if w < .99: continue
            row = C._row(A, t); d, L = arm_ok(A, (row['x'], row['z']), row['heading'], P, c['hand'])
            if d > L + tol: v.append(Violation('portée', f"action « {c['kind']} » à distance : la main de {A.id} est à {d:.2f} m de la cible, son bras fait {L:.2f} m", t, A.id, d=d, L=L, kind=c['kind'])); break
            bear = math.atan2(P[0] - row['x'], P[2] - row['z'])
            if abs(_wrap(bear - row['heading'])) > math.radians(75): v.append(Violation('orientation', f"{A.id} touche une cible qu'il n'a pas en face ({math.degrees(abs(_wrap(bear - row['heading']))):.0f}° d'écart)", t, A.id)); break
            sh = shoulder_of(A, (row['x'], row['z']), row['heading'], c['hand'], row['y'])
            hit = geo.seg_hits_body3(sh, P, t=t, end_margin=END_MARGIN)
            if hit: v.append(Violation('main_traverse', f"la main de {A.id} (« {c['kind']} ») passe à travers {hit!r} pour atteindre sa cible", t, A.id, solid=hit, kind=c['kind'])); break
            if not (row['y'] - .05 <= P[1] <= row['y'] + SHOULDER_Y * A.scale + ARM * A.scale + .05): v.append(Violation('portée', f"« {c['kind']} » à {P[1]:.2f} m de haut : hors de portée verticale de {A.id} (épaule à {row['y'] + SHOULDER_Y * A.scale:.2f} m)", t, A.id)); break
    for e in C.events:
        if e['kind'] == 'take':
            cs = [c for c in C.contacts if c['who'] == e['who'] and c['kind'] == 'take' and abs(c['hits'][0] - e['t']) < 1e-6]
            if not cs: v.append(Violation('cause', f"{e['who']} prend {e['item']!r} sans geste de la main", e['t'], e['who']))
    return v


def audit(C, fps=30):
    from . import combat
    return audit_actors(C, fps) + audit_contacts(C) + combat.audit_fight(C)


# ----------------------------------------------------------------------------------------------------------------------- film-level exports
def held_extras(C, aid, boxes, hand='R'):
    """the `extras` of a cast entry that attach an object to the hand while the story says the actor holds it"""
    out = []
    for (t0, t1, item, h) in C.actors[aid].helds:
        out.append({'bone': 'hand' + h, 'at': [0, -1.2, 1.5], 't0': t0, 't1': t1, 'boxes': boxes[item]})
    return out


def contacts_for_painter(C, t0, t1):
    """contacts that overlap [t0, t1] as the painter reads them: {who, hand, pose, keys: [[T, x, y, z, w], ...]} in world-local coordinates and ABSOLUTE film time"""
    out = []
    for c in C.contacts:
        if c['t1'] < t0 or c['t0'] > t1: continue
        out.append(dict(who=c['who'], hand=c['hand'], pose=c['pose'], keys=[[round(t, 4), round(p[0], 4), round(p[1], 4), round(p[2], 4), round(w, 3)] for (t, w, p) in c['keys']]))
    return out


# ----------------------------------------------------------------------------------------------------------------------- the director's entry points
class BlockedActing:
    """stand-in for acting.timeline.ShotActing / tracks.TrackActing for a shot of a blocked film: it does not place anybody, it LOOKS at the film's single trajectory"""

    def __init__(self, C, t0, dur):
        self.C = C; self.t0 = float(t0); self.dur = float(dur); self.lines = []; self.tracks = {a: None for a in C.actors}; self.world = None

    def end_states(self): return {}
    def sample(self, t): return self.C.sample(self.t0 + t)
    def position(self, tr, t): return (0., 0.)


def geo_of(ep):
    from . import stagegeo
    b = ep['blocking']; name = b.get('world', 'station')
    if name not in stagegeo.GEOS: raise PlanError(f"blocking : le lieu {name!r} n'a pas encore de géométrie (disponible : {', '.join(stagegeo.GEOS)})")
    return stagegeo.station(b.get('doors')) if name == 'station' else stagegeo.GEOS[name](b.get('doors')) if name == 'demo' else stagegeo.GEOS[name]()


def compile_episode(ep):
    """-> (Compiled, Geo) for an episode that carries a `blocking` block"""
    geo = geo_of(ep); plan = dict(ep['blocking']['plan']); plan.setdefault('duration', ep.get('duration'))
    return compile_plan(plan, geo), geo


def preflight(ep, C, geo, shots_abs, aspect='9:16', strict=True):
    """the whole deterministic check, before a single image: bodies, hands, doors, cameras, framing. Returns (violations, report dict)"""
    from . import camplan
    v = audit(C); cv, rows, stats = camplan.audit_film(shots_abs, C, geo, aspect, tight_max=float(ep['blocking'].get('tight_max', .22)), insert_max=int(ep['blocking'].get('insert_max', 8)))
    v += cv
    # the world is one: a door or a light is in the same state in every shot, so the keys that describe the world must be the same table everywhere
    for key in ep['blocking'].get('world_keys', []):
        seen = {json_key(s.get('env', {}).get(key)) for s in ep['shots'] if key in (s.get('env') or {})}
        if len(seen) > 1: v.append(Violation('monde_incohérent', f"la clé de monde « {key} » n'a pas la même valeur dans tous les plans ({len(seen)} variantes)"))
        if not seen and key in ep.get('world_env', {}): pass
    rep = dict(violations=[x.to_json() for x in v], shots=rows, **stats)
    return v, rep


def json_key(v):
    import json
    return json.dumps(v, sort_keys=True, default=str)


def audit_contract(c, geo, vmax=None, declared=None, contact_ok=None):
    """The same questions asked of a FINISHED contract (any film, hand-written or generated, blocked or not): is a body inside a solid, does it jump between two
    frames or at a cut, does it go from inside to outside without a door, does it stand on the ground (the row's `y` against the geometry's ground), are two bodies
    in the same place, are the coordinates in the world's own frame? This is how the first remakes are shown to have been wrong, and how a future film is
    checked even if it never went through compile_plan. `vmax` = {actor: m/s} (default 5). `declared` = [{who, t0, t1}] the supernatural vanish / appear windows the
    story declared (default: the contract's own `declared_warps`): the only jumps that are excused. A stage may carry a `frame` ({dx, dz, yaw}) when its rows are not
    in the geometry's own coordinates; `contact_ok` = [{a, b, t0, t1}] windows where two bodies may touch."""
    from .stagegeo import Frame
    v = []; fps = c['fps']; per = {}; declared = declared if declared is not None else (c.get('declared_warps') or []); contact_ok = contact_ok or c.get('contact_ok') or []
    for st in c['stages']:
        if st.get('world') != geo.name: continue
        fr = Frame.of(st.get('frame'))
        for aid, rows in st['actors'].items():
            n = int(round((st['t1'] - st['t0']) * fps)); per.setdefault(aid, []).append((st['id'], st['t0'], rows[:max(1, n)], fr))
    ix = {n: i for i, n in enumerate(c['actor_cols'])}; bx0, bz0, bx1, bz1 = geo.bounds; M = 40.; seen = {}
    in_warp = lambda aid, t: any(w['who'] == aid and w['t0'] - 1.5 / fps <= t <= w['t1'] + 1.5 / fps for w in declared)
    for aid, segs in per.items():
        cast = c['casts'].get(aid) or {}; kind = 'faceless' if cast.get('kind') == 'faceless' else 'human'; vm = (vmax or {}).get(aid, 5.); r = KINDS[kind]['r']
        H = BODY_H * float(cast.get('scale') or KINDS[kind]['scale']); prev = None; flagged = set(); zprev = None; wrong_frame = False
        for sid, t0, rows, fr in segs:
            for i, row in enumerate(rows):
                if not row[ix['vis']]: continue
                t = t0 + i / fps; x, z = fr.to_local(row[ix['x']], row[ix['z']]); y = row[ix['y']]
                if not (bx0 - M <= x <= bx1 + M and bz0 - M <= z <= bz1 + M):
                    if (sid, 'frame') not in flagged: flagged.add((sid, 'frame')); v.append(Violation('repère', f"{aid} est en ({x:.1f}, {z:.1f}) dans le plan {sid} : hors du lieu {geo.name!r} de plus de {M:.0f} m. Les lignes d'acteur doivent être dans le repère LOCAL du monde (le peintre ajoute l'origine du monde lui-même)", t, aid))
                    continue
                g = geo.ground_y(x, z) if geo.floors else geo.base_y
                h = geo.hit_body(x, z, r - .03, t, y=g if g is not None else None, h=H)
                if h and (sid, h) not in flagged: flagged.add((sid, h)); v.append(Violation('solide', f"{aid} est dans {h!r} en ({x:.2f}, {z:.2f}) dans le plan {sid}", t, aid, solid=h))
                if g is None and (sid, 'void') not in flagged and not row[ix['air']] > .05: flagged.add((sid, 'void')); v.append(Violation('vide', f"{aid} se tient au-dessus du vide en ({x:.2f}, {z:.2f}) dans le plan {sid}", t, aid))
                elif g is not None and row[ix['air']] <= .05 and abs(y - g) > .06 and (sid, 'ground') not in flagged:
                    flagged.add((sid, 'ground')); v.append(Violation('sol', f"{aid} est {'enfoncé de ' + format(g - y, '.2f') if y < g else 'en l' + chr(39) + 'air à ' + format(y - g, '.2f')} m par rapport au sol ({g:.2f} m) en ({x:.1f}, {z:.1f}) dans le plan {sid}", t, aid, dy=y - g))
                if prev is not None:
                    d = math.hypot(x - prev[1], z - prev[2]); dt = max(1e-3, t - prev[0])
                    if d > vm * dt + .35 and (sid, 'tp') not in flagged and not in_warp(aid, t) and not in_warp(aid, prev[0]):
                        flagged.add((sid, 'tp')); v.append(Violation('téléportation', f"{aid} saute de {d:.1f} m en {dt * 1000:.0f} ms au début du plan {sid} ({prev[3]} → {sid})", t, aid, d=d))
                    elif d > .05 and not in_warp(aid, t) and ('wall', sid) not in flagged:
                        bad = geo.seg_free(prev[1:3], (x, z), r - .03, t, step=.05)
                        if bad: flagged.add(('wall', sid)); v.append(Violation('mur', f"{aid} traverse {bad!r} dans le plan {sid}", t, aid, solid=bad))
                zn = geo.zone_at(x, z)
                if zprev is not None and zn != zprev and zn and geo.zones[zn]['indoor'] != geo.zones[zprev]['indoor'] and not _zones_connected(geo, zprev, zn, t) and ('z', sid) not in flagged and not in_warp(aid, t):
                    flagged.add(('z', sid)); v.append(Violation('passage', f"{aid} passe de « {zprev} » à « {zn} » sans porte ouverte (plan {sid})", t, aid))
                if zn: zprev = zn
                prev = (t, x, z, sid)
    # two bodies in the same place: frame by frame, within each stage
    for st in c['stages']:
        if st.get('world') != geo.name: continue
        fr = Frame.of(st.get('frame')); n = int(round((st['t1'] - st['t0']) * fps)); ids = list(st['actors'])
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                A_, B_ = ids[a], ids[b]; ca, cb = c['casts'].get(A_) or {}, c['casts'].get(B_) or {}
                ra = KINDS['faceless' if ca.get('kind') == 'faceless' else 'human']['r']; rb = KINDS['faceless' if cb.get('kind') == 'faceless' else 'human']['r']; lim = (ra + rb) * OVERLAP
                ra_, rb_ = st['actors'][A_], st['actors'][B_]; cnt = 0; first = None; dmin = 9.
                for i in range(min(n, len(ra_), len(rb_))):
                    if not (ra_[i][ix['vis']] and rb_[i][ix['vis']]): continue
                    t = st['t0'] + i / fps
                    if any({w['a'], w['b']} == {A_, B_} and w['t0'] <= t <= w['t1'] for w in contact_ok): continue
                    d = math.hypot(ra_[i][ix['x']] - rb_[i][ix['x']], ra_[i][ix['z']] - rb_[i][ix['z']])
                    if d < lim:
                        cnt += 1; dmin = min(dmin, d); first = t if first is None else first
                if cnt >= 3: v.append(Violation('chevauchement', f"{A_} et {B_} se traversent dans le plan {st['id']} : {cnt / fps:.1f} s à moins de {lim:.2f} m (au plus près {dmin:.2f} m)", first, A_, other=B_, dmin=dmin))
    return v
