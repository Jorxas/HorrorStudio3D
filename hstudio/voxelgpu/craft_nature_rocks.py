"""Craft : roches, cristaux, grottes, terriers, nids, ruches, toiles (suite de craft_nature.py, style du studio : peu de boîtes franches, teintes de la palette)."""
import math
from .craft import PAL
from .craft_nature import recipe, mass, tilt, U, pick, shade, mix, EX, LEAF

ROCK = (PAL['stone_dark'], PAL['stone'], PAL['stone_light'])


@recipe('boulder', group='Roches', label='Rocher', variants=4)
def boulder(m, seed=0):
    rx, ry, rz = [(9, 6, 8), (6, 10, 6), (12, 4, 9), (8, 7, 8)][seed % 4]
    mass(m, 0, 0, 0, rx, ry, rz, ROCK); mass(m, rx * .9, 0, rz * .5, 3.5, 2.4, 3.5, ROCK); mass(m, -rx * .8, 0, -rz * .4, 2.6, 2, 2.6, ROCK)


@recipe('mossy_boulder', group='Roches', label='Rocher moussu', variants=3)
def mossy_boulder(m, seed=0):
    mass(m, 0, 0, 0, 10, 7, 9, ROCK); m.box(-7, 12.6, -6, 14, 1.8, 12, PAL['leaf']); m.box(-4, 13.6, -3, 8, 1.4, 6, PAL['leaf_light'])
    mass(m, 9, 0, 6, 4.4, 3, 4, ROCK)
    for k in range(3): m.box(U(m, -6, 6), 15, U(m, -4, 4), 1.6, 1.6, 1.6, pick(m, PAL['white'], PAL['cloth_yellow']))


@recipe('cliff_face', group='Roches', label='Falaise', variants=3)
def cliff_face(m, seed=0):
    cols = [PAL['stone'], mix(PAL['stone'], PAL['sand'], .3), PAL['stone_dark'], mix(PAL['stone'], PAL['clay'], .25)]
    for i in range(8):
        d = U(m, 7, 11); w = 34 - i * 1.4 + U(m, -2, 2); m.box(-w / 2, i * 5, -d + 2, w, 5, d, cols[(i + seed) % 4])
        if i % 3 == 1: m.box(-w / 2 + 3, i * 5 + 5, -d + 2, w * .4, 1.4, d, PAL['leaf'])
    for k in range(3): m.box(U(m, -12, 10), U(m, 8, 30), 3, 1.2, U(m, 5, 10), 1.2, PAL['coal'])


@recipe('rock_arch', group='Roches', label='Arche rocheuse', variants=2)
def rock_arch(m, seed=0):
    for s in (-1, 1):
        m.box(s * 11 - 4.5, 0, -5, 9, 12, 10, pick(m, PAL['stone'], PAL['stone_dark'])); m.box(s * 11 - 3.6 + U(m, -.8, .8), 12, -4.5, 7.2, 12, 9, PAL['stone_light'])
    m.box(-13, 24, -5, 26, 4, 10, PAL['stone']); m.box(-9, 28, -4.4, 18, 3, 8.8, PAL['stone_light']); m.box(-8, 20.5, -4.6, 16, 3.5, 9.2, PAL['stone_dark'])
    m.box(-18, 0, -10, 36, .8, 20, PAL['sand'])
    for k in range(3): mass(m, U(m, -16, 16), 0, U(m, 6, 10), 2.8, 2, 2.4, ROCK)


def cone(m, x, y, z, w, h, color, up=True):
    n = 3
    for i in range(n):
        ww = max(1.4, w * (1 - i / n * .85)); hh = h / n; yy = y + i * hh if up else y - (i + 1) * hh
        m.box(x - ww / 2, yy, z - ww / 2, ww, hh, ww, mix(color, shade(color, .75), i / n))


def slabs(m, ceiling=True):
    m.box(-15, 0, -15, 30, 2, 30, shade(PAL['stone_dark'], .85))
    if ceiling: m.box(-15, 38, -15, 30, 5, 30, shade(PAL['stone_dark'], .9))


