"""B directs: an episode in the DSL of docs/FORMAT_EPISODE.md (shots, actors, actions, camera intentions) + the keys of
docs/VOXELGPU.md -> a scene contract (hstudio/voxelgpu/contract.py) that the voxel painter (A) renders on the GPU.

What is B's, unchanged: the régie (`acting.timeline.ShotActing`: A* paths, speeds, turns, sits, gestures, reactions, speech
behaviour, gaze, continuity of states between shots of the same world) and the cinematographer (`acting.cinema.solve`:
sizes, lens, 180-degree rule, over-the-shoulder / clean singles, moves, no zoom). What is new here is only the translation
of their output (sampled every frame) into the columns of the contract, plus two camera rigs that are tables
(`orbit_keys`, `path`) for shots a film wants written exactly.

Nothing here draws. No randomness, no clock: the same episode gives the same contract.
"""
import copy, json, math
import numpy as np
from ..acting import cinema, rig, gestures as GS
from ..acting.timeline import ShotActing, smooth, wrap
from ..acting import timeline as TL, approach
from . import contract as C
from .worlds import VoxWorld, WORLDS
from .tracks import TrackActing
from . import blocking as BLK, camplan as CAMP, faceact as FACE, genre_intent as GENRE, footkin as FK, b_props as BP, b_sets as BS, b_space as SP, b_chars as BC, b_monsters as BM, b_extras as EX

HAND_IDX = {'relaxed': 0, 'fist': 1, 'open': 2, 'point': 3, 'grip': 4}

# B's face names (director/validate.FACES) -> the expressions of A (engine/face4.js). Each of the 43 names of B now has ITS OWN preset in face4.js (same name):
# nothing falls back on "the closest of the 17" any more. EXPR_MAP_LEGACY is the old 17-preset table, kept so a film made before this port can be re-rendered as it was:
# set HSTUDIO_EXPR_LEGACY=1 in the environment (the 17 presets themselves are unchanged either way).
EXPR_MAP_LEGACY = {
    'neutral': 'neutral', 'calm': 'neutral', 'cool': 'neutral', 'talk': 'neutral', 'closed': 'blink', 'sleeping': 'blink', 'bored': 'neutral', 'tired': 'sad',
    'happy': 'smile', 'joy': 'smile', 'grin': 'smile', 'laugh': 'smile', 'smirk': 'smile', 'proud': 'smile', 'love': 'smile', 'wink': 'smile', 'silly': 'smile', 'excited': 'surprised',
    'shy': 'worried', 'nervous': 'worried', 'confused': 'worried', 'thinking': 'worried', 'suspicious': 'worried', 'urgent': 'worried', 'dizzy': 'worried', 'smile_sad': 'sad',
    'sad': 'sad', 'crying': 'cry', 'pain': 'grit', 'disgusted': 'grit', 'angry': 'grit', 'furious': 'shout', 'evil': 'determined', 'determined': 'determined',
    'scared': 'scared', 'shocked': 'scream', 'surprised': 'surprised', 'relief': 'relief',
}
EXPR_MAP = dict(EXPR_MAP_LEGACY) if __import__('os').environ.get('HSTUDIO_EXPR_LEGACY') == '1' else {n: n for n in (
    'neutral', 'talk', 'closed', 'calm', 'cool', 'bored', 'tired', 'sleeping', 'urgent', 'happy', 'grin', 'joy', 'laugh', 'excited', 'love', 'wink', 'silly', 'smirk', 'proud', 'shy',
    'nervous', 'confused', 'thinking', 'suspicious', 'dizzy', 'smile_sad', 'sad', 'crying', 'pain', 'disgusted', 'angry', 'furious', 'evil', 'determined', 'scared', 'shocked',
    'surprised', 'relief', 'ko', 'skull', 'robot', 'alien', 'creature', 'double',
    'fixed_smile', 'predator', 'predator_smile')}      # 6/11/2026 : les 3 expressions du récit ont leur préréglage VOXEL
# arm pose -> hand pose of A (0 relaxed, 1 fist, 2 open, 3 point, 4 grip)
HAND_OF = {'point': 3, 'fist': 1, 'thumb': 1, 'knock': 1, 'wave': 2, 'stop': 2, 'surrender': 2, 'up': 2, 'stretch': 2, 'salute': 2, 'clap': 2, 'pray': 2, 'hug': 2,
           'hold': 4, 'hold_up': 4, 'reach': 2, 'forward': 2, 'side': 2, 'shrug': 2, 'wide': 2, 'wide_up': 2}
K_WALK = 2 * math.pi / .853      # A's walk: 0.95 m/s at 7 rad/s -> one cycle (two steps) per 0.853 m
K_RUN = 11. / 3.4                # A's run: phase 11 rad/s at 3.4 m/s
V_WALK, V_RUN = .95, 3.4
SEAT_H = round(FK.seat_for_flat_feet(), 3)     # a sitting body's soles on the floor (the old .47 sank them 4.8 cm into it)
HEAD_W = .85                     # width of A's head WITH its hair (m), told to the cinematographer so a close shot leaves it room
EYE, HEIGHT = 1.82, 2.2          # A's characters are taller than B's skeleton (1.85 m): eye and top of the head
ASPECT_K = {'9:16': (9 / 16, 1.0), '16:9': (16 / 9, .72)}      # (width/height, vertical field factor, as B's pixel3d)
CLEAR = ('wide', 'full', 'medium_full', 'establishing', 'group', 'two_shot', None)


