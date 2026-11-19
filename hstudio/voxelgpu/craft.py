"""Éléments « craft » : plantes, arbres, blocs de terrain, créatures, objets et petits lieux dans l'esprit des jeux de blocs, DESSINÉS ICI dans le style du studio.

Aucune texture ni aucun modèle d'un jeu existant n'est repris : chaque recette écrit ses boîtes elle-même, avec la palette (`PAL`) et le grain des décors de PIXEL 3D, pour que
ces éléments se posent à côté des meubles, des lieux et des personnages du studio sans qu'on voie la différence de main. L'inspiration est le genre (des animaux carrés, des
arbres en blocs, des minerais, des puits), pas une copie.

Écrire une recette :

    from .craft import recipe, Model, PAL

    @recipe('oak_tree', group='Nature', label='Chêne', kind='decor')          # kind : decor | creature | item | structure
    def oak_tree(m: Model, seed=0):
        m.box(-2, 0, -2, 4, 24, 4, PAL['wood'])                                # x, y, z (coin bas), largeur, hauteur, profondeur : en voxels de 1/16 m
        m.box(-8, 22, -8, 16, 10, 16, PAL['leaf'], jitter=.12)                 # `jitter` : variation de couleur par boîte (grain)

Repère : le modèle est centré sur x et z, posé au sol (y = 0 en bas), sa face avant regarde vers +z (la caméra de VOXEL). Unités d'écriture : le voxel (1/16 m) ; la sortie est en mètres.
`seed` rend la variante (arbres tous différents). `m.mirror_x()` copie le côté gauche vers le droit. `m.emit` pose une boîte lumineuse ; `m.light` une lumière de plan.
"""
import math, random

PX = 1. / 16.
REG = {}
KINDS = ('decor', 'creature', 'item', 'structure')

# Palette du studio : les couleurs des décors de PIXEL 3D (meubles, arbres, pierres), pas celles d'un autre jeu. Valeurs (r, g, b) 0-255.
PAL = dict(
    wood=(110, 80, 50), wood_dark=(70, 50, 36), wood_light=(150, 112, 72), plank=(120, 86, 56), bark=(60, 44, 30), birch=(214, 210, 198),
    leaf=(40, 90, 46), leaf_dark=(30, 60, 34), leaf_light=(70, 130, 62), pine=(24, 62, 40), autumn=(190, 100, 30), blossom=(240, 170, 200),
    grass=(60, 120, 50), dirt=(96, 68, 44), mud=(56, 41, 28), stone=(120, 120, 124), stone_dark=(78, 78, 84), stone_light=(160, 160, 164), cobble=(104, 104, 108),
    sand=(200, 170, 118), snow=(230, 234, 240), ice=(170, 210, 230), water=(50, 100, 170), lava=(239, 109, 30), brick=(150, 70, 52), clay=(144, 90, 68),
    iron=(190, 190, 196), iron_dark=(110, 112, 120), gold=(222, 180, 50), copper=(167, 99, 59), coal=(34, 34, 38), gem=(96, 196, 214), ruby=(200, 40, 60),
    skin=(218, 176, 125), skin_dark=(150, 100, 70), white=(236, 234, 226), black=(24, 24, 28), cloth_red=(160, 40, 40), cloth_blue=(50, 70, 130), cloth_green=(60, 100, 60),
    cloth_yellow=(210, 180, 60), cloth_brown=(110, 80, 56), fur_brown=(130, 90, 56), fur_grey=(140, 140, 146), fur_white=(228, 226, 218), fur_black=(40, 36, 36), fur_orange=(200, 120, 50),
    pink=(230, 150, 160), bone=(226, 222, 204), slime=(83, 184, 85), glass=(170, 210, 230), cloth=(190, 180, 160), rope=(160, 130, 80), straw=(214, 186, 90),
)


def _hex(c): return (int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])


