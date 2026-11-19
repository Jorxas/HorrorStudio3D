"""Éléments « craft » : objets (outils, armes, mobilier, atelier, éclairage, magie, coffres), dessinés ici dans le style du studio (voir craft.py).

Chaque recette écrit ses propres boîtes (aucune texture ni aucun modèle d'un jeu existant). Unité d'écriture : le voxel = 1/16 m. Les outils et les armes sont posés À PLAT sur le sol
(leur forme se lit du dessus, comme sur un établi) ; le mobilier et les objets de décor sont debout. Les flammes, braises, vitres de lanterne et runes sont émissives et posent une lumière.
"""
import math
from .craft import recipe, Model, PAL

STEEL = (206, 210, 220); STEEL_D = (128, 132, 144); LEATHER = (96, 62, 40); LEATHER_L = (132, 92, 58)
FLAME = (255, 168, 60); FLAME2 = (255, 224, 130); EMBER = (232, 92, 24); RUST = (150, 112, 92)
PARCH = (222, 208, 170); BOOK = [(120, 36, 36), (36, 70, 110), (46, 96, 56), (150, 110, 40)]


def _seg(m, x0, z0, x1, z1, y, h, t, color, jitter=0., emis=0.):
    """une barre mince de (x0, z0) à (x1, z1), à la hauteur y : le long d'un segment quelconque (étoile de rituel, croisillons...)"""
    dx, dz = x1 - x0, z1 - z0; L = math.hypot(dx, dz); cx, cz = (x0 + x1) / 2., (z0 + z1) / 2.
    m.box(cx - L / 2., y, cz - t / 2., L, h, t, color, jitter=jitter, emis=emis, ry=math.atan2(-dz, dx))


def _fit(m, mx):
    """ramène le plus grand côté du modèle à `mx` mètres (un outil n'est pas plus grand qu'un homme) : boîtes, lumières ; les détails fins restent proportionnels"""
    if not m.boxes: return
    lo = [min(b[k] - b[s] / 2 for b in m.boxes) for k, s in (('x', 'w'), ('y', 'h'), ('z', 'd'))]; hi = [max(b[k] + b[s] / 2 for b in m.boxes) for k, s in (('x', 'w'), ('y', 'h'), ('z', 'd'))]
    big = max(hi[i] - lo[i] for i in range(3))
    if big <= mx: return
    k = mx / big
    for b in m.boxes:
        for c in ('x', 'y', 'z', 'w', 'h', 'd'): b[c] *= k
    for l in m.lights: l['at'] = [v * k for v in l['at']]; l['dist'] *= max(.6, k)


def fit(mx):
    def deco(fn):
        def run(m, seed=0): fn(m, seed); _fit(m, mx)
        run.__name__ = fn.__name__; return run
    return deco


# =================================================================================================== Outils et armes
def _stump(m, r=8):
    """souche de bois sur laquelle un outil est planté : écorce autour, cernes sur le dessus"""
    m.box(-r, 0, -r + 2, 2 * r, 6, 2 * r - 4, PAL['bark']); m.box(-r + 2, 0, -r, 2 * r - 4, 6, 2 * r, PAL['bark'])
    m.box(-r + 2, 6, -r + 3, 2 * r - 4, 1, 2 * r - 6, PAL['wood_light']); m.box(-3, 6, -3, 6, 1, 6, PAL['wood'])


def _grip(m, y0, y1, w=2):
    m.box(-w / 2., y0, -1.5, w, y1 - y0, 3, PAL['wood'])


@recipe('pickaxe', group='Outils et armes', label='Pioche', kind='item')
@fit(1.3)
def pickaxe(m, seed=0):
    _stump(m); _grip(m, 6, 36); m.box(-1.5, 6, -2, 3, 8, 4, LEATHER)
    m.box(-2, 33, -2, 4, 4, 4, PAL['iron_dark']); m.box(-10, 34, -1.5, 20, 3, 3, PAL['iron'])
    for s in (-1, 1):
        x = 10 if s > 0 else -13
        m.box(x, 31, -1.5, 3, 4, 3, PAL['iron']); m.box(x + (1 if s > 0 else 0), 28, -1.5, 2, 3, 3, STEEL)


@recipe('axe', group='Outils et armes', label='Hache', kind='item')
@fit(1.3)
def axe(m, seed=0):
    _stump(m); _grip(m, 6, 38); m.box(-1.5, 6, -2, 3, 8, 4, LEATHER)
    m.box(-2, 26, -2, 4, 8, 4, PAL['iron_dark']); m.box(2, 24, -1.5, 8, 12, 3, PAL['iron']); m.box(10, 22, -1.5, 3, 16, 3, STEEL); m.box(-6, 28, -1.5, 4, 5, 3, PAL['iron_dark'])


@recipe('shovel', group='Outils et armes', label='Pelle', kind='item')
@fit(1.4)
def shovel(m, seed=0):
    _grip(m, 8, 38); m.box(-4, 36, -1.5, 8, 2, 3, PAL['wood']); m.box(-4, 34, -1.5, 2, 4, 3, PAL['wood']); m.box(2, 34, -1.5, 2, 4, 3, PAL['wood'])
    m.box(-1.5, 8, -2, 3, 3, 4, PAL['iron_dark']); m.box(-4, 2, -1.5, 8, 7, 3, PAL['iron']); m.box(-3, 0, -1.5, 6, 2, 3, PAL['iron']); m.box(-2, 0, -1.5, 4, 1, 3, STEEL)
    m.box(-9, 0, -7, 18, 1, 14, PAL['dirt']); m.box(-6, 1, -5, 4, 2, 4, PAL['dirt'])


@recipe('hoe', group='Outils et armes', label='Houe', kind='item')
@fit(1.4)
def hoe(m, seed=0):
    _stump(m); _grip(m, 6, 40); m.box(-1.5, 6, -2, 3, 8, 4, LEATHER)
    m.box(-2, 36, -2, 4, 3, 4, PAL['iron_dark']); m.box(1, 36, -1.5, 11, 3, 3, PAL['iron']); m.box(9, 28, -1.5, 3, 9, 3, PAL['iron']); m.box(9, 25, -1.5, 3, 3, 3, STEEL)


@recipe('sword', group='Outils et armes', label='Épée', kind='item', variants=3)
@fit(1.1)
def sword(m, seed=0):
    k = seed % 3
    blade = [STEEL, STEEL, RUST][k]; guard = [PAL['iron_dark'], PAL['gold'], (92, 70, 60)][k]; bw = [4, 4, 6][k]; hl = [(232, 236, 244), (240, 220, 150), (122, 92, 78)][k]
    m.box(-9, 0, -9, 18, 6, 18, PAL['stone']); m.box(-7, 6, -7, 14, 1, 14, PAL['stone_light'])     # pierre dans laquelle la lame est plantée
    m.box(-bw / 2., 7, -1, bw, 22, 2, blade); m.box(-1, 7, -1.5, 2, 21, 3, hl)                                 # lame (arête claire au milieu)
    m.box(-8 if k != 2 else -9, 29, -1.5, 16 if k != 2 else 18, 3, 3, guard)                                    # garde
    m.box(-1.5, 32, -1.5, 3, 7, 3, LEATHER); m.box(-2, 39, -2, 4, 3, 4, guard)                                  # poignée et pommeau
    if k == 1: m.box(-1, 40, 2, 2, 1, 1, PAL['ruby'])
    if k == 2: m.box(-bw / 2., 14, -1.5, 2, 3, 3, (110, 78, 62)); m.box(1, 22, -1.5, 2, 2, 3, (110, 78, 62))               # écailles de rouille


