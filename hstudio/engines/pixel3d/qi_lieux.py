"""Intérieurs variés (PS1) : le dressage d'une pièce, les lieux complets, l'enregistrement et la montée en gamme des lieux livrés.

    {"type": "appartement", "disposition": "studio" | "familial" | "loft" | "mansarde", "ambiance": "moutarde"}       4 appartements, 10 ambiances
    {"type": "hall_immeuble" | "escalier_immeuble" | "cafe_quartier" | "boutique" | "salon_maison", "ambiance": "menthe"}
Sous la clé d'épisode `diversite` (profil production), `bedroom`, `kid_bedroom`, `living_room`, `kitchen`, `bathroom`, `library`, `cafe`, `shop`, une pièce `room` écrite à la main et
l'`apartment` d'Ascenseur Zéro reçoivent palette et détails ; sans la clé `finish()` rend le lieu tel quel (boîte pour boîte)."""
import copy
import zlib
import numpy as np
from . import quartiers as Q, interieurs as I
from . import environment_variation as EV

DRESS_KINDS = ('bedroom', 'kid_bedroom', 'living_room', 'kitchen', 'bathroom', 'library', 'cafe', 'shop', 'attic', 'office')
TOPS = {'table': .8, 'desk': .77, 'dining_table': .8, 'cafe_table': .76, 'counter': .94, 'counter_long': .94, 'nightstand': .52, 'tv_stand': .56}
SEATS = {'sofa': .46, 'armchair': .46, 'bed': .52, 'bed_double': .52}
_CLS = {}


def _rng(*k): return np.random.default_rng(zlib.crc32('|'.join(str(x) for x in k).encode()) & 0x7fffffff)


def _tint(room, pal, explicit_walls, hard):
    if not explicit_walls:
        room['wall_color'] = list(pal['wall'])
    room['ceiling_color'] = list(pal['trim']); room['wainscot'] = False
    kind = room.get('floor', 'wood')
    if kind in ('wood', 'carpet', 'linoleum'): fk, c1, c2 = pal['floor']
    elif kind in ('tiles', 'checker'): fk, c1, c2 = pal['hard']
    else: return
    if hard and kind in ('wood', 'carpet', 'linoleum'): fk, c1, c2 = pal['hard']
    room['floor'] = fk; room['floor_color'] = [round(v / 255., 3) for v in (*c1, *c2)]


def _abs(room, x, z): ox, oz = room.get('origin', [0, 0]); return round(ox + x, 3), round(oz + z, 3)


