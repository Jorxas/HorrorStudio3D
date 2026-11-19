"""CONSOLE 2D — expressivity of the flat faces (opt-in, nothing changes by default).

The console look stays flat: aplats, clean silhouettes, no gradient on the face, no voxel. A face is
built from a handful of filled shapes — eye white, iris, pupil, catchlight, eyelids (plain skin laid
back over the eye), lash line, tapered eyebrows, a soft nose plane, a parametric mouth — plus tears,
sweat, blush and gritted teeth when the expression calls for them.

Everything is procedural and deterministic: the same (expression, seed, t) always gives the same
face, so renders stay reproducible and the regression fingerprints keep their meaning.

How to turn it on (default is the historical flat face, bit for bit):
  episode          "faces": "expressive"
  one shot/scene   {"type": "face", "faces": "expressive", ...}
  one character    library/characters/<id>.json -> "look": {"faces": "expressive"}
  back off again   "faces": "flat" at the more precise level

Reusable parameters, per identity (library/characters/<id>.json -> "personality"):
  expressive 0..1   amplitude of the expressions (Léa .85 emotes more than Mamie .6)
  energy     0..1   speed of the micro-movements (blinks, saccades, brow drift)
  shy        0..1   the gaze slips away and down, the brows stay lower
Per look: "iris" and "lip" colours, "lashes": true, "brow_color".
"""
import math

# ---------------------------------------------------------------- colours
def mix(c1, c2, k):
    return tuple(int(a + (b - a) * k) for a, b in zip(c1, c2))

def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)

def clamp(x, a=0., b=1.):
    return a if x < a else (b if x > b else x)

# ---------------------------------------------------------------- deterministic noise
def _h(*a):
    """stable hash of a few numbers -> 0..1 (no RNG object, no global state)"""
    x = 0x9E3779B9
    for v in a:
        x = (x ^ (int(v * 1024) & 0xffffffff)) * 1664525 + 1013904223
        x &= 0xffffffff
        x ^= x >> 15
    return (x & 0xffffff) / 0xffffff

def _vnoise(seed, t, rate=1., k=0):
    """value noise in -.5 .. .5, smooth, deterministic"""
    x = t * rate
    i = math.floor(x)
    f = x - i
    f = f * f * (3 - 2 * f)
    a = _h(seed, i, k)
    b = _h(seed, i + 1, k)
    return a + (b - a) * f - .5

def _saccade(seed, t, rate=.75):
    """the eye jumps to a new fixation then holds it (what a still eye really does)"""
    x = t * rate
    i = math.floor(x)
    f = x - i
    k = clamp(f / .10)
    k = k * k * (3 - 2 * k)
    ax, ay = _h(seed, i, 7) - .5, _h(seed, i, 11) - .5
    bx, by = _h(seed, i + 1, 7) - .5, _h(seed, i + 1, 11) - .5
    return ax + (bx - ax) * k, ay + (by - ay) * k

def blink_amount(seed, t, rate=1., slow=1.):
    """0 open .. 1 closed — fast close, short hold, slower opening, and the odd double blink"""
    period = 3.4 / max(.2, rate)
    cyc = t / period + seed * 7.13
    i = math.floor(cyc)
    x = (cyc - i) * period                      # seconds since this cycle started
    x -= _h(seed, i, 23) * period * .55         # the blink does not land on a metronome
    close, hold, opening = .065 * slow, .035 * slow, .125 * slow
    def pulse(s):
        y = x - s
        if y < 0 or y > close + hold + opening: return 0.
        if y < close: return y / close
        if y < close + hold: return 1.
        return 1 - (y - close - hold) / opening
    a = pulse(0.)
    if _h(seed, i, 31) > .80: a = max(a, pulse(.30 * slow))        # double blink
    return clamp(a)

# ---------------------------------------------------------------- expression table
# brow_in  > 0 : the inner end comes down (anger)      < 0 : it rises (worry, sadness)
# brow_out > 0 : the outer end comes down (sadness, fatigue)
# brow_y   > 0 : both brows sit lower                  < 0 : they rise
# lid 0..1 : upper eyelid closure (negative = lid pulled up, white above the iris)
# lid_low 0..1 : lower lid pushed up (squint of a true smile, mistrust)
_DEF = dict(eye_w=1., eye_h=1., lid=.07, lid_low=0., eye_arc=0., pupil=1., iris=1.,
            brow_y=0., brow_in=0., brow_out=0., brow_w=1., brow_th=1., brow_asym=0.,
            mouth='line', mouth_w=1., mouth_h=1., mouth_y=0., mouth_open=0., mouth_tilt=0.,
            teeth=0., tear=0., sweat=0., blush=0., tense=0., bags=0.,
            blink_rate=1., blink_slow=1., gaze_amt=1., gaze_bias=(0., 0.), breath=1.)

