"""Background life: three to five secondary characters who are present, busy and synchronised on a scene.

WHAT THIS IS NOT. There is no crowd engine here, no per-inhabitant AI, no new verb, no new renderer path and no
second body. Every behaviour below is written with the actions `acting/timeline.py` already owns -- `walk_to`,
`run_to`, `wait`, `look_around`, `look_at`, `turn_to`, `gesture`, `face`, `react`, `follow`, `exit` -- and every
figurant is a plain entry of the episode `cast`, i.e. a look the two engines already know how to dress. What this
module adds is the three things a scene file cannot hold by itself and that nobody wants to write by hand four
times per shot:

  1. IDENTITIES (`FIGURANTS`). Recognisable people, not recolours of one: a coat under a beanie, a hoodie under
     a cap, an apron on a bald head, a dress under a hood. The silhouette carries the identity -- garment, head,
     stature -- because at twelve metres in a 9:16 frame a colour does not read and an outline does. The corpulent cube body itself is NOT
     set here: it is the episode's own `"body": "voxel_premium"` key, shared with the leads, because a figurant
     built from another body would be a mixed model and that is exactly the defect to avoid.
  2. SAFE GROUND (`LANES`). A sidewalk is not where a place generator says the sidewalk anchor is: it is the
     corridor that is actually free of streetlights, hydrants, mailboxes and bus shelters. The lanes below were
     measured on the real `SetWorld.obstacles()` of the place (see tools/check_background_plan.py, which
     re-measures them on every run and fails if a waypoint or a segment stops being walkable).
  3. ORCHESTRATION (`BEATS`). A shot says what the street is DOING -- living, startled, fleeing -- and each
     figurant answers from its own role with its own small delay. The delay is derived from the figurant id and
     the scene seed, so the same scene renders identically twice and the reactions are still not simultaneous.

OPT-IN, OFF BY DEFAULT. `apply()` returns the episode UNCHANGED (the very same object) unless it carries an
`"extras"` key: no episode, demo or test in the repository carries one, so every existing render is frame for
frame what it was. `HSTUDIO_EXTRAS=0` in the environment forces the expansion off even for a scene that asks for
it, which is the global switch to keep closed until the owner has judged the video.

The episode key, in full:

  "extras": {
    "set": "rue",                       # which set the lanes belong to (default: the episode default_set)
    "lanes": "city_street",             # lane table (default: the type of that set); or an inline table
    "seed": 5,                          # the only source of the per-figurant delays and lateral offsets
    "troupe": ["passante", "flaneur", "vendeur", "mamie"],
    "clear": 3.6,                       # metres kept between a figurant and any lead (see KEEP_CLEAR)
    "enter": {"passante": [-5.0, 4.6]},     # where a figurant starts, when the lane default is not what the frame needs
    "spots":  {"vendeur": "porte_proche"},  # which named standing place a role takes
    "beats": [
      {"shot": 0, "do": "life"},
      {"shot": 2, "do": "threat", "at": 1.1, "from": [0.0, 24.0]},
      {"shot": 3, "do": "flee",   "from": [0.0, 24.0]}
    ]
  }

WHAT IT DELIBERATELY DOES NOT DO, and what the integrator would have to decide (this lot does not touch
acting/cinema.py, hstudio/director/ nor the storyboard tools, so these are proposals and not changes):
  - `ShotActing.speech()` turns a speaker towards the NEAREST person within 3.5 m. A figurant that walks closer
    to a lead than their dialogue partner therefore steals the eyeline. This module keeps figurants `clear`
    metres away from every lead instead, and tools/check_background_motion.py MEASURES that the nearest person to
    each speaker is always a lead. The real fix is one line in timeline.py (skip a cast entry marked
    `"crowd": true` when choosing the listener) and it belongs to whoever owns that file.
  - the camera solver already dodges non-subject bodies (engines/pixel3d/acted.py, `blocked_at`), so a figurant
    never has to be told about the lens. Nothing here asks for a camera change."""
import math, os, copy
from .timeline import h32        # the acting layer's own hash: the figurants' delays come from the same one

