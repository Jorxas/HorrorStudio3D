"""Richer, more varied and more narrative places for the pixel3d engine (V3, additive).

Three things live here, and nothing else in the engine changes:

1. **Extra props** (`NEW_PROPS`, `NEW_PROP_LIGHTS`), registered into `world.PROPS` at import: lamps with real
   geometry (pendant, floor, desk, sconce, bare bulb, neon tube), wall dressing (posters, frames, clocks, cracks,
   damp stains, graffiti, pinned notes, child drawings), room fittings (radiator, pipes, vents, coat rack, wall
   shelf, cobwebs), floor clutter (clothes, books, bottles, suitcase, bucket, broken glass, dust sheets) and horror
   clues (handprint, scratch marks, tally marks, broken doll, cracked mirror, knocked-over chair, open diary).
2. **Four new place archetypes** (`NEW_PLACES`), registered into `places.PLACES`: `corridor`, `stairwell`,
   `parking` and `alley` (outdoor). They are the kinds of place the owner asked for and that no recipe had.
3. **The `variation` dressing pass** (`dress`): one optional key on any set spec turns a bare room into a dressed,
   worn, inhabited one, driven by a narrative intention rather than by a list of props:

       "sets": {"chambre": {"type": "bedroom", "variation": {"mood": "abandoned", "seed": 3}}}
       "sets": {"salon":   {"type": "living_room", "variation": "lived_in"}}
       "sets": {"cave":    {"type": "basement", "variation": {"story": "la petite a disparu ici", "density": 1.2}}}

Design rules kept on purpose:
  * **Opt-in only.** `dress()` returns the spec object unchanged when `variation` is absent, so every shipped
    episode, demo and baseline renders box for box as before (`tools/regress.py`, `tools/regress_v2.py`).
  * **Data, not geometry.** This pass only writes props / zones / anchors into the set spec. The micro-finish of
    the boxes a set already built (mouldings, welts, seams, table-top accessories) is the job of the separate art
    pass of `feature/pixel3d-art-redesign` (`art.decor` / `art.furniture`); the two stack without overlapping.
  * **Deterministic.** Every choice comes from `numpy.default_rng(seed ^ crc32(place))`: same spec, same video.
  * **Nothing in the way.** Placement goes through `Keepout`: the footprint of the props the recipe already put
    down (measured by calling `sets.prop_boxes`), a disc around every anchor where an actor can stand, and the
    camera lane from the `start` anchor to the middle of the room. Object counts are capped (`max_objects`).
"""
import copy, functools, math, zlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .r3d import B, C, Box, M_WOODV, M_PLASTER, M_METAL, M_DOOR, M_CARD, M_FABRIC
from . import world as W
from . import places as PL
from ...paths import FONT_PIXEL

# ===================================================================== small helpers
def _sh(c, f):
    """shade a colour by a factor"""
    return tuple(max(0, min(255, int(round(v * f)))) for v in tuple(c)[:3])


def _mix(a, b, t):
    return tuple(max(0, min(255, int(round(a[i] * (1 - t) + b[i] * t)))) for i in range(3))


@functools.lru_cache(maxsize=256)
def _text_tex(lines, w, h, fg, bg, fs):
    """pixel-art sheet of centred lines (cached: a poster is drawn once per episode)"""
    im = Image.new('RGBA', (w, h), bg)
    d = ImageDraw.Draw(im)
    d.fontmode = '1'
    f = ImageFont.truetype(FONT_PIXEL, fs)
    y = max(2, (h - len(lines) * (fs + 3)) // 2)
    for l in lines:
        d.text(((w - d.textlength(l, font=f)) / 2, y), l, font=f, fill=tuple(fg) + (255,))
        y += fs + 3
    return np.array(im)


def _txt(lines, size=(48, 64), fg=(240, 236, 226), bg=(26, 24, 30, 255), fs=8):
    lines = tuple(str(l)[:14] for l in (lines if isinstance(lines, (list, tuple)) else [lines]))[:5]
    return _text_tex(lines, int(size[0]), int(size[1]), tuple(fg), tuple(bg), int(fs))


@functools.lru_cache(maxsize=128)
def _poster_tex(art, seed, w, h):
    """printed sheet: a gig poster, a film poster, a map, a missing notice or the rules of the series"""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.fontmode = '1'
    rng = np.random.default_rng(seed * 977 + 11)
    f = ImageFont.truetype(FONT_PIXEL, 7)
    f2 = ImageFont.truetype(FONT_PIXEL, 5)

    def ctext(y, s, col, fo=None):
        fo = fo or f
        d.text(((w - d.textlength(s, font=fo)) / 2, y), s, font=fo, fill=col + (255,))

    if art == 'band':
        bgc = [(28, 24, 40), (44, 18, 24), (18, 32, 34)][int(rng.integers(0, 3))]
        d.rectangle([0, 0, w, h], fill=bgc + (255,))
        d.ellipse([w * .22, h * .16, w * .78, h * .16 + w * .56], fill=_mix(bgc, (240, 220, 120), .8) + (255,))
        for k in range(7):                                        # a crowd silhouette along the bottom
            x = int(rng.integers(0, w))
            hh = int(h * (.10 + .08 * rng.random()))
            d.rectangle([x, h - hh, x + 3, h], fill=(10, 8, 12, 255))
        ctext(int(h * .68), ['NOIR', 'ECHO', 'VOLT', 'CENDRE'][int(rng.integers(0, 4))], (244, 240, 228))
        ctext(int(h * .82), 'EN TOURNEE', (200, 196, 186), f2)
    elif art == 'film':
        d.rectangle([0, 0, w, h], fill=(16, 14, 20, 255))
        d.rectangle([2, 2, w - 3, int(h * .58)], fill=(34, 30, 44, 255))
        for k in range(5):                                        # a lit window grid, cinema-poster style
            x = 4 + int(rng.integers(0, max(1, w - 10)))
            d.rectangle([x, int(h * .28), x + 2, int(h * .36)], fill=(236, 206, 120, 255))
        ctext(int(h * .62), ['LA NUIT', 'ETAGE 0', 'SANS NOM'][int(rng.integers(0, 3))], (236, 80, 70))
        ctext(int(h * .78), 'INTERDIT -16', (190, 186, 178), f2)
    elif art == 'map':
        d.rectangle([0, 0, w, h], fill=(214, 198, 158, 255))
        for k in range(6):
            y = int(h * (.14 + .13 * k))
            d.line([3, y, w - 4, y], fill=(150, 132, 100, 255))
        for k in range(5):
            x = int(rng.integers(4, max(5, w - 5)))
            y = int(rng.integers(4, max(5, h - 5)))
            d.rectangle([x, y, x + 2, y + 2], fill=(170, 60, 50, 255))
        ctext(2, 'PLAN', (90, 72, 50), f2)
    elif art == 'missing':
        d.rectangle([0, 0, w, h], fill=(232, 228, 216, 255))
        ctext(3, 'DISPARUE', (180, 30, 30))
        d.rectangle([int(w * .26), int(h * .22), int(w * .74), int(h * .66)], fill=(60, 58, 64, 255))
        d.ellipse([int(w * .38), int(h * .30), int(w * .62), int(h * .52)], fill=(150, 140, 130, 255))
        ctext(int(h * .70), 'VUE LE 3/11', (40, 38, 40), f2)
        ctext(int(h * .82), 'APPELEZ', (40, 38, 40), f2)
    else:                                                          # the rules of the series, pinned on a wall
        d.rectangle([0, 0, w, h], fill=(236, 232, 220, 255))
        ctext(3, 'REGLES', (30, 28, 32))
        for k, s in enumerate(('1 NE PAS', '  SORTIR', '2 NE PAS', '  REGARDER', '3 NE PAS', '  PAUSER')):
            d.text((3, int(h * .22) + k * 7), s, font=f2, fill=(40, 38, 40, 255))
    return np.array(im)


@functools.lru_cache(maxsize=64)
def _drawing_tex(seed, w, h):
    """a child's crayon drawing: a house, a sun, the family, and one black figure too many"""
    im = Image.new('RGBA', (w, h), (246, 242, 230, 255))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(seed * 313 + 7)
    d.rectangle([int(w * .10), int(h * .42), int(w * .52), int(h * .80)], fill=(196, 140, 96, 255))
    d.polygon([(int(w * .06), int(h * .42)), (int(w * .31), int(h * .18)), (int(w * .56), int(h * .42))], fill=(170, 60, 56, 255))
    d.rectangle([int(w * .24), int(h * .58), int(w * .36), int(h * .80)], fill=(110, 76, 50, 255))
    d.ellipse([int(w * .74), int(h * .06), int(w * .96), int(h * .28)], fill=(244, 214, 70, 255))
    n = 2 + int(rng.integers(0, 2))
    for k in range(n + 1):
        x = int(w * (.58 + .13 * k))
        col = (60, 90, 170, 255) if k < n else (26, 24, 28, 255)
        d.line([x, int(h * .60), x, int(h * .82)], fill=col, width=2)
        d.ellipse([x - 4, int(h * .52), x + 4, int(h * .60)], fill=col)
        d.line([x - 6, int(h * .68), x + 6, int(h * .68)], fill=col, width=2)
    d.line([0, int(h * .83), w, int(h * .83)], fill=(80, 140, 70, 255), width=3)
    return np.array(im)


@functools.lru_cache(maxsize=64)
def _grime_tex(kind, seed, w, h):
    """a worn surface patch: damp stain, soot, peeled wallpaper, spray tag"""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    a = np.zeros((h, w, 4), np.uint8)
    rng = np.random.default_rng(seed * 61 + 5)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    if kind == 'damp':
        cx, cy = w * .5, h * .25
        r = np.hypot((xx - cx) / (w * .55), (yy - cy) / (h * .70))
        n = rng.random((h, w)) * .34
        m = r + n < .9
        a[m] = (74, 66, 54, 190)
        m2 = r + n < .55
        a[m2] = (54, 48, 40, 225)
    elif kind == 'soot':
        m = rng.random((h, w)) < np.clip(1.1 - yy / max(1, h), 0, 1) * .5
        a[m] = (34, 32, 32, 200)
    elif kind == 'peel':
        edge = (h * .34 + h * .22 * np.sin(xx / max(1., w) * 7.0)).astype(np.int32)
        m = yy < edge
        a[m] = (150, 142, 124, 235)
        m2 = (yy >= edge) & (yy < edge + 2)
        a[m2] = (90, 82, 70, 255)
    else:                                                          # spray tag
        col = [(220, 60, 70), (70, 200, 120), (240, 200, 60), (110, 150, 240)][int(rng.integers(0, 4))]
        im2 = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im2)
        d.fontmode = '1'
        f = ImageFont.truetype(FONT_PIXEL, max(6, int(h * .45)))
        s = ['ICI', 'RIEN', 'AIDE', 'SORS', '0'][int(rng.integers(0, 5))]
        d.text(((w - d.textlength(s, font=f)) / 2, h * .22), s, font=f, fill=col + (235,))
        return np.array(im2)
    im = Image.fromarray(a)
    return np.array(im)


# ===================================================================== lamps with real geometry
def P_pendant_lamp(p, c):
    """ceiling rose, flex and a conical shade; built in absolute heights under `ceiling` (default 2.6)"""
    ce = float(p.get('ceiling', 2.6))
    drop = float(p.get('drop', .62))
    y = ce - drop
    col = c or (226, 222, 212)
    out = [C((0, ce - .04, 0), (.16, .07, .16), (60, 58, 56), mat=M_METAL),
           C((0, ce - drop / 2 - .02, 0), (.025, drop - .04, .025), (40, 38, 38))]
    for i in range(4):                                            # a cone made of four shrinking rings
        out.append(C((0, y - .04 - i * .07, 0), (.44 - .09 * i, .075, .44 - .09 * i), _sh(col, 1 - .05 * i), mat=M_PLASTER))
    out.append(C((0, y - .30, 0), (.14, .16, .14), (255, 228, 176), emis=2.2 * float(p.get('on', 1.)), cast=False))
    return out


def P_floor_lamp(p, c):
    """tripod floor lamp: three splayed feet, a pole and a fabric drum shade"""
    col = c or (214, 196, 160)
    out = [C((0, .02, 0), (.44, .04, .44), (52, 48, 46), mat=M_METAL)]
    for a in (0., 2.094, 4.189):
        out.append(C((math.cos(a) * .17, .26, math.sin(a) * .17), (.05, .52, .05), (58, 52, 48), mat=M_WOODV))
    out.append(C((0, .85, 0), (.045, 1.2, .045), (62, 58, 54), mat=M_METAL))
    for i in range(3):
        out.append(C((0, 1.46 + i * .09, 0), (.40 + .015 * i, .095, .40 + .015 * i), _sh(col, .92 + .06 * i), mat=M_FABRIC))
    out.append(C((0, 1.48, 0), (.26, .18, .26), (255, 226, 172), emis=1.9 * float(p.get('on', 1.)), cast=False))
    return out


def P_desk_lamp(p, c):
    """articulated desk lamp: base, two arm segments and a cone head (put it on a desk with "y")"""
    col = c or (56, 92, 132)
    return [C((0, .02, 0), (.20, .04, .20), _sh(col, .8), mat=M_METAL),
            C((0, .19, .02), (.035, .34, .035), col, mat=M_METAL),
            C((0, .35, -.10), (.035, .035, .26), col, mat=M_METAL),
            C((0, .33, -.23), (.17, .13, .17), col, mat=M_METAL),
            C((0, .26, -.23), (.12, .04, .12), (255, 232, 182), emis=1.7 * float(p.get('on', 1.)), cast=False)]