def _eff_fov(fov, fov_k): return math.degrees(2 * math.atan(math.tan(math.radians(fov) / 2) * fov_k))


def _scale_of(casts, aid):
    d = casts.get(aid) or {}
    return float(d.get('scale') or (.95 if d.get('preset') == 'lina' else 1.05 if d.get('preset') == 'alien' else 1.))


def _subject(aid, s, scale, face):
    k = rig.smooth(s['rig'].get('sit', 0.)); y = s.get('y', 0.)
    gz = s['heading'] + float(s['rig'].get('head', (0., 0.))[0]) if face else None
    return cinema.Subject(aid, s['x'], s['z'], s['heading'], eye=(EYE - .42 * k) * scale + y, height=HEIGHT * scale, base=y, gaze=gz, head_w=HEAD_W * scale)


def _capsule(s, scale):
    k = rig.smooth(s['rig'].get('sit', 0.))
    return (s['x'], s['z'], (HEIGHT - .42 * k) * scale + s.get('y', 0.))


def _probe(others):
    """a point is seen from pos unless another character (a vertical capsule) stands in between"""
    def probe(pos, pt):
        O = np.asarray(pos, float); P = np.asarray(pt, float); d = P - O
        for (ox, oz, oh) in others or []:
            if math.hypot(P[0] - ox, P[2] - oz) < .4: continue
            dx, dz = d[0], d[2]; ll = dx * dx + dz * dz
            if ll < 1e-6: continue
            u = ((ox - O[0]) * dx + (oz - O[2]) * dz) / ll
            if .05 < u < .95 and math.hypot(O[0] + dx * u - ox, O[2] + dz * u - oz) < .3 and O[1] + d[1] * u < oh: return False
        return True
    return probe


