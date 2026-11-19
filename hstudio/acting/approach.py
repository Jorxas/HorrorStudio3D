"""Directed locomotion ("l'approche"): a character turns before walking, walks the way the body faces, and brakes
facing whoever they came to talk to. Shared by both engines, nothing here knows about pixels.

Opt-in. Episode or shot key `"approach": "directed"` (anything in OFF_WORDS, or no key at all, keeps the historical
behaviour exactly). Old episodes are untouched: without the key no controller is built, `Track.heading_at` and
`ShotActing.sample` return what they always returned.

### The defect this fixes (measured, see docs/LOCOMOTION_DIRIGEE.md)

`Track.heading_at` reads every path, then every turn. The quarter turn that `walk()` schedules to launch a walk
starts at the walk's own start time, so it won the comparison for the whole walk: the body kept the angle of the
*first leg* of the path and then crabbed through every corner, feet skating. On the owner's scene (Lea walking to
Tom across the living room) the body stayed at -10 deg while the travel direction went -10 -> -90 -> -137 deg:
127 deg of error, 6.6 cm of stance-foot slide per frame, and she arrived beside Tom without ever facing him.

### What this module adds on top of "footing"

`"footing"` (hstudio/acting/timeline.py, feature/actor-motion) reads the heading sources in chronological order and
ends a walk on a mid-stance. That removes the frozen heading but leaves the body snapping to each new tangent, gives
no anticipation, and never turns an actor towards the person they walked up to. This module is the layer above:

- a **reference heading** = the chronologically last thing that drives the body (path tangent while walking, turn
  target otherwise). When `footing` is present its ordering already agrees with this, so the two do not fight;
  this module deliberately reads the raw target and does its own smoothing instead of footing's `TAKEOVER` fade.
- a **rate-limited, critically damped body heading**: a real pelvis turns at ~150-200 deg/s, it does not teleport
  to the tangent of the next corner. The acceleration cap is what makes the feet and pelvis *lag*, which is the
  anticipation the eye reads.
- an **anticipation chain** head -> torso -> pelvis -> feet. The head is given a lead on the direction the body is
  about to take (`lead`), the torso banks into the turn and shifts its weight forward just before the first step
  (`roll` / `lean`), the pelvis and feet arrive last through the acceleration cap. Only parameters `rig.solve`
  already understands are used, so no engine changes and no skeleton change.
- a **braking stop facing the interlocutor**: `walk_to` towards an actor ends with a turn onto that actor, at a
  distance that cannot overlap them.
- a **small seeded naturalism**: per-character turn rate, lead time and a few degrees of "not quite square" on the
  final facing. Seeded from the character id, so the render stays deterministic.

Deliberate lateral movement is preserved: a walk flagged `"strafe": true` keeps its scheduled facing and is left
alone by the controller, which is the only way to move sideways on purpose.
"""
import math
import numpy as np
from .timeline import wrap, heading_of, h32

OFF_WORDS = ('off', 'none', 'legacy', 'snap', 'frozen', '')     # on "approach", any of these means historical
HZ = 60.                       # the controller is integrated on a fixed grid: the result cannot depend on when an
PAD = .5                       # engine samples it (same guarantee as the precomputed eyeline)

RATE = 3.1                     # rad/s, body yaw speed cap (~178 deg/s)
ACCEL = 14.0                   # rad/s^2, what makes the pelvis and the feet lag behind the intent
TAU = .16                      # s, critically damped pull towards the reference
LEAD = .26                     # s, how far ahead the head looks
BANK = .055                    # rad of torso roll per rad/s of body yaw
SET_LEAN = .09                 # rad of forward lean in the weight shift before the first step
SET_DUR = .34                  # s, how long that weight shift lasts
MIN_GAP = .62                  # m, closest an approach may stop to another actor (bodies are ~.52 m wide)
TALK_GAP = 1.15                # m, default stopping distance of an approach towards an actor


def wanted(episode, shot):
    """episode / shot "approach": "directed" (or true) -> the directed locomotion controller is built"""
    v = shot.get('approach', episode.get('approach'))
    if isinstance(v, str): return v.strip().lower() not in OFF_WORDS
    return bool(v)


def stop_dist(asked, to_actor):
    """distance an approach stops at. Towards another actor: what the episode asked, but never close enough to
    stand inside their body, and a conversation distance when nothing was asked. Towards anything else (a door, a
    point, an item) the episode is left alone: only a body can be walked into."""
    if not to_actor: return float(asked) if asked else 0.
    return max(float(asked), MIN_GAP) if asked else TALK_GAP


