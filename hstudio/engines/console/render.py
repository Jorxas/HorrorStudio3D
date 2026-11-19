"""CONSOLE engine ("Ne mets pas pause"): flat night-blue vector illustration + green pixel console screen.

Scenes (shot["scene"]["type"]): console, screen, door, room, rule_card, face, split, hallway, window, black.
Screen contents (160x144, 4 greens, scanlines): menu, text, room, door, eyes, static, warning, level, pause, face, timer.
Camera: 2D push/pull/pan/drift/handheld + shake. Formats 9:16 and 16:9.
"""
import math, numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from ..common import build_subs, active_sub, hearts_at, font
from ...paths import FONT_PIXEL, FONT_MONTSERRAT, FONT_BEBAS, FONT_MONO

# ---------------------------------------------------------------- palette (catalogue)
BG = (13, 18, 42); WALL = (22, 29, 62); FURN = (34, 44, 92)
GOLD = (255, 201, 60); GREEN_UI = (156, 255, 122); ORANGE = (255, 128, 64); RED = (255, 77, 94)
WHITE = (240, 240, 245); GREY = (200, 202, 212)
SCR = [(8, 22, 14), (34, 74, 46), (104, 164, 86), (194, 232, 146)]
DOOR = (122, 84, 50); DOOR_D = (88, 58, 34); DOOR_L = (150, 106, 66)
LABEL_COLORS = {'green': GREEN_UI, 'orange': ORANGE, 'red': RED, 'gold': GOLD, 'white': WHITE, 'blue': (130, 170, 255)}

def clamp(x, a=0., b=1.): return max(a, min(b, x))
def ease(t): t = clamp(t); return t * t * (3 - 2 * t)
def lerp(a, b, t): return a + (b - a) * t
def val(v, u, d=None):
    if v is None: return d
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v): return lerp(v[0], v[1], ease(u))
    return v
def mix(c1, c2, t): return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))
def rnd(seed): return np.random.default_rng(seed)

def cam_subjects(on):
    """the names written in a shot's `camera.on`, as a list.

    `docs/FORMAT_EPISODE.md` writes the subjects of a plan as a list -- `"on": ["lea", "tom"]` -- and a single
    name as a bare string. Both forms are read here, once, so the framing (`scene_at`) and the quality control
    (`qc_observe`) can never disagree again. A name may also be a place, a door or an object: this returns it,
    and the caller keeps only the names it knows as characters."""
    if isinstance(on, str): return [on]
    if isinstance(on, (list, tuple)): return [a for a in on if isinstance(a, str)]
    return []

def vgrad(w, h, top, bot):
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    a = np.array(top, np.float32) * (1 - t) + np.array(bot, np.float32) * t
    return Image.fromarray(np.repeat(a, w, 1).astype(np.uint8))

