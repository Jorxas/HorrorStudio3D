"""OBJETS DÉTAILLÉS, LOT « drame » (09/11/2026), version PS1 native : objets d'un drame réaliste (série « Le Choix de Demain »), génériques.

Découvert tout seul par `objets._load_lots()` (fichier `objets_<lot>.py`) : aucune ligne à écrire ailleurs. La version VOXEL native est
`voxelgpu/b_objets_drame.py` (même plan, mêmes réglages, autre exécution) ; les images (dessins au crayon, toile de la couverture, photo d'identité,
billet de train) sont dessinées ICI et partagées par les deux versions.

Posés (face avant vers -z, x à droite vu de face, y = 0 posé ; la clé `y` du décor soulève) :
  od_carnet   carnet de dessin A5 à l'italienne (0,21 x 0,15 x 0,02 m) : toile usée (coins élimés, tranche abîmée), élastique, feuilles volantes.
              `ouvert` (défaut false : couverture en haut ; true : les deux pages, lues depuis l'avant), `dessin` (page de droite : enfant (défaut),
              deux_amis, trois_amis, vide), `legende` (une ligne à la main sous le dessin, 18 caractères), `mouille` (couverture assombrie, taches d'eau,
              pages gondolées, trait dilué), `couleur` (couverture : bleu_vert (défaut), brun, rouge, gris, vert, bleu, noir ou [r, g, b]).
              Page de gauche : petits croquis et l'étoile dessinée au coin (détail de la série).
  od_bouquet  bouquet de fleurs blanches (roses, lys, gypsophile, feuillage), papier, ruban noué (0,45 m) : couché, face en haut, fleurs vers +z
              (défaut) ou `debout` (penché vers l'arrière, contre une stèle placée derrière) ; `photo` : portrait (défaut, jeune femme souriante aux
              longs cheveux bouclés bruns) | vide | false (pas de photo) ; `couleur` des fleurs (blanc (défaut), creme, rose, jaune, rouge, mauve...),
              `ruban`, `papier` (couleurs).
  od_billet   billet de train (0,15 x 0,07 m), lisible depuis l'avant : `texte` (lignes de 14 caractères, défaut VAL-RIVE / DEPART 19:10),
              `froisse` (défaut true : plis en escalier), `couleur` (papier).
Tenus (`hold`) :
  od_carnet          fermé, debout DEVANT le poing, couverture de face (gestes `hold` à deux mains ou `chest` : contre la poitrine ; `show`)
  od_carnet_ouvert   ouvert, les pages vers celui qui le tient, centré sur le poing (tenu par le bas du dos) : à filmer par-dessus l'épaule
  od_carnet_montre   ouvert, les pages vers l'avant, tenu par son bord : on montre le dessin (geste `hold` : entre les deux poings ; `show`)
  od_bouquet         tenu par le bas, fleurs en haut, photo vers l'avant (gestes `hold`, `show` ; pas `idle` : il remonte le long du bras)
  od_billet          pincé devant le poing, recto vers l'avant (`show`)
`vers_soi: true` / `montre: true` retournent n'importe lequel. Le contenu d'un objet tenu se règle par la clé d'épisode : {"objets": {"contenu":
{"od_carnet": {"dessin": "enfant", "legende": "LINA, 6 ANS", "mouille": true}}}} ; les trois carnets tenus lisent ce réglage d'`od_carnet` (un réglage
sous `od_carnet_ouvert` / `od_carnet_montre` passe devant). Le carnet posé se règle sur le décor lui-même.
VOXEL montre le monde en miroir (les images restent lisibles) : la page du dessin y est de l'autre côté du dos qu'en PS1 ; un insert valable dans les
deux styles cadre les deux pages, ou vise x = +0,105 (PS1) / -0,105 (VOXEL) dans le repère du carnet.
Rien d'aléatoire non semé, aucune horloge, rien de gore ni d'horreur."""
import functools, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from .r3d import B, C, M_FABRIC, M_CARD
from . import objets as OD, objets_tex as T

_g, _sh, _col = OD._g, OD._sh, OD._col

# ================================================================== palettes
COVERS = {'bleu_vert': (64, 98, 100), 'brun': (112, 80, 54), 'rouge': (126, 52, 48), 'gris': (100, 100, 104), 'vert': (72, 98, 66), 'bleu': (58, 74, 112),
          'noir': (42, 42, 46), 'creme': (206, 196, 170)}
FLOWERS = {'blanc': (242, 240, 232), 'creme': (240, 228, 200), 'rose': (238, 170, 182), 'jaune': (240, 210, 96), 'rouge': (176, 36, 46), 'mauve': (176, 140, 200),
           'orange': (236, 140, 70), 'bleu': (130, 160, 220)}
PAPER_SK = (232, 224, 203)                 # papier à dessin crème (un peu sombre : sous une lampe forte, le trait reste lisible)
GRAPHITE = (42, 39, 36)                    # mine de crayon, foncée et neutre-chaude (le papier sature avant le trait ; un gris bleuté vire au magenta en VOXEL)
BOARD = (178, 168, 146)                    # carton gris-beige sous la toile (coins élimés)


def colour(v, default, names=COVERS):
    """réglage de couleur : un nom de la palette, [r, g, b], ou rien (défaut)"""
    if isinstance(v, str): return tuple(names.get(v.strip().lower(), default))
    return _col(v, default)


def _new(W, H, bg):
    im = Image.new('RGBA', (W, H), tuple(int(v) for v in bg[:3]) + (255,))
    return im, ImageDraw.Draw(im)


def _rgba(c, a=255): return tuple(int(v) for v in c[:3]) + (a,)


def _hand(d, x, y, s, col, jitter=True):
    """une ligne écrite à la main en petite police (les lettres sautent d'un texel, l'encre varie un peu) ; rend la largeur"""
    s = T.ascii_up(s); cx = x
    for i, ch in enumerate(s):
        dy = 1 if (jitter and (i * 5 + 3) % 7 == 0) else 0
        k = .86 + .14 * ((i * 3) % 4) / 3
        T.mini(d, cx, y + dy, ch, _rgba(T._shade(col, k)))
        cx += 4
    return cx - x


# ================================================================== pencil drawings (ink layer 'L' : 0 = paper, 255 = full graphite)
def _curl(d, x, y, r, a0, ink):
    """une boucle de cheveux : un arc de cercle presque fermé qui tourne (petite spirale)"""
    d.arc([x - r, y - r, x + r, y + r], a0, a0 + 290, fill=ink)
    if r >= 3: d.point((int(round(x + .4 * r * math.cos(math.radians(a0 + 300)))), int(round(y + .4 * r * math.sin(math.radians(a0 + 300))))), fill=ink)


def _hatch(d, x0, y0, x1, y1, step, ink, slope=1, mask=None):
    """hachures en biais dans un rectangle (et dans `mask` si donné : une fonction (x, y) -> bool)"""
    for k in range(-(y1 - y0), (x1 - x0) + 1, step):
        for t in range(0, y1 - y0 + 1):
            x = x0 + k + t if slope > 0 else x1 - k - t; y = y0 + t
            if x0 <= x <= x1 and (mask is None or mask(x, y)): d.point((x, y), fill=ink)


