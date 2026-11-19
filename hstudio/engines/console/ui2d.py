"""CONSOLE 2D, the on-screen interface in the "aplats" art direction (V3, opt-in: episode "art": "aplat").

Second slice of the art redesign. `aplat.py` redrew the *image*; this redraws what sits **on** it: HUD, clock,
hearts, subtitles, choice cards, rule card, timer, end card, and the interactive states of all of them.

Nothing here runs unless an episode asks for `"art": "aplat"`. An episode without the key never reaches this
module: `ConsoleEngine.ui` branches on `self.art` and the original methods are untouched. That is what
tools/regress.py and tools/regress_v2.py keep proving.

The interface obeys the same five rules as the sets (see the header of aplat.py), read as interface:

1. Flat fields.      Every panel is one flat colour. The old UI leaned on a gaussian-blurred slab behind the
                     subtitles; here a subtitle sits on a hard-edged plate. No blur anywhere in this file.
2. Limited palette.  No UI colour is hard-coded. `roles()` derives every one of them from the scene palette, so
                     the interface changes mood with the room instead of floating above it in its own colours.
                     The one exception is text contrast, which is *computed* (`on()`), never picked by hand.
3. Ink.              Every panel carries the same contour as a prop, plus a hard offset block of ink instead of
                     a soft drop shadow. That offset is what makes a panel sit on the image rather than in it.
4. Light is a shape. An active element is not lit, it is *filled*: selection swaps the plate to the key colour
                     and the text to its complement. State is read as a value step, exactly like a lit surface.
5. Silhouette first. One shape vocabulary everywhere -- the cut corner (`cut`) -- so a panel is recognisable as
                     this series' interface at thumbnail size, which is the size most of the audience sees.

Interactive states are a closed vocabulary, used identically by the choice cards, the hearts and the rec dot:

    idle      plate `plate`, ink contour, text `paper_d`
    active    plate in the element's own colour, text = on(plate), plus the cursor notch
    pressed   the whole panel moved onto its own drop block (it reads as pushed into the page)
    spent     ink contour only, no fill (an empty heart, the rec dot between blinks)

Legibility was the constraint, not an afterthought: the panels keep the anchors, sizes and font sizes of the
original UI (subtitle 78/70, HUD at 56/70, choice cards at the same fractions of the frame), so what changes is
the drawing, not the reading distance. Everything scales from `S = min(W, H) / 1080`, identical in 9:16 and 16:9.
"""
from PIL import Image, ImageDraw
from ..common import font, active_sub, hearts_at
from ...paths import FONT_MONTSERRAT, FONT_BEBAS, FONT_MONO
from . import aplat

mix = aplat.mix


# ---------------------------------------------------------------- colour roles (rule 2)
def roles(pal):
    """the interface colours, all derived from the scene palette: the UI follows the room's mood.

    All of them are palette entries except `paper_d`, which is a value step between two of them. That one is
    only ever used by panels composited *after* `ConsoleEngine.post`, so it is never seen by `aplat.snap`; the
    rule card, which is drawn on the scene canvas and therefore does go through the snap, uses palette entries
    only. Keeping it that way is what lets the snap stay exactly as the sets left it."""
    return {
        'ink':     pal['ink'],
        'plate':   pal['shadow'],
        'plate_l': pal['wall_d'],
        'paper':   pal['moon'],
        'paper_d': mix(pal['moon'], pal['shadow'], 0.42),
        'accent':  pal['accent'],
        'key':     pal['light'],
        'glow':    pal['glow'],
        'sky':     pal['sky'],
    }


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def on(col, R):
    """text colour for a given plate: computed, never chosen, so no palette can produce unreadable text"""
    return R['ink'] if lum(col) > 140 else R['paper']


def label_color(name, R):
    """the subtitle speaker colours of the series, re-expressed in the palette of the moment"""
    return {'green': R['glow'], 'orange': R['key'], 'red': R['accent'], 'gold': R['accent'],
            'white': R['paper'], 'blue': R['sky']}.get(name or 'green', R['glow'])


