"""Human faces for the voxel painter: what the first engine did well (a gaze that goes somewhere, blinks that mean something, brows that carry tension,
micro-expressions, emotions with a duration and a cause) ported onto engine A's parametric face (engine/face4.js), as DATA the painter only plays.

The painter used to receive ONE name per frame (`expr`), blended over 0.2 s, plus a random blink and a random saccade: the same smile-or-fear preset for as long
as the name held, eyes that wandered by themselves, no relation between what a character looks at and what it feels. This module computes, per character and per
frame (deterministic, no clock, no randomness beyond a hash of the time slot):

  * eyes     aimed at the thing the story makes the character look at (`look` beats of blocking.py): the head turns first (blocking.py, speed limited), the eyes take
             the residual with a BALLISTIC saccade (duration 21 ms + 2.2 ms/deg, the main sequence the first engine used in acting/eyeflow.py) then smooth pursuit,
             with micro-saccades while fixating and a short downward avoidance glance when afraid;
  * lids     blinks whose rate follows the tension (a frightened person stares, then blinks twice after a shock), a startle blink 50 ms after a cause, closure shape
             asymmetric (fast down, slow up), lids narrowing with `determined` / `worried` through the preset;
  * brows    pulled by the tonic emotion and flicked by micro-expressions (a 0.2 s brow flash at a cause, even when the face then stays neutral);
  * mouth    tension (lips pressed, corners down) and open during an inhale after a shock;
  * emotion  two layers. TONIC: the state the character is in (`emote` beats), cross-faded over 0.45 s. PHASIC: reactions to a CAUSE (`react` beats) that start
             after a human reaction latency (0.18 s), peak, hold and decay (attack, hold, decay), each carrying the thing that provoked it, so the face of a character
             who hears a bang changes AFTER the bang and looks towards where it came from.

Output: columns FACE_COLS per frame; `e1`/`e2` index the contract's `expressions`, `i1`/`i2` their intensities (the painter adds i * (preset - neutral) to the neutral face).
"""
import math

FACE_COLS = ['lx', 'ly', 'blink', 'bdi', 'bdo', 'mo', 'ms', 'tilt', 'e1', 'i1', 'e2', 'i2']
HZ = 120.
LAT = .18                       # human reaction latency to an event (s)


def _h(n):
    s = math.sin(n * 127.1 + 311.7) * 43758.5453; return s - math.floor(s)


def _sm(k): k = max(0., min(1., k)); return k * k * (3 - 2 * k)


def _wrap(a): return (a + math.pi) % (2 * math.pi) - math.pi


def _deg(r): return abs(r) * 57.2958


def build(C, aid, face_map, expressions, duration):
    """-> list of rows (one per 1/120 s) for the actor `aid` of the compiled blocking C; `face_map` = director.EXPR_MAP.
    Default: the layer that shipped with the continuity film, unchanged. `plan['face'] = {'model': 'human'}` (or the actor's `face_model`) switches to the human model below."""
    model = (C.actors[aid].spec.get('face_model') or (C.plan.get('face') or {}).get('model') or 'legacy')
    if model == 'human': return _build_human(C, aid, face_map, expressions, duration)
    if model != 'legacy': raise ValueError(f"modèle de visage inconnu : {model!r} (legacy | human)")
    return _build_legacy(C, aid, face_map, expressions, duration)