def P_wall_sconce(p, c):
    """wall light: bracket plus a half shade (against a wall, front -z)"""
    col = c or (196, 188, 170)
    return [C((0, 1.78, -.03), (.14, .22, .06), (62, 58, 54), mat=M_METAL),
            C((0, 1.88, -.14), (.30, .10, .22), _sh(col, 1.02), mat=M_PLASTER),
            C((0, 1.80, -.14), (.22, .09, .16), _sh(col, .9), mat=M_PLASTER),
            C((0, 1.84, -.14), (.11, .12, .11), (255, 220, 164), emis=2.0 * float(p.get('on', 1.)), cast=False)]


def P_bare_bulb(p, c):
    """a bulb on a bare flex: the horror staple. `flicker` is handled by PROP_LIGHTS."""
    ce = float(p.get('ceiling', 2.6))
    drop = float(p.get('drop', .75))
    y = ce - drop
    return [C((0, ce - .03, 0), (.10, .06, .10), (48, 46, 44), mat=M_METAL),
            C((0, ce - drop / 2, 0), (.018, drop, .018), (34, 32, 32)),
            C((0, y - .04, 0), (.055, .09, .055), (168, 164, 158), mat=M_METAL),
            C((0, y - .14, 0), (.115, .15, .115), (255, 234, 192), emis=2.6 * float(p.get('on', 1.)), cast=False)]


def P_neon_tube(p, c):
    """ceiling strip light; "dead": the tube is there but gives no light"""
    ce = float(p.get('ceiling', 2.6))
    L = float(p.get('length', 1.2))
    dead = bool(p.get('dead', False))
    return [B((-L / 2, ce - .13, -.09), (L, .07, .18), (96, 98, 104), mat=M_METAL),
            B((-L / 2 + .04, ce - .19, -.07), (L - .08, .055, .14), (226, 236, 246) if dead else (248, 250, 242),
              emis=0. if dead else 2.0 * float(p.get('on', 1.)), cast=False),
            C((-L / 2 + .03, ce - .16, 0), (.05, .09, .14), (70, 70, 74), mat=M_METAL),
            C((L / 2 - .03, ce - .16, 0), (.05, .09, .14), (70, 70, 74), mat=M_METAL)]


def P_exit_sign(p, c):
    """green emergency sign over a door"""
    return [C((0, 2.18, -.05), (.44, .20, .04), (28, 32, 30), mat=M_METAL),
            C((0, 2.18, -.08), (.38, .15, .01), (90, 240, 140), emis=1.9 * float(p.get('on', 1.)), cast=False,
              tex={'-z': _txt(['SORTIE'], (40, 16), (10, 40, 20), (120, 250, 160, 255), 7)}, texemis=1.6)]


# ===================================================================== wall dressing
def P_poster(p, c):
    """a printed sheet taped flat on a wall (front -z). "art": band | film | map | missing | rules"""
    w = float(p.get('width', .62))
    h = float(p.get('height', .88))
    art = str(p.get('art', 'band'))
    s = int(p.get('seed', 0))
    y = float(p.get('at_y', 1.52))
    tex = _poster_tex(art, s, 40, 56)
    out = [B((-w / 2, y - h / 2, -.018), (w, h, .018), (210, 206, 198), mat=M_CARD, tex={'-z': tex})]
    if p.get('tape', True):
        for sx in (-1, 1):
            out.append(C((sx * (w / 2 - .05), y + h / 2 - .01, -.022), (.07, .035, .006), (226, 222, 206), mat=M_CARD, cast=False))
    return out


def P_framed_photo(p, c):
    """framed portrait; "scratched": the face is crossed out"""
    w = float(p.get('width', .34))
    h = float(p.get('height', .42))
    y = float(p.get('at_y', 1.56))
    frame = c or (62, 46, 34)
    im = Image.new('RGBA', (24, 30), (168, 162, 150, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 20, 24, 30], fill=(96, 104, 92, 255))
    d.ellipse([8, 7, 16, 17], fill=(206, 176, 150, 255))
    d.rectangle([7, 17, 17, 24], fill=(70, 86, 128, 255))
    if p.get('scratched'):
        d.line([5, 4, 19, 20], fill=(150, 20, 20, 255), width=2)
        d.line([19, 4, 5, 20], fill=(150, 20, 20, 255), width=2)
    return [B((-w / 2, y - h / 2, -.035), (w, h, .035), frame, mat=M_WOODV),
            B((-w / 2 + .035, y - h / 2 + .035, -.042), (w - .07, h - .07, .008), (180, 176, 168), refl=.22,
              tex={'-z': np.array(im)})]


def P_picture_frames(p, c):
    """a small gallery wall: three frames at slightly different heights"""
    out = []
    s = int(p.get('seed', 0))
    rng = np.random.default_rng(s * 29 + 3)
    for k, (dx, dy, w, h) in enumerate(((-.30, .06, .26, .32), (.02, -.04, .34, .26), (.34, .08, .22, .28))):
        y = 1.52 + dy
        fr = [(62, 46, 34), (36, 34, 36), (148, 132, 96)][int(rng.integers(0, 3))]
        out.append(B((dx - w / 2, y - h / 2, -.03), (w, h, .03), fr, mat=M_WOODV))
        out.append(B((dx - w / 2 + .03, y - h / 2 + .03, -.036), (w - .06, h - .06, .006),
                     [(150, 146, 140), (120, 128, 136), (160, 140, 124)][k], refl=.2))
    return out


def P_wall_clock(p, c):
    """a real round-ish clock: rim, face, two hands. "stopped": the hands give an odd hour."""
    y = float(p.get('at_y', 2.02))
    rim = c or (46, 42, 40)
    hh, mm = (3, 7) if not p.get('stopped') else (int(p.get('hour', 3)), int(p.get('minute', 33)))
    out = [C((0, y, -.03), (.34, .34, .05), rim, mat=M_METAL),
           C((0, y, -.055), (.28, .28, .012), (234, 230, 218), mat=M_PLASTER)]
    for k in range(4):                                            # four marks, enough at this resolution
        a = k * math.pi / 2
        out.append(C((math.sin(a) * .11, y + math.cos(a) * .11, -.062), (.025, .025, .006), (60, 56, 54), cast=False))
    ah = (hh % 12) / 12 * 6.283
    am = (mm % 60) / 60 * 6.283
    out.append(C((math.sin(ah) * .045, y + math.cos(ah) * .045, -.064), (.035, .09, .006), (40, 38, 36), cast=False))
    out.append(C((math.sin(am) * .07, y + math.cos(am) * .07, -.064), (.022, .13, .006), (40, 38, 36), cast=False))
    return out


def P_wall_crack(p, c):
    """a crack running down a wall: four short thin boxes at slight angles"""
    s = int(p.get('seed', 0))
    rng = np.random.default_rng(s * 17 + 1)
    h = float(p.get('height', 1.5))
    y0 = float(p.get('at_y', .55))
    out = []
    x = 0.
    for k in range(4):
        seg = h / 4
        x += float(rng.uniform(-.09, .09))
        out.append(C((x, y0 + seg * (k + .5), -.006), (.022 + .012 * float(rng.random()), seg, .012), (40, 36, 34), cast=False))
        if k == 2:
            out.append(C((x + .10, y0 + seg * 2.6, -.006), (.17, .018, .012), (40, 36, 34), cast=False))
    return out


def P_damp_stain(p, c):
    """a damp patch spreading down from the ceiling or up from the floor"""
    w = float(p.get('width', 1.1))
    h = float(p.get('height', .95))
    y = float(p.get('at_y', 1.9))
    kind = str(p.get('kind', 'damp'))
    return [B((-w / 2, y - h / 2, -.012), (w, h, .012), (78, 70, 58), mat=M_PLASTER, cast=False,
              tex={'-z': _grime_tex(kind, int(p.get('seed', 0)), 30, 26)})]


def P_graffiti(p, c):
    """a spray tag on a wall or a pillar"""
    w = float(p.get('width', .9))
    h = float(p.get('height', .5))
    y = float(p.get('at_y', 1.25))
    return [B((-w / 2, y - h / 2, -.008), (w, h, .008), (120, 118, 114), cast=False,
              tex={'-z': _grime_tex('tag', int(p.get('seed', 0)), 28, 16)}, texemis=.12)]


def P_notes_wall(p, c):
    """pinned papers joined by red string: someone was trying to understand something"""
    s = int(p.get('seed', 0))
    rng = np.random.default_rng(s * 53 + 9)
    out = [B((-.55, 1.12, -.014), (1.10, .80, .014), (58, 50, 42), mat=M_CARD)]
    pts = []
    for k in range(6):
        x = -.44 + .18 * k + float(rng.uniform(-.03, .03))
        y = 1.12 + float(rng.uniform(-.24, .26))
        pts.append((x, y))
        out.append(B((x - .055, y - .07, -.024), (.11, .14, .008), (232, 228, 214), mat=M_CARD, cast=False))
        out.append(C((x, y, -.030), (.022, .022, .006), (200, 40, 40), cast=False))
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):             # the string, as two straight runs per link
        for t in (.25, .75):
            out.append(C((ax + (bx - ax) * t, ay + (by - ay) * t, -.028), (.055, .012, .005), (170, 34, 34), cast=False))
    return out


def P_child_drawing(p, c):
    """a crayon drawing taped to a wall"""
    w = float(p.get('width', .40))
    h = float(p.get('height', .30))
    y = float(p.get('at_y', 1.18))
    return [B((-w / 2, y - h / 2, -.012), (w, h, .012), (246, 242, 230), mat=M_CARD,
              tex={'-z': _drawing_tex(int(p.get('seed', 0)), 28, 22)})]


def P_handprint(p, c):
    """a hand pressed on a wall, in red"""
    y = float(p.get('at_y', 1.32))
    col = c or (128, 22, 20)
    out = [C((0, y, -.008), (.11, .13, .008), col, cast=False)]
    for k, (dx, dh) in enumerate(((-.065, .09), (-.025, .12), (.02, .12), (.058, .09))):
        out.append(C((dx, y + .10 + dh / 2, -.008), (.026, dh, .008), col, cast=False))
    out.append(C((-.085, y - .035, -.008), (.055, .035, .008), col, cast=False))
    return out


def P_scratch_marks(p, c):
    """four parallel scratches, as if something was dragged down the surface"""
    y = float(p.get('at_y', 1.25))
    L = float(p.get('height', .46))
    out = []
    for k in range(4):
        out.append(C((-.10 + k * .066, y, -.009), (.016, L - .03 * (k % 2), .010), (52, 40, 36), cast=False))
    return out


def P_tally_marks(p, c):
    """days counted on a wall: five groups of five"""
    y = float(p.get('at_y', 1.42))
    out = []
    n = int(p.get('count', 23))
    for k in range(min(n, 20)):
        g, i = divmod(k, 5)
        x = -.34 + g * .145 + i * .022
        out.append(C((x, y, -.007), (.012, .16, .007), (226, 222, 210), cast=False))
        if i == 4:
            out.append(C((x - .048, y, -.008), (.125, .016, .007), (226, 222, 210), cast=False))
    return out


def P_radiator(p, c):
    """a ribbed radiator under a window (front -z)"""
    L = float(p.get('length', .9))
    col = c or (226, 224, 218)
    out = [B((-L / 2, .18, -.10), (L, .54, .10), _sh(col, .9), mat=M_METAL)]
    n = max(4, int(L / .085))
    for k in range(n):
        out.append(B((-L / 2 + .02 + k * (L - .04) / n, .18, -.14), ((L - .04) / n * .62, .54, .05), col, mat=M_METAL))
    out += [C((-L / 2 + .05, .12, -.07), (.05, .12, .05), (150, 148, 144), mat=M_METAL),
            C((L / 2 - .05, .12, -.07), (.05, .12, .05), (150, 148, 144), mat=M_METAL)]
    return out


def P_light_switch(p, c):
    return [C((0, 1.12, -.016), (.095, .095, .016), (232, 230, 224), mat=M_PLASTER, cast=False),
            C((0, 1.12, -.026), (.045, .055, .010), (208, 206, 200), cast=False)]


def P_wall_shelf(p, c):
    """a bracket shelf with a few things on it"""
    L = float(p.get('length', .85))
    y = float(p.get('at_y', 1.42))
    col = c or (116, 86, 56)
    out = [B((-L / 2, y, -.24), (L, .035, .24), col, mat=M_WOODV)]
    for sx in (-1, 1):
        out.append(C((sx * (L / 2 - .07), y - .06, -.12), (.03, .09, .18), (62, 58, 54), mat=M_METAL))
    cols = ((150, 40, 40), (40, 80, 140), (200, 170, 60), (60, 120, 70))
    x = -L / 2 + .07
    for k in range(4):
        wd = .055 + .02 * (k % 3)
        out.append(B((x, y + .035, -.20), (wd, .20 + .03 * (k % 2), .14), cols[k % 4], mat=M_CARD))
        x += wd + .012
    out.append(C((L / 2 - .17, y + .10, -.13), (.14, .13, .14), (190, 186, 178), mat=M_PLASTER))
    out.append(C((L / 2 - .17, y + .20, -.13), (.16, .10, .16), (54, 92, 48), mat=M_FABRIC))
    return out


