"""Créatures « craft » : animaux de ferme, animaux sauvages, animaux marins et volants, monstres. Toutes ORIGINALES, dessinées ici avec la palette du studio (craft.PAL).

Statiques : une pose debout ou au repos par variante (aucune animation). Unité d'écriture : le voxel de 1/16 m ; face avant vers +z ; centré au sol.
Chaque recette montre plusieurs variantes (robe, race, espèce) choisies par la graine `seed`.
"""
import math
from .craft import recipe as _recipe, PAL as P, Model

G_FARM, G_WILD, G_SEA, G_MON = 'Animaux de ferme', 'Animaux sauvages', 'Animaux marins et volants', 'Monstres'
K = 'creature'


def recipe(name, group='Divers', label=None, kind='decor', variants=1, note=''):
    """comme craft.recipe, mais sans `jitter` : le grain est ajouté par le peintre (docs/STYLE_GUIDE_STUDIO.md, section 6), pas dans les données"""
    def deco(fn):
        def wrapped(m, seed=0):
            orig = m.box
            def box(x, y, z, w, h, d, color, jitter=0., emis=0., ry=0.): return orig(x, y, z, w, h, d, color, 0., emis, ry)
            m.box = box; return fn(m, seed)
        wrapped.__name__ = fn.__name__; wrapped.__module__ = fn.__module__; wrapped.__doc__ = fn.__doc__
        return _recipe(name, group, label, kind, variants, note)(wrapped)
    return deco


def pick(seed, *o): return o[seed % len(o)]
def dark(c, k=.6): return tuple(int(v * k) for v in c)
def light(c, k=1.25): return tuple(min(255, int(v * k)) for v in c)


def _fr(a, b, s):
    x = a
    while x <= b + 1e-6: yield x; x += s


def blob(m, cx, cy, cz, rx, ry, rz, color, jitter=.12, step=2., half=False):
    """une masse arrondie de boîtes (pas décimal accepté, contrairement à Model.blob)"""
    for x in _fr(-rx, rx, step):
        for y in _fr(0 if half else -ry, ry, step):
            for z in _fr(-rz, rz, step):
                if (x / rx) ** 2 + (y / ry) ** 2 + (z / rz) ** 2 <= 1.0 + m.rng.random() * .25: m.box(cx + x, cy + y, cz + z, step, step, step, color, jitter=jitter)


class Sc:
    """Model à l'échelle k (agrandir un monstre sans réécrire ses cotes)"""
    def __init__(self, m, k=1.): self.m, self.k = m, k
    def box(self, x, y, z, w, h, d, c, **kw): k = self.k; self.m.box(x * k, y * k, z * k, w * k, h * k, d * k, c, **kw); return self
    def emit(self, x, y, z, w, h, d, c, power=1.5): k = self.k; self.m.emit(x * k, y * k, z * k, w * k, h * k, d * k, c, power); return self
    def light(self, x, y, z, c, power=1.2, radius=3.): k = self.k; self.m.light(x * k, y * k, z * k, c, power, radius); return self
    def blob(self, cx, cy, cz, rx, ry, rz, c, **kw): k = self.k; blob(self.m, cx * k, cy * k, cz * k, rx * k, ry * k, rz * k, c, **kw); return self
    @property
    def rng(self): return self.m.rng


def rot90(m, k=1):
    """tourne les boîtes déjà écrites de k quarts de tour (x' = z, z' = -x) : un poisson écrit tête vers +z se voit de PROFIL par la caméra"""
    for _ in range(k):
        for b in m.boxes:
            b['x'], b['z'] = b['z'], -b['x']; b['w'], b['d'] = b['d'], b['w']
        for l in m.lights: l['at'][0], l['at'][2] = l['at'][2], -l['at'][0]


def eyes(m, cx, y, zf, dx, col=None, s=1.0, white=None, side=False):
    """deux yeux : sur la face avant (z = zf) ou, si `side`, sur les flancs de la tête (x = ±dx)"""
    col = col or P['black']
    for sg in (-1, 1):
        if side:
            x = cx + sg * dx - (0 if sg > 0 else .8)
            if white: m.box(x - (0 if sg > 0 else .1), y - .4, zf - .4, .9, s + .8, s + .8, white)
            m.box(x + (.1 if sg > 0 else 0), y, zf, .8, s, s, col)
        else:
            x = cx + sg * dx - s / 2
            if white: m.box(x - .5, y - .5, zf - .5, s + 1, s + 1, .9, white)
            m.box(x, y, zf - .3, s, s, 1.0, col)


def patches(m, col, n, W, H, L, y0, minsz=3, maxsz=6):
    """taches de robe posées sur le dessus et les flancs d'un corps (x ∈ [-W/2, W/2], z ∈ [-L/2, L/2], y ∈ [y0, y0+H])"""
    r = m.rng
    for _ in range(n):
        side = r.choice((-1, 1, 0)); pw, ph = r.randint(minsz, maxsz), r.randint(minsz, maxsz - 1); z = r.randint(int(-L / 2 + 1), max(int(-L / 2 + 1), int(L / 2 - pw - 1)))
        if side == 0: m.box(r.randint(int(-W / 2), max(int(-W / 2), int(W / 2 - ph))), y0 + H - .1, z, ph, .7, pw, col, jitter=.05)
        else: m.box((W / 2 - .1) if side > 0 else (-W / 2 - .6), r.randint(int(y0 + 1), max(int(y0 + 1), int(y0 + H - ph))), z, .7, ph, pw, col, jitter=.05)


def quad(m, col, belly=None, L=20, W=10, H=9, leg=8, lw=3, head=(7, 7, 7), head_lift=2, snout=None, snout_col=None, nostril=True, ears=None, ear_col=None, ear_size=(2, 3, 1.5),
         tail=None, tail_col=None, legcol=None, hoof=None, eye=None, eye_white=None, patch=None, patch_n=0, horns=None, horn_col=None, neck=1, eye_dy=0.):
    """un quadrupède : 4 pattes, corps, tête avec museau / oreilles / queue ; la tête regarde vers +z"""
    belly = belly or col; legcol = legcol or col; ear_col = ear_col or col; tail_col = tail_col or col
    for sx in (-1, 1):
        for sz in (-1, 1):
            x = sx * (W / 2 - lw / 2) - lw / 2; z = sz * (L / 2 - lw - .3) - lw / 2
            m.box(x, 0, z, lw, leg, lw, legcol, jitter=.05)
            if hoof: m.box(x - .1, 0, z - .1, lw + .2, 1.6, lw + .2, hoof)
    m.box(-W / 2, leg, -L / 2, W, H, L, col, jitter=.06)
    m.box(-W / 2 + 1, leg - .6, -L / 2 + 1, W - 2, 1.6, L - 2, belly)
    if patch and patch_n: patches(m, patch, patch_n, W, H, L, leg)
    hw, hh, hd = head; hy = leg + H - hh + head_lift; hz = L / 2 - neck
    m.box(-hw / 2, hy, hz, hw, hh, hd, col, jitter=.05)
    zf = hz + hd
    if snout:
        sw, sh, sd = snout; sc = snout_col or col
        m.box(-sw / 2, hy + 1, zf - .2, sw, sh, sd, sc, jitter=.04)
        if nostril: m.box(-sw / 2 + .6, hy + 1 + sh - 1.2, zf + sd - .3, 1, 1, .6, P['black']); m.box(sw / 2 - 1.6, hy + 1 + sh - 1.2, zf + sd - .3, 1, 1, .6, P['black'])
    eyes(m, 0, hy + hh - 3 + eye_dy, zf, hw / 2 - 1.5, eye, 1.2 if not eye_dy else 1.0, eye_white)
    if ears == 'up':
        ew, eh, ed = ear_size
        for sg in (-1, 1): m.box(sg * (hw / 2 - ew / 2 - .3) - ew / 2, hy + hh - .2, hz + hd / 2 - ed / 2, ew, eh, ed, ear_col, jitter=.04)
    elif ears == 'flop':
        ew, eh, ed = ear_size
        for sg in (-1, 1): m.box(sg * (hw / 2 + ew / 2 - .2) - ew / 2, hy + hh - eh - .5, hz + hd / 2 - ed / 2 - .5, ew, eh, ed, ear_col, jitter=.04)
    elif ears == 'side':
        ew, eh, ed = ear_size
        for sg in (-1, 1): m.box(sg * (hw / 2 + ew / 2) - ew / 2, hy + hh - eh, hz + hd / 2 - ed / 2, ew, eh, ed, ear_col, jitter=.04)
    if horns:
        for sg in (-1, 1):
            m.box(sg * (hw / 2 - .3) - .8, hy + hh, hz + 1.5, 1.6, 2.5, 1.6, horn_col or P['bone']); m.box(sg * (hw / 2 + .5) - .8, hy + hh + 2, hz + 1.5, 1.6, 1.5, 1.6, horn_col or P['bone'])
    if tail == 'down': m.box(-.8, leg + H - 7, -L / 2 - 1.2, 1.6, 7, 1.6, tail_col, jitter=.05); m.box(-1.2, leg + H - 9, -L / 2 - 1.5, 2.4, 2.6, 2.4, dark(tail_col, .8))
    elif tail == 'short': m.box(-1, leg + H - 4, -L / 2 - 2, 2, 3, 2.5, tail_col)
    elif tail == 'up': m.box(-.8, leg + H - 1, -L / 2 - 1.5, 1.6, 6, 1.6, tail_col)
    elif tail == 'curl': m.box(-.7, leg + H - 3, -L / 2 - 1.5, 1.4, 1.4, 2, tail_col); m.box(-.7, leg + H - 1.6, -L / 2 - 2.5, 1.4, 1.4, 1.4, tail_col)
    elif tail == 'bushy': m.box(-2, leg + H - 5, -L / 2 - 6, 4, 4, 7, tail_col, jitter=.06); m.box(-2, leg + H - 5, -L / 2 - 8, 4, 4, 2.5, light(tail_col, 1.3))


# ====================================================================== ANIMAUX DE FERME
@recipe('cow', G_FARM, 'Vache', K, variants=3)
def cow(m, seed=0):
    col, pc = pick(seed, (P['white'], P['black']), (P['white'], P['fur_brown']), (P['fur_brown'], P['white']))
    quad(m, col, belly=P['pink'] if seed % 3 != 2 else col, L=22, W=11, H=10, leg=9, lw=3.2, head=(8, 8, 7), head_lift=-1, snout=(6, 4, 2), snout_col=P['pink'], ears='side', ear_col=col, ear_size=(3, 1.6, 2),
         tail='down', tail_col=col, hoof=dark(P['stone_dark'], .6), patch=pc, patch_n=7, horns=True, horn_col=P['bone'], eye_white=P['white'])
    m.box(-2.5, 8.4, -1, 5, 2.2, 4, P['pink'])             # pis


@recipe('pig', G_FARM, 'Cochon', K, variants=2)
def pig(m, seed=0):
    col = pick(seed, P['pink'], light(P['pink'], 1.0))
    quad(m, col, L=17, W=9, H=8, leg=5, lw=2.8, head=(7, 7, 6), head_lift=-.5, snout=(4, 3, 2.5), snout_col=dark(col, .85), ears='flop', ear_col=dark(col, .85), ear_size=(1.5, 3, 3), tail='curl', tail_col=col, hoof=dark(col, .6))
    if seed % 2: patches(m, P['fur_black'], 4, 9, 8, 17, 5, 3, 5)


