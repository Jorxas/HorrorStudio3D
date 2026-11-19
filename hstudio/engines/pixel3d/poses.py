"""Body language for the blocky characters: articulated arms (shoulder -> elbow -> hand drawn as a staircase of
axis-aligned blocks, which keeps the pixel-art look), animated gestures, postures (sit, kneel, crouch, jump, lie),
objects held in the hand, and looks (outfits, hair styles, hats).

Local frame of a character: lat = towards its main-arm side, up = +y, fwd = the way it faces.
World: x = cx + lat * f, z = cz + fwd * f (f = +1 facing +z, -1 facing -z)."""
import math
import numpy as np
from .r3d import C, Box, M_FABRIC, M_METAL, M_WOODV, FACES

SHOULDER_Y, SHOULDER_X = 1.40, .32

from ...acting.gestures import ARM_POSES, GESTURES, body_motion, arm_pose

POSTURES = ('stand', 'sit', 'kneel', 'crouch', 'jump', 'lie')
HOLD_ITEMS = ('phone', 'cup', 'book', 'flashlight', 'candle', 'key', 'letter', 'flower', 'gift', 'sword', 'ball', 'bag',
              'umbrella', 'balloon', 'microphone', 'staff', 'wand', 'torch', 'shield', 'map', 'guitar', 'bottle', 'apple', 'camera', 'ice_cream', 'newspaper')
OUTFITS = ('hoodie', 'tshirt', 'shirt', 'suit', 'dress', 'coat', 'armor', 'robe', 'apron', 'lab_coat', 'uniform', 'spacesuit')
HAIR_STYLES = ('short', 'long', 'ponytail', 'bun', 'spiky', 'curly', 'bald',
               'strands', 'strands_long', 'strands_ponytail')      # real locks: layered cubic strands (opt-in look)
STRAND_STYLES = ('strands', 'strands_long', 'strands_ponytail')
HATS = ('none', 'cap', 'beanie', 'hood', 'tophat', 'crown', 'wizard', 'witch', 'pirate', 'chef', 'police', 'helmet', 'astronaut', 'cowboy', 'party', 'antenna')


def _seg(p0, p1, size, col, k, mat=0):
    """thick segment from p0 to p1 as one box (axis-aligned) or a staircase of blocks (pixel-art diagonal)"""
    p0 = np.asarray(p0, np.float32); p1 = np.asarray(p1, np.float32); d = p1 - p0; L = float(np.linalg.norm(d))
    if L < 1e-4: return [C(tuple(p0), size, col, mat=mat, **k)]
    nz = np.abs(d) > 1e-4
    if nz.sum() == 1:
        ax = int(np.argmax(nz)); sz = list(size); sz[ax] = abs(float(d[ax])) + size[ax]
        return [C(tuple((p0 + p1) / 2), tuple(sz), col, mat=mat, **k)]
    n = max(1, int(math.ceil(L / (min(size) * .55))))
    return [C(tuple(p0 + d * (i / n)), size, col, mat=mat, **k) for i in range(n + 1)]


def arms(cx, cz, f, yb, g, gesture, sleeve, fore, skin, k, armsw=0., outfit=None):
    """both arms for a gesture. Returns (boxes, main-hand world position)"""
    main, other = GESTURES.get(gesture or 'idle', ('down', 'down'))
    bx = []; hand_main = None
    for side, pose in ((1, main), (-1, other)):
        e, h = arm_pose(pose, side, g, gesture, armsw)
        sh = (cx + side * SHOULDER_X * f, yb + SHOULDER_Y, cz)
        W = lambda o: (sh[0] + side * o[0] * f, sh[1] + o[1], sh[2] + o[2] * f)
        pe, ph = W(e), W(h)
        # the arm of the far side sits a little behind so crossed arms do not z-fight
        if pose == 'cross' and side < 0: ph = (ph[0], ph[1] - .05, ph[2] - .03 * f)
        bx += _seg(sh, pe, (.13, .14, .14), sleeve, k, M_FABRIC)
        bx += _seg(pe, ph, (.12, .13, .13), fore, k, 0 if fore == skin else M_FABRIC)
        hand = (.12, .12, .12)
        if pose in ('wave', 'stop', 'surrender'): hand = (.12, .15, .05)
        elif pose == 'mouth': hand = (.10, .09, .08)
        bx.append(C(ph, hand, skin, **k))
        if pose == 'point': bx.append(C((ph[0], ph[1], ph[2] + .09 * f), (.03, .03, .1), skin, **k))
        if pose == 'thumb': bx.append(C((ph[0], ph[1] + .09, ph[2]), (.035, .08, .035), skin, **k))
        if side == 1: hand_main = ph
    return bx, hand_main


