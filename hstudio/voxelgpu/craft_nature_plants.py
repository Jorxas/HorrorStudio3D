"""Craft : plantes, fleurs, champignons, cultures (suite de craft_nature.py, style du studio : peu de boîtes, teintes de la palette, aucun bruit)."""
import math
from .craft import PAL
from .craft_nature import recipe, mass, trunk, tilt, U, pick, shade, mix, EX, LEAF


# ------------------------------------------------------------------ fleurs : une tige fine, une feuille, une tête de quelques boîtes
def star(m, x, y, z, s, petal, center, cs=2.4):
    """une tête de fleur vue de face : quatre boîtes en étoile + un cœur"""
    for a in (0, .785, 1.571, 2.356): m.box(x - s / 2, y - .8, z - .4, s, 1.6, 1.2, petal); tilt(m, rz=a)
    m.box(x - cs / 2, y - cs / 2, z - .8, cs, cs, 1.8, center)


def flower_recipe(name, label, head, h=(8, 14), n=(3, 5), area=7, variants=2, stem=None):
    def fn(m, seed=0):
        for k in range(int(U(m, *n)) + 1):
            x, z = U(m, -area, area), U(m, -area * .7, area * .7); hh = U(m, *h)
            m.box(x - .5, 0, z - .5, 1, hh, 1, stem or PAL['leaf']); m.box(x, hh * .35, z - .6, 4.4, 1.2, 1.6, PAL['leaf_light']); tilt(m, rz=.5)
            head(m, x, hh, z, seed + k)
    recipe(name, group='Plantes', label=label, variants=variants)(fn)


def h_daisy(m, x, y, z, s): star(m, x, y + 1, z, 6.4, PAL['white'], PAL['gold'])
def h_poppy(m, x, y, z, s): star(m, x, y + 1, z, 5.6, PAL['ruby'], PAL['black'], 2)
def h_cornflower(m, x, y, z, s): star(m, x, y + 1, z, 5.6, EX['sky'], EX['violet'], 2)
def h_dandelion(m, x, y, z, s):
    if s % 2: m.box(x - 2, y, z - 2, 4, 4, 4, PAL['white']); m.box(x - 3, y + 1, z - 1, 6, 2, 2, PAL['white'])
    else: star(m, x, y + 1, z, 4.6, PAL['cloth_yellow'], PAL['gold'], 2.2)
def h_sunflower(m, x, y, z, s): star(m, x, y + 4, z, 11, PAL['cloth_yellow'], PAL['wood_dark'], 6)
def h_tulip(m, x, y, z, s):
    c = [PAL['ruby'], PAL['cloth_yellow'], PAL['pink'], PAL['white']][s % 4]; m.box(x - 1.6, y - 1, z - 1.6, 3.2, 3.4, 3.2, c); m.box(x - 2.2, y + 2, z - 2.2, 4.4, 2.6, 4.4, c)
def h_bluebell(m, x, y, z, s):
    for k in range(3): d = 1 if k % 2 else -1; m.box(x + d * 1.4 - 1.2, y - k * 2.2, z - 1.2, 2.4, 2.6, 2.4, EX['violet'] if k % 2 else PAL['cloth_blue'])
def h_lavender(m, x, y, z, s): m.box(x - 1, y - 8, z - 1, 2, 9, 2, EX['violet']); m.box(x - 1.8, y - 5, z - .6, 3.6, 2, 1.2, EX['lilac'])
def h_orchid(m, x, y, z, s):
    m.box(x - 3, y, z - .5, 6, 2.4, 1.2, EX['rose']); m.box(x - 1.2, y + 1, z - .5, 2.4, 3, 1.2, EX['rose']); m.box(x - 1.6, y - 1.6, z - .8, 3.2, 2.4, 2, EX['violet'])
def h_lily(m, x, y, z, s): star(m, x, y + 2, z, 6.4, PAL['white'], PAL['gold'], 2)
def h_rose(m, x, y, z, s):
    c = [PAL['ruby'], PAL['cloth_yellow'], PAL['pink']][s % 3]; m.box(x - 2.4, y - 1, z - 2.4, 4.8, 2.4, 4.8, shade(c, .85)); m.box(x - 1.8, y + 1.4, z - 1.8, 3.6, 2, 3.6, c); m.box(x - 1, y + 3.4, z - 1, 2, 1.4, 2, shade(c, 1.15))
