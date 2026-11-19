"""PIXEL 3D characters driven by the shared skeleton (acting/rig.py): every body part is a group of boxes in its
own rotated frame (r3d instances), so limbs swing, knees bend and the body turns at any angle. The look (outfits,
hair styles, hats, held objects) reuses the original builders of poses.py, only re-anchored on the joints."""
import math, numpy as np
from .r3d import C, orient, M_FABRIC
from . import art
from . import bodies
from . import eyes as EY
from . import assets as A
from . import poses as P
from ...acting import rig

# Measurement hook, off in production. tools/cadrage_qc.py sets it to a dict and build() files each emitted group
# under the name of the skeleton frame it came from ("foreR", "head", "torso"...), so a rendered image can be read
# back body part by body part. None here: one `is not None` test per emitted group and nothing else.
PARTS = None

def _part_of(sk, frame):
    for name, fr in sk.frames.items():
        if fr is frame: return name
    return 'hold'

def _scaled(bx, s):
    if s != 1.0:
        for b in bx: b.lo = b.lo * s; b.hi = b.hi * s
    return bx

def look_kw(look, spec=None):
    spec = spec or {}
    lk = lambda key: spec.get(key, look.get(key))
    return dict(hood=tuple(look.get('hood', A.HOOD)), jeans=tuple(look.get('jeans', A.JEANS)), hair=tuple(look.get('hair', A.HAIR)),
                skin=tuple(look.get('skin', A.SKIN)), shirt=tuple(look['shirt']) if look.get('shirt') else None,
                outfit=lk('outfit') if lk('outfit') in P.OUTFITS else 'hoodie', hair_style=lk('hair_style') if lk('hair_style') in P.HAIR_STYLES else None,
                hat=lk('hat') if lk('hat') in P.HATS else None, hat_color=tuple(lk('hat_color')) if lk('hat_color') else None,
                tie=tuple(lk('tie')) if lk('tie') else None, cape=tuple(lk('cape')) if lk('cape') else None,
                headphones=look.get('headphones', True), backpack=look.get('backpack', True), hair_long=look.get('hair_long', False),
                eyes=tuple(look['eyes']) if look.get('eyes') else None, scale=float(look.get('scale', spec.get('scale', 1.0))),
                # expressive look (opt-in, see assets.face_tex_hd / poses.hair_strands): absent keys = V2 rendering
                hair2=tuple(look['hair2']) if look.get('hair2') else None, detail=bool(lk('detail')),
                accent=tuple(look['accent']) if look.get('accent') else None)