def P_coat_rack(p, c):
    """a coat stand with two hanging coats: a good foreground silhouette"""
    col = c or (72, 56, 42)
    out = [C((0, .03, 0), (.42, .06, .42), _sh(col, .8), mat=M_WOODV),
           C((0, .90, 0), (.06, 1.74, .06), col, mat=M_WOODV)]
    for a in (0., 1.571, 3.142, 4.712):
        out.append(C((math.cos(a) * .12, 1.66, math.sin(a) * .12), (.12, .035, .12), col, mat=M_WOODV))
    for (dx, cc, hh) in ((-.14, (44, 48, 62), 1.00), (.16, (72, 54, 44), .86)):
        out.append(C((dx, 1.62 - hh / 2 + .06, 0), (.30, hh, .17), cc, mat=M_FABRIC))
        out.append(C((dx, 1.60, 0), (.22, .09, .13), _sh(cc, 1.15), mat=M_FABRIC))
    return out


def P_door_frame(p, c):
    """an empty doorway seen from the room it opens into: a foreground occluder for depth"""
    w = float(p.get('width', 1.05))
    h = float(p.get('height', 2.12))
    col = c or (92, 84, 76)
    return [B((-w / 2 - .09, 0, -.11), (.09, h + .09, .22), col, mat=M_WOODV),
            B((w / 2, 0, -.11), (.09, h + .09, .22), col, mat=M_WOODV),
            B((-w / 2 - .09, h, -.11), (w + .18, .09, .22), col, mat=M_WOODV)]


def P_pipes(p, c):
    """a run of pipes under the ceiling, with a valve and a drip stain"""
    L = float(p.get('length', 4.))
    ce = float(p.get('ceiling', 2.6))
    col = c or (104, 96, 86)
    out = [B((-L / 2, ce - .26, -.09), (L, .11, .11), col, mat=M_METAL),
           B((-L / 2, ce - .42, -.05), (L, .07, .07), _sh(col, .86), mat=M_METAL)]
    for k in range(max(2, int(L / 1.6))):
        x = -L / 2 + .4 + k * 1.6
        out.append(C((x, ce - .18, -.035), (.06, .14, .06), _sh(col, .75), mat=M_METAL))
    out.append(C((-L / 2 + .9, ce - .21, -.035), (.20, .20, .05), (168, 72, 48), mat=M_METAL))
    return out


def P_air_vent(p, c):
    """a grille in a wall"""
    w = float(p.get('width', .46))
    h = float(p.get('height', .30))
    y = float(p.get('at_y', 2.1))
    out = [B((-w / 2, y - h / 2, -.03), (w, h, .03), (92, 92, 96), mat=M_METAL)]
    for k in range(4):
        out.append(B((-w / 2 + .03, y - h / 2 + .035 + k * (h - .07) / 4, -.042), (w - .06, (h - .07) / 7, .012), (36, 36, 40), cast=False))
    return out


def P_cobweb(p, c):
    """a web just under the ceiling: three diagonals and two cross threads (place it with rot facing the room)"""
    s = float(p.get('size', 1.))
    y = float(p.get('at_y', float(p.get('ceiling', 2.6)) - .26))
    col = (206, 204, 198)
    out = []
    for a in (.35, .70, 1.15):
        out.append(C((math.cos(a) * .19 * s, y - math.sin(a) * .04, -math.sin(a) * .19 * s),
                     (.40 * s, .010, .40 * s), col, cast=False, mat=M_FABRIC))
    for r in (.11, .20):
        out.append(C((r * .7 * s, y - .02, -r * .7 * s), (r * 1.5 * s, .008, r * 1.5 * s), col, cast=False, mat=M_FABRIC))
    return out


# ===================================================================== floor clutter
def P_clothes_pile(p, c):
    s = float(p.get('size', 1.))
    cols = ((58, 64, 86), (104, 70, 62), (70, 78, 70), (120, 112, 96))
    sd = int(p.get('seed', 0))
    rng = np.random.default_rng(sd * 41 + 13)
    out = []
    for k in range(4):
        out.append(C((float(rng.uniform(-.16, .16)) * s, (.04 + .055 * k) * s, float(rng.uniform(-.14, .14)) * s),
                     ((.46 - .07 * k) * s, .07 * s, (.38 - .05 * k) * s), cols[k % 4], mat=M_FABRIC))
    return out


def P_books_pile(p, c):
    cols = ((150, 40, 40), (40, 80, 140), (200, 170, 60), (60, 120, 70), (120, 60, 130))
    sd = int(p.get('seed', 0))
    rng = np.random.default_rng(sd * 37 + 5)
    out = []
    y = 0.
    for k in range(int(p.get('count', 5))):
        t = .038 + .018 * float(rng.random())
        out.append(C((float(rng.uniform(-.04, .04)), y + t / 2, float(rng.uniform(-.04, .04))),
                     (.21, t, .15), cols[k % 5], mat=M_CARD))
        y += t
    return out


def P_bottles(p, c):
    sd = int(p.get('seed', 0))
    rng = np.random.default_rng(sd * 23 + 7)
    out = []
    for k in range(int(p.get('count', 4))):
        x = float(rng.uniform(-.22, .22))
        z = float(rng.uniform(-.18, .18))
        g = (58, 96, 62) if k % 2 else (126, 92, 44)
        if k == 2 and p.get('fallen', True):                      # one lying on its side
            out += [C((x, .035, z), (.26, .07, .07), g, refl=.25), C((x + .17, .035, z), (.05, .04, .04), (210, 206, 196))]
        else:
            out += [C((x, .10, z), (.075, .20, .075), g, refl=.25), C((x, .24, z), (.035, .09, .035), g, refl=.25),
                    C((x, .29, z), (.04, .02, .04), (210, 206, 196))]
    return out


def P_cardboard_stack(p, c):
    """a column of taped moving boxes: a big readable silhouette"""
    n = int(p.get('count', 3))
    col = c or (142, 110, 74)
    out = []
    y = 0.
    for k in range(n):
        w = .58 - .05 * k
        hh = .40 - .03 * k
        out.append(C((.03 * (k % 2), y + hh / 2, -.02 * (k % 3)), (w, hh, w * .82), _sh(col, 1 - .05 * k), mat=M_CARD))
        out.append(C((.03 * (k % 2), y + hh - .005, -.02 * (k % 3)), (w * .18, .012, w * .84), (206, 198, 180), mat=M_CARD, cast=False))
        y += hh
    return out


def P_suitcase(p, c):
    col = c or (92, 62, 46)
    if p.get('open'):
        return [B((-.30, 0, -.21), (.60, .13, .42), col, mat=M_CARD), B((-.30, .13, .18), (.60, .42, .05), col, mat=M_CARD),
                B((-.26, .13, -.17), (.52, .07, .34), (158, 148, 132), mat=M_FABRIC)]
    return [B((-.30, 0, -.11), (.60, .42, .22), col, mat=M_CARD),
            B((-.30, .20, -.12), (.60, .035, .24), _sh(col, .72), mat=M_CARD),
            C((0, .455, 0), (.17, .07, .04), (56, 50, 44), mat=M_METAL),
            C((-.22, .36, -.125), (.05, .05, .012), (176, 160, 110), mat=M_METAL),
            C((.22, .36, -.125), (.05, .05, .012), (176, 160, 110), mat=M_METAL)]


def P_bucket(p, c):
    col = c or (120, 126, 134)
    out = [C((0, .14, 0), (.30, .28, .30), col, mat=M_METAL), C((0, .27, 0), (.33, .03, .33), _sh(col, .8), mat=M_METAL)]
    if p.get('water', True):
        out.append(C((0, .25, 0), (.26, .012, .26), (46, 56, 58), refl=.55, cast=False))
    if p.get('mop', False):
        out += [C((.02, .80, .03), (.045, 1.5, .045), (134, 102, 62), mat=M_WOODV),
                C((.02, .22, .03), (.22, .18, .20), (182, 176, 160), mat=M_FABRIC)]
    return out


def P_broken_glass(p, c):
    sd = int(p.get('seed', 0))
    rng = np.random.default_rng(sd * 19 + 3)
    out = []
    for k in range(9):
        out.append(C((float(rng.uniform(-.30, .30)), .008, float(rng.uniform(-.26, .26))),
                     (.03 + .04 * float(rng.random()), .012, .03 + .04 * float(rng.random())),
                     (182, 196, 198), refl=.5, cast=False))
    return out


def P_papers_scattered(p, c):
    sd = int(p.get('seed', 0))
    rng = np.random.default_rng(sd * 31 + 11)
    out = []
    for k in range(7):
        out.append(C((float(rng.uniform(-.38, .38)), .006 + .004 * k, float(rng.uniform(-.32, .32))),
                     (.21, .006, .15), (226, 222, 208), mat=M_CARD, cast=False))
    return out


def P_toy_scatter(p, c):
    sd = int(p.get('seed', 0))
    rng = np.random.default_rng(sd * 43 + 17)
    cols = ((220, 70, 60), (60, 120, 200), (240, 200, 60), (80, 180, 100))
    out = []
    for k in range(5):
        out.append(C((float(rng.uniform(-.30, .30)), .055, float(rng.uniform(-.26, .26))), (.11, .11, .11), cols[k % 4]))
    out.append(C((.22, .09, -.18), (.18, .18, .18), (230, 150, 170)))
    return out


def P_dust_sheet(p, c):
    """furniture under a sheet: a shape you cannot name, which is the point"""
    w = float(p.get('width', 1.3))
    d_ = float(p.get('depth', .8))
    h = float(p.get('height', .9))
    col = c or (196, 192, 180)
    out = [C((0, h * .34, 0), (w, h * .68, d_), col, mat=M_FABRIC),
           C((.04, h * .80, -.03), (w * .78, h * .26, d_ * .82), _sh(col, 1.04), mat=M_FABRIC),
           C((-w * .30, h * .14, d_ * .10), (w * .30, h * .28, d_ * .5), _sh(col, .9), mat=M_FABRIC)]
    for sx in (-1, 1):                                            # the hem hanging a little off the floor
        out.append(C((sx * w * .42, .03, 0), (w * .14, .06, d_ * .96), _sh(col, .84), mat=M_FABRIC, cast=False))
    return out


# ===================================================================== horror clues
def P_doll_broken(p, c):
    col = c or (214, 190, 170)
    return [C((0, .055, 0), (.14, .11, .09), (182, 72, 96), mat=M_FABRIC),
            C((0, .15, -.01), (.11, .11, .10), col),
            C((-.11, .045, .05), (.09, .05, .05), col),
            C((.14, .02, -.08), (.05, .04, .12), col),                   # the arm that came off
            C((.02, .19, -.05), (.10, .05, .04), (60, 44, 34), mat=M_FABRIC),
            C((-.025, .165, -.052), (.016, .016, .006), (30, 28, 30), cast=False),
            C((.025, .165, -.052), (.016, .016, .006), (30, 28, 30), cast=False)]


def P_mirror_cracked(p, c):
    """a wall mirror with a star crack: the reflection is broken into pieces"""
    w = float(p.get('width', .72))
    h = float(p.get('height', 1.18))
    y = float(p.get('at_y', 1.42))
    out = [B((-w / 2, y - h / 2, -.05), (w, h, .05), c or (52, 42, 34), mat=M_WOODV),
           B((-w / 2 + .05, y - h / 2 + .05, -.062), (w - .10, h - .10, .014), (186, 192, 196), refl=.80, grain=0.)]
    for a in (0.3, 1.3, 2.4, 3.6, 4.8):                           # radiating fracture lines
        for r in (.12, .26):
            out.append(C((math.cos(a) * r * .8, y + math.sin(a) * r, -.070), (.030, .030, .006), (62, 66, 70), cast=False))
    return out


def P_chair_knocked(p, c):
    """a chair on its side: someone left in a hurry"""
    col = c or (104, 78, 52)
    return [B((-.22, .36, -.21), (.44, .06, .42), col, mat=M_WOODV),
            B((-.22, .02, .16), (.44, .40, .05), col, mat=M_WOODV)] + \
           [B((x, .34, z), (.045, .04, .045), _sh(col, .8), mat=M_WOODV) for x in (-.20, .16) for z in (-.19, .15)] + \
           [B((-.21, 0, -.20), (.42, .05, .05), _sh(col, .7), mat=M_WOODV)]


def P_open_diary(p, c):
    """an open notebook with a pen (put it on a table with "y")"""
    return [B((-.17, 0, -.11), (.17, .025, .22), (238, 234, 220), mat=M_CARD),
            B((0, 0, -.11), (.17, .025, .22), (232, 228, 214), mat=M_CARD),
            B((-.175, -.004, -.115), (.35, .006, .23), (92, 36, 36), mat=M_CARD),
            C((-.085, .029, .02), (.11, .004, .004), (60, 58, 60), cast=False),
            C((-.085, .029, -.02), (.09, .004, .004), (60, 58, 60), cast=False),
            C((.07, .029, .04), (.012, .012, .15), (40, 60, 120), cast=False)]


def P_tv_old(p, c):
    """a boxy set on short legs, with static on the tube"""
    col = c or (62, 58, 54)
    return [B((-.33, .10, -.28), (.66, .50, .50), col, mat=M_PLASTER),
            B((-.28, .15, -.30), (.50, .38, .02), (22, 24, 28), refl=.25),
            B((-.265, .165, -.312), (.47, .35, .008), (120, 136, 150), emis=1.15 * float(p.get('on', 1.))),
            C((.26, .35, -.30), (.05, .05, .02), (168, 160, 148), mat=M_METAL),
            C((.26, .25, -.30), (.05, .05, .02), (168, 160, 148), mat=M_METAL)] + \
           [C((x, .05, z), (.05, .10, .05), (40, 38, 36)) for x in (-.26, .26) for z in (-.20, .20)]


