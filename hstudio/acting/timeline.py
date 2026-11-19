"""Action timeline ("la régie"): turns the actions of a shot into continuous tracks for every character.

Shared by both engines. A shot may contain
  "actors":  [{"id": "lea", "at": "porte", "facing": "+z", "face": "calm", "hold": "cup", "posture": "sit", "on": "canape"}]
  "actions": [{"who": "lea", "do": "walk_to", "to": "table"}, {"who": "lea", "do": "pick", "item": "key"}, ...]
Actions of one character run one after the other ("at": seconds into the shot to force a start time, or
"with": index of an action to start together). Characters keep their state from the previous shot of the same set
(position, orientation, posture, held object) unless the shot says otherwise: continuity is automatic.

Verbs: walk_to / run_to / sneak_to (to, speed, stop_dist, face), turn_to (target), look_at (target, dur), look_around,
gesture (name, dur), face (name), pick (item, from), put (item, on), give (to), sit (on), stand, open / close (door),
react (startle | gasp | flinch | laugh | nod | shake_head | sigh | cheer | shiver), follow (target, dist), wait (dur),
enter (from: an anchor off screen -> walks to "to"), exit (to).

The engine supplies a World: anchor(name) -> (x, z), obstacles() -> [(x0, z0, x1, z1)], bounds() -> (x0, z0, x1, z1),
seat(name) -> (x, z, yaw, height) | None, door(name) -> dict | None, item(name) -> (x, y, z) | None."""
import math, heapq, numpy as np
from . import rig

SPEEDS = {'walk': 1.15, 'slow': .7, 'run': 3.1, 'sneak': .55, 'stroll': .85, 'hurry': 1.7}
REACTS = {'startle': 1.0, 'gasp': 1.1, 'flinch': .6, 'laugh': 1.6, 'nod': .9, 'shake_head': 1.0, 'sigh': 1.4, 'cheer': 1.4, 'shiver': 1.4}
TALK_GESTURES = ('extend', 'shrug', 'hand_chest', 'point', 'think')
SAD = {'sad', 'crying', 'tired', 'bored', 'smile_sad'}; TENSE = {'scared', 'nervous', 'shocked', 'urgent'}; UP = {'proud', 'joy', 'excited', 'happy', 'cool'}

def smooth(x): x = min(1., max(0., x)); return x * x * (3 - 2 * x)
def wrap(a): return (a + math.pi) % (2 * math.pi) - math.pi
def heading_of(dx, dz): return math.atan2(dx, dz)
def h32(*v):
    h = 2166136261
    for x in v:
        for c in str(x): h = ((h ^ ord(c)) * 16777619) & 0xffffffff
    return h / 4294967295.

FACING = {'+z': 0., '-z': math.pi, '+x': math.pi / 2, '-x': -math.pi / 2}
TAKEOVER = .3                 # s a body takes to swing from where it was looking into the direction it walks off in
OFF_WORDS = ('snap', 'frozen', 'legacy', 'off', 'none', '')      # any of these, on "eyeline" or "footing", means historical
LIM_YAW = .95                 # rad the neck turns away from the torso; LIM_PITCH, the same up and down
LIM_PITCH = .45


def neck(gz, aid, t, h, yaw, pitch):
    """(delivered yaw, delivered pitch, residual, clamped) -- THE one definition of what the neck delivers and
    of what it leaves to the eyes. `gz` is the gaze controller of the shot, or None.

    The residual is the part of the aim the neck could not deliver: the clamp below, plus the slew lag of
    acting/gaze.py when the episode asked for one. ShotActing.sample() and ShotActing.raw_eye() both go
    through here, so acting/eyeflow.py can never smooth a residual the renderer does not have."""
    want = (yaw, pitch)
    if gz is not None: yaw, pitch = gz.head(aid, t, h, yaw, pitch)
    clamped = abs(yaw) > LIM_YAW
    yaw = max(-LIM_YAW, min(LIM_YAW, yaw)); pitch = max(-LIM_PITCH, min(LIM_PITCH, pitch))
    return yaw, pitch, (want[0] - yaw, want[1] - pitch), clamped

# ------------------------------------------------------------------ path planning (grid A*, string pulling)
class Grid:
    def __init__(self, world, radius=.26, cell=.2):
        b = world.bounds(); self.x0, self.z0, x1, z1 = b; self.c = cell
        self.nx = max(2, int(math.ceil((x1 - self.x0) / cell)) + 1); self.nz = max(2, int(math.ceil((z1 - self.z0) / cell)) + 1)
        self.block = np.zeros((self.nx, self.nz), bool)
        xs = self.x0 + np.arange(self.nx) * cell; zs = self.z0 + np.arange(self.nz) * cell
        for (a0, c0, a1, c1) in world.obstacles():
            ix = (xs >= a0 - radius) & (xs <= a1 + radius); iz = (zs >= c0 - radius) & (zs <= c1 + radius)
            self.block[np.ix_(ix, iz)] = True
        self.hgt = None
        if getattr(world, 'has_levels', False):           # levels (V3): nobody walks into a void, a step over 35 cm is a wall
            H = np.full((self.nx, self.nz), np.nan, np.float32)
            for i, x in enumerate(xs):
                for j, z in enumerate(zs):
                    h = world.ground_y(float(x), float(z))
                    if h is not None: H[i, j] = h
            void = np.isnan(H); edge = void.copy()          # the feet keep a cell away from the edge
            edge[1:] |= void[:-1]; edge[:-1] |= void[1:]; edge[:, 1:] |= void[:, :-1]; edge[:, :-1] |= void[:, 1:]
            self.block |= edge; self.hgt = np.nan_to_num(H, nan=-1e3)
    def cell(self, x, z): return (min(self.nx - 1, max(0, int(round((x - self.x0) / self.c)))), min(self.nz - 1, max(0, int(round((z - self.z0) / self.c)))))
    def pos(self, i, j): return (self.x0 + i * self.c, self.z0 + j * self.c)
    def free(self, i, j): return 0 <= i < self.nx and 0 <= j < self.nz and not self.block[i, j]
    def step_ok(self, a, b): return self.hgt is None or abs(float(self.hgt[a]) - float(self.hgt[b])) <= .35
    def line_free(self, a, b):
        n = int(math.hypot(b[0] - a[0], b[1] - a[1]) / (self.c * .5)) + 1; prev = None
        for k in range(n + 1):
            x = a[0] + (b[0] - a[0]) * k / n; z = a[1] + (b[1] - a[1]) * k / n
            cl = self.cell(x, z)
            if not self.free(*cl): return False
            if prev is not None and not self.step_ok(prev, cl): return False
            prev = cl
        return True
    def nearest_free(self, x, z):
        i, j = self.cell(x, z)
        if self.free(i, j): return (x, z)
        for r in range(1, 12):
            best = None
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    if max(abs(di), abs(dj)) == r and self.free(i + di, j + dj):
                        p = self.pos(i + di, j + dj); d = math.hypot(p[0] - x, p[1] - z)
                        if best is None or d < best[0]: best = (d, p)
            if best: return best[1]
        return (x, z)
    def path(self, a, b):
        if self.line_free(a, b): return [a, b]
        s, g = self.cell(*a), self.cell(*b)
        if not self.free(*s): s = self.cell(*self.nearest_free(*a))
        if not self.free(*g): g = self.cell(*self.nearest_free(*b))
        openq = [(0., s)]; came = {s: None}; cost = {s: 0.}
        while openq:
            _, cur = heapq.heappop(openq)
            if cur == g: break
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nb = (cur[0] + di, cur[1] + dj)
                if not self.free(*nb) or not self.step_ok(cur, nb): continue
                if di and dj and not (self.free(cur[0] + di, cur[1]) and self.free(cur[0], cur[1] + dj)): continue
                nc = cost[cur] + math.hypot(di, dj)
                if nb not in cost or nc < cost[nb]:
                    cost[nb] = nc; came[nb] = cur; heapq.heappush(openq, (nc + math.hypot(nb[0] - g[0], nb[1] - g[1]), nb))
        if g not in came:
            if self.hgt is None: return [a, b]
            g = min(came, key=lambda c: math.hypot(c[0] - g[0], c[1] - g[1])); b = self.pos(*g)   # V3: stop at the edge, never walk on the void
        cells = []; c_ = g
        while c_ is not None: cells.append(c_); c_ = came[c_]
        pts = [a] + [self.pos(*c_) for c_ in reversed(cells[1:-1])] + [b]
        out = [pts[0]]; i = 0                                  # string pulling
        while i < len(pts) - 1:
            j = len(pts) - 1
            while j > i + 1 and not self.line_free(pts[i], pts[j]): j -= 1
            out.append(pts[j]); i = j
        return out

