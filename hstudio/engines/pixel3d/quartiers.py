"""Quartiers variés (V3, chantier « bâtiments et intérieurs variés ») : NEUF identités de quartier, nettement différentes.

POURQUOI. Le constat (31/10/2026) : « le moteur ne fait pas assez de détails à l'intérieur des bâtiments et utilise toujours une même couleur terne ».
Mesuré : `city_street` posait des boîtes unies (aucune fenêtre, aucune porte) dans cinq teintes de gris-brun, et l'ancien générateur de ville de
moteur_voxel (`town.js`) répétait UN gabarit de maison. Les moyens existaient (`env` : façades riches, `variation` : habillage d'intérieur) mais ils
étaient INACTIFS par défaut, et même actifs ils gardaient la palette terne (`WALLS`, `FLOORS` : beige, brun, gris) : un mur peint plus finement
reste un mur gris-brun.

CE QUE CE MODULE DONNE, tout en PS1 ET en VOXEL (règle des deux versions : docs/REGLE_DEUX_VERSIONS.md) :
  * `IDENTITES` : brique rouge, crépi pastel, bois, verre et acier, art déco, industriel, méditerranéen, nuit au néon, cité colorée --
    chacune avec sa palette franche, ses hauteurs, ses formes de toit, sa matière de mur, ses fenêtres, ses détails (balcons, auvents, enseignes,
    climatiseurs, plantes, tags, escaliers de secours, cheminées, volets, objets de toit) et son mobilier de rue ;
  * `plan_building` : le PLAN d'un bâtiment (grille de travées, fenêtres avec leur intérieur, détails), lu par les DEUX peintres : la version PS1
    le peint en texture (`qt_facade.py`) et pose des détails en boîtes (`qt_props.py`) ; la version VOXEL (`voxelgpu/b_quartiers.py`) le construit
    en vrais volumes (fenêtres en retrait, balcons, auvents, volets) ;
  * le lieu `quartier` ({"type": "quartier", "identite": "art_deco", "sky": "night", "seed": 3}) et l'élément composable `quartier` ;
  * la clé d'épisode `diversite` (posée par le profil `production`) : un `city_street` / `apartment` / pièce sans couleur demandée prend alors
    une identité et une palette. Sans la clé, RIEN ne change, au pixel près (tools/regress.py).

Tout est déterministe (graine = lieu + identité + `seed`), rien n'est lu sur disque, aucun modèle externe."""
import copy
import functools
import math
import zlib
import numpy as np

_STATE = None                         # état de la clé d'épisode `diversite` (None = absent = rien ne change)

# ================================================================================================ les identités
ROOM_CURT = [(244, 236, 214), (226, 112, 112), (116, 156, 226), (242, 202, 98), (150, 206, 150), (222, 150, 214)]

