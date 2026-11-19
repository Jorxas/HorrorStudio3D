"""CONSOLE 2D "aplats" characters (V3, opt-in): the same shared skeleton, drawn as a flat 2D illustration.

Nothing here replaces `flat.py`: the legacy figures keep rendering the legacy episodes untouched. This module is
only reached when an episode asks for `"art": "aplat"`.

What the drawing does differently from `flat.draw_figure`:
- ink contour on every shape, at a weight proportional to the figure (the main "this is a drawing" signal);
- two tones per surface, split along the key light: limbs get a shadow stripe, the head a `pieslice` shadow whose
  flat chord is the terminator, and the lit edge gets a rim stroke so the silhouette separates from the set;
- a built silhouette: wider shoulder taper, mitt hands, chunky shoes, a bigger head, hair as one flat shape;
- expressions from a real table (`EXPR`): eye shape, brow tilt and height, mouth shape, pupil direction, built
  large enough to read at thumbnail size;
- motion reads that cost nothing: hair lag against the walk direction, and a flat contact shadow that shrinks
  when the character leaves the ground.

The expression names are the ones the rest of the studio already uses (acting layer, pixel3d faces), so a shot
written for PIXEL 3D plays here without being rewritten.
"""
import math
from ...acting import rig
from .aplat import shade, mix, disc, quad, rbox, box, shadow_of, rim_arc

# ---------------------------------------------------------------- expressions
# eye:    open | wide | squint | closed | arc | half
# mouth:  line | o_small | o_wide | smile | grin | frown | grimace
# brow:   + = inner end raised (worry, fear, sadness), - = inner end lowered (anger, suspicion, resolve)
# brow_h: + = the whole brow sits higher on the forehead (openness, surprise)
EXPR = {
    'neutral':    dict(eye='open',   brow=0.00, brow_h=0.00, mouth='line'),
    'tired':      dict(eye='half',   brow=0.05, brow_h=-0.05, mouth='line'),
    'sleeping':   dict(eye='closed', brow=0.00, brow_h=-0.02, mouth='o_small'),
    'closed':     dict(eye='closed', brow=0.00, brow_h=0.00, mouth='line'),
    'scared':     dict(eye='wide',   brow=0.16, brow_h=0.10, mouth='o_wide'),
    'shocked':    dict(eye='wide',   brow=0.18, brow_h=0.12, mouth='o_wide'),
    'surprised':  dict(eye='wide',   brow=0.12, brow_h=0.10, mouth='o_small'),
    'nervous':    dict(eye='wide',   brow=0.12, brow_h=0.04, mouth='grimace'),
    'suspicious': dict(eye='squint', brow=-0.10, brow_h=-0.05, mouth='line'),
    'angry':      dict(eye='squint', brow=-0.20, brow_h=-0.08, mouth='grimace'),
    'determined': dict(eye='squint', brow=-0.14, brow_h=-0.04, mouth='line'),
    'sad':        dict(eye='half',   brow=0.18, brow_h=0.02, mouth='frown'),
    'crying':     dict(eye='half',   brow=0.20, brow_h=0.04, mouth='frown'),
    'smile_sad':  dict(eye='half',   brow=0.12, brow_h=0.00, mouth='smile'),
    'smile':      dict(eye='open',   brow=0.00, brow_h=0.02, mouth='smile'),
    'happy':      dict(eye='arc',    brow=0.00, brow_h=0.04, mouth='smile'),
    'joy':        dict(eye='arc',    brow=0.00, brow_h=0.06, mouth='grin'),
    'laugh':      dict(eye='arc',    brow=0.00, brow_h=0.06, mouth='grin'),
    'excited':    dict(eye='wide',   brow=0.02, brow_h=0.08, mouth='grin'),
    'proud':      dict(eye='open',   brow=-0.05, brow_h=0.02, mouth='smile'),
}

def expr_of(name):
    return EXPR.get(name or 'neutral', EXPR['neutral'])

def full_look(look):
    """the look of a library character with its preset expanded (same identity as the other engine)"""
    pre = look.get('preset') or look.get('kind')
    if pre:
        try:
            from ..pixel3d.creatures import PRESETS
            if pre in PRESETS:
                return dict(PRESETS[pre], **{k: v for k, v in look.items() if k not in ('kind', 'preset')})
        except Exception:
            pass
    return look