def dress(o, kind, ask, pal_name, theme=None, force_tint=True):
    """pièces d'un lieu -> palette + plinthes + mur d'accent + détails dans l'espace libre. -> un NOUVEAU dict (l'entrée n'est pas modifiée)"""
    o = copy.deepcopy(o); pal = I.PAL[pal_name]; rng = _rng(kind, pal_name, (ask or {}).get('seed', 0)); props = o.setdefault('props', []); blocks = o.setdefault('blocks', [])
    o['_qi'] = {'palette': pal_name, 'kind': kind}
    for room in o.get('rooms') or []:
        w, d = room.get('size', [4, 5]); ox, oz = room.get('origin', [0, 0]); h = float(room.get('height', o.get('height', 2.6)))
        keep = []
        for p in room.get('props', []):                                                       # un détail de vie écrit dans une pièce passe au niveau du lieu : c'est lui que VOXEL refait en natif
            if str(p.get('type', '')).startswith('qi_'): props.append(dict(p, at=list(_abs(room, *p['at'])), group='qi'))
            else: keep.append(p)
        room['props'] = keep
        explicit = bool(room.get('wall_color'))                                                  # une couleur écrite (par l'histoire ou la recette) reste la couleur
        if force_tint: _tint(room, pal, explicit, kind in ('kitchen', 'bathroom'))
        ko = EV.Keepout(); kw = EV.Keepout(); locs = []
        for p in room.get('props', []):
            m = EV._metrics(p); x, z = _abs(room, *p['at']); ko.disc(x, z, m[0] + .1)
            if m[3] > 1.3: kw.disc(x, z, m[0] + .2)
            locs.append((p, x, z, m))
        for p in props: ko.disc(float(p['at'][0]), float(p['at'][1]), .35)
        for k, v in (o.get('anchors') or {}).items():
            if '.' in k and k.split('.')[0] == room.get('id'): continue
            ko.disc(float(v[0]) + ox * 0, float(v[1]), .5)
        ko.lane((ox + w * .3, oz + .45), (ox, oz + d / 2), .5)
        def add(kind_, x, z, y=0., rot=0, **kw_): props.append(dict(type=kind_, at=[round(x, 3), round(z, 3)], y=round(y, 3), rot=rot, group='qi', **kw_))
        # plinthes et mur d'accent : blocs de coque (restent convertis en VOXEL, ce sont des murs)
        for wall in 'SNWE':
            for (a, b) in EV._wall_runs(room, wall, margin=.05):
                if b - a < .3: continue
                if wall in 'SN': blocks.append(dict(at=[round(ox - w / 2 + (a + b) / 2, 3), 0, round(oz + (.07 if wall == 'S' else d - .12), 3)], size=[round(b - a, 3), .12, .03], color=list(pal['trim']), material='flat', group='qis'))
                else: blocks.append(dict(at=[round(ox - w / 2 + (.12 if wall == 'W' else w - .17), 3), 0, round(oz + (a + b) / 2, 3)], size=[.03, .12, round(b - a, 3)], color=list(pal['trim']), material='flat', group='qis'))
        runs = EV._wall_runs(room, 'N', margin=.3)
        if runs and theme != 'neutre':
            a, b = max(runs, key=lambda r: r[1] - r[0])
            if b - a > 1.4: blocks.append(dict(at=[round(ox - w / 2 + (a + b) / 2, 3), 0, round(oz + d - .13, 3)], size=[round(b - a, 3), round(h - .02, 3), .03], color=list(pal['wall2']), material='flat', group='qis'))
        # rideaux de chaque fenêtre
        for wn in room.get('windows') or []:
            wall = wn.get('wall', 'N'); L = w if wall in 'SN' else d; u = float(wn.get('pos', .5)) * L; x, z, rot = EV._wall_spot(room, wall, u, inset=.09)
            ax, az = _abs(room, x, z); add('qi_curtain', ax, az, 0., rot, w=round(float(wn.get('width', 1.2)) + .55, 2), h=round(h - .25, 2), color=list(pal['curt']))
        # détails posés sur les meubles
        for (p, x, z, m) in locs:
            t = p.get('type')
            if t in TOPS:
                top = TOPS[t]
                if t in ('table', 'dining_table', 'cafe_table'): add('qi_tableware', x, z, top, 0, kind=('coffee' if t == 'table' and rng.random() < .5 else 'dinner' if t != 'cafe_table' else 'coffee'), acc=list(pal['acc']), seed=int(rng.integers(0, 99)))
                elif t in ('nightstand', 'tv_stand'): add('qi_lamp' if t == 'nightstand' else 'qi_vase', x, z, top, 0, **({'kind': 'table', 'shade': list(pal['shade'])} if t == 'nightstand' else {'color': list(pal['sofa'])}))
                elif t == 'desk': add('qi_lamp', x - .35, z, top, 0, kind='table', shade=list(pal['shade'])); add('qi_books', x + .2, z, top, p.get('rot', 0), w=.5, seed=int(rng.integers(0, 99)))
                elif t in ('counter', 'counter_long'): add('qi_tableware', x + .3, z, top, 0, kind='fruit')
            elif t in SEATS and theme != 'neutre': add('qi_cushions', x, z + (.25 if p.get('rot', 0) == 0 else 0), SEATS[t], int(p.get('rot', 0)), cols=[list(pal['arm']), list(pal['curt']), list(pal['acc'])], w=1.5 if t == 'sofa' else .8)
            if t == 'sofa' and not p.get('color'): p['color'] = list(pal['sofa'])
            if t == 'armchair' and not p.get('color'): p['color'] = list(pal['arm'])
            if t == 'rug' and not p.get('color'): p['color'] = list(pal['rug'][0])
        # cadres, étagères, plantes, lampe, tapis : dans l'espace libre
        n = 0; walls = list('NEW' if kind != 'cafe' else 'NEWS')
        for wall in walls:
            for (a, b) in EV._wall_runs(room, wall, margin=.4):
                if b - a < .9 or n >= 5: continue
                u = float(rng.uniform(a + .4, b - .4)); x, z, rot = EV._wall_spot(room, wall, u, inset=.05); ax, az = _abs(room, x, z)
                ix, iz = _abs(room, *EV._wall_spot(room, wall, u, inset=.5)[:2])
                if not kw.free(ix, iz, .3): continue
                add('qi_frame', ax, az, 1.35, rot, w=round(float(rng.uniform(.5, .8)), 2), h=round(float(rng.uniform(.6, .95)), 2), art=str(rng.choice(['soleil', 'geo', 'rayures', 'paysage'])), cols=[list(pal['acc']), list(pal['sofa']), list(pal['wall2'])], seed=int(rng.integers(0, 99))); n += 1
        for k, kk in enumerate(('monstera', 'ficus', 'cactus', 'palm')[:2 + int(w * d > 20)]):
            for _ in range(12):
                wall = 'NEWS'[int(rng.integers(0, 4))]; L = w if wall in 'SN' else d; u = float(rng.uniform(.5, L - .5)); x, z, rot = EV._wall_spot(room, wall, u, inset=.4); ax, az = _abs(room, x, z)
                if ko.free(ax, az, .32) and not (wall == 'S' and abs(x) < 1.2): add('qi_plant', ax, az, 0., 0, kind=kk, pot=list(pal['acc']), size=round(float(rng.uniform(.9, 1.3)), 2)); ko.disc(ax, az, .35); break
        for _ in range(12):
            wall = 'NEW'[int(rng.integers(0, 3))]; L = w if wall in 'SN' else d; u = float(rng.uniform(.5, L - .5)); x, z, rot = EV._wall_spot(room, wall, u, inset=.4); ax, az = _abs(room, x, z)
            if ko.free(ax, az, .3): add('qi_lamp', ax, az, 0., 0, kind='floor', shade=list(pal['shade'])); ko.disc(ax, az, .3); break
        if kind in ('living_room', 'bedroom', 'kid_bedroom', 'library') and not any(p.get('type') in ('bookshelf', 'qi_bookcase') for p in room.get('props', [])):
            for wall in 'WE':
                for (a, b) in EV._wall_runs(room, wall, margin=.4):
                    if b - a > 1.3 and not any(q['type'] == 'qi_bookcase' for q in props):
                        u = float(rng.uniform(a + .6, b - .6)); x, z, rot = EV._wall_spot(room, wall, u, inset=.19); ax, az = _abs(room, x, z)
                        if kw.free(*_abs(room, *EV._wall_spot(room, wall, u, inset=.5)[:2]), .45): add('qi_bookcase', ax, az, 0., rot, color=list(pal['wood']), seed=int(rng.integers(0, 99)))
        if not any(p.get('type') == 'rug' for p in room.get('props', [])) and theme != 'neutre' and kind != 'bathroom':
            add('qi_rug', ox, oz + d * .46, 0., 0, w=round(min(2.6, w * .42), 2), d=round(min(1.8, d * .3), 2), cols=[list(pal['rug'][0]), list(pal['rug'][1])], pattern='bordure' if rng.random() < .6 else 'rayures')
    return o


