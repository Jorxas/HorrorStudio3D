"""Vertical actions of the shared acting layer (V3): jump, climb, fall. Both engines use them.

They need nothing from an engine but its World: anchors and, when the set has levels (rooftops, ledges, a cliff, the bed
of the console bedroom), ground_y(x, z) -> height of the surface there, or None over a void. Each verb schedules
- the ground part (run-up, approach) with the usual paths: planted feet, footsteps;
- an airborne segment on the track: {"t0", "t1", "y": y(t), "y1": height after it, "style": leap|tuck|flail|climb};
- the horizontal motion meanwhile (a constant-speed path, no walk cycle);
- knee bends (anticipation, landing) and events for the sound ("jump", "land", "climb", "fall").
The skeleton draws the air pose from the rig parameters air / air_k / air_style (rig.solve). Trajectories are ballistic
(g = 9.81 m/s2, "hang" > 1 gives a longer, cinematic flight) and deterministic."""
import math
from . import timeline as TL

G = 9.81

class Flight(TL.Path):
    """horizontal motion during an airborne segment: constant speed, no walk cycle"""
    air = True
    def __init__(self, a, b, t0, dur):
        super().__init__([a, b], t0, max(.05, math.hypot(b[0] - a[0], b[1] - a[1]) / max(dur, 1e-3)))
        self.t1 = t0 + dur; self.dur = dur
    def dist(self, t): return min(self.D, max(0., (t - self.t0) / max(self.dur, 1e-3) * self.D))

def _levels(sa):
    return sa.world.ground_y if getattr(sa.world, 'has_levels', False) else None

def _scan(sa, a, b, y0, step=.08):
    """walking from a towards b on the level y0: (last point on that level, first point beyond, its height) or None"""
    gy = _levels(sa)
    if gy is None: return None
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step)); prev = a
    for k in range(1, n + 1):
        p = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n); h = gy(*p)
        if h is None or abs(h - y0) > .35: return prev, p, h
        prev = p
    return None

def _ballistic(t0, y0, vy, g):
    return lambda u: y0 + vy * (u - t0) - .5 * g * (u - t0) ** 2

@TL.verb('jump')
def jump(sa, tr, a, t0):
    """{"do": "jump", "to": anchor | [x, z] (where to land; none: on the spot), "run": true|false (default: a run-up when
    the gap is wider than 1.1 m), "hang": 1.0, "style": "leap"|"tuck", "height": apex of a jump on the spot,
    "land_y": landing height when it is not a level of the set (a vehicle, a moving platform),
    "time": flight duration (shorter = flatter arc: diving through a door)}"""
    here = tr.pos_at(t0); y0 = sa.level(tr, t0)
    g = G / max(.5, float(a.get('hang', 1.)))
    tgt = sa.resolve_xz(a.get('to'), t0) if a.get('to') is not None else None
    if tgt is None or math.hypot(tgt[0] - here[0], tgt[1] - here[1]) < .15:      # on the spot
        hgt = float(a.get('height', .45)); T = 2 * math.sqrt(2 * hgt / g); tr.squats.append((t0, .34, .45)); tf = t0 + .2
        tr.airs.append(dict(t0=tf, t1=tf + T, y=_ballistic(tf, y0, g * T / 2, g), y1=y0, style=a.get('style', 'tuck')))
        tr.squats.append((tf + T - .02, .36, .42)); tr.events += [(tf, 'jump', {}), (tf + T, 'land', {'height': hgt})]
        return tf + T + .36
    d = math.hypot(tgt[0] - here[0], tgt[1] - here[1]); ux, uz = (tgt[0] - here[0]) / d, (tgt[1] - here[1]) / d
    gy = _levels(sa)
    y1 = float(a['land_y']) if a.get('land_y') is not None else (gy(*tgt) if gy else None)
    if y1 is None: y1 = y0
    sc = _scan(sa, here, tgt, y0)
    if sc is not None: take = sc[0]
    else: back = min(1.4, d * .5) if d > 1.6 else 0.; take = (tgt[0] - ux * back, tgt[1] - uz * back) if back else here
    gap = math.hypot(tgt[0] - take[0], tgt[1] - take[1])
    run = a.get('run'); run = (gap > 1.1 and math.hypot(take[0] - here[0], take[1] - here[1]) > .6) if run is None else bool(run)
    if run and math.hypot(take[0] - here[0], take[1] - here[1]) > .5:        # a sprint fast enough for a ~0.8 s flight (low arc)
        v = max(TL.SPEEDS['run'], min(6., gap / .8)) if not isinstance(a.get('speed'), (int, float)) else float(a['speed'])
        if a.get('time'): v = max(TL.SPEEDS['run'], min(7.5, gap / float(a['time'])))
        t = sa.walk(tr, t0, take, speed=v, run=1., keep=True); tr.squats.append((t - .12, .2, .22))
    else:
        run = False; t = sa.turn(tr, t0, TL.heading_of(ux, uz))
        if math.hypot(take[0] - here[0], take[1] - here[1]) > .1: t = sa.walk(tr, t, take, final_heading=TL.heading_of(ux, uz))
        tr.squats.append((t, .4, .55)); t += .27
        v = max(1.2, gap / max(.38, .3 + .12 * gap))
    T = max(.32, gap / v); vy = (y1 - y0 + .5 * g * T * T) / T
    style = a.get('style', 'leap' if run else 'tuck')
    tr.airs.append(dict(t0=t, t1=t + T, y=_ballistic(t, y0, vy, g), y1=y1, style=style, lean=.22 if style == 'leap' else .08))
    if gap > .05: tr.paths.append(Flight(take, tgt, t, T))
    tr.looks.append((t - .45, t + T * .8, ('point', (tgt[0], y1 + .3, tgt[1]))))                    # eyes on the landing spot
    fall_h = max(0., y0 + max(0., vy) ** 2 / (2 * g) - y1)
    tr.squats.append((t + T - .03, .42 + .12 * min(1., fall_h / 2), .5 + .25 * min(1., fall_h / 2.5)))
    tr.events += [(t, 'jump', {'run': run}), (t + T, 'land', {'height': fall_h})]
    return t + T + .42

