"""CONSOLE 2D: two extra night palettes and two extra silhouettes, as flat colour (never voxels).

Why this file exists on its own
-------------------------------
`engines/console/render.py` is being rewritten right now on `feature/console2d-art-redesign` and
`feature/studio-integration` (flat-colour pass, new UI, new 2D figures). Editing it here would guarantee a merge
conflict for no benefit, so this increment ships the palettes as **data plus a reversible runtime patch**: the module
changes nothing by itself, `apply()` installs a palette into the render module, `reset()` puts the original back.
`tools/console_palette_sheet.py` renders the proof through the real engine that way, without touching one line of it.

Wiring it into production is three lines, to be added once the console rewrite has landed (see
docs/DECORS_VARIATION.md, section "CONSOLE 2D"):

    from .scene_palettes import apply as apply_palette          # engines/console/render.py, ConsoleEngine.__init__
    if episode.get('palette'):
        apply_palette(episode['palette'])                       # "nuit_sepia" | "hopital_froid" | "defaut"

The palettes keep the signature of the style untouched: flat fills, two-step gradients, the green CRT screen
(`SCR`) and the gold/green UI colours are never repainted. Only the room itself changes.

Known limit of the runtime patch (visible on docs/world_variety/console2d_palettes.png): `apply()` repaints the
module constants, `SceneBuilder.wall` and `SceneBuilder.floor`, which covers the wall, the floor, the furniture and
the door. The night window with its moon, the vanishing planes of the `hallway` scene and the window frame colour
are written as literals inside `SceneBuilder.static_layer`, so they stay blue whatever the palette. Repainting them
means reading `frame` / `far` / `glow` from the palette at four places in `static_layer`; that is part of the same
three-line wiring and must wait for the console rewrite to land.
"""
import numpy as np
from PIL import Image, ImageDraw

# Each palette is the full set of flat colours a console scene is painted with. `wall` is the two-stop vertical
# gradient of the back wall, `stripe` the faint wallpaper ruling, `floor`/`floor_line` the ground, `far` the
# darker planes of a hallway, `glow` the colour of a light spill.
PALETTES = {
    'defaut': dict(
        bg=(13, 18, 42), wall=((16, 22, 52), (10, 14, 34)), stripe=4, furn=(34, 44, 92),
        floor=(8, 11, 26), floor_line=(26, 32, 66), far=((18, 24, 56), (10, 13, 32)),
        door=(122, 84, 50), door_d=(88, 58, 34), door_l=(150, 106, 66),
        frame=(46, 58, 110), glow=(120, 150, 220), dark=(4, 5, 10),
        label='Défaut (nuit bleue) — la palette livrée'),
    'nuit_sepia': dict(
        bg=(30, 22, 16), wall=((44, 32, 22), (22, 16, 11), ), stripe=5, furn=(74, 54, 36),
        floor=(20, 14, 10), floor_line=(66, 48, 32), far=((38, 27, 18), (18, 13, 9)),
        door=(126, 86, 46), door_d=(84, 54, 28), door_l=(166, 124, 72),
        frame=(96, 70, 42), glow=(226, 168, 92), dark=(9, 6, 4),
        label='Nuit sépia — ampoule jaune, maison ancienne, chaleur morte'),
    'hopital_froid': dict(
        bg=(18, 30, 32), wall=((28, 46, 48), (14, 24, 26)), stripe=3, furn=(44, 70, 72),
        floor=(12, 21, 22), floor_line=(44, 72, 74), far=((24, 40, 42), (12, 20, 22)),
        door=(92, 110, 108), door_d=(60, 76, 76), door_l=(132, 152, 148),
        frame=(60, 88, 90), glow=(150, 226, 220), dark=(5, 9, 10),
        label='Hôpital froid — néon vert-gris, carrelage, veille de nuit'),
}
NAMES = tuple(PALETTES)

# Two more silhouettes beside the shipped adult one. A silhouette is a list of flat shapes in units of the figure's
# height h and of its shoulder width w (w = h * `width`): ('rect', x0, y0, x1, y1, radius) or ('ellipse', ...),
# y measured upwards from the floor. Flat black shapes only: the console style never shades a silhouette.
SILHOUETTES = {
    'adulte': dict(width=.22, parts=[('rect', -.5, .0, .5, .82, .3), ('ellipse', -.42, .78, .42, 1.0)],
                   eyes=(.16, .90), label='Adulte (la silhouette livrée)'),
    'enfant': dict(width=.30, parts=[('rect', -.5, .0, .5, .70, .34), ('ellipse', -.56, .64, .56, 1.0),
                                     ('rect', -.74, .22, -.46, .62, .5), ('rect', .46, .22, .74, .62, .5)],
                   eyes=(.20, .86), label='Enfant — tête large, épaules basses, bras le long du corps'),
    'longue': dict(width=.15, parts=[('rect', -.5, .0, .5, .86, .22), ('ellipse', -.62, .84, .62, 1.0),
                                     ('rect', -1.3, .30, -.5, .42, .5), ('rect', .5, .30, 1.3, .42, .5)],
                   eyes=(.22, .92), label='Longue — très haute et fine, bras trop longs'),
}
SIL_NAMES = tuple(SILHOUETTES)