def palette_of(eng, shot):
    """the palette this frame is drawn in -- read from the shot, never from the renderer's last state, so a
    frame is the same whatever order the frames were asked for (the engine must stay deterministic)"""
    pname = (shot.get('scene') or {}).get('palette') or eng.palette
    return aplat.palette(pname)


# ---------------------------------------------------------------- flat primitives (rules 1, 3, 5)
def cut_pts(x0, y0, x1, y1, c):
    """the shape of every panel in this interface: a rectangle with its top-right corner cut off"""
    c = max(0, min(c, (x1 - x0) / 2, (y1 - y0) / 2))
    return [(x0, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1), (x0, y1)]


def stroke(d, pts, col, w):
    d.line([tuple(p) for p in pts] + [tuple(pts[0])], fill=col, width=max(1, int(w)), joint='curve')


def panel(d, x0, y0, x1, y1, fill, R, iw, cut=None, drop=None, ink=True):
    """a flat panel: a hard block of ink behind it (rule 3, no blur), the field, then the contour"""
    c = (y1 - y0) * 0.28 if cut is None else cut
    dp = iw * 2.2 if drop is None else drop
    if dp:
        d.polygon(cut_pts(x0 + dp, y0 + dp, x1 + dp, y1 + dp, c), fill=R['ink'])
    pts = cut_pts(x0, y0, x1, y1, c)
    d.polygon(pts, fill=fill)
    if ink:
        stroke(d, pts, R['ink'], iw)
    return pts


def notch(d, x, y, h, col):
    """the cursor: a hard triangle pointing into the panel it selects. The only 'pointer' in this interface."""
    d.polygon([(x, y - h / 2), (x + h * 0.72, y), (x, y + h / 2)], fill=col)


def text_at(d, xy, s, f, col, R=None, off=0):
    """text, optionally misregistered against a hard ink copy of itself (a printing idiom, not a glow)"""
    if off and R:
        d.text((xy[0] + off, xy[1] + off), s, font=f, fill=R['ink'])
    d.text(xy, s, font=f, fill=col)


def centered(d, y, s, f, col, W, R=None, off=0):
    w = d.textlength(s, font=f)
    text_at(d, ((W - w) / 2, y), s, f, col, R, off)
    return w


def heart_pts(x, y, s):
    return [(x, y + s * .3), (x + s * .5, y - s * .2), (x + s, y + s * .3),
            (x + s * 1.5, y - s * .2), (x + s * 2, y + s * .3), (x + s, y + s * 1.3)]


