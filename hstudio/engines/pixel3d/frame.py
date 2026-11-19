"""Evaluate one frame of a PIXEL 3D episode: shot lookup, actors, camera presets, transient objects, lights.

A shot (see docs/DSL.md) looks like:
{"lines": [3, 4], "set": "etage_zero",
 "camera": {"preset": "closeup", "subject": "double", "move": "push_in", "shake": .2},
 "actors": [{"id": "double", "at": "corridor.end", "facing": "-z", "face": "double", "lipsync": true}],
 "objects": [...], "state": {...}, "fx": {...}, "ui": {...}, "sfx": [...], "audio": {...}}
"""
import math, numpy as np
from .r3d import B, C, Box
from . import assets as A
from . import poses as P
from . import creatures as CR
from . import world as W
from . import effects as FX
from . import lighting as LT
from . import bodies
from .sets import make_set, sv

D2R = math.pi / 180
def clamp(x, a=0., b=1.): return max(a, min(b, x))
def ease(t): t = clamp(t); return t * t * (3 - 2 * t)
def lerp(a, b, t): return a + (b - a) * t
CUR_T = [0.]      # seconds since the start of the current shot/cut (set by build_frame)
def val(v, u, default=None):
    """number | [a, b] (interpolated over the shot) | [a, b, t0, t1] (interpolated between t0 and t1 seconds) | None"""
    if v is None: return default
    if isinstance(v, (list, tuple)) and all(isinstance(x, (int, float)) for x in v):
        if len(v) == 2: return lerp(v[0], v[1], ease(u))
        if len(v) == 4: return lerp(v[0], v[1], ease((CUR_T[0] - v[2]) / max(1e-3, v[3] - v[2])))
    return v

def apply_state_track(shot, state, T):
    """`state_track` d'un plan dirigé : {"dt": 1/30, "values": {"shop": [...], "car": [[cx, cz, cap, feux, marche arrière], ...]}} lue à l'instant T du plan (tables écrites image par image : lumières qui grésillent, voiture qui recule)"""
    tr = shot.get('state_track')
    if not tr: return state
    dt = float(tr.get('dt', 1 / 30.)); j = max(0, int(T / dt + 1e-6)); out = dict(state)
    for k, arr in (tr.get('values') or {}).items(): out[k] = arr[min(j, len(arr) - 1)]
    return out

def resolve_state(state, u):
    out = {}
    for k, v in state.items():
        out[k] = val(v, u, v) if isinstance(v, (list, tuple)) and len(v) == 4 and all(isinstance(x, (int, float)) for x in v) else v
    return out

def apply_cut(shot, T, span):
    """shot['cuts'] = [{"at": seconds, ...overrides}] -> (effective shot, local T, local duration)"""
    cuts = shot.get('cuts') or []
    cur = None
    for c in cuts:
        if T >= float(c.get('at', 0)): cur = c
    if cur is None:
        first = min([float(c.get('at', 0)) for c in cuts] + [span])
        return shot, T, first
    eff = dict(shot); eff.update({k: v for k, v in cur.items() if k != 'at'})
    nxt = [float(c.get('at', 0)) for c in cuts if float(c.get('at', 0)) > float(cur.get('at', 0))]
    end = min(nxt) if nxt else span
    return eff, T - float(cur.get('at', 0)), end - float(cur.get('at', 0))

SHAKE = .35
def shake_offsets(T, a, f=1.):
    a *= SHAKE
    return (a * (math.sin(T * 37.1 * f) + .6 * math.sin(T * 23.7 * f + 1.3)),
            a * (math.sin(T * 31.3 * f + 2) + .6 * math.sin(T * 19.1 * f)),
            a * .6 * math.sin(T * 27.7 * f + .5))

FACE_KINDS = A.FACE_KINDS
DEFAULT_CAST = {
    'hero': {}, 'double': {}, 'boy': {},
    'creature': dict(hood=(22, 22, 26), jeans=(14, 14, 18), hair=(8, 8, 10), skin=(176, 160, 150), eyes=(255, 40, 40), kind='creature'),
}

class Timeline:
    """line timings -> shot spans"""
    def __init__(self, episode, lines, duration):
        self.ep = episode; self.lines = lines; self.duration = duration
        self.shots = episode['shots']
        n = len(lines)
        self.spans = []
        for k, s in enumerate(self.shots):
            l0, l1 = s['lines']
            pre = s.get('pre', .12)
            t0 = lines[l0]['start'] - pre if l0 > 0 else 0.
            nxt = None
            for s2 in self.shots[k + 1:]:
                nxt = s2; break
            if nxt is not None:
                t1 = (lines[nxt['lines'][0]]['start'] - nxt.get('pre', .12)) if nxt['lines'][0] > 0 else 0.
            else:
                t1 = duration
            self.spans.append((t0, max(t1, t0 + 1 / 30)))
    def at(self, g):
        for k, (a, b) in enumerate(self.spans):
            if a <= g < b: return k, a, b
        return len(self.spans) - 1, self.spans[-1][0], self.spans[-1][1]

