"""PIXEL 3D assets: 24x24 faces, blocky characters, in-world textures (signs, phone UI, mirror writing, cracks)."""
import math, functools, numpy as np
from PIL import Image, ImageDraw, ImageFont
from .r3d import B, C, Box, M_FABRIC, M_WOODV, M_PLASTER, M_METAL, M_CEIL, M_DOOR, M_CARD
from ...paths import FONT_PIXEL as FONT
from . import poses as P
SKIN = (214, 150, 112); HOOD = (70, 76, 86); JEANS = (34, 40, 58); HAIR = (26, 22, 26)

# ---------------- faces (24x24) ----------------
LEGACY_FACES = ('neutral', 'urgent', 'talk', 'happy', 'double', 'grin', 'scared', 'closed', 'sad', 'smile_sad', 'creature')
NEW_FACES = ('joy', 'laugh', 'excited', 'love', 'wink', 'silly', 'smirk', 'proud', 'shy', 'calm', 'surprised', 'shocked', 'nervous',
             'crying', 'angry', 'furious', 'disgusted', 'confused', 'suspicious', 'thinking', 'bored', 'tired', 'sleeping',
             'determined', 'evil', 'cool', 'pain', 'dizzy', 'ko', 'skull', 'robot', 'alien', 'predator', 'predator_smile', 'fixed_smile')
FACE_KINDS = LEGACY_FACES + NEW_FACES          # 'blank' (visage sans traits) est aussi accepté par face_tex, réservé aux archétypes PS1 (ps1_elements.py), hors liste du directeur
GAZE = {None: (0, 0), 'center': (0, 0), 'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1),
        'up_left': (-1, -1), 'up_right': (1, -1), 'down_left': (-1, 1), 'down_right': (1, 1)}

@functools.lru_cache(maxsize=1024)
def face_tex(kind='neutral', mouth=0, smile=0, crack=0, skin=SKIN, hair=HAIR, tilt=0, gaze=None, glasses=None, beard=None, bald=False, blink=False, eye=None):
    im = Image.new('RGBA', (24, 24), skin + (255,)); d = ImageDraw.Draw(im)
    if not bald:
        d.rectangle([0, 0, 23, 4], fill=hair)
        for x, h in ((0, 9), (3, 7), (6, 8), (9, 6), (12, 8), (15, 6), (18, 8), (21, 9)): d.rectangle([x, 4, x + 2, h], fill=hair)
        d.rectangle([0, 0, 1, 23], fill=hair); d.rectangle([22, 0, 23, 23], fill=hair)
    else:
        d.point([(16, 2), (17, 2), (17, 3)], fill=tuple(min(255, c + 40) for c in skin))       # shine
    red = (232, 30, 40); white = (236, 232, 222); dark = (18, 14, 18); lip = (110, 50, 50)
    ey = 11; my = 17; gx, gy = GAZE.get(gaze, (0, 0))
    # eye aim (engines/pixel3d/eyes.py, opt-in): the pupils carry what the neck could not, in texels, instead
    # of the nine coarse labels of GAZE. `eye=None` -- the default and every delivered render -- changes nothing.
    if eye is not None: gx, gy = int(eye[0]), int(eye[1])
    if beard in (True, 'full', 'beard'):
        d.rectangle([3, 16, 20, 23], fill=hair); d.rectangle([2, 13, 4, 16], fill=hair); d.rectangle([19, 13, 21, 16], fill=hair)
        d.rectangle([8, my - 1, 15, my + 1], fill=skin)
    elif beard == 'mustache': d.rectangle([7, 15, 16, 16], fill=hair)
    elif beard == 'stubble':
        for p in ((5, 18), (8, 20), (11, 21), (14, 20), (17, 18), (6, 21), (16, 21), (10, 19), (13, 19)): d.point(p, fill=tuple(int(c * .7) for c in skin))
    if kind == 'blank': pass                  # visage sans traits (grand homme maigre, spectre, épouvantail) : la peau seule
    elif kind == 'fixed_smile':
        # Unnaturally wide, held smile with tiny BLACK eyes; no glowing pupils or happy cheeks.
        for x in (7, 16): d.rectangle([x, ey, x + 1, ey + 1], fill=dark)
        d.line([(3, 16), (5, 18), (18, 18), (20, 16)], fill=(71, 38, 41), width=2)
        d.polygon([(4, 16), (7, 17), (16, 17), (19, 16), (17, 20), (6, 20)], fill=white)
        for x in (7, 10, 13, 16): d.line([(x, 18), (x, 19)], fill=(158, 146, 135))
    elif kind in LEGACY_FACES:
        _legacy_face(d, kind, mouth, smile, gx, gy, ey, my, red, white, dark, lip)
    else:
        _new_face(d, kind, mouth, gx, gy, ey, my, white, dark, lip, skin)
    if blink:                                  # eyelids closed for a few frames (acting layer)
        d.rectangle([3, ey - 1, 20, ey + 3], fill=skin)
        d.rectangle([4, ey + 1, 9, ey + 1], fill=dark); d.rectangle([14, ey + 1, 19, ey + 1], fill=dark)
    if glasses in (True, 'glasses', 'round'):
        fr = (40, 38, 48)
        for x in (6, 15): d.rectangle([x - 2, ey - 2, x + 4, ey + 4], outline=fr)
        d.rectangle([11, ey, 12, ey], fill=fr)
    elif glasses in ('sun', 'sunglasses'):
        for x in (6, 15): d.rectangle([x - 2, ey - 1, x + 4, ey + 3], fill=(12, 12, 16))
        d.rectangle([11, ey, 12, ey], fill=(12, 12, 16)); d.point([(5, ey), (14, ey)], fill=(200, 210, 230))
    a = np.array(im)
    if crack:
        rng = np.random.default_rng(11); k = int(crack * 110)
        x, y = 12, 9
        for i in range(k):
            a[y, x] = (52, 8, 12, 255) if i % 5 else (226, 220, 214, 255)
            x = int(np.clip(x + rng.integers(-1, 2), 0, 23)); y = int(np.clip(y + rng.integers(-1, 2), 0, 23))
            if i % 16 == 15: x, y = rng.integers(2, 22), rng.integers(2, 22)
    if tilt:                                   # pixel-art friendly head tilt: shear rows instead of rotating
        sh_ = math.tan(math.radians(tilt)); b_ = a.copy()
        for yy in range(24):
            dx = int(round(sh_ * (yy - 12) * .5)); b_[yy] = np.roll(a[yy], dx, axis=0)
            if dx > 0: b_[yy, :dx] = skin + (255,)
            elif dx < 0: b_[yy, dx:] = skin + (255,)
        a = b_
    return a

