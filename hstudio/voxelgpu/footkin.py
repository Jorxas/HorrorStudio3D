"""Where the feet of the voxel painter really are, computed from the contract rows BEFORE any image is drawn.

Why. A foot that goes through the floor or skates on it is invisible to a check on the actor's root position: the root moves smoothly, the damage is in the
legs. The painter (voxelgpu_js/engine/anim.js) builds the legs from a few numbers per frame (gait, phase, amp, sit, crouch, seat_h), all in the contract, and
the maths is closed-form: thigh angle a, knee flexion k, foot pitch b, lengths th / sh / ft in 1/16 m. This module is a port of `walk`, `run`, `plant`, `footDrop`
and `sit` of anim.js (hips roll and turn included), so the height and the forward position of the heel and the toe of each foot can be asked of any contract row.
`tools/check_facephysics.py` runs the REAL anim.js under Node (tools/anim_probe.mjs) on a grid of poses and compares: the two agree to the micrometre.

  * `feet(row)`        both feet: ankle, heel and toe (z forward, y up), lowest point, in the character's frame, scale 1
  * `audit_feet(c)`    violations on a finished contract: sole under the ground, both feet in the air, planted foot dragged over the ground, body carried with idle legs
  * `slide_stats(c)`   the numbers behind them (drag per contact, metres)
  * `drag_of_cycle`    the drag of a walk cycle for a speed / phase-per-metre / amplitude; `fit_gait` searches the least dragging pair

Measured on this port (docs/FACE_PHYSICS_20261029.md): the painter's nominal walk drags a planted foot ~8 cm on average, 17 cm at most per contact; a body sitting with
the contract's default seat height (.47) has its soles 4.8 cm under the floor.
Everything is deterministic; nothing here draws.
"""
import math

PX = 1. / 16.
TH, SH, FT = 6.5 * PX, 5.5 * PX, 2.0 * PX              # chars4.js LEN
HEEL, TOE = 2.3 * PX, 1.9 * PX                          # anim.js footDrop: the heel is 2.3 px behind the ankle, the toe pivot 1.9 px in front
HIP_Y = 14 * PX                                         # chars4.js hipY
K_WALK = 2 * math.pi / .853                             # director.RowMaker: phase per metre
K_RUN = 11. / 3.4
CONTACT_TOL = .006                                      # a sole point within 6 mm of the ground is in contact (the hips roll moves a flat foot by +-4 mm)


def _wrap(a): return (a + math.pi) % (2 * math.pi) - math.pi


def _bump(p, c, w):
    d = _wrap(p - c) * w
    return math.cos(d) ** 2 if abs(d) < math.pi / 2 else 0.


def _legs_walk(phase, amp):
    s = amp / .6; out = []
    for side in (1, -1):
        p = phase + (0. if side > 0 else math.pi)
        a = .36 * s * math.sin(p)
        k = s * (.95 * _bump(p, -.35, 1.05) + .16 * _bump(p, math.pi / 2 + .5, 2.2))
        b = s * (.22 * _bump(p, math.pi / 2 + .05, 2.4) - .42 * _bump(p, -math.pi / 2 - .4, 2.4) + .1 * _bump(p, .15, 1.6))
        out.append((side, a, k, b))
    return out, .004 * s * math.cos(2 * phase)


def _legs_run(phase, amp):
    s = amp; out = []
    for side in (1, -1):
        p = phase + (0. if side > 0 else math.pi)
        a = .1 + .62 * s * math.sin(p)
        k = s * (1.7 * _bump(p, -.55, .95) + .35 * _bump(p, math.pi / 2 + .4, 2.))
        b = s * (.15 * _bump(p, math.pi / 2, 2.4) - .6 * _bump(p, -math.pi / 2 - .3, 2.2) + .15 * _bump(p, .2, 1.6))
        out.append((side, a, k, b))
    return out, .05 * s * max(0., math.cos(2 * phase - .6))


def _hips_turn(mode, phase, amp):
    """(roll, yaw) of the hips in the walk / run of anim.js"""
    if mode == 2: return 0., .1 * amp * math.sin(phase)
    s = amp / .6; return .03 * s * math.cos(phase), .07 * s * math.sin(phase)


def foot_drop(a, k, b):
    """anim.js footDrop: height of the hips over the ground for the lowest point of this foot to touch it"""
    ank = TH * math.cos(a) + SH * math.cos(a - k)
    return ank + max(FT * math.cos(b) + HEEL * math.sin(b), FT * math.cos(b) - TOE * math.sin(b))