# ===================================================================== corridor / stairwell / parking / alley fittings
def P_concrete_pillar(p, c):
    """a square car-park pillar with a painted band and a number"""
    h = float(p.get('height', 2.5))
    s = float(p.get('size', .44))
    col = c or (124, 122, 118)
    out = [B((-s / 2, 0, -s / 2), (s, h, s), col, mat=M_PLASTER)]
    band = tuple(p.get('band', (206, 176, 54)))
    out.append(B((-s / 2 - .006, .62, -s / 2 - .006), (s + .012, .16, s + .012), band, mat=M_PLASTER, cast=False))
    if p.get('text'):
        out.append(B((-.15, 1.42, -s / 2 - .012), (.30, .30, .012), (234, 230, 220), mat=M_PLASTER, cast=False,
                     tex={'-z': _txt([str(p['text'])], (20, 20), (40, 38, 38), (236, 232, 222, 255), 10)}))
    return out


def P_parking_sign(p, c):
    """a numbered bay sign hanging from the ceiling"""
    ce = float(p.get('ceiling', 2.5))
    txt = str(p.get('text', 'A 12'))
    return [C((0, ce - .10, 0), (.03, .20, .03), (70, 70, 74), mat=M_METAL),
            B((-.34, ce - .52, -.02), (.68, .32, .04), (38, 62, 124), mat=M_METAL,
              tex={'-z': _txt([txt], (36, 18), (238, 236, 230), (38, 62, 124, 255), 9)})]


def P_handrail(p, c):
    """a steel handrail: top rail, mid rail and posts"""
    L = float(p.get('length', 2.4))
    h = float(p.get('height', 1.0))
    col = c or (118, 120, 126)
    out = [B((-L / 2, h - .05, -.03), (L, .05, .06), col, mat=M_METAL),
           B((-L / 2, h * .52, -.025), (L, .04, .05), _sh(col, .9), mat=M_METAL)]
    n = max(2, int(L / .8) + 1)
    for k in range(n):
        out.append(B((-L / 2 + k * (L - .06) / (n - 1), 0, -.025), (.06, h - .05, .05), _sh(col, .85), mat=M_METAL))
    return out


def P_stair_flight(p, c):
    """a straight run of steps going up towards +z, with a stringer on each side"""
    n = int(p.get('steps', 9))
    rise = float(p.get('rise', .19))
    run = float(p.get('run', .27))
    w = float(p.get('width', 1.2))
    col = c or (128, 124, 118)
    out = []
    for k in range(n):
        out.append(B((-w / 2, k * rise, k * run), (w, rise, run + .02), _sh(col, 1 - .012 * k), mat=M_PLASTER))
        out.append(B((-w / 2, (k + 1) * rise - .018, k * run), (w, .018, run + .02), _sh(col, 1.12), mat=M_PLASTER, cast=False))
    for sx in (-1, 1):
        out.append(B((sx * w / 2 - (.07 if sx > 0 else 0), 0, 0), (.07, n * rise * .55, n * run), _sh(col, .8), mat=M_PLASTER))
    rail = str(p.get('rail', ''))                             # a rail climbs with the steps: one short run per step
    rc = (118, 120, 126)
    for sx in (-1, 1):
        if not ((sx < 0 and 'L' in rail) or (sx > 0 and 'R' in rail)):
            continue
        x = sx * (w / 2 - .06)
        for k in range(n):
            y = (k + 1) * rise
            out.append(B((x - .025, y + .88, k * run), (.05, .05, run + .02), rc, mat=M_METAL, cast=False))
            if k % 2 == 0:
                out.append(B((x - .02, y, k * run + run * .3), (.04, .90, .04), _sh(rc, .85), mat=M_METAL, cast=False))
    return out


def P_wheelie_bin(p, c):
    col = c or (46, 68, 54)
    return [B((-.33, .10, -.26), (.66, .92, .52), col, mat=M_PLASTER),
            B((-.34, 1.00, -.27), (.68, .07, .56), _sh(col, 1.1), mat=M_PLASTER),
            C((-.28, .09, .20), (.07, .18, .18), (34, 34, 36)),
            C((.28, .09, .20), (.07, .18, .18), (34, 34, 36)),
            C((0, 1.06, -.27), (.26, .05, .05), _sh(col, .7), mat=M_METAL)]


def P_dumpster(p, c):
    col = c or (72, 86, 72)
    return [B((-.95, .14, -.62), (1.90, .92, 1.24), col, mat=M_METAL),
            B((-.98, 1.02, -.64), (.96, .09, 1.28), _sh(col, 1.12), mat=M_METAL),
            B((.02, 1.02, -.64), (.96, .09, 1.28), _sh(col, .96), mat=M_METAL),
            B((-.99, .10, -.66), (1.98, .08, 1.32), _sh(col, .7), mat=M_METAL)] + \
           [C((x, .08, z), (.08, .16, .16), (32, 32, 34)) for x in (-.82, .82) for z in (-.48, .48)]


def P_pallet(p, c):
    col = c or (152, 122, 82)
    out = []
    for k in range(5):
        out.append(B((-.55, .09, -.45 + k * .22), (1.10, .025, .13), col, mat=M_WOODV))
    for k in range(3):
        out.append(B((-.55 + k * .47, 0, -.45), (.12, .09, .92), _sh(col, .82), mat=M_WOODV))
    return out


def P_tyre_stack(p, c):
    out = []
    for k in range(int(p.get('count', 4))):
        out.append(C((.02 * (k % 2), .07 + k * .13, -.02 * (k % 3)), (.62, .13, .62), (34, 33, 35), mat=M_PLASTER))
    return out


def P_jerrycan(p, c):
    col = c or (164, 76, 32)
    return [B((-.13, 0, -.09), (.26, .38, .18), col, mat=M_METAL),
            C((0, .41, 0), (.10, .05, .09), _sh(col, .8), mat=M_METAL),
            C((0, .43, -.06), (.17, .035, .035), _sh(col, .7), mat=M_METAL)]


def P_trolley(p, c):
    """a shopping trolley, usually on its own and somewhere it should not be"""
    col = c or (158, 162, 170)
    out = [B((-.28, .46, -.40), (.56, .04, .80), col, mat=M_METAL)]
    for k in range(6):
        out.append(B((-.28, .46 + k * .07, -.40), (.56, .012, .012), col, mat=M_METAL))
        out.append(B((-.28, .46 + k * .07, .38), (.56, .012, .012), col, mat=M_METAL))
    for sx in (-1, 1):
        out.append(B((sx * .27, .46, -.40), (.014, .44, .80), _sh(col, .9), mat=M_METAL))
        out.append(C((sx * .22, .07, -.32), (.05, .14, .14), (44, 44, 46)))
        out.append(C((sx * .22, .07, .32), (.05, .14, .14), (44, 44, 46)))
    out.append(B((-.28, .90, .36), (.56, .05, .05), (168, 60, 52), mat=M_PLASTER))
    return out


def P_pram(p, c):
    col = c or (52, 56, 72)
    return [C((0, .62, 0), (.52, .34, .84), col, mat=M_FABRIC),
            C((0, .84, .18), (.50, .30, .40), _sh(col, .85), mat=M_FABRIC),
            C((0, .44, 0), (.07, .36, .07), (90, 92, 98), mat=M_METAL),
            C((0, .92, -.42), (.46, .04, .04), (90, 92, 98), mat=M_METAL)] + \
           [C((x, .13, z), (.06, .26, .26), (36, 36, 38)) for x in (-.24, .24) for z in (-.30, .30)]


def P_letterboxes(p, c):
    """a bank of mailboxes in an entrance hall (front -z)"""
    col = c or (86, 94, 104)
    out = [B((-.62, .80, -.14), (1.24, 1.00, .14), col, mat=M_METAL)]
    for r in range(4):
        for k in range(4):
            x = -.58 + k * .30
            y = .85 + r * .235
            out.append(B((x, y, -.155), (.27, .205, .016), _sh(col, 1.08 - .04 * ((r + k) % 3)), mat=M_METAL))
            out.append(C((x + .225, y + .10, -.162), (.022, .05, .006), (200, 196, 186), cast=False))
    return out


def P_noticeboard(p, c):
    """a glazed noticeboard with a few sheets behind it"""
    out = [B((-.55, .95, -.07), (1.10, .80, .07), c or (62, 70, 62), mat=M_METAL),
           B((-.50, 1.00, -.085), (1.00, .70, .012), (206, 200, 186), mat=M_CARD)]
    for k, (dx, dy, w, h) in enumerate(((-.30, .12, .30, .38), (.06, .16, .26, .30), (.26, -.10, .24, .22))):
        out.append(B((dx - w / 2, 1.33 + dy - h / 2, -.095), (w, h, .006), (236, 232, 218), mat=M_CARD, cast=False))
    out.append(B((-.52, .98, -.10), (1.04, .74, .006), (176, 190, 196), refl=.42, grain=0., cast=False))
    return out


def P_fire_escape(p, c):
    """a steel platform and ladder bolted to a wall (front -z)"""
    y = float(p.get('at_y', 2.5))
    col = c or (74, 72, 70)
    out = [B((-1.1, y, -1.00), (2.20, .07, 1.00), col, mat=M_METAL)]
    for k in range(9):
        out.append(B((-1.1, y + .07, -1.00 + k * .11), (2.20, .012, .012), col, mat=M_METAL))
    out += [B((-1.1, y + .07, -1.00), (.05, .92, .05), col, mat=M_METAL), B((1.05, y + .07, -1.00), (.05, .92, .05), col, mat=M_METAL),
            B((-1.1, y + .92, -1.02), (2.20, .05, .05), col, mat=M_METAL)]
    for k in range(int(y / .26)):                                 # the ladder down to the ground
        out.append(B((-.26, k * .26, -.82), (.52, .030, .030), _sh(col, .9), mat=M_METAL))
    for sx in (-1, 1):
        out.append(B((sx * .26 - .025, 0, -.84), (.05, y, .05), _sh(col, .85), mat=M_METAL))
    return out


def P_laundry_line(p, c):
    """washing strung across an alley above the actors"""
    y = float(p.get('at_y', 3.0))
    L = float(p.get('length', 6.))
    cols = ((206, 202, 190), (110, 128, 160), (176, 94, 86), (196, 190, 160), (96, 104, 112))
    out = [B((-L / 2, y, -.012), (L, .015, .015), (58, 56, 52), cast=False)]
    n = int(p.get('count', 6))
    for k in range(n):
        x = -L / 2 + (k + .6) * L / (n + .2)
        hh = .42 + .16 * ((k * 7) % 3)
        out.append(C((x, y - hh / 2 - .02, 0), (.34, hh, .04), cols[k % 5], mat=M_FABRIC, cast=False))
    return out


def P_steam_vent(p, c):
    """a street vent with a plume rising from it (three fading blocks)"""
    out = [C((0, .03, 0), (.80, .06, .60), (74, 74, 78), mat=M_METAL)]
    for k in range(4):
        out.append(C((.03 * k, .22 + k * .40, -.02 * k), (.42 + .14 * k, .40, .34 + .12 * k),
                     (176, 178, 182), mat=M_FABRIC, cast=False, dissolve=.45 + .12 * k))
    return out


def P_fire_extinguisher(p, c):
    return [C((0, .70, -.09), (.17, .42, .17), (176, 38, 32), mat=M_METAL),
            C((0, .93, -.09), (.07, .09, .07), (54, 52, 50), mat=M_METAL),
            C((0, .98, -.14), (.05, .05, .14), (54, 52, 50), mat=M_METAL),
            B((-.09, .62, -.03), (.18, .22, .03), (120, 118, 114), mat=M_METAL)]


def P_floor_drain(p, c):
    out = [C((0, .005, 0), (.34, .02, .34), (86, 84, 82), mat=M_METAL, cast=False)]
    for k in range(4):
        out.append(C((0, .016, -.12 + k * .08), (.28, .012, .035), (40, 40, 42), cast=False))
    return out


def P_puddle_ring(p, c):
    """a shallow puddle as a reflective disc (outdoors prefer a water zone)"""
    s = float(p.get('size', 1.))
    return [C((0, .004, 0), (1.0 * s, .008, .76 * s), (36, 38, 42), refl=.62, grain=0., cast=False)]


def P_plastic_curtain(p, c):
    """hanging strips of plastic in a doorway: a cheap, effective foreground occluder"""
    w = float(p.get('width', 1.1))
    h = float(p.get('height', 2.0))
    n = max(3, int(w / .16))
    out = []
    for k in range(n):
        x = -w / 2 + (k + .5) * w / n
        out.append(C((x, h / 2 + .06, 0), (w / n * .88, h - .12, .015), (214, 216, 208), mat=M_FABRIC,
                     refl=.18, cast=False, dissolve=.18))
    return out