def _legacy_face(d, kind, mouth, smile, gx, gy, ey, my, red, white, dark, lip):
    """the original expressions, pixel for pixel (only the pupils of the plain eyes follow the gaze)"""
    ey = 11
    if kind in ('neutral', 'urgent', 'talk', 'happy'):
        for x in (6, 15): d.rectangle([x + gx, ey + gy, x + 2 + gx, ey + 2 + gy], fill=dark)
        if kind == 'happy':                                       # rosy cheeks
            for x in (3, 18): d.rectangle([x, ey + 4, x + 2, ey + 5], fill=(214, 128, 112))
    elif kind in ('double', 'grin'):
        for x in (6, 15): d.rectangle([x - 1, ey - 1, x + 3, ey + 3], fill=dark); d.rectangle([x, ey, x + 2, ey + 2], fill=red)
    elif kind == 'scared':
        for x in (5, 15): d.rectangle([x, ey - 1, x + 3, ey + 3], fill=white); d.rectangle([x + 1, ey, x + 2, ey + 2], fill=dark)
        d.rectangle([5, ey - 3, 8, ey - 3], fill=dark); d.rectangle([15, ey - 3, 18, ey - 3], fill=dark)
    elif kind in ('closed', 'sad', 'smile_sad'):
        for x in (5, 15): d.rectangle([x, ey + 1, x + 3, ey + 1], fill=dark)
        if kind in ('sad', 'smile_sad'):
            d.rectangle([4, ey - 2, 7, ey - 2], fill=dark); d.rectangle([16, ey - 2, 19, ey - 2], fill=dark)
            d.rectangle([5, ey + 4, 5, ey + 6], fill=(120, 170, 230)); d.rectangle([19, ey + 4, 19, ey + 6], fill=(120, 170, 230))
    elif kind == 'creature':
        for x in (5, 15): d.rectangle([x - 1, ey - 1, x + 4, ey + 3], fill=dark); d.rectangle([x + 1, ey, x + 2, ey + 1], fill=red)
        d.rectangle([4, ey + 3, 4, ey + 6], fill=(90, 10, 14)); d.rectangle([19, ey + 3, 19, ey + 5], fill=(90, 10, 14))
    if kind in ('double', 'neutral', 'happy') and mouth > 0:
        h = max(1, int(mouth * 4)); d.rectangle([8, my, 15, my + h], fill=(70, 25, 35))
        if h > 1: d.rectangle([9, my, 14, my], fill=white)
    elif kind in ('neutral', 'closed', 'double'):
        d.rectangle([8, my, 15, my], fill=lip)
    elif kind == 'happy':                                         # smile, corners up
        d.rectangle([8, my + 1, 15, my + 1], fill=lip); d.point([(7, my), (16, my)], fill=lip)
    elif kind == 'urgent':
        d.rectangle([8, my - 1, 15, my + 2], fill=(90, 30, 40)); d.rectangle([9, my - 1, 14, my - 1], fill=white)
    elif kind == 'sad':
        d.rectangle([9, my + 1, 14, my + 1], fill=lip); d.point([(8, my + 2), (15, my + 2)], fill=lip)
    elif kind == 'smile_sad':
        d.rectangle([9, my + 1, 14, my + 1], fill=lip); d.point([(8, my), (15, my)], fill=lip)
    elif kind == 'scared':
        d.rectangle([9, my, 14, my + 3], fill=(60, 20, 30)); d.rectangle([10, my, 13, my], fill=white)
    elif kind in ('grin', 'creature'):
        w = 5 if kind == 'grin' else 3 + int(smile * 9)
        x0 = max(0, 12 - w); x1 = min(23, 11 + w); hh = 3 + int(mouth * 3)
        d.rectangle([x0, my - 1, x1, my + hh], fill=(150, 14, 20)); d.rectangle([x0, my - 1, x1, my - 1], fill=white)
        d.rectangle([x0, my + hh, x1, my + hh], fill=white)
        for x in range(x0 + 1, x1, 2): d.rectangle([x, my - 1, x, my + hh], fill=(150, 14, 20))
        d.rectangle([x0 + 1, my, x1 - 1, my + hh - 1], fill=(60, 4, 8))
        for x in range(x0, x1 + 1, 2): d.point([(x, my), (x, my + hh - 1)], fill=white)

