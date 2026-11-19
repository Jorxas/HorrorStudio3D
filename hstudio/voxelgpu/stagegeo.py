"""The geometry of a place, as DATA the director can check before anything is drawn.

Why this exists. The remakes of the first unified-engine mission wrote every shot on its own: an actor was placed at hand-typed
coordinates at the start of each shot (`tracks`, one key at t=0), nothing remembered where he stood in the shot before, and the
world handed to the planner (`worlds.VoxWorld`) had no obstacle and no wall: `obstacles()` returned `[]`. So a clerk could stand
inside a counter, walk out through a glass wall between two cuts, and appear next to the monster. The first engine (pixel3d + the
régie, `acting/timeline.py`) did not have that defect because its `ShotActing` is given the state the previous shot ended in
(`start_states`), plans paths on a grid built from the world's real `obstacles()`, and knows doors, seats and items.

This module gives the voxel worlds that same knowledge, once, in one place:
  * solids      boxes that stop a body (walls, shelves, counter, pumps, car...) and/or the view; glass stops a body but not the view
  * portals     doorways in walls; a portal is a wall piece while it is closed and a gap while it is open, depending on TIME
  * zones       named areas (shop, reserve, lot...) so "inside / outside" is a question with an answer
  * marks       named standing places with a heading, used by the story instead of raw coordinates
  * landmarks   boxes the camera is asked to show (the car, the shop front, the breaker panel...)

Coordinates are the painter's (A): x along the street, z towards the lot (the camera side), y up, metres, local to the world.
The numbers are read from `voxelgpu_js/engine/sets4b.js` (the shop, counter, shelves, car) and `reserve.js` (the back room);
`tools/check_blocking.py` greps those constants so the two cannot drift apart without a test failing.
Nothing here is random and nothing reads a clock.
"""
import math
import numpy as np
from ..acting.timeline import Grid, World

BODY_R = {'human': .28, 'faceless': .34}


class Solid:
    """an axis-aligned box. body: stops walking; view: stops sight lines (glass: body yes, view no)"""
    __slots__ = ('id', 'x0', 'z0', 'x1', 'z1', 'y0', 'y1', 'body', 'view', 'kind')

    def __init__(self, id, x0, z0, x1, z1, y0=0., y1=3.2, body=True, view=True, kind='wall'):
        self.id = id; self.x0, self.z0, self.x1, self.z1 = min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1)
        self.y0, self.y1 = y0, y1; self.body, self.view, self.kind = body, view, kind

    def rect(self): return (self.x0, self.z0, self.x1, self.z1)

    def contains(self, x, z, m=0.): return self.x0 - m <= x <= self.x1 + m and self.z0 - m <= z <= self.z1 + m


class Portal:
    """a doorway: a wall piece (rect) while closed. `open_at(t)` says whether it is a gap at time t. `swing` is how far the leaf is open (0..1)
    as a table of (t, value) in film time, the same table the painter reads (env key), so the picture and the check agree."""

    def __init__(self, id, rect, a, b, y1=2.25, swing=None, locked=False, leaf='x'):
        self.id = id; self.rect = rect; self.a, self.b = a, b; self.y1 = y1; self.swing = swing or [[0., 0.]]; self.locked = locked; self.leaf = leaf

    def amount(self, t):
        s = self.swing
        if t <= s[0][0]: return s[0][1]
        for i in range(len(s) - 1):
            if t < s[i + 1][0]:
                k = (t - s[i][0]) / max(1e-6, s[i + 1][0] - s[i][0]); return s[i][1] + (s[i + 1][1] - s[i][1]) * k
        return s[-1][1]

    def open_at(self, t): return self.amount(t) >= .6          # a body fits through when the leaf is wide open

    def center(self):
        x0, z0, x1, z1 = self.rect; return ((x0 + x1) / 2, (z0 + z1) / 2)


class _GridWorld(World):
    def __init__(self, bounds, rects, geo=None):
        super().__init__({}, bounds); self._r = rects; self._geo = geo
        self.has_levels = bool(geo is not None and geo.floors)            # levels: the grid refuses voids and steps over 35 cm (acting.timeline.Grid)
    def obstacles(self): return self._r
    def ground_y(self, x, z): return self._geo.ground_y(x, z) if self._geo is not None else 0.