@recipe('stalagmites', group='Roches', label='Stalagmites', variants=3)
def stalagmites(m, seed=0):
    slabs(m, ceiling=False)
    for k in range(5): cone(m, U(m, -11, 11), 2, U(m, -11, 11), U(m, 3.5, 8), U(m, 8, 22), mix(PAL['stone'], PAL['sand'], U(m, 0, .5)))


@recipe('stalactites', group='Roches', label='Stalactites', variants=3)
def stalactites(m, seed=0):
    slabs(m)
    for k in range(6): cone(m, U(m, -12, 12), 38, U(m, -12, 12), U(m, 3.5, 7), U(m, 8, 20), mix(PAL['stone'], PAL['sand'], U(m, 0, .5)), up=False)


@recipe('cave_columns', group='Roches', label='Colonnes de grotte', variants=2)
def cave_columns(m, seed=0):
    slabs(m)
    for k in range(2):
        x, z = U(m, -8, 8), U(m, -8, 8); cone(m, x, 2, z, 9, 17, PAL['stone_light']); cone(m, x, 38, z, 9, 17, PAL['stone_light'], up=False); m.box(x - 2, 17, z - 2, 4, 6, 4, mix(PAL['stone'], PAL['sand'], .3))


def crystal_recipe(name, label, col, emis=.6):
    def fn(m, seed=0):
        m.box(-9, 0, -9, 18, 2, 18, PAL['stone_dark']); mass(m, 0, 2, 0, 8, 3, 8, ROCK)
        for k in range(6):
            x, z = U(m, -5, 5), U(m, -5, 5); h = U(m, 9, 22); w = U(m, 2.6, 4.2)
            m.box(x - w / 2, 4, z - w / 2, w, h * .65, w, col, emis=emis); m.box(x - w * .32, 4 + h * .65, z - w * .32, w * .64, h * .35, w * .64, shade(col, 1.25), emis=emis * 1.2); tilt(m, rz=U(m, -.12, .12))
        m.light(0, 14, 2, col, power=1.0, radius=3.4)
    recipe(name, group='Roches', label=label, variants=2)(fn)


crystal_recipe('crystal_amethyst', 'Cristaux d\'améthyste', EX['violet'])
crystal_recipe('crystal_aqua', 'Cristaux bleus', PAL['gem'])
crystal_recipe('crystal_citrine', 'Cristaux jaunes', PAL['gold'])
crystal_recipe('crystal_rose', 'Cristaux roses', PAL['pink'])
crystal_recipe('crystal_ruby', 'Cristaux rouges', PAL['ruby'])
crystal_recipe('crystal_emerald', 'Cristaux verts', PAL['leaf_light'])


@recipe('mine_tunnel_mouth', group='Roches', label='Bouche de galerie de mine', variants=2)
def mine_tunnel_mouth(m, seed=0):
    mass(m, 0, 0, -4, 20, 10, 9, ROCK); m.box(-8, 0, 3, 16, 20, 3, PAL['black'])
    for s in (-1, 1): m.box(s * 8 - 1.5, 0, 4.4, 3, 20, 3, PAL['wood'])
    m.box(-10, 19, 4.4, 20, 3, 3, PAL['wood_dark'])
    for x in range(-6, 8, 4): m.box(x - .6, .2, 6, 1.2, .8, 14, PAL['wood_dark'])
    for s in (-3, 3): m.box(s - .4, .8, 6, .8, .8, 16, PAL['iron_dark'])
    m.box(5, 13, 4.6, 2, 3, 2, PAL['cloth_yellow'], emis=1.5); m.light(5.5, 14, 6, PAL['cloth_yellow'], power=1.0, radius=3.4)
    if seed: m.box(-3, 1.6, 12, 7, 4, 5, PAL['iron_dark']); m.box(-3.6, 5, 11.4, 8.2, 1, 6.2, PAL['wood_dark'])