def h_thistle(m, x, y, z, s): m.box(x - 2, y - 2, z - 2, 4, 3, 4, PAL['leaf']); m.box(x - 2.4, y + 1, z - 2.4, 4.8, 3, 4.8, EX['violet'])
def h_allium(m, x, y, z, s): mass(m, x, y - 1, z, 3.6, 3, 3.6, (EX['violet'], EX['lilac'], EX['lilac']))


flower_recipe('daisy', 'Marguerites', h_daisy)
flower_recipe('poppy', 'Coquelicots', h_poppy)
flower_recipe('cornflower', 'Bleuets', h_cornflower)
flower_recipe('dandelion', 'Pissenlits', h_dandelion)
flower_recipe('sunflower', 'Tournesols', h_sunflower, h=(22, 30), n=(1, 3), area=8)
flower_recipe('tulip', 'Tulipes', h_tulip, h=(8, 13), variants=4)
flower_recipe('bluebell', 'Jacinthes des bois', h_bluebell, h=(10, 15))
flower_recipe('lavender', 'Lavande', h_lavender, h=(8, 12), n=(5, 7))
flower_recipe('orchid', 'Orchidées', h_orchid, h=(9, 14), n=(2, 4))
flower_recipe('lily_flower', 'Lys', h_lily, h=(12, 18), n=(2, 4), variants=1)
flower_recipe('rose_bush', 'Rosiers', h_rose, h=(12, 18), n=(2, 4), variants=3, stem=PAL['leaf_dark'])
flower_recipe('thistle', 'Chardons', h_thistle, h=(10, 16), n=(3, 5), variants=1)
flower_recipe('allium', 'Alliums', h_allium, h=(14, 22), n=(2, 4), variants=1)


@recipe('bush', group='Plantes', label='Buisson', variants=3)
def bush(m, seed=0):
    mass(m, 0, 1, 0, U(m, 8, 10), U(m, 4, 5), U(m, 7, 9), LEAF)
    for k in range(2): mass(m, U(m, -7, 7), 1, U(m, -5, 5), U(m, 4, 5.5), 3, U(m, 4, 5.5), LEAF)
    m.box(-1, 0, -1, 2, 3, 2, PAL['bark'])


@recipe('berry_bush', group='Plantes', label='Buisson à baies', variants=3)
def berry_bush(m, seed=0):
    bush(m, seed); col = [PAL['ruby'], PAL['cloth_blue'], PAL['autumn']][seed % 3]
    for k in range(7): a = U(m, 0, 6.28); r = U(m, 8, 11); m.box(math.cos(a) * r - 1.1, U(m, 2.5, 8), math.sin(a) * r * .8 - 1.1, 2.2, 2.2, 2.2, col)


@recipe('flowering_bush', group='Plantes', label='Buisson fleuri', variants=3)
def flowering_bush(m, seed=0):
    bush(m, seed); col = [PAL['pink'], PAL['white'], PAL['cloth_yellow']][seed % 3]
    for k in range(8): a = U(m, 0, 6.28); r = U(m, 7, 11); m.box(math.cos(a) * r - 1.2, U(m, 3, 9), math.sin(a) * r * .8 - 1.2, 2.4, 2.4, 2, col)


@recipe('tall_grass', group='Plantes', label='Herbes hautes', variants=3)
def tall_grass(m, seed=0):
    for k in range(int(U(m, 12, 18))):
        x, z = U(m, -9, 9), U(m, -7, 7); h = U(m, 9, 20); m.box(x - .6, 0, z - .6, 1.2, h, 1.2, pick(m, PAL['grass'], PAL['leaf'], PAL['leaf_light'])); tilt(m, rz=U(m, -.25, .25))