# ================================================================================================ lieux complets
def _room(PL, spec, rid, size, walls, floor, light='warm', **kw):
    o, r = PL._room(spec, rid, size, walls, floor, light=light, **kw)
    return o, r


def _pal(spec, kind, d=0):
    st = Q.active() or {}
    return I.palette(spec.get('ambiance') or st.get('ambiance'), int(spec.get('seed', 0)) + int(st.get('seed', 0)) + int(st.get('base', 0)) + zlib.crc32(kind.encode()) % 97 + d)


def _finish(o, kind, spec, pal_name, **kw):
    o = dress(o, kind, spec, pal_name, **kw); o['anchors'] = dict(o.get('anchors') or {})
    return o


def appartement(spec):
    from . import places as PL
    disp = str(spec.get('disposition') or ['studio', 'familial', 'loft', 'mansarde'][int(spec.get('seed', 0)) % 4]); pn = _pal(spec, 'appartement'); pal = I.PAL[pn]
    dn = {'studio': dict(size=[7, 5.5], h=2.6), 'familial': dict(size=[8.5, 6.2], h=2.7), 'loft': dict(size=[9, 6.5], h=3.7), 'mansarde': dict(size=[7.5, 5], h=2.25)}.get(disp, dict(size=[7, 5.5], h=2.6))
    w, d = dn['size']; wall = 'brick' if disp == 'loft' else 'plaster'
    o, r = _room(PL, spec, 'sejour', dn['size'], wall, 'wood', 'warm', height=dn['h'], windows=[{'wall': 'N', 'pos': .2, 'night': spec.get('night', False), 'width': 1.4}, {'wall': 'N', 'pos': .8, 'night': spec.get('night', False), 'width': 1.4}] if disp != 'mansarde' else [{'wall': 'N', 'pos': .5, 'width': 1.6, 'night': spec.get('night', False)}],
                 doors=[{'id': 'porte', 'wall': 'W', 'pos': .22}])
    if disp == 'loft': r['wall_color'] = [176, 82, 60]
    o['height'] = dn['h'] + .05
    sx = w / 2
    if disp == 'studio':
        r['props'] = [{'type': 'bed', 'at': [-sx + 1.3, d - 1.05], 'rot': 0, 'id': 'lit', 'color': list(pal['arm'])}, {'type': 'nightstand', 'at': [-sx + 2.25, d - .3], 'rot': 0}, {'type': 'nightstand', 'at': [-sx + .35, d - .3], 'rot': 0},
                      {'type': 'wardrobe', 'at': [-sx + .32, 2.6], 'rot': 3}, {'type': 'sofa', 'at': [1.0, d - .6], 'rot': 0, 'id': 'canape', 'color': list(pal['sofa'])}, {'type': 'table', 'at': [1.0, d - 1.8], 'rot': 0},
                      {'type': 'armchair', 'at': [2.6, d - 1.9], 'rot': 1}, {'type': 'tv_stand', 'at': [1.2, .35], 'rot': 2}, {'type': 'counter_long', 'at': [sx - .35, 1.4], 'rot': 1}, {'type': 'fridge', 'at': [sx - .35, 3.0], 'rot': 1},
                      {'type': 'dining_table', 'at': [-1.0, 1.4], 'id': 'table'}, {'type': 'chair', 'at': [-1.7, 1.4], 'rot': 3}, {'type': 'chair', 'at': [-.3, 1.4], 'rot': 1}]
        o['blocks'] = [{'at': [-.4, 0, d - 1.8], 'size': [.1, 1.2, 3.0], 'color': list(pal['wall2']), 'material': 'flat', 'group': 'qis'}]
        o['anchors'] = {'lit': (-sx + 1.3, d - 1.2), 'canape': (1.0, d - 1.5), 'table': (-1.0, 1.4), 'fenetre': (-3, d - .6), 'porte': (-sx + .7, 1.5), 'centre': (0, 2.5), 'cuisine': (sx - 1.0, 1.4)}
    elif disp == 'familial':
        r['props'] = [{'type': 'sofa', 'at': [-1.2, d - .6], 'rot': 0, 'id': 'canape', 'color': list(pal['sofa'])}, {'type': 'armchair', 'at': [-3.3, d - 1.7], 'rot': 3}, {'type': 'armchair', 'at': [.9, d - 1.9], 'rot': 1},
                      {'type': 'table', 'at': [-1.2, d - 1.8], 'rot': 0}, {'type': 'tv_stand', 'at': [-1.2, 2.3], 'rot': 2}, {'type': 'bookshelf', 'at': [-sx + .2, 2.6], 'rot': 3},
                      {'type': 'dining_table', 'at': [2.6, 2.0], 'id': 'table'}, {'type': 'chair', 'at': [1.9, 2.0], 'rot': 3}, {'type': 'chair', 'at': [3.3, 2.0], 'rot': 1}, {'type': 'chair', 'at': [2.6, 1.3], 'rot': 0}, {'type': 'chair', 'at': [2.6, 2.7], 'rot': 2},
                      {'type': 'counter_long', 'at': [sx - 1.3, d - .35], 'rot': 0}, {'type': 'fridge', 'at': [sx - .35, d - 1.2], 'rot': 1}]
        o['anchors'] = {'canape': (-1.2, d - 1.5), 'table': (2.6, 2.0), 'fenetre': (-3.4, d - .6), 'porte': (-sx + .7, 1.5), 'centre': (0, 2.6), 'cuisine': (sx - 1.3, d - 1.0)}
    elif disp == 'loft':
        r['props'] = [{'type': 'sofa', 'at': [-1.5, d - .7], 'rot': 0, 'id': 'canape', 'color': list(pal['sofa'])}, {'type': 'armchair', 'at': [.9, d - 2.0], 'rot': 1, 'color': list(pal['arm'])}, {'type': 'table', 'at': [-1.5, d - 2.0], 'rot': 0},
                      {'type': 'bed_double', 'at': [sx - 1.4, d - 1.3], 'rot': 0, 'id': 'lit', 'color': list(pal['arm'])}, {'type': 'nightstand', 'at': [sx - 2.5, d - .3], 'rot': 0}, {'type': 'bookshelf', 'at': [-sx + .2, 2.2], 'rot': 3},
                      {'type': 'bookshelf', 'at': [-sx + .2, 3.4], 'rot': 3}, {'type': 'dining_table', 'at': [-1.5, 1.6], 'id': 'table'}, {'type': 'chair', 'at': [-2.2, 1.6], 'rot': 3}, {'type': 'chair', 'at': [-.8, 1.6], 'rot': 1},
                      {'type': 'counter_long', 'at': [sx - 1.0, 1.0], 'rot': 2}, {'type': 'column', 'at': [1.3, 2.6]}]
        o['anchors'] = {'canape': (-1.5, d - 1.5), 'lit': (sx - 1.4, d - 1.6), 'table': (-1.5, 1.6), 'fenetre': (-3, d - .6), 'porte': (-sx + .7, 1.5), 'centre': (0, 3.0)}
    else:
        r['props'] = [{'type': 'bed_double', 'at': [-1.8, d - 1.3], 'rot': 0, 'id': 'lit', 'color': list(pal['arm'])}, {'type': 'nightstand', 'at': [-.5, d - .3], 'rot': 0}, {'type': 'sofa', 'at': [1.7, d - .6], 'rot': 0, 'id': 'canape', 'color': list(pal['sofa'])},
                      {'type': 'table', 'at': [1.7, d - 1.8], 'rot': 0}, {'type': 'dining_table', 'at': [-.5, 1.4], 'id': 'table'}, {'type': 'chair', 'at': [-1.2, 1.4], 'rot': 3}, {'type': 'chair', 'at': [.2, 1.4], 'rot': 1},
                      {'type': 'wardrobe', 'at': [-sx + .32, 2.4], 'rot': 3}, {'type': 'counter_long', 'at': [sx - .35, 1.6], 'rot': 1}, {'type': 'fridge', 'at': [sx - .35, 3.0], 'rot': 1}]
        o['blocks'] = [dict(at=[x, 2.25 - .16, d / 2], size=[.25, .16, d], color=list(pal['wood']), material='wood', group='qis') for x in (-2.5, 0, 2.5)]
        o['anchors'] = {'lit': (-1.8, d - 1.2), 'canape': (1.7, d - 1.5), 'table': (-.5, 1.4), 'fenetre': (0, d - .6), 'porte': (-sx + .7, 1.5), 'centre': (0, 2.4)}
    o['_qi_pal'] = pn
    return _finish(o, 'appartement', spec, pn)