NEW_PROPS = {k[2:]: v for k, v in list(globals().items()) if k.startswith('P_') and callable(v)}
NEW_PROP_LIGHTS = {
    'pendant_lamp':  [((0, 2.0, 0), (1, .88, .70), 1.5, 4.2, False)],
    'floor_lamp':    [((0, 1.48, 0), (1, .86, .66), 1.2, 3.4, False)],
    'desk_lamp':     [((0, .28, -.22), (1, .90, .74), .8, 2.0, False)],
    'wall_sconce':   [((0, 1.84, -.22), (1, .84, .62), .9, 3.0, False)],
    'bare_bulb':     [((0, 1.84, 0), (1, .92, .80), 1.4, 4.0, True)],
    'neon_tube':     [((0, 2.30, 0), (.96, .98, .92), 1.1, 4.0, False)],
    'exit_sign':     [((0, 2.18, -.3), (.35, 1., .5), .35, 1.8, False)],
    'tv_old':        [((0, .34, -.5), (.45, .62, .95), .55, 2.2, True)],
    'steam_vent':    [((0, .6, 0), (.6, .64, .7), .25, 1.6, 'soft')],
}


# ===================================================================== four new place archetypes
def corridor(spec):
    """A block-of-flats corridor: long one-point perspective, numbered doors on both sides, strip lights (one dead),
    letterboxes, a noticeboard, a bike, a pram, a worn runner. The camera starts at z = .5 looking +z."""
    s = int(spec.get('seed', 0))
    rng = np.random.default_rng(s * 911 + 17)
    d = float(spec.get('length', 16.))
    wd = float(spec.get('width', 2.6))
    ce = 2.5
    doors = [{'id': 'porte.1', 'wall': 'W', 'pos': 2.2 / d, 'width': 1.0},
             {'id': 'porte.2', 'wall': 'E', 'pos': 4.6 / d, 'width': 1.0},
             {'id': 'porte.3', 'wall': 'W', 'pos': 8.0 / d, 'width': 1.0},
             {'id': 'porte.4', 'wall': 'E', 'pos': 11.2 / d, 'width': 1.0},
             {'id': 'porte.fond', 'wall': 'N', 'pos': .5, 'width': 1.1}]
    for dr in doors:
        if dr['id'] == str(spec.get('open_door', '')):
            dr['open'] = 1.
    o, r = PL._room(spec, 'couloir', [wd, d], 'wallpaper', 'linoleum', light='none', height=ce,
                    doors=doors, ceiling_color=[132, 128, 118])
    r['wall_color'] = spec.get('wall_color', [128, 112, 96])
    o['fill'] = float(spec.get('fill', .40))
    o['ambient'] = spec.get('ambient', (.12, .115, .11))
    o['fog'] = float(spec.get('fog', .035))
    o['ambience'] = spec.get('ambience', 'room')
    o['zones'] = [{'rect': [-wd / 2 + .45, .4, wd / 2 - .45, d - .4], 'ground': 'carpet'}]
    o['textured_ground'] = True
    o['ground'] = 'linoleum'
    props = []
    dead = int(rng.integers(0, 4))
    for k, z in enumerate(np.arange(1.6, d - .6, 3.0)):           # the strip lights give the corridor its rhythm
        props.append({'type': 'neon_tube', 'at': [0., float(z)], 'ceiling': ce, 'length': 1.3, 'dead': k == dead})
    for k, dr in enumerate(doors[:4]):
        side = -1 if dr['wall'] == 'W' else 1
        z = dr['pos'] * d
        wx = side * (wd / 2 - .11)
        rt = 3 if side < 0 else 1
        props.append({'type': 'poster', 'at': [wx, z + 1.05], 'rot': rt, 'art': 'rules' if k == 1 else 'map',
                      'width': .34, 'height': .46, 'at_y': 1.58, 'seed': s + k})
        props.append({'type': 'wall_shelf', 'at': [wx, z - 1.15], 'rot': rt, 'length': .6, 'at_y': 1.30} if k == 2
                     else {'type': 'light_switch', 'at': [wx, z - .85], 'rot': rt})
        props.append({'type': 'poster', 'at': [wx, z], 'rot': rt, 'art': 'map', 'width': .13, 'height': .17,
                      'at_y': 1.92, 'tape': False, 'seed': s * 7 + k})
    props += [{'type': 'letterboxes', 'at': [-wd / 2 + .11, 1.0], 'rot': 3},
              {'type': 'noticeboard', 'at': [wd / 2 - .11, 1.9], 'rot': 1},
              {'type': 'radiator', 'at': [wd / 2 - .11, 7.0], 'rot': 1, 'length': .9},
              {'type': 'bicycle', 'at': [-wd / 2 + .30, 5.6], 'rot': 0},
              {'type': 'pram', 'at': [wd / 2 - .45, 13.0], 'rot': 0},
              {'type': 'exit_sign', 'at': [0., d - .16], 'rot': 0},
              {'type': 'damp_stain', 'at': [-wd / 2 + .1, 9.6], 'rot': 3, 'width': 1.4, 'height': 1.0, 'at_y': 1.85, 'seed': s},
              {'type': 'wall_crack', 'at': [wd / 2 - .1, 10.4], 'rot': 1, 'height': 1.6, 'at_y': .5, 'seed': s + 2},
              {'type': 'cobweb', 'at': [-wd / 2 + .2, d - .3], 'rot': 0, 'ceiling': ce},
              {'type': 'cobweb', 'at': [wd / 2 - .2, d - .3], 'rot': 1, 'ceiling': ce}]
    r['props'] = [p for p in props if p]
    o['anchors'] = {'couloir.start': (0., .9), 'couloir.mid': (0., d / 2), 'couloir.fond': (0., d - 1.2),
                    'porte.1': (-wd / 2 + .7, 2.2), 'porte.2': (wd / 2 - .7, 4.6), 'porte.3': (-wd / 2 + .7, 8.0),
                    'porte.4': (wd / 2 - .7, 11.2), 'boites': (-wd / 2 + .8, 1.0), 'velo': (-wd / 2 + .8, 5.6),
                    'start': (0., .5)}
    return o


def stairwell(spec):
    """A concrete stairwell over two storeys: a flight going up to a landing, handrails, a window on the landing,
    a bare bulb, graffiti. Actors stay on the ground floor (the landing is scenery: see docs/DECORS_VARIATION.md)."""
    s = int(spec.get('seed', 0))
    ce = float(spec.get('height', 5.0))
    wd, dp = 4.0, 5.6
    o, r = PL._room(spec, 'escalier', [wd, dp], 'concrete', 'stone', light='none', height=ce,
                    doors=[{'id': 'porte', 'wall': 'S', 'pos': .22, 'width': 1.0}],
                    windows=[{'id': 'fenetre', 'wall': 'E', 'pos': .74, 'night': spec.get('night', True)}],
                    ceiling='plain', ceiling_color=[104, 102, 98])
    r['wall_color'] = spec.get('wall_color', [120, 118, 112])
    r['wainscot'] = False
    o['fill'] = float(spec.get('fill', .30))
    o['fog'] = float(spec.get('fog', .03))
    o['ambient'] = spec.get('ambient', (.125, .125, .125))
    o['ambience'] = spec.get('ambience', 'room')
    rise, run, nst = .19, .27, 12
    top = nst * rise                                          # 2.28 m: the landing, one storey up
    zend = 1.5 + nst * run
    r['props'] = [
        {'type': 'stair_flight', 'at': [-1.05, 1.5], 'rot': 0, 'steps': nst, 'rise': rise, 'run': run,
         'width': 1.5, 'rail': 'R'},
        {'type': 'handrail', 'at': [-1.05, zend + .62], 'rot': 0, 'length': 1.5, 'height': 1.0, 'y': top},
        {'type': 'handrail', 'at': [-.28, zend + .35], 'rot': 1, 'length': .8, 'height': 1.0, 'y': top},
        {'type': 'bare_bulb', 'at': [.95, 2.2], 'ceiling': ce - 1.9},
        {'type': 'neon_tube', 'at': [-.6, zend + .4], 'ceiling': ce, 'length': 1.1},
        {'type': 'graffiti', 'at': [wd / 2 - .11, 2.1], 'rot': 1, 'width': 1.0, 'height': .55, 'at_y': 1.35, 'seed': s},
        {'type': 'wall_crack', 'at': [-wd / 2 + .1, 1.4], 'rot': 3, 'height': 1.8, 'at_y': .4, 'seed': s + 1},
        {'type': 'damp_stain', 'at': [wd / 2 - .1, 4.4], 'rot': 1, 'width': 1.1, 'height': 1.0, 'at_y': 2.2, 'seed': s + 5},
        {'type': 'pipes', 'at': [1.55, dp / 2], 'rot': 1, 'length': dp - .8, 'ceiling': ce},
        {'type': 'radiator', 'at': [wd / 2 - .11, 1.1], 'rot': 1, 'length': .8},
        {'type': 'bucket', 'at': [1.5, 1.0], 'water': True, 'mop': True},
        {'type': 'cardboard_stack', 'at': [1.45, 4.6], 'rot': 2, 'count': 2},
        {'type': 'poster', 'at': [-wd / 2 + .11, 3.6], 'rot': 3, 'art': 'missing', 'width': .5, 'height': .7,
         'at_y': 1.55, 'seed': s},
        {'type': 'exit_sign', 'at': [-1.1, .18], 'rot': 2},
        {'type': 'letterboxes', 'at': [1.88, 3.2], 'rot': 1},
        {'type': 'cobweb', 'at': [-wd / 2 + .22, dp - .3], 'rot': 0, 'at_y': ce - .3},
    ]
    o['anchors'] = {'escalier.bas': (-1.05, 1.1), 'palier': (-1.05, zend + .6), 'porte': (-1.1, .5),
                    'fenetre': (wd / 2 - .5, dp * .74), 'escalier.cote': (1.25, 2.4), 'escalier.fond': (1.2, 4.8),
                    'start': (1.1, .6)}
    return o


def parking(spec):
    """An underground car park: pillars, painted bays, parked cars, strip lights (some dead), hanging signs, pipes,
    a lone trolley, a puddle. Wide, low and deep: strong silhouettes and real depth."""
    s = int(spec.get('seed', 0))
    wd = float(spec.get('width', 20.))
    dp = float(spec.get('depth', 22.))
    ce = 2.55
    o, r = PL._room(spec, 'parking', [wd, dp], 'concrete', 'none', light='none', dark=True, height=ce,
                    ceiling='plain', ceiling_color=[104, 102, 100])
    r['wall_color'] = spec.get('wall_color', [116, 114, 110])
    r['wainscot'] = False
    o['textured_ground'] = True
    o['ground'] = 'concrete'
    o['fill'] = float(spec.get('fill', .34))
    o['ambient'] = spec.get('ambient', (.10, .10, .105))
    o['fog'] = float(spec.get('fog', .045))
    o['ambience'] = spec.get('ambience', 'cave')
    zones = []
    for k in range(7):                                            # painted bay lines, both sides of the aisle
        x = -wd / 2 + 1.2 + k * 2.6
        for z0, z1 in ((1.2, 6.2), (dp - 6.2, dp - 1.2)):
            zones.append({'rect': [x - .06, z0, x + .06, z1], 'ground': 'snow'})
    zones.append({'rect': [-wd / 2 + 1.1, 6.1, wd / 2 - 1.1, 6.25], 'ground': 'snow'})
    zones.append({'circle': [3.4, 12.6, 1.7], 'ground': 'water'})
    o['zones'] = zones
    props = []
    for k, z in enumerate(np.arange(2.4, dp - 1.0, 4.4)):         # ceiling lights down the aisle
        for x in (-4.2, 4.2):
            props.append({'type': 'neon_tube', 'at': [float(x), float(z)], 'ceiling': ce, 'length': 1.5,
                          'dead': ((k * 2 + (x > 0)) % 5) == 3})
    for (cx, cz, rt, col) in ((-7.8, 3.6, 0, (46, 58, 98)), (-5.2, 3.6, 0, (168, 164, 158)), (2.6, 3.6, 0, (92, 36, 36)),
                              (-2.6, dp - 3.6, 2, (54, 66, 56)), (5.2, dp - 3.6, 2, (34, 36, 40))):
        props.append({'type': 'car', 'at': [cx, cz], 'rot': rt, 'color': list(col)})
    for k, (px, pz) in enumerate([(x, z) for z in (7.8, 13.0, 18.2) for x in (-6.8, -1.6, 3.6, 8.4)]):
        p = {'type': 'concrete_pillar', 'at': [float(px), float(pz)], 'height': ce}
        if k % 4 == 0:
            p['text'] = 'ABC'[k % 3] + str(k + 1)
        props.append(p)
    props += [{'type': 'parking_sign', 'at': [0., 9.2], 'ceiling': ce, 'text': 'NIVEAU -2'},
              {'type': 'parking_sign', 'at': [-5.0, 16.6], 'ceiling': ce, 'text': 'A 01-14'},
              {'type': 'pipes', 'at': [0., dp / 2], 'rot': 0, 'length': dp - 1.0, 'ceiling': ce},
              {'type': 'exit_sign', 'at': [-wd / 2 + .12, 10.4], 'rot': 3},
              {'type': 'trolley', 'at': [1.1, 10.2], 'rot': 1},
              {'type': 'floor_drain', 'at': [3.4, 12.6]},
              {'type': 'wheelie_bin', 'at': [wd / 2 - .7, 8.6], 'rot': 1},
              {'type': 'wheelie_bin', 'at': [wd / 2 - .7, 9.5], 'rot': 1},
              {'type': 'tyre_stack', 'at': [-wd / 2 + .9, 15.4], 'count': 4},
              {'type': 'jerrycan', 'at': [-wd / 2 + .8, 14.4], 'rot': 1},
              {'type': 'fire_extinguisher', 'at': [-wd / 2 + .12, 7.2], 'rot': 3},
              {'type': 'graffiti', 'at': [-1.6, 12.77], 'rot': 0, 'width': .42, 'height': .3, 'at_y': 1.3, 'seed': s},
              {'type': 'graffiti', 'at': [wd / 2 - .11, 12.0], 'rot': 1, 'width': 1.6, 'height': .8, 'at_y': 1.4, 'seed': s + 4},
              {'type': 'damp_stain', 'at': [-wd / 2 + .1, 18.0], 'rot': 3, 'width': 1.8, 'height': 1.3, 'at_y': 1.9, 'seed': s + 2},
              {'type': 'papers_scattered', 'at': [-3.4, 11.0], 'seed': s},
              {'type': 'broken_glass', 'at': [2.0, 16.2], 'seed': s + 1}]
    r['props'] = props
    o['anchors'] = {'parking.entree': (0., 1.2), 'parking.allee': (0., 10.0), 'parking.fond': (0., dp - 2.0),
                    'voiture.1': (-5.2, 5.6), 'voiture.2': (2.6, 5.6), 'pilier': (-1.6, 13.0),
                    'flaque': (3.4, 12.6), 'sortie': (-wd / 2 + 1.0, 10.4), 'chariot': (1.1, 10.2),
                    'start': (0., .8)}
    return o


