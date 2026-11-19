"""CONSOLE engine side of the shared acting layer: flat-style characters drawn from the shared skeleton
(acting/rig.py) and a 2D stage (meters -> pixels) for the real-world scenes (room, door, hallway).

The same actions as in PIXEL 3D (walk_to, sit, stand, look_at, gesture, react, pick...) drive these characters;
only the drawing differs: thick rounded limbs, a rounded torso, a big head with the console's face style."""
import math, numpy as np
from PIL import ImageDraw
from ...acting import rig

NIGHT = (20, 28, 66)
def tint(c, k=.38): return tuple(int(a * (1 - k) + b * k) for a, b in zip(c, NIGHT))
def shade(c, f): return tuple(max(0, min(255, int(v * f))) for v in c)

class Stage:
    """meters <-> canvas pixels for one console scene type; anchors adapt to the 9:16 / 16:9 composition"""
    def __init__(self, typ, CW, CH, sc=None):
        self.typ = typ; self.CW, self.CH = CW, CH; sc = sc or {}
        if typ == 'door':
            s = min(CW / 1.0, CH / 1.65); dw = s * .5; dh = dw * 2.15
            self.ppm = dh / 2.05; self.floor = CH * .8; self.zk = .0
            dx = (CW * float(sc.get('x', .55)) - CW / 2) / self.ppm
            self.anchors = {'door': (dx, 0.), 'door.front': (dx, .9), 'door.side': (dx + 1.0, .6), 'center': (0., .8), 'left': (-1.2, .8), 'right': (1.2, .8)}
        elif typ == 'hallway':
            self.ppm = CH * .22 / 1.8; self.floor = CH * .66; self.zk = .5
            self.anchors = {'end': (0., 0.), 'middle': (0., 2.5), 'front': (0., 5.), 'center': (0., 2.)}
        else:                                   # bedroom ('room')
            self.ppm = CH * .235; self.floor = CH * .755; self.zk = .07
            m = lambda fx: (CW * fx - CW / 2) / self.ppm
            self.anchors = {'bed': (m(.30), .45), 'bed.edge': (m(.30), 1.0), 'desk': (m(.84), .35), 'door': (m(.93), .2), 'door.front': (m(.86), .9),
                            'window': (m(.27), .2), 'center': (0., 1.2), 'left': (m(.15), 1.2), 'right': (m(.75), 1.2), 'front': (0., 2.4)}
        self.seats = {}
        if typ == 'room':
            m = lambda fx: (CW * fx - CW / 2) / self.ppm
            self.seats = {'bed': (m(.30), .55, 0., .50), 'desk_chair': (m(.80), .55, 0., .47)}
        # V3 levels a character can stand on (jump onto the bed...): opt-in, "levels": "auto" | [{"rect": [x0, z0, x1, z1], "y"}]
        lv = sc.get('levels'); self.levels = []
        if lv == 'auto' and typ == 'room':
            m = lambda fx: (CW * fx - CW / 2) / self.ppm
            self.levels = [((m(.11), .15, m(.6), .75), .75)]; self.anchors.update({'bed.top': (m(.36), .45), 'bed.foot': (m(.66), 1.0)})
        elif isinstance(lv, list):
            self.levels = [(tuple(float(v) for v in l['rect']), float(l.get('y', .5))) for l in lv if isinstance(l, dict) and l.get('rect')]
    def to_px(self, x, y, z):
        """world (x right, y up, z towards the camera) -> canvas (px, py, scale)"""
        if self.typ == 'hallway':
            k = 1 / (1 + max(0., 5 - z) * .32); sx = self.CW / 2 + x * self.ppm * 3 * k; fy = self.CH * (.66 + .34 * (1 - k)) ; s = self.ppm * 3 * k
            return sx, fy - y * s, s
        s = self.ppm * (1 + self.zk * z)
        return self.CW / 2 + x * s, self.floor + z * self.CH * .055 - y * s, s

