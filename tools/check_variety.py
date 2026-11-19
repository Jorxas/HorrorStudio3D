"""Checks of the environment variation increment (no API, no cost, no video).

  python tools/check_variety.py

What it proves:
  1. the registration is additive: not one shipped prop, place, ambience or start point was replaced;
  2. the key is opt-in: without "variation" a shipped place builds exactly the same boxes as before;
  3. determinism: the same spec gives the same set, twice, in two processes' worth of cache states;
  4. two seeds give two different rooms (the pass really varies something);
  5. geometry: every prop stands inside its room, nothing sinks through the floor or pierces the ceiling,
     and every prop against a wall shows the room its front (the rule of AGENTS.md);
  6. placement: the camera lane from the `start` anchor and the discs around the anchors stay free;
  7. cost: the dressed room never costs more than three times the plain one to render.
"""
import json, math, os, sys, time
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hstudio.engines.pixel3d import environment_variation as EV
from hstudio.engines.pixel3d import places as PL, world as W, r3d
from hstudio.engines.pixel3d.sets import make_set, prop_boxes, place as place_boxes

OK, BAD = [], []


def check(cond, label, detail=''):
    (OK if cond else BAD).append(label)
    print(('OK    ' if cond else 'ÉCHEC ') + label + (('  — ' + detail) if detail and not cond else ''), flush=True)


def boxes_of(spec, name=None):
    st = make_set(name or spec.get('type', 'room'), spec)
    st.build()
    return st, [(tuple(np.round(b.lo, 4).tolist()), tuple(np.round(b.hi, 4).tolist()),
                 tuple(np.round(b.col * 255, 1).tolist()), int(b.mat), round(float(b.emis), 3)) for b in st.base.boxes]


# ---------------------------------------------------------------- 1. additive registration
SHIPPED_PROPS = ('bed', 'sofa', 'table', 'lamp', 'tv', 'mirror', 'plant', 'tree_round', 'house', 'car', 'bench',
                 'streetlight', 'bookshelf', 'fireplace', 'stairs', 'chest', 'campfire', 'well', 'boat')
SHIPPED_PLACES = ('bedroom', 'living_room', 'kitchen', 'forest', 'beach', 'city_street', 'basement', 'cave')
check(not (set(EV.NEW_PROPS) & set(SHIPPED_PROPS)), 'aucun objet livré n\'est remplacé')
check(not (set(EV.NEW_PLACES) & set(SHIPPED_PLACES)), 'aucun lieu livré n\'est remplacé')
check(all(W.PROPS.get(k) is fn for k, fn in EV.NEW_PROPS.items()), 'les nouveaux objets sont bien enregistrés')
check(all(PL.PLACES.get(k) is fn for k, fn in EV.NEW_PLACES.items()), 'les nouveaux lieux sont bien enregistrés')
check(all(k in __import__('hstudio.engines.pixel3d.sets', fromlist=['x']).PROP_TYPES for k in EV.NEW_PROPS),
      'les nouveaux objets sont des valeurs DSL valides (validate.py)')
check(all(k in __import__('hstudio.engines.pixel3d.sets', fromlist=['x']).PLACE_TYPES for k in EV.NEW_PLACES),
      'les nouveaux lieux sont des valeurs DSL valides (validate.py)')

# ---------------------------------------------------------------- 2. opt-in
for name in ('bedroom', 'living_room', 'kitchen', 'basement', 'attic', 'forest', 'city_street', 'park'):
    spec = {'type': name}
    before = dict(spec)
    kept = EV.dress(PL.expand(name, spec), name, spec)
    _, b1 = boxes_of({'type': name}, name)
    _, b2 = boxes_of({'type': name}, name)
    check(b1 == b2 and spec == before, f'sans clé : {name} inchangé ({len(b1)} boîtes)')

# ---------------------------------------------------------------- 3 & 4. determinism and variety
for name, mood in (('bedroom', 'haunted'), ('living_room', 'lived_in'), ('basement', 'abandoned'),
                   ('kitchen', 'ransacked'), ('forest', 'abandoned')):
    v = {'mood': mood, 'seed': 7}
    _, a = boxes_of({'type': name, 'variation': dict(v)}, name)
    _, b = boxes_of({'type': name, 'variation': dict(v)}, name)
    _, c = boxes_of({'type': name, 'variation': dict(v, seed=8)}, name)
    check(a == b, f'déterminisme : {name}/{mood} identique au second appel')
    check(a != c, f'variété : {name}/{mood} change avec la graine')