def _draw_enfant(d, W, H):
    """portrait au crayon d'une fillette d'environ six ans aux cheveux bouclés, souriante (de face, tête et épaules, tee-shirt rayé)"""
    cx, cy = W // 2, 34
    # ombre griffonnée derrière la tête, à gauche (la lumière vient de droite)
    _hatch(d, cx - 46, 8, cx - 26, 70, 3, 50, 1, lambda x, y: ((x - cx + 36) / 10.) ** 2 + ((y - cy - 6) / 26.) ** 2 <= 1.)
    # masse des boucles : couronne extérieure, couronne intérieure, boucles qui tombent jusqu'aux épaules
    for (Rx, Ry, n, ink) in ((29, 29, 18, 235), (23, 23, 15, 165)):
        for i in range(n):
            a = math.radians(-42 + i * 264 / (n - 1)); r = 3 + (i * 7 + Rx) % 3 if ink > 200 else 3
            _curl(d, cx + Rx * math.cos(a), cy - 1 - Ry * math.sin(a), r, (i * 77 + Rx) % 360, ink)
    for sx in (-1, 1):
        for (dx, dy, r) in ((29, 13, 4), (28, 21, 4), (25, 28, 3), (33, 6, 3)):
            _curl(d, cx + sx * dx, cy + dy, r, (dx * 31 + dy * 7 + (90 if sx > 0 else 0)) % 360, 225)
    hair = lambda x, y: ((x - cx) / 31.) ** 2 + ((y - cy) / 31.) ** 2 <= 1.
    _hatch(d, cx - 31, 4, cx - 10, 62, 3, 85, -1, hair)
    # visage : on efface l'encre dessous ; joues et menton au trait
    face = [cx - 15, cy - 15, cx + 15, cy + 17]
    d.ellipse(face, fill=0)
    d.arc(face, 10, 170, fill=235); d.arc(face, 170, 196, fill=140); d.arc(face, 344, 370, fill=140)
    # frange de boucles sur le front
    for i, x in enumerate(range(cx - 13, cx + 14, 6)): _curl(d, x, cy - 13 + (i % 2), 3, 190 + i * 45, 220)
    # sourcils, yeux (iris sombre, reflet, paupière, cil), nez, grand sourire, lèvre, fossettes, joues
    for sx in (-1, 1):
        ex = cx + sx * 7
        d.arc([ex - 4, cy - 9, ex + 4, cy - 4], 205, 335, fill=150)
        d.ellipse([ex - 2, cy - 2, ex + 2, cy + 2], fill=245); d.point((ex - 1, cy - 1), fill=0); d.point((ex - 1 if sx < 0 else ex, cy - 1), fill=0)
        d.arc([ex - 4, cy - 4, ex + 4, cy + 3], 200, 340, fill=215); d.point((ex + sx * 4, cy - 2), fill=200)
        for (ox, oy) in ((10, 7), (11, 8), (9, 8)): d.point((cx + sx * ox, cy + oy), fill=75)
    d.point((cx, cy + 5), fill=140); d.point((cx + 1, cy + 6), fill=170); d.point((cx - 1, cy + 7), fill=110)
    d.arc([cx - 7, cy + 3, cx + 7, cy + 13], 12, 168, fill=240)
    d.arc([cx - 4, cy + 8, cx + 4, cy + 14], 40, 140, fill=115)
    d.point((cx - 8, cy + 7), fill=160); d.point((cx + 8, cy + 7), fill=160)
    # cou, épaules, encolure ronde, tee-shirt rayé
    d.line([(cx - 5, cy + 16), (cx - 5, cy + 22)], fill=200); d.line([(cx + 5, cy + 16), (cx + 5, cy + 22)], fill=200)
    d.line([(cx - 5, cy + 22), (cx - 17, cy + 26), (cx - 26, cy + 31), (cx - 31, cy + 41)], fill=230)
    d.line([(cx + 5, cy + 22), (cx + 17, cy + 26), (cx + 26, cy + 31), (cx + 31, cy + 41)], fill=230)
    d.arc([cx - 8, cy + 17, cx + 8, cy + 27], 0, 180, fill=215)
    for y, hw in ((cy + 30, 25), (cy + 34, 28), (cy + 38, 30)):
        d.line([(cx - hw, y), (cx + hw, y)], fill=90)


def _draw_deux_amis(d, W, H):
    """deux enfants assis sur un banc, vus de dos (une tête bouclée, une tête aux cheveux courts), un arbre, l'horizon"""
    g = 64
    d.line([(4, g), (W - 5, g)], fill=110)
    for x in range(8, W - 8, 9): d.point((x, g + 3), fill=70); d.point((x + 4, g + 6), fill=60)
    # arbre à droite
    d.line([(W - 18, g), (W - 18, 30)], fill=200); d.line([(W - 17, g), (W - 17, 34)], fill=140)
    for (x, y, r) in ((W - 18, 22, 9), (W - 26, 28, 7), (W - 11, 28, 7), (W - 19, 31, 6)): d.arc([x - r, y - r, x + r, y + r], 0, 360, fill=150)
    _hatch(d, W - 30, 14, W - 6, 36, 3, 70, -1, lambda x, y: ((x - W + 18) / 12.) ** 2 + ((y - 25) / 10.) ** 2 <= 1)
    # banc : dossier (deux lattes), siège, pieds
    for y in (40, 45): d.rectangle([14, y, 86, y + 2], outline=210)
    d.rectangle([12, 54, 88, 56], outline=225)
    for x in (18, 80): d.line([(x, 47), (x, 54)], fill=200); d.line([(x, 57), (x, g)], fill=210); d.line([(x + 2, 57), (x + 2, g)], fill=140)
    # enfant de gauche (boucles), de dos
    d.ellipse([31, 22, 47, 39], fill=0)
    for j, (x, y) in enumerate(((33, 25), (39, 23), (45, 25), (32, 31), (38, 29), (44, 31), (35, 35), (41, 35), (47, 36), (31, 37))):
        _curl(d, x, y, 3, (j * 83) % 360, 215 if j % 3 else 170)
    d.line([(30, 54), (30, 42), (34, 39), (44, 39), (48, 42), (48, 54)], fill=225)
    _hatch(d, 31, 42, 47, 53, 3, 80, 1)
    # enfant de droite (cheveux courts, sac à dos), de dos, la main sur l'épaule de l'autre
    d.ellipse([57, 23, 71, 38], outline=225)
    for x in range(59, 70, 2): d.line([(x, 25), (x + (1 if x > 64 else 0), 31)], fill=150)
    d.line([(55, 54), (55, 42), (59, 39), (69, 39), (73, 42), (73, 54)], fill=225)
    d.rectangle([58, 42, 70, 52], outline=190); d.line([(60, 42), (60, 39)], fill=160); d.line([(68, 42), (68, 39)], fill=160)
    d.line([(55, 43), (50, 41), (46, 40)], fill=210)