class ConsoleWorld:
    """World interface of acting/timeline.py for a console scene"""
    def __init__(self, stage): self.st = stage; self.has_levels = bool(getattr(stage, 'levels', None))
    camera_heading = 0.                       # in the console stage the viewer looks along -z: facing it = heading 0
    floor_y = 0.
    def ground_y(self, x, z):
        best = 0.
        for (x0, z0, x1, z1), y in self.st.levels:
            if x0 <= x <= x1 and z0 <= z <= z1: best = max(best, y)
        return best
    def anchor(self, name):
        if name in self.st.anchors: return self.st.anchors[name]
        if name in self.st.seats: return self.st.seats[name][:2]
        return None
    def obstacles(self): return []
    def bounds(self): return (-8, -1, 8, 6)
    def seat(self, name): return self.st.seats.get(name)
    def door(self, name): return None
    def item(self, name): return None

def full_look(look):
    """the look of a library character with its preset expanded (same identity as in PIXEL 3D)"""
    pre = look.get('preset') or look.get('kind')
    if pre:
        try:
            from ..pixel3d.creatures import PRESETS
            if pre in PRESETS: return dict(PRESETS[pre], **{k: v for k, v in look.items() if k not in ('kind', 'preset')})
        except Exception: pass
    return look

def draw_figure(d, stage, sample, look, t, face_fn=None):
    """one character, from the skeleton of the sample (same parameters as PIXEL 3D)"""
    look = full_look(look)
    sk = rig.solve(sample['rig']); h = sample['heading']; c, s_ = math.cos(h), math.sin(h)
    X, Z = sample['x'], sample['z']; Y = float(sample.get('y', 0.))     # Y: standing on a level, or in the air (V3)
    def W(p):                                         # local joint -> canvas (orthographic front view, depth = z)
        wx = X + p[0] * c + p[2] * s_; wz = Z - p[0] * s_ + p[2] * c
        return stage.to_px(wx, float(p[1]) + Y, wz)
    def depth(p): return Z - p[0] * s_ + p[2] * c
    skin = tint(tuple(look.get('skin', (224, 172, 136))), .22); hood = tint(tuple(look.get('hood', (48, 58, 100))))
    jeans = tint(tuple(look.get('jeans', (30, 34, 60)))); hair = tint(tuple(look.get('hair', (24, 26, 46))), .2)
    outfit = look.get('outfit', 'hoodie'); style = look.get('hair_style') or ('long' if look.get('hair_long') else 'short')
    if outfit == 'dress': jeans = skin                                  # bare legs under a dress
    J = sk.joints
    P = {k: W(v) for k, v in J.items()}
    sc = P['pelvis'][2]
    front = math.cos(h)                              # 1 = facing the viewer, -1 = back to the viewer, 0 = profile
    def limb(a, b, w, col):
        (x0, y0, _), (x1, y1, _) = P[a], P[b]; ww = max(2, int(w * sc))
        d.line([x0, y0, x1, y1], fill=col, width=ww); r = ww / 2
        for (x, y) in ((x0, y0), (x1, y1)): d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    # far limbs first (the side turned away from the viewer)
    far = 'L' if depth(J['shL']) < depth(J['shR']) else 'R'; near = 'R' if far == 'L' else 'L'
    for tag, k in ((far, .85), (near, 1.)):
        limb('hip' + tag, 'kn' + tag, .17, shade(jeans, k)); limb('kn' + tag, 'an' + tag, .15, shade(jeans, k))
        ax, ay, _ = P['an' + tag]; fw = .14 * sc; d.rounded_rectangle([ax - fw, ay - .03 * sc, ax + fw + .06 * sc * math.sin(h), ay + .05 * sc], radius=int(.03 * sc) + 1, fill=(14, 14, 22))
    # torso: quad between shoulders and hips
    sh = [P['shL'], P['shR']]; hp = [P['hipL'], P['hipR']]
    wsh = .5 * sc * max(.55, abs(front) + .25); whp = .44 * sc * max(.6, abs(front) + .3)
    cx_s = (sh[0][0] + sh[1][0]) / 2; cy_s = (sh[0][1] + sh[1][1]) / 2; cx_h = (hp[0][0] + hp[1][0]) / 2; cy_h = (hp[0][1] + hp[1][1]) / 2
    d.polygon([(cx_s - wsh / 2, cy_s - .04 * sc), (cx_s + wsh / 2, cy_s - .04 * sc), (cx_h + whp / 2, cy_h + .08 * sc), (cx_h - whp / 2, cy_h + .08 * sc)], fill=hood)
    if outfit == 'dress':                                               # the skirt flares over the hips
        d.polygon([(cx_h - whp * .55, cy_h - .02 * sc), (cx_h + whp * .55, cy_h - .02 * sc), (cx_h + whp * .8, cy_h + .42 * sc), (cx_h - whp * .8, cy_h + .42 * sc)], fill=hood)
    else: d.rounded_rectangle([cx_h - whp / 2, cy_h - .02 * sc, cx_h + whp / 2, cy_h + .12 * sc], radius=int(.05 * sc), fill=jeans)
    if front > .3 and outfit == 'hoodie':
        for k_ in (-1, 1): d.line([cx_s + k_ * .05 * sc, cy_s + .05 * sc, cx_s + k_ * .05 * sc, cy_s + .2 * sc], fill=(170, 172, 190), width=max(1, int(.02 * sc)))
    if front > .3 and look.get('tie'): d.polygon([(cx_s, cy_s + .02 * sc), (cx_s - .03 * sc, cy_s + .22 * sc), (cx_s, cy_s + .27 * sc), (cx_s + .03 * sc, cy_s + .22 * sc)], fill=tint(tuple(look['tie'])))
    fore = skin if outfit in ('tshirt', 'dress') else hood                # short sleeves: bare forearms
    for tag, k in ((far, .85), (near, 1.)):
        limb('sh' + tag, 'el' + tag, .12, shade(hood, k)); limb('el' + tag, 'ha' + tag, .11, shade(fore, k))
        hx, hy, _ = P['ha' + tag]; r = .065 * sc; d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=skin)
    if sample.get('hold') == 'console':
        hx, hy, _ = P['haR']; w = .16 * sc; d.rounded_rectangle([hx - w, hy - w * 1.3, hx + w * .4, hy + w * .3], radius=int(w * .2), fill=(214, 214, 222))
        d.rectangle([hx - w * .8, hy - w * 1.1, hx + w * .2, hy - w * .3], fill=(104, 164, 86))
    # head
    hx, hy, _ = P['head']; r = .2 * sc; hyaw = h + float(sample['rig'].get('head', (0., 0.))[0]); hf = math.cos(hyaw)
    if style == 'ponytail' and hf < .6:                                # the tail behind the head
        tx_ = hx - math.sin(hyaw) * r * .9; d.ellipse([tx_ - r * .3, hy - r * .2, tx_ + r * .3, hy + r * 1.1], fill=hair)
    if style == 'long': d.rounded_rectangle([hx - r * 1.05, hy - r * .4, hx + r * 1.05, hy + r * 1.25], radius=int(r * .4), fill=hair)
    d.ellipse([hx - r, hy - r * 1.05, hx + r, hy + r * 1.05], fill=skin if hf > -.35 else hair)
    hat = look.get('hat'); hat_c = tint(tuple(look.get('hat_color') or look.get('hood', (60, 60, 70))), .3)
    if hf > -.35:
        if style != 'bald' and hat not in ('hood', 'beanie'):
            d.chord([hx - r * 1.04, hy - r * 1.18, hx + r * 1.04, hy + r * .25], 180, 360, fill=hair)
            if style == 'curly':
                for k_ in range(-2, 3): bx = hx + k_ * r * .42; d.ellipse([bx - r * .3, hy - r * 1.28, bx + r * .3, hy - r * .68], fill=hair)
            elif style == 'bun': d.ellipse([hx - r * .32, hy - r * 1.55, hx + r * .32, hy - r * .95], fill=hair)
            elif style == 'spiky':
                for k_ in range(-2, 3): bx = hx + k_ * r * .4; d.polygon([(bx - r * .22, hy - r * .9), (bx, hy - r * 1.42), (bx + r * .22, hy - r * .9)], fill=hair)
            if style in ('long', 'ponytail') and hf > .25:
                d.rectangle([hx - r * 1.02, hy - r * .2, hx - r * .8, hy + r * (1.2 if style == 'long' else .5)], fill=hair)
                d.rectangle([hx + r * .8, hy - r * .2, hx + r * 1.02, hy + r * (1.2 if style == 'long' else .5)], fill=hair)
        if hf > .25: face(d, hx + math.sin(hyaw) * r * .25, hy, r, sample, t, look, skin, hair)
        else:
            side = 1 if math.sin(hyaw) > 0 else -1          # profile: one eye and a nose
            ex = hx + side * r * .45; d.ellipse([ex - r * .08, hy - r * .1, ex + r * .08, hy + r * .06], fill=(20, 20, 30))
            d.polygon([(hx + side * r * .95, hy + r * .05), (hx + side * r * 1.12, hy + r * .2), (hx + side * r * .95, hy + r * .3)], fill=skin)
        fx_ = hx + math.sin(hyaw) * r * .25; lw = max(1, int(r * .07))
        if look.get('beard') and hf > .25:
            bc = hair if look['beard'] not in ('stubble',) else shade(skin, .75)
            if look['beard'] == 'mustache': d.rectangle([fx_ - r * .25, hy + r * .38, fx_ + r * .25, hy + r * .46], fill=bc)
            else: d.chord([fx_ - r * .78, hy + r * .05, fx_ + r * .78, hy + r * 1.08], 0, 180, fill=bc); d.ellipse([fx_ - r * .14, hy + r * .44, fx_ + r * .14, hy + r * .6], fill=(70, 30, 40))
        if look.get('glasses') and hf > .25:                           # same identity as in PIXEL 3D: Tom's glasses, Mamie's glasses
            gc = (30, 28, 36) if look['glasses'] not in ('sun', 'sunglasses') else (20, 20, 26)
            for k_ in (-1, 1):
                gx = fx_ + k_ * r * .38; box = [gx - r * .24, hy - r * .16, gx + r * .24, hy + r * .2]
                if look['glasses'] in ('sun', 'sunglasses'): d.rounded_rectangle(box, radius=int(r * .08), fill=gc)
                else: d.rounded_rectangle(box, radius=int(r * .08), outline=gc, width=lw)
            d.line([fx_ - r * .14, hy - r * .02, fx_ + r * .14, hy - r * .02], fill=gc, width=lw)
        if hat in ('cap', 'beanie', 'hood', 'tophat', 'crown'):
            if hat == 'cap': d.chord([hx - r * 1.05, hy - r * 1.2, hx + r * 1.05, hy + r * .1], 180, 360, fill=hat_c); d.rectangle([fx_ - r * .2, hy - r * .55, fx_ + r * 1.0 * (1 if math.sin(hyaw) >= 0 else -1) + r * .2, hy - r * .45], fill=hat_c)
            elif hat == 'beanie': d.chord([hx - r * 1.06, hy - r * 1.3, hx + r * 1.06, hy + r * .05], 180, 360, fill=hat_c); d.rectangle([hx - r * 1.06, hy - r * .55, hx + r * 1.06, hy - r * .35], fill=shade(hat_c, .85))
            elif hat == 'hood': d.arc([hx - r * 1.25, hy - r * 1.35, hx + r * 1.25, hy + r * 1.15], 160, 380, fill=hood, width=max(2, int(r * .28)))
            elif hat == 'tophat': d.rectangle([hx - r * .65, hy - r * 1.9, hx + r * .65, hy - r * .8], fill=hat_c); d.rectangle([hx - r * 1.0, hy - r * .9, hx + r * 1.0, hy - r * .78], fill=hat_c)
            else: d.polygon([(hx - r * .7, hy - r * .85), (hx - r * .7, hy - r * 1.35), (hx - r * .35, hy - r * 1.1), (hx, hy - r * 1.45), (hx + r * .35, hy - r * 1.1), (hx + r * .7, hy - r * 1.35), (hx + r * .7, hy - r * .85)], fill=(230, 190, 60))
        if look.get('headphones', True) and hat not in ('hood', 'beanie'):      # the player's headphones (default, as in PIXEL 3D)
            d.arc([hx - r * 1.08, hy - r * 1.22, hx + r * 1.08, hy + r * .5], 190, 350, fill=(26, 26, 32), width=max(2, int(r * .12)))
            for k_ in (-1, 1):
                ex_ = hx + k_ * r * 1.0 * max(.3, abs(math.cos(hyaw)))
                if abs(math.cos(hyaw)) > .3 or (k_ > 0) == (math.sin(hyaw) > 0):
                    d.rounded_rectangle([ex_ - r * .17, hy - r * .25, ex_ + r * .17, hy + r * .25], radius=int(r * .08), fill=(26, 26, 32))
                    d.ellipse([ex_ - r * .05, hy - r * .05, ex_ + r * .05, hy + r * .05], fill=(80, 255, 130))
    else:
        d.ellipse([hx - r * .96, hy - r * 1.0, hx + r * .96, hy + r * .98], fill=hair)
        if style == 'bun': d.ellipse([hx - r * .3, hy - r * 1.4, hx + r * .3, hy - r * .85], fill=hair)