def _build_legacy(C, aid, face_map, expressions, duration):
    """-> list of rows (one per 1/120 s) for the actor `aid` of the compiled blocking C; `face_map` = director.EXPR_MAP"""
    A = C.actors[aid]; n = int(duration * HZ) + 4; ex = {nm: i for i, nm in enumerate(expressions)}
    nm = lambda f: face_map.get(f, f) if face_map.get(f, f) in ex else 'neutral'
    # --- tonic emotion: (t, preset, intensity) crossfaded over .45 s
    ton = [(-1e9, 'neutral', 1.)] + [(t, nm(f), float(i)) for (t, f, i) in getattr(A, 'tonic', [(t_, f_, 1.) for (t_, f_) in A.faces_expr])]
    # --- phasic reactions: (onset, preset, peak, attack, hold, decay, look target or None)
    rea = [(a, nm(b), c, d_, e, f, g) for (a, b, c, d_, e, f, g) in getattr(A, 'reactions', [])]
    ts = [(k / HZ) for k in range(n)]
    rows = []; eye_y = eye_p = 0.; sacc = None; last_tgt = None; blink_t0 = -9.; next_blink = 1.2 + _h(1.) * 2.
    for k, t in enumerate(ts):
        # tonic cross-fade
        j = max(i for i, e in enumerate(ton) if e[0] <= t)
        cur = ton[j]; w = _sm((t - cur[0]) / .45) if j else 1.
        e_w = {cur[1]: cur[2] * w}
        if j: e_w[ton[j - 1][1]] = e_w.get(ton[j - 1][1], 0.) + ton[j - 1][2] * (1 - w)
        # phasic
        brow = 0.; inhale = 0.; startle_t = None
        for (t0, pre, peak, att, hold, dec, tgt) in rea:
            u = t - t0
            if u < 0 or u > att + hold + dec + .1: continue
            v = peak * (_sm(u / att) if u < att else 1. if u < att + hold else 1. - _sm((u - att - hold) / dec))
            e_w[pre] = max(e_w.get(pre, 0.), v)
            brow = max(brow, v * (1. if u < att + hold + .25 else 0.) * (_sm(u / .06) * (1. - _sm((u - .2) / .25))))      # the brow flash: up fast, back in 0.45 s
            inhale = max(inhale, v if u < att + hold else 0.)
            if 0 <= u < .35: startle_t = t0
        tens = 0.
        for e in C.events:
            if e['who'] == aid and e['kind'] == 'tension' and e['t'] <= t < e['until']: tens = e.get('value', .6)
        top = sorted(e_w.items(), key=lambda kv: -kv[1])[:2]
        (e1, i1) = top[0] if top else ('neutral', 0.); (e2, i2) = top[1] if len(top) > 1 else ('neutral', 0.)
        # --- eyes: where the character is looking, minus what the head already delivers
        row = C._row(A, t); yaw, hy, hp = row['heading'], row['rig']['head'][0], row['rig']['head'][1]
        tgt = _gaze_target(C, A, t)
        if tgt is None: want_y = want_p = 0.
        else:
            dx, dz = tgt[0] - row['x'], tgt[1] - row['z']; bear = math.atan2(dx, dz); dist = max(.4, math.hypot(dx, dz))
            want_y = max(-.6, min(.6, _wrap(bear - yaw - hy))); want_p = max(-.35, min(.35, -(math.atan2(tgt[2] - 1.85, dist) + hp)))
        key = None if tgt is None else (round(tgt[0], 1), round(tgt[1], 1))
        if key != last_tgt and last_tgt is not None and abs(want_y - eye_y) > .05:
            sacc = (t, eye_y, want_y); last_tgt = key
        elif last_tgt is None: last_tgt = key
        if sacc is not None:
            dur = .021 + .0022 * _deg(sacc[2] - sacc[1]); u = (t - sacc[0]) / max(.02, dur)
            if u >= 1.: sacc = None; eye_y = want_y
            else: eye_y = sacc[1] + (sacc[2] - sacc[1]) * _sm(u)
        else: eye_y += (want_y - eye_y) * min(1., 9. / HZ)                                  # smooth pursuit, a little lagging
        eye_p += (want_p - eye_p) * min(1., 7. / HZ)
        # micro-saccades while fixating (a fresh tiny offset each .35-.9 s), and a downward avoidance glance when afraid
        slot = int(t / .45); ms_x = (_h(slot * 1.7 + 3.) - .5) * .09; ms_y = (_h(slot * 2.3 + 9.) - .5) * .06
        avoid = 0.
        if tens > .5 and _h(int(t / 2.7) * 3.1 + 5.) > .72 and (t % 2.7) < .5: avoid = .55
        lx = max(-1., min(1., eye_y / .55 + ms_x)); ly = max(-1., min(1., eye_p / .35 + ms_y + avoid))
        # --- lids: blinks. A frightened, fixating person blinks rarely; a shock gives a quick double blink
        period = 3.0 + 2.6 * min(1., tens)               # a frightened person fixates and blinks rarely
        if t >= next_blink and t - blink_t0 > .3:
            blink_t0 = t; next_blink = t + period * (.6 + .8 * _h(int(t * 3) + 7.))
        if startle_t is not None and (t - startle_t) % 1.0 < 0.0: pass
        b = 0.; u = t - blink_t0
        if 0 <= u < .17: b = _sm(u / .06) if u < .06 else 1. - _sm((u - .06) / .11)
        for (t0, pre, peak, att, hold, dec, tg) in rea:
            for off in (LAT * 0 + .05, .38):                                               # a startle blink 50 ms after the onset, a second one 0.38 s later
                uu = t - (t0 + off)
                if peak > .5 and 0 <= uu < .17: b = max(b, _sm(uu / .06) if uu < .06 else 1. - _sm((uu - .06) / .11))
        # --- brows / mouth from tension and micro-expression
        bdi = -3.2 * brow + 1.0 * tens; bdo = -1.4 * brow - .4 * tens
        mo = .22 * inhale; ms = -.25 * tens * (1. - brow); tilt = .12 * tens
        rows.append([round(v, 4) for v in (lx, ly, b, bdi, bdo, mo, ms, tilt, ex[e1], i1, ex[e2], i2)])
    return rows


