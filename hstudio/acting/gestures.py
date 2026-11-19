"""Gesture vocabulary shared by both engines: arm poses as (elbow, hand) offsets from the shoulder, the gestures that
combine them, and their small animations. Used by pixel3d/poses.py (original figures) and acting/rig.py (skeleton)."""
import math

# (elbow, hand) offsets from the shoulder, in (lat, up, fwd); lat > 0 = away from the body
ARM_POSES = {
    'down':      ((0., -.29, 0.), (0., -.60, 0.)),
    'up':        ((.02, .27, .02), (.04, .53, .04)),
    'forward':   ((0., -.04, .28), (0., -.05, .55)),
    'side':      ((.28, 0., 0.), (.56, .0, 0.)),
    'hip':       ((.17, -.21, -.03), (-.03, -.42, .07)),
    'chest':     ((.02, -.27, .10), (-.22, -.17, .21)),
    'belly':     ((.03, -.28, .08), (-.27, -.36, .18)),
    'head':      ((.20, .16, .02), (-.15, .48, 0.)),
    'face':      ((.04, -.12, .24), (-.24, .30, .27)),
    'chin':      ((0., -.24, .18), (-.24, .17, .23)),
    'mouth':     ((.10, -.20, .20), (-.25, .17, .25)),
    'ear':       ((.10, -.10, .10), (-.07, .28, .06)),
    'cover_ear': ((.14, -.08, .04), (-.09, .28, 0.)),
    'point':     ((.02, -.02, .28), (.02, -.02, .55)),
    'wave':      ((.20, -.02, .04), (.24, .31, .04)),
    'stop':      ((0., -.04, .26), (0., .10, .50)),
    'fist':      ((.06, .26, .04), (.06, .50, .06)),
    'thumb':     ((.02, -.26, .10), (0., -.21, .33)),
    'cross':     ((.05, -.27, .10), (-.40, -.18, .21)),
    'behind':    ((0., -.27, -.07), (-.18, -.44, -.20)),
    'pocket':    ((.04, -.28, .06), (-.16, -.42, .17)),
    'shrug':     ((.12, -.26, .02), (.32, -.28, .20)),
    'pray':      ((.06, -.26, .12), (-.30, -.10, .24)),
    'hug':       ((.10, -.05, .30), (-.18, -.05, .50)),
    'hold':      ((0., -.28, .07), (-.08, -.30, .30)),
    'hold_up':   ((.02, -.20, .16), (-.06, -.02, .36)),
    'reach':     ((0., .04, .28), (0., .16, .53)),
    'salute':    ((.20, 0., .10), (-.20, .40, .20)),
    'surrender': ((.26, 0., 0.), (.28, .30, 0.)),
    'stretch':   ((.12, .25, 0.), (.22, .50, 0.)),
    'knock':     ((.02, -.10, .26), (.02, .08, .46)),
    'clap':      ((.08, -.20, .20), (-.24, -.10, .34)),
    # 31/10/2026 (clip de bal) : bras tendus sur les côtés à hauteur d'épaule, un peu en avant ; et en V vers le haut
    'wide':      ((.28, .0, .05), (.57, .01, .10)),
    'wide_up':   ((.21, .19, .04), (.41, .41, .08)),
}

# gesture -> (main arm, other arm). Animations are applied in arm_pose().
GESTURES = {
    'wave': ('wave', 'down'), 'point': ('point', 'down'), 'stop': ('stop', 'down'), 'hands_hips': ('hip', 'hip'),
    'cross_arms': ('cross', 'cross'), 'facepalm': ('face', 'down'), 'cover_face': ('face', 'face'), 'think': ('chin', 'belly'),
    'shrug': ('shrug', 'shrug'), 'thumbs_up': ('thumb', 'down'), 'victory': ('fist', 'down'), 'cheer': ('up', 'up'),
    'surrender': ('surrender', 'surrender'), 'stretch': ('stretch', 'stretch'), 'salute': ('salute', 'down'), 'phone': ('ear', 'down'),
    'pray': ('pray', 'pray'), 'hug': ('hug', 'hug'), 'clap': ('clap', 'clap'), 'hands_mouth': ('mouth', 'mouth'),
    'cover_ears': ('cover_ear', 'cover_ear'), 'head_scratch': ('head', 'down'), 'hands_behind': ('behind', 'behind'),
    'pockets': ('pocket', 'pocket'), 'reach': ('reach', 'down'), 'hold': ('hold', 'hold'), 'show': ('hold_up', 'down'),
    'knock': ('knock', 'down'), 'arm_up': ('up', 'down'), 'extend': ('forward', 'down'), 'chest': ('chest', 'down'),
    'hand_chest': ('chest', 'down'), 'dance': ('up', 'side'), 'shiver': ('cross', 'cross'), 'nod': ('down', 'down'),
    'shake_head': ('down', 'down'), 'laugh': ('belly', 'down'), 'idle': ('down', 'down'),
    'arms_wide': ('wide', 'wide'), 'arms_wide_up': ('wide_up', 'wide_up'),
}


def body_motion(gesture, g):
    """(dx, dy, head_dx, head_dy) of the whole body / head for animated gestures"""
    if gesture == 'dance': return .05 * math.sin(g * 5), .04 * abs(math.sin(g * 5)), 0., 0.
    if gesture == 'shiver': return .012 * math.sin(g * 61), 0., .006 * math.sin(g * 47), 0.
    if gesture == 'nod': return 0., 0., 0., -.035 * (.5 + .5 * math.sin(g * 7))
    if gesture == 'shake_head': return 0., 0., .035 * math.sin(g * 9), 0.
    if gesture == 'laugh': return 0., .012 * abs(math.sin(g * 13)), 0., .01 * abs(math.sin(g * 13))
    if gesture == 'cheer': return 0., .03 * abs(math.sin(g * 7)), 0., 0.
    return 0., 0., 0., 0.


def arm_pose(name, side, g, gesture=None, armsw=0.):
    """elbow and hand offsets (lat, up, fwd) for one arm at time g"""
    e, h = ARM_POSES.get(name, ARM_POSES['down'])
    e, h = list(e), list(h)
    if name == 'down' and armsw: h[2] += armsw * side; e[2] += armsw * side * .5        # walking swing
    if gesture == 'wave' and name == 'wave': h[0] += .07 * math.sin(g * 9)
    elif gesture == 'clap': o = .09 * (.5 + .5 * math.sin(g * 11)); h[0] += o; e[0] += o * .5
    elif gesture == 'victory' and name == 'fist': h[1] += .06 * math.sin(g * 8); e[1] += .03 * math.sin(g * 8)
    elif gesture == 'knock' and name == 'knock': h[2] += .05 * max(0., math.sin(g * 12))
    elif gesture == 'cheer': h[1] += .03 * math.sin(g * 7 + side)
    elif gesture == 'dance':
        k = .5 + .5 * math.sin(g * 5 + (0 if side > 0 else math.pi))
        a0, a1 = ARM_POSES['up'], ARM_POSES['side']
        e = [a0[0][i] * k + a1[0][i] * (1 - k) for i in range(3)]; h = [a0[1][i] * k + a1[1][i] * (1 - k) for i in range(3)]
    return e, h