@recipe('sheep', G_FARM, 'Mouton', K, variants=2)
def sheep(m, seed=0):
    if seed % 2 == 0:                                      # laineux : de grands volumes de laine
        wool = P['white']
        for sx in (-1, 1):
            for sz in (-1, 1): m.box(sx * 3.2 - 1, 0, sz * 5.5 - 1, 2, 7, 2, P['fur_black'])
        m.box(-6, 7, -9, 12, 9, 18, wool); m.box(-6.6, 8, -8, 13.2, 6, 15, light(wool, .96)); m.box(-5, 16, -7, 10, 1.8, 13, wool)
        m.box(-3, 10, 8, 6, 6, 6, P['fur_black']); m.box(-3.2, 15.5, 9, 6.4, 2, 5, wool)
        eyes(m, 0, 13.5, 14, 1.8, P['black'], 1.0, P['white'])
        for sg in (-1, 1): m.box(sg * 3.6 - 1.2, 12, 9.5, 2.4, 1.6, 2.6, P['fur_black'])
    else:                                                    # tondu
        quad(m, light(P['pink'], 1.05), L=16, W=8, H=8, leg=7, lw=2.4, head=(5.5, 6.5, 6), head_lift=1, ears='side', ear_col=P['fur_black'], ear_size=(2.4, 1.5, 2.2), tail='short', tail_col=P['white'], legcol=P['fur_black'])
        m.box(-3, 12, 8, 6, 7, 6, P['fur_black'], jitter=.05)
        m.box(-4, 15, -2, 8, 2, 12, P['white'], jitter=.08)


@recipe('chicken', G_FARM, 'Poule', K, variants=2)
def chicken(m, seed=0):
    col = pick(seed, P['white'], P['fur_brown'])
    m.box(-.7, 0, -1.8, 1, 5, 1, P['fur_orange']); m.box(.7, 0, -1.8, 1, 5, 1, P['fur_orange'])
    m.box(-.7, 0, -2.6, 1.2, .8, 2.5, P['fur_orange']); m.box(.7, 0, -2.6, 1.2, .8, 2.5, P['fur_orange'])
    m.box(-3.2, 4.5, -5, 6.4, 6, 10, col, jitter=.06); m.box(-2.8, 9.5, -7, 5.6, 3, 5, col, jitter=.06); m.box(-3.4, 5, -3, 1.2, 4, 6, dark(col, .9)); m.box(2.2, 5, -3, 1.2, 4, 6, dark(col, .9))
    m.box(-2, 9, 3, 4, 6, 4, col, jitter=.05); m.box(-.5, 12, 6.8, 1, 1.5, 2.2, P['fur_orange']); m.box(-.4, 10.2, 6.8, .8, 1.5, 1.6, P['fur_orange'])
    m.box(-.8, 14.8, 4, 1.6, 2.2, 2.6, P['ruby']); m.box(-.5, 9.2, 6.6, 1, 1.8, 1.2, P['ruby'])
    eyes(m, 0, 12.4, 7, 1.7, P['black'], 1.0)


@recipe('chick', G_FARM, 'Poussin', K)
def chick(m, seed=0):
    c = P['cloth_yellow']
    m.box(-.6, 0, -.8, .8, 3, .8, P['fur_orange']); m.box(.8, 0, -.8, .8, 3, .8, P['fur_orange'])
    m.box(-3, 2.6, -3.2, 6, 5, 6.4, c, jitter=.06); m.box(-2.4, 6.5, 0, 4.8, 4.2, 4.2, c, jitter=.05)
    m.box(-.6, 7.6, 3.8, 1.2, 1, 1.6, P['fur_orange']); eyes(m, 0, 8.6, 4.2, 1.5, P['black'], .9)
    for sg in (-1, 1): m.box(sg * 3 - (0 if sg > 0 else .9), 3.6, -2.2, .9, 3, 3.6, light(c, .9))


def _horse(m, seed, donkey=False):
    coats = [(P['fur_brown'], P['fur_black']), (P['fur_black'], P['fur_black']), (P['fur_white'], P['fur_grey']), ((214, 170, 100), (238, 228, 200))]
    col, mane = (P['fur_grey'], dark(P['fur_grey'], .6)) if donkey else coats[seed % 4]
    L, W, H, leg = (20, 8, 10, 13) if donkey else (24, 9, 11, 16)
    for sx in (-1, 1):
        for sz in (-1, 1):
            x = sx * (W / 2 - 1.6) - 1.6; z = sz * (L / 2 - 3) - 1.6
            m.box(x, 0, z, 3.2, leg, 3.2, col, jitter=.05); m.box(x - .1, 0, z - .1, 3.4, 2, 3.4, dark(col, .5) if not donkey else P['black'])
            if seed % 4 == 3 or donkey: m.box(x, 2, z, 3.2, 2, 3.2, light(col, 1.25))
    m.box(-W / 2, leg, -L / 2, W, H, L, col, jitter=.05)
    nx = 3.4 if not donkey else 3.6
    m.box(-nx / 2 - .3, leg + H - 3, L / 2 - 4, nx + .6, 8, 4.6, col, jitter=.04); m.box(-nx / 2, leg + H + 3, L / 2 - 2.4, nx, 6, 4, col, jitter=.04)
    hy = leg + H + 5; m.box(-2.4, hy, L / 2 + .4, 4.8, 5.5, 4.4, col, jitter=.04); m.box(-2.1, hy - .4, L / 2 + 4.4, 4.2, 4.2, 5.4, col if not donkey else light(col, 1.2), jitter=.04)
    m.box(-2.2, hy - .4, L / 2 + 8.6, 4.4, 2.4, 1.2, dark(col, .6) if not donkey else light(col, 1.4)); m.box(-1.5, hy + .8, L / 2 + 9.6, 1, 1, .6, P['black']); m.box(.5, hy + .8, L / 2 + 9.6, 1, 1, .6, P['black'])
    eyes(m, 0, hy + 3.6, L / 2 + 3.8, 2.4, P['black'], 1.1, P['white'], side=True)
    for sg in (-1, 1):
        if donkey: m.box(sg * 1.5 - .9, hy + 5.4, L / 2 + .6, 1.8, 6.5, 1.4, col); m.box(sg * 1.5 - .6, hy + 6.5, L / 2 + .8, 1.2, 4, .6, light(col, 1.4))
        else: m.box(sg * 1.6 - .8, hy + 5.4, L / 2 + .8, 1.6, 3, 1.4, col)
    m.box(-.6, leg + H + 2, L / 2 - 4, 1.2, 10, 1.6, mane, jitter=.08); m.box(-.7, hy + 5.2, L / 2 + .2, 1.4, 1.4, 3, mane)
    tl = 8 if donkey else 12; m.box(-1.3, leg + H - 3 - tl + 4, -L / 2 - 2.2, 2.6, tl, 2.6, mane if not donkey else dark(col, .7), jitter=.07)


@recipe('horse', G_FARM, 'Cheval', K, variants=4)
def horse(m, seed=0): _horse(m, seed)


@recipe('donkey', G_FARM, 'Âne', K)
def donkey(m, seed=0): _horse(m, seed, True)


@recipe('goat', G_FARM, 'Chèvre', K, variants=2)
def goat(m, seed=0):
    col = pick(seed, P['white'], P['fur_brown'])
    quad(m, col, L=15, W=7, H=7, leg=8, lw=2, head=(5, 6, 6), head_lift=2, snout=(3.4, 3, 2.4), snout_col=light(col, .95), ears='side', ear_col=dark(col, .8), ear_size=(3, 1.2, 2), tail='up', tail_col=col, hoof=P['black'], horns=True, horn_col=P['bone'])
    m.box(-.7, 12.5, 10, 1.4, 3, 1.4, light(col, 1.15))        # barbiche


@recipe('llama', G_FARM, 'Lama', K, variants=2)
def llama(m, seed=0):
    col = pick(seed, P['cloth'], P['fur_brown']); wool = light(col, 1.12)
    for sx in (-1, 1):
        for sz in (-1, 1): m.box(sx * 2.8 - 1.2, 0, sz * 6 - 1.2, 2.4, 12, 2.4, dark(col, .85), jitter=.05)
    m.box(-4.5, 12, -9, 9, 9, 18, wool, jitter=.1); m.box(-3.6, 11.4, -8, 7.2, 1.6, 16, light(col, 1.3))
    m.box(-2.2, 19, 5, 4.4, 8, 4.4, wool, jitter=.08); m.box(-2, 26, 5.4, 4, 3, 4, wool, jitter=.06)
    m.box(-2.4, 26.4, 7.5, 4.8, 4.6, 4.2, col, jitter=.05); m.box(-1.6, 26, 11, 3.2, 3, 2.4, light(col, 1.15)); eyes(m, 0, 29, 11.6, 1.7, P['black'], 1.0, P['white'])
    for sg in (-1, 1): m.box(sg * 2 - .8, 31, 8, 1.6, 4.2, 1.6, col); m.box(sg * 2 - .5, 32, 8.2, 1, 2.6, .8, P['pink'])
    m.box(-1.3, 15, -10.5, 2.6, 3, 2, wool)


@recipe('dog', G_FARM, 'Chien', K, variants=4)
def dog(m, seed=0):
    breed = seed % 4
    if breed == 0: col, belly, ear = P['fur_brown'], light(P['fur_brown'], 1.2), dark(P['fur_brown'], .7); L, W, H, leg, head = 17, 7, 7, 8, (6, 6, 6)       # berger
    elif breed == 1: col, belly, ear = P['fur_grey'], P['white'], P['fur_grey']; L, W, H, leg, head = 16, 7.5, 7.5, 8, (6.5, 6.5, 6)                            # husky
    elif breed == 2: col, belly, ear = P['white'], P['white'], P['fur_black']; L, W, H, leg, head = 16, 6.5, 7, 9, (5.5, 6, 6.5)                              # dalmatien
    else: col, belly, ear = P['fur_orange'], P['white'], P['fur_orange']; L, W, H, leg, head = 11, 5.5, 5.5, 5, (5, 5, 5)                                       # terrier
    quad(m, col, belly=belly, L=L, W=W, H=H, leg=leg, lw=2.2, head=head, head_lift=2, snout=(3, 2.6, 3), snout_col=light(col, 1.1) if breed in (0, 3) else P['white'], ears='flop' if breed in (0, 2) else 'up',
         ear_col=ear, ear_size=(1.4, 3, 2.2) if breed in (0, 2) else (1.8, 2.8, 1.4), tail='up' if breed in (1, 3) else 'down', tail_col=col, eye_white=P['white'] if breed == 1 else None)
    if breed == 2: patches(m, P['black'], 9, W, H, L, leg, 1, 3)
    if breed == 1:                                           # husky : masque sombre sur le haut de la tête, joues blanches
        hh_, hz_ = head[1], L / 2 - 1; hy_ = leg + H - hh_ + 2
        m.box(-head[0] / 2 + .2, hy_ + hh_ - 1.8, hz_ + .6, head[0] - .4, 2, head[2] - 1.2, dark(col, .62), jitter=.04); m.box(-1.2, hy_ + 1, hz_ + head[2] - .4, 2.4, hh_ - 3, .6, P['white'])