# ------------------------------------------------------------------ measured invariants (also asserted by the tools)
BODY = .52              # m, two bodies closer than this interpenetrate (same number as tools/locomotion_qc.py)
MIN_GAP = .95           # m, the planner never aims two figurants closer than this
PASS_GAP = .78          # m, shoulder to shoulder on a pavement: what two bodies CROSSING need, which is less than
                        # what two bodies STOPPING need. Still a quarter of a metre clear of BODY, so nobody ever
                        # interpenetrates; using MIN_GAP here instead would make every walker stop dead behind
                        # anybody standing on a 0.4 m wide sidewalk corridor, and that is not how a street looks.
KEEP_CLEAR = 3.6        # m kept from every lead: just outside the 3.5 m listener radius of ShotActing.speech()
REACT_WINDOW = .45      # s, a figurant's startle must land inside [threat, threat + REACT_WINDOW]
SPEED_ORDER = {'slow': 0, 'stroll': 1, 'walk': 2, 'hurry': 3, 'run': 4}   # only used to cap a body behind a slower one


# ------------------------------------------------------------------ 1. the identities
# Each look uses only keys the two engines already read (engines/pixel3d/poses.py OUTFITS / HAIR_STYLES / HATS,
# engines/console/figure2d.py). `role` is what the figurant does when the street is merely living; `lane` is the
# sidewalk it belongs to and `dir` the way it walks along it (+1 away from the camera, -1 towards it, 0 stays).
FIGURANTS = {
    'passante': dict(
        label='La passante pressee', role='walker', lane='left', dir=+1, speed='hurry', busy='phone',
        look=dict(outfit='coat', hat='beanie', hat_color=(182, 74, 62), hair_style='ponytail', hair=(54, 38, 30),
                  hood=(92, 80, 102), jeans=(46, 44, 54), skin=(226, 188, 154), headphones=False, backpack=False)),
    'flaneur': dict(
        label='Le flaneur au casque', role='walker', lane='right', dir=-1, speed='stroll', busy='pockets',
        look=dict(outfit='hoodie', hat='cap', hat_color=(40, 46, 60), hair_style='short', hair=(28, 22, 18),
                  hood=(62, 122, 104), jeans=(58, 60, 70), skin=(172, 116, 84), headphones=True, backpack=False)),
    'vendeur': dict(
        label='Le vendeur sur le pas de la porte', role='host', lane='left', dir=0, speed='walk', busy='show',
        scale=1.06,
        look=dict(outfit='apron', hat='none', hair_style='bald', hair=(36, 30, 26), hood=(232, 228, 218),
                  jeans=(70, 66, 62), skin=(206, 150, 112), headphones=False, backpack=False)),
    'mamie': dict(
        label='La mamie au cabas', role='waiter', lane='right', dir=0, speed='slow', busy='hands_behind',
        scale=.94,
        look=dict(outfit='dress', hat='hood', hat_color=(108, 66, 92), hair_style='bun', hair=(220, 220, 224), glasses=True,
                  hood=(146, 94, 124), jeans=(146, 94, 124), skin=(224, 196, 170), headphones=False, backpack=False)),
    'ado': dict(
        label="L'ado au bord du trottoir", role='waiter', lane='left', dir=0, speed='walk', busy='phone',
        scale=.82,
        look=dict(outfit='tshirt', hat='none', hair_style='spiky', hair=(220, 180, 70), hood=(220, 70, 60),
                  jeans=(44, 52, 92), skin=(216, 172, 136), headphones=False, backpack=True)),
}
DEFAULT_TROUPE = ('passante', 'flaneur', 'vendeur', 'mamie', 'ado')

