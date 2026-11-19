"""Craft : nature et blocs, DANS LE STYLE DU STUDIO (docs/STYLE_GUIDE_STUDIO.md) : peu de boîtes franches, 2 à 6 couleurs de la palette, aucun bruit de couleur (le grain vient du peintre).

Un arbre = un tronc + quelques masses de feuillage ; un bloc = un cube + quelques plaques ; un champignon = un pied + un chapeau. Le détail vient de pièces fines, pas du nombre de cubes.
Toutes les couleurs sont ramenées à la palette `PAL` (+ quelques teintes sourdes `EX` pour les fleurs) : `recipe` ci-dessous le fait pour chaque boîte et coupe le `jitter`.
"""
import math
from .craft import recipe as _recipe, Model, PAL

EX = dict(violet=(130, 100, 150), lilac=(165, 140, 180), teal=(70, 130, 140), amber=(200, 140, 50), rose=(190, 110, 130), sky=(110, 140, 190), orange=(200, 110, 40), cream=(230, 220, 190))
_ALL = {**PAL, **EX}


def snap(c):
    """la couleur de la palette la plus proche"""
    return min(_ALL.values(), key=lambda p: (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2)


def recipe(name, **kw):
    """comme craft.recipe, mais chaque boîte est ramenée à la palette et sans jitter (règles 4 et 6 du guide de style)"""
    def deco(fn):
        def wrapped(m, seed=0):
            ob = m.box
            m.box = lambda x, y, z, w, h, d, color, jitter=0., emis=0., ry=0.: ob(x, y, z, w, h, d, snap(color), jitter=0., emis=emis, ry=ry)
            return fn(m, seed)
        return _recipe(name, **kw)(wrapped)
    return deco


def clamp(v): return max(0, min(255, int(v)))
def shade(c, k): return tuple(clamp(v * k) for v in c)
def mix(a, b, t): return tuple(clamp(a[i] * (1 - t) + b[i] * t) for i in range(3))
def U(m, a, b): return m.rng.uniform(a, b)
def pick(m, *xs): return xs[int(m.rng.random() * len(xs)) % len(xs)]


def tilt(m, rz=0., rx=0.):
    """incline la dernière boîte écrite (rotation autour de z puis x, en radians) : branches, palmes, lignes de toile"""
    b = m.boxes[-1]
    if rz: b['rz'] = rz
    if rx: b['rx'] = rx


def mass(m, cx, y, cz, rx, ry, rz, cols):
    """une masse arrondie (feuillage, buisson, rocher, nuage) : trois boîtes qui se croisent, teintes sombre / base / claire ; (rx, ry, rz) = demi-largeurs, y = bas"""
    lo, base, hi = cols
    m.box(cx - rx, y + ry * .3, cz - rz * .72, 2 * rx, ry * 1.4, 1.44 * rz, lo)
    m.box(cx - rx * .72, y, cz - rz, 1.44 * rx, ry * 1.4, 2 * rz, base)
    m.box(cx - rx * .72, y + ry * .3, cz - rz * .72, 1.44 * rx, ry * 1.7, 1.44 * rz, hi)


def trunk(m, x, z, h, w, color=None, lean=0., split=.62):
    """un tronc en deux pièces qui s'affinent, incliné ; rend le point du haut (x, y, z)"""
    color = color or PAL['bark']; h1 = h * split
    m.box(x - w / 2, 0, z - w / 2, w, h1, w, color)
    m.box(x - w * .4 + lean, h1, z - w * .4, w * .8, h - h1, w * .8, color)
    return x + lean, h, z


def roots(m, w, color=None):
    color = color or PAL['bark']
    for sx, sz in ((1, 1), (-1, 1), (1, -1), (-1, -1)): m.box(sx * w * .55 - 1.5, 0, sz * w * .4 - 1.5, 3, 2, 3, color)


LEAF = (PAL['leaf'], mix(PAL['leaf'], PAL['leaf_light'], .5), PAL['leaf_light'])


# ------------------------------------------------------------------ arbres
@recipe('oak_tree', group='Arbres', label='Chêne', variants=3)
def oak_tree(m, seed=0):
    tx, ty, tz = trunk(m, 0, 0, U(m, 20, 26), U(m, 4.4, 5.4), lean=U(m, -1.5, 1.5)); roots(m, 5)
    mass(m, tx, ty - 2, tz, U(m, 9, 11), U(m, 5, 6), U(m, 9, 11), LEAF)
    for k in range(2): mass(m, tx + U(m, -8, 8), ty - 6 + k * 3, tz + U(m, -7, 7), U(m, 5, 6.5), 3.6, U(m, 5, 6.5), LEAF)


@recipe('birch_tree', group='Arbres', label='Bouleau', variants=3)
def birch_tree(m, seed=0):
    tx, ty, tz = trunk(m, 0, 0, U(m, 30, 38), 3.2, PAL['birch'], lean=U(m, -1.5, 1.5), split=.7)
    for k in range(4): m.box(-1.8, U(m, 3, ty - 4), U(m, -1.4, .4), .5, 1.2, 1.6, PAL['black'])
    pal = (mix(PAL['leaf'], PAL['straw'], .4), mix(PAL['leaf_light'], PAL['straw'], .3), PAL['leaf_light'])
    mass(m, tx, ty - 6, tz, 6, 5, 6, pal); mass(m, tx + U(m, -3, 3), ty + 1, tz, 4.4, 4, 4.4, pal)


@recipe('spruce_tree', group='Arbres', label='Épicéa', variants=3)
def spruce_tree(m, seed=0):
    m.box(-1.6, 0, -1.6, 3.2, 12, 3.2, PAL['bark']); tiers = int(U(m, 5, 7)); y = 4.
    for i in range(tiers):
        w = (1 - i / tiers) * 20 + 4 + U(m, -1, 1); h = U(m, 5, 6.5)
        m.box(-w / 2, y, -w / 2, w, h, w, pick(m, PAL['pine'], PAL['leaf_dark']))
        if w > 9: m.box(-w / 2 + 2, y + h, -w / 2 + 2, w - 4, 1.2, w - 4, PAL['leaf'])
        y += h * .72
    m.box(-1.2, y, -1.2, 2.4, 5, 2.4, PAL['pine'])


@recipe('pine_tree', group='Arbres', label='Pin', variants=2)
def pine_tree(m, seed=0):
    tx, ty, tz = trunk(m, 0, 0, U(m, 38, 46), 3.6, mix(PAL['bark'], PAL['clay'], .35), lean=U(m, -2.5, 2.5), split=.75)
    for i in range(3):
        w, d = U(m, 12, 17), U(m, 10, 14); y = ty - 12 + i * 5; m.box(tx - w / 2 + U(m, -3, 3), y, tz - d / 2, w, 3.4, d, pick(m, PAL['pine'], PAL['leaf_dark']))
    m.box(tx - 6, ty, tz - 5, 12, 3, 10, PAL['pine'])


@recipe('jungle_tree', group='Arbres', label='Acajou de jungle', variants=2)
def jungle_tree(m, seed=0):
    tx, ty, tz = trunk(m, 0, 0, U(m, 44, 54), 5, mix(PAL['bark'], PAL['wood'], .4), lean=U(m, -2, 2), split=.8)
    for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1)): m.box(sx * 4.2 - 1.2, 0, sz * 4.2 - 1.2, 2.4, 11, 2.4, PAL['bark'])
    cols = (shade(PAL['leaf_dark'], .8), PAL['leaf'], PAL['leaf_light'])
    mass(m, tx, ty - 3, tz, 14, 6, 14, cols); mass(m, tx + 9, ty - 7, tz + 4, 7, 4, 7, cols); mass(m, tx - 9, ty - 6, tz - 4, 7, 4, 7, cols)
    for k in range(4): m.box(tx + U(m, -11, 11), ty - U(m, 14, 24), tz + U(m, -8, 10), 1, U(m, 12, 22), 1, PAL['leaf_dark'])


