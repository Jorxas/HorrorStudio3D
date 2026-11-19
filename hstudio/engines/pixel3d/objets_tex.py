"""Images des objets détaillés (clé d'épisode `objets`), partagées par les deux versions natives (PS1 : textures des faces ; VOXEL : décalcomanies).

Tout est dessiné ici, en pixels, avec PIL : écrans de téléphone, cadran, clavier, standard, papier imprimé, couverture de livre, page de carnet,
écrans d'ordinateur et de télévision, cadran de radio, cadran d'horloge, étiquettes, photos. Règles :
  * une image est lisible depuis la face où on la pose (faces verticales : telle quelle ; face du dessus lue depuis l'avant -z : `flat()`, retournée
    de haut en bas : mesuré sur le lanceur de rayons, voir tools/check_objets.py) ;
  * aucun hasard non semé, aucune horloge : une image ne dépend que de ses paramètres (lru_cache) ;
  * les textes reçus sont des tuples (hachables) : `lines()` convertit une liste ou une chaîne.
Couleurs RGBA 0-255 ; les tableaux rendus sont des uint8 (H, W, 4)."""
import functools, math, unicodedata, weakref, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ...paths import FONT_PIXEL


@functools.lru_cache(maxsize=32)
def image_locale(path, sha256, width=80, height=144):
    """Explicit local rendered image, content-addressed; never a URL or a network fetch."""
    from pathlib import Path
    p=Path(path)
    if not p.is_file() or p.stat().st_size>8*1024*1024:
        raise ValueError('écran : image locale absente ou supérieure à 8 Mo')
    raw=p.read_bytes()
    if len(str(sha256))!=64 or hashlib.sha256(raw).hexdigest()!=sha256:
        raise ValueError('écran : empreinte de l’image différente de celle validée')
    with Image.open(p) as im:
        if im.width*im.height>16_000_000:raise ValueError('écran : image trop grande')
        return np.asarray(im.convert('RGBA').resize((width,height),Image.Resampling.NEAREST)).copy()

# ------------------------------------------------------------------ fonts
@functools.lru_cache(maxsize=4)
def _font(sz): return ImageFont.truetype(FONT_PIXEL, sz)


_MINI = {
    '0': '111101101101111', '1': '010110010010111', '2': '111001111100111', '3': '111001111001111', '4': '101101111001001',
    '5': '111100111001111', '6': '111100111101111', '7': '111001010010010', '8': '111101111101111', '9': '111101111001111',
    ':': '000010000010000', ' ': '000000000000000', '-': '000000111000000', '.': '000000000000010', '/': '001001010100100',
    'A': '010101111101101', 'B': '110101110101110', 'C': '011100100100011', 'D': '110101101101110', 'E': '111100110100111',
    'F': '111100110100100', 'G': '011100101101011', 'H': '101101111101101', 'I': '111010010010111', 'J': '001001001101010',
    'K': '101101110101101', 'L': '100100100100111', 'M': '101111111101101', 'N': '110101101101101', 'O': '010101101101010',
    'P': '110101110100100', 'Q': '010101101110011', 'R': '110101110101101', 'S': '011100010001110', 'T': '111010010010010',
    'U': '101101101101111', 'V': '101101101101010', 'W': '101101111111101', 'X': '101101010101101', 'Y': '101101010010010',
    'Z': '111001010100111', "'": '010010000000000', '>': '100010001010100', '<': '001010100010001', '!': '010010010000010',
    '(': '010100100100010', ')': '010001001001010', '?': '111001011000010', ',': '000000000010100', '+': '000010111010000',
    '%': '101001010100101', '#': '101111101111101', '@': '111101111100011', '=': '000111000111000', '*': '101010101000000', '&': '010101010101011',
}


def ascii_up(s):
    """majuscules sans accents (la petite police 3x5 n'a que A-Z, chiffres et ponctuation)"""
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode('ascii')
    return s.upper()