class FrameContext:
    def __init__(self, episode, lines, env, duration):
        self.ep = episode; self.lines = lines; self.env = env; self.duration = duration
        self.tl = Timeline(episode, lines, duration)
        self.sets = {}
        self.anchor_cache = {}
        custom = episode.get('sets', {}) or {}
        self.set_specs = custom
        self._acting = None; self.cam_memory = {}; self.cam_cache = {}
    def get_acting(self):
        """shared action timeline (acting/timeline.py) for the shots that use actions / engine_version 2"""
        if self._acting is None:
            from ...acting.timeline import Acting
            from .stage import SetWorld
            def world_of(name, shot): return SetWorld(self.get_set(name or 'etage_zero'), shot, self.ep, self.set_specs.get(name or 'etage_zero'))
            self._acting = Acting(self.ep, self.tl.spans, self.lines, world_of, self.ep.get('cast'))
        return self._acting
    def get_set(self, name):
        if name not in self.sets:
            spec = dict(self.set_specs.get(name, {}))
            if 'type' not in spec:
                from .places import PLACES
                spec['type'] = name if (name in ('etage_zero', 'apartment', 'pompe_station', 'theatre_bal', 'hotel_nuit') or name in PLACES) else 'room'
            self.sets[name] = make_set(name, spec)
        return self.sets[name]
    def mouth(self, g):
        k = int(g * 30)
        return float(self.env[min(max(k, 0), len(self.env) - 1)]) if len(self.env) else 0.

def anchor_xz(st, a, default=(0, 0)):
    if a is None: return default
    if isinstance(a, (list, tuple)):
        return (float(a[0]), float(a[-1])) if len(a) in (2, 3) else default
    if isinstance(a, str):
        if a in st.anchors: return st.anchors[a]
        for k, v in st.anchors.items():         # tolerant match
            if k.lower() == a.lower() or k.split('.')[-1] == a: return v
    return default

def anchor_xyz(st, a, actors, y_default=1.4):
    """anchor name | actor id(.head/.chest/.feet) | [x, z] | [x, y, z]"""
    if isinstance(a, (list, tuple)):
        return (float(a[0]), float(a[1]), float(a[2])) if len(a) == 3 else (float(a[0]), y_default, float(a[1]))
    if isinstance(a, str):
        base, _, part = a.partition('.')
        if base in actors:
            ac = actors[base]; s = ac['scale']
            # bodies.head_y: 1.68 / 1.70 are the stock head joint and its eyes. With the body refit on (opt-in)
            # the skull is smaller and sits higher, so these two -- and only these two -- follow it. Identity,
            # to the bit, without the key: the chest, the hands and the feet never move.
            y = {'head': bodies.head_y(1.68), 'eyes': bodies.head_y(1.7), 'chest': 1.3, 'hands': 1.0, 'feet': .15, '': 1.6}.get(part, 1.6) * s + ac['yoff']
            return (ac['x'], y, ac['z'])
        x, z = anchor_xz(st, a)
        return (x, y_default, z)
    return (0., y_default, 0.)

# ------------------------------------------------------------------ actors
def eval_actors(ctx, shot, st, T, u, g):
    out = {}
    for a in shot.get('actors', []) or []:
        aid = a.get('id', 'hero')
        look = dict(DEFAULT_CAST.get(aid, {})); look.update((ctx.ep.get('cast', {}) or {}).get(aid, {}))
        pre = look.get('preset') or look.get('kind')
        if pre in CR.PRESETS: look = dict(CR.PRESETS[pre], **{k_: v_ for k_, v_ in look.items() if k_ != 'kind'})   # zombie, knight, astronaut...
        if 'creature' in aid and 'kind' not in look: look.update(DEFAULT_CAST['creature'])
        s0, s1 = a.get('start', 0.), a.get('end', 1.)
        k = ease((u - s0) / max(1e-3, s1 - s0)) if a.get('to') is not None else 0.
        if a.get('ease') == 'linear' and a.get('to') is not None: k = clamp((u - s0) / max(1e-3, s1 - s0))
        x0, z0 = anchor_xz(st, a.get('at'), (0, 0))
        if a.get('to') is not None:
            x1, z1 = anchor_xz(st, a.get('to'), (x0, z0)); x, z = lerp(x0, x1, k), lerp(z0, z1, k)
        else: x, z = x0, z0
        x += float(a.get('dx', 0)); z += float(a.get('dz', 0))
        moving = a.get('to') is not None and s0 <= u <= s1
        mv = a.get('move', 'walk' if moving else 'still')
        if mv == 'run': sw = .5 * math.sin(g * 13) if moving or a.get('move') == 'run' else 0
        elif mv == 'walk': sw = .22 * math.sin(g * 6) if moving else 0
        elif mv == 'stumble': sw = .3 * math.sin(g * 9)
        else: sw = 0
        if mv == 'run' and not moving and a.get('move') == 'run': sw = .5 * math.sin(g * 13)
        sc_ = float(look.get('scale', a.get('scale', 1.0)))
        out[aid] = dict(spec=a, look=look, x=x, z=z, swing=sw, scale=sc_, yoff=float(val(a.get('y'), u, 0.) or 0.), moving=moving)
    return out