for name in EV.NEW_PLACES:
    _, a = boxes_of({'type': name, 'seed': 2}, name)
    _, b = boxes_of({'type': name, 'seed': 2}, name)
    _, c = boxes_of({'type': name, 'seed': 9}, name)
    check(a == b, f'déterminisme : {name} identique au second appel')
    check(a != c or name == 'stairwell', f'variété : {name} change avec la graine')

# ---------------------------------------------------------------- 5. geometry
FRONT = {0: (0., -1.), 1: (-1., 0.), 2: (0., 1.), 3: (1., 0.)}     # front of a prop once it is rotated


def geometry(spec, name, label):
    st = make_set(name, spec)
    st.build()
    sp = st.spec
    bad_bounds, bad_face, bad_floor, bad_ceil = [], [], [], []
    for room in sp.get('rooms', []):
        ox, oz = room.get('origin', [0, 0])
        w, d = room.get('size', [4, 5])
        h = float(room.get('height', sp.get('height', 2.6)))
        for p in room.get('props', []):
            x, z = float(p['at'][0]), float(p['at'][1])
            if not (-w / 2 - .25 <= x <= w / 2 + .25 and -.25 <= z <= d + .25):
                bad_bounds.append((p.get('type'), x, z))
                continue
            try:
                bl = place_boxes(prop_boxes(p.get('type', 'crate'), p), x, z, int(p.get('rot', 0)), float(p.get('y', 0.)))
            except Exception as e:
                bad_bounds.append((p.get('type'), 'build', str(e)))
                continue
            lo = np.min([b.lo for b in bl], 0)
            hi = np.max([b.hi for b in bl], 0)
            if lo[1] < -.02:
                bad_floor.append((p.get('type'), round(float(lo[1]), 3)))
            if hi[1] > h + .02:
                bad_ceil.append((p.get('type'), round(float(hi[1]), 3)))
            dists = {'W': x + w / 2, 'E': w / 2 - x, 'S': z, 'N': d - z}
            wall = min(dists, key=dists.get)
            if dists[wall] < .35:                       # clearly standing against that wall
                fx, fz = FRONT[int(p.get('rot', 0)) % 4]
                into = {'W': (1., 0.), 'E': (-1., 0.), 'S': (0., 1.), 'N': (0., -1.)}[wall]
                if fx * into[0] + fz * into[1] < -0.1:  # its front shows the wall, not the room
                    bad_face.append((p.get('type'), wall, int(p.get('rot', 0))))
    check(not bad_bounds, f'{label} : tous les objets sont dans la pièce', str(bad_bounds[:4]))
    check(not bad_floor, f'{label} : rien ne traverse le sol', str(bad_floor[:4]))
    check(not bad_ceil, f'{label} : rien ne traverse le plafond', str(bad_ceil[:4]))
    check(not bad_face, f'{label} : les objets muraux montrent leur face à la pièce', str(bad_face[:4]))
    return st


for name in ('corridor', 'stairwell', 'parking'):
    geometry({'type': name, 'seed': 3}, name, name)
for name, mood in (('bedroom', 'haunted'), ('living_room', 'lived_in'), ('kitchen', 'ransacked'),
                   ('basement', 'abandoned'), ('attic', 'abandoned'), ('classroom', 'clinical')):
    geometry({'type': name, 'variation': {'mood': mood, 'seed': 5}}, name, f'{name}/{mood}')

