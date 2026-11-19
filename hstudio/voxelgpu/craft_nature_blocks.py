"""Craft : blocs de terrain et minerais (suite de craft_nature.py). Un bloc fait 16 voxels = 1 m : un cube plein + quelques plaques fines posées sur les faces (style du studio :
peu de boîtes, teintes de la palette, aucun bruit de couleur ; le grain est ajouté par le peintre)."""
import math
from .craft import PAL
from .craft_nature import recipe, tilt, U, pick, shade, mix, EX

S = 16; H = 8.
T = .5                                                                          # épaisseur des plaques posées sur les faces


def cube(m, color): m.box(-H, 0, -H, S, S, S, color)


def plate(m, face, u, v, w, h, color, emis=0., t=T):
    """une plaque sur une face : f devant (u le long de x, v en hauteur), r droite (u le long de z), l gauche, t dessus (u le long de x, v le long de z)"""
    if face == 'f': m.box(-H + u, v, H, w, h, t, color, emis=emis)
    elif face == 'r': m.box(H, v, -H + u, t, h, w, color, emis=emis)
    elif face == 'l': m.box(-H - t, v, -H + u, t, h, w, color, emis=emis)
    elif face == 't': m.box(-H + u, S, -H + v, w, t, h, color, emis=emis)


def scatter(m, base_cols, n, size=(2.4, 4.4), faces='frt', emis=0.):
    """des taches irrégulières de teintes données, réparties sur les faces visibles"""
    for k in range(n):
        f = faces[k % len(faces)]; w, h = U(m, *size), U(m, *size)
        plate(m, f, U(m, 1, S - w - 1), U(m, 1, S - h - 1), w, h, pick(m, *base_cols), emis=emis)


def block(name, label, base, cols, n=7, variants=1, size=(2.4, 4.4), extra=None, group='Blocs'):
    def fn(m, seed=0):
        cube(m, base); scatter(m, cols, n, size)
        if extra: extra(m, seed)
    recipe(name, group=group, label=label, variants=variants)(fn)


block('block_dirt', 'Terre', PAL['dirt'], [PAL['mud'], shade(PAL['dirt'], 1.15), PAL['stone_dark']], n=8, variants=2)
block('block_stone', 'Pierre', PAL['stone'], [PAL['stone_dark'], PAL['stone_light']], n=8, variants=2)
block('block_sand', 'Sable', PAL['sand'], [PAL['straw'], shade(PAL['sand'], .88)], n=6, variants=2)
block('block_clay', 'Argile', PAL['clay'], [shade(PAL['clay'], .85), shade(PAL['clay'], 1.1)], n=5)
block('block_mud', 'Boue', PAL['mud'], [shade(PAL['mud'], 1.3), shade(PAL['mud'], .75)], n=6)
block('block_gravel', 'Gravier', PAL['stone_dark'], [PAL['stone'], PAL['cobble'], PAL['straw'], PAL['stone_light']], n=14, size=(3, 5), variants=2)
block('block_snow', 'Neige', PAL['snow'], [PAL['ice'], PAL['white']], n=5)


@recipe('block_grass', group='Blocs', label='Terre herbeuse', variants=2)
def block_grass(m, seed=0):
    cube(m, PAL['dirt']); m.box(-H - .3, 12.4, -H - .3, S + .6, 3.9, S + .6, PAL['grass'])
    for f in 'fr':
        for k in range(3): plate(m, f, U(m, 1, 12), 9.2 + U(m, 0, 1.4), U(m, 3, 5), 3.4, PAL['grass'], t=.9)
    scatter(m, [PAL['mud'], PAL['stone_dark']], 4, faces='fr', size=(2, 3))


@recipe('block_cobble', group='Blocs', label='Pavés', variants=2)
def block_cobble(m, seed=0):
    cube(m, shade(PAL['stone_dark'], .9))
    for f in 'fr':
        for r in range(3):
            for c in range(3): plate(m, f, 1 + c * 5 + (r % 2) * 1.5, 1 + r * 5, 4.2, 4, pick(m, PAL['stone'], PAL['cobble'], PAL['stone_light']))
    for r in range(3):
        for c in range(3): plate(m, 't', 1 + c * 5 + (r % 2) * 1.5, 1 + r * 5, 4.2, 4, pick(m, PAL['stone'], PAL['cobble'], PAL['stone_light']))


@recipe('block_sandstone', group='Blocs', label='Grès', variants=1)
def block_sandstone(m, seed=0):
    cube(m, mix(PAL['sand'], PAL['clay'], .25))
    for y in (3, 8, 13): m.box(-H - .3, y, -H - .3, S + .6, 1.8, S + .6, shade(PAL['sand'], .85))
    m.box(-H, S, -H, S, T, S, PAL['sand'])


@recipe('block_ice', group='Blocs', label='Glace', variants=1)
def block_ice(m, seed=0):
    cube(m, PAL['ice'])
    for f in 'frt': plate(m, f, 3, 3, 1, 9, PAL['white']); plate(m, f, 4, 8, 7, 1, PAL['white']); plate(m, f, 10, 2, 1, 5, PAL['white'])


@recipe('block_volcanic_glass', group='Blocs', label='Roche vitrifiée sombre', variants=1)
def block_volcanic_glass(m, seed=0):
    cube(m, PAL['black'])
    for f in 'frt':
        plate(m, f, 2, 3, 12, 1.2, EX['violet']); tilt(m, rz=.5); plate(m, f, 3, 9, 9, 1, EX['lilac'])