@recipe('fern', group='Plantes', label='Fougère', variants=3)
def fern(m, seed=0):
    for k in range(6):
        a = k * math.pi / 3 + U(m, -.2, .2); L = U(m, 9, 13); m.box(1.5, 1.5, -1.5, L, 1.2, 3, pick(m, PAL['leaf'], PAL['leaf_light']), ry=-a); m.box(1.5 + L * .85, .4, -1.2, 3, 1.2, 2.4, PAL['leaf_dark'], ry=-a)
    m.box(-1.5, 0, -1.5, 3, 2.4, 3, PAL['leaf_dark'])


@recipe('reeds', group='Plantes', label='Roseaux et quenouilles', variants=2)
def reeds(m, seed=0):
    m.box(-10, 0, -10, 20, 1.2, 20, PAL['mud']); m.box(-6, 1.2, -5, 12, .5, 9, PAL['water'])
    for k in range(9):
        x, z = U(m, -9, 9), U(m, -9, 9); h = U(m, 18, 34); m.box(x - .5, 1.2, z - .5, 1, h, 1, pick(m, PAL['leaf'], PAL['straw'])); tilt(m, rz=U(m, -.12, .12))
        if k % 3 == 0: m.box(x - 1.2, 1.2 + h - 8, z - 1.2, 2.4, 6, 2.4, PAL['wood_dark'])


@recipe('lily_pads', group='Plantes', label='Nénuphars', variants=2)
def lily_pads(m, seed=0):
    m.box(-12, 0, -12, 24, 1.5, 24, PAL['water'])
    for k in range(4): s = U(m, 5, 8); m.box(U(m, -10, 5), 1.5, U(m, -10, 5), s, .8, s, PAL['leaf'])
    star(m, 2, 2.6, 3, 4.4, PAL['pink'], PAL['gold'], 1.8)


@recipe('hanging_vines', group='Plantes', label='Lianes sur mur', variants=2)
def hanging_vines(m, seed=0):
    m.box(-13, 0, -2.5, 26, 20, 3, PAL['stone']); m.box(-13, 8, -2.6, 12, 4, 3, PAL['stone_dark']); m.box(2, 14, -2.6, 11, 4, 3, PAL['stone_dark'])
    for k in range(7):
        x = U(m, -12, 11); ln = U(m, 6, 18); m.box(x, 20 - ln, .6, 1.2, ln, 1.2, pick(m, PAL['leaf_dark'], PAL['leaf'])); m.box(x - .8, 20 - ln - 1, .7, 2.8, 2, 1.4, PAL['leaf_light'])


@recipe('sugar_cane', group='Plantes', label='Canne à sucre', variants=2)
def sugar_cane(m, seed=0):
    m.box(-8, 0, -8, 16, 1.5, 16, PAL['sand'])
    for k in range(4):
        x, z = U(m, -5, 5), U(m, -5, 5); h = U(m, 18, 30); m.box(x - 1, 1.5, z - 1, 2, h, 2, mix(PAL['leaf'], PAL['straw'], .45)); m.box(x - 1.4, 1.5 + h * .5, z - 1.4, 2.8, 1.2, 2.8, PAL['leaf_dark'])
        m.box(x, 1.5 + h, z - .6, 4, 1.2, 1.2, PAL['leaf_light']); tilt(m, rz=.4)


@recipe('cactus', group='Plantes', label='Cactus', variants=3)
def cactus(m, seed=0):
    m.box(-8, 0, -8, 16, 1.5, 16, PAL['sand']); h = U(m, 20, 30); g = mix(PAL['leaf'], PAL['leaf_dark'], .3)
    m.box(-2.5, 1.5, -2.5, 5, h, 5, g); m.box(-.4, 1.5, 2.4, .8, h - 1, .5, PAL['leaf_dark'])
    for a in range(int(U(m, 1, 3)) + 1):
        s = 1 if a % 2 else -1; y = U(m, h * .35, h * .65); m.box(s * 2.5 - (0 if s > 0 else 5), y, -2, 5, 4, 4, g); m.box(s * 6 - 2, y, -2, 4, U(m, 6, 11), 4, g)
    if seed % 2: m.box(-1.5, h + 1.5, -1.5, 3, 2, 3, PAL['pink'])