# ---------------------------------------------------------------- flat icons (rule card)
def icon(d, kind, cx, cy, size, R, iw):
    """the rule-card pictograms as flat shapes with one ink contour, instead of the old 16x16 pixel grid"""
    s = size / 2
    if kind in ('door_x', 'door'):
        # the same door as the set, reduced to a pictogram: leaf, the lit half, the handle
        pts = [(cx - s * .68, cy - s * .86), (cx + s * .68, cy - s * .86), (cx + s * .68, cy + s * .86),
               (cx - s * .68, cy + s * .86)]
        d.polygon(pts, fill=R['paper']); stroke(d, pts, R['ink'], iw)
        d.polygon([(cx + s * .16, cy - s * .86), (cx + s * .68, cy - s * .86),
                   (cx + s * .68, cy + s * .86), (cx + s * .16, cy + s * .86)], fill=R['plate_l'])
        d.ellipse([cx + s * .34, cy - s * .10, cx + s * .54, cy + s * .10], fill=R['ink'])
    elif kind in ('eye', 'eye_x'):
        pts = [(cx - s * .95, cy), (cx, cy - s * .58), (cx + s * .95, cy), (cx, cy + s * .58)]
        d.polygon(pts, fill=R['paper']); stroke(d, pts, R['ink'], iw)
        d.ellipse([cx - s * .34, cy - s * .34, cx + s * .34, cy + s * .34], fill=R['ink'])
    elif kind in ('clock', 'clock_x'):
        d.ellipse([cx - s * .84, cy - s * .84, cx + s * .84, cy + s * .84], fill=R['paper'], outline=R['ink'], width=iw)
        d.line([cx, cy, cx, cy - s * .56], fill=R['ink'], width=max(2, iw))
        d.line([cx, cy, cx + s * .42, cy], fill=R['ink'], width=max(2, iw))
    elif kind in ('phone', 'phone_x', 'console', 'console_x'):
        pts = cut_pts(cx - s * .52, cy - s * .88, cx + s * .52, cy + s * .88, s * .2)
        d.polygon(pts, fill=R['plate_l']); stroke(d, pts, R['ink'], iw)
        d.rectangle([cx - s * .34, cy - s * .70, cx + s * .34, cy + s * .04], fill=R['glow'], outline=R['ink'], width=max(1, iw - 1))
        d.ellipse([cx - s * .30, cy + s * .30, cx - s * .06, cy + s * .54], fill=R['ink'])
    elif kind in ('light_off', 'bulb'):
        d.ellipse([cx - s * .52, cy - s * .86, cx + s * .52, cy + s * .18], fill=R['key'], outline=R['ink'], width=iw)
        d.rectangle([cx - s * .26, cy + s * .18, cx + s * .26, cy + s * .62], fill=R['plate_l'], outline=R['ink'], width=iw)
    elif kind in ('bed', 'bed_x'):
        pts = [(cx - s * .92, cy - s * .10), (cx + s * .92, cy - s * .10),
               (cx + s * .92, cy + s * .46), (cx - s * .92, cy + s * .46)]
        d.polygon(pts, fill=R['plate_l']); stroke(d, pts, R['ink'], iw)
        d.polygon([(cx - s * .86, cy - s * .40), (cx - s * .28, cy - s * .40),
                   (cx - s * .28, cy - s * .10), (cx - s * .86, cy - s * .10)], fill=R['paper'])
        stroke(d, [(cx - s * .86, cy - s * .40), (cx - s * .28, cy - s * .40),
                   (cx - s * .28, cy - s * .10), (cx - s * .86, cy - s * .10)], R['ink'], max(1, iw - 1))
    if kind.endswith('_x'):
        # the interdiction: two accent bars the size of the pictogram, each backed by an ink bar so the cross
        # keeps its contour whatever it crosses (rule 3 -- the cross is a shape, not a highlight)
        w = max(4, int(size * .10))
        for a, b in (((-1, -1), (1, 1)), ((1, -1), (-1, 1))):
            x0, y0 = cx + a[0] * s * .80, cy + a[1] * s * .80
            x1, y1 = cx + b[0] * s * .80, cy + b[1] * s * .80
            d.line([x0, y0, x1, y1], fill=R['ink'], width=int(w * 1.6))
            d.line([x0, y0, x1, y1], fill=R['accent'], width=w)