def _gaze_target(C, A, t):
    from .blocking import _look_target
    cur = None
    for lk in A.looks:
        if lk[0] <= t: cur = lk
        else: break
    if cur is None or cur[1][0] == 'clear': return None
    r = _look_target(C, cur[1], t)
    return None if r is None else (r[0], r[1], r[2])


# ------------------------------------------------------------------------------------------------------------------------- the human model (opt-in)
# What the first engine knew about a face and the legacy layer above did not use. Sources: engines/console/expression.py (blink rate and speed per emotion, persona
# expressive / energy / shy, gaze bias), engines/pixel3d/eyes.py + acting/eyeflow.py (ballistic saccade, pursuit), acting/timeline.py (reaction table), pixel3d/frame.py
# (the mouth follows the voice envelope). Everything below is derived from the CAUSES in the plan (emote / react / tension / talk beats and the events the story makes);
# nothing moves for its own sake, and an expression change without a cause is something audit_faces() reports.
BLINK_RATE = {'neutral': 1., 'worried': 1.3, 'scared': .55, 'scaredL': .55, 'scaredR': .55, 'scream': .4, 'shout': .6, 'grit': .6, 'determined': .7, 'smile': 1., 'relief': 1.4,
              'sad': 1.3, 'cry': 1.7, 'surprised': .5, 'blink': 1., 'lookL': 1., 'lookR': 1.}
BLINK_SLOW = {'sad': 1.4, 'cry': 1.3, 'relief': 1.3, 'worried': 1.1}
FADE_IN = {'scared': .25, 'scaredL': .25, 'scaredR': .25, 'scream': .2, 'surprised': .18, 'shout': .25, 'grit': .3, 'determined': .4, 'worried': .45, 'smile': .5,
           'relief': .8, 'sad': .8, 'cry': .7, 'neutral': .6}
MOUTH_GAIN = {'scared': .85, 'scaredL': .85, 'scaredR': .85, 'scream': 1.3, 'shout': 1.25, 'grit': .6, 'smile': 1., 'sad': .8, 'cry': .9, 'determined': .8, 'worried': .9, 'relief': .9}


def _clamp(x, a=0., b=1.): return a if x < a else b if x > b else x


def _blink_shape(u, slow=1.):
    """0 open .. 1 closed: fast close (60 ms), short hold (30 ms), slower opening (130 ms); `slow` stretches it (a tired or sad face)"""
    c, h, o = .06 * slow, .03, .13 * slow
    if u < 0 or u > c + h + o: return 0.
    return _sm(u / c) if u < c else 1. if u < c + h else 1. - _sm((u - c - h) / o)


def _weighted(e_w, table, default=1.):
    tot = sum(e_w.values()) or 1.
    return sum(w * table.get(k, default) for k, w in e_w.items()) / tot