def _foot(side, a, k, b, hips_y, roll=0., yaw=0.):
    """one foot in the character's frame (z forward, x to its left, y up), scale 1. The whole leg chain hangs from the hips, which the walk rolls (rotation.z) and
    turns (rotation.y) a little: anim.js applies Rz then Ry (three.js 'XYZ' Euler), and so does this."""
    az = TH * math.sin(a) + SH * math.sin(a - k); ay = -(TH * math.cos(a) + SH * math.cos(a - k)); x0 = side * 2 * PX
    pts = {'ankle': (x0, ay, az),
           'heel': (x0, ay - FT * math.cos(b) - HEEL * math.sin(b), az + FT * math.sin(b) - HEEL * math.cos(b)),      # 2.3 px behind, 2 px under the ankle, pitched by b (toe up)
           'toe': (x0, ay - FT * math.cos(b) + TOE * math.sin(b), az + FT * math.sin(b) + TOE * math.cos(b))}
    cr, sr, cy, sy = math.cos(roll), math.sin(roll), math.cos(yaw), math.sin(yaw)

    def T(p):
        x, y, z = p; x, y = x * cr - y * sr, x * sr + y * cr; x, z = x * cy + z * sy, -x * sy + z * cy; return (x, y + hips_y, z)
    P = {k_: T(v) for k_, v in pts.items()}
    return dict(side=side, ankle=P['ankle'], sole_y=min(P['heel'][1], P['toe'][1]), heel_y=P['heel'][1], toe_y=P['toe'][1], heel_z=P['heel'][2], toe_z=P['toe'][2], pitch=b)


def feet(row, cols=None, scale=1.):
    """-> {'L': foot, 'R': foot} for one contract row (a dict, or a list with `cols`), or None if the legs are not driven by gait / sit (idle, crouch, air)"""
    g = row if isinstance(row, dict) else dict(zip(cols, row))
    mode = int(g.get('gait', 0)); sit = float(g.get('sit', 0.))
    if sit > .02:
        hips = HIP_Y + (float(g.get('seat_h', .47)) + .02 - HIP_Y) * sit
        return {'L' if s == 1 else 'R': _foot(s, 1.5 * sit, 1.25 * sit, .25 * sit + .22 * sit, hips) for s in (1, -1)}
    if float(g.get('crouch', 0.)) > .02 or float(g.get('air', 0.)) > .05 or mode == 0: return None
    ph, amp = float(g.get('phase', 0.)), float(g.get('amp', .6))
    legs, lift = (_legs_run if mode == 2 else _legs_walk)(ph, amp)
    d = max(foot_drop(a, k, b) for (_, a, k, b) in legs); roll, yaw = _hips_turn(mode, ph, amp)
    return {'L' if s == 1 else 'R': _foot(s, a, k, b, d + lift, roll, yaw) for (s, a, k, b) in legs}


def seat_for_flat_feet():
    """the seat_h at which a sitting body's soles touch the ground (anim.js sit does not plant the feet: the contract's `seat_h` decides, and the default .47 sinks them)"""
    lo, hi = .3, .8
    for _ in range(40):
        mid = (lo + hi) / 2
        if feet(dict(gait=0, sit=1., seat_h=mid))['L']['sole_y'] < 0: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def _contacts(f, S):
    """-> {(side, 'heel'|'toe'): (z, y)} in metres (scaled) for the feet dict of `feet()`"""
    out = {}
    for k in 'LR':
        out[(k, 'heel')] = (f[k]['heel_z'] * S, f[k]['heel_y'] * S); out[(k, 'toe')] = (f[k]['toe_z'] * S, f[k]['toe_y'] * S)
    return out


class _Episodes:
    """A sole point that stays on the ground for several frames should stay at the same spot of the ground. What a viewer sees is how far it is dragged during one
    contact (a `drag`, in metres): for every sole point, every run of consecutive frames in contact, the distance the point travelled over the ground."""

    def __init__(self, min_frames=4): self.cur = {}; self.done = []; self.min = min_frames

    def push(self, key, in_contact, step):
        if in_contact:
            e = self.cur.setdefault(key, [0., 0]); e[0] += step; e[1] += 1
        else: self.close(key)

    def close(self, key):
        e = self.cur.pop(key, None)
        if e is not None and e[1] >= self.min: self.done.append(abs(e[0]))

    def flush(self):
        for key in list(self.cur): self.close(key)
        return self.done


