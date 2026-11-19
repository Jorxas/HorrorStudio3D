"""Lieu prêt `cimetiere_calme` : un cimetière de petite ville, paisible et lisible (drame, deuil, souvenir — PAS l'horreur) (9 novembre 2026).

Né pour la série « Le Choix de Demain » (la tombe de Lina sous la pluie), rangé ici pour toute histoire. Le lieu `graveyard` existant reste celui de
l'horreur (nuit, arbres morts, château) ; celui-ci est clair : pelouse, allées de gravier, stèles grises soignées, fleurs, cyprès, petite chapelle.
    LIEUX = {'cimetiere': {'type': 'cimetiere_calme', 'sky': 'overcast', 'weather': 'rain',
                           'tombe': {'nom': 'LINA', 'texte': '18 ANS', 'fleurs': True, 'photo': True}}}

Uniquement des blocs, des décors (`props`) et des zones de sol : PS1 et VOXEL les dessinent de la même façon (aucune clé nouvelle du moteur).
Repère (mètres) : x vers la droite quand on regarde vers +z ; le portail est à z = 0 ; l'allée centrale (gravier, |x| < 1,1) monte vers +z ;
les tombes sont en rangées de part et d'autre (stèle au fond, à z = 5,9 / 10,9 / 15,9 / 20,9 ; dalle devant elle, vers le portail), une allée de gravier
transversale devant chaque rangée ; les visiteurs se tiennent devant la dalle (z de la stèle − 2,5) et regardent vers +z.
La TOMBE mise en avant (option `tombe`) : x = 3,0, stèle à z = 10,9 (face vers -z, granit sombre poli, texte gravé doré), dalle de z 9,0 à 10,8 ;
`fleurs` : bouquet détaillé de fleurs blanches (`od_bouquet`, lot drame) debout contre la droite de la stèle, `photo` (portrait) attachée à son ruban ; `fleurs: 'blocs'` : bouquet en blocs + cadre photo.

Options :
  tombe   {'nom': 'LINA', 'texte': '18 ANS', 'fleurs': True, 'photo': True, 'x': 3.0, 'rang': 2} (nom ≤ 8 caractères, texte ≤ 10, sans accent) ; False = aucune
  chapelle True (défaut) : la petite chapelle au fond (z 29 à 34)
  sky / weather comme tout lieu extérieur (défaut 'overcast', sans pluie)
Repères : entree, start, allee, tombe, devant_tombe, cote_tombe, banc, chapelle, rang1 … rang4.
"""
GREY = (168, 168, 164); GRANITE = (86, 88, 96); BORDER = (190, 188, 182); GOLD = (236, 206, 128)
LEAF = (60, 112, 58); WHITE_F = (246, 246, 240); WALL = (176, 170, 160)
ROWS = (5.9, 10.9, 15.9, 20.9)
COLS = (-8.2, -5.6, -3.0, 3.0, 5.6, 8.2)


def block(at, size, color, material='plaster', **kw):
    return dict(at=[round(float(x), 3) for x in at], size=[round(float(x), 3) for x in size], color=list(color), material=material, **kw)


def _grave(B, x, zs, k):
    """an ordinary grave: border, slab, headstone (three shapes), sometimes a pot of flowers ; deterministic from k"""
    sh = (k * 7) % 3; tone = 150 + (k * 13) % 36; col = (tone, tone, tone - 4)
    B += [block((x, 0, zs - .95), (1.15, .1, 1.95), BORDER, 'stone'), block((x, .1, zs - .97), (.98, .2, 1.8), col, 'stone')]
    h = .75 + .1 * ((k * 5) % 4)
    if sh == 0:                                                     # upright stone with a rounded top
        B += [block((x, .1, zs - .03), (.9, h, .15), col, 'stone'), block((x, .1 + h, zs - .03), (.7, .08, .15), col, 'stone'),
              block((x, .18 + h, zs - .03), (.4, .06, .15), col, 'stone')]
    elif sh == 1:                                                   # a stone cross on a base
        B += [block((x, .1, zs - .03), (.6, .3, .2), col, 'stone'), block((x, .4, zs - .03), (.14, h + .3, .14), col, 'stone'),
              block((x, .4 + h * .7, zs - .03), (.56, .13, .14), col, 'stone')]
    else:                                                           # low wide stone
        B += [block((x, .1, zs - .03), (1.0, h * .7, .18), col, 'stone'), block((x, .1 + h * .7, zs - .03), (1.06, .06, .22), col, 'stone')]
    if k % 3 != 1:                                                  # a pot of flowers on the slab
        fc = ((214, 70, 80), (240, 196, 70), (170, 120, 210), (240, 240, 236))[k % 4]
        B += [block((x + .25, .3, zs - .45), (.2, .18, .2), (150, 80, 60)), block((x + .25, .48, zs - .45), (.26, .14, .26), fc, 'fabric'),
              block((x + .25, .48, zs - .45), (.3, .06, .1), LEAF, 'fabric')]