@recipe('cat', G_FARM, 'Chat', K, variants=4)
def cat(m, seed=0):
    col, belly = pick(seed, (P['fur_orange'], P['white']), (P['fur_black'], P['fur_black']), (P['fur_grey'], P['white']), (P['white'], P['white']))
    quad(m, col, belly=belly, L=12, W=5, H=5, leg=5, lw=1.8, head=(5, 4.6, 4.2), head_lift=1.4, snout=(2, 1.4, 1.2), snout_col=P['pink'], nostril=False, ears='up', ear_col=col, ear_size=(1.6, 2, 1), tail='up', tail_col=col,
         eye=dark(P['gem'], .7) if seed != 2 else dark(P['cloth_yellow'], .75), eye_white=None, eye_dy=1.1)
    m.box(-.5, 12, -7.4, 1, 6, 1, col); m.box(-.5, 17.5, -7.4, 1, 1, 1, dark(col, .7))
    if seed == 0: patches(m, dark(P['fur_orange'], .75), 4, 5, 5, 12, 5, 1, 3)


@recipe('rabbit', G_FARM, 'Lapin', K, variants=3)
def rabbit(m, seed=0):
    col, belly = pick(seed, (P['fur_white'], P['white']), (P['fur_brown'], light(P['fur_brown'], 1.3)), (P['fur_grey'], P['white']))
    m.box(-3, 0, -5.5, 6, 5.5, 7, col, jitter=.06); m.box(-2.6, .6, -6, 5.2, 3.6, 2, belly); m.box(-2.2, 4, -.5, 4.4, 4.6, 4.4, col, jitter=.05)
    m.box(-1.5, 3.8, 3.5, 3, 3, 2.4, light(col, 1.05)); m.box(-.5, 5.2, 5.7, 1, .8, .6, P['pink']); eyes(m, 0, 6, 3.8, 1.8, P['black'], .9)
    for sg in (-1, 1):
        m.box(sg * 1.2 - .8, 8.3, -.2, 1.6, 6.5, 1, col); m.box(sg * 1.2 - .4, 8.8, .6, .8, 5, .4, P['pink']); m.box(sg * 3 - (0 if sg > 0 else 1.4), 0, -2.8, 1.4, 1.6, 4.5, dark(col, .85)); m.box(sg * 1.5 - .6, 0, 1.3, 1.2, 4, 1.2, col)
    m.box(-1.2, 2.5, -7.8, 2.4, 2.4, 2.4, P['white'])


# ====================================================================== ANIMAUX SAUVAGES
@recipe('wolf', G_WILD, 'Loup', K, variants=3)
def wolf(m, seed=0):
    col, belly, mark = pick(seed, (P['fur_grey'], light(P['fur_grey'], 1.35), dark(P['fur_grey'], .6)), (P['fur_white'], P['white'], P['fur_grey']), (P['fur_black'], dark(P['fur_grey'], .8), P['black']))
    quad(m, col, belly=belly, L=20, W=7.5, H=8, leg=10, lw=2.4, head=(6.4, 6, 5.5), head_lift=1, snout=(3.2, 3, 4.4), snout_col=light(col, 1.02), ears='up', ear_col=col, ear_size=(1.8, 2.8, 1.3), tail='bushy', tail_col=dark(col, .85),
         eye=P['cloth_yellow'] if seed != 1 else P['gem'])
    m.box(-3.8, 10 + 7, 7, 7.6, 3, 7, light(col, 1.03)); m.box(-4, 10 + 2, -9, 8, 5, 8, col, jitter=.08); m.box(-3, 10 + 8.4, -9, 6, 1.6, 17, mark)


@recipe('fox', G_WILD, 'Renard', K, variants=2)
def fox(m, seed=0):
    col, tip = pick(seed, (P['fur_orange'], P['white']), (P['fur_grey'], P['white']))
    quad(m, col, belly=P['white'], L=14, W=6, H=6, leg=7, lw=1.8, head=(5.4, 5, 4.6), head_lift=1.6, snout=(2.6, 2.2, 3.4), snout_col=P['white'], ears='up', ear_col=col, ear_size=(2, 3, 1.2), tail='bushy', tail_col=col, legcol=dark(col, .45))
    m.box(-2, 7 + 6 + 3.8, 7.6, 4, 1, 1.2, dark(col, .4)); m.box(-1.9, 7 + 0, -14.5, 3.8, 3.8, 2.4, tip)


@recipe('bear', G_WILD, 'Ours', K, variants=3)
def bear(m, seed=0):
    col, muzzle = pick(seed, (P['fur_brown'], light(P['fur_brown'], 1.5)), (P['fur_black'], P['fur_brown']), (P['fur_white'], P['cloth']))
    quad(m, col, L=22, W=12, H=11, leg=9, lw=4.2, head=(8, 7, 6), head_lift=-1.5, snout=(4.4, 3.4, 3), snout_col=muzzle, ears='side', ear_col=col, ear_size=(2.4, 2.2, 1.8), tail='short', tail_col=col, hoof=P['black'])
    m.box(-4.4, 9 + 11 - 1, 7, 8.8, 3, 7, dark(col, .9), jitter=.08)


@recipe('deer', G_WILD, 'Cerf', K, variants=2)
def deer(m, seed=0):
    col = pick(seed, P['fur_brown'], (170, 120, 70))
    for sx in (-1, 1):
        for sz in (-1, 1): m.box(sx * 2.8 - 1, 0, sz * 6.3 - 1, 2, 15, 2, dark(col, .85), jitter=.04); m.box(sx * 2.8 - 1.1, 0, sz * 6.3 - 1.1, 2.2, 1.6, 2.2, P['black'])
    m.box(-4, 15, -9, 8, 8, 18, col, jitter=.06); m.box(-3, 14.4, -8, 6, 1.5, 16, P['white']); m.box(-4.1, 16, -9, 8.2, 3, 5, light(col, 1.25))
    m.box(-2, 21, 5, 4, 7, 4, col, jitter=.05); m.box(-2.3, 27, 5.4, 4.6, 5, 4, col, jitter=.05); m.box(-1.6, 27, 9.2, 3.2, 3.4, 3.6, light(col, 1.2)); m.box(-.8, 28.2, 12.6, 1.6, 1.2, .8, P['black'])
    eyes(m, 0, 30, 9, 2.3, P['black'], 1.0, P['white'], side=True)
    for sg in (-1, 1):
        m.box(sg * 2.4 - .9, 31.5, 6, 1.8, 3, 1.4, col); m.box(sg * 1.5 - .4, 32, 6.8, .8, 5, .8, P['bone'])
        if seed % 2 == 0: m.box(sg * 2.6 - .4, 36, 6.8, .8, 3, .8, P['bone']); m.box(sg * 3.8 - .4, 38, 6.8, .8, 4, .8, P['bone']); m.box(sg * 3 - .4, 38.4, 8.2, .8, .8, 2.5, P['bone'])
    m.box(-1.3, 20, -10, 2.6, 4, 2, P['white'])


@recipe('boar', G_WILD, 'Sanglier', K)
def boar(m, seed=0):
    col = dark(P['fur_brown'], .6)
    quad(m, col, L=19, W=9, H=9, leg=6, lw=2.6, head=(6.6, 6.2, 6.6), head_lift=-1.5, snout=(4, 3, 3.4), snout_col=dark(P['pink'], .6), ears='up', ear_col=col, ear_size=(2, 2.4, 1.2), tail='short', tail_col=col, hoof=P['black'])
    m.box(-3.5, 6 + 9 - .4, -8, 7, 3.2, 14, P['fur_black'], jitter=.08)
    for sg in (-1, 1): m.box(sg * 2.4 - .5, 6 + 1.2, 9.4 + 5.5, 1, 2.2, 1.2, P['bone'])


@recipe('squirrel', G_WILD, 'Écureuil', K)
def squirrel(m, seed=0):
    c = P['fur_orange']
    m.box(-2, 0, -2.4, 4, 5, 4.6, c, jitter=.05); m.box(-1.6, 4.6, -.4, 3.2, 3.4, 3.4, c, jitter=.05); m.box(-1.1, 5, 3, 2.2, 1.8, 1.2, light(c, 1.3)); m.box(-.4, 6.4, 3.8, .8, .8, .5, P['black'])
    eyes(m, 0, 6.2, 3, 1.3, P['black'], .8)
    for sg in (-1, 1): m.box(sg * 1.2 - .5, 7.8, 1, 1, 2, 1, c)
    m.box(-1.6, 1.5, -6, 3.2, 8, 3, c, jitter=.07); m.box(-1.8, 8, -5.4, 3.6, 4, 3, light(c, 1.2)); m.box(-1.4, 0, 1, 2.8, 1.4, 1.6, dark(c, .8))


@recipe('spider', G_WILD, 'Araignée', K, variants=2)
def spider(m, seed=0):
    col, eyec = pick(seed, (P['black'], P['ruby']), (P['fur_brown'], P['cloth_yellow']))
    m.box(-4.6, 3.4, -9.4, 9.2, 4.4, 9.4, col); m.box(-3.6, 7.6, -8.4, 7.2, 1.6, 7.4, dark(col, 1.15)); m.box(-3, 3.8, .2, 6, 3.6, 5.2, dark(col, 1.2) if seed == 0 else col)
    if seed == 1: m.box(-1.5, 9.2, -8, 3, .6, 6, P['cloth_yellow'])
    for sg in (-1, 1):
        for i, zz in enumerate((-4, -1.6, 1, 3.2)):
            f = 1 + (i % 2) * .15; m.box(sg * 3.5 - (0 if sg > 0 else 3), 5.5, zz, 3, 1, 1, dark(col, 1.2)); m.box(sg * (6.4 * f) - (0 if sg > 0 else 1), 5.5, zz, 1, 1, 1, dark(col, 1.2))
            m.box(sg * (6.4 * f) - (0 if sg > 0 else 1.2), 0, zz + (i - 1.5) * .4, 1.2, 6.5, 1.2, dark(col, 1.2))
    for sg in (-1, 1): m.box(sg * 1.5 - .4, 5, 5.4, .8, .8, .6, eyec); m.box(sg * .7 - .4, 6, 5.4, .8, .8, .6, eyec); m.box(sg * 1.2 - .5, 2.6, 5.5, 1, 2.6, 1, P['bone'])


@recipe('snake', G_WILD, 'Serpent', K, variants=2)
def snake(m, seed=0):
    col, alt = pick(seed, (P['leaf'], P['cloth_yellow']), (P['fur_brown'], P['sand']))
    n = 10
    for i in range(n):
        t = i / (n - 1); z = -14 + t * 22; x = math.sin(t * 9) * 5 * (1 - t * .4); w = 3.4 - t * 1.4 if t < .85 else 2.6
        m.box(x - w / 2, 0, z - 2.2, w, 2.6 + (1 - t) * 1.2, 4.4, col if i % 3 else alt)
    hx = math.sin(9) * 5 * .6
    m.box(hx - 2.2, 0, 8, 4.4, 3.4, 4.8, col); eyes(m, hx, 2.2, 12.5, 1.5, P['black'], .9, P['cloth_yellow']); m.box(hx - .3, .6, 12.7, .6, .4, 2.4, P['ruby']); m.box(hx - .8, .6, 15, 1.6, .4, .6, P['ruby'])