def drag_of_cycle(v, k_per_m, amp, run=False, n=480):
    """(mean drag, max drag) in metres per contact of the planted sole points for a body walking at v (m/s) with this phase-per-metre and amplitude"""
    w = k_per_m * v; dt = (2 * math.pi / max(1e-6, w)) / n; fn = _legs_run if run else _legs_walk; prev = None; ep = _Episodes(min_frames=max(3, n // 60))
    for i in range(n * 2 + 1):
        ph = w * dt * i; legs, lift = fn(ph, amp); d = max(foot_drop(a, k, b) for (_, a, k, b) in legs); roll, yaw = _hips_turn(2 if run else 1, ph, amp)
        cur = _contacts({('L' if s_ == 1 else 'R'): _foot(s_, a, k, b, d + lift, roll, yaw) for (s_, a, k, b) in legs}, 1.)
        if prev is not None:
            for key, (z1, y1) in cur.items():
                z0, y0 = prev[key]; ep.push(key, max(y0, y1) < CONTACT_TOL, v * dt + (z1 - z0))
        prev = cur
    ds = ep.flush()
    return (sum(ds) / len(ds), max(ds)) if ds else (9., 9.)


def fit_gait(v, run=False):
    """(phase_per_metre, amp, mean drag m, max drag m): the pair that drags the planted foot least at speed v, with an amplitude that still reads as a walk
    (60 % to 120 % of the painter's own amp(v)). The painter's constants are K_WALK / K_RUN and amp = .62 (v/.95)^.8 (walk)."""
    nominal = (min(1., max(.35, v / 3.4)) if run else .62 * min(1.35, max(.12, v / .95)) ** .8); best = None
    for amp in [nominal * f for f in (.6, .7, .8, .9, 1., 1.1, 1.2)]:
        for kk in [x / 10. for x in range(30, 130, 2)]:
            m, mx = drag_of_cycle(v, kk, amp, run, n=240)
            sc = m + .5 * mx
            if best is None or sc < best[0]: best = (sc, kk, amp, m, mx)
    return best[1], best[2], best[3], best[4]


def _iter_feet(c, aid=None):
    """yield (aid, stage id, t, row dict, scale, feet or None) for every frame of a contract, in time order"""
    fps = c['fps']; cols = c['actor_cols']
    for st in c['stages']:
        n = int(round((st['t1'] - st['t0']) * fps))
        for a, rows in st['actors'].items():
            if aid and a != aid: continue
            S = float(((c.get('casts') or {}).get(a) or {}).get('scale') or 1.)
            for i, r in enumerate(rows[:max(1, n)]):
                g = dict(zip(cols, r))
                yield a, st['id'], st['t0'] + i / fps, g, S, (feet(g, cols, S) if g['vis'] else None)


def slide_stats(c, aid=None):
    """-> {actor: dict(mean=m, max=m, n=contacts, still=metres)} on a finished contract: how far a planted foot is dragged per contact, and how far the actor was
    carried along the ground with idle legs (the worst skate)."""
    fps = c['fps']; eps = {}; prev = {}; still = {}
    for a, sid, t, g, S, f in _iter_feet(c, aid):
        pr = prev.get(a); ok = pr is not None and abs(t - pr[0] - 1. / fps) < .5 / fps and pr[4] == sid
        walking = f is not None and g['gait'] in (1, 2) and g['sit'] <= .02
        if ok and g['vis'] and g['gait'] == 0 and g['sit'] <= .02 and g['crouch'] <= .02 and g['air'] <= .05:
            d = math.hypot(g['x'] - pr[2], g['z'] - pr[3])
            if d * fps > .15: still[a] = still.get(a, 0.) + d              # translating with idle legs
        if not walking:
            if a in eps: eps[a].flush()
            prev[a] = (t, None, g['x'], g['z'], sid) if g['vis'] else None; continue
        cur = _contacts(f, S)
        if ok and pr[1] is not None:
            vfwd = (g['x'] - pr[2]) * math.sin(g['yaw']) + (g['z'] - pr[3]) * math.cos(g['yaw']); E = eps.setdefault(a, _Episodes(3))
            for key, (z1, y1) in cur.items():
                z0, y0 = pr[1][key]; E.push(key, max(y0, y1) < CONTACT_TOL * S, vfwd + (z1 - z0))
        prev[a] = (t, cur, g['x'], g['z'], sid)
    out = {}
    for a, E in eps.items():
        ds = E.flush()
        if ds: out[a] = dict(mean=sum(ds) / len(ds), max=max(ds), n=len(ds), still=still.get(a, 0.))
    for a, d in still.items():
        if a in out: out[a]['still'] = d
        else: out[a] = dict(mean=0., max=0., n=0, still=d)
    return out


def audit_feet(c, tol_sink=.025, tol_float=.05, drag_mean=.12, drag_max=.25, still_max=.5, max_per_actor=3):
    """The feet of every visible actor of a finished contract, frame by frame -> list of blocking.Violation:
      pied_dans_le_sol   a sole point deeper than tol_sink under the actor's ground (the row's own `y`), walking or sitting
      pied_flotte        both feet more than tol_float above it
      pied_glisse        the planted foot is dragged over the ground: mean drag per contact > drag_mean, or one contact > drag_max (metres)
      glisse_sans_pas    the actor is carried along the ground for more than still_max metres with no walk cycle (legs idle)
    The painter's own nominal walk drags a foot ~8 cm on average and ~17 cm at most per contact: inside the limits, so a standard walk is never flagged."""
    from .blocking import Violation
    v = []; cnt = {}
    for a, sid, t, g, S, f in _iter_feet(c):
        if f is None: continue
        sit = g['sit'] > .02; low = min(f['L']['sole_y'], f['R']['sole_y']) * S
        if low < -tol_sink and cnt.get((a, 'sink'), 0) < max_per_actor:
            cnt[(a, 'sink')] = cnt.get((a, 'sink'), 0) + 1
            v.append(Violation('pied_dans_le_sol', f"{a} a un pied {(-low) * 100:.1f} cm sous le sol ({'assis, siège ' + format(g['seat_h'], '.2f') if sit else 'en marche'}, plan {sid})", t, a, depth=-low))
        if low > tol_float and cnt.get((a, 'float'), 0) < max_per_actor:
            cnt[(a, 'float')] = cnt.get((a, 'float'), 0) + 1
            v.append(Violation('pied_flotte', f"{a} : les deux pieds sont à {low * 100:.1f} cm au-dessus du sol ({'assis' if sit else 'en marche'}, plan {sid})", t, a, height=low))
    for a, d in slide_stats(c).items():
        if d['n'] >= 1 and (d['max'] > drag_max or (d['n'] >= 4 and d['mean'] > drag_mean)):
            v.append(Violation('pied_glisse', f"{a} : le pied d'appui est traîné de {d['mean'] * 100:.0f} cm en moyenne et jusqu'à {d['max'] * 100:.0f} cm par appui ({d['n']} appuis)", None, a, **d))
        if d['still'] > still_max: v.append(Violation('glisse_sans_pas', f"{a} glisse sur {d['still']:.1f} m sans cycle de marche (jambes immobiles)", None, a, **d))
    return v


# ---------------------------------------------------------------------------------------------------------------------------------------- planted gait (data)
# Result of `fit_gait` on the exact port above (docs/FACE_PHYSICS_20261029.md): for a given speed, the (phase per metre, amplitude) pair that drags the planted foot the
# least while the amplitude stays within 60 - 120 % of the painter's own. Below .95 m/s the search degenerates into a shuffle (K > 8), so the painter's own gait is kept there.
# (speed m/s, phase per metre, amplitude, mean drag cm, max drag cm) -- the painter's own gait at the same speeds drags 8.6 / 17.4 cm (.95), 10.9 / 18.1 cm (1.2), 11.6 / 20.6 cm (1.5).
PLANTED_WALK = [(0.95, 4.6, 0.744, 4.7, 12.1), (1.2, 4.0, 0.897, 3.7, 5.9), (1.5, 3.8, 0.946, 3.7, 6.3)]
PLANTED_RUN = [(2.5, 11.4, 0.441, 2.5, 6.4), (3.4, 8.6, 0.6, 3.1, 7.3)]


def planted_gait(v, run=False):
    """(phase per metre, amplitude) that plants the foot at speed v (m/s), interpolated in PLANTED_WALK / PLANTED_RUN; None where the painter's own gait is kept
    (walking under the first tabulated speed). This is what `director.RowMaker` would write instead of K_WALK / its amp formula, behind an opt-in key."""
    tab = PLANTED_RUN if run else PLANTED_WALK
    if v < tab[0][0] - 1e-9: return None
    if v >= tab[-1][0]: return tab[-1][1], tab[-1][2]
    for (v0, k0, a0, *_), (v1, k1, a1, *_) in zip(tab[:-1], tab[1:]):
        if v0 <= v <= v1: u = (v - v0) / (v1 - v0); return k0 + (k1 - k0) * u, a0 + (a1 - a0) * u
