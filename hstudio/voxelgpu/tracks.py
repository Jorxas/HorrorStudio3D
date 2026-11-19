"""Direct tracks: a shot whose actors are written as KEYFRAMES instead of verbs ("tracks"), for scenes that must be staged
exactly (a remake of a given film, a storyboard, a creature that only stands and turns its head).

It is the same contract as the régie's: `TrackActing.sample(t)` returns, for every actor, the dict that
`director.RowMaker.row` already reads (x, z, y, heading, face, talking, visible, rig{...}), so gait phase driven by distance,
the arms through B's gesture library, the head, the sit and the expression all come out of the existing code path. Nothing is
random and nothing reads a clock.

    "tracks": {
      "lea": [ {"t": 0,   "p": [x, y, z], "yaw": 3.14, "face": "scared", "talk": 0, "head": [yaw, pitch], "vis": 1,
                "gesture": "point", "gw": 1, "sit": 0, "crouch": 0, "air": 0, "lean": 0, "run": 0, "hands": "fist"},
               {"t": 2.0, "p": [x2, y, z2]} ]
    }

A key only has to say what changes: numbers (p, yaw, head, gw, sit, crouch, air, lean, run) are interpolated (smoothstep) from key to key,
names (face, gesture, hands) and flags (talk, vis) hold until the next key that sets them. Yaw is B's heading, atan2(dx, dz):
0 faces +z (the camera side of A's worlds). `"cut": true` on a key makes numbers JUMP to it instead of gliding (a teleport inside the shot).
"""
import math


def _sm(k): k = max(0., min(1., k)); return k * k * (3 - 2 * k)


def _wrap(a): return (a + math.pi) % (2 * math.pi) - math.pi


NUM = ('yaw', 'gw', 'sit', 'crouch', 'air', 'lean', 'run', 'slump', 'tension')
HOLD = ('face', 'gesture', 'hands', 'talk', 'vis', 'back')


class TrackActing:
    """stand-in for acting.timeline.ShotActing for a shot written with keyframes"""

    def __init__(self, shot, dur, casts):
        self.dur = float(dur); self.lines = []; self.tracks = {}; self.world = None; self.keys = {}
        for aid, keys in (shot.get('tracks') or {}).items():
            ks = sorted((dict(k) for k in keys), key=lambda k: float(k['t']))
            if not ks: continue
            for k in ks: k['t'] = float(k['t'])
            if 'p' not in ks[0]: raise ValueError(f"piste {aid!r} : la première clé doit donner la position `p`")
            self.keys[aid] = ks; self.tracks[aid] = None

    def end_states(self): return {}

    def _state(self, ks, t):
        """numeric fields interpolated between the keys that set them, names / flags held from the last key that set them"""
        out = {}
        for name in ('p', 'head') + NUM:
            pts = [(k['t'], k[name], bool(k.get('cut'))) for k in ks if name in k]
            if not pts: continue
            i = 0
            while i + 1 < len(pts) and pts[i + 1][0] <= t: i += 1
            ta, va, _ = pts[i]
            if i + 1 >= len(pts) or pts[i + 1][2]: out[name] = va; continue
            tb, vb, _ = pts[i + 1]; kk = _sm((t - ta) / max(1e-6, tb - ta))
            if name == 'yaw': out[name] = va + _wrap(vb - va) * kk
            elif name in ('p', 'head'): out[name] = [x + (y - x) * kk for x, y in zip(va, vb)]
            else: out[name] = va + (vb - va) * kk
        for name in HOLD:
            for k in ks:
                if k['t'] <= t and name in k: out[name] = k[name]
        return out

    def sample(self, t):
        out = {}
        for aid, ks in self.keys.items():
            s = self._state(ks, t); p = s.get('p', [0., 0., 0.])
            gest = s.get('gesture'); gw = float(s.get('gw', 1.))
            rig = dict(sit=float(s.get('sit', 0.)), crouch=float(s.get('crouch', 0.)), air=float(s.get('air', 0.)), lean=float(s.get('lean', 0.)),
                       slump=float(s.get('slump', 0.)), tension=float(s.get('tension', 0.)), run=float(s.get('run', 0.)),
                       head=tuple(s.get('head', (0., 0.))), gestures=[(gest, gw, t)] if gest else [], hands=s.get('hands'), back=bool(s.get('back', 0)))
            out[aid] = dict(x=float(p[0]), y=float(p[1]), z=float(p[2]), heading=float(s.get('yaw', 0.)), face=s.get('face', 'neutral'),
                            talking=bool(s.get('talk', 0)), visible=bool(s.get('vis', 1)), rig=rig)
        return out

    def position(self, tr, t): return (0., 0.)