# ---------------------------------------------------------------- HUD
def hud(eng, img, ui_, g, R, S):
    """one cartouche instead of four floating items: a plate with the level tag, the clock and the hearts.

    The old HUD was three unrelated bits of text at the top-left. Grouping them into a single panel is what
    makes the interface read as *designed* rather than *overlaid* -- and it gives the clock a field to sit on,
    which is what the subtitles were missing too."""
    d = ImageDraw.Draw(img)
    v = eng.aspect == '9:16'
    iw = max(2, int(4 * S))
    x0 = int(50 * S)
    y0 = int((60 * S) if v else (36 * S))
    ft = font(FONT_MONO, int(26 * S), 'Bold')
    fc = font(FONT_BEBAS, int((108 if v else 92) * S))

    level = str(eng.hud.get('level', 'NIVEAU 1')).upper()
    clock = eng.clock(g, ui_)
    pad = int(18 * S)
    dot = int(13 * S)
    tag_h = int(42 * S)
    tag_w = int(d.textlength(level, font=ft)) + dot * 3 + pad * 2
    clock_w = int(d.textlength(clock, font=fc))

    hs = hearts_at(eng.ep, eng.lines, g)
    if eng.game is not None and eng.game.has_hp():          # hearts of the game = hearts of the episode
        n = eng.game.hp_at(g)
        hs = [1] * n + [0] * (eng.game.max_hp - n)
    hs = hs[:3]
    hsz = int(23 * S)
    pitch = int(58 * S)
    hearts_w = (len(hs) - 1) * pitch + hsz * 2 if hs else 0

    body_w = max(tag_w, clock_w + pad * 2, hearts_w + pad * 2)
    clock_h = int(fc.size * 0.80)
    body_h = pad + clock_h + (int(12 * S) + hsz * 2 if hs else 0) + pad
    x1 = x0 + body_w
    y_tag1 = y0 + tag_h

    # the cartouche: the body first, the tag plate riding on its top edge
    panel(d, x0, y_tag1 - iw, x1, y_tag1 + body_h, R['plate'], R, iw, cut=int(26 * S))
    panel(d, x0, y0, x0 + tag_w, y_tag1, R['accent'], R, iw, cut=int(16 * S), drop=0)
    tcol = on(R['accent'], R)
    # the rec dot: filled while it is on, contour only while it is off (the "spent" state of the vocabulary)
    dcx, dcy = x0 + pad + dot / 2, y0 + tag_h / 2
    if int(g * 2) % 2 == 0:
        d.ellipse([dcx - dot / 2, dcy - dot / 2, dcx + dot / 2, dcy + dot / 2], fill=tcol)
    else:
        d.ellipse([dcx - dot / 2, dcy - dot / 2, dcx + dot / 2, dcy + dot / 2], outline=tcol, width=max(2, iw - 1))
    d.text((x0 + pad + dot * 2, y0 + tag_h / 2 - ft.size * 0.72), level, font=ft, fill=tcol)

    # the clock, misregistered against an ink copy of itself (rule 3: ink, not a glow)
    d.text((x0 + pad + max(2, iw - 1), y_tag1 + pad - int(fc.size * 0.18) + max(2, iw - 1)), clock, font=fc, fill=R['ink'])
    d.text((x0 + pad, y_tag1 + pad - int(fc.size * 0.18)), clock, font=fc, fill=R['paper'])

    hy = y_tag1 + pad + clock_h + int(12 * S)
    for i, h in enumerate(hs):
        hx = x0 + pad + i * pitch
        pts = heart_pts(hx, hy, hsz)
        if h:
            d.polygon(pts, fill=R['accent'])
            stroke(d, pts, R['ink'], max(2, iw - 2))
        else:                                    # spent: the contour alone, no fill
            stroke(d, pts, R['paper_d'], max(2, iw - 2))