def alley(spec):
    """An outdoor dead-end alley at night: two blocks of flats for walls, wet asphalt, a dumpster, bins, pallets,
    a fire escape, washing lines overhead, a steam vent, one streetlight. The outdoor archetype of this increment."""
    s = int(spec.get('seed', 0))
    night = spec.get('sky', 'night') == 'night'
    wd = float(spec.get('width', 5.0))
    dp = float(spec.get('length', 26.))
    o = PL._base(spec, outdoor=True, sky='night', ground='asphalt', fog=.05, ambience='city', stars=False,
                 wet=spec.get('wet', True), fill=.42,
                 backdrop=[{'type': 'city', 'height': 14, 'density': 36}], ambient=(.125, .13, .165),
                 zones=[{'circle': [-1.2, 7.4, 1.5], 'ground': 'water'},
                        {'circle': [1.6, 15.2, 1.1], 'ground': 'water'},
                        {'rect': [-wd / 2, -4, -wd / 2 + .5, dp], 'ground': 'stone'},
                        {'rect': [wd / 2 - .5, -4, wd / 2, dp], 'ground': 'stone'}])
    o['fill'] = float(spec.get('fill', .66))
    blocks = []
    for side in (-1, 1):
        for k in range(3):
            z0 = -4 + k * (dp + 4) / 3
            hh = 13. + 3. * ((k * 3 + (side > 0)) % 3)
            blocks.append({'at': [side * (wd / 2 + 4.5), 0., z0 + (dp + 4) / 6], 'size': [9., hh, (dp + 4) / 3 - .3],
                           'color': [96 + 14 * ((k + side) % 3), 84, 74], 'material': 'plaster',
                           'facade': {'style': 'old' if (k + side) % 2 else 'brick', 'lit': .22 if night else 0.,
                                      'night': night, 'seed': s * 5 + k * 3 + (side > 0)}})
    blocks.append({'at': [0., 0., dp + 1.2], 'size': [wd + 9., 15., 2.4], 'color': [88, 80, 72], 'material': 'plaster',
                   'facade': {'style': 'concrete', 'lit': .12 if night else 0., 'night': night, 'seed': s + 41}})
    o['blocks'] = blocks + list(spec.get('blocks', []))
    props = [{'type': 'dumpster', 'at': [-wd / 2 + 1.15, 11.2], 'rot': 1, 'color': [70, 84, 70]},
             {'type': 'wheelie_bin', 'at': [wd / 2 - .75, 5.4], 'rot': 3},
             {'type': 'wheelie_bin', 'at': [wd / 2 - .75, 6.4], 'rot': 3, 'color': [52, 60, 88]},
             {'type': 'wheelie_bin', 'at': [-wd / 2 + .8, 17.6], 'rot': 1, 'color': [96, 78, 48]},
             {'type': 'pallet', 'at': [wd / 2 - .9, 13.4], 'rot': 1},
             {'type': 'pallet', 'at': [wd / 2 - .9, 14.2], 'rot': 1},
             {'type': 'tyre_stack', 'at': [-wd / 2 + .9, 20.4], 'count': 3},
             {'type': 'jerrycan', 'at': [-wd / 2 + .7, 19.3], 'rot': 1},
             {'type': 'fire_escape', 'at': [wd / 2 - .02, 9.0], 'rot': 3, 'at_y': 3.2},
             {'type': 'laundry_line', 'at': [0., 6.2], 'rot': 1, 'at_y': 3.6, 'length': wd + .6, 'count': 5},
             {'type': 'laundry_line', 'at': [0., 16.8], 'rot': 1, 'at_y': 4.1, 'length': wd + .6, 'count': 4},
             {'type': 'steam_vent', 'at': [1.3, 9.4]},
             {'type': 'streetlight', 'at': [-wd / 2 + .45, 3.0], 'rot': 1},
             {'type': 'streetlight', 'at': [-wd / 2 + .45, 9.6], 'rot': 1},
             {'type': 'wall_sconce', 'at': [wd / 2 - .04, 6.0], 'rot': 3},
             {'type': 'wall_sconce', 'at': [-wd / 2 + .04, 20.6], 'rot': 1},
             {'type': 'wall_sconce', 'at': [-wd / 2 + .04, 12.6], 'rot': 1},
             {'type': 'wall_sconce', 'at': [wd / 2 - .04, 19.4], 'rot': 3},
             {'type': 'streetlight', 'at': [wd / 2 - .45, 16.0], 'rot': 3},
             {'type': 'lantern', 'at': [wd / 2 - .55, 22.4], 'rot': 3},
             {'type': 'graffiti', 'at': [-wd / 2 + .02, 8.2], 'rot': 1, 'width': 2.0, 'height': 1.0, 'at_y': 1.6, 'seed': s},
             {'type': 'graffiti', 'at': [wd / 2 - .02, 18.0], 'rot': 3, 'width': 1.6, 'height': .9, 'at_y': 1.4, 'seed': s + 6},
             {'type': 'graffiti', 'at': [0., dp - .02], 'rot': 0, 'width': 2.4, 'height': 1.1, 'at_y': 1.7, 'seed': s + 9},
             {'type': 'poster', 'at': [-wd / 2 + .02, 14.6], 'rot': 1, 'art': 'missing', 'width': .55, 'height': .78,
              'at_y': 1.62, 'seed': s},
             {'type': 'poster', 'at': [wd / 2 - .02, 21.0], 'rot': 3, 'art': 'band', 'width': .6, 'height': .84,
              'at_y': 1.55, 'seed': s + 2},
             {'type': 'door', 'at': [wd / 2 - .06, 22.4], 'rot': 3, 'color': [70, 62, 54]},
             {'type': 'exit_sign', 'at': [wd / 2 - .12, 22.4], 'rot': 3},
             {'type': 'floor_drain', 'at': [-1.2, 7.4]},
             {'type': 'papers_scattered', 'at': [.9, 12.4], 'seed': s + 1},
             {'type': 'broken_glass', 'at': [-1.9, 18.6], 'seed': s + 3},
             {'type': 'bicycle', 'at': [-wd / 2 + .40, 15.2], 'rot': 0}]
    o['props'] = props + list(spec.get('props', []))
    o['anchors'] = {'ruelle.entree': (0., 1.6), 'ruelle.mid': (0., 11.0), 'ruelle.fond': (0., dp - 2.2),
                    'benne': (-wd / 2 + 2.1, 11.2), 'escalier_feu': (wd / 2 - 1.5, 9.0), 'porte': (wd / 2 - 1.1, 22.4),
                    'lampadaire': (-wd / 2 + 1.2, 3.0), 'affiche': (-wd / 2 + .9, 14.6), 'start': (0., .6)}
    return o


NEW_PLACES = {'corridor': corridor, 'stairwell': stairwell, 'parking': parking, 'alley': alley}
NEW_AMBIENCE = {'corridor': 'room', 'stairwell': 'room', 'parking': 'cave', 'alley': 'city'}
NEW_START = {'corridor': (0., .5), 'stairwell': (1.1, .6), 'parking': (0., .8), 'alley': (0., .6)}


# ===================================================================== the variation pass
# One narrative intention -> a dressing plan. "mood" is what the shot is about, not a list of furniture:
#   lived_in   someone lives here now          cosy      warm, soft, a home worth losing
#   child      a child's room, too many toys    clinical  wiped clean, nothing personal
#   abandoned  empty for years, damp, dust      ransacked someone searched it in a hurry
#   haunted    lived in, then something came
MOODS = {
    'lived_in':  dict(wear=.20, clutter=.55, clues=.00, lamp='floor_lamp',
                      furniture=('bookshelf', 'armchair', 'plant', 'coat_rack', 'tv_old', 'shelf', 'wall_shelf'),
                      wall=('poster', 'picture_frames', 'wall_clock', 'wall_shelf', 'light_switch', 'framed_photo'),
                      floor=('books_pile', 'clothes_pile', 'suitcase', 'bottles')),
    'cosy':      dict(wear=.10, clutter=.45, clues=.00, lamp='floor_lamp',
                      furniture=('bookshelf', 'armchair', 'plant', 'wall_shelf', 'coat_rack'),
                      wall=('picture_frames', 'framed_photo', 'wall_shelf', 'wall_clock', 'light_switch'),
                      floor=('books_pile', 'clothes_pile')),
    'child':     dict(wear=.15, clutter=.80, clues=.10, lamp='pendant_lamp',
                      furniture=('bookshelf', 'shelf', 'plant', 'cardboard_stack', 'wall_shelf'),
                      wall=('child_drawing', 'poster', 'picture_frames', 'light_switch', 'wall_shelf'),
                      floor=('toy_scatter', 'books_pile', 'clothes_pile')),
    'clinical':  dict(wear=.05, clutter=.15, clues=.00, lamp='neon_tube',
                      furniture=('locker', 'shelf', 'plant', 'noticeboard'),
                      wall=('light_switch', 'air_vent', 'noticeboard', 'wall_clock'),
                      floor=('bucket',)),
    'abandoned': dict(wear=.85, clutter=.55, clues=.30, lamp='bare_bulb',
                      furniture=('dust_sheet', 'cardboard_stack', 'boxes', 'shelf', 'crate', 'barrel'),
                      wall=('damp_stain', 'wall_crack', 'peel', 'cobweb', 'poster', 'air_vent'),
                      floor=('dust_sheet', 'cardboard_stack', 'papers_scattered', 'broken_glass', 'bottles')),
    'ransacked': dict(wear=.60, clutter=.95, clues=.45, lamp='bare_bulb',
                      furniture=('boxes', 'crate', 'shelf', 'cardboard_stack', 'locker'),
                      wall=('wall_crack', 'scratch_marks', 'damp_stain', 'poster', 'light_switch'),
                      floor=('papers_scattered', 'clothes_pile', 'broken_glass', 'chair_knocked', 'suitcase', 'books_pile')),
    'haunted':   dict(wear=.55, clutter=.55, clues=.85, lamp='bare_bulb',
                      furniture=('dust_sheet', 'coat_rack', 'boxes', 'mirror_cracked', 'bookshelf'),
                      wall=('damp_stain', 'tally_marks', 'handprint', 'child_drawing', 'notes_wall', 'cobweb'),
                      floor=('doll_broken', 'papers_scattered', 'chair_knocked', 'dust_sheet')),
}
# The shell of the room itself: wall finish and floor. Changing these is what makes two bedrooms read as two
# different flats rather than the same set with new ornaments. Floors are left alone when the recipe drew its own
# ground (floor "none": caves, car parks).
SHELLS = {
    'lived_in':  dict(walls=('wallpaper', 'plaster', 'plaster_blue', 'wood'), floor=('wood', 'carpet', 'linoleum', 'checker')),
    'cosy':      dict(walls=('wallpaper', 'wood', 'plaster'), floor=('wood', 'carpet')),
    'child':     dict(walls=('plaster_blue', 'plaster_green', 'wallpaper'), floor=('wood', 'carpet')),
    'clinical':  dict(walls=('hospital', 'tiles', 'plaster'), floor=('linoleum', 'tiles')),
    'abandoned': dict(walls=('plaster', 'wallpaper', 'concrete', 'brick'), floor=('wood', 'concrete', 'tiles')),
    'ransacked': dict(walls=('wallpaper', 'plaster', 'plaster_green'), floor=('wood', 'linoleum', 'carpet')),
    'haunted':   dict(walls=('wallpaper', 'wood', 'plaster', 'brick'), floor=('wood', 'carpet', 'tiles')),
}
# A floor may only be swapped inside its own family, so a bedroom never ends up tiled like a bathroom.
FLOOR_FAMILY = {'wood': 'soft', 'carpet': 'soft', 'linoleum': 'soft', 'checker': 'soft',
                'tiles': 'hard', 'concrete': 'hard', 'marble': 'hard', 'stone': 'hard', 'cobble': 'hard'}
CLUES = ('handprint', 'tally_marks', 'scratch_marks', 'notes_wall', 'child_drawing', 'doll_broken',
         'mirror_cracked', 'chair_knocked', 'open_diary')