def round_corners(pts, r=.35):
    """replace sharp corners by short arcs (sampled) so heading changes are smooth"""
    if len(pts) < 3: return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = (np.array(pts[i - 1]), np.array(pts[i]), np.array(pts[i + 1]))
        a = p0 - p1; b = p2 - p1; la, lb = np.linalg.norm(a), np.linalg.norm(b)
        rr = min(r, la * .45, lb * .45)
        q0 = p1 + a / la * rr; q2 = p1 + b / lb * rr
        for k in range(6):
            u = k / 5; q = (1 - u) ** 2 * q0 + 2 * (1 - u) * u * p1 + u * u * q2; out.append((float(q[0]), float(q[1])))
    out.append(pts[-1]); return out

class Path:
    """a polyline walked with a smooth trapezoid speed profile; phase tied to distance (planted feet).
    keep: no slowing down at the end (the run-up of a jump reaches the edge at full speed)"""
    def __init__(self, pts, t0, speed, run=0., crouch=0., phase0=None, keep=False, plant=False):
        self.pts = np.array(pts, np.float32); seg = np.linalg.norm(np.diff(self.pts, axis=0), axis=1)
        self.cum = np.concatenate([[0.], np.cumsum(seg)]); self.D = float(self.cum[-1]); self.v = speed; self.run = run; self.crouch = crouch
        ta = .45 if run < .5 else .35
        if self.D < self.v * ta: ta = self.D / self.v
        self.ta = max(ta, 1e-3); self.cruise = max(0., self.D / self.v - ta); self.t0 = t0; self.t1 = t0 + self.cruise + 2 * self.ta
        self.keep = keep
        if keep: self.t1 = t0 + self.ta + max(0., self.D - self.v * self.ta / 2) / self.v
        S = rig.stride_for(speed); beta = rig.stance_beta(run)
        if plant:                                                # a whole number of cycles: the walk ends on the pose
            m = max(1, round(self.D / S))                        # it started from (one foot flat, the other passing),
            self.S = self.D / m if self.D > .05 else S           # so the stop closes the feet instead of sliding them
        else:
            k = max(1, round(2 * self.D / S - beta))             # (historical: lands a quarter cycle off, legs split)
            self.S = self.D / max(.5, (k / 2 + beta / 2)) if self.D > .05 else S
        self.phase0 = math.pi * beta if phase0 is None else phase0
    def dist(self, t):
        t = t - self.t0
        if t <= 0: return 0.
        ta, v = self.ta, self.v
        if self.keep:
            if t < ta: x = t / ta; return min(self.D, v * ta * (x ** 3 - x ** 4 / 2))
            return min(self.D, v * ta / 2 + v * (t - ta))
        if t < ta: x = t / ta; return v * ta * (x ** 3 - x ** 4 / 2)
        if t < ta + self.cruise: return v * ta / 2 + v * (t - ta)
        t2 = t - ta - self.cruise
        if t2 >= ta: return self.D
        x = t2 / ta; return v * ta / 2 + v * self.cruise + v * ta * (x - (x ** 3 - x ** 4 / 2))
    def point(self, d):
        d = min(max(d, 0.), self.D); i = int(np.searchsorted(self.cum, d, side='right') - 1); i = min(i, len(self.pts) - 2)
        l = self.cum[i + 1] - self.cum[i]; u = (d - self.cum[i]) / l if l > 1e-6 else 0.
        p = self.pts[i] + (self.pts[i + 1] - self.pts[i]) * u
        return float(p[0]), float(p[1])
    def tangent(self, d, ahead=.35):
        a = self.point(d - .05); b = self.point(min(self.D, d + ahead))
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-4: a = self.point(self.D - .3); b = self.point(self.D)
        return heading_of(b[0] - a[0], b[1] - a[1])

# ------------------------------------------------------------------ one character during one shot
class Track:
    def __init__(self, aid, st):
        self.id = aid; self.x, self.z = st['x'], st['z']; self.heading = st['heading']
        self.paths = []; self.turns = []; self.gestures = []; self.faces = [(-1e9, st.get('face', 'neutral'))]
        self.looks = []; self.reaches = []; self.holds = [(-1e9, st.get('hold'))]; self.sits = []; self.events = []
        self.reacts = []; self.base_gesture = st.get('gesture'); self.sit0 = 1. if st.get('posture') == 'sit' else 0.
        self.seat = st.get('seat'); self.crouch0 = 1. if st.get('posture') == 'crouch' else 0.
        self.follow = None; self.cursor = 0.; self.talk = []; self.visible = st.get('visible'); self.gone = False
        self.seed = h32(aid) * 10; self.persona = st.get('persona', {}) or {}
        self.airs = []; self.squats = []; self.y0 = float(st.get('y', 0.))     # V3: airborne segments (jump, climb, fall), knee bends
        self.path_heading = bool(st.get('path_heading'))       # opt-in: the body faces where it walks (episode "footing")
        self._hsrc = None                                      # cache of heading_sources()
        self.ctrl = None            # opt-in directed locomotion (episode "approach", see acting/approach.py)

    # state at the end of what has been scheduled so far
    def pos_at(self, t):
        x, z = self.x, self.z
        for p in self.paths:
            if t >= p.t0: x, z = p.point(p.dist(t))
        return x, z
    def heading_sources(self):
        """what drives the heading, as (start time, kind, object): a path (0) or a turn (1).
        Historically paths were read first and turns second, so a turn scheduled before a walk (the quarter turn
        towards the first leg of the path) kept the heading for the rest of the shot: the character then walked
        sideways along every corner, feet skating. With "footing": "path" they are read in chronological order,
        so each one only holds the heading until the next one starts."""
        key = (len(self.paths), len(self.turns))             # scheduling only appends: the count is enough
        if self._hsrc is None or self._hsrc[0] != key:
            src = [(p.t0, 0, p) for p in self.paths] + [(x[0], 1, x) for x in self.turns]
            self._hsrc = (key, sorted(src, key=lambda e: e[:2]) if self.path_heading else src)
        return self._hsrc[1]

    def heading_at(self, t):
        # Deux options opt-in décrivent le même geste, et leur ordre ici EST la décision d'intégration :
        # "approach" (acting/approach.py) est la couche au-dessus de "footing" -- son propre `_reference()`
        # relit les sources dans l'ordre chronologique, exactement comme `heading_sources()`, puis les lisse à
        # taux limité. Les deux ne se battent donc pas, mais si les deux clés sont posées c'est "approach" qui
        # décide du cap. Ce n'est pas un accident de placement : `tools/check_approche.py` l'épingle.
        if self.ctrl is not None: return self.ctrl.heading(t)      # "approach": rate-limited, follows the path
        h = self.heading; prev = sw = None
        for (t0, kind, o) in self.heading_sources():
            if t < t0: continue
            if kind == 0:
                prev, sw = ((h, t0) if (self.path_heading and t0 > 0) else (None, None))   # ease into the walk
                d = o.dist(t)
                h = o.tangent(d) if (d < o.D - .02 or t < o.t1) else o.tangent(o.D)
                if getattr(o, 'backwards', False): h += math.pi
            else:
                prev = sw = None
                (x0, dur, h0, h1) = o
                if h0 is None: h0 = h                   # resolved here: whatever the earlier sources leave at this time
                k = smooth((t - x0) / dur); h = h0 + wrap(h1 - h0) * k if t < x0 + dur else h1
        if sw is not None and t < sw + TAKEOVER: h = prev + wrap(h - prev) * smooth((t - sw) / TAKEOVER)
        if self.follow and t >= self.follow['t0'] and 'P' in self.follow:
            ts, P = self.follow['ts'], self.follow['P']; i = int(np.clip(np.searchsorted(ts, t) - 1, 0, len(ts) - 1))
            for j in range(i, -1, -1):                         # last direction of motion
                if j < i and math.hypot(P[i][0] - P[j][0], P[i][1] - P[j][1]) > .08: return heading_of(P[i][0] - P[j][0], P[i][1] - P[j][1])
        return h
    def sit_at(self, t):
        s = self.sit0
        for (t0, dur, a, b) in self.sits:
            if t >= t0: s = a + (b - a) * smooth((t - t0) / dur)
        return s

