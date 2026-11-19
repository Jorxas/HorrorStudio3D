"""PIXEL 3D building facades -- EXPERIMENTAL, OPT-IN ONLY (episode key "env").

The shipped facade stays the default and is never touched by this module. Without the key `active()` returns
None, `ppm()` is the shipped 4, `tex()` returns None, and every frame is the same bytes it was before
(tools/regress.py, tools/regress_v2.py, tools/check_env.py).

WHY. The lot before this one took the raster from 216x384 to 648x1152 and the image stopped staircasing.
That immediately exposed the NEXT limit, and it is not the raster: a building facade is a texture drawn at
**4 pixels per metre** (`compose.PPM`), on which a window is a plain filled rectangle -- no frame, no sill,
no mullion, no glass, no door anywhere. A 2.6 m bay is ten texels wide and the window inside it is four.
Blown up on a wall six metres from the camera, that is a coloured sticker, and nine times more rays only
make the sticker sharper.

So the buildings read as generic: same flat plaster, same rectangles, no ground floor, nothing that says
which building this is. That is what the owner's note is about -- "bâtiments crédibles non génériques avec
portes, fenêtres, matériaux et détails différenciés".

WHAT IT CHANGES, and all of it is TEXTURE:

- **resolution**: `ppm` 4 -> 12 (preset `riche`). A 2.6 m bay becomes 31 texels, enough for a frame, a sill
  and a pair of mullions. Textures are `lru_cache`d per (size, style, seed, face), so the cost is paid once
  per distinct wall and never per frame;
- **the wall itself**: brick courses with per-brick colour jitter, plaster blocks, or concrete panels with
  their joints -- picked by style, so two styles no longer differ only in hue;
- **the window**: a recessed glass pane, a lintel and a sill that catch the light, jambs, one or two
  mullions, and per-window glass colour. Some are lit warm, some are cold and dark, some have a blind at
  half mast, some are boarded;
- **the ground floor**: a door, with a frame, a step, a handle and a light above it -- plus shopfronts on
  the wider bays. The shipped facade had no ground floor at all, which is the single reason an alley never
  looked like it led anywhere;
- **the age**: a downpipe, damp running from the sills, and a few cracks.

Emission is carried in a FIFTH texture channel, not in the alpha (see r3d.shade). Without that, an opaque
stone sill would glow exactly as hard as the lit window above it, which is what the shipped facade does and
gets away with only because it draws nothing but windows.

WHAT IT IS NOT. No new geometry: the facade is still one flat face of one box, so a window has no depth and
a sill casts no shadow. The relief you see is painted. It is also NOT a material system -- the wall under
the texture keeps the material (`plaster`, `metal`) the set gave it.

    "env": "riche"                                   the retained preset (see PRESETS)
    "env": {"style": "riche", "ppm": 16}             same, tuned
    "env": false | absent                            the shipped facade, bit for bit
"""
import functools
import numpy as np

_STATE = None

# `ppm` is the facade texture resolution in pixels per metre (the shipped value is 4). `detail` scales the
# optional passes (courses, stains, downpipes); `doors` turns the ground floor on.
PRESETS = {
    # the configuration retained after measurement -- see docs/P1_DECOR_URBAIN_20261025.md
    'riche': dict(ppm=12, detail=1., doors=True),
    # half the texels: measured, kept reachable for a machine in a hurry
    'riche_rapide': dict(ppm=8, detail=1., doors=True),
    # the finest measured, to show where texels stop paying
    'riche_max': dict(ppm=18, detail=1., doors=True),
    # the resolution alone, no new detail: isolates what the texels are worth on their own
    'dense_seul': dict(ppm=12, detail=0., doors=False),
}
KEYS = tuple(sorted(PRESETS['riche']))


def register(name, **spec):
    """an extension adds its own facade preset (registry, not if/elif -- see AGENTS.md)"""
    PRESETS[name] = dict(PRESETS['riche'], **{k: v for k, v in spec.items() if k in PRESETS['riche']})
    return PRESETS[name]


