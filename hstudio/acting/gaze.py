"""Gaze controller ("la régie du regard"), shared by both engines, opt-in per episode.

Why it exists. In the régie the head target is read frame by frame: an explicit `look_at`, else whoever is speaking,
else an idle glance. Those sources switch instantly — a new line starts, a `look_at` runs out — so the head can
teleport from one frame to the next. Measured on the ten demo scenarios (`python tools/motion_qc.py`): 78 frames out
of 13 525 turn the gaze by more than 25 degrees in 1/30 s, worst case 93.6 degrees, typically a yaw going from +0.4
to +54.4 degrees (the clamp) in a single frame. A head cannot do that and the eye catches it.

What it does. It keeps the raw targets of the régie and plays them the way an actor would:
- it works on the gaze *in the world* (heading + head yaw), so a character keeps looking at the same thing while the
  body turns, instead of dragging the head along with the torso;
- a reaction delay (`latency`) before the head leaves for a new target, then a critically damped slew limited to
  `speed` rad/s — plus whatever the body itself is turning at, so the head is never held back by its own torso;
- anticipation at the cuts (`lead`): over the last fraction of a second of a shot the gaze leaves for wherever the
  régie will want it at the first frame of the next shot, so the cut lands on a head already aimed. The next shot
  starts from the state the previous one ended on, so a cut never resets the head.

It is deterministic: everything is precomputed on a fixed 60 Hz grid at build time, so the result does not depend on
which times an engine happens to sample. Nothing here knows about pixels or about an engine.

Switched on per episode (and overridable per shot) with "eyeline" ("gaze" is accepted as an alias; the per-actor
key "gaze" keeps its own meaning, the direction the drawn eyes point):
    "eyeline": "smooth"                                     the defaults below
    "eyeline": {"speed": 5.5, "lead": .5, "latency": .1}    same, tuned
    "eyeline": "snap" | false | absent                      the historical behaviour, frame for frame
"""
import math
from .timeline import wrap, smooth, OFF_WORDS

DEFAULTS = {
    'rate': 60.,          # Hz of the internal grid (fixed: determinism does not depend on the engine's sampling)
    'speed': 4.6,         # rad/s the head may turn on its own (~265 deg/s, a brisk but human head turn)
    'ease': .11,          # s, smoothing time of the critically damped slew (yaw)
    'pitch_ease': .16,    # s, same for the pitch (a head nods more slowly than it turns)
    'latency': .13,       # s before the head leaves for a target that just appeared
    'lead': .45,          # s of anticipation before a cut
    'anticipate': True,   # leave for the next shot's target before the cut
    'carry': True,        # start a shot from the gaze the previous one ended on
    'limit': .95,         # rad the neck can turn away from the torso (the régie clamps the yaw at the same value)
}


def options(spec, base=None):
    """episode / shot "eyeline" value -> options dict, or None for the historical behaviour (the default: absent
    means absent, so every episode written before this module renders frame for frame as it used to)"""
    if spec is None or spec is False or (isinstance(spec, str) and spec in OFF_WORDS): return None
    out = dict(base if base is not None else DEFAULTS)
    if isinstance(spec, dict):
        for k, v in spec.items():
            if k in DEFAULTS: out[k] = bool(v) if isinstance(DEFAULTS[k], bool) else float(v)
    return out


def _damp(cur, vel, tgt, ease, dt, vmax, angle=True):
    """one step of a critically damped slew towards tgt, never faster than vmax (Unity's SmoothDamp)"""
    omega = 2. / max(ease, 1e-3)
    change = wrap(cur - tgt) if angle else (cur - tgt)
    mx = vmax * max(ease, 1e-3)
    change = max(-mx, min(mx, change))
    goal = cur - change
    x = omega * dt; ex = 1. / (1. + x + .48 * x * x + .235 * x * x * x)
    temp = (vel + omega * change) * dt
    vel = (vel - omega * temp) * ex
    return goal + (change + temp) * ex, vel


class Solver:
    """precomputed gaze of every character of one shot: time -> (world gaze angle, pitch)"""
    __slots__ = ('opt', 'dur', 'dt', 'table', 'last')

    def __init__(self, opt, dur, dt, table):
        self.opt = opt; self.dur = dur; self.dt = dt; self.table = table
        self.last = {aid: (g[-1], p[-1], gv[-1], pv[-1]) for aid, (g, p, gv, pv) in table.items()}

    def head(self, aid, t, heading, yaw_raw, pitch_raw):
        """(yaw, pitch) relative to the torso; falls back to the régie for a character the solver does not know"""
        row = self.table.get(aid)
        if row is None: return yaw_raw, pitch_raw
        g, p, _gv, _pv = row
        u = min(max(t, 0.), self.dur) / self.dt
        i = int(u); i = min(i, len(g) - 2) if len(g) > 1 else 0
        f = min(1., max(0., u - i)) if len(g) > 1 else 0.
        ga = g[i] + wrap(g[i + 1] - g[i]) * f if len(g) > 1 else g[0]
        pa = p[i] + (p[i + 1] - p[i]) * f if len(p) > 1 else p[0]
        return wrap(ga - heading), pa