# ------------------------------------------------------------------ 2. the safe ground
# A lane is a polyline of waypoints that the acting layer walks between (its own A* still routes around whatever
# stands in the way); `spots` are places where somebody may STAND for a whole shot; `away` is where a frightened
# body runs out of the set. Every number was read off the real obstacles of the place, never off its anchors.
LANES = {
    'city_street': {
        # the left sidewalk at x = -5.0 is the one corridor of this place that is free from z = -2 to z = 30:
        # x = -4.2 has the trash can and the mailbox, x = -3.8 the streetlights, x = -5.4 the shop fronts.
        'left': [(-5.0, -1.4), (-5.0, 2.2), (-5.0, 8.0), (-5.0, 14.5), (-5.0, 21.0), (-5.0, 27.5)],
        # the right sidewalk has the hydrant at (4.2, 5.9) and the bus shelter at (4.7..5.3, 12.5..15.5): the lane
        # steps inwards to x = 4.0 to pass the shelter and stays outside the road, which ends at x = 3.2.
        'right': [(4.5, -1.4), (4.5, 2.4), (4.55, 8.6), (4.0, 13.2), (4.55, 18.5), (4.55, 25.0)],
        # standing places. The `_loin` ones are the useful ones in 9:16: a vertical frame is only ~4.2 m wide at
        # the subject's own depth, so a figurant standing beside the lead is OUT of frame while the same figurant
        # fifteen metres further up the street is inside it. The near spots stay for 16:9 and for a hall.
        # The `_loin` ones also stand OFF the lane centre line, by more than MIN_GAP, which is the only way a
        # body can stand on a 0.4 m wide sidewalk corridor without a walker having to stop behind it: the
        # shopkeeper is in his doorway between two buildings (x = -6.2 is free from z = 14.5 to 19.5) and the
        # woman waiting is on the kerb (x = 3.4, the edge of the roadway, free except under the traffic light).
        'spots': {'devanture': (-5.0, 7.2), 'vitrine': (-5.0, 11.4), 'arret': (4.3, 10.6), 'bord': (4.5, 3.4),
                  'porte_proche': (-6.2, 5.6), 'bordure_proche': (3.4, 7.0),
                  'porte_loin': (-6.2, 17.0), 'bordure_loin': (3.4, 16.4), 'trottoir_loin': (-5.0, 21.0)},
        'away': {'left': (-5.0, -1.4), 'right': (4.5, -1.4)},
        # how far off the centre line a figurant may be pushed so that two bodies on the SAME lane never walk
        # down the same line: +-.15 m here, because x = -5.2 is still free but x = -5.28 is already the shop front.
        'lat': .15,
    },
}
# where a role stands when the scene does not say: the host in front of his shop, the waiters at their spot
HOME = {'host': 'devanture', 'waiter': {'left': 'bord', 'right': 'arret'}}


# ------------------------------------------------------------------ 3. the orchestration
BEATS = {}


def beat(name):
    """decorator registering a beat (registry, not if/elif -- AGENTS.md)"""
    def reg(fn):
        BEATS[name] = fn
        return fn
    return reg