@recipe('seaweed', group='Plantes', label='Algues', variants=2)
def seaweed(m, seed=0):
    m.box(-10, 0, -10, 20, 1.5, 20, mix(PAL['sand'], PAL['water'], .35))
    for k in range(6):
        x, z = U(m, -8, 8), U(m, -8, 8); h = U(m, 14, 30); c = pick(m, PAL['leaf'], PAL['leaf_dark']); m.box(x - .8, 1.5, z - .8, 1.6, h * .6, 1.6, c); m.box(x - .8 + U(m, -1.5, 1.5), 1.5 + h * .6, z - .8, 1.6, h * .4, 1.6, PAL['leaf_light'])
    m.box(-6, 1.5, 4, 5, 3, 4, PAL['stone']); m.box(4, 1.5, -5, 4, 2.4, 4, PAL['stone_dark'])


@recipe('moss_patch', group='Plantes', label='Mousse', variants=2)
def moss_patch(m, seed=0):
    for k in range(6): m.box(U(m, -9, 5), 0, U(m, -7, 4), U(m, 5, 9), U(m, .8, 1.6), U(m, 4, 8), pick(m, PAL['leaf'], PAL['leaf_light'], PAL['grass']))
    m.box(3, .8, 2, 1.8, 2.4, 1.8, PAL['white']); m.box(-6, .8, -2, 1.8, 2, 1.8, PAL['cloth_yellow'])


# ------------------------------------------------------------------ champignons
def mushroom(m, x, z, h, capw, cap, stem=None, spots=True, emis=0.):
    stem = stem or PAL['bone']; sw = max(2., capw * .3)
    m.box(x - sw / 2, 0, z - sw / 2, sw, h, sw, stem)
    m.box(x - capw / 2, h, z - capw / 2, capw, 1.6, capw, shade(cap, .7))
    m.box(x - capw / 2 + .8, h + 1.6, z - capw / 2 + .8, capw - 1.6, 2.2, capw - 1.6, cap, emis=emis)
    m.box(x - capw / 2 + 2.6, h + 3.8, z - capw / 2 + 2.6, max(1.5, capw - 5.2), 1.6, max(1.5, capw - 5.2), shade(cap, 1.12), emis=emis)
    if spots:
        m.box(x - capw * .25, h + 3.7, z + capw * .1, 1.6, 1, 1.6, PAL['white']); m.box(x + capw * .1, h + 3.7, z - capw * .22, 1.4, 1, 1.4, PAL['white'])


def mush_recipe(name, label, cap, n, size, h, variants=2, **kw):
    def fn(m, seed=0):
        m.box(-9, 0, -9, 18, .8, 18, mix(PAL['dirt'], PAL['leaf'], .35))
        for k in range(int(U(m, *n))): mushroom(m, U(m, -6, 6), U(m, -6, 6), U(m, *h), U(m, *size), cap, **kw)
    recipe(name, group='Champignons', label=label, variants=variants)(fn)


mush_recipe('mushroom_red', 'Amanites', PAL['ruby'], (3, 5), (6, 9), (4, 8))
mush_recipe('mushroom_brown', 'Champignons bruns', mix(PAL['wood'], PAL['clay'], .3), (3, 5), (6, 9), (4, 8), spots=False)
mush_recipe('mushroom_yellow', 'Girolles', PAL['gold'], (3, 5), (5, 7), (3, 6), spots=False)
mush_recipe('mushroom_purple', 'Pieds violets', EX['violet'], (3, 5), (5, 7), (3, 6))


@recipe('giant_mushroom_red', group='Champignons', label='Champignon géant rouge', variants=2)
def giant_mushroom_red(m, seed=0):
    mushroom(m, 0, 0, U(m, 26, 34), U(m, 22, 28), PAL['ruby']); mushroom(m, 13, 6, 12, 10, PAL['ruby']); mushroom(m, -12, 8, 9, 8, PAL['ruby'])


@recipe('giant_mushroom_brown', group='Champignons', label='Champignon géant brun', variants=2)
def giant_mushroom_brown(m, seed=0):
    mushroom(m, 0, 0, U(m, 22, 30), U(m, 26, 32), mix(PAL['wood'], PAL['clay'], .3), spots=False); mushroom(m, -13, 7, 10, 9, mix(PAL['wood'], PAL['clay'], .3), spots=False)