def _draw_trois_amis(d, W, H):
    """trois enfants qui se tiennent la main devant la façade d'une école (fronton, horloge, fenêtres, porte, marches)"""
    x0, x1, top = 12, W - 13, 18
    d.polygon([(x0 + 26, top), (W // 2, top - 12), (x1 - 26, top)], outline=215)
    d.ellipse([W // 2 - 5, top - 9, W // 2 + 5, top + 1], outline=225); d.line([(W // 2, top - 4), (W // 2, top - 7)], fill=225); d.line([(W // 2, top - 4), (W // 2 + 3, top - 3)], fill=225)
    d.rectangle([x0, top, x1, 66], outline=225)
    d.line([(x0, top + 3), (x1, top + 3)], fill=150)
    for r, y in enumerate((top + 8, top + 22)):
        for x in range(x0 + 6, x1 - 8, 13):
            if r == 1 and abs(x + 4 - W // 2) < 9: continue
            d.rectangle([x, y, x + 8, y + 9], outline=200); d.line([(x + 4, y), (x + 4, y + 9)], fill=120); d.line([(x, y + 4), (x + 8, y + 4)], fill=120)
    d.rectangle([W // 2 - 6, top + 30, W // 2 + 6, 66], outline=225); d.arc([W // 2 - 6, top + 25, W // 2 + 6, top + 35], 180, 360, fill=225)
    d.line([(W // 2, top + 32), (W // 2, 66)], fill=150)
    _hatch(d, x0 + 1, top + 4, x1 - 1, 65, 4, 45, 1)
    d.line([(4, 72), (W - 5, 72)], fill=120)
    # trois enfants (la tête du milieu bouclée), main dans la main, debout devant la porte
    for i, x in enumerate((W // 2 - 26, W // 2, W // 2 + 26)):
        hy = 44 + (2 if i != 1 else 0)
        d.ellipse([x - 6, hy - 6, x + 6, hy + 6], fill=0); d.ellipse([x - 6, hy - 6, x + 6, hy + 6], outline=235)
        if i == 1:
            for k in range(9):
                a = math.radians(200 + k * 18 - 60); _curl(d, x + 7 * math.cos(a), hy + 6 * math.sin(a), 2, k * 60, 215)
        elif i == 0:
            d.arc([x - 7, hy - 8, x + 7, hy + 2], 180, 360, fill=220); d.line([(x - 6, hy - 1), (x - 7, hy + 7)], fill=200); d.line([(x + 6, hy - 1), (x + 7, hy + 7)], fill=200)
        else:
            d.arc([x - 6, hy - 7, x + 6, hy + 1], 180, 360, fill=220); d.line([(x - 6, hy - 3), (x + 6, hy - 3)], fill=150)
        d.point((x - 2, hy), fill=220); d.point((x + 2, hy), fill=220); d.arc([x - 3, hy, x + 3, hy + 4], 20, 160, fill=200)
        d.polygon([(x - 4, hy + 7), (x + 4, hy + 7), (x + 7, hy + 20), (x - 7, hy + 20)], fill=0, outline=225)
        d.line([(x - 3, hy + 20), (x - 3, 71)], fill=225); d.line([(x + 3, hy + 20), (x + 3, 71)], fill=225)
        if i < 2: d.line([(x + 6, hy + 11), (x + 13, hy + 15), (x + 20, hy + 11)], fill=210)


DRAWINGS = {'enfant': _draw_enfant, 'deux_amis': _draw_deux_amis, 'trois_amis': _draw_trois_amis}


def _draw_croquis(d, W, H):
    """page de gauche : petits croquis (arbre, chat assis, maison, oiseaux, une main, une tasse) et l'étoile dessinée au coin"""
    # l'étoile, au coin en haut à gauche (cinq branches, tracée d'un seul trait, repassée)
    cx, cy, R, r = 12, 12, 8, 3.3
    pts = [(cx + (R if k % 2 == 0 else r) * math.sin(math.radians(k * 36)), cy - (R if k % 2 == 0 else r) * math.cos(math.radians(k * 36))) for k in range(10)]
    d.polygon(pts, outline=245); d.line(pts[:3], fill=200)
    # arbre
    d.line([(26, 70), (26, 54)], fill=200); d.line([(27, 70), (27, 56)], fill=130)
    for (x, y, rr) in ((26, 46, 8), (20, 51, 5), (33, 51, 5)): d.arc([x - rr, y - rr, x + rr, y + rr], 0, 360, fill=150)
    d.line([(16, 70), (38, 70)], fill=110)
    # chat assis, de profil
    d.ellipse([52, 56, 66, 70], outline=210); d.ellipse([60, 47, 70, 57], outline=210)
    d.polygon([(61, 49), (62, 44), (64, 48)], outline=210); d.polygon([(67, 48), (69, 44), (70, 49)], outline=210)
    d.arc([46, 60, 58, 72], 90, 250, fill=200); d.point((66, 51), fill=230)
    # maison
    d.rectangle([84, 26, 102, 40], outline=200); d.polygon([(82, 27), (93, 17), (104, 27)], outline=210); d.rectangle([91, 32, 95, 40], outline=150)
    d.rectangle([86, 29, 89, 32], outline=130); d.line([(98, 20), (98, 16), (100, 16), (100, 22)], fill=150)
    # oiseaux
    for (x, y) in ((40, 18), (48, 14), (55, 20)): d.arc([x - 3, y - 2, x, y + 2], 200, 340, fill=170); d.arc([x, y - 2, x + 3, y + 2], 200, 340, fill=170)
    # une main esquissée (doigts) et une tasse
    d.line([(80, 71), (80, 58)], fill=170); d.arc([80, 62, 88, 68], 180, 300, fill=150)
    for k in range(5):
        a = math.radians(k * 72 - 90); x, y = 80 + 4 * math.cos(a), 54 + 4 * math.sin(a); d.ellipse([x - 2, y - 2, x + 2, y + 2], outline=180)
    d.point((80, 54), fill=200)
    d.rectangle([98, 60, 108, 70], outline=170); d.arc([106, 62, 112, 68], 270, 450, fill=170)
    for k in range(3): d.line([(100 + k * 3, 57), (101 + k * 3, 53)], fill=70)
    # quelques traits d'essai
    d.line([(40, 34), (52, 30)], fill=60); d.line([(41, 37), (55, 32)], fill=50); d.line([(42, 40), (50, 37)], fill=50)


def _paper(W, H, paper, seed):
    """papier à dessin : grain discret (déterministe)"""
    a = np.empty((H, W, 4), np.uint8); a[..., :3] = paper; a[..., 3] = 255
    yy, xx = np.mgrid[0:H, 0:W]
    m = ((xx * 7 + yy * 13 + seed * 5) % 23 == 0) | ((xx * 11 + yy * 5 + seed) % 31 == 0)
    a[m, :3] = np.array(T._shade(paper, .955), np.uint8)
    return a


def _tide(a, spots, col=(176, 150, 112)):
    """auréoles d'eau séchée : bords plus sombres, intérieur un peu plus pâle"""
    H, W = a.shape[:2]; yy, xx = np.mgrid[0:H, 0:W]
    for (x, y, rx, ry) in spots:
        q = ((xx - x) / rx) ** 2 + ((yy - y) / ry) ** 2
        wob = .1 * np.sin(xx * .9 + yy * .7)
        inner = q < .82 + wob; rim = (q >= .82 + wob) & (q < 1. + wob)
        a[inner, :3] = (a[inner, :3].astype(np.float32) * .97).astype(np.uint8)
        a[rim, :3] = (a[rim, :3].astype(np.float32) * .6 + np.array(col, np.float32) * .4).astype(np.uint8)
    return a


def _ink_to_rgba(ink, paper, mouille, seed, legende='', W=0):
    """compose le calque d'encre sur le papier ; `mouille` : trait dilué (flou, plus pâle) et auréoles"""
    lay = ink
    if mouille: lay = ink.filter(ImageFilter.GaussianBlur(.5))
    al = np.minimum(1., np.asarray(lay, np.float32) / 255. * (1.3 if mouille else 1.15))
    H, Wd = al.shape
    a = _paper(Wd, H, T._shade(paper, .93) if mouille else paper, seed).astype(np.float32)
    gc = np.array((54, 50, 48) if mouille else GRAPHITE, np.float32)
    a[..., :3] = a[..., :3] * (1 - al[..., None]) + gc * al[..., None]
    return a.astype(np.uint8)


@functools.lru_cache(maxsize=32)
def sketch_page(dessin='enfant', legende='', mouille=False, W=120, H=86):
    """page de droite du carnet : le dessin au crayon (`dessin` : enfant, deux_amis, trois_amis, vide) et sa légende manuscrite"""
    ink = Image.new('L', (W, H), 0); d = ImageDraw.Draw(ink)
    fn = DRAWINGS.get(str(dessin))
    if fn: fn(d, W, H)
    a = _ink_to_rgba(ink, PAPER_SK, mouille, 1)
    im = Image.fromarray(a, 'RGBA'); dd = ImageDraw.Draw(im)
    t = T.ascii_up(legende)[:18]
    if t: _hand(dd, max(2, (W - T.mini_w(t)) // 2), H - 9, t, (74, 66, 62) if mouille else (36, 33, 30))
    a = np.array(im)
    if mouille: a = _tide(a, ((W * .78, H * .3, 16, 12), (W * .18, H * .74, 12, 9)))
    return a


@functools.lru_cache(maxsize=4)
def croquis_page(mouille=False, W=120, H=86):
    """page de gauche : croquis et étoile au coin"""
    ink = Image.new('L', (W, H), 0); d = ImageDraw.Draw(ink); _draw_croquis(d, W, H)
    a = _ink_to_rgba(ink, PAPER_SK, mouille, 2)
    if mouille: a = _tide(a, ((W * .55, H * .6, 18, 13),))
    return a


@functools.lru_cache(maxsize=32)
def spread(dessin='enfant', legende='', mouille=False, W=120, H=86):
    """les deux pages ouvertes (gauche : croquis et étoile ; droite : le dessin), ombre du pli au milieu ; une seule image (l'ordre des pages ne bouge jamais)"""
    a = np.concatenate([croquis_page(bool(mouille), W, H), sketch_page(str(dessin), str(legende), bool(mouille), W, H)], 1).astype(np.float32)
    for k, f in enumerate((.72, .8, .88, .94)):
        a[:, W - 1 - k, :3] *= f; a[:, W + k, :3] *= f
    if mouille:                                                            # gondolé : bandes d'ombre douces
        for y in range(H): a[y, :, :3] *= .965 + .035 * math.cos(y * .3)
    return np.clip(a, 0, 255).astype(np.uint8)


# ================================================================== canvas cover, spine, page edges
@functools.lru_cache(maxsize=16)
def canvas(col=COVERS['bleu_vert'], mouille=False, W=84, H=60, seed=0):
    """toile de couverture usée : trame croisée, coins élimés (le carton gris-beige apparaît), fils effilochés au bord, éraflures ; `mouille` :
    toile assombrie et auréoles d'eau. Image symétrique à l'échelle de la mise en page (rien à lire)"""
    base = T._shade(col, .8) if mouille else tuple(col)
    a = np.empty((H, W, 4), np.uint8); a[..., 3] = 255
    yy, xx = np.mgrid[0:H, 0:W]
    k = np.where((xx + yy) % 2 == 0, 1.06, .93) * np.where(yy % 3 == 0, .95, 1.) * np.where(xx % 4 == 1, 1.03, 1.)
    a[..., :3] = np.clip(np.array(base, np.float32)[None, None] * k[..., None], 0, 255).astype(np.uint8)
    edge = np.minimum(np.minimum(xx, W - 1 - xx), np.minimum(yy, H - 1 - yy))
    fray = (edge == 0) & ((xx * 3 + yy * 5 + seed) % 4 != 0)
    a[fray, :3] = np.array(T._shade(base, 1.35), np.uint8)
    for (cx, cy) in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)):
        r = np.hypot(xx - cx, yy - cy); rr = 5.5 + 1.5 * np.sin((xx * 1.7 + yy * 2.3) + seed)
        worn = r < rr; a[worn, :3] = np.array(T._shade(BOARD, .9 if mouille else 1.), np.uint8)
        thr = (r >= rr) & (r < rr + 1.2) & ((xx + yy) % 2 == 0); a[thr, :3] = np.array(T._shade(base, 1.45), np.uint8)
    for (x, y, L) in ((W * .3, H * .35, 6), (W * .62, H * .7, 5), (W * .7, H * .22, 4)):
        for t in range(int(L)): a[min(H - 1, int(y + t * .5)), min(W - 1, int(x + t)), :3] = T._shade(base, 1.22)
    if mouille: a = _tide(a, ((W * .35, H * .45, 15, 11), (W * .72, H * .3, 10, 8)), col=T._shade(base, .7))
    return a


@functools.lru_cache(maxsize=8)
def spine(col=COVERS['bleu_vert'], mouille=False, W=60, H=8):
    """tranche (dos) abîmée : toile qui s'effiloche, une déchirure qui montre le carton, fils qui pendent"""
    base = T._shade(col, .62 if mouille else .82)
    a = np.empty((H, W, 4), np.uint8); a[..., 3] = 255
    yy, xx = np.mgrid[0:H, 0:W]
    a[..., :3] = np.clip(np.array(base, np.float32)[None, None] * np.where((xx + yy) % 2 == 0, 1.07, .92)[..., None], 0, 255).astype(np.uint8)
    a[(yy == 0) | (yy == H - 1), :3] = T._shade(base, 1.4)
    t0, t1 = int(W * .58), int(W * .78)
    a[2:H - 2, t0:t1, :3] = BOARD; a[2:H - 2, t0, :3] = T._shade(base, 1.5); a[2:H - 2, t1 - 1, :3] = T._shade(base, 1.5)
    for x in range(t0 + 2, t1 - 2, 3): a[min(H - 1, 2 + (x % 3)), x, :3] = T._shade(base, 1.6)
    for x in range(0, W, 7): a[H // 2, x, :3] = T._shade(base, 1.3)
    return a


@functools.lru_cache(maxsize=4)
def page_block(W=60, H=8, wavy=False):
    """tranche des pages vue de côté : feuilles serrées (et gondolées si mouillées)"""
    a = np.empty((H, W, 4), np.uint8); a[..., 3] = 255; a[..., :3] = (232, 224, 204)
    for y in range(0, H, 2):
        for x in range(W):
            yy = y + (int(1.2 * math.sin(x * .5 + y)) if wavy else 0)
            if 0 <= yy < H: a[yy, x, :3] = (204, 194, 170)
    return a


# ================================================================== the ID photo hung on the bouquet's ribbon
@functools.lru_cache(maxsize=8)
def id_photo(sujet='portrait', W=32, H=40):
    """photo d'identité : `portrait` = jeune femme souriante aux longs cheveux bouclés bruns, fond gris-bleu clair, liseré blanc ; `vide` : fond seul"""
    im, d = _new(W, H, (250, 250, 246))
    bg = (176, 194, 210); d.rectangle([1, 1, W - 2, H - 2], fill=_rgba(bg))
    for y in range(1, H - 1): d.line([(1, y), (W - 2, y)], fill=_rgba(T._shade(bg, 1.06 - .12 * y / H)))
    if sujet != 'vide':
        cx = W / 2; hair, hl, dk = (88, 54, 34), (132, 88, 56), (58, 34, 22); skin = (232, 192, 160); sk2 = (210, 164, 130)
        d.ellipse([cx - 11, 5, cx + 11, 30], fill=_rgba(hair))
        d.rectangle([cx - 12, 14, cx + 12, H - 6], fill=_rgba(hair))
        for (x, y) in ((cx - 12, 18), (cx - 13, 24), (cx - 12, 30), (cx - 13, 35), (cx + 11, 18), (cx + 12, 24), (cx + 11, 30), (cx + 12, 35), (cx - 6, 6), (cx + 4, 5)):
            d.arc([x - 2, y - 2, x + 2, y + 2], 0, 300, fill=_rgba(hl))
        d.rectangle([cx - 15, H - 8, cx + 15, H - 2], fill=(150, 64, 72, 255)); d.polygon([(cx - 4, H - 8), (cx + 4, H - 8), (cx, H - 4)], fill=_rgba(skin))
        d.rectangle([cx - 2, 27, cx + 1, H - 8], fill=_rgba(sk2))
        d.ellipse([cx - 7, 9, cx + 7, 28], fill=_rgba(skin))
        d.polygon([(cx - 8, 9), (cx + 7, 8), (cx + 4, 13), (cx - 2, 12), (cx - 6, 15)], fill=_rgba(hair))
        for sx in (-1, 1):
            ex = int(cx + sx * 3.5 - (1 if sx > 0 else 0))
            d.line([(ex - 1, 14), (ex + 1, 14)], fill=_rgba(hl)); d.line([(ex - 1, 17), (ex + 1, 17)], fill=(244, 240, 234, 255))
            d.point((ex, 17), fill=(44, 30, 24, 255)); d.line([(ex - 1, 16), (ex + 1, 16)], fill=(40, 26, 22, 255))
        d.point((int(cx) - 1, 20), fill=_rgba(sk2)); d.point((int(cx), 21), fill=_rgba(sk2))
        d.line([(cx - 3, 23), (cx + 2, 23)], fill=(250, 246, 240, 255)); d.line([(cx - 4, 22), (cx - 3, 23)], fill=(176, 80, 80, 255)); d.line([(cx + 2, 23), (cx + 3, 22)], fill=(176, 80, 80, 255))
        d.line([(cx - 3, 24), (cx + 2, 24)], fill=(196, 104, 100, 255))
        for (x, y) in ((cx - 6, 20), (cx + 5, 20)): d.point((int(x), y), fill=(226, 160, 140, 255))
    return np.array(im)


# ================================================================== train ticket
TICKET = ('VAL-RIVE', 'DEPART 19:10')


@functools.lru_cache(maxsize=16)
def ticket(texte=TICKET, froisse=True, W=80, H=38, paper=(238, 230, 212)):
    """billet de train : bandeau de couleur « BILLET » et petit train, lignes lisibles (14 caractères), code-barres, pointillés ;
    `froisse` : plis (traits clairs et sombres)"""
    im, d = _new(W, H, paper)
    band = (40, 92, 120)
    d.rectangle([0, 0, W - 1, 8], fill=_rgba(band)); T.mini(d, 3, 2, 'BILLET', (246, 244, 236, 255)); T.mini(d, W - 22, 2, '2E CL', (200, 222, 232, 255))
    d.rectangle([28, 2, 39, 5], fill=(246, 244, 236, 255)); d.polygon([(39, 2), (41, 5), (39, 5)], fill=(246, 244, 236, 255))
    for x in (30, 33, 36): d.point((x, 3), fill=_rgba(band))
    for x in (30, 37): d.point((x, 6), fill=(246, 244, 236, 255))
    ink = (30, 32, 44); y = 12
    for j, l in enumerate(list(texte)[:3]):
        t = T.ascii_up(l)[:14]
        T.mini(d, 4, y, t, _rgba(ink)); y += 8
    for x in range(W - 15, W - 3):
        if (x * 7) % 5 < 3: d.line([(x, 13), (x, 30)], fill=(26, 26, 30, 255))
    for x in range(2, W - 2, 3): d.point((x, H - 5), fill=_rgba(T._shade(paper, .7)))
    d.rectangle([0, 0, W - 1, H - 1], outline=_rgba(T._shade(paper, .82)))
    a = np.array(im)
    if froisse:
        for x in (W // 4, W // 2 + 2, 3 * W // 4):
            for yy in range(H):
                xx = min(W - 1, max(0, x + (yy * 3) // H - 1))
                a[yy, xx, :3] = (a[yy, xx, :3].astype(np.float32) * .78).astype(np.uint8)
                if xx + 1 < W: a[yy, xx + 1, :3] = np.clip(a[yy, xx + 1, :3].astype(np.float32) * 1.08, 0, 255).astype(np.uint8)
        for t in range(18):
            xx, yy = 6 + t * 2, 30 - t
            if 0 <= yy < H: a[yy, xx, :3] = (a[yy, xx, :3].astype(np.float32) * .86).astype(np.uint8)
    return a


@functools.lru_cache(maxsize=4)
def ticket_back(W=80, H=38, paper=(238, 230, 212)):
    """dos du billet : piste magnétique brune, petites lignes de conditions"""
    im, d = _new(W, H, T._shade(paper, .96))
    d.rectangle([0, 6, W - 1, 12], fill=(92, 62, 40, 255))
    for y in range(18, H - 4, 4): d.line([(4, y), (W - 5 - (y * 7) % 13, y)], fill=_rgba(T._shade(paper, .75)))
    d.rectangle([0, 0, W - 1, H - 1], outline=_rgba(T._shade(paper, .8)))
    return np.array(im)


@functools.lru_cache(maxsize=2)
def scrap(W=40, H=10):
    """bout de feuille volante qui dépasse du carnet : le bas d'un croquis (un arc, deux traits, une hachure), seule partie visible"""
    ink = Image.new('L', (W, H), 0); d = ImageDraw.Draw(ink)
    d.arc([3, -8, 19, 8], 0, 180, fill=170); d.line([(22, 2), (34, 7)], fill=140); d.line([(24, 1), (37, 4)], fill=90)
    for x in range(6, 16, 3): d.line([(x, 1), (x + 2, 4)], fill=80)
    return _ink_to_rgba(ink, (244, 240, 228), False, 3)


# ================================================================== settings shared by both versions
DRAW_ALIAS = {'portrait': 'enfant', 'fillette': 'enfant', 'banc': 'deux_amis', 'deux': 'deux_amis', 'ecole': 'trois_amis', 'trois': 'trois_amis'}
PAGE = (232, 224, 204); ELASTIC = (30, 28, 32); SHEET = (246, 242, 232); OLD_SHEET = (232, 220, 188)
GREEN, GREEN2, GREEN3 = (78, 120, 64), (56, 96, 54), (40, 72, 46)
PAPERS = {'kraft': (178, 146, 104), 'blanc': (238, 236, 230), 'creme': (232, 222, 196)}
TICKET_PAPERS = {'creme': (238, 230, 212), 'blanc': (244, 242, 236), 'rose': (240, 216, 214), 'vert': (214, 230, 214)}


def pick(v, c, default, names):
    """couleur réglée (`couleur`) ou donnée à part (`color`, couleur du personnage) : nom de palette ou [r, g, b] ; tout le reste -> défaut"""
    for x in (v, c):
        if x is None or (hasattr(x, '__len__') and len(x) == 0): continue
        if isinstance(x, str): return tuple(names.get(x.strip().lower(), default))
        try:
            xs = list(x)
            if all(isinstance(t, str) for t in xs): return tuple(names.get(''.join(xs).strip().lower(), default))     # tuple('brun') (objets.held)
            return tuple(int(t) for t in xs[:3])
        except (TypeError, ValueError): continue
    return tuple(default)


def merged(name, cfg):
    """contenu d'un carnet tenu : celui réglé sous `od_carnet` (clé d'épisode), puis le sien par-dessus"""
    p = dict(OD._cfg('od_carnet')) if name != 'od_carnet' else {}
    p.update(cfg or {})
    return p


def carnet_params(p, c=None):
    """-> (couleur de couverture, ouvert, dessin, légende, mouillé)"""
    col = pick(_g(p, 'couleur', 'colour'), c if c is not None else p.get('color'), COVERS['bleu_vert'], COVERS)
    d = _g(p, 'dessin', 'drawing', default='enfant')
    d = 'vide' if d in (False, None, '', 'none', 'aucun') else DRAW_ALIAS.get(str(d), str(d))
    return col, bool(_g(p, 'ouvert', 'open', default=False)), d, str(_g(p, 'legende', 'caption', default='') or '')[:18], bool(_g(p, 'mouille', 'wet', default=False))


def bouquet_params(p, c=None):
    """-> (fleurs, ruban, papier, photo (sujet ou None), debout)"""
    fl = pick(_g(p, 'couleur', 'colour'), c if c is not None else p.get('color'), FLOWERS['blanc'], FLOWERS)
    rib = pick(_g(p, 'ruban', 'ribbon'), None, (168, 146, 190), FLOWERS); pap = pick(_g(p, 'papier', 'paper'), None, PAPERS['kraft'], PAPERS)
    ph = _g(p, 'photo', default='portrait')
    ph = None if ph in (False, None, 'none', 'aucune', '') else ('vide' if ph == 'vide' else 'portrait')
    return fl, rib, pap, ph, bool(_g(p, 'debout', 'standing', default=False))


def billet_params(p, c=None):
    """-> (lignes du billet, froissé, papier)"""
    pap = pick(_g(p, 'couleur', 'colour'), c if c is not None else p.get('color'), TICKET_PAPERS['creme'], TICKET_PAPERS)
    tx = tuple(T.ascii_up(x)[:14] for x in T.lines(_g(p, 'texte', 'text'), TICKET))[:3]
    return tx, bool(_g(p, 'froisse', 'crumpled', default=True)), pap


def segs(n, W): return [(W * i // n, W * (i + 1) // n) for i in range(n)]


def cols(img, a, b): return np.ascontiguousarray(np.asarray(img)[:, a:b])


def rows(img, a, b): return np.ascontiguousarray(np.asarray(img)[a:b])


# ================================================================== geometry helpers
from . import objets_souvenirs as S                                     # helpers shared by the lots: _shift, _floor, _lay_up, _hold, _grip, _face


def lean(bx, k, top=None, ref=None):
    """penche un objet debout (cisaillement en escalier, boîte par boîte) : z += k * y (le haut recule), ou z += k * (top - y) si `top` (le bas recule) ;
    `ref` : {indice: y} pour qu'un groupe (nœud, pans, photo) glisse d'un bloc au lieu de se déformer"""
    ref = ref or {}
    for i, b in enumerate(bx):
        yc = ref.get(i, float(b.lo[1] + b.hi[1]) / 2); dz = k * (yc if top is None else (top - yc))
        b.lo = b.lo + np.array([0, 0, dz], np.float32); b.hi = b.hi + np.array([0, 0, dz], np.float32)
    return bx


# ================================================================== the objects (PS1), local frame
def b_carnet_ferme(col, mouille):
    """carnet fermé posé à plat, couverture en haut : plat de dos, bloc de pages (tranches lignées), plat de couverture en toile usée, tranche (dos) abîmée
    à gauche, élastique de fermeture, trois feuilles volantes qui dépassent (tranche, tête, pied : un coin de croquis)"""
    cw = T._shade(col, .8) if mouille else col; pg = page_block(60, 8, mouille); cv = canvas(col, mouille); out = []
    out += [B((-.105, 0, -.075), (.21, .003, .15), _sh(cw, .9), mat=M_FABRIC), B((-.102, .003, -.072), (.204, .014, .144), PAGE, tex={'+x': pg, '-z': pg, '+z': pg})]
    tops = []
    if mouille:                                                         # pages gonflées : la couverture monte vers la tranche, en trois marches
        for i, (a, b) in enumerate(segs(3, cv.shape[1])):
            x0 = -.105 + .07 * i; y = .017 + .0013 * i; tops.append((x0, x0 + .07, y + .003))
            out.append(B((x0, y, -.075), (.07, .003, .15), cw, tex={'+y': T.flat(cols(cv, a, b))}))
    else:
        out.append(B((-.105, .017, -.075), (.21, .003, .15), cw, tex={'+y': T.flat(cv)})); tops.append((-.105, .105, .02))
    out.append(B((-.109, -.0002, -.0755), (.0045, .0206, .151), _sh(cw, .82), tex={'-x': spine(col, mouille)}))
    ty = max(t[2] for t in tops if t[0] <= .074 <= t[1] + 1e-6)
    out += [B((.07, ty, -.0752), (.008, .0012, .1504), ELASTIC), B((.07, 0, -.0765), (.008, ty + .0012, .0013), ELASTIC), B((.07, 0, .0752), (.008, ty + .0012, .0013), ELASTIC)]
    out += [B((.05, .0085, -.052), (.068, .0008, .095), SHEET), B((-.04, .0125, .02), (.085, .0008, .07), OLD_SHEET),
            B((-.085, .0055, -.075), (.05, .0008, .029), (244, 240, 228)), B((-.085, .0055, -.086), (.05, .0008, .011), (244, 240, 228), tex={'+y': T.flat(scrap())})]
    return out


def b_carnet_ouvert(col, dessin, legende, mouille):
    """carnet ouvert posé à plat : deux plats de toile, le dos au milieu, deux blocs de pages, les deux pages (une seule image : croquis et étoile à gauche,
    le dessin à droite, lues depuis l'avant ; `mouille` : gondolées en quatre bandes), l'élastique qui sort à droite, une feuille volante qui dépasse en haut"""
    cw = T._shade(col, .8) if mouille else col; pg = page_block(60, 8, mouille); sp = spread(dessin, legende, mouille); out = []
    out += [B((-.214, 0, -.077), (.212, .003, .154), cw, mat=M_FABRIC), B((.002, 0, -.077), (.212, .003, .154), cw, mat=M_FABRIC),
            B((-.006, 0, -.077), (.012, .0026, .154), _sh(cw, .7))]
    out += [B((-.207, .003, -.072), (.204, .008, .144), PAGE, tex={'-z': pg, '+z': pg, '-x': pg}),
            B((.003, .003, -.072), (.204, .008, .144), PAGE, tex={'-z': pg, '+z': pg, '+x': pg})]
    H = sp.shape[0]
    if mouille:
        for i, (a, b) in enumerate(segs(4, H)):
            z1 = .072 - .144 * a / H; z0 = .072 - .144 * b / H; dy = (0., .0012, .0004, .0016)[i]
            out.append(B((-.207, .011 + dy, z0), (.414, .001, z1 - z0), PAPER_SK, tex={'+y': T.flat(rows(sp, a, b))}))
    else:
        out.append(B((-.207, .011, -.072), (.414, .001, .144), PAPER_SK, tex={'+y': T.flat(sp)}))
    out += [B((.205, .0005, -.046), (.022, .0012, .008), ELASTIC), B((.222, 0, -.06), (.007, .0012, .12), ELASTIC)]
    out.append(B((-.16, .0102, .05), (.075, .0006, .052), OLD_SHEET))
    return out


def b_carnet_debout(col, mouille):
    """carnet fermé debout (pour le tenir) : couverture vers -z, dos (tranche) à gauche, y de 0 à 0,15 ; élastique vertical, feuilles volantes qui
    dépassent de la tranche et du pied"""
    cw = T._shade(col, .8) if mouille else col; pg = page_block(60, 8, mouille); pgv = np.ascontiguousarray(np.rot90(pg)); out = []
    cv = canvas(col, mouille)
    if mouille:
        for i, (a, b) in enumerate(segs(3, cv.shape[1])):
            out.append(B((-.105 + .07 * i, 0, -.01 - .0013 * i), (.07, .15, .003), cw, tex={'-z': cols(cv, a, b)}))
    else: out.append(B((-.105, 0, -.01), (.21, .15, .003), cw, tex={'-z': cv}))
    out += [B((-.105, 0, .007), (.21, .15, .003), _sh(cw, .92), tex={'+z': canvas(col, mouille, seed=1)}),
            B((-.102, .003, -.007), (.204, .144, .014), PAGE, tex={'+x': pgv, '+y': T.flat(pg), '-y': pg}),
            B((-.109, -.0005, -.0105), (.0045, .151, .0215), _sh(cw, .82), tex={'-x': np.ascontiguousarray(np.rot90(spine(col, mouille)))})]
    zf = -.0102 - (.0026 if mouille else 0.)
    out += [B((.07, -.0012, zf - .0012), (.008, .1524, .0012), ELASTIC), B((.07, -.0012, .0101), (.008, .1524, .0012), ELASTIC),
            B((.07, .15, zf - .0012), (.008, .0012, .0125 - zf), ELASTIC), B((.07, -.0012, zf - .0012), (.008, .0012, .0125 - zf), ELASTIC)]
    out += [B((.05, .03, -.002), (.068, .09, .0008), SHEET), B((-.06, -.012, .002), (.075, .08, .0008), OLD_SHEET)]
    return out


def b_carnet_ouvert_debout(col, dessin, legende, mouille):
    """carnet ouvert debout (pour le tenir) : les deux pages vers -z (une image), les plats de toile derrière (+z), l'élastique qui pend, une feuille volante"""
    cw = T._shade(col, .8) if mouille else col; pg = page_block(60, 8, mouille); sp = spread(dessin, legende, mouille); out = []
    out += [B((-.214, 0, 0), (.212, .154, .003), cw, tex={'+z': canvas(col, mouille, seed=1)}), B((.002, 0, 0), (.212, .154, .003), cw, tex={'+z': canvas(col, mouille, seed=2)}),
            B((-.006, 0, 0), (.012, .154, .0042), _sh(cw, .7))]
    out += [B((-.207, .005, -.008), (.204, .144, .008), PAGE, tex={'+y': T.flat(pg), '-y': pg}), B((.003, .005, -.008), (.204, .144, .008), PAGE, tex={'+y': T.flat(pg), '-y': pg})]
    H = sp.shape[0]
    if mouille:
        for i, (a, b) in enumerate(segs(4, H)):
            y1 = .149 - .144 * a / H; y0 = .149 - .144 * b / H; dz = (0., .0012, .0004, .0016)[i]
            out.append(B((-.207, y0, -.0088 - dz), (.414, y1 - y0, .0008), PAPER_SK, tex={'-z': rows(sp, a, b)}, texemis=.12))
    else:
        out.append(B((-.207, .005, -.0088), (.414, .144, .0008), PAPER_SK, tex={'-z': sp}, texemis=.12))                # lueur du papier (comme od_paper) : lisible à contre-jour
    out += [B((.17, -.016, .003), (.008, .17, .0012), ELASTIC), B((-.17, .1, -.006), (.07, .07, .0006), OLD_SHEET)]
    return out


def k_carnet(p, c):
    col, ouvert, dessin, leg, m = carnet_params(p, c)
    return b_carnet_ouvert(col, dessin, leg, m) if ouvert else b_carnet_ferme(col, m)


ROSES = ((-.05, .31, -.04), (.047, .318, -.045), (-.004, .355, -.012), (-.05, .36, .036), (.056, .352, .03), (.008, .392, .048), (-.002, .312, -.066))
LILIES = ((-.09, .345, -.004), (.09, .356, -.012), (0., .41, .012))
KNOT_Y = .15                                                            # hauteur du ruban (le groupe photo + nœud + pans glisse d'un bloc quand le bouquet penche)
CONE = (.04, 8, .03, .05, .022)                                          # cornet : bas, rangs, hauteur d'un rang, largeur du bas, élargissement par rang
CONE_TOP = CONE[0] + CONE[1] * CONE[2]


def cone_w(y):
    """largeur du cornet (x) à la hauteur y ; profondeur = 0,62 x largeur"""
    i = max(0, min(CONE[1] - 1, int((y - CONE[0]) / CONE[2]))); return CONE[3] + CONE[4] * i


@functools.lru_cache(maxsize=8)
def rose_top(col=FLOWERS['blanc'], S_=10):
    """rose vue de dessus : pétales en anneaux, cœur serré (image symétrique : rien à lire)"""
    im, d = _new(S_, S_, col); c = (S_ - 1) / 2
    for r, k in ((4.5, .86), (3., .78), (1.6, .7)): d.ellipse([c - r, c - r, c + r, c + r], outline=_rgba(T._shade(col, k)))
    d.rectangle([c - .5, c - .5, c + .5, c + .5], fill=_rgba(T._shade(col, .62)))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def rose_side(col=FLOWERS['blanc'], W=10, H=8):
    """rose vue de côté : bords des pétales en arcs (symétrique gauche-droite)"""
    im, d = _new(W, H, col)
    for (x0, x1, y) in ((0, W - 1, 1), (1, W // 2, 4), (W // 2 - 1, W - 2, 4)): d.arc([x0, y, x1, y + 6], 200, 340, fill=_rgba(T._shade(col, .8)))
    d.line([(0, H - 1), (W - 1, H - 1)], fill=_rgba(T._shade(col, .75)))
    return np.array(im)


def b_bouquet(fl, rib, pap, photo, marks=None):
    """bouquet debout (pour le tenir ; posé, il est couché ou penché) : tiges coupées, cornet de papier kraft plié (huit rangs), papier de soie en couronne,
    ruban autour du cornet, la petite photo glissée sous le ruban (vers -z), nœud à deux boucles sur le côté et ses pans, sept roses (pétales en anneaux),
    trois lys (six pétales, étamines), gypsophile, feuillage ; y de 0 à 0,46. `marks` (dict) reçoit les indices du groupe photo + nœud + pans"""
    fl2, fl3 = _sh(fl, .88), _sh(fl, .72); out = []
    rt, rs = rose_top(tuple(fl)), rose_side(tuple(fl))
    for i, (x, z) in enumerate(((-.016, -.006), (-.006, .008), (.004, -.01), (.014, .004), (0., 0.), (-.012, .014), (.01, .014))):
        out += [B((x * 1.5 - .003, 0, z * 1.5 - .003), (.006, .045, .006), GREEN if i % 2 else GREEN2), B((x - .003, .045, z - .003), (.006, .16, .006), GREEN2),
                B((x * 1.5 - .0035, 0, z * 1.5 - .0035), (.007, .0025, .007), (178, 198, 134))]
    y0c, n, h, _, _ = CONE
    for i in range(n):
        y0 = y0c + i * h; w = cone_w(y0); d = w * .62
        out += OD.rnd2(0, y0, .006, w, h, d, _sh(pap, 1. - .04 * (i % 2)), mat=M_CARD)
        if i % 2 == 0: out.append(C((-.03 + i * .004, y0 + h, .006 - d / 2 - .0006), (.004, 2 * h if i < n - 1 else h, .0012), _sh(pap, .74)))
    for kk in range(10):
        a = math.radians(kk * 36 + 18); wt = cone_w(CONE_TOP - .01) / 2
        out.append(C((math.cos(a) * wt, CONE_TOP + (.012 if kk % 2 else 0.), .006 + math.sin(a) * wt * .62), (.034, .03 + (.012 if kk % 2 else 0.), .022), (246, 244, 238)))
    wr = cone_w(KNOT_Y) + .006; dr = wr * .62
    out += OD.rnd2(0, KNOT_Y - .015, .006, wr, .018, dr, rib, mat=M_FABRIC)
    k0 = len(out); zf = .006 - dr / 2                                   # devant du ruban
    if photo:                                                           # photo glissée sous le ruban (devant le rang le plus large qu'elle couvre), un brin de ruban devant son bas
        zp = min(zf, .006 - cone_w(KNOT_Y + .036) * .31) - .003
        out += [B((-.02, KNOT_Y - .012, zp - .0016), (.04, .05, .0016), (250, 250, 246), tex={'-z': id_photo(photo)}),
                B((-.025, KNOT_Y - .015, zp - .0034), (.05, .018, .0016), rib, mat=M_FABRIC)]
    bx_ = .056
    out += [C((bx_ - .018, KNOT_Y + .002, zf - .004), (.03, .022, .01), rib, mat=M_FABRIC), C((bx_ + .018, KNOT_Y + .002, zf - .002), (.03, .022, .01), rib, mat=M_FABRIC),
            C((bx_, KNOT_Y - .004, zf - .008), (.012, .016, .01), _sh(rib, .82))]
    out += OD.line((bx_ - .004, KNOT_Y - .012, zf - .007), (bx_ - .016, KNOT_Y - .08, zf - .01), .009, rib, n=3) + OD.line((bx_ + .004, KNOT_Y - .012, zf - .006), (bx_ + .02, KNOT_Y - .072, zf - .008), .009, rib, n=3)
    if marks is not None: marks['knot'] = (k0, len(out))
    for (x, y, z) in ROSES:
        out += [C((x, y - .024, z), (.02, .008, .02), GREEN2), C((x, y, z), (.052, .04, .052), fl, tex={'-z': rs, '+z': rs, '-x': rs, '+x': rs}),
                C((x, y + .004, z), (.038, .05, .038), fl2), C((x, y + .0295, z), (.03, .003, .03), fl, tex={'+y': T.flat(rt)})]
    for (x, y, z) in LILIES:
        c0 = np.array((x, y, z))
        out.append(C(tuple(c0), (.016, .02, .016), (222, 232, 190)))
        for kk in range(6):
            a = math.radians(kk * 60 + 30); tip = c0 + np.array((math.cos(a) * .058, .026, math.sin(a) * .046))
            out += OD.line(tuple(c0 + (0, .006, 0)), tuple(tip), .013, fl if kk % 2 else fl2, n=2)
        for kk in range(3):
            a = math.radians(kk * 120); dx, dz = math.cos(a) * .008, math.sin(a) * .008
            out += [C((x + dx, y + .016, z + dz), (.0015, .02, .0015), (206, 216, 160)), C((x + dx, y + .028, z + dz), (.005, .004, .005), (170, 82, 40))]
    for kk in range(12):
        a = math.radians(kk * 30 + 7); r = .1 + .012 * (kk % 3)
        out.append(C((math.cos(a) * r, .31 + .07 * ((kk * 7) % 5) / 5, .006 + math.sin(a) * r * .75), (.009, .009, .009), (250, 250, 248)))
    for kk in range(9):
        a = math.radians(kk * 40 + 20)
        out += OD.line((math.cos(a) * .05, .29, .006 + math.sin(a) * .04), (math.cos(a) * .135, .31 + .014 * (kk % 2), .006 + math.sin(a) * .1), .017, GREEN if kk % 2 else GREEN3, n=2)
    out += OD.line((-.03, .3, .05), (-.055, .455, .07), .012, GREEN3, n=3) + OD.line((.035, .3, .05), (.06, .445, .075), .012, GREEN3, n=3)
    return out


def knot_ref(marks, y=KNOT_Y):
    """le groupe photo + nœud + pans glisse d'un bloc, comme le rang du cornet à la hauteur `y` (le bas de la photo quand le haut recule, son haut quand
    c'est le bas qui recule : la photo reste devant tous les rangs qu'elle couvre)"""
    a, b = marks.get('knot', (0, 0)); return {i: y for i in range(a, b)}


def lay_bouquet(bx, marks):
    """bouquet couché : les tiges retombent au sol (cisaillement), face (photo, nœud) en haut, fleurs vers +z, centré"""
    return S._floor(S._shift(S._lay_up(lean(bx, .25, top=.46, ref=knot_ref(marks, KNOT_Y + .04))), 0., 0., -.23))


def k_bouquet(p, c):
    fl, rib, pap, photo, debout = bouquet_params(p, c); mk = {}
    bx = b_bouquet(fl, rib, pap, photo, mk)
    return lean(bx, .3, ref=knot_ref(mk)) if debout else lay_bouquet(bx, mk)


def b_billet_flat(texte, froisse, pap):
    """billet posé à plat, lu depuis l'avant ; `froisse` : quatre facettes à des hauteurs différentes, reliées par leurs plis"""
    img = ticket(texte, froisse, paper=pap)
    if not froisse: return [B((-.075, 0, -.035), (.15, .0008, .07), pap, tex={'+y': T.flat(img)})]
    out = []; hs = (0., .0042, .0012, .005); n = 4
    for i, (a, b) in enumerate(segs(n, img.shape[1])):
        out.append(B((-.075 + .15 * i / n, hs[i], -.035), (.15 / n, .0008, .07), pap, tex={'+y': T.flat(cols(img, a, b))}))
        if i: out.append(B((-.075 + .15 * i / n - .0004, min(hs[i], hs[i - 1]), -.035), (.0008, abs(hs[i] - hs[i - 1]) + .0008, .07), _sh(pap, .86)))
    return out


def b_billet_debout(texte, froisse, pap):
    """billet debout (pour le tenir) : le recto vers -z, le verso (piste magnétique) vers +z ; `froisse` : facettes décalées en z"""
    img = ticket(texte, froisse, paper=pap); bk = ticket_back(paper=pap)
    if not froisse: return [B((-.075, 0, -.0004), (.15, .07, .0008), pap, tex={'-z': img, '+z': bk})]
    out = []; zs = (0., -.004, -.0012, -.005); n = 4; sg = segs(n, img.shape[1]); sb = segs(n, bk.shape[1])
    for i, (a, b) in enumerate(sg):
        a2, b2 = sb[n - 1 - i]                                          # verso : vu de derrière, les colonnes vont dans l'autre sens
        out.append(B((-.075 + .15 * i / n, 0, zs[i] - .0004), (.15 / n, .07, .0008), pap, tex={'-z': cols(img, a, b), '+z': cols(bk, a2, b2)}))
        if i: out.append(B((-.075 + .15 * i / n - .0004, 0, min(zs[i], zs[i - 1]) - .0004), (.0008, .07, abs(zs[i] - zs[i - 1]) + .0008), _sh(pap, .86)))
    return out


def k_billet(p, c):
    tx, fr, pap = billet_params(p, c)
    return b_billet_flat(tx, fr, pap)


# ================================================================== held (PS1) : P(lat, haut, avant) autour du poing (cube de 12 cm)
GRIP_PS1 = {'carnet_y': .03, 'carnet_d': .09, 'ouvert_e': .035, 'ouvert_d': .02, 'lire_y': -.04, 'lire_d': .02, 'bouquet_y': .02, 'billet_d': .07}


def h_carnet(P, F, k, lights, col, cfg):
    """carnet fermé debout DEVANT le poing (il le cache en partie), tenu par le bas, couverture de face : gestes `hold` (deux mains, contre la poitrine),
    `chest`, `show` ; `vers_soi: true` : couverture vers soi. (9/11 : pendu sous le poing, il disparaissait en VOXEL avec le geste `hold`)"""
    p = merged('od_carnet', cfg); colr, _, _, _, m = carnet_params(p, col); fc = S._face(p)
    return S._hold(P, F, b_carnet_debout(colr, m), S._grip(fc, 0., GRIP_PS1['carnet_y'], 0., GRIP_PS1['carnet_d']), fc)


def open_grip(fc, e, d=0.):
    """carnet ouvert tenu par son bord extérieur (le bord de la page de droite vu par celui qui le tient) : poing à `e` du bord, le carnet vers l'intérieur,
    `d` devant le poing (avec le geste `hold`, l'autre poing reste derrière les pages au lieu de les traverser)"""
    return S._grip(fc, (.214 + e) * (1 if fc == 'holder' else -1), .077, 0., d)


def h_carnet_ouvert(P, F, k, lights, col, cfg):
    """carnet ouvert, les pages vers celui qui le tient, tenu par le bas du dos, centré sur le poing : la page du dessin reste du côté de l'épaule de la
    main qui tient (à filmer par-dessus cette épaule) et le carnet ne passe pas devant le visage"""
    p = merged('od_carnet_ouvert', cfg); colr, _, d, leg, m = carnet_params(p, col); fc = S._face(p, 'holder')
    return S._hold(P, F, b_carnet_ouvert_debout(colr, d, leg, m), S._grip(fc, 0., GRIP_PS1['lire_y'], 0., GRIP_PS1['lire_d']), fc)


def h_carnet_montre(P, F, k, lights, col, cfg):
    """carnet ouvert, les pages vers l'avant : on montre le dessin (à quelqu'un, à la caméra) ; tenu par le bord, le carnet devant la poitrine"""
    p = merged('od_carnet_montre', cfg); colr, _, d, leg, m = carnet_params(p, col); fc = S._face(p, 'front')
    return S._hold(P, F, b_carnet_ouvert_debout(colr, d, leg, m), open_grip(fc, GRIP_PS1['ouvert_e'], GRIP_PS1['ouvert_d']), fc)


def h_bouquet(P, F, k, lights, col, cfg):
    """bouquet tenu par le bas des tiges, fleurs en haut, photo et nœud vers l'avant (`vers_soi: true` : vers soi)"""
    fl, rib, pap, photo, _ = bouquet_params(cfg, col); fc = S._face(cfg)
    return S._hold(P, F, b_bouquet(fl, rib, pap, photo), S._grip(fc, 0., GRIP_PS1['bouquet_y'], .006, 0.), fc)


def h_billet(P, F, k, lights, col, cfg):
    """billet pincé devant le poing, le recto vers l'avant (`vers_soi: true` : vers soi)"""
    tx, fr, pap = billet_params(cfg, col); fc = S._face(cfg)
    return S._hold(P, F, b_billet_debout(tx, fr, pap), S._grip(fc, 0., -.02, 0., GRIP_PS1['billet_d']), fc)


# ================================================================== registration (objets._load_lots)
POSED = [('od_carnet', k_carnet, 'carnet de dessin (toile usée, élastique)', None), ('od_bouquet', k_bouquet, 'bouquet de fleurs blanches (photo au ruban)', None),
         ('od_billet', k_billet, 'billet de train froissé, lisible', None)]
HELD = [('od_carnet', h_carnet, 'carnet de dessin fermé (contre la poitrine)'), ('od_carnet_ouvert', h_carnet_ouvert, 'carnet ouvert, pages vers soi'),
        ('od_carnet_montre', h_carnet_montre, 'carnet ouvert, dessin montré vers l\'avant'), ('od_bouquet', h_bouquet, 'bouquet tenu par les tiges'),
        ('od_billet', h_billet, 'billet de train montré')]


def enregistrer(R):
    """un nom déjà pris par un autre lot est sauté (et dit) : le reste du lot se charge quand même"""
    for kind, fn, lab, lights in POSED:
        try: R.objet(kind, fn, lab, lumieres=lights)
        except ValueError as e: print(e)
    for name, fn, lab in HELD:
        try: R.tenu(name, fn, lab)
        except ValueError as e: print(e)