# ---------------------------------------------------------------- subtitles
def subtitle(eng, img, s, ui_, R, S, shot=None):
    """the subtitle on a hard plate instead of a blurred slab, with the speaker as a tab welded to its top edge.

    This is the single biggest legibility win of the slice: the old blur gave a soft, uneven backing whose
    contrast depended on the image under it; a flat plate gives the same contrast on every frame, which is what
    a phone screen in daylight needs."""
    W, H = eng.W, eng.H
    v = eng.aspect == '9:16'
    d = ImageDraw.Draw(img)
    iw = max(2, int(4 * S))
    fs = int((78 if v else 70) * S)
    f = font(FONT_MONTSERRAT, fs, 'Black')
    words = s['words']
    text = ' '.join(w for w, _ in words)
    tw = d.textlength(text, font=f)
    if tw > W - 100 * S:
        f = font(FONT_MONTSERRAT, max(12, int(fs * (W - 100 * S) / tw)), 'Black')
        tw = d.textlength(text, font=f)
        fs = f.size
    pos = ui_.get('subs', 'mid')
    named = {'mid': H * .655, 'low': H * .8, 'top': H * .3}
    y = named.get(pos, H * .655)
    if ui_.get('choice'):
        y = H * .5
    elif getattr(eng, 'caps', None) is not None:     # sous-titres surs, la regle seule (captions/safe.py)
        from ...captions import safe as _CAPS
        y = _CAPS.place_rule(eng.caps, pos, named, H, eng.aspect, _CAPS.shot_hint(shot),
                             fs * 1.18 + int(26 * S), int(46 * S))

    padx, padt, padb = int(30 * S), int(22 * S), int(26 * S)
    bx0 = max(int(8 * S), int((W - tw) / 2 - padx))
    bx1 = min(W - int(8 * S), int((W + tw) / 2 + padx))
    by0 = int(y - padt)
    by1 = int(y + fs * 1.18 + padb)
    panel(d, bx0, by0, bx1, by1, R['plate'], R, iw, cut=int((by1 - by0) * 0.22))

    ln = eng.lines[s['line']]
    if ln.get('label'):
        lab = ln['label'].upper().strip('— ').strip()
        fl = font(FONT_MONO, int(28 * S), 'Bold')
        lw = d.textlength(lab, font=fl)
        tabh = int(46 * S)
        # the tab is as wide as the name, not as wide as the plate: a long speaker ("VOIX DERRIÈRE LA PORTE")
        # over a two-word subtitle sticks out to the right rather than getting cut off. Only the frame edge
        # bounds it, and if even that is not enough the name shrinks instead of being clipped.
        room = W - int(8 * S) - bx0 - int(44 * S)
        if lw > room:
            fl = font(FONT_MONO, max(10, int(fl.size * room / lw)), 'Bold')
            lw = d.textlength(lab, font=fl)
        tx1 = bx0 + int(lw + 44 * S)
        panel(d, bx0, by0 - tabh + iw, tx1, by0 + iw, label_color(ln.get('label_color', 'green'), R), R, iw,
              cut=int(14 * S), drop=0)
        d.text((bx0 + int(22 * S), by0 - tabh + iw + tabh / 2 - fl.size * 0.72), lab, font=fl,
               fill=on(label_color(ln.get('label_color', 'green'), R), R))

    x = (W - tw) / 2
    for w, kf in words:
        d.text((x, y), w, font=f, fill=R['accent'] if kf else R['paper'])
        x += d.textlength(w + ' ', font=f)


# ---------------------------------------------------------------- choice cards
def choice(eng, img, c, g, R, S):
    """the two choices as flat cards. Selection is a filled plate, not a glow: rule 4 applied to an interface."""
    d = ImageDraw.Draw(img)
    W, H = eng.W, eng.H
    v = eng.aspect == '9:16'
    iw = max(2, int(4 * S))
    fb = font(FONT_BEBAS, int((150 if v else 120) * S))
    t = str(c.get('title', 'QUI CROIS-TU ?')).upper()
    y0 = H * (.2 if v else .12)
    tw = d.textlength(t, font=fb)
    if tw > W - 80 * S:
        fb = font(FONT_BEBAS, max(12, int(fb.size * (W - 80 * S) / tw)))
    # the title: a hard accent copy under a paper copy. A print misregistration, never a drop shadow.
    # Kept tight (about one ink weight): on the before/after sheet a wider offset read as a blurred fringe at
    # thumbnail size, which is the size that has to work first.
    w_ = d.textlength(t, font=fb)
    d.text(((W - w_) / 2 - iw, y0 - iw), t, font=fb, fill=R['accent'])
    d.text(((W - w_) / 2, y0), t, font=fb, fill=R['paper'])

    sel = c.get('cursor', 'blink')
    if sel in ('blink', '?'):
        sel = 'A' if int(g * 1.5) % 2 == 0 else 'B'
    cols = {'A': tuple(c.get('A_color') or R['glow']), 'B': tuple(c.get('B_color') or R['key'])}
    fp = font(FONT_MONTSERRAT, int((50 if v else 46) * S), 'Black')
    fl = font(FONT_BEBAS, int((86 if v else 78) * S))
    press = str(c.get('press', '') or '').upper()

    for k, L_ in enumerate(('A', 'B')):
        txt = c.get(L_, '')
        txt = ' '.join(txt) if isinstance(txt, list) else str(txt)
        if v:
            x0, x1, y = W * .09, W * .91, H * (.66 + k * .1)
            hgt = int(130 * S)
        else:
            x0 = W * (.08 + k * .44); x1 = x0 + W * .4; y = H * .7
            hgt = int(120 * S)
        act = sel == L_
        dp = iw * 2.4
        # pressed: the card sits on its own drop block instead of above it
        off = dp if press == L_ else 0
        fill = cols[L_] if act else R['plate']
        panel(d, x0 + off, y + off, x1 + off, y + hgt + off, fill, R, iw,
              cut=int(hgt * 0.34), drop=0 if off else dp)
        tcol = on(fill, R) if act else R['paper_d']
        # the letter badge, inverted against the card so A / B reads first at thumbnail size
        bx0 = x0 + off + int(14 * S)
        bsz = hgt - int(28 * S)
        badge = R['ink'] if act else mix(cols[L_], R['plate'], .5)
        panel(d, bx0, y + off + int(14 * S), bx0 + bsz, y + off + int(14 * S) + bsz, badge, R, max(2, iw - 1),
              cut=int(bsz * 0.26), drop=0)
        lw = d.textlength(L_, font=fl)
        d.text((bx0 + bsz / 2 - lw / 2, y + off + int(14 * S) + bsz / 2 - fl.size * 0.70), L_, font=fl,
               fill=cols[L_] if act else on(badge, R))
        d.text((bx0 + bsz + int(22 * S), y + off + hgt / 2 - fp.size * 0.68), txt.upper()[:22], font=fp, fill=tcol)
        if act:
            notch(d, x0 + off - int(26 * S), y + off + hgt / 2, int(40 * S), R['accent'])