VERBS = {}          # verbs added outside the core list (V3: acting/motion.py, extensions): name -> fn(shot, track, action, t0) -> t1
def verb(name):
    """decorator registering an action verb usable in "actions" by both engines"""
    def reg(fn): VERBS[name] = fn; return fn
    return reg

class World:
    """default world (no obstacles) used when an engine gives none"""
    def __init__(self, anchors=None, bounds=(-6, -2, 6, 12)): self.a = anchors or {}; self.b = bounds
    def anchor(self, name): return self.a.get(name)
    def obstacles(self): return []
    def bounds(self): return self.b
    def seat(self, name): return None
    def door(self, name): return None
    def item(self, name): return None

# ------------------------------------------------------------------ a shot
class ShotActing:
    def __init__(self, shot, world, start_states, lines_rel, dur, cast=None, props_state=None, footing=False, directed=False,
                 plant=False):
        """start_states: {id: state}; lines_rel: [(t0, t1, speaker, line_index)] relative to the shot start;
        props_state: what the previous shots changed in the set (door angles, objects put down);
        footing: opt-in, the body faces where it walks for the whole path (see Track.heading_sources);
        directed: opt-in directed locomotion, la couche au-dessus de footing (acting/approach.py);
        plant: opt-in, the stride is quantised so a path ends on the rest pose (see walk(); "foot_plant").
        Les trois sont indépendantes et cumulables : sans aucune des trois, le rendu est celui d'avant."""
        self.world = world; self.dur = dur; self.cast = cast or {}; self.tracks = {}; self.items = {}
        self.approach = bool(directed); self.plant_stride = bool(plant)
        self.doors = {}; self.lines = lines_rel; self.events = []
        self.gaze = None                                 # gaze controller (acting/gaze.py), only when the episode asks
        self.eyeflow = None                              # pupil flow (acting/eyeflow.py), only when the episode asks
        for did, ang in ((props_state or {}).get('doors') or {}).items():
            if ang > .001: self.doors[did] = [(-1e9, 1e-3, ang)]
        for it, own in ((props_state or {}).get('items') or {}).items(): self.items[it] = [(-1e9, own)]
        self._grid = None
        ids = [a.get('id', 'hero') for a in (shot.get('actors') or [])]
        for a in (shot.get('actions') or []):
            w = a.get('who', 'hero')
            if w not in ids: ids.append(w)
        absent = set(shot.get('absent') or [])
        if not shot.get('only_listed'):                      # continuity: whoever is on this set stays, until they exit
            for aid, st_ in start_states.items():
                if aid not in ids and not st_.get('gone'): ids.append(aid)
        ids = [i for i in ids if i not in absent]
        for aid in ids:
            st = dict(start_states.get(aid) or {})
            spec = next((a for a in (shot.get('actors') or []) if a.get('id', 'hero') == aid), {})
            if spec.get('at') is not None:
                p = self.resolve_xz(spec['at'])
                if p: st['x'], st['z'] = p; st.pop('y', None)
            st.setdefault('x', 0.); st.setdefault('z', 0.)
            fc = spec.get('facing', st.get('facing_spec'))
            if fc is not None or 'heading' not in st: st['heading'] = self.resolve_heading(fc, (st['x'], st['z']))
            for k in ('face', 'hold', 'gesture', 'visible'):
                if k in spec: st[k] = spec[k]
            if spec.get('posture'): st['posture'] = spec['posture']
            if spec.get('on'):
                se = world.seat(spec['on'])
                if se:                                     # the feet in front of the seat, the pelvis on it (as the sit verb)
                    se = seat_depth(se, world.obstacles()); dp = se[4]
                    st['x'], st['z'], st['heading'] = se[0] + math.sin(se[2]) * dp, se[1] + math.cos(se[2]) * dp, se[2]; st['posture'] = 'sit'; st['seat'] = se
            st['persona'] = (self.cast.get(aid) or {}).get('personality', {}); st['path_heading'] = footing
            self.tracks[aid] = Track(aid, st)
        for aid, tr in self.tracks.items():
            if tr.sit0 and tr.seat is None: tr.seat = (tr.x, tr.z, tr.heading, .47)
        self.spec_actors = {a.get('id', 'hero'): a for a in (shot.get('actors') or [])}
        acts = list(shot.get('actions') or [])
        done = {}
        for i, a in enumerate(acts):
            tr = self.tracks[a.get('who', 'hero')]
            t0 = float(a['at']) if a.get('at') is not None else (done[a['with']][0] if a.get('with') is not None and a['with'] in done else tr.cursor)
            t1 = self.schedule(tr, a, t0)
            done[i] = (t0, t1); tr.cursor = max(tr.cursor, t1)
        for aid, tr in self.tracks.items():
            if tr.follow: tr.follow['build'](self)
        self.world_events = []; self.lightning = []; self.lights = []
        for w in shot.get('world') or []:                  # the set acts on its own: a door opens, lightning, lights
            t = float(w.get('at', 0.))
            if w.get('door'):
                amt = float(w.get('open', 1.)); dur = float(w.get('dur', 1.2)); self.doors.setdefault(w['door'], []).append((t, dur, amt))
                self.world_events.append((t, 'door_slam' if (amt < .05 and dur < .5) else ('door_open' if amt > 0 else 'door_close'), {'door': w['door'], 'slow': dur > 1.5}))
            if w.get('lightning'):
                self.lightning.append(t); self.world_events.append((t + float(w.get('thunder_delay', .9)), 'thunder', {'gain': float(w.get('gain', .9))}))
            if w.get('lights'): self.lights.append((t, float(w.get('dur', 99.)), w['lights']))
        self.speech()
        if self.approach: approach.attach(self)        # last: every path and turn must already be scheduled

    # ---------------- helpers
    def grid(self):
        if self._grid is None: self._grid = Grid(self.world)
        return self._grid
    def resolve_xz(self, a, t=None):
        if a is None: return None
        if isinstance(a, (list, tuple)) and len(a) >= 2: return (float(a[0]), float(a[-1]))
        if isinstance(a, str):
            if a in getattr(self, 'tracks', {}): return self.position(self.tracks[a], t if t is not None else 0.)
            p = self.world.anchor(a)
            if p is not None: return (float(p[0]), float(p[1]))
            it = self.world.item(a)
            if it is not None: return (float(it[0]), float(it[2]))
        return None
    def resolve_heading(self, fc, at):
        if fc is None or fc == 'camera': return getattr(self.world, 'camera_heading', math.pi)
        if isinstance(fc, (int, float)): return math.radians(float(fc))
        if isinstance(fc, str) and fc in FACING: return FACING[fc]
        if fc == 'away': return getattr(self.world, 'camera_heading', math.pi) + math.pi
        p = self.resolve_xz(fc)
        if p: return heading_of(p[0] - at[0], p[1] - at[1])
        return math.pi
    def target_point(self, tgt, t):
        """3D point to look at: actor (head), anchor, item, [x,y,z], 'camera' (None)"""
        if isinstance(tgt, (list, tuple)): return (float(tgt[0]), float(tgt[1]) if len(tgt) == 3 else 1.5, float(tgt[-1]))
        if isinstance(tgt, str):
            if tgt in self.tracks:
                x, z = self.position(self.tracks[tgt], t); return (x, 1.6 - .35 * self.tracks[tgt].sit_at(t) + self.level(self.tracks[tgt], t), z)
            it = self.world.item(tgt)
            if it is not None: return tuple(float(v) for v in it)
            p = self.world.anchor(tgt)
            if p is not None: return (float(p[0]), 1.4, float(p[1]))
        return None

    def level(self, tr, t):
        """height of the feet: an airborne segment, else the level under the character (V3 worlds with levels), else
        where the last landing left them (0 on flat sets)"""
        for seg in tr.airs:
            if seg['t0'] <= t <= seg['t1']: return seg['y'](t)
        h = self.world.ground_y(*self.position(tr, t)) if getattr(self.world, 'has_levels', False) else None
        if h is None:
            h = tr.y0
            for seg in tr.airs:
                if t > seg['t1']: h = seg['y1']
        return h

    def walk(self, tr, t0, to_xz, speed=1.15, run=0., crouch=0., stop_dist=0., final_heading=None, backwards=False, keep=False, strafe=False):
        a = tr.pos_at(t0); b = to_xz
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        if stop_dist and d > stop_dist: b = (a[0] + (b[0] - a[0]) * (1 - stop_dist / d), a[1] + (b[1] - a[1]) * (1 - stop_dist / d))
        if math.hypot(b[0] - a[0], b[1] - a[1]) < .08:
            t1 = t0
        else:
            pts = round_corners(self.grid().path(a, b))
            h0 = tr.heading_at(t0)
            if tr.path_heading:                             # aim the quarter turn at what the path will really read
                h1 = Path(pts, t0, speed, run, crouch, keep=keep, plant=True).tangent(0.) + (math.pi if backwards else 0.)
            else: h1 = heading_of(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]) + (math.pi if backwards else 0.)
            tt = t0
            # Fusion des deux options. `add_turn` avec `path_heading` faux retombe exactement sur l'ancien
            # `tr.turns.append((t0, dur, h0, h1))`, donc le défaut ne bouge pas d'une image.
            if abs(wrap(h1 - h0)) > .5 and not (self.approach and strafe):   # turn towards the path first
                dur = .35 + .25 * abs(wrap(h1 - h0)) / math.pi
                if tr.path_heading: dur *= .7; self.add_turn(tr, t0, dur, h0, h1); tt = t0 + dur   # ends where the path starts
                else:
                    self.add_turn(tr, t0, dur, h0, h1)
                    tt = t0 + dur * (1. if self.approach else .7)  # "approach": turn first, then step (no skating)
            # `plant` quantises the stride so the path ends on the rest pose. It was reachable only through
            # "footing", which ALSO turns the body along the path -- a staging change. The two are independent:
            # `plant` touches nothing but the stride fed to the gait phase (not the polyline, not dist(t), not
            # t1, not tangent()), so the body walks the very same line, at the same times, facing the same way.
            # That is why "foot_plant" can be asked for on its own. docs/mesures/foot_plant.json
            p = Path(pts, tt, speed, run, crouch, keep=keep, plant=tr.path_heading or self.plant_stride)
            p.backwards = backwards; p.strafe = strafe
            tr.paths.append(p); t1 = p.t1
            tr.events += [(e, 'step', {'run': run > .5}) for e in self.steps(p)]
        if final_heading is not None:
            h0 = tr.heading_at(t1)
            if abs(wrap(final_heading - h0)) > .05:
                dur = .4 + .3 * abs(wrap(final_heading - h0)) / math.pi; self.add_turn(tr, t1, dur, h0, final_heading); t1 += dur
        return t1

    def add_turn(self, tr, t0, dur, h0, h1):
        """schedule a turn. With "footing" the start angle is left open: a turn inserted later but earlier in time
        (a character turning towards whoever speaks) must not leave a stale start angle behind it."""
        tr.turns.append((t0, dur, None if tr.path_heading else h0, h1))

    def steps(self, p):
        """footstep times: heel strikes = start of each stance (phase crosses k*pi for the two feet)"""
        out = []; n = int(p.D / p.S * 2) + 2
        for k in range(1, n + 1):
            ph = k * math.pi
            if ph < p.phase0: continue
            d = (ph - p.phase0) / (2 * math.pi) * p.S
            if d > p.D + 1e-3: break
            lo, hi = p.t0, p.t1                                # invert dist(t) by bisection
            for _ in range(28):
                mid = (lo + hi) / 2
                if p.dist(mid) < d: lo = mid
                else: hi = mid
            out.append(hi)
        return out

    def turn(self, tr, t0, target_heading, dur=None):
        h0 = tr.heading_at(t0); dh = abs(wrap(target_heading - h0))
        if dh < .03: return t0
        dur = dur or (.45 + .35 * dh / math.pi); self.add_turn(tr, t0, dur, h0, target_heading); return t0 + dur

    # ---------------- one action
    def schedule(self, tr, a, t0):
        do = a.get('do', 'wait'); W = self.world
        if do in VERBS: return VERBS[do](self, tr, a, t0)
        if do in ('walk_to', 'run_to', 'sneak_to', 'go', 'enter', 'exit'):
            if do == 'enter' and a.get('from') is not None:
                p = self.resolve_xz(a['from'], t0)
                if p: tr.x, tr.z = p if not tr.paths else (tr.x, tr.z)
            sp = a.get('speed', {'run_to': 'run', 'sneak_to': 'sneak'}.get(do, 'walk'))
            v = SPEEDS.get(sp, float(sp) if isinstance(sp, (int, float)) else 1.15)
            run = 1. if (sp == 'run' or v > 2.4) else (.4 if sp == 'hurry' else 0.)
            tgt = a.get('to')
            b = self.resolve_xz(tgt, t0)
            if b is None: return t0
            to_actor = isinstance(tgt, str) and tgt in self.tracks
            sd = float(a.get('stop_dist', .95 if to_actor else 0.))
            if self.approach: sd = approach.stop_dist(a.get('stop_dist'), to_actor)
            fh = None
            if a.get('face') is not None:
                fp = self.resolve_xz(a['face'], t0)
                fh = FACING[a['face']] if isinstance(a['face'], str) and a['face'] in FACING else (heading_of(fp[0] - b[0], fp[1] - b[1]) if fp else None)
            if fh is None and self.approach: fh = approach.stop_facing(self, tr, tgt, b, sd, a)
            t1 = self.walk(tr, t0, b, v, run, .3 if sp == 'sneak' else 0., sd, fh, bool(a.get('backwards')), strafe=bool(a.get('strafe')))
            if do == 'exit': tr.gone = True; tr.visible = (-1e9, t1 + float(a.get('linger', 0.)))
            return t1
        if do == 'turn_to':
            tg = a.get('target', a.get('to'))
            p = self.tracks[tg].pos_at(1e9) if isinstance(tg, str) and tg in self.tracks and tg != tr.id else self.resolve_xz(tg, t0)   # a walking person: where they will stop
            x, z = tr.pos_at(t0)
            tg_ = a.get('target'); h = FACING[tg_] if isinstance(tg_, str) and tg_ in FACING else (heading_of(p[0] - x, p[1] - z) if p else tr.heading_at(t0))
            return self.turn(tr, t0, h, a.get('dur'))
        if do == 'look_at':
            dur = float(a.get('dur', self.dur - t0)); tr.looks.append((t0, t0 + dur, a.get('target', 'camera'))); return t0 + float(a.get('hold', min(dur, .6)))
        if do == 'look_around':
            dur = float(a.get('dur', 2.6)); tr.looks.append((t0, t0 + dur, ('around', float(a.get('amount', 1.))))); return t0 + dur
        if do == 'gesture':
            dur = float(a.get('dur', 1.6)); tr.gestures.append((t0, t0 + dur, a.get('name', 'wave'), float(a.get('weight', 1.)))); return t0 + dur
        if do == 'face':
            tr.faces.append((t0, a.get('name', 'neutral')))
            if a.get('dur'): tr.faces.append((t0 + float(a['dur']), a.get('then', 'neutral'))); return t0 + float(a['dur'])
            return t0
        if do == 'react':
            kind = a.get('kind', 'startle'); dur = REACTS.get(kind, 1.)
            tr.reacts.append((t0, dur, kind))
            face = {'startle': 'shocked', 'gasp': 'shocked', 'flinch': 'scared', 'laugh': 'laugh', 'sigh': 'sad', 'cheer': 'joy', 'shiver': 'scared'}.get(kind)
            if face and a.get('face', True): tr.faces.append((t0, a.get('face') if isinstance(a.get('face'), str) else face))
            g = {'startle': 'surrender', 'gasp': 'hands_mouth', 'flinch': 'cover_face', 'laugh': 'laugh', 'nod': 'nod', 'shake_head': 'shake_head',
                 'cheer': 'cheer', 'shiver': 'shiver'}.get(kind)
            if g: tr.gestures.append((t0, t0 + dur, g, 1.))
            tr.events.append((t0, 'react', {'kind': kind}))
            return t0 + dur
        if do in ('pick', 'take'):
            item = a.get('item'); ip = W.item(item) if item else None
            if ip is None and a.get('from') is not None:
                q = self.resolve_xz(a['from'], t0); ip = (q[0], .8, q[1]) if q else None
            t = t0
            if ip is not None:
                x, z = tr.pos_at(t)
                if math.hypot(ip[0] - x, ip[2] - z) > .75:
                    t = self.walk(tr, t, (ip[0], ip[2]), stop_dist=.55)
                x, z = tr.pos_at(t); t = self.turn(tr, t, heading_of(ip[0] - x, ip[2] - z))
                self.items.setdefault(item, []).append((t + .45, tr.id))
                tr.reaches.append((t, t + .45, t + 1.0, 1, ('world', ip)))
                tr.holds.append((t + .45, item)); tr.events.append((t + .45, 'pickup', {'item': item}))
                tr.looks.append((t - .2, t + .8, ('point', ip)))
                return t + 1.0
            tr.holds.append((t, item)); return t
        if do == 'put':
            item = a.get('item') or self.hold_at(tr, t0); q = self.resolve_xz(a.get('on'), t0)
            t = t0
            if q is not None:
                x, z = tr.pos_at(t)
                if math.hypot(q[0] - x, q[1] - z) > .75: t = self.walk(tr, t, q, stop_dist=.55)
                x, z = tr.pos_at(t); t = self.turn(tr, t, heading_of(q[0] - x, q[1] - z))
                pt = (q[0], float(a.get('y', .8)), q[1])
                tr.reaches.append((t, t + .45, t + 1.0, 1, ('world', pt))); tr.holds.append((t + .45, None))
                self.items.setdefault(item, []).append((t + .45, ('at', pt))); tr.events.append((t + .45, 'put', {'item': item}))
                return t + 1.0
            tr.holds.append((t, None)); return t
        if do == 'give':
            rc = self.tracks.get(a.get('to')); item = a.get('item') or self.hold_at(tr, t0)
            if rc is None: return t0
            t = t0; x, z = tr.pos_at(t); rx, rz = rc.pos_at(t)
            if math.hypot(rx - x, rz - z) > 1.25: t = self.walk(tr, t, (rx, rz), stop_dist=1.0); x, z = tr.pos_at(t)
            t = self.turn(tr, t, heading_of(rx - x, rz - z)); self.turn(rc, t - .3, heading_of(x - rx, z - rz))
            mid = ((x + rx) / 2, 1.05, (z + rz) / 2)
            tr.reaches.append((t, t + .55, t + 1.1, 1, ('world', mid))); rc.reaches.append((t + .1, t + .55, t + 1.2, 1, ('world', mid)))
            tr.holds.append((t + .55, None)); rc.holds.append((t + .55, item)); tr.looks.append((t, t + 1.2, rc.id)); rc.looks.append((t, t + 1.4, tr.id))
            tr.events.append((t + .55, 'give', {'item': item, 'to': rc.id}))
            return t + 1.1
        if do == 'sit':
            se = W.seat(a.get('on')) if a.get('on') else None
            if se is None:
                x, z = tr.pos_at(t0); h = tr.heading_at(t0); se = (x - math.sin(h) * .3, z - math.cos(h) * .3, h, .47)
            se = seat_depth(se, W.obstacles()); sx, sz, sh, sy, dp = se
            front = (sx + math.sin(sh) * dp, sz + math.cos(sh) * dp)
            obs = [o for o in (W.obstacles() or []) if not (o[0] <= sx <= o[2] and o[1] <= sz <= o[3])]    # not the seat itself
            inside = lambda p_, m: any(o[0] - m < p_[0] < o[2] + m and o[1] - m < p_[1] < o[3] + m for o in obs)
            if inside(front, .12):                     # a chair at a table: arrive beside the place, then slide in while sitting
                rx, rz = math.cos(sh), -math.sin(sh); here = tr.pos_at(t0)
                cands = [c for c in [(front[0] + rx * k, front[1] + rz * k) for k in (.55, -.55, .75, -.75)] + [(sx + math.sin(sh) * .7, sz + math.cos(sh) * .7)] if not inside(c, .22)]
                if cands:
                    ap = min(cands, key=lambda c: math.hypot(c[0] - here[0], c[1] - here[1]))
                    t = self.walk(tr, t0, ap, final_heading=sh)
                    sl = Path([ap, front], t, .9); tr.paths.append(sl); tr.turns.append((t, .01, sh, sh))   # side step, still facing the table
                    t2 = t + (sl.t1 - t) * .6                                                              # sits down as the step ends
                    tr.sits.append((t2, 1.0, tr.sit_at(t2), 1.)); tr.seat = se; tr.events.append((t2 + .6, 'sit', {}))
                    return t2 + 1.0
            t = self.walk(tr, t0, front, final_heading=sh)
            tr.sits.append((t, 1.0, tr.sit_at(t), 1.)); tr.seat = se; tr.events.append((t + .6, 'sit', {}))
            return t + 1.0
        if do == 'stand':
            if tr.sit_at(t0) < .01: return t0
            tr.sits.append((t0, .9, tr.sit_at(t0), 0.)); tr.events.append((t0 + .2, 'stand', {})); return t0 + .9
        if do in ('open', 'close'):
            dr = W.door(a.get('door', a.get('target')))
            if dr is None: return t0
            hx, hz = dr['handle_front']; t = self.walk(tr, t0, (hx, hz), final_heading=dr['facing'])
            k = self.doors.setdefault(dr['id'], [])
            dur = float(a.get('dur', 1.1)); amount = float(a.get('amount', 1.)) if do == 'open' else 0.
            tr.reaches.append((t, t + .35, t + .35 + dur * .6, 1, ('door', dr['id'])))
            k.append((t + .35, dur, amount)); tr.events.append((t + .35, 'door_open' if do == 'open' else 'door_close', {'door': dr['id']}))
            return t + .35 + dur * .7
        if do == 'follow':
            tgt = self.tracks.get(a.get('target'))
            if tgt is None: return t0
            dist = float(a.get('dist', 1.0)); lag = float(a.get('lag', .5)); vmax = float(a.get('max_speed', 1.8)); me = tr
            def build(sa, me=me, tgt=tgt, t0=t0, dist=dist, lag=lag, vmax=vmax):
                dt = 1 / 30.; ts = np.arange(t0, sa.dur + .1, dt); x, z = me.pos_at(t0); pts = []
                for t in ts:
                    gx, gz = tgt.pos_at(max(t0, t - lag)); dx, dz = gx - x, gz - z; d = math.hypot(dx, dz)
                    if d > dist: st_ = min(d - dist, vmax * dt); x += dx / d * st_; z += dz / d * st_
                    pts.append((x, z))
                P = np.array(pts, np.float32); cum = np.concatenate([[0.], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
                me.follow.update(ts=ts, P=P, cum=cum)
            tr.follow = {'t0': t0, 'build': build}
            return t0
        if do == 'wait': return t0 + float(a.get('dur', 1.))
        return t0

    def hold_at(self, tr, t):
        h = None
        for (t0, it) in tr.holds:
            if t >= t0: h = it
        return h

    def busy_moving(self, tr, t):
        return any(p.t0 - .1 <= t <= p.t1 + .1 for p in tr.paths) or any(t0 <= t <= t0 + d for (t0, d, _, _) in tr.turns) or (tr.follow is not None and t >= tr.follow['t0'])

    def orient_to(self, tr, other, t):
        """turn the body towards someone when the head alone would have to turn too far (people face who they talk to)"""
        if tr is other or self.busy_moving(tr, t) or tr.sit_at(t) > .3: return
        x, z = self.position(tr, t); ox, oz = self.position(other, t)
        want = heading_of(ox - x, oz - z)
        if abs(wrap(want - tr.heading_at(t))) > .55: self.turn(tr, t, want)

    def speech(self):
        """mouth, talk gestures and listener behaviour from the lines spoken in this shot"""
        for (l0, l1, who, li) in self.lines:
            tr = self.tracks.get(who)
            if tr is None: continue
            tr.talk.append((l0, l1))
            ex = lambda o: bool((self.cast.get(o.id) or {}).get('extra'))        # figurants (voxelgpu/b_extras.py) : ils ne volent jamais le regard d'un principal ; entre eux, ils se parlent
            people = [o for o in self.tracks.values() if o is not tr and not (self.cast.get(o.id) or {}).get('kind') and ex(o) == ex(tr)]
            if people:
                x, z = self.position(tr, l0)
                near = min(people, key=lambda o: math.hypot(self.position(o, l0)[0] - x, self.position(o, l0)[1] - z))
                if math.hypot(self.position(near, l0)[0] - x, self.position(near, l0)[1] - z) < 3.5:
                    self.orient_to(tr, near, max(0., l0 - .2))
                    for o in people:
                        if math.hypot(self.position(o, l0)[0] - x, self.position(o, l0)[1] - z) < 3.5: self.orient_to(o, tr, max(0., l0 - .1))
            expr = float(tr.persona.get('expressive', .6))
            t = l0 + .25; k = 0
            while t < l1 - .6 and expr > .15:
                busy = any(g0 <= t <= g1 for (g0, g1, _, _) in tr.gestures) or any(r0 <= t <= r1 for (r0, _, r1, _, _) in tr.reaches)
                if not busy:
                    name = TALK_GESTURES[int(h32(tr.id, li, k) * len(TALK_GESTURES))]
                    d = 1.1 + .8 * h32(li, k, tr.id)
                    tr.gestures.append((t, min(l1, t + d), name, .45 + .45 * expr))
                t += 1.6 + 1.6 * h32(tr.id, k, li) / max(expr, .3); k += 1

    # ---------------- sampling
    def end_states(self):
        out = {}
        for aid, tr in self.tracks.items():
            x, z = self.position(tr, self.dur); h = tr.heading_at(self.dur)
            st = {'x': x, 'z': z, 'heading': h, 'face': self.face_at(tr, self.dur), 'hold': self.hold_at(tr, self.dur), 'gesture': tr.base_gesture}
            if tr.sit_at(self.dur) > .5: st['posture'] = 'sit'; st['seat'] = tr.seat
            if tr.gone: st['gone'] = True
            if tr.airs or getattr(self.world, 'has_levels', False): st['y'] = self.level(tr, self.dur)
            out[aid] = st
        return out
    def position(self, tr, t):
        if tr.follow and t >= tr.follow['t0'] and 'P' in tr.follow:
            ts, P = tr.follow['ts'], tr.follow['P']; f = (t - ts[0]) / (ts[1] - ts[0]) if len(ts) > 1 else 0.
            i = int(np.clip(math.floor(f), 0, len(ts) - 2)); u = min(1., max(0., f - i))
            return float(P[i][0] + (P[i + 1][0] - P[i][0]) * u), float(P[i][1] + (P[i + 1][1] - P[i][1]) * u)
        return tr.pos_at(t)
    def face_at(self, tr, t):
        f = 'neutral'
        for (t0, n) in tr.faces:
            if t >= t0: f = n
        return f

    def gait(self, tr, t):
        """walk weight, phase, stride, run, crouch at time t"""
        for seg in tr.airs:                                    # in the air: no walk cycle (rig.solve takes the air pose)
            if seg['t0'] <= t <= seg['t1']: return 0., 0., 1.25, 0., 0.
        if tr.follow and t >= tr.follow['t0'] and 'P' in tr.follow:
            a = self.position(tr, t - .15); b = self.position(tr, t); v = math.hypot(b[0] - a[0], b[1] - a[1]) / .15
            ts, cum = tr.follow['ts'], tr.follow['cum']; d = float(np.interp(t, ts, cum)); S = rig.stride_for(max(.8, v))
            return min(1., v / .35), math.pi * .62 + 2 * math.pi * d / S, S, min(1., max(0., (v - 1.9) / 1.2)), 0.
        for p in tr.paths:
            if getattr(p, 'air', False): continue
            if p.t0 - .05 <= t <= p.t1 + .3:
                d = p.dist(t); ph = p.phase0 + (-1 if getattr(p, 'backwards', False) else 1) * 2 * math.pi * d / p.S
                w = 1. if t <= p.t1 else 1 - smooth((t - p.t1) / .3)
                return w, ph, p.S, p.run, p.crouch
        for (t0, dur, h0, h1) in tr.turns:                     # small steps while turning on the spot
            if t0 <= t <= t0 + dur and not any(p.t0 <= t <= p.t1 for p in tr.paths):
                k = (t - t0) / dur; return .35 * math.sin(math.pi * k), math.pi * .62 + 2 * math.pi * k, .5, 0., 0.
        return 0., 0., 1.25, 0., 0.

    def raw_head(self, aid, tr, t, x, z, y, h, s, w, base, speaking, look_at_camera=None):
        """head (yaw, pitch) relative to the torso, before the gaze controller: explicit look, conversation,
        walking ahead, idle glances. The target can change from one frame to the next (a new speaker, a look_at that
        ends): that is what acting/gaze.py smooths when the episode asks for it."""
        tgt = None
        for (l0, l1, tg) in tr.looks:
            if l0 <= t <= l1: tgt = (l0, l1, tg)
        yaw = pitch = 0.
        if tgt is not None and isinstance(tgt[2], tuple) and tgt[2][0] == 'around':
            k = (t - tgt[0]) / max(1e-3, tgt[1] - tgt[0]); amt = tgt[2][1]
            yaw = 1.05 * amt * math.sin(2 * math.pi * k) * math.sin(math.pi * k); pitch = .05 * math.sin(4 * math.pi * k)
            return yaw, pitch
        pt = None
        if tgt is not None:
            tg = tgt[2]
            pt = tg[1] if isinstance(tg, tuple) and tg[0] == 'point' else (look_at_camera if tg == 'camera' else self.target_point(tg, t))
        elif speaking and aid not in speaking: pt = self.target_point(speaking[0], t)
        elif aid in speaking and len(self.tracks) > 1:
            others = [o for o in self.tracks if o != aid]
            o = min(others, key=lambda o_: math.hypot(base[o_][0] - x, base[o_][1] - z)); pt = self.target_point(o, t)
        if pt is not None:
            dx, dz = pt[0] - x, pt[2] - z; hy = 1.62 * (1 - .35 * s) + y
            yaw = wrap(heading_of(dx, dz) - h); pitch = math.atan2(pt[1] - hy, math.hypot(dx, dz) + 1e-6)
            k = 1.
            if tgt is not None: k = smooth((t - tgt[0]) / .3) * (1 - smooth((t - tgt[1]) / .3))
            yaw *= k; pitch *= k
        elif w > .3:
            yaw = .12 * math.sin(t * .9 + tr.seed)
        else:
            yaw = .10 * math.sin(t * .37 + tr.seed) + .06 * math.sin(t * 1.3 + tr.seed * 2)
        return yaw, pitch

    def raw_heads(self, t, look_at_camera=None):
        """{id: (yaw, pitch, heading)} before the gaze controller, for every character of the shot at time t"""
        base = {aid: (*self.position(tr, t), tr.heading_at(t)) for aid, tr in self.tracks.items()}
        speaking = [tr.id for tr in self.tracks.values() if any(a <= t <= b for a, b in tr.talk)]
        out = {}
        for aid, tr in self.tracks.items():
            x, z, h = base[aid]
            w = self.gait(tr, t)[0]; s = tr.sit_at(t); y = self.level(tr, t)
            out[aid] = (*self.raw_head(aid, tr, t, x, z, y, h, s, w, base, speaking, look_at_camera), h)
        return out

    def raw_eye(self, t):
        """{id: (residual yaw, residual pitch)} -- exactly the `eye` of sample(t) before acting/eyeflow.py
        smooths it. Same `neck()` as the renderer, so the smoothing can only ever be applied to the real
        residual; it is what eyeflow.build() reads on its 60 Hz grid."""
        return {aid: neck(self.gaze, aid, t, h, yaw, pitch)[2]
                for aid, (yaw, pitch, h) in self.raw_heads(t).items()}

    def sample(self, t, look_at_camera=None):
        """-> {id: dict(x, z, heading, rig=params for rig.solve, face, hold, talking, reach_world, visible)}"""
        base = {}
        for aid, tr in self.tracks.items():
            x, z = self.position(tr, t); h = tr.heading_at(t)
            base[aid] = (x, z, h)
        out = {}
        speaking = [tr.id for tr in self.tracks.values() if any(a <= t <= b for a, b in tr.talk)]
        for aid, tr in self.tracks.items():
            x, z, h = base[aid]
            y = self.level(tr, t)
            w, ph, S, run, crouch = self.gait(tr, t)
            s = tr.sit_at(t)
            gests = []
            if tr.base_gesture and tr.base_gesture not in ('idle',): gests.append((tr.base_gesture, 1., t))
            for (g0, g1, name, wt) in tr.gestures:
                if g0 - .01 <= t <= g1 + .3:
                    k = smooth((t - g0) / .28) * (1 - smooth((t - g1) / .3)); gests.append((name, wt * k, t - g0))
            face = self.face_at(tr, t)
            p = dict(t=t, seed=tr.seed, phase=ph, gait=w, run=run, stride=S, sit=s, crouch=max(crouch, tr.crouch0), gestures=gests)
            if tr.seat: p['seat_h'] = tr.seat[3]; p['seat_z'] = -(tr.seat[4] if len(tr.seat) > 4 else .30)
            for seg in tr.airs:                                 # V3: take-off, flight, landing (rig.solve air pose)
                if seg['t0'] - .06 <= t <= seg['t1'] + .02:
                    p['air'] = smooth((t - seg['t0'] + .06) / .12) * (1 - smooth((t - seg['t1'] + .1) / .12))
                    p['air_k'] = min(1., max(0., (t - seg['t0']) / max(1e-3, seg['t1'] - seg['t0']))); p['air_style'] = seg.get('style', 'leap')
                    if seg.get('lean') is not None: p['lean'] = p.get('lean', 0.) + seg['lean'] * p['air']
            for (q0, qd, amt) in tr.squats:                     # knees bend before a jump, absorb the landing
                if q0 <= t <= q0 + qd: p['crouch'] = max(p['crouch'], amt * math.sin(math.pi * (t - q0) / qd))
            if face in SAD: p['slump'] = .7
            if face in TENSE: p['tension'] = .6
            if face in UP: p['chest_up'] = .6
            bounce = 0.
            for (r0, dur, kind) in tr.reacts:
                k = (t - r0) / dur
                if 0 <= k <= 1:
                    if kind == 'startle': bounce += .07 * math.sin(math.pi * min(1., k * 2.5)) ; p['lean'] = p.get('lean', 0.) - .25 * math.sin(math.pi * k)
                    elif kind == 'sigh': p['slump'] = max(p.get('slump', 0.), .8 * math.sin(math.pi * k))
                    elif kind == 'laugh': bounce += .015 * abs(math.sin(t * 14)); p['lean'] = p.get('lean', 0.) + .12 * math.sin(math.pi * k)
                    elif kind == 'flinch': p['lean'] = p.get('lean', 0.) - .15 * math.sin(math.pi * k); p['tension'] = 1.
                    elif kind == 'cheer': bounce += .05 * abs(math.sin(t * 8))
            p['bounce'] = bounce
            # reach: target point in the character's local frame
            reach = {}; hold_world = None
            for (r0, rc, r1, side, tgt) in tr.reaches:
                if r0 <= t <= r1 + .05:
                    wt = smooth((t - r0) / max(1e-3, rc - r0)) if t < rc else 1 - smooth((t - rc - .12) / max(1e-3, r1 - rc - .12))
                    if tgt[0] == 'world': P_ = tgt[1]
                    elif tgt[0] == 'door': P_ = self.door_handle(tgt[1], t)
                    else: continue
                    dx, dz = P_[0] - x, P_[2] - z; c, s_ = math.cos(-h), math.sin(-h)
                    reach[side] = ((dx * c + dz * s_, P_[1] - y if y else P_[1], -dx * s_ + dz * c), wt)
            p['reach'] = reach
            # head: explicit look, conversation, walking ahead, idle glances
            yaw, pitch = self.raw_head(aid, tr, t, x, z, y, h, s, w, base, speaking, look_at_camera)
            lim = LIM_YAW
            # What the NECK could not deliver: its clamp, plus the slew lag of the gaze controller when the
            # episode asked for one. It is what an eye is for, and until now nobody carried it: the head
            # simply stopped at 0.95 rad and the character addressed someone he was not looking at (measured
            # in docs/P1_INTERACTION_REGARD_20261025.md). Written next to `gaze` and `blink` as a pure
            # measurement, in radians, in the head's own frame; applying it is a matter for an engine
            # (engines/pixel3d/eyes.py, opt-in). A consumer that ignores this key renders exactly as before,
            # which is why CONSOLE 2D is untouched by it.
            yaw, pitch, eye, clamped = neck(self.gaze, aid, t, h, yaw, pitch)
            gaze = ('right' if yaw > 0 else 'left') if clamped else None
            # the régie's target teleports (a line starts, a shot cuts) and so did this residual, one frame
            # from one edge of the socket to the other: acting/eyeflow.py replays it as a saccade when the
            # episode asks ("eye_smooth"). Absent key, absent solver, same floats as before.
            if self.eyeflow is not None: eye = self.eyeflow.eye(aid, t, eye)
            if abs(yaw) > .45 and gaze is None: gaze = 'right' if yaw > 0 else 'left'
            for (l0, l1, _) in [(a, b, 0) for (a, b) in tr.talk]:                     # nods while speaking
                if l0 <= t <= l1: pitch += .05 * math.sin(t * 7.3 + tr.seed)
            if speaking and aid not in speaking: pitch += .03 * max(0., math.sin(t * 2.1 + tr.seed))
            p['head'] = (yaw, pitch)
            if tr.ctrl is not None: tr.ctrl.decorate(p, t, lim)    # "approach": head leads, torso banks
            blink = (t * (1 / 3.3) + tr.seed) % 1. < .036
            vis = True
            if tr.visible is not None: vis = tr.visible[0] <= t <= tr.visible[1]
            out[aid] = dict(x=x, z=z, y=y, heading=h, rig=p, face=face, hold=self.hold_at(tr, t), talking=aid in speaking,
                            gaze=gaze, blink=blink, eye=eye, visible=vis, seat=tr.seat if s > .01 else None)
        return out

    def door_angle(self, did, t):
        a = 0.
        for (t0, dur, amount) in self.doors.get(did, []):
            if t >= t0: a = a + (amount - a) * smooth((t - t0) / dur) if t < t0 + dur else amount
        return a
    def door_handle(self, did, t):
        dr = self.world.door(did)
        if dr is None: return (0, 1., 0)
        return dr['handle'](self.door_angle(did, t))

    def item_owner(self, item, t):
        """None (at its world place) | actor id | ('at', point)"""
        own = None
        for (t0, who) in sorted(self.items.get(item, []), key=lambda e: e[0]):
            if t >= t0: own = who
        return own

    def all_events(self):
        ev = []
        for tr in self.tracks.values(): ev += [(t, kind, tr.id, d) for (t, kind, d) in tr.events]
        return sorted(ev, key=lambda e: e[0])

def seat_depth(se, obstacles):
    """(x, z, yaw, height, depth): the feet go just past the front edge of the furniture (deep sofa, simple chair)"""
    sx, sz, sh = se[0], se[1], se[2]; dx, dz = math.sin(sh), math.cos(sh); out = .30
    for o in obstacles or []:
        if o[0] <= sx <= o[2] and o[1] <= sz <= o[3]:
            ts = [((o[2] if dx > 0 else o[0]) - sx) / dx] if abs(dx) > 1e-3 else []
            ts += [((o[3] if dz > 0 else o[1]) - sz) / dz] if abs(dz) > 1e-3 else []
            if ts: out = min(.45, max(.30, min(ts) + .06))
    return tuple(se[:4]) + (out,)

# ------------------------------------------------------------------ the whole episode (continuity)
class Acting:
    """compiles every shot that uses actions or the v2 acting, in order, carrying states per set"""
    def __init__(self, episode, spans, lines, world_of, cast=None):
        self.shots = {}; self.ep = episode; states = {}; props = {}
        cast = cast or episode.get('cast', {}) or {}
        from .cast import series
        carried = episode.get('series_state')               # explicit state (replay of a given point of the series)
        if carried is None: carried = ((series(episode.get('series')) or {}).get('state') or {}) if episode.get('series') else {}
        self.first_seen = set(); self.set_of = {}
        meta = episode.get('lines', {}) or {}
        for k, shot in enumerate(episode['shots']):
            if not uses_acting(episode, shot): continue
            set_name = shot.get('set', episode.get('default_set')); w = world_of(set_name, shot)
            t0, t1 = spans[k]
            l0, l1 = shot['lines']; lr = []
            for li in range(l0, l1 + 1):
                if li >= len(lines): break
                sp = (meta.get(str(li)) or {}).get('speaker') or lines[li].get('speaker')
                if sp: lr.append((lines[li]['start'] - t0, lines[li]['end'] - t0, sp, li))
            st = states.setdefault(set_name, {}); ps = props.setdefault(set_name, {})
            if shot.get('reset'): st.clear(); ps.clear()
            for a_ in [x.get('id', 'hero') for x in (shot.get('actors') or [])] + [x.get('who', 'hero') for x in (shot.get('actions') or [])]:
                if a_ not in self.first_seen:                 # first appearance in this episode: what the series remembers
                    self.first_seen.add(a_); ref = (cast.get(a_) or {}).get('ref', a_) if isinstance(cast.get(a_), dict) else a_
                    keep = carried.get(a_) or carried.get(ref) or {}
                    if keep.get('hold') and a_ not in st: st[a_] = dict(st.get(a_, {}), hold=keep['hold'])
            if shot.get('tracks'):                                   # mise en scène dirigée à la main (acting/directed.py)
                from .directed import DirectedActing
                sa = DirectedActing(shot, t1 - t0, w, cast)
                self.shots[k] = sa; self.set_of[k] = set_name; st.update(sa.end_states()); continue
            sa = ShotActing(shot, w, st, lr, t1 - t0, cast, ps,
                            footing(episode, shot), approach.wanted(episode, shot), planted(episode, shot))
            self.shots[k] = sa; self.set_of[k] = set_name
            st.update(sa.end_states())
            ps['doors'] = {d: sa.door_angle(d, t1 - t0) for d in sa.doors}        # continuity of the set itself
            ps['items'] = {it: sa.item_owner(it, t1 - t0) for it in sa.items}
        from . import gaze as _gaze                          # opt-in gaze controller (episode / shot "eyeline")
        _gaze.plan(self, episode, self.set_of)
        from . import eyeflow as _eyeflow                     # opt-in pupil flow (episode / shot "eye_smooth"),
        _eyeflow.plan(self, episode, self.set_of)             # after the head: it reads the residual the head leaves

def uses_acting(episode, shot):
    return bool(shot.get('actions')) or bool(shot.get('tracks')) or int(episode.get('engine_version', 1)) >= 2

def footing(episode, shot):
    """episode / shot "footing": "path" (or true) -> the body turns along the path it walks instead of keeping the
    heading of the quarter turn that started the walk. Absent or false: the historical behaviour, frame for frame."""
    v = shot.get('footing', episode.get('footing'))
    return bool(v) and not (isinstance(v, str) and v in OFF_WORDS)

def planted(episode, shot):
    """episode / shot "foot_plant": true -> the stride of every path is quantised so the walk ends on the rest
    pose, instead of a quarter cycle off with the legs split. The soles then stop being dragged through the floor
    while the walk cycle fades out at the end of a path (tools/foot_plant_qc.py measures it).

    Nothing else changes: same polyline, same speed profile, same heading, same shot length -- only the stride
    the gait phase is tied to. "footing" already implied it; this key gives it without the heading change, so a
    staged scene can have planted feet without being re-staged. Absent or false: the historical behaviour.
    """
    v = shot.get('foot_plant', episode.get('foot_plant'))
    return bool(v) and not (isinstance(v, str) and v in OFF_WORDS)

from . import motion  # noqa: E402,F401  (registers the V3 verbs: jump, climb, fall)
from . import approach  # noqa: E402  (opt-in directed locomotion, episode "approach")