def actor_face(ctx, a, look, g, u, T):
    kind = a.get('face', look.get('face', 'creature' if look.get('kind') == 'creature' else 'neutral'))
    for ch in a.get('face_changes', []) or []:              # [{"at": seconds, "face": "grin"}]
        if T >= float(ch.get('at', 1e9)): kind = ch.get('face', kind)
    if kind not in FACE_KINDS: kind = 'neutral'
    mouth = 0.
    if a.get('lipsync'): mouth = int(ctx.mouth(g) * 4) / 4.
    elif a.get('mouth') is not None:
        mouth = float(val(a.get('mouth'), u, 0.))
        if a.get('laugh'): mouth = .5 + .5 * math.sin(g * 26)
    if a.get('laugh') and a.get('mouth') is None: mouth = .5 + .5 * math.sin(g * 26)
    if kind == 'talk' and not a.get('lipsync'): kind = 'neutral'
    smile = float(val(a.get('smile'), u, .8))
    crack = float(val(a.get('crack'), u, .5 if kind == 'creature' else 0.))
    if kind == 'creature' and a.get('grin_grow'): smile = .25 + .75 * round(u * 6) / 6
    tilt = int(val(a.get('tilt'), u, 0.) or 0)
    skin = tuple(look.get('skin', A.SKIN)); hair = tuple(look.get('hair', A.HAIR))
    gaze = a.get('gaze') if a.get('gaze') in A.GAZE else None
    gl = a.get('glasses', look.get('glasses')); gl = gl if gl in (True, 'glasses', 'round', 'sun', 'sunglasses') else None
    bd = a.get('beard', look.get('beard')); bd = bd if bd in (True, 'full', 'beard', 'mustache', 'stubble') else None
    return A.face_tex(kind, mouth, round(smile, 2), round(crack, 2), skin=skin, hair=hair, tilt=tilt, gaze=gaze, glasses=gl, beard=bd,
                      bald=look.get('hair_style') == 'bald')

_YAW_X = {'+x': np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], np.float32), '-x': np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], np.float32),
          '-z': np.array([[-1, 0, 0], [0, 1, 0], [0, 0, -1]], np.float32)}
def place_actor(bx, x, z, y, fc, cam_z, lights=None, out_lights=None):
    """boxes built at the origin facing +z -> turned towards fc and moved to (x, y, z)"""
    if fc in ('camera', 'away', None): fc = ('+z' if cam_z > z else '-z') if fc != 'away' else ('-z' if cam_z > z else '+z')
    if fc in (1, '1'): fc = '+z'
    if fc in (-1, '-1'): fc = '-z'
    R = _YAW_X.get(fc)
    if R is not None:
        bx = P._rotate(bx, R, lambda a_, b_, t: np.ascontiguousarray(np.rot90(t, 2)) if fc == '-z' and b_ in (2, 3) else t)
    off = np.array([x, y, z], np.float32)
    for b in bx: b.lo = b.lo + off; b.hi = b.hi + off
    if lights and out_lights is not None:
        for p_, c_, pw, r_ in lights:
            q = np.asarray(p_, np.float32); q = (R @ q if R is not None else q) + off; out_lights.append((tuple(float(v) for v in q), c_, pw, r_))
    return bx

def actor_kwargs(a, look, ac, g, u, lights):
    lk = lambda key: a.get(key, look.get(key))
    gest = a.get('gesture') if a.get('gesture') in P.GESTURES else None
    post = a.get('posture') if a.get('posture') in P.POSTURES else None
    item = lk('hold') if lk('hold') in P.HOLD_ITEMS else None
    return dict(hood=tuple(look.get('hood', A.HOOD)), jeans=tuple(look.get('jeans', A.JEANS)), hair=tuple(look.get('hair', A.HAIR)), skin=tuple(look.get('skin', A.SKIN)),
                swing=ac['swing'] * (1 if a.get('move') != 'still' else 0) if post in (None, 'stand') else 0., armsw=ac['swing'] * .7,
                hidden=bool(a.get('reflection_only')), noref=bool(a.get('no_reflection')), dissolve=float(val(a.get('dissolve'), u, 0.) or 0.), yoff=ac['yoff'],
                eyes=tuple(look['eyes']) if look.get('eyes') else None, headphones=look.get('headphones', True), backpack=look.get('backpack', True),
                hair_long=look.get('hair_long', False), scale=ac['scale'], shirt=tuple(look['shirt']) if look.get('shirt') else None,
                gesture=gest or ('idle' if post or item else None), posture=post, hold=item, hold_color=tuple(a['hold_color']) if a.get('hold_color') else None, g=g,
                outfit=lk('outfit') if lk('outfit') in P.OUTFITS else None, hair_style=lk('hair_style') if lk('hair_style') in P.HAIR_STYLES else None,
                hat=lk('hat') if lk('hat') in P.HATS else None, hat_color=tuple(lk('hat_color')) if lk('hat_color') else None, tie=tuple(lk('tie')) if lk('tie') else None,
                lie_head=a.get('head_to', '-x'), lights=lights, cape=tuple(lk('cape')) if lk('cape') else None, pose=None, arm_up=0.)