def salon_maison(spec):
    from . import places as PL
    pn = _pal(spec, 'salon'); pal = I.PAL[pn]
    o, r = _room(PL, spec, 'salon', [6.2, 5.2], 'plaster', 'wood', 'warm', windows=[{'wall': 'N', 'pos': .2, 'night': spec.get('night', False), 'width': 1.3}, {'wall': 'N', 'pos': .8, 'night': spec.get('night', False), 'width': 1.3}], doors=[{'id': 'porte', 'wall': 'E', 'pos': .2}])
    r['props'] = [{'type': 'sofa', 'at': [0, 4.6], 'rot': 0, 'id': 'canape', 'color': list(pal['sofa'])}, {'type': 'table', 'at': [0, 3.2], 'rot': 0}, {'type': 'armchair', 'at': [-2.2, 3.0], 'rot': 3, 'color': list(pal['arm'])},
                  {'type': 'armchair', 'at': [2.0, 3.0], 'rot': 1, 'color': list(pal['arm'])}, {'type': 'tv_stand', 'at': [0, .4], 'rot': 2}, {'type': 'fireplace', 'at': [-2.95, 1.6], 'rot': 3}]
    o['anchors'] = {'canape': (0, 4.0), 'tv': (0, .5), 'cheminee': (-2.7, 1.6), 'fenetre': (-1.5, 4.6), 'porte': (2.8, 1.2), 'table': (0, 3.2)}
    return _finish(o, 'living_room', spec, pn)


