"""PIXEL 3D frames of shots driven by the shared acting layer (actions, continuity, skeleton, cinematographer)."""
import math, numpy as np
from . import r3d
from .r3d import orient
from . import creatures as CR
from . import rigfig
from . import costumes as COS
from . import bodies
from .frame import resolve_look, eval_camera, eval_objects, with_shadows, anchor_xyz, look_angles, shake_offsets, val, without_hidden
from . import effects as FX
from . import lighting as LT
from ...acting import cinema, rig

HEAD_W = .60        # width of a pixel3d head with its hair, measured on rigfig.build (a real head is ~0.16 m)

PRESET_SHOT = {'closeup': 'close', 'medium': 'medium', 'full': 'full', 'wide': 'wide', 'ots': 'ots', 'pov': 'pov', 'high_corner': 'wide', 'low': 'full'}

def cam_boxes(st, sa, times=None):
    """the set as the camera must see it during a shot: doors moved by the characters at their real angles"""
    world = sa.world; gone = set(); extra = []
    for did, dr in getattr(world, 'doors', {}).items():
        if did in getattr(sa, 'doors', {}):
            gone.add(dr['box'])
            for t in sorted(set(times if times is not None else (0., sa.dur * .5, sa.dur))): extra += world.door_boxes(did, sa.door_angle(did, t))
    return [b for i, b in enumerate(st.base.boxes) if i not in gone] + extra

def _probe_fn(st, others=None, boxes=None):
    """visibility of a point: static set boxes + other characters as vertical capsules [(x, z, height)]"""
    boxes = [b for b in (st.base.boxes if boxes is None else boxes) if not b.hidden and b.cast]
    def probe(pos, pt):
        O = np.asarray(pos, np.float32); P_ = np.asarray(pt, np.float32); d = P_ - O; L = float(np.linalg.norm(d))
        if L < 1e-3: return True
        for (ox, oz, oh) in (others or []):
            if math.hypot(P_[0] - ox, P_[2] - oz) < .4: continue          # the character the point belongs to
            dx, dz = float(d[0]), float(d[2]); ll = dx * dx + dz * dz
            if ll < 1e-6: continue
            u = ((ox - O[0]) * dx + (oz - O[2]) * dz) / ll
            if .05 < u < .95 and math.hypot(O[0] + dx * u - ox, O[2] + dz * u - oz) < .28 and O[1] + d[1] * u < oh: return False
        occ = r3d.trace(O[None], (d / L)[None].astype(np.float32), boxes, primary=False, tmax=np.array([L - .15], np.float32), shadow=True)
        return not bool(occ[0])
    return probe

def capsule(v):
    """occluder of a character for the probes: body centre (a seated body is behind the feet) and height"""
    k = rig.smooth(v['rig'].get('sit', 0.)); h = v['heading']; dp = -float(v['rig'].get('seat_z', -.30))
    return (v['x'] - math.sin(h) * dp * k, v['z'] - math.cos(h) * dp * k, 1.9 - .42 * k + v.get('y', 0.))

def _blocked_fn(st, world, boxes=None):
    sp = getattr(st, 'spec', {}) or {}
    rooms = [] if sp.get('outdoor') else [(r.get('origin', [0, 0])[0] - r['size'][0] / 2 + .18, r.get('origin', [0, 0])[1] + .18,
                                          r.get('origin', [0, 0])[0] + r['size'][0] / 2 - .18, r.get('origin', [0, 0])[1] + r['size'][1] - .18,
                                          float(r.get('height', sp.get('height', 2.6))) - .15) for r in sp.get('rooms', []) or []]
    bnd = [r3d.wbounds(b) for b in (st.base.boxes if boxes is None else boxes) if not b.hidden]
    levels = getattr(world, 'has_levels', False)
    def blocked(pos):
        x, y, z = pos
        if levels:                                   # V3: above the level under the camera (over a void: above the ground)
            lv = world.ground_y(x, z)
            if y < (world.floor_y if lv is None else lv) + .25: return True
        elif y < .25: return True
        if rooms and not any(a <= x <= c and b <= z <= d and y <= h for (a, b, c, d, h) in rooms): return True
        for (lo, hi) in bnd:
            if lo[0] - .3 <= x <= hi[0] + .3 and lo[1] - .3 <= y <= hi[1] + .3 and lo[2] - .3 <= z <= hi[2] + .3: return True
        return False
    return blocked