# ---------------------------------------------------------------- the figure
def draw_figure(d, stage, sample, look, t, pal, light=(-0.42, 0.91)):
    """one character of the shared acting layer, in the aplats style"""
    look = full_look(look)
    sk = rig.solve(sample['rig'])
    h = sample['heading']
    c, s_ = math.cos(h), math.sin(h)
    X, Z = sample['x'], sample['z']
    Y = float(sample.get('y', 0.))
    J = sk.joints

    def W(p):
        wx = X + p[0] * c + p[2] * s_
        wz = Z - p[0] * s_ + p[2] * c
        return stage.to_px(wx, float(p[1]) + Y, wz)

    def depth(p):
        return Z - p[0] * s_ + p[2] * c

    P = {k: W(v) for k, v in J.items()}
    sc = P['pelvis'][2]                                   # pixels per metre at this character's depth
    ink = pal['ink']
    iw = max(2, int(0.019 * sc))                          # the ink weight, proportional to the figure
    lx, ly = light
    ln = math.hypot(lx, ly) or 1.0
    lx, ly = lx / ln, ly / ln
    lang = math.degrees(math.atan2(ly, lx))               # canvas angle towards the key light

    # colours of the look, kept flat (no tinting towards the night: the palette already carries the mood)
    skin = tuple(look.get('skin', pal['skin']))
    skin_s = mix(skin, pal['shadow'], 0.42)
    skin_r = mix(skin, pal['light'], 0.18)
    hood = tuple(look.get('hood', pal['furn_l']))
    hood_s = mix(hood, pal['shadow'], 0.46)
    hood_r = mix(hood, pal['light'], 0.22)
    jeans = tuple(look.get('jeans', pal['furn_d']))
    jeans_s = mix(jeans, pal['shadow'], 0.46)
    hair = tuple(look.get('hair', (26, 24, 44)))
    hair_r = mix(hair, pal['light'], 0.26)
    outfit = look.get('outfit', 'hoodie')
    style = look.get('hair_style') or ('long' if look.get('hair_long') else 'short')
    if outfit == 'dress':
        jeans = skin
        jeans_s = skin_s

    front = c                                             # 1 facing the viewer, -1 back turned, 0 profile
    gait = float(sample['rig'].get('gait', 0.) or 0.)

    # ---- contact shadow (flat, shrinks when the character is off the ground)
    fx_px, fy_px, _ = stage.to_px(X, 0., Z)
    air = max(0.0, min(1.0, Y / 0.9))
    sw = sc * 0.34 * (1 - 0.55 * air)
    sh_ = sc * 0.085 * (1 - 0.55 * air)
    d.ellipse([fx_px - sw, fy_px - sh_, fx_px + sw, fy_px + sh_], fill=pal['shadow'])

    fore = skin if outfit in ('tshirt', 'dress') else hood
    fore_s = skin_s if outfit in ('tshirt', 'dress') else hood_s

    def limb(a, b, w, col, col_s):
        """an inked limb in two tones: ink underneath, flat fill, then a shadow stripe away from the light"""
        (x0, y0, _), (x1, y1, _) = P[a], P[b]
        ww = max(3, int(w * sc))
        for width, c in ((ww + iw * 2, ink), (ww, col)):
            d.line([x0, y0, x1, y1], fill=c, width=width, joint='curve')
            for (x, y) in ((x0, y0), (x1, y1)):
                r_ = width / 2
                d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=c)
        off = ww * 0.28
        d.line([x0 - lx * off, y0 - ly * off, x1 - lx * off, y1 - ly * off],
               fill=col_s, width=max(2, int(ww * 0.40)), joint='curve')

    def arm(tag, k):
        limb('sh' + tag, 'el' + tag, 0.105, shade(hood, k), shade(hood_s, k))
        limb('el' + tag, 'ha' + tag, 0.095, shade(fore, k), shade(fore_s, k))
        hx_, hy_, _ = P['ha' + tag]
        disc(d, hx_, hy_, 0.082 * sc, shade(skin, k), ink, iw)        # a mitt: one solid shape, no fingers

    def leg(tag, k):
        limb('hip' + tag, 'kn' + tag, 0.160, shade(jeans, k), shade(jeans_s, k))
        limb('kn' + tag, 'an' + tag, 0.138, shade(jeans, k), shade(jeans_s, k))
        ax, ay, _ = P['an' + tag]
        fw = 0.145 * sc
        toe = 0.09 * sc * s_
        rbox(d, ax - fw, ay - 0.045 * sc, ax + fw + toe, ay + 0.05 * sc, 0.035 * sc,
             shade((26, 26, 38), k), ink, iw)

    far = 'L' if depth(J['shL']) < depth(J['shR']) else 'R'
    near = 'R' if far == 'L' else 'L'
    # Draw order matters more than anything else here: the far arm goes behind the torso and the near arm in
    # front of it. Drawn in one pass (as the legacy figure does) a flat rig reads as a cut-out with both arms
    # pasted flat on the chest.
    arm(far, 0.80)
    leg(far, 0.84)
    leg(near, 1.0)

    # ---- hips, then the torso over them
    sh = [P['shL'], P['shR']]
    hp = [P['hipL'], P['hipR']]
    cx_s, cy_s = (sh[0][0] + sh[1][0]) / 2, (sh[0][1] + sh[1][1]) / 2
    cx_h, cy_h = (hp[0][0] + hp[1][0]) / 2, (hp[0][1] + hp[1][1]) / 2
    turn = max(0.52, abs(front) + 0.30)                   # a body turned away is narrower on screen
    wsh = 0.50 * sc * turn
    whp = 0.37 * sc * turn
    if outfit == 'dress':
        skirt = [(cx_h - whp * 0.58, cy_h - 0.02 * sc), (cx_h + whp * 0.58, cy_h - 0.02 * sc),
                 (cx_h + whp * 0.92, cy_h + 0.46 * sc), (cx_h - whp * 0.92, cy_h + 0.46 * sc)]
        d.polygon(skirt, fill=hood)
        d.polygon(shadow_of(skirt, light), fill=hood_s)
        d.line([tuple(p) for p in skirt] + [tuple(skirt[0])], fill=ink, width=iw, joint='curve')
    else:
        rbox(d, cx_h - whp * 0.56, cy_h - 0.03 * sc, cx_h + whp * 0.56, cy_h + 0.15 * sc, 0.05 * sc, jeans, ink, iw)

    # the torso is a built shape, not a slab: sloped shoulders, a waist, one straight terminator
    torso = [(cx_s - wsh * 0.50, cy_s + 0.05 * sc),
             (cx_s - wsh * 0.33, cy_s - 0.07 * sc),
             (cx_s + wsh * 0.33, cy_s - 0.07 * sc),
             (cx_s + wsh * 0.50, cy_s + 0.05 * sc),
             (cx_h + whp * 0.54, cy_h + 0.08 * sc),
             (cx_h - whp * 0.54, cy_h + 0.08 * sc)]
    d.polygon(torso, fill=hood)
    d.polygon(shadow_of(torso, light), fill=hood_s)
    d.line([tuple(p) for p in torso] + [tuple(torso[0])], fill=ink, width=iw, joint='curve')
    # rim stroke down the lit edge: this is what lifts the silhouette off the set
    rim = (torso[0], torso[5]) if lx < 0 else (torso[3], torso[4])
    d.line(list(rim), fill=hood_r, width=max(2, iw))
    if front > 0.3 and look.get('tie'):
        quad(d, [(cx_s, cy_s + 0.02 * sc), (cx_s - 0.035 * sc, cy_s + 0.22 * sc),
                 (cx_s, cy_s + 0.28 * sc), (cx_s + 0.035 * sc, cy_s + 0.22 * sc)],
             tuple(look['tie']), ink, max(1, iw - 1))

    # ---- neck and collar: without them the head sits straight on the chest and the figure reads as a robot
    nx, ny, _ = P['neck']
    d.line([nx, ny - 0.06 * sc, nx, cy_s + 0.02 * sc], fill=skin_s, width=max(4, int(0.155 * sc)))
    if outfit == 'hoodie':
        collar = [(nx - wsh * 0.30, cy_s + 0.06 * sc), (nx - wsh * 0.21, cy_s - 0.07 * sc),
                  (nx + wsh * 0.21, cy_s - 0.07 * sc), (nx + wsh * 0.30, cy_s + 0.06 * sc)]
        d.polygon(collar, fill=hood_r)
        d.polygon(shadow_of(collar, light), fill=hood)
        d.line([tuple(p) for p in collar] + [tuple(collar[0])], fill=ink, width=iw, joint='curve')
        if front > 0.3:                                   # the drawstrings, short, as two flat ticks
            for k_ in (-1, 1):
                d.line([nx + k_ * wsh * 0.14, cy_s + 0.05 * sc, nx + k_ * wsh * 0.16, cy_s + 0.19 * sc],
                       fill=pal['moon'], width=max(2, int(0.018 * sc)))

    arm(near, 1.0)

    # ---- the handheld, if the character holds it
    if sample.get('hold') == 'console':
        hx, hy, _ = P['haR']
        w = 0.16 * sc
        rbox(d, hx - w, hy - w * 1.35, hx + w * 0.45, hy + w * 0.35, w * 0.22, (206, 206, 216), ink, iw)
        d.rectangle([hx - w * 0.78, hy - w * 1.12, hx + w * 0.22, hy - w * 0.28], fill=pal['glow'])
        d.rectangle([hx - w * 0.78, hy - w * 1.12, hx + w * 0.22, hy - w * 0.28], outline=ink, width=max(1, iw - 1))

    # ---- head
    hx, hy, _ = P['head']
    r = 0.212 * sc                                        # a bigger head than the legacy figure: more legible
    hyaw = h + float(sample['rig'].get('head', (0., 0.))[0])
    hf = math.cos(hyaw)
    lag = -math.sin(h) * gait * r * 0.16                  # the hair trails the walk

    if style == 'ponytail' and hf < 0.6:
        tx = hx - math.sin(hyaw) * r * 0.95 + lag
        rbox(d, tx - r * 0.32, hy - r * 0.2, tx + r * 0.32, hy + r * 1.15, r * 0.3, hair, ink, iw)
    if style == 'long':
        rbox(d, hx - r * 1.1 + lag, hy - r * 0.45, hx + r * 1.1 + lag, hy + r * 1.3, r * 0.42, hair, ink, iw)

    hb = [hx - r, hy - r * 1.06, hx + r, hy + r * 1.06]
    if hf > -0.35:
        d.ellipse(hb, fill=skin)
        d.pieslice(hb, lang + 92, lang + 268, fill=skin_s)        # flat shadow half, chord = terminator
        d.arc(hb, lang - 44, lang + 44, fill=skin_r, width=max(2, iw))
        d.ellipse(hb, outline=ink, width=iw)
    else:
        d.ellipse(hb, fill=hair)
        d.pieslice(hb, lang + 92, lang + 268, fill=mix(hair, pal['shadow'], 0.4))
        d.ellipse(hb, outline=ink, width=iw)

    hat = look.get('hat')
    hat_c = tuple(look.get('hat_color') or look.get('hood', pal['furn']))
    fx_ = hx + math.sin(hyaw) * r * 0.25

    if hf > -0.35:
        # hair as one flat shape with a hard highlight band
        if style != 'bald' and hat not in ('hood', 'beanie'):
            d.chord([hx - r * 1.06 + lag * 0.5, hy - r * 1.22, hx + r * 1.06 + lag * 0.5, hy + r * 0.28], 180, 360, fill=hair)
            rim_arc(d, [hx - r * 1.06 + lag * 0.5, hy - r * 1.22, hx + r * 1.06 + lag * 0.5, hy + r * 0.28],
                    lang, 52, hair_r, max(2, int(iw * 1.4)))
            d.chord([hx - r * 1.06 + lag * 0.5, hy - r * 1.22, hx + r * 1.06 + lag * 0.5, hy + r * 0.28], 180, 360,
                    outline=ink, width=iw)
            if style == 'curly':
                for k_ in range(-2, 3):
                    disc(d, hx + k_ * r * 0.44 + lag * 0.5, hy - r * 0.98, r * 0.33, hair, ink, max(1, iw - 1))
            elif style == 'bun':
                disc(d, hx + lag, hy - r * 1.26, r * 0.36, hair, ink, iw)
            elif style == 'spiky':
                for k_ in range(-2, 3):
                    bx = hx + k_ * r * 0.42 + lag * 0.5
                    quad(d, [(bx - r * 0.24, hy - r * 0.9), (bx, hy - r * 1.46), (bx + r * 0.24, hy - r * 0.9)], hair, ink, max(1, iw - 1))
            if style in ('long', 'ponytail') and hf > 0.25:
                for s in (-1, 1):
                    d.rectangle([hx + s * r * 0.9 - r * 0.12 + lag * 0.5, hy - r * 0.25,
                                 hx + s * r * 0.9 + r * 0.12 + lag * 0.5, hy + r * (1.25 if style == 'long' else 0.55)], fill=hair)

        if hf > 0.25:
            face(d, fx_, hy, r, sample, t, pal, ink, iw, lang)
        else:
            side = 1 if math.sin(hyaw) > 0 else -1                 # profile: one eye, a nose, a mouth line
            ex = hx + side * r * 0.42
            disc(d, ex, hy + r * 0.02, r * 0.11, (22, 20, 32))
            quad(d, [(hx + side * r * 0.96, hy + r * 0.04), (hx + side * r * 1.16, hy + r * 0.2),
                     (hx + side * r * 0.94, hy + r * 0.3)], skin, ink, max(1, iw - 1))
            d.line([hx + side * r * 0.5, hy + r * 0.52, hx + side * r * 0.86, hy + r * 0.52], fill=(96, 44, 52), width=max(2, int(r * 0.07)))

        if look.get('beard') and hf > 0.25:
            bc = hair if look['beard'] != 'stubble' else mix(skin, hair, 0.45)
            if look['beard'] == 'mustache':
                d.rectangle([fx_ - r * 0.28, hy + r * 0.36, fx_ + r * 0.28, hy + r * 0.46], fill=bc)
            else:
                d.chord([fx_ - r * 0.8, hy + r * 0.02, fx_ + r * 0.8, hy + r * 1.1], 0, 180, fill=bc)
                d.chord([fx_ - r * 0.8, hy + r * 0.02, fx_ + r * 0.8, hy + r * 1.1], 0, 180, outline=ink, width=max(1, iw - 1))
        if look.get('glasses') and hf > 0.25:
            gc = (30, 28, 36)
            solid = look['glasses'] in ('sun', 'sunglasses')
            for k_ in (-1, 1):
                gx = fx_ + k_ * r * 0.4
                bx = [gx - r * 0.27, hy - r * 0.2, gx + r * 0.27, hy + r * 0.22]
                if solid:
                    d.rounded_rectangle(bx, radius=int(r * 0.08), fill=(20, 20, 26), outline=ink, width=iw)
                else:
                    d.rounded_rectangle(bx, radius=int(r * 0.08), outline=gc, width=max(2, iw))
            d.line([fx_ - r * 0.14, hy - r * 0.01, fx_ + r * 0.14, hy - r * 0.01], fill=gc, width=max(2, iw))

        if hat in ('cap', 'beanie', 'hood', 'tophat', 'crown'):
            side = 1 if math.sin(hyaw) >= 0 else -1
            if hat == 'cap':
                d.chord([hx - r * 1.08, hy - r * 1.24, hx + r * 1.08, hy + r * 0.12], 180, 360, fill=hat_c)
                d.chord([hx - r * 1.08, hy - r * 1.24, hx + r * 1.08, hy + r * 0.12], 180, 360, outline=ink, width=iw)
                quad(d, [(fx_ - r * 0.2, hy - r * 0.58), (fx_ + side * r * 1.2, hy - r * 0.54),
                         (fx_ + side * r * 1.2, hy - r * 0.4), (fx_ - r * 0.2, hy - r * 0.44)], hat_c, ink, max(1, iw - 1))
            elif hat == 'beanie':
                d.chord([hx - r * 1.1, hy - r * 1.34, hx + r * 1.1, hy + r * 0.08], 180, 360, fill=hat_c)
                d.chord([hx - r * 1.1, hy - r * 1.34, hx + r * 1.1, hy + r * 0.08], 180, 360, outline=ink, width=iw)
                d.rectangle([hx - r * 1.1, hy - r * 0.58, hx + r * 1.1, hy - r * 0.34], fill=shade(hat_c, 0.82), outline=ink, width=iw)
            elif hat == 'hood':
                d.arc([hx - r * 1.3, hy - r * 1.4, hx + r * 1.3, hy + r * 1.2], 160, 380, fill=hood, width=max(3, int(r * 0.3)))
            elif hat == 'tophat':
                box(d, hx - r * 0.66, hy - r * 1.95, hx + r * 0.66, hy - r * 0.82, hat_c, ink, iw)
                box(d, hx - r * 1.02, hy - r * 0.92, hx + r * 1.02, hy - r * 0.76, hat_c, ink, iw)
            else:
                quad(d, [(hx - r * 0.72, hy - r * 0.86), (hx - r * 0.72, hy - r * 1.38), (hx - r * 0.36, hy - r * 1.12),
                         (hx, hy - r * 1.48), (hx + r * 0.36, hy - r * 1.12), (hx + r * 0.72, hy - r * 1.38),
                         (hx + r * 0.72, hy - r * 0.86)], pal['accent'], ink, iw)

        if look.get('headphones', True) and hat not in ('hood', 'beanie'):
            d.arc([hx - r * 1.12, hy - r * 1.26, hx + r * 1.12, hy + r * 0.52], 190, 350, fill=(26, 26, 32), width=max(3, int(r * 0.15)))
            for k_ in (-1, 1):
                ex_ = hx + k_ * r * 1.02 * max(0.3, abs(math.cos(hyaw)))
                if abs(math.cos(hyaw)) > 0.3 or (k_ > 0) == (math.sin(hyaw) > 0):
                    rbox(d, ex_ - r * 0.19, hy - r * 0.28, ex_ + r * 0.19, hy + r * 0.28, r * 0.08, (34, 34, 42), ink, max(1, iw - 1))
                    disc(d, ex_, hy, r * 0.06, pal['glow'])
    else:
        # back of the head: without a rim and the headphones this is just a hole in the frame
        bb = [hx - r * 1.0, hy - r * 1.02, hx + r * 1.0, hy + r * 1.0]
        d.ellipse(bb, fill=hair)
        d.arc(bb, lang - 62, lang + 62, fill=hair_r, width=max(2, int(iw * 1.5)))
        d.ellipse(bb, outline=ink, width=iw)
        d.arc([hx - r * 0.62, hy + r * 0.1, hx + r * 0.62, hy + r * 0.95], 200, 340,
              fill=mix(hair, pal['shadow'], 0.45), width=max(2, iw))      # the nape, so the shape has a top and a bottom
        if style == 'bun':
            disc(d, hx, hy - r * 1.3, r * 0.36, hair, ink, iw)
        if style in ('long', 'ponytail'):
            rbox(d, hx - r * 0.5, hy - r * 0.2, hx + r * 0.5, hy + r * 1.15, r * 0.3, hair, ink, iw)
        if look.get('headphones', True) and hat not in ('hood', 'beanie'):
            d.arc([hx - r * 1.06, hy - r * 1.10, hx + r * 1.06, hy + r * 0.60], 185, 355, fill=(34, 34, 42), width=max(3, int(iw * 1.6)))
            for k_ in (-1, 1):
                rbox(d, hx + k_ * r * 1.02 - r * 0.19, hy - r * 0.28, hx + k_ * r * 1.02 + r * 0.19, hy + r * 0.28,
                     r * 0.08, (34, 34, 42), ink, max(1, iw - 1))