@recipe('bow', group='Outils et armes', label='Arc', kind='item')
@fit(1.3)
def bow(m, seed=0):
    _stump(m, 7); oy = 8
    m.box(2, oy + 12, -2, 4, 7, 4, LEATHER)
    for i in range(5):                                                       # deux branches symétriques qui s'écartent du poignet
        x = 4 - i if i < 4 else 0
        m.box(x, oy + 19 + 3 * i, -1.5, 3, 3, 3, PAL['wood']); m.box(x, oy + 12 - 3 * (i + 1), -1.5, 3, 3, 3, PAL['wood'])
    m.box(-1, oy - 3, -1.5, 3, 2, 3, PAL['wood_dark']); m.box(-1, oy + 34, -1.5, 3, 2, 3, PAL['wood_dark'])
    m.box(-2, oy - 2, -0.5, 1, 36, 1, (226, 216, 180))                       # la corde
    m.box(9, 8, 2, 2, 22, 2, PAL['wood_light']); m.box(8, 28, 2, 4, 4, 2, STEEL); m.box(8, 8, 2, 4, 3, 2, PAL['cloth_red'])   # une flèche plantée dans la souche


@recipe('crossbow', group='Outils et armes', label='Arbalète', kind='item')
@fit(1.0)
def crossbow(m, seed=0):
    m.box(-22, 0, -2, 44, 28, 2, PAL['wood_dark']); m.box(-22, 0, -3, 44, 2, 1, PAL['wood']); m.box(-22, 26, -3, 44, 2, 1, PAL['wood'])     # plaque de bois
    m.box(-16, 10, 0, 30, 4, 3, PAL['wood']); m.box(-16, 10, 0, 7, 6, 3, PAL['wood_dark']); m.box(-4, 14, 1, 20, 1, 1, PAL['wood_dark'])
    m.box(10, 4, 0, 3, 16, 3, PAL['wood_dark']); m.box(8, 3, 0, 3, 3, 3, PAL['wood_dark']); m.box(8, 18, 0, 3, 3, 3, PAL['wood_dark'])
    m.box(9, 4, 2, 1, 14, 1, (214, 204, 168)); m.box(14, 9, 0, 3, 6, 3, PAL['iron_dark']); m.box(-5, 6, 0, 2, 6, 3, PAL['iron_dark'])
    m.box(-6, 15, 1, 20, 1, 1, STEEL); m.box(14, 15, 1, 2, 1, 1, STEEL)


@recipe('shield', group='Outils et armes', label='Bouclier', kind='item', variants=2)
@fit(1.0)
def shield(m, seed=0):
    k = seed % 2; base = [PAL['cloth_blue'], PAL['cloth_red']][k]; mark = [PAL['white'], PAL['gold']][k]
    m.box(-6, 0, -5, 12, 2, 10, PAL['wood_dark']); m.box(-1, 2, -1, 2, 6, 2, PAL['wood_dark'])
    rows = [(26, 4, 20), (22, 4, 20), (18, 4, 18), (14, 4, 16), (10, 4, 12), (7, 3, 8), (5, 2, 4)]
    for y, h, w in rows:
        m.box(-w / 2. - 1, y, -1, w + 2, h, 3, PAL['iron_dark']); m.box(-w / 2. + 1, y, 1, w - 2, h, 2, base)
    if k == 0: m.box(-2, 8, 3, 4, 20, 1, mark); m.box(-7, 18, 3, 14, 4, 1, mark)
    else: m.box(-9, 20, 3, 18, 3, 1, mark); m.box(-1, 7, 3, 2, 14, 1, mark)
    m.box(-3, 15, 3, 6, 6, 2, PAL['iron']); m.box(-1, 17, 5, 2, 2, 1, STEEL)


@recipe('helmet', group='Outils et armes', label='Casque', kind='item')
@fit(0.6)
def helmet(m, seed=0):
    m.box(-6, 0, -5, 12, 2, 10, PAL['wood_dark']); m.box(-1, 2, -1, 2, 5, 2, PAL['wood_dark'])
    m.box(-6, 7, -6, 12, 4, 12, PAL['iron']); m.box(-5, 11, -5, 10, 4, 10, PAL['iron']); m.box(-4, 15, -4, 8, 2, 8, STEEL)
    m.box(-1, 17, -5, 2, 3, 10, PAL['cloth_red']); m.box(-5, 8, 6, 10, 3, 1, PAL['black']); m.box(-1, 7, 6, 2, 6, 2, PAL['iron_dark'])
    m.box(-7, 7, -4, 1, 5, 8, PAL['iron_dark']); m.box(6, 7, -4, 1, 5, 8, PAL['iron_dark'])


def _plate(m, y0):
    m.box(-6, y0, -3, 12, 12, 6, PAL['iron']); m.box(-8, y0 + 10, -3, 4, 3, 6, PAL['iron_dark']); m.box(4, y0 + 10, -3, 4, 3, 6, PAL['iron_dark'])
    m.box(-6, y0, -3.5, 12, 2, 7, LEATHER); m.box(-1, y0, 3.5, 2, 2, 1, PAL['gold']); m.box(-4, y0 + 4, 3, 8, 6, 1, STEEL)


@recipe('breastplate', group='Outils et armes', label='Plastron', kind='item')
@fit(0.9)
def breastplate(m, seed=0):
    m.box(-6, 0, -4, 12, 2, 8, PAL['wood_dark']); m.box(-1, 2, -1, 2, 14, 2, PAL['wood_dark']); m.box(-9, 16, -1, 18, 2, 2, PAL['wood']); _plate(m, 8)


@recipe('armor_stand', group='Outils et armes', label="Mannequin d'armure", kind='item')
@fit(2.0)
def armor_stand(m, seed=0):
    m.box(-7, 0, -5, 14, 2, 10, PAL['wood_dark'])
    for s in (-1, 1): m.box(s * 3 - 1.5, 2, -2, 3, 12, 4, PAL['iron_dark']); m.box(s * 3 - 2, 2, -3, 4, 3, 6, PAL['iron'])
    _plate(m, 14); m.box(-9, 22, -2, 3, 2, 4, PAL['iron_dark']); m.box(6, 22, -2, 3, 2, 4, PAL['iron_dark'])
    for s in (-1, 1): m.box(s * 8 - 2, 14, -2, 4, 10, 4, PAL['iron']); m.box(s * 8 - 2, 12, -2, 4, 2, 4, PAL['iron_dark'])
    m.box(-4, 26, -4, 8, 3, 8, PAL['iron']); m.box(-5, 29, -5, 10, 5, 10, PAL['iron']); m.box(-4, 34, -4, 8, 2, 8, STEEL); m.box(-1, 36, -5, 2, 3, 10, PAL['cloth_red'])
    m.box(-4, 30, 5, 8, 2, 1, PAL['black'])


@recipe('weapon_rack', group='Outils et armes', label='Râtelier à armes', kind='item')
@fit(1.8)
def weapon_rack(m, seed=0):
    m.box(-18, 0, -3, 3, 30, 4, PAL['wood_dark']); m.box(15, 0, -3, 3, 30, 4, PAL['wood_dark'])
    m.box(-18, 8, -2, 36, 3, 3, PAL['wood']); m.box(-18, 20, -2, 36, 3, 3, PAL['wood']); m.box(-20, 0, -5, 40, 2, 8, PAL['wood_dark'])
    for i, x in enumerate((-12, -5, 3, 10)):
        m.box(x - 1, 9, 1, 2, 22, 2, [STEEL, PAL['iron'], STEEL, RUST][i]); m.box(x - 3, 9, 1, 6, 2, 2, PAL['gold'] if i % 2 else PAL['iron_dark']); m.box(x - 1, 6, 1, 2, 3, 2, LEATHER)
    m.box(-1, 12, 3, 2, 14, 1, PAL['wood_light']); m.box(-3, 24, 1, 6, 4, 2, PAL['cloth_red'])


