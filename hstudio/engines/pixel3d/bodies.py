"""PIXEL 3D body proportions -- EXPERIMENTAL, OPT-IN ONLY (episode key "body").

The shipped PIXEL 3D body ("ancien rendu") stays the default and is never touched by this module. Without the
key `active()` returns None, `shape()` is never called, and `rigfig.build` emits exactly the boxes it emitted
before, bit for bit (tools/regress.py, tools/regress_v2.py, tools/check_corps.py).

WHY. A stock PIXEL 3D head is 0.40 m of skull and 0.43 m of hair on a ~1.94 m silhouette: the head blob is
0.46 m tall, i.e. about **4.2 heads of body height**, the proportion of a toy, where the owner's artistic
reference is a ~7-head figure. It is also the mechanical cause of the retreat of `camera_face_track`
(`cinema.HEAD_SHARE`): a close shot asks for 0.60 / 0.66 = 0.91 m of image width for the skull alone, so the
camera backs off and the shot stops being intimate.

`tools/proto_proportions.py` measured, before this module existed, that shrinking the head ALONE fails: the
torso stays 0.50 m wide and the silhouette reads as a block under a small head. The preset `tete_seule` below
is exactly that failing configuration, kept so the report can measure it instead of asserting it.

WHAT IT IS, AND WHAT IT IS NOT. This is a refit of the **rendered volumes** of PIXEL 3D, not a new skeleton:

- the shared skeleton `hstudio/acting/rig.py` is NOT touched. Joint positions, bone lengths, gait phase, the
  two-bone IK and the foot planting are bit-for-bit what they were. That is deliberate: `rig.py` is also the
  skeleton of the CONSOLE 2D engine, and the brief forbids dragging CONSOLE 2D into a 3D refit;
- every change is a scale or a rigid translation applied to the boxes of ONE skeleton frame, inside
  `rigfig.build`'s own `emit`. Bone lengths are preserved by construction: the limb boxes are scaled across
  (local x and z) and never along the bone (local y, the axis of every frame built by `rig.seg_frame`);
- the only new geometry is a neck and two deltoid caps, which the stock body simply has not got -- its torso
  ends at 1.44 m and its head starts at 1.48 m, so there is no neck at all today.

`arm_in` slides each whole arm chain inwards (shoulder, elbow and hand together, a rigid translation, so the
chain stays a chain). The `reach` IK of `rig.py` aims for the hand rig.py computes, NOT for the one the refit
draws: until `aimed()` existed, a hand closing on a door handle landed `arm_in` metres inside it -- the cost
named in docs/P1_CORPS_PROPORTIONS_20261024.md (sec. 5b). `aimed()` cures it by aiming the IK that much
further OUT instead of moving the chain back (which would undo the refit), and the correction is exact rather
than approximate: see its own docstring. `acted.arm_points` goes through the same `solve()`, so the
cinematographer keeps measuring the arms the renderer really draws.

Same discipline for the head: a smaller skull sitting a little higher than its joint is no longer where the
camera used to aim. `head_y()` maps a height anchored on the stock head (1.68 m the joint, 1.70 m the eyes) to
where that point really is, and the PIXEL 3D framing asks it instead of believing a constant. Both corrections
are switchable (`reach_fix`, `head_aim`) so that tools/interaction_qc.py can MEASURE the defect instead of
asserting it, exactly as the preset `tete_seule` keeps the failing prototype measurable.
"""
import numpy as np
from ...acting import rig

_EX = np.array([1., 0., 0.], np.float32)
_EY = np.array([0., 1., 0.], np.float32)