def _build_human(C, aid, face_map, expressions, duration):
    from . import lipsync
    A = C.actors[aid]; n = int(duration * HZ) + 4; ex = {nm_: i for i, nm_ in enumerate(expressions)}
    nm = lambda f: face_map.get(f, f) if face_map.get(f, f) in ex else 'neutral'
    pers = dict(expressive=.6, energy=.5, shy=0.); pers.update(A.persona)
    amp = _clamp(float(pers['expressive']) * 1.25 + .25, .25, 1.6); energy = _clamp(float(pers['energy'])); shy = _clamp(float(pers['shy'])); spd = .75 + .55 * energy
    ton = [(-1e9, 'neutral', 1.)] + [(t, nm(f), min(1.3, float(i) * amp)) for (t, f, i) in getattr(A, 'tonic', [(t_, f_, 1.) for (t_, f_) in A.faces_expr])]
    rea = [(a, nm(b), min(1.2, c * amp), d_, e, f, g) for (a, b, c, d_, e, f, g) in getattr(A, 'reactions', [])]
    meta = getattr(A, 'react_meta', [{}] * len(rea))
    lip = lipsync.track_for(A, duration); talks = list(A.talk); arr = C.arr[aid]; N = len(arr['x'])
    tail_blinks = [b + .08 for (a, b) in talks if _h(a * 3.3 + 1.) > .35]
    rows = []; eye_y = eye_p = 0.; sacc = None; last_key = None; blinks = []; last_blink = -9.; next_blink = 1.0 + _h(1. + len(aid)) * 2.2 / spd; used_tail = set(); wander = (0., 0.); wander_i = -1
    for k in range(n):
        t = k / HZ; i = min(k, N - 1)
        # --- tonic emotion, cross-faded at the speed of the emotion it goes to
        j = max(ii for ii, e in enumerate(ton) if e[0] <= t)
        cur = ton[j]; w = _sm((t - cur[0]) / FADE_IN.get(cur[1], .45)) if j else 1.
        e_w = {cur[1]: cur[2] * w}
        if j: e_w[ton[j - 1][1]] = e_w.get(ton[j - 1][1], 0.) + ton[j - 1][2] * (1 - w)
        # --- phasic reactions with a cause: the upper face (brows, lids) answers first, the lower face (the inhale) 80 ms later
        brow = 0.; inhale = 0.; staring = False
        for ri, (t0, pre, peak, att, hold, dec, tgt_) in enumerate(rea):
            u = t - t0
            if u < 0 or u > att + hold + dec + .2: continue
            v = peak * (_sm(u / att) if u < att else 1. if u < att + hold else 1. - _sm((u - att - hold) / dec))
            e_w[pre] = max(e_w.get(pre, 0.), v)
            brow = max(brow, v * (_sm(u / .06) * (1. - _sm((u - .2) / .25))))
            ui = u - .08
            if 0 <= ui < att + hold: inhale = max(inhale, peak * _sm(ui / max(.05, att)))
            if u < att + hold * .7 and peak > .45: staring = True
        tens = 0.
        for e in C.events:
            if e['who'] == aid and e['kind'] == 'tension' and e['t'] <= t < e['until']: tens = e.get('value', .6)
        top = sorted(e_w.items(), key=lambda kv: -kv[1])[:2]
        (e1, i1) = top[0] if top else ('neutral', 0.); (e2, i2) = top[1] if len(top) > 1 else ('neutral', 0.)
        # --- speech
        sp_open = pressed = emph = 0.
        if lip is not None and any(a - .2 <= t <= b + .2 for a, b in talks): sp_open, pressed, emph = lip.at(t)
        speaking = any(a <= t <= b for a, b in talks)
        # --- eyes: where the character is looking, minus what the head already delivers
        yaw, hy, hp = arr['yaw'][i], arr['hyaw'][i], arr['hpit'][i]; x, z = arr['x'][i], arr['z'][i]
        tgt = _gaze_target(C, A, t)
        if tgt is None:                                         # nothing to look at: the eyes settle on a fixation, then move to another one now and then
            wi = int(t * (.45 + .45 * energy) + _h(len(aid)) * 5)
            if wi != wander_i:
                wander_i = wi; calm = 1. - .6 * tens
                wander = ((_h(wi * 1.9 + 4.) - .5) * .5 * calm, ((_h(wi * 2.7 + 8.) - .5) * .22 + .08 * shy) * calm)
            want_y, want_p = wander; key = ('w', wander_i)
        else:
            dx, dz = tgt[0] - x, tgt[1] - z; bear = math.atan2(dx, dz); dist = max(.4, math.hypot(dx, dz))
            want_y = max(-.6, min(.6, _wrap(bear - yaw - hy))); want_p = max(-.35, min(.35, -(math.atan2(tgt[2] - 1.85, dist) + hp))); key = (round(tgt[0], 1), round(tgt[1], 1))
            want_p += .14 * shy; want_y += .08 * shy * (1. if _h(len(aid) * 1.3) > .5 else -1.)           # a shy face drops its eyes and slips them aside
            for (a, b) in talks:                                                                             # a speaker looks away a moment as he starts a thought, then comes back
                if a <= t < a + .9 and _h(a * 7.3 + len(aid)) > .45:
                    u = (t - a) / .9; bump = math.sin(math.pi * u) ** 2; sgn = 1. if _h(a * 5.1) > .5 else -1.
                    want_y += sgn * .28 * bump; want_p += (-.1 if _h(a * 2.2) > .5 else .12) * bump
        if key != last_key and last_key is not None and abs(want_y - eye_y) > .05:
            sacc = (t, eye_y, want_y); last_key = key
            if abs(want_y - eye_y) > .25 and t - last_blink > .8 and _h(k * .37 + 11.) > .4:           # a large gaze shift is accompanied by a blink
                blinks.append((t + .03, BLINK_SLOW.get(e1, 1.))); last_blink = t + .03
        elif last_key is None: last_key = key
        if sacc is not None:
            dur = .021 + .0022 * _deg(sacc[2] - sacc[1]); u = (t - sacc[0]) / max(.02, dur)
            if u >= 1.: eye_y = sacc[2]; sacc = None                                   # the saccade lands where it was aimed; pursuit takes over from there (legacy snapped to the NEW target here)
            else: eye_y = sacc[1] + (sacc[2] - sacc[1]) * _sm(u)
        else: eye_y += (want_y - eye_y) * min(1., 9. / HZ)
        eye_p += (want_p - eye_p) * min(1., 7. / HZ)
        slot = int(t / .45); ms_x = (_h(slot * 1.7 + 3.) - .5) * .09; ms_y = (_h(slot * 2.3 + 9.) - .5) * .06
        avoid = .55 if (tens > .5 and _h(int(t / 2.7) * 3.1 + 5.) > .72 and (t % 2.7) < .5) else 0.
        lx = max(-1., min(1., eye_y / .55 + ms_x)); ly = max(-1., min(1., eye_p / .35 + ms_y + avoid))
        # --- lids: the rate follows the emotion and the tension; a stare is not interrupted; the lid follows a downward gaze; blinks have causes
        rate = _weighted(e_w, BLINK_RATE) * (1. - .45 * min(1., tens)) * spd
        if t >= next_blink and t - last_blink > .3:
            if staring: next_blink = t + .25
            else:
                blinks.append((t, _weighted(e_w, BLINK_SLOW))); last_blink = t
                if _h(int(t * 5) + 3.) > .86: blinks.append((t + .3, 1.))                                    # the odd double blink
                next_blink = t + (3.4 / max(.2, rate)) * (.6 + .8 * _h(int(t * 3) + 7.))
        for ti, tb in enumerate(tail_blinks):
            if ti not in used_tail and t >= tb: used_tail.add(ti); blinks.append((tb, 1.)); last_blink = tb          # the end of a sentence
        for ri, (t0, pre, peak, att, hold, dec, tg) in enumerate(rea):
            m = meta[ri] if ri < len(meta) else {}
            if m.get('startle', peak > .5) and peak > .45:
                for off in ((.05, .38) if peak > .7 else (.05,)):
                    tb = t0 + off
                    if t >= tb and t - tb < 1. / HZ + 1e-9: blinks.append((tb, 1.)); last_blink = max(last_blink, tb)
        blinks = [bk for bk in blinks if t - bk[0] < .6]
        b = 0.
        for (tb, sl) in blinks: b = max(b, _blink_shape(t - tb, sl))
        b = max(b, .22 * max(0., ly - .1))
        # --- brows: the tonic expression carries them; here only what has a cause: the flash at a stimulus, effort under tension, a stressed beginning of speech
        em = emph if energy > .35 else 0.
        bdi = (-3.2 * brow + 1.0 * tens - .9 * em) * min(1.3, amp); bdo = (-1.4 * brow - .4 * tens - .5 * em) * min(1.3, amp)
        # --- mouth: the voice opens it, silence and bilabials close it, the inhale of a shock opens it a little, a frightened person breathes
        gain = _weighted(e_w, MOUTH_GAIN)
        mo = .55 * gain * sp_open + .22 * inhale
        if not speaking and tens > .6: mo += .05 * tens * (.5 + .5 * math.sin(2 * math.pi * .85 * t))
        ms = -.25 * tens * (1. - brow) - .12 * pressed; tilt = .12 * tens
        rows.append([round(v, 4) for v in (lx, ly, b, bdi, bdo, mo, ms, tilt, ex[e1], i1, ex[e2], i2)])
    return rows