def subjects_at(sa, samp, ids, looks, face=False):
    """face: also tell the cinematographer where each head looks (body heading + head yaw), so that a close shot
    frames the face and not the flat side of the cubic head"""
    out = []
    for aid in ids:
        s = samp.get(aid)
        if s is None: continue
        sc_ = float(looks[aid].get('scale', 1.0)) if aid in looks else 1.
        animal = looks.get(aid, {}).get('kind') in CR.ANIMALS; y = s.get('y', 0.)
        if animal: out.append(cinema.Subject(aid, s['x'], s['z'], s['heading'], .55 * sc_ + y, base=y)); continue
        hd = rig.solve(s['rig']).joints['head'] * sc_; c, s_ = math.cos(s['heading']), math.sin(s['heading'])
        gz = s['heading'] + float(s['rig'].get('head', (0., 0.))[0]) if face else None
        # body refit (opt-in, engines/pixel3d/bodies.py): the head group is smaller and sits a little higher
        # than its joint. Both are told to the cinematographer, which is what makes a close shot come closer.
        # bodies.eye_off(.03) carries that lift AND the 3 cm eye offset scaled with the skull it belongs to: a
        # smaller head has its eyes less far above its own joint. Exactly .03 without the key.
        out.append(cinema.Subject(aid, s['x'] + hd[0] * c + hd[2] * s_, s['z'] - hd[0] * s_ + hd[2] * c, s['heading'],
                                  float(hd[1]) + bodies.eye_off(.03) * sc_ + y,
                                  base=y, gaze=gz, head_w=HEAD_W * bodies.head_scale() * sc_ if face else None))
    return out


def face_track(ctx, c):
    """is face-aware framing asked for? shot camera key, else episode key, else the historical behaviour"""
    v = c.get('face_track')
    if v is None: v = (getattr(ctx, 'ep', None) or {}).get('camera_face_track')
    return cinema.FACE_TRACK_DEFAULT if v is None else bool(v)

CLEAR_FACE_DEFAULT = False      # episode "camera_clear_face" / shot camera "clear_face"; off = the historical framing
CLEAR_FACE_STEP = .4            # how often the arms are sampled over the shot, in seconds
CLEAR_FACE_MAX = 24             # ...and at most that many samples, so a long shot does not cost more than a short one
CLEAR_FACE_SHOTS = ('close', 'extreme_close', 'medium', 'medium_full', 'ots', 'dialogue')

def clear_face(ctx, c):
    """is the camera asked to keep the subject's own hands off his own face? shot key, else episode key, else no"""
    v = c.get('clear_face')
    if v is None: v = (getattr(ctx, 'ep', None) or {}).get('camera_clear_face')
    return CLEAR_FACE_DEFAULT if v is None else bool(v)

def arm_points(sm, aid, looks):
    """the two arm chains of one actor at one instant: (shoulder, elbow, mid-forearm, hand) in world coordinates.
    That is what can come between the lens and his face in a tight shot, and what cinema.arm_penalty measures.
    The cinematographer has probes for the set and for the other characters, none for the subject's own limbs;
    these points are exactly what it was missing. Animals have no readable face: skipped."""
    s = sm.get(aid)
    if s is None or looks.get(aid, {}).get('kind') in CR.ANIMALS: return ()
    sc_ = float(looks[aid].get('scale', 1.)) if aid in looks else 1.
    sk = bodies.solve(s['rig']); c, n = math.cos(s['heading']), math.sin(s['heading'])
    bx, by, bz = s['x'], s.get('y', 0.), s['z']
    bd = bodies.active()
    def w(j, off=0.):
        p = (sk.joints[j] + off) * sc_
        return (bx + float(p[0]) * c + float(p[2]) * n, by + float(p[1]), bz - float(p[0]) * n + float(p[2]) * c)
    out = []
    for tag in 'LR':
        # the refit slides the whole arm chain inwards; measure the arms the renderer really draws, not the ones
        # rig.py keeps (the shift is exactly the one bodies.shape applies to the three arm groups)
        off = bodies.arm_shift(bd, sk, 1 if tag == 'R' else -1)
        sh = w('sh' + tag, off); e = w('el' + tag, off); h = w('ha' + tag, off)
        out.append((sh, e, ((e[0] + h[0]) / 2, (e[1] + h[1]) / 2, (e[2] + h[2]) / 2), h))
    return tuple(out)

def _centroid(sa, ids, t, looks):
    sm = sa.sample(max(0., min(t, sa.dur))); pts = [(sm[a]['x'], sm[a]['z']) for a in ids if a in sm]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)) if pts else (0., 0.)