class Plan:
    """one expansion: what was decided, why, and everything a test needs to check it without rendering"""
    def __init__(self, ep, spec):
        self.ep = ep
        self.spec = dict(spec or {})
        self.seed = self.spec.get('seed', 7)
        self.set = self.spec.get('set') or ep.get('default_set') or 'set'
        tbl = self.spec.get('lanes') or (((ep.get('sets') or {}).get(self.set) or {}).get('type'))
        self.table_name = tbl if isinstance(tbl, str) else '(inline)'
        self.lanes = copy.deepcopy(tbl if isinstance(tbl, dict) else LANES.get(tbl) or {})
        troupe = self.spec.get('troupe') or 4
        if isinstance(troupe, int):
            troupe = list(DEFAULT_TROUPE[:max(0, min(troupe, len(DEFAULT_TROUPE)))])
        self.troupe = [f for f in troupe if f in FIGURANTS]
        self.unknown = [f for f in (troupe or []) if f not in FIGURANTS]
        self.clear = float(self.spec.get('clear', KEEP_CLEAR))
        self.at = {}            # figurant -> (x, z) where it is right now in the plan
        self.at0 = None         # the same table frozen at the start of the beat being planned (see queue())
        self.steps = []         # the readable trace: (shot, figurant, what, when)
        self.events = []        # (shot, figurant, 'react' | 'flee', t) -- what the tools check against the threat
        self.leads = _leads(ep, self.spec)
        self.notes = []

    # -- geometry -------------------------------------------------------
    def lat(self, fid):
        """the figurant's own lateral offset on its lane: two bodies on one sidewalk never share the centre line"""
        w = float(self.lanes.get('lat', .15))
        return round((2 * h32(self.seed, fid, 'lat') - 1) * w, 3)

    def lane(self, fid):
        dx = self.lat(fid)
        return [(round(x + dx, 3), z) for (x, z) in (self.lanes.get(FIGURANTS[fid]['lane']) or [])]

    def lane_clearance(self):
        """{lane: the closest a body walking that lane ever comes to a lead}. The `place()` solver only moves
        END points; a lane that runs within `clear` metres of a lead cannot be fixed by moving an endpoint, so it
        is reported here instead of being silently accepted. tools/check_background_motion.py measures the real
        thing on the sampled tracks; this is the early warning, available without rendering."""
        out = {}
        for name, pts in self.lanes.items():
            if not isinstance(pts, list) or not self.leads:
                continue
            d = min(_seg_dist(pts[i], pts[i + 1], L) for i in range(len(pts) - 1) for L in self.leads)
            out[name] = round(d, 3)
        return out

    def spot(self, fid):
        f = FIGURANTS[fid]
        h = HOME.get(f['role'])
        name = (h.get(f['lane']) if isinstance(h, dict) else h) or None
        s = (self.lanes.get('spots') or {}).get((self.spec.get('spots') or {}).get(fid, name))
        return (round(s[0] + self.lat(fid), 3), s[1]) if s else None

    def jitter(self, fid, tag, lo, hi):
        return lo + (hi - lo) * h32(self.seed, fid, tag)

    def free(self, fid, p, others):
        """p is far enough from every lead and from everybody already placed"""
        for (lx, lz) in self.leads:
            if math.hypot(p[0] - lx, p[1] - lz) < self.clear:
                return False
        for q in others:
            if math.hypot(p[0] - q[0], p[1] - q[1]) < MIN_GAP:
                return False
        return True

    def place(self, fid, p, others):
        """the first of a fixed list of candidates that clears the leads and the others: deterministic, and the
        offsets stay on the sidewalk (lateral +-.32 m, along the lane up to +-3.2 m)"""
        for dx, dz in ((0, 0), (0, 1.6), (0, -1.6), (.32, .8), (-.32, .8), (.32, -.8), (-.32, -.8), (0, 3.2), (0, -3.2)):
            q = (round(p[0] + dx, 3), round(p[1] + dz, 3))
            if self.free(fid, q, others):
                return q, (dx, dz) != (0, 0)
        return (round(p[0], 3), round(p[1], 3)), True

    def forward(self, fid, dist):
        """the point `dist` metres further along the lane, in the figurant's own direction"""
        pts = self.lane(fid)
        d = FIGURANTS[fid]['dir'] or 1
        if not pts:
            return None
        here = self.at.get(fid) or pts[0]
        best = None
        for p in pts:
            ahead = (p[1] - here[1]) * d
            if ahead > .4 and (best is None or ahead < best[0]):
                best = (ahead, p)
        if best is None:
            return None
        if best[0] <= dist * 1.6:
            return best[1]
        # the next waypoint is far: stop `dist` along the way, ON the line that joins them. Taking the far
        # waypoint's x (which is what a shorter version of this would do) would put the body off the lane
        # wherever the lane bends -- the right pavement steps in to 4.0 to pass the bus shelter.
        f = dist / max(1e-6, abs(best[1][1] - here[1]))
        return (round(here[0] + (best[1][0] - here[0]) * f, 3), round(here[1] + d * dist, 3))

    def standers(self, fid):
        """where the figurants who are NOT walking are standing right now (everybody but `fid`)"""
        return [self.at[f] for f in self.at
                if f != fid and f in FIGURANTS and FIGURANTS[f]['role'] != 'walker']

    def stop_short(self, here, p, blockers):
        """a sidewalk is 0.4 m wide: you do not walk around somebody, you squeeze past them (PASS_GAP) and, when
        even that does not fit, you stop behind them. Returns the point of the segment `here` -> `p` that keeps
        PASS_GAP from every blocker, or None when there is no room to move at all."""
        d = math.hypot(p[0] - here[0], p[1] - here[1])
        if d < 1e-6:
            return p
        lim = d
        for q in blockers:
            if _seg_dist(here, p, q) >= PASS_GAP:
                continue
            # first point of the segment that comes closer than PASS_GAP to q, minus a 15 cm margin
            for k in range(int(d / .05) + 1):
                u = k * .05
                x, z = here[0] + (p[0] - here[0]) * u / d, here[1] + (p[1] - here[1]) * u / d
                if math.hypot(x - q[0], z - q[1]) < PASS_GAP:
                    lim = min(lim, max(0., u - .15))
                    break
        if lim >= d - 1e-6:
            return p
        if lim < .35:
            return None
        return (round(here[0] + (p[0] - here[0]) * lim / d, 3), round(here[1] + (p[1] - here[1]) * lim / d, 3))

    def queue(self, fid, who, threat):
        """the order in which the figurants of ONE lane leave it, nearest to the exit first, plus the rule that
        makes a file of running bodies impossible to turn into a pile-up: nobody moves faster than the body
        directly in front of them, and nobody starts before it. -> (rank, speed, earliest start)"""
        lane = FIGURANTS[fid]['lane']
        # positions AS THEY WERE WHEN THE BEAT STARTED: `self.at` is rewritten as each figurant is planned, and
        # a rank read off a half-updated table would put two bodies at the same place in the file.
        at0 = self.at0 or self.at
        grp = [f for f in who if FIGURANTS[f]['lane'] == lane and f in at0]
        p = self.exitpoint(fid, threat) or (0., 0.)
        grp.sort(key=lambda f: (math.hypot(at0[f][0] - p[0], at0[f][1] - p[1]), f))
        order = ['run' if FIGURANTS[f]['speed'] not in ('slow', 'stroll') else 'hurry' for f in grp]
        for i in range(1, len(order)):
            if SPEED_ORDER[order[i]] > SPEED_ORDER[order[i - 1]]:
                order[i] = order[i - 1]              # stuck behind a slower body
        rank = grp.index(fid)
        return rank, order[rank], len(grp)

    def exitpoint(self, fid, threat):
        """the end of the lane FURTHEST from the threat: fleeing is causal, not a constant direction"""
        pts = self.lane(fid)
        if not pts:
            return None
        ends = [pts[0], pts[-1]]
        if threat is None:
            a = (self.lanes.get('away') or {}).get(FIGURANTS[fid]['lane'])
            return (round(a[0] + self.lat(fid), 3), a[1]) if a else ends[0]
        return max(ends, key=lambda p: math.hypot(p[0] - threat[0], p[1] - threat[1]))