def cafe_quartier(spec):
    from . import places as PL
    pn = _pal(spec, 'cafe'); pal = I.PAL[pn]
    o, r = _room(PL, spec, 'cafe', [9, 7], 'wood', 'wood', 'warm', windows=[{'wall': 'S', 'pos': p_, 'night': spec.get('night', False), 'width': 1.6} for p_ in (.2, .8)], doors=[{'id': 'porte', 'wall': 'S', 'pos': .5}])
    r['props'] = [{'type': 'bar', 'at': [0, 5.9]}, {'type': 'qi_cakecase', 'at': [-2.3, 5.55], 'rot': 0}] + [{'type': 'cafe_table', 'at': [x, z]} for x in (-3.1, -1.1, 1.1, 3.1) for z in (1.9, 3.4)] \
                 + [{'type': 'chair', 'at': [x + .6, z], 'rot': 1, 'color': list(pal['arm'] if (x + z) % 2 else pal['sofa'])} for x in (-3.1, -1.1, 1.1, 3.1) for z in (1.9, 3.4)] \
                 + [{'type': 'qi_stool', 'at': [x, 5.2], 'color': list(pal['arm'] if i % 2 else pal['acc'])} for i, x in enumerate((-.9, -.3, .3, .9, 1.5, 2.1))] \
                 + [{'type': 'qi_menu', 'at': [2.9, 6.96], 'rot': 0, 'w': 1.0, 'h': 1.2, 'text': ['MENU', 'CAFÉ 2', 'THÉ 3', 'GÂTEAU 4']}, {'type': 'qi_pendants', 'at': [-1.1, 2.6], 'cols': [list(pal['shade']), list(pal['arm']), list(pal['acc'])], 'y': 2.55},
                    {'type': 'qi_pendants', 'at': [1.1, 2.6], 'cols': [list(pal['acc']), list(pal['shade']), list(pal['arm'])], 'y': 2.55}, {'type': 'sign', 'at': [0, 6.98], 'rot': 0, 'text': spec.get('name', 'CAFÉ'), 'color': list(pal['wall2'])}]
    for p in r['props']: p.setdefault('group', 'qi') if p['type'].startswith('qi_') else None
    o['anchors'] = {'comptoir': (0, 5.3), 'table.1': (-3.1, 1.9), 'table.2': (1.1, 3.4), 'entree': (0, .4)}
    return _finish(o, 'cafe', spec, pn)


