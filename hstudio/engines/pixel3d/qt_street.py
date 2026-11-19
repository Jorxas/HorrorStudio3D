"""Le lieu `quartier` (une rue bordée de bâtiments à identité), l'élément composable `quartier`, l'enregistrement, et la montée en gamme des lieux livrés.

    {"type": "quartier", "identite": "art_deco", "sky": "night", "seed": 3}          une rue de 70 m, deux rangées de bâtiments, mobilier de rue
    {"kind": "quartier", "identite": "brique_rouge", "rect": [...]}                  dans un lieu `composed` (compose.BUILDERS)

Sans la clé d'épisode `diversite`, `upgrade()` rend le lieu demandé tel quel : `city_street` reste `city_street`, boîte pour boîte."""
import numpy as np
from . import quartiers as Q, qt_props as P
from .quartiers import IDENTITES

ROAD_HALF = 3.2
_CLS = None


def register(PLACES):
    """enregistrement additif (clés nouvelles seulement) : accessoires qt_*, lieu `quartier`, élément composable"""
    from . import world as W, places as PL
    for k, fn in P.NEW_PROPS.items(): W.PROPS.setdefault(k, fn)
    for k, l in P.NEW_LIGHTS.items(): W.PROP_LIGHTS.setdefault(k, l)
    PLACES.setdefault('quartier', quartier)
    PL.DEFAULT_AMBIENCE.setdefault('quartier', 'city'); PL.START.setdefault('quartier', (0., 1.))
    from . import compose
    compose.BUILDERS.setdefault('quartier', element)
    from . import qi_lieux as QL
    QL.register(PLACES)


def set_class():
    """RoomSet qui ne garde que les lumières proches (une rue de 70 m a trente lampadaires : le coût d'une lumière est par pixel)"""
    global _CLS
    if _CLS is None:
        from .sets import RoomSet

        class QuartierSet(RoomSet):
            name = 'quartier'
            NEAR = 10

            def lights(self, state, t, u, cam_pos):
                L = super().lights(state, t, u, cam_pos)
                fill, body = L[-1], L[:-1]
                big = [l for l in body if l[3] >= 100]; small = [l for l in body if l[3] < 100]
                small.sort(key=lambda l: (l[0][0] - cam_pos[0]) ** 2 + (l[0][2] - cam_pos[2]) ** 2)
                return small[:self.NEAR] + big + [fill]

            def voxel_native(self):
                """VOXEL : les bâtiments, détails de rue et lampadaires sont refaits en volumes par voxelgpu/b_quartiers.py (autre version, même plan)"""
                from ...voxelgpu import b_quartiers as BQ
                return BQ.native_hide(self), BQ.native_items(self)

            def voxel_bsets(self):
                from ...voxelgpu import b_quartiers as BQ
                return BQ.native_bsets(self)
        _CLS = QuartierSet
    return _CLS


def wrap(o):
    """le lieu construit par make_set : un RoomSet, ou son cousin de quartier / d'intérieur habillé (VOXEL en refait les volumes)"""
    from .sets import RoomSet
    if isinstance(o, dict) and o.get('_qt'): return set_class()(o)
    if isinstance(o, dict) and o.get('_qi'):
        from . import qi_lieux as QL
        return QL.wrap_cls()(o)
    return RoomSet(o)


def finish(o, kind, spec, name=None):
    from . import qi_lieux as QL
    return QL.finish(o, kind, spec, name)


NO_DAY = ('neon_nuit',)


def upgrade(kind, spec, name=None):
    """lieu livré -> lieu à identité, SEULEMENT sous la clé `diversite` (sinon (kind, spec) rendus tels quels)"""
    st = Q.active()
    if not st: return kind, spec
    spec = spec or {}
    if spec.get('diversite') is False: return kind, spec
    if kind == 'city_street' and st['exterieurs']:
        sp = dict(spec); sp['type'] = 'quartier'; sp['_from'] = 'city_street'; sp['_name'] = name or 'rue'
        return 'quartier', sp
    from . import qi_lieux as QL
    return QL.upgrade(kind, spec, name)