class Floor:
    """a horizontal walkable surface at height y (a kerb, a loading dock, the bus floor); `void` = nothing to stand on (a pit, the water)"""
    __slots__ = ('x0', 'z0', 'x1', 'z1', 'y', 'kind', 'void')

    def __init__(self, x0, z0, x1, z1, y=0., kind='floor', void=False):
        self.x0, self.z0, self.x1, self.z1 = min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1); self.y = float(y); self.kind = kind; self.void = void

    def contains(self, x, z): return self.x0 <= x <= self.x1 and self.z0 <= z <= self.z1


class Frame:
    """The transform between a world's local coordinates and the film's (or another world's) coordinates: a translation and a yaw (the painter places every
    world at an `origin` with `W.at(x, y, z)` and no rotation, so the default is a pure translation; `yaw` is there for places that are rotated).
    `to_world(x, z)` and `to_local(x, z)` are exact inverses; headings add the yaw. Used to ask a contract the right question when its rows are not in the
    geometry's own frame, and to catch rows that are in NO frame (absolute coordinates where local ones are expected)."""
    __slots__ = ('dx', 'dy', 'dz', 'yaw')

    def __init__(self, dx=0., dz=0., yaw=0., dy=0.): self.dx, self.dy, self.dz, self.yaw = float(dx), float(dy), float(dz), float(yaw)

    def to_world(self, x, z):
        c, s = math.cos(self.yaw), math.sin(self.yaw); return (self.dx + x * c + z * s, self.dz - x * s + z * c)

    def to_local(self, x, z):
        c, s = math.cos(self.yaw), math.sin(self.yaw); x -= self.dx; z -= self.dz; return (x * c - z * s, x * s + z * c)

    def heading_to_world(self, h): return h + self.yaw
    def heading_to_local(self, h): return h - self.yaw

    @staticmethod
    def of(d):
        if d is None: return Frame()
        if isinstance(d, Frame): return d
        return Frame(d.get('dx', 0.), d.get('dz', 0.), d.get('yaw', 0.), d.get('dy', 0.))