def build(sample, look, face, k=None, spec=None, lights=None):
    """boxes of one character for one frame. sample: dict from acting.timeline (x, z, heading, rig, hold...)"""
    if look.get('kind') == 'veilleur':                # 15/11/2026 : le Veilleur (veilleur.py), opt-in par le cast `kind: veilleur` ; aucun autre personnage ne passe ici
        from . import veilleur as VE
        return VE.build(sample, look, k, spec, lights, PARTS)
    if art.on('figure'): return art.figure(sample, look, face, k, spec, lights)      # art v2, opt-in (episode "art")
    # bodies.promoted: the premium look keys the engine already owns, filled in where the scene left them
    # empty, and ONLY under a premium body preset (`promote`). The very same object without the key, so
    # look_kw below reads exactly what it read before, to the bit.
    k = k or {}; L = look_kw(bodies.promoted(look), spec); s = L['scale']
    # bodies.solve = rig.solve, plus the reach correction of the refit (bit-for-bit rig.solve without the key):
    # the IK must aim where the refitted hand is DRAWN, not where rig.py would put it. acted.arm_points reads
    # the same function, so the cinematographer and the renderer can never disagree about one hand.
    sk = bodies.solve(sample['rig'])
    Rw = rig.rot_y(sample['heading']); base = np.array([sample['x'], float(sample.get('y', 0.)), sample['z']], np.float32)
    out = []
    bd = bodies.active()                 # refonte des proportions, opt-in (cle d'episode "body"); None = ancien rendu
    def emit(boxes, frame, name=None):
        R, o = frame
        if name is None: name = _part_of(sk, frame) if (PARTS is not None or bd is not None) else None
        if bd is not None: boxes, o = bodies.shape(bd, name, boxes, o, R, sk, L, k)
        bx = orient(_scaled(boxes, s), 0., Rw @ (np.asarray(o, np.float32) * s) + base, Rw @ R)
        if PARTS is not None: PARTS.setdefault(name, []).extend(bx)
        out.extend(bx)
    hood, jeans, skin, hair = L['hood'], L['jeans'], L['skin'], L['hair']; outfit = L['outfit']
    low = skin if outfit == 'dress' else jeans; shoes = (28, 26, 28)
    # legs
    for tag in 'LR':
        emit([C((0, -rig.THIGH / 2 + .03, 0), (.18, rig.THIGH + .10, .21), low, mat=M_FABRIC, **k)], sk.frames['thigh' + tag])
        emit([C((0, -rig.SHIN / 2 + .01, 0), (.17, rig.SHIN + .06, .19), low, mat=M_FABRIC, **k)], sk.frames['shin' + tag])
        emit([C((0, .04, .03), (.19, .08, .27), shoes, **k)], sk.frames['foot' + tag])
    # torso (frame origin = pelvis)
    yb = -rig.PELVIS_Y; tb = [C((0, -.03, 0), (.44, .16, .25), low if outfit != 'dress' else hood, mat=M_FABRIC, **k)]
    if outfit == 'hoodie':
        tb.append(C((0, yb + 1.12, 0), (.50, .64, .28), hood, mat=M_FABRIC, **k))
        if L['shirt']: tb.append(C((0, yb + 1.12, .142), (.2, .5, .01), L['shirt'], **k))
        tb.append(C((0, yb + 1.0, .145), (.30, .14, .01), tuple(int(c * .75) for c in hood), **k))
        for sd in (-1, 1): tb.append(C((sd * .05, yb + 1.30, .145), (.022, .16, .012), (196, 196, 186), **k))
        if L['hat'] != 'hood': tb.append(C((0, yb + 1.46, -.06), (.44, .10, .22), tuple(int(c * .85) for c in hood), **k))
    else:
        tb += P.torso(0., 0., 1, yb, outfit, hood, skin, k, tie=L['tie'], shirt=L['shirt'], apron_color=look.get('apron_color'))
    if L['backpack'] and outfit in ('hoodie', 'tshirt', 'coat', 'spacesuit', 'suit'):
        tb.append(C((0, yb + 1.16, -.21), (.38, .48, .15), (36, 40, 44) if outfit != 'spacesuit' else (220, 220, 226), mat=M_FABRIC, **k))
    if L['cape']: tb.append(C((0, yb + .92, -.2), (.54, 1.05, .03), L['cape'], mat=M_FABRIC, **k))
    if L['detail']: tb += P.outfit_detail(0., 0., 1, yb, outfit, hood, k, accent=L['accent'])
    emit(tb, sk.frames['torso'])
    # neck and deltoid caps: volumes the stock body has not got, so they are a GROUP OF THEIR OWN and the
    # measuring tools can tell a narrowed trunk from the shoulders that bridge it (opt-in, empty by default)
    if bd is not None: emit(bodies.neck_and_shoulders(bd, skin, hood, k), sk.frames['torso'], 'neck')
    # the premium garment volumes (square shoulder step, zip, pockets): their OWN group too, and for the
    # same reason -- the silhouette tools must keep reading a trunk where they read a trunk, and this
    # group is deliberately NOT scaled by `torso`/`torso_z` (bodies.extras states its numbers final).
    if bd is not None and bd.get('detail'): emit(bodies.extras(bd, L, k), sk.frames['torso'], 'voxel')
    # arms
    fore = skin if outfit in ('tshirt', 'dress') else hood
    for tag in 'LR':
        emit([C((0, -rig.UPPER / 2 + .03, 0), (.13, rig.UPPER + .08, .14), hood, mat=M_FABRIC, **k)], sk.frames['upper' + tag])
        emit([C((0, -rig.FORE / 2 + .02, 0), (.12, rig.FORE + .03, .13), fore, mat=0 if fore == skin else M_FABRIC, **k)], sk.frames['fore' + tag])
        emit([C((0, -.02, 0), (.12, .12, .12), skin, **k)], sk.frames['hand' + tag])
    # head (frame origin = head centre)
    hb = [C((0, 0, 0), (.40, .40, .38), skin, tex={'+z': face}, **k)]
    hb += P.hair_and_hat(0., -1.68, 0., 1, hair, 'long' if (L['hair_long'] and not L['hair_style']) else L['hair_style'], L['hat'], L['hat_color'], hood, k, hair2=L['hair2'])
    if L['headphones'] == 'cou':                      # 9/11/2026 : headphones worn around the neck (opt-in value 'cou')
        hb += [C((sd * .19, -.3, .03), (.07, .15, .15), (26, 26, 32), **k) for sd in (-1, 1)] + [C((0, -.33, -.11), (.44, .05, .06), (26, 26, 32), **k)]
    elif L['headphones'] and L['hat'] not in ('hood', 'beanie'):
        for sd in (-1, 1):
            hb.append(C((sd * .225, 0, 0), (.06, .16, .16), (26, 26, 32), **k))
            hb.append(C((sd * .258, 0, .04), (.02, .035, .035), (80, 255, 130), emis=1.6, cast=False, **k))
        if not L['hat'] or L['hat'] == 'none': hb.append(C((0, .275, 0), (.48, .045, .1), (26, 26, 32), **k))
    if L['eyes'] is not None:
        for sd in (-1, 1): hb.append(C((sd * .09, .025, .195), (.05, .045, .01), L['eyes'], emis=3.2, cast=False, **k))
    emit(hb, sk.frames['head'])
    # held object: upright in the torso frame, at the main hand
    item = sample.get('hold')
    if item in P.HOLD_ITEMS:
        il = []
        ib = P.held_item(item, (0., 0., 0.), 1, k, il, tuple(spec['hold_color']) if spec and spec.get('hold_color') else None)
        left = bool(sample['rig'].get('left'))            # scène dirigée `side: "left"` (31/10/2026) : l'objet passe dans la main gauche, en miroir ; absent = rien ne change
        if left:
            for b_ in ib: lo_, hi_ = b_.lo.copy(), b_.hi.copy(); b_.lo = np.array([-hi_[0], lo_[1], lo_[2]], np.float32); b_.hi = np.array([-lo_[0], hi_[1], hi_[2]], np.float32)
            il = [((-p_[0], p_[1], p_[2]), c_, pw, r_) for (p_, c_, pw, r_) in il]
        R_t = sk.frames['torso'][0]; hand = sk.joints['haL' if left else 'haR']
        emit(ib, (R_t, hand))
        if item == 'flashlight':                       # a torch lights ahead, not the face of who holds it
            il = [((p_[0], p_[1], p_[2] * 1.9), c_, pw * .45, r_ * 1.3) for (p_, c_, pw, r_) in il]
        tc = look.get('torche') if item in ('flashlight', 'od_flashlight') else None
        if tc and lights is not None:                  # 15/11/2026, cast key `torche` (opt-in): the beam is a SPOT that starts at the lens and follows the hand
            cfg = tc if isinstance(tc, dict) else {}
            hs_ = float(bd['hand']) if bd is not None else 1.
            hnd = hand + bodies.arm_shift(bd, sk, -1 if left else 1)
            lens = Rw @ (R_t @ np.array([0., 0., .19], np.float32) * (s * hs_) + hnd * s) + base
            d = Rw @ (sk.frames['head'][0] if cfg.get('vise') == 'regard' else R_t) @ np.array([0., 0., 1.], np.float32)
            d = d + np.array([0., -math.tan(math.radians(float(cfg.get('pente', 4.)))), 0.], np.float32); d = d / float(np.linalg.norm(d))
            half = float(cfg.get('angle', 17.))
            lights.append((tuple(float(v) for v in lens + d * .04), (1., .95, .84), float(cfg.get('puissance', 4.)), float(cfg.get('portee', 8.)), False,
                           (tuple(float(v) for v in d), math.cos(math.radians(half * .55)), math.cos(math.radians(half)))))
            il = [((0., .05, .6), (1., .93, .8), .22, 1.3)]                  # only a faint spill near the hand (no light floating ahead of the body)
        if lights is not None:
            # with the body refit on, the held object follows the hand that was slid inwards and shrank with it:
            # its light must follow too, or a torch would light from where the hand no longer is
            hs_ = float(bd['hand']) if bd is not None else 1.
            hand = hand + bodies.arm_shift(bd, sk, -1 if left else 1)
            for (p_, c_, pw, r_) in il:
                q = Rw @ (R_t @ np.asarray(p_, np.float32) * (s * hs_) + hand * s) + base; lights.append((tuple(float(v) for v in q), c_, pw, r_))
    return out, sk