def _seg_dist(a, b, p):
    """distance from point p to the segment a-b"""
    ax, az = a; bx, bz = b; px, pz = p
    dx, dz = bx - ax, bz - az
    n = dx * dx + dz * dz
    u = 0. if n < 1e-9 else max(0., min(1., ((px - ax) * dx + (pz - az) * dz) / n))
    return math.hypot(px - (ax + dx * u), pz - (az + dz * u))


def _leads(ep, spec):
    """where the real characters stand, read off the episode itself: every `actors` entry and every `walk_to`
    target of a cast member that is neither a figurant nor a creature.

    Creatures are excluded for the same reason `ShotActing.speech()` excludes them from `people`: `clear` exists
    to keep a figurant OUT OF THE LISTENER RADIUS of a speaking character, and a dog or a ghost never becomes
    anybody's interlocutor. Counting the menace as a lead would push the figurants off their own pavement to
    respect a radius that does not apply to it."""
    if spec.get('leads') is not None:
        return [tuple(p) for p in spec['leads']]
    cast = ep.get('cast') or {}
    mine = set(spec.get('troupe') if isinstance(spec.get('troupe'), list) else DEFAULT_TROUPE)
    mine |= {cid for cid, c in cast.items() if isinstance(c, dict) and c.get('kind')}
    out = []
    for sh in ep.get('shots') or []:
        for a in sh.get('actors') or []:
            if a.get('id') in mine:
                continue
            p = a.get('at')
            if isinstance(p, (list, tuple)) and len(p) == 2:
                out.append((float(p[0]), float(p[1])))
        for a in sh.get('actions') or []:
            if a.get('who') in mine or a.get('do') not in ('walk_to', 'run_to', 'sneak_to', 'go'):
                continue
            p = a.get('to')
            if isinstance(p, (list, tuple)) and len(p) == 2:
                out.append((float(p[0]), float(p[1])))
    return out