# ------------------------------------------------------------------------------------------------- le lieu
def _street_props(o, I, rng, night, ident, descs, z0, z1, front_x):
    kinds = {'gas': 'qt_lamp', 'old': 'qt_lamp', 'modern': 'qt_lamp_cool', 'deco': 'qt_lamp', 'lantern': 'qt_lamp', 'neon': 'qt_lamp_neon'}
    lk = kinds[I['lamp']]
    for i, z in enumerate(np.arange(z0 + 3, z1 - 2, 11.)):
        for side in (-1, 1):
            if (i + (side > 0)) % 2: continue
            o['props'].append(dict(type=lk, at=[side * 4.3, round(float(z) + (3 if side > 0 else 0), 1)], rot=3 if side < 0 else 1, style=I['lamp'], group='qts'))
    if I.get('tree'):
        for i, z in enumerate(np.arange(z0 + 6, z1 - 4, 10.)):
            side = -1 if i % 2 else 1
            if I.get('lawn') or (I['tree'] == 'palm' and i % 2): continue
            o['props'].append(dict(type=I['tree'], at=[side * 4.6, round(float(z), 1)], rot=int(rng.integers(0, 4)), size=round(float(rng.uniform(.9, 1.15)), 2), group='qts'))
    cars = I['cars']
    for k in range(3):
        z = float(rng.uniform(z0 + 6, z1 - 8)); side = -1 if k % 2 else 1
        if z < 9 or abs(z - 10) < 3.5: continue
        o['props'].append(dict(type='car', at=[side * 2.2, round(z, 1)], color=list(cars[int(rng.integers(0, len(cars)))]), rot=0, group='qts'))
    o['props'] += [dict(type='trash_can', at=[-4.2, 4.0]), dict(type='hydrant', at=[4.2, 6.0]), dict(type='mailbox', at=[-4.3, 12.0]), dict(type='bus_stop', at=[5.0, 15.0], rot=1)]
    for d in descs:                                                                   # terrasses de café devant quelques vitrines
        if not d['near'] or ident not in ('brique_rouge', 'crepi_pastel', 'mediterraneen', 'art_deco'): continue
        fr = P.Frame(d)
        for b, cell in enumerate(d['cells'][0]):
            if cell['t'] == 'shop' and (b + d['seed']) % 2 == 0:
                x, z = fr.pt((b + .5) * d['W'] / d['bays'], -1.7)
                if abs(x) < 4.9: o['props'].append(dict(type='qt_terrace', at=[round(x, 2), round(z, 2)], col=list(cell['col']), group='qts'))