def legs(cx, cz, f, yoff, posture, swing, jeans, shoes, skin, k, outfit=None, g=0.):
    """legs for a posture. Returns (boxes, vertical offset of the upper body)"""
    bx = []; low = skin if outfit == 'dress' else jeans
    if posture == 'sit':                      # seat at .47 m: put a chair / sofa / bench under the actor
        hy = yoff + .47
        for s in (-1, 1):
            x = cx + s * .11
            bx.append(C((x, hy, cz + .20 * f), (.18, .17, .46), jeans if outfit != 'dress' else skin, mat=M_FABRIC, **k))
            bx.append(C((x, hy / 2 + yoff / 2, cz + .40 * f), (.17, hy - yoff, .18), low, mat=M_FABRIC, **k))
            bx.append(C((x, yoff + .04, cz + .45 * f), (.19, .08, .27), shoes, **k))
        if outfit == 'dress': bx.append(C((cx, hy + .02, cz + .16 * f), (.50, .2, .46), None or jeans, mat=M_FABRIC, **k))
        return bx, -.33
    if posture == 'kneel':                    # right knee on the floor, left foot forward
        bx.append(C((cx - .11, yoff + .47, cz + .18 * f), (.18, .17, .40), low, mat=M_FABRIC, **k))
        bx.append(C((cx - .11, yoff + .23, cz + .36 * f), (.17, .46, .18), low, mat=M_FABRIC, **k))
        bx.append(C((cx - .11, yoff + .04, cz + .42 * f), (.19, .08, .27), shoes, **k))
        bx.append(C((cx + .11, yoff + .30, cz), (.18, .46, .18), low, mat=M_FABRIC, **k))
        bx.append(C((cx + .11, yoff + .08, cz - .22 * f), (.17, .16, .44), low, mat=M_FABRIC, **k))
        return bx, -.30
    if posture == 'crouch':
        for s in (-1, 1):
            x = cx + s * .12
            bx += _seg((x, yoff + .40, cz), (x, yoff + .52, cz + .32 * f), (.18, .17, .17), low, k, M_FABRIC)
            bx += _seg((x, yoff + .52, cz + .32 * f), (x, yoff + .08, cz + .26 * f), (.17, .16, .16), low, k, M_FABRIC)
            bx.append(C((x, yoff + .04, cz + .30 * f), (.19, .08, .27), shoes, **k))
        return bx, -.42
    if posture == 'jump':                     # knees tucked, bouncing
        up = .32 * abs(math.sin(g * 4.2)) + .05
        for s in (-1, 1):
            x = cx + s * .11
            bx += _seg((x, yoff + up + .78, cz), (x, yoff + up + .52, cz + .20 * f), (.18, .17, .18), low, k, M_FABRIC)
            bx += _seg((x, yoff + up + .52, cz + .20 * f), (x, yoff + up + .26, cz - .02 * f), (.17, .16, .17), low, k, M_FABRIC)
            bx.append(C((x, yoff + up + .22, cz + .02 * f), (.19, .08, .27), shoes, **k))
        return bx, up - .02
    # standing / walking (same blocks as the original figure)
    bx.append(C((cx - .11, yoff + .40, cz + swing * f), (.18, .80, .21), low, mat=M_FABRIC, **k))
    bx.append(C((cx + .11, yoff + .40, cz - swing * f), (.18, .80, .21), low, mat=M_FABRIC, **k))
    bx.append(C((cx - .11, yoff + .04, cz + swing * f + .03 * f), (.19, .08, .27), shoes, **k))
    bx.append(C((cx + .11, yoff + .04, cz - swing * f + .03 * f), (.19, .08, .27), shoes, **k))
    return bx, 0.