EXPRESSIONS = {
    'neutral':    {},
    'calm':       dict(lid=.17, brow_y=.04, mouth='smile', mouth_w=.75, mouth_h=.40),
    'tired':      dict(lid=.46, lid_low=.08, eye_h=.95, brow_in=-.10, brow_out=.18, brow_y=.15,
                       mouth='line', mouth_w=.85, mouth_y=.04, mouth_tilt=-.18, blink_rate=1.9,
                       blink_slow=1.7, bags=1., gaze_amt=.7),
    'bored':      dict(lid=.40, brow_out=.12, brow_y=.10, mouth='line', mouth_w=.80, mouth_tilt=-.35,
                       blink_rate=1.4, blink_slow=1.3, gaze_amt=1.2, gaze_bias=(.5, .25)),
    'sleeping':   dict(lid=1., brow_y=.08, mouth='line', mouth_w=.55, mouth_tilt=-.1, breath=2.2),
    'closed':     dict(lid=1., brow_y=.04, mouth='line', mouth_w=.75),
    'sad':        dict(lid=.24, eye_h=.98, brow_in=-.32, brow_out=.14, mouth='frown', mouth_w=.85,
                       mouth_h=.80, bags=.5),
    'crying':     dict(lid=.32, eye_h=.92, brow_in=-.36, brow_out=.16, mouth='open', mouth_open=.55,
                       mouth_w=.90, tear=1., bags=.6, blink_rate=1.6),
    'smile_sad':  dict(lid=.27, brow_in=-.24, brow_out=.10, mouth='smile', mouth_w=.80, mouth_h=.38,
                       mouth_tilt=-.16, bags=.4),
    'happy':      dict(lid=.08, lid_low=.30, brow_y=-.07, mouth='smile', mouth_w=1.10, mouth_h=.90,
                       blush=.30),
    'smile':      dict(lid=.10, lid_low=.22, brow_y=-.04, mouth='smile', mouth_w=1.0, mouth_h=.70),
    'joy':        dict(eye_arc=1., lid_low=.55, brow_y=-.13, mouth='grin', teeth=1., mouth_w=1.20,
                       mouth_h=1.10, blush=.55),
    'laugh':      dict(eye_arc=1., lid_low=.55, brow_y=-.13, mouth='open', mouth_open=.85, teeth=1.,
                       mouth_w=1.10, mouth_h=1.10, blush=.55),
    'excited':    dict(eye_w=1.12, eye_h=1.18, brow_y=-.18, mouth='grin', teeth=.75, mouth_w=1.15,
                       mouth_h=1.0, blush=.35, blink_rate=1.3),
    'proud':      dict(lid=.19, lid_low=.22, brow_y=-.09, mouth='smile', mouth_w=.90, mouth_h=.60),
    'cool':       dict(lid=.32, lid_low=.10, brow_y=-.05, mouth='smirk', mouth_w=.90, mouth_tilt=.55),
    'smirk':      dict(lid=.24, lid_low=.16, brow_asym=.55, brow_in=.06, mouth='smirk', mouth_w=.85,
                       mouth_tilt=.65),
    'grin':       dict(lid=.08, lid_low=.34, mouth='grin', teeth=1., mouth_w=1.15, mouth_h=1.0),
    'determined': dict(lid=.13, lid_low=.20, brow_in=.28, brow_y=.12, brow_th=1.15, mouth='line',
                       mouth_w=.95, tense=.40, blink_rate=.7),
    'angry':      dict(lid=.05, lid_low=.24, brow_in=.44, brow_y=.17, brow_th=1.28, pupil=.80,
                       mouth='frown', mouth_w=.90, mouth_h=.70, teeth=.45, tense=.75, blink_rate=.6),
    'scared':     dict(eye_w=1.24, eye_h=1.34, lid=-.07, brow_in=-.30, brow_y=-.14, pupil=.72,
                       mouth='o', mouth_open=.50, mouth_w=.75, sweat=.60, tense=.50, blink_rate=.55,
                       gaze_amt=1.25),
    'nervous':    dict(eye_w=1.08, eye_h=1.12, brow_in=-.22, brow_y=-.10, mouth='wavy', mouth_w=.90,
                       sweat=.40, gaze_amt=1.40, blink_rate=1.6),
    'shocked':    dict(eye_w=1.34, eye_h=1.44, lid=-.11, brow_y=-.22, pupil=.60, mouth='o',
                       mouth_open=.78, mouth_w=.85, blink_rate=.4),
    'surprised':  dict(eye_w=1.24, eye_h=1.30, lid=-.05, brow_y=-.22, pupil=.80, mouth='o',
                       mouth_open=.55, mouth_w=.80),
    'wide':       dict(eye_w=1.28, eye_h=1.38, lid=-.08, brow_y=-.20, pupil=.70, mouth='o',
                       mouth_open=.58, mouth_w=.78, blink_rate=.5),
    'urgent':     dict(eye_w=1.14, eye_h=1.20, brow_in=.12, brow_y=-.12, mouth='open', mouth_open=.60,
                       mouth_w=1.0, tense=.60, teeth=.3),
    'thinking':   dict(lid=.26, lid_low=.12, brow_asym=.70, brow_in=.14, brow_y=.03, mouth='line',
                       mouth_w=.70, mouth_tilt=.30, gaze_bias=(.55, -.55), gaze_amt=.8),
    'suspicious': dict(lid=.36, lid_low=.28, brow_in=.20, brow_asym=.85, brow_y=.14, mouth='line',
                       mouth_w=.72, mouth_tilt=-.22, gaze_bias=(.35, 0.), blink_rate=.7),
    'confused':   dict(lid=.12, brow_asym=1., brow_in=-.14, mouth='wavy', mouth_w=.80, mouth_tilt=.28,
                       gaze_bias=(.3, -.3)),
}
ALIAS = {'tense': 'nervous', 'worried': 'nervous', 'afraid': 'scared', 'panic': 'shocked',
         'sleep': 'sleeping', 'asleep': 'sleeping', 'serious': 'determined', 'mad': 'angry',
         'surprise': 'surprised', 'sorry': 'smile_sad', 'shy': 'smile_sad'}