# A preset is read, never guessed. `head` scales the whole head group (skull, hair, hat, headphones) about the
# head joint; `head_lift` then raises the group along the head's own +y so the skull top stays near its former
# height instead of the character losing 10 cm of stature; `neck` is the WIDTH of the new neck block, its
# height being derived from the skull it has to reach (0 = no neck, i.e. the stock body); `torso` / `torso_z`
# narrow the torso across and in depth; `arm` / `hand` / `leg` thin the limbs across the bone; `arm_in` slides
# the arm chains inwards (see the note above).
# `reach_fix` / `head_aim` are not shapes: they are the two coherence corrections of the refit (the reach IK
# aims where the hand is really drawn, the camera aims where the head really is). They are ON in every preset;
# `{"style": "refit", "reach_fix": 0}` restores the measured defect for tools/interaction_qc.py.
# `detail` / `promote` are not shapes either, and they are 0 in every preset but `voxel_premium`: the first
# APPENDS the premium volumes (`hand_extra`, `foot_extra`, `head_extra`, `extras`) to the groups the preset
# already emits, the second fills in the premium look keys the engine already owns (`promoted`). Both are
# switchable one at a time -- `{"style": "voxel_premium", "detail": 0}` is the look alone, `"promote": 0` the
# volumes alone -- so the report can MEASURE which of the two does the work instead of claiming both.
PRESETS = {
    # (deleted 2026-10-31: `refit`, `refit_fort`, `tete_seule` -- the human body with a neck, rejected by
    #  the owner; the measurements stay in docs/P1_CORPS_PROPORTIONS_20261024.md)
    # THE OTHER DIRECTION, and the one the owner's reference images ask for. `refit` above walks AWAY from
    # it: 6.79 heads and a 12.5 cm neck is a human figure, and the references are Minecraft -- a big cubic
    # head sitting straight on the shoulders, no neck at all. The measured surprise is that the SHIPPED body
    # is already nearly there (4.20 heads, no neck), so this preset is a small, measured nudge towards the
    # exact block ratios of the reference and not a refit: head 8x8x8, torso 8 wide x 12 tall x 4 deep,
    # limbs 4 wide, i.e. 4.0 heads, shoulders 0.50 of the height, torso 0.25, head as wide as the torso.
    # `neck` stays 0 on purpose: it is the signature of the look, not an oversight. See tools/corps_qc.py.
    'minecraft': dict(head=1.08, head_lift=0., neck=0., torso=.94, torso_z=.90, arm=1.25, hand=1.15, leg=1.25,
                      arm_in=-.046, reach_fix=1., head_aim=1., detail=0., promote=0.),
    # THE SAME SILHOUETTE, FINISHED. `voxel_premium` inherits the nine shape numbers of `minecraft` to the
    # digit -- short compact body, big cubic head, no neck, thick limbs, shoulders wider than the trunk -- and
    # changes NOTHING about them. What it adds is the two things the owner's reference miniature has and the
    # engine's cube body has not: VOLUME where a block reads as one flat face (a fist with knuckles and a
    # thumb, a shoe with a sole and a toe cap, a square shoulder line, a zip and two pockets), and the premium
    # look keys the engine already owns but nobody switches on (48x48 face with brows and iris, layered cubic
    # hair locks, garment shading). It is a FINISH on the Minecraft body, not a second body: `shape()` only
    # ever APPENDS boxes to the groups `minecraft` already emits, so the silhouette ratios of corps_qc.py move
    # only by what the new volumes really occupy, and `rig.py` still knows nothing about any of it.
    'voxel_premium': dict(head=1.08, head_lift=0., neck=0., torso=.94, torso_z=.90, arm=1.25, hand=1.15, leg=1.25,
                          arm_in=-.046, reach_fix=1., head_aim=1., detail=1., promote=1.),
}
KEYS = tuple(sorted(PRESETS['minecraft']))
_STATE = None

# which skeleton frames belong to which arm (and on which side), and which ones are legs
ARM_FRAMES = {'upperR': 1, 'foreR': 1, 'handR': 1, 'hold': 1, 'upperL': -1, 'foreL': -1, 'handL': -1}
LEG_FRAMES = ('thighR', 'thighL', 'shinR', 'shinL', 'footR', 'footL')