def actor_boxes(ctx, actors, cam_z, g, u, T, pov_id=None):
    bx = []; extra_lights = []
    for aid, ac in actors.items():
        a = ac['spec']; look = ac['look']
        if aid == pov_id: continue
        fc = a.get('facing', 'camera')
        if look.get('kind') in CR.ANIMALS:                     # animals and fantasy creatures
            if a.get('visible') is not None and not (a['visible'][0] <= T <= a['visible'][1]): continue
            k_ = dict(hidden=bool(a.get('reflection_only')), noref=bool(a.get('no_reflection')), dissolve=float(val(a.get('dissolve'), u, 0.) or 0.))
            ab = CR.animal(look['kind'], look.get('color'), ac['swing'] * (1 if a.get('move') != 'still' else 0), g, k_, a.get('posture'), float(look.get('size', ac['scale'])))
            bx += place_actor(ab, ac['x'], ac['z'], ac['yoff'], fc, cam_z); continue
        if fc in ('+x', '-x'):                                 # side view: build facing +z, then turn
            lts = []
            kwx = actor_kwargs(a, look, ac, g, u, lts)
            fb = A.figure(0., 0., 1, actor_face(ctx, a, look, g, u, T), **kwx)
            bx += place_actor(fb, ac['x'], ac['z'], 0., fc, cam_z, lights=lts, out_lights=extra_lights); ac['facing'] = fc; continue
        if fc in ('+z', 1, '1'): f = 1
        elif fc in ('-z', -1, '-1'): f = -1
        elif fc == 'away': f = -1 if cam_z > ac['z'] else 1
        else: f = 1 if cam_z > ac['z'] else -1
        ac['facing'] = f
        if a.get('visible') is not None:
            v0, v1 = a['visible']
            if not (v0 <= T <= v1): continue
        diss = float(val(a.get('dissolve'), u, 0.) or 0.)
        face = actor_face(ctx, a, look, g, u, T)
        kw = dict(hood=tuple(look.get('hood', A.HOOD)), jeans=tuple(look.get('jeans', A.JEANS)), hair=tuple(look.get('hair', A.HAIR)),
                  skin=tuple(look.get('skin', A.SKIN)), swing=ac['swing'] * (1 if a.get('move') != 'still' else 0), armsw=ac['swing'] * .7,
                  hidden=bool(a.get('reflection_only')), noref=bool(a.get('no_reflection')), dissolve=diss, yoff=ac['yoff'],
                  pose=a.get('pose') if a.get('pose') in ('chest', 'extend') else None, arm_up=1. if a.get('pose') == 'arm_up' else 0.,
                  eyes=tuple(look['eyes']) if look.get('eyes') else None, headx=float(val(a.get('head_x'), u, 0.) or 0.),
                  heady=float(val(a.get('head_y'), u, 0.) or 0.), headphones=look.get('headphones', look.get('kind') != 'creature' or True),
                  backpack=look.get('backpack', True), hair_long=look.get('hair_long', False), scale=ac['scale'], shirt=tuple(look['shirt']) if look.get('shirt') else None)
        # body language and looks (poses.py); absent keys keep the original figure
        gest = a.get('gesture') if a.get('gesture') in P.GESTURES else None
        post = a.get('posture') if a.get('posture') in P.POSTURES else None
        item = a.get('hold', look.get('hold')) if a.get('hold', look.get('hold')) in P.HOLD_ITEMS else None
        lk = lambda key: a.get(key, look.get(key))
        kw.update(gesture=gest, posture=post, hold=item, hold_color=tuple(a['hold_color']) if a.get('hold_color') else None, g=g,
                  outfit=lk('outfit') if lk('outfit') in P.OUTFITS else None, hair_style=lk('hair_style') if lk('hair_style') in P.HAIR_STYLES else None,
                  hat=lk('hat') if lk('hat') in P.HATS else None, hat_color=tuple(lk('hat_color')) if lk('hat_color') else None,
                  tie=tuple(lk('tie')) if lk('tie') else None, lie_head=a.get('head_to', '-x'), lights=extra_lights, cape=tuple(lk('cape')) if lk('cape') else None)
        if gest or post or item: kw['swing'] = kw['swing'] if post in (None, 'stand') else 0.
        bx += A.figure(ac['x'], ac['z'], f, face, **kw)
        if look.get('kind') == 'creature' or a.get('red_glow'):
            extra_lights.append(((ac['x'], 1.1, ac['z'] + f * 1.1), (1, .12, .08), .5 * float(a.get('glow', .9)), 1.4))
    return bx, extra_lights

# ------------------------------------------------------------------ camera
def look_angles(p, t):
    dx, dy, dz = t[0] - p[0], t[1] - p[1], t[2] - p[2]
    return math.atan2(dx, dz), math.atan2(dy, math.hypot(dx, dz) + 1e-6)