def known(expr):
    e = ALIAS.get(expr, expr)
    return e in EXPRESSIONS


# ---------------------------------------------------------------- parameters at time t
def face_params(expr='neutral', t=0., seed=0., talking=False, blink=None, gaze=(0., 0.),
                persona=None, intensity=1.):
    """resolved face parameters at time t: expression + identity + micro-movements

    expr      name of the expression (unknown names fall back on 'neutral')
    seed      per character, keeps two people from blinking together
    blink     None -> the module drives its own smooth blink; a float forces the closure
    gaze      (-1..1, -1..1) where the eyes are pointing, right/down positive
    persona   {"expressive", "energy", "shy"} from the character library
    """
    base = EXPRESSIONS.get(ALIAS.get(expr, expr), EXPRESSIONS['neutral'])
    p = dict(_DEF)
    pers = persona or {}
    amp = clamp(float(pers.get('expressive', .6)) * 1.25 + .25, .25, 1.6) * max(0., intensity)
    energy = clamp(float(pers.get('energy', .5)), 0., 1.)
    shy = clamp(float(pers.get('shy', 0.)), 0., 1.)
    # expression blended towards neutral by the character's own expressiveness
    for k, v in base.items():
        if k in ('mouth', 'gaze_bias'):
            p[k] = v
        elif k in ('blink_rate', 'blink_slow', 'gaze_amt', 'breath', 'eye_w', 'eye_h', 'brow_w',
                   'brow_th', 'pupil', 'iris', 'mouth_w', 'mouth_h'):
            p[k] = 1. + (v - 1.) * amp                       # multipliers blend towards 1
        else:
            p[k] = v * amp
    p['expr'] = ALIAS.get(expr, expr)

    spd = .75 + .55 * energy
    # ---- blink
    if blink is None:
        p['blink'] = blink_amount(seed, t, p['blink_rate'] * spd, p['blink_slow'])
    else:
        p['blink'] = clamp(float(blink))
    p['lid'] = clamp(p['lid'] + (1. - p['lid']) * p['blink'], -.2, 1.)
    # ---- gaze: aim + saccades + the shy look away
    sx, sy = _saccade(seed, t, .55 + .7 * energy)
    gx = clamp(gaze[0] * p['gaze_amt'] + p['gaze_bias'][0] * amp + sx * .22 - shy * .20, -1.1, 1.1)
    gy = clamp(gaze[1] * p['gaze_amt'] + p['gaze_bias'][1] * amp + sy * .16 + shy * .16, -1.1, 1.1)
    p['gaze'] = (gx, gy)
    # ---- micro-movements: the brows drift, the pupils breathe, the chest lifts the head
    p['brow_y'] += _vnoise(seed, t, .55 * spd, 1) * .045 * amp
    p['brow_in'] += _vnoise(seed, t, .40 * spd, 2) * .035 * amp
    p['pupil'] *= 1. + _vnoise(seed, t, .33 * spd, 3) * .06
    p['breath_y'] = math.sin(t * (1.05 + .5 * energy) / max(.3, p['breath']) + seed * 5.1) * .018 * p['breath']
    p['sway'] = _vnoise(seed, t, .22 * spd, 4) * .030
    p['tear_phase'] = (t * .55 + seed) % 1.                   # the tears roll, they do not hang
    if p['tense']:
        p['sway'] += math.sin(t * 13.7 + seed) * .004 * p['tense']       # the held breath trembles
    # ---- speech
    p['talk'] = 0.
    p['talk_w'] = 1.
    if talking:
        o, w = _viseme(seed, t, 6.4 + 1.6 * energy)
        p['talk'] = o
        p['talk_w'] = w
        p['brow_y'] -= .035 * amp * o                         # the brows mark the accents
    return p