def register(name, **spec):
    """an extension adds its own body preset (registry, not if/elif -- see AGENTS.md)"""
    PRESETS[name] = dict(PRESETS['minecraft'], **{k: v for k, v in spec.items() if k in PRESETS['minecraft']})
    return PRESETS[name]


def configure(spec):
    """`spec` is the episode's `body` key: None / False (off), a preset name, or {"style": name, <overrides>}.
    Returns the resolved preset or None. Called once per engine, exactly like art.configure(ep['art'])."""
    global _STATE
    _STATE = None
    if not spec: return None
    if isinstance(spec, str): name, over = spec, {}
    elif isinstance(spec, dict):
        name = spec.get('style') or spec.get('preset') or 'minecraft'
        over = {k: v for k, v in spec.items() if k not in ('style', 'preset')}
    else: return None
    if name not in PRESETS: return None
    st = dict(PRESETS[name])
    for key, v in over.items():
        if key not in st: continue
        # `arm_in` is the only signed one: positive slides the arm chains IN (the human refit), negative
        # slides them OUT (the Minecraft shoulder, wider than the torso). The others are scales and a
        # negative scale would turn a box inside out.
        lo = -1. if key == 'arm_in' else 0.
        try: st[key] = max(lo, min(2., float(v)))
        except (TypeError, ValueError): pass
    st['name'] = name
    _STATE = st
    return st


def use(state):
    """re-assert a resolved preset before rendering (several engines can live in one process, as in art.use)"""
    global _STATE
    _STATE = state
    return state


def active(): return _STATE


def head_scale(): return float(_STATE['head']) if _STATE else 1.0
def head_lift(): return float(_STATE['head_lift']) if _STATE else 0.0

HEAD_JOINT = rig.PELVIS_Y + rig.NECK_UP + rig.HEAD_UP        # 1.68 m: where rig.py keeps the head, refit or not


def head_y(nominal=HEAD_JOINT):
    """a height the PIXEL 3D framing aims at, anchored on the STOCK head (1.68 m its joint, 1.70 m its eyes)
    -> where that point really is once the head is refitted: the group is scaled about the joint by `head` and
    then lifted by `head_lift`, so a point `d` above the joint ends up `head * d` above the lifted joint.

    Without the key (or with `head_aim: 0`) this returns `nominal` unchanged, to the bit -- which is why the
    stock framing cannot move. With `refit` it raises the close-shot aim by 4.5 cm: the refitted eyes sit at
    1.74 m, and a camera still aiming at 1.70 m puts the face that much too high in a 0.62 m frame."""
    if not _STATE or float(_STATE.get('head_aim', 1.)) < .5: return float(nominal)
    return HEAD_JOINT + float(_STATE['head_lift']) + (float(nominal) - HEAD_JOINT) * float(_STATE['head'])


def eye_off(d=.03):
    """how far above the head JOINT the eyes sit, for a head joint read on a SOLVED skeleton (seated, leaning,
    crouching: `head_y` cannot serve there, the joint is not at 1.68 m any more). The stock answer is `d`, the
    offset the cinematographer has always used; the refitted skull is lifted and scaled about its own joint, so
    the offset is lifted too and shrinks with the skull. Exactly `d` without the key."""
    if not _STATE: return float(d)
    k = float(_STATE['head']) if float(_STATE.get('head_aim', 1.)) >= .5 else 1.
    return float(_STATE['head_lift']) + float(d) * k


def notices(ep):
    """what this refit cannot carry, said in French on the render log instead of in silence"""
    if not _STATE: return []
    art = (ep or {}).get('art')
    nm = art if isinstance(art, str) else ((art.get('style') or art.get('preset')) if isinstance(art, dict) else None)
    if nm and nm != 'grade_only':
        return [f'corps "{_STATE["name"]}" : la direction artistique "{nm}" construit ses propres volumes '
                f'(art.figure) et garde ses proportions d\'origine ; la refonte du corps ne s\'y applique pas']
    return []


