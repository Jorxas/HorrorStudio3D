"""PIXEL 3D art direction v2 -- EXPERIMENTAL, OPT-IN ONLY.

The shipped PIXEL 3D look ("ancien style") stays the default and is never touched by this module. A project turns
this one on explicitly with the episode key `"art"` (see docs/ART_PIXEL3D_V2.md); nothing activates it on its own,
no heuristic, no director prompt, no fallback. With `"art"` absent the module is inert: `active()` returns None and
every call site keeps its original code path, bit for bit (tools/regress.py, tools/regress_v2.py).

What it redesigns, all behind that one key:
- `figure()`   richer voxel bodies: tapered torso, deltoids, neck, two-piece limbs, cuffs/collar/belt/hem, soled
               shoes, palm+thumb hands, multi-layer hair with per-strand sway driven by the gait;
- `face_hd()`  a 48x48 parametric face (the stock one is 24x24 hand-drawn): brows, lids, iris + pupil + catchlight,
               nose with its shadow, lips, cheeks, per-expression deformation for every name of assets.FACE_KINDS;
- `decor()`    skirting board, dado rail and cornice found on the walls of a set, cached per set;
- `grade()`    cinematic finish: halation, filmic curve, split tone, vignette, and a finer palette quantisation
               (18 values / 7 saturations / 12 deg hue steps on an 8x8 ordered dither instead of 12 / 5 / 20 on 4x4).

Determinism is kept: no wall clock, no unseeded randomness. Everything is a function of the frame's own data.
This is a first increment put up for a human visual judgement; it is not declared the final style.
"""
import math, functools, zlib
import numpy as np
from PIL import Image, ImageDraw
from . import r3d
from .r3d import C, orient, M_FABRIC, M_WOODV, M_PLASTER, M_CLEAN, M_DOOR, M_METAL
from . import assets as A
from . import poses as P
from ...acting import rig

# --------------------------------------------------------------------------- presets / activation
PRESETS = {
    # the only full preset of this first increment; `detail` scales the optional geometry (0 = none, 1 = all)
    'voxel_hd': dict(figure=True, face=True, decor=True, grade=True, detail=1.0, sway=1.0),
    # same body and face work, stock image finish: useful to judge the geometry alone
    'voxel_hd_flat': dict(figure=True, face=True, decor=True, grade=False, detail=1.0, sway=1.0),
    # image finish alone, stock bodies: useful to judge the grade alone
    'grade_only': dict(figure=False, face=False, decor=False, grade=True, detail=0.0, sway=0.0),
}
FEATURES = ('figure', 'face', 'decor', 'grade')
_STATE = None


def register(name, **spec):
    """an extension adds its own art preset (registry, not if/elif -- see AGENTS.md)"""
    PRESETS[name] = dict(PRESETS['voxel_hd'], **spec)
    return PRESETS[name]


def configure(spec):
    """`spec` is the episode's `art` key: None / False (off), a preset name, or {"style": name, <overrides>}.
    Returns the resolved preset or None. Called once per engine, exactly like r3d.configure(aspect)."""
    global _STATE
    _STATE = None
    if not spec: return None
    if isinstance(spec, str): name, over = spec, {}
    elif isinstance(spec, dict):
        name = spec.get('style') or spec.get('preset') or 'voxel_hd'
        over = {k: v for k, v in spec.items() if k not in ('style', 'preset')}
    else: return None
    if name not in PRESETS: return None
    st = dict(PRESETS[name], **{k: v for k, v in over.items() if k in PRESETS[name]})
    st['name'] = name
    _STATE = st
    return st


def use(state):
    """re-assert a resolved preset before rendering. Several engines can live in the same process (tools, the web
    server, the catalogue): each one owns its state and sets it back on every frame instead of trusting a global."""
    global _STATE
    _STATE = state
    return state


def active(): return _STATE


# --------------------------------------------------------------------------- overlaps with the V2 expressive look
# Lot 3 ("pixel3d-expressivity", already integrated) redesigned the same two things from the character's side:
# the 48x48 face (look "face_detail": "hd") and the body details (look "hair2" / "detail" / "accent"). Both are
# opt-in, this art direction is opt-in, and nothing stops an episode from asking for both at once. Git merges
# those two code paths without a single conflict, so nothing would have warned anybody. These notices do.
# They state a scope rule, not an artistic verdict: which of the two becomes the style is the owner's call.
_V2_LOOK_KEYS = ('hair2', 'detail', 'accent')


def notices(cast):
    """French messages for the places where this art direction and the V2 expressive look overlap.

    `cast` is the resolved cast (acting.cast.resolve_cast: character id -> look). Returns the messages, empty
    when the art direction is off or when no character asks for the V2 keys. The caller prints them on the
    render log and keeps them, exactly like lighting._warn does. Pure: it reads, it decides nothing."""
    out = []
    if not _STATE: return out
    nm = _STATE.get('name') or 'art v2'
    if on('face'):
        who = sorted(cid for cid, lk in (cast or {}).items() if (lk or {}).get('face_detail') == 'hd')
        if who:
            out.append(f"visage : {', '.join(who)} demande « face_detail: hd » et l" + "'" + f"épisode demande la "
                       f"direction artistique « {nm} ». La clé du personnage l" + "'" + f"emporte (portée la plus "
                       f"précise) : c" + "'" + f"est le visage expressif du lot 3 qui est rendu, pas celui de "
                       f"« {nm} ». Le choix final du style reste humain.")
    if on('figure'):
        who = sorted(cid for cid, lk in (cast or {}).items() if any((lk or {}).get(k) for k in _V2_LOOK_KEYS))
        if who:
            out.append(f"silhouette : la direction artistique « {nm} » redessine le corps entier et ne porte pas "
                       f"les clés hair2 / detail / accent de {', '.join(who)} : elles ne sont pas rendues.")
    return out
def on(feature): return bool(_STATE) and bool(_STATE.get(feature))
def detail(): return float(_STATE.get('detail', 1.)) if _STATE else 0.


# --------------------------------------------------------------------------- colour helpers
def _sh(c, f): return tuple(max(0, min(255, int(round(v * f)))) for v in tuple(c)[:3])
def _mix(a, b, t): return tuple(max(0, min(255, int(round(a[i] * (1 - t) + b[i] * t)))) for i in range(3))