def torso(cx, cz, f, yb, outfit, top, skin, k, tie=None, shirt=None, apron_color=None):
    """torso of an outfit (the hoodie is drawn by figure() itself, unchanged)"""
    bx = []; dark = tuple(int(c * .75) for c in top)
    if outfit == 'coat':
        bx.append(C((cx, yb + 1.03, cz), (.52, .82, .30), top, mat=M_FABRIC, **k))
        bx.append(C((cx, yb + 1.03, cz + f * .152), (.03, .80, .01), dark, **k))
        for y in (1.25, 1.05, .85): bx.append(C((cx + .05, yb + y, cz + f * .153), (.03, .03, .01), (200, 190, 160), **k))
        bx.append(C((cx, yb + 1.46, cz), (.46, .1, .3), dark, **k))
    elif outfit == 'dress':
        bx.append(C((cx, yb + 1.14, cz), (.46, .60, .26), top, mat=M_FABRIC, **k))
        bx.append(C((cx, yb + .66, cz), (.56, .40, .34), top, mat=M_FABRIC, **k))          # skirt
        bx.append(C((cx, yb + .86, cz + f * .135), (.47, .04, .01), dark, **k))             # belt
    elif outfit == 'robe':                       # long robe down to the ankles (wizard, king)
        bx.append(C((cx, yb + 1.12, cz), (.52, .64, .30), top, mat=M_FABRIC, **k))
        bx.append(C((cx, yb + .48, cz), (.58, .80, .36), top, mat=M_FABRIC, **k))
        bx.append(C((cx, yb + .86, cz + f * .182), (.5, .05, .01), (220, 190, 80), **k))
    elif outfit == 'armor':
        mt = tuple(min(255, int(c * 1.1)) for c in top)
        bx.append(C((cx, yb + 1.12, cz), (.54, .66, .32), mt, mat=M_METAL, **k))
        for s_ in (-1, 1): bx.append(C((cx + s_ * .30, yb + 1.42, cz), (.2, .1, .3), mt, mat=M_METAL, **k))
        bx.append(C((cx, yb + .82, cz), (.56, .08, .34), (90, 60, 40), **k)); bx.append(C((cx, yb + 1.25, cz + f * .162), (.1, .2, .01), (200, 40, 40), **k))
    elif outfit == 'spacesuit':
        bx.append(C((cx, yb + 1.12, cz), (.60, .70, .36), top, mat=M_FABRIC, **k))
        bx.append(C((cx, yb + 1.2, cz + f * .182), (.24, .16, .02), (60, 64, 80), **k))
        for i, col in enumerate(((255, 60, 60), (60, 255, 120), (80, 160, 255))): bx.append(C((cx - .07 + i * .07, yb + 1.2, cz + f * .193), (.04, .04, .01), col, emis=2., **k))
    elif outfit in ('lab_coat', 'apron', 'uniform'):
        inner = tuple(shirt) if shirt else top
        bx.append(C((cx, yb + 1.12, cz), (.50, .64, .28), inner, mat=M_FABRIC, **k))
        if outfit == 'lab_coat':
            for s_ in (-1, 1): bx.append(C((cx + s_ * .16, yb + .98, cz + f * .145), (.18, .92, .01), (240, 242, 244), mat=M_FABRIC, **k))
            bx.append(C((cx, yb + .98, cz - f * .145), (.5, .92, .01), (240, 242, 244), mat=M_FABRIC, **k))
        elif outfit == 'apron':
            ac=tuple(apron_color) if apron_color is not None else (246,246,242)
            pc=tuple(int(v*.80) for v in ac) if apron_color is not None else (200,200,196)
            bx.append(C((cx, yb + .95, cz + f * .145), (.36, .75, .01), ac, mat=M_FABRIC, **k)); bx.append(C((cx, yb + 1.0, cz + f * .148), (.2, .12, .01), pc, **k))
        else:
            bx.append(C((cx - .12, yb + 1.30, cz + f * .143), (.07, .08, .01), (230, 190, 60), emis=.3, **k)); bx.append(C((cx, yb + .84, cz), (.52, .06, .30), (20, 20, 22), **k))
            for s_ in (-1, 1): bx.append(C((cx + s_ * .22, yb + 1.44, cz), (.12, .03, .26), (230, 190, 60), **k))
    else:
        bx.append(C((cx, yb + 1.12, cz), (.50, .64, .28), top, mat=M_FABRIC, **k))
        if outfit == 'suit':
            bx.append(C((cx, yb + 1.30, cz + f * .142), (.12, .28, .01), (232, 230, 222), **k))
            bx.append(C((cx, yb + 1.26, cz + f * .148), (.045, .26, .01), tuple(tie or (150, 30, 40)), **k))
        elif outfit == 'shirt':
            bx.append(C((cx, yb + 1.40, cz + f * .142), (.18, .05, .01), (236, 234, 226), **k))
            for y in (1.30, 1.18, 1.06, .94): bx.append(C((cx, yb + y, cz + f * .143), (.025, .025, .01), (236, 234, 226), **k))
        elif outfit == 'tshirt' and shirt: bx.append(C((cx, yb + 1.18, cz + f * .142), (.18, .16, .01), tuple(shirt), **k))
    return bx