@recipe('acacia_tree', group='Arbres', label='Acacia', variants=2)
def acacia_tree(m, seed=0):
    tx, ty, tz = trunk(m, 0, 0, U(m, 12, 16), 3.4, mix(PAL['bark'], PAL['stone'], .25), lean=U(m, -1, 1))
    m.box(tx - 8, ty - 1, tz - 1.2, 16, 2, 2.4, PAL['bark']); tilt(m, rz=U(m, -.25, .25))
    cols = (mix(PAL['leaf'], PAL['straw'], .15), mix(PAL['leaf_light'], PAL['straw'], .3), mix(PAL['leaf_light'], PAL['straw'], .5))
    mass(m, tx, ty + 1, tz, 14, 2.6, 9, cols); mass(m, tx - 9, ty - 1, tz + 2, 8, 2, 6, cols); mass(m, tx + 9, ty - 1, tz - 2, 8, 2, 6, cols)


@recipe('dark_oak_tree', group='Arbres', label='Chêne sombre', variants=2)
def dark_oak_tree(m, seed=0):
    tx, ty, tz = trunk(m, 0, 0, U(m, 14, 18), 7, shade(PAL['bark'], .8), lean=U(m, -1, 1)); roots(m, 7, shade(PAL['bark'], .8))
    cols = (shade(PAL['leaf_dark'], .75), shade(PAL['leaf'], .65), PAL['leaf_dark'])
    mass(m, tx, ty - 2, tz, 15, 7, 15, cols); mass(m, tx + 10, ty - 5, tz + 3, 7, 4, 7, cols); mass(m, tx - 10, ty - 5, tz - 3, 7, 4, 7, cols)


