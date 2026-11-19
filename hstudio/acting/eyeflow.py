"""Pupil flow ("le lissage du regard"), opt-in per episode, key "eye_smooth".

WHY. `acting/timeline` measures, for every sampled character, the part of the aim the NECK could not deliver
(the 0.95 rad clamp, plus the slew lag of `acting/gaze.py` when the episode asks for one). That residual is
what `engines/pixel3d/eyes.py` turns into a pupil offset when `"eye_aim"` is on. It is computed frame by
frame from the regie's RAW target, and the regie switches target instantly: a line starts, a `look_at` runs
out, a shot cuts. Measured on `demo6_continuite` with `"eyeline": "smooth"`, sampled at the render's own
30 Hz, the residual moves by up to **60 degrees between two consecutive frames** -- more than twice the whole
mechanical range of the drawn eye. The pupils teleport from one edge of the socket to the other in one frame.
docs/P1_INTERACTION_REGARD_20261025.md section 10 names this as the defect that lot left behind.

It cannot be fixed in the renderer: frames are rendered by a `spawn` pool, one process per frame, with no
state from the frame before. So, exactly like the head, it is **precomputed** here on a fixed 60 Hz grid at
build time, and the renderer only reads a table.

WHAT IT MODELS, and why not a plain damper. A damped slew would make the pupils drift like syrup, which is
not what an eye does and would look worse than the teleport. A human eye does two things and this module does
those two and nothing else:

- **saccade**: when the target moves further than `threshold`, the eye launches a ballistic jump towards
  where the target was *at launch* and does not re-aim mid-flight. Its duration follows the measured main
  sequence of human saccades, `D = base + gain * amplitude`, capped at `reach` because the drawn eye has no
  more travel than that: a full-deflection jump takes ~78 ms, a little over two frames at 30 i/s instead of
  none. The reaction delay that goes with it in a human is NOT retained, and what it costs is measured
  rather than asserted (see PRESETS);
- **smooth pursuit**: below `threshold` the eye follows its target continuously, limited to `pursuit` rad/s
  (~34 deg/s, the order of magnitude of human pursuit). That is what keeps a slowly drifting aim from firing
  a saccade every frame;
- plus `latency`, a reaction delay before either reacts to a target that just appeared.

What it does NOT model: micro-saccades, fixational drift and tremor, vergence, lid coupling, the head's own
counter-rotation (vestibulo-ocular reflex). Those are other lots.

The residual is a measurement that only `engines/pixel3d/eyes.py` consumes, so smoothing it changes no pose,
no camera and no skeleton. CONSOLE 2D ignores the key and renders bit for bit as before, and so does PIXEL 3D
without `"eye_aim"`. Absent key = absent: every episode written before this module renders exactly as it did.

    "eye_smooth": "saccade"                                        the defaults below
    "eye_smooth": {"latency": .05, "pursuit": .8}                  same, tuned
    "eye_smooth": "snap" | false | absent                          the historical behaviour, frame for frame
"""
import math
from .timeline import smooth, OFF_WORDS

DEFAULTS = {
    'rate': 60.,          # Hz of the internal grid (fixed: determinism does not depend on the engine's sampling)
    'latency': 0.,        # s before the eye reacts to a target that just appeared (see PRESETS: measured at 0)
    'threshold': .05,     # rad of target error above which the eye saccades instead of pursuing (~2.9 deg)
    'base': .021,         # s, the intercept of the saccadic main sequence
    'gain': .126,         # s/rad, its slope: the human 2.2 ms per degree
    'reach': .45,         # rad at which the drawn pupils are at full deflection: a longer jump is not longer
    'pursuit': .6,        # rad/s of smooth pursuit below the threshold (~34 deg/s)
    'carry': True,        # a cut does not reset the eye: it starts where the previous shot left it
}

# THE RETAINED PRESET TAKES THE HUMAN MOVEMENT AND NOT THE HUMAN REACTION TIME, and that is a measurement,
# not a taste. The criterion was written in tools/regard_qc.py before the first number: halve the share of
# pairs that jump more than two texels, without costing more than 1 degree of aim accuracy. The main sequence
# (2.2 ms/deg, so ~78 ms for a full-deflection jump) does it for +0.6 deg. Adding the real saccadic latency
# of ~70 ms buys nothing more -- the jumps are already gone -- and costs another 0.6 deg, because the pupils
# then sit on the wrong side while they wait. `humain` keeps those timings reachable so the report can
# measure what they cost instead of asserting it.
PRESETS = {
    # retained after measurement -- see docs/P1_LISSAGE_REGARD_20261025.md
    'saccade': dict(DEFAULTS),
}


def register(name, **spec):
    """an extension adds its own pupil-flow preset (registry, not if/elif -- see AGENTS.md)"""
    PRESETS[name] = dict(DEFAULTS, **{k: v for k, v in spec.items() if k in DEFAULTS})
    return PRESETS[name]


def options(spec, base=None):
    """episode / shot "eye_smooth" value -> options dict, or None for the historical behaviour (absent means
    absent, so every episode written before this module keeps its frame-for-frame pupils)"""
    if spec is None or spec is False or (isinstance(spec, str) and spec in OFF_WORDS): return None
    if spec is True:
        out = dict(base if base is not None else PRESETS['saccade'])
        out.setdefault('name', 'saccade'); return out
    if isinstance(spec, str):
        p = PRESETS.get(spec)
        return dict(p, name=spec) if p is not None else None
    if isinstance(spec, dict):
        name = spec.get('style') or spec.get('preset')
        if name is not None:
            p = PRESETS.get(name)
            if p is None: return None
            out = dict(p)
        else:
            out = dict(base if base is not None else PRESETS['saccade'])
        for k, v in spec.items():
            if k in DEFAULTS: out[k] = bool(v) if isinstance(DEFAULTS[k], bool) else float(v)
        out['name'] = name or out.get('name') or 'saccade'
        return out
    return None