def _tone(c, t):
    """lighter (t > 0) or darker (t < 0) shade of a colour, for cubic strand layering"""
    o = (255, 244, 228) if t > 0 else (0, 0, 0)
    return tuple(int(round(c[i] + (o[i] - c[i]) * abs(t))) for i in range(3))


def hair_strands(hx, hy, cz, f, hair, style, k, hair2=None):
    """real hair in layered cubic locks: a skull cap, a staged fringe over the forehead, side locks and a nape mass.
    Three tones (base / lit top / shaded under) so the layers read as separate strands at 216x384.
    Box budget: 12 (strands), 16 (strands_long), 15 (strands_ponytail) - a hero look, not a crowd look."""
    bx = []; base = tuple(hair); lo = _tone(base, -.30); hi = tuple(hair2) if hair2 else _tone(base, .26)
    bx.append(C((hx, hy + 1.885, cz - f * .01), (.42, .07, .41), base, **k))                  # skull cap
    bx.append(C((hx, hy + 1.925, cz - f * .05), (.34, .035, .30), hi, **k))                   # lit crown
    bx.append(C((hx, hy + 1.70, cz - f * .205), (.42, .40, .06), lo, **k))                    # back of the head
    for dx, dz, w, h, t in ((-.155, .03, .11, .17, hi), (-.05, .06, .10, .11, base),          # fringe, staged locks
                            (.055, .05, .10, .14, hi), (.155, .02, .11, .09, base)):
        bx.append(C((hx + dx, hy + 1.845 - h / 2 + .02, cz + (.185 + dz) * f), (w, h, .06), t, **k))
    for s in (-1, 1):                                                                          # side locks, two layers
        bx.append(C((hx + s * .215, hy + 1.70, cz - f * .02), (.05, .40, .34), base, **k))
        bx.append(C((hx + s * .195, hy + 1.76, cz + f * .13), (.07, .26, .10), hi if s > 0 else lo, **k))
    if style == 'strands_long':
        bx.append(C((hx, hy + 1.36, cz - f * .20), (.40, .54, .07), base, **k))               # mass down the back
        bx.append(C((hx, hy + 1.22, cz - f * .18), (.26, .30, .06), lo, **k))                 # tapered tip
        for s in (-1, 1): bx.append(C((hx + s * .19, hy + 1.44, cz - f * .04), (.06, .36, .26), hi if s > 0 else base, **k))
    elif style == 'strands_ponytail':
        bx.append(C((hx, hy + 1.63, cz - f * .28), (.11, .36, .09), base, **k))
        bx.append(C((hx, hy + 1.42, cz - f * .31), (.08, .18, .07), lo, **k))
        bx.append(C((hx, hy + 1.82, cz - f * .255), (.13, .05, .07), (206, 62, 84), **k))      # scrunchie
    return bx


def outfit_detail(cx, cz, f, yb, outfit, top, k, accent=None):
    """a few boxes that break the flat single-colour top: shoulder yoke, hem band, chest panel, cuffs.
    Opt-in (look `"detail": true`); 4 boxes, so it stays cheap."""
    bx = []; top = tuple(top); ac = tuple(accent) if accent else _tone(top, -.28); hi = _tone(top, .14)
    if outfit == 'hoodie':
        bx.append(C((cx, yb + 1.355, cz), (.505, .07, .285), hi, mat=M_FABRIC, **k))           # shoulder yoke, lit
        bx.append(C((cx, yb + .83, cz), (.505, .07, .285), ac, mat=M_FABRIC, **k))            # hem band
        bx.append(C((cx, yb + 1.18, cz + f * .144), (.17, .34, .01), hi, **k))                # chest panel
        bx.append(C((cx, yb + 1.465, cz + f * .09), (.24, .035, .12), ac, **k))               # collar edge
    else:
        bx.append(C((cx, yb + 1.355, cz), (.50, .06, .28), hi, mat=M_FABRIC, **k))
        bx.append(C((cx, yb + .86, cz), (.50, .06, .28), ac, mat=M_FABRIC, **k))
    return bx


