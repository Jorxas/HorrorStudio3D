"""CHAMBRE 313 (PS1) : personnages et objets tenus, ajoutés au moteur SANS modifier ses fichiers figés.

`poses.py` et `creatures.py` sont épinglés (manifeste SHA-256 de `tools/check_voxelgpu.py`) : on n'y écrit rien. `register()`
ajoute, une seule fois par processus (appelé depuis `sets.py`) :
  * des préréglages de `cast` dans `creatures.PRESETS` : `receptionniste`, six clients (`cliente_agee`, `client_pyjama`,
    `cliente_peignoir`, `client_tshirt`, `cliente_nuisette`, `ado_pyjama`), `pompier`, `pompier_2`, `chef_pompier`,
    `technicien`, `mere_fantome`, `garcon_fantome` ;
  * des tenues (`poses.OUTFITS`) : `gilet` (chemise blanche + gilet sombre + badge ; `hood` = la chemise, `shirt` = le gilet),
    `pyjama` (haut rayé), `peignoir` (peignoir ceinturé jusqu'aux genoux), `chemise_nuit` (longue chemise de nuit),
    `veste_feu` (veste de pompier à bandes réfléchissantes), `polo` (polo à col et patte de boutonnage) ;
  * un couvre-chef (`poses.HATS`) : `casque_f1` (casque de pompier à visière, couleur `hat_color`) ;
  * des objets tenus (`poses.HOLD_ITEMS`, main droite) : `crowbar` (pied-de-biche), `handset` (combiné), `mobile` (portable,
    écran « 02:16 »), `mobile_0213`, `mobile_0214`, `printout` (journal du standard imprimé), `notebook` (carnet du pompier).
Les fonctions `poses.torso`, `poses.hair_and_hat` et `poses.held_item` sont enveloppées : pour toute valeur qu'elles connaissaient
déjà, elles rendent la main à la fonction d'origine (mêmes boîtes, même ordre). Sans ces noms dans un épisode, rien ne change.
Clé de look `face_fade` (0..1, `rigfig.face_for` enveloppée) : les traits se fondent dans la peau (la mère : 0,6).
Rien d'aléatoire, aucune horloge."""
import functools
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .r3d import C, M_FABRIC, M_METAL
from ...paths import FONT_PIXEL

NEW_OUTFITS = ('gilet', 'pyjama', 'peignoir', 'chemise_nuit', 'veste_feu', 'polo')
NEW_HATS = ('casque_f1',)
NEW_ITEMS = ('crowbar', 'handset', 'mobile', 'mobile_0213', 'mobile_0214', 'printout', 'notebook')
_ORIG = {}
_DONE = [False]

# ------------------------------------------------------------------ small text helpers (shared with hotel.py)
@functools.lru_cache(maxsize=8)
def font(sz): return ImageFont.truetype(FONT_PIXEL, sz)

# 3x5 bitmap font for tiny labels (the pixel TTF is 8 px wide per glyph: too wide for a switchboard)
_MINI = {
    '0': '111101101101111', '1': '010110010010111', '2': '111001111100111', '3': '111001111001111', '4': '101101111001001',
    '5': '111100111001111', '6': '111100111101111', '7': '111001010010010', '8': '111101111101111', '9': '111101111001111',
    ':': '000010000010000', ' ': '000000000000000', '-': '000000111000000', '.': '000000000000010', '/': '001001010100100',
    'A': '010101111101101', 'B': '110101110101110', 'C': '011100100100011', 'D': '110101101101110', 'E': '111100110100111',
    'F': '111100110100100', 'G': '011100101101011', 'H': '101101111101101', 'I': '111010010010111', 'J': '001001001101010',
    'K': '101101110101101', 'L': '100100100100111', 'M': '101111111101101', 'N': '110101101101101', 'O': '010101101101010',
    'P': '110101110100100', 'Q': '010101101110011', 'R': '110101110101101', 'S': '011100010001110', 'T': '111010010010010',
    'U': '101101101101111', 'V': '101101101101010', 'W': '101101111111101', 'X': '101101010101101', 'Y': '101101010010010',
    'Z': '111001010100111', 'É': '111100110100111', 'È': '111100110100111', 'Ê': '111100110100111', "'": '010010000000000',
    '>': '100010001010100', '<': '001010100010001', '!': '010010010000010', '(': '010100100100010', ')': '010001001001010',
}