WALL_CLUES = ('handprint', 'tally_marks', 'scratch_marks', 'notes_wall', 'child_drawing', 'mirror_cracked')
# Free text from the story -> a mood and the clues it calls for. The story stays in charge (AGENTS.md, "story first").
STORY_WORDS = {
    'abandoned': ('abandonn', 'vide depuis', 'poussi', 'ruine', 'condamn', 'moisi', 'personne depuis', 'désaffect'),
    'ransacked': ('fouill', 'saccag', 'cambriol', 'retourn', 'dévast', 'désordre', 'tout renvers'),
    'haunted':   ('disparu', 'hant', 'fant', 'revient', 'quelque chose', 'marques', 'elle était là', 'depuis la nuit'),
    'child':     ('enfant', 'petite', 'petit gar', 'jouet', 'béb', 'fille de'),
    'clinical':  ('hôpital', 'hopital', 'labo', 'clinique', 'bureau', 'propre', 'neutre'),
    'cosy':      ('chaleureu', 'douillet', 'cocon', 'famille', 'noël', 'noel'),
}


def _mood_of(v, place):
    """the mood asked for, or the one the story text implies, or the one the place suggests"""
    if v.get('mood') in MOODS:
        return v['mood']
    txt = str(v.get('story', '')).lower()
    if txt:
        hits = [(sum(txt.count(w) for w in ws), m) for m, ws in STORY_WORDS.items()]
        best = max(hits)
        if best[0] > 0:
            return best[1]
    return {'basement': 'abandoned', 'attic': 'abandoned', 'cave': 'abandoned', 'parking': 'abandoned',
            'kid_bedroom': 'child', 'hospital_room': 'clinical', 'lab': 'clinical', 'office': 'clinical',
            'shop': 'clinical', 'classroom': 'clinical'}.get(place, 'lived_in')


# How many of one kind a single room may hold. A second poster is fine; a second conspiracy board is not, and a
# room with three cracked mirrors stops being frightening. Anything not listed falls back to the bag's own cap.
KIND_CAP = {'notes_wall': 1, 'tally_marks': 1, 'mirror_cracked': 1, 'noticeboard': 1, 'wall_clock': 1,
            'coat_rack': 1, 'tv_old': 1, 'handprint': 2, 'child_drawing': 2, 'picture_frames': 2,
            'bookshelf': 2, 'dust_sheet': 2, 'armchair': 1, 'chair_knocked': 1, 'suitcase': 1, 'locker': 1}


class Bag:
    """draws from a shuffled bag instead of picking at random every time: a wall gets variety, not eleven copies
    of the same stain. `cap` is the default number of one kind a room may hold; KIND_CAP overrides it."""

    def __init__(self, kinds, rng, cap=3):
        self.kinds = list(dict.fromkeys(kinds))
        self.rng = rng
        self.cap = cap
        self.left = []
        self.count = {}

    def draw(self):
        for _ in range(3 * max(1, len(self.kinds))):
            if not self.left:
                self.left = list(self.kinds)
                self.rng.shuffle(self.left)
            k = self.left.pop()
            if self.count.get(k, 0) < min(self.cap, KIND_CAP.get(k, self.cap)):
                self.count[k] = self.count.get(k, 0) + 1
                return k
        return None


class Keepout:
    """where nothing may be dropped: prop footprints, the spots actors stand on, the camera lane"""

    def __init__(self):
        self.discs = []
        self.segs = []

    def disc(self, x, z, r):
        self.discs.append((float(x), float(z), float(r)))
        return self

    def lane(self, a, b, r):
        self.segs.append((float(a[0]), float(a[1]), float(b[0]), float(b[1]), float(r)))
        return self

    def free(self, x, z, r):
        for (px, pz, pr) in self.discs:
            if (x - px) ** 2 + (z - pz) ** 2 < (pr + r) ** 2:
                return False
        for (ax, az, bx, bz, lr) in self.segs:
            dx, dz = bx - ax, bz - az
            L2 = dx * dx + dz * dz + 1e-9
            t = max(0., min(1., ((x - ax) * dx + (z - az) * dz) / L2))
            if (x - (ax + t * dx)) ** 2 + (z - (az + t * dz)) ** 2 < (lr + r) ** 2:
                return False
        return True


def _metrics(p):
    """(half-extent in xz, lo_z, hi_z before rotation, top height) of a prop, read off the boxes it really builds"""
    from .sets import prop_boxes, place as place_boxes
    try:
        raw = prop_boxes(p.get('type', 'crate'), dict(p, rot=0))
        bl = place_boxes([Box(b.lo.copy(), b.hi.copy(), b.col * 255) for b in raw], 0., 0., int(p.get('rot', 0)))
    except Exception:
        return (.35, -.3, .3, 1.0)
    if not raw:
        return (.25, -.2, .2, .5)
    lo = np.min([b.lo for b in bl], 0)
    hi = np.max([b.hi for b in bl], 0)
    return (float(max(hi[0] - lo[0], hi[2] - lo[2])) / 2,
            float(min(b.lo[2] for b in raw)), float(max(b.hi[2] for b in raw)), float(hi[1]))


def _footprint(p):
    return _metrics(p)[0]


def _wall_runs(room, wall, margin=.34):
    """the free runs of a wall, in wall-length coordinates, with the door and window openings taken out"""
    w, d = room.get('size', [4, 5])
    L = w if wall in 'SN' else d
    cuts = []
    for g in list(room.get('doors', []) or []) + list(room.get('windows', []) or []):
        if g.get('wall', 'S' if g in (room.get('doors') or []) else 'N') != wall:
            continue
        c = float(g.get('pos', .5)) * L
        hw = float(g.get('width', 1.1)) / 2 + margin
        cuts.append((c - hw, c + hw))
    cuts.sort()
    runs = []
    cur = .25
    for a, b in cuts:
        if a - cur > .45:
            runs.append((cur, a))
        cur = max(cur, b)
    if L - .25 - cur > .45:
        runs.append((cur, L - .25))
    return runs


def _wall_spot(room, wall, u, inset=.10):
    """(at_x, at_z, rot) of a point at wall-length u, in room-relative coordinates"""
    w, d = room.get('size', [4, 5])
    if wall == 'S':
        return (-w / 2 + u, inset, 2)
    if wall == 'N':
        return (-w / 2 + u, d - inset, 0)
    if wall == 'W':
        return (-w / 2 + inset, u, 3)
    return (w / 2 - inset, u, 1)


def _wall_item(kind, rng, seed, ce):
    """the spec of one wall item, with the random choices this kind needs"""
    p = {'type': kind, 'seed': int(seed)}
    if kind == 'poster':
        p.update(art=('band', 'film', 'map', 'rules', 'missing')[int(rng.integers(0, 5))],
                 width=round(float(rng.uniform(.46, .68)), 2), height=round(float(rng.uniform(.64, .92)), 2),
                 at_y=round(float(rng.uniform(1.38, 1.62)), 2))
    elif kind == 'peel':
        p.update(type='damp_stain', kind='peel', width=round(float(rng.uniform(.7, 1.3)), 2),
                 height=round(float(rng.uniform(.8, 1.3)), 2), at_y=round(ce - float(rng.uniform(.5, .8)), 2))
    elif kind == 'damp_stain':
        p.update(kind=('damp', 'damp', 'soot')[int(rng.integers(0, 3))],
                 width=round(float(rng.uniform(.8, 1.6)), 2), height=round(float(rng.uniform(.8, 1.4)), 2),
                 at_y=round(ce - float(rng.uniform(.45, .9)), 2))
    elif kind == 'wall_crack':
        p.update(height=round(float(rng.uniform(1.0, 1.8)), 2), at_y=round(float(rng.uniform(.3, .7)), 2))
    elif kind == 'graffiti':
        p.update(width=round(float(rng.uniform(.7, 1.5)), 2), height=round(float(rng.uniform(.4, .7)), 2),
                 at_y=round(float(rng.uniform(1.1, 1.5)), 2))
    elif kind == 'wall_clock':
        p.update(at_y=round(min(ce - .45, 2.0), 2), stopped=bool(rng.random() < .5),
                 hour=int(rng.integers(1, 13)), minute=int(rng.integers(0, 60)))
    elif kind == 'framed_photo':
        p.update(at_y=round(float(rng.uniform(1.44, 1.64)), 2), scratched=bool(rng.random() < .25))
    elif kind == 'wall_shelf':
        p.update(length=round(float(rng.uniform(.65, .95)), 2), at_y=round(float(rng.uniform(1.26, 1.5)), 2))
    elif kind == 'tally_marks':
        p.update(count=int(rng.integers(11, 21)), at_y=round(float(rng.uniform(1.25, 1.5)), 2))
    elif kind == 'handprint':
        p.update(at_y=round(float(rng.uniform(1.10, 1.45)), 2))
    elif kind == 'scratch_marks':
        p.update(at_y=round(float(rng.uniform(1.05, 1.40)), 2), height=round(float(rng.uniform(.35, .55)), 2))
    elif kind == 'child_drawing':
        p.update(at_y=round(float(rng.uniform(.95, 1.35)), 2))
    elif kind == 'cobweb':
        p.update(at_y=round(ce - .26, 2), size=round(float(rng.uniform(.8, 1.3)), 2))
    elif kind == 'air_vent':
        p.update(at_y=round(min(ce - .40, 2.1), 2))
    elif kind == 'mirror_cracked':
        p.update(at_y=round(float(rng.uniform(1.34, 1.52)), 2))
    h = float(p.get('height', .5))                            # never let a stain or a poster pierce the ceiling
    if 'at_y' in p:
        p['at_y'] = round(min(float(p['at_y']), ce - .10 - h / 2), 2)
    return p


def _tint(col, wear):
    """a worn wall: darker, browner, less saturated"""
    c = tuple(int(v) for v in col)
    return _sh(_mix(c, (104, 94, 80), min(.42, wear * .45)), 1 - .16 * wear)


def _depth(p):
    """(lo_z, hi_z) of a prop before it is rotated: how far it sticks out of the wall it stands against"""
    m = _metrics(p)
    return (m[1], m[2])