def tomb_blocks(t):
    x = float(t.get('x', 3.0)); zs = ROWS[int(t.get('rang', 2)) - 1]
    B = [block((x, 0, zs - .95), (1.3, .12, 2.05), BORDER, 'stone'), block((x, .12, zs - 1.0), (1.08, .2, 1.8), GRANITE, 'stone'),
         block((x, .32, zs - 1.0), (1.0, .02, 1.7), (110, 112, 120), 'stone'),                     # polished top of the slab
         block((x, .12, zs - .04), (1.06, 1.0, .18), GRANITE, 'stone'), block((x, 1.12, zs - .04), (.86, .08, .18), GRANITE, 'stone'),
         block((x, 1.2, zs - .04), (.52, .06, .18), GRANITE, 'stone')]
    if t.get('fleurs') == 'blocs':
        # (option) a bouquet in plain blocks leaning on the headstone: paper cone, ribbon, leaves, blossoms ; by default the detailed `od_bouquet`
        bx, bz = x + .34, zs - .3                                                   # on the right of the headstone: the engraving stays visible
        B += [block((bx, .34, bz - .12), (.12, .12, .12), (232, 226, 206), 'card'), block((bx, .46, bz - .06), (.18, .14, .16), (232, 226, 206), 'card'),
              block((bx, .6, bz), (.24, .12, .18), (232, 226, 206), 'card'), block((bx, .55, bz - .02), (.26, .04, .2), (236, 170, 186), 'fabric')]
        for i, (dx, dy, dz) in enumerate(((-.09, .74, .02), (0, .78, .04), (.09, .74, .0), (-.05, .86, .06), (.05, .88, .05), (-.11, .84, .08), (.11, .82, .07), (0, .94, .08))):
            B.append(block((bx + dx, dy, bz + dz), (.08, .075, .075), WHITE_F, 'fabric'))
            B.append(block((bx + dx, dy + .025, bz + dz - .015), (.03, .03, .02), (250, 226, 120), 'fabric'))
        for dx, dy in ((-.15, .68), (.15, .68), (-.04, .68), (.08, .65)):
            B.append(block((bx + dx, dy, bz + .02), (.06, .08, .04), LEAF, 'fabric'))
    return B


def chapel_blocks():
    B = [block((0, 0, 31.5), (5.0, 4.2, 5.0), (214, 206, 190)), block((0, 4.2, 31.5), (5.4, .3, 5.4), (120, 80, 62), 'wood'),
         block((0, 4.5, 31.5), (4.2, .5, 5.4), (120, 80, 62), 'wood'), block((0, 5.0, 31.5), (3.0, .5, 5.4), (120, 80, 62), 'wood'),
         block((0, 5.5, 31.5), (1.8, .5, 5.4), (120, 80, 62), 'wood'), block((0, 6.0, 31.5), (.7, .4, 5.4), (120, 80, 62), 'wood'),
         block((0, 0, 28.96), (1.4, 2.4, .1), (96, 64, 44), 'door'), block((0, 2.4, 28.97), (1.6, .2, .1), (196, 190, 176)),
         block((0, 3.1, 28.96), (.7, .7, .06), (230, 200, 140), 'light', emissive=.5)]
    return B


def walls_blocks():
    B = []
    for sx in (-1, 1):
        B += [block((sx * 7.0, 0, -.4), (11.0, 1.1, .4), WALL, 'stone'), block((sx * 7.0, 1.1, -.4), (11.2, .1, .5), (196, 190, 180), 'stone'),
              block((sx * 12.6, 0, 12.8), (.4, 1.1, 26.4), WALL, 'stone'), block((sx * 1.5, 0, -.4), (.5, 1.8, .5), WALL, 'stone'),
              block((sx * 1.5, 1.8, -.4), (.6, .12, .6), (196, 190, 180), 'stone')]
    B.append(block((0, 0, 26.2), (25.6, 1.1, .4), WALL, 'stone'))
    return B