@recipe('frog', G_WILD, 'Grenouille', K, variants=2)
def frog(m, seed=0):
    col, belly = pick(seed, (P['leaf_light'], P['cloth_yellow']), (P['cloth_yellow'], P['white']))
    m.box(-3.4, 1.4, -4, 6.8, 4.4, 7.4, col, jitter=.07); m.box(-3, .6, -3.6, 6, 1.4, 6.6, belly)
    m.box(-3, 3.8, 2.4, 6, 3.2, 3, col, jitter=.05); m.box(-2.6, 3, 5, 5.2, 1, .6, dark(col, .6))
    for sg in (-1, 1):
        m.box(sg * 2.2 - 1.1, 6.4, 2.2, 2.2, 2.2, 2.2, col); m.box(sg * 2.2 - .6, 6.8, 3.8, 1.2, 1.4, .7, P['black'])
        m.box(sg * 4.2 - (0 if sg > 0 else 2.2), .4, -4.6, 2.2, 1.6, 6, dark(col, .85)); m.box(sg * 5.2 - (0 if sg > 0 else 1.2), 0, -1.2, 1.2, 1, 3.6, dark(col, .85)); m.box(sg * 2.4 - .7, 0, 3.6, 1.4, 2.4, 1.6, dark(col, .85)); m.box(sg * 2.4 - 1, 0, 4.8, 2, .7, 1.8, dark(col, .85))
    if seed == 1: patches(m, P['black'], 5, 6.8, 4.4, 7.4, 1.4, 1, 2)


@recipe('turtle', G_WILD, 'Tortue', K, variants=2)
def turtle(m, seed=0):
    shell, skin = pick(seed, (P['leaf_dark'], P['leaf']), (P['fur_brown'], P['sand']))
    m.box(-5.4, 1, -6.4, 10.8, 1.6, 12.8, P['bone'])
    m.box(-6, 2.4, -7, 12, 2.4, 14, shell); m.box(-5, 4.6, -6, 10, 1.8, 12, light(shell, 1.08)); m.box(-3.4, 6.2, -4.6, 6.8, 1.2, 9.2, light(shell, 1.18))
    for sx in (-1, 1):
        for sz in (-1, 1): m.box(sx * 4.6 - 1.4, 0, sz * 4.6 - 1.4, 2.8, 2.4, 2.8, skin)
    m.box(-1.6, 1.8, 7.4, 3.2, 3, 4.2, skin); eyes(m, 0, 3.4, 11.4, 1.1, P['black'], .8); m.box(-.5, 1.6, -9, 1, 1, 2, skin)


@recipe('hedgehog', G_WILD, 'Hérisson', K)
def hedgehog(m, seed=0):
    sp, sk = P['fur_brown'], P['fur_orange']
    m.box(-4.4, .8, -6, 8.8, 3.2, 9.6, sp); m.box(-3.8, 4, -5.4, 7.6, 2.2, 8.4, dark(sp, .8)); m.box(-3, 6.2, -4.6, 6, 1.4, 6.6, dark(sp, .65))
    for i in range(6): m.box(-3.6 + i * 1.3, 7.4, -4 - (i % 2) * .6, .8, 2.2, .8, dark(sp, .55))
    m.box(-2, .8, 3, 4, 3.4, 3.8, sk); m.box(-.8, 1.4, 6.6, 1.6, 1.4, 1, P['black']); eyes(m, 0, 2.8, 6.8, 1.4, P['black'], .8)
    for sg in (-1, 1): m.box(sg * 2.2 - .6, 0, 2.2, 1.2, 1.2, 1.6, sk); m.box(sg * 3 - .7, 0, -4, 1.4, 1.4, 1.6, sk)


# ====================================================================== ANIMAUX MARINS ET VOLANTS
def _bird(m, body, wing, beak, belly=None, size=1., legs=P['fur_orange'], crest=None, tail=None, eye_white=None, hy=0.):
    s = size; belly = belly or body
    m.box(-.8 * s, 0, -.9 * s, .9 * s, 6 * s, .9 * s, legs); m.box(.8 * s, 0, -.9 * s, .9 * s, 6 * s, .9 * s, legs)
    m.box(-3.4 * s, 5.5 * s, -5.2 * s, 6.8 * s, 6.4 * s, 10.4 * s, body, jitter=.06); m.box(-2.8 * s, 5.2 * s, -3 * s, 5.6 * s, 2 * s, 7 * s, belly)
    m.box(-2.6 * s, 10.2 * s, 2 * s, 5.2 * s, 5.2 * s, 5 * s, body, jitter=.05)
    m.box(-.8 * s, 11.5 * s, 7 * s, 1.6 * s, 1.6 * s, 3 * s, beak); m.box(-.7 * s, 10.6 * s, 7 * s, 1.4 * s, .9 * s, 2.4 * s, dark(beak, .85))
    eyes(m, 0, 13 * s, 6.9 * s, 2 * s, P['black'], 1.1 * s, eye_white)
    for sg in (-1, 1): m.box(sg * 3.4 * s - (0 if sg > 0 else 1.4 * s), 6 * s, -3.8 * s, 1.4 * s, 4.6 * s, 7.6 * s, wing, jitter=.07)
    tail = tail or dark(body, .8); m.box(-2 * s, 6.6 * s, -9 * s, 4 * s, 1.6 * s, 5 * s, tail, jitter=.06)
    if crest: m.box(-.6 * s, 15 * s, 3 * s, 1.2 * s, 2.4 * s, 3 * s, crest)


@recipe('parrot', G_SEA, 'Perroquet', K, variants=2)
def parrot(m, seed=0):
    body, wing, tail = pick(seed, (P['ruby'], P['cloth_blue'], P['cloth_yellow']), (P['leaf'], P['cloth_yellow'], P['cloth_blue']))
    _bird(m, body, wing, P['bone'], belly=light(body, 1.1), size=1.15, legs=P['stone_dark'], tail=tail, eye_white=P['white'])
    m.box(-1, 11, 8.6, 2, 2, 1.4, P['bone'])


@recipe('owl', G_SEA, 'Hibou', K)
def owl(m, seed=0):
    c = P['fur_brown']
    m.box(-1.6, 0, -.8, 1.2, 3, 1.2, P['fur_orange']); m.box(.4, 0, -.8, 1.2, 3, 1.2, P['fur_orange'])
    m.box(-4, 2.6, -4, 8, 11, 8, c, jitter=.07); m.box(-3, 2.2, -3.4, 6, 8, 2, light(c, 1.5)); m.box(-4.4, 12, -4.2, 8.8, 5, 8.4, c, jitter=.05)
    for sg in (-1, 1):
        m.box(sg * 2.3 - 1.6, 12.6, 3.6, 3.2, 3.2, .9, P['white']); m.box(sg * 2.3 - .8, 13.2, 4.2, 1.6, 1.8, .9, P['cloth_yellow']); m.box(sg * 2.3 - .5, 13.6, 4.7, 1, 1, .6, P['black'])
        m.box(sg * 3.6 - .8, 16.6, -2, 1.8, 2.2, 1.6, c); m.box(sg * 4.4 - (0 if sg > 0 else 1.6), 4, -3, 1.6, 8, 6, dark(c, .8), jitter=.05)
    m.box(-.7, 11.4, 4.2, 1.4, 1.8, 1.4, P['fur_orange']); m.box(-3, 2.4, -7, 6, 3, 4, dark(c, .85))


@recipe('crow', G_SEA, 'Corbeau', K)
def crow(m, seed=0): _bird(m, P['black'], dark(P['black'], 1.4), P['stone_dark'], belly=P['black'], size=1.1, legs=P['stone_dark'], tail=P['black'], eye_white=P['stone_light'])


@recipe('duck', G_SEA, 'Canard', K, variants=2)
def duck(m, seed=0):
    if seed % 2 == 0: _bird(m, P['fur_brown'], dark(P['fur_brown'], .8), P['cloth_yellow'], belly=light(P['fur_brown'], 1.3), size=1.05, legs=P['fur_orange'])
    else: _bird(m, P['white'], P['cloth'], P['fur_orange'], size=1.05, legs=P['fur_orange'])
    m.box(-1.8, 12, 5.5, 3.6, 1.5, 1.2, P['leaf'] if seed % 2 == 0 else P['white'])


@recipe('swan', G_SEA, 'Cygne', K)
def swan(m, seed=0):
    c = P['white']
    m.box(-4, 1, -7, 8, 6, 13, c, jitter=.04); m.box(-3.4, .6, -9.5, 6.8, 3, 4, c); m.box(-4.4, 4, -6, 1.8, 4, 8, light(c, .95)); m.box(2.6, 4, -6, 1.8, 4, 8, light(c, .95))
    m.box(-1.2, 5, 4, 2.4, 6, 2.4, c); m.box(-1.2, 10, 5, 2.4, 6, 2.4, c); m.box(-1.8, 15, 5.6, 3.6, 3.6, 4.6, c)
    m.box(-1, 15.8, 10, 2, 1.4, 3.2, P['fur_orange']); m.box(-.7, 16.8, 10, 1.4, .8, 1, P['black']); eyes(m, 0, 17.4, 10, 1.3, P['black'], .8)
    m.box(-6, 0, -8, 12, .6, 18, P['water'])


@recipe('penguin', G_SEA, 'Pingouin', K)
def penguin(m, seed=0):
    m.box(-3, 0, -2.6, 2.6, 1, 4.6, P['fur_orange']); m.box(.4, 0, -2.6, 2.6, 1, 4.6, P['fur_orange'])
    m.box(-3.6, 1, -3.4, 7.2, 12, 6.8, P['black'], jitter=.04); m.box(-2.6, 1.4, -.2, 5.2, 9, 3.6, P['white']); m.box(-3, 12.6, -3, 6, 4.6, 6, P['black'])
    m.box(-.9, 14.4, 3, 1.8, 1.4, 2.4, P['fur_orange']); eyes(m, 0, 15.2, 3, 1.8, P['white'], 1.0); eyes(m, 0, 15.4, 3.4, 1.8, P['black'], .6)
    for sg in (-1, 1): m.box(sg * 3.6 - (0 if sg > 0 else 1.2), 3.6, -2.4, 1.2, 7, 4.4, dark(P['black'], 1.3))
    m.box(-1.6, 12.6, 2.6, 3.2, 1.4, 1, P['cloth_yellow'])