@recipe('wolf_trap', group='Outils et armes', label='Piège à loups', kind='item')
@fit(1.2)
def wolf_trap(m, seed=0):
    n = 18
    for i in range(n):                                    # mâchoires ouvertes à plat : un anneau de fer garni de dents tournées vers le haut
        a = 2 * math.pi * i / n; c, s = math.cos(a), math.sin(a)
        m.box(c * 10 - 2, 0, s * 10 - 2, 4, 2, 4, PAL['iron'])
        if not (abs(s) < .25 and c > 0):
            m.box(c * 7.5 - .5, 2, s * 7.5 - .5, 1, 5, 1, STEEL); m.box(c * 7.5 - 1.5, 2, s * 7.5 - 1.5, 3, 1, 3, PAL['iron_dark'])
    m.box(-4, 0, -4, 8, 2, 8, PAL['iron_dark']); m.box(-2, 2, -2, 4, 1, 4, PAL['iron']); m.box(-12, 0, -1, 3, 4, 2, PAL['iron_dark']); m.box(9, 0, -1, 3, 4, 2, PAL['iron_dark'])
    for i in range(6): m.box(12 + i * 3, 0, (i % 2) * 2 - 1, 3, 2, 2, PAL['iron_dark'])
    m.box(30, 0, -2, 4, 12, 4, PAL['wood_dark'])


# =================================================================================================== Mobilier
@recipe('bookshelf', group='Mobilier', label='Étagère à livres', kind='item')
@fit(2.2)
def bookshelf(m, seed=0):
    m.box(-14, 0, -4, 28, 40, 2, PAL['wood_dark']); m.box(-14, 0, -4, 3, 40, 8, PAL['wood']); m.box(11, 0, -4, 3, 40, 8, PAL['wood']); m.box(-14, 38, -4, 28, 3, 9, PAL['wood'])
    for sh in range(5):
        y = 1 + sh * 8; m.box(-11, y, -4, 22, 1, 7, PAL['wood'])
        x = -10; i = sh * 2 + seed
        while x < 9:
            w = 4 + (i * 5 % 4); w = min(w, 9 - x); h = 5 + (i * 3 % 3)
            if (i + sh) % 5 == 3: x += 3; i += 1; continue
            m.box(x, y + 1, -2, w, h, 5, BOOK[(i * 2) % 4]); x += w; i += 1
    m.box(-14, 0, -4, 28, 2, 8, PAL['wood_dark'])


@recipe('wooden_bed', group='Mobilier', label='Lit en bois', kind='item')
@fit(2.1)
def wooden_bed(m, seed=0):
    m.box(-11, 0, -17, 22, 6, 34, PAL['wood_dark'])
    for sx in (-1, 1):
        for z in (-17, 14): m.box(sx * 9 - 2, 0, z, 4, 9, 3, PAL['wood'])
    m.box(-11, 6, -17, 22, 14, 3, PAL['wood']); m.box(-11, 6, 14, 22, 8, 3, PAL['wood'])
    m.box(-10, 6, -14, 20, 5, 28, PAL['cloth']); m.box(-10, 11, -2, 20, 2, 16, PAL['cloth_red']); m.box(-9, 11, -13, 18, 3, 7, PAL['white'])
    m.box(-10, 13, -2, 20, 1, 3, PAL['cloth_yellow'])


@recipe('camp_bed', group='Mobilier', label='Lit de camp', kind='item')
@fit(2.0)
def camp_bed(m, seed=0):
    m.box(-9, 9, -17, 18, 1, 34, PAL['cloth'])
    for sx in (-1, 1): m.box(sx * 9 - (1 if sx < 0 else 0), 8, -17, 1, 2, 34, PAL['wood'])
    for z in (-14, 12):
        for sx in (-1, 1): m.box(sx * 8 - 1, 0, z, 2, 9, 2, PAL['wood_dark']); m.box(sx * 8 - 1, 0, z + (4 if z < 0 else -4), 2, 9, 2, PAL['wood_dark'])
        m.box(-9, 4, z, 18, 1, 2, PAL['wood'])
    m.box(-8, 10, -15, 16, 3, 9, PAL['white']); m.box(-9, 10, -3, 18, 2, 16, PAL['cloth_green'])


@recipe('cradle', group='Mobilier', label='Berceau', kind='item')
@fit(1.1)
def cradle(m, seed=0):
    for z in (-12, 10): m.box(-9, 0, z, 18, 2, 2, PAL['wood_dark']); m.box(-11, 1, z, 3, 3, 2, PAL['wood_dark']); m.box(8, 1, z, 3, 3, 2, PAL['wood_dark'])
    m.box(-9, 3, -12, 18, 2, 24, PAL['wood'])
    for sx in (-1, 1): m.box(sx * 9 - (2 if sx < 0 else 0), 5, -12, 2, 9, 24, PAL['wood'])
    m.box(-9, 5, -12, 18, 11, 2, PAL['wood']); m.box(-9, 5, 10, 18, 7, 2, PAL['wood'])
    m.box(-7, 5, -10, 14, 4, 20, PAL['white']); m.box(-7, 9, -2, 14, 2, 11, PAL['cloth_blue'])
    for x in range(-8, 8, 4): m.box(x, 14, -12, 1, 6, 1, PAL['wood_light'])


@recipe('grandfather_clock', group='Mobilier', label='Horloge comtoise', kind='item')
@fit(2.2)
def grandfather_clock(m, seed=0):
    m.box(-7, 0, -5, 14, 5, 10, PAL['wood_dark']); m.box(-6, 5, -4, 12, 24, 8, PAL['wood']); m.box(-8, 29, -5, 16, 3, 10, PAL['wood_dark'])
    m.box(-7, 32, -4, 14, 12, 8, PAL['wood']); m.box(-8, 44, -5, 16, 3, 10, PAL['wood_dark']); m.box(-5, 47, -3, 10, 3, 6, PAL['wood_dark']); m.box(-1, 50, -1, 2, 2, 2, PAL['gold'])
    m.box(-5, 33, 4, 10, 9, 1, PAL['white']); m.box(-0.5, 37, 5, 1, 4, 1, PAL['black']); m.box(-0.5, 37, 5, 3, 1, 1, PAL['black'])
    m.box(-3, 8, 4, 6, 18, 1, PAL['black']); m.box(-1, 10, 5, 2, 12, 1, PAL['gold']); m.box(-3, 8, 5, 6, 3, 1, PAL['gold'])


@recipe('standing_mirror', group='Mobilier', label='Miroir sur pied', kind='item')
@fit(1.9)
def standing_mirror(m, seed=0):
    m.box(-10, 0, -4, 3, 3, 8, PAL['wood_dark']); m.box(7, 0, -4, 3, 3, 8, PAL['wood_dark'])
    m.box(-9, 3, -2, 18, 34, 3, PAL['wood']); m.box(-8, 4, 1, 16, 32, 1, (176, 200, 212)); m.box(-5, 8, 2, 3, 20, 1, (214, 232, 240))
    m.box(-9, 36, -2, 18, 3, 3, PAL['gold']); m.box(-10, 3, 0, 1, 34, 1, PAL['gold']); m.box(9, 3, 0, 1, 34, 1, PAL['gold'])


@recipe('ladder', group='Mobilier', label='Échelle', kind='item')
@fit(2.4)
def ladder(m, seed=0):
    for sx in (-1, 1): m.box(sx * 7 - 1, 0, -1, 2, 44, 3, PAL['wood'])
    for y in range(4, 42, 5): m.box(-6, y, -0.5, 12, 2, 2, PAL['wood_light'])
    for sx in (-1, 1): m.box(sx * 7 - 1.5, 0, -1.5, 3, 2, 4, PAL['wood_dark'])


@recipe('signpost', group='Mobilier', label='Poteau indicateur', kind='item', variants=2)
def signpost(m, seed=0):
    m.box(-2, 0, -2, 4, 40, 4, PAL['wood_dark']); m.box(-3, 38, -3, 6, 2, 6, PAL['wood'])
    for i, (y, side) in enumerate([(30, 1), (22, -1)] if seed % 2 == 0 else [(30, -1), (22, 1), (14, 1)]):
        x0 = 2 if side > 0 else -16
        m.box(x0, y, 2, 14, 6, 2, PAL['plank']); m.box(x0 + (14 if side > 0 else -2), y + 1, 2, 2, 4, 2, PAL['plank']); m.box(x0 + 2, y + 3, 4, 9, 1, 1, PAL['wood_dark'])