def cimetiere(spec):
    from .places import _base
    spec = spec or {}
    sky = spec.get('sky', 'overcast')
    zones = [{'rect': [-1.1, -3.0, 1.1, 26.0], 'ground': 'stone'}] + [{'rect': [-10.0, zs - 3.3, 10.0, zs - 2.3], 'ground': 'stone'} for zs in ROWS]
    o = _base(dict(spec, sky=sky), outdoor=True, sky=sky, ground='grass', backdrop=['hills', 'forest'], fog=.02, ambience='park', fill=.62,
              wet=bool(spec.get('weather') == 'rain'), zones=zones)
    t = spec.get('tombe', {'nom': 'LINA', 'texte': '18 ANS'})
    t = dict({'nom': 'LINA', 'texte': '18 ANS', 'fleurs': True, 'photo': True, 'x': 3.0, 'rang': 2}, **t) if t else None
    B = walls_blocks()
    k = 0
    for zs in ROWS:
        for x in COLS:
            k += 1
            if t and abs(x - float(t['x'])) < .1 and abs(zs - ROWS[int(t['rang']) - 1]) < .1: continue
            _grave(B, x, zs, k)
    if t: B += tomb_blocks(t)
    if spec.get('chapelle', True): B += chapel_blocks()
    o['blocks'] = list(spec.get('blocks', [])) + B
    P = o['props']
    P += [{'type': 'pine', 'at': [sx * 11.4, z], 'size': 1.35, 'color': [44, 92, 58]} for z in (3.0, 9.0, 15.0, 21.0) for sx in (-1, 1)]
    P += [{'type': 'tree_round', 'at': [6.9, 13.4], 'size': 1.3, 'color': [70, 118, 60]}, {'type': 'tree_round', 'at': [-6.9, 8.4], 'size': 1.2, 'color': [74, 122, 62]}]
    P += [{'type': 'bench', 'at': [-1.9, 12.6], 'rot': 1}, {'type': 'bush', 'at': [-3.0, 27.6], 'color': [60, 110, 60]}, {'type': 'bush', 'at': [3.0, 27.6], 'color': [60, 110, 60]}]
    if t:
        x = float(t['x']); zs = ROWS[int(t['rang']) - 1]
        lines = [str(t.get('nom', 'LINA'))[:8]] + ([str(t['texte'])[:10]] if t.get('texte') else [])
        # engraved text: a painted panel (`objets: False`), not the printed sheet the episode key `objets` would make of a `note`
        P.append({'type': 'note', 'at': [x - .14, zs - .135], 'y': .3, 'rot': 0, 'w': .64, 'text': lines, 'fs': 9, 'color': list(GRANITE), 'ink': list(GOLD), 'glow': .55, 'objets': False})
        ph = t.get('photo', True); ph = ('portrait' if ph is True else ph) if ph else False
        if t.get('fleurs', True) and t.get('fleurs') != 'blocs':
            # the detailed bouquet of white flowers (lot `drame`) standing against the right of the headstone, the photo tied to its ribbon
            P.append({'type': 'od_bouquet', 'at': [x + .3, zs - .36], 'y': .32, 'rot': 0, 'debout': True, 'photo': ph})
        elif ph:                                                                    # block bouquet: a framed photo in front of it
            P.append({'type': 'od_photo_frame', 'at': [x + .34, zs - .5], 'y': .34, 'rot': 0, 'photo': ph if ph in ('portrait', 'couple', 'famille', 'enfant') else 'portrait',
                      'largeur': .22, 'haut': .28})
    zt = ROWS[int(t['rang']) - 1] if t else 10.9; xt = float(t['x']) if t else 3.0
    o['anchors'] = dict(o.get('anchors') or {}, **{'entree': (0., 0.), 'start': (0., 2.0), 'allee': (0., 8.0), 'tombe': (xt, zt),
                                                   'devant_tombe': (xt, zt - 2.5), 'cote_tombe': (xt - 1.4, zt - 1.6), 'banc': (-1.9, 12.6), 'chapelle': (0., 28.5)})
    for i, zs in enumerate(ROWS): o['anchors'][f'rang{i + 1}'] = (0., zs - 2.8)
    return o


def register(PLACES):
    """adds the place `cimetiere_calme` ; nothing is replaced"""
    if 'cimetiere_calme' not in PLACES: PLACES['cimetiere_calme'] = cimetiere