def eval_camera(ctx, shot, st, actors, T, u, g):
    c = shot.get('camera', {}) or {}
    pre = c.get('preset', 'wide'); mv = c.get('move', 'static'); amt = float(c.get('amount', 1.0)); e = ease(u)
    subj = c.get('subject'); sa = actors.get(subj) if subj else None
    fov = c.get('fov')
    def facing_of(ac):
        fc = ac['spec'].get('facing', 'camera')
        return 1 if fc in ('+z', 1) else (-1 if fc in ('-z', -1) else None)
    def xfacing(ac):
        fc = ac['spec'].get('facing') if ac else None
        return 1 if fc == '+x' else (-1 if fc == '-x' else None)
    tgt_spec = c.get('target')
    pov_id = None
    if pre in ('closeup', 'medium', 'full') and sa:
        s = sa['scale']; f = facing_of(sa)
        if f is None: f = 1
        dist = float(c.get('dist', {'closeup': .78, 'medium': 1.6, 'full': 3.0}[pre]))
        hy = {'closeup': bodies.head_y(1.68), 'medium': 1.45, 'full': 1.2}[pre] * s + sa['yoff']
        pos = [sa['x'] + float(c.get('side', 0)), hy + float(c.get('height', 0)) - (0 if pre == 'closeup' else .0), sa['z'] + f * dist]
        if xfacing(sa): pos = [sa['x'] + xfacing(sa) * dist, pos[1], sa['z'] + float(c.get('side', 0))]
        tgt = [sa['x'], {'closeup': bodies.head_y(1.67), 'medium': 1.4, 'full': 1.1}[pre] * s + sa['yoff'], sa['z']]
        fov = fov if fov is not None else {'closeup': 52, 'medium': 64, 'full': 72}[pre]
    elif pre == 'ots' and sa:
        f = facing_of(sa) or 1
        pos = [sa['x'] + float(c.get('side', .32)), 1.78 * sa['scale'] + float(c.get('height', 0)), sa['z'] - f * float(c.get('dist', .85))]
        tgt = list(anchor_xyz(st, tgt_spec, actors, 1.6)) if tgt_spec else [sa['x'], 1.6, sa['z'] + f * 4]
        if xfacing(sa):
            xf = xfacing(sa); pos = [sa['x'] - xf * float(c.get('dist', .85)), pos[1], sa['z'] + float(c.get('side', .32))]
            if not tgt_spec: tgt = [sa['x'] + xf * 4, 1.6, sa['z']]
        fov = fov if fov is not None else 74
    elif pre == 'pov':
        if sa:
            pov_id = subj
            pos = [sa['x'], 1.62 * sa['scale'] + sa['yoff'] + float(c.get('height', 0)), sa['z']]
            f = facing_of(sa) or 1
            tgt = list(anchor_xyz(st, tgt_spec, actors, 1.6)) if tgt_spec else ([pos[0] + xfacing(sa) * 5, pos[1], pos[2]] if xfacing(sa) else [pos[0], pos[1], pos[2] + f * 5])
        else:
            fx, fz = anchor_xz(st, c.get('from'), (0, 0)); pos = [fx, 1.6 + float(c.get('height', 0)), fz]
            tgt = list(anchor_xyz(st, tgt_spec, actors, 1.6)) if tgt_spec else [fx, 1.6, fz + 5]
        fov = fov if fov is not None else 88
    elif pre == 'insert':
        tgt = list(anchor_xyz(st, tgt_spec or c.get('from'), actors, float(c.get('target_y', 1.1))))
        d = float(c.get('dist', .7)); ang = float(c.get('angle', 180)) * D2R
        pos = [tgt[0] + math.sin(ang) * d, tgt[1] + float(c.get('height', .15)), tgt[2] + math.cos(ang) * d]
        fov = fov if fov is not None else 70
    elif pre == 'free' and c.get('keys'):
        ks = c['keys']; k0 = ks[0]; k1 = ks[-1] if len(ks) > 1 else ks[0]
        p0 = k0.get('pos', [0, 1.6, 0]); p1 = k1.get('pos', p0)
        pos = [lerp(p0[i], p1[i], e) for i in range(3)]
        t0_ = k0.get('look', [0, 1.6, 5]); t1_ = k1.get('look', t0_)
        tgt = [lerp(t0_[i], t1_[i], e) for i in range(3)]
        fov = lerp(k0.get('fov', 75), k1.get('fov', k0.get('fov', 75)), e) if fov is None else fov
    else:   # wide / high_corner / low
        fx, fz = anchor_xz(st, c.get('from'), None) if c.get('from') is not None else (None, None)
        if fx is None:
            if sa:
                f = facing_of(sa) or 1; fx, fz = sa['x'] + .2, sa['z'] + f * 3.2
                if xfacing(sa): fx, fz = sa['x'] + xfacing(sa) * 3.2, sa['z'] + .2
            else: fx, fz = 0, 0
        y = {'high_corner': 2.35, 'low': .45}.get(pre, 1.6) + float(c.get('height', 0))
        if isinstance(c.get('from'), (list, tuple)) and len(c['from']) == 3: y = float(c['from'][1])
        pos = [fx + float(c.get('side', 0)), y, fz]
        if tgt_spec is not None: tgt = list(anchor_xyz(st, tgt_spec, actors, 1.5 if pre != 'low' else 1.3))
        elif sa: tgt = [sa['x'], 1.4 * sa['scale'], sa['z']]
        else:
            d_ = 1 if c.get('look', '+z') in ('+z', 'forward') else -1
            tgt = [pos[0], 1.5, pos[2] + d_ * 6]
        fov = fov if fov is not None else {'high_corner': 96, 'low': 80}.get(pre, 82)
    if isinstance(fov, (list, tuple)): fov = lerp(fov[0], fov[1], e)
    fov = float(fov)
    # camera moves
    dirv = np.array(tgt, float) - np.array(pos, float); dn = np.linalg.norm(dirv) + 1e-6; dirv /= dn
    if mv in ('dolly_in', 'dolly_out'):
        d = .6 * amt * (e if mv == 'dolly_in' else -e)
        d = min(d, dn - .25)
        pos = list(np.array(pos) + dirv * d)
    elif mv in ('push_in', 'pull_out'):
        fov *= (1 - .3 * amt * e) if mv == 'push_in' else (1 + .3 * amt * e)
    elif mv in ('crane_up', 'crane_down'):
        pos[1] += (.8 if mv == 'crane_up' else -.8) * amt * e
    elif mv in ('track_left', 'track_right'):
        side = np.array([dirv[2], 0, -dirv[0]]); sgn = 1 if mv == 'track_right' else -1
        pos = list(np.array(pos) + side * sgn * .8 * amt * (e - .5))
    yaw, pitch = look_angles(pos, tgt)
    if mv in ('pan_left', 'pan_right'): yaw += (1 if mv == 'pan_right' else -1) * 25 * D2R * amt * (e - .5)
    elif mv in ('tilt_up', 'tilt_down'): pitch += (1 if mv == 'tilt_up' else -1) * 25 * D2R * amt * (e - .5)
    elif mv in ('orbit_left', 'orbit_right'):
        ang = (1 if mv == 'orbit_right' else -1) * 40 * D2R * amt * (e - .5)
        r = np.array(pos) - np.array(tgt); ca, sa_ = math.cos(ang), math.sin(ang)
        pos = [tgt[0] + r[0] * ca + r[2] * sa_, pos[1], tgt[2] - r[0] * sa_ + r[2] * ca]; yaw, pitch = look_angles(pos, tgt)
    elif mv == 'look_around':
        yaw += float(c.get('look_deg', 55)) * D2R * math.sin(clamp(u) * 2 * math.pi) * amt
        pitch += 4 * D2R * math.sin(u * math.pi)
    elif mv == 'whip_turn':                               # turn around (POV) in the first ~0.5 s
        k = ease(T / max(.2, float(c.get('turn_time', .55)))); yaw = yaw + math.pi * (1 - k)
    yaw += float(c.get('yaw', 0)) * D2R; pitch += float(val(c.get('pitch'), u, 0.) or 0.) * D2R
    roll = float(val(c.get('roll'), u, 0.) or 0.) * D2R
    shk = float(val(c.get('shake'), u, 0.) or 0.) + (.05 if mv == 'handheld' else 0)
    if c.get('walk_bob'): pos[1] += float(c['walk_bob']) * abs(math.sin(g * 13))
    s = shake_offsets(T, shk, float(c.get('shake_freq', 1.)))
    cam = ((pos[0] + s[0] * .1, pos[1] + s[1] * .1, pos[2] + s[2] * .05), yaw + s[0] * .02, pitch + s[1] * .02, roll + s[2] * .03, fov)
    return cam, pov_id