def mini_text(d, x, y, s, col, scale=1):
    """draw `s` with the 3x5 font at (x, y) (top-left), one texel per dot times `scale`; returns the width drawn"""
    cx = x
    for ch in str(s).upper():
        g = _MINI.get(ch, _MINI[' '])
        for i, v in enumerate(g):
            if v == '1':
                px, py = cx + (i % 3) * scale, y + (i // 3) * scale
                d.rectangle([px, py, px + scale - 1, py + scale - 1], fill=col)
        cx += 4 * scale
    return cx - x


def mini_width(s, scale=1): return len(str(s)) * 4 * scale - scale


def big_text(d, x, y, s, col, sz=8):
    d.fontmode = '1'; d.text((x, y), s, font=font(sz), fill=col)
    return d.textlength(s, font=font(sz))


def seg7(d, x, y, s, col, dim=None, w=7, h=12, t=2):
    """seven-segment digits (LED clock, phone call timer): `s` like '02:13'"""
    SEG = {'0': 'abcdef', '1': 'bc', '2': 'abged', '3': 'abgcd', '4': 'fgbc', '5': 'afgcd', '6': 'afgedc', '7': 'abc', '8': 'abcdefg', '9': 'abcdfg', '-': 'g', ' ': ''}
    cx = x
    for ch in s:
        if ch == ':':
            d.rectangle([cx + 1, y + h // 3 - 1, cx + t, y + h // 3 - 1 + t - 1], fill=col)
            d.rectangle([cx + 1, y + 2 * h // 3, cx + t, y + 2 * h // 3 + t - 1], fill=col); cx += t + 3; continue
        on = SEG.get(ch, '')
        rects = {'a': (cx + t, y, cx + w - t - 1, y + t - 1), 'g': (cx + t, y + h // 2 - t // 2, cx + w - t - 1, y + h // 2 - t // 2 + t - 1),
                 'd': (cx + t, y + h - t, cx + w - t - 1, y + h - 1), 'f': (cx, y + t, cx + t - 1, y + h // 2 - 1), 'b': (cx + w - t, y + t, cx + w - 1, y + h // 2 - 1),
                 'e': (cx, y + h // 2, cx + t - 1, y + h - t - 1), 'c': (cx + w - t, y + h // 2, cx + w - 1, y + h - t - 1)}
        for k_, r in rects.items():
            if k_ in on: d.rectangle(r, fill=col)
            elif dim is not None: d.rectangle(r, fill=dim)
        cx += w + 3
    return cx - x


# ------------------------------------------------------------------ held-object textures
@functools.lru_cache(maxsize=8)
def mobile_tex(hhmm='02:16', date='VEN. 31 OCT'):
    """lock screen of the receptionist's phone: big time, date, notification line; 40x72 texels"""
    W, H = 40, 72
    im = Image.new('RGBA', (W, H), (10, 14, 34, 255)); d = ImageDraw.Draw(im)
    for y in range(H):                                              # night wallpaper gradient
        c = (10 + y // 6, 14 + y // 5, 34 + y // 3); d.line([(0, y), (W - 1, y)], fill=c + (255,))
    d.rectangle([0, 0, W - 1, 4], fill=(4, 6, 12, 255)); mini_text(d, 2, 0, '4G', (200, 200, 210, 255))
    d.rectangle([W - 9, 1, W - 3, 3], outline=(200, 200, 210, 255))
    sw = 0
    for ch in hhmm: sw += (7 + 3) if ch != ':' else 5
    seg7(d, (W - sw) // 2 + 1, 14, hhmm, (240, 244, 255, 255), w=7, h=13, t=2)
    mini_text(d, (W - mini_width(date)) // 2, 32, date, (190, 200, 230, 255))
    d.rectangle([3, 44, W - 4, 55], fill=(36, 42, 70, 255)); mini_text(d, 5, 47, 'APPEL', (240, 200, 90, 255)); mini_text(d, 25, 47, '313', (255, 120, 90, 255))
    d.rectangle([14, H - 6, W - 15, H - 5], fill=(200, 200, 210, 255))
    return np.array(im)


LOG_LINES = ('JOURNAL STANDARD', 'NUIT DU 30 AU 31/10', '', 'HEURE  POSTE   DUREE', '23:52  CH 106  00:18', '00:37  EXT     01:04',
             '02:13  CH 313  00:47', '02:14  EXT     00:22', '', 'IMPRIME LE 31/10', 'POUR ENQUETE')


@functools.lru_cache(maxsize=4)
def log_tex(lines=LOG_LINES, hl='02:13'):
    """the printed switchboard log (A4-ish, 176x248 texels): the 02:13 line underlined in red pen"""
    W, H = 176, 248
    im = Image.new('RGBA', (W, H), (236, 234, 226, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
    for y in range(0, H, 2): d.line([(0, y), (W - 1, y)], fill=(232, 230, 221, 255))          # paper grain
    y = 14
    for i, l in enumerate(lines):
        if not l: y += 8; continue
        col = (24, 24, 30, 255) if i > 1 else (20, 20, 26, 255)
        x = 10 if i > 1 else (W - d.textlength(l, font=font(8))) / 2
        d.text((x, y), l, font=font(8), fill=col)
        if l.startswith(hl):
            d.line([(8, y + 10), (W - 10, y + 10)], fill=(190, 30, 30, 255), width=2)
            d.ellipse([W - 52, y - 4, W - 4, y + 13], outline=(190, 30, 30, 255), width=1)
        y += 15 if i > 1 else 13
        if i == 1: d.line([(10, y), (W - 10, y)], fill=(60, 60, 66, 255)); y += 6
    d.rectangle([0, 0, W - 1, H - 1], outline=(200, 198, 190, 255))
    return np.array(im)


@functools.lru_cache(maxsize=2)
def notebook_tex():
    W, H = 32, 44
    im = Image.new('RGBA', (W, H), (238, 236, 226, 255)); d = ImageDraw.Draw(im)
    for y in range(8, H - 2, 5): d.line([(2, y), (W - 3, y)], fill=(170, 190, 220, 255))
    d.line([(6, 0), (6, H - 1)], fill=(210, 120, 120, 255))
    for i, w in enumerate((20, 14, 22, 9, 17)): d.line([(8, 6 + i * 5), (8 + w, 6 + i * 5)], fill=(40, 40, 60, 255))
    mini_text(d, 8, 32, '313 ?', (40, 40, 60, 255))
    return np.array(im)


# ------------------------------------------------------------------ held objects (local hand frame of poses.held_item)
def _item(item, hand, f, k, lights, col):
    x, y, z = hand; bx = []
    P = lambda lat, up, fwd: (x + lat * f, y + up, z + fwd * f)
    if item == 'crowbar':                              # pied-de-biche : 78 cm, crochet en haut, biseau en bas, peint en rouge sombre
        steel = tuple(col or (122, 26, 24))
        bx.append(C(P(0, .26, .02), (.032, .72, .032), steel, mat=M_METAL, **k))
        bx.append(C(P(0, .62, .045), (.032, .04, .06), steel, mat=M_METAL, **k))
        bx.append(C(P(0, .66, .085), (.03, .05, .04), steel, mat=M_METAL, **k))
        bx.append(C(P(0, .615, .115), (.028, .05, .03), (70, 72, 78), mat=M_METAL, **k))          # claw tip, bare steel
        bx.append(C(P(0, -.12, .035), (.03, .05, .04), (70, 72, 78), mat=M_METAL, **k))           # chisel end
        bx.append(C(P(0, -.03, .02), (.04, .1, .04), (30, 30, 34), **k))                          # grip
    elif item == 'handset':                            # combiné du téléphone de la réception (bordeaux, comme le poste)
        iv = tuple(col or (122, 34, 36))
        bx.append(C(P(0, .04, .03), (.05, .22, .05), iv, **k))
        bx.append(C(P(0, .15, .06), (.07, .07, .07), iv, **k))
        bx.append(C(P(0, -.07, .065), (.07, .065, .07), iv, **k))
        bx.append(C(P(0, -.12, .02), (.012, .1, .012), (60, 58, 52), **k))                       # cord stub
    elif item in ('mobile', 'mobile_0213', 'mobile_0214'):
        hhmm = {'mobile': '02:16', 'mobile_0213': '02:13', 'mobile_0214': '02:14'}[item]
        bx.append(C(P(0, .06, .05), (.075, .15, .016), (16, 16, 20), mat=M_METAL, **k))
        bx.append(C(P(0, .06, .041), (.066, .136, .002), (60, 80, 140), tex={'-z': mobile_tex(hhmm)}, texemis=1.1, cast=False, **k))
        bx.append(C(P(0, .06, .059), (.066, .136, .002), (60, 80, 140), tex={'+z': mobile_tex(hhmm)}, texemis=1.1, cast=False, **k))   # also readable when he shows it
        if lights is not None: lights.append((P(0, .08, -.08), (.55, .62, 1.), .35, .8))
    elif item == 'printout':
        bx.append(C(P(0, .1, .13), (.21, .297, .004), (236, 234, 226), tex={'-z': log_tex(), '+z': log_tex()}, texemis=.15, **k))
    elif item == 'notebook':
        bx.append(C(P(0, .05, .1), (.11, .15, .016), (40, 44, 60), **k))                           # cover
        bx.append(C(P(0, .05, .091), (.1, .14, .002), (238, 236, 226), tex={'-z': notebook_tex(), '+z': notebook_tex()}, **k))
        bx.append(C(P(.07, .1, .1), (.01, .12, .01), (30, 60, 160), **k))                          # pen clipped on
    return bx


def held_item(item, hand, f, k, lights=None, col=None):
    if item in NEW_ITEMS and hand is not None: return _item(item, hand, f, k, lights, col)
    return _ORIG['held_item'](item, hand, f, k, lights, col)


# ------------------------------------------------------------------ outfits
def _shade(c, m): return tuple(max(0, min(255, int(v * m))) for v in c)


def torso(cx, cz, f, yb, outfit, top, skin, k, tie=None, shirt=None, apron_color=None):
    if outfit not in NEW_OUTFITS: return _ORIG['torso'](cx, cz, f, yb, outfit, top, skin, k, tie=tie, shirt=shirt, apron_color=apron_color)
    bx = []; top = tuple(top)
    if outfit == 'gilet':                             # chemise (top) + gilet sans manches (shirt) + badge
        vest = tuple(shirt) if shirt else (36, 40, 52)
        bx.append(C((cx, yb + 1.12, cz), (.50, .64, .28), top, mat=M_FABRIC, **k))                # shirt (shoulders, collar)
        bx.append(C((cx, yb + 1.06, cz), (.52, .52, .30), vest, mat=M_FABRIC, **k))               # waistcoat body
        bx.append(C((cx, yb + 1.26, cz + f * .152), (.13, .14, .01), top, **k))                   # V of the shirt
        bx.append(C((cx, yb + 1.25, cz + f * .156), (.035, .13, .01), tuple(tie) if tie else _shade(top, .82), **k))
        bx.append(C((cx, yb + 1.43, cz + f * .06), (.30, .05, .18), top, **k))                    # collar
        for yy in (1.13, 1.03, .93): bx.append(C((cx + .02, yb + yy, cz + f * .153), (.025, .025, .01), _shade(vest, 1.9), **k))
        bx.append(C((cx - .14, yb + 1.21, cz + f * .156), (.09, .055, .01), (236, 232, 214), emis=.15, **k))   # badge
        bx.append(C((cx - .14, yb + 1.215, cz + f * .158), (.07, .012, .004), (40, 70, 140), **k))
        bx.append(C((cx, yb + .80, cz), (.505, .05, .29), _shade(vest, .7), **k))                 # hem
    elif outfit == 'pyjama':                          # haut rayé, col passepoilé, boutons
        lt = _shade(top, 1.35)
        bx.append(C((cx, yb + 1.12, cz), (.50, .64, .28), top, mat=M_FABRIC, **k))
        for yy in (.90, 1.04, 1.18, 1.32): bx.append(C((cx, yb + yy, cz), (.505, .045, .285), lt, mat=M_FABRIC, **k))
        bx.append(C((cx, yb + 1.41, cz + f * .07), (.30, .05, .17), lt, **k))
        for yy in (1.30, 1.16, 1.02): bx.append(C((cx, yb + yy, cz + f * .145), (.022, .022, .01), (236, 232, 222), **k))
    elif outfit == 'peignoir':                        # peignoir ceinturé jusqu'aux genoux, encolure en V
        lt = _shade(top, 1.12); dk = _shade(top, .78)
        bx.append(C((cx, yb + 1.08, cz), (.54, .72, .32), top, mat=M_FABRIC, **k))
        bx.append(C((cx, yb + .58, cz), (.58, .40, .36), top, mat=M_FABRIC, **k))                 # skirt to the knees
        bx.append(C((cx, yb + 1.30, cz + f * .162), (.12, .18, .01), skin, **k))                  # V neck
        for s_ in (-1, 1): bx.append(C((cx + s_ * .08, yb + 1.28, cz + f * .168), (.05, .24, .01), lt, **k))   # lapels
        bx.append(C((cx, yb + .90, cz), (.555, .06, .325), dk, **k))                              # belt
        bx.append(C((cx + .1, yb + .80, cz + f * .17), (.05, .16, .01), dk, **k))                 # belt end
    elif outfit == 'chemise_nuit':                    # longue chemise de nuit (années 2000), dentelle au col
        lt = _shade(top, 1.1)
        bx.append(C((cx, yb + 1.12, cz), (.46, .62, .26), top, mat=M_FABRIC, **k))
        bx.append(C((cx, yb + .50, cz), (.56, .66, .34), top, mat=M_FABRIC, **k))                 # long skirt
        bx.append(C((cx, yb + 1.40, cz + f * .135), (.24, .05, .01), lt, **k))                    # lace
        bx.append(C((cx, yb + 1.34, cz + f * .132), (.10, .08, .01), skin, **k))                  # neckline
    elif outfit == 'veste_feu':                       # veste de feu : bandes jaune / argent, col montant, poche radio
        yel = (226, 204, 40); sil = (200, 204, 210)
        bx.append(C((cx, yb + 1.06, cz), (.56, .80, .34), top, mat=M_FABRIC, **k))
        bx.append(C((cx, yb + .80, cz), (.565, .06, .345), yel, emis=.18, **k))
        bx.append(C((cx, yb + .755, cz), (.565, .03, .345), sil, emis=.35, **k))
        bx.append(C((cx, yb + 1.18, cz), (.565, .05, .345), yel, emis=.18, **k))
        bx.append(C((cx, yb + 1.145, cz), (.565, .025, .345), sil, emis=.35, **k))
        bx.append(C((cx, yb + 1.46, cz), (.42, .09, .30), _shade(top, .8), **k))                  # high collar
        bx.append(C((cx, yb + 1.00, cz + f * .172), (.03, .58, .01), _shade(top, .6), **k))       # zip flap
        bx.append(C((cx - .15, yb + 1.30, cz + f * .175), (.09, .12, .02), (30, 30, 34), **k))    # radio pocket
        bx.append(C((cx - .15, yb + 1.39, cz + f * .18), (.015, .08, .015), (20, 20, 22), **k))   # antenna
        bx.append(C((cx, yb + 1.0, cz - f * .175), (.38, .07, .01), sil, tex={'-z': _back_tex()}, emis=.3, **k))   # "POMPIERS"
    elif outfit == 'polo':
        bx.append(C((cx, yb + 1.12, cz), (.50, .64, .28), top, mat=M_FABRIC, **k))
        bx.append(C((cx, yb + 1.42, cz + f * .06), (.32, .05, .19), _shade(top, 1.25), **k))
        bx.append(C((cx, yb + 1.33, cz + f * .142), (.05, .14, .01), _shade(top, .75), **k))
        for yy in (1.37, 1.29): bx.append(C((cx, yb + yy, cz + f * .148), (.02, .02, .01), (230, 230, 226), **k))
        bx.append(C((cx - .13, yb + 1.24, cz + f * .144), (.08, .06, .01), (236, 160, 40), **k))  # logo patch
    return bx


@functools.lru_cache(maxsize=1)
def _back_tex():
    im = Image.new('RGBA', (40, 8), (200, 204, 210, 255)); d = ImageDraw.Draw(im)
    mini_text(d, 2, 2, 'POMPIERS', (30, 34, 48, 255)); return np.array(im)


def hair_and_hat(hx, hy, cz, f, hair, style, hat, hat_col, top, k, hair2=None):
    if hat != 'casque_f1': return _ORIG['hair_and_hat'](hx, hy, cz, f, hair, style, hat, hat_col, top, k, hair2=hair2)
    bx = _ORIG['hair_and_hat'](hx, hy, cz, f, hair, style, None, None, top, k, hair2=hair2)[1:2] if style not in ('bald',) else []   # nape hair only
    hm = tuple(hat_col or (196, 198, 204))
    bx.append(C((hx, hy + 1.93, cz), (.47, .12, .46), hm, mat=M_METAL, **k))                    # dome
    bx.append(C((hx, hy + 2.01, cz), (.36, .06, .38), hm, mat=M_METAL, **k))
    bx.append(C((hx, hy + 2.045, cz), (.06, .03, .40), _shade(hm, .8), mat=M_METAL, **k))          # crest
    for s_ in (-1, 1): bx.append(C((hx + s_ * .235, hy + 1.80, cz), (.03, .18, .40), hm, mat=M_METAL, **k))
    bx.append(C((hx, hy + 1.86, cz + f * .23), (.42, .05, .03), _shade(hm, .7), mat=M_METAL, **k))  # brow rim
    bx.append(C((hx, hy + 1.82, cz + f * .245), (.38, .06, .012), (210, 170, 70), refl=.3, cast=False, **k))   # raised gold visor
    bx.append(C((hx, hy + 1.66, cz - f * .23), (.44, .26, .03), (30, 32, 40), mat=M_FABRIC, **k))   # neck flap
    return bx


# ------------------------------------------------------------------ cast presets
_COMMON = dict(headphones=False, backpack=False)
PRESETS = {
    'receptionniste': dict(outfit='gilet', hood=(222, 222, 216), shirt=(34, 38, 52), jeans=(30, 32, 40), hair=(44, 30, 22), hair_style='short', skin=(212, 160, 124), **_COMMON),
    'cliente_agee': dict(outfit='peignoir', hood=(150, 122, 162), jeans=(186, 176, 196), hair=(214, 212, 218), hair_style='bun', glasses=True, skin=(222, 176, 150), face='tired', **_COMMON),
    'client_pyjama': dict(outfit='pyjama', hood=(70, 96, 140), jeans=(70, 96, 140), hair=(70, 52, 36), hair_style='short', beard='stubble', skin=(206, 150, 112), face='tired', **_COMMON),
    'cliente_peignoir': dict(outfit='peignoir', hood=(214, 212, 204), jeans=(210, 156, 120), hair=(96, 60, 36), hair_style='long', skin=(214, 162, 128), face='scared', **_COMMON),
    'client_tshirt': dict(outfit='tshirt', hood=(112, 116, 124), jeans=(46, 48, 58), hair=(30, 26, 24), hair_style='spiky', skin=(170, 120, 88), face='nervous', **_COMMON),
    'cliente_nuisette': dict(outfit='chemise_nuit', hood=(186, 120, 140), jeans=(186, 120, 140), hair=(36, 24, 20), hair_style='ponytail', skin=(176, 122, 92), face='scared', **_COMMON),
    'ado_pyjama': dict(outfit='hoodie', hood=(60, 120, 90), jeans=(90, 70, 110), hair=(120, 84, 50), hair_style='curly', skin=(222, 172, 140), scale=.92, headphones=True, backpack=False, face='tired'),
    'pompier': dict(outfit='veste_feu', hood=(32, 38, 58), jeans=(32, 38, 58), hat='casque_f1', hat_color=(196, 198, 204), hair=(40, 30, 24), skin=(206, 150, 112), **_COMMON),
    'pompier_2': dict(outfit='veste_feu', hood=(32, 38, 58), jeans=(32, 38, 58), hat='casque_f1', hat_color=(196, 198, 204), hair=(20, 18, 18), skin=(150, 100, 72), beard='stubble', **_COMMON),
    'chef_pompier': dict(outfit='veste_feu', hood=(28, 32, 50), jeans=(28, 32, 50), hat='casque_f1', hat_color=(236, 236, 232), hair=(150, 150, 150), skin=(210, 156, 120), beard='mustache', hold='notebook', **_COMMON),
    'technicien': dict(outfit='polo', hood=(40, 78, 120), jeans=(52, 52, 58), hair=(90, 70, 50), hair_style='short', glasses=True, skin=(214, 166, 130), hold='bag', hold_color=(40, 40, 44), **_COMMON),
    'mere_fantome': dict(outfit='chemise_nuit', hood=(196, 204, 214), jeans=(196, 204, 214), hair=(34, 28, 28), hair_style='long', skin=(226, 224, 222), face='neutral', face_fade=.6, **_COMMON),
    'garcon_fantome': dict(outfit='pyjama', hood=(120, 150, 196), jeans=(120, 150, 196), hair=(70, 52, 36), hair_style='short', skin=(230, 214, 204), scale=.62, face='neutral', **_COMMON),
}


def face_for(look, sample, mouth_env=0.):
    """look key `face_fade` (0..1): the features melt into the skin -- a face one can barely make out (the mother). Absent: the original face, the very same array"""
    tex = _ORIG['face_for'](look, sample, mouth_env)
    f = float((look or {}).get('face_fade', 0.) or 0.) if isinstance(look, dict) else 0.
    if f <= 0.: return tex
    sk = np.asarray(look.get('skin', (214, 150, 112)), np.float32)[:3]
    out = np.asarray(tex).astype(np.float32).copy(); out[..., :3] = out[..., :3] * (1. - f) + sk * f
    return out.astype(np.asarray(tex).dtype)


def register():
    """install the outfits, hat, held objects and presets once per process (idempotent)"""
    if _DONE[0]: return
    from . import poses as P, creatures as CR
    _ORIG['torso'] = P.torso; _ORIG['hair_and_hat'] = P.hair_and_hat; _ORIG['held_item'] = P.held_item
    P.torso = torso; P.hair_and_hat = hair_and_hat; P.held_item = held_item
    P.OUTFITS = tuple(P.OUTFITS) + tuple(o for o in NEW_OUTFITS if o not in P.OUTFITS)
    P.HATS = tuple(P.HATS) + tuple(h for h in NEW_HATS if h not in P.HATS)
    P.HOLD_ITEMS = tuple(P.HOLD_ITEMS) + tuple(i for i in NEW_ITEMS if i not in P.HOLD_ITEMS)
    for k_, v in PRESETS.items(): CR.PRESETS.setdefault(k_, dict(v))
    from . import rigfig as RF
    _ORIG['face_for'] = RF.face_for; RF.face_for = face_for
    _DONE[0] = True