@recipe('bat', G_SEA, 'Chauve-souris', K, variants=2)
def bat(m, seed=0):
    c = pick(seed, P['fur_black'], dark(P['fur_brown'], .7)); y0 = 8
    m.box(-2, y0, -2, 4, 5, 4, c, jitter=.06); m.box(-1.8, y0 + 5, -1, 3.6, 3.4, 3.4, c); m.box(-.7, y0 + 5.4, 2.4, 1.4, 1.4, .7, P['pink'])
    eyes(m, 0, y0 + 6.6, 2.2, 1.1, P['ruby'], .8)
    for sg in (-1, 1):
        m.box(sg * 1.2 - .5, y0 + 8.2, -.4, 1, 2.6, 1, c); m.box(sg * 1.5 - .5, y0 + 9, -.4, 1, 1.2, .8, P['pink'])
        for i in range(5):
            w = 3 + i * 1.6; h = 7 - i * 1.0 + (1.4 if i == 2 else 0); m.box(sg * (2 + i * 2.4) - (0 if sg > 0 else 2.4), y0 + 1.5 + (i * .6) - (h - 3), -1 - i * .5, 2.4, h, .8, dark(c, .9) if i % 2 else c, jitter=.05)
    m.box(-.6, y0 - 2, -1, 1.2, 2.4, 1.2, c)


@recipe('bee', G_SEA, 'Abeille', K)
def bee(m, seed=0):
    y0 = 5
    for i in range(5): m.box(-2.4 + (i == 4) * .5, y0 + .4, -5 + i * 2, 4.8 - (i == 4), 4.4, 2, P['cloth_yellow'] if i % 2 == 0 else P['black'], jitter=.04)
    m.box(-2.2, y0 + .6, 4.6, 4.4, 4, 3, P['black']); eyes(m, 0, y0 + 2.4, 7.4, 1.5, P['white'], 1.4); m.box(-.5, y0 - .2, -6.2, 1, 1, 2, P['black']); m.box(-1.5, y0 + 4.2, 6.6, .6, 2.2, .6, P['black']); m.box(.9, y0 + 4.2, 6.6, .6, 2.2, .6, P['black'])
    for sg in (-1, 1): m.box(sg * 3.6 - (0 if sg > 0 else 3.4), y0 + 4.4, -2, 3.4, .5, 5, light(P['glass'], 1.2)); m.box(sg * 2.2 - .4, y0 - 2, 0, .8, 2.4, .8, P['black']); m.box(sg * 2.2 - .4, y0 - 2, 2.4, .8, 2.4, .8, P['black'])


@recipe('butterfly', G_SEA, 'Papillon', K, variants=3)
def butterfly(m, seed=0):
    a, b = pick(seed, (P['fur_orange'], P['black']), (P['cloth_blue'], P['white']), (P['cloth_yellow'], P['ruby'])); y0 = 4
    m.box(-.6, y0, -.6, 1.2, 8, 1.2, P['black'], jitter=.03); m.box(-1, y0 + 8, -.8, 2, 2, 1.8, P['black'])
    for sg in (-1, 1):
        m.box(sg * .5 - .3, y0 + 10, .4, .6, 3.4, .6, P['black']); m.box(sg * 1.4 - .6, y0 + 13, .4, 1.2, 1.2, .6, a)
        x0 = .6 if sg > 0 else -.6 - 6.4
        m.box(x0, y0 + 3.6, -.4, 6.4, 7.6, .7, a, jitter=.03); m.box(x0 + (0 if sg > 0 else 1.4), y0 + 6.2, -.8, 5, 4.2, .6, b, jitter=.03)      # grande aile et son motif
        m.box(sg * 3 - 1.8 if sg > 0 else -4.8, y0 + 7.4, -1.2, 2.2, 2.2, .6, light(a, 1.15))
        x1 = .6 if sg > 0 else -.6 - 4.6
        m.box(x1, y0 - .4, -.2, 4.6, 4.4, .7, b, jitter=.03); m.box(x1 + (0 if sg > 0 else 1.4), y0 + .4, -.6, 3.2, 2.4, .6, a, jitter=.03)       # petite aile
    m.box(-.5, y0 - 1.4, -.5, 1, 1.6, 1, P['black'])


@recipe('fish', G_SEA, 'Poisson', K, variants=3)
def fish(m, seed=0):
    col, fin, stripe = pick(seed, (P['fur_orange'], P['ruby'], P['white']), (P['leaf'], P['leaf_dark'], P['cloth_yellow']), (P['cloth_yellow'], P['cloth_blue'], P['black']))
    y0 = 3
    m.box(-2, y0, -6, 4, 7, 12, col, jitter=.05); m.box(-1.6, y0 + .4, 5.6, 3.2, 5.4, 2.6, col, jitter=.04); m.box(-1.6, y0 + 1.4, -8.2, 3.2, 4.4, 2.6, col)
    for i in range(3): m.box(-2.1, y0 + .2, -4 + i * 4, 4.2, 7.2, 1.2, stripe if seed else P['white']) if seed else None
    if seed == 2:
        for z in (-3, 0.5, 4): m.box(-2.1, y0, z, 4.2, 7, 1, stripe)
    m.box(-.5, y0 + 7, -4, 1, 3.6, 8, fin, jitter=.05); m.box(-.5, y0 - 1.6, -3, 1, 2.4, 5, fin); m.box(-.5, y0 + .6, -11, 1, 7.4, 3.6, fin, jitter=.05)
    for sg in (-1, 1): m.box(sg * 2 - (0 if sg > 0 else .6), y0 + 1.5, 0, .6, 2.2, 3, fin)
    eyes(m, 0, y0 + 4.6, 5.9, 1.9, P['black'], 1.2, P['white'], side=True)
    rot90(m)


@recipe('squid', G_SEA, 'Calmar', K)
def squid(m, seed=0):
    c = P['pink']; y0 = 6
    m.box(-3, y0 + 7, -2, 6, 5, 6, light(c, 1.0), jitter=.05); m.box(-2.2, y0 + 11.6, -1.4, 4.4, 5.4, 4.8, c, jitter=.05); m.box(-4.4, y0 + 13, 0, 1.4, 3, 3, dark(c, .85)); m.box(3, y0 + 13, 0, 1.4, 3, 3, dark(c, .85))
    m.box(-3.6, y0 + 4, -2.6, 7.2, 3.6, 7.2, c, jitter=.05); eyes(m, 0, y0 + 8.4, 4, 2.6, P['black'], 1.6, P['white'])
    for i in range(8):
        a = i * math.pi / 4; x = math.cos(a) * 2.6; z = math.sin(a) * 2.6; m.box(x - .8, y0, z - .8 + 1, 1.6, 4, 1.6, dark(c, .95), jitter=.05); m.box(x * 1.2 - .7, y0 - 3, z * 1.2 - .7 + 1, 1.4, 3, 1.4, dark(c, .8))


@recipe('octopus', G_SEA, 'Poulpe', K)
def octopus(m, seed=0):
    c = P['ruby']
    m.box(-4.6, 3.6, -4.6, 9.2, 3.6, 9.2, c); m.box(-3.8, 7, -3.8, 7.6, 3, 7.6, c); m.box(-2.6, 9.8, -2.6, 5.2, 1.6, 5.2, dark(c, .9)); eyes(m, 0, 6.2, 4.7, 2.2, P['black'], 1.6, P['white'])
    for i in range(8):
        a = i * math.pi / 4 + .2
        for t in range(3): r = 3.4 + t * 3.2; m.box(math.cos(a) * r - 1.3, max(0, 3.4 - t * 1.6), math.sin(a) * r - 1.3, 2.6 - t * .5, 2.6, 2.6 - t * .5, dark(c, .9 - t * .04))


@recipe('shark', G_SEA, 'Requin', K)
def shark(m, seed=0):
    c, b = P['fur_grey'], P['white']; y0 = 4
    m.box(-4, y0, -12, 8, 8, 22, c, jitter=.04); m.box(-3.4, y0 - .4, -11, 6.8, 3, 21, b); m.box(-2.4, y0 + 1, 10, 4.8, 5.4, 6, c); m.box(-1.6, y0 + 1.6, 12, 3.2, 2.2, 5, light(c, 1.1))
    m.box(-.7, y0 + 8, -4, 1.4, 6, 7, dark(c, .8)); m.box(-.7, y0 + 8, -4, 1.4, 2, 7, c); m.box(-.7, y0 - 1.5, -13, 1.4, 3, 3, c)
    m.box(-.7, y0 + 2, -19, 1.4, 11, 3.6, dark(c, .85)); m.box(-.7, y0 - 3, -17, 1.4, 5, 3.2, dark(c, .85))
    for sg in (-1, 1): m.box(sg * 4 - (0 if sg > 0 else 5), y0 + 1, 1, 5, .9, 4, dark(c, .8)); m.box(sg * 5.6 - (0 if sg > 0 else 3), y0 + 2.2, 2, 3, .8, 1.8, dark(c, .7))
    eyes(m, 0, y0 + 5.6, 15.6, 3, P['black'], 1.1, side=True)
    for i in range(6): m.box(-2.2 + i * .8, y0 + 1.8, 16.2, .5, 1, .6, P['white'])
    for sg in (-1, 1):
        for i in range(3): m.box(sg * 4 - (0 if sg > 0 else .5), y0 + 2 + i * 1, 11.6 - i * .5, .5, .5, .6, P['black'])
    rot90(m)


@recipe('dolphin', G_SEA, 'Dauphin', K)
def dolphin(m, seed=0):
    c, b = (96, 120, 150), P['white']; y0 = 5
    m.box(-3.4, y0, -10, 6.8, 7, 18, c, jitter=.04); m.box(-3, y0 - .4, -9, 6, 2.4, 17, b); m.box(-2.6, y0 + .6, 8, 5.2, 5.4, 3, c); m.box(-1.2, y0 + .8, 11, 2.4, 2.2, 5, light(c, 1.1)); m.box(-1.2, y0 + .8, 11, 2.4, .8, 5, b)
    m.box(-.6, y0 + 7, -3, 1.2, 4, 5, dark(c, .85)); m.box(-.7, y0 + 1.2, -14, 1.4, 3, 4, dark(c, .85)); m.box(-4.6, y0 + 1.8, -17, 4.6, .8, 2.6, dark(c, .85)); m.box(0, y0 + 1.8, -17, 4.6, .8, 2.6, dark(c, .85))
    for sg in (-1, 1): m.box(sg * 3.4 - (0 if sg > 0 else 3.4), y0 + 1.2, 3, 3.4, .8, 3, dark(c, .8))
    eyes(m, 0, y0 + 4.2, 8.6, 2.5, P['black'], 1.0, side=True)
    rot90(m)


@recipe('crab', G_SEA, 'Crabe', K, variants=2)
def crab(m, seed=0):
    c = pick(seed, P['fur_orange'], P['ruby']); l = light(c, 1.15)
    m.box(-6, 1.6, -4, 12, 4, 8, c, jitter=.06); m.box(-5, 5.4, -3, 10, .8, 6, l, jitter=.06)
    for sg in (-1, 1):
        for i in range(3):
            m.box(sg * 6 - (0 if sg > 0 else 3.4), 3, -3 + i * 2.6, 3.4, 1, 1.2, dark(c, .85)); m.box(sg * (8.6 + i * .4) - (0 if sg > 0 else 1.2), 0, -3 + i * 2.6, 1.2, 3.6, 1.2, dark(c, .85))
        m.box(sg * 5 - (0 if sg > 0 else 3), 3.2, 4, 3, 1.6, 6, c); m.box(sg * 5.6 - (0 if sg > 0 else 4.6), 2.4, 9, 4.6, 3, 3.4, l, jitter=.05); m.box(sg * 6.6 - (0 if sg > 0 else 2), 2.4, 12, 2.2, 3, 2.2, l); m.box(sg * 5.4 - (0 if sg > 0 else 1.4), 2.8, 12, 1.4, .9, 3, dark(c, .6))
        m.box(sg * 2 - .5, 6.2, 3.4, 1, 2.6, 1, c); m.box(sg * 2 - .8, 8.4, 3.2, 1.6, 1.6, 1.6, P['white']); m.box(sg * 2 - .4, 8.8, 4.6, .8, .8, .5, P['black'])