@recipe('fence', group='Mobilier', label='Barrière de bois', kind='item')
def fence(m, seed=0):
    for x in (-16, 0, 16): m.box(x - 2, 0, -2, 4, 20, 4, PAL['wood_dark']); m.box(x - 3, 20, -3, 6, 2, 6, PAL['wood'])
    for y in (6, 13): m.box(-16, y, -1, 32, 3, 2, PAL['plank'])


@recipe('iron_grate', group='Mobilier', label='Grille de fer', kind='item')
def iron_grate(m, seed=0):
    m.box(-14, 0, -2, 28, 3, 4, PAL['iron_dark']); m.box(-14, 31, -2, 28, 3, 4, PAL['iron_dark']); m.box(-14, 0, -2, 3, 34, 4, PAL['iron_dark']); m.box(11, 0, -2, 3, 34, 4, PAL['iron_dark'])
    for x in range(-9, 10, 4): m.box(x - .5, 3, -1, 1.5, 28, 2, PAL['iron'])
    m.box(-11, 14, -1, 22, 2, 2, PAL['iron_dark']); m.box(-3, 12, 1, 6, 6, 2, PAL['iron_dark']); m.box(-1, 14, 3, 2, 2, 1, PAL['gold'])


@recipe('cage', group='Mobilier', label='Cage', kind='item')
@fit(1.8)
def cage(m, seed=0):
    m.box(-12, 0, -12, 24, 3, 24, PAL['iron_dark']); m.box(-12, 25, -12, 24, 3, 24, PAL['iron_dark'])
    for x in range(-11, 12, 4):
        for z in (-11, 10): m.box(x, 3, z, 2, 22, 2, PAL['iron'])
    for z in range(-7, 8, 4):
        for x in (-11, 10): m.box(x, 3, z, 2, 22, 2, PAL['iron'])
    m.box(-2, 28, -2, 4, 6, 4, PAL['iron_dark']); m.box(-4, 34, -1, 8, 2, 2, PAL['iron_dark']); m.box(-3, 12, 11, 6, 4, 2, PAL['iron_dark']); m.box(-1, 13, 13, 2, 2, 1, PAL['gold'])
    m.box(-4, 3, -4, 8, 2, 8, PAL['bone']); m.box(-3, 5, -3, 3, 3, 3, PAL['bone'])


@recipe('hitching_post', group='Mobilier', label='Poteau à anneau', kind='item')
@fit(1.9)
def hitching_post(m, seed=0):
    m.box(-3, 0, -3, 6, 30, 6, PAL['wood_dark']); m.box(-4, 28, -4, 8, 3, 8, PAL['wood']); m.box(-4, 0, -4, 8, 2, 8, PAL['stone_dark'])
    m.box(2, 18, -1, 4, 6, 2, PAL['iron_dark']); m.box(5, 16, -1, 3, 10, 2, PAL['iron_dark']); m.box(6, 18, -.5, 1, 6, 1, PAL['coal'])
    m.box(-3, 12, 3, 6, 2, 2, PAL['rope']); m.box(-3, 8, 3, 2, 6, 2, PAL['rope'])


@recipe('bell', group='Mobilier', label='Cloche', kind='item')
@fit(1.9)
def bell(m, seed=0):
    for sx in (-1, 1): m.box(sx * 14 - 1.5, 0, -2, 3, 38, 4, PAL['wood_dark']); m.box(sx * 12 - 1.5, 0, -4, 3, 3, 8, PAL['wood_dark'])
    m.box(-16, 36, -2, 32, 3, 4, PAL['wood']); m.box(-1, 34, -1, 2, 2, 2, PAL['iron_dark']); m.box(-2, 32, -2, 4, 2, 4, PAL['iron_dark'])
    bronze = (150, 104, 52)
    for i, (y, w, h) in enumerate([(28, 8, 4), (24, 10, 4), (20, 12, 4), (16, 14, 4), (12, 18, 4)]):          # corps évasé, plus étroit en haut
        m.box(-w / 2., y, -w / 2., w, h, w, bronze)
    m.box(-10, 10, -10, 20, 2, 20, PAL['gold']); m.box(-4, 26, 3.5, 8, 6, 1, (112, 150, 120))            # bord doré, trace de vert-de-gris
    m.box(-1.5, 6, -1.5, 3, 5, 3, PAL['iron_dark']); m.box(-2.5, 4, -2.5, 5, 3, 5, PAL['iron'])                      # battant


# =================================================================================================== Cuisine et atelier
@recipe('anvil', group='Cuisine et atelier', label='Enclume', kind='item')
@fit(1.0)
def anvil(m, seed=0):
    m.box(-10, 0, -10, 20, 10, 20, PAL['bark']); m.box(-8, 10, -8, 16, 1, 16, PAL['wood_light']); oy = 11
    m.box(-7, oy, -4, 14, 3, 8, PAL['iron_dark']); m.box(-4, oy + 3, -3, 8, 5, 6, PAL['iron'])
    m.box(-9, oy + 8, -4, 18, 4, 8, PAL['iron']); m.box(9, oy + 9, -3, 5, 3, 6, PAL['iron']); m.box(14, oy + 9, -2, 4, 2, 4, PAL['iron']); m.box(18, oy + 10, -1, 3, 1, 2, PAL['iron'])
    m.box(-8, oy + 12, -3, 16, 1, 6, STEEL); m.box(-1, oy + 12, -1, 2, 1, 2, PAL['iron_dark'])
    m.box(-14, 10, 1, 6, 2, 2, PAL['wood']); m.box(-9, 10, 0, 3, 4, 4, PAL['iron_dark'])          # marteau posé sur la souche


@recipe('forge', group='Cuisine et atelier', label='Forge', kind='item')
@fit(2.4)
def forge(m, seed=0):
    m.box(-14, 0, -10, 28, 24, 20, PAL['stone']); m.box(-15, 0, -11, 30, 3, 22, PAL['stone_dark']); m.box(-15, 22, -11, 30, 3, 22, PAL['stone_dark'])
    m.box(-6, 25, -6, 12, 20, 12, PAL['stone_dark']); m.box(-7, 43, -7, 14, 3, 14, PAL['stone'])
    m.box(-8, 4, 10, 16, 12, 1, PAL['coal']); m.box(-9, 3, 10, 1, 14, 2, PAL['stone_light']); m.box(8, 3, 10, 1, 14, 2, PAL['stone_light']); m.box(-9, 16, 10, 18, 2, 2, PAL['stone_light'])
    m.emit(-7, 4, 9, 14, 3, 2, EMBER, 1.6); m.emit(-5, 7, 9, 10, 5, 2, FLAME, 1.8); m.emit(-3, 12, 9, 6, 3, 2, FLAME2, 2.0); m.light(0, 9, 14, FLAME, 1.8, 5.)
    m.box(15, 4, -4, 8, 2, 8, PAL['wood_dark']); m.box(15, 10, -4, 8, 2, 8, PAL['wood']); m.box(15, 6, -3, 8, 4, 6, LEATHER); m.box(23, 7, -1, 3, 2, 2, PAL['iron_dark'])