def face(d, cx, cy, r, sample, t, pal, ink, iw, lang):
    """the face in aplats: flat shapes only, built large so the expression reads in a thumbnail"""
    e = expr_of(sample.get('face'))
    eye_kind = e['eye']
    if sample.get('blink') and eye_kind not in ('closed',):
        eye_kind = 'closed'
    dark = (22, 20, 32)
    white = (242, 242, 248)
    lip = (104, 44, 54)
    look_x = 0.0
    lk = sample.get('look_x')
    if isinstance(lk, (int, float)):
        look_x = max(-1.0, min(1.0, float(lk))) * r * 0.08

    for s in (-1, 1):
        x = cx + s * r * 0.40
        y = cy + r * 0.03
        if eye_kind == 'closed':
            d.line([x - r * 0.19, y, x + r * 0.19, y], fill=dark, width=max(2, int(r * 0.085)))
        elif eye_kind == 'arc':
            d.arc([x - r * 0.2, y - r * 0.16, x + r * 0.2, y + r * 0.16], 200, 340, fill=dark, width=max(2, int(r * 0.085)))
        elif eye_kind == 'squint':
            lid = [(x - r * 0.21, y - r * 0.005), (x + r * 0.21, y - r * 0.04),
                   (x + r * 0.21, y + r * 0.055), (x - r * 0.21, y + r * 0.07)]
            d.polygon(lid, fill=white)
            d.ellipse([x - r * 0.07 + look_x, y - r * 0.035, x + r * 0.07 + look_x, y + r * 0.06], fill=dark)
            d.polygon(lid, outline=ink, width=max(1, iw - 1))
        else:
            wide = eye_kind == 'wide'
            half = eye_kind == 'half'
            w = r * (0.21 if wide else 0.17)
            hgt = r * (0.25 if wide else (0.11 if half else 0.19))
            bx = [x - w, y - hgt, x + w, y + hgt]
            d.ellipse(bx, fill=white)
            p = r * (0.085 if wide else 0.095)
            d.ellipse([x - p + look_x, y - p * 0.9, x + p + look_x, y + p * 1.1], fill=dark)
            if wide:                                      # a catch light: one hard dot, the fear read
                d.ellipse([x - p * 0.3 + look_x, y - p * 0.6, x + p * 0.1 + look_x, y - p * 0.2], fill=white)
            d.ellipse(bx, outline=ink, width=max(1, iw - 1))
        # brow: a thick tapered quad, not a line
        by = y - r * (0.40 if eye_kind == 'wide' else 0.33) - e['brow_h'] * r
        tilt = e['brow'] * s * r
        th = r * 0.075
        d.polygon([(x - r * 0.22, by - tilt), (x + r * 0.22, by + tilt),
                   (x + r * 0.22, by + tilt + th), (x - r * 0.22, by - tilt + th)], fill=dark)

    my = cy + r * 0.56
    talking = sample.get('talking') and int(t * 9) % 2 == 0
    m = 'o_small' if talking and e['mouth'] in ('line', 'frown') else e['mouth']
    if talking and e['mouth'] in ('o_wide', 'grin', 'grimace'):
        m = e['mouth']
    if m == 'o_wide':
        d.ellipse([cx - r * 0.16, my - r * 0.14, cx + r * 0.16, my + r * 0.2], fill=(62, 26, 34), outline=ink, width=max(1, iw - 1))
    elif m == 'o_small':
        d.ellipse([cx - r * 0.1, my - r * 0.08, cx + r * 0.1, my + r * 0.1], fill=(62, 26, 34))
    elif m == 'smile':
        d.arc([cx - r * 0.26, my - r * 0.22, cx + r * 0.26, my + r * 0.12], 20, 160, fill=lip, width=max(2, int(r * 0.075)))
    elif m == 'grin':
        d.chord([cx - r * 0.3, my - r * 0.2, cx + r * 0.3, my + r * 0.26], 0, 180, fill=(62, 26, 34), outline=ink, width=max(1, iw - 1))
        d.rectangle([cx - r * 0.26, my - r * 0.02, cx + r * 0.26, my + r * 0.05], fill=white)
    elif m == 'frown':
        d.arc([cx - r * 0.22, my, cx + r * 0.22, my + r * 0.28], 200, 340, fill=lip, width=max(2, int(r * 0.07)))
    elif m == 'grimace':
        d.rectangle([cx - r * 0.2, my - r * 0.06, cx + r * 0.2, my + r * 0.08], fill=(62, 26, 34))
        for k in range(-2, 3):
            d.line([cx + k * r * 0.1, my - r * 0.06, cx + k * r * 0.1, my + r * 0.08], fill=white, width=max(1, int(r * 0.03)))
    else:
        d.line([cx - r * 0.20, my, cx + r * 0.20, my], fill=lip, width=max(2, int(r * 0.075)))

    if sample.get('face') == 'crying':
        for s in (-1, 1):
            d.rectangle([cx + s * r * 0.4 - r * 0.04, cy + r * 0.2, cx + s * r * 0.4 + r * 0.04, cy + r * 0.52],
                        fill=(140, 200, 255))