@TL.verb('climb')
def climb(sa, tr, a, t0):
    """{"do": "climb", "to": anchor | [x, z] on a higher level (a ledge, a wall, a bed), "height": rise when the set has no
    levels}: walks to the wall, both hands on the edge, pulls up, kneels on top and stands"""
    here = tr.pos_at(t0); y0 = sa.level(tr, t0); tgt = sa.resolve_xz(a.get('to'), t0)
    if tgt is None: return t0
    d = max(1e-3, math.hypot(tgt[0] - here[0], tgt[1] - here[1])); ux, uz = (tgt[0] - here[0]) / d, (tgt[1] - here[1]) / d
    gy = _levels(sa); sc = _scan(sa, here, tgt, y0)
    if sc is not None and sc[2] is not None: edge = sc[1]; y1 = sc[2]
    else: edge = (tgt[0] - ux * .4, tgt[1] - uz * .4); y1 = gy(*tgt) if gy else None
    if y1 is None or y1 <= y0 + .2: y1 = y0 + float(a.get('height', .9))
    h = TL.heading_of(ux, uz); approach = (edge[0] - ux * .38, edge[1] - uz * .38)
    t = sa.walk(tr, t0, approach, final_heading=h) if math.hypot(approach[0] - here[0], approach[1] - here[1]) > .08 else sa.turn(tr, t0, h)
    rise = y1 - y0; up = .8 + .35 * min(2., rise); rx, rz = math.cos(h), -math.sin(h)
    for side in (1, -1):
        tr.reaches.append((t, t + .3, t + .3 + up * .75, side, ('world', (edge[0] + rx * .2 * side + ux * .06, y1 + .03, edge[1] + rz * .2 * side + uz * .06))))
    tr.airs.append(dict(t0=t + .3, t1=t + .3 + up, y=lambda u, a_=t + .3: y0 + rise * TL.smooth((u - a_) / up), y1=y1, style='climb', lean=.35))
    top = (edge[0] + ux * .45, edge[1] + uz * .45)
    tr.paths.append(Flight(approach, top, t + .3 + up * .45, up * .55))
    tr.squats.append((t + .3 + up - .05, .55, .6))
    tr.events += [(t + .3, 'climb', {}), (t + .3 + up, 'land', {'height': .2})]
    return t + .3 + up + .5

@TL.verb('fall')
def fall(sa, tr, a, t0):
    """{"do": "fall", "to": where the fall drifts to (default 0.8 m ahead), "depth": metres when no level is below}:
    loses balance, falls with the arms flailing; lands (knees bend) when the drop is short, else falls out of frame"""
    here = tr.pos_at(t0); y0 = sa.level(tr, t0); h = tr.heading_at(t0)
    tgt = sa.resolve_xz(a.get('to'), t0) if a.get('to') is not None else (here[0] + math.sin(h) * .8, here[1] + math.cos(h) * .8)
    gy = _levels(sa); y1 = gy(*tgt) if gy else None
    if y1 is None or y1 > y0 - .2: y1 = float(getattr(sa.world, 'floor_y', y0 - float(a.get('depth', 2.)))) if gy else y0 - float(a.get('depth', 2.))
    drop = max(.2, y0 - y1); T = math.sqrt(2 * drop / G)
    tr.airs.append(dict(t0=t0, t1=t0 + T, y=lambda u: max(y1, y0 - .5 * G * (u - t0) ** 2), y1=y1, style='flail', lean=-.15))
    if math.hypot(tgt[0] - here[0], tgt[1] - here[1]) > .05: tr.paths.append(Flight(here, tgt, t0, T))
    tr.faces.append((t0, 'scared')); tr.events.append((t0, 'fall', {'height': drop}))
    if drop < 3.:
        tr.squats.append((t0 + T - .03, .5, .7)); tr.events.append((t0 + T, 'land', {'height': drop})); return t0 + T + .5
    return t0 + T