def interaction_points(sa, ids, end):
    """objects touched by the subjects during the shot: (point, heading of the actor at that moment)"""
    out = []
    for aid in ids:
        tr = sa.tracks.get(aid)
        if tr is None: continue
        for (r0, rc, r1, side, tgt) in tr.reaches:
            if tgt[0] == 'world': out.append((tgt[1], tr.heading_at(rc)))
            elif tgt[0] == 'door': out.append((sa.door_handle(tgt[1], rc), tr.heading_at(rc)))
    return out

def plan_camera(ctx, sa, c, st, looks):
    """camera for the whole shot, solved once: the subjects are taken over the duration of their action so that a
    static camera frames the whole movement; a follow camera gets a validated, smoothed path"""
    sm0 = sa.sample(0.)
    ids = c.get('on') or [a for a in sm0 if looks.get(a, {}).get('kind') not in CR.ANIMALS] or list(sm0)
    if isinstance(ids, str): ids = [ids]
    places = [a for a in ids if a not in sm0]                    # anchors / props / objects to keep in the frame
    ids = [a for a in ids if a in sm0]
    if not ids and places:                                       # what the characters look at (reveal): seen from their side
        pts = [p for p in (sa.world.anchor(nm) for nm in places) if p]
        if not pts: return None
        ax = sum(p[0] for p in pts) / len(pts); az = sum(p[1] for p in pts) / len(pts)
        peo = [(v['x'], v['z']) for v in sm0.values()] or [(ax, az - 3)]
        gx = sum(p[0] for p in peo) / len(peo); gz = sum(p[1] for p in peo) / len(peo)
        h = math.atan2(gx - ax, gz - az); sb = cam_boxes(st, sa)
        people = [cinema.Subject(a_, v['x'], v['z'], v['heading'], 1.62 + v.get('y', 0.), base=v.get('y', 0.)) for a_, v in sm0.items() if looks.get(a_, {}).get('kind') not in CR.ANIMALS]
        b0 = _blocked_fn(st, sa.world, sb); blk = lambda p_: b0(p_) or any(math.hypot(p_[0] - q.x, p_[2] - q.z) < .45 for q in people)
        sol = None
        if people:                        # what a character looks at: over his shoulder, the place in the frame
            near = min(people, key=lambda q: math.hypot(q.x - ax, q.z - az))
            sol = cinema.solve(dict(c, shot='ots', speaker='poi', size=c.get('size', 'full'), _fallback=True), [cinema.Subject('poi', ax, az, h, 1.25), near],
                               r3d.ASPECT, r3d.FOV_K, _probe_fn(st, None, sb), blk, ctx.cam_memory)
            if sol is not None and sol.get('shot') != 'ots': sol = None
        if sol is None:
            subj = [cinema.Subject('poi', p[0], p[1], h, 1.1, 2.2) for p in pts]
            sol = cinema.solve(dict(c, angle=c.get('angle', 'front')), subj, r3d.ASPECT, r3d.FOV_K, _probe_fn(st, None, sb), blk, ctx.cam_memory)
        return None if sol is None else dict(sol=sol, cam=c, ids=[], step=.1, score=sol.get('score', 1.))
    if not ids: return None
    fr = c.get('from')
    if fr is not None:                                           # the side of the set chosen by the director
        fp = sa.world.anchor(fr) if isinstance(fr, str) else (fr if isinstance(fr, (list, tuple)) and len(fr) == 2 else None)
        if fp:
            cx_, cz_ = _centroid(sa, ids, sa.dur * .5, looks); c = dict(c, _from_az=math.atan2(float(fp[0]) - cx_, float(fp[1]) - cz_))
    sb = cam_boxes(st, sa); probe, blocked0 = _probe_fn(st, None, sb), _blocked_fn(st, sa.world, sb)
    def blocked_at(t, r=.6):
        sm = sa.sample(t); oth = [(v['x'], v['z']) for a_, v in sm.items() if a_ not in ids]
        return lambda p: blocked0(p) or any(math.hypot(p[0] - ox, p[2] - oz) < r for ox, oz in oth)
    blocked = blocked_at(min(sa.dur, .5), .38 if c.get('shot') in ('ots', 'dialogue', 'close', 'extreme_close', 'medium') else 1.0)
    end = min(sa.dur, max([tr.cursor for tr in sa.tracks.values()] + [.5]))
    follow = c.get('move') == 'follow'
    times = [0.] if follow else sorted(set([0., end * .25, end * .5, end * .75, end, min(sa.dur, end + .5)]))
    cf = clear_face(ctx, c)
    # `clear_face` implies the face-aware model, and that is not a convenience: measured on demo6_continuite, the
    # arm term ALONE buys 21.5 % -> 14.0 % of forearm in the frame and then spends it on angles where the face is
    # not seen at all, because without a gaze the face term is silent and nothing holds the camera in front.
    # Dodging an arm is only worth doing towards the face. docs/P1_PROTOTYPE_VISUEL_20261024.md
    ft = face_track(ctx, c) or cf
    subj = []; gz = {}
    for t in times:
        ss = sa.sample(t); got = subjects_at(sa, ss, ids, looks, ft); subj += got
        for s_ in got:
            if s_.gaze is not None: gz.setdefault(s_.id, []).append(s_.gaze)
    last = subjects_at(sa, sa.sample(end), ids, looks, ft)
    for s_ in subj: s_.heading = next((l.heading for l in last if l.id == s_.id), s_.heading)
    moved = any(math.hypot(a.x - b.x, a.z - b.z) > .6 for a in subj for b in subj if a.id == b.id)
    if not moved: subj = list(last)
    elif len(ids) == 1 and moved and c.get('shot') in ('close', 'extreme_close', 'medium'): subj = list(last)
    for s_ in subj:                                   # the head turns while the shot plays: the camera is judged on
        v = gz.get(s_.id)                             # every sampled moment, not only on the last one
        if s_.gaze is None or not v: continue
        s_.gazes = tuple(v)
    if cf and len(ids) <= 2 and (c.get('shot') in CLEAR_FACE_SHOTS or not c.get('shot')):
        arm = {}
        # Over the WHOLE shot, not over `end`: `end` is where the written actions stop, while the gestures that
        # cause the defect are the ones the regie adds under the spoken line, often long after the last action.
        step = max(CLEAR_FACE_STEP, sa.dur / CLEAR_FACE_MAX)
        t_ = 0.
        while t_ <= sa.dur + 1e-6:
            ss = sa.sample(min(t_, sa.dur))
            for a_ in ids:
                pts = arm_points(ss, a_, looks)
                if pts: arm.setdefault(a_, []).append(pts)
            t_ += step
        for s_ in subj:
            if s_.id in arm: s_.arms = tuple(arm[s_.id])
    pois = interaction_points(sa, ids, end)
    for nm in places:
        p_ = sa.world.anchor(nm) or (sa.world.item(nm) and (sa.world.item(nm)[0], sa.world.item(nm)[2]))
        if p_: pois.append(((float(p_[0]), 1.0, float(p_[1])), 0.))
    if pois and c.get('shot') not in ('ots', 'pov', 'close', 'extreme_close') and not follow:   # show the hand and the object
        for (p_, h_) in pois: subj.append(cinema.Subject('poi', p_[0], p_[2], h_, max(.5, p_[1]), .3))
    smid = sa.sample(end * .5)
    oth = [capsule(v) for a_, v in smid.items() if looks.get(a_, {}).get('kind') not in CR.ANIMALS]     # subjects hide each other too
    if len(ids) == 1 and c.get('shot') in ('close', 'extreme_close', 'medium', 'medium_full') and not moved and c.get('from') is None:
        me = smid[ids[0]]; hm = me['heading'] + float(me['rig'].get('head', (0., 0.))[0])
        def faced(v):                                       # the person addressed: in front of the speaker's face, close
            dx, dz = v['x'] - me['x'], v['z'] - me['z']; L = math.hypot(dx, dz) + 1e-6
            return (dx * math.sin(hm) + dz * math.cos(hm)) / L - .15 * L
        ppl = [(faced(v), a_) for a_, v in smid.items() if a_ != ids[0] and looks.get(a_, {}).get('kind') not in CR.ANIMALS
               and math.hypot(v['x'] - me['x'], v['z'] - me['z']) < 3.2]
        if ppl:                                             # in a conversation: clean single from beside the person addressed
            pa = smid[max(ppl)[1]]; c = dict(c, _partner=cinema.Subject(max(ppl)[1], pa['x'], pa['z'], pa['heading'], 1.62))
    sol = cinema.solve(c, subj, r3d.ASPECT, r3d.FOV_K, _probe_fn(st, oth, sb) if c.get('shot') != 'ots' else probe, blocked, ctx.cam_memory)
    if sol is None: return None
    plan = dict(sol=sol, cam=c, ids=ids, step=.1)
    ts = np.arange(0., sa.dur + .2, .1)
    if follow:                        # a valid camera every second, smoothly chained (continuity of the side)
        vmax = 0.                     # V3: a sprint, a jump: keys twice as often, less lag (walking shots are unchanged)
        for t in np.arange(0., sa.dur, .25):
            for i_ in ids:
                p0 = sa.position(sa.tracks[i_], float(t)); p1 = sa.position(sa.tracks[i_], float(t) + .25)
                vmax = max(vmax, math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / .25)
        fast = vmax > 2.2; kstep = .5 if fast else 1.; lag = .06 if fast else .25
        keys = []; prev = None; kt = list(np.arange(0., sa.dur + 1e-3, kstep)) + [sa.dur]
        for t in kt:
            smp = sa.sample(float(t)); sj = subjects_at(sa, smp, ids, looks, ft)
            ck = dict(c, move='static'); ck.setdefault('shot', 'full'); ck.setdefault('angle', 1.0)     # tracking from three-quarter side
            if prev is not None: ck['_prefer_az'] = prev
            oth = [capsule(v) for a_, v in smp.items() if looks.get(a_, {}).get('kind') not in CR.ANIMALS]
            so = cinema.solve(ck, sj, r3d.ASPECT, r3d.FOV_K, _probe_fn(st, oth, sb), blocked_at(float(t), .95), ctx.cam_memory)
            if so is None: continue
            prev = so.get('az'); keys.append((float(t), np.array(so['pos'], np.float32), np.array(so['target'], np.float32), so['fov']))
        if keys:
            P_ = []; Tg = []
            for t in ts:
                j = max(0, min(len(keys) - 2, int(np.searchsorted([k_[0] for k_ in keys], t)) - 1)) if len(keys) > 1 else 0
                if len(keys) == 1: P_.append(keys[0][1]); Tg.append(keys[0][2]); continue
                a_, b_ = keys[j], keys[j + 1]; w_ = cinema.smooth((t - a_[0]) / max(1e-3, b_[0] - a_[0]))
                P_.append(a_[1] * (1 - w_) + b_[1] * w_)
                cen = _centroid(sa, ids, t - lag, looks)
                tg = a_[2] * (1 - w_) + b_[2] * w_; tg = np.array([cen[0] * .5 + tg[0] * .5, tg[1], cen[1] * .5 + tg[2] * .5], np.float32); Tg.append(tg)
            P_ = np.array(P_); Tg = np.array(Tg); k_ = np.ones(5) / 5
            for arr in (P_, Tg):
                for j in range(3):
                    pad = np.concatenate([np.full(2, arr[0, j]), arr[:, j], np.full(2, arr[-1, j])]); arr[:, j] = np.convolve(pad, k_, 'valid')
            plan['path'] = (ts, P_, Tg); plan['sol'] = dict(sol, fov=max(k_[3] for k_ in keys))
    elif moved and c.get('shot') in ('wide', 'full', 'medium_full', 'establishing', 'group', 'two_shot', None):
        c0 = np.array(sol['target'], np.float32); cen0 = _centroid(sa, ids, end * .5, looks); Tg = []
        cp = np.array(sol['pos'], np.float32); R0 = float(math.hypot(c0[0] - cp[0], c0[2] - cp[2])) or 1.
        for t in ts:
            acc = [_centroid(sa, ids, t - .6 * i / 4, looks) for i in range(5)]
            cx = sum(p[0] for p in acc) / 5; cz = sum(p[1] for p in acc) / 5
            g = c0 + np.array([(cx - cen0[0]) * .6, 0., (cz - cen0[1]) * .6], np.float32)
            dx, dz = float(g[0] - cp[0]), float(g[2] - cp[2]); L = math.hypot(dx, dz) or 1.      # a pan turns the camera, it does not tilt it
            Tg.append(np.array([cp[0] + dx / L * R0, c0[1], cp[2] + dz / L * R0], np.float32))
        plan['pan'] = (ts, np.array(Tg))
    mv = c.get('move')
    if mv in ('dolly_in', 'push', 'dolly_out', 'track', 'orbit', 'crane_up', 'crane_down') and plan.get('path') is None:
        amt = float(c.get('amount', .5)); heads = [(s_.x, s_.eye, s_.z) for s_ in subj if s_.id != 'poi'][:4]
        for _ in range(5):                            # the move must stay inside the set and keep the subjects visible
            cc = dict(c, amount=amt); ends = [cinema.apply_move(sol, cc, uu, 0.)[0] for uu in (0., .5, 1.)]
            if not any(blocked0(p_) for p_ in ends) and all(probe(ends[-1], h_) for h_ in heads): break
            amt *= .5
        else: amt = 0.
        plan['cam'] = dict(c, amount=amt) if amt > .03 else dict(c, move='static')
    plan['score'] = sol.get('score', 1.)
    return plan

