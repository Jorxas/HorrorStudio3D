"""Effects registry of the PIXEL 3D engine (V3).

A shot's "objects" whose type is registered here are drawn by the effect, frame by frame, deterministically:
  EFFECTS[name](fx, o) -> (boxes, lights)       fx: Fx (frame context and helpers), o: the object of the shot
  SOUNDS[name](o) -> [(t, sfx, gain, dur)]       sounds of the effect, t in seconds from the start of the shot
The original object types of frame.eval_objects (phone, debris, glass_burst...) are unchanged; new effects, from the core
or from extensions (capabilities/extensions.py), register here with @effect(name, sounds=...).

Effects of the core
  lightning_bolt  {"at", "to": group | anchor | actor | [x, y, z], "from": [x, y, z], "seed", "branches", "dur", "flash"}
  collapse        {"target": group (an element of a composed set), "at", "dur", "remain": share left standing,
                   "lean": [dx, dz] where the debris go, "chunk": metres, "seed"}: the element breaks from the top down
  mover           {"thing": "creature:dragon" | "prop:car" | ..., "path": [[x, y, z], ...], "start", "dur" | "speed",
                   "ease": in_out | linear | out | in, "size", "color", "bank", "pitch" (nose follows the slope, x factor),
                   "lean" (nose down with speed: helicopters), "stay", "wait", "yaw" (offset),
                   "hold": [x, y, z] + "hover": bob amplitude (a thing staying in place), "carry": [{"who", "from"}],
                   "light_power": factor on the lights of the thing (searchlight...),
                   "sound": {"name", "gain", "dur"}}: anything follows a smooth 3D path, faces where it goes, banks in turns
Helpers: Fx.point() resolves a target, Fx.hide(group) removes the static boxes of an element for this frame."""
import math
import numpy as np
from .r3d import B, C, Box, orient
from . import creatures as CR
from ...acting import rig

EFFECTS = {}; SOUNDS = {}
G = 9.81

def effect(name, sounds=None):
    def reg(fn):
        EFFECTS[name] = fn
        if sounds is not None: SOUNDS[name] = sounds
        return fn
    return reg

def smooth(x): x = min(1., max(0., x)); return x * x * (3 - 2 * x)

class Fx:
    def __init__(self, ctx, shot, st, actors, cam, T, u, g):
        self.ctx, self.shot, self.st, self.actors, self.cam, self.T, self.u, self.g = ctx, shot, st, actors, cam, T, u, g
    def group_boxes(self, gid):
        base = self.st.base.boxes
        return [base[i] for i in getattr(self.st, 'groups', {}).get(gid, [])]
    def hide(self, gid):
        hs = getattr(self.ctx, 'hide_static', None)
        if hs is not None: hs.update(id(b) for b in self.group_boxes(gid))
    def point(self, a, y=1.4):
        """group id (top centre) | actor id | anchor | [x, z] | [x, y, z] -> (x, y, z)"""
        if isinstance(a, (list, tuple)):
            return (float(a[0]), float(a[1]), float(a[2])) if len(a) == 3 else (float(a[0]), y, float(a[1]))
        if isinstance(a, str):
            bx = self.group_boxes(a)
            if bx:
                lo = np.min([b.lo for b in bx], 0); hi = np.max([b.hi for b in bx], 0)
                return (float(lo[0] + hi[0]) / 2, float(hi[1]), float(lo[2] + hi[2]) / 2)
            if a in self.actors: ac = self.actors[a]; return (ac['x'], 1.6 + ac.get('yoff', 0.), ac['z'])
            p = self.st.anchors.get(a)
            if p is not None: return (float(p[0]), y, float(p[1]))
        return (0., y, 0.)
    def flash(self, amount):
        self.ctx.fx_flash = max(getattr(self.ctx, 'fx_flash', 0.), float(amount))
    def since(self, o):
        """seconds since the effect started: "at" (in the shot) or "at_abs" (in the episode: the same event continues
        identically over several shots, e.g. a building still collapsing after the cut)"""
        return self.g - float(o['at_abs']) if o.get('at_abs') is not None else self.T - float(o.get('at', 0.))