IDENTITES = {
    'brique_rouge': dict(
        budget=18, label='Brique rouge', sky='day', kind='brick', wet=False,
        walls=[(176, 58, 44), (154, 48, 40), (190, 80, 52), (140, 46, 40)], trim=(240, 230, 208), dark=(46, 40, 50),
        accents=[(34, 114, 76), (30, 70, 132), (214, 152, 34), (170, 34, 46), (240, 240, 232)],
        floors=(3, 5), fh=3.1, bay=2.7, width=(7, 12), depth=(10, 14), shape='sq', ww=1.0, wh=1.55, sill=.95,
        roofs=['flat'], gap=(0., .3), ground=['door', 'shop', 'shop', 'win'], lit=.5,
        p=dict(fire=.7, awn=.8, ac=.3, plant=.4, chimney=.6, blade=.6, tag=.8, ivy=.2, poster=.6, shut=0., box=.25, balcony=0., pipe=1., stoop=.5),
        roof_objs=['water_tank', 'water_tank', 'ac_unit', 'antenna', 'roof_vent', 'satellite_dish'],
        names=['BOULANGERIE', 'CAFÉ', 'LIBRAIRIE', 'PIZZA', 'FLEURS', 'PRIMEUR'], lamp='gas', tree='tree_round', backdrop='city', fog=.016, ground_k='stone',
        cars=[(40, 90, 170), (200, 40, 40), (236, 236, 230), (30, 30, 36)]),
    'crepi_pastel': dict(
        budget=16, label='Crépi pastel', sky='day', kind='plaster', wet=False,
        walls=[(246, 170, 182), (160, 220, 190), (250, 226, 140), (150, 196, 238), (196, 172, 232), (252, 194, 146)], trim=(255, 252, 244), dark=(70, 74, 96),
        accents=[(226, 78, 98), (40, 150, 150), (240, 150, 40), (90, 100, 200), (255, 252, 244)],
        floors=(2, 4), fh=2.9, bay=2.5, width=(4.5, 7), depth=(8, 11), shape='arch', ww=.95, wh=1.5, sill=.9,
        roofs=['gable_front', 'gable', 'hip'], gap=(0., .1), ground=['door', 'shop', 'win'], lit=.55,
        p=dict(fire=0., awn=.6, ac=.1, plant=.6, chimney=.7, blade=.5, tag=.05, ivy=.1, poster=.1, shut=.7, box=.7, balcony=.2, pipe=.3, stoop=.3),
        roof_objs=['roof_vent', 'satellite_dish'],
        names=['GLACES', 'FLEURS', 'BOUTIQUE', 'CHOCOLAT', 'THÉ', 'PÂTISSERIE'], lamp='old', tree='blossom_tree', backdrop='hills', fog=.012, ground_k='cobble',
        cars=[(244, 160, 178), (150, 214, 200), (252, 232, 150), (240, 240, 236)], roof_cols=[(200, 100, 70), (92, 112, 170), (150, 70, 90)]),
    'bois': dict(
        budget=14, label='Maisons de bois', sky='day', kind='siding', wet=False,
        walls=[(158, 44, 40), (36, 112, 124), (222, 166, 52), (56, 108, 72), (52, 76, 130), (214, 214, 204)], trim=(246, 244, 236), dark=(52, 50, 58),
        accents=[(40, 70, 120), (200, 60, 50), (240, 240, 232), (60, 120, 70)],
        floors=(2, 3), fh=2.8, bay=2.6, width=(7, 10), depth=(8, 11), shape='sq', ww=.9, wh=1.4, sill=.9,
        roofs=['gable', 'gable_front', 'gable'], gap=(2.5, 6.), ground=['door', 'win', 'win'], lit=.5,
        p=dict(fire=0., awn=.1, ac=.1, plant=.7, chimney=.9, blade=0., tag=0., ivy=.2, poster=0., shut=.8, box=.5, balcony=0., pipe=.4, stoop=1., porch=.8),
        roof_objs=['chimney_stack'],
        names=['ÉPICERIE'], lamp='old', tree='autumn_tree', backdrop='forest', fog=.014, ground_k='grass', lawn=True,
        cars=[(120, 40, 40), (50, 80, 120), (220, 210, 190)], roof_cols=[(72, 70, 80), (112, 56, 46), (58, 84, 70)]),
    'verre_acier': dict(
        budget=8, label='Verre et acier', sky='overcast', kind='glass', wet=True,
        walls=[(52, 128, 160), (70, 150, 176), (40, 96, 140), (88, 120, 168)], trim=(196, 204, 214), dark=(30, 40, 56),
        accents=[(250, 120, 30), (250, 250, 250), (30, 200, 190)],
        floors=(6, 11), fh=3.5, bay=1.9, width=(9, 14), depth=(12, 16), shape='pane', ww=1.6, wh=2.4, sill=.5, gf=4.6,
        roofs=['flat', 'stepped_glass'], gap=(2., 5.), ground=['lobby'], upper='pane', lit=.55,
        p=dict(fire=0., awn=0., ac=0., plant=.1, chimney=0., blade=.3, tag=0., ivy=0., poster=0., shut=0., box=0., balcony=0., pipe=0., stoop=0., canopy=.9),
        roof_objs=['ac_unit', 'ac_unit', 'antenna', 'roof_vent'],
        names=['BANQUE', 'HÔTEL', 'CAFÉ', 'ASSURANCES'], lamp='modern', tree='birch', backdrop='city', fog=.012, ground_k='stone',
        cars=[(220, 220, 224), (20, 24, 30), (60, 90, 150)]),
    'art_deco': dict(
        budget=10, label='Art déco', sky='dawn', kind='stone', wet=False,
        walls=[(238, 218, 168), (230, 200, 150), (244, 228, 188), (214, 190, 140)], trim=(222, 176, 70), dark=(22, 98, 92),
        accents=[(22, 120, 110), (126, 28, 54), (222, 176, 70), (28, 60, 100)],
        floors=(6, 11), fh=3.2, bay=2.4, width=(10, 15), depth=(12, 16), shape='tall', ww=.9, wh=1.9, sill=.75, gf=4.4,
        roofs=['stepped', 'stepped'], gap=(0., .5), ground=['shop', 'door', 'shop', 'lobby'], lit=.5, bands=True,
        p=dict(fire=0., awn=.3, ac=.1, plant=.1, chimney=0., blade=.6, tag=.05, ivy=0., poster=.1, shut=0., box=0., balcony=.2, pipe=.2, stoop=.3, canopy=.8, neon_vert=.7),
        roof_objs=['antenna'],
        names=['THÉÂTRE', 'CINÉMA', 'GRAND HÔTEL', 'BIJOUX', 'CAFÉ'], lamp='deco', tree='birch', backdrop='city', fog=.014, ground_k='marble',
        cars=[(24, 80, 76), (120, 24, 50), (236, 222, 180), (24, 28, 36)]),
    'industriel': dict(
        budget=12, label='Industriel', sky='overcast', kind='metal', wet=False,
        walls=[(110, 142, 152), (182, 112, 58), (168, 84, 50), (96, 120, 132), (206, 164, 56)], trim=(200, 196, 186), dark=(40, 44, 50),
        accents=[(244, 196, 30), (36, 110, 190), (200, 60, 40), (240, 240, 232)],
        floors=(2, 4), fh=4.0, bay=3.4, width=(12, 20), depth=(14, 20), shape='strip', ww=2.4, wh=1.0, sill=2.0, gf=4.6,
        roofs=['sawtooth', 'flat', 'sawtooth'], gap=(1., 3.), ground=['garage', 'garage', 'door'], lit=.35,
        p=dict(fire=.8, awn=0., ac=.2, plant=0., chimney=.7, blade=.2, tag=.9, ivy=0., poster=.1, shut=0., box=0., balcony=0., pipe=1., stoop=0., tower=.6),
        roof_objs=['roof_vent', 'roof_vent', 'water_tank', 'ac_unit'],
        names=['ATELIER', 'ENTREPÔT', 'GARAGE', 'USINE'], lamp='modern', tree='bush', backdrop='city', fog=.02, ground_k='stone',
        cars=[(240, 200, 40), (60, 100, 170), (200, 70, 50), (210, 210, 206)]),
    'mediterraneen': dict(
        budget=14, label='Méditerranéen', sky='day', kind='plaster', wet=False,
        walls=[(250, 246, 236), (252, 240, 220), (236, 196, 110), (250, 226, 196), (244, 244, 240)], trim=(255, 255, 250), dark=(60, 78, 100),
        accents=[(24, 100, 200), (24, 138, 170), (200, 60, 70), (40, 140, 90)],
        floors=(2, 3), fh=2.9, bay=2.6, width=(5, 8), depth=(8, 11), shape='arch', ww=.8, wh=1.4, sill=.95,
        roofs=['terrace', 'terracotta', 'dome', 'terrace'], gap=(0., .2), ground=['arch', 'door', 'arch', 'shop'], lit=.5,
        p=dict(fire=0., awn=.5, ac=.05, plant=.9, chimney=.1, blade=.3, tag=0., ivy=.3, poster=0., shut=.9, box=.9, balcony=.5, pipe=.1, stoop=.4, bougainvillea=.7),
        roof_objs=['roof_vent'],
        names=['TAVERNE', 'OLIVES', 'POISSON', 'GLACES', 'ÉPICES'], lamp='lantern', tree='palm', backdrop='islands', fog=.01, ground_k='cobble', blue_dome=(30, 100, 200),
        cars=[(236, 236, 230), (30, 100, 200), (210, 150, 40)], roof_cols=[(206, 100, 62), (190, 86, 56)]),
    'neon_nuit': dict(
        budget=14, label='Nuit au néon', sky='night', kind='panels', wet=True,
        walls=[(46, 42, 82), (36, 52, 90), (70, 38, 84), (34, 40, 56)], trim=(90, 86, 130), dark=(18, 20, 36),
        accents=[(255, 40, 170), (30, 230, 255), (80, 255, 130), (255, 170, 30), (170, 90, 255)],
        floors=(6, 10), fh=2.9, bay=2.0, width=(5, 8), depth=(9, 13), shape='sq', ww=1.0, wh=1.3, sill=.85,
        roofs=['flat'], gap=(0., .6), ground=['shop', 'shop', 'door', 'shop'], lit=.65,
        p=dict(fire=.25, awn=.5, ac=.9, plant=.3, chimney=0., blade=0., tag=.7, ivy=0., poster=.7, shut=0., box=.1, balcony=.2, pipe=.9, stoop=0., neon_vert=1., neon_band=1.),
        roof_objs=['water_tank', 'ac_unit', 'antenna', 'satellite_dish', 'roof_vent'],
        names=['RAMEN', 'KARAOKÉ', 'BAR', 'HÔTEL', '24H', 'DISQUES', 'PHARMACIE'], lamp='neon', tree=None, backdrop='city', fog=.03, ground_k='stone',
        cars=[(240, 60, 150), (40, 220, 240), (30, 30, 40), (250, 190, 40)]),
    'cite_couleurs': dict(
        budget=18, label='Cité colorée', sky='day', kind='panels', wet=False,
        walls=[(176, 170, 158), (164, 168, 172), (184, 174, 158)], trim=(236, 232, 222), dark=(58, 60, 72),
        accents=[(232, 112, 24), (20, 150, 164), (236, 190, 24), (214, 44, 80), (70, 150, 60), (52, 92, 200)],
        floors=(5, 8), fh=2.9, bay=3.0, width=(14, 22), depth=(9, 12), shape='sq', ww=1.2, wh=1.3, sill=.9,
        roofs=['flat'], gap=(3., 7.), ground=['door', 'win', 'garage', 'win'], upper='panelwin', lit=.45,
        p=dict(fire=0., awn=0., ac=.2, plant=.3, chimney=0., blade=0., tag=.6, ivy=.1, poster=.1, shut=0., box=.1, balcony=1., pipe=.4, stoop=0., laundry=.7, dish=.6),
        roof_objs=['satellite_dish', 'roof_vent', 'water_tank'],
        names=['TABAC', 'PRESSING', 'ÉPICERIE'], lamp='modern', tree='tree_round', backdrop='hills', fog=.014, ground_k='concrete', lawn=False,
        cars=[(240, 126, 30), (30, 170, 180), (226, 60, 90), (240, 240, 232)]),
}
ORDER = tuple(IDENTITES)
ALIASES = {'brique': 'brique_rouge', 'brick': 'brique_rouge', 'pastel': 'crepi_pastel', 'crepi': 'crepi_pastel', 'bois': 'bois', 'wood': 'bois',
           'verre': 'verre_acier', 'glass': 'verre_acier', 'deco': 'art_deco', 'art deco': 'art_deco', 'industrie': 'industriel', 'industrial': 'industriel',
           'mediterranee': 'mediterraneen', 'meditérranéen': 'mediterraneen', 'neon': 'neon_nuit', 'nuit': 'neon_nuit', 'cite': 'cite_couleurs', 'hlm': 'cite_couleurs'}