def palette(name):
    return PALETTES.get(name or 'defaut', PALETTES['defaut'])


def silhouette(draw, name, x, y_floor, h, eyes=True, blink=1.0, col=None):
    """draw one flat silhouette; `draw` is a PIL ImageDraw, `h` the full height in pixels"""
    sp = SILHOUETTES.get(name or 'adulte', SILHOUETTES['adulte'])
    w = h * sp['width']
    c = tuple(col or (4, 5, 10))
    for part in sp['parts']:
        kind = part[0]
        x0, y0, x1, y1 = (part[1] * w + x, y_floor - part[2] * h, part[3] * w + x, y_floor - part[4] * h)
        box = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
        if kind == 'ellipse':
            draw.ellipse(box, fill=c)
        else:
            draw.rounded_rectangle(box, radius=max(1, int(w * (part[5] if len(part) > 5 else .2))), fill=c)
    if eyes and blink > .15:
        ex, ey = sp['eyes']
        r = max(2, h * .012)
        for s in (-1, 1):
            cx = x + s * w * ex
            cy = y_floor - h * ey
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 230, 230))


def swatch(name, width=520, height=120):
    """a readable strip of a palette, for the documentation"""
    p = palette(name)
    keys = ('bg', 'wall', 'furn', 'floor', 'door', 'door_l', 'frame', 'glow')
    im = Image.new('RGB', (width, height), (10, 11, 15))
    d = ImageDraw.Draw(im)
    cw = width // len(keys)
    for i, k in enumerate(keys):
        c = p[k]
        c = c[0] if isinstance(c[0], (tuple, list)) else c
        d.rectangle([i * cw, 0, (i + 1) * cw - 2, height], fill=tuple(c))
    return im


# --------------------------------------------------------------------- reversible runtime patch
_SAVED = None


def apply(name, render_module=None):
    """install a palette into engines/console/render.py at runtime (constants, wall(), floor(), scene cache)"""
    global _SAVED
    if render_module is None:
        from . import render as render_module
    if _SAVED is None:
        _SAVED = {k: getattr(render_module, k) for k in ('BG', 'WALL', 'FURN', 'DOOR', 'DOOR_D', 'DOOR_L')}
        _SAVED['wall'] = render_module.SceneBuilder.wall
        _SAVED['floor'] = render_module.SceneBuilder.floor
    p = palette(name)
    render_module.BG = tuple(p['bg'])
    render_module.WALL = tuple(p['wall'][0])
    render_module.FURN = tuple(p['furn'])
    render_module.DOOR = tuple(p['door'])
    render_module.DOOR_D = tuple(p['door_d'])
    render_module.DOOR_L = tuple(p['door_l'])

    def wall(self):
        im = render_module.vgrad(self.CW, self.CH, tuple(p['wall'][0]), tuple(p['wall'][1]))
        a = np.asarray(im).astype(np.int16)
        x = np.arange(self.CW)[None, :, None]
        a += ((np.sin(x * .11) > .92) * int(p['stripe'])).astype(np.int16)
        return render_module.grain(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)), 4, 1)

    def floor(self, im, y0, col=None):
        d = ImageDraw.Draw(im)
        d.rectangle([0, y0, self.CW, self.CH], fill=tuple(p['floor']))
        d.line([0, y0, self.CW, y0], fill=tuple(p['floor_line']), width=3)

    render_module.SceneBuilder.wall = wall
    render_module.SceneBuilder.floor = floor
    render_module._GLOW_CACHE.clear()
    return p


def reset(render_module=None):
    """put the shipped palette back (the module is left exactly as it was found)"""
    global _SAVED
    if _SAVED is None:
        return
    if render_module is None:
        from . import render as render_module
    for k in ('BG', 'WALL', 'FURN', 'DOOR', 'DOOR_D', 'DOOR_L'):
        setattr(render_module, k, _SAVED[k])
    render_module.SceneBuilder.wall = _SAVED['wall']
    render_module.SceneBuilder.floor = _SAVED['floor']
    render_module._GLOW_CACHE.clear()
    _SAVED = None


def inventory():
    return {'palettes': {k: v['label'] for k, v in PALETTES.items()},
            'silhouettes': {k: v['label'] for k, v in SILHOUETTES.items()},
            'wired_into_production': False,
            'why': 'engines/console/render.py est en cours de refonte (console2d-art-redesign, studio-integration)'}