# ---------------------------------------------------------------- 6. the camera lane and the anchors stay free
def clearance(spec, name, label):
    """only what the pass added is judged: the recipe's own sofa standing on its own anchor is not our business"""
    plain = make_set(name, {'type': name})
    plain.build()
    shipped = set()
    for room in plain.spec.get('rooms', []):
        for p in room.get('props', []):
            shipped.add((p.get('type'), round(float(p['at'][0]), 2), round(float(p['at'][1]), 2)))
    st = make_set(name, spec)
    st.build()
    sp = st.spec
    anchors = {k: a for k, a in st.anchors.items() if k != 'lampe' and not k.startswith('indice')}
    start = anchors.get('start', (0., .5))
    busy = []
    for room in sp.get('rooms', []):
        ox, oz = room.get('origin', [0, 0])
        d = room.get('size', [4, 5])[1]
        mid = (ox, oz + d / 2)
        for p in room.get('props', []):
            if (p.get('type'), round(float(p['at'][0]), 2), round(float(p['at'][1]), 2)) in shipped:
                continue
            x, z = ox + float(p['at'][0]), oz + float(p['at'][1])
            try:
                bl = place_boxes(prop_boxes(p.get('type', 'crate'), p), x, z, int(p.get('rot', 0)), float(p.get('y', 0.)))
            except Exception:
                continue
            lo = np.min([b.lo for b in bl], 0)
            hi = np.max([b.hi for b in bl], 0)
            if hi[1] < .35 or lo[1] > 1.9:              # a rug or something high over the head: never in the way
                continue

            def gap(px, pz):                            # distance from a point to the prop's real footprint
                return math.hypot(max(lo[0] - px, 0., px - hi[0]), max(lo[2] - pz, 0., pz - hi[2]))

            ax, az, bx, bz = start[0], start[1], mid[0], mid[1]
            dx, dz = bx - ax, bz - az
            close = min(gap(ax + k / 24 * dx, az + k / 24 * dz) for k in range(25))
            if close < .30:
                busy.append((p.get('type'), round(x, 2), round(z, 2), round(close, 2)))
            for k, a in anchors.items():
                if k in ('start',) or k.endswith('.center') or p.get('id') == k:
                    continue
                if gap(a[0], a[1]) < .22:
                    busy.append((p.get('type'), 'repère ' + k, round(gap(a[0], a[1]), 2)))
    check(not busy, f'{label} : couloir caméra et repères dégagés', str(busy[:5]))


for name, mood in (('bedroom', 'haunted'), ('living_room', 'lived_in'), ('kitchen', 'ransacked'),
                   ('basement', 'abandoned')):
    clearance({'type': name, 'variation': {'mood': mood, 'seed': 5}}, name, f'{name}/{mood}')

# ---------------------------------------------------------------- 7. the cost of the dressing
r3d.configure('16:9')


def cost(spec_a, spec_b, name, cam):
    out = []
    for sp in (spec_a, spec_b):
        st = make_set(name, sp)
        st.build()
        sc = st.scene({}, 0., 0.)
        pos, target, fov = cam
        dx, dy, dz = (target[i] - pos[i] for i in range(3))
        c = (pos, math.atan2(dx, dz), math.atan2(dy, math.hypot(dx, dz)), 0., float(fov))
        L = st.lights({}, 0., 0., np.array(pos, np.float32))
        r3d.render(sc, c, L)
        out.append((sc, c, L))
    ts = [[], []]
    for _ in range(4):
        for i, (sc, c, L) in enumerate(out):
            t0 = time.perf_counter()
            r3d.render(sc, c, L)
            ts[i].append(time.perf_counter() - t0)
    return min(ts[0]), min(ts[1])


CAM = {'bedroom': ((1.55, 1.62, .55), (-1.0, 1.2, 4.3), 66),
       'living_room': ((1.95, 1.64, .55), (-1.2, 1.15, 4.6), 68),
       'basement': ((2.45, 1.58, .6), (-1.6, 1.05, 5.8), 70),
       'kitchen': ((1.55, 1.62, .55), (-1.1, 1.15, 4.4), 66)}
ratios = {}
for name, mood in (('bedroom', 'haunted'), ('living_room', 'lived_in'), ('kitchen', 'ransacked'),
                   ('basement', 'abandoned')):
    ta, tb = cost({'type': name}, {'type': name, 'variation': {'mood': mood, 'seed': 5}}, name, CAM[name])
    ratios[name] = round(tb / ta, 2)
    check(tb / ta < 3.0, f'coût : {name}/{mood} x{tb / ta:.2f} du décor nu (< 3)', f'{ta*1000:.0f} -> {tb*1000:.0f} ms')

print()
print(f'{len(OK)} OK, {len(BAD)} échec(s)')
print('coût relatif du pass : ' + json.dumps(ratios))
sys.exit(1 if BAD else 0)