@recipe('block_lava', group='Blocs', label='Lave', variants=1)
def block_lava(m, seed=0):
    cube(m, PAL['coal'])
    for f in 'frt':
        for k in range(3): plate(m, f, U(m, 1, 9), U(m, 1, 9), U(m, 4, 7), U(m, 3, 6), PAL['lava'], emis=1.4)
    m.light(0, 8, 9, PAL['lava'], power=1.0, radius=3.2)


@recipe('block_water', group='Blocs', label='Eau', variants=1)
def block_water(m, seed=0):
    cube(m, PAL['water']); m.box(-H, S, -H, S, T, S, mix(PAL['water'], PAL['ice'], .3))
    for f in 'fr': plate(m, f, 1, 11, 10, 1, mix(PAL['water'], PAL['white'], .45)); plate(m, f, 5, 5, 9, 1, mix(PAL['water'], PAL['white'], .45))


@recipe('block_log', group='Blocs', label='Tronc', variants=2)
def block_log(m, seed=0):
    cube(m, mix(PAL['bark'], PAL['wood'], .5)); m.box(-7, S, -7, 14, T, 14, PAL['wood_light']); m.box(-4.4, S + .2, -4.4, 8.8, T, 8.8, PAL['wood']); m.box(-2, S + .4, -2, 4, T, 4, PAL['wood_light'])
    for f in 'fr':
        for x in (3, 7, 12): plate(m, f, x, 1, 1.2, 14, PAL['bark'])


@recipe('block_planks', group='Blocs', label='Planches', variants=1)
def block_planks(m, seed=0):
    cube(m, PAL['plank'])
    for f in 'fr':
        for y in (4, 8, 12): plate(m, f, 0, y, S, .8, PAL['wood_dark'])
        for y in (2, 6, 10, 14): plate(m, f, 1.4, y, 1, 1, PAL['black']); plate(m, f, 13.6, y, 1, 1, PAL['black'])


def brick_face(m, f, mortar_col, col, rows=4):
    for r in range(rows):
        off = 3.5 if r % 2 else 0
        for c in range(3):
            x = off + c * 7 - (3.5 if r % 2 else 0)
            plate(m, f, max(0, x) + .6, r * 4 + .6, min(6.2, S - max(0, x) - .6), 3, pick(m, col, shade(col, .92), shade(col, 1.07)))


@recipe('block_stone_bricks', group='Blocs', label='Pierre taillée', variants=1)
def block_stone_bricks(m, seed=0):
    cube(m, PAL['stone_dark']); brick_face(m, 'f', PAL['stone_dark'], PAL['stone']); brick_face(m, 'r', PAL['stone_dark'], PAL['stone']); m.box(-H, S, -H, S, T, S, PAL['stone'])


@recipe('block_bricks', group='Blocs', label='Briques', variants=1)
def block_bricks(m, seed=0):
    cube(m, PAL['stone_light']); brick_face(m, 'f', PAL['stone_light'], PAL['brick']); brick_face(m, 'r', PAL['stone_light'], PAL['brick']); m.box(-H, S, -H, S, T, S, PAL['brick'])


@recipe('block_glass', group='Blocs', label='Verre', variants=1)
def block_glass(m, seed=0):
    cube(m, mix(PAL['glass'], PAL['ice'], .3))
    for f in 'fr':
        plate(m, f, 0, 0, S, 1.4, PAL['iron']); plate(m, f, 0, S - 1.4, S, 1.4, PAL['iron']); plate(m, f, 0, 0, 1.4, S, PAL['iron']); plate(m, f, S - 1.4, 0, 1.4, S, PAL['iron'])
        plate(m, f, 3, 3, 1.4, 9, PAL['white']); plate(m, f, 6, 3, 1, 5, PAL['white'])
    m.box(-H, S, -H, S, T, S, PAL['glass'])


# ------------------------------------------------------------------ minerais : de la pierre avec des veines
def ore(name, label, col, emis=0.):
    def fn(m, seed=0):
        cube(m, PAL['stone']); scatter(m, [PAL['stone_dark'], PAL['stone_light']], 4, faces='frt', size=(2, 3.4))
        for k in range(6):
            f = 'frt'[k % 3]; w = U(m, 3, 4.6); plate(m, f, U(m, 1, S - w - 1), U(m, 1, S - w - 1), w, U(m, 3, 4.6), col, emis=emis, t=.7)
    recipe('ore_' + name, group='Minerais', label=label, variants=2)(fn)


ore('coal', 'Charbon', PAL['coal'])
ore('iron', 'Fer', mix(PAL['iron'], PAL['clay'], .35))
ore('copper', 'Cuivre', PAL['copper'])
ore('gold', 'Or', PAL['gold'])
ore('gem', 'Gemmes', PAL['gem'], .9)
ore('ruby', 'Rubis', PAL['ruby'], .8)
ore('emerald', 'Émeraudes', PAL['leaf_light'], .8)
ore('amethyst', 'Améthyste', EX['violet'], .8)
ore('silver', 'Argent', PAL['iron'])
ore('sulfur', 'Soufre', PAL['cloth_yellow'], .3)