def _across(boxes, fx, fz):
    """thin a limb ACROSS the bone only: local y is the bone axis in every frame built by rig.seg_frame"""
    if fx == 1.0 and fz == 1.0: return boxes
    for b in boxes:
        b.lo = np.array([b.lo[0] * fx, b.lo[1], b.lo[2] * fz], np.float32)
        b.hi = np.array([b.hi[0] * fx, b.hi[1], b.hi[2] * fz], np.float32)
    return boxes


def _uniform(boxes, f):
    """scale a group about its frame origin: sizes AND offsets (a smaller head carries smaller headphones)"""
    if f == 1.0: return boxes
    for b in boxes: b.lo = b.lo * f; b.hi = b.hi * f
    return boxes


def arm_shift(st, sk, side):
    """rigid inward translation of one WHOLE arm chain, in the character's local frame (zeros when inert).
    The same vector is used by the renderer and by acted.arm_points, so the cinematographer keeps measuring
    the arms it actually sees."""
    if not st or not st.get('arm_in'): return np.zeros(3, np.float32)
    return (-float(side) * float(st['arm_in'])) * (sk.frames['torso'][0] @ _EX)


def aimed(st, params):
    """the rig parameters of one character, with the `reach` IK targets corrected for the inward slide of the
    arms (identity when there is nothing to correct -- no refit, no `arm_in`, no reach, or `reach_fix: 0`).

    WHY. `rig.solve` puts the hand ON the target; `shape()` then slides the whole arm chain `arm_in` inwards,
    so the hand the renderer DRAWS misses the door handle by 6.5 cm. The cure is not to move the chain back
    (that would undo the refit) but to aim the IK that much further out: solve for `target - shift`, draw at
    `+ shift`, and the drawn hand lands on the handle.

    It is EXACT, not an approximation, and for a reason worth writing down: the shift is a rigid translation
    and the torso frame it is built from does not depend on `reach` at all, so the shoulder-to-target distance
    is the same before and after the correction --
    `|(target - shift) - shoulder| == |target - (shoulder + shift)|`. The reach envelope of the chain, and
    therefore the clamp inside `two_bone`, are untouched: a target that was reachable stays reachable, and one
    that was out of range stays out of range by exactly the same margin."""
    rc = (params or {}).get('reach')
    if not st or not rc or not st.get('arm_in') or float(st.get('reach_fix', 1.)) < .5: return params
    sk = rig.solve(params)                       # for the torso frame only: it does not depend on `reach`
    fixed = dict(rc)
    for side, aim in rc.items():
        if not aim or len(aim) < 2 or aim[0] is None: continue
        off = arm_shift(st, sk, side)
        fixed[side] = (tuple(float(aim[0][i]) - float(off[i]) for i in range(3)), aim[1])
    out = dict(params); out['reach'] = fixed
    return out


def solve(params):
    """the skeleton as the PIXEL 3D renderer needs it: `rig.solve`, plus the reach correction above. Every
    consumer of the DRAWN arms goes through here (rigfig.build, acted.arm_points), so the cinematographer and
    the renderer can never read two different hands. Bit-for-bit `rig.solve` without the key."""
    return rig.solve(aimed(_STATE, params) if _STATE else params)