def mini(d, x, y, s, col, scale=1):
    """texte en police 3x5 (4 texels par caractère) ; rend la largeur dessinée"""
    cx = x
    for ch in ascii_up(s):
        g = _MINI.get(ch, _MINI[' '])
        for i, v in enumerate(g):
            if v == '1':
                px, py = cx + (i % 3) * scale, y + (i // 3) * scale
                d.rectangle([px, py, px + scale - 1, py + scale - 1], fill=col)
        cx += 4 * scale
    return cx - x


def mini_w(s, scale=1): return max(0, len(ascii_up(s)) * 4 * scale - scale)


def big(d, x, y, s, col, sz=8):
    d.fontmode = '1'; d.text((x, y), str(s), font=_font(sz), fill=col)
    return d.textlength(str(s), font=_font(sz))


def big_w(s, sz=8): return int(ImageDraw.Draw(Image.new('L', (1, 1))).textlength(str(s), font=_font(sz)))


SEG = {'0': 'abcdef', '1': 'bc', '2': 'abged', '3': 'abgcd', '4': 'fgbc', '5': 'afgcd', '6': 'afgedc', '7': 'abc', '8': 'abcdefg', '9': 'abcdfg', '-': 'g', ' ': ''}


def seg7(d, x, y, s, col, dim=None, w=7, h=12, t=2):
    """chiffres à sept segments (réveil, horloge LED, écran d'appel)"""
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


def seg7_w(s, w=7, t=2): return sum((t + 3) if ch == ':' else (w + 3) for ch in s) - 3


def lines(v, default=()):
    """liste / chaîne / None -> tuple de lignes (hachable, pour lru_cache)"""
    if v is None: return tuple(default)
    if isinstance(v, str): return tuple(v.split('\n'))
    return tuple(str(x) for x in v)


def hhmm(v, default='10:10'):
    """'2:13' / '02h13' / [2, 13] / 2.25 -> '02:13'"""
    if v is None: return default
    if isinstance(v, (list, tuple)) and len(v) >= 2: h, m = int(v[0]), int(v[1])
    elif isinstance(v, (int, float)): h = int(v); m = int(round((float(v) - h) * 60))
    else:
        s = str(v).lower().replace('h', ':').replace('.', ':')
        try: h, m = (int(x or 0) for x in (s.split(':') + ['0'])[:2])
        except ValueError: return default
    return f'{h % 24:02d}:{m % 60:02d}'


_FLATS = weakref.WeakValueDictionary()          # les images passées par flat() (tools/check_objets.py vérifie qu'une face du dessus n'en reçoit pas d'autre)


def flat(img):
    """image d'une face du DESSUS, lisible depuis l'avant (-z) : retournée de haut en bas (mesuré : le lanceur de rayons pose la rangée 0 vers -z)"""
    out = np.ascontiguousarray(np.flipud(np.asarray(img)))
    _FLATS[id(out)] = out
    return out


def is_flat(a): return _FLATS.get(id(a)) is a


def _arr(im): return np.array(im.convert('RGBA'))


def _rgba(c, a=255): c = tuple(int(v) for v in c[:3]); return c + (a,)


def _shade(c, k): return tuple(max(0, min(255, int(v * k))) for v in c[:3])


# ------------------------------------------------------------------ phone screens
@functools.lru_cache(maxsize=32)
def phone_screen(mode='verrou', heure='02:13', date='VEN. 31 OCT', nom='INCONNU', texte=(), W=40, H=84):
    """écran de smartphone : `verrou` (heure, date, notification), `appel` (appel entrant, nom, décrocher / raccrocher), `message` (bulles),
    `lignes` (texte libre), `noir` (éteint, reflet). Coins arrondis : texels transparents (la coque se voit)."""
    im = Image.new('RGBA', (W, H), (8, 10, 20, 255)); d = ImageDraw.Draw(im)
    if mode == 'noir':
        im = Image.new('RGBA', (W, H), (6, 7, 10, 255)); d = ImageDraw.Draw(im)
        for i in range(H // 2): d.point((W - 6 - i // 3, 4 + i), fill=(30, 34, 44, 255))          # reflet en biais
    else:
        top, bot = ((18, 22, 52), (52, 20, 60)) if mode != 'appel' else ((14, 40, 34), (10, 16, 26))
        for y in range(H):
            k = y / max(1, H - 1); d.line([(0, y), (W - 1, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)) + (255,))
        d.rectangle([0, 0, W - 1, 5], fill=(4, 5, 10, 255))                                     # barre d'état
        mini(d, 2, 1, heure, (220, 224, 236, 255))
        for i in range(4): d.rectangle([W - 16 + i * 2, 4 - i, W - 15 + i * 2, 4], fill=(220, 224, 236, 255))
        d.rectangle([W - 7, 1, W - 3, 4], outline=(220, 224, 236, 255)); d.point((W - 2, 2), fill=(220, 224, 236, 255))
        if mode == 'verrou':
            sw = seg7_w(heure, 7, 2); seg7(d, (W - sw) // 2, 13, heure, (244, 246, 255, 255), w=7, h=13, t=2)
            mini(d, (W - mini_w(date)) // 2, 31, date, (200, 206, 232, 255))
            d.rectangle([3, 41, W - 4, 58], fill=(46, 50, 78, 255)); d.rectangle([5, 43, 9, 47], fill=(70, 200, 110, 255))
            tl = list(texte) or ['APPEL MANQUE', 'CHAMBRE 313']
            mini(d, 11, 43, tl[0][:7], (250, 250, 250, 255))
            if len(tl) > 1: mini(d, 5, 50, tl[1][:9], (210, 214, 236, 255))
            d.rectangle([W // 2 - 6, H - 5, W // 2 + 6, H - 4], fill=(210, 214, 236, 255))
            d.rectangle([4, H - 13, 8, H - 9], outline=(210, 214, 236, 255)); d.rectangle([W - 9, H - 13, W - 5, H - 9], outline=(210, 214, 236, 255))
        elif mode == 'appel':
            mini(d, (W - mini_w('APPEL')) // 2, 10, 'APPEL', (170, 220, 190, 255))
            d.ellipse([W // 2 - 8, 18, W // 2 + 8, 34], fill=(70, 90, 120, 255)); d.ellipse([W // 2 - 3, 21, W // 2 + 3, 27], fill=(200, 210, 230, 255))
            d.rectangle([W // 2 - 5, 28, W // 2 + 5, 33], fill=(200, 210, 230, 255))
            nm = ascii_up(nom)[:9]; mini(d, (W - mini_w(nm)) // 2, 38, nm, (250, 250, 250, 255))
            tl = list(texte)
            if tl: mini(d, (W - mini_w(tl[0][:9])) // 2, 46, tl[0][:9], (190, 220, 200, 255))
            d.ellipse([5, H - 20, 15, H - 10], fill=(220, 50, 50, 255)); d.ellipse([W - 16, H - 20, W - 6, H - 10], fill=(60, 200, 90, 255))
            d.rectangle([8, H - 16, 12, H - 14], fill=(255, 255, 255, 255)); d.rectangle([W - 13, H - 17, W - 9, H - 13], fill=(255, 255, 255, 255))
        elif mode == 'message':
            d.rectangle([0, 6, W - 1, 15], fill=(16, 18, 30, 255)); d.ellipse([2, 7, 9, 14], fill=(190, 60, 80, 255))
            mini(d, 11, 9, ascii_up(nom)[:7], (240, 240, 244, 255))
            tl = list(texte) or ['TU DORS ?', 'REPONDS', 'JE SUIS', 'DEVANT']
            y = 19
            for i, l in enumerate(tl[:6]):
                w_ = min(W - 8, mini_w(l[:8]) + 4); x0 = 2 if i % 2 == 0 else W - 2 - w_
                d.rectangle([x0, y, x0 + w_, y + 8], fill=(44, 48, 66, 255) if i % 2 == 0 else (40, 100, 220, 255)); mini(d, x0 + 2, y + 2, l[:8], (246, 246, 250, 255)); y += 11
        else:                                                                                   # lignes libres
            y = 9
            for l in (list(texte) or ['...'])[:9]:
                mini(d, 2, y, l[:9], (236, 238, 248, 255)); y += 8
    a = np.array(im)
    for (x, y) in ((0, 0), (1, 0), (0, 1), (W - 1, 0), (W - 2, 0), (W - 1, 1), (0, H - 1), (1, H - 1), (0, H - 2), (W - 1, H - 1), (W - 2, H - 1), (W - 1, H - 2)): a[y, x, 3] = 0
    return a


@functools.lru_cache(maxsize=4)
def phone_back(col=(40, 44, 60), logo=(200, 200, 210), W=40, H=84):
    """dos du smartphone vu de derrière : bloc photo (trois objectifs + flash) en haut à gauche vu de dos, logo au centre"""
    im = Image.new('RGBA', (W, H), _rgba(col)); d = ImageDraw.Draw(im)
    dk = _shade(col, .6); lt = _shade(col, 1.35)
    d.rectangle([W - 18, 3, W - 4, 20], fill=_rgba(dk)); d.rectangle([W - 18, 3, W - 4, 3], fill=_rgba(lt))
    for (x, y) in ((W - 16, 5), (W - 10, 5), (W - 16, 12)):
        d.rectangle([x, y, x + 4, y + 4], fill=(14, 14, 18, 255)); d.point((x + 1, y + 1), fill=(120, 150, 200, 255))
    d.rectangle([W - 9, 13, W - 7, 15], fill=(250, 240, 200, 255))
    d.rectangle([W // 2 - 3, H // 2 - 3, W // 2 + 3, H // 2 + 3], fill=_rgba(logo)); d.rectangle([W // 2 - 1, H // 2 - 5, W // 2 + 1, H // 2 - 4], fill=_rgba(logo))
    return np.array(im)


# ------------------------------------------------------------------ desk phones
@functools.lru_cache(maxsize=4)
def rotary_dial(body=(30, 30, 34), label='313'):
    """cadran rotatif 32x32 : couronne chiffrée, dix trous, pastille centrale avec le numéro du poste, butée"""
    S = 32; im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=_rgba(_shade(body, 1.15)))
    d.ellipse([2, 2, S - 3, S - 3], fill=(226, 220, 204, 255))                                 # couronne crème
    c = (S - 1) / 2.
    for k in range(10):
        a = math.radians(60 + k * 27)                                                           # trous de 1 (en haut à droite) à 0, sens horaire
        x, y = c + math.cos(a) * 10.4, c - math.sin(a) * 10.4
        d.ellipse([x - 2.6, y - 2.6, x + 2.6, y + 2.6], fill=(24, 22, 24, 255))
        dig = str((k + 1) % 10); g = _MINI[dig]
        for i, v in enumerate(g):
            if v == '1': d.point((int(round(x - 1 + i % 3)), int(round(y - 2 + i // 3))), fill=(236, 232, 220, 255))
    d.ellipse([10, 10, S - 11, S - 11], fill=(236, 232, 218, 255)); d.ellipse([10, 10, S - 11, S - 11], outline=(150, 140, 120, 255))
    mini(d, int(c - mini_w(label) / 2) + 1, int(c - 2), label, (150, 30, 30, 255))
    d.line([(S - 6, S - 9), (S - 3, S - 12)], fill=(190, 192, 200, 255), width=2)            # butée
    return np.array(im)


@functools.lru_cache(maxsize=4)
def keypad(rows=4, cols=3, key=(226, 222, 210), ink=(30, 30, 34), base=(40, 38, 40)):
    """clavier téléphonique vu de face : touches claires à chiffres (1-9, *, 0, #)"""
    labels = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#']
    kw, kh, g = 9, 7, 2; W = cols * kw + (cols + 1) * g; H = rows * kh + (rows + 1) * g
    im = Image.new('RGBA', (W, H), _rgba(base)); d = ImageDraw.Draw(im)
    for r in range(rows):
        for c_ in range(cols):
            x = g + c_ * (kw + g); y = g + r * (kh + g)
            d.rectangle([x, y, x + kw - 1, y + kh - 1], fill=_rgba(key)); d.line([(x, y + kh - 1), (x + kw - 1, y + kh - 1)], fill=_rgba(_shade(key, .7)))
            lab = labels[r * cols + c_] if r * cols + c_ < len(labels) else ''
            mini(d, x + 3, y + 1, lab, _rgba(ink))
    return np.array(im)


@functools.lru_cache(maxsize=8)
def lcd(text='02:13', W=36, H=10, fg=(30, 50, 30), bg=(150, 176, 120)):
    im = Image.new('RGBA', (W, H), _rgba(bg)); d = ImageDraw.Draw(im)
    mini(d, max(1, (W - mini_w(text)) // 2), (H - 5) // 2, ascii_up(text)[:W // 4], _rgba(fg))
    return np.array(im)


# ------------------------------------------------------------------ switchboard
@functools.lru_cache(maxsize=16)
def switch_strip(row_label='3', n=13, lit=(), W=None, H=12):
    """bandeau d'une rangée du standard (une contremarche) : numéro d'étage, puis n voyants éteints numérotés ; un voyant allumé est une vraie boîte devant"""
    cell = 7; W = W or (8 + n * cell + 2)
    im = Image.new('RGBA', (W, H), (40, 36, 30, 255)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 6, H - 1], fill=(170, 150, 100, 255)); mini(d, 2, (H - 5) // 2, row_label[:1], (30, 26, 20, 255))
    for i in range(n):
        x = 8 + i * cell; num = f'{i + 1:02d}'
        d.rectangle([x, 1, x + cell - 2, 5], fill=(214, 206, 180, 255)); mini(d, x, 1, num[-1], (40, 36, 30, 255)) if cell < 8 else None
        on = f'{row_label}{num}' in lit
        d.rectangle([x + 1, 7, x + cell - 3, H - 2], fill=(255, 150, 40, 255) if on else (70, 40, 22, 255))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def jack_strip(n=13, W=None, H=8):
    """dessus d'une marche : n jacks (trous cerclés de métal)"""
    cell = 7; W = W or (8 + n * cell + 2)
    im = Image.new('RGBA', (W, H), (36, 34, 32, 255)); d = ImageDraw.Draw(im)
    for i in range(n):
        x = 8 + i * cell + 1
        d.rectangle([x, 2, x + 3, 5], fill=(160, 160, 166, 255)); d.rectangle([x + 1, 3, x + 2, 4], fill=(6, 6, 8, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def plate(text='STANDARD', W=48, H=9, bg=(176, 150, 90), fg=(40, 30, 16)):
    im = Image.new('RGBA', (W, H), _rgba(bg)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, H - 1], outline=_rgba(_shade(bg, .7)))
    mini(d, max(1, (W - mini_w(text)) // 2), (H - 5) // 2, text[:W // 4], _rgba(fg))
    return np.array(im)


# ------------------------------------------------------------------ paper, books, notebooks
@functools.lru_cache(maxsize=16)
def paper(texte=(), titre='', W=168, H=238, entete=True, pli=False, encre=(26, 26, 32), papier=(238, 236, 228), surligne=''):
    """feuille A4 imprimée (police 8 px : ~20 caractères par ligne, ~19 lignes) ; `surligne` : début d'une ligne soulignée au stylo rouge"""
    im = Image.new('RGBA', (W, H), _rgba(papier)); d = ImageDraw.Draw(im); d.fontmode = '1'
    for y in range(0, H, 3): d.line([(0, y), (W - 1, y)], fill=_rgba(_shade(papier, .985)))
    y = 8
    if entete:
        d.rectangle([8, 6, 22, 18], fill=(60, 70, 110, 255)); d.rectangle([11, 9, 19, 15], fill=_rgba(papier))
        mini(d, 26, 7, 'HOTEL DU PARC', (60, 70, 110, 255)); mini(d, 26, 13, '12 RUE DES LILAS', (110, 110, 120, 255)); y = 26
    if titre:
        tw = big_w(ascii_up(titre)[:20]); big(d, max(4, (W - tw) // 2), y, ascii_up(titre)[:20], _rgba(encre)); y += 12
        d.line([(10, y), (W - 11, y)], fill=_rgba(_shade(encre, 2.2))); y += 6
    for l in texte:
        if y > H - 12: break
        if not l: y += 7; continue
        t = ascii_up(l)[:20]; big(d, 8, y, t, _rgba(encre))
        if surligne and t.startswith(ascii_up(surligne)):
            d.line([(6, y + 10), (W - 8, y + 10)], fill=(190, 30, 30, 255), width=2)
        y += 12
    if pli: d.line([(0, H // 3), (W - 1, H // 3)], fill=_rgba(_shade(papier, .86)))
    d.polygon([(W - 14, H - 1), (W - 1, H - 14), (W - 1, H - 1)], fill=_rgba(_shade(papier, .82)))     # coin corné
    d.rectangle([0, 0, W - 1, H - 1], outline=_rgba(_shade(papier, .9)))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def book_cover(titre='LE SILENCE', auteur='M. ARNAUD', col=(120, 30, 36), W=40, H=58):
    im = Image.new('RGBA', (W, H), _rgba(col)); d = ImageDraw.Draw(im)
    lt = _shade(col, 1.5); gold = (220, 186, 90, 255)
    d.rectangle([2, 2, W - 3, H - 3], outline=gold); d.rectangle([4, 4, W - 5, H - 5], outline=_rgba(_shade(col, .75)))
    words = ascii_up(titre).split()[:3]; y = 10
    for w in words:
        w = w[:9]; mini(d, (W - mini_w(w)) // 2, y, w, gold); y += 7
    d.rectangle([W // 2 - 6, y + 4, W // 2 + 6, y + 14], fill=_rgba(lt)); d.rectangle([W // 2 - 3, y + 6, W // 2 + 3, y + 12], fill=_rgba(_shade(col, .6)))
    a = ascii_up(auteur)[:9]; mini(d, (W - mini_w(a)) // 2, H - 11, a, gold)
    return np.array(im)


@functools.lru_cache(maxsize=16)
def book_spine(titre='LE SILENCE', col=(120, 30, 36), W=8, H=58):
    """dos du livre : titre écrit de haut en bas (lu en penchant la tête à droite, comme une vraie tranche)"""
    im = Image.new('RGBA', (H, W), _rgba(col)); d = ImageDraw.Draw(im)
    t = ascii_up(titre)[:13]; mini(d, (H - mini_w(t)) // 2, 2, t, (220, 186, 90, 255))
    d.line([(3, 0), (3, W - 1)], fill=(220, 186, 90, 255)); d.line([(H - 4, 0), (H - 4, W - 1)], fill=(220, 186, 90, 255))
    return np.array(im.rotate(-90, expand=True))


@functools.lru_cache(maxsize=4)
def page_edge(W=40, H=6, horiz=True):
    im = Image.new('RGBA', (W, H), (232, 226, 206, 255)); d = ImageDraw.Draw(im)
    for i in range(0, H if horiz else W, 2):
        if horiz: d.line([(0, i), (W - 1, i)], fill=(206, 198, 176, 255))
        else: d.line([(i, 0), (i, H - 1)], fill=(206, 198, 176, 255))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def open_pages(texte=(), W=96, H=64):
    """deux pages ouvertes vues de dessus (à poser avec flat()) : texte sur deux colonnes, pli au milieu"""
    im = Image.new('RGBA', (W, H), (238, 232, 212, 255)); d = ImageDraw.Draw(im)
    d.rectangle([W // 2 - 1, 0, W // 2, H - 1], fill=(200, 190, 166, 255))
    tl = list(texte) or ['IL ETAIT', 'UNE FOIS', 'UNE PORTE', 'QUI NE', 'S OUVRAIT', 'JAMAIS', 'LA NUIT', 'SAUF A', '2 H 13', 'PRECISES', 'ET CE', 'SOIR LA']
    for col_ in range(2):
        y = 5
        for l in tl[col_ * 7:(col_ + 1) * 7]:
            mini(d, 4 + col_ * (W // 2), y, l[:10], (40, 36, 34, 255)); y += 8
    mini(d, W // 4 - 2, H - 7, '12', (120, 110, 90, 255)); mini(d, 3 * W // 4 - 2, H - 7, '13', (120, 110, 90, 255))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def notebook_page(texte=(), W=40, H=56, encre=(30, 40, 120)):
    """page de carnet à lignes bleues, marge rouge, écriture à la main (petite police penchée d'un texel)"""
    im = Image.new('RGBA', (W, H), (240, 238, 228, 255)); d = ImageDraw.Draw(im)
    for y in range(8, H - 2, 6): d.line([(1, y), (W - 2, y)], fill=(170, 190, 226, 255))
    d.line([(6, 0), (6, H - 1)], fill=(220, 120, 120, 255))
    tl = list(texte) or ['MARDI', '313 ?', 'QUI A', 'APPELE', '2H13']
    y = 3
    for l in tl[:8]:
        mini(d, 8, y, l[:8], _rgba(encre)); y += 6
    return np.array(im)


@functools.lru_cache(maxsize=4)
def notebook_cover(col=(40, 44, 60), W=40, H=56):
    im = Image.new('RGBA', (W, H), _rgba(col)); d = ImageDraw.Draw(im)
    d.rectangle([4, 8, W - 5, 16], fill=(230, 226, 210, 255)); mini(d, 6, 10, 'NOTES', (60, 60, 70, 255))
    return np.array(im)


# ------------------------------------------------------------------ computer / TV / radio screens
@functools.lru_cache(maxsize=16)
def computer_screen(mode='bureau', texte=(), titre='', W=64, H=40, heure='02:13'):
    """écran d'ordinateur : `bureau` (fond, icônes, une fenêtre), `texte` (document), `mail`, `appel` (alerte rouge), `noir`, `lignes`"""
    im = Image.new('RGBA', (W, H), (16, 40, 70, 255)); d = ImageDraw.Draw(im)
    if mode == 'noir':
        im = Image.new('RGBA', (W, H), (6, 8, 10, 255)); d = ImageDraw.Draw(im)
        for i in range(H // 2): d.point((W - 8 - i, 3 + i), fill=(24, 28, 34, 255))
        return np.array(im)
    for y in range(H):
        k = y / H; d.line([(0, y), (W - 1, y)], fill=(int(20 + 30 * k), int(50 + 40 * k), int(90 + 50 * k), 255))
    d.rectangle([0, H - 5, W - 1, H - 1], fill=(20, 22, 30, 255)); d.rectangle([1, H - 4, 4, H - 2], fill=(70, 140, 230, 255)); mini(d, W - 21, H - 5, heure, (220, 224, 236, 255))
    if mode == 'bureau':
        for i in range(4): d.rectangle([2, 2 + i * 7, 6, 6 + i * 7], fill=[(240, 200, 80, 255), (90, 170, 240, 255), (240, 240, 240, 255), (120, 200, 120, 255)][i])
    if mode in ('bureau', 'texte', 'mail', 'lignes', 'appel'):
        x0, y0, x1, y1 = (10, 3, W - 3, H - 7) if mode == 'bureau' else (1, 1, W - 2, H - 6)
        bar = (190, 40, 40) if mode == 'appel' else (60, 90, 160)
        d.rectangle([x0, y0, x1, y1], fill=(236, 236, 232, 255)); d.rectangle([x0, y0, x1, y0 + 5], fill=_rgba(bar))
        d.rectangle([x1 - 4, y0 + 1, x1 - 1, y0 + 4], fill=(230, 80, 70, 255))
        tt = titre or {'bureau': 'NOTES', 'texte': 'RAPPORT', 'mail': 'BOITE', 'lignes': '', 'appel': 'APPEL'}[mode]
        mini(d, x0 + 2, y0 + 1, tt[:(x1 - x0) // 4 - 2], (250, 250, 250, 255))
        tl = list(texte)
        if not tl:
            tl = {'bureau': ['NUIT DU 31', 'RAS', ''], 'texte': ['LE CLIENT', 'DE LA 313', 'N EST PAS', 'REDESCENDU'], 'mail': ['> DIRECTION', '> CH 313', '> URGENT'],
                  'lignes': ['...'], 'appel': ['CH 313', '02:13']}[mode]
        y = y0 + 8
        for l in tl:
            if y > y1 - 5: break
            mini(d, x0 + 2, y, l[:(x1 - x0) // 4 - 1], (30, 30, 40, 255) if mode != 'appel' else (170, 20, 20, 255), 1); y += 6
    return np.array(im)


@functools.lru_cache(maxsize=4)
def keyboard_top(W=60, H=20, key=(60, 62, 70), base=(34, 34, 38)):
    """clavier vu de dessus (à poser avec flat())"""
    im = Image.new('RGBA', (W, H), _rgba(base)); d = ImageDraw.Draw(im)
    for r in range(4):
        n = 14 - (r % 2); off = 1 + (r % 2) * 2
        for i in range(n):
            x = off + i * 4; y = 2 + r * 4
            if x + 3 > W - 1: break
            d.rectangle([x, y, x + 2, y + 2], fill=_rgba(key))
    d.rectangle([14, 18, W - 16, 19], fill=_rgba(key))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def laptop_deck(W=68, H=48, alu=(176, 178, 186)):
    """dessus de l'ordinateur portable (à poser avec flat()) : clavier noir et pavé tactile, vus depuis l'utilisateur"""
    im = Image.new('RGBA', (W, H), _rgba(alu)); d = ImageDraw.Draw(im)
    d.rectangle([4, 3, W - 5, 27], fill=(30, 30, 34, 255))
    for r in range(5):
        for i in range(15):
            x = 5 + i * 4; y = 4 + r * 4 + (1 if r == 4 else 0)
            if x + 3 > W - 5: break
            if r == 4 and 3 < i < 11: continue
            d.rectangle([x, y, x + 2, y + 2], fill=(74, 76, 84, 255))
    d.rectangle([22, 23, W - 23, 26], fill=(74, 76, 84, 255))
    d.rectangle([W // 2 - 12, 31, W // 2 + 12, 44], fill=_rgba(_shade(alu, .9)), outline=_rgba(_shade(alu, .75)))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def tv_screen(mode='neige', texte=(), W=96, H=56, seed=0):
    """écran de télévision : `neige` (parasites semés), `mire` (barres de couleur), `journal` (présentateur + bandeau), `film` (scène bleutée), `noir`, `lignes`"""
    if mode == 'neige':
        rng = np.random.default_rng(7 + seed)
        v = (rng.random((H, W)) * 200 + 30).astype(np.uint8); a = np.stack([v, v, v, np.full_like(v, 255)], -1)
        a[(np.arange(H) % 7 == 3)] = (a[(np.arange(H) % 7 == 3)] * .7).astype(np.uint8)
        return a
    im = Image.new('RGBA', (W, H), (10, 12, 16, 255)); d = ImageDraw.Draw(im)
    if mode == 'mire':
        cols = [(200, 200, 200), (200, 200, 30), (30, 200, 200), (30, 200, 30), (200, 30, 200), (200, 30, 30), (30, 30, 200)]
        bw = W / len(cols)
        for i, c in enumerate(cols): d.rectangle([int(i * bw), 0, int((i + 1) * bw) - 1, int(H * .7)], fill=_rgba(c))
        for i in range(8): d.rectangle([int(i * W / 8), int(H * .72), int((i + 1) * W / 8) - 1, H - 1], fill=_rgba((i * 32,) * 3))
        d.ellipse([W // 2 - 14, H // 2 - 14, W // 2 + 14, H // 2 + 14], outline=(255, 255, 255, 255))
        mini(d, W // 2 - 10, H // 2 - 2, 'MIRE', (255, 255, 255, 255))
    elif mode == 'journal':
        d.rectangle([0, 0, W - 1, H - 1], fill=(30, 50, 90, 255)); d.rectangle([W - 34, 6, W - 6, 26], fill=(70, 100, 150, 255))
        d.rectangle([20, 18, 44, 44], fill=(40, 40, 50, 255)); d.rectangle([25, 8, 39, 22], fill=(210, 160, 130, 255)); d.rectangle([25, 8, 39, 11], fill=(60, 40, 30, 255))
        d.rectangle([0, H - 12, W - 1, H - 1], fill=(190, 30, 30, 255))
        t = ascii_up((list(texte) or ['FLASH : INCENDIE A L HOTEL DU PARC'])[0]); mini(d, 2, H - 9, t[:W // 4], (255, 255, 255, 255))
    elif mode == 'film':
        for y in range(H): d.line([(0, y), (W - 1, y)], fill=(int(20 + 40 * y / H), int(30 + 50 * y / H), int(70 + 60 * y / H), 255))
        d.rectangle([0, int(H * .75), W - 1, H - 1], fill=(14, 18, 26, 255)); d.rectangle([W // 2 + 8, int(H * .35), W // 2 + 14, int(H * .75)], fill=(10, 10, 14, 255))
        d.ellipse([W // 2 + 7, int(H * .25), W // 2 + 15, int(H * .37)], fill=(10, 10, 14, 255)); d.ellipse([12, 6, 22, 16], fill=(230, 230, 210, 255))
    elif mode == 'lignes':
        y = 4
        for l in (list(texte) or ['...'])[:8]:
            mini(d, 4, y, ascii_up(l)[:W // 4 - 1], (230, 236, 240, 255)); y += 7
    else:                                                                              # noir : verre bombé, un reflet
        for i in range(H // 2): d.point((W - 10 - i, 3 + i), fill=(26, 30, 36, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def radio_face(on=True, W=64, H=36, wood=(110, 70, 40)):
    """façade de radio ancienne : toile de haut-parleur tressée, liseré doré, fenêtre de fréquences (lumineuse quand elle marche) et aiguille"""
    im = Image.new('RGBA', (W, H), _rgba(wood)); d = ImageDraw.Draw(im)
    d.rectangle([3, 3, W // 2 - 2, H - 4], fill=(150, 120, 80, 255))
    for x in range(4, W // 2 - 2):
        for y in range(4, H - 4):
            if (x + y) % 3 == 0 or (x - y) % 4 == 0: d.point((x, y), fill=(120, 92, 60, 255))
    d.rectangle([3, 3, W // 2 - 2, H - 4], outline=(214, 180, 90, 255))
    win = (230, 200, 120) if on else (120, 110, 90)
    d.rectangle([W // 2 + 2, 4, W - 4, 16], fill=_rgba(win), outline=(214, 180, 90, 255))
    for i in range(7): d.line([(W // 2 + 4 + i * 4, 6), (W // 2 + 4 + i * 4, 8)], fill=(60, 40, 20, 255))
    mini(d, W // 2 + 4, 10, '88  108', (60, 40, 20, 255)); d.line([(W // 2 + 15, 5), (W // 2 + 15, 15)], fill=(200, 30, 20, 255))
    return np.array(im)


# ------------------------------------------------------------------ clocks
@functools.lru_cache(maxsize=32)
def clock_face(heure='10:10', S=32, rim=(46, 42, 40), face=(236, 232, 218), ink=(30, 28, 26), rouge=True):
    """cadran rond vu de face (coins transparents) : douze graduations, aiguilles des heures et des minutes, trotteuse rouge"""
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=_rgba(rim)); d.ellipse([2, 2, S - 3, S - 3], fill=_rgba(face))
    c = (S - 1) / 2.
    for k in range(12):
        a = k * math.pi / 6; r0, r1 = (S / 2 - 5, S / 2 - 3) if k % 3 else (S / 2 - 7, S / 2 - 3)
        d.line([(c + math.sin(a) * r0, c - math.cos(a) * r0), (c + math.sin(a) * r1, c - math.cos(a) * r1)], fill=_rgba(ink), width=1 if k % 3 else 2)
    h, m = (int(x) for x in hhmm(heure).split(':'))
    ah = ((h % 12) + m / 60.) * math.pi / 6; am = m * math.pi / 30
    d.line([(c, c), (c + math.sin(ah) * S * .24, c - math.cos(ah) * S * .24)], fill=_rgba(ink), width=2)
    d.line([(c, c), (c + math.sin(am) * S * .36, c - math.cos(am) * S * .36)], fill=_rgba(ink), width=1)
    if rouge: d.line([(c, c), (c + math.sin(am + 2.2) * S * .38, c - math.cos(am + 2.2) * S * .38)], fill=(200, 30, 30, 255), width=1)
    d.rectangle([c - 1, c - 1, c + 1, c + 1], fill=_rgba(ink))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def led_clock(heure='02:13', on=True, W=40, H=16, col=(255, 60, 40)):
    im = Image.new('RGBA', (W, H), (12, 8, 8, 255)); d = ImageDraw.Draw(im)
    t = hhmm(heure); sw = seg7_w(t, 7, 2)
    seg7(d, (W - sw) // 2, 2, t, _rgba(col) if on else (40, 14, 12, 255), dim=(34, 14, 12, 255), w=7, h=12, t=2)
    return np.array(im)


# ------------------------------------------------------------------ labels, photos, tags
@functools.lru_cache(maxsize=32)
def label(texte='CHATEAU', sous='1998', bg=(236, 226, 200), fg=(90, 20, 30), W=30, H=20, cadre=True):
    im = Image.new('RGBA', (W, H), _rgba(bg)); d = ImageDraw.Draw(im)
    if cadre: d.rectangle([1, 1, W - 2, H - 2], outline=_rgba(fg))
    t = ascii_up(texte)[:W // 4]; mini(d, max(1, (W - mini_w(t)) // 2), 4 if sous else (H - 5) // 2, t, _rgba(fg))
    if sous:
        s = ascii_up(sous)[:W // 4]; mini(d, max(1, (W - mini_w(s)) // 2), H - 9, s, _rgba(_shade(fg, 1.4)))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def mug_print(texte='', motif='coeur', col=(236, 232, 222), ink=(200, 40, 60), W=24, H=20):
    im = Image.new('RGBA', (W, H), _rgba(col)); d = ImageDraw.Draw(im)
    if texte:
        words = ascii_up(texte).split()[:2]; y = 3 if len(words) > 1 else 7
        for w in words: w = w[:5]; mini(d, (W - mini_w(w)) // 2, y, w, _rgba(ink)); y += 7
    elif motif == 'coeur':
        for (x, y) in ((8, 6), (9, 6), (14, 6), (15, 6)): pass
        d.polygon([(12, 16), (5, 9), (5, 6), (8, 4), (12, 7), (16, 4), (19, 6), (19, 9)], fill=_rgba(ink))
    elif motif == 'rayures':
        for y in range(2, H, 4): d.rectangle([0, y, W - 1, y + 1], fill=_rgba(ink))
    return np.array(im)


@functools.lru_cache(maxsize=16)
def photo(sujet='portrait', seed=0, W=24, H=30, raye=False):
    """photo dans un cadre : `portrait`, `couple`, `famille`, `enfant`, `paysage`, `maison` ; `raye` : visage barré (horreur)"""
    rng = np.random.default_rng(31 + seed)
    im = Image.new('RGBA', (W, H), (150, 160, 170, 255)); d = ImageDraw.Draw(im)
    if sujet == 'paysage' or sujet == 'maison':
        for y in range(H): d.line([(0, y), (W - 1, y)], fill=(int(120 + 80 * y / H), int(150 + 60 * y / H), int(200 - 40 * y / H), 255))
        d.polygon([(0, H * .65), (W * .35, H * .35), (W * .7, H * .62), (W - 1, H * .5), (W - 1, H - 1), (0, H - 1)], fill=(80, 110, 80, 255))
        if sujet == 'maison':
            d.rectangle([W * .3, H * .55, W * .7, H * .85], fill=(220, 210, 190, 255)); d.polygon([(W * .26, H * .56), (W * .5, H * .38), (W * .74, H * .56)], fill=(160, 60, 50, 255))
            d.rectangle([W * .45, H * .7, W * .55, H * .85], fill=(80, 50, 40, 255))
        return np.array(im)
    bg = [(150, 168, 186), (186, 168, 140), (140, 160, 140)][seed % 3]
    d.rectangle([0, 0, W - 1, H - 1], fill=_rgba(bg))
    people = {'portrait': [(.5, 1.0)], 'enfant': [(.5, .78)], 'couple': [(.33, 1.0), (.67, .92)], 'famille': [(.22, 1.0), (.78, .95), (.5, .7)]}.get(sujet, [(.5, 1.0)])
    skins = [(222, 176, 140), (196, 140, 104), (232, 190, 160)]; hairs = [(50, 36, 28), (180, 140, 70), (30, 26, 24), (120, 70, 40)]
    for i, (px, sc) in enumerate(people):
        cx = W * px; hw = W * .13 * sc * (1.25 if len(people) == 1 else 1); top = H * (1 - .78 * sc)
        sk = skins[int(rng.integers(0, 3))]; hr = hairs[int(rng.integers(0, 4))]; sh = tuple(int(v) for v in rng.integers(40, 200, 3))
        d.rectangle([cx - hw * 1.5, top + hw * 2.3, cx + hw * 1.5, H - 1], fill=_rgba(sh))
        d.rectangle([cx - hw, top, cx + hw, top + hw * 2.2], fill=_rgba(sk)); d.rectangle([cx - hw, top - 1, cx + hw, top + hw * .5], fill=_rgba(hr))
        ey = top + hw * 1.0
        d.point((int(cx - hw * .45), int(ey)), fill=(30, 26, 26, 255)); d.point((int(cx + hw * .45), int(ey)), fill=(30, 26, 26, 255))
        d.line([(int(cx - hw * .35), int(ey + hw * .7)), (int(cx + hw * .35), int(ey + hw * .7))], fill=(150, 70, 70, 255))
        if raye and i == 0:
            d.line([(cx - hw - 1, top), (cx + hw + 1, top + hw * 2.2)], fill=(20, 16, 16, 255), width=2); d.line([(cx + hw + 1, top), (cx - hw - 1, top + hw * 2.2)], fill=(20, 16, 16, 255), width=2)
    return np.array(im)


@functools.lru_cache(maxsize=16)
def tag(texte='313', W=16, H=10, bg=(200, 60, 40), fg=(255, 240, 220)):
    im = Image.new('RGBA', (W, H), _rgba(bg)); d = ImageDraw.Draw(im)
    t = ascii_up(texte)[:W // 4]; mini(d, max(1, (W - mini_w(t)) // 2), (H - 5) // 2, t, _rgba(fg))
    d.point((1, 1), fill=(30, 30, 30, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def grille(W=16, H=16, col=(40, 40, 44)):
    """trous d'un haut-parleur / d'un micro de combiné"""
    im = Image.new('RGBA', (W, H), _rgba(col)); d = ImageDraw.Draw(im)
    for y in range(1, H, 3):
        for x in range(1 + (y // 3) % 2, W, 3): d.point((x, y), fill=(8, 8, 10, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def knurl(W=8, H=16, col=(40, 40, 44)):
    im = Image.new('RGBA', (W, H), _rgba(col)); d = ImageDraw.Draw(im)
    for y in range(0, H, 2): d.line([(0, y), (W - 1, y)], fill=_rgba(_shade(col, .6)))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def ribs(W=24, H=36, col=(60, 90, 140)):
    """coque de valise rigide : nervures verticales, ligne de fermeture éclair"""
    im = Image.new('RGBA', (W, H), _rgba(col)); d = ImageDraw.Draw(im)
    for x in range(3, W - 2, 5): d.line([(x, 2), (x, H - 3)], fill=_rgba(_shade(col, 1.25))); d.line([(x + 1, 2), (x + 1, H - 3)], fill=_rgba(_shade(col, .8)))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def stitch(W=24, H=16, col=(120, 60, 40)):
    """cuir piqué : surpiqûre claire sur le bord"""
    im = Image.new('RGBA', (W, H), _rgba(col)); d = ImageDraw.Draw(im)
    lt = _rgba(_shade(col, 1.6))
    for x in range(2, W - 2, 2): d.point((x, 2), fill=lt); d.point((x, H - 3), fill=lt)
    for y in range(2, H - 2, 2): d.point((2, y), fill=lt); d.point((W - 3, y), fill=lt)
    return np.array(im)


@functools.lru_cache(maxsize=4)
def crema(W=12, H=12):
    """surface d'un café vue de dessus : crème claire en spirale sur fond brun"""
    im = Image.new('RGBA', (W, H), (70, 40, 22, 255)); d = ImageDraw.Draw(im)
    d.ellipse([2, 2, W - 3, H - 3], fill=(110, 70, 40, 255)); d.ellipse([4, 4, W - 5, H - 5], fill=(86, 52, 30, 255)); d.point((W // 2 + 1, H // 2 - 2), fill=(150, 110, 70, 255))
    return np.array(im)


@functools.lru_cache(maxsize=4)
def plate_top(S=32, col=(240, 238, 232), bord=(60, 90, 160)):
    """assiette vue de dessus : filet bleu sur l'aile, fond légèrement creusé ; coins transparents (la boîte en croix fait le reste du rond)"""
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=_rgba(col)); d.ellipse([2, 2, S - 3, S - 3], outline=_rgba(bord))
    d.ellipse([7, 7, S - 8, S - 8], fill=_rgba(_shade(col, .95)), outline=_rgba(_shade(col, .85)))
    return np.array(im)