def boutique(spec):
    from . import places as PL
    theme = str(spec.get('theme') or 'epicerie'); pn = _pal(spec, 'boutique'); pal = I.PAL[pn]
    o, r = _room(PL, spec, 'magasin', [8, 7], 'plaster', 'tiles', 'neon', windows=[{'wall': 'S', 'pos': .2, 'night': False, 'width': 1.8}, {'wall': 'S', 'pos': .82, 'night': False, 'width': 1.8}], doors=[{'id': 'entree', 'wall': 'S', 'pos': .5}])
    pr = [{'type': 'qi_shelving', 'at': [x, 6.7], 'rot': 0, 'w': 1.5, 'seed': i} for i, x in enumerate((-2.8, -1.1, .6, 2.3))] + [{'type': 'qi_shelving', 'at': [-3.8, z], 'rot': 3, 'w': 1.4, 'seed': 10 + z} for z in (2.2, 4.0)]
    if theme == 'mode': pr += [{'type': 'qi_mannequin', 'at': [x, 3.2], 'color': list(c)} for x, c in ((-1.4, pal['sofa']), (0, pal['acc']), (1.4, pal['arm']))]
    else: pr += [{'type': 'qi_crates', 'at': [1.3, 3.2], 'rot': 0, 'seed': 1}, {'type': 'qi_crates', 'at': [-1.4, 3.8], 'rot': 0, 'seed': 2}]
    pr += [{'type': 'counter', 'at': [2.7, 1.3], 'rot': 2}, {'type': 'cash_register', 'at': [2.7, 1.3], 'rot': 2}, {'type': 'qi_pendants', 'at': [0, 3.4], 'cols': [list(pal['shade']), list(pal['acc']), list(pal['arm'])], 'y': 2.5}]
    r['props'] = pr
    o['anchors'] = {'caisse': (2.7, 1.9), 'rayon.1': (-1.2, 3.0), 'rayon.2': (1.2, 5.0), 'entree': (0, .4)}
    return _finish(o, 'shop', spec, pn, theme='neutre')


def hall_immeuble(spec):
    from . import places as PL
    pn = _pal(spec, 'hall'); pal = I.PAL[pn]
    o, r = _room(PL, spec, 'hall', [5.4, 8.0], 'plaster', 'tiles', 'warm', height=3.0, light_power=1.0, windows=[], doors=[{'id': 'porte', 'wall': 'S', 'pos': .5, 'width': 1.6}, {'id': 'cave', 'wall': 'W', 'pos': .9}])
    o['height'] = 3.05
    r['props'] = [{'type': 'qi_elevator', 'at': [0, 7.9], 'rot': 0}, {'type': 'qi_mailboxes', 'at': [-2.55, 4.4], 'rot': 3, 'cols': 4, 'seed': 3}, {'type': 'qi_stairs', 'at': [2.1, 7.7], 'rot': 1, 'n': 9, 'w': 1.1, 'color': list(pal['wall2']), 'rail': list(pal['acc'])},
                  {'type': 'bench', 'at': [-2.1, 2.2], 'rot': 3}, {'type': 'qi_doormat', 'at': [0, 1.0], 'color': list(pal['sofa'])}, {'type': 'qi_plant', 'at': [-1.9, 7.3], 'kind': 'ficus', 'pot': list(pal['acc'])},
                  {'type': 'qi_pendants', 'at': [0, 4.6], 'cols': [list(pal['shade']), list(pal['arm']), list(pal['acc'])], 'y': 2.9}, {'type': 'noticeboard', 'at': [-2.62, 6.1], 'rot': 3}]
    o['anchors'] = {'entree': (0, 1.2), 'ascenseur': (0, 7.0), 'boites': (-2.0, 4.4), 'escalier': (1.5, 6.5), 'centre': (0, 4.0)}
    return _finish(o, 'hall', spec, pn, theme='neutre')