class Model:
    """un modèle en construction : des boîtes en voxels de 1/16 m, un repère centré au sol"""

    def __init__(self, seed=0):
        self.boxes = []; self.lights = []; self.seed = seed; self.rng = random.Random(seed * 7919 + 13)

    def box(self, x, y, z, w, h, d, color, jitter=0., emis=0., ry=0.):
        """coin bas (x, y, z), taille (w, h, d), en voxels ; `jitter` = variation de couleur (0 à .3) ; `ry` : rotation en radians autour du centre de la boîte"""
        c = tuple(color)
        if jitter: k = 1. + (self.rng.random() - .5) * 2 * jitter; c = tuple(max(0, min(255, int(v * k))) for v in c)
        b = dict(x=(x + w / 2.) * PX, y=(y + h / 2.) * PX, z=(z + d / 2.) * PX, w=w * PX, h=h * PX, d=d * PX, color=_hex(c))
        if emis: b['emis'] = emis
        if ry: b['ry'] = ry
        self.boxes.append(b); return self

    def mirror_x(self, from_n=0):
        """copie en miroir (x -> -x) les boîtes écrites depuis `from_n` : on n'écrit que la moitié d'un animal, d'un meuble, d'une façade"""
        for b in list(self.boxes[from_n:]):
            if abs(b['x']) < 1e-6: continue
            c = dict(b); c['x'] = -b['x']
            if 'ry' in c: c['ry'] = -c['ry']
            self.boxes.append(c)
        return self

    def emit(self, x, y, z, w, h, d, color, power=1.5): return self.box(x, y, z, w, h, d, color, emis=power)

    def light(self, x, y, z, color, power=1.2, radius=3.):
        self.lights.append(dict(at=[x * PX, y * PX, z * PX], color=_hex(color), i=power * 2.2, dist=radius * 1.5, decay=1.4)); return self

    def ring(self, cx, cy, cz, r, h, color, n=12, size=3, jitter=.1):
        """un anneau de boîtes (tronc creux, puits, tour, couronne)"""
        for i in range(n):
            a = 2 * math.pi * i / n; self.box(cx + math.cos(a) * r - size / 2., cy, cz + math.sin(a) * r - size / 2., size, h, size, color, jitter=jitter)
        return self

    def blob(self, cx, cy, cz, rx, ry, rz, color, jitter=.12, step=2):
        """une masse arrondie faite de boîtes (feuillage, buisson, rocher, nuage)"""
        st = max(1, int(round(step)))                                     # un pas décimal faisait planter `range`
        for x in range(int(-rx), int(rx) + 1, st):
            for y in range(int(-ry), int(ry) + 1, st):
                for z in range(int(-rz), int(rz) + 1, st):
                    if (x / rx) ** 2 + (y / ry) ** 2 + (z / rz) ** 2 <= 1.0 + self.rng.random() * .25: self.box(cx + x, cy + y, cz + z, st, st, st, color, jitter=jitter)
        return self


def recipe(name, group='Divers', label=None, kind='decor', variants=1, note=''):
    """enregistre une recette `fn(m: Model, seed: int)` sous le nom `name` (unique) ; `variants` = nombre de graines montrées dans le catalogue"""
    def reg(fn):
        if name in REG: raise ValueError(f'recette craft en double : {name}')
        if kind not in KINDS: raise ValueError(f'kind inconnu : {kind}')
        REG[name] = dict(fn=fn, group=group, label=label or name.replace('_', ' ').capitalize(), kind=kind, variants=variants, note=note); return fn
    return reg


def build(name, seed=0):
    """-> (boîtes en mètres, lumières) d'une recette, graine `seed`"""
    if name not in REG: raise KeyError(f'élément craft inconnu : {name}')
    m = Model(seed); REG[name]['fn'](m, seed)
    return m.boxes, m.lights


def bset(name, at=(0., 0.), y=0., rot=0, scale=1., seed=0):
    """-> ({"type": "bset", ...}, lumières de plan) : la recette posée en `at` = [x, z], tournée de `rot` quarts de tour, agrandie de `scale`"""
    boxes, lights = build(name, seed); c, s = (1, 0), None
    ry = rot * math.pi / 2.; cs, sn = math.cos(ry), math.sin(ry); out = []
    for b in boxes:
        x, z = b['x'] * scale, b['z'] * scale
        o = dict(b, x=round(x * cs + z * sn + at[0], 4), y=round(b['y'] * scale + y, 4), z=round(-x * sn + z * cs + at[1], 4), w=round(b['w'] * scale, 4), h=round(b['h'] * scale, 4), d=round(b['d'] * scale, 4))
        if rot % 4: o['ry'] = round(b.get('ry', 0.) + ry, 4)
        out.append(o)
    lt = []
    for l in lights:
        x, z = l['at'][0] * scale, l['at'][2] * scale
        lt.append(dict(l, at=[round(x * cs + z * sn + at[0], 3), round(l['at'][1] * scale + y, 3), round(-x * sn + z * cs + at[1], 3)]))
    return dict(type='bset', boxes=out, craft=name), lt


def load_all():
    """importe les modules de recettes (chacun s'enregistre à l'import) ; un module absent ou cassé n'empêche pas les autres"""
    import importlib
    for mod in ('craft_nature', 'craft_things', 'craft_creatures', 'craft_places'):
        try: importlib.import_module(f'{__package__}.{mod}')
        except ModuleNotFoundError as e:
            if mod not in str(e): raise
    return REG


def catalogue():
    """fiches pour le catalogue : (nom, groupe, libellé, genre, variantes)"""
    load_all(); return [(n, r['group'], r['label'], r['kind'], r['variants']) for n, r in sorted(REG.items(), key=lambda kv: (kv[1]['group'], kv[0]))]