def hair_and_hat(hx, hy, cz, f, hair, style, hat, hat_col, top, k, hair2=None):
    """hair blocks around the head (head centre at hy + 1.68) and an optional hat"""
    bx = []; style = style or 'short'
    if style in STRAND_STYLES:
        if not hat or hat == 'none': return hair_strands(hx, hy, cz, f, hair, style, k, hair2)
        style = 'long' if style == 'strands_long' else ('ponytail' if style == 'strands_ponytail' else 'short')
    if style != 'bald':
        if not hat or hat == 'none': bx.append(C((hx, hy + 1.90, cz - f * .02), (.43, .08, .42), hair, **k))
        bx.append(C((hx, hy + 1.70, cz - f * .20), (.42, .38, .06), hair, **k))
    if style == 'long':
        bx.append(C((hx, hy + 1.5, cz - f * .2), (.44, .62, .08), hair, **k))
        for s in (-1, 1): bx.append(C((hx + s * .215, hy + 1.56, cz - f * .04), (.04, .42, .3), hair, **k))
    elif style == 'ponytail':
        bx.append(C((hx, hy + 1.60, cz - f * .27), (.10, .34, .08), hair, **k))
        bx.append(C((hx, hy + 1.80, cz - f * .25), (.12, .05, .06), (200, 60, 80), **k))
    elif style == 'bun' and (not hat or hat == 'none'):
        bx.append(C((hx, hy + 2.00, cz - f * .12), (.18, .16, .16), hair, **k))
    elif style == 'spiky' and (not hat or hat == 'none'):
        for dx, dz, h in ((-.14, .04, .10), (-.05, .10, .13), (.06, .02, .12), (.15, .08, .09), (0, -.12, .11)):
            bx.append(C((hx + dx, hy + 1.94 + h / 2, cz + dz * f), (.08, h, .08), hair, **k))
    elif style == 'curly':
        if not hat or hat == 'none': bx.append(C((hx, hy + 1.94, cz - f * .02), (.50, .14, .48), hair, **k))
        for s in (-1, 1): bx.append(C((hx + s * .245, hy + 1.78, cz - f * .04), (.07, .26, .38), hair, **k))
    hc = tuple(hat_col or (180, 40, 50))
    if hat == 'cap':
        bx.append(C((hx, hy + 1.92, cz), (.44, .09, .44), hc, mat=M_FABRIC, **k))
        bx.append(C((hx, hy + 1.885, cz + f * .27), (.30, .025, .16), hc, **k))
    elif hat == 'beanie':
        bx.append(C((hx, hy + 1.95, cz), (.45, .15, .44), hc, mat=M_FABRIC, **k))
        bx.append(C((hx, hy + 1.87, cz), (.47, .05, .46), tuple(int(c * .8) for c in hc), mat=M_FABRIC, **k))
    elif hat == 'hood':
        hd = tuple(int(c * .9) for c in top)
        bx.append(C((hx, hy + 1.93, cz - f * .02), (.50, .07, .46), hd, mat=M_FABRIC, **k))
        for s in (-1, 1): bx.append(C((hx + s * .235, hy + 1.70, cz - f * .02), (.05, .44, .44), hd, mat=M_FABRIC, **k))
        bx.append(C((hx, hy + 1.70, cz - f * .23), (.50, .46, .05), hd, mat=M_FABRIC, **k))
    elif hat == 'tophat':
        bx.append(C((hx, hy + 1.905, cz), (.54, .03, .50), (24, 22, 26), **k))
        bx.append(C((hx, hy + 2.07, cz), (.34, .30, .32), (24, 22, 26), **k))
        bx.append(C((hx, hy + 1.95, cz), (.35, .04, .33), hc, **k))
    elif hat in ('wizard', 'witch', 'party'):
        hc2 = tuple(hat_col or {'wizard': (70, 50, 140), 'witch': (30, 24, 36), 'party': (230, 60, 120)}[hat]); n = 6 if hat != 'party' else 4
        if hat != 'party': bx.append(C((hx, hy + 1.895, cz), (.62 if hat == 'witch' else .52, .03, .60 if hat == 'witch' else .5), hc2, **k))
        for i in range(n):
            w = (.42 if hat != 'party' else .3) * (1 - i / n) + .04
            bx.append(C((hx + (i * .02 if hat == 'witch' else 0), hy + 1.95 + i * .1, cz - (i * .015 * f if hat == 'wizard' else 0)), (w, .1, w), hc2, mat=M_FABRIC, **k))
        if hat == 'wizard':
            for dx, dy, dz in ((.1, 2.05, .2), (-.12, 2.2, .14), (.05, 2.35, .1)): bx.append(C((hx + dx, hy + dy, cz + dz * f), (.04, .04, .01), (250, 230, 120), emis=1.5, **k))
        if hat == 'party': bx.append(C((hx, hy + 2.36, cz), (.07, .07, .07), (250, 230, 80), **k))
    elif hat == 'pirate':
        bx.append(C((hx, hy + 1.94, cz), (.56, .12, .36), (24, 22, 24), **k)); bx.append(C((hx, hy + 2.02, cz), (.36, .1, .3), (24, 22, 24), **k))
        bx.append(C((hx, hy + 1.98, cz + .182 * f), (.06, .06, .01), (240, 240, 236), **k))
    elif hat == 'chef':
        hc = tuple(hat_col or (246, 246, 244))
        bx.append(C((hx, hy + 1.93, cz), (.44, .06, .44), hc, **k)); bx.append(C((hx, hy + 2.1, cz), (.4, .3, .4), hc, mat=M_FABRIC, **k))
    elif hat == 'police':
        bx.append(C((hx, hy + 1.93, cz), (.44, .1, .44), tuple(hat_col or (30, 40, 80)), **k)); bx.append(C((hx, hy + 1.885, cz + f * .26), (.32, .025, .14), (20, 20, 22), **k))
        bx.append(C((hx, hy + 1.94, cz + f * .222), (.07, .06, .01), (230, 190, 60), emis=.4, **k))
    elif hat == 'helmet':
        hm = tuple(hat_col or (160, 162, 170))
        bx.append(C((hx, hy + 1.9, cz), (.46, .12, .44), hm, mat=M_METAL, **k))
        for s_ in (-1, 1): bx.append(C((hx + s_ * .225, hy + 1.72, cz), (.04, .36, .42), hm, mat=M_METAL, **k))
        bx.append(C((hx, hy + 1.72, cz - f * .215), (.46, .38, .04), hm, mat=M_METAL, **k))
        if not hat_col: bx.append(C((hx, hy + 1.82, cz + f * .205), (.42, .06, .02), hm, mat=M_METAL, **k))
    elif hat == 'astronaut':
        bx.append(C((hx, hy + 1.72, cz), (.52, .5, .5), (170, 200, 230), refl=.45, emis=.05, cast=False, **k)); bx.append(C((hx, hy + 1.45, cz), (.5, .08, .48), (236, 236, 240), **k))
    elif hat == 'cowboy':
        hc2 = tuple(hat_col or (150, 100, 50))
        bx.append(C((hx, hy + 1.905, cz), (.7, .03, .64), hc2, **k)); bx.append(C((hx, hy + 2.0, cz), (.36, .18, .34), hc2, **k))
    elif hat == 'antenna':
        bx.append(C((hx, hy + 2.0, cz), (.02, .22, .02), (60, 60, 64), **k)); bx.append(C((hx, hy + 2.13, cz), (.06, .06, .06), (255, 60, 60), emis=2., **k))
    elif hat == 'crown':
        gold = (232, 190, 60)
        bx.append(C((hx, hy + 1.925, cz), (.42, .07, .40), gold, emis=.25, **k))
        for dx in (-.15, 0, .15): bx.append(C((hx + dx, hy + 2.0, cz + .2 * f), (.06, .08, .02), gold, emis=.25, **k))
        bx.append(C((hx, hy + 1.93, cz + .205 * f), (.05, .04, .01), (220, 40, 60), emis=.6, **k))
    return bx