def neck_and_shoulders(st, skin, hood, k):
    """the two volumes the stock body has not got: a neck (its torso ends at 1.44 m, its head starts at
    1.48 m) and two deltoid caps bridging the narrowed torso back to the shoulder joints, which rig.py keeps
    at +/- 0.32 m. Built AFTER the torso is narrowed, in the torso frame, in the same
    `yb + <nominal world height>` convention as rigfig.build and art._torso_v2.

    The neck is not given a height: it is DERIVED, from the torso top up to just inside the shrunken skull, so
    that it can never leave a gap nor poke through the face whatever `head` and `head_lift` are set to. Its
    lower part is covered by the garment's own collar, exactly as a real one is."""
    from .r3d import C, M_FABRIC
    w = float(st.get('neck', 0.))               # neck width in metres; 0 = no neck, i.e. the stock body
    if w <= 0: return []
    yb = -rig.PELVIS_Y
    head_c = rig.PELVIS_Y + rig.NECK_UP + rig.HEAD_UP + float(st['head_lift'])     # where the skull now sits
    top = head_c - .20 * float(st['head']) + .03                                   # 3 cm inside it, never a gap
    bot = 1.40                                                                     # inside the torso volume
    out = [C((0, yb + (top + bot) / 2, -.01), (w, max(.04, top - bot), w * .92), skin, **k),
           # a collar: without it the derived neck reads as a bare pale column, measured on the first renders
           C((0, yb + 1.465, .005), (w * 1.55, .075, w * 1.50), tuple(int(c * .82) for c in hood), mat=M_FABRIC, **k)]
    dx = (rig.SHOULDER_X - float(st.get('arm_in', 0.))) * .80
    cap = .105 * float(st.get('arm', 1.)) + .025
    for sd in (-1, 1):                          # deltoid caps: bridge the narrowed torso back to the shoulder
        out.append(C((sd * dx, yb + 1.355, 0), (cap, .165, .20 * float(st.get('torso_z', 1.)) + .04),
                     hood, mat=M_FABRIC, **k))
    return out


# ---------------------------------------------------------------------------------------------------
# THE PREMIUM FINISH OF THE CUBE BODY (`detail: 1`, i.e. the preset `voxel_premium` and nothing else).
#
# WHY VOLUMES AND NOT A TEXTURE. The reference miniature is not a flat cube character: its hand is a
# geometric fist with knuckles and a thumb closing on a bar, its shoe has a sole, its shoulder line is a
# square step and its garment has edges that catch the light. The engine draws boxes and shades them per
# face, so a face that is not THERE cannot catch light whatever the texture says -- the stock hand is ONE
# 12 cm cube, and no shading makes one cube read as a fist. Each function below is a handful of boxes and
# nothing more; none of them touches a bone, a joint, a frame or a scale.
#
# WHERE EACH ONE GOES, AND WHY IT MATTERS. `hand_extra` / `foot_extra` / `head_extra` are APPENDED to the
# group they belong to, BEFORE that group is scaled, so they shrink and swing with the limb and the grip
# stays the grip (the IK target is the hand frame origin, which none of them moves). `extras` is a group of
# its OWN ("voxel") on the torso frame, so it is NOT scaled by `torso`/`torso_z` -- its numbers are the
# final width of the trunk -- and so the silhouette tools keep reading a trunk, a neck and two arms exactly
# where they read them before.
def _tones(c):
    """(base, lit, shaded) of one colour -- the three tones the layered cubic look is built on"""
    from .poses import _tone
    return tuple(c), _tone(tuple(c), .16), _tone(tuple(c), -.26)


def hand_extra(st, L, k, side):
    """a FIST instead of a cube: palm (already there) + knuckle row + thumb + sleeve cuff. 3 boxes.

    Local frame of a hand (rig.seg_frame): -y runs on down the forearm (so the fingers are BELOW the wrist
    joint), +z is the character's forward, +x is their right. The knuckles therefore sit low and a little
    forward, and the thumb inwards and forward -- `side` is +1 for the right chain, -1 for the left, the
    same convention as ARM_FRAMES, so one formula serves both hands and they stay mirror images.

    The hand JOINT is the frame origin and nothing here moves it: `reach` still lands the wrist on the door
    handle to the millionth (tools/interaction_qc.py), and the fist closes just under and in front of it,
    which is where a fist that grips a bar really is."""
    from .r3d import C, M_FABRIC
    sl = L['hood'] if L['outfit'] not in ('tshirt', 'dress') else L['skin']
    base, lit, dark = _tones(L['skin'])
    return [C((0, -.082, .016), (.116, .050, .106), dark, **k),                          # knuckles: the gripping edge
            C((-side * .052, -.040, .048), (.046, .072, .056), lit, **k),                # thumb, inwards and forward
            C((0, .048, 0), (.140, .044, .144), _tones(sl)[2], mat=M_FABRIC, **k)]       # sleeve cuff