def identity(name, seed=0):
    """nom (ou alias, ou None = choisi par la graine) -> clé d'IDENTITES"""
    if isinstance(name, str):
        k = name.strip().lower().replace(' ', '_').replace('-', '_')
        k = ALIASES.get(k, ALIASES.get(name.strip().lower(), k))
        if k in IDENTITES: return k
    return ORDER[int(seed) % len(ORDER)]


# ================================================================================================ le plan d'un bâtiment
def _pick(rng, seq):
    return seq[int(rng.integers(0, len(seq)))]


def _jit(c, rng, a=.07):
    return tuple(int(max(0, min(255, v * (1 + (rng.random() - .5) * 2 * a)))) for v in c)


def _plan(ident, rng, n, front, rect, near=True, seed=0, top=None):
    """UN bâtiment : dimensions, couleurs, grille de travées (fenêtres, portes, vitrines), détails. Lu par les deux peintres.

    `front` : face tournée vers la rue ('+x', '-x', '-z', '+z') ; `rect` : (x0, z0, x1, z1) en mètres ; `near` : le bâtiment reçoit ses
    détails en volume (balcons, auvents...), sinon ils sont peints à plat (les bâtiments lointains restent riches sans coûter de boîtes)."""
    I = IDENTITES[ident]
    x0, z0, x1, z1 = rect
    along_z = front in ('+x', '-x')
    Wf = (z1 - z0) if along_z else (x1 - x0)
    D = (x1 - x0) if along_z else (z1 - z0)
    nf = int(rng.integers(I['floors'][0], I['floors'][1] + 1)); fh = I['fh']; gf = I.get('gf', fh + .5)
    if top is not None: nf = max(1, int(round((top - gf) / fh)) + 1)
    H = gf + (nf - 1) * fh
    body = _jit(_pick(rng, I['walls']), rng, .04)
    bays = max(1, int(round(Wf / I['bay'])))
    P = I['p']
    fy = [0.] + [gf + k * fh for k in range(nf - 1)]
    fhs = [gf] + [fh] * (nf - 1)
    cells = []
    lit_rows = rng.random(nf) < .35
    door_bay = int(rng.integers(0, bays))
    fire_bay = None
    if nf >= 3 and rng.random() < P.get('fire', 0.): fire_bay = int(rng.integers(0, bays))
    if fire_bay == door_bay and bays > 1: fire_bay = (fire_bay + 1) % bays
    acc = I['accents']
    for f in range(nf):
        row = []
        for b in range(bays):
            cell = {'t': 'win', 'lit': bool(rng.random() < min(.95, I['lit'] * (1.7 if lit_rows[f] else .8))), 'in': _pick(rng, ROOMS_LIT),
                    'curt': _pick(rng, ROOM_CURT) if rng.random() < .75 else None, 'who': int(_pick(rng, (0, 0, 0, 1, 1, 2, 2, 3, 4))), 'half': bool(rng.random() < .35),
                    'shade': _pick(rng, ROOM_SHADE)}
            if f == 0:
                kind = 'door' if b == door_bay else _pick(rng, I['ground'])
                if kind == 'win' and near and rng.random() < .5 and len(I['ground']) > 1: kind = 'door'
                cell['t'] = kind
                cell['col'] = _pick(rng, acc)
                cell['lamp'] = bool(rng.random() < .75)
                if kind in ('shop', 'garage') and bays == 1: cell['t'] = 'door'
                if cell['t'] == 'shop':
                    cell['name'] = _pick(rng, I['names']); cell['lit'] = bool(rng.random() < .85)
                    if rng.random() < P.get('awn', 0.): cell['awn'] = (_pick(rng, acc), (244, 240, 230))
                    if I.get('p', {}).get('neon_band'): cell['neon'] = _pick(rng, acc)
                    if rng.random() < P.get('blade', 0.): cell['blade'] = cell['name']
                if cell['t'] == 'arch': cell['plant'] = bool(rng.random() < .6)
            else:
                up = I.get('upper')
                if up == 'pane': cell['t'] = 'pane'
                elif up == 'panelwin' and b % 2 == 1: cell = {'t': 'panel', 'col': _pick(rng, acc)}
                if cell['t'] == 'win':
                    if rng.random() < P.get('shut', 0.): cell['shut'] = _jit(_pick(rng, acc), rng, .03)
                    if rng.random() < P.get('box', 0.): cell['box'] = [_pick(rng, FLOWERS) for _ in range(3)]
                    if rng.random() < P.get('ac', 0.): cell['ac'] = True
                    if f == nf - 1 and I['shape'] in ('arch', 'sq') and rng.random() < .15: cell['shape'] = 'round'
                    if rng.random() < P.get('balcony', 0.) and f >= 1 and bays >= 2:
                        cell['t'] = 'bdoor'; cell['bal'] = dict(w=Wf / bays * .82, slab=_c_light(I['trim'], .9), rail=_pick(rng, I['accents']) if rng.random() < .5 else I['dark'],
                                                                   kind=_pick(rng, ('rail', 'rail', 'solid')), plants=bool(rng.random() < .55), laundry=bool(rng.random() < P.get('laundry', .15)))
                if fire_bay == b and f >= 1: cell['t'] = 'bdoor'; cell['fire'] = True; cell.pop('bal', None)
            row.append(cell)
        cells.append(row)
    if near:                                                                         # budget de volume : au-delà, le détail reste PEINT à plat (coût par boîte, mesuré)
        cand = [(f, b, k, c) for f, row in enumerate(cells) for b, cell in enumerate(row) for k, c in (('bal', 12), ('ac', 3), ('box', 2)) if cell.get(k)]
        order = rng.permutation(len(cand)); left = int(I.get('budget', 30))
        for i in order:
            f, b, k, c = cand[int(i)]
            if left >= c: left -= c
            else: cells[f][b]['flat'] = cells[f][b].get('flat', []) + [k]
    desc = dict(id=f'qtb{n}', ident=ident, front=front, rect=tuple(float(v) for v in rect), W=float(Wf), D=float(D), floors=nf, fh=fh, gf=gf, H=float(H), fy=fy, fhs=fhs,
                body=body, trim=I['trim'], dark=I['dark'], accent=_pick(rng, acc), bays=bays, cells=cells, seed=int(seed), near=bool(near), fire_bay=fire_bay, door_bay=door_bay)
    desc['roof'] = _pick(rng, I['roofs'])
    desc['roof_col'] = _pick(rng, I.get('roof_cols') or [(70, 70, 76)])
    desc['chimneys'] = [round(float(rng.uniform(.18, .82)) * Wf, 2) for _ in range(int(rng.random() < P.get('chimney', 0.)) + int(rng.random() < P.get('chimney', 0.) * .4))]
    desc['roof_objs'] = [(_pick(rng, I['roof_objs']), float(rng.uniform(.15, .85)), float(rng.uniform(.2, .8))) for _ in range(int(rng.integers(1, 4)))] if I.get('roof_objs') else []
    desc['stoop'] = bool(rng.random() < P.get('stoop', 0.)); desc['porch'] = bool(rng.random() < P.get('porch', 0.)); desc['canopy'] = bool(rng.random() < P.get('canopy', 0.))
    desc['tower'] = bool(rng.random() < P.get('tower', 0.)); desc['ivy'] = bool(rng.random() < P.get('ivy', 0.)); desc['boug'] = bool(rng.random() < P.get('bougainvillea', 0.))
    desc['neon_vert'] = [dict(u=float(rng.uniform(.06, .94)) * Wf, h=float(rng.uniform(2.6, 5.2)), y=float(rng.uniform(gf * .8, max(gf, H * .5))), col=_pick(rng, acc), text=_pick(rng, I['names']))
                         for _ in range(int(rng.integers(1, 3)) if rng.random() < P.get('neon_vert', 0.) else 0)]
    desc['tags'] = []
    if rng.random() < P.get('tag', 0.):
        for _ in range(int(rng.integers(1, 3))):
            u = float(rng.uniform(.05, .7)) * Wf; desc['tags'].append((u, .5, u + float(rng.uniform(1.4, 2.6)), float(rng.uniform(1.4, 2.4))))
    desc['posters'] = [(float(rng.uniform(.05, .9)) * Wf, .9, .55, .8) for _ in range(int(rng.integers(1, 3)) if rng.random() < P.get('poster', 0.) else 0)]
    desc['pipes'] = [round(float(rng.uniform(.03, .97)) * Wf, 2) for _ in range(max(1, bays // 3))] if rng.random() < P.get('pipe', 0.) else []
    desc['bands'] = bool(I.get('bands')); desc['dish'] = bool(rng.random() < P.get('dish', 0.))
    return desc


@functools.lru_cache(maxsize=512)
def building(ident, n, front, rect, near=True, seed=0, top=None):
    """le plan d'un bâtiment, refait à l'identique à partir de sa clé (graine = quartier + numéro) : la clé tient dans un bloc de décor sans
    emporter le plan avec elle, et le plan est partagé (ne pas le modifier)."""
    rng = np.random.default_rng((int(seed) * 1000003 + int(n) * 7919 + zlib.crc32(ident.encode())) & 0x7fffffff)
    return _plan(ident, rng, n, front, tuple(float(v) for v in rect), bool(near), int(seed) * 1000 + int(n), top)


ROOMS_LIT = ((255, 214, 148), (255, 188, 130), (255, 226, 176), (210, 226, 255), (255, 176, 190), (190, 255, 214), (255, 238, 140), (226, 196, 255))
ROOM_SHADE = ((230, 90, 70), (240, 170, 50), (90, 150, 230), (200, 90, 200), (90, 190, 120))
FLOWERS = ((236, 60, 90), (250, 210, 50), (250, 250, 250), (200, 90, 230), (255, 130, 60))


def _c_light(c, f):
    return tuple(int(min(255, v * (1 + (1 - f)))) for v in c)


def plan_face(desc, role, night):
    """le plan peint d'UNE face d'un bâtiment (le peintre `qt_facade.paint` n'a besoin que de lui). role = 'front' | 'side' | 'back'"""
    I = IDENTITES[desc['ident']]
    rng = np.random.default_rng((desc['seed'] * 977 + {'front': 1, 'side': 2, 'back': 3}[role] * 31) & 0x7fffffff)
    if role == 'front':
        Wf, cells, bays = desc['W'], desc['cells'], desc['bays']
        fy, fhs = desc['fy'], desc['fhs']
    else:
        Wf = desc['D']; bays = max(1, int(round(Wf / (I['bay'] * 1.5))))
        cells = []
        for f in range(desc['floors']):
            row = []
            for b in range(bays):
                blank = rng.random() < (.45 if role == 'back' else .3)
                c = {'t': 'blank' if blank else 'win', 'lit': bool(rng.random() < I['lit'] * .8), 'in': _pick(rng, ROOMS_LIT), 'curt': _pick(rng, ROOM_CURT) if rng.random() < .7 else None,
                     'who': int(_pick(rng, (0, 0, 0, 1, 2, 3))), 'half': bool(rng.random() < .3), 'shade': _pick(rng, ROOM_SHADE)}
                if I.get('upper') == 'pane' and not blank: c['t'] = 'pane'
                row.append(c)
            cells.append(row)
        fy, fhs = desc['fy'], desc['fhs']
    plan = dict(I=I, W=Wf, H=desc['H'] + (.1 if role == 'front' else .1), kind=I['kind'], col=desc['body'], trim=desc['trim'], dark=desc['dark'], bays=bays, floors=desc['floors'], fy=fy, fhs=fhs,
                cells=cells, seed=desc['seed'] + (0 if role == 'front' else 7 if role == 'side' else 13), far=not desc['near'], ww=I['ww'], wh=I['wh'], sill=I['sill'], shape=I['shape'],
                wear=1. if I['kind'] != 'glass' else 0.)
    bands = []
    if desc['bands'] or I['kind'] in ('brick', 'stone'):
        for f in range(1, desc['floors']):                                           # un cordon à chaque étage (pierre, or...)
            if desc['bands'] or f % 2 == 0: bands.append((fy[f] - .12, .2, _c_light(desc['trim'], .85) if I['kind'] == 'brick' else desc['trim']))
    bands.append((desc['H'] - .32, .34, desc['trim']))                               # corniche : bandeau haut
    plan['bands'] = bands
    plan['plinth'] = (.55, _c_light(desc['dark'], 1.25)) if I['kind'] in ('brick', 'plaster', 'stone', 'siding') else None
    if I['kind'] == 'stone':                                                         # pilastres cannelés entre les travées
        bw = Wf / bays
        plan['pilasters'] = [(k * bw - .13, k * bw + .13, _c_light(desc['trim'], .98)) for k in range(0, bays + 1)]
    if role == 'front':
        plan['tags'] = desc['tags']; plan['posters'] = desc['posters']; plan['pipes'] = desc['pipes']; plan['ivy'] = desc['ivy']
        if I['p'].get('neon_band') and night:
            plan['neons'] = [(float(rng.uniform(0, Wf * .6)), float(fy[f] + fhs[f] * .92), _pick(rng, I['accents']), float(rng.uniform(1.0, 3.0))) for f in range(1, desc['floors']) if rng.random() < .45]
        if I.get('lamp') == 'lantern' and night:
            plan['strings'] = [(.3, desc['gf'] + .2, Wf - .6, [(255, 220, 120), (255, 120, 90), (120, 200, 255)])]
    else:
        plan['pipes'] = desc['pipes'][:1]
    return plan


# ================================================================================================ clé d'épisode `diversite`
PRESETS = {
    'decors': dict(exterieurs=True, interieurs=True),                  # ce que pose le profil « production »
    'quartiers': dict(exterieurs=True, interieurs=False),
    'interieurs': dict(exterieurs=False, interieurs=True),
}


def configure(spec, episode=None):
    """`spec` = la clé d'épisode `diversite` : None / False (absente), un nom de PRESETS, ou {"quartier": nom, "ambiance": nom, "seed": n, "exterieurs": bool, "interieurs": bool}.
    -> l'état résolu, ou None. Appelé une fois par moteur, comme facades.configure."""
    global _STATE
    _STATE = None
    if not spec: return None
    if spec is True: name, over = 'decors', {}
    elif isinstance(spec, str): name, over = spec, {}
    elif isinstance(spec, dict):
        name = spec.get('style') or spec.get('preset') or 'decors'; over = {k: v for k, v in spec.items() if k not in ('style', 'preset')}
    else: return None
    if name not in PRESETS: return None
    st = dict(PRESETS[name]); st['name'] = name
    for k in ('exterieurs', 'interieurs'):
        if k in over: st[k] = bool(over[k])
    st['quartier'] = over.get('quartier'); st['ambiance'] = over.get('ambiance')
    try: st['seed'] = int(over.get('seed', 0))
    except (TypeError, ValueError): st['seed'] = 0
    ep = episode if isinstance(episode, dict) else {}
    st['base'] = (zlib.crc32(str(ep.get('title', '')).encode('utf-8')) & 0xffff) if 'seed' not in over else 0     # un épisode = un quartier, et pas le même qu'un autre
    _STATE = st
    return st


def use(state):
    """re-pose l'état avant de rendre (le pool « spawn » reconstruit le moteur par processus)"""
    global _STATE
    _STATE = state
    return state


def active(): return _STATE


def signature():
    """clé de cache pour les lieux construits sous cet état (voxelgpu/b_sets.get)"""
    s = _STATE
    return '' if not s else f"qt:{s['name']}:{int(s['exterieurs'])}{int(s['interieurs'])}:{s['quartier']}:{s['ambiance']}:{s['seed']}:{s['base']}"


def notices(ep):
    """ce que fait la clé, dit en français dans le journal de rendu"""
    s = _STATE
    if not s: return []
    out = [f'décors « {s["name"]} » : quartiers à identité ({", ".join(IDENTITES[k]["label"] for k in ORDER[:3])}...), intérieurs à palette et détails ; '
           f'sans cette clé les lieux livrés restent identiques']
    out.append('décors : en PS1 le relief des fenêtres est peint, balcons / auvents / enseignes sont de vraies boîtes ; en VOXEL tout est construit en volume')
    return out