# ====================================================================== MONSTRES
def humanoid(m, skin, shirt, pants, k=1., shoes=None, hair=None, head=8, tw=8, th=12, legh=12, arms=(3, 11), face=True, eyec=None, hunch=0., sleeves=None, y0=0.):
    """un humanoïde de 32 voxels de haut (2 m) à l'échelle k : jambes, torse, bras, tête ; la face avant regarde vers +z. Rend un `Sc` pour ajouter des détails"""
    s = Sc(m, k); shoes = shoes or dark(pants, .6); sleeves = sleeves or shirt
    for sg in (-1, 1):
        s.box(sg * tw / 4 - 2 + (0 if sg < 0 else 0), y0, -2, 4 - .2, legh, 4, pants, jitter=.05); s.box(sg * tw / 4 - 2.2, y0, -2.4, 4.4, 2.2, 4.8, shoes)
    s.box(-tw / 2, y0 + legh - .2, -2 - hunch * .3, tw, th, 4 + hunch * .3, shirt, jitter=.06)
    aw, ah = arms
    for sg in (-1, 1):
        s.box(sg * (tw / 2 + aw / 2) - aw / 2, y0 + legh + th - ah - .2, -aw / 2 + hunch * .3, aw, ah, aw, sleeves, jitter=.05); s.box(sg * (tw / 2 + aw / 2) - aw / 2 + .1, y0 + legh + th - ah - .2, -aw / 2 + hunch * .3, aw - .2, 2.6, aw, skin)
    hy = y0 + legh + th - .2
    s.box(-head / 2, hy + hunch * .3, -head / 2 + hunch * .8, head, head, head, skin, jitter=.05)
    if hair: s.box(-head / 2 - .2, hy + head - 2 + hunch * .3, -head / 2 - .2 + hunch * .8, head + .4, 2.4, head + .4, hair, jitter=.08); s.box(-head / 2 - .2, hy + head - 5 + hunch * .3, -head / 2 - .2 + hunch * .8, head + .4, 5, 2, hair, jitter=.08)
    if face:
        zf = head / 2 + hunch * .8
        for sg in (-1, 1): s.box(sg * head / 4 - .9, hy + head * .55 + hunch * .3, zf - .2, 1.8, 1.4, 1, P['white']); s.box(sg * head / 4 - .5 + (.2 if sg < 0 else 0), hy + head * .55 + .2 + hunch * .3, zf + .1, 1.1, 1.1, 1, eyec or P['black'])
        s.box(-1.4, hy + head * .22 + hunch * .3, zf - .2, 2.8, .9, 1, dark(skin, .4))
    s.hy = hy; s.head = head; s.zf = head / 2 + hunch * .8
    return s


@recipe('wanderer_rags', G_MON, 'Rôdeur en haillons', K, variants=2)
def wanderer_rags(m, seed=0):
    skin = pick(seed, (150, 168, 130), (186, 176, 160)); rag = pick(seed, (70, 66, 56), (88, 74, 60))
    s = humanoid(m, skin, rag, dark(rag, .75), hair=P['black'], hunch=2.4, eyec=P['ruby'], arms=(2.6, 13), sleeves=dark(rag, .9))
    for i in range(7): s.box(-4 + i * 1.3, 17, -2.4, 1, 2.6 + (i % 3) * 1.6, 4.8, rag, jitter=.14)
    for sg in (-1, 1): s.box(sg * 5.2 - 1.2, 11, -1.6, 2.4, 2, 3.2, dark(skin, .7))
    s.box(-4.2, 28, -3.6, 8.4, 1.6, 3.6, dark(rag, .9), jitter=.1)


@recipe('skeleton_archer', G_MON, 'Squelette archer', K)
def skeleton_archer(m, seed=0):
    b = P['bone']; db = dark(b, .7)
    for sg in (-1, 1): m.box(sg * 2 - .8, 0, -.8, 1.6, 14, 1.6, b); m.box(sg * 2 - 1.6, 0, -1.6, 3.2, 1.4, 3.6, db)
    m.box(-3, 13, -1.4, 6, 2, 2.8, b)
    for i in range(4): m.box(-3.6, 15 + i * 2.1, -1.6, 7.2, 1.2, 3.2, b, jitter=.04)
    m.box(-.8, 14, -1.2, 1.6, 9, 1.6, db)
    for sg in (-1, 1): m.box(sg * 5 - .8, 14, -.8, 1.6, 9, 1.6, b); m.box(sg * 5 - .8, 14, .4, 1.6, 1.6, 4, b)
    m.box(-3.6, 23, -3.4, 7.2, 6.8, 6.8, b, jitter=.03); m.box(-2.4, 22, -2, 4.8, 1.4, 4, db)
    for sg in (-1, 1): m.box(sg * 1.8 - 1, 25.8, 3.2, 2, 2.2, .8, P['black']); m.box(sg * 1.8 - .4, 26.2, 3.5, .8, .8, .6, P['ruby'])
    m.box(-.8, 24.4, 3.2, 1.6, 1.4, .8, P['black']); m.box(-2.2, 22.8, 3.2, 4.4, .8, .7, P['black'])
    m.box(-9.2, 16, 6.4, 1.4, 7, 1.6, P['wood_dark'])                                                 # arc : poignée, branches qui se courbent vers l'avant, corde
    for i, (dy, dz) in enumerate(((0, .4), (3.4, 1.4), (6.2, 2.8), (8.4, 4.4))):
        m.box(-9.1, 23 + dy - 1, 6.4 + dz, 1.2, 3.6, 1.5, P['wood'], jitter=.05); m.box(-9.1, 16 - dy - 2.6, 6.4 + dz, 1.2, 3.6, 1.5, P['wood'], jitter=.05)
    m.box(-8.9, 5.8, 6.2, .4, 30, .4, P['cloth']); m.box(-8.9, 18.6, 7, .5, .5, 11, P['wood_light'])
    m.box(4, 14, -4.4, 3.6, 7, 2, P['wood']); m.box(4.4, 14, -4.8, .6, 7, .6, P['cloth_red']); m.box(5.4, 14, -4.8, .6, 7, .6, P['cloth_red'])


@recipe('slime', G_MON, 'Gelée', K, variants=3)
def slime(m, seed=0):
    c = pick(seed, P['slime'], P['gem'], P['pink']); core = dark(c, .45); s = 14 if seed != 2 else 11
    t = .9
    for x in (0, s - t):
        for z in (0, s - t): m.box(x - s / 2, 0, z - s / 2, t, s, t, light(c, 1.1), emis=.15)
    for y in (0, s - t):
        for z in (0, s - t): m.box(-s / 2, y, z - s / 2, s, t, t, light(c, 1.1), emis=.15)
        for x in (0, s - t): m.box(x - s / 2, y, -s / 2, t, t, s, light(c, 1.1), emis=.15)
    m.box(-s / 2 + 1, 0, -s / 2 + 1, s - 2, 1.6, s - 2, dark(c, .9), jitter=.05)
    for i in range(14): m.box(m.rng.uniform(-s / 2 + 1.5, s / 2 - 3), m.rng.uniform(2, s - 3), m.rng.uniform(-s / 2 + 1.5, s / 2 - 3), 1.4, 1.4, 1.4, light(c, 1.3), emis=.2)
    m.box(-3, 3, -3, 6, 6, 6, core, jitter=.05); eyes(m, 0, 7, s / 2 - .2, 2.4, P['black'], 1.6, P['white']); m.box(-1.5, 3.8, s / 2 - .2, 3, .9, 1, P['black'])
    for sg in (-1, 1): m.box(sg * (s / 2 - .5) - .3, 0, 0, .6, 1.4, 3, c)


@recipe('ghost', G_MON, 'Fantôme', K, variants=2)
def ghost(m, seed=0):
    c = pick(seed, (214, 224, 236), (190, 230, 214)); y0 = 3
    for i in range(10):
        w = 9 + (i > 6) * -2 * (i - 6) * .4 + (i < 3) * 1.4; zd = 7 + (i < 3) * 1.4 - (i > 6) * .8; y = y0 + i * 2.2
        m.box(-w / 2, y, -zd / 2, w, 2.4, zd, c, jitter=.02, emis=.25)
    for i in range(6): m.box(-5.5 + i * 2.1, y0 - 2 + (i % 2) * 1.8, -3, 2.1, 3.4 + (i % 2) * -1.6, 6, c, emis=.25)
    for sg in (-1, 1): m.box(sg * 6.4 - (0 if sg > 0 else 3), y0 + 9, -1, 3, 2, 2.4, c, emis=.2); m.box(sg * 8.2 - (0 if sg > 0 else 2.4), y0 + 6, -1, 2.4, 3.4, 2.4, c, emis=.2)
    for sg in (-1, 1): m.box(sg * 2.2 - 1, y0 + 14, 3.4, 2, 3, 1, P['black']); m.box(sg * 2.2 - .6, y0 + 12.4, 3.4, 1.2, 1.4, 1, dark(c, .3))
    m.box(-1.3, y0 + 10, 3.4, 2.6, 2.2, 1, P['black']); m.light(0, y0 + 10, 4, c, .6, 3)


@recipe('stone_golem', G_MON, 'Golem de pierre', K, variants=2)
def stone_golem(m, seed=0):
    c = pick(seed, P['stone'], dark(P['stone'], .8)); mo = P['leaf_dark']
    for sg in (-1, 1): m.box(sg * 5 - 3.5, 0, -3.5, 7, 12, 7, c, jitter=.1); m.box(sg * 5 - 3.8, 0, -3.8, 7.6, 2, 7.6, dark(c, .75))
    m.box(-9, 12, -5, 18, 14, 10, c, jitter=.1); m.box(-6, 24, -6, 12, 5, 11, light(c, 1.1), jitter=.1)
    for sg in (-1, 1): m.box(sg * 12.4 - 3.5, 8, -3.5, 7, 20, 7, c, jitter=.1); m.box(sg * 12.4 - 4.5, 3, -4.5, 9, 8, 9, dark(c, .85), jitter=.1)
    m.box(-4, 28, -4, 8, 7, 8, c, jitter=.08); m.box(-1, 31, 4, 2, 3, 2, dark(c, .8))
    for sg in (-1, 1): m.box(sg * 2 - 1, 32, 4, 2, 1.6, 1, P['black']); m.emit(sg * 2 - .6, 32.2, 4.4, 1.2, 1, .8, P['ruby'] if seed else P['gem'], 1.6)
    for i in range(9): m.box(m.rng.randint(-9, 6), m.rng.randint(12, 26), 4.8, m.rng.randint(2, 4), m.rng.randint(1, 3), .8, mo, jitter=.1)
    m.box(-9, 26, -5, 6, 2, 10, mo, jitter=.12)