def face(d, cx, cy, r, sample, t, look=None, skin=None, hair=None):
    """console-style face (same expression names as PIXEL 3D)

    look["faces"] == "expressive" switches to the expressive face (expression.py): eyelids, gaze,
    eyebrows, a mouth that really speaks, micro-movements. Anything else keeps the historical face,
    pixel for pixel."""
    if look is not None and (look.get('faces') or 'flat') == 'expressive':
        return expressive_face(d, cx, cy, r, sample, t, look, skin, hair)
    ex = sample.get('face', 'neutral'); dark = (22, 20, 32); lip = (96, 44, 52)
    wide = ex in ('scared', 'shocked', 'surprised', 'nervous'); blink = sample.get('blink')
    for s in (-1, 1):
        x = cx + s * r * .38; y = cy + r * .02
        if blink or ex in ('sleeping', 'closed'): d.line([x - r * .14, y, x + r * .14, y], fill=dark, width=max(1, int(r * .07))); continue
        if ex in ('joy', 'laugh', 'happy'): d.arc([x - r * .15, y - r * .12, x + r * .15, y + r * .12], 200, 340, fill=dark, width=max(1, int(r * .07))); continue
        w = r * (.17 if wide else .12); hgt = r * (.17 if wide else .11)
        d.ellipse([x - w, y - hgt, x + w, y + hgt], fill=(240, 240, 246)); p = r * .06; d.ellipse([x - p, y - p, x + p, y + p], fill=dark)
        by = y - r * (.32 if wide else .25); tilt = {'angry': .12, 'determined': .08, 'sad': -.12, 'scared': -.08}.get(ex, 0.) * s
        d.line([x - r * .17, by - tilt * r, x + r * .17, by + tilt * r], fill=dark, width=max(1, int(r * .06)))
    my = cy + r * .52; talk = sample.get('talking') and int(t * 9) % 2 == 0
    if talk or wide: d.ellipse([cx - r * .12, my - r * .1, cx + r * .12, my + r * .12], fill=(70, 30, 40))
    elif ex in ('happy', 'joy', 'laugh', 'smile', 'proud', 'excited'): d.arc([cx - r * .24, my - r * .2, cx + r * .24, my + r * .1], 20, 160, fill=lip, width=max(1, int(r * .06)))
    elif ex in ('sad', 'crying', 'smile_sad'): d.arc([cx - r * .2, my, cx + r * .2, my + r * .25], 200, 340, fill=lip, width=max(1, int(r * .05)))
    else: d.line([cx - r * .14, my, cx + r * .14, my], fill=lip, width=max(1, int(r * .05)))


