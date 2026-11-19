"""Le Veilleur (15 novembre 2026, « Le Phare qui efface ») : personnage de la bibliothèque, PIXEL 3D (PS1).

Très grand (≈ 2,3 m) mais aux proportions VOXEL compactes : grand imperméable noir trempé et luisant (col relevé, ceinture, pans qui suivent
les jambes, gouttes qui tombent de l'ourlet), pantalon sombre, bottes, GANTS BLANCS (paume, quatre doigts, pouce), et à la place de la tête un
RECTANGLE DE VERRE DÉPOLI vide, pâle, sans yeux ni bouche (jamais d'yeux cyan), cerclé d'un fin cadre de fer comme une vitre de lanterne,
légèrement lumineux pour se lire dans le noir, et qui reflète ce qui l'entoure (le voyant rouge).
Il marche, descend un escalier, se tient immobile (squelette commun, acting/rig.py) et RAMPE au sol (pose dédiée, le squelette ne la fait pas).

Dans un épisode :
    "cast": {"veilleur": {"ref": "veilleur"}}              (bibliothèque : library/characters/veilleur.json, `kind: veilleur`)
    "cast": {"veilleur": {"kind": "veilleur", "scale": 1.2, "fissure": 0, "lueur": .1, "cadre": true}}
Clés de cast : `scale` (défaut 1,2 -> 2,38 m cadre compris), `fissure` 0..1 (fissure en SOURIRE dans le verre), `lueur` (émission du verre, défaut 0,07),
`cadre` (cadre de fer du verre, défaut vrai), `gouttes` (défaut vrai).
Clés de piste dirigée (par clé, elles glissent d'une clé à l'autre) : `x_rampe` 0 (debout) .. 1 (à quatre pattes, ventre bas, la tête de verre
en avant ; on avance en déplaçant `p`, les mains et les genoux suivent la distance parcourue) ; `x_fissure` 0..1 (la fissure s'ouvre) ; `x_lueur`
(émission du verre, par clé). Avec `talk: 1` (la voix de Noé qui sort du verre), le verre palpite faiblement.
Tout le reste (p, yaw, head, gesture, reach_r/reach_l, vis, dissolve) est celui de tous les acteurs. PS1 seulement : en VOXEL il reste une
silhouette sombre approchée (pas de tête de verre)."""
import functools, math
import numpy as np
from .r3d import C, orient, M_FABRIC, M_METAL
from ...acting import rig

COAT = (26, 28, 34); COAT_HI = (40, 44, 52); TROUS = (20, 21, 26); BOOT = (14, 14, 16); GLOVE = (236, 234, 226); GLASS = (138, 150, 160); RIM = (48, 52, 58)
DROP = (170, 196, 222)