@recipe('iron_golem', G_MON, 'Golem de fer', K)
def iron_golem(m, seed=0):
    c, d = P['iron'], P['iron_dark']
    for sg in (-1, 1): m.box(sg * 4.6 - 3, 0, -3, 6, 12, 6, d, jitter=.04); m.box(sg * 4.6 - 3.4, 0, -3.6, 6.8, 2, 7.6, dark(d, .7))
    m.box(-8, 12, -5, 16, 12, 10, c, jitter=.04); m.box(-6, 20, 4.8, 12, 3, .8, d); m.box(-3, 12, 4.8, 6, 6, .8, d)
    for x in (-6, -2, 2): m.box(x, 13, 5, 3, 7, .8, P['copper'], jitter=.1)
    for sg in (-1, 1): m.box(sg * 11 - 2.5, 7, -2.5, 5, 18, 5, d, jitter=.04); m.box(sg * 11 - 3.5, 3, -3.5, 7, 6, 7, c, jitter=.04); m.box(sg * 8.6 - 2, 22, -3, 4, 3, 6, c)
    m.box(-4.4, 24, -4.4, 8.8, 7, 8.8, c, jitter=.04); m.box(-1.2, 27, 4, 2.4, 4, 2.4, d)
    for sg in (-1, 1): m.box(sg * 2.4 - 1.2, 28.6, 4.2, 2.4, 1.6, .8, P['black']); m.emit(sg * 2.4 - .6, 28.8, 4.6, 1.2, 1.2, .7, P['cloth_yellow'], 1.8)
    m.box(-4.8, 30.6, -4.8, 9.6, 1.4, 9.6, d)
    for i in range(6): m.box(-6 + i * 2.2, 14 + (i % 2) * 5, -5.8, 1.2, 3, .8, P['leaf_dark'], jitter=.1)


@recipe('witch', G_MON, 'Sorcière', K, variants=2)
def witch(m, seed=0):
    skin = pick(seed, (140, 170, 110), (220, 190, 160)); robe = pick(seed, (70, 40, 90), (40, 40, 50)); hat = dark(robe, .8)
    s = humanoid(m, skin, robe, dark(robe, .8), shoes=P['black'], hair=pick(seed, (60, 80, 50), P['fur_grey']), arms=(3, 11), sleeves=robe)
    s.box(-5, 8, -3.4, 10, 12, 7, robe, jitter=.05)                                  # robe longue
    s.box(-6.4, 28.6, -6.4, 12.8, 1.4, 12.8, hat, jitter=.04)
    for i in range(6): s.box(-4 + i * .3, 29.8 + i * 2.8, -4 + i * .3 - (i > 3) * .6, 8 - i * 1.3, 2.8, 8 - i * 1.3, hat, jitter=.04)
    s.box(-4.6, 30, -4.6, 9.2, 1.2, 9.2, P['cloth_yellow']); s.box(-.8, s.hy + 8 - .5, s.zf, 1.6, 2.6, 1.8, dark(skin, .85))
    s.box(14, 0, -.8, 1.4, 22, 1.4, P['wood']); s.box(12.4, 0, -1.6, 4.6, 6, 3.2, P['straw'], jitter=.1)


@recipe('imp', G_MON, 'Lutin', K, variants=2)
def imp(m, seed=0):
    skin, cloth = pick(seed, ((190, 80, 60), P['coal']), (P['leaf_light'], P['cloth_red']))
    s = humanoid(m, skin, cloth, dark(cloth, .8), k=.55, hair=None, head=9, tw=7, th=9, legh=9, arms=(2.4, 9), eyec=P['cloth_yellow'])
    for sg in (-1, 1): s.box(sg * (4.5 + 2.8) - (0 if sg > 0 else 3), s.hy + 4, -.8, 3, 2.4, 1.2, skin); s.box(sg * 3.4 - .8, s.hy + 9, -1, 1.6, 4, 1.6, dark(skin, .7)); s.box(sg * 3.4 - .5, s.hy + 12.6, -1, 1, 2, 1, P['bone'])
    s.box(-.7, 9, -4.2, 1.4, 1.4, 6, skin); s.box(-1.6, 9, -9, 3.2, 3.2, 3.2, dark(skin, .8))
    s.box(-2.6, s.hy + 3, s.zf, 5.2, 1.2, 1, P['black'])
    for i in range(3): s.box(-1.2 + i * .9, s.hy + 3.4, s.zf, .4, 1, .6, P['white'])


@recipe('ogre', G_MON, 'Ogre', K, variants=2)
def ogre(m, seed=0):
    skin = pick(seed, P['leaf_light'], P['skin_dark']); cloth = P['cloth_brown']
    s = humanoid(m, skin, cloth, dark(cloth, .8), k=1.35, hair=P['black'], head=8, tw=10, th=12, legh=11, arms=(4, 12), sleeves=skin, eyec=P['ruby'], hunch=2)
    s.box(-5.6, 12, -3.4, 11.2, 4, 6.8, P['wood'], jitter=.06); s.box(-2.4, s.hy + 1, s.zf, 4.8, 2.4, 1.4, dark(skin, .8))
    for sg in (-1, 1): s.box(sg * 2.2 - .7, s.hy + 1.2, s.zf + .6, 1.4, 2.4, 1.2, P['bone'])
    s.box(11.5, 2, 1, 3, 26, 3, P['wood'], jitter=.05); s.box(10.5, 22, .4, 5, 8, 4.4, dark(P['wood'], .8), jitter=.05)
    for i in range(4): s.box(13.2, 24 + (i % 2) * 3, .6 + i * .6, 1.2, 1.2, 1.2, P['iron'])


@recipe('wraith', G_MON, 'Spectre à capuche', K)
def wraith(m, seed=0):
    c = (28, 28, 40); y0 = 4
    for i in range(10): w = 9 + (i < 3) * 2 - (i > 8) * 1.4; m.box(-w / 2, y0 + i * 2.4, -3.6, w, 2.6, 7.2, c, jitter=.04)
    for i in range(7): m.box(-5.6 + i * 1.6, y0 - 2 + (i % 3) * 1.4, -3, 1.6, 3.6 - (i % 3) * 1.2, 6, c, jitter=.08)
    m.box(-4.6, y0 + 22, -4.4, 9.2, 8, 8.8, c, jitter=.03); m.box(-5, y0 + 27, -2, 10, 3.6, 5, dark(c, .8)); m.box(-3.4, y0 + 23.6, 3.4, 6.8, 5.2, 1.4, P['black'])
    for sg in (-1, 1): m.emit(sg * 1.6 - .7, y0 + 25.4, 4.2, 1.4, 1.6, .8, P['gem'], 2.2)
    for sg in (-1, 1): m.box(sg * 7 - (0 if sg > 0 else 2.6), y0 + 12, -.8, 2.6, 8, 3.6, dark(c, 1.1), jitter=.05); m.box(sg * 8 - (0 if sg > 0 else 1.4), y0 + 8, 1.4, 1.4, 5, 1.4, P['bone'])
    m.light(0, y0 + 24, 6, P['gem'], .5, 3)


@recipe('mushroom_man', G_MON, 'Homme-champignon', K, variants=3)
def mushroom_man(m, seed=0):
    cap, spot = pick(seed, (P['ruby'], P['white']), (P['cloth_brown'], P['cloth']), (P['cloth_blue'], P['gem']))
    for sg in (-1, 1): m.box(sg * 2.2 - 1.5, 0, -1.6, 3, 7, 3.2, P['cloth']); m.box(sg * 2.2 - 1.7, 0, -2, 3.4, 1.6, 4.4, dark(P['cloth'], .7))
    m.box(-4, 6, -3.2, 8, 10, 6.4, P['cloth']); m.box(-4.2, 6, -3.4, 8.4, 2, 6.8, light(P['cloth'], .85))
    for sg in (-1, 1): m.box(sg * 5.6 - (0 if sg > 0 else 2), 8, -1.2, 2, 7, 2.4, P['cloth']); m.box(sg * 5.6 - (0 if sg > 0 else 2.2), 7.2, -1.4, 2.4, 1.8, 2.8, dark(P['cloth'], .85))
    m.box(-8.6, 14.6, -8.6, 17.2, 1.2, 17.2, dark(P['cloth'], .72))
    tiers = ((20, 2.4), (17.6, 2.2), (14, 2.2), (9.6, 2)); y = 15.6
    for w, h in tiers: m.box(-w / 2, y, -w / 2, w, h, w, cap); y += h
    for x, z in ((-6, 2), (5, -4), (-2, -6), (4, 4), (-7, -3)): m.box(x - 1.3, 17.2, z - 1.3, 2.6, 1.3, 2.6, spot)
    m.box(-2, 22.2, -2, 4, 1.2, 4, spot)
    eyes(m, 0, 10.6, 3.2, 1.8, P['black'], 1.6, P['white']); m.box(-1.4, 8.4, 3.2, 2.8, .9, .8, P['black'])


@recipe('gargoyle', G_MON, 'Gargouille', K, variants=2)
def gargoyle(m, seed=0):
    c = pick(seed, P['stone_dark'], dark(P['cobble'], .8)); l = light(c, 1.2)
    for sg in (-1, 1): m.box(sg * 4.4 - 2, 0, -2, 4, 9, 6, c, jitter=.08); m.box(sg * 4.4 - 2.4, 0, 2, 4.8, 2, 4, dark(c, .8))
    m.box(-6, 8, -4, 12, 11, 8, c, jitter=.08); m.box(-4.4, 9, 3.6, 8.8, 7, 1, l)
    for sg in (-1, 1): m.box(sg * 7.4 - 1.8, 12, -1, 3.6, 8, 4, c, jitter=.08); m.box(sg * 7.4 - 2, 8, 2.4, 4, 4, 4, dark(c, .85))
    m.box(-4.6, 18, -2, 9.2, 8, 8, c, jitter=.06); m.box(-3.4, 18.4, 5.8, 6.8, 4, 2.6, l)
    for sg in (-1, 1): m.box(sg * 3.4 - .8, 25.6, 1.6, 1.6, 4.6, 1.6, P['bone']); m.box(sg * 2.2 - 1, 22.6, 6.4, 2, 1.8, .8, P['black']); m.emit(sg * 2.2 - .5, 22.9, 6.8, 1, 1, .7, P['lava'], 1.8)
    m.box(-2.4, 18.4, 7.8, 4.8, 1, .8, P['black'])
    for sg in (-1, 1):
        for i in range(5): h = 12 - i * 1.6; m.box(sg * (6 + i * 3.2) - (0 if sg > 0 else 3), 15 + i * 1.8 - (h - 6) * .6, -3.6 - i * .4, 3, h, 1, dark(c, .9) if i % 2 else c, jitter=.08)
    m.box(-1.2, 8, -8, 2.4, 2.4, 5, c)