def held_item(item, hand, f, k, lights=None, col=None):
    """object in the main hand (hand = world position of the hand centre)"""
    if not item or hand is None: return []
    x, y, z = hand; bx = []
    P = lambda lat, up, fwd: (x + lat * f, y + up, z + fwd * f)
    if item == 'phone':
        bx.append(C(P(0, .05, .02), (.075, .15, .025), (20, 20, 24), mat=M_METAL, **k))
        bx.append(C(P(0, .05, .034), (.06, .12, .004), (120, 190, 255), emis=1.2, cast=False, **k))
    elif item == 'cup':
        bx.append(C(P(0, .06, .06), (.09, .11, .09), tuple(col or (236, 232, 222)), **k))
        bx.append(C(P(.06, .07, .06), (.03, .06, .02), tuple(col or (236, 232, 222)), **k))
        bx.append(C(P(0, .115, .06), (.07, .005, .07), (90, 50, 30), **k))
    elif item == 'book':
        bx.append(C(P(0, .02, .08), (.20, .26, .045), tuple(col or (150, 50, 50)), **k))
        bx.append(C(P(.01, .02, .08), (.19, .25, .05), (236, 230, 210), **k))
    elif item == 'flashlight':
        bx.append(C(P(0, 0, .09), (.05, .05, .20), (30, 30, 34), mat=M_METAL, **k))
        bx.append(C(P(0, 0, .195), (.06, .06, .01), (255, 250, 220), emis=3., cast=False, **k))
        if lights is not None: lights.append((P(0, 0, 1.3), (1, .95, .82), 2.4, 3.6))
    elif item == 'candle':
        bx.append(C(P(0, .07, .04), (.045, .13, .045), (236, 226, 196), **k))
        bx.append(C(P(0, .16, .04), (.025, .045, .025), (255, 170, 60), emis=3., cast=False, **k))
        if lights is not None: lights.append((P(0, .3, .1), (1, .62, .3), .9, 2.4))
    elif item == 'key':
        bx.append(C(P(0, .02, .07), (.05, .05, .015), (220, 180, 60), emis=.3, **k))
        bx.append(C(P(0, .02, .12), (.015, .015, .08), (220, 180, 60), emis=.3, **k))
    elif item == 'letter':
        bx.append(C(P(0, .05, .07), (.18, .12, .008), (240, 236, 222), **k))
        bx.append(C(P(0, .05, .075), (.03, .03, .006), (190, 30, 40), **k))
    elif item == 'flower':
        bx.append(C(P(0, .13, .04), (.015, .24, .015), (60, 140, 60), **k))
        bx.append(C(P(0, .27, .04), (.07, .06, .07), tuple(col or (230, 60, 90)), **k))
        bx.append(C(P(0, .27, .04), (.025, .025, .075), (250, 210, 80), **k))
    elif item == 'gift':
        c = tuple(col or (200, 40, 60))
        bx.append(C(P(0, .06, .14), (.22, .18, .22), c, **k))
        bx.append(C(P(0, .06, .14), (.04, .185, .225), (250, 210, 80), **k)); bx.append(C(P(0, .06, .14), (.225, .185, .04), (250, 210, 80), **k))
    elif item == 'sword':
        bx.append(C(P(0, .02, 0), (.04, .14, .04), (90, 60, 40), **k))
        bx.append(C(P(0, .10, 0), (.18, .03, .04), (200, 180, 90), mat=M_METAL, **k))
        bx.append(C(P(0, .48, 0), (.05, .74, .015), (210, 214, 222), mat=M_METAL, emis=.15, **k))
    elif item == 'ball':
        bx.append(C(P(0, .02, .14), (.22, .22, .22), tuple(col or (230, 120, 40)), **k))
    elif item == 'bag':
        bx.append(C(P(0, -.20, 0), (.26, .30, .12), tuple(col or (200, 170, 120)), **k))
        bx.append(C(P(0, -.03, 0), (.12, .04, .02), (60, 50, 40), **k))
    elif item == 'umbrella':
        bx.append(C(P(0, .35, 0), (.025, .80, .025), (40, 40, 44), **k))
        bx.append(C(P(0, .78, 0), (.95, .08, .95), tuple(col or (40, 90, 170)), mat=M_FABRIC, **k))
        bx.append(C(P(0, .72, 0), (.80, .05, .80), tuple(int(c * .8) for c in (col or (40, 90, 170))), mat=M_FABRIC, **k))
    elif item == 'balloon':
        bx.append(C(P(0, .55, 0), (.008, 1.0, .008), (230, 230, 230), **k))
        bx.append(C(P(0, 1.18, 0), (.30, .34, .30), tuple(col or (230, 50, 70)), refl=.15, **k))
    elif item in ('staff', 'wand'):
        L = .9 if item == 'staff' else .3
        bx.append(C(P(0, L / 2 - .1, 0), (.04 if item == 'staff' else .02, L + .3 if item == 'staff' else L, .04 if item == 'staff' else .02), (110, 76, 46) if item == 'staff' else (40, 30, 26), **k))
        bx.append(C(P(0, L + (.12 if item == 'staff' else .02), 0), (.1, .1, .1) if item == 'staff' else (.03, .03, .03), tuple(col or (120, 200, 255)), emis=2.5, cast=False, **k))
        if lights is not None: lights.append((P(0, L + .15, 0), (.6, .8, 1.), .7 if item == 'staff' else .4, 2.0))
    elif item == 'torch':
        bx.append(C(P(0, .15, 0), (.05, .45, .05), (90, 60, 36), **k)); bx.append(C(P(0, .42, 0), (.1, .14, .1), (255, 150, 40), emis=3., cast=False, **k))
        if lights is not None: lights.append((P(0, .55, .1), (1, .58, .28), 1.5, 4.0))
    elif item == 'shield':
        c = tuple(col or (160, 40, 40))
        bx.append(C(P(.02, 0, .1), (.06, .5, .4), c, mat=M_METAL, **k)); bx.append(C(P(.06, 0, .1), (.02, .2, .1), (220, 190, 70), **k))
    elif item == 'map':
        bx.append(C(P(0, .06, .1), (.34, .24, .01), (226, 206, 160), **k)); bx.append(C(P(.05, .04, .106), (.04, .04, .004), (200, 40, 40), **k))
    elif item == 'guitar':
        c = tuple(col or (170, 90, 40))
        bx.append(C(P(-.12, -.08, .12), (.32, .3, .1), c, mat=M_WOODV, **k)); bx.append(C(P(.12, .05, .12), (.35, .05, .04), (60, 40, 26), **k)); bx.append(C(P(-.12, -.08, .172), (.08, .08, .005), (20, 14, 10), **k))
    elif item == 'bottle':
        bx.append(C(P(0, .08, .05), (.06, .18, .06), tuple(col or (60, 140, 80)), refl=.3, **k)); bx.append(C(P(0, .2, .05), (.03, .06, .03), tuple(col or (60, 140, 80)), **k))
    elif item == 'apple': bx.append(C(P(0, .05, .07), (.08, .08, .08), tuple(col or (210, 40, 40)), **k)); bx.append(C(P(0, .1, .07), (.01, .03, .01), (80, 60, 30), **k))
    elif item == 'camera': bx.append(C(P(0, .02, .1), (.16, .1, .07), (30, 30, 34), mat=M_METAL, **k)); bx.append(C(P(0, .02, .15), (.06, .06, .04), (60, 70, 90), refl=.4, **k))
    elif item == 'ice_cream':
        bx.append(C(P(0, .05, .05), (.05, .12, .05), (220, 170, 90), **k)); bx.append(C(P(0, .14, .05), (.08, .07, .08), tuple(col or (250, 190, 210)), **k))
    elif item == 'newspaper': bx.append(C(P(0, .06, .12), (.3, .36, .01), (232, 230, 222), **k)); bx.append(C(P(0, .16, .126), (.24, .04, .004), (30, 30, 30), **k))
    elif item == 'microphone':
        bx.append(C(P(0, .08, .02), (.035, .16, .035), (30, 30, 34), mat=M_METAL, **k))
        bx.append(C(P(0, .19, .02), (.06, .07, .06), (150, 150, 160), mat=M_METAL, **k))
    return bx