def _viseme(seed, t, rate=6.5):
    """mouth opening 0..1 and width 0..1.4 of a speaking mouth: syllables, closures, phrasing"""
    x = t * rate
    i = math.floor(x)
    f = x - i
    f = f * f * (3 - 2 * f)
    a, b = _h(seed, i, 3), _h(seed, i + 1, 3)
    aw, bw = _h(seed, i, 5), _h(seed, i + 1, 5)
    o = a + (b - a) * f
    w = aw + (bw - aw) * f
    o = o * o                                                  # consonants close more than vowels
    env = .45 + .55 * clamp(.5 + .9 * math.sin(2 * math.pi * (t * .55 + seed * 3.1)))
    return clamp(o * env * 1.6), .65 + .7 * w


# ---------------------------------------------------------------- drawing
def draw_face(d, cx, cy, r, p, skin, hair, lip=None, iris=None, dark=(22, 20, 32),
              white=(242, 242, 248), sep=.38, eye_y=0., mouth_y=.52, nose=True, socket=True,
              lashes=True, brow_color=None, brow_top=-.42):
    """one expressive flat face. r = half-width of the head; cx, cy = its centre.

    Everything is painted in aplats on top of the already drawn skin: the eyelids are simply the
    skin put back over the eye, which keeps the silhouette crisp at any size."""
    lip = tuple(lip) if lip else mix(shade(skin, .55), (120, 44, 56), .5)
    iris = tuple(iris) if iris else mix(hair, (40, 54, 92), .45)
    brow = tuple(brow_color) if brow_color else shade(hair, .92)
    gx, gy = p['gaze']
    ew = r * .19 * p['eye_w']
    eh = r * .165 * p['eye_h']
    ey = cy + r * eye_y
    lid = p['lid']
    th = max(1, int(r * .045))

    # ---- eyes
    for s in (-1, 1):
        x = cx + s * r * sep
        if p['eye_arc'] > .5 and lid < .9:                      # happy eyes: two arcs, nothing else
            d.arc([x - ew * 1.05, ey - eh * .55, x + ew * 1.05, ey + eh * 1.75], 185, 355,
                  fill=dark, width=max(2, int(r * .055)))
            continue
        if lid >= .985:                                         # closed: one calm line
            d.line([x - ew * .92, ey, x + ew * .92, ey], fill=dark, width=th)
            continue
        if socket:
            d.ellipse([x - ew * 1.16, ey - eh * 1.22, x + ew * 1.16, ey + eh * 1.22],
                      fill=shade(skin, .958))
        d.ellipse([x - ew, ey - eh, x + ew, ey + eh], fill=white)
        pr = eh * .62 * clamp(p['iris'], .4, 1.6)
        px = x + gx * (ew - pr * .80)
        py = ey + gy * (eh - pr * .70)
        d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=iris)
        qr = pr * .52 * clamp(p['pupil'], .35, 1.8)
        d.ellipse([px - qr, py - qr, px + qr, py + qr], fill=dark)
        cl = pr * .30
        d.ellipse([px - pr * .42 - cl, py - pr * .42 - cl, px - pr * .42 + cl, py - pr * .42 + cl],
                  fill=white)
        # eyelids = the skin laid back over the eye (flat, no clipping needed)
        if lid > .005:
            ly = ey - eh + 2 * eh * lid
            d.rectangle([x - ew * 1.3, ey - eh * 1.45, x + ew * 1.3, ly], fill=skin)
            if lashes: d.line([x - ew * .98, ly, x + ew * .98, ly], fill=dark, width=th)
        elif lid < -.02:                                        # lid pulled up: white above the iris
            d.line([x - ew * .9, ey - eh * (1 + lid * 2), x + ew * .9, ey - eh * (1 + lid * 2)],
                   fill=shade(skin, .88), width=max(1, th // 2))
        if p['lid_low'] > .01:
            ly = ey + eh - 2 * eh * min(.42, p['lid_low'])
            d.rectangle([x - ew * 1.3, ly, x + ew * 1.3, ey + eh * 1.45], fill=skin)
            if lashes: d.line([x - ew * .9, ly, x + ew * .9, ly], fill=shade(skin, .80),
                              width=max(1, th // 2))
        if p['bags'] > .05:                                     # the shadow of a short night
            d.arc([x - ew * 1.05, ey - eh * .2, x + ew * 1.05, ey + eh * 2.0], 20, 160,
                  fill=shade(skin, .86), width=max(1, int(r * .022 * (1 + p['bags']))))

    # ---- eyebrows: they act, but they never climb into the hair nor fall into the eye
    bw_ = r * .21 * p['brow_w']
    bth = max(2, int(r * .052 * p['brow_th']))
    hi = cy + r * brow_top + bth * .5                            # just under the hairline
    lo = ey - eh - r * .055                                      # just over the upper lid
    lo_in = ey - eh * .42                                        # the inner end may frown onto the eye
    if lo < hi: hi = lo - r * .02
    for s in (-1, 1):
        x = cx + s * r * sep
        asym = 1. + (p['brow_asym'] * .45 if s > 0 else -p['brow_asym'] * .25)
        by = ey - eh * .55 - r * (.26 - p['brow_y'] * asym * .70)
        yi = by + r * p['brow_in'] * asym * .55                  # inner end
        yo = by + r * p['brow_out'] * asym * .55                 # outer end
        dn = max(0., yi - lo_in, yo - lo)                        # slide the pair, keep the angle
        yi -= dn; yo -= dn
        up = max(0., hi - min(yi, yo))
        yi += up; yo += up
        yi = min(lo_in, yi); yo = min(lo, yo)
        xi, xo = x - s * bw_ * .95, x + s * bw_
        d.line([xi, yi, xo, yo], fill=brow, width=bth)
        for (bx, byy) in ((xi, yi), (xo, yo)):
            d.ellipse([bx - bth * .5, byy - bth * .5, bx + bth * .5, byy + bth * .5], fill=brow)

    # ---- nose: one soft plane, enough to hold the face together without breaking the aplats
    if nose:
        nx = cx + gx * r * .025
        ny = cy + r * .25
        d.polygon([(nx - r * .050, ny + r * .045), (nx + r * .050, ny + r * .045),
                   (nx + r * .012, ny - r * .060)], fill=shade(skin, .925))

    # ---- mouth
    _mouth(d, cx, cy + r * mouth_y, r, p, lip, dark, skin)

    # ---- the extras that sell the emotion
    if p['tear'] > .05:
        for s in (-1, 1):
            k = (p.get('tear_phase', 0.) + (.5 if s > 0 else 0.)) % 1.
            tx = cx + s * r * (sep + .15)
            ty = ey + eh * .6 + r * .60 * k
            tw = r * .045 * p['tear'] * (1 - .35 * k)
            d.ellipse([tx - tw, ty - tw * 1.5, tx + tw, ty + tw * 1.5], fill=(150, 205, 255))
    if p['sweat'] > .05:
        sx_ = cx + r * .72
        sy_ = cy - r * .40
        sw = r * .055 * p['sweat']
        d.polygon([(sx_, sy_ - sw * 2.1), (sx_ + sw, sy_ + sw * .5), (sx_ - sw, sy_ + sw * .5)],
                  fill=(176, 220, 255))
        d.ellipse([sx_ - sw, sy_ - sw * .3, sx_ + sw, sy_ + sw * 1.4], fill=(176, 220, 255))
    if p['blush'] > .05:
        for s in (-1, 1):
            bx = cx + s * r * .66
            d.ellipse([bx - r * .16, cy + r * .20, bx + r * .16, cy + r * .33],
                      fill=mix(skin, (236, 110, 110), .45 * p['blush']))


def _mouth(d, cx, my, r, p, lip, dark, skin):
    kind = p['mouth']
    mw = r * .22 * p['mouth_w']
    tilt = p['mouth_tilt'] * r * .07
    my += r * p['mouth_y']
    lw = max(2, int(r * .050))
    talk = p['talk']
    if talk > .02:                                               # speaking: the shape follows the voice
        w = mw * (.54 + .40 * p['talk_w'])
        h = r * .042 + r * .125 * talk * max(.6, p['mouth_h'])
        d.ellipse([cx - w, my - h * .45, cx + w, my + h * 1.05], fill=shade(lip, .45))
        if p['teeth'] > .2 and talk > .3:
            d.rectangle([cx - w * .78, my - h * .35, cx + w * .78, my - h * .35 + h * .30],
                        fill=(238, 238, 236))
        d.line([cx - w * .52, my + h * 1.06, cx + w * .52, my + h * 1.06],
               fill=shade(skin, .91), width=max(1, lw // 2))
        return
    if p['mouth_open'] > .02 or kind == 'o':
        o = max(.18, p['mouth_open'])
        w = mw * (.46 if kind == 'o' else .78)
        h = r * .155 * o * max(.6, p['mouth_h'])
        d.ellipse([cx - w, my - h, cx + w, my + h], fill=shade(lip, .45))
        if p['teeth'] > .2:
            d.rectangle([cx - w * .78, my - h * .82, cx + w * .78, my - h * .82 + h * .42],
                        fill=(238, 238, 236))
        return
    if kind == 'smile':
        h = r * .17 * p['mouth_h']
        d.arc([cx - mw, my - h, cx + mw, my + h], 20, 160, fill=lip, width=lw)
        d.line([cx - mw * .98, my + h * .18 + tilt, cx - mw * .80, my - h * .12 + tilt],
               fill=lip, width=max(1, lw - 1))
        d.line([cx + mw * .98, my + h * .18 - tilt, cx + mw * .80, my - h * .12 - tilt],
               fill=lip, width=max(1, lw - 1))
        return
    if kind == 'grin':
        h = r * .14 * p['mouth_h']
        d.chord([cx - mw, my - h, cx + mw, my + h * 2.4], 0, 180, fill=shade(lip, .45))
        if p['teeth'] > .2:
            d.rectangle([cx - mw * .86, my + h * .02, cx + mw * .86, my + h * .60],
                        fill=(238, 238, 236))
        return
    if kind == 'frown':
        h = r * .17 * p['mouth_h']
        d.arc([cx - mw, my, cx + mw, my + h * 1.6], 200, 340, fill=lip, width=lw)
        return
    if kind == 'smirk':                                          # one corner clearly higher than the other
        up = tilt * 2.4
        d.line([cx - mw, my + up * .40, cx + mw * .50, my + up * .10], fill=lip, width=lw)
        d.line([cx + mw * .50, my + up * .10, cx + mw * .98, my - up], fill=lip, width=lw)
        d.line([cx + mw * .98, my - up, cx + mw * .86, my - up * 1.35], fill=lip, width=max(1, lw - 1))
        return
    if kind == 'wavy':
        n = 4
        pts = [(cx - mw + 2 * mw * i / n, my + (r * .035 if i % 2 else -r * .035)) for i in range(n + 1)]
        d.line(pts, fill=lip, width=max(1, lw - 1), joint='curve')
        return
    d.line([cx - mw * .72, my + tilt, cx + mw * .72, my - tilt], fill=lip, width=lw)
    if p['tense'] > .3:                                          # jaw clenched: the lips go pale
        d.line([cx - mw * .60, my - r * .035, cx + mw * .60, my - r * .035],
               fill=shade(skin, .88), width=max(1, lw // 2))