class Geo:
    def __init__(self, name, bounds):
        self.name = name; self.bounds = bounds; self.solids = []; self.portals = {}; self.zones = {}; self.marks = {}; self.landmarks = {}
        self.items = {}; self._grids = {}; self.floors = []; self.base_y = 0.; self.frame = Frame()

    # ---- declaration
    def solid(self, *a, **k): s = Solid(*a, **k); self.solids.append(s); return s
    def portal(self, p): self.portals[p.id] = p; return p
    def zone(self, name, rects, indoor=False): self.zones[name] = dict(rects=rects, indoor=indoor)
    def mark(self, name, x, z, yaw=0.): self.marks[name] = (x, z, yaw)
    def floor(self, *a, **k): f = Floor(*a, **k); self.floors.append(f); self._grids.clear(); return f

    def ground_y(self, x, z):
        """height of the ground at (x, z): the highest floor that holds the point, `base_y` if none, None over a void"""
        best = None
        for f in self.floors:
            if f.contains(x, z):
                if f.void: return None
                best = f.y if best is None else max(best, f.y)
        return self.base_y if best is None else best

    # ---- queries
    def zone_at(self, x, z):
        best = None
        for n, zn in self.zones.items():
            for (x0, z0, x1, z1) in zn['rects']:
                if x0 <= x <= x1 and z0 <= z <= z1:
                    a = (x1 - x0) * (z1 - z0)
                    if best is None or a < best[0]: best = (a, n)       # the smallest zone that holds the point
        return best[1] if best else None

    def indoor(self, x, z):
        z_ = self.zone_at(x, z); return bool(z_ and self.zones[z_]['indoor'])

    def closed_portals(self, t):
        return [p for p in self.portals.values() if not p.open_at(t)]

    def body_rects(self, t=None, include_portals=True):
        """rects that stop a walking body at time t (None = every portal closed)"""
        r = [s.rect() for s in self.solids if s.body]
        if include_portals:
            r += [p.rect for p in self.portals.values() if t is None or not p.open_at(t)]
        return r

    def hit_body(self, x, z, r, t=None, skip_portals=False, y=None, h=None):
        """the first body solid / closed portal the disc (x, z, r) overlaps, or None. With `y` (feet height) and `h` (body height) a solid that ends under the feet
        or starts over the head does not count (a beam over a doorway, a rug); without them the historical 2D test."""
        for s in self.solids:
            if y is not None and (s.y1 <= y + .05 or s.y0 >= y + (1.8 if h is None else h)): continue
            if s.body and s.contains(x, z, r - 1e-6) and _disc_rect(x, z, r, s.rect()): return s.id
        if skip_portals: return None
        for p in self.portals.values():
            if (t is None or not p.open_at(t)) and _disc_rect(x, z, r, p.rect): return p.id
        return None

    def seg_free(self, a, b, r, t=None, step=.04, skip_portals=False):
        """no body solid between a and b for a disc of radius r (sampled every 4 cm: thinner than any wall here)"""
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
        for k in range(n + 1):
            x = a[0] + (b[0] - a[0]) * k / n; z = a[1] + (b[1] - a[1]) * k / n
            h = self.hit_body(x, z, r, t, skip_portals)
            if h: return h
        return None

    def grid(self, r, open_portals=(), cell=.12):
        """the planner's grid (acting.timeline.Grid) for a body radius, with the named portals open and every other closed"""
        key = (round(r, 3), tuple(sorted(open_portals)), cell)
        if key not in self._grids:
            rects = [s.rect() for s in self.solids if s.body] + [p.rect for p in self.portals.values() if p.id not in open_portals]
            self._grids[key] = Grid(_GridWorld(self.bounds, rects, self), radius=r - 1e-3, cell=cell)
        return self._grids[key]

    def view_blockers(self, y_cap=None):
        return [s for s in self.solids if s.view]

    def ray(self, p0, p1, ignore=(), t=None):
        """the first view-blocking solid met by the 3D segment p0 -> p1 (slab test), or None. Glass lets the view through. With `t` (film time) a door that is
        CLOSED at that moment also blocks the view (a closed door is a wall; without `t` portals are ignored, as before)."""
        d = [p1[i] - p0[i] for i in range(3)]; best = None
        boxes = [(s.id, s.x0, s.y0, s.z0, s.x1, s.y1, s.z1) for s in self.solids if s.view and s.id not in ignore]
        if t is not None: boxes += [(q.id, q.rect[0], 0., q.rect[1], q.rect[2], q.y1, q.rect[3]) for q in self.portals.values() if q.id not in ignore and not q.open_at(t)]
        for (sid, x0, y0, z0, x1, y1, z1) in boxes:
            t0, t1 = 0., 1.
            for lo, hi, o, dd in ((x0, x1, p0[0], d[0]), (y0, y1, p0[1], d[1]), (z0, z1, p0[2], d[2])):
                if abs(dd) < 1e-9:
                    if o < lo or o > hi: t0 = 2.; break
                else:
                    a, b = (lo - o) / dd, (hi - o) / dd
                    if a > b: a, b = b, a
                    t0, t1 = max(t0, a), min(t1, b)
                    if t0 > t1: break
            if t0 <= t1 and t0 <= 1.0:
                if best is None or t0 < best[0]: best = (t0, sid)
        return best[1] if best else None

    def ray_dist(self, p0, p1, ignore=()):
        """distance (m) along p0 -> p1 to the first view-blocking solid that is not a ceiling slab, or None"""
        d = [p1[i] - p0[i] for i in range(3)]; L = math.sqrt(sum(v * v for v in d)) or 1.; best = None
        for s in self.solids:
            if not s.view or s.id in ignore or s.kind == 'ceiling': continue
            t0, t1 = 0., 1.
            for lo, hi, o, dd in ((s.x0, s.x1, p0[0], d[0]), (s.y0, s.y1, p0[1], d[1]), (s.z0, s.z1, p0[2], d[2])):
                if abs(dd) < 1e-9:
                    if o < lo or o > hi: t0 = 2.; break
                else:
                    a, b = (lo - o) / dd, (hi - o) / dd
                    if a > b: a, b = b, a
                    t0, t1 = max(t0, a), min(t1, b)
                    if t0 > t1: break
            if t0 <= t1 and t0 <= 1.0 and (best is None or t0 < best): best = t0
        return None if best is None else best * L

    def solid_at_point(self, p, m=0.):
        """a view/body solid that contains the 3D point (camera inside a wall, a character's head inside a shelf...)"""
        for s in self.solids:
            if s.x0 - m <= p[0] <= s.x1 + m and s.z0 - m <= p[2] <= s.z1 + m and s.y0 - m <= p[1] <= s.y1 + m and (s.body or s.view): return s.id
        for q in self.portals.values():
            x0, z0, x1, z1 = q.rect
            if x0 - m <= p[0] <= x1 + m and z0 - m <= p[2] <= z1 + m and 0 <= p[1] <= q.y1 and not q.open_at(0.): return q.id
        return None

    def seg_hits_body3(self, p0, p1, ignore=(), t=None, end_margin=0.):
        """the first body solid or closed portal met by the 3D segment p0 -> p1 (slab test), or None; the last `end_margin` metres of the segment are not tested
        (a hand that ends ON a surface touches it, it does not go through it). Glass counts: a hand does not go through a window."""
        d = [p1[i] - p0[i] for i in range(3)]; L = math.sqrt(sum(v * v for v in d))
        if L < 1e-9: return None
        tmax = max(0., 1. - end_margin / L); boxes = [(s.id, s.x0, s.y0, s.z0, s.x1, s.y1, s.z1) for s in self.solids if s.body and s.id not in ignore]
        boxes += [(q.id, q.rect[0], 0., q.rect[1], q.rect[2], q.y1, q.rect[3]) for q in self.portals.values() if q.id not in ignore and (t is None or not q.open_at(t))]
        best = None
        for (sid, x0, y0, z0, x1, y1, z1) in boxes:
            t0, t1 = 0., tmax
            for lo, hi, o, dd in ((x0, x1, p0[0], d[0]), (y0, y1, p0[1], d[1]), (z0, z1, p0[2], d[2])):
                if abs(dd) < 1e-9:
                    if o < lo or o > hi: t0 = 2.; break
                else:
                    a, b = (lo - o) / dd, (hi - o) / dd
                    if a > b: a, b = b, a
                    t0, t1 = max(t0, a), min(t1, b)
                    if t0 > t1: break
            if t0 <= t1 and t0 <= tmax and (best is None or t0 < best[0]): best = (t0, sid)
        return best[1] if best else None

    def reachable_from(self, start, r, open_portals=()):
        """the grid cells a body of radius r can walk to from `start` (flood fill on the planner's own grid) -> (grid, boolean array)"""
        g = self.grid(r, tuple(open_portals)); s = g.cell(*start)
        if not g.free(*s): s = g.cell(*g.nearest_free(*start))
        seen = np.zeros_like(g.block); stack = [s]; seen[s] = True
        while stack:
            i, j = stack.pop()
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (i + di, j + dj)
                if g.free(*n) and not seen[n] and g.step_ok((i, j), n): seen[n] = True; stack.append(n)
        return g, seen

    def can_walk(self, a, b, r, open_portals=()):
        """True if a body of radius r can walk from a to b with the given portals open (and every other closed)"""
        g, seen = self.reachable_from(a, r, open_portals); c = g.cell(*b)
        if not g.free(*c): c = g.cell(*g.nearest_free(*b))
        return bool(seen[c])

    def validate(self, radii=None):
        """The geometry checks ITSELF, before any film uses it: every named mark is inside the bounds, not inside a solid for a human body, and every mark can be
        reached from every other once all the doors are open; every doorway is wide enough for the biggest body; every portal joins zones that exist.
        Returns [(code, message)], empty if sound."""
        radii = radii or BODY_R; v = []; rmax = max(radii.values()); rh = radii['human']
        x0, z0, x1, z1 = self.bounds; bad = set()
        for n, (x, z, yaw) in self.marks.items():
            if not (x0 <= x <= x1 and z0 <= z <= z1): v.append(('repère_hors_lieu', f"le repère {n!r} ({x:.2f}, {z:.2f}) est hors des limites du lieu")); bad.add(n)
            h = self.hit_body(x, z, rh - .03, None, skip_portals=True)
            if h: v.append(('repère_dans_solide', f"le repère {n!r} ({x:.2f}, {z:.2f}) est dans {h!r} : personne ne peut s'y tenir")); bad.add(n)
        names = [n for n in self.marks if n not in bad]
        if names:
            ref = names[0]; allp = tuple(self.portals)
            for n in names[1:]:
                if not self.can_walk(self.marks[ref][:2], self.marks[n][:2], rh, allp): v.append(('repère_isolé', f"le repère {n!r} n'est pas joignable à pied depuis {ref!r}, même portes ouvertes"))
        for q in self.portals.values():
            a0, c0, a1, c1 = q.rect; width = max(a1 - a0, c1 - c0)
            if width < 2 * rmax + .08: v.append(('porte_étroite', f"la porte {q.id!r} fait {width:.2f} m de large : le plus gros corps ({2 * rmax:.2f} m) n'y passe pas"))
            for side in (q.a, q.b):
                if side not in self.zones: v.append(('porte_zone', f"la porte {q.id!r} relie la zone {side!r} qui n'existe pas"))
        for s in self.solids:
            if s.x1 - s.x0 < 1e-6 or s.z1 - s.z0 < 1e-6 or s.y1 <= s.y0: v.append(('solide_dégénéré', f"le solide {s.id!r} n'a pas de volume"))
        return v

    def land(self, name):
        if name not in self.landmarks: raise KeyError(f'repère inconnu : {name!r} (connus : {", ".join(self.landmarks)})')
        return self.landmarks[name]