@functools.lru_cache(maxsize=24)
def glass_tex(fissure_q, W=24, H=32):
    """the frosted pane: pale, grainy, brighter at the top, a faint inner rim ; `fissure_q` (0..16) opens a crack shaped like a SMILE from the
    middle towards the corners, with small branches. Five channels: RGBA + emission mask (the crack does not glow)."""
    f = fissure_q / 16.
    rng = np.random.default_rng(5)
    yy = np.arange(H, dtype=np.float32)[:, None] / H
    base = np.array(GLASS, np.float32)[None, None] * (1.06 - .14 * yy[..., None]) + (rng.random((H, W, 1)).astype(np.float32) - .5) * 16.
    img = np.zeros((H, W, 5), np.float32); img[..., :3] = base; img[..., 3] = 255.; img[..., 4] = 255.
    img[0, :, :3] *= .86; img[-1, :, :3] *= .86; img[:, 0, :3] *= .86; img[:, -1, :3] *= .86
    if f > 0:
        cx = (W - 1) / 2.; half = f * (W / 2. - 1.5)
        pts = []
        for x in range(W):
            if abs(x - cx) > half: continue
            y = int(round(H * .64 - .045 * (x - cx) ** 2 + (1 if (x % 3 == 0) else 0) - (1 if x % 5 == 2 else 0)))
            pts.append((x, y))
        for (x, y) in pts:
            for yy_ in (y + 1, y, y - 1):                                        # three pixels thick: the PS1 dither and the glow eat thin strokes
                if 0 <= yy_ < H: img[yy_, x, :3] = (22, 24, 30); img[yy_, x, 4] = 0.
            if 0 <= y + 2 < H: img[y + 2, x, :3] = np.minimum(255, img[y + 2, x, :3] * 1.2); img[y + 2, x, 4] = 255.
        if f > .55 and pts:                                                      # small branches at both corners and under the middle
            for (x, y) in (pts[0], pts[-1]):
                for d in range(1, 1 + int(4 * (f - .5) * 2)):
                    xx = x - d if x < cx else x + d; y2 = y - d
                    if 0 <= xx < W and 0 <= y2 < H: img[y2, xx, :3] = (52, 56, 62); img[y2, xx, 4] = 0.
            mid = pts[len(pts) // 2]
            for d in range(1, 1 + int(3 * (f - .5) * 2)):
                y2 = mid[1] + d
                if y2 < H: img[y2, mid[0] + (d % 2), :3] = (52, 56, 62); img[y2, mid[0] + (d % 2), 4] = 0.
    return np.clip(img, 0, 255).astype(np.uint8)


def _crawl(p, look_head=(0., 0.)):
    """joints and frames of the crawl (local frame: +z = where he crawls), driven by the gait phase (distance travelled)"""
    sk = rig.Skeleton(); J = sk.joints; Fr = sk.frames
    ph = float(p.get('phase', 0.)); t = float(p.get('t', 0.)); w = float(p.get('gait', 0.))
    lean = 1.33 + .04 * math.sin(ph * 2) * w
    roll = .07 * math.sin(ph) * w
    pel = rig.V(.0, .40 + .02 * math.sin(ph * 2) * w, -.62); J['pelvis'] = pel
    Rt = rig.rot_x(lean) @ rig.rot_z(roll); Fr['torso'] = (Rt, pel)
    neck = pel + Rt @ rig.V(0, rig.NECK_UP, 0); J['neck'] = neck; J['chest'] = pel + Rt @ rig.V(0, .32, 0)
    hy, hp = look_head
    Rh = Rt @ rig.rot_y(float(hy)) @ rig.rot_x(-(1.22 + float(hp)))              # the glass held up, looking ahead
    J['head'] = neck + Rh @ rig.V(0, rig.HEAD_UP, 0); Fr['head'] = (Rh, J['head'])
    fwd = Rt @ rig.V(0, 0, 1)
    for side in (1, -1):
        tag = 'R' if side > 0 else 'L'
        sh = pel + Rt @ rig.V(side * rig.SHOULDER_X, rig.SHOULDER_Y - rig.PELVIS_Y, 0)
        q = ph + (0. if side > 0 else math.pi)
        hz = .14 + .17 * math.sin(q) * w; hl = .07 * max(0., math.cos(q)) * w
        tgt = rig.V(side * .36, .19 + hl, hz)
        el, ha = rig.two_bone(sh, tgt, rig.UPPER, rig.FORE, rig.V(side * .8, .3, -.4))
        J['sh' + tag], J['el' + tag], J['ha' + tag] = sh, el, ha
        Fr['upper' + tag] = (rig.seg_frame(sh, el, fwd), sh); Fr['fore' + tag] = (rig.seg_frame(el, ha, rig.V(0, 1, 0)), el); Fr['hand' + tag] = (Fr['fore' + tag][0], ha)
        hip = pel + rig.V(side * rig.HIP_X, 0, 0)
        dy = float(hip[1]) - .07; dz = math.sqrt(max(rig.THIGH ** 2 - dy * dy, 0.))
        kn = rig.V(side * (rig.HIP_X + .03), .07, float(hip[2]) + dz + .07 * math.sin(q + math.pi) * w)       # knees on the floor, dragged
        an = kn + rig.V(0, .02, -rig.SHIN)
        J['hip' + tag], J['kn' + tag], J['an' + tag] = hip, kn, an
        Fr['thigh' + tag] = (rig.seg_frame(hip, kn), hip); Fr['shin' + tag] = (rig.seg_frame(kn, an, rig.V(0, -1, 0)), kn)
        Fr['foot' + tag] = (rig.rot_x(math.pi), rig.V(float(an[0]), .1, float(an[2])))                         # boots flat, toes backwards (as kneeling)
    return sk


def _blend(a, b, k):
    """skeleton between standing (a) and crawling (b): joints interpolated, frames rebuilt from them"""
    if k <= 1e-3: return a
    if k >= .999: return b
    sk = rig.Skeleton(); J = sk.joints; Fr = sk.frames
    for n in a.joints:
        if n in b.joints: J[n] = a.joints[n] * (1 - k) + b.joints[n] * k
    la = math.atan2(float((a.joints['neck'] - a.joints['pelvis'])[2]), float((a.joints['neck'] - a.joints['pelvis'])[1]))
    lb = math.atan2(float((b.joints['neck'] - b.joints['pelvis'])[2]), float((b.joints['neck'] - b.joints['pelvis'])[1]))
    Rt = rig.rot_x(la * (1 - k) + lb * k); Fr['torso'] = (Rt, J['pelvis'])
    ha_ = a.frames['head'][0]; hb_ = b.frames['head'][0]
    pa = math.atan2(float(ha_[2, 1]), float(ha_[1, 1])); pb = math.atan2(float(hb_[2, 1]), float(hb_[1, 1]))
    Fr['head'] = (rig.rot_x(pa * (1 - k) + pb * k), J['head'])
    fwd = Rt @ rig.V(0, 0, 1)
    for tag in 'RL':
        Fr['upper' + tag] = (rig.seg_frame(J['sh' + tag], J['el' + tag], fwd), J['sh' + tag]); Fr['fore' + tag] = (rig.seg_frame(J['el' + tag], J['ha' + tag], fwd), J['el' + tag])
        Fr['hand' + tag] = (Fr['fore' + tag][0], J['ha' + tag])
        Fr['thigh' + tag] = (rig.seg_frame(J['hip' + tag], J['kn' + tag]), J['hip' + tag]); Fr['shin' + tag] = (rig.seg_frame(J['kn' + tag], J['an' + tag]), J['kn' + tag])
        fa, fb = a.frames['foot' + tag], b.frames['foot' + tag]
        Fr['foot' + tag] = (fa[0] if k < .5 else fb[0], fa[1] * (1 - k) + fb[1] * k)
    return sk


def build(sample, look, k=None, spec=None, lights=None, parts=None):
    """boxes of the Veilleur for one frame (same contract as rigfig.build: -> (boxes, skeleton))"""
    k = dict(k or {}); spec = spec or {}
    s = float(look.get('scale', spec.get('scale', 1.2)))
    xp = sample.get('xp') or {}
    crawl = max(0., min(1., float(xp.get('rampe', look.get('rampe', 0.)) or 0.)))
    fis = max(0., min(1., float(xp.get('fissure', look.get('fissure', 0.)) or 0.)))
    glow = float(xp.get('lueur', look.get('lueur', .07)))
    if sample.get('talking'):                                               # the voice comes out of the glass: it flickers faintly while he "speaks"
        glow += .1 * (.5 + .5 * math.sin(float(sample['rig'].get('t', 0.)) * 17.)) * (.6 + .4 * math.sin(float(sample['rig'].get('t', 0.)) * 5.3))
    rp = sample['rig']
    sk_s = rig.solve(rp)
    sk = _blend(sk_s, _crawl(rp, rp.get('head', (0., 0.))), crawl) if crawl > 1e-3 else sk_s
    Rw = rig.rot_y(sample['heading']); base = np.array([sample['x'], float(sample.get('y', 0.)), sample['z']], np.float32)
    out = []
    def emit(boxes, frame, name):
        R, o = frame
        for b in boxes: b.lo = b.lo * s; b.hi = b.hi * s
        bx = orient(boxes, 0., Rw @ (np.asarray(o, np.float32) * s) + base, Rw @ R)
        if parts is not None: parts.setdefault(name, []).extend(bx)
        out.extend(bx)
    kk = dict(hidden=k.get('hidden', False), noref=k.get('noref', False), dissolve=float(k.get('dissolve', 0.) or 0.))
    kw = {kk_: v for kk_, v in kk.items() if v}
    # legs: long coat over the thighs (down past the knee), dark trousers, boots
    for tag in 'LR':
        ln = rig.THIGH + .26 * (1. - crawl)                                    # kneeling or crawling, the coat no longer hangs past the knee
        emit([C((0, -ln / 2 + .07, 0), (.26, ln, .29), COAT, mat=M_FABRIC, refl=.05, **kw)], sk.frames['thigh' + tag], 'thigh' + tag)
        emit([C((0, -rig.SHIN / 2 + .03, 0), (.2, rig.SHIN, .22), TROUS, mat=M_FABRIC, **kw)], sk.frames['shin' + tag], 'shin' + tag)
        emit([C((0, .05, .04), (.24, .12, .33), BOOT, refl=.1, **kw), C((0, .02, .04), (.25, .04, .34), (8, 8, 10), **kw)], sk.frames['foot' + tag], 'foot' + tag)
    # torso: coat body, shoulder pads, belt and buckle, front opening and buttons, coat tails behind, high collar around the base of the glass
    yb = -rig.PELVIS_Y
    tb = [C((0, -.02, 0), (.56, .22, .36), COAT, mat=M_FABRIC, refl=.05, **kw), C((0, yb + 1.13, 0), (.64, .74, .38), COAT, mat=M_FABRIC, refl=.05, **kw)]
    tb += [C((sd * .27, yb + 1.39, 0), (.2, .12, .4), COAT_HI, mat=M_FABRIC, refl=.05, **kw) for sd in (-1, 1)]
    tb += [C((0, yb + .86, 0), (.66, .07, .4), (12, 12, 14), **kw), C((0, yb + .86, .205), (.1, .07, .01), (110, 110, 116), mat=M_METAL, **kw),
           C((.02, yb + 1.1, .193), (.03, .62, .01), (12, 12, 14), **kw)]
    tb += [C((-.06, yb + y_, .194), (.04, .04, .01), (70, 72, 78), mat=M_METAL, **kw) for y_ in (1.0, 1.2, 1.38)]
    tb += [C((0, yb + .52, -.18), (.6, .55, .05), COAT, mat=M_FABRIC, refl=.05, **kw), C((0, yb + 1.36, -.03), (.5, .2, .42), COAT_HI, mat=M_FABRIC, refl=.05, **kw)]                # high collar, just under the glass
    emit(tb, sk.frames['torso'], 'torso')
    if look.get('gouttes', True) and not k.get('hidden'):                    # drops falling from the hem of the soaked coat (their own part: not the torso)
        t = float(rp.get('t', 0.)); dr = []
        for i, (dx, dz) in enumerate(((-.22, .16), (.2, .17), (.1, -.2), (-.15, -.21))):
            ph = (t * 1.3 + i * .27) % 1.
            dr.append(C((dx, yb + .3 - ph * .29, dz), (.02, .035, .02), DROP, emis=.25, cast=False, **kw))
        emit(dr, sk.frames['torso'], 'gouttes')
    # arms: coat sleeves, cuffs ; hands: WHITE GLOVES (palm, four fingers, thumb)
    for tag in 'LR':
        emit([C((0, -rig.UPPER / 2 + .03, 0), (.19, rig.UPPER + .1, .2), COAT, mat=M_FABRIC, refl=.05, **kw)], sk.frames['upper' + tag], 'upper' + tag)
        emit([C((0, -rig.FORE / 2 + .02, 0), (.18, rig.FORE + .04, .19), COAT, mat=M_FABRIC, refl=.05, **kw),
              C((0, -rig.FORE + .03, 0), (.21, .07, .22), COAT_HI, mat=M_FABRIC, **kw)], sk.frames['fore' + tag], 'fore' + tag)
        g = [C((0, -.06, 0), (.15, .14, .16), GLOVE, **kw)]
        g += [C((dx, -.17, .0), (.036, .1, .05), GLOVE, **kw) for dx in (-.054, -.018, .018, .054)]
        g += [C((0, -.08, .09), (.05, .08, .04), GLOVE, **kw), C((0, .0, 0), (.16, .04, .17), (210, 208, 200), **kw)]
        emit(g, sk.frames['hand' + tag], 'hand' + tag)
    # head: the empty frosted glass (no eyes, no mouth), a thin iron frame like a lantern pane
    hb = [C((0, .03, 0), (.36, .5, .3), GLASS, emis=glow, refl=.06, tex={'+z': glass_tex(int(round(fis * 16)))}, texemis=glow, **kw)]
    if look.get('cadre', True):
        for (sx, sy, sz, w, h, d) in ((0, .285, 0, .39, .03, .33), (0, -.225, 0, .39, .03, .33), (-.185, .03, 0, .03, .52, .33), (.185, .03, 0, .03, .52, .33)):
            hb.append(C((sx, sy, sz), (w, h, d), RIM, mat=M_METAL, **kw))
    emit(hb, sk.frames['head'], 'head')
    return out, sk