# ------------------------------------------------------------------------------------------------------------------------- plan -> tonic / phasic lists
def attach(plan_beats, C):
    """turn the `emote` / `react` beats of a plan into the `tonic` / `reactions` lists of each actor (called by blocking.compile_plan). A `react` carries optionally
    the `cause` that provoked it (an event type of eventreact.py), `startle` (blink + inhale), `audibility`: kept in `A.react_meta`, parallel to `A.reactions`."""
    pairs = {}
    for b in plan_beats:
        A = C.actors[b['who']]
        if not hasattr(A, 'tonic'): A.tonic = []; A.reactions = []; A.react_meta = []
        pairs.setdefault(b['who'], [])
        if b['do'] == 'emote': A.tonic.append((float(b['t']), b['face'], float(b.get('i', 1.))))
        elif b['do'] == 'react':
            t0 = float(b['t']) + float(b.get('latency', LAT)); tgt = b.get('look')
            tup = (t0, b['face'], float(b.get('i', .9)), float(b.get('attack', .12)), float(b.get('hold', .5)), float(b.get('decay', 1.2)), tgt)
            meta = {k: b[k] for k in ('cause', 'startle', 'audibility', 'seen') if k in b}; meta['onset'] = t0
            pairs[b['who']].append((tup, meta))
    for aid, A in C.actors.items():
        if hasattr(A, 'tonic'):
            A.tonic.sort(key=lambda e: e[0]); ps = sorted(pairs.get(aid, []), key=lambda p: p[0][0])
            A.reactions = [p[0] for p in ps]; A.react_meta = [p[1] for p in ps]