# -- the beats ------------------------------------------------------
@beat('life')
def _life(pl, fid, b, acts):
    """the street is merely living: the walkers walk their lane, the host hails his doorway, the waiters wait"""
    f = FIGURANTS[fid]
    t0 = round(pl.jitter(fid, 'go', .0, 1.1), 2)
    if f['role'] == 'walker':
        p = pl.forward(fid, float(b.get('dist', 6.5)))
        if p is None:
            return
        q, moved = pl.place(fid, p, [v for k, v in pl.at.items() if k != fid])
        here = pl.at.get(fid) or q
        short = pl.stop_short(here, q, pl.standers(fid))
        if short is None:                       # somebody is standing in the way and the sidewalk is too narrow
            acts.append({'who': fid, 'do': 'look_around', 'at': t0, 'dur': 1.8})
            pl.steps.append((b['shot'], fid, 'bloque derriere quelqu un : attend au lieu de traverser le corps', t0))
            return
        acts.append({'who': fid, 'do': 'walk_to', 'to': list(short), 'speed': f['speed'], 'at': t0})
        pl.at[fid] = short
        pl.steps.append((b['shot'], fid, f'marche jusqu a {short} ({f["speed"]})'
                         + (' [ecarte]' if moved else '') + (' [arret derriere quelqu un]' if short != q else ''), t0))
        return
    if f['role'] == 'host':
        tgt = b.get('toward') or (pl.leads[0] if pl.leads else None)
        acts.append({'who': fid, 'do': 'gesture', 'name': f['busy'], 'at': t0, 'dur': 1.6})
        if tgt is not None:
            acts.append({'who': fid, 'do': 'turn_to', 'target': list(tgt), 'at': round(t0 + .1, 2)})
            acts.append({'who': fid, 'do': 'look_at', 'target': list(tgt), 'at': round(t0 + .2, 2), 'dur': 1.8})
        pl.steps.append((b['shot'], fid, f'hele vers {tgt} (geste {f["busy"]})', t0))
        return
    # waiter: look around, one small busy gesture -- a body that is present without going anywhere
    acts.append({'who': fid, 'do': 'look_around', 'at': t0, 'dur': round(pl.jitter(fid, 'look', 1.8, 2.8), 2)})
    acts.append({'who': fid, 'do': 'gesture', 'name': f['busy'], 'at': round(t0 + .6, 2), 'dur': 1.5})
    pl.steps.append((b['shot'], fid, f'attend sur place (regarde autour, {f["busy"]})', t0))


@beat('greet')
def _greet(pl, fid, b, acts):
    """two figurants acknowledge each other: they turn, one waves, both hold the look. No line, no caption."""
    pair = list(b.get('pair') or [])
    if fid not in pair or len(pair) < 2:
        return _life(pl, fid, b, acts)
    other = pair[1] if pair[0] == fid else pair[0]
    t0 = round(float(b.get('at', .2)) + pl.jitter(fid, 'greet', .0, .35), 2)
    acts.append({'who': fid, 'do': 'turn_to', 'target': other, 'at': t0})
    acts.append({'who': fid, 'do': 'look_at', 'target': other, 'at': round(t0 + .1, 2), 'dur': float(b.get('dur', 2.2))})
    acts.append({'who': fid, 'do': 'gesture', 'name': 'wave' if pair[0] == fid else 'extend',
                 'at': round(t0 + .25, 2), 'dur': 1.4})
    pl.steps.append((b['shot'], fid, f'salue {other}', t0))