def _disc_rect(x, z, r, rc):
    cx = min(max(x, rc[0]), rc[2]); cz = min(max(z, rc[1]), rc[3])
    return (x - cx) ** 2 + (z - cz) ** 2 < r * r


# ------------------------------------------------------------------------------------------------------------------- the station
def station(door_swings=None):
    """La station-service : supérette (sets4b.js), arrière-boutique (reserve.js), auvent et pompes, parking.
    `door_swings` = {portal id: [[t, amount], ...]} (the same tables the painter reads as env keys)."""
    ds = door_swings or {}
    g = Geo('station', (-24., -20., 24., 32.))
    X0, X1, Z0, Z1, HH = -4.5, 4.5, -7., 3.5, 3.2
    RX0, RX1, RZ0 = .6, 4.4, -12.0                    # back room: interior x 0.6..4.4, z -12.0..-7.2 (reserve.js)
    # --- the shop shell (sets4b.js: walls .2 thick, glass front on z = 3.5, the back wall on z = -7.1)
    g.solid('mur_ouest', X0 - .2, Z0 - .2, X0, Z1 + .05, 0, HH)
    g.solid('mur_est', X1, Z0 - .2, X1 + .2, Z1 + .05, 0, HH)
    g.solid('mur_fond_g', X0 - .2, Z0 - .2, 3.0, Z0, 0, HH)
    g.solid('mur_fond_d', 3.9, Z0 - .2, X1 + .2, Z0, 0, HH)
    g.solid('linteau_fond', 3.0, Z0 - .2, 3.9, Z0, 2.25, HH, body=False)
    g.solid('vitrine', X0 - .2, Z1 - .05, X1 + .2, Z1 + .05, 0, HH, view=False, kind='glass')             # the whole glass front, door included
    g.solid('plafond_boutique', X0 - .2, Z0 - .2, X1 + .2, 7.5, HH, HH + .12, body=False, kind='ceiling')   # also the porch roof out to z = 7.5
    g.solid('facade_haut', X0 - .2, Z1 - .15, X1 + .2, Z1 + .2, HH, HH + 1.3, body=False, kind='ceiling')
    g.solid('batiment_ouest', -7.9, -8.25, X0 - .2, 3.25, 0, 4.4)
    g.solid('batiment_est', X1 + .2, -8.25, 7.9, 3.25, 0, 4.4)
    # --- the entrance (double glass door, centre of the front): closed and locked all along this film
    g.portal(Portal('entree', (-.9, Z1 - .1, .9, Z1 + .1), 'boutique', 'parking', y1=2.3, swing=ds.get('entree'), locked=True, leaf='z'))
    # --- the back room
    g.solid('res_ouest', RX0 - .2, RZ0 - .2, RX0, Z0, 0, 2.8)
    g.solid('res_nord', RX0 - .2, RZ0 - .2, RX1 + .2, RZ0, 0, 2.8)
    g.solid('res_est_s', RX1, RZ0, RX1 + .2, -11.55, 0, 2.8)
    g.solid('res_est_n', RX1, -10.45, RX1 + .2, Z0, 0, 2.8)
    g.solid('res_toit', RX0 - .2, RZ0 - .2, RX1 + .2, Z0, 2.8, 2.95, body=False, kind='ceiling')
    g.portal(Portal('reserve', (3.0, Z0 - .2, 3.9, Z0), 'boutique', 'reserve', y1=2.25, swing=ds.get('reserve'), leaf='z'))
    g.portal(Portal('service', (RX1, -11.55, RX1 + .2, -10.45), 'reserve', 'arriere', y1=2.2, swing=ds.get('service'), leaf='x'))
    # --- shop furniture (sets4b.js shelfUnit / fridges / counter), with the half-thickness of their products
    g.solid('rayon_1', -3.0, -5.65, -2.2, -.55, 0, 1.95)
    g.solid('rayon_2', -1.0, -5.65, -.2, -.55, 0, 1.95)
    g.solid('rayon_3', 1.0, -5.65, 1.8, -1.55, 0, 1.95)
    g.solid('rayon_mur', X0, -6.65, X0 + .45, 2.05, 0, 1.95)
    g.solid('frigos', -4.03, Z0, 2.43, Z0 + .72, 0, 2.1)
    g.solid('comptoir_a', 2.35, .8, 4.25, 1.6, 0, 1.1)
    g.solid('comptoir_b', 3.55, -1.5, X1, .85, 0, 1.1)
    # --- the back room's furniture (reserve.js)
    g.solid('etagere_est', RX1 - .55, -10.2, RX1, -8.5, 0, 2.0)
    g.solid('etabli', RX0, -12.0, RX0 + .65, -10.7, 0, .95)
    g.solid('tableau_elec', RX0, -9.55, RX0 + .22, -8.45, 0, 2.0, body=False)        # the breaker board is flat on the west wall: a lump, not an obstacle
    g.solid('fut', 1.55, -9.0, 2.05, -8.5, 0, .9)
    # --- outside: pumps, canopy posts, car, lamp posts, price pole
    for px in (-12.5, -9.5): g.solid(f'pompe_{px:g}', px - .3, 11.75, px + .3, 12.25, 0, 1.7)
    for (px, pz) in ((-13.5, 10.), (-8.5, 10.), (-13.5, 14.), (-8.5, 14.)): g.solid(f'poteau_{px:g}_{pz:g}', px - .15, pz - .15, px + .15, pz + .15, 0, 4.0)
    g.solid('auvent', -15., 9., -7., 15., 4.0, 4.5, body=False, kind='ceiling')
    cx, cz = CAR_AT
    g.solid('voiture', cx - 1.46, cz - 2.37, cx + 1.46, cz + 2.37, 0, 1.25, kind='car')
    for i, (lx, lz) in enumerate(((-7., 20.), (8., 18.), (18., 6.))): g.solid(f'lampadaire_{i}', lx - .1, lz - .1, lx + .1, lz + .1, 0, 6.4)
    g.solid('poteau_prix', -6.11, 14.09, -5.89, 14.31, 0, 6.8)
    # --- zones (smallest wins)
    g.zone('boutique', [(X0, Z0, X1, Z1)], True)
    g.zone('reserve', [(RX0, RZ0, RX1, Z0)], True)
    g.zone('parking', [(-24., Z1, 24., 32.)])
    g.zone('cote_est', [(7.9, -14., 24., Z1)])
    g.zone('cote_ouest', [(-24., -14., -7.9, Z1)])
    g.zone('arriere', [(-24., -20., 24., -7.4)])
    g.zone('sous_porche', [(X0, Z1, X1, 7.5)])
    g.zone('pompes', [(-15., 9., -7., 15.)])
    # --- named standing places (x, z, yaw; yaw 0 faces +z = the lot)
    for n, (x, z, yaw) in {
        'caisse': (2.9, .2, .67), 'porte_dedans': (.25, 3.06, 0.), 'comptoir_clients': (2.62, 1.95, math.pi), 'allee_est': (2.7, -.2, 0.), 'affiche': (3.55, -3.4, math.pi / 2),
        'fenetre_est': (2.3, 2.95, 0.), 'devant_reserve': (3.45, -6.2, math.pi), 'seuil_reserve': (3.45, -6.7, math.pi), 'dans_reserve': (3.2, -8.3, 0.),
        'tableau_elec': (1.28, -9.2, -math.pi / 2), 'porte_service_int': (3.9, -11., math.pi / 2),
        'parking_loin': (.4, 9.5, math.pi), 'vitre': (.4, 3.95, math.pi), 'vitre_porte_est': (1.75, 4.05, math.pi),
        'service_dehors': (5.1, -11., -math.pi / 2), 'derriere_porte': (4.05, -7.95, 0.), 'cote_est_sud': (9., 5.2, 0.), 'cote_est_nord': (9., -11., 0.),
        'pompe_4': (-9.5, 10.6, math.pi),
    }.items(): g.mark(n, x, z, yaw)
    # --- what the camera is asked to show: (x0, y0, z0, x1, y1, z1)
    g.landmarks.update({
        'voiture': (cx - 1.46, 0., cz - 2.37, cx + 1.46, 1.25, cz + 2.37), 'vitrine': (X0, 0., Z1, X1, HH, Z1), 'entree': (-.9, 0., Z1, .9, 2.3, Z1),
        'boutique': (X0, 0., Z0, X1, HH, Z1), 'pompes': (-13.2, 0., 11.7, -8.8, 1.7, 12.3), 'auvent': (-15., 3.9, 9., -7., 4.5, 15.),
        'porte_reserve': (3.0, 0., Z0 - .05, 3.9, 2.25, Z0 + .05), 'comptoir': (2.35, 0., -1.5, X1, 1.1, 1.6), 'enseigne': (-2.6, 3.3, 3.5, 2.6, 4.3, 3.9),
        'tableau_elec': (RX0, .9, -9.5, RX0 + .2, 2.0, -8.5), 'porte_service': (RX1, 0., -11.55, RX1 + .2, 2.2, -10.45), 'affiche': (4.4, 1.0, -3.8, X1, 2.0, -3.0),
        'reserve': (RX0, 0., RZ0, RX1, 2.8, Z0), 'dalle': (2.2, 3.05, -.2, 3.0, 3.2, .6), 'prix': (-6.55, 6.2, 13.9, -5.45, 7.8, 14.3),
    })
    g.items.update({'torche': dict(at=(3.0, 1.09, 1.58), zone='boutique')})
    return g


CAR_AT = (4.2, 7.3)            # the car, 3 m from the entrance in front (the narration says "trois mètres d'obscurité"); read by sets4b.js through env.car_at


# ------------------------------------------------------------------------------------------------------------------------------- the bus (levels only)
def bus():
    """« Le bus de nuit » (horror_kit.js, WORLDS['bus']): the floor of the bus is at y = 0 over x[-1.4, 1.4] z[-12.4, 0.4]; the ground outside is 0.96 m lower
    (`note` of worlds.py: « plancher y=0, sol extérieur y=-0.96 »). Only the LEVELS are described (no walls, doors or seats are known yet): enough to ask a contract whether
    somebody stands on the right ground, not whether he walked through a window."""
    g = Geo('bus', (-30., -20., 30., 10.)); g.base_y = -.96
    g.floor(-1.4, -12.4, 1.4, .4, y=0., kind='plancher')
    return g


def _demo(doors=None):
    from .placesgeo import demo_world
    return demo_world(doors)


GEOS = {'station': station, 'bus': bus, 'demo': _demo}          # the places that have a geometry (blocking.geo_of and the contract audits read this)