def configure(spec):
    """`spec` is the episode's `env` key: None / False (off), a preset name, or {"style": name, ...}.
    Returns the resolved preset or None. Called once per engine, exactly like finish.configure(ep['finish'])."""
    global _STATE
    _STATE = None
    if not spec: return None
    if spec is True: name, over = 'riche', {}
    elif isinstance(spec, str): name, over = spec, {}
    elif isinstance(spec, dict):
        name = spec.get('style') or spec.get('preset') or 'riche'
        over = {k: v for k, v in spec.items() if k not in ('style', 'preset')}
    else: return None
    if name not in PRESETS: return None
    st = dict(PRESETS[name])
    for key, v in over.items():
        if key not in st: continue
        if key == 'doors': st[key] = bool(v); continue
        if key == 'ppm':
            try: st[key] = max(4, min(24, int(round(float(v)))))
            except (TypeError, ValueError): pass
            continue
        try: st[key] = max(0., min(1., float(v)))
        except (TypeError, ValueError): pass
    st['name'] = name
    _STATE = st
    return st


def use(state):
    """re-assert a resolved preset before rendering (the spawn pool rebuilds the engine per worker)"""
    global _STATE
    _STATE = state
    return state


def active(): return _STATE


def ppm(default=4):
    """facade texture pixels per metre; the shipped 4 without the key, so compose.py is unchanged"""
    return int(_STATE['ppm']) if _STATE else int(default)


