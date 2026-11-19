"""Shared skeleton and procedural body animation (used by both engines).

Local frame of a character: origin on the floor between the feet, +y up, +z the way it faces, +x its "main" side
(the side of the main arm in gestures.ARM_POSES). solve() turns a few animation parameters into joint positions and
limb frames; pixel3d builds rotated boxes from the frames, the console engine draws flat shapes from the joints.

Techniques (cheap and deterministic):
- walk / run: the gait phase advances with the distance travelled (not with time), the stance foot moves backwards
  exactly as fast as the body moves forwards -> feet stay planted at any speed, including while accelerating;
- legs and arms: two-bone inverse kinematics (feet on the floor, hands on a target), lengths always preserved;
- sitting / crouching: the pelvis moves to the seat while the feet stay planted, the knees follow from the IK and the
  torso leans forward during the transition;
- layers: rest pose < walk swing < gestures (weighted blend) < reach IK; plus breathing, idle sway, emotion posture
  and head look (yaw / pitch relative to the torso)."""
import math, numpy as np
from .gestures import arm_pose

PELVIS_Y, HIP_X, THIGH, SHIN, ANKLE_Y = .80, .11, .38, .36, .06
SHOULDER_Y, SHOULDER_X, UPPER, FORE = 1.40, .32, .29, .31
NECK_UP, HEAD_UP = .66, .22                     # neck above the pelvis, head centre above the neck
LEG = THIGH + SHIN

def rot_x(a):
    c, s = math.cos(a), math.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], np.float32)      # + : top towards +z
def rot_y(a):
    c, s = math.cos(a), math.sin(a); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], np.float32)      # + : +z towards +x
def rot_z(a):
    c, s = math.cos(a), math.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float32)
def smooth(x): x = min(1., max(0., x)); return x * x * (3 - 2 * x)
def V(*a): return np.array(a, np.float32)

def seg_frame(p0, p1, fwd=(0., 0., 1.)):
    """rotation whose local -y points from p0 to p1, local +z as close as possible to fwd"""
    d = np.asarray(p1, np.float32) - np.asarray(p0, np.float32); n = float(np.linalg.norm(d))
    y = -d / n if n > 1e-6 else V(0, 1, 0)
    z = np.asarray(fwd, np.float32); z = z - y * float(z @ y)
    if np.linalg.norm(z) < 1e-4: z = V(0, 1, 0) - y * float(y[1]); z = z if np.linalg.norm(z) > 1e-4 else V(1, 0, 0)
    z = z / np.linalg.norm(z); x = np.cross(y, z)
    return np.stack([x, y, z], 1).astype(np.float32)

def two_bone(root, target, l1, l2, pole):
    """middle joint of a two-bone chain reaching target (clamped to reach), bending towards pole"""
    root = np.asarray(root, np.float32); t = np.asarray(target, np.float32) - root
    d = float(np.linalg.norm(t)); d = min(max(d, abs(l1 - l2) + 1e-3), l1 + l2 - 1e-3)
    tn = t / (float(np.linalg.norm(t)) + 1e-9)
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d); h = math.sqrt(max(0., l1 * l1 - a * a))
    p = np.asarray(pole, np.float32) - tn * float(np.asarray(pole, np.float32) @ tn)
    p = p / (float(np.linalg.norm(p)) + 1e-9)
    mid = root + tn * a + p * h
    end = root + tn * d
    return mid, end

def foot_cycle(psi, beta, S, lift):
    """foot (z forward, y up) relative to the hip during a gait cycle; psi in radians, beta = stance share"""
    p = (psi / (2 * math.pi)) % 1.
    if p < beta: return beta * S * (.5 - p / beta), 0.
    q = (p - beta) / (1 - beta); e = q * q * (3 - 2 * q)
    return -beta * S / 2 + beta * S * e, lift * math.sin(math.pi * q)

def stride_for(speed):
    return min(2.4, max(.7, .55 + .62 * speed))

def stance_beta(run): return .62 - .27 * run

class Skeleton:
    __slots__ = ('joints', 'frames', 'seated')
    def __init__(s): s.joints = {}; s.frames = {}; s.seated = 0.