# ------------------------------------------------------------------ objects
def eval_objects(ctx, shot, st, actors, cam, T, u, g):
    out = []; lights = []
    pos, yaw, pitch, roll, fov = cam
    fwd = (math.sin(yaw), math.cos(yaw))
    for o in shot.get('objects', []) or []:
        typ = o.get('type')
        if typ == 'phone':
            d = float(o.get('dist', .5)); lift = ease(clamp(T / float(o.get('lift', .001) or .001))) if o.get('lift') else 1.
            vib = float(o.get('vibrate', 0)) * .012 * math.sin(g * 90)
            x, y, z = pos[0] + fwd[0] * d + vib, pos[1] - .08 - (1 - lift) * .6 + float(o.get('dy', 0)), pos[2] + fwd[1] * d
            sgn = 1 if fwd[1] >= 0 else -1; face = '-z' if sgn > 0 else '+z'
            msgs = tuple(o.get('messages', []))
            k = o.get('reveal')                      # progressive messages: number of messages shown grows over the shot
            if k: msgs = msgs[:max(1, int(math.ceil(len(msgs) * clamp(u * 1.3))))]
            hdr = str(o.get('header', 'INCONNU')).upper()
            if o.get('header_after') and T >= float(o.get('header_switch', .25)): hdr = str(o['header_after']).upper()
            elif o.get('header_after') and int(g * 30) % 2: hdr = hdr[:3] + '#' + hdr[4:]
            tex = A.phone_tex(hdr, tuple(m.upper() for m in msgs), bool(o.get('typing')), bool(o.get('highlight_last')))
            out += [C((x, y, z), (.27, .47, .012), (20, 22, 40), tex={face: tex}, texemis=1.15, cast=False),
                    C((x, y, z + sgn * .012), (.3, .52, .02), (24, 24, 28), cast=False),
                    C((x - .16, y - .12, z + sgn * .01), (.07, .2, .06), A.SKIN, cast=False), C((x + .16, y - .14, z + sgn * .01), (.07, .18, .06), A.SKIN, cast=False),
                    C((x, y - .29, z + sgn * .02), (.22, .08, .07), A.SKIN, cast=False)]
            lights.append(((x, y, z - sgn * .3), (.5, .6, 1.0), .5, 1.0))
        elif typ == 'arm':                         # an arm reaching from the camera towards a point (press a button, grab...)
            tgt = anchor_xyz(st, o.get('target'), actors, float(o.get('target_y', 1.1)))
            k = ease(clamp((T - float(o.get('start', 0))) / float(o.get('time', .5))))
            hx = lerp(pos[0] + fwd[0] * .3 + .25, tgt[0], k * float(o.get('reach', .95))); hy = lerp(pos[1] - .5, tgt[1], k * float(o.get('reach', .95)))
            hz = lerp(pos[2] + fwd[1] * .3, tgt[2], k * float(o.get('reach', .95)))
            out.append(C((hx, hy, hz), (.14, .13, .18), A.SKIN))
            sx, sy, sz = pos[0] + .3, pos[1] - .7, pos[2]
            for i in range(1, 4):
                f_ = i / 4; out.append(C((lerp(sx, hx, f_), lerp(sy, hy, f_), lerp(sz, hz, f_)), (.14, .14, .14), A.HOOD))
        elif typ == 'debris':
            c_ = anchor_xz(st, o.get('at'), (pos[0], pos[2] + 2 * fwd[1])); r = np.random.default_rng(int(o.get('seed', 1)))
            t0 = float(o.get('start', 0))
            for i in range(int(o.get('count', 18))):
                ts = t0 + r.uniform(0, 3.0); tt = T - ts
                if tt < 0: continue
                x = c_[0] + r.uniform(-1.6, 1.6); z = c_[1] + r.uniform(-2.5, 2.5); y = max(.03, 2.55 - 4.9 * tt * tt)
                big = r.random() < .35
                out.append(C((x, y, z), (.5, .04, .5) if big else (.06, .06, .06), (120, 118, 110) if big else (150, 146, 136), cast=big))
        elif typ == 'dust':
            c_ = anchor_xz(st, o.get('at'), (pos[0], pos[2])); r = np.random.default_rng(int(o.get('seed', 3)))
            for i in range(int(o.get('count', 40))):
                x = c_[0] + r.uniform(-1.6, 1.6); z = c_[1] + r.uniform(-3, 1); sp = r.uniform(.2, .6); ph = r.uniform(0, 2.6)
                out.append(C((x, 2.55 - ((g * sp + ph) % 2.6), z), (.018, .018, .018), (200, 196, 186), cast=False))
        elif typ == 'glass_burst':
            c_ = anchor_xyz(st, o.get('at', 'mirror'), actors, 1.3); t0 = float(o.get('start', 0)); tt = T - t0
            if tt >= 0:
                r = np.random.default_rng(2); dz = float(o.get('dir', 1))
                for i in range(40):
                    p = np.array([c_[0] + r.uniform(-.8, .8), r.uniform(.6, 2.2), c_[2]]); v = np.array([r.uniform(-1.5, 1.5), r.uniform(-.5, 2.5), dz * r.uniform(1.5, 5.5)])
                    q = p + v * tt + np.array([0, -4.9 * tt * tt, 0]); q[1] = max(q[1], .03)
                    out.append(C(tuple(q), (.07, .07, .03), (225, 235, 245), refl=.6, emis=.5))
        elif typ == 'eyes':                        # two glowing eyes in the dark
            c_ = anchor_xyz(st, o.get('at'), actors, float(o.get('y', 1.65)))
            col = tuple(o.get('color', (255, 40, 40)))
            if not o.get('blink') or (g * 1.3) % 3 > .15:
                out += [C((c_[0] - .08, c_[1], c_[2]), (.05, .05, .02), col, emis=3.5, cast=False), C((c_[0] + .08, c_[1], c_[2]), (.05, .05, .02), col, emis=3.5, cast=False)]
        elif typ == 'prop':
            from .sets import prop_boxes, place
            x, z = anchor_xz(st, o.get('at'), (0, 0))
            out += place(prop_boxes(o.get('kind', 'crate'), o), x, z, int(o.get('rot', 0)))
        elif typ == 'light':
            p_ = anchor_xyz(st, o.get('at'), actors, float(o.get('y', 2.0)))
            k = float(o.get('power', 1.0))
            if o.get('flicker') and ((int(g * 10) * 2654435761) & 0xffff) / 65535. > .6: k *= .2
            lights.append((p_, tuple(o.get('color', (1, .9, .75))), k, float(o.get('radius', 2.5))))
        elif typ == 'hands_push':                  # two hands pushing forward from the camera
            k = abs(math.sin(T * float(o.get('rate', 9))))
            z0 = pos[2] + fwd[1] * (.55 + .1 * k); x0 = pos[0] + fwd[0] * (.55 + .1 * k)
            out += [C((x0 - .15, pos[1] - .6, z0), (.16, .14, .2), A.SKIN), C((x0 + .15, pos[1] - .6, z0), (.16, .14, .2), A.SKIN),
                    C((x0 - .3, pos[1] - .75, z0 - fwd[1] * .55), (.14, .14, .9), A.HOOD), C((x0 + .3, pos[1] - .75, z0 - fwd[1] * .55), (.14, .14, .9), A.HOOD)]
        elif typ in FX.EFFECTS:                    # V3 effects registry (effects.py, extensions): lightning, collapse, movers...
            bx, lt = FX.EFFECTS[typ](FX.Fx(ctx, shot, st, actors, cam, T, u, g), o)
            out += bx; lights += lt
    return out, lights