# ------------------------------------------------------------------------------------------------------------------------- the data, for the painter and for the checks
def build_all(C, face_map, expressions, duration, skip=()):
    """-> {actor: rows} for every actor that has a face (the faceless are skipped by the director; `skip` names more). The rows are FACE_COLS at HZ: exactly what
    `director.build` stores in `stage['faces']` and `film_unified.js` plays."""
    return {a: build(C, a, face_map, expressions, duration) for a, A in C.actors.items() if A.kind != 'faceless' and a not in skip}


def semantic(C, aid, rows, expressions):
    """the face of one actor read back as events a human can check: blink instants, gaze shifts, reactions with their causes, the talk windows, how the mouth is driven.
    Everything is measured on the ROWS the painter will play, not on the intentions."""
    ix = {c: i for i, c in enumerate(FACE_COLS)}; A = C.actors[aid]; blinks = []; sacc = []; was = 0.; lx0 = None; reacts = []
    for k, r in enumerate(rows):
        t = k / HZ
        if r[ix['blink']] > .5 and was <= .5: blinks.append(round(t, 3))
        was = r[ix['blink']]
        if lx0 is not None and abs(r[ix['lx']] - lx0) > .12: sacc.append(round(t, 3))
        lx0 = r[ix['lx']]
    for (t0, pre, peak, att, hold, dec, tgt), m in zip(getattr(A, 'reactions', []), getattr(A, 'react_meta', [])):
        reacts.append(dict(onset=round(t0, 3), face=pre, peak=round(peak, 3), cause=m.get('cause'), look=tgt))
    lip = getattr(A, 'lip', False)
    return dict(blinks=blinks, saccades=sacc, reactions=reacts, talk=[(round(a, 3), round(b, 3)) for a, b in A.talk], lip_driven=lip,
                model=(A.spec.get('face_model') or (C.plan.get('face') or {}).get('model') or 'legacy'), duration=len(rows) / HZ)


