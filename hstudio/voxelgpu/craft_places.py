"""Éléments « craft » : petits lieux et constructions (maisons, ruines, fortifications, ponts, parcours d'obstacles), dessinés ici dans le style du studio (voir craft.py).

Chaque recette écrit ses propres boîtes (aucune texture ni aucun modèle d'un jeu existant) ; l'inspiration est le genre : des constructions en blocs lisibles de loin, au grain fin
(`jitter`, assises de pierre, colombages, tuiles étagées), pas des cubes unis ni des briques de jouet. Unité : le voxel = 1/16 m ; face avant vers +z ; les fenêtres éclairées sont
émissives et posent une lumière.
"""
import math
from .craft import recipe, Model, PAL

PLASTER = (184, 168, 136); PLASTER_D = (160, 142, 112); SLATE = (88, 92, 104); THATCH = (196, 164, 84); TILE = (156, 72, 54); WIN = (255, 206, 120); WIN_G = (150, 255, 170)
MOSS = (64, 104, 54); STEEL = (206, 210, 220); FLAME = (255, 168, 60); FLAME2 = (255, 224, 130); NIGHT = (30, 36, 52)


def _canopy(m, cx, cy, cz, rx, ry, rz, color, jitter=0., step=0):
    """feuillage ou mousse : trois gros volumes empilés au lieu d'un nuage de petits cubes"""
    m.box(cx - rx, cy - ry, cz - rz, 2 * rx, ry * 1.2, 2 * rz, color); m.box(cx - rx * .75, cy, cz - rz * .75, 1.5 * rx, ry * 1.0, 1.5 * rz, tuple(int(v * 1.08) for v in color))
    m.box(cx - rx * .4, cy + ry * .8, cz - rz * .4, .8 * rx, ry * .6, .8 * rz, tuple(int(v * 1.14) for v in color))