# --------------------------------------------------------------------------- 48x48 parametric face
# per expression: brows (inner dy, outer dy, px; negative = raised), eye opening 0..1, eye shape, pupil radius,
# mouth curve (-1 frown .. +1 smile), mouth opening 0..1, mouth width (px), and free tags.
_DEF = dict(brow=(0, 0), eye=.60, shape='round', pupil=2, curve=0., open=0., width=10, tags=())
EXPR = {
    'neutral':     dict(),
    'talk':        dict(open=.5, width=9),
    'urgent':      dict(brow=(-2, 1), eye=.95, open=.55, width=11, tags=('sweat',)),
    'happy':       dict(brow=(-1, -1), eye=.5, curve=.8, tags=('blush',)),
    'double':      dict(eye=.7, curve=.2),
    'grin':        dict(brow=(-1, 0), eye=.45, curve=1., open=.35, width=13, tags=('teeth',)),
    'scared':      dict(brow=(-3, 2), eye=1., pupil=1, curve=-.7, open=.6, width=8, tags=('sweat', 'pale')),
    'closed':      dict(eye=0., shape='line'),
    'sad':         dict(brow=(-3, 2), eye=.45, curve=-.8, tags=('shade',)),
    'smile_sad':   dict(brow=(-3, 1), eye=.45, curve=.4, tags=('shade',)),
    'creature':    dict(eye=1., shape='glow', pupil=0, curve=-.4, open=.7, width=14, tags=('teeth', 'pale')),
    'joy':         dict(brow=(-2, -2), eye=.2, shape='arc', curve=1., open=.45, width=13, tags=('blush', 'teeth')),
    'laugh':       dict(brow=(-2, -2), eye=.15, shape='arc', curve=1., open=.9, width=14, tags=('blush', 'teeth', 'tongue')),
    'excited':     dict(brow=(-3, -2), eye=1., pupil=3, curve=.9, open=.5, width=12, tags=('blush', 'star')),
    'love':        dict(eye=.9, shape='heart', curve=.8, tags=('blush',)),
    'wink':        dict(brow=(-1, -1), eye=.6, curve=.8, tags=('wink', 'blush')),
    'silly':       dict(brow=(-1, -2), eye=.5, curve=.6, open=.5, width=11, tags=('tongue',)),
    'smirk':       dict(brow=(-1, 1), eye=.45, shape='narrow', curve=.5, tags=('asym',)),
    'proud':       dict(brow=(-2, -1), eye=.4, shape='narrow', curve=.6, tags=('chin_up',)),
    'shy':         dict(brow=(-2, 1), eye=.35, curve=.3, tags=('blush', 'look_down')),
    'calm':        dict(brow=(-1, 0), eye=.35, curve=.25),
    'surprised':   dict(brow=(-4, -3), eye=1., pupil=2, open=.7, width=7, tags=('round_mouth',)),
    'shocked':     dict(brow=(-4, -3), eye=1., pupil=1, open=.95, width=9, tags=('round_mouth', 'pale', 'sweat')),
    'nervous':     dict(brow=(-2, 2), eye=.75, pupil=1, curve=-.4, width=9, tags=('sweat', 'squiggle')),
    'crying':      dict(brow=(-3, 2), eye=.25, shape='arc_down', curve=-.9, open=.5, width=11, tags=('tear',)),
    'angry':       dict(brow=(2, -3), eye=.55, shape='narrow', curve=-.8, width=11),
    'furious':     dict(brow=(3, -4), eye=.7, shape='narrow', pupil=1, curve=-1., open=.5, width=13, tags=('teeth', 'red')),
    'disgusted':   dict(brow=(1, -2), eye=.35, shape='narrow', curve=-.6, tags=('asym', 'green')),
    'confused':    dict(brow=(-3, 1), eye=.6, curve=-.2, tags=('asym_brow',)),
    'suspicious':  dict(brow=(1, -1), eye=.3, shape='narrow', curve=-.3, tags=('look_side',)),
    'thinking':    dict(brow=(-2, 1), eye=.5, curve=-.1, tags=('look_up',)),
    'bored':       dict(brow=(1, 0), eye=.3, shape='narrow', curve=-.3, tags=('look_side', 'shade')),
    'tired':       dict(brow=(-1, 2), eye=.25, shape='narrow', curve=-.4, tags=('shade', 'eyebags')),
    'sleeping':    dict(eye=0., shape='arc_down', curve=.1, open=.3, width=6, tags=('zzz',)),
    'determined':  dict(brow=(2, -2), eye=.6, curve=-.1, width=12, tags=('jawset',)),
    'evil':        dict(brow=(2, -3), eye=.5, shape='narrow', curve=.8, width=13, tags=('teeth', 'red', 'asym')),
    'cool':        dict(brow=(-1, 0), eye=.5, shape='narrow', curve=.4, tags=('asym',)),
    'pain':        dict(brow=(-3, 3), eye=.1, shape='arc_down', curve=-.9, open=.6, width=11, tags=('teeth', 'sweat')),
    'dizzy':       dict(brow=(-2, 0), eye=.9, shape='spiral', curve=-.2, open=.4, width=9, tags=('squiggle',)),
    'ko':          dict(eye=.9, shape='x', curve=-.5, open=.5, width=9, tags=('pale',)),
    'skull':       dict(eye=1., shape='hollow', pupil=0, curve=0., width=15, tags=('teeth', 'bone')),
    'robot':       dict(eye=.8, shape='glow', pupil=0, curve=0., width=12, tags=('plate',)),
    'alien':       dict(eye=1., shape='almond', pupil=0, curve=-.1, width=7, tags=('green',)),
}


def _expr(kind):
    e = dict(_DEF); e.update(EXPR.get(kind, {})); return e


def _base_skin(skin, pale, green):
    """48x48 skin plate: vertical light, darker temples and jaw, cheekbone lift"""
    yy, xx = np.mgrid[0:48, 0:48].astype(np.float32)
    cx = (xx - 23.5) / 23.5
    # the falloffs are gentler and the whole plate is lifted: stacked with the vignette and the grade, the first
    # increment's plate made a close-up read as a dark mask (docs/ART_PIXEL3D_V2.md, defect 1).
    f = 1. - .19 * np.clip((np.abs(cx) - .46) / .54, 0, 1)                     # temples and jaw sides fall off
    f *= 1. + .10 * np.clip(1 - yy / 17., 0, 1)                                # forehead catches the light
    f *= 1. - .09 * np.clip((yy - 38) / 10., 0, 1)                             # under the chin
    f *= 1. + .06 * np.exp(-(((xx - 12) / 7.) ** 2 + ((yy - 28) / 5.) ** 2))   # cheekbones
    f *= 1. + .06 * np.exp(-(((xx - 35) / 7.) ** 2 + ((yy - 28) / 5.) ** 2))
    f *= 1.09                                                                  # overall lift of the face plate
    col = np.array(skin, np.float32)
    if pale: col = col * .80 + np.array([38, 44, 48], np.float32)
    if green: col = col * .55 + np.array([70, 130, 70], np.float32)
    a = np.clip(col[None, None] * f[..., None], 0, 255).astype(np.uint8)
    return np.dstack([a, np.full((48, 48), 255, np.uint8)])