class CameraPlan:
    """one shot's camera: `at(t)` -> (pos, target, fov, roll) in stage-local metres"""

    def __init__(self, sa, shot, world, casts, aspect, memory, abs_t0, subject_ids, first_in_world, lead=0.):
        self.lead = lead; self.sa = sa; self.world = world; self.casts = casts; self.abs_t0 = abs_t0; self.memory = memory
        self.aspect_k, self.fov_k = ASPECT_K[aspect]
        c = dict(shot.get('camera') or {})
        self.mode = c.get('rig', 'solve'); self.c = c; self.dur = sa.dur; self.plan = None
        self.ids = [a for a in (c.get('on') if isinstance(c.get('on'), list) else [c['on']] if c.get('on') else subject_ids) if a in sa.tracks] or [a for a in subject_ids if a in sa.tracks]
        if self.mode == 'solve':
            if not c.get('shot'):                         # no intention written: B's coverage planner decides
                speaking = [a for a in self.ids if any(l[2] == a for l in sa.lines)]
                moving = [a for a in self.ids if sa.sample(.5 * sa.dur)[a]['rig'].get('gait', 0) > .5]
                c.update(cinema.auto_camera(shot, self.ids, speaking, moving, first_in_world, None, self.aspect_k)); self.c = c
            self.plan = self._plan()

    # -- camera by intention (a port of pixel3d/acted.plan_camera: the same solver, the same 5 sampled moments, the same follow keys)
    def _plan(self):
        sa, c, ids, ak, fk = self.sa, self.c, self.ids, self.aspect_k, self.fov_k
        face = bool(c.get('face_track') or c.get('clear_face'))
        end = min(sa.dur, max([tr.cursor for tr in sa.tracks.values()] + [.5]))
        follow = c.get('move') == 'follow'
        times = [0.] if follow else sorted(set([0., end * .25, end * .5, end * .75, end, min(sa.dur, end + .5)]))
        subj = []; gz = {}
        for t in times:
            ss = sa.sample(t)
            got = [_subject(a, ss[a], _scale_of(self.casts, a), face) for a in ids if a in ss]
            subj += got
            for s_ in got:
                if s_.gaze is not None: gz.setdefault(s_.id, []).append(s_.gaze)
        ssE = sa.sample(end); last = [_subject(a, ssE[a], _scale_of(self.casts, a), face) for a in ids if a in ssE]
        for s_ in subj: s_.heading = next((l.heading for l in last if l.id == s_.id), s_.heading)
        moved = any(math.hypot(a.x - b.x, a.z - b.z) > .6 for a in subj for b in subj if a.id == b.id)
        if not moved: subj = list(last)
        elif len(ids) == 1 and c.get('shot') in ('close', 'extreme_close', 'medium'): subj = list(last)
        for s_ in subj:
            v = gz.get(s_.id)
            if s_.gaze is not None and v: s_.gazes = tuple(v)
        smid = sa.sample(end * .5)
        oth = [_capsule(v, _scale_of(self.casts, a)) for a, v in smid.items() if a not in ids]
        def blocked_at(t, r=.6):
            sm = sa.sample(t); o = [(v['x'], v['z']) for a, v in sm.items() if a not in ids]
            return lambda p: self.world.blocked_for_camera(p) or any(math.hypot(p[0] - ox, p[2] - oz) < r for ox, oz in o)
        blocked = blocked_at(min(sa.dur, .5), .38 if c.get('shot') in ('ots', 'dialogue', 'close', 'extreme_close', 'medium') else 1.0)
        fr = c.get('from')
        if fr is not None:
            fp = sa.world.anchor(fr) if isinstance(fr, str) else (fr if isinstance(fr, (list, tuple)) and len(fr) == 2 else None)
            if fp:
                cx = sum(s_.x for s_ in subj) / len(subj); cz = sum(s_.z for s_ in subj) / len(subj)
                c = dict(c, _from_az=math.atan2(float(fp[0]) - cx, float(fp[1]) - cz))
        if len(ids) == 1 and c.get('shot') in ('close', 'extreme_close', 'medium', 'medium_full') and not moved and c.get('from') is None:
            me = smid[ids[0]]; hm = me['heading'] + float(me['rig'].get('head', (0., 0.))[0])
            def faced(v):
                dx, dz = v['x'] - me['x'], v['z'] - me['z']; L = math.hypot(dx, dz) + 1e-6
                return (dx * math.sin(hm) + dz * math.cos(hm)) / L - .15 * L
            ppl = [(faced(v), a) for a, v in smid.items() if a != ids[0] and math.hypot(v['x'] - me['x'], v['z'] - me['z']) < 3.2]
            if ppl:
                pa = smid[max(ppl)[1]]; c = dict(c, _partner=cinema.Subject(max(ppl)[1], pa['x'], pa['z'], pa['heading'], EYE))
        sol = cinema.solve(c, subj, ak, fk, _probe(oth) if c.get('shot') != 'ots' else None, blocked, self.memory)
        if sol is None: raise ValueError(f"plan sans caméra : le cinématographe n'a trouvé aucune position pour {c.get('shot')} sur {ids}")
        plan = dict(sol=sol, cam=c, step=.1)
        ts = np.arange(0., sa.dur + .2, .1)
        if follow:
            vmax = 0.
            for t in np.arange(0., sa.dur, .25):
                for i_ in ids:
                    p0 = sa.position(sa.tracks[i_], float(t)); p1 = sa.position(sa.tracks[i_], float(t) + .25)
                    vmax = max(vmax, math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / .25)
            fast = vmax > 2.2; kstep = .5 if fast else 1.; lag = .06 if fast else .25
            keys = []; prev = None
            for t in list(np.arange(0., sa.dur + 1e-3, kstep)) + [sa.dur]:
                smp = sa.sample(float(t)); sj = [_subject(a, smp[a], _scale_of(self.casts, a), face) for a in ids if a in smp]
                ck = dict(c, move='static'); ck.setdefault('shot', 'full'); ck.setdefault('angle', 1.0)
                if prev is not None: ck['_prefer_az'] = prev
                o2 = [_capsule(v, _scale_of(self.casts, a)) for a, v in smp.items() if a not in ids]
                so = cinema.solve(ck, sj, ak, fk, _probe(o2), blocked_at(float(t), .95), self.memory)
                if so is None: continue
                prev = so.get('az'); keys.append((float(t), np.array(so['pos'], float), np.array(so['target'], float), so['fov']))
            if keys:
                P_ = []; Tg = []
                for t in ts:
                    j = max(0, min(len(keys) - 2, int(np.searchsorted([k_[0] for k_ in keys], t)) - 1)) if len(keys) > 1 else 0
                    if len(keys) == 1: P_.append(keys[0][1]); Tg.append(keys[0][2]); continue
                    a_, b_ = keys[j], keys[j + 1]; w_ = cinema.smooth((t - a_[0]) / max(1e-3, b_[0] - a_[0]))
                    P_.append(a_[1] * (1 - w_) + b_[1] * w_)
                    cen = self._centroid(ids, t - lag)
                    tg = a_[2] * (1 - w_) + b_[2] * w_; Tg.append(np.array([cen[0] * .5 + tg[0] * .5, tg[1], cen[1] * .5 + tg[2] * .5]))
                P_ = np.array(P_); Tg = np.array(Tg); k_ = np.ones(5) / 5
                for arr in (P_, Tg):
                    for j in range(3):
                        pad = np.concatenate([np.full(2, arr[0, j]), arr[:, j], np.full(2, arr[-1, j])]); arr[:, j] = np.convolve(pad, k_, 'valid')
                plan['path'] = (ts, P_, Tg); plan['sol'] = dict(sol, fov=max(k_[3] for k_ in keys))
        elif moved and c.get('shot') in CLEAR:
            c0 = np.array(sol['target'], float); cen0 = self._centroid(ids, end * .5); cp = np.array(sol['pos'], float); R0 = float(math.hypot(c0[0] - cp[0], c0[2] - cp[2])) or 1.; Tg = []
            for t in ts:
                acc = [self._centroid(ids, t - .6 * i / 4) for i in range(5)]
                cx = sum(p[0] for p in acc) / 5; cz = sum(p[1] for p in acc) / 5
                g = c0 + np.array([(cx - cen0[0]) * .6, 0., (cz - cen0[1]) * .6]); dx, dz = float(g[0] - cp[0]), float(g[2] - cp[2]); L = math.hypot(dx, dz) or 1.
                Tg.append(np.array([cp[0] + dx / L * R0, c0[1], cp[2] + dz / L * R0]))
            plan['pan'] = (ts, np.array(Tg))
        mv = c.get('move')
        if mv in ('dolly_in', 'push', 'dolly_out', 'track', 'orbit', 'crane_up', 'crane_down') and plan.get('path') is None:
            amt = float(c.get('amount', .5)); heads = [(s_.x, s_.eye, s_.z) for s_ in subj if s_.id != 'poi'][:4]; probe = _probe(oth)
            for _ in range(5):
                cc = dict(c, amount=amt); ends = [cinema.apply_move(sol, cc, uu, 0.)[0] for uu in (0., .5, 1.)]
                if not any(self.world.blocked_for_camera(p_) for p_ in ends) and all(probe(ends[-1], h_) for h_ in heads): break
                amt *= .5
            else: amt = 0.
            plan['cam'] = dict(c, amount=amt) if amt > .03 else dict(c, move='static')
        return plan

    def _centroid(self, ids, t):
        t = max(0., min(self.sa.dur, t)); ps = [self.sa.position(self.sa.tracks[a], t) for a in ids if a in self.sa.tracks]
        return (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps))

    # -- evaluation
    def at(self, t, smp=None):
        if self.mode == 'orbit_keys': return self._orbit_keys(t, smp)
        if self.mode == 'path': return self._path(t, smp)
        plan = self.plan; sol, c = plan['sol'], plan['cam']
        if plan.get('path') is not None:
            ts, P_, Tg = plan['path']; f = min(max(t / plan['step'], 0.), len(ts) - 1.001); i = int(f); w_ = f - i
            sol = dict(sol, pos=tuple(float(P_[i][j] * (1 - w_) + P_[i + 1][j] * w_) for j in range(3)), target=tuple(float(Tg[i][j] * (1 - w_) + Tg[i + 1][j] * w_) for j in range(3)))
            c = dict(c, move='static')
        elif plan.get('pan') is not None:
            ts, Tg = plan['pan']; f = min(max(t / plan['step'], 0.), len(ts) - 1.001); i = int(f); w_ = f - i
            sol = dict(sol, target=tuple(float(Tg[i][j] * (1 - w_) + Tg[i + 1][j] * w_) for j in range(3)))
        if c.get('shot') == 'pov' and self.ids:
            s = (smp or self.sa.sample(t)).get(self.ids[0])
            if s:
                hy, hp = s['rig'].get('head', (0., 0.)); h = s['heading'] + hy; eye = (EYE - .42 * rig.smooth(s['rig'].get('sit', 0.))) * _scale_of(self.casts, self.ids[0]) + s.get('y', 0.)
                pos = (s['x'] + math.sin(h) * .12, eye, s['z'] + math.cos(h) * .12); sol = dict(sol, pos=pos, target=(pos[0] + math.sin(h) * 4, eye - .25 + 4 * math.tan(hp), pos[2] + math.cos(h) * 4))
        u = max(0., t - self.lead) / max(1e-6, self.dur - self.lead)
        pos, tgt = cinema.apply_move(sol, c, u, self.abs_t0 + t - self.lead)
        roll = math.radians(float(c.get('roll', 0.)))
        return pos, tgt, _eff_fov(sol.get('fov', 50.) * getattr(self.world, 'fov_boost', 1.), self.fov_k), roll      # `fov_boost` : champ plus large dans une pièce (b_sets.BSetWorld)

    # -- tables
    def _orbit_keys(self, t, smp):
        """camera around a character from a table of marks [[t_abs, angle, distance, camera height, look height, fov], ...]
        (angle from +x towards +z); smoothstep between marks; optional roll sway. Evaluated on the ABSOLUTE time, so two stages
        that dissolve into each other share the same camera."""
        c = self.c; T = self.abs_t0 + t - self.lead; keys = c['keys']
        j = 0
        while j < len(keys) - 2 and T > keys[j + 1][0]: j += 1
        a, b = keys[j], keys[j + 1]; k = smooth((T - a[0]) / max(1e-6, b[0] - a[0])); v = [a[i] * (1 - k) + b[i] * k for i in range(1, 6)]
        s = (smp or self.sa.sample(t))[self.ids[0]]; ang, dist, ch, lh, fov = v
        pos = (s['x'] + math.cos(ang) * dist, ch, s['z'] + math.sin(ang) * dist)
        tgt = (s['x'] + float(c.get('look_dx', .25)), lh, s['z'] + float(c.get('look_dz', 0.)))
        roll = math.radians(float(c.get('roll_deg', 0.))) * math.sin(2 * math.pi * T / float(c.get('roll_period', 16.)))
        return pos, tgt, _eff_fov(fov, self.fov_k), roll

    def _path(self, t, smp=None):
        """camera from a table of keys {t, pos, look, fov, roll}. `look` may be a point or {"on": actor, "h": height, "dx","dz"} (the point is
        read from the actor's track at that time), so a shot can follow somebody without the cinematographer"""
        c = self.c; keys = c['keys']; T = t - self.lead + (self.abs_t0 if c.get('absolute') else 0.)
        j = 0
        while j < len(keys) - 2 and T > keys[j + 1]['t']: j += 1
        a, b = keys[j], keys[min(j + 1, len(keys) - 1)]; k = smooth((T - a['t']) / max(1e-6, b['t'] - a['t'])) if b is not a else 0.
        if b is not a and (b.get('cut') or a.get('hold')): k = 0.
        smp = smp or (self.sa.sample(t) if self.sa is not None else {})

        def pt(v):
            if isinstance(v, dict):
                s_ = smp.get(v['on'])
                if s_ is None: raise ValueError(f"caméra : l'acteur {v['on']!r} n'est pas dans le plan")
                return (s_['x'] + float(v.get('dx', 0.)), float(v.get('h', 1.4)) + s_.get('y', 0.), s_['z'] + float(v.get('dz', 0.)))
            return tuple(v)
        mix = lambda p, q: tuple(p[i] * (1 - k) + q[i] * k for i in range(3))
        roll = float(a.get('roll', c.get('roll', 0.))) * (1 - k) + float(b.get('roll', c.get('roll', 0.))) * k
        return mix(pt(a['pos']), pt(b['pos'])), mix(pt(a['look']), pt(b['look'])), _eff_fov(a.get('fov', 50) * (1 - k) + b.get('fov', 50) * k, self.fov_k), math.radians(roll)