@recipe('willow_tree', group='Arbres', label='Saule', variants=2)
def willow_tree(m, seed=0):
    tx, ty, tz = trunk(m, 0, 0, U(m, 16, 20), 5, mix(PAL['bark'], PAL['wood_dark'], .3), lean=U(m, -2, 2)); roots(m, 5)
    cols = (mix(PAL['leaf_dark'], PAL['leaf'], .5), PAL['leaf'], mix(PAL['leaf'], PAL['leaf_light'], .5))
    mass(m, tx, ty - 2, tz, 11, 5, 11, cols)
    for k in range(10):
        a = k * 2 * math.pi / 10; r = U(m, 8, 11.5); ln = U(m, 8, 20)
        m.box(tx + math.cos(a) * r - .6, ty - 1 - ln, tz + math.sin(a) * r - .6, 1.2, ln, 1.2, pick(m, PAL['leaf'], PAL['leaf_light']))


@recipe('cherry_tree', group='Arbres', label='Cerisier en fleurs', variants=2)
def cherry_tree(m, seed=0):
    tx, ty, tz = trunk(m, 0, 0, U(m, 14, 18), 4, shade(PAL['bark'], .9), lean=U(m, -2, 2))
    cols = (mix(PAL['pink'], PAL['clay'], .3), PAL['pink'], mix(PAL['pink'], PAL['white'], .5))
    mass(m, tx, ty - 3, tz, 11, 6, 11, cols); mass(m, tx + 7, ty - 6, tz + 3, 6, 4, 6, cols); mass(m, tx - 7, ty - 6, tz - 3, 6, 4, 6, cols)
    for k in range(3): m.box(U(m, -12, 12), 0, U(m, -10, 10), 3, .6, 2.4, PAL['pink'])


@recipe('dead_tree', group='Arbres', label='Arbre mort', variants=3)
def dead_tree(m, seed=0):
    col = mix(PAL['bark'], PAL['stone'], .4); tx, ty, tz = trunk(m, 0, 0, U(m, 22, 30), 4, col, lean=U(m, -2, 2), split=.7)
    for k in range(4):
        sg = 1 if k % 2 else -1; y = ty * (.38 + k * .15)
        m.box(sg * 5 - 4.5, y, -1, 9, 1.8, 2, col); tilt(m, rz=sg * U(m, .45, .7)); m.box(sg * 11 - 3.5, y + 5.5, -.8, 7, 1.5, 1.6, mix(col, PAL['stone'], .3)); tilt(m, rz=sg * U(m, .8, 1.1))