def without_hidden(ctx, boxes):
    """static boxes removed by an effect this frame (a collapsing building is drawn by the effect)"""
    hs = getattr(ctx, 'hide_static', None)
    return [b for b in boxes if id(b) not in hs] if hs else boxes

def with_shadows(L, cam_pos, n=2):
    p = np.asarray(cam_pos, np.float32)
    sc_ = [li / (1 + float(((np.asarray(lp) - p) ** 2).sum()) / (lr * lr)) for (lp, lc, li, lr, *_) in L]
    top = set(np.argsort(sc_)[::-1][:n].tolist())
    return [tuple(l[:4]) + ((i in top),) + tuple(l[5:]) for i, l in enumerate(L)]

def resolve_look(ctx, aid):
    look = dict(DEFAULT_CAST.get(aid, {})); look.update((ctx.ep.get('cast', {}) or {}).get(aid, {}))
    pre = look.get('preset') or look.get('kind')
    if pre in CR.PRESETS: look = dict(CR.PRESETS[pre], **{k_: v_ for k_, v_ in look.items() if k_ != 'kind'})
    if 'creature' in aid and 'kind' not in look: look.update(DEFAULT_CAST['creature'])
    elif look.get('kind') == 'creature': look = dict(DEFAULT_CAST['creature'], **look)
    return look