# ---------------------------------------------------------------------------------------------------------------- actor rows
class RowMaker:
    """turns B's per-frame samples of one character into contract rows. Gait phase is DRIVEN BY DISTANCE with A's own
    stride (0.853 m per walk cycle), so A's feet do not slide on the ground whatever stride B's skeleton would use."""

    def __init__(self, fps, scale, planted=False):
        self.fps = fps; self.scale = scale; self.dist = 0.; self.last = None; self.v_s = 0.; self.steps = []; self.prev_ph = None; self.ph_run = 0.
        self.planted = planted; self.pphase = 0.          # opt-in `gait: planted`: phase integrated with the stride that plants the foot (footkin.planted_gait)

    def row(self, t, s, exprs):
        p = s['rig']; ix = C.ACTOR_COLS; r = dict.fromkeys(ix, 0.)
        k_sit = rig.smooth(p.get('sit', 0.)); h = s['heading']
        x, z = s['x'], s['z']
        if k_sit > 0:                                      # B's x, z are the feet; A's root is the pelvis, behind them on a seat
            d = float(p.get('seat_z', -.30)) * k_sit; x += math.sin(h) * d; z += math.cos(h) * d
        v = 0.
        if self.last is not None:
            v = math.hypot(x - self.last[0], z - self.last[1]) * self.fps; self.dist += v / self.fps
        self.last = (x, z); self.v_s += (v - self.v_s) * .5           # light smoothing, no lag worth the name at 24 fps
        run = float(p.get('run', 0.)); mode = 2 if run > .5 else 1 if (self.v_s > .08 or p.get('gait', 0.) > .25) else 0
        if p.get('air', 0.) > .05: mode = 0
        r['vis'] = 1. if s.get('visible', True) else 0.
        r['x'], r['y'], r['z'], r['yaw'] = x, s.get('y', 0.), z, h
        r['gait'] = mode
        if mode == 2:
            r['phase'] = self.dist * K_RUN; r['amp'] = min(1., max(.35, self.v_s / V_RUN))
        elif mode == 1:
            r['phase'] = self.dist * K_WALK; r['amp'] = .62 * min(1.35, max(.12, self.v_s / V_WALK)) ** .8 if self.v_s > .08 else .12
        if self.planted:
            pg = FK.planted_gait(self.v_s, run=mode == 2) if mode in (1, 2) else None
            self.pphase += (v / self.fps) * (pg[0] if pg else (K_RUN if mode == 2 else K_WALK))
            if mode in (1, 2):
                r['phase'] = self.pphase
                if pg: r['amp'] = pg[1]
        if p.get('back') and mode in (1, 2): r['phase'] = -r['phase']       # walking backwards: the legs cycle the other way, so the planted foot still does not slide
        r['sit'] = k_sit; r['seat_h'] = float(p.get('seat_h', SEAT_H)); r['crouch'] = rig.smooth(p.get('crouch', 0.)); r['air'] = float(p.get('air', 0.))
        r['lean'] = float(p.get('lean', 0.)) + .16 * float(p.get('slump', 0.)) - .07 * float(p.get('chest_up', 0.)) + .04 * float(p.get('tension', 0.))
        f_ = s.get('face', 'neutral'); face = EXPR_MAP.get(f_, f_ if f_ in exprs else 'neutral'); r['expr'] = exprs.index(face)
        r['talk'] = 1. if s.get('talking') else 0.
        hy, hp = p.get('head', (0., 0.)); r['hyaw'], r['hpit'] = float(hy), float(hp)
        # arms: only when something other than the walk swing asks for them (gesture, reach, air, tension): B's skeleton gives
        # elbow and wrist offsets from the shoulder, A's IK puts its own wrist there
        gests = [g for g in (p.get('gestures') or []) if g[1] > 1e-3]; tot = min(1., sum(g[1] for g in gests))
        reach = max([w for (_, w) in (p.get('reach') or {}).values()] + [0.])
        w = min(1., tot + reach + .8 * float(p.get('air', 0.)) * (p.get('air_style') != 'climb'))
        if w > .02:
            sk = rig.solve(p); J = sk.joints
            for side, tag, key in ((1, 'R', 'p'), (-1, 'L', 'n')):
                sh = J['sh' + tag]; el = J['el' + tag]; ha = J['ha' + tag]
                for a, vv in zip('xyz', el - sh): r[f'e{key}{a}'] = float(vv)
                for a, vv in zip('xyz', ha - sh): r[f'h{key}{a}'] = float(vv)
                best = max(gests, key=lambda g: g[1], default=None)
                if best is not None: r['hand' + key] = HAND_OF.get(GS_ARM(best[0], -side if p.get('left') else side), 0)      # `side: left` : le geste est joué par l'autre bras
        hp = p.get('hands')
        if hp:
            hl, hr = (hp, hp) if isinstance(hp, str) else hp
            r['handp'], r['handn'] = HAND_IDX.get(hl, 0), HAND_IDX.get(hr, 0)
            r['armw'] = w
        r['armw'] = w
        row = [float(r[c]) for c in ix]
        # heel strikes (A convention: phase = pi/2 + k*pi), for footprints
        if mode in (1, 2):
            ph = r['phase']
            if self.prev_ph is not None and ph > self.prev_ph:
                k0 = math.floor((self.prev_ph - math.pi / 2) / math.pi) + 1; k1 = math.floor((ph - math.pi / 2) / math.pi)
                for kk in range(k0, k1 + 1):
                    self.steps.append([round(t, 4), x, z, h, 1 if kk % 2 == 0 else -1])
            self.prev_ph = ph
        return row