# ------------------------------------------------------------------ lightning
def _bolt(p0, p1, seed, rough=.18, levels=5):
    """midpoint displacement: jagged polyline between two points"""
    rng = np.random.default_rng(seed); pts = [np.array(p0, np.float32), np.array(p1, np.float32)]
    L = float(np.linalg.norm(pts[1] - pts[0]))
    for lv in range(levels):
        out = [pts[0]]
        for a, b in zip(pts[:-1], pts[1:]):
            m = (a + b) / 2; amp = L * rough / (2 ** lv)
            m = m + np.array([rng.uniform(-amp, amp), rng.uniform(-amp, amp) * .3, rng.uniform(-amp, amp)], np.float32); out += [m, b]
        pts = out
    return pts

def _segment_boxes(a, b, w, col, emis):
    """a jagged pixel-art stroke: small boxes stepping from a to b"""
    out = []; d = b - a; n = max(1, int(abs(float(d[1])) / .7) + int(math.hypot(float(d[0]), float(d[2])) / .7))
    for k in range(n):
        p = a + d * (k + .5) / n; seg = np.abs(d) / n
        out.append(C(tuple(float(v) for v in p), (max(w, float(seg[0])), max(w, float(seg[1])), max(w, float(seg[2]))), col, emis=emis, cast=False))
    return out

