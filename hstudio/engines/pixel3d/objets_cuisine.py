"""OBJETS DÉTAILLÉS, LOT A « cuisine et salle de bain » (01/11/2026), version PS1 native (PIXEL 3D).

Lot découvert tout seul par objets._load_lots (fichier `objets_<lot>.py`) ; la version VOXEL native est voxelgpu/b_objets_cuisine.py (même plan,
mêmes réglages, mêmes images : les images de ce lot sont dessinées ICI et partagées). Aucune ligne n'est écrite ailleurs.

Posés (repère : face avant vers -z, x à droite vu de face, y = 0 posé ; la clé `y` du décor soulève, `color` = couleur principale) :
  od_kettle          bouilloire : `modele` electrique (défaut) | gaz ; `allumee` (voyant, fenêtre éclairée, vapeur) ; `niveau` d'eau 0..1
  od_coffee_maker    cafetière filtre et sa verseuse : `plein` 0..1 (café dans la verseuse), `allumee`, `heure` (horloge du socle), `niveau` du réservoir
  od_toaster         grille-pain : `tartines` sorties | dedans | false ; `allumee` (fentes rougeoyantes, levier baissé)
  od_microwave       micro-ondes : porte vitrée tramée, cadran de minuterie, afficheur ; `ecran` / `heure`, `allume` (four éclairé), `ouverte`, `contenu` bol
  od_saucepan        casserole : `contenu` eau | soupe | lait | vide, `bout` (bulles + vapeur), `couvercle` (verre)
  od_frying_pan      poêle : `contenu` vide | oeuf | oeufs | bacon
  od_kitchen_knife   couteau de cuisine couché, pointe vers +x : `sang`
  od_cutting_board   planche à découper : `contenu` vide | carottes | pain | oignon, `couteau` (le couteau posé dessus)
  od_bowl            bol : `contenu` soupe | cereales | lait | riz | vide, `cuillere`, `vapeur`, `filet` (couleur du liseré)
  od_teapot          théière (bec à gauche, anse à droite) : `vapeur`, `motif` (couleur du décor peint)
  od_pill_box        boîte de médicaments lisible : `nom`, `dose`, `sous`, `patient` (étiquette de pharmacie), `posologie`, `plaquette`, `restants` (0..10)
  od_toothbrush_glass verre à dents et ses brosses : `brosses` 1..3, `dentifrice`
  od_soap            savon sur son porte-savon : `modele` pain (défaut) | pompe ; `mousse`
  od_towel           serviette pliée : `pile` 1..4, `bande` (couleur du liteau), `couleurs` (une par serviette)
  od_hair_dryer      sèche-cheveux couché, embout vers +x, poignée vers l'avant, cordon enroulé
Tenus (P(lat, haut, avant) autour de la main droite) : od_kitchen_knife (`prise` bas (défaut) | haut | avant, `sang`), od_bowl (`contenu`), od_teapot (par l'anse,
bec vers l'avant), od_pill_box (étiquette vers l'avant, posologie vers celui qui la tient).
Règles : préfixe od_, ajouts seulement, rien d'aléatoire non semé, aucune horloge. Images des faces du dessus : T.flat (sinon miroir)."""
import functools, math
import numpy as np
from PIL import Image, ImageDraw
from .r3d import B, C, M_FABRIC, M_WOODV, M_METAL, M_CARD
from . import objets as OD, objets_tex as T

rnd, rnd2, line, _g, _sh, _col = OD.rnd, OD.rnd2, OD.line, OD._g, OD._sh, OD._col
STEEL = (192, 196, 204); BLADE = (214, 218, 228); DARK = (34, 34, 38); WHITE = (238, 236, 230); CERAM = (240, 238, 232)
WATER = (120, 160, 196); SOUP = (196, 96, 40); MILK = (244, 242, 234); COFFEE = (60, 34, 18)
CONTENTS = {'eau': WATER, 'soupe': SOUP, 'lait': MILK, 'cereales': MILK, 'riz': (236, 232, 220), 'cafe': COFFEE, 'the': (150, 80, 30)}


# ================================================================== helpers
def shift(bx, dx=0., dy=0., dz=0.):
    v = np.array([dx, dy, dz], np.float32)
    for b in bx: b.lo = b.lo + v; b.hi = b.hi + v
    return bx


def disk(x, y, z, r, h, col, n=None, k=None, **kw):
    """disque plein « rond » en rangées le long de z (un cercle en escalier, comme un rond en pixels) ; y = le bas.
    La rangée de devant donne une face plate en z = -r, large de 2*sqrt(r² - (r - r/n)²) : on y pose une étiquette."""
    k = k or {}; n = n or max(4, 2 * int(round(r / .02))); out = []
    for i in range(n):
        zm = -r + 2 * r * (i + .5) / n; hw = math.sqrt(max(0., r * r - zm * zm))
        out.append(C((x, y + h / 2, z + zm), (2 * hw, h, 2 * r / n), col, **kw, **k))
    return out


def ring(x, y, z, r, r_in, h, col, k=None, **kw):
    """anneau « rond » en rangées (paroi d'un bol, d'une casserole, d'une poêle : creux pour de vrai) ; y = le bas.
    Rangées fines (de l'épaisseur de la paroi) aux deux pôles, pour que la paroi ne s'épaississe pas devant et derrière."""
    k = k or {}; out = []; t = max(.006, (r - r_in) * 1.4)
    zs = sorted(set([round(-r + i * t, 5) for i in range(int((r - r_in * .55) / t) + 1)] + [round(-r_in * .55 + i * 2 * r_in * .55 / 4, 5) for i in range(5)]))
    zs = [q for q in zs if q < -r_in * .55 - 1e-6] + [round(-r_in * .55 + i * 2 * r_in * .55 / 4, 5) for i in range(5)]
    zs = zs + [-q for q in reversed(zs) if q < -r_in * .55 - 1e-6]
    for z0, z1 in zip(zs[:-1], zs[1:]):
        zm = (z0 + z1) / 2; ho = math.sqrt(max(0., r * r - zm * zm)); zin = min(abs(z0), abs(z1))
        if max(abs(z0), abs(z1)) < r_in:
            hi_ = math.sqrt(max(0., r_in * r_in - max(abs(z0), abs(z1)) ** 2))
            if ho - hi_ > 1e-4:
                out += [C((x - (ho + hi_) / 2, y + h / 2, z + zm), (ho - hi_, h, z1 - z0), col, **kw, **k), C((x + (ho + hi_) / 2, y + h / 2, z + zm), (ho - hi_, h, z1 - z0), col, **kw, **k)]
        else: out.append(C((x, y + h / 2, z + zm), (2 * ho, h, z1 - z0), col, **kw, **k))
    return out


def rndx(x0, x1, cy, cz, d, col, **kw):
    """prisme « rond » couché le long de x (corps de sèche-cheveux, manche)"""
    xc, L = (x0 + x1) / 2, x1 - x0
    return [C((xc, cy, cz), (L, d * .62, d), col, **kw), C((xc, cy, cz), (L, d, d * .62), col, **kw), C((xc, cy, cz), (L, d * .87, d * .87), col, **kw)]


def rndz(z0, z1, cx, cy, d, col, **kw):
    """disque / bouton « rond » couché le long de z (bouton de cadran sur une face avant)"""
    zc, L = (z0 + z1) / 2, z1 - z0
    return [C((cx, cy, zc), (d * .62, d, L), col, **kw), C((cx, cy, zc), (d, d * .62, L), col, **kw), C((cx, cy, zc), (d * .87, d * .87, L), col, **kw)]


def steam(x, y, z, n=4, s=.016, step=.026, col=(224, 226, 230), d0=.5):
    return [C((x + .01 * math.sin(i * 2.1 + .4), y + step * i, z + .008 * math.cos(i * 1.6)), (s, s * 1.3, s), col, dissolve=d0 + .11 * i, cast=False) for i in range(n)]


def _im(W, H, bg):
    im = Image.new('RGBA', (W, H), T._rgba(bg)); return im, ImageDraw.Draw(im)