@recipe('workbench', group='Cuisine et atelier', label='Établi', kind='item')
@fit(1.6)
def workbench(m, seed=0):
    m.box(-18, 16, -8, 36, 3, 16, PAL['plank'])
    for sx in (-1, 1):
        for z in (-7, 4): m.box(sx * 15 - 1.5, 0, z, 3, 16, 3, PAL['wood_dark'])
    m.box(-16, 5, -7, 32, 2, 14, PAL['wood']); m.box(-16, 9, -7, 32, 1, 1, PAL['wood_dark'])
    m.box(10, 19, 3, 4, 6, 4, PAL['iron_dark']); m.box(14, 21, 4, 6, 2, 2, PAL['iron']); m.box(19, 19, 3, 2, 6, 4, PAL['iron_dark'])             # étau
    m.box(-14, 19, 0, 8, 2, 2, PAL['wood']); m.box(-7, 19, -1, 3, 4, 4, PAL['iron'])                                                          # marteau
    m.box(-4, 19, -5, 10, 1, 4, PAL['wood_light']); m.box(-3, 20, -4, 7, 1, 1, PAL['wood_dark'])                                              # planche et trait de scie
    m.box(-16, 19, 4, 1, 3, 1, STEEL); m.box(-14, 19, 4, 1, 3, 1, STEEL); m.box(-12, 19, 4, 1, 2, 1, STEEL); m.box(-17, 7, 0, 5, 3, 3, PAL['iron_dark'])


@recipe('cooking_table', group='Cuisine et atelier', label='Table de cuisson', kind='item')
@fit(1.7)
def cooking_table(m, seed=0):
    m.box(-18, 14, -8, 36, 3, 16, PAL['plank'])
    for sx in (-1, 1):
        for z in (-7, 4): m.box(sx * 15 - 1.5, 0, z, 3, 14, 3, PAL['wood_dark'])
    m.box(-14, 17, -5, 11, 7, 10, PAL['coal']); m.box(-15, 23, -6, 13, 1, 12, PAL['iron_dark']); m.box(-13, 24, -4, 9, 1, 8, (160, 76, 34)); m.box(-17, 19, -1, 2, 3, 2, PAL['iron_dark'])
    m.box(3, 17, -6, 12, 1, 12, PAL['coal']); m.box(15, 17, -1, 8, 1, 2, PAL['coal']); m.box(5, 18, -3, 4, 1, 4, (214, 170, 70))
    m.box(-2, 17, 3, 7, 1, 4, PAL['wood_light']); m.box(-1, 18, 4, 5, 1, 1, STEEL); m.box(-1, 18, -7, 6, 4, 4, (196, 146, 74)); m.box(-1, 22, -6, 4, 1, 2, (160, 110, 56))
    m.box(-16, 17, 4, 3, 3, 3, PAL['cloth_red']); m.box(-20, 32, -1, 40, 1, 2, PAL['iron_dark']); m.box(-12, 24, -1, 1, 8, 1, PAL['iron_dark'])


@recipe('cauldron', group='Cuisine et atelier', label='Chaudron', kind='item')
@fit(1.1)
def cauldron(m, seed=0):
    for a in (0.5, 2.6, 4.7): m.box(math.cos(a) * 8 - 2, 0, math.sin(a) * 8 - 2, 4, 5, 4, PAL['iron_dark'])
    for (y, w, h) in [(4, 14, 3), (7, 18, 5), (12, 21, 5), (17, 20, 3)]: m.box(-w / 2., y, -w / 2., w, h, w, PAL['coal'])
    m.box(-11, 19, -11, 22, 2, 22, PAL['iron_dark']); m.box(-9, 19, -9, 18, 2, 18, (96, 220, 120), emis=1.5)
    for (x, z, s) in [(-4, -2, 2), (3, 4, 3), (-2, 5, 2), (5, -4, 2)]: m.emit(x, 21, z, s, s, s, (170, 255, 170), 1.8)
    m.box(-13, 14, -1, 2, 8, 2, PAL['iron_dark']); m.box(11, 14, -1, 2, 8, 2, PAL['iron_dark']); m.box(-12, 21, -1, 24, 2, 2, PAL['iron_dark'])
    m.light(0, 24, 0, (110, 255, 140), 1.5, 4.)
    m.box(-12, 0, -1, 24, 3, 2, PAL['bark'], ry=.5); m.box(-12, 0, -1, 24, 3, 2, PAL['bark'], ry=-.5); m.emit(-3, 1, -3, 6, 3, 6, EMBER, 1.3)


@recipe('scale', group='Cuisine et atelier', label='Balance', kind='item')
@fit(1.0)
def scale(m, seed=0):
    gold = (196, 156, 62)
    m.box(-7, 0, -4, 14, 3, 8, PAL['wood_dark']); m.box(-1.5, 3, -1.5, 3, 26, 3, PAL['wood']); m.box(-3, 28, -3, 6, 3, 6, gold)
    m.box(-15, 31, -1, 30, 2, 2, gold); m.box(-1, 33, -1, 2, 2, 2, gold)
    for (x, y) in ((-15, 17), (13, 21)):
        m.box(x - .5, y + 6, -.5, 1, 14, 1, PAL['rope']); m.box(x - 4, y + 4, -4, 9, 2, 8, gold); m.box(x - 5, y + 6, -5, 11, 1, 10, gold)
    m.box(-17, 23, -3, 4, 3, 4, PAL['iron_dark']); m.box(-14, 23, 1, 3, 2, 3, PAL['iron']); m.box(-12, 24, -2, 3, 3, 3, PAL['iron_dark'])


@recipe('minecart', group='Cuisine et atelier', label='Wagonnet sur rails', kind='item')
@fit(2.2)
def minecart(m, seed=0):
    for x in range(-26, 27, 7): m.box(x, 0, -9, 3, 2, 18, PAL['wood_dark'])
    for z in (-7, 5): m.box(-30, 2, z, 60, 2, 2, PAL['iron'])
    m.box(-12, 5, -7, 24, 3, 14, PAL['iron_dark']); m.box(-12, 8, -7, 24, 8, 2, PAL['iron_dark']); m.box(-12, 8, 5, 24, 8, 2, PAL['iron_dark'])
    m.box(-12, 8, -7, 2, 8, 14, PAL['iron_dark']); m.box(10, 8, -7, 2, 8, 14, PAL['iron_dark']); m.box(-13, 15, -8, 26, 2, 2, PAL['iron']); m.box(-13, 15, 6, 26, 2, 2, PAL['iron']); m.box(-13, 15, -8, 2, 2, 16, PAL['iron']); m.box(11, 15, -8, 2, 2, 16, PAL['iron'])
    for (x, z) in ((-8, -8), (6, -8), (-8, 7), (6, 7)): m.box(x, 3, z, 4, 4, 2, PAL['coal'])
    m.box(-9, 8, -5, 18, 8, 10, PAL['gold']); m.box(-7, 16, -4, 14, 3, 8, (236, 196, 80)); m.box(-4, 19, -2, 8, 2, 4, (255, 224, 120))


# =================================================================================================== Éclairage
@recipe('lantern', group='Éclairage', label='Lanterne', kind='item')
@fit(0.5)
def lantern(m, seed=0):
    m.box(-5, 0, -5, 10, 2, 10, PAL['iron_dark']); m.emit(-4, 2, -4, 8, 11, 8, (255, 204, 120), 1.3)
    for sx in (-1, 1):
        for sz in (-1, 1): m.box(sx * 4 - (1 if sx < 0 else 0), 2, sz * 4 - (1 if sz < 0 else 0), 1, 11, 1, PAL['iron_dark'])
    m.box(-5, 13, -5, 10, 2, 10, PAL['iron_dark']); m.box(-4, 15, -4, 8, 2, 8, PAL['iron_dark']); m.box(-2, 17, -2, 4, 2, 4, PAL['iron_dark'])
    m.box(-4, 19, -.5, 1, 4, 1, PAL['iron']); m.box(3, 19, -.5, 1, 4, 1, PAL['iron']); m.box(-4, 23, -.5, 8, 1, 1, PAL['iron']); m.light(0, 8, 0, (255, 200, 110), 1.4, 4.)


@recipe('torch', group='Éclairage', label='Torche', kind='item')
@fit(1.5)
def torch(m, seed=0):
    m.box(-6, 0, -6, 12, 4, 12, PAL['stone']); m.box(-4, 4, -4, 8, 2, 8, PAL['stone_light']); m.box(-1, 4, -1, 2, 20, 2, PAL['wood'])
    m.box(-2.5, 20, -2.5, 5, 6, 5, LEATHER); m.box(-3, 25, -3, 6, 1, 6, PAL['wood_dark'])
    m.emit(-3, 26, -3, 6, 4, 6, FLAME, 1.7); m.emit(-2, 30, -2, 4, 4, 4, FLAME2, 2.0); m.emit(-1, 34, -1, 2, 3, 2, FLAME2, 2.2); m.light(0, 28, 0, FLAME, 2.0, 5.)