def solve(p):
    """p: dict with optional keys
    t, seed                 time (s) and per-character seed for breathing / sway
    phase, gait, run, stride  gait phase (rad), walk weight 0..1, run 0..1, stride (m per cycle)
    sit, seat_h, seat_z     0..1 seated, seat height, seat position behind the feet; crouch 0..1
    gestures                [(name, weight, local_time)]; reach {+1|-1: ((x,y,z) local, weight)}
    head                    (yaw, pitch) relative to the torso (rad, + = towards +x / up)
    lean, roll              extra torso pitch (+ forward) / roll; slump 0..1, tension 0..1, chest_up 0..1, bounce (m)
    air, air_k, air_style   V3: weight of the air pose 0..1, progress through the flight, leap | tuck | flail | climb
    """
    sk = Skeleton(); J = sk.joints; Fr = sk.frames
    t = float(p.get('t', 0.)); seed = float(p.get('seed', 0.))
    w = float(p.get('gait', 0.)); run = float(p.get('run', 0.)); ph = float(p.get('phase', 0.)); S = float(p.get('stride', 1.25))
    s_sit = float(p.get('sit', 0.)); crouch = float(p.get('crouch', 0.)); tension = float(p.get('tension', 0.))
    slump = float(p.get('slump', 0.)); chest_up = float(p.get('chest_up', 0.))
    beta = stance_beta(run); lift = .07 + .10 * run
    breath = math.sin(t * 2 * math.pi / 3.6 + seed * 1.3)
    idle = (1 - w) * (1 - max(s_sit, crouch))
    sway = .012 * math.sin(t * 2 * math.pi / 6.5 + seed) * idle
    # feet (planted, or following the gait cycle)
    feet = {}
    for side, off in ((1, 0.), (-1, math.pi)):
        z, y = foot_cycle(ph + off, beta, S, lift)
        iz = .035 * side
        feet[side] = V(side * (HIP_X - .015 * w), w * y, w * z + (1 - w) * iz)
    air = float(p.get('air', 0.)); air_k = float(p.get('air_k', .5)); air_style = p.get('air_style', 'leap')
    if air > 0:                                   # V3, in the air (acting/motion.py): legs split, tucked or kicking
        for side in (1, -1):
            if air_style == 'leap': tgt = V(side * HIP_X, .30 + .08 * math.sin(math.pi * air_k), .30) if side > 0 else V(side * HIP_X, .22, -.56)
            elif air_style == 'flail': q = t * 11 + side * 1.7; tgt = V(side * (HIP_X + .05), .22 + .1 * math.sin(q), .18 * math.sin(q + 1.))
            elif air_style == 'climb': tgt = V(side * HIP_X, .42, -.05)
            else: tgt = V(side * HIP_X, .40 + .05 * math.sin(math.pi * air_k), .12)
            feet[side] = feet[side] * (1 - air) + tgt * air
    # pelvis: lowest constraint of the legs on the floor, then seat / crouch / bounce
    py = PELVIS_Y
    for side in (1, -1):
        f = feet[side]; dz = float(f[2]); reach = LEG - .006
        py = min(py, math.sqrt(max(reach * reach - dz * dz, 0.)) + ANKLE_Y + float(f[1]))
    py -= .025 * run + .04 * tension * idle
    pz = 0.
    if s_sit > 0:
        e = smooth(s_sit); py = py + (float(p.get('seat_h', .47)) - py) * e; pz = float(p.get('seat_z', -.30)) * e
        for side in (1, -1): feet[side][2] = feet[side][2] + (.10 - feet[side][2]) * e      # feet slide a little forward
    if crouch > 0:
        e = smooth(crouch); py = py + (.46 - py) * e; pz = pz + (-.08 - pz) * e
    # 31/10/2026, scène dirigée (clés `kneel`, `sit_floor`) : à genoux (cuisses droites, tibias à plat derrière) ; assis par terre, jambes repliées
    # sur le côté. Absentes ou nulles : rien de ce qui suit n'est lu, le squelette est celui d'avant au bit près.
    kneel = float(p.get('kneel', 0.) or 0.); sitf = float(p.get('sit_floor', 0.) or 0.)
    if kneel > 0:
        e = smooth(kneel); py = py + (THIGH + .05 - py) * e
        for side in (1, -1): feet[side] = feet[side] * (1 - e) + V(side * HIP_X, 0., -SHIN - .02) * e
    if sitf > 0:
        e = smooth(sitf); py = py + (.13 - py) * e
        for side, tgt in ((1, V(.36, 0., -.12)), (-1, V(.27, 0., .14))): feet[side] = feet[side] * (1 - e) + tgt * e
    py += float(p.get('bounce', 0.)) + .003 * breath * idle
    pel = V(sway, py, pz); J['pelvis'] = pel
    # torso
    transit = math.sin(math.pi * min(1., s_sit)) if 0 < s_sit < 1 else 0.
    lean = float(p.get('lean', 0.)) + .18 * run + .03 * w + .16 * slump - .07 * chest_up + .50 * transit + .40 * smooth(crouch) - .06 * smooth(s_sit) * (1 - transit)
    roll = float(p.get('roll', 0.)) + .03 * w * math.sin(ph)
    if sitf > 0: lean -= .06 * smooth(sitf); roll -= .12 * smooth(sitf)
    Rt = rot_x(lean) @ rot_z(roll)
    Fr['torso'] = (Rt, pel)
    J['chest'] = pel + Rt @ V(0, .32, 0)
    neck = pel + Rt @ V(0, NECK_UP + .004 * breath, 0); J['neck'] = neck
    hy, hp = p.get('head', (0., 0.))
    hp = float(hp) - .30 * slump + .06 * chest_up
    Rh = Rt @ rot_y(float(hy)) @ rot_x(-hp)
    J['head'] = neck + Rh @ V(0, HEAD_UP, 0); Fr['head'] = (Rh, J['head'])
    # arms: rest < walk swing < gestures < reach
    gests = [g_ for g_ in (p.get('gestures') or []) if g_[1] > 1e-3]
    tot = min(1., sum(g_[1] for g_ in gests))
    for side in (1, -1):
        tag = 'R' if side > 0 else 'L'
        sh = pel + Rt @ V(side * (SHOULDER_X - .02 * tension), SHOULDER_Y - PELVIS_Y + .006 * breath + .03 * tension - .03 * slump, 0)
        if run > .01:
            re = V(.02, -.26, -.03 + .0 * run); rh = V(.04, -.30 + .06 * run, .22 * run)
        else:
            re = V(.03, -.29, -.01); rh = V(.05, -.59, .03)
        sw = -.62 * float(feet[side][2]) * w
        rest_e = re + V(0, 0, sw * .5); rest_h = rh + V(0, abs(sw) * .12, sw)
        if tension: rest_e = rest_e * (1 - .3 * tension) + V(0, -.20, .10) * .3 * tension; rest_h = rest_h * (1 - .3 * tension) + V(-.10, -.25, .22) * .3 * tension
        if air > 0 and air_style != 'climb':      # arms balance the jump (opposite to the legs), wave in a fall
            if air_style == 'flail': ae, ah = V(.24, .04, .05), V(.36, .28 + .12 * math.sin(t * 13 + side * 2.1), .08)
            elif air_style == 'tuck': ae, ah = V(.10, -.22, .16), V(.08, -.30, .40)
            elif side > 0: ae, ah = V(.14, -.12, -.12), V(.18, -.05, -.32)
            else: ae, ah = V(.12, -.10, .16), V(.10, .10, .42)
            rest_e = rest_e * (1 - air) + ae * air; rest_h = rest_h * (1 - air) + ah * air
        e_l = rest_e * (1 - tot); h_l = rest_h * (1 - tot)
        for name, wt, lt in gests:
            e_, h_ = arm_pose(GESTURE_ARM(name, -side if p.get('left') else side), side, lt, name, 0.)      # `left` : le geste est joué en miroir (bras gauche)
            e_l = e_l + V(*e_) * (wt / max(tot, 1.) if tot > 1 else wt); h_l = h_l + V(*h_) * (wt / max(tot, 1.) if tot > 1 else wt)
        to_l = lambda o: Rt @ V(side * float(o[0]), float(o[1]), float(o[2]))
        el = sh + to_l(e_l); ha = sh + to_l(h_l)
        el = sh + (el - sh) * (UPPER / (float(np.linalg.norm(el - sh)) + 1e-9)); ha = el + (ha - el) * (FORE / (float(np.linalg.norm(ha - el)) + 1e-9))
        rc = (p.get('reach') or {}).get(side)
        if rc and rc[1] > 1e-3:
            tgt, wr = np.asarray(rc[0], np.float32), smooth(rc[1])
            mid, end = two_bone(sh, tgt, UPPER, FORE, V(side * .5, -1., -.35))
            el = el + (mid - el) * wr; ha = ha + (end - ha) * wr
            el = sh + (el - sh) * (UPPER / (float(np.linalg.norm(el - sh)) + 1e-9)); ha = el + (ha - el) * (FORE / (float(np.linalg.norm(ha - el)) + 1e-9))
        J['sh' + tag], J['el' + tag], J['ha' + tag] = sh, el, ha
        fwd = Rt @ V(0, 0, 1)
        Fr['upper' + tag] = (seg_frame(sh, el, fwd), sh); Fr['fore' + tag] = (seg_frame(el, ha, fwd), el); Fr['hand' + tag] = (Fr['fore' + tag][0], ha)
    # legs: hips -> ankles by IK, knees forward
    for side in (1, -1):
        tag = 'R' if side > 0 else 'L'
        hip = pel + V(side * HIP_X, 0, 0)
        ank = feet[side] + V(0, ANKLE_Y, 0)
        if s_sit > .02 or crouch > .02 or kneel > .02 or sitf > .02 or float(np.linalg.norm(ank - hip)) < LEG - .002:
            kn, ank2 = two_bone(hip, ank, THIGH, SHIN, V(0, 0, 1))
        else:                                                 # straight leg (avoid a degenerate IK)
            d = (ank - hip) / (float(np.linalg.norm(ank - hip)) + 1e-9); kn = hip + d * THIGH; ank2 = kn + d * SHIN
        J['hip' + tag], J['kn' + tag], J['an' + tag] = hip, kn, ank2
        Fr['thigh' + tag] = (seg_frame(hip, kn), hip); Fr['shin' + tag] = (seg_frame(kn, ank2), kn)
        lifted = float(feet[side][1])
        Fr['foot' + tag] = (rot_x(-2.2 * lifted), V(float(ank2[0]), float(ank2[1]) - ANKLE_Y, float(ank2[2])))
        if kneel > 0: Fr['foot' + tag] = (rot_x(math.pi * smooth(kneel)), Fr['foot' + tag][1])              # à genoux : plante vers le haut, orteils vers l'arrière
    sk.seated = smooth(s_sit)
    return sk

def GESTURE_ARM(name, side):
    from .gestures import GESTURES
    main, other = GESTURES.get(name, ('down', 'down'))
    return main if side > 0 else other
