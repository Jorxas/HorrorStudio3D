"""CONSOLE 2D, "aplats" art direction (V3, opt-in: episode "art": "aplat").

This is a new look for the console engine, not a change to the old one. Nothing here runs unless an episode
asks for it, so every existing episode still renders pixel for pixel (tools/regress.py, tools/regress_v2.py).

The five rules of the style (what makes it read as a deliberate 2D illustration and not as the old night-blue mush):

1. Flat fields.      Every surface is one single colour. No vertical gradient, no grain, no soft vignette.
                     Depth is read from the value step between two planes, never from a blur.
2. Limited palette.  One named palette per mood (night / alert / game / dawn), ~16 colours each: three darks,
                     two wall mids, two floor values, furniture, light, two accents, skin. `snap()` forces the
                     whole frame back onto that palette after the camera resize (ConsoleEngine.post), so the
                     camera's bicubic interpolation cannot soften an edge: the aplats survive the move. Every
                     effect applied after the snap is global (dim, flicker, fade, flash, glitch), and a global
                     operation maps a flat field to a flat field, so nothing re-introduces a gradient.
3. Ink.              One contour colour outlines characters and foreground props, at a weight proportional to
                     the figure. This single stroke is what separates this style from the old one at a glance.
4. Light is a shape. A light source is drawn as a hard-edged polygon (door wedge, window parallelogram with the
                     shadow of its mullions, screen spill), never as a blurred radial glow. Surfaces take two
                     tones, split along the light direction.
5. Silhouette first. Characters are staged against a contrasting flat value (`notan` backing band) so the
                     silhouette reads, and every shape is simplified until it is legible at thumbnail size.

Geometry note: the sets keep the exact anchors the old ones had (door_geom, floor at .755 CH, bed at .30,
desk at .84, door at .93, window at .27) because the acting layer (flat.Stage) and the quality control compute
positions from them. The look changes, the staging grid does not.
"""
import math
import numpy as np
from PIL import Image, ImageDraw

# ---------------------------------------------------------------- palettes
# Each palette is a flat, limited set. Keys are roles, not colours, so a scene can change mood without redrawing.
PALETTES = {
    'night': {
        'ink':      (11, 10, 20),
        'shadow':   (20, 19, 40),
        'wall':     (44, 43, 88),
        'wall_d':   (32, 31, 66),
        'wall_l':   (58, 56, 108),
        'floor':    (27, 26, 54),
        'floor_l':  (37, 36, 72),
        'furn':     (56, 52, 102),
        'furn_d':   (38, 35, 72),
        'furn_l':   (76, 70, 130),
        'sky':      (46, 62, 116),
        'moon':     (228, 231, 214),
        'light':    (255, 198, 112),
        'light_d':  (176, 124, 76),
        'accent':   (231, 62, 84),
        'glow':     (126, 226, 122),
        'skin':     (231, 178, 141),
        'skin_d':   (168, 118, 98),
    },
    'alert': {                                   # the room when the game punishes the player: red key light
        'ink':      (14, 8, 14),
        'shadow':   (34, 12, 24),
        'wall':     (74, 24, 44),
        'wall_d':   (52, 16, 32),
        'wall_l':   (98, 34, 56),
        'floor':    (42, 14, 28),
        'floor_l':  (58, 20, 36),
        'furn':     (86, 30, 50),
        'furn_d':   (60, 20, 36),
        'furn_l':   (112, 42, 64),
        'sky':      (60, 26, 54),
        'moon':     (228, 206, 206),
        'light':    (255, 108, 96),
        'light_d':  (186, 62, 62),
        'accent':   (255, 214, 92),
        'glow':     (255, 120, 108),
        'skin':     (226, 158, 136),
        'skin_d':   (162, 96, 88),
    },
    'game': {                                    # the console owns the room: green key light
        'ink':      (8, 16, 12),
        'shadow':   (14, 32, 24),
        'wall':     (26, 58, 46),
        'wall_d':   (18, 44, 34),
        'wall_l':   (36, 76, 58),
        'floor':    (16, 40, 32),
        'floor_l':  (24, 54, 42),
        'furn':     (34, 72, 56),
        'furn_d':   (22, 50, 38),
        'furn_l':   (48, 96, 72),
        'sky':      (22, 56, 48),
        'moon':     (214, 232, 206),
        'light':    (146, 236, 138),
        'light_d':  (92, 166, 94),
        'accent':   (236, 228, 108),
        'glow':     (146, 236, 138),
        'skin':     (206, 196, 148),
        'skin_d':   (140, 134, 102),
    },
    'dawn': {                                    # the end of the night, when the episode lets go
        'ink':      (26, 18, 30),
        'shadow':   (48, 34, 56),
        'wall':     (92, 68, 102),
        'wall_d':   (70, 50, 80),
        'wall_l':   (120, 92, 128),
        'floor':    (62, 44, 70),
        'floor_l':  (82, 60, 90),
        'furn':     (110, 80, 112),
        'furn_d':   (80, 58, 86),
        'furn_l':   (142, 108, 136),
        'sky':      (158, 136, 160),
        'moon':     (248, 240, 220),
        'light':    (255, 212, 158),
        'light_d':  (206, 152, 118),
        'accent':   (231, 98, 96),
        'glow':     (168, 226, 170),
        'skin':     (238, 192, 158),
        'skin_d':   (182, 134, 112),
    },
}