@recipe('burrow', group='Roches', label='Terrier', variants=2)
def burrow(m, seed=0):
    d = (PAL['dirt'], shade(PAL['dirt'], 1.12), shade(PAL['dirt'], 1.25)); mass(m, 0, 0, 0, 12, 5, 10, d); m.box(-9, 8.4, -6, 18, 1.4, 12, PAL['grass'])
    m.box(-3, 0, 6, 6, 5, 3, PAL['black']); m.box(-4, 4.6, 6, 8, 1.4, 3, shade(PAL['dirt'], .7)); m.box(-4.6, 0, 5.4, 1.4, 4.6, 3, shade(PAL['dirt'], .8))
    for k in range(3): m.box(U(m, -5, 5), 0, U(m, 9, 12), 2, 1, 2, d[1])


@recipe('bird_nest', group='Roches', label='Nid', variants=2)
def bird_nest(m, seed=0):
    for k in range(10): a = k * 2 * math.pi / 10 + U(m, -.2, .2); r = U(m, 5, 7); m.box(math.cos(a) * r - 3, U(m, 0, 3), math.sin(a) * r - .5, 6, 1, 1, pick(m, PAL['wood'], PAL['straw']), ry=-a)
    m.box(-5, 0, -5, 10, 1.4, 10, PAL['straw'])
    for k in range(3): m.box(-4 + k * 3, 1.4, U(m, -1.5, 1.5) - 1.2, 2.6, 3.2, 2.6, PAL['ice'] if seed else PAL['white'])


@recipe('beehive', group='Roches', label='Ruche', variants=2)
def beehive(m, seed=0):
    m.box(-9, 0, -9, 18, 1.5, 18, PAL['wood'])
    for i, w in enumerate([14, 12.4, 10.4, 8.2, 6, 3.6]): m.box(-w / 2, 1.5 + i * 3, -w / 2, w, 3.2, w, PAL['straw'] if i % 2 else mix(PAL['straw'], PAL['gold'], .4))
    m.box(-1.6, 3, 6.7, 3.2, 2.4, 1, PAL['black'])
    for k in range(4): m.box(U(m, -9, 8), U(m, 3, 14), U(m, 2, 10), 1.6, 1.2, 1.2, PAL['gold'])


@recipe('spider_web', group='Roches', label='Toile d\'araignée', variants=2)
def spider_web(m, seed=0):
    m.box(-13, 0, -2, 2.4, 26, 2.4, PAL['wood_dark']); m.box(-13, 24, -2, 26, 2.4, 2.4, PAL['wood_dark'])
    ox, oy = -10.6, 23.8
    for k in range(5):
        a = -math.pi / 2 + k * (math.pi / 2) / 4; L = U(m, 18, 22)
        m.box(ox + math.cos(a) * L / 2 - L / 2, oy + math.sin(a) * L / 2 - .3, -.3, L, .7, .6, PAL['white']); tilt(m, rz=a)
    for r in (7, 13, 19):
        for k in range(4): a = -math.pi / 2 + (k + .5) * (math.pi / 2) / 4; m.box(ox + math.cos(a) * r - 2.6, oy + math.sin(a) * r - .3, -.2, 5.2, .6, .5, PAL['white']); tilt(m, rz=a + math.pi / 2)
    x, y = ox + 7, oy - 8; m.box(x, y, -1, 2.6, 2.6, 2.4, PAL['black']); m.box(x + .5, y + 2, -1.2, 1.6, 1.2, 1.4, PAL['ruby'])


@recipe('standing_stone', group='Roches', label='Menhir', variants=3)
def standing_stone(m, seed=0):
    for i, (w, h) in enumerate([(9, 12), (7.6, 12), (5.6, 9)]): m.box(-w / 2 + U(m, -.5, .5), sum(x[1] for x in [(9, 12), (7.6, 12), (5.6, 9)][:i]), -2.6, w, h, 5.2, pick(m, PAL['stone'], PAL['stone_light'], PAL['stone_dark']))
    m.box(-4.4, 0, -2.8, 8.8, 3, 5.6, PAL['leaf'])
    for k in range(3): m.box(-.8 + (k % 2) * 1.6, 12 + k * 5, 2.7, 1.2, 2.6, .6, PAL['gem'], emis=1.1)
    m.light(0, 18, 4, PAL['gem'], power=.8, radius=3)
    for k in range(3): mass(m, U(m, -8, 8), 0, U(m, -5, 5), 2.6, 1.6, 2.6, ROCK)