def camera_acted(ctx, sa, shot, st, samp, looks, T, u, g, k):
    c = dict(shot.get('camera') or {})
    if c.get('rig') == 'path':                                             # caméra écrite en clés (acting/directed.py) : la même pour tous les styles
        from ...acting.directed import path_camera
        pos, tgt, fov, roll, shk = path_camera(c, samp, T)
        if c.get('pulse'):                                                 # clip musical : la caméra bat sur les temps (audio/music_cues.py)
            from ...audio.music_cues import camera_pulse
            fov, shk = camera_pulse(getattr(ctx, 'ep', None), c['pulse'], g, fov, shk)
        yaw, pitch = look_angles(pos, tgt)
        if shk:
            s_ = shake_offsets(T, shk); pos = (pos[0] + s_[0] * .1, pos[1] + s_[1] * .1, pos[2] + s_[2] * .05); yaw += s_[0] * .02; pitch += s_[1] * .02
        return (tuple(float(v) for v in pos), yaw, pitch, roll, float(fov)), None
    if c.get('preset') == 'free' and not c.get('shot'): return None
    if not c.get('shot') and c.get('preset') in PRESET_SHOT:              # original presets -> intentions
        c['shot'] = PRESET_SHOT[c['preset']]
        if c.get('subject'): c.setdefault('on', [c['subject']])
    if not c.get('shot'):
        ids = list(samp.keys()); people = [a for a in ids if looks.get(a, {}).get('kind') not in CR.ANIMALS] or ids
        speaking = [a for a in people if samp[a]['talking']]
        moving = [a for a in people if samp[a]['rig'].get('gait', 0) > .5]
        prev = ctx.ep['shots'][k - 1] if k > 0 else None
        first = prev is None or prev.get('set', ctx.ep.get('default_set')) != shot.get('set', ctx.ep.get('default_set'))
        c.update(cinema.auto_camera(shot, people, speaking, moving, first, samp[people[0]]['face'] if people else None, r3d.ASPECT))
    key = (k, r3d.RW)
    if key not in ctx.cam_cache: ctx.cam_cache[key] = plan_camera(ctx, sa, c, st, looks)
    plan = ctx.cam_cache[key]
    if plan is None: return None
    sol, c, ids = plan['sol'], plan['cam'], plan['ids']
    delta = (0., 0.)
    if plan.get('path') is not None:                    # follow: precomputed, validated camera path
        ts, P_, Tg = plan['path']; f = min(max(T / plan['step'], 0.), len(ts) - 1.001); i = int(f); w_ = f - i
        pos = tuple(float(P_[i][j] * (1 - w_) + P_[i + 1][j] * w_) for j in range(3)); tgt = tuple(float(Tg[i][j] * (1 - w_) + Tg[i + 1][j] * w_) for j in range(3))
        sol = dict(sol, pos=pos, target=tgt); c = dict(c, move='static')
    elif plan.get('pan') is not None:                   # static camera panning with the action
        ts, Tg = plan['pan']; f = min(max(T / plan['step'], 0.), len(ts) - 1.001); i = int(f); w_ = f - i
        sol = dict(sol, target=tuple(float(Tg[i][j] * (1 - w_) + Tg[i + 1][j] * w_) for j in range(3)))
    if c.get('shot') == 'pov':
        s = samp.get(ids[0]) if ids else None
        if s:
            hy, hp = s['rig'].get('head', (0., 0.)); h = s['heading'] + hy
            eye = 1.62 - .36 * rig.smooth(s['rig'].get('sit', 0.)) + s.get('y', 0.)
            pos = (s['x'] + math.sin(h) * .12, eye, s['z'] + math.cos(h) * .12)
            tgt = (pos[0] + math.sin(h) * 4, eye - .25 + 4 * math.tan(hp), pos[2] + math.cos(h) * 4)
            sol = dict(sol, pos=pos, target=tgt)
    pos, tgt = cinema.apply_move(sol, c, u, T)
    yaw, pitch = look_angles(pos, tgt)
    roll = float(c.get('roll', 0.)) * math.pi / 180
    shk = float(val(c.get('shake'), u, 0.) or 0.)
    if shk:
        s_ = shake_offsets(T, shk); pos = (pos[0] + s_[0] * .1, pos[1] + s_[1] * .1, pos[2] + s_[2] * .05); yaw += s_[0] * .02; pitch += s_[1] * .02
    return (tuple(float(v) for v in pos), yaw, pitch, roll, float(sol['fov'])), (ids[0] if c.get('shot') == 'pov' and ids else None)