@recipe('candelabra', group='Éclairage', label='Chandelier', kind='item')
@fit(1.1)
def candelabra(m, seed=0):
    G = (200, 160, 60)
    m.box(-6, 0, -6, 12, 2, 12, G); m.box(-4, 2, -4, 8, 2, 8, G); m.box(-1, 4, -1, 2, 18, 2, G); m.box(-2, 12, -2, 4, 3, 4, G)
    m.box(-10, 18, -1, 20, 2, 2, G); m.box(-10, 18, -1, 2, 5, 2, G); m.box(8, 18, -1, 2, 5, 2, G)
    for (x, y) in ((-9, 23), (0, 22), (9, 23)):
        m.box(x - 2, y - 1, -2, 4, 1, 4, G); m.box(x - 1, y, -1, 2, 7, 2, PAL['white']); m.emit(x - .5, y + 7, -.5, 1, 2, 1, FLAME2, 2.0)
    m.light(0, 33, 0, FLAME, 1.7, 5.)


@recipe('candles', group='Éclairage', label='Bougies', kind='item', variants=2)
def candles(m, seed=0):
    m.box(-10, 0, -10, 20, 1, 20, PAL['iron_dark'] if seed % 2 == 0 else PAL['clay'])
    pts = [(-5, -3, 10), (3, -4, 7), (0, 3, 12), (-6, 5, 5), (6, 4, 8)][:3 + seed % 2 * 2]
    for (x, z, h) in pts:
        m.box(x - 1.5, 1, z - 1.5, 3, h, 3, (236, 228, 200)); m.box(x - 2, 1, z - 2, 4, 2, 4, (226, 216, 184)); m.box(x - 1.5, 1 + h - 3, z + 1.5, 1, 3, 1, (246, 240, 220))
        m.box(x - .5, 1 + h, z - .5, 1, 1, 1, PAL['black']); m.emit(x - .5, 2 + h, z - .5, 1, 2, 1, FLAME2, 2.0)
    m.light(0, 14, 0, FLAME, 1.2, 3.)


@recipe('oil_lamp', group='Éclairage', label="Lampe à huile", kind='item')
@fit(0.5)
def oil_lamp(m, seed=0):
    m.box(-6, 0, -4, 12, 6, 8, PAL['clay']); m.box(-4, 6, -3, 8, 2, 6, PAL['clay']); m.box(-2, 8, -2, 4, 2, 4, PAL['iron_dark'])
    m.box(6, 3, -1, 5, 2, 2, PAL['clay']); m.box(-9, 1, -1, 3, 5, 2, PAL['clay']); m.box(-9, 5, -1, 5, 1, 2, PAL['clay']); m.box(10, 5, -.5, 2, 1, 1, PAL['black'])
    m.emit(10, 6, -1, 2, 3, 2, FLAME, 1.8); m.emit(10.5, 9, -.5, 1, 2, 1, FLAME2, 2.0); m.light(11, 8, 0, FLAME, 1.4, 3.5)


@recipe('brazier', group='Éclairage', label='Brasero', kind='item')
@fit(1.1)
def brazier(m, seed=0):
    for (sx, sz) in ((-1, -1), (1, -1), (-1, 1), (1, 1)): m.box(sx * 8 - 1.5, 0, sz * 8 - 1.5, 3, 12, 3, PAL['iron_dark'])
    m.box(-9, 11, -9, 18, 2, 18, PAL['iron_dark']); m.box(-12, 13, -12, 24, 3, 3, PAL['iron']); m.box(-12, 13, 9, 24, 3, 3, PAL['iron'])
    m.box(-12, 13, -9, 3, 3, 18, PAL['iron']); m.box(9, 13, -9, 3, 3, 18, PAL['iron'])
    m.emit(-9, 13, -9, 18, 2, 18, EMBER, 1.5); m.emit(-6, 15, -6, 12, 4, 12, FLAME, 1.7); m.emit(-3, 19, -3, 6, 5, 6, FLAME2, 2.0); m.emit(-1, 24, -1, 2, 3, 2, FLAME2, 2.2); m.light(0, 20, 0, FLAME, 2.0, 6.)


@recipe('campfire', group='Éclairage', label='Feu de camp', kind='item')
@fit(1.4)
def campfire(m, seed=0):
    for i in range(9):
        a = 2 * math.pi * i / 9; m.box(math.cos(a) * 14 - 3, 0, math.sin(a) * 14 - 3, 6, 4 + (i % 2), 6, PAL['stone'] if i % 3 else PAL['stone_dark'])
    for r in (.5, -.5, 1.6): m.box(-11, 2, -2, 22, 4, 4, PAL['bark'], ry=r)
    m.emit(-5, 3, -5, 10, 3, 10, EMBER, 1.6); m.emit(-4, 6, -4, 8, 6, 8, FLAME, 1.8); m.emit(-2.5, 12, -2.5, 5, 6, 5, FLAME2, 2.0); m.emit(-1, 18, -1, 2, 4, 2, FLAME2, 2.2); m.light(0, 10, 0, FLAME, 2.2, 6.)


# =================================================================================================== Magie et mystère
@recipe('spellbook_lectern', group='Magie et mystère', label='Grimoire sur pupitre', kind='item')
def spellbook_lectern(m, seed=0):
    m.box(-8, 0, -6, 16, 3, 12, PAL['wood_dark']); m.box(-3, 3, -3, 6, 20, 6, PAL['wood']); m.box(-5, 23, -4, 10, 2, 8, PAL['wood_dark'])
    for i in range(4): m.box(-11, 25 + i * 2, -6 + i * 1.5 - 1, 22, 2, 3, PAL['wood'])         # plateau incliné fait de marches
    m.box(-11, 25, 3, 22, 3, 2, PAL['wood_dark']); m.box(-9, 27, -4, 8, 2, 7, (96, 28, 40)); m.box(1, 27, -4, 8, 2, 7, (96, 28, 40))                  # livre ouvert : couvertures
    m.box(-8, 29, -3, 7, 1, 6, PARCH); m.box(1, 29, -3, 7, 1, 6, PARCH)
    for i in range(3): m.box(-7, 30, -2 + i * 2, 5, 1, 1, (70, 50, 40)); m.box(2, 30, -2 + i * 2, 5, 1, 1, (70, 50, 40))
    m.emit(-3, 30, 0, 2, 1, 2, (120, 220, 255), 2.0); m.emit(3, 30, -1, 2, 1, 2, (255, 200, 90), 2.0); m.light(0, 34, 0, (140, 220, 255), 1.2, 3.)


@recipe('ritual_circle', group='Magie et mystère', label='Cercle de rituel', kind='item')
def ritual_circle(m, seed=0):
    R = (255, 70, 60); n = 24
    for i in range(n):
        a = 2 * math.pi * i / n; m.box(math.cos(a) * 30 - 2.5, 0, math.sin(a) * 30 - 2.5, 5, 1, 5, PAL['stone_dark'] if i % 2 else PAL['stone'])
        m.emit(math.cos(a) * 25 - .5, 1, math.sin(a) * 25 - .5, 1, 1, 1, R, 1.4)
    pts = [(math.cos(2 * math.pi * k / 5 - math.pi / 2) * 22, math.sin(2 * math.pi * k / 5 - math.pi / 2) * 22) for k in range(5)]
    for k in range(5):
        x0, z0 = pts[k]; x1, z1 = pts[(k + 2) % 5]; _seg(m, x0, z0, x1, z1, 1, 1, 1.5, R, emis=1.7)
        m.box(x0 - 2, 0, z0 - 2, 4, 6, 4, PAL['white']); m.emit(x0 - .5, 6, z0 - .5, 1, 2, 1, FLAME2, 2.0)
    m.light(0, 8, 0, (255, 90, 70), 1.6, 8.)