@beat('threat')
def _threat(pl, fid, b, acts):
    """ONE event, four individual answers, all inside REACT_WINDOW: startle, turn towards it, keep the fear on
    the face. The delay is the figurant's own, so nobody jumps on the same frame."""
    at = float(b.get('at', 0.))
    tgt = b.get('from')
    t0 = round(at + pl.jitter(fid, 'react', .06, REACT_WINDOW - .09), 2)
    acts.append({'who': fid, 'do': 'react', 'kind': b.get('kind', 'startle'), 'at': t0})
    if tgt is not None:
        acts.append({'who': fid, 'do': 'turn_to', 'target': list(tgt), 'at': round(t0 + .18, 2)})
        acts.append({'who': fid, 'do': 'look_at', 'target': list(tgt), 'at': round(t0 + .2, 2),
                     'dur': float(b.get('dur', 1.6))})
    acts.append({'who': fid, 'do': 'face', 'name': b.get('face', 'scared'), 'at': round(t0 + .25, 2)})
    pl.steps.append((b['shot'], fid, f'sursaute et se tourne vers {tgt}', t0))
    pl.events.append((b['shot'], fid, 'react', t0))


@beat('flee')
def _flee(pl, fid, b, acts):
    """Away from the threat, along its own lane, and out of the set. The lane is a 0.4 m corridor, so the bodies
    leave it in FILE: `Plan.queue` puts the one nearest the exit in front, forbids anybody to run faster than the
    body ahead and forbids anybody to start before it. That is what keeps four frightened people from walking
    through each other, and it costs no avoidance loop at render time."""
    tgt = tuple(b['from']) if b.get('from') else None
    p = pl.exitpoint(fid, tgt)
    if p is None:
        return
    who = [w for w in (b.get('who') or pl.troupe) if w in pl.troupe]
    rank, speed, n = pl.queue(fid, who, tgt)
    t0 = round(float(b.get('at', 0.)) + rank * float(b.get('stagger', .35))
               + pl.jitter(fid, 'flee', .0, .3), 2)
    # the exit points are staggered along the lane too: four bodies must not pile up on one waypoint
    d = 1 if p[1] >= ((pl.at0 or pl.at).get(fid) or p)[1] else -1
    p = (p[0], round(p[1] - d * rank * MIN_GAP, 3))
    q, moved = pl.place(fid, p, [v for k, v in pl.at.items() if k != fid])
    acts.append({'who': fid, 'do': 'face', 'name': 'scared', 'at': t0})
    acts.append({'who': fid, 'do': 'exit' if b.get('exit', True) else 'run_to', 'to': list(q),
                 'speed': speed, 'at': t0})
    pl.at[fid] = q
    pl.steps.append((b['shot'], fid, f'fuit vers {q} ({speed}, {rank + 1}e sur {n} dans sa voie)'
                     + (' [ecarte]' if moved else ''), t0))
    pl.events.append((b['shot'], fid, 'flee', t0))


@beat('escort')
def _escort(pl, fid, b, acts):
    """one figurant stays with a lead instead of leaving: `follow` keeps the distance by itself"""
    who = b.get('target')
    if not who:
        return
    t0 = round(float(b.get('at', 0.)) + pl.jitter(fid, 'esc', .1, .6), 2)
    acts.append({'who': fid, 'do': 'follow', 'target': who, 'dist': float(b.get('dist', 1.8)), 'at': t0})
    pl.steps.append((b['shot'], fid, f'suit {who} a {b.get("dist", 1.8)} m', t0))


@beat('hold')
def _hold(pl, fid, b, acts):
    """nothing new: the acting layer carries position, heading and face over from the previous shot by itself"""
    pl.steps.append((b['shot'], fid, 'garde sa place (continuite)', 0.))