def _stone(m, x, y, z, w, h, d, color=None, courses=4):
    """de la pierre en assises : une rangée un peu plus claire, la suivante un peu plus sombre"""
    color = color or PAL['stone']; i = 0
    while i < h:
        hh = min(courses, h - i); k = .92 if (i // courses) % 2 else 1.05
        m.box(x, y + i, z, w, hh, d, tuple(max(0, min(255, int(v * k))) for v in color)); i += courses


def _gable(m, w, d, y0, color, over=3, layer=3, step=3, len_over=2, wall=None, jitter=0.):
    """toit à deux pans, faîte le long de x : une rangée de tuiles par étage, de plus en plus étroite ; pignons remplis avec la couleur du mur"""
    n = int((d / 2. + over) / step)
    for i in range(n):
        zw = d + 2 * over - 2 * i * step
        if zw <= 0: break
        m.box(-w / 2. - len_over, y0 + i * layer, -(d / 2. + over) + i * step, w + 2 * len_over, layer, zw, color, jitter=jitter)
        if wall and d - 2 * i * step > 0:
            for sx in (-1, 1): m.box(sx * (w / 2. - 1) - 1, y0 + i * layer, -d / 2. + i * step, 2, layer, d - 2 * i * step, wall)
    m.box(-w / 2. - len_over, y0 + n * layer - 1, -1.5, w + 2 * len_over, 2, 3, tuple(int(v * .82) for v in color))                                  # faîtière


def _win(m, x, y, z, w=6, h=7, lit=True, frame=None):
    frame = frame or PAL['wood_dark']
    m.box(x - w / 2. - 1, y - 1, z, w + 2, h + 2, 1, frame); m.box(x - w / 2., y, z + 1, w, h, 1, WIN if lit else (70, 90, 110), emis=1.3 if lit else 0.)
    m.box(x - .5, y, z + 2, 1, h, 1, frame); m.box(x - w / 2., y + h / 2. - .5, z + 2, w, 1, 1, frame)
    if lit: m.light(x, y + h / 2., z + 6, WIN, .7, 3.)


def _door(m, x, y, z, w=9, h=17, color=None):
    color = color or PAL['wood']
    m.box(x - w / 2. - 1, y, z, w + 2, h + 1, 1, PAL['wood_dark']); m.box(x - w / 2., y, z + 1, w, h, 1, color)
    for i in range(1, 3): m.box(x - w / 2., y + 3 + i * 5, z + 2, w, 1, 1, PAL['wood_dark'])
    m.box(x + w / 2. - 2, y + h / 2., z + 2, 1.5, 1.5, 1, PAL['gold'])


def _chimney(m, x, y, z, h=14, w=5):
    _stone(m, x, y, z, w, h, w, PAL['stone_dark']); m.box(x - 1, y + h, z - 1, w + 2, 2, w + 2, PAL['stone'])


def _house(m, w, d, h, wall, roof, lit=True, timber=True, chimney=True, base=PAL['stone_dark']):
    _stone(m, -w / 2. - 1, 0, -d / 2. - 1, w + 2, 4, d + 2, base)
    m.box(-w / 2., 4, -d / 2., w, h, d, wall)
    if timber:
        for sx in (-1, 1): m.box(sx * (w / 2. - 1) - 1, 4, d / 2. - .5, 2, h, 1.5, PAL['wood_dark']); m.box(sx * (w / 2. - 1) - 1, 4, -d / 2. - 1, 2, h, 1.5, PAL['wood_dark'])
        m.box(-w / 2., 4 + h // 2, d / 2. - .5, w, 2, 1.5, PAL['wood_dark']); m.box(-w / 2., 4 + h - 2, d / 2. - .5, w, 2, 1.5, PAL['wood_dark'])
    _door(m, 0, 4, d / 2.)
    for sx in (-1, 1):
        _win(m, sx * w / 3., 4 + 9, d / 2., lit=lit)
        if h > 24: _win(m, sx * w / 3., 4 + h - 12, d / 2., lit=lit)
    _gable(m, w, d, 4 + h, roof, wall=wall)
    if chimney: _chimney(m, w / 2. - 10, 4 + h, -3, 14 + d // 6)
    m.box(-7, 0, d / 2. + 1, 14, 2, 6, PAL['stone']); m.box(-6, 2, d / 2. + 1, 12, 1, 4, PAL['stone_light'])


def _log_walls(m, w, d, rows, color):
    for r in range(rows):
        y = 4 + r * 4; ex = 2 if r % 2 else 0; ez = 0 if r % 2 else 2
        m.box(-w / 2. - ex, y, d / 2. - 3, w + 2 * ex, 4, 3, color); m.box(-w / 2. - ex, y, -d / 2., w + 2 * ex, 4, 3, color)
        m.box(-w / 2., y, -d / 2. - ez, 3, 4, d + 2 * ez, color); m.box(w / 2. - 3, y, -d / 2. - ez, 3, 4, d + 2 * ez, color)


# =================================================================================================== Maisons et villages
@recipe('cabin', group='Maisons et villages', label='Cabane en rondins', kind='structure')
def cabin(m, seed=0):
    w, d = 56, 44
    _stone(m, -w / 2. - 2, 0, -d / 2. - 2, w + 4, 4, d + 4, PAL['stone_dark']); _log_walls(m, w, d, 7, PAL['wood'])
    m.box(-w / 2. + 3, 4, -d / 2. + 3, w - 6, 28, d - 6, PAL['wood_dark'])
    _door(m, 0, 4, d / 2. + 0.5, 10, 18); _win(m, -18, 14, d / 2. + 0.5, 7, 7); _win(m, 18, 14, d / 2. + 0.5, 7, 7)
    _gable(m, w, d, 32, (126, 90, 58), over=5, wall=PAL['wood'])
    _chimney(m, 14, 32, -8, 16, 7)
    m.box(-w / 2. - 8, 4, 2, 6, 14, 18, PAL['wood_dark']); m.box(-w / 2. - 8, 4, 2, 6, 3, 18, PAL['bark'])
    for i in range(3): m.box(-w / 2. - 7, 4 + i * 4, 3 + (i % 2), 4, 4, 14, PAL['wood_light'])         # tas de bois
    m.box(-12, 0, d / 2. + 3, 24, 3, 8, PAL['plank']); m.emit(26, 24, d / 2. + 1, 3, 4, 3, WIN, 1.3); m.light(26, 26, d / 2. + 5, WIN, 1.0, 4.)


@recipe('village_house', group='Maisons et villages', label='Maison de village', kind='structure', variants=3)
def village_house(m, seed=0):
    k = seed % 3
    if k == 0: _house(m, 64, 48, 32, PLASTER, TILE)
    elif k == 1: _house(m, 56, 44, 26, (150, 112, 74), THATCH, base=PAL['stone'])
    else:
        _house(m, 60, 44, 40, (128, 134, 148), SLATE, lit=True)
        _stone(m, 20, 4, -22, 20, 56, 20, PAL['stone_dark']); _gable(m, 20, 20, 60, SLATE, over=2, wall=PAL['stone_dark'])


@recipe('barn', group='Maisons et villages', label='Grange', kind='structure')
def barn(m, seed=0):
    w, d = 80, 56; red = (140, 50, 44)
    _stone(m, -w / 2. - 1, 0, -d / 2. - 1, w + 2, 4, d + 2, PAL['stone_dark']); m.box(-w / 2., 4, -d / 2., w, 36, d, red)
    for x in range(-w // 2, w // 2, 8): m.box(x, 4, d / 2., 1, 36, 1, (120, 40, 36))
    m.box(-12, 4, d / 2., 24, 30, 1.5, PAL['white']); m.box(-12, 4, d / 2. + 1.5, 24, 2, 1, PAL['white']); m.box(-12, 32, d / 2. + 1.5, 24, 2, 1, PAL['white'])
    _seg(m, -12, d / 2. + 2, 12, d / 2. + 2, 4, 30, 1, PAL['white']) if False else None
    for i in range(14): m.box(-12 + i * 0.0 + i * 1.8, 4 + i * 2.1, d / 2. + 2.6, 2, 2, 1, PAL['white'])
    for i in range(14): m.box(10 - i * 1.8, 4 + i * 2.1, d / 2. + 2.6, 2, 2, 1, PAL['white'])
    _gable(m, w, d, 40, (96, 96, 104), over=4, layer=4, step=3, wall=red); m.box(-6, 56, d / 2. - 1, 12, 8, 2, PAL['wood_dark']); m.box(-5, 57, d / 2., 10, 6, 1, NIGHT)
    for sx in (-1, 1): m.box(sx * 38 - 1, 4, d / 2., 2, 26, 1, PAL['white'])
    m.box(-34, 0, d / 2. + 2, 20, 8, 10, PAL['straw']); m.box(30, 0, d / 2. + 2, 12, 10, 8, PAL['straw'])


@recipe('windmill', group='Maisons et villages', label='Moulin à vent', kind='structure')
def windmill(m, seed=0):
    for i, (w, h) in enumerate([(36, 14), (34, 14), (32, 14), (30, 14), (28, 12)]):
        m.box(-w / 2., i * 14 if i < 4 else 56, -w / 2., w, h, w, PLASTER if i else PAL['stone'])
    m.box(-18, 0, -18, 36, 6, 36, PAL['stone_dark']); _door(m, 0, 4, 18, 8, 15); _win(m, 0, 30, 15.5, 6, 8)
    for i in range(7): m.box(-16 + i * 2, 68 + i * 3, -16 + i * 2, 32 - i * 4, 3, 32 - i * 4, (130, 70, 52))
    m.box(-3, 62, 14, 6, 6, 14, PAL['wood_dark'])                                                       # axe des pales
    for (dx, dy) in ((1, 1), (-1, 1), (1, -1), (-1, -1)):                                                 # quatre pales en croix, en diagonale
        for t in range(1, 15): m.box(3 + dx * t * 2 - 1.5 if dx > 0 else dx * t * 2 - 1.5, 64 + dy * t * 2 - 1, 27, 3, 3, 2, PAL['wood'])
        for t in range(6, 15):
            for u in range(0, 5): m.box((dx * t * 2) + (-dy * u * 1.5) + (1 if dx > 0 else -4), 64 + dy * t * 2 + (dx * u * 1.5) - 1, 26, 3, 3, 1, PAL['cloth'])


@recipe('well', group='Maisons et villages', label='Puits', kind='structure')
def well(m, seed=0):
    n = 14
    for i in range(n):
        a = 2 * math.pi * i / n; m.box(math.cos(a) * 12 - 3, 0, math.sin(a) * 12 - 3, 6, 11, 6, PAL['stone'] if i % 2 else PAL['stone_dark'])
    m.box(-9, 9, -9, 18, 1, 18, (40, 70, 96)); m.box(-8, 10, -8, 16, 1, 16, (60, 110, 160), emis=.25)
    for sx in (-1, 1): m.box(sx * 13 - 1.5, 11, -1.5, 3, 24, 3, PAL['wood'])
    m.box(-15, 33, -2, 30, 3, 4, PAL['wood_dark']); m.box(-3, 28, -2, 6, 5, 4, PAL['wood']); m.box(-.5, 12, -.5, 1, 16, 1, PAL['rope'])
    for i in range(7): m.box(-16 + i * 2.5, 35 + i, -8 + 0, 6, 3, 16, (150, 80, 56)) if False else None
    for i in range(5): m.box(-17 + i * 1.5, 36 + i * 3, -10, 34 - i * 3, 3, 20, (150, 80, 56))
    m.box(-3, 11, -3, 6, 5, 6, PAL['wood_dark'])


@recipe('fountain', group='Maisons et villages', label='Fontaine', kind='structure')
def fountain(m, seed=0):
    n = 16; W = (100, 156, 214)
    for i in range(n):
        a = 2 * math.pi * i / n; m.box(math.cos(a) * 24 - 4, 0, math.sin(a) * 24 - 4, 8, 10, 8, PAL['stone'] if i % 2 else PAL['stone_dark'])
    m.box(-22, 2, -22, 44, 7, 44, W, emis=.15)
    m.box(-5, 2, -5, 10, 18, 10, PAL['stone_light']); m.box(-12, 14, -12, 24, 3, 24, PAL['stone']); m.box(-10, 17, -10, 20, 1, 20, W, emis=.2)
    m.box(-3, 17, -3, 6, 14, 6, PAL['stone_light']); m.box(-7, 28, -7, 14, 3, 14, PAL['stone']); m.box(-1, 31, -1, 2, 8, 2, (180, 220, 250), emis=.5); m.box(-2, 39, -2, 4, 2, 4, (200, 235, 255), emis=.5)
    for i in range(8):
        a = 2 * math.pi * i / 8; m.box(math.cos(a) * 11 - .5, 11 + (i % 2) * 2, math.sin(a) * 11 - .5, 1, 4, 1, (190, 225, 250), emis=.4)


@recipe('perched_hut', group='Maisons et villages', label='Cabane perchée', kind='structure')
def perched_hut(m, seed=0):
    m.box(-8, 0, -8, 16, 60, 16, PAL['bark']); m.box(-10, 0, -10, 20, 4, 20, PAL['bark'])
    for i in range(3): m.box(-3 + i * 3, 50 + i * 5, -14 - i * 2, 20, 4, 8, PAL['bark'], ry=.4 * (i - 1))
    m.box(-26, 52, -26, 52, 3, 52, PAL['plank'])
    for sx in (-1, 1):
        for sz in (-1, 1): m.box(sx * 24 - 1, 55, sz * 24 - 1, 2, 10, 2, PAL['wood_dark'])
    m.box(-24, 55, 23, 48, 2, 2, PAL['wood_dark']); m.box(-24, 55, -25, 48, 2, 2, PAL['wood_dark'])
    _log_walls_h(m)
    _canopy(m, -14, 80, 0, 26, 12, 26, PAL['leaf_dark'], step=4); _canopy(m, 14, 88, -6, 22, 10, 22, PAL['leaf'], step=4)
    for i in range(10): m.box(-34, 4 + i * 5, 6, 2, 2, 12, PAL['wood_light']) if False else None
    for sx in (-1, 1): m.box(30 + sx * 0, 4, 10 + sx * 5, 2, 50, 2, PAL['wood'])
    for i in range(9): m.box(30, 6 + i * 5, 9, 2, 2, 8, PAL['wood_light'])
    m.emit(-4, 64, 20, 8, 7, 1, WIN, 1.3); m.light(0, 66, 24, WIN, .9, 4.)


def _log_walls_h(m):
    for r in range(6):
        y = 55 + r * 4
        m.box(-18, y, 14, 36, 4, 3, PAL['wood']); m.box(-18, y, -17, 36, 4, 3, PAL['wood']); m.box(-18, y, -17, 3, 4, 34, PAL['wood']); m.box(15, y, -17, 3, 4, 34, PAL['wood'])
    _gable(m, 36, 34, 79, PAL['leaf_dark'], over=4, step=3, layer=3, wall=PAL['wood'])
    m.box(-4, 56, 17, 8, 14, 1, PAL['wood_dark'])


@recipe('tent_camp', group='Maisons et villages', label='Camp de tentes', kind='structure')
def tent_camp(m, seed=0):
    def tent(cx, cz, w, d, h, c, c2):
        n = h // 3; stp = w / 2. / n
        for i in range(n):                                                    # toile à deux pans, pignon vers la caméra (+z)
            xw = w - 2 * i * stp; m.box(cx - xw / 2., i * 3, cz - d / 2., xw, 3, d, c if i % 2 == 0 else c2)
        for i in range(n - 1):
            xw = w - 2 * (i + 1) * stp - 2; m.box(cx - xw / 2., i * 3, cz + d / 2. - .5, xw, 3, 1.5, (34, 26, 22))
        m.box(cx - 1, 0, cz + d / 2. - .5, 2, h - 4, 1.5, PAL['wood_dark']); m.box(cx - 1, h - 1, cz - d / 2., 2, 3, d + 4, PAL['wood_dark'])
        m.box(cx - w / 2. - 1, 0, cz + d / 2. + 1, 3, 3, 3, PAL['rope']); m.box(cx + w / 2. - 2, 0, cz + d / 2. + 1, 3, 3, 3, PAL['rope'])
        m.box(cx - .5, h + 2, cz + d / 2., 1, 7, 1, PAL['wood_dark']); m.box(cx, h + 5, cz + d / 2., 7, 4, 1, PAL['cloth_red'])
    tent(-30, -14, 30, 30, 24, (176, 158, 122), (154, 136, 102)); tent(28, -12, 28, 28, 22, (112, 128, 96), (96, 112, 82)); tent(0, -46, 30, 26, 22, (150, 104, 92), (128, 88, 78))
    for i in range(8):
        a = 2 * math.pi * i / 8; m.box(math.cos(a) * 9 - 2, 0, 18 + math.sin(a) * 9 - 2, 4, 3, 4, PAL['stone'])
    m.box(-8, 2, 14, 16, 3, 3, PAL['bark'], ry=.4); m.box(-8, 2, 14, 16, 3, 3, PAL['bark'], ry=-.4); m.emit(-3, 3, 15, 6, 6, 6, FLAME, 1.7); m.emit(-1.5, 9, 16.5, 3, 5, 3, FLAME2, 2.0); m.light(0, 10, 18, FLAME, 1.8, 6.)
    m.box(-18, 0, 20, 8, 5, 3, PAL['wood_dark']); m.box(10, 0, 22, 8, 5, 3, PAL['wood_dark'])


# =================================================================================================== Ruines et mystère
@recipe('haunted_house', group='Ruines et mystère', label='Maison hantée', kind='structure')
def haunted_house(m, seed=0):
    dark = (76, 70, 78); roof = (46, 44, 56)
    _house(m, 64, 48, 44, dark, roof, lit=False, timber=False, chimney=False, base=PAL['stone_dark'])
    for sx in (-1, 1):
        for y in (13, 36): m.box(sx * 21 - 3, y, 24.5, 6, 7, 1, WIN_G, emis=1.2)
    m.light(0, 20, 34, WIN_G, 1.1, 6.)
    m.box(-12, 4, 24, 24, 2, 1.2, PAL['wood_dark']); m.box(20, 48, -14, 16, 26, 16, dark); _gable(m, 16, 16, 74, roof, over=2, wall=dark); m.box(25, 56, 2, 6, 8, 1, WIN_G, emis=1.3)
    for i in range(9): m.box(-32 + i * 0, 0, 0, 0, 0, 0, PAL['black']) if False else None
    for i in range(6): m.box(-44 + i * 8, 0, 34, 2, 12, 2, PAL['wood_dark']); m.box(-44 + i * 8, 10, 34, 8, 2, 1, PAL['wood_dark'])
    m.box(-50, 0, 10, 4, 22, 4, PAL['bark']); m.box(-56, 16, 8, 14, 3, 3, PAL['bark'], ry=.5); m.box(-48, 12, 14, 12, 3, 3, PAL['bark'], ry=-.4); m.box(-50, 22, 10, 3, 10, 3, PAL['bark'])


@recipe('ruined_chapel', group='Ruines et mystère', label='Chapelle en ruine', kind='structure')
def ruined_chapel(m, seed=0):
    w, d = 48, 80; S = PAL['stone']
    _stone(m, -w / 2., 0, -d / 2., w, 4, d, PAL['stone_dark'])
    _stone(m, -w / 2., 4, -d / 2., 4, 44, d, S); _stone(m, w / 2. - 4, 4, -d / 2., 4, 28, d - 24, S); _stone(m, -w / 2., 4, -d / 2., w, 56, 4, S)
    _stone(m, -w / 2., 4, d / 2. - 12, 14, 20, 4, S); _stone(m, w / 2. - 14, 4, d / 2. - 4, 14, 12, 4, S)
    m.box(-8, 28, -d / 2. - .5, 16, 18, 5, NIGHT); m.box(-10, 46, -d / 2. - .5, 20, 2, 5, S); m.box(-6, 50, -d / 2. - .5, 12, 2, 5, S); m.box(-2, 52, -d / 2. - .5, 4, 2, 5, S)         # fenêtre ogivale vide
    for z in (-20, 0, 20): m.box(-w / 2. - 2, 4, z - 3, 6, 36, 6, PAL['stone_light']); m.box(-w / 2. - 3, 40, z - 4, 8, 3, 8, PAL['stone_light'])
    m.box(-4, 8, -d / 2. + 8, 8, 4, 12, PAL['stone_light']); m.box(-2, 12, -d / 2. + 12, 4, 14, 2, PAL['stone_light']); m.box(-6, 22, -d / 2. + 12, 12, 3, 2, PAL['stone_light'])
    for (x, z, s) in [(-6, 10, 5), (4, 16, 4), (12, 0, 6), (-12, 26, 4), (8, 30, 5)]: m.box(x, 4, z, s, s - 1, s, S)
    _canopy(m, -14, 6, 18, 10, 4, 8, MOSS, step=3)


@recipe('crypt', group='Ruines et mystère', label='Crypte', kind='structure')
def crypt(m, seed=0):
    S = PAL['stone']
    for i in range(4): _stone(m, -34 + i * 2, i * 2, 24 - i * 6, 68 - i * 4, 2, 12, PAL['stone_light'])
    _stone(m, -28, 8, -20, 56, 30, 40, S); _stone(m, -30, 38, -22, 60, 4, 44, PAL['stone_dark'])
    for i in range(5): m.box(-32 + i * 3, 42 + i * 4, -22, 64 - i * 6, 4, 44, PAL['stone_dark'] if i % 2 else S) if i < 5 else None
    for sx in (-1, 1): _stone(m, sx * 20 - 4, 8, 20, 8, 30, 8, PAL['stone_light']); m.box(sx * 20 - 5, 38, 19, 10, 3, 10, PAL['stone_light'])
    m.box(-10, 8, 20, 20, 24, 2, NIGHT); m.box(-12, 8, 20, 2, 26, 3, PAL['iron_dark']); m.box(10, 8, 20, 2, 26, 3, PAL['iron_dark']); m.box(-12, 32, 20, 24, 3, 3, PAL['iron_dark'])
    for x in range(-8, 9, 4): m.box(x - .5, 9, 22, 1.5, 22, 1, PAL['iron'])
    m.emit(-8, 36, 22.5, 16, 1, 1, (120, 220, 255), 1.3); m.emit(-1, 16, 22.5, 2, 12, 1, (120, 220, 255), 1.3); m.light(0, 20, 28, (120, 220, 255), 1.0, 5.)
    m.box(-30, 8, 4, 3, 7, 3, PAL['bone']); _canopy(m, -30, 10, 18, 8, 4, 6, MOSS, step=3)


@recipe('witch_tower', group='Ruines et mystère', label='Tour de sorcière', kind='structure')
def witch_tower(m, seed=0):
    for i, (r, h) in enumerate([(22, 22), (20, 20), (18, 20), (16, 18)]):
        y0 = [0, 22, 42, 62][i]
        for j in range(16):
            a = 2 * math.pi * j / 16; m.box(math.cos(a) * r - 4, y0, math.sin(a) * r - 4, 8, h, 8, PAL['stone'] if j % 2 else PAL['stone_dark'])
    for j in range(16):
        a = 2 * math.pi * j / 16; m.box(math.cos(a) * 20 - 3, 80, math.sin(a) * 20 - 3, 6, 4, 6, PAL['wood_dark'])
    for i, (r, h) in enumerate([(18, 4), (15, 4), (12, 4), (9, 4), (6, 4), (3, 4)]):
        m.box(-r, 84 + i * 4, -r, 2 * r, h, 2 * r, (74, 52, 98) if i % 2 else (88, 62, 112))
    m.box(-1, 108, -1, 2, 10, 2, PAL['wood_dark']); m.box(-4, 116, -1, 8, 2, 2, PAL['cloth_red'])
    for (y, a) in ((16, 1.57), (36, 0.4), (54, 2.9), (72, 4.7)):
        x, z = math.cos(a) * 21, math.sin(a) * 21; m.box(x - 3, y, z - 3, 6, 8, 6, (190, 110, 255), emis=1.4)
    m.light(0, 40, 26, (190, 110, 255), 1.4, 7.)
    m.box(-4, 0, 20, 8, 14, 4, PAL['wood_dark']); m.box(24, 40, -6, 14, 3, 14, PAL['wood']); m.box(24, 43, -6, 14, 2, 2, PAL['wood_dark'])
    m.box(26, 46, 2, 3, 5, 3, PAL['black']); m.box(-9, 100, 12, 8, 12, 3, PAL['wood_dark'], ry=.3) if False else None


@recipe('menhirs', group='Ruines et mystère', label='Cercle de menhirs', kind='structure', variants=2)
def menhirs(m, seed=0):
    n = 9 + seed % 2 * 3; S = PAL['stone']
    for i in range(n):
        a = 2 * math.pi * i / n; h = 26 + (i * 7 % 5) * 6 + (10 if seed % 2 else 0); r = 36 if seed % 2 == 0 else 40; x, z = math.cos(a) * r, math.sin(a) * r
        m.box(x - 4, 0, z - 3, 8, h, 6, S if i % 2 else PAL['stone_dark']); m.box(x - 3, h, z - 2.5, 6, 4, 5, S); m.box(x - 2, h + 4, z - 2, 4, 3, 4, S)
        m.box(x - 3, 8, z + 3, 2, 4, 1, MOSS)
    m.box(-10, 0, -8, 20, 10, 16, PAL['stone_dark']); m.box(-8, 10, -6, 16, 2, 12, PAL['stone']); m.emit(-4, 12, -2, 8, 1, 4, (120, 255, 190), 1.2); m.light(0, 14, 0, (120, 255, 190), .9, 5.)
    if seed % 2 == 0:
        for sx in (-1, 1): m.box(sx * 8 - 3, 0, -34, 6, 30, 6, S)
        m.box(-14, 30, -35, 28, 5, 8, PAL['stone_light'])


@recipe('temple_ruins', group='Ruines et mystère', label='Ruines de temple', kind='structure')
def temple_ruins(m, seed=0):
    S = PAL['stone_light']
    for i in range(3): _stone(m, -50 + i * 4, i * 4, -36 + i * 4, 100 - i * 8, 4, 72 - i * 8, PAL['sand'] if i == 0 else S)
    for i in range(6):
        x = -36 + i * 14; h = [34, 22, 38, 8, 30, 14][i]
        m.box(x - 5, 12, -22, 10, 3, 10, PAL['stone']); m.box(x - 4, 15, -21, 8, h, 8, S); m.box(x - 5, 15 + h, -22, 10, 3, 10, PAL['stone']) if h > 20 else None
        m.box(x - 5, 12, 6, 10, 3, 10, PAL['stone']); m.box(x - 4, 15, 7, 8, [30, 38, 12, 34, 20, 36][i], 8, S)
    m.box(-36, 49, -22, 40, 5, 10, PAL['stone']); m.box(14, 40, 7, 30, 5, 10, PAL['stone'], ry=.06)
    for (x, z, s) in [(-10, 20, 6), (20, -4, 5), (-30, 4, 4), (38, -20, 6)]: m.box(x, 12, z, s, s - 2, s, PAL['stone'])
    _canopy(m, 30, 14, 22, 12, 4, 10, MOSS, step=3); _canopy(m, -34, 14, -24, 8, 5, 8, PAL['leaf'], step=3)


@recipe('ancient_portal', group='Ruines et mystère', label='Portail de pierre antique', kind='structure')
def ancient_portal(m, seed=0):
    S = PAL['stone']
    m.box(-34, 0, -10, 68, 6, 20, PAL['stone_dark'])
    for sx in (-1, 1):
        _stone(m, sx * 24 - 5, 6, -6, 10, 56, 12, S); m.box(sx * 24 - 6, 62, -7, 12, 4, 14, PAL['stone_light'])
        for y in (14, 26, 38, 50): m.emit(sx * 24 - 2 - (0 if sx < 0 else 0), y, 6.5, 4, 3, 1, (120, 255, 220), 1.5)
    for i in range(6): m.box(-24 + i * 4, 62 + i * 3, -6, 48 - i * 8, 3, 12, S if i % 2 else PAL['stone_light'])
    m.box(-6, 80, -7, 12, 5, 14, PAL['stone_light']); m.emit(-3, 82, 7.5, 6, 2, 1, (120, 255, 220), 1.6)
    m.box(-20, 6, -1, 40, 52, 1, (60, 230, 200), emis=1.1); m.box(-14, 14, 0, 28, 36, 1, (190, 255, 240), emis=1.5); m.box(-6, 26, 1, 12, 12, 1, (255, 255, 255), emis=1.8)
    m.light(0, 30, 16, (110, 255, 220), 1.8, 8.)


@recipe('graveyard', group='Ruines et mystère', label='Cimetière', kind='structure')
def graveyard(m, seed=0):
    I = PAL['iron_dark']
    m.box(-52, 0, -36, 104, 2, 72, (52, 62, 44))
    for x in range(-52, 53, 8):
        if abs(x) < 10: continue
        m.box(x - .7, 2, 36, 1.5, 22, 1.5, I); m.box(x - 1.5, 24, 35.5, 3, 3, 3, I) if x % 16 == 0 else None
    for sx in (-1, 1):
        m.box(sx * 52 - 2, 0, 34, 4, 28, 4, PAL['stone_dark']); m.box(sx * 52 - 3, 28, 33, 6, 3, 6, PAL['stone'])
        m.box(sx * 10 - 2, 0, 34, 4, 28, 4, PAL['stone_dark']); m.box(sx * 10 - 3, 28, 33, 6, 3, 6, PAL['stone']); m.emit(sx * 10 - 1, 31, 35, 2, 3, 2, FLAME2, 1.8)
    m.box(-10, 22, 35.5, 20, 2, 2, I);
    for i in range(7): m.box(-8 + i * 3, 24 + (3 - abs(i - 3)), 35.5, 1.5, 6 - (3 - abs(i - 3)) * 0 + 0, 1.5, I) if False else None
    for x in (-8, -4, 0, 4, 8): m.box(x - .5, 3, 36, 1.5, 19, 1, I)
    for (x, z, k) in [(-36, 10, 0), (-20, 0, 1), (-4, 14, 2), (14, 4, 0), (30, 16, 1), (40, -8, 2), (-30, -16, 1), (10, -14, 0), (-8, -24, 2)]:
        h = 14 + (x * 3 % 9); m.box(x - 5, 2, z - 2, 10, 3, 5, PAL['mud']); m.box(x - 4, 3, z - 2, 8, h, 3, PAL['stone'])
        if k == 1: m.box(x - 7, 3 + h - 8, z - 2, 14, 4, 3, PAL['stone'])
        else: m.box(x - 3, 3 + h, z - 2, 6, 2, 3, PAL['stone']); m.box(x - 2, 3 + h + 2, z - 2, 4, 1, 3, PAL['stone'])
    m.box(34, 2, -30, 4, 40, 4, PAL['bark']); m.box(26, 26, -30, 14, 3, 3, PAL['bark'], ry=.5); m.box(36, 34, -30, 14, 3, 3, PAL['bark'], ry=-.4); m.box(34, 40, -30, 3, 10, 3, PAL['bark'])
    m.box(-46, 2, -30, 32, 22, 12, PAL['stone']); m.box(-48, 24, -31, 36, 4, 14, PAL['stone_dark']); m.box(-34, 2, -18.5, 8, 14, 1, NIGHT)


@recipe('arch', group='Ruines et mystère', label='Arche', kind='structure', variants=2)
def arch(m, seed=0):
    S = PAL['stone'] if seed % 2 == 0 else PAL['stone_light']
    for sx in (-1, 1):
        _stone(m, sx * 22 - 5, 0, -6, 10, 46, 12, S)
        for i in range(8): m.box(sx * (22 - i * 2.2) - 4 if sx > 0 else sx * (22 - i * 2.2) - 4, 46 + i * 4, -6, 8, 4, 12, S if i % 2 else PAL['stone_dark'])
    m.box(-5, 76, -6, 10, 5, 12, PAL['stone_light']); m.box(-34, 0, -9, 68, 3, 18, PAL['stone_dark'])
    _canopy(m, -24, 40, 6, 4, 8, 3, MOSS, step=3)
    if seed % 2: m.emit(-3, 70, 6.5, 6, 3, 1, (255, 220, 120), 1.4); m.light(0, 60, 14, (255, 220, 120), .9, 5.)


@recipe('mine_entrance', group='Ruines et mystère', label='Entrée de mine', kind='structure')
def mine_entrance(m, seed=0):
    for i in range(7): _stone(m, -50 + i * 4, i * 10, -30, 100 - i * 8, 10, 40 - i * 2, PAL['stone'] if i % 2 else PAL['stone_dark'])
    m.box(-12, 0, 8, 24, 30, 2, NIGHT)
    for sx in (-1, 1): m.box(sx * 13 - 2, 0, 9, 4, 34, 4, PAL['wood'])
    m.box(-17, 30, 9, 34, 5, 5, PAL['wood']); m.box(-12, 34, 9, 24, 3, 5, PAL['wood_dark'])
    for z in range(10, 46, 6): m.box(-9, 0, z, 18, 1, 3, PAL['wood_dark'])
    for sx in (-1, 1): m.box(sx * 6 - .7, 1, 10, 1.5, 1, 36, PAL['iron'])
    m.box(-2, 26, 14, 4, 2, 1, PAL['iron_dark']); m.box(-3, 18, 14, 6, 8, 3, PAL['iron_dark']); m.emit(-2, 19, 17, 4, 6, 1, WIN, 1.4); m.light(0, 22, 20, WIN, 1.3, 5.)
    m.box(14, 0, 22, 10, 8, 14, PAL['wood_dark']); m.box(16, 8, 24, 6, 3, 8, PAL['gold']); m.box(-26, 0, 20, 8, 6, 6, PAL['stone_dark'])


# =================================================================================================== Fortifications
@recipe('watchtower', group='Fortifications', label='Tour de guet', kind='structure')
def watchtower(m, seed=0):
    for sx in (-1, 1):
        for sz in (-1, 1): m.box(sx * 14 - 2, 0, sz * 14 - 2, 4, 64, 4, PAL['wood_dark'])
    for y in (14, 36):
        for z in (-14, 12): m.box(-14, y, z - 1, 28, 3, 4, PAL['wood'])
        for x in (-14, 12): m.box(x - 1, y, -14, 4, 3, 28, PAL['wood'])
    m.box(-22, 64, -22, 44, 3, 44, PAL['plank'])
    for z in (-22, 20): m.box(-22, 67, z, 44, 3, 2, PAL['wood'])
    for x in (-22, 20): m.box(x, 67, -22, 2, 3, 44, PAL['wood'])
    for sx in (-1, 1):
        for sz in (-1, 1): m.box(sx * 18 - 1.5, 67, sz * 18 - 1.5, 3, 18, 3, PAL['wood_dark'])
    for i, w in enumerate((46, 36, 26, 16)): m.box(-w / 2., 85 + i * 4, -w / 2., w, 4, w, TILE)
    m.box(-12, 8, 14, 3, 62, 2, PAL['wood']); m.box(-4, 8, 14, 3, 62, 2, PAL['wood'])
    for y in range(12, 66, 8): m.box(-12, y, 14, 11, 2, 2, PAL['wood'])
    m.emit(-2, 70, 12, 4, 6, 4, WIN, 1.4); m.light(0, 74, 16, WIN, 1.2, 6.)


@recipe('castle_wall', group='Fortifications', label='Mur de château', kind='structure')
def castle_wall(m, seed=0):
    _stone(m, -48, 0, -8, 96, 40, 16); m.box(-50, 0, -9, 100, 4, 18, PAL['stone_dark']); m.box(-48, 40, -4, 96, 2, 8, PAL['stone_dark'])
    for x in range(-48, 48, 16): m.box(x, 42, 4, 8, 8, 4, PAL['stone']); m.box(x, 42, -8, 8, 8, 4, PAL['stone'])
    for sx in (-1, 1): _stone(m, sx * 44 - 4, 0, -12, 8, 48, 24, PAL['stone_light'])
    for x in (-24, 0, 24): m.box(x - 1, 18, 8, 2, 12, 1, NIGHT)
    for x in (-34, 34):
        m.box(x - 1, 24, 8, 2, 6, 2, PAL['iron_dark']); m.emit(x - 1.5, 30, 8, 3, 4, 3, FLAME, 1.7); m.light(x, 32, 12, FLAME, 1.4, 5.)
    m.box(8, 12, 8, 2, 2, 1, PAL['iron_dark']); m.box(8, 8, 8, 10, 14, 1, PAL['cloth_red']); m.box(10, 14, 9, 6, 4, 1, PAL['gold'])


@recipe('town_gate', group='Fortifications', label='Porte de ville', kind='structure')
def town_gate(m, seed=0):
    for sx in (-1, 1):
        _stone(m, sx * 40 - 14, 0, -14, 28, 70, 28, PAL['stone']); m.box(sx * 40 - 16, 70, -16, 32, 4, 32, PAL['stone_dark'])
        for i in range(4): m.box(sx * 40 - 16 + i * 10, 74, 12, 6, 6, 4, PAL['stone']); m.box(sx * 40 - 16 + i * 10, 74, -16, 6, 6, 4, PAL['stone'])
        m.box(sx * 40 - 1, 40, 14, 2, 12, 1, NIGHT); m.box(sx * 40 - 5, 52, 14.5, 10, 18, 1, PAL['cloth_red'] if sx < 0 else PAL['cloth_blue'])
    _stone(m, -26, 46, -10, 52, 22, 20, PAL['stone']); m.box(-28, 66, -12, 56, 4, 24, PAL['stone_dark'])
    for i in range(5): m.box(-26 + i * 2, 40 + i * 1.5, -10, 52 - i * 4, 2, 20, PAL['stone_dark'])
    for x in range(-22, 23, 6): m.box(x - 1, 0, 6, 2, 44, 2, PAL['iron_dark'])
    for y in (10, 26, 40): m.box(-24, y, 6, 48, 2, 2, PAL['iron_dark'])
    m.box(-26, 0, -12, 52, 3, 24, PAL['stone_dark']); m.emit(-27, 36, 10, 3, 5, 3, FLAME, 1.7); m.emit(24, 36, 10, 3, 5, 3, FLAME, 1.7); m.light(0, 38, 16, FLAME, 1.5, 7.)


# =================================================================================================== Ponts et ports
@recipe('stone_bridge', group='Ponts et ports', label='Pont de pierre', kind='structure')
def stone_bridge(m, seed=0):
    for (y, wopen, h) in [(14, 24, 4), (10, 40, 4), (6, 52, 4), (2, 58, 4), (0, 62, 2)]:
        for sx in (-1, 1):
            x0 = wopen / 2. if sx > 0 else -60; w = 60 - wopen / 2.
            m.box(x0, y, -12, w, h, 24, PAL['stone_dark'] if y > 8 else PAL['stone'])
    _stone(m, -60, 18, -12, 120, 4, 24, PAL['stone_light'], courses=4)
    for z in (-12, 9): m.box(-60, 22, z, 120, 7, 3, PAL['stone'])
    for x in range(-60, 60, 20):
        for z in (-12, 9): m.box(x, 29, z, 6, 3, 3, PAL['stone_light'])
    for sx in (-1, 1): m.box(sx * 60 - 4, 0, -14, 8, 30, 28, PAL['stone_dark'])
    m.emit(-1.5, 30, -13, 3, 5, 3, WIN, 1.3); m.light(0, 34, -8, WIN, 1.0, 5.)


@recipe('wood_bridge', group='Ponts et ports', label='Pont de bois', kind='structure')
def wood_bridge(m, seed=0):
    m.box(-60, 10, -8, 120, 2, 16, PAL['plank']); m.box(-60, 8, -6, 120, 2, 3, PAL['wood_dark']); m.box(-60, 8, 3, 120, 2, 3, PAL['wood_dark'])
    for x in (-56, -24, 8, 40):
        for z in (-8, 5): m.box(x, 0, z, 3, 10, 3, PAL['wood_dark'])
        m.box(x - 1, 4, -8, 5, 2, 16, PAL['wood'])
    for z in (-8, 6): m.box(-60, 17, z, 120, 2, 2, PAL['wood'])
    for x in range(-60, 61, 20):
        for z in (-8, 6): m.box(x - 1, 12, z, 2, 9, 2, PAL['wood_dark'])
    for x in range(-60, 60, 8): m.box(x, 12, -8, 1, 1, 16, PAL['wood'])
    m.box(-62, 0, -10, 6, 12, 20, PAL['stone_dark']); m.box(56, 0, -10, 6, 12, 20, PAL['stone_dark'])


@recipe('pier', group='Ponts et ports', label='Ponton', kind='structure')
def pier(m, seed=0):
    m.box(-12, 8, -50, 24, 2, 100, PAL['plank'])
    for z in range(-48, 49, 24):
        for sx in (-1, 1): m.box(sx * 10 - 2, 0, z, 4, 8, 4, PAL['wood_dark'])
        m.box(-12, 6, z, 24, 2, 3, PAL['wood'])
    for z in (-46, 0, 46):
        for sx in (-1, 1): m.box(sx * 12 - 2, 10, z, 4, 8, 4, PAL['wood_dark']); m.box(sx * 12 - 3, 18, z - 1, 6, 2, 6, PAL['iron_dark'])
    m.box(-2, 10, -48, 4, 28, 4, PAL['wood_dark']); m.emit(-3, 38, -49, 6, 6, 6, WIN, 1.4); m.light(0, 40, -46, WIN, 1.4, 6.)
    for i, (y, w) in enumerate([(2, 22), (4, 26), (6, 28)]): m.box(18, y, 10 - w / 2., 22 - i * 2, 2, w, PAL['wood'] if i < 2 else PAL['cloth_red'])
    m.box(20, 8, -4, 18, 1, 2, PAL['wood_light']); m.box(-10, 10, 30, 6, 6, 6, PAL['wood_dark']); m.box(-10, 16, 30, 6, 1, 6, PAL['rope'])


@recipe('lighthouse', group='Ponts et ports', label='Phare', kind='structure')
def lighthouse(m, seed=0):
    for i, (w, c) in enumerate([(40, PAL['white']), (36, PAL['cloth_red']), (32, PAL['white']), (28, PAL['cloth_red']), (26, PAL['white'])]):
        m.box(-w / 2., 6 + i * 22, -w / 2., w, 22, w, c)
    m.box(-24, 0, -24, 48, 6, 48, PAL['stone_dark']); m.box(-20, 116, -20, 40, 3, 40, PAL['iron_dark'])
    for z in (-20, 18): m.box(-20, 119, z, 40, 3, 2, PAL['iron_dark'])
    for x in (-20, 18): m.box(x, 119, -20, 2, 3, 40, PAL['iron_dark'])
    for sx in (-1, 1):
        for sz in (-1, 1): m.box(sx * 9 - 1, 119, sz * 9 - 1, 2, 18, 2, PAL['iron_dark'])
    m.emit(-8, 119, -8, 16, 16, 16, (255, 236, 170), 2.0); m.box(-11, 135, -11, 22, 3, 22, PAL['iron_dark'])
    for i, w in enumerate((20, 14, 8, 3)): m.box(-w / 2., 138 + i * 4, -w / 2., w, 4, w, PAL['cloth_red'])
    m.light(0, 128, 14, (255, 236, 170), 2.6, 14.)
    _door(m, 0, 6, 20, 8, 15); m.box(-30, 0, 24, 18, 10, 14, PAL['wood_dark']); _gable(m, 18, 14, 10, TILE, over=2, layer=2, step=2, wall=PAL['wood_dark'])


# =================================================================================================== Parcours et plateformes
@recipe('platform_stone', group='Parcours et plateformes', label='Plateforme de pierre flottante', kind='structure', variants=2)
def platform_stone(m, seed=0):
    k = seed % 2
    m.box(-24, 18, -24, 48, 6, 48, PAL['stone']); m.box(-24, 24, -24, 48, 2, 48, MOSS)
    for i, w in enumerate((40, 30, 20, 10)): m.box(-w / 2., 12 - i * 6, -w / 2., w, 6, w, PAL['stone_dark'])
    if k:
        m.box(-12, 26, -12, 24, 4, 24, PAL['stone_light']); m.emit(-5, 30, -5, 10, 1, 10, (120, 255, 200), 1.3); m.light(0, 34, 0, (120, 255, 200), .9, 5.)
    else:
        m.box(-20, 26, 14, 8, 8, 8, PAL['stone_dark']); m.box(12, 26, -20, 6, 5, 6, PAL['stone_dark'])


@recipe('platform_wood', group='Parcours et plateformes', label='Plateforme de bois suspendue', kind='structure')
def platform_wood(m, seed=0):
    m.box(-26, 24, -18, 52, 4, 36, PAL['plank']); m.box(-26, 20, -14, 52, 4, 3, PAL['wood_dark']); m.box(-26, 20, 10, 52, 4, 3, PAL['wood_dark']); m.box(-4, 20, -18, 8, 4, 36, PAL['wood_dark'])
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = sx * 24, sz * 16; m.box(x - 3, 24, z - 3, 6, 6, 6, PAL['iron_dark']); m.box(x - .5, 30, z - .5, 1, 40, 1, PAL['rope']); m.box(x - 2, 70, z - 2, 4, 2, 4, PAL['iron_dark'])
    m.box(-28, 28, -20, 56, 1, 2, PAL['wood']); m.box(-28, 28, 18, 56, 1, 2, PAL['wood'])


@recipe('platform_neon', group='Parcours et plateformes', label='Plateforme à liseré lumineux', kind='structure')
def platform_neon(m, seed=0):
    C = (80, 220, 255)
    m.box(-26, 16, -18, 52, 8, 36, PAL['coal']); m.box(-22, 8, -14, 44, 8, 28, (40, 42, 52)); m.box(-14, 2, -8, 28, 6, 16, (30, 32, 40))
    for z in (-18, 17): m.emit(-26, 24, z, 52, 1, 1, C, 1.5)
    for x in (-26, 25): m.emit(x, 24, -18, 1, 1, 36, C, 1.5)
    m.emit(-24, 24, -.5, 48, 1, 1, C, .9); m.emit(-14, 12, -14.5, 28, 1, 1, C, 1.1); m.light(0, 30, 0, C, 1.1, 6.)


@recipe('spinning_bar', group='Parcours et plateformes', label='Barre tournante', kind='structure', variants=2)
def spinning_bar(m, seed=0):
    m.box(-20, 0, -20, 40, 3, 40, PAL['stone']); m.box(-6, 3, -6, 12, 26, 12, PAL['stone_dark']); m.box(-9, 29, -9, 18, 6, 18, PAL['iron_dark'])
    a = .45 if seed % 2 == 0 else 1.25; Y = (230, 190, 50); K = (36, 36, 40)
    for i in range(8):
        t = (i - 3.5) * 10; m.box(t * math.cos(a) - 5, 32, -t * math.sin(a) - 3, 10, 4, 6, Y if i % 2 == 0 else K, ry=a)
    for s in (-1, 1): m.box(s * 40 * math.cos(a) - 2, 31, -s * 40 * math.sin(a) - 4, 4, 6, 8, PAL['iron_dark'], ry=a)


@recipe('lava_islands', group='Parcours et plateformes', label='Sol de lave et îlots', kind='structure')
def lava_islands(m, seed=0):
    m.box(-50, 0, -50, 100, 3, 100, PAL['lava'], emis=.9)
    for (sx, sz, w, d) in ((-1, -1, 100, 4), (-1, 1, 100, 4)): m.box(-50, 0, sz * 48 - (2 if sz < 0 else 2), w, 6, d, PAL['stone_dark'])
    for sx in (-1, 1): m.box(sx * 48 - 2, 0, -50, 4, 6, 100, PAL['stone_dark'])
    for (x, z, w, d, h) in [(-34, 30, 24, 20, 8), (-6, 8, 18, 18, 6), (22, -14, 22, 16, 8), (36, 32, 14, 14, 6), (-30, -26, 16, 16, 6)]:
        m.box(x - w / 2., 0, z - d / 2., w, h, d, PAL['stone']); m.box(x - w / 2. + 2, h, z - d / 2. + 2, w - 4, 1, d - 4, PAL['stone_light'])
    m.box(-6, 6, 4, 4, 18, 4, PAL['wood_dark']); m.box(-4, 20, 4, 8, 4, 1, PAL['cloth_red'])
    m.light(0, 10, 0, (255, 110, 40), 1.8, 12.)


@recipe('springboard', group='Parcours et plateformes', label='Tremplin', kind='structure')
def springboard(m, seed=0):
    m.box(-18, 0, -14, 36, 3, 28, PAL['wood_dark'])
    for i in range(5): m.box(-9, 3 + i * 4, -7, 18, 1.5, 14, PAL['iron'])
    for sx in (-1, 1): m.box(sx * 9 - 1, 3, -9, 2, 20, 2, PAL['iron_dark']); m.box(sx * 9 - 1, 3, 7, 2, 20, 2, PAL['iron_dark'])
    m.box(-20, 23, -16, 40, 3, 32, (176, 52, 52)); m.box(-20, 26, -16, 40, 1, 3, PAL['white']); m.box(-20, 26, 13, 40, 1, 3, PAL['white'])
    m.box(-8, 26, -3, 16, 1, 3, PAL['white']); m.box(-4, 26, 1, 8, 1, 3, PAL['white'])


@recipe('checkpoint_gate', group='Parcours et plateformes', label='Porte de point de passage', kind='structure')
def checkpoint_gate(m, seed=0):
    G = (90, 255, 140)
    for sx in (-1, 1): _stone(m, sx * 28 - 4, 0, -5, 8, 48, 10, PAL['stone'])
    m.box(-32, 48, -5, 64, 5, 10, PAL['stone_dark']); m.emit(-24, 40, -1, 48, 3, 2, G, 1.6)
    for sx in (-1, 1): m.emit(sx * 24 - 1, 4, -1, 2, 36, 2, G, 1.3)
    m.emit(-24, 0, -12, 48, 1, 1, G, 1.1); m.emit(-24, 0, 11, 48, 1, 1, G, 1.1)
    m.box(-1, 53, -1, 2, 14, 2, PAL['wood_dark']); m.box(1, 60, -.5, 12, 7, 1, G, emis=.9); m.light(0, 30, 10, G, 1.3, 7.)


@recipe('suspension_bridge', group='Parcours et plateformes', label='Pont suspendu', kind='structure')
def suspension_bridge(m, seed=0):
    ys = [10, 8, 6, 5, 5, 6, 8, 10]
    for i, y in enumerate(ys): m.box(-64 + i * 16, y, -8, 16, 2, 16, PAL['plank'])
    for sx in (-1, 1):
        for sz in (-1, 1): m.box(sx * 64 - 3, 0, sz * 10 - 3, 6, 48, 6, PAL['wood_dark'])
        m.box(sx * 64 - 4, 44, -14, 8, 4, 28, PAL['wood'])
    cy = [46, 38, 30, 26, 26, 30, 38, 46]
    for sz in (-1, 1):
        for i, y in enumerate(cy): m.box(-64 + i * 16, y, sz * 10 - 1, 16, 2, 2, PAL['rope'])
        for i in range(1, 8): m.box(-64 + i * 16 - .5, ys[min(i, 7)] + 2, sz * 10 - .5, 1, cy[i] - ys[min(i, 7)] - 2, 1, PAL['rope'])


@recipe('slide', group='Parcours et plateformes', label='Toboggan', kind='structure')
def slide(m, seed=0):
    for i in range(6): m.box(-40 + i * 4, 0, -10, 4, 8 + i * 6, 20, PAL['wood'] if i % 2 else PAL['plank'])
    m.box(-18, 38, -12, 14, 3, 24, PAL['plank']); m.box(-18, 41, -12, 14, 3, 2, PAL['wood_dark']); m.box(-18, 41, 10, 14, 3, 2, PAL['wood_dark'])
    for sx in (-1, 0): m.box(-18 + sx * 0 - (0 if sx else 0), 0, -12, 3, 38, 3, PAL['wood_dark']) if False else None
    for sz in (-1, 1): m.box(-18, 0, sz * 11 - 1.5, 3, 38, 3, PAL['wood_dark'])
    B = (60, 110, 190)
    for i in range(9): m.box(-4 + i * 7, 36 - i * 4, -8, 7, 3, 16, B); m.box(-4 + i * 7, 39 - i * 4, -9, 7, 3, 2, B); m.box(-4 + i * 7, 39 - i * 4, 7, 7, 3, 2, B)
    m.box(56, 0, -9, 10, 2, 18, PAL['sand'])


@recipe('climbing_wall', group='Parcours et plateformes', label="Mur d'escalade", kind='structure')
def climbing_wall(m, seed=0):
    m.box(-24, 0, -4, 48, 56, 6, PAL['stone_dark']); m.box(-26, 0, -5, 3, 58, 8, PAL['wood']); m.box(23, 0, -5, 3, 58, 8, PAL['wood']); m.box(-28, 56, -10, 56, 3, 16, PAL['wood'])
    for i, (x, y) in enumerate([(-16, 6), (-4, 10), (12, 8), (4, 18), (-14, 22), (16, 26), (-4, 30), (-16, 38), (8, 40), (18, 46), (-8, 48), (0, 20)]):
        m.box(x - 4, y, 2, 8, 2, 3, [(200, 60, 52), (230, 190, 60), (70, 130, 200)][i % 3])                    # prises allongées, pas des cubes
    m.box(-28, 0, 3, 56, 3, 22, (60, 110, 170)); m.box(-28, 3, 3, 56, 1, 2, PAL['white'])


@recipe('narrow_walkway', group='Parcours et plateformes', label='Passerelle étroite', kind='structure')
def narrow_walkway(m, seed=0):
    m.box(-60, 24, -2, 120, 3, 4, PAL['wood'])
    for x in (-56, -16, 24, 56): m.box(x - 2, 0, -2, 4, 24, 4, PAL['wood_dark'])
    for x in (-56, -16, 24, 56): m.box(x - 1, 27, -3, 2, 12, 2, PAL['wood_dark'])
    m.box(-60, 36, -3, 120, 1, 1, PAL['rope']); m.box(-60, 32, -3, 120, 1, 1, PAL['rope'])
    m.box(-64, 0, -6, 8, 24, 12, PAL['stone_dark']); m.box(56, 0, -6, 8, 24, 12, PAL['stone_dark'])


@recipe('spikes', group='Parcours et plateformes', label='Piques', kind='structure')
def spikes(m, seed=0):
    m.box(-24, 0, -24, 48, 3, 48, PAL['iron_dark'])
    for i in range(4):
        for j in range(4):
            x, z = -18 + i * 12, -18 + j * 12; m.box(x - 2, 3, z - 2, 4, 6, 4, PAL['iron']); m.box(x - 1, 9, z - 1, 2, 7, 2, (206, 210, 220)); m.box(x - .5, 16, z - .5, 1, 4, 1, (230, 232, 240))
    m.box(-26, 0, -26, 52, 4, 2, PAL['stone_dark']); m.box(-26, 0, 24, 52, 4, 2, PAL['stone_dark'])


@recipe('light_portal', group='Parcours et plateformes', label='Portail lumineux', kind='structure')
def light_portal(m, seed=0):
    B = (110, 190, 255)
    m.box(-28, 0, -8, 56, 6, 16, PAL['stone_dark']); m.box(-22, 6, -6, 44, 4, 12, PAL['stone'])
    m.box(-24, 14, -3, 5, 36, 6, PAL['stone_light']); m.box(19, 14, -3, 5, 36, 6, PAL['stone_light']); m.box(-18, 50, -3, 36, 5, 6, PAL['stone_light']); m.box(-18, 9, -3, 36, 5, 6, PAL['stone_dark'])
    for (x, y) in ((-22, 44), (17, 44), (-22, 9), (17, 9)): m.box(x, y, -3, 5, 6, 6, PAL['stone'])
    m.emit(-19, 14, -2, 2, 36, 4, B, 1.2); m.emit(17, 14, -2, 2, 36, 4, B, 1.2); m.emit(-17, 48, -2, 34, 2, 4, B, 1.2); m.emit(-17, 14, -2, 34, 2, 4, B, 1.2)       # liseré lumineux autour de l'ouverture
    m.emit(-17, 16, -.5, 34, 32, 1, (150, 205, 255), .55); m.emit(-9, 24, 0, 18, 16, 1, (210, 235, 255), .8); m.light(0, 32, 12, B, 1.2, 7.)


@recipe('conveyor', group='Parcours et plateformes', label='Tapis roulant', kind='structure')
def conveyor(m, seed=0):
    for z in (-12, 9): m.box(-40, 4, z, 80, 8, 3, PAL['iron_dark'])
    for x in (-36, -12, 12, 34): m.box(x - 2, 0, -12, 4, 4, 24, PAL['iron_dark'])
    m.box(-40, 8, -9, 80, 2, 18, PAL['coal']); m.box(-42, 6, -10, 4, 6, 20, PAL['iron']); m.box(38, 6, -10, 4, 6, 20, PAL['iron'])
    A = (255, 190, 60)
    for i in range(6):
        x = -30 + i * 12
        for s in (-1, 1): m.emit(x - 4, 10, s * 3.5 - 1, 8, 1, 2, A, .9) if False else None
        m.box(x - 4, 10, -6, 8, 1, 2, A, emis=.8, ry=.6); m.box(x - 4, 10, 3, 8, 1, 2, A, emis=.8, ry=-.6)


@recipe('jump_pillar', group='Parcours et plateformes', label='Pilier à sauter', kind='structure', variants=2)
def jump_pillar(m, seed=0):
    k = seed % 2; ex = 16 if k else 0
    m.box(-10, 0, -10, 20, 16, 20, PAL['stone_dark']); m.box(-8, 16, -8, 16, 16 + ex, 16, PAL['stone']); m.box(-7, 32 + ex, -7, 14, 14, 14, PAL['stone_light'])
    m.box(-13, 46 + ex, -13, 26, 3, 26, PAL['wood']); m.box(-13, 49 + ex, -13, 26, 1, 3, PAL['wood_dark']); m.box(-13, 49 + ex, 10, 26, 1, 3, PAL['wood_dark'])
    if k: m.box(-9, 14, -9, 18, 3, 18, MOSS)


@recipe('platform_spiral', group='Parcours et plateformes', label='Spirale de plateformes', kind='structure')
def platform_spiral(m, seed=0):
    m.box(-4, 0, -4, 8, 104, 8, PAL['stone_dark']); m.box(-16, 0, -16, 32, 4, 32, PAL['stone'])
    for i in range(8):
        a = i * .85; m.box(math.cos(a) * 34 - 11, 10 + i * 11, math.sin(a) * 34 - 8, 22, 4, 16, PAL['stone'] if i % 2 else PAL['stone_light'], ry=-(a + math.pi / 2))
    m.box(-12, 100, -12, 24, 4, 24, PAL['stone_light']); m.emit(-3, 104, -3, 6, 1, 6, (120, 255, 200), 1.3); m.light(0, 110, 0, (120, 255, 200), 1.0, 6.)


@recipe('start_arch', group='Parcours et plateformes', label='Arche de départ', kind='structure')
def start_arch(m, seed=0):
    G = (90, 255, 140)
    for sx in (-1, 1): m.box(sx * 30 - 3, 0, -4, 6, 52, 8, PAL['wood_dark']); m.box(sx * 30 - 5, 0, -6, 10, 4, 12, PAL['stone'])
    m.box(-36, 50, -4, 72, 6, 8, PAL['wood']); m.emit(-30, 44, -3, 60, 3, 2, G, 1.5); m.box(-34, 56, -4, 68, 2, 8, PAL['wood_dark'])
    for sx in (-1, 1): m.box(sx * 22 - 4, 28, 4, 8, 16, 1, PAL['cloth_red'] if sx < 0 else PAL['cloth_blue']); m.box(sx * 22 - .5, 44, 4, 1, 4, 1, PAL['wood_dark'])
    m.emit(-24, 0, -10, 48, 1, 3, G, 1.2); m.light(0, 30, 12, G, 1.2, 8.)


@recipe('finish_arch', group='Parcours et plateformes', label="Arche d'arrivée", kind='structure')
def finish_arch(m, seed=0):
    for sx in (-1, 1): m.box(sx * 30 - 3, 0, -4, 6, 52, 8, PAL['stone_dark']); m.box(sx * 30 - 5, 0, -6, 10, 4, 12, PAL['stone'])
    m.box(-36, 50, -4, 72, 6, 8, PAL['stone']); m.box(-34, 56, -4, 68, 2, 8, PAL['stone_dark'])
    for r in range(2):
        for c in range(8): m.box(-32 + c * 8, 44 + r * 3, 4, 8, 3, 1, PAL['white'] if (r + c) % 2 == 0 else PAL['black'], emis=.5)
    for sx in (-1, 1): m.box(sx * 22 - 4, 28, 4, 8, 14, 1, (230, 190, 60)); m.box(sx * 22 - .5, 42, 4, 1, 4, 1, PAL['wood_dark'])
    m.emit(-24, 0, -10, 48, 1, 3, (255, 224, 130), 1.2); m.light(0, 30, 12, (255, 224, 130), 1.2, 8.)