def spec_of(d):
    """the "eye_smooth" of an episode or of a shot"""
    return d.get('eye_smooth')


class Solver:
    """precomputed pupil residual of every character of one shot: time -> (yaw, pitch) in radians"""
    __slots__ = ('opt', 'dur', 'dt', 'table', 'last')

    def __init__(self, opt, dur, dt, table):
        self.opt = opt; self.dur = dur; self.dt = dt; self.table = table
        self.last = {aid: (ys[-1], ps[-1]) for aid, (ys, ps) in table.items()}

    def eye(self, aid, t, raw):
        """the smoothed residual; falls back to `raw` for a character the solver does not know"""
        row = self.table.get(aid)
        if row is None: return raw
        ys, ps = row
        if len(ys) < 2: return (ys[0], ps[0])
        u = min(max(t, 0.), self.dur) / self.dt
        i = min(int(u), len(ys) - 2)
        f = min(1., max(0., u - i))
        return (ys[i] + (ys[i + 1] - ys[i]) * f, ps[i] + (ps[i + 1] - ps[i]) * f)


def build(sa, opt, start=None):
    """pupil-flow Solver of one shot.
    start: {id: (yaw, pitch)} the previous shot ended on, so a cut does not reset the eye"""
    dt = 1. / float(opt['rate']); n = max(2, int(round(sa.dur / dt)) + 1)
    ts = [min(sa.dur, i * dt) for i in range(n)]
    lat = int(round(float(opt['latency']) / dt))
    thr = float(opt['threshold']); base = float(opt['base']); gain = float(opt['gain'])
    reach = float(opt['reach']); pur = float(opt['pursuit']) * dt
    # The residual is clamped to the eye's own travel BEFORE anything is smoothed, and that is not a detail:
    # a residual of 50 degrees and one of 90 draw the SAME fully deflected pupil, so a saccade sized on the
    # raw angle spends most of its flight outside the socket and crosses the whole visible range in a
    # fraction of a frame -- which is the teleport, unchanged, with extra steps. Clamping here makes the
    # amplitude the eye really travels the amplitude the main sequence is given. `reach` is the same angle
    # `engines/pixel3d/eyes.py` saturates at (`yaw`), so for the delivered presets this clips nothing the
    # renderer would have drawn.
    def cl(v): return max(-reach, min(reach, v))
    raw = [{a: (cl(e[0]), cl(e[1])) for a, e in sa.raw_eye(t).items()} for t in ts]
    start = start or {}
    table = {}
    for aid in sa.tracks:
        if aid not in raw[0]: continue
        col = [r.get(aid) for r in raw]
        if any(c is None for c in col): continue
        st = start.get(aid) if opt['carry'] else None
        cur, curp = st if st is not None else col[0]
        ys = [cur]; ps = [curp]
        sac = None                                        # (t0, t1, from_yaw, from_pitch, to_yaw, to_pitch)
        for i in range(1, n):
            t = ts[i]
            if sac is not None:                           # ballistic: in flight, the target of the launch holds
                k = (t - sac[0]) / (sac[1] - sac[0])
                if k >= 1.: sac = None                    # landed: this step may launch a corrective saccade
                else:
                    e = smooth(k)
                    cur = sac[2] + (sac[4] - sac[2]) * e
                    curp = sac[3] + (sac[5] - sac[3]) * e
            if sac is None:
                ty, tp = col[max(0, i - lat)]
                dy = ty - cur; dp = tp - curp
                amp = math.hypot(dy, dp)
                if amp > thr:                             # saccade: the main sequence, on the travel it can show
                    dur = base + gain * min(amp, 2. * reach)
                    # launched one step BACK, so that this step already advances: anchoring it at `t` would
                    # replay smooth(dt/dur) twice and hold the pupil still for a frame, which is the defect
                    sac = (t - dt, t - dt + dur, cur, curp, ty, tp)
                    e = smooth(min(1., dt / dur))
                    cur = cur + dy * e; curp = curp + dp * e
                elif amp > 1e-12:                         # smooth pursuit, speed-limited
                    k = min(1., pur / amp)
                    cur = cur + dy * k; curp = curp + dp * k
            ys.append(cur); ps.append(curp)
        table[aid] = (ys, ps)
    return Solver(opt, sa.dur, dt, table)


def plan(acting, episode, set_of):
    """attach a pupil-flow solver to every acted shot that asks for one (episode / shot "eye_smooth").
    set_of: {shot index: set name}; shots of the same set in a row carry the eye across the cut."""
    ep_opt = spec_of(episode)
    prev_end = None; prev_k = None
    for k in sorted(acting.shots):
        sa = acting.shots[k]
        if getattr(sa, 'directed', False): prev_end = None; prev_k = None; continue          # plan dirigé à la main : le regard est écrit
        shot = episode['shots'][k]
        here = spec_of(shot)
        opt = options(here, options(ep_opt)) if here is not None else options(ep_opt)
        if opt is None: prev_end = None; prev_k = None; continue
        start = prev_end if (prev_k == k - 1 and set_of.get(k - 1) == set_of.get(k)) else None
        placed = {x.get('id', 'hero') for x in (shot.get('actors') or []) if x.get('at') is not None or x.get('on')}
        if start: start = {a: v for a, v in start.items() if a not in placed}
        sa.eyeflow = build(sa, opt, start)
        prev_end = sa.eyeflow.last; prev_k = k