# the diegetic console screen keeps its own four greens (it is a 1989 handheld, not our art direction)
SCR = [(8, 22, 14), (34, 74, 46), (104, 164, 86), (194, 232, 146)]
# the plastic of the console body, flat
SHELL = [(232, 231, 237), (198, 196, 206), (150, 148, 160), (84, 86, 100), (52, 54, 64)]
BUTTON = (198, 54, 86)

def palette(name='night'):
    return PALETTES.get(name or 'night', PALETTES['night'])

def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)

def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

# ---------------------------------------------------------------- palette snapping (rule 2)
_SNAP_CACHE = {}

def _snap_palette(pal):
    """a 'P' mode image holding exactly the colours of this style, for Image.quantize"""
    key = tuple(sorted(pal.items()))
    if key in _SNAP_CACHE:
        return _SNAP_CACHE[key]
    cols = list(dict.fromkeys(list(pal.values()) + SCR + SHELL + [BUTTON, (255, 255, 255), (0, 0, 0)]))
    flat = [v for c in cols for v in c]
    flat += [0] * (768 - len(flat))
    p = Image.new('P', (1, 1))
    p.putpalette(flat)
    if len(_SNAP_CACHE) > 8:
        _SNAP_CACHE.clear()
    _SNAP_CACHE[key] = (p, len(cols))
    return _SNAP_CACHE[key]

def snap(img, pal):
    """force every pixel onto the palette: restores hard edges the camera's resampling softened"""
    p, _ = _snap_palette(pal)
    return img.convert('RGB').quantize(palette=p, dither=Image.Dither.NONE).convert('RGB')

# ---------------------------------------------------------------- flat primitives
def quad(d, pts, col, ink=None, w=2):
    d.polygon([tuple(p) for p in pts], fill=col)
    if ink:
        d.line([tuple(p) for p in pts] + [tuple(pts[0])], fill=ink, width=w, joint='curve')

def box(d, x0, y0, x1, y1, col, ink=None, w=2):
    d.rectangle([x0, y0, x1, y1], fill=col)
    if ink:
        d.rectangle([x0, y0, x1, y1], outline=ink, width=w)

def rbox(d, x0, y0, x1, y1, r, col, ink=None, w=2):
    d.rounded_rectangle([x0, y0, x1, y1], radius=max(1, int(r)), fill=col)
    if ink:
        d.rounded_rectangle([x0, y0, x1, y1], radius=max(1, int(r)), outline=ink, width=w)

def disc(d, cx, cy, r, col, ink=None, w=2):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    if ink:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ink, width=w)

def wedge(d, x0, x1, y_top, y_bot, spread, col):
    """hard-edged cone of light falling towards the camera (rule 4): a trapezoid, nothing blurred"""
    d.polygon([(x0, y_top), (x1, y_top), (x1 + spread, y_bot), (x0 - spread, y_bot)], fill=col)

def clip_half(pts, p0, n):
    """Sutherland-Hodgman: the part of a polygon on the +n side of the line through p0.

    This is how a flat surface takes its second tone: the terminator is a straight cut whose direction is the
    key light, so the body, the head (a pieslice on the same angle) and the props all break on the same line."""
    out = []
    N = len(pts)
    def side(p): return (p[0] - p0[0]) * n[0] + (p[1] - p0[1]) * n[1]
    for i in range(N):
        a, b = pts[i], pts[(i + 1) % N]
        sa, sb = side(a), side(b)
        if sa >= 0:
            out.append(tuple(a))
        if (sa >= 0) != (sb >= 0) and abs(sa - sb) > 1e-9:
            t = sa / (sa - sb)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out

def shadow_of(pts, light, bias=0.12):
    """the shaded part of a flat shape: everything on the far side of the terminator"""
    lx, ly = light
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    ext = max(max(abs(p[0] - cx) for p in pts), max(abs(p[1] - cy) for p in pts))
    p0 = (cx + lx * ext * bias, cy + ly * ext * bias)
    return clip_half(pts, p0, (-lx, -ly))