# ---------------------------------------------------------------- timer
def timer(eng, img, t, g, R, S):
    """the countdown as a plate that inverts on every beat instead of disappearing: the pulse stays, the number
    never leaves the frame (the old one blinked out, which on a phone reads as a glitch)"""
    d = ImageDraw.Draw(img)
    W, H = eng.W, eng.H
    iw = max(2, int(4 * S))
    fb = font(FONT_BEBAS, int(150 * S))
    s = f'0:{int(t):02d}'
    tw = d.textlength(s, font=fb)
    hot = int(g * 4) % 2 == 0 or t < 2
    pad = int(26 * S)
    x0 = (W - tw) / 2 - pad
    x1 = (W + tw) / 2 + pad
    y0 = H * .2 - int(14 * S)
    y1 = y0 + fb.size * 0.88 + int(22 * S)
    fill = R['accent'] if hot else R['plate']
    panel(d, x0, y0, x1, y1, fill, R, iw, cut=int((y1 - y0) * 0.26))
    d.text(((W - tw) / 2, y0 + int(6 * S)), s, font=fb, fill=on(fill, R) if hot else R['accent'])


# ---------------------------------------------------------------- rule card
def card_unit(W, H):
    """the rule card's size reference, in the pixels of whichever canvas it is drawn on.

    Both callers draw a region whose *visible* extent is W x H in that canvas's own pixels (the scene canvas is
    larger, but the camera only keeps W x H of it; the overlay layer is exactly W x H). Deriving the unit from
    the visible frame is what keeps the card roughly the same object in 9:16 and in 16:9. The height term binds
    in 16:9 and is what leaves the lower third free for the subtitle plate."""
    return min(W, H * 0.84) * 0.96


