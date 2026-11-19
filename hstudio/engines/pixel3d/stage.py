"""PIXEL 3D side of the shared acting layer: the set seen as a World (anchors, obstacles, seats, doors, loose objects)
and the graphics of what characters change in it (doors on hinges, objects on tables)."""
import math, numpy as np
from .r3d import C, B, orient, M_DOOR
from .sets import _rot
from . import poses as P

# seat height, pelvis offset in the prop frame (lat, fwd) for each seat of a prop. Props face -z at rot 0.
SEATS = {'chair': (.47, [(0., .02)]), 'armchair': (.47, [(0., .06)]), 'sofa': (.47, [(-.55, .08), (0., .08), (.55, .08)]),
         'bench': (.47, [(-.5, .02), (.5, .02)]), 'throne': (.57, [(0., .05)]), 'school_desk': (.47, [(0., -.46)]),
         'picnic': (.05, [(0., 0.)]), 'bed': (.52, [(0., .0)]), 'bunk_bed': (.47, [(0., 0.)]), 'stool': (.62, [(0., 0.)])}

def _front_heading(rot):
    fx, fz = _rot(0., -1., int(rot)); return math.atan2(fx, fz)

class SetWorld:
    def __init__(self, st, shot=None, ep=None, set_spec=None):
        if st.base is None: st.build()
        self.st = st; sp = st.spec if hasattr(st, 'spec') else {}
        self._seats = {}; self._items = {}
        props = []
        for r in sp.get('rooms', []) or []:
            ox, oz = r.get('origin', [0, 0])
            for p in r.get('props', []) or []: props.append((p, ox, oz))
        for p in sp.get('props', []) or []: props.append((p, 0., 0.))
        count = {}
        for p, ox, oz in props:
            kind = p.get('type');
            if kind not in SEATS: continue
            h, spots = SEATS[kind]; rot = int(p.get('rot', 0)); hd = _front_heading(rot)
            if kind == 'bed': hd = _front_heading(rot + 1)
            base = p.get('id') or kind; n = count.get(base, 0); count[base] = n + 1
            name = base if n == 0 else f'{base}.{n + 1}'
            for i, (lat, fwd) in enumerate(spots):
                lx, lz = _rot(lat, -fwd, rot); se = (ox + p['at'][0] + lx, oz + p['at'][1] + lz, hd, h)
                key = name if (len(spots) == 1 or (len(spots) == 3 and i == 1) or (len(spots) == 2 and i == 0)) else f'{name}.{i + 1}'
                self._seats.setdefault(key, se); self._seats.setdefault(f'{name}.{i + 1}', se)
        for src in (sp.get('items') or [], (set_spec or {}).get('items') or [], (shot or {}).get('items') or []):
            for it in src: self._items[it.get('id', it.get('type'))] = dict(it)
        # levels (V3, composed sets): roofs, ledges, platforms; outside them the ground, or a void when it is deep
        self._walk = [(tuple(float(v) for v in w['rect']), float(w.get('y', 0.))) for w in sp.get('walkable') or []]
        self.floor_y = float(sp.get('ground_y', 0.)); self._ground_ok = bool(sp.get('ground_walkable', self.floor_y > -1.))
        self.has_levels = bool(self._walk)
        # obstacles: footprints of static boxes between ankle and head height (walls, furniture, trees...)
        self._obs = []
        for b in st.base.boxes:
            lo, hi = b.lo, b.hi
            lev = 0.
            if self._walk:                                    # height above the level the box stands on
                lev = self.ground_y(float(lo[0] + hi[0]) / 2, float(lo[2] + hi[2]) / 2)
                lev = float(lo[1]) if lev is None else lev    # over the void (an edge, a parapet): it stands on its own bottom
            if hi[1] < lev + .18 or lo[1] > lev + 1.5 or (hi[1] - lo[1]) < .04: continue
            if (hi[0] - lo[0]) * (hi[2] - lo[2]) > 400: continue
            self._obs.append((float(lo[0]), float(lo[2]), float(hi[0]), float(hi[2])))
        rects = getattr(st, 'room_rects', None) or []
        if self._walk:
            self._bounds = (min(r[0] for r, _ in self._walk) - 3, min(r[1] for r, _ in self._walk) - 3, max(r[2] for r, _ in self._walk) + 3, max(r[3] for r, _ in self._walk) + 3)
        elif sp.get('rooms') and not sp.get('outdoor'):
            xs = [r.get('origin', [0, 0])[0] - r['size'][0] / 2 for r in sp['rooms']] + [r.get('origin', [0, 0])[0] + r['size'][0] / 2 for r in sp['rooms']]
            zs = [r.get('origin', [0, 0])[1] for r in sp['rooms']] + [r.get('origin', [0, 0])[1] + r['size'][1] for r in sp['rooms']]
            self._bounds = (min(xs) - .5, min(zs) - .5, max(xs) + .5, max(zs) + .5)
        else:
            pts = list(st.anchors.values()) or [(0, 0)]
            self._bounds = (min(p[0] for p in pts) - 10, min(p[1] for p in pts) - 8, max(p[0] for p in pts) + 10, max(p[1] for p in pts) + 12)
        self.doors = {}
        for did, di in (getattr(st, 'door_info', {}) or {}).items(): self.doors[did] = self._door(di)

    def anchor(self, name):
        a = self.st.anchors.get(name)
        if a is None:
            for k, v in self.st.anchors.items():
                if k.lower() == str(name).lower() or k.split('.')[-1] == name: return v
        if a is None and name in self._seats: return self._seats[name][:2]
        return a
    def obstacles(self): return self._obs
    def bounds(self): return self._bounds
    def ground_y(self, x, z):
        """height of the surface under (x, z): the highest level there, else the ground, else None (a void)"""
        best = None
        for (x0, z0, x1, z1), y in self._walk:
            if x0 <= x <= x1 and z0 <= z <= z1 and (best is None or y > best): best = y
        if best is None and (self._ground_ok or not self._walk): best = self.floor_y
        return best
    def seat(self, name): return self._seats.get(name)
    def item(self, name):
        it = self._items.get(name)
        if it is None: return None
        a = it.get('at', [0, .8, 0])
        if len(a) == 2: a = [a[0], .8, a[1]]
        return tuple(float(v) for v in a)
    def items(self): return self._items
    def door(self, name): return self.doors.get(name)

    def _door(self, di):
        wall = di['wall']; hx, hz = di['hinge']; w = di['width']
        normal = {'S': (0, 1), 'N': (0, -1), 'W': (1, 0), 'E': (-1, 0)}[wall]
        yaw0 = {'S': 0., 'N': 0., 'W': -math.pi / 2, 'E': -math.pi / 2}[wall]
        sgn = {'S': -1, 'N': 1, 'W': 1, 'E': -1}[wall]
        along = (math.cos(yaw0), -math.sin(yaw0))                      # local +x (hinge -> free end) when closed
        def yaw(a): return yaw0 + sgn * 1.45 * a
        def handle(a):
            y = yaw(a); c, s = math.cos(y), math.sin(y)
            side = math.sin(yaw0) * normal[0] + math.cos(yaw0) * normal[1]       # local +z towards the room?
            lx, lz = w - .1, .07 * (1 if side > 0 else -1)
            return (hx + c * lx + s * lz, 1.0, hz - s * lx + c * lz)
        free = (hx + along[0] * w, hz + along[1] * w)
        front = (free[0] + along[0] * .22 + normal[0] * .55, free[1] + along[1] * .22 + normal[1] * .55)
        facing = math.atan2(-normal[0], -normal[1])
        return dict(id=di['id'], box=di['box'], hinge=(hx, hz), width=w, color=di['color'], yaw=yaw, handle=handle, handle_front=front, facing=facing)

    def door_boxes(self, did, angle):
        d = self.doors[did]; y = d['yaw'](angle)
        bx = [B((0., 0., -.03), (d['width'], 2.08, .06), d['color'], mat=M_DOOR),
              C((d['width'] - .1, 1.0, .06), (.1, .04, .05), (200, 196, 180)), C((d['width'] - .1, 1.0, -.06), (.1, .04, .05), (200, 196, 180))]
        return orient(bx, y, (d['hinge'][0], 0., d['hinge'][1]))

    def item_boxes(self, name, where=None, lights=None):
        """an object lying in the set (not held): at its place, or where it was put down"""
        it = self._items.get(name) or {}
        p = where if where is not None else self.item(name)
        if p is None: return []
        rot = float(it.get('yaw', 0.))
        bx = P.held_item(it.get('type', name), (0., 0., 0.), 1, {}, lights, tuple(it['color']) if it.get('color') else None)
        if not bx: return []
        lo = min(float(b.lo[1]) for b in bx)
        return orient(bx, rot, (p[0], p[1] - lo, p[2]))