def _ctr(d, W, y, s, col, scale=1):
    s = T.ascii_up(s); T.mini(d, max(0, (W - T.mini_w(s, scale)) // 2), y, s, col, scale)


# ================================================================== images (shared with VOXEL)
@functools.lru_cache(maxsize=16)
def gauge(level=.6, W=13, H=36, water=(110, 160, 210), glass=(170, 186, 200), frame=(60, 64, 70), lit=False):
    """fenêtre graduée d'un réservoir (bouilloire, cafetière) : niveau d'eau, traits, MAX en haut"""
    im, d = _im(W, H, frame)
    d.rectangle([1, 1, W - 2, H - 2], fill=T._rgba(glass))
    wy = int(round(8 + (H - 10) * (1 - max(0., min(1., level)))))
    wc = (90, 170, 255) if lit else water
    d.rectangle([1, wy, W - 2, H - 2], fill=T._rgba(wc)); d.line([(1, wy), (W - 2, wy)], fill=T._rgba(T._shade(wc, 1.35)))
    for y in range(10, H - 2, 6): d.line([(W - 5, y), (W - 2, y)], fill=(36, 40, 50, 255))
    T.mini(d, 1, 2, 'MAX', (36, 40, 50, 255))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def mw_panel(W=40, H=76, body=(44, 44, 48)):
    """tableau de commande du micro-ondes (sans l'afficheur, peint à part pour qu'il luise seul) : touches 1-9, START, graduations du cadran"""
    im, d = _im(W, H, body)
    d.rectangle([2, 2, W - 3, 15], fill=(10, 12, 12, 255))
    for r in range(3):
        for c_ in range(3):
            x = 4 + c_ * 11; y = 19 + r * 7
            d.rectangle([x, y, x + 9, y + 5], fill=(78, 80, 86, 255)); d.line([(x, y + 5), (x + 9, y + 5)], fill=(30, 30, 34, 255))
            T.mini(d, x + 4, y, '123456789'[r * 3 + c_], (224, 224, 228, 255))
    d.rectangle([4, 41, W - 5, 47], fill=(40, 120, 64, 255)); _ctr(d, W, 42, 'START', (236, 250, 238, 255))
    cx, cy = (W - 1) / 2., 62.
    for k in range(12):
        a = math.radians(-150 + k * 25); r0, r1 = (10, 12) if k % 3 else (9, 12)
        d.line([(cx + math.sin(a) * r0, cy - math.cos(a) * r0), (cx + math.sin(a) * r1, cy - math.cos(a) * r1)], fill=(214, 214, 220, 255))
    T.mini(d, 3, 70, '0', (214, 214, 220, 255)); T.mini(d, W - 10, 70, '30', (214, 214, 220, 255))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def mw_display(text='02:13', W=34, H=12, col=(90, 230, 170)):
    im, d = _im(W, H, (8, 12, 10))
    t = str(text)
    if all(ch in '0123456789:- ' for ch in t):
        sw = T.seg7_w(t, 5, 1); T.seg7(d, max(0, (W - sw) // 2), 1, t, T._rgba(col), dim=(20, 34, 28, 255), w=5, h=10, t=1)
    else: _ctr(d, W, 4, t[:8], T._rgba(col))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def mesh(W=48, H=36, base=(18, 20, 24), dot=(52, 56, 62)):
    """grille de la porte du micro-ondes : trame de petits trous"""
    im, d = _im(W, H, base)
    for y in range(1, H, 3):
        for x in range(1 + (y // 3) % 2, W, 3): d.point((x, y), fill=T._rgba(dot))
    d.rectangle([0, 0, W - 1, H - 1], outline=(10, 10, 12, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def vents(W=24, H=12, body=(200, 200, 196)):
    im, d = _im(W, H, body)
    for y in range(2, H - 1, 3): d.line([(2, y), (W - 3, y)], fill=T._rgba(T._shade(body, .45)))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def surface(kind='soupe', S=16, bout=False):
    """dessus d'un liquide / d'un contenu vu de haut (à poser avec flat()) : soupe aux herbes, céréales dans le lait, riz, eau qui bout, intérieur vide"""
    base = CONTENTS.get(kind, STEEL if kind == 'vide' else WATER)
    im, d = _im(S, S, base)
    if kind == 'soupe':
        for (x, y) in ((3, 4), (10, 3), (6, 10), (12, 11), (8, 6), (2, 12)): d.point((x, y), fill=(70, 120, 40, 255))
        for (x, y) in ((5, 7), (11, 7), (8, 12), (13, 4)): d.point((x, y), fill=(236, 170, 80, 255))
    elif kind == 'cereales':
        for i, (x, y) in enumerate(((2, 2), (6, 3), (11, 2), (4, 7), (9, 6), (13, 8), (2, 11), (7, 11), (11, 12), (5, 14), (13, 13), (8, 9))):
            c = ((200, 140, 60), (226, 176, 90), (170, 110, 40))[i % 3]; d.rectangle([x, y, x + 1, y + 1], fill=T._rgba(c))
    elif kind == 'riz':
        for y in range(1, S, 2):
            for x in range((y // 2) % 2, S, 3): d.point((x, y), fill=(250, 248, 242, 255))
    elif kind in ('eau', 'lait', 'the', 'cafe'):
        d.line([(3, 4), (8, 3)], fill=T._rgba(T._shade(base, 1.3)))
    elif kind == 'vide':
        d.ellipse([1, 1, S - 2, S - 2], fill=T._rgba(T._shade(base, .8))); d.ellipse([4, 4, S - 5, S - 5], fill=T._rgba(T._shade(base, .7)))
        d.line([(4, 5), (6, 3)], fill=T._rgba(T._shade(base, 1.2)))
    if bout:
        for (x, y) in ((3, 3), (10, 5), (6, 11), (12, 12), (8, 8)): d.ellipse([x - 1, y - 1, x + 1, y + 1], outline=T._rgba(T._shade(base, 1.45)))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def board_top(W=76, H=52, wood=(178, 128, 80)):
    """dessus de la planche à découper : veines du bois, rigole, entailles de couteau (positions fixes)"""
    im, d = _im(W, H, wood)
    for i, y in enumerate(range(2, H, 4)):
        d.line([(0, y), (W // 3, y + (i % 2)), (2 * W // 3, y), (W - 1, y + 1)], fill=T._rgba(T._shade(wood, .88 if i % 2 else .93)))
    d.rectangle([4, 4, W - 5, H - 5], outline=T._rgba(T._shade(wood, .7)))
    for (x, y, l) in ((20, 16, 9), (28, 22, 12), (40, 18, 8), (34, 30, 10), (50, 26, 11), (24, 34, 7)):
        d.line([(x, y), (x + l, y + l // 3)], fill=T._rgba(T._shade(wood, .76)))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def pill_top(nom='SOMNIX', dose='10 MG', sous='SOMNIFERE', band=(40, 90, 170), patient='', W=64, H=32):
    """dessus (ou face avant tenue) de la boîte de médicaments : bande de couleur, nom en grand, dosage, indication, croix verte ;
    `patient` : étiquette jaune de la pharmacie à la place de l'indication"""
    im, d = _im(W, H, (246, 246, 242))
    d.rectangle([0, 0, 5, H - 1], fill=T._rgba(band))
    n = T.ascii_up(nom)[:8]; T.big(d, 9, 1, n, T._rgba(T._shade(band, .7)), 8)
    T.mini(d, 9, 12, T.ascii_up(dose)[:12], (60, 60, 70, 255))
    if patient:
        d.rectangle([7, 18, W - 3, H - 2], fill=(250, 236, 140, 255), outline=(190, 170, 80, 255))
        T.mini(d, 9, 19, T.ascii_up(patient)[:13], (40, 40, 50, 255)); T.mini(d, 9, 25, 'PHARMACIE', (110, 100, 60, 255))
    else:
        T.mini(d, 9, 19, T.ascii_up(sous)[:12], (90, 90, 100, 255)); T.mini(d, 9, 25, 'BOITE DE 30', (130, 130, 140, 255))
        d.rectangle([W - 9, 24, W - 3, 30], fill=(250, 250, 250, 255)); d.rectangle([W - 7, 24, W - 5, 30], fill=(40, 160, 80, 255)); d.rectangle([W - 9, 26, W - 3, 28], fill=(40, 160, 80, 255))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def pill_side(nom='SOMNIX', dose='10 MG', band=(40, 90, 170), W=64, H=14):
    im, d = _im(W, H, (246, 246, 242))
    d.rectangle([0, 0, 3, H - 1], fill=T._rgba(band)); d.rectangle([W - 4, 0, W - 1, H - 1], fill=T._rgba(band))
    _ctr(d, W, 2, T.ascii_up(nom)[:7], T._rgba(T._shade(band, .7))); _ctr(d, W, 8, T.ascii_up(dose)[:12], (70, 70, 80, 255))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def pill_end(dose='10 MG', band=(40, 90, 170), W=28, H=14):
    im, d = _im(W, H, band); _ctr(d, W, 5, T.ascii_up(dose)[:6], (250, 250, 250, 255))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def pill_back(lignes=('POSOLOGIE', '1 CP LE SOIR', 'NE PAS', 'DEPASSER'), band=(40, 90, 170), W=64, H=32):
    """dos de la boîte : la posologie, lisible par celui qui la tient"""
    im, d = _im(W, H, (246, 246, 242))
    d.rectangle([0, 0, W - 1, 3], fill=T._rgba(band))
    y = 6
    for i, l in enumerate(list(lignes)[:4]):
        T.mini(d, 4, y, T.ascii_up(l)[:14], (40, 40, 50, 255) if i else T._rgba(T._shade(band, .7))); y += 6
    return np.array(im)


@functools.lru_cache(maxsize=16)
def blister(restants=7, W=48, H=20):
    """plaquette vue de dessus (à poser avec flat()) : dix alvéoles, les pilules prises laissent l'opercule déchiré"""
    im, d = _im(W, H, (196, 198, 206))
    d.rectangle([0, 0, W - 1, H - 1], outline=(150, 152, 160, 255))
    for i in range(10):
        r, c_ = divmod(i, 5); x = 3 + c_ * 9; y = 3 + r * 9
        if i < restants: d.ellipse([x, y, x + 5, y + 5], fill=(214, 216, 222, 255), outline=(150, 152, 160, 255))
        else: d.rectangle([x, y, x + 5, y + 5], fill=(60, 60, 66, 255)); d.line([(x, y + 5), (x + 5, y)], fill=(230, 230, 236, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def toothpaste(W=56, H=16, col=(250, 250, 250), a=(200, 40, 40), b=(40, 90, 190)):
    im, d = _im(W, H, col)
    d.rectangle([0, 0, W - 1, 2], fill=T._rgba(a)); d.rectangle([0, H - 3, W - 1, H - 1], fill=T._rgba(b))
    _ctr(d, W, 6, 'DENTIFRICE', T._rgba(b))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def soap_top(col=(230, 190, 200), W=36, H=24):
    """dessus du savon : SAVON en creux dans un médaillon"""
    im, d = _im(W, H, col)
    d.ellipse([2, 2, W - 3, H - 3], outline=T._rgba(T._shade(col, .82)))
    _ctr(d, W, 9, 'SAVON', T._rgba(T._shade(col, .72)))
    d.line([(5, 6), (10, 4)], fill=T._rgba(T._shade(col, 1.12)))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def towel_top(col=(236, 234, 228), band=(110, 130, 170), W=64, H=40):
    """dessus d'une serviette pliée (à poser avec flat()) : bouclette (trame) et le liteau qui court le long du bord avant"""
    im, d = _im(W, H, col)
    for y in range(H):
        for x in range((y % 2), W, 2): d.point((x, y), fill=T._rgba(T._shade(col, .93)))
    d.rectangle([0, H - 8, W - 1, H - 5], fill=T._rgba(band)); d.line([(0, H - 7), (W - 1, H - 7)], fill=T._rgba(T._shade(band, 1.3)))
    d.line([(0, H - 1), (W - 1, H - 1)], fill=T._rgba(T._shade(col, .8)))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def towel_side(col=(236, 234, 228), W=40, H=14):
    """tranche d'une serviette pliée : les épaisseurs"""
    im, d = _im(W, H, col)
    for y in (4, 9): d.line([(0, y), (W - 1, y)], fill=T._rgba(T._shade(col, .7)))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def grille_ronde(S=16, col=(30, 30, 34)):
    """entrée d'air du sèche-cheveux : grille ronde, anneaux"""
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=T._rgba(col))
    for r in (2, 4, 6): d.ellipse([S / 2 - r - .5, S / 2 - r - .5, S / 2 + r - .5, S / 2 + r - .5], outline=(90, 92, 100, 255))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def teapot_band(col=CERAM, ink=(50, 80, 160), W=32, H=12):
    """frise peinte de la théière : fleurs bleues et feuilles"""
    im, d = _im(W, H, col)
    d.line([(0, 1), (W - 1, 1)], fill=T._rgba(ink)); d.line([(0, H - 2), (W - 1, H - 2)], fill=T._rgba(ink))
    for i, x in enumerate(range(3, W, 8)):
        d.rectangle([x, 4, x + 2, 6], fill=T._rgba(ink)); d.point((x + 1, 5), fill=(240, 220, 120, 255))
        d.point((x + 4, 7 if i % 2 else 4), fill=(70, 130, 80, 255)); d.point((x + 5, 6 if i % 2 else 5), fill=(70, 130, 80, 255))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def plaque(text='CAFE', W=24, H=7, bg=(200, 200, 206), fg=(30, 30, 34)):
    return T.plate(text, W, H, bg, fg)


# ================================================================== the objects (PS1)
def k_kettle(p, c):
    """bouilloire : électrique (socle, corps rond qui s'affine, fenêtre graduée en relief, couvercle et son bouton, bec à gauche, poignée à droite,
    interrupteur qui s'allume) ou `modele: gaz` (émaillée, anse sur le dessus, bec en col de cygne, sifflet) ; `allumee`, `niveau`, `vapeur`"""
    on = bool(_g(p, 'allumee', 'on', default=False)); lvl = float(_g(p, 'niveau', default=.6))
    if _g(p, 'modele', default='electrique') == 'gaz': return _kettle_gas(p, c, on)
    col = _col(c, WHITE); dk = DARK
    out = disk(0, 0, 0, .095, .02, dk)
    for (y0, h, r) in ((.02, .012, .08), (.032, .045, .086), (.077, .05, .083), (.127, .045, .079), (.172, .03, .075), (.202, .02, .07)):
        out += disk(0, y0, 0, r, h, col, refl=.1)
    out += disk(0, .222, 0, .062, .01, _sh(col, .9)) + disk(0, .232, 0, .05, .005, _sh(col, .96))
    out += [C((-.078, .2, 0), (.03, .04, .05), col), C((-.096, .214, 0), (.024, .03, .042), col), C((-.109, .226, 0), (.014, .012, .034), _sh(col, .9))]       # bec
    out += [C((.086, .208, 0), (.04, .026, .034), dk), C((.113, .14, 0), (.026, .162, .034), dk), C((.092, .065, 0), (.034, .02, .034), dk)]                   # poignée
    out += [C((.1265, .085, 0), (.004, .022, .018), (255, 120, 40) if on else (90, 40, 30), emis=2.2 if on else 0., cast=False)]                                 # interrupteur
    out += [C((.045, .2365, 0), (.024, .006, .024), dk)]                                                                                                       # bouton du couvercle
    out.append(B((.01, .045, -.0875), (.03, .12, .012), (150, 170, 190), tex={'-z': gauge(lvl, lit=on)}, texemis=.6 if on else 0., cast=False))
    out.append(B((-.034, .14, -.0805), (.026, .009, .0015), (200, 200, 206), tex={'-z': plaque('KETL', 20, 7)}))
    out.append(C((0, .007, .1), (.008, .008, .03), dk))
    if on or _g(p, 'vapeur', 'steam', default=False): out += steam(-.112, .24, 0, 5)
    return out


def _kettle_gas(p, c, on):
    col = _col(c, (176, 40, 36)); dk = DARK; cr = (232, 226, 212)
    out = disk(0, 0, 0, .085, .01, _sh(col, .55))
    for (y0, h, r) in ((.01, .02, .098), (.03, .04, .105), (.07, .02, .1), (.09, .015, .088), (.105, .012, .072), (.117, .008, .056)): out += disk(0, y0, 0, r, h, col, refl=.25)
    out += disk(0, .125, 0, .045, .008, cr) + disk(0, .133, 0, .014, .016, dk)
    out += [C((-.05, .155, 0), (.01, .07, .012), STEEL, mat=M_METAL), C((.05, .155, 0), (.01, .07, .012), STEEL, mat=M_METAL), C((0, .19, 0), (.13, .022, .026), dk)]
    for i in range(6):
        t = (i + .5) / 6; out.append(C((-.09 - .062 * t, .045 + .09 * t, 0), (.028 - .01 * t, .024, .028 - .01 * t), col))
    out += [C((-.157, .148, 0), (.03, .022, .03), dk), C((-.172, .153, 0), (.012, .006, .012), dk)]
    if on: out += steam(-.165, .17, 0, 5)
    return out


def k_coffee_maker(p, c):
    """cafetière filtre : socle avec plaque chauffante, horloge LCD et interrupteur, colonne et réservoir à fenêtre graduée, capot et porte-filtre,
    verseuse en verre (café au niveau `plein`, col noir, bec, anse, graduations)"""
    body = _col(c, (36, 36, 40)); on = bool(_g(p, 'allumee', 'on', default=False)); plein = float(_g(p, 'plein', default=.6)); glass = (200, 214, 222)
    out = [B((-.1, 0, -.12), (.2, .035, .24), body), B((-.1, .035, .04), (.2, .23, .08), body), B((-.1, .265, -.12), (.2, .055, .24), body),
           B((-.092, .32, -.11), (.184, .006, .2), _sh(body, 1.25))]
    out += rnd(0, .035, -.04, .13, .004, .13, (64, 64, 68), mat=M_METAL)
    out.append(B((-.085, .01, -.1215), (.05, .016, .002), (40, 60, 40), tex={'-z': T.lcd(T.hhmm(_g(p, 'heure', 'time'), '07:00'), 24, 8)}, texemis=.6, cast=False))
    out.append(C((.065, .0175, -.1215), (.022, .012, .003), (255, 60, 40) if on else (90, 26, 22), emis=2.4 if on else 0., cast=False))
    out.append(B((.1, .07, .05), (.002, .17, .06), (150, 170, 190), tex={'+x': gauge(float(_g(p, 'niveau', default=.4)), water=(150, 180, 210))}))
    out.append(B((-.03, .282, -.1215), (.06, .016, .0015), (200, 200, 206), tex={'-z': plaque('CAFE', 24, 7)}))
    out += rnd(0, .235, -.04, .11, .03, .11, _sh(body, .85)) + rnd(0, .222, -.04, .07, .013, .07, _sh(body, .85))
    cz = -.04
    out += rnd2(0, .039, cz, .125, .006, .125, glass, refl=.3, dissolve=.3)
    if plein > .02: out += rnd2(0, .045, cz, .112, .11 * min(1., plein), .112, COFFEE, refl=.15)
    out += rnd2(0, .039, cz, .128, .12, .128, glass, refl=.35, dissolve=.66, cast=False) + rnd2(0, .159, cz, .1, .012, .1, glass, refl=.35, dissolve=.6, cast=False)
    out += rnd(0, .171, cz, .106, .03, .106, (30, 30, 34)) + rnd(0, .201, cz, .088, .012, .088, (30, 30, 34)) + [C((0, .195, cz - .06), (.035, .012, .02), (30, 30, 34))]
    out += [C((.073, .19, cz), (.03, .014, .02), (30, 30, 34)), C((.093, .13, cz), (.016, .11, .024), (30, 30, 34)), C((.075, .08, cz), (.03, .012, .02), (30, 30, 34))]
    for i in range(4): out.append(C((-.022, .062 + .022 * i, cz - .066), (.012 if i % 2 else .018, .0025, .002), (236, 236, 240), emis=.15, cast=False))
    out.append(C((-.03, .1, cz - .066), (.004, .07, .002), (240, 246, 250), emis=.2, cast=False))                       # reflet du verre
    out.append(C((0, .01, .13), (.008, .008, .02), (30, 30, 34)))
    if on: out += steam(.03, .33, .07, 4)
    return out


def k_toaster(p, c):
    """grille-pain deux fentes : corps chromé (ou couleur), joues noires, fentes (rougeoyantes `allumee`), tartines, levier, bouton de dorage, touches, plaque"""
    col = _col(c, (196, 198, 206)); chrome = c is None; on = bool(_g(p, 'allumee', 'on', default=False)); tart = _g(p, 'tartines', default=False)
    down = on or tart == 'dedans'; mk = dict(mat=M_METAL, refl=.3) if chrome else {}
    out = [B((-.142, 0, -.082), (.284, .014, .164), DARK), B((-.14, .014, -.08), (.28, .168, .16), col, **mk), B((-.134, .182, -.074), (.268, .01, .148), col, **mk),
           B((-.148, .024, -.07), (.008, .15, .14), DARK), B((.14, .024, -.07), (.008, .15, .14), DARK)]
    for zc in (-.03, .03):
        out.append(B((-.105, .1915, zc - .012), (.21, .0015, .024), (255, 110, 40) if on else (14, 12, 10), emis=1.8 if on else 0., cast=False))
        if tart in ('sorties', 'dedans', True):
            yb = .17 if tart == 'dedans' else .12
            out += [B((-.085, yb, zc - .008), (.17, .193 - yb + (.0 if tart == 'dedans' else .06), .016), (222, 168, 96)),
                    B((-.087, yb + (.0 if tart == 'dedans' else .002), zc - .009), (.004, .193 - yb + (.0 if tart == 'dedans' else .058), .018), (168, 104, 50)),
                    B((.083, yb, zc - .009), (.004, .193 - yb + (.0 if tart == 'dedans' else .058), .018), (168, 104, 50))]
            if tart != 'dedans': out.append(C((0, .253, zc), (.17, .008, .018), (176, 112, 54)))
    out += [B((.088, .045, -.0815), (.014, .125, .0015), (14, 14, 16)), C((.095, .07 if down else .155, -.092), (.034, .016, .022), (30, 30, 34))]   # levier
    out += rndz(-.088, -.08, .05, .06, .03, (36, 36, 40)) + [C((.05, .07, -.0885), (.003, .01, .002), (240, 240, 240), emis=.2, cast=False)]          # bouton de dorage
    for i in range(6): out.append(C((.05 + .021 * math.sin(math.radians(-100 + i * 40)), .06 + .021 * math.cos(math.radians(-100 + i * 40)), -.081), (.003, .003, .001), (30, 30, 34)))
    out += [C((.05, .11, -.082), (.02, .01, .004), (200, 40, 40)), C((.05, .128, -.082), (.02, .01, .004), (60, 120, 200))]
    out.append(B((-.08, .075, -.0815), (.07, .016, .0015), (200, 200, 206), tex={'-z': plaque('TOAST', 28, 7)}))
    out.append(C((0, .02, -.0825), (.1, .008, .005), (60, 60, 64)))
    if chrome: out += [C((-.115, .1, -.0812), (.006, .14, .001), (250, 250, 255), emis=.35, cast=False), C((-.1, .1, -.0812), (.002, .14, .001), (250, 250, 255), emis=.25, cast=False)]
    out.append(C((-.12, .006, .09), (.008, .008, .02), DARK))
    return out


def k_microwave(p, c):
    """micro-ondes : caisson creux (on voit dedans), plateau de verre, porte à vitre tramée (ou `ouverte`), poignée, tableau de commande avec afficheur,
    touches, START et cadran de minuterie en relief, ouïes ; `allume` : four éclairé (lampe, parois qui luisent) ; `contenu` bol"""
    cab = _col(c, (214, 214, 210)); on = bool(_g(p, 'allume', 'allumee', 'on', default=False)); door = (34, 34, 38); inner = (206, 204, 196)
    em = .45 if on else 0.
    txt = _g(p, 'ecran', 'screen'); txt = str(txt) if txt not in (None, True) else T.hhmm(_g(p, 'heure', 'time'), '02:13')
    out = [B((-.24, .01, -.17), (.48, .02, .35), cab), B((-.24, .27, -.17), (.48, .02, .35), cab), B((-.24, .03, -.17), (.02, .24, .35), cab),
           B((-.22, .03, .16), (.32, .24, .02), cab), B((.1, .03, -.17), (.14, .24, .35), cab)]
    out += [B((-.22, .03, -.17), (.32, .002, .33), inner, emis=em), B((-.22, .268, -.17), (.32, .002, .33), inner, emis=em), B((-.22, .032, -.17), (.002, .236, .33), inner, emis=em),
            B((-.22, .032, .158), (.32, .236, .002), inner, emis=em * 1.2), B((.098, .032, -.17), (.002, .236, .33), inner, emis=em)]
    out += [C((.09, .255, .1), (.014, .02, .03), (255, 236, 180) if on else (180, 176, 168), emis=2.2 if on else 0., cast=False)]
    out += rnd2(-.06, .033, -.005, .25, .006, .25, (206, 216, 220), refl=.3) + [C((-.06, .034, -.005), (.06, .006, .06), (90, 90, 96))]
    if _g(p, 'contenu', default='') == 'bol': out += shift(k_bowl({'contenu': 'soupe', 'cuillere': False, 'vapeur': on}, None), -.06, .039, -.005)
    for x in (-.21, .21):
        for z in (-.15, .15): out.append(C((x, .005, z), (.03, .01, .03), DARK))
    if _g(p, 'ouverte', 'open', default=False):                                                        # porte ouverte à 90° sur sa charnière gauche
        out += [B((-.255, .025, -.51), (.015, .25, .33), door, refl=.15), B((-.2405, .06, -.48), (.002, .175, .24), (20, 22, 26), tex={'+x': mesh()}),
                C((-.262, .15, -.49), (.012, .16, .014), STEEL, mat=M_METAL)]
    else:
        out += [B((-.235, .235, -.185), (.33, .04, .015), door, refl=.15), B((-.235, .025, -.185), (.33, .035, .015), door, refl=.15),
                B((-.235, .06, -.185), (.03, .175, .015), door, refl=.15), B((.035, .06, -.185), (.06, .175, .015), door, refl=.15)]
        out.append(B((-.205, .06, -.183), (.24, .175, .008), (22, 24, 28), tex={'-z': mesh()}, dissolve=.5, refl=.2, cast=False))
        out += [C((.07, .15, -.2), (.016, .16, .016), STEEL, mat=M_METAL), C((.07, .08, -.19), (.012, .012, .014), STEEL, mat=M_METAL), C((.07, .22, -.19), (.012, .012, .014), STEEL, mat=M_METAL)]
    out.append(B((.1, .025, -.172), (.135, .25, .002), (44, 44, 48), tex={'-z': mw_panel()}))
    out.append(B((.107, .23, -.1735), (.115, .036, .0015), (8, 12, 10), tex={'-z': mw_display(txt)}, texemis=1.1, cast=False))
    ky = .275 - 62. / 76 * .25
    out += rndz(-.19, -.173, .1675, ky, .042, (40, 40, 44)) + rndz(-.196, -.19, .1675, ky, .03, (60, 60, 66)) + [C((.1675, ky + .011, -.1965), (.004, .014, .002), (240, 240, 240), emis=.2, cast=False)]
    out.append(B((.24, .18, -.06), (.002, .06, .12), cab, tex={'+x': vents(24, 12, cab)}))
    out.append(C((.0, .02, .19), (.008, .008, .02), DARK))
    return out


def _liquid(x, y, z, r, kind, bout=False, k=None):
    """dessus d'un contenu : disque rond + détail peint sur le carré central"""
    col = CONTENTS.get(kind, STEEL)
    out = disk(x, y, z, r, .002, col, k=k, refl=.12 if kind in ('eau', 'the', 'cafe') else 0.)
    h = r * .55
    out.append(B((x - h, y + .002, z - h), (2 * h, .0005, 2 * h), col, tex={'+y': T.flat(surface(kind, 16, bout))}, **(k or {})))
    return out


def k_saucepan(p, c):
    """casserole en inox, creuse pour de vrai : fond épais, paroi, bord clair, contenu peint, manche plat qui monte (rivets, trou), `couvercle` de verre à bouton, `bout`"""
    st = _col(c, STEEL); cont = _g(p, 'contenu', default='eau'); bout = bool(_g(p, 'bout', default=False)); M = dict(mat=M_METAL, refl=.25)
    R, Ri, top = .09, .084, .1
    yl = .014 if cont == 'vide' else .07
    out = disk(0, 0, 0, .086, .008, _sh(st, .7), mat=M_METAL) + disk(0, .008, 0, R, yl - .008, st, **M)
    out += disk(0, yl, 0, Ri, .002, _sh(st, .72), mat=M_METAL) if cont == 'vide' else _liquid(0, yl, 0, Ri, cont if cont in CONTENTS else 'eau', bout)
    out += ring(0, yl, 0, R, Ri, top - yl, st, **M) + ring(0, top, 0, R + .0015, Ri, .004, _sh(st, 1.15), mat=M_METAL)
    out += [C((.093, .075, -.008), (.006, .006, .006), _sh(st, .8)), C((.093, .075, .008), (.006, .006, .006), _sh(st, .8)), C((.1, .078, 0), (.016, .03, .026), st, **M)]
    for i in range(6): out.append(C((.115 + i * .03, .088 + i * .004, 0), (.032, .009, .026 - i * .0012), st, **M))
    out += [C((.29, .108, 0), (.03, .009, .026), st, **M), C((.293, .1131, 0), (.011, .0005, .011), (16, 16, 18))]
    if _g(p, 'couvercle', 'lid', default=False):
        out += disk(0, top + .004, 0, R + .003, .005, (190, 204, 214), dissolve=.45, refl=.3, cast=False) + ring(0, top + .004, 0, R + .004, R - .004, .007, st, mat=M_METAL)
        out += disk(0, top + .009, 0, .05, .003, (190, 204, 214), dissolve=.4, refl=.3, cast=False) + disk(0, top + .012, 0, .013, .016, DARK)
    if bout:
        for (x, z) in ((-.03, .02), (.02, -.03), (.04, .03), (-.01, -.045)): out.append(C((x, yl + .004, z), (.008, .004, .008), _sh(CONTENTS.get(cont, WATER), 1.4), cast=False))
        out += steam(0, .13, 0, 5)
    return out


def k_frying_pan(p, c):
    """poêle creuse : fond, paroi évasée en deux gradins, revêtement noir, bord, manche en bakélite (bague, rivets, trou) ; `contenu` oeuf, oeufs, bacon"""
    ext = _col(c, (58, 58, 64)); cont = _g(p, 'contenu', default='vide')
    out = disk(0, 0, 0, .1, .012, _sh(ext, .8)) + disk(0, .012, 0, .107, .002, (28, 28, 30), refl=.15)
    out.append(B((-.05, .014, -.05), (.1, .0005, .1), (28, 28, 30), tex={'+y': T.flat(surface('vide', 16))}, refl=.15))
    out += ring(0, .008, 0, .116, .106, .014, ext) + ring(0, .022, 0, .128, .116, .02, ext) + ring(0, .042, 0, .129, .121, .003, _sh(ext, 1.35), mat=M_METAL)
    out += [C((.127, .03, -.009), (.004, .008, .008), STEEL), C((.127, .03, .009), (.004, .008, .008), STEEL), C((.14, .033, 0), (.024, .022, .032), STEEL, mat=M_METAL)]
    for i in range(6): out.append(C((.168 + i * .032, .036 + i * .0045, 0), (.034, .02, .028), (28, 28, 30)))
    out.append(C((.328, .0602, 0), (.012, .0005, .012), (8, 8, 10)))
    y = .014
    for (x, z) in {'oeuf': [(-.01, .01)], 'oeufs': [(-.045, .02), (.04, -.025)]}.get(cont, []):
        out += disk(x, y, z, .045, .005, (246, 244, 236)) + [C((x + .03, y + .002, z + .028), (.036, .004, .03), (246, 244, 236)), C((x - .034, y + .002, z - .02), (.028, .004, .036), (242, 240, 230))]
        out += disk(x + .004, y + .004, z - .004, .016, .009, (250, 176, 30)) + [C((x, y + .0135, z - .01), (.008, .001, .006), (255, 232, 160), emis=.2, cast=False)]
    if cont == 'bacon':
        for z in (-.05, -.01, .03): out += [B((-.075, y, z), (.15, .005, .026), (170, 60, 50)), B((-.075, y + .0052, z + .006), (.15, .0005, .007), (236, 200, 180))]
    return out


def _blade(n=9, L=.188, w0=.046):
    """profil de lame de chef : (t, largeur) le long de la lame, du talon à la pointe (le tranchant remonte vers le dos)"""
    return [((i + .5) / n, w0 * (1 - ((i + .5) / n) ** 2.4) + .004) for i in range(n)]


def k_kitchen_knife(p, c):
    """couteau de chef couché sur le flanc, pointe vers +x, tranchant vers l'avant : manche (trois rivets), mitre, lame effilée avec biseau clair ; `sang`"""
    hc = _col(c, (44, 34, 30)); sang = bool(_g(p, 'sang', 'blood', default=False)); zs = .012; n = 9; L = .188
    out = [B((-.16, 0, -.021), (.12, .016, .024), hc), B((-.155, .016, -.018), (.11, .0025, .018), _sh(hc, 1.2)), C((-.163, .008, -.009), (.008, .014, .02), _sh(hc, .8))]
    out += [C((x, .0188, -.009), (.006, .001, .006), STEEL, mat=M_METAL) for x in (-.14, -.105, -.07)]
    out += [C((-.034, .009, -.008), (.012, .018, .032), STEEL, mat=M_METAL, refl=.3)]
    for i, (t, w) in enumerate(_blade(n, L)):
        x0 = -.028 + L * i / n; dx = L / n
        out += [B((x0, 0, zs - w), (dx, .0025, w), STEEL, mat=M_METAL, refl=.35), B((x0, .0004, zs - w), (dx, .0025, .005), (236, 240, 246), emis=.08, refl=.35)]
    if sang:
        for (x, z, w, d) in ((.02, -.02, .05, .012), (.07, -.01, .03, .01), (.1, -.002, .02, .006), (.04, -.004, .02, .008)): out.append(B((x, .0026, z), (w, .0006, d), (110, 8, 12)))
        for (x, z) in ((.19, -.01), (.205, .015), (.175, .03)): out.append(C((x, .0005, z), (.008, .001, .008), (100, 6, 10)))
    return out


def k_cutting_board(p, c):
    """planche à découper en bois : coins arrondis, veines, rigole, entailles, trou ; `contenu` carottes, pain, oignon ; `couteau` posé dessus"""
    wood = _col(c, (178, 128, 80)); cont = _g(p, 'contenu', default='vide')
    out = [B((-.19, 0, -.12), (.38, .022, .24), wood, mat=M_WOODV), B((-.18, 0, -.13), (.36, .022, .26), wood, mat=M_WOODV),
           B((-.18, .022, -.12), (.36, .0008, .24), wood, tex={'+y': T.flat(board_top(76, 52, wood))}), C((.162, .0232, 0), (.022, .001, .022), (40, 26, 16))]
    y = .023
    if cont == 'carottes':
        or_ = (230, 120, 30)
        out += [C((-.08 + i * .03, y + .008, -.03), (.03 - i * .003, .016 - i * .0015, .016 - i * .0015), or_) for i in range(5)]
        out += [C((-.1, y + .009, -.03), (.014, .01, .012), (90, 150, 50)), C((-.112, y + .012, -.035), (.018, .006, .006), (90, 150, 50))]
        for (x, z) in ((.04, .04), (.07, .03), (.06, .065), (.095, .05), (.03, .075)):
            out += rnd2(x, y, z, .022, .006, .022, or_) + [C((x, y + .0062, z), (.008, .0005, .008), (250, 170, 80))]
    elif cont == 'pain':
        out += rnd(-.05, y, .0, .2, .06, .09, (196, 136, 70)) + [C((-.05, y + .061, 0), (.17, .004, .06), (214, 160, 90))]
        for i in range(3): out += [B((.07 + i * .022, y, -.045), (.012, .055, .08), (232, 206, 160)), B((.07 + i * .022, y, -.045), (.012, .055, .004), (180, 120, 60))]
    elif cont == 'oignon':
        out += rnd2(-.03, y, .0, .07, .035, .07, (220, 180, 120)) + rnd2(-.03, y + .035, .0, .05, .002, .05, (240, 230, 220))
        for i in range(3): out.append(C((.06, y + .003, -.02 + i * .02), (.04, .004, .008), (240, 226, 230)))
    if _g(p, 'couteau', 'knife', default=False): out += shift(k_kitchen_knife({}, None), .0, y, .08)
    return out


BOWL = ((.008, .02, .05), (.02, .032, .061), (.032, .046, .068), (.046, .058, .072), (.058, .068, .075))


def _bowl(x, y, z, col, fil, cont, k=None, spoon=True, steam_=False):
    """bol creux en faïence (repère : x, y = le bas, z) : pied, panse évasée en gradins, contenu au niveau, paroi au-dessus, liseré, bord clair"""
    k = k or {}; yc = .022 if cont == 'vide' else .056; wall = .006
    out = disk(x, y, z, .034, .008, _sh(col, .88), k=k)
    for (y0, y1, r) in BOWL:
        if y1 <= yc + 1e-6: out += disk(x, y + y0, z, r, y1 - y0, col, k=k)
        elif y0 >= yc - 1e-6: out += ring(x, y + y0, z, r, r - wall, y1 - y0, col, k=k)
        else: out += disk(x, y + y0, z, r, yc - y0, col, k=k) + ring(x, y + yc, z, r, r - wall, y1 - yc, col, k=k)
    rc = [r for (y0, y1, r) in BOWL if y0 <= yc < y1][0] - wall
    if cont == 'vide': out += disk(x, y + yc, z, rc, .002, _sh(col, .86), k=k)
    else: out += _liquid(x, y + yc, z, rc, cont if cont in CONTENTS else 'soupe', k=k)
    out += ring(x, y + .06, z, .0757, .07, .003, fil, k=k) + ring(x, y + .068, z, .075, .069, .002, _sh(col, 1.06), k=k)
    if spoon: out += line((x + .02, y + yc + .004, z - .01), (x + .085, y + .1, z - .035), .008, STEEL, n=4, k=k, mat=M_METAL) + [C((x + .008, y + yc + .003, z - .004), (.026, .005, .02), STEEL, mat=M_METAL, **k)]
    if steam_: out += [C((x + .01 * math.sin(i * 2.), y + .085 + .028 * i, z), (.016, .02, .016), (224, 226, 230), dissolve=.5 + .11 * i, cast=False, **k) for i in range(4)]
    return out


def k_bowl(p, c):
    """bol en faïence creux : pied, panse évasée, liseré coloré, bord ; `contenu` soupe (défaut, vapeur), cereales, lait, riz, vide ; `cuillere`, `vapeur`, `filet`"""
    cont = _g(p, 'contenu', default='soupe')
    return _bowl(0, 0, 0, _col(c, CERAM), _col(_g(p, 'filet'), (60, 90, 160)), cont, spoon=_g(p, 'cuillere', 'spoon', default=True), steam_=_g(p, 'vapeur', 'steam', default=cont == 'soupe'))


TEAPOT = ((0, .008, .045), (.008, .022, .066), (.022, .07, .083), (.07, .092, .076), (.092, .106, .064), (.106, .114, .052))


def _teapot_body(x, y, z, col, k=None):
    k = k or {}; out = []
    for (y0, y1, r) in TEAPOT: out += disk(x, y + y0, z, r, y1 - y0, col, n=6 if r > .06 else 4, k=k, refl=.1)
    out += disk(x, y + .114, z, .046, .008, _sh(col, .97), k=k) + disk(x, y + .122, z, .034, .008, col, k=k) + disk(x, y + .13, z, .01, .006, col, k=k) + disk(x, y + .136, z, .016, .01, col, k=k)
    out += ring(x, y + .112, z, .054, .046, .003, (200, 160, 70), k=k)
    return out


def k_teapot(p, c):
    """théière en porcelaine : pied, panse ronde en gradins, frise peinte, couvercle à bouton et filet doré, bec effilé à gauche, anse à droite ; `vapeur`, `motif`"""
    col = _col(c, CERAM); ink = _col(_g(p, 'motif'), (50, 80, 160))
    out = _teapot_body(0, 0, 0, col)
    out.append(B((-.038, .036, -.0838), (.076, .022, .002), col, tex={'-z': teapot_band(col, ink)}))
    for i in range(6):
        t = (i + .5) / 6; out.append(C((-.075 - .058 * t, .04 + .068 * t, 0), (.028 - .012 * t, .022 - .004 * t, .028 - .012 * t), col))
    out += [C((-.137, .111, 0), (.012, .006, .014), _sh(col, .9))]
    out += [C((.088, .098, 0), (.03, .014, .02), col), C((.108, .07, 0), (.014, .05, .02), col), C((.088, .042, 0), (.03, .014, .02), col)]
    if _g(p, 'vapeur', 'steam', default=False): out += steam(-.14, .13, 0, 4)
    return out


def _pill_cfg(p):
    band = _col(_g(p, 'couleur_bande', 'bande', 'color'), (40, 90, 170))
    pos = _g(p, 'posologie'); pos = tuple(T.lines(pos)) if pos else ('POSOLOGIE', '1 CP LE SOIR', 'NE PAS', 'DEPASSER')
    return (str(_g(p, 'nom', 'texte', 'text', default='SOMNIX')), str(_g(p, 'dose', default='10 MG')), str(_g(p, 'sous', default='SOMNIFERE')), band,
            str(_g(p, 'patient', default='') or ''), pos)


def k_pill_box(p, c):
    """boîte de médicaments couchée : nom, dosage, indication lisibles sur le dessus et la tranche, posologie au dos, `patient` (étiquette de pharmacie) ;
    `plaquette` (défaut) : plaquette de dix comprimés à côté, `restants`"""
    nom, dose, sous, band, pat, pos = _pill_cfg(dict(p, color=c) if c is not None else p)
    out = [B((-.055, 0, -.0275), (.11, .025, .055), (246, 246, 242), mat=M_CARD,
             tex={'+y': T.flat(pill_top(nom, dose, sous, band, pat)), '-z': pill_side(nom, dose, band), '+z': pill_side(nom, dose, band), '+x': pill_end(dose, band), '-x': pill_end(dose, band)}),
           B((-.055, .0248, -.0275), (.11, .0006, .006), (230, 230, 226))]                    # rabat du couvercle
    if _g(p, 'plaquette', 'blister', default=True):
        rest = int(_g(p, 'restants', default=7))
        out.append(B((-.03, 0, -.1), (.1, .003, .045), (196, 198, 206), tex={'+y': T.flat(blister(rest))}, mat=M_METAL, refl=.25))
        for i in range(min(10, max(0, rest))):
            r, c_ = divmod(i, 5); out.append(C((-.03 + (3 + c_ * 9 + 3) / 48 * .1, .0045, -.1 + .045 - (3 + r * 9 + 3) / 20 * .045), (.0105, .003, .0105), (226, 228, 232), refl=.2))
    return out


def k_toothbrush_glass(p, c):
    """verre à dents translucide, deux brosses penchées (manche, tête, poils blancs et bleus), tube de dentifrice couché à côté"""
    gl = _col(c, (196, 214, 222)); n = int(_g(p, 'brosses', default=2))
    out = rnd2(0, 0, 0, .07, .01, .07, gl, refl=.3) + rnd2(0, .01, 0, .072, .09, .072, gl, refl=.35, dissolve=.7, cast=False) + OD._rim_ps1(.036, .1, gl)
    out += rnd2(0, .01, 0, .06, .004, .06, (170, 196, 214), refl=.3)
    for i, (col, a, b) in enumerate((((40, 110, 200), (-.008, .012, .008), (-.048, .2, .03)), ((230, 90, 130), (.01, .012, -.006), (.05, .19, -.025)),
                                     ((70, 170, 110), (.0, .012, .012), (.006, .205, .05)))[:max(1, min(3, n))]):
        out += line(a, b, .011, col, n=9)
        d = np.subtract(b, a); d = d / np.linalg.norm(d); hd = np.add(b, d * .02)
        out += [C(tuple(hd), (.013, .028, .013), col), C(tuple(np.add(hd, (0, 0, -.011))), (.011, .024, .01), (246, 246, 250)), C(tuple(np.add(hd, (0, .004, -.016))), (.009, .012, .004), (90, 170, 230))]
    if _g(p, 'dentifrice', default=True):
        out += [B((.05, 0, -.075), (.12, .024, .042), (250, 250, 250), tex={'+y': T.flat(toothpaste())}), B((.17, 0, -.078), (.022, .008, .048), (240, 240, 240)),
                C((.042, .012, -.054), (.016, .022, .022), (200, 40, 40)), C((.03, .012, -.054), (.01, .016, .016), (200, 40, 40))]
    return out


def k_soap(p, c):
    """porte-savon en faïence (rebord, nervures) et pain de savon arrondi marqué SAVON ; `modele` pompe (flacon de savon liquide à pompe) ; `mousse`"""
    col = _col(c, (232, 184, 196))
    if _g(p, 'modele', default='pain') == 'pompe':
        out = [B((-.035, 0, -.022), (.07, .13, .044), col, refl=.25), B((-.03, .03, -.0235), (.06, .06, .002), (246, 244, 236), tex={'-z': T.label('SAVON', 'LIQUIDE', (246, 244, 236), (120, 60, 90), 30, 20)})]
        out += rnd2(0, .13, 0, .032, .014, .032, WHITE) + [C((0, .158, 0), (.008, .03, .008), WHITE), C((0, .177, -.004), (.03, .014, .024), WHITE), C((0, .18, -.03), (.008, .006, .036), WHITE)]
        return out
    cer = (236, 236, 232)
    out = rnd(0, 0, 0, .135, .01, .1, cer) + [B((-.0675, .01, -.05), (.135, .012, .006), cer), B((-.0675, .01, .044), (.135, .012, .006), cer),
                                              B((-.0675, .01, -.044), (.006, .012, .088), cer), B((.0615, .01, -.044), (.006, .012, .088), cer)]
    out += [C((0, .012, z), (.1, .004, .006), _sh(cer, .92)) for z in (-.026, 0, .026)]
    out += rnd(0, .014, 0, .092, .024, .058, col, refl=.15) + rnd(0, .038, 0, .082, .005, .05, col, refl=.15)
    out.append(B((-.03, .0432, -.018), (.06, .0005, .036), col, tex={'+y': T.flat(soap_top(col))}, refl=.15))
    if _g(p, 'mousse', default=False):
        for (x, y, z) in ((-.03, .044, .01), (.02, .045, -.012), (.045, .03, .02), (-.046, .026, -.02), (.0, .046, .015)): out.append(C((x, y, z), (.012, .008, .012), (250, 250, 252), dissolve=.25, cast=False))
    return out


def k_towel(p, c):
    """serviette éponge pliée : rouleaux des plis devant (arrondis, rainures), gros pli derrière, coussin du dessus (bouclette, liteau le long du bord),
    tranches à trois épaisseurs ; `pile` de serviettes (1 à 4), `couleurs`, `bande`"""
    n = max(1, min(4, int(_g(p, 'pile', default=1)))); band = _col(_g(p, 'bande'), (110, 130, 170)); cols = _g(p, 'couleurs') or []; H = .066
    out = []
    for i in range(n):
        col = _col(cols[i] if i < len(cols) else c, WHITE); y0 = i * .068; dx = .006 * (1 if i % 2 else -1) * (i > 0); F = dict(mat=M_FABRIC)
        out += [B((-.152 + dx, y0 + .003, -.094), (.304, H - .006, .188), col, **F), B((-.147 + dx, y0 + H - .004, -.09), (.294, .004, .178), col, tex={'+y': T.flat(towel_top(col, band))}, **F),
                B((.152 + dx, y0 + .008, -.088), (.001, H - .016, .176), col, tex={'+x': towel_side(col)}), B((-.153 + dx, y0 + .008, -.088), (.001, H - .016, .176), col, tex={'-x': towel_side(col)}),
                C((dx, y0 + H / 2, .094), (.296, H - .012, .012), col, **F)]
        for k_ in range(3):
            yc = y0 + .012 + .021 * k_
            out += [C((dx, yc, -.094), (.298, .019, .014), col, **F), C((dx, yc, -.099), (.288, .013, .006), _sh(col, .98), **F)]
        out.append(C((dx, y0 + .033, -.1022), (.286, .004, .001), band))
    return out


def k_hair_dryer(p, c):
    """sèche-cheveux couché sur le flanc : corps cylindrique, grille d'entrée d'air, bague, embout concentrateur (+x), poignée vers l'avant avec
    curseurs de vitesse et de chaleur, anneau de suspension, cordon enroulé sur la tablette et sa fiche"""
    col = _col(c, (70, 120, 132)); dk = DARK; cy = .0375
    out = rndx(-.07, .085, cy, 0, .075, col, refl=.15) + rndx(-.095, -.07, cy, 0, .07, dk) + rndx(.085, .1, cy, 0, .064, STEEL, mat=M_METAL, refl=.3)
    out.append(B((-.0965, cy - .026, -.026), (.0015, .052, .052), dk, tex={'-x': grille_ronde()}))
    out += [C((.12, cy, 0), (.04, .034, .056), dk), C((.1405, cy, 0), (.002, .008, .046), (8, 8, 10))]
    out += [C((.03, .034, -.065), (.046, .034, .07), col), C((.022, .033, -.135), (.042, .032, .075), col), C((.018, .033, -.176), (.036, .03, .012), _sh(col, .8))]
    out += [C((.03, .0515, -.08), (.012, .002, .022), (200, 40, 40)), C((.026, .0505, -.115), (.012, .002, .018), (240, 240, 240)), C((.015, .0505, -.1), (.004, .001, .03), dk)]
    out += [C((.018, .034, -.19), (.03, .008, .016), dk), C((.018, .034, -.198), (.012, .008, .004), (16, 16, 18))]
    cord = [(.018, .02, -.185), (-.04, .005, -.22), (-.13, .005, -.21), (-.19, .005, -.13), (-.18, .005, -.02), (-.12, .005, .04)]
    for a, b in zip(cord[:-1], cord[1:]): out += line(a, b, .007, dk, n=max(2, int(np.linalg.norm(np.subtract(a, b)) / .012)))
    out += [C((-.1, .012, .055), (.03, .024, .022), (230, 230, 226)), C((-.082, .01, .05), (.01, .004, .004), STEEL, mat=M_METAL), C((-.082, .01, .062), (.01, .004, .004), STEEL, mat=M_METAL)]
    return out


# ================================================================== held in the hand (PS1)
def h_kitchen_knife(P, F, k, lights, col, cfg):
    """couteau tenu au poing, lame vue à plat de face (le tranchant vers l'extérieur de la main) : `prise` bas (défaut : lame vers le sol le long de la jambe),
    haut (lame dressée au-dessus du poing, la menace) ou avant (lame pointée devant, tranchant en bas : lisible de profil) ; `sang`"""
    hc = _col(col, (44, 34, 30)); prise = cfg.get('prise', 'bas'); sang = bool(cfg.get('sang', False)); out = []; n = 9; L = .19
    if prise in ('bas', 'haut'):
        sg = -1. if prise == 'bas' else 1.
        out += [C(P(0, -sg * .005, 0), (.026, .13, .022), hc, **k), C(P(0, -sg * .071, 0), (.022, .008, .02), _sh(hc, .8), **k), C(P(.002, sg * .068, 0), (.032, .012, .026), STEEL, mat=M_METAL, **k)]
        out += [C(P(.0, -sg * y, .0115), (.006, .006, .001), STEEL, **k) for y in (.05, .015)]
        for i, (t, w) in enumerate(_blade(n, L)):
            y = sg * (.074 + L * (i + .5) / n)
            out += [C(P(-.014 + w / 2, y, 0), (w, L / n, .004), BLADE, mat=M_METAL, refl=.2, **k), C(P(-.014 + w - .0025, y, 0), (.005, L / n, .0044), (240, 244, 250), emis=.25, mat=M_METAL, **k)]
            if sang and i in (2, 3, 5): out.append(C(P(-.004, y, .0018), (.012, L / n * .8, .0006), (110, 8, 12), **k))
        return out
    out += [C(P(0, 0, -.005), (.022, .026, .13), hc, **k), C(P(0, 0, -.071), (.02, .022, .008), _sh(hc, .8), **k)]
    out += [C(P(.0115, .002, z), (.001, .006, .006), STEEL, **k) for z in (-.05, -.015)]
    out += [C(P(0, .002, .068), (.026, .032, .012), STEEL, mat=M_METAL, **k)]
    for i, (t, w) in enumerate(_blade(n, L)):
        z = .074 + L * (i + .5) / n
        out += [C(P(0, .014 - w / 2, z), (.004, w, L / n), BLADE, mat=M_METAL, refl=.2, **k), C(P(0, .014 - w + .0025, z), (.0044, .005, L / n), (240, 244, 250), emis=.25, mat=M_METAL, **k)]
        if sang and i in (1, 2, 4): out.append(C(P(0, .006 - w / 3, z), (.0036, .01, L / n * .8), (110, 8, 12), **k))
    return out


def h_bowl(P, F, k, lights, col, cfg):
    """bol tenu par le côté, devant le poing : la main serre la panse, le contenu se voit"""
    cont = cfg.get('contenu', 'soupe'); q = P(-.04, -.035, .09)
    return _bowl(q[0], q[1], q[2], _col(col, CERAM), _col(cfg.get('filet'), (60, 90, 160)), cont, k=k, spoon=bool(cfg.get('cuillere', False)), steam_=cfg.get('vapeur', cont == 'soupe'))


def h_teapot(P, F, k, lights, col, cfg):
    """théière tenue par l'anse, le bec vers l'avant (prête à verser) : panse devant le poing, frise visible de côté"""
    col = _col(col, CERAM); ink = _col(cfg.get('motif'), (50, 80, 160))
    x, y, z = P(0, -.072, .118); out = _teapot_body(x, y, z, col, k)
    out.append(C(P(.0835, -.072 + .05, .118), (.002, .02, .076), col, tex={F['out']: teapot_band(col, ink)}, **k))
    out += [C(P(0, .026, .022), (.02, .014, .034), col, **k), C(P(0, -.002, .006), (.02, .05, .014), col, **k), C(P(0, -.03, .022), (.02, .014, .034), col, **k)]
    for i in range(6):
        t = (i + .5) / 6; s = .028 - .012 * t; out.append(C(P(0, -.032 + .068 * t, .193 + .058 * t), (s, .022 - .004 * t, s), col, **k))
    return out


def h_pill_box(P, F, k, lights, col, cfg):
    """boîte de médicaments tenue entre les doigts, au-dessus du poing : étiquette vers l'avant (on la montre), posologie vers celui qui la tient"""
    nom, dose, sous, band, pat, pos = _pill_cfg(dict(cfg, color=col) if col else cfg)
    return [C(P(-.02, .072, .075), (.11, .055, .025), (246, 246, 242), mat=M_CARD, tex={F['front']: pill_top(nom, dose, sous, band, pat), F['back']: pill_back(pos, band)}, **k),
            C(P(-.02, .1, .075), (.11, .0006, .025), (230, 230, 226), **k)]


# ================================================================== registration
def enregistrer(R):
    R.objet('od_kettle', k_kettle, 'bouilloire')
    R.objet('od_coffee_maker', k_coffee_maker, 'cafetière et sa verseuse')
    R.objet('od_toaster', k_toaster, 'grille-pain')
    R.objet('od_microwave', k_microwave, 'micro-ondes')
    R.objet('od_saucepan', k_saucepan, 'casserole')
    R.objet('od_frying_pan', k_frying_pan, 'poêle')
    R.objet('od_kitchen_knife', k_kitchen_knife, 'couteau de cuisine')
    R.objet('od_cutting_board', k_cutting_board, 'planche à découper')
    R.objet('od_bowl', k_bowl, 'bol')
    R.objet('od_teapot', k_teapot, 'théière')
    R.objet('od_pill_box', k_pill_box, 'boîte de médicaments')
    R.objet('od_toothbrush_glass', k_toothbrush_glass, 'brosses à dents dans leur verre')
    R.objet('od_soap', k_soap, 'savon')
    R.objet('od_towel', k_towel, 'serviette pliée')
    R.objet('od_hair_dryer', k_hair_dryer, 'sèche-cheveux')
    R.tenu('od_kitchen_knife', h_kitchen_knife, 'couteau de cuisine (lame vers le sol vue à plat ; `prise` haut / avant)')
    R.tenu('od_bowl', h_bowl, 'bol tenu par le côté')
    R.tenu('od_teapot', h_teapot, 'théière tenue par l\'anse, bec vers l\'avant')
    R.tenu('od_pill_box', h_pill_box, 'boîte de médicaments montrée (étiquette vers l\'avant)')