def rule_card(im, sc, T, u, pal, unit):
    """the rule as a printed card: ink field, paper rule frame, accent tag, the broken rule reversed out.

    Drawn on whatever canvas it is given (the scene canvas for a `rule_card` shot, an overlay layer for
    `ui.rule`), so both entry points produce the same object. The card's height follows its content -- the old
    one was a fixed fraction of the frame and left a hole between the last line and the pictogram.

    `unit` is the card's size reference, given in the pixels of the canvas it is drawn on. The caller computes
    it from the *visible* frame rather than from the canvas, because the scene canvas is 18% wider than what
    the camera keeps: sized on the canvas, the card's ink contour fell outside the frame on both sides.

    Everything here uses palette entries only: a `rule_card` shot is drawn before `aplat.snap`, so a derived
    tone would be quantised to whatever palette colour happened to be nearest."""
    CW, CH = im.size
    R = roles(pal)
    d = ImageDraw.Draw(im)
    iw = max(2, int(5 * min(CW, CH) / 1080.0))
    W_ = unit
    cx = CW / 2

    lines = [str(l).upper() for l in sc.get('lines', ['NE QUITTE PAS', 'TA CHAMBRE'])[:3]]
    hl = sc.get('highlight', len(lines) - 1)
    fb = font(FONT_BEBAS, int(W_ * .115))
    pad = W_ * .085
    step = W_ * .125
    icon_sz = W_ * .22
    card_w = W_ * .86
    card_h = pad + len(lines) * step + W_ * .05 + icon_sz + pad
    cy0 = CH * (.40 if CW > CH else .44) - card_h / 2   # above centre: the subtitle plate owns the lower third

    panel(d, cx - card_w / 2, cy0, cx + card_w / 2, cy0 + card_h, R['plate'], R, iw, cut=W_ * .09)
    # the paper rule inside the ink contour: the card reads as printed matter, not as a dialog box
    inset = W_ * .035
    stroke(d, cut_pts(cx - card_w / 2 + inset, cy0 + inset, cx + card_w / 2 - inset, cy0 + card_h - inset, W_ * .055),
           R['paper'], max(2, iw - 2))

    num = sc.get('number', 1)
    tag = str(sc.get('tag', f'RÈGLE N°{num}')).upper()
    ft = font(FONT_MONO, int(W_ * .034), 'Bold')
    tw = d.textlength(tag, font=ft)
    tag_h = W_ * .075
    ty = cy0 - tag_h * .42
    panel(d, cx - tw / 2 - W_ * .035, ty, cx + tw / 2 + W_ * .035, ty + tag_h, R['accent'], R, iw, cut=W_ * .022)
    d.text((cx - tw / 2, ty + tag_h / 2 - ft.size * 0.72), tag, font=ft, fill=on(R['accent'], R))

    y = cy0 + pad
    for i, l in enumerate(lines):
        lw = d.textlength(l, font=fb)
        if i == hl:
            # the rule that matters is reversed out of a paper band: the strongest value step on the card.
            # The band is measured on the glyphs themselves, so it fits any wording in any aspect.
            bb = d.textbbox((cx - lw / 2, y), l, font=fb)
            panel(d, bb[0] - W_ * .030, bb[1] - W_ * .018, bb[2] + W_ * .030, bb[3] + W_ * .020,
                  R['paper'], R, max(2, iw - 1), cut=W_ * .022, drop=0)
            d.text((cx - lw / 2, y), l, font=fb, fill=R['ink'])
        else:
            d.text((cx - lw / 2, y), l, font=fb, fill=R['paper'])
        y += step
    icon(d, sc.get('icon', 'door_x'), cx, cy0 + card_h - pad - icon_sz / 2, icon_sz, R, iw)


