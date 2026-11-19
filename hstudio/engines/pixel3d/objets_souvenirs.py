"""OBJETS DÉTAILLÉS, LOT B « bureau, souvenirs et horreur » (01/11/2026), version PS1 native.

Découvert tout seul par `objets._load_lots()` (fichier `objets_<lot>.py`) : aucune ligne à écrire ailleurs. La version VOXEL native est
`voxelgpu/b_objets_souvenirs.py` (même plan, mêmes réglages, autre exécution) ; les images (page tapée, cassette, photo instantanée, lettre...)
sont dessinées ici et partagées par les deux versions.

Posés (`od_*`, face avant vers -z, x à droite vu de face, y = 0 posé) :
  od_typewriter      machine à écrire (`texte` : la feuille tapée, lisible ; `feuille: false`)
  od_tape_recorder   magnétophone à cassette, une cassette dans la fenêtre et une à côté (`etiquette`, `etiquette2`, `enregistre`, `cassette: false`)
  od_cassette        une cassette seule dans son boîtier ouvert (`etiquette`)
  od_film_camera     appareil photo argentique (reflex : prisme, objectif bagué, levier d'armement, courroie)
  od_polaroid        appareil photo instantané, la photo qui sort (`photo` : silhouette, visage, fenetre, vide, maison, portrait... ; `legende` ; `photo: false`)
  od_walkie_talkie   talkie-walkie debout (`canal`, `voyant`)
  od_binoculars      jumelles couchées, courroie
  od_teddy_bear      ours en peluche assis (bouton dépareillé, couture, rapiéçage ; `ruban`)
  od_porcelain_doll  poupée ancienne assise (visage de porcelaine `fele`, robe `color`, `cheveux`)
  od_music_box       boîte à musique ouverte : danseuse, miroir, mécanisme sous verre (`ferme: true`)
  od_hand_mirror     miroir à main posé à plat (`fele`)
  od_envelope        enveloppe et lettre dépliée, lisibles (`nom`, `adresse`, `texte`, `lettre: false`, `dos: true`)
  od_candelabra      chandelier à trois branches, bougies allumées (`allumee`, `cire`)
  od_axe             hache couchée (`billot: true` : plantée dans un billot)
  od_knife_horror    grand couteau couché
  od_syringe         seringue ancienne à trois anneaux (`contenu` : vert, ambre, clair)
Tenus (`hold`) : od_polaroid, od_polaroid_photo, od_walkie_talkie, od_binoculars, od_teddy_bear, od_porcelain_doll, od_hand_mirror, od_envelope,
od_axe, od_knife_horror, od_cassette. Réglages par la clé d'épisode {"objets": {"contenu": {"od_envelope": {"texte": [...]}}}}.

Un objet tenu est le MÊME objet que posé, tourné vers l'avant du personnage (`_hold`) ou vers lui (`vers_soi`), saisi par sa prise, devant le poing.
Hache et couteau tenus : vus à plat, tranchant vers l'extérieur (`tranchant: avant` : vers l'avant) ; couteau `lame: bas` (prise poignard) ;
hache `prise: haut` (tenue sous le fer, le manche qui pend : à préférer bras le long du corps, geste `idle`).
Rien d'aléatoire, aucune horloge, rien de gore."""
import functools, math
import numpy as np
from PIL import Image, ImageDraw
from .r3d import B, C, M_FABRIC, M_WOODV, M_METAL, M_CARD
from . import objets as OD, objets_tex as T

_g, _sh, _col = OD._g, OD._sh, OD._col
METAL, BRASS, BLACK, IVORY = OD.METAL, OD.BRASS, OD.BLACK, OD.IVORY
CHROME = (206, 208, 214); STEEL = (176, 180, 188); PAPER = (236, 232, 216)


# ================================================================== images (shared with VOXEL)
def _new(W, H, bg):
    im = Image.new('RGBA', (W, H), tuple(int(v) for v in bg[:3]) + ((int(bg[3]),) if len(bg) > 3 else (255,)))
    return im, ImageDraw.Draw(im)


def _rgba(c, a=255): return tuple(int(v) for v in c[:3]) + (a,)


TYPED = ('NUIT DU 31 OCTOBRE', '', 'IL FRAPPE ENCORE', 'A LA PORTE.', 'IL FRAPPE ENCORE', 'A LA PORTE.', 'IL FRAPPE ENC')