def audit_faces(C, tracks, expressions, min_blink_rate=4., max_blink_rate=36., stare_max=12.):
    """What a viewer reads as a dead, nervous or unmotivated face, measured on the rows themselves (tracks = {actor: rows} from build_all):
      clignements          blink rate outside human bounds (min_blink_rate .. max_blink_rate per minute, over at least 10 s) or a blink longer than 0.45 s / shorter than 0.1 s
      regard_fixe          no blink for more than stare_max seconds
      oeil_saute           the pupils move by more than 0.45 of their range in one 1/120 s step (a saccade takes at least 21 ms)
      expression_sans_cause  the dominant expression changes with no `emote` / `react` / `tension` beat in the window that explains it (the « emoji » defect)
      expression_clignote  more than 4 changes of dominant expression in one second
      saut_intensite       the dominant expression's intensity jumps by more than 0.25 in one step (outside a blink)
      bouche_sans_parole   the mouth opens (beyond a breath) while the actor neither talks nor reacts
    Returns blocking.Violation objects."""
    from .blocking import Violation
    v = []; ix = {c: i for i, c in enumerate(FACE_COLS)}
    for aid, rows in tracks.items():
        A = C.actors[aid]; T = len(rows) / HZ; flagged = set()
        blink_runs = []; run0 = None
        for k, r in enumerate(rows):
            b = r[ix['blink']] > .5
            if b and run0 is None: run0 = k
            if not b and run0 is not None: blink_runs.append((run0 / HZ, (k - run0) / HZ)); run0 = None
        if T >= 10.:
            rate = len(blink_runs) / T * 60.
            if not (min_blink_rate <= rate <= max_blink_rate): v.append(Violation('clignements', f"{aid} cligne {rate:.0f} fois par minute (humain : {min_blink_rate:.0f} à {max_blink_rate:.0f})", None, aid, rate=rate))
            last = 0.
            for (t0, d) in blink_runs + [(T, 0.)]:
                if t0 - last > stare_max: v.append(Violation('regard_fixe', f"{aid} ne cligne pas pendant {t0 - last:.0f} s à partir de {last:.0f} s", last, aid))
                last = t0 + d
        for (t0, d) in blink_runs:
            if d > .45 or d < .02: v.append(Violation('clignements', f"{aid} : un clignement dure {d * 1000:.0f} ms à {t0:.1f} s", t0, aid, dur=d))
        # emotion changes need a cause
        causes = [t for (t, f, i) in getattr(A, 'tonic', [])] + [(t0 - .02) for (t0, *_r) in getattr(A, 'reactions', [])]
        tails = [t + 1.3 for t in [t for (t, f, i) in getattr(A, 'tonic', [])]] + [(t0 + att + hold + dec + .15) for (t0, p_, pk, att, hold, dec, tg) in getattr(A, 'reactions', [])]
        windows = [(a, b) for a, b in zip(causes, tails)]
        changes = []; prev_e = None
        for k, r in enumerate(rows):
            e = int(r[ix['e1']]); t = k / HZ
            if prev_e is not None and e != prev_e and r[ix['i1']] > .05:
                changes.append(t)
                if not any(a <= t <= b for a, b in windows) and ('cause', int(t)) not in flagged:
                    flagged.add(('cause', int(t))); v.append(Violation('expression_sans_cause', f"{aid} : l'expression passe de « {expressions[prev_e]} » à « {expressions[e]} » à {t:.2f} s sans événement qui l'explique", t, aid))
            prev_e = e
            if k and abs(r[ix['lx']] - rows[k - 1][ix['lx']]) > .45 and ('jump', int(t)) not in flagged: flagged.add(('jump', int(t))); v.append(Violation('oeil_saute', f"{aid} : les pupilles sautent de {abs(r[ix['lx']] - rows[k - 1][ix['lx']]):.2f} en 8 ms à {t:.2f} s", t, aid))
            if k and r[ix['e1']] == rows[k - 1][ix['e1']] and abs(r[ix['i1']] - rows[k - 1][ix['i1']]) > .25 and ('pop', int(t)) not in flagged:
                flagged.add(('pop', int(t))); v.append(Violation('saut_intensite', f"{aid} : l'intensité de l'expression saute de {abs(r[ix['i1']] - rows[k - 1][ix['i1']]):.2f} en une image à {t:.2f} s", t, aid))
        for i0, t in enumerate(changes):
            if sum(1 for u in changes[i0:] if u - t <= 1.) > 4: v.append(Violation('expression_clignote', f"{aid} : plus de 4 changements d'expression en une seconde à {t:.1f} s", t, aid)); break
        reacts = [(t0, t0 + att + hold + dec + .3) for (t0, p_, pk, att, hold, dec, tg) in getattr(A, 'reactions', [])]
        tens = [(e['t'], e['until']) for e in C.events if e['who'] == aid and e['kind'] == 'tension']
        for k in range(0, len(rows), 6):
            t = k / HZ; mo = rows[k][ix['mo']]
            if mo > .12 and not any(a - .2 <= t <= b + .2 for a, b in A.talk) and not any(a <= t <= b for a, b in reacts) and not any(a <= t <= b for a, b in tens) and ('mouth', int(t)) not in flagged:
                flagged.add(('mouth', int(t))); v.append(Violation('bouche_sans_parole', f"{aid} : la bouche s'ouvre ({mo:.2f}) à {t:.1f} s sans parole ni réaction", t, aid))
    return v