@recipe('altar', group='Magie et mystère', label='Autel', kind='item')
@fit(1.8)
def altar(m, seed=0):
    m.box(-18, 0, -12, 36, 4, 24, PAL['stone_dark']); m.box(-15, 4, -9, 30, 4, 18, PAL['stone'])
    m.box(-12, 8, -6, 24, 12, 12, PAL['stone_light']); m.box(-14, 20, -7, 28, 3, 14, PAL['stone']); m.box(-10, 23, -4, 20, 1, 8, PAL['cloth_red'])
    m.box(-4, 24, -1, 4, 1, 4, PAL['gold']); m.box(-3, 25, 0, 2, 4, 2, PAL['gold']); m.box(-4, 29, -1, 4, 2, 4, PAL['gold'])                              # calice
    m.box(5, 24, -2, 5, 4, 4, PAL['bone']); m.box(6, 24, 1, 3, 1, 1, PAL['black'])                                                         # crâne
    for x in (-11, 11): m.box(x - 1.5, 24, -1.5, 3, 7, 3, (236, 228, 200)); m.emit(x - .5, 31, -.5, 1, 2, 1, FLAME2, 2.0)
    m.emit(-9, 12, 6.5, 18, 1, 1, (255, 70, 60), 1.3); m.emit(-1, 9, 6.5, 2, 9, 1, (255, 70, 60), 1.3); m.light(0, 34, 2, FLAME, 1.4, 5.)


@recipe('gravestone', group='Magie et mystère', label='Tombe', kind='item', variants=3)
def gravestone(m, seed=0):
    k = seed % 3
    m.box(-12, 0, -10, 24, 3, 26, PAL['dirt']); m.box(-10, 3, -6, 20, 2, 20, PAL['mud'])
    if k == 0:
        m.box(-8, 0, -8, 16, 5, 6, PAL['stone_dark']); m.box(-7, 5, -7, 14, 18, 4, PAL['stone']); m.box(-5, 23, -7, 10, 3, 4, PAL['stone']); m.box(-3, 26, -7, 6, 2, 4, PAL['stone'])
        m.box(-3, 17, -3.5, 6, 1, 1, PAL['stone_dark']); m.box(-1, 13, -3.5, 2, 8, 1, PAL['stone_dark'])
    elif k == 1:
        m.box(-8, 0, -8, 16, 4, 6, PAL['stone_dark']); m.box(-3, 4, -7, 6, 22, 4, PAL['stone']); m.box(-9, 16, -7, 18, 5, 4, PAL['stone'])
        m.box(-8, 4, -7, 16, 3, 4, PAL['stone_light'])
    else:
        m.box(-9, 0, -8, 18, 5, 6, PAL['stone_dark']); m.box(-8, 5, -7, 16, 12, 4, PAL['stone']); m.box(-8, 17, -7, 3, 5, 4, PAL['stone']); m.box(5, 17, -7, 3, 3, 4, PAL['stone'])    # pierre ébréchée
        m.box(-4, 11, -3.5, 8, 1, 1, PAL['stone_dark']); m.box(-2, 7, -3.5, 4, 1, 1, PAL['stone_dark'])
    m.box(-7, 5, -3.2, 5, 4, 1, (70, 110, 56)); m.box(4, 3, 4, 7, 2, 6, (56, 96, 50))                                              # mousse


@recipe('grave_cross', group='Magie et mystère', label='Croix de tombe', kind='item')
def grave_cross(m, seed=0):
    m.box(-12, 0, -10, 24, 3, 24, PAL['dirt']); m.box(-9, 3, -4, 18, 2, 14, PAL['mud'])
    m.box(-2, 3, -6, 4, 30, 4, PAL['wood']); m.box(-9, 20, -6, 18, 4, 4, PAL['wood']); m.box(-1, 22, -2, 2, 2, 1, PAL['wood_dark'])
    m.box(-7, 1, 4, 6, 4, 4, PAL['stone_dark']); m.box(4, 3, 5, 5, 6, 1, (56, 96, 50))


@recipe('coffin', group='Magie et mystère', label='Cercueil', kind='item', variants=2)
@fit(2.2)
def coffin(m, seed=0):
    k = seed % 2
    prof = [(-14, 8), (-9, 12), (-4, 14), (4, 14), (9, 12), (14, 8)]          # (z, largeur) : étroit aux pieds, large aux épaules
    for zi in range(0, 10):
        z = -18 + zi * 4; w = [8, 10, 12, 14, 14, 14, 14, 12, 10, 8][zi]
        m.box(-w / 2., 2, z, w, 8, 4, PAL['wood_dark']); m.box(-w / 2. - 1, 2, z, 1, 8, 4, PAL['wood']); m.box(w / 2., 2, z, 1, 8, 4, PAL['wood'])
    m.box(-5, 0, -16, 3, 2, 3, PAL['wood']); m.box(2, 0, -16, 3, 2, 3, PAL['wood']); m.box(-5, 0, 11, 3, 2, 3, PAL['wood']); m.box(2, 0, 11, 3, 2, 3, PAL['wood'])
    if k == 0:                                                                  # fermé, couvercle orné
        m.box(-5, 10, -16, 10, 1, 30, PAL['wood']); m.box(-1, 11, -10, 2, 1, 18, PAL['gold']); m.box(-4, 11, -5, 8, 1, 2, PAL['gold'])
    else:                                                                       # ouvert : intérieur capitonné, couvercle posé contre
        m.box(-5, 8, -14, 10, 1, 26, (96, 28, 40)); m.box(-6, 9, -14, 1, 1, 26, PAL['wood']); m.box(5, 9, -14, 1, 1, 26, PAL['wood'])
        m.box(11, 0, -14, 11, 2, 28, PAL['wood'], ry=.22); m.box(15, 2, -8, 3, 1, 18, PAL['gold'], ry=.22)
        m.box(-4, 9, -12, 8, 2, 8, PAL['white']); m.box(-3, 11, -11, 6, 2, 4, PAL['bone'])


@recipe('sarcophagus', group='Magie et mystère', label='Sarcophage', kind='item')
def sarcophagus(m, seed=0):
    m.box(-12, 0, -22, 24, 12, 44, PAL['stone']); m.box(-13, 0, -23, 26, 3, 46, PAL['stone_dark'])
    m.box(-11, 12, -21, 22, 3, 42, PAL['stone_light']); m.box(-7, 15, -18, 14, 3, 36, PAL['stone'])
    m.box(-4, 18, -17, 8, 5, 6, PAL['gold']); m.box(-5, 18, -11, 10, 2, 8, PAL['gold']); m.box(-3, 18, -3, 6, 2, 16, PAL['gold']); m.box(-3, 20, -15, 6, 1, 1, PAL['black'])
    for z in range(-18, 18, 6): m.box(-12.2, 6, z, 1, 3, 4, PAL['stone_dark'])
    m.emit(-10, 7, 22.5, 20, 1, 1, (90, 210, 220), 1.2)


@recipe('doll', group='Magie et mystère', label='Poupée', kind='item')
def doll(m, seed=0):
    m.box(-5, 0, -5, 4, 3, 5, PAL['cloth_brown']); m.box(1, 0, -5, 4, 3, 5, PAL['cloth_brown']); m.box(-6, 3, -4, 12, 2, 6, PAL['white'])
    m.box(-5, 5, -3, 10, 10, 6, PAL['cloth_blue']); m.box(-6, 4, -4, 12, 3, 8, PAL['cloth_blue']); m.box(-8, 10, -2, 3, 7, 4, PAL['skin']); m.box(5, 10, -2, 3, 5, 4, PAL['skin'])
    m.box(-5, 15, -4, 10, 9, 9, PAL['skin']); m.box(-6, 22, -5, 12, 4, 11, PAL['black']); m.box(-6, 16, -5, 2, 6, 10, PAL['black']); m.box(4, 16, -5, 2, 6, 10, PAL['black'])
    m.box(-3, 19, 5, 2, 2, 1, PAL['black']); m.box(1, 19, 5, 2, 2, 1, PAL['black']); m.box(-2, 16, 5, 4, 1, 1, PAL['cloth_red']); m.box(-3, 18, 5, 1, 1, 1, PAL['white'])