def inner_quad(pts, away, k):
    """the shadow part of a flat quad: the two corners on the far side of the light pulled towards the lit side"""
    a, b, c, e = [np.asarray(p, np.float32) for p in pts]
    if away == 'right':
        return [tuple(b), tuple(c), tuple(c + (e - c) * k), tuple(b + (a - b) * k)]
    if away == 'left':
        return [tuple(a), tuple(e), tuple(e + (c - e) * k), tuple(a + (b - a) * k)]
    if away == 'bottom':
        return [tuple(e), tuple(c), tuple(c + (b - c) * k), tuple(e + (a - e) * k)]
    return [tuple(a), tuple(b), tuple(b + (c - b) * k), tuple(a + (e - a) * k)]

def rim_arc(d, bbox, lang, half, col, w, lo=180.0, hi=360.0):
    """a rim stroke on a shape that only covers part of its circle.

    Hair is a chord over 180..360 of the head ellipse: an arc placed blindly at the light angle lands across the
    face when the key light comes from below (which, in this series, it usually does -- the console screen).
    Clipping the lit window to the shape's own range means a light from below simply puts no rim on the hair."""
    best = None
    for k in (-360.0, 0.0, 360.0):
        s, e = max(lang - half + k, lo), min(lang + half + k, hi)
        if e - s > 4 and (best is None or e - s > best[1] - best[0]):
            best = (s, e)
    if best:
        d.arc(bbox, best[0], best[1], fill=col, width=w)

def light_dir(sc, typ):
    """unit vector in canvas space pointing from the subject towards the key light (rule 4)"""
    key = sc.get('key')
    if not key:
        if typ == 'door':
            key = 'door'
        elif typ == 'room':
            key = 'screen' if sc.get('console_on_bed', True) else ('door' if sc.get('light_under') else 'window')
        else:
            key = 'front'
    return {
        'door':   (0.84, 0.54),      # the warm strip under the door, low and to the side
        'window': (-0.80, -0.60),    # the moon, high and to the left
        'screen': (-0.42, 0.91),     # the console on the bed, from below: the horror lighting of the series
        'lamp':   (0.70, -0.71),
        'front':  (0.0, -1.0),
        'none':   (0.0, -1.0),
    }.get(key, (-0.42, 0.91))