@recipe('glow_mushroom', group='Champignons', label='Champignons lumineux', variants=2)
def glow_mushroom(m, seed=0):
    m.box(-9, 0, -9, 18, .8, 18, PAL['stone_dark'])
    for k in range(int(U(m, 3, 5))): mushroom(m, U(m, -6, 6), U(m, -6, 6), U(m, 5, 14), U(m, 6, 10), PAL['gem'], stem=PAL['ice'], spots=False, emis=1.1)
    m.light(0, 14, 2, PAL['gem'], power=1.1, radius=3.2)


@recipe('fairy_ring', group='Champignons', label='Rond de sorcières', variants=2)
def fairy_ring(m, seed=0):
    m.box(-11, 0, -11, 22, .8, 22, mix(PAL['grass'], PAL['dirt'], .2))
    for k in range(8): a = k * 2 * math.pi / 8 + U(m, -.2, .2); mushroom(m, math.cos(a) * 8, math.sin(a) * 8, U(m, 3, 6), U(m, 4, 5.5), PAL['ruby'], spots=False)


# ------------------------------------------------------------------ cultures
def bed(m, w=22, d=22): m.box(-w / 2, 0, -d / 2, w, 1.6, d, PAL['dirt'])


@recipe('wheat_field', group='Cultures', label='Champ de blé', variants=3)
def wheat_field(m, seed=0):
    bed(m); col = PAL['straw'] if seed != 1 else PAL['leaf_light']
    for r in range(4): m.box(-10, 1.6, -9 + r * 5, 20, U(m, 10, 14), 3, pick(m, col, shade(col, .9))); m.box(-10, 1.6 + 9, -9 + r * 5 - .4, 20, 5, 3.8, shade(col, 1.12))


@recipe('corn_stalks', group='Cultures', label='Maïs', variants=2)
def corn_stalks(m, seed=0):
    bed(m)
    for ix in (-6, 0, 6):
        for iz in (-5, 4):
            x, z = ix + U(m, -1, 1), iz + U(m, -1, 1); h = U(m, 24, 32); m.box(x - 1, 1.6, z - 1, 2, h, 2, PAL['leaf'])
            m.box(x + 1, 14, z - 1, 2.4, 6, 2.4, PAL['cloth_yellow']); m.box(x - 5, 10, z - .6, 6, 1, 1.4, PAL['leaf_dark']); tilt(m, rz=.3); m.box(x - 1.4, 1.6 + h, z - 1.4, 2.8, 3, 2.8, PAL['straw'])


def pumpkin(m, x, z, s, col, face=False):
    m.box(x - s * .5, 0, z - s * .45, s, s * .72, s * .9, col); m.box(x - s * .3, 0, z - s * .5, s * .6, s * .72, s, shade(col, 1.08)); m.box(x - s * .5, s * .5, z - s * .35, s, s * .22, s * .7, shade(col, .92))
    m.box(x - .8, s * .72, z - .8, 1.6, 2.6, 1.6, PAL['leaf_dark'])
    if face:
        for dx in (-.22, .22): m.box(x + dx * s - .9, s * .38, z + s * .45 - .1, 1.8, 1.8, .9, PAL['gold'], emis=1.4)
        m.box(x - s * .2, s * .12, z + s * .45 - .1, s * .4, 1.4, .9, PAL['gold'], emis=1.4); m.light(x, s * .4, z + 2, PAL['autumn'], power=1.1, radius=2.6)


@recipe('pumpkin', group='Cultures', label='Citrouille', variants=3)
def pumpkin_r(m, seed=0): pumpkin(m, 0, 0, [14, 11, 17][seed % 3], [PAL['orange'] if 'orange' in PAL else EX['orange'], PAL['cream'] if 'cream' in PAL else EX['cream'], PAL['autumn']][seed % 3])


@recipe('jack_o_lantern', group='Cultures', label='Citrouille sculptée (lanterne)', variants=1)
def jack(m, seed=0): pumpkin(m, 0, 0, 14, EX['orange'], face=True)