def escalier_immeuble(spec):
    from . import places as PL
    pn = _pal(spec, 'escalier'); pal = I.PAL[pn]
    o, r = _room(PL, spec, 'escalier', [4.2, 9.0], 'plaster', 'tiles', 'warm', height=3.2, windows=[{'wall': 'N', 'pos': .5, 'night': spec.get('night', False), 'width': 1.1}], doors=[{'id': 'porte', 'wall': 'S', 'pos': .3}, {'id': 'porte.palier', 'wall': 'E', 'pos': .7}])
    o['height'] = 3.25
    r['props'] = [{'type': 'qi_stairs', 'at': [1.0, 8.2], 'rot': 1, 'n': 14, 'w': 1.3, 'rise': .2, 'run': .3, 'color': list(pal['wall2']), 'rail': list(pal['acc'])}, {'type': 'qi_plant', 'at': [-1.6, 6.5], 'kind': 'palm', 'pot': list(pal['acc'])},
                  {'type': 'qi_doormat', 'at': [1.4, 5.2], 'rot': 0, 'color': list(pal['sofa'])}, {'type': 'qi_pendants', 'at': [0, 3.0], 'cols': [list(pal['shade']), list(pal['arm']), list(pal['acc'])], 'y': 3.0}]
    o['anchors'] = {'escalier.bas': (-.9, 1.5), 'palier': (-.8, 7.5), 'fenetre': (0, 8.4), 'porte': (-.8, 1.0), 'centre': (-.4, 4.5)}
    return _finish(o, 'escalier', spec, pn, theme='neutre')


NEW_PLACES = {'appartement': appartement, 'salon_maison': salon_maison, 'cafe_quartier': cafe_quartier, 'boutique': boutique, 'hall_immeuble': hall_immeuble, 'escalier_immeuble': escalier_immeuble}
NEW_AMBIENCE = {'appartement': 'room', 'salon_maison': 'room', 'cafe_quartier': 'cafe', 'boutique': 'room', 'hall_immeuble': 'room', 'escalier_immeuble': 'room'}


def register(PLACES):
    from . import world as W, places as PL
    for k, fn in I.NEW_PROPS.items(): W.PROPS.setdefault(k, fn)
    for k, l in I.NEW_LIGHTS.items(): W.PROP_LIGHTS.setdefault(k, l)
    for k, fn in NEW_PLACES.items(): PLACES.setdefault(k, fn)
    for k, a in NEW_AMBIENCE.items(): PL.DEFAULT_AMBIENCE.setdefault(k, a)


# ================================================================================================ montée en gamme des lieux livrés (clé `diversite`)
UPGRADE = {'cafe': 'cafe_quartier', 'shop': 'boutique'}


def upgrade(kind, spec, name=None):
    st = Q.active()
    if not st or not st.get('interieurs'): return kind, spec
    spec = spec or {}
    if spec.get('diversite') is False: return kind, spec
    if kind in UPGRADE and not spec.get('rooms'): sp = dict(spec); sp['type'] = UPGRADE[kind]; return UPGRADE[kind], sp
    return kind, spec


def finish(o, kind, spec, name=None):
    """lieu étendu -> lieu habillé (palette + détails) SI la clé est là et que le lieu est une pièce livrée ou écrite à la main ; sinon le même objet"""
    st = Q.active()
    if not st or not st.get('interieurs') or not isinstance(o, dict): return o
    if (spec or {}).get('diversite') is False or o.get('_qi') or o.get('outdoor') or not o.get('rooms'): return o
    if kind not in DRESS_KINDS and kind not in ('room',): return o
    if kind == 'room' and not (spec or {}).get('type', 'room') == 'room': return o
    pn = _pal(spec or {}, kind + '|' + str(name or ''))
    return dress(o, kind, spec or {}, pn, force_tint=True)