def face_for(look, sample, mouth_env=0.):
    """24x24 face texture for a sample: expression, mouth while speaking, blink, gaze"""
    # same promotion as in build(), and it has to be here too: this function reads the RAW look, so a premium
    # preset that did not pass through here would draw a premium body under a 24x24 V2 face. Identity (the
    # very same object) without the key.
    look = bodies.promoted(look)
    kind = sample.get('face', 'neutral')
    if kind not in A.FACE_KINDS: kind = 'neutral'
    mouth = 0.
    if sample.get('talking'):
        mouth = int(mouth_env * 4) / 4.
        if kind == 'neutral': kind = 'talk'
    gl = look.get('glasses'); gl = gl if gl in (True, 'glasses', 'round', 'sun', 'sunglasses') else None
    # eye aim (opt-in, episode key "eye_aim"): the pupils carry the part of the aim the neck could not. None
    # without the key, and then every painter below is called exactly as it was before this lot.
    eye = EY.offset(sample, 48), EY.offset(sample, 24)
    bd = look.get('beard'); bd = bd if bd in (True, 'full', 'beard', 'mustache', 'stubble') else None
    # Two 48x48 faces now live side by side, both opt-in, both off by default: the expressive face of lot 3
    # (character key "face_detail": "hd", assets.face_tex_hd) and the parametric face of the art direction
    # (episode key "art", art.face_hd). The character key is tested first because the narrower scope wins over
    # the episode-wide one, as everywhere else in this DSL -- a mechanical rule, NOT an artistic verdict: which
    # of the two becomes the style is still the owner's call. An episode that asks for both is told so in
    # French by art.notices(), never left to guess. docs/RAPPORT_INTEGRATION_ART_OPTIN_20261024.md
    if look.get('face_detail') == 'hd':      # opt-in 48x48 expressive face (brows, iris, cheeks); V2 looks untouched
        return A.face_tex_hd(kind, mouth, .0, skin=tuple(look.get('skin', A.SKIN)), hair=tuple(look.get('hair', A.HAIR)), gaze=sample.get('gaze'),
                             glasses=gl, beard=bd, bald=look.get('hair_style') == 'bald', blink=bool(sample.get('blink')) and kind not in ('closed', 'sleeping'),
                             iris=tuple(look.get('iris', (96, 62, 44))), fringe=look.get('hair_style') not in P.STRAND_STYLES,
                             lips=tuple(look['lips']) if look.get('lips') else None, eye=eye[0])
    if art.on('face'):                                      # art v2, opt-in: 48x48 parametric face
        return art.face_hd(kind, mouth, tuple(look.get('skin', A.SKIN)), tuple(look.get('hair', A.HAIR)), sample.get('gaze'),
                           gl, bd, look.get('hair_style') == 'bald',
                           bool(sample.get('blink')) and kind not in ('closed', 'sleeping'),
                           tuple(look['eyes']) if look.get('eyes') else None)
    return A.face_tex(kind, mouth, .8, .0, skin=tuple(look.get('skin', A.SKIN)), hair=tuple(look.get('hair', A.HAIR)), gaze=sample.get('gaze'),
                      glasses=gl, beard=bd, bald=look.get('hair_style') == 'bald', blink=bool(sample.get('blink')) and kind not in ('closed', 'sleeping'),
                      eye=eye[1])