# ------------------------------------------------------------------------------------------------------------------------- film time <-> stage rows
def stage_rows(rows, t0, n, fps):
    """the rows a stage must store: frame j of a stage that starts at film time `t0` plays the face of FILM time t0 + j / fps. `rows` are indexed from the start of the FILM
    (build() and build_all() return them that way). `director.build` currently indexes them with the stage-local time, so every stage but the first plays the face of the
    wrong instant (measured: 581 of 591 sampled frames of the continuity film; see docs/FACE_PHYSICS_20261029.md): this is the function that fixes it."""
    return [[round(v, 4) for v in rows[min(len(rows) - 1, int(round(max(0., t0 + j / fps) * HZ)))]] for j in range(n)]


def audit_stage_sync(c, tracks, step=5, tol=1e-3):
    """`visage_décalé`: the face rows stored in the stages of a contract must be those of the film time of each frame (tracks = {actor: rows} from build_all).
    One violation per actor, with the share of sampled frames that play another instant's face."""
    from .blocking import Violation
    v = []; fps = c['fps']
    for aid, rows in tracks.items():
        bad = tot = 0; first = None
        for st in c['stages']:
            fr = (st.get('faces') or {}).get(aid)
            if not fr: continue
            for j in range(0, min(len(fr), int(round((st['t1'] - st['t0']) * fps))), step):
                want = rows[min(len(rows) - 1, int(round((st['t0'] + j / fps) * HZ)))]; tot += 1
                if max(abs(a - b) for a, b in zip(fr[j], want)) > tol:
                    bad += 1; first = first if first is not None else (st['id'], st['t0'] + j / fps)
        if tot and bad / tot > .05:
            v.append(Violation('visage_décalé', f"{aid} : {bad} images sur {tot} jouent le visage d'un autre instant (premier écart : plan {first[0]}, {first[1]:.2f} s) : les lignes de visage doivent être lues à l'heure du FILM, pas à l'heure du plan", first[1], aid, bad=bad, total=tot))
    return v