def radial(w, h, cx, cy, r, col, alpha=1.0, power=2.0):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / max(r, 1)
    a = np.clip(1 - d, 0, 1) ** power * alpha
    out = np.zeros((h, w, 4), np.uint8); out[..., :3] = col; out[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(out)

_GLOW_CACHE = {}
def _cached_radial(w, h, cx, cy, r, col, alpha=1.0, power=2.0):
    k = ('rad', w, h, int(cx), int(cy), int(r), col, alpha, power)
    if k not in _GLOW_CACHE: _GLOW_CACHE[k] = radial(w, h, cx, cy, r, col, alpha, power)
    return _GLOW_CACHE[k]

def glow_layer(size, draw_fn, blur, color=None, key=None):
    """blurred mask layer; blurred at 1/4 resolution (fast) and cached when a key is given"""
    if key is not None and (key, size) in _GLOW_CACHE: return _GLOW_CACHE[(key, size)]
    q = 4; sm = (max(1, size[0] // q), max(1, size[1] // q))
    m = Image.new('L', sm, 0)
    class _Sc:                                   # scale drawing calls to the small mask
        def __init__(s, d): s.d = d
        def __getattr__(s, n):
            f = getattr(s.d, n)
            def w(xy, *a, **k):
                xy = [v / q for v in xy] if isinstance(xy, (list, tuple)) and xy and not isinstance(xy[0], (list, tuple)) else [(x / q, y / q) for x, y in xy]
                if 'radius' in k: k['radius'] = max(1, int(k['radius'] / q))
                if 'width' in k: k['width'] = max(1, int(k['width'] / q))
                return f(xy, *a, **k)
            return w
    draw_fn(_Sc(ImageDraw.Draw(m))); m = m.filter(ImageFilter.GaussianBlur(max(1, blur / q))).resize(size, Image.BILINEAR)
    lay = Image.new('RGBA', size, (color or (255, 255, 255)) + (0,)); lay.putalpha(m)
    if key is not None:
        if len(_GLOW_CACHE) > 64: _GLOW_CACHE.clear()
        _GLOW_CACHE[(key, size)] = lay
    return lay

def grain(img, amt=10, seed=0):
    a = np.asarray(img).astype(np.int16)
    n = rnd(seed).integers(-amt, amt + 1, a.shape[:2])[..., None]
    return Image.fromarray(np.clip(a + n, 0, 255).astype(np.uint8))

# ---------------------------------------------------------------- pixel screen (160x144)
def screen_image(sp, T, u, g):
    """-> RGB 160x144 in the 4 greens"""
    W_, H_ = 160, 144
    im = Image.new('RGB', (W_, H_), SCR[0]); d = ImageDraw.Draw(im); d.fontmode = '1'
    f8 = font(FONT_PIXEL, 8)
    typ = sp.get('type', 'menu')
    def txt(x, y, s, c=SCR[3]): d.text((x, y), s, font=f8, fill=c)
    def ctext(y, s, c=SCR[3]):
        w = d.textlength(s, font=f8); d.text(((W_ - w) / 2, y), s, font=f8, fill=c)
    if typ == 'menu':
        ctext(8, sp.get('title', 'SAUVEGARDES').upper()[:18]); d.line([6, 20, W_ - 7, 20], fill=SCR[2])
        items = sp.get('items', ['FICHIER 1']); cur = int(sp.get('cursor', 0))
        d.rectangle([8, 28, W_ - 9, 28 + 22 * len(items[:4]) + 8], outline=SCR[2])
        for i, it in enumerate(items[:4]):
            y = 36 + i * 22; c = SCR[3] if i == cur else SCR[2]
            txt(16, y, it.upper()[:14], c)
            if i == cur and int(g * 3) % 2 == 0: txt(W_ - 22, y, '<', SCR[3])
            if sp.get('heart') == i: d.polygon([(W_ - 30, y + 2), (W_ - 27, y), (W_ - 24, y + 3), (W_ - 21, y), (W_ - 18, y + 2), (W_ - 24, y + 8)], fill=SCR[2])
    elif typ == 'text':
        s = str(sp.get('text', '')).upper()
        if sp.get('typewriter', True): s = s[:int(len(s) * clamp(T / max(.3, float(sp.get('type_time', 1.6)))))]
        d.rectangle([4, 70, W_ - 5, H_ - 6], fill=SCR[0], outline=SCR[3])
        words = s.split(); lines = []; cur = ''
        for w in words:
            if len(cur) + len(w) + 1 > 17: lines.append(cur); cur = w
            else: cur = (cur + ' ' + w).strip()
        if cur: lines.append(cur)
        for i, l in enumerate(lines[-5:]): txt(10, 78 + i * 12, l)
        if sp.get('speaker'): txt(8, 58, str(sp['speaker']).upper()[:16], SCR[2])
        if int(g * 3) % 2 == 0: d.rectangle([W_ - 14, H_ - 14, W_ - 10, H_ - 10], fill=SCR[3])
        _pixel_room(d, W_, 52, small=True)
    elif typ in ('room', 'door'):
        if typ == 'room': _pixel_room(d, W_, H_, figure=sp.get('figure', False), g=g, door_open=sp.get('door_open', False))
        else: _pixel_door(d, W_, H_, open_=float(val(sp.get('open'), u, 0.) or 0.), eyes=sp.get('eyes', False), g=g)
    elif typ == 'eyes':
        if (g * 1.3) % 3 > .15:
            for x in (62, 92): d.rectangle([x, 66, x + 7, 71], fill=SCR[3]); d.rectangle([x + 3, 67, x + 4, 70], fill=SCR[0])
    elif typ == 'static':
        a = rnd(int(g * 30)).integers(0, 4, (H_, W_)); pal = np.array(SCR, np.uint8)
        im = Image.fromarray(pal[a]); d = ImageDraw.Draw(im)
        if sp.get('text'): ctext(66, str(sp['text']).upper()[:18], SCR[3])
    elif typ == 'warning':
        if int(g * 2.5) % 2 == 0 or not sp.get('blink', True):
            d.polygon([(80, 18), (124, 92), (36, 92)], outline=SCR[3]); txt(77, 46, '!', SCR[3])
        ctext(104, str(sp.get('text', 'ATTENTION')).upper()[:18]); ctext(118, str(sp.get('text2', '')).upper()[:18], SCR[2])
    elif typ == 'level':
        ctext(40, str(sp.get('title', 'NIVEAU 1')).upper()); ctext(64, str(sp.get('subtitle', '')).upper()[:18], SCR[2])
        if int(g * 2) % 2 == 0: ctext(110, str(sp.get('press', 'APPUIE SUR START')).upper()[:18], SCR[2])
    elif typ == 'pause':
        ctext(30, 'PAUSE');
        for i, it in enumerate(sp.get('items', ['CONTINUER', 'QUITTER'])[:3]):
            c = SCR[3] if i == int(sp.get('cursor', 0)) else SCR[2]; ctext(64 + i * 20, it.upper()[:14], c)
    elif typ == 'face':
        mood = sp.get('mood', 'smile')
        d.ellipse([46, 24, 114, 116], outline=SCR[3], width=2)
        for x in (64, 90): d.rectangle([x, 56, x + 6, 64], fill=SCR[3])
        if mood == 'smile': d.arc([62, 66, 98, 98], 20, 160, fill=SCR[3], width=2)
        elif mood == 'grin':
            d.rectangle([58, 82, 102, 94], fill=SCR[3])
            for x in range(60, 102, 6): d.line([x, 82, x, 94], fill=SCR[0])
        else: d.line([66, 90, 94, 90], fill=SCR[3], width=2)
    elif typ == 'timer':
        t = max(0., float(sp.get('seconds', 10)) - T); s = f'{int(t // 60)}:{int(t % 60):02d}'
        d.text((40, 52), s, font=font(FONT_PIXEL, 24), fill=SCR[3])
    elif typ == 'game' and CURRENT_GAME[0] is not None:     # the simulated game (game.py), state at time g
        from .game import draw_game
        im = draw_game(CURRENT_GAME[0], g, W_, H_, sp.get('title'))
    return im

CURRENT_GAME = [None]                 # set by ConsoleEngine (one engine per process)

def _pixel_room(d, W_, H_, small=False, figure=False, g=0., door_open=False):
    if small: return
    d.rectangle([0, 0, W_, H_], fill=SCR[1]); d.rectangle([0, int(H_ * .66), W_, H_], fill=SCR[0])
    d.rectangle([94, 20, 118, 40], outline=SCR[3]); d.polygon([(101, 28), (104, 25), (106, 28), (109, 25), (112, 28), (106, 34)], fill=SCR[3])  # frame + heart
    d.rectangle([126, 14, 154, 64], outline=SCR[2], width=2); d.line([126, 39, 154, 39], fill=SCR[2])           # shelf/window
    d.rectangle([40, 72, 112, 92], fill=SCR[2]); d.rectangle([40, 66, 60, 74], fill=SCR[3]); d.rectangle([38, 62, 42, 98], fill=SCR[3])  # bed
    d.rectangle([114, 70, 116, 92], fill=SCR[3]); d.ellipse([110, 62, 120, 72], fill=SCR[3])                    # lamp
    d.rectangle([120, 84, 126, 92], fill=SCR[0])
    if door_open: d.rectangle([4, 30, 26, 96], fill=SCR[0])
    if figure:
        x = 10; d.rectangle([x, 46, x + 12, 110], fill=SCR[0]); d.ellipse([x - 1, 36, x + 13, 50], fill=SCR[0])
        if (g * 1.3) % 3 > .15: d.point([(x + 3, 42), (x + 9, 42)], fill=SCR[3])

def _pixel_door(d, W_, H_, open_=0., eyes=False, g=0.):
    d.rectangle([0, 0, W_, H_], fill=SCR[1]); d.rectangle([0, 118, W_, H_], fill=SCR[0])
    d.rectangle([54, 22, 106, 120], fill=SCR[0]); x1 = 104 - int(48 * open_)
    d.rectangle([56, 24, x1, 118], fill=SCR[2]); d.rectangle([60, 30, x1 - 4, 64], outline=SCR[1]); d.rectangle([60, 72, x1 - 4, 112], outline=SCR[1])
    d.rectangle([x1 - 8, 70, x1 - 5, 74], fill=SCR[3])
    if eyes and open_ > .1 and (g * 1.3) % 3 > .15: d.point([(x1 + 4, 60), (x1 + 9, 60)], fill=SCR[3])
    d.rectangle([56, 118, 104, 121], fill=SCR[3])

def screen_on_canvas(sp, T, u, g, w, h, scan=True):
    """160x144 pixel screen scaled to (w, h) with scanlines and slight bloom"""
    im = screen_image(sp, T, u, g).resize((w, h), Image.NEAREST)
    if scan:
        a = np.asarray(im).astype(np.float32); k = max(2, h // 144)
        a[k - 1::k] *= .72; im = Image.fromarray(a.astype(np.uint8))
    return im

# ---------------------------------------------------------------- scenes (static layer + dynamic overlay)
class SceneBuilder:
    def __init__(self, W, H, art=None, palette='night'):
        self.W, self.H = W, H; self.CW, self.CH = int(W * 1.18), int(H * 1.18)
        self.cache = {}
        self.art = art or ''                   # '' = the original look; 'aplat' = the V3 flat art direction
        self.palette = palette or 'night'      # default palette name of the aplat art direction
        self._sets = {}                        # AplatSets per palette (only used by the aplat path)
        self._pal = None                       # palette of the last rendered frame, read back by the grade

    def sets(self, name):
        """the flat sets for one palette (aplat path only)"""
        from . import aplat
        if name not in self._sets:
            self._sets[name] = aplat.AplatSets(self.CW, self.CH, aplat.palette(name))
        return self._sets[name]

    def wall(self):
        im = vgrad(self.CW, self.CH, (16, 22, 52), (10, 14, 34))
        a = np.asarray(im).astype(np.int16)
        x = np.arange(self.CW)[None, :, None]
        a += ((np.sin(x * .11) > .92) * 4).astype(np.int16)              # faint wallpaper stripes
        return grain(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)), 4, 1)

    def floor(self, im, y0, col=(8, 11, 26)):
        d = ImageDraw.Draw(im); d.rectangle([0, y0, self.CW, self.CH], fill=col)
        d.line([0, y0, self.CW, y0], fill=(26, 32, 66), width=3)

    def door_geom(self, x_rel=.5):
        CW, CH = self.CW, self.CH; s = min(CW / 1.0, CH / 1.65)
        dw = int(s * .5); dh = int(dw * 2.15)
        x0 = int(CW * x_rel - dw / 2); y1 = int(CH * .8); y0 = y1 - dh
        return x0, y0, x0 + dw, y1

    def draw_door(self, im, p, x_rel=.55):
        d = ImageDraw.Draw(im); x0, y0, x1, y1 = self.door_geom(x_rel); dw = x1 - x0
        fr = int(dw * .07)
        d.rectangle([x0 - fr, y0 - fr, x1 + fr, y1], fill=(20, 16, 22))
        col = tuple(p.get('color', DOOR))
        dimg = vgrad(dw, y1 - y0, mix(col, DOOR_L, .25), mix(col, DOOR_D, .4))
        im.paste(dimg, (x0, y0))
        m = int(dw * .13); mid = y0 + int((y1 - y0) * .45)
        for (a, b) in ((y0 + m, mid - m // 2), (mid + m // 2, y1 - m)):
            d.rectangle([x0 + m, a, x1 - m, b], outline=mix(col, DOOR_D, .7), width=max(2, dw // 70))
            d.line([x0 + m + 3, b - 2, x1 - m - 2, b - 2], fill=mix(col, DOOR_L, .5), width=2)
        hx = x1 - int(dw * .13); hy = y0 + int((y1 - y0) * .55)
        d.rounded_rectangle([hx - dw * .03, hy - dw * .1, hx + dw * .03, hy + dw * .1], radius=int(dw * .03), fill=(200, 202, 210))
        d.ellipse([hx - dw * .045, hy - dw * .045, hx + dw * .045, hy + dw * .045], fill=(220, 222, 228))
        d.ellipse([(x0 + x1) / 2 - 4, y0 + (y1 - y0) * .2 - 4, (x0 + x1) / 2 + 4, y0 + (y1 - y0) * .2 + 4], fill=(40, 30, 22))
        return (x0, y0, x1, y1)

    def static_layer(self, key, sc):
        if key in self.cache: return self.cache[key]
        typ = sc.get('type', 'door'); CW, CH = self.CW, self.CH
        im = self.wall()
        if typ in ('door', 'split', 'hallway'):
            self.floor(im, int(CH * .8))
            if typ == 'door': self.draw_door(im, sc, sc.get('x', .55))
            if typ == 'hallway':
                d = ImageDraw.Draw(im); cx = CW // 2
                d.polygon([(0, 0), (cx - CW * .18, CH * .32), (cx - CW * .18, CH * .66), (0, CH)], fill=(18, 24, 56))
                d.polygon([(CW, 0), (cx + CW * .18, CH * .32), (cx + CW * .18, CH * .66), (CW, CH)], fill=(18, 24, 56))
                d.rectangle([cx - CW * .18, CH * .32, cx + CW * .18, CH * .66], fill=(10, 13, 32))
                d.polygon([(0, CH), (cx - CW * .18, CH * .66), (cx + CW * .18, CH * .66), (CW, CH)], fill=(8, 11, 26))
                dw = CW * .08; d.rectangle([cx - dw, CH * .42, cx + dw, CH * .66], fill=(70, 48, 30))
        elif typ == 'room':
            self.floor(im, int(CH * .74)); d = ImageDraw.Draw(im)
            wx0, wy0 = int(CW * .12), int(CH * .22); ww, wh = int(CW * .3), int(CH * .2)        # window with moon
            d.rectangle([wx0, wy0, wx0 + ww, wy0 + wh], fill=(26, 40, 86))
            im.paste(radial(ww, wh, ww * .7, wh * .3, wh * .9, (120, 150, 220), .5), (wx0, wy0), radial(ww, wh, ww * .7, wh * .3, wh * .9, (120, 150, 220), .5))
            d.ellipse([wx0 + ww * .62, wy0 + wh * .15, wx0 + ww * .78, wy0 + wh * .15 + ww * .16], fill=(230, 232, 210))
            d.rectangle([wx0, wy0, wx0 + ww, wy0 + wh], outline=(46, 58, 110), width=8); d.line([wx0 + ww / 2, wy0, wx0 + ww / 2, wy0 + wh], fill=(46, 58, 110), width=6)
            bx0, by0 = int(CW * .08), int(CH * .62)                                                  # bed
            d.rounded_rectangle([bx0, by0, bx0 + CW * .55, by0 + CH * .14], radius=20, fill=FURN)
            d.rounded_rectangle([bx0 + 10, by0 - CH * .03, bx0 + CW * .55 - 10, by0 + CH * .05], radius=30, fill=(48, 62, 130))
            d.rounded_rectangle([bx0 + 20, by0 - CH * .05, bx0 + CW * .16, by0 + CH * .01], radius=24, fill=(60, 74, 140))
            d.rectangle([CW * .74, CH * .5, CW * .95, CH * .74], fill=FURN)                               # desk + lamp
            d.rectangle([CW * .82, CH * .38, CW * .83, CH * .5], fill=(60, 66, 110)); d.ellipse([CW * .79, CH * .35, CW * .86, CH * .4], fill=(70, 80, 130))
            d.rectangle([CW * .62, CH * .2, CW * .72, CH * .34], fill=(30, 38, 80), outline=(46, 58, 110), width=4)  # poster
            self.draw_door(im, {}, .93) if sc.get('door', True) else None
        elif typ == 'console':
            pass
        elif typ == 'rule_card':
            a = np.asarray(im).astype(np.int16); s = max(24, CW // 22)
            a[::s] += 6; a[:, ::s] += 6; im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        elif typ == 'window':
            d = ImageDraw.Draw(im); wx0, wy0, ww, wh = int(CW * .2), int(CH * .25), int(CW * .6), int(CH * .4)
            d.rectangle([wx0, wy0, wx0 + ww, wy0 + wh], fill=(18, 28, 64))
            for i in range(60):
                r_ = rnd(i); d.point((wx0 + r_.integers(0, ww), wy0 + r_.integers(0, wh)), fill=(170, 180, 220))
            d.ellipse([wx0 + ww * .7, wy0 + wh * .12, wx0 + ww * .82, wy0 + wh * .12 + ww * .12], fill=(232, 232, 214))
            d.rectangle([wx0, wy0, wx0 + ww, wy0 + wh], outline=(46, 58, 110), width=10); d.line([wx0 + ww / 2, wy0, wx0 + ww / 2, wy0 + wh], fill=(46, 58, 110), width=8)
            d.line([wx0, wy0 + wh / 2, wx0 + ww, wy0 + wh / 2], fill=(46, 58, 110), width=8)
            self.floor(im, int(CH * .8))
        elif typ == 'face':
            im = vgrad(CW, CH, (10, 14, 34), (6, 8, 20))
        elif typ == 'black':
            im = Image.new('RGB', (CW, CH), (6, 8, 18))
        self.cache[key] = im
        return im

    # ---------------- dynamic parts
    def console_body(self, im, sc, T, u, g, full_screen=False):
        CW, CH = self.CW, self.CH; d = ImageDraw.Draw(im)
        if full_screen:
            sw = int(min(CW * .8, CH * .7 * 160 / 144)); sh = int(sw * 144 / 160)
            x0, y0 = (CW - sw) // 2, int(CH * .45 - sh / 2)
            im.paste(screen_on_canvas(sc.get('screen', {}), T, u, g, sw, sh), (x0, y0))
            gl = glow_layer((CW, CH), lambda dd: dd.rectangle([x0, y0, x0 + sw, y0 + sh], fill=70), 60, (120, 220, 120), key=('scrglow', x0, y0, sw)); im.alpha_composite(gl)
            return
        bw = int(min(CW * .9, CH * .55)); bh = int(bw * 1.62)
        x0 = (CW - bw) // 2 + int(CW * float(sc.get('x_offset', 0))); y0 = int(CH * .16)
        shadow = glow_layer((CW, CH), lambda dd: dd.rounded_rectangle([x0 + 20, y0 + 30, x0 + bw + 20, y0 + bh + 30], radius=bw // 9, fill=200), 40, (0, 0, 0), key=('cshadow', x0, y0, bw))
        im.alpha_composite(shadow)
        body = vgrad(bw, bh, (226, 225, 232), (178, 176, 188)).convert('RGBA')
        mk = Image.new('L', (bw, bh), 0); ImageDraw.Draw(mk).rounded_rectangle([0, 0, bw - 1, bh - 1], radius=bw // 9, fill=255)
        im.paste(body, (x0, y0), mk); d = ImageDraw.Draw(im)
        bz = int(bw * .07); sx0, sy0, sx1 = x0 + bz, y0 + int(bw * .07), x0 + bw - bz; sy1 = sy0 + int((sx1 - sx0) * .86)
        d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=bw // 24, fill=(56, 60, 76))
        ix0, iy0 = sx0 + int(bw * .07), sy0 + int(bw * .06); iw = sx1 - sx0 - int(bw * .14); ih = int(iw * 144 / 160)
        led = (255, 60, 60) if sc.get('led', True) and (int(g * 2) % 2 == 0 or not sc.get('led_blink')) else (90, 30, 30)
        d.ellipse([sx0 + bw * .025, sy0 + bw * .03, sx0 + bw * .045, sy0 + bw * .05], fill=led)
        scr = screen_on_canvas(sc.get('screen', {}), T, u, g, iw, ih)
        im.paste(scr, (ix0, iy0))
        im.alpha_composite(glow_layer((CW, CH), lambda dd: dd.rectangle([ix0, iy0, ix0 + iw, iy0 + ih], fill=70), 50, (140, 230, 120), key=('cglow', ix0, iy0, iw)))
        d = ImageDraw.Draw(im)
        cy = sy1 + int(bh * .17); cx = x0 + int(bw * .22); a = int(bw * .045)
        d.rounded_rectangle([cx - a * 3, cy - a, cx + a * 3, cy + a], radius=6, fill=(52, 54, 64)); d.rounded_rectangle([cx - a, cy - a * 3, cx + a, cy + a * 3], radius=6, fill=(52, 54, 64))
        for k, (bx, by) in enumerate(((x0 + bw * .66, cy + a * .6), (x0 + bw * .84, cy - a * .6))):
            pressed = sc.get('press') in (('B', 'A')[k], 'AB') and int(T * 6) % 2 == 0
            r_ = a * (1.75 if not pressed else 1.6)
            d.ellipse([bx - r_, by - r_, bx + r_, by + r_], fill=(196, 52, 84) if not pressed else (150, 36, 60))
        for k in range(2):
            px = x0 + bw * (.36 + k * .18); py = cy + int(bh * .15); d.rounded_rectangle([px - bw * .06, py - 6, px + bw * .06, py + 6], radius=6, fill=(120, 120, 130))
        for i in range(6):
            for j in range(4): d.ellipse([x0 + bw * .76 + j * 12, cy + bh * .12 + i * 12, x0 + bw * .76 + j * 12 + 6, cy + bh * .12 + i * 12 + 6], fill=(130, 130, 140))

    def under_door_light(self, im, sc, T, u, g):
        lu = sc.get('light_under')
        if not lu: return
        col = {'warm': (255, 196, 120), 'orange': ORANGE, 'red': (255, 70, 70), 'green': (160, 255, 140), 'white': (240, 240, 230)}.get(lu if isinstance(lu, str) else 'warm', (255, 196, 120))
        x0, y0, x1, y1 = self.door_geom(sc.get('x', .55)); CW, CH = self.CW, self.CH
        flick = 1 - .5 * float(bool(sc.get('flicker')) and ((int(g * 9) * 2654435761) & 0xffff) / 65535. > .7)
        spread = (x1 - x0) * .9
        fx_ = (x0 + x1) / 2 + (math.sin(g * 1.4) * (x1 - x0) * .08 if sc.get('feet_move') else 0)
        ck = ('cone', x0, y1, bool(sc.get('feet')), round(fx_ / 6), flick)
        if ck in _GLOW_CACHE: lay = _GLOW_CACHE[ck]
        else: lay = None
        cone = Image.new('L', (CW, CH), 0); dd = ImageDraw.Draw(cone)
        dd.polygon([(x0 + 6, y1), (x1 - 6, y1), (x1 + spread, CH), (x0 - spread, CH)], fill=int(150 * flick))
        feet = sc.get('feet')
        if feet:
            fx = (x0 + x1) / 2 + (math.sin(g * 1.4) * (x1 - x0) * .08 if sc.get('feet_move') else 0)
            fw = (x1 - x0) * .07
            for s in (-1, 1):
                cx = fx + s * (x1 - x0) * .12
                dd.polygon([(cx - fw, y1), (cx + fw, y1), (cx + fw * 3.5 + s * spread * .2, CH), (cx - fw * 3.5 + s * spread * .2, CH)], fill=0)
        if lay is None:
            cone = cone.resize((CW // 4, CH // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4.5)).resize((CW, CH), Image.BILINEAR)
            lay = Image.new('RGBA', (CW, CH), col + (0,)); lay.putalpha(cone)
            if len(_GLOW_CACHE) > 64: _GLOW_CACHE.clear()
            _GLOW_CACHE[ck] = lay
        im.alpha_composite(lay)
        d = ImageDraw.Draw(im); d.rectangle([x0, y1 - 5, x1, y1 + 2], fill=mix(col, (255, 255, 255), .3))
        if feet:
            fx = (x0 + x1) / 2 + (math.sin(g * 1.4) * (x1 - x0) * .08 if sc.get('feet_move') else 0); fw = (x1 - x0) * .07
            for s in (-1, 1):
                cx = fx + s * (x1 - x0) * .12; d.rectangle([cx - fw, y1 - 5, cx + fw, y1 + 2], fill=(10, 8, 12))

    def rule_card(self, im, sc, T, u):
        CW, CH = self.CW, self.CH; d = ImageDraw.Draw(im); W = min(CW, CH * .75)
        num = sc.get('number', 1); tag = sc.get('tag', f'RÈGLE N°{num}')
        ft = font(FONT_MONTSERRAT, int(W * .03), 'Black'); tw = d.textlength(tag, font=ft)
        y0 = CH * .5 - W * .45
        d.rounded_rectangle([CW / 2 - tw / 2 - 18, y0, CW / 2 + tw / 2 + 18, y0 + W * .05], radius=12, fill=(214, 52, 74))
        d.text((CW / 2 - tw / 2, y0 + W * .008), tag, font=ft, fill=(255, 240, 240))
        fb = font(FONT_BEBAS, int(W * .11)); y = y0 + W * .07
        lines = sc.get('lines', ['NE QUITTE PAS', 'TA CHAMBRE']); hl = sc.get('highlight', len(lines) - 1)
        for i, l in enumerate(lines[:3]):
            l = l.upper(); w = d.textlength(l, font=fb)
            d.text((CW / 2 - w / 2 + 4, y + 5), l, font=fb, fill=(0, 0, 0)); d.text((CW / 2 - w / 2, y), l, font=fb, fill=GOLD if i == hl else (226, 228, 236))
            y += W * .1
        self.icon(im, sc.get('icon', 'door_x'), CW / 2, y + W * .12, W * .2, T)

    def icon(self, im, kind, cx, cy, size, T):
        d = ImageDraw.Draw(im); s = size / 16
        def px(x, y, c): d.rectangle([cx - size / 2 + x * s, cy - size / 2 + y * s, cx - size / 2 + (x + 1) * s - 1, cy - size / 2 + (y + 1) * s - 1], fill=c)
        if kind in ('door_x', 'door'):
            for y in range(1, 15):
                for x in range(4, 12): px(x, y, DOOR if (x + y) % 5 else DOOR_D)
            px(10, 8, (220, 220, 220))
        elif kind in ('eye', 'eye_x'):
            for x in range(2, 14):
                yh = int(3 * math.sin((x - 2) / 11 * math.pi)); px(x, 8 - yh, WHITE); px(x, 8 + yh, WHITE)
            for x in range(6, 10):
                for y in range(6, 10): px(x, y, (40, 40, 60))
        elif kind in ('clock', 'clock_x'):
            for a in range(0, 360, 15):
                px(int(8 + 6 * math.cos(math.radians(a))), int(8 + 6 * math.sin(math.radians(a))), WHITE)
            for k in range(4): px(8, 8 - k, WHITE); px(8 + k, 8, WHITE)
        elif kind in ('phone', 'phone_x', 'console', 'console_x'):
            for y in range(2, 15):
                for x in range(5, 11): px(x, y, (190, 190, 200))
            for y in range(3, 9):
                for x in range(6, 10): px(x, y, SCR[2])
        elif kind in ('light_off', 'bulb'):
            for a in range(0, 360, 20): px(int(8 + 4 * math.cos(math.radians(a))), int(6 + 4 * math.sin(math.radians(a))), GOLD)
            for x in range(6, 11): px(x, 12, GREY)
        elif kind in ('bed', 'bed_x'):
            for x in range(1, 15): px(x, 10, FURN); px(x, 11, FURN)
            for x in range(2, 6): px(x, 8, WHITE); px(x, 9, WHITE)
        if kind.endswith('_x') or kind == 'door_x':
            w = max(4, int(size * .07))
            d.line([cx - size * .42, cy - size * .42, cx + size * .42, cy + size * .42], fill=(255, 77, 94), width=w)
            d.line([cx + size * .42, cy - size * .42, cx - size * .42, cy + size * .42], fill=(255, 77, 94), width=w)

    def face(self, im, sc, T, u, g):
        if (sc.get('faces') or 'flat') == 'expressive': return self.face_expressive(im, sc, T, u, g)
        CW, CH = self.CW, self.CH; d = ImageDraw.Draw(im)
        light = {'green': (120, 230, 120), 'orange': ORANGE, 'red': (255, 70, 80), 'blue': (110, 150, 255)}.get(sc.get('light', 'green'), (120, 230, 120))
        cx, cy = CW / 2, CH * .48; r = min(CW, CH) * .26
        im.alpha_composite(_cached_radial(CW, CH, cx, cy + r * 1.2, r * 2.6, light, .45, 1.6))
        skin = mix((224, 172, 136), light, .22); hair = (24, 26, 46); hood = (48, 58, 100)
        d.rounded_rectangle([cx - r * 1.4, cy + r * .95, cx + r * 1.4, CH], radius=int(r * .6), fill=hood)
        d.ellipse([cx - r * .9, cy - r * 1.05, cx + r * .9, cy + r * 1.1], fill=skin)
        d.chord([cx - r * .98, cy - r * 1.2, cx + r * .98, cy + r * .5], 180, 360, fill=hair)
        d.polygon([(cx - r * .95, cy - r * .3), (cx - r * .5, cy - r * .55), (cx, cy - r * .35), (cx + r * .6, cy - r * .6), (cx + r * .95, cy - r * .25), (cx + r * .95, cy - r * .8), (cx - r * .95, cy - r * .8)], fill=hair)
        ex = sc.get('expression', 'scared'); look = {'left': -.18, 'right': .18}.get(sc.get('look', 'center'), 0.) * r
        blink = (g % 4) < .12 and ex not in ('closed',)
        for s in (-1, 1):
            ex_x = cx + s * r * .38; ey = cy + r * .05
            if ex == 'closed' or blink: d.line([ex_x - r * .17, ey, ex_x + r * .17, ey], fill=(30, 26, 40), width=int(r * .05)); continue
            wv = r * (.2 if ex in ('scared', 'wide') else .16); hv = r * (.16 if ex in ('scared', 'wide') else .1)
            d.ellipse([ex_x - wv, ey - hv, ex_x + wv, ey + hv], fill=(244, 244, 248))
            pr = r * (.055 if ex in ('scared', 'wide') else .07)
            d.ellipse([ex_x - pr + look, ey - pr, ex_x + pr + look, ey + pr], fill=(20, 20, 30))
            by = ey - r * (.3 if ex in ('scared', 'wide') else .24)
            d.line([ex_x - r * .2, by + (s * r * .04 if ex == 'scared' else 0), ex_x + r * .2, by - (s * r * .04 if ex == 'scared' else 0)], fill=hair, width=int(r * .06))
        my = cy + r * .55
        if ex in ('scared', 'wide'): d.ellipse([cx - r * .12, my - r * .1, cx + r * .12, my + r * .14], fill=(70, 30, 40))
        elif ex == 'crying':
            d.arc([cx - r * .2, my, cx + r * .2, my + r * .25], 200, 340, fill=(90, 40, 50), width=int(r * .04))
            for s in (-1, 1): d.line([cx + s * r * .38, cy + r * .2, cx + s * r * .4, cy + r * .5], fill=(140, 200, 255), width=int(r * .04))
        elif ex == 'smile': d.arc([cx - r * .25, my - r * .2, cx + r * .25, my + r * .1], 20, 160, fill=(90, 40, 50), width=int(r * .05))
        else: d.line([cx - r * .15, my, cx + r * .15, my], fill=(90, 40, 50), width=int(r * .045))

    def face_expressive(self, im, sc, T, u, g):
        """close-up of an acted face (opt-in "faces": "expressive"): neck and ears so the head stops
        floating, eyelids and a real gaze, brows that act, a mouth that speaks, and the chest that breathes."""
        from . import expression as X
        CW, CH = self.CW, self.CH
        look = dict(sc.get('_look') or {})
        light = {'green': (120, 230, 120), 'orange': ORANGE, 'red': (255, 70, 80), 'blue': (110, 150, 255)}.get(sc.get('light', 'green'), (120, 230, 120))
        gz = sc.get('look', 'center')
        gaze = ({'left': (-.62, 0.), 'right': (.62, 0.), 'up': (0., -.58), 'down': (0., .55),
                 'away': (-.78, .18), 'center': (0., 0.)}.get(gz, (0., 0.)) if isinstance(gz, str)
                else (float(gz[0]), float(gz[1])))
        p = X.face_params(sc.get('expression', 'scared'), t=g, seed=float(sc.get('seed', .37)),
                          talking=bool(sc.get('_talk')), gaze=gaze, persona=look.get('personality'),
                          intensity=float(sc.get('intensity', look.get('face_intensity', 1.))))
        r = min(CW, CH) * .26
        cx = CW / 2 + r * p['sway'] * 2.0
        cy = CH * .48 + r * p['breath_y'] * 1.6
        im.alpha_composite(_cached_radial(CW, CH, CW / 2, CH * .48 + r * 1.2, r * 2.6, light, .45, 1.6))
        d = ImageDraw.Draw(im)
        skin = mix(tuple(look.get('skin', (224, 172, 136))), light, .22)
        hair = tuple(look.get('hair', (24, 26, 46))); hood = tuple(look.get('hood', (48, 58, 100)))
        style = look.get('hair_style') or ('long' if look.get('hair_long') else 'short')
        d.rounded_rectangle([cx - r * 1.4, cy + r * 1.05, cx + r * 1.4, CH], radius=int(r * .6), fill=hood)
        d.polygon([(cx - r * .34, cy + r * .62), (cx + r * .34, cy + r * .62),
                   (cx + r * .40, cy + r * 1.12), (cx - r * .40, cy + r * 1.12)], fill=X.shade(skin, .80))
        for s_ in (-1, 1):                                        # ears, behind the head
            d.ellipse([cx + s_ * r * .88 - r * .13, cy - r * .04, cx + s_ * r * .88 + r * .13, cy + r * .32], fill=X.shade(skin, .92))
        d.ellipse([cx - r * .9, cy - r * 1.05, cx + r * .9, cy + r * 1.1], fill=skin)
        d.chord([cx - r * .90, cy - r * 1.08, cx + r * .90, cy + r * .08], 180, 360, fill=hair)
        d.polygon([(cx - r * .78, cy - r * .46), (cx - r * .34, cy - r * .66), (cx + r * .06, cy - r * .48),
                   (cx + r * .50, cy - r * .68), (cx + r * .78, cy - r * .44), (cx + r * .78, cy - r * .90),
                   (cx - r * .78, cy - r * .90)], fill=hair)
        if style in ('long', 'ponytail'):
            for s_ in (-1, 1):
                d.rounded_rectangle([cx + s_ * r * .86 - r * .13, cy - r * .55, cx + s_ * r * .86 + r * .13, cy + r * (.95 if style == 'long' else .35)], radius=int(r * .12), fill=hair)
        X.draw_face(d, cx, cy, r * .9, p, skin, hair, lip=look.get('lip'), iris=look.get('iris'),
                    brow_color=look.get('brow_color'), sep=.42, eye_y=.04, mouth_y=.56,
                    nose=look.get('nose', True), socket=look.get('eye_socket', True), lashes=look.get('lashes', True))
        if look.get('glasses'):
            gc = (30, 28, 36) if look['glasses'] not in ('sun', 'sunglasses') else (20, 20, 26)
            rr = r * .9; lw = max(2, int(rr * .035))
            for s_ in (-1, 1):
                gx = cx + s_ * rr * .42
                box = [gx - rr * .26, cy + rr * .04 - rr * .20, gx + rr * .26, cy + rr * .04 + rr * .22]
                if look['glasses'] in ('sun', 'sunglasses'): d.rounded_rectangle(box, radius=int(rr * .08), fill=gc)
                else: d.rounded_rectangle(box, radius=int(rr * .08), outline=gc, width=lw)
            d.line([cx - rr * .16, cy + rr * .02, cx + rr * .16, cy + rr * .02], fill=gc, width=lw)

    def figure_silhouette(self, im, x, y_floor, h, g, eyes=True):
        d = ImageDraw.Draw(im); w = h * .22
        d.rounded_rectangle([x - w / 2, y_floor - h * .82, x + w / 2, y_floor], radius=int(w * .3), fill=(4, 5, 10))
        d.ellipse([x - w * .42, y_floor - h, x + w * .42, y_floor - h * .78], fill=(4, 5, 10))
        if eyes and (g * 1.3) % 3 > .15:
            for s in (-1, 1): d.ellipse([x + s * w * .16 - 4, y_floor - h * .9 - 3, x + s * w * .16 + 4, y_floor - h * .9 + 3], fill=(255, 230, 230))

    # ---------------- the aplat art direction (V3, opt-in: nothing below runs for a legacy episode)
    def aplat_static(self, key, sc, A):
        if key in self.cache: return self.cache[key]
        typ = sc.get('type', 'door')
        if typ == 'room': im = A.room(sc, self.door_geom(.93))
        elif typ == 'door': im = A.door_scene(sc, self.door_geom(sc.get('x', .55)))
        elif typ == 'hallway': im = A.hallway(sc)
        elif typ == 'window': im = A.window_scene(sc)
        elif typ == 'black': im = Image.new('RGB', (self.CW, self.CH), A.pal['ink'])
        else: im = A.face_bg(sc)                       # face, console, screen, rule_card, split: the graphic backdrop
        self.cache[key] = im
        return im

    def render_aplat(self, k, sc, T, u, g):
        from . import aplat
        from .figure2d import draw_figure as draw_fig2d
        typ = sc.get('type', 'door'); pname = sc.get('palette') or self.palette   # a shot can change palette
        A = self.sets(pname); pal = A.pal; self._pal = pal
        CW, CH = self.CW, self.CH
        base = self.aplat_static((k, typ, pname, float(sc.get('x', .55))), sc, A).copy().convert('RGBA')
        d = ImageDraw.Draw(base)
        light = aplat.light_dir(sc, typ)
        lamp = {'warm': pal['light'], 'orange': pal['light'], 'red': pal['accent'],
                'green': pal['glow'], 'white': pal['moon']}

        def door_light(geom, lu):
            col = lamp.get(lu if isinstance(lu, str) else 'warm', pal['light'])
            flick = 1 - .45 * float(bool(sc.get('flicker')) and ((int(g * 9) * 2654435761) & 0xffff) / 65535. > .7)
            fmove = math.sin(g * 1.4) * .08 if sc.get('feet_move') else 0.
            A.under_door(d, geom, pal, col, feet=bool(sc.get('feet')), feet_x=fmove, flick=flick)

        if typ == 'console': A.console_body(base, sc, T, u, g)
        elif typ == 'screen': A.console_body(base, sc, T, u, g, full_screen=True)
        elif typ == 'face': A.face_closeup(base, sc, T, u, g)
        elif typ == 'rule_card':
            from . import ui2d; ui2d.rule_card(base, sc, T, u, pal, ui2d.card_unit(self.W, self.H))
        elif typ == 'door':
            geom = self.door_geom(sc.get('x', .55))
            if sc.get('light_under'): door_light(geom, sc['light_under'])
            if sc.get('knock') and any(0 <= T - float(t) < .12 for t in sc['knock']):
                base = ImageChops.offset(base, int(rnd(int(g * 50)).integers(-6, 7)), 0); d = ImageDraw.Draw(base)
            o = float(val(sc.get('open'), u, 0.) or 0.)
            if o > .02:
                x0, y0, x1, y1 = geom
                d.rectangle([x0, y0, x0 + (x1 - x0) * o * .35, y1], fill=pal['ink'])
                if sc.get('eyes') and (g * 1.3) % 3 > .15:
                    ey = y0 + (y1 - y0) * .35; ex = x0 + (x1 - x0) * o * .17
                    for s in (-1, 1): d.ellipse([ex + s * 10 - 5, ey - 5, ex + s * 10 + 5, ey + 5], fill=pal['moon'])
        elif typ == 'room':
            if sc.get('console_on_bed', True):          # the handheld left on the bed: a flat shape, a hard spill
                bx, by = CW * .40, CH * .615
                d.polygon([(bx - CW * .07, by), (bx + CW * .07, by), (bx + CW * .17, CH * .80), (bx - CW * .17, CH * .80)],
                          fill=aplat.mix(pal['furn'], pal['glow'], .30))
                aplat.rbox(d, bx - CW * .030, by - CH * .030, bx + CW * .030, by + CH * .014, CH * .005,
                           aplat.SHELL[1], pal['ink'], A.ink_w)
                d.rectangle([bx - CW * .022, by - CH * .024, bx + CW * .022, by - CH * .002], fill=pal['glow'])
            if sc.get('light_under'): door_light(self.door_geom(.93), sc['light_under'])
            if sc.get('figure'): A.silhouette(d, CW * float(sc.get('figure_x', .86)), CH * .755, CH * .42, g, pal)
        elif typ == 'window':
            if sc.get('silhouette'):
                wx0, wy0, ww, wh = int(CW * .20), int(CH * .25), int(CW * .60), int(CH * .40)
                A.silhouette(d, wx0 + ww * float(sc.get('silhouette_x', .35)), wy0 + wh, wh * .8, g, pal, eyes=sc.get('eyes', True))
        elif typ == 'hallway':
            if sc.get('figure'): A.silhouette(d, CW / 2, CH * .66, CH * .22, g, pal)
        elif typ == 'split':
            left = sc.get('left', {'type': 'screen'}); right = sc.get('right', {'type': 'door'})
            half = CW // 2
            sub = SceneBuilder(self.W // 2, self.H, self.art, pname)
            def part(spec, kk): return sub.render(kk, spec, T, u, g).resize((half, CH))
            base.paste(part(left, (k, 'L')), (0, 0)); base.paste(part(right, (k, 'R')), (half, 0))
            d = ImageDraw.Draw(base)
            d.rectangle([half - A.ink_w * 2, 0, half + A.ink_w * 2, CH], fill=pal['ink'])
        if typ == 'room' and float(sc.get('_door_open', 0.)) > .02:        # bedroom door ajar (game -> room link)
            x0, y0, x1, y1 = self.door_geom(.93); o = float(sc['_door_open'])
            d.rectangle([x0, y0, x0 + (x1 - x0) * o * .35, y1], fill=pal['ink'])
        if sc.get('_actors'):
            stage, samples, looks, Tg = sc['_actors']
            for aid, smp in sorted(samples.items(), key=lambda kv: kv[1]['z']):
                if smp.get('visible', True): draw_fig2d(d, stage, smp, looks.get(aid, {}), Tg, pal, light)
        return base

    def render(self, k, sc, T, u, g):
        if self.art == 'aplat': return self.render_aplat(k, sc, T, u, g)
        typ = sc.get('type', 'door')
        base = self.static_layer((k, typ), sc).convert('RGBA')
        CW, CH = self.CW, self.CH
        if typ == 'console': self.console_body(base, sc, T, u, g)
        elif typ == 'screen': self.console_body(base, sc, T, u, g, full_screen=True)
        elif typ == 'door':
            self.under_door_light(base, sc, T, u, g)
            if sc.get('knock') and any(0 <= T - float(t) < .12 for t in sc['knock']):
                base = ImageChops.offset(base, int(rnd(int(g * 50)).integers(-6, 7)), 0)
            if float(val(sc.get('open'), u, 0.) or 0.) > .02:
                x0, y0, x1, y1 = self.door_geom(sc.get('x', .55)); o = float(val(sc.get('open'), u, 0.))
                d = ImageDraw.Draw(base); d.rectangle([x0, y0, x0 + (x1 - x0) * o * .35, y1], fill=(3, 3, 6))
                if sc.get('eyes') and (g * 1.3) % 3 > .15:
                    ey = y0 + (y1 - y0) * .35; ex = x0 + (x1 - x0) * o * .17
                    for s in (-1, 1): d.ellipse([ex + s * 9 - 4, ey - 3, ex + s * 9 + 4, ey + 3], fill=(255, 230, 230))
        elif typ == 'room':
            if sc.get('console_on_bed', True):
                bx, by = CW * .4, CH * .6
                base.alpha_composite(_cached_radial(CW, CH, bx, by, CW * .25, (120, 230, 120), .35))
                d = ImageDraw.Draw(base); d.rounded_rectangle([bx - 26, by - 40, bx + 26, by + 20], radius=8, fill=(200, 200, 208)); d.rectangle([bx - 18, by - 32, bx + 18, by - 6], fill=SCR[2])
            if sc.get('figure'): self.figure_silhouette(base, CW * float(sc.get('figure_x', .86)), CH * .74, CH * .42, g)
            if sc.get('light_under'): self.under_door_light(base, dict(sc, x=.93), T, u, g)
        elif typ == 'rule_card': self.rule_card(base, sc, T, u)
        elif typ == 'face': self.face(base, sc, T, u, g)
        elif typ == 'window':
            if sc.get('silhouette'):
                wx0, wy0, ww, wh = int(CW * .2), int(CH * .25), int(CW * .6), int(CH * .4)
                self.figure_silhouette(base, wx0 + ww * float(sc.get('silhouette_x', .35)), wy0 + wh, wh * .8, g, eyes=sc.get('eyes', True))
        elif typ == 'hallway':
            if sc.get('figure'): self.figure_silhouette(base, CW / 2, CH * .66, CH * .22, g)
        elif typ == 'split':
            left = sc.get('left', {'type': 'screen'}); right = sc.get('right', {'type': 'door'})
            half = CW // 2
            sub = SceneBuilder(self.W // 2, self.H)
            def part(spec, kk):
                if spec.get('type') == 'screen':
                    sw = int(half * .98); shh = int(sw * 144 / 160); img = Image.new('RGBA', (half, CH), BG + (255,))
                    img.paste(screen_on_canvas(spec.get('screen', {'type': 'room', 'figure': True}), T, u, g, sw, shh), ((half - sw) // 2, int(CH * .3)))
                    return img
                return sub.render(kk, spec, T, u, g).resize((half, CH))
            base.paste(part(left, (k, 'L')), (0, 0)); base.paste(part(right, (k, 'R')), (half, 0))
            ImageDraw.Draw(base).line([half, 0, half, CH], fill=(0, 0, 0), width=6)
        if typ == 'room' and float(sc.get('_door_open', 0.)) > .02:             # the bedroom door ajar (game -> room link)
            x0, y0, x1, y1 = self.door_geom(.93); o = float(sc['_door_open'])
            ImageDraw.Draw(base).rectangle([x0, y0, x0 + (x1 - x0) * o * .35, y1], fill=(3, 3, 6))
        if sc.get('_actors'):                                                     # characters of the shared acting layer
            from .flat import draw_figure
            stage, samples, looks, Tg = sc['_actors']; d = ImageDraw.Draw(base)
            for aid, smp in sorted(samples.items(), key=lambda kv: kv[1]['z']):
                if smp.get('visible', True): draw_figure(d, stage, smp, looks.get(aid, {}), Tg)
        return base

# ---------------------------------------------------------------- engine
class ConsoleEngine:
    name = 'console'
    def __init__(self, episode, lines, env, duration, aspect='9:16'):
        from ...capabilities.extensions import ensure_loaded; ensure_loaded()     # stable, fingerprinted extensions (V3)
        from ..pixel3d.frame import Timeline
        from ...acting.cast import apply as _cast; _cast(episode)          # library characters (persistent identities)
        self.ep = episode; self.lines = lines; self.env = env; self.duration = duration; self.aspect = aspect
        self.W, self.H = (1080, 1920) if aspect == '9:16' else (1920, 1080)
        self.tl = Timeline(episode, lines, duration)
        self.art = str(episode.get('art') or '')          # '' = the original look, 'aplat' = the V3 art direction
        self.palette = str(episode.get('palette') or 'night')   # default palette of the aplat art direction
        self.sb = SceneBuilder(self.W, self.H, self.art, self.palette)
        self.subs = build_subs(lines, 16, 4, True)
        self.hud = episode.get('hud', {}) or {}
        self.faces = str(episode.get('faces') or 'flat')      # 'expressive' switches on the acted 2D faces (opt-in)
        # sous-titres surs : opt-in (cle "caption_safe"). Ce moteur dessine en 2D et n'a pas de boite de
        # visage projetee, donc seule la REGLE s'applique ici (zone sure + levee 9:16 sur les plans
        # serres) ; la mesure est reservee a pixel3d. None = le bandeau livre, au pixel pres.
        from ...captions import safe as _CAPS
        self.caps = _CAPS.configure(episode.get('caption_safe'))
        # where the aplat art direction and the expressive flat faces overlap, say it in French, not in silence
        self.art_warnings = []
        if self.art == 'aplat':
            from . import aplat as _ap
            self.art_warnings = _ap.notices(episode, self.art, episode.get('cast') or {})
            for _m in self.art_warnings: print(f'[art] {_m}')
        # the game in the console, the room's reactions to it (links.py) and the characters (shared acting layer)
        from .game import GameTimeline
        from .links import World
        uses_game = any(sh.get('game') for sh in episode['shots']) or any((sh.get('scene') or {}).get('screen', {}).get('type') == 'game' for sh in episode['shots'])
        self.game = None; self.world = None
        if uses_game or any(sh.get('world') for sh in episode['shots']) or episode.get('links'):
            g0 = GameTimeline(episode, self.tl.spans) if uses_game else None
            self.world = World(episode, self.tl.spans, g0)
            self.game = GameTimeline(episode, self.tl.spans, self.world.extra_game) if (uses_game and self.world.extra_game) else g0
            if self.world.extra_game: self.world = World(episode, self.tl.spans, self.game)
        CURRENT_GAME[0] = self.game
        self.acting = None; self.stages = {}
        from ...acting.timeline import uses_acting
        if any(uses_acting(episode, sh) for sh in episode['shots']):
            from ...acting.timeline import Acting
            from .flat import Stage, ConsoleWorld
            ep2 = dict(episode, shots=[dict(sh, set=(sh.get('scene') or {}).get('type', 'door')) for sh in episode['shots']])
            def world_of(name, shot):
                st = self.stage(name, shot.get('scene') or {}); return ConsoleWorld(st)
            self.acting = Acting(ep2, self.tl.spans, lines, world_of, episode.get('cast'))

    def stage(self, typ, sc):
        from .flat import Stage
        key = (typ, float(sc.get('x', .55)), str(sc.get('levels')))
        if key not in self.stages: self.stages[key] = Stage(typ, self.sb.CW, self.sb.CH, sc)
        return self.stages[key]

    def scene_at(self, k, shot, g, T):
        """scene dict of the shot + the room's state (links) + the characters"""
        sc = dict(shot.get('scene', {'type': 'door'})); typ = sc.get('type', 'door')
        if self.world is not None and typ in ('door', 'room', 'hallway', 'window', 'split'):
            ws = self.world.at(g)
            tgt = sc if typ != 'split' else sc.setdefault('right', dict(sc.get('right') or {'type': 'door'}))
            if 'door' in ws['touched'] and 'open' not in tgt: tgt['open'] = ws['door']
            if typ == 'room' and 'door' in ws['touched']: sc['_door_open'] = ws['door']
            if ws['feet'] and 'feet' not in tgt: tgt['feet'] = True
            if ws['light_under'] and 'light_under' not in tgt: tgt['light_under'] = ws['light_under']
            if ws['knock'] and 'knock' not in tgt: tgt['knock'] = [t - (g - T) for t in ws['knock']]
        if typ == 'face':                                        # close-up: opt-in expressive face, identity, speech
            if 'faces' not in sc: sc['faces'] = self.faces
            if sc.get('faces') == 'expressive':
                who = sc.get('who')
                if who and who in (self.ep.get('cast') or {}): sc['_look'] = (self.ep['cast'] or {})[who]
                tk = sc.get('talk', 'auto')
                sc['_talk'] = bool(active_sub(self.subs, g)) if tk == 'auto' else bool(tk)
        if self.acting is not None and k in self.acting.shots and typ in ('room', 'door', 'hallway'):
            sa = self.acting.shots[k]; samples = sa.sample(T)
            looks = {aid: dict((self.ep.get('cast') or {}).get(aid, {})) for aid in samples}
            if self.faces != 'flat':
                for lk in looks.values(): lk.setdefault('faces', self.faces)
            sc['_actors'] = (self.stage(typ, sc), samples, looks, T)
            # "on" is documented as the list of subjects to frame ("on": ["lea", "tom"]); a bare name stays
            # accepted, and a name that is a place, a door or an object is not a subject at all. qc_observe()
            # below already reads it that way: the framing must agree with the quality control, not crash on it.
            on = (shot.get('camera') or {}).get('on')
            subjects = [a for a in cam_subjects(on) if a in samples]
            if subjects:                                        # the camera keeps those characters in frame
                from ...acting import rig
                stg = self.stage(typ, sc); pts = []
                for a in subjects:
                    smp = samples[a]; hy = 1.55 - .35 * rig.smooth(smp['rig'].get('sit', 0.)) + smp.get('y', 0.)
                    pts.append(stg.to_px(smp['x'], hy, smp['z'])[:2])
                # centre of what the subjects span, so a group is held in frame instead of one of its members.
                # With a single subject min == max: the historical point, bit for bit.
                px = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
                py = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
                self._focus = (px / self.sb.CW, min(.62, py / self.sb.CH + .06))
        return sc

    def world_fx(self, shot, g):
        if self.world is None: return shot
        ws = self.world.at(g); fx = dict(shot.get('fx') or {})
        if ws['flicker']: fx['flicker'] = True
        if ws['dim'] > .01: fx['dim'] = max(float(fx.get('dim', 0.) or 0.) if not isinstance(fx.get('dim'), list) else 0., ws['dim'])
        return dict(shot, fx=fx)

    def qc_observe(self, g):
        """quality control (acting/qc.py): characters of an acted room / door / hallway scene on the canvas"""
        k, t0, t1 = self.tl.at(g)
        if self.acting is None or k not in self.acting.shots: return None
        shot = self.ep['shots'][k]; sc = shot.get('scene') or {}; typ = sc.get('type', 'door')
        if typ not in ('room', 'door', 'hallway'): return None
        from ...acting import rig
        stg = self.stage(typ, sc); sm = self.acting.shots[k].sample(g - t0)
        on = (shot.get('camera') or {}).get('on')
        subjects = cam_subjects(on) if isinstance(on, (str, list)) else list(sm)   # no `on`: control everyone
        people = {}
        for a, s in sm.items():
            px, py, _ = stg.to_px(s['x'], 1.55 - .35 * rig.smooth(s['rig'].get('sit', 0.)) + s.get('y', 0.), s['z'])
            inside = .02 * stg.CW < px < .98 * stg.CW and .02 * stg.CH < py < .98 * stg.CH
            people[a] = dict(in_frame=inside, visible=bool(inside and s.get('visible', 1)), talking=bool(s['talking']), uv=(round(px / stg.CW * 2 - 1, 3), round(1 - py / stg.CH * 2, 3)))
        return dict(shot=k, subjects=[a for a in subjects if a in sm], people=people, cam=None)

    def qc_image(self, g):
        im = self.frame(g).convert('RGB'); return np.asarray(im.resize((im.size[0] // 5, im.size[1] // 5)))

    def acting_events(self):
        out = []
        if self.acting is not None:
            for k, sa in self.acting.shots.items():
                t0 = self.tl.spans[k][0]
                for (t, kind, who, d) in sa.all_events():
                    d = dict(d)
                    if kind == 'step': d['surface'] = 'wood'
                    out.append((t0 + t, kind, who, d))
        if self.world is not None: out += self.world.sfx
        return sorted(out, key=lambda e: e[0])

    def camera(self, img, shot, T, u, g):
        c = shot.get('camera', {}) or {}; CW, CH = img.size
        mv = c.get('move', 'drift'); amt = float(c.get('amount', 1.)); e = ease(u)
        z = float(val(c.get('zoom'), u, 1.0) or 1.0)
        fx, fy = c.get('focus', [.5, .5])
        if getattr(self, '_focus', None) is not None and c.get('on'): fx, fy = self._focus
        self._focus = None
        if mv == 'push_in': z *= 1 + .12 * amt * e
        elif mv == 'pull_out': z *= 1 + .12 * amt * (1 - e)
        elif mv == 'drift': z *= 1 + .03 * e
        dx = dy = 0.
        if mv == 'pan_left': dx = -.06 * amt * (e - .5)
        elif mv == 'pan_right': dx = .06 * amt * (e - .5)
        elif mv == 'pan_up': dy = -.06 * amt * (e - .5)
        elif mv == 'pan_down': dy = .06 * amt * (e - .5)
        shk = float(val(c.get('shake'), u, 0.) or 0.) + (.15 if mv == 'handheld' else 0)
        sx = shk * 6 * (math.sin(T * 37.1) + .6 * math.sin(T * 23.7 + 1.3)); sy = shk * 6 * (math.sin(T * 31.3 + 2) + .6 * math.sin(T * 19.1))
        vw, vh = self.W / z, self.H / z
        cx = CW * (fx + dx) + sx; cy = CH * (fy + dy) + sy
        cx = clamp(cx, vw / 2, CW - vw / 2); cy = clamp(cy, vh / 2, CH - vh / 2)
        box = (cx - vw / 2, cy - vh / 2, cx + vw / 2, cy + vh / 2)
        self.last_box = box                                   # read by tools/console_face_sheet.py (canvas -> frame)
        return img.resize((self.W, self.H), Image.BICUBIC, box=box)

    def post(self, img, shot, T, u, g, k):
        fx = shot.get('fx', {}) or {}
        if self.art == 'aplat':
            # rule 2: snap back onto the palette the camera's resampling just softened. Everything applied
            # after this point is a global operation, which keeps a flat field flat.
            from . import aplat
            img = aplat.snap(img, self.sb._pal or aplat.palette(self.palette))
        a = np.asarray(img.convert('RGB')).astype(np.float32)
        fl = fx.get('flicker')
        if fl and ((int(g * 9) * 2654435761) & 0xffff) / 65535. > .65: a *= .45
        red = float(val(fx.get('red'), u, 0.) or 0.)
        if red: a = a * (1 - .4 * red) + np.array([255, 40, 60]) * .4 * red * (a.mean(-1, keepdims=True) / 255 + .2)
        gl = fx.get('glitch')
        if gl == 'pulse': gl = .5 if int(g * 8) % 3 == 0 else 0
        gl = float(val(gl, u, 0.) or 0.)
        if gl:
            r = rnd(int(g * 30)); H, W = a.shape[:2]
            for _ in range(int(3 + gl * 10)):
                y = r.integers(0, H - 40); h = r.integers(6, 50); dx = r.integers(-int(20 + gl * 60), int(20 + gl * 60) + 1)
                a[y:y + h] = np.roll(a[y:y + h], dx, axis=1)
            a[..., 0] = np.roll(a[..., 0], 6, axis=1); a[..., 2] = np.roll(a[..., 2], -6, axis=1)
        flv = fx.get('flash'); f_amt = 0.
        if isinstance(flv, (int, float)): f_amt = float(flv) * clamp(1 - T / .25)
        elif isinstance(flv, list):
            for e_ in flv:
                at, amtv, dur = (list(e_) + [.25])[:3]
                if at <= T < at + dur: f_amt = max(f_amt, float(amtv) * (1 - (T - at) / dur))
        if f_amt: a = a * (1 - f_amt) + 255 * f_amt
        dim = float(val(fx.get('dim'), u, 0.) or 0.)
        if dim: a *= (1 - dim)
        if fx.get('fade_in'): a *= clamp(T / float(fx['fade_in']))
        if fx.get('fade_out'):
            k0, k1 = self.tl.spans[k]; a *= clamp((k1 - g) / float(fx['fade_out']))
        if self.art != 'aplat':                  # the soft vignette and the grain are the old look, by definition
            H, W = a.shape[:2]; yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            v = 1 - .55 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 2
            a *= np.clip(v, .35, 1)[..., None]
            a += (rnd(int(g * 30) + 3).random(a.shape[:2])[..., None] - .5) * 8
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    # ---------------- UI
    def ui(self, img, shot, T, u, g):
        if self.art == 'aplat':                  # V3: the interface redrawn in the flat art direction (ui2d.py)
            from . import ui2d
            return ui2d.ui(self, img, shot, T, u, g)
        d = ImageDraw.Draw(img); W, H = self.W, self.H; ui = shot.get('ui', {}) or {}; v = self.aspect == '9:16'
        if ui.get('endcard'):
            return self.endcard(img, ui['endcard'] if isinstance(ui['endcard'], dict) else {}, g)
        if ui.get('hud', True) and self.hud.get('show', True):
            x0, y0 = (56, 70) if v else (56, 44)
            fm = font(FONT_MONO, 26, 'Bold'); fb = font(FONT_MONO, 88 if v else 72, 'Bold')
            if int(g * 2) % 2 == 0: d.ellipse([x0, y0 + 8, x0 + 14, y0 + 22], fill=(232, 52, 64))
            d.text((x0 + 24, y0), str(self.hud.get('level', 'NIVEAU 1')).upper(), font=fm, fill=(232, 52, 64))
            d.text((x0 + 4, y0 + 36), self.clock(g, ui), font=fb, fill=(214, 216, 226))
            hs = hearts_at(self.ep, self.lines, g)
            if self.game is not None and self.game.has_hp():         # hearts of the game = hearts of the episode
                n = self.game.hp_at(g); hs = [1] * n + [0] * (self.game.max_hp - n)
            for i, h in enumerate(hs[:3]):
                hx = x0 + 6 + i * 38; hy = y0 + (140 if v else 124)
                self.heart(d, hx, hy, 15, h)
        if ui.get('rule'): self.sb_rule_overlay(img, ui['rule'], T, u)
        if ui.get('choice'): self.choice(img, ui['choice'], g)
        if ui.get('timer'):
            k0, k1 = self.tl.spans[self.tl.at(g)[0]]; t = max(0., k1 - g)
            fb = font(FONT_MONO, 120, 'Bold'); s = f'0:{int(t):02d}'; w = d.textlength(s, font=fb)
            if int(g * 4) % 2 == 0 or t < 2: d.text(((W - w) / 2, H * .2), s, font=fb, fill=RED)
        if ui.get('subs', 'mid') != 'off':
            s = active_sub(self.subs, g)
            if s: self.subtitle(img, s, ui, shot)
        return img

    def clock(self, g, ui):
        if ui.get('clock'): return str(ui['clock'])
        st = str(self.hud.get('clock_start', '3:07')); hh, mm = (int(x) for x in st.split(':'))
        m = hh * 60 + mm + int(g * float(self.hud.get('clock_rate', 1 / 8)))
        return f'{(m // 60) % 24}:{m % 60:02d}'

    def heart(self, d, x, y, s, full):
        pts = [(x, y + s * .3), (x + s * .5, y - s * .2), (x + s, y + s * .3), (x + s * 1.5, y - s * .2), (x + s * 2, y + s * .3), (x + s, y + s * 1.3)]
        if full: d.polygon(pts, fill=(232, 52, 64))
        else: d.polygon(pts, outline=(150, 150, 165))

    def subtitle(self, img, s, ui, shot=None):
        W, H = self.W, self.H; v = self.aspect == '9:16'
        fs = 78 if v else 70; f = font(FONT_MONTSERRAT, fs, 'Black')
        words = s['words']; d = ImageDraw.Draw(img)
        text = ' '.join(w for w, _ in words); tw = d.textlength(text, font=f)
        pos = ui.get('subs', 'mid'); named = {'mid': H * .655, 'low': H * .8, 'top': H * .3}
        y = named.get(pos, H * .655)
        if ui.get('choice'): y = H * .5
        elif self.caps is not None:                  # sous-titres surs, la regle seule (captions/safe.py)
            from ...captions import safe as _CAPS
            y = _CAPS.place_rule(self.caps, pos, named, H, self.aspect, _CAPS.shot_hint(shot), fs * 1.6, 46.)
        if tw > W - 80:
            f = font(FONT_MONTSERRAT, int(fs * (W - 80) / tw), 'Black'); tw = d.textlength(text, font=f)
        bx0, by0 = int(max(0, (W - tw) / 2 - 30)), int(max(0, y - 30)); bx1, by1 = int(min(W, (W + tw) / 2 + 40)), int(min(H, y + fs * 1.6))
        sh = Image.new('L', (bx1 - bx0, by1 - by0), 0); sd = ImageDraw.Draw(sh); x = (W - tw) / 2 - bx0
        for w, kf in words:
            sd.text((x + 4, y - by0 + 6), w, font=f, fill=230); x += d.textlength(w + ' ', font=f)
        sh = sh.filter(ImageFilter.GaussianBlur(5)); img.paste(Image.new('RGB', sh.size, (0, 0, 0)), (bx0, by0), sh)
        d = ImageDraw.Draw(img); x = (W - tw) / 2
        ln = self.lines[s['line']]
        if ln.get('label'):
            lab = ln['label'].upper()
            if not lab.startswith('—'): lab = f'— {lab} —'
            fl = font(FONT_MONO, 28, 'Bold'); lw = d.textlength(lab, font=fl)
            d.text(((W - lw) / 2, y - 46), lab, font=fl, fill=LABEL_COLORS.get(ln.get('label_color', 'green'), GREEN_UI))
        for w, kf in words:
            d.text((x, y), w, font=f, fill=GOLD if kf else WHITE); x += d.textlength(w + ' ', font=f)

    def sb_rule_overlay(self, img, r, T, u):
        if self.art == 'aplat':
            # a flat scrim of the palette's ink, then the printed card. A uniform blend sends a flat field to a
            # flat field, so the scrim does not reintroduce a gradient over the aplats underneath.
            from . import aplat, ui2d
            pal = aplat.palette(r.get('palette') or self.palette)
            lay = Image.new('RGBA', (self.W, self.H), tuple(pal['ink']) + (214,))
            ui2d.rule_card(lay, r, T, u, pal, ui2d.card_unit(self.W, self.H)); img.paste(lay, (0, 0), lay)
            return
        lay = Image.new('RGBA', (self.sb.CW, self.sb.CH), (8, 10, 24, 200)); self.sb.rule_card(lay, r, T, u)
        lay = lay.resize((self.W, self.H)); img.paste(lay, (0, 0), lay)

    def choice(self, img, c, g):
        d = ImageDraw.Draw(img); W, H = self.W, self.H; v = self.aspect == '9:16'
        fb = font(FONT_BEBAS, 150 if v else 120); t = c.get('title', 'QUI CROIS-TU ?').upper(); w = d.textlength(t, font=fb)
        y0 = H * (.2 if v else .12)
        d.text(((W - w) / 2 + 5, y0 + 6), t, font=fb, fill=(0, 0, 0)); d.text(((W - w) / 2, y0), t, font=fb, fill=WHITE)
        letters = [L_ for L_ in ('A', 'B', 'C') if c.get(L_)] or ['A', 'B']      # 3 branches: A/B/C (story layer)
        sel = c.get('cursor', 'blink')
        if sel in ('blink', '?'): sel = letters[int(g * 1.5) % len(letters)]
        cols = {'A': tuple(c.get('A_color', GREEN_UI)), 'B': tuple(c.get('B_color', ORANGE)), 'C': tuple(c.get('C_color', GOLD))}
        fp = font(FONT_MONTSERRAT, 50 if v else 46, 'Black'); n = len(letters)
        for k, L_ in enumerate(letters):
            txt = c.get(L_, ''); txt = ' '.join(txt) if isinstance(txt, list) else str(txt)
            if v: x0, x1, y = W * .09, W * .91, H * (.66 + k * .1)                # 3 options still fit vertically
            elif n < 3: x0 = W * (.08 + k * .44); x1 = x0 + W * .4; y = H * .7    # 2 options: unchanged layout
            else: x0 = W * (.05 + k * .317); x1 = x0 + W * .29; y = H * .7
            hgt = 130 if v else 120; on = sel == L_
            col = cols[L_] if on else mix(cols[L_], (20, 24, 44), .55)
            d.rounded_rectangle([x0, y, x1, y + hgt], radius=hgt // 2, fill=col)
            d.ellipse([x0 + 16, y + 16, x0 + hgt - 16, y + hgt - 16], fill=(16, 20, 40))
            lw = d.textlength(L_, font=fp); d.text((x0 + hgt / 2 - lw / 2, y + hgt / 2 - 30), L_, font=fp, fill=col)
            d.text((x0 + hgt + 10, y + hgt / 2 - 30), txt.upper()[:22], font=fp, fill=(16, 20, 40))

    def endcard(self, img, e, g):
        img.paste(Image.new('RGB', img.size, (8, 10, 24)), (0, 0)); d = ImageDraw.Draw(img); W, H = self.W, self.H; v = self.aspect == '9:16'
        fb = font(FONT_BEBAS, 170 if v else 150); fs = font(FONT_MONO, 40, 'Bold'); fm = font(FONT_MONTSERRAT, 46, 'Black')
        def cen(y, t, f, c):
            w = d.textlength(t, font=f); d.text(((W - w) / 2, y), t, font=f, fill=c)
        title = e.get('title', self.hud.get('series', 'NE METS PAS PAUSE')).upper()
        y = H * (.22 if v else .1)
        for i, part in enumerate(title.split('\n')): cen(y + i * (160 if v else 140), part, fb, WHITE if i == 0 else GOLD)
        y += (160 if v else 140) * (title.count('\n') + 1) + 20
        cen(y, (e.get('part') or self.hud.get('level', '')).upper(), fs, (232, 52, 64)); y += 110
        cen(y, e.get('headline', 'A OU B ?').upper(), font(FONT_BEBAS, 130 if v else 110), GOLD); y += 170 if v else 140
        cen(y, e.get('cta', 'VOTE EN COMMENTAIRE').upper(), fm, WHITE); y += 100
        bw = 330; d.rounded_rectangle([W / 2 - bw, y, W / 2 + bw, y + 100], radius=50, fill=(232, 52, 64))
        cen(y + 22, e.get('button', 'ABONNE-TOI').upper(), fm, WHITE)
        fo = max(0., (g - (self.duration - 1.3)) / 1.3)
        if fo > 0: img = Image.blend(img, Image.new('RGB', img.size, (0, 0, 0)), min(1., fo * .85))
        return img

    def raw_frame(self, g):
        k, t0, t1 = self.tl.at(g)
        shot = self.ep['shots'][k]; T = g - t0; u = clamp(T / max(1e-3, t1 - t0))
        canvas = self.sb.render(k, self.scene_at(k, shot, g, T), T, u, g); shot = self.world_fx(shot, g)
        return self.post(self.camera(canvas.convert('RGB'), shot, T, u, g), shot, T, u, g, k)

    def frame(self, g):
        k, t0, t1 = self.tl.at(g)
        shot = self.ep['shots'][k]; T = g - t0; u = clamp(T / max(1e-3, t1 - t0))
        sc = self.scene_at(k, shot, g, T); shot = self.world_fx(shot, g)
        if (shot.get('fx') or {}).get('black'): img = Image.new('RGB', (self.W, self.H), (4, 5, 10))
        else:
            canvas = self.sb.render(k, sc, T, u, g)
            img = self.camera(canvas.convert('RGB'), shot, T, u, g)
            img = self.post(img, shot, T, u, g, k)
        return self.ui(img, shot, T, u, g)