class Approach:
    """the body heading of one character during one shot, integrated once on the fixed grid"""

    def __init__(self, sa, tr):
        self.tr = tr
        self.rate = RATE * (.9 + .2 * h32(tr.id, 'approach'))    # naturalism: this body is not the average body
        self.lead = LEAD * (.85 + .3 * h32('lead', tr.id))
        self.t0 = -PAD
        n = int((sa.dur + 2 * PAD) * HZ) + 2
        self.ts = self.t0 + np.arange(n) / HZ
        des = np.array([self._reference(float(t)) for t in self.ts], np.float64)
        H = np.empty(n); W = np.empty(n)
        h = float(des[0]); w = 0.; dt = 1. / HZ
        for i in range(n):
            want = max(-self.rate, min(self.rate, wrap(float(des[i]) - h) / TAU))
            w += max(-ACCEL * dt, min(ACCEL * dt, want - w))
            h = h + w * dt
            H[i] = h; W[i] = w
        self.H = H; self.W = W
        self.walks = [(p.t0, p.t1) for p in tr.paths if not getattr(p, 'air', False)]

    # ---------------- the reference the body tries to reach
    def _reference(self, t):
        """the chronologically last thing that drives the body: the tangent of the path being walked, else the
        target of the last turn. Reading them in time order is what the frozen-heading defect got wrong; a walk
        flagged "strafe" is skipped here so a deliberate side step keeps its facing."""
        tr = self.tr
        src = [(p.t0, 0, p) for p in tr.paths if not getattr(p, 'strafe', False)]
        src += [(x[0], 1, x) for x in tr.turns]
        h = tr.heading
        for (t0, kind, o) in sorted(src, key=lambda e: e[:2]):
            if t < t0: continue
            if kind == 0:
                d = o.dist(t)
                h = o.tangent(d if (d < o.D - .02 or t < o.t1) else o.D)
                if getattr(o, 'backwards', False): h += math.pi
            else:
                h = o[3]
        return h

    def _at(self, A, t):
        f = (t - self.t0) * HZ
        i = int(np.clip(math.floor(f), 0, len(self.ts) - 2)); u = min(1., max(0., f - i))
        return float(A[i] + (A[i + 1] - A[i]) * u)

    # ---------------- what the regie and the engines read
    def heading(self, t):
        return self._at(self.H, t)

    def decorate(self, p, t, limit=.95):
        """the rest of the chain, on parameters rig.solve already understands: the head leads the turn, the torso
        banks into it and shifts its weight forward before the first step. The pelvis and the feet are already
        late, because the acceleration cap made them late."""
        w = self._at(self.W, t)
        turning = min(1., abs(w) / 1.2)
        if turning > .01:                                # head: look where the body is about to be
            want = wrap(self._reference(t + self.lead) - self._at(self.H, t))
            want = max(-limit, min(limit, want))
            yaw, pitch = p.get('head', (0., 0.))
            p['head'] = (yaw + (want - yaw) * .55 * turning, pitch)
        p['roll'] = p.get('roll', 0.) - BANK * w         # torso banks into the turn
        for (a, _b) in self.walks:                       # weight forward in the last .34 s before the first step
            if a - SET_DUR <= t < a:
                p['lean'] = p.get('lean', 0.) + SET_LEAN * math.sin(math.pi * (t - a + SET_DUR) / SET_DUR)
                break


def attach(sa):
    """build the controller of every character of a shot, once everything else is scheduled"""
    for tr in sa.tracks.values():
        if tr.follow is None:                            # "follow" drives its own heading from its own path
            tr.ctrl = Approach(sa, tr)


def walk_stop(tr, t0, to_xz, sd):
    """where a walk really stops: the asked point pulled back by the stopping distance (same rule as walk())"""
    a = tr.pos_at(t0); d = math.hypot(to_xz[0] - a[0], to_xz[1] - a[1])
    if not sd or d <= sd: return a if d <= sd else to_xz
    return (a[0] + (to_xz[0] - a[0]) * (1 - sd / d), a[1] + (to_xz[1] - a[1]) * (1 - sd / d))


def stop_facing(sa, tr, target, to_xz, sd, action):
    """heading an approach brakes onto: the actor walked up to, a few degrees off square (nobody stops perfectly
    aligned). None when the action already asked for a facing, or when the target is not someone else."""
    if action.get('face') is not None or action.get('strafe'): return None
    if not (isinstance(target, str) and target in sa.tracks) or target == tr.id: return None
    px, pz = sa.tracks[target].pos_at(1e9)
    sx, sz = walk_stop(tr, 0., to_xz, sd)
    off = math.radians(-5. + 10. * h32('stop', tr.id, target))
    return heading_of(px - sx, pz - sz) + off