def _eye(d, cx, cy, e, skin, iris, dark, white, gx, gy, closed):
    """one eye: lids, sclera, iris, pupil, catchlight"""
    h = max(0, int(round(e['eye'] * 5)))
    shape = e['shape']
    if closed or h == 0 or shape in ('line', 'arc', 'arc_down'):
        y = cy + (1 if shape == 'arc_down' else 0)
        if shape == 'arc':                                   # happy closed eye, curved up
            d.rectangle([cx - 4, y, cx + 4, y], fill=dark); d.point([(cx - 5, y - 1), (cx + 5, y - 1)], fill=dark)
        elif shape == 'arc_down':
            d.rectangle([cx - 4, y, cx + 4, y], fill=dark); d.point([(cx - 5, y + 1), (cx + 5, y + 1)], fill=dark)
        else:
            d.rectangle([cx - 4, y, cx + 4, y], fill=dark)
            d.rectangle([cx - 4, y + 1, cx + 4, y + 1], fill=_sh(skin, .82))
        return
    if shape == 'x':
        for i in range(-3, 4): d.point([(cx + i, cy + i), (cx + i, cy - i)], fill=dark)
        return
    if shape == 'hollow':
        d.ellipse([cx - 5, cy - 4, cx + 5, cy + 4], fill=(14, 12, 14)); return
    if shape == 'glow':
        d.rectangle([cx - 5, cy - h, cx + 5, cy + h], fill=iris)
        d.rectangle([cx - 3, cy - h + 1, cx + 3, cy + h - 1], fill=_mix(iris, (255, 255, 255), .55)); return
    if shape == 'heart':
        for (dx, dy) in ((-2, -2), (-1, -3), (0, -2), (1, -3), (2, -2), (-2, -1), (-1, -1), (0, -1), (1, -1),
                         (2, -1), (-1, 0), (0, 0), (1, 0), (0, 1)):
            d.point((cx + dx, cy + dy), fill=(236, 54, 92))
        return
    top = cy - h; bot = cy + (h if shape != 'narrow' else max(1, h - 2))
    if shape == 'almond':
        d.polygon([(cx - 6, cy), (cx, top - 1), (cx + 6, cy), (cx, bot + 1)], fill=(16, 14, 20)); return
    d.ellipse([cx - 5, top, cx + 5, bot], fill=white)
    if shape == 'spiral':
        for (dx, dy) in ((0, 0), (1, 0), (1, 1), (0, 2), (-2, 1), (-2, -1), (0, -2), (3, -1)): d.point((cx + dx, cy + dy), fill=dark)
        return
    # iris narrower than the lid slit: a 7 px disc filled the whole opening and the eye read as a pale ring with
    # white only in the corners. 5 px wide leaves 3 px of sclera on each side, so the eye keeps a white / iris /
    # pupil reading at this scale, and the iris is lightened while the pupil stays the only truly dark value.
    irx = 2
    ex = cx + gx * 2; ey_ = int(np.clip(cy + gy * 2, top + 1, bot - 1))
    iry = min(3, max(1, (bot - top) // 2))
    iy0 = max(top + 1, ey_ - iry); iy1 = min(bot - 1, ey_ + iry)       # a half-closed lid crops the iris,
    if iy1 < iy0: iy0 = iy1 = (top + bot) // 2                         # it does not smear across the whole eye
    d.ellipse([ex - irx, iy0, ex + irx, iy1], fill=_sh(iris, .78))              # limbus, the darker iris rim
    if iy1 - iy0 >= 3:
        d.ellipse([ex - irx + 1, iy0 + 1, ex + irx - 1, iy1 - 1], fill=_mix(iris, (255, 255, 255), .22))
    pr = 1 if e['pupil'] >= 2 else 0                                           # a round pupil, never a slit
    pry = min(pr, max(0, (iy1 - iy0) // 2))
    if e['pupil'] >= 1: d.ellipse([ex - pr, ey_ - pry, ex + pr, ey_ + pry], fill=dark)
    if iy1 > iy0: d.point((ex - 2, iy0), fill=(252, 250, 246))         # catchlight, clear of the pupil
    d.rectangle([cx - 5, top, cx + 5, top], fill=_sh(skin, .78))       # upper lid line, lighter than before
    d.point((cx - 5 if cx < 23 else cx + 5, top), fill=_sh(skin, .58))    # outer lash corner keeps the definition
    if bot + 1 <= cy + 6: d.rectangle([cx - 4, bot + 1, cx + 4, bot + 1], fill=_sh(skin, 1.08))   # lower lid catch
    if 'eyebags' in e['tags']: d.rectangle([cx - 4, bot + 2, cx + 4, bot + 2], fill=_sh(skin, .74))


def _brow(d, cx, by, inner_dy, outer_dy, side, hair):
    """one eyebrow, 3 steps from the inner to the outer end"""
    s = 1 if side > 0 else -1
    for i, dx in enumerate((-4, -1, 2)):
        t = i / 2.
        y = by + int(round(inner_dy * (1 - t) + outer_dy * t))
        x0 = cx + s * dx
        d.rectangle([min(x0, x0 + s * 3), y, max(x0, x0 + s * 3), y + 1], fill=hair)


def _mouth(d, cx, my, e, skin, dark, lip):
    cur = e['curve']; op = e['open']; w = int(e['width']) // 2
    if 'round_mouth' in e['tags']:
        r = 2 + int(op * 3)
        d.ellipse([cx - r, my - r, cx + r, my + r], fill=(58, 24, 28))
        d.ellipse([cx - r + 1, my - r + 1, cx + r - 1, my + r - 1], fill=(34, 14, 18)); return
    if op > .05:
        h = max(1, int(round(op * 6)))
        d.rounded_rectangle([cx - w, my - h // 2, cx + w, my + h - h // 2], radius=1, fill=(58, 24, 28))
        if 'teeth' in e['tags']: d.rectangle([cx - w + 1, my - h // 2, cx + w - 1, my - h // 2], fill=(238, 234, 226))
        if 'tongue' in e['tags']: d.rectangle([cx - 2, my + h - h // 2 - 1, cx + 2, my + h - h // 2], fill=(206, 86, 104))
    if 'squiggle' in e['tags']:
        for i in range(-w, w + 1): d.point((cx + i, my + (i % 2)), fill=lip)
        return
    for i in range(-w, w + 1):
        t = i / max(1., w)
        y = my + int(round(-cur * 2.4 * (1 - t * t) + (1.2 if cur < 0 else 0) * abs(t)))
        if 'asym' in e['tags'] and i < 0: y = my
        d.point((cx + i, y), fill=lip)
        if op <= .05: d.point((cx + i, y + 1), fill=_sh(skin, .80))


def _nose(d, skin):
    d.rectangle([22, 24, 25, 29], fill=_sh(skin, 1.05))
    d.rectangle([21, 29, 26, 30], fill=_sh(skin, .80))
    d.point([(21, 28), (26, 28)], fill=_sh(skin, .68))


@functools.lru_cache(maxsize=2048)
def face_hd(kind='neutral', mouth=0., skin=A.SKIN, hair=A.HAIR, gaze=None, glasses=None, beard=None,
            bald=False, blink=False, eyes=None):
    """48x48 face for the art v2 head. Same inputs as assets.face_tex, four times the pixels."""
    e = _expr(kind if kind in EXPR else 'neutral')
    if mouth > 0: e = dict(e, open=max(e['open'], .15 + .55 * float(mouth)))
    tags = e['tags']
    im = Image.fromarray(_base_skin(skin, 'pale' in tags, 'green' in tags)); d = ImageDraw.Draw(im)
    dark = (18, 14, 18); white = (238, 234, 226); lip = (150, 40, 44) if 'red' in tags else (122, 58, 58)
    iris = tuple(eyes) if eyes else ((226, 60, 48) if 'red' in tags else (92, 126, 150))
    gx, gy = A.GAZE.get(gaze, (0, 0))
    if 'look_down' in tags: gy = 1
    if 'look_up' in tags: gy = -1
    if 'look_side' in tags: gx = 1
    if 'shade' in tags: d.rectangle([2, 10, 45, 20], fill=_sh(skin, .88))   # a shadow over the eyes, for the low moods
    ey, my = (20, 33) if 'chin_up' in tags else (22, 35)
    _nose(d, skin)
    for side, cx in ((-1, 14), (1, 33)):
        _eye(d, cx, ey, e, skin, iris, dark, white, gx, gy, blink or ('wink' in tags and side > 0))
    if 'bone' not in tags and 'plate' not in tags:
        bi, bo = e['brow']
        bcol = _sh(skin, .55) if bald else tuple(hair)
        for side, cx in ((-1, 14), (1, 33)):
            ii, oo = (bo, bi) if ('asym_brow' in tags and side > 0) else (bi, bo)
            _brow(d, cx, ey - 7, ii, oo, side, bcol)
    _mouth(d, 23, my, e, skin, dark, lip)
    if 'blush' in tags:
        for cx in (9, 38): d.rectangle([cx - 3, 29, cx + 3, 31], fill=_mix(skin, (236, 96, 110), .38))
    if 'tear' in tags:
        for cx in (14, 33): d.rectangle([cx + 3, ey + 4, cx + 4, ey + 9], fill=(150, 206, 238))
    if 'sweat' in tags:
        d.rectangle([39, 9, 41, 13], fill=(170, 216, 240)); d.point([(40, 14)], fill=(170, 216, 240))
    if 'star' in tags:
        for cx in (6, 41): d.point([(cx, 18), (cx - 1, 19), (cx + 1, 19), (cx, 20)], fill=(250, 232, 120))
    if 'zzz' in tags:
        d.rectangle([37, 6, 42, 6], fill=white); d.rectangle([37, 10, 42, 10], fill=white)
        for i in range(4): d.point((41 - i, 7 + i), fill=white)
    if 'jawset' in tags:
        d.rectangle([7, 38, 11, 41], fill=_sh(skin, .93)); d.rectangle([36, 38, 40, 41], fill=_sh(skin, .93))
    if 'plate' in tags:
        d.rectangle([4, 4, 43, 5], fill=(120, 126, 136)); d.rectangle([4, 42, 43, 43], fill=(120, 126, 136))
        d.rectangle([23, 4, 24, 43], fill=(100, 106, 116))
    # beard / stubble, scaled from the 24x24 convention
    if beard in (True, 'full', 'beard'):
        d.rectangle([6, 32, 41, 47], fill=hair); d.rectangle([4, 26, 9, 33], fill=hair); d.rectangle([38, 26, 43, 33], fill=hair)
        d.rectangle([16, my - 3, 31, my + 3], fill=_sh(skin, .95))
        _mouth(d, 23, my, e, skin, dark, lip)
    elif beard == 'mustache':
        d.rectangle([14, my - 5, 32, my - 3], fill=hair)
    elif beard == 'stubble':
        for (px, py) in ((10, 36), (16, 40), (22, 42), (28, 40), (34, 36), (12, 42), (32, 42), (20, 38), (26, 38), (14, 34), (33, 34)):
            d.rectangle([px, py, px + 1, py + 1], fill=_sh(skin, .70))
    # hairline: the volume is voxels, the texture only closes the top of the forehead
    if not bald:
        d.rectangle([0, 0, 47, 7], fill=hair)
        for x, h in ((0, 15), (6, 11), (12, 13), (18, 9), (24, 13), (30, 9), (36, 13), (42, 15)):
            d.rectangle([x, 7, x + 5, h], fill=hair)
        d.rectangle([0, 0, 3, 47], fill=hair); d.rectangle([44, 0, 47, 47], fill=hair)
        d.rectangle([0, 0, 47, 1], fill=_sh(hair, 1.45))                  # top highlight
    if glasses in (True, 'glasses', 'round'):
        fr = (40, 38, 48)
        for cx in (14, 33): d.ellipse([cx - 7, ey - 6, cx + 7, ey + 6], outline=fr, width=2)
        d.rectangle([21, ey - 1, 26, ey], fill=fr)
    elif glasses in ('sun', 'sunglasses'):
        for cx in (14, 33): d.rounded_rectangle([cx - 7, ey - 5, cx + 7, ey + 5], radius=2, fill=(12, 12, 16))
        d.rectangle([21, ey - 1, 26, ey], fill=(12, 12, 16))
        d.rectangle([9, ey - 3, 12, ey - 2], fill=(190, 204, 226)); d.rectangle([28, ey - 3, 31, ey - 2], fill=(190, 204, 226))
    return np.array(im)


# --------------------------------------------------------------------------- multi-layer hair
def hair_layers(hair, style, hat, k, sway=0.):
    """hair as voxel shells in the head frame (origin = head centre): scalp, crown highlight, jagged fringe,
    side locks and a back mass, plus the strands of the style. `sway` (metres) is the secondary motion."""
    bx = []; style = style or 'short'
    if style == 'bald': return bx
    hidden_top = bool(hat) and hat != 'none'
    d0 = _sh(hair, .78); d1 = tuple(hair); d2 = _sh(hair, 1.30)
    if not hidden_top:
        bx.append(C((0, .205, -.01), (.42, .07, .40), d0, **k))                    # scalp shell
        bx.append(C((0, .245, -.02), (.37, .05, .35), d1, **k))                    # crown
        bx.append(C((0, .272, -.03), (.26, .03, .24), d2, **k))                    # top highlight
        for i, (dx, h, dz) in enumerate(((-.155, .055, .02), (-.075, .085, .035), (.005, .065, .03),
                                         (.085, .090, .025), (.160, .050, .015))):
            bx.append(C((dx + sway * .35, .195 - h / 2 + .03, .135 + dz * .6), (.075, h + .07, .055), d1 if i % 2 else d2, **k))   # jagged fringe (behind the face plate: no shadow on the eyes)
    # the back of the head: shells at three shades instead of one flat dark plate. Seen from behind or three
    # quarters back the first increment read as a single dark block (docs/ART_PIXEL3D_V2.md, defect 2). Nothing
    # here goes deeper than the old plate's rear face (z = -.2325), so the silhouette the cinematographer was
    # tuned on does not move.
    bx.append(C((0, .145, -.180), (.39, .15, .085), d1, **k))                      # upper occiput, catches light
    bx.append(C((0, .195, -.150), (.34, .07, .09), d2, **k))                       # crown wrap highlight
    bx.append(C((0, .025, -.198), (.40, .26, .065), d0, **k))                      # mid mass
    bx.append(C((0, -.120, -.185), (.35, .12, .075), _sh(hair, .64), **k))         # nape, in shadow
    if _STATE and detail() > .3:                                                   # strand breaks across the mass
        for i, dx in enumerate((-.135, -.045, .045, .135)):
            bx.append(C((dx, .03, -.222), (.05, .33, .022), d2 if i % 2 else d1, **k))
    for s in (-1, 1):
        bx.append(C((s * .203, .055, -.045), (.036, .33, .30), d1, **k))           # side shells
        bx.append(C((s * .196, .085, -.150), (.045, .20, .075), d2, **k))          # rear corner of the skull
        bx.append(C((s * .215, -.09, .02 + sway * .25 * s), (.04, .12, .09), d0, **k))   # temple locks
    if style == 'long':
        for i, (dy, hh, dz) in enumerate(((-.17, .30, -.22), (-.42, .26, -.21), (-.64, .20, -.19))):
            bx.append(C((sway * (.25 + .25 * i), dy, dz + sway * .3), (.44 - i * .04, hh, .09), d1 if i % 2 == 0 else d0, **k))
        for s in (-1, 1):
            bx.append(C((s * .205, -.18 + sway * .2 * s, -.02), (.045, .46, .30), d1, **k))
            bx.append(C((s * .205, -.42 + sway * .4 * s, -.05), (.04, .22, .22), d0, **k))
    elif style == 'ponytail':
        bx.append(C((0, .07, -.27), (.11, .22, .07), d2, **k))                      # gathered base, lit
        bx.append(C((0, .19, -.25), (.13, .05, .07), (200, 60, 80), **k))
        for i in range(3):                                                          # the tail trails behind
            bx.append(C((sway * (.5 + i * .6), .02 - i * .16, -.295 - i * .03), (.11 - i * .015, .17, .085), d2 if i % 2 == 0 else d1, **k))
            bx.append(C((sway * (.5 + i * .6) - .03, .02 - i * .16, -.325 - i * .03), (.035, .15, .028), _sh(hair, 1.55), **k))   # lit edge, so the tail reads against the back
    elif style == 'bun' and not hidden_top:
        bx.append(C((0, .315, -.09), (.19, .17, .17), d1, **k)); bx.append(C((0, .345, -.09), (.12, .09, .11), d2, **k))
    elif style == 'spiky' and not hidden_top:
        for i, (dx, dz, h) in enumerate(((-.15, .04, .13), (-.06, .11, .17), (.05, .02, .15), (.15, .09, .12),
                                         (0, -.13, .14), (-.10, -.06, .10), (.11, -.09, .11))):
            bx.append(C((dx + sway * .3, .255 + h / 2, dz), (.065, h, .065), d1 if i % 2 else d2, **k))
    elif style == 'curly':
        if not hidden_top:
            for (dx, dy, dz) in ((-.17, .25, .04), (-.05, .285, .10), (.08, .26, .02), (.18, .24, .08),
                                 (0, .27, -.12), (-.12, .24, -.10), (.13, .25, -.11)):
                bx.append(C((dx, dy, dz), (.16, .13, .16), d1, **k))
        for s in (-1, 1):
            for j, dy in enumerate((.06, -.10, -.24)):
                bx.append(C((s * (.235 + .01 * (j % 2)), dy, -.02 + sway * .2 * s), (.13, .14, .17), d1 if j % 2 else d0, **k))
    else:                                                                           # short
        if not hidden_top: bx.append(C((0, .225, -.11), (.40, .06, .20), d2, **k))
        bx.append(C((0, -.13, -.195), (.33, .10, .06), d0, **k))                    # nape
    return bx


# --------------------------------------------------------------------------- the body
_SHOE = (30, 28, 32)
_TORSO_OUTFITS = ('hoodie', 'tshirt', 'shirt', 'suit', 'coat', 'dress', 'uniform', 'lab_coat', 'apron')


def _torso_v2(yb, outfit, hood, skin, shirt, tie, cape, backpack, k, det):
    """tapered torso in the pelvis frame: hips, waist, chest, yoke, deltoids, and the garment's own details"""
    bx = []
    low = skin if outfit == 'dress' else None
    bx.append(C((0, -.02, 0), (.42, .18, .24), low or hood, mat=M_FABRIC, **k))                   # hips
    if outfit not in _TORSO_OUTFITS:                     # armor, robe, spacesuit...: keep the original builder
        bx += P.torso(0., 0., 1, yb, outfit, hood, skin, k, tie=tie, shirt=shirt)
        if det > .3: bx.append(C((0, yb + 1.455, -.02), (.24, .11, .19), _sh(skin, .98), **k))
        if cape: bx.append(C((0, yb + .92, -.20), (.54, 1.05, .03), tuple(cape), mat=M_FABRIC, **k))
        return bx
    bx.append(C((0, yb + .96, 0), (.40, .26, .23), hood, mat=M_FABRIC, **k))                      # waist (narrow)
    bx.append(C((0, yb + 1.19, .005), (.47, .24, .26), hood, mat=M_FABRIC, **k))                  # chest (wide)
    bx.append(C((0, yb + 1.34, -.01), (.46, .10, .25), _sh(hood, .94), mat=M_FABRIC, **k))        # yoke
    if det > .3:
        for s in (-1, 1): bx.append(C((s * .232, yb + 1.30, 0), (.085, .17, .22), _sh(hood, 1.06), mat=M_FABRIC, **k))   # deltoid caps
        bx.append(C((0, yb + 1.455, -.02), (.24, .11, .19), _sh(skin, .98), **k))                 # neck
        bx.append(C((0, yb + 1.41, .01), (.30, .05, .24), _sh(hood, .80), mat=M_FABRIC, **k))     # collar
    if shirt: bx.append(C((0, yb + 1.16, .133), (.20, .46, .012), tuple(shirt), **k))
    if tie:
        bx.append(C((0, yb + 1.30, .139), (.07, .09, .012), tuple(tie), **k))
        bx.append(C((0, yb + 1.12, .139), (.09, .28, .012), tuple(tie), **k))
    if det > .3:
        if outfit == 'hoodie':
            bx.append(C((0, yb + 1.00, .132), (.30, .14, .013), _sh(hood, .74), **k))             # kangaroo pocket
            for sd in (-1, 1): bx.append(C((sd * .05, yb + 1.33, .136), (.022, .15, .014), (200, 198, 188), **k))   # drawstrings
            bx.append(C((0, yb + 1.44, -.10), (.42, .11, .17), _sh(hood, .86), mat=M_FABRIC, **k))                  # hood bunched
            bx.append(C((0, yb + .83, 0), (.44, .07, .25), _sh(hood, .80), mat=M_FABRIC, **k))                      # hem band
        elif outfit in ('shirt', 'suit', 'uniform', 'lab_coat'):
            bx.append(C((0, yb + 1.18, .134), (.015, .40, .012), _sh(hood, .72), **k))            # button placket
            for j in range(3): bx.append(C((0, yb + 1.05 + j * .12, .141), (.026, .026, .008), (226, 222, 212), **k))
            if outfit in ('suit', 'uniform'):
                for sd in (-1, 1): bx.append(C((sd * .12, yb + 1.30, .130), (.14, .20, .016), _sh(hood, .88), mat=M_FABRIC, **k))   # lapels
            bx.append(C((0, yb + .88, 0), (.43, .05, .25), _sh(hood, .76), mat=M_FABRIC, **k))    # belt line
        elif outfit == 'dress':
            bx.append(C((0, yb + .62, 0), (.52, .42, .34), hood, mat=M_FABRIC, **k))              # skirt
            bx.append(C((0, yb + .42, 0), (.56, .07, .38), _sh(hood, .86), mat=M_FABRIC, **k))
        elif outfit == 'coat':
            bx.append(C((0, yb + .80, 0), (.50, .46, .28), hood, mat=M_FABRIC, **k))              # long panels
            bx.append(C((0, yb + 1.14, .140), (.016, .50, .012), _sh(hood, .70), **k))
    if backpack and outfit in ('hoodie', 'tshirt', 'coat', 'suit'):
        pk = (36, 40, 44)
        bx.append(C((0, yb + 1.14, -.21), (.36, .46, .14), pk, mat=M_FABRIC, **k))
        if det > .3:
            bx.append(C((0, yb + 1.30, -.285), (.24, .14, .04), _sh(pk, 1.18), mat=M_FABRIC, **k))
            for s in (-1, 1): bx.append(C((s * .16, yb + 1.22, .11), (.05, .40, .035), _sh(pk, .9), mat=M_FABRIC, **k))   # straps
    if cape: bx.append(C((0, yb + .92, -.20), (.54, 1.05, .03), tuple(cape), mat=M_FABRIC, **k))
    return bx


def figure(sample, look, face, k=None, spec=None, lights=None):
    """art v2 body for one frame. Same contract as rigfig.build: -> (boxes, skeleton)."""
    from .rigfig import look_kw, _scaled
    k = k or {}; L = look_kw(look, spec); s = L['scale']; det = detail()
    sk = rig.solve(sample['rig'])
    Rw = rig.rot_y(sample['heading']); base = np.array([sample['x'], float(sample.get('y', 0.)), sample['z']], np.float32)
    out = []

    def emit(boxes, frame):
        R, o = frame
        out.extend(orient(_scaled(boxes, s), 0., Rw @ (np.asarray(o, np.float32) * s) + base, Rw @ R))

    hood, jeans, skin, hair = L['hood'], L['jeans'], L['skin'], L['hair']; outfit = L['outfit']
    low = skin if outfit == 'dress' else jeans
    p = sample.get('rig', {}) or {}
    swf = float(_STATE.get('sway', 1.)) if _STATE else 0.
    sway = .022 * swf * math.sin(float(p.get('phase', 0.)) * .5 + float(p.get('t', 0.)) * 1.7) * (.35 + .65 * float(p.get('gait', 0.)))
    # legs: thigh in two volumes, calf shaped, trouser cuff, soled shoe
    for tag in 'LR':
        emit([C((0, -rig.THIGH * .32, 0), (.195, rig.THIGH * .64 + .08, .225), low, mat=M_FABRIC, **k),
              C((0, -rig.THIGH * .82, 0), (.175, rig.THIGH * .46, .205), low, mat=M_FABRIC, **k)], sk.frames['thigh' + tag])
        shn = [C((0, -rig.SHIN * .30, -.01), (.175, rig.SHIN * .62 + .06, .205), low, mat=M_FABRIC, **k),
               C((0, -rig.SHIN * .80, 0), (.145, rig.SHIN * .44, .165), low, mat=M_FABRIC, **k)]
        if det > .3: shn.append(C((0, -rig.SHIN * .97, 0), (.155, .05, .175), _sh(low, .80), mat=M_FABRIC, **k))   # cuff
        emit(shn, sk.frames['shin' + tag])
        ft = [C((0, .055, .035), (.185, .07, .255), _SHOE, **k),
              C((0, .018, .035), (.195, .035, .265), _sh(_SHOE, .62), **k)]                       # sole
        if det > .3:
            ft.append(C((0, .075, .145), (.17, .055, .06), _sh(_SHOE, 1.25), **k))                # toe cap
            ft.append(C((0, .095, -.07), (.15, .06, .07), _sh(_SHOE, .85), **k))                  # heel counter
        emit(ft, sk.frames['foot' + tag])
    emit(_torso_v2(-rig.PELVIS_Y, outfit, hood, skin, L['shirt'], L['tie'], L['cape'], L['backpack'], k, det), sk.frames['torso'])
    # arms: upper arm and forearm in two volumes each, cuff, palm and thumb
    fore = skin if outfit in ('tshirt', 'dress') else hood
    fmat = 0 if fore == skin else M_FABRIC
    for tag in 'LR':
        emit([C((0, -rig.UPPER * .30, 0), (.145, rig.UPPER * .62 + .07, .155), hood, mat=M_FABRIC, **k),
              C((0, -rig.UPPER * .80, 0), (.125, rig.UPPER * .44, .135), hood, mat=M_FABRIC, **k)], sk.frames['upper' + tag])
        fa = [C((0, -rig.FORE * .30, 0), (.125, rig.FORE * .60 + .05, .135), fore, mat=fmat, **k),
              C((0, -rig.FORE * .80, 0), (.105, rig.FORE * .44, .115), fore, mat=fmat, **k)]
        if det > .3 and fore != skin: fa.append(C((0, -rig.FORE * .96, 0), (.115, .045, .125), _sh(hood, .78), mat=M_FABRIC, **k))
        emit(fa, sk.frames['fore' + tag])
        sd = 1 if tag == 'R' else -1
        hd = [C((0, -.035, .005), (.105, .115, .115), skin, **k)]
        if det > .3:
            hd.append(C((sd * .055, -.015, .035), (.045, .055, .065), _sh(skin, .94), **k))       # thumb
            hd.append(C((0, -.105, .01), (.095, .055, .10), _sh(skin, .90), **k))                 # fingers
        emit(hd, sk.frames['hand' + tag])
    # head: cranium + proud face plate + jaw + ears + brow ridge, then the hair shells
    hb = [C((0, .01, -.02), (.40, .40, .34), skin, **k),
          C((0, -.01, .175), (.355, .345, .035), skin, tex={'+z': face}, **k)]
    if det > .3:
        hb.append(C((0, -.175, .055), (.30, .09, .27), _sh(skin, .92), **k))                      # jaw
        for sd in (-1, 1): hb.append(C((sd * .205, -.015, -.03), (.035, .13, .10), _sh(skin, .96), **k))   # ears
        hb.append(C((0, .105, .185), (.33, .030, .02), _sh(skin, .97), **k))                      # brow ridge, barely shaded: at .88 it read as a dark bar across a close-up
    hb += hair_layers(hair, ('long' if (L['hair_long'] and not L['hair_style']) else L['hair_style']), L['hat'], k, sway)
    hb += P.hair_and_hat(0., -1.68, 0., 1, hair, 'bald', L['hat'], L['hat_color'], hood, k)       # the hat only
    if L['headphones'] and L['hat'] not in ('hood', 'beanie'):
        for sd in (-1, 1):
            hb.append(C((sd * .235, 0, 0), (.055, .17, .17), (26, 26, 32), **k))
            hb.append(C((sd * .266, 0, .04), (.02, .035, .035), (80, 255, 130), emis=1.6, cast=False, **k))
        if not L['hat'] or L['hat'] == 'none': hb.append(C((0, .282, 0), (.47, .045, .10), (26, 26, 32), **k))
    if L['eyes'] is not None:
        for sd in (-1, 1): hb.append(C((sd * .09, .025, .198), (.05, .045, .01), L['eyes'], emis=3.2, cast=False, **k))
    emit(hb, sk.frames['head'])
    item = sample.get('hold')
    if item in P.HOLD_ITEMS:
        il = []
        ib = P.held_item(item, (0., 0., 0.), 1, k, il, tuple(spec['hold_color']) if spec and spec.get('hold_color') else None)
        R_t = sk.frames['torso'][0]; hand = sk.joints['haR']
        emit(ib, (R_t, hand))
        if item == 'flashlight': il = [((q[0], q[1], q[2] * 1.9), c_, pw * .45, r_ * 1.3) for (q, c_, pw, r_) in il]
        if lights is not None:
            for (q, c_, pw, r_) in il:
                w = Rw @ (R_t @ np.asarray(q, np.float32) * s + hand * s) + base
                lights.append((tuple(float(v) for v in w), c_, pw, r_))
    return out, sk


# --------------------------------------------------------------------------- set dressing
_DECOR_CACHE = {}
MAX_WALLS = 28
WALL_MATS = (M_WOODV, M_PLASTER, M_CLEAN)         # the three wall finishes of the sets (panelling, plaster, paint)
MAX_DRESS = 150                                   # hard cap on the boxes the furniture pass may add to a set
_SPAN = .70                                       # below this a block is a crate or a pot, not a piece of furniture


def _is_wall(sz, mat):
    """the same test decor() uses, so the furniture pass never dresses a wall twice"""
    return (mat in WALL_MATS and sz[1] >= 1.3 and (sz[0] < .32 or sz[2] < .32) and max(sz[0], sz[2]) >= .5)


def _thin_axis(sz):
    return 0 if sz[0] <= sz[2] else 2


def _dress_soft(lo, sz, col, det):
    """upholstery (sofa, armchair, bed, cushion): a lit welt along the top edge, a shadow welt at the base and
    cushion seams across the long axis. The shipped sets build these as one plain block."""
    out = []
    c = [float(lo[i] + sz[i] / 2) for i in range(3)]
    top = float(lo[1] + sz[1])
    out.append(C((c[0], top - .018, c[2]), (float(sz[0]) + .022, .038, float(sz[2]) + .022), _sh(col, 1.24), mat=M_FABRIC, cast=False))
    out.append(C((c[0], float(lo[1]) + .030, c[2]), (float(sz[0]) + .026, .058, float(sz[2]) + .026), _sh(col, .68), mat=M_FABRIC, cast=False))
    if det <= .3: return out
    lng = 0 if sz[0] >= sz[2] else 2                      # seams run across the long axis
    n = 2 if max(sz[0], sz[2]) < 1.5 else 3
    for i in range(1, n):
        q = float(lo[lng]) + float(sz[lng]) * i / n
        s = [0., .028, 0.]
        s[lng] = .030; s[2 - lng] = float(sz[2 - lng]) * .88
        ctr = [c[0], top - .004, c[2]]; ctr[lng] = q
        out.append(C(tuple(ctr), tuple(s), _sh(col, .60), mat=M_FABRIC, cast=False))
    if lo[1] <= .07:                                      # feet, so the block stops growing out of the floor
        for sx in (-1, 1):
            for szn in (-1, 1):
                out.append(C((c[0] + sx * (float(sz[0]) / 2 - .06), float(lo[1]) + .022, c[2] + szn * (float(sz[2]) / 2 - .06)),
                             (.075, .05, .075), _sh(col, .42), cast=False))
    return out


def _dress_top(lo, sz, col, det):
    """a table, desk or shelf top already in the set: an overhanging lip and an apron rail under it"""
    out = []
    c = [float(lo[i] + sz[i] / 2) for i in range(3)]
    top = float(lo[1] + sz[1])
    out.append(C((c[0], top + .008, c[2]), (float(sz[0]) + .055, .024, float(sz[2]) + .055), _sh(col, 1.16), mat=M_WOODV, cast=False))
    if det > .3:
        out.append(C((c[0], float(lo[1]) - .045, c[2]), (float(sz[0]) * .90, .055, float(sz[2]) * .90), _sh(col, .70), mat=M_WOODV, cast=False))
    return out


def _dress_block(lo, sz, col, det):
    """a solid block of furniture standing on the floor (the shipped coffee tables and counters are one box):
    a proud top plate, a recessed apron that reads as a drawer front, and corner feet"""
    out = []
    c = [float(lo[i] + sz[i] / 2) for i in range(3)]
    top = float(lo[1] + sz[1])
    out.append(C((c[0], top + .014, c[2]), (float(sz[0]) + .065, .034, float(sz[2]) + .065), _sh(col, 1.22), mat=M_WOODV, cast=False))
    if det <= .3: return out
    out.append(C((c[0], top - .085, c[2]), (float(sz[0]) - .07, .085, float(sz[2]) + .016), _sh(col, .60), mat=M_WOODV, cast=False))
    if max(sz[0], sz[2]) > .9:                            # a drawer pull on the long face
        lng = 0 if sz[0] >= sz[2] else 2
        s = [0., .026, 0.]; s[lng] = .16; s[2 - lng] = float(sz[2 - lng]) + .03
        out.append(C((c[0], top - .085, c[2]), tuple(s), _sh(col, 1.35), cast=False))
    for sx in (-1, 1):
        for szn in (-1, 1):
            out.append(C((c[0] + sx * (float(sz[0]) / 2 - .055), float(lo[1]) + .028, c[2] + szn * (float(sz[2]) / 2 - .055)),
                         (.07, .062, .07), _sh(col, .46), cast=False))
    return out


def _dress_tall(lo, sz, col, ceil_y, det):
    """a bookcase, wardrobe or counter taller than a person: a cornice, a plinth and four corner posts. Kept
    orientation-agnostic on purpose -- a box carries no tag, so which face is the front cannot be known."""
    out = []
    c = [float(lo[i] + sz[i] / 2) for i in range(3)]
    top = float(lo[1] + sz[1])
    if ceil_y is not None: top = min(top, float(ceil_y) - .04)
    if top - float(lo[1]) < .6: return out
    out.append(C((c[0], top - .030, c[2]), (float(sz[0]) + .075, .055, float(sz[2]) + .075), _sh(col, 1.20), mat=M_WOODV, cast=False))
    out.append(C((c[0], float(lo[1]) + .045, c[2]), (float(sz[0]) + .045, .085, float(sz[2]) + .045), _sh(col, .58), mat=M_WOODV, cast=False))
    if det <= .3: return out
    for sx in (-1, 1):
        for szn in (-1, 1):
            out.append(C((c[0] + sx * (float(sz[0]) / 2 - .035), (float(lo[1]) + top) / 2, c[2] + szn * (float(sz[2]) / 2 - .035)),
                         (.07, top - float(lo[1]) - .14, .07), _sh(col, 1.08), mat=M_WOODV, cast=False))
    return out


def _dress_panel(lo, sz, col, det):
    """a window, a framed picture or a screen: the shipped sets build them as one thin slab on the wall. Add the
    frame around it, and a sill when it sits high enough to have one."""
    out = []
    t = _thin_axis(sz); w = 2 - t
    c = [float(lo[i] + sz[i] / 2) for i in range(3)]
    fr = _sh(col, .52) if sum(col) > 330 else _sh(col, 1.45)
    d = float(sz[t]) + .045
    for dy in (-1, 1):                                    # head and sill rails
        s = [0., .055, 0.]; s[t] = d; s[w] = float(sz[w]) + .085
        ctr = list(c); ctr[1] = c[1] + dy * (float(sz[1]) / 2 + .012)
        out.append(C(tuple(ctr), tuple(s), fr, cast=False))
    for dw in (-1, 1):                                    # the two jambs
        s = [0., float(sz[1]) + .085, 0.]; s[t] = d; s[w] = .055
        ctr = list(c); ctr[w] = c[w] + dw * (float(sz[w]) / 2 + .012)
        out.append(C(tuple(ctr), tuple(s), fr, cast=False))
    if det > .3 and float(lo[1]) > .55:                   # a sill to stand things on
        s = [0., .045, 0.]; s[t] = d + .075; s[w] = float(sz[w]) + .16
        ctr = list(c); ctr[1] = float(lo[1]) - .055
        out.append(C(tuple(ctr), tuple(s), _sh(fr, 1.12), cast=False))
    if det > .3 and float(sz[1]) > .7 and float(sz[w]) > .7:    # a glazing bar across a real window
        s = [0., .03, 0.]; s[t] = float(sz[t]) + .02; s[w] = float(sz[w]) - .02
        out.append(C((c[0], c[1], c[2]), tuple(s), fr, cast=False))
    return out


def _dress_door(lo, sz, col, det):
    """a door leaf (material M_DOOR, so this one is certain): the casing around it and a handle"""
    out = []
    t = _thin_axis(sz); w = 2 - t
    c = [float(lo[i] + sz[i] / 2) for i in range(3)]
    fr = _sh(col, 1.35)
    s = [0., .07, 0.]; s[t] = float(sz[t]) + .06; s[w] = float(sz[w]) + .13
    out.append(C((c[0], float(lo[1] + sz[1]) + .025, c[2]), tuple(s), fr, cast=False))        # lintel
    for dw in (-1, 1):
        s = [0., float(sz[1]), 0.]; s[t] = float(sz[t]) + .06; s[w] = .06
        ctr = list(c); ctr[w] = c[w] + dw * (float(sz[w]) / 2 + .030)
        out.append(C(tuple(ctr), tuple(s), fr, cast=False))                                   # jambs
    if det > .3:
        ctr = list(c); ctr[1] = float(lo[1]) + float(sz[1]) * .47
        ctr[w] = c[w] + float(sz[w]) * .36
        s = [0., .05, 0.]; s[t] = float(sz[t]) + .07; s[w] = .10
        out.append(C(tuple(ctr), tuple(s), (196, 178, 120), mat=M_METAL, cast=False))          # handle
    return out


def _dress_rug(lo, sz, col, det):
    """a rug is a single flat slab in the shipped sets: give it a border and a woven inner band"""
    c = [float(lo[i] + sz[i] / 2) for i in range(3)]
    y = float(lo[1] + sz[1])
    out = [C((c[0], y - .004, c[2]), (float(sz[0]) + .07, .010, float(sz[2]) + .07), _sh(col, .66), mat=M_FABRIC, cast=False)]
    if det > .3:
        out.append(C((c[0], y + .004, c[2]), (float(sz[0]) * .80, .008, float(sz[2]) * .74), _sh(col, 1.28), mat=M_FABRIC, cast=False))
        out.append(C((c[0], y + .006, c[2]), (float(sz[0]) * .62, .008, float(sz[2]) * .54), _sh(col, .86), mat=M_FABRIC, cast=False))
    return out


# --------------------------------------------------------------------------- accessories on the flat tops
def _acc_books(x, y, z, rng):
    """a short stack of books, each one a little off the one below"""
    out = []; h = y
    for i in range(2 + int(rng.integers(0, 2))):
        t = .035 + float(rng.random()) * .02
        col = _BOOK_COLS[int(rng.integers(0, len(_BOOK_COLS)))]
        out.append(C((x + (float(rng.random()) - .5) * .035, h + t / 2, z + (float(rng.random()) - .5) * .035),
                     (.17, t, .13), col, mat=M_WOODV, cast=False))
        h += t
    return out


def _acc_mug(x, y, z, rng):
    col = _MUG_COLS[int(rng.integers(0, len(_MUG_COLS)))]
    return [C((x, y + .045, z), (.075, .09, .075), col, cast=False),
            C((x + .052, y + .048, z), (.028, .045, .022), col, cast=False),               # handle
            C((x, y + .088, z), (.055, .008, .055), _sh(col, .55), cast=False)]            # what is in it


def _acc_bottle(x, y, z, rng):
    col = (62, 86, 64) if rng.random() < .5 else (96, 68, 48)
    return [C((x, y + .075, z), (.07, .15, .07), col, cast=False),
            C((x, y + .175, z), (.032, .05, .032), col, cast=False),
            C((x, y + .205, z), (.036, .018, .036), _sh(col, 1.5), cast=False)]


def _acc_bowl(x, y, z, rng):
    col = (206, 198, 182) if rng.random() < .5 else (150, 120, 96)
    return [C((x, y + .028, z), (.16, .056, .16), col, cast=False),
            C((x, y + .052, z), (.115, .02, .115), _sh(col, .52), cast=False)]


def _acc_papers(x, y, z, rng):
    out = [C((x, y + .008, z), (.21, .016, .16), (218, 214, 202), mat=M_WOODV, cast=False)]
    if rng.random() < .6:
        out.append(C((x + .03, y + .020, z - .02), (.17, .010, .13), (232, 228, 218), mat=M_WOODV, cast=False))
    return out


def _acc_candle(x, y, z, rng):
    h = .09 + float(rng.random()) * .06
    return [C((x, y + .012, z), (.10, .024, .10), (120, 108, 92), mat=M_METAL, cast=False),
            C((x, y + .024 + h / 2, z), (.05, h, .05), (236, 226, 196), cast=False),
            C((x, y + .030 + h + .018, z), (.026, .036, .026), (255, 176, 70), emis=2.6, cast=False)]


_BOOK_COLS = ((150, 40, 40), (40, 80, 140), (60, 120, 70), (200, 170, 60), (120, 60, 130), (210, 120, 40))
_MUG_COLS = ((226, 222, 214), (180, 70, 60), (60, 100, 140), (90, 92, 98))
ACC = (_acc_books, _acc_mug, _acc_bottle, _acc_bowl, _acc_papers, _acc_books, _acc_candle)


def _blocked(x, y, z, occupied, r=.15, h=.32):
    """is something already standing on that spot? the set's own props win, an accessory never grows through one"""
    for (lo, hi) in occupied:
        if hi[1] <= y + .005 or lo[1] >= y + h: continue
        if lo[0] - r < x < hi[0] + r and lo[2] - r < z < hi[2] + r: return True
    return False


def _accessories(tops, occupied, det):
    """small items on the free part of the flat tops the set already built. The seed comes from the surface's own
    geometry, so a set is always dressed the same way: no wall clock, no unseeded randomness (AGENTS.md)."""
    out = []
    if det <= .5: return out
    placed = 0
    for (lo, sz) in sorted(tops, key=lambda t: (round(float(t[0][0]), 3), round(float(t[0][1]), 3), round(float(t[0][2]), 3))):
        y = float(lo[1] + sz[1])
        if not (.25 <= y <= 1.65): continue                   # under a seat or above the top of frame
        lng = 0 if sz[0] >= sz[2] else 2
        span = float(sz[lng]); other = float(sz[2 - lng])
        if span < .5 or other < .28: continue
        rng = np.random.default_rng(zlib.crc32(('%.3f,%.3f,%.3f,%.3f,%.3f' % (
            float(lo[0]), float(lo[1]), float(lo[2]), span, other)).encode()))
        n = 1 if span < .95 else 2
        for i in range(n):
            if placed >= 7: return out                        # a dressed set, not a cluttered one
            t = min(max((i + .5) / n + (float(rng.random()) - .5) * .20, .15), .85)
            px = [0., y, 0.]
            px[lng] = float(lo[lng]) + span * t
            px[2 - lng] = float(lo[2 - lng]) + other * (.34 + .32 * float(rng.random()))
            if _blocked(px[0], y, px[2], occupied): continue
            out += ACC[int(rng.integers(0, len(ACC)))](px[0], y, px[2], rng)
            occupied = occupied + [(np.array([px[0] - .13, y, px[2] - .13], np.float32),
                                    np.array([px[0] + .13, y + .3, px[2] + .13], np.float32))]
            placed += 1
    return out


def furniture(boxes, ceil_y):
    """richer voxel furniture, props and set dressing, read off the geometry the set already built. Like decor()
    it is a pure function of the scene's boxes: it never edits places.py, world.PROPS or compose.py, so with the
    art key absent the shipped sets stay identical box for box. A box carries no name, so every rule here is a
    size / material / height test, and anything ambiguous is left alone on purpose."""
    det = detail()
    out = []; tops = []; occ = []
    nwall = 0
    for b in boxes:
        if b.inst is not None or b.hidden: continue
        occ.append((b.lo, b.hi))
        if _is_wall(b.hi - b.lo, b.mat): nwall += 1
    # furniture dressing is for rooms only. Outdoors a box is a rock, a tree trunk or a roof, and its bounding
    # box says nothing about what it is: the same rules that give a sofa its welts would give a boulder feet.
    # The outdoor props of world.py keep their shipped look -- that is a deliberate limit of this increment.
    if ceil_y is None and nwall < 2: return []
    for b in boxes:
        if b.inst is not None or b.hidden or b.emis > 0: continue
        lo = b.lo; sz = b.hi - b.lo
        if _is_wall(sz, b.mat): continue                       # decor() already put mouldings on that one
        if sz[1] > 2.45 or max(sz[0], sz[2]) > 4.: continue    # a floor, a ceiling or a ground slab
        col = tuple(int(v) for v in np.round(b.col * 255).tolist())
        foot = float(min(sz[0], sz[2])); span = float(max(sz[0], sz[2]))
        if b.mat == M_DOOR and sz[1] > 1.4 and foot < .3:
            out += _dress_door(lo, sz, col, det)
        elif foot <= .09 and sz[1] >= .35 and span >= .40 and lo[1] >= .25:
            out += _dress_panel(lo, sz, col, det)              # a window, a picture, a screen
        elif sz[1] <= .06 and lo[1] <= .06 and foot >= .5:
            out += _dress_rug(lo, sz, col, det)
        elif span < _SPAN: continue                            # a crate, a pot, a book: too small to be furniture
        elif b.mat == M_FABRIC and sz[1] >= .18 and foot >= .16:
            out += _dress_soft(lo, sz, col, det)               # upholstery
        elif lo[1] <= .12 and sz[1] >= 1.3 and foot >= .22:
            out += _dress_tall(lo, sz, col, ceil_y, det)       # bookcase, wardrobe, counter
        elif sz[1] <= .17 and foot >= .35 and lo[1] >= .35:
            out += _dress_top(lo, sz, col, det); tops.append((lo, sz))      # a table or shelf top
        elif lo[1] <= .08 and .22 <= sz[1] <= .95 and foot >= .35:
            out += _dress_block(lo, sz, col, det); tops.append((lo, sz))    # a solid block of furniture
        if len(out) >= MAX_DRESS: return out[:MAX_DRESS]
    out += _accessories(tops, occ, det)
    return out[:MAX_DRESS]


def decor(boxes, ceil_y):
    """skirting board, dado rail and cornice on the walls already in the scene, then the furniture, prop and
    accessory dressing of furniture(). A pure function of the scene geometry, cached: the same set pays the scan
    only once."""
    if not on('decor'): return []
    det = detail()
    walls = []; sig = []
    for b in boxes:
        if b.inst is not None or b.hidden: continue
        sz = b.hi - b.lo
        sig.append((tuple(np.round(b.lo, 3).tolist()), tuple(np.round(b.hi, 3).tolist()),
                    tuple(np.round(b.col * 255, 0).tolist()), int(b.mat), round(float(b.emis), 2)))
        if b.mat not in WALL_MATS: continue
        if sz[1] < 1.3 or not (sz[0] < .32 or sz[2] < .32) or max(sz[0], sz[2]) < .5: continue
        walls.append((tuple(np.round(b.lo, 3).tolist()), tuple(np.round(b.hi, 3).tolist()),
                      tuple(np.round(b.col * 255, 0).tolist())))
        if len(walls) > MAX_WALLS: return []              # a big open set: not worth the boxes
    # the key covers every static box, not just the walls: the furniture pass reads them all
    key = (zlib.crc32(repr(sig).encode()), round(float(ceil_y) if ceil_y is not None else 0., 3), round(det, 2))
    hit = _DECOR_CACHE.get(key)
    if hit is not None: return hit
    out = []
    for (lo_, hi_, col) in walls:
        lo = np.array(lo_, np.float32); hi = np.array(hi_, np.float32); sz = hi - lo
        thin = 0 if sz[0] < sz[2] else 2                  # the wall's thickness axis
        wide = 2 - thin
        c = (lo + hi) / 2
        top = float(min(hi[1], ceil_y)) if ceil_y is not None else float(hi[1])
        base_col = tuple(int(v) for v in col)
        size = [0., 0., 0.]; size[wide] = float(sz[wide]) * .995
        size[thin] = float(sz[thin]) + .07; size[1] = .11                                            # skirting board
        out.append(C((float(c[0]), float(lo[1]) + .055, float(c[2])), tuple(size), _sh(base_col, .62), mat=M_FABRIC, cast=False))
        if det > .5:
            size[1] = .045                                                                            # cornice
            out.append(C((float(c[0]), top - .055, float(c[2])), tuple(size), _sh(base_col, 1.18), mat=M_FABRIC, cast=False))
            size[thin] = float(sz[thin]) + .035; size[1] = .035                                       # dado rail
            out.append(C((float(c[0]), float(lo[1]) + .95, float(c[2])), tuple(size), _sh(base_col, .80), mat=M_FABRIC, cast=False))
    out += furniture(boxes, ceil_y)
    _DECOR_CACHE[key] = out
    return out


# --------------------------------------------------------------------------- image finish
_DITHER = {}


def _dither():
    key = (r3d.RW, r3d.RH)
    if key not in _DITHER:
        m = (np.array([[0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26],
                       [12, 44, 4, 36, 14, 46, 6, 38], [60, 28, 52, 20, 62, 30, 54, 22],
                       [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
                       [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21]], np.float32) + .5) / 64.
        _DITHER[key] = np.tile(m, (r3d.RH // 8 + 1, r3d.RW // 8 + 1))[:r3d.RH, :r3d.RW]
    return _DITHER[key]


_VIGN = {}


def _vignette(strength):
    key = (r3d.RW, r3d.RH, round(strength, 3))
    if key not in _VIGN:
        yy, xx = np.mgrid[0:r3d.RH, 0:r3d.RW].astype(np.float32)
        u = (xx / r3d.RW - .5) * 2; v = (yy / r3d.RH - .5) * 2
        rr = np.sqrt(u * u * .92 + v * v * .78)
        _VIGN[key] = (1. - strength * np.clip(rr - .42, 0, None) ** 1.6)[..., None]
    return _VIGN[key]


def halation(hdr, thr=.55, k=.40):
    """warm bleed around the bright parts, measured on the frame BEFORE the tone curve (where a practical really
    is above 1.0) and added after it: a bloom folded into the curve would be compressed away."""
    br = np.clip(hdr.max(-1, keepdims=True) - thr, 0, None)
    s_ = br.reshape(r3d.RH // 8, 8, r3d.RW // 8, 8, 1).mean((1, 3))
    for _ in range(3): s_ = (s_ + np.roll(s_, 1, 0) + np.roll(s_, -1, 0) + np.roll(s_, 1, 1) + np.roll(s_, -1, 1)) / 5
    up = np.repeat(np.repeat(s_, 8, 0), 8, 1)
    for _ in range(2): up = (up + np.roll(up, 4, 0) + np.roll(up, -4, 0) + np.roll(up, 4, 1) + np.roll(up, -4, 1)) / 5
    return up * k * np.array([1.0, .86, .66], np.float32)


def _curve(v):
    return (v * (2.51 * v + .03)) / (v * (2.43 * v + .59) + .14)


_FILM_K, _WHITE = .50, 1.25
_FILM_N = _curve(_WHITE * _FILM_K)


def _filmic(x):
    """ACES-like shoulder carried to the three channels as a ratio, so mid tones keep their colour instead of being
    washed out by a per-channel curve; the brightest values are bleached towards white first, the way a practical
    burns out on film. Scaled so mid grey keeps the brightness of the shipped look."""
    m = x.max(-1, keepdims=True)
    x = x + (m - x) * np.clip((m - 1.15) / 1.2, 0, 1) * .70           # only the practicals burn out white
    m = x.max(-1, keepdims=True)
    return np.clip(x * (np.clip(_curve(m * _FILM_K) / _FILM_N, 0, 1) / np.maximum(m, 1e-5)), 0, 1)


def quantise(rgb, vlev=18, slev=7, hstep=12., levels=None):
    """palette step of the art v2: finer than r3d.pixelate, on an 8x8 ordered dither.
    `levels` (engines/pixel3d/finish.py): None keeps these defaults, False removes the step entirely."""
    if levels is not None:
        if levels is False: return (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
        vlev, slev, hstep = levels
    a = np.clip(rgb, 0, 1)
    h, s, v = r3d.rgb2hsv(a)
    bt = _dither()
    h = np.round(h / hstep) * hstep
    s = np.clip(np.floor(s * (slev - 1) + bt * .75 + .5), 0, slev - 1) / (slev - 1)
    v = np.clip(np.floor(v * (vlev - 1) + bt), 0, vlev - 1) / (vlev - 1)
    return (np.clip(r3d.hsv2rgb(h, s, v), 0, 1) * 255).astype(np.uint8)


def grade(img, saturation=.5, exposure=1.0, seed=0, levels=None):
    """full image finish of the art v2, in order: exposure -> filmic shoulder -> split tone -> saturation -> warm
    cast -> halation -> vignette -> palette. `img` is the frame out of r3d.render; r3d.glow is NOT applied before
    it (halation replaces it, measured on this frame and added after the curve)."""
    hdr = np.clip(img * float(exposure), 0, None)
    img = _filmic(hdr)
    lum = (img * np.array([.299, .587, .114], np.float32)).sum(-1, keepdims=True)
    shadow = np.clip(1 - lum * 2.4, 0, 1); high = np.clip(lum * 1.7 - .45, 0, 1)
    img = img + shadow * np.array([-.006, .002, .018], np.float32) + high * np.array([.014, .005, -.010], np.float32)
    img = lum + (img - lum) * float(saturation) * 1.25          # the v2 palette carries a little more colour
    img = img * np.array([1.0, .985, .945], np.float32)         # same warm cast as the shipped grade
    img = (img + halation(hdr)) * _vignette(.22)
    img = np.clip(img, 0, None) + (np.random.default_rng(int(seed) + 7).random(img.shape[:2], np.float32)[..., None] - .5) * .022
    return quantise(img, levels=levels)