def quartier(spec):
    """lieu `quartier` : une rue avec deux rangées de bâtiments d'une même identité (voir quartiers.IDENTITES)"""
    from . import places as PL
    st = Q.active() or {}
    seed = int(spec.get('seed', 0)) + int(st.get('seed', 0)) + int(st.get('base', 0))
    asked = spec.get('identite') or spec.get('identity') or spec.get('quartier') or st.get('quartier')
    ident = Q.identity(asked, seed)
    I = IDENTITES[ident]
    explicit_sky = spec.get('sky')
    if not asked and spec.get('_from') and not explicit_sky and ident in NO_DAY: ident = ORDER_NEXT(ident); I = IDENTITES[ident]
    sky = explicit_sky or I['sky']
    night = sky in ('night', 'storm')
    wet = bool(spec.get('wet', I['wet'] or night))
    rng = np.random.default_rng((seed * 7919 + sum(map(ord, ident))) & 0x7fffffff)
    z0, z1 = -8., float(spec.get('length', 64.))
    lawn = bool(I.get('lawn'))
    front_x = 8.2 if lawn else 5.1
    kw = dict(outdoor=True, sky=sky, ground='grass' if lawn else I['ground_k'], backdrop=[I['backdrop']] if I['backdrop'] != 'city' else [{'type': 'city', 'height': 14, 'density': 40}],
              fog=I['fog'], ambience='city', stars=night, wet=wet, fill=.5, textured_ground=True)
    o = PL._base(spec, **kw)
    sidewalk = I['ground_k'] if not lawn else 'stone'
    o['zones'] = [{'rect': [-4.9, z0 - 4, 4.9, z1 + 30], 'ground': sidewalk}, {'rect': [-ROAD_HALF, z0 - 4, ROAD_HALF, z1 + 30], 'ground': 'road'}]
    if not lawn: o['ground'] = sidewalk
    if night: o['ambient'] = spec.get('ambient', (.11, .11, .18))                 # une rue de nuit reste lisible : les façades colorées gardent leur teinte
    o['_qt'] = dict(ident=ident, label=I['label'], night=night, sky=sky)
    descs = []; blocks = []; props = []; n = 0
    for side in (-1, 1):
        z = z0 + float(rng.uniform(0, 3))
        while z < z1:
            Wd = float(rng.uniform(*I['width'])); Dp = float(rng.uniform(*I['depth']))
            zc = z + Wd / 2; near = bool(-6 < zc < 22)
            rect = (-front_x - Dp, z, -front_x, z + Wd) if side < 0 else (front_x, z, front_x + Dp, z + Wd)
            d = Q.building(ident, n, '+x' if side < 0 else '-x', rect, near, seed, None); n += 1
            descs.append(d); bl, pr = P.build_ps1(d, night, detail=near); blocks += bl; props += pr
            z += Wd + float(rng.uniform(*I['gap']))
    ew = 24.; ed = float(rng.uniform(*I['depth']))                                    # le bâtiment qui ferme la rue
    rect = (-ew / 2, z1 + 1, ew / 2, z1 + 1 + ed)
    d = Q.building(ident, n, '-z', rect, False, seed, None); n += 1
    descs.append(d); bl, pr = P.build_ps1(d, night, detail=False); blocks += bl; props += pr
    o['blocks'] = blocks + list(o.get('blocks', []))
    o['props'] = props + list(o.get('props', []))
    _street_props(o, I, rng, night, ident, descs, z0, z1, front_x)
    if lawn:                                                                         # allée de jardin et boîtes aux lettres
        o['zones'].append({'rect': [-front_x, z0, front_x, z1], 'ground': 'grass'}); o['zones'] = [o['zones'][1], o['zones'][0]] + o['zones'][2:]
        o['zones'][1] = {'rect': [-4.9, z0 - 4, 4.9, z1 + 30], 'ground': 'stone'}
    o['_qt']['bkeys'] = [[d['ident'], int(d['id'][3:]), d['front'], list(d['rect']), bool(d['near']), int(d['seed']) // 1000, None] for d in descs]
    a = {'sidewalk.left': (-4.5, 6), 'sidewalk.right': (4.5, 6), 'crossing': (0, 10), 'bus_stop': (4.6, 14), 'shop.left': (-6, 8), 'shop.right': (6, 20), 'street.far': (0, 28),
         'quartier.debut': (0, 0), 'quartier.fond': (0, 50), 'rue.milieu': (0, 24)}
    o['anchors'] = dict(a, **(o.get('anchors') or {}))
    return o


def ORDER_NEXT(ident):
    ks = list(Q.ORDER); i = ks.index(ident)
    for k in range(1, len(ks) + 1):
        if ks[(i + k) % len(ks)] not in NO_DAY: return ks[(i + k) % len(ks)]
    return ident


def element(e, c):
    """élément composable `quartier` : {"kind": "quartier", "identite": ..., "rect": [x0, z0, x1, z1], "front": "-z", "count": 3, "seed": 0} -> une rangée de bâtiments"""
    x0, z0, x1, z1 = (float(v) for v in e['rect'])
    seed = int(e.get('seed', c.seed)); ident = Q.identity(e.get('identite') or e.get('identity'), seed); I = IDENTITES[ident]
    rng = np.random.default_rng(seed * 31 + 7)
    front = e.get('front', '-z' if (x1 - x0) >= (z1 - z0) else '+x')
    n = int(e.get('count', 3)); night = bool(c.night); near = bool(e.get('near', True))
    span = (x1 - x0) if front in ('-z', '+z') else (z1 - z0)
    Wd = span / n; depth = float(e.get('depth', rng.uniform(*I['depth'])))
    for k in range(n):
        if front == '-z': rect = (x0 + k * Wd, z1 - depth, x0 + (k + 1) * Wd - .2, z1)
        elif front == '+z': rect = (x0 + k * Wd, z0, x0 + (k + 1) * Wd - .2, z0 + depth)
        elif front == '+x': rect = (x0, z0 + k * Wd, x0 + depth, z0 + (k + 1) * Wd - .2)
        else: rect = (x1 - depth, z0 + k * Wd, x1, z0 + (k + 1) * Wd - .2)
        c.n += 1
        d = Q.building(ident, 400 + c.n, front, rect, near, seed, None if e.get('top') is None else float(e['top']))
        bl, pr = P.build_ps1(d, night, detail=near)
        for b in bl: b['at'][1] += c.gy
        for p in pr: p['y'] = round(p.get('y', 0.) + c.gy, 3)
        c.blocks += bl; c.props += pr; c.occupied.append(rect)