def foot_extra(st, L, k):
    """a SHOE instead of a block: a sole and a raised toe cap. 2 boxes.

    The sole is built as `C((0, h / 2, ...), (..., h, ...))` on purpose: its underside is then at exactly
    y = 0 in the foot frame, the same height as the stock shoe, so `tools/corps_qc.py`'s `pied` measure and
    the foot planting of `rig.py` are untouched to the bit. `shape()` scales a foot across the bone only
    (x, and z by `leg * .92 + .08`), never in y, so that stays true at any `leg`."""
    from .r3d import C
    h = .032
    return [C((0, h / 2, .035), (.206, h, .286), (20, 19, 21), **k),                     # sole, underside at y=0
            C((0, .062, .148), (.166, .062, .056), (44, 42, 46), **k)]                   # toe cap


def head_extra(st, L, k):
    """two ears, and only when nothing covers them. 2 boxes, 0 under a hood / beanie / helmet / headphones.

    Deliberately NOT a brow ridge: a block in front of the forehead is where the staged fringe of
    `poses.hair_strands` and the eye blocks already live, and the brows the reference asks for are painted
    by the 48x48 face (`assets.face_tex_hd`, switched on by `promoted`) where they cannot hide an eye.
    Nothing here is taller or lower than the skull, so the `tetes` ratio of corps_qc.py cannot move."""
    from .r3d import C
    if L.get('hat') in ('hood', 'beanie', 'helmet', 'astronaut') or (L.get('headphones') and L.get('headphones') != 'cou'): return []
    base, lit, dark = _tones(L['skin'])
    return [C((sd * .202, -.012, -.012), (.038, .082, .072), dark if sd < 0 else base, **k) for sd in (-1, 1)]


def extras(st, L, k):
    """the garment volumes, in a group of their own on the torso frame: a square shoulder step, a zip
    placket and two pockets. 5 boxes, and 0 without `detail`.

    These are the only numbers of this module expressed in FINAL metres rather than nominal ones, because
    this group is not scaled by `torso` / `torso_z`: the trunk of `voxel_premium` is .50 * .94 = .470 wide
    and .28 * .90 = .252 deep, so the front face is at z = .126 and everything that must sit on it is a
    couple of millimetres in front, never coplanar (a raycaster shows coplanar faces as noise)."""
    from .r3d import C, M_FABRIC
    if not float(st.get('detail', 0.)): return []
    yb = -rig.PELVIS_Y
    base, lit, dark = _tones(L['hood'])
    ac = tuple(L['accent']) if L.get('accent') else dark
    out = []
    for sd in (-1, 1):                     # the square shoulder step of the reference, over a narrowed trunk
        out.append(C((sd * .276, yb + 1.372, 0), (.142, .086, .262), lit, mat=M_FABRIC, **k))
    # a zip and two patch pockets belong on a street garment and nowhere else: on a dress, a robe, armour or
    # a spacesuit they would read as a mistake, so those get a waist band and a chest seam instead. The
    # shoulder step above is universal -- it is the square shoulder line of the reference, not a garment.
    if L['outfit'] in ('hoodie', 'coat', 'tshirt', 'shirt', 'uniform', 'apron', 'lab_coat'):
        out.append(C((0, yb + 1.13, .136), (.034, .430, .014), ac, **k))                 # zip placket
        for sd in (-1, 1):                                                               # two patch pockets
            out.append(C((sd * .118, yb + .935, .134), (.142, .098, .012), dark, **k))
    else:
        out.append(C((0, yb + .905, 0), (.478, .062, .258), ac, mat=M_FABRIC, **k))      # waist band
        out.append(C((0, yb + 1.19, .133), (.062, .340, .012), lit, **k))                # chest seam
    return out