# ------------------------------------------------------------------ the expansion itself
def plan(ep):
    """-> (Plan, {shot index: {'actors': [...], 'actions': [...]}}) without touching `ep`"""
    pl = Plan(ep, ep.get('extras') or {})
    out = {}
    if not pl.troupe:
        pl.notes.append('aucun figurant connu demande' + (f' (inconnus : {pl.unknown})' if pl.unknown else ''))
        return pl, out
    if not pl.lanes:
        pl.notes.append(f'aucune voie connue pour « {pl.table_name} » : rien ne peut etre place')
        return pl, out
    beats = sorted((dict(b) for b in (pl.spec.get('beats') or [])), key=lambda b: int(b.get('shot', 0)))
    if not beats:
        pl.notes.append('aucun temps (« beats ») demande')
    for name, d in sorted(pl.lane_clearance().items()):
        if d < pl.clear:
            pl.notes.append(f'voie « {name} » a {d:.2f} m d un premier role (< clear = {pl.clear:.2f} m) : '
                            'un figurant passera dans le rayon d ecoute de 3,5 m de ShotActing.speech()')
    first = True
    for b in beats:
        sh = int(b.get('shot', 0))
        b['shot'] = sh
        who = [f for f in (b.get('who') or pl.troupe) if f in pl.troupe]
        slot = out.setdefault(sh, {'actors': [], 'actions': []})
        if first:                                  # the entrance: one `actors` line each, then continuity takes over
            placed = []
            for fid in pl.troupe:
                f = FIGURANTS[fid]
                enter = (pl.spec.get('enter') or {}).get(fid)
                home = (round(float(enter[0]) + pl.lat(fid), 3), float(enter[1])) if enter else None
                if home is None and f['role'] in HOME:
                    home = pl.spot(fid)
                lane = pl.lane(fid)
                if home is None:
                    i = 1 if f['dir'] >= 0 else len(lane) - 2
                    home = lane[max(0, min(i, len(lane) - 1))] if lane else (0., 0.)
                    home = (home[0], round(home[1] + f['dir'] * pl.jitter(fid, 'start', -1.4, 1.4), 2))
                q, moved = pl.place(fid, home, placed)
                placed.append(q)
                pl.at[fid] = q
                facing = '+z' if f['dir'] > 0 else ('-z' if f['dir'] < 0 else ('-x' if f['lane'] == 'right' else '+x'))
                slot['actors'].append({'id': fid, 'at': list(q), 'facing': facing})
                pl.steps.append((sh, fid, f'entre en scene a {q} ({facing})' + (' [ecarte]' if moved else ''), 0.))
            first = False
        fn = BEATS.get(b.get('do', 'life'))
        if fn is None:
            pl.notes.append(f'temps inconnu « {b.get("do")} » au plan {sh} : ignore')
            continue
        pl.at0 = dict(pl.at)
        for fid in who:
            fn(pl, fid, b, slot['actions'])
        pl.at0 = None
    return pl, out


def enabled():
    """the global switch, closed from the outside while the look is not validated"""
    return os.environ.get('HSTUDIO_EXTRAS', '1').strip().lower() not in ('0', 'off', 'no', 'false')


def apply(ep):
    """opt-in expansion, in place and idempotent. No `"extras"` key (every episode shipped today) or the global
    switch closed -> the SAME object is returned and nothing at all has happened."""
    if not isinstance(ep, dict) or not ep.get('extras') or ep.get('_extras_done') or not enabled():
        return ep
    pl, per_shot = plan(ep)
    shots = ep.get('shots') or []
    for sh, add in sorted(per_shot.items()):
        if sh >= len(shots):
            pl.notes.append(f'plan {sh} absent de l episode : ignore')
            continue
        s = shots[sh]
        if add['actors']:
            have = {a.get('id') for a in (s.get('actors') or [])}
            s['actors'] = list(s.get('actors') or []) + [a for a in add['actors'] if a['id'] not in have]
        if add['actions']:
            s['actions'] = list(s.get('actions') or []) + add['actions']
    cast = ep.setdefault('cast', {})
    for fid in pl.troupe:
        f = FIGURANTS[fid]
        if fid in cast:
            continue
        look = dict(f['look'])
        if f.get('scale'):
            look['scale'] = f['scale']
        cast[fid] = look
    ep['_extras_done'] = True
    ep['_extras_plan'] = {'troupe': pl.troupe, 'lanes': pl.table_name, 'seed': pl.seed, 'clear': pl.clear,
                          'lane_clearance': pl.lane_clearance(), 'lat': {f: pl.lat(f) for f in pl.troupe},
                          'steps': [[s, f, w, t] for (s, f, w, t) in pl.steps],
                          'events': [[s, f, k, t] for (s, f, k, t) in pl.events], 'notes': pl.notes}
    return ep


def expanded(ep):
    """a copy of the episode with the figurants written out, for a tool that wants to read the real JSON"""
    return apply(copy.deepcopy(ep))


def report(ep):
    """the readable trace of the last expansion (None when nothing was expanded)"""
    return (ep or {}).get('_extras_plan')