# ---------------------------------------------------------------- end card
def endcard(eng, img, e, g, R, S):
    """the end card composed for this style: the graphic band of `face_bg`, the series' eye, flat plates."""
    W, H = eng.W, eng.H
    v = eng.aspect == '9:16'
    img.paste(Image.new('RGB', img.size, R['ink']), (0, 0))
    d = ImageDraw.Draw(img)
    iw = max(2, int(5 * S))
    # the same off-centre band that backs the face close-up: the end card belongs to the same drawing
    d.polygon([(W * .08, 0), (W * .74, 0), (W * .60, H), (0, H)], fill=R['plate'])

    fb = font(FONT_BEBAS, int((170 if v else 150) * S))
    fs = font(FONT_MONO, int(40 * S), 'Bold')
    fm = font(FONT_MONTSERRAT, int(46 * S), 'Black')
    title = str(e.get('title', eng.hud.get('series', 'NE METS PAS PAUSE'))).upper()
    y = H * (.22 if v else .08)
    step = int((160 if v else 140) * S)
    for i, part in enumerate(title.split('\n')):
        w_ = d.textlength(part, font=fb)
        d.text(((W - w_) / 2 - iw * 1.8, y + i * step - iw * 1.8), part, font=fb, fill=R['accent'])
        d.text(((W - w_) / 2, y + i * step), part, font=fb, fill=R['paper'])
    y += step * (title.count('\n') + 1) + int(20 * S)

    part = str(e.get('part') or eng.hud.get('level', '')).upper()
    if part:
        pw = d.textlength(part, font=fs)
        ph = int(62 * S)
        panel(d, W / 2 - pw / 2 - int(26 * S), y, W / 2 + pw / 2 + int(26 * S), y + ph, R['accent'], R, iw,
              cut=int(18 * S))
        d.text(((W - pw) / 2, y + ph / 2 - fs.size * 0.74), part, font=fs, fill=on(R['accent'], R))
    y += int(130 * S)

    fh = font(FONT_BEBAS, int((130 if v else 110) * S))
    centered(d, y, str(e.get('headline', 'A OU B ?')).upper(), fh, R['key'], W, R, iw)
    y += int((170 if v else 140) * S)
    centered(d, y, str(e.get('cta', 'VOTE EN COMMENTAIRE')).upper(), fm, R['paper'], W)
    y += int(110 * S)

    bw = int(340 * S)
    bh = int(108 * S)
    panel(d, W / 2 - bw, y, W / 2 + bw, y + bh, R['accent'], R, iw, cut=int(34 * S))
    btn = str(e.get('button', 'ABONNE-TOI')).upper()
    bwt = d.textlength(btn, font=fm)
    d.text(((W - bwt) / 2, y + bh / 2 - fm.size * 0.70), btn, font=fm, fill=on(R['accent'], R))

    # the eye of the series, the motif of the bedroom poster, as the signature of the card
    ey = y + bh + int((150 if v else 110) * S)
    ew = int((150 if v else 120) * S)
    if ey + ew * 0.6 < H:
        pts = [(W / 2 - ew, ey), (W / 2, ey - ew * .56), (W / 2 + ew, ey), (W / 2, ey + ew * .56)]
        d.polygon(pts, fill=R['plate_l'])
        stroke(d, pts, R['paper_d'], max(2, iw - 2))
        d.ellipse([W / 2 - ew * .30, ey - ew * .30, W / 2 + ew * .30, ey + ew * .30], fill=R['paper'])
        d.ellipse([W / 2 - ew * .13, ey - ew * .13, W / 2 + ew * .13, ey + ew * .13], fill=R['ink'])

    fo = max(0., (g - (eng.duration - 1.3)) / 1.3)
    if fo > 0:
        img = Image.blend(img, Image.new('RGB', img.size, R['ink']), min(1., fo * .85))
    return img


# ---------------------------------------------------------------- entry point
def ui(eng, img, shot, T, u, g):
    """the whole interface for one frame, in aplats. Called only when the episode asked for `"art": "aplat"`."""
    pal = palette_of(eng, shot)
    R = roles(pal)
    S = min(eng.W, eng.H) / 1080.0
    ui_ = shot.get('ui', {}) or {}
    if ui_.get('endcard'):
        return endcard(eng, img, ui_['endcard'] if isinstance(ui_['endcard'], dict) else {}, g, R, S)
    if ui_.get('hud', True) and eng.hud.get('show', True):
        hud(eng, img, ui_, g, R, S)
    if ui_.get('rule'):
        eng.sb_rule_overlay(img, ui_['rule'], T, u)
    if ui_.get('choice'):
        choice(eng, img, ui_['choice'], g, R, S)
    if ui_.get('timer'):
        k0, k1 = eng.tl.spans[eng.tl.at(g)[0]]
        timer(eng, img, max(0., k1 - g), g, R, S)
    if ui_.get('subs', 'mid') != 'off':
        s = active_sub(eng.subs, g)
        if s:
            subtitle(eng, img, s, ui_, R, S, shot)
    return img