# which hair style of the V2 look has a layered cubic twin, and which one it is. A style with no twin
# (bun, spiky, curly, bald) is LEFT ALONE: promoting it would change the character's haircut, which is the
# owner's artistic choice and not a finish.
_HAIR_PREMIUM = {None: 'strands', 'short': 'strands', 'long': 'strands_long', 'ponytail': 'strands_ponytail'}


def promoted(look):
    """the character look a premium preset asks for -> the SAME look with the premium keys the engine already
    owns filled IN WHERE THE SCENE LEFT THEM EMPTY. Identity (the very same object) without the key, without
    `promote`, or for a look that already sets them -- so a scene that chose its own face or hair keeps it.

    None of these keys is new: `face_detail: "hd"` (assets.face_tex_hd, 48x48 -- brows, iris with a highlight,
    nuanced cheeks, emotional mouth), the three `strands*` hair styles (poses.hair_strands, layered cubic
    locks in three tones) and `detail: true` (poses.outfit_detail) all shipped in earlier lots and all were
    reachable only by writing them out character by character, as library/characters/lea_hd.json does. What
    `voxel_premium` adds is that ONE episode key now dresses the whole cast, which is the difference between
    an option that exists and an option the owner can judge on a video."""
    st = _STATE
    if not st or not float(st.get('promote', 0.)) or not isinstance(look, dict): return look
    out = dict(look)
    out.setdefault('face_detail', 'hd')
    out.setdefault('detail', True)
    hs = out.get('hair_style')
    if out.get('hair_long') and hs is None: out['hair_style'] = 'strands_long'
    elif hs in _HAIR_PREMIUM: out['hair_style'] = _HAIR_PREMIUM[hs]
    if 'hair2' not in out:
        from .poses import _tone
        from . import assets as _A
        out['hair2'] = _tone(tuple(out.get('hair', _A.HAIR)), .30)       # the lit tone of the upper locks
    return out


def shape(st, name, boxes, o, R, sk, L, k):
    """-> (boxes, frame origin) for ONE emitted skeleton group. The only entry point of this module into the
    renderer; `name` is the name of the skeleton frame the group came from (rigfig._part_of)."""
    o = np.asarray(o, np.float32)
    # the premium volumes are APPENDED to the group BEFORE it is scaled, so a fist shrinks with the hand it
    # belongs to and a sole with the foot. `fine` is 0 in every preset but `voxel_premium`.
    fine = float(st.get('detail', 0.))
    if name == 'head':
        if fine: boxes = boxes + head_extra(st, L, k)
        _uniform(boxes, float(st['head']))
        lift = float(st['head_lift'])
        return boxes, (o + R @ (_EY * lift) if lift else o)
    if name == 'torso':
        _across(boxes, float(st['torso']), float(st['torso_z']))
        return boxes, o
    if name in ARM_FRAMES:
        if name == 'hold' or name.startswith('hand'):
            # `hold` is the HELD OBJECT in the hand frame, not the hand: it must scale with the hand and
            # must not grow a second fist.
            if fine and name.startswith('hand'): boxes = boxes + hand_extra(st, L, k, ARM_FRAMES[name])
            _uniform(boxes, float(st['hand']))
        else: _across(boxes, float(st['arm']), float(st['arm']))
        return boxes, o + arm_shift(st, sk, ARM_FRAMES[name])
    if name in LEG_FRAMES:
        f = float(st['leg'])
        if fine and name.startswith('foot'): boxes = boxes + foot_extra(st, L, k)
        _across(boxes, f, f if not name.startswith('foot') else f * .92 + .08)   # a shoe keeps most of its length
        return boxes, o
    return boxes, o