def _new_face(d, kind, mouth, gx, gy, ey, my, white, dark, lip, skin):
    inside = (70, 25, 35); blush = (226, 120, 110); tear = (120, 170, 230)
    def dots(dx=0, dy=0):
        for x in (6, 15): d.rectangle([x + dx, ey + dy, x + 2 + dx, ey + 2 + dy], fill=dark)
    def big(px=2, sparkle=False):
        for x in (6, 15):
            d.rectangle([x - 1, ey - 1, x + 3, ey + 3], fill=white)
            if px == 2: d.rectangle([x + 1 + gx, ey + 1 + gy, x + 2 + gx, ey + 2 + gy], fill=dark)
            else: d.point((x + 1 + gx, ey + 1 + gy), fill=dark)
            if sparkle: d.point((x, ey), fill=(255, 255, 255))
    def arcs():                      # closed happy eyes ^ ^
        for x in (5, 15): d.point([(x, ey + 1), (x + 1, ey), (x + 2, ey), (x + 3, ey + 1)], fill=dark)
    def squeeze():                   # > <
        d.point([(5, ey - 1), (6, ey), (7, ey + 1), (6, ey + 2), (5, ey + 3)], fill=dark)
        d.point([(18, ey - 1), (17, ey), (16, ey + 1), (17, ey + 2), (18, ey + 3)], fill=dark)
    def lines(y=ey + 1):
        for x in (5, 15): d.rectangle([x, y, x + 3, y], fill=dark)
    def half(dx=0):                  # heavy lids
        for x in (6, 15):
            d.rectangle([x - 1, ey, x + 3, ey], fill=(70, 40, 40)); d.rectangle([x + dx, ey + 1, x + 2 + dx, ey + 2], fill=dark)
    def brows(kind_):
        L = {'angry': [(5, 9), (6, 9), (7, 10), (8, 10), (9, 10)], 'sad': [(5, 10), (6, 10), (7, 10), (8, 9), (9, 9)],
             'raised': [(5, 8), (6, 7), (7, 7), (8, 7), (9, 8)], 'flat': [(5, 9), (6, 9), (7, 9), (8, 9), (9, 9)],
             'low': [(5, 10), (6, 10), (7, 10), (8, 10), (9, 10)]}
        for side, k_ in ((0, kind_[0]), (1, kind_[1])):
            for x, y in L[k_]: d.point((23 - x if side else x, y), fill=dark)
    def cheeks(c=blush): d.rectangle([3, ey + 4, 5, ey + 5], fill=c); d.rectangle([18, ey + 4, 20, ey + 5], fill=c)
    def m_line(x0=8, x1=15): d.rectangle([x0, my, x1, my], fill=lip)
    def m_smile(w=0): d.rectangle([8 - w, my + 1, 15 + w, my + 1], fill=lip); d.point([(7 - w, my), (16 + w, my)], fill=lip)
    def m_frown(): d.rectangle([9, my, 14, my], fill=lip); d.point([(8, my + 1), (15, my + 1)], fill=lip)
    def m_open(h=3, teeth=True, tongue=False):
        d.rectangle([8, my, 15, my + h - 1], fill=inside); d.rectangle([9, my + h, 14, my + h], fill=inside)
        if teeth: d.rectangle([8, my, 15, my], fill=white)
        if tongue: d.rectangle([11, my + h - 1, 12, my + h], fill=(206, 96, 110))
    def m_o(big_=False):
        if big_: d.rectangle([9, my - 1, 14, my + 4], fill=inside); d.point([(9, my - 1), (14, my - 1), (9, my + 4), (14, my + 4)], fill=skin)
        else: d.rectangle([10, my - 1, 13, my + 3], fill=inside); d.point([(10, my - 1), (13, my - 1), (10, my + 3), (13, my + 3)], fill=skin)
    def m_teeth():
        d.rectangle([7, my - 1, 16, my + 3], fill=dark); d.rectangle([8, my, 15, my + 2], fill=white)
        for x in (10, 13): d.line([(x, my), (x, my + 2)], fill=(150, 140, 130))
    def m_wavy(): d.point([(8, my + 1), (9, my), (10, my), (11, my + 1), (12, my + 1), (13, my), (14, my), (15, my + 1)], fill=lip)
    def m_smirk(): d.rectangle([9, my + 1, 13, my + 1], fill=lip); d.point([(14, my), (15, my - 1)], fill=lip)
    def heart(cx, cy, c=(232, 40, 80)):
        for x, y in ((-2, -1), (-1, -1), (1, -1), (2, -1), (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (-1, 1), (0, 1), (1, 1), (0, 2)):
            d.point((cx + x, cy + y), fill=c)
    talking = mouth > 0
    def talk_or(fn, *a):
        if talking: h = max(1, int(mouth * 4)); d.rectangle([8, my, 15, my + h], fill=inside); (h > 1) and d.rectangle([9, my, 14, my], fill=white)
        else: fn(*a)
    k = kind
    if k in ('joy', 'laugh'): arcs(); cheeks(); m_open(3 + int(mouth * 2), tongue=True)
    elif k == 'excited': big(2, True); brows(('raised', 'raised')); m_open(3 + int(mouth * 2))
    elif k == 'love': heart(7, ey + 1); heart(16, ey + 1); cheeks(); talk_or(m_smile, 1)
    elif k == 'wink': d.rectangle([6 + gx, ey + gy, 8 + gx, ey + 2 + gy], fill=dark); d.point([(15, ey + 1), (16, ey), (17, ey), (18, ey + 1)], fill=dark); talk_or(m_smile, 0)
    elif k == 'silly': d.rectangle([6, ey, 8, ey + 2], fill=dark); d.point([(15, ey + 1), (16, ey), (17, ey), (18, ey + 1)], fill=dark); m_smile(0); d.rectangle([11, my + 2, 13, my + 4], fill=(206, 96, 110))
    elif k == 'smirk': half(gx); brows(('flat', 'raised')); talk_or(m_smirk)
    elif k == 'proud': arcs(); brows(('raised', 'raised')); talk_or(m_smile, 1)
    elif k == 'shy': dots(gx, 1); cheeks((236, 110, 110)); d.rectangle([4, ey + 4, 6, ey + 5], fill=(236, 110, 110)); talk_or(m_line, 10, 13)
    elif k == 'calm': lines(); talk_or(m_smile, 0)
    elif k == 'surprised': big(2); brows(('raised', 'raised')); m_o(mouth > .3)
    elif k == 'shocked': big(1); brows(('raised', 'raised')); m_o(True); d.point([(20, 10), (19, 11), (20, 11), (20, 12)], fill=tear)
    elif k == 'nervous': dots(gx, gy); brows(('sad', 'sad')); d.point([(20, 9), (19, 10), (20, 10), (21, 10), (20, 11)], fill=tear); talk_or(m_wavy)
    elif k == 'crying':
        brows(('sad', 'sad')); squeeze() if mouth > .5 else lines(ey + 1)
        for x in (6, 16): d.rectangle([x, ey + 2, x + 1, ey + 9], fill=tear)
        m_open(2 + int(mouth * 2), teeth=False)
    elif k == 'angry': dots(gx, gy); brows(('angry', 'angry')); talk_or(m_frown)
    elif k == 'furious': dots(gx, gy); brows(('angry', 'angry')); cheeks((214, 60, 50)); m_teeth()
    elif k == 'disgusted': half(gx); brows(('angry', 'flat')); d.point([(11, 15), (12, 15)], fill=(150, 90, 80)); talk_or(m_wavy)
    elif k == 'confused': dots(1 if not gx else gx, -1 if not gy else gy); brows(('flat', 'raised')); talk_or(m_wavy)
    elif k == 'suspicious': half(gx or 1); brows(('low', 'low')); talk_or(m_line, 10, 15)
    elif k == 'thinking': dots(gx or -1, gy or -1); brows(('flat', 'raised')); talk_or(m_line, 12, 16)
    elif k == 'bored': half(gx); talk_or(m_line, 9, 14)
    elif k == 'tired':
        half(gx); d.rectangle([5, ey + 3, 9, ey + 3], fill=tuple(int(c * .8) for c in skin)); d.rectangle([14, ey + 3, 18, ey + 3], fill=tuple(int(c * .8) for c in skin))
        talk_or(m_o, False)
    elif k == 'sleeping': lines(ey + 1); d.rectangle([11, my, 12, my + 1], fill=inside)
    elif k == 'determined': dots(gx, gy); brows(('angry', 'angry')); talk_or(m_line, 9, 14)
    elif k in ('predator', 'predator_smile'):
        for x in (6,15):
            d.rectangle([x-1,ey-1,x+3,ey+3],fill=(205,181,53))
            d.rectangle([x+1+gx,ey+gy,x+1+gx,ey+2+gy],fill=dark)
        brows(('low','low'))
        if k == 'predator_smile':
            h=3+int(mouth*3)
            d.rectangle([6,my-1,17,my+h],fill=(45,23,28))
            d.rectangle([7,my-1,16,my-1],fill=white)
            d.polygon([(8,my),(10,my),(9,my+3)],fill=white)
            d.polygon([(14,my),(16,my),(15,my+3)],fill=white)
            d.point([(5,my-2),(18,my-2)],fill=lip)
        else:talk_or(m_line)
    elif k == 'evil': half(gx); brows(('angry', 'angry')); talk_or(m_smirk)
    elif k == 'cool': d.rectangle([4, ey - 1, 10, ey + 3], fill=(12, 12, 16)); d.rectangle([13, ey - 1, 19, ey + 3], fill=(12, 12, 16)); d.rectangle([10, ey, 13, ey], fill=(12, 12, 16)); d.point([(5, ey), (14, ey)], fill=(200, 210, 230)); talk_or(m_smirk)
    elif k == 'pain': squeeze(); brows(('sad', 'sad')); m_teeth()
    elif k == 'dizzy':
        for x in (6, 15): d.rectangle([x - 1, ey - 1, x + 3, ey + 3], outline=dark); d.point((x + 1, ey + 1), fill=dark); d.point((x + 3, ey + 1), fill=skin)
        m_wavy()
    elif k == 'ko':
        for x in (5, 15): d.point([(x, ey - 1), (x + 3, ey - 1), (x + 1, ey), (x + 2, ey), (x + 1, ey + 1), (x + 2, ey + 1), (x, ey + 2), (x + 3, ey + 2)], fill=dark)
        m_o(False)
    elif k == 'skull':
        for x in (5, 14): d.rectangle([x, ey - 1, x + 4, ey + 3], fill=dark)
        d.polygon([(11, 15), (12, 15), (12, 16), (11, 16)], fill=dark)
        d.rectangle([7, my, 16, my + 2], fill=dark)
        for x in range(8, 16, 2): d.rectangle([x, my, x, my + 2], fill=white)
    elif k == 'robot':
        for x in (5, 14): d.rectangle([x, ey, x + 4, ey + 2], fill=(60, 230, 255))
        d.rectangle([7, my - 1, 16, my + 2], fill=(50, 54, 60))
        for x in range(8, 16, 2): d.line([(x, my - 1), (x, my + 2)], fill=(120, 126, 136))
        if talking: d.rectangle([8, my, 15, my + 1], fill=(60, 230, 255))
    elif k == 'alien':
        for x0, x1 in ((4, 10), (13, 19)): d.ellipse([x0, ey - 3, x1, ey + 4], fill=(10, 10, 14))
        d.point([(6, ey - 1), (15, ey - 1)], fill=(200, 220, 255)); talk_or(m_line, 10, 13)
    else: dots(gx, gy); talk_or(m_line)

# ---------------- expressive face (opt-in, 48x48) ----------------
# A second, higher resolution face painter. It never replaces `face_tex`: the renderer samples a texture by its own
# shape (r3d scales u,v by tx.shape), so a 48x48 array drops on the same head box. Opt-in through the character look
# (`"face_detail": "hd"`, see rigfig.face_for); without that key nothing changes.
# One expression = one row of parameters (brows, lids, mouth, cheeks) instead of one hand-drawn branch. Kinds that are
# not in the table (stylised masks: skull, robot, alien...) fall back to the 24x24 art, nearest-upscaled.
HD_SIZE = 48
# kind -> (brow_left, brow_right, lid, mouth, cheek)
HD_EXPR = {
    'neutral': ('flat', 'flat', 'open', 'line', None), 'talk': ('flat', 'flat', 'open', 'open', None),
    'urgent': ('raised', 'raised', 'wide', 'teeth', None), 'happy': ('arch', 'arch', 'open', 'smile', 'blush'),
    'double': ('flat', 'flat', 'wide', 'line', None), 'grin': ('low', 'low', 'wide', 'teeth', None),
    'scared': ('raised', 'raised', 'wide', 'open', 'pale'), 'closed': ('flat', 'flat', 'closed', 'line', None),
    'sad': ('sad', 'sad', 'closed', 'frown', None), 'smile_sad': ('sad', 'sad', 'closed', 'smile', None),
    'creature': ('low', 'low', 'wide', 'teeth', None),
    'joy': ('arch', 'arch', 'arc', 'bigsmile', 'blush'), 'laugh': ('arch', 'arch', 'arc', 'tongue', 'blush'),
    'excited': ('raised', 'raised', 'wide', 'open', 'blush'), 'love': ('arch', 'arch', 'heart', 'smile', 'blush'),
    'wink': ('flat', 'raised', 'wink', 'smile', 'blush'), 'silly': ('raised', 'flat', 'wink', 'tongue', 'blush'),
    'smirk': ('flat', 'raised', 'half', 'smirk', None), 'proud': ('raised', 'raised', 'arc', 'smile', None),
    'shy': ('sad', 'sad', 'narrow', 'small', 'hot'), 'calm': ('flat', 'flat', 'closed', 'smile', None),
    'surprised': ('raised', 'raised', 'wide', 'o', None), 'shocked': ('raised', 'raised', 'wide', 'obig', 'pale'),
    'nervous': ('sad', 'sad', 'open', 'wavy', 'pale'), 'crying': ('sad', 'sad', 'squeeze', 'open', 'hot'),
    'angry': ('angry', 'angry', 'narrow', 'frown', None), 'furious': ('angry', 'angry', 'narrow', 'teeth', 'hot'),
    'disgusted': ('angry', 'flat', 'half', 'wavy', None), 'confused': ('flat', 'raised', 'open', 'wavy', None),
    'suspicious': ('low', 'low', 'half', 'line', None), 'thinking': ('flat', 'raised', 'open', 'small', None),
    'bored': ('flat', 'flat', 'half', 'line', None), 'tired': ('low', 'low', 'half', 'o', 'pale'),
    'sleeping': ('flat', 'flat', 'closed', 'o', None), 'determined': ('angry', 'angry', 'narrow', 'line', None),
    'evil': ('angry', 'angry', 'half', 'smirk', None), 'cool': ('flat', 'flat', 'shades', 'smirk', None),
    'pain': ('sad', 'sad', 'squeeze', 'grimace', 'hot'), 'dizzy': ('flat', 'flat', 'spiral', 'wavy', 'pale'),
    'ko': ('flat', 'flat', 'cross', 'o', 'pale'),
}
HD_KINDS = tuple(HD_EXPR)
# brow name -> (x, y) of the three segments, left side, y relative to the eye line (negative = up)
_BROWS = {'flat': ((0, -7), (4, -7), (8, -7)), 'raised': ((0, -9), (4, -11), (8, -10)),
          'arch': ((0, -8), (4, -11), (9, -9)), 'angry': ((0, -10), (4, -8), (8, -6)),
          'sad': ((0, -6), (4, -8), (8, -10)), 'low': ((0, -6), (4, -6), (8, -5))}

def _mix(c, o, t):
    return tuple(int(round(c[i] + (o[i] - c[i]) * t)) for i in range(3))

@functools.lru_cache(maxsize=512)
def face_tex_hd(kind='neutral', mouth=0, crack=0, skin=SKIN, hair=HAIR, tilt=0, gaze=None, glasses=None, beard=None,
                bald=False, blink=False, iris=(96, 62, 44), fringe=True, lips=None, eye=None):
    """48x48 expressive face: eyebrows, iris / pupil / highlight, shaded cheeks and nose, emotional mouth.
    `iris` is the eye colour, `lips` the lip colour (default derived from the skin). Deterministic and cached."""
    if kind not in HD_EXPR:                                  # stylised masks keep their 24x24 art
        a = face_tex(kind, mouth, .8, crack, skin, hair, tilt, gaze, glasses, beard, bald, blink,
                     None if eye is None else (int(eye[0]) // 2, int(eye[1]) // 2))
        return np.repeat(np.repeat(a, 2, 0), 2, 1)
    S = HD_SIZE
    shade = _mix(skin, (40, 24, 30), .30); deep = _mix(skin, (40, 24, 30), .48)
    lit = _mix(skin, (255, 244, 230), .22); lip = tuple(lips) if lips else _mix(skin, (150, 58, 70), .55)
    lip_d = _mix(lip, (40, 14, 22), .40); inside = (74, 26, 36); teeth = (238, 234, 224)
    white = (240, 238, 232); dark = (20, 16, 20)
    bl, br, lid, mo, cheek = HD_EXPR[kind]
    gx, gy = GAZE.get(gaze, (0, 0)); gx *= 2; gy *= 2
    # eye aim (engines/pixel3d/eyes.py, opt-in), in texels of THIS 48x48 face. None = the historical pupils.
    if eye is not None: gx, gy = int(eye[0]), int(eye[1])
    if blink and lid not in ('closed', 'arc', 'squeeze', 'shades', 'cross'): lid = 'closed'
    im = Image.new('RGBA', (S, S), skin + (255,)); d = ImageDraw.Draw(im)
    ey, my, cx = 22, 34, 24
    # --- skin modelling: lit forehead, shaded jaw and temples, nose
    for i, y in enumerate(range(0, 12)): d.rectangle([0, y, S - 1, y], fill=_mix(lit, skin, i / 11.))
    for i, y in enumerate(range(38, S)): d.rectangle([0, y, S - 1, y], fill=_mix(skin, shade, (i + 1) / 12.))
    for x0, x1 in ((0, 2), (S - 3, S - 1)): d.rectangle([x0, 10, x1, 41], fill=shade)
    d.rectangle([25, 26, 25, 30], fill=_mix(skin, shade, .26))                    # nose: a shadow down one side
    d.rectangle([22, 30, 25, 30], fill=_mix(skin, shade, .18))                    # and under the tip
    d.point([(22, 30), (25, 30)], fill=_mix(skin, shade, .46))                    # nostrils
    if cheek == 'blush':
        for x in (5, 32): d.rectangle([x, ey + 7, x + 10, ey + 10], fill=_mix(skin, (236, 120, 118), .55))
    elif cheek == 'hot':
        for x in (4, 31): d.rectangle([x, ey + 6, x + 12, ey + 11], fill=_mix(skin, (238, 96, 96), .75))
    elif cheek == 'pale':
        for x in (4, 31): d.rectangle([x, ey + 6, x + 12, ey + 11], fill=_mix(skin, (190, 196, 212), .45))
    else:
        for x in (3, 37): d.rectangle([x, ey + 6, x + 7, ey + 12], fill=_mix(skin, shade, .13))
    if not bald and fringe:                                  # staged cubic fringe (2 px steps), lighter on top
        hi_ = _mix(hair, (255, 240, 220), .14)
        d.rectangle([0, 0, S - 1, 6], fill=hair); d.rectangle([0, 0, S - 1, 1], fill=hi_)
        for x, h in ((0, 15), (6, 11), (12, 13), (18, 8), (24, 12), (30, 9), (36, 13), (42, 16)):
            d.rectangle([x, 6, x + 5, h], fill=hair)
            d.rectangle([x, 6, x + 5, 7], fill=_mix(hair, hi_, .5))
        d.rectangle([0, 0, 3, S - 1], fill=hair); d.rectangle([S - 4, 0, S - 1, S - 1], fill=hair)
        d.rectangle([0, 0, 1, S - 1], fill=_mix(hair, hi_, .4)); d.rectangle([S - 2, 0, S - 1, S - 1], fill=_mix(hair, (0, 0, 0), .25))
    elif bald:
        d.rectangle([32, 3, 35, 5], fill=lit)
    # --- brows
    for side, nm in ((-1, bl), (1, br)):
        for i, (bxp, byp) in enumerate(_BROWS[nm]):
            x = cx + side * (6 + bxp) - (3 if side < 0 else 0)
            d.rectangle([x, ey + byp, x + 3, ey + byp + 2], fill=_mix(hair, dark, .3))
    # --- eyes
    def socket(x0):
        d.rectangle([x0, ey - 4, x0 + 10, ey + 5], fill=_mix(skin, shade, .45))
    if lid == 'shades':
        for x0 in (5, 26): d.rectangle([x0, ey - 4, x0 + 16, ey + 5], fill=(14, 14, 18))
        d.rectangle([21, ey - 2, 26, ey], fill=(14, 14, 18))
        for x0 in (7, 28): d.rectangle([x0, ey - 3, x0 + 3, ey - 1], fill=(190, 204, 226))
    elif lid in ('closed', 'arc', 'squeeze', 'cross', 'wink'):
        for side, x0 in ((-1, 7), (1, 28)):
            if lid == 'wink' and side < 0:
                _hd_eye(d, x0, ey, 'open', gx, gy, iris, white, dark, skin, shade, deep); continue
            if lid == 'arc':
                d.rectangle([x0 + 1, ey - 1, x0 + 2, ey], fill=dark); d.rectangle([x0 + 3, ey - 2, x0 + 9, ey - 1], fill=dark)
                d.rectangle([x0 + 10, ey - 1, x0 + 11, ey], fill=dark)
            elif lid == 'squeeze':
                for i in range(5): d.rectangle([x0 + 1 + i * 2, ey - 3 + abs(i - 2) * 2, x0 + 2 + i * 2, ey - 1 + abs(i - 2) * 2], fill=dark)
            elif lid == 'cross':
                for i in range(5):
                    d.rectangle([x0 + 1 + i * 2, ey - 3 + i * 2, x0 + 2 + i * 2, ey - 2 + i * 2], fill=dark)
                    d.rectangle([x0 + 9 - i * 2, ey - 3 + i * 2, x0 + 10 - i * 2, ey - 2 + i * 2], fill=dark)
            else:
                lash = _mix(dark, skin, .22)
                d.rectangle([x0 + 1, ey, x0 + 10, ey], fill=lash); d.point([(x0, ey + 1), (x0 + 11, ey + 1)], fill=lash)
                d.rectangle([x0 + 2, ey + 1, x0 + 9, ey + 1], fill=_mix(skin, shade, .55))
    elif lid == 'heart':
        for x0 in (6, 27):
            for dx, dy in ((1, 0), (2, 0), (4, 0), (5, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1),
                           (1, 2), (2, 2), (3, 2), (4, 2), (5, 2), (2, 3), (3, 3), (4, 3), (3, 4)):
                d.rectangle([x0 + dx * 2, ey - 3 + dy * 2, x0 + dx * 2 + 1, ey - 2 + dy * 2], fill=(236, 46, 86))
    elif lid == 'spiral':
        for x0 in (7, 28):
            socket(x0); d.ellipse([x0, ey - 4, x0 + 10, ey + 5], fill=white, outline=dark)
            d.ellipse([x0 + 2, ey - 2, x0 + 8, ey + 3], outline=dark); d.point([(x0 + 5, ey), (x0 + 6, ey)], fill=dark)
    else:
        for x0 in (7, 28):
            socket(x0); _hd_eye(d, x0, ey, lid, gx, gy, iris, white, dark, skin, shade, deep)
    if kind in ('double', 'creature'):                        # red glowing pupils keep their identity
        for x0 in (7, 28): d.rectangle([x0 + 4 + gx, ey - 1 + gy, x0 + 7 + gx, ey + 2 + gy], fill=(232, 30, 40))
    if kind == 'crying':
        for x0 in (9, 31): d.rectangle([x0, ey + 3, x0 + 2, ey + 18], fill=(120, 170, 230))
    elif kind in ('nervous', 'shocked'):
        d.rectangle([39, ey - 4, 41, ey], fill=(120, 170, 230)); d.rectangle([38, ey - 1, 42, ey + 2], fill=(150, 196, 240))
    elif kind == 'tired':
        for x0 in (8, 29): d.rectangle([x0, ey + 6, x0 + 9, ey + 7], fill=deep)
    # --- mouth
    _hd_mouth(d, mo, mouth, my, lip, lip_d, inside, teeth, skin, shade)
    # --- facial hair, glasses (same families as the 24x24 painter)
    if beard in (True, 'full', 'beard'):
        d.rectangle([6, 32, 41, S - 1], fill=hair); d.rectangle([4, 26, 9, 33], fill=hair); d.rectangle([38, 26, 43, 33], fill=hair)
        d.rectangle([16, my - 2, 31, my + 3], fill=skin); _hd_mouth(d, mo, mouth, my, lip, lip_d, inside, teeth, skin, shade)
    elif beard == 'mustache': d.rectangle([14, my - 4, 33, my - 1], fill=hair)
    elif beard == 'stubble':
        for p in ((10, 36), (16, 40), (22, 42), (28, 40), (34, 36), (12, 42), (32, 42), (20, 38), (26, 38)):
            d.rectangle([p[0], p[1], p[0] + 1, p[1] + 1], fill=_mix(skin, hair, .45))
    if glasses in (True, 'glasses', 'round'):
        fr = (42, 40, 50)
        for x0 in (5, 26): d.rectangle([x0, ey - 5, x0 + 15, ey + 6], outline=fr, width=2)
        d.rectangle([21, ey - 1, 26, ey], fill=fr)
    elif glasses in ('sun', 'sunglasses') and lid != 'shades':
        for x0 in (5, 26): d.rectangle([x0, ey - 5, x0 + 15, ey + 6], fill=(12, 12, 16))
        d.rectangle([21, ey - 2, 26, ey], fill=(12, 12, 16))
        for x0 in (7, 28): d.rectangle([x0, ey - 4, x0 + 3, ey - 2], fill=(196, 208, 230))
    a = np.array(im)
    if crack:
        rng = np.random.default_rng(11); x, y = 24, 18
        for i in range(int(crack * 220)):
            a[y, x] = (52, 8, 12, 255) if i % 5 else (226, 220, 214, 255)
            x = int(np.clip(x + rng.integers(-2, 3), 0, S - 1)); y = int(np.clip(y + rng.integers(-2, 3), 0, S - 1))
            if i % 16 == 15: x, y = rng.integers(4, S - 4), rng.integers(4, S - 4)
    if tilt:
        sh_ = math.tan(math.radians(tilt)); b_ = a.copy()
        for yy in range(S):
            dx = int(round(sh_ * (yy - S / 2) * .5)); b_[yy] = np.roll(a[yy], dx, axis=0)
            if dx > 0: b_[yy, :dx] = skin + (255,)
            elif dx < 0: b_[yy, dx:] = skin + (255,)
        a = b_
    return a

def _hd_eye(d, x0, ey, lid, gx, gy, iris, white, dark, skin, shade, deep):
    """one eye: sclera, iris, pupil, highlight, lash line and lid, inside an 11x10 socket at (x0, ey-4)"""
    top = {'wide': -5, 'open': -4, 'narrow': -2, 'half': -1}.get(lid, -4)
    bot = {'wide': 6, 'open': 5, 'narrow': 4, 'half': 4}.get(lid, 5)
    d.ellipse([x0, ey + top, x0 + 11, ey + bot], fill=white)
    d.ellipse([x0 + 1, ey + top + 1, x0 + 10, ey + top + 3], fill=_mix(white, (150, 150, 160), .45))   # lid shadow on the sclera
    ix = x0 + 3 + gx; iy = ey - 2 + gy
    if lid == 'half': iy = max(iy, ey - 1)
    d.ellipse([ix, iy, ix + 5, iy + 5], fill=tuple(iris))
    d.ellipse([ix + 1, iy + 3, ix + 4, iy + 5], fill=_mix(iris, (0, 0, 0), .35))                       # lower iris, deeper
    d.rectangle([ix + 2, iy + 2, ix + 3, iy + 3], fill=dark)                                           # pupil
    d.point([(ix + 1, iy + 1), (ix + 2, iy + 1)], fill=(255, 255, 255))                                # catchlight
    d.point([(ix + 4, iy + 4)], fill=_mix(iris, (255, 255, 255), .55))                                 # bounce light
    d.rectangle([x0, ey + top, x0 + 11, ey + top + 1], fill=dark)                                       # lashes
    d.point([(x0, ey + top + 2), (x0 + 11, ey + top + 2)], fill=dark)
    if lid in ('narrow', 'half'):
        d.rectangle([x0, ey + top - 1, x0 + 11, ey + top], fill=_mix(skin, shade, .6))                 # heavy upper lid
    d.rectangle([x0 + 1, ey + bot, x0 + 10, ey + bot], fill=deep)                                       # lower lid crease

def _hd_mouth(d, mo, mouth, my, lip, lip_d, inside, teeth, skin, shade):
    open_h = int(mouth * 8)
    if mouth > 0 and mo in ('line', 'small', 'smile', 'smirk', 'wavy', 'frown'):
        h = max(2, open_h)
        d.rounded_rectangle([16, my - 1, 31, my + h], 2, fill=inside)
        d.rectangle([17, my - 1, 30, my], fill=teeth)
        d.rectangle([15, my - 2, 32, my - 2], fill=lip_d); d.rectangle([16, my + h + 1, 31, my + h + 1], fill=lip)
        return
    if mo == 'line':
        d.rectangle([17, my, 30, my], fill=lip_d); d.rectangle([18, my + 1, 29, my + 1], fill=lip)
    elif mo == 'small':
        d.rectangle([19, my, 28, my + 1], fill=lip_d); d.rectangle([20, my + 2, 27, my + 2], fill=lip)
    elif mo in ('smile', 'bigsmile'):
        w = 0 if mo == 'smile' else 3
        d.rectangle([16 - w, my + 1, 31 + w, my + 2], fill=lip_d)
        d.rectangle([17 - w, my + 3, 30 + w, my + 3], fill=lip)
        d.rectangle([14 - w, my - 1, 15 - w, my], fill=lip_d); d.rectangle([32 + w, my - 1, 33 + w, my], fill=lip_d)
        if mo == 'bigsmile':
            d.rectangle([14, my + 2, 33, my + 6], fill=inside); d.rectangle([15, my + 2, 32, my + 3], fill=teeth)
            d.rectangle([14, my + 7, 33, my + 8], fill=lip)
    elif mo == 'frown':
        d.rectangle([18, my, 29, my + 1], fill=lip_d); d.rectangle([16, my + 2, 17, my + 3], fill=lip_d)
        d.rectangle([30, my + 2, 31, my + 3], fill=lip_d)
    elif mo in ('open', 'tongue'):
        h = 5 + open_h
        d.rounded_rectangle([15, my - 2, 32, my + h], 3, fill=inside)
        d.rectangle([16, my - 2, 31, my], fill=teeth)
        if mo == 'tongue': d.rounded_rectangle([20, my + h - 4, 27, my + h], 2, fill=(212, 102, 116))
        d.rectangle([14, my - 3, 33, my - 3], fill=lip_d); d.rectangle([15, my + h + 1, 32, my + h + 1], fill=lip)
    elif mo in ('o', 'obig'):
        r = 3 if mo == 'o' else 5
        d.ellipse([24 - r, my - 1, 23 + r, my + r + 1], fill=lip)
        d.ellipse([25 - r, my, 22 + r, my + r], fill=inside)
    elif mo == 'teeth':
        d.rectangle([14, my - 3, 33, my + 6], fill=lip_d); d.rectangle([15, my - 1, 32, my + 4], fill=teeth)
        for x in (20, 26): d.rectangle([x, my - 1, x, my + 4], fill=(168, 160, 152))
        d.rectangle([15, my + 2, 32, my + 2], fill=(188, 182, 174))
    elif mo == 'grimace':
        d.rectangle([15, my - 2, 32, my + 5], fill=inside); d.rectangle([16, my - 1, 31, my + 1], fill=teeth)
        d.rectangle([16, my + 3, 31, my + 4], fill=teeth)
    elif mo == 'wavy':
        for i, x in enumerate(range(15, 33, 3)):
            d.rectangle([x, my + (0 if i % 2 else 2), x + 2, my + (1 if i % 2 else 3)], fill=lip_d)
    elif mo == 'smirk':
        d.rectangle([18, my + 2, 27, my + 3], fill=lip_d); d.rectangle([28, my, 30, my + 1], fill=lip_d)
        d.rectangle([31, my - 2, 32, my - 1], fill=lip)
    else:
        d.rectangle([16, my, 31, my + 1], fill=lip_d)

# ---------------- characters (boxes) ----------------
def figure(x, z, facing=1, face=None, hood=HOOD, jeans=JEANS, hair=HAIR, skin=SKIN, swing=0., armsw=0., hidden=False, dissolve=0., yoff=0., arm_up=0., glow=0., eyes=None, pose=None, noref=False, headx=0., heady=0.,
           headphones=True, backpack=True, hair_long=False, scale=1.0, shirt=None,
           gesture=None, posture=None, hold=None, hold_color=None, g=0., outfit=None, hair_style=None, hat=None, hat_color=None, tie=None,
           lie_head='-x', lights=None, cape=None):
    """blocky character (hoodie, jeans, backpack, headphones). facing=+1 -> face towards +z, -1 -> towards -z; swing in metres.
    gesture / posture / hold / outfit / hair_style / hat: body language and looks (see poses.py). Without them the
    character is built exactly as in the original episodes."""
    if posture == 'lie':
        kw = dict(face=face, hood=hood, jeans=jeans, hair=hair, skin=skin, hidden=hidden, dissolve=dissolve, glow=glow, eyes=eyes, noref=noref,
                  headphones=headphones, backpack=False, hair_long=hair_long, scale=scale, shirt=shirt, gesture=gesture, hold=hold,
                  hold_color=hold_color, g=g, outfit=outfit, hair_style=hair_style, hat=hat, hat_color=hat_color, tie=tie, cape=cape)
        return P.lie(figure(0., 0., 1, **kw), x, z, lie_head, yoff)
    modern = bool(gesture or (posture and posture != 'stand') or hold or (outfit and outfit != 'hoodie') or hair_style or (hat and hat != 'none') or cape)
    if modern: return _figure_modern(x, z, facing, face, hood, jeans, hair, skin, swing, armsw, hidden, dissolve, yoff, glow, eyes, noref, headx, heady,
                                     headphones, backpack, hair_long, scale, shirt, gesture, posture, hold, hold_color, g, outfit, hair_style, hat, hat_color, tie, lights, cape)
    f = facing; k = dict(hidden=hidden, dissolve=dissolve, noref=noref)
    bx = []; face = face if face is not None else face_tex('neutral')
    bx.append(C((x - .11, yoff + .40, z + swing * f), (.18, .80, .21), jeans, mat=M_FABRIC, **k))
    bx.append(C((x + .11, yoff + .40, z - swing * f), (.18, .80, .21), jeans, mat=M_FABRIC, **k))
    bx.append(C((x - .11, yoff + .04, z + swing * f + .03 * f), (.19, .08, .27), (28, 26, 28), **k))   # shoes
    bx.append(C((x + .11, yoff + .04, z - swing * f + .03 * f), (.19, .08, .27), (28, 26, 28), **k))
    bx.append(C((x, yoff + 1.12, z), (.50, .64, .28), hood, mat=M_FABRIC, **k))
    if shirt: bx.append(C((x, yoff + 1.12, z + f * .142), (.2, .5, .01), shirt, **k))
    bx.append(C((x, yoff + 1.0, z + f * .145), (.30, .14, .01), tuple(int(c * .75) for c in hood), **k))         # pocket
    for s in (-1, 1): bx.append(C((x + s * .05, yoff + 1.30, z + f * .145), (.022, .16, .012), (196, 196, 186), **k))   # drawstrings
    bx.append(C((x, yoff + 1.46, z - f * .06), (.44, .10, .22), tuple(int(c * .85) for c in hood), **k))     # hood collar
    for s in (-1, 1):
        az = z + armsw * f * s
        if pose == 'chest' and s == 1:
            bx.append(C((x + .30, yoff + 1.25, z + .02 * f), (.13, .32, .15), hood, mat=M_FABRIC, **k))
            bx.append(C((x + .12, yoff + 1.18, z + .2 * f), (.30, .13, .13), hood, mat=M_FABRIC, **k))
            bx.append(C((x - .02, yoff + 1.20, z + .2 * f), (.12, .12, .1), skin, **k))
        elif pose == 'extend' and s == 1:
            bx.append(C((x + .30, yoff + 1.32, z + .38 * f), (.13, .13, .62), hood, mat=M_FABRIC, **k))
            bx.append(C((x + .30, yoff + 1.32, z + .74 * f), (.13, .12, .14), skin, **k))
            for q in (-1, 0, 1): bx.append(C((x + .30 + q * .04, yoff + 1.32, z + .84 * f), (.025, .02, .08), skin, **k))
        elif arm_up and s == 1:
            bx.append(C((x + s * .32, yoff + 1.45, z + .12 * f), (.13, .56, .15), hood, mat=M_FABRIC, **k))
            bx.append(C((x + s * .32, yoff + 1.78, z + .12 * f), (.12, .12, .14), skin, **k))
        else:
            bx.append(C((x + s * .32, yoff + 1.13, az), (.13, .58, .15), hood, mat=M_FABRIC, **k))
            bx.append(C((x + s * .32, yoff + .79, az), (.12, .11, .14), skin, **k))
    if backpack: bx.append(C((x, yoff + 1.16, z - f * .21), (.38, .48, .15), (36, 40, 44), mat=M_FABRIC, **k))        # backpack
    tex = {'+z': face} if f > 0 else {'-z': face}
    hx = x + headx; hy = yoff + heady
    bx.append(C((hx, hy + 1.68, z), (.40, .40, .38), skin, tex=tex, **k))                           # head
    bx.append(C((hx, hy + 1.90, z - f * .02), (.43, .08, .42), hair, **k))
    bx.append(C((hx, hy + 1.70, z - f * .20), (.42, .38, .06), hair, **k))
    if headphones == 'cou':                           # 9/11/2026 : headphones worn around the neck (opt-in value 'cou')
        bx += [C((hx + s * .19, hy + 1.38, z + f * .03), (.07, .15, .15), (26, 26, 32), **k) for s in (-1, 1)] + [C((hx, hy + 1.35, z - f * .11), (.44, .05, .06), (26, 26, 32), **k)]
    elif headphones:
        for s in (-1, 1):
            bx.append(C((hx + s * .225, hy + 1.68, z), (.06, .16, .16), (26, 26, 32), **k))
            bx.append(C((hx + s * .258, hy + 1.68, z + f * .04), (.02, .035, .035), (80, 255, 130), emis=1.6 if glow == 0 else glow, cast=False, **k))
        bx.append(C((hx, hy + 1.955, z), (.48, .045, .1), (26, 26, 32), **k))
    if hair_long:
        bx.append(C((hx, hy + 1.5, z - f * .2), (.44, .62, .08), hair, **k))
        for s in (-1, 1): bx.append(C((hx + s * .215, hy + 1.56, z - f * .04), (.04, .42, .3), hair, **k))
    if eyes is not None:
        for s in (-1, 1): bx.append(C((hx + s * .09, hy + 1.705, z + f * .195), (.05, .045, .01), eyes, emis=3.2, cast=False, **k))
    if scale != 1.0:
        o = np.array([x, 0, z], np.float32)
        for b in bx:
            b.lo = (b.lo - o) * scale + o; b.hi = (b.hi - o) * scale + o
    return bx

def _figure_modern(x, z, f, face, hood, jeans, hair, skin, swing, armsw, hidden, dissolve, yoff, glow, eyes, noref, headx, heady,
                   headphones, backpack, hair_long, scale, shirt, gesture, posture, hold, hold_color, g, outfit, hair_style, hat, hat_color, tie, lights, cape=None):
    """character with gestures, postures, held objects and outfits (poses.py)"""
    k = dict(hidden=hidden, dissolve=dissolve, noref=noref); face = face if face is not None else face_tex('neutral')
    outfit = outfit or 'hoodie'; posture = posture or 'stand'
    dx, dy, hdx, hdy = P.body_motion(gesture, g); x = x + dx; yoff = yoff + dy
    bx, dyu = P.legs(x, z, f, yoff, posture, swing, jeans, (28, 26, 28), skin, k, outfit, g)
    yb = yoff + dyu
    if outfit == 'hoodie':
        bx.append(C((x, yb + 1.12, z), (.50, .64, .28), hood, mat=M_FABRIC, **k))
        if shirt: bx.append(C((x, yb + 1.12, z + f * .142), (.2, .5, .01), shirt, **k))
        bx.append(C((x, yb + 1.0, z + f * .145), (.30, .14, .01), tuple(int(c * .75) for c in hood), **k))
        for s in (-1, 1): bx.append(C((x + s * .05, yb + 1.30, z + f * .145), (.022, .16, .012), (196, 196, 186), **k))
        if hat != 'hood': bx.append(C((x, yb + 1.46, z - f * .06), (.44, .10, .22), tuple(int(c * .85) for c in hood), **k))
    else:
        bx += P.torso(x, z, f, yb, outfit, hood, skin, k, tie=tie, shirt=shirt)
    fore = skin if outfit in ('tshirt', 'dress') else hood
    ab, hand = P.arms(x, z, f, yb, g, gesture, hood, fore, skin, k, armsw=armsw if gesture in (None, 'idle') else 0., outfit=outfit)
    bx += ab
    if backpack and outfit in ('hoodie', 'tshirt', 'coat', 'spacesuit', 'suit'): bx.append(C((x, yb + 1.16, z - f * .21), (.38, .48, .15), (36, 40, 44) if outfit != 'spacesuit' else (220, 220, 226), mat=M_FABRIC, **k))
    if cape: bx.append(C((x, yb + .92, z - f * .2), (.54, 1.05, .03), tuple(cape), mat=M_FABRIC, **k))
    hx = x + headx + hdx; hy = yb + heady + hdy
    bx.append(C((hx, hy + 1.68, z), (.40, .40, .38), skin, tex={'+z': face} if f > 0 else {'-z': face}, **k))
    bx += P.hair_and_hat(hx, hy, z, f, hair, 'long' if (hair_long and not hair_style) else hair_style, hat, hat_color, hood, k)
    if headphones == 'cou':                           # 9/11/2026 : headphones worn around the neck (opt-in value 'cou')
        bx += [C((hx + s * .19, hy + 1.38, z + f * .03), (.07, .15, .15), (26, 26, 32), **k) for s in (-1, 1)] + [C((hx, hy + 1.35, z - f * .11), (.44, .05, .06), (26, 26, 32), **k)]
    elif headphones and hat not in ('hood', 'beanie'):
        for s in (-1, 1):
            bx.append(C((hx + s * .225, hy + 1.68, z), (.06, .16, .16), (26, 26, 32), **k))
            bx.append(C((hx + s * .258, hy + 1.68, z + f * .04), (.02, .035, .035), (80, 255, 130), emis=1.6 if glow == 0 else glow, cast=False, **k))
        if not hat or hat == 'none': bx.append(C((hx, hy + 1.955, z), (.48, .045, .1), (26, 26, 32), **k))
    if eyes is not None:
        for s in (-1, 1): bx.append(C((hx + s * .09, hy + 1.705, z + f * .195), (.05, .045, .01), eyes, emis=3.2, cast=False, **k))
    item_lights = []
    bx += P.held_item(hold, hand, f, k, item_lights, hold_color)
    if scale != 1.0:
        o = np.array([x, 0, z], np.float32)
        for b in bx: b.lo = (b.lo - o) * scale + o; b.hi = (b.hi - o) * scale + o
        item_lights = [((np.array(p) - o) * scale + o, c, pw, r) for p, c, pw, r in item_lights]
    if lights is not None: lights += [(tuple(float(v) for v in p), c, pw, r) for p, c, pw, r in item_lights]
    return bx

CREATURE = dict(hood=(22, 22, 26), jeans=(14, 14, 18), hair=(8, 8, 10), skin=(176, 160, 150), eyes=(255, 40, 40))

# ---------------- textures ----------------
def text_tex(lines, size=(64, 32), fg=(255, 255, 255), bg=(0, 0, 0, 0), fs=8, pad=2):
    im = Image.new('RGBA', size, bg); d = ImageDraw.Draw(im); d.fontmode = '1'
    f = ImageFont.truetype(FONT, fs); y = pad
    for l in lines:
        w = d.textlength(l, font=f); d.text(((size[0] - w) / 2, y), l, font=f, fill=fg + (255,)); y += fs + 3
    return np.array(im)

@functools.lru_cache(maxsize=1)
def panel_tex():
    im = Image.new('RGBA', (48, 96), (52, 54, 60, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
    f = ImageFont.truetype(FONT, 8)
    d.rectangle([0, 0, 47, 95], outline=(30, 30, 34, 255))
    for i, (t, y) in enumerate([('3', 8), ('2', 24), ('1', 40), ('R', 56)]):
        d.ellipse([12, y - 1, 36, y + 15], fill=(88, 90, 96, 255), outline=(30, 30, 34, 255)); d.text((20, y + 3), t, font=f, fill=(235, 235, 235, 255))
    d.ellipse([12, 72, 36, 90], fill=(240, 40, 44, 255), outline=(120, 10, 14, 255)); d.text((20, 77), '0', font=f, fill=(255, 235, 235, 255))
    return np.array(im)
@functools.lru_cache(maxsize=1)
def panel_tex_open():
    im = Image.new('RGBA', (48, 24), (52, 54, 60, 255)); d = ImageDraw.Draw(im)
    d.ellipse([4, 2, 22, 20], fill=(120, 124, 132, 255)); d.ellipse([26, 2, 44, 20], fill=(212, 168, 60, 255))
    d.polygon([(9, 11), (14, 7), (14, 15)], fill=(20, 20, 24, 255)); d.polygon([(19, 11), (14, 7), (14, 15)], fill=(20, 20, 24, 255))
    d.polygon([(30, 11), (35, 7), (35, 15)], fill=(20, 20, 24, 255)); d.polygon([(40, 11), (35, 7), (35, 15)], fill=(20, 20, 24, 255))
    return np.array(im)

@functools.lru_cache(maxsize=4)
def writing_tex():
    """'LAISSE-MOI SORTIR' scrawled on the mirror (from part 2), with drips"""
    im = Image.new('RGBA', (96, 96), (0, 0, 0, 0)); d = ImageDraw.Draw(im); d.fontmode = '1'
    f = ImageFont.truetype(FONT, 16); rng = np.random.default_rng(4)
    for txt, y in (('LAISSE', 34), ('-MOI', 54), ('SORTIR', 76)):
        w = d.textlength(txt, font=f); d.text(((96 - w) / 2, y), txt, font=f, fill=(225, 222, 215, 235))
        for _ in range(4):
            x = int(rng.uniform((96 - w) / 2 + 2, (96 + w) / 2 - 2)); L = int(rng.uniform(3, 9))
            d.line([(x, y + 15), (x, y + 15 + L)], fill=(215, 212, 205, 220))
    return np.array(im)

def crack_tex(prog, w=96, h=96, seed=5):
    a = np.zeros((h, w, 4), np.uint8)
    if prog <= 0: return a
    rng = np.random.default_rng(seed)
    cx, cy = w * .52, h * .42
    for r in range(11):
        ang = rng.uniform(0, 2 * math.pi); L = int(prog * rng.uniform(.5, 1.0) * 85)
        x, y = cx, cy; da = rng.uniform(-.25, .25)
        for i in range(L):
            ang += rng.uniform(-.35, .35) * .6 + da * .02
            x += math.cos(ang); y += math.sin(ang)
            xi, yi = int(x), int(y)
            if 0 <= xi < w and 0 <= yi < h: a[yi, xi] = (240, 244, 250, 255)
            if i % 12 == 11:
                bx_, by_, ba = x, y, ang + rng.choice([-1, 1]) * .9
                for j in range(int((L - i) * .5)):
                    ba += rng.uniform(-.3, .3); bx_ += math.cos(ba); by_ += math.sin(ba)
                    xi, yi = int(bx_), int(by_)
                    if 0 <= xi < w and 0 <= yi < h: a[yi, xi] = (220, 228, 240, 255)
    if prog > .05: a[int(cy) - 1:int(cy) + 2, int(cx) - 1:int(cx) + 2] = (255, 255, 255, 255)
    return a

@functools.lru_cache(maxsize=64)
def mirror_tex(prog_q):
    a = writing_tex().copy(); c = crack_tex(prog_q / 20.)
    m = c[..., 3] > 0; a[m] = c[m]; return a

@functools.lru_cache(maxsize=1)
def wetsign_tex():
    im = Image.new('RGBA', (32, 48), (232, 196, 40, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'
    d.polygon([(16, 6), (26, 24), (6, 24)], outline=(20, 20, 20, 255)); d.text((14, 12), '!', font=ImageFont.truetype(FONT, 8), fill=(20, 20, 20, 255))
    f = ImageFont.truetype(FONT, 8)
    d.text((4, 30), 'SOL', font=f, fill=(20, 20, 20, 255)); d.text((0, 39), 'MOUIL', font=f, fill=(20, 20, 20, 255))
    return np.array(im)

def digit_tex(txt='0'):
    return text_tex([txt], (16, 12), (255, 40, 36), (12, 4, 4, 255), 8, 2)

# ---------------- floor / AO ----------------
# ======================= part 4 additions =======================
def _wrap(text, n=10):
    out = []; cur = ''
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > n: out.append(cur); cur = w
        else: cur = (cur + ' ' + w).strip()
    if cur: out.append(cur)
    return out

@functools.lru_cache(maxsize=64)
def phone_tex(header='INCONNU', msgs=(), typing=False, new_last=False):
    """phone screen like part 2: navy UI, '?' avatar, message bubbles (newest at the bottom)"""
    W_, H_ = 104, 181
    im = Image.new('RGBA', (W_, H_), (10, 12, 24, 255)); d = ImageDraw.Draw(im); d.fontmode = '1'; f = ImageFont.truetype(FONT, 8)
    d.rectangle([0, 0, W_ - 1, 17], fill=(28, 36, 64, 255))
    d.ellipse([4, 3, 15, 14], fill=(120, 130, 160, 255)); d.text((7, 5), '?', font=f, fill=(20, 24, 40, 255))
    d.text((19, 5), header, font=f, fill=(225, 228, 240, 255))
    blocks = []
    for i, m in enumerate(msgs):
        lines = _wrap(m, 11); h = len(lines) * 10 + 6
        blocks.append((lines, h, new_last and i == len(msgs) - 1))
    if typing: blocks.append((['. . .'], 16, False))
    y = H_ - 6
    for lines, h, hl in reversed(blocks):
        y -= h
        if y < 20: break
        d.rectangle([3, y, W_ - 4, y + h - 2], fill=(46, 78, 140, 255) if hl else (34, 50, 96, 255))
        for k, l in enumerate(lines): d.text((6, y + 4 + k * 10), l, font=f, fill=(240, 236, 226, 255))
        y -= 4
    return np.array(im)

@functools.lru_cache(maxsize=32)
def ceil_crack_tex(q):
    prog = q / 16.; w, h = 38, 184
    a = np.zeros((h, w, 4), np.uint8)
    if prog <= 0: return a
    rng = np.random.default_rng(17)
    for cz in (150, 163, 130, 172, 110, 90):
        cx = rng.uniform(8, 30)
        for r in range(6):
            ang = rng.uniform(0, 2 * math.pi); L = int(prog * rng.uniform(10, 34)); x, y = cx, cz
            for i in range(L):
                ang += rng.uniform(-.5, .5); x += math.cos(ang); y += math.sin(ang)
                if 0 <= int(x) < w and 0 <= int(y) < h: a[int(y), int(x)] = (20, 14, 12, 255)
        if prog > .55:
            rr = int((prog - .55) * 6)
            a[max(0, cz - rr):cz + rr, max(0, int(cx) - rr):int(cx) + rr] = (4, 3, 3, 255)     # holes where tiles fell
    return a

@functools.lru_cache(maxsize=1)
def city_tex():
    rng = np.random.default_rng(3); a = np.zeros((40, 48, 4), np.uint8); a[..., 3] = 255
    for y in range(40): a[y, :, :3] = (int(14 + y * .6), int(20 + y * .8), int(48 + y * 1.2))
    for b in range(9):
        x0 = int(rng.uniform(0, 44)); bw = int(rng.uniform(4, 9)); bh = int(rng.uniform(10, 30))
        a[40 - bh:, x0:x0 + bw, :3] = (10, 12, 22)
        for _ in range(int(bw * bh / 9)):
            yy = int(rng.uniform(40 - bh + 1, 39)); xx = int(rng.uniform(x0, min(47, x0 + bw - 1)))
            if rng.random() < .55: a[yy, xx, :3] = (250, 214, 120)
    return a