# ---------------------------------------------------------------- sets
class AplatSets:
    """the flat sets. One method per scene type; geometry matches the legacy sets so the staging grid holds."""

    def __init__(self, CW, CH, pal):
        self.CW, self.CH = CW, CH
        self.pal = pal
        self.ink_w = max(2, int(min(CW, CH) * 0.0035))

    # -------- shared furniture of the night
    def _baseboard(self, d, y, pal):
        d.rectangle([0, y, self.CW, y + self.ink_w * 2], fill=pal['ink'])

    def _poster(self, d, x0, y0, w, h, pal):
        box(d, x0, y0, x0 + w, y0 + h, pal['wall_d'], pal['ink'], self.ink_w)
        # a flat graphic: a single eye, the motif of the series
        cx, cy = x0 + w / 2, y0 + h * 0.46
        d.polygon([(cx - w * 0.3, cy), (cx, cy - h * 0.17), (cx + w * 0.3, cy), (cx, cy + h * 0.17)], fill=pal['accent'])
        disc(d, cx, cy, w * 0.09, pal['ink'])
        d.rectangle([x0 + w * 0.2, y0 + h * 0.76, x0 + w * 0.8, y0 + h * 0.82], fill=pal['wall_l'])

    def _window(self, d, x0, y0, w, h, pal, floor_y=None, moonlight=True):
        """flat night sky + hard moon; the light it throws is a parallelogram on the floor with mullion shadows"""
        if moonlight and floor_y is not None:
            # rule 4: the shape of the light, skewed away from the window, with the cross of the frame in it
            sk = w * 1.15
            quad(d, [(x0 + w * 0.05, y0 + h), (x0 + w * 0.95, y0 + h),
                     (x0 + w * 0.95 + sk, floor_y + self.CH * 0.1), (x0 + w * 0.05 + sk, floor_y + self.CH * 0.1)],
                 pal['floor_l'])
            # the mullions cut two dark bars across that shape
            for fx in (0.5,):
                xa = x0 + w * fx
                d.polygon([(xa - w * 0.035, y0 + h), (xa + w * 0.035, y0 + h),
                           (xa + w * 0.035 + sk, floor_y + self.CH * 0.1), (xa - w * 0.035 + sk, floor_y + self.CH * 0.1)], fill=pal['floor'])
        box(d, x0, y0, x0 + w, y0 + h, pal['sky'], pal['ink'], self.ink_w)
        disc(d, x0 + w * 0.70, y0 + h * 0.30, min(w, h) * 0.17, pal['moon'])
        # a few flat stars, seeded by position (deterministic)
        for i in range(7):
            sx = x0 + w * ((i * 0.37 + 0.11) % 1.0)
            sy = y0 + h * ((i * 0.61 + 0.07) % 0.62)
            d.rectangle([sx, sy, sx + self.ink_w, sy + self.ink_w], fill=pal['moon'])
        fw = max(self.ink_w * 2, int(w * 0.035))
        d.rectangle([x0 + w / 2 - fw / 2, y0, x0 + w / 2 + fw / 2, y0 + h], fill=pal['ink'])
        d.rectangle([x0, y0 + h / 2 - fw / 2, x0 + w, y0 + h / 2 + fw / 2], fill=pal['ink'])
        d.rectangle([x0 - self.ink_w, y0 + h, x0 + w + self.ink_w, y0 + h + self.ink_w * 3], fill=pal['furn_d'])

    def _bed(self, d, pal):
        """flat bed: mattress, blanket with a folded corner, pillow, headboard. Anchored on the legacy .30 bed spot."""
        CW, CH = self.CW, self.CH
        iw = self.ink_w
        x0, x1 = CW * 0.055, CW * 0.615
        top = CH * 0.620
        bot = CH * 0.790
        # headboard (left, against the wall)
        box(d, x0 - CW * 0.015, top - CH * 0.115, x0 + CW * 0.055, bot, pal['furn_d'], pal['ink'], iw)
        # mattress block
        quad(d, [(x0, top), (x1, top - CH * 0.012), (x1, bot - CH * 0.012), (x0, bot)], pal['furn'], pal['ink'], iw)
        # blanket: one flat field, a lighter step, with a hard folded corner
        fold = CW * 0.11
        quad(d, [(x0 + CW * 0.10, top + CH * 0.004), (x1, top - CH * 0.008),
                 (x1, bot - CH * 0.030), (x0 + CW * 0.10, bot - CH * 0.022)], pal['furn_l'], pal['ink'], iw)
        quad(d, [(x0 + CW * 0.10, top + CH * 0.004), (x0 + CW * 0.10 + fold, top + CH * 0.002),
                 (x0 + CW * 0.10 + fold * 0.55, top + CH * 0.034), (x0 + CW * 0.10, top + CH * 0.030)], pal['furn'], pal['ink'], iw)
        # pillow
        rbox(d, x0 + CW * 0.012, top - CH * 0.030, x0 + CW * 0.135, top + CH * 0.028,
             CH * 0.014, pal['wall_l'], pal['ink'], iw)

    def _desk(self, d, pal, lamp=True):
        CW, CH = self.CW, self.CH
        iw = self.ink_w
        x0, x1 = CW * 0.735, CW * 0.955
        top = CH * 0.545
        box(d, x0, top, x1, top + CH * 0.022, pal['furn_l'], pal['ink'], iw)
        box(d, x0 + CW * 0.012, top + CH * 0.022, x0 + CW * 0.042, CH * 0.755, pal['furn_d'], pal['ink'], iw)
        box(d, x1 - CW * 0.042, top + CH * 0.022, x1 - CW * 0.012, CH * 0.755, pal['furn_d'], pal['ink'], iw)
        if lamp:
            lx = CW * 0.820
            d.rectangle([lx - CW * 0.006, CH * 0.455, lx + CW * 0.006, top], fill=pal['furn_d'])
            quad(d, [(lx - CW * 0.045, CH * 0.455), (lx + CW * 0.045, CH * 0.455),
                     (lx + CW * 0.028, CH * 0.418), (lx - CW * 0.028, CH * 0.418)], pal['furn_l'], pal['ink'], iw)
            # the lamp's light: a hard cone, two flat steps
            wedge(d, lx - CW * 0.040, lx + CW * 0.040, CH * 0.457, top, CW * 0.055, pal['light_d'])
            wedge(d, lx - CW * 0.022, lx + CW * 0.022, CH * 0.457, top, CW * 0.028, pal['light'])

    def door_quad(self, geom):
        x0, y0, x1, y1 = geom
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def draw_door(self, d, geom, pal, col=None, ajar=0.0):
        """a flat door: frame, two panels as value steps, a hard handle. No wood gradient."""
        x0, y0, x1, y1 = geom
        iw = self.ink_w
        dw = x1 - x0
        fr = int(dw * 0.075)
        base = tuple(col) if col else pal['furn']
        box(d, x0 - fr, y0 - fr, x1 + fr, y1, pal['ink'])
        box(d, x0, y0, x1, y1, base, pal['ink'], iw)
        # the leaf takes two tones split by the key light coming from the side
        d.polygon([(x0 + dw * 0.60, y0), (x1, y0), (x1, y1), (x0 + dw * 0.60, y1)], fill=shade(base, 0.76))
        m = dw * 0.14
        mid = y0 + (y1 - y0) * 0.45
        for (a, b) in ((y0 + m, mid - m * 0.5), (mid + m * 0.5, y1 - m)):
            box(d, x0 + m, a, x1 - m, b, shade(base, 1.14), pal['ink'], max(1, iw - 1))
            d.polygon([(x0 + dw * 0.60, a), (x1 - m, a), (x1 - m, b), (x0 + dw * 0.60, b)], fill=shade(base, 0.88))
        hx = x1 - dw * 0.13
        hy = y0 + (y1 - y0) * 0.55
        disc(d, hx, hy, dw * 0.052, pal['wall_l'], pal['ink'], iw)
        if ajar > 0.02:
            d.rectangle([x0, y0, x0 + dw * ajar * 0.35, y1], fill=pal['ink'])

    def under_door(self, d, geom, pal, col, feet=False, feet_x=0.0, flick=1.0):
        """rule 4: the strip of light under a door is a shape, not a glow"""
        x0, y0, x1, y1 = geom
        spread = (x1 - x0) * 0.95
        c_out = mix(pal['floor'], col, 0.45 * flick)
        c_in = mix(pal['floor'], col, 0.80 * flick)
        wedge(d, x0 + 4, x1 - 4, y1, self.CH, spread, c_out)
        wedge(d, x0 + (x1 - x0) * 0.18, x1 - (x1 - x0) * 0.18, y1, self.CH, spread * 0.58, c_in)
        d.rectangle([x0, y1 - self.ink_w * 2, x1, y1 + self.ink_w], fill=mix(col, (255, 255, 255), 0.35 * flick))
        if feet:
            fx = (x0 + x1) / 2 + feet_x * (x1 - x0)
            fw = (x1 - x0) * 0.075
            for s in (-1, 1):
                cx = fx + s * (x1 - x0) * 0.12
                d.polygon([(cx - fw, y1), (cx + fw, y1),
                           (cx + fw * 3.4 + s * spread * 0.2, self.CH), (cx - fw * 3.4 + s * spread * 0.2, self.CH)], fill=pal['ink'])
                d.rectangle([cx - fw, y1 - self.ink_w * 2, cx + fw, y1 + self.ink_w], fill=pal['ink'])

    def notan(self, d, x_rel, y_floor, pal, up=True):
        """staging aid (rule 5): a hard-edged band of a contrasting flat value behind the subject,
        so a dark silhouette never sits on a dark wall. One value step, never a glow."""
        CW, CH = self.CW, self.CH
        cx = CW * x_rel
        w = CW * 0.30
        col = pal['wall_l'] if up else pal['wall_d']
        d.polygon([(cx - w * 0.5, 0), (cx + w * 0.5, 0),
                   (cx + w * 0.62, y_floor), (cx - w * 0.62, y_floor)], fill=col)

    # -------- the scene types
    def room(self, sc, door_geom=None):
        CW, CH = self.CW, self.CH
        pal = self.pal
        im = Image.new('RGB', (CW, CH), pal['wall'])
        d = ImageDraw.Draw(im)
        floor_y = int(CH * 0.755)                 # same floor as flat.Stage for 'room'
        # the wall takes two flat values: the side away from the window falls one step
        d.polygon([(CW * 0.52, 0), (CW, 0), (CW, floor_y), (CW * 0.58, floor_y)], fill=pal['wall_d'])
        if sc.get('notan', True):
            self.notan(d, float(sc.get('notan_x', 0.5)), floor_y, pal, up=True)
        d.rectangle([0, floor_y, CW, CH], fill=pal['floor'])
        wx0, wy0 = int(CW * 0.145), int(CH * 0.215)
        ww, wh = int(CW * 0.255), int(CH * 0.200)
        self._window(d, wx0, wy0, ww, wh, pal, floor_y=floor_y, moonlight=sc.get('moonlight', True))
        self._poster(d, int(CW * 0.615), int(CH * 0.205), int(CW * 0.115), int(CH * 0.150), pal)
        self._baseboard(d, floor_y, pal)
        if door_geom is not None and sc.get('door', True):
            self.draw_door(d, door_geom, pal)
        self._desk(d, pal, lamp=sc.get('lamp', True))
        self._bed(d, pal)
        return im

    def door_scene(self, sc, geom):
        CW, CH = self.CW, self.CH
        pal = self.pal
        im = Image.new('RGB', (CW, CH), pal['wall'])
        d = ImageDraw.Draw(im)
        floor_y = int(CH * 0.80)                  # same floor as flat.Stage for 'door'
        d.polygon([(0, 0), (CW * 0.22, 0), (CW * 0.26, floor_y), (0, floor_y)], fill=pal['wall_d'])
        d.polygon([(CW * 0.82, 0), (CW, 0), (CW, floor_y), (CW * 0.78, floor_y)], fill=pal['wall_d'])
        d.rectangle([0, floor_y, CW, CH], fill=pal['floor'])
        self._baseboard(d, floor_y, pal)
        self.draw_door(d, geom, pal, sc.get('color'))
        return im

    def hallway(self, sc):
        """one-point perspective built from flat planes: four trapezoids and a hard doorway at the end"""
        CW, CH = self.CW, self.CH
        pal = self.pal
        im = Image.new('RGB', (CW, CH), pal['shadow'])
        d = ImageDraw.Draw(im)
        cx = CW // 2
        iw = self.ink_w
        ex, ey0, ey1 = CW * 0.18, CH * 0.32, CH * 0.66
        d.polygon([(0, 0), (cx - ex, ey0), (cx - ex, ey1), (0, CH)], fill=pal['wall'])
        d.polygon([(CW, 0), (cx + ex, ey0), (cx + ex, ey1), (CW, CH)], fill=pal['wall_d'])
        d.polygon([(0, 0), (cx - ex, ey0), (cx + ex, ey0), (CW, 0)], fill=pal['shadow'])
        d.polygon([(0, CH), (cx - ex, ey1), (cx + ex, ey1), (CW, CH)], fill=pal['floor'])
        d.rectangle([cx - ex, ey0, cx + ex, ey1], fill=pal['wall_l'])
        # the ink lines of the perspective: this is what makes it read as a drawing
        for p in ((0, 0, cx - ex, ey0), (CW, 0, cx + ex, ey0), (0, CH, cx - ex, ey1), (CW, CH, cx + ex, ey1)):
            d.line(p, fill=pal['ink'], width=iw)
        d.rectangle([cx - ex, ey0, cx + ex, ey1], outline=pal['ink'], width=iw)
        dw = CW * 0.075
        box(d, cx - dw, ey0 + (ey1 - ey0) * 0.22, cx + dw, ey1, pal['furn'], pal['ink'], iw)
        if sc.get('light_under'):
            col = {'warm': pal['light'], 'red': pal['accent'], 'green': pal['glow']}.get(sc.get('light_under'), pal['light'])
            wedge(d, cx - dw, cx + dw, ey1, CH, CW * 0.22, mix(pal['floor'], col, 0.5))
        # two flat ceiling lamps, as shapes
        for k, fy in ((0, 0.10), (1, 0.20)):
            w = CW * (0.055 - k * 0.018)
            d.rectangle([cx - w, CH * fy, cx + w, CH * fy + CH * 0.012], fill=pal['light_d'])
        return im

    def window_scene(self, sc):
        CW, CH = self.CW, self.CH
        pal = self.pal
        im = Image.new('RGB', (CW, CH), pal['wall'])
        d = ImageDraw.Draw(im)
        floor_y = int(CH * 0.80)
        d.rectangle([0, floor_y, CW, CH], fill=pal['floor'])
        self._window(d, int(CW * 0.20), int(CH * 0.25), int(CW * 0.60), int(CH * 0.40), pal, floor_y=floor_y)
        self._baseboard(d, floor_y, pal)
        return im

    def face_bg(self, sc):
        pal = self.pal
        im = Image.new('RGB', (self.CW, self.CH), pal['shadow'])
        d = ImageDraw.Draw(im)
        # a hard graphic backdrop: one off-centre band, so the head always has a value to sit against
        d.polygon([(self.CW * 0.08, 0), (self.CW * 0.72, 0), (self.CW * 0.60, self.CH), (0, self.CH)], fill=pal['wall_d'])
        return im

    def face_closeup(self, im, sc, T, u, g):
        """the close-up: one big head in aplats, lit by a hard key, with the shared expression table"""
        from .figure2d import face as draw_face
        CW, CH = self.CW, self.CH
        pal = self.pal
        d = ImageDraw.Draw(im)
        iw = self.ink_w * 2
        key = {'green': pal['glow'], 'orange': pal['light'], 'red': pal['accent'], 'blue': pal['sky'],
               'warm': pal['light']}.get(sc.get('light', 'green'), pal['glow'])
        cx, cy = CW * 0.5, CH * 0.50
        r = min(CW, CH) * 0.205                                  # small enough that the shoulders stay in frame
        lang = math.degrees(math.atan2(0.86, -0.5))              # keyed from below-left: the screen in his hands
        skin = mix(tuple(sc.get('skin') or pal['skin']), key, 0.18)
        skin_s = mix(skin, pal['shadow'], 0.32)                  # a close-up carries less contrast than a figure
        skin_r = mix(skin, key, 0.22)
        hair = tuple(sc.get('hair') or (26, 24, 44))
        hood = mix(tuple(sc.get('hood') or pal['furn_l']), key, 0.1)
        # shoulders / hood as one flat mass, so the head is never floating
        quad(d, [(cx - r * 1.9, CH), (cx - r * 1.45, cy + r * 1.0),
                 (cx + r * 1.45, cy + r * 1.0), (cx + r * 1.9, CH)], hood, pal['ink'], iw)
        d.polygon(inner_quad([(cx - r * 1.9, CH), (cx - r * 1.45, cy + r * 1.0),
                              (cx + r * 1.45, cy + r * 1.0), (cx + r * 1.9, CH)], 'right', 0.46),
                  fill=mix(hood, pal['shadow'], 0.45))
        # neck
        box(d, cx - r * 0.34, cy + r * 0.72, cx + r * 0.34, cy + r * 1.1, skin_s, pal['ink'], iw)
        hb = [cx - r, cy - r * 1.08, cx + r, cy + r * 1.08]
        d.ellipse(hb, fill=skin)
        d.pieslice(hb, lang + 92, lang + 268, fill=skin_s)
        d.arc(hb, lang - 44, lang + 44, fill=skin_r, width=max(3, iw))
        d.ellipse(hb, outline=pal['ink'], width=iw)
        d.chord([cx - r * 1.05, cy - r * 1.24, cx + r * 1.05, cy + r * 0.26], 180, 360, fill=hair)
        rim_arc(d, [cx - r * 1.05, cy - r * 1.24, cx + r * 1.05, cy + r * 0.26], lang, 50,
                mix(hair, key, 0.3), max(3, int(iw * 1.3)))
        d.chord([cx - r * 1.05, cy - r * 1.24, cx + r * 1.05, cy + r * 0.26], 180, 360, outline=pal['ink'], width=iw)
        sample = {'face': sc.get('expression', 'scared'),
                  'blink': (g % 4) < 0.12 and sc.get('expression') != 'closed',
                  'talking': sc.get('talking', False),
                  'look_x': {'left': -1.0, 'right': 1.0}.get(sc.get('look', 'center'), 0.0)}
        draw_face(d, cx, cy, r, sample, g, pal, pal['ink'], max(2, self.ink_w), lang)
        # the key light itself, as a hard shape at the bottom of the frame (the screen he is staring into)
        if sc.get('key_shape', True):
            d.polygon([(cx - r * 0.9, CH), (cx + r * 0.9, CH), (cx + r * 0.45, CH - r * 0.5), (cx - r * 0.45, CH - r * 0.5)],
                      fill=mix(hood, key, 0.55))

    def silhouette(self, d, x, y_floor, h, g, pal, eyes=True):
        """a flat silhouette: the shape alone carries it, so the shape has to be built (shoulders, neck, head)"""
        w = h * 0.24
        col = pal['ink']
        quad(d, [(x - w * 0.52, y_floor), (x - w * 0.46, y_floor - h * 0.70),
                 (x - w * 0.60, y_floor - h * 0.76), (x - w * 0.22, y_floor - h * 0.84),
                 (x + w * 0.22, y_floor - h * 0.84), (x + w * 0.60, y_floor - h * 0.76),
                 (x + w * 0.46, y_floor - h * 0.70), (x + w * 0.52, y_floor)], col)
        d.ellipse([x - w * 0.40, y_floor - h, x + w * 0.40, y_floor - h * 0.80], fill=col)
        if eyes and (g * 1.3) % 3 > 0.15:
            for s in (-1, 1):
                r_ = max(2, h * 0.012)
                d.ellipse([x + s * w * 0.17 - r_, y_floor - h * 0.91 - r_,
                           x + s * w * 0.17 + r_, y_floor - h * 0.91 + r_], fill=pal['moon'])

    def console_body(self, im, sc, T, u, g, full_screen=False):
        """the handheld, in aplats: flat shell, ink contour, hard screen bezel. The screen itself stays pixel."""
        from .render import screen_on_canvas
        CW, CH = self.CW, self.CH
        pal = self.pal
        d = ImageDraw.Draw(im)
        iw = self.ink_w
        if full_screen:
            sw = int(min(CW * 0.84, CH * 0.72 * 160 / 144))
            sh = int(sw * 144 / 160)
            x0, y0 = (CW - sw) // 2, int(CH * 0.45 - sh / 2)
            box(d, x0 - iw * 6, y0 - iw * 6, x0 + sw + iw * 6, y0 + sh + iw * 6, SHELL[4], pal['ink'], iw)
            im.paste(screen_on_canvas(sc.get('screen', {}), T, u, g, sw, sh), (x0, y0))
            # the screen spills onto the room as a hard shape, not a blur
            d.polygon([(x0, y0 + sh), (x0 + sw, y0 + sh), (x0 + sw + CW * 0.13, CH), (x0 - CW * 0.13, CH)],
                      fill=mix(pal['floor'], pal['glow'], 0.22))
            return
        bw = int(min(CW * 0.86, CH * 0.53))
        bh = int(bw * 1.62)
        x0 = (CW - bw) // 2 + int(CW * float(sc.get('x_offset', 0)))
        y0 = int(CH * 0.17)
        # contact shadow: a flat offset shape
        d.rounded_rectangle([x0 + bw * 0.05, y0 + bh * 0.04, x0 + bw * 1.05, y0 + bh * 1.04],
                            radius=bw // 9, fill=pal['shadow'])
        rbox(d, x0, y0, x0 + bw, y0 + bh, bw // 9, SHELL[1], pal['ink'], iw * 2)
        d.polygon([(x0 + bw * 0.62, y0 + bh * 0.02), (x0 + bw, y0 + bh * 0.10),
                   (x0 + bw, y0 + bh * 0.96), (x0 + bw * 0.62, y0 + bh * 0.99)], fill=SHELL[2])
        bz = int(bw * 0.07)
        sx0, sy0, sx1 = x0 + bz, y0 + int(bw * 0.07), x0 + bw - bz
        sy1 = sy0 + int((sx1 - sx0) * 0.86)
        rbox(d, sx0, sy0, sx1, sy1, bw // 24, SHELL[3], pal['ink'], iw)
        ix0, iy0 = sx0 + int(bw * 0.07), sy0 + int(bw * 0.06)
        iw_ = sx1 - sx0 - int(bw * 0.14)
        ih = int(iw_ * 144 / 160)
        led_on = sc.get('led', True) and (int(g * 2) % 2 == 0 or not sc.get('led_blink'))
        disc(d, sx0 + bw * 0.035, sy0 + bw * 0.04, bw * 0.014, pal['accent'] if led_on else shade(pal['accent'], 0.4))
        im.paste(screen_on_canvas(sc.get('screen', {}), T, u, g, iw_, ih), (ix0, iy0))
        d.rectangle([ix0 - iw, iy0 - iw, ix0 + iw_ + iw, iy0 + ih + iw], outline=pal['ink'], width=iw)
        # controls, as flat shapes with ink
        cy = sy1 + int(bh * 0.17)
        cx = x0 + int(bw * 0.22)
        a = int(bw * 0.045)
        box(d, cx - a * 3, cy - a, cx + a * 3, cy + a, SHELL[4], pal['ink'], iw)
        box(d, cx - a, cy - a * 3, cx + a, cy + a * 3, SHELL[4], pal['ink'], iw)
        for k, (bx, by) in enumerate(((x0 + bw * 0.66, cy + a * 0.6), (x0 + bw * 0.84, cy - a * 0.6))):
            pressed = sc.get('press') in (('B', 'A')[k], 'AB') and int(T * 6) % 2 == 0
            disc(d, bx, by, a * (1.75 if not pressed else 1.55), BUTTON if not pressed else shade(BUTTON, 0.72), pal['ink'], iw)
        for k in range(2):
            px = x0 + bw * (0.36 + k * 0.18)
            py = cy + int(bh * 0.15)
            rbox(d, px - bw * 0.06, py - a * 0.4, px + bw * 0.06, py + a * 0.4, a * 0.4, SHELL[2], pal['ink'], max(1, iw - 1))
        for i in range(5):
            sy = cy + bh * 0.125 + i * bh * 0.016
            d.line([x0 + bw * 0.74, sy, x0 + bw * 0.88, sy], fill=SHELL[3], width=max(1, iw - 1))

# ---------------------------------------------------------------- overlap with the expressive flat faces (lot 4)
# "console2d-expressivity" (already integrated) draws its expressive faces through flat.face / expression.py,
# reached from the original SceneBuilder path and from ConsoleEngine.face_expressive. The aplat path draws its
# own faces (figure2d.face, AplatSets.face_closeup) and never looks at "faces": "expressive". Git merges the two
# without a conflict, so an episode asking for both would just quietly lose one. This says so, in French.
# It is the exact mirror of engines/pixel3d/art.notices(). See docs/RAPPORT_INTEGRATION_ART_OPTIN_20261024.md.
def notices(episode, art, cast=None):
    """French messages for an episode that asks for the aplat art direction and for the expressive faces.

    `art` is the resolved art name ('' = off). Returns the messages, empty when the art direction is off or when
    nothing asks for the expressive faces. Pure: it reads, it decides nothing."""
    out = []
    if art != 'aplat': return out
    asks = []
    if str((episode or {}).get('faces') or '') == 'expressive': asks.append('épisode')
    for i, sh in enumerate((episode or {}).get('shots') or []):
        sc = sh.get('scene') if isinstance(sh.get('scene'), dict) else {}
        if str(sh.get('faces') or sc.get('faces') or '') == 'expressive': asks.append(f'plan {i}')
    for cid, lk in sorted((cast or {}).items()):
        if str((lk or {}).get('faces') or '') == 'expressive': asks.append(cid)
    if asks:
        out.append('visages : ' + ', '.join(asks) + ' demande « faces: expressive », mais la direction artistique '
                   '« aplat » dessine ses propres visages (figure2d / face_closeup) : le visage expressif du lot '
                   'CONSOLE 2D est ignoré. Le choix final du style reste humain.')
    return out