@recipe('pumpkin_patch', group='Cultures', label='Champ de citrouilles', variants=2)
def pumpkin_patch(m, seed=0):
    bed(m, 26, 22)
    for x, z, s in [(-6, -3, 12), (5, -4, 9), (1, 4, 14)]: pumpkin(m, x, z, s, pick(m, EX['orange'], PAL['autumn'])); m.box(x, 1.6, z + 5, U(m, 6, 10), .8, 1, PAL['leaf'])


@recipe('melon', group='Cultures', label='Pastèque et melon', variants=2)
def melon(m, seed=0):
    base, stripe = (PAL['leaf'], PAL['leaf_dark']) if seed == 0 else (PAL['cloth_yellow'], PAL['gold'])
    m.box(-5, 0, -4.6, 10, 9, 9.2, base)
    for i in range(3): m.box(-5.2 + i * 3.6, 0, -4.8, 1.4, 9, 9.6, stripe)
    m.box(-.7, 9, -.7, 1.4, 2.4, 1.4, PAL['leaf_dark']); m.box(7, 0, 2, 7, 6, 7, base); m.box(7, 5.5, 2, 7, 1, 7, stripe)


@recipe('carrot_patch', group='Cultures', label='Carottes', variants=2)
def carrot_patch(m, seed=0):
    bed(m, 20, 20)
    for k in range(5):
        x, z = U(m, -7, 7), U(m, -7, 7); m.box(x - 1, 1.6, z - 1, 2, 1.6, 2, EX['orange']); m.box(x - 1.6, 3, z - .8, 3.2, U(m, 4, 6), 1.6, PAL['leaf_light']); m.box(x - .8, 3, z - 1.6, 1.6, U(m, 4, 6), 3.2, PAL['leaf'])
    m.box(-6, 1.6, 9.4, 6, 1.6, 1.8, EX['orange'])


@recipe('cabbage_patch', group='Cultures', label='Choux', variants=2)
def cabbage_patch(m, seed=0):
    bed(m, 22, 18)
    for k, (x, z) in enumerate([(-6, -4), (3, -5), (6, 3), (-3, 4)]):
        c = pick(m, PAL['leaf'], PAL['leaf_light']); mass(m, x, 1.6, z, 4.4, 3, 4.4, (shade(c, .8), c, shade(c, 1.12)))


@recipe('hay_bale', group='Cultures', label='Botte de foin', variants=2)
def hay_bale(m, seed=0):
    m.box(-8, 0, -5, 16, 10, 10, PAL['straw'])
    for x in (-4.5, 3.5): m.box(x, -.1, -5.3, 1.2, 10.2, 10.6, PAL['wood_dark'])
    for k in range(3): m.box(U(m, -9, 8), U(m, 1, 9), 5, U(m, 2, 3.4), .7, .7, PAL['cloth_yellow'])
    if seed: m.box(-8, 10, -5, 16, 5, 10, PAL['straw'])


@recipe('strawberry_patch', group='Cultures', label='Fraisiers', variants=1)
def strawberry_patch(m, seed=0):
    bed(m, 20, 16)
    for ix in (-6, 0, 6): mass(m, ix, 1.6, 0, 3.6, 1.8, 5, LEAF)
    for k in range(4): m.box(U(m, -8, 8), 1.6, 5.6, 1.6, 1.8, 1.6, PAL['ruby'])


@recipe('sprout_rows', group='Cultures', label='Jeunes pousses', variants=2)
def sprout_rows(m, seed=0):
    m.box(-12, 0, -10, 24, 1.6, 20, PAL['dirt'])
    for r in range(3):
        m.box(-12, 1.6, -8 + r * 6, 24, 1.2, 3, shade(PAL['dirt'], .78))
        for i in range(-9, 10, 6): m.box(i - .5, 2.8, -8 + r * 6 + 1, 1, U(m, 2, 4), 1, PAL['leaf_light']); m.box(i - 1.4, 3.6, -8 + r * 6 + 1, 2.8, .8, 1, PAL['leaf'])