def _dress_room(o, room, v, mood, rng, ce, budget):
    """put the dressing of one room into its props list; returns the anchors worth naming"""
    plan = MOODS[mood]
    wear = float(v.get('wear', plan['wear']))
    dens = float(v.get('density', 1.))
    w, d = room.get('size', [4, 5])
    area = w * d
    ox, oz = room.get('origin', [0, 0])
    props = room.setdefault('props', [])
    ko = Keepout()                                            # the floor: everything already standing on it
    wko = Keepout()                                           # the walls: only what is tall enough to hide a poster
    for p in props:
        half, _lz, _hz, top = _metrics(p)
        ko.disc(p['at'][0], p['at'][1], half + .12)
        if top > 1.25:
            wko.disc(p['at'][0], p['at'][1], half * .8)
    start = (o.get('anchors') or {}).get('start')
    for k, a in (o.get('anchors') or {}).items():             # where an actor can stand
        if k == 'start':
            continue
        ko.disc(a[0] - ox, a[1] - oz, .62)
    # RoomSet also derives <room>.center / .front / .back / .left / .right and one point per door and window,
    # and the director may send an actor to any of them. They are not in the spec, so they are rebuilt here.
    for (ax, az) in ((0., d / 2), (0., .6), (0., d - .6), (-w / 2 + .6, d / 2), (w / 2 - .6, d / 2)):
        ko.disc(ax, az, .55)
    for g in list(room.get('doors') or []) + list(room.get('windows') or []):
        wl = g.get('wall', 'S')
        t = float(g.get('pos', .5))
        ko.disc(*((-w / 2 + w * t, .45) if wl == 'S' else (-w / 2 + w * t, d - .45) if wl == 'N'
                  else (-w / 2 + .45, d * t) if wl == 'W' else (w / 2 - .45, d * t)), .55)
    centre = (0., d / 2)
    lko = Keepout()                                           # the bare lane, for what is only bolted to a wall
    a0 = (start[0] - ox, start[1] - oz) if start else (0., .4)
    ko.lane(a0, centre, .78)                                  # the camera lane, kept clear
    lko.lane(a0, centre, .30)
    named = {}
    n_furn = max(2, int(round((1.6 + area * .095) * dens)))
    n_wall = max(4, int(round((4. + area * .26) * dens)))
    n_floor = max(1, int(round((1 + area * .10) * plan['clutter'] * dens)))
    n_clue = int(round(min(3., 3. * plan['clues'] * dens)))
    if v.get('clues') is False:
        n_clue = 0
    used = 0
    walls = ['N', 'W', 'E', 'S']
    rng.shuffle(walls)

    # ---- furniture: pieces the recipe does not have, against the free parts of the walls, facing the room.
    # This is what makes two bedrooms look like two different bedrooms rather than the same one redecorated.
    fur_bag = Bag(v.get('furniture') or plan['furniture'], rng, cap=2)
    for i in range(n_furn):
        if used >= budget:
            break
        kind = fur_bag.draw()
        if kind is None:
            break
        p = {'type': kind, 'seed': int(rng.integers(0, 9999))}
        if kind == 'dust_sheet':
            p.update(width=round(float(rng.uniform(.9, 1.6)), 2), depth=round(float(rng.uniform(.7, 1.0)), 2),
                     height=round(float(rng.uniform(.8, 1.3)), 2))
        if kind == 'cardboard_stack':
            p['count'] = int(rng.integers(2, 5))
        lo_z, hi_z = _depth(p)
        half = _footprint(p)
        spot = None
        order = list(walls)
        rng.shuffle(order)
        for wall in order:
            for (a, b) in _wall_runs(room, wall, .40):
                if b - a < half * 2 + .25:
                    continue
                for t in (.5, .26, .74, .14, .86):
                    u = a + (b - a) * t
                    x, z, rt = _wall_spot(room, wall, u, .11 + hi_z)
                    if ko.free(x, z, half + .10):
                        spot = (x, z, rt)
                        break
                if spot:
                    break
            if spot:
                break
        if spot is None:
            continue
        p['at'] = [round(spot[0], 2), round(spot[1], 2)]
        p['rot'] = spot[2]
        props.append(p)
        ko.disc(spot[0], spot[1], half + .08)
        if _metrics(p)[3] > 1.25:
            wko.disc(spot[0], spot[1], half * .8)
        used += 1

    # ---- walls: posters, frames, wear, clues. The far wall (N) is the one the camera sees most, so it is served
    # first and twice; the side walls catch the rest.
    pool = list(plan['wall'])
    if wear > .5:
        pool += ['damp_stain', 'wall_crack']
    if wear > .7:
        pool += ['peel']
    bag = Bag([x for x in pool if x != 'cobweb'], rng, cap=3)
    k = 0
    for wall in ['N', 'N'] + walls:
        for (a, b) in _wall_runs(room, wall):
            if k >= n_wall or used >= budget:
                break
            n_here = max(1, int((b - a) // 1.05))
            for i in range(n_here):
                if k >= n_wall or used >= budget:
                    break
                u = a + (b - a) * (i + .5) / n_here + float(rng.uniform(-.14, .14))
                kind = bag.draw()
                if kind is None:
                    break                                     # every kind has reached its cap: a dressed wall, not a pile
                p = _wall_item(kind, rng, int(rng.integers(0, 9999)), ce)
                x, z, rt = _wall_spot(room, wall, u)
                if not wko.free(x, z, .30):
                    continue
                m = _metrics(p)
                dep = m[2] - m[1]
                # a flat poster cannot be in anybody's way; a shelf or a radiator juts into the room and can be
                if not lko.free(x, z, m[0] if dep > .12 else dep):
                    continue
                p['at'] = [round(x, 2), round(z, 2)]
                p['rot'] = rt
                props.append(p)
                wko.disc(x, z, .34)
                if dep > .12:
                    ko.disc(x, z, dep)
                k += 1
                used += 1
    if wear > .7:                                             # webs in the two far corners
        for sx in (-1, 1):
            p = _wall_item('cobweb', rng, 1, ce)
            p['at'] = [round(sx * (w / 2 - .22), 2), round(d - .26, 2)]
            p['rot'] = 0 if sx < 0 else 1
            props.append(p)
            used += 1

    # ---- one lamp with real geometry, against a wall or in the middle of the ceiling. A room that already has a
    # ceiling light gets a second source at eye level instead, never a second bulb overhead (it blows the image out).
    lamp = v.get('lamp', plan['lamp'])
    lit = str(room.get('light') or 'none') != 'none'
    if lamp in ('pendant_lamp', 'bare_bulb', 'neon_tube') and lit and 'lamp' not in v:
        lamp = 'floor_lamp' if mood in ('lived_in', 'cosy', 'child') else 'wall_sconce'
    if lamp and used < budget:
        if lamp in ('pendant_lamp', 'bare_bulb', 'neon_tube'):
            props.append({'type': lamp, 'at': [0., round(d * .52, 2)], 'ceiling': ce,
                          'light_power': .8 if lit else 1.})
        else:
            spot = None
            for wall in ('N', 'W', 'E'):
                for (a, b) in _wall_runs(room, wall, .55):
                    for t in (.5, .22, .78):
                        x, z, rt = _wall_spot(room, wall, a + (b - a) * t, .30)
                        if ko.free(x, z, .34) and wko.free(x, z, .30):
                            spot = (x, z, rt)
                            break
                    if spot:
                        break
                if spot:
                    break
            if spot:
                props.append({'type': lamp, 'at': [round(spot[0], 2), round(spot[1], 2)], 'rot': spot[2],
                              'light_power': .65 if lit else 1.})
                ko.disc(spot[0], spot[1], .4)
                named['lampe'] = (ox + spot[0], oz + spot[1])
        used += 1

    # ---- floor clutter, only round the edges: the middle of a room is where the acting happens
    fbag = Bag(plan['floor'], rng, cap=3)
    cands = []
    for i in range(max(14, n_floor * 10)):
        side = int(rng.integers(0, 4))
        t = float(rng.uniform(.10, .90))
        band = float(rng.uniform(.40, 1.05))
        if side == 0:
            x, z = -w / 2 + band, d * t
        elif side == 1:
            x, z = w / 2 - band, d * t
        elif side == 2:
            x, z = -w / 2 + w * t, d - band
        else:
            x, z = -w / 2 + w * t, band
        cands.append((x, z))
    placed = 0
    for (x, z) in cands:
        if placed >= n_floor or used >= budget:
            break
        kind = fbag.draw()
        if kind is None:
            break
        p = {'type': kind, 'at': [round(x, 2), round(z, 2)], 'rot': int(rng.integers(0, 4)),
             'seed': int(rng.integers(0, 9999))}
        if kind == 'dust_sheet':
            p.update(width=round(float(rng.uniform(.9, 1.5)), 2), depth=round(float(rng.uniform(.7, 1.0)), 2),
                     height=round(float(rng.uniform(.7, 1.0)), 2))
        if kind == 'cardboard_stack':
            p['count'] = int(rng.integers(2, 4))
        r = _footprint(p)
        if not ko.free(x, z, r + .10):
            continue
        props.append(p)
        ko.disc(x, z, r + .08)
        placed += 1
        used += 1

    # ---- the clues: on a wall the camera will see, or on the floor near a named anchor
    for i in range(n_clue):
        if used >= budget:
            break
        kinds = [c for c in CLUES if c in plan['wall'] or c in plan['floor']] or list(CLUES)
        kind = kinds[int(rng.integers(0, len(kinds)))]
        p = _wall_item(kind, rng, int(rng.integers(0, 9999)), ce)
        if kind in WALL_CLUES:
            runs = _wall_runs(room, 'N', .5)
            wall = 'N'
            if not runs:
                runs, wall = _wall_runs(room, 'W', .5), 'W'
            if not runs:
                continue
            a, b = runs[int(rng.integers(0, len(runs)))]
            x, z, rt = _wall_spot(room, wall, (a + b) / 2)
            p['at'] = [round(x, 2), round(z, 2)]
            p['rot'] = rt
        else:
            spot = None
            for (x, z) in cands:
                if ko.free(x, z, .4):
                    spot = (x, z)
                    break
            if spot is None:
                continue
            p['at'] = [round(spot[0], 2), round(spot[1], 2)]
            p['rot'] = int(rng.integers(0, 4))
            ko.disc(spot[0], spot[1], .4)
        props.append(p)
        named['indice' if i == 0 else 'indice.%d' % (i + 1)] = (ox + p['at'][0], oz + p['at'][1])
        used += 1

    # ---- the shell: wall finish, floor, and the tint of both
    if v.get('shell', True) and room.get('floor') != 'none':
        from .sets import WALLS
        sh = SHELLS[mood]
        wk = v.get('walls') or sh['walls'][int(rng.integers(0, len(sh['walls'])))]
        fam = FLOOR_FAMILY.get(room.get('floor', 'wood'))
        same = [f for f in sh['floor'] if FLOOR_FAMILY.get(f) == fam]
        fk = v.get('floor') or (same[int(rng.integers(0, len(same)))] if same else room.get('floor', 'wood'))
        room['walls'] = wk
        room['floor'] = fk
        base = list(WALLS.get(wk, WALLS['plaster'])[0])
        jitter = [float(rng.uniform(.82, 1.14)) for _ in range(3)]
        room['wall_color'] = [max(0, min(255, int(base[i] * jitter[i]))) for i in range(3)]

    # ---- wear on the surfaces themselves
    if wear > .30:
        room['clean'] = False
        if 'wall_color' not in room:
            from .sets import WALLS
            room['wall_color'] = list(WALLS.get(room.get('walls', 'plaster'), WALLS['plaster'])[0])
        room['wall_color'] = list(_tint(room['wall_color'], wear))
        o['fog'] = round(min(.075, float(o.get('fog', .03)) + .018 * wear), 4)
        o['fill'] = round(max(.22, float(o.get('fill', .5)) * (1 - .18 * wear)), 3)
    o['_variation_count'] = int(o.get('_variation_count', 0)) + used
    return named



def _dress_outdoor(o, v, mood, rng, budget):
    """outdoors there are no walls: litter, debris and one or two lamps along the edges of the walkable ground"""
    plan = MOODS[mood]
    dens = float(v.get('density', 1.))
    props = o.setdefault('props', [])
    anchors = o.get('anchors') or {}
    avoid = []
    for k, a in anchors.items():
        avoid.append([a[0] - 1.1, a[1] - 1.1, a[0] + 1.1, a[1] + 1.1])
    for p in props:
        if isinstance(p.get('at'), list) and len(p['at']) >= 2:
            r = _footprint(p) + .2
            avoid.append([p['at'][0] - r, p['at'][1] - r, p['at'][0] + r, p['at'][1] + r])
    xs = [a[0] for a in anchors.values()] or [0.]
    zs = [a[1] for a in anchors.values()] or [6.]
    area = [min(xs) - 5., max(min(zs) - 1., -2.), max(xs) + 5., max(zs) + 5.]
    litter = ['papers_scattered', 'bottles', 'broken_glass', 'pallet', 'tyre_stack', 'jerrycan', 'cardboard_stack']
    if mood in ('abandoned', 'ransacked', 'haunted'):
        litter += ['wheelie_bin', 'suitcase', 'doll_broken', 'chair_knocked']
    n = max(2, int(round(5 * plan['clutter'] * dens)))
    got = W.scatter([{'type': litter, 'count': min(n, budget), 'area': area, 'min_dist': 1.6, 'avoid': avoid}],
                    int(v.get('seed', 0)) * 3 + 1)
    for p in got:
        p['seed'] = int(abs(hash((p['type'], p['at'][0], p['at'][1]))) % 9999)
        p.pop('size', None)
    props += got
    if mood in ('abandoned', 'haunted', 'ransacked'):
        for k in range(min(2, budget - len(got))):
            x = float(rng.uniform(area[0] + 1, area[2] - 1))
            z = float(rng.uniform(area[1] + 2, area[3] - 2))
            if all(not (a[0] <= x <= a[2] and a[1] <= z <= a[3]) for a in avoid):
                props.append({'type': 'lantern' if k else 'streetlight', 'at': [round(x, 2), round(z, 2)]})
    return {}


def dress(spec, place='', ask=None):
    """Opt-in enrichment of a set spec. `spec` is the expanded spec (what RoomSet will read); `ask` is the spec the
    episode actually wrote, because `places.expand` only forwards a whitelist of keys. Returns `spec` itself when
    there is no "variation" key, so every episode written before this module renders exactly as before."""
    if not isinstance(spec, dict):
        return spec
    v = spec.get('variation') or (ask or {}).get('variation')
    if not v:
        return spec
    if isinstance(v, str):
        v = {'mood': v}
    if not isinstance(v, dict):
        return spec
    out = copy.deepcopy(spec)
    mood = _mood_of(v, place)
    out['_variation'] = {'mood': mood, 'place': place}
    seed = int(v.get('seed', 0)) ^ (zlib.crc32((str(place) + '|' + mood).encode()) & 0xffff)
    rng = np.random.default_rng(seed)
    budget = int(v.get('max_objects', 0) or 0)
    named = {}
    rooms = out.get('rooms') or []
    if rooms:
        for room in rooms:
            w, d = room.get('size', [4, 5])
            cap = budget or min(34, int(8 + w * d * .42))
            ce = float(room.get('height', out.get('height', 2.6)))
            named.update(_dress_room(out, room, v, mood, rng, ce, cap))
    elif out.get('walkable') or 'ground_y' in out:
        # a place with levels (rooftops, cliffs): the ground is metres below the action, so litter dropped at y=0
        # would fall into the void. Dressing a composed place needs its own rules; it is left untouched on purpose.
        out['_variation']['skipped'] = 'lieu à niveaux (compose.py) : habillage extérieur non applicable'
    else:
        named.update(_dress_outdoor(out, v, mood, rng, budget or 9))
    if named:
        out['anchors'] = dict(out.get('anchors') or {}, **{k: tuple(val) for k, val in named.items()})
    return out


# ===================================================================== inventory and registration
def inventory():
    """what this module adds, for the documentation and the capability audit"""
    return {'props': sorted(NEW_PROPS), 'prop_lights': sorted(NEW_PROP_LIGHTS), 'places': sorted(NEW_PLACES),
            'moods': sorted(MOODS), 'clues': sorted(CLUES),
            'props_total_after': len(W.PROPS), 'places_total_after': len(PL.PLACES)}


_REGISTERED = False


def register():
    """additive registration: new keys only, never a replacement of an existing prop or place"""
    global _REGISTERED
    if _REGISTERED:
        return
    for k, fn in NEW_PROPS.items():
        W.PROPS.setdefault(k, fn)
    for k, l in NEW_PROP_LIGHTS.items():
        W.PROP_LIGHTS.setdefault(k, l)
    for k, fn in NEW_PLACES.items():
        PL.PLACES.setdefault(k, fn)
    for k, a in NEW_AMBIENCE.items():
        PL.DEFAULT_AMBIENCE.setdefault(k, a)
    for k, st in NEW_START.items():
        PL.START.setdefault(k, st)
    _REGISTERED = True


register()