# ------------------------------------------------------------------ lying down
_ROT_X = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], np.float32)       # face up, head towards -z
_YAW = {'-z': (np.eye(3, dtype=np.float32), 0),
        '+z': (np.array([[-1, 0, 0], [0, 1, 0], [0, 0, -1]], np.float32), 2),
        '-x': (np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], np.float32), 1),
        '+x': (np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], np.float32), -1)}
_FACE_VEC = {k: v for k, v in (('-x', (-1, 0, 0)), ('+x', (1, 0, 0)), ('-y', (0, -1, 0)), ('+y', (0, 1, 0)), ('-z', (0, 0, -1)), ('+z', (0, 0, 1)))}
_VEC_FACE = {v: FACES[k] for k, v in _FACE_VEC.items()}
_ID_VEC = {FACES[k]: np.array(v, np.float32) for k, v in _FACE_VEC.items()}

def _rotate(bx, R, tex_fn):
    for b in bx:
        c = np.stack([R @ b.lo, R @ b.hi]); b.lo = c.min(0); b.hi = c.max(0)
        if b.tex:
            nt = {}
            for fid, t in b.tex.items():
                v = tuple(int(round(q)) for q in R @ _ID_VEC[fid]); nt[_VEC_FACE[v]] = tex_fn(fid, _VEC_FACE[v], t)
            b.tex = nt
    return bx

def lie(bx, x, z, head='-x', bed_y=0.):
    """turn a standing figure built at the origin facing +z into one lying on its back"""
    bx = _rotate(bx, _ROT_X, lambda a, b_, t: np.ascontiguousarray(t[:, ::-1]) if b_ == FACES['+y'] else t)
    R, k = _YAW.get(head, _YAW['-x'])
    if k: bx = _rotate(bx, R, lambda a, b_, t: np.ascontiguousarray(np.rot90(t, k)) if b_ == FACES['+y'] else t)
    lo = np.min([b.lo for b in bx], 0); hi = np.max([b.hi for b in bx], 0)
    off = np.array([x - (lo[0] + hi[0]) / 2, bed_y - lo[1], z - (lo[2] + hi[2]) / 2], np.float32)
    for b in bx: b.lo = b.lo + off; b.hi = b.hi + off
    return bx