@functools.lru_cache(maxsize=16)
def typed_page(texte=(), W=84, H=64, ink=(34, 30, 36), paper=PAPER):
    """feuille dans la machine : lignes tapées (frappe inégale, lettres qui sautent d'un texel), la dernière à moitié"""
    im, d = _new(W, H, paper)
    for y in range(H - 6, H): d.line([(0, y), (W - 1, y)], fill=_rgba(T._shade(paper, .93 - .02 * (y - H + 6))))
    y = 5
    for j, l in enumerate(list(texte) or list(TYPED)):
        x = 4
        for i, ch in enumerate(T.ascii_up(l)[:(W - 6) // 4]):
            v = (i * 7 + j * 13) % 5
            T.mini(d, x, y + (1 if (i * 5 + j * 3) % 11 == 0 else 0), ch, _rgba(T._shade(ink, .7 + .16 * v)))
            x += 4
        y += 7
        if y > H - 7: break
    return np.array(im)


@functools.lru_cache(maxsize=2)
def typebar_fan(W=44, H=16):
    """corbeille des barres à caractères vue de dessus (à poser avec flat()) : les barres convergent vers le guide, en haut (côté rouleau)"""
    im, d = _new(W, H, (16, 16, 18)); cx, cy = (W - 1) / 2, -3
    for i in range(23):
        a = math.radians(-72 + i * 144 / 22)
        d.line([(cx + math.sin(a) * 6, cy + math.cos(a) * 6), (cx + math.sin(a) * (H + 4), cy + math.cos(a) * (H + 4))], fill=(150, 150, 158, 255))
    d.rectangle([cx - 2, 0, cx + 2, 2], fill=(196, 196, 204, 255))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def cassette_face(texte=('NE PAS', 'ECOUTER'), W=48, H=30, shell=(36, 36, 40), label=(232, 226, 200), ink=(36, 44, 130), band=(190, 40, 40)):
    """cassette audio vue de face : étiquette écrite à la main, bande de couleur, fenêtre avec les deux bobines, trapèze du bas"""
    im, d = _new(W, H, shell)
    d.rectangle([2, 2, W - 3, 22], fill=_rgba(label)); d.rectangle([2, 2, W - 3, 3], fill=_rgba(band))
    t = [T.ascii_up(x) for x in (list(texte) or ['FACE A'])]
    if t: T.mini(d, max(3, (W - T.mini_w(t[0][:11])) // 2), 5, t[0][:11], _rgba(ink))
    if len(t) > 1: T.mini(d, max(3, (W - T.mini_w(t[1][:11])) // 2), 17, t[1][:11], _rgba(ink))
    d.rectangle([11, 11, W - 12, 15], fill=(22, 20, 20, 255)); d.rectangle([11, 11, W - 12, 15], outline=(110, 104, 96, 255))
    d.ellipse([12, 9, 21, 17], fill=(84, 56, 38, 255)); d.ellipse([W - 21, 10, W - 14, 16], fill=(84, 56, 38, 255))
    for cx in (16.5, W - 17.5):
        d.ellipse([cx - 2.5, 10.5, cx + 2.5, 15.5], fill=(226, 224, 218, 255)); d.point((int(cx), 13), fill=(30, 30, 30, 255))
    d.rectangle([3, 11, 6, 15], fill=_rgba(T._shade(label, .85))); T.mini(d, 3, 11, 'A', (30, 30, 34, 255))
    d.polygon([(8, 23), (W - 9, 23), (W - 6, H - 1), (5, H - 1)], fill=_rgba(T._shade(shell, 1.25)))
    for x in (12, 18, W - 20, W - 14): d.rectangle([x, 25, x + 1, 26], fill=(8, 8, 10, 255))
    for (x, y) in ((3, 25), (W - 4, 25), (W // 2, 27)): d.point((x, y), fill=(150, 150, 156, 255))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def tape_key(sym='play', W=12, H=7, bg=(28, 28, 30)):
    """touche de magnétophone : enregistrement (rond rouge), retour, avance, lecture, arrêt, pause"""
    im, d = _new(W, H, bg); fg = (232, 232, 236, 255); cy = H // 2
    if sym == 'rec': d.ellipse([W // 2 - 2, cy - 2, W // 2 + 2, cy + 2], fill=(220, 40, 36, 255))
    elif sym == 'rew': d.polygon([(2, cy), (5, cy - 2), (5, cy + 2)], fill=fg); d.polygon([(6, cy), (9, cy - 2), (9, cy + 2)], fill=fg)
    elif sym == 'ff': d.polygon([(9, cy), (6, cy - 2), (6, cy + 2)], fill=fg); d.polygon([(5, cy), (2, cy - 2), (2, cy + 2)], fill=fg)
    elif sym == 'play': d.polygon([(8, cy), (4, cy - 2), (4, cy + 2)], fill=fg)
    elif sym == 'stop': d.rectangle([4, cy - 2, 7, cy + 1], fill=fg)
    else: d.rectangle([4, cy - 2, 5, cy + 2], fill=fg); d.rectangle([7, cy - 2, 8, cy + 2], fill=fg)
    return np.array(im)


@functools.lru_cache(maxsize=8)
def counter_img(n='013', W=14, H=7):
    im, d = _new(W, H, (14, 14, 16))
    for i, ch in enumerate(str(n)[:3]):
        d.rectangle([1 + i * 4, 1, 3 + i * 4, 5], fill=(30, 30, 32, 255)); T.mini(d, 1 + i * 4, 1, ch, (236, 236, 232, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def leather(W=24, H=12, col=(30, 30, 32)):
    """gainage grenu d'un boîtier d'appareil photo"""
    im, d = _new(W, H, col); lt = _rgba(T._shade(col, 1.6))
    for y in range(0, H, 2):
        for x in range((y // 2) % 2, W, 2): d.point((x, y), fill=lt)
    return np.array(im)


@functools.lru_cache(maxsize=8)
def lens_img(S=16, rim=(26, 26, 28), glass=(44, 36, 86)):
    """lentille vue de face : bague, verre traité violet-bleu, reflets (coins = couleur de la plaque)"""
    im, d = _new(S, S, (0, 0, 0, 0))
    d.ellipse([0, 0, S - 1, S - 1], fill=_rgba(rim)); d.ellipse([1, 1, S - 2, S - 2], outline=(120, 120, 128, 255))
    d.ellipse([3, 3, S - 4, S - 4], fill=_rgba(glass)); d.ellipse([S // 3, S // 3, S - 1 - S // 3, S - 1 - S // 3], fill=_rgba(T._shade(glass, .45)))
    d.arc([3, 3, S - 4, S - 4], 20, 80, fill=(150, 80, 170, 255))
    for (x, y) in ((S // 3, S // 3 - 1), (S // 3 - 1, S // 3), (S // 3, S // 3)): d.point((x, y), fill=(220, 226, 255, 255))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def polaroid_img(sujet='silhouette', legende='', W=26, H=32, seed=0):
    """photo instantanée : cadre blanc, image carrée en haut, large bande du bas avec la légende à la main.
    `silhouette` (couloir au flash, une silhouette pâle au fond), `visage`, `fenetre` (visage à la fenêtre), `vide` (en train d'apparaître), `maison`, ou un sujet de T.photo"""
    im, d = _new(W, H, (242, 240, 232)); x0, y0 = 2, 2; S = W - 4; x1, y1 = x0 + S - 1, y0 + S - 1; cx = (x0 + x1) / 2
    if sujet == 'silhouette':
        d.rectangle([x0, y0, x1, y1], fill=(10, 10, 14, 255)); m = 8
        d.polygon([(x0, y0), (x1, y0), (x1 - m, y0 + m - 1), (x0 + m, y0 + m - 1)], fill=(54, 56, 62, 255))
        d.polygon([(x0, y1), (x1, y1), (x1 - m, y1 - m + 2), (x0 + m, y1 - m + 2)], fill=(92, 84, 72, 255))
        d.polygon([(x0, y0), (x0 + m, y0 + m - 1), (x0 + m, y1 - m + 2), (x0, y1)], fill=(96, 100, 104, 255))
        d.polygon([(x1, y0), (x1 - m, y0 + m - 1), (x1 - m, y1 - m + 2), (x1, y1)], fill=(78, 82, 88, 255))
        d.rectangle([x0 + m, y0 + m - 1, x1 - m, y1 - m + 2], fill=(4, 4, 6, 255))
        d.rectangle([int(cx) - 1, y0 + m + 1, int(cx), y0 + m + 2], fill=(206, 210, 204, 255))       # tête
        d.rectangle([int(cx) - 1, y0 + m + 3, int(cx), y1 - m + 2], fill=(176, 180, 176, 255))         # corps long
        d.point((int(cx) - 2, y0 + m + 4), fill=(150, 154, 150, 255)); d.point((int(cx) + 1, y0 + m + 4), fill=(150, 154, 150, 255))
        for i in range(3): d.line([(x0 + i, y0), (x0 + i, y1)], fill=(140 - 30 * i, 140 - 30 * i, 136 - 30 * i, 255))   # brûlure du flash
    elif sujet in ('visage', 'fenetre'):
        d.rectangle([x0, y0, x1, y1], fill=(8, 10, 14, 255))
        if sujet == 'fenetre':
            d.rectangle([x0 + 4, y0 + 3, x1 - 4, y1 - 3], fill=(26, 34, 46, 255)); d.line([(cx, y0 + 3), (cx, y1 - 3)], fill=(60, 60, 64, 255)); d.line([(x0 + 4, y0 + S // 2), (x1 - 4, y0 + S // 2)], fill=(60, 60, 64, 255))
            fx, fy, fw = cx + 2, y0 + S // 2 + 2, 3
        else: fx, fy, fw = cx, y0 + S // 2, 6
        d.ellipse([fx - fw, fy - fw * 1.3, fx + fw, fy + fw * 1.3], fill=(200, 196, 186, 255))
        e = max(1, fw // 2)
        d.rectangle([fx - e - 1, fy - e, fx - e, fy - e + 1], fill=(6, 6, 6, 255)); d.rectangle([fx + e - 1, fy - e, fx + e, fy - e + 1], fill=(6, 6, 6, 255))
        d.rectangle([fx - 1, fy + e, fx, fy + e + max(1, e)], fill=(20, 12, 12, 255))
    elif sujet == 'vide':
        for y in range(y0, y1 + 1): d.line([(x0, y), (x1, y)], fill=(86 + (y - y0), 96 + (y - y0) // 2, 84 + (y - y0) // 3, 255))
        d.rectangle([int(cx) - 3, y0 + 7, int(cx) + 2, y1 - 4], fill=(100, 112, 98, 255))
    elif sujet == 'maison':
        d.rectangle([x0, y0, x1, y1], fill=(16, 20, 34, 255)); d.rectangle([x0, y1 - 5, x1, y1], fill=(18, 24, 18, 255))
        d.rectangle([x0 + 5, y0 + 9, x1 - 5, y1 - 5], fill=(40, 38, 44, 255)); d.polygon([(x0 + 3, y0 + 10), (cx, y0 + 3), (x1 - 3, y0 + 10)], fill=(30, 26, 30, 255))
        d.rectangle([x0 + 8, y0 + 12, x0 + 10, y0 + 14], fill=(240, 200, 110, 255)); d.rectangle([x1 - 10, y0 + 12, x1 - 8, y0 + 14], fill=(20, 18, 22, 255))
        d.rectangle([int(cx) - 1, y1 - 9, int(cx) + 1, y1 - 5], fill=(10, 8, 8, 255))
    else:
        ph = Image.fromarray(np.ascontiguousarray(T.photo(str(sujet), int(seed), 24, 30)[3:27])).resize((S, S), Image.NEAREST); im.paste(ph, (x0, y0))
    if legende:
        t = T.ascii_up(legende)[:6]; T.mini(d, max(1, (W - T.mini_w(t)) // 2), y1 + 2, t, (40, 50, 140, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def bear_muzzle(W=12, H=10, col=(222, 192, 146), dark=(44, 28, 22)):
    im, d = _new(W, H, col)
    d.polygon([(3, 1), (8, 1), (7, 3), (4, 3)], fill=_rgba(dark)); d.point((4, 1), fill=(120, 100, 90, 255))
    d.line([(5, 3), (5, 6)], fill=_rgba(dark)); d.line([(6, 3), (6, 6)], fill=_rgba(dark))
    d.line([(2, 6), (4, 8), (5, 7), (6, 7), (7, 8), (9, 6)], fill=_rgba(dark))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def button_img(col=(70, 110, 160), S=6):
    """gros bouton à quatre trous cousu en croix (l'œil dépareillé)"""
    im, d = _new(S, S, (0, 0, 0, 0))
    d.ellipse([0, 0, S - 1, S - 1], fill=_rgba(col)); d.ellipse([0, 0, S - 1, S - 1], outline=_rgba(T._shade(col, .6)))
    for (x, y) in ((S // 2 - 1, S // 2 - 1), (S // 2, S // 2 - 1), (S // 2 - 1, S // 2), (S // 2, S // 2)): d.point((x, y), fill=(230, 222, 200, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def paw_pad(W=8, H=10, col=(222, 192, 146), fur=(150, 100, 60)):
    im, d = _new(W, H, fur)
    d.ellipse([1, 3, W - 2, H - 1], fill=_rgba(col))
    for x in (1, 3, 5): d.rectangle([x, 0, x + 1, 1], fill=_rgba(col))
    for y in range(4, H - 1, 2): d.point((W - 2, y), fill=(80, 56, 40, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def tartan(W=10, H=10, base=(56, 84, 60)):
    im, d = _new(W, H, base)
    for i in (2, 7): d.line([(i, 0), (i, H - 1)], fill=(170, 40, 40, 255)); d.line([(0, i), (W - 1, i)], fill=(170, 40, 40, 255))
    d.line([(5, 0), (5, H - 1)], fill=(220, 190, 70, 255))
    for i in range(0, W, 2): d.point((i, 0), fill=(240, 236, 226, 255)); d.point((i, H - 1), fill=(240, 236, 226, 255))
    for i in range(0, H, 2): d.point((0, i), fill=(240, 236, 226, 255)); d.point((W - 1, i), fill=(240, 236, 226, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def seam(W=16, H=6, fur=(150, 100, 60)):
    """couture recousue en travers du front (gros points noirs)"""
    im, d = _new(W, H, fur)
    for i in range(1, W - 1, 3):
        y = int(1 + (H - 3) * i / W)
        d.line([(i, y - 1), (i + 1, y + 2)], fill=(24, 18, 16, 255))
    d.line([(0, 1), (W - 1, H - 2)], fill=_rgba(T._shade(fur, .7)))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def doll_face(W=16, H=16, skin=(242, 228, 216), fele=True):
    """visage de poupée de porcelaine : grands yeux de verre bleus, cils, joues roses, bouche en cœur ; `fele` : une fêlure qui passe près de l'œil"""
    im, d = _new(W, H, skin)
    for ex in (3, 10):
        d.line([(ex, 3), (ex + 2, 3)], fill=(150, 104, 70, 255))
        d.rectangle([ex, 6, ex + 2, 8], fill=(250, 250, 250, 255)); d.rectangle([ex, 6, ex + 1, 8], fill=(80, 130, 196, 255)); d.point((ex + 1, 7), fill=(10, 10, 14, 255))
        d.point((ex, 6), fill=(230, 240, 255, 255)); d.line([(ex - 1, 5), (ex + 3, 5)], fill=(20, 16, 16, 255)); d.point((ex - 1, 4), fill=(20, 16, 16, 255)); d.point((ex + 3, 4), fill=(20, 16, 16, 255))
    for (x, y) in ((2, 10), (3, 10), (12, 10), (13, 10)): d.point((x, y), fill=(234, 158, 160, 255))
    d.point((7, 9), fill=(218, 196, 186, 255)); d.point((8, 9), fill=(218, 196, 186, 255))
    d.line([(6, 12), (9, 12)], fill=(186, 40, 52, 255)); d.point((7, 13), fill=(160, 30, 40, 255)); d.point((8, 13), fill=(160, 30, 40, 255)); d.point((7, 11), fill=(186, 40, 52, 255))
    if fele: d.line([(12, 0), (11, 2), (13, 4), (13, 5), (14, 9), (13, 11), (15, 14)], fill=(96, 86, 86, 255))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def doll_dress(W=16, H=16, col=(120, 40, 60), lace=(238, 232, 218)):
    im, d = _new(W, H, col)
    d.rectangle([0, 0, W - 1, 3], fill=_rgba(lace))
    for x in range(0, W, 2): d.point((x, 4), fill=_rgba(lace))
    for y in (6, 9, 12): d.rectangle([W // 2 - 1, y, W // 2, y + 1], fill=(244, 240, 230, 255))
    d.rectangle([0, H - 2, W - 1, H - 1], fill=_rgba(T._shade(col, .6)))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def marquetry(W=40, H=14, wood=(110, 60, 34)):
    """façade de boîte à musique : veinage, filet clair, rosace, entrée de serrure en laiton"""
    im, d = _new(W, H, wood)
    for y in range(0, H, 3): d.line([(0, y), (W - 1, y + (1 if y % 2 else 0))], fill=_rgba(T._shade(wood, .82)))
    d.rectangle([1, 1, W - 2, H - 2], outline=(214, 176, 112, 255))
    cx, cy = W // 2, H // 2
    for a in range(0, 360, 45):
        x, y = cx + 4 * math.cos(math.radians(a)), cy + 3 * math.sin(math.radians(a)); d.point((int(round(x)), int(round(y))), fill=(226, 196, 130, 255))
    d.ellipse([cx - 1, cy - 1, cx + 1, cy + 1], fill=(196, 160, 80, 255)); d.point((cx, cy), fill=(10, 8, 6, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def oval_mirror(W=14, H=12, rim=(200, 170, 90), glass=(196, 208, 220)):
    im, d = _new(W, H, (0, 0, 0, 0))
    d.ellipse([0, 0, W - 1, H - 1], fill=_rgba(rim)); d.ellipse([1, 1, W - 2, H - 2], fill=_rgba(glass))
    d.line([(3, 3), (5, 2)], fill=(250, 252, 255, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def mirror_back(W=20, H=26, col=(186, 186, 192)):
    """dos repoussé d'un miroir à main : ovales concentriques, cartouche, fleurons, ternissure"""
    im, d = _new(W, H, (0, 0, 0, 0)); lt, dk = _rgba(T._shade(col, 1.18)), _rgba(T._shade(col, .62))
    d.ellipse([0, 0, W - 1, H - 1], fill=_rgba(col)); d.ellipse([2, 2, W - 3, H - 3], outline=dk); d.ellipse([3, 3, W - 4, H - 4], outline=lt)
    d.ellipse([W // 2 - 4, H // 2 - 5, W // 2 + 3, H // 2 + 4], outline=dk)
    for a in range(0, 360, 30):
        x, y = W / 2 + (W / 2 - 5) * math.cos(math.radians(a)), H / 2 + (H / 2 - 5) * math.sin(math.radians(a)); d.point((int(x), int(y)), fill=lt)
    for (x, y) in ((6, 15), (7, 16), (13, 8), (12, 18)): d.point((x, y), fill=_rgba(T._shade(col, .45)))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def envelope_front(nom='MME C. ROUX', adresse=('12 RUE DES LILAS', '76000 ROUEN'), W=48, H=34, paper=(226, 214, 186), ink=(36, 36, 84)):
    """enveloppe : adresse à la main, timbre dentelé, tampon de la poste"""
    im, d = _new(W, H, paper)
    d.rectangle([W - 12, 2, W - 3, 13], fill=(244, 240, 230, 255))
    for i in range(W - 12, W - 2, 2): d.point((i, 2), fill=_rgba(paper)); d.point((i, 13), fill=_rgba(paper))
    d.rectangle([W - 11, 3, W - 4, 12], fill=(160, 44, 40, 255)); d.ellipse([W - 9, 5, W - 6, 9], fill=(232, 210, 190, 255)); d.rectangle([W - 10, 10, W - 5, 12], fill=(232, 210, 190, 255))
    d.ellipse([W - 22, 3, W - 13, 12], outline=(70, 70, 80, 255)); T.mini(d, W - 20, 6, '31', (70, 70, 80, 255))
    for k in range(3): d.line([(W - 14 + j, 5 + k * 3 + (1 if j % 4 < 2 else 0)) for j in range(0, 12, 2)], fill=(70, 70, 80, 255))
    y = 17
    for l in [nom] + list(adresse):
        T.mini(d, 4, y, T.ascii_up(l)[:(W - 6) // 4], _rgba(ink)); d.line([(3, y + 6), (3 + T.mini_w(T.ascii_up(l)[:(W - 6) // 4]), y + 6)], fill=_rgba(T._shade(paper, .9))); y += 6
    return np.array(im)


@functools.lru_cache(maxsize=4)
def envelope_back(W=48, H=34, paper=(226, 214, 186), seal=(150, 20, 30), broken=True):
    im, d = _new(W, H, paper); ln = _rgba(T._shade(paper, .8))
    d.line([(0, 0), (W // 2, H // 2 + 2), (W - 1, 0)], fill=ln); d.line([(0, H - 1), (W // 2 - 4, H // 2 + 2)], fill=ln); d.line([(W - 1, H - 1), (W // 2 + 4, H // 2 + 2)], fill=ln)
    cx, cy = W // 2, H // 2 + 1
    d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=_rgba(seal)); d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], outline=_rgba(T._shade(seal, .6)))
    if broken: d.line([(cx - 4, cy), (cx + 4, cy - 1)], fill=_rgba(T._shade(paper, .7)))
    return np.array(im)


LETTER = ('LE 31 OCTOBRE', '', 'CLAIRE,', 'NE REVIENS PAS', 'A LA MAISON.', 'IL DORT DANS', 'TA CHAMBRE', 'DEPUIS TROIS', 'NUITS.', '', 'MAMAN')


@functools.lru_cache(maxsize=16)
def letter_img(texte=(), W=60, H=84, paper=(240, 234, 216), ink=(36, 36, 74)):
    """lettre écrite à la main : lignes bleu pâle, date alignée à droite, deux plis"""
    im, d = _new(W, H, paper)
    for y in range(11, H - 2, 7): d.line([(2, y), (W - 3, y)], fill=(196, 206, 226, 255))
    y = 5
    for j, l in enumerate(list(texte) or list(LETTER)):
        if y > H - 8: break
        t = T.ascii_up(l)[:(W - 4) // 4]
        x = W - 3 - T.mini_w(t) if (j == 0 and t.startswith('LE ')) else 3
        T.mini(d, x, y, t, _rgba(T._shade(ink, 1. + .12 * (j % 2))))
        y += 7
    for y in (H // 3, 2 * H // 3): d.line([(0, y), (W - 1, y)], fill=_rgba(T._shade(paper, .86)))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def graduations(W=40, H=6, glass=(206, 220, 226), ink=(40, 52, 64)):
    im, d = _new(W, H, glass)
    for i, x in enumerate(range(2, W - 1, 3)): d.line([(x, 0), (x, 3 if i % 5 else 5)], fill=_rgba(ink))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def end_grain(S=24, wood=(150, 112, 70)):
    """bout d'un billot vu de dessus : cernes, fente, entailles de hache"""
    im, d = _new(S, S, (0, 0, 0, 0)); c = (S - 1) / 2
    d.ellipse([0, 0, S - 1, S - 1], fill=_rgba(T._shade(wood, .55)))
    d.ellipse([1, 1, S - 2, S - 2], fill=_rgba(wood))
    for r in range(3, S // 2 - 1, 2): d.ellipse([c - r, c - r, c + r, c + r], outline=_rgba(T._shade(wood, .82)))
    d.line([(c, c), (c + 3, S - 3)], fill=_rgba(T._shade(wood, .5)))
    for k in range(4): d.line([(5 + k * 3, 6 + k), (9 + k * 3, 4 + k)], fill=_rgba(T._shade(wood, .62)))
    return np.array(im)


# ================================================================== small builders
def cyl_x(x0, x1, y, z, r, col, **kw):
    L, xc = abs(x1 - x0), (x0 + x1) / 2
    return [C((xc, y, z), (L, 2 * r, 2 * r * .62), col, **kw), C((xc, y, z), (L, 2 * r * .62, 2 * r), col, **kw), C((xc, y, z), (L, 2 * r * .87, 2 * r * .87), col, **kw)]


def cyl_z(x, y, z0, z1, r, col, **kw):
    L, zc = abs(z1 - z0), (z0 + z1) / 2
    return [C((x, y, zc), (2 * r, 2 * r * .62, L), col, **kw), C((x, y, zc), (2 * r * .62, 2 * r, L), col, **kw), C((x, y, zc), (2 * r * .87, 2 * r * .87, L), col, **kw)]


def cyl_y(x, y0, y1, z, r, col, **kw):
    return OD.rnd(x, y0, z, 2 * r, y1 - y0, 2 * r, col, **kw)


def rbox(cx, y0, cz, w, h, d, e, col, **kw):
    """pavé aux arêtes verticales chanfreinées (deux boîtes en croix)"""
    return [C((cx, y0 + h / 2, cz), (w, h, d - 2 * e), col, **kw), C((cx, y0 + h / 2, cz), (w - 2 * e, h, d), col, **kw)]


def _shift(bx, dx=0., dy=0., dz=0.):
    o = np.array([dx, dy, dz], np.float32)
    for b in bx: b.lo = b.lo + o; b.hi = b.hi + o
    return bx


_SWAP = {0: 1, 1: 0, 2: 2, 3: 3, 4: 5, 5: 4}


def _half_tex(tex):
    """images d'un objet tourné d'un demi-tour : les faces ±x / ±z s'échangent, l'image du dessus tourne de 180° (et reste une image « flat »)"""
    out = {}
    for k, v in tex.items():
        if k == 3: out[3] = T.flat(np.flipud(np.rot90(v, 2)))
        elif k == 2: out[2] = np.ascontiguousarray(np.rot90(v, 2))
        else: out[_SWAP[k]] = v
    return out


def _lay_x(bx):
    """objet debout (axe y) -> couché le long de x : (x, y, z) -> (y, -x, z) ; seules les images des faces ±z suivent (tournées d'un quart)"""
    for b in bx:
        lo, hi = b.lo.copy(), b.hi.copy()
        b.lo = np.array([lo[1], -hi[0], lo[2]], np.float32); b.hi = np.array([hi[1], -lo[0], hi[2]], np.float32)
        if b.tex: b.tex = {k: np.ascontiguousarray(np.rot90(v, -1 if k == 4 else 1)) for k, v in b.tex.items() if k in (4, 5)}
    return bx


def _lay_up(bx):
    """objet debout face vers -z -> couché face vers le haut : (x, y, z) -> (x, -z, y) ; l'image de face devient lisible depuis l'avant (flat)"""
    for b in bx:
        lo, hi = b.lo.copy(), b.hi.copy()
        b.lo = np.array([lo[0], -hi[2], lo[1]], np.float32); b.hi = np.array([hi[0], -lo[2], hi[1]], np.float32)
        if b.tex:
            nt = {}
            for k, v in b.tex.items():
                if k == 4: nt[3] = T.flat(v)
                elif k == 3: nt[5] = np.ascontiguousarray(np.fliplr(v))
            b.tex = nt
    return bx


def _floor(bx):
    """pose l'objet sur y = 0"""
    if not bx: return bx
    y0 = float(min(b.lo[1] for b in bx))
    return _shift(bx, 0., -y0, 0.)


def _hold(P, F, bx, anchor=(0., 0., 0.), face='front'):
    """boîtes d'un objet (repère posé : face avant vers -z) -> boîtes autour de la main. `anchor` = le point de l'objet qui est dans le poing.
    face 'front' : l'objet montre sa face avant devant le personnage ; 'holder' : il la tourne vers celui qui le tient"""
    f = F.get('f', 1); s = -1. if face == 'front' else 1.; ax, ay, az = anchor
    flip = s * f < 0
    for b in bx:
        p0 = np.array(P(s * (float(b.lo[0]) - ax), float(b.lo[1]) - ay, s * (float(b.lo[2]) - az)), np.float32)
        p1 = np.array(P(s * (float(b.hi[0]) - ax), float(b.hi[1]) - ay, s * (float(b.hi[2]) - az)), np.float32)
        b.lo = np.minimum(p0, p1); b.hi = np.maximum(p0, p1)
        if flip and b.tex: b.tex = _half_tex(b.tex)
    return bx


def _face(cfg, default='front'):
    """réglage commun des objets tenus : `vers_soi: true` (face vers celui qui tient) / `montre: true` (face vers l'avant)"""
    if cfg.get('vers_soi') is True: return 'holder'
    if cfg.get('montre') is True: return 'front'
    if cfg.get('vers_soi') is False: return 'front'
    if cfg.get('montre') is False: return 'holder'
    return default


# ================================================================== the objects (PS1), local frame
def b_typewriter(p, c):
    """machine à écrire de bureau : quatre rangées de touches rondes sur tiges, barre d'espace, corbeille des barres, rouleau et ses molettes,
    levier de retour chariot, bobines de ruban, plaque de marque, feuille engagée avec le texte tapé (`texte`)"""
    col = _col(c, (30, 30, 34)); dk = _sh(col, .6); cap = (232, 226, 210); out = []
    out += [C((x, .005, z), (.03, .01, .03), (20, 20, 20)) for x in (-.125, .125) for z in (-.1, .1)]
    out += [B((-.15, .01, -.12), (.3, .03, .25), col, refl=.15), B((-.14, .01, -.142), (.28, .022, .024), dk)]
    rows = ((-.122, 8, .046), (-.098, 9, .057), (-.074, 10, .068), (-.05, 10, .079))
    for r, (z, n, yt) in enumerate(rows):
        out.append(B((-.14, .03, z - .013), (.28, yt - .028 - .006, .024), col, refl=.15))
        x0 = -(n - 1) * .0115 + (.004 if r % 2 else 0.)
        for i in range(n):
            x = x0 + i * .023
            out += [C((x, yt - .012, z), (.004, .02, .004), METAL, mat=M_METAL), C((x, yt, z), (.02, .004, .02), CHROME, mat=M_METAL, refl=.3),
                    C((x, yt + .0035, z), (.016, .003, .016), cap)]
    out += [C((0, .036, -.138), (.13, .009, .012), CHROME, mat=M_METAL, refl=.3), C((-.05, .03, -.13), (.006, .012, .012), METAL), C((.05, .03, -.13), (.006, .012, .012), METAL)]
    out.append(B((-.15, .04, -.039), (.3, .07, .012), col, refl=.15))
    out.append(B((-.06, .085, -.04), (.12, .016, .001), col, tex={'-z': T.plate('NOCTA', 30, 8, col, (212, 176, 90))}))
    out += [B((-.15, .04, -.03), (.024, .08, .13), col, refl=.15), B((.126, .04, -.03), (.024, .08, .13), col, refl=.15), B((-.126, .04, .03), (.252, .065, .07), col, refl=.15)]
    out.append(B((-.126, .09, -.03), (.252, .006, .06), (16, 16, 18), tex={'+y': T.flat(typebar_fan())}))
    for sx in (-1, 1):
        out += cyl_y(sx * .093, .118, .124, .01, .026, CHROME, mat=M_METAL, refl=.3) + [C((sx * .093, .126, .01), (.008, .006, .008), dk)]
        out += cyl_y(sx * .093, .112, .118, .01, .021, (60, 24, 26), mat=M_FABRIC)
    out += [C((0, .118, .028), (.022, .016, .006), CHROME, mat=M_METAL), C((0, .113, .03), (.17, .006, .002), (60, 24, 26))]
    out += [B((-.17, .095, .035), (.34, .02, .065), col, refl=.15)]
    out += cyl_x(-.155, .155, .13, .06, .024, (22, 22, 24)) + cyl_x(-.19, -.155, .13, .06, .02, dk) + cyl_x(.155, .19, .13, .06, .02, dk)
    out += [C((-.172, .13, .06), (.004, .046, .046), CHROME, mat=M_METAL), C((.172, .13, .06), (.004, .046, .046), CHROME, mat=M_METAL)]
    out += [C((0, .157, .036), (.21, .005, .005), CHROME, mat=M_METAL, refl=.3)] + [C((sx * .05, .157, .034), (.016, .01, .01), (30, 30, 30)) for sx in (-1, 1)]
    out += OD.line((-.165, .14, .045), (-.2, .165, .0), .008, CHROME, n=4, mat=M_METAL) + [C((-.205, .168, -.004), (.018, .012, .012), CHROME, mat=M_METAL)]
    out += [B((-.15, .13, .083), (.3, .1, .006), col, refl=.15), C((-.1, .19, .08), (.004, .1, .004), CHROME, mat=M_METAL)]
    if _g(p, 'feuille', 'paper', default=True) is not False:
        img = typed_page(T.lines(_g(p, 'texte', 'text')))
        out += OD.bands(-.105, .105, .152, .046, .048, .155, img, PAPER, 4, '-z', (0., .008))
        out.append(B((-.105, .1, .067), (.21, .06, .002), PAPER))
    return out


def b_cassette(label=('NE PAS', 'ECOUTER'), shell=(36, 36, 40), band=(190, 40, 40)):
    """une cassette couchée, étiquette vers le haut, la bande vers l'avant (centrée, 10 x 6,4 cm)"""
    img = cassette_face(tuple(label), shell=tuple(shell), band=tuple(band))
    return [B((-.05, 0, -.032), (.1, .011, .064), shell), B((-.05, .011, -.032), (.1, .001, .064), shell, tex={'+y': T.flat(img)}),
            B((-.03, .002, -.0325), (.06, .006, .001), (20, 20, 22))]


def b_tape_recorder(p, c):
    """magnétophone portable : haut-parleur grillagé, fenêtre fumée sur la cassette, six touches piano (enregistrement rouge), compteur, voyant,
    poignée, micro ; une seconde cassette posée à côté (`etiquette2`, `cassette: false`)"""
    col = _col(c, (44, 44, 48)); dk = _sh(col, .6); sil = (176, 176, 182); rec = bool(_g(p, 'enregistre', 'rec', default=False)); out = []
    out += [B((-.12, 0, -.075), (.24, .045, .15), col), B((-.121, 0, -.076), (.242, .006, .152), dk)]
    out += [B((-.116, .045, -.04), (.11, .002, .105), sil, mat=M_METAL), B((-.112, .046, -.036), (.102, .003, .097), (36, 36, 40), tex={'+y': T.flat(T.grille(26, 24, (40, 40, 44)))})]
    out += [B((-.002, .045, -.04), (.118, .002, .105), sil, mat=M_METAL), B((.004, .039, -.034), (.106, .007, .082), (20, 20, 22))]
    lab = T.lines(_g(p, 'etiquette', 'label'), ('NE PAS', 'ECOUTER'))
    out += _shift(b_cassette(lab), .057, .035, .007)
    out += [B((.004, .047, -.034), (.106, .003, .004), sil, mat=M_METAL), B((.004, .047, .044), (.106, .003, .004), sil, mat=M_METAL),
            B((.004, .047, -.03), (.004, .003, .074), sil, mat=M_METAL), B((.106, .047, -.03), (.004, .003, .074), sil, mat=M_METAL)]
    out.append(B((.008, .0485, -.03), (.098, .002, .074), (40, 44, 52), dissolve=.55, refl=.35, cast=False))
    out += [B((-.115, .036, -.077), (.23, .009, .036), (16, 16, 18))]
    for i, sym in enumerate(('rec', 'rew', 'ff', 'play', 'stop', 'pause')):
        x = -.09 + i * .036; kc = (180, 30, 30) if sym == 'rec' else (34, 34, 36)
        y1 = .052 if not (rec and sym in ('rec', 'play')) else .047
        out.append(B((x - .015, .04, -.076), (.03, y1 - .04, .034), kc, tex={'-z': tape_key(sym, bg=kc), '+y': T.flat(tape_key(sym, bg=kc))}))
    out += [B((.02, .045, .05), (.03, .003, .013), (14, 14, 16), tex={'+y': T.flat(counter_img(str(_g(p, 'compteur', default='013'))))}),
            C((.07, .047, .057), (.007, .004, .007), (255, 40, 30) if rec else (90, 20, 20), emis=2.5 if rec else 0., cast=False)]
    out += [C((-.085, .056, .066), (.012, .022, .012), dk), C((.085, .056, .066), (.012, .022, .012), dk), C((0, .066, .066), (.182, .012, .016), dk)]
    out += [B((-.11, .015, -.0765), (.016, .012, .001), (20, 20, 20), tex={'-z': T.grille(8, 6, (24, 24, 26))}),
            B((-.06, .012, -.0762), (.12, .016, .001), col, tex={'-z': T.plate('NOCTA  K7', 40, 6, col, (200, 200, 206))})]
    out += [C((.121, .025, .0), (.004, .01, .03), sil, mat=M_METAL), C((.122, .025, -.004), (.004, .012, .006), (20, 20, 20))]
    if _g(p, 'cassette', default=True) is not False:
        out += _shift(b_cassette(T.lines(_g(p, 'etiquette2', default=None), ('POUR', 'CLAIRE')), band=(40, 90, 170)), .19, 0., -.04)
    return out


def k_cassette(p, c):
    """cassette posée dans son boîtier ouvert (couvercle translucide relevé, jaquette)"""
    lab = T.lines(_g(p, 'etiquette', 'label'), ('NE PAS', 'ECOUTER'))
    out = [B((-.056, 0, -.036), (.112, .004, .072), (226, 228, 232), dissolve=.35, refl=.3), B((-.054, .004, .028), (.108, .012, .006), (200, 60, 50))]
    out += _shift(b_cassette(lab, _col(c, (36, 36, 40))), 0., .004, -.004)
    out += [B((-.056, .004, .036), (.112, .07, .004), (226, 228, 232), dissolve=.45, refl=.35, cast=False)]
    return out


def b_film_camera(p, c):
    """reflex argentique : gainage grenu, capots chromés, prisme titré, molettes, déclencheur, levier d'armement, objectif bagué (mise au point
    crantée, échelle des distances), verre traité, œillets et courroie"""
    ch = _col(c, CHROME); blk = (30, 30, 32); out = []
    out += [B((-.07, 0, -.0225), (.14, .008, .045), ch, mat=M_METAL, refl=.3),
            B((-.069, .008, -.0215), (.138, .058, .043), blk, tex={'-z': leather(), '+z': leather()}),
            B((-.07, .066, -.0225), (.14, .012, .045), ch, mat=M_METAL, refl=.3)]
    out += [B((-.025, .078, -.02), (.05, .02, .04), ch, mat=M_METAL, refl=.3), B((-.019, .098, -.016), (.038, .012, .032), ch, mat=M_METAL, refl=.3),
            B((-.024, .081, -.0205), (.048, .013, .001), blk, tex={'-z': T.plate('NOCTA', 24, 6, blk, (226, 226, 232))}), C((0, .1115, 0), (.02, .003, .02), ch, mat=M_METAL)]
    out += cyl_y(-.048, .078, .09, .0, .011, blk) + [C((-.048, .092, .0), (.004, .003, .018), ch, mat=M_METAL)]
    out += cyl_y(.036, .078, .082, .0, .013, blk) + cyl_y(.036, .082, .088, .0, .012, ch, mat=M_METAL)
    out += cyl_y(.054, .078, .086, -.01, .0045, ch, mat=M_METAL) + [C((.05, .084, .008), (.034, .003, .008), ch, mat=M_METAL), C((.058, .0785, .013), (.007, .001, .007), (16, 16, 16))]
    y = .044
    out += cyl_z(0, y, -.0225, -.03, .029, ch, mat=M_METAL, refl=.3) + cyl_z(0, y, -.03, -.04, .028, blk) + cyl_z(0, y, -.04, -.043, .0285, ch, mat=M_METAL)
    out += cyl_z(0, y, -.043, -.062, .031, (22, 22, 24))
    for z in (-.046, -.051, -.056): out += [C((0, y + .031, z), (.024, .002, .002), (90, 90, 96)), C((0, y - .031, z), (.024, .002, .002), (90, 90, 96))]
    out += cyl_z(0, y, -.062, -.074, .026, blk) + cyl_z(0, y, -.074, -.078, .027, ch, mat=M_METAL)
    out.append(B((-.021, y - .021, -.0785), (.042, .042, .001), blk, tex={'-z': lens_img(16, blk)}, refl=.12))
    out += [C((.045, .05, -.024), (.006, .016, .004), ch, mat=M_METAL), C((-.032, .03, -.024), (.008, .008, .004), ch, mat=M_METAL)]
    out += [C((0, .086, .026), (.022, .016, .008), blk)]
    for sx in (-1, 1): out.append(C((sx * .072, .06, 0), (.006, .008, .006), ch, mat=M_METAL))
    if _g(p, 'courroie', 'strap', default=True):
        st = (86, 52, 30)
        out += OD.line((-.075, .058, 0), (-.1, .004, .03), .01, st, n=4) + OD.line((-.1, .004, .03), (.1, .004, .055), .012, st, n=6) + OD.line((.1, .004, .055), (.075, .058, 0), .01, st, n=4)
    return out


def b_polaroid(p, c, photo=True):
    """appareil instantané : coque claire, façade noire, objectif, fenêtre du flash, viseur, déclencheur rouge, deux filets de couleur,
    fente d'éjection et la photo qui sort (`photo`, `legende`), dragonne"""
    col = _col(c, (232, 230, 222)); blk = (30, 30, 32); out = []
    out += [B((-.0575, 0, -.06), (.115, .075, .13), col), B((-.0575, .075, -.06), (.115, .03, .062), col), B((-.0575, .075, .002), (.115, .014, .03), col),
            B((-.055, .0, .07), (.11, .065, .002), _sh(col, .9))]
    out.append(B((-.055, .012, -.0612), (.11, .088, .0012), blk))
    out += cyl_z(0, .056, -.061, -.072, .027, blk) + cyl_z(0, .056, -.072, -.075, .022, CHROME, mat=M_METAL)
    out.append(B((-.018, .038, -.0755), (.036, .036, .001), blk, tex={'-z': lens_img(14, blk)}, refl=.12))
    fl = bool(_g(p, 'flash', default=False))
    out += [B((-.048, .09, -.0625), (.05, .011, .0012), (238, 238, 232), emis=2.5 if fl else 0., cast=not fl), B((.022, .09, -.0625), (.02, .011, .0012), (16, 18, 28), refl=.4)]
    out += [C((-.044, .066, -.066), (.014, .014, .008), (200, 30, 30)), B((-.009, .012, -.0626), (.005, .016, .001), (200, 40, 40)), B((-.004, .012, -.0626), (.005, .016, .001), (232, 136, 40))]
    out += [B((-.046, .005, -.0625), (.092, .005, .001), (8, 8, 8))]
    out += [C((.022, .096, .032), (.016, .012, .008), blk)]
    out += OD.line((.058, .03, .02), (.07, -.0, .05), .006, (40, 40, 44), n=3) if not photo else []
    if photo and _g(p, 'photo', default='silhouette') is not False:
        img = polaroid_img(str(_g(p, 'photo', default='silhouette')), str(_g(p, 'legende', 'caption', default='')))
        vis = np.ascontiguousarray(img[int(img.shape[0] * .2):])
        out += [B((-.044, .006, -.147), (.088, .0018, .086), (242, 240, 232), tex={'+y': T.flat(vis)})]
    return out


def b_polaroid_photo(cfg, c=None):
    """photo instantanée debout (pour la tenir) : image vers -z, dos gris du film vers +z"""
    img = polaroid_img(str(_g(cfg, 'photo', default='silhouette')), str(_g(cfg, 'legende', 'caption', default='')))
    return [B((-.044, 0, -.001), (.088, .107, .002), (242, 240, 232), tex={'-z': img}), B((-.044, 0, .001), (.088, .107, .0005), (70, 72, 74))]


def b_walkie(p, c):
    """talkie-walkie debout : coque aux arêtes chanfreinées, grille du haut-parleur, écran du canal (`canal`), clavier, antenne caoutchouc,
    deux molettes, voyant (`voyant`), alternat sur le flanc, pince de ceinture au dos"""
    col = _col(c, (40, 42, 46)); rub = (22, 22, 24); out = []
    out += rbox(0, 0, 0, .062, .19, .036, .005, col) + rbox(0, .186, 0, .056, .006, .03, .004, _sh(col, .9))
    out += [B((-.025, .1, -.0185), (.05, .062, .002), (28, 28, 30), tex={'-z': T.grille(24, 30, (32, 32, 34))})]
    ch = str(_g(p, 'canal', 'channel', default='03'))
    out += [B((-.021, .071, -.0186), (.042, .02, .002), (150, 190, 110), tex={'-z': T.lcd(f'CH {ch}', 24, 11, (20, 40, 20), (150, 190, 110))}, texemis=.6, cast=False)]
    for r in range(2):
        for i in range(3): out.append(C((-.014 + i * .014, .053 - r * .013, -.0195), (.01, .007, .003), (64, 64, 68)))
    out += [B((-.02, .012, -.0186), (.04, .01, .001), col, tex={'-z': T.plate('NOCTA', 20, 5, col, (200, 200, 206))})]
    out += [C((-.017, .2, 0), (.016, .02, .016), rub)] + cyl_y(-.017, .21, .31, 0, .0055, rub) + [C((-.017, .315, 0), (.013, .01, .013), rub)]
    out += cyl_y(.004, .19, .202, 0, .007, (30, 30, 32)) + cyl_y(.02, .19, .206, 0, .008, (30, 30, 32)) + [C((.02, .207, 0), (.004, .002, .012), (200, 200, 200))]
    v = _g(p, 'voyant', 'led', default='rouge'); vc = (60, 230, 90) if v == 'vert' else (255, 40, 30)
    out.append(C((.006, .188, -.0172), (.005, .004, .004), vc if v else (70, 20, 20), emis=2.6 if v else 0., cast=False))
    out += [B((-.0335, .1, -.012), (.003, .045, .024), rub), C((-.0325, .075, 0), (.003, .01, .012), rub), C((-.0325, .155, 0), (.003, .008, .01), rub)]
    out += [B((.031, .03, -.012), (.002, .12, .024), rub)]
    out += [B((-.014, .07, .018), (.028, .1, .004), (52, 52, 56)), C((0, .17, .018), (.028, .006, .006), (52, 52, 56)), B((-.026, .02, .0181), (.052, .04, .001), _sh(col, .8))]
    return out


def b_binoculars(p, c, strap=True):
    """jumelles à prismes couchées : tubes d'objectif gainés, verres traités devant (-z), boîtiers de prismes, oculaires à bonnettes, pont et charnière,
    molette de mise au point crantée, plaque 8x40, courroie"""
    col = _col(c, (34, 34, 36)); rub = (20, 20, 22); out = []
    for sx in (-1, 1):
        x = sx * .05
        out += cyl_z(x, .028, -.066, -.005, .025, col) + cyl_z(x, .028, -.069, -.064, .026, rub)
        out.append(B((x - .02, .008, -.0695), (.04, .04, .001), rub, tex={'-z': lens_img(16, rub, (40, 36, 96))}, refl=.45))
        for z in (-.05, -.035, -.02): out += [C((x, .028, z), (.0505, .004, .046), _sh(col, .7)), C((x, .028, z), (.046, .0505, .004), _sh(col, .7))]
        out += rbox(sx * .04, .004, .02, .06, .052, .06, .008, col) + [C((sx * .04, .057, .02), (.048, .004, .048), _sh(col, 1.2))]
        xe = sx * .03
        out += cyl_z(xe, .036, .05, .07, .014, col) + cyl_z(xe, .036, .07, .082, .016, rub)
        out.append(B((xe - .01, .026, .082), (.02, .02, .001), rub, tex={'+z': lens_img(8, rub, (30, 30, 60))}))
        out.append(C((sx * .072, .042, .02), (.008, .01, .01), METAL, mat=M_METAL))
    out += cyl_z(0, .044, -.004, .052, .011, (46, 46, 48)) + [B((-.03, .038, .0), (.06, .008, .042), (46, 46, 48))]
    out += cyl_x(-.012, .012, .058, .04, .014, (54, 54, 56))
    for z in (.03, .036, .042, .048): out.append(C((0, .072, z), (.025, .002, .002), (110, 110, 116)))
    out.append(B((-.07, .0565, .0), (.028, .001, .012), col, tex={'+y': T.flat(T.plate('8X40', 14, 6, col, (210, 210, 214)))}))
    if strap and _g(p, 'courroie', 'strap', default=True):
        st = (40, 40, 42)
        out += OD.line((-.076, .042, .02), (-.095, .004, .07), .009, st, n=3) + OD.line((-.095, .004, .07), (.0, .004, .115), .011, st, n=5) + OD.line((.0, .004, .115), (.095, .004, .07), .011, st, n=5) + OD.line((.095, .004, .07), (.076, .042, .02), .009, st, n=3)
    return out


def b_bear(p, c, mode='assis'):
    """ours en peluche : `assis` (posé, jambes devant) ou `pendu` (tenu par une patte, le corps qui pend). Museau brodé, un œil-bouton noir et un gros bouton
    bleu dépareillé, oreilles doublées, nœud de ruban, rapiéçage écossais, couture recousue au front, une touffe de rembourrage qui dépasse"""
    fur = _col(c, (150, 100, 60)); lt = (222, 192, 146); dark = (40, 26, 20); rib = _col(_g(p, 'ruban', 'ribbon'), (150, 30, 40)); kw = dict(mat=M_FABRIC)
    out = []
    if mode == 'assis':
        out += OD.rnd(0, 0, .01, .15, .06, .13, fur, **kw)
        for sx in (-1, 1):
            x = sx * .045
            out += [C((x, .035, -.055), (.06, .06, .1), fur, **kw), C((x, .04, -.108), (.066, .074, .02), fur, **kw),
                    B((x - .026, .01, -.1185), (.052, .058, .001), lt, tex={'-z': paw_pad(col=lt, fur=fur)})]
    else:
        out += OD.rnd(0, .02, .0, .14, .05, .12, fur, **kw)
        for sx in (-1, 1):
            x = sx * .045
            out += [C((x, -.03, -.005), (.06, .1, .06), fur, **kw), C((x, -.09, -.012), (.066, .03, .074), fur, **kw),
                    B((x - .026, -.1055, -.04), (.052, .001, .056), lt, tex={'-y': paw_pad(col=lt, fur=fur)})]
    out += OD.rnd(0, .03, .01, .14, .12, .12, fur, **kw)
    out += [B((-.035, .05, -.0515), (.07, .075, .002), lt, mat=M_FABRIC), B((.012, .085, -.0525), (.028, .028, .001), (56, 84, 60), tex={'-z': tartan()})]
    out += OD.rnd(0, .15, .0, .13, .11, .11, fur, **kw)
    out += [C((0, .185, -.06), (.062, .046, .042), lt, **kw), B((-.031, .162, -.0815), (.062, .046, .001), lt, tex={'-z': bear_muzzle(col=lt)})]
    out += [C((0, .2, -.084), (.022, .012, .008), dark, refl=.3)]
    out += [C((-.03, .222, -.0525), (.014, .014, .006), (12, 12, 14), refl=.4), C((-.033, .226, -.0558), (.003, .003, .001), (220, 220, 230))]
    out += [B((.019, .211, -.0565), (.022, .022, .004), fur, tex={'-z': button_img((70, 110, 160))}), C((.03, .222, -.0532), (.004, .004, .004), (230, 222, 200))]
    out += [B((-.04, .234, -.0555), (.08, .02, .001), fur, tex={'-z': seam(fur=fur)})]
    for sx in (-1, 1):
        out += [C((sx * .056, .262, .005), (.046, .044, .026), fur, **kw), C((sx * .056, .258, -.0085), (.028, .026, .002), lt, **kw)]
    out += [C((0, .152, .01), (.124, .016, .11), rib), C((0, .152, -.049), (.014, .018, .012), rib), C((-.019, .156, -.05), (.024, .022, .008), rib), C((.019, .156, -.05), (.024, .022, .008), rib),
            C((-.008, .136, -.052), (.007, .022, .004), rib), C((.01, .134, -.052), (.007, .026, .004), rib)]
    out += [C((-.064, .148, -.03), (.02, .016, .02), (244, 240, 230), **kw), C((-.06, .158, -.034), (.012, .01, .012), (236, 232, 222), **kw)]
    if mode == 'assis':
        for sx in (-1, 1):
            out += OD.line((sx * .07, .135, .0), (sx * .088, .07, -.045), .045, fur, n=3, mat=M_FABRIC) + [C((sx * .09, .058, -.055), (.04, .036, .04), fur, **kw), C((sx * .09, .056, -.0755), (.026, .024, .001), lt)]
    else:
        out += OD.line((-.07, .14, 0), (-.085, .33, 0), .042, fur, n=5, mat=M_FABRIC) + [C((-.086, .345, 0), (.04, .036, .04), fur, **kw), C((-.086, .345, -.0205), (.026, .024, .001), lt)]
        out += OD.line((.07, .135, 0), (.085, .05, -.01), .045, fur, n=3, mat=M_FABRIC) + [C((.086, .04, -.012), (.04, .036, .04), fur, **kw)]
    return out


def b_doll(p, c, mode='assis'):
    """poupée ancienne : tête de porcelaine (`fele` : fêlée), anglaises qui tombent sur les épaules, gros nœud, robe de velours à col de dentelle et boutons de nacre,
    jupon de dentelle, manches bouffantes, mains de porcelaine, bas blancs et bottines. `assis` (posée) ou `debout` (tenue par la taille)"""
    dress = _col(c, (110, 34, 54)); lace = (238, 232, 218); skin = (242, 228, 216); hair = _col(_g(p, 'cheveux', 'hair'), (150, 96, 46)); boot = (24, 20, 20); stk = (236, 232, 226)
    out = []
    if mode == 'assis':
        out += OD.rnd(0, 0, 0, .2, .006, .185, lace) + OD.rnd(0, .006, 0, .19, .064, .17, dress, mat=M_FABRIC) + OD.rnd(0, .07, .005, .14, .05, .12, dress, mat=M_FABRIC)
        for sx in (-1, 1):
            out += [C((sx * .03, .016, -.11), (.026, .026, .06), stk), C((sx * .03, .026, -.148), (.03, .046, .026), boot, refl=.25)]
        y0 = .12
    else:
        for sx in (-1, 1): out += [C((sx * .022, .015, -.004), (.026, .03, .036), boot, refl=.25), C((sx * .022, .05, 0), (.022, .04, .022), stk)]
        out += OD.rnd(0, .062, 0, .15, .006, .13, lace) + OD.rnd(0, .068, 0, .145, .07, .125, dress, mat=M_FABRIC) + OD.rnd(0, .138, 0, .11, .06, .09, dress, mat=M_FABRIC)
        y0 = .198
    out += [C((0, y0 + .04, 0), (.08, .08, .06), dress, mat=M_FABRIC), B((-.03, y0 + .002, -.0305), (.06, .066, .001), dress, tex={'-z': doll_dress(col=dress, lace=lace)}),
            C((0, y0 + .081, 0), (.088, .012, .066), lace), C((0, y0 + .006, 0), (.084, .01, .064), _sh(dress, .6))]
    for sx in (-1, 1):
        out += [C((sx * .055, y0 + .062, 0), (.036, .034, .042), dress, mat=M_FABRIC), C((sx * .06, y0 + .02, -.012), (.022, .05, .022), dress, mat=M_FABRIC),
                C((sx * .06, y0 - .008, -.014), (.026, .008, .026), lace), C((sx * .06, y0 - .02, -.016), (.018, .018, .018), skin, refl=.25)]
    out += [C((0, y0 + .092, 0), (.026, .016, .026), skin)]
    hy = y0 + .1
    out += [C((0, hy + .04, 0), (.084, .08, .078), skin, refl=.3), B((-.037, hy + .004, -.0395), (.074, .072, .001), skin, tex={'-z': doll_face(fele=bool(_g(p, 'fele', 'cracked', default=True)))}, refl=.25)]
    out += [C((0, hy + .084, .006), (.094, .018, .088), hair), C((0, hy + .045, .036), (.094, .09, .022), hair), C((0, hy + .074, -.034), (.08, .012, .012), hair)]
    for sx in (-1, 1):
        for i in range(4):
            out.append(C((sx * (.05 + .002 * i), hy + .055 - i * .022, .012 - .004 * i), (.018, .026, .02), _sh(hair, 1. - .06 * (i % 2))))
    bow = _col(_g(p, 'noeud', 'bow'), (238, 230, 214))
    out += [C((0, hy + .098, .0), (.022, .02, .02), bow), C((-.026, hy + .1, .0), (.032, .028, .014), bow), C((.026, hy + .1, .0), (.032, .028, .014), bow)]
    return out


def b_music_box(p, c):
    """boîte à musique ouverte : coffret de bois verni et marqueté, intérieur de velours, danseuse au tutu sur son socle, miroir ovale dans le couvercle,
    peigne et cylindre à picots sous une vitre, clé papillon sur le côté, pieds boule ; `ferme: true` : couvercle rabattu"""
    wood = _col(c, (110, 60, 34)); vel = _col(_g(p, 'velours', 'velvet'), (140, 22, 42)); out = []
    out += [C((sx * .07, .003, sz * .04), (.012, .006, .012), BRASS, mat=M_METAL) for sx in (-1, 1) for sz in (-1, 1)]
    y0 = .006
    out += [B((-.08, y0, -.05), (.16, .012, .1), wood, mat=M_WOODV), B((-.08, y0, -.05), (.16, .06, .008), wood, mat=M_WOODV, tex={'-z': marquetry(wood=wood)}),
            B((-.08, y0, .042), (.16, .06, .008), wood, mat=M_WOODV), B((-.08, y0, -.042), (.008, .06, .084), wood, mat=M_WOODV), B((.072, y0, -.042), (.008, .06, .084), wood, mat=M_WOODV)]
    out += [B((-.08, y0 + .058, -.05), (.16, .004, .1), _sh(wood, 1.25), mat=M_WOODV)] if False else []
    if _g(p, 'ferme', 'closed', default=False):
        return out + [B((-.081, y0 + .06, -.051), (.162, .016, .102), wood, mat=M_WOODV, tex={'+y': T.flat(marquetry(wood=wood))}), C((0, y0 + .052, -.052), (.012, .012, .004), BRASS, mat=M_METAL)]
    out += [B((-.072, y0 + .012, -.042), (.144, .03, .084), vel, mat=M_FABRIC)]
    out += cyl_x(-.066, -.032, y0 + .03, .0, .009, BRASS, mat=M_METAL) + [B((-.066, y0 + .036, -.024), (.034, .003, .014), STEEL, mat=M_METAL)]
    for i in range(6): out.append(C((-.063 + i * .006, y0 + .039, .0), (.002, .002, .002), (240, 236, 220)))
    out += [B((-.072, y0 + .042, -.042), (.052, .002, .084), (196, 214, 226), dissolve=.55, refl=.35, cast=False), B((-.021, y0 + .012, -.042), (.004, .032, .084), _sh(wood, 1.2))]
    bx, bz = .025, .0; fy = y0 + .042
    out += cyl_y(bx, fy, fy + .006, bz, .016, BRASS, mat=M_METAL, refl=.3)
    pink = (238, 186, 196); skin = (240, 220, 206)
    out += [C((bx - .002, fy + .02, bz), (.004, .028, .004), pink), C((bx + .005, fy + .03, bz), (.004, .012, .004), pink)]
    out += cyl_y(bx, fy + .03, fy + .036, bz, .016, (250, 240, 244)) + cyl_y(bx, fy + .036, fy + .04, bz, .012, (246, 230, 236))
    out += [C((bx, fy + .047, bz), (.01, .016, .007), pink), C((bx, fy + .059, bz), (.008, .009, .008), skin), C((bx, fy + .065, bz + .002), (.006, .005, .006), (60, 36, 26))]
    out += [C((bx - .008, fy + .058, bz), (.003, .016, .003), skin), C((bx + .008, fy + .058, bz), (.003, .016, .003), skin), C((bx, fy + .068, bz), (.016, .003, .003), skin)]
    out += [B((-.08, y0 + .06, .04), (.16, .11, .012), wood, mat=M_WOODV, tex={'+z': marquetry(wood=wood)}), B((-.072, y0 + .066, .0395), (.144, .098, .001), vel, mat=M_FABRIC)]
    out += [B((-.034, y0 + .085, .039), (.068, .058, .001), vel, tex={'-z': oval_mirror()}, refl=.6)]
    out += [C((.083, y0 + .03, 0), (.006, .006, .006), BRASS, mat=M_METAL), C((.089, y0 + .03, 0), (.004, .02, .006), BRASS, mat=M_METAL),
            C((.089, y0 + .04, 0), (.004, .012, .016), BRASS, mat=M_METAL), C((.089, y0 + .02, 0), (.004, .012, .016), BRASS, mat=M_METAL)]
    return out


def b_mirror(p, c):
    """miroir à main debout, glace vers -z : cadre ovale en gradins, glace qui reflète (`fele` : fêlé), dos repoussé, cimier, col et manche tourné"""
    fr = _col(c, (186, 186, 192)); gl = (172, 192, 208); out = []
    W_, H_, yc = .14, .18, .24; n = 9
    for i in range(n):
        y0 = -H_ / 2 + H_ * i / n; y1 = -H_ / 2 + H_ * (i + 1) / n; ym = (y0 + y1) / 2
        hw = max(W_ * .18, (W_ / 2) * math.sqrt(max(0., 1 - (ym / (H_ / 2)) ** 2)) * 1.05)
        out.append(B((-hw, yc + y0, -.004), (2 * hw, y1 - y0, .01), fr, mat=M_METAL, refl=.2))
        iw = hw - .012; Hi = H_ / 2 - .012
        if abs(ym) < Hi and iw > .01:
            gw = max(.008, (W_ / 2 - .012) * math.sqrt(max(0., 1 - (ym / Hi) ** 2)) * 1.03)
            out.append(B((-gw, yc + y0, -.0055), (2 * gw, y1 - y0, .0016), gl, refl=.78))
    out.append(B((-.05, yc - .07, .006), (.1, .14, .001), fr, tex={'+z': mirror_back(col=fr)}, mat=M_METAL))
    out += [C((0, yc + H_ / 2 + .008, 0), (.034, .018, .012), fr, mat=M_METAL), C((0, yc + H_ / 2 + .02, 0), (.012, .01, .01), fr, mat=M_METAL)]
    out += [C((0, yc - H_ / 2 - .006, 0), (.03, .02, .016), fr, mat=M_METAL), C((0, .14, 0), (.026, .008, .02), fr, mat=M_METAL),
            C((0, .085, 0), (.022, .1, .016), fr, mat=M_METAL), C((0, .035, 0), (.026, .006, .02), fr, mat=M_METAL), C((0, .016, 0), (.03, .032, .022), fr, mat=M_METAL)]
    if _g(p, 'fele', 'cracked', default=True):
        k = (70, 72, 80); o = (.028, yc - .04, -.0072)
        for (a, b_) in (((.018, -.012), (.034, -.03)), ((-.012, -.02), (-.018, -.048)), ((.004, .026), (-.01, .062)), ((-.022, .006), (-.044, .018)), ((.02, .01), (.03, .02))):
            m_ = (o[0] + a[0], o[1] + a[1], o[2]); out += OD.line(o, m_, .0018, k, n=3, cast=False) + OD.line(m_, (o[0] + b_[0], o[1] + b_[1], o[2]), .0018, k, n=3, cast=False)
    return out


def b_envelope_flat(p, c):
    """enveloppe à plat (adresse et timbre, ou `dos: true` : rabat et cachet de cire brisé) + lettre dépliée à côté, lisible depuis l'avant (`texte`)"""
    pap = _col(c, (226, 214, 186)); out = []
    if _g(p, 'dos', 'back', default=False): img = envelope_back(paper=pap, broken=bool(_g(p, 'lettre', 'letter', default=True)))
    else: img = envelope_front(str(_g(p, 'nom', 'name', default='MME C. ROUX')), T.lines(_g(p, 'adresse', 'address'), ('12 RUE DES LILAS', '76000 ROUEN')), paper=pap)
    out += [B((-.17, 0, -.06), (.162, .003, .114), pap, tex={'+y': T.flat(img)}, mat=M_CARD)]
    if _g(p, 'lettre', 'letter', default=True):
        lt = letter_img(T.lines(_g(p, 'texte', 'text'))); H = lt.shape[0]
        for i, (ya, yb) in enumerate(((.0035, .0035), (.001, .001), (.0035, .0035))):
            r0, r1 = H * i // 3, H * (i + 1) // 3; z0 = .105 - .21 * (i + 1) / 3
            out.append(B((.0, ya, z0), (.148, .0015, .07), (240, 234, 216), tex={'+y': T.flat(np.ascontiguousarray(lt[r0:r1]))}))
    return out


def b_candelabra(p, c):
    """chandelier à trois branches : pied en gradins, fût à nœuds, bras en S, bobèches et bassinets, trois bougies de hauteurs différentes avec coulures,
    mèches et flammes (`allumee`) ; `cire` : couleur des bougies"""
    m = _col(c, (170, 134, 70)); wax = _col(_g(p, 'cire', 'wax'), (232, 222, 196)); lit = bool(_g(p, 'allumee', 'on', 'lit', default=True)); kw = dict(mat=M_METAL, refl=.25); out = []
    out += cyl_y(0, 0, .014, 0, .07, m, **kw) + cyl_y(0, .014, .028, 0, .052, m, **kw) + cyl_y(0, .028, .05, 0, .026, m, **kw)
    out += cyl_y(0, .05, .11, 0, .011, m, **kw) + cyl_y(0, .11, .13, 0, .02, m, **kw) + cyl_y(0, .13, .19, 0, .009, m, **kw) + cyl_y(0, .19, .21, 0, .018, m, **kw) + cyl_y(0, .21, .3, 0, .01, m, **kw)
    for sx in (-1, 1):
        out += OD.line((0, .228, 0), (sx * .07, .212, 0), .013, m, n=4, **kw) + OD.line((sx * .07, .212, 0), (sx * .115, .238, 0), .013, m, n=3, **kw) + OD.line((sx * .115, .238, 0), (sx * .13, .268, 0), .013, m, n=2, **kw)
    tops = []
    for x, cy, h in ((-.13, .268, .11), (0., .3, .145), (.13, .268, .125)):
        out += cyl_y(x, cy, cy + .012, 0, .02, m, **kw) + cyl_y(x, cy + .01, cy + .015, 0, .028, m, **kw)
        y0 = cy + .015
        out += OD.rnd2(x, y0, 0, .022, h, .022, wax) + [C((x, y0 + h - .002, 0), (.018, .004, .018), _sh(wax, .9))]
        out += [C((x + .011, y0 + h - .02, .004), (.005, .03, .005), wax), C((x - .009, y0 + h - .045, -.008), (.005, .05, .005), wax), C((x + .014, y0 + .004, .006), (.01, .006, .01), wax)]
        top = y0 + h; out.append(C((x, top + .005, 0), (.003, .01, .003), (26, 20, 18)))
        if lit:
            out += [C((x, top + .016, 0), (.008, .016, .008), (255, 240, 180), emis=2.8, cast=False), C((x, top + .021, 0), (.014, .03, .014), (255, 150, 50), emis=1.6, dissolve=.45, cast=False)]
        tops.append(top)
    return out


def b_axe(p, c):
    """hache debout (pour la tenir, le manche selon y) : manche de frêne galbé, poignée salie, fer à joues et talon, tranchant affûté qui brille,
    coin de serrage, taches de rouille"""
    wood = _col(c, (156, 112, 68)); st = (74, 76, 82); br = (206, 210, 216); rust = (122, 64, 32); out = []
    out += [C((0, .025, .006), (.03, .05, .042), wood, mat=M_WOODV), C((0, .13, .005), (.024, .16, .034), _sh(wood, .78), mat=M_WOODV), C((0, .13, .005), (.03, .16, .028), _sh(wood, .78), mat=M_WOODV),
            C((0, .34, .002), (.024, .26, .032), wood, mat=M_WOODV), C((0, .34, .002), (.028, .26, .026), wood, mat=M_WOODV), C((0, .535, 0), (.024, .13, .03), wood, mat=M_WOODV)]
    out += [B((-.012, .6, -.032), (.024, .11, .064), st, mat=M_METAL), B((-.011, .615, .032), (.022, .08, .03), st, mat=M_METAL), B((-.0115, .618, .06), (.023, .074, .004), (90, 92, 98), mat=M_METAL)]
    out += [B((-.01, .59, -.07), (.02, .13, .04), st, mat=M_METAL), B((-.008, .578, -.11), (.016, .154, .04), st, mat=M_METAL), B((-.006, .566, -.14), (.012, .178, .03), _sh(st, 1.15), mat=M_METAL)]
    out += [B((-.0035, .562, -.152), (.007, .186, .012), br, mat=M_METAL, refl=.35), B((-.0065, .566, -.142), (.013, .178, .006), br, mat=M_METAL, refl=.3)]
    out += [C((0, .713, 0), (.016, .006, .03), wood), C((0, .716, 0), (.004, .006, .03), (50, 50, 54))]
    out += [B((.0101, .63, -.085), (.001, .022, .014), rust), B((-.0111, .66, -.05), (.001, .016, .02), rust), B((.0121, .64, .0), (.001, .03, .02), rust)]
    return out


def b_knife(p, c):
    """grand couteau debout (manche selon y, tranchant vers -z) : manche noir à trois rivets, culot, mitre, lame large qui s'effile en pointe,
    fil brillant, taches sombres (rien de gore)"""
    hd = _col(c, (26, 24, 24)); st = (188, 192, 200); br = (226, 230, 236); out = []
    out += [C((0, .06, .0), (.02, .12, .028), hd), C((0, .06, 0), (.016, .12, .034), hd), C((0, .004, 0), (.022, .008, .034), (60, 60, 64), mat=M_METAL)]
    for y in (.025, .06, .095):
        for sx in (-1, 1): out.append(C((sx * .0105, y, 0), (.002, .008, .008), METAL, mat=M_METAL))
    out += [C((0, .127, -.002), (.012, .014, .04), st, mat=M_METAL, refl=.3)]
    n = 9; y0, L = .134, .22
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n; tm = (t0 + t1) / 2
        ze = -.036 + .036 * tm ** 1.8; zs = .016 - .012 * tm ** 3
        out += [B((-.002, y0 + L * t0, ze), (.004, L / n, zs - ze), st, mat=M_METAL, refl=.35), B((-.0025, y0 + L * t0, ze - .001), (.005, L / n, .006), br, mat=M_METAL, refl=.4)]
    out += [C((0, y0 + L + .006, .002), (.003, .012, .006), st, mat=M_METAL)]
    out += [B((.0021, .2, -.01), (.001, .02, .012), (90, 82, 70)), B((-.0031, .26, -.004), (.001, .014, .01), (90, 82, 70))]
    return out


def b_syringe(p, c):
    """seringue ancienne couchée : corps de verre gradué, liquide (`contenu`), piston de caoutchouc, bagues de métal, deux anneaux pour les doigts,
    tige et anneau du pouce, embout et aiguille"""
    gl = (206, 220, 226); m = _col(c, METAL); y = .009
    liq = {'vert': (110, 220, 120), 'ambre': (214, 140, 40), 'clair': (190, 220, 236), 'noir': (30, 30, 34)}.get(str(_g(p, 'contenu', default='vert')), (110, 220, 120))
    out = cyl_x(-.005, .078, y, 0, .0064, liq, emis=.25 if _g(p, 'contenu', default='vert') == 'vert' else 0.)
    bar = cyl_x(-.02, .08, y, 0, .0085, gl, refl=.4, dissolve=.42, cast=False)
    bar[0].tex = {3: T.flat(graduations())}; bar[1].tex = {4: graduations()}
    out += bar + [C((-.007, y, 0), (.006, .0125, .0125), (40, 40, 44))] + cyl_x(-.02, -.007, y, 0, .0022, m, mat=M_METAL)
    out += cyl_x(.078, .088, y, 0, .0092, m, mat=M_METAL, refl=.3) + cyl_x(.088, .1, y, 0, .0042, m, mat=M_METAL, refl=.3) + [C((.1225, y, 0), (.045, .0016, .0016), (226, 230, 236), mat=M_METAL, refl=.4)]
    out += cyl_x(-.027, -.019, y, 0, .0098, m, mat=M_METAL, refl=.3)
    for sz in (-1, 1):
        cz = sz * .023
        out += [C((-.023, .0025, cz - .008), (.02, .004, .004), m, mat=M_METAL), C((-.023, .0025, cz + .008), (.02, .004, .004), m, mat=M_METAL),
                C((-.031, .0025, cz), (.004, .004, .02), m, mat=M_METAL), C((-.015, .0025, cz), (.004, .004, .02), m, mat=M_METAL), C((-.023, .005, sz * .0115), (.006, .006, .007), m, mat=M_METAL)]
    out += [C((-.048, y, 0), (.042, .004, .004), m, mat=M_METAL), C((-.069, .006, 0), (.004, .008, .008), m, mat=M_METAL)]
    out += [C((-.08, .0025, -.009), (.022, .004, .004), m, mat=M_METAL), C((-.08, .0025, .009), (.022, .004, .004), m, mat=M_METAL), C((-.089, .0025, 0), (.004, .004, .022), m, mat=M_METAL),
            C((-.071, .0025, 0), (.004, .004, .022), m, mat=M_METAL)]
    return out


# ================================================================== posed kinds
def k_typewriter(p, c): return b_typewriter(p, c)
def k_tape_recorder(p, c): return b_tape_recorder(p, c)
def k_film_camera(p, c): return b_film_camera(p, c)
def k_polaroid(p, c): return b_polaroid(p, c, photo=_g(p, 'photo', default='silhouette') is not False)
def k_walkie(p, c): return b_walkie(p, c)
def k_binoculars(p, c): return b_binoculars(p, c)
def k_bear(p, c): return b_bear(p, c, 'assis')
def k_doll(p, c): return b_doll(p, c, 'assis')
def k_music_box(p, c): return b_music_box(p, c)
def k_mirror(p, c): return _floor(_shift(_lay_up(b_mirror(p, c)), 0., 0., -.18))
def k_envelope(p, c): return b_envelope_flat(p, c)
def k_candelabra(p, c): return b_candelabra(p, c)
def k_syringe(p, c): return b_syringe(p, c)
def k_knife(p, c): return _floor(_shift(_lay_x(b_knife(p, c)), -.18, 0., 0.))


def k_axe(p, c):
    if not _g(p, 'billot', 'block', default=False): return _floor(_shift(_lay_x(b_axe(p, c)), -.36, 0., 0.))
    wood = (128, 92, 58); bark = (70, 52, 38); out = []
    out += OD.rnd(0, 0, 0, .42, .34, .4, bark, mat=M_WOODV) + [B((-.12, .34, -.12), (.24, .002, .24), wood, tex={'+y': T.flat(end_grain(wood=wood))}), C((0, .3405, 0), (.3, .002, .16), wood), C((0, .3405, 0), (.16, .002, .3), wood)]
    st = (74, 76, 82); top = .342
    out += [B((-.012, top - .03, -.07), (.024, .055, .1), st, mat=M_METAL), B((-.012, top + .025, -.045), (.024, .03, .05), st, mat=M_METAL), B((-.011, top + .045, .0), (.022, .03, .03), st, mat=M_METAL)]
    hw = _col(c, (156, 112, 68))
    out += OD.line((0, top + .04, .02), (0, top + .3, .55), .028, hw, n=14, mat=M_WOODV) + [C((0, top + .31, .57), (.032, .04, .04), hw, mat=M_WOODV)]
    return out


# ================================================================== held (PS1)
def _grip(face, x, y, z, d):
    """point de prise d'un objet tenu : (x, y, z) de l'objet est mis dans le poing, puis l'objet avance de `d` devant la main (le poing de PS1 est un cube de 12 cm)"""
    return (x, y, z + d) if face == 'front' else (x, y, z - d)


def _edge_out(bx):
    """lame vue à plat : (x, y, z) -> (z, y, -x), le tranchant (-z) passe du côté extérieur de la main, le plat de la lame vers l'avant"""
    for b in bx:
        lo, hi = b.lo.copy(), b.hi.copy()
        b.lo = np.array([lo[2], lo[1], -hi[0]], np.float32); b.hi = np.array([hi[2], hi[1], -lo[0]], np.float32); b.tex = {}
    return bx


def h_polaroid(P, F, k, lights, col, cfg):
    """appareil instantané tenu par le dessous du boîtier, l'objectif devant, la photo qui sort"""
    fc = _face(cfg)
    return _hold(P, F, b_polaroid(cfg, col, photo=_g(cfg, 'photo', default='silhouette') is not False), _grip(fc, 0., .0, .0, .075), fc)


def h_polaroid_photo(P, F, k, lights, col, cfg):
    """photo instantanée pincée par la bande du bas, devant le poing : l'image se montre devant (`vers_soi: true` : on la regarde)"""
    fc = _face(cfg)
    return _hold(P, F, b_polaroid_photo(cfg), _grip(fc, 0., .0, 0., .075), fc)


def h_walkie(P, F, k, lights, col, cfg):
    """talkie-walkie tenu par le bas, antenne en haut, grille et écran vers celui qui parle (`montre: true` : vers l'avant)"""
    fc = _face(cfg, 'holder')
    return _hold(P, F, b_walkie(cfg, col), _grip(fc, 0., .02, 0., .05), fc)


def h_binoculars(P, F, k, lights, col, cfg):
    """jumelles tenues par le pont, posées sur le poing, les objectifs devant"""
    fc = _face(cfg)
    return _hold(P, F, b_binoculars(cfg, col, strap=False), _grip(fc, 0., -.03, .0, .06), fc)


def h_bear(P, F, k, lights, col, cfg):
    """ours en peluche qui pend au bout du bras, tenu par une patte, tourné vers l'avant"""
    fc = _face(cfg)
    return _hold(P, F, b_bear(cfg, col, 'pendu'), _grip(fc, -.086, .345, 0., .03), fc)


def h_doll(P, F, k, lights, col, cfg):
    """poupée tenue par la taille, debout, le visage vers l'avant"""
    fc = _face(cfg)
    return _hold(P, F, b_doll(cfg, col, 'debout'), _grip(fc, 0., .215, 0., .035), fc)


def h_mirror(P, F, k, lights, col, cfg):
    """miroir à main tenu par le manche, la glace vers celui qui s'y regarde (`montre: true` : vers l'avant)"""
    fc = _face(cfg, 'holder')
    return _hold(P, F, b_mirror(cfg, col), _grip(fc, 0., .07, 0., .02), fc)


def h_envelope(P, F, k, lights, col, cfg):
    """lettre tenue droite devant le poing, lisible des deux côtés (comme la feuille du standard), l'enveloppe derrière dans la même main"""
    lt = letter_img(T.lines(cfg.get('texte'))); pap = _col(col, (226, 214, 186))
    env = envelope_front(str(cfg.get('nom', 'MME C. ROUX')), T.lines(cfg.get('adresse'), ('12 RUE DES LILAS', '76000 ROUEN')), paper=pap)
    bx = [B((-.074, .0, -.001), (.148, .21, .002), (240, 234, 216), tex={'-z': lt, '+z': lt}, texemis=.1),
          B((-.03, -.03, .006), (.162, .114, .003), pap, tex={'-z': env, '+z': envelope_back(paper=pap)})]
    return _hold(P, F, bx, _grip('front', 0., .03, 0., .07), 'front')


def h_axe(P, F, k, lights, col, cfg):
    """hache tenue au bas du manche, le fer en haut, vue à plat (tranchant vers l'extérieur ; `tranchant: avant` : vers l'avant ; `prise: haut` : tenue sous le fer)"""
    bx = b_axe(cfg, col); ay = .52 if cfg.get('prise') == 'haut' else .16
    if cfg.get('tranchant') != 'avant': bx = _edge_out(bx); return _hold(P, F, bx, (.004, ay, 0.), 'front')
    return _hold(P, F, bx, (0., ay, .004), 'front')


def h_knife(P, F, k, lights, col, cfg):
    """grand couteau tenu par le manche, lame vers le haut vue à plat (`tranchant: avant` : tranchant devant ; `lame: bas` : prise poignard, lame vers le bas)"""
    bx = b_knife(cfg, col); ay = .06
    if cfg.get('lame') == 'bas':
        for b in bx:
            lo, hi = b.lo.copy(), b.hi.copy(); b.lo = np.array([-hi[0], -hi[1], lo[2]], np.float32); b.hi = np.array([-lo[0], -lo[1], hi[2]], np.float32)
        ay = -.06
    if cfg.get('tranchant') != 'avant': bx = _edge_out(bx)
    return _hold(P, F, bx, (0., ay, 0.), 'front')


def h_cassette(P, F, k, lights, col, cfg):
    """cassette montrée entre les doigts, devant le poing, l'étiquette vers l'avant (`vers_soi: true` : vers soi)"""
    lab = T.lines(_g(cfg, 'etiquette', 'label'), ('NE PAS', 'ECOUTER')); fc = _face(cfg)
    img = cassette_face(lab, shell=_col(col, (36, 36, 40)))
    bx = [B((-.05, 0, -.0055), (.1, .064, .011), _col(col, (36, 36, 40)), tex={'-z': img}), B((-.03, -.001, -.004), (.06, .002, .008), (20, 20, 22))]
    return _hold(P, F, bx, _grip(fc, 0., -.02, 0., .07), fc)


# ================================================================== registration (objets._load_lots)
POSED = [('od_typewriter', k_typewriter, 'machine à écrire', None), ('od_tape_recorder', k_tape_recorder, 'magnétophone à cassette', None),
         ('od_cassette', k_cassette, 'cassette audio dans son boîtier', None), ('od_film_camera', k_film_camera, 'appareil photo argentique', None),
         ('od_polaroid', k_polaroid, 'appareil photo instantané', None), ('od_walkie_talkie', k_walkie, 'talkie-walkie', None),
         ('od_binoculars', k_binoculars, 'jumelles', None), ('od_teddy_bear', k_bear, 'ours en peluche', None), ('od_porcelain_doll', k_doll, 'poupée ancienne', None),
         ('od_music_box', k_music_box, 'boîte à musique', None), ('od_hand_mirror', k_mirror, 'miroir à main', None), ('od_envelope', k_envelope, 'enveloppe et lettre', None),
         ('od_candelabra', k_candelabra, 'chandelier à trois branches', [((0, .5, 0), (1, .62, .3), .8, 2.4, 'soft')]), ('od_axe', k_axe, 'hache', None),
         ('od_knife_horror', k_knife, 'grand couteau', None), ('od_syringe', k_syringe, 'seringue ancienne', None)]
HELD = [('od_polaroid', h_polaroid, 'appareil instantané tenu, la photo qui sort'), ('od_polaroid_photo', h_polaroid_photo, 'photo instantanée montrée'),
        ('od_walkie_talkie', h_walkie, 'talkie-walkie (grille vers soi)'), ('od_binoculars', h_binoculars, 'jumelles tenues par le pont'),
        ('od_teddy_bear', h_bear, 'ours en peluche tenu par la patte'), ('od_porcelain_doll', h_doll, 'poupée tenue par la taille'),
        ('od_hand_mirror', h_mirror, 'miroir à main (glace vers soi)'), ('od_envelope', h_envelope, 'lettre et enveloppe'),
        ('od_axe', h_axe, 'hache'), ('od_knife_horror', h_knife, 'grand couteau'), ('od_cassette', h_cassette, 'cassette montrée')]


def enregistrer(R):
    """un nom déjà pris par un autre lot est sauté (et dit) : le reste du lot se charge quand même"""
    for kind, fn, lab, lights in POSED:
        try: R.objet(kind, fn, lab, lumieres=lights)
        except ValueError as e: print(e)
    for name, fn, lab in HELD:
        try: R.tenu(name, fn, lab)
        except ValueError as e: print(e)