def cap():
    """(max width, max height) of a facade texture in texels. The shipped caps assume 4 px/m; at 12 they
    would clip a wide district block back to a smear, which is worse than not raising the resolution."""
    if not _STATE: return 320, 640
    k = max(1, int(_STATE['ppm']) // 4)
    return 320 * k, 640 * k


def notices(ep):
    """what this facade does and does not do, said in French on the render log instead of in silence"""
    if not _STATE: return []
    st = _STATE
    out = [f'décors "{st["name"]}" : façades à {st["ppm"]} texels/m (livré : 4), '
           f'{"rez-de-chaussée avec portes" if st["doors"] else "sans rez-de-chaussée"}, '
           f'détails {"complets" if float(st["detail"]) >= 1 else "réduits"}']
    out.append('décors : le relief des fenêtres est PEINT, pas construit — une embrasure n\'a pas de '
               'profondeur et un appui ne porte pas d\'ombre')
    return out


# --------------------------------------------------------------------------- the texture itself
def _jit(rng, shape, amp):
    return (rng.random(shape, np.float32) - .5) * 2 * amp


def _wall(a, e, style, rng, detail, body):
    """the wall itself: masonry courses, plaster blocks or concrete panels. Opaque, never emissive.

    This is the pass that stops two buildings of different styles from differing only in hue: a masonry wall
    has courses with a mortar line and a different colour per block, a concrete wall has panels with a
    recessed joint, plaster has broad blocks. `body` is the block's own colour from the set, and the whole
    wall is tinted by it so that the buildings the set author made different stay different -- without this
    an opaque texture would paint every block the same and a street would go generic again.

    COURSE SIZE IS NOT TO SCALE, and saying so matters: a real brick course is ~8.5 cm, which at 12 texels
    per metre is one texel and would read as noise. The courses here are ~1/4 m, the smallest size that
    still reads as masonry at this resolution."""
    th, tw = a.shape[:2]
    yy, xx = np.mgrid[0:th, 0:tw]
    base = np.zeros((th, tw, 3), np.float32)
    if style == 'brick':
        ch = 3                                                                # ~1/4 m course (see docstring)
        course = yy // ch
        bw = max(3, ch * 2)
        off = (course % 2) * (bw // 2)
        brick = (xx + off) // bw
        hsh = ((brick * 73856093) ^ (course * 19349663)) % 1000 / 1000.
        base[..., 0] = .50 + .22 * hsh; base[..., 1] = .22 + .12 * hsh; base[..., 2] = .17 + .09 * hsh
        mortar = ((yy % ch) == 0) | (((xx + off) % bw) == 0)
        base[mortar] = base[mortar] * .55 + np.array([.56, .54, .50], np.float32) * .45
    elif style in ('concrete', 'office', 'glass'):
        panel = max(6, int(round(tw / 4.)))
        base[:] = (.46, .46, .45)
        seam = ((xx % panel) == 0) | ((yy % max(6, panel)) == 0)
        base[seam] = (.36, .36, .36)
        base *= (1 + _jit(rng, (th, tw, 1), .05))
    else:                                                                     # old / plaster
        base[:] = (.60, .55, .45)
        blk = max(8, int(round(tw / 3.)))
        seam = ((yy % blk) == 0)
        base[seam] = (.52, .48, .40)
        base *= (1 + _jit(rng, (th, tw, 1), .07))
    if detail > 0:
        # damp, and it has to be IRREGULAR or it reads as scratches: a few wide runs, not one per column,
        # each fading downwards, blurred across three texels so the edge is not a hard line
        runs = np.zeros((1, tw), np.float32)
        for _ in range(max(1, tw // 40)):
            c = int(rng.integers(0, max(1, tw))); w = int(rng.integers(2, max(3, tw // 22)))
            runs[0, max(0, c - w):c + w] = np.maximum(runs[0, max(0, c - w):c + w], .5 + .5 * rng.random())
        if tw > 4:
            runs = (runs + np.roll(runs, 1, 1) + np.roll(runs, -1, 1)) / 3.
        fall = np.clip(1 - yy / (th * .62), 0, 1) ** 1.4
        base *= (1 - .22 * detail * runs * fall)[..., None]
    # Tint, and the WAY it is done decides whether the comparison is honest. The shipped facade left the
    # body colour showing through between its windows, so the wall simply WAS the set's colour. An opaque
    # texture must therefore land on the same brightness, or every wall comes out darker than before and
    # the whole prototype looks better or worse for the wrong reason. So: normalise the pattern to unit
    # luminance (which keeps the style's own hue and its courses), then multiply by the set's colour
    # desaturated a little -- brightness matched exactly, hue leaning towards what the set asked for.
    W_LUM = np.array([.30, .59, .11], np.float32)
    bodyf = np.asarray(body, np.float32) / 255.
    pat = base / max(1e-6, float((base * W_LUM).sum(-1).mean()))
    lb = float((bodyf * W_LUM).sum())
    mix = bodyf * .45 + lb * .55
    base = pat * mix[None, None, :]
    a[..., :3] = np.clip(base * 255, 0, 255).astype(np.uint8)
    a[..., 3] = 255
    e[:] = 0


def _window(a, e, r0, r1, c0, c1, rng, lit, night, win_col, dark_col, detail):
    """one window: lintel, sill, jambs, recessed glass, mullions, and sometimes a blind or boards.

    `r0..r1` / `c0..c1` is the OPENING in the wall, frame included. Everything is painted; the only texels
    that become emissive are the glass ones, and only when the window is lit."""
    if r1 - r0 < 3 or c1 - c0 < 3:
        a[r0:r1, c0:c1, :3] = win_col if (night and rng.random() < lit) else dark_col
        a[r0:r1, c0:c1, 3] = 255
        return
    fr = max(1, (r1 - r0) // 10)                                              # frame thickness in texels
    # lintel above and sill below: lighter stone, they are what catches a street light
    a[max(0, r0 - fr):r0, max(0, c0 - fr):c1 + fr, :3] = (150, 144, 132)
    a[max(0, r0 - fr):r0, max(0, c0 - fr):c1 + fr, 3] = 255
    a[r1:r1 + fr + 1, max(0, c0 - fr - 1):c1 + fr + 1, :3] = (168, 162, 148)
    a[r1:r1 + fr + 1, max(0, c0 - fr - 1):c1 + fr + 1, 3] = 255
    # the reveal: a dark band inside the opening, which is what reads as depth on a flat face
    a[r0:r1, c0:c1, :3] = (28, 26, 28); a[r0:r1, c0:c1, 3] = 255
    g0, g1, h0, h1 = r0 + fr, r1 - fr, c0 + fr, c1 - fr
    if g1 <= g0 or h1 <= h0: return
    boarded = detail > 0 and rng.random() < .07
    if boarded:                                                               # a boarded-up window: no glass, no glow
        a[g0:g1, h0:h1, :3] = (92, 70, 48); a[g0:g1, h0:h1, 3] = 255
        for k in range(g0, g1, max(2, (g1 - g0) // 3)):
            a[k:k + 1, h0:h1, :3] = (66, 48, 32)
        return
    on = night and (rng.random() < lit)
    if on:
        c = tuple(int(min(255, v * (.82 + .3 * rng.random()))) for v in win_col)
    else:
        c = tuple(int(v * (.8 + .4 * rng.random())) for v in dark_col) if night else (108, 138, 166)
    a[g0:g1, h0:h1, :3] = c; a[g0:g1, h0:h1, 3] = 255
    if on: e[g0:g1, h0:h1] = 255
    # a blind or a curtain, half way down: it is what makes a row of windows stop looking stamped
    if detail > 0 and rng.random() < .30:
        hgt = int((g1 - g0) * (.25 + .4 * rng.random()))
        if hgt > 0:
            a[g0:g0 + hgt, h0:h1, :3] = (206, 196, 176) if on else (74, 70, 68)
            if on: e[g0:g0 + hgt, h0:h1] = 120                                # a blind glows, but less than glass
    # mullions: one vertical always, one horizontal on the taller windows
    mc = (h0 + h1) // 2
    a[g0:g1, mc:mc + max(1, fr // 2 + 1), :3] = (62, 58, 54); a[g0:g1, mc:mc + max(1, fr // 2 + 1), 3] = 255
    e[g0:g1, mc:mc + max(1, fr // 2 + 1)] = 0
    if g1 - g0 > 8:
        mr = g0 + (g1 - g0) // 3
        a[mr:mr + max(1, fr // 2 + 1), h0:h1, :3] = (62, 58, 54); a[mr:mr + max(1, fr // 2 + 1), h0:h1, 3] = 255
        e[mr:mr + max(1, fr // 2 + 1), h0:h1] = 0


def _door(a, e, r0, r1, c0, c1, rng, night, lit_above):
    """a ground-floor door: frame, panels, handle, a step, and a lamp over it when the street is dark.

    This is the piece the shipped facade has not got at all, and the reason an alley never looked like it
    led anywhere: a wall with no door is a wall, not a building."""
    if r1 - r0 < 4 or c1 - c0 < 3: return
    fr = max(1, (c1 - c0) // 9)
    a[r0 - fr:r1, c0 - fr:c1 + fr, :3] = (176, 168, 152); a[r0 - fr:r1, c0 - fr:c1 + fr, 3] = 255   # surround
    a[r0:r1, c0:c1, :3] = (104, 66, 44); a[r0:r1, c0:c1, 3] = 255                                   # the leaf
    ph = (r1 - r0) // 3
    for k in (1, 2):                                                           # two recessed panels
        p0 = r0 + ph * (k - 1) + max(1, ph // 6); p1 = r0 + ph * k - max(1, ph // 6)
        a[p0:p1, c0 + fr:c1 - fr, :3] = (78, 48, 32)
    hr = r0 + (r1 - r0) * 55 // 100
    a[hr:hr + max(1, fr), c1 - 2 * fr - 1:c1 - fr, :3] = (196, 176, 110)       # handle
    a[r1 - max(1, fr):r1, c0 - fr - 1:c1 + fr + 1, :3] = (150, 146, 138)       # step
    if lit_above:                                                              # the lamp over the door
        lr = max(0, r0 - 3 * fr - 1); lc0, lc1 = (c0 + c1) // 2 - fr, (c0 + c1) // 2 + fr + 1
        a[lr:lr + 2 * fr, lc0:lc1, :3] = (255, 226, 160); a[lr:lr + 2 * fr, lc0:lc1, 3] = 255
        e[lr:lr + 2 * fr, lc0:lc1] = 255
        # the pool of light it throws on its own wall, painted: the engine's point lights do the rest
        gh = 4 * fr
        for k in range(gh):
            rr = lr + 2 * fr + k
            if rr >= a.shape[0]: break
            w = fr + k
            s0, s1 = max(0, (c0 + c1) // 2 - w), min(a.shape[1], (c0 + c1) // 2 + w)
            f = (1 - k / gh) * .45
            a[rr, s0:s1, :3] = np.clip(a[rr, s0:s1, :3].astype(np.float32) * (1 - f) + np.array([255, 224, 170]) * f, 0, 255).astype(np.uint8)


def _shopfront(a, e, r0, r1, c0, c1, rng, night):
    """a lit shopfront on a wide ground-floor bay: a big pane, a stall riser, an awning band"""
    if r1 - r0 < 4 or c1 - c0 < 6: return
    fr = max(1, (r1 - r0) // 12)
    a[r0:r1, c0:c1, :3] = (46, 42, 40); a[r0:r1, c0:c1, 3] = 255
    g0, g1 = r0 + 2 * fr, r1 - 3 * fr
    if g1 <= g0: return
    on = night and rng.random() < .75
    col = (255, 232, 182) if on else (64, 72, 84)
    a[g0:g1, c0 + fr:c1 - fr, :3] = col; a[g0:g1, c0 + fr:c1 - fr, 3] = 255
    if on: e[g0:g1, c0 + fr:c1 - fr] = 255
    step = max(2, (c1 - c0) // 4)
    for k in range(c0 + fr, c1 - fr, step):                                    # window divisions
        a[g0:g1, k:k + max(1, fr), :3] = (40, 38, 36); e[g0:g1, k:k + max(1, fr)] = 0
    a[r1 - 3 * fr:r1, c0:c1, :3] = (92, 74, 56)                                # stall riser
    a[r0:r0 + 2 * fr, c0:c1, :3] = (120, 48, 44) if rng.random() < .5 else (44, 72, 92)   # awning band


def _pipe(a, e, col, rng):
    """a downpipe: one vertical line of a different material, and the stain it leaves"""
    th, tw = a.shape[:2]
    w = max(1, tw // 90 + 1)
    c = int(col)
    a[:, c:c + w, :3] = (86, 84, 80); a[:, c:c + w, 3] = 255; e[:, c:c + w] = 0
    for k in range(0, th, max(8, th // 7)):                                    # brackets
        a[k:k + max(1, w), max(0, c - w):c + 2 * w, :3] = (70, 68, 64)


@functools.lru_cache(maxsize=512)
def _tex(width, height, style, lit, seed, night, face, ppm_, detail, doors, body):
    """RGBA + emission (5 channels) facade of one side, fully opaque: the body colour no longer shows
    through, because the wall itself is drawn here. Cached per distinct wall, never rebuilt per frame."""
    from .compose import STYLES
    st = STYLES.get(style, STYLES['concrete'])
    mw, mh = cap()
    tw = max(8, min(mw, int(round(width * ppm_)))); th = max(8, min(mh, int(round(height * ppm_))))
    a = np.zeros((th, tw, 5), np.uint8)
    rgba = a[..., :4]; e = a[..., 4]
    rng = np.random.default_rng(seed * 131 + face * 17 + 3)
    if st.get('windows', True) is False:                                       # rock, ice: wall only
        _wall(rgba, e, 'old' if style == 'rock' else 'concrete', rng, detail, body)
        return a
    _wall(rgba, e, style, rng, detail, body)
    floors = max(1, int(height // st['floor'])); bays = max(1, int(width // st['bay']))
    lit_rows = rng.random(floors) < .35
    for f in range(floors):
        y0 = f * st['floor'] + st['floor'] * .32; y1 = y0 + st['floor'] * st['wh']
        r0 = max(0, th - int(round(y1 * th / height))); r1 = min(th, th - int(round(y0 * th / height)))
        if r1 <= r0: r1 = min(th, r0 + 1)
        ground = (f == 0) and doors
        door_bay = int(rng.integers(0, bays)) if ground else -1
        for b in range(bays):
            cx = (b + .5) * width / bays; hw = width / bays * st['ww'] / 2
            c0 = max(0, int(round((cx - hw) * tw / width))); c1 = min(tw, max(c0 + 1, int(round((cx + hw) * tw / width))))
            if ground:
                # the ground floor: a door on some bays, a shopfront on the wide ones, a window otherwise.
                # `forced` guarantees one door per wall: a building with no entrance is a wall, and that is
                # exactly what made the shipped alley look like a corridor between two blocks
                gr1 = min(th, th - int(round(st['floor'] * .12 * th / height)))
                forced = (b == door_bay)
                roll = 0. if forced else rng.random()
                if roll < .14:
                    _door(rgba, e, r0, gr1, c0, c1, rng, night, lit_above=night and rng.random() < .7)
                    continue
                if roll < .40 and (c1 - c0) >= 6:
                    _shopfront(rgba, e, r0, gr1, c0, c1, rng, night)
                    continue
            p = lit * (1.8 if lit_rows[f] else .7)
            _window(rgba, e, r0, r1, c0, c1, rng, min(1., p), night,
                    st['win'], st['dark'], detail)
    if detail > 0:
        for k in range(max(1, bays // 3)):
            _pipe(rgba, e, min(tw - 2, int((k + .5) * tw / max(1, bays // 3)) + rng.integers(-2, 3)), rng)
    return a


def tex(width, height, style, lit, seed, night, face, body=(150, 150, 150)):
    """-> the 5-channel facade of one side, or None when the key is absent (compose.py then uses its own).
    Sizes are rounded exactly as compose.facade_tex rounds them, so the cache hits the same way. `body` is
    the block's own colour: the texture is opaque, so without it every building would come out the same."""
    st = _STATE
    if not st: return None
    return _tex(round(float(width), 1), round(float(height), 1), style, float(lit), int(seed), bool(night),
                int(face), int(st['ppm']), float(st['detail']), bool(st['doors']),
                tuple(int(c) for c in body))