@recipe('palm_tree', group='Arbres', label='Palmier', variants=3)
def palm_tree(m, seed=0):
    h = U(m, 28, 38); lean = U(m, -5, 5); col = mix(PAL['wood'], PAL['sand'], .25)
    for i in range(3): t = i / 3.; m.box(lean * t * t - 1.7, h / 3 * i, -1.7, 3.4, h / 3, 3.4, col)
    top = h; tx = lean * .9
    for k in range(7):
        a = k * 2 * math.pi / 7 + U(m, -.2, .2); L = U(m, 11, 15)
        m.box(tx + math.cos(a) * L / 2 - L / 2, top, math.sin(a) * L / 2 - 1.2, L, 1.6, 2.4, PAL['leaf'], ry=-a)
        m.box(tx + math.cos(a) * (L + 1.5) - L * .22 - L * .5 + L * .5 - 1.8, top - 3.4, math.sin(a) * (L + 1.5) - 1.2, 3.6, 3.4, 2.4, PAL['leaf_dark'], ry=-a)
    for k in range(3): m.box(tx + U(m, -2, 2) - 1.2, top - 3, U(m, -2, 2) - 1.2, 2.4, 2.4, 2.4, PAL['wood_dark'])


@recipe('baobab_tree', group='Arbres', label='Baobab', variants=1)
def baobab_tree(m, seed=0):
    col = mix(PAL['bark'], PAL['sand'], .35); m.box(-7, 0, -7, 14, 18, 14, col); m.box(-5, 18, -5, 10, 12, 10, col)
    for k in range(4): a = k * 1.57 + .4; m.box(math.cos(a) * 5 - 1.5, 28, math.sin(a) * 5 - 1.5, 3, 6, 3, col)
    cols = (PAL['leaf_dark'], PAL['leaf'], PAL['leaf_light'])
    for k in range(4): a = k * 1.57 + .4; mass(m, math.cos(a) * 8, 33, math.sin(a) * 8, 6, 3, 6, cols)
    mass(m, 0, 35, 0, 7, 3, 7, cols)


@recipe('sequoia_tree', group='Arbres', label='Séquoia', variants=2)
def sequoia_tree(m, seed=0):
    col = mix(PAL['bark'], PAL['clay'], .3); tx, ty, tz = trunk(m, 0, 0, U(m, 70, 88), 9, col, split=.8); roots(m, 9, col)
    y = ty - 26
    for i in range(5):
        w = 6 + i * 3.4; m.box(-w / 2, y, -w / 2, w, 4, w, pick(m, PAL['pine'], PAL['leaf_dark'])); y += 5.6
    m.box(-2, ty - 4, -2, 4, 10, 4, PAL['pine'])


@recipe('autumn_tree', group='Arbres', label='Arbre d\'automne', variants=3)
def autumn_tree(m, seed=0):
    tx, ty, tz = trunk(m, 0, 0, U(m, 18, 24), 4.4, lean=U(m, -1.5, 1.5)); roots(m, 4.4)
    pals = [(PAL['copper'], PAL['autumn'], PAL['gold']), (PAL['ruby'], (200, 70, 40), PAL['autumn']), (PAL['autumn'], PAL['gold'], PAL['cloth_yellow'])][seed % 3]
    mass(m, tx, ty - 2, tz, 9, 5, 9, pals); mass(m, tx + 7, ty - 6, tz + 3, 6, 4, 6, pals); mass(m, tx - 7, ty - 6, tz - 2, 6, 4, 6, pals)
    for k in range(4): m.box(U(m, -12, 12), 0, U(m, -9, 9), 3, .6, 2.4, pick(m, *pals))


# suites (fichiers créés avec celui-ci)
for _mod in ("craft_nature_plants", "craft_nature_blocks", "craft_nature_rocks"):
    try:
        __import__(__package__ + "." + _mod)
    except ModuleNotFoundError as _e:
        if _mod not in str(_e): raise