@recipe('drakeling', G_MON, 'Dragonnet', K, variants=3)
def drakeling(m, seed=0):
    c, b = pick(seed, (P['leaf'], P['cloth_yellow']), (P['ruby'], P['fur_orange']), (P['cloth_blue'], P['gem']))
    for sg in (-1, 1): m.box(sg * 3.4 - 1.6, 0, -1.8, 3.2, 8, 3.6, dark(c, .85), jitter=.05); m.box(sg * 3.4 - 1.8, 0, 1.2, 3.6, 1.4, 2.6, P['black'])
    m.box(-4, 7, -6, 8, 8, 12, c, jitter=.07); m.box(-3, 7.6, -5, 6, 3, 10.4, b)
    for i in range(6): m.box(-.8, 15 + (i % 2) * .6, -5 + i * 2, 1.6, 2.4, 1.4, dark(c, .65))
    m.box(-2.4, 12, 5, 4.8, 6, 4, c, jitter=.05); m.box(-3.2, 17, 5.4, 6.4, 5.6, 6.4, c, jitter=.05); m.box(-2.4, 17, 11.6, 4.8, 3.4, 3.2, light(c, 1.1)); eyes(m, 0, 20.2, 11.8, 2.6, P['black'], 1.4, P['cloth_yellow'])
    for sg in (-1, 1): m.box(sg * 1.2 - .5, 17.6, 14.4, 1, .8, .6, P['black']); m.box(sg * 2.6 - .8, 22.6, 6.4, 1.6, 4, 1.6, P['bone']); m.box(sg * 2.6 - .8, 25, 5.2, 1.6, 2, 1.6, P['bone'])
    for i in range(5): m.box(-2 + i * .2, 5 + i * .2, -7.6 - i * 2.4, 4 - i * .6, 4 - i * .6, 2.6, c, jitter=.06)
    m.box(-.4, 5, -20, .8, 2.4, 2, dark(c, .6))
    for sg in (-1, 1):
        for i in range(4): hh = 10 - i * 1.6; m.box(sg * (4 + i * 2.8) - (0 if sg > 0 else 2.6), 13 + i * 1.4 - (hh - 6) * .4, -3 - i * .3, 2.6, hh, .8, b if i % 2 else dark(c, .85), jitter=.05)


@recipe('werewolf', G_MON, 'Loup-garou', K, variants=2)
def werewolf(m, seed=0):
    fur = pick(seed, P['fur_grey'], dark(P['fur_brown'], .7)); bellyc = light(fur, 1.3)
    for sg in (-1, 1): m.box(sg * 4.4 - 2.4, 0, -3, 4.8, 15, 5.4, fur, jitter=.08); m.box(sg * 4.4 - 2.6, 0, -2.4, 5.2, 2.2, 7.4, P['black'])
    m.box(-7, 13, -3.6, 14, 14, 8.6, fur, jitter=.1); m.box(-3.4, 12, 3.6, 6.8, 11, 1, bellyc, jitter=.08)
    for sg in (-1, 1): m.box(sg * 9 - 2.2, 4, 0, 4.4, 24, 4.4, fur, jitter=.1); m.box(sg * 9 - 2.6, 0, 0, 5.2, 5, 5, dark(fur, .8)); [m.box(sg * 9 - 1.8 + k * 1.3 - 1.3, 0, 4.6, .8, .8, 1.6, P['bone']) for k in range(3)]
    m.box(-4.6, 26, 1, 9.2, 9.6, 8.4, fur, jitter=.07); m.box(-2.8, 26.4, 8.8, 5.6, 4.8, 5.6, light(fur, 1.1)); m.box(-1, 29.6, 14, 2, 1.8, 1, P['black']); m.box(-2, 26.2, 9, 4, 1.4, 4.6, P['white'])
    for sg in (-1, 1): m.box(sg * 3.4 - 1, 34, 3, 2.4, 4.4, 1.8, fur); eyes(m, 0, 31.4, 9.2, 2.3, P['cloth_yellow'], 1.5, side=False)
    m.box(-2, 12, -9, 4, 3.6, 7, dark(fur, .8), jitter=.1); m.box(-6, 24, -2, 12, 3, 6, light(fur, 1.1), jitter=.12)


@recipe('mummy', G_MON, 'Momie', K, variants=2)
def mummy(m, seed=0):
    w, d = P['cloth'], dark(P['cloth'], .72)
    def wrap(x, y, z, bw, bh, bd):
        n = int(bh // 2.2)
        for i in range(n + 1): m.box(x, y + i * 2.2 - (i == n) * .2, z, bw, 2.2, bd, w if (i + seed) % 2 else d, jitter=.05)
    for sg in (-1, 1): wrap(sg * 4 - 2, 0, -2, 4, 12, 4)
    wrap(-4, 12, -2, 8, 12, 4.4)
    m.box(4.2, 18, -2, 4, .8, 4.6, d); m.box(-8, 17, -2.2, 4, 2, 4.6, w)
    for sg in (-1, 1): wrap(sg * 6.6 - 1.5, 11, -1.4, 3, 11, 3)
    m.box(-4, 24, -4, 8, 8, 8, w, jitter=.04)
    for i in range(4): m.box(-4.2, 24.6 + i * 1.8, -4.2, 8.4, 1, 8.4, d if i % 2 else w)
    m.box(-3.2, 28, 3.6, 6.4, 1.6, .8, P['black'])
    for sg in (-1, 1): m.emit(sg * 1.8 - .8, 28.2, 4, 1.6, 1.2, .8, P['cloth_yellow'], 1.6)
    m.box(-5, 21, 4.8, 3, .8, .8, d); m.box(1, 20, 4.8, 4, .8, .8, w)
    m.box(6.4, 11.6, -6, 1.6, 1.2, 8, w)


@recipe('scarecrow', G_MON, 'Épouvantail', K, variants=2)
def scarecrow(m, seed=0):
    straw, cloth, cl2 = P['straw'], pick(seed, P['cloth_blue'], P['cloth_red']), P['cloth_brown']
    m.box(-1, 0, -1, 2, 36, 2, P['wood'], jitter=.05); m.box(-12, 21, -1, 24, 2, 2, P['wood'], jitter=.05); m.box(-4.4, 0, -3, 8.8, 3, 6, P['wood'], jitter=.05)
    m.box(-4.4, 12, -2.6, 8.8, 14, 5.2, cloth, jitter=.06)
    for i in range(7): m.box(-4 + i * 1.3, 11 - m.rng.random() * 2, -2.6, 1, 2 + m.rng.random() * 2, 5.2, cloth, jitter=.12)
    for sg in (-1, 1): m.box(sg * 8 - (0 if sg > 0 else 7), 19.4, -2, 7, 4.4, 4, cloth, jitter=.06); [m.box(sg * (12 + k) - (0 if sg > 0 else .8), 19 - k * .5, -.6, .8, 3 + k, .8, straw, jitter=.1) for k in range(4)]
    m.box(-4.6, 26, -4.4, 9.2, 8, 8.8, P['cloth'], jitter=.05); m.box(-3.4, 26.4, 4.2, 6.8, 6.8, .6, light(P['cloth'], 1.05))
    for sg in (-1, 1): m.box(sg * 2 - 1.2, 30.2, 4.5, 2.4, 2.4, .8, P['black']); m.box(sg * 2 - .4, 30.2 + .4, 5, .8, .8, .4, P['white'])
    for i in range(6): m.box(-2.6 + i * .9, 27.4 + (i % 2) * .4, 4.5, .5, 1.6, .7, P['black'])
    m.box(-7.4, 34, -7, 14.8, 1.4, 14, cl2, jitter=.05); m.box(-4.6, 35, -4.6, 9.2, 5, 9.2, cl2, jitter=.05); m.box(-4.8, 35.2, -4.8, 9.6, 1.4, 9.6, P['ruby'])
    for k in range(6): m.box(-5 + k * 1.7, 24 + m.rng.random(), -3.8, 1, 2.6, 1, straw, jitter=.1)


@recipe('pumpkin_creature', G_MON, 'Citrouille vivante', K, variants=2)
def pumpkin_creature(m, seed=0):
    o = pick(seed, P['fur_orange'], P['straw'])
    for sg in (-1, 1): m.box(sg * 3 - 1.3, 0, -1.3, 2.6, 8, 2.6, P['leaf_dark']); m.box(sg * 3 - 1.6, 0, -1.6, 3.2, 1.4, 3.8, P['bark'])
    m.box(-3.6, 7, -2, 7.2, 8, 4, P['bark'])
    for sg in (-1, 1): m.box(sg * 5.2 - (0 if sg > 0 else 1.6), 9, -1, 1.6, 7, 2, P['leaf_dark'])
    m.box(-9, 15.4, -8.4, 18, 13, 16.8, o); m.box(-7, 14, -6.6, 14, 1.6, 13.2, dark(o, .85)); m.box(-7, 28.2, -6.6, 14, 1.6, 13.2, dark(o, .85))
    for x in (-6, -3, 0, 3, 6): m.box(x - .4, 15.4, 8.3, .8, 13, .5, dark(o, .72))
    m.box(-1.6, 29.6, -1.6, 3.2, 3, 3.2, P['leaf_dark']); m.box(-.4, 31.6, -1.2, 1.6, 2.4, 1.2, P['leaf'])
    for sg in (-1, 1): m.box(sg * 3.4 - 1.5, 23.2, 7.6, 3, 3, 1.4, P['black']); m.emit(sg * 3.4 - 1, 23.5, 8.4, 2, 2, .7, P['cloth_yellow'], 1.8)
    m.box(-4.4, 17.8, 7.8, 8.8, 2, 1.4, P['black'])
    for i in range(4): m.emit(-3.4 + i * 2.2, 18, 8.4, 1.6, 1.4, .7, P['cloth_yellow'], 1.6)
    m.light(0, 22, 10, P['fur_orange'], .8, 3.5)


@recipe('giant_spider', G_MON, 'Araignée géante', K)
def giant_spider(m, seed=0):
    c = dark(P['black'], 1.5); s = Sc(m, 2.4)
    s.box(-4.6, 3.4, -9.4, 9.2, 4.4, 9.4, c); s.box(-3.6, 7.6, -8.4, 7.2, 1.6, 7.4, dark(c, 1.15)); s.box(-3, 3.8, .2, 6, 3.6, 5.2, dark(c, 1.3))
    for i in range(5): s.box(-1 + i * .1, 9.4, -8 + i * 1.8, 2, .6, 1, P['ruby'])
    for sg in (-1, 1):
        for i, zz in enumerate((-5, -2, 1, 3.6)):
            f = 1 + (i % 2) * .18; s.box(sg * 3.6 - (0 if sg > 0 else 3.2), 6.2, zz, 3.2, 1.1, 1.1, dark(c, 1.3)); s.box(sg * (6.6 * f) - (0 if sg > 0 else 1.1), 6.2, zz, 1.1, 1.1, 1.1, dark(c, 1.3)); s.box(sg * (6.6 * f) - (0 if sg > 0 else 1.3), 0, zz + (i - 1.5) * .4, 1.3, 7.4, 1.3, dark(c, 1.3))
    for sg in (-1, 1):
        for ex, ey in ((1.6, 5.6), (.8, 6.8), (2.3, 4.4)): s.emit(sg * ex - .4, ey, 5.8, .9, .9, .6, P['ruby'], 1.8)
        s.box(sg * 1.2 - .6, 2.4, 5.4, 1.2, 3.4, 1.4, P['bone']); s.box(sg * 2.4 - .5, 1.6, 6.4, 1, 1.4, 1.6, P['black'])
    s.box(-2.4, 3, 4.6, 4.8, 4.4, 1.2, dark(c, 1.2))