def _windows(st):
    sp = getattr(st, 'spec', {}) or {}; out = []
    for r in sp.get('rooms', []) or []:
        for wn in r.get('windows', []) or []: out.append(st._wall_point(r, wn.get('wall', 'N'), wn.get('pos', .5), inset=.5))
    if not out:
        a = list(st.anchors.values()) or [(0, 0)]; out.append((sum(p[0] for p in a) / len(a), sum(p[1] for p in a) / len(a)))
    return out

def build_acted(ctx, sa, shot, st, state, g, T, u, k):
    samp = sa.sample(T)
    for aid, (dx, dy, dz) in FX.carry_offsets(shot, T, sa).items():          # riding a mover (a helicopter, a cart): carried along
        if aid in samp: samp[aid] = dict(samp[aid], x=samp[aid]['x'] + dx, y=samp[aid].get('y', 0.) + dy, z=samp[aid]['z'] + dz)
    looks = {aid: resolve_look(ctx, aid) for aid in samp}
    samp = COS.add_spin(sa, samp, looks, T)               # costumes: spin rate for the skirt flare (the very same dict when nobody wears one)
    res = camera_acted(ctx, sa, shot, st, samp, looks, T, u, g, k)
    if res is None:                                       # free camera keys: original evaluator with pseudo actors
        actors = {aid: dict(spec={'id': aid, 'facing': '+z' if math.cos(s['heading']) > 0 else '-z'}, look=looks[aid], x=s['x'], z=s['z'],
                            swing=0., scale=float(looks[aid].get('scale', 1.)), yoff=0., moving=False) for aid, s in samp.items()}
        cam, pov_id = eval_camera(ctx, shot, st, actors, T, u, g)
    else:
        cam, pov_id = res
    sc = st.scene(state, g, u)
    world = sa.world
    # doors moved by the characters replace the closed door of the set
    gone = set(); extra = []
    for did, dr in world.doors.items():
        if did in sa.doors:
            gone.add(dr['box']); extra += world.door_boxes(did, sa.door_angle(did, T))
    boxes = [b for i, b in enumerate(sc.boxes) if i not in gone] + extra
    # loose objects (not in a hand)
    olights = []
    for name, it in world.items().items():
        own = sa.item_owner(name, T)
        if own is None: boxes += world.item_boxes(name, None, olights)
        elif isinstance(own, tuple) and own[0] == 'at': boxes += world.item_boxes(name, own[1], olights)
    # characters
    alights = []; env = ctx.mouth(g)
    for aid, s in samp.items():
        if not s['visible'] or aid == pov_id: continue
        look = looks[aid]; spec = sa.spec_actors.get(aid, {})
        kflags = dict(hidden=bool(spec.get('reflection_only')), noref=bool(spec.get('no_reflection')), dissolve=max(float(s.get('dissolve', 0.) or 0.), float(val(spec.get('dissolve'), u, 0.) or 0.)))
        if look.get('kind') == 'faceless':                    # l'homme sans visage du premier moteur (faceless.py)
            from . import faceless as FL
            hd = s['heading']; dd = '+z' if abs(hd) < math.pi / 4 else ('-z' if abs(hd) > 3 * math.pi / 4 else ('+x' if hd > 0 else '-x')); xp = s.get('xp') or {}
            boxes += FL.faceless(s['x'], s['z'], dd, phase=s['rig'].get('phase', 0.) / (2 * math.pi), run=min(1., float(s['rig'].get('gait', 0.)) * (.4 + .6 * float(s['rig'].get('run', 0.)))),
                                 tilt=xp.get('tilt', 0.), recoil=xp.get('recoil', 0.), reach=xp.get('reach', 0.), hunch=xp.get('hunch', 0.), pitch=xp.get('pitch', 0.), palm=xp.get('palm'),
                                 dissolve=kflags['dissolve'], scale=float(look.get('scale', 1.12)))
            continue
        if look.get('kind') in CR.ANIMALS:
            p = s['rig']; sw = .32 * math.sin(p.get('phase', 0.)) * p.get('gait', 0.)
            ab = CR.animal(look['kind'], look.get('color'), sw, g, kflags, spec.get('posture'), float(look.get('size', look.get('scale', 1.))))
            boxes += orient(ab, s['heading'], (s['x'], s.get('y', 0.), s['z'])); continue
        hold = s.get('hold')
        if hold in world.items(): s = dict(s, hold=world.items()[hold].get('type', hold))
        if look.get('kind') == 'creature' and s.get('face', 'neutral') == 'neutral': s = dict(s, face='creature')
        if look.get('costume') and COS.wants(look):          # 18th-century costume (opt-in cast key `costume`, costumes.py)
            face = COS.face_for(look, s, env if s['talking'] else 0.)           # the painted pixel head (face_skin) or the engine's face
            bx, sk = COS.build(s, look, face, kflags, spec, alights)
        else:
            face = rigfig.face_for(look, s, env if s['talking'] else 0.)
            bx, sk = rigfig.build(s, look, face, kflags, spec, alights)
        boxes += bx
        if look.get('kind') == 'creature' or spec.get('red_glow'):
            alights.append(((s['x'], 1.1, s['z'] + 1.1 * math.cos(s['heading'])), (1, .12, .08), .45, 1.4))
    actors = {aid: dict(spec={'id': aid}, look=looks[aid], x=s['x'], z=s['z'], scale=float(looks[aid].get('scale', 1.)), yoff=0., heading=s['heading'])
              for aid, s in samp.items()}
    obx, olt = eval_objects(ctx, shot, st, actors, cam, T, u, g)
    sc.boxes = without_hidden(ctx, boxes) + obx
    if shot.get('fog') is not None: sc.fogk = float(shot['fog'])
    for (l0, ld, mode) in getattr(sa, 'lights', []):         # light events of the shot (flicker, off, dark)
        if l0 <= T <= l0 + ld: state = dict(state, lights=mode)
    Ls = st.lights(state, g, u, cam[0])
    for tl in getattr(sa, 'lightning', []):                  # lightning through the windows (double flash)
        dt = T - tl
        if 0 <= dt < .9:
            k = math.exp(-dt * 9) + .7 * math.exp(-max(0., dt - .22) * 12) * (dt > .22)
            for wp in _windows(st): Ls.append(((wp[0], 1.8, wp[1]), (.72, .8, 1.0), 7. * k, 9.))
    if Ls and samp:                                       # the camera fill light must not burn faces in close-ups
        cp = cam[0]; d, near = min((math.hypot(s['x'] - cp[0], s['z'] - cp[2]), a_) for a_, s in samp.items())
        outdoor = bool((getattr(st, 'spec', {}) or {}).get('outdoor'))
        p_, c_, pw, r_ = Ls[-1][:4]
        sn = samp[near]; hx, hz = sn['x'], sn['z']                   # a face already lit by the set needs less fill (no burnt skin)
        fh = sn['heading'] + float(sn['rig'].get('head', (0., 0.))[0]); fx_, fz_ = math.sin(fh), math.cos(fh); key = 0.
        for l in Ls[:-1]:                                            # only the lights in front of the face count (Lambert)
            if l[3] >= 50: continue
            vx, vy, vz = l[0][0] - hx, l[0][1] - 1.4, l[0][2] - hz; dd = math.sqrt(vx * vx + vy * vy + vz * vz) + 1e-6
            key += l[2] / (1 + dd * dd / (l[3] * l[3])) * max(0., (vx * fx_ + vz * fz_) / dd)
        nominal = pw / (1 + (d / r_) ** 2)                           # fill received by the face, then completed up to a readable face
        m = min(1.6 if d < 1.6 else 1., max(.25, (.6 - key) / max(nominal, 1e-3)))
        Ls[-1] = (p_, c_, pw * m, r_)
    L = Ls + alights + olt + olights
    for l in (shot.get('lights') or []):
        p_ = anchor_xyz(st, l.get('at'), actors, float(l.get('y', 2.0)))
        L.append((p_, tuple(l.get('color', (1, .9, .75))), float(val(l.get('power'), u, 1.0)), float(l.get('radius', 2.5))))
    if hasattr(st, 'stage_frame'):            # lumière de scène d'un théâtre (theatre.py, clé `stage_light`) : seul ce lieu a la méthode
        L = st.stage_frame(ctx, k, shot, {a: (s['x'], s.get('y', 0.), s['z']) for a, s in samp.items() if s['visible']}, cam, sc, L, len(Ls), T, u, g, state)
    L, lx = LT.plan(ctx, shot, st, actors, cam, sc, L, len(Ls), T, u, g)     # V3: narrative lighting intention (opt-in)
    L = [l for l in L if l[2] > 1e-3]
    return sc, cam, with_shadows(L, cam[0]) + [l for l in lx if l[2] > 1e-3], shot, T, u, k, state