def build_frame(ctx, g):
    """-> (scene, cam, lights, shot, T, u, shot_index)"""
    k, t0, t1 = ctx.tl.at(g)
    shot0 = ctx.ep['shots'][k]
    shot, T, span = apply_cut(shot0, g - t0, t1 - t0)
    u = clamp(T / max(1e-3, span)); CUR_T[0] = T; W.TIME[0] = g
    ctx.hide_static = set(); ctx.fx_flash = 0.                 # set by effects during this frame
    st = ctx.get_set(shot.get('set', ctx.ep.get('default_set', 'etage_zero')))
    state = dict(ctx.ep.get('state', {}) or {}); state.update(shot.get('state', {}) or {})
    state = apply_state_track(shot, resolve_state(state, u), T)
    acting = ctx.get_acting()
    if k in acting.shots:
        from .acted import build_acted
        return build_acted(ctx, acting.shots[k], shot, st, state, g, g - t0, clamp((g - t0) / max(1e-3, t1 - t0)), k)
    actors = eval_actors(ctx, shot, st, T, u, g)
    cam, pov_id = eval_camera(ctx, shot, st, actors, T, u, g)
    sc = st.scene(state, g, u)
    abx, alights = actor_boxes(ctx, actors, cam[0][2], g, u, T, pov_id)
    obx, olights = eval_objects(ctx, shot, st, actors, cam, T, u, g)
    sc.boxes = without_hidden(ctx, sc.boxes) + abx + obx
    if shot.get('fog') is not None: sc.fogk = float(shot['fog'])
    Lset = st.lights(state, g, u, cam[0])
    L = Lset + alights + olights
    for l in (shot.get('lights') or []):
        p_ = anchor_xyz(st, l.get('at'), actors, float(l.get('y', 2.0)))
        L.append((p_, tuple(l.get('color', (1, .9, .75))), float(l.get('power', 1.0)), float(l.get('radius', 2.5))))
    if hasattr(st, 'stage_frame'):            # lumière de scène d'un théâtre (theatre.py, clé `stage_light`) : seul ce lieu a la méthode
        L = st.stage_frame(ctx, k, shot, {a: (v['x'], v['yoff'], v['z']) for a, v in actors.items()}, cam, sc, L, len(Lset), T, u, g, state)
    L, lx = LT.plan(ctx, shot, st, actors, cam, sc, L, len(Lset), T, u, g)   # V3: narrative lighting intention (opt-in)
    L = [l for l in L if l[2] > 1e-3]
    return sc, cam, with_shadows(L, cam[0]) + [l for l in lx if l[2] > 1e-3], shot, T, u, k, state