def build(sa, opt, start=None, next_raw=None, skip=()):
    """gaze Solver of one shot.
    start:    {id: (gaze, pitch, gaze_vel, pitch_vel)} the previous shot ended on (continuity across the cut)
    next_raw: {id: (yaw, pitch, heading)} the régie wants at the first frame of the next shot (anticipation)
    skip:     characters repositioned by the next shot: anticipating their gaze would aim at the wrong place"""
    dt = 1. / float(opt['rate']); n = max(2, int(round(sa.dur / dt)) + 1)
    ts = [min(sa.dur, i * dt) for i in range(n)]
    raw = [sa.raw_heads(t) for t in ts]
    lead = float(opt['lead']) if opt['anticipate'] else 0.
    lat = int(round(float(opt['latency']) / dt))
    start = start or {}; next_raw = next_raw or {}; lim = float(opt['limit'])
    table = {}
    for aid in sa.tracks:
        if aid not in raw[0]: continue
        head0 = [r.get(aid) for r in raw]
        if any(h is None for h in head0): continue
        world = [h[2] + h[0] for h in head0]                       # the gaze in the world: heading + yaw
        pitch = [h[1] for h in head0]
        nx = next_raw.get(aid)
        aim_g = (nx[2] + nx[0]) if (nx is not None and aid not in skip and lead > 0) else None
        st = start.get(aid)
        if opt['carry'] and st is not None: cur, cp, vel, pv = st
        else: cur, cp, vel, pv = world[0], pitch[0], 0., 0.
        gs = [cur]; ps = [cp]; gv = [vel]; pv_ = [pv]
        for i in range(1, n):
            j = max(0, i - lat)
            tg = world[j]; tp = pitch[j]
            if aim_g is not None and ts[i] > sa.dur - lead:        # anticipation: leave for the next shot's target
                k = smooth((ts[i] - (sa.dur - lead)) / lead)
                tg = tg + wrap(aim_g - tg) * k
                tp = tp + (nx[1] - tp) * k
            turn = abs(wrap(head0[i][2] - head0[i - 1][2])) / dt   # the body's own rotation, free for the head
            cur, vel = _damp(cur, vel, tg, opt['ease'], dt, float(opt['speed']) + turn)
            off = wrap(cur - head0[i][2])                          # the neck cannot turn further than the régie draws
            if abs(off) > lim: cur = head0[i][2] + (lim if off > 0 else -lim); vel = 0.
            cp, pv = _damp(cp, pv, tp, opt['pitch_ease'], dt, float(opt['speed']), angle=False)
            gs.append(cur); ps.append(cp); gv.append(vel); pv_.append(pv)
        table[aid] = (gs, ps, gv, pv_)
    return Solver(opt, sa.dur, dt, table)


def spec_of(d):
    """the "eyeline" of an episode or of a shot ("gaze" accepted as an alias)"""
    return d.get('eyeline', d.get('gaze'))


def plan(acting, episode, set_of):
    """attach a gaze controller to every acted shot that asks for one (episode / shot "eyeline").
    set_of: {shot index: set name}; shots of the same set in a row carry the gaze across the cut."""
    ep_opt = spec_of(episode)
    ks = sorted(acting.shots)
    prev_end = None; prev_k = None
    for k in ks:
        sa = acting.shots[k]
        if getattr(sa, 'directed', False): prev_end = None; prev_k = None; continue          # plan dirigé à la main : la tête est écrite, pas lissée
        shot = episode['shots'][k]
        here_spec = spec_of(shot)
        opt = options(here_spec, options(ep_opt)) if here_spec is not None else options(ep_opt)
        if opt is None: prev_end = None; prev_k = None; continue
        nk = k + 1
        nxt = acting.shots.get(nk)
        if getattr(nxt, 'directed', False): nxt = None
        same_next = nxt is not None and set_of.get(nk) == set_of.get(k)
        next_raw = nxt.raw_heads(0.) if same_next else None
        skip = {x.get('id', 'hero') for x in ((episode['shots'][nk].get('actors') or []) if same_next else [])
                if x.get('at') is not None or x.get('on')}
        start = prev_end if (prev_k == k - 1 and set_of.get(k - 1) == set_of.get(k)) else None
        here = {x.get('id', 'hero') for x in (shot.get('actors') or []) if x.get('at') is not None or x.get('on')}
        if start: start = {a: v for a, v in start.items() if a not in here}
        sa.gaze = build(sa, opt, start, next_raw, skip)
        prev_end = sa.gaze.last; prev_k = k