def make_apartment(cls, spec):
    """l'appartement d'Ascenseur Zéro : sans la clé `diversite` c'est `cls(spec)` tel quel ; avec elle, autres murs, sol, canapé et détails de vie (le plan reste le même : repères, portes, miroir)"""
    st = Q.active()
    if not st or not st.get('interieurs') or (spec or {}).get('diversite') is False: return cls(spec)
    pn = _pal(spec or {}, 'apartment'); pal = I.PAL[pn]; sp = dict(spec or {}); lob = bool(sp.get('lobby'))
    sp.setdefault('wall_color', list(pal['wall2'] if not lob else pal['wall'])); sp.setdefault('apt_wall', list(pal['wall'] if not lob else pal['wall2'])); sp.setdefault('sofa_color', list(pal['sofa'])); sp['_qi'] = pn
    return apartment_cls(cls)(sp)


def apartment_cls(base):
    if 'a' not in _CLS:
        class QApartment(base):
            def build(self):
                super().build(); dress_apartment(self, self.base)

            def voxel_native(self):
                from ...voxelgpu import b_interieurs as BI
                hide, items = super().voxel_native(); return set(hide) | BI.native_hide(self), items

            def voxel_bsets(self):
                from ...voxelgpu import b_interieurs as BI
                return BI.native_bsets(self)
        _CLS['a'] = QApartment
    return _CLS['a']


def dress_apartment(ap, sc):
    """détails de vie posés à la main dans le salon de l'appartement (z 9..16) : tapis, cadres, rideaux, plantes, coussins, livres, vaisselle"""
    from .sets import prop_boxes, place
    pal = I.PAL[ap.spec['_qi']]; fk, c1, c2 = pal['floor']; colr = [v / 255. for v in (*c1, *c2)]; base = sc.floor_fn; lobby = bool(ap.spec.get('lobby'))

    def floor_fn(P):
        alb, refl = base(P); m = P[:, 2] >= 9.05
        if m.any(): a, r = I.floor(fk, P[m, 0], P[m, 2], colr); alb[m] = a; refl[m] = r
        return alb, refl
    if not lobby: sc.floor_fn = floor_fn
    ap.qi_props = []; ap.qi_boxes = []
    L = [('qi_rug', -.2, 12.4, 0., 0, dict(w=2.6, d=1.9, cols=[list(pal['rug'][0]), list(pal['rug'][1])])),
         ('qi_frame', -2.97, 13.9, 1.4, 3, dict(w=.7, h=.85, art='soleil', cols=[list(pal['acc']), list(pal['sofa']), list(pal['wall2'])], seed=3)),
         ('qi_frame', -1.8, 15.92, 1.45, 0, dict(w=.6, h=.75, art='geo', cols=[list(pal['acc']), list(pal['sofa']), list(pal['wall2'])], seed=5)),
         ('qi_frame', 1.9, 15.92, 1.45, 0, dict(w=.6, h=.75, art='rayures', cols=[list(pal['sofa']), list(pal['acc']), list(pal['wall2'])], seed=7)),
         ('qi_curtain', 2.9, 12.5, 0., 1, dict(w=3.5, h=2.35, color=list(pal['curt']))), ('qi_plant', 2.55, 15.35, 0., 0, dict(kind='ficus', pot=list(pal['acc']))), ('qi_plant', -2.7, 9.7, 0., 0, dict(kind='monstera', pot=list(pal['acc']))),
         ('qi_cushions', -2.62, 12.2, .45, 3, dict(w=1.6, cols=[list(pal['arm']), list(pal['curt']), list(pal['acc'])])), ('qi_tableware', 1.18, 10.25, .8, 0, dict(kind='fruit')),
         ('qi_bookcase', 2.84, 15.1, 0., 1, dict(color=list(pal['wood']), seed=4)), ('qi_lamp', 2.5, 9.6, 0., 0, dict(kind='floor', shade=list(pal['shade'])))]
    if lobby: L = [x for x in L if x[0] in ('qi_plant', 'qi_frame')]
    for (k, x, z, y, rot, kw) in L:
        pr = dict(type=k, at=[x, z], y=y, rot=rot, group='qi', **kw); ap.qi_props.append(pr); n0 = len(sc.boxes)
        for b in place(prop_boxes(k, pr), x, z, rot, y): sc.add(b)
        ap.qi_boxes += list(range(n0, len(sc.boxes)))


def wrap_cls():
    """RoomSet d'un lieu habillé : VOXEL en refait les détails (voxelgpu/b_interieurs.py) au lieu de repeindre les boîtes PS1"""
    if 'c' not in _CLS:
        from .sets import RoomSet

        class InterieurSet(RoomSet):
            def voxel_native(self):
                from ...voxelgpu import b_interieurs as BI
                return BI.native_hide(self), []

            def voxel_bsets(self):
                from ...voxelgpu import b_interieurs as BI
                return BI.native_bsets(self)
        _CLS['c'] = InterieurSet
    return _CLS['c']