@recipe('music_box', group='Magie et mystère', label='Boîte à musique', kind='item')
def music_box(m, seed=0):
    m.box(-9, 0, -7, 18, 8, 14, PAL['wood']); m.box(-10, 0, -8, 20, 2, 16, PAL['wood_dark']); m.box(-10, 8, -8, 20, 1, 3, PAL['gold']); m.box(-10, 8, 5, 20, 1, 3, PAL['gold'])
    m.box(-9, 9, -8, 18, 13, 2, PAL['wood']); m.box(-8, 10, -6, 16, 11, 1, (176, 200, 212)); m.box(-9, 8, -7, 18, 1, 14, PAL['cloth_red']); m.box(-9, 21, -8, 18, 1, 2, PAL['gold'])
    m.box(-1, 9, -1, 2, 6, 2, PAL['gold']); m.box(-2, 14, -2, 4, 5, 4, PAL['cloth']); m.box(-1.5, 19, -1.5, 3, 3, 3, PAL['skin']); m.box(-4, 15, -1, 8, 1, 1, PAL['cloth'])
    m.box(9, 4, -1, 4, 1, 1, PAL['gold']); m.box(12, 3, -1, 2, 3, 1, PAL['gold'])


@recipe('hourglass', group='Magie et mystère', label='Sablier', kind='item')
def hourglass(m, seed=0):
    m.box(-8, 0, -8, 16, 3, 16, PAL['wood_dark']); m.box(-8, 29, -8, 16, 3, 16, PAL['wood_dark'])
    for (x, z) in ((-7, -7), (5, -7), (-7, 5), (5, 5)): m.box(x, 3, z, 2, 26, 2, PAL['wood'])
    G = (170, 205, 225)
    m.box(-6, 4, -6, 12, 1, 12, G); m.box(-5, 5, -5, 10, 3, 10, G); m.box(-3, 8, -3, 6, 4, 6, G); m.box(-1, 12, -1, 2, 6, 2, G); m.box(-3, 18, -3, 6, 4, 6, G); m.box(-5, 22, -5, 10, 3, 10, G); m.box(-6, 25, -6, 12, 1, 12, G)
    m.box(-4, 5, -4, 8, 2, 8, (232, 200, 120)); m.box(-2, 7, -2, 4, 2, 4, (232, 200, 120)); m.box(-.5, 12, -.5, 1, 6, 1, (232, 200, 120)); m.box(-2, 22, -2, 4, 1, 4, (232, 200, 120))


# =================================================================================================== Coffres et caisses
def _chest(m, body, band, lock, open_=False, gold_inside=False):
    m.box(-12, 0, -8, 24, 12, 16, body)
    for x in (-12, 10): m.box(x, 0, -8.5, 2, 12, 17, band)
    m.box(-12, 4, -8.5, 24, 2, 17, band)
    for dx in (-12, 10): m.box(dx, 12, -8.5, 2, 3, 17, band)
    if not open_:
        m.box(-12, 12, -8, 24, 3, 16, body); m.box(-11, 15, -7, 22, 2, 14, body); m.box(-9, 17, -5, 18, 1, 10, body)
        m.box(-2, 8, 8, 4, 6, 2, lock); m.box(-1, 9, 10, 2, 2, 1, PAL['black'])
    else:
        m.box(-11, 11, -7, 22, 1, 14, (60, 30, 28)); m.box(-12, 12, -8, 24, 12, 3, body); m.box(-11, 22, -8, 22, 3, 3, body); m.box(-12, 12, -9, 24, 2, 1, band)
        m.box(-12, 12, -8, 2, 12, 3, band); m.box(10, 12, -8, 2, 12, 3, band)
        if gold_inside:
            m.box(-9, 11, -5, 18, 3, 10, PAL['gold']); m.box(-6, 14, -3, 12, 2, 6, (255, 220, 110)); m.box(-2, 16, -1, 4, 1, 2, PAL['gem']); m.emit(-4, 15, -2, 3, 1, 3, (255, 226, 130), 1.3); m.light(0, 18, 0, (255, 210, 100), 1.2, 3.)


@recipe('chest', group='Coffres et caisses', label='Coffre', kind='item', variants=2)
def chest(m, seed=0):
    if seed % 2 == 0: _chest(m, PAL['wood'], PAL['iron_dark'], PAL['gold'])
    else: _chest(m, (84, 58, 44), PAL['iron'], PAL['iron_dark'])


@recipe('chest_open', group='Coffres et caisses', label='Coffre ouvert', kind='item')
def chest_open(m, seed=0): _chest(m, PAL['wood'], PAL['iron_dark'], PAL['gold'], open_=True, gold_inside=True)


@recipe('chest_trapped', group='Coffres et caisses', label='Coffre piégé', kind='item')
@fit(1.3)
def chest_trapped(m, seed=0):
    _chest(m, (96, 50, 44), PAL['coal'], PAL['iron_dark'])
    m.box(-16, 1, 12, 32, 1, 1, (180, 60, 60)); m.box(-17, 0, 11, 3, 4, 3, PAL['wood_dark']); m.box(14, 0, 11, 3, 4, 3, PAL['wood_dark'])                  # fil de déclenchement tendu devant
    m.box(-15, 0, -14, 5, 4, 3, (170, 40, 40)); m.box(-8, 0, -14, 5, 4, 3, (170, 40, 40)); m.box(-14, 4, -14, 1, 3, 1, PAL['rope']); m.box(-14, 0, -11, 3, 1, 8, (190, 60, 50))     # bâtons de poudre
    m.box(11, 0, 12, 6, 1, 6, PAL['iron_dark']); m.box(12, 1, 13, 4, 1, 4, PAL['iron'])                                                                 # plaque de pression


@recipe('crate', group='Coffres et caisses', label='Caisse', kind='item', variants=2)
def crate(m, seed=0):
    k = seed % 2
    for i in range(4): m.box(-10, i * 5, -10, 20, 4, 20, PAL['plank'] if i % 2 == 0 else (130, 94, 62))
    for (x, z) in ((-10, -10), (8, -10), (-10, 8), (8, 8)): m.box(x, 0, z, 2, 20, 2, PAL['wood_dark'])
    m.box(-10, 0, -10, 20, 2, 20, PAL['wood_dark'])
    if k == 1: m.box(-6, 6, 10, 12, 8, 1, PAL['cloth_red']); m.box(-4, 8, 11, 8, 1, 1, PAL['white']); m.box(-1, 8, 11, 2, 4, 1, PAL['white'])
    else: m.box(-10, 8, 10, 20, 1, 1, PAL['iron_dark']); m.box(-10, 8, -11, 20, 1, 1, PAL['iron_dark'])


@recipe('barrel', group='Coffres et caisses', label='Tonneau', kind='item')
def barrel(m, seed=0):
    m.box(-6, 0, -9, 12, 20, 18, PAL['wood']); m.box(-9, 0, -6, 18, 20, 12, PAL['wood']); m.box(-8, 0, -8, 16, 20, 16, PAL['wood'])
    for y in (3, 15): m.box(-9.5, y, -6, 19, 2, 12, PAL['iron_dark']); m.box(-6, y, -9.5, 12, 2, 19, PAL['iron_dark']); m.box(-8.5, y, -8.5, 17, 2, 17, PAL['iron_dark'])
    m.box(-7, 20, -7, 14, 1, 14, PAL['wood_light']); m.box(-1, 21, -1, 2, 1, 2, PAL['wood_dark']); m.box(-5, 20.5, -5, 10, 1, 1, PAL['wood_dark'])