def GS_ARM(name, side):
    main, other = GS.GESTURES.get(name, ('down', 'down'))
    return main if side > 0 else other


def _expand_props(items, sets):
    """a props list may contain {"use": "name"} entries that stand for a named list of `prop_sets` (reusable dressing); nesting allowed"""
    out = []
    for it in items:
        if isinstance(it, dict) and 'use' in it and 'type' not in it:
            if it['use'] not in sets: raise ValueError(f"jeu d'accessoires inconnu : {it['use']!r} (définis : {', '.join(sets) or 'aucun'})")
            out.extend(_expand_props(sets[it['use']], sets))
        else: out.append(it)
    return out


# ---------------------------------------------------------------------------------------------------------------- build
def build(ep, aspect=None, fps=None, verbose=False):
    """episode (dict) -> contract (dict). The episode DSL is B's, see docs/VOXELGPU.md for the keys added for the painter."""
    from .. import profiles; profiles.apply(ep)                                                          # "profile": "production" (même profil que PIXEL 3D)
    from ..engines.pixel3d import quartiers as QT; QT.configure(ep.get('diversite'), ep)                  # clé `diversite` (quartiers et intérieurs variés) : posée par le profil, lue aussi par les lieux de VOXEL ; absente = rien ne change
    from ..engines.pixel3d import objets as OD; OD.configure(ep.get('objets'), ep)                         # clé `objets` (objets détaillés, 01/11/2026) : posée par le profil ; absente = rien ne change
    aspect = aspect or ep.get('aspect', '9:16'); fps = int(fps or ep.get('fps', 24))
    if aspect not in ASPECT_K: raise ValueError(f'format inconnu : {aspect}')
    casts = {k: BM.resolve(k, BC.resolve(k, v)) for k, v in (ep.get('casts') or {}).items()}      # personnages et animaux de PIXEL 3D (b_chars.py) ; un cast sans leurs clés est copié tel quel
    exprs = list(C.EXPRESSIONS)
    shots = ep['shots']; dis = [float(s.get('dissolve', 0.)) if i else 0. for i, s in enumerate(shots)]
    t0s = []; t = 0.
    for s in shots:
        t0s.append(t); t += float(s['dur'])
    total = float(ep.get('duration') or t)
    states = {}; props = {}; memory = {}; stages = []; seen_world = set(); extras_reports = []
    blk = geo = None; report = None
    if ep.get('blocking'):       # one trajectory per actor for the WHOLE film, checked against the place before any image (blocking.py, camplan.py)
        blk, geo = GENRE.compile_episode(ep)      # transparent without `vanish` beats; with them: one life per appearance, declared and verified
        for a in blk.actors: casts.setdefault(a, {'preset': 'npc'})
        abs_shots = [dict(sh, _t0=t0s[i]) for i, sh in enumerate(shots) if sh.get('frame')]
        viol, report = GENRE.preflight(ep, blk, geo, abs_shots, aspect)
        if viol and ep['blocking'].get('audit', 'strict') == 'strict':
            raise ValueError('mise en scène refusée avant rendu (%d problèmes) :' % len(viol) + chr(10) + '  ' + (chr(10) + '  ').join(repr(x) for x in viol[:40]))
    face_rows = {}
    if blk is not None and ep.get('faces', True):            # the face layer (faceact.py): eyes that look, blinks, brows, reactions with a cause, for every character that has a face
        for a in blk.actors:
            if not (casts.get(a) or {}).get('kind'): face_rows[a] = FACE.build(blk, a, EXPR_MAP, exprs, total + 1.)
    for k, shot in enumerate(shots):
        bset = None
        if shot.get('set') is not None:        # un lieu de PIXEL 3D (pièce, maison, rue, forêt...) peint sur le plateau : b_sets.py
            sname = shot['set']; spec = (ep.get('sets') or {}).get(sname) if isinstance(sname, str) else sname
            if spec is None: raise ValueError(f"plan {k} : lieu « {sname} » absent de `sets` de l'épisode")
            bset = BS.get(sname if isinstance(sname, str) else spec.get('type', 'set'), spec); world = bset.world; wname = 'plateau'
            for an, av in (shot.get('anchors') or {}).items(): world.a[an] = tuple(av)
        else:
            wname = shot['stage']; world = VoxWorld(wname, shot.get('anchors'))
        dur = float(shot['dur']); tail = dis[k + 1] if k + 1 < len(shots) else 0.
        skey = wname + (':' + (shot['set'] if isinstance(shot['set'], str) else json.dumps(shot['set'], sort_keys=True)) if bset else '')
        st = states.setdefault(skey, {}); ps = props.setdefault(skey, {})
        if shot.get('reset'): st.clear(); ps.clear()
        for a in [x.get('id', 'hero') for x in (shot.get('actors') or [])] + [x.get('who', 'hero') for x in (shot.get('actions') or [])]:
            if a not in casts: casts[a] = {'preset': 'npc'}
        # espace entre les acteurs et avec les décors (b_space.py) : `spacing` dans l'épisode ou le plan (le studio le pose pour ses nouveaux épisodes ; absent = films déjà faits inchangés), `intimacy` lève la distance de conversation
        spacing = bool(shot.get('spacing', ep.get('spacing', False))); intim = bool(shot.get('intimacy', ep.get('intimacy', False)))
        has_extras = EX.wants(shot, ep) and blk is None and not shot.get('tracks')                          # figurants animés (b_extras.py) : opt-in par la clé `extras` ; la séparation des corps est alors forcée (sauf `extras.spacing: false`)
        if has_extras and (EX._cfg(shot, ep) or {}).get('spacing', True): spacing = True
        pr_ = list(ep.get('world_props') or []) + list(shot.get('props') or [])
        conv_props = BP.convert_props(_expand_props(pr_, ep.get('prop_sets') or {})) if pr_ else None            # décors de PIXEL 3D / vox / craft -> boîtes VOXEL (b_props.py), faits UNE fois : obstacles ET peinture
        space_rects = []
        if spacing:
            shot = SP.spaced_actions(shot, casts, _scale_of, intim)                                               # une approche vers un acteur s'arrête à la distance de conversation
            space_rects = SP.footprints(conv_props[0]) if conv_props else []
            if space_rects: world = SP.ObsWorld(world, space_rects)                                              # l'A* de la régie contourne les décors du plan
        lead = round(float(shot.get('lead', 0.)) * fps) / fps
        if has_extras:
            def _mk_sa(sh, _w=world, _st=st, _ps=ps, _lead=lead):                                                # la régie des seuls principaux : leur trajet fixe les zones interdites aux figurants
                return ShotActing(sh, _w, dict(_st), [(float(l[0]), float(l[1]), l[2], i) for i, l in enumerate(sh.get('speech') or [])], dur + tail + _lead, {a: (casts.get(a) or {}) for a in casts}, _ps,
                                  TL.footing(ep, sh), approach.wanted(ep, sh), TL.planted(ep, sh))      # même lecture que PIXEL 3D ("off" veut dire off)
            def _probe(sa0, _shot=shot, _w=world, _lead=lead, _k=k):                                          # la caméra du plan sans figurants : trois instants (pose, cible, champ)
                try:
                    cp = CameraPlan(sa0, dict(_shot, **{'extras': False}), _w, casts, aspect, copy.deepcopy(memory), t0s[_k], [a for a in sa0.tracks if a in sa0.tracks and not (casts.get(a) or {}).get('extra')], skey not in seen_world, _lead)
                    return [(lambda r: ((r[0][0], r[0][1], r[0][2]), (r[1][0], r[1][1], r[1][2]), r[2], ASPECT_K[aspect][0]))(cp.at(tt, sa0.sample(tt))) for tt in (0., max(0., (dur + tail) / 2.), max(0., dur + tail - .1))]
                except Exception: return None
            tags = list(WORLDS.get(wname, {}).get('tags', [])) + (['night'] if bset is not None and (getattr(bset.st, 'spec', {}) or {}).get('sky') == 'night' else [])
            xr = EX.expand(shot, k, ep, world, casts, st, _mk_sa, dur + tail + lead, wname, tags, bool(getattr(world, 'indoor', False)), shot['set'] if isinstance(shot.get('set'), str) else None, _scale_of,
                           lambda cid, d: BM.resolve(cid, BC.resolve(cid, d)), fps, _probe)
            if xr:
                shot, new_casts, xrep = xr; casts.update(new_casts); extras_reports.append(xrep)
        elif blk is None and not shot.get('tracks'):                                                              # figurants d'un plan précédent de ce lieu : sans `extras` ici, ils quittent le plan (pas de statues)
            gone_ = [a for a, c in casts.items() if (c or {}).get('extra') and a in st and not st[a].get('gone')]
            if gone_: shot = dict(shot, absent=sorted(set(shot.get('absent') or []) | set(gone_)))
        lines = [(float(l[0]), float(l[1]), l[2], i) for i, l in enumerate(shot.get('speech') or [])]     # (t0, t1, who) relative to the shot
        if blk is not None:
            lead = 0.; sa = BLK.BlockedActing(blk, t0s[k], dur + tail)
        elif shot.get('tracks'):
            for a in shot['tracks']: casts.setdefault(a, {'preset': 'npc'})
            sa = TrackActing(shot, dur + tail + lead, casts)
        else:
            sa = ShotActing(shot, world, st, lines, dur + tail + lead, {a: (casts.get(a) or {}) for a in casts}, ps,
                            TL.footing(ep, shot), approach.wanted(ep, shot), TL.planted(ep, shot))
        if spacing and blk is None and not shot.get('tracks'): sa = SP.ConversationSpacing(sa, fps, casts, _scale_of, intim, space_rects)       # corps qui ne se traversent pas, distance de conversation
        st.update(sa.end_states())
        ids = [a for a in sa.tracks.keys() if not (casts.get(a) or {}).get('worlds') or wname in casts[a]['worlds']]      # an actor that belongs to other worlds is not drawn (nor written) in this one
        cam = CameraPlan(sa, shot, world, casts, aspect, memory, t0s[k], [a for a in ids if not (casts.get(a) or {}).get('extra')] or ids, skey not in seen_world, lead); seen_world.add(skey)
        n = int(math.ceil((dur + tail) * fps - 1e-9)) + 2
        makers = {a: RowMaker(fps, _scale_of(casts, a), ep.get('gait') == 'planted') for a in ids}
        actors = {a: [] for a in ids}; camera = []; faces = {a: [] for a in face_rows if a in ids}
        j0 = int(round(lead * fps))
        for j in range(n + j0):                         # the lead is played (so walkers are already walking) but not stored
            tt = j / fps; smp = sa.sample(tt)
            rows = {a: makers[a].row(tt - lead, smp[a], exprs) for a in ids}
            if j < j0: continue
            for a in ids: actors[a].append(rows[a])
            for a, fr_ in face_rows.items():
                if a in faces: faces[a].append(fr_[min(len(fr_) - 1, int(round(max(0., t0s[k] + tt - lead) * FACE.HZ)))])      # FILM time, not the stage's: face rows are indexed from the start of the film
            pos, tgt, fov, roll = cam.at(tt, smp)
            camera.append([round(float(v), 5) for v in (*pos, *tgt, fov, roll)])
        stage = dict(id=shot.get('id', f'{k:02d}_{wname}'), world=wname, t0=t0s[k], t1=t0s[k] + dur, tail=tail, dissolve=dis[k], mood=shot.get('mood', ep.get('mood')),
                     look=shot.get('look') or {}, camera=camera, actors={a: [[round(v, 5) for v in row] for row in rows] for a, rows in actors.items()},
                     focus_actor=shot.get('focus_actor', (cam.ids or [None])[0]))
        for key in ('dof', 'mblur', 'shadow_s', 'env', 'shake', 'spots', 'lights'):
            if key in shot: stage[key] = shot[key]
        if shot.get('prints'):
            pr = dict(shot['prints']); who = pr.setdefault('actor', stage['focus_actor']); stage['prints'] = pr
            stage['steps'] = {who: [[s_[0] + t0s[k], *s_[1:]] for s_ in makers[who].steps]}
        if bset:
            part = bset.stage_parts(t0s[k], t0s[k] + dur + tail); stage['props'] = part['props']; stage['lights'] = part['lights'] + list(stage.get('lights') or []); stage['env'] = {**part['env'], **(stage.get('env') or {})}
            if shot.get('weather') is not None: stage['env']['weather'] = shot['weather']; stage['env']['weather_amount'] = float(shot.get('weather_amount', 1.))
            if bset.doors: stage['doors'] = bset.door_tracks(sa, len(camera), j0, fps)
        if conv_props:
            sp_, b_lights = conv_props
            stage['props'] = list(stage.get('props') or []) + sp_
            if b_lights: stage['lights'] = list(stage.get('lights') or []) + b_lights
        if faces: stage['faces'] = {a: [[round(v, 4) for v in r] for r in rows] for a, rows in faces.items()}
        if blk is not None: stage['contacts'] = BLK.contacts_for_painter(blk, t0s[k], t0s[k] + dur + tail)
        if ep.get('world_env'): stage['env'] = {**ep['world_env'], **(stage.get('env') or {})}
        stage['foley_steps'] = {a: [[round(t0s[k] + s_[0], 4), *s_[1:]] for s_ in makers[a].steps] for a in ids if makers[a].steps}
        stages.append(stage)
        if verbose: print(f"[voxelgpu] plan {k} {wname}: {len(ids)} acteurs, {n} images, caméra {cam.mode}/{(cam.c or {}).get('shot')}")
    genre = ep.get('genre', 'neutral')
    for s in stages:
        if not s.get('mood') and ep.get('genre'): s['mood'] = C.GENRES.get(genre, 'neutral')
    out = dict(schema=C.SCHEMA, face_style=('legacy' if __import__('os').environ.get('HSTUDIO_FACE_LEGACY') == '1' else 'natural'), title=ep.get('title', 'sans titre'), genre=genre, aspect=aspect, fps=fps, duration=total, casts=casts, expressions=exprs,
               actor_cols=C.ACTOR_COLS, stages=stages, fx=ep.get('fx') or [], captions=ep.get('captions') or [], caption_style=ep.get('caption_style') or {}, hud=ep.get('hud'), cards=ep.get('cards') or [],
               audio=ep.get('audio') or {})
    if ep.get('words'): out['words'] = C.clean_words(ep['words'])                       # mots 3D d'un clip musical (peints par VOXEL, voir docs/FORMAT_EPISODE.md)
    if face_rows: out['face_cols'] = FACE.FACE_COLS
    if extras_reports: out['extras'] = extras_reports                                  # figurants : demandés / placés / ignorés par plan (b_extras.py)
    if report is not None: out['preflight'] = report
    probs = C.validate(out)
    if probs: raise ValueError('contrat invalide : ' + '; '.join(probs[:5]))
    return out