@effect('lightning_bolt', sounds=lambda o: [(float(o.get('at', 0.)), 'thunder_close', float(o.get('gain', 1.)), None)])
def lightning_bolt(fx, o):
    dt = fx.since(o)
    if dt < 0 or dt > 1.2: return [], []
    tgt = fx.point(o.get('to'), 0.)
    src = o.get('from') or [tgt[0] + float(o.get('drift', 6.)), tgt[1] + float(o.get('height', 45.)), tgt[2] + float(o.get('drift', 6.)) * .5]
    seed = int(o.get('seed', 7)); out = []; L = []
    on = dt < .08 or .13 < dt < .3 or .36 < dt < .4
    if on and dt < float(o.get('dur', .45)):
        col = tuple(o.get('color', (225, 235, 255)))
        pts = _bolt(src, tgt, seed)
        for a, b in zip(pts[:-1], pts[1:]): out += _segment_boxes(a, b, float(o.get('width', .5)), col, 4.)
        rng = np.random.default_rng(seed + 1)
        for k in range(int(o.get('branches', 2))):            # forks from the upper half
            i = int(rng.integers(2, len(pts) // 2)); p = pts[i]; q = p + np.array([rng.uniform(-6, 6), -rng.uniform(4, 9), rng.uniform(-6, 6)], np.float32)
            br = _bolt(p, q, seed + 10 + k, .22, 3)
            for a, b in zip(br[:-1], br[1:]): out += _segment_boxes(a, b, float(o.get('width', .5)) * .6, col, 3.)
        mid = pts[len(pts) // 2]
        L += [((tgt[0], tgt[1] + 2.5, tgt[2]), (.78, .84, 1.), 9., 28.), ((float(mid[0]), float(mid[1]), float(mid[2])), (.7, .78, 1.), 6., 45.)]
        fx.flash(float(o.get('flash', .55)) * (1. if dt < .08 else .6))
    rng = np.random.default_rng(seed + 3)                      # sparks at the impact
    for k in range(int(o.get('sparks', 26))):
        v = np.array([rng.uniform(-4, 4), rng.uniform(1, 6), rng.uniform(-4, 4)]); p = np.array(tgt) + v * dt + np.array([0, -.5 * G * dt * dt, 0])
        if dt < rng.uniform(.4, 1.1): out.append(C(tuple(float(x) for x in p), (.09, .09, .09), (255, 190, 90), emis=3., cast=False))
    if dt < .9: L.append(((tgt[0], tgt[1] + .5, tgt[2]), (1., .55, .25), 2.5 * (1 - dt / .9), 8.))
    return out, L

# ------------------------------------------------------------------ collapse
def _cropped(body, top):
    """the standing part of a textured box, its facade cut at the right row"""
    lo = body.lo.copy(); hi = body.hi.copy(); H = float(hi[1] - lo[1]); frac = max(0., min(1., (top - float(lo[1])) / max(H, 1e-3)))
    hi[1] = lo[1] + H * frac
    b = Box(lo, hi, tuple(body.col * 255), emis=body.emis, refl=body.refl, grain=body.grain, texemis=body.texemis, mat=body.mat)
    tex = {}
    for k, arr in body.tex.items():
        if k in (2, 3): continue                               # top / bottom faces
        r0 = int(round(arr.shape[0] * (1 - frac))); tex[k] = arr[min(r0, arr.shape[0] - 1):]
    b.tex = tex
    return b

def _rot(ax, ay, az): return rig.rot_y(ay) @ rig.rot_x(ax) @ rig.rot_z(az)

@effect('collapse', sounds=lambda o: [(float(o.get('at', 0.)), 'collapse', float(o.get('gain', 1.)), float(o.get('dur', 6.)) + 1.5)])
def collapse(fx, o):
    dt = fx.since(o); t0 = fx.T - dt                           # start of the collapse in shot time (may be before the shot)
    gid = o.get('target'); boxes = fx.group_boxes(gid)
    if dt < 0 or not boxes: return [], []
    fx.hide(gid)
    body = max(boxes, key=lambda b: float(b.hi[1] - b.lo[1]) * float((b.hi[0] - b.lo[0]) * (b.hi[2] - b.lo[2])))
    lo, hi = body.lo, body.hi; H = float(hi[1] - lo[1]); dur = float(o.get('dur', 6.)); stop = float(lo[1]) + H * float(o.get('remain', .35))
    floor = float(getattr(fx.st.base, 'floor_y', 0.))
    front = float(hi[1]) - (float(hi[1]) - stop) * min(1., dt / dur) ** 1.25
    out = [_cropped(body, front)]; L = []
    lean = np.array(o.get('lean', [0., 1.]), np.float32); lean = lean / (np.linalg.norm(lean) + 1e-6)
    rng = np.random.default_rng(int(o.get('seed', 5))); ch = float(o.get('chunk', 2.4))
    w, d = float(hi[0] - lo[0]), float(hi[2] - lo[2]); col = body.col * 255
    layer = 0; y = float(hi[1])
    while y - ch > stop - 1e-3:                                # layers from the top down: each breaks when the front passes it
        yb = y - ch; ts = t0 + dur * ((float(hi[1]) - yb) / max(1e-3, float(hi[1]) - stop)) ** (1 / 1.25)
        nx, nz = (2, 2) if layer % 2 == 0 else (3, 2)
        for i in range(nx):
            for j in range(nz):
                k = rng.random(12)
                if fx.T < ts: continue
                sx, sz = w / nx * (.75 + .25 * k[0]), d / nz * (.75 + .25 * k[1]); sy = ch * (.6 + .4 * k[2])
                p0 = np.array([float(lo[0]) + w * (i + .5) / nx, yb + ch / 2, float(lo[2]) + d * (j + .5) / nz], np.float32)
                out_dir = np.array([p0[0] - (float(lo[0]) + w / 2), 0, p0[2] - (float(lo[2]) + d / 2)], np.float32)
                v = np.array([lean[0] * (1 + 3 * k[3]) + out_dir[0] * .4 * k[4], 1.5 * k[5] - .5, lean[1] * (1 + 3 * k[3]) + out_dir[2] * .4 * k[4]], np.float32)
                tt = fx.T - ts; tl = (v[1] + math.sqrt(max(0., v[1] ** 2 + 2 * G * (p0[1] - floor - sy / 2)))) / G     # time to reach the ground
                te = min(tt, tl); p = p0 + v * te + np.array([0, -.5 * G * te * te, 0], np.float32)
                wsp = (k[6:9] - .5) * 3.; R = _rot(*(wsp * te))
                shade = .7 + .35 * k[9]
                if k[10] < .22:                                 # a piece of lit facade: glowing glass, readable at night
                    cc, em = (255, 214, 150), 1.6 * max(0., 1. - tt / 3.)
                else: cc, em = tuple(int(min(255, (c * .6 + 150 * .4) * shade)) for c in col), 0.
                out += orient([C((0, 0, 0), (sx, sy, sz), cc, mat=body.mat, emis=em)], 0., tuple(float(x) for x in p), R)
                for q in range(2):                              # dust trailing the chunk
                    age = tt - .15 * q
                    if 0 < age < 2.5:
                        dp = p0 + v * min(age, tl) * .6 + np.array([0, -.25 * G * min(age, tl) ** 2, 0], np.float32)
                        s_ = .8 + 1.5 * age
                        out.append(C(tuple(float(x) for x in dp), (s_, s_ * .8, s_), (176, 172, 164), cast=False, dissolve=min(.92, .4 + .2 * age)))
        y = yb; layer += 1
    if dt < dur + 1.5:                                          # glow and sparks at the breaking front
        flick = .7 + .3 * math.sin(fx.g * 23) * math.sin(fx.g * 9)
        L.append(((float(lo[0] + hi[0]) / 2, front, float(lo[2] + hi[2]) / 2), (1., .5, .2), 2.2 * flick, 14.))
        for k in range(14):
            a = k * 2.4 + fx.g * 3; r = .5 + (k % 3) * .5
            out.append(C((float(lo[0] + hi[0]) / 2 + math.cos(a) * w * .45, front + .3 * math.sin(fx.g * 7 + k), float(lo[2] + hi[2]) / 2 + math.sin(a) * d * .45), (.12, .12, .12), (255, 170, 70), emis=3., cast=False))
    for k in range(10):                                         # the cloud rising from the street
        age = dt - .8 - k * .3
        if age > 0:
            s_ = 2 + 2.2 * age; a = k * 1.9
            out.append(C((float(lo[0] + hi[0]) / 2 + math.cos(a) * (w * .4 + age), floor + s_ * .4, float(lo[2] + hi[2]) / 2 + math.sin(a) * (d * .4 + age)), (s_, s_ * .7, s_), (160, 156, 148), cast=False, dissolve=min(.9, .4 + .08 * age)))
    return out, L

# ------------------------------------------------------------------ mover
class _Spline:
    """Catmull-Rom through the points, parametrised by arc length"""
    def __init__(self, pts):
        P = [np.asarray(p, np.float32) for p in pts]
        if len(P) == 1: P = P * 2
        P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
        S = []
        for i in range(1, len(P) - 2):
            p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
            for t in np.linspace(0, 1, 24, endpoint=False):
                S.append(.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
        S.append(P[-2]); self.S = np.array(S, np.float32)
        self.cum = np.concatenate([[0.], np.cumsum(np.linalg.norm(np.diff(self.S, axis=0), axis=1))]); self.L = float(self.cum[-1])
    def at(self, s):
        s = min(max(s, 0.), self.L); i = int(np.clip(np.searchsorted(self.cum, s) - 1, 0, len(self.S) - 2))
        l = self.cum[i + 1] - self.cum[i]; u = (s - self.cum[i]) / l if l > 1e-6 else 0.
        return self.S[i] + (self.S[i + 1] - self.S[i]) * u

_SPLINES = {}
def _spline(o):
    key = id(o)
    if key not in _SPLINES or _SPLINES[key][0] is not o: _SPLINES[key] = (o, _Spline(o['path']))
    return _SPLINES[key][1]

EASE = {'linear': lambda x: x, 'in_out': smooth, 'out': lambda x: 1 - (1 - x) ** 2, 'in': lambda x: x * x}

def mover_state(o, T):
    """(position, rotation, visible) of a mover at T seconds into the shot"""
    yo = math.radians(float(o.get('yaw', 0.)))
    if o.get('hold') is not None:
        p = np.asarray(o['hold'], np.float32) + np.array([0, float(o.get('hover', .12)) * math.sin(T * 1.4), 0], np.float32)
        return p, rig.rot_y(math.radians(float(o.get('face', 0.))) + yo) @ rig.rot_z(.03 * math.sin(T * .9)), True
    sp = _spline(o); start = float(o.get('start', 0.))
    dur = float(o['dur']) if o.get('dur') else sp.L / max(.1, float(o.get('speed', 6.)))
    x = (T - start) / max(1e-3, dur)
    if (x < 0 and not o.get('wait', True)) or (x > 1 and not o.get('stay', True)): return None, None, False
    e = EASE.get(o.get('ease', 'in_out'), smooth); s = sp.L * e(min(1., max(0., x)))
    p = sp.at(s); a = sp.at(s - .4); b = sp.at(s + .4)
    if np.linalg.norm(b - a) < 1e-3: a, b = sp.at(sp.L - .8), sp.at(sp.L)
    dv = b - a; yaw = math.atan2(float(dv[0]), float(dv[2]))
    pitch = -math.atan2(float(dv[1]), math.hypot(float(dv[0]), float(dv[2])) + 1e-6) * float(o.get('pitch', 1.))
    if o.get('lean'):                              # a helicopter tilts its nose down to fly forwards, more when faster
        s2 = sp.L * e(min(1., max(0., x + .1 / max(1e-3, dur))))
        pitch += float(o['lean']) * min(1., (s2 - s) / .1 / 12.)
    a2, b2 = sp.at(s + .4), sp.at(s + 2.)
    yaw2 = math.atan2(float(b2[0] - a2[0]), float(b2[2] - a2[2])); turn = (yaw2 - yaw + math.pi) % (2 * math.pi) - math.pi
    roll = max(-.7, min(.7, -turn * float(o.get('bank', .8))))
    return p, rig.rot_y(yaw + yo) @ rig.rot_x(pitch) @ rig.rot_z(roll), True

def _mover_sounds(o):
    snd = o.get('sound')
    if not snd: return []
    snd = {'name': snd} if isinstance(snd, str) else snd
    return [(float(snd.get('at', o.get('start', 0.))), snd['name'], float(snd.get('gain', .7)), snd.get('dur'))]

@effect('mover', sounds=_mover_sounds)
def mover(fx, o):
    p, R, vis = mover_state(o, fx.T)
    if not vis or not o.get('thing'): return [], []
    kind, _, name = str(o['thing']).partition(':'); size = float(o.get('size', 1.)); col = tuple(o['color']) if o.get('color') else None
    if kind == 'creature':
        bx = CR.animal(name, col, 0., fx.g, {}, o.get('posture', 'fly'), size); lights = []
    else:
        from .sets import prop_boxes
        from . import world as W
        bx = prop_boxes(name, dict(o, _t=fx.g, color=o.get('color') or ()))
        if size != 1.:
            for b in bx: b.lo = b.lo * size; b.hi = b.hi * size
        lk = float(o.get('light_power', 1.))
        lights = [(tuple(float(v) for v in (R @ (np.asarray(lp, np.float32) * size) + p)), c_, pw * lk, rad) for (lp, c_, pw, rad, _f) in W.PROP_LIGHTS.get(name, [])]
    return orient(bx, 0., tuple(float(v) for v in p), R), lights

def carry_offsets(shot, T, sa=None):
    """characters riding a mover ("carry"): how far it took them since they boarded -> {id: (dx, dy, dz)}.
    "from": seconds into the shot, or "landing": the end of the character's last jump in this shot (jumping aboard)"""
    out = {}
    for o in shot.get('objects') or []:
        if o.get('type') != 'mover': continue
        for c in o.get('carry') or []:
            if c.get('from') == 'landing':
                tr = sa.tracks.get(c['who']) if sa is not None else None
                if tr is None or not tr.airs: continue
                t1 = tr.airs[-1]['t1']
            else: t1 = float(c.get('from', 0.))
            if T <= t1: continue
            p1, _, _ = mover_state(o, t1); p, _, vis = mover_state(o, T)
            if p is not None and p1 is not None: out[c['who']] = tuple(float(v) for v in (p - p1))
    return out

def sounds(shot, t_shot=0.):
    """[(t, sfx, gain, dur)] of the effects of a shot, relative to its start (t_shot: its start in the episode, for
    "at_abs"); "sound": false silences an effect repeated over several shots"""
    out = []
    for o in shot.get('objects') or []:
        fn = SOUNDS.get(o.get('type'))
        if not fn or o.get('sound') is False: continue
        shift = float(o['at_abs']) - t_shot - float(o.get('at', 0.)) if o.get('at_abs') is not None else 0.
        out += [(t + shift, n, gn, d) for (t, n, gn, d) in fn(o)]
    return out