def expressive_face(d, cx, cy, r, sample, t, look, skin=None, hair=None):
    """the acted face of a figure: the head yaw/pitch of the rig becomes a real gaze, the expression
    opens the lids and the brows, the dialogue moves the mouth (opt-in, see expression.py)"""
    from . import expression as X
    rg = sample.get('rig') or {}
    yaw, pitch = (list(rg.get('head', (0., 0.))) + [0., 0.])[:2]
    gaze = (max(-1., min(1., yaw / .95)) * .78, max(-1., min(1., -pitch / .45)) * .62)
    if sample.get('gaze') == 'left': gaze = (min(-.45, gaze[0]), gaze[1])
    elif sample.get('gaze') == 'right': gaze = (max(.45, gaze[0]), gaze[1])
    p = X.face_params(sample.get('face', 'neutral'), t=t, seed=float(rg.get('seed', 0.)),
                      talking=bool(sample.get('talking')), gaze=gaze,
                      persona=look.get('personality'), intensity=float(look.get('face_intensity', 1.)))
    sk = tuple(skin or tint(tuple(look.get('skin', (224, 172, 136))), .22))
    hr = tuple(hair or tint(tuple(look.get('hair', (24, 26, 46))), .2))
    X.draw_face(d, cx, cy + r * p['breath_y'] * .4, r, p, sk, hr,
                lip=look.get('lip'), iris=look.get('iris'), brow_color=look.get('brow_color'),
                sep=.38, eye_y=.02, mouth_y=.52, nose=look.get('nose', True),
                socket=look.get('eye_socket', True), lashes=look.get('lashes', True))